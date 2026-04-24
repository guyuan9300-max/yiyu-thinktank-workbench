from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.ai import AiInvocationError
from app.services.knowledge_base import CitationMatch, RetrievalBundle
from app.services.topic_capture import TopicSearchHit


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def make_app_only(tmp_path: Path):
    return create_app(tmp_path / "data")


def wait_for_topic_insight_status(client: TestClient, candidate_id: str, *, expected: str = "ready", timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = client.app.state.app_state.db.fetchone(
            "SELECT insight_status FROM topic_candidates WHERE id = ?",
            (candidate_id,),
        )
        if row is not None and row["insight_status"] == expected:
            return row
        time.sleep(0.1)
    return client.app.state.app_state.db.fetchone(
        "SELECT insight_status FROM topic_candidates WHERE id = ?",
        (candidate_id,),
    )


def create_test_client_record(client: TestClient, name: str = "知识底座测试客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于知识底座测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def seed_session_user(
    client: TestClient,
    *,
    user_id: str = "user_emp",
    email: str = "employee@example.com",
    full_name: str = "普通员工",
    primary_role: str = "employee",
) -> dict:
    payload = {
        "id": user_id,
        "organizationId": "org_1",
        "email": email,
        "fullName": full_name,
        "primaryRole": primary_role,
        "accountStatus": "approved",
    }
    client.app.state.app_state.db.set_setting("cloud_session_user", json.dumps(payload, ensure_ascii=False))
    return payload


def seed_cloud_token(client: TestClient, token: str = "token_demo") -> None:
    client.app.state.app_state.db.set_setting("cloud_access_token", token)


def test_growth_overview_smoke_does_not_fail_when_no_badges_have_synced(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        response = client.get("/api/v1/growth/overview")

        assert response.status_code == 200
        payload = response.json()
        assert "abilities" in payload
        assert "updatedAt" in payload
    finally:
        client.__exit__(None, None, None)


def insert_local_event_line_notification(
    client: TestClient,
    *,
    notification_id: str,
    user: dict,
    event_line_id: str = "line_demo",
    title: str = "事件线系统通知",
    other_user_ids: list[tuple[str, str, str]] | None = None,
) -> None:
    timestamp = app_main.now_iso()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO event_line_notifications(
            id, organization_id, event_line_id, event_line_name, operation_label,
            actor_id, actor_name, title, summary, metadata_json,
            main_owner_names_json, participant_names_json, operated_at, created_at, updated_at,
            sync_status, cloud_id, cloud_payload_json, last_synced_at, last_cloud_version,
            pending_sync_action, last_sync_error
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            notification_id,
            user["organizationId"],
            event_line_id,
            "测试事件线",
            "状态更新",
            user["id"],
            user["fullName"],
            title,
            "验证本地系统通知已阅逻辑。",
            "{}",
            json.dumps([user["fullName"]], ensure_ascii=False),
            json.dumps([user["fullName"]], ensure_ascii=False),
            timestamp,
            timestamp,
            timestamp,
            "synced",
            "",
            "",
            timestamp,
            "",
            "",
            "",
        ),
    )
    receipt_rows = [
        (
            notification_id,
            user["organizationId"],
            user["id"],
            user["fullName"],
            user["email"],
            None,
            timestamp,
            timestamp,
        )
    ]
    for other_user_id, other_name, other_email in other_user_ids or []:
        receipt_rows.append(
            (
                notification_id,
                user["organizationId"],
                other_user_id,
                other_name,
                other_email,
                None,
                timestamp,
                timestamp,
            )
        )
    db.conn.executemany(
        """
        INSERT INTO event_line_notification_receipts(
            notification_id, organization_id, user_id, full_name, email, read_at, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        receipt_rows,
    )


def stub_cloud_auth_me(monkeypatch, user_payload: dict, *, base_url: str = "http://127.0.0.1:47830"):
    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == f"{base_url.rstrip('/')}/api/v1/auth/me":
            return httpx.Response(200, json=user_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)


def stub_cloud_strategic_services(
    monkeypatch,
    *,
    leader_user_id: str | None,
    base_url: str = "http://127.0.0.1:47830",
    tasks_payload: dict | None = None,
    review_dashboard_payload: dict | None = None,
):
    org_model_payload = {
        "organization": {
            "organizationId": "org_1",
            "name": "益语智库",
            "annualGoal": "",
            "annualStrategyYear": "2026",
            "annualStrategy": "",
            "quarterPlans": [],
            "quarterlyFocus": [],
            "leaderUserId": leader_user_id,
            "managementUserIds": [],
            "updatedAt": "2026-03-22T00:00:00",
        },
        "departments": [],
        "roles": [],
        "bindings": [],
        "reportingLines": [],
        "taskControlRules": [],
        "roleProcessTemplates": [],
        "focusItems": [],
        "departmentPlans": [],
        "updatedAt": "2026-03-22T00:00:00",
    }
    tasks_payload = tasks_payload or {"tasks": [], "lists": [], "tags": []}
    review_dashboard_payload = review_dashboard_payload or {}

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = f"{base_url.rstrip('/')}"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/settings/org-model/profile":
            return httpx.Response(200, json=org_model_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(200, json=tasks_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/employees/directory":
            return httpx.Response(200, json=[])
        if method.upper() == "GET" and url.startswith(f"{normalized}/api/v1/reviews/dashboard"):
            return httpx.Response(200, json=review_dashboard_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)


def wait_for_knowledge_ready(client: TestClient, client_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["pendingJobs"] == 0 and payload["runningJobs"] == 0 and payload["lastJobStatus"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def test_health_and_structural_defaults(tmp_path: Path):
    client = make_client(tmp_path)

    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["appName"] == "益语智库自用平台"
    assert payload["buildVersion"]
    assert payload["startedAt"]
    assert "knowledge.vectorize-answer" in payload["featureFlags"]
    assert "knowledge.reclass-events" in payload["featureFlags"]
    assert "chat.general-answer" in payload["featureFlags"]
    assert payload["stats"]["clients"] == 0

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200
    task_payload = task_board.json()
    assert len(task_payload["lists"]) >= 4
    assert isinstance(task_payload["tasks"], list)
    assert task_payload["tasks"] == []


def test_cross_site_browser_requests_are_rejected(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="跨站保护测试客户")

    rejected_read = client.get(
        "/api/v1/clients",
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert rejected_read.status_code == 403, rejected_read.text

    rejected_delete = client.delete(
        f"/api/v1/clients/{client_id}",
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert rejected_delete.status_code == 403, rejected_delete.text

    allowed_read = client.get(
        "/api/v1/clients",
        headers={"origin": "http://127.0.0.1:4173", "referer": "http://127.0.0.1:4173/app"},
    )
    assert allowed_read.status_code == 200, allowed_read.text


def test_local_browser_requests_allow_dynamic_renderer_ports(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.get(
        "/api/v1/settings/tasks",
        headers={"origin": "http://127.0.0.1:4174", "referer": "http://127.0.0.1:4174/"},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:4174"


def test_local_browser_preflight_allows_dynamic_renderer_ports(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.options(
        "/api/v1/system/health",
        headers={
            "origin": "http://127.0.0.1:4174",
            "access-control-request-method": "GET",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:4174"


def test_template_fill_start_reuses_existing_active_run_for_same_template(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="模板填写排队测试客户")
    timestamp = "2026-03-24T09:00:00"
    template_path = "/tmp/demo-template.docx"
    existing_run_id = "tmplfill_existing"
    client.app.state.app_state.db.execute(
        """
        INSERT INTO client_template_fill_runs(
            id, client_id, template_name, template_path, status, phase, progress, stage_label, elapsed_ms,
            field_count, processed_count, filled_count, missing_count, current_field_label, evidence_titles_json, fields_json, output_path, error_message,
            created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'running', 'retrieving', 18, '正在检索资料', 1200, 65, 12, 5, 7, '机构全称', '[]', '[]', NULL, NULL, ?, ?)
        """,
        (existing_run_id, client_id, "demo-template.docx", template_path, timestamp, timestamp),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/documents/fill-template/start",
        json={"templatePath": template_path},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == existing_run_id
    assert payload["status"] == "running"


def test_event_line_clarification_fields_persist_locally(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="事件线澄清测试客户")

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "项目推进确认线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "stage": "等待客户确认",
            "currentBlocker": "还在等客户最终确认方向。",
            "nextStep": "本周内补齐会后动作并同步下一轮排期。",
            "recentDecision": "先补齐资料，再推进下一轮方案沟通。",
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["stage"] == "等待客户确认"
    assert payload["currentBlocker"] == "还在等客户最终确认方向。"
    assert payload["nextStep"] == "本周内补齐会后动作并同步下一轮排期。"
    assert payload["recentDecision"] == "先补齐资料，再推进下一轮方案沟通。"

    detail = client.get(f"/api/v1/event-lines/{event_line_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["eventLine"]["currentBlocker"] == "还在等客户最终确认方向。"
    assert detail.json()["eventLine"]["recentDecision"] == "先补齐资料，再推进下一轮方案沟通。"

    row = client.app.state.app_state.db.fetchone(
        "SELECT current_blocker, recent_decision FROM event_lines WHERE id = ?",
        (event_line_id,),
    )
    assert row is not None
    assert row["current_blocker"] == "还在等客户最终确认方向。"
    assert row["recent_decision"] == "先补齐资料，再推进下一轮方案沟通。"


def test_event_line_clarification_draft_can_be_generated_from_conversation(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="事件线聊天整理客户")

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "客户确认推进线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    drafted = client.post(
        f"/api/v1/event-lines/{event_line_id}/clarification-draft",
        json={
            "conversationText": (
                "今天和客户沟通后，先统一了这一轮方案口径。"
                "现在还在等客户确认最终版本，资料也没补齐。"
                "下一步是明天下午把会后动作整理好并同步给客户。"
                "刚刚决定先补资料，再推进下一轮方案沟通。"
            ),
        },
    )
    assert drafted.status_code == 200, drafted.text
    payload = drafted.json()
    assert payload["summary"]
    assert payload["stage"] in {"等待确认", "资料补齐中", "执行推进中"}
    assert "沟通" in payload["intent"] or "推进" in payload["intent"]
    assert "确认" in payload["currentBlocker"] or "资料" in payload["currentBlocker"]
    assert "同步给客户" in payload["nextStep"] or "下一步" in payload["nextStep"]
    assert "先补资料" in payload["recentDecision"] or "推进下一轮方案沟通" in payload["recentDecision"]
    assert payload["confidence"] in {"low", "medium", "high"}


def test_task_action_os_fields_persist_locally(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="任务对象层收口测试客户")

    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "业务扩展推进线",
            "kind": "project_line",
            "primaryClientId": client_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧还没确认合作边界。",
            "nextStep": "整理确认项并约下一轮沟通。",
            "recentDecision": "先收口范围，再决定报价方式。",
            "evidenceCount": 2,
        },
    )
    assert event_line.status_code == 200, event_line.text
    event_line_id = event_line.json()["id"]

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进黄河合作确认",
            "description": "继续围绕合作范围做确认和整理。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧还没确认合作边界。",
            "nextAction": "把确认项发给对方并锁时间。",
            "recentDecision": "先收口范围，再决定报价方式。",
            "evidenceCount": 3,
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["businessCategory"] == "业务扩展"
    assert payload["currentBlocker"] == "客户侧还没确认合作边界。"
    assert payload["nextAction"] == "把确认项发给对方并锁时间。"
    assert payload["recentDecision"] == "先收口范围，再决定报价方式。"
    assert payload["evidenceCount"] == 3

    updated = client.patch(
        f"/api/v1/tasks/{payload['id']}",
        json={
            "businessCategory": "正式交付",
            "currentBlocker": "客户已确认合作边界，转入交付准备。",
            "nextAction": "输出首版交付清单。",
            "recentDecision": "先交付一版结构化清单。",
            "evidenceCount": 5,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["businessCategory"] == "正式交付"
    assert updated_payload["currentBlocker"] == "客户已确认合作边界，转入交付准备。"
    assert updated_payload["nextAction"] == "输出首版交付清单。"
    assert updated_payload["recentDecision"] == "先交付一版结构化清单。"
    assert updated_payload["evidenceCount"] == 5

    row = client.app.state.app_state.db.fetchone(
        "SELECT business_category, current_blocker, next_action, recent_decision, evidence_count FROM tasks WHERE id = ?",
        (payload["id"],),
    )
    assert row is not None
    assert row["business_category"] == "正式交付"
    assert row["current_blocker"] == "客户已确认合作边界，转入交付准备。"
    assert row["next_action"] == "输出首版交付清单。"
    assert row["recent_decision"] == "先交付一版结构化清单。"
    assert row["evidence_count"] == 5


def test_personal_task_scope_mode_persists_locally_and_clears_shared_refs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="个人任务隔离测试客户")
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "不该挂上的共享事件线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert event_line.status_code == 200, event_line.text

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "和朋友见面",
            "description": "个人安排，不进入组织任务线。",
            "priority": "normal",
            "listId": "list-0",
            "scopeMode": "PERSONAL_ONLY",
            "clientId": client_id,
            "eventLineId": event_line.json()["id"],
            "projectModuleId": "module_should_clear",
            "projectFlowId": "flow_should_clear",
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["scopeMode"] == "PERSONAL_ONLY"
    assert payload["clientId"] in ("", None)
    assert payload["eventLineId"] in ("", None)
    assert payload["projectModuleId"] in ("", None)
    assert payload["projectFlowId"] in ("", None)

    row = client.app.state.app_state.db.fetchone(
        "SELECT scope_mode, client_id, event_line_id, project_module_id, project_flow_id FROM tasks WHERE id = ?",
        (payload["id"],),
    )
    assert row["scope_mode"] == "PERSONAL_ONLY"
    assert row["client_id"] is None
    assert row["event_line_id"] is None
    assert row["project_module_id"] is None
    assert row["project_flow_id"] is None


def test_strategic_cockpit_defaults_to_read_only_without_ceo(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页只读客户")

    response = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["permission"]["canEdit"] is False
    assert "CEO" in payload["permission"]["notice"]
    assert payload["headline"]["coreBreakthrough"]["value"]
    assert payload["readiness"]["status"] in {"ready", "insufficient"}


def test_strategic_cockpit_ceo_confirm_persists_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页 CEO 客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    confirm_response = client.post(
        f"/api/v1/clients/{client_id}/strategic-cockpit/confirm",
        json={
            "weekSummary": "本周已经把业务盘点会变成正式经营入口。",
            "mainContradiction": "业务推进动作已有，但关键判断还没有稳定压成经营语言。",
            "coreBreakthrough": "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。",
            "focusItems": ["确认本周期主问题", "让周会只围绕一条主线", "补齐关键资料"],
        },
    )
    assert confirm_response.status_code == 200, confirm_response.text
    payload = confirm_response.json()
    assert payload["permission"]["canEdit"] is True
    assert payload["headline"]["weekSummary"]["status"] == "confirmed"
    assert payload["headline"]["weekSummary"]["value"] == "本周已经把业务盘点会变成正式经营入口。"
    assert payload["headline"]["mainContradiction"]["status"] == "confirmed"
    assert payload["headline"]["coreBreakthrough"]["value"] == "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。"
    assert payload["headline"]["focusStatus"] == "confirmed"
    assert payload["headline"]["focusItems"][0] == "确认本周期主问题"

    row = client.app.state.app_state.db.fetchone(
        "SELECT week_summary, main_contradiction, core_breakthrough FROM strategic_cockpit_snapshots WHERE client_id = ?",
        (client_id,),
    )
    assert row is not None
    assert row["week_summary"] == "本周已经把业务盘点会变成正式经营入口。"
    assert row["main_contradiction"] == "业务推进动作已有，但关键判断还没有稳定压成经营语言。"
    assert row["core_breakthrough"] == "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。"


def test_strategic_cockpit_confirm_rejects_non_ceo(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页非 CEO 客户")
    seed_session_user(client, user_id="user_member", full_name="普通成员")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id="user_ceo")

    confirm_response = client.post(
        f"/api/v1/clients/{client_id}/strategic-cockpit/confirm",
        json={
            "weekSummary": "不应写入",
            "mainContradiction": "不应写入",
            "coreBreakthrough": "不应写入",
            "focusItems": ["不应写入"],
        },
    )
    assert confirm_response.status_code == 403, confirm_response.text


def test_strategic_cockpit_relationship_task_needs_contextual_description(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="关系推进背景测试客户")

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟敦和林红吃饭",
            "desc": "",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    first_snapshot = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert first_snapshot.status_code == 200, first_snapshot.text
    first_payload = first_snapshot.json()
    assert any("只写了动作名" in item for item in first_payload["readiness"]["gaps"])

    updated_task = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "desc": "敦和基金会的林红负责合作拓展，当前双方正在讨论联合研究，这次见面希望确认合作边界和下次方案节奏。",
        },
    )
    assert updated_task.status_code == 200, updated_task.text

    second_snapshot = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert second_snapshot.status_code == 200, second_snapshot.text
    second_payload = second_snapshot.json()
    assert not any("只写了动作名" in item for item in second_payload["readiness"]["gaps"])


def test_strategic_meeting_pack_writes_into_meeting_object(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会草稿客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert response.status_code == 200, response.text
    payload = response.json()
    meeting = payload["meeting"]
    assert meeting["title"] == "战略周会草稿客户 周盘点会"
    assert "必须澄清的问题" in meeting["notes"]
    assert meeting["agendaItems"]

    source_row = client.app.state.app_state.db.fetchone(
        "SELECT title, content_text FROM meeting_sources WHERE meeting_id = ?",
        (meeting["id"],),
    )
    assert source_row is not None
    assert source_row["title"] == "战略陪伴周会清单草案"
    assert "建议议程" in source_row["content_text"]


def test_strategic_meeting_pack_apply_updates_cockpit_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会回填客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    meeting_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert meeting_response.status_code == 200, meeting_response.text
    meeting_id = meeting_response.json()["meeting"]["id"]

    ingest_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest",
        json={
            "transcriptText": "本周我们决定先把客户盘点会固定下来，并把关键阻塞收敛成一条主线。",
            "notes": "决定先把客户盘点会固定下来。庆华负责下周推进。当前还缺关键资料待补。",
        },
    )
    assert ingest_response.status_code == 200, ingest_response.text

    extract_response = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/extract")
    assert extract_response.status_code == 200, extract_response.text

    apply_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply")
    assert apply_response.status_code == 200, apply_response.text
    payload = apply_response.json()
    assert payload["headline"]["weekSummary"]["status"] == "confirmed"
    assert payload["headline"]["mainContradiction"]["status"] == "confirmed"
    assert payload["headline"]["coreBreakthrough"]["status"] == "confirmed"
    assert payload["headline"]["focusStatus"] == "confirmed"

    row = client.app.state.app_state.db.fetchone(
        "SELECT week_summary, main_contradiction, core_breakthrough FROM strategic_cockpit_snapshots WHERE client_id = ?",
        (client_id,),
    )
    assert row is not None
    assert row["week_summary"]
    assert row["main_contradiction"]
    assert row["core_breakthrough"]


def test_strategic_meeting_pack_apply_updates_event_line_memory(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会事件线回写客户")
    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "敦和合作推进线",
            "kind": "project_line",
            "status": "active",
            "summary": "围绕敦和合作推进持续补齐信息并确认节奏。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    meeting_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert meeting_response.status_code == 200, meeting_response.text
    meeting_id = meeting_response.json()["meeting"]["id"]

    client.app.state.app_state.db.execute(
        "INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES(?, ?, ?, ?)",
        (
            app_main.new_id("decision"),
            meeting_id,
            "先确认敦和合作边界，再推进下次正式方案沟通。",
            "2026-03-22T10:00:00",
        ),
    )

    apply_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply")
    assert apply_response.status_code == 200, apply_response.text

    memory_response = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert memory_response.status_code == 200, memory_response.text
    memory_payload = memory_response.json()
    assert "先确认敦和合作边界" in memory_payload["eventLineMemorySnapshot"]["recentDecision"]


def test_feishu_meeting_launch_and_minutes_writeback_flow(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="飞书纪要测试客户")
    sent_messages: list[dict] = []

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", lambda **kwargs: ("tenant_token", {"code": 0}))

    def fake_send_text_message(**kwargs):
        sent_messages.append(kwargs)
        return {"code": 0}

    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    launch_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/launch-feishu",
        json={
            "title": "日慈基金会项目推进会",
            "scheduledAt": "2026-03-18T14:00",
            "sourceTaskId": "task_demo_1",
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch_payload = launch_response.json()
    assert launch_payload["deliveryStatus"] == "sent"
    assert launch_payload["deliveryMode"] == "configured_receiver"
    assert "纪要回写" in launch_payload["commandHint"]
    meeting_id = launch_payload["meeting"]["id"]
    assert sent_messages and meeting_id in sent_messages[0]["text"]

    event_response = client.post(
        "/api/v1/channels/feishu/events",
        json={
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_type": "user"},
                "message": {
                    "chat_id": "chat_ops_room",
                    "message_type": "text",
                    "content": json.dumps(
                        {
                            "text": (
                                f"纪要回写 {meeting_id}\n"
                                "本次会议决定先推进资料补齐。"
                                "庆华负责跟进客户反馈。"
                                "当前存在资源风险。"
                            )
                        },
                        ensure_ascii=False,
                    ),
                },
            },
        },
    )
    assert event_response.status_code == 200, event_response.text
    assert event_response.json()["ok"] is True

    meeting_detail = client.get(f"/api/v1/clients/{client_id}/meetings/{meeting_id}")
    assert meeting_detail.status_code == 200, meeting_detail.text
    meeting_payload = meeting_detail.json()
    assert meeting_payload["stage"] == "extracted"
    assert "资料补齐" in meeting_payload["notes"]
    assert len(meeting_payload["actionItems"]) >= 1
    assert len(meeting_payload["decisions"]) >= 1
    assert len(meeting_payload["risks"]) >= 1
    assert len(sent_messages) >= 2


def test_feishu_user_binding_callback_persists_current_user(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu", email="guyuan@klngo.org", full_name="顾源")
    seed_cloud_token(client)
    stub_cloud_auth_me(monkeypatch, session_user)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    start_payload = start_response.json()
    assert "open.feishu.cn" in start_payload["authorizeUrl"]
    assert start_payload["state"]
    assert start_payload["callbackUrl"].endswith("/api/v1/auth/feishu/callback")
    assert start_payload["qrReady"] is False
    assert start_payload["qrBlockedReason"]

    monkeypatch.setattr(app_main, "fetch_app_access_token", lambda **kwargs: ("app_token", {"code": 0}))
    monkeypatch.setattr(
        app_main,
        "exchange_authorization_code",
        lambda **kwargs: {
            "access_token": "user_access_token",
            "open_id": "ou_bound_user",
            "user_id": "feishu_user_1",
            "tenant_key": "tenant_1",
        },
    )
    monkeypatch.setattr(
        app_main,
        "fetch_user_info",
        lambda **kwargs: {
            "open_id": "ou_bound_user",
            "user_id": "feishu_user_1",
            "name": "顾源",
            "email": "guyuan@klngo.org",
            "tenant_key": "tenant_1",
        },
    )

    callback_response = client.get(
        "/api/v1/auth/feishu/callback",
        params={"state": start_payload["state"], "code": "authorization_code_1"},
    )
    assert callback_response.status_code == 200, callback_response.text
    assert "飞书账号绑定成功" in callback_response.text

    binding_response = client.get("/api/v1/settings/feishu-user-binding")
    assert binding_response.status_code == 200, binding_response.text
    binding_payload = binding_response.json()
    assert binding_payload["linked"] is True
    assert binding_payload["openId"] == "ou_bound_user"
    assert binding_payload["email"] == "guyuan@klngo.org"
    assert binding_payload["name"] == "顾源"


def test_feishu_user_binding_start_uses_configured_public_callback(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
            "userBindingCallbackUrl": "https://workbench.yiyu.example.com/api/v1/auth/feishu/callback",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu_callback", email="guyuan@klngo.org", full_name="顾源")
    seed_cloud_token(client)
    stub_cloud_auth_me(monkeypatch, session_user)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    payload = start_response.json()
    assert payload["callbackUrl"] == "https://workbench.yiyu.example.com/api/v1/auth/feishu/callback"
    assert payload["qrReady"] is True
    assert payload["qrBlockedReason"] is None


def test_feishu_user_binding_uses_cloud_relay_for_mobile_scan(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client.app.state.app_state.cloud_api_url = "https://cloud.yiyu.example.com"
    client.app.state.app_state.db.set_setting("cloud_access_token", "token_demo")

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    cloud_user_payload = {
        "id": "user_feishu_cloud",
        "organizationId": "org_1",
        "email": "guyuan@klngo.org",
        "fullName": "顾源",
        "primaryRole": "employee",
        "accountStatus": "approved",
    }
    seen_states: list[str] = []

    def fake_cloud_request(method: str, url: str, **kwargs):
        if url == "https://cloud.yiyu.example.com/api/v1/auth/me":
            return httpx.Response(200, json=cloud_user_payload)
        if url == "https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions" and method.upper() == "POST":
            payload = kwargs.get("json") or {}
            seen_states.append(str(payload.get("state") or ""))
            return httpx.Response(200, json={"message": "ok"})
        if url.startswith("https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions/") and method.upper() == "GET":
            state_token = url.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "state": state_token,
                    "status": "authorized",
                    "expiresAt": "2099-01-01T00:00:00",
                    "authorizedAt": "2099-01-01T00:00:00",
                    "code": "authorization_code_cloud",
                },
            )
        if url.startswith("https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions/") and method.upper() == "DELETE":
            return httpx.Response(200, json={"message": "ok"})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    start_payload = start_response.json()
    assert start_payload["callbackUrl"] == "https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/callback"
    assert start_payload["qrReady"] is True
    assert start_payload["qrBlockedReason"] is None
    assert seen_states == [start_payload["state"]]

    monkeypatch.setattr(app_main, "fetch_app_access_token", lambda **kwargs: ("app_token", {"code": 0}))
    monkeypatch.setattr(
        app_main,
        "exchange_authorization_code",
        lambda **kwargs: {
            "access_token": "user_access_token",
            "open_id": "ou_bound_user_cloud",
            "user_id": "feishu_user_cloud",
            "tenant_key": "tenant_1",
        },
    )
    monkeypatch.setattr(
        app_main,
        "fetch_user_info",
        lambda **kwargs: {
            "open_id": "ou_bound_user_cloud",
            "user_id": "feishu_user_cloud",
            "name": "顾源",
            "email": "guyuan@klngo.org",
            "tenant_key": "tenant_1",
        },
    )

    binding_response = client.get("/api/v1/settings/feishu-user-binding")
    assert binding_response.status_code == 200, binding_response.text
    binding_payload = binding_response.json()
    assert binding_payload["linked"] is True
    assert binding_payload["openId"] == "ou_bound_user_cloud"
    assert binding_payload["email"] == "guyuan@klngo.org"


def test_auth_me_keeps_cached_session_when_cloud_is_temporarily_unavailable(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    session_user = seed_session_user(
        client,
        user_id="user_cached",
        email="guyuan@klngo.org",
        full_name="顾源源",
        primary_role="admin",
    )
    seed_cloud_token(client, "token_cached")
    client.app.state.app_state.db.set_setting("cloud_refresh_token", "refresh_cached")

    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == "http://127.0.0.1:47830/api/v1/auth/me":
            raise httpx.ConnectError("cloud unavailable", request=httpx.Request(method, url))
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["id"] == session_user["id"]
    assert payload["user"]["email"] == session_user["email"]
    assert "已保留当前设备上的登录状态" in (payload["message"] or "")


def test_feishu_meeting_launch_prefers_bound_user_over_global_receiver(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="飞书绑定优先级测试客户")
    sent_messages: list[dict] = []

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu_bound", email="guyuan@klngo.org", full_name="顾源")
    client.app.state.app_state.db.set_setting(
        f"settings.feishu_user_binding:{session_user['id']}",
        json.dumps(
            {
                "linked": True,
                "readyForAuthorization": True,
                "appId": "cli_test_app",
                "userId": session_user["id"],
                "openId": "ou_bound_priority",
                "name": "顾源",
                "email": "guyuan@klngo.org",
                "tenantKey": "tenant_1",
                "boundAt": "2026-03-18T10:00:00",
                "lastVerifiedAt": "2026-03-18T10:05:00",
            },
            ensure_ascii=False,
        ),
    )

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", lambda **kwargs: ("tenant_token", {"code": 0}))

    def fake_send_text_message(**kwargs):
        sent_messages.append(kwargs)
        return {"code": 0}

    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    launch_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/launch-feishu",
        json={
            "title": "顾源飞书绑定会议",
            "scheduledAt": "2026-03-18T16:00",
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch_payload = launch_response.json()
    assert launch_payload["deliveryStatus"] == "sent"
    assert launch_payload["deliveryMode"] == "bound_user"
    assert launch_payload["deliveryTarget"] == "顾源"
    assert sent_messages[0]["receive_id_type"] == "open_id"
    assert sent_messages[0]["receive_id"] == "ou_bound_priority"


def test_startup_requeues_stale_knowledge_jobs(tmp_path: Path):
    app = make_app_only(tmp_path)
    db = app.state.app_state.db
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_stale', '僵尸任务客户', '僵尸任务客户', '公益', '内部陪伴', '测试僵尸任务恢复', '推进中', '2026-03-13T00:00:00', '2026-03-13T00:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, job_type, status, payload_json, total_items, processed_items,
            last_error, created_at, started_at, finished_at, updated_at
        )
        VALUES('kjob_stale', 'client_stale', 'rebuild_client_knowledge', 'running', '{}', 1, 0, NULL, '2026-03-13T00:00:00', '2026-03-13T00:00:01', NULL, '2026-03-13T00:00:01')
        """
    )
    client = TestClient(app)
    client.__enter__()
    try:
        row = db.fetchone("SELECT status, last_error FROM knowledge_jobs WHERE id = 'kjob_stale'")
        assert row is not None
        assert row["status"] in {"queued", "running"}
        assert row["last_error"] == "worker_restart_requeued"
    finally:
        client.__exit__(None, None, None)


def test_settings_accept_qwen_provider(tmp_path: Path):
    client = make_client(tmp_path)

    updated = client.post(
        "/api/v1/settings",
        json={
            "aiProvider": "qwen",
            "aiModel": "qwen3.5-plus",
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["settings"]["aiProvider"] == "qwen"
    assert payload["settings"]["aiModel"] == "qwen3.5-plus"


def test_feishu_bot_settings_can_be_saved_without_secret(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    initial = client.get("/api/v1/settings/feishu-bot")
    assert initial.status_code == 200
    assert initial.json()["hasAppSecret"] is False

    saved = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "receiveIdType": "email",
            "receiverId": "owner@example.com",
            "botName": "罗茜茜",
        },
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["appId"] == "cli_test"
    assert payload["receiveIdType"] == "email"
    assert payload["receiverId"] == "owner@example.com"
    assert payload["botName"] == "罗茜茜"
    assert payload["hasAppSecret"] is False
    assert payload["ready"] is False


def test_feishu_bot_connect_and_send_test_message(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    sent: dict = {}

    def fake_fetch_tenant_access_token(*, app_id: str, app_secret: str, transport=None):
        assert app_id == "cli_test"
        assert app_secret == "secret_test"
        return "tenant_token_test", {"tenant_access_token": "tenant_token_test"}

    def fake_send_text_message(*, tenant_access_token: str, receive_id_type: str, receive_id: str, text: str, transport=None):
        sent.update(
            {
                "tenant_access_token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "text": text,
            }
        )
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", fake_fetch_tenant_access_token)
    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    connected = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "receiveIdType": "email",
            "receiverId": "owner@example.com",
            "botName": "罗茜茜",
            "appSecret": "secret_test",
            "sendTestMessage": True,
            "testMessage": "罗茜茜测试消息",
        },
    )
    assert connected.status_code == 200
    payload = connected.json()
    assert payload["hasAppSecret"] is True
    assert payload["ready"] is True
    assert payload["lastConnectionStatus"] == "success"
    assert payload["lastTestMessageAt"]
    assert sent == {
        "tenant_access_token": "tenant_token_test",
        "receive_id_type": "email",
        "receive_id": "owner@example.com",
        "text": "罗茜茜测试消息",
    }


def test_system_admin_settings_accept_and_clear_brand_logo(tmp_path: Path):
    client = make_client(tmp_path)
    png_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )

    saved = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": png_data_url},
    )
    assert saved.status_code == 200
    assert saved.json()["brandLogoDataUrl"] == png_data_url

    fetched = client.get("/api/v1/settings/system-admin")
    assert fetched.status_code == 200
    assert fetched.json()["brandLogoDataUrl"] == png_data_url

    cleared = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["brandLogoDataUrl"] is None


