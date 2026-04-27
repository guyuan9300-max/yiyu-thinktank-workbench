from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from app.db import Database
from app.models import WorkspaceContextRefreshEventRecord
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


def _row_to_refresh_event(row) -> WorkspaceContextRefreshEventRecord:
    return WorkspaceContextRefreshEventRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
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
    dedupe_key = f"{normalized_client_id}:{normalized_scope_type}:{normalized_scope_id}:{normalized_reason}"

    existing = db.fetchone(
        """
        SELECT *
        FROM workspace_context_refresh_events
        WHERE dedupe_key = ? AND status IN ('queued', 'running')
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (dedupe_key,),
    )
    if existing:
        return _row_to_refresh_event(existing), True

    now = _now_iso()
    event_id = new_id("wcrf")
    db.execute(
        """
        INSERT INTO workspace_context_refresh_events(
            id, client_id, scope_type, scope_id, source_type, source_id,
            reason, priority, status, job_id, dedupe_key, error, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'queued', NULL, ?, NULL, ?, ?)
        """,
        (
            event_id,
            normalized_client_id,
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
    db.execute(
        """
        UPDATE workspace_context_refresh_events
        SET status = ?,
            job_id = ?,
            error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (status, job_id, (error or "").strip() or None, now, event_id),
    )
    row = db.fetchone("SELECT * FROM workspace_context_refresh_events WHERE id = ?", (event_id,))
    if not row:
        raise KeyError("workspace_context_refresh_event_not_found")
    return _row_to_refresh_event(row)


def list_workspace_context_refresh_events(
    db: Database,
    *,
    client_id: str,
    active_only: bool = False,
    limit: int = 50,
) -> list[WorkspaceContextRefreshEventRecord]:
    ensure_workspace_context_refresh_schema(db)
    where_sql = "client_id = ?"
    params: list[object] = [client_id]
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


def _lookup_job_status(db: Database, job_id: str) -> str | None:
    normalized = str(job_id or "").strip()
    if not normalized:
        return None
    row = db.fetchone("SELECT status FROM knowledge_jobs WHERE id = ? LIMIT 1", (normalized,))
    if row and row["status"] is not None:
        return str(row["status"])
    row = db.fetchone("SELECT status FROM analysis_jobs WHERE id = ? LIMIT 1", (normalized,))
    if row and row["status"] is not None:
        return str(row["status"])
    row = db.fetchone("SELECT status FROM execution_tickets WHERE id = ? LIMIT 1", (normalized,))
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

    stale_running = db.fetchall(
        """
        SELECT id, job_id, updated_at
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
        job_status = _lookup_job_status(db, job_id or "")
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
        SELECT id
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
