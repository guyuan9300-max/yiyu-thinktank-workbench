from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "proposal-approval-p23") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal approval p23",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_proposal(
    client: TestClient,
    *,
    proposal_id: str,
    client_id: str,
    status: str = "pending_review",
    kind: str = "meeting_followup",
) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'medium', ?, ?, ?, ?, '[]', '[]', '{}', 'tester', NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            kind,
            status,
            f"{kind} title",
            f"{kind} summary",
            f"{kind} rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            now,
            now,
        ),
    )


def test_proposal_approval_flow_and_state_guard(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    insert_proposal(client, proposal_id="proposal_p23_pending", client_id=client_id, status="pending_review", kind="meeting_followup")
    insert_proposal(client, proposal_id="proposal_p23_rejected", client_id=client_id, status="rejected", kind="evidence_request")

    before_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)

    approve = client.post(
        "/api/v1/proposals/proposal_p23_pending/approve",
        json={"decidedBy": "tester", "note": "人工批准"},
    )
    assert approve.status_code == 200, approve.text
    approved = approve.json()
    assert approved["status"] == "approved"
    assert approved["decidedBy"] == "tester"
    assert approved.get("executionTicketId") in {None, ""}

    preview = client.get("/api/v1/proposals/proposal_p23_pending/execution-preview")
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["proposalId"] == "proposal_p23_pending"
    assert preview_payload["executionType"] == "meeting_followup"
    assert preview_payload["willCreateTask"] is True

    reject = client.post(
        "/api/v1/proposals/proposal_p23_pending/reject",
        json={"decidedBy": "tester", "note": "回退驳回"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

    approve_rejected = client.post(
        "/api/v1/proposals/proposal_p23_pending/approve",
        json={"decidedBy": "tester", "note": "不应允许"},
    )
    assert approve_rejected.status_code == 409, approve_rejected.text

    after_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    assert after_tickets == before_tickets
