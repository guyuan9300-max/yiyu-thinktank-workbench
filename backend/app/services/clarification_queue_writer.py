"""[A] V2.3 阶段 3 P1 · clarification_queue_writer · 把 cross_source 嫌疑对写进澄清队列

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md § 五 4 层澄清(L1 事实)+ B AI K-3 异议 1

接通 cross_source_check + clarification_records (B AI 推荐 V2.3 空表复用)

clarification_records schema:
  scope_type / scope_id (client_id) / slot_key / question / status / answer_text /
  write_scope_json / resolved_fact_ids_json / reusable / created_at

把 cross_source 嫌疑对转成"用户可回答的问题":
  "心灵魔法学院" vs "心理魔法学院" → question="A组织项目, 应该是'心灵魔法学院'还是'心理魔法学院'? (同音字疑似)"
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_cross_source_candidate(
    db: _DbLike,
    *,
    client_id: str,
    text_a: str,
    text_b: str,
    suspicion: float,
    layer: str = "char_similarity",
    fact_ids: list[str] | None = None,
) -> str:
    """把一个跨源嫌疑对写到 clarification_records 等用户裁决.

    Returns:
        clarification_record_id
    """
    rec_id = f"clar_{uuid.uuid4().hex[:24]}"
    now = _now_iso()

    # 生成可回答的问题
    if suspicion >= 0.95:
        question = f"系统判断「{text_a}」跟「{text_b}」是同一概念 (相似度 {suspicion:.2f}), 是否确认合并?"
    elif suspicion >= 0.6:
        question = f"「{text_a}」和「{text_b}」相似度 {suspicion:.2f} (可能同音字/同义), 它们指同一概念吗?"
    else:
        question = f"「{text_a}」vs「{text_b}」 (相似度 {suspicion:.2f}, 低嫌疑)"

    slot_key = f"cross_source/{layer}/{text_a[:20]}__{text_b[:20]}"
    write_scope = {
        "client_id": client_id,
        "suspicion_score": suspicion,
        "layer": layer,
        "candidates": [text_a, text_b],
    }

    db.execute(
        """INSERT INTO clarification_records (
            id, scope_type, scope_id, slot_key, question, status,
            write_scope_json, resolved_fact_ids_json, reusable,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, 0, ?, ?)""",
        (
            rec_id, "client", client_id, slot_key, question,
            json.dumps(write_scope, ensure_ascii=False),
            json.dumps(fact_ids or [], ensure_ascii=False),
            now, now,
        ),
    )
    return rec_id


def batch_write_scan_results(
    db: _DbLike, client_id: str, candidates: list[dict[str, Any]],
    threshold: float = 0.6,
) -> dict[str, int]:
    """把 cross_source scan 结果批量写入 clarification_records.

    Args:
        candidates: scan_client_for_cross_source_candidates 返回值
        threshold: 只写 suspicion >= threshold 的

    Returns:
        {"written": N, "skipped_low_suspicion": N, "skipped_dup": N}
    """
    stats = {"written": 0, "skipped_low_suspicion": 0, "skipped_dup": 0}
    for c in candidates:
        if c.get("suspicion", 0) < threshold:
            stats["skipped_low_suspicion"] += 1
            continue
        # 去重 (按 slot_key)
        slot_key = f"cross_source/char_similarity/{c['text_a'][:20]}__{c['text_b'][:20]}"
        existing = db.fetchone(
            "SELECT id FROM clarification_records WHERE slot_key = ?",
            (slot_key,),
        )
        if existing:
            stats["skipped_dup"] += 1
            continue
        write_cross_source_candidate(
            db, client_id=client_id,
            text_a=c["text_a"], text_b=c["text_b"],
            suspicion=c["suspicion"],
            layer="char_similarity",
        )
        stats["written"] += 1
    return stats


def list_pending_clarifications(
    db: _DbLike, client_id: str, limit: int = 50,
) -> list[dict[str, Any]]:
    """拉某客户的 pending 澄清队列 (按 created_at DESC)."""
    rows = db.fetchall(
        """SELECT * FROM clarification_records
           WHERE scope_type = 'client' AND scope_id = ? AND status = 'pending'
           ORDER BY created_at DESC LIMIT ?""",
        (client_id, limit),
    )
    return [dict(r) for r in rows]
