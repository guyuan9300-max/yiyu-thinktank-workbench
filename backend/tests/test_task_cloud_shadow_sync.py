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
    client.app.state.app_state.cloud_api_url = BASE_URL
    db.set_setting("cloud_api_url", BASE_URL)
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


def seed_client(client: TestClient, *, client_id: str = "client_foundation", name: str = "乡村发展基金会") -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, '', '', 'foundation', '', '', '#5B7BFE', '2026-04-20T09:00:00', '2026-04-20T09:00:00')
        """,
        (client_id, name),
    )


def seed_event_line(
    client: TestClient,
    *,
    event_line_id: str = "eline_local_only",
    name: str = "云南儿童资助研究",
    client_id: str = "client_foundation",
    sync_status: str = "local",
    cloud_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO event_lines(
            id, name, kind, status, visibility_scope, primary_client_id, primary_client_name,
            participant_ids_json, created_at, updated_at, sync_status, cloud_id, pending_sync_action, last_sync_error
        ) VALUES(?, ?, 'custom', 'active', 'project_public', ?, ?, '[]', '2026-04-20T09:00:00', '2026-04-27T09:00:00', ?, ?, '', '')
        """,
        (event_line_id, name, client_id, "乡村发展基金会", sync_status, cloud_id),
    )


class SelectiveInlineThread:
    def __init__(self, target=None, args=(), kwargs=None, **_options):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self) -> None:
        if getattr(self.target, "__name__", "") == "_try_cloud_sync_task":
            self.target(*self.args, **self.kwargs)


