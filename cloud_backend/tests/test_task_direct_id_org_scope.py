from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DEFAULT_ORG_ID, create_app, now_iso
from app.security import hash_password


FOREIGN_ORG_ID = "org_direct_id_foreign"
FOREIGN_USER_ID = "user_direct_id_foreign"
FOREIGN_LIST_ID = "list_direct_id_foreign"
FOREIGN_TASK_ID = "task_direct_id_foreign"
SAME_ORG_TASK_ID = "task_direct_id_same_org"
SAME_ORG_USERS = {
    "creator": ("user_direct_id_creator", "direct-id-creator@example.com"),
    "owner": ("user_direct_id_owner", "direct-id-owner@example.com"),
    "collaborator": ("user_direct_id_collaborator", "direct-id-collaborator@example.com"),
    "outsider": ("user_direct_id_outsider", "direct-id-outsider@example.com"),
}
SAME_ORG_PASSWORD = "Password123!"


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


def user_auth_headers(client: TestClient, role: str) -> dict[str, str]:
    if role == "admin":
        return auth_headers(client)
    _, email = SAME_ORG_USERS[role]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SAME_ORG_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_same_org_task(client: TestClient) -> None:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    password_hash = hash_password(SAME_ORG_PASSWORD)
    for role, (user_id, email) in SAME_ORG_USERS.items():
        db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', 'approved', ?, NULL, '[]', ?, ?)
            """,
            (user_id, DEFAULT_ORG_ID, email, f"同组织{role}", password_hash, timestamp, timestamp, timestamp),
        )
    list_row = db.fetchone(
        "SELECT id FROM task_lists WHERE organization_id = ? AND archived_at IS NULL ORDER BY is_default DESC LIMIT 1",
        (DEFAULT_ORG_ID,),
    )
    assert list_row is not None
    creator_id = SAME_ORG_USERS["creator"][0]
    owner_id = SAME_ORG_USERS["owner"][0]
    collaborator_id = SAME_ORG_USERS["collaborator"][0]
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, creator_id, owner_id, priority, list_id,
            progress_status, source_type, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, '同组织成员任务', '只有任务成员可见', ?, ?, 'normal', ?,
                 'todo', 'manual', '[]', '[]', ?, ?)
        """,
        (SAME_ORG_TASK_ID, DEFAULT_ORG_ID, creator_id, owner_id, str(list_row["id"]), timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO task_collaborators(
            task_id, user_id, order_index, is_owner, inbox_status, handled_at, created_at, updated_at
        ) VALUES(?, ?, 0, 0, 'accepted', ?, ?, ?)
        """,
        (SAME_ORG_TASK_ID, collaborator_id, timestamp, timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at)
        VALUES('activity_direct_id_same_org', ?, ?, 'member_only_event', '{"secret":"仅成员可见"}', ?)
        """,
        (SAME_ORG_TASK_ID, creator_id, timestamp),
    )


def same_org_task_snapshot(client: TestClient) -> dict[str, object]:
    db = client.app.state.app_state.db
    return {
        "note_count": int(db.scalar("SELECT COUNT(*) FROM task_notes WHERE task_id = ?", (SAME_ORG_TASK_ID,)) or 0),
        "activity_count": int(
            db.scalar("SELECT COUNT(*) FROM task_activity_events WHERE task_id = ?", (SAME_ORG_TASK_ID,)) or 0
        ),
        "link_count": int(db.scalar("SELECT COUNT(*) FROM task_org_links WHERE task_id = ?", (SAME_ORG_TASK_ID,)) or 0),
    }


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


def test_same_org_outsider_cannot_read_task_activity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, "outsider")
    before = same_org_task_snapshot(client)

    detail_response = client.get(f"/api/v1/tasks/{SAME_ORG_TASK_ID}", headers=headers)
    response = client.get(f"/api/v1/tasks/{SAME_ORG_TASK_ID}/activity", headers=headers)

    assert detail_response.status_code == 404, detail_response.text
    assert detail_response.json() == {"detail": "Task not found"}
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert "仅成员可见" not in response.text
    assert same_org_task_snapshot(client) == before


def test_same_org_outsider_cannot_update_task_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    db = client.app.state.app_state.db
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO task_notes(id, organization_id, task_id, user_id, note, created_at, updated_at)
        VALUES('note_direct_id_same_org', ?, ?, ?, '原始成员备注', ?, ?)
        """,
        (DEFAULT_ORG_ID, SAME_ORG_TASK_ID, SAME_ORG_USERS["creator"][0], timestamp, timestamp),
    )
    headers = user_auth_headers(client, "outsider")
    before = same_org_task_snapshot(client)
    note_before = db.fetchone(
        "SELECT user_id, note, created_at, updated_at FROM task_notes WHERE task_id = ?",
        (SAME_ORG_TASK_ID,),
    )
    assert note_before is not None

    detail_response = client.get(f"/api/v1/tasks/{SAME_ORG_TASK_ID}", headers=headers)
    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/note",
        headers=headers,
        json={"note": "同组织 outsider 越权备注"},
    )

    assert detail_response.status_code == 404, detail_response.text
    assert detail_response.json() == {"detail": "Task not found"}
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert same_org_task_snapshot(client) == before
    note_after = db.fetchone(
        "SELECT user_id, note, created_at, updated_at FROM task_notes WHERE task_id = ?",
        (SAME_ORG_TASK_ID,),
    )
    assert note_after is not None
    assert tuple(note_after) == tuple(note_before)


@pytest.mark.parametrize("role", ["creator", "owner", "collaborator", "admin"])
def test_task_members_and_admin_can_read_activity_and_update_note(
    role: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, role)

    activity_response = client.get(f"/api/v1/tasks/{SAME_ORG_TASK_ID}/activity", headers=headers)
    note_response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/note",
        headers=headers,
        json={"note": f"{role} 合法备注"},
    )

    assert activity_response.status_code == 200, activity_response.text
    assert any(item["id"] == "activity_direct_id_same_org" for item in activity_response.json())
    assert note_response.status_code == 200, note_response.text
    assert note_response.json()["note"] == f"{role} 合法备注"
    assert same_org_task_snapshot(client) == {"note_count": 1, "activity_count": 2, "link_count": 1}
