from __future__ import annotations

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402
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
        (user_id, organization_id, email, full_name, hash_password("Simulate123!"), datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat()),
    )


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> str:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={"appId": "cli_demo_app", "appSecret": "secret_demo"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return str(response.json()["organizationId"])


def disable_outbound_feishu(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(cloud_main, "_notify_task_feishu_recipients", lambda *args, **kwargs: None)
    service = client.app.state.app_state.feishu_notifications
    if service is not None:
        monkeypatch.setattr(service, "notify_weekly_review", lambda *args, **kwargs: None)


def seed_delivery_target(client: TestClient, organization_id: str, user_id: str, receive_id: str) -> None:
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=organization_id,
        user_id=user_id,
        mobile="13800138000",
        receive_id=receive_id,
        match_status="matched",
        last_error=None,
    )


def create_task(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
    owner_id: str,
    collaborator_ids: list[str] | None = None,
    event_line_id: str | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": start_date or today,
            "dueDate": due_date or f"{today}T18:00",
            "collaboratorIds": collaborator_ids or [],
            "ownerId": owner_id,
            "eventLineId": event_line_id,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_inbound_service(client: TestClient) -> cloud_main.FeishuInboundService:
    return cloud_main.FeishuInboundService(client.app.state.app_state)


def capture_query_delivery(monkeypatch) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = {"texts": [], "cards": [], "patched_cards": []}

    def fake_send_text_message(*, tenant_access_token, receive_id_type, receive_id, text):
        records["texts"].append({"receive_id": receive_id, "text": text})
        return {"code": 0, "data": {"message_id": f"om_text_{len(records['texts'])}"}}

    def fake_send_interactive_message(*, tenant_access_token, receive_id_type, receive_id, card):
        message_id = f"om_card_{len(records['cards']) + 1}"
        records["cards"].append({"receive_id": receive_id, "card": card, "message_id": message_id})
        return {"code": 0, "data": {"message_id": message_id}}

    def fake_patch_interactive_message(*, tenant_access_token, message_id, card):
        records["patched_cards"].append({"message_id": message_id, "card": card})
        return {"code": 0, "data": {"message_id": message_id}}

    monkeypatch.setattr(cloud_main, "_feishu_send_text_message", fake_send_text_message)
    monkeypatch.setattr(cloud_main, "_feishu_send_interactive_message", fake_send_interactive_message)
    monkeypatch.setattr(cloud_main, "_feishu_patch_interactive_message", fake_patch_interactive_message)
    return records


def _flatten_card_text(card: dict) -> str:
    chunks: list[str] = []
    header = card.get("header")
    if isinstance(header, dict):
        title = header.get("title")
        if isinstance(title, dict) and title.get("content"):
            chunks.append(str(title["content"]))
    for element in card.get("elements", []):
        if not isinstance(element, dict):
            continue
        if element.get("content"):
            chunks.append(str(element["content"]))
        for child in element.get("elements", []):
            if isinstance(child, dict) and child.get("content"):
                chunks.append(str(child["content"]))
    return "\n".join(chunks)


def latest_query_reply_text(records: dict[str, list[dict[str, object]]]) -> str:
    if records["patched_cards"]:
        return _flatten_card_text(records["patched_cards"][-1]["card"])  # type: ignore[arg-type]
    if records["cards"]:
        return _flatten_card_text(records["cards"][-1]["card"])  # type: ignore[arg-type]
    if records["texts"]:
        return str(records["texts"][-1]["text"])
    return ""


def test_mapped_sender_can_query_today_tasks_and_logs_result(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")
    create_task(client, headers, title="今天要跟进的筹款任务", owner_id=user["id"])

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_today_tasks",
        text="我今天有哪些任务",
    )

    assert len(records["cards"]) == 1
    assert "正在处理" in _flatten_card_text(records["cards"][0]["card"])  # type: ignore[arg-type]
    assert len(records["patched_cards"]) == 1
    final_text = latest_query_reply_text(records)
    assert "我今天的任务" in final_text
    assert "今天要跟进的筹款任务" in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_today_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_today"
    assert str(log_row["status"]) == "resolved"
    assert str(log_row["resolved_user_id"]) == user["id"]


def test_unfinished_task_question_is_treated_as_task_list_not_title_keyword_search(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")
    create_task(client, headers, title="补飞书查询规则", owner_id=user["id"])

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_unfinished_list",
        text="我有哪些任务未完成",
    )

    final_text = latest_query_reply_text(records)
    assert "我的待办" in final_text
    assert "补飞书查询规则" in final_text
    assert "标题包含" not in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_unfinished_list",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_open"


def test_sender_profile_can_auto_bind_unique_account_before_querying(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    create_task(client, headers, title="本周待处理项目复盘", owner_id=user["id"])

    monkeypatch.setattr(
        cloud_main,
        "_feishu_fetch_contact_user_profile",
        lambda **_: cloud_main.FeishuSenderProfile(
            open_id="ou_admin_auto",
            feishu_user_id="user_admin_auto",
            name=user["fullName"],
            email=user["email"],
            mobile="13800138000",
        ),
    )
    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin_auto",
        sender_feishu_user_id="user_admin_auto",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_auto_bind",
        text="我本周有哪些任务",
    )

    final_text = latest_query_reply_text(records)
    assert "我本周的任务" in final_text

    target_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_delivery_targets WHERE organization_id = ? AND user_id = ?",
        (organization_id, user["id"]),
    )
    assert target_row is not None
    assert str(target_row["receive_id"]) == "ou_admin_auto"
    assert str(target_row["match_status"]) == "matched"


def test_unresolved_sender_gets_binding_guide_and_scope_denied_is_explicit(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_contact_user_profile", lambda **_: None)
    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_unknown",
        sender_feishu_user_id=None,
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_unresolved",
        text="我今天有哪些任务",
    )
    assert "识别" in latest_query_reply_text(records)
    unresolved_log = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_unresolved",),
    )
    assert str(unresolved_log["status"]) == "unresolved"

    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_scope_denied",
        text="林佳维有哪些任务",
    )
    assert "仅支持查询你本人" in latest_query_reply_text(records)
    denied_log = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_scope_denied",),
    )
    assert str(denied_log["status"]) == "denied"
    assert str(denied_log["query_type"]) == "scope_denied"


