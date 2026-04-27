from __future__ import annotations

import json
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
    }
    db.set_setting("cloud_access_token", "expired-access")
    db.set_setting("cloud_refresh_token", "refresh-1")
    db.set_setting("cloud_session_user", json.dumps(user_payload, ensure_ascii=False))

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
    assert db.get_setting("cloud_access_token", "") == "fresh-access"
    assert db.get_setting("cloud_refresh_token", "") == "refresh-2"
