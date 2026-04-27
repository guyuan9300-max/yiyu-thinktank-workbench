from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_token(client: TestClient) -> None:
    client.app.state.app_state.db.set_setting("cloud_access_token", "token_demo")


def ensure_default_list(client: TestClient) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR IGNORE INTO task_lists(
            id, organization_id, name, color, sort_order, is_default, scope
        ) VALUES(?, '', ?, ?, 0, 1, 'org')
        """,
        ("list-0", "收集箱", "#5B7BFE"),
    )


def seed_cloud_shadow_task(client: TestClient, *, task_id: str, cloud_id: str, status: str = "inbox") -> None:
    ensure_default_list(client)
    client.app.state.app_state.db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, source_type, source_id,
            tags_json, tag_ids_json, created_at, updated_at, sync_status, cloud_id
        ) VALUES(?, '', ?, ?, ?, 'normal', 'list-0', '', ?, ?, ?, ?, ?, 60, 'COLLAB_SHARED', 'manual', NULL, '[]', '[]', ?, ?, 'synced', ?)
        """,
        (
            task_id,
            "乡基会报表",
            "本地旧影子",
            status,
            "user_emp",
            "普通员工",
            "todo",
            "周五",
            "2026-04-17T09:00:00",
            "2026-04-17T00:00:00",
            "2026-04-17T00:00:00",
            cloud_id,
        ),
    )


def test_confirm_task_writes_back_cloud_payload_to_existing_local_shadow(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)
    seed_cloud_shadow_task(client, task_id="task_local_1", cloud_id="task_cloud_1")

    cloud_task = {
        "id": "task_cloud_1",
        "title": "乡基会报表",
        "description": "云端已确认",
        "priority": "normal",
        "listId": "list-0",
        "listName": "收集箱",
        "listColor": "#5B7BFE",
        "dueDate": "2026-04-17T09:00:00",
        "durationMinutes": 60,
        "scopeMode": "COLLAB_SHARED",
        "ownerId": "user_emp",
        "ownerName": "普通员工",
        "sourceType": "manual",
        "progressStatus": "todo",
        "viewerInboxStatus": "accepted",
        "collaborators": [
            {
                "userId": "user_emp",
                "fullName": "普通员工",
                "email": "employee@example.com",
                "orderIndex": 0,
                "isOwner": True,
                "inboxStatus": "accepted",
                "handledAt": "2026-04-17T00:05:00",
            }
        ],
        "createdAt": "2026-04-17T00:00:00",
        "updatedAt": "2026-04-17T00:05:00",
        "tags": [],
    }
    board_payload = {
        "tasks": [cloud_task],
        "lists": [
            {
                "id": "list-0",
                "name": "收集箱",
                "color": "#5B7BFE",
                "sortOrder": 0,
                "isDefault": True,
                "scope": "org",
            }
        ],
        "tags": [],
    }

    def fake_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url.endswith("/api/v1/auth/me"):
            return httpx.Response(
                200,
                json={
                    "id": "user_emp",
                    "organizationId": "org_1",
                    "email": "employee@example.com",
                    "fullName": "普通员工",
                    "primaryRole": "employee",
                    "accountStatus": "approved",
                },
            )
        if method.upper() == "POST" and url.endswith("/api/v1/tasks/task_cloud_1/collaborators/user_emp/accept"):
            return httpx.Response(200, json=cloud_task)
        if method.upper() == "GET" and url.endswith("/api/v1/tasks"):
            return httpx.Response(200, json=board_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.post("/api/v1/tasks/task_cloud_1/confirm")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "todo"

    local_row = client.app.state.app_state.db.fetchone(
        "SELECT id, status, progress_status, description, cloud_id FROM tasks WHERE id = ?",
        ("task_local_1",),
    )
    assert local_row is not None
    assert local_row["status"] == "todo"
    assert local_row["progress_status"] == "todo"
    assert local_row["description"] == "云端已确认"
    assert local_row["cloud_id"] == "task_cloud_1"

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    tasks = {item["id"]: item for item in board.json()["tasks"]}
    assert tasks["task_local_1"]["status"] == "todo"


def test_task_board_pull_refreshes_existing_cloud_shadow_row(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)
    seed_cloud_shadow_task(client, task_id="task_local_2", cloud_id="task_cloud_2")

    board_payload = {
        "tasks": [
            {
                "id": "task_cloud_2",
                "title": "乡基会报表",
                "description": "云端最新版",
                "priority": "normal",
                "listId": "list-0",
                "listName": "收集箱",
                "listColor": "#5B7BFE",
                "dueDate": "2026-04-17T09:00:00",
                "durationMinutes": 60,
                "scopeMode": "COLLAB_SHARED",
                "ownerId": "user_emp",
                "ownerName": "普通员工",
                "sourceType": "manual",
                "progressStatus": "todo",
                "viewerInboxStatus": "accepted",
                "createdAt": "2026-04-17T00:00:00",
                "updatedAt": "2026-04-17T00:10:00",
                "tags": [],
            }
        ],
        "lists": [
            {
                "id": "list-0",
                "name": "收集箱",
                "color": "#5B7BFE",
                "sortOrder": 0,
                "isDefault": True,
                "scope": "org",
            }
        ],
        "tags": [],
    }

    def fake_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url.endswith("/api/v1/tasks"):
            return httpx.Response(200, json=board_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    tasks = {item["id"]: item for item in response.json()["tasks"]}
    assert tasks["task_local_2"]["status"] == "todo"

    local_row = client.app.state.app_state.db.fetchone(
        "SELECT id, status, description, cloud_id FROM tasks WHERE id = ?",
        ("task_local_2",),
    )
    assert local_row is not None
    assert local_row["status"] == "todo"
    assert local_row["description"] == "云端最新版"
    assert local_row["cloud_id"] == "task_cloud_2"
