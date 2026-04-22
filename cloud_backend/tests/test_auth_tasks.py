from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["YIYU_CLOUD_QINGHUA_PASSWORD"] = "Qinghua123!"
os.environ["YIYU_CLOUD_JIANING_PASSWORD"] = "Jianing123!"
os.environ["YIYU_CLOUD_YISHUO_PASSWORD"] = "Yishuo123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


def setup_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            child.unlink()


def auth_headers(client: TestClient, email: str = "admin@yiyu-system.com", password: str = "Admin123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_register_approve_login_and_collaboration_flow():
    app = create_app()
    client = TestClient(app)

    department_options = client.get("/api/v1/auth/department-options")
    assert department_options.status_code == 200, department_options.text
    assert any(item["id"] == "dept_consult_strategy" for item in department_options.json())

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-user@yiyu-system.com",
            "fullName": "新成员",
            "password": "Password123!",
            "departmentId": "dept_customer_service",
            "jobTitle": "客户成功专员",
            "managerName": "顾源源",
            "currentFocus": "先熟悉客户服务流程与常用资料库",
            "isDepartmentLead": False,
        },
    )
    assert register.status_code == 200, register.text

    pending_login = client.post("/api/v1/auth/login", json={"email": "new-user@yiyu-system.com", "password": "Password123!"})
    assert pending_login.status_code == 403

    admin_headers = auth_headers(client)
    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    pending_user = next(item for item in employees.json() if item["email"] == "new-user@yiyu-system.com")
    assert pending_user["departmentId"] == "dept_customer_service"
    assert pending_user["departmentName"] == "客户服务部"
    assert pending_user["jobTitle"] == "客户成功专员"
    assert pending_user["managerName"] == "顾源源"
    assert pending_user["currentFocus"] == "先熟悉客户服务流程与常用资料库"
    assert pending_user["isDepartmentLead"] is False

    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["departmentId"] == "dept_customer_service"
    org_profile = client.get("/api/v1/settings/org-model/profile", headers=admin_headers)
    assert org_profile.status_code == 200, org_profile.text
    approved_binding = next(item for item in org_profile.json()["bindings"] if item["userId"] == pending_user["id"])
    assert approved_binding["departmentId"] == "dept_customer_service"
    assert approved_binding["primaryRoleId"] == "role_cs_member"
    assert approved_binding["managerUserId"] == "user_guyuan"
    assert approved_binding["currentFocus"] == "先熟悉客户服务流程与常用资料库"
    assert approved_binding["projectRoleLabels"] == ["客户成功专员"]
    assert approved_binding["isManager"] is False
    approved_line = next(item for item in org_profile.json()["reportingLines"] if item["reportUserId"] == pending_user["id"])
    assert approved_line["managerUserId"] == "user_guyuan"
    assert approved_line["lineType"] == "business"

    patch_department = client.patch(
        f"/api/v1/admin/employees/{pending_user['id']}/department",
        json={"departmentId": "dept_info_data"},
        headers=admin_headers,
    )
    assert patch_department.status_code == 200, patch_department.text
    assert patch_department.json()["departmentName"] == "信息数据部"
    org_profile_after_patch = client.get("/api/v1/settings/org-model/profile", headers=admin_headers)
    assert org_profile_after_patch.status_code == 200, org_profile_after_patch.text
    patched_binding = next(item for item in org_profile_after_patch.json()["bindings"] if item["userId"] == pending_user["id"])
    assert patched_binding["departmentId"] == "dept_info_data"
    assert patched_binding["primaryRoleId"] == "role_info_member"
    assert patched_binding["managerUserId"] == "user_guyuan"
    assert patched_binding["projectRoleLabels"] == ["客户成功专员"]

    user_headers = auth_headers(client, "new-user@yiyu-system.com", "Password123!")
    directory = client.get("/api/v1/employees/directory", headers=user_headers)
    assert directory.status_code == 200, directory.text
    assert any(item["id"] == pending_user["id"] and item["departmentId"] == "dept_info_data" for item in directory.json())
    candidates = client.get("/api/v1/employees/mention-candidates", headers=user_headers)
    assert candidates.status_code == 200
    assert candidates.json()[0]["isSelf"] is True
    assert len(candidates.json()) >= 3
    assert any(item["id"] == "user_qinghua" for item in candidates.json())

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】多人协作任务",
            "description": "请一起跟进",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T14:30",
            "clientId": "client_demo_yellow_river",
            "projectModuleId": "module_client_delivery",
            "projectFlowId": "flow_weekly_sync",
            "collaboratorIds": [pending_user["id"], "user_qinghua", "user_jianing"],
            "tags": ["会议", "紧急"],
        },
        headers=user_headers,
    )
    assert task.status_code == 200, task.text
    body = task.json()
    assert body["dueDate"] == "2026-03-20T14:30"
    assert body["clientId"] == "client_demo_yellow_river"
    assert body["projectModuleId"] == "module_client_delivery"
    assert body["projectFlowId"] == "flow_weekly_sync"
    assert body["ownerId"] == pending_user["id"]
    assert len(body["collaborators"]) == 3

    updated = client.patch(
        f"/api/v1/tasks/{body['id']}",
        json={
            "clientId": "client_demo_for_love",
            "projectModuleId": "module_strategy_review",
            "projectFlowId": "flow_risk_review",
            "priority": "normal",
        },
        headers=user_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["clientId"] == "client_demo_for_love"
    assert updated.json()["projectModuleId"] == "module_strategy_review"
    assert updated.json()["projectFlowId"] == "flow_risk_review"

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    accepted = client.post(
        f"/api/v1/tasks/{body['id']}/collaborators/user_qinghua/accept",
        headers=qinghua_headers,
    )
    assert accepted.status_code == 200, accepted.text

    collaborator_update = client.patch(
        f"/api/v1/tasks/{body['id']}",
        json={
            "title": "【测试】协作者已调整标题",
            "ownerId": "user_qinghua",
        },
        headers=qinghua_headers,
    )
    assert collaborator_update.status_code == 200, collaborator_update.text
    assert collaborator_update.json()["title"] == "【测试】协作者已调整标题"
    assert collaborator_update.json()["ownerId"] == "user_qinghua"

    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    returned = client.post(
        f"/api/v1/tasks/{body['id']}/collaborators/user_jianing/return",
        json={"reason": "当前优先级冲突，需要重新排期"},
        headers=jianing_headers,
    )
    assert returned.status_code == 200, returned.text
    assert any(item["inboxStatus"] == "returned" for item in returned.json()["collaborators"])

    activity = client.get(f"/api/v1/tasks/{body['id']}/activity", headers=user_headers)
    assert activity.status_code == 200
    event_types = [item["eventType"] for item in activity.json()]
    assert "accepted" in event_types
    assert "returned" in event_types


def test_mention_candidates_fill_recent_gap_with_other_approved_employees():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    response = client.get("/api/v1/employees/mention-candidates", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload[0]["id"] == "user_jianing"
    assert payload[0]["isSelf"] is True
    assert any(item["id"] == "user_qinghua" for item in payload)
    assert any(item["id"] == "user_yishuo" for item in payload)


def test_collaborator_can_update_task_content_and_owner():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "协作者权限测试任务",
            "description": "初始描述",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-20",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_qinghua",
        },
        headers=qinghua_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    accept = client.post(
        f"/api/v1/tasks/{task_id}/collaborators/user_jianing/accept",
        headers=jianing_headers,
    )
    assert accept.status_code == 200, accept.text

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "title": "协作者已修改标题",
            "description": "协作者已修改描述",
            "ownerId": "user_jianing",
        },
        headers=jianing_headers,
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["title"] == "协作者已修改标题"
    assert payload["description"] == "协作者已修改描述"
    assert payload["ownerId"] == "user_jianing"


