from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.services.data_center_access import normalize_department_ids
from app.services.knowledge_v2 import upsert_canonical_text_document
from app.services.memory_foundation import (
    record_meeting_publish_writeback,
    record_task_attachment_writeback,
    record_task_writeback,
    record_weekly_review_writeback,
    refresh_event_line_memory_snapshot,
    refresh_organization_notebook_snapshot,
    upsert_memory_fact,
)

logger = logging.getLogger(__name__)


SUPPORTED_SOURCE_TYPES = {
    "task",
    "task_note",
    "task_attachment",
    "meeting",
    "weekly_review",
    "weekly_review_entry",
    "event_line_manual_update",
    # P7（2026-05-18）— 外部抓取信源开闸：资讯情报站采集的所有信源都从这里入
    "external_search_engine",   # 360/Sogou/Bing 等公开搜索引擎 hit
    "external_sentiment",       # 舆情通用占位（不知道具体平台）
    "external_timely",          # 时效情报通用占位
    "wechat_article",           # 搜狗微信公众号文章
    "weibo_post",               # 微博正文（含 site: 二级缓存）
    "xiaohongshu_note",         # 小红书笔记（Playwright 桥接后启用）
    "zhihu_answer",             # 知乎回答 / 文章
    "bilibili_video",           # B 站视频/简介
    "tianyancha_basic",         # 天眼查基础信息
    "tianyancha_risk",          # 天眼查司法/行政处罚（真负面）
    "foundation_registry",      # 基金会中心网 / 民政部公示
    "baijiahao_article",        # 百家号自媒体长文
    "douyin_video",             # 抖音（Playwright 桥接后启用）
    "enterprise_credit",        # 企查查/启信宝（天眼查备用）
}

PRIVATE_VISIBILITY_SCOPES = {"self", "private", "personal"}
PRIVATE_CONTENT_DOMAINS = {"personal", "private"}
SKIPPED_ORPHAN_CLIENT_STATUS = "skipped_orphan_client"

TEXT_DOC_CONFIG: dict[str, dict[str, str]] = {
    "task": {
        "canonical_kind": "task_doc",
        "origin_type": "task",
        "visible_category": "任务资料",
        "secondary_category": "用户任务输入",
    },
    "task_note": {
        "canonical_kind": "task_note_doc",
        "origin_type": "task_note",
        "visible_category": "任务备注",
        "secondary_category": "用户任务输入",
    },
    "meeting": {
        "canonical_kind": "meeting_doc",
        "origin_type": "meeting",
        "visible_category": "会议纪要",
        "secondary_category": "用户会议输入",
    },
    "weekly_review": {
        "canonical_kind": "review_doc",
        "origin_type": "weekly_review",
        "visible_category": "周复盘",
        "secondary_category": "用户复盘输入",
    },
    "weekly_review_entry": {
        "canonical_kind": "review_entry_doc",
        "origin_type": "weekly_review_entry",
        "visible_category": "任务复盘",
        "secondary_category": "用户复盘输入",
    },
    "event_line_manual_update": {
        "canonical_kind": "event_line_update_doc",
        "origin_type": "event_line_manual_update",
        "visible_category": "事件线更新",
        "secondary_category": "用户事件线输入",
    },
}


@dataclass
class DataCenterIngestPayload:
    sourceType: str
    sourceId: str
    title: str = ""
    bodyText: str = ""
    sandboxId: str | None = None
    organizationId: str | None = None
    departmentId: str | None = None
    departmentIds: list[str] | None = None
    ownerUserId: str | None = None
    sourceEntityType: str | None = None
    sourceEntityId: str | None = None
    clientId: str | None = None
    eventLineId: str | None = None
    taskId: str | None = None
    meetingId: str | None = None
    weekLabel: str | None = None
    contentDomain: str = "work"
    visibilityScope: str = "project_public"
    documentId: str | None = None
    sourceVersion: str = ""
    lifecycleStatus: str = "active"
    metadata: dict[str, Any] | None = None


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


def _normalize_body(value: object | None) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _metadata_text(metadata: dict[str, Any] | None, *keys: str) -> str:
    if not isinstance(metadata, dict):
        return ""
    for key in keys:
        value = _text(metadata.get(key))
        if value:
            return value
    return ""


