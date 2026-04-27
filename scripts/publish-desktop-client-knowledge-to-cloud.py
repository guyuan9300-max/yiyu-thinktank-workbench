#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
DEFAULT_CLOUD_BASE_URL = os.environ.get("YIYU_CLOUD_API_URL", "http://101.126.34.232").rstrip("/")
SUPPORTED_SOURCE_TYPES = (
    "workspace_snapshot",
    "client_dna",
    "event_line_snapshot",
    "meeting_summary",
    "knowledge_surrogate",
    "strategic_cockpit",
)


def table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(db, table_name):
        return set()
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


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
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} 失败：HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {url} 失败：{exc}") from exc
    return json.loads(body)


def stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_clients(db: sqlite3.Connection, selected_client_ids: Iterable[str] | None) -> list[sqlite3.Row]:
    selected = [item.strip() for item in (selected_client_ids or []) if item.strip()]
    db.row_factory = sqlite3.Row
    if selected:
        placeholders = ",".join("?" for _ in selected)
        rows = db.execute(
            f"SELECT id, name, alias, updated_at FROM clients WHERE id IN ({placeholders}) ORDER BY updated_at DESC",
            tuple(selected),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, name, alias, updated_at FROM clients ORDER BY updated_at DESC",
        ).fetchall()
    return list(rows)


def build_workspace_snapshot(db: sqlite3.Connection, client_row: sqlite3.Row) -> dict[str, object]:
    client_id = str(client_row["id"])
    event_line_rows = db.execute(
        """
        SELECT id, name, stage, summary, current_blocker, next_step, recent_decision, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        LIMIT 6
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "event_lines") else []
    task_rows = db.execute(
        """
        SELECT id, title, progress_status, current_blocker, next_action, event_line_id, updated_at
        FROM tasks
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "tasks") else []
    event_line_name_by_id = {str(row["id"]): normalize_text(row["name"]) for row in event_line_rows}
    surrogate_rows = db.execute(
        """
        SELECT id, title, overview_summary, source_type, updated_at
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 4
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "knowledge_surrogates") else []

    goals = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["name"]) or "事件线",
            "summary": normalize_text(row["summary"]) or normalize_text(row["next_step"]),
            "subtitle": normalize_text(row["stage"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in event_line_rows[:4]
    ]
    related_tasks = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["title"]) or "未命名任务",
            "status": normalize_text(row["progress_status"]),
            "eventLineName": event_line_name_by_id.get(normalize_text(row["event_line_id"])) or None,
            "nextAction": normalize_text(row["next_action"]) or normalize_text(row["current_blocker"]) or None,
        }
        for row in task_rows[:6]
    ]
    open_questions = [
        {
            "id": f"question-{row['id']}",
            "title": normalize_text(row["title"]) or "开放问题",
            "summary": normalize_text(row["current_blocker"]) or normalize_text(row["next_action"]),
            "subtitle": normalize_text(row["progress_status"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in task_rows[:4]
        if normalize_text(row["current_blocker"]) or normalize_text(row["next_action"])
    ]
    recent_documents = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["title"]) or "知识代理",
            "summary": normalize_text(row["overview_summary"]),
            "subtitle": normalize_text(row["source_type"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in surrogate_rows[:4]
    ]
    available_sources = ["workspace_snapshot"]
    missing_sources = []
    if recent_documents:
        available_sources.append("knowledge_surrogate")
    else:
        missing_sources.append("knowledge_surrogate")
    if not open_questions:
        missing_sources.append("recent_meetings")
    if not goals and not related_tasks:
        missing_sources.append("workspace_snapshot")

    status = "rich" if recent_documents and goals and related_tasks else ("partial" if goals or related_tasks else "missing")
    return {
        "status": status,
        "client": {
            "id": client_id,
            "name": normalize_text(client_row["name"]) or "客户",
            "updatedAt": normalize_text(client_row["updated_at"]) or None,
        },
        "goals": goals,
        "meetings": [],
        "documentCards": recent_documents,
        "latestOpenQuestions": open_questions,
        "latestConflicts": [
            {
                "id": f"conflict-{row['id']}",
                "title": normalize_text(row["name"]) or "事件线冲突",
                "summary": normalize_text(row["recent_decision"]) or normalize_text(row["current_blocker"]),
                "subtitle": normalize_text(row["stage"]),
                "updatedAt": normalize_text(row["updated_at"]) or None,
            }
            for row in event_line_rows[:3]
            if normalize_text(row["recent_decision"]) or normalize_text(row["current_blocker"])
        ],
        "relatedTasks": related_tasks,
        "availableSources": available_sources,
        "missingSources": missing_sources,
    }


def build_client_dna_summary(db: sqlite3.Connection, client_row: sqlite3.Row) -> dict[str, object] | None:
    if not table_exists(db, "client_dna_documents"):
        return None
    rows = db.execute(
        """
        SELECT module_key, title, summary, normalized_text, updated_at
        FROM client_dna_documents
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (str(client_row["id"]),),
    ).fetchall()
    if not rows:
        return None
    modules = []
    summaries = []
    latest_updated_at = normalize_text(client_row["updated_at"])
    for row in rows:
        text = normalize_text(row["summary"]) or normalize_text(row["normalized_text"])
        if not text or text.startswith('{"prompt'):
            continue
        latest_updated_at = normalize_text(row["updated_at"]) or latest_updated_at
        title = normalize_text(row["title"]) or normalize_text(row["module_key"]) or "客户资料"
        modules.append(
            {
                "moduleKey": normalize_text(row["module_key"]),
                "title": title,
                "summary": text[:2000],
                "updatedAt": normalize_text(row["updated_at"]) or None,
            }
        )
        summaries.append(f"{title}：{text[:220]}")
    if not modules:
        return None
    return {
        "summary": "；".join(summaries[:6]),
        "modules": modules,
        "updatedAt": latest_updated_at or None,
    }


