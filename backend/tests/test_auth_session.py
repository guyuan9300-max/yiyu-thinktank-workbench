from __future__ import annotations

import json
import sys
import threading
import time
from threading import Event, Thread
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    activate_sandbox,
    create_sandbox,
    ensure_organization_sandbox_for_session,
    get_active_sandbox_id,
    get_active_sandbox_setting,
    set_active_sandbox_setting,
    set_sandbox_setting,
)
from app.services.workspace_context import WorkspaceContext  # noqa: E402


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


def test_restart_uses_active_workspace_cloud_instead_of_bootstrap_env(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    initial = TestClient(create_app(data_dir))
    initial.__enter__()
    db = initial.app.state.app_state.db
    user_payload = {
        "id": "user-restart",
        "organizationId": "org-restart",
        "organizationName": "重启测试组织",
        "email": "restart@example.test",
        "fullName": "重启测试成员",
        "primaryRole": "employee",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    workspace = create_sandbox(
        db,
        kind="organization",
        name="重启测试组织",
        cloud_api_url="https://workspace-cloud.example.test",
    )
    db.execute(
        "UPDATE sandboxes SET organization_id = ?, cloud_instance_id = ?, identity_state = 'verified' WHERE id = ?",
        ("org-restart", "cloud-restart", workspace.id),
    )
    for key, value in (
        ("cloud_access_token", "restart-access"),
        ("cloud_refresh_token", "restart-refresh"),
        ("cloud_session_user", json.dumps(user_payload, ensure_ascii=False)),
        ("cloud_session_user_snapshot", json.dumps(user_payload, ensure_ascii=False)),
    ):
        set_sandbox_setting(db, workspace.id, key, value)
    activate = initial.post(f"/api/v1/workspaces/{workspace.id}/activate")
    assert activate.status_code == 200, activate.text
    initial.__exit__(None, None, None)

    monkeypatch.setenv("YIYU_CLOUD_API_URL", "http://127.0.0.1:49999")
    requested_urls: list[str] = []

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None, trust_env=None):
        requested_urls.append(url)
        assert url.startswith("https://workspace-cloud.example.test/")
        assert (headers or {}).get("Authorization") == "Bearer restart-access"
        if url.endswith("/api/v1/auth/me"):
            return httpx.Response(200, json=user_payload)
        if url.endswith("/api/v1/me/org-membership"):
            return httpx.Response(
                200,
                json={
                    "hasOrganization": True,
                    "membershipStatus": "approved",
                    "organizationId": "org-restart",
                    "organizationName": "重启测试组织",
                },
            )
        if url.endswith("/api/v1/settings/org-ai-config/runtime-secret"):
            return httpx.Response(404, json={"detail": "not configured"})
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)
    restarted = TestClient(create_app(data_dir))
    restarted.__enter__()
    response = restarted.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    assert response.json()["authenticated"] is True
    restarted_db = restarted.app.state.app_state.db
    assert get_active_sandbox_setting(restarted_db, "cloud_access_token", "") == "restart-access"
    assert get_active_sandbox_setting(restarted_db, "cloud_refresh_token", "") == "restart-refresh"
    assert requested_urls
    assert all("127.0.0.1:49999" not in url for url in requested_urls)
    restarted.__exit__(None, None, None)


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


def test_organization_cloud_session_without_org_claim_fails_closed() -> None:
    context = WorkspaceContext(
        sandbox_id="sandbox_org_a",
        kind="organization",
        organization_id="org_a",
        cloud_api_url="https://org-a.example.test",
        access_token="token-without-org-claim",
        session_user={"id": "user_a"},
    )

    assert context.has_cloud_session is True
    assert context.session_matches_workspace is False


