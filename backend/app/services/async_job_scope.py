from __future__ import annotations

from typing import Any

from app.db import Database
from app.services.workspace_context import WorkspaceContext, load_workspace_context


ASYNC_JOB_TABLES = (
    "knowledge_jobs",
    "analysis_jobs",
    "workspace_context_refresh_events",
)


class AsyncJobScopeError(RuntimeError):
    """Permanent async-job scope violation; callers must fail closed, not retry/fallback."""

    def __init__(self, code: str, *, client_id: str = "", sandbox_id: str = "") -> None:
        self.code = str(code or "async_job_scope_invalid")
        self.client_id = str(client_id or "").strip()
        self.sandbox_id = str(sandbox_id or "").strip()
        super().__init__(
            f"async_job_scope:{self.code}:client={self.client_id or '-'}:sandbox={self.sandbox_id or '-'}"
        )


def load_persisted_job_workspace_context(
    db: Database,
    *,
    sandbox_id: str | None,
    client_id: str,
) -> WorkspaceContext:
    """Resolve only the scope persisted on a job; never consult active/default workspace."""

    normalized_sandbox_id = str(sandbox_id or "").strip()
    normalized_client_id = str(client_id or "").strip()
    if not normalized_sandbox_id:
        raise AsyncJobScopeError("missing_sandbox_id", client_id=normalized_client_id)
    if not normalized_client_id:
        raise AsyncJobScopeError("missing_client_id", sandbox_id=normalized_sandbox_id)

    client_row = db.fetchone(
        "SELECT sandbox_id FROM clients WHERE id = ? LIMIT 1",
        (normalized_client_id,),
    )
    if not client_row:
        raise AsyncJobScopeError(
            "client_not_found",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )
    parent_sandbox_id = str(client_row["sandbox_id"] or "").strip()
    if not parent_sandbox_id:
        raise AsyncJobScopeError(
            "client_missing_sandbox_id",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )
    if parent_sandbox_id != normalized_sandbox_id:
        raise AsyncJobScopeError(
            "client_sandbox_mismatch",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )

    sandbox_row = db.fetchone(
        "SELECT status FROM sandboxes WHERE id = ? LIMIT 1",
        (normalized_sandbox_id,),
    )
    if not sandbox_row:
        raise AsyncJobScopeError(
            "sandbox_not_found",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )
    if str(sandbox_row["status"] or "").strip() != "active":
        raise AsyncJobScopeError(
            "sandbox_not_active",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )

    context = load_workspace_context(db, normalized_sandbox_id)
    if context.kind == "missing" or context.sandbox_id != normalized_sandbox_id:
        raise AsyncJobScopeError(
            "workspace_context_mismatch",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )
    if not context.session_matches_workspace:
        raise AsyncJobScopeError(
            "workspace_session_mismatch",
            client_id=normalized_client_id,
            sandbox_id=normalized_sandbox_id,
        )
    return context


def resolve_client_workspace_context(db: Database, client_id: str) -> WorkspaceContext:
    """Derive a new job scope from its authoritative parent client."""

    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        raise AsyncJobScopeError("missing_client_id")
    row = db.fetchone(
        "SELECT sandbox_id FROM clients WHERE id = ? LIMIT 1",
        (normalized_client_id,),
    )
    if not row:
        raise AsyncJobScopeError("client_not_found", client_id=normalized_client_id)
    sandbox_id = str(row["sandbox_id"] or "").strip()
    if not sandbox_id:
        raise AsyncJobScopeError("client_missing_sandbox_id", client_id=normalized_client_id)
    return load_persisted_job_workspace_context(
        db,
        sandbox_id=sandbox_id,
        client_id=normalized_client_id,
    )


def backfill_async_job_sandbox_ids(db: Database) -> dict[str, int]:
    """Idempotently fill NULL scope only when the exact parent client proves it."""

    def _backfill(conn: Any) -> dict[str, int]:
        results = {table_name: 0 for table_name in ASYNC_JOB_TABLES}
        for table_name in ASYNC_JOB_TABLES:
            columns = {
                str(row["name"])
                for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if not {"client_id", "sandbox_id"}.issubset(columns):
                continue
            cursor = conn.execute(
                f"""
                UPDATE {table_name}
                   SET sandbox_id = (
                       SELECT clients.sandbox_id
                         FROM clients
                        WHERE clients.id = {table_name}.client_id
                          AND TRIM(COALESCE(clients.sandbox_id, '')) <> ''
                        LIMIT 1
                   )
                 WHERE TRIM(COALESCE({table_name}.sandbox_id, '')) = ''
                   AND EXISTS (
                       SELECT 1
                         FROM clients
                        WHERE clients.id = {table_name}.client_id
                          AND TRIM(COALESCE(clients.sandbox_id, '')) <> ''
                   )
                """
            )
            results[table_name] = max(int(cursor.rowcount or 0), 0)
        return results

    return db.run_in_transaction(_backfill)
