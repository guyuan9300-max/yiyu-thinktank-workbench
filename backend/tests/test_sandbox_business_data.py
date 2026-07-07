from __future__ import annotations

import sys
from pathlib import Path
import json
from datetime import datetime

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    DEFAULT_LOCAL_SANDBOX_ID,
    ensure_organization_sandbox_for_session,
    ensure_sandbox_registry,
    set_sandbox_setting,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": "",
            "domain": "测试领域",
            "type": "公益组织",
            "intro": "用于工作空间隔离测试",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def create_task_record(client: TestClient, title: str, client_id: str | None = None) -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": "用于工作空间隔离测试",
            "priority": "normal",
            "listId": "",
            "clientId": client_id,
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": name, "cloudApiUrl": f"https://{name}.example.test"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["activeSandboxId"])


def current_operator_identity(client: TestClient) -> tuple[str, str]:
    db = client.app.state.app_state.db
    row = db.fetchone("SELECT id, name FROM operators ORDER BY created_at ASC LIMIT 1")
    assert row is not None
    return str(row["id"]), str(row["name"] or "当前用户")


def badge_by_id(payload: dict, badge_id: str) -> dict:
    for category in payload["categories"]:
        for badge in category["badges"]:
            if badge["id"] == badge_id:
                return badge
    raise AssertionError(f"badge not found: {badge_id}")


