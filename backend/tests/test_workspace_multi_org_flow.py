from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import get_active_sandbox, get_active_sandbox_setting  # noqa: E402


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


def test_multi_org_login_selection_creates_matching_workspace(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    state = client.app.state.app_state
    state.cloud_api_url = "https://cloud-a.example.test"
    state.db.set_setting("cloud_api_url", "https://cloud-a.example.test")

    def fake_cloud_request(method, url, **kwargs):
        if method == "POST" and url.endswith("/api/v1/auth/login"):
            return FakeCloudResponse(
                200,
                {
                    "organizationSelectionRequired": True,
                    "organizationSelectionToken": "select-token-1",
                    "organizations": [
                        {
                            "organizationId": "org_a",
                            "organizationName": "组织 A",
                            "memberId": "member_a",
                            "fullName": "多组织用户",
                            "email": "multi@example.com",
                            "primaryRole": "admin",
                            "accountStatus": "approved",
                            "membershipStatus": "approved",
                        },
                        {
                            "organizationId": "org_b",
                            "organizationName": "组织 B",
                            "memberId": "member_b",
                            "fullName": "多组织用户",
                            "email": "multi@example.com",
                            "primaryRole": "employee",
                            "accountStatus": "approved",
                            "membershipStatus": "approved",
                        },
                    ],
                },
            )
        if method == "POST" and url.endswith("/api/v1/auth/select-organization"):
            assert kwargs["json"]["organizationSelectionToken"] == "select-token-1"
            assert kwargs["json"]["organizationId"] == "org_b"
            return FakeCloudResponse(
                200,
                {
                    "accessToken": "access-org-b",
                    "refreshToken": "refresh-org-b",
                    "user": {
                        "id": "member_b",
                        "organizationId": "org_b",
                        "organizationName": "组织 B",
                        "email": "multi@example.com",
                        "fullName": "多组织用户",
                        "primaryRole": "employee",
                        "accountStatus": "approved",
                        "membershipStatus": "approved",
                    },
                },
            )
        if method == "GET" and url.endswith("/api/v1/me/org-membership"):
            return FakeCloudResponse(
                200,
                {
                    "hasOrganization": True,
                    "organizationId": "org_b",
                    "organizationName": "组织 B",
                    "membershipStatus": "approved",
                    "organizationWorkspaceClientId": "client-org-b",
                },
            )
        if method == "GET" and url.endswith("/api/v1/settings/org-ai-config/secret"):
            return FakeCloudResponse(403, {"detail": "forbidden"})
        if method == "GET" and url.endswith("/api/v1/settings/org-object-storage-config/secret"):
            return FakeCloudResponse(200, {"provider": "", "enabled": False, "credentials": {}, "extraConfig": {}})
        raise AssertionError(f"unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "multi@example.com", "password": "Password123!", "rememberMe": True},
    )
    assert login.status_code == 200, login.text
    login_payload = login.json()
    assert login_payload["authenticated"] is False
    assert login_payload["organizationSelectionRequired"] is True
    assert {org["organizationId"] for org in login_payload["organizations"]} == {"org_a", "org_b"}

    selected = client.post(
        "/api/v1/auth/select-organization",
        json={"organizationSelectionToken": "select-token-1", "organizationId": "org_b"},
    )
    assert selected.status_code == 200, selected.text
    payload = selected.json()
    assert payload["authenticated"] is True
    assert payload["user"]["organizationId"] == "org_b"

    active = get_active_sandbox(state.db)
    assert active.kind == "organization"
    assert active.organizationId == "org_b"
    assert active.organizationName == "组织 B"
    assert active.cloudApiUrl == "https://cloud-a.example.test"
    assert get_active_sandbox_setting(state.db, "cloud_access_token", "") == "access-org-b"
    assert get_active_sandbox_setting(state.db, "cloud_refresh_token", "") == "refresh-org-b"
