from __future__ import annotations

from pathlib import Path

import httpx

import app.main as app_main
from test_api_smoke import make_client, seed_cloud_token


def _stub_org_model(monkeypatch, payload: dict) -> None:
    def fake_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url.endswith("/api/v1/settings/org-model/profile"):
            return httpx.Response(200, json=payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)


def _org_model_payload(*, strategy: str = "以公益组织数字资产和战略陪伴为核心，沉淀可复用的方法、资料和判断。") -> dict:
    return {
        "organization": {
            "organizationId": "org_1",
            "name": "益语智库",
            "annualGoal": "让组织工作资料持续转化为可复用的数字资产。",
            "annualStrategyYear": "2026",
            "annualStrategy": strategy,
            "quarterPlans": [],
            "quarterlyFocus": ["数据中心", "战略陪伴", "客户工作台"],
            "leaderUserId": "user_ceo",
            "leaderName": "负责人",
            "introDocument": None,
            "managementUserIds": [],
            "updatedAt": "2026-05-04T09:00:00",
        },
        "departments": [
            {
                "id": "dept_data",
                "name": "信息与数据中心",
                "color": "#2563eb",
                "mission": "负责资料清洗、索引、文档级供料和事实安全边界。",
                "businessContext": "把组织工作资料变成可检索、可计算、可复用的资产。",
                "teamContext": "",
                "quarterlyFocus": [],
                "collaborationDepartmentIds": [],
                "active": True,
                "updatedAt": "2026-05-04T09:00:00",
            }
        ],
        "roles": [],
        "bindings": [],
        "reportingLines": [],
        "taskControlRules": [],
        "roleProcessTemplates": [],
        "focusItems": [
            {
                "id": "focus_data_center",
                "periodKey": "2026Q2",
                "title": "数据中心价值闭环",
                "statement": "用真实客户工作台回答验证资料供料质量。",
                "priority": "high",
                "status": "active",
                "evidenceKeywords": [],
                "updatedAt": "2026-05-04T09:00:00",
            }
        ],
        "departmentPlans": [],
        "updatedAt": "2026-05-04T09:00:00",
    }


def test_organization_dna_v2_refresh_generates_snapshot(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_cloud_token(client)
    _stub_org_model(monkeypatch, _org_model_payload())

    refreshed = client.post("/api/v1/digital-assets/organization-dna/refresh", json={"triggerSource": "test"})
    assert refreshed.status_code == 200, refreshed.text
    run_payload = refreshed.json()
    assert run_payload["jobType"] == "organization_dna_refresh"
    assert run_payload["status"] == "completed"
    assert run_payload["processedItems"] >= 2
    assert run_payload["events"]

    response = client.get("/api/v1/digital-assets/organization-dna")
    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmedCount"] >= 1
    assert payload["stableItems"]
    assert payload["riskItems"]
    assert "益语智库" in payload["stableItems"][0]["contentMarkdown"]


def test_organization_dna_v2_collects_task_and_review_evolving_signals(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    state = client.app.state.app_state
    seed_cloud_token(client)
    _stub_org_model(monkeypatch, _org_model_payload())
    now = "2026-05-04T10:00:00"
    state.db.execute(
        """
        INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
        VALUES('list_org_dna', 'org_1', '组织 DNA 测试', '#2563eb', 0, 1, 'org')
        """
    )
    state.db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id,
            owner_id, owner_name, progress_status, ddl, source_type, source_id,
            tags_json, tag_ids_json, current_blocker, next_action, recent_decision,
            created_at, updated_at
        ) VALUES(?, 'org_1', ?, ?, 'todo', 'high', 'list_org_dna', 'user_ceo',
                 'user_ceo', '负责人', 'doing', '', 'manual', NULL, '[]', '[]', ?, ?, ?, ?, ?)
        """,
        (
            "task_org_dna_signal",
            "推进组织 DNA v2 深度调用",
            "把组织 DNA 从设置页静态文本改成数字资产中心里的自动刷新工具。",
            "旧 DNA 调用只读短摘要，无法支撑任务建议。",
            "先建立 stable/evolving/gap/risk 四类资料层，再接入功能区工具读取。",
            "不再恢复旧设置页入口。",
            now,
            now,
        ),
    )
    state.db.execute(
        """
        INSERT INTO weekly_reviews(
            id, organization_id, week_label, operator_id, user_id, work_progress,
            work_blocker, work_direction, next_week_focus, support_needed, summary,
            submitted_at, created_at, updated_at
        ) VALUES(?, 'org_1', ?, 'user_ceo', 'user_ceo', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "review_org_dna_signal",
            "2026-W19",
            "完成组织 DNA v2 的方向拆解和旧入口拆除。",
            "需要让刷新链持续读取任务和复盘。",
            "组织 DNA 应该脱离人工正文编辑，依靠资料积累自动更新。",
            "验证数字资产中心能展示组织 DNA。",
            "需要补齐更多组织介绍资料。",
            "本周重点是把组织 DNA 变成可调用工具，而不是静态配置。",
            now,
            now,
            now,
        ),
    )

    refreshed = client.post("/api/v1/digital-assets/organization-dna/refresh", json={"triggerSource": "test"})
    assert refreshed.status_code == 200, refreshed.text
    payload = client.get("/api/v1/digital-assets/organization-dna").json()
    evolving_text = "\n".join(item["contentMarkdown"] for item in payload["evolvingItems"])
    assert "推进组织 DNA v2 深度调用" in evolving_text
    assert "2026-W19" in evolving_text
    assert any(item["status"] == "candidate" for item in payload["evolvingItems"])


def test_organization_dna_v2_gap_stays_candidate_when_evidence_is_weak(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_cloud_token(client)
    _stub_org_model(monkeypatch, _org_model_payload(strategy=""))

    refreshed = client.post("/api/v1/digital-assets/organization-dna/refresh", json={"triggerSource": "test"})
    assert refreshed.status_code == 200, refreshed.text
    payload = client.get("/api/v1/digital-assets/organization-dna").json()
    gap_items = [item for item in payload["gapItems"] if item["sourceId"] == "org_stable_profile_gaps"]
    assert gap_items
    assert gap_items[0]["status"] == "candidate"
    assert gap_items[0]["evidenceLevel"] == "weak"
    assert gap_items[0]["status"] != "confirmed"
