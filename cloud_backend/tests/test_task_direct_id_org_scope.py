from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, now_iso
from app.security import hash_password


FOREIGN_ORG_ID = "org_direct_id_foreign"
FOREIGN_USER_ID = "user_direct_id_foreign"
FOREIGN_LIST_ID = "list_direct_id_foreign"
FOREIGN_TASK_ID = "task_direct_id_foreign"


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    return TestClient(create_app())


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@yiyu-system.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_foreign_task(client: TestClient) -> None:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO organizations(id, name, slug, created_at, updated_at)
        VALUES(?, 'Direct ID 外组织', 'direct-id-foreign', ?, ?)
        """,
        (FOREIGN_ORG_ID, timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, ?, '外组织用户', ?, 'employee', 'approved', 'approved', ?, NULL, '[]', ?, ?)
        """,
        (
            FOREIGN_USER_ID,
            FOREIGN_ORG_ID,
            "direct-id-foreign@example.com",
            hash_password("Password123!"),
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO task_lists(
            id, organization_id, name, color, sort_order, is_default, scope, archived_at
        ) VALUES(?, ?, '外组织默认清单', '#999999', 0, 1, 'org', NULL)
        """,
        (FOREIGN_LIST_ID, FOREIGN_ORG_ID),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, creator_id, owner_id, priority, list_id,
            progress_status, source_type, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, '外组织机密任务', '不得跨组织读取或修改', ?, ?, 'normal', ?,
                 'todo', 'manual', '[]', '[]', ?, ?)
        """,
        (
            FOREIGN_TASK_ID,
            FOREIGN_ORG_ID,
            FOREIGN_USER_ID,
            FOREIGN_USER_ID,
            FOREIGN_LIST_ID,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at)
        VALUES('activity_direct_id_foreign', ?, ?, 'secret_event', '{"secret":"不可泄漏"}', ?)
        """,
        (FOREIGN_TASK_ID, FOREIGN_USER_ID, timestamp),
    )


def foreign_task_snapshot(client: TestClient) -> dict[str, object]:
    db = client.app.state.app_state.db
    task = db.fetchone(
        "SELECT title, progress_status, evidence_count, updated_at FROM tasks WHERE id = ?",
        (FOREIGN_TASK_ID,),
    )
    assert task is not None
    return {
        "task": tuple(task),
        "activity_count": int(
            db.scalar("SELECT COUNT(*) FROM task_activity_events WHERE task_id = ?", (FOREIGN_TASK_ID,)) or 0
        ),
        "note_count": int(db.scalar("SELECT COUNT(*) FROM task_notes WHERE task_id = ?", (FOREIGN_TASK_ID,)) or 0),
        "attachment_count": int(
            db.scalar("SELECT COUNT(*) FROM task_attachments WHERE task_id = ?", (FOREIGN_TASK_ID,)) or 0
        ),
        "link_count": int(db.scalar("SELECT COUNT(*) FROM task_org_links WHERE task_id = ?", (FOREIGN_TASK_ID,)) or 0),
    }


def assert_foreign_task_unchanged(client: TestClient, before: dict[str, object]) -> None:
    assert foreign_task_snapshot(client) == before


def test_cross_org_task_update_returns_404_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)

    response = client.patch(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}",
        headers=headers,
        json={"title": "越权修改"},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert_foreign_task_unchanged(client, before)


def test_cross_org_task_delete_returns_404_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)

    response = client.delete(f"/api/v1/tasks/{FOREIGN_TASK_ID}", headers=headers)

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert_foreign_task_unchanged(client, before)


def test_cross_org_task_attachment_upload_returns_404_without_db_or_file_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)
    data_dir = client.app.state.app_state.data_dir
    files_before = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*") if path.is_file())

    response = client.post(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/attachments",
        headers=headers,
        files={"file": ("foreign-secret.txt", b"must not persist", "text/plain")},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert_foreign_task_unchanged(client, before)
    files_after = sorted(path.relative_to(data_dir) for path in data_dir.rglob("*") if path.is_file())
    assert files_after == files_before


def test_cross_org_task_note_returns_404_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)

    response = client.post(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/note",
        headers=headers,
        json={"note": "越权备注"},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert_foreign_task_unchanged(client, before)


def test_cross_org_task_activity_returns_404_without_leaking_activity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)

    response = client.get(f"/api/v1/tasks/{FOREIGN_TASK_ID}/activity", headers=headers)

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert "不可泄漏" not in response.text
    assert_foreign_task_unchanged(client, before)


def test_cross_org_task_plan_link_patch_returns_404_without_implicit_link_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    before = foreign_task_snapshot(client)

    response = client.patch(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/plan-link",
        headers=headers,
        json={"focusItemId": None, "departmentPlanItemId": None},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert_foreign_task_unchanged(client, before)
