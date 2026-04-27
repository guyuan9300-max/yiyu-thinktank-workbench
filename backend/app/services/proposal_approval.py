from __future__ import annotations

from datetime import datetime

from app.db import Database, from_json
from app.models import (
    ExecutionArtifactRefRecord,
    ExecutionTicketRecord,
    ExecutionTicketResultRecord,
    ProposalApprovalResultRecord,
    ProposalExecutionPreviewRecord,
    ProposalRecordRecord,
    ProposalTargetRefRecord,
)
from app.services.knowledge_v2 import new_id


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _execution_ticket_row_to_record(row) -> ExecutionTicketRecord:
    payload_data = from_json(row["payload_json"], {})
    result_data = from_json(row["result_json"], {})
    if not isinstance(result_data, dict):
        result_data = {}
    artifact_refs_data = result_data.get("artifactRefs", [])
    artifact_refs = [
        ExecutionArtifactRefRecord(
            artifactType=str(item.get("artifactType") or ""),
            refId=str(item.get("refId") or ""),
            title=str(item.get("title") or ""),
        )
        for item in artifact_refs_data
        if isinstance(item, dict)
    ] if isinstance(artifact_refs_data, list) else []
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
        ] if isinstance(result_data.get("createdTaskIds"), list) else [],
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


def _proposal_row_to_record(db: Database, row) -> ProposalRecordRecord:
    target_refs_data = from_json(row["target_refs_json"], [])
    target_refs = [ProposalTargetRefRecord(**item) for item in target_refs_data] if isinstance(target_refs_data, list) else []
    source_refs_data = from_json(row["source_refs_json"], [])
    boundary_notes_data = from_json(row["boundary_notes_json"], [])
    payload_data = from_json(row["payload_json"], {})
    execution_ticket = None
    if row["execution_ticket_id"]:
        ticket_row = db.fetchone("SELECT * FROM execution_tickets WHERE id = ?", (str(row["execution_ticket_id"]),))
        if ticket_row:
            execution_ticket = _execution_ticket_row_to_record(ticket_row)
    return ProposalRecordRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        status=str(row["status"]),  # type: ignore[arg-type]
        riskLevel=str(row["risk_level"] or "medium"),  # type: ignore[arg-type]
        title=str(row["title"]),
        summary=str(row["summary"] or ""),
        rationale=str(row["rationale"] or ""),
        targetRefs=target_refs,
        sourceRefs=[str(item).strip() for item in source_refs_data if str(item).strip()] if isinstance(source_refs_data, list) else [],
        boundaryNotes=[str(item).strip() for item in boundary_notes_data if str(item).strip()] if isinstance(boundary_notes_data, list) else [],
        payload=payload_data if isinstance(payload_data, dict) else {},
        createdBy=str(row["created_by"] or ""),
        decidedBy=str(row["decided_by"]) if row["decided_by"] else None,
        decidedAt=str(row["decided_at"]) if row["decided_at"] else None,
        rejectedReason=str(row["rejected_reason"]) if row["rejected_reason"] else None,
        executionTicketId=str(row["execution_ticket_id"]) if row["execution_ticket_id"] else None,
        executionTicket=execution_ticket,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def get_proposal_record(
    db: Database,
    *,
    proposal_id: str,
) -> ProposalRecordRecord:
    row = db.fetchone("SELECT * FROM proposal_records WHERE id = ?", (proposal_id,))
    if not row:
        raise KeyError("proposal_not_found")
    return _proposal_row_to_record(db, row)


def list_proposal_records(
    db: Database,
    *,
    client_id: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> list[ProposalRecordRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if client_id:
        clauses.append("client_id = ?")
        params.append(client_id)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.fetchall(
        f"SELECT * FROM proposal_records {where_clause} ORDER BY updated_at DESC, created_at DESC LIMIT ?",
        (*params, int(limit)),
    )
    return [_proposal_row_to_record(db, row) for row in rows]


def build_execution_preview_for_proposal(
    db: Database,
    *,
    proposal: ProposalRecordRecord,
) -> ProposalExecutionPreviewRecord:
    del db
    target_types = {item.targetType for item in proposal.targetRefs}
    kind = proposal.kind
    return ProposalExecutionPreviewRecord(
        proposalId=proposal.id,
        executionType=kind,
        riskLevel=proposal.riskLevel,
        willCreateTask=kind in {"meeting_followup", "evidence_request", "judgment_review", "context_refresh", "task_prep"},
        willCreatePrepArtifact=kind in {"task_prep", "meeting_prep"},
        willCreateEvidenceRequest=kind == "evidence_request",
        willUpdateEventLine=("event_line" in target_types and kind == "meeting_followup"),
        summary=(
            "审批后可创建 execution ticket；执行阶段会按 proposal kind 生成任务/准备包/事件线活动。"
        ),
        warnings=[
            "执行动作仍需人工触发，不会自动执行。",
            "不会自动写入 approved judgment。",
        ],
    )


def approve_proposal_record(
    db: Database,
    *,
    proposal_id: str,
    decided_by: str,
    note: str = "",
) -> ProposalApprovalResultRecord:
    proposal = get_proposal_record(db, proposal_id=proposal_id)
    if proposal.status != "pending_review":
        raise ValueError("proposal_not_approvable")
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE proposal_records
        SET status = 'approved',
            decided_by = ?,
            decided_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        ((decided_by or "user").strip() or "user", timestamp, timestamp, proposal_id),
    )
    updated = get_proposal_record(db, proposal_id=proposal_id)
    preview = build_execution_preview_for_proposal(db, proposal=updated)
    if note.strip():
        db.execute(
            """
            INSERT INTO approval_records(
                id, object_type, object_id, client_id, status, note, actor_id, actor_name, created_at,
                approval_target_type, approval_target_id, policy_type, decision, comment, decided_by, decided_at, metadata_json
            )
            VALUES(?, 'proposal_record', ?, ?, 'completed', ?, ?, ?, ?, 'proposal_record', ?, 'proposal_review', 'approved', ?, ?, ?, '{}')
            """,
            (
                new_id("apr"),
                proposal_id,
                updated.clientId,
                note,
                decided_by or "user",
                decided_by or "user",
                timestamp,
                proposal_id,
                note,
                decided_by or "user",
                timestamp,
            ),
        )
    return ProposalApprovalResultRecord(proposal=updated, executionPreview=preview)


def reject_proposal_record(
    db: Database,
    *,
    proposal_id: str,
    decided_by: str,
    reason: str = "",
) -> ProposalRecordRecord:
    proposal = get_proposal_record(db, proposal_id=proposal_id)
    if proposal.status not in {"pending_review", "approved"}:
        raise ValueError("proposal_not_rejectable")
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE proposal_records
        SET status = 'rejected',
            rejected_reason = ?,
            decided_by = ?,
            decided_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            (reason or "人工驳回").strip(),
            (decided_by or "user").strip() or "user",
            timestamp,
            timestamp,
            proposal_id,
        ),
    )
    return get_proposal_record(db, proposal_id=proposal_id)