def test_event_line_clarification_fields_persist_in_cloud_backend():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "云端事件线澄清",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "businessCategory": "业务扩展",
            "stage": "资料补齐中",
            "currentBlocker": "客户侧接口人还没确认最终口径。",
            "nextStep": "把这周会议结论同步给客户并确认时间。",
            "recentDecision": "先统一资料，再进入下一轮推进。",
            "evidenceCount": 4,
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["businessCategory"] == "业务扩展"
    assert body["stage"] == "资料补齐中"
    assert body["currentBlocker"] == "客户侧接口人还没确认最终口径。"
    assert body["nextStep"] == "把这周会议结论同步给客户并确认时间。"
    assert body["recentDecision"] == "先统一资料，再进入下一轮推进。"
    assert body["evidenceCount"] == 4

    detail = client.get(f"/api/v1/event-lines/{event_line_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["eventLine"]["businessCategory"] == "业务扩展"
    assert detail.json()["eventLine"]["currentBlocker"] == "客户侧接口人还没确认最终口径。"
    assert detail.json()["eventLine"]["recentDecision"] == "先统一资料，再进入下一轮推进。"
    assert detail.json()["eventLine"]["evidenceCount"] == 4


def test_desktop_event_line_import_preserves_id_and_skips_existing_rows():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    payload = {
        "eventLines": [
            {
                "id": "eline_desktop_import_1",
                "name": "桌面端补迁移事件线",
                "kind": "project_line",
                "status": "active",
                "visibilityScope": "project_public",
                "businessCategory": "业务扩展",
                "stage": "资料补齐中",
                "summary": "先把本地事件线补到云端。",
                "intent": "保留原始 ID 迁移到云端",
                "currentBlocker": "还没正式迁移。",
                "recentDecision": "先做增量导入。",
                "nextStep": "确认导入成功后再讨论任务规则。",
                "evidenceCount": 2,
                "ownerId": "user_qinghua",
                "primaryClientId": "client_demo_yellow_river",
                "participantIds": ["user_qinghua", "user_admin"],
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
                "activities": [
                    {
                        "id": "ela_desktop_import_1",
                        "sourceType": "manual_note",
                        "sourceId": "ela_desktop_import_1",
                        "happenedAt": now_iso(),
                        "actorId": "user_qinghua",
                        "title": "桌面备注",
                        "summary": "这是从桌面端补迁移过来的备注。",
                        "metadata": {"source": "desktop"},
                    }
                ],
            }
        ]
    }

    imported = client.post("/api/v1/event-lines/import-desktop", json=payload, headers=headers)
    assert imported.status_code == 200, imported.text
    imported_payload = imported.json()
    assert imported_payload["requested"] == 1
    assert imported_payload["imported"] == 1
    assert imported_payload["items"][0]["id"] == "eline_desktop_import_1"
    assert imported_payload["items"][0]["status"] == "imported"
    assert imported_payload["items"][0]["importedActivityCount"] == 1

    detail = client.get("/api/v1/event-lines/eline_desktop_import_1", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["eventLine"]["id"] == "eline_desktop_import_1"
    assert detail_payload["eventLine"]["ownerId"] == "user_qinghua"
    assert detail_payload["eventLine"]["primaryClientId"] == "client_demo_yellow_river"
    assert any(item["id"] == "ela_desktop_import_1" for item in detail_payload["activities"])

    second_run = client.post("/api/v1/event-lines/import-desktop", json=payload, headers=headers)
    assert second_run.status_code == 200, second_run.text
    second_payload = second_run.json()
    assert second_payload["imported"] == 0
    assert second_payload["skipped"] == 1
    assert second_payload["items"][0]["status"] == "skipped"


def test_review_dashboard_works_for_task_with_event_line_context():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会合作推进",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert event_line.status_code == 200, event_line.text
    event_line_id = event_line.json()["id"]

    updated_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "businessCategory": "业务扩展",
            "stage": "方案推进中",
            "summary": "围绕黄河基金会合作方案持续推进。",
            "intent": "确认合作范围与报价口径。",
            "currentBlocker": "客户侧预算和范围还没完全收口。",
            "recentDecision": "先继续推进官网侧准备，再给出报价判断。",
            "nextStep": "整理合作方案并约下一轮确认。",
            "evidenceCount": 3,
        },
        headers=headers,
    )
    assert updated_line.status_code == 200, updated_line.text

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给黄河教系统合作方案",
            "description": "围绕黄河基金会合作范围继续推进方案整理。",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T10:00",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧预算和范围还没完全收口。",
            "nextAction": "整理合作方案并约下一轮确认。",
            "recentDecision": "先继续推进官网侧准备，再给出报价判断。",
            "evidenceCount": 5,
        },
        headers=headers,
    )
    assert task.status_code == 200, task.text
    task_payload = task.json()
    assert task_payload["businessCategory"] == "业务扩展"
    assert task_payload["currentBlocker"] == "客户侧预算和范围还没完全收口。"
    assert task_payload["nextAction"] == "整理合作方案并约下一轮确认。"
    assert task_payload["recentDecision"] == "先继续推进官网侧准备，再给出报价判断。"
    assert task_payload["evidenceCount"] == 5

    created_review = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "workFreeNote": "围绕黄河基金会合作推进。",
        },
        headers=headers,
    )
    assert created_review.status_code == 200, created_review.text

    dashboard = client.get("/api/v1/reviews/dashboard?weekLabel=2026-W12", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()
    matched = next(item for item in payload["workItems"] if item["taskId"] == task_payload["id"])
    assert matched["taskSnapshot"]["eventLineContext"]["id"] == event_line_id
    assert matched["taskSnapshot"]["eventLineContext"]["name"] == "黄河基金会合作推进"
    assert matched["taskSnapshot"]["eventLineContext"]["businessCategory"] == "业务扩展"
    assert matched["taskSnapshot"]["eventLineContext"]["evidenceCount"] == 3
    assert matched["taskSnapshot"]["eventLineContext"]["primaryClientId"] == "client_demo_yellow_river"


def test_personal_task_scope_mode_persists_in_cloud_backend():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "不应挂接的共享线",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert event_line.status_code == 200, event_line.text

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "去健身",
            "description": "个人安排，不进入共享判断。",
            "priority": "normal",
            "listId": "list-0",
            "scopeMode": "PERSONAL_ONLY",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line.json()["id"],
            "projectModuleId": "module_should_clear",
            "projectFlowId": "flow_should_clear",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["scopeMode"] == "PERSONAL_ONLY"
    assert body["clientId"] in ("", None)
    assert body["eventLineId"] in ("", None)
    assert body["projectModuleId"] in ("", None)
    assert body["projectFlowId"] in ("", None)

    row = client.app.state.app_state.db.fetchone(
        "SELECT scope_mode, client_id, event_line_id, project_module_id, project_flow_id FROM tasks WHERE id = ?",
        (body["id"],),
    )
    assert row["scope_mode"] == "PERSONAL_ONLY"
    assert row["client_id"] is None
    assert row["event_line_id"] is None
    assert row["project_module_id"] is None
    assert row["project_flow_id"] is None


def test_personal_growth_content_is_self_only_and_excluded_from_team_report():
    app = create_app()
    client = TestClient(app)

    week_label = "2026-W11"
    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    submitted = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": week_label,
            "workProgress": "完成客户材料整理并推进会议纪要落地。",
            "workBlocker": "跨部门协作信息不同步。",
            "blockerType": "协作卡住",
            "workDirection": "围绕战略陪伴闭环推进。",
            "nextWeekFocus": "补齐客户访谈与周会动作项。",
            "supportNeeded": "需要一个更清晰的优先级排序。",
            "relatedPlanIds": ["plan_mgr_support"],
            "workFreeNote": "工作域内容用于层级视野。",
            "personalGrowthNote": "我最近有些焦虑，想更稳定地安排节奏。",
            "personalPrivateNote": "这是完全私密的成长备注，只能自己看。",
        },
        headers=jianing_headers,
    )
    assert submitted.status_code == 200, submitted.text
    dashboard = submitted.json()
    assert dashboard["personalGrowthCard"]["summary"].startswith("我最近有些焦虑")
    assert dashboard["workSignalCard"]["contentDomain"] == "work"

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    team_dashboard = client.get("/api/v1/reviews/dashboard", headers=qinghua_headers)
    assert team_dashboard.status_code == 200, team_dashboard.text
    payload = team_dashboard.json()
    assert payload["teamReport"] is not None
    assert payload["teamReport"]["sourcePolicy"]["excludedDomains"] == ["personal", "private", "self_only"]
    serialized = str(payload["teamReport"])
    assert "完全私密的成长备注" not in serialized
    assert "最近有些焦虑" not in serialized


