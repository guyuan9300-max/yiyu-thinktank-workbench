from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import AiStructuredResponse
from app.db import to_json


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "diagnostics-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "diagnostics p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_diagnostics_endpoint(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="回答",
            judgment="j",
            analysis="a",
            actions="act",
            timeline="t",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请给我一个摘要"},
    )
    assert response.status_code == 200, response.text
    message = response.json()

    db = client.app.state.app_state.db
    db.execute(
        """
        UPDATE chat_messages
        SET answer_mode = 'grounded_fallback', failure_reason = 'llm_read_timeout',
            timing_json = ?, retrieval_summary_json = ?
        WHERE id = ?
        """,
        (
            to_json({"retrievalMs": 120.0, "llmMs": 1800.0, "totalMs": 2100.0}),
            to_json({"answerIntent": "business_profile", "pageContextQuality": "usable"}),
            message["id"],
        ),
    )

    diag = client.get(
        "/api/v1/runtime/workspace-chat-diagnostics",
        params={"clientId": client_id, "recentMessages": 20},
    )
    assert diag.status_code == 200, diag.text
    payload = diag.json()

    assert payload["clientId"] == client_id
    assert payload["groundedFallbackRate"] >= 0
    assert payload["llmTimeoutRate"] >= 0
    assert "sourceIntegrityMatch" in payload
    assert "runningBuildVersion" in payload
    assert "fallbackTemplateUsedRate" in payload
    assert "dataCenterPrimaryEnabledRate" in payload
    assert "materialQuality" in payload
    assert "dataCenterQuality" in payload