def test_system_admin_settings_reject_non_png_brand_logo(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": "data:image/jpeg;base64,abcd"},
    )
    assert response.status_code == 400
    assert "只支持 PNG" in response.text


def test_feishu_events_url_verification_returns_challenge(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/channels/feishu/events",
        json={"type": "url_verification", "challenge": "challenge_token_demo"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge_token_demo"}


def test_feishu_events_reply_to_text_message(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "botName": "罗茜茜",
            "appSecret": "secret_test",
        },
    )

    sent: dict = {}

    def fake_fetch_tenant_access_token(*, app_id: str, app_secret: str, transport=None):
        assert app_id == "cli_test"
        assert app_secret == "secret_test"
        return "tenant_token_test", {"tenant_access_token": "tenant_token_test"}

    def fake_send_text_message(*, tenant_access_token: str, receive_id_type: str, receive_id: str, text: str, transport=None):
        sent.update(
            {
                "tenant_access_token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "text": text,
            }
        )
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", fake_fetch_tenant_access_token)
    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    response = client.post(
        "/api/v1/channels/feishu/events",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_type": "user"},
                "message": {
                    "chat_id": "oc_chat_demo",
                    "message_type": "text",
                    "content": "{\"text\":\"你是谁？\"}",
                },
            },
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent == {
        "tenant_access_token": "tenant_token_test",
        "receive_id_type": "chat_id",
        "receive_id": "oc_chat_demo",
        "text": "我是罗茜茜。飞书入站链路刚接通，现在先支持固定回复；客户上下文问答还没接上。",
    }


def test_chat_start_returns_loading_then_poll_completes(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "问答异步测试客户")
    state = client.app.state.app_state

    def fake_bundle(client_id_arg: str, prompt: str) -> RetrievalBundle:
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[],
            coverage=0.0,
            retrieval_summary={
                "masterHitCount": 0,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 0,
                "drillthroughUsed": False,
                "matchedTerms": [],
            },
            context_text="",
            matched_terms=[],
            failure_reason="没有命中当前资料",
        )

    def fake_general(prompt: str, note: str = "", *, subject_name: str = ""):
        return app_main.AiStructuredResponse(
            content=f"当前资料暂无相关内容，但基于通用知识可以先给出一版关于{subject_name or '当前客户'}的概览回答。",
            judgment=f"这是关于{subject_name or '当前客户'}的通用知识回答，不是客户资料结论。",
            analysis="这是一家面向公益服务的组织，通常围绕教育、救助、社区支持等方向开展工作。",
            actions="下一步建议：补充机构介绍、项目简介与对外材料。",
            timeline="补充资料后可再次生成更完整回答。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_bundle(client_id_arg, prompt))
    monkeypatch.setattr(state.ai, "generate_general_fallback", fake_general)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "什么是公益组织？请简要解释。"},
    )
    assert started.status_code == 200
    payload = started.json()
    assert payload["assistantMessage"]["status"] == "loading"
    message_id = payload["assistantMessage"]["id"]

    deadline = time.time() + 20.0
    final_payload = None
    while time.time() < deadline:
        polled = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{message_id}")
        assert polled.status_code == 200
        final_payload = polled.json()
        if final_payload["status"] == "success":
            break
        time.sleep(0.1)

    assert final_payload is not None
    assert final_payload["status"] == "success"
    assert final_payload["llmInvoked"] is True
    assert final_payload["answerMode"] == "general_answer"
    assert "问答异步测试客户" in final_payload["content"]


