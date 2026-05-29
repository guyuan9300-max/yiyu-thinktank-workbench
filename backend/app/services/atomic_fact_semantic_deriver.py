"""[A] V2.4 P0-1 · AtomicFactSemanticDeriver · 原子事实 → 语义表派生器

服务: docs/V2.4_MASTER_PLAN.md § 阶段 1

把 atomic_facts (第 3 层原料) 自动派生到 4 张语义表 (第 5/6 层):

  atomic_facts 中的内容           → 派生到                       → 故事卡段
  ─────────────────────────────────────────────────────────────────────
  attribute 含日期 / time_anchor  → event_line_activities         → 段 4 时间线
  attribute 含'风险'/'卡点'/'担忧' → risk_signals                  → 段 8 风险
  attribute 含'承诺'/'下一步'/'交付' → commitments                  → 段 9 下一步
  attribute 含'判断'/'核心判断'/'用户判断' → strategic_thought_insights → 段 6 关键判断

幂等: 每次跑前按 source_fingerprint (atomic_fact_id) 去重, 不重复派生.

调用方:
  · IngestPipeline.ingest() 写完 atomic_facts 自动调 derive_all(client_id) (推荐)
  · 后台任务定时跑 (兜底)
  · 测试 runner 手动调
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
class DeriveResult:
    """单次派生统计."""
    event_line_activities_new: int = 0
    risk_signals_new: int = 0
    commitments_new: int = 0
    strategic_insights_new: int = 0
    skipped_duplicate: int = 0
    error_count: int = 0


# ─── 1 · 时间线派生 ─────────────────────────────────────


_TIMELINE_ATTR_KEYWORDS = [
    "日期", "时间", "出席", "首次沟通", "对外公开",
    "行动", "发生时间", "举办", "上线", "发布",
]


def _attr_indicates_timeline(attr: str, value: str) -> bool:
    """判断 atomic_fact 是否应派生为 timeline event."""
    if not attr:
        return False
    if any(kw in attr for kw in _TIMELINE_ATTR_KEYWORDS):
        return True
    # value 含 YYYY-MM-DD 或 "X月X日" 也算
    if value and (re.search(r"\d{4}-\d{2}-\d{2}", value) or re.search(r"\d+\s*月\s*\d+\s*日", value)):
        return True
    return False


def derive_event_line_activities(db: _DbLike, client_id: str) -> int:
    """atomic_facts → event_line_activities.

    策略:
      1. 找 client 下所有 event_lines
      2. 找 atomic_facts 中:
         · time_anchor 非空, OR
         · attribute / value 含日期标记
      3. 用 source_fingerprint=atomic_fact_id 去重
      4. 写入 event_line_activities
    """
    # 找 client 的 event_line (没有就跳过)
    el_rows = db.fetchall(
        "SELECT id FROM event_lines WHERE primary_client_id = ? LIMIT 1",
        (client_id,),
    )
    if not el_rows:
        logger.debug("派生时间线: client %s 无 event_line, 跳过", client_id)
        return 0
    event_line_id = dict(el_rows[0])["id"]

    # 拉 atomic_facts
    fact_rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type,
                  time_anchor, evidence_text, created_at
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in fact_rows]

    # 已派生过的 source_id (用 source_id 字段 = atomic_fact_id)
    existing_rows = db.fetchall(
        """SELECT source_id FROM event_line_activities
           WHERE event_line_id = ? AND source_type = 'atomic_fact'""",
        (event_line_id,),
    )
    existing_ids = {dict(r)["source_id"] for r in existing_rows}

    new_count = 0
    for f in facts:
        # 必须有时间锚 OR 文本含日期
        has_time = f["time_anchor"] or _attr_indicates_timeline(f["attribute"], f["value_text"])
        if not has_time:
            continue
        if f["id"] in existing_ids:
            continue

        happened_at = f["time_anchor"] or _extract_date_from_text(
            f"{f['attribute']} {f['value_text']}"
        ) or f["created_at"]

        title = f"{f['subject_text']} · {f['attribute']}"[:200]
        summary = (f["value_text"] or "")[:500]

        actor_name = f["subject_text"][:80] if "李" in (f["subject_text"] or "") or \
                     "王" in (f["subject_text"] or "") or "陈" in (f["subject_text"] or "") else "sys"

        try:
            db.execute(
                """INSERT INTO event_line_activities (
                    id, event_line_id, source_type, source_id, happened_at,
                    actor_id, actor_name, title, summary, metadata_json,
                    is_key, created_at
                ) VALUES (?, ?, 'atomic_fact', ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    f"ela_{uuid.uuid4().hex[:24]}",
                    event_line_id, f["id"], happened_at,
                    None, actor_name, title, summary,
                    json.dumps({
                        "source_type": f["source_type"],
                        "atomic_fact_subject": f["subject_text"],
                        "atomic_fact_attribute": f["attribute"],
                    }, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            new_count += 1
        except Exception as exc:
            logger.warning("派生 event_line_activities 失败 fact=%s: %s", f["id"], exc)
    return new_count


def _extract_date_from_text(text: str) -> str | None:
    """从中文文本里抽 ISO date (X月X日 → 2026-MM-DD, 假设当年)."""
    if not text:
        return None
    # 优先 ISO
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1) + "T00:00:00+00:00"
    # 中文 "5月6日" / "5 月 6 日"
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return f"2026-{month:02d}-{day:02d}T00:00:00+00:00"
    # "5/6"
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"2026-{month:02d}-{day:02d}T00:00:00+00:00"
    return None


# ─── 2 · 风险信号派生 ───────────────────────────────────


_RISK_ATTR_KEYWORDS = [
    "风险", "卡点", "担忧", "隐患", "隐性风险",
    "服务质量失控", "扩张过快", "宣传压力", "用户担忧",
]


def derive_risk_signals(db: _DbLike, client_id: str) -> int:
    """atomic_facts attribute=风险等 → risk_signals."""
    fact_rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type, confidence
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in fact_rows]

    existing_rows = db.fetchall(
        """SELECT source_id FROM risk_signals
           WHERE client_id = ? AND source_type = 'atomic_fact'""",
        (client_id,),
    )
    existing_ids = {dict(r)["source_id"] for r in existing_rows}

    new_count = 0
    for f in facts:
        attr = f["attribute"] or ""
        value = f["value_text"] or ""
        # attribute 或 value 命中风险关键词
        if not any(kw in attr for kw in _RISK_ATTR_KEYWORDS):
            if not any(kw in value for kw in ["风险", "失控", "扩张过快", "宣传压力"]):
                continue
        if f["id"] in existing_ids:
            continue

        # severity 由 confidence + attribute 决定
        conf = f["confidence"] or 0.5
        if "隐性" in attr or "失控" in value:
            severity = "high"
        elif conf >= 0.85:
            severity = "high"
        elif conf >= 0.6:
            severity = "medium"
        else:
            severity = "low"

        title = f"{f['subject_text']} · {attr}"[:200]
        description = value[:500]

        try:
            now = _now_iso()
            db.execute(
                """INSERT INTO risk_signals (
                    id, client_id, signal_kind, title, description,
                    severity, related_term_ids_json, source_type, source_id,
                    captured_at, status, resolution_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, '[]', 'atomic_fact', ?, ?, 'active', '', ?, ?)""",
                (
                    f"risk_{uuid.uuid4().hex[:24]}",
                    client_id, "operational_risk", title, description,
                    severity, f["id"], now, now, now,
                ),
            )
            new_count += 1
        except Exception as exc:
            logger.warning("派生 risk_signals 失败 fact=%s: %s", f["id"], exc)
    return new_count


