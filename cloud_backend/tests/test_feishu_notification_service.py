from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


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


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> None:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={"appId": "cli_demo_app", "appSecret": "secret_demo"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def seed_member_mobile(client: TestClient, user_id: str, mobile: str) -> None:
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET feishu_mobile = ?, updated_at = ? WHERE id = ?",
        (mobile, now_iso(), user_id),
    )


def configure_send_mocks(monkeypatch, sent_cards: list[dict[str, object]]) -> None:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else None,
            None if mobile == "13800138000" else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {"receive_id": receive_id, "card": card}
        )
        or {"code": 0},
    )


def test_weekly_review_send_uses_unified_card_service(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W15",
            "taskEntries": [],
            "workProgress": "推进飞书提醒卡片化\n梳理任务提醒链路",
            "workBlocker": "还需要完善逾期提醒",
            "nextWeekFocus": "补齐消息统一规范",
            "workFreeNote": "这周把四类消息先收进同一条云端发送链路。",
            "personalGrowthNote": "开始形成统一通知底座意识。",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_admin"
    assert sent_cards[0]["card"]["header"]["template"] == "cyan"

    row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'weekly_review' ORDER BY created_at DESC LIMIT 1"
    )
    assert row is not None
    assert str(row["delivery_status"]) == "sent_card"


def test_badge_unlock_endpoint_sends_once_with_dedupe(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    payload = {
        "badgeId": "badge_exec_demo",
        "badgeName": "执行推进试跑者",
        "categoryName": "执行推进",
        "badgeDescription": "完成第一次真实飞书提醒链路打通。",
        "xp": 18,
    }
    first = client.post("/api/v1/me/feishu-notifications/badge-unlock", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/me/feishu-notifications/badge-unlock", json=payload, headers=headers)
    assert second.status_code == 200, second.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["card"]["header"]["template"] == "green"
    assert first.json()["deliveryStatus"] == "sent_card"
    assert second.json()["deliveryStatus"] == "sent_card"

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'badge_unlock' ORDER BY created_at ASC"
    )
    assert len(rows) == 1


def test_overdue_digest_sends_red_summary_once_per_day(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "逾期测试任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-09",
            "dueDate": "2026-04-09T09:00",
            "collaboratorIds": [user["id"]],
            "ownerId": user["id"],
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    sent_cards.clear()

    service = client.app.state.app_state.feishu_notifications
    assert service is not None
    reference_time = datetime(2026, 4, 13, 9, 0, 0)
    service.process_overdue_digest(reference_time=reference_time)
    service.process_overdue_digest(reference_time=reference_time)

    assert len(sent_cards) == 1
    assert sent_cards[0]["card"]["header"]["template"] == "red"

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'overdue_digest' ORDER BY created_at ASC"
    )
    assert len(rows) == 1
    assert str(rows[0]["delivery_status"]) == "sent_card"


def test_overdue_digest_does_not_treat_date_only_due_today_as_overdue(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "今天到期但还没过期的任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-04-13",
            "collaboratorIds": [user["id"]],
            "ownerId": user["id"],
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    sent_cards.clear()

    service = client.app.state.app_state.feishu_notifications
    assert service is not None
    service.process_overdue_digest(reference_time=datetime(2026, 4, 13, 10, 0, 0))

    assert sent_cards == []


def test_overdue_digest_excludes_completed_tasks(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "已经完成的历史任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-04-09",
            "collaboratorIds": [user["id"]],
            "ownerId": user["id"],
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    client.app.state.app_state.db.execute(
        "UPDATE tasks SET progress_status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
        ("2026-04-10T09:30:00", now_iso(), task_id),
    )
    sent_cards.clear()

    service = client.app.state.app_state.feishu_notifications
    assert service is not None
    service.process_overdue_digest(reference_time=datetime(2026, 4, 13, 10, 0, 0))

    assert sent_cards == []