def test_chat_thread_detail_returns_only_selected_thread_messages(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "线程隔离测试客户")

    first_prompt = "线程一：机构定位怎么理解？"
    second_prompt = "线程二：团队状态怎么看？"

    first_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": first_prompt},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": second_prompt},
    )
    assert second_response.status_code == 200

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    first_thread = next(thread for thread in workspace_payload["threads"] if thread["title"] == first_prompt[:16])
    second_thread = next(thread for thread in workspace_payload["threads"] if thread["title"] == second_prompt[:16])
    assert first_thread["id"] != second_thread["id"]

    first_thread_detail = client.get(f"/api/v1/clients/{client_id}/workspace/chat/threads/{first_thread['id']}")
    assert first_thread_detail.status_code == 200
    first_payload = first_thread_detail.json()

    assert first_payload["thread"]["id"] == first_thread["id"]
    assert {message["threadId"] for message in first_payload["messages"]} == {first_thread["id"]}
    assert [message["content"] for message in first_payload["messages"] if message["role"] == "user"] == [first_prompt]
    assert second_prompt not in [message["content"] for message in first_payload["messages"] if message["role"] == "user"]

    second_thread_detail = client.get(f"/api/v1/clients/{client_id}/workspace/chat/threads/{second_thread['id']}")
    assert second_thread_detail.status_code == 200
    second_payload = second_thread_detail.json()
    assert [message["content"] for message in second_payload["messages"] if message["role"] == "user"] == [second_prompt]


def test_demo_data_can_be_loaded_on_demand(tmp_path: Path):
    client = make_client(tmp_path)

    before = client.get("/api/v1/settings")
    assert before.status_code == 200
    assert before.json()["settings"]["demoDataLoaded"] is False

    loaded = client.post("/api/v1/settings/demo-data/load")
    assert loaded.status_code == 200
    assert loaded.json()["loaded"] is True
    assert loaded.json()["clients"] == 2

    clients = client.get("/api/v1/clients")
    assert clients.status_code == 200
    assert {item["name"] for item in clients.json()} == {"为爱黔行", "星辰科技"}

    cleared = client.post("/api/v1/settings/demo-data/clear")
    assert cleared.status_code == 200
    assert cleared.json()["loaded"] is False
    assert client.get("/api/v1/clients").json() == []


