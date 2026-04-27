from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import AiStructuredResponse


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "mobile-snapshot-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "mobile snapshot p24",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _mock_answer() -> AiStructuredResponse:
    return AiStructuredResponse(
        content="mock",
        judgment="mock",
        analysis="mock",
        actions="mock",
        timeline="mock",
    )


def test_mobile_snapshot_contains_data_center_summaries(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    llm_called = {"count": 0}

    def _counted(*_args, **_kwargs):
        llm_called["count"] += 1
        return _mock_answer()

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", _counted)

    response = client.get(f"/api/v1/clients/{client_id}/data-center/mobile-snapshot")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("clientId") == client_id
    assert isinstance(payload.get("proposalDraftSummary"), dict)
    assert isinstance(payload.get("openProposalSummary"), dict)
    assert isinstance(payload.get("latestExecutionTickets"), list)
    assert isinstance(payload.get("evidenceQualitySummary"), dict)
    assert payload.get("kernelReadiness") in {"ready", "partial", "weak"}
    assert llm_called["count"] == 0
