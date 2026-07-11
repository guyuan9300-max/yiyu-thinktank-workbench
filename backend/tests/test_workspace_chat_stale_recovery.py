from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "异步 stale 测试客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于异步 stale recovery 测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def iso_seconds_ago(seconds: int) -> str:
    return (datetime.now() - timedelta(seconds=seconds)).replace(microsecond=0).isoformat()


def seed_loading_chat(
    client: TestClient,
    client_id: str,
    *,
    suffix: str,
    assistant_age_seconds: int,
    assistant_content: str = "数据中心主链已就绪，正在组织回答……",
    run_status: str | None = "running",
    run_phase: str = "generating_long_answer",
    run_updated_age_seconds: int = 60,
) -> dict[str, str]:
    db = client.app.state.app_state.db
    thread_id = f"thread_stale_{suffix}"
    user_message_id = f"msg_user_stale_{suffix}"
    assistant_message_id = f"msg_assistant_stale_{suffix}"
    run_id = f"analysis_stale_{suffix}"
    thread_created_at = iso_seconds_ago(max(assistant_age_seconds, run_updated_age_seconds) + 10)
    assistant_created_at = iso_seconds_ago(assistant_age_seconds)
    run_updated_at = iso_seconds_ago(run_updated_age_seconds)
    db.execute(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        (thread_id, client_id, f"stale recovery {suffix}", thread_created_at, run_updated_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json,
            status, created_at
        )
        VALUES(?, ?, 'user', ?, NULL, NULL, 0, NULL, NULL, NULL, NULL, '{}', '{}', '[]', 'success', ?)
        """,
        (user_message_id, thread_id, "请生成一段长回答", thread_created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json,
            status, created_at
        )
        VALUES(?, ?, 'assistant', ?, NULL, 'AI · doubao', 0, 'doubao', NULL, NULL, NULL, '{}', ?, '[]', 'loading', ?)
        """,
        (
            assistant_message_id,
            thread_id,
            assistant_content,
            json.dumps({"phase": "generating", "stageLabel": "正在生成回答"}, ensure_ascii=False),
            assistant_created_at,
        ),
    )
    if run_status is not None:
        db.execute(
            """
            INSERT INTO client_analysis_runs(
                id, client_id, thread_id, user_message_id, assistant_message_id, question,
                status, phase, progress, progress_floor, progress_ceiling, stage_label, elapsed_ms,
                evidence_summary_json, long_answer, structured_summary_json, long_answer_status, summary_status,
                answer_mode, llm_invoked, provider_used, failure_reason, timing_json, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, 68, 58, 96, '正在生成回答', 0,
                   '{}', NULL, '{}', 'pending', 'pending', NULL, 1, 'doubao', NULL, '{}', ?, ?)
            """,
            (
                run_id,
                client_id,
                thread_id,
                user_message_id,
                assistant_message_id,
                "请生成一段长回答",
                run_status,
                run_phase,
                thread_created_at,
                run_updated_at,
            ),
        )
    return {
        "threadId": thread_id,
        "userMessageId": user_message_id,
        "assistantMessageId": assistant_message_id,
        "runId": run_id,
    }


def test_stale_recovery_does_not_fail_running_long_answer_before_threshold(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    ids = seed_loading_chat(
        client,
        client_id,
        suffix="fresh_long",
        assistant_age_seconds=180,
        run_phase="generating_long_answer",
        run_updated_age_seconds=60,
    )

    response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{ids['runId']}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    row = client.app.state.app_state.db.fetchone("SELECT status, answer_mode FROM chat_messages WHERE id = ?", (ids["assistantMessageId"],))
    assert row["status"] == "loading"
    assert row["answer_mode"] is None


def test_stale_recovery_fails_running_long_answer_after_threshold(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    ids = seed_loading_chat(
        client,
        client_id,
        suffix="stale_long",
        assistant_age_seconds=500,
        run_phase="generating_long_answer",
        run_updated_age_seconds=430,
    )

    response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{ids['runId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["failureReason"] == "analysis_run_stale_recovered"
    message = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{ids['assistantMessageId']}").json()
    assert message["status"] == "success"
    assert message["answerMode"] == "system_failure"
    assert message["failureReason"] == "analysis_run_stale_recovered"
    assert message["retrievalSummary"]["staleRecoveryBasis"] == "analysis_run.generating_long_answer.updated_at"
    assert message["retrievalSummary"]["staleThresholdSeconds"] == 90


def test_stale_recovery_preserves_partial_loading_content(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    partial = "这是模型已经生成的一段有效回答，应该被保留下来，而不是被失败占位文案覆盖。"
    ids = seed_loading_chat(
        client,
        client_id,
        suffix="partial",
        assistant_age_seconds=500,
        assistant_content=partial,
        run_phase="generating_long_answer",
        run_updated_age_seconds=430,
    )

    response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{ids['runId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "llm_partial_preserved_after_stale_recovery"
    message = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{ids['assistantMessageId']}").json()
    assert message["content"] == partial
    assert message["answerMode"] == "grounded_fallback"
    assert message["failureReason"] == "llm_partial_preserved_after_stale_recovery"
    assert message["retrievalSummary"]["partialGenerationPreserved"] is True


def test_analysis_run_poll_only_recovers_requested_run(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    first = seed_loading_chat(
        client,
        client_id,
        suffix="scope_one",
        assistant_age_seconds=500,
        run_phase="generating_long_answer",
        run_updated_age_seconds=430,
    )
    second = seed_loading_chat(
        client,
        client_id,
        suffix="scope_two",
        assistant_age_seconds=500,
        run_phase="generating_long_answer",
        run_updated_age_seconds=430,
    )

    response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{first['runId']}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    second_run = client.app.state.app_state.db.fetchone("SELECT status FROM client_analysis_runs WHERE id = ?", (second["runId"],))
    second_message = client.app.state.app_state.db.fetchone("SELECT status FROM chat_messages WHERE id = ?", (second["assistantMessageId"],))
    assert second_run["status"] == "running"
    assert second_message["status"] == "loading"


def test_message_poll_recovers_only_requested_orphan_loading_message(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    first = seed_loading_chat(
        client,
        client_id,
        suffix="orphan_one",
        assistant_age_seconds=1000,
        run_status=None,
    )
    second = seed_loading_chat(
        client,
        client_id,
        suffix="orphan_two",
        assistant_age_seconds=1000,
        run_status=None,
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{first['assistantMessageId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["answerMode"] == "system_failure"
    assert payload["failureReason"] == "orphan_loading_message_recovered"
    second_message = client.app.state.app_state.db.fetchone("SELECT status FROM chat_messages WHERE id = ?", (second["assistantMessageId"],))
    assert second_message["status"] == "loading"
