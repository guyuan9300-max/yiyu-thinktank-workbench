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


def create_client_record(client: TestClient, name: str = "kernel-consistency-p22") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel consistency p22",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_reports_kernel_consistency(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="基于当前资料，核心业务以资源支持与项目服务为主。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    retrieval_summary = payload.get("retrievalSummary") or {}
    assert retrieval_summary.get("kernelResultUsed") is True
    assert isinstance(retrieval_summary.get("kernelRouteIntent"), str)
    assert isinstance(retrieval_summary.get("kernelAnswerPlanIntent"), str)
    assert isinstance(retrieval_summary.get("chatAnswerPlanIntent"), str)

    consistency = retrieval_summary.get("kernelConsistency") or {}
    assert consistency.get("routeIntentMatched") is True
    assert consistency.get("answerPlanMatched") is True
    assert retrieval_summary.get("chatAnswerPlanIntent") == "business_profile"
