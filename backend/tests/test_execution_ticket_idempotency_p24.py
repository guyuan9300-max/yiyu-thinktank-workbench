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


def create_client_record(client: TestClient, name: str = "execution-ticket-idempotency-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "execution ticket idempotency p24",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_approved_proposal(client: TestClient, *, proposal_id: str, client_id: str, kind: str = "evidence_request") -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, ?, 'approved', 'medium', ?, ?, ?, ?, '[]', '[]', '{}', 'tester', 'tester', ?, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            kind,
            f"{kind} title",
            f"{kind} summary",
            f"{kind} rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            now,
            now,
            now,
        ),
    )


def test_execution_ticket_create_is_idempotent(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    insert_approved_proposal(client, proposal_id="proposal_exec_idempotent", client_id=client_id)
    db = client.app.state.app_state.db

    first = client.post(
        "/api/v1/proposals/proposal_exec_idempotent/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert first.status_code == 200, first.text
    first_ticket = (first.json().get("executionTicket") or {}).get("id")
    assert isinstance(first_ticket, str) and first_ticket

    second = client.post(
        "/api/v1/proposals/proposal_exec_idempotent/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert second.status_code == 200, second.text
    second_ticket = (second.json().get("executionTicket") or {}).get("id")
    assert second_ticket == first_ticket

    ticket_count = int(
        db.scalar(
            "SELECT COUNT(1) AS count FROM execution_tickets WHERE proposal_id = ?",
            ("proposal_exec_idempotent",),
        )
        or 0
    )
    assert ticket_count == 1
