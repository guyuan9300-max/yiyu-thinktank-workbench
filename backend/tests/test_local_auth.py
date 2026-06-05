from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(data_dir: Path) -> TestClient:
    app = create_app(data_dir)
    client = TestClient(app)
    client.__enter__()
    return client


def test_auth_me_requires_local_registration_when_device_is_empty(tmp_path: Path) -> None:
    client = make_client(tmp_path / "data")

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["sessionMode"] == "local"
    assert payload["user"] is None
    assert payload["requiresLocalIdentitySetup"] is True
    assert payload["localIdentityStatus"] == "needs_setup"
    assert "本机账号" in payload["message"]


def test_local_register_creates_identity_without_calling_cloud(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    db = client.app.state.app_state.db

    def fail_cloud_request(*args, **kwargs):
        raise AssertionError("local auth should not call cloud httpx")

    monkeypatch.setattr(app_main.httpx, "request", fail_cloud_request)

    response = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "local-owner@example.com",
            "fullName": "本机负责人",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "本机工作区",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "local"
    assert payload["user"]["email"] == "local-owner@example.com"
    assert payload["user"]["primaryRole"] == "admin"
    assert payload["user"]["membershipStatus"] == "approved"

    row = db.fetchone(
        """
        SELECT email, password_hash, local_organization_name, organization_mode, membership_status
        FROM local_identities
        WHERE email = ?
        """,
        ("local-owner@example.com",),
    )
    assert row is not None
    assert row["password_hash"] != "Password123!"
    assert row["local_organization_name"] == "本机工作区"
    assert row["organization_mode"] == "create"
    assert row["membership_status"] == "approved"

    auth_me = client.get("/api/v1/auth/me")
    assert auth_me.status_code == 200, auth_me.text
    assert auth_me.json()["authenticated"] is True
    assert auth_me.json()["user"]["email"] == "local-owner@example.com"


def test_local_register_join_existing_org_keeps_pending_invite_locally(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    db = client.app.state.app_state.db

    def fail_cloud_request(*args, **kwargs):
        raise AssertionError("local auth should not call cloud httpx")

    monkeypatch.setattr(app_main.httpx, "request", fail_cloud_request)

    response = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "joiner@example.com",
            "fullName": "等待加入组织",
            "password": "Password123!",
            "organizationMode": "join",
            "inviteCode": "INVITE-001",
            "departmentId": "dept_customer_service",
            "jobTitle": "咨询顾问",
            "managerName": "负责人A",
            "currentFocus": "先完成桌面初始化",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "local"
    assert payload["user"]["membershipStatus"] == "pending"
    assert payload["user"]["departmentId"] == "dept_customer_service"
    assert payload["user"]["organizationName"] == "待加入组织"
    assert payload["user"]["pendingInviteCode"] == "INVITE-001"
    assert payload["user"]["jobTitle"] == "咨询顾问"
    assert payload["user"]["managerName"] == "负责人A"
    assert payload["user"]["currentFocus"] == "先完成桌面初始化"

    row = db.fetchone(
        """
        SELECT organization_mode, pending_invite_code, pending_department_id, job_title, manager_name, current_focus, membership_status
        FROM local_identities
        WHERE email = ?
        """,
        ("joiner@example.com",),
    )
    assert row is not None
    assert row["organization_mode"] == "join"
    assert row["pending_invite_code"] == "INVITE-001"
    assert row["pending_department_id"] == "dept_customer_service"
    assert row["job_title"] == "咨询顾问"
    assert row["manager_name"] == "负责人A"
    assert row["current_focus"] == "先完成桌面初始化"
    assert row["membership_status"] == "pending"


def test_local_login_verifies_password_and_respects_remember_me(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    client = make_client(data_dir)

    register = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "remember@example.com",
            "fullName": "本机登录用户",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "记忆工作区",
        },
    )
    assert register.status_code == 200, register.text

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200, logout.text
    assert logout.json()["authenticated"] is False

    wrong_password = client.post(
        "/api/v1/local-auth/login",
        json={"identifier": "remember@example.com", "password": "wrong-password", "rememberMe": False},
    )
    assert wrong_password.status_code == 401

    session_only = client.post(
        "/api/v1/local-auth/login",
        json={"identifier": "remember@example.com", "password": "Password123!", "rememberMe": False},
    )
    assert session_only.status_code == 200, session_only.text
    assert session_only.json()["authenticated"] is True

    client.__exit__(None, None, None)

    reopened = make_client(data_dir)
    reopened_auth = reopened.get("/api/v1/auth/me")
    assert reopened_auth.status_code == 200, reopened_auth.text
    assert reopened_auth.json()["authenticated"] is False

    remembered = reopened.post(
        "/api/v1/local-auth/login",
        json={"identifier": "remember@example.com", "password": "Password123!", "rememberMe": True},
    )
    assert remembered.status_code == 200, remembered.text
    reopened.__exit__(None, None, None)

    reopened_again = make_client(data_dir)
    remembered_auth = reopened_again.get("/api/v1/auth/me")
    assert remembered_auth.status_code == 200, remembered_auth.text
    assert remembered_auth.json()["authenticated"] is True
    assert remembered_auth.json()["user"]["email"] == "remember@example.com"


def test_auth_me_requires_local_identity_setup_for_legacy_workspace_data(tmp_path: Path) -> None:
    client = make_client(tmp_path / "data")
    db = client.app.state.app_state.db
    timestamp = "2026-05-08T10:00:00"
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES('legacy-client-1', '旧库客户', '旧库客户', 'legacy.example', 'consulting', '', 'active', '#5B7BFE', ?, ?)
        """,
        (timestamp, timestamp),
    )

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["sessionMode"] == "local"
    assert payload["user"] is None
    assert payload["requiresLocalIdentitySetup"] is True
    assert payload["localIdentityStatus"] == "needs_setup"
    assert "已有本地数据" in payload["message"]

    complete = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "legacy-owner@example.com",
            "fullName": "旧库负责人",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "旧库本机组织",
        },
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["authenticated"] is True
    preserved = db.fetchone("SELECT name FROM clients WHERE id = ?", ("legacy-client-1",))
    assert preserved is not None
    assert preserved["name"] == "旧库客户"


def test_cloud_login_binds_current_local_identity(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    state = client.app.state.app_state
    db = state.db
    state.cloud_api_url = "http://cloud.example.test"
    db.set_setting("cloud_api_url", "http://cloud.example.test")

    local = client.post(
        "/api/v1/local-auth/register",
        json={
            "email": "local-bind@example.com",
            "fullName": "待绑定用户",
            "password": "Password123!",
            "organizationMode": "create",
            "organizationName": "待绑定本机组织",
        },
    )
    assert local.status_code == 200, local.text
    local_user_id = local.json()["user"]["id"]

    class FakeCloudResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.content = b"{}"
            self.text = str(payload)

        def json(self) -> dict:
            return self._payload

    def fake_cloud_request(method, url, **kwargs):
        if method == "POST" and url.endswith("/api/v1/auth/login"):
            assert kwargs["json"]["identifier"] == "cloud-user@example.com"
            return FakeCloudResponse(
                200,
                {
                    "accessToken": "access-1",
                    "refreshToken": "refresh-1",
                    "user": {
                        "id": "cloud-user-1",
                        "organizationId": "cloud-org-1",
                        "email": "cloud-user@example.com",
                        "fullName": "云端用户",
                        "primaryRole": "admin",
                        "accountStatus": "approved",
                        "membershipStatus": "approved",
                    },
                },
            )
        if method == "GET" and url.endswith("/api/v1/me/org-membership"):
            return FakeCloudResponse(200, {"hasOrganization": False})
        raise AssertionError(f"unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "cloud-user@example.com", "password": "CloudPass123!", "rememberMe": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "cloud"
    assert payload["user"]["id"] == "cloud-user-1"

    row = db.fetchone(
        """
        SELECT bound_cloud_user_id, bound_cloud_organization_id, bound_cloud_email
        FROM local_identities
        WHERE id = ?
        """,
        (local_user_id,),
    )
    assert row is not None
    assert row["bound_cloud_user_id"] == "cloud-user-1"
    assert row["bound_cloud_organization_id"] == "cloud-org-1"
    assert row["bound_cloud_email"] == "cloud-user@example.com"


def test_admin_claim_proxy_refreshes_cloud_session_user(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    state = client.app.state.app_state
    state.cloud_api_url = "http://cloud.example.test"
    state.db.set_setting("cloud_api_url", "http://cloud.example.test")

    class FakeCloudResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.content = b"{}"
            self.text = str(payload)

        def json(self) -> dict:
            return self._payload

    def fake_cloud_request(method, url, **kwargs):
        if method == "POST" and url.endswith("/api/v1/auth/login"):
            return FakeCloudResponse(
                200,
                {
                    "accessToken": "access-claim",
                    "refreshToken": "refresh-claim",
                    "user": {
                        "id": "claim-user-1",
                        "organizationId": "claim-org-1",
                        "organizationName": "待认领组织",
                        "email": "claim-user@example.com",
                        "fullName": "待认领用户",
                        "primaryRole": "employee",
                        "accountStatus": "approved",
                        "membershipStatus": "none",
                    },
                },
            )
        if method == "GET" and url.endswith("/api/v1/me/org-membership"):
            return FakeCloudResponse(200, {"hasOrganization": False, "membershipStatus": "none"})
        if method == "GET" and url.endswith("/api/v1/auth/me"):
            return FakeCloudResponse(
                200,
                {
                    "id": "claim-user-1",
                    "organizationId": "claim-org-1",
                    "organizationName": "待认领组织",
                    "email": "claim-user@example.com",
                    "fullName": "待认领用户",
                    "primaryRole": "admin",
                    "accountStatus": "approved",
                    "membershipStatus": "approved",
                },
            )
        if method == "GET" and url.endswith("/api/v1/me/org-membership/admin-claim-status"):
            return FakeCloudResponse(
                200,
                {
                    "hasOrganization": True,
                    "organizationId": "claim-org-1",
                    "organizationName": "待认领组织",
                    "hasAdmin": False,
                    "canClaim": True,
                    "reason": None,
                    "currentUserRole": "employee",
                    "currentUserMembershipStatus": "none",
                },
            )
        if method == "POST" and url.endswith("/api/v1/me/org-membership/admin-claim"):
            return FakeCloudResponse(
                200,
                {
                    "id": "claim-user-1",
                    "organizationId": "claim-org-1",
                    "organizationName": "待认领组织",
                    "email": "claim-user@example.com",
                    "fullName": "待认领用户",
                    "primaryRole": "admin",
                    "accountStatus": "approved",
                    "membershipStatus": "approved",
                },
            )
        raise AssertionError(f"unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "claim-user@example.com", "password": "CloudPass123!", "rememberMe": True},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["primaryRole"] == "employee"

    status = client.get("/api/v1/me/org-membership/admin-claim-status")
    assert status.status_code == 200, status.text
    assert status.json()["canClaim"] is True

    claim = client.post("/api/v1/me/org-membership/admin-claim")
    assert claim.status_code == 200, claim.text
    payload = claim.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "cloud"
    assert payload["user"]["primaryRole"] == "admin"

    auth_me = client.get("/api/v1/auth/me")
    assert auth_me.status_code == 200, auth_me.text
    assert auth_me.json()["user"]["primaryRole"] == "admin"