def test_client_meeting_publish_writes_task(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/clients",
        json={
            "name": "测试客户",
            "alias": "测试",
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于 API 烟雾测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    client_id = created.json()["id"]

    meeting = client.post(f"/api/v1/clients/{client_id}/meetings", json={"title": "本周推进会"})
    assert meeting.status_code == 200
    meeting_id = meeting.json()["meeting"]["id"]

    ingest = client.post(
        f"/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest",
        json={"transcriptText": "决定本周由庆华负责补齐方案，跟进捐赠人反馈。", "notes": "待确认时间点。"},
    )
    assert ingest.status_code == 200

    extract = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/extract")
    assert extract.status_code == 200
    assert len(extract.json()["meeting"]["actionItems"]) >= 1

    resolve = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/resolve")
    assert resolve.status_code == 200

    publish = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/publish")
    assert publish.status_code == 200

    tasks = client.get("/api/v1/tasks")
    task_items = tasks.json()["tasks"]
    assert any(task["sourceId"] == meeting_id for task in task_items)
    meeting_task = next(task for task in task_items if task["sourceId"] == meeting_id)
    assert meeting_task["listId"] == ""
    assert meeting_task["listIds"] == []


def test_topics_promote_to_task(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "测试雷达",
            "prompt": "验证候选晋升链路",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "测试候选",
            "summary": "将候选分别转为任务和成长手册。",
            "source": "测试",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]

    to_task = client.post(f"/api/v1/topics/candidates/{candidate_id}/promote-task")
    assert to_task.status_code == 200
    assert to_task.json()["sourceType"] == "topic_candidate"
    assert to_task.json()["listId"] == ""
    assert to_task.json()["listIds"] == []


def test_topics_task_plan_and_batch_promote(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "资助机会",
            "prompt": "关注公益组织可申请的资助信息。",
            "timeRange": "7_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "国际基金会开放资助申请",
            "summary": "某国际基金会面向公益组织开放资助申请，需提交申请表、机构资料，截止到2026年3月17日。",
            "source": "Grant Weekly",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "Grant application deadline is March 17, 2026. Prepare organization profile, proposal form and submit before deadline.",
    )

    plan = client.post(f"/api/v1/topics/candidates/{candidate_id}/task-plan")
    assert plan.status_code == 200
    plan_payload = plan.json()
    assert plan_payload["candidateId"] == candidate_id
    assert len(plan_payload["tasks"]) >= 3
    assert any(task["dueDate"] == "2026-03-17" for task in plan_payload["tasks"])

    promoted = client.post(
        f"/api/v1/topics/candidates/{candidate_id}/promote-tasks",
        json={
            "tasks": [
                {
                    "title": "撰写申请表",
                    "desc": "完成资助申请表初稿。",
                    "priority": "high",
                    "listId": "list-0",
                    "dueDate": "2026-03-16",
                    "ddl": "3月16日前",
                    "ownerName": "测试员",
                    "collaboratorIds": [],
                    "tags": ["资助申报"],
                    "note": "需先核对预算字段。",
                },
                {
                    "title": "整理组织资料",
                    "desc": "准备机构简介、案例和证明材料。",
                    "priority": "normal",
                    "listId": "list-0",
                    "dueDate": "2026-03-17",
                    "ddl": "3月17日前",
                    "ownerName": "测试员",
                    "collaboratorIds": [],
                    "tags": ["材料准备"],
                    "note": "包含近两年项目成果。",
                },
            ]
        },
    )
    assert promoted.status_code == 200
    promoted_payload = promoted.json()
    assert promoted_payload["createdCount"] == 2

    tasks = client.get("/api/v1/tasks")
    assert tasks.status_code == 200
    task_items = tasks.json()["tasks"]
    assert sum(1 for task in task_items if task["sourceId"] == candidate_id) == 2
    assert any(task["note"] == "需先核对预算字段。" for task in task_items if task["sourceId"] == candidate_id)

    topics = client.get("/api/v1/topics")
    candidate = next(item for item in topics.json()["candidates"] if item["id"] == candidate_id)
    assert candidate["status"] == "promoted"


def test_topic_candidate_insight_extracts_points_reasons_and_practical_uses(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "大模型应用",
            "prompt": "关注公益与咨询行业的大模型落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "公益组织开始用 AI 做客户研究",
            "summary": "文章介绍了公益咨询团队如何把 AI 用在客户研究、复盘和材料整理中，并提到可以沉淀内部方法。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "The article explains how nonprofit consulting teams use AI for client research, internal review, and knowledge management. It suggests turning the workflow into a reusable playbook and collecting tool resources for the team.",
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert payload["candidateId"] == candidate_id
    assert "一、" in payload["overview"]
    assert "二、" in payload["overview"]
    assert "三、" in payload["overview"]
    assert len(payload["overview"]) >= 80
    assert len(payload["keyPoints"]) >= 1
    assert len(payload["recommendationReasons"]) >= 1
    assert len(payload["practicalUses"]) >= 1
    assert len(payload["editorialNote"]) >= 80
    assert len(payload["discussionPrompts"]) >= 1


def test_topic_candidate_prefetches_insight_on_create(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "安全观察",
            "prompt": "关注大模型落地中的安全与治理风险。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "大模型安全落地的新方案",
            "summary": "文章讨论了企业在大模型落地过程中面临的安全风险，并介绍了覆盖评估、防护和数据治理的整体方案。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]

    wait_for_topic_insight_status(client, candidate_id)
    db = client.app.state.app_state.db
    row = db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
    assert row is not None
    assert row["overview"]
    assert row["editorial_note"]


def test_topic_candidate_chat_uses_candidate_context(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "大模型应用",
            "prompt": "关注 AI 落地案例、团队方法和业务变化。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "OpenAI 用真实客户案例展示 AI 落地效果",
            "summary": "文章介绍了 AI 如何在真实业务场景中落地，并强调效率提升来自工作流重构，不只是工具升级。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    captured: dict[str, str] = {}

    def fake_generate_topic_candidate_chat_response(prompt: str, system_instruction: str, context_summary: str):
        captured["prompt"] = prompt
        captured["system_instruction"] = system_instruction
        captured["context_summary"] = context_summary
        return AiStructuredResponse(
            content="这条新闻真正值得继续追问的，是 AI 改变的到底是工具能力，还是咨询服务的交付结构。",
            judgment="",
            analysis="",
            actions="",
            timeline="",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_topic_candidate_chat_response", fake_generate_topic_candidate_chat_response)

    response = client.post(
        f"/api/v1/topics/candidates/{candidate_id}/chat",
        json={
            "question": "这件事对咨询团队的服务结构意味着什么？",
            "history": [
                {
                    "role": "user",
                    "content": "我已经看完了这篇新闻。",
                    "createdAt": "2026-03-16T10:00:00",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidateId"] == candidate_id
    assert payload["message"]["role"] == "assistant"
    assert "交付结构" in payload["answer"]
    assert captured["prompt"] == "这件事对咨询团队的服务结构意味着什么？"
    assert "当前情报标题：OpenAI 用真实客户案例展示 AI 落地效果" in captured["context_summary"]
    assert "候选摘要：" in captured["context_summary"]
    assert "已发生的对话：" in captured["context_summary"]
    assert "用户：我已经看完了这篇新闻。" in captured["context_summary"]


def test_topic_candidate_insight_refreshes_stale_editorial_tone(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "一个新的 GitHub 开源 AI coding agent 项目",
            "summary": "这个项目希望把开发过程里的重复步骤压缩掉，让普通开发者也能更快跑起来。",
            "source": "GitHub",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "九千星标背后不仅是工具的流行，更折射出专业能力民主化的深层趋势，意味着组织需要重新审视竞争壁垒。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "build_topic_candidate_insight",
        lambda **kwargs: {
            "overview": "一、这篇文章主要讲什么：它介绍了一个新的 GitHub 开源项目，重点展示它如何压缩开发流程中的重复环节。\n二、文章里最值得抓住的观点：项目希望把原本重度依赖经验的步骤做薄。\n三、它对团队的实际价值：可以帮助团队更快判断这种工具有没有真实落地价值。",
            "keyPoints": [
                "这个项目想解决的是开发流程里那些重复、繁琐、门槛高的步骤。",
                "它的价值不在于概念新，而在于让普通开发者更快跑起来。",
                "如果它真能接进工作流，影响的会是交付速度和协作方式。",
            ],
            "recommendationReasons": [
                "它把“到底替用户省了哪一步”讲得更清楚了。",
                "它适合拿来判断这种开源项目是不是只有概念，还是已经有产品价值。",
            ],
            "practicalUses": [
                "从“开源项目是不是产品雏形”这个角度写一篇短评。",
                "拆解它到底替用户省了哪一步，以及这一步为什么值钱。",
            ],
            "editorialNote": "如果把这个 GitHub 项目当成一个产品来看，最重要的不是它有多少功能，而是它到底替用户省掉了哪一步麻烦。它真正值钱的地方，是把原来很重、很慢、很专业的一段流程，压缩成普通开发者也能先跑起来的一套用法。所以大周更想讲清楚的是：它到底解决了什么具体问题，能让谁少花时间，值不值得接进真实工作流。",
            "discussionPrompts": [
                "这个项目最核心是在替用户省哪一步麻烦？",
                "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
            ],
        },
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "替用户省掉了哪一步麻烦" in payload["editorialNote"]
    assert "专业能力民主化" not in payload["editorialNote"]
    assert "背后不仅是工具的流行" not in payload["editorialNote"]


def test_topic_candidate_insight_refreshes_generic_editorial_template(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "字节开源多 Agent 框架获三十四万星",
            "summary": "文章提到字节开源的多 Agent 框架在 GitHub 走红，并强调它原生适配飞书，面向企业自动化场景。",
            "source": "新浪财经",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "build_topic_candidate_insight",
        lambda **kwargs: {
            "overview": "一、这篇文章主要讲什么：它介绍了字节开源的多 Agent 框架，强调高 star 增长、飞书适配和企业自动化定位。\n二、文章里最值得抓住的观点：项目试图把多代理协作和流程编排打包成更容易接入的框架。\n三、它对团队的实际价值：适合用来判断这种高热开源项目到底有没有真实业务落地价值。",
            "keyPoints": [
                "字节开源的多 Agent 框架在 GitHub 获得超 34 万星，短时间内形成了很高热度。",
                "文章特别提到它原生适配飞书，并定位企业自动化场景。",
                "项目强调多代理协作、流程编排和现成集成能力。",
            ],
            "recommendationReasons": [
                "它把企业自动化框架到底替谁省事、能省哪一步这件事讲得更具体了。",
                "它适合帮助团队判断高热开源项目和真实落地能力之间有没有断层。",
            ],
            "practicalUses": [
                "围绕多 Agent 框架到底能不能接进企业自动化场景写一篇短评。",
                "拆解飞书适配和流程编排到底意味着什么真实使用门槛。",
            ],
            "editorialNote": "字节这套多 Agent 框架最值得看的，不是星数本身，而是它把飞书适配和企业自动化场景一起讲出来了。这样看，它想解决的不是“再做一个 Agent demo”，而是把多代理协作真正塞进企业现有流程里。如果这点讲得实，它的价值就在于帮团队少掉一大段从零拼装流程编排和集成能力的工作。",
            "discussionPrompts": [
                "飞书适配到底只是展示层集成，还是已经触到真实流程编排？",
                "34 万星代表热度，还是已经代表了可复用价值？",
            ],
        },
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "飞书" in payload["editorialNote"]
    assert "企业自动化" in payload["editorialNote"]
    assert "如果把这个 GitHub 项目当成一个产品来看" not in payload["editorialNote"]


def test_topic_candidate_insight_grounds_editorial_note_to_article_facts(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "字节开源多 Agent 框架获三十四万星",
            "summary": "文章提到字节开源的多 Agent 框架在 GitHub 走红，并强调它原生适配飞书，面向企业自动化场景。",
            "source": "新浪财经",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        "UPDATE topic_candidates SET source_url = ? WHERE id = ?",
        ("https://example.com/agent-framework", candidate_id),
    )
    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "字节开源的多 Agent 框架在 GitHub 获得超 34 万星，文章特别提到它原生适配飞书，目标是企业自动化场景。原文还强调多代理协作、流程编排和现成集成能力，想减少团队从零搭框架的成本。",
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "34 万星" in payload["editorialNote"] or "34万星" in payload["editorialNote"]
    assert "飞书" in payload["editorialNote"]
    assert "如果把这个 GitHub 项目当成一个产品来看" not in payload["editorialNote"]


def test_topic_candidate_can_be_deleted_with_cached_insight(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "删除测试",
            "prompt": "验证候选删除后不会残留解析缓存。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "待删除候选",
            "summary": "验证删除操作。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    wait_for_topic_insight_status(client, candidate_id)

    deleted = client.delete(f"/api/v1/topics/candidates/{candidate_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    db = client.app.state.app_state.db
    assert db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,)) is None
    assert db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,)) is None
    seen = db.fetchone(
        "SELECT * FROM topic_candidate_seen WHERE radar_id = ? AND title_source_key = ?",
        (radar_id, "待删除候选||测试来源"),
    )
    assert seen is not None
    assert seen["deleted_at"] is not None


def test_topic_radar_update_keeps_record_count_stable(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "原始雷达",
            "prompt": "原始提示词",
            "timeRange": "3_days",
            "preferredSources": [{"url": "https://example.com/research", "label": "研究站"}],
        },
    )
    assert created.status_code == 200
    radar_id = created.json()["id"]
    assert created.json()["preferredSources"] == [{"url": "https://example.com/research", "label": "研究站"}]

    updated = client.put(
        f"/api/v1/topics/radars/{radar_id}",
        json={
            "title": "更新后的雷达",
            "prompt": "更新后的提示词",
            "timeRange": "7_days",
            "preferredSources": [{"url": "https://news.example.org", "label": "资讯站"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == radar_id
    assert updated.json()["title"] == "更新后的雷达"
    assert updated.json()["prompt"] == "更新后的提示词"
    assert updated.json()["timeRange"] == "7_days"
    assert updated.json()["preferredSources"] == [{"url": "https://news.example.org", "label": "资讯站"}]

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    assert len(topics.json()["radars"]) == 1
    assert topics.json()["radars"][0]["id"] == radar_id
    assert topics.json()["radars"][0]["preferredSources"] == [{"url": "https://news.example.org", "label": "资讯站"}]


def test_topic_radar_source_label_normalizes_url_and_uses_ai(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    monkeypatch.setattr(client.app.state.app_state.ai, "suggest_short_title", lambda prompt: "公益媒体")

    response = client.post(
        "/api/v1/topics/radars/source-label",
        json={"url": "chinadevelopmentbrief.org.cn/topics"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://chinadevelopmentbrief.org.cn/topics",
        "label": "公益媒体",
    }


def test_topic_radar_assist_generates_title_and_expands_prompt(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    monkeypatch.setattr(client.app.state.app_state.ai, "suggest_short_title", lambda prompt: "资助情报")
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "suggest_topic_search_queries",
        lambda *, title, prompt, time_range: ["公益资助 申报公告", "基金会 资助项目", "社会组织 征集通知"],
    )

    assisted = client.post(
        "/api/v1/topics/radars/assist",
        json={
            "prompt": "公益资助信息",
            "timeRange": "7_days",
        },
    )
    assert assisted.status_code == 200
    payload = assisted.json()
    assert payload["title"] == "资助情报"
    assert payload["queries"] == ["公益资助 申报公告", "基金会 资助项目", "社会组织 征集通知"]
    assert "公益资助信息" in payload["prompt"]
    assert "近 7 天" in payload["prompt"]
    assert "“公益资助 申报公告”" in payload["prompt"]


def test_topic_capture_writes_real_search_results_into_candidate_pool(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "公益咨询团队",
            "prompt": "关注公益咨询团队如何用 AI 做客户研究与项目复盘。",
            "timeRange": "3_days",
            "preferredSources": [{"url": "https://chinadevelopmentbrief.org.cn/topics", "label": "公益媒体"}],
        },
    )
    assert created.status_code == 200

    def fake_fetch(*args, **kwargs):
        assert kwargs["preferred_source_urls"] == ["https://chinadevelopmentbrief.org.cn/topics"]
        return [
            TopicSearchHit(
                title="AI is changing how nonprofit consultancies run client research",
                summary="Consulting teams are using AI to support client research and project reviews.",
                source="测试来源A",
                source_url="https://example.com/a",
                published_at="2026-03-13T10:00:00+08:00",
                provider="google_news",
                query="公益咨询团队 AI 客户研究",
            ),
            TopicSearchHit(
                title="AI is changing how nonprofit consultancies run client research",
                summary="重复结果不应再次写入。",
                source="测试来源A",
                source_url="https://example.com/a",
                published_at="2026-03-13T10:00:00+08:00",
                provider="google_news",
                query="公益咨询团队 AI 客户研究",
            ),
            TopicSearchHit(
                title="咨询项目复盘开始结构化沉淀",
                summary="项目复盘流程开始沉淀成标准动作。",
                source="测试来源B",
                source_url="https://example.com/b",
                published_at="2026-03-13T12:00:00+08:00",
                provider="bing_news",
                query="公益咨询团队 项目复盘",
            ),
        ]

    monkeypatch.setattr(app_main, "fetch_topic_candidates_from_web", fake_fetch)

    capture = client.post("/api/v1/topics/capture")
    assert capture.status_code == 200
    payload = capture.json()
    assert payload["totalCreated"] == 2
    assert payload["totalSkipped"] == 1
    assert payload["runs"][0]["createdCount"] == 2
    assert payload["runs"][0]["query"] == "公益咨询团队 AI 客户研究"

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    candidates = topics.json()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["captureMethod"] == "web_search"
    assert candidates[0]["capturedBy"] == "大周"
    assert candidates[0]["sourceUrl"].startswith("https://example.com/")
    assert all(any("\u4e00" <= char <= "\u9fff" for char in candidate["title"]) for candidate in candidates)
    assert all(any("\u4e00" <= char <= "\u9fff" for char in candidate["summary"]) for candidate in candidates)


def test_deleted_topic_candidate_is_not_recaptured(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "重复新闻测试",
            "prompt": "验证删除后的新闻不会再次抓回。",
            "timeRange": "3_days",
        },
    )
    assert created.status_code == 200

    def fake_fetch(*args, **kwargs):
        return [
            TopicSearchHit(
                title="同一条新闻",
                summary="第一次抓到后删除，再抓取时不应重新进入候选池。",
                source="测试来源",
                source_url="https://example.com/repeated-news?oc=5",
                published_at="2026-03-15T09:00:00+08:00",
                provider="google_news",
                query="重复新闻测试",
            )
        ]

    monkeypatch.setattr(app_main, "fetch_topic_candidates_from_web", fake_fetch)

    first_capture = client.post("/api/v1/topics/capture")
    assert first_capture.status_code == 200
    assert first_capture.json()["totalCreated"] == 1
    candidate_id = first_capture.json()["runs"][0]["candidates"][0]["id"]

    deleted = client.delete(f"/api/v1/topics/candidates/{candidate_id}")
    assert deleted.status_code == 200

    second_capture = client.post("/api/v1/topics/capture")
    assert second_capture.status_code == 200
    assert second_capture.json()["totalCreated"] == 0
    assert second_capture.json()["totalSkipped"] == 1

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    assert topics.json()["candidates"] == []


def test_legacy_scan_and_import_only_accepts_json_and_csv(tmp_path: Path):
    client = make_client(tmp_path)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    json_path = legacy_dir / "client.json"
    csv_path = legacy_dir / "records.csv"
    sqlite_path = legacy_dir / "archive.sqlite"
    json_path.write_text('{"name":"legacy"}', encoding="utf-8")
    csv_path.write_text("title,summary\nalpha,beta\n", encoding="utf-8")
    sqlite_path.write_text("not a real sqlite file", encoding="utf-8")

    scanned = client.post("/api/v1/settings/legacy-scan", json={"path": str(legacy_dir)})
    assert scanned.status_code == 200
    payload = scanned.json()
    entries = {item["path"]: item for item in payload["entries"]}
    assert entries[str(json_path)]["importable"] is True
    assert entries[str(csv_path)]["importable"] is True
    assert entries[str(sqlite_path)]["importable"] is False

    created = client.post(
        "/api/v1/clients",
        json={
            "name": "旧数据接收客户",
            "alias": "旧数据",
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "旧数据导入测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    client_id = created.json()["id"]

    imported = client.post(
        "/api/v1/imports",
        json={
            "clientId": client_id,
            "mode": "file",
            "paths": [str(json_path), str(csv_path)],
            "allowLegacy": True,
        },
    )
    assert imported.status_code == 200
    assert sum(item["importedCount"] for item in imported.json()) == 2

    rejected = client.post(
        "/api/v1/imports",
        json={
            "clientId": client_id,
            "mode": "file",
            "paths": [str(sqlite_path)],
            "allowLegacy": True,
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()[0]["importedCount"] == 0
    assert rejected.json()[0]["skippedCount"] == 1


def test_workspace_import_builds_document_cards_and_knowledge_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    root = tmp_path / "knowledge-source"
    nested = root / "项目资料"
    nested.mkdir(parents=True)
    (nested / "推进纪要.md").write_text(
        "# 项目推进纪要\n本周主要推进捐赠人沟通、预算梳理与阶段里程碑确认。\n下一步需要补齐项目执行方案与传播节奏。",
        encoding="utf-8",
    )
    (nested / "品牌传播.txt").write_text(
        "传播计划围绕品牌故事、媒体合作与活动节奏展开，需要同步公众号与社媒安排。",
        encoding="utf-8",
    )

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(root)]},
    )
    assert imported.status_code == 200
    assert sum(item["importedCount"] for item in imported.json()) == 2
    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert [folder["label"] for folder in payload["folders"]] == ["财务与筹款", "品牌与传播", "项目与业务", "组织与战略", "其他资料", "战略陪伴"]
    assert payload["knowledgeStatus"]["totalDocuments"] == 2
    assert payload["knowledgeStatus"]["totalChunks"] >= 2
    assert payload["knowledgeStatus"]["surrogateCount"] == 2
    assert payload["knowledgeStatus"]["reclassifiedDocumentCount"] == 2
    assert payload["knowledgeStatus"]["qdrantReady"] is True
    assert payload["knowledgeStatus"]["embeddingMode"] in {"fastembed", "fastembed_available", "hash_fallback"}
    assert payload["knowledgeStatus"]["pendingJobs"] == 0
    assert payload["knowledgeStatus"]["runningJobs"] == 0
    assert payload["knowledgeJobs"][0]["status"] == "completed"
    assert len(payload["recentReclassEvents"]) >= 2
    assert len(payload["documentCards"]) == 2
    first_card = payload["documentCards"][0]
    assert first_card["docId"].startswith("dock_")
    assert first_card["chunkCount"] >= 1
    assert first_card["primaryCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}
    assert first_card["surrogateMdPath"].endswith(".md")
    assert Path(first_card["surrogateMdPath"]).exists()
    assert Path(first_card["sourcePath"]).exists()
    assert first_card["logicalCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}
    notebook = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook.status_code == 200
    notebook_facts = [item["factValue"] for item in notebook.json()["keyFacts"]]
    assert any("推进纪要" in item or "品牌传播" in item for item in notebook_facts)


def test_workspace_import_auto_generates_client_dna_candidates(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "自动候选客户")
    source = tmp_path / "auto-dna-source"
    source.mkdir()
    (source / "项目介绍.md").write_text(
        "# 项目介绍\n益语智库是一家长期服务公益机构的战略陪伴团队，当前项目聚焦任务协同、会议复盘与资料底盘建设。\n"
        "团队成员包括顾源源、庆华和罗茜茜，当前重点是把组织介绍、项目介绍和市场背景统一成系统上下文。",
        encoding="utf-8",
    )

    def fake_generate_structured(prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        if "组织介绍" in prompt:
            return AiStructuredResponse(
                content="## 1. 组织定位\n益语智库是一家面向公益机构的战略陪伴与知识底盘建设团队。\n\n## 2. 工作方式\n强调陪伴式共创、任务协同和资料沉淀。",
                judgment="益语智库聚焦公益行业的战略陪伴与知识底盘建设，强调陪伴式共创和长期沉淀。",
                analysis="仍缺组织发展历史\n仍缺核心使命的更完整表述",
                actions="项目介绍.md",
                timeline="建议继续补组织发展材料后再重扫。",
            )
        if "团队介绍" in prompt:
            return AiStructuredResponse(
                content="## 1. 团队概述\n当前团队围绕项目运营、研究和协同支持展开。\n\n## 2. 核心负责人\n顾源源负责整体推进。",
                judgment="当前团队已能看出负责人和协作框架，但角色分工还需要更细。",
                analysis="仍缺客户侧接口人\n仍缺完整角色分工",
                actions="项目介绍.md",
                timeline="建议补团队分工资料。",
            )
        if "市场背景" in prompt:
            return AiStructuredResponse(
                content="## 1. 行业概况\n公益机构正在持续提升任务协同、资料管理与项目复盘能力。",
                judgment="市场背景已有公益行业数字化协同方向的基本判断。",
                analysis="仍缺竞品或参照对象\n仍缺行业趋势数据",
                actions="项目介绍.md",
                timeline="建议补行业研究材料。",
            )
        return AiStructuredResponse(
            content="## 1. 项目概述\n当前项目聚焦任务、会议与知识底盘的一体化建设。\n\n## 2. 当前重点\n先把已有资料转成系统共享上下文。",
            judgment="该项目当前重点是把已有资料沉淀成系统可引用的统一项目上下文。",
            analysis="仍缺成功标准\n仍缺更细的服务范围",
            actions="项目介绍.md",
            timeline="建议补项目目标和服务范围后再重扫。",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", fake_generate_structured)

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(source)]},
    )
    assert imported.status_code == 200

    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    modules = {item["moduleKey"]: item for item in workspace.json()["dnaModules"]}
    assert modules["organization_intro"]["hasDocument"] is True
    assert modules["organization_intro"]["sourceKind"] == "generated"
    assert "仍缺组织发展历史" in modules["organization_intro"]["missingInfo"]
    assert modules["business_intro"]["fileName"].endswith("business_intro-candidate.md")
    assert modules["team_intro"]["sourceKind"] == "generated"
    assert modules["market_intro"]["sourceKind"] == "generated"


def test_rebuild_backfills_logical_mappings_for_existing_knowledge_docs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="历史知识回填客户")
    file_path = tmp_path / "legacy-org-intro.md"
    file_path.write_text(
        "# 机构介绍\n为爱黔行当前重点在山区儿童教育、捐赠人沟通和项目推进。",
        encoding="utf-8",
    )

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    ready = wait_for_knowledge_ready(client, client_id)
    assert ready["surrogateCount"] == 1

    app_state = client.app.state.app_state
    app_state.db.execute(
        "DELETE FROM logical_file_mappings WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE client_id = ?)",
        (client_id,),
    )
    app_state.db.execute(
        """
        UPDATE knowledge_documents
        SET current_human_path = NULL, human_folder_category = NULL, reclassified_at = NULL, reclass_reason = '', reclass_confidence = classification_confidence
        WHERE client_id = ?
        """,
        (client_id,),
    )

    rebuild = client.post(f"/api/v1/clients/{client_id}/knowledge/rebuild")
    assert rebuild.status_code == 200
    rebuild_ready = wait_for_knowledge_ready(client, client_id)
    assert rebuild_ready["reclassifiedDocumentCount"] == 1

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert payload["recentReclassEvents"]
    assert payload["documentCards"][0]["logicalCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}


def test_chat_uses_knowledge_citations_and_general_answer_fallback(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="问答测试客户")
    file_path = tmp_path / "donor-note.md"
    file_path.write_text(
        "# 捐赠人反馈\n捐赠人最关心预算透明度和项目里程碑，建议下周补充预算拆解并同步月度推进节奏。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    search = client.post(
        f"/api/v1/clients/{client_id}/knowledge/search",
        json={"prompt": "捐赠人反馈里提到的预算和推进节奏是什么？"},
    )
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["searchId"]
    assert search_payload["masterHitCount"] >= 1
    assert search_payload["surrogateHitCount"] >= 1

    grounded = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "捐赠人反馈里提到的预算和推进节奏是什么？", "searchId": search_payload["searchId"]},
    )
    assert grounded.status_code == 200
    grounded_payload = grounded.json()
    assert grounded_payload["evidence"]
    assert grounded_payload["evidence"][0]["score"] is not None
    assert grounded_payload["evidence"][0]["coverage"] >= 0.5
    assert grounded_payload["evidence"][0]["retrievalStage"] in {"surrogate", "raw_chunk", "master_index"}
    assert grounded_payload["llmInvoked"] is True
    assert grounded_payload["answerMode"] in {"grounded_answer", "grounded_fallback", "low_confidence_answer"}
    assert grounded_payload["retrievalSummary"]["searchId"] == search_payload["searchId"]
    assert grounded_payload["retrievalSummary"]["cacheHit"] is True

    general = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CEO 新年度组织架构怎么调整？"},
    )
    assert general.status_code == 200
    general_payload = general.json()
    assert general_payload["llmInvoked"] is True
    assert general_payload["answerMode"] == "general_answer"
    assert general_payload["retrievalSummary"]["retrievalStage"] == "background_only"
    assert general_payload["evidence"] == []
    assert "以下内容不是基于当前客户原始资料的正式分析" in general_payload["content"]


def test_identity_role_query_requires_explicit_role_evidence(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="CFFC")
    transcript = tmp_path / "workshop.md"
    transcript.write_text(
        "# 战略工作坊实录\n顾源源在本次工作坊中主要负责提问、梳理业务逻辑和推进后续访谈，并未担任 CFFC 内部角色。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(transcript)]},
    )
    assert imported.status_code == 200
    wait_for_knowledge_ready(client, client_id)

    def should_not_run(*args, **kwargs):
        raise AssertionError("identity guard should prevent normal answer generation")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", should_not_run)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 创始人是什么样的人，分析一下"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "identity_role_evidence_insufficient"
    assert "不足以直接确认" in payload["content"]
    assert "创始人" in payload["content"]


def test_strategy_query_prefers_cross_category_materials(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略问题检索客户")
    strategy_doc = tmp_path / "org-strategy.md"
    strategy_doc.write_text(
        "# 组织战略与治理\n当前战略重点是把项目陪伴与机构筹资联动起来，董事会更关注组织治理、年度路线图和关键风险。",
        encoding="utf-8",
    )
    brand_doc = tmp_path / "brand-note.md"
    brand_doc.write_text(
        "# 品牌传播规划\n目前品牌传播的主要任务是统一外部叙事、优化机构介绍和捐赠人沟通材料，避免战略表达与传播表达脱节。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(strategy_doc), str(brand_doc)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 2

    search = client.post(
        f"/api/v1/clients/{client_id}/knowledge/search",
        json={"prompt": "结合现有资料，概括这个机构的战略重点、传播线索和潜在风险。"},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["masterHitCount"] >= 2
    assert payload["surrogateHitCount"] >= 1
    assert "组织与战略" in payload.get("categoryCoverage", [])
    assert "品牌与传播" in payload.get("categoryCoverage", [])


def test_vectorize_answer_creates_memory_doc_and_export_answer_writes_docx(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略陪伴测试客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，当前重点在捐赠人沟通和项目里程碑梳理。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍为爱黔行"},
    )
    assert answer.status_code == 200
    message_id = answer.json()["id"]

    vectorized = client.post(
        f"/api/v1/clients/{client_id}/knowledge/vectorize-answer",
        json={"messageId": message_id},
    )
    assert vectorized.status_code == 200
    vector_payload = vectorized.json()
    assert vector_payload["sourceType"] == "memory_answer"
    assert Path(vector_payload["surrogateMdPath"]).exists()

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["knowledgeStatus"]["memoryDocCount"] == 1

    reclass_events = client.get(f"/api/v1/clients/{client_id}/knowledge/reclass-events")
    assert reclass_events.status_code == 200

    exported = client.post(
        f"/api/v1/clients/{client_id}/knowledge/export-answer",
        json={"messageId": message_id},
    )
    assert exported.status_code == 200
    export_path = Path(exported.json()["path"])
    assert export_path.exists()
    assert export_path.suffix == ".docx"


def test_chat_falls_back_to_local_retrieval_summary_when_llm_generation_times_out(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="本地综述兜底客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，已经形成机构介绍、项目推进和捐赠人沟通三条主线。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_qwen_timeout(*args, **kwargs):
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_qwen_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_general_fallback", raise_qwen_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "为爱黔行是一家什么样的机构？请简要介绍。"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["llmInvoked"] is True
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] in {"llm_local_fallback_after_retry", "llm_compact_fallback"}
    assert "为爱黔行" in payload["content"]
    assert payload["evidence"]


def test_analysis_run_keeps_evidence_summary_when_long_answer_fails(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="异步分析兜底客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，已经形成机构介绍、项目推进和捐赠人沟通三条主线。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_qwen_timeout(*args, **kwargs):
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_qwen_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_qwen_timeout)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "为爱黔行是一家什么样的机构？请简要介绍。"},
    )
    assert started.status_code == 200
    start_payload = started.json()
    run_id = start_payload["analysisRun"]["id"]
    assert start_payload["analysisRun"]["status"] == "queued"

    deadline = time.time() + 30.0
    evidence_seen = False
    final_run: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["evidenceSummary"]["masterHitCount"] >= 1:
            evidence_seen = True
            assert payload["evidenceSummary"]["evidenceList"]
        if payload["status"] in {"completed", "failed"}:
            final_run = payload
            break
        time.sleep(0.1)

    assert evidence_seen is True
    assert final_run is not None
    assert final_run["status"] == "completed"
    assert final_run["longAnswerStatus"] == "fallback"
    assert final_run["summaryStatus"] == "fallback"
    assert final_run["failureReason"] == "llm_local_fallback_after_retry"
    assert final_run["evidenceSummary"]["summaryText"]
    assert final_run["longAnswer"]
    assert final_run["structuredSummary"]


def test_organization_dna_upload_replace_and_settings_roundtrip(tmp_path: Path):
    client = make_client(tmp_path)

    uploaded = client.post(
        "/api/v1/settings/org-dna/organization_intro",
        json={
          "markdownContent": "# 组织介绍\n益语智库专注于公益咨询与知识沉淀。",
          "fileName": "organization-intro.md",
        },
    )
    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["moduleKey"] == "organization_intro"
    assert payload["hasDocument"] is True
    assert "益语智库" in payload["normalizedText"]

    replaced = client.post(
        "/api/v1/settings/org-dna/organization_intro",
        json={
          "markdownContent": "# 组织介绍\n益语智库专注于公益咨询、任务协同与知识工作台。",
          "fileName": "organization-intro-v2.md",
        },
    )
    assert replaced.status_code == 200
    replaced_payload = replaced.json()
    assert replaced_payload["fileName"] == "organization-intro-v2.md"
    assert "任务协同" in replaced_payload["normalizedText"]

    modules = client.get("/api/v1/settings/org-dna")
    assert modules.status_code == 200
    assert len(modules.json()["modules"]) == 4

    topics_settings = client.post(
        "/api/v1/settings/topics",
        json={
            "defaultTimeRange": "7_days",
            "defaultTaskOwnerMode": "empty",
            "useOrgDnaForInsight": True,
        },
    )
    assert topics_settings.status_code == 200
    assert topics_settings.json()["defaultTimeRange"] == "7_days"
    assert topics_settings.json()["defaultTaskOwnerMode"] == "empty"

    analysis_settings = client.post(
        "/api/v1/settings/analysis-workbench",
        json={
            "defaultTitlePrefix": "组织分析",
            "useOrgDna": True,
        },
    )
    assert analysis_settings.status_code == 200
    assert analysis_settings.json()["defaultTitlePrefix"] == "组织分析"


def test_client_dna_documents_are_saved_and_prioritized_in_chat_context(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "客户DNA测试客户")
    state = client.app.state.app_state

    uploaded = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n该客户是公益行业的可信基础设施与协作中枢。",
            "fileName": "client-organization-intro.md",
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["hasDocument"] is True

    uploaded = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/business_intro",
        json={
            "markdownContent": "# 项目介绍\n核心项目围绕行业研究、陪伴式咨询与知识底座建设展开。",
            "fileName": "client-business-intro.md",
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["hasDocument"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    assert len(workspace_payload["dnaModules"]) == 4
    assert workspace_payload["dnaModules"][0]["clientId"] == client_id
    assert any(module["hasDocument"] for module in workspace_payload["dnaModules"])

    seed_timestamp = "2026-03-14T10:00:00"
    state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_seed', ?, NULL, '普通资料', '/tmp/source.md', 'md', 'file', '这里是普通知识库中的一段背景材料。', '[]', ?)
        """,
        (client_id, seed_timestamp),
    )
    state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_doc_seed', ?, NULL, 'doc_seed', 'kd_doc_seed_uid', '/tmp/source.md', '/tmp/source.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '机构介绍', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_seed', 'normalized_seed', ?, ?
        )
        """,
        (client_id, seed_timestamp, seed_timestamp),
    )

    captured_context: dict[str, str] = {}

    def fake_bundle(db, data_dir, client_id_arg: str, prompt: str) -> RetrievalBundle:
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_doc_seed",
                    chunk_id="chunk_seed",
                    title="普通资料",
                    excerpt="这里是普通知识库中的一段背景材料。",
                    score=0.9,
                    coverage=0.5,
                    section_label="原文片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["客户"],
                    path="/tmp/source.md",
                )
            ],
            coverage=0.5,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "drillthroughUsed": True,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["客户"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        captured_context["context"] = context_summary
        return app_main.AiStructuredResponse(
            content="这是基于客户 DNA 优先整理的一版回答。",
            judgment="已优先纳入客户 DNA。",
            analysis="1. 先读客户 DNA。\n2. 再结合普通资料。",
            actions="继续补充更多客户 DNA 模块。",
            timeline="可继续扩写。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fake_bundle)
    monkeypatch.setattr(state.ai, "generate_chat_response", fake_generate_chat_response)

    answered = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍这家客户"},
    )
    assert answered.status_code == 200
    answered_payload = answered.json()
    assert answered_payload["retrievalSummary"]["memoryBackgroundUsed"] is True
    assert answered_payload["retrievalSummary"]["memoryBackgroundSources"]
    context = captured_context["context"]
    assert "统一记忆背景（仅用于帮助理解组织与推进，不作为正式引证）：" in context
    assert "统一记忆使用规则=统一记忆只作为背景上下文" in context
    assert context.index("统一记忆背景（仅用于帮助理解组织与推进，不作为正式引证）：") < context.index("客户背景底稿（仅用于理解客户，不作为正式引证）：")
    assert "客户背景底稿（仅用于理解客户，不作为正式引证）：" in context
    assert "背景底稿使用规则=背景底稿只用于理解客户、修正语境和帮助组织分析，不作为正式引证或确定性事实来源。" in context
    assert "[组织介绍]" in context
    assert "可信基础设施与协作中枢" in context
    assert "[项目介绍]" in context
    assert "核心项目围绕行业研究、陪伴式咨询与知识底座建设展开" in context
    assert context.index("客户背景底稿（仅用于理解客户，不作为正式引证）：") < context.index("原始证据包（可用于正式判断）：")


def test_client_dna_documents_only_accept_markdown_extensions(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "Markdown 校验测试客户")

    rejected = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n这是一次错误扩展名测试。",
            "fileName": "organization-intro.txt",
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert "只允许上传 .md、.markdown 或 .docx 文件" in rejected.text

    accepted = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n这是一次正确扩展名测试。",
            "fileName": "organization-intro.markdown",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["hasDocument"] is True


def test_tasks_consume_project_dna_and_module_flow_context(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "项目上下文打通测试客户")

    uploads = {
        "organization_intro": "# 组织介绍\n该组织是一家长期深耕公益行业的战略陪伴机构，强调陪伴式共创与知识沉淀。",
        "business_intro": "# 项目介绍\n本项目聚焦公益机构的智能任务协同、会议复盘和项目资料底盘建设。",
        "team_intro": "# 团队介绍\n项目由顾源源总体负责，罗茜茜负责客户协同，庆华负责策略研判。",
        "market_intro": "# 市场背景\n当前公益咨询行业正在加速 AI 化，但对安全、治理和协同质量要求更高。",
    }
    for module_key, markdown in uploads.items():
        response = client.post(
            f"/api/v1/clients/{client_id}/dna-documents/{module_key}",
            json={
                "markdownContent": markdown,
                "fileName": f"{module_key}.md",
            },
        )
        assert response.status_code == 200, response.text

    created_module = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "客户协同模块",
            "goal": "统一客户接口、任务推进和会议纪要回流。",
            "description": "这个模块负责把客户接口、项目节奏和资料沉淀打成一个闭环。",
            "ownerName": "罗茜茜",
        },
    )
    assert created_module.status_code == 200, created_module.text
    module_payload = created_module.json()

    created_flow = client.post(
        f"/api/v1/clients/{client_id}/project-flows",
        json={
            "moduleId": module_payload["id"],
            "name": "客户周会复盘流程",
            "scenario": "客户周会后同步纪要、任务和风险。",
            "description": "先汇总会议纪要，再同步行动项与风险，最后回填项目资料。",
            "riskPoints": ["若纪要不完整，会导致任务上下文偏差。"],
        },
    )
    assert created_flow.status_code == 200, created_flow.text
    flow_payload = created_flow.json()

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "同步本周客户周会纪要",
            "desc": "把会议纪要、行动项和风险统一回填到项目底盘。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "projectModuleId": module_payload["id"],
            "projectFlowId": flow_payload["id"],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["clientId"] == client_id
    assert task_payload["projectModuleId"] == module_payload["id"]
    assert task_payload["projectModuleName"] == "客户协同模块"
    assert task_payload["projectFlowId"] == flow_payload["id"]
    assert task_payload["projectFlowName"] == "客户周会复盘流程"
    assert task_payload["projectContext"]["projectModuleId"] == module_payload["id"]
    assert task_payload["projectContext"]["projectFlowId"] == flow_payload["id"]
    assert "智能任务协同" in task_payload["projectContext"]["backgroundSummary"]
    assert "统一客户接口" in task_payload["projectContext"]["goalSummary"]
    assert "纪要不完整" in task_payload["projectContext"]["riskSummary"]
    assert "组织介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "项目介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "团队介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "市场背景介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert f"任务模块：{module_payload['name']}" in task_payload["projectContext"]["sourceEvidence"]
    assert f"流程：{flow_payload['name']}" in task_payload["projectContext"]["sourceEvidence"]

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert any(item["id"] == module_payload["id"] for item in workspace_payload["projectModules"])
    assert any(item["id"] == flow_payload["id"] for item in workspace_payload["projectFlows"])


def test_task_attachment_is_archived_to_workspace_and_event_line(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "任务附件归档测试客户")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会方案推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "方案补齐",
            "summary": "持续推进基金会合作方案与资料沉淀。",
            "intent": "把合作方案、资料、会议和支持请求沉淀到一条线里。",
            "nextStep": "补齐关键材料并继续推进方案。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_payload = created_event_line.json()

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "补齐黄河基金会合作方案材料",
            "desc": "上传方案资料并沉淀到项目工作台。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_payload["id"],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_payload["id"],
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "黄河基金会-合作方案补充.md",
                "# 黄河基金会合作方案\n\n本周补齐合作范围、背景资料与下一步动作。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded_task = upload_response.json()
    assert len(uploaded_task["attachments"]) == 1
    attachment = uploaded_task["attachments"][0]
    assert attachment["clientId"] == client_id
    assert attachment["eventLineId"] == event_line_payload["id"]
    assert attachment["documentId"]
    assert "本周补齐合作范围" in (attachment.get("summary") or "")
    assert Path(attachment["path"]).exists()

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert any(document["id"] == attachment["documentId"] for document in workspace_payload["documents"])

    event_line_detail = client.get(f"/api/v1/event-lines/{event_line_payload['id']}")
    assert event_line_detail.status_code == 200, event_line_detail.text
    detail_payload = event_line_detail.json()
    assert any(
        item["sourceType"] == "attachment" and item["metadata"].get("documentId") == attachment["documentId"]
        for item in detail_payload["activities"]
    )

    evidence_count = client.app.state.app_state.db.scalar(
        "SELECT COUNT(1) AS count FROM evidence_refs WHERE source_type = 'task_attachment' AND document_id = ?",
        (attachment["documentId"],),
    )
    assert evidence_count == 1


def test_memory_foundation_phase1_builds_notebook_event_line_and_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "记忆底座测试客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n这是一家围绕战略陪伴与知识沉淀提供服务的组织。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "记忆底座推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "资料补齐",
            "summary": "围绕客户资料补齐、会议结论和下一步动作持续推进。",
            "intent": "形成连续工作记忆，而不是只看单条任务。",
            "nextStep": "继续补齐材料并安排下次对齐会。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "补齐战略陪伴项目资料",
            "desc": "需要把客户背景、会议纪要和关键问题统一沉淀到事件线里。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    upload_response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": "补齐战略陪伴项目资料",
        },
        files={
            "file": (
                "战略陪伴补充资料.md",
                "# 补充资料\n\n这周先明确客户当前主要困境，再补齐下一步判断依据。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    task_payload = upload_response.json()
    assert task_payload["memoryHints"]
    assert task_payload["backgroundReadiness"]["level"] in {"medium", "high"}
    assert task_payload["linkedFactsPreview"]

    review_response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "taskEntries": [
                {
                    "taskId": task_id,
                    "contentDomain": "work",
                    "note": "本周已经补齐了部分背景，但还缺客户当前最真实的阻塞信息。",
                }
            ],
            "workFreeNote": "这周最明显的问题是背景证据还不够厚。",
        },
    )
    assert review_response.status_code == 200, review_response.text
    review_payload = review_response.json()
    summary_card = review_payload["workAnalysis"]["eventLineSummaries"][0]
    assert summary_card["eventLineId"] in {event_line_id, f"event_line::{event_line_id}"}
    if summary_card.get("memoryConfidence") is not None:
        assert summary_card["memoryConfidence"] > 0
    if summary_card.get("backgroundSources"):
        assert any(source in {"事件线记忆", "event_line_memory"} for source in summary_card["backgroundSources"])

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    notebook_payload = notebook_response.json()
    assert notebook_payload["organizationNotebookSnapshot"]["clientId"] == client_id
    assert notebook_payload["organizationNotebookSnapshot"]["currentStage"] == "推进中"
    assert notebook_payload["linkedEventLines"][0]["id"] == event_line_id
    assert any(item["factKey"].startswith("dna_module:organization_intro") for item in notebook_payload["keyFacts"])

    event_line_memory = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert event_line_memory.status_code == 200, event_line_memory.text
    memory_payload = event_line_memory.json()
    assert memory_payload["eventLineMemorySnapshot"]["eventLineId"] == event_line_id
    assert memory_payload["eventLineMemorySnapshot"]["lineName"] == "记忆底座推进线"
    assert memory_payload["eventLineMemorySnapshot"]["predictionReadiness"] > 0
    assert any("附件" in item or "任务" in item for item in memory_payload["evidenceRefs"])
    assert any("还缺客户当前最真实的阻塞信息" in item for item in memory_payload["eventLineMemorySnapshot"]["analysisSignals"])

    memory_status = client.get(f"/api/v1/clients/{client_id}/memory-status")
    assert memory_status.status_code == 200, memory_status.text
    status_payload = memory_status.json()
    assert status_payload["clientId"] == client_id
    assert status_payload["totalEventLines"] == 1
    assert status_payload["coveredEventLines"] == 1


def test_notebook_sanitizes_prompt_and_executive_summary_pollution(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "脏背景测试客户")
    db = client.app.state.app_state.db

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n这里先放一个正常组织介绍。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    db.execute(
        """
        UPDATE client_dna_documents
        SET summary = ?, updated_at = ?
        WHERE client_id = ? AND module_key = 'organization_intro'
        """,
        (
            '{"prompt":"你将作为深度研究+写作综合体","title":"日慈基金会机构DNA"}',
            "2026-03-23T10:00:00",
            client_id,
        ),
    )
    db.execute(
        "UPDATE clients SET intro = ?, updated_at = ? WHERE id = ?",
        (
            "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
            "2026-03-23T10:00:00",
            client_id,
        ),
    )

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    notebook = notebook_response.json()["organizationNotebookSnapshot"]
    assert '{"prompt"' not in notebook["organizationIntro"]
    assert "执行摘要" not in notebook["organizationIntro"]
    assert '{"prompt"' not in notebook["collaborationRelationship"]
    assert "执行摘要" not in notebook["collaborationRelationship"]


def test_task_memory_enrichment_matches_notebook_references(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "敦和合作客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n敦和基金会当前由林红负责合作拓展，正在与益语讨论联合研究和后续方案边界。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟敦和林红吃饭",
            "desc": "先确认联合研究合作边界。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task_payload = next(item for item in board.json()["tasks"] if item["id"] == task_id)
    assert any("命中对象" in hint for hint in task_payload["memoryHints"])
    assert any("人物背景" in hint for hint in task_payload["memoryHints"])
    assert any("对象背景" in hint for hint in task_payload["memoryHints"])
    assert any("关联背景" in hint for hint in task_payload["memoryHints"])
    assert "notebook_reference_match" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert "person_facts" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert "task_reference_match" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert any(fact["scopeType"] == "person" for fact in task_payload["linkedFactsPreview"])
    assert any(fact["factKey"].startswith("reference_match:") for fact in task_payload["linkedFactsPreview"])
    assert any("敦和基金会" in fact["factValue"] or "林红" in fact["factValue"] for fact in task_payload["linkedFactsPreview"])


def test_clarification_answer_writes_memory_facts(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "澄清写回答测试客户")

    created = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "current_goal",
            "question": "当前合作最核心的目标是什么？",
        },
    )
    assert created.status_code == 200, created.text
    clarification_id = created.json()["id"]

    answered = client.post(
        f"/api/v1/clarifications/{clarification_id}/answer",
        json={"answer": "先把组织背景补齐。再把季度重点和关键动作对齐。"},
    )
    assert answered.status_code == 200, answered.text
    answered_payload = answered.json()
    assert answered_payload["status"] == "answered"
    assert len(answered_payload["resolvedFactIds"]) >= 2

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    fact_values = [item["factValue"] for item in notebook_response.json()["keyFacts"]]
    assert any("先把组织背景补齐" in item for item in fact_values)
    assert any("季度重点和关键动作对齐" in item for item in fact_values)


def test_clarification_answer_backfills_person_scope_for_task_background(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "敦和合作客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n敦和基金会当前由林红负责合作拓展，正在与益语讨论联合研究和后续方案边界。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    clarification = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "partner_context",
            "question": "林红当前负责什么？",
        },
    )
    assert clarification.status_code == 200, clarification.text

    answered = client.post(
        f"/api/v1/clarifications/{clarification.json()['id']}/answer",
        json={"answer": "林红是敦和基金会合作拓展负责人，当前主要对接联合研究合作边界。"},
    )
    assert answered.status_code == 200, answered.text
    assert len(answered.json()["resolvedFactIds"]) >= 2

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟林红确认联合研究边界",
            "desc": "确认下一步合作方案。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task_payload = next(item for item in board.json()["tasks"] if item["id"] == task_id)
    assert "person_facts" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert any(
        fact["scopeType"] == "person" and fact["sourceType"] == "clarification"
        for fact in task_payload["linkedFactsPreview"]
    )
    assert any(
        "合作拓展负责人" in fact["factValue"]
        for fact in task_payload["linkedFactsPreview"]
        if fact["scopeType"] == "person"
    )


def test_refresh_task_contexts_backfills_existing_tasks(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "黄河基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会合作方案推进线",
            "kind": "project_line",
            "status": "active",
            "summary": "围绕黄河基金会合作方案持续推进。",
            "intent": "确认合作方向，补齐方案材料。",
            "nextStep": "进入方案确认并继续推进对外沟通。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_module = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "合作方案",
            "goal": "推进合作方案确认与落地。",
            "description": "围绕合作方案进行分析、补齐和确认。",
            "keywords": ["合作方案", "方案确认", "基金会合作"],
        },
    )
    assert created_module.status_code == 200, created_module.text
    module_id = created_module.json()["id"]

    created_flow = client.post(
        f"/api/v1/clients/{client_id}/project-flows",
        json={
            "moduleId": module_id,
            "name": "方案确认",
            "description": "确认当前合作方案与推进节奏。",
            "steps": ["补齐方案", "确认方向", "继续推进"],
            "riskPoints": ["方向不清", "材料不足"],
        },
    )
    assert created_flow.status_code == 200, created_flow.text
    flow_id = created_flow.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "黄河基金会合作方案推进与方案确认",
            "desc": "先补齐合作方案资料，再推进方案确认与下一轮沟通。",
            "priority": "high",
            "listId": "list-0",
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["clientId"] is None
    assert task_payload["eventLineId"] is None
    assert task_payload["projectModuleId"] is None
    assert task_payload["projectFlowId"] is None

    refreshed = client.post("/api/v1/tasks/refresh-contexts")
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    assert refreshed_payload["totalTasks"] >= 1
    assert refreshed_payload["updatedTasks"] >= 1
    assert refreshed_payload["clientUpdatedTasks"] >= 1
    assert refreshed_payload["eventLineUpdatedTasks"] >= 1
    assert refreshed_payload["moduleUpdatedTasks"] >= 1
    assert refreshed_payload["flowUpdatedTasks"] >= 1
    assert refreshed_payload["failedTasks"] == 0

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    refreshed_task = next(item for item in board.json()["tasks"] if item["id"] == task_payload["id"])
    assert refreshed_task["clientId"] == client_id
    assert refreshed_task["eventLineId"] == event_line_id
    assert refreshed_task["projectModuleId"] == module_id
    assert refreshed_task["projectFlowId"] == flow_id
    assert refreshed_task["backgroundReadiness"]["level"] in {"medium", "high"}
    event_line_memory = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert event_line_memory.status_code == 200, event_line_memory.text
    assert event_line_memory.json()["eventLineMemorySnapshot"]["confidence"] > 0


def test_bootstrap_event_lines_creates_starter_lines_for_existing_tasks(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "黄河基金会")

    business_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给黄河基金会系统合作方案",
            "desc": "先补齐合作方案，再推进系统合作确认与下一步沟通。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert business_task.status_code == 200, business_task.text
    business_task_id = business_task.json()["id"]
    assert business_task.json()["eventLineId"] is None

    personal_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "去体检",
            "desc": "个人安排。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert personal_task.status_code == 200, personal_task.text
    personal_task_id = personal_task.json()["id"]

    bootstrapped = client.post("/api/v1/tasks/bootstrap-event-lines")
    assert bootstrapped.status_code == 200, bootstrapped.text
    payload = bootstrapped.json()
    assert payload["createdEventLines"] >= 1
    assert payload["linkedTasks"] >= 1
    assert payload["failedTasks"] == 0

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    items = {item["id"]: item for item in board.json()["tasks"]}
    assert items[business_task_id]["eventLineId"]
    assert items[personal_task_id]["eventLineId"] is None
    assert items[business_task_id]["backgroundReadiness"]["level"] in {"medium", "high"}

    event_lines = client.get("/api/v1/event-lines")
    assert event_lines.status_code == 200, event_lines.text
    assert len(event_lines.json()) >= 1
    memory_response = client.get(f"/api/v1/event-lines/{items[business_task_id]['eventLineId']}/memory")
    assert memory_response.status_code == 200, memory_response.text
    assert memory_response.json()["eventLineMemorySnapshot"]["predictionReadiness"] > 0


def test_event_line_context_bundle_returns_memory_tasks_and_evidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "演示确认",
            "summary": "围绕系统演示、反馈和下一步合作判断持续推进。",
            "intent": "让关键联系人理解益语系统与合作目标的关系。",
            "nextStep": "补齐演示反馈并推进下一轮确认。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    updated_event_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "currentBlocker": "张真还没有把这次系统演示和内部协同目标正式对齐。",
            "recentDecision": "先用系统演示确认合作边界，再决定是否扩大到正式项目。",
            "nextStep": "整理会后反馈，并约下一轮确认会。",
        },
    )
    assert updated_event_line.status_code == 200, updated_event_line.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "通过现场演示让张真判断系统和当前合作目标的关系，并收集会后动作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    clarification = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "partner_context",
            "question": "张真在日慈当前负责什么？",
        },
    )
    assert clarification.status_code == 200, clarification.text
    answered = client.post(
        f"/api/v1/clarifications/{clarification.json()['id']}/answer",
        json={"answer": "张真目前负责日慈和益语的系统演示与下一步合作判断。"},
    )
    assert answered.status_code == 200, answered.text

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示反馈.md",
                "# 演示反馈\n\n张真重点关注系统与组织现有协同流程的贴合度。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    bundle_response = client.get(f"/api/v1/event-lines/{event_line_id}/context-bundle")
    assert bundle_response.status_code == 200, bundle_response.text
    payload = bundle_response.json()
    assert payload["eventLineId"] == event_line_id
    assert payload["lineName"] == "日慈系统演示推进线"
    assert payload["currentBlocker"] == "张真还没有把这次系统演示和内部协同目标正式对齐。"
    assert payload["nextStep"] == "整理会后反馈，并约下一轮确认会。"
    assert payload["taskCount"] >= 1
    assert payload["attachmentCount"] >= 1
    assert any(item["sourceId"] == task_payload["id"] for item in payload["taskFacts"])
    assert any(item["sourceId"] == attachment["id"] for item in payload["attachmentFacts"])
    assert any("张真" in item["summary"] for item in payload["clarificationFacts"])
    assert payload["evidenceRefs"]


def test_task_views_builtins_and_custom_view_roundtrip(tmp_path: Path):
    client = make_client(tmp_path)

    listed = client.get("/api/v1/task-views")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    preset_keys = {item["key"] for item in payload["presets"]}
    assert preset_keys == {"event_line", "risk", "source", "business_category"}
    built_in_kinds = {item["kind"] for item in payload["views"] if item["builtIn"]}
    assert {"event_line", "risk", "source", "business_category"} <= built_in_kinds

    created = client.post(
        "/api/v1/task-views",
        json={
            "name": "高证据事件线",
            "kind": "custom",
            "description": "优先查看高证据、已挂事件线的任务。",
            "calendarScope": "event_line",
            "shareability": "org",
            "sortBy": "evidenceCount",
            "sortDirection": "desc",
            "visibleFields": ["title", "status", "evidenceCount", "eventLine"],
            "filterSet": {
                "onlyWithEventLine": True,
                "minimumEvidenceCount": 1,
            },
        },
    )
    assert created.status_code == 200, created.text
    created_payload = created.json()
    assert created_payload["builtIn"] is False
    assert created_payload["kind"] == "custom"
    assert created_payload["sortBy"] == "evidenceCount"
    assert created_payload["filterSet"]["onlyWithEventLine"] is True
    assert created_payload["filterSet"]["minimumEvidenceCount"] == 1

    updated = client.patch(
        f"/api/v1/task-views/{created_payload['id']}",
        json={
            "name": "高证据风险线",
            "description": "聚焦高证据且存在风险的任务。",
            "calendarScope": "risk",
            "shareability": "private",
            "sortBy": "updatedAt",
            "sortDirection": "asc",
            "visibleFields": ["title", "priority", "businessCategory", "evidenceCount"],
            "filterSet": {
                "onlyWithEventLine": True,
                "onlyRisky": True,
                "minimumEvidenceCount": 2,
            },
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["name"] == "高证据风险线"
    assert updated_payload["calendarScope"] == "risk"
    assert updated_payload["sortDirection"] == "asc"
    assert updated_payload["filterSet"]["onlyRisky"] is True
    assert updated_payload["filterSet"]["minimumEvidenceCount"] == 2

    relisted = client.get("/api/v1/task-views")
    assert relisted.status_code == 200, relisted.text
    relisted_payload = relisted.json()
    custom_view = next(item for item in relisted_payload["views"] if item["id"] == created_payload["id"])
    assert custom_view["name"] == "高证据风险线"
    assert custom_view["description"] == "聚焦高证据且存在风险的任务。"


def test_task_context_preview_returns_bundle_and_judgment(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "CFFC")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "CFFC系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "战略陪伴中",
            "summary": "围绕 CFFC 的系统演示、合作判断和下一步行动持续推进。",
            "intent": "判断这次会谈是否能从关系动作收成业务结论。",
            "nextStep": "整理系统演示反馈，并确认会后动作。",
            "primaryClientId": client_id,
            "businessCategory": "业务扩展",
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    updated_event_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "currentBlocker": "这次会谈的目标和会后动作还没有被明确钉住。",
            "recentDecision": "先让对方理解系统与客户价值的关系，再决定是否继续扩大合作。",
            "nextStep": "把会谈结论压成一条明确判断和下一步动作。",
        },
    )
    assert updated_event_line.status_code == 200, updated_event_line.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "CFFC洪峰鸿鹄计划AI技术合作",
            "desc": "线下会谈，重点看数字化平台设计附件，并判断会后是否能进入下一轮合作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "CFFC数字化平台设计.md",
                "# 平台设计\n\n本次会谈重点确认数字化平台设计是否能服务基金会客户的深度价值。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text

    preview_response = client.get(f"/api/v1/tasks/{task_payload['id']}/context-preview")
    assert preview_response.status_code == 200, preview_response.text
    payload = preview_response.json()
    assert payload["taskId"] == task_payload["id"]
    assert payload["clientId"] == client_id
    assert payload["judgmentVersion"] == "event_line_judgment_v1"
    assert payload["bundleFingerprint"]
    assert payload["coverageScore"] >= 0
    assert payload["confidenceScore"] >= 0
    assert payload["safeOutputMode"] in {"needs_input", "summary_only", "full_judgment"}
    assert payload["publishState"] in {"local_preview", "publish_ready"}
    assert payload["contextBundle"]["eventLineId"] == event_line_id
    assert payload["contextBundle"]["lineName"] == "CFFC系统演示推进线"
    assert payload["contextBundle"]["attachmentCount"] >= 1
    assert payload["judgment"]["eventLineId"] == event_line_id
    assert payload["judgment"]["judgmentVersion"] == "event_line_judgment_v1"
    assert payload["judgment"]["bundleFingerprint"]
    assert payload["judgment"]["coverageScore"] >= 0
    assert payload["judgment"]["confidenceScore"] >= 0
    assert payload["judgment"]["safeOutputMode"] in {"needs_input", "summary_only", "full_judgment"}
    assert payload["judgment"]["publishState"] in {"local_preview", "publish_ready"}
    assert "CFFC" in payload["judgment"]["whatHappened"]
    assert "会谈" in payload["judgment"]["whatHappened"] or "系统" in payload["judgment"]["whatHappened"] or "推进" in payload["judgment"]["whatHappened"]
    assert payload["judgment"]["minimumAction"]
    assert payload["summaryChips"]
    assert payload["readiness"] in {"medium", "high"}


def test_review_dashboard_drill_target_returns_event_line_evidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "演示确认",
            "summary": "围绕系统演示、反馈和下一步合作判断持续推进。",
            "intent": "让关键联系人理解益语系统与合作目标的关系。",
            "nextStep": "补齐演示反馈并推进下一轮确认。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "演示系统并记录反馈，判断下一步合作方向。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示反馈.md",
                "# 演示反馈\n\n张真重点关注系统与组织现有协同流程的贴合度。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "event_line",
            "targetId": event_line_id,
            "targetLabel": "日慈系统演示推进线",
        },
    )
    assert drill.status_code == 200, drill.text
    payload = drill.json()
    assert payload["target"]["targetType"] == "event_line"
    assert payload["target"]["targetId"] == event_line_id
    assert payload["eventLineDetail"]["eventLine"]["id"] == event_line_id
    assert any(item["id"] == task_payload["id"] for item in payload["tasks"])
    assert any(item["documentId"] == attachment["documentId"] for item in payload["attachments"])
    assert payload["eventLineMemory"] is not None
    assert payload["eventLineMemory"]["confidence"] >= 0


def test_review_dashboard_drill_target_supports_meeting_and_attachment_group(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_meeting = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "日慈系统演示推进会"},
    )
    assert created_meeting.status_code == 200, created_meeting.text
    meeting_id = created_meeting.json()["meeting"]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟进日慈系统演示反馈",
            "desc": "根据会议演示反馈整理下一步动作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "sourceType": "meeting",
            "sourceId": meeting_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示纪要.md",
                "# 会议纪要\n\n后续需要把系统演示与组织现有流程衔接起来。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    meeting_drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "meeting",
            "targetId": meeting_id,
            "targetLabel": "日慈系统演示推进会",
        },
    )
    assert meeting_drill.status_code == 200, meeting_drill.text
    meeting_payload = meeting_drill.json()
    assert meeting_payload["meetings"][0]["id"] == meeting_id
    assert any(item["id"] == task_payload["id"] for item in meeting_payload["tasks"])
    assert any(item["id"] == attachment["id"] for item in meeting_payload["attachments"])

    attachment_drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "attachment_group",
            "targetId": f"attachment_group:{attachment['id']}",
            "targetLabel": attachment["title"],
            "targetFilters": json.dumps({"attachmentIds": [attachment["id"]], "taskIds": [task_payload["id"]]}),
        },
    )
    assert attachment_drill.status_code == 200, attachment_drill.text
    attachment_payload = attachment_drill.json()
    assert any(item["id"] == attachment["id"] for item in attachment_payload["attachments"])
    assert any(item["id"] == task_payload["id"] for item in attachment_payload["tasks"])


