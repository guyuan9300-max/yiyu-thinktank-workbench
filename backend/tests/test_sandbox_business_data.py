from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.sandbox_registry import (  # noqa: E402
    DEFAULT_LOCAL_SANDBOX_ID,
    ensure_sandbox_registry,
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
            "listId": "list-0",
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


def test_clients_tasks_and_documents_follow_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    data_dir = client.app.state.app_state.data_dir

    local_client_id = create_client_record(client, "本机项目 A")
    local_task_id = create_task_record(client, "本机任务 A", local_client_id)
    doc_path = data_dir / "sandbox-doc-a.md"
    doc_path.write_text("# 本机文档 A\n\n只应在本机工作空间可见。", encoding="utf-8")
    db.execute(
        """
        INSERT INTO documents(id, client_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "doc_local_a",
            local_client_id,
            "本机文档 A",
            str(doc_path),
            "md",
            "manual",
            "只应在本机工作空间可见。",
            "[]",
            "2026-06-18T00:00:00Z",
        ),
    )

    assert local_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert local_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert client.get("/api/v1/documents/doc_local_a/text").status_code == 200

    org_workspace_id = create_workspace(client, "org-b")
    assert org_workspace_id != DEFAULT_LOCAL_SANDBOX_ID

    assert local_client_id not in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert local_task_id not in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert client.get("/api/v1/documents/doc_local_a/text").status_code == 404
    assert client.get(f"/api/v1/clients/{local_client_id}/workspace").status_code == 404
    assert client.get(f"/api/v1/clients/{local_client_id}/delete-preview").status_code == 404
    assert client.patch(f"/api/v1/tasks/{local_task_id}", json={"title": "不应跨空间修改"}).status_code == 404

    org_client_id = create_client_record(client, "组织项目 B")
    org_task_id = create_task_record(client, "组织任务 B", org_client_id)
    assert org_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert org_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 200, response.text
    assert local_client_id in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert org_client_id not in {item["id"] for item in client.get("/api/v1/clients").json()}
    assert local_task_id in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}
    assert org_task_id not in {item["id"] for item in client.get("/api/v1/tasks").json()["tasks"]}


def test_task_tags_can_share_names_across_workspaces(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first = client.post(
        "/api/v1/task-tags",
        json={"name": "待跟进", "scope": "org", "color": "#5B7BFE"},
    )
    assert first.status_code == 200, first.text
    first_id = str(first.json()["id"])

    create_workspace(client, "org-tag")
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

    response = client.post(f"/api/v1/workspaces/{DEFAULT_LOCAL_SANDBOX_ID}/activate")
    assert response.status_code == 200, response.text
    local_tags = client.get("/api/v1/task-tags")
    assert local_tags.status_code == 200, local_tags.text
    local_tag_ids = {item["id"] for item in local_tags.json()["tags"]}
    assert first_id in local_tag_ids
    assert second_id not in local_tag_ids


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
