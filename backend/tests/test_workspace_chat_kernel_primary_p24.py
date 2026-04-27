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


def create_client_record(client: TestClient, name: str = "kernel-primary-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel primary p24",
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


def test_workspace_chat_kernel_primary_dual_switch_and_allowlist(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", lambda *_args, **_kwargs: _mock_answer())

    # workspace switch on, but retrieval setting switch off -> kernel primary disabled
    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "1")
    disable_kernel = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": False, "chatKernelPrimaryClientAllowlist": [client_id]},
    )
    assert disable_kernel.status_code == 200, disable_kernel.text
    disabled = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert disabled.status_code == 200, disabled.text
    disabled_summary = disabled.json().get("retrievalSummary") or {}
    assert disabled_summary.get("kernelPrimaryUsed") is False

    # retrieval switch on but allowlist mismatch -> disabled
    mismatch = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": ["other_client"]},
    )
    assert mismatch.status_code == 200, mismatch.text
    mismatch_resp = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert mismatch_resp.status_code == 200, mismatch_resp.text
    mismatch_summary = mismatch_resp.json().get("retrievalSummary") or {}
    assert mismatch_summary.get("kernelPrimaryUsed") is False

    # dual-switch + allowlist hit -> kernel primary enabled
    enabled_setting = client.post(
        "/api/v1/retrieval/settings",
        json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": [client_id]},
    )
    assert enabled_setting.status_code == 200, enabled_setting.text
    enabled_resp = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert enabled_resp.status_code == 200, enabled_resp.text
    enabled_summary = enabled_resp.json().get("retrievalSummary") or {}
    assert enabled_summary.get("kernelPrimaryUsed") is True
    assert enabled_summary.get("kernelPrimaryFallbackUsed") is False
    assert isinstance(enabled_summary.get("kernelRouteIntent"), str)
    assert isinstance(enabled_summary.get("kernelAnswerPlanIntent"), str)
    assert isinstance(enabled_summary.get("kernelSelectedEvidenceCount"), int)
    consistency = enabled_summary.get("kernelConsistency") or {}
    assert consistency.get("legacyFallbackUsed") is False
    assert isinstance(consistency.get("selectedEvidenceOverlap"), (int, float))