# ─── 3 · 承诺/任务派生 ──────────────────────────────────


_COMMITMENT_ATTR_KEYWORDS = [
    "承诺", "下一步", "交付", "提供", "回复",
    "完成时间", "deadline", "答应",
]


def derive_commitments(db: _DbLike, client_id: str) -> int:
    """atomic_facts attribute=承诺等 → commitments."""
    fact_rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type, time_anchor
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in fact_rows]

    existing_rows = db.fetchall(
        """SELECT source_id FROM commitments
           WHERE client_id = ? AND source_type = 'atomic_fact'""",
        (client_id,),
    )
    existing_ids = {dict(r)["source_id"] for r in existing_rows}

    new_count = 0
    for f in facts:
        attr = f["attribute"] or ""
        value = f["value_text"] or ""
        if not any(kw in attr for kw in _COMMITMENT_ATTR_KEYWORDS):
            continue
        if f["id"] in existing_ids:
            continue

        committer = f["subject_text"][:80]
        recipient = "项目方"  # 默认; 解析不出来时
        content = value[:500]
        deadline = _extract_date_from_text(value) or _extract_date_from_text(attr)

        try:
            now = _now_iso()
            db.execute(
                """INSERT INTO commitments (
                    id, client_id, committer, recipient, commitment_type,
                    content, deadline, status, related_term_ids_json,
                    source_type, source_id, fulfilled_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'delivery', ?, ?, 'pending', '[]',
                          'atomic_fact', ?, NULL, ?, ?)""",
                (
                    f"com_{uuid.uuid4().hex[:24]}",
                    client_id, committer, recipient,
                    content, deadline, f["id"], now, now,
                ),
            )
            new_count += 1
        except Exception as exc:
            logger.warning("派生 commitments 失败 fact=%s: %s", f["id"], exc)
    return new_count


