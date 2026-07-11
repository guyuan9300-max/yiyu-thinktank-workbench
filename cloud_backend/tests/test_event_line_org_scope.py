from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DEFAULT_ORG_ID, create_app, now_iso
from app.security import hash_password


PASSWORD = "Password123!"
USERS = {
    "owner": ("user_event_scope_owner", "event-owner@example.com"),
    "participant": ("user_event_scope_participant", "event-participant@example.com"),
    "outsider": ("user_event_scope_outsider", "event-outsider@example.com"),
}
FOREIGN_ORG_ID = "org_event_scope_foreign"
FOREIGN_USER_ID = "user_event_scope_foreign"
FOREIGN_CLIENT_ID = "client_event_scope_foreign"
FOREIGN_DEPARTMENT_ID = "dept_event_scope_foreign"
FOREIGN_EVENT_LINE_ID = "eline_event_scope_foreign"
SAME_CLIENT_ID = "client_event_scope_same"
SAME_DEPARTMENT_ID = "dept_event_scope_same"


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    return TestClient(create_app())


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def auth_headers(client: TestClient, role: str) -> dict[str, str]:
    if role == "admin":
        return login(client, "admin@yiyu-system.com", "Admin123!")
    return login(client, USERS[role][1], PASSWORD)


def seed_scope_relations(client: TestClient) -> None:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    password_hash = hash_password(PASSWORD)
    for role, (user_id, email) in USERS.items():
        db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', 'approved', ?, NULL, '[]', ?, ?)
            """,
            (user_id, DEFAULT_ORG_ID, email, f"事件线{role}", password_hash, timestamp, timestamp, timestamp),
        )
    db.execute(
        "INSERT INTO clients(id, organization_id, name, alias, type, created_at, updated_at) VALUES(?, ?, '同组织客户', '', 'client', ?, ?)",
        (SAME_CLIENT_ID, DEFAULT_ORG_ID, timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO org_departments(id, organization_id, name, updated_at)
        VALUES(?, ?, '同组织部门', ?)
        """,
        (SAME_DEPARTMENT_ID, DEFAULT_ORG_ID, timestamp),
    )
    db.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES(?, '事件线外组织', 'event-scope-foreign', ?, ?)",
        (FOREIGN_ORG_ID, timestamp, timestamp),
    )
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            membership_status, approved_at, approved_by, recent_mentions_json, created_at, updated_at
        ) VALUES(?, ?, 'event-foreign@example.com', '事件线外组织用户', ?, 'employee',
                 'approved', 'approved', ?, NULL, '[]', ?, ?)
        """,
        (FOREIGN_USER_ID, FOREIGN_ORG_ID, password_hash, timestamp, timestamp, timestamp),
    )
    db.execute(
        "INSERT INTO clients(id, organization_id, name, alias, type, created_at, updated_at) VALUES(?, ?, '外组织客户', '', 'client', ?, ?)",
        (FOREIGN_CLIENT_ID, FOREIGN_ORG_ID, timestamp, timestamp),
    )
    db.execute(
        "INSERT INTO org_departments(id, organization_id, name, updated_at) VALUES(?, ?, '外组织部门', ?)",
        (FOREIGN_DEPARTMENT_ID, FOREIGN_ORG_ID, timestamp),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, organization_id, name, kind, status, visibility_scope, evidence_count,
            owner_id, primary_client_id, primary_client_name, primary_department_id,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, '外组织事件线', 'custom', 'active', 'private', 0,
                 ?, ?, '外组织客户', ?, ?, ?, ?)
        """,
        (
            FOREIGN_EVENT_LINE_ID,
            FOREIGN_ORG_ID,
            FOREIGN_USER_ID,
            FOREIGN_CLIENT_ID,
            FOREIGN_DEPARTMENT_ID,
            f'["{FOREIGN_USER_ID}"]',
            timestamp,
            timestamp,
        ),
    )


