from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.db import Database, from_json
from app.models import (
    DnaToolPurpose,
    OrganizationDnaRefreshEventRecord,
    OrganizationDnaRefreshRunRecord,
    OrganizationDnaToolContextRecord,
    OrganizationDnaV2ItemRecord,
    OrganizationDnaV2Kind,
    OrganizationDnaV2SnapshotRecord,
)

EventCallback = Callable[[str, str, dict[str, object]], None]

_KIND_ORDER: dict[str, int] = {
    "stable_dna": 0,
    "evolving_dna": 1,
    "gap_dna": 2,
    "risk_dna": 3,
}
_STATUS_ORDER: dict[str, int] = {
    "confirmed": 0,
    "candidate": 1,
    "stale": 2,
    "deprecated": 3,
}
_PURPOSE_KIND_MAP: dict[str, list[str]] = {
    "intro": ["stable_dna", "risk_dna"],
    "strategy": ["stable_dna", "evolving_dna", "risk_dna"],
    "task_next_action": ["evolving_dna", "gap_dna", "risk_dna"],
    "asset_gap": ["gap_dna", "evolving_dna", "risk_dna"],
    "public_material": ["stable_dna", "risk_dna"],
    "risk_check": ["risk_dna", "stable_dna"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _stable_id(module_kind: str, source_type: str, source_id: str, title: str) -> str:
    digest = hashlib.sha1(f"{module_kind}|{source_type}|{source_id}|{title}".encode("utf-8")).hexdigest()[:16]
    return f"orgdna_{digest}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _list_text(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values[:limit]:
        if isinstance(value, str):
            text = value.strip()
        else:
            title = _text(_get(value, "title"))
            statement = _text(_get(value, "statement"))
            objective = _text(_get(value, "objective"))
            text = "：".join([part for part in [title, statement or objective] if part])
        if text:
            result.append(text)
    return result


def _clip(value: str, limit: int = 420) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _markdown(title: str, lines: list[str], *, source_label: str, observed_at: str) -> str:
    body = [f"# {title}", "", f"- 来源：{source_label}", f"- 观察时间：{observed_at}", ""]
    body.extend(line for line in lines if _text(line))
    return "\n".join(body).strip()


def _item(
    *,
    module_kind: OrganizationDnaV2Kind,
    title: str,
    lines: list[str],
    summary: str,
    status: str,
    evidence_level: str,
    source_type: str,
    source_id: str,
    source_label: str,
    observed_at: str,
    source_created_at: str | None = None,
    valid_days: int = 90,
    confidence_score: int = 60,
    now: str,
) -> OrganizationDnaV2ItemRecord:
    content = _markdown(title, lines, source_label=source_label, observed_at=observed_at)
    return OrganizationDnaV2ItemRecord(
        id=_stable_id(module_kind, source_type, source_id, title),
        moduleKind=module_kind,
        title=title,
        contentMarkdown=content,
        summary=_clip(summary or "\n".join(lines), 220),
        status=status,  # type: ignore[arg-type]
        evidenceLevel=evidence_level,  # type: ignore[arg-type]
        sourceType=source_type,
        sourceId=source_id,
        sourceLabel=source_label,
        observedAt=observed_at,
        sourceCreatedAt=source_created_at,
        lastSeenAt=now,
        validUntil=_future_iso(valid_days) if valid_days > 0 else None,
        confidenceScore=max(0, min(100, int(confidence_score))),
        createdAt=now,
        updatedAt=now,
    )


def _row_to_item(row: Any) -> OrganizationDnaV2ItemRecord:
    return OrganizationDnaV2ItemRecord(
        id=str(row["id"]),
        moduleKind=str(row["module_kind"]),  # type: ignore[arg-type]
        title=str(row["title"]),
        contentMarkdown=str(row["content_markdown"]),
        summary=str(row["summary"] or ""),
        status=str(row["status"]),  # type: ignore[arg-type]
        evidenceLevel=str(row["evidence_level"]),  # type: ignore[arg-type]
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        sourceLabel=str(row["source_label"]),
        observedAt=str(row["observed_at"]),
        sourceCreatedAt=str(row["source_created_at"]) if row["source_created_at"] else None,
        lastSeenAt=str(row["last_seen_at"]),
        validUntil=str(row["valid_until"]) if row["valid_until"] else None,
        confidenceScore=int(row["confidence_score"] or 0),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _row_to_event(row: Any) -> OrganizationDnaRefreshEventRecord:
    detail = from_json(str(row["detail_json"] or "{}"), {})
    if not isinstance(detail, dict):
        detail = {}
    return OrganizationDnaRefreshEventRecord(
        id=str(row["id"]),
        runId=str(row["run_id"]),
        level=str(row["level"] or "info"),  # type: ignore[arg-type]
        message=str(row["message"] or ""),
        detail=detail,  # type: ignore[arg-type]
        createdAt=str(row["created_at"]),
    )


def _row_to_run(db: Database, row: Any, *, include_events: bool = False) -> OrganizationDnaRefreshRunRecord:
    events: list[OrganizationDnaRefreshEventRecord] = []
    if include_events:
        event_rows = db.fetchall(
            """
            SELECT * FROM organization_dna_refresh_events
            WHERE run_id = ?
            ORDER BY created_at ASC
            """,
            (str(row["id"]),),
        )
        events = [_row_to_event(event) for event in event_rows]
    return OrganizationDnaRefreshRunRecord(
        id=str(row["id"]),
        jobType="organization_dna_refresh",
        status=str(row["status"] or "queued"),  # type: ignore[arg-type]
        triggerSource=str(row["trigger_source"] or "manual"),
        totalItems=int(row["total_items"] or 0),
        processedItems=int(row["processed_items"] or 0),
        error=str(row["error"]) if row["error"] else None,
        createdAt=str(row["created_at"]),
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        finishedAt=str(row["finished_at"]) if row["finished_at"] else None,
        updatedAt=str(row["updated_at"]),
        events=events,
    )


def _upsert_item(db: Database, item: OrganizationDnaV2ItemRecord) -> None:
    db.execute(
        """
        INSERT INTO organization_dna_v2_items(
            id, module_kind, title, content_markdown, summary, status, evidence_level,
            source_type, source_id, source_label, observed_at, source_created_at,
            last_seen_at, valid_until, confidence_score, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            module_kind = excluded.module_kind,
            title = excluded.title,
            content_markdown = excluded.content_markdown,
            summary = excluded.summary,
            status = excluded.status,
            evidence_level = excluded.evidence_level,
            source_type = excluded.source_type,
            source_id = excluded.source_id,
            source_label = excluded.source_label,
            observed_at = excluded.observed_at,
            source_created_at = excluded.source_created_at,
            last_seen_at = excluded.last_seen_at,
            valid_until = excluded.valid_until,
            confidence_score = excluded.confidence_score,
            updated_at = excluded.updated_at
        """,
        (
            item.id,
            item.moduleKind,
            item.title,
            item.contentMarkdown,
            item.summary,
            item.status,
            item.evidenceLevel,
            item.sourceType,
            item.sourceId,
            item.sourceLabel,
            item.observedAt,
            item.sourceCreatedAt,
            item.lastSeenAt,
            item.validUntil,
            item.confidenceScore,
            item.createdAt,
            item.updatedAt,
        ),
    )


def _mark_stale_missing_items(db: Database, seen_ids: set[str], now: str) -> int:
    if not seen_ids:
        db.execute(
            """
            UPDATE organization_dna_v2_items
            SET status = 'stale', updated_at = ?
            WHERE status NOT IN ('stale', 'deprecated')
            """,
            (now,),
        )
        return int(db.scalar("SELECT changes() AS count"))
    placeholders = ",".join("?" for _ in seen_ids)
    params: tuple[Any, ...] = (now, *sorted(seen_ids))
    db.execute(
        f"""
        UPDATE organization_dna_v2_items
        SET status = 'stale', updated_at = ?
        WHERE status NOT IN ('stale', 'deprecated')
          AND id NOT IN ({placeholders})
        """,
        params,
    )
    return int(db.scalar("SELECT changes() AS count"))


def _emit(event_callback: EventCallback | None, level: str, message: str, detail: dict[str, object] | None = None) -> None:
    if event_callback:
        event_callback(level, message, detail or {})


def _collect_org_model_items(org_model: Any, now: str) -> list[OrganizationDnaV2ItemRecord]:
    items: list[OrganizationDnaV2ItemRecord] = []
    organization = _get(org_model, "organization")
    org_name = _text(_get(organization, "name")) or "当前组织"
    org_updated_at = _text(_get(organization, "updatedAt")) or now
    annual_goal = _text(_get(organization, "annualGoal"))
    annual_strategy = _text(_get(organization, "annualStrategy"))
    annual_year = _text(_get(organization, "annualStrategyYear"))
    quarterly_focus = _list_text(_get(organization, "quarterlyFocus"), limit=6)
    focus_items = _list_text(_get(org_model, "focusItems"), limit=8)
    departments = _get(org_model, "departments") or []
    department_lines: list[str] = []
    if isinstance(departments, list):
        for department in departments[:8]:
            name = _text(_get(department, "name"))
            mission = _text(_get(department, "mission"))
            business = _text(_get(department, "businessContext"))
            if name:
                department_lines.append(f"- {name}：{mission or business or '暂无明确使命说明'}")

    stable_lines = [f"## 组织名称\n{org_name}"]
    if annual_goal:
        stable_lines.append(f"## 年度目标\n{annual_goal}")
    if annual_strategy:
        label = f"{annual_year} 年度战略" if annual_year else "年度战略"
        stable_lines.append(f"## {label}\n{annual_strategy}")
    if quarterly_focus:
        stable_lines.append("## 近期重点\n" + "\n".join(f"- {item}" for item in quarterly_focus))
    if focus_items:
        stable_lines.append("## 组织焦点\n" + "\n".join(f"- {item}" for item in focus_items))
    if department_lines:
        stable_lines.append("## 业务/部门体系\n" + "\n".join(department_lines))

    if len("\n".join(stable_lines)) > 30:
        items.append(
            _item(
                module_kind="stable_dna",
                title=f"{org_name}稳定组织画像",
                lines=stable_lines,
                summary=f"{org_name}的稳定定位、年度目标、战略重点和业务体系。",
                status="confirmed" if annual_goal or annual_strategy or focus_items else "candidate",
                evidence_level="internal",
                source_type="org_model",
                source_id=_text(_get(organization, "organizationId")) or "current_org",
                source_label="组织模型",
                observed_at=org_updated_at,
                source_created_at=org_updated_at,
                valid_days=180,
                confidence_score=82 if annual_goal or annual_strategy else 64,
                now=now,
            )
        )

    intro = _get(organization, "introDocument")
    intro_text = _text(_get(intro, "summary")) or _clip(_text(_get(intro, "normalizedText")), 1200)
    if intro_text:
        items.append(
            _item(
                module_kind="stable_dna",
                title=f"{org_name}介绍资料摘要",
                lines=["## 介绍资料", intro_text],
                summary=intro_text,
                status="confirmed",
                evidence_level="internal",
                source_type="org_intro_document",
                source_id=_text(_get(intro, "contentHash")) or _text(_get(intro, "fileName")) or "org_intro_document",
                source_label=_text(_get(intro, "fileName")) or "组织介绍资料",
                observed_at=_text(_get(intro, "uploadedAt")) or org_updated_at,
                source_created_at=_text(_get(intro, "uploadedAt")) or org_updated_at,
                valid_days=180,
                confidence_score=88,
                now=now,
            )
        )
    return items


def _collect_task_items(db: Database, now: str) -> list[OrganizationDnaV2ItemRecord]:
    recent_rows = db.fetchall(
        """
        SELECT id, title, description, status, progress_status, priority, owner_name,
               current_blocker, next_action, recent_decision, business_category,
               event_line_id, created_at, updated_at,
               '' AS related_client_name
        FROM tasks
        ORDER BY updated_at DESC
        LIMIT 40
        """
    )
    client_signal_rows = db.fetchall(
        """
        SELECT t.id, t.title, t.description, t.status, t.progress_status, t.priority, t.owner_name,
               t.current_blocker, t.next_action, t.recent_decision, t.business_category,
               t.event_line_id, t.created_at, t.updated_at,
               COALESCE(
                   source_client.name,
                   event_client.name,
                   (
                       SELECT c.name
                       FROM clients c
                       WHERE t.title LIKE '%' || c.name || '%'
                          OR t.description LIKE '%' || c.name || '%'
                          OR (c.alias != '' AND t.title LIKE '%' || c.alias || '%')
                          OR (c.alias != '' AND t.description LIKE '%' || c.alias || '%')
                       LIMIT 1
                   ),
                   ''
               ) AS related_client_name
        FROM tasks t
        LEFT JOIN event_lines e ON e.id = t.event_line_id
        LEFT JOIN clients source_client ON source_client.id = t.source_id
        LEFT JOIN clients event_client ON event_client.id = e.primary_client_id
        WHERE source_client.id IS NOT NULL
           OR event_client.id IS NOT NULL
           OR EXISTS (
               SELECT 1
               FROM clients c
               WHERE t.title LIKE '%' || c.name || '%'
                  OR t.description LIKE '%' || c.name || '%'
                  OR (c.alias != '' AND t.title LIKE '%' || c.alias || '%')
                  OR (c.alias != '' AND t.description LIKE '%' || c.alias || '%')
           )
        ORDER BY t.updated_at DESC
        LIMIT 80
        """
    )
    rows_by_id: dict[str, Any] = {}
    for row in list(recent_rows) + list(client_signal_rows):
        rows_by_id[str(row["id"])] = row
    rows = sorted(rows_by_id.values(), key=lambda row: str(row["updated_at"] or ""), reverse=True)
    items: list[OrganizationDnaV2ItemRecord] = []
    for row in rows:
        title = _text(row["title"])
        if not title:
            continue
        related_client_name = _text(row["related_client_name"])
        description = _clip(_text(row["description"]), 500)
        next_action = _clip(_text(row["next_action"]), 260)
        blocker = _clip(_text(row["current_blocker"]), 260)
        decision = _clip(_text(row["recent_decision"]), 260)
        if len(description + next_action + blocker + decision) < 24:
            continue
        lines = [f"## 任务\n{title}", f"- 状态：{_text(row['progress_status']) or _text(row['status'])}"]
        if related_client_name:
            lines.append(f"- 关联客户：{related_client_name}")
        if _text(row["business_category"]):
            lines.append(f"- 业务分类：{_text(row['business_category'])}")
        if description:
            lines.append(f"## 背景\n{description}")
        if decision:
            lines.append(f"## 最近决策\n{decision}")
        if next_action:
            lines.append(f"## 下一步\n{next_action}")
        if blocker:
            lines.append(f"## 当前阻塞\n{blocker}")
        items.append(
            _item(
                module_kind="evolving_dna",
                title=f"任务演化信号：{title}",
                lines=lines,
                summary=next_action or decision or description or title,
                status="candidate",
                evidence_level="internal",
                source_type="task",
                source_id=str(row["id"]),
                source_label=f"任务：{title}" + (f"（{related_client_name}）" if related_client_name else ""),
                observed_at=_text(row["updated_at"]) or now,
                source_created_at=_text(row["created_at"]) or None,
                valid_days=45,
                confidence_score=74 if related_client_name else 68,
                now=now,
            )
        )
    return items


def _collect_review_items(db: Database, now: str) -> list[OrganizationDnaV2ItemRecord]:
    rows = db.fetchall(
        """
        SELECT id, week_label, work_progress, work_blocker, work_direction,
               next_week_focus, support_needed, summary, work_free_note,
               submitted_at, created_at, updated_at
        FROM weekly_reviews
        ORDER BY COALESCE(NULLIF(submitted_at, ''), updated_at, created_at) DESC
        LIMIT 16
        """
    )
    items: list[OrganizationDnaV2ItemRecord] = []
    for row in rows:
        week_label = _text(row["week_label"]) or "最近复盘"
        summary = _clip(_text(row["summary"]), 500)
        progress = _clip(_text(row["work_progress"]), 500)
        direction = _clip(_text(row["work_direction"]), 360)
        next_focus = _clip(_text(row["next_week_focus"]), 360)
        blocker = _clip(_text(row["work_blocker"]), 300)
        support = _clip(_text(row["support_needed"]), 300)
        if len(summary + progress + direction + next_focus + blocker + support) < 24:
            continue
        lines = [f"## 周复盘\n{week_label}"]
        if summary:
            lines.append(f"## 总结\n{summary}")
        if progress:
            lines.append(f"## 进展\n{progress}")
        if direction:
            lines.append(f"## 方向\n{direction}")
        if next_focus:
            lines.append(f"## 下周重点\n{next_focus}")
        if blocker:
            lines.append(f"## 阻塞\n{blocker}")
        if support:
            lines.append(f"## 需要支持\n{support}")
        items.append(
            _item(
                module_kind="evolving_dna",
                title=f"复盘演化信号：{week_label}",
                lines=lines,
                summary=summary or next_focus or direction,
                status="candidate",
                evidence_level="internal",
                source_type="weekly_review",
                source_id=str(row["id"]),
                source_label=f"周复盘：{week_label}",
                observed_at=_text(row["submitted_at"]) or _text(row["updated_at"]) or now,
                source_created_at=_text(row["created_at"]) or None,
                valid_days=45,
                confidence_score=70,
                now=now,
            )
        )
    return items


def _collect_event_line_items(db: Database, now: str) -> list[OrganizationDnaV2ItemRecord]:
    rows = db.fetchall(
        """
        SELECT id, name, kind, status, business_category, stage, summary, intent,
               current_blocker, recent_decision, next_step, primary_client_name,
               created_at, updated_at
        FROM event_lines
        ORDER BY updated_at DESC
        LIMIT 80
        """
    )
    items: list[OrganizationDnaV2ItemRecord] = []
    for row in rows:
        name = _text(row["name"])
        if not name:
            continue
        summary = _clip(_text(row["summary"]), 500)
        intent = _clip(_text(row["intent"]), 360)
        next_step = _clip(_text(row["next_step"]), 300)
        blocker = _clip(_text(row["current_blocker"]), 300)
        decision = _clip(_text(row["recent_decision"]), 300)
        if len(summary + intent + next_step + blocker + decision) < 24:
            continue
        lines = [f"## 事件线\n{name}", f"- 阶段：{_text(row['stage']) or '未标注'}", f"- 状态：{_text(row['status']) or 'active'}"]
        if _text(row["primary_client_name"]):
            lines.append(f"- 关联客户：{_text(row['primary_client_name'])}")
        if intent:
            lines.append(f"## 意图\n{intent}")
        if summary:
            lines.append(f"## 摘要\n{summary}")
        if decision:
            lines.append(f"## 最近决策\n{decision}")
        if next_step:
            lines.append(f"## 下一步\n{next_step}")
        if blocker:
            lines.append(f"## 阻塞\n{blocker}")
        items.append(
            _item(
                module_kind="evolving_dna",
                title=f"事件线演化信号：{name}",
                lines=lines,
                summary=next_step or decision or summary or intent,
                status="candidate",
                evidence_level="internal",
                source_type="event_line",
                source_id=str(row["id"]),
                source_label=f"事件线：{name}",
                observed_at=_text(row["updated_at"]) or now,
                source_created_at=_text(row["created_at"]) or None,
                valid_days=60,
                confidence_score=66,
                now=now,
            )
        )
    return items


def _collect_gap_items(db: Database, org_model: Any, now: str) -> list[OrganizationDnaV2ItemRecord]:
    items: list[OrganizationDnaV2ItemRecord] = []
    organization = _get(org_model, "organization")
    org_name = _text(_get(organization, "name")) or "当前组织"
    intro = _get(organization, "introDocument")
    annual_strategy = _text(_get(organization, "annualStrategy"))
    intro_text = _text(_get(intro, "summary")) or _text(_get(intro, "normalizedText"))
    missing: list[str] = []
    if not intro_text:
        missing.append("缺少可复用的组织介绍资料，stable_dna 只能依赖组织模型字段。")
    if not annual_strategy:
        missing.append("缺少年度战略正文，战略类功能只能读取任务和复盘里的演化信号。")
    if missing:
        items.append(
            _item(
                module_kind="gap_dna",
                title="组织稳定画像资料缺口",
                lines=["## 缺口", *[f"- {line}" for line in missing], "## 建议", "先由系统补齐组织介绍和年度战略资料；如果内部没有成文资料，再沉淀一份组织方法说明。"],
                summary="；".join(missing),
                status="candidate",
                evidence_level="weak",
                source_type="system_gap_scan",
                source_id="org_stable_profile_gaps",
                source_label="组织 DNA 缺口扫描",
                observed_at=now,
                valid_days=30,
                confidence_score=58,
                now=now,
            )
        )

    thin_task_count = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM tasks
            WHERE length(trim(COALESCE(description, ''))) < 40
               OR length(trim(COALESCE(next_action, ''))) = 0
            """
        )
    )
    if thin_task_count:
        items.append(
            _item(
                module_kind="gap_dna",
                title="任务背景和下一步信息缺口",
                lines=[
                    f"## 观察\n当前有 {thin_task_count} 个任务缺少足够的背景说明或下一步字段。",
                    "## 影响\n任务与日程功能调用组织 DNA 时，可以知道有任务存在，但难以稳定推断组织方法、交付节奏和协作阻塞。",
                    "## 建议\n优先补齐任务背景、当前阻塞、下一步、关联事件线或项目说明。",
                ],
                summary=f"有 {thin_task_count} 个任务缺少背景或下一步。",
                status="candidate",
                evidence_level="internal",
                source_type="system_gap_scan",
                source_id="thin_task_context",
                source_label="任务资料完整度扫描",
                observed_at=now,
                valid_days=30,
                confidence_score=70,
                now=now,
            )
        )

    event_line_gap_count = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM event_lines
            WHERE length(trim(COALESCE(next_step, ''))) = 0
               OR length(trim(COALESCE(summary, ''))) = 0
            """
        )
    )
    if event_line_gap_count:
        items.append(
            _item(
                module_kind="gap_dna",
                title="事件线说明缺口",
                lines=[
                    f"## 观察\n当前有 {event_line_gap_count} 条事件线缺少摘要或下一步。",
                    "## 影响\n组织 DNA 能捕捉到工作对象，但无法把它稳定转化成组织能力变化或方法沉淀。",
                    "## 建议\n补齐事件线的目标、当前阶段、关键决策、下一步和阻塞。",
                ],
                summary=f"有 {event_line_gap_count} 条事件线缺少摘要或下一步。",
                status="candidate",
                evidence_level="internal",
                source_type="system_gap_scan",
                source_id="event_line_context_gaps",
                source_label="事件线资料完整度扫描",
                observed_at=now,
                valid_days=30,
                confidence_score=68,
                now=now,
            )
        )

    review_count = int(db.scalar("SELECT COUNT(1) AS count FROM weekly_reviews"))
    if review_count == 0:
        items.append(
            _item(
                module_kind="gap_dna",
                title="复盘资料缺口",
                lines=[
                    "## 观察\n系统内还没有周复盘资料。",
                    "## 影响\n组织 DNA 难以从周期性工作反思中提炼组织能力变化、协作阻塞和风险边界。",
                    "## 建议\n开始沉淀每周进展、阻塞、方向和下周重点。",
                ],
                summary="系统内还没有周复盘资料。",
                status="candidate",
                evidence_level="weak",
                source_type="system_gap_scan",
                source_id="weekly_review_absent",
                source_label="复盘资料扫描",
                observed_at=now,
                valid_days=30,
                confidence_score=54,
                now=now,
            )
        )
    return items


def _default_risk_items(now: str) -> list[OrganizationDnaV2ItemRecord]:
    risk_specs = [
        (
            "客户事实不能被组织 DNA 替代",
            "组织 DNA 只能提供益语自身定位、方法和边界，不能替代客户资料、客户 DNA 或客户工作台事实来源。",
        ),
        (
            "内部战略任务不能默认进入公开材料",
            "任务、复盘、事件线里的内部推进口径，只能用于内部建议；生成对外材料时必须降级或过滤。",
        ),
        (
            "弱证据不能升级为正式组织事实",
            "单条任务标题、单次复盘表述、互联网弱来源只能作为候选信号，不能被写成 confirmed 的组织定位。",
        ),
        (
            "数字和成效必须带来源",
            "涉及规模、比例、增长、成效和时间节点时，如果没有 L1/L2 或明确内部来源，应保留为待证据确认。",
        ),
    ]
    items: list[OrganizationDnaV2ItemRecord] = []
    for index, (title, body) in enumerate(risk_specs, start=1):
        items.append(
            _item(
                module_kind="risk_dna",
                title=title,
                lines=["## 边界", body],
                summary=body,
                status="confirmed",
                evidence_level="internal",
                source_type="system_rule",
                source_id=f"organization_dna_risk_rule_{index}",
                source_label="组织 DNA 系统边界规则",
                observed_at=now,
                valid_days=365,
                confidence_score=94,
                now=now,
            )
        )
    return items


def refresh_organization_dna_v2(
    db: Database,
    org_model: Any,
    *,
    run_id: str = "",
    trigger_source: str = "manual",
    event_callback: EventCallback | None = None,
) -> OrganizationDnaV2SnapshotRecord:
    now = _now_iso()
    _emit(event_callback, "info", "开始刷新组织 DNA v2", {"runId": run_id, "triggerSource": trigger_source})
    candidate_items: list[OrganizationDnaV2ItemRecord] = []
    collectors = [
        ("stable", lambda: _collect_org_model_items(org_model, now)),
        ("tasks", lambda: _collect_task_items(db, now)),
        ("reviews", lambda: _collect_review_items(db, now)),
        ("event_lines", lambda: _collect_event_line_items(db, now)),
        ("gaps", lambda: _collect_gap_items(db, org_model, now)),
        ("risks", lambda: _default_risk_items(now)),
    ]
    for name, collector in collectors:
        try:
            items = collector()
            candidate_items.extend(items)
            _emit(event_callback, "info", f"已计算 {name} 组织 DNA 信号", {"count": len(items)})
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            _emit(event_callback, "warning", f"{name} 组织 DNA 信号计算失败", {"error": str(exc)})

    seen_ids: set[str] = set()
    for item in candidate_items:
        _upsert_item(db, item)
        seen_ids.add(item.id)
    stale_count = _mark_stale_missing_items(db, seen_ids, now)
    _emit(
        event_callback,
        "info",
        "组织 DNA v2 写入完成",
        {"processedItems": len(candidate_items), "staleItems": stale_count},
    )
    return get_organization_dna_snapshot(db)


def get_organization_dna_snapshot(db: Database) -> OrganizationDnaV2SnapshotRecord:
    rows = db.fetchall(
        """
        SELECT * FROM organization_dna_v2_items
        WHERE status != 'deprecated'
        ORDER BY updated_at DESC
        """
    )
    items = [_row_to_item(row) for row in rows]
    items.sort(key=lambda item: (_KIND_ORDER.get(item.moduleKind, 99), _STATUS_ORDER.get(item.status, 99), -item.confidenceScore, item.title))
    grouped: dict[str, list[OrganizationDnaV2ItemRecord]] = {
        "stable_dna": [],
        "evolving_dna": [],
        "gap_dna": [],
        "risk_dna": [],
    }
    status_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    updated_at: str | None = None
    for item in items:
        grouped.setdefault(item.moduleKind, []).append(item)
        status_counts[item.status] += 1
        kind_counts[item.moduleKind] += 1
        if not updated_at or item.updatedAt > updated_at:
            updated_at = item.updatedAt

    latest_run_row = db.fetchone(
        """
        SELECT * FROM organization_dna_refresh_runs
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    latest_run = _row_to_run(db, latest_run_row, include_events=True) if latest_run_row else None
    return OrganizationDnaV2SnapshotRecord(
        generatedAt=_now_iso(),
        stableItems=grouped.get("stable_dna", []),
        evolvingItems=grouped.get("evolving_dna", []),
        gapItems=grouped.get("gap_dna", []),
        riskItems=grouped.get("risk_dna", []),
        itemCounts={key: int(value) for key, value in kind_counts.items()},
        confirmedCount=int(status_counts.get("confirmed", 0)),
        candidateCount=int(status_counts.get("candidate", 0)),
        staleCount=int(status_counts.get("stale", 0)),
        latestRun=latest_run,
        updatedAt=updated_at,
    )


def build_organization_dna_tool_context(
    db: Database,
    *,
    purpose: DnaToolPurpose,
    max_chars: int = 12000,
) -> OrganizationDnaToolContextRecord:
    kinds = _PURPOSE_KIND_MAP.get(str(purpose), ["stable_dna", "risk_dna"])
    placeholders = ",".join("?" for _ in kinds)
    rows = db.fetchall(
        f"""
        SELECT * FROM organization_dna_v2_items
        WHERE module_kind IN ({placeholders})
          AND status IN ('confirmed', 'candidate', 'stale')
        ORDER BY module_kind ASC, status ASC, confidence_score DESC, updated_at DESC
        """,
        tuple(kinds),
    )
    items = [_row_to_item(row) for row in rows]
    items.sort(key=lambda item: (kinds.index(item.moduleKind) if item.moduleKind in kinds else 99, _STATUS_ORDER.get(item.status, 99), -item.confidenceScore))
    chunks: list[str] = [f"# 组织 DNA v2 工具上下文", f"用途：{purpose}"]
    source_levels: Counter[str] = Counter()
    observed_times: list[str] = []
    selected_kinds: list[str] = []
    warnings: list[str] = []
    for item in items:
        source_levels[item.evidenceLevel] += 1
        observed_times.append(item.observedAt)
        if item.moduleKind not in selected_kinds:
            selected_kinds.append(item.moduleKind)
        block = (
            f"\n## {item.title}\n"
            f"- 类型：{item.moduleKind}\n"
            f"- 状态：{item.status}\n"
            f"- 来源：{item.sourceLabel}\n"
            f"- 时间：{item.observedAt}\n\n"
            f"{item.contentMarkdown}\n"
        )
        if len("\n".join(chunks)) + len(block) > max_chars:
            warnings.append("组织 DNA 工具上下文已按场景预算截断。")
            break
        chunks.append(block)
    time_scope = ""
    if observed_times:
        time_scope = f"{min(observed_times)} 至 {max(observed_times)}"
    return OrganizationDnaToolContextRecord(
        purpose=purpose,
        selectedKinds=selected_kinds,  # type: ignore[arg-type]
        contextText="\n".join(chunks).strip(),
        sourceLevelSummary={key: int(value) for key, value in source_levels.items()},
        timeScopeSummary=time_scope,
        warnings=warnings,
    )
