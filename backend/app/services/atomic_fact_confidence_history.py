"""[A] V2.3 阶段 1 A 补充 1 · atomic_fact_confidence_history · 置信度时间序列

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md A 视角 § 末尾 补充 1

定位:
  用户甲蓝图 § 四 机制一 原话: "置信度不是固定数字, 而是不断变化的状态"
  当前 atomic_facts.confidence 是单值字段 — 看不到演化.

  本表记录每条 fact 的 confidence 变化轨迹:
    · 何时变化
    · 触发事件 (user_confirm / cross_source / superseded / outdated)
    · 旧值 / 新值
    · 证据链接

  用途:
    1. 用户在战略陪伴看到 "AI 这条事实置信度 0.65 → 0.85, 因为客户官方文件确认"
    2. 数据中心追溯 "为什么这条事实被推翻 / 升级"
    3. AI 学习 "哪些 trigger 真有效"
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Protocol


# ─── 类型 ──────────────────────────────────────────────


ConfidenceTrigger = Literal[
    "user_confirm",         # 用户在战略陪伴采纳 → 置信度升级
    "user_correct",         # 用户修正值 → 旧值 supersede + 新值高置信
    "user_dismiss",         # 用户标"不重要" → 降权
    "cross_source_confirm", # 跨源印证(多源指向同一事实)→ 提高
    "cross_source_conflict", # 跨源冲突 → 降低 (等用户裁决)
    "superseded_by_new",    # 被新版本 supersede → 旧版本归零
    "outdated_decay",       # 时间衰减(老事实, 无新证据)→ 降低
    "llm_self_verify",      # L3 自校验调整
    "initial_extract",      # 首次抽取 (initial_confidence 写入)
]


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


# ─── Schema ──────────────────────────────────────────


def ensure_schema(db: _DbLike) -> None:
    """创建 atomic_fact_confidence_history 表 (idempotent)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS atomic_fact_confidence_history (
            id TEXT PRIMARY KEY,
            fact_id TEXT NOT NULL,                  -- 指向 atomic_facts.id
            old_confidence REAL,                    -- 旧值 (initial_extract 时为 null)
            new_confidence REAL NOT NULL,           -- 新值
            trigger_event TEXT NOT NULL,            -- ConfidenceTrigger enum
            evidence_link TEXT,                     -- 触发证据 (source_id / chunk_id / user_action_id)
            actor_id TEXT,                          -- 谁触发 (user / ai / system)
            reasoning_note TEXT,                    -- 短说明 (≤200 字)
            changed_at TEXT NOT NULL
        )
        """
    )
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_fact_conf_hist_fact ON atomic_fact_confidence_history (fact_id, changed_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_fact_conf_hist_trigger ON atomic_fact_confidence_history (trigger_event)",
        "CREATE INDEX IF NOT EXISTS idx_fact_conf_hist_actor ON atomic_fact_confidence_history (actor_id)",
    ]:
        db.execute(sql)


# ─── Utility ────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Main API ────────────────────────────────────────


def record_confidence_change(
    db: _DbLike,
    *,
    fact_id: str,
    new_confidence: float,
    trigger_event: str,
    old_confidence: float | None = None,
    evidence_link: str | None = None,
    actor_id: str | None = None,
    reasoning_note: str | None = None,
) -> str:
    """记录一次 fact 置信度变化. 返回 history_id.

    Args:
        fact_id: atomic_facts.id
        new_confidence: 新置信度
        trigger_event: ConfidenceTrigger enum
        old_confidence: 旧值 (initial_extract 时可空)
        evidence_link: 触发证据 (source_id / chunk_id / user_action_id)
        actor_id: 谁触发
        reasoning_note: 短说明

    Side-effect:
        本函数只写历史表, 不改 atomic_facts.confidence (上层负责).
    """
    now = _now_iso()
    history_id = f"conf_hist_{uuid.uuid4().hex[:24]}"
    db.execute(
        """
        INSERT INTO atomic_fact_confidence_history (
            id, fact_id, old_confidence, new_confidence,
            trigger_event, evidence_link, actor_id, reasoning_note,
            changed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            history_id, fact_id, old_confidence, new_confidence,
            trigger_event, evidence_link, actor_id,
            (reasoning_note or "")[:200], now,
        ),
    )
    return history_id


def list_history_for_fact(db: _DbLike, fact_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """拉某 fact 的置信度演化历史."""
    rows = db.fetchall(
        """SELECT * FROM atomic_fact_confidence_history
           WHERE fact_id = ? ORDER BY changed_at DESC LIMIT ?""",
        (fact_id, limit),
    )
    return [dict(r) for r in rows]


def get_current_trend(db: _DbLike, fact_id: str) -> str:
    """看某 fact 最近 5 次变化趋势 (rising / falling / stable / mixed)."""
    rows = db.fetchall(
        """SELECT old_confidence, new_confidence FROM atomic_fact_confidence_history
           WHERE fact_id = ? ORDER BY changed_at DESC LIMIT 5""",
        (fact_id,),
    )
    if not rows:
        return "stable"
    deltas: list[float] = []
    for r in rows:
        old = float(r["old_confidence"]) if r["old_confidence"] is not None else None
        new = float(r["new_confidence"]) if r["new_confidence"] is not None else None
        if old is not None and new is not None:
            deltas.append(new - old)
    if not deltas:
        return "stable"
    pos = sum(1 for d in deltas if d > 0.05)
    neg = sum(1 for d in deltas if d < -0.05)
    if pos > neg + 1: return "rising"
    if neg > pos + 1: return "falling"
    if pos > 0 and neg > 0: return "mixed"
    return "stable"
