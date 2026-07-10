from __future__ import annotations

import json
import sys
from threading import Event, Thread
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    create_sandbox,
    get_active_sandbox_setting,
    set_sandbox_setting,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_auth_me_refreshes_expired_cloud_session(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    user_payload = {
      "id": "user_guyuan",
      "organizationId": "org_yiyu_default",
      "email": "guyuan@klngo.org",
      "fullName": "顾源源",
      "primaryRole": "admin",
      "accountStatus": "approved",
      "membershipStatus": "approved",
    }
    workspace = create_sandbox(
        db,
        kind="organization",
        name="益语智库",
        cloud_api_url="http://127.0.0.1:47830",
    )
    db.execute(
        "UPDATE sandboxes SET organization_id = ?, cloud_instance_id = ?, identity_state = 'verified' WHERE id = ?",
        ("org_yiyu_default", "cloud-yiyu", workspace.id),
    )
    set_sandbox_setting(db, workspace.id, "cloud_access_token", "expired-access")
    set_sandbox_setting(db, workspace.id, "cloud_refresh_token", "refresh-1")
    set_sandbox_setting(db, workspace.id, "cloud_session_user", json.dumps(user_payload, ensure_ascii=False))
    set_sandbox_setting(db, workspace.id, "cloud_session_user_snapshot", json.dumps(user_payload, ensure_ascii=False))
    activate = client.post(f"/api/v1/workspaces/{workspace.id}/activate")
    assert activate.status_code == 200, activate.text

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        if url.endswith("/api/v1/auth/me"):
            authorization = (headers or {}).get("Authorization")
            if authorization == "Bearer expired-access":
                return httpx.Response(401, json={"detail": "invalid token"})
            if authorization == "Bearer fresh-access":
                return httpx.Response(200, json=user_payload)
        if url.endswith("/api/v1/auth/refresh"):
            assert method == "POST"
            assert json == {"refreshToken": "refresh-1"}
            return httpx.Response(
                200,
                json={
                    "accessToken": "fresh-access",
                    "refreshToken": "refresh-2",
                    "user": user_payload,
                },
            )
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["email"] == "guyuan@klngo.org"
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "fresh-access"
    assert get_active_sandbox_setting(db, "cloud_refresh_token", "") == "refresh-2"


def test_late_auth_me_response_cannot_replace_new_active_workspace(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    workspace_a = create_sandbox(
        db,
        kind="organization",
        name="组织 A",
        cloud_api_url="https://cloud-a.example.test",
    )
    workspace_b = create_sandbox(
        db,
        kind="organization",
        name="组织 B",
        cloud_api_url="https://cloud-b.example.test",
    )
    db.execute(
        "UPDATE sandboxes SET organization_id = ?, cloud_instance_id = ?, identity_state = 'verified' WHERE id = ?",
        ("org-a", "cloud-a", workspace_a.id),
    )
    db.execute(
        "UPDATE sandboxes SET organization_id = ?, cloud_instance_id = ?, identity_state = 'verified' WHERE id = ?",
        ("org-b", "cloud-b", workspace_b.id),
    )
    user_a = {
        "id": "user-a",
        "organizationId": "org-a",
        "organizationName": "组织 A",
        "email": "a@example.test",
        "fullName": "成员 A",
        "primaryRole": "employee",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    user_b = {
        "id": "user-b",
        "organizationId": "org-b",
        "organizationName": "组织 B",
        "email": "b@example.test",
        "fullName": "成员 B",
        "primaryRole": "employee",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    for workspace, access_token, refresh_token, user in (
        (workspace_a, "access-a", "refresh-a", user_a),
        (workspace_b, "access-b", "refresh-b", user_b),
    ):
        set_sandbox_setting(db, workspace.id, "cloud_access_token", access_token)
        set_sandbox_setting(db, workspace.id, "cloud_refresh_token", refresh_token)
        set_sandbox_setting(db, workspace.id, "cloud_session_user", json.dumps(user, ensure_ascii=False))
        set_sandbox_setting(db, workspace.id, "cloud_session_user_snapshot", json.dumps(user, ensure_ascii=False))
    activate = client.post(f"/api/v1/workspaces/{workspace_a.id}/activate")
    assert activate.status_code == 200, activate.text

    request_started = Event()
    release_response = Event()

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert method == "GET"
        assert url == "https://cloud-a.example.test/api/v1/auth/me"
        assert (headers or {}).get("Authorization") == "Bearer access-a"
        request_started.set()
        assert release_response.wait(timeout=3)
        return httpx.Response(200, json=user_a)

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    result: dict[str, object] = {}

    def read_auth_state() -> None:
        response = client.get("/api/v1/auth/me")
        result["status_code"] = response.status_code
        result["payload"] = response.json()

    thread = Thread(target=read_auth_state)
    thread.start()
    assert request_started.wait(timeout=3)
    switch = client.post(f"/api/v1/workspaces/{workspace_b.id}/activate")
    assert switch.status_code == 200, switch.text
    release_response.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert result["status_code"] == 409
    assert db.get_setting("active_sandbox_id", "") == workspace_b.id
    assert get_active_sandbox_setting(db, "cloud_access_token", "") == "access-b"
    assert get_active_sandbox_setting(db, "cloud_session_user", "") == json.dumps(user_b, ensure_ascii=False)
    rows = db.fetchall("SELECT id, organization_id, cloud_api_url FROM sandboxes WHERE kind = 'organization'")
    assert {(row["id"], row["organization_id"], row["cloud_api_url"]) for row in rows} == {
        (workspace_a.id, "org-a", "https://cloud-a.example.test"),
        (workspace_b.id, "org-b", "https://cloud-b.example.test"),
    }
