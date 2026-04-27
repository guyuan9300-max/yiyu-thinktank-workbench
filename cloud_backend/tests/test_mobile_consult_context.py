from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["ARK_API_KEY"] = "test-ark-key"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402
from app import main as cloud_main  # noqa: E402
from app import knowledge_store as cloud_knowledge_store  # noqa: E402


def setup_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def auth_headers(client: TestClient):
    response = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_client(app, client_id: str = "client_mobile_context", client_name: str = "日慈基金会") -> tuple[str, str]:
    timestamp = cloud_main.now_iso()
    app.state.app_state.db.execute(
        "INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
        (client_id, "org_yiyu_default", client_name, "", timestamp, timestamp),
    )
    return client_id, client_name


def test_mobile_capabilities_and_workspace_routes_stop_faking_missing_routes():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, _ = seed_client(app)

    capabilities = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    payload = capabilities.json()
    assert payload["consultationChat"] is True
    assert payload["clientWorkspace"] is True
    assert payload["strategicCockpit"] is True
    assert payload["contextBundle"] is True
    assert payload["consultationPayloadVersion"] == "v2"

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert workspace_payload["status"] in {"partial", "missing", "rich"}
    assert "missingSources" in workspace_payload
    assert "sourceAvailability" in workspace_payload

    cockpit = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit", headers=headers)
    assert cockpit.status_code == 200, cockpit.text
    cockpit_payload = cockpit.json()
    assert cockpit_payload["status"] in {"partial", "missing", "rich"}
    assert "missingSources" in cockpit_payload
    assert "sourceAvailability" in cockpit_payload


def test_thin_context_consult_forces_limited_context(monkeypatch):
    captured: dict[str, str] = {}

    def fake_qwen_chat(api_key: str, payload: dict, timeout: object) -> str:
        captured["system"] = str(payload["messages"][0]["content"])
        return "已知：当前只找到客户名。\n\n缺失：还没有工作台、DNA、会议或 cockpit。\n\n下一步：先同步客户工作台与 DNA。"

    monkeypatch.setattr(cloud_main, "_sync_qwen_chat", fake_qwen_chat)
    monkeypatch.setattr(cloud_knowledge_store, "find_desktop_app_db_path", lambda: None)

    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, client_name = seed_client(app)

    response = client.post(
        "/api/v1/consultation/chat",
        headers=headers,
        json={
            "message": f"介绍一下{client_name}",
            "clientId": client_id,
            "clientName": client_name,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answerMode"] == "limited_context"
    assert payload["contextQuality"]["level"] == "thin"
    missing_types = {item["type"] for item in payload["missingContext"]}
    assert "workspace" in missing_types
    assert "client_dna" in missing_types
    assert "meeting" in missing_types
    assert "strategic_cockpit" in missing_types
    assert "只能根据【已知事实】回答" in captured["system"]
    assert "通常基金会可能" in captured["system"]


def test_publish_knowledge_mirror_flips_capability_and_feeds_workspace():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, _ = seed_client(app)

    before = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["knowledgeMirror"] is False

    publish = client.post(
        "/api/v1/mobile/knowledge-mirror/publish",
        headers=headers,
        json={
            "items": [
                {
                    "clientId": client_id,
                    "sourceType": "workspace_snapshot",
                    "sourceId": f"workspace:{client_id}",
                    "snapshotVersion": 1,
                    "snapshotHash": "abc123",
                    "updatedAt": "2026-04-19T10:00:00",
                    "payload": {
                        "status": "partial",
                        "goals": [{"id": "g1", "title": "准备沟通材料", "summary": "本周先补客户材料"}],
                        "meetings": [],
                        "documentCards": [],
                        "latestOpenQuestions": [],
                        "latestConflicts": [],
                        "relatedTasks": [{"id": "task-1", "title": "准备材料", "status": "todo"}],
                        "missingSources": ["client_dna", "recent_meetings"],
                    },
                    "evidenceRefs": ["seed:test"],
                }
            ]
        },
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["publishedCount"] == 1

    after = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert after.status_code == 200, after.text
    assert after.json()["knowledgeMirror"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    assert payload["status"] == "partial"
    assert payload["goals"][0]["title"] == "准备沟通材料"