def _metadata_department_ids(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    return list(
        normalize_department_ids(
            metadata.get("departmentIds")
            or metadata.get("department_ids")
            or metadata.get("collaborationDepartmentIds")
            or metadata.get("collaboration_department_ids")
            or metadata.get("primaryDepartmentId")
            or metadata.get("departmentId")
            or metadata.get("department_id")
        )
    )


def _payload_department_ids(payload: DataCenterIngestPayload) -> list[str]:
    return list(normalize_department_ids(payload.departmentIds or payload.departmentId))


def _payload_department_ids_json(payload: DataCenterIngestPayload) -> str:
    return to_json(_payload_department_ids(payload))


def _load_payload(payload: DataCenterIngestPayload | dict[str, Any]) -> DataCenterIngestPayload:
    if isinstance(payload, DataCenterIngestPayload):
        return payload
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return DataCenterIngestPayload(
        sourceType=_text(payload.get("sourceType") or payload.get("source_type")),
        sourceId=_text(payload.get("sourceId") or payload.get("source_id")),
        title=_text(payload.get("title")),
        bodyText=_text(payload.get("bodyText") or payload.get("body_text")),
        sandboxId=_text(payload.get("sandboxId") or payload.get("sandbox_id")) or _metadata_text(metadata, "sandboxId", "sandbox_id") or None,
        organizationId=_text(payload.get("organizationId") or payload.get("organization_id")) or _metadata_text(metadata, "organizationId", "organization_id") or None,
        departmentId=_text(payload.get("departmentId") or payload.get("department_id")) or _metadata_text(metadata, "departmentId", "department_id", "primaryDepartmentId") or None,
        departmentIds=list(
            normalize_department_ids(
                payload.get("departmentIds")
                or payload.get("department_ids")
                or _metadata_department_ids(metadata)
                or payload.get("departmentId")
                or payload.get("department_id")
                or _metadata_text(metadata, "departmentId", "department_id", "primaryDepartmentId")
            )
        ),
        ownerUserId=_text(payload.get("ownerUserId") or payload.get("owner_user_id")) or _metadata_text(metadata, "ownerUserId", "owner_user_id", "ownerId", "userId", "operatorId") or None,
        sourceEntityType=_text(payload.get("sourceEntityType") or payload.get("source_entity_type")) or None,
        sourceEntityId=_text(payload.get("sourceEntityId") or payload.get("source_entity_id")) or None,
        clientId=_text(payload.get("clientId") or payload.get("client_id")) or None,
        eventLineId=_text(payload.get("eventLineId") or payload.get("event_line_id")) or None,
        taskId=_text(payload.get("taskId") or payload.get("task_id")) or None,
        meetingId=_text(payload.get("meetingId") or payload.get("meeting_id")) or None,
        weekLabel=_text(payload.get("weekLabel") or payload.get("week_label")) or None,
        contentDomain=_text(payload.get("contentDomain") or payload.get("content_domain")) or "work",
        visibilityScope=_text(payload.get("visibilityScope") or payload.get("visibility_scope")) or "project_public",
        documentId=_text(payload.get("documentId") or payload.get("document_id")) or None,
        sourceVersion=_text(payload.get("sourceVersion") or payload.get("source_version")),
        lifecycleStatus=_text(payload.get("lifecycleStatus") or payload.get("lifecycle_status")) or "active",
        metadata=metadata,
    )


def _payload_hash(payload: DataCenterIngestPayload) -> str:
    normalized = {
        "sourceType": payload.sourceType,
        "sourceId": payload.sourceId,
        "title": _normalize_body(payload.title),
        "bodyText": _normalize_body(payload.bodyText),
        "documentId": payload.documentId or "",
    }
    return hashlib.sha256(_json_dumps(normalized).encode("utf-8")).hexdigest()


def _is_private(payload: DataCenterIngestPayload) -> bool:
    scope = payload.visibilityScope.strip().lower()
    domain = payload.contentDomain.strip().lower()
    if scope in PRIVATE_VISIBILITY_SCOPES or domain in PRIVATE_CONTENT_DOMAINS:
        return True
    if (payload.metadata or {}).get("personalPrivateNote"):
        return True
    return False


def _payload_private_task_id(payload: DataCenterIngestPayload) -> str:
    if payload.sourceType not in {"task", "task_note", "task_attachment", "weekly_review_entry"}:
        return ""
    return _text(payload.taskId or payload.sourceId or payload.sourceEntityId)


def _task_id_is_private(db: Database, task_id: str) -> bool:
    if not task_id:
        return False
    row = db.fetchone("SELECT scope_mode FROM tasks WHERE id = ?", (task_id,))
    return _text(_row_get(row, "scope_mode")).upper() == "PERSONAL_ONLY"


def _client_exists(db: Database, client_id: str | None) -> bool:
    client_id = _text(client_id)
    if not client_id:
        return False
    return db.fetchone("SELECT id FROM clients WHERE id = ?", (client_id,)) is not None


def _stale_client_id_for_payload(db: Database, payload: DataCenterIngestPayload, *, private: bool) -> str:
    if private:
        return ""
    client_id = _text(payload.clientId)
    if not client_id or _client_exists(db, client_id):
        return ""
    return client_id


def _orphan_client_metadata(payload: DataCenterIngestPayload, stale_client_id: str) -> dict[str, Any]:
    metadata = dict(payload.metadata or {})
    metadata.update(
        {
            "staleClientId": stale_client_id,
            "sourceType": payload.sourceType,
            "sourceId": payload.sourceId,
            "sourceTitle": payload.title,
            "softIsolated": True,
            "softIsolationReason": "stale_client_id",
        }
    )
    return metadata


def _fact_value(payload: DataCenterIngestPayload) -> str:
    title = _text(payload.title) or payload.sourceType
    body = _normalize_body(payload.bodyText)
    if body:
        value = f"{title}：{body}" if title else body
    elif payload.documentId:
        value = f"{title} 已绑定资料 {payload.documentId}"
    else:
        value = title
    return value[:900]


def ensure_data_center_ingest_schema(db: Database) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS data_center_ingest_events (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_version TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL,
            sandbox_id TEXT NOT NULL DEFAULT '',
            organization_id TEXT NOT NULL DEFAULT '',
            department_id TEXT NOT NULL DEFAULT '',
            department_ids_json TEXT NOT NULL DEFAULT '[]',
            owner_user_id TEXT NOT NULL DEFAULT '',
            source_entity_type TEXT NOT NULL DEFAULT '',
            source_entity_id TEXT NOT NULL DEFAULT '',
            client_id TEXT,
            event_line_id TEXT,
            task_id TEXT,
            meeting_id TEXT,
            week_label TEXT,
            title TEXT NOT NULL DEFAULT '',
            visibility_scope TEXT NOT NULL DEFAULT 'project_public',
            content_domain TEXT NOT NULL DEFAULT 'work',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            document_id TEXT,
            status TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_type, source_id, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_source
            ON data_center_ingest_events(source_type, source_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_client
            ON data_center_ingest_events(client_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_scope
            ON data_center_ingest_events(visibility_scope, content_domain, updated_at DESC);
        """
    )
    for column_name, definition in (
        ("organization_id", "TEXT NOT NULL DEFAULT ''"),
        ("sandbox_id", "TEXT NOT NULL DEFAULT ''"),
        ("department_id", "TEXT NOT NULL DEFAULT ''"),
        ("department_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("owner_user_id", "TEXT NOT NULL DEFAULT ''"),
        ("source_entity_type", "TEXT NOT NULL DEFAULT ''"),
        ("source_entity_id", "TEXT NOT NULL DEFAULT ''"),
        ("lifecycle_status", "TEXT NOT NULL DEFAULT 'active'"),
    ):
        if not db.has_column("data_center_ingest_events", column_name):
            db.ensure_column("data_center_ingest_events", column_name, definition)
    rows = db.fetchall(
        """
        SELECT id, department_id
        FROM data_center_ingest_events
        WHERE COALESCE(department_id, '') != ''
          AND COALESCE(department_ids_json, '[]') IN ('', '[]')
        """
    )
    for row in rows:
        db.execute(
            "UPDATE data_center_ingest_events SET department_ids_json = ? WHERE id = ?",
            (to_json([str(row["department_id"])]), str(row["id"])),
        )
    for update_sql in (
        """
        UPDATE data_center_ingest_events
        SET sandbox_id = (
            SELECT clients.sandbox_id
            FROM clients
            WHERE clients.id = data_center_ingest_events.client_id
              AND COALESCE(clients.sandbox_id, '') != ''
            LIMIT 1
        )
        WHERE COALESCE(sandbox_id, '') = ''
          AND COALESCE(client_id, '') != ''
          AND EXISTS (
            SELECT 1 FROM clients
            WHERE clients.id = data_center_ingest_events.client_id
              AND COALESCE(clients.sandbox_id, '') != ''
          )
        """,
        """
        UPDATE data_center_ingest_events
        SET sandbox_id = (
            SELECT tasks.sandbox_id
            FROM tasks
            WHERE tasks.id = data_center_ingest_events.task_id
              AND COALESCE(tasks.sandbox_id, '') != ''
            LIMIT 1
        )
        WHERE COALESCE(sandbox_id, '') = ''
          AND COALESCE(task_id, '') != ''
          AND EXISTS (
            SELECT 1 FROM tasks
            WHERE tasks.id = data_center_ingest_events.task_id
              AND COALESCE(tasks.sandbox_id, '') != ''
          )
        """,
        """
        UPDATE data_center_ingest_events
        SET sandbox_id = (
            SELECT event_lines.sandbox_id
            FROM event_lines
            WHERE event_lines.id = data_center_ingest_events.event_line_id
              AND COALESCE(event_lines.sandbox_id, '') != ''
            LIMIT 1
        )
        WHERE COALESCE(sandbox_id, '') = ''
          AND COALESCE(event_line_id, '') != ''
          AND EXISTS (
            SELECT 1 FROM event_lines
            WHERE event_lines.id = data_center_ingest_events.event_line_id
              AND COALESCE(event_lines.sandbox_id, '') != ''
          )
        """,
        """
        UPDATE data_center_ingest_events
        SET sandbox_id = (
            SELECT c.sandbox_id
            FROM documents d
            JOIN clients c ON c.id = d.client_id
            WHERE d.id = data_center_ingest_events.document_id
              AND COALESCE(c.sandbox_id, '') != ''
            LIMIT 1
        )
        WHERE COALESCE(sandbox_id, '') = ''
          AND COALESCE(document_id, '') != ''
          AND EXISTS (
            SELECT 1
            FROM documents d
            JOIN clients c ON c.id = d.client_id
            WHERE d.id = data_center_ingest_events.document_id
              AND COALESCE(c.sandbox_id, '') != ''
          )
        """,
        """
        UPDATE data_center_ingest_events
        SET sandbox_id = (
            SELECT c.sandbox_id
            FROM meetings m
            JOIN clients c ON c.id = m.client_id
            WHERE m.id = data_center_ingest_events.meeting_id
              AND COALESCE(c.sandbox_id, '') != ''
            LIMIT 1
        )
        WHERE COALESCE(sandbox_id, '') = ''
          AND COALESCE(meeting_id, '') != ''
          AND EXISTS (
            SELECT 1
            FROM meetings m
            JOIN clients c ON c.id = m.client_id
            WHERE m.id = data_center_ingest_events.meeting_id
              AND COALESCE(c.sandbox_id, '') != ''
          )
        """,
    ):
        try:
            db.execute(update_sql)
        except Exception:
            pass
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_lifecycle
        ON data_center_ingest_events(source_type, source_id, lifecycle_status, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_source_entity
        ON data_center_ingest_events(source_entity_type, source_entity_id, lifecycle_status, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_sandbox
        ON data_center_ingest_events(sandbox_id, source_type, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_ingest_events_access_scope
        ON data_center_ingest_events(organization_id, department_id, owner_user_id, lifecycle_status)
        """
    )
    try:
        if not db.has_column("memory_facts", "sandbox_id"):
            db.ensure_column("memory_facts", "sandbox_id", "TEXT NOT NULL DEFAULT ''")
        for update_sql in (
            """
            UPDATE memory_facts
            SET sandbox_id = (
                SELECT clients.sandbox_id
                FROM clients
                WHERE clients.id = memory_facts.scope_id
                  AND COALESCE(clients.sandbox_id, '') != ''
                LIMIT 1
            )
            WHERE COALESCE(memory_facts.sandbox_id, '') = ''
              AND memory_facts.scope_type = 'client'
              AND EXISTS (
                SELECT 1 FROM clients
                WHERE clients.id = memory_facts.scope_id
                  AND COALESCE(clients.sandbox_id, '') != ''
              )
            """,
            """
            UPDATE memory_facts
            SET sandbox_id = (
                SELECT tasks.sandbox_id
                FROM tasks
                WHERE tasks.id = memory_facts.scope_id
                  AND COALESCE(tasks.sandbox_id, '') != ''
                LIMIT 1
            )
            WHERE COALESCE(memory_facts.sandbox_id, '') = ''
              AND memory_facts.scope_type = 'task'
              AND EXISTS (
                SELECT 1 FROM tasks
                WHERE tasks.id = memory_facts.scope_id
                  AND COALESCE(tasks.sandbox_id, '') != ''
              )
            """,
            """
            UPDATE memory_facts
            SET sandbox_id = (
                SELECT event_lines.sandbox_id
                FROM event_lines
                WHERE event_lines.id = memory_facts.scope_id
                  AND COALESCE(event_lines.sandbox_id, '') != ''
                LIMIT 1
            )
            WHERE COALESCE(memory_facts.sandbox_id, '') = ''
              AND memory_facts.scope_type = 'event_line'
              AND EXISTS (
                SELECT 1 FROM event_lines
                WHERE event_lines.id = memory_facts.scope_id
                  AND COALESCE(event_lines.sandbox_id, '') != ''
              )
            """,
        ):
            db.execute(update_sql)
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_facts_sandbox_scope
            ON memory_facts(sandbox_id, scope_type, scope_id, updated_at DESC)
            """
        )
    except Exception:
        pass


def _resolve_payload_sandbox_id(
    db: Database,
    payload: DataCenterIngestPayload,
    *,
    document_id: str | None = None,
) -> str:
    def _first(query: str, params: tuple[object, ...]) -> str:
        try:
            row = db.fetchone(query, params)
        except Exception:
            return ""
        return _text(_row_get(row, "sandbox_id"))

    explicit_sandbox_id = _text(payload.sandboxId)
    if explicit_sandbox_id:
        if _first("SELECT id AS sandbox_id FROM sandboxes WHERE id = ? LIMIT 1", (explicit_sandbox_id,)):
            return explicit_sandbox_id

    for value, query in (
        (
            payload.clientId,
            "SELECT sandbox_id FROM clients WHERE id = ? AND COALESCE(sandbox_id, '') != '' LIMIT 1",
        ),
        (
            payload.taskId,
            "SELECT sandbox_id FROM tasks WHERE id = ? AND COALESCE(sandbox_id, '') != '' LIMIT 1",
        ),
        (
            payload.eventLineId,
            "SELECT sandbox_id FROM event_lines WHERE id = ? AND COALESCE(sandbox_id, '') != '' LIMIT 1",
        ),
    ):
        normalized = _text(value)
        if normalized:
            sandbox_id = _first(query, (normalized,))
            if sandbox_id:
                return sandbox_id

    normalized_document_id = _text(document_id or payload.documentId)
    if normalized_document_id:
        sandbox_id = _first(
            """
            SELECT c.sandbox_id
            FROM documents d
            JOIN clients c ON c.id = d.client_id
            WHERE d.id = ?
              AND COALESCE(c.sandbox_id, '') != ''
            LIMIT 1
            """,
            (normalized_document_id,),
        )
        if sandbox_id:
            return sandbox_id

    normalized_meeting_id = _text(payload.meetingId)
    if normalized_meeting_id:
        sandbox_id = _first(
            """
            SELECT c.sandbox_id
            FROM meetings m
            JOIN clients c ON c.id = m.client_id
            WHERE m.id = ?
              AND COALESCE(c.sandbox_id, '') != ''
            LIMIT 1
            """,
            (normalized_meeting_id,),
        )
        if sandbox_id:
            return sandbox_id

    return ""


def _upsert_ingest_event(
    db: Database,
    payload: DataCenterIngestPayload,
    *,
    content_hash: str,
    status: str,
    document_id: str | None,
    error_message: str = "",
) -> str:
    ensure_data_center_ingest_schema(db)
    now = _now_iso()
    event_id = _new_id("dcing")
    sandbox_id = _resolve_payload_sandbox_id(db, payload, document_id=document_id)
    db.execute(
        """
        INSERT INTO data_center_ingest_events(
            id, source_type, source_id, source_version, content_hash,
            sandbox_id, organization_id, department_id, department_ids_json, owner_user_id, source_entity_type, source_entity_id,
            client_id, event_line_id, task_id, meeting_id, week_label, title,
            visibility_scope, content_domain, lifecycle_status, document_id, status, error_message,
            metadata_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, source_id, content_hash) DO UPDATE SET
            source_version = excluded.source_version,
            sandbox_id = excluded.sandbox_id,
            organization_id = excluded.organization_id,
            department_id = excluded.department_id,
            department_ids_json = excluded.department_ids_json,
            owner_user_id = excluded.owner_user_id,
            source_entity_type = excluded.source_entity_type,
            source_entity_id = excluded.source_entity_id,
            client_id = excluded.client_id,
            event_line_id = excluded.event_line_id,
            task_id = excluded.task_id,
            meeting_id = excluded.meeting_id,
            week_label = excluded.week_label,
            title = excluded.title,
            visibility_scope = excluded.visibility_scope,
            content_domain = excluded.content_domain,
            lifecycle_status = excluded.lifecycle_status,
            document_id = excluded.document_id,
            status = excluded.status,
            error_message = excluded.error_message,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            event_id,
            payload.sourceType,
            payload.sourceId,
            payload.sourceVersion or "",
            content_hash,
            sandbox_id,
            payload.organizationId or "",
            payload.departmentId or "",
            _payload_department_ids_json(payload),
            payload.ownerUserId or "",
            payload.sourceEntityType or payload.sourceType,
            payload.sourceEntityId or payload.sourceId,
            payload.clientId,
            payload.eventLineId,
            payload.taskId,
            payload.meetingId,
            payload.weekLabel,
            payload.title,
            payload.visibilityScope or "project_public",
            payload.contentDomain or "work",
            payload.lifecycleStatus or "active",
            document_id,
            status,
            error_message,
            to_json(payload.metadata or {}),
            now,
            now,
        ),
    )
    row = db.fetchone(
        """
        SELECT id
        FROM data_center_ingest_events
        WHERE source_type = ? AND source_id = ? AND content_hash = ?
        """,
        (payload.sourceType, payload.sourceId, content_hash),
    )
    return str(row["id"]) if row else event_id


def _write_memory_facts(
    db: Database,
    payload: DataCenterIngestPayload,
    *,
    content_hash: str,
    document_id: str | None,
    private: bool,
) -> int:
    value = _fact_value(payload)
    if not value:
        return 0
    source_id = f"{payload.sourceId}:{content_hash[:12]}"
    fact_key = f"data_center_ingest:{payload.sourceType}:{payload.sourceId}"
    evidence_refs = [f"{payload.sourceType}:{payload.sourceId}"]
    if document_id:
        evidence_refs.append(f"document:{document_id}")

    scopes: list[tuple[str, str]] = []
    if private:
        metadata = payload.metadata or {}
        person_id = _text(metadata.get("userId") or metadata.get("operatorId") or metadata.get("actorId")) or "self"
        scopes.append(("person", person_id))
        if payload.taskId:
            scopes.append(("task", payload.taskId))
    else:
        if payload.taskId:
            scopes.append(("task", payload.taskId))
        if payload.clientId:
            scopes.append(("client", payload.clientId))
        if payload.eventLineId:
            scopes.append(("event_line", payload.eventLineId))

    written = 0
    seen: set[tuple[str, str]] = set()
    for scope_type, scope_id in scopes:
        if not scope_id or (scope_type, scope_id) in seen:
            continue
        seen.add((scope_type, scope_id))
        upsert_memory_fact(
            db,
            scope_type=scope_type,
            scope_id=scope_id,
            fact_key=fact_key,
            fact_value=value,
            source_type=payload.sourceType,
            source_id=source_id,
            confidence=0.82 if payload.sourceType != "task_attachment" else 0.9,
            freshness=1.0,
            evidence_refs=evidence_refs,
        )
        db.execute(
            """
            UPDATE memory_facts
            SET sandbox_id = ?, organization_id = ?, department_id = ?, owner_user_id = ?,
                source_entity_type = ?, source_entity_id = ?,
                visibility_scope = ?, content_domain = ?, lifecycle_status = ?,
                department_ids_json = ?
            WHERE scope_type = ? AND scope_id = ? AND fact_key = ? AND source_type = ? AND source_id = ?
            """,
            (
                _resolve_payload_sandbox_id(db, payload, document_id=document_id),
                payload.organizationId or "",
                payload.departmentId or "",
                payload.ownerUserId or "",
                payload.sourceEntityType or payload.sourceType,
                payload.sourceEntityId or payload.sourceId,
                payload.visibilityScope or "project_public",
                payload.contentDomain or "work",
                payload.lifecycleStatus or "active",
                _payload_department_ids_json(payload),
                scope_type,
                scope_id,
                fact_key,
                payload.sourceType,
                source_id,
            ),
        )
        written += 1
    return written


def _upsert_text_document_if_needed(
    db: Database,
    data_dir: Path,
    payload: DataCenterIngestPayload,
    *,
    private: bool,
    content_hash: str,
) -> str | None:
    if payload.sourceType == "task_attachment":
        _bind_existing_document_metadata(db, payload, private=private)
        return payload.documentId
    if private:
        _mark_documents_for_source_entity(
            db,
            source_entity_type=payload.sourceEntityType or payload.sourceType,
            source_entity_id=payload.sourceEntityId or payload.sourceId,
            lifecycle_status="scope_released",
        )
        return payload.documentId
    body = _text(payload.bodyText)
    if not body or not payload.clientId:
        return payload.documentId
    config = TEXT_DOC_CONFIG.get(payload.sourceType)
    if not config:
        return payload.documentId
    now = _now_iso()
    source_entity_type = payload.sourceEntityType or payload.sourceType
    source_entity_id = payload.sourceEntityId or payload.sourceId
    origin_id = payload.sourceId
    if payload.sourceType == "weekly_review_entry":
        _mark_documents_for_source_entity(
            db,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            lifecycle_status="superseded",
        )
        origin_id = f"{payload.sourceId}:{content_hash[:12]}"
    result = upsert_canonical_text_document(
        db,
        data_dir=data_dir,
        client_id=payload.clientId,
        canonical_kind=config["canonical_kind"],
        origin_type=config["origin_type"],
        origin_id=origin_id,
        title=payload.title or payload.sourceType,
        text=body,
        visible_category=config["visible_category"],
        secondary_category=config["secondary_category"],
        created_at=now,
        updated_at=now,
        organization_id=payload.organizationId or "",
        department_id=payload.departmentId or "",
        department_ids=_payload_department_ids(payload),
        owner_user_id=payload.ownerUserId or "",
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        visibility_scope=payload.visibilityScope or "project_public",
        content_domain=payload.contentDomain or "work",
        lifecycle_status=payload.lifecycleStatus or "active",
    )
    if not result:
        return payload.documentId
    return _text(result.get("documentId")) or payload.documentId


def _bind_existing_document_metadata(db: Database, payload: DataCenterIngestPayload, *, private: bool) -> None:
    if not payload.documentId:
        return
    lifecycle_status = payload.lifecycleStatus or "active"
    visibility_scope = payload.visibilityScope or "project_public"
    content_domain = payload.contentDomain or "work"
    is_searchable = 0 if private or lifecycle_status != "active" else 1
    for table_name, id_column in (("documents", "id"), ("v2_documents", "document_id")):
        db.execute(
            f"""
            UPDATE {table_name}
            SET organization_id = ?, department_id = ?, owner_user_id = ?,
                source_entity_type = ?, source_entity_id = ?,
                visibility_scope = ?, content_domain = ?, lifecycle_status = ?, is_searchable = ?,
                department_ids_json = ?
            WHERE {id_column} = ?
            """,
            (
                payload.organizationId or "",
                payload.departmentId or "",
                payload.ownerUserId or "",
                payload.sourceEntityType or payload.sourceType,
                payload.sourceEntityId or payload.sourceId,
                visibility_scope,
                content_domain,
                lifecycle_status,
                is_searchable,
                _payload_department_ids_json(payload),
                payload.documentId,
            ),
        )


def _refresh_related_snapshots(db: Database, payload: DataCenterIngestPayload, *, private: bool) -> None:
    if private:
        return
    if payload.clientId:
        try:
            refresh_organization_notebook_snapshot(db, payload.clientId)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("refresh organization notebook after ingest failed: %s", exc)
    if payload.eventLineId:
        try:
            refresh_event_line_memory_snapshot(db, payload.eventLineId)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("refresh event line memory after ingest failed: %s", exc)


def _mark_documents_for_source_entity(
    db: Database,
    *,
    source_entity_type: str,
    source_entity_id: str,
    lifecycle_status: str,
    superseded_by_event_id: str = "",
) -> None:
    source_entity_type = _text(source_entity_type)
    source_entity_id = _text(source_entity_id)
    lifecycle_status = _text(lifecycle_status) or "inactive"
    if not source_entity_type or not source_entity_id:
        return
    now = _now_iso()
    is_searchable = 1 if lifecycle_status == "active" else 0
    db.execute(
        """
        UPDATE documents
        SET lifecycle_status = ?, is_searchable = ?
        WHERE source_entity_type = ? AND source_entity_id = ?
        """,
        (lifecycle_status, is_searchable, source_entity_type, source_entity_id),
    )
    db.execute(
        """
        UPDATE v2_documents
        SET lifecycle_status = ?, is_searchable = ?, updated_at = ?
        WHERE source_entity_type = ? AND source_entity_id = ?
        """,
        (lifecycle_status, is_searchable, now, source_entity_type, source_entity_id),
    )
    db.execute(
        """
        UPDATE memory_facts
        SET lifecycle_status = ?, valid_to = COALESCE(NULLIF(valid_to, ''), ?), superseded_by_event_id = ?
        WHERE source_entity_type = ? AND source_entity_id = ?
        """,
        (lifecycle_status, now, superseded_by_event_id, source_entity_type, source_entity_id),
    )
    ensure_data_center_ingest_schema(db)
    db.execute(
        """
        UPDATE data_center_ingest_events
        SET lifecycle_status = ?, updated_at = ?
        WHERE source_entity_type = ? AND source_entity_id = ?
        """,
        (lifecycle_status, now, source_entity_type, source_entity_id),
    )
    if lifecycle_status != "active":
        try:
            from app.services.data_center_sync import enqueue_data_center_lifecycle_for_ingest_event

            rows = db.fetchall(
                """
                SELECT id
                FROM data_center_ingest_events
                WHERE source_entity_type = ? AND source_entity_id = ?
                """,
                (source_entity_type, source_entity_id),
            )
            for row in rows:
                enqueue_data_center_lifecycle_for_ingest_event(
                    db,
                    str(row["id"]),
                    lifecycle_status=lifecycle_status,
                )
        except Exception as exc:  # pragma: no cover - sync queue must not block lifecycle changes
            logger.warning("data center lifecycle sync enqueue failed: %s", exc)


def mark_ingested_source_inactive(
    db: Database,
    *,
    source_type: str | None = None,
    source_id: str | None = None,
    task_id: str | None = None,
    lifecycle_status: str = "inactive",
) -> None:
    ensure_data_center_ingest_schema(db)
    lifecycle_status = _text(lifecycle_status) or "inactive"
    now = _now_iso()
    event_filters: list[str] = []
    params: list[Any] = []
    if source_type and source_id:
        event_filters.append("(source_type = ? AND source_id = ?)")
        params.extend([source_type, source_id])
    if task_id:
        event_filters.append("task_id = ?")
        params.append(task_id)
    if not event_filters:
        return
    rows = db.fetchall(
        f"""
        SELECT source_type, source_id, source_entity_type, source_entity_id, document_id
        FROM data_center_ingest_events
        WHERE {' OR '.join(event_filters)}
        """,
        tuple(params),
    )
    for row in rows:
        _mark_documents_for_source_entity(
            db,
            source_entity_type=_text(row["source_entity_type"]) or _text(row["source_type"]),
            source_entity_id=_text(row["source_entity_id"]) or _text(row["source_id"]),
            lifecycle_status=lifecycle_status,
        )
        document_id = _text(row["document_id"])
        if document_id:
            db.execute(
                "UPDATE documents SET lifecycle_status = ?, is_searchable = 0 WHERE id = ?",
                (lifecycle_status, document_id),
            )
            db.execute(
                "UPDATE v2_documents SET lifecycle_status = ?, is_searchable = 0, updated_at = ? WHERE document_id = ?",
                (lifecycle_status, now, document_id),
            )
    if source_type and source_id:
        db.execute(
            """
            UPDATE memory_facts
            SET lifecycle_status = ?, valid_to = COALESCE(NULLIF(valid_to, ''), ?)
            WHERE source_type = ? AND (source_id = ? OR source_id LIKE ?)
            """,
            (lifecycle_status, now, source_type, source_id, f"{source_id}:%"),
        )
        db.execute(
            """
            UPDATE v2_documents
            SET lifecycle_status = ?, is_searchable = 0, updated_at = ?
            WHERE origin_type = ? AND (origin_id = ? OR origin_id LIKE ?)
            """,
            (lifecycle_status, now, source_type, source_id, f"{source_id}:%"),
        )
        db.execute(
            """
            UPDATE documents
            SET lifecycle_status = ?, is_searchable = 0
            WHERE origin_type = ? AND (origin_id = ? OR origin_id LIKE ?)
            """,
            (lifecycle_status, source_type, source_id, f"{source_id}:%"),
        )
        db.execute(
            """
            UPDATE data_center_ingest_events
            SET lifecycle_status = ?, updated_at = ?
            WHERE source_type = ? AND source_id = ?
            """,
            (lifecycle_status, now, source_type, source_id),
        )
        if lifecycle_status != "active":
            try:
                from app.services.data_center_sync import enqueue_data_center_lifecycle_for_ingest_event

                rows = db.fetchall(
                    """
                    SELECT id
                    FROM data_center_ingest_events
                    WHERE source_type = ? AND source_id = ?
                    """,
                    (source_type, source_id),
                )
                for row in rows:
                    enqueue_data_center_lifecycle_for_ingest_event(
                        db,
                        str(row["id"]),
                    lifecycle_status=lifecycle_status,
                )
            except Exception as exc:  # pragma: no cover - sync queue must not block lifecycle changes
                logger.warning("data center lifecycle sync enqueue failed: %s", exc)


def _soft_isolate_ingested_source(
    db: Database,
    *,
    source_type: str,
    source_id: str,
    source_entity_type: str = "",
    source_entity_id: str = "",
    document_id: str | None = None,
    lifecycle_status: str = "scope_released",
) -> None:
    source_type = _text(source_type)
    source_id = _text(source_id)
    source_entity_type = _text(source_entity_type) or source_type
    source_entity_id = _text(source_entity_id) or source_id
    if source_entity_type and source_entity_id:
        _mark_documents_for_source_entity(
            db,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            lifecycle_status=lifecycle_status,
        )
    if source_type and source_id:
        mark_ingested_source_inactive(
            db,
            source_type=source_type,
            source_id=source_id,
            lifecycle_status=lifecycle_status,
        )
    document_id = _text(document_id)
    if document_id:
        now = _now_iso()
        db.execute(
            "UPDATE documents SET lifecycle_status = ?, is_searchable = 0 WHERE id = ?",
            (lifecycle_status, document_id),
        )
        db.execute(
            "UPDATE v2_documents SET lifecycle_status = ?, is_searchable = 0, updated_at = ? WHERE document_id = ?",
            (lifecycle_status, now, document_id),
        )


def _skip_orphan_client_ingest(
    db: Database,
    payload: DataCenterIngestPayload,
    *,
    stale_client_id: str,
    content_hash: str,
) -> dict[str, Any]:
    payload.metadata = _orphan_client_metadata(payload, stale_client_id)
    payload.lifecycleStatus = "scope_released"
    _soft_isolate_ingested_source(
        db,
        source_type=payload.sourceType,
        source_id=payload.sourceId,
        source_entity_type=payload.sourceEntityType or payload.sourceType,
        source_entity_id=payload.sourceEntityId or payload.sourceId,
        document_id=payload.documentId,
        lifecycle_status="scope_released",
    )
    error_message = f"stale_client_id:{stale_client_id}"
    event_id = _upsert_ingest_event(
        db,
        payload,
        content_hash=content_hash,
        status=SKIPPED_ORPHAN_CLIENT_STATUS,
        document_id=payload.documentId,
        error_message=error_message,
    )
    return {
        "ingestEventId": event_id,
        "status": SKIPPED_ORPHAN_CLIENT_STATUS,
        "documentId": payload.documentId,
        "memoryFactCount": 0,
        "contentHash": content_hash,
        "errorMessage": error_message,
    }


def _result_is_orphan_client_skip(result: dict[str, Any] | None) -> bool:
    return isinstance(result, dict) and _text(result.get("status")) == SKIPPED_ORPHAN_CLIENT_STATUS


def _orphan_ingest_event_rows(db: Database, *, limit: int | None = None) -> list[Any]:
    ensure_data_center_ingest_schema(db)
    limit_clause = ""
    params: tuple[Any, ...] = ()
    if limit is not None:
        limit_clause = "LIMIT ?"
        params = (max(1, int(limit)),)
    return db.fetchall(
        f"""
        SELECT e.*
        FROM data_center_ingest_events e
        LEFT JOIN clients c ON c.id = e.client_id
        WHERE COALESCE(e.client_id, '') != ''
          AND c.id IS NULL
        ORDER BY e.updated_at DESC, e.created_at DESC
        {limit_clause}
        """,
        params,
    )


def _merge_orphan_ingest_event_metadata(row: Any) -> dict[str, Any]:
    metadata = from_json(str(_row_get(row, "metadata_json") or "{}"), {})
    if not isinstance(metadata, dict):
        metadata = {}
    stale_client_id = _text(_row_get(row, "client_id"))
    metadata.update(
        {
            "staleClientId": stale_client_id,
            "sourceType": _text(_row_get(row, "source_type")),
            "sourceId": _text(_row_get(row, "source_id")),
            "sourceTitle": _text(_row_get(row, "title")),
            "softIsolated": True,
            "softIsolationReason": "stale_client_id",
        }
    )
    return metadata


def _repair_orphan_ingest_event_row(db: Database, row: Any) -> bool:
    status = _text(_row_get(row, "status"))
    if status == SKIPPED_ORPHAN_CLIENT_STATUS:
        return False
    stale_client_id = _text(_row_get(row, "client_id"))
    if not stale_client_id:
        return False
    _soft_isolate_ingested_source(
        db,
        source_type=_text(_row_get(row, "source_type")),
        source_id=_text(_row_get(row, "source_id")),
        source_entity_type=_text(_row_get(row, "source_entity_type")),
        source_entity_id=_text(_row_get(row, "source_entity_id")),
        document_id=_text(_row_get(row, "document_id")) or None,
        lifecycle_status="scope_released",
    )
    db.execute(
        """
        UPDATE data_center_ingest_events
        SET status = ?,
            error_message = ?,
            lifecycle_status = 'scope_released',
            metadata_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            SKIPPED_ORPHAN_CLIENT_STATUS,
            f"stale_client_id:{stale_client_id}",
            to_json(_merge_orphan_ingest_event_metadata(row)),
            _now_iso(),
            _text(_row_get(row, "id")),
        ),
    )
    return True


def build_orphan_client_ingest_repair_report(
    db: Database,
    *,
    apply: bool = False,
    sample_limit: int = 20,
) -> dict[str, Any]:
    ensure_data_center_ingest_schema(db)
    sample_limit = max(1, min(int(sample_limit or 20), 200))
    orphan_task_rows = db.fetchall(
        """
        SELECT t.id, t.title, t.client_id, t.status, t.updated_at
        FROM tasks t
        LEFT JOIN clients c ON c.id = t.client_id
        WHERE COALESCE(t.client_id, '') != ''
          AND c.id IS NULL
        ORDER BY t.updated_at DESC
        LIMIT ?
        """,
        (sample_limit,),
    )
    orphan_event_line_rows = db.fetchall(
        """
        SELECT e.id, e.name, e.primary_client_id, e.primary_client_name, e.status, e.updated_at
        FROM event_lines e
        LEFT JOIN clients c ON c.id = e.primary_client_id
        WHERE COALESCE(e.primary_client_id, '') != ''
          AND c.id IS NULL
        ORDER BY e.updated_at DESC
        LIMIT ?
        """,
        (sample_limit,),
    )
    orphan_ingest_rows = _orphan_ingest_event_rows(db)
    fk_error_rows = [
        row
        for row in orphan_ingest_rows
        if "FOREIGN KEY" in _text(_row_get(row, "error_message")).upper()
    ]
    already_skipped_count = sum(
        1 for row in orphan_ingest_rows if _text(_row_get(row, "status")) == SKIPPED_ORPHAN_CLIENT_STATUS
    )
    repaired_count = 0
    if apply:
        for row in orphan_ingest_rows:
            if _repair_orphan_ingest_event_row(db, row):
                repaired_count += 1
        orphan_ingest_rows = _orphan_ingest_event_rows(db)
        fk_error_rows = [
            row
            for row in orphan_ingest_rows
            if "FOREIGN KEY" in _text(_row_get(row, "error_message")).upper()
        ]
        already_skipped_count = sum(
            1 for row in orphan_ingest_rows if _text(_row_get(row, "status")) == SKIPPED_ORPHAN_CLIENT_STATUS
        )

    def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows[:sample_limit]]

    return {
        "applied": bool(apply),
        "orphanTaskCount": int(
            db.scalar(
                """
                SELECT COUNT(1)
                FROM tasks t
                LEFT JOIN clients c ON c.id = t.client_id
                WHERE COALESCE(t.client_id, '') != ''
                  AND c.id IS NULL
                """
            )
            or 0
        ),
        "orphanEventLineCount": int(
            db.scalar(
                """
                SELECT COUNT(1)
                FROM event_lines e
                LEFT JOIN clients c ON c.id = e.primary_client_id
                WHERE COALESCE(e.primary_client_id, '') != ''
                  AND c.id IS NULL
                """
            )
            or 0
        ),
        "orphanIngestEventCount": len(orphan_ingest_rows),
        "fkErrorIngestEventCount": len(fk_error_rows),
        "alreadySkippedOrphanClientIngestCount": already_skipped_count,
        "repairedIngestEventCount": repaired_count,
        "orphanTaskSamples": _rows_to_dicts(orphan_task_rows),
        "orphanEventLineSamples": _rows_to_dicts(orphan_event_line_rows),
        "orphanIngestEventSamples": _rows_to_dicts(orphan_ingest_rows[:sample_limit]),
    }


def ingest_user_input(
    db: Database,
    data_dir: Path | str,
    payload: DataCenterIngestPayload | dict[str, Any],
) -> dict[str, Any]:
    loaded = _load_payload(payload)
    if loaded.sourceType not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"unsupported DataCenterIngest sourceType: {loaded.sourceType}")
    if not loaded.sourceId:
        loaded.sourceId = (
            loaded.taskId
            or loaded.meetingId
            or loaded.documentId
            or _text((loaded.metadata or {}).get("id"))
            or "unknown"
        )

    ensure_data_center_ingest_schema(db)
    if _task_id_is_private(db, _payload_private_task_id(loaded)):
        return {
            "ingestEventId": None,
            "status": "skipped_private_task",
            "documentId": loaded.documentId,
            "memoryFactCount": 0,
            "contentHash": "",
            "errorMessage": "",
        }
    content_hash = _payload_hash(loaded)
    private = _is_private(loaded)
    has_content = bool(_text(loaded.bodyText) or loaded.documentId)
    stale_client_id = _stale_client_id_for_payload(db, loaded, private=private)
    if has_content and stale_client_id:
        return _skip_orphan_client_ingest(
            db,
            loaded,
            stale_client_id=stale_client_id,
            content_hash=content_hash,
        )
    status = "private_stored" if private else "ready"
    document_id = loaded.documentId
    memory_fact_count = 0
    error_message = ""

    if not has_content:
        status = "skipped_empty"
        event_id = _upsert_ingest_event(
            db,
            loaded,
            content_hash=content_hash,
            status=status,
            document_id=document_id,
        )
        return {
            "ingestEventId": event_id,
            "status": status,
            "documentId": document_id,
            "memoryFactCount": 0,
            "contentHash": content_hash,
            "errorMessage": "",
        }

    try:
        document_id = _upsert_text_document_if_needed(db, Path(data_dir), loaded, private=private, content_hash=content_hash)
        memory_fact_count = _write_memory_facts(
            db,
            loaded,
            content_hash=content_hash,
            document_id=document_id,
            private=private,
        )
        _refresh_related_snapshots(db, loaded, private=private)
    except Exception as exc:
        logger.exception("DataCenterIngest failed for %s/%s", loaded.sourceType, loaded.sourceId)
        status = "error"
        error_message = str(exc)

    event_id = _upsert_ingest_event(
        db,
        loaded,
        content_hash=content_hash,
        status=status,
        document_id=document_id,
        error_message=error_message,
    )
    if status == "ready":
        try:
            from app.services.data_center_sync import enqueue_data_center_sync_for_ingest_event

            enqueue_data_center_sync_for_ingest_event(db, event_id)
        except Exception as exc:  # pragma: no cover - sync queue must not block local ingest
            logger.warning("data center sync enqueue failed: %s", exc)
    return {
        "ingestEventId": event_id,
        "status": status,
        "documentId": document_id,
        "memoryFactCount": memory_fact_count,
        "contentHash": content_hash,
        "errorMessage": error_message,
    }


def _task_row(db: Database, task_id: str) -> Any | None:
    return db.fetchone(
        """
        SELECT
            t.*,
            COALESCE(t.client_id, el.primary_client_id) AS resolved_client_id,
            COALESCE(c.name, el.primary_client_name) AS resolved_client_name,
            el.name AS resolved_event_line_name,
            el.primary_department_id AS resolved_department_id,
            el.visibility_scope AS resolved_event_line_visibility_scope
        FROM tasks t
        LEFT JOIN event_lines el ON el.id = t.event_line_id
        LEFT JOIN clients c ON c.id = COALESCE(t.client_id, el.primary_client_id)
        WHERE t.id = ?
        """,
        (task_id,),
    )


def _task_visibility(row: Any | None) -> tuple[str, str]:
    scope_mode = _text(_row_get(row, "scope_mode")).upper()
    if scope_mode == "PERSONAL_ONLY":
        return "personal", "self"
    event_visibility = _text(_row_get(row, "resolved_event_line_visibility_scope")).lower()
    if event_visibility in PRIVATE_VISIBILITY_SCOPES:
        return "personal", "self"
    return "work", "project_public"


def _task_row_is_private(row: Any | None) -> bool:
    return _text(_row_get(row, "scope_mode")).upper() == "PERSONAL_ONLY"


# ──────────────────────────────────────────────────────────────────────────
# P7（2026-05-18）外部抓取信源入库 helper
# ──────────────────────────────────────────────────────────────────────────


def ingest_external_observation(
    db: Database,
    *,
    source_type: str,
    source_url: str,
    title: str,
    body_text: str,
    client_id: str | None = None,
    project_module_id: str | None = None,
    captured_at: str | None = None,
    published_at: str | None = None,
    sentiment_label: str | None = None,
    intent_kind: str | None = None,
    query_text: str | None = None,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """把资讯情报站抓回的一条 hit 写入 data_center_ingest_events。

    复用现有 ingest 基础设施：
      - hash 去重（content_hash UNIQUE）
      - 客户绑定（client_id 字段）
      - 多源对比 / 澄清流程在此基础上 build_proposal_drafts

    Args:
        source_type: SUPPORTED_SOURCE_TYPES 中的某个外部值（如 'external_sentiment'）。
        source_url: 抓到的页面 URL，作为 sourceId 保证去重。
        title, body_text: 标题和正文（snippet 或全文）。
        client_id, project_module_id: 关联到哪个客户/业务线。
        captured_at, published_at: 抓取时间 / 原始发布时间。
        sentiment_label: 'negative' / 'neutral' / 'positive' / None。
        intent_kind: 'evaluation' / 'policy' / 'funding' / ... 业务意图分类。
        query_text: 触发这条 hit 的搜索 query（用于回溯）。
        metadata_extra: 其他需要保留的元数据（直接 merge 进 metadata_json）。

    Returns: 同 ingest_user_input 的 result，含 ingestEventId / status 等。
    """
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"external source_type not allowed: {source_type}")

    url = (source_url or "").strip()
    if not url:
        raise ValueError("source_url required")

    metadata: dict[str, Any] = {
        "ingestKind": "external_observation",
        "sourceUrl": url,
        "capturedAt": captured_at or _now_iso(),
    }
    if published_at:
        metadata["publishedAt"] = published_at
    if sentiment_label:
        metadata["sentimentLabel"] = sentiment_label
    if intent_kind:
        metadata["intentKind"] = intent_kind
    if query_text:
        metadata["queryText"] = query_text
    if metadata_extra:
        metadata.update(metadata_extra)

    # P9 证据等级：根据 source_type 自动判定，保证下游消费者可隔离
    # external_observation 严格禁止用作客户事实（fill_table_evaluator 必须过滤）
    AUTHORITATIVE_SOURCES = {
        "tianyancha_basic", "tianyancha_risk",
        "foundation_registry", "enterprise_credit",
    }
    evidence_tier = (
        "third_party_authoritative" if source_type in AUTHORITATIVE_SOURCES
        else "external_observation"
    )
    metadata["evidenceTier"] = evidence_tier

    payload = DataCenterIngestPayload(
        sourceType=source_type,
        sourceId=url,                              # URL 作为 sourceId，天然去重
        title=(title or "").strip()[:300],
        bodyText=(body_text or "").strip(),
        clientId=client_id or None,
        sourceEntityType="project_module" if project_module_id else ("client" if client_id else ""),
        sourceEntityId=project_module_id or client_id or "",
        # 外部抓取默认 work 域、project_public 可见——任何团队成员可见
        contentDomain="work",
        visibilityScope="project_public",
        metadata=metadata,
    )

    result = ingest_user_input(db, "", payload)

    # 落库后强制设 evidence_tier 字段（payload 走 metadata 不影响主字段）
    ingest_event_id = result.get("ingestEventId") if isinstance(result, dict) else None
    if ingest_event_id:
        try:
            db.execute(
                "UPDATE data_center_ingest_events SET evidence_tier = ? WHERE id = ?",
                (evidence_tier, ingest_event_id),
            )
        except Exception:  # noqa: BLE001
            pass  # 字段不存在时静默忽略（旧 DB 兜底）
    return result


def purge_private_task_ingest_events(db: Database) -> int:
    ensure_data_center_ingest_schema(db)
    task_rows = db.fetchall(
        """
        SELECT id
        FROM tasks
        WHERE COALESCE(scope_mode, 'COLLAB_SHARED') = 'PERSONAL_ONLY'
        """
    )
    task_ids = [_text(row["id"]) for row in task_rows if _text(row["id"])]
    if not task_ids:
        return 0
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.fetchall(
        f"""
        SELECT id
        FROM data_center_ingest_events
        WHERE task_id IN ({placeholders})
           OR source_id IN ({placeholders})
           OR source_entity_id IN ({placeholders})
        """,
        (*task_ids, *task_ids, *task_ids),
    )
    event_ids = [_text(row["id"]) for row in rows if _text(row["id"])]
    if not event_ids:
        return 0
    event_placeholders = ",".join("?" for _ in event_ids)
    db.execute(
        f"DELETE FROM data_center_ingest_events WHERE id IN ({event_placeholders})",
        tuple(event_ids),
    )
    return len(event_ids)


def _task_payload_base(row: Any) -> dict[str, Any]:
    content_domain, visibility_scope = _task_visibility(row)
    organization_id = _text(_row_get(row, "organization_id"))
    department_id = _text(_row_get(row, "primary_department_id") or _row_get(row, "resolved_department_id"))
    owner_user_id = _text(_row_get(row, "owner_id") or _row_get(row, "creator_id"))
    task_id = _text(_row_get(row, "id"))
    return {
        "organizationId": organization_id or None,
        "departmentId": department_id or None,
        "departmentIds": [department_id] if department_id else [],
        "ownerUserId": owner_user_id or None,
        "sourceEntityType": "task",
        "sourceEntityId": task_id or None,
        "clientId": _text(_row_get(row, "resolved_client_id") or _row_get(row, "client_id")) or None,
        "eventLineId": _text(_row_get(row, "event_line_id")) or None,
        "taskId": task_id or None,
        "contentDomain": content_domain,
        "visibilityScope": visibility_scope,
        "metadata": {
            "organizationId": organization_id,
            "departmentId": department_id,
            "departmentIds": [department_id] if department_id else [],
            "ownerUserId": owner_user_id,
            "status": _text(_row_get(row, "status")),
            "progressStatus": _text(_row_get(row, "progress_status")),
            "priority": _text(_row_get(row, "priority")),
            "scopeMode": _text(_row_get(row, "scope_mode")),
            "ownerName": _text(_row_get(row, "owner_name")),
            "dueDate": _text(_row_get(row, "due_date") or _row_get(row, "ddl")),
            "eventLineName": _text(_row_get(row, "resolved_event_line_name")),
            "clientName": _text(_row_get(row, "resolved_client_name")),
        },
    }


def _task_note_text(db: Database, task_id: str) -> str:
    note_row = db.fetchone(
        """
        SELECT note FROM task_notes WHERE task_id = ?
        UNION ALL
        SELECT note FROM task_notes_cloud WHERE task_id = ?
        LIMIT 1
        """,
        (task_id, task_id),
    )
    return _text(_row_get(note_row, "note"))


def _render_task_body(row: Any, note_text: str = "") -> str:
    parts = [
        ("标题", _row_get(row, "title")),
        ("描述", _row_get(row, "description")),
        ("备注", note_text),
        ("状态", _row_get(row, "status")),
        ("进展状态", _row_get(row, "progress_status")),
        ("负责人", _row_get(row, "owner_name")),
        ("截止时间", _row_get(row, "due_date") or _row_get(row, "ddl")),
        ("当前阻塞", _row_get(row, "current_blocker")),
        ("下一步", _row_get(row, "next_action")),
        ("最近决策", _row_get(row, "recent_decision")),
    ]
    return "\n".join(f"{label}：{_text(value)}" for label, value in parts if _text(value))


def ingest_task_by_id(db: Database, data_dir: Path | str, task_id: str) -> dict[str, Any] | None:
    row = _task_row(db, task_id)
    if not row:
        return None
    if _task_row_is_private(row):
        return None
    note_text = _task_note_text(db, task_id)
    payload = {
        "sourceType": "task",
        "sourceId": task_id,
        "title": _text(_row_get(row, "title")),
        "bodyText": _render_task_body(row, note_text),
        "sourceVersion": _text(_row_get(row, "updated_at")),
        **_task_payload_base(row),
    }
    result = ingest_user_input(db, data_dir, payload)
    if _result_is_orphan_client_skip(result):
        return result
    try:
        if not _is_private(_load_payload(payload)):
            record_task_writeback(
                db,
                task_id=task_id,
                title=_text(_row_get(row, "title")),
                description=_text(_row_get(row, "description")),
                status=_text(_row_get(row, "status")),
                due_date=_text(_row_get(row, "due_date") or _row_get(row, "ddl")) or None,
                client_id=payload["clientId"],
                event_line_id=payload["eventLineId"],
            )
    except Exception as exc:  # pragma: no cover - compatibility writeback should not block ingest
        logger.warning("legacy task writeback failed after DataCenterIngest: %s", exc)
    return result


def ingest_task_note_by_id(
    db: Database,
    data_dir: Path | str,
    task_id: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    row = _task_row(db, task_id)
    if _task_row_is_private(row):
        return None
    if note is None:
        note_row = db.fetchone(
            """
            SELECT note, updated_at FROM task_notes WHERE task_id = ?
            UNION ALL
            SELECT note, updated_at FROM task_notes_cloud WHERE task_id = ?
            LIMIT 1
            """,
            (task_id, task_id),
        )
        note = _text(_row_get(note_row, "note"))
        source_version = _text(_row_get(note_row, "updated_at"))
    else:
        source_version = _now_iso()
    if not row and not note:
        return None
    title = _text(_row_get(row, "title")) if row else f"任务 {task_id}"
    base = _task_payload_base(row) if row else {"taskId": task_id, "metadata": {}}
    payload = {
        "sourceType": "task_note",
        "sourceId": task_id,
        "title": f"{title} 备注",
        "bodyText": _text(note),
        "sourceVersion": source_version,
        **base,
        "sourceEntityType": "task_note",
        "sourceEntityId": task_id,
    }
    result = ingest_user_input(db, data_dir, payload)
    if _result_is_orphan_client_skip(result):
        return result
    if row:
        ingest_task_by_id(db, data_dir, task_id)
    return result


def ingest_task_attachment_by_id(
    db: Database,
    data_dir: Path | str,
    attachment_id: str,
) -> dict[str, Any] | None:
    row = db.fetchone(
        """
        SELECT id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at
        FROM task_attachments
        WHERE id = ?
        UNION ALL
        SELECT id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at
        FROM task_attachments_cloud
        WHERE id = ?
        LIMIT 1
        """,
        (attachment_id, attachment_id),
    )
    if not row:
        return None
    task = _task_row(db, _text(_row_get(row, "task_id")))
    if _task_row_is_private(task):
        return None
    content_domain, visibility_scope = _task_visibility(task)
    title = _text(_row_get(row, "title")) or "任务附件"
    body = f"任务附件：{title}\n文件类型：{_text(_row_get(row, 'kind'))}\n文件路径：{_text(_row_get(row, 'path'))}"
    department_id = _text(_row_get(task, "primary_department_id") or _row_get(task, "resolved_department_id"))
    payload = {
        "sourceType": "task_attachment",
        "sourceId": attachment_id,
        "title": title,
        "bodyText": body,
        "organizationId": _text(_row_get(task, "organization_id")) or None,
        "departmentId": department_id or None,
        "departmentIds": [department_id] if department_id else [],
        "ownerUserId": _text(_row_get(task, "owner_id") or _row_get(task, "creator_id")) or None,
        "sourceEntityType": "task_attachment",
        "sourceEntityId": attachment_id,
        "clientId": _text(_row_get(row, "client_id")) or _text(_row_get(task, "resolved_client_id")) or None,
        "eventLineId": _text(_row_get(row, "event_line_id")) or _text(_row_get(task, "event_line_id")) or None,
        "taskId": _text(_row_get(row, "task_id")) or None,
        "contentDomain": content_domain,
        "visibilityScope": visibility_scope,
        "documentId": _text(_row_get(row, "document_id")) or None,
        "sourceVersion": _text(_row_get(row, "created_at")),
        "metadata": {
            "path": _text(_row_get(row, "path")),
            "kind": _text(_row_get(row, "kind")),
            "source": _text(_row_get(row, "source")),
            "sizeBytes": _row_get(row, "size_bytes", 0),
        },
    }
    result = ingest_user_input(db, data_dir, payload)
    if _result_is_orphan_client_skip(result):
        return result
    try:
        if payload["clientId"] and not _is_private(_load_payload(payload)):
            record_task_attachment_writeback(
                db,
                task_id=_text(payload["taskId"]),
                client_id=_text(payload["clientId"]),
                event_line_id=_text(payload["eventLineId"]) or None,
                attachment_title=title,
                attachment_path=_text(_row_get(row, "path")),
            )
    except Exception as exc:  # pragma: no cover - compatibility writeback should not block ingest
        logger.warning("legacy task attachment writeback failed after DataCenterIngest: %s", exc)
    return result


def _render_meeting_body(db: Database, meeting_id: str, row: Any) -> str:
    source_rows = db.fetchall(
        "SELECT title, content_text FROM meeting_sources WHERE meeting_id = ? ORDER BY created_at ASC",
        (meeting_id,),
    )
    decision_rows = db.fetchall("SELECT summary FROM decisions WHERE meeting_id = ? ORDER BY created_at ASC", (meeting_id,))
    action_rows = db.fetchall(
        "SELECT title, owner_name, due_date FROM action_items WHERE meeting_id = ? ORDER BY created_at ASC",
        (meeting_id,),
    )
    risk_rows = db.fetchall("SELECT summary, severity FROM risks WHERE meeting_id = ? ORDER BY created_at ASC", (meeting_id,))
    parts = [
        f"会议标题：{_text(_row_get(row, 'title'))}",
        f"会议阶段：{_text(_row_get(row, 'stage'))}",
        f"会议时间：{_text(_row_get(row, 'scheduled_at'))}",
        f"纪要：{_text(_row_get(row, 'notes'))}",
        f"转写：{_text(_row_get(row, 'transcript_text'))}",
    ]
    for source in source_rows:
        parts.append(f"补充材料：{_text(_row_get(source, 'title'))} {_text(_row_get(source, 'content_text'))}")
    for index, decision in enumerate(decision_rows, start=1):
        parts.append(f"决议{index}：{_text(_row_get(decision, 'summary'))}")
    for index, action in enumerate(action_rows, start=1):
        parts.append(
            f"行动项{index}：{_text(_row_get(action, 'title'))}"
            f"｜负责人：{_text(_row_get(action, 'owner_name'))}"
            f"｜截止：{_text(_row_get(action, 'due_date'))}"
        )
    for index, risk in enumerate(risk_rows, start=1):
        parts.append(f"风险{index}：{_text(_row_get(risk, 'summary'))}｜等级：{_text(_row_get(risk, 'severity'))}")
    return "\n".join(part for part in parts if _normalize_body(part).split("：", 1)[-1])


def ingest_meeting_by_id(db: Database, data_dir: Path | str, meeting_id: str) -> dict[str, Any] | None:
    row = db.fetchone("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    if not row:
        return None
    payload = {
        "sourceType": "meeting",
        "sourceId": meeting_id,
        "title": _text(_row_get(row, "title")) or "会议记录",
        "bodyText": _render_meeting_body(db, meeting_id, row),
        "organizationId": _text(_row_get(row, "organization_id")) or None,
        "ownerUserId": _text(_row_get(row, "owner_id") or _row_get(row, "created_by")) or None,
        "sourceEntityType": "meeting",
        "sourceEntityId": meeting_id,
        "clientId": _text(_row_get(row, "client_id")) or None,
        "meetingId": meeting_id,
        "contentDomain": "work",
        "visibilityScope": "project_public",
        "sourceVersion": _text(_row_get(row, "updated_at")),
        "metadata": {
            "stage": _text(_row_get(row, "stage")),
            "scheduledAt": _text(_row_get(row, "scheduled_at")),
        },
    }
    result = ingest_user_input(db, data_dir, payload)
    if _result_is_orphan_client_skip(result):
        return result
    try:
        event_line_rows = db.fetchall(
            """
            SELECT DISTINCT event_line_id
            FROM event_line_activities
            WHERE source_type = 'meeting' AND source_id = ? AND event_line_id IS NOT NULL
            """,
            (meeting_id,),
        )
        event_line_ids = [_text(row["event_line_id"]) for row in event_line_rows if _text(row["event_line_id"])]
        if payload["clientId"]:
            record_meeting_publish_writeback(
                db,
                client_id=_text(payload["clientId"]),
                meeting_id=meeting_id,
                meeting_title=_text(payload["title"]),
                event_line_ids=event_line_ids,
            )
    except Exception as exc:  # pragma: no cover - compatibility writeback should not block ingest
        logger.warning("legacy meeting writeback failed after DataCenterIngest: %s", exc)
    return result


def _render_weekly_review_body(row: Any) -> str:
    parts = [
        ("本周总结", _row_get(row, "summary")),
        ("工作进展", _row_get(row, "work_progress")),
        ("工作阻塞", _row_get(row, "work_blocker")),
        ("下周方向", _row_get(row, "work_direction")),
        ("下周重点", _row_get(row, "next_week_focus")),
        ("需要支持", _row_get(row, "support_needed")),
        ("自由记录", _row_get(row, "work_free_note")),
    ]
    return "\n".join(f"{label}：{_text(value)}" for label, value in parts if _text(value))


def _render_private_weekly_review_body(row: Any) -> str:
    parts = [
        ("个人成长", _row_get(row, "personal_growth_note")),
        ("私人记录", _row_get(row, "personal_private_note")),
    ]
    return "\n".join(f"{label}：{_text(value)}" for label, value in parts if _text(value))


def _render_weekly_entry_body(row: Any, snapshot: dict[str, Any]) -> str:
    structured = from_json(_row_get(row, "structured_note_json"), {})
    if not isinstance(structured, dict):
        structured = {}
    parts = [
        ("任务", snapshot.get("title")),
        ("复盘", _row_get(row, "note")),
        ("本周进展", structured.get("progress") or structured.get("reflection")),
        ("下一步", structured.get("nextAction") or structured.get("next_action")),
        ("经验", structured.get("successExperience") or structured.get("success_experience")),
    ]
    return "\n".join(f"{label}：{_text(value)}" for label, value in parts if _text(value))


def _ingest_weekly_review_entry(db: Database, data_dir: Path | str, row: Any) -> dict[str, Any] | None:
    snapshot = from_json(_row_get(row, "task_snapshot_json"), {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    task_id = _text(_row_get(row, "task_id"))
    task = _task_row(db, task_id)
    if _task_row_is_private(task):
        return None
    content_domain = _text(_row_get(row, "content_domain")) or "work"
    visibility_scope = "self" if content_domain.lower() in PRIVATE_CONTENT_DOMAINS else "project_public"
    client_id = _text(snapshot.get("clientId")) or _text(_row_get(task, "resolved_client_id") if task else "")
    event_line_id = _text(snapshot.get("eventLineId")) or _text(_row_get(task, "event_line_id") if task else "")
    department_id = _text(snapshot.get("departmentId")) or _text(_row_get(task, "primary_department_id") if task else "") or _text(_row_get(task, "resolved_department_id") if task else "")
    owner_user_id = _text(snapshot.get("ownerId")) or _text(_row_get(task, "owner_id") if task else "") or _text(_row_get(row, "user_id"))
    title = _text(snapshot.get("title")) or _text(_row_get(task, "title") if task else "") or f"任务 {task_id} 复盘"
    payload = {
        "sourceType": "weekly_review_entry",
        "sourceId": _text(_row_get(row, "id")) or f"{_text(_row_get(row, 'review_id'))}:{task_id}",
        "title": f"{title} 复盘",
        "bodyText": _render_weekly_entry_body(row, snapshot),
        "organizationId": _text(_row_get(row, "organization_id")) or _text(_row_get(task, "organization_id") if task else "") or None,
        "departmentId": department_id or None,
        "departmentIds": [department_id] if department_id else [],
        "ownerUserId": owner_user_id or None,
        "sourceEntityType": "weekly_review_entry",
        "sourceEntityId": _text(_row_get(row, "id")) or f"{_text(_row_get(row, 'review_id'))}:{task_id}",
        "clientId": client_id or None,
        "eventLineId": event_line_id or None,
        "taskId": task_id or None,
        "weekLabel": _text(_row_get(row, "week_label")) or None,
        "contentDomain": content_domain,
        "visibilityScope": visibility_scope,
        "sourceVersion": _text(_row_get(row, "updated_at")),
        "metadata": {
            "reviewId": _text(_row_get(row, "review_id")),
            "userId": _text(_row_get(row, "user_id")),
            "organizationId": _text(_row_get(row, "organization_id")),
            "departmentIds": [department_id] if department_id else [],
            "taskSnapshot": snapshot,
        },
    }
    return ingest_user_input(db, data_dir, payload)


def ingest_weekly_review_by_id(
    db: Database,
    data_dir: Path | str,
    review_id: str,
    *,
    include_entries: bool = True,
) -> dict[str, Any] | None:
    row = db.fetchone("SELECT * FROM weekly_reviews WHERE id = ?", (review_id,))
    if not row:
        return None
    result = ingest_user_input(
        db,
        data_dir,
        {
            "sourceType": "weekly_review",
            "sourceId": review_id,
            "title": f"{_text(_row_get(row, 'week_label'))} 周复盘",
            "bodyText": _render_weekly_review_body(row),
            "sandboxId": _text(_row_get(row, "sandbox_id")) or None,
            "organizationId": _text(_row_get(row, "organization_id")) or None,
            "ownerUserId": _text(_row_get(row, "user_id") or _row_get(row, "operator_id")) or None,
            "sourceEntityType": "weekly_review",
            "sourceEntityId": review_id,
            "weekLabel": _text(_row_get(row, "week_label")) or None,
            "contentDomain": "work",
            "visibilityScope": "company",
            "sourceVersion": _text(_row_get(row, "updated_at")),
            "metadata": {
                "organizationId": _text(_row_get(row, "organization_id")),
                "sandboxId": _text(_row_get(row, "sandbox_id")),
                "operatorId": _text(_row_get(row, "operator_id")),
                "userId": _text(_row_get(row, "user_id")),
            },
        },
    )
    private_body = _render_private_weekly_review_body(row)
    if private_body:
        ingest_user_input(
            db,
            data_dir,
            {
                "sourceType": "weekly_review",
                "sourceId": f"{review_id}:personal_private",
                "title": f"{_text(_row_get(row, 'week_label'))} 个人复盘",
                "bodyText": private_body,
                "sandboxId": _text(_row_get(row, "sandbox_id")) or None,
                "organizationId": _text(_row_get(row, "organization_id")) or None,
                "ownerUserId": _text(_row_get(row, "user_id") or _row_get(row, "operator_id")) or None,
                "sourceEntityType": "weekly_review",
                "sourceEntityId": f"{review_id}:personal_private",
                "weekLabel": _text(_row_get(row, "week_label")) or None,
                "contentDomain": "personal",
                "visibilityScope": "self",
                "sourceVersion": _text(_row_get(row, "updated_at")),
                "metadata": {
                    "organizationId": _text(_row_get(row, "organization_id")),
                    "sandboxId": _text(_row_get(row, "sandbox_id")),
                    "operatorId": _text(_row_get(row, "operator_id")),
                    "userId": _text(_row_get(row, "user_id")),
                    "personalPrivateNote": bool(_text(_row_get(row, "personal_private_note"))),
                },
            },
        )
    if include_entries:
        rows = db.fetchall(
            "SELECT * FROM weekly_review_task_entries WHERE review_id = ? ORDER BY updated_at ASC",
            (review_id,),
        )
        for entry in rows:
            _ingest_weekly_review_entry(db, data_dir, entry)
    try:
        record_weekly_review_writeback(db, review_id=review_id)
    except Exception as exc:  # pragma: no cover - compatibility writeback should not block ingest
        logger.warning("legacy weekly review writeback failed after DataCenterIngest: %s", exc)
    return result


def backfill_weekly_review_ingest(
    db: Database,
    data_dir: Path | str,
    *,
    week_label: str | None = None,
    review_id: str | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    where: list[str] = []
    params: list[object] = []
    if review_id:
        where.append("id = ?")
        params.append(review_id)
    if week_label:
        where.append("week_label = ?")
        params.append(week_label)
    sql = "SELECT id FROM weekly_reviews"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    succeeded = 0
    failed = 0
    for row in rows:
        try:
            result = ingest_weekly_review_by_id(db, data_dir, _text(_row_get(row, "id")))
            if result is None:
                failed += 1
            else:
                succeeded += 1
        except Exception as exc:
            failed += 1
            logger.warning("weekly review ingest backfill failed: %s", exc)
    return {"scanned": len(rows), "succeeded": succeeded, "failed": failed}


def _render_event_line_body(row: Any) -> str:
    parts = [
        ("事件线", _row_get(row, "name")),
        ("阶段", _row_get(row, "stage")),
        ("摘要", _row_get(row, "summary")),
        ("意图", _row_get(row, "intent")),
        ("当前阻塞", _row_get(row, "current_blocker")),
        ("最近决策", _row_get(row, "recent_decision")),
        ("下一步", _row_get(row, "next_step")),
    ]
    return "\n".join(f"{label}：{_text(value)}" for label, value in parts if _text(value))


def ingest_event_line_by_id(db: Database, data_dir: Path | str, event_line_id: str) -> dict[str, Any] | None:
    row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
    if not row:
        return None
    visibility_scope = _text(_row_get(row, "visibility_scope")) or "project_public"
    content_domain = "personal" if visibility_scope.lower() in PRIVATE_VISIBILITY_SCOPES else "work"
    department_id = _text(_row_get(row, "primary_department_id"))
    payload = {
        "sourceType": "event_line_manual_update",
        "sourceId": event_line_id,
        "title": _text(_row_get(row, "name")) or "事件线更新",
        "bodyText": _render_event_line_body(row),
        "organizationId": _text(_row_get(row, "organization_id")) or None,
        "departmentId": department_id or None,
        "departmentIds": [department_id] if department_id else [],
        "ownerUserId": _text(_row_get(row, "owner_id")) or None,
        "sourceEntityType": "event_line_manual_update",
        "sourceEntityId": event_line_id,
        "clientId": _text(_row_get(row, "primary_client_id")) or None,
        "eventLineId": event_line_id,
        "contentDomain": content_domain,
        "visibilityScope": visibility_scope,
        "sourceVersion": _text(_row_get(row, "updated_at")),
        "metadata": {
            "organizationId": _text(_row_get(row, "organization_id")),
            "stage": _text(_row_get(row, "stage")),
            "status": _text(_row_get(row, "status")),
            "ownerName": _text(_row_get(row, "owner_name")),
            "primaryDepartmentId": department_id,
            "departmentIds": [department_id] if department_id else [],
        },
    }
    return ingest_user_input(db, data_dir, payload)


def backfill_data_center_ingest(
    db: Database,
    data_dir: Path | str,
    *,
    source_types: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    ensure_data_center_ingest_schema(db)
    selected = source_types or [
        "task",
        "task_note",
        "task_attachment",
        "meeting",
        "weekly_review",
        "event_line_manual_update",
    ]
    counts = {source_type: 0 for source_type in selected}
    errors: list[str] = []

    def _rows(query: str, params: tuple = ()) -> list[Any]:
        suffix = f" LIMIT {int(limit)}" if limit else ""
        return db.fetchall(query + suffix, params)

    for source_type in selected:
        try:
            if source_type == "task":
                for row in _rows(
                    """
                    SELECT id
                    FROM tasks
                    WHERE COALESCE(scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
                    ORDER BY updated_at DESC
                    """
                ):
                    if ingest_task_by_id(db, data_dir, _text(row["id"])):
                        counts[source_type] += 1
            elif source_type == "task_note":
                for row in _rows(
                    """
                    SELECT task_id FROM task_notes
                    UNION
                    SELECT task_id FROM task_notes_cloud
                    ORDER BY task_id
                    """
                ):
                    if ingest_task_note_by_id(db, data_dir, _text(row["task_id"])):
                        counts[source_type] += 1
            elif source_type == "task_attachment":
                for row in _rows(
                    """
                    SELECT id FROM task_attachments
                    UNION
                    SELECT id FROM task_attachments_cloud
                    ORDER BY id
                    """
                ):
                    if ingest_task_attachment_by_id(db, data_dir, _text(row["id"])):
                        counts[source_type] += 1
            elif source_type == "meeting":
                for row in _rows("SELECT id FROM meetings ORDER BY updated_at DESC"):
                    if ingest_meeting_by_id(db, data_dir, _text(row["id"])):
                        counts[source_type] += 1
            elif source_type == "weekly_review":
                for row in _rows("SELECT id FROM weekly_reviews ORDER BY updated_at DESC"):
                    if ingest_weekly_review_by_id(db, data_dir, _text(row["id"])):
                        counts[source_type] += 1
            elif source_type == "event_line_manual_update":
                for row in _rows("SELECT id FROM event_lines ORDER BY updated_at DESC"):
                    if ingest_event_line_by_id(db, data_dir, _text(row["id"])):
                        counts[source_type] += 1
        except Exception as exc:
            logger.exception("DataCenterIngest backfill failed for %s", source_type)
            errors.append(f"{source_type}: {exc}")
    return {"counts": counts, "errors": errors}
