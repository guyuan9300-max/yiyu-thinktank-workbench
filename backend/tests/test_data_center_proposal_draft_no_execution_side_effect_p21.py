from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "proposal-draft-side-effect") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal draft side effect",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_proposal_draft_no_execution_side_effect(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    proposal_records_before = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    tickets_before = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)

    created = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "还缺哪些关键资料？",
            "mode": "proposal",
            "includeActionSuggestions": True,
            "shadow": True,
            "persistDrafts": True,
        },
    )
    assert created.status_code == 200, created.text
    created_payload = created.json()
    assert len(created_payload["persistedProposalDraftIds"]) >= 1
    draft_id = created_payload["persistedProposalDraftIds"][0]

    reviewed = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/mark-reviewed",
        json={"note": "已人工查看"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "reviewed"

    rejected = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/reject",
        json={"reason": "暂不推进"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    proposal_records_after = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    tickets_after = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    assert proposal_records_after == proposal_records_before
    assert tickets_after == tickets_before
