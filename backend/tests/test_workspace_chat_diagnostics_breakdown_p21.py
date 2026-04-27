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


def create_client_record(client: TestClient, name: str = "diagnostics-breakdown") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "diagnostics breakdown",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_diagnostics_breakdown(tmp_path: Path, monkeypatch):
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

    reply = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请介绍一下这个客户"},
    )
    assert reply.status_code == 200, reply.text
    message = reply.json()

    db = client.app.state.app_state.db
    db.execute(
        """
        UPDATE chat_messages
        SET answer_mode = 'grounded_fallback',
            failure_reason = 'llm_read_timeout',
            timing_json = ?,
            retrieval_summary_json = ?,
            evidence_json = ?
        WHERE id = ?
        """,
        (
            to_json({"retrievalMs": 180.0, "llmMs": 2100.0, "totalMs": 2400.0}),
            to_json(
                {
                    "answerIntent": "general",
                    "pageContextQuality": "weak",
                    "rawChunkHitCount": 1,
                    "selectedEvidenceCount": 0,
                    "generationPolicy": {
                        "shouldUseCompactFirst": True,
                        "shouldUseLocalOnly": False,
                    },
                }
            ),
            to_json([{"title": "模板.pptx", "path": "/tmp/模板.pptx", "sourceType": "draft", "excerpt": "短"}]),
            message["id"],
        ),
    )

    diagnostics = client.get(
        "/api/v1/runtime/workspace-chat-diagnostics",
        params={"clientId": client_id, "recentMessages": 20},
    )
    assert diagnostics.status_code == 200, diagnostics.text
    payload = diagnostics.json()
    assert "breakdown" in payload
    for key in ("generation", "retrieval", "evidenceQuality", "dataIntegrity", "intent"):
        assert key in payload["breakdown"]
        assert payload["breakdown"][key]["status"] in {"ok", "warning", "critical"}
        assert isinstance(payload["breakdown"][key]["details"], dict)
