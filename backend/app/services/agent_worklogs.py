from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from app.db import Database
from app.services.knowledge_base import tokenize
from app.models import (
    TaskTagRecord,
    TaskRecord,
    TaskCollaboratorRecord,
    TaskActivityRecord,
    AgentWeeklyPlanItemPayload,
    AgentWeeklyPlanItemRecord,
    AgentWeeklyPlanPayload,
    AgentWeeklyPlanRecord,
    AgentWorklogRecord,
    AgentWorklogResponse,
    AgentWeeklyDigestRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)


AGENT_DEPARTMENTS = {
    "strategy_design": {
        "agentName": "庆华",
        "departmentName": "咨询策略部",
        "color": "#5B7BFE",
        "sourceType": "activity_log",
    },
    "tech_development": {
        "agentName": "佳乐",
        "departmentName": "科技发展部",
        "color": "#F59E0B",
        "sourceType": "workspace_sync",
    },
    "info_data": {
        "agentName": "大周",
        "departmentName": "信息数据部",
        "color": "#10B981",
        "sourceType": "topic_capture",
    },
}

DONE_KEYWORDS = ("已完成", "完成", "收束", "发布", "提交", "验收通过", "关闭", "解决")
BLOCKER_KEYWORDS = ("风险", "阻塞", "卡住", "未完成", "待确认", "仍需", "问题", "阻力", "失败", "回退")

AGENT_TASK_TAGS = {
    "strategy_design": ("战略设计", "#5B7BFE"),
    "tech_development": ("软件系统", "#F59E0B"),
    "info_data": ("信息情报", "#10B981"),
}

AGENT_AUTO_SOURCE_TYPE = "agent_auto"


def _month_bounds(month_label: str) -> tuple[date, date]:
    try:
        year, month = month_label.split("-", 1)
        month_start = date(int(year), int(month), 1)
    except Exception as exc:
        raise ValueError(f"Invalid month label: {month_label}") from exc
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month - timedelta(days=1)


def _week_bounds(week_label: str) -> tuple[date, date]:
    match = re.match(r"^(\d{4})-W(\d{2})$", week_label.strip())
    if not match:
        raise ValueError(f"Invalid week label: {week_label}")
    year = int(match.group(1))
    week = int(match.group(2))
    week_start = date.fromisocalendar(year, week, 1)
    return week_start, week_start + timedelta(days=6)


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _week_label(value: date) -> str:
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _humanize_action(action: str) -> str:
    mapping = {
        "task.create": "新建任务",
        "task.update": "更新任务",
        "task.confirm": "确认任务",
        "task.note.update": "补充任务说明",
        "review.create": "提交周复盘",
        "meeting.publish": "发布会议任务",
        "meeting.resolve": "整理会议结论",
        "settings.review_governance.update": "调整复盘治理",
        "settings.tasks.update": "调整任务设置",
    }
    return mapping.get(action, action.replace(".", " / "))


def _parse_json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _status_keyword_match(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _clean_text(text)
    return any(keyword in normalized for keyword in keywords)


def _entry_match_score(item_tokens: set[str], entry: AgentWorklogRecord) -> int:
    if not item_tokens:
        return 0
    entry_tokens = set(tokenize(" ".join([entry.title, entry.summary, *entry.detailLines])))
    overlap = item_tokens & entry_tokens
    if overlap:
        return len(overlap)
    normalized_item = re.sub(r"\s+", "", " ".join(item_tokens))
    normalized_entry = re.sub(r"\s+", "", " ".join([entry.title, entry.summary, *entry.detailLines]))
    if normalized_item and normalized_item in normalized_entry:
        return 1
    return 0


def _infer_plan_item_status(item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord]) -> str:
    item_tokens = set(tokenize(" ".join([item.title, item.rationale, item.scheduleHint])))
    matched_entries = [
        entry for entry in entries
        if _entry_match_score(item_tokens, entry) > 0
    ]
    if not matched_entries:
        return item.status
    joined_text = " ".join(
        " ".join([entry.title, entry.summary, *entry.detailLines])
        for entry in matched_entries
    )
    if _status_keyword_match(joined_text, BLOCKER_KEYWORDS):
        return "blocked"
    if _status_keyword_match(joined_text, DONE_KEYWORDS):
        return "done"
    return "doing"


def _agent_task_tag(agent_key: str) -> TaskTagRecord:
    label, color = AGENT_TASK_TAGS.get(agent_key, ("机器人工作", "#64748B"))
    return TaskTagRecord(
        id=f"agent_tag_{agent_key}",
        name=label,
        color=color,
        scope="org",
        updatedAt=datetime.now().replace(microsecond=0).isoformat(),
    )


