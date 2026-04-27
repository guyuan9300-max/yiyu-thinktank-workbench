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


def create_client_record(client: TestClient, name: str = "proposal-draft-persistence") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal draft persistence",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_proposal_draft_persistence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db
    before_proposals = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    before_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)

    response = client.post(
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
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload["persistedProposalDraftIds"], list)
    assert len(payload["persistedProposalDraftIds"]) >= 1

    listed = client.get(
        "/api/v1/data-center/proposal-drafts",
        params={"clientId": client_id, "limit": 100},
    )
    assert listed.status_code == 200, listed.text
    records = listed.json()
    persisted_ids = set(payload["persistedProposalDraftIds"])
    assert any(str(item.get("id") or "") in persisted_ids for item in records)

    after_proposals = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    after_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    assert after_proposals == before_proposals
    assert after_tickets == before_tickets
