from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.ai import AiInvocationError


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_llm_healthcheck_classifies_ssl_handshake_timeout(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)

    def _raise(*_args, **_kwargs):
        raise AiInvocationError("doubao", "_ssl.c:999 The handshake operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "_qwen_generate", _raise)

    response = client.post("/api/v1/runtime/llm-healthcheck", json={"provider": "doubao"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["errorKind"] == "ssl_handshake_timeout"


def test_llm_provider_probe_returns_multiple_results(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "healthcheck",
        lambda **kwargs: {
            "provider": kwargs.get("provider") or "doubao",
            "model": "test-model",
            "success": True,
            "latencyMs": 12,
            "error": None,
            "errorKind": None,
        },
    )

    response = client.post(
        "/api/v1/runtime/llm-provider-probe",
        json={"clientId": None, "providers": ["doubao", "qwen"], "prompt": "ping"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["prompt"] == "ping"
    assert len(payload["results"]) == 2
