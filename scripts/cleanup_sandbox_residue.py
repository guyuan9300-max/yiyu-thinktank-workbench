#!/usr/bin/env python3
"""Report and conservatively clean local sandbox residue.

This script is intentionally local-only. It never contacts cloud services and
never deletes cloud data. By default it runs in dry-run mode; pass --apply to
copy a SQLite backup and apply the conservative fixes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not table_exists(conn, table):
        return False
    return any(str(row["name"]) == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def session_organization_id(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ""
    return str(parsed.get("organizationId") or "").strip() if isinstance(parsed, dict) else ""


def merge_metadata(raw: str | None, patch: dict[str, Any]) -> str:
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed.update(patch)
    return json.dumps(parsed, ensure_ascii=False)


def report_identity_residue(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT s.*, ss.value AS session_user
        FROM sandboxes s
        LEFT JOIN sandbox_settings ss
          ON ss.sandbox_id = s.id AND ss.key = 'cloud_session_user'
        WHERE s.kind = 'organization' AND s.status = 'active'
        """
    ).fetchall()
    mismatches: list[dict[str, str]] = []
    duplicate_groups: dict[str, list[str]] = {}
    for row in rows:
        sandbox_id = str(row["id"])
        org_id = str(row["organization_id"] or "").strip()
        session_org_id = session_organization_id(row["session_user"])
        if org_id and session_org_id and org_id != session_org_id:
            mismatches.append({"sandboxId": sandbox_id, "organizationId": org_id, "sessionOrganizationId": session_org_id})
        cloud_instance_id = str(row["cloud_instance_id"] or "").strip()
        if cloud_instance_id and org_id:
            duplicate_groups.setdefault(f"{cloud_instance_id}::{org_id}", []).append(sandbox_id)
    duplicates = {key: value for key, value in duplicate_groups.items() if len(value) > 1}
    return {"identityMismatches": mismatches, "duplicateCloudIdentities": duplicates}


