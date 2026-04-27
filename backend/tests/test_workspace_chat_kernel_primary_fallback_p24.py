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


def create_client_record(client: TestClient, name: str = "kernel-primary-fallback-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel primary fallback p24",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_kernel_primary_fallback_meta(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "1")
    client.app.state.app_state.db.set_setting("workspace_chat_use_legacy_fallback", "1")
    setting = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": [client_id]},
    )
    assert setting.status_code == 200, setting.text

    def _raise_error(*_args, **_kwargs):
        raise AiInvocationError("mock", "read timeout")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", _raise_error)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请总结当前客户关键信息"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}
    assert retrieval_summary.get("kernelPrimaryUsed") is True
    assert retrieval_summary.get("kernelPrimaryFallbackUsed") is True
    assert retrieval_summary.get("kernelPrimaryFallbackReason") in {
        "legacy_template_fallback",
        "llm_generation_failed",
        "llm_partial_preserved_after_retry",
    }
    consistency = retrieval_summary.get("kernelConsistency") or {}
    assert consistency.get("legacyFallbackUsed") is True
    assert "RouteDecision" not in str(payload.get("content") or "")
