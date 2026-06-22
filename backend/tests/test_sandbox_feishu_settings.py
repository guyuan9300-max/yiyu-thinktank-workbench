from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    DEFAULT_LOCAL_SANDBOX_ID,
    activate_sandbox,
    create_sandbox,
    get_sandbox_setting,
    set_sandbox_setting,
)
from app.services.feishu_sync import FeishuSyncState  # noqa: E402


class FakeCloudResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}"
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def register_local_user(client: TestClient) -> str:
    response = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "workspace-feishu@example.com",
            "fullName": "工作空间飞书测试",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "本机测试组织",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]["id"]


def test_feishu_bot_settings_are_scoped_by_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    org = create_sandbox(db, kind="organization", name="组织 B", cloud_api_url="https://cloud-b.example.test")

    set_sandbox_setting(
        db,
        DEFAULT_LOCAL_SANDBOX_ID,
        "settings.feishu_bot",
        json.dumps({"appId": "cli_a", "receiverId": "ou_a", "updatedAt": "2026-06-18T00:00:00+00:00"}),
    )
    set_sandbox_setting(
        db,
        org.id,
        "settings.feishu_bot",
        json.dumps({"appId": "cli_b", "receiverId": "ou_b", "updatedAt": "2026-06-18T00:00:00+00:00"}),
    )

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    local_response = client.get("/api/v1/settings/feishu-bot")
    assert local_response.status_code == 200, local_response.text
    assert local_response.json()["appId"] == "cli_a"

    activate_sandbox(db, org.id)
    org_response = client.get("/api/v1/settings/feishu-bot")
    assert org_response.status_code == 200, org_response.text
    assert org_response.json()["appId"] == "cli_b"

    empty_org = create_sandbox(db, kind="organization", name="组织 C", cloud_api_url="https://cloud-c.example.test")
    activate_sandbox(db, empty_org.id)
    empty_response = client.get("/api/v1/settings/feishu-bot")
    assert empty_response.status_code == 200, empty_response.text
    assert empty_response.json()["appId"] == ""
    assert empty_response.json()["secretFingerprint"] is None


