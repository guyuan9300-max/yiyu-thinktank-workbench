from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import DEFAULT_ORG_ID, create_app, now_iso  # noqa: E402


def _set_seed_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@yiyu-system.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _insert_empty_client(
    app,
    client_id: str = "client_empty_mobile_contract",
    client_name: str = "空白测试客户",
) -> tuple[str, str]:
    timestamp = now_iso()
    app.state.app_state.db.execute(
        """
        INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at)
        VALUES(?, ?, ?, NULL, ?, ?)
        """,
        (client_id, DEFAULT_ORG_ID, client_name, timestamp, timestamp),
    )
    return client_id, client_name


def test_mobile_capabilities_and_openapi_contract(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    client = TestClient(create_app())
    headers = _auth_headers(client)

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200, openapi.text
    paths = openapi.json()["paths"]
    assert "/api/v1/mobile/capabilities" in paths
    assert "/api/v1/clients/{client_id}/workspace" in paths
    assert "/api/v1/clients/{client_id}/strategic-cockpit" in paths

    chat_payload_fields = openapi.json()["components"]["schemas"]["ConsultationChatPayload"]["properties"]
    chat_response_fields = openapi.json()["components"]["schemas"]["ConsultationChatResponse"]["properties"]
    assert "workspaceContext" in chat_payload_fields
    assert "taskBoardContext" in chat_payload_fields
    assert "answerMode" in chat_response_fields
    assert "contextQuality" in chat_response_fields
    assert "reply" in chat_response_fields

    capabilities = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    body = capabilities.json()
    assert body["consultationChat"] is True
    assert body["clientWorkspace"] is True
    assert body["strategicCockpit"] is True
    assert body["consultationPayloadVersion"] == "v2"


def test_workspace_and_cockpit_return_structured_missing_for_valid_client(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    app = create_app()
    client_id, _ = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    workspace_body = workspace.json()
    assert workspace_body["status"] == "missing"
    assert workspace_body["updatedAt"] is None
    assert "workspace_snapshot" in workspace_body["missingSources"]
    assert workspace_body["goals"] == []

    cockpit = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit", headers=headers)
    assert cockpit.status_code == 200, cockpit.text
    cockpit_body = cockpit.json()
    assert cockpit_body["status"] == "missing"
    assert cockpit_body["updatedAt"] is None
    assert cockpit_body["headline"]["summary"] == ""
    assert cockpit_body["pendingMaterials"] == []
    assert "strategic_cockpit" in cockpit_body["missingSources"]


def test_thin_context_chat_returns_limited_context_metadata(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_qwen_chat(api_key, chat_payload, timeout):  # noqa: ANN001
        captured["systemPrompt"] = chat_payload["messages"][0]["content"]
        return "当前已知事实：只锁定了客户名，缺少工作台、DNA、会议和战略判断资料。"

    monkeypatch.setattr(cloud_main, "_sync_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)

    response = client.post(
        "/api/v1/consultation/chat",
        json={"message": "介绍一下这个客户", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answerMode"] == "limited_context"
    assert body["contextQuality"]["level"] == "thin"
    assert {"workspace", "client_dna", "meeting", "strategic_cockpit"}.issubset(
        set(body["contextQuality"]["missingSources"]),
    )
    assert "严禁根据客户名字" in str(captured["systemPrompt"])
