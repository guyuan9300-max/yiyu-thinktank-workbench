from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402
from app.security import hash_password  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> tuple[dict[str, str], dict]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['accessToken']}"}, payload["user"]


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> str:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_demo_app",
            "appSecret": "secret_demo",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["organizationId"]


def seed_member_mobile(client: TestClient, user_id: str, mobile: str) -> None:
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET feishu_mobile = ?, updated_at = ? WHERE id = ?",
        (mobile, now_iso(), user_id),
    )


def ensure_member(client: TestClient, *, user_id: str, organization_id: str, full_name: str, email: str) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role,
            account_status, membership_status, approved_at, recent_mentions_json,
            created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', 'approved', ?, '[]', ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (user_id, organization_id, email, full_name, hash_password("Simulate123!"), now_iso(), now_iso(), now_iso()),
    )


def test_create_task_sends_card_notifications_to_phone_matched_owner_and_collaborators(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@example.org", "Admin123!")
    org_id = save_org_feishu_integration(client, admin_headers, monkeypatch)
    ensure_member(client, user_id="user_qinghua", organization_id=org_id, full_name="庆华", email="member-a@example.org")
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else "ou_qinghua" if mobile == "13900139000" else None,
            None if mobile in {"13800138000", "13900139000"} else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {
                "token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "card": card,
            }
        ) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】飞书任务提醒",
            "description": "创建后应通知负责人和协作者",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-10",
            "dueDate": "2026-04-10T18:00",
            "collaboratorIds": [admin_user["id"], "user_qinghua"],
            "ownerId": "user_qinghua",
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    assert len(sent_cards) == 2
    assert {str(item["receive_id"]) for item in sent_cards} == {"ou_admin", "ou_qinghua"}
    assert all(str(item["card"]["header"]["template"]) == "blue" for item in sent_cards)
    assert any("你的角色：负责人" in str(item["card"]["elements"][1]["content"]) for item in sent_cards)
    assert any("你的角色：协作者" in str(item["card"]["elements"][1]["content"]) for item in sent_cards)

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_task_notifications WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(rows) == 2
    assert {str(row["delivery_status"]) for row in rows} == {"sent"}

    target_rows = client.app.state.app_state.db.fetchall(
        "SELECT user_id, match_status, receive_id FROM org_feishu_delivery_targets WHERE organization_id = ? ORDER BY user_id ASC",
        (org_id,),
    )
    status_by_user = {str(row["user_id"]): (str(row["match_status"]), str(row["receive_id"])) for row in target_rows}
    assert status_by_user[admin_user["id"]] == ("matched", "ou_admin")
    assert status_by_user["user_qinghua"] == ("matched", "ou_qinghua")

    generic_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, delivery_channel FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(generic_rows) == 2
    assert {str(row["delivery_status"]) for row in generic_rows} == {"sent_card"}
    assert {str(row["delivery_channel"]) for row in generic_rows} == {"interactive"}


def test_title_only_update_is_queued_then_sent_as_content_notification(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_main.FeishuNotificationService, "task_change_merge_window_seconds", 0)
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@example.org", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_lookup_open_id_by_mobile", lambda *, tenant_access_token, mobile: ("ou_admin", None))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append({"receive_id": receive_id, "card": card}) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "只改标题延迟提醒",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "collaboratorIds": [admin_user["id"]],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    before_count = client.app.state.app_state.db.fetchone(
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'content_fields_changed'",
        (task_id,),
    )["count"]
    sent_cards.clear()

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "只改标题进入延迟提醒"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert sent_cards == []

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT message_type, delivery_status FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert any(str(row["message_type"]) == "task_content_changed" and str(row["delivery_status"]) == "queued" for row in queued_rows)

    client.app.state.app_state.feishu_notifications.process_due_notifications()

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_admin"
    assert "任务内容已更新" in str(sent_cards[0]["card"]["header"]["title"]["content"])
    assert "变更项：标题" in str(sent_cards[0]["card"]["elements"][1]["content"])

    after_count = client.app.state.app_state.db.fetchone(
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'content_fields_changed'",
        (task_id,),
    )["count"]
    assert after_count == before_count + 1


def test_key_field_changes_send_immediately_and_missing_mobile_recipients_are_skipped(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@example.org", "Admin123!")
    org_id = save_org_feishu_integration(client, admin_headers, monkeypatch)
    ensure_member(client, user_id="user_qinghua", organization_id=org_id, full_name="庆华", email="member-a@example.org")
    ensure_member(client, user_id="user_jianing", organization_id=org_id, full_name="嘉宁", email="member-b@example.org")
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else "ou_qinghua" if mobile == "13900139000" else None,
            None if mobile in {"13800138000", "13900139000"} else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {
                "receive_id": receive_id,
                "card": card,
            }
        ) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】变更任务提醒",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-10",
            "dueDate": "2026-04-10T10:00",
            "collaboratorIds": [admin_user["id"], "user_qinghua"],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    sent_cards.clear()

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "deadlineAt": "2026-04-11T14:30",
            "ownerId": "user_qinghua",
            "collaboratorIds": ["user_qinghua", "user_jianing"],
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_qinghua"
    assert "变更项：截止时间、负责人、协作者" in str(sent_cards[0]["card"]["elements"][1]["content"])

    rows = client.app.state.app_state.db.fetchall(
        "SELECT recipient_user_id, delivery_status, changed_fields_json, delivery_message FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'key_fields_changed' ORDER BY recipient_user_id ASC",
        (task_id,),
    )
    assert len(rows) == 2
    status_by_user = {str(row["recipient_user_id"]): str(row["delivery_status"]) for row in rows}
    assert status_by_user == {"user_jianing": "skipped_unbound", "user_qinghua": "sent"}
    assert any("成员尚未填写飞书手机号" in str(row["delivery_message"]) for row in rows if str(row["recipient_user_id"]) == "user_jianing")
    assert all("deadlineAt" in str(row["changed_fields_json"]) for row in rows)
    assert all("ownerId" in str(row["changed_fields_json"]) for row in rows)
    assert all("collaboratorIds" in str(row["changed_fields_json"]) for row in rows)

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, recipient_user_id FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? AND message_type = 'task_changed' ORDER BY recipient_user_id ASC",
        (task_id,),
    )
    assert {str(row["delivery_status"]) for row in queued_rows} == {"sent_card", "skipped_unbound"}


def test_immediate_change_absorbs_pending_content_change_into_one_notification(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_main.FeishuNotificationService, "task_change_merge_window_seconds", 999)
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@example.org", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_lookup_open_id_by_mobile", lambda *, tenant_access_token, mobile: ("ou_admin", None))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append({"receive_id": receive_id, "card": card}) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "混合变更任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "collaboratorIds": [admin_user["id"]],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    sent_cards.clear()

    title_updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "标题先改一下"},
        headers=admin_headers,
    )
    assert title_updated.status_code == 200, title_updated.text
    assert sent_cards == []

    due_updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-04-11T11:30"},
        headers=admin_headers,
    )
    assert due_updated.status_code == 200, due_updated.text

    assert len(sent_cards) == 1
    merged_card_text = str(sent_cards[0]["card"]["elements"][1]["content"])
    assert "变更项：标题、截止时间" in merged_card_text or "变更项：截止时间、标题" in merged_card_text

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, delivery_message FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? AND message_type = 'task_content_changed' ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(queued_rows) == 1
    assert str(queued_rows[0]["delivery_status"]) == "cancelled"
    assert "已并入一次即时任务更新提醒" in str(queued_rows[0]["delivery_message"])
