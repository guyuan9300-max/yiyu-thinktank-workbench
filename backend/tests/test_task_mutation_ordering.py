from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    ensure_organization_sandbox_for_session,
    set_active_sandbox_setting,
)


BASE_URL = "https://cloud.example.test"


def make_client(data_dir: Path) -> TestClient:
    previous_worker_setting = os.environ.get("YIYU_DISABLE_STARTUP_WORKERS")
    os.environ["YIYU_DISABLE_STARTUP_WORKERS"] = "1"
    client = TestClient(create_app(data_dir))
    try:
        client.__enter__()
    finally:
        if previous_worker_setting is None:
            os.environ.pop("YIYU_DISABLE_STARTUP_WORKERS", None)
        else:
            os.environ["YIYU_DISABLE_STARTUP_WORKERS"] = previous_worker_setting
    return client


def seed_cloud_task(client: TestClient) -> tuple[str, str]:
    state = client.app.state.app_state
    user_payload = {
        "id": "user-owner",
        "organizationId": "org-task-mutation",
        "organizationName": "任务修改测试组织",
        "email": "owner@example.test",
        "fullName": "测试负责人",
        "primaryRole": "admin",
        "accountStatus": "approved",
        "membershipStatus": "approved",
    }
    workspace = ensure_organization_sandbox_for_session(
        state.db,
        organization_id="org-task-mutation",
        organization_name="任务修改测试组织",
        cloud_api_url=BASE_URL,
        cloud_instance_id="cloud-task-mutation",
    )
    state.cloud_api_url = BASE_URL
    set_active_sandbox_setting(state.db, "cloud_access_token", "access-token")
    set_active_sandbox_setting(state.db, "cloud_refresh_token", "refresh-token")
    set_active_sandbox_setting(state.db, "cloud_session_user", json.dumps(user_payload, ensure_ascii=False))
    set_active_sandbox_setting(state.db, "cloud_session_user_snapshot", json.dumps(user_payload, ensure_ascii=False))

    list_id = "list-task-mutation"
    state.db.execute(
        """
        INSERT INTO task_lists(
            id, sandbox_id, organization_id, name, color, is_default,
            sync_status, cloud_id
        ) VALUES(?, ?, ?, '收集箱', '#5B7BFE', 1, 'synced', ?)
        """,
        (list_id, workspace.id, "org-task-mutation", list_id),
    )
    timestamp = now_iso()
    task_id = "task-local-mutation"
    state.db.execute(
        """
        INSERT INTO tasks(
            id, sandbox_id, organization_id, title, description, status,
            priority, list_id, owner_id, owner_name, progress_status, ddl,
            scheduled_start_at, scheduled_end_at, duration_minutes, source_type,
            tags_json, tag_ids_json, created_at, updated_at, sync_status, cloud_id
        ) VALUES(
            ?, ?, ?, '拖动测试任务', '', 'todo', 'normal', ?, 'user-owner',
            '测试负责人', 'todo', '待确认', '2026-07-14T09:00',
            '2026-07-14T10:00', 60, 'manual', '[]', '[]', ?, ?, 'synced', ?
        )
        """,
        (
            task_id,
            workspace.id,
            "org-task-mutation",
            list_id,
            timestamp,
            timestamp,
            "task-cloud-mutation",
        ),
    )
    return workspace.id, task_id


def cloud_task_payload(body: dict, *, updated_at: str) -> dict:
    return {
        "id": "task-cloud-mutation",
        "organizationId": "org-task-mutation",
        "title": "拖动测试任务",
        "description": "",
        "priority": "normal",
        "listId": "list-task-mutation",
        "listName": "收集箱",
        "progressStatus": body.get("progressStatus", "todo"),
        "completedAt": body.get("completedAt"),
        "ownerId": "user-owner",
        "ownerName": "测试负责人",
        "scheduledStartAt": body.get("scheduledStartAt"),
        "scheduledEndAt": body.get("scheduledEndAt"),
        "durationMinutes": 60,
        "scopeMode": "COLLAB_SHARED",
        "collaborators": [],
        "tags": [],
        "createdAt": "2026-07-14T08:00:00",
        "updatedAt": updated_at,
    }


