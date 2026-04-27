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


def create_client_record(client: TestClient, name: str = "proposal-exec-ticket-p23") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal execution ticket p23",
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
    status: str,
    kind: str,
) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    payload = {
        "meetingId": "meeting_x",
        "actionItems": [{"id": "act_1", "title": "补齐证据", "summary": "补齐核心证据材料"}],
    }
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'medium', ?, ?, ?, ?, '[]', '[]', ?, 'tester', NULL, NULL, NULL, NULL, ?, ?)
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
            to_json(payload),
            now,
            now,
        ),
    )


def test_execution_ticket_create_execute_and_dry_run(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    insert_proposal(
        client,
        proposal_id="proposal_exec_ready",
        client_id=client_id,
        status="approved",
        kind="evidence_request",
    )
    insert_proposal(
        client,
        proposal_id="proposal_exec_pending",
        client_id=client_id,
        status="pending_review",
        kind="meeting_followup",
    )

    before_ticket_count = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    before_task_count = int(db.scalar("SELECT COUNT(1) AS count FROM tasks") or 0)

    dry_run = client.post(
        "/api/v1/proposals/proposal_exec_ready/execution-ticket",
        json={"requestedBy": "tester", "dryRun": True},
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["executionTicket"] is None
    ticket_count_after_dry_run = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    assert ticket_count_after_dry_run == before_ticket_count

    create_ticket = client.post(
        "/api/v1/proposals/proposal_exec_ready/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert create_ticket.status_code == 200, create_ticket.text
    created_payload = create_ticket.json()
    ticket = created_payload["executionTicket"]
    assert ticket is not None
    assert ticket["status"] == "pending"
    assert created_payload["proposal"]["status"] == "execution_pending"

    execute = client.post(
        f"/api/v1/execution-tickets/{ticket['id']}/execute",
        json={"requestedBy": "tester"},
    )
    assert execute.status_code == 200, execute.text
    execute_payload = execute.json()
    executed_ticket = execute_payload.get("executionTicket") or {}
    assert executed_ticket.get("status") == "executed"
    result = executed_ticket.get("result") or {}
    assert isinstance(result.get("createdTaskIds"), list)
    assert result.get("createdTaskIds")
    assert execute_payload["proposal"]["status"] == "executed"

    after_task_count = int(db.scalar("SELECT COUNT(1) AS count FROM tasks") or 0)
    assert after_task_count >= before_task_count + 1

    invalid = client.post(
        "/api/v1/proposals/proposal_exec_pending/execution-ticket",
        json={"requestedBy": "tester"},
    )
    assert invalid.status_code == 409, invalid.text

