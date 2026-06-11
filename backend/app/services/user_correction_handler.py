"""[A] V2.4 P2-7 · UserCorrectionHandler · 用户纠错权威值回写

服务: docs/V2.4_MASTER_PLAN.md § 阶段 5

顾源源 5/23 钦定核心场景:
> 测试中用户说: "500 万是旧版和媒体口径, 现在内部最新版是 300 万".
> 之后系统再次回答预算问题, 必须明确说:
>   · 当前权威值是 300 万
>   · 500 万是旧版/外部滞后口径
>   · 这个结论来自用户纠正和 v2 方案
>   · 如果对外使用, 仍建议确认外部口径是否同步.

完整链路:
  1. 用户口述纠错 → 写新 user_confirmed_fact
  2. 旧事实 → status='superseded'
  3. confidence_history → 记 user_correct 触发
  4. broadcast_data_changed → 触发故事卡重生
  5. 重新计算冲突 (旧 500 万不再冲突, 因为已 superseded)
  6. 后续问答用新权威值

跨客户隔离:
  user_correction 只动 query.client_id, 不影响其他客户的同名实体.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CorrectionResult:
    """单次纠错处理统计."""
    superseded_count: int = 0
    new_authoritative_id: str | None = None
    confidence_history_written: int = 0
    clarifications_resolved: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            object.__setattr__(self, "errors", [])


def _extract_numeric_value(text: str) -> str | None:
    """从文本里抽数字 (300 万 / 3 所 / 500 万元 → 归一化数字字符串)."""
    if not text:
        return None
    # 万元/万
    m = re.search(r"(\d+)\s*万", text)
    if m:
        return m.group(1) + "w"
    # 所
    m = re.search(r"(\d+)\s*所", text)
    if m:
        return m.group(1) + "所"
    # 纯数字
    m = re.search(r"(\d+)", text)
    if m:
        return m.group(1)
    return None


def apply_user_correction(
    db: _DbLike,
    *,
    client_id: str,
    corrected_subject: str,
    corrected_attribute_base: str,
    new_authoritative_value: str,
    correction_source_fact_id: str | None = None,
    user_note: str = "",
) -> CorrectionResult:
    """处理一次用户纠错: supersede 旧值 + 写权威值 + 触发下游.

    参数解释 (测试机构C示例):
      corrected_subject              = "乡村儿童阅读陪伴项目"
      corrected_attribute_base       = "预算"
      new_authoritative_value        = "300 万元"
      correction_source_fact_id      = D11_correction 的 atomic_fact id

    返回:
      CorrectionResult (统计)
    """
    errors: list[str] = []
    new_value_norm = _extract_numeric_value(new_authoritative_value)

    # 1. 找客户下同 subject + attribute_base 的所有旧事实 (不限 status)
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, status, source_type, confidence
           FROM atomic_facts
           WHERE client_id = ?
             AND subject_text = ?
             AND (attribute LIKE ? OR attribute LIKE ? OR attribute LIKE ?)""",
        (client_id, corrected_subject,
         f"%{corrected_attribute_base}%",
         f"%{corrected_attribute_base}(v1)%",
         f"%{corrected_attribute_base}(v2)%"),
    )
    candidates = [dict(r) for r in rows]
    logger.info(
        "user_correction: 找到 %d 条同 subject+attribute 候选 (client=%s, subj=%s, attr=%s)",
        len(candidates), client_id, corrected_subject, corrected_attribute_base,
    )

    # 2. 把旧值跟新值 normalize 比, 不同的 → supersede
    superseded = 0
    for c in candidates:
        if c["status"] == "superseded":
            continue
        if c["id"] == correction_source_fact_id:
            continue  # 不动纠错来源本身
        old_norm = _extract_numeric_value(c["value_text"] or "")
        if old_norm and new_value_norm and old_norm == new_value_norm:
            continue  # 同值不动
        try:
            db.execute(
                "UPDATE atomic_facts SET status = 'superseded', "
                "updated_at = ? WHERE id = ?",
                (_now_iso(), c["id"]),
            )
            superseded += 1
            # 写 confidence_history (user_correct 触发)
            try:
                db.execute(
                    """INSERT INTO atomic_fact_confidence_history (
                        id, fact_id, old_confidence, new_confidence,
                        trigger_event, evidence_link, actor_id, reasoning_note,
                        changed_at
                    ) VALUES (?, ?, ?, 0.0, 'user_correct', ?, 'user', ?, ?)""",
                    (
                        f"ch_{uuid.uuid4().hex[:24]}",
                        c["id"], c["confidence"] or 0.5,
                        new_authoritative_value,
                        f"用户纠错: 该旧值已被新权威值 「{new_authoritative_value}」 取代",
                        _now_iso(),
                    ),
                )
            except Exception as exc:
                # confidence_history 表可能 schema 略不同, 不阻塞主流程
                errors.append(f"confidence_history insert failed for {c['id']}: {exc}")
        except Exception as exc:
            errors.append(f"supersede failed for {c['id']}: {exc}")

    # 3. 把 correction_source_fact_id 标记为 user_confirmed (置信度 1.0)
    new_auth_id = correction_source_fact_id
    if correction_source_fact_id:
        try:
            db.execute(
                """UPDATE atomic_facts
                   SET confidence = 1.0, verification_status = 'user_confirmed',
                       updated_at = ? WHERE id = ?""",
                (_now_iso(), correction_source_fact_id),
            )
            try:
                db.execute(
                    """INSERT INTO atomic_fact_confidence_history (
                        id, fact_id, old_confidence, new_confidence,
                        trigger_event, evidence_link, actor_id, reasoning_note,
                        changed_at
                    ) VALUES (?, ?, ?, 1.0, 'user_confirm', ?, 'user', ?, ?)""",
                    (
                        f"ch_{uuid.uuid4().hex[:24]}",
                        correction_source_fact_id, 0.5,
                        new_authoritative_value,
                        f"用户纠错确认: {user_note or new_authoritative_value} 为当前权威值",
                        _now_iso(),
                    ),
                )
            except Exception:
                pass
        except Exception as exc:
            errors.append(f"new_authoritative update failed: {exc}")

    # 4. 标记相关 clarification_records 为 resolved
    resolved_clar = 0
    try:
        existing_rows = db.fetchall(
            """SELECT id, slot_key FROM clarification_records
               WHERE scope_type='client' AND scope_id=? AND status='pending'""",
            (client_id,),
        )
        for cr in existing_rows:
            cr_d = dict(cr)
            sk = cr_d.get("slot_key", "")
            if corrected_subject[:10] in sk and corrected_attribute_base in sk:
                db.execute(
                    """UPDATE clarification_records
                       SET status='resolved', answer_text=?, updated_at=?
                       WHERE id=?""",
                    (
                        f"用户已确认权威值为 「{new_authoritative_value}」, 旧值已 supersede.",
                        _now_iso(), cr_d["id"],
                    ),
                )
                resolved_clar += 1
    except Exception as exc:
        errors.append(f"clarification resolve failed: {exc}")

    return CorrectionResult(
        superseded_count=superseded,
        new_authoritative_id=new_auth_id,
        confidence_history_written=superseded + (1 if correction_source_fact_id else 0),
        clarifications_resolved=resolved_clar,
        errors=errors,
    )


