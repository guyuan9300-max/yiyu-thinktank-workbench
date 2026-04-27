from __future__ import annotations

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


def create_client_record(client: TestClient, name: str = "prep-mode-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "prep mode p2",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_task_record(client: TestClient, client_id: str, title: str = "准备任务") -> str:
    lists = client.get("/api/v1/task-lists")
    assert lists.status_code == 200, lists.text
    list_id = lists.json()["lists"][0]["id"]

    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": "用于 prep mode 测试",
            "listId": list_id,
            "clientId": client_id,
            "ownerName": "测试",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_prep_mode_returns_structured_pack(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    task_id = create_task_record(client, client_id)

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "task_detail",
                "scopeType": "task",
                "scopeId": task_id,
                "taskId": task_id,
                "clientId": client_id,
            },
            "prompt": "这条任务下一步应该做什么？",
            "mode": "prep",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["prepResult"] is not None
    assert payload["prepResult"]["prepType"] in {"task", "meeting", "client_conversation"}
    assert "knownFacts" in payload["prepResult"]
    assert payload["proposalDrafts"] == []
