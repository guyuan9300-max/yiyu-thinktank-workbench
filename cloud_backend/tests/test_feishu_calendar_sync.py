from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def stub_feishu_task_center(monkeypatch):
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: {"code": 0, "data": {"task": {"guid": "task_guid_auto", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_auto"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_task",
        lambda *, tenant_access_token, task_guid, body, update_fields: {"code": 0, "data": {"task": {"guid": task_guid, "url": f"https://applink.feishu.cn/client/todo/detail?guid={task_guid}"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_task",
        lambda *, tenant_access_token, task_guid: {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_add_task_members",
        lambda *, tenant_access_token, task_guid, members: {"code": 0, "data": {}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: {"code": 0, "data": {"event": {"event_id": "evt_auto_mirror"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: {"code": 0, "data": {"event": {"event_id": event_id}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_calendar_event_attendees",
        lambda *, tenant_access_token, calendar_id, event_id: {"code": 0, "data": {"items": []}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event_attendees",
        lambda *, tenant_access_token, calendar_id, event_id, open_ids, need_notification=False: {"code": 0, "data": {"items": []}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_set_docx_org_editable",
        lambda *, tenant_access_token, document_id: {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_add_docx_member_permission",
        lambda *, tenant_access_token, document_id, open_id, perm="full_access": {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_transfer_docx_owner",
        lambda *, tenant_access_token, document_id, open_id: {"code": 0},
    )


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")
    return TestClient(create_app())


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> None:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={"appId": "cli_demo_app", "appSecret": "secret_demo"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def bind_current_user_to_feishu(client: TestClient, headers: dict[str, str], receive_id: str = "ou_admin") -> str:
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    payload = profile.json()
    user_id = payload["id"]
    state = client.app.state.app_state
    timestamp = cloud_main.now_iso()
    state.db.execute(
        """
        INSERT INTO org_feishu_member_authorizations(
            organization_id, user_id, app_id, open_id, authorized_at, last_verified_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, user_id) DO UPDATE SET
            app_id = excluded.app_id,
            open_id = excluded.open_id,
            authorized_at = excluded.authorized_at,
            last_verified_at = excluded.last_verified_at,
            updated_at = excluded.updated_at
        """,
        (payload["organizationId"], user_id, "cli_demo_app", receive_id, timestamp, timestamp, timestamp),
    )
    state.db.execute("UPDATE employee_accounts SET feishu_mobile = ? WHERE id = ?", ("13800138000", user_id))
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        state,
        organization_id=payload["organizationId"],
        user_id=user_id,
        mobile="13800138000",
        receive_id=receive_id,
        match_status="matched",
        last_error=None,
    )
    return user_id


def bind_current_user_to_feishu_docs(client: TestClient, headers: dict[str, str], receive_id: str = "ou_doc_import") -> str:
    user_id = bind_current_user_to_feishu(client, headers, receive_id=receive_id)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    state = client.app.state.app_state
    cloud_main._store_feishu_member_tokens(  # noqa: SLF001
        state,
        organization_id=profile.json()["organizationId"],
        user_id=user_id,
        token_payload={"access_token": "user_access_demo", "refresh_token": "refresh_demo", "expires_in": 3600},
    )
    return user_id


def bind_user_to_feishu(client: TestClient, organization_id: str, user_id: str, receive_id: str) -> None:
    state = client.app.state.app_state
    state.db.execute("UPDATE employee_accounts SET feishu_mobile = ? WHERE id = ?", (f"139{abs(hash(user_id)) % 100000000:08d}", user_id))
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        state,
        organization_id=organization_id,
        user_id=user_id,
        mobile=f"139{abs(hash(user_id)) % 100000000:08d}",
        receive_id=receive_id,
        match_status="matched",
        last_error=None,
    )


def authorize_user_to_feishu(client: TestClient, organization_id: str, user_id: str, receive_id: str) -> None:
    state = client.app.state.app_state
    timestamp = cloud_main.now_iso()
    state.db.execute(
        """
        INSERT INTO org_feishu_member_authorizations(
            organization_id, user_id, app_id, open_id, authorized_at, last_verified_at, updated_at
        ) VALUES(?, ?, 'cli_demo_app', ?, ?, ?, ?)
        ON CONFLICT(organization_id, user_id) DO UPDATE SET
            app_id = excluded.app_id,
            open_id = excluded.open_id,
            authorized_at = excluded.authorized_at,
            last_verified_at = excluded.last_verified_at,
            updated_at = excluded.updated_at
        """,
        (organization_id, user_id, receive_id, timestamp, timestamp, timestamp),
    )
    bind_user_to_feishu(client, organization_id, user_id, receive_id)


def seed_feishu_inbound_cursor(client: TestClient, organization_id: str, user_id: str, open_id: str, since: str = "2026-05-01T00:00:00+08:00") -> None:
    state = client.app.state.app_state
    timestamp = cloud_main.now_iso()
    state.db.execute(
        """
        INSERT INTO org_feishu_task_inbound_cursors(
            organization_id, user_id, open_id, inbound_started_at, cursor_updated_at,
            last_success_at, last_checked_at, last_error, last_seen_remote_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, NULL, NULL, '', '[]', ?, ?)
        ON CONFLICT(organization_id, user_id) DO UPDATE SET
            open_id = excluded.open_id,
            cursor_updated_at = excluded.cursor_updated_at,
            updated_at = excluded.updated_at
        """,
        (organization_id, user_id, open_id, since, since, timestamp, timestamp),
    )


def test_feishu_member_authorization_requests_document_import_scopes(tmp_path, monkeypatch):
    registered: dict[str, str] = {}
    monkeypatch.setenv("YIYU_FEISHU_OAUTH_RELAY_BASE_URL", "https://oauth.yiyu.love")
    monkeypatch.setattr(
        cloud_main,
        "_register_feishu_oauth_relay_session",
        lambda **kwargs: registered.update(kwargs),
    )
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)

    response = client.post("/api/v1/me/feishu-authorization/start", headers=headers)

    assert response.status_code == 200, response.text
    query = parse_qs(urlparse(response.json()["authorizeUrl"]).query)
    assert query["redirect_uri"] == ["https://oauth.yiyu.love/feishu/member/callback"]
    assert response.json()["callbackUrl"] == "https://oauth.yiyu.love/feishu/member/callback"
    assert registered["state_token"] == response.json()["state"]
    assert registered["claim_secret"]
    scopes = set(" ".join(query.get("scope", [])).split())
    assert "offline_access" in scopes
    assert "docx:document:readonly" in scopes
    assert "drive:export:readonly" in scopes
    assert "wiki:wiki:readonly" in scopes


def test_feishu_member_authorization_claims_code_from_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("YIYU_FEISHU_OAUTH_RELAY_BASE_URL", "https://oauth.yiyu.love")
    monkeypatch.setattr(cloud_main, "_register_feishu_oauth_relay_session", lambda **_: None)
    monkeypatch.setattr(cloud_main, "_claim_feishu_oauth_relay_code", lambda **_: {"status": "authorized", "code": "relay_code_demo"})
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_exchange_authorization_code",
        lambda **_: {
            "access_token": "user_access_demo",
            "refresh_token": "refresh_demo",
            "expires_in": 3600,
            "open_id": "ou_relay_member",
            "union_id": "on_relay_member",
        },
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_fetch_user_info",
        lambda **_: {"open_id": "ou_relay_member", "union_id": "on_relay_member", "name": "授权成员"},
    )
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    started = client.post("/api/v1/me/feishu-authorization/start", headers=headers)
    assert started.status_code == 200, started.text

    status_response = client.get("/api/v1/me/feishu-authorization", headers=headers)

    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert payload["linked"] is True
    assert payload["openId"] == "ou_relay_member"
    assert payload["name"] == "授权成员"


def another_employee_id(client: TestClient, organization_id: str, excluded_user_id: str) -> str:
    state = client.app.state.app_state
    row = state.db.fetchone(
        "SELECT id FROM employee_accounts WHERE organization_id = ? AND id != ? ORDER BY created_at ASC LIMIT 1",
        (organization_id, excluded_user_id),
    )
    if not row:
        user_id = "user_feishu_collaborator"
        state.db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
                department_id, department_name, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', ?, ?, NULL, NULL, '[]', NULL, NULL, NULL, ?, ?)
            """,
            (
                user_id,
                organization_id,
                "feishu-collaborator@example.com",
                "飞书协作者",
                cloud_main.hash_password("Collaborator123!"),
                cloud_main.now_iso(),
                excluded_user_id,
                cloud_main.now_iso(),
                cloud_main.now_iso(),
            ),
        )
        row = state.db.fetchone("SELECT id FROM employee_accounts WHERE id = ?", (user_id,))
    assert row and row["id"]
    return str(row["id"])


def create_task(client: TestClient, headers: dict[str, str], **overrides) -> str:
    payload = {
        "title": "同步到飞书日历",
        "description": "这是一条需要进入日程的任务。",
        "priority": "normal",
        "listId": "list-0",
    }
    payload.update(overrides)
    response = client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_create_task_creates_calendar_mirror_after_task_center_sync(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_auto_create"}}},
    )

    task_id = create_task(
        client,
        headers,
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T11:00",
    )

    assert created_events
    assert created_events[0]["summary"] == "同步到飞书日历"
    assert created_events[0]["reminders"] == [{"minutes": 0}]
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "evt_auto_create"
    assert payload["details"]["calendarMirror"] is True
    assert payload["details"]["calendarMode"] == "scheduled"


def test_task_center_sync_adds_owner_and_collaborators_as_feishu_assignees(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    organization_id = profile.json()["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_admin_assignee")
    collaborator_id = another_employee_id(client, organization_id, user_id)
    bind_user_to_feishu(client, organization_id, collaborator_id, "ou_collaborator_assignee")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_bodies: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: created_bodies.append(body)
        or {"code": 0, "data": {"task": {"guid": "task_guid_members", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_members"}}},
    )

    task_id = create_task(
        client,
        headers,
        ownerId=user_id,
        collaboratorIds=[user_id, collaborator_id],
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T11:00",
    )

    assert task_id
    assert created_bodies
    assert created_bodies[0]["members"] == [
        {"id": "ou_admin_assignee", "type": "user", "role": "assignee"},
        {"id": "ou_collaborator_assignee", "type": "user", "role": "assignee"},
    ]
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["details"]["taskMemberOpenIdCount"] == 2


def test_create_task_auto_syncs_feishu_task_center_when_user_is_matched(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_task_assignee")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_bodies: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: created_bodies.append(body)
        or {"code": 0, "data": {"task": {"guid": "task_guid_created", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_created"}}},
    )

    task_id = create_task(
        client,
        headers,
        ownerId=user_id,
        dueDate="2026-05-28",
    )

    assert created_bodies
    assert created_bodies[0]["summary"] == "同步到飞书日历"
    assert created_bodies[0]["members"] == [{"id": "ou_task_assignee", "type": "user", "role": "assignee"}]
    assert created_bodies[0]["due"]["is_all_day"] is True
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "task_guid_created"
    assert payload["remoteUrl"].startswith("https://applink.feishu.cn/client/todo/detail")
    assert payload["details"]["taskMemberSyncStatus"] == "synced"


def test_create_task_syncs_feishu_task_center_even_without_matched_member(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_bodies: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: created_bodies.append(body)
        or {"code": 0, "data": {"task": {"guid": "task_guid_missing_member", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_missing_member"}}},
    )

    task_id = create_task(client, headers, dueDate="2026-05-28")

    assert created_bodies
    assert created_bodies[0]["members"] == []
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "task_guid_missing_member"
    assert payload["details"]["taskMemberSyncStatus"] == "missing_members"
    assert payload["details"]["taskMemberOpenIdCount"] == 0
    assert payload["details"]["taskMemberMissingUserCount"] >= 1
    assert "飞书账号手机号" in payload["details"]["taskMemberSyncMessage"]


def test_create_task_syncs_feishu_task_center_with_partial_member_match(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    organization_id = profile.json()["organizationId"]
    owner_id = bind_current_user_to_feishu(client, headers, receive_id="ou_task_owner_partial")
    collaborator_id = another_employee_id(client, organization_id, owner_id)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_bodies: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: created_bodies.append(body)
        or {"code": 0, "data": {"task": {"guid": "task_guid_partial_member", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_partial_member"}}},
    )

    task_id = create_task(client, headers, ownerId=owner_id, collaboratorIds=[owner_id, collaborator_id], dueDate="2026-05-28")

    assert created_bodies
    assert created_bodies[0]["members"] == [{"id": "ou_task_owner_partial", "type": "user", "role": "assignee"}]
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["details"]["taskMemberSyncStatus"] == "partial"
    assert payload["details"]["taskMemberOpenIdCount"] == 1
    assert payload["details"]["taskMemberMissingUserCount"] >= 1


def test_update_task_auto_updates_feishu_task_center_completion_and_members(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_task_owner")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: {"code": 0, "data": {"task": {"guid": "task_guid_update", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_update"}}},
    )
    updated_payloads: list[dict] = []
    added_members: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_task",
        lambda *, tenant_access_token, task_guid, body, update_fields: updated_payloads.append(
            {"task_guid": task_guid, "body": body, "update_fields": update_fields}
        )
        or {"code": 0, "data": {"task": {"guid": task_guid, "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_update"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_add_task_members",
        lambda *, tenant_access_token, task_guid, members: added_members.append({"task_guid": task_guid, "members": members}) or {"code": 0},
    )
    calendar_updates: list[dict] = []
    calendar_deletes: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: calendar_updates.append({"event_id": event_id, "body": body})
        or {"code": 0, "data": {"event": {"event_id": event_id}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: calendar_deletes.append(event_id) or {"code": 0},
    )
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")
    calendar_updates.clear()
    calendar_deletes.clear()

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "飞书任务中心更新测试", "progressStatus": "done"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert updated_payloads
    assert updated_payloads[0]["task_guid"] == "task_guid_update"
    assert updated_payloads[0]["body"]["summary"] == "飞书任务中心更新测试"
    assert "members" not in updated_payloads[0]["body"]
    assert updated_payloads[0]["body"]["completed_at"] > 0
    assert "completed_at" in updated_payloads[0]["update_fields"]
    assert added_members == [
        {"task_guid": "task_guid_update", "members": [{"id": "ou_task_owner", "type": "user", "role": "assignee"}]}
    ]
    assert calendar_updates == []
    assert calendar_deletes == []


def test_update_inbound_feishu_task_falls_back_to_member_invoker_when_tenant_unauthorized(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_member_invoker")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")
    state = client.app.state.app_state
    state.db.execute(
        """
        UPDATE org_feishu_sync_mappings
        SET remote_id = 'task_guid_user_created', remote_url = 'https://applink.feishu.cn/client/todo/detail?guid=task_guid_user_created'
        WHERE local_id = ? AND remote_type = 'feishu_task'
        """,
        (task_id,),
    )

    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_task",
        lambda **kwargs: (_ for _ in ()).throw(
            HTTPException(status_code=400, detail="Invoker is unauthorized to update a task for the task with guid 'task_guid_user_created'.")
        ),
    )
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    user_updates: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_task_as_user",
        lambda *, user_access_token, task_guid, body, update_fields: user_updates.append(
            {"user_access_token": user_access_token, "task_guid": task_guid, "body": body, "update_fields": update_fields}
        )
        or {"code": 0, "data": {"task": {"guid": task_guid, "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_user_created"}}},
    )

    response = client.patch(f"/api/v1/tasks/{task_id}", json={"progressStatus": "done"}, headers=headers)

    assert response.status_code == 200, response.text
    assert user_updates
    assert user_updates[0]["user_access_token"] == "user_access_demo"
    assert user_updates[0]["task_guid"] == "task_guid_user_created"
    assert user_updates[0]["body"]["completed_at"] > 0
    outbox = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_id = ? AND remote_type = 'feishu_task'",
        (task_id,),
    )
    assert outbox is None
    mapping = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'feishu_task'",
        (task_id,),
    )
    assert mapping["sync_status"] == "synced"
    assert '"taskUpdateInvoker": "member_user"' in str(mapping["metadata_json"])


def test_failed_feishu_task_sync_is_retried_from_outbox(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_retry_task_owner")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))

    def fail_create_task(*, tenant_access_token, body):
        raise RuntimeError("task api temporarily unavailable")

    monkeypatch.setattr(cloud_main, "_feishu_create_task", fail_create_task)
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")
    state = client.app.state.app_state
    row = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_type = 'task' AND local_id = ? AND action = 'retry_task_sync'",
        (task_id,),
    )
    assert row is not None
    assert row["sync_status"] == "failed"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.json()["status"] == "failed"

    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: {"code": 0, "data": {"task": {"guid": "task_guid_retry", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_retry"}}},
    )

    processed = cloud_main._process_feishu_sync_outbox_once(state)  # noqa: SLF001
    retried = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_type = 'task' AND local_id = ? AND action = 'retry_task_sync'",
        (task_id,),
    )

    assert processed == 1
    assert retried["sync_status"] == "synced"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "task_guid_retry"


def test_failed_calendar_mirror_sync_is_retried_from_outbox(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_calendar_retry_owner")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))

    def fail_create_calendar(*, tenant_access_token, calendar_id, body):
        raise RuntimeError("calendar api temporarily unavailable")

    monkeypatch.setattr(cloud_main, "_feishu_create_calendar_event", fail_create_calendar)
    task_id = create_task(client, headers, ownerId=user_id, scheduledStartAt="2026-05-28T09:00")
    state = client.app.state.app_state
    row = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_type = 'task' AND local_id = ? AND action = 'retry_calendar_sync'",
        (task_id,),
    )
    assert row is not None
    assert row["sync_status"] == "failed"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.json()["status"] == "failed"

    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: {"code": 0, "data": {"event": {"event_id": "evt_retry_mirror"}}},
    )

    processed = cloud_main._process_feishu_sync_outbox_once(state)  # noqa: SLF001
    retried = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_type = 'task' AND local_id = ? AND action = 'retry_calendar_sync'",
        (task_id,),
    )

    assert processed == 1
    assert retried["sync_status"] == "synced"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "evt_retry_mirror"


def test_feishu_task_remote_id_conflict_is_blocked_without_rebinding(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_task_conflict")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: {
            "code": 0,
            "data": {"task": {"guid": "task_guid_shared", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_shared"}},
        },
    )

    first_task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")
    second_task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-29")

    first_status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": first_task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    second_status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": second_task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert first_status.json()["status"] == "synced"
    assert first_status.json()["remoteId"] == "task_guid_shared"
    payload = second_status.json()
    assert payload["status"] == "mapping_conflict"
    assert payload["remoteId"] is None
    assert payload["details"]["conflictRemoteId"] == "task_guid_shared"
    assert payload["details"]["conflictLocalId"] == first_task_id
    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_sync_mappings WHERE remote_type = 'feishu_task' AND remote_id = ?",
        ("task_guid_shared",),
    )
    assert len(rows) == 1
    assert rows[0]["local_id"] == first_task_id


def test_calendar_remote_id_conflict_is_blocked_without_rebinding(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_calendar_conflict")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    task_counter = {"value": 0}

    def create_unique_task(*, tenant_access_token, body):
        task_counter["value"] += 1
        guid = f"task_guid_calendar_conflict_{task_counter['value']}"
        return {"code": 0, "data": {"task": {"guid": guid, "url": f"https://applink.feishu.cn/client/todo/detail?guid={guid}"}}}

    monkeypatch.setattr(cloud_main, "_feishu_create_task", create_unique_task)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: {"code": 0, "data": {"event": {"event_id": "evt_shared_mirror"}}},
    )

    first_task_id = create_task(client, headers, ownerId=user_id, scheduledStartAt="2026-05-28T09:00")
    second_task_id = create_task(client, headers, ownerId=user_id, scheduledStartAt="2026-05-29T09:00")

    first_status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": first_task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    second_status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": second_task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert first_status.json()["status"] == "synced"
    assert first_status.json()["remoteId"] == "evt_shared_mirror"
    payload = second_status.json()
    assert payload["status"] == "mapping_conflict"
    assert payload["remoteId"] is None
    assert payload["details"]["conflictRemoteId"] == "evt_shared_mirror"
    assert payload["details"]["conflictLocalId"] == first_task_id
    task_status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": second_task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert task_status.json()["status"] == "synced"
    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_sync_mappings WHERE remote_type = 'calendar_event' AND remote_id = ?",
        ("evt_shared_mirror",),
    )
    assert len(rows) == 1
    assert rows[0]["local_id"] == first_task_id


def test_feishu_mapping_diagnostics_reports_anomalies_without_repairing(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    organization_id = profile.json()["organizationId"]
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))

    first_task_id = create_task(client, headers, dueDate="2026-05-28")
    second_task_id = create_task(client, headers, dueDate="2026-05-29")
    state = client.app.state.app_state
    cloud_main._upsert_feishu_sync_mapping(  # noqa: SLF001
        state,
        organization_id=organization_id,
        local_type="task",
        local_id=first_task_id,
        remote_type="feishu_task",
        status_value="synced",
        message="测试重复远端任务。",
        remote_id="task_guid_duplicate_diag",
    )
    cloud_main._upsert_feishu_sync_mapping(  # noqa: SLF001
        state,
        organization_id=organization_id,
        local_type="task",
        local_id=second_task_id,
        remote_type="feishu_task",
        status_value="synced",
        message="测试重复远端任务。",
        remote_id="task_guid_duplicate_diag",
    )
    cloud_main._upsert_feishu_sync_mapping(  # noqa: SLF001
        state,
        organization_id=organization_id,
        local_type="task",
        local_id=first_task_id,
        remote_type="calendar_event",
        status_value="synced",
        message="缺少远端 ID。",
        clear_remote_id=True,
    )
    cloud_main._upsert_feishu_sync_mapping(  # noqa: SLF001
        state,
        organization_id=organization_id,
        local_type="task",
        local_id="task_missing_for_diag",
        remote_type="calendar_event",
        status_value="failed",
        message="孤儿映射。",
        remote_id="evt_orphan_diag",
    )

    issues = cloud_main._inspect_feishu_task_sync_mappings(state, organization_id=organization_id)  # noqa: SLF001
    issue_types = {item["type"] for item in issues}

    assert {"duplicate_remote_id", "missing_remote_id", "orphan_local_task"}.issubset(issue_types)
    duplicate = next(item for item in issues if item["type"] == "duplicate_remote_id" and item["remoteId"] == "task_guid_duplicate_diag")
    assert set(duplicate["localIds"]) == {first_task_id, second_task_id}
    rows = state.db.fetchall(
        "SELECT * FROM org_feishu_sync_mappings WHERE remote_type = 'feishu_task' AND remote_id = ?",
        ("task_guid_duplicate_diag",),
    )
    assert len(rows) == 2


def test_delete_task_clears_remote_feishu_task_mapping(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_task_delete")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_task",
        lambda *, tenant_access_token, body: {"code": 0, "data": {"task": {"guid": "task_guid_delete", "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_delete"}}},
    )
    delete_calls: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_task",
        lambda *, tenant_access_token, task_guid: delete_calls.append(task_guid) or {"code": 0},
    )
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")

    response = client.delete(f"/api/v1/tasks/{task_id}", headers=headers)

    assert response.status_code == 200, response.text
    assert delete_calls == ["task_guid_delete"]
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "feishu_task"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "skipped"
    assert payload["remoteId"] is None
    assert payload["details"]["deletedRemoteId"] == "task_guid_delete"


def test_feishu_task_inbound_first_poll_initializes_cursor_without_history_import(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_first_poll")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: pytest.fail("首次启用反向同步不应拉取和导入历史飞书任务"),
    )

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["initialized"] == 1
    task_count = client.app.state.app_state.db.scalar(
        "SELECT COUNT(1) FROM tasks WHERE organization_id = ? AND source_type = 'feishu_task'",
        (organization_id,),
    )
    assert task_count == 0


def test_feishu_task_inbound_skips_unmatched_members_without_creating_wrong_task(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_bound_member")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_bound_member")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: {
            "code": 0,
            "data": {
                "items": [
                    {
                        "guid": "task_guid_unmatched_member",
                        "summary": "无法匹配成员的飞书任务",
                        "members": [{"id": "ou_not_bound_in_yiyu"}],
                        "updated_at": "2026-05-28T10:05:00+08:00",
                    }
                ]
            },
        },
    )

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 0
    assert result["skipped"] == 1
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_unmatched_member",))
    assert task_row is None


def test_feishu_task_inbound_creates_regular_yiyu_task_for_single_member_and_calendar_mirror(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_owner")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_owner")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: {
            "code": 0,
            "data": {
                "items": [
                    {
                        "guid": "task_guid_inbound_private",
                        "summary": "手机上创建的飞书任务",
                        "description": "从飞书任务中心自动进入益语。",
                        "members": [{"id": "ou_inbound_owner", "role": "assignee"}],
                        "start": {"datetime": "2026-05-28T10:00:00+08:00"},
                        "due": {"datetime": "2026-05-28T11:00:00+08:00"},
                        "updated_at": "2026-05-28T10:05:00+08:00",
                        "url": "https://applink.feishu.cn/client/todo/detail?guid=task_guid_inbound_private",
                    }
                ]
            },
        },
    )

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_type = 'feishu_task' AND source_id = ?", ("task_guid_inbound_private",))
    assert task_row is not None
    assert task_row["title"] == "手机上创建的飞书任务"
    assert task_row["scope_mode"] == "COLLAB_SHARED"
    assert task_row["owner_id"] == user_id
    mapping = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'feishu_task'", (task_row["id"],))
    assert mapping["remote_id"] == "task_guid_inbound_private"
    calendar = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'calendar_event'", (task_row["id"],))
    assert calendar["sync_status"] == "synced"


def test_feishu_task_inbound_creates_collab_task_for_multiple_matched_members(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    owner_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_owner_multi")
    collaborator_id = another_employee_id(client, organization_id, owner_id)
    authorize_user_to_feishu(client, organization_id, collaborator_id, "ou_inbound_collab_multi")
    seed_feishu_inbound_cursor(client, organization_id, owner_id, "ou_inbound_owner_multi")
    seed_feishu_inbound_cursor(client, organization_id, collaborator_id, "ou_inbound_collab_multi")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    remote_task = {
        "guid": "task_guid_inbound_collab",
        "summary": "多人飞书协作任务",
        "members": [{"id": "ou_inbound_owner_multi"}, {"id": "ou_inbound_collab_multi"}],
        "due": {"date": "2026-05-29", "is_all_day": True},
        "updated_at": "2026-05-29T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_collab",))
    assert task_row["scope_mode"] == "COLLAB_SHARED"
    assert task_row["owner_id"] == owner_id
    collaborators = set(cloud_main._task_collaborator_ids(client.app.state.app_state, str(task_row["id"])))  # noqa: SLF001
    assert collaborators == {owner_id, collaborator_id}


def test_feishu_task_inbound_updates_existing_task_without_pushing_back_to_feishu(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_update")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_update")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    remote_task = {
        "guid": "task_guid_inbound_update",
        "summary": "飞书任务初始标题",
        "members": [{"id": "ou_inbound_update"}],
        "updated_at": "2026-05-29T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [remote_task]}})
    cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_update",))
    assert task_row["title"] == "飞书任务初始标题"
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_update", since="2026-05-29T09:00:01+08:00")

    def fail_if_outbound_update(**kwargs):
        raise AssertionError("反向同步更新益语任务时不应立即回推飞书任务")

    monkeypatch.setattr(cloud_main, "_feishu_update_task", fail_if_outbound_update)
    updated_remote_task = {
        **remote_task,
        "summary": "飞书任务修改后的标题",
        "description": "飞书侧更新描述",
        "completed_at": 1780000000000,
        "updated_at": "2026-05-29T10:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [updated_remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    updated_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_row["id"],))
    assert updated_row["title"] == "飞书任务修改后的标题"
    assert updated_row["description"] == "飞书侧更新描述"
    assert updated_row["progress_status"] == "done"


def test_feishu_task_inbound_does_not_overwrite_newer_local_completion(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_stale")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_stale")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    remote_task = {
        "guid": "task_guid_inbound_stale",
        "summary": "飞书旧状态不应覆盖本地完成",
        "members": [{"id": "ou_inbound_stale"}],
        "updated_at": "2026-05-29T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [remote_task]}})
    cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_stale",))
    assert task_row is not None
    client.app.state.app_state.db.execute(
        "UPDATE tasks SET progress_status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
        ("2026-05-29T10:05:00+08:00", "2026-05-29T10:05:00+08:00", task_row["id"]),
    )
    client.app.state.app_state.db.execute(
        "UPDATE org_feishu_sync_mappings SET last_synced_at = ? WHERE local_id = ? AND remote_type = 'feishu_task'",
        ("2026-05-29T09:00:00+08:00", task_row["id"]),
    )
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_stale", since="2026-05-29T09:00:01+08:00")
    stale_remote_task = {
        **remote_task,
        "summary": "飞书旧状态不应覆盖本地完成",
        "completed_at": 0,
        "updated_at": "2026-05-29T10:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [stale_remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["skipped"] == 1
    updated_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_row["id"],))
    assert updated_row["progress_status"] == "done"
    mapping = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'feishu_task'",
        (task_row["id"],),
    )
    assert mapping["sync_status"] == "skipped"
    assert "remote_stale" in str(mapping["metadata_json"]) or "skip_stale_remote" in str(mapping["metadata_json"])


def test_feishu_task_inbound_does_not_revert_local_due_date_when_outbound_sync_failed(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_due_guard")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-06-20")
    state = client.app.state.app_state

    def fail_update_task(**kwargs):
        raise HTTPException(status_code=400, detail="simulated task update outage")

    monkeypatch.setattr(cloud_main, "_feishu_update_task", fail_update_task)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_member_access_token_for_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no member token")),
    )

    response = client.patch(f"/api/v1/tasks/{task_id}", json={"dueDate": "2026-06-26"}, headers=headers)

    assert response.status_code == 200, response.text
    local_after_patch = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    assert local_after_patch["due_date"] == "2026-06-26"
    mapping_after_patch = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'feishu_task'",
        (task_id,),
    )
    assert mapping_after_patch["sync_status"] == "failed"

    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_due_guard", since="2026-06-20T00:00:00+08:00")
    stale_remote_task = {
        "guid": str(mapping_after_patch["remote_id"]),
        "summary": "同步到飞书日历",
        "description": "这是一条需要进入日程的任务。",
        "members": [{"id": "ou_inbound_due_guard"}],
        "due": {"date": "2026-06-20", "is_all_day": True},
        "updated_at": "2026-06-30T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [stale_remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(state)  # noqa: SLF001

    assert result["skipped"] == 1
    local_after_inbound = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    assert local_after_inbound["due_date"] == "2026-06-26"
    mapping_after_inbound = state.db.fetchone(
        "SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'feishu_task'",
        (task_id,),
    )
    assert mapping_after_inbound["sync_status"] == "queued"
    assert "pending_local_outbound" in str(mapping_after_inbound["metadata_json"])


def test_feishu_task_inbound_completion_keeps_existing_calendar_event(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_done_keep_calendar")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_done_keep_calendar")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    remote_task = {
        "guid": "task_guid_inbound_done_keep_calendar",
        "summary": "飞书任务完成保留日历",
        "members": [{"id": "ou_inbound_done_keep_calendar"}],
        "due": {"datetime": "2026-05-29T09:00:00+08:00"},
        "updated_at": "2026-05-29T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [remote_task]}})
    cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_done_keep_calendar",))
    assert task_row is not None
    calendar = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'calendar_event'", (task_row["id"],))
    assert calendar["remote_id"] == "evt_auto_mirror"
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_done_keep_calendar", since="2026-05-29T09:00:01+08:00")

    def fail_if_calendar_changed(**kwargs):
        raise AssertionError("飞书任务完成时不应改写或删除已有日历事件")

    monkeypatch.setattr(cloud_main, "_feishu_update_calendar_event", fail_if_calendar_changed)
    monkeypatch.setattr(cloud_main, "_feishu_delete_calendar_event", fail_if_calendar_changed)
    updated_remote_task = {
        **remote_task,
        "completed_at": 1780000000000,
        "updated_at": "2026-05-29T10:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [updated_remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    updated_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_row["id"],))
    assert updated_row["progress_status"] == "done"
    kept = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'calendar_event'", (task_row["id"],))
    assert kept["remote_id"] == "evt_auto_mirror"


def test_feishu_task_inbound_keeps_calendar_event_when_remote_task_loses_time(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_keep_calendar")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_keep_calendar")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    remote_task = {
        "guid": "task_guid_inbound_keep_calendar",
        "summary": "飞书任务带日程",
        "members": [{"id": "ou_inbound_keep_calendar"}],
        "due": {"datetime": "2026-05-29T09:00:00+08:00"},
        "updated_at": "2026-05-29T09:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [remote_task]}})
    cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_keep_calendar",))
    assert task_row is not None
    calendar = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'calendar_event'", (task_row["id"],))
    assert calendar["remote_id"] == "evt_auto_mirror"
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_keep_calendar", since="2026-05-29T09:00:01+08:00")

    def fail_if_calendar_changed(**kwargs):
        raise AssertionError("飞书任务变成无时间时不应改写或删除已有日历事件")

    monkeypatch.setattr(cloud_main, "_feishu_update_calendar_event", fail_if_calendar_changed)
    monkeypatch.setattr(cloud_main, "_feishu_delete_calendar_event", fail_if_calendar_changed)
    updated_remote_task = {
        "guid": "task_guid_inbound_keep_calendar",
        "summary": "飞书任务无日程",
        "members": [{"id": "ou_inbound_keep_calendar"}],
        "updated_at": "2026-05-29T10:00:00+08:00",
    }
    monkeypatch.setattr(cloud_main, "_feishu_list_member_recent_tasks", lambda **_: {"code": 0, "data": {"items": [updated_remote_task]}})

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    kept = client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ? AND remote_type = 'calendar_event'", (task_row["id"],))
    assert kept["sync_status"] == "skipped"
    assert kept["remote_id"] == "evt_auto_mirror"
    assert "task_without_time_keep_existing_event" in kept["metadata_json"]


def test_feishu_task_inbound_delete_removes_yiyu_task_and_calendar_mapping(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_delete")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_delete")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: {
            "code": 0,
            "data": {
                "items": [
                    {
                        "guid": "task_guid_inbound_delete",
                        "summary": "即将删除的飞书任务",
                        "members": [{"id": "ou_inbound_delete"}],
                        "start": {"datetime": "2026-05-30T10:00:00+08:00"},
                        "updated_at": "2026-05-30T10:00:00+08:00",
                    }
                ]
            },
        },
    )
    cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001
    task_row = client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE source_id = ?", ("task_guid_inbound_delete",))
    assert task_row is not None
    delete_calls: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: delete_calls.append(event_id) or {"code": 0},
    )
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_delete", since="2026-05-30T10:00:01+08:00")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: {
            "code": 0,
            "data": {
                "items": [
                    {
                        "guid": "task_guid_inbound_delete",
                        "deleted": True,
                        "members": [{"id": "ou_inbound_delete"}],
                        "updated_at": "2026-05-30T11:00:00+08:00",
                    }
                ]
            },
        },
    )

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 1
    assert client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_row["id"],)) is None
    assert client.app.state.app_state.db.fetchone("SELECT * FROM org_feishu_sync_mappings WHERE local_id = ?", (task_row["id"],)) is None
    assert delete_calls == ["evt_auto_mirror"]


def test_feishu_task_inbound_delete_without_mapping_does_not_delete_similar_yiyu_task(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    local_task_id = create_task(client, headers, title="标题相同但没有飞书映射", dueDate="2026-05-30")
    user_id = bind_current_user_to_feishu(client, headers, receive_id="ou_inbound_delete_no_mapping")
    seed_feishu_inbound_cursor(client, organization_id, user_id, "ou_inbound_delete_no_mapping")
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_member_access_token_for_user", lambda *args, **kwargs: "user_access_demo")
    monkeypatch.setattr(
        cloud_main,
        "_feishu_list_member_recent_tasks",
        lambda **_: {
            "code": 0,
            "data": {
                "items": [
                    {
                        "guid": "task_guid_deleted_without_mapping",
                        "summary": "标题相同但没有飞书映射",
                        "deleted": True,
                        "members": [{"id": "ou_inbound_delete_no_mapping"}],
                        "updated_at": "2026-05-30T11:00:00+08:00",
                    }
                ]
            },
        },
    )

    result = cloud_main._process_feishu_task_inbound_once(client.app.state.app_state)  # noqa: SLF001

    assert result["synced"] == 0
    assert result["skipped"] == 1
    assert client.app.state.app_state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (local_task_id,)) is not None


def test_sync_document_creates_feishu_docx_and_writes_blocks(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    bind_current_user_to_feishu(client, headers)
    created_titles: list[str] = []
    appended_blocks: list[list[dict]] = []
    sent_messages: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: created_titles.append(title)
        or {"code": 0, "data": {"document": {"document_id": "docx_demo_1"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [
            {"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown[:20], "text_element_style": {}}}], "style": {}}}
        ],
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_append_docx_blocks",
        lambda *, tenant_access_token, document_id, blocks: appended_blocks.append(blocks) or {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_text_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, text: sent_messages.append(text) or {"code": 0},
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_local_1",
            "title": "项目会议纪要",
            "content": "# 项目会议纪要\n\n- 已确认下一步。",
            "clientId": "client_demo",
            "triggerSource": "document_created",
            "notifyOnCreate": True,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "synced"
    assert payload["remoteType"] == "docx_document"
    assert payload["remoteId"] == "docx_demo_1"
    assert created_titles == ["项目会议纪要"]
    assert appended_blocks and appended_blocks[0][0]["block_type"] == 3
    assert sent_messages and "项目会议纪要" in sent_messages[0]
    assert "https://feishu.cn/docx/docx_demo_1" in sent_messages[0]


def test_sync_document_waits_for_member_feishu_binding(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    user_id = profile.json()["id"]
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=profile.json()["organizationId"],
        user_id=user_id,
        mobile="13800138000",
        receive_id="ou_delivery_only",
        match_status="matched",
        last_error=None,
    )
    created_titles: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: created_titles.append(title)
        or {"code": 0, "data": {"document": {"document_id": "docx_should_not_create"}}},
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_pending_binding",
            "title": "待绑定文档",
            "content": "需要当前成员先绑定飞书身份。",
            "clientId": "client_demo",
            "triggerSource": "document_created",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["remoteId"] is None
    assert payload["details"]["blockedReason"] == "member_authorization_required"
    assert created_titles == []


def test_sync_answer_export_document_notifies_current_user_on_create(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    user_id = profile.json()["id"]
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu(client, headers, receive_id="ou_doc_creator")
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=profile.json()["organizationId"],
        user_id=user_id,
        mobile="13800138000",
        receive_id="ou_admin",
        match_status="matched",
        last_error=None,
    )
    sent_messages: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: {"code": 0, "data": {"document": {"document_id": "docx_answer_export"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [{"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown, "text_element_style": {}}}], "style": {}}}],
    )
    monkeypatch.setattr(cloud_main, "_feishu_append_docx_blocks", lambda *, tenant_access_token, document_id, blocks: {"code": 0})
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_text_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, text: sent_messages.append(text) or {"code": 0},
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_answer_export",
            "title": "AI 回答导出",
            "content": "这是 AI 回答导出的正文。",
            "clientId": "client_demo",
            "triggerSource": "answer_export_document_created",
            "notifyOnCreate": False,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "synced"
    assert sent_messages and "AI 回答导出" in sent_messages[0]
    assert "https://feishu.cn/docx/docx_answer_export" in sent_messages[0]


def test_synced_document_defaults_to_org_editable_and_creator_owner(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    user_id = profile.json()["id"]
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu(client, headers, receive_id="ou_doc_creator")
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=profile.json()["organizationId"],
        user_id=user_id,
        mobile="13800138000",
        receive_id="ou_doc_creator",
        match_status="matched",
        last_error=None,
    )
    org_editable_calls: list[str] = []
    member_permission_calls: list[dict] = []
    owner_transfer_calls: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: {"code": 0, "data": {"document": {"document_id": "docx_permission_demo"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [{"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown, "text_element_style": {}}}], "style": {}}}],
    )
    monkeypatch.setattr(cloud_main, "_feishu_append_docx_blocks", lambda *, tenant_access_token, document_id, blocks: {"code": 0})
    monkeypatch.setattr(
        cloud_main,
        "_feishu_set_docx_org_editable",
        lambda *, tenant_access_token, document_id: org_editable_calls.append(document_id) or {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_add_docx_member_permission",
        lambda *, tenant_access_token, document_id, open_id, perm="full_access": member_permission_calls.append(
            {"documentId": document_id, "openId": open_id, "perm": perm}
        ) or {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_transfer_docx_owner",
        lambda *, tenant_access_token, document_id, open_id: owner_transfer_calls.append(
            {"documentId": document_id, "openId": open_id}
        ) or {"code": 0},
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_permission_demo",
            "title": "权限测试文档",
            "content": "这是需要全员可编辑的文档。",
            "clientId": "client_demo",
            "triggerSource": "document_created",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert org_editable_calls == ["docx_permission_demo"]
    assert member_permission_calls == [
        {"documentId": "docx_permission_demo", "openId": "ou_doc_creator", "perm": "full_access"}
    ]
    assert owner_transfer_calls == [{"documentId": "docx_permission_demo", "openId": "ou_doc_creator"}]
    assert payload["details"]["docxOrgEditableStatus"] == "synced"
    assert payload["details"]["docxCreatorOwnerStatus"] == "transferred"


def test_sync_document_preserves_inline_image_position_as_docx_image_block(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    bind_current_user_to_feishu(client, headers)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: {"code": 0, "data": {"document": {"document_id": "docx_inline_image"}}},
    )
    append_calls: list[list[dict]] = []

    def fake_append(*, tenant_access_token, document_id, blocks):
        append_calls.append(blocks)
        if blocks and blocks[0].get("block_type") == 27:
            return {"code": 0, "data": {"children": [{"block_id": "img_block_1"}]}}
        return {"code": 0, "data": {"children": [{"block_id": f"text_block_{len(append_calls)}"}]}}

    uploaded: list[dict] = []
    patched: list[dict] = []
    monkeypatch.setattr(cloud_main, "_feishu_append_docx_blocks", fake_append)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_upload_docx_image_media",
        lambda *, tenant_access_token, document_id, image_block_id, image_bytes, mime, alt="": uploaded.append(
            {"documentId": document_id, "imageBlockId": image_block_id, "mime": mime, "alt": alt, "size": len(image_bytes)}
        ) or {"code": 0, "data": {"file_token": "file_token_image"}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_set_docx_image_token",
        lambda *, tenant_access_token, document_id, image_block_id, file_token: patched.append(
            {"documentId": document_id, "imageBlockId": image_block_id, "fileToken": file_token}
        ) or {"code": 0},
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_inline_image",
            "title": "图片位置测试",
            "content": "图片前\n\n![阶段图](data:image/png;base64,aGVsbG8=)\n\n图片后",
            "clientId": "client_demo",
            "triggerSource": "document_created",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert [call[0]["block_type"] for call in append_calls[:3]] == [3, 27, 3]
    assert uploaded == [{"documentId": "docx_inline_image", "imageBlockId": "img_block_1", "mime": "image/png", "alt": "阶段图", "size": 5}]
    assert patched == [{"documentId": "docx_inline_image", "imageBlockId": "img_block_1", "fileToken": "file_token_image"}]
    details = response.json()["details"]
    assert details["inlineImageDetectedCount"] == 1
    assert details["inlineImageUploadedCount"] == 1
    assert details["inlineImageOmittedCount"] == 0


def test_sync_document_does_not_write_base64_text_when_image_upload_fails(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    bind_current_user_to_feishu(client, headers)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: {"code": 0, "data": {"document": {"document_id": "docx_inline_image_fail"}}},
    )
    appended_text = []

    def fake_append(*, tenant_access_token, document_id, blocks):
        appended_text.extend(str(block) for block in blocks)
        if blocks and blocks[0].get("block_type") == 27:
            return {"code": 0, "data": {"children": [{"block_id": "img_block_fail"}]}}
        return {"code": 0, "data": {"children": [{"block_id": "text_block"}]}}

    monkeypatch.setattr(cloud_main, "_feishu_append_docx_blocks", fake_append)
    monkeypatch.setattr(
        cloud_main,
        "_feishu_upload_docx_image_media",
        lambda **_: (_ for _ in ()).throw(RuntimeError("upload failed")),
    )

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={
            "localId": "doc_inline_image_fail",
            "title": "图片失败测试",
            "content": "![图](data:image/png;base64,aGVsbG8=)",
            "clientId": "client_demo",
            "triggerSource": "document_created",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    joined = "\n".join(appended_text)
    assert "aGVsbG8=" not in joined
    assert "data:image" not in joined
    assert "图片暂未同步" in joined
    assert response.json()["details"]["inlineImageFailedCount"] == 1


def test_sync_document_records_not_configured_without_feishu_credentials(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/feishu-sync/documents",
        json={"localId": "doc_local_2", "title": "未配置测试", "content": "正文"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "not_configured"
    assert "飞书应用" in payload["message"]


def test_sync_document_updates_existing_docx_in_place_when_mapping_exists(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    bind_current_user_to_feishu(client, headers)
    create_calls: list[str] = []
    clear_calls: list[str] = []
    append_calls: list[str] = []
    permission_calls: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: create_calls.append(title)
        or {"code": 0, "data": {"document": {"document_id": "docx_same"}}},
    )
    monkeypatch.setattr(cloud_main, "_feishu_clear_docx_document", lambda *, tenant_access_token, document_id: clear_calls.append(document_id))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [{"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown, "text_element_style": {}}}], "style": {}}}],
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_append_docx_blocks",
        lambda *, tenant_access_token, document_id, blocks: append_calls.append(document_id) or {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_ensure_feishu_docx_default_permissions",
        lambda state, *, tenant_access_token, document_id, current_user: permission_calls.append(document_id) or {},
    )

    first = client.post(
        "/api/v1/feishu-sync/documents",
        json={"localId": "doc_local_same", "title": "同一文档", "content": "第一版"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/feishu-sync/documents",
        json={"localId": "doc_local_same", "title": "同一文档", "content": "第二版"},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert create_calls == ["同一文档"]
    assert clear_calls == ["docx_same"]
    assert append_calls == ["docx_same", "docx_same"]
    assert permission_calls == ["docx_same"]
    assert second.json()["remoteId"] == "docx_same"
    assert second.json()["details"]["action"] == "update"
    assert second.json()["details"]["docxPermissionSyncSkipped"] is True


def test_sync_document_preserves_existing_docx_when_clear_fails(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    bind_current_user_to_feishu(client, headers)
    create_calls: list[str] = []
    append_calls: list[str] = []

    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: create_calls.append(title)
        or {"code": 0, "data": {"document": {"document_id": "docx_keep"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [{"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown, "text_element_style": {}}}], "style": {}}}],
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_append_docx_blocks",
        lambda *, tenant_access_token, document_id, blocks: append_calls.append(document_id) or {"code": 0},
    )

    first = client.post(
        "/api/v1/feishu-sync/documents",
        json={"localId": "doc_local_clear_failed", "title": "保留原文档", "content": "第一版"},
        headers=headers,
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_clear_docx_document",
        lambda *, tenant_access_token, document_id: (_ for _ in ()).throw(RuntimeError("clear failed")),
    )

    second = client.post(
        "/api/v1/feishu-sync/documents",
        json={"localId": "doc_local_clear_failed", "title": "保留原文档", "content": "第二版"},
        headers=headers,
    )
    row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_sync_outbox WHERE local_id = ?",
        ("doc_local_clear_failed",),
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert create_calls == ["保留原文档"]
    assert append_calls == ["docx_keep"]
    payload = second.json()
    assert payload["status"] == "failed"
    assert payload["remoteId"] == "docx_keep"
    assert payload["details"]["action"] == "update_failed_clear"
    assert payload["details"]["preservedRemoteId"] == "docx_keep"
    assert row["sync_status"] == "failed"


def test_feishu_delete_accepts_successful_non_json_response(monkeypatch):
    import httpx

    class DummyResponse:
        status_code = 204

        def json(self):
            raise ValueError("no json body")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def delete(self, *args, **kwargs):
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", DummyClient)

    assert cloud_main._feishu_api_delete(tenant_access_token="tenant_demo", path="/docx/v1/documents/demo/blocks/block_1") == {"code": 0, "data": {}}


def test_clear_docx_document_uses_children_batch_delete(monkeypatch):
    delete_calls: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_api_get",
        lambda *, tenant_access_token, path: {
            "code": 0,
            "data": {
                "items": [
                    {"block_id": "docx_demo", "children": ["block_1", "block_2"]},
                    {"block_id": "block_1", "parent_id": "docx_demo"},
                    {"block_id": "block_2", "parent_id": "docx_demo"},
                ]
            },
        },
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_api_delete_with_body",
        lambda **kwargs: delete_calls.append(kwargs) or {"code": 0},
    )

    cloud_main._feishu_clear_docx_document(tenant_access_token="tenant_demo", document_id="docx_demo")

    assert len(delete_calls) == 1
    assert delete_calls[0]["path"] == "/docx/v1/documents/docx_demo/blocks/docx_demo/children/batch_delete"
    assert delete_calls[0]["params"]["document_revision_id"] == -1
    assert delete_calls[0]["body"] == {"start_index": 0, "end_index": 2}


def test_outbox_retry_prefers_original_request_user(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["organizationId"]
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    actors: list[str] = []

    def fake_sync(state, *, payload, current_user, queue_on_failure=True):
        actors.append(current_user.id)
        return cloud_main.FeishuSyncStatusRecord(
            localType="document",
            localId=payload.localId,
            remoteType="docx_document",
            remoteId="docx_retry_user",
            remoteUrl="https://feishu.cn/docx/docx_retry_user",
            status="synced",
            message="ok",
            lastSyncedAt=cloud_main.now_iso(),
            updatedAt=cloud_main.now_iso(),
            details={},
        )

    cloud_main._queue_feishu_sync_outbox(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=organization_id,
        local_type="document",
        local_id="doc_retry_user",
        remote_type="docx_document",
        action="retry_docx_sync",
        payload={"title": "重试文档", "content": "重试正文", "requestedByUserId": profile["id"]},
        status_value="failed",
        last_error="first failed",
    )
    monkeypatch.setattr(cloud_main, "_sync_document_to_feishu_docx_record", fake_sync)

    processed = cloud_main._process_feishu_sync_outbox_once(client.app.state.app_state)  # noqa: SLF001

    assert processed == 1
    assert actors == [profile["id"]]


def test_outbox_retry_processes_failed_docx_sync(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu(client, headers, receive_id="ou_doc_retry")
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_docx_document",
        lambda *, tenant_access_token, title: {"code": 0, "data": {"document": {"document_id": "docx_retry"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_convert_markdown_to_blocks",
        lambda *, tenant_access_token, markdown: [{"block_type": 3, "text": {"elements": [{"text_run": {"content": markdown, "text_element_style": {}}}], "style": {}}}],
    )
    monkeypatch.setattr(cloud_main, "_feishu_append_docx_blocks", lambda *, tenant_access_token, document_id, blocks: {"code": 0})
    state = client.app.state.app_state
    cloud_main._queue_feishu_sync_outbox(  # noqa: SLF001
        state,
        organization_id=client.get("/api/v1/auth/me", headers=headers).json()["organizationId"],
        local_type="document",
        local_id="doc_retry",
        remote_type="docx_document",
        action="retry_docx_sync",
        payload={"title": "重试文档", "content": "重试正文", "clientId": "client_demo"},
        status_value="failed",
        last_error="first failed",
    )

    processed = cloud_main._process_feishu_sync_outbox_once(state)  # noqa: SLF001
    row = state.db.fetchone("SELECT * FROM org_feishu_sync_outbox WHERE local_id = ?", ("doc_retry",))

    assert processed == 1
    assert row["sync_status"] == "synced"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "document", "localId": "doc_retry", "remoteType": "docx_document"},
        headers=headers,
    )
    assert status.json()["status"] == "synced"


def test_update_task_updates_existing_calendar_mirror_when_time_or_title_changes(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_events: list[dict] = []
    updated_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_existing_mirror"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: updated_events.append({"event_id": event_id, "body": body})
        or {"code": 0, "data": {"event": {"event_id": event_id}}},
    )
    task_id = create_task(
        client,
        headers,
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T11:00",
    )

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "title": "更新后的飞书日程任务",
            "scheduledStartAt": "2026-05-26T14:00",
            "scheduledEndAt": "2026-05-26T15:30",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert len(created_events) == 1
    assert updated_events
    assert updated_events[0]["event_id"] == "evt_existing_mirror"
    assert updated_events[0]["body"]["summary"] == "更新后的飞书日程任务"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "evt_existing_mirror"
    assert payload["details"]["action"] == "update"


def test_update_task_updates_existing_calendar_event_mapping(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    organization_id = profile.json()["organizationId"]
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    deleted_events: list[str] = []
    updated_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: deleted_events.append(event_id) or {"code": 0},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: updated_events.append({"event_id": event_id, "body": body})
        or {"code": 0, "data": {"event": {"event_id": event_id}}},
    )
    task_id = create_task(client, headers, scheduledStartAt="2026-05-26T10:00", scheduledEndAt="2026-05-26T11:00")
    cloud_main._upsert_feishu_sync_mapping(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=organization_id,
        local_type="task",
        local_id=task_id,
        remote_type="calendar_event",
        status_value="synced",
        message="旧版同步到飞书日历。",
        remote_id="evt_remove_time",
        remote_url="https://feishu.example/calendar/evt_remove_time",
        metadata={"legacyCalendarEvent": True},
        last_synced_at=cloud_main.now_iso(),
    )

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "清理旧日程映射"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert deleted_events == []
    assert updated_events and updated_events[0]["event_id"] == "evt_remove_time"
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.json()["status"] == "synced"
    assert status.json()["remoteId"] == "evt_remove_time"
    assert status.json()["details"]["action"] == "update"


def test_update_task_keeps_existing_calendar_event_when_time_is_removed(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_keep_when_time_removed"}}},
    )
    update_calls: list[dict] = []
    delete_calls: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: update_calls.append({"event_id": event_id, "body": body})
        or {"code": 0, "data": {"event": {"event_id": event_id}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: delete_calls.append(event_id) or {"code": 0},
    )
    task_id = create_task(
        client,
        headers,
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T11:00",
    )
    assert created_events
    update_calls.clear()

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": None, "scheduledEndAt": None},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert update_calls == []
    assert delete_calls == []
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "skipped"
    assert payload["remoteId"] == "evt_keep_when_time_removed"
    assert payload["details"]["reason"] == "task_without_time_keep_existing_event"
    assert payload["details"]["keptExistingRemoteId"] == "evt_keep_when_time_removed"


def test_sync_task_calendar_route_creates_and_updates_mirror(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))

    created_events: list[dict] = []
    updated_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_demo_1"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: updated_events.append({"event_id": event_id, "body": body})
        or {"code": 0, "data": {"event": {"event_id": event_id}}},
    )

    task_id = create_task(
        client,
        headers,
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T11:30",
        durationMinutes=60,
    )

    first = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert first_payload["status"] == "synced"
    assert first_payload["remoteId"] == "evt_demo_1"
    assert first_payload["details"]["calendarMode"] == "scheduled"
    assert created_events and created_events[0]["reminders"] == [{"minutes": 0}]

    second = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "synced"
    assert updated_events and updated_events[0]["event_id"] == "evt_demo_1"


def test_sync_task_calendar_route_fails_for_inverted_time(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    calls: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda **kwargs: calls.append(kwargs) or {"code": 0, "data": {"event": {"event_id": "evt_should_not_create"}}},
    )

    task_id = create_task(
        client,
        headers,
        scheduledStartAt="2026-05-26T10:00",
        scheduledEndAt="2026-05-26T09:00",
    )
    response = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "failed"
    assert "结束时间早于" in payload["message"]
    assert calls == []


def test_sync_task_calendar_route_creates_deadline_time_mirror(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_deadline"}}},
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_update_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id, body: {"code": 0, "data": {"event": {"event_id": event_id}}},
    )

    task_id = create_task(client, headers, deadlineAt="2026-05-26T18:00")
    response = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "evt_deadline"
    assert payload["details"]["calendarMode"] == "deadline"
    assert created_events
    assert created_events[0]["reminders"] == [{"minutes": 0}]


def test_date_only_task_creates_calendar_mirror_at_default_morning_time(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    created_events: list[dict] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: created_events.append(body)
        or {"code": 0, "data": {"event": {"event_id": "evt_date_only"}}},
    )

    task_id = create_task(client, headers, dueDate="2026-05-26")

    assert task_id
    assert created_events
    assert created_events[0]["start_time"]["timestamp"] == str(int(cloud_main.datetime(2026, 5, 26, 9, tzinfo=cloud_main.FEISHU_SYNC_TZ).timestamp()))
    assert created_events[0]["end_time"]["timestamp"] == str(int(cloud_main.datetime(2026, 5, 26, 10, tzinfo=cloud_main.FEISHU_SYNC_TZ).timestamp()))
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["details"]["calendarMode"] == "date_only"
    assert payload["details"]["dateOnlyDefaultTime"] == "09:00"


def test_sync_task_calendar_skips_task_without_explicit_time(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    calls: list[dict] = []
    monkeypatch.setattr(cloud_main, "_feishu_create_calendar_event", lambda **kwargs: calls.append(kwargs) or {})

    task_id = create_task(client, headers)
    response = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "skipped"
    assert "没有明确时间" in payload["message"]
    assert calls == []


def test_done_task_without_existing_calendar_does_not_create_mirror(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    calls: list[dict] = []
    monkeypatch.setattr(cloud_main, "_feishu_create_calendar_event", lambda **kwargs: calls.append(kwargs) or {})
    task_id = create_task(client, headers, dueDate="2026-05-26")
    state = client.app.state.app_state
    calls.clear()
    state.db.execute(
        "DELETE FROM org_feishu_sync_mappings WHERE local_type = 'task' AND local_id = ? AND remote_type = 'calendar_event'",
        (task_id,),
    )
    response = client.patch(f"/api/v1/tasks/{task_id}", json={"progressStatus": "done"}, headers=headers)

    assert response.status_code == 200, response.text
    assert calls == []
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.json()["status"] == "skipped"
    assert "已完成" in status.json()["message"]


def test_feishu_calendar_status_is_synced_after_task_center_creates_mirror(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    task_id = create_task(client, headers, scheduledStartAt="2026-05-26T10:00")

    response = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "synced"
    assert response.json()["details"]["calendarMirror"] is True


def test_feishu_doc_import_status_requires_document_token(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu(client, headers)

    response = client.get("/api/v1/feishu-doc-import/status", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["linked"] is True
    assert payload["ready"] is False
    assert "令牌" in payload["reason"]


def test_feishu_doc_import_resolves_links_after_member_token(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu_docs(client, headers)

    def fake_user_api_post(*, user_access_token, path, body=None):
        assert user_access_token == "user_access_demo"
        assert path == "/drive/v1/metas/batch_query"
        assert body == {
            "request_docs": [{"doc_token": "ABCabc123", "doc_type": "docx"}],
            "with_url": True,
        }
        return {
            "code": 0,
            "data": {
                "metas": [
                    {
                        "doc_token": "ABCabc123",
                        "doc_type": "docx",
                        "title": "真实飞书标题",
                        "url": "https://example.feishu.cn/docx/ABCabc123",
                    }
                ]
            },
        }

    monkeypatch.setattr(cloud_main, "_feishu_user_api_post", fake_user_api_post)

    status = client.get("/api/v1/feishu-doc-import/status", headers=headers)
    response = client.post(
        "/api/v1/feishu-doc-import/resolve-links",
        json={"links": ["https://example.feishu.cn/docx/ABCabc123"]},
        headers=headers,
    )

    assert status.status_code == 200, status.text
    assert status.json()["ready"] is True
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["token"] == "ABCabc123"
    assert item["type"] == "docx"
    assert item["title"] == "真实飞书标题"


def test_feishu_doc_import_search_returns_user_visible_candidates(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu_docs(client, headers)

    def fake_user_api_post(*, user_access_token, path, body=None):
        assert user_access_token == "user_access_demo"
        assert path == "/drive/v1/files/search"
        assert body == {"search_key": "导入测试", "count": 10, "offset": 0}
        return {
            "code": 0,
            "data": {
                "items": [
                    {
                        "obj_token": "docx_search_1",
                        "obj_type": "docx",
                        "title": "飞书导入测试文档",
                        "url": "https://example.feishu.cn/docx/docx_search_1",
                    }
                ]
            },
        }

    monkeypatch.setattr(cloud_main, "_feishu_user_api_post", fake_user_api_post)

    response = client.post(
        "/api/v1/feishu-doc-import/search",
        json={"query": "导入测试", "pageSize": 10},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"][0]["title"] == "飞书导入测试文档"
    assert payload["items"][0]["token"] == "docx_search_1"


def test_feishu_doc_import_export_encodes_chinese_filename_header(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu_docs(client, headers)
    monkeypatch.setattr(cloud_main, "_feishu_export_docx_bytes", lambda **_: b"docx-bytes")

    response = client.post(
        "/api/v1/feishu-doc-import/export-docx",
        json={"token": "docx_zh_title", "type": "docx", "title": "中文标题"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.content == b"docx-bytes"
    assert response.headers["x-feishu-file-name"] == "%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98.docx"
    assert "filename*=UTF-8''%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98.docx" in response.headers["content-disposition"]


def test_feishu_doc_import_registers_mapping_metadata(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    bind_current_user_to_feishu_docs(client, headers)

    response = client.post(
        "/api/v1/feishu-doc-import/mappings",
        json={
            "localId": "local_doc_import_1",
            "remoteId": "docx_remote_1",
            "remoteUrl": "https://example.feishu.cn/docx/docx_remote_1",
            "title": "飞书导入映射测试",
            "clientId": "client_demo",
            "remoteUpdatedAt": "2026-06-11T10:00:00+00:00",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "docx_remote_1"
    assert payload["details"]["direction"] == "feishu_to_workbench"
    assert payload["details"]["clientId"] == "client_demo"
    assert payload["details"]["remoteUpdatedAt"] == "2026-06-11T10:00:00+00:00"
