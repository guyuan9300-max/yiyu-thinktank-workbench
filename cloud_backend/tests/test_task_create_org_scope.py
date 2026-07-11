from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DEFAULT_ORG_ID, create_app, now_iso
from app.security import hash_password


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


def seed_other_org(client: TestClient) -> str:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    organization_id = "org_task_scope_other"
    db.execute(
        """
        INSERT INTO organizations(id, name, slug, created_at, updated_at)
        VALUES(?, '任务隔离测试组织', 'task-scope-other', ?, ?)
        """,
        (organization_id, timestamp, timestamp),
    )
    return organization_id


def seed_employee(client: TestClient, *, user_id: str, organization_id: str) -> None:
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', 'approved', ?, 'user_admin', '[]', ?, ?)
        """,
        (
            user_id,
            organization_id,
            f"{user_id}@example.com",
            f"{user_id} 用户",
            hash_password("Password123!"),
            timestamp,
            timestamp,
            timestamp,
        ),
    )


def default_list_id(client: TestClient) -> str:
    row = client.app.state.app_state.db.fetchone(
        """
        SELECT id
        FROM task_lists
        WHERE organization_id = ? AND archived_at IS NULL AND is_default = 1
        ORDER BY sort_order ASC, id ASC
        LIMIT 1
        """,
        (DEFAULT_ORG_ID,),
    )
    assert row is not None
    return str(row["id"])


@pytest.mark.parametrize("invalid_list_kind", ["missing", "archived", "cross_org"])
def test_create_task_falls_back_to_current_org_default_for_unusable_list_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_list_kind: str,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    db = client.app.state.app_state.db
    expected_list_id = default_list_id(client)
    requested_list_id = f"list_task_scope_{invalid_list_kind}"

    if invalid_list_kind == "archived":
        db.execute(
            """
            INSERT INTO task_lists(
                id, organization_id, name, color, sort_order, is_default, scope, archived_at
            ) VALUES(?, ?, '已归档清单', '#999999', 99, 0, 'org', ?)
            """,
            (requested_list_id, DEFAULT_ORG_ID, now_iso()),
        )
    elif invalid_list_kind == "cross_org":
        other_org_id = seed_other_org(client)
        db.execute(
            """
            INSERT INTO task_lists(
                id, organization_id, name, color, sort_order, is_default, scope, archived_at
            ) VALUES(?, ?, '其他组织清单', '#999999', 0, 1, 'org', NULL)
            """,
            (requested_list_id, other_org_id),
        )

    task_id = f"task_scope_list_{invalid_list_kind}"
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "id": task_id,
            "title": f"清单隔离-{invalid_list_kind}",
            "listId": requested_list_id,
            "collaboratorIds": [],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["listId"] == expected_list_id
    task_row = db.fetchone(
        "SELECT organization_id, list_id FROM tasks WHERE id = ?",
        (task_id,),
    )
    assert task_row is not None
    assert str(task_row["organization_id"]) == DEFAULT_ORG_ID
    assert str(task_row["list_id"]) == expected_list_id
    resolved_list_row = db.fetchone(
        "SELECT organization_id, archived_at FROM task_lists WHERE id = ?",
        (str(task_row["list_id"]),),
    )
    assert resolved_list_row is not None
    assert str(resolved_list_row["organization_id"]) == DEFAULT_ORG_ID
    assert resolved_list_row["archived_at"] is None


@pytest.mark.parametrize("member_field", ["ownerId", "collaboratorIds"])
def test_create_task_rejects_cross_org_members_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    member_field: str,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    db = client.app.state.app_state.db
    other_org_id = seed_other_org(client)
    foreign_user_id = "user_task_scope_foreign"
    seed_employee(client, user_id=foreign_user_id, organization_id=other_org_id)
    task_id = f"task_scope_foreign_{member_field.lower()}"
    payload: dict[str, object] = {
        "id": task_id,
        "title": f"跨组织成员隔离-{member_field}",
        "listId": default_list_id(client),
        "collaboratorIds": [],
    }
    payload[member_field] = foreign_user_id if member_field == "ownerId" else [foreign_user_id]

    response = client.post("/api/v1/tasks", headers=headers, json=payload)

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "User not found"}
    assert db.fetchone("SELECT id FROM tasks WHERE id = ?", (task_id,)) is None
    assert db.fetchone("SELECT task_id FROM task_collaborators WHERE task_id = ?", (task_id,)) is None
    assert db.fetchone("SELECT task_id FROM task_activity_events WHERE task_id = ?", (task_id,)) is None


def test_create_task_accepts_current_org_member_and_keeps_retry_and_org_invariants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    db = client.app.state.app_state.db
    member_id = "user_task_scope_local"
    seed_employee(client, user_id=member_id, organization_id=DEFAULT_ORG_ID)
    task_id = "task_scope_local_member"
    payload = {
        "id": task_id,
        "title": "本组织成员任务",
        "listId": default_list_id(client),
        "ownerId": member_id,
        "collaboratorIds": [member_id],
    }

    first = client.post("/api/v1/tasks", headers=headers, json=payload)
    retry = client.post("/api/v1/tasks", headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"] == task_id
    assert retry.json()["ownerId"] == member_id
    task_row = db.fetchone(
        """
        SELECT t.organization_id AS task_org_id,
               t.list_id,
               l.organization_id AS list_org_id,
               owner.organization_id AS owner_org_id
        FROM tasks t
        JOIN task_lists l ON l.id = t.list_id
        LEFT JOIN employee_accounts owner ON owner.id = t.owner_id
        WHERE t.id = ?
        """,
        (task_id,),
    )
    assert task_row is not None
    assert {
        str(task_row["task_org_id"]),
        str(task_row["list_org_id"]),
        str(task_row["owner_org_id"]),
    } == {DEFAULT_ORG_ID}
    task_count = db.fetchone("SELECT COUNT(*) AS count FROM tasks WHERE id = ?", (task_id,))
    collaborator_count = db.fetchone(
        "SELECT COUNT(*) AS count FROM task_collaborators WHERE task_id = ? AND user_id = ?",
        (task_id, member_id),
    )
    cross_org_collaborator_count = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM task_collaborators tc
        JOIN tasks t ON t.id = tc.task_id
        JOIN employee_accounts member ON member.id = tc.user_id
        WHERE tc.task_id = ? AND member.organization_id != t.organization_id
        """,
        (task_id,),
    )
    assert task_count is not None and int(task_count["count"]) == 1
    assert collaborator_count is not None and int(collaborator_count["count"]) == 1
    assert cross_org_collaborator_count is not None and int(cross_org_collaborator_count["count"]) == 0