def test_cloud_login_rejects_membership_organization_mismatch_before_bootstrap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path)
    state = client.app.state.app_state
    original_sandbox_id = get_active_sandbox_id(state.db)
    draft_response = client.post(
        "/api/v1/clients",
        json={
            "name": "登录失败不得迁移的本机草稿",
            "alias": "",
            "domain": "auth-mismatch-test",
            "type": "公益组织",
            "intro": "保持在原本机草稿沙箱",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert draft_response.status_code == 200, draft_response.text
    draft_client_id = str(draft_response.json()["id"])
    cloud_a = "https://org-a-mismatch.example.test"
    request_paths: list[str] = []
    directory_calls = 0

    class FakeCloudResponse:
        def __init__(self, payload: object):
            self.status_code = 200
            self._payload = payload
            self.content = b"{}"
            self.text = str(payload)
            self.headers: dict[str, str] = {}

        def json(self):
            return self._payload

    def fake_cloud_request(method: str, url: str, **kwargs):
        del kwargs
        request_paths.append(f"{method} {url.removeprefix(cloud_a)}")
        if method == "POST" and url == f"{cloud_a}/api/v1/auth/login":
            return FakeCloudResponse(
                {
                    "accessToken": "access-a-mismatch",
                    "refreshToken": "refresh-a-mismatch",
                    "user": {
                        "id": "user-a-mismatch",
                        "organizationId": "org_a",
                        "organizationName": "组织 A",
                        "email": "a-mismatch@example.test",
                        "fullName": "用户 A",
                        "primaryRole": "admin",
                        "accountStatus": "approved",
                        "membershipStatus": "approved",
                    },
                }
            )
        if method == "GET" and url == f"{cloud_a}/api/v1/cloud-instance":
            return FakeCloudResponse({"cloudInstanceId": "cloud-a-mismatch"})
        if method == "GET" and url == f"{cloud_a}/api/v1/me/org-membership":
            return FakeCloudResponse(
                {
                    "hasOrganization": True,
                    "organizationId": "org_b",
                    "organizationName": "组织 B",
                    "membershipStatus": "approved",
                }
            )
        raise AssertionError(f"downstream bootstrap must not run: {method} {url}")

    def unexpected_directory_sync(*args, **kwargs):
        nonlocal directory_calls
        directory_calls += 1
        raise AssertionError("directory bootstrap must not run after membership mismatch")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)
    monkeypatch.setattr(
        "app.modules.organization.sync_organization_directory",
        unexpected_directory_sync,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "a-mismatch@example.test",
            "password": "Password123!",
            "rememberMe": True,
            "cloudApiUrl": cloud_a,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "组织成员关系与登录工作空间不一致"}
    assert request_paths == [
        "POST /api/v1/auth/login",
        "GET /api/v1/me/org-membership",
    ]
    assert directory_calls == 0
    assert get_active_sandbox_id(state.db) == original_sandbox_id
    assert state.db.fetchone(
        "SELECT id FROM sandboxes WHERE organization_id = ?",
        ("org_a",),
    ) is None
    draft_row = state.db.fetchone(
        "SELECT sandbox_id FROM clients WHERE id = ?",
        (draft_client_id,),
    )
    assert draft_row is not None
    assert str(draft_row["sandbox_id"]) == original_sandbox_id
    assert get_active_sandbox_setting(state.db, "cloud_access_token", "") == ""
    assert get_active_sandbox_setting(state.db, "cloud_refresh_token", "") == ""


def test_cloud_login_bootstrap_remains_bound_to_login_workspace_during_switch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path)
    state = client.app.state.app_state
    db = state.db
    cloud_a = "https://org-a.example.test"
    cloud_b = "https://org-b.example.test"
    state.cloud_api_url = cloud_a
    db.set_setting("cloud_api_url", cloud_a)
    workspace_b = ensure_organization_sandbox_for_session(
        db,
        organization_id="org_b",
        organization_name="组织 B",
        cloud_api_url=cloud_b,
        cloud_instance_id="cloud-b",
    )
    activate_sandbox(db, workspace_b.id)

    membership_started = threading.Event()
    release_membership = threading.Event()
    request_records: list[tuple[str, str, str]] = []
    directory_calls: list[tuple[str, str, str, str]] = []

    class FakeCloudResponse:
        def __init__(self, status_code: int, payload: object):
            self.status_code = status_code
            self._payload = payload
            self.content = b"{}"
            self.text = str(payload)
            self.headers: dict[str, str] = {}

        def json(self):
            return self._payload

    def fake_cloud_request(method: str, url: str, **kwargs):
        authorization = str((kwargs.get("headers") or {}).get("Authorization") or "")
        request_records.append((method, url, authorization))
        if method == "POST" and url == f"{cloud_a}/api/v1/auth/login":
            return FakeCloudResponse(
                200,
                {
                    "accessToken": "access-a",
                    "refreshToken": "refresh-a",
                    "user": {
                        "id": "user-a",
                        "organizationId": "org_a",
                        "organizationName": "组织 A",
                        "email": "a@example.test",
                        "fullName": "用户 A",
                        "primaryRole": "admin",
                        "accountStatus": "approved",
                        "membershipStatus": "approved",
                    },
                },
            )
        if method == "GET" and url == f"{cloud_a}/api/v1/cloud-instance":
            return FakeCloudResponse(
                200,
                {"cloudInstanceId": "cloud-a", "service": "test", "version": "test"},
            )
        if method == "GET" and url == f"{cloud_a}/api/v1/me/org-membership":
            assert authorization == "Bearer access-a"
            membership_started.set()
            assert release_membership.wait(timeout=5)
            return FakeCloudResponse(
                200,
                {
                    "hasOrganization": True,
                    "organizationId": "org_a",
                    "organizationName": "组织 A",
                    "membershipStatus": "approved",
                },
            )
        if method == "GET" and url == f"{cloud_a}/api/v1/task-lists":
            assert authorization == "Bearer access-a"
            return FakeCloudResponse(
                200,
                {
                    "lists": [
                        {
                            "id": "list-a",
                            "name": "组织 A 清单",
                            "scope": "org",
                            "isDefault": True,
                            "organizationId": "org_a",
                        }
                    ]
                },
            )
        if method == "GET" and url == f"{cloud_a}/api/v1/settings/org-ai-config/runtime-secret":
            assert authorization == "Bearer access-a"
            return FakeCloudResponse(403, {"detail": "not configured"})
        if method == "GET" and url in {
            f"{cloud_a}/api/v1/settings/org-object-storage-config",
            f"{cloud_a}/api/v1/settings/org-object-storage-config/secret",
        }:
            assert authorization == "Bearer access-a"
            return FakeCloudResponse(
                200,
                {
                    "orgId": "org_a",
                    "provider": "",
                    "enabled": False,
                    "credentials": {},
                    "extraConfig": {},
                },
            )
        raise AssertionError(f"unexpected cloud request: {method} {url}")

    def fake_directory_sync(
        _db,
        *,
        cloud_base_url: str,
        cloud_token: str,
        client_sandbox_id: str,
        expected_organization_id: str,
        **_kwargs,
    ):
        from app.modules.organization import SyncReport

        directory_calls.append(
            (
                cloud_base_url,
                cloud_token,
                client_sandbox_id,
                expected_organization_id,
            )
        )
        return SyncReport(status="ok", synced_at="2026-07-11T00:00:00Z")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)
    monkeypatch.setattr(
        "app.modules.organization.sync_organization_directory",
        fake_directory_sync,
    )

    result: dict[str, object] = {}

    def run_login() -> None:
        result["response"] = client.post(
            "/api/v1/auth/login",
            json={
                "identifier": "a@example.test",
                "password": "Password123!",
                "rememberMe": True,
                "cloudApiUrl": cloud_a,
            },
        )

    worker = threading.Thread(target=run_login, daemon=True)
    worker.start()
    assert membership_started.wait(timeout=5)
    switched = client.post(f"/api/v1/workspaces/{workspace_b.id}/activate")
    assert switched.status_code == 200, switched.text
    release_membership.set()
    worker.join(timeout=8)
    assert not worker.is_alive()
    response = result["response"]
    assert getattr(response, "status_code") == 200

    workspace_a = db.fetchone(
        "SELECT id FROM sandboxes WHERE organization_id = ?",
        ("org_a",),
    )
    assert workspace_a is not None
    sandbox_a = str(workspace_a["id"])
    assert directory_calls == [(cloud_a, "access-a", sandbox_a, "org_a")]

    client_a = db.fetchone(
        "SELECT id FROM clients WHERE sandbox_id = ? AND name = ?",
        (sandbox_a, "组织 A"),
    )
    assert client_a is not None
    assert db.fetchone(
        "SELECT id FROM clients WHERE sandbox_id = ? AND name = ?",
        (workspace_b.id, "组织 A"),
    ) is None
    assert db.fetchone(
        "SELECT id FROM task_lists WHERE sandbox_id = ? AND cloud_id = ?",
        (sandbox_a, "list-a"),
    ) is not None
    assert db.fetchone(
        "SELECT id FROM task_lists WHERE sandbox_id = ? AND cloud_id = ?",
        (workspace_b.id, "list-a"),
    ) is None

    deadline = time.monotonic() + 3
    expected_async_paths = {
        "/api/v1/settings/org-ai-config/runtime-secret",
        "/api/v1/settings/org-object-storage-config/secret",
    }
    while time.monotonic() < deadline:
        observed = {
            url.removeprefix(cloud_a)
            for _, url, _ in request_records
            if url.startswith(cloud_a)
        }
        if expected_async_paths.issubset(observed):
            break
        time.sleep(0.02)

    authorized_requests = [
        (url, authorization)
        for _, url, authorization in request_records
        if authorization
    ]
    assert authorized_requests
    assert all(url.startswith(cloud_a) for url, _ in authorized_requests)
    assert all(auth == "Bearer access-a" for _, auth in authorized_requests)
