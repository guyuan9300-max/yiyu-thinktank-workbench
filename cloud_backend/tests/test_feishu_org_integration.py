from __future__ import annotations

import sys
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    monkeypatch.setenv("YIYU_CLOUD_PUBLIC_BASE_URL", "https://workbench.example.com")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_org_feishu_validate_and_member_authorization_ready(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: "app_token_demo")

    saved = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_demo_app",
            "appSecret": "secret_demo",
            "callbackMode": "cloud_relay",
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["enabled"] is True
    assert payload["authorizationReady"] is True
    assert payload["effectiveCallbackUrl"].startswith("https://workbench.example.com/")
    assert payload["recentAudits"][0]["validationStatus"] == "success"

    authorization = client.get("/api/v1/me/feishu-authorization", headers=headers)
    assert authorization.status_code == 200, authorization.text
    authorization_payload = authorization.json()
    assert authorization_payload["linked"] is False
    assert authorization_payload["readyForAuthorization"] is True
    assert authorization_payload["organizationId"] == payload["organizationId"]


def test_invalid_feishu_config_does_not_override_existing_valid_config(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: "app_token_demo")
    initial = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_good_app",
            "appSecret": "secret_good",
            "callbackMode": "cloud_relay",
        },
        headers=headers,
    )
    assert initial.status_code == 200, initial.text

    def raise_invalid(**_kwargs):
        raise HTTPException(status_code=400, detail="飞书应用校验失败")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", raise_invalid)

    failed = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_bad_app",
            "appSecret": "secret_bad",
            "callbackMode": "cloud_relay",
        },
        headers=headers,
    )
    assert failed.status_code == 400, failed.text

    current = client.get("/api/v1/org-integrations/feishu", headers=headers)
    assert current.status_code == 200, current.text
    current_payload = current.json()
    assert current_payload["appId"] == "cli_good_app"
    assert current_payload["enabled"] is True
    audit_statuses = {item["validationStatus"] for item in current_payload["recentAudits"]}
    assert "failed" in audit_statuses
    assert "success" in audit_statuses