def test_review_dashboard_drill_target_supports_support_request(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "支持请求客户")

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "协调外部支持资源",
            "desc": "这条任务需要跨部门支持。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "支持说明.md",
                "需要额外资源支持来推进当前任务。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    client.app.state.app_state.db.set_setting("cloud_access_token", "test-token")

    def fake_httpx_request(method: str, url: str, **kwargs):
        parsed = httpx.URL(url)
        if method == "GET" and parsed.path == "/api/v1/support-requests":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "support_req_1",
                        "taskId": task_payload["id"],
                        "requesterUserId": "user_test",
                        "targetScope": "department",
                        "targetRefId": "dept_ops",
                        "requestType": "collaboration",
                        "urgency": "high",
                        "summary": "需要跨部门协作支持",
                        "status": "open",
                        "resolutionNote": "",
                        "createdAt": "2026-03-23T10:00:00",
                        "updatedAt": "2026-03-23T10:00:00",
                    }
                ],
            )
        if method == "GET" and parsed.path == "/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "lists": [
                        {
                            "id": task_payload["listId"],
                            "name": task_payload["listName"],
                            "color": task_payload["listColor"],
                            "sortOrder": 0,
                            "isDefault": True,
                        }
                    ],
                    "tasks": [
                        {
                            "id": task_payload["id"],
                            "title": task_payload["title"],
                            "description": task_payload["desc"],
                            "progressStatus": "todo",
                            "priority": task_payload["priority"],
                            "listId": task_payload["listId"],
                            "listName": task_payload["listName"],
                            "listColor": task_payload["listColor"],
                            "ownerName": task_payload["ownerName"],
                            "sourceType": task_payload["sourceType"],
                            "sourceId": task_payload["sourceId"],
                            "clientId": task_payload["clientId"],
                            "clientName": task_payload["clientName"],
                            "durationMinutes": task_payload["durationMinutes"],
                            "createdAt": task_payload["createdAt"],
                            "updatedAt": task_payload["updatedAt"],
                            "attachments": [],
                        }
                    ],
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(httpx, "request", fake_httpx_request)

    drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "support_request",
            "targetId": "support_req_1",
            "targetLabel": "需要跨部门协作支持",
        },
    )
    assert drill.status_code == 200, drill.text
    payload = drill.json()
    assert payload["supportRequests"][0]["id"] == "support_req_1"
    assert any(item["id"] == task_payload["id"] for item in payload["tasks"])
    assert any(item["id"] == attachment["id"] for item in payload["attachments"])


