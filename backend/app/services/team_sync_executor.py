"""[B] 2026-05-27 V2.3 Step 3 · 本地 → 云端 team_documents 同步执行器

设计:
  · 手动触发模式 (不开后台 thread, 减少未知风险)
  · 从 source_registry 扫待同步项 (跨 outbox 路径, 直接基于真权威来源表)
  · batch 50 个/批 POST 到 cloud_backend
  · 已同步: 标 status='synced'
  · 失败 5 次: 标 status='failed' (人工介入)
  · retry-with-backoff: 单次失败立刻 retry, 不挂 worker

入口:
  · run_team_sync_once(db, cloud_request_fn) → 同步一批
  · enqueue_all_unsynced(db) → 把所有 source_registry 待同步项标 'pending'
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

logger = logging.getLogger(__name__)


SYNC_STATE_SETTING_PREFIX = "team_sync:state:"
DEFAULT_BATCH_SIZE = 50
MAX_ATTEMPTS = 5


def ensure_team_sync_schema(db: Any) -> None:
    """加 team_sync_state 表 — 跟踪每个 source_id 是否已同步到云端."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS team_sync_state (
            source_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            cloud_team_doc_id TEXT,
            synced_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_sync_state_status ON team_sync_state(status, attempts)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_sync_state_client ON team_sync_state(client_id)"
    )


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def enqueue_all_unsynced(db: Any) -> dict[str, int]:
    """把所有 source_registry 但未在 team_sync_state 的项标 'pending'."""
    ensure_team_sync_schema(db)
    rows = db.fetchall(
        """
        SELECT sr.source_id, sr.client_id, sr.org_id AS organization_id, sr.content_hash
        FROM source_registry sr
        LEFT JOIN team_sync_state tss ON tss.source_id = sr.source_id
        WHERE tss.source_id IS NULL
          AND sr.org_id IS NOT NULL AND sr.org_id != ''
          AND sr.status = 'active'
        """
    )
    now = _now_iso()
    inserted = 0
    for row in rows:
        try:
            db.execute(
                """
                INSERT INTO team_sync_state(
                    source_id, client_id, organization_id, content_hash,
                    status, attempts, last_error, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, 'pending', 0, '', ?, ?)
                """,
                (
                    row["source_id"],
                    row["client_id"],
                    row["organization_id"],
                    row["content_hash"],
                    now,
                    now,
                ),
            )
            inserted += 1
        except Exception as exc:
            logger.warning("enqueue_all_unsynced row %s failed: %s", row["source_id"], exc)
    return {"inserted": inserted, "total_scanned": len(rows)}


def _build_sync_payload(db: Any, source_id: str) -> dict[str, Any] | None:
    """构造 1 个 source_registry 项的同步 payload."""
    row = db.fetchone(
        """
        SELECT sr.source_id, sr.source_type, sr.source_channel, sr.source_owner,
               sr.client_id, sr.user_id, sr.org_id, sr.source_time, sr.capture_time,
               sr.visibility_scope, sr.content_hash, sr.version_id, sr.source_role,
               sr.initial_confidence, sr.raw_reference,
               vd.id AS v2_document_id, vd.document_id, vd.file_name, vd.kind,
               vd.content_hash AS file_content_hash, vd.preview_text, vd.markdown_content,
               vd.section_count, vd.chunk_count, vd.parse_status,
               vd.organization_id AS vd_org_id, vd.owner_user_id, vd.department_id,
               vd.department_ids_json, vd.visibility_scope AS vd_visibility_scope,
               vd.content_domain, vd.lifecycle_status, vd.imported_at, vd.updated_at
        FROM source_registry sr
        LEFT JOIN v2_documents vd ON vd.id = sr.raw_reference
        WHERE sr.source_id = ?
        """,
        (source_id,),
    )
    if not row:
        return None
    return {
        "sourceId": row["source_id"],
        "sourceType": row["source_type"],
        "sourceChannel": row["source_channel"],
        "sourceOwner": row["source_owner"],
        "clientId": row["client_id"],
        "userId": row["user_id"],
        "orgId": row["org_id"],
        "sourceTime": row["source_time"],
        "captureTime": row["capture_time"],
        "visibilityScope": row["visibility_scope"],
        "contentHash": row["content_hash"],
        "versionId": row["version_id"],
        "sourceRole": row["source_role"],
        "initialConfidence": row["initial_confidence"],
        # v2_documents 真内容字段
        "v2Document": {
            "id": row["v2_document_id"],
            "documentId": row["document_id"],
            "fileName": row["file_name"],
            "kind": row["kind"],
            "fileContentHash": row["file_content_hash"],
            "previewText": (row["preview_text"] or "")[:2000],  # 预览限 2k
            "markdownContent": (row["markdown_content"] or "")[:50000],  # 内容限 50k
            "sectionCount": row["section_count"],
            "chunkCount": row["chunk_count"],
            "parseStatus": row["parse_status"],
            "orgId": row["vd_org_id"],
            "ownerUserId": row["owner_user_id"],
            "departmentId": row["department_id"],
            "departmentIdsJson": row["department_ids_json"],
            "visibilityScope": row["vd_visibility_scope"],
            "contentDomain": row["content_domain"],
            "lifecycleStatus": row["lifecycle_status"],
            "importedAt": row["imported_at"],
            "updatedAt": row["updated_at"],
        } if row["v2_document_id"] else None,
    }