def seed_workspace_session(client: TestClient, sandbox_id: str) -> None:
    db = client.app.state.app_state.db
    row = db.fetchone("SELECT organization_id, organization_name, name FROM sandboxes WHERE id = ?", (sandbox_id,))
    assert row is not None
    organization_id = str(row["organization_id"] or sandbox_id)
    organization_name = str(row["organization_name"] or row["name"] or sandbox_id)
    set_sandbox_setting(db, sandbox_id, "cloud_access_token", f"token-{sandbox_id}")
    set_sandbox_setting(db, sandbox_id, "cloud_refresh_token", f"refresh-{sandbox_id}")
    set_sandbox_setting(
        db,
        sandbox_id,
        "cloud_session_user",
        json.dumps(
            {
                "id": f"user-{sandbox_id}",
                "email": f"{sandbox_id}@example.test",
                "fullName": "沙箱测试用户",
                "organizationId": organization_id,
                "organizationName": organization_name,
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )


def test_clients_tasks_and_documents_follow_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    data_dir = client.app.state.app_state.data_dir

    draft_client_id = create_client_record(client, "草稿项目 A")
    draft_task_id = create_task_record(client, "草稿任务 A", draft_client_id)
    doc_path = data_dir / "sandbox-doc-a.md"
    doc_path.write_text("# 草稿文档 A\n\n创建组织后应迁入该组织。", encoding="utf-8")
    db.execute(
        """
        INSERT INTO documents(id, client_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "doc_local_a",
            draft_client_id,
            "草稿文档 A",
            str(doc_path),
            "md",
            "manual",
            "创建组织后应迁入该组织。",
            "[]",
            "2026-06-18T00:00:00Z",
        ),
    )

    assert draft_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert draft_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert client.get("/api/v1/documents/doc_local_a/text").status_code == 200

    org_a_id = create_workspace(client, "org-a")
    assert org_a_id != DEFAULT_LOCAL_SANDBOX_ID

    assert draft_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert draft_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert client.get("/api/v1/documents/doc_local_a/text").status_code == 200

    org_client_id = create_client_record(client, "组织项目 A")
    org_task_id = create_task_record(client, "组织任务 A", org_client_id)
    assert org_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert org_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}

    org_b_id = create_workspace(client, "org-b")
    assert org_b_id != org_a_id
    assert draft_client_id not in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert org_client_id not in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert draft_task_id not in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert org_task_id not in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert client.get("/api/v1/documents/doc_local_a/text").status_code == 404
    assert client.get(f"/api/v1/clients/{draft_client_id}/workspace").status_code == 404
    assert client.get(f"/api/v1/clients/{draft_client_id}/delete-preview").status_code == 404
    assert client.patch(f"/api/v1/tasks/{draft_task_id}", json={"title": "不应跨空间修改"}).status_code == 404

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    assert draft_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert org_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert draft_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert org_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}


def test_task_tags_can_share_names_across_workspaces(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first = client.post(
        "/api/v1/task-tags",
        json={"name": "待跟进", "scope": "org", "color": "#5B7BFE"},
    )
    assert first.status_code == 200, first.text
    first_id = str(first.json()["id"])

    org_a_id = create_workspace(client, "org-tag-a")
    active_tags = client.get("/api/v1/task-tags")
    assert active_tags.status_code == 200, active_tags.text
    active_tag_ids = {item["id"] for item in active_tags.json()["tags"]}
    assert first_id in active_tag_ids

    org_b_id = create_workspace(client, "org-tag-b")
    assert org_b_id != org_a_id
    second = client.post(
        "/api/v1/task-tags",
        json={"name": "待跟进", "scope": "org", "color": "#22C55E"},
    )
    assert second.status_code == 200, second.text
    second_id = str(second.json()["id"])
    assert second_id != first_id

    active_tags = client.get("/api/v1/task-tags")
    assert active_tags.status_code == 200, active_tags.text
    active_tag_ids = {item["id"] for item in active_tags.json()["tags"]}
    assert second_id in active_tag_ids
    assert first_id not in active_tag_ids

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    org_a_tags = client.get("/api/v1/task-tags")
    assert org_a_tags.status_code == 200, org_a_tags.text
    org_a_tag_ids = {item["id"] for item in org_a_tags.json()["tags"]}
    assert first_id in org_a_tag_ids
    assert second_id not in org_a_tag_ids


def test_legacy_business_rows_are_backfilled_to_default_workspace(tmp_path: Path) -> None:
    db = Database(tmp_path / "legacy.db")
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy_client", "历史项目", "", "测试领域", "公益组织", "", "active", "#5B7BFE", "t", "t"),
    )
    db.execute(
        """
        INSERT INTO task_lists(id, name, color, sort_order, is_default, scope)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        ("legacy_list", "历史清单", "#5B7BFE", 0, 1, "org"),
    )
    db.execute(
        """
        INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, tags_json, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy_task", "历史任务", "", "todo", "normal", "legacy_list", "", "待确认", "manual", "[]", "t", "t"),
    )
    db.execute(
        """
        INSERT INTO task_tags(id, name, scope, color)
        VALUES(?, ?, ?, ?)
        """,
        ("legacy_tag", "历史标签", "org", "#5B7BFE"),
    )

    active_id = ensure_sandbox_registry(db)
    assert active_id == DEFAULT_LOCAL_SANDBOX_ID

    for table, row_id in (
        ("clients", "legacy_client"),
        ("task_lists", "legacy_list"),
        ("tasks", "legacy_task"),
        ("task_tags", "legacy_tag"),
    ):
        row = db.fetchone(f"SELECT sandbox_id FROM {table} WHERE id = ?", (row_id,))
        assert row is not None
        assert row["sandbox_id"] == DEFAULT_LOCAL_SANDBOX_ID


def test_dashboard_and_handbook_are_filtered_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    set_sandbox_setting(
        db,
        DEFAULT_LOCAL_SANDBOX_ID,
        "cloud_session_user",
        json.dumps(
            {
                "id": "local-admin",
                "email": "local@example.com",
                "fullName": "本机管理员",
                "organizationId": "org-local",
                "organizationName": "本机组织",
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    local_client_id = create_client_record(client, "本机统计客户")
    local_task_id = create_task_record(client, "本机统计任务", local_client_id)
    db.execute(
        "INSERT INTO meetings(id, client_id, title, stage, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
        ("meeting_local", local_client_id, "本机会议", "draft", "2026-06-22T00:00:00Z", "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO handbook_entries(id, title, summary, tags_json, source_type, client_id, source_object_type, source_object_id, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("handbook_local", "本机手册", "本机", "[]", "manual", local_client_id, "task", local_task_id, "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO client_dna_documents(client_id, module_key, title, markdown_content, normalized_text, summary, file_name, content_hash, updated_at, updated_by) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (local_client_id, "overview", "本机 DNA", "text", "text", "summary", "local.md", "hash-local", "2026-06-22T00:00:00Z", "tester"),
    )

    org_a = ensure_organization_sandbox_for_session(
        db,
        organization_id="org-stats",
        organization_name="统计组织",
        cloud_api_url="https://org-stats-a.example.test",
    )
    org_a_id = org_a.id
    set_sandbox_setting(db, org_a_id, "cloud_access_token", "token-org-stats-a")
    set_sandbox_setting(db, org_a_id, "cloud_refresh_token", "refresh-org-stats-a")
    set_sandbox_setting(
        db,
        org_a_id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "org-admin",
                "email": "org@example.com",
                "fullName": "组织管理员",
                "organizationId": "org-stats",
                "organizationName": "统计组织",
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    db.execute("DELETE FROM memory_facts")
    db.execute(
        "INSERT INTO memory_facts(id, scope_type, scope_id, fact_key, fact_value, source_type, source_id, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("fact_local", "client", local_client_id, "k", "v", "manual", "source", "2026-06-22T00:00:00Z", "2026-06-22T00:00:00Z"),
    )
    dashboard_a = client.get("/api/v1/brain/dashboard")
    assert dashboard_a.status_code == 200, dashboard_a.text
    pulse_a = dashboard_a.json()["pulse"]
    assert pulse_a["meetingCount"] == 1
    assert pulse_a["memoryCount"] == 1
    assert pulse_a["handbookCount"] == 1
    assert pulse_a["dnaCount"] == 1

    org_b = ensure_organization_sandbox_for_session(
        db,
        organization_id="org-stats-b",
        organization_name="统计组织 B",
        cloud_api_url="https://org-stats-b.example.test",
    )
    org_b_id = org_b.id
    set_sandbox_setting(db, org_b_id, "cloud_access_token", "token-org-stats-b")
    set_sandbox_setting(db, org_b_id, "cloud_refresh_token", "refresh-org-stats-b")
    set_sandbox_setting(
        db,
        org_b_id,
        "cloud_session_user",
        json.dumps(
            {
                "id": "org-b-admin",
                "email": "org-b@example.com",
                "fullName": "组织 B 管理员",
                "organizationId": "org-stats-b",
                "organizationName": "统计组织 B",
                "primaryRole": "admin",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    org_client_id = create_client_record(client, "组织统计客户")
    org_task_id = create_task_record(client, "组织统计任务", org_client_id)
    db.execute("DELETE FROM memory_facts")
    db.execute(
        "INSERT INTO memory_facts(id, scope_type, scope_id, fact_key, fact_value, source_type, source_id, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("fact_local", "client", local_client_id, "k", "v", "manual", "source", "2026-06-22T00:00:00Z", "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO memory_facts(id, scope_type, scope_id, fact_key, fact_value, source_type, source_id, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("fact_org", "task", org_task_id, "k", "v", "manual", "source", "2026-06-22T00:00:00Z", "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO meetings(id, client_id, title, stage, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
        ("meeting_org", org_client_id, "组织会议", "draft", "2026-06-22T00:00:00Z", "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO handbook_entries(id, title, summary, tags_json, source_type, client_id, source_object_type, source_object_id, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("handbook_org", "组织手册", "组织", "[]", "manual", org_client_id, "task", org_task_id, "2026-06-22T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO client_dna_documents(client_id, module_key, title, markdown_content, normalized_text, summary, file_name, content_hash, updated_at, updated_by) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (org_client_id, "overview", "组织 DNA", "text", "text", "summary", "org.md", "hash-org", "2026-06-22T00:00:00Z", "tester"),
    )

    dashboard = client.get("/api/v1/brain/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    pulse = dashboard.json()["pulse"]
    assert pulse["meetingCount"] == 1
    assert pulse["memoryCount"] == 1
    assert pulse["handbookCount"] == 1
    assert pulse["dnaCount"] == 1
    handbook = client.get("/api/v1/handbook")
    assert handbook.status_code == 200, handbook.text
    assert [item["id"] for item in handbook.json()["entries"]] == ["handbook_org"]
    assert client.get("/api/v1/handbook/handbook_local").status_code == 404

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    local_dashboard = client.get("/api/v1/brain/dashboard")
    assert local_dashboard.status_code == 200, local_dashboard.text
    local_pulse = local_dashboard.json()["pulse"]
    assert local_pulse["meetingCount"] == 1
    assert local_pulse["memoryCount"] == 1
    assert local_pulse["handbookCount"] == 1
    assert local_pulse["dnaCount"] == 1
    local_handbook = client.get("/api/v1/handbook")
    assert local_handbook.status_code == 200, local_handbook.text
    assert [item["id"] for item in local_handbook.json()["entries"]] == ["handbook_local"]
    assert client.get("/api/v1/handbook/handbook_org").status_code == 404


def test_event_lines_are_filtered_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    org_a_id = create_workspace(client, "event-org-a")
    client_a_id = create_client_record(client, "事件线客户 A")
    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "事件线 A",
            "kind": "project_line",
            "primaryClientId": client_a_id,
            "summary": "只应在 A 空间可见",
        },
    )
    assert created.status_code == 200, created.text
    event_line_id = str(created.json()["id"])

    assert event_line_id in {item["id"] for item in client.get("/api/v1/event-lines").json()}
    assert client.get(f"/api/v1/event-lines/{event_line_id}").status_code == 200

    org_b_id = create_workspace(client, "event-org-b")
    assert org_b_id != org_a_id
    assert event_line_id not in {item["id"] for item in client.get("/api/v1/event-lines").json()}
    assert client.get(f"/api/v1/event-lines/{event_line_id}").status_code == 404

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    assert event_line_id in {item["id"] for item in client.get("/api/v1/event-lines").json()}


def test_workspace_json_settings_are_scoped_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    org_a_id = create_workspace(client, "settings-org-a")
    update_a = client.post(
        "/api/v1/settings/topics",
        json={
            "defaultTimeRange": "7_days",
            "requireInsightBeforeActions": False,
        },
    )
    assert update_a.status_code == 200, update_a.text
    assert update_a.json()["defaultTimeRange"] == "7_days"
    assert update_a.json()["requireInsightBeforeActions"] is False

    org_b_id = create_workspace(client, "settings-org-b")
    assert org_b_id != org_a_id
    settings_b = client.get("/api/v1/settings/topics")
    assert settings_b.status_code == 200, settings_b.text
    assert settings_b.json()["defaultTimeRange"] == "3_days"
    assert settings_b.json()["requireInsightBeforeActions"] is True

    update_b = client.post("/api/v1/settings/topics", json={"defaultTimeRange": "30_days"})
    assert update_b.status_code == 200, update_b.text
    assert update_b.json()["defaultTimeRange"] == "30_days"

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    settings_a = client.get("/api/v1/settings/topics")
    assert settings_a.status_code == 200, settings_a.text
    assert settings_a.json()["defaultTimeRange"] == "7_days"
    assert settings_a.json()["requireInsightBeforeActions"] is False


def test_task_settings_are_scoped_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    org_a_id = create_workspace(client, "task-settings-org-a")
    update_a = client.post(
        "/api/v1/settings/tasks",
        json={
            "showCompletedTasks": True,
            "defaultDueDatePreset": "today",
        },
    )
    assert update_a.status_code == 200, update_a.text
    assert update_a.json()["showCompletedTasks"] is True
    assert update_a.json()["defaultDueDatePreset"] == "today"

    org_b_id = create_workspace(client, "task-settings-org-b")
    assert org_b_id != org_a_id
    settings_b = client.get("/api/v1/settings/tasks")
    assert settings_b.status_code == 200, settings_b.text
    assert settings_b.json()["showCompletedTasks"] is False

    update_b = client.post("/api/v1/settings/tasks", json={"showCompletedTasks": False})
    assert update_b.status_code == 200, update_b.text
    assert update_b.json()["showCompletedTasks"] is False

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    settings_a = client.get("/api/v1/settings/tasks")
    assert settings_a.status_code == 200, settings_a.text
    assert settings_a.json()["showCompletedTasks"] is True
    assert settings_a.json()["defaultDueDatePreset"] == "today"


def test_topic_radars_are_filtered_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    org_a_id = create_workspace(client, "topic-org-a")
    radar_a = client.post(
        "/api/v1/topics/radars",
        json={"title": "A 空间雷达", "prompt": "只追踪 A 空间", "timeRange": "7_days"},
    )
    assert radar_a.status_code == 200, radar_a.text
    radar_a_id = str(radar_a.json()["id"])
    topics_a = client.get("/api/v1/topics")
    assert topics_a.status_code == 200, topics_a.text
    assert radar_a_id in {item["id"] for item in topics_a.json()["radars"]}

    org_b_id = create_workspace(client, "topic-org-b")
    assert org_b_id != org_a_id
    topics_b = client.get("/api/v1/topics")
    assert topics_b.status_code == 200, topics_b.text
    assert radar_a_id not in {item["id"] for item in topics_b.json()["radars"]}

    radar_b = client.post(
        "/api/v1/topics/radars",
        json={"title": "B 空间雷达", "prompt": "只追踪 B 空间", "timeRange": "3_days"},
    )
    assert radar_b.status_code == 200, radar_b.text
    radar_b_id = str(radar_b.json()["id"])

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    topics_a_again = client.get("/api/v1/topics")
    assert topics_a_again.status_code == 200, topics_a_again.text
    radar_ids = {item["id"] for item in topics_a_again.json()["radars"]}
    assert radar_a_id in radar_ids
    assert radar_b_id not in radar_ids


def test_growth_badges_and_weekly_reviews_are_filtered_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    operator_id, operator_name = current_operator_identity(client)

    org_a_id = create_workspace(client, "growth-org-a")
    task_a_id = create_task_record(client, "A 空间成长任务")
    db.execute(
        "UPDATE tasks SET owner_id = ?, owner_name = ?, creator_id = ?, sandbox_id = ? WHERE id = ?",
        (operator_id, operator_name, operator_id, org_a_id, task_a_id),
    )
    org_a_meta = db.fetchone("SELECT organization_id FROM sandboxes WHERE id = ?", (org_a_id,))
    assert org_a_meta is not None
    db.execute(
        """
        INSERT INTO weekly_reviews(id, sandbox_id, organization_id, week_label, operator_id, user_id, summary, work_free_note, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "review_growth_a",
            org_a_id,
            str(org_a_meta["organization_id"] or ""),
            "2026-W27",
            operator_id,
            operator_id,
            "A 空间复盘",
            "A 空间复盘",
            "2026-07-01T00:00:00Z",
            "2026-07-01T00:00:00Z",
        ),
    )

    badges_a = client.get("/api/v1/growth/badges")
    assert badges_a.status_code == 200, badges_a.text
    assert badge_by_id(badges_a.json(), "spark_start")["progressValue"] >= 1
    history_a = client.get("/api/v1/reviews/history")
    assert history_a.status_code == 200, history_a.text
    assert {item["weekLabel"] for item in history_a.json()["items"]} == {"2026-W27"}

    org_b_id = create_workspace(client, "growth-org-b")
    assert org_b_id != org_a_id
    badges_b = client.get("/api/v1/growth/badges")
    assert badges_b.status_code == 200, badges_b.text
    assert badge_by_id(badges_b.json(), "spark_start")["progressValue"] == 0
    history_b = client.get("/api/v1/reviews/history")
    assert history_b.status_code == 200, history_b.text
    assert history_b.json()["items"] == []

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    badges_a_again = client.get("/api/v1/growth/badges")
    assert badges_a_again.status_code == 200, badges_a_again.text
    assert badge_by_id(badges_a_again.json(), "spark_start")["progressValue"] >= 1


def test_intelligence_refresh_settings_and_source_configs_are_scoped(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    org_a_id = create_workspace(client, "intel-settings-a")
    org_b_id = create_workspace(client, "intel-settings-b")
    now = datetime.now().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO intelligence_source_configs(
            id, scope_type, scope_id, source_type, source_name, source_url_template,
            content_kinds_json, created_at, updated_at, next_due_at
        ) VALUES(?, 'global', ?, 'web_search', ?, ?, ?, ?, ?, ?)
        """,
        ("isrc_a", org_a_id, "A source", "https://a.example.test", '["profile_completion"]', now, now, "2026-01-01T00:00:00Z"),
    )
    db.execute(
        """
        INSERT INTO intelligence_source_configs(
            id, scope_type, scope_id, source_type, source_name, source_url_template,
            content_kinds_json, created_at, updated_at, next_due_at
        ) VALUES(?, 'global', ?, 'web_search', ?, ?, ?, ?, ?, ?)
        """,
        ("isrc_b", org_b_id, "B source", "https://b.example.test", '["profile_completion"]', now, now, "2026-01-01T00:00:00Z"),
    )

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    update_a = client.put("/api/v1/intelligence/refresh-cycle-settings", json={"profileCompletionHours": 11})
    assert update_a.status_code == 200, update_a.text
    assert update_a.json()["profileCompletionHours"] == 11
    source_a_due = db.fetchone("SELECT next_due_at FROM intelligence_source_configs WHERE id = 'isrc_a'")["next_due_at"]
    source_b_due = db.fetchone("SELECT next_due_at FROM intelligence_source_configs WHERE id = 'isrc_b'")["next_due_at"]
    assert source_a_due != "2026-01-01T00:00:00Z"
    assert source_b_due == "2026-01-01T00:00:00Z"

    response = client.post(f"/api/v1/workspaces/{org_b_id}/activate")
    assert response.status_code == 200, response.text
    settings_b = client.get("/api/v1/intelligence/refresh-cycle-settings")
    assert settings_b.status_code == 200, settings_b.text
    assert settings_b.json()["profileCompletionHours"] == 72

    update_b = client.put("/api/v1/intelligence/refresh-cycle-settings", json={"profileCompletionHours": 22})
    assert update_b.status_code == 200, update_b.text
    assert update_b.json()["profileCompletionHours"] == 22
    source_b_due_after = db.fetchone("SELECT next_due_at FROM intelligence_source_configs WHERE id = 'isrc_b'")["next_due_at"]
    assert source_b_due_after != "2026-01-01T00:00:00Z"

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    settings_a = client.get("/api/v1/intelligence/refresh-cycle-settings")
    assert settings_a.status_code == 200, settings_a.text
    assert settings_a.json()["profileCompletionHours"] == 11


def test_digital_assets_dashboard_only_uses_active_workspace_clients(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    org_a = ensure_organization_sandbox_for_session(
        db,
        organization_id="asset-org-a",
        organization_name="asset-org-a",
        cloud_api_url="https://asset-org-a.example.test",
    )
    org_a_id = org_a.id
    seed_workspace_session(client, org_a_id)
    client_a_id = create_client_record(client, "资产客户 A")
    org_b = ensure_organization_sandbox_for_session(
        db,
        organization_id="asset-org-b",
        organization_name="asset-org-b",
        cloud_api_url="https://asset-org-b.example.test",
    )
    org_b_id = org_b.id
    seed_workspace_session(client, org_b_id)
    client_b_id = create_client_record(client, "资产客户 B")
    assert org_b_id != org_a_id

    dashboard_b = client.get("/api/v1/digital-assets/dashboard")
    assert dashboard_b.status_code == 200, dashboard_b.text
    dumped_b = json.dumps(dashboard_b.json(), ensure_ascii=False)
    assert client_b_id in dumped_b or "资产客户 B" in dumped_b
    assert client_a_id not in dumped_b
    assert "资产客户 A" not in dumped_b

    response = client.post(f"/api/v1/workspaces/{org_a_id}/activate")
    assert response.status_code == 200, response.text
    dashboard_a = client.get("/api/v1/digital-assets/dashboard")
    assert dashboard_a.status_code == 200, dashboard_a.text
    dumped_a = json.dumps(dashboard_a.json(), ensure_ascii=False)
    assert client_a_id in dumped_a or "资产客户 A" in dumped_a
    assert client_b_id not in dumped_a
    assert "资产客户 B" not in dumped_a
