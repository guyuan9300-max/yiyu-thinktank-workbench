from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.workspace_chat_diagnostics import build_workspace_chat_diagnostics


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "诊断证据计数客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于 workspace chat diagnostics 测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def seed_assistant_message(
    client: TestClient,
    client_id: str,
    *,
    suffix: str,
    retrieval_summary: dict[str, object],
    evidence: list[dict[str, object]] | None = None,
    answer_mode: str = "grounded_answer",
) -> None:
    db = client.app.state.app_state.db
    thread_id = f"thread_diag_{suffix}"
    user_message_id = f"msg_user_diag_{suffix}"
    assistant_message_id = f"msg_assistant_diag_{suffix}"
    created_at = f"2026-05-03T00:00:{int(suffix):02d}"
    db.execute(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        (thread_id, client_id, f"诊断线程 {suffix}", created_at, created_at),
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
        (user_message_id, thread_id, "测试问题", created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json,
            status, created_at
        )
        VALUES(?, ?, 'assistant', ?, NULL, 'AI · doubao', 1, 'doubao', ?, 'sufficient', NULL, '{}', ?, ?, 'success', ?)
        """,
        (
            assistant_message_id,
            thread_id,
            "诊断回答",
            answer_mode,
            json.dumps(retrieval_summary, ensure_ascii=False),
            json.dumps(evidence or [], ensure_ascii=False),
            created_at,
        ),
    )


def diagnostics_for(client: TestClient, client_id: str) -> dict[str, object]:
    return build_workspace_chat_diagnostics(
        client.app.state.app_state.db,
        data_dir=client.app.state.app_state.data_dir,
        client_id=client_id,
        recent_messages=20,
    )


def test_diagnostics_uses_kernel_selected_evidence_count(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    seed_assistant_message(
        client,
        client_id,
        suffix="01",
        retrieval_summary={"dataCenterPrimaryEnabled": True, "kernelSelectedEvidenceCount": 5},
        evidence=[],
    )

    result = diagnostics_for(client, client_id)
    retrieval = result["breakdown"]["retrieval"]["details"]  # type: ignore[index]

    assert retrieval["zeroEvidenceCount"] == 0
    assert retrieval["selectedEvidenceCountTotal"] == 5
    assert retrieval["selectedEvidenceCountSources"] == {"kernelSelectedEvidenceCount": 1}


def test_diagnostics_keeps_legacy_selected_evidence_count_compatible(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    seed_assistant_message(
        client,
        client_id,
        suffix="01",
        retrieval_summary={"selectedEvidenceCount": 4},
        evidence=[],
    )

    retrieval = diagnostics_for(client, client_id)["breakdown"]["retrieval"]["details"]  # type: ignore[index]

    assert retrieval["zeroEvidenceCount"] == 0
    assert retrieval["selectedEvidenceCountTotal"] == 4
    assert retrieval["selectedEvidenceCountSources"] == {"selectedEvidenceCount": 1}


def test_diagnostics_falls_back_to_evidence_json_without_double_counting(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    seed_assistant_message(
        client,
        client_id,
        suffix="01",
        retrieval_summary={},
        evidence=[
            {"id": "ev1", "title": "证据 1", "excerpt": "正文", "sourceType": "raw_chunk", "matchedTerms": []},
            {"id": "ev2", "title": "证据 2", "excerpt": "正文", "sourceType": "raw_chunk", "matchedTerms": []},
            {"id": "ev3", "title": "证据 3", "excerpt": "正文", "sourceType": "raw_chunk", "matchedTerms": []},
        ],
    )

    retrieval = diagnostics_for(client, client_id)["breakdown"]["retrieval"]["details"]  # type: ignore[index]

    assert retrieval["zeroEvidenceCount"] == 0
    assert retrieval["selectedEvidenceCountTotal"] == 3
    assert retrieval["selectedEvidenceCountSources"] == {"evidence_json": 1}


def test_diagnostics_counts_zero_evidence_once_when_all_sources_empty(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    seed_assistant_message(
        client,
        client_id,
        suffix="01",
        retrieval_summary={},
        evidence=[],
    )

    retrieval = diagnostics_for(client, client_id)["breakdown"]["retrieval"]["details"]  # type: ignore[index]

    assert retrieval["zeroEvidenceCount"] == 1
    assert retrieval["selectedEvidenceCountTotal"] == 0
    assert retrieval["selectedEvidenceCountSources"] == {"none": 1}


def test_system_failure_with_kernel_evidence_is_not_zero_evidence(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    seed_assistant_message(
        client,
        client_id,
        suffix="01",
        retrieval_summary={"kernelSelectedEvidenceCount": 2, "dataCenterPrimaryEnabled": True},
        evidence=[],
        answer_mode="system_failure",
    )

    result = diagnostics_for(client, client_id)
    retrieval = result["breakdown"]["retrieval"]["details"]  # type: ignore[index]

    assert retrieval["zeroEvidenceCount"] == 0
    assert retrieval["selectedEvidenceCountTotal"] == 2
    assert result["systemFailureRate"] == 1.0
