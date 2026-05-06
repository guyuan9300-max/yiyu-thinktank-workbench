from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app, now_iso


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.app.state.app_state.db.set_setting("cloud_access_token", "")
    return client


def test_create_task_list_is_idempotent_for_active_name(tmp_path: Path):
    client = make_client(tmp_path)

    first = client.post(
        "/api/v1/task-lists",
        json={"name": "收集箱", "color": "#5B7BFE", "isDefault": True, "scope": "org"},
    )
    second = client.post(
        "/api/v1/task-lists",
        json={"name": " 收集箱 ", "color": "#5B7BFE", "isDefault": True, "scope": "org"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]


def test_repair_duplicate_task_lists_moves_tasks_and_deletes_empty_duplicates(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, scope, archived_at) VALUES(?, ?, ?, ?, ?, ?, NULL)",
        ("list_dup_repair", "收集箱", "#5B7BFE", 100, 1, "org"),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_name, progress_status,
            ddl, source_type, tags_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "task_dup_list",
            "重复清单上的任务",
            "",
            "doing",
            "normal",
            "list_dup_repair",
            "庆华",
            "todo",
            "待确认",
            "manual",
            "[]",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT OR REPLACE INTO task_settings(
            operator_id, default_list_id, default_priority, default_due_date_preset,
            default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
            auto_assign_self, updated_at
        ) VALUES(?, ?, 'normal', 'today', 'list', 'manual', 0, 'work', 1, ?)
        """,
        ("op_qh", "list_dup_repair", timestamp),
    )

    response = client.post("/api/v1/task-lists/repair-duplicates")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["movedTaskCount"] >= 1
    assert body["deletedListCount"] >= 1
    assert db.fetchone("SELECT id FROM task_lists WHERE id = ?", ("list_dup_repair",)) is None
    task_row = db.fetchone("SELECT list_id FROM tasks WHERE id = ?", ("task_dup_list",))
    assert task_row is not None
    assert task_row["list_id"] == "list-0"
    settings_row = db.fetchone("SELECT default_list_id FROM task_settings WHERE operator_id = ?", ("op_qh",))
    assert settings_row is not None
    assert settings_row["default_list_id"] == "list-0"


def test_task_settings_default_list_only_allows_inbox_or_org_task_destination(tmp_path: Path):
    client = make_client(tmp_path)

    invalid = client.post(
        "/api/v1/settings/tasks",
        json={"defaultListId": "plist-1", "defaultPriority": "normal", "defaultDueDatePreset": "none"},
    )
    valid = client.post(
        "/api/v1/settings/tasks",
        json={"defaultListId": "list-0", "defaultPriority": "normal", "defaultDueDatePreset": "none"},
    )

    assert invalid.status_code == 400, invalid.text
    assert "收集箱或组织任务" in invalid.text
    assert valid.status_code == 200, valid.text
    assert valid.json()["defaultListId"] == "list-0"
