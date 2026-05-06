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


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_personal_register_can_upgrade_to_shared_org_and_invite_member(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "local-first-owner@example.com",
            "fullName": "本地优先拥有者",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    owner_headers = {"Authorization": f"Bearer {register.json()['accessToken']}"}

    membership = client.get("/api/v1/account/membership", headers=owner_headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["isPersonalWorkspace"] is True

    created_org = client.post("/api/v1/orgs", json={"name": "益语测试组织"}, headers=owner_headers)
    assert created_org.status_code == 200, created_org.text
    assert created_org.json()["organizationName"] == "益语测试组织"
    assert created_org.json()["isPersonalWorkspace"] is False

    invitation = client.post(
        "/api/v1/org-invitations",
        json={"roleName": "研究员", "expiresInDays": 7, "maxUses": 1},
        headers=owner_headers,
    )
    assert invitation.status_code == 200, invitation.text
    invite_code = invitation.json()["code"]

    joiner = client.post(
        "/api/v1/auth/register",
        json={
            "email": "joiner@example.com",
            "fullName": "加入成员",
            "password": "Password123!",
        },
    )
    assert joiner.status_code == 200, joiner.text
    joiner_headers = {"Authorization": f"Bearer {joiner.json()['accessToken']}"}

    redeemed = client.post("/api/v1/org-invitations/redeem", json={"code": invite_code}, headers=joiner_headers)
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["organizationName"] == "益语测试组织"
    assert redeemed.json()["jobTitle"] == "研究员"
    assert redeemed.json()["isPersonalWorkspace"] is False


def test_import_local_structured_data_creates_lists_tasks_and_tags(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    owner_headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    response = client.post(
        "/api/v1/sync/import-local",
        json={
            "taskLists": [
                {"localId": "list-local-1", "name": "本地导入清单", "color": "#123456", "scope": "org"},
            ],
            "tasks": [
                {
                    "localId": "task-local-1",
                    "title": "导入后的结构化任务",
                    "description": "只同步结构化记录",
                    "priority": "high",
                    "listLocalId": "list-local-1",
                    "tags": ["同步", "组织"],
                }
            ],
        },
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["importedListCount"] == 1
    assert payload["importedTaskCount"] == 1
    assert payload["importedTagCount"] >= 1

    tasks = client.get("/api/v1/tasks", headers=owner_headers)
    assert tasks.status_code == 200, tasks.text
    imported_task = next(item for item in tasks.json()["tasks"] if item["sourceType"] == "local_import")
    assert imported_task["title"] == "导入后的结构化任务"
    assert "同步" in [tag["name"] for tag in imported_task["tags"]]