def test_late_older_patch_cannot_overwrite_latest_local_mutation(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    sandbox_id, task_id = seed_cloud_task(client)
    first_started = Event()
    release_first = Event()

    def fake_request(method: str, url: str, **kwargs):
        assert method == "PATCH"
        assert url == f"{BASE_URL}/api/v1/tasks/task-cloud-mutation"
        headers = kwargs.get("headers") or {}
        body = kwargs.get("json") or {}
        mutation_seq = int(headers["X-Yiyu-Local-Mutation-Seq"])
        if mutation_seq == 1:
            first_started.set()
            assert release_first.wait(timeout=5)
        return httpx.Response(
            200,
            json=cloud_task_payload(body, updated_at=f"2026-07-14T10:00:0{mutation_seq}"),
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            client.patch,
            f"/api/v1/tasks/{task_id}",
            json={"scheduledStartAt": "2026-07-14T11:00", "scheduledEndAt": "2026-07-14T12:00"},
            headers={"X-Yiyu-Client-Mutation-Id": "drag-1"},
        )
        assert first_started.wait(timeout=5)

        while_first_is_blocked = client.app.state.app_state.db.fetchone(
            "SELECT scheduled_start_at, sync_status, local_mutation_seq FROM tasks WHERE id = ? AND sandbox_id = ?",
            (task_id, sandbox_id),
        )
        assert while_first_is_blocked["scheduled_start_at"] == "2026-07-14T11:00"
        assert while_first_is_blocked["sync_status"] == "syncing"
        assert int(while_first_is_blocked["local_mutation_seq"]) == 1

        second = executor.submit(
            client.patch,
            f"/api/v1/tasks/{task_id}",
            json={"scheduledStartAt": "2026-07-14T14:00", "scheduledEndAt": "2026-07-14T15:00"},
            headers={"X-Yiyu-Client-Mutation-Id": "drag-2"},
        )
        second_response = second.result(timeout=5)
        assert second_response.status_code == 200, second_response.text
        release_first.set()
        first_response = first.result(timeout=5)
        assert first_response.status_code == 200, first_response.text

    final_row = client.app.state.app_state.db.fetchone(
        "SELECT scheduled_start_at, scheduled_end_at, sync_status, local_mutation_seq, pending_base_snapshot_json FROM tasks WHERE id = ? AND sandbox_id = ?",
        (task_id, sandbox_id),
    )
    assert final_row["scheduled_start_at"] == "2026-07-14T14:00"
    assert final_row["scheduled_end_at"] == "2026-07-14T15:00"
    assert final_row["sync_status"] == "synced"
    assert int(final_row["local_mutation_seq"]) == 2
    assert final_row["pending_base_snapshot_json"] == ""
    client.__exit__(None, None, None)


def test_client_operation_order_rejects_request_that_arrives_late(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    sandbox_id, task_id = seed_cloud_task(client)
    cloud_calls: list[dict] = []

    def fake_request(method: str, url: str, **kwargs):
        assert method == "PATCH"
        assert url == f"{BASE_URL}/api/v1/tasks/task-cloud-mutation"
        body = kwargs.get("json") or {}
        cloud_calls.append(body)
        return httpx.Response(
            200,
            json=cloud_task_payload(body, updated_at="2026-07-14T10:05:00"),
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    latest = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": "2026-07-17T14:00", "scheduledEndAt": "2026-07-17T15:00"},
        headers={
            "X-Yiyu-Client-Mutation-Id": "drag-latest",
            "X-Yiyu-Client-Mutation-Session": "renderer-session-a",
            "X-Yiyu-Client-Mutation-Order": "200",
        },
    )
    assert latest.status_code == 200, latest.text

    arrived_late = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": "2026-07-16T14:00", "scheduledEndAt": "2026-07-16T15:00"},
        headers={
            "X-Yiyu-Client-Mutation-Id": "drag-older",
            "X-Yiyu-Client-Mutation-Session": "renderer-session-a",
            "X-Yiyu-Client-Mutation-Order": "100",
        },
    )
    assert arrived_late.status_code == 200, arrived_late.text
    assert arrived_late.json()["scheduledStartAt"] == "2026-07-17T14:00"
    assert len(cloud_calls) == 1

    final_row = client.app.state.app_state.db.fetchone(
        """SELECT scheduled_start_at, scheduled_end_at,
                  last_client_mutation_session, last_client_mutation_order
           FROM tasks WHERE id = ? AND sandbox_id = ?""",
        (task_id, sandbox_id),
    )
    assert final_row["scheduled_start_at"] == "2026-07-17T14:00"
    assert final_row["scheduled_end_at"] == "2026-07-17T15:00"
    assert final_row["last_client_mutation_session"] == "renderer-session-a"
    assert int(final_row["last_client_mutation_order"]) == 200

    after_restart = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": "2026-07-18T14:00", "scheduledEndAt": "2026-07-18T15:00"},
        headers={
            "X-Yiyu-Client-Mutation-Id": "drag-new-session",
            "X-Yiyu-Client-Mutation-Session": "renderer-session-b",
            "X-Yiyu-Client-Mutation-Order": "1",
        },
    )
    assert after_restart.status_code == 200, after_restart.text
    assert after_restart.json()["scheduledStartAt"] == "2026-07-18T14:00"
    assert len(cloud_calls) == 2
    client.__exit__(None, None, None)


