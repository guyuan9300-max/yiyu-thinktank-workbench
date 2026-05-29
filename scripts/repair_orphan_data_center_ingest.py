#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import Database  # noqa: E402
from app.services.data_center_ingest import build_orphan_client_ingest_repair_report  # noqa: E402


def default_db_path() -> Path:
    return Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"


def _fetchall(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params)]


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def build_readonly_report(db_path: Path, *, sample_limit: int) -> dict:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        orphan_task_sql = """
            FROM tasks t
            LEFT JOIN clients c ON c.id = t.client_id
            WHERE COALESCE(t.client_id, '') != ''
              AND c.id IS NULL
        """
        orphan_event_sql = """
            FROM event_lines e
            LEFT JOIN clients c ON c.id = e.primary_client_id
            WHERE COALESCE(e.primary_client_id, '') != ''
              AND c.id IS NULL
        """
        orphan_ingest_sql = """
            FROM data_center_ingest_events e
            LEFT JOIN clients c ON c.id = e.client_id
            WHERE COALESCE(e.client_id, '') != ''
              AND c.id IS NULL
        """
        return {
            "applied": False,
            "orphanTaskCount": _scalar(conn, f"SELECT COUNT(1) {orphan_task_sql}"),
            "orphanEventLineCount": _scalar(conn, f"SELECT COUNT(1) {orphan_event_sql}"),
            "orphanIngestEventCount": _scalar(conn, f"SELECT COUNT(1) {orphan_ingest_sql}"),
            "fkErrorIngestEventCount": _scalar(
                conn,
                f"SELECT COUNT(1) {orphan_ingest_sql} AND UPPER(COALESCE(e.error_message, '')) LIKE '%FOREIGN KEY%'",
            ),
            "alreadySkippedOrphanClientIngestCount": _scalar(
                conn,
                f"SELECT COUNT(1) {orphan_ingest_sql} AND e.status = 'skipped_orphan_client'",
            ),
            "repairedIngestEventCount": 0,
            "orphanTaskSamples": _fetchall(
                conn,
                f"""
                SELECT t.id, t.title, t.client_id, t.status, t.updated_at
                {orphan_task_sql}
                ORDER BY t.updated_at DESC
                LIMIT ?
                """,
                (sample_limit,),
            ),
            "orphanEventLineSamples": _fetchall(
                conn,
                f"""
                SELECT e.id, e.name, e.primary_client_id, e.primary_client_name, e.status, e.updated_at
                {orphan_event_sql}
                ORDER BY e.updated_at DESC
                LIMIT ?
                """,
                (sample_limit,),
            ),
            "orphanIngestEventSamples": _fetchall(
                conn,
                f"""
                SELECT e.*
                {orphan_ingest_sql}
                ORDER BY e.updated_at DESC, e.created_at DESC
                LIMIT ?
                """,
                (sample_limit,),
            ),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or soft-isolate DataCenterIngest rows with stale client references.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Only print stale client counts and samples.")
    mode.add_argument("--apply", action="store_true", help="Soft-isolate stale client ingest rows.")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="SQLite database path.")
    parser.add_argument("--json-output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument("--sample-limit", type=int, default=20, help="Maximum sample rows per category.")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"database does not exist: {args.db}")

    if args.dry_run:
        report = build_readonly_report(args.db, sample_limit=args.sample_limit)
    else:
        db = Database(args.db)
        report = build_orphan_client_ingest_repair_report(
            db,
            apply=True,
            sample_limit=args.sample_limit,
        )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
