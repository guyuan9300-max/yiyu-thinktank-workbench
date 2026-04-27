from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from app.db import Database, from_json


UpsertCanonicalTextDocument = Callable[..., dict[str, Any] | None]


def _row_value(row: Any, key: str, default: str = "") -> Any:
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _json_list(value: Any) -> list[Any]:
    parsed = from_json(str(value or "[]"), [])
    return parsed if isinstance(parsed, list) else []


def _append_field(lines: list[str], label: str, value: Any) -> None:
    cleaned = _clean_text(value)
    if cleaned:
        lines.append(f"- {label}：{cleaned}")


def _common_client_terms(name: str, alias: str) -> list[str]:
    terms: list[str] = []
    for raw in (name, alias):
        cleaned = _clean_text(raw)
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
        for suffix in ("公益基金会", "基金会", "有限公司", "公司", "中心", "项目"):
            if cleaned.endswith(suffix):
                shortened = cleaned[: -len(suffix)].strip()
                if len(shortened) >= 2 and shortened not in terms:
                    terms.append(shortened)
    return terms


def _text_contains_any(text: str, terms: list[str]) -> list[str]:
    normalized = _clean_text(text)
    return [term for term in terms if term and term in normalized]


def _client_row(db: Database, client_id: str) -> Any | None:
    return db.fetchone("SELECT id, name, alias FROM clients WHERE id = ?", (client_id,))


def _table_columns(db: Database, table_name: str) -> set[str]:
    try:
        return {str(row["name"]) for row in db.fetchall(f"PRAGMA table_info({table_name})")}
    except Exception:
        return set()


def _task_rows_for_client(db: Database, client_id: str) -> list[Any]:
    return db.fetchall(
        """
        SELECT
            t.*,
            pm.name AS project_module_name,
            pf.name AS project_flow_name,
            el.name AS event_line_name
        FROM tasks t
        LEFT JOIN project_modules pm ON pm.id = t.project_module_id
        LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        WHERE t.client_id = ?
        ORDER BY COALESCE(NULLIF(t.updated_at, ''), t.created_at) DESC
        """,
        (client_id,),
    )


def _task_line(row: Any) -> str:
    parts = [
        _clean_text(_row_value(row, "title")) or str(_row_value(row, "id")),
        f"状态：{_clean_text(_row_value(row, 'status')) or '未标注'}",
        f"进度：{_clean_text(_row_value(row, 'progress_status')) or '未标注'}",
    ]
    deadline = _clean_text(_row_value(row, "due_date")) or _clean_text(_row_value(row, "ddl"))
    if deadline:
        parts.append(f"截止：{deadline}")
    module_name = _clean_text(_row_value(row, "project_module_name"))
    flow_name = _clean_text(_row_value(row, "project_flow_name"))
    event_line_name = _clean_text(_row_value(row, "event_line_name"))
    if module_name:
        parts.append(f"项目：{module_name}")
    if flow_name:
        parts.append(f"流程：{flow_name}")
    if event_line_name:
        parts.append(f"事件线：{event_line_name}")
    return "- " + "｜".join(parts)


def _render_relation_sources(sources: list[tuple[str, str]]) -> list[str]:
    if not sources:
        return ["- 关系置信度：weak", "- 关系来源：可能相关，仍需结合上下文判断。"]
    confidence_order = {"strong": 0, "medium": 1, "weak": 2}
    best = sorted(sources, key=lambda item: confidence_order.get(item[0], 9))[0][0]
    lines = [f"- 关系置信度：{best}"]
    for confidence, reason in sources:
        qualifier = "可能相关" if confidence == "weak" else "关联依据"
        lines.append(f"- {qualifier}：{reason}")
    return lines


