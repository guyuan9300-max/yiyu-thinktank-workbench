from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app


BASE_URL = "http://127.0.0.1:47830"


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_session(client: TestClient, *, user_id: str = "user_guyuan") -> None:
    db = client.app.state.app_state.db
    db.set_setting("cloud_access_token", "token_demo")
    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": user_id,
                "organizationId": "org_1",
                "email": "guyuanyuan@example.com",
                "fullName": "顾源源",
                "primaryRole": "admin",
                "accountStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )


def seed_task_list(client: TestClient) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR IGNORE INTO task_lists(id, name, color, sort_order, is_default, scope)
        VALUES('list-0', '收集箱', '#5B7BFE', 0, 1, 'org')
        """
    )


def seed_task_with_collaborator(
    client: TestClient,
    *,
    task_id: str = "task_collab_1",
    status: str = "inbox",
    progress_status: str = "todo",
    collaborator_status: str = "pending",
) -> None:
    db = client.app.state.app_state.db
    seed_task_list(client)
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, progress_status, priority, list_id, owner_name,
            ddl, source_type, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'normal', 'list-0', '顾源源', '待确认', 'manual', '[]', '[]', '2026-04-27T09:00:00', '2026-04-27T09:00:00')
        """,
        (task_id, "协作任务", "需要协作者确认", status, progress_status),
    )
    db.execute(
        """
        INSERT INTO task_collaborators(
            task_id, organization_id, user_id, full_name, email, order_index, is_owner,
            inbox_status, created_at, updated_at
        ) VALUES(?, 'org_1', 'user_guyuan', '顾源源', 'guyuanyuan@example.com', 0, 0, ?, '2026-04-27T09:00:00', '2026-04-27T09:00:00')
        """,
        (task_id, collaborator_status),
    )


def test_cloud_event_line_list_upserts_local_shadow(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == f"{BASE_URL}/api/v1/event-lines":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "eline_brand_platform",
                        "organizationId": "org_1",
                        "name": "品牌传播平台",
                        "kind": "custom",
                        "status": "active",
                        "visibilityScope": "project_public",
                        "summary": "推进品牌传播平台合作。",
                        "primaryClientId": "client_foundation",
                        "primaryClientName": "乡村发展基金会",
                        "createdAt": "2026-04-20T09:00:00",
                        "updatedAt": "2026-04-27T09:00:00",
                    }
                ],
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/event-lines")
    assert response.status_code == 200, response.text
    assert response.json()[0]["id"] == "eline_brand_platform"

    row = client.app.state.app_state.db.fetchone(
        "SELECT id, name, primary_client_id, sync_status FROM event_lines WHERE id = ?",
        ("eline_brand_platform",),
    )
    assert row is not None
    assert row["name"] == "品牌传播平台"
    assert row["primary_client_id"] == "client_foundation"
    assert row["sync_status"] == "synced"


def test_task_create_self_heals_cloud_only_event_line(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_task_list(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == f"{BASE_URL}/api/v1/event-lines/eline_cloud_only":
            return httpx.Response(
                200,
                json={
                    "eventLine": {
                        "id": "eline_cloud_only",
                        "organizationId": "org_1",
                        "name": "品牌传播平台",
                        "kind": "custom",
                        "status": "active",
                        "primaryClientId": "client_foundation",
                        "primaryClientName": "乡村发展基金会",
                        "createdAt": "2026-04-20T09:00:00",
                        "updatedAt": "2026-04-27T09:00:00",
                    }
                },
            )
        if method.upper() == "POST" and url == f"{BASE_URL}/api/v1/tasks":
            payload = kwargs.get("json") or {}
            return httpx.Response(
                200,
                json={
                    "id": "cloud_task_saved",
                    "title": payload.get("title"),
                    "description": payload.get("description"),
                    "priority": payload.get("priority") or "normal",
                    "progressStatus": "todo",
                    "listId": "list-0",
                    "listName": "收集箱",
                    "listColor": "#5B7BFE",
                    "eventLineId": payload.get("eventLineId"),
                    "clientId": payload.get("clientId"),
                    "ownerName": "顾源源",
                    "sourceType": "manual",
                    "collaborators": [],
                    "createdAt": "2026-04-27T09:10:00",
                    "updatedAt": "2026-04-27T09:10:00",
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "乡村发展基金会传播平台合作协议",
            "desc": "推进合作协议沟通。",
            "priority": "high",
            "listId": "list-0",
            "eventLineId": "eline_cloud_only",
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["eventLineId"] == "eline_cloud_only"

    row = client.app.state.app_state.db.fetchone(
        "SELECT id, name, primary_client_id FROM event_lines WHERE id = ?",
        ("eline_cloud_only",),
    )
    assert row is not None
    assert row["name"] == "品牌传播平台"
    assert row["primary_client_id"] == "client_foundation"


def test_local_task_records_hydrate_collaboration_state(tmp_path: Path):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    client.app.state.app_state.db.set_setting("cloud_access_token", "")
    seed_task_with_collaborator(client, status="doing", progress_status="doing")

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    task = next(item for item in response.json()["tasks"] if item["id"] == "task_collab_1")
    assert task["collaborators"][0]["userId"] == "user_guyuan"
    assert task["collaborationSummary"]["pending"] == 1
    assert task["viewerInboxStatus"] == "pending"


def test_confirm_and_reject_fallback_update_collaborator_rows(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_task_with_collaborator(client, task_id="task_confirm", status="inbox", progress_status="todo")
    seed_task_with_collaborator(client, task_id="task_reject", status="inbox", progress_status="todo")

    def unavailable_cloud(method: str, url: str, **kwargs):
        return httpx.Response(503, json={"detail": "cloud unavailable"})

    monkeypatch.setattr(app_main.httpx, "request", unavailable_cloud)

    confirmed = client.post("/api/v1/tasks/task_confirm/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "todo"
    assert confirmed.json()["viewerInboxStatus"] == "accepted"
    confirm_row = client.app.state.app_state.db.fetchone(
        "SELECT inbox_status, handled_at FROM task_collaborators WHERE task_id = ? AND user_id = ?",
        ("task_confirm", "user_guyuan"),
    )
    assert confirm_row["inbox_status"] == "accepted"
    assert confirm_row["handled_at"]

    rejected = client.post("/api/v1/tasks/task_reject/reject", json={"reason": "边界不清楚"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["viewerInboxStatus"] == "returned"
    reject_row = client.app.state.app_state.db.fetchone(
        "SELECT inbox_status, return_reason, handled_at FROM task_collaborators WHERE task_id = ? AND user_id = ?",
        ("task_reject", "user_guyuan"),
    )
    assert reject_row["inbox_status"] == "returned"
    assert reject_row["return_reason"] == "边界不清楚"
    assert reject_row["handled_at"]


def test_completed_tasks_repair_pending_collaborators_on_list(tmp_path: Path):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    client.app.state.app_state.db.set_setting("cloud_access_token", "")
    seed_task_with_collaborator(
        client,
        task_id="task_done_with_pending",
        status="done",
        progress_status="done",
        collaborator_status="pending",
    )

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    task = next(item for item in response.json()["tasks"] if item["id"] == "task_done_with_pending")
    assert task["status"] == "done"
    assert task["collaborationSummary"]["pending"] == 0
    assert task["collaborationSummary"]["accepted"] == 1
