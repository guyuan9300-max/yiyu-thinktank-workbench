#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
DEFAULT_CLOUD_BASE_URL = os.environ.get("YIYU_CLOUD_API_URL", "").rstrip("/")


def load_cloud_access_token(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT value FROM settings WHERE key = 'cloud_access_token'").fetchone()
    token = str(row[0]).strip() if row and row[0] else ""
    if not token:
        raise SystemExit("未找到 cloud_access_token，请先在桌面版里登录云端账号。")
    return token


def fetch_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> object:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} 失败：HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {url} 失败：{exc}") from exc
    return json.loads(body)


def local_event_lines_payload(db: sqlite3.Connection) -> list[dict[str, object]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT id, name, kind, status, visibility_scope, business_category, stage, summary, intent,
               current_blocker, recent_decision, next_step, evidence_count, owner_id, owner_name,
               primary_client_id, primary_client_name, primary_department_id, primary_department_name,
               participant_ids_json, closed_at, closed_by_user_id, cloud_id, sync_status,
               pending_sync_action, last_sync_error, created_at, updated_at
        FROM event_lines
        ORDER BY updated_at DESC, created_at DESC
        """
    ).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        activities = db.execute(
            """
            SELECT id, source_type, source_id, happened_at, actor_id, title, summary, metadata_json
            FROM event_line_activities
            WHERE event_line_id = ?
            ORDER BY happened_at ASC, id ASC
            """,
            (str(row["id"]),),
        ).fetchall()
        result.append(
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "kind": str(row["kind"] or "custom"),
                "status": str(row["status"] or "active"),
                "visibilityScope": str(row["visibility_scope"] or "project_public"),
                "businessCategory": str(row["business_category"]) if row["business_category"] else None,
                "stage": str(row["stage"]) if row["stage"] else None,
                "summary": str(row["summary"]) if row["summary"] else None,
                "intent": str(row["intent"]) if row["intent"] else None,
                "currentBlocker": str(row["current_blocker"]) if row["current_blocker"] else None,
                "recentDecision": str(row["recent_decision"]) if row["recent_decision"] else None,
                "nextStep": str(row["next_step"]) if row["next_step"] else None,
                "evidenceCount": int(row["evidence_count"] or 0),
                "ownerId": str(row["owner_id"]) if row["owner_id"] else None,
                "primaryClientId": str(row["primary_client_id"]) if row["primary_client_id"] else None,
                "primaryClientName": str(row["primary_client_name"]) if row["primary_client_name"] else None,
                "primaryDepartmentId": str(row["primary_department_id"]) if row["primary_department_id"] else None,
                "participantIds": [
                    str(item)
                    for item in json.loads(row["participant_ids_json"] or "[]")
                    if str(item).strip()
                ],
                "closedAt": str(row["closed_at"]) if row["closed_at"] else None,
                "closedByUserId": str(row["closed_by_user_id"]) if row["closed_by_user_id"] else None,
                "cloudId": str(row["cloud_id"]) if "cloud_id" in row.keys() and row["cloud_id"] else None,
                "syncStatus": str(row["sync_status"]) if "sync_status" in row.keys() and row["sync_status"] else None,
                "pendingSyncAction": str(row["pending_sync_action"]) if "pending_sync_action" in row.keys() and row["pending_sync_action"] else None,
                "lastSyncError": str(row["last_sync_error"]) if "last_sync_error" in row.keys() and row["last_sync_error"] else None,
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
                "activities": [
                    {
                        "id": str(activity["id"]),
                        "sourceType": str(activity["source_type"]),
                        "sourceId": str(activity["source_id"]),
                        "happenedAt": str(activity["happened_at"]),
                        "actorId": str(activity["actor_id"]) if activity["actor_id"] else None,
                        "title": str(activity["title"]),
                        "summary": str(activity["summary"]),
                        "metadata": (
                            json.loads(activity["metadata_json"] or "{}")
                            if activity["metadata_json"]
                            else {}
                        ),
                    }
                    for activity in activities
                ],
            }
        )
    return result


def ensure_sync_columns(db: sqlite3.Connection) -> None:
    table_columns = {
        table: {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for table in ("event_lines", "tasks")
    }
    for table in ("event_lines", "tasks"):
        columns = table_columns.get(table, set())
        if "sync_status" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'local'")
        if "cloud_id" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN cloud_id TEXT")
        if "cloud_payload_json" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN cloud_payload_json TEXT NOT NULL DEFAULT ''")
        if "last_synced_at" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN last_synced_at TEXT NOT NULL DEFAULT ''")
        if "last_cloud_version" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN last_cloud_version TEXT NOT NULL DEFAULT ''")
        if "pending_sync_action" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN pending_sync_action TEXT NOT NULL DEFAULT ''")
        if "last_sync_error" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN last_sync_error TEXT NOT NULL DEFAULT ''")


def local_event_line_remote_identity(item: dict[str, object]) -> set[str]:
    identities = {str(item["id"])}
    cloud_id = str(item.get("cloudId") or "").strip()
    if cloud_id:
        identities.add(cloud_id)
    return identities


def related_task_rows(db: sqlite3.Connection, event_line_ids: list[str]) -> list[sqlite3.Row]:
    if not event_line_ids:
        return []
    placeholders = ", ".join("?" for _ in event_line_ids)
    return db.execute(
        f"""
        SELECT id, cloud_id, event_line_id, title, description, priority, list_id,
               deadline_at, scheduled_start_at, scheduled_end_at, completed_at, start_date, due_date,
               duration_minutes, scope_mode, client_id, project_module_id, project_flow_id, owner_id,
               source_type, source_id, business_category, current_blocker, next_action, recent_decision,
               evidence_count, sync_status, pending_sync_action, last_sync_error, cloud_payload_json
        FROM tasks
        WHERE event_line_id IN ({placeholders})
        ORDER BY updated_at DESC, created_at DESC
        """,
        tuple(event_line_ids),
    ).fetchall()


def queue_local_repair(db: sqlite3.Connection, missing: list[dict[str, object]], task_rows: list[sqlite3.Row]) -> dict[str, int]:
    ensure_sync_columns(db)
    queued_event_lines = 0
    queued_tasks = 0
    for item in missing:
        event_line_id = str(item["id"])
        action = "archive" if str(item.get("status") or "") == "archived" else "create"
        db.execute(
            """
            UPDATE event_lines
            SET sync_status = 'pending',
                pending_sync_action = ?,
                cloud_payload_json = ?,
                last_sync_error = ''
            WHERE id = ?
            """,
            (action, json.dumps(item, ensure_ascii=False), event_line_id),
        )
        queued_event_lines += 1
    for row in task_rows:
        task_id = str(row["id"])
        task_cloud_id = str(row["cloud_id"] or "").strip()
        task_action = "update" if task_cloud_id else "create"
        existing_payload = str(row["cloud_payload_json"] or "").strip()
        task_payload = existing_payload
        if not task_payload:
            task_payload = json.dumps(
                {
                    "title": str(row["title"] or ""),
                    "description": str(row["description"] or ""),
                    "priority": str(row["priority"] or "normal"),
                    "listId": str(row["list_id"] or "list-0"),
                    "deadlineAt": str(row["deadline_at"]) if row["deadline_at"] else None,
                    "scheduledStartAt": str(row["scheduled_start_at"]) if row["scheduled_start_at"] else None,
                    "scheduledEndAt": str(row["scheduled_end_at"]) if row["scheduled_end_at"] else None,
                    "completedAt": str(row["completed_at"]) if row["completed_at"] else None,
                    "startDate": str(row["start_date"]) if row["start_date"] else None,
                    "dueDate": str(row["due_date"]) if row["due_date"] else None,
                    "durationMinutes": int(row["duration_minutes"] or 60),
                    "scopeMode": str(row["scope_mode"] or "COLLAB_SHARED"),
                    "clientId": str(row["client_id"]) if row["client_id"] else None,
                    "eventLineId": str(row["event_line_id"]) if row["event_line_id"] else None,
                    "projectModuleId": str(row["project_module_id"]) if row["project_module_id"] else None,
                    "projectFlowId": str(row["project_flow_id"]) if row["project_flow_id"] else None,
                    "ownerId": str(row["owner_id"]) if row["owner_id"] else None,
                    "sourceType": str(row["source_type"] or "manual"),
                    "sourceId": str(row["source_id"]) if row["source_id"] else None,
                    "businessCategory": str(row["business_category"]) if row["business_category"] else None,
                    "currentBlocker": str(row["current_blocker"]) if row["current_blocker"] else None,
                    "nextAction": str(row["next_action"]) if row["next_action"] else None,
                    "recentDecision": str(row["recent_decision"]) if row["recent_decision"] else None,
                    "evidenceCount": int(row["evidence_count"] or 0),
                },
                ensure_ascii=False,
            )
        db.execute(
            """
            UPDATE tasks
            SET sync_status = 'pending',
                pending_sync_action = ?,
                cloud_payload_json = ?,
                last_sync_error = ?
            WHERE id = ?
            """,
            (task_action, task_payload, "等待关联事件线先同步到云端", task_id),
        )
        queued_tasks += 1
    db.commit()
    return {"eventLines": queued_event_lines, "tasks": queued_tasks}


def main() -> int:
    parser = argparse.ArgumentParser(description="把桌面本地事件线增量补到当前云端。")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="本地桌面 app.db 路径")
    parser.add_argument("--base-url", default=DEFAULT_CLOUD_BASE_URL, help="云端 API Base URL")
    parser.add_argument("--dry-run", action="store_true", help="只显示待修复条目，不写本地同步队列")
    parser.add_argument("--apply", action="store_true", help="只修补本地 sync metadata 和重试队列，不直接写云端")
    parser.add_argument("--upload-cloud", action="store_true", help="旧行为：直接调用云端 import-desktop 上传缺失事件线")
    args = parser.parse_args()

    if not str(args.base_url or "").strip():
        raise SystemExit("请通过 --base-url 或 YIYU_CLOUD_API_URL 显式指定云端 API Base URL。")

    db_path = Path(args.db_path).expanduser()
    if not db_path.exists():
        raise SystemExit(f"本地数据库不存在：{db_path}")

    conn = sqlite3.connect(str(db_path))
    ensure_sync_columns(conn)
    token = load_cloud_access_token(conn)
    local_event_lines = local_event_lines_payload(conn)
    remote_event_lines = fetch_json(f"{args.base_url}/api/v1/event-lines", token)
    if not isinstance(remote_event_lines, list):
        raise SystemExit("云端事件线返回格式异常。")
    remote_ids = {
        str(item.get("id"))
        for item in remote_event_lines
        if isinstance(item, dict) and item.get("id")
    }
    missing = [item for item in local_event_lines if local_event_line_remote_identity(item).isdisjoint(remote_ids)]
    missing_ids = [str(item["id"]) for item in missing]
    related_tasks = related_task_rows(conn, missing_ids)

    print(f"本地事件线：{len(local_event_lines)} 条")
    print(f"云端事件线：{len(remote_ids)} 条")
    print(f"待补迁移：{len(missing)} 条")
    for item in missing:
        print(f"- {item['id']} | {item['name']}")
    print(f"关联任务：{len(related_tasks)} 条")
    for row in related_tasks[:30]:
        cloud_suffix = f" cloud_id={row['cloud_id']}" if row["cloud_id"] else " local-only"
        print(f"  - {row['id']} | event_line_id={row['event_line_id']} | {row['title']}{cloud_suffix}")

    if args.apply:
        result = queue_local_repair(conn, missing, related_tasks)
        print(json.dumps({"queued": result}, ensure_ascii=False, indent=2))
        return 0

    if args.dry_run or not args.upload_cloud or not missing:
        return 0

    result = fetch_json(
        f"{args.base_url}/api/v1/event-lines/import-desktop",
        token,
        method="POST",
        payload={"eventLines": missing},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
