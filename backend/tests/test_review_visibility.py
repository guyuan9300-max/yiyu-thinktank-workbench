from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_department_lead_only_receives_own_department_summary(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    lists_response = client.get("/api/v1/tasks")
    assert lists_response.status_code == 200
    default_list_id = lists_response.json()["lists"][0]["id"]

    governance_response = client.post(
        "/api/v1/settings/review-governance",
        json={
            "departments": [
                {
                    "id": "dept_consult_strategy",
                    "name": "咨询策略部",
                    "color": "#5B7BFE",
                    "monthlyDna": "本月重点是把战略判断和客户方案打磨做深。",
                    "leaders": [{"id": "lead_1", "fullName": "部门负责人"}],
                    "members": [
                        {"id": "lead_1", "fullName": "部门负责人"},
                        {"id": "member_1", "fullName": "同事甲"},
                    ],
                },
                {
                    "id": "dept_info_data",
                    "name": "信息数据部",
                    "color": "#10B981",
                    "monthlyDna": "本月重点是把信息处理和数据口径校准下来。",
                    "leaders": [{"id": "lead_2", "fullName": "别的负责人"}],
                    "members": [{"id": "member_2", "fullName": "同事乙"}],
                },
            ]
        },
    )
    assert governance_response.status_code == 200

    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "lead_1",
                "organizationId": "org_1",
                "email": "lead@example.com",
                "fullName": "部门负责人",
                "primaryRole": "employee",
                "accountStatus": "approved",
            }
        ),
    )

    task_one = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进战略判断",
            "desc": "整理本周战略推进结论",
            "priority": "high",
            "listId": default_list_id,
            "dueDate": "2026-03-14",
            "ddl": "2026-03-14",
            "ownerId": "member_1",
            "ownerName": "同事甲",
            "collaboratorIds": ["lead_1"],
            "tagIds": [],
        },
    )
    assert task_one.status_code == 200
    task_one_id = task_one.json()["id"]

    task_two = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进信息清洗",
            "desc": "整理本周信息数据侧工作",
            "priority": "normal",
            "listId": default_list_id,
            "dueDate": "2026-03-15",
            "ddl": "2026-03-15",
            "ownerId": "member_2",
            "ownerName": "同事乙",
            "collaboratorIds": [],
            "tagIds": [],
        },
    )
    assert task_two.status_code == 200
    task_two_id = task_two.json()["id"]

    review_response = client.post(
        "/api/v1/reviews/weekly/draft",
        json={
            "weekLabel": "2026-W11",
            "taskEntries": [
                {
                    "taskId": task_one_id,
                    "contentDomain": "work",
                    "note": "本周已完成主要判断整理。",
                    "structuredNote": {
                        "progress": "完成关键判断梳理",
                        "successReason": "问题口径更清晰",
                        "blockerReason": "",
                        "supportNeeded": "",
                        "nextAction": "下周继续推进方案表达",
                    },
                },
                {
                    "taskId": task_two_id,
                    "contentDomain": "work",
                    "note": "本周在处理数据清洗。",
                    "structuredNote": {
                        "progress": "完成数据清洗第一轮",
                        "successReason": "",
                        "blockerReason": "口径还不统一",
                        "supportNeeded": "",
                        "nextAction": "补齐统一字段说明",
                    },
                },
            ],
        },
    )
    assert review_response.status_code == 200

    dashboard = client.get("/api/v1/reviews?weekLabel=2026-W11&skipAi=true")
    assert dashboard.status_code == 200
    payload = dashboard.json()

    assert payload["executiveOrgReport"] is None
    assert payload["simulationBundle"] is None
    assert payload["agentDepartmentDigests"] == []
    assert payload["agentDepartmentPlans"] == []
    assert payload["activePerspective"] == "department"
    assert [item["key"] for item in payload["availablePerspectives"]] == ["department", "mine"]
    assert payload["activeDepartmentId"] == "dept_consult_strategy"
    assert [item["taskId"] for item in payload["workItems"]] == [task_one_id]
    assert payload["departmentReports"] == []


def test_department_lead_can_view_own_agent_execution_tasks_only(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    governance_response = client.post(
        "/api/v1/settings/review-governance",
        json={
            "departments": [
                {
                    "id": "dept_consult_strategy",
                    "name": "咨询策略部",
                    "color": "#5B7BFE",
                    "monthlyDna": "本月重点是把战略判断做深。",
                    "leaders": [{"id": "lead_1", "fullName": "部门负责人"}],
                    "members": [{"id": "lead_1", "fullName": "部门负责人"}],
                },
                {
                    "id": "dept_tech",
                    "name": "科技发展部",
                    "color": "#F59E0B",
                    "monthlyDna": "本月重点是推进系统迭代。",
                    "leaders": [{"id": "lead_2", "fullName": "别的负责人"}],
                    "members": [{"id": "lead_2", "fullName": "别的负责人"}],
                },
            ]
        },
    )
    assert governance_response.status_code == 200

    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "lead_1",
                "organizationId": "org_1",
                "email": "lead@example.com",
                "fullName": "部门负责人",
                "primaryRole": "employee",
                "accountStatus": "approved",
            }
        ),
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "log_qinghua_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            json.dumps({"title": "推进战略判断闭环"}, ensure_ascii=False),
            "2026-03-12T10:00:00",
        ),
    )

    response = client.get("/api/v1/tasks/agent-execution?week=2026-W11")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert all(any(tag["name"] == "咨询策略部" for tag in item["tags"]) for item in payload)

    forbidden = client.get("/api/v1/tasks/agent-execution?week=2026-W11&department=科技发展部")
    assert forbidden.status_code == 403