def _plan_status_to_task_status(status: str) -> str:
    if status == "done":
        return "done"
    if status in {"doing", "blocked"}:
        return "doing"
    return "todo"


def _plan_status_to_completion_status(status: str) -> str:
    if status == "done":
        return "done_on_time"
    if status == "blocked":
        return "not_done"
    if status == "doing":
        return "in_progress"
    return "in_progress"


def _compose_agent_progress(plan_item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord], digest: AgentWeeklyDigestRecord) -> str:
    if entries:
        evidence_titles = "、".join(entry.title for entry in entries[:2])
        return f"本周围绕「{plan_item.title}」已有自动工作痕迹：{evidence_titles}。"
    return digest.summary


def _compose_agent_success_experience(entries: list[AgentWorklogRecord]) -> str:
    if not entries:
        return ""
    for entry in entries:
        joined = " ".join([entry.title, entry.summary, *entry.detailLines])
        if _status_keyword_match(joined, DONE_KEYWORDS):
            return _clean_text(entry.summary or entry.title)
    return _clean_text(entries[0].summary)


def _compose_agent_failure_insight(entries: list[AgentWorklogRecord]) -> str:
    if not entries:
        return ""
    for entry in entries:
        joined = " ".join([entry.title, entry.summary, *entry.detailLines])
        if _status_keyword_match(joined, BLOCKER_KEYWORDS):
            return _clean_text(entry.summary or entry.title)
    return _clean_text(entries[0].summary)


def _agent_due_label(week_end: date, schedule_hint: str) -> str:
    hint = _clean_text(schedule_hint)
    return hint or week_end.isoformat()


def _default_task_list_id(db: Database) -> str:
    row = db.fetchone(
        "SELECT id FROM task_lists WHERE is_default = 1 ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1"
    )
    if row:
        return str(row["id"])
    fallback = db.fetchone("SELECT id FROM task_lists ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1")
    if fallback:
        return str(fallback["id"])
    raise ValueError("No task list configured for agent tasks")


def _parse_agent_task_identity(task_id: str) -> tuple[str, str, int] | None:
    match = re.match(r"^agent_task_([a-z_]+)_(\d{4}-W\d{2})_(\d+)$", task_id)
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _agent_auto_source_id(week_label: str, agent_key: str, item_index: int) -> str:
    return f"{week_label}::{agent_key}::{item_index}"


def _matched_entries_for_plan_item(plan_item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord]) -> list[AgentWorklogRecord]:
    item_tokens = set(tokenize(" ".join([plan_item.title, plan_item.rationale, plan_item.scheduleHint])))
    return [
        entry for entry in entries
        if _entry_match_score(item_tokens, entry) > 0
    ]


