from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.services.data_center_access import normalize_department_ids


PRIVATE_VISIBILITY_SCOPES = {"self", "private", "personal"}
PRIVATE_CONTENT_DOMAINS = {"personal", "private"}
INACTIVE_LIFECYCLE_STATUSES = {"deleted", "superseded", "scope_released", "inactive"}
SYNC_EXCLUDED_INGEST_STATUSES = {"skipped_empty", "skipped_missing_client", "error", "private_stored"}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


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


def _json_loads(value: object | None) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return None


def _department_ids(value: object | None) -> list[str]:
    parsed = _json_loads(value)
    return list(normalize_department_ids(parsed if parsed is not None else value))


def _clean_summary(value: object | None, *, limit: int = 1200) -> str:
    text = " ".join(_text(value).split())
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def ensure_data_center_sync_schema(db: Database) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS data_center_sync_outbox (
            id TEXT PRIMARY KEY,
            ingest_event_id TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            document_id TEXT,
            organization_id TEXT NOT NULL DEFAULT '',
            department_ids_json TEXT NOT NULL DEFAULT '[]',
            owner_user_id TEXT NOT NULL DEFAULT '',
            visibility_scope TEXT NOT NULL DEFAULT 'project_public',
            content_domain TEXT NOT NULL DEFAULT 'work',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_type, source_id, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_data_center_sync_outbox_status
            ON data_center_sync_outbox(status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_data_center_sync_outbox_ingest_event
            ON data_center_sync_outbox(ingest_event_id);
        CREATE INDEX IF NOT EXISTS idx_data_center_sync_outbox_scope
            ON data_center_sync_outbox(organization_id, visibility_scope, content_domain, lifecycle_status);
        """
    )
    for column_name, definition in (
        ("ingest_event_id", "TEXT NOT NULL DEFAULT ''"),
        ("source_type", "TEXT NOT NULL DEFAULT ''"),
        ("source_id", "TEXT NOT NULL DEFAULT ''"),
        ("content_hash", "TEXT NOT NULL DEFAULT ''"),
        ("document_id", "TEXT"),
        ("organization_id", "TEXT NOT NULL DEFAULT ''"),
        ("department_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("owner_user_id", "TEXT NOT NULL DEFAULT ''"),
        ("visibility_scope", "TEXT NOT NULL DEFAULT 'project_public'"),
        ("content_domain", "TEXT NOT NULL DEFAULT 'work'"),
        ("lifecycle_status", "TEXT NOT NULL DEFAULT 'active'"),
        ("payload_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("error_message", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ):
        if not db.has_column("data_center_sync_outbox", column_name):
            db.ensure_column("data_center_sync_outbox", column_name, definition)


def _ingest_event_row(db: Database, ingest_event_id: str) -> Any | None:
    return db.fetchone(
        """
        SELECT *
        FROM data_center_ingest_events
        WHERE id = ?
        LIMIT 1
        """,
        (ingest_event_id,),
    )


def _document_row(db: Database, document_id: str) -> Any | None:
    if not document_id:
        return None
    return db.fetchone(
        """
        SELECT
            d.id AS document_id,
            d.client_id AS doc_client_id,
            d.title AS doc_title,
            d.kind AS doc_kind,
            d.source AS doc_source,
            d.excerpt AS doc_excerpt,
            d.canonical_kind AS doc_canonical_kind,
            d.origin_type AS doc_origin_type,
            d.origin_id AS doc_origin_id,
            d.organization_id AS doc_organization_id,
            d.department_id AS doc_department_id,
            d.department_ids_json AS doc_department_ids_json,
            d.owner_user_id AS doc_owner_user_id,
            d.source_entity_type AS doc_source_entity_type,
            d.source_entity_id AS doc_source_entity_id,
            d.visibility_scope AS doc_visibility_scope,
            d.content_domain AS doc_content_domain,
            d.lifecycle_status AS doc_lifecycle_status,
            d.is_searchable AS doc_is_searchable,
            vd.file_name AS v2_file_name,
            vd.kind AS v2_kind,
            vd.visible_category AS v2_visible_category,
            vd.secondary_category AS v2_secondary_category,
            vd.parse_status AS v2_parse_status,
            vd.preview_text AS v2_preview_text,
            vd.doc_index_text AS v2_doc_index_text,
            vd.markdown_content AS v2_markdown_content,
            vd.content_hash AS v2_content_hash,
            vd.canonical_kind AS v2_canonical_kind,
            vd.origin_type AS v2_origin_type,
            vd.origin_id AS v2_origin_id,
            vd.organization_id AS v2_organization_id,
            vd.department_id AS v2_department_id,
            vd.department_ids_json AS v2_department_ids_json,
            vd.owner_user_id AS v2_owner_user_id,
            vd.source_entity_type AS v2_source_entity_type,
            vd.source_entity_id AS v2_source_entity_id,
            vd.visibility_scope AS v2_visibility_scope,
            vd.content_domain AS v2_content_domain,
            vd.lifecycle_status AS v2_lifecycle_status,
            vd.is_searchable AS v2_is_searchable
        FROM documents d
        LEFT JOIN v2_documents vd ON vd.document_id = d.id
        WHERE d.id = ?
        LIMIT 1
        """,
        (document_id,),
    )


def _best_summary(event_row: Any, doc_row: Any | None, *, source_type: str) -> str:
    values: list[object | None] = []
    if doc_row is not None:
        values.extend(
            [
                _row_get(doc_row, "v2_preview_text"),
                _row_get(doc_row, "doc_excerpt"),
                _row_get(doc_row, "v2_doc_index_text"),
            ]
        )
        if source_type != "task_attachment":
            values.append(_row_get(doc_row, "v2_markdown_content"))
    metadata = _json_loads(_row_get(event_row, "metadata_json"))
    if isinstance(metadata, dict):
        values.extend([metadata.get("summary"), metadata.get("preview"), metadata.get("excerpt")])
    for value in values:
        summary = _clean_summary(value)
        if summary:
            return summary
    return ""


def _event_department_ids(row: Any, doc_row: Any | None = None) -> list[str]:
    department_ids = _department_ids(_row_get(row, "department_ids_json"))
    if department_ids:
        return department_ids
    department_id = _text(_row_get(row, "department_id"))
    if department_id:
        return [department_id]
    if doc_row is not None:
        department_ids = _department_ids(_row_get(doc_row, "v2_department_ids_json") or _row_get(doc_row, "doc_department_ids_json"))
        if department_ids:
            return department_ids
        department_id = _text(_row_get(doc_row, "v2_department_id") or _row_get(doc_row, "doc_department_id"))
        if department_id:
            return [department_id]
    return []


def _is_private(row: Any) -> bool:
    scope = _text(_row_get(row, "visibility_scope")).lower()
    domain = _text(_row_get(row, "content_domain")).lower()
    return scope in PRIVATE_VISIBILITY_SCOPES or domain in PRIVATE_CONTENT_DOMAINS


def _base_item_from_event(row: Any, doc_row: Any | None = None) -> dict[str, Any]:
    source_type = _text(_row_get(row, "source_type"))
    department_ids = _event_department_ids(row, doc_row)
    title = _text(_row_get(row, "title"))
    if not title and doc_row is not None:
        title = _text(_row_get(doc_row, "v2_file_name") or _row_get(doc_row, "doc_title"))
    organization_id = _text(_row_get(row, "organization_id"))
    if not organization_id and doc_row is not None:
        organization_id = _text(_row_get(doc_row, "v2_organization_id") or _row_get(doc_row, "doc_organization_id"))
    owner_user_id = _text(_row_get(row, "owner_user_id"))
    if not owner_user_id and doc_row is not None:
        owner_user_id = _text(_row_get(doc_row, "v2_owner_user_id") or _row_get(doc_row, "doc_owner_user_id"))
    visibility_scope = _text(_row_get(row, "visibility_scope")) or "project_public"
    content_domain = _text(_row_get(row, "content_domain")) or "work"
    lifecycle_status = _text(_row_get(row, "lifecycle_status")) or "active"
    document_id = _text(_row_get(row, "document_id"))
    summary = _best_summary(row, doc_row, source_type=source_type)
    return {
        "itemKind": "data_center_item",
        "ingestEventId": _text(_row_get(row, "id")),
        "sourceType": source_type,
        "sourceId": _text(_row_get(row, "source_id")),
        "sourceVersion": _text(_row_get(row, "source_version")),
        "contentHash": _text(_row_get(row, "content_hash")),
        "documentId": document_id,
        "title": title,
        "summary": summary,
        "clientId": _text(_row_get(row, "client_id")),
        "eventLineId": _text(_row_get(row, "event_line_id")),
        "taskId": _text(_row_get(row, "task_id")),
        "meetingId": _text(_row_get(row, "meeting_id")),
        "weekLabel": _text(_row_get(row, "week_label")),
        "organizationId": organization_id,
        "departmentIds": department_ids,
        "departmentIdsJson": to_json(department_ids),
        "ownerUserId": owner_user_id,
        "sourceEntityType": _text(_row_get(row, "source_entity_type")) or source_type,
        "sourceEntityId": _text(_row_get(row, "source_entity_id")) or _text(_row_get(row, "source_id")),
        "visibilityScope": visibility_scope,
        "contentDomain": content_domain,
        "lifecycleStatus": lifecycle_status,
        "document": {
            "title": _text(_row_get(doc_row, "v2_file_name") or _row_get(doc_row, "doc_title")) if doc_row is not None else "",
            "kind": _text(_row_get(doc_row, "v2_kind") or _row_get(doc_row, "doc_kind")) if doc_row is not None else "",
            "source": _text(_row_get(doc_row, "doc_source")) if doc_row is not None else "",
            "canonicalKind": _text(_row_get(doc_row, "v2_canonical_kind") or _row_get(doc_row, "doc_canonical_kind")) if doc_row is not None else "",
            "originType": _text(_row_get(doc_row, "v2_origin_type") or _row_get(doc_row, "doc_origin_type")) if doc_row is not None else "",
            "originId": _text(_row_get(doc_row, "v2_origin_id") or _row_get(doc_row, "doc_origin_id")) if doc_row is not None else "",
            "parseStatus": _text(_row_get(doc_row, "v2_parse_status")) if doc_row is not None else "",
            "visibleCategory": _text(_row_get(doc_row, "v2_visible_category")) if doc_row is not None else "",
            "secondaryCategory": _text(_row_get(doc_row, "v2_secondary_category")) if doc_row is not None else "",
            "hasReadableSummary": bool(summary),
        },
    }


def _sync_exclusion_reason(row: Any, doc_row: Any | None) -> str:
    ingest_status = _text(_row_get(row, "status"))
    if ingest_status in SYNC_EXCLUDED_INGEST_STATUSES:
        return f"ingest_status:{ingest_status}"
    if ingest_status != "ready":
        return f"ingest_status:{ingest_status or 'unknown'}"
    if _is_private(row):
        return "private"
    lifecycle_status = _text(_row_get(row, "lifecycle_status")) or "active"
    if lifecycle_status in INACTIVE_LIFECYCLE_STATUSES:
        return f"lifecycle:{lifecycle_status}"
    if not _text(_row_get(row, "organization_id")):
        return "missing_organization"
    if not _event_department_ids(row, doc_row):
        return "missing_department_scope"
    if not _text(_row_get(row, "owner_user_id")):
        return "missing_owner"
    if not _text(_row_get(row, "document_id")):
        return "missing_document"
    if doc_row is None:
        return "missing_document"
    return ""


def build_data_center_sync_item_from_ingest_event(
    db: Database,
    ingest_event_id: str,
) -> tuple[dict[str, Any] | None, str]:
    row = _ingest_event_row(db, ingest_event_id)
    if row is None:
        return None, "missing_ingest_event"
    doc_row = _document_row(db, _text(_row_get(row, "document_id")))
    reason = _sync_exclusion_reason(row, doc_row)
    if reason:
        return None, reason
    return _base_item_from_event(row, doc_row), ""


def _upsert_outbox_item(
    db: Database,
    item: dict[str, Any],
    *,
    status: str = "pending",
    error_message: str = "",
) -> dict[str, Any]:
    ensure_data_center_sync_schema(db)
    now = _now_iso()
    source_type = _text(item.get("sourceType"))
    source_id = _text(item.get("sourceId"))
    content_hash = _text(item.get("contentHash"))
    department_ids_json = _text(item.get("departmentIdsJson")) or to_json(item.get("departmentIds") or [])
    db.execute(
        """
        INSERT INTO data_center_sync_outbox(
            id, ingest_event_id, source_type, source_id, content_hash, document_id,
            organization_id, department_ids_json, owner_user_id, visibility_scope, content_domain,
            lifecycle_status, payload_json, status, attempts, error_message, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        ON CONFLICT(source_type, source_id, content_hash) DO UPDATE SET
            ingest_event_id = excluded.ingest_event_id,
            document_id = excluded.document_id,
            organization_id = excluded.organization_id,
            department_ids_json = excluded.department_ids_json,
            owner_user_id = excluded.owner_user_id,
            visibility_scope = excluded.visibility_scope,
            content_domain = excluded.content_domain,
            lifecycle_status = excluded.lifecycle_status,
            payload_json = excluded.payload_json,
            status = excluded.status,
            error_message = excluded.error_message,
            updated_at = excluded.updated_at
        """,
        (
            _new_id("dcsync"),
            _text(item.get("ingestEventId")),
            source_type,
            source_id,
            content_hash,
            _text(item.get("documentId")) or None,
            _text(item.get("organizationId")),
            department_ids_json,
            _text(item.get("ownerUserId")),
            _text(item.get("visibilityScope")) or "project_public",
            _text(item.get("contentDomain")) or "work",
            _text(item.get("lifecycleStatus")) or "active",
            to_json(item),
            status,
            error_message,
            now,
            now,
        ),
    )
    row = db.fetchone(
        """
        SELECT id, status
        FROM data_center_sync_outbox
        WHERE source_type = ? AND source_id = ? AND content_hash = ?
        """,
        (source_type, source_id, content_hash),
    )
    return {
        "status": "queued",
        "outboxId": _text(_row_get(row, "id")),
        "outboxStatus": _text(_row_get(row, "status")),
    }


def enqueue_data_center_sync_for_ingest_event(db: Database, ingest_event_id: str) -> dict[str, Any]:
    ensure_data_center_sync_schema(db)
    item, reason = build_data_center_sync_item_from_ingest_event(db, ingest_event_id)
    if not item:
        return {"status": "excluded", "reason": reason}
    return _upsert_outbox_item(db, item)


def _lifecycle_action(lifecycle_status: str) -> str:
    if lifecycle_status == "deleted":
        return "tombstone"
    if lifecycle_status == "scope_released":
        return "scope_release"
    if lifecycle_status == "superseded":
        return "supersede"
    return "inactive"


def build_lifecycle_sync_item_from_ingest_event(
    db: Database,
    ingest_event_id: str,
    *,
    lifecycle_status: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    row = _ingest_event_row(db, ingest_event_id)
    if row is None:
        return None, "missing_ingest_event"
    if _is_private(row):
        return None, "private"
    document_id = _text(_row_get(row, "document_id"))
    doc_row = _document_row(db, document_id)
    item = _base_item_from_event(row, doc_row)
    lifecycle = _text(lifecycle_status) or _text(_row_get(row, "lifecycle_status")) or "inactive"
    if not item.get("organizationId"):
        return None, "missing_organization"
    if not item.get("departmentIds"):
        return None, "missing_department_scope"
    if not item.get("ownerUserId"):
        return None, "missing_owner"
    item["itemKind"] = "data_center_lifecycle"
    item["syncAction"] = _lifecycle_action(lifecycle)
    item["lifecycleStatus"] = lifecycle
    return item, ""


def enqueue_data_center_lifecycle_for_ingest_event(
    db: Database,
    ingest_event_id: str,
    *,
    lifecycle_status: str | None = None,
) -> dict[str, Any]:
    ensure_data_center_sync_schema(db)
    item, reason = build_lifecycle_sync_item_from_ingest_event(
        db,
        ingest_event_id,
        lifecycle_status=lifecycle_status,
    )
    if not item:
        return {"status": "excluded", "reason": reason}
    return _upsert_outbox_item(db, item)


def _preview_record_from_event(row: Any, *, reason: str = "") -> dict[str, Any]:
    return {
        "ingestEventId": _text(_row_get(row, "id")),
        "sourceType": _text(_row_get(row, "source_type")),
        "sourceId": _text(_row_get(row, "source_id")),
        "title": _text(_row_get(row, "title")),
        "status": _text(_row_get(row, "status")),
        "reason": reason,
    }


def _preview_record_from_outbox(row: Any) -> dict[str, Any]:
    payload = from_json(_text(_row_get(row, "payload_json")), {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "outboxId": _text(_row_get(row, "id")),
        "ingestEventId": _text(_row_get(row, "ingest_event_id")),
        "sourceType": _text(_row_get(row, "source_type")),
        "sourceId": _text(_row_get(row, "source_id")),
        "documentId": _text(_row_get(row, "document_id")),
        "title": _text(payload.get("title")),
        "summary": _clean_summary(payload.get("summary"), limit=260),
        "status": _text(_row_get(row, "status")),
        "visibilityScope": _text(_row_get(row, "visibility_scope")),
        "contentDomain": _text(_row_get(row, "content_domain")),
        "lifecycleStatus": _text(_row_get(row, "lifecycle_status")),
        "itemKind": _text(payload.get("itemKind")),
        "syncAction": _text(payload.get("syncAction")),
    }


def build_data_center_sync_preview(db: Database, *, limit: int = 100) -> dict[str, Any]:
    ensure_data_center_sync_schema(db)
    limit = max(1, min(int(limit or 100), 500))
    outbox_rows = db.fetchall(
        """
        SELECT *
        FROM data_center_sync_outbox
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    event_rows = db.fetchall(
        """
        SELECT *
        FROM data_center_ingest_events
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        (limit * 5,),
    )
    existing_keys = {
        (
            _text(_row_get(row, "source_type")),
            _text(_row_get(row, "source_id")),
            _text(_row_get(row, "content_hash")),
        )
        for row in outbox_rows
    }
    uploadable_items: list[dict[str, Any]] = []
    excluded_items: list[dict[str, Any]] = []
    missing_meta_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    lifecycle_items: list[dict[str, Any]] = []
    duplicate_count = 0
    seen_keys: set[tuple[str, str, str]] = set()
    for row in event_rows:
        key = (
            _text(_row_get(row, "source_type")),
            _text(_row_get(row, "source_id")),
            _text(_row_get(row, "content_hash")),
        )
        if key in seen_keys:
            duplicate_count += 1
            continue
        seen_keys.add(key)
        if key in existing_keys:
            continue
        item, reason = build_data_center_sync_item_from_ingest_event(db, _text(_row_get(row, "id")))
        if item:
            uploadable_items.append(
                {
                    "ingestEventId": item["ingestEventId"],
                    "sourceType": item["sourceType"],
                    "sourceId": item["sourceId"],
                    "documentId": item["documentId"],
                    "title": item["title"],
                    "summary": _clean_summary(item.get("summary"), limit=260),
                }
            )
            continue
        record = _preview_record_from_event(row, reason=reason)
        if reason.startswith("missing_"):
            missing_meta_items.append(record)
        elif reason == "private" or reason == "ingest_status:private_stored":
            private_items.append(record)
        elif reason.startswith("lifecycle:"):
            lifecycle_items.append(record)
        else:
            excluded_items.append(record)

    pending_rows = [row for row in outbox_rows if _text(_row_get(row, "status")) == "pending"]
    failed_rows = [row for row in outbox_rows if _text(_row_get(row, "status")) == "error"]
    return {
        "generatedAt": _now_iso(),
        "pendingCount": len(pending_rows),
        "uploadableCount": len(uploadable_items),
        "excludedCount": len(excluded_items),
        "missingMetaCount": len(missing_meta_items),
        "privateCount": len(private_items),
        "lifecycleCount": len(lifecycle_items),
        "duplicateCount": duplicate_count,
        "failedCount": len(failed_rows),
        "items": [_preview_record_from_outbox(row) for row in outbox_rows],
        "uploadableItems": uploadable_items[:limit],
        "excludedItems": excluded_items[:limit],
        "missingMetaItems": missing_meta_items[:limit],
        "privateItems": private_items[:limit],
        "lifecycleItems": lifecycle_items[:limit],
    }
