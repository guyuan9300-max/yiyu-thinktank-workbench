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
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_org_feishu_validate_and_delivery_profile_flow(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@example.org", "Admin123!")

    before = client.get("/api/v1/me/feishu-delivery-profile", headers=headers)
    assert before.status_code == 200, before.text
    before_payload = before.json()
    assert before_payload["deliveryStatus"] == "integration_pending"
    assert before_payload["readyForNotifications"] is False

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_token_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda **_: (None, "暂未在飞书通讯录中找到该手机号，请确认该成员已加入当前飞书组织且手机号填写正确。"),
    )

    saved = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_demo_app",
            "appSecret": "secret_demo",
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["enabled"] is True
    assert payload["appId"] == "cli_demo_app"
    assert payload["recentAudits"][0]["validationStatus"] == "success"
    assert "手机号" in (payload["lastValidationMessage"] or "")

    delivery = client.get("/api/v1/me/feishu-delivery-profile", headers=headers)
    assert delivery.status_code == 200, delivery.text
    delivery_payload = delivery.json()
    assert delivery_payload["deliveryStatus"] == "missing_mobile"
    assert delivery_payload["readyForNotifications"] is False

    saved_mobile = client.post(
        "/api/v1/me/feishu-delivery-profile",
        json={"mobile": "138 0013 8000"},
        headers=headers,
    )
    assert saved_mobile.status_code == 200, saved_mobile.text
    saved_mobile_payload = saved_mobile.json()
    assert saved_mobile_payload["mobile"] == "13800138000"
    assert saved_mobile_payload["normalizedMobile"] == "13800138000"
    assert saved_mobile_payload["deliveryStatus"] == "not_found"
    assert saved_mobile_payload["readyForNotifications"] is False
    assert "暂未在飞书通讯录中找到该手机号" in (saved_mobile_payload["blockedReason"] or "")


def test_invalid_feishu_config_does_not_override_existing_valid_config(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@example.org", "Admin123!")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    initial = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_good_app",
            "appSecret": "secret_good",
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
