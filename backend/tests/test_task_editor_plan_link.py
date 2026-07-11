from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    ensure_organization_sandbox_for_session,
    set_active_sandbox_setting,
)


BASE_URL = "http://127.0.0.1:47830"


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_session(client: TestClient) -> None:
    user_payload = {
        "id": "user_owner",
        "organizationId": "org_default",
        "email": "owner@example.com",
        "fullName": "当前负责人",
        "primaryRole": "employee",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    state = client.app.state.app_state
    state.cloud_api_url = BASE_URL
    ensure_organization_sandbox_for_session(
        state.db,
        organization_id="org_default",
        organization_name="默认组织",
        cloud_api_url=BASE_URL,
    )
    set_active_sandbox_setting(state.db, "cloud_access_token", "token_owner")
    set_active_sandbox_setting(state.db, "cloud_session_user", json.dumps(user_payload, ensure_ascii=False))


def test_create_task_returns_owner_in_collaborators(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "负责人不应在保存后消失",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-06-15",
            "ownerId": "user_owner",
            "ownerName": "当前负责人",
            "collaboratorIds": ["user_owner"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ownerId"] == "user_owner"
    assert payload["ownerName"] == "当前负责人"
    assert payload["collaborators"] == [
        {
            "userId": "user_owner",
            "fullName": "当前负责人",
            "email": "",
            "orderIndex": 0,
            "isOwner": True,
            "inboxStatus": "accepted",
            "returnReason": None,
            "handledAt": payload["collaborators"][0]["handledAt"],
        }
    ]
    assert payload["collaborators"][0]["handledAt"]


def test_read_plan_link_treats_unsynced_cloud_task_404_as_empty(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_cloud_session(client)
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_id, owner_name,
            ddl, due_date, source_type, tags_json, sync_status, created_at, updated_at
        ) VALUES(?, ?, '', 'todo', 'normal', 'list-0', ?, ?, '待确认', ?, 'manual', '[]', 'syncing', ?, ?)
        """,
        ("task_local_pending", "刚创建的云端任务", "user_owner", "当前负责人", "2026-06-15", timestamp, timestamp),
    )

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert method == "GET"
        assert url == f"{BASE_URL}/api/v1/tasks/task_local_pending/plan-link"
        assert headers == {"Authorization": "Bearer token_owner"}
        return httpx.Response(404, json={"detail": "Task not found"})

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/tasks/task_local_pending/plan-link")

    assert response.status_code == 200, response.text
    assert response.json() is None


def test_patch_plan_link_uses_cloud_id_mapping(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_cloud_session(client)
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO tasks(
            id, cloud_id, title, description, status, priority, list_id, owner_id, owner_name,
            ddl, due_date, source_type, tags_json, sync_status, created_at, updated_at
        ) VALUES(?, ?, ?, '', 'todo', 'normal', 'list-0', ?, ?, '待确认', ?, 'manual', '[]', 'synced', ?, ?)
        """,
        (
            "task_local_synced",
            "task_cloud_synced",
            "已同步的任务",
            "user_owner",
            "当前负责人",
            "2026-06-15",
            timestamp,
            timestamp,
        ),
    )

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        assert method == "PATCH"
        assert url == f"{BASE_URL}/api/v1/tasks/task_cloud_synced/plan-link"
        assert headers == {"Authorization": "Bearer token_owner"}
        assert json == {
            "departmentPlanItemId": "plan_item_1",
            "focusItemId": None,
            "linkedBy": "manager",
            "confidence": 1.0,
        }
        return httpx.Response(
            200,
            json={
                "taskId": "task_cloud_synced",
                "departmentPlanItemId": "plan_item_1",
                "focusItemId": None,
                "linkedBy": "manager",
                "confidence": 1.0,
                "updatedAt": timestamp,
            },
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.patch(
        "/api/v1/tasks/task_local_synced/plan-link",
        json={"departmentPlanItemId": "plan_item_1", "focusItemId": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["taskId"] == "task_cloud_synced"
