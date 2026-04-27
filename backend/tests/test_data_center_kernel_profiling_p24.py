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


def create_client_record(client: TestClient, name: str = "kernel-profiling-p24") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel profiling p24",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _mock_answer() -> AiStructuredResponse:
    return AiStructuredResponse(
        content="这是一个测试回答。",
        judgment="ok",
        analysis="ok",
        actions="ok",
        timeline="ok",
    )


def test_data_center_kernel_diagnostic_contains_profiling_and_search_no_llm(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    llm_called = {"count": 0}

    def _counted(*_args, **_kwargs):
        llm_called["count"] += 1
        return _mock_answer()

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", _counted)

    search = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "mode": "search",
            "prompt": "查找核心业务相关资料",
            "shadow": True,
        },
    )
    assert search.status_code == 200, search.text
    assert llm_called["count"] == 0

    diagnostic = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "mode": "diagnostic",
            "prompt": "诊断当前链路",
            "shadow": True,
        },
    )
    assert diagnostic.status_code == 200, diagnostic.text
    debug = diagnostic.json().get("debug") or {}
    profiling = debug.get("profiling") or {}
    assert isinstance(profiling.get("totalMs"), (int, float))
    assert isinstance(profiling.get("routeMs"), (int, float))
    assert isinstance(profiling.get("answerChainMs"), (int, float))