def test_feishu_app_secret_does_not_bleed_to_new_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    register_local_user(client)

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    saved = client.post(
        "/api/v1/settings/feishu-bot",
        json={"appId": "cli_local_secret", "appSecret": "secret-local"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["secretFingerprint"]

    org = create_sandbox(db, kind="organization", name="组织 Secret", cloud_api_url="https://cloud-secret.example.test")
    activate_sandbox(db, org.id)
    org_response = client.get("/api/v1/settings/feishu-bot")
    assert org_response.status_code == 200, org_response.text
    assert org_response.json()["appId"] == ""
    assert org_response.json()["secretFingerprint"] is None


def test_feishu_input_memory_is_scoped_by_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    save_local = client.post(
        "/api/v1/local-input-memory/feishu",
        json={"rememberInputs": True, "appId": "cli_local", "callbackMode": "cloud_relay"},
    )
    assert save_local.status_code == 200, save_local.text
    assert save_local.json()["feishuIntegration"]["appId"] == "cli_local"

    org = create_sandbox(db, kind="organization", name="组织 D", cloud_api_url="https://cloud-d.example.test")
    activate_sandbox(db, org.id)
    org_before = client.get("/api/v1/local-input-memory")
    assert org_before.status_code == 200, org_before.text
    assert org_before.json()["feishuIntegration"]["appId"] == ""

    save_org = client.post(
        "/api/v1/local-input-memory/feishu",
        json={"rememberInputs": True, "appId": "cli_org", "callbackMode": "cloud_relay"},
    )
    assert save_org.status_code == 200, save_org.text
    assert save_org.json()["feishuIntegration"]["appId"] == "cli_org"

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    local_again = client.get("/api/v1/local-input-memory")
    assert local_again.status_code == 200, local_again.text
    assert local_again.json()["feishuIntegration"]["appId"] == "cli_local"


def test_feishu_user_binding_is_scoped_by_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    user_id = register_local_user(client)
    org = create_sandbox(db, kind="organization", name="组织 E", cloud_api_url="https://cloud-e.example.test")

    set_sandbox_setting(
        db,
        DEFAULT_LOCAL_SANDBOX_ID,
        f"settings.feishu_user_binding:{user_id}",
        json.dumps({"linked": True, "userId": user_id, "openId": "ou_local", "name": "本机飞书成员"}),
    )
    set_sandbox_setting(
        db,
        org.id,
        f"settings.feishu_user_binding:{user_id}",
        json.dumps({"linked": True, "userId": user_id, "openId": "ou_org", "name": "组织飞书成员"}),
    )

    local_sync = FeishuSyncState(
        db,
        None,
        settings_getter=lambda key, default="": get_scoped_feishu_test_setting(db, DEFAULT_LOCAL_SANDBOX_ID, key, default),
    )
    org_sync = FeishuSyncState(
        db,
        None,
        settings_getter=lambda key, default="": get_scoped_feishu_test_setting(db, org.id, key, default),
    )

    assert local_sync.get_user_binding(user_id)["openId"] == "ou_local"
    assert org_sync.get_user_binding(user_id)["openId"] == "ou_org"


def test_legacy_feishu_user_binding_endpoint_maps_member_authorization(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    org = create_sandbox(db, kind="organization", name="组织授权", cloud_api_url="https://cloud-auth.example.test")
    activate_sandbox(db, org.id)
    set_sandbox_setting(db, org.id, "cloud_api_url", "https://cloud-auth.example.test")
    set_sandbox_setting(db, org.id, "cloud_access_token", "token-feishu-auth")
    set_sandbox_setting(
        db,
        org.id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "member-feishu",
                "email": "member@example.com",
                "fullName": "飞书成员",
                "organizationId": "org-feishu",
                "organizationName": "组织授权",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    client.app.state.app_state.cloud_api_url = "https://cloud-auth.example.test"

    def fake_cloud_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/api/v1/me/feishu-authorization"):
            return FakeCloudResponse(
                200,
                {
                    "linked": True,
                    "readyForAuthorization": True,
                    "organizationId": "org-feishu",
                    "organizationName": "组织授权",
                    "appId": "cli_member",
                    "userId": "member-feishu",
                    "openId": "ou_member",
                    "unionId": "on_member",
                    "feishuUserId": "user_member",
                    "name": "飞书成员",
                    "email": "member@example.com",
                    "boundAt": "2026-06-22T10:00:00+08:00",
                    "lastVerifiedAt": "2026-06-22T10:00:00+08:00",
                },
            )
        raise AssertionError(f"unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/settings/feishu-user-binding")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["linked"] is True
    assert payload["appId"] == "cli_member"
    assert payload["openId"] == "ou_member"
    assert payload["lastError"] is None


def test_feishu_oauth_callback_writes_to_original_workspace(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    user_id = register_local_user(client)

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    saved = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_local_oauth",
            "appSecret": "secret-local-oauth",
            "userBindingCallbackUrl": "http://testserver/api/v1/auth/feishu/callback",
        },
    )
    assert saved.status_code == 200, saved.text
    state_token = "fs_state_original_workspace"
    set_sandbox_setting(
        db,
        DEFAULT_LOCAL_SANDBOX_ID,
        f"settings.feishu_oauth_state:{state_token}",
        json.dumps(
            {
                "userId": user_id,
                "expiresAt": "2099-01-01T00:00:00",
                "sandboxId": DEFAULT_LOCAL_SANDBOX_ID,
                "createdAt": "2026-06-18T00:00:00+00:00",
            }
        ),
    )

    org = create_sandbox(db, kind="organization", name="组织 OAuth", cloud_api_url="https://cloud-oauth.example.test")
    set_sandbox_setting(
        db,
        org.id,
        "settings.feishu_bot",
        json.dumps({"appId": "cli_org_oauth", "receiverId": "ou_org", "updatedAt": "2026-06-18T00:00:00+00:00"}),
    )
    activate_sandbox(db, org.id)

    monkeypatch.setattr(app_main, "fetch_app_access_token", lambda **kwargs: ("tenant-token", 7200))
    monkeypatch.setattr(
        app_main,
        "exchange_authorization_code",
        lambda **kwargs: {"access_token": "user-token", "open_id": "ou_from_local_callback"},
    )
    monkeypatch.setattr(
        app_main,
        "fetch_user_info",
        lambda **kwargs: {"open_id": "ou_from_local_callback", "name": "飞书授权用户", "email": "oauth@example.com"},
    )

    callback = client.get(f"/api/v1/auth/feishu/callback?code=code-from-feishu&state={state_token}")
    assert callback.status_code == 200, callback.text
    local_raw = get_sandbox_setting(db, DEFAULT_LOCAL_SANDBOX_ID, f"settings.feishu_user_binding:{user_id}", "")
    org_raw = get_sandbox_setting(db, org.id, f"settings.feishu_user_binding:{user_id}", "")
    assert json.loads(local_raw)["openId"] == "ou_from_local_callback"
    assert org_raw == ""


def get_scoped_feishu_test_setting(db, sandbox_id: str, key: str, default: str = "") -> str:
    mapped_key = f"settings.{key}" if key.startswith("feishu_user_binding:") else key

    return get_sandbox_setting(db, sandbox_id, mapped_key, default)
