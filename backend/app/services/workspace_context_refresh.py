from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Literal

from app.db import Database
from app.models import WorkspaceContextRefreshEventRecord
from app.services.async_job_scope import resolve_client_workspace_context
from app.services.knowledge_v2 import new_id

ACTIVE_REFRESH_STATUSES = ("queued", "running")


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_workspace_context_refresh_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_context_refresh_events (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            sandbox_id TEXT,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT,
            reason TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'queued',
            job_id TEXT,
            dedupe_key TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.ensure_column("workspace_context_refresh_events", "sandbox_id", "TEXT")
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_context_refresh_client
        ON workspace_context_refresh_events(client_id, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_context_refresh_active_dedupe
        ON workspace_context_refresh_events(dedupe_key)
        WHERE status IN ('queued', 'running')
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_context_refresh_sandbox_client
        ON workspace_context_refresh_events(sandbox_id, client_id, updated_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_context_refresh_sandbox_status
        ON workspace_context_refresh_events(sandbox_id, status, updated_at DESC)
        """
    )


def _row_to_refresh_event(row) -> WorkspaceContextRefreshEventRecord:
    return WorkspaceContextRefreshEventRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        sandboxId=str(row["sandbox_id"]) if row["sandbox_id"] else None,
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]) if row["source_id"] else None,
        reason=str(row["reason"]),
        priority=str(row["priority"] or "normal"),  # type: ignore[arg-type]
        status=str(row["status"] or "queued"),  # type: ignore[arg-type]
        jobId=str(row["job_id"]) if row["job_id"] else None,
        dedupeKey=str(row["dedupe_key"]),
        error=str(row["error"]) if row["error"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def enqueue_workspace_context_refresh(
    db: Database,
    *,
    client_id: str,
    source_type: str,
    source_id: str | None = None,
    reason: str,
    scope_type: str = "client",
    scope_id: str | None = None,
    priority: Literal["low", "normal", "high"] = "normal",
) -> tuple[WorkspaceContextRefreshEventRecord, bool]:
    ensure_workspace_context_refresh_schema(db)
    normalized_client_id = str(client_id or "").strip()
    normalized_scope_type = str(scope_type or "client").strip() or "client"
    normalized_scope_id = str(scope_id or "").strip() or (
        normalized_client_id if normalized_scope_type == "client" else (str(source_id or "").strip() or normalized_client_id)
    )
    normalized_source_type = str(source_type or "unknown").strip() or "unknown"
    normalized_reason = str(reason or normalized_source_type).strip() or normalized_source_type
    normalized_priority = priority if priority in {"low", "normal", "high"} else "normal"
    workspace_context = resolve_client_workspace_context(db, normalized_client_id)
    sandbox_id = workspace_context.sandbox_id
    dedupe_key = (
        f"{sandbox_id}:{normalized_client_id}:{normalized_scope_type}:"
        f"{normalized_scope_id}:{normalized_reason}"
    )

    existing = db.fetchone(
        """
        SELECT *
        FROM workspace_context_refresh_events
        WHERE sandbox_id = ? AND dedupe_key = ? AND status IN ('queued', 'running')
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (sandbox_id, dedupe_key),
    )
    if existing:
        return _row_to_refresh_event(existing), True

    now = _now_iso()
    event_id = new_id("wcrf")
    try:
        db.execute(
            """
            INSERT INTO workspace_context_refresh_events(
                id, client_id, sandbox_id, scope_type, scope_id, source_type, source_id,
                reason, priority, status, job_id, dedupe_key, error, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', NULL, ?, NULL, ?, ?)
            """,
            (
                event_id,
                normalized_client_id,
                sandbox_id,
                normalized_scope_type,
                normalized_scope_id,
                normalized_source_type,
                str(source_id).strip() if source_id else None,
                normalized_reason,
                normalized_priority,
                dedupe_key,
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError:
        # 并发 enqueue 可能同时通过前置 SELECT；唯一索引是最终仲裁者。
        existing = db.fetchone(
            """
            SELECT *
            FROM workspace_context_refresh_events
            WHERE sandbox_id = ? AND dedupe_key = ? AND status IN ('queued', 'running')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (sandbox_id, dedupe_key),
        )
        if existing:
            return _row_to_refresh_event(existing), True
        raise
    row = db.fetchone("SELECT * FROM workspace_context_refresh_events WHERE id = ?", (event_id,))
    assert row is not None
    return _row_to_refresh_event(row), False


def mark_workspace_context_refresh_event_status(
    db: Database,
    *,
    event_id: str,
    status: Literal["queued", "running", "completed", "failed", "canceled"],
    job_id: str | None = None,
    error: str | None = None,
) -> WorkspaceContextRefreshEventRecord:
    ensure_workspace_context_refresh_schema(db)
    now = _now_iso()
    def _mark(conn):
        existing = conn.execute(
            "SELECT id, sandbox_id FROM workspace_context_refresh_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if not existing:
            raise KeyError("workspace_context_refresh_event_not_found")
        persisted_sandbox_id = str(existing["sandbox_id"] or "")
        updated = conn.execute(
            """
            UPDATE workspace_context_refresh_events
            SET status = ?,
                job_id = ?,
                error = ?,
                updated_at = ?
            WHERE id = ? AND COALESCE(sandbox_id, '') = ?
            """,
            (status, job_id, (error or "").strip() or None, now, event_id, persisted_sandbox_id),
        )
        if updated.rowcount != 1:
            raise RuntimeError("workspace_context_refresh_event_scope_changed")
        return conn.execute(
            "SELECT * FROM workspace_context_refresh_events WHERE id = ? AND COALESCE(sandbox_id, '') = ?",
            (event_id, persisted_sandbox_id),
        ).fetchone()

    row = db.run_in_transaction(_mark)
    assert row is not None
    return _row_to_refresh_event(row)


def list_workspace_context_refresh_events(
    db: Database,
    *,
    client_id: str,
    active_only: bool = False,
    limit: int = 50,
) -> list[WorkspaceContextRefreshEventRecord]:
    ensure_workspace_context_refresh_schema(db)
    workspace_context = resolve_client_workspace_context(db, client_id)
    where_sql = "sandbox_id = ? AND client_id = ?"
    params: list[object] = [workspace_context.sandbox_id, client_id]
    if active_only:
        where_sql += " AND status IN ('queued', 'running')"
    params.append(int(max(1, min(limit, 300))))
    rows = db.fetchall(
        f"""
        SELECT *
        FROM workspace_context_refresh_events
        WHERE {where_sql}
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_row_to_refresh_event(row) for row in rows]


def mark_workspace_context_refresh_event_running(
    db: Database,
    *,
    event_id: str,
    job_id: str | None = None,
) -> WorkspaceContextRefreshEventRecord:
    return mark_workspace_context_refresh_event_status(
        db,
        event_id=event_id,
        status="running",
        job_id=job_id,
        error=None,
    )


def mark_workspace_context_refresh_event_completed(
    db: Database,
    *,
    event_id: str,
    job_id: str | None = None,
) -> WorkspaceContextRefreshEventRecord:
    return mark_workspace_context_refresh_event_status(
        db,
        event_id=event_id,
        status="completed",
        job_id=job_id,
        error=None,
    )


def mark_workspace_context_refresh_event_failed(
    db: Database,
    *,
    event_id: str,
    error: str,
    job_id: str | None = None,
) -> WorkspaceContextRefreshEventRecord:
    return mark_workspace_context_refresh_event_status(
        db,
        event_id=event_id,
        status="failed",
        job_id=job_id,
        error=error,
    )


def _lookup_job_status(db: Database, job_id: str, sandbox_id: str) -> str | None:
    normalized = str(job_id or "").strip()
    if not normalized:
        return None
    row = db.fetchone(
        "SELECT status FROM knowledge_jobs WHERE id = ? AND sandbox_id = ? LIMIT 1",
        (normalized, sandbox_id),
    )
    if row and row["status"] is not None:
        return str(row["status"])
    row = db.fetchone(
        "SELECT status FROM analysis_jobs WHERE id = ? AND sandbox_id = ? LIMIT 1",
        (normalized, sandbox_id),
    )
    if row and row["status"] is not None:
        return str(row["status"])
    row = db.fetchone(
        """
        SELECT ticket.status
        FROM execution_tickets ticket
        JOIN clients client ON client.id = ticket.client_id
        WHERE ticket.id = ? AND client.sandbox_id = ?
        LIMIT 1
        """,
        (normalized, sandbox_id),
    )
    if row and row["status"] is not None:
        return str(row["status"])
    return None


def recover_stale_workspace_context_refresh_events(
    db: Database,
    *,
    max_age_minutes: int = 30,
    queued_max_age_minutes: int = 120,
) -> dict[str, int]:
    ensure_workspace_context_refresh_schema(db)
    now = datetime.now()
    running_threshold = (now - timedelta(minutes=max(1, max_age_minutes))).isoformat()
    queued_threshold = (now - timedelta(minutes=max(1, queued_max_age_minutes))).isoformat()

    recovered_completed = 0
    recovered_failed = 0
    recovered_queued_failed = 0

    invalid_active = db.fetchall(
        """
        SELECT event.id
        FROM workspace_context_refresh_events event
        LEFT JOIN clients client ON client.id = event.client_id
        LEFT JOIN sandboxes sandbox ON sandbox.id = event.sandbox_id
        WHERE event.status IN ('queued', 'running')
          AND (
              TRIM(COALESCE(event.sandbox_id, '')) = ''
              OR client.id IS NULL
              OR TRIM(COALESCE(client.sandbox_id, '')) = ''
              OR client.sandbox_id <> event.sandbox_id
              OR sandbox.id IS NULL
              OR sandbox.status <> 'active'
          )
        """
    )
    for row in invalid_active:
        mark_workspace_context_refresh_event_failed(
            db,
            event_id=str(row["id"]),
            error="async_job_scope_invalid",
        )
        recovered_failed += 1

    stale_running = db.fetchall(
        """
        SELECT id, job_id, sandbox_id, updated_at
        FROM workspace_context_refresh_events
        WHERE status = 'running' AND updated_at <= ?
        ORDER BY updated_at ASC
        """,
        (running_threshold,),
    )
    for row in stale_running:
        event_id = str(row["id"] or "").strip()
        if not event_id:
            continue
        job_id = str(row["job_id"] or "").strip() or None
        job_status = _lookup_job_status(db, job_id or "", str(row["sandbox_id"] or ""))
        normalized_job_status = str(job_status or "").strip().lower()
        if normalized_job_status in {"completed", "done", "executed", "success", "succeeded", "ready"}:
            mark_workspace_context_refresh_event_completed(db, event_id=event_id, job_id=job_id)
            recovered_completed += 1
            continue
        if normalized_job_status in {"failed", "error", "rejected", "canceled", "cancelled"}:
            mark_workspace_context_refresh_event_failed(
                db,
                event_id=event_id,
                job_id=job_id,
                error=f"stale_refresh_event_job_failed:{normalized_job_status}",
            )
            recovered_failed += 1
            continue
        mark_workspace_context_refresh_event_failed(
            db,
            event_id=event_id,
            job_id=job_id,
            error="stale_refresh_event_recovered",
        )
        recovered_failed += 1

    stale_queued = db.fetchall(
        """
        SELECT id, sandbox_id
        FROM workspace_context_refresh_events
        WHERE status = 'queued' AND created_at <= ?
        ORDER BY created_at ASC
        """,
        (queued_threshold,),
    )
    for row in stale_queued:
        event_id = str(row["id"] or "").strip()
        if not event_id:
            continue
        mark_workspace_context_refresh_event_failed(
            db,
            event_id=event_id,
            error="stale_refresh_event_queued_too_long",
        )
        recovered_queued_failed += 1

    return {
        "runningRecoveredCompleted": recovered_completed,
        "runningRecoveredFailed": recovered_failed,
        "queuedRecoveredFailed": recovered_queued_failed,
    }