def build_event_line_snapshots(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "event_lines"):
        return []
    rows = db.execute(
        """
        SELECT id, name, status, stage, summary, current_blocker, next_step, recent_decision, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        """,
        (str(client_row["id"]),),
    ).fetchall()
    return [
        {
            "sourceId": str(row["id"]),
            "payload": {
                "id": str(row["id"]),
                "name": normalize_text(row["name"]),
                "status": normalize_text(row["status"]),
                "stage": normalize_text(row["stage"]),
                "summary": normalize_text(row["summary"]),
                "currentBlocker": normalize_text(row["current_blocker"]),
                "nextStep": normalize_text(row["next_step"]),
                "recentDecision": normalize_text(row["recent_decision"]),
            },
            "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
        }
        for row in rows
    ]


def build_meeting_summaries(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "meetings"):
        return []
    columns = table_columns(db, "meetings")
    required = {"id", "client_id"}
    if not required.issubset(columns):
        return []
    title_column = "title" if "title" in columns else None
    summary_column = "summary" if "summary" in columns else ("overview" if "overview" in columns else None)
    date_column = "meeting_date" if "meeting_date" in columns else ("held_at" if "held_at" in columns else "updated_at")
    rows = db.execute(
        f"""
        SELECT id, {title_column or 'id'} AS meeting_title,
               {summary_column or 'id'} AS meeting_summary,
               {date_column} AS meeting_date,
               updated_at
        FROM meetings
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (str(client_row["id"]),),
    ).fetchall()
    result = []
    for row in rows:
        title = normalize_text(row["meeting_title"]) or "会议"
        summary = normalize_text(row["meeting_summary"])
        result.append(
            {
                "sourceId": str(row["id"]),
                "payload": {
                    "title": title,
                    "summary": summary,
                    "meetingDate": normalize_text(row["meeting_date"]) or None,
                },
                "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
            }
        )
    return result


def build_surrogates(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "knowledge_surrogates"):
        return []
    rows = db.execute(
        """
        SELECT id, title, overview_summary, retrieval_summary, source_type, updated_at
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (str(client_row["id"]),),
    ).fetchall()
    return [
        {
            "sourceId": str(row["id"]),
            "payload": {
                "title": normalize_text(row["title"]) or "知识代理",
                "summary": normalize_text(row["overview_summary"]) or normalize_text(row["retrieval_summary"]),
                "overviewSummary": normalize_text(row["overview_summary"]),
                "sourceType": normalize_text(row["source_type"]),
            },
            "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
        }
        for row in rows
        if normalize_text(row["overview_summary"]) or normalize_text(row["retrieval_summary"])
    ]


def build_cockpit_snapshot(workspace_snapshot: dict[str, object], client_row: sqlite3.Row) -> dict[str, object]:
    goals = workspace_snapshot.get("goals") if isinstance(workspace_snapshot.get("goals"), list) else []
    open_questions = workspace_snapshot.get("latestOpenQuestions") if isinstance(workspace_snapshot.get("latestOpenQuestions"), list) else []
    documents = workspace_snapshot.get("documentCards") if isinstance(workspace_snapshot.get("documentCards"), list) else []
    headline = (
        "已从桌面端发布轻量战略 cockpit，可作为手机端咨询的止损上下文。"
        if goals or documents
        else "当前桌面端没有足够资料生成正式战略 cockpit。"
    )
    return {
        "status": "partial" if goals or documents or open_questions else "missing",
        "headline": {"summary": headline},
        "health": [{"summary": item.get("summary") or item.get("title") or "暂无健康线索"} for item in goals[:3] if isinstance(item, dict)],
        "twoWeekChanges": [{"summary": item.get("summary") or item.get("title") or "暂无变化线索"} for item in goals[:3] if isinstance(item, dict)],
        "pendingDecisions": [{"summary": item.get("summary") or item.get("title") or "暂无待决策"} for item in open_questions[:3] if isinstance(item, dict)],
        "pendingMaterials": [{"summary": item.get("summary") or item.get("title") or "暂无待补材料"} for item in documents[:3] if isinstance(item, dict)],
        "updatedAt": normalize_text(client_row["updated_at"]) or None,
    }


