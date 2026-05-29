from __future__ import annotations

import sys
from pathlib import Path

import pytest
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
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.org", "password": "Admin123!"})
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


def test_create_task_does_not_create_extra_calendar_event_when_task_center_is_primary(tmp_path, monkeypatch):
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

    assert created_events == []
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "skipped"
    assert payload["remoteId"] is None
    assert payload["details"]["calendarSyncRetired"] is True
    assert payload["details"]["triggerSource"].endswith("calendar_route_retired") or payload["details"]["triggerSource"].endswith("task_center_primary")


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
    task_id = create_task(client, headers, ownerId=user_id, dueDate="2026-05-28")

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


def test_sync_document_creates_feishu_docx_and_writes_blocks(tmp_path, monkeypatch):
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
        receive_id="ou_admin",
        match_status="matched",
        last_error=None,
    )
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


def test_sync_answer_export_document_notifies_current_user_on_create(tmp_path, monkeypatch):
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


def test_update_task_does_not_update_extra_calendar_event_when_time_or_title_changes(tmp_path, monkeypatch):
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
        or {"code": 0, "data": {"event": {"event_id": "evt_should_not_create"}}},
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
    assert created_events == []
    assert updated_events == []
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "skipped"
    assert payload["details"]["calendarSyncRetired"] is True


def test_update_task_deletes_existing_legacy_calendar_event_mapping(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    profile = client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200, profile.text
    organization_id = profile.json()["organizationId"]
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    deleted_events: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: deleted_events.append(event_id) or {"code": 0},
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
    assert deleted_events == ["evt_remove_time"]
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.json()["status"] == "skipped"
    assert status.json()["remoteId"] is None
    assert status.json()["details"]["deleteStatus"] == "deleted"


def test_sync_task_calendar_route_is_retired_and_does_not_create_event(tmp_path, monkeypatch):
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
    assert first_payload["status"] == "skipped"
    assert first_payload["remoteId"] is None
    assert first_payload["details"]["calendarSyncRetired"] is True
    assert created_events == []

    second = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "skipped"
    assert updated_events == []


def test_sync_task_calendar_route_retired_even_for_inverted_time(tmp_path, monkeypatch):
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
    assert payload["status"] == "skipped"
    assert "任务中心" in payload["message"]
    assert calls == []


def test_sync_task_calendar_route_retired_for_deadline_time(tmp_path, monkeypatch):
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
    assert payload["status"] == "skipped"
    assert payload["details"]["calendarSyncRetired"] is True
    assert created_events == []


def test_sync_task_calendar_skips_task_without_explicit_time(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    calls: list[dict] = []
    monkeypatch.setattr(cloud_main, "_feishu_create_calendar_event", lambda **kwargs: calls.append(kwargs) or {})

    task_id = create_task(client, headers)
    response = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "skipped"
    assert "任务中心" in payload["message"]
    assert calls == []


def test_feishu_calendar_status_is_skipped_when_direct_calendar_sync_is_retired(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    task_id = create_task(client, headers, scheduledStartAt="2026-05-26T10:00")

    response = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "skipped"
    assert response.json()["details"]["calendarSyncRetired"] is True
