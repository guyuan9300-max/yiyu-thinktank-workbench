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


def create_client_record(client: TestClient, name: str = "ops-panel-batch-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "ops panel batch contract p24",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_pending_proposal(client: TestClient, *, proposal_id: str, client_id: str) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, 'meeting_followup', 'pending_review', 'medium', ?, ?, ?, ?, '[]', '[]', '{}', 'tester', NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            f"{proposal_id} title",
            f"{proposal_id} summary",
            f"{proposal_id} rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            now,
            now,
        ),
    )


def test_data_center_ops_panel_batch_contract_p24(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"
    api_path = repo_root / "src" / "renderer" / "lib" / "api.ts"

    assert panel_path.exists()
    panel_text = panel_path.read_text(encoding="utf-8")
    api_text = api_path.read_text(encoding="utf-8")

    assert "batchApproveProposals" in panel_text
    assert "batchRejectProposals" in panel_text
    assert "retryExecutionTicket" in panel_text
    assert "getExecutionTicketLogs" in panel_text
    assert "确认执行" in panel_text

    assert "batchApproveProposals(" in api_text
    assert "batchRejectProposals(" in api_text
    assert "retryExecutionTicket(" in api_text
    assert "getExecutionTicketLogs(" in api_text

    client = make_client(tmp_path)
    client_id = create_client_record(client)
    ids = ["proposal_batch_1", "proposal_batch_2", "proposal_batch_3"]
    for proposal_id in ids:
        insert_pending_proposal(client, proposal_id=proposal_id, client_id=client_id)

    approved = client.post(
        "/api/v1/proposals/batch-approve",
        json={"proposalIds": ids, "decidedBy": "tester", "note": "batch approve"},
    )
    assert approved.status_code == 200, approved.text
    approved_payload = approved.json()
    assert approved_payload["total"] == 3
    assert approved_payload["succeeded"] == 3
    assert approved_payload["failed"] == 0

    rejected = client.post(
        "/api/v1/proposals/batch-reject",
        json={"proposalIds": ids, "decidedBy": "tester", "note": "batch reject"},
    )
    assert rejected.status_code == 200, rejected.text
    rejected_payload = rejected.json()
    assert rejected_payload["total"] == 3
    assert rejected_payload["succeeded"] == 3
    assert rejected_payload["failed"] == 0