def create_event_line(client: TestClient, visibility_scope: str = "project_public") -> str:
    response = client.post(
        "/api/v1/event-lines",
        headers=auth_headers(client, "admin"),
        json={
            "name": f"{visibility_scope} 事件线",
            "visibilityScope": visibility_scope,
            "ownerId": USERS["owner"][0],
            "participantIds": [USERS["participant"][0]],
            "primaryClientId": SAME_CLIENT_ID,
            "primaryDepartmentId": SAME_DEPARTMENT_ID,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def attach_task(client: TestClient, event_line_id: str) -> str:
    db = client.app.state.app_state.db
    timestamp = now_iso()
    admin = db.fetchone("SELECT id FROM employee_accounts WHERE email = 'admin@yiyu-system.com'")
    task_list = db.fetchone(
        "SELECT id FROM task_lists WHERE organization_id = ? AND archived_at IS NULL ORDER BY is_default DESC LIMIT 1",
        (DEFAULT_ORG_ID,),
    )
    assert admin is not None and task_list is not None
    task_id = f"task_{event_line_id}"
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, creator_id, owner_id, priority, list_id,
            progress_status, source_type, scope_mode, client_id, event_line_id,
            tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, '事件线关联任务', '', ?, ?, 'normal', ?, 'todo', 'manual',
                 'COLLAB_SHARED', ?, ?, '[]', '[]', ?, ?)
        """,
        (
            task_id,
            DEFAULT_ORG_ID,
            str(admin["id"]),
            USERS["owner"][0],
            str(task_list["id"]),
            SAME_CLIENT_ID,
            event_line_id,
            timestamp,
            timestamp,
        ),
    )
    return task_id


def event_line_snapshot(client: TestClient, event_line_id: str) -> dict[str, object]:
    db = client.app.state.app_state.db
    row = db.fetchone(
        """
        SELECT name, status, visibility_scope, owner_id, primary_client_id, primary_client_name,
               primary_department_id, participant_ids_json, updated_at
        FROM event_lines WHERE id = ?
        """,
        (event_line_id,),
    )
    assert row is not None
    return {
        "event_line": tuple(row),
        "activities": [
            tuple(item)
            for item in db.fetchall(
                "SELECT source_type, source_id, actor_id, title, summary, metadata_json, happened_at FROM event_line_activities WHERE event_line_id = ? ORDER BY id",
                (event_line_id,),
            )
        ],
        "tasks": [
            tuple(item)
            for item in db.fetchall(
                "SELECT id, client_id, updated_at FROM tasks WHERE event_line_id = ? ORDER BY id",
                (event_line_id,),
            )
        ],
    }


def event_line_counts(client: TestClient) -> tuple[int, int]:
    db = client.app.state.app_state.db
    return (
        int(db.scalar("SELECT COUNT(*) FROM event_lines WHERE organization_id = ?", (DEFAULT_ORG_ID,)) or 0),
        int(db.scalar("SELECT COUNT(*) FROM event_line_activities") or 0),
    )


@pytest.mark.parametrize(
    ("field", "value", "expected_detail"),
    [
        ("ownerId", FOREIGN_USER_ID, "User not found"),
        ("participantIds", [FOREIGN_USER_ID], "User not found"),
        ("primaryDepartmentId", FOREIGN_DEPARTMENT_ID, "Department not found"),
        ("primaryClientId", FOREIGN_CLIENT_ID, "Client not found"),
    ],
)
def test_event_line_create_rejects_cross_org_relations_without_side_effects(
    field: str,
    value: object,
    expected_detail: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    payload: dict[str, object] = {
        "name": "不得创建的跨组织关系事件线",
        "ownerId": USERS["owner"][0],
        "participantIds": [USERS["participant"][0]],
        "primaryClientId": SAME_CLIENT_ID,
        "primaryDepartmentId": SAME_DEPARTMENT_ID,
    }
    payload[field] = value
    before = event_line_counts(client)

    response = client.post("/api/v1/event-lines", headers=auth_headers(client, "admin"), json=payload)

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": expected_detail}
    assert event_line_counts(client) == before


@pytest.mark.parametrize(
    ("payload", "expected_detail"),
    [
        ({"ownerId": FOREIGN_USER_ID}, "User not found"),
        ({"participantIds": [FOREIGN_USER_ID]}, "User not found"),
        ({"primaryDepartmentId": FOREIGN_DEPARTMENT_ID}, "Department not found"),
        ({"primaryClientId": FOREIGN_CLIENT_ID, "syncLinkedTaskClientIds": True}, "Client not found"),
    ],
)
def test_event_line_update_rejects_cross_org_relations_without_side_effects(
    payload: dict[str, object],
    expected_detail: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    event_line_id = create_event_line(client)
    attach_task(client, event_line_id)
    before = event_line_snapshot(client, event_line_id)

    response = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        headers=auth_headers(client, "owner"),
        json=payload,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": expected_detail}
    assert event_line_snapshot(client, event_line_id) == before


def test_same_org_outsider_event_line_update_is_404_with_zero_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    event_line_id = create_event_line(client)
    before = event_line_snapshot(client, event_line_id)

    response = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        headers=auth_headers(client, "outsider"),
        json={"summary": "outsider 越权更新"},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Event line not found"}
    assert event_line_snapshot(client, event_line_id) == before


def test_private_event_line_is_only_visible_to_members_and_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    event_line_id = create_event_line(client, "private")

    for role in ("owner", "participant", "admin"):
        response = client.get(f"/api/v1/event-lines/{event_line_id}", headers=auth_headers(client, role))
        assert response.status_code == 200, response.text
    outsider_headers = auth_headers(client, "outsider")
    outsider_detail = client.get(f"/api/v1/event-lines/{event_line_id}", headers=outsider_headers)
    outsider_list = client.get("/api/v1/event-lines", headers=outsider_headers)

    assert outsider_detail.status_code == 404, outsider_detail.text
    assert outsider_detail.json() == {"detail": "Event line not found"}
    assert outsider_list.status_code == 200, outsider_list.text
    assert event_line_id not in {item["id"] for item in outsider_list.json()}


def test_project_public_event_line_remains_readable_to_same_org_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    event_line_id = create_event_line(client, "project_public")
    headers = auth_headers(client, "outsider")

    detail = client.get(f"/api/v1/event-lines/{event_line_id}", headers=headers)
    listed = client.get("/api/v1/event-lines", headers=headers)

    assert detail.status_code == 200, detail.text
    assert event_line_id in {item["id"] for item in listed.json()}


@pytest.mark.parametrize("role", ["owner", "participant", "admin"])
def test_event_line_members_and_admin_can_update(
    role: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    event_line_id = create_event_line(client)

    response = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        headers=auth_headers(client, role),
        json={"summary": f"{role} 合法更新"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == f"{role} 合法更新"


def test_cross_org_event_line_update_is_404_with_zero_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_scope_relations(client)
    before = event_line_snapshot(client, FOREIGN_EVENT_LINE_ID)

    response = client.patch(
        f"/api/v1/event-lines/{FOREIGN_EVENT_LINE_ID}",
        headers=auth_headers(client, "admin"),
        json={"summary": "跨组织越权更新"},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Event line not found"}
    assert event_line_snapshot(client, FOREIGN_EVENT_LINE_ID) == before
