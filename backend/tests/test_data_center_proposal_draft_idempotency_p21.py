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


def create_client_record(client: TestClient, name: str = "proposal-draft-idempotency") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal draft idempotency",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_proposal_draft_idempotency(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    payload = {
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
    }
    first = client.post("/api/v1/data-center/resolve", json=payload)
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert len(first_payload["persistedProposalDraftIds"]) >= 1

    count_after_first = int(db.scalar("SELECT COUNT(1) AS count FROM data_center_proposal_drafts") or 0)

    second = client.post("/api/v1/data-center/resolve", json=payload)
    assert second.status_code == 200, second.text
    second_payload = second.json()
    assert len(second_payload["persistedProposalDraftIds"]) == 0
    assert len(second_payload["dedupedDraftIds"]) >= 1

    count_after_second = int(db.scalar("SELECT COUNT(1) AS count FROM data_center_proposal_drafts") or 0)
    assert count_after_second == count_after_first