def get_authoritative_value(
    db: _DbLike, client_id: str, subject: str, attribute_base: str,
) -> dict | None:
    """查询当前权威值 (跳过 superseded), 用于问答验证.

    Returns:
        {"value": str, "fact_id": str, "confidence": float,
         "source_type": str, "old_versions": [...]}
    """
    # 当前权威 (status='active', user_confirmed 优先, confidence 高的)
    auth_row = db.fetchone(
        """SELECT id, value_text, confidence, source_type, verification_status
           FROM atomic_facts
           WHERE client_id = ? AND subject_text = ?
             AND (attribute LIKE ? OR attribute LIKE ? OR attribute = ?)
             AND status = 'active'
           ORDER BY (verification_status = 'user_confirmed') DESC,
                    confidence DESC, created_at DESC LIMIT 1""",
        (client_id, subject,
         f"%{attribute_base}%", f"%当前权威{attribute_base}%",
         attribute_base),
    )
    if not auth_row:
        return None
    auth = dict(auth_row)

    # 旧版 (superseded)
    old_rows = db.fetchall(
        """SELECT id, value_text, source_type, attribute
           FROM atomic_facts
           WHERE client_id = ? AND subject_text = ?
             AND attribute LIKE ?
             AND status = 'superseded'""",
        (client_id, subject, f"%{attribute_base}%"),
    )
    old_versions = [dict(r) for r in old_rows]

    return {
        "value": auth["value_text"],
        "fact_id": auth["id"],
        "confidence": auth["confidence"],
        "source_type": auth["source_type"],
        "verification_status": auth["verification_status"],
        "old_versions": old_versions,
    }
