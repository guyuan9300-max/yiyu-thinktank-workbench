from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import AiStructuredResponse


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
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "thread scope guard",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_start_ignores_thread_from_other_client(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_a = create_client_record(client, "client-a")
    client_b = create_client_record(client, "client-b")

    def fake_generate_chat_response(*_args, **_kwargs):
        return AiStructuredResponse(
            content="这是回答。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="now",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    first = client.post(
        f"/api/v1/clients/{client_a}/workspace/chat/start",
        json={"prompt": "先创建 A 的线程"},
    )
    assert first.status_code == 200, first.text
    foreign_thread_id = first.json()["threadId"]

    second = client.post(
        f"/api/v1/clients/{client_b}/workspace/chat/start",
        json={"prompt": "介绍日慈基金会", "threadId": foreign_thread_id},
    )
    assert second.status_code == 200, second.text
    payload = second.json()

    assert payload["threadId"] != foreign_thread_id

    foreign_detail = client.get(f"/api/v1/clients/{client_a}/workspace/chat/threads/{foreign_thread_id}")
    assert foreign_detail.status_code == 200, foreign_detail.text
    foreign_messages = foreign_detail.json()["messages"]
    assert all(message["content"] != "介绍日慈基金会" for message in foreign_messages)

    new_detail = client.get(f"/api/v1/clients/{client_b}/workspace/chat/threads/{payload['threadId']}")
    assert new_detail.status_code == 200, new_detail.text
    new_messages = new_detail.json()["messages"]
    assert any(message["role"] == "user" and message["content"] == "介绍日慈基金会" for message in new_messages)
