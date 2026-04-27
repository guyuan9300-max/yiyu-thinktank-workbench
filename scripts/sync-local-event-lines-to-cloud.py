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
DEFAULT_CLOUD_BASE_URL = os.environ.get("YIYU_CLOUD_API_URL", "http://101.126.34.232").rstrip("/")


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
               participant_ids_json, closed_at, closed_by_user_id, created_at, updated_at
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


def main() -> int:
    parser = argparse.ArgumentParser(description="把桌面本地事件线增量补到当前云端。")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="本地桌面 app.db 路径")
    parser.add_argument("--base-url", default=DEFAULT_CLOUD_BASE_URL, help="云端 API Base URL")
    parser.add_argument("--dry-run", action="store_true", help="只显示待迁移条目，不真正写入云端")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser()
    if not db_path.exists():
        raise SystemExit(f"本地数据库不存在：{db_path}")

    conn = sqlite3.connect(str(db_path))
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
    missing = [item for item in local_event_lines if str(item["id"]) not in remote_ids]

    print(f"本地事件线：{len(local_event_lines)} 条")
    print(f"云端事件线：{len(remote_ids)} 条")
    print(f"待补迁移：{len(missing)} 条")
    for item in missing:
        print(f"- {item['id']} | {item['name']}")

    if args.dry_run or not missing:
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