def test_weekly_review_and_event_line_queries_return_personal_summaries(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")

    review_response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": cloud_main._week_label_for_today(),  # noqa: SLF001
            "taskEntries": [],
            "workProgress": "完成飞书查询链路接线",
            "workBlocker": "等待补全权限配置",
            "nextWeekFocus": "验证私聊机器人查询稳定性",
            "supportNeeded": "需要补开发者平台权限",
        },
        headers=headers,
    )
    assert review_response.status_code == 200, review_response.text

    event_line_response = client.post(
        "/api/v1/event-lines",
        json={
            "name": "飞书桥联调",
            "kind": "coordination_line",
            "status": "active",
            "participantIds": [user["id"]],
        },
        headers=headers,
    )
    assert event_line_response.status_code == 200, event_line_response.text
    event_line_id = event_line_response.json()["id"]
    create_task(
        client,
        headers,
        title="联调飞书查询入口",
        owner_id=user["id"],
        event_line_id=event_line_id,
    )

    records = capture_query_delivery(monkeypatch)
    service = make_inbound_service(client)

    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_review_status",
        text="我这周复盘提交了吗",
    )
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_eventline_list",
        text="我参与的事件线有哪些",
    )

    combined = "\n".join(
        _flatten_card_text(item["card"])  # type: ignore[arg-type]
        for item in records["patched_cards"]
    )
    assert "已提交周复盘" in combined
    assert "飞书桥联调" in combined


def test_model_parse_can_filter_tasks_by_collaboration_partner(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    ensure_member(client, user_id="user_qinghua", organization_id=admin_user["organizationId"], full_name="庆华", email="qinghua@yiyu-system.com")
    ensure_member(client, user_id="user_jianing", organization_id=admin_user["organizationId"], full_name="佳宁", email="jianing@yiyu-system.com")
    _, qinghua_user = auth_headers(client, "qinghua@yiyu-system.com", "Simulate123!")
    _, jianing_user = auth_headers(client, "jianing@yiyu-system.com", "Simulate123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, admin_user["id"], "ou_admin")

    create_task(
        client,
        headers,
        title="测试卡片更新慢通知",
        owner_id=admin_user["id"],
        collaborator_ids=[admin_user["id"], qinghua_user["id"]],
    )
    create_task(
        client,
        headers,
        title="另一个协作任务",
        owner_id=admin_user["id"],
        collaborator_ids=[admin_user["id"], jianing_user["id"]],
    )

    monkeypatch.setattr(
        cloud_main,
        "_load_feishu_query_model_config",
        lambda state, org_id: cloud_main.FeishuQueryModelConfig(
            api_key="demo-key",
            model="demo-model",
            base_url="https://models.example.test/v1",
            provider="test",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_sync_qwen_chat",
        lambda api_key, payload, timeout, *, base_url: json.dumps(
            {
                "intent": "tasks_list",
                "status_filter": "open",
                "time_filter": "none",
                "participant_name": qinghua_user["fullName"],
                "owner_name": "",
                "keyword": "",
            },
            ensure_ascii=False,
        ),
    )

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_partner_tasks",
        text=f"我和{qinghua_user['fullName']}协作的任务有哪些",
    )

    final_text = latest_query_reply_text(records)
    assert "测试卡片更新慢通知" in final_text
    assert "另一个协作任务" not in final_text
    assert qinghua_user["fullName"] in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_partner_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_list"
    assert str(log_row["status"]) == "resolved"


def test_model_parse_can_distinguish_overdue_unfinished_tasks(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, admin_user["id"], "ou_admin")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    create_task(
        client,
        headers,
        title="已经过期但还没完成",
        owner_id=admin_user["id"],
        start_date=yesterday,
        due_date=f"{yesterday}T18:00",
    )
    create_task(
        client,
        headers,
        title="今天还没过期的任务",
        owner_id=admin_user["id"],
        start_date=today,
        due_date=f"{today}T21:00",
    )

    monkeypatch.setattr(
        cloud_main,
        "_load_feishu_query_model_config",
        lambda state, org_id: cloud_main.FeishuQueryModelConfig(
            api_key="demo-key",
            model="demo-model",
            base_url="https://models.example.test/v1",
            provider="test",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_sync_qwen_chat",
        lambda api_key, payload, timeout, *, base_url: json.dumps(
            {
                "intent": "tasks_list",
                "status_filter": "overdue",
                "time_filter": "none",
                "participant_name": "",
                "owner_name": "",
                "keyword": "",
            },
            ensure_ascii=False,
        ),
    )

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_overdue_open_tasks",
        text="我有哪些任务过期了但还没完成",
    )

    final_text = latest_query_reply_text(records)
    assert "我的逾期任务" in final_text
    assert "已经过期但还没完成" in final_text
    assert "今天还没过期的任务" not in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_overdue_open_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_list"