def report_duplicate_client_shells(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(conn, "clients"):
        return []
    rows = conn.execute(
        """
        SELECT COALESCE(sandbox_id, '') AS sandbox_id,
               LOWER(TRIM(name)) AS normalized_name,
               COUNT(1) AS count,
               GROUP_CONCAT(id) AS ids
        FROM clients
        WHERE TRIM(COALESCE(name, '')) != ''
        GROUP BY COALESCE(sandbox_id, ''), LOWER(TRIM(name))
        HAVING COUNT(1) > 1
        ORDER BY count DESC, normalized_name ASC
        """
    ).fetchall()
    return [
        {
            "sandboxId": str(row["sandbox_id"] or ""),
            "name": str(row["normalized_name"] or ""),
            "count": int(row["count"] or 0),
            "clientIds": str(row["ids"] or "").split(","),
        }
        for row in rows
    ]


def report_unassigned(conn: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in ("event_lines", "memory_facts", "data_center_ingest_events", "weekly_reviews"):
        if table_exists(conn, table) and column_exists(conn, table, "sandbox_id"):
            out[table] = int(conn.execute(f"SELECT COUNT(1) AS count FROM {table} WHERE COALESCE(sandbox_id, '') = ''").fetchone()["count"] or 0)
    return out


def archive_identity_mismatches(conn: sqlite3.Connection) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    report = report_identity_residue(conn)
    changed = 0
    for item in report["identityMismatches"]:
        sandbox_id = item["sandboxId"]
        row = conn.execute("SELECT metadata_json FROM sandboxes WHERE id=?", (sandbox_id,)).fetchone()
        metadata_json = merge_metadata(
            row["metadata_json"] if row else "{}",
            {"archivedReason": "identity_mismatch", "archivedAt": now, **item},
        )
        conn.execute(
            """
            UPDATE sandboxes
               SET status='archived',
                   identity_state='mismatch',
                   identity_error=?,
                   metadata_json=?,
                   updated_at=?
             WHERE id=?
            """,
            ("云会话组织与工作空间身份不一致，已由本机清理归档。", metadata_json, now, sandbox_id),
        )
        for key in ("cloud_access_token", "cloud_refresh_token", "cloud_session_user"):
            conn.execute(
                """
                INSERT INTO sandbox_settings(sandbox_id, key, value, updated_at)
                VALUES(?, ?, '', ?)
                ON CONFLICT(sandbox_id, key) DO UPDATE SET value='', updated_at=excluded.updated_at
                """,
                (sandbox_id, key, now),
            )
        changed += 1
    return changed


def backfill_parent_owned_rows(conn: sqlite3.Connection) -> dict[str, int]:
    changed: dict[str, int] = {}
    if table_exists(conn, "event_lines") and table_exists(conn, "clients"):
        cursor = conn.execute(
            """
            UPDATE event_lines
               SET sandbox_id = (
                   SELECT clients.sandbox_id FROM clients WHERE clients.id = event_lines.primary_client_id
               )
             WHERE COALESCE(event_lines.sandbox_id, '') = ''
               AND COALESCE(event_lines.primary_client_id, '') != ''
               AND EXISTS (
                   SELECT 1 FROM clients
                   WHERE clients.id = event_lines.primary_client_id
                     AND COALESCE(clients.sandbox_id, '') != ''
               )
            """
        )
        changed["event_lines"] = cursor.rowcount if cursor.rowcount is not None else 0
    if table_exists(conn, "memory_facts"):
        total = 0
        if table_exists(conn, "clients"):
            total += conn.execute(
                """
                UPDATE memory_facts
                   SET sandbox_id = (SELECT clients.sandbox_id FROM clients WHERE clients.id = memory_facts.scope_id)
                 WHERE COALESCE(memory_facts.sandbox_id, '') = ''
                   AND memory_facts.scope_type = 'client'
                   AND EXISTS (
                       SELECT 1 FROM clients
                       WHERE clients.id = memory_facts.scope_id
                         AND COALESCE(clients.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        if table_exists(conn, "tasks"):
            total += conn.execute(
                """
                UPDATE memory_facts
                   SET sandbox_id = (SELECT tasks.sandbox_id FROM tasks WHERE tasks.id = memory_facts.scope_id)
                 WHERE COALESCE(memory_facts.sandbox_id, '') = ''
                   AND memory_facts.scope_type = 'task'
                   AND EXISTS (
                       SELECT 1 FROM tasks
                       WHERE tasks.id = memory_facts.scope_id
                         AND COALESCE(tasks.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        if table_exists(conn, "event_lines"):
            total += conn.execute(
                """
                UPDATE memory_facts
                   SET sandbox_id = (SELECT event_lines.sandbox_id FROM event_lines WHERE event_lines.id = memory_facts.scope_id)
                 WHERE COALESCE(memory_facts.sandbox_id, '') = ''
                   AND memory_facts.scope_type = 'event_line'
                   AND EXISTS (
                       SELECT 1 FROM event_lines
                       WHERE event_lines.id = memory_facts.scope_id
                         AND COALESCE(event_lines.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        changed["memory_facts"] = total
    if table_exists(conn, "data_center_ingest_events"):
        total = 0
        if table_exists(conn, "clients") and column_exists(conn, "data_center_ingest_events", "client_id"):
            total += conn.execute(
                """
                UPDATE data_center_ingest_events
                   SET sandbox_id = (SELECT clients.sandbox_id FROM clients WHERE clients.id = data_center_ingest_events.client_id)
                 WHERE COALESCE(data_center_ingest_events.sandbox_id, '') = ''
                   AND COALESCE(data_center_ingest_events.client_id, '') != ''
                   AND EXISTS (
                       SELECT 1 FROM clients
                       WHERE clients.id = data_center_ingest_events.client_id
                         AND COALESCE(clients.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        if table_exists(conn, "tasks") and column_exists(conn, "data_center_ingest_events", "task_id"):
            total += conn.execute(
                """
                UPDATE data_center_ingest_events
                   SET sandbox_id = (SELECT tasks.sandbox_id FROM tasks WHERE tasks.id = data_center_ingest_events.task_id)
                 WHERE COALESCE(data_center_ingest_events.sandbox_id, '') = ''
                   AND COALESCE(data_center_ingest_events.task_id, '') != ''
                   AND EXISTS (
                       SELECT 1 FROM tasks
                       WHERE tasks.id = data_center_ingest_events.task_id
                         AND COALESCE(tasks.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        if table_exists(conn, "event_lines") and column_exists(conn, "data_center_ingest_events", "event_line_id"):
            total += conn.execute(
                """
                UPDATE data_center_ingest_events
                   SET sandbox_id = (SELECT event_lines.sandbox_id FROM event_lines WHERE event_lines.id = data_center_ingest_events.event_line_id)
                 WHERE COALESCE(data_center_ingest_events.sandbox_id, '') = ''
                   AND COALESCE(data_center_ingest_events.event_line_id, '') != ''
                   AND EXISTS (
                       SELECT 1 FROM event_lines
                       WHERE event_lines.id = data_center_ingest_events.event_line_id
                         AND COALESCE(event_lines.sandbox_id, '') != ''
                   )
                """
            ).rowcount or 0
        changed["data_center_ingest_events"] = total
    return changed


def build_report(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "identity": report_identity_residue(conn),
        "duplicateClientShells": report_duplicate_client_shells(conn),
        "unassigned": report_unassigned(conn),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report or clean local sandbox residue")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to local app.db")
    parser.add_argument("--apply", action="store_true", help="Apply conservative cleanup after backing up the DB")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    db_path = args.db.expanduser()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    backup_path = None
    if args.apply:
        backup_path = db_path.with_name(f"{db_path.name}.bak-sandbox-cleanup-{now_tag()}")
        shutil.copy2(db_path, backup_path)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, Path(str(backup_path) + suffix))

    conn = connect(db_path)
    before = build_report(conn)
    applied: dict[str, Any] = {}
    if args.apply:
        try:
            conn.execute("BEGIN")
            applied["archivedIdentityMismatches"] = archive_identity_mismatches(conn)
            applied["backfilled"] = backfill_parent_owned_rows(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    after = build_report(conn)
    payload = {
        "db": str(db_path),
        "backup": str(backup_path) if backup_path else None,
        "mode": "apply" if args.apply else "dry-run",
        "before": before,
        "applied": applied,
        "after": after,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"DB: {payload['db']}")
        if backup_path:
            print(f"Backup: {backup_path}")
        print(f"Mode: {payload['mode']}")
        print(json.dumps({"before": before, "applied": applied, "after": after}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
