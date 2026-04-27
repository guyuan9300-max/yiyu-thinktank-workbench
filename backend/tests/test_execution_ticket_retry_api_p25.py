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


def create_client_record(client: TestClient, name: str = "execution-ticket-retry-api-p25") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "execution ticket retry api p25",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_approved_proposal(client: TestClient, *, proposal_id: str, client_id: str) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, 'task_prep', 'approved', 'medium', ?, ?, ?, ?, '[]', '[]', '{}', 'tester', 'tester', ?, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            "task prep title",
            "task prep summary",
            "task prep rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            now,
            now,
            now,
        ),
    )


def test_execution_ticket_retry_api_p25(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    proposal_id = "proposal_exec_retry_api_p25"
    insert_approved_proposal(client, proposal_id=proposal_id, client_id=client_id)
    db = client.app.state.app_state.db

    created = client.post(
        f"/api/v1/proposals/{proposal_id}/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("executionTicket") or {}).get("id")
    assert isinstance(ticket_id, str) and ticket_id

    not_retryable = client.post(
        f"/api/v1/execution-tickets/{ticket_id}/retry",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert not_retryable.status_code == 409, not_retryable.text

    now = datetime.now().replace(microsecond=0).isoformat()
    db.execute(
        "UPDATE execution_tickets SET status = 'failed', retry_count = 0, max_retries = 3, updated_at = ? WHERE id = ?",
        (now, ticket_id),
    )
    db.execute(
        "UPDATE proposal_records SET status = 'failed', updated_at = ? WHERE id = ?",
        (now, proposal_id),
    )
    retry_ok = client.post(
        f"/api/v1/execution-tickets/{ticket_id}/retry",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert retry_ok.status_code == 200, retry_ok.text
    payload = retry_ok.json()
    assert (payload.get("executionTicket") or {}).get("status") == "pending"
