from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_task_list_repair_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"

from app.main import DEFAULT_ORG_ID, create_app, now_iso  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_cloud_create_task_list_is_idempotent_for_active_name():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)

    first = client.post(
        "/api/v1/task-lists",
        json={"name": "收集箱", "color": "#5B7BFE", "isDefault": True, "scope": "org"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/task-lists",
        json={"name": " 收集箱 ", "color": "#5B7BFE", "isDefault": True, "scope": "org"},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]


def test_cloud_repair_duplicate_task_lists_moves_tasks_and_deletes_empty_duplicates():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        ("list_dup_repair", DEFAULT_ORG_ID, "收集箱", "#5B7BFE", 100, 1, "org"),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, creator_id, owner_id, priority, list_id,
            progress_status, source_type, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "task_dup_list",
            DEFAULT_ORG_ID,
            "重复清单上的任务",
            "",
            "user_admin",
            "user_admin",
            "normal",
            "list_dup_repair",
            "todo",
            "manual",
            "[]",
            "[]",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT OR REPLACE INTO task_settings(
            user_id, organization_id, default_list_id, default_priority, default_due_date_preset,
            default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
            auto_assign_self, updated_at
        ) VALUES(?, ?, ?, 'normal', 'today', 'list', 'manual', 0, 'work', 1, ?)
        """,
        ("user_admin", DEFAULT_ORG_ID, "list_dup_repair", timestamp),
    )

    response = client.post("/api/v1/task-lists/repair-duplicates", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["movedTaskCount"] >= 1
    assert body["deletedListCount"] >= 1
    assert db.fetchone("SELECT id FROM task_lists WHERE id = ?", ("list_dup_repair",)) is None
    task_row = db.fetchone("SELECT list_id FROM tasks WHERE id = ?", ("task_dup_list",))
    assert task_row is not None
    assert task_row["list_id"] == "list-0"
    settings_row = db.fetchone("SELECT default_list_id FROM task_settings WHERE user_id = ?", ("user_admin",))
    assert settings_row is not None
    assert settings_row["default_list_id"] == "list-0"


def test_cloud_task_settings_default_list_only_allows_inbox_or_org_task_destination():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)

    invalid = client.post(
        "/api/v1/settings/tasks",
        json={"defaultListId": "plist-1", "defaultPriority": "normal", "defaultDueDatePreset": "none"},
        headers=headers,
    )
    valid = client.post(
        "/api/v1/settings/tasks",
        json={"defaultListId": "list-0", "defaultPriority": "normal", "defaultDueDatePreset": "none"},
        headers=headers,
    )

    assert invalid.status_code == 400, invalid.text
    assert "收集箱或组织任务" in invalid.text
    assert valid.status_code == 200, valid.text
    assert valid.json()["defaultListId"] == "list-0"
