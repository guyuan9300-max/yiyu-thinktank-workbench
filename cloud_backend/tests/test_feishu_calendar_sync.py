from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402


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


def test_create_task_auto_syncs_calendar_when_task_has_explicit_time(tmp_path, monkeypatch):
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

    assert len(created_events) == 1
    status = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["remoteId"] == "evt_auto_create"
    assert payload["details"]["triggerSource"] == "task_created"


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
    assert second.json()["remoteId"] == "docx_same"
    assert second.json()["details"]["action"] == "update"


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


def test_update_task_auto_updates_calendar_when_time_or_title_changes(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: {"code": 0, "data": {"event": {"event_id": "evt_auto_update"}}},
    )
    updated_events: list[dict] = []
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
    assert updated_events
    assert updated_events[0]["event_id"] == "evt_auto_update"
    assert updated_events[0]["body"]["summary"] == "更新后的飞书日程任务"


def test_update_task_removing_explicit_time_deletes_mapped_calendar_event(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    save_org_feishu_integration(client, headers, monkeypatch)
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_create_calendar_event",
        lambda *, tenant_access_token, calendar_id, body: {"code": 0, "data": {"event": {"event_id": "evt_remove_time"}}},
    )
    deleted_events: list[str] = []
    monkeypatch.setattr(
        cloud_main,
        "_feishu_delete_calendar_event",
        lambda *, tenant_access_token, calendar_id, event_id: deleted_events.append(event_id) or {"code": 0},
    )
    task_id = create_task(client, headers, scheduledStartAt="2026-05-26T10:00", scheduledEndAt="2026-05-26T11:00")

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"scheduledStartAt": None, "scheduledEndAt": None},
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


def test_sync_task_calendar_creates_and_then_updates_event(tmp_path, monkeypatch):
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
    assert created_events[0]["start_time"]["timestamp"] < created_events[0]["end_time"]["timestamp"]

    second = client.post(f"/api/v1/feishu-sync/calendar/tasks/{task_id}", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "synced"
    assert updated_events[0]["event_id"] == "evt_demo_1"


def test_sync_task_calendar_rejects_inverted_time_without_feishu_call(tmp_path, monkeypatch):
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
    assert payload["status"] == "time_invalid"
    assert "结束时间" in payload["message"]
    assert calls == []


def test_sync_task_calendar_uses_deadline_time_as_short_event(tmp_path, monkeypatch):
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
    assert payload["details"]["calendarMode"] == "deadline"
    assert int(created_events[0]["end_time"]["timestamp"]) - int(created_events[0]["start_time"]["timestamp"]) == 30 * 60


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
    assert "没有明确时间" in payload["message"]
    assert calls == []


def test_feishu_sync_status_reports_missing_config_after_auto_sync_attempt(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client)
    task_id = create_task(client, headers, scheduledStartAt="2026-05-26T10:00")

    response = client.get(
        "/api/v1/feishu-sync/status",
        params={"localType": "task", "localId": task_id, "remoteType": "calendar_event"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "not_configured"
