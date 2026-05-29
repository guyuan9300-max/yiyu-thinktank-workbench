from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


class RecordingExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        self.submissions.append((fn, args))
        return object()

    def shutdown(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str) -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于 workspace chat start dedupe 测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def count_rows(client: TestClient, table: str, client_id: str) -> int:
    if table == "client_analysis_runs":
        row = client.app.state.app_state.db.fetchone(
            "SELECT COUNT(1) AS count FROM client_analysis_runs WHERE client_id = ?",
            (client_id,),
        )
    else:
        row = client.app.state.app_state.db.fetchone(
            """
            SELECT COUNT(1) AS count
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE t.client_id = ?
            """,
            (client_id,),
        )
    assert row is not None
    return int(row["count"] or 0)


def test_chat_start_reuses_existing_active_run_for_same_client(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步去重客户")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    first = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()
    second = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()

    assert first["reusedActiveRun"] is False
    assert second["reusedActiveRun"] is True
    assert second["dedupeReason"] == "client_active_run"
    assert second["threadId"] == first["threadId"]
    assert second["userMessage"]["id"] == first["userMessage"]["id"]
    assert second["assistantMessage"]["id"] == first["assistantMessage"]["id"]
    assert second["analysisRun"]["id"] == first["analysisRun"]["id"]
    assert count_rows(client, "client_analysis_runs", client_id) == 1
    assert count_rows(client, "chat_messages", client_id) == 2
    assert len(executor.submissions) == 1


def test_chat_start_reuses_running_run_for_same_client(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步 running 去重客户")
    client.app.state.app_state.chat_answer_executor = RecordingExecutor()

    first = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()
    client.app.state.app_state.db.execute(
        "UPDATE client_analysis_runs SET status = 'running', phase = 'generating_long_answer', updated_at = ? WHERE id = ?",
        (datetime.now().replace(microsecond=0).isoformat(), first["analysisRun"]["id"]),
    )
    second = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "另一个问题"}).json()

    assert second["reusedActiveRun"] is True
    assert second["analysisRun"]["id"] == first["analysisRun"]["id"]
    assert count_rows(client, "client_analysis_runs", client_id) == 1
    assert count_rows(client, "chat_messages", client_id) == 2


def test_chat_start_creates_new_run_after_active_run_is_recovered_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步 stale 后新建客户")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    first = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()
    stale_time = (datetime.now() - timedelta(seconds=430)).replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        UPDATE client_analysis_runs
        SET status = 'running', phase = 'generating_long_answer', updated_at = ?
        WHERE id = ?
        """,
        (stale_time, first["analysisRun"]["id"]),
    )
    second = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "重新介绍这个客户"}).json()

    assert second["reusedActiveRun"] is False
    assert second["analysisRun"]["id"] != first["analysisRun"]["id"]
    assert count_rows(client, "client_analysis_runs", client_id) == 2
    assert len(executor.submissions) == 2


def test_chat_start_creates_new_run_after_cancel(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步取消后新建客户")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    first = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()
    cancel = client.post(f"/api/v1/clients/{client_id}/analysis-runs/{first['analysisRun']['id']}/cancel")
    assert cancel.status_code == 200

    second = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "重新介绍这个客户"}).json()

    assert second["reusedActiveRun"] is False
    assert second["analysisRun"]["id"] != first["analysisRun"]["id"]
    assert count_rows(client, "client_analysis_runs", client_id) == 2
    assert len(executor.submissions) == 2


def test_chat_start_executor_unavailable_marks_created_run_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步执行器不可用客户")
    client.app.state.app_state.chat_answer_executor = None

    response = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["reusedActiveRun"] is False
    assert payload["analysisRun"]["status"] == "failed"
    assert payload["analysisRun"]["failureReason"] == "chat_executor_unavailable"
    assert payload["assistantMessage"]["status"] == "success"
    assert payload["assistantMessage"]["answerMode"] == "system_failure"
    assert count_rows(client, "client_analysis_runs", client_id) == 1
    assert count_rows(client, "chat_messages", client_id) == 2


def test_chat_start_allows_different_clients_to_have_active_runs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first_client_id = create_test_client_record(client, "异步客户 A")
    second_client_id = create_test_client_record(client, "异步客户 B")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    first = client.post(f"/api/v1/clients/{first_client_id}/workspace/chat/start", json={"prompt": "介绍 A"}).json()
    second = client.post(f"/api/v1/clients/{second_client_id}/workspace/chat/start", json={"prompt": "介绍 B"}).json()

    assert first["reusedActiveRun"] is False
    assert second["reusedActiveRun"] is False
    assert count_rows(client, "client_analysis_runs", first_client_id) == 1
    assert count_rows(client, "client_analysis_runs", second_client_id) == 1
    assert len(executor.submissions) == 2