def seed_task_with_collaborator(
    client: TestClient,
    *,
    task_id: str = "task_collab_1",
    status: str = "inbox",
    progress_status: str = "todo",
    collaborator_status: str = "pending",
    sync_status: str = "local",
    cloud_id: str | None = None,
) -> None:
    db = client.app.state.app_state.db
    seed_task_list(client)
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, progress_status, priority, list_id, owner_name,
            ddl, source_type, tags_json, tag_ids_json, sync_status, cloud_id, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'normal', 'list-0', '顾源源', '待确认', 'manual', '[]', '[]', ?, ?, '2026-04-27T09:00:00', '2026-04-27T09:00:00')
        """,
        (task_id, "协作任务", "需要协作者确认", status, progress_status, sync_status, cloud_id),
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


def test_event_line_list_returns_local_merged_view_when_cloud_available(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_client(client, name="士平基金会")
    seed_event_line(client, name="云南儿童资助研究", client_id="client_foundation")

    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == f"{BASE_URL}/api/v1/event-lines":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "eline_cloud_synced",
                        "organizationId": "org_1",
                        "name": "云端项目线",
                        "kind": "custom",
                        "status": "active",
                        "visibilityScope": "project_public",
                        "createdAt": "2026-04-21T09:00:00",
                        "updatedAt": "2026-04-27T09:00:00",
                    }
                ],
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/event-lines")
    assert response.status_code == 200, response.text
    event_lines = {item["id"]: item for item in response.json()}
    assert "eline_cloud_synced" in event_lines
    assert "eline_local_only" in event_lines
    assert event_lines["eline_local_only"]["primaryClientName"] == "士平基金会"
    assert event_lines["eline_local_only"]["syncStatus"] == "local"


def test_delete_event_line_uses_cloud_id_and_blocks_cloud_resurrection(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_client(client, name="日慈基金会")
    seed_event_line(
        client,
        event_line_id="eline_local_shadow",
        name="日慈基金会跟笑雨老师核对她的教师项目进度。",
        client_id="client_foundation",
        sync_status="synced",
        cloud_id="cloud_eline_shadow",
    )
    requests: list[tuple[str, str]] = []

    def fake_cloud_request(method: str, url: str, **kwargs):
        method = method.upper()
        requests.append((method, url))
        if method == "DELETE" and url == f"{BASE_URL}/api/v1/event-lines/cloud_eline_shadow":
            return httpx.Response(405, json={"detail": "DELETE not supported"})
        if method == "PATCH" and url == f"{BASE_URL}/api/v1/event-lines/cloud_eline_shadow":
            payload = kwargs.get("json") or {}
            assert payload.get("status") == "archived"
            return httpx.Response(
                200,
                json={
                    "id": "cloud_eline_shadow",
                    "organizationId": "org_1",
                    "name": "日慈基金会跟笑雨老师核对她的教师项目进度。",
                    "kind": "custom",
                    "status": "archived",
                    "primaryClientId": "client_foundation",
                    "primaryClientName": "日慈基金会",
                    "createdAt": "2026-03-24T12:35:18",
                    "updatedAt": "2026-03-24T12:37:54",
                },
            )
        if method == "GET" and url == f"{BASE_URL}/api/v1/event-lines":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "cloud_eline_shadow",
                        "organizationId": "org_1",
                        "name": "日慈基金会跟笑雨老师核对她的教师项目进度。",
                        "kind": "custom",
                        "status": "archived",
                        "primaryClientId": "client_foundation",
                        "primaryClientName": "日慈基金会",
                        "createdAt": "2026-03-24T12:35:18",
                        "updatedAt": "2026-03-24T12:37:54",
                    }
                ],
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.delete("/api/v1/event-lines/eline_local_shadow")
    assert response.status_code == 200, response.text
    assert ("DELETE", f"{BASE_URL}/api/v1/event-lines/cloud_eline_shadow") in requests
    assert ("PATCH", f"{BASE_URL}/api/v1/event-lines/cloud_eline_shadow") in requests

    db = client.app.state.app_state.db
    assert db.fetchone("SELECT id FROM event_lines WHERE id = ?", ("eline_local_shadow",)) is None
    list_response = client.get("/api/v1/event-lines")
    assert list_response.status_code == 200, list_response.text
    ids = {item["id"] for item in list_response.json()}
    assert "eline_local_shadow" not in ids
    assert "cloud_eline_shadow" not in ids
    assert db.fetchone(
        "SELECT cloud_id FROM event_line_delete_tombstones WHERE cloud_id = ?",
        ("cloud_eline_shadow",),
    ) is not None


def test_event_line_create_cloud_failure_marks_pending_and_visible(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_client(client, name="士平基金会")

    def unavailable_cloud(method: str, url: str, **kwargs):
        if method.upper() == "POST" and url == f"{BASE_URL}/api/v1/event-lines":
            return httpx.Response(503, json={"detail": "cloud unavailable"})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", unavailable_cloud)

    response = client.post(
        "/api/v1/event-lines",
        json={"name": "云南儿童资助研究", "primaryClientId": "client_foundation"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "云南儿童资助研究"
    assert payload["primaryClientName"] == "士平基金会"
    assert payload["syncStatus"] == "pending"
    assert payload["pendingSyncAction"] == "create"
    assert "cloud unavailable" in payload["lastSyncError"]


def test_task_cloud_sync_resolves_local_only_event_line_cloud_id_first(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_client(client)
    seed_task_list(client)
    seed_event_line(client, event_line_id="eline_local_only", client_id="client_foundation")
    monkeypatch.setattr(app_main, "Thread", SelectiveInlineThread)
    requests: list[tuple[str, str, dict]] = []

    def fake_cloud_request(method: str, url: str, **kwargs):
        payload = kwargs.get("json") or {}
        requests.append((method.upper(), url, payload))
        if method.upper() == "GET" and url == f"{BASE_URL}/api/v1/event-lines/eline_local_only":
            return httpx.Response(404, json={"detail": "Event line not found"})
        if method.upper() == "POST" and url == f"{BASE_URL}/api/v1/event-lines":
            assert payload.get("id") == "eline_local_only"
            return httpx.Response(
                200,
                json={
                    **payload,
                    "id": "cloud_eline_local_only",
                    "organizationId": "org_1",
                    "createdAt": "2026-04-27T09:00:00",
                    "updatedAt": "2026-04-27T09:00:00",
                },
            )
        if method.upper() == "PATCH" and url == f"{BASE_URL}/api/v1/event-lines/cloud_eline_local_only":
            return httpx.Response(
                200,
                json={
                    **payload,
                    "id": "cloud_eline_local_only",
                    "organizationId": "org_1",
                    "createdAt": "2026-04-27T09:00:00",
                    "updatedAt": "2026-04-27T09:00:01",
                },
            )
        if method.upper() == "POST" and url == f"{BASE_URL}/api/v1/tasks":
            assert payload.get("eventLineId") == "cloud_eline_local_only"
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
            "clientId": "client_foundation",
            "eventLineId": "eline_local_only",
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["eventLineId"] == "eline_local_only"
    assert any(method == "POST" and url.endswith("/api/v1/tasks") and payload.get("eventLineId") == "cloud_eline_local_only" for method, url, payload in requests)
    event_line_row = client.app.state.app_state.db.fetchone("SELECT cloud_id, sync_status FROM event_lines WHERE id = ?", ("eline_local_only",))
    assert event_line_row["cloud_id"] == "cloud_eline_local_only"
    assert event_line_row["sync_status"] == "synced"


def test_client_rename_refreshes_event_line_name_and_marks_cloud_update(tmp_path: Path):
    client = make_client(tmp_path)
    seed_client(client, name="士平基金会")
    seed_event_line(
        client,
        event_line_id="eline_synced",
        name="云南儿童资助研究",
        client_id="client_foundation",
        sync_status="synced",
        cloud_id="cloud_eline_synced",
    )

    response = client.put(
        "/api/v1/clients/client_foundation",
        json={
            "name": "士平公益基金会",
            "alias": "",
            "domain": "",
            "type": "foundation",
            "intro": "",
            "stage": "",
        },
    )
    assert response.status_code == 200, response.text

    event_lines = client.get("/api/v1/event-lines")
    assert event_lines.status_code == 200, event_lines.text
    event_line = next(item for item in event_lines.json() if item["id"] == "eline_synced")
    assert event_line["primaryClientName"] == "士平公益基金会"
    assert event_line["syncStatus"] == "pending"
    assert event_line["pendingSyncAction"] == "update"


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


def test_cloud_backed_confirm_does_not_fake_success_when_cloud_fails(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_task_with_collaborator(
        client,
        task_id="task_cloud_confirm",
        status="inbox",
        progress_status="todo",
        sync_status="synced",
        cloud_id="cloud_task_confirm",
    )

    def unavailable_cloud(method: str, url: str, **kwargs):
        return httpx.Response(503, json={"detail": "cloud unavailable"})

    monkeypatch.setattr(app_main.httpx, "request", unavailable_cloud)

    confirmed = client.post("/api/v1/tasks/task_cloud_confirm/confirm")
    assert confirmed.status_code == 503, confirmed.text
    assert "云端协作确认失败" in confirmed.text
    row = client.app.state.app_state.db.fetchone(
        """
        SELECT t.status, tc.inbox_status
        FROM tasks t
        JOIN task_collaborators tc ON tc.task_id = t.id
        WHERE t.id = ? AND tc.user_id = ?
        """,
        ("task_cloud_confirm", "user_guyuan"),
    )
    assert row["status"] == "inbox"
    assert row["inbox_status"] == "pending"


def test_cloud_confirm_success_updates_local_inbox_state_even_when_shadow_upsert_skips(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_session(client)
    seed_task_with_collaborator(
        client,
        task_id="task_cloud_pending_local",
        status="inbox",
        progress_status="todo",
        sync_status="pending",
        cloud_id="cloud_task_pending_local",
    )

    def cloud_accept(method: str, url: str, **kwargs):
        if method == "GET" and url.endswith("/api/v1/auth/me"):
            return httpx.Response(
                200,
                json={
                    "id": "user_guyuan",
                    "organizationId": "org_1",
                    "email": "guyuanyuan@example.com",
                    "fullName": "顾源源",
                    "primaryRole": "admin",
                    "accountStatus": "approved",
                },
            )
        assert method == "POST"
        assert url.endswith("/api/v1/tasks/cloud_task_pending_local/collaborators/user_guyuan/accept")
        return httpx.Response(
            200,
            json={
                "id": "cloud_task_pending_local",
                "organizationId": "org_1",
                "title": "协作任务",
                "description": "需要协作者确认",
                "priority": "normal",
                "listId": "list-0",
                "listName": "收件箱",
                "listColor": "#5B7BFE",
                "creatorId": "user_guyuan",
                "ownerId": "user_guyuan",
                "ownerName": "顾源源",
                "progressStatus": "todo",
                "scopeMode": "COLLAB_SHARED",
                "sourceType": "manual",
                "durationMinutes": 60,
                "viewerInboxStatus": "accepted",
                "collaborators": [
                    {
                        "userId": "user_guyuan",
                        "fullName": "顾源源",
                        "email": "guyuanyuan@example.com",
                        "orderIndex": 0,
                        "isOwner": False,
                        "inboxStatus": "accepted",
                        "handledAt": "2026-04-27T09:01:00",
                    }
                ],
                "createdAt": "2026-04-27T09:00:00",
                "updatedAt": "2026-04-27T09:01:00",
            },
        )

    monkeypatch.setattr(app_main.httpx, "request", cloud_accept)

    confirmed = client.post("/api/v1/tasks/task_cloud_pending_local/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "todo"
    assert confirmed.json()["viewerInboxStatus"] == "accepted"
    row = client.app.state.app_state.db.fetchone(
        """
        SELECT t.status, tc.inbox_status
        FROM tasks t
        JOIN task_collaborators tc ON tc.task_id = t.id
        WHERE t.id = ? AND tc.user_id = ?
        """,
        ("task_cloud_pending_local", "user_guyuan"),
    )
    assert row["status"] == "todo"
    assert row["inbox_status"] == "accepted"


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