def test_review_dashboard_surfaces_cross_week_trend_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")
    operator_id = client.app.state.app_state.db.get_setting("current_operator_id", "") or "op_qh"

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "stage": "演示确认",
            "primaryClientId": client_id,
            "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
            "nextStep": "先确认演示目标，再补齐下一轮动作。",
            "recentDecision": "先看系统，再判断是否进入深度合作。",
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "演示系统并判断下一步合作方向。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
            "dueDate": "2026-03-19",
            "businessCategory": "业务扩展",
            "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
            "nextAction": "整理确认问题后再约下一轮演示。",
            "recentDecision": "先做系统演示，再决定合作深度。",
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, 'task.update', 'task', ?, ?, ?)
        """,
        (
            "log_due_1",
            "本地用户",
            task_id,
            json.dumps({"dueDate": "2026-03-12"}, ensure_ascii=False),
            "2026-03-05T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, 'task.update', 'task', ?, ?, ?)
        """,
        (
            "log_due_2",
            "本地用户",
            task_id,
            json.dumps({"dueDate": "2026-03-19"}, ensure_ascii=False),
            "2026-03-12T10:00:00",
        ),
    )

    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at
        ) VALUES(?, '2026-W11', ?, '', '', '', '', ?, ?)
        """,
        ("review_prev", operator_id, "2026-03-08T09:00:00", "2026-03-08T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W11', 'work', ?, ?, ?, ?, ?, ?)
        """,
        (
            "entry_prev",
            "review_prev",
            task_id,
            "上一周已经卡在客户确认和支持依赖上。",
            json.dumps(
                {
                    "lightweightTag": "资源不够",
                    "supportNeeded": "需要客户关键人进一步确认演示目标。",
                    "blockerReason": "客户真实需求与系统演示范围还没对齐。",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "id": task_id,
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "eventLineId": event_line_id,
                    "listName": "收集箱",
                    "listColor": "#EEF2FF",
                    "orgContext": {"needsReview": True},
                    "eventLineContext": {
                        "id": event_line_id,
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-08T09:00:00",
            "2026-03-08T09:00:00",
            "2026-03-08T09:00:00",
        ),
    )

    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at
        ) VALUES(?, '2026-W12', ?, '', '', '', '', ?, ?)
        """,
        ("review_current", operator_id, "2026-03-19T10:00:00", "2026-03-19T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, ?, ?, ?, ?, ?)
        """,
        (
            "entry_current",
            "review_current",
            task_id,
            "这周仍然卡在确认链上，还需要客户侧继续对齐。",
            json.dumps(
                {
                    "lightweightTag": "资源不够",
                    "supportNeeded": "还需要客户关键人给出演示边界确认。",
                    "blockerReason": "客户真实需求与系统演示范围还没对齐。",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "id": task_id,
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "eventLineId": event_line_id,
                    "listName": "收集箱",
                    "listColor": "#EEF2FF",
                    "orgContext": {"needsReview": True},
                    "eventLineContext": {
                        "id": event_line_id,
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-19T10:00:00",
            "2026-03-19T10:00:00",
            "2026-03-19T10:00:00",
        ),
    )

    review_response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert review_response.status_code == 200, review_response.text
    payload = review_response.json()
    trend_signals = payload["workAnalysis"]["trendSignals"]
    signal_types = {item["signalType"] for item in trend_signals}
    assert "repeat_reschedule" in signal_types
    assert "repeat_review_pending" in signal_types
    assert "repeat_support_request" in signal_types
    assert "escalating_blocker" in signal_types

    reschedule_signal = next(item for item in trend_signals if item["signalType"] == "repeat_reschedule")
    assert task_id in reschedule_signal["relatedTaskIds"]
    assert reschedule_signal["windowLabel"] == "连续 2-3 周"


def test_memory_backfill_route_upgrades_legacy_tasks_and_reviews(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "旧任务回填客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_legacy",
            "旧事件线",
            "资料补齐",
            "围绕旧资料和旧任务继续推进。",
            "把历史任务串成稳定推进线。",
            "客户真实阻塞还没写清。",
            "先补会议纪要。",
            "先补会议纪要并回收到同一条推进线上。",
            "legacy-owner",
            client_id,
            "旧任务回填客户",
            "2026-03-01T10:00:00",
            "2026-03-01T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', ?, ?, ?, NULL, NULL, '本周', NULL, 60, '旧负责人', 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (
            "task_legacy",
            "整理旧项目资料",
            "把历史会议纪要和关键判断补齐到同一条推进线上。",
            app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID,
            client_id,
            "eline_legacy",
            "2026-03-12T10:00:00",
            "2026-03-12T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W11', '', '', '', '', ?, ?)
        """,
        ("review_legacy", "2026-03-02T10:00:00", "2026-03-02T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W11', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_legacy",
            "review_legacy",
            "task_legacy",
            "这条旧任务已经暴露出客户真实阻塞仍未被说清。",
            json.dumps(
                {
                    "id": "task_legacy",
                    "title": "整理旧项目资料",
                    "status": "doing",
                    "eventLineId": "eline_legacy",
                    "clientId": client_id,
                    "listName": "收集箱",
                    "ownerName": "旧负责人",
                    "tags": [],
                }
            ),
            "2026-03-02T10:00:00",
            "2026-03-02T10:00:00",
            "2026-03-02T10:00:00",
        ),
    )

    response = client.post("/api/v1/memory/backfill")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["taskFactsBackfilled"] >= 1
    assert payload["reviewSignalsBackfilled"] >= 1
    assert payload["eventLineSnapshotsRefreshed"] >= 1
    assert payload["notebooksRefreshed"] >= 1

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task = next(item for item in board.json()["tasks"] if item["id"] == "task_legacy")
    assert task["memoryHints"]
    assert task["backgroundReadiness"]["backgroundSources"]

    reviews = client.get("/api/v1/reviews", params={"weekLabel": "2026-W11"})
    assert reviews.status_code == 200, reviews.text
    review_summary = reviews.json()["workAnalysis"]["eventLineSummaries"][0]
    assert review_summary["eventLineId"] == "eline_legacy"
    assert review_summary["memoryConfidence"] > 0
    if review_summary.get("backgroundSources"):
        assert any(source in {"事件线记忆", "event_line_memory"} for source in review_summary["backgroundSources"])


def test_weekly_review_analysis_ignores_polluted_event_line_background(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "周判断清洗客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_dirty_review",
            "向光奖马翔宇老师介绍数字化系统",
            "关系推进",
            "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
            '{"prompt":"你将作为深度研究 + 机构与项目运营写作综合体"}',
            "当前没有特别突出的阻塞，但仍需盯住推进收束。",
            "执行摘要：继续推进介绍。",
            "建议先明确这一阶段的核心事项。",
            "review-owner",
            client_id,
            "周判断清洗客户",
            "2026-03-21T10:00:00",
            "2026-03-21T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', ?, ?, ?, NULL, NULL, '本周', NULL, 60, '顾源源', 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (
            "task_dirty_review",
            "向马翔宇老师介绍数字化系统",
            "先把系统价值讲清楚，再推进后续判断。",
            app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID,
            client_id,
            "eline_dirty_review",
            "2026-03-21T10:00:00",
            "2026-03-21T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W12', '', '', '', '', ?, ?)
        """,
        ("review_dirty", "2026-03-22T10:00:00", "2026-03-22T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_dirty",
            "review_dirty",
            "task_dirty_review",
            "这周已经完成第一次介绍，但还需要继续推进下次沟通。",
            json.dumps(
                {
                    "id": "task_dirty_review",
                    "title": "向马翔宇老师介绍数字化系统",
                    "status": "doing",
                    "eventLineId": "eline_dirty_review",
                    "clientId": client_id,
                    "listName": "收集箱",
                    "eventLineContext": {
                        "id": "eline_dirty_review",
                        "name": "向光奖马翔宇老师介绍数字化系统",
                        "summary": "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
                        "intent": '{"prompt":"你将作为深度研究 + 机构与项目运营写作综合体"}',
                        "currentBlocker": "当前没有特别突出的阻塞，但仍需盯住推进收束。",
                        "recentDecision": "最近线索：正文 益语2026一季度计划 传统战略咨询这个品类正在收缩。",
                        "nextStep": "建议先明确这一阶段的核心事项。",
                    },
                    "projectContext": {
                        "currentFocus": "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。"
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-22T10:00:00",
            "2026-03-22T10:00:00",
            "2026-03-22T10:00:00",
        ),
    )

    response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert response.status_code == 200, response.text
    summary = next(
        item
        for item in response.json()["workAnalysis"]["eventLineSummaries"]
        if item["eventLineId"] == "eline_dirty_review"
    )
    assert '{"prompt"' not in summary["whatThisLineIs"]
    assert "执行摘要" not in summary["whatThisLineIs"]
    assert '{"prompt"' not in summary["whatHappenedThisWeek"]
    assert "执行摘要" not in summary["whatHappenedThisWeek"]
    assert "最近线索：" not in summary["whatHappenedThisWeek"]
    assert "向马翔宇老师介绍数字化系统" in summary["whatHappenedThisWeek"]


def test_reviews_route_accepts_notebook_and_event_line_memory_evidence_refs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "周复盘证据来源客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO organization_notebook_snapshots(
            id, client_id, organization_intro, collaboration_relationship, current_stage,
            business_modules_json, key_people_json, key_products_json, current_challenges_json,
            collaboration_goals_json, recent_facts_json, information_gaps_json, confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, '[]', ?, ?, '[]', ?, ?, '[]', 0.92, ?, ?)
        """,
        (
            "notebook_review_sources",
            client_id,
            "该机构正在推进数字化合作验证。",
            "当前与益语处于方案共创与会谈推进阶段。",
            "推进中",
            json.dumps(["张真"], ensure_ascii=False),
            json.dumps(["益语系统"], ensure_ascii=False),
            json.dumps(["本周已完成第一次系统介绍"], ensure_ascii=False),
            json.dumps(["明确系统演示后的合作判断"], ensure_ascii=False),
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, business_category, stage, summary, intent, current_blocker, recent_decision, next_step, evidence_count,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, ?, 3, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_review_sources",
            "日慈系统演示推进线",
            "业务扩展",
            "推进中",
            "围绕系统演示与合作判断继续推进。",
            "把系统演示收束成下一步合作动作。",
            "客户还没有明确会后判断边界。",
            "本周已经完成第一次系统演示。",
            "会后收齐关键反馈，并判断是否进入下一轮。",
            "顾源源",
            client_id,
            "周复盘证据来源客户",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO event_line_memory_snapshots(
            id, event_line_id, line_name, current_stage, current_work, current_blocker, recent_decision, next_step,
            evidence_refs_json, clarification_needs_json, analysis_signals_json, prediction_readiness, confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', 0.72, 0.88, ?, ?)
        """,
        (
            "eline_memory_review_sources",
            "eline_review_sources",
            "日慈系统演示推进线",
            "推进中",
            "本周重点是完成系统介绍并确认合作目标。",
            "客户真实需求与演示范围还需对齐。",
            "已经完成第一轮介绍，等待会后反馈。",
            "整理会后问题并形成合作判断。",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', ?, ?, ?, NULL, NULL, '本周', NULL, 60, '顾源源', 'meeting', 'meeting_demo_1', '[]', '[]', ?, ?)
        """,
        (
            "task_review_sources",
            "给日慈张真看益语系统",
            "这次会谈要确认系统与对方合作目标的关系，并收齐会后动作。",
            app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID,
            client_id,
            "eline_review_sources",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W12', '', '', '', '', ?, ?)
        """,
        ("review_sources", "2026-03-24T09:00:00", "2026-03-24T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_sources",
            "review_sources",
            "task_review_sources",
            "这周已完成系统介绍，仍需用会后反馈确认下一轮合作动作。",
            json.dumps(
                {
                    "id": "task_review_sources",
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "clientId": client_id,
                    "eventLineId": "eline_review_sources",
                    "listName": "收集箱",
                    "eventLineContext": {
                        "id": "eline_review_sources",
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与演示范围还需对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )

    response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload["workAnalysis"], dict)
    assert "eventLineSummaries" in payload["workAnalysis"]


def test_cloud_task_board_builds_event_line_shadow_and_memory_hints(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)

    tasks_payload = {
        "tasks": [
            {
                "id": "cloud_task_1",
                "title": "推进飞书会议联调",
                "description": "跟进授权回调和会议按钮联通情况。",
                "status": "doing",
                "priority": "high",
                "listId": "list-1",
                "listName": "客户项目",
                "listColor": "#5B7BFE",
                "eventLineId": "eline_cloud_shadow",
                "eventLineName": "飞书会议联调",
                "ownerName": "顾源源",
                "sourceType": "manual",
                "createdAt": "2026-03-20T09:00:00",
                "updatedAt": "2026-03-22T09:30:00",
                "collaborators": [],
            }
        ],
        "lists": [
            {"id": "list-1", "name": "客户项目", "color": "#5B7BFE", "sortOrder": 1, "isDefault": False}
        ],
        "tags": [],
    }

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(200, json=tasks_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/employees/directory":
            return httpx.Response(200, json=[])
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines/eline_cloud_shadow":
            return httpx.Response(
                200,
                json={
                    "eventLine": {
                        "id": "eline_cloud_shadow",
                        "name": "飞书会议联调",
                        "kind": "custom",
                        "status": "active",
                        "stage": "推进中",
                        "summary": "当前集中处理飞书授权回调和会议按钮闭环。",
                        "currentBlocker": "redirect URI 仍需和应用后台配置对齐。",
                        "recentDecision": "先完成回调链，再验证会议发起。",
                        "nextStep": "逐项验证授权回调、绑定状态和会议发起。",
                        "evidenceCount": 3,
                    }
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task = board.json()["tasks"][0]
    assert task["eventLineId"] == "eline_cloud_shadow"
    assert task["backgroundReadiness"]["level"] in {"medium", "high"}
    assert "event_line_memory" in task["backgroundReadiness"]["backgroundSources"]
    assert task["memoryHints"]

    shadow_row = client.app.state.app_state.db.fetchone(
        "SELECT id, name FROM event_lines WHERE id = ?",
        ("eline_cloud_shadow",),
    )
    assert shadow_row is not None

    memory_response = client.get("/api/v1/event-lines/eline_cloud_shadow/memory")
    assert memory_response.status_code == 200, memory_response.text
    snapshot = memory_response.json()["eventLineMemorySnapshot"]
    assert snapshot is not None
    assert snapshot["confidence"] > 0


def test_bootstrap_local_cloud_snapshot_pulls_event_lines(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_session_user(client)
    seed_cloud_token(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-lists":
            return httpx.Response(
                200,
                json={
                    "lists": [
                        {"id": "list_bootstrap_1", "name": "启动清单", "color": "#5B7BFE", "sortOrder": 1, "isDefault": False}
                    ]
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-tags":
            return httpx.Response(200, json={"tags": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [
                        {
                            "id": "task_bootstrap_1",
                            "title": "跟进事件线冷启动快照",
                            "description": "验证任务面板启动时会补齐事件线本地缓存。",
                            "status": "doing",
                            "priority": "high",
                            "listId": "list_bootstrap_1",
                            "creatorId": "user_emp",
                            "ownerId": "user_emp",
                            "ownerName": "普通员工",
                            "sourceType": "manual",
                            "eventLineId": "eline_bootstrap_1",
                            "createdAt": "2026-04-21T09:00:00",
                            "updatedAt": "2026-04-21T09:10:00",
                            "collaborators": [],
                        }
                    ]
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "eline_bootstrap_1",
                        "name": "冷启动事件线",
                        "kind": "custom",
                        "status": "active",
                        "updatedAt": "2026-04-21T09:15:00",
                    }
                ],
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines/eline_bootstrap_1":
            return httpx.Response(
                200,
                json={
                    "eventLine": {
                        "id": "eline_bootstrap_1",
                        "name": "冷启动事件线",
                        "kind": "custom",
                        "status": "active",
                        "stage": "推进中",
                        "summary": "验证启动时事件线能进本地缓存。",
                        "updatedAt": "2026-04-21T09:15:00",
                    },
                    "activities": [],
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-group-templates":
            return httpx.Response(200, json={"templates": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/reviews/history":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    payload = board.json()
    assert payload["tasks"][0]["eventLineId"] == "eline_bootstrap_1"
    assert payload["tasks"][0]["eventLineName"] == "冷启动事件线"

    event_line_row = client.app.state.app_state.db.fetchone(
        "SELECT id, name FROM event_lines WHERE id = ?",
        ("eline_bootstrap_1",),
    )
    assert event_line_row is not None
    assert event_line_row["name"] == "冷启动事件线"


def test_background_local_cloud_sync_isolates_failed_bucket(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    seed_cloud_token(client)
    client.app.state.app_state.db.set_setting("local_cloud_sync_last_success_at", "2026-04-21T09:00:00")
    client.app.state.app_state.db.set_setting("local_cloud_sync_snapshot_user_id", session_user["id"])
    client.app.state.app_state.db.set_setting("local_cloud_sync_snapshot_org_id", session_user["organizationId"])
    app_main._local_cloud_sync_runtime["last_started_at"] = 0.0
    app_main._local_cloud_sync_runtime["running"] = False

    sync_errors: list[Exception] = []

    class ImmediateThread:
        def __init__(self, *, target=None, daemon=None, **kwargs):
            self._target = target
            self.daemon = daemon

        def start(self):
            try:
                if self._target:
                    self._target()
            except Exception as exc:  # pragma: no cover - assertion aid
                sync_errors.append(exc)

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-lists":
            return httpx.Response(
                200,
                json={
                    "lists": [
                        {"id": "list_sync_1", "name": "同步清单", "color": "#4F46E5", "sortOrder": 1, "isDefault": False}
                    ]
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-tags":
            return httpx.Response(200, json={"tags": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [
                        {
                            "id": "task_sync_1",
                            "title": "同步时保住任务清单",
                            "description": "即便事件线接口失败，也不能让任务和清单一起消失。",
                            "status": "todo",
                            "priority": "normal",
                            "listId": "list_sync_1",
                            "creatorId": "user_emp",
                            "ownerId": "user_emp",
                            "ownerName": "普通员工",
                            "sourceType": "manual",
                            "createdAt": "2026-04-21T10:00:00",
                            "updatedAt": "2026-04-21T10:05:00",
                            "collaborators": [],
                        }
                    ]
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines":
            return httpx.Response(503, json={"detail": "event line service unavailable"})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-group-templates":
            return httpx.Response(200, json={"templates": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/reviews/history":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main, "Thread", ImmediateThread)
    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    assert sync_errors == []

    list_row = client.app.state.app_state.db.fetchone(
        "SELECT id, name FROM task_lists WHERE id = ?",
        ("list_sync_1",),
    )
    assert list_row is not None
    task_row = client.app.state.app_state.db.fetchone(
        "SELECT id, title FROM tasks WHERE id = ?",
        ("task_sync_1",),
    )
    assert task_row is not None
    assert client.app.state.app_state.db.get_setting("local_cloud_sync.event_lines.last_error", "")


def test_reject_task_local_fallback_returns_rejected_task(tmp_path: Path):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    list_id = board.json()["lists"][0]["id"]
    seed_cloud_token(client)

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "本地退回任务",
            "desc": "验证 reject 的本地分支不会再丢失。",
            "listId": list_id,
            "sourceType": "manual",
            "ownerId": session_user["id"],
            "ownerName": session_user["fullName"],
            "collaboratorIds": [session_user["id"]],
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    rejected = client.post(
        f"/api/v1/tasks/{task_id}/reject",
        json={"reason": "当前资源不足，先退回补充信息。"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    collaborator_row = client.app.state.app_state.db.fetchone(
        "SELECT inbox_status, return_reason FROM task_collaborators WHERE task_id = ? AND user_id = ?",
        (task_id, session_user["id"]),
    )
    assert collaborator_row is not None
    assert collaborator_row["inbox_status"] == "returned"
    assert collaborator_row["return_reason"] == "当前资源不足，先退回补充信息。"


def test_confirm_task_local_fallback_returns_task_for_pending_collaborator(tmp_path: Path):
    client = make_client(tmp_path)
    creator_user = seed_session_user(
        client,
        user_id="user_creator",
        email="creator@example.com",
        full_name="普通发起人",
    )
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    list_id = board.json()["lists"][0]["id"]

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "协作待确认任务",
            "desc": "验证普通协作者在本地确认后不会再丢任务。",
            "listId": list_id,
            "sourceType": "manual",
            "ownerId": creator_user["id"],
            "ownerName": creator_user["fullName"],
            "collaboratorIds": [creator_user["id"], "user_collab"],
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    db = client.app.state.app_state.db
    db.conn.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute("UPDATE tasks SET list_id = 'list-0' WHERE id = ?", (task_id,))
    finally:
        db.conn.execute("PRAGMA foreign_keys = ON")

    collaborator_user = seed_session_user(
        client,
        user_id="user_collab",
        email="collab@example.com",
        full_name="普通协作者",
    )

    confirmed = client.post(f"/api/v1/tasks/{task_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["status"] == "doing"
    assert payload["listId"] == app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID
    assert payload["viewerInboxStatus"] == "accepted"

    collaborator_row = db.fetchone(
        "SELECT inbox_status FROM task_collaborators WHERE task_id = ? AND user_id = ?",
        (task_id, collaborator_user["id"]),
    )
    assert collaborator_row is not None
    assert collaborator_row["inbox_status"] == "accepted"


def test_mark_event_line_notification_read_queues_local_sync(tmp_path: Path):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    insert_local_event_line_notification(
        client,
        notification_id="notif_local_single",
        user=session_user,
        other_user_ids=[("user_other", "其他成员", "other@example.com")],
    )

    inbox_before = client.get("/api/v1/inbox/notifications")
    assert inbox_before.status_code == 200, inbox_before.text
    assert [item["id"] for item in inbox_before.json()["notifications"]] == ["notif_local_single"]

    marked = client.post("/api/v1/inbox/notifications/notif_local_single/read")
    assert marked.status_code == 200, marked.text
    assert marked.json()["id"] == "notif_local_single"
    assert marked.json()["viewerReadAt"]

    notification_row = client.app.state.app_state.db.fetchone(
        "SELECT sync_status, pending_sync_action FROM event_line_notifications WHERE id = ?",
        ("notif_local_single",),
    )
    assert notification_row is not None
    assert notification_row["sync_status"] == "queued"
    assert notification_row["pending_sync_action"] == "read"

    receipt_row = client.app.state.app_state.db.fetchone(
        "SELECT read_at FROM event_line_notification_receipts WHERE notification_id = ? AND user_id = ?",
        ("notif_local_single", session_user["id"]),
    )
    assert receipt_row is not None
    assert receipt_row["read_at"]

    inbox_after = client.get("/api/v1/inbox/notifications")
    assert inbox_after.status_code == 200, inbox_after.text
    assert inbox_after.json()["notifications"] == []


def test_mark_event_line_notifications_read_batch_queues_local_sync(tmp_path: Path):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    notification_ids = ["notif_local_batch_1", "notif_local_batch_2"]
    for index, notification_id in enumerate(notification_ids, start=1):
        insert_local_event_line_notification(
            client,
            notification_id=notification_id,
            user=session_user,
            event_line_id=f"line_batch_{index}",
            title=f"批量系统通知 {index}",
            other_user_ids=[(f"user_other_{index}", f"其他成员{index}", f"other{index}@example.com")],
        )

    marked = client.post("/api/v1/inbox/notifications/read-batch", json={"notificationIds": notification_ids})
    assert marked.status_code == 200, marked.text
    payload = marked.json()
    assert payload["updatedCount"] == 2
    assert payload["notificationIds"] == notification_ids

    rows = client.app.state.app_state.db.fetchall(
        "SELECT id, sync_status, pending_sync_action FROM event_line_notifications WHERE id IN (?, ?) ORDER BY created_at ASC",
        (notification_ids[0], notification_ids[1]),
    )
    assert len(rows) == 2
    for row in rows:
        assert row["sync_status"] == "queued"
        assert row["pending_sync_action"] == "read"

    unread_rows = client.app.state.app_state.db.fetchall(
        "SELECT notification_id, read_at FROM event_line_notification_receipts WHERE user_id = ? ORDER BY notification_id ASC",
        (session_user["id"],),
    )
    assert len(unread_rows) == 2
    assert all(row["read_at"] for row in unread_rows)

    inbox_after = client.get("/api/v1/inbox/notifications")
    assert inbox_after.status_code == 200, inbox_after.text
    assert inbox_after.json()["notifications"] == []


def test_task_board_preserves_empty_list_from_cloud_payload(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    seed_cloud_token(client)
    app_main._local_cloud_sync_runtime["last_started_at"] = 0.0
    app_main._local_cloud_sync_runtime["running"] = False

    class ImmediateThread:
        def __init__(self, *, target=None, daemon=None, **kwargs):
            self._target = target
            self.daemon = daemon

        def start(self):
            if self._target:
                self._target()

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-lists":
            return httpx.Response(200, json={"lists": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-tags":
            return httpx.Response(200, json={"tags": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [
                        {
                            "id": "task_cloud_no_list",
                            "title": "云端无清单任务",
                            "description": "不应被回退成默认清单。",
                            "status": "todo",
                            "priority": "normal",
                            "listId": "",
                            "listName": "",
                            "listColor": "",
                            "listIds": [],
                            "listNames": [],
                            "creatorId": session_user["id"],
                            "creatorName": session_user["fullName"],
                            "ownerId": session_user["id"],
                            "ownerName": session_user["fullName"],
                            "sourceType": "manual",
                            "createdAt": "2026-04-23T10:00:00",
                            "updatedAt": "2026-04-23T10:05:00",
                            "collaborators": [],
                        }
                    ]
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines":
            return httpx.Response(200, json={"eventLines": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/task-group-templates":
            return httpx.Response(200, json={"templates": []})
        if method.upper() == "GET" and url == f"{normalized}/api/v1/reviews/history":
            return httpx.Response(200, json={"items": []})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main, "Thread", ImmediateThread)
    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    payload = board.json()
    assert len(payload["tasks"]) == 1
    task = payload["tasks"][0]
    assert task["listId"] == ""
    assert task["listName"] == ""
    assert task["listNames"] == []


def test_inbox_aggregate_preserves_cloud_collaboration_display_fields(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    default_list_id = app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID
    session_user = seed_session_user(
        client,
        user_id="user_admin",
        email="admin@example.com",
        full_name="系统管理员",
        primary_role="admin",
    )
    seed_cloud_token(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [],
                    "lists": [
                        {
                            "id": default_list_id,
                            "name": "客户项目",
                            "color": "#5B7BFE",
                            "sortOrder": 0,
                            "isDefault": True,
                            "scope": "org",
                        }
                    ],
                    "tags": [],
                    "commonTags": [],
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/inbox":
            return httpx.Response(
                200,
                json={
                    "pendingTasks": [
                        {
                            "id": "task_cloud_pending_display",
                            "title": "云端待确认任务",
                            "description": "验证本地桥接保留协作展示字段。",
                            "status": "inbox",
                            "progressStatus": "todo",
                            "priority": "normal",
                            "listId": default_list_id,
                            "listName": "客户项目",
                            "listColor": "#5B7BFE",
                            "listIds": [default_list_id],
                            "listNames": ["客户项目"],
                            "creatorId": "user_qinghua",
                            "creatorName": "清华",
                            "creatorDisplayName": "清华",
                            "ownerId": session_user["id"],
                            "ownerName": session_user["fullName"],
                            "ownerDisplayName": session_user["fullName"],
                            "sourceType": "manual",
                            "collaborators": [
                                {
                                    "userId": session_user["id"],
                                    "fullName": session_user["fullName"],
                                    "email": session_user["email"],
                                    "orderIndex": 0,
                                    "isOwner": True,
                                    "inboxStatus": "pending",
                                },
                                {
                                    "userId": "user_qinghua",
                                    "fullName": "清华",
                                    "email": "qinghua@example.com",
                                    "orderIndex": 1,
                                    "isOwner": False,
                                    "inboxStatus": "accepted",
                                },
                            ],
                            "collaborationSummary": {"pending": 1, "accepted": 1, "returned": 0},
                            "pendingParticipantNames": [session_user["fullName"]],
                            "viewerInboxStatus": "pending",
                            "viewerCanConfirm": True,
                            "viewerCanReject": True,
                            "createdAt": "2026-04-23T10:00:00",
                            "updatedAt": "2026-04-23T10:05:00",
                        }
                    ],
                    "systemNotifications": [],
                    "outboundPendingTasks": [],
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    inbox = client.get("/api/v1/inbox")
    assert inbox.status_code == 200, inbox.text
    payload = inbox.json()
    assert len(payload["pendingTasks"]) == 1
    task = payload["pendingTasks"][0]
    assert task["creatorDisplayName"] == "清华"
    assert task["ownerDisplayName"] == session_user["fullName"]
    assert task["pendingParticipantNames"] == [session_user["fullName"]]
    assert task["viewerInboxStatus"] == "pending"
    assert task["viewerCanConfirm"] is True
    assert task["viewerCanReject"] is True


def test_cloud_inbox_merges_board_pending_when_cloud_inbox_omits_task(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    default_list_id = app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID
    session_user = seed_session_user(
        client,
        user_id="user_receiver",
        email="receiver@example.com",
        full_name="接收人",
    )
    seed_cloud_token(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/inbox":
            return httpx.Response(
                200,
                json={"pendingTasks": [], "systemNotifications": [], "outboundPendingTasks": []},
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [
                        {
                            "id": "task_board_pending_only",
                            "title": "看板里仍待我确认的任务",
                            "description": "云端 inbox 漏掉时，本地桥接应从任务看板补回。",
                            "status": "todo",
                            "progressStatus": "todo",
                            "priority": "normal",
                            "listId": default_list_id,
                            "listName": "客户项目",
                            "listColor": "#5B7BFE",
                            "listIds": [default_list_id],
                            "listNames": ["客户项目"],
                            "creatorId": "user_creator",
                            "creatorName": "发起人",
                            "ownerId": session_user["id"],
                            "ownerName": session_user["fullName"],
                            "sourceType": "manual",
                            "collaborators": [
                                {
                                    "userId": session_user["id"],
                                    "fullName": session_user["fullName"],
                                    "email": session_user["email"],
                                    "orderIndex": 0,
                                    "isOwner": True,
                                    "inboxStatus": "pending",
                                }
                            ],
                            "collaborationSummary": {"pending": 1, "accepted": 0, "returned": 0},
                            "createdAt": "2026-04-24T08:00:00",
                            "updatedAt": "2026-04-24T08:05:00",
                        }
                    ],
                    "lists": [
                        {
                            "id": default_list_id,
                            "name": "客户项目",
                            "color": "#5B7BFE",
                            "sortOrder": 0,
                            "isDefault": True,
                            "scope": "org",
                        }
                    ],
                    "tags": [],
                    "commonTags": [],
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    inbox = client.get("/api/v1/inbox")
    assert inbox.status_code == 200, inbox.text
    payload = inbox.json()
    assert [task["id"] for task in payload["pendingTasks"]] == ["task_board_pending_only"]
    assert payload["pendingTasks"][0]["viewerInboxStatus"] == "pending"
    assert payload["pendingTasks"][0]["viewerCanConfirm"] is True


def test_inbox_upsert_preserves_pending_local_empty_list_from_stale_default_payload(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    default_list_id = app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID
    session_user = seed_session_user(
        client,
        user_id="user_creator",
        email="creator@example.com",
        full_name="发起人",
    )
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "清单清空后不应被客户项目回灌",
            "desc": "本地已明确保存为无清单。",
            "priority": "normal",
            "listId": "",
            "listIds": [],
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    db = client.app.state.app_state.db
    db.execute("DELETE FROM task_list_links WHERE task_id = ?", (task_id,))
    db.execute(
        """
        UPDATE tasks
        SET list_id = NULL,
            updated_at = '2026-04-24T12:00:00',
            sync_status = 'queued',
            pending_sync_action = 'update',
            last_synced_at = '2026-04-24T11:00:00',
            last_cloud_version = '2026-04-24T11:30:00'
        WHERE id = ?
        """,
        (task_id,),
    )
    seed_cloud_token(client)

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "tasks": [],
                    "lists": [
                        {
                            "id": default_list_id,
                            "name": "客户项目",
                            "color": "#5B7BFE",
                            "sortOrder": 0,
                            "isDefault": True,
                            "scope": "org",
                        }
                    ],
                    "tags": [],
                    "commonTags": [],
                },
            )
        if method.upper() == "GET" and url == f"{normalized}/api/v1/inbox":
            return httpx.Response(
                200,
                json={
                    "pendingTasks": [],
                    "systemNotifications": [],
                    "outboundPendingTasks": [
                        {
                            "id": task_id,
                            "title": "清单清空后不应被客户项目回灌",
                            "description": "云端旧快照仍带默认清单。",
                            "status": "todo",
                            "progressStatus": "todo",
                            "priority": "normal",
                            "listId": default_list_id,
                            "listName": "客户项目",
                            "listColor": "#5B7BFE",
                            "listIds": [default_list_id],
                            "listNames": ["客户项目"],
                            "creatorId": session_user["id"],
                            "creatorName": session_user["fullName"],
                            "ownerId": "",
                            "ownerName": "",
                            "sourceType": "manual",
                            "collaborators": [
                                {
                                    "userId": "user_owner",
                                    "fullName": "负责人",
                                    "email": "owner@example.com",
                                    "orderIndex": 0,
                                    "isOwner": True,
                                    "inboxStatus": "pending",
                                }
                            ],
                            "collaborationSummary": {"pending": 1, "accepted": 0, "returned": 0},
                            "createdAt": "2026-04-24T09:00:00",
                            "updatedAt": "2026-04-24T11:30:00",
                        }
                    ],
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    inbox = client.get("/api/v1/inbox")
    assert inbox.status_code == 200, inbox.text
    local_row = db.fetchone("SELECT list_id, sync_status, pending_sync_action FROM tasks WHERE id = ?", (task_id,))
    assert local_row["list_id"] is None
    assert local_row["sync_status"] == "queued"
    assert local_row["pending_sync_action"] == "update"
    links = db.fetchall("SELECT list_id FROM task_list_links WHERE task_id = ?", (task_id,))
    assert links == []


def test_task_can_be_created_without_any_list_locally(tmp_path: Path):
    client = make_client(tmp_path)

    settings = client.get("/api/v1/settings/tasks")
    assert settings.status_code == 200, settings.text
    assert settings.json()["defaultListId"] is None

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "本地无清单任务",
            "desc": "保存后保持无清单。",
            "priority": "normal",
            "listId": "",
            "listIds": [],
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["listId"] == ""
    assert payload["listName"] == ""
    assert payload["listIds"] == []
    assert payload["listNames"] == []

    default_list_id = app_main.DEFAULT_LOCAL_ORG_TASK_LIST_ID
    set_default = client.post("/api/v1/settings/tasks", json={"defaultListId": default_list_id})
    assert set_default.status_code == 200, set_default.text
    assert set_default.json()["defaultListId"] == default_list_id
    clear_default = client.post("/api/v1/settings/tasks", json={"defaultListId": None})
    assert clear_default.status_code == 200, clear_default.text
    assert clear_default.json()["defaultListId"] is None


def test_task_board_excludes_legacy_event_line_notification_rows(tmp_path: Path):
    client = make_client(tmp_path)
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    list_id = board.json()["lists"][0]["id"]
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "遗留事件线通知任务",
            "desc": "这条任务会被改造成遗留通知记录。",
            "priority": "normal",
            "listId": list_id,
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    client.app.state.app_state.db.execute(
        "UPDATE tasks SET source_type = 'event_line_notification', progress_status = 'inbox' WHERE id = ?",
        (task_id,),
    )

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    visible_ids = {task["id"] for task in board.json()["tasks"]}
    assert task_id not in visible_ids


def test_collaboration_inbox_cleans_legacy_notification_tasks_and_returns_notifications(tmp_path: Path):
    client = make_client(tmp_path)
    session_user = seed_session_user(client)
    insert_local_event_line_notification(
        client,
        notification_id="notif_inbox_aggregate",
        user=session_user,
    )
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    list_id = board.json()["lists"][0]["id"]
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "聚合收件箱不应显示的旧通知任务",
            "desc": "这条旧任务形态应被收件箱清掉。",
            "priority": "normal",
            "listId": list_id,
        },
    )
    assert created.status_code == 200, created.text
    legacy_task_id = created.json()["id"]
    client.app.state.app_state.db.execute(
        "UPDATE tasks SET source_type = 'event_line_notification', progress_status = 'inbox' WHERE id = ?",
        (legacy_task_id,),
    )

    inbox = client.get("/api/v1/inbox")
    assert inbox.status_code == 200, inbox.text
    payload = inbox.json()
    assert payload["pendingTasks"] == []
    assert [item["id"] for item in payload["systemNotifications"]] == ["notif_inbox_aggregate"]
    assert payload["outboundPendingTasks"] == []

    legacy_row = client.app.state.app_state.db.fetchone(
        "SELECT id FROM tasks WHERE id = ?",
        (legacy_task_id,),
    )
    assert legacy_row is None


def test_employee_can_edit_business_settings_but_not_sensitive_settings(tmp_path: Path):
    client = make_client(tmp_path)
    client.app.state.app_state.db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "user_emp",
                "organizationId": "org_1",
                "email": "employee@example.com",
                "fullName": "普通员工",
                "primaryRole": "employee",
                "accountStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    topics_updated = client.post(
        "/api/v1/settings/topics",
        json={"defaultTimeRange": "14_days"},
    )
    assert topics_updated.status_code == 200
    assert topics_updated.json()["defaultTimeRange"] == "14_days"

    sensitive = client.post(
        "/api/v1/settings",
        json={"aiProvider": "qwen", "aiModel": "qwen3.5-plus"},
    )
    assert sensitive.status_code == 403


def test_org_dna_context_is_injected_into_topics_and_analysis(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    uploaded = client.post(
        "/api/v1/settings/org-dna/market_intro",
        json={
            "markdownContent": "# 市场介绍\n机构目前重点关注公益咨询市场中的 AI 落地、安全治理和筹资效率议题。",
            "fileName": "market.md",
        },
    )
    assert uploaded.status_code == 200

    radar = client.post(
        "/api/v1/topics/radars",
        json={"title": "AI 安全", "prompt": "关注大模型安全方案", "timeRange": "3_days"},
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]
    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "移动云推出大模型安全方案",
            "summary": "文章介绍覆盖评估、防护和数据治理的安全方案。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    captured: dict[str, str] = {}

    def fake_insight_builder(**kwargs):
        captured["organization_context"] = kwargs.get("organization_context", "")
        return {
            "overview": "一、文章主旨。二、核心观点。三、团队价值。",
            "keyPoints": ["要点一"],
            "recommendationReasons": ["值得关注"],
            "practicalUses": ["整理案例"],
        }

    def fake_generate_structured(prompt, system_instruction, context_summary):
        captured["analysis_context"] = context_summary
        return app_main.AiStructuredResponse(
            content="分析综述",
            judgment="判断",
            analysis="分析",
            actions="动作",
            timeline="时间线",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "build_topic_candidate_insight", fake_insight_builder)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", fake_generate_structured)
    monkeypatch.setattr(app_main, "fetch_topic_source_excerpt", lambda url: "source excerpt")
    client.app.state.app_state.db.execute("DELETE FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
    client.app.state.app_state.db.execute("UPDATE topic_candidates SET insight_status = 'pending' WHERE id = ?", (candidate_id,))
    topics_settings = client.post(
        "/api/v1/settings/topics",
        json={"requireInsightBeforeActions": False},
    )
    assert topics_settings.status_code == 200

    refreshed = client.post(f"/api/v1/topics/candidates/{candidate_id}/task-plan")
    assert refreshed.status_code == 200
    assert "公益咨询市场中的 AI 落地" in captured.get("organization_context", "")

    analysis = client.post(
        "/api/v1/analysis-tools/runs",
        json={"templateId": "tpl_systemic", "title": "组织分析", "inputText": "请分析当前系统"},
    )
    assert analysis.status_code == 200
    assert "公益咨询市场中的 AI 落地" in captured.get("analysis_context", "")
