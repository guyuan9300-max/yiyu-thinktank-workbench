# backend/tests/test_strategic_learning_workbench.py

```python
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


def ensure_default_list_id(client: TestClient) -> str:
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200
    return board.json()["lists"][0]["id"]


def create_client_record(client: TestClient, *, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益合作",
            "type": "client",
            "intro": f"{name} 项目资料",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def create_task_record(
    client: TestClient,
    *,
    list_id: str,
    title: str,
    desc: str,
    client_id: str | None = None,
    business_category: str = "strategic_accompaniment",
) -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "normal",
            "listId": list_id,
            "dueDate": "2026-04-21",
            "ddl": "2026-04-21",
            "ownerName": "测试用户",
            "ownerId": None,
            "collaboratorIds": [],
            "tagIds": [],
            "clientId": client_id,
            "businessCategory": business_category,
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def lesson_titles(payload: dict) -> list[str]:
    return [item["title"] for item in payload["genericLessons"]]


def test_growth_workbench_default_mode_still_works(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/api/v1/growth/workbench")
    assert response.status_code == 200
    payload = response.json()
    assert "learningSummary" in payload
    assert "sourceMode" in payload


def test_strategic_growth_workbench_empty_returns_starter_presets(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/api/v1/growth/workbench?mode=strategic")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scopeMode"] == "strategic"
    assert payload["sourceMode"] == "empty"
    assert payload["learningSummary"]["generator"] == "rules"
    assert payload["genericLessons"]
    assert any("机构介绍三段式" in item["title"] for item in payload["genericLessons"])
    assert payload["reasoningTrace"]["mode"] == "rules_only"
    assert payload["reasoningTrace"]["aiContribution"] == []


def test_strategic_intro_task_matches_intro_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="日慈基金会")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="介绍日慈基金会，给出简洁清晰的项目资料",
        desc="请整理机构背景与项目重点，并形成可读的一页介绍。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "机构介绍三段式" in titles
    assert "项目介绍五要素" in titles or "一页简介写作卡" in titles
    assert "事实、判断、建议分离卡" in titles
    assert payload["learningSummary"]["generator"] == "rules"


def test_strategic_meeting_task_matches_meeting_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="为爱黔行")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="提炼最新会议纪要，整理下一步行动项",
        desc="把会议讨论拆成事实、决定、行动、风险，并明确下一步责任人。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "会议纪要四分法" in titles
    assert "下一步行动提取卡" in titles


def test_strategic_judgment_task_matches_judgment_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="乡基会")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="把待确认判断整理成正式判断草案",
        desc="补齐证据后给出正式判断，并说明边界与风险。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "候选判断转正式判断卡" in titles
    assert "证据够不够检查卡" in titles
    assert payload["reasoningTrace"]["mode"] == "rules_only"
    assert payload["reasoningTrace"]["aiContribution"] == []

```
