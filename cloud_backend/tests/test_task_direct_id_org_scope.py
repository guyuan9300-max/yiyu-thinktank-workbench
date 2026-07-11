from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as cloud_main
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


def configure_org_ai_and_asr(client: TestClient) -> None:
    headers = auth_headers(client)
    ai = client.post(
        "/api/v1/settings/org-ai-config",
        headers=headers,
        json={
            "aiProvider": "openai-compatible",
            "aiBaseUrl": "https://models.example.com/v1",
            "aiModel": "test-model",
            "apiKey": "direct-id-org-ai-key",
        },
    )
    assert ai.status_code == 200, ai.text
    asr = client.post(
        "/api/v1/settings/org-asr-config",
        headers=headers,
        json={
            "provider": "doubao_file",
            "appId": "direct-id-org-asr-app",
            "accessToken": "direct-id-org-asr-token",
        },
    )
    assert asr.status_code == 200, asr.text


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


def seed_audio_attachment(
    client: TestClient,
    *,
    task_id: str,
    organization_id: str,
    attachment_id: str,
    created_by_user_id: str,
) -> Path:
    state = client.app.state.app_state
    timestamp = now_iso()
    relative_path = Path("task-attachments") / task_id / f"{attachment_id}.m4a"
    attachment_path = state.data_dir / relative_path
    attachment_path.parent.mkdir(parents=True, exist_ok=True)
    attachment_path.write_bytes(b"fake-audio-for-direct-id-security-test")
    state.db.execute(
        """
        INSERT INTO task_attachments(
            id, organization_id, task_id, client_id, event_line_id, document_id,
            title, summary, path, kind, source, mime_type, size_bytes, duration_seconds,
            created_by_user_id, created_at
        ) VALUES(?, ?, ?, NULL, NULL, NULL, '权限边界录音', NULL, ?, 'audio', 'mobile',
                 'audio/mp4', ?, 0, ?, ?)
        """,
        (
            attachment_id,
            organization_id,
            task_id,
            relative_path.as_posix(),
            attachment_path.stat().st_size,
            created_by_user_id,
            timestamp,
        ),
    )
    return attachment_path


def install_transcription_spies(
    monkeypatch: pytest.MonkeyPatch,
    watched_attachment_path: Path,
) -> dict[str, int]:
    calls = {
        "asr_config": 0,
        "ai_config": 0,
        "file_read": 0,
        "asr": 0,
        "document": 0,
        "summary": 0,
    }
    read_bytes = Path.read_bytes
    create_document = cloud_main._create_consultation_knowledge_request_internal
    resolve_asr_config = cloud_main._org_asr_runtime_config_or_503
    resolve_ai_config = cloud_main._org_ai_runtime_config_or_503

    def resolve_asr_config_spy(*args, **kwargs):
        calls["asr_config"] += 1
        return resolve_asr_config(*args, **kwargs)

    def resolve_ai_config_spy(*args, **kwargs):
        calls["ai_config"] += 1
        return resolve_ai_config(*args, **kwargs)

    def read_bytes_spy(path: Path) -> bytes:
        if path == watched_attachment_path:
            calls["file_read"] += 1
        return read_bytes(path)

    def transcribe(*args, **kwargs) -> str:
        assert kwargs["app_id"] == "direct-id-org-asr-app"
        assert kwargs["access_token"] == "direct-id-org-asr-token"
        calls["asr"] += 1
        return "权限边界测试转写文本"

    def create_document_spy(*args, **kwargs):
        calls["document"] += 1
        return create_document(*args, **kwargs)

    def summarize(*args, **kwargs) -> str:
        calls["summary"] += 1
        return "权限边界测试摘要"

    monkeypatch.setattr(Path, "read_bytes", read_bytes_spy)
    monkeypatch.setattr(cloud_main, "_org_asr_runtime_config_or_503", resolve_asr_config_spy)
    monkeypatch.setattr(cloud_main, "_org_ai_runtime_config_or_503", resolve_ai_config_spy)
    monkeypatch.setattr(cloud_main, "transcribe_audio_with_doubao", transcribe)
    monkeypatch.setattr(cloud_main, "_create_consultation_knowledge_request_internal", create_document_spy)
    monkeypatch.setattr(cloud_main, "_generate_recording_summary", summarize)
    return calls


