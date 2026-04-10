from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
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


def test_create_task_sends_text_notifications_to_phone_matched_owner_and_collaborators(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    org_id = save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_messages: list[dict[str, str]] = []
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
        "_feishu_send_text_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, text: sent_messages.append(
            {
                "token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "text": text,
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

    assert len(sent_messages) == 2
    assert {item["receive_id"] for item in sent_messages} == {"ou_admin", "ou_qinghua"}
    assert all("【益语智库】你有新的协作任务" in item["text"] for item in sent_messages)
    assert any("你的角色：负责人" in item["text"] for item in sent_messages)
    assert any("你的角色：协作者" in item["text"] for item in sent_messages)

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


def test_title_only_update_does_not_send_feishu_notification(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_lookup_open_id_by_mobile", lambda *, tenant_access_token, mobile: ("ou_admin", None))
    monkeypatch.setattr(cloud_main, "_feishu_send_text_message", lambda **_: {"code": 0})

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "只改标题不提醒",
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
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ?",
        (task_id,),
    )["count"]

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "只改标题仍不提醒"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    after_count = client.app.state.app_state.db.fetchone(
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ?",
        (task_id,),
    )["count"]
    assert before_count == after_count


def test_key_field_changes_send_and_missing_mobile_recipients_are_skipped(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_messages: list[dict[str, str]] = []
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
        "_feishu_send_text_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, text: sent_messages.append(
            {
                "receive_id": receive_id,
                "text": text,
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
    sent_messages.clear()

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "dueDate": "2026-04-11T14:30",
            "ownerId": "user_qinghua",
            "collaboratorIds": ["user_qinghua", "user_jianing"],
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    assert len(sent_messages) == 1
    assert sent_messages[0]["receive_id"] == "ou_qinghua"
    assert "变更项：截止时间、负责人、协作者" in sent_messages[0]["text"]

    rows = client.app.state.app_state.db.fetchall(
        "SELECT recipient_user_id, delivery_status, changed_fields_json, delivery_message FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'key_fields_changed' ORDER BY recipient_user_id ASC",
        (task_id,),
    )
    assert len(rows) == 2
    status_by_user = {str(row["recipient_user_id"]): str(row["delivery_status"]) for row in rows}
    assert status_by_user == {"user_jianing": "skipped_unbound", "user_qinghua": "sent"}
    assert any("成员尚未填写飞书手机号" in str(row["delivery_message"]) for row in rows if str(row["recipient_user_id"]) == "user_jianing")
    assert all("dueDate" in str(row["changed_fields_json"]) for row in rows)
    assert all("ownerId" in str(row["changed_fields_json"]) for row in rows)
    assert all("collaboratorIds" in str(row["changed_fields_json"]) for row in rows)
