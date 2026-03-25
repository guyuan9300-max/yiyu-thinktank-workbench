from __future__ import annotations

import os
import sqlite3
from pathlib import Path


AUDIT_PREFIX = "【审计】%"
AUDIT_CONTAINS = "%【审计】%"
AUDIT_FIXTURE_PATH = "/tmp/yiyu-audit-fixtures%"
AUDIT_FIXTURE_CONTAINS = "%/tmp/yiyu-audit-fixtures%"


def resolve_db_path() -> Path:
    data_dir = os.environ.get("YIYU_WORKBENCH_DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser() / "app.db"
    return Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"


def delete_like(cursor: sqlite3.Cursor, table: str, column: str, pattern: str) -> int:
    cursor.execute(f"DELETE FROM {table} WHERE {column} LIKE ?", (pattern,))
    return cursor.rowcount


def main() -> None:
    db_path = resolve_db_path()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        deleted: dict[str, int] = {}
        audit_client_ids = [row[0] for row in cursor.execute("SELECT id FROM clients WHERE name LIKE ?", (AUDIT_PREFIX,)).fetchall()]
        audit_meeting_ids: list[str] = []
        if audit_client_ids:
            placeholders = ",".join("?" for _ in audit_client_ids)
            audit_meeting_ids = [
                row[0]
                for row in cursor.execute(
                    f"SELECT id FROM meetings WHERE client_id IN ({placeholders})",
                    tuple(audit_client_ids),
                ).fetchall()
            ]

        deleted["task_notes.audit"] = delete_like(cursor, "task_notes", "note", AUDIT_CONTAINS)
        deleted["weekly_reviews.audit"] = delete_like(cursor, "weekly_reviews", "summary", AUDIT_CONTAINS)
        deleted["chat_messages.audit"] = delete_like(cursor, "chat_messages", "content", AUDIT_CONTAINS)
        deleted["activity_logs.audit"] = delete_like(cursor, "activity_logs", "detail_json", AUDIT_CONTAINS)
        deleted["activity_logs.fixture"] = delete_like(cursor, "activity_logs", "detail_json", AUDIT_FIXTURE_CONTAINS)
        deleted["documents.fixture"] = delete_like(cursor, "documents", "path", AUDIT_FIXTURE_PATH)
        deleted["imports.fixture"] = delete_like(cursor, "imports", "source_path", AUDIT_FIXTURE_PATH)
        deleted["client_folders.fixture"] = delete_like(cursor, "client_folders", "path", AUDIT_FIXTURE_PATH)
        deleted["analysis_runs.audit"] = delete_like(cursor, "analysis_runs", "input_text", AUDIT_CONTAINS)
        deleted["topic_candidates.audit"] = delete_like(cursor, "topic_candidates", "title", AUDIT_PREFIX)
        deleted["handbook_entries.audit"] = delete_like(cursor, "handbook_entries", "title", AUDIT_PREFIX)
        if audit_meeting_ids:
            placeholders = ",".join("?" for _ in audit_meeting_ids)
            cursor.execute(
                f"DELETE FROM tasks WHERE source_type = 'meeting' AND source_id IN ({placeholders})",
                tuple(audit_meeting_ids),
            )
            deleted["tasks.audit_meeting_source"] = cursor.rowcount
        else:
            deleted["tasks.audit_meeting_source"] = 0
        deleted["tasks.audit"] = delete_like(cursor, "tasks", "title", AUDIT_PREFIX)
        deleted["topic_radars.audit"] = delete_like(cursor, "topic_radars", "title", AUDIT_PREFIX)
        deleted["clients.audit"] = delete_like(cursor, "clients", "name", AUDIT_PREFIX)
        conn.commit()
    finally:
        conn.close()

    print(f"Audit cleanup completed for {db_path}")
    for key, count in deleted.items():
        print(f"{key}: {count}")


if __name__ == "__main__":
    main()