def run_team_sync_once(
    db: Any,
    cloud_request: Callable[..., Any],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """跑一次 team sync — 扫 pending 项, batch POST 到云端.

    Args:
      cloud_request: 调用云端 API 的 callable, 签名同 main.py 的 cloud_request
                     (method, path, json_body, timeout) → response dict
      dry_run: True 时只构造 payload, 不真 POST
    """
    ensure_team_sync_schema(db)

    # 取一批 pending
    rows = db.fetchall(
        """
        SELECT source_id FROM team_sync_state
        WHERE status = 'pending' AND attempts < ?
        ORDER BY created_at ASC LIMIT ?
        """,
        (MAX_ATTEMPTS, batch_size),
    )
    if not rows:
        return {"status": "no_pending", "count": 0}

    source_ids = [str(r["source_id"]) for r in rows]
    payloads = []
    for sid in source_ids:
        p = _build_sync_payload(db, sid)
        if p:
            payloads.append(p)

    if dry_run:
        return {
            "status": "dry_run",
            "count": len(payloads),
            "sample": payloads[0] if payloads else None,
        }

    # POST 到云端
    try:
        response = cloud_request(
            "POST",
            "/api/v1/data-center/items/batch",
            json_body={"items": payloads},
            timeout=30.0,
        )
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            now = _now_iso()
            message = "当前组织云暂不支持 data-center batch 同步接口，已停止本批队列自动重试。"
            for sid in source_ids:
                db.execute(
                    """
                    UPDATE team_sync_state
                    SET last_error = ?, updated_at = ?, status = 'cloud_unsupported'
                    WHERE source_id = ?
                    """,
                    (message, now, sid),
                )
            logger.info("run_team_sync_once cloud batch endpoint unsupported (404); marked %d item(s)", len(source_ids))
            return {"status": "cloud_unsupported", "error": message, "count": len(source_ids)}
        logger.warning("run_team_sync_once cloud POST failed: %s", exc)
        # 把这一批失败计入
        now = _now_iso()
        for sid in source_ids:
            db.execute(
                """
                UPDATE team_sync_state
                SET attempts = attempts + 1, last_error = ?, updated_at = ?,
                    status = CASE WHEN attempts + 1 >= ? THEN 'failed' ELSE 'pending' END
                WHERE source_id = ?
                """,
                (str(exc)[:500], now, MAX_ATTEMPTS, sid),
            )
        return {"status": "batch_failed", "error": str(exc), "count": len(source_ids)}

    # 解析云端返回
    if not isinstance(response, dict):
        return {"status": "invalid_response", "count": 0}

    accepted = response.get("accepted") or []
    rejected = response.get("rejected") or []
    duplicates = response.get("duplicates") or []  # 云端按 (org_id, content_hash) 判定已存在

    now = _now_iso()
    accepted_set = {item["sourceId"] for item in accepted if isinstance(item, dict)}
    duplicates_set = {item["sourceId"] for item in duplicates if isinstance(item, dict)}
    rejected_set = {item["sourceId"] for item in rejected if isinstance(item, dict)}

    # 写回 cloud_team_doc_id (server 给的 id)
    accepted_map = {
        item["sourceId"]: item.get("teamDocId")
        for item in accepted if isinstance(item, dict)
    }
    duplicates_map = {
        item["sourceId"]: item.get("teamDocId")
        for item in duplicates if isinstance(item, dict)
    }

    for sid in source_ids:
        if sid in accepted_set:
            db.execute(
                """
                UPDATE team_sync_state
                SET status = 'synced', cloud_team_doc_id = ?, synced_at = ?,
                    last_error = '', updated_at = ?
                WHERE source_id = ?
                """,
                (accepted_map.get(sid, ""), now, now, sid),
            )
        elif sid in duplicates_set:
            db.execute(
                """
                UPDATE team_sync_state
                SET status = 'synced', cloud_team_doc_id = ?, synced_at = ?,
                    last_error = 'cloud_dedup_reused', updated_at = ?
                WHERE source_id = ?
                """,
                (duplicates_map.get(sid, ""), now, now, sid),
            )
        elif sid in rejected_set:
            error_msg = next(
                (item.get("reason", "rejected") for item in rejected
                 if isinstance(item, dict) and item.get("sourceId") == sid),
                "rejected",
            )
            db.execute(
                """
                UPDATE team_sync_state
                SET attempts = attempts + 1, last_error = ?, updated_at = ?,
                    status = CASE WHEN attempts + 1 >= ? THEN 'failed' ELSE 'pending' END
                WHERE source_id = ?
                """,
                (str(error_msg)[:500], now, MAX_ATTEMPTS, sid),
            )

    return {
        "status": "ok",
        "count": len(source_ids),
        "accepted": len(accepted_set),
        "duplicates": len(duplicates_set),
        "rejected": len(rejected_set),
    }


def get_sync_stats(db: Any) -> dict[str, int]:
    """统计当前 team sync 状态."""
    ensure_team_sync_schema(db)
    rows = db.fetchall(
        "SELECT status, COUNT(*) AS n FROM team_sync_state GROUP BY status"
    )
    stats = {row["status"]: int(row["n"]) for row in rows}
    return {
        "pending": stats.get("pending", 0),
        "synced": stats.get("synced", 0),
        "failed": stats.get("failed", 0),
        "total": sum(stats.values()),
    }