def task_sensitive_snapshot(client: TestClient, task_id: str) -> dict[str, object]:
    db = client.app.state.app_state.db
    task = db.fetchone(
        """
        SELECT title, description, priority, list_id, progress_status, owner_id,
               completion_note, completed_at, event_line_id, updated_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    )
    assert task is not None
    return {
        "task": tuple(task),
        "activity_count": int(
            db.scalar("SELECT COUNT(*) FROM task_activity_events WHERE task_id = ?", (task_id,)) or 0
        ),
        "link_count": int(db.scalar("SELECT COUNT(*) FROM task_org_links WHERE task_id = ?", (task_id,)) or 0),
        "links": [
            tuple(row)
            for row in db.fetchall(
                """
                SELECT organization_id, approval_state, blocked_at_step, needs_review, updated_at
                FROM task_org_links
                WHERE task_id = ?
                ORDER BY organization_id
                """,
                (task_id,),
            )
        ],
        "collaborators": [
            tuple(row)
            for row in db.fetchall(
                """
                SELECT user_id, inbox_status, return_reason, handled_at, updated_at
                FROM task_collaborators
                WHERE task_id = ?
                ORDER BY user_id
                """,
                (task_id,),
            )
        ],
        "attachments": [
            tuple(row)
            for row in db.fetchall(
                """
                SELECT id, organization_id, summary, path, size_bytes
                FROM task_attachments
                WHERE task_id = ?
                ORDER BY id
                """,
                (task_id,),
            )
        ],
        "consultation_answer_count": int(
            db.scalar("SELECT COUNT(*) FROM consultation_answers WHERE task_id = ?", (task_id,)) or 0
        ),
        "knowledge_request_count": int(
            db.scalar(
                """
                SELECT COUNT(*)
                FROM consultation_knowledge_requests req
                JOIN consultation_answers answer ON answer.id = req.answer_id
                WHERE answer.task_id = ?
                """,
                (task_id,),
            )
            or 0
        ),
        "mention_history": [
            tuple(row)
            for row in db.fetchall(
                """
                SELECT actor_id, mentioned_user_id, use_count, last_mentioned_at
                FROM mention_history
                WHERE actor_id IN (
                    SELECT creator_id FROM tasks WHERE id = ?
                )
                ORDER BY actor_id, mentioned_user_id
                """,
                (task_id,),
            )
        ],
    }


def seed_task_review_link(client: TestClient, task_id: str, organization_id: str) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO task_org_links(
            task_id, organization_id, approval_state, blocked_at_step, needs_review, updated_at
        ) VALUES(?, ?, 'pending', NULL, 1, ?)
        """,
        (task_id, organization_id, now_iso()),
    )


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