def _build_qinghua_logs(db: Database, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    rows = db.fetchall(
        """
        SELECT created_at, action, entity_type, detail_json
        FROM activity_logs
        WHERE actor_name = ?
        ORDER BY created_at DESC
        """,
        ("庆华",),
    )
    grouped: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        created_on = _to_date(str(row["created_at"]))
        if not created_on or created_on < month_start or created_on > month_end:
            continue
        grouped[created_on.isoformat()].append(row)

    config = AGENT_DEPARTMENTS["strategy_design"]
    entries: list[AgentWorklogRecord] = []
    for day in sorted(grouped.keys(), reverse=True):
        day_rows = grouped[day]
        action_labels = []
        for row in day_rows[:4]:
            detail = _parse_json_object(row["detail_json"])
            detail_title = _clean_text(str(detail.get("title") or detail.get("taskTitle") or ""))
            label = _humanize_action(str(row["action"]))
            action_labels.append(f"{label}：{detail_title}" if detail_title else label)
        summary = f"庆华这一天处理了 {len(day_rows)} 条战略侧内部动作，重点包括：{'、'.join(action_labels)}。"
        entries.append(
            AgentWorklogRecord(
                id=f"agent_qinghua_{day}",
                agentKey="strategy_design",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=day,
                weekLabel=_week_label(date.fromisoformat(day)),
                title=f"庆华当日处理了 {len(day_rows)} 条战略动作",
                summary=summary,
                detailLines=action_labels,
                sourceType="activity_log",
                createdAt=str(day_rows[0]["created_at"]),
            )
        )
    return entries


def _build_dazhou_logs(db: Database, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    rows = db.fetchall(
        """
        SELECT c.id, c.title, c.source, c.created_at, r.title AS radar_title
        FROM topic_candidates c
        LEFT JOIN topic_radars r ON r.id = c.radar_id
        WHERE c.captured_by = ?
        ORDER BY c.created_at DESC
        """,
        ("大周",),
    )
    grouped: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        created_on = _to_date(str(row["created_at"]))
        if not created_on or created_on < month_start or created_on > month_end:
            continue
        grouped[created_on.isoformat()].append(row)

    config = AGENT_DEPARTMENTS["info_data"]
    entries: list[AgentWorklogRecord] = []
    for day in sorted(grouped.keys(), reverse=True):
        day_rows = grouped[day]
        radar_titles = sorted({str(row["radar_title"] or "") for row in day_rows if str(row["radar_title"] or "").strip()})
        source_titles = [str(row["title"]) for row in day_rows[:3]]
        summary = (
            f"大周这一天新增 {len(day_rows)} 条情报线索。"
            + (f" 主要覆盖：{'、'.join(radar_titles[:3])}。" if radar_titles else "")
        )
        entries.append(
            AgentWorklogRecord(
                id=f"agent_dazhou_{day}",
                agentKey="info_data",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=day,
                weekLabel=_week_label(date.fromisoformat(day)),
                title=f"大周当日新增 {len(day_rows)} 条情报线索",
                summary=summary,
                detailLines=source_titles,
                sourceType="topic_capture",
                createdAt=str(day_rows[0]["created_at"]),
            )
        )
    return entries


def _extract_thread_sync_sections(path: Path) -> list[tuple[date, str, list[str]]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    sections: list[tuple[date, str, list[str]]] = []
    current_date: date | None = None
    current_title = ""
    current_lines: list[str] = []
    heading_pattern = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(.*)$")

    def flush() -> None:
        nonlocal current_date, current_title, current_lines
        if current_date is not None and current_lines:
            sections.append((current_date, current_title, current_lines[:]))
        current_date = None
        current_title = ""
        current_lines = []

    for line in content:
        heading_match = heading_pattern.match(line.strip())
        if heading_match:
            flush()
            current_date = date.fromisoformat(heading_match.group(1))
            current_title = heading_match.group(2).strip() or "系统同步"
            continue
        if current_date is not None:
            current_lines.append(line.rstrip())
    flush()
    return sections


def _section_summary_lines(lines: list[str]) -> tuple[str, list[str]]:
    cleaned = [
        _clean_text(re.sub(r"^-\s*", "", line.strip()))
        for line in lines
        if line.strip().startswith("- ")
    ]
    preferred = [
        item for item in cleaned
        if ("当前状态" in item or "已完成" in item or "开始" in item or "风险点" in item)
        and "验证结果" not in item
    ]
    detail_lines = preferred[:4] or cleaned[:4]
    summary = " ".join(detail_lines[:2]) if detail_lines else "今天有系统开发同步，但还没有整理成结构化说明。"
    return summary, detail_lines


def _build_jiale_logs(thread_sync_path: Path, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    sections = _extract_thread_sync_sections(thread_sync_path)
    config = AGENT_DEPARTMENTS["tech_development"]
    entries: list[AgentWorklogRecord] = []
    for section_date, title, lines in sections:
        if section_date < month_start or section_date > month_end:
            continue
        summary, detail_lines = _section_summary_lines(lines)
        entries.append(
            AgentWorklogRecord(
                id=f"agent_jiale_{section_date.isoformat()}_{abs(hash(title)) % 10000}",
                agentKey="tech_development",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=section_date.isoformat(),
                weekLabel=_week_label(section_date),
                title=title,
                summary=summary,
                detailLines=detail_lines,
                sourceType="workspace_sync",
                createdAt=section_date.isoformat(),
            )
        )
    return entries


def _build_focus_items(
    *,
    db: Database,
    agent_key: str,
    week_label: str,
    week_entries: list[AgentWorklogRecord],
) -> list[str]:
    if agent_key == "strategy_design":
        rows = db.fetchall(
            """
            SELECT title
            FROM tasks
            WHERE owner_name = ? AND status != 'done'
            ORDER BY updated_at DESC
            LIMIT 3
            """,
            ("庆华",),
        )
        items = [f"继续推进「{str(row['title'])}」" for row in rows]
        return items or ["继续处理战略问答与关键判断类任务。"]
    if agent_key == "info_data":
        rows = db.fetchall(
            """
            SELECT title
            FROM topic_radars
            ORDER BY created_at ASC
            LIMIT 3
            """
        )
        items = [f"继续跟进「{str(row['title'])}」雷达" for row in rows]
        return items or ["继续补抓高相关情报，并把可执行线索转成任务。"]
    section_titles = [entry.title for entry in week_entries[:3] if entry.title.strip()]
    return [f"继续推进「{title}」" for title in section_titles] or ["继续推进软件系统主线改动，并同步风险和验收结果。"]


def _build_weekly_digests(db: Database, worklogs: list[AgentWorklogRecord]) -> list[AgentWeeklyDigestRecord]:
    grouped: dict[tuple[str, str], list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        grouped[(entry.agentKey, entry.weekLabel)].append(entry)

    digests: list[AgentWeeklyDigestRecord] = []
    for (agent_key, week_label), entries in grouped.items():
        config = AGENT_DEPARTMENTS[agent_key]
        entries.sort(key=lambda item: (item.date, item.createdAt), reverse=True)
        summary = f"{config['agentName']} 本周累计记录 {len(entries)} 条工作日志，主要围绕：{'、'.join(entry.title for entry in entries[:2])}。"
        digests.append(
            AgentWeeklyDigestRecord(
                agentKey=agent_key,  # type: ignore[arg-type]
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                weekLabel=week_label,
                summary=summary,
                focusItems=_build_focus_items(db=db, agent_key=agent_key, week_label=week_label, week_entries=entries),
                evidenceCount=len(entries),
                sourcePolicy={
                    "sourceType": config["sourceType"],
                    "realLogMode": True,
                    "evidenceCount": len(entries),
                },
            )
        )
    digests.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return digests


def _plan_schedule_hint(agent_key: str, index: int) -> str:
    if agent_key == "strategy_design":
        hints = ["周一先校准重点判断", "周中持续验证问答与策略输出", "周末前完成重点结论收束"]
    elif agent_key == "info_data":
        hints = ["每天巡检新增信号", "周中补抓高相关线索", "周末前整理可转任务的情报"]
    else:
        hints = ["周初推进主线改动接线", "周中同步风险与验证结果", "周末前收束系统验收与文档同步"]
    return hints[min(index, len(hints) - 1)]


def _plan_status(value: object) -> str:
    text = str(value or "planned").strip().lower()
    return text if text in {"planned", "doing", "done", "blocked"} else "planned"


def _normalize_plan_items(
    *,
    week_label: str,
    agent_key: str,
    raw_items: list[object],
) -> list[AgentWeeklyPlanItemRecord]:
    items: list[AgentWeeklyPlanItemRecord] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            continue
        title = _clean_text(str(raw_item.get("title") or ""))
        if not title:
            continue
        items.append(
            AgentWeeklyPlanItemRecord(
                id=f"{agent_key}_{week_label}_{index}",
                title=title,
                rationale=_clean_text(str(raw_item.get("rationale") or "")),
                scheduleHint=_clean_text(str(raw_item.get("scheduleHint") or "")),
                status=_plan_status(raw_item.get("status")),
            )
        )
    return items


def _load_plan_override_rows(db: Database, week_label: str) -> dict[str, object]:
    rows = db.fetchall(
        """
        SELECT *
        FROM agent_weekly_plan_overrides
        WHERE week_label = ?
        ORDER BY updated_at DESC
        """,
        (week_label,),
    )
    return {str(row["agent_key"]): row for row in rows}


def _apply_plan_overrides(
    *,
    db: Database,
    week_label: str,
    derived_plans: list[AgentWeeklyPlanRecord],
) -> list[AgentWeeklyPlanRecord]:
    override_rows = _load_plan_override_rows(db, week_label)
    derived_by_agent = {plan.agentKey: plan for plan in derived_plans}
    merged: list[AgentWeeklyPlanRecord] = []

    for agent_key, config in AGENT_DEPARTMENTS.items():
        derived_plan = derived_by_agent.get(agent_key)
        override_row = override_rows.get(agent_key)
        if override_row is None and derived_plan is None:
            continue
        if override_row is None and derived_plan is not None:
            merged.append(derived_plan)
            continue

        raw_items = []
        try:
            raw_items = json.loads(str(override_row["plan_items_json"] or "[]"))
        except Exception:
            raw_items = []
        override_items = _normalize_plan_items(
            week_label=week_label,
            agent_key=agent_key,
            raw_items=raw_items if isinstance(raw_items, list) else [],
        )
        summary = _clean_text(str(override_row["summary"] or ""))
        base_summary = derived_plan.summary if derived_plan else f"{config['agentName']} 本周正式计划。"
        merged.append(
            AgentWeeklyPlanRecord(
                agentKey=agent_key,  # type: ignore[arg-type]
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                weekLabel=week_label,
                summary=summary or base_summary,
                planItems=override_items or (derived_plan.planItems if derived_plan else []),
                sourcePolicy={
                    **(derived_plan.sourcePolicy if derived_plan else {"planMode": "manual_override"}),
                    "manualOverride": True,
                    "updatedBy": str(override_row["updated_by"] or ""),
                    "updatedAt": str(override_row["updated_at"] or ""),
                    "sourceType": config["sourceType"],
                },
            )
        )

    merged.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return merged


def _build_weekly_plans(
    db: Database,
    worklogs: list[AgentWorklogRecord],
    weekly_digests: list[AgentWeeklyDigestRecord] | None = None,
) -> list[AgentWeeklyPlanRecord]:
    grouped: dict[tuple[str, str], list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        grouped[(entry.agentKey, entry.weekLabel)].append(entry)

    digests = weekly_digests if weekly_digests is not None else _build_weekly_digests(db, worklogs)
    plans: list[AgentWeeklyPlanRecord] = []
    for digest in digests:
        entries = grouped.get((digest.agentKey, digest.weekLabel), [])
        entries = sorted(entries, key=lambda item: (item.date, item.createdAt), reverse=True)
        plan_items: list[AgentWeeklyPlanItemRecord] = []
        focus_items = digest.focusItems[:3]
        for index, item in enumerate(focus_items):
            evidence_title = entries[index].title if index < len(entries) else digest.summary
            draft_item = AgentWeeklyPlanItemRecord(
                id=f"{digest.agentKey}_{digest.weekLabel}_{index}",
                title=item,
                rationale=f"基于最近的真实工作痕迹推演：{evidence_title}",
                scheduleHint=_plan_schedule_hint(digest.agentKey, index),
            )
            plan_items.append(
                draft_item.model_copy(update={"status": _infer_plan_item_status(draft_item, entries)})
            )
        if not plan_items:
            draft_item = AgentWeeklyPlanItemRecord(
                id=f"{digest.agentKey}_{digest.weekLabel}_default",
                title=f"维持{digest.departmentName}当前主线推进",
                rationale=digest.summary,
                scheduleHint=_plan_schedule_hint(digest.agentKey, 0),
            )
            plan_items.append(
                draft_item.model_copy(update={"status": _infer_plan_item_status(draft_item, entries)})
            )
        plans.append(
            AgentWeeklyPlanRecord(
                agentKey=digest.agentKey,
                agentName=digest.agentName,
                departmentName=digest.departmentName,
                color=digest.color,
                weekLabel=digest.weekLabel,
                summary=f"{digest.agentName} 本周计划由 {digest.evidenceCount} 条真实日志推演而来，优先围绕：{'、'.join(item.title for item in plan_items[:2])}。",
                planItems=plan_items,
                sourcePolicy={
                    "planMode": "derived_from_real_logs",
                    "evidenceCount": digest.evidenceCount,
                    "sourceType": digest.sourcePolicy.get("sourceType"),
                    "autoStatus": True,
                },
            )
        )
    plans.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return plans


def _build_agent_worklogs_for_range(
    *,
    db: Database,
    range_start: date,
    range_end: date,
    thread_sync_path: Path,
) -> list[AgentWorklogRecord]:
    worklogs = [
        *_build_qinghua_logs(db, range_start, range_end),
        *_build_dazhou_logs(db, range_start, range_end),
        *_build_jiale_logs(thread_sync_path, range_start, range_end),
    ]
    worklogs.sort(key=lambda item: (item.date, item.createdAt, item.agentName), reverse=True)
    return worklogs


def build_agent_weekly_digests(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[AgentWeeklyDigestRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    return _build_weekly_digests(db, worklogs)


def build_agent_weekly_plans(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[AgentWeeklyPlanRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_digests = _build_weekly_digests(db, worklogs)
    derived_plans = _build_weekly_plans(db, worklogs, weekly_digests)
    return _apply_plan_overrides(db=db, week_label=week_label, derived_plans=derived_plans)


def build_agent_weekly_review_items(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[WeeklyReviewTaskEntryRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_digests = _build_weekly_digests(db, worklogs)
    weekly_plans = _apply_plan_overrides(
        db=db,
        week_label=week_label,
        derived_plans=_build_weekly_plans(db, worklogs, weekly_digests),
    )
    digest_by_agent = {item.agentKey: item for item in weekly_digests}
    worklogs_by_agent = defaultdict(list)
    for log in worklogs:
        worklogs_by_agent[log.agentKey].append(log)

    review_items: list[WeeklyReviewTaskEntryRecord] = []
    for plan in weekly_plans:
        digest = digest_by_agent.get(plan.agentKey)
        if digest is None:
            continue
        week_entries = sorted(
            worklogs_by_agent.get(plan.agentKey, []),
            key=lambda item: (item.date, item.createdAt),
            reverse=True,
        )
        tag = _agent_task_tag(plan.agentKey)
        for index, plan_item in enumerate(plan.planItems):
            matched_entries = _matched_entries_for_plan_item(plan_item, week_entries)
            status = _plan_status(plan_item.status)
            progress = _compose_agent_progress(plan_item, matched_entries or week_entries[:2], digest)
            success_experience = _compose_agent_success_experience(matched_entries) if status == "done" else ""
            failure_insight = _compose_agent_failure_insight(matched_entries) if status == "blocked" else ""
            blocker_reason = failure_insight if status == "blocked" else ""
            next_action = plan_item.scheduleHint or (digest.focusItems[index + 1] if index + 1 < len(digest.focusItems) else "")
            created_at = matched_entries[0].createdAt if matched_entries else (week_entries[0].createdAt if week_entries else week_start.isoformat())
            review_items.append(
                WeeklyReviewTaskEntryRecord(
                    id=f"agent_review_{plan.agentKey}_{plan.weekLabel}_{index}",
                    reviewId=f"agent_review_{plan.agentKey}_{plan.weekLabel}",
                    taskId=f"agent_task_{plan.agentKey}_{plan.weekLabel}_{index}",
                    weekLabel=plan.weekLabel,
                    contentDomain="work",
                    note="",
                    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
                        reflection=success_experience or failure_insight or blocker_reason or next_action,
                        lightweightTag="等待他人" if status == "blocked" else "",
                        planCommitment=plan_item.title,
                        progress=progress,
                        completionStatus=_plan_status_to_completion_status(status),  # type: ignore[arg-type]
                        departmentPlanId=plan_item.id,
                        departmentPlanAlignment="aligned",
                        organizationPlanId=None,
                        organizationPlanAlignment="unknown",
                        successReason=success_experience,
                        successExperience=success_experience,
                        blockerReason=blocker_reason,
                        failureInsight=failure_insight,
                        supportNeeded="需要 CEO 或跨部门支持" if status == "blocked" else "",
                        nextAction=next_action,
                    ),
                    reviewedAt=created_at,
                    taskSnapshot=WeeklyReviewTaskSnapshotRecord(
                        title=plan_item.title,
                        status=_plan_status_to_task_status(status),  # type: ignore[arg-type]
                        dueDate=week_end.isoformat(),
                        createdAt=created_at,
                        ownerId=f"agent:{plan.agentKey}",
                        ownerName=plan.agentName,
                        tags=[tag],
                        listName=plan.departmentName,
                        listColor=plan.color,
                    ),
                )
            )
    review_items.sort(key=lambda item: (item.taskSnapshot.ownerName or "", item.taskId))
    return review_items


def sync_agent_execution_tasks(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[str]:
    week_start, week_end = _week_bounds(week_label)
    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label=week_label,
        thread_sync_path=thread_sync_path,
    )
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    worklogs_by_agent: dict[str, list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        worklogs_by_agent[entry.agentKey].append(entry)

    task_list_id = _default_task_list_id(db)
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    expected_ids: list[str] = []

    for plan in weekly_plans:
        tag_names = [plan.departmentName, "机器人任务"]
        for index, plan_item in enumerate(plan.planItems):
            task_id = f"agent_task_{plan.agentKey}_{plan.weekLabel}_{index}"
            expected_ids.append(task_id)
            matched_entries = _matched_entries_for_plan_item(plan_item, worklogs_by_agent.get(plan.agentKey, []))
            status = _plan_status_to_task_status(_plan_status(plan_item.status))
            description = _compose_agent_progress(plan_item, matched_entries or worklogs_by_agent.get(plan.agentKey, [])[:2], next(
                (item for item in _build_weekly_digests(db, worklogs) if item.agentKey == plan.agentKey and item.weekLabel == plan.weekLabel),
                AgentWeeklyDigestRecord(
                    agentKey=plan.agentKey,
                    agentName=plan.agentName,
                    departmentName=plan.departmentName,
                    color=plan.color,
                    weekLabel=plan.weekLabel,
                    summary=plan.summary,
                    focusItems=[],
                    evidenceCount=0,
                    sourcePolicy={},
                ),
            ))
            created_at = matched_entries[0].createdAt if matched_entries else timestamp
            db.execute(
                """
                INSERT INTO tasks(
                    id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    priority = excluded.priority,
                    list_id = excluded.list_id,
                    owner_name = excluded.owner_name,
                    ddl = excluded.ddl,
                    source_type = excluded.source_type,
                    source_id = excluded.source_id,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    plan_item.title,
                    description,
                    status,
                    "normal",
                    task_list_id,
                    plan.agentName,
                    _agent_due_label(week_end, plan_item.scheduleHint),
                    AGENT_AUTO_SOURCE_TYPE,
                    _agent_auto_source_id(plan.weekLabel, plan.agentKey, index),
                    json.dumps(tag_names, ensure_ascii=False),
                    "[]",
                    created_at,
                    timestamp,
                ),
            )
            note_content = "\n".join(
                part for part in [
                    f"部门：{plan.departmentName}",
                    f"计划说明：{plan_item.rationale}",
                    f"调度提示：{plan_item.scheduleHint}",
                    f"本周自动进展：{description}",
                    f"状态：{_plan_status(plan_item.status)}",
                ] if _clean_text(part)
            )
            existing_note = db.fetchone("SELECT id FROM task_notes WHERE task_id = ?", (task_id,))
            if existing_note:
                db.execute(
                    "UPDATE task_notes SET note = ?, updated_at = ? WHERE task_id = ?",
                    (note_content, timestamp, task_id),
                )
            else:
                db.execute(
                    "INSERT INTO task_notes(id, task_id, note, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                    (f"agent_note_{task_id}", task_id, note_content, timestamp, timestamp),
                )

    if expected_ids:
        placeholders = ",".join("?" for _ in expected_ids)
        db.execute(
            f"DELETE FROM tasks WHERE source_type = ? AND source_id LIKE ? AND id NOT IN ({placeholders})",
            (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%", *expected_ids),
        )
    else:
        db.execute(
            "DELETE FROM tasks WHERE source_type = ? AND source_id LIKE ?",
            (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%"),
        )
    return expected_ids


def build_agent_execution_tasks(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[TaskRecord]:
    sync_agent_execution_tasks(db=db, week_label=week_label, thread_sync_path=thread_sync_path)
    rows = db.fetchall(
        """
        SELECT t.*, l.name AS list_name, l.color AS list_color
        FROM tasks t
        JOIN task_lists l ON l.id = t.list_id
        WHERE t.source_type = ? AND t.source_id LIKE ?
        ORDER BY t.owner_name COLLATE NOCASE ASC, t.updated_at DESC
        """,
        (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%"),
    )
    tasks: list[TaskRecord] = []
    for row in rows:
        note_row = db.fetchone("SELECT note FROM task_notes WHERE task_id = ?", (str(row["id"]),))
        identity = _parse_agent_task_identity(str(row["id"]))
        agent_key = identity[0] if identity else "strategy_design"
        tasks.append(
            TaskRecord(
                id=str(row["id"]),
                title=str(row["title"]),
                desc=str(row["description"]),
                status=str(row["status"]),  # type: ignore[arg-type]
                creatorId=f"agent:{agent_key}",
                creatorName=str(row["owner_name"]),
                priority=str(row["priority"]),  # type: ignore[arg-type]
                listId=str(row["list_id"]),
                listName=str(row["list_name"]),
                listColor=str(row["list_color"]),
                ddl=str(row["ddl"]),
                ownerId=f"agent:{agent_key}",
                ownerName=str(row["owner_name"]),
                sourceType=str(row["source_type"]),
                sourceId=str(row["source_id"]) if row["source_id"] else None,
                tags=[
                    _agent_task_tag(agent_key),
                    TaskTagRecord(
                        id=f"agent_dept_{agent_key}",
                        name=str(next((meta["departmentName"] for key, meta in AGENT_DEPARTMENTS.items() if key == agent_key), "机器人部门")),
                        color=str(next((meta["color"] for key, meta in AGENT_DEPARTMENTS.items() if key == agent_key), "#64748B")),
                        scope="org",
                        updatedAt=str(row["updated_at"]),
                    ),
                ],
                note=str(note_row["note"]) if note_row else None,
                collaborators=[],
                collaborationSummary={},
                viewerInboxStatus=None,
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
        )
    return tasks


def build_agent_execution_task_activity(
    *,
    db: Database,
    task_id: str,
    thread_sync_path: Path,
) -> list[TaskActivityRecord]:
    identity = _parse_agent_task_identity(task_id)
    if identity is None:
        return []
    agent_key, week_label, item_index = identity
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label=week_label,
        thread_sync_path=thread_sync_path,
    )
    plan = next((item for item in weekly_plans if item.agentKey == agent_key), None)
    if plan is None or item_index >= len(plan.planItems):
        return []
    plan_item = plan.planItems[item_index]
    matched_entries = _matched_entries_for_plan_item(
        plan_item,
        [entry for entry in worklogs if entry.agentKey == agent_key],
    )
    actor_id = f"agent:{agent_key}"
    actor_name = plan.agentName
    activities: list[TaskActivityRecord] = [
        TaskActivityRecord(
            id=f"agent_activity_created_{task_id}",
            taskId=task_id,
            actorId=actor_id,
            actorName=actor_name,
            eventType="agent.plan_synced",
            payload={
                "weekLabel": week_label,
                "planTitle": plan_item.title,
                "status": plan_item.status,
                "scheduleHint": plan_item.scheduleHint,
            },
            createdAt=week_start.isoformat(),
        )
    ]
    for index, entry in enumerate(matched_entries):
        activities.append(
            TaskActivityRecord(
                id=f"agent_activity_{task_id}_{index}",
                taskId=task_id,
                actorId=actor_id,
                actorName=actor_name,
                eventType="agent.worklog",
                payload={
                    "title": entry.title,
                    "summary": entry.summary,
                    "detailLines": entry.detailLines,
                    "sourceType": entry.sourceType,
                    "departmentName": entry.departmentName,
                },
                createdAt=entry.createdAt,
            )
        )
    activities.sort(key=lambda item: item.createdAt, reverse=True)
    return activities


def upsert_agent_weekly_plan_override(
    *,
    db: Database,
    payload: AgentWeeklyPlanPayload,
    updated_by: str,
) -> None:
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    plan_items = [
        AgentWeeklyPlanItemRecord(
            id=f"{payload.agentKey}_{payload.weekLabel}_{index}",
            title=_clean_text(item.title),
            rationale=_clean_text(item.rationale),
            scheduleHint=_clean_text(item.scheduleHint),
            status=_plan_status(item.status),
        )
        for index, item in enumerate(payload.planItems)
        if _clean_text(item.title)
    ]
    row = db.fetchone(
        """
        SELECT id, created_at
        FROM agent_weekly_plan_overrides
        WHERE week_label = ? AND agent_key = ?
        """,
        (payload.weekLabel, payload.agentKey),
    )
    serialized_items = json.dumps(
        [
            {
                "title": item.title,
                "rationale": item.rationale,
                "scheduleHint": item.scheduleHint,
                "status": item.status,
            }
            for item in plan_items
        ],
        ensure_ascii=False,
    )
    if row:
        db.execute(
            """
            UPDATE agent_weekly_plan_overrides
            SET summary = ?, plan_items_json = ?, updated_by = ?, updated_at = ?
            WHERE week_label = ? AND agent_key = ?
            """,
            (
                _clean_text(payload.summary),
                serialized_items,
                updated_by,
                timestamp,
                payload.weekLabel,
                payload.agentKey,
            ),
        )
        return
    db.execute(
        """
        INSERT INTO agent_weekly_plan_overrides(
            id, week_label, agent_key, summary, plan_items_json, updated_by, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"agent_plan_override_{payload.agentKey}_{payload.weekLabel}",
            payload.weekLabel,
            payload.agentKey,
            _clean_text(payload.summary),
            serialized_items,
            updated_by,
            timestamp,
            timestamp,
        ),
    )


def build_agent_worklog_response(
    *,
    db: Database,
    month_label: str,
    thread_sync_path: Path,
) -> AgentWorklogResponse:
    month_start, month_end = _month_bounds(month_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=month_start,
        range_end=month_end,
        thread_sync_path=thread_sync_path,
    )
    represented_weeks = sorted({item.weekLabel for item in worklogs}, reverse=True)
    weekly_digests: list[AgentWeeklyDigestRecord] = []
    weekly_plans: list[AgentWeeklyPlanRecord] = []
    for week_label in represented_weeks:
        week_digests = build_agent_weekly_digests(
            db=db,
            week_label=week_label,
            thread_sync_path=thread_sync_path,
        )
        weekly_digests.extend(week_digests)
        weekly_plans.extend(
            build_agent_weekly_plans(
                db=db,
                week_label=week_label,
                thread_sync_path=thread_sync_path,
            )
        )
    weekly_digests.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    weekly_plans.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return AgentWorklogResponse(
        month=month_label,
        worklogs=worklogs,
        weeklyDigests=weekly_digests,
        weeklyPlans=weekly_plans,
    )
