from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_ready(client: TestClient, *, base_url: str = "http://127.0.0.1:47830") -> None:
    state = client.app.state.app_state
    state.cloud_api_url = base_url
    state.db.set_setting("cloud_api_url", base_url)
    state.db.set_setting("cloud_access_token", "token_demo")


def test_apply_org_membership_verifies_cloud_persistence(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_ready(client)

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert (headers or {}).get("Authorization") == "Bearer token_demo"
        if url.endswith("/api/v1/me/org-membership/apply"):
            assert method == "POST"
            assert json == {"inviteCode": "INVITE_1"}
            return httpx.Response(
                200,
                json={"hasOrganization": False, "membershipStatus": "none"},
            )
        if url.endswith("/api/v1/me/org-membership"):
            assert method == "GET"
            return httpx.Response(
                200,
                json={
                    "hasOrganization": True,
                    "organizationId": "org_1",
                    "organizationName": "益语智库",
                    "departmentId": "dep_1",
                    "departmentName": "产品",
                    "membershipStatus": "approved",
                },
            )
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    resp = client.post("/api/v1/me/org-membership/apply", json={"inviteCode": "INVITE_1"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["hasOrganization"] is True
    assert payload["organizationId"] == "org_1"
    assert payload["membershipStatus"] != "none"


def test_apply_org_membership_raises_when_verify_stays_none(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_ready(client)

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert (headers or {}).get("Authorization") == "Bearer token_demo"
        if url.endswith("/api/v1/me/org-membership/apply"):
            return httpx.Response(200, json={"hasOrganization": False, "membershipStatus": "none"})
        if url.endswith("/api/v1/me/org-membership"):
            return httpx.Response(200, json={"hasOrganization": False, "membershipStatus": "none"})
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    resp = client.post("/api/v1/me/org-membership/apply", json={"inviteCode": "INVITE_2"})
    assert resp.status_code == 502, resp.text
    assert "云端尚未确认入组状态" in resp.text