@pytest.mark.parametrize(
    ("route_suffix", "payload"),
    [
        ("complete-with-review", {"reviewNote": "不得跨组织完成"}),
        ("review/approve", None),
        ("review/return", {"reason": "不得跨组织退回复核"}),
    ],
)
def test_cross_org_task_terminal_route_is_404_and_has_zero_side_effects(
    route_suffix: str,
    payload: dict[str, str] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    seed_task_review_link(client, FOREIGN_TASK_ID, FOREIGN_ORG_ID)
    before = task_sensitive_snapshot(client, FOREIGN_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/{route_suffix}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert task_sensitive_snapshot(client, FOREIGN_TASK_ID) == before


@pytest.mark.parametrize(
    ("route_suffix", "payload"),
    [
        ("complete-with-review", {"reviewNote": "outsider 不得完成"}),
        ("review/approve", None),
        ("review/return", {"reason": "outsider 不得退回复核"}),
    ],
)
def test_same_org_outsider_task_terminal_route_is_404_and_has_zero_side_effects(
    route_suffix: str,
    payload: dict[str, str] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    seed_task_review_link(client, SAME_ORG_TASK_ID, DEFAULT_ORG_ID)
    headers = user_auth_headers(client, "outsider")
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/{route_suffix}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


@pytest.mark.parametrize("role", ["creator", "owner", "collaborator", "admin"])
def test_task_members_and_admin_can_complete_with_review(
    role: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, role)
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/complete-with-review",
        headers=headers,
        json={"reviewNote": f"{role} 合法完成复盘"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["progressStatus"] == "done"
    assert response.json()["completionNote"] == f"{role} 合法完成复盘"
    after = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    assert after["activity_count"] == int(before["activity_count"]) + 1


@pytest.mark.parametrize(
    ("route_suffix", "payload", "expected_state", "expected_needs_review", "expected_blocked"),
    [
        ("review/approve", None, "approved", 0, None),
        ("review/return", {"reason": "合法退回复核"}, "rejected", 1, "合法退回复核"),
    ],
)
def test_admin_can_approve_or_return_visible_task_review(
    route_suffix: str,
    payload: dict[str, str] | None,
    expected_state: str,
    expected_needs_review: int,
    expected_blocked: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    seed_task_review_link(client, SAME_ORG_TASK_ID, DEFAULT_ORG_ID)
    headers = auth_headers(client)
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/{route_suffix}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200, response.text
    link = client.app.state.app_state.db.fetchone(
        "SELECT approval_state, needs_review, blocked_at_step FROM task_org_links WHERE task_id = ?",
        (SAME_ORG_TASK_ID,),
    )
    assert link is not None
    assert tuple(link) == (expected_state, expected_needs_review, expected_blocked)
    after = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    assert after["activity_count"] == int(before["activity_count"]) + 1


def test_same_org_outsider_task_update_is_404_and_has_zero_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, "outsider")
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.patch(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}",
        headers=headers,
        json={"title": "outsider 越权更新"},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


@pytest.mark.parametrize(
    "payload",
    [
        {"ownerId": FOREIGN_USER_ID},
        {"collaboratorIds": [FOREIGN_USER_ID]},
    ],
)
def test_task_update_rejects_cross_org_user_relations_without_side_effects(
    payload: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    seed_foreign_task(client)
    headers = user_auth_headers(client, "creator")
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.patch(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "User not found"}
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


def test_task_creator_can_assign_same_org_owner_and_collaborators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, "creator")
    next_owner_id = SAME_ORG_USERS["outsider"][0]
    collaborator_id = SAME_ORG_USERS["collaborator"][0]

    response = client.patch(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}",
        headers=headers,
        json={"ownerId": next_owner_id, "collaboratorIds": [collaborator_id, next_owner_id]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["ownerId"] == next_owner_id
    assert {item["userId"] for item in response.json()["collaborators"]} == {next_owner_id, collaborator_id}


@pytest.mark.parametrize("requested_list_kind", ["foreign", "missing", "archived"])
def test_task_update_writes_resolved_current_org_list(
    requested_list_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    seed_foreign_task(client)
    db = client.app.state.app_state.db
    default_row = db.fetchone(
        """
        SELECT id FROM task_lists
        WHERE organization_id = ? AND archived_at IS NULL
        ORDER BY is_default DESC, sort_order ASC
        LIMIT 1
        """,
        (DEFAULT_ORG_ID,),
    )
    assert default_row is not None
    if requested_list_kind == "foreign":
        requested_list_id = FOREIGN_LIST_ID
    elif requested_list_kind == "missing":
        requested_list_id = "list_direct_id_missing"
    else:
        requested_list_id = "list_direct_id_archived"
        db.execute(
            """
            INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
            VALUES(?, ?, '已归档清单', '#999999', 99, 0, 'org', ?)
            """,
            (requested_list_id, DEFAULT_ORG_ID, now_iso()),
        )

    response = client.patch(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}",
        headers=user_auth_headers(client, "creator"),
        json={"listId": requested_list_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["listId"] == str(default_row["id"])
    task_row = db.fetchone("SELECT list_id FROM tasks WHERE id = ?", (SAME_ORG_TASK_ID,))
    assert task_row is not None
    assert str(task_row["list_id"]) == str(default_row["id"])


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


def test_cross_org_attachment_transcription_stops_before_file_ai_or_document_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_foreign_task(client)
    admin_row = client.app.state.app_state.db.fetchone(
        "SELECT id FROM employee_accounts WHERE email = 'admin@yiyu-system.com'"
    )
    assert admin_row is not None
    admin_id = str(admin_row["id"])
    attachment_id = "attachment_direct_id_cross_org"
    attachment_path = seed_audio_attachment(
        client,
        task_id=FOREIGN_TASK_ID,
        # Deliberately malformed tenant edge: the attachment claims the actor's org
        # while its task belongs to another org. Authorization must scope the task first.
        organization_id=DEFAULT_ORG_ID,
        attachment_id=attachment_id,
        created_by_user_id=admin_id,
    )
    calls = install_transcription_spies(monkeypatch, attachment_path)
    before = task_sensitive_snapshot(client, FOREIGN_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/attachments/{attachment_id}/transcribe-to-document",
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert calls == {
        "asr_config": 0,
        "ai_config": 0,
        "file_read": 0,
        "asr": 0,
        "document": 0,
        "summary": 0,
    }
    assert task_sensitive_snapshot(client, FOREIGN_TASK_ID) == before


@pytest.mark.parametrize("parent_kind", ["event_line", "client"])
def test_corrupt_cross_org_attachment_parent_stops_before_config_file_or_provider_access(
    parent_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    seed_same_org_task(client)
    seed_foreign_task(client)
    state = client.app.state.app_state
    timestamp = now_iso()
    parent_id = f"foreign_attachment_parent_{parent_kind}"
    if parent_kind == "event_line":
        state.db.execute(
            """
            INSERT INTO event_lines(
                id, organization_id, name, kind, status, owner_id,
                participant_ids_json, created_at, updated_at
            ) VALUES(?, ?, '外组织事件线', 'custom', 'active', ?, '[]', ?, ?)
            """,
            (parent_id, FOREIGN_ORG_ID, FOREIGN_USER_ID, timestamp, timestamp),
        )
    else:
        state.db.execute(
            """
            INSERT INTO clients(id, organization_id, name, alias, type, created_at, updated_at)
            VALUES(?, ?, '外组织客户', '', 'client', ?, ?)
            """,
            (parent_id, FOREIGN_ORG_ID, timestamp, timestamp),
        )

    attachment_id = f"attachment_corrupt_parent_{parent_kind}"
    attachment_path = seed_audio_attachment(
        client,
        task_id=SAME_ORG_TASK_ID,
        organization_id=DEFAULT_ORG_ID,
        attachment_id=attachment_id,
        created_by_user_id=SAME_ORG_USERS["creator"][0],
    )
    state.db.execute(
        f"UPDATE task_attachments SET {parent_kind}_id = ? WHERE id = ?",
        (parent_id, attachment_id),
    )
    calls = install_transcription_spies(monkeypatch, attachment_path)
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/attachments/{attachment_id}/transcribe-to-document",
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert calls == {
        "asr_config": 0,
        "ai_config": 0,
        "file_read": 0,
        "asr": 0,
        "document": 0,
        "summary": 0,
    }
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


def test_same_org_outsider_attachment_transcription_stops_before_any_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    attachment_id = "attachment_direct_id_same_org_outsider"
    attachment_path = seed_audio_attachment(
        client,
        task_id=SAME_ORG_TASK_ID,
        organization_id=DEFAULT_ORG_ID,
        attachment_id=attachment_id,
        created_by_user_id=SAME_ORG_USERS["creator"][0],
    )
    calls = install_transcription_spies(monkeypatch, attachment_path)
    headers = user_auth_headers(client, "outsider")
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/attachments/{attachment_id}/transcribe-to-document",
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert calls == {
        "asr_config": 0,
        "ai_config": 0,
        "file_read": 0,
        "asr": 0,
        "document": 0,
        "summary": 0,
    }
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


@pytest.mark.parametrize("role", ["creator", "owner", "collaborator", "admin"])
def test_task_members_and_admin_can_transcribe_audio_attachment(
    role: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    configure_org_ai_and_asr(client)
    seed_same_org_task(client)
    attachment_id = f"attachment_direct_id_legal_{role}"
    attachment_path = seed_audio_attachment(
        client,
        task_id=SAME_ORG_TASK_ID,
        organization_id=DEFAULT_ORG_ID,
        attachment_id=attachment_id,
        created_by_user_id=SAME_ORG_USERS["creator"][0],
    )
    calls = install_transcription_spies(monkeypatch, attachment_path)
    headers = user_auth_headers(client, role)
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/attachments/{attachment_id}/transcribe-to-document",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["transcript"] == "权限边界测试转写文本"
    assert calls == {
        "asr_config": 1,
        "ai_config": 1,
        "file_read": 1,
        "asr": 1,
        "document": 1,
        "summary": 1,
    }
    after = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    assert after["activity_count"] == int(before["activity_count"]) + 1
    assert after["consultation_answer_count"] == int(before["consultation_answer_count"]) + 1
    assert after["knowledge_request_count"] == int(before["knowledge_request_count"]) + 1
    attachment = next(item for item in after["attachments"] if item[0] == attachment_id)
    assert attachment[2] == "权限边界测试摘要"


@pytest.mark.parametrize("action", ["accept", "return"])
def test_cross_org_collaboration_action_is_404_and_has_zero_side_effects(
    action: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    seed_foreign_task(client)
    actor_id = SAME_ORG_USERS["outsider"][0]
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO task_collaborators(
            task_id, user_id, order_index, is_owner, inbox_status, handled_at, created_at, updated_at
        ) VALUES(?, ?, 0, 0, 'pending', NULL, ?, ?)
        """,
        (FOREIGN_TASK_ID, actor_id, timestamp, timestamp),
    )
    headers = user_auth_headers(client, "outsider")
    before = task_sensitive_snapshot(client, FOREIGN_TASK_ID)
    request_kwargs: dict[str, object] = {"headers": headers}
    if action == "return":
        request_kwargs["json"] = {"reason": "不得跨组织退回"}

    response = client.post(
        f"/api/v1/tasks/{FOREIGN_TASK_ID}/collaborators/{actor_id}/{action}",
        **request_kwargs,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert task_sensitive_snapshot(client, FOREIGN_TASK_ID) == before


@pytest.mark.parametrize("action", ["accept", "return"])
def test_same_org_outsider_cannot_act_on_another_collaborator_item(
    action: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    headers = user_auth_headers(client, "outsider")
    collaborator_id = SAME_ORG_USERS["collaborator"][0]
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    request_kwargs: dict[str, object] = {"headers": headers}
    if action == "return":
        request_kwargs["json"] = {"reason": "越权退回"}

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/collaborators/{collaborator_id}/{action}",
        **request_kwargs,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Task not found"}
    assert task_sensitive_snapshot(client, SAME_ORG_TASK_ID) == before


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_reason"),
    [("accept", "accepted", None), ("return", "returned", "合法退回")],
)
def test_collaborator_can_accept_or_return_own_item(
    action: str,
    expected_status: str,
    expected_reason: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    seed_same_org_task(client)
    collaborator_id = SAME_ORG_USERS["collaborator"][0]
    client.app.state.app_state.db.execute(
        """
        UPDATE task_collaborators
        SET inbox_status = 'pending', return_reason = NULL, handled_at = NULL
        WHERE task_id = ? AND user_id = ?
        """,
        (SAME_ORG_TASK_ID, collaborator_id),
    )
    headers = user_auth_headers(client, "collaborator")
    before = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    request_kwargs: dict[str, object] = {"headers": headers}
    if action == "return":
        request_kwargs["json"] = {"reason": expected_reason}

    response = client.post(
        f"/api/v1/tasks/{SAME_ORG_TASK_ID}/collaborators/{collaborator_id}/{action}",
        **request_kwargs,
    )

    assert response.status_code == 200, response.text
    row = client.app.state.app_state.db.fetchone(
        """
        SELECT inbox_status, return_reason, handled_at
        FROM task_collaborators
        WHERE task_id = ? AND user_id = ?
        """,
        (SAME_ORG_TASK_ID, collaborator_id),
    )
    assert row is not None
    assert str(row["inbox_status"]) == expected_status
    assert row["return_reason"] == expected_reason
    assert row["handled_at"] is not None
    after = task_sensitive_snapshot(client, SAME_ORG_TASK_ID)
    assert after["activity_count"] == int(before["activity_count"]) + 1


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