def test_late_completion_response_cannot_overwrite_restored_task(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    sandbox_id, task_id = seed_cloud_task(client)
    completion_started = Event()
    release_completion = Event()

    def fake_request(method: str, url: str, **kwargs):
        assert method == "PATCH"
        assert url == f"{BASE_URL}/api/v1/tasks/task-cloud-mutation"
        headers = kwargs.get("headers") or {}
        body = kwargs.get("json") or {}
        mutation_seq = int(headers["X-Yiyu-Local-Mutation-Seq"])
        if headers.get("X-Yiyu-Client-Mutation-Id") == "complete-1":
            completion_started.set()
            assert release_completion.wait(timeout=20)
        return httpx.Response(
            200,
            json=cloud_task_payload(body, updated_at=f"2026-07-14T10:10:0{mutation_seq}"),
        )

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        completion = executor.submit(
            client.patch,
            f"/api/v1/tasks/{task_id}",
            json={"progressStatus": "done", "completedAt": "2026-07-14T10:10:00"},
            headers={"X-Yiyu-Client-Mutation-Id": "complete-1"},
        )
        assert completion_started.wait(timeout=5)

        restored_request = executor.submit(
            client.patch,
            f"/api/v1/tasks/{task_id}",
            json={"progressStatus": "doing", "completedAt": None},
            headers={"X-Yiyu-Client-Mutation-Id": "restore-2"},
        )
        restored = restored_request.result(timeout=15)
        assert restored.status_code == 200, restored.text
        restored_body = restored.json()
        assert restored_body["status"] == "doing"
        assert restored_body["completedAt"] is None

        release_completion.set()
        completion_response = completion.result(timeout=5)
        assert completion_response.status_code == 200, completion_response.text

    final_row = client.app.state.app_state.db.fetchone(
        "SELECT progress_status, completed_at, sync_status, local_mutation_seq FROM tasks WHERE id = ? AND sandbox_id = ?",
        (task_id, sandbox_id),
    )
    assert final_row["progress_status"] == "doing"
    assert final_row["completed_at"] is None
    assert final_row["sync_status"] == "synced"
    assert int(final_row["local_mutation_seq"]) == 2
    client.__exit__(None, None, None)


def test_retryable_failure_keeps_latest_position_pending(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    sandbox_id, task_id = seed_cloud_task(client)

    monkeypatch.setattr(
        app_main.httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(503, json={"detail": "temporary outage"}),
    )
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": "2026-07-14T13:00", "scheduledEndAt": "2026-07-14T14:00"},
        headers={"X-Yiyu-Client-Mutation-Id": "drag-retry"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["scheduledStartAt"] == "2026-07-14T13:00"
    assert response.json()["syncStatus"] == "pending"
    row = client.app.state.app_state.db.fetchone(
        "SELECT scheduled_start_at, sync_status, pending_sync_action, cloud_payload_json, pending_base_snapshot_json FROM tasks WHERE id = ? AND sandbox_id = ?",
        (task_id, sandbox_id),
    )
    assert row["scheduled_start_at"] == "2026-07-14T13:00"
    assert row["sync_status"] == "pending"
    assert row["pending_sync_action"] == "update"
    assert "2026-07-14T13:00" in str(row["cloud_payload_json"])
    assert str(row["pending_base_snapshot_json"]).strip()
    client.__exit__(None, None, None)


def test_authoritative_rejection_rolls_back_only_current_mutation(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path / "data")
    sandbox_id, task_id = seed_cloud_task(client)

    monkeypatch.setattr(
        app_main.httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(422, json={"detail": "time range rejected"}),
    )
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": "2026-07-14T16:00", "scheduledEndAt": "2026-07-14T15:00"},
        headers={"X-Yiyu-Client-Mutation-Id": "drag-invalid"},
    )

    assert response.status_code == 422, response.text
    row = client.app.state.app_state.db.fetchone(
        "SELECT scheduled_start_at, scheduled_end_at, sync_status, pending_sync_action, pending_base_snapshot_json FROM tasks WHERE id = ? AND sandbox_id = ?",
        (task_id, sandbox_id),
    )
    assert row["scheduled_start_at"] == "2026-07-14T09:00"
    assert row["scheduled_end_at"] == "2026-07-14T10:00"
    assert row["sync_status"] == "synced"
    assert row["pending_sync_action"] == ""
    assert row["pending_base_snapshot_json"] == ""
    client.__exit__(None, None, None)