# ─── 4 · 战略判断派生 ───────────────────────────────────


_INSIGHT_ATTR_KEYWORDS = [
    "判断", "核心判断", "用户判断", "我方判断", "下周重点",
    "观察", "意见", "评估", "AI 判断",
]


def derive_strategic_insights(db: _DbLike, client_id: str) -> int:
    """atomic_facts attribute=判断等 → strategic_thought_insights."""
    fact_rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type, confidence
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in fact_rows]

    # 拉 client name 写 client_name 字段
    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = dict(client_row)["name"] if client_row else ""

    existing_rows = db.fetchall(
        """SELECT source_fingerprint FROM strategic_thought_insights
           WHERE client_id = ? AND source_fingerprint LIKE 'af:%'""",
        (client_id,),
    )
    existing_fps = {dict(r)["source_fingerprint"] for r in existing_rows}

    new_count = 0
    for f in facts:
        attr = f["attribute"] or ""
        value = f["value_text"] or ""
        if not any(kw in attr for kw in _INSIGHT_ATTR_KEYWORDS):
            continue
        fp = f"af:{f['id']}"
        if fp in existing_fps:
            continue

        # insight_type 推断
        if "用户" in attr:
            insight_type = "user_observation"
        elif "我方" in attr:
            insight_type = "yiyu_advisory"
        elif "下周重点" in attr or "下一步" in attr:
            insight_type = "next_step"
        else:
            insight_type = "strategic_shift"

        title = f"{f['subject_text']} · {attr}"[:200]
        signal_score = int((f["confidence"] or 0.5) * 100)

        try:
            now = _now_iso()
            db.execute(
                """INSERT INTO strategic_thought_insights (
                    id, scope_type, client_id, client_name,
                    project_module_id, project_module_name,
                    title, insight_type, insight_text,
                    future_judgment, recommended_action,
                    evidence_summary, evidence_labels_json,
                    source_refs_json, source_fingerprint,
                    signal_score, raw_payload_json,
                    is_favorite, is_deleted,
                    generated_at, created_at, updated_at
                ) VALUES (?, 'client', ?, ?, NULL, NULL,
                          ?, ?, ?,
                          '', ?,
                          ?, '[]', ?, ?,
                          ?, '{}',
                          0, 0,
                          ?, ?, ?)""",
                (
                    f"sti_{uuid.uuid4().hex[:24]}",
                    client_id, client_name,
                    title, insight_type, value[:1000],
                    "",  # recommended_action (留空)
                    value[:500], json.dumps([f["source_type"]], ensure_ascii=False),
                    fp, signal_score,
                    now, now, now,
                ),
            )
            new_count += 1
        except Exception as exc:
            logger.warning("派生 strategic_insights 失败 fact=%s: %s", f["id"], exc)
    return new_count


# ─── 主入口 · derive_all ────────────────────────────────


def derive_all(db: _DbLike, client_id: str) -> DeriveResult:
    """一次跑全部 4 个派生函数."""
    try:
        ela = derive_event_line_activities(db, client_id)
    except Exception as exc:
        logger.exception("derive_event_line_activities 失败: %s", exc)
        ela = 0
    try:
        risk = derive_risk_signals(db, client_id)
    except Exception as exc:
        logger.exception("derive_risk_signals 失败: %s", exc)
        risk = 0
    try:
        com = derive_commitments(db, client_id)
    except Exception as exc:
        logger.exception("derive_commitments 失败: %s", exc)
        com = 0
    try:
        insight = derive_strategic_insights(db, client_id)
    except Exception as exc:
        logger.exception("derive_strategic_insights 失败: %s", exc)
        insight = 0
    return DeriveResult(
        event_line_activities_new=ela,
        risk_signals_new=risk,
        commitments_new=com,
        strategic_insights_new=insight,
    )