def test_feishu_binding_relay_session_roundtrip():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    create_response = client.post(
        "/api/v1/integrations/feishu/user-binding/sessions",
        json={
            "state": "fs_state_demo",
            "expiresAt": (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    assert create_response.json()["status"] == "pending"

    callback_response = client.get(
        "/api/v1/integrations/feishu/user-binding/callback",
        params={"state": "fs_state_demo", "code": "authorization_code_demo"},
    )
    assert callback_response.status_code == 200, callback_response.text
    assert "飞书授权结果已回传" in callback_response.text

    status_response = client.get(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert payload["status"] == "authorized"
    assert payload["code"] == "authorization_code_demo"

    delete_response = client.delete(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    missing_response = client.get(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert missing_response.status_code == 404


def test_task_overdue_only_after_calendar_day_ends():
    app = create_app()
    client = TestClient(app)

    admin_login = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "overdue-check@yiyu-system.com", "fullName": "逾期校验员", "password": "Password123!", "departmentId": "dept_customer_service"},
    )
    assert register.status_code == 200, register.text

    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    assert employees.status_code == 200, employees.text
    pending_user = next(item for item in employees.json() if item["email"] == "overdue-check@yiyu-system.com")

    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text

    user_login = client.post("/api/v1/auth/login", json={"email": "overdue-check@yiyu-system.com", "password": "Password123!"})
    assert user_login.status_code == 200, user_login.text
    user_headers = {"Authorization": f"Bearer {user_login.json()['accessToken']}"}
    user_id = user_login.json()["user"]["id"]

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    due_today = client.post(
        "/api/v1/tasks",
        json={
            "title": "今天 16:00 截止也不算逾期",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": f"{today.isoformat()}T16:00",
            "collaboratorIds": [],
        },
        headers=user_headers,
    )
    assert due_today.status_code == 200, due_today.text

    due_yesterday = client.post(
        "/api/v1/tasks",
        json={
            "title": "昨天截止才算逾期",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": f"{yesterday.isoformat()}T16:00",
            "collaboratorIds": [],
        },
        headers=user_headers,
    )
    assert due_yesterday.status_code == 200, due_yesterday.text

    metrics = cloud_main._task_metrics_for_user(app.state.app_state, user_id)
    assert metrics["taskCount"] == 2
    assert metrics["activeCount"] == 2
    assert metrics["overdueCount"] == 1


def test_review_history_lists_previous_weeks_and_dashboard_can_switch_by_weeklabel():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")

    first = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W11",
            "workFreeNote": "W11 工作复盘",
            "personalGrowthNote": "W11 成长复盘",
        },
        headers=headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "workFreeNote": "W12 工作复盘",
            "personalGrowthNote": "W12 成长复盘",
        },
        headers=headers,
    )
    assert second.status_code == 200, second.text

    history = client.get("/api/v1/reviews/history", headers=headers)
    assert history.status_code == 200, history.text
    history_payload = history.json()["items"]
    assert [item["weekLabel"] for item in history_payload][:2] == ["2026-W12", "2026-W11"]

    dashboard = client.get("/api/v1/reviews/dashboard?weekLabel=2026-W11", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_payload = dashboard.json()
    assert dashboard_payload["currentReview"]["weekLabel"] == "2026-W11"
    assert dashboard_payload["currentReview"]["workFreeNote"] == "W11 工作复盘"


def test_org_model_profile_roundtrip():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)

    response = client.get('/api/v1/settings/org-model/profile', headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['organization']['name'] == '益语智库'
    assert len(payload['departments']) == 4
    assert len(payload['roles']) >= 4
    assert len(payload['bindings']) >= 4
    assert 'roleProcessTemplates' in payload

    payload['organization']['annualGoal'] = '把 AI 任务系统和组织判断真正打通'
    payload['organization']['quarterlyFocus'] = ['组织模型 P0 上线', '部门周计划接入']
    payload['departments'][0]['mission'] = '把策略判断转成可执行路径'
    payload['focusItems'] = [
        {
            'id': 'focus_q2_signal',
            'periodKey': '2026-Q2',
            'title': '管理信号引擎上线',
            'statement': '让部门总结和 CEO 总结能直接引用结构化管理信号',
            'ownerUserId': 'user_admin',
            'priority': 'high',
            'status': 'active',
            'evidenceKeywords': ['管理信号', '周总结', '组织判断'],
            'updatedAt': '',
        }
    ]
    payload['departmentPlans'] = [
        {
            'id': 'plan_consult_w12',
            'departmentId': 'dept_consult_strategy',
            'weekLabel': '2026-W12',
            'ownerUserId': 'user_qinghua',
            'summary': '把咨询判断沉淀成可复用的策略输出结构',
            'majorRisks': ['资料不完整'],
            'dependencies': ['等待科技发展部确认能力边界'],
            'status': 'active',
            'items': [
                {
                    'id': 'plan_item_consult_signal',
                    'focusItemId': 'focus_q2_signal',
                    'title': '沉淀咨询判断模板',
                    'statement': '把顾问判断过程写成固定模板',
                    'ownerUserId': 'user_qinghua',
                    'status': 'active',
                    'expectedOutput': '判断模板 v1',
                    'sortOrder': 0,
                    'updatedAt': '',
                }
            ],
            'updatedAt': '',
        }
    ]
    payload['roleProcessTemplates'] = [
        {
            'id': 'process_cs_followup',
            'roleTemplateId': 'role_cs_member',
            'name': '客户周会后推进流程',
            'triggerType': 'weekly_followup',
            'triggerCondition': '客户周会结束',
            'keySteps': ['确认需补资料项', '更新客户工作台', '同步飞书群重点', '生成下周待确认事项'],
            'collaborationStep': '同步飞书群重点',
            'approvalStep': '生成下周待确认事项',
            'outputArtifact': '客户推进摘要 + 新任务清单',
            'commonBlockers': ['资料未补齐', '等待部门确认'],
            'active': True,
            'updatedAt': '',
        }
    ]

    updated = client.post('/api/v1/settings/org-model/profile', json=payload, headers=headers)
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload['organization']['annualGoal'] == '把 AI 任务系统和组织判断真正打通'
    assert updated_payload['organization']['quarterlyFocus'] == ['组织模型 P0 上线', '部门周计划接入']
    assert updated_payload['departments'][0]['mission'] == '把策略判断转成可执行路径'
    assert updated_payload['focusItems'][0]['title'] == '管理信号引擎上线'
    assert updated_payload['departmentPlans'][0]['items'][0]['title'] == '沉淀咨询判断模板'
    assert len(updated_payload['roleProcessTemplates']) == 1
    assert updated_payload['roleProcessTemplates'][0]['triggerType'] == 'weekly_followup'

    reread = client.get('/api/v1/settings/org-model/profile', headers=headers)
    assert reread.status_code == 200, reread.text
    reread_payload = reread.json()
    assert reread_payload['organization']['annualGoal'] == '把 AI 任务系统和组织判断真正打通'
    assert reread_payload['departments'][0]['mission'] == '把策略判断转成可执行路径'
    assert reread_payload['focusItems'][0]['evidenceKeywords'] == ['管理信号', '周总结', '组织判断']
    assert reread_payload['departmentPlans'][0]['dependencies'] == ['等待科技发展部确认能力边界']
    assert reread_payload['roleProcessTemplates'][0]['commonBlockers'] == ['资料未补齐', '等待部门确认']


def test_task_org_link_and_department_control_permissions():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部关键推进",
            "description": "需要下周给 CEO 汇报",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T16:00",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_jianing",
        },
        headers=qinghua_headers,
    )
    assert create.status_code == 200, create.text
    create_payload = create.json()
    task_id = create_payload["id"]
    assert create_payload["orgContext"]["departmentId"] == "dept_customer_service"
    assert create_payload["orgContext"]["roleTemplateId"] == "role_cs_lead"
    assert create_payload["orgContext"]["controlRuleId"] == "rule_department_key"
    assert create_payload["orgContext"]["controlLevel"] == "department_control"
    assert create_payload["orgContext"]["needsReview"] is True
    assert create_payload["orgContext"]["approvalState"] == "pending"

    link_row = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert link_row is not None
    assert str(link_row["department_id"]) == "dept_customer_service"
    assert str(link_row["role_template_id"]) == "role_cs_lead"
    assert str(link_row["control_rule_id"]) == "rule_department_key"

    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    denied = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-03-21T18:00"},
        headers=jianing_headers,
    )
    assert denied.status_code == 403
    assert "截止时间" in denied.text

    allowed = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-03-21T18:00"},
        headers=qinghua_headers,
    )
    assert allowed.status_code == 200, allowed.text
    allowed_payload = allowed.json()
    assert allowed_payload["dueDate"] == "2026-03-21T18:00"
    assert allowed_payload["orgContext"]["controlLevel"] == "department_control"


