from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")
    return TestClient(create_app())


def test_cloud_registration_without_organization_name_uses_default_name(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "local-first-owner@example.com",
            "phone": "13800138101",
            "fullName": "本地优先拥有者",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    owner_headers = {"Authorization": f"Bearer {register.json()['accessToken']}"}

    membership = client.get("/api/v1/me/org-membership", headers=owner_headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["organizationName"] == "本地优先拥有者 的组织"
    assert membership.json()["membershipStatus"] == "none"
    assert membership.json()["hasOrganization"] is False

    blocked_tasks = client.get("/api/v1/tasks", headers=owner_headers)
    assert blocked_tasks.status_code == 403
    assert "组织身份尚未确认" in blocked_tasks.text


def test_cloud_registration_uses_local_organization_name(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "local-org-name@example.com",
            "phone": "13800138102",
            "fullName": "本机身份用户",
            "password": "Password123!",
            "organizationName": "本机初始化组织",
        },
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['accessToken']}"}

    membership = client.get("/api/v1/me/org-membership", headers=headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["organizationName"] == "本机初始化组织"
    assert membership.json()["membershipStatus"] == "none"
    assert membership.json()["hasOrganization"] is False


def test_cloud_registration_conflicting_email_returns_binding_guidance(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    first = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing-cloud@example.com",
            "phone": "13800138103",
            "fullName": "已有云账号",
            "password": "Password123!",
        },
    )
    assert first.status_code == 200, first.text

    conflict = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing-cloud@example.com",
            "phone": "13800138104",
            "fullName": "重复云账号",
            "password": "Password123!",
        },
    )
    assert conflict.status_code == 409
    assert "登录已有云账号绑定" in conflict.text


def test_cloud_registration_invalid_invite_returns_clear_error(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-invite@example.com",
            "phone": "13800138105",
            "fullName": "无效邀请码用户",
            "password": "Password123!",
            "inviteCode": "not-a-real-invite",
        },
    )
    assert response.status_code == 400
    assert "邀请码无效" in response.text
