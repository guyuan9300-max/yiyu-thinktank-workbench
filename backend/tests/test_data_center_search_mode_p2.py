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


def create_client_record(client: TestClient, name: str = "search-mode-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "search mode p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_search_mode_does_not_require_llm(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("llm_should_not_be_called_in_search_mode")),
    )

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "CFFC 核心业务是什么？",
            "mode": "search",
            "includeRawEvidence": False,
            "includeActionSuggestions": False,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["searchResult"] is not None
    assert payload["searchResult"]["routeDecision"]["intent"] == "business_profile"
    assert "selectedHits" in payload["searchResult"]