def build_publish_items(
    db: sqlite3.Connection,
    client_row: sqlite3.Row,
    include: set[str],
) -> list[dict[str, object]]:
    client_id = str(client_row["id"])
    client_name = normalize_text(client_row["name"]) or "客户"
    items: list[dict[str, object]] = []

    workspace_snapshot = build_workspace_snapshot(db, client_row)
    workspace_updated_at = normalize_text(workspace_snapshot.get("client", {}).get("updatedAt") if isinstance(workspace_snapshot.get("client"), dict) else client_row["updated_at"]) or normalize_text(client_row["updated_at"])

    def append_item(source_type: str, source_id: str, payload: dict[str, object], updated_at: str, evidence_refs: list[str] | None = None) -> None:
        items.append(
            {
                "clientId": client_id,
                "sourceType": source_type,
                "sourceId": source_id,
                "snapshotVersion": 1,
                "snapshotHash": stable_hash(payload),
                "updatedAt": updated_at,
                "payload": payload,
                "evidenceRefs": evidence_refs or [],
            }
        )

    if "workspace_snapshot" in include:
        append_item(
            "workspace_snapshot",
            f"workspace:{client_id}",
            workspace_snapshot,
            workspace_updated_at,
            [f"client:{client_name}"],
        )

    if "client_dna" in include:
        dna_summary = build_client_dna_summary(db, client_row)
        if dna_summary:
            append_item(
                "client_dna",
                f"dna:{client_id}",
                dna_summary,
                normalize_text(dna_summary.get("updatedAt")) or workspace_updated_at,
                [f"client:{client_name}", "client_dna_documents"],
            )

    if "event_line_snapshot" in include:
        for snapshot in build_event_line_snapshots(db, client_row):
            append_item(
                "event_line_snapshot",
                str(snapshot["sourceId"]),
                dict(snapshot["payload"]),
                str(snapshot["updatedAt"]),
                [f"client:{client_name}", f"event_line:{snapshot['sourceId']}"],
            )

    if "meeting_summary" in include:
        for summary in build_meeting_summaries(db, client_row):
            append_item(
                "meeting_summary",
                str(summary["sourceId"]),
                dict(summary["payload"]),
                str(summary["updatedAt"]),
                [f"client:{client_name}", f"meeting:{summary['sourceId']}"],
            )

    if "knowledge_surrogate" in include:
        for surrogate in build_surrogates(db, client_row):
            append_item(
                "knowledge_surrogate",
                str(surrogate["sourceId"]),
                dict(surrogate["payload"]),
                str(surrogate["updatedAt"]),
                [f"client:{client_name}", f"knowledge:{surrogate['sourceId']}"],
            )

    if "strategic_cockpit" in include:
        cockpit_snapshot = build_cockpit_snapshot(workspace_snapshot, client_row)
        append_item(
            "strategic_cockpit",
            f"cockpit:{client_id}",
            cockpit_snapshot,
            normalize_text(cockpit_snapshot.get("updatedAt")) or workspace_updated_at,
            [f"client:{client_name}", "workspace_snapshot"],
        )

    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="把桌面端客户知识快照手动发布到云端 mirror。")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="桌面端本地 app.db 路径")
    parser.add_argument("--base-url", default=DEFAULT_CLOUD_BASE_URL, help="云端 API Base URL")
    parser.add_argument("--client-id", action="append", dest="client_ids", help="只发布指定 client_id，可重复传入")
    parser.add_argument(
        "--include",
        default="workspace_snapshot,client_dna,event_line_snapshot,meeting_summary,knowledge_surrogate,strategic_cockpit",
        help="逗号分隔的 sourceType 白名单",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印将要发布的条目，不真正调用云端")
    args = parser.parse_args()

    include = {item.strip() for item in args.include.split(",") if item.strip()}
    unsupported = sorted(include - set(SUPPORTED_SOURCE_TYPES))
    if unsupported:
        raise SystemExit(f"不支持的 sourceType：{', '.join(unsupported)}")

    db_path = Path(args.db_path).expanduser()
    if not db_path.exists():
        raise SystemExit(f"本地数据库不存在：{db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    token = load_cloud_access_token(conn)
    clients = load_clients(conn, args.client_ids)
    if not clients:
        raise SystemExit("没有找到需要发布的客户。")

    all_items: list[dict[str, object]] = []
    for client_row in clients:
        all_items.extend(build_publish_items(conn, client_row, include))

    print(f"客户数量：{len(clients)}")
    print(f"待发布快照：{len(all_items)} 条")
    for item in all_items[:20]:
        print(f"- {item['clientId']} | {item['sourceType']} | {item['sourceId']}")
    if len(all_items) > 20:
        print(f"... 其余 {len(all_items) - 20} 条未展开")

    if args.dry_run or not all_items:
        return 0

    result = fetch_json(
        f"{args.base_url}/api/v1/mobile/knowledge-mirror/publish",
        token,
        method="POST",
        payload={"items": all_items},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