def test_task_plan_link_and_support_request_flow():
    app = create_app()
    client = TestClient(app)

    admin_headers = auth_headers(client)
    profile = client.get('/api/v1/settings/org-model/profile', headers=admin_headers).json()
    profile['focusItems'] = [
        {
            'id': 'focus_q2_signal',
            'periodKey': '2026-Q2',
            'title': '管理信号引擎上线',
            'statement': '推进周总结和任务系统的管理信号能力',
            'ownerUserId': 'user_admin',
            'priority': 'high',
            'status': 'active',
            'evidenceKeywords': ['管理信号', '任务系统'],
            'updatedAt': '',
        }
    ]
    profile['departmentPlans'] = [
        {
            'id': 'plan_info_w12',
            'departmentId': 'dept_info_data',
            'weekLabel': '2026-W12',
            'ownerUserId': 'user_yishuo',
            'summary': '搭建信息数据部本周重点',
            'majorRisks': [],
            'dependencies': [],
            'status': 'active',
            'items': [
                {
                    'id': 'plan_item_signal',
                    'focusItemId': 'focus_q2_signal',
                    'title': '管理信号模板接入',
                    'statement': '完善管理信号模板与导入逻辑',
                    'ownerUserId': 'user_yishuo',
                    'status': 'active',
                    'expectedOutput': '模板 v1',
                    'sortOrder': 0,
                    'updatedAt': '',
                }
            ],
            'updatedAt': '',
        }
    ]
    saved = client.post('/api/v1/settings/org-model/profile', json=profile, headers=admin_headers)
    assert saved.status_code == 200, saved.text

    yishuo_headers = auth_headers(client, "yishuo@yiyu-system.com", "Yishuo123!")
    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "管理信号模板接入周总结",
            "description": "本周把管理信号模板接进组织总结",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-19T10:00",
        },
        headers=yishuo_headers,
    )
    assert create.status_code == 200, create.text
    task_id = create.json()["id"]

    recompute = client.post(f"/api/v1/tasks/{task_id}/plan-link/recompute", headers=admin_headers)
    assert recompute.status_code == 200, recompute.text
    recompute_payload = recompute.json()
    assert recompute_payload["focusItemId"] == "focus_q2_signal"
    assert recompute_payload["departmentPlanItemId"] == "plan_item_signal"

    support = client.post(
        "/api/v1/support-requests",
        json={
            "taskId": task_id,
            "targetScope": "department",
            "targetRefId": "dept_info_data",
            "requestType": "resource",
            "urgency": "medium",
            "summary": "需要补一位同事协助整理历史模板",
        },
        headers=yishuo_headers,
    )
    assert support.status_code == 200, support.text
    support_id = support.json()["id"]

    listed = client.get("/api/v1/support-requests?taskId=" + task_id, headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == support_id for item in listed.json())

    resolved = client.post(
        f"/api/v1/support-requests/{support_id}/resolve",
        json={"status": "resolved", "resolutionNote": "已由部门负责人安排支持"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"


def test_event_line_roundtrip_and_detail_collects_task_and_support_request():
    app = create_app()
    client = TestClient(app)

    admin_headers = auth_headers(client)

    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "云南连心推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "本周推进",
            "summary": "串起云南连心相关任务、会议和支持请求。",
            "intent": "推进云南连心合作闭环",
            "ownerId": "user_admin",
            "primaryClientId": "client_demo_yellow_river",
            "primaryDepartmentId": "dept_consult_strategy",
            "participantIds": ["user_admin", "user_qinghua"],
        },
        headers=admin_headers,
    )
    assert created_line.status_code == 200, created_line.text
    event_line = created_line.json()
    assert event_line["name"] == "云南连心推进线"
    assert event_line["primaryClientId"] == "client_demo_yellow_river"

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进云南连心合作方案",
            "description": "补齐合作方案与对接节奏",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-24T14:00",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line["id"],
        },
        headers=admin_headers,
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["eventLineId"] == event_line["id"]
    assert task_payload["eventLineName"] == "云南连心推进线"

    support_request = client.post(
        "/api/v1/support-requests",
        json={
            "taskId": task_payload["id"],
            "targetScope": "department",
            "targetRefId": "dept_consult_strategy",
            "requestType": "collaboration",
            "urgency": "medium",
            "summary": "需要补齐云南连心合作推进中的协作确认。",
        },
        headers=admin_headers,
    )
    assert support_request.status_code == 200, support_request.text

    detail = client.get(f"/api/v1/event-lines/{event_line['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["eventLine"]["id"] == event_line["id"]
    assert any(item["id"] == task_payload["id"] for item in detail_payload["tasks"])
    activity_source_types = [item["sourceType"] for item in detail_payload["activities"]]
    assert "task_activity" in activity_source_types
    assert "support_request" in activity_source_types


def test_task_review_approve_and_return_follow_org_permissions():
    app = create_app()
    client = TestClient(app)
    db = app.state.app_state.db

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    admin_headers = auth_headers(client)

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "review-worker@yiyu-system.com", "fullName": "复核执行员", "password": "Password123!", "departmentId": "dept_customer_service"},
    )
    assert register.status_code == 200, register.text

    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    assert employees.status_code == 200, employees.text
    pending_user = next(item for item in employees.json() if item["email"] == "review-worker@yiyu-system.com")
    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    worker_headers = auth_headers(client, "review-worker@yiyu-system.com", "Password123!")

    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部待复核任务",
            "description": "需要部门负责人复核",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-23T16:00",
            "collaboratorIds": [pending_user["id"]],
            "ownerId": pending_user["id"],
        },
        headers=qinghua_headers,
    )
    assert create.status_code == 200, create.text
    task_id = create.json()["id"]
    assert create.json()["orgContext"]["needsReview"] is True
    assert create.json()["orgContext"]["approvalState"] == "pending"

    self_owned = client.post(
        "/api/v1/tasks",
        json={
            "title": "自己创建自己负责的任务",
            "description": "验证负责人不能自己复核",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-23T18:00",
            "ownerId": pending_user["id"],
        },
        headers=worker_headers,
    )
    assert self_owned.status_code == 200, self_owned.text
    self_task_id = self_owned.json()["id"]
    db.execute(
        """
        UPDATE task_org_links
           SET approval_state = 'pending',
               needs_review = 1,
               updated_at = ?
         WHERE task_id = ?
        """,
        (now_iso(), self_task_id),
    )
    self_denied = client.post(f"/api/v1/tasks/{self_task_id}/review/approve", headers=worker_headers)
    assert self_denied.status_code == 403, self_denied.text

    denied = client.post(f"/api/v1/tasks/{task_id}/review/approve", headers=worker_headers)
    assert denied.status_code == 403, denied.text

    approved = client.post(f"/api/v1/tasks/{task_id}/review/approve", headers=qinghua_headers)
    assert approved.status_code == 200, approved.text
    approved_payload = approved.json()
    assert approved_payload["orgContext"]["needsReview"] is False
    assert approved_payload["orgContext"]["approvalState"] == "approved"

    create_again = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部退回复核任务",
            "description": "需要退回复核",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-24T16:00",
            "collaboratorIds": [pending_user["id"]],
            "ownerId": pending_user["id"],
        },
        headers=qinghua_headers,
    )
    assert create_again.status_code == 200, create_again.text
    second_task_id = create_again.json()["id"]

    returned = client.post(
        f"/api/v1/tasks/{second_task_id}/review/return",
        json={"reason": "等待补充客户信息"},
        headers=qinghua_headers,
    )
    assert returned.status_code == 200, returned.text
    returned_payload = returned.json()
    assert returned_payload["orgContext"]["approvalState"] == "rejected"
    assert returned_payload["orgContext"]["needsReview"] is True
    assert returned_payload["orgContext"]["blockedAtStep"] == "等待补充客户信息"


