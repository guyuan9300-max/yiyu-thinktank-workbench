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


def create_client_record(client: TestClient, name: str = "proposal-mode-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal mode p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_proposal_mode_returns_drafts_only(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    before = client.app.state.app_state.db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "当前还缺什么材料？",
            "mode": "proposal",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["proposalDrafts"] is not None
    assert isinstance(payload["proposalDrafts"], list)

    after = client.app.state.app_state.db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0
    assert after == before
