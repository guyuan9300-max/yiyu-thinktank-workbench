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


def create_client_record(client: TestClient, name: str = "execution-ticket-logs-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "execution ticket logs p24",
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
        VALUES(?, ?, 'meeting_followup', 'approved', 'medium', ?, ?, ?, ?, '[]', '[]', ?, 'tester', 'tester', ?, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            "meeting followup title",
            "meeting followup summary",
            "meeting followup rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            to_json(
                {
                    "meetingId": "meeting_p24_logs",
                    "actionItems": [{"id": "act_1", "title": "补材料", "summary": "补齐会议材料"}],
                }
            ),
            now,
            now,
            now,
        ),
    )


def test_execution_ticket_logs_api_returns_stage_logs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    proposal_id = "proposal_exec_logs"
    insert_approved_proposal(client, proposal_id=proposal_id, client_id=client_id)

    created = client.post(
        f"/api/v1/proposals/{proposal_id}/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("executionTicket") or {}).get("id")
    assert isinstance(ticket_id, str) and ticket_id

    executed = client.post(
        f"/api/v1/execution-tickets/{ticket_id}/execute",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert executed.status_code == 200, executed.text
    assert (executed.json().get("executionTicket") or {}).get("status") == "executed"

    logs_resp = client.get(f"/api/v1/execution-tickets/{ticket_id}/logs?limit=120")
    assert logs_resp.status_code == 200, logs_resp.text
    logs = logs_resp.json()
    assert isinstance(logs, list)
    assert logs
    stages = {str(item.get("stage")) for item in logs}
    assert "validate" in stages
    assert "execute_action" in stages
    assert "write_result" in stages
