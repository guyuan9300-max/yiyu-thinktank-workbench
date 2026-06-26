"""经验手册条目 (handbook_entries) 云端同步 service.

跟 exp_wall_service 真**push/pull 真模式一致**:
- 本地写 handbook_entries → mark sync_status='pending' + pending_sync_action='upsert'
- 本地软删 → mark sync_status='pending' + pending_sync_action='upsert' (status='deleted')
- 后台 worker 每 5 min push 待推送条目 + pull 增量

顾源源 5/27 · handbook_entries 真**才是前端经验墙真当前真数据源**.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from app.db import Database

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _row_to_cloud_payload(row: sqlite3.Row) -> dict[str, object]:
    """本地 handbook_entries row → cloud POST payload (camelCase, 全字段)."""
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "summary": str(row["summary"]),
        "tagsJson": str(row["tags_json"] or "[]"),
        "sourceType": str(row["source_type"]),
        "clientId": str(row["client_id"]) if row["client_id"] else None,
        "sourceObjectType": str(row["source_object_type"]) if row["source_object_type"] else None,
        "sourceObjectId": str(row["source_object_id"]) if row["source_object_id"] else None,
        "sourceTitle": str(row["source_title"]) if row["source_title"] else None,
        "eventLineId": str(row["event_line_id"]) if row["event_line_id"] else None,
        "eventLineName": str(row["event_line_name"]) if row["event_line_name"] else None,
        "projectModuleId": str(row["project_module_id"]) if row["project_module_id"] else None,
        "projectModuleName": str(row["project_module_name"]) if row["project_module_name"] else None,
        "projectFlowId": str(row["project_flow_id"]) if row["project_flow_id"] else None,
        "projectFlowName": str(row["project_flow_name"]) if row["project_flow_name"] else None,
        "projectStage": str(row["project_stage"]) if row["project_stage"] else None,
        "businessCategory": str(row["business_category"]) if row["business_category"] else None,
        "abilityKeysJson": str(row["ability_keys_json"] or "[]"),
        "evidenceRefsJson": str(row["evidence_refs_json"] or "[]"),
        "contextSummary": str(row["context_summary"] or ""),
        "reuseCount": int(row["reuse_count"] or 0),
        "lastReusedAt": str(row["last_reused_at"]) if row["last_reused_at"] else None,
        "authorUserId": str(row["author_user_id"] or ""),
        "authorUserName": str(row["author_user_name"] or ""),
        # status / deleted_by_user_id / deleted_at 真本地 schema 可能没有 — 真接 row.get 兜底
        "status": str(row["status"]) if "status" in row.keys() and row["status"] else "active",
        "deletedByUserId": (
            str(row["deleted_by_user_id"])
            if "deleted_by_user_id" in row.keys() and row["deleted_by_user_id"]
            else None
        ),
        "deletedAt": (
            str(row["deleted_at"])
            if "deleted_at" in row.keys() and row["deleted_at"]
            else None
        ),
        "createdAt": str(row["created_at"]),
        "updatedAt": _now_iso(),  # 本地 schema 真无 updated_at, push 时用当前时间
    }


def mark_entry_pending(db: Database, entry_id: str) -> None:
    """供 create_handbook_entry / 软删 handler 真调用. 真**真**幂等."""
    db.conn.execute(
        "UPDATE handbook_entries SET sync_status='pending', pending_sync_action='upsert' WHERE id = ?",
        (entry_id,),
    )
    db.conn.commit()


def push_pending_entries_to_cloud(
    db: Database,
    *,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    sandbox_id: str | None = None,
) -> dict[str, int]:
    """扫 sync_status='pending' 真 handbook entry, 真逐条 POST. 真成功 → 'synced', 失败 → 'failed'."""
    if sandbox_id:
        rows = db.fetchall(
            "SELECT * FROM handbook_entries WHERE sync_status = 'pending' AND sandbox_id = ? ORDER BY created_at ASC LIMIT 50",
            (sandbox_id,),
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM handbook_entries WHERE sync_status = 'pending' ORDER BY created_at ASC LIMIT 50"
        )
    pushed = 0
    failed = 0
    for row in rows:
        entry_id = str(row["id"])
        # author_user_id 必填 (云端 schema NOT NULL), 真没 author 真跳过
        if not row["author_user_id"]:
            db.conn.execute(
                "UPDATE handbook_entries SET sync_status='failed' WHERE id = ?",
                (entry_id,),
            )
            failed += 1
            continue
        try:
            payload = _row_to_cloud_payload(row)
            resp = httpx_client.post(
                f"{cloud_base_url.rstrip('/')}/api/v1/handbook/entries/sync",
                json=payload,
                headers={"Authorization": f"Bearer {cloud_token}"},
                timeout=15.0,
            )
            if 200 <= resp.status_code < 300:
                db.conn.execute(
                    "UPDATE handbook_entries SET sync_status='synced', last_synced_at=?, pending_sync_action='' WHERE id = ?",
                    (_now_iso(), entry_id),
                )
                pushed += 1
            else:
                logger.warning(
                    "push handbook entry %s failed: HTTP %d %s",
                    entry_id, resp.status_code, resp.text[:200],
                )
                db.conn.execute(
                    "UPDATE handbook_entries SET sync_status='failed' WHERE id = ?",
                    (entry_id,),
                )
                failed += 1
        except Exception as exc:
            logger.warning("push handbook entry %s exception: %s", entry_id, exc)
            db.conn.execute(
                "UPDATE handbook_entries SET sync_status='failed' WHERE id = ?",
                (entry_id,),
            )
            failed += 1
    db.conn.commit()
    return {"pushed": pushed, "failed": failed}


def _scoped_pull_key(base_key: str, sandbox_id: str | None) -> str:
    normalized = (sandbox_id or "").strip()
    return f"{base_key}.{normalized}" if normalized else base_key


def pull_entries_from_cloud(
    db: Database,
    *,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    sandbox_id: str | None = None,
) -> dict[str, object]:
    """定时拉云端增量 handbook entries (since=settings.last_handbook_pull_at).

    合并策略:
      · 云端权威 — 按 id upsert 到本地
      · 跳过 sync_status='pending' 真本地 row (避免覆盖还未 push 的更新)
      · 自己 push 真 entry 真也会回流, 真**幂等不伤**
      · 本地真 handbook_entries 真**无 status / deleted_by_user_id / deleted_at**, 真**这次顺手补真**
    """
    # 真**先补字段** (idempotent)
    db.conn.execute("PRAGMA foreign_keys=ON")
    cols = {row[1] for row in db.conn.execute("PRAGMA table_info(handbook_entries)").fetchall()}
    if "status" not in cols:
        db.conn.execute("ALTER TABLE handbook_entries ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    if "deleted_by_user_id" not in cols:
        db.conn.execute("ALTER TABLE handbook_entries ADD COLUMN deleted_by_user_id TEXT")
    if "deleted_at" not in cols:
        db.conn.execute("ALTER TABLE handbook_entries ADD COLUMN deleted_at TEXT")
    db.conn.commit()

    pull_key = _scoped_pull_key("last_handbook_pull_at", sandbox_id)
    since = db.get_setting(pull_key, "") or db.get_setting("last_handbook_pull_at", "")
    try:
        resp = httpx_client.get(
            f"{cloud_base_url.rstrip('/')}/api/v1/handbook/entries/sync",
            params={"since": since} if since else {},
            headers={"Authorization": f"Bearer {cloud_token}"},
            timeout=20.0,
        )
        if not (200 <= resp.status_code < 300):
            logger.warning("pull handbook entries failed: HTTP %d", resp.status_code)
            return {"pulled": 0, "merged": 0, "skipped_pending": 0}
        data = resp.json()
    except Exception as exc:
        logger.warning("pull handbook entries exception: %s", exc)
        return {"pulled": 0, "merged": 0, "skipped_pending": 0}

    entries = data.get("entries", []) or []
    server_ts = data.get("serverTimestamp", "") or _now_iso()
    merged = 0
    skipped_pending = 0
    for e in entries:
        entry_id = str(e.get("id", ""))
        if not entry_id:
            continue
        existing = db.fetchone(
            "SELECT sync_status FROM handbook_entries WHERE id = ?",
            (entry_id,),
        )
        if existing and str(existing["sync_status"]) == "pending":
            skipped_pending += 1
            continue
        db.conn.execute(
            """
            INSERT INTO handbook_entries(
                id, sandbox_id, title, summary, tags_json,
                source_type, client_id, source_object_type, source_object_id, source_title,
                event_line_id, event_line_name,
                project_module_id, project_module_name, project_flow_id, project_flow_name,
                project_stage, business_category,
                ability_keys_json, evidence_refs_json, context_summary,
                reuse_count, last_reused_at,
                author_user_id, author_user_name,
                status, deleted_by_user_id, deleted_at,
                created_at,
                sync_status, last_synced_at, pending_sync_action
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, '')
            ON CONFLICT(id) DO UPDATE SET
                sandbox_id = excluded.sandbox_id,
                title = excluded.title,
                summary = excluded.summary,
                tags_json = excluded.tags_json,
                ability_keys_json = excluded.ability_keys_json,
                evidence_refs_json = excluded.evidence_refs_json,
                context_summary = excluded.context_summary,
                reuse_count = excluded.reuse_count,
                last_reused_at = excluded.last_reused_at,
                status = excluded.status,
                deleted_by_user_id = excluded.deleted_by_user_id,
                deleted_at = excluded.deleted_at,
                author_user_name = excluded.author_user_name,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at,
                pending_sync_action = ''
            """,
            (
                entry_id, (sandbox_id or "sbx_local_default"), str(e.get("title", "")), str(e.get("summary", "")), str(e.get("tagsJson", "[]")),
                str(e.get("sourceType", "")),
                e.get("clientId"), e.get("sourceObjectType"), e.get("sourceObjectId"), e.get("sourceTitle"),
                e.get("eventLineId"), e.get("eventLineName"),
                e.get("projectModuleId"), e.get("projectModuleName"),
                e.get("projectFlowId"), e.get("projectFlowName"),
                e.get("projectStage"), e.get("businessCategory"),
                str(e.get("abilityKeysJson", "[]")), str(e.get("evidenceRefsJson", "[]")), str(e.get("contextSummary", "")),
                int(e.get("reuseCount", 0)), e.get("lastReusedAt"),
                str(e.get("authorUserId", "")), str(e.get("authorUserName", "")),
                str(e.get("status", "active")), e.get("deletedByUserId"), e.get("deletedAt"),
                str(e.get("createdAt", "")),
                _now_iso(),
            ),
        )
        merged += 1

    db.set_setting(pull_key, server_ts)
    db.conn.commit()
    return {"pulled": len(entries), "merged": merged, "skipped_pending": skipped_pending}


__all__ = [
    "mark_entry_pending",
    "push_pending_entries_to_cloud",
    "pull_entries_from_cloud",
]