def _render_event_line_doc(db: Database, *, client_id: str, client_name: str, row: Any, relation_sources: list[tuple[str, str]]) -> str:
    event_line_id = str(_row_value(row, "id"))
    title = _clean_text(_row_value(row, "name")) or event_line_id
    lines = [
        f"# 事件线：{title}",
        "",
        "## 基本信息",
        f"- 客户：{client_name or client_id}",
        *_render_relation_sources(relation_sources),
    ]
    for label, key in (
        ("类型", "kind"),
        ("状态", "status"),
        ("阶段", "stage"),
        ("业务分类", "business_category"),
        ("负责人", "owner_name"),
        ("当前阻塞", "current_blocker"),
        ("最近决策", "recent_decision"),
        ("下一步", "next_step"),
        ("摘要", "summary"),
    ):
        _append_field(lines, label, _row_value(row, key))

    task_rows = db.fetchall(
        """
        SELECT t.*, pm.name AS project_module_name, pf.name AS project_flow_name, el.name AS event_line_name
        FROM tasks t
        LEFT JOIN project_modules pm ON pm.id = t.project_module_id
        LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        WHERE t.client_id = ? AND t.event_line_id = ?
        ORDER BY COALESCE(NULLIF(t.updated_at, ''), t.created_at) DESC
        LIMIT 20
        """,
        (client_id, event_line_id),
    )
    if task_rows:
        lines.extend(["", "## 相关任务"])
        lines.extend(_task_line(task) for task in task_rows)

    activity_rows = db.fetchall(
        "SELECT title, summary, happened_at, actor_name, is_key FROM event_line_activities WHERE event_line_id = ? ORDER BY happened_at DESC, created_at DESC LIMIT 20",
        (event_line_id,),
    )
    if activity_rows:
        lines.extend(["", "## 关键活动"])
        for activity in activity_rows:
            marker = "关键" if int(_row_value(activity, "is_key", 0) or 0) else "记录"
            lines.append(
                f"- {marker}｜{_clean_text(_row_value(activity, 'happened_at')) or '未记录时间'}｜{_clean_text(_row_value(activity, 'title')) or '未命名活动'}：{_clean_text(_row_value(activity, 'summary')) or '无摘要'}"
            )

    attachment_rows = db.fetchall(
        "SELECT file_name, file_type, description, local_path, uploaded_at FROM event_line_attachments WHERE event_line_id = ? ORDER BY uploaded_at DESC LIMIT 20",
        (event_line_id,),
    )
    if attachment_rows:
        lines.extend(["", "## 相关附件"])
        for attachment in attachment_rows:
            lines.append(
                f"- {_clean_text(_row_value(attachment, 'file_name')) or '未命名附件'}｜类型：{_clean_text(_row_value(attachment, 'file_type')) or '未知'}｜说明：{_clean_text(_row_value(attachment, 'description')) or '无'}"
            )

    judgment_rows = db.fetchall(
        """
        SELECT topic, status, risk_level, confidence, summary, updated_at
        FROM judgment_versions
        WHERE target_type = 'event_line' AND target_id = ?
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (event_line_id,),
    )
    if judgment_rows:
        lines.extend(["", "## 相关判断"])
        for judgment in judgment_rows:
            lines.append(
                f"- {_clean_text(_row_value(judgment, 'topic')) or '未命名判断'}｜状态：{_clean_text(_row_value(judgment, 'status')) or '未标注'}｜风险：{_clean_text(_row_value(judgment, 'risk_level')) or '未标注'}｜{_clean_text(_row_value(judgment, 'summary'))}"
            )

    return "\n".join(lines)


def _materialize_event_line_docs(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    client_name: str,
    upsert: UpsertCanonicalTextDocument,
    now_iso: Callable[[], str],
) -> int:
    rows = db.fetchall(
        """
        SELECT DISTINCT el.*
        FROM event_lines el
        LEFT JOIN tasks t ON t.event_line_id = el.id AND t.client_id = ?
        WHERE el.primary_client_id = ? OR t.id IS NOT NULL
        ORDER BY COALESCE(NULLIF(el.updated_at, ''), el.created_at) DESC
        """,
        (client_id, client_id),
    )
    count = 0
    for row in rows:
        sources: list[tuple[str, str]] = []
        if _clean_text(_row_value(row, "primary_client_id")) == client_id:
            sources.append(("strong", "事件线 primary_client_id 直接指向当前客户。"))
        task_count = int(
            db.scalar(
                "SELECT COUNT(*) FROM tasks WHERE client_id = ? AND event_line_id = ?",
                (client_id, str(_row_value(row, "id"))),
            )
            or 0
        )
        if task_count:
            sources.append(("medium", f"当前客户有 {task_count} 条任务关联这条事件线。"))
        text = _render_event_line_doc(db, client_id=client_id, client_name=client_name, row=row, relation_sources=sources)
        if upsert(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind="event_line_doc",
            origin_type="event_line",
            origin_id=str(_row_value(row, "id")),
            title=f"事件线：{_clean_text(_row_value(row, 'name')) or _row_value(row, 'id')}",
            text=text,
            visible_category="事件线资料",
            secondary_category="软件沉淀",
            created_at=str(_row_value(row, "created_at") or now_iso()),
            updated_at=str(_row_value(row, "updated_at") or _row_value(row, "created_at") or now_iso()),
        ):
            count += 1
    return count


def _render_project_module_doc(db: Database, *, client_id: str, client_name: str, row: Any) -> str:
    module_id = str(_row_value(row, "id"))
    name = _clean_text(_row_value(row, "name")) or module_id
    lines = [
        f"# 项目模块：{name}",
        "",
        "## 基本信息",
        f"- 客户：{client_name or client_id}",
        "- 关系置信度：strong",
        "- 关系来源：project_modules.client_id 直接指向当前客户。",
    ]
    _append_field(lines, "别名", _row_value(row, "alias"))
    _append_field(lines, "负责人", _row_value(row, "owner_name"))
    goal = _clean_text(_row_value(row, "goal"))
    description = _clean_text(_row_value(row, "description"))
    lines.extend(["", "## 项目说明"])
    if goal:
        lines.append(f"- 目标：{goal}")
    if description:
        lines.append(description)
    if not goal and not description:
        lines.append("暂无明确项目说明。")

    deliverables = [_clean_text(item) for item in _json_list(_row_value(row, "deliverables_json")) if _clean_text(item)]
    if deliverables:
        lines.extend(["", "## 交付物"])
        lines.extend(f"- {item}" for item in deliverables[:20])
    keywords = [_clean_text(item) for item in _json_list(_row_value(row, "keywords_json")) if _clean_text(item)]
    if keywords:
        lines.extend(["", "## 关键词", "- " + "、".join(keywords[:30])])

    flow_rows = db.fetchall("SELECT name, description, scenario FROM project_flows WHERE client_id = ? AND module_id = ? ORDER BY updated_at DESC LIMIT 20", (client_id, module_id))
    if flow_rows:
        lines.extend(["", "## 相关流程"])
        for flow in flow_rows:
            lines.append(f"- {_clean_text(_row_value(flow, 'name')) or '未命名流程'}：{_clean_text(_row_value(flow, 'description')) or _clean_text(_row_value(flow, 'scenario')) or '暂无说明'}")

    task_rows = db.fetchall(
        """
        SELECT t.*, pm.name AS project_module_name, pf.name AS project_flow_name, el.name AS event_line_name
        FROM tasks t
        LEFT JOIN project_modules pm ON pm.id = t.project_module_id
        LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        WHERE t.client_id = ? AND t.project_module_id = ?
        ORDER BY COALESCE(NULLIF(t.updated_at, ''), t.created_at) DESC
        LIMIT 20
        """,
        (client_id, module_id),
    )
    if task_rows:
        lines.extend(["", "## 相关任务"])
        lines.extend(_task_line(task) for task in task_rows)
    return "\n".join(lines)


def _render_project_flow_doc(db: Database, *, client_id: str, client_name: str, row: Any) -> str:
    flow_id = str(_row_value(row, "id"))
    name = _clean_text(_row_value(row, "name")) or flow_id
    module_name = _clean_text(_row_value(row, "module_name"))
    lines = [
        f"# 项目流程：{name}",
        "",
        "## 基本信息",
        f"- 客户：{client_name or client_id}",
        "- 关系置信度：strong",
        "- 关系来源：project_flows.client_id 直接指向当前客户。",
    ]
    _append_field(lines, "所属项目模块", module_name)
    lines.extend(["", "## 项目说明"])
    description = _clean_text(_row_value(row, "description"))
    scenario = _clean_text(_row_value(row, "scenario"))
    if description:
        lines.append(description)
    if scenario:
        lines.append(f"- 场景：{scenario}")
    if not description and not scenario:
        lines.append("暂无明确项目说明。")

    for label, key in (
        ("触发条件", "trigger_condition"),
        ("步骤", "steps_json"),
        ("输入", "inputs_json"),
        ("输出", "outputs_json"),
        ("协作者", "collaborators_json"),
        ("风险点", "risk_points_json"),
    ):
        value = _row_value(row, key)
        if key.endswith("_json"):
            items = [_clean_text(item) for item in _json_list(value) if _clean_text(item)]
            if items:
                lines.extend(["", f"## {label}"])
                lines.extend(f"- {item}" for item in items[:20])
        else:
            _append_field(lines, label, value)

    task_rows = db.fetchall(
        """
        SELECT t.*, pm.name AS project_module_name, pf.name AS project_flow_name, el.name AS event_line_name
        FROM tasks t
        LEFT JOIN project_modules pm ON pm.id = t.project_module_id
        LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        WHERE t.client_id = ? AND t.project_flow_id = ?
        ORDER BY COALESCE(NULLIF(t.updated_at, ''), t.created_at) DESC
        LIMIT 20
        """,
        (client_id, flow_id),
    )
    if task_rows:
        lines.extend(["", "## 相关任务"])
        lines.extend(_task_line(task) for task in task_rows)
    return "\n".join(lines)


def _materialize_project_docs(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    client_name: str,
    upsert: UpsertCanonicalTextDocument,
    now_iso: Callable[[], str],
) -> int:
    count = 0
    module_rows = db.fetchall("SELECT * FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
    for row in module_rows:
        if upsert(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind="project_doc",
            origin_type="project_module",
            origin_id=str(_row_value(row, "id")),
            title=f"项目模块：{_clean_text(_row_value(row, 'name')) or _row_value(row, 'id')}",
            text=_render_project_module_doc(db, client_id=client_id, client_name=client_name, row=row),
            visible_category="项目资料",
            secondary_category="软件沉淀",
            created_at=str(_row_value(row, "created_at") or now_iso()),
            updated_at=str(_row_value(row, "updated_at") or _row_value(row, "created_at") or now_iso()),
        ):
            count += 1

    flow_rows = db.fetchall(
        """
        SELECT f.*, m.name AS module_name
        FROM project_flows f
        LEFT JOIN project_modules m ON m.id = f.module_id
        WHERE f.client_id = ?
        ORDER BY f.updated_at DESC
        """,
        (client_id,),
    )
    for row in flow_rows:
        if upsert(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind="project_doc",
            origin_type="project_flow",
            origin_id=str(_row_value(row, "id")),
            title=f"项目流程：{_clean_text(_row_value(row, 'name')) or _row_value(row, 'id')}",
            text=_render_project_flow_doc(db, client_id=client_id, client_name=client_name, row=row),
            visible_category="项目资料",
            secondary_category="软件沉淀",
            created_at=str(_row_value(row, "created_at") or now_iso()),
            updated_at=str(_row_value(row, "updated_at") or _row_value(row, "created_at") or now_iso()),
        ):
            count += 1
    return count


def _review_text(row: Any) -> str:
    return "\n".join(
        _clean_text(_row_value(row, key))
        for key in (
            "week_label",
            "summary",
            "work_progress",
            "work_blocker",
            "blocker_type",
            "work_direction",
            "next_week_focus",
            "support_needed",
            "work_free_note",
            "personal_growth_note",
        )
        if _clean_text(_row_value(row, key))
    )


def _review_relation_sources(db: Database, *, client_id: str, row: Any, client_terms: list[str], project_terms: list[str], event_line_terms: list[str]) -> list[tuple[str, str]]:
    review_id = str(_row_value(row, "id"))
    sources: list[tuple[str, str]] = []
    direct_task_count = int(
        db.scalar(
            """
            SELECT COUNT(*)
            FROM weekly_review_task_entries e
            JOIN tasks t ON t.id = e.task_id
            WHERE e.review_id = ? AND t.client_id = ?
            """,
            (review_id, client_id),
        )
        or 0
    )
    if direct_task_count:
        sources.append(("strong", f"复盘关联了当前客户的 {direct_task_count} 条任务。"))

    indirect_count = int(
        db.scalar(
            """
            SELECT COUNT(*)
            FROM weekly_review_task_entries e
            JOIN tasks t ON t.id = e.task_id
            LEFT JOIN project_modules pm ON pm.id = t.project_module_id
            LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
            LEFT JOIN event_lines el ON el.id = t.event_line_id
            WHERE e.review_id = ?
              AND (
                pm.client_id = ?
                OR pf.client_id = ?
                OR el.primary_client_id = ?
              )
            """,
            (review_id, client_id, client_id, client_id),
        )
        or 0
    )
    if indirect_count and not direct_task_count:
        sources.append(("medium", f"复盘通过项目或事件线间接关联当前客户 {indirect_count} 次。"))

    text = _review_text(row)
    matched_client_terms = _text_contains_any(text, client_terms)
    if matched_client_terms:
        sources.append(("weak", f"复盘正文命中客户词：{'、'.join(matched_client_terms[:5])}。"))
    matched_project_terms = _text_contains_any(text, project_terms)
    if matched_project_terms:
        sources.append(("weak", f"复盘正文命中项目词：{'、'.join(matched_project_terms[:5])}。"))
    matched_event_line_terms = _text_contains_any(text, event_line_terms)
    if matched_event_line_terms:
        sources.append(("weak", f"复盘正文命中事件线词：{'、'.join(matched_event_line_terms[:5])}。"))
    return sources


def _render_review_doc(db: Database, *, client_id: str, client_name: str, row: Any, relation_sources: list[tuple[str, str]]) -> str:
    lines = [
        f"# 周复盘：{_clean_text(_row_value(row, 'week_label')) or _row_value(row, 'id')}",
        "",
        "## 关联客户",
        f"- 客户：{client_name or client_id}",
        *_render_relation_sources(relation_sources),
        "",
        "## 基本信息",
    ]
    _append_field(lines, "提交时间", _row_value(row, "submitted_at") or _row_value(row, "updated_at") or _row_value(row, "created_at"))
    for label, key in (
        ("工作总结", "summary"),
        ("工作进展", "work_progress"),
        ("工作阻塞", "work_blocker"),
        ("阻塞类型", "blocker_type"),
        ("工作方向", "work_direction"),
        ("下周重点", "next_week_focus"),
        ("需要支持", "support_needed"),
        ("自由备注", "work_free_note"),
        ("成长备注", "personal_growth_note"),
    ):
        value = _clean_text(_row_value(row, key))
        if value:
            lines.extend(["", f"## {label}", "", value])

    entry_rows = db.fetchall(
        """
        SELECT e.note, e.content_domain, e.task_snapshot_json, t.title, t.client_id, t.status, t.due_date, t.ddl
        FROM weekly_review_task_entries e
        LEFT JOIN tasks t ON t.id = e.task_id
        WHERE e.review_id = ?
        ORDER BY e.updated_at DESC
        LIMIT 20
        """,
        (str(_row_value(row, "id")),),
    )
    if entry_rows:
        lines.extend(["", "## 关联任务记录"])
        for entry in entry_rows:
            title = _clean_text(_row_value(entry, "title")) or "未命名任务"
            note = _clean_text(_row_value(entry, "note"))
            lines.append(f"- {title}｜状态：{_clean_text(_row_value(entry, 'status')) or '未标注'}｜记录：{note or '无'}")
    return "\n".join(lines)


def _materialize_review_docs(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    client_name: str,
    upsert: UpsertCanonicalTextDocument,
    now_iso: Callable[[], str],
) -> int:
    client_row = _client_row(db, client_id)
    client_terms = _common_client_terms(client_name, _clean_text(_row_value(client_row, "alias")) if client_row else "")
    project_rows = db.fetchall("SELECT name, alias FROM project_modules WHERE client_id = ?", (client_id,))
    flow_rows = db.fetchall("SELECT name FROM project_flows WHERE client_id = ?", (client_id,))
    event_line_rows = db.fetchall("SELECT name FROM event_lines WHERE primary_client_id = ? OR id IN (SELECT event_line_id FROM tasks WHERE client_id = ? AND event_line_id IS NOT NULL)", (client_id, client_id))
    project_terms = [_clean_text(_row_value(row, "name")) for row in project_rows] + [_clean_text(_row_value(row, "alias")) for row in project_rows] + [_clean_text(_row_value(row, "name")) for row in flow_rows]
    event_line_terms = [_clean_text(_row_value(row, "name")) for row in event_line_rows]

    count = 0
    review_rows = db.fetchall("SELECT * FROM weekly_reviews ORDER BY COALESCE(NULLIF(updated_at, ''), created_at) DESC")
    for row in review_rows:
        relation_sources = _review_relation_sources(
            db,
            client_id=client_id,
            row=row,
            client_terms=[term for term in client_terms if term],
            project_terms=[term for term in project_terms if term],
            event_line_terms=[term for term in event_line_terms if term],
        )
        if not relation_sources:
            continue
        title = f"周复盘：{_clean_text(_row_value(row, 'week_label')) or _row_value(row, 'id')}（{client_name or client_id}相关）"
        if upsert(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind="review_doc",
            origin_type="weekly_review",
            origin_id=f"{_row_value(row, 'id')}:{client_id}",
            title=title,
            text=_render_review_doc(db, client_id=client_id, client_name=client_name, row=row, relation_sources=relation_sources),
            visible_category="周复盘",
            secondary_category="软件沉淀",
            created_at=str(_row_value(row, "created_at") or now_iso()),
            updated_at=str(_row_value(row, "updated_at") or _row_value(row, "created_at") or now_iso()),
        ):
            count += 1
    return count


def _calendar_item_time(row: Any) -> str:
    return (
        _clean_text(_row_value(row, "starts_at"))
        or _clean_text(_row_value(row, "scheduled_at"))
        or _clean_text(_row_value(row, "due_date"))
        or _clean_text(_row_value(row, "ddl"))
        or _clean_text(_row_value(row, "created_at"))
    )


def _materialize_calendar_doc(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    client_name: str,
    upsert: UpsertCanonicalTextDocument,
    now_iso: Callable[[], str],
) -> int:
    task_columns = _table_columns(db, "tasks")
    date_columns = [column for column in ("starts_at", "due_date", "ddl", "ends_at", "start_date") if column in task_columns]
    if date_columns:
        date_condition = " OR ".join(f"COALESCE(NULLIF(t.{column}, ''), '') != ''" for column in date_columns)
        date_order = "COALESCE(" + ", ".join(f"NULLIF(t.{column}, '')" for column in date_columns) + ", t.created_at)"
    else:
        date_condition = "1 = 0"
        date_order = "t.created_at"
    task_rows = db.fetchall(
        f"""
        SELECT t.*, pm.name AS project_module_name, pf.name AS project_flow_name, el.name AS event_line_name
        FROM tasks t
        LEFT JOIN project_modules pm ON pm.id = t.project_module_id
        LEFT JOIN project_flows pf ON pf.id = t.project_flow_id
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        WHERE t.client_id = ?
          AND ({date_condition})
        ORDER BY {date_order} DESC
        LIMIT 80
        """,
        (client_id,),
    )
    meeting_rows = db.fetchall(
        "SELECT id, title, stage, scheduled_at, updated_at FROM meetings WHERE client_id = ? AND COALESCE(NULLIF(scheduled_at, ''), '') != '' ORDER BY scheduled_at DESC LIMIT 80",
        (client_id,),
    )
    if not task_rows and not meeting_rows:
        return 0
    lines = [
        f"# 客户日历与节奏：{client_name or client_id}",
        "",
        "## 资料边界",
        "- 关系置信度：strong",
        "- 关系来源：来自当前客户任务时间字段和会议时间字段。",
        "- 说明：这不是完整飞书日历，只代表软件内已经沉淀的任务与会议时间。",
    ]
    if task_rows:
        lines.extend(["", "## 任务时间"])
        for task in task_rows:
            time_value = _calendar_item_time(task)
            lines.append(f"- {time_value or '未记录时间'}｜任务：{_task_line(task).removeprefix('- ')}")
    if meeting_rows:
        lines.extend(["", "## 会议时间"])
        for meeting in meeting_rows:
            lines.append(f"- {_clean_text(_row_value(meeting, 'scheduled_at')) or '未记录时间'}｜会议：{_clean_text(_row_value(meeting, 'title')) or _row_value(meeting, 'id')}｜阶段：{_clean_text(_row_value(meeting, 'stage')) or '未标注'}")
    updated_at = now_iso()
    if task_rows:
        updated_at = str(_row_value(task_rows[0], "updated_at") or updated_at)
    if meeting_rows and str(_row_value(meeting_rows[0], "updated_at") or "") > updated_at:
        updated_at = str(_row_value(meeting_rows[0], "updated_at"))
    return 1 if upsert(
        db,
        data_dir=data_dir,
        client_id=client_id,
        canonical_kind="calendar_doc",
        origin_type="calendar_rollup",
        origin_id=client_id,
        title=f"客户日历与节奏：{client_name or client_id}",
        text="\n".join(lines),
        visible_category="日历节奏",
        secondary_category="软件沉淀",
        created_at=updated_at,
        updated_at=updated_at,
    ) else 0


def materialize_workspace_relation_documents(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    upsert_canonical_text_document: UpsertCanonicalTextDocument,
    now_iso: Callable[[], str],
) -> dict[str, int]:
    client = _client_row(db, client_id)
    client_name = _clean_text(_row_value(client, "name")) if client else client_id
    counts = {"event_line_doc": 0, "project_doc": 0, "review_doc": 0, "calendar_doc": 0}
    counts["event_line_doc"] = _materialize_event_line_docs(
        db,
        data_dir=data_dir,
        client_id=client_id,
        client_name=client_name,
        upsert=upsert_canonical_text_document,
        now_iso=now_iso,
    )
    counts["project_doc"] = _materialize_project_docs(
        db,
        data_dir=data_dir,
        client_id=client_id,
        client_name=client_name,
        upsert=upsert_canonical_text_document,
        now_iso=now_iso,
    )
    counts["review_doc"] = _materialize_review_docs(
        db,
        data_dir=data_dir,
        client_id=client_id,
        client_name=client_name,
        upsert=upsert_canonical_text_document,
        now_iso=now_iso,
    )
    counts["calendar_doc"] = _materialize_calendar_doc(
        db,
        data_dir=data_dir,
        client_id=client_id,
        client_name=client_name,
        upsert=upsert_canonical_text_document,
        now_iso=now_iso,
    )
    return counts
