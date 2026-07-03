from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import activate_sandbox, create_sandbox, set_active_sandbox_setting  # noqa: E402


BASE_URL = "http://127.0.0.1:47830"


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_session(client: TestClient) -> None:
    user_payload = {
        "id": "user_admin",
        "organizationId": "org_yiyu_default",
        "organizationName": "益语智库",
        "email": "admin@example.com",
        "fullName": "管理员",
        "primaryRole": "admin",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    state = client.app.state.app_state
    sandbox = create_sandbox(state.db, kind="organization", name="益语智库", cloud_api_url=BASE_URL)
    state.db.execute(
        "UPDATE sandboxes SET organization_id = ?, organization_name = ? WHERE id = ?",
        ("org_yiyu_default", "益语智库", sandbox.id),
    )
    activate_sandbox(state.db, sandbox.id)
    state.cloud_api_url = BASE_URL
    set_active_sandbox_setting(state.db, "cloud_api_url", BASE_URL)
    set_active_sandbox_setting(state.db, "cloud_access_token", "token_admin")
    set_active_sandbox_setting(state.db, "cloud_session_user", json.dumps(user_payload, ensure_ascii=False))


def test_local_maintenance_mode_requires_cloud_session(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    status = client.get("/api/v1/maintenance-mode/status")
    assert status.status_code == 200
    assert status.json()["available"] is False
    assert status.json()["active"] is False

    enter = client.post("/api/v1/maintenance-mode/enter")
    assert enter.status_code == 403


def test_local_maintenance_mode_enter_and_exit_are_session_local(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_cloud_session(client)

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert headers == {"Authorization": "Bearer token_admin"}
        if url.endswith("/api/v1/maintenance-mode/status"):
            return httpx.Response(
                200,
                json={
                    "available": True,
                    "active": False,
                    "canEnter": True,
                    "canManagePermissions": False,
                    "organizationId": "org_yiyu_default",
                    "userId": "user_admin",
                },
            )
        if url.endswith("/api/v1/maintenance-mode/enter"):
            return httpx.Response(
                200,
                json={
                    "available": True,
                    "active": True,
                    "canEnter": True,
                    "canManagePermissions": False,
                    "organizationId": "org_yiyu_default",
                    "userId": "user_admin",
                },
            )
        if url.endswith("/api/v1/maintenance-mode/exit"):
            return httpx.Response(
                200,
                json={
                    "available": True,
                    "active": False,
                    "canEnter": True,
                    "canManagePermissions": False,
                    "organizationId": "org_yiyu_default",
                    "userId": "user_admin",
                },
            )
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    inactive = client.get("/api/v1/maintenance-mode/status")
    assert inactive.status_code == 200
    assert inactive.json()["active"] is False

    entered = client.post("/api/v1/maintenance-mode/enter")
    assert entered.status_code == 200, entered.text
    assert entered.json()["active"] is True
    assert client.app.state.app_state.maintenance_mode_active is True

    active = client.get("/api/v1/maintenance-mode/status")
    assert active.status_code == 200
    assert active.json()["active"] is True

    exited = client.post("/api/v1/maintenance-mode/exit")
    assert exited.status_code == 200
    assert exited.json()["active"] is False
    assert client.app.state.app_state.maintenance_mode_active is False
