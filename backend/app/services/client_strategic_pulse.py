"""客户战略脉搏 - 战略陪伴克制版主页数据源.

读 evidence_cards + tasks + event_lines + event_line_activities,
输出 3 个区块:
- weeklyEvents: 本周新动态 (近 7 天关键事实)
- upcomingTodos: 你接下来要做 (按到期紧迫度排序的任务)
- currentBlockers: 当前卡点 (主线层面的阻塞/长期无活动)

本期不调 LLM, 不做业务语义重写; 仅从现有字段过滤+包装.
Phase 2 关系网完善后再升级输出质量.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any


__all__ = ["compute_strategic_pulse", "compute_pulse_summary_for_clients"]


# --- DTO (不可变) ---


@dataclass(frozen=True)
class PulseEvent:
    title: str
    occurred_at: str
    impact: str  # advance / neutral / block
    source_type: str
    source_id: str
    source_label: str


@dataclass(frozen=True)
class PulseTodo:
    title: str
    due_date: str | None
    days_until_due: int | None
    urgency: str  # overdue / today / this_week / later
    source_task_id: str | None
    event_line_id: str | None
    event_line_name: str


@dataclass(frozen=True)
class PulseBlocker:
    title: str
    reason: str
    stuck_days: int
    event_line_id: str
    suggested_action: str


# --- 入口 ---


def compute_strategic_pulse(
    db: sqlite3.Connection,
    client_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """计算指定客户的战略脉搏数据.

    Args:
        db: SQLite 连接 (row_factory 已配置为 Row).
        client_id: 客户 ID.
        now: 当前时间 (注入用于测试); 默认 UTC 现在.

    Returns:
        dict 形如:
        {
            "clientId": str,
            "weekStart": ISO datetime,
            "weekEnd": ISO datetime,
            "weeklyEvents": [...],
            "upcomingTodos": [...],
            "currentBlockers": [...],
            "generatedAt": ISO datetime,
        }
    """
    now = now or datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    today = now.date()

    weekly_events = _fetch_weekly_events(db, client_id, week_start)
    upcoming_todos = _fetch_upcoming_todos(db, client_id, today)
    current_blockers = _fetch_current_blockers(db, client_id, now)

    # P3 · 字典反哺 — 把 task title / event summary 用 canonical name 替换别名
    # 例: "兴盛计划方案" → "测试项目A方案"
    try:
        from app.services.glossary_helpers import canonicalize
        weekly_events = [_canonicalize_event(db, client_id, e, canonicalize) for e in weekly_events]
        upcoming_todos = [_canonicalize_todo(db, client_id, t, canonicalize) for t in upcoming_todos]
        current_blockers = [_canonicalize_blocker(db, client_id, b, canonicalize) for b in current_blockers]
    except Exception:
        pass  # 字典查询失败不阻塞主路径

    return {
        "clientId": client_id,
        "weekStart": week_start.isoformat(),
        "weekEnd": now.isoformat(),
        "weeklyEvents": [_event_to_dict(e) for e in weekly_events],
        "upcomingTodos": [_todo_to_dict(t) for t in upcoming_todos],
        "currentBlockers": [_blocker_to_dict(b) for b in current_blockers],
        "generatedAt": now.isoformat(),
    }


def _canonicalize_event(db, client_id: str, event, canon_fn):
    """对 event 的 title/summary 做字典 canonical 化."""
    if hasattr(event, "_replace"):  # NamedTuple
        kwargs = {}
        for f in event._fields:
            v = getattr(event, f)
            if isinstance(v, str) and v:
                kwargs[f] = canon_fn(db, client_id, v)
        return event._replace(**kwargs) if kwargs else event
    return event


def _canonicalize_todo(db, client_id: str, todo, canon_fn):
    return _canonicalize_event(db, client_id, todo, canon_fn)


def _canonicalize_blocker(db, client_id: str, blocker, canon_fn):
    return _canonicalize_event(db, client_id, blocker, canon_fn)


# --- 数据源 1: 本周新动态 ---


_TEST_QUOTE_SUFFIXES: tuple[str, ...] = (
    # 通用归档动作标记 (任何 *.ext 已进入项目资料层 都被视为系统附件标记, 非真业务事实)
    " 已进入项目资料层",
    " 已作为任务附件进入项目资料库",
    " 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。",
)

_TEST_QUOTE_PREFIXES: tuple[str, ...] = (
    "smoke ",
    "test_",
    "offline upload",
    "progress test",
    "attachment smoke",
    "测试附件",
    "这是烟测附件内容",
    "with_client_test",
    "no_client_test",
    "prog_test",
    "final_test",
)

_TEMPLATE_BLOCKER_PHRASES: tuple[str, ...] = (
    "当前没有特别突出的阻塞",
    "飞书会议按钮联调",
    "预期输出：诊断提纲V1",
)


def _is_test_quote(quote: str) -> bool:
    """识别测试垃圾证据."""
    if not quote or len(quote.strip()) < 8:
        return True
    quote = quote.strip()
    for suffix in _TEST_QUOTE_SUFFIXES:
        if quote.endswith(suffix):
            return True
    for prefix in _TEST_QUOTE_PREFIXES:
        if quote.lower().startswith(prefix.lower()):
            return True
    return False


def _fetch_weekly_events(
    db: sqlite3.Connection,
    client_id: str,
    week_start: datetime,
) -> list[PulseEvent]:
    """读 evidence_cards 近 7 天的事实, 过滤测试垃圾."""
    week_start_iso = week_start.isoformat()
    try:
        rows = db.execute(
            """
            SELECT id, source_type, source_id, normalized_claim, quote,
                   polarity, time_anchor, updated_at
            FROM evidence_cards
            WHERE client_id = ?
              AND updated_at >= ?
            ORDER BY updated_at DESC
            LIMIT 30
            """,
            (client_id, week_start_iso),
        ).fetchall()
    except sqlite3.Error:
        return []

    events: list[PulseEvent] = []
    seen_titles: set[str] = set()

    for row in rows:
        quote = (row["quote"] or "").strip()
        normalized = (row["normalized_claim"] or "").strip()
        if _is_test_quote(quote) and _is_test_quote(normalized):
            continue
        title = normalized or quote
        title = title.replace("\n", " ").strip()[:120]
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        events.append(
            PulseEvent(
                title=title,
                occurred_at=row["time_anchor"] or row["updated_at"] or "",
                impact=_infer_impact(row["polarity"], quote, normalized),
                source_type=row["source_type"] or "evidence",
                source_id=row["id"],
                source_label="",
            )
        )
        if len(events) >= 5:
            break

    return events


def _infer_impact(
    polarity: str | None,
    quote: str,
    claim: str,
) -> str:
    """polarity 字段当前一律 'neutral'; 用关键词补足三档判断."""
    if polarity == "advance":
        return "advance"
    if polarity == "block":
        return "block"
    text = f"{quote} {claim}"
    block_kws = (
        "卡住", "阻塞", "无法", "失败", "停滞", "离职",
        "辞职", "辞退", "逾期", "中断", "终止", "停摆",
    )
    advance_kws = (
        "完成", "通过", "确认", "已交付", "签约", "上线",
        "达成", "同意", "敲定", "落地",
    )
    for kw in block_kws:
        if kw in text:
            return "block"
    for kw in advance_kws:
        if kw in text:
            return "advance"
    return "neutral"


# --- 数据源 2: 你接下来要做 ---


def _fetch_upcoming_todos(
    db: sqlite3.Connection,
    client_id: str,
    today: date,
) -> list[PulseTodo]:
    """从 tasks 拉未完成任务, 按到期紧迫度排."""
    try:
        rows = db.execute(
            """
            SELECT t.id, t.title, t.due_date, t.deadline_at,
                   t.event_line_id, t.status,
                   el.name AS event_line_name
            FROM tasks t
            LEFT JOIN event_lines el ON t.event_line_id = el.id
            WHERE t.client_id = ?
              AND t.status NOT IN ('done', 'completed', 'cancelled', 'archived')
              AND COALESCE(t.kind, 'task') IN ('task', 'todo', '')
            ORDER BY COALESCE(t.deadline_at, t.due_date) ASC NULLS LAST
            LIMIT 30
            """,
            (client_id,),
        ).fetchall()
    except sqlite3.Error:
        rows = []

    todos: list[PulseTodo] = []
    for row in rows:
        due_raw = row["deadline_at"] or row["due_date"] or ""
        due_date_iso, days, urgency = _compute_urgency(due_raw, today)
        title = (row["title"] or "(无标题)").strip()
        todos.append(
            PulseTodo(
                title=title[:120],
                due_date=due_date_iso,
                days_until_due=days,
                urgency=urgency,
                source_task_id=row["id"],
                event_line_id=row["event_line_id"],
                event_line_name=(row["event_line_name"] or "").strip(),
            )
        )

    # M4: 补 tasks 之外的源 (原 pulse 只读 tasks, 漏 commitments / 会议待办 / 主线衍生待办)
    try:
        for row in db.execute(
            """SELECT id, committer, recipient, content, deadline FROM commitments
               WHERE client_id=? AND COALESCE(status,'pending') NOT IN ('fulfilled','cancelled','done')""",
            (client_id,),
        ).fetchall():
            due_iso, days, urgency = _compute_urgency(row["deadline"] or "", today)
            todos.append(PulseTodo(
                title=f"承诺: {row['committer']}→{row['recipient']}: {str(row['content'] or '')[:80]}"[:120],
                due_date=due_iso, days_until_due=days, urgency=urgency,
                source_task_id=f"commit:{row['id']}", event_line_id=None, event_line_name="",
            ))
    except sqlite3.Error:
        pass
    try:
        for row in db.execute(
            """SELECT ai.id, ai.title, ai.due_date, m.title AS meeting_title
               FROM action_items ai JOIN meetings m ON m.id=ai.meeting_id
               WHERE m.client_id=?
                 AND (ai.publish_status IS NULL OR ai.publish_status NOT IN ('completed','dismissed'))
                 AND ai.title NOT LIKE '%补齐%' AND ai.title NOT LIKE '%占位%'""",
            (client_id,),
        ).fetchall():
            due_iso, days, urgency = _compute_urgency(row["due_date"] or "", today)
            todos.append(PulseTodo(
                title=f"会议待办: {str(row['title'] or '')[:90]}"[:120],
                due_date=due_iso, days_until_due=days, urgency=urgency,
                source_task_id=f"action:{row['id']}", event_line_id=None,
                event_line_name=str(row["meeting_title"] or ""),
            ))
    except sqlite3.Error:
        pass
    try:
        for row in db.execute(
            """SELECT id, name, next_step FROM event_lines
               WHERE primary_client_id=? AND next_step IS NOT NULL AND TRIM(next_step)!=''
                 AND COALESCE(status,'')!='closed' AND closed_at IS NULL""",
            (client_id,),
        ).fetchall():
            due_iso, days, urgency = _compute_urgency("", today)
            todos.append(PulseTodo(
                title=f"[主线:{row['name']}] {str(row['next_step'] or '').strip()[:90]}"[:120],
                due_date=due_iso, days_until_due=days, urgency=urgency,
                source_task_id=f"eventline:{row['id']}", event_line_id=str(row["id"]),
                event_line_name=str(row["name"] or ""),
            ))
    except sqlite3.Error:
        pass

    # 按紧迫度排序; 同档内按 days_until_due 升序
    rank = {"overdue": 0, "today": 1, "this_week": 2, "later": 3}
    todos.sort(
        key=lambda t: (
            rank.get(t.urgency, 99),
            t.days_until_due if t.days_until_due is not None else 9999,
        )
    )
    return todos[:12]  # M4: 6→12, 容纳新增的 commitments/会议待办/主线衍生


def _compute_urgency(
    due_raw: str,
    today: date,
) -> tuple[str | None, int | None, str]:
    """解析 due date, 计算紧迫度档位.

    Returns:
        (due_date_iso, days_until_due, urgency).
        due_raw 为空或解析失败 → (None, None, "later").
    """
    if not due_raw:
        return None, None, "later"
    date_part = due_raw.split("T")[0].strip()
    if not date_part:
        return None, None, "later"
    try:
        due = datetime.strptime(date_part, "%Y-%m-%d").date()
    except ValueError:
        return None, None, "later"
    delta = (due - today).days
    if delta < 0:
        return date_part, delta, "overdue"
    if delta == 0:
        return date_part, 0, "today"
    if delta <= 7:
        return date_part, delta, "this_week"
    return date_part, delta, "later"


# --- 数据源 3: 当前卡点 ---


def _fetch_current_blockers(
    db: sqlite3.Connection,
    client_id: str,
    now: datetime,
) -> list[PulseBlocker]:
    """主线层面的阻塞: status='active' 且 30 天以上无活动, 或 current_blocker 有真内容."""
    try:
        rows = db.execute(
            """
            SELECT el.id, el.name, el.current_blocker, el.next_step,
                   el.status, el.updated_at,
                   (SELECT MAX(happened_at)
                    FROM event_line_activities
                    WHERE event_line_id = el.id) AS last_activity_at
            FROM event_lines el
            WHERE el.primary_client_id = ?
              AND el.status = 'active'
              AND (el.closed_at IS NULL OR el.closed_at = '')
            ORDER BY el.updated_at DESC
            """,
            (client_id,),
        ).fetchall()
    except sqlite3.Error:
        return []

    blockers: list[PulseBlocker] = []
    for row in rows:
        last_iso = row["last_activity_at"] or row["updated_at"] or ""
        if not last_iso:
            continue
        last_dt = _parse_iso_datetime(last_iso)
        if last_dt is None:
            continue
        delta_days = max(0, (now - last_dt).days)
        raw_blocker = (row["current_blocker"] or "").strip()
        has_real_blocker = bool(raw_blocker) and not any(
            phrase in raw_blocker for phrase in _TEMPLATE_BLOCKER_PHRASES
        )
        is_stuck = delta_days >= 30

        if not (has_real_blocker or is_stuck):
            continue

        if has_real_blocker:
            reason = raw_blocker[:200]
        else:
            reason = f"主线 {delta_days} 天无活动"

        title = (row["name"] or "").strip()
        if not title or title.startswith("eline_"):
            # 数据脏 (name 是 id) 跳过
            continue

        blockers.append(
            PulseBlocker(
                title=title[:120],
                reason=reason,
                stuck_days=delta_days,
                event_line_id=row["id"],
                suggested_action="",
            )
        )
        if len(blockers) >= 5:
            break

    return blockers


def _parse_iso_datetime(value: str) -> datetime | None:
    """容错解析 ISO 时间; 失败返回 None."""
    value = (value or "").strip()
    if not value:
        return None
    # 兼容 "Z" 结尾
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --- 批量摘要 (本周概览客户脉搏区块用) ---


def compute_pulse_summary_for_clients(
    db: sqlite3.Connection,
    *,
    now: datetime | None = None,
    exclude_smoke: bool = True,
) -> list[dict[str, Any]]:
    """计算所有客户的本周脉搏摘要 - 用于本周概览顶部.

    返回每个客户的简化数据 (不深入到具体事件), 让本周概览能一眼看出
    哪些客户本周有动态, 哪些静默. 详细内容点开后由 compute_strategic_pulse 提供.

    返回字段:
        - clientId / clientName / clientStage
        - weeklyNewDocumentCount: 本周新增文档数
        - weeklyNewTaskCount: 本周新建任务数
        - weeklyNewEvidenceCount: 本周新 evidence (过滤垃圾后)
        - currentBlockerCount: 当前卡点数
        - overdueTodoCount: 已逾期待办数
        - hasActivity: 是否有任一动态 (用于排序/突出)
        - topSignal: 一句话最显著信号 (业务语言)
    """
    now = now or datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    today = now.date()

    try:
        # 冷冻项目不参与战略脉冲计算 — 它们退出所有自动周聚合
        client_rows = db.execute(
            """
            SELECT id, name, stage, alias
            FROM clients
            WHERE frozen_at IS NULL
            ORDER BY updated_at DESC
            """
        ).fetchall()
    except sqlite3.Error:
        return []

    summaries: list[dict[str, Any]] = []
    for client_row in client_rows:
        client_id = client_row["id"]
        client_name = client_row["name"] or ""
        client_alias = client_row["alias"] or ""

        if exclude_smoke and (
            client_alias == "workspace-smoke"
            or client_name == "安装态冒烟客户"
            or client_name.endswith("冒烟客户")
        ):
            continue

        summary = _build_single_client_summary(
            db,
            client_id=client_id,
            client_name=client_name,
            client_stage=client_row["stage"] or "",
            week_start=week_start,
            now=now,
            today=today,
        )
        summaries.append(summary)

    # 排序: 有动态的在前 (按本周新增量降序), 静默的在后 (按 clientName)
    summaries.sort(
        key=lambda s: (
            0 if s["hasActivity"] else 1,
            -(s["weeklyNewDocumentCount"] + s["weeklyNewTaskCount"] + s["weeklyNewEvidenceCount"]),
            -s["currentBlockerCount"],
            s["clientName"],
        )
    )
    return summaries


def _build_single_client_summary(
    db: sqlite3.Connection,
    *,
    client_id: str,
    client_name: str,
    client_stage: str,
    week_start: datetime,
    now: datetime,
    today: date,
) -> dict[str, Any]:
    week_start_iso = week_start.isoformat()

    # 本周新文档
    try:
        new_docs = db.execute(
            """
            SELECT COUNT(*) AS c FROM documents
            WHERE client_id = ?
              AND created_at >= ?
              AND id NOT LIKE 'sysdoc_%'
            """,
            (client_id, week_start_iso),
        ).fetchone()
        new_doc_count = int(new_docs["c"]) if new_docs else 0
    except sqlite3.Error:
        new_doc_count = 0

    # 本周新建任务 (created_at 在本周内)
    try:
        new_tasks = db.execute(
            """
            SELECT COUNT(*) AS c FROM tasks
            WHERE client_id = ?
              AND created_at >= ?
            """,
            (client_id, week_start_iso),
        ).fetchone()
        new_task_count = int(new_tasks["c"]) if new_tasks else 0
    except sqlite3.Error:
        new_task_count = 0

    # 本周新 evidence (调用现有过滤函数)
    new_evidence = _fetch_weekly_events(db, client_id, week_start)
    new_evidence_count = len(new_evidence)

    # 当前卡点 (调用现有函数)
    blockers = _fetch_current_blockers(db, client_id, now)
    blocker_count = len(blockers)

    # 已逾期待办
    todos = _fetch_upcoming_todos(db, client_id, today)
    overdue_count = sum(1 for t in todos if t.urgency == "overdue")

    has_activity = (
        new_doc_count > 0
        or new_task_count > 0
        or new_evidence_count > 0
        or blocker_count > 0
        or overdue_count > 0
    )

    top_signal = _compose_top_signal(
        new_doc_count=new_doc_count,
        new_task_count=new_task_count,
        new_evidence_count=new_evidence_count,
        blocker_count=blocker_count,
        overdue_count=overdue_count,
    )

    return {
        "clientId": client_id,
        "clientName": client_name,
        "clientStage": client_stage,
        "weeklyNewDocumentCount": new_doc_count,
        "weeklyNewTaskCount": new_task_count,
        "weeklyNewEvidenceCount": new_evidence_count,
        "currentBlockerCount": blocker_count,
        "overdueTodoCount": overdue_count,
        "hasActivity": has_activity,
        "topSignal": top_signal,
    }


def _compose_top_signal(
    *,
    new_doc_count: int,
    new_task_count: int,
    new_evidence_count: int,
    blocker_count: int,
    overdue_count: int,
) -> str:
    """组合"最显著一句话" - 优先选用户最该关心的事."""
    if overdue_count > 0:
        return f"{overdue_count} 项任务已逾期"
    if blocker_count >= 3:
        return f"{blocker_count} 处主线长期停滞"
    if new_doc_count >= 3:
        return f"本周新增 {new_doc_count} 份资料待消化"
    if new_task_count > 0 and new_doc_count > 0:
        return f"本周 +{new_task_count} 任务 / +{new_doc_count} 资料"
    if blocker_count > 0:
        return f"{blocker_count} 处卡点待处理"
    if new_task_count > 0:
        return f"本周新增 {new_task_count} 项任务"
    if new_doc_count > 0:
        return f"本周新增 {new_doc_count} 份资料"
    if new_evidence_count > 0:
        return f"本周新增 {new_evidence_count} 条事实"
    return "本周无动态"


# --- DTO → dict (camelCase 给前端) ---


def _event_to_dict(e: PulseEvent) -> dict[str, Any]:
    return {
        "title": e.title,
        "occurredAt": e.occurred_at,
        "impact": e.impact,
        "sourceType": e.source_type,
        "sourceId": e.source_id,
        "sourceLabel": e.source_label,
    }


def _todo_to_dict(t: PulseTodo) -> dict[str, Any]:
    return {
        "title": t.title,
        "dueDate": t.due_date,
        "daysUntilDue": t.days_until_due,
        "urgency": t.urgency,
        "sourceTaskId": t.source_task_id,
        "eventLineId": t.event_line_id,
        "eventLineName": t.event_line_name,
    }


def _blocker_to_dict(b: PulseBlocker) -> dict[str, Any]:
    return {
        "title": b.title,
        "reason": b.reason,
        "stuckDays": b.stuck_days,
        "eventLineId": b.event_line_id,
        "suggestedAction": b.suggested_action,
    }
