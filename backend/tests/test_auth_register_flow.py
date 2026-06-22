from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import get_active_sandbox, get_active_sandbox_setting  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_register_restores_cloud_session_immediately(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    client.app.state.app_state.cloud_api_url = "http://127.0.0.1:47830"
    db.set_setting("cloud_api_url", "http://127.0.0.1:47830")
    cloud_payload = {
        "accessToken": "cloud-access-token",
        "refreshToken": "cloud-refresh-token",
        "user": {
            "id": "user_personal_1",
            "organizationId": "org_yiyu_default",
            "email": "personal@example.com",
            "fullName": "个人用户",
            "primaryRole": "employee",
            "accountStatus": "approved",
        },
    }

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        if url.endswith("/api/v1/auth/register"):
            assert method == "POST"
            assert json == {
                "email": "personal@example.com",
                "fullName": "个人用户",
                "password": "Password123!",
                "isDepartmentLead": False,
            }
            return httpx.Response(200, json=cloud_payload)
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "personal@example.com",
            "fullName": "个人用户",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "cloud"
    assert payload["user"]["email"] == "personal@example.com"
    active_workspace = get_active_sandbox(db)
    assert active_workspace.kind == "organization"
    assert active_workspace.organizationId == "org_yiyu_default"
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "cloud-access-token"
    assert get_active_sandbox_setting(db, "cloud_refresh_token", "") == "cloud-refresh-token"
    assert json.loads(get_active_sandbox_setting(db, "cloud_session_user", ""))["email"] == "personal@example.com"
