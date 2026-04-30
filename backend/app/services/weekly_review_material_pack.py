from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.db import Database, from_json
from app.services.data_center_access import (
    DataCenterAccessContext,
    build_document_access_where,
    build_ingest_event_access_where,
    normalize_access_context,
    normalize_department_ids,
)
from app.services.knowledge_v2 import retrieve_knowledge_bundle


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        keys = row.keys()
    except Exception:
        keys = []
    return row[key] if key in keys else default


def _clean(value: object | None, *, limit: int = 1200) -> str:
    cleaned = re.sub(r"\s+", " ", _text(value)).strip()
    return cleaned[:limit]


def _parse_date_only(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _week_bounds(week_label: str) -> tuple[datetime.date, datetime.date] | None:
    match = re.match(r"^(\d{4})-W(\d{2})$", week_label.strip())
    if not match:
        return None
    try:
        start = datetime.fromisocalendar(int(match.group(1)), int(match.group(2)), 1).date()
    except ValueError:
        return None
    return start, start + timedelta(days=6)


def _task_date(row: Any) -> datetime.date | None:
    return _parse_date_only(_text(_row_get(row, "due_date"))) or _parse_date_only(_text(_row_get(row, "created_at")))


def _in_week(row: Any, week_label: str) -> bool:
    bounds = _week_bounds(week_label)
    if not bounds:
        return False
    task_date = _task_date(row)
    if task_date is None:
        return False
    start, end = bounds
    return start <= task_date <= end


def _is_private_visibility(visibility_scope: str, content_domain: str) -> bool:
    return visibility_scope.lower() in {"self", "private", "personal"} or content_domain.lower() in {"personal", "private"}


def _row_visible(
    *,
    context: DataCenterAccessContext,
    organization_id: str,
    owner_user_id: str,
    department_id: str,
    department_ids: tuple[str, ...],
    visibility_scope: str = "project_public",
    content_domain: str = "work",
    lifecycle_status: str = "active",
) -> bool:
    if not context.include_inactive and lifecycle_status and lifecycle_status != "active":
        return False
    if context.organization_id and organization_id != context.organization_id:
        return False
    is_private = _is_private_visibility(visibility_scope, content_domain)
    if is_private:
        return bool(context.include_personal and context.viewer_user_id and owner_user_id == context.viewer_user_id)
    if context.is_ceo:
        return True
    if context.viewer_user_id and owner_user_id == context.viewer_user_id:
        return True
    visible_departments = set(context.department_ids)
    if not visible_departments:
        return False
    candidate_departments = set(department_ids)
    if department_id:
        candidate_departments.add(department_id)
    return bool(candidate_departments & visible_departments)


def _task_visibility(row: Any) -> tuple[str, str]:
    if _text(_row_get(row, "scope_mode")).upper() == "PERSONAL_ONLY":
        return "self", "personal"
    event_visibility = _text(_row_get(row, "event_visibility_scope")) or "project_public"
    if event_visibility.lower() in {"self", "private", "personal"}:
        return "self", "personal"
    return "project_public", "work"


def _task_row_visible(row: Any, context: DataCenterAccessContext) -> bool:
    visibility_scope, content_domain = _task_visibility(row)
    if _is_private_visibility(visibility_scope, content_domain):
        return False
    department_id = _text(_row_get(row, "event_department_id"))
    return _row_visible(
        context=context,
        organization_id=_text(_row_get(row, "organization_id")),
        owner_user_id=_text(_row_get(row, "owner_id") or _row_get(row, "creator_id")),
        department_id=department_id,
        department_ids=normalize_department_ids(department_id),
        visibility_scope=visibility_scope,
        content_domain=content_domain,
        lifecycle_status="active",
    )


def _serialize_review_entry(row: Any, doc_row: Any | None = None) -> dict[str, Any]:
    structured = from_json(_text(_row_get(row, "structured_note_json")), {})
    if not isinstance(structured, dict):
        structured = {}
    snapshot = from_json(_text(_row_get(row, "task_snapshot_json")), {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    return {
        "entryId": _text(_row_get(row, "id")),
        "reviewId": _text(_row_get(row, "review_id")),
        "taskId": _text(_row_get(row, "task_id")),
        "weekLabel": _text(_row_get(row, "week_label")),
        "organizationId": _text(_row_get(row, "organization_id")),
        "contentDomain": _text(_row_get(row, "content_domain")) or "work",
        "note": _clean(_row_get(row, "note"), limit=1600),
        "structuredNote": structured,
        "taskSnapshot": snapshot,
        "reviewedAt": _text(_row_get(row, "reviewed_at")),
        "updatedAt": _text(_row_get(row, "updated_at")),
        "documentId": _text(_row_get(doc_row, "document_id")) if doc_row is not None else "",
        "documentTitle": _text(_row_get(doc_row, "file_name") or _row_get(doc_row, "document_title")) if doc_row is not None else "",
        "documentExcerpt": _clean(_row_get(doc_row, "preview_text") or _row_get(doc_row, "document_excerpt"), limit=900) if doc_row is not None else "",
    }


def _serialize_task(row: Any, review_by_task: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_id = _text(_row_get(row, "id"))
    return {
        "taskId": task_id,
        "organizationId": _text(_row_get(row, "organization_id")),
        "title": _text(_row_get(row, "title")),
        "description": _clean(_row_get(row, "description"), limit=800),
        "status": _text(_row_get(row, "status")),
        "progressStatus": _text(_row_get(row, "progress_status")),
        "clientId": _text(_row_get(row, "client_id") or _row_get(row, "event_client_id")),
        "clientName": _text(_row_get(row, "client_name") or _row_get(row, "event_client_name")),
        "eventLineId": _text(_row_get(row, "event_line_id")),
        "eventLineName": _text(_row_get(row, "event_line_name")),
        "departmentId": _text(_row_get(row, "event_department_id")),
        "ownerUserId": _text(_row_get(row, "owner_id") or _row_get(row, "creator_id")),
        "ownerName": _text(_row_get(row, "owner_name")),
        "dueDate": _text(_row_get(row, "due_date") or _row_get(row, "ddl")),
        "createdAt": _text(_row_get(row, "created_at")),
        "updatedAt": _text(_row_get(row, "updated_at")),
        "reviewEntryId": _text(review_by_task.get(task_id, {}).get("entryId")),
    }


def _serialize_event_line(row: Any) -> dict[str, Any]:
    return {
        "eventLineId": _text(_row_get(row, "id")),
        "organizationId": _text(_row_get(row, "organization_id")),
        "name": _text(_row_get(row, "name")),
        "stage": _text(_row_get(row, "stage")),
        "summary": _clean(_row_get(row, "summary"), limit=700),
        "intent": _clean(_row_get(row, "intent"), limit=500),
        "currentBlocker": _clean(_row_get(row, "current_blocker"), limit=500),
        "recentDecision": _clean(_row_get(row, "recent_decision"), limit=500),
        "nextStep": _clean(_row_get(row, "next_step"), limit=500),
        "clientId": _text(_row_get(row, "primary_client_id")),
        "clientName": _text(_row_get(row, "primary_client_name")),
        "departmentId": _text(_row_get(row, "primary_department_id")),
        "ownerUserId": _text(_row_get(row, "owner_id")),
        "visibilityScope": _text(_row_get(row, "visibility_scope")) or "project_public",
    }


def _serialize_client(row: Any) -> dict[str, Any]:
    return {
        "clientId": _text(_row_get(row, "id")),
        "name": _text(_row_get(row, "name")),
        "alias": _text(_row_get(row, "alias")),
        "domain": _text(_row_get(row, "domain")),
        "type": _text(_row_get(row, "type")),
        "stage": _text(_row_get(row, "stage")),
        "intro": _clean(_row_get(row, "intro"), limit=700),
    }


def _attachment_summary(row: Any) -> str:
    return _clean(
        _row_get(row, "preview_text")
        or _row_get(row, "doc_index_text")
        or _row_get(row, "document_excerpt"),
        limit=900,
    )


def _pack_fingerprint(pack_without_fingerprint: dict[str, Any]) -> str:
    payload = json.dumps(pack_without_fingerprint, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_weekly_review_material_pack(
    *,
    db: Database,
    data_dir: Path | str,
    access_context: DataCenterAccessContext | dict[str, Any] | None,
    week_label: str,
    include_remote_cache: bool = False,
) -> dict[str, Any]:
    del include_remote_cache
    context = normalize_access_context(access_context)

    document_access = build_document_access_where("vd", "d", context)
    review_doc_rows = db.fetchall(
        f"""
        SELECT
            entry.*,
            vd.document_id,
            vd.file_name,
            vd.preview_text,
            vd.updated_at AS document_updated_at,
            d.title AS document_title,
            d.excerpt AS document_excerpt
        FROM v2_documents vd
        JOIN documents d ON d.id = vd.document_id
        JOIN weekly_review_task_entries entry
          ON entry.id = COALESCE(NULLIF(vd.source_entity_id, ''), vd.origin_id)
        WHERE entry.week_label = ?
          AND vd.canonical_kind = 'review_entry_doc'
          AND vd.origin_type = 'weekly_review_entry'
          AND LOWER(COALESCE(entry.content_domain, 'work')) NOT IN ('personal', 'private')
          AND NOT EXISTS (
                SELECT 1
                FROM tasks t
                WHERE t.id = entry.task_id
                  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') = 'PERSONAL_ONLY'
          )
          AND {document_access.sql}
        ORDER BY entry.updated_at DESC
        """,
        (week_label, *document_access.params),
    )

    ingest_access = build_ingest_event_access_where("e", context)
    event_rows = db.fetchall(
        f"""
        SELECT entry.*
        FROM data_center_ingest_events e
        JOIN weekly_review_task_entries entry
          ON entry.id = COALESCE(NULLIF(e.source_entity_id, ''), e.source_id)
        WHERE e.source_type = 'weekly_review_entry'
          AND e.week_label = ?
          AND LOWER(COALESCE(entry.content_domain, 'work')) NOT IN ('personal', 'private')
          AND NOT EXISTS (
                SELECT 1
                FROM tasks t
                WHERE t.id = entry.task_id
                  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') = 'PERSONAL_ONLY'
          )
          AND {ingest_access.sql}
        ORDER BY entry.updated_at DESC
        """,
        (week_label, *ingest_access.params),
    )

    review_entries_by_id: dict[str, dict[str, Any]] = {}
    for row in review_doc_rows:
        entry = _serialize_review_entry(row, row)
        if entry["entryId"]:
            review_entries_by_id[entry["entryId"]] = entry
    for row in event_rows:
        entry_id = _text(_row_get(row, "id"))
        if entry_id and entry_id not in review_entries_by_id:
            review_entries_by_id[entry_id] = _serialize_review_entry(row)
    review_entries = list(review_entries_by_id.values())
    review_by_task = {entry["taskId"]: entry for entry in review_entries if entry.get("taskId")}

    task_rows: list[Any] = []
    task_ids = sorted({entry["taskId"] for entry in review_entries if entry.get("taskId")})
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        task_rows.extend(
            db.fetchall(
                f"""
                SELECT
                    t.*,
                    c.name AS client_name,
                    el.name AS event_line_name,
                    el.primary_client_id AS event_client_id,
                    el.primary_client_name AS event_client_name,
                    el.primary_department_id AS event_department_id,
                    el.visibility_scope AS event_visibility_scope
                FROM tasks t
                LEFT JOIN clients c ON c.id = t.client_id
                LEFT JOIN event_lines el ON el.id = t.event_line_id
                WHERE t.id IN ({placeholders})
                  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
                """,
                tuple(task_ids),
            )
        )

    bounds = _week_bounds(week_label)
    if bounds is not None:
        start, end = bounds
        task_rows.extend(
            db.fetchall(
                """
                SELECT
                    t.*,
                    c.name AS client_name,
                    el.name AS event_line_name,
                    el.primary_client_id AS event_client_id,
                    el.primary_client_name AS event_client_name,
                    el.primary_department_id AS event_department_id,
                    el.visibility_scope AS event_visibility_scope
                FROM tasks t
                LEFT JOIN clients c ON c.id = t.client_id
                LEFT JOIN event_lines el ON el.id = t.event_line_id
                WHERE (date(t.due_date) BETWEEN ? AND ? OR date(t.created_at) BETWEEN ? AND ?)
                  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
                """,
                (str(start), str(end), str(start), str(end)),
            )
        )

    tasks_by_id: dict[str, dict[str, Any]] = {}
    excluded_missing_department_task_ids: list[str] = []
    for row in task_rows:
        task_id = _text(_row_get(row, "id"))
        if not task_id or task_id in tasks_by_id:
            continue
        if not _task_row_visible(row, context):
            if not context.is_ceo and not _text(_row_get(row, "event_department_id")) and task_id not in excluded_missing_department_task_ids:
                excluded_missing_department_task_ids.append(task_id)
            continue
        if task_id not in review_by_task and not _in_week(row, week_label):
            continue
        tasks_by_id[task_id] = _serialize_task(row, review_by_task)
    tasks = list(tasks_by_id.values())

    event_line_ids = sorted({task["eventLineId"] for task in tasks if task.get("eventLineId")})
    event_lines: list[dict[str, Any]] = []
    if event_line_ids:
        placeholders = ",".join("?" for _ in event_line_ids)
        rows = db.fetchall(f"SELECT * FROM event_lines WHERE id IN ({placeholders})", tuple(event_line_ids))
        for row in rows:
            department_id = _text(_row_get(row, "primary_department_id"))
            if not _row_visible(
                context=context,
                organization_id=_text(_row_get(row, "organization_id")),
                owner_user_id=_text(_row_get(row, "owner_id")),
                department_id=department_id,
                department_ids=normalize_department_ids(department_id),
                visibility_scope=_text(_row_get(row, "visibility_scope")) or "project_public",
                content_domain="personal" if (_text(_row_get(row, "visibility_scope")).lower() in {"self", "private", "personal"}) else "work",
                lifecycle_status="active" if _text(_row_get(row, "status")) not in {"deleted", "archived"} else "deleted",
            ):
                continue
            event_lines.append(_serialize_event_line(row))

    client_ids = sorted(
        {
            value
            for value in [
                *(task.get("clientId") for task in tasks),
                *(task.get("clientId") for task in event_lines),
            ]
            if _text(value)
        }
    )
    clients: list[dict[str, Any]] = []
    if client_ids:
        placeholders = ",".join("?" for _ in client_ids)
        clients = [_serialize_client(row) for row in db.fetchall(f"SELECT * FROM clients WHERE id IN ({placeholders})", tuple(client_ids))]

    documents: list[dict[str, Any]] = []
    if client_ids:
        query_parts = [week_label]
        query_parts.extend(task["title"] for task in tasks[:12] if task.get("title"))
        query_parts.extend(entry["note"] for entry in review_entries[:8] if entry.get("note"))
        retrieval_prompt = _clean(" ".join(query_parts), limit=1000) or week_label
        for client_id in client_ids[:6]:
            bundle = retrieve_knowledge_bundle(
                db,
                Path(data_dir),
                client_id,
                retrieval_prompt,
                access_context=context,
            )
            for citation in getattr(bundle, "citations", [])[:5]:
                documents.append(
                    {
                        "clientId": client_id,
                        "title": _clean(getattr(citation, "title", ""), limit=140),
                        "excerpt": _clean(getattr(citation, "excerpt", ""), limit=900),
                        "documentId": _text(getattr(citation, "knowledge_document_id", "")),
                        "canonicalKind": _text(getattr(citation, "canonical_kind", "")),
                        "originType": _text(getattr(citation, "origin_type", "")),
                        "originId": _text(getattr(citation, "origin_id", "")),
                        "score": float(getattr(citation, "score", 0.0) or 0.0),
                    }
                )

    attachments: list[dict[str, Any]] = []
    visible_task_ids = sorted(tasks_by_id.keys())
    if visible_task_ids:
        placeholders = ",".join("?" for _ in visible_task_ids)
        attachment_rows = db.fetchall(
            f"""
            SELECT
                'task_attachments' AS source_table,
                a.id,
                a.task_id,
                a.client_id,
                a.event_line_id,
                a.document_id,
                a.title,
                a.kind,
                a.source,
                a.size_bytes,
                a.created_at,
                d.excerpt AS document_excerpt,
                vd.preview_text,
                vd.doc_index_text,
                vd.content_hash,
                vd.parse_status,
                vd.updated_at AS document_updated_at
            FROM task_attachments a
            LEFT JOIN documents d ON d.id = a.document_id
            LEFT JOIN v2_documents vd ON vd.document_id = a.document_id
            WHERE a.task_id IN ({placeholders})
            UNION ALL
            SELECT
                'task_attachments_cloud' AS source_table,
                a.id,
                a.task_id,
                a.client_id,
                a.event_line_id,
                a.document_id,
                a.title,
                a.kind,
                a.source,
                a.size_bytes,
                a.created_at,
                d.excerpt AS document_excerpt,
                vd.preview_text,
                vd.doc_index_text,
                vd.content_hash,
                vd.parse_status,
                vd.updated_at AS document_updated_at
            FROM task_attachments_cloud a
            LEFT JOIN documents d ON d.id = a.document_id
            LEFT JOIN v2_documents vd ON vd.document_id = a.document_id
            WHERE a.task_id IN ({placeholders})
            """,
            tuple([*visible_task_ids, *visible_task_ids]),
        )
        attachment_doc_ids = sorted({_text(_row_get(row, "document_id")) for row in attachment_rows if _text(_row_get(row, "document_id"))})
        accessible_doc_ids: set[str] = set()
        if attachment_doc_ids:
            doc_placeholders = ",".join("?" for _ in attachment_doc_ids)
            access = build_document_access_where("vd", "d", context)
            for row in db.fetchall(
                f"""
                SELECT DISTINCT vd.document_id
                FROM v2_documents vd
                JOIN documents d ON d.id = vd.document_id
                WHERE vd.document_id IN ({doc_placeholders})
                  AND {access.sql}
                """,
                tuple([*attachment_doc_ids, *access.params]),
            ):
                accessible_doc_ids.add(_text(_row_get(row, "document_id")))
        for row in attachment_rows:
            document_id = _text(_row_get(row, "document_id"))
            can_read_summary = bool(document_id and document_id in accessible_doc_ids)
            task_id = _text(_row_get(row, "task_id"))
            task = tasks_by_id.get(task_id, {})
            attachments.append(
                {
                    "attachmentId": _text(_row_get(row, "id")),
                    "sourceTable": _text(_row_get(row, "source_table")),
                    "taskId": task_id,
                    "taskTitle": _text(task.get("title")),
                    "clientId": _text(_row_get(row, "client_id") or task.get("clientId")),
                    "eventLineId": _text(_row_get(row, "event_line_id") or task.get("eventLineId")),
                    "documentId": document_id,
                    "title": _text(_row_get(row, "title")),
                    "kind": _text(_row_get(row, "kind")),
                    "source": _text(_row_get(row, "source")),
                    "sizeBytes": int(_row_get(row, "size_bytes", 0) or 0),
                    "createdAt": _text(_row_get(row, "created_at")),
                    "documentUpdatedAt": _text(_row_get(row, "document_updated_at")),
                    "contentHash": _text(_row_get(row, "content_hash")) if can_read_summary else "",
                    "parseStatus": _text(_row_get(row, "parse_status")) if can_read_summary else "",
                    "summary": _attachment_summary(row) if can_read_summary else "",
                    "hasReadableSummary": bool(can_read_summary and _attachment_summary(row)),
                }
            )

    missing_meta = {
        "missingOrganizationCount": sum(1 for item in [*tasks, *review_entries] if not _text(item.get("organizationId"))),
        "missingDepartmentCount": sum(1 for item in tasks if not _text(item.get("departmentId"))),
        "missingOwnerCount": sum(1 for item in tasks if not _text(item.get("ownerUserId"))),
        "missingDepartmentTaskIds": [item["taskId"] for item in tasks if not _text(item.get("departmentId"))],
        "excludedMissingDepartmentCount": len(excluded_missing_department_task_ids),
        "excludedMissingDepartmentTaskIds": excluded_missing_department_task_ids,
    }
    source_counts = {
        "reviewEntries": len(review_entries),
        "tasks": len(tasks),
        "eventLines": len(event_lines),
        "clients": len(clients),
        "documents": len(documents),
        "attachments": len(attachments),
        "readableAttachmentSummaries": len([item for item in attachments if item.get("hasReadableSummary")]),
    }
    pack = {
        "weekLabel": week_label,
        "accessMeta": {
            "organizationId": context.organization_id,
            "viewerUserId": context.viewer_user_id,
            "role": context.role,
            "departmentIds": list(context.department_ids),
            "includePersonal": context.include_personal,
            "includeInactive": context.include_inactive,
        },
        "reviewEntries": review_entries,
        "tasks": tasks,
        "eventLines": event_lines,
        "clients": clients,
        "documents": documents,
        "attachments": attachments,
        "sourceCounts": source_counts,
        "missingMeta": missing_meta,
    }
    return {**pack, "packFingerprint": _pack_fingerprint(pack)}
