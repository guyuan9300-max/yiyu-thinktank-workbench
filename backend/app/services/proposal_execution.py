from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Callable

from app.db import Database, from_json, to_json
from app.models import (
    ExecutionArtifactRefRecord,
    ExecutionTicketLogRecord,
    ExecutionTicketRecord,
    ExecutionTicketResultRecord,
    ProposalExecutionResultRecord,
    ProposalRecordRecord,
)
from app.services.knowledge_v2 import new_id
from app.services.proposal_approval import get_proposal_record


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _build_idempotency_key(*, proposal_id: str, proposal_updated_at: str, execution_type: str) -> str:
    raw = f"{proposal_id}|{proposal_updated_at}|{execution_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _execution_ticket_row_to_record(row) -> ExecutionTicketRecord:
    payload_data = from_json(row["payload_json"], {})
    result_data = from_json(row["result_json"], {})
    if not isinstance(result_data, dict):
        result_data = {}
    artifact_refs_data = result_data.get("artifactRefs", [])
    artifact_refs = (
        [
            ExecutionArtifactRefRecord(
                artifactType=str(item.get("artifactType") or ""),
                refId=str(item.get("refId") or ""),
                title=str(item.get("title") or ""),
            )
            for item in artifact_refs_data
            if isinstance(item, dict)
        ]
        if isinstance(artifact_refs_data, list)
        else []
    )
    result_record = ExecutionTicketResultRecord(
        resultType=(
            str(result_data.get("resultType") or "")
            if str(result_data.get("resultType") or "") in {"recorded_only", "prep_artifact_ready", "followup_task_created", "failed"}
            else ("failed" if str(row["status"]) == "failed" else "recorded_only")
        ),
        summary=str(result_data.get("summary") or result_data.get("message") or ""),
        createdTaskIds=[
            str(item).strip()
            for item in result_data.get("createdTaskIds", [])
            if str(item).strip()
        ]
        if isinstance(result_data.get("createdTaskIds"), list)
        else [],
        artifactRefs=artifact_refs,
    )
    return ExecutionTicketRecord(
        id=str(row["id"]),
        proposalId=str(row["proposal_id"]),
        clientId=str(row["client_id"]),
        executionType=str(row["execution_type"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        payload=payload_data if isinstance(payload_data, dict) else {},
        result=result_record,
        idempotencyKey=str(row["idempotency_key"]) if row["idempotency_key"] else None,
        retryCount=int(row["retry_count"] or 0),
        maxRetries=int(row["max_retries"] or 3),
        lastError=str(row["last_error"]) if row["last_error"] else None,
        lastAttemptAt=str(row["last_attempt_at"]) if row["last_attempt_at"] else None,
        errorMessage=str(row["error_message"]) if row["error_message"] else None,
        executedAt=str(row["executed_at"]) if row["executed_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _log_execution_ticket_stage(
    db: Database,
    *,
    ticket_id: str,
    stage: str,
    status: str,
    message: str = "",
    payload: dict[str, object] | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO execution_ticket_logs(
            id, ticket_id, stage, status, message, payload_json, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("exlog"),
            ticket_id,
            stage,
            status,
            (message or "").strip(),
            to_json(payload or {}),
            _now_iso(),
        ),
    )


def get_execution_ticket(
    db: Database,
    *,
    ticket_id: str,
) -> ExecutionTicketRecord:
    row = db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (ticket_id,))
    if not row:
        raise KeyError("execution_ticket_not_found")
    return _execution_ticket_row_to_record(row)


def create_execution_ticket_for_proposal(
    db: Database,
    *,
    proposal_id: str,
    requested_by: str,
    dry_run: bool = False,
) -> ProposalExecutionResultRecord:
    proposal = get_proposal_record(db, proposal_id=proposal_id)
    if dry_run:
        raise ValueError("dry_run_preview_only")

    if proposal.executionTicketId:
        existing_ticket = get_execution_ticket(db, ticket_id=proposal.executionTicketId)
        if existing_ticket.status in {"pending", "running", "executed"}:
            return ProposalExecutionResultRecord(proposal=proposal, executionTicket=existing_ticket)

    idempotency_key = _build_idempotency_key(
        proposal_id=proposal.id,
        proposal_updated_at=proposal.updatedAt,
        execution_type=proposal.kind,
    )
    existing = db.fetchone(
        """
        SELECT *
        FROM execution_tickets
        WHERE proposal_id = ? AND idempotency_key = ? AND status IN ('pending', 'running', 'executed')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (proposal.id, idempotency_key),
    )
    if existing:
        ticket = _execution_ticket_row_to_record(existing)
        if proposal.executionTicketId != ticket.id:
            db.execute(
                """
                UPDATE proposal_records
                SET execution_ticket_id = ?,
                    status = CASE WHEN status = 'approved' THEN 'execution_pending' ELSE status END,
                    updated_at = ?
                WHERE id = ?
                """,
                (ticket.id, _now_iso(), proposal.id),
            )
            proposal = get_proposal_record(db, proposal_id=proposal.id)
        return ProposalExecutionResultRecord(proposal=proposal, executionTicket=ticket)

    if proposal.status != "approved":
        raise ValueError("proposal_not_ready_for_execution_ticket")

    timestamp = _now_iso()
    payload = proposal.payload if isinstance(proposal.payload, dict) else {}
    payload = {
        **payload,
        "requestedBy": (requested_by or "user").strip() or "user",
    }
    ticket_id = new_id("exec")
    db.execute(
        """
        INSERT INTO execution_tickets(
            id, proposal_id, client_id, execution_type, status, payload_json, result_json,
            idempotency_key, retry_count, max_retries, last_error, last_attempt_at,
            error_message, executed_at, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'pending', ?, '{}', ?, 0, 3, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            ticket_id,
            proposal.id,
            proposal.clientId,
            proposal.kind,
            to_json(payload),
            idempotency_key,
            timestamp,
            timestamp,
        ),
    )
    _log_execution_ticket_stage(
        db,
        ticket_id=ticket_id,
        stage="validate",
        status="success",
        message="execution ticket created",
        payload={"proposalId": proposal.id, "executionType": proposal.kind},
    )
    db.execute(
        """
        UPDATE proposal_records
        SET status = 'execution_pending',
            execution_ticket_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (ticket_id, timestamp, proposal.id),
    )
    updated = get_proposal_record(db, proposal_id=proposal.id)
    ticket = get_execution_ticket(db, ticket_id=ticket_id)
    return ProposalExecutionResultRecord(proposal=updated, executionTicket=ticket)


def execute_proposal_ticket(
    db: Database,
    *,
    ticket_id: str,
    executor: Callable[[ProposalRecordRecord, ExecutionTicketRecord], dict[str, object]],
) -> ExecutionTicketRecord:
    ticket = get_execution_ticket(db, ticket_id=ticket_id)
    if ticket.status == "executed":
        return ticket
    if ticket.status == "failed":
        raise ValueError("execution_ticket_retry_required")
    if ticket.status not in {"pending", "running"}:
        raise ValueError("execution_ticket_not_executable")
    proposal = get_proposal_record(db, proposal_id=ticket.proposalId)
    if proposal.status not in {"execution_pending", "approved"}:
        raise ValueError("proposal_not_execution_pending")

    started_at = _now_iso()
    _log_execution_ticket_stage(db, ticket_id=ticket.id, stage="validate", status="started", message="start execution")
    db.execute(
        """
        UPDATE execution_tickets
        SET status = 'running',
            last_attempt_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (started_at, started_at, ticket.id),
    )
    _log_execution_ticket_stage(
        db,
        ticket_id=ticket.id,
        stage="prepare_payload",
        status="success",
        message="payload prepared",
        payload={"executionType": ticket.executionType},
    )

    try:
        _log_execution_ticket_stage(db, ticket_id=ticket.id, stage="execute_action", status="started", message="run executor")
        result = executor(proposal, ticket)
        _log_execution_ticket_stage(db, ticket_id=ticket.id, stage="execute_action", status="success", message="executor success")
        db.execute(
            """
            UPDATE execution_tickets
            SET status = 'executed',
                result_json = ?,
                last_error = NULL,
                error_message = NULL,
                executed_at = ?,
                last_attempt_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (to_json(result), _now_iso(), started_at, _now_iso(), ticket.id),
        )
        _log_execution_ticket_stage(
            db,
            ticket_id=ticket.id,
            stage="write_result",
            status="success",
            message="execution result written",
        )
        db.execute(
            """
            UPDATE proposal_records
            SET status = 'executed',
                execution_ticket_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (ticket.id, _now_iso(), proposal.id),
        )
        _log_execution_ticket_stage(
            db,
            ticket_id=ticket.id,
            stage="update_proposal_status",
            status="success",
            message="proposal set executed",
        )
    except Exception as exc:
        error_text = str(exc)
        db.execute(
            """
            UPDATE execution_tickets
            SET status = 'failed',
                result_json = ?,
                last_error = ?,
                error_message = ?,
                last_attempt_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                to_json(
                    {
                        "resultType": "failed",
                        "summary": error_text,
                        "createdTaskIds": [],
                        "artifactRefs": [],
                    }
                ),
                error_text,
                error_text,
                started_at,
                _now_iso(),
                ticket.id,
            ),
        )
        _log_execution_ticket_stage(
            db,
            ticket_id=ticket.id,
            stage="write_result",
            status="failed",
            message=error_text,
        )
        db.execute(
            """
            UPDATE proposal_records
            SET status = 'failed',
                execution_ticket_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (ticket.id, _now_iso(), proposal.id),
        )
        _log_execution_ticket_stage(
            db,
            ticket_id=ticket.id,
            stage="update_proposal_status",
            status="failed",
            message="proposal set failed",
        )
    return get_execution_ticket(db, ticket_id=ticket.id)


def retry_execution_ticket(
    db: Database,
    *,
    ticket_id: str,
    requested_by: str = "user",
) -> ExecutionTicketRecord:
    ticket = get_execution_ticket(db, ticket_id=ticket_id)
    if ticket.status != "failed":
        raise ValueError("execution_ticket_not_retryable")
    if int(ticket.retryCount or 0) >= int(ticket.maxRetries or 3):
        raise ValueError("execution_ticket_retry_exceeded")
    proposal = get_proposal_record(db, proposal_id=ticket.proposalId)
    now = _now_iso()
    db.execute(
        """
        UPDATE execution_tickets
        SET status = 'pending',
            retry_count = ?,
            last_error = NULL,
            error_message = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (int(ticket.retryCount or 0) + 1, now, ticket.id),
    )
    db.execute(
        """
        UPDATE proposal_records
        SET status = 'execution_pending',
            updated_at = ?
        WHERE id = ?
        """,
        (now, proposal.id),
    )
    _log_execution_ticket_stage(
        db,
        ticket_id=ticket.id,
        stage="retry",
        status="success",
        message=f"retry requested by {(requested_by or 'user').strip() or 'user'}",
        payload={"retryCount": int(ticket.retryCount or 0) + 1},
    )
    return get_execution_ticket(db, ticket_id=ticket.id)


def list_execution_ticket_logs(
    db: Database,
    *,
    ticket_id: str,
    limit: int = 200,
) -> list[ExecutionTicketLogRecord]:
    rows = db.fetchall(
        """
        SELECT *
        FROM execution_ticket_logs
        WHERE ticket_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (ticket_id, int(limit)),
    )
    records: list[ExecutionTicketLogRecord] = []
    for row in rows:
        payload = from_json(str(row["payload_json"] or "{}"), {})
        records.append(
            ExecutionTicketLogRecord(
                id=str(row["id"]),
                ticketId=str(row["ticket_id"]),
                stage=str(row["stage"]),  # type: ignore[arg-type]
                status=str(row["status"]),  # type: ignore[arg-type]
                message=str(row["message"] or ""),
                payload=payload if isinstance(payload, dict) else {},
                createdAt=str(row["created_at"]),
            )
        )
    return records


def list_execution_tickets(
    db: Database,
    *,
    client_id: str | None = None,
    status: str | None = None,
    limit: int = 60,
) -> list[ExecutionTicketRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if client_id:
        clauses.append("client_id = ?")
        params.append(client_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.fetchall(
        f"SELECT * FROM execution_tickets {where_clause} ORDER BY updated_at DESC, created_at DESC LIMIT ?",
        (*params, int(limit)),
    )
    return [_execution_ticket_row_to_record(row) for row in rows]

