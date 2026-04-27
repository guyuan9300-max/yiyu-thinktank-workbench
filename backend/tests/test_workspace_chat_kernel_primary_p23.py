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


def create_client_record(client: TestClient, name: str = "kernel-primary-p23") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel primary p23",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _mock_answer() -> AiStructuredResponse:
    return AiStructuredResponse(
        content="基于当前资料，核心业务聚焦资源支持与项目服务。",
        judgment="结论稳定",
        analysis="证据已覆盖核心业务相关表达。",
        actions="补充服务对象与交付方式证据。",
        timeline="本周完成证据补齐。",
    )


def test_workspace_chat_kernel_primary_toggle(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "0")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", lambda *_args, **_kwargs: _mock_answer())

    baseline = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert baseline.status_code == 200, baseline.text
    baseline_summary = baseline.json().get("retrievalSummary") or {}
    assert baseline_summary.get("kernelResultUsed") is True
    assert baseline_summary.get("kernelPrimaryUsed") is False

    setting = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": [client_id]},
    )
    assert setting.status_code == 200, setting.text
    assert setting.json().get("chatKernelPrimaryEnabled") is True
    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "1")

    enabled = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert enabled.status_code == 200, enabled.text
    enabled_summary = enabled.json().get("retrievalSummary") or {}
    assert enabled_summary.get("kernelPrimaryUsed") is True
    consistency = enabled_summary.get("kernelConsistency") or {}
    assert isinstance(consistency.get("routeIntentMatched"), bool)
    assert isinstance(consistency.get("answerPlanMatched"), bool)
    assert isinstance(consistency.get("selectedEvidenceOverlap"), (int, float))