def test_org_model_backfill_restores_missing_task_links_for_existing_tasks():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "历史任务补链验证",
            "description": "验证存量任务能补回组织挂接",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-22T10:00",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_jianing",
        },
        headers=qinghua_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    app.state.app_state.db.execute("DELETE FROM task_org_links WHERE task_id = ?", (task_id,))
    missing = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert missing is None

    admin_headers = auth_headers(client)
    backfill = client.post("/api/v1/settings/org-model/backfill-task-links", headers=admin_headers)
    assert backfill.status_code == 200, backfill.text
    payload = backfill.json()
    assert payload["organizationId"] == "org_yiyu_default"
    assert payload["linkedTasks"] >= 1
    assert payload["createdLinks"] >= 1

    restored = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert restored is not None
    assert str(restored["department_id"]) == "dept_customer_service"


def test_event_line_notifications_can_be_marked_read_in_batch():
    app = create_app()
    client = TestClient(app)

    admin_headers = auth_headers(client)
    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "批量已阅事件线通知",
            "kind": "project_line",
            "status": "active",
            "ownerId": "user_admin",
            "primaryClientId": "client_demo_yellow_river",
            "participantIds": ["user_admin", "user_qinghua"],
        },
        headers=admin_headers,
    )
    assert created_line.status_code == 200, created_line.text
    event_line_id = created_line.json()["id"]

    closed = client.post(f"/api/v1/event-lines/{event_line_id}/close", headers=admin_headers)
    assert closed.status_code == 200, closed.text

    notification_rows = app.state.app_state.db.fetchall(
        "SELECT id, progress_status FROM tasks WHERE source_type = 'event_line_notification' AND event_line_id = ? ORDER BY created_at ASC",
        (event_line_id,),
    )
    assert len(notification_rows) == 1
    notification_id = str(notification_rows[0]["id"])
    assert str(notification_rows[0]["progress_status"]) == "inbox"

    marked = client.post(
        "/api/v1/tasks/notifications/read-batch",
        json={"taskIds": [notification_id]},
        headers=admin_headers,
    )
    assert marked.status_code == 200, marked.text
    payload = marked.json()
    assert payload["updatedCount"] == 1
    assert payload["taskIds"] == [notification_id]

    intermediate = app.state.app_state.db.fetchone(
        "SELECT progress_status FROM tasks WHERE id = ?",
        (notification_id,),
    )
    assert intermediate is not None
    assert str(intermediate["progress_status"]) == "inbox"

    qinghua_marked = client.post(
        "/api/v1/tasks/notifications/read-batch",
        json={"taskIds": [notification_id]},
        headers=qinghua_headers,
    )
    assert qinghua_marked.status_code == 200, qinghua_marked.text

    refreshed = app.state.app_state.db.fetchone(
        "SELECT progress_status FROM tasks WHERE id = ?",
        (notification_id,),
    )
    assert refreshed is not None
    assert str(refreshed["progress_status"]) == "done"
