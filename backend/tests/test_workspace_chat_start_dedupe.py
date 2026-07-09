from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.services.ai import AiHealth


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


def test_chat_start_creates_new_run_for_different_prompt_while_running(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "异步 running 去重客户")
    client.app.state.app_state.chat_answer_executor = RecordingExecutor()

    first = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"}).json()
    client.app.state.app_state.db.execute(
        "UPDATE client_analysis_runs SET status = 'running', phase = 'generating_long_answer', updated_at = ? WHERE id = ?",
        (datetime.now().replace(microsecond=0).isoformat(), first["analysisRun"]["id"]),
    )
    second = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "另一个问题"}).json()

    assert second["reusedActiveRun"] is False
    assert second["analysisRun"]["id"] != first["analysisRun"]["id"]
    assert count_rows(client, "client_analysis_runs", client_id) == 2
    assert count_rows(client, "chat_messages", client_id) == 4


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


def test_packaged_chat_start_allows_org_cloud_proxy_without_local_fingerprint(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "组织云代理客户")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    monkeypatch.setattr(app_main, "BACKEND_RUNTIME_MODE", "packaged")
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "get_health",
        lambda: AiHealth(
            provider="openai_compatible",
            provider_label="豆包火山方舟",
            base_url="cloud://org-ai",
            model="doubao-seed-2-1-pro-260628",
            ready=True,
            detail="组织 AI 已启用，成员通过云端代调用，不下发管理员 API Key。",
            credential_source="organization_cloud_proxy",
            fingerprint=None,
            profile_key="org_cloud_proxy",
            mode="cloud",
        ),
    )

    response = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"})

    assert response.status_code == 200
    assert response.json()["analysisRun"]["id"]
    assert len(executor.submissions) == 1


def test_packaged_chat_start_still_blocks_direct_provider_without_fingerprint(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "缺密钥客户")
    client.app.state.app_state.chat_answer_executor = RecordingExecutor()

    monkeypatch.setattr(app_main, "BACKEND_RUNTIME_MODE", "packaged")
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "get_health",
        lambda: AiHealth(
            provider="openai_compatible",
            provider_label="豆包火山方舟",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model="doubao-seed-2-1-pro-260628",
            ready=True,
            detail="凭证已配置。",
            credential_source="local",
            fingerprint=None,
            profile_key="unified",
            mode="cloud",
        ),
    )

    response = client.post(f"/api/v1/clients/{client_id}/workspace/chat/start", json={"prompt": "介绍这个客户"})

    assert response.status_code == 409
    assert "API Key 未配置" in response.json()["detail"]


def test_short_connectivity_prompt_uses_lightweight_direct_path(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "工作台轻量直答客户")
    executor = RecordingExecutor()
    client.app.state.app_state.chat_answer_executor = executor

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_lightweight_text_response",
        lambda *args, **kwargs: "星丛普通成员 AI 可用。",
    )
    model_snapshot = {
        "profileKey": "online_primary",
        "provider": "openai_compatible",
        "model": "doubao-seed-2-1-pro-260628",
        "modelLabel": "豆包 Seed 2.1",
        "mode": "cloud",
    }
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "resolved_model_snapshot",
        lambda *, task_kind="default": model_snapshot,
    )
    monkeypatch.setattr(client.app.state.app_state.ai, "last_model_snapshot", lambda: model_snapshot)

    def fail_if_data_center_runs(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("short connectivity prompt should not run data-center retrieval")

    monkeypatch.setattr(app_main, "resolve_data_center_kernel", fail_if_data_center_runs)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "请只回复：星丛普通成员 AI 可用。", "creativityMode": "creative"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(executor.submissions) == 1

    fn, args = executor.submissions[0]
    fn(*args)

    assistant_id = payload["assistantMessage"]["id"]
    row = client.app.state.app_state.db.fetchone(
        "SELECT content, answer_mode, evidence_status, retrieval_summary_json FROM chat_messages WHERE id = ?",
        (assistant_id,),
    )
    assert row is not None
    assert row["content"] == "星丛普通成员 AI 可用。"
    assert row["answer_mode"] == "general_answer"
    assert row["evidence_status"] == "none"
    summary = json.loads(str(row["retrieval_summary_json"] or "{}"))
    assert summary["lightweightDirect"] is True
    assert summary["creativityMode"] == "creative"
    assert summary["materialAccessMode"] == "lightweight_direct"
    assert summary["retrievalStage"] == "skipped_lightweight_direct"

    run_row = client.app.state.app_state.db.fetchone(
        "SELECT status, long_answer_status, summary_status FROM client_analysis_runs WHERE id = ?",
        (payload["analysisRun"]["id"],),
    )
    assert run_row is not None
    assert run_row["status"] == "completed"
    assert run_row["long_answer_status"] == "ready"
    assert run_row["summary_status"] == "ready"
