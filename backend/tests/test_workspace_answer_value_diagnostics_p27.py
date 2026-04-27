from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "workspace-answer-value-p27") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace answer diagnostics p27",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _insert_message(
    client: TestClient,
    *,
    thread_id: str,
    message_id: str,
    answer_mode: str,
    failure_reason: str | None,
    retrieval_summary: dict[str, object],
) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        )
        VALUES(?, ?, 'assistant', ?, '{}', 'AI · test', 1, 'doubao',
               ?, 'partial', ?, '{"totalMs":1000,"llmMs":300}', ?, '[]', 'success', ?)
        """,
        (
            message_id,
            thread_id,
            f"{message_id} content",
            answer_mode,
            failure_reason,
            to_json(retrieval_summary),
            now,
        ),
    )


def test_workspace_answer_value_diagnostics_p27(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db
    thread_id = "thread_workspace_value_p27"
    now = datetime.now().replace(microsecond=0).isoformat()
    db.execute(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        (thread_id, client_id, "workspace value", now, now),
    )

    _insert_message(
        client,
        thread_id=thread_id,
        message_id="msg_p27_1",
        answer_mode="grounded_fallback",
        failure_reason="llm_timeout",
        retrieval_summary={
            "fallbackReason": "llm_timeout",
            "fallbackPresentationMode": "compact_user_answer",
            "kernelPrimaryUsed": True,
            "kernelPrimaryFallbackUsed": True,
            "generationFailureDetail": "read timeout",
            "answerQuality": {"grade": "fail", "officialBoundaryViolation": False, "candidateAsOfficialRisk": False},
            "selectedEvidenceCount": 0,
        },
    )
    _insert_message(
        client,
        thread_id=thread_id,
        message_id="msg_p27_2",
        answer_mode="grounded_fallback",
        failure_reason="state_only",
        retrieval_summary={
            "fallbackReason": "state_only",
            "fallbackPresentationMode": "state_cards_only",
            "kernelPrimaryUsed": True,
            "kernelPrimaryFallbackUsed": False,
            "answerQuality": {"grade": "warn", "officialBoundaryViolation": False, "candidateAsOfficialRisk": False},
            "selectedEvidenceCount": 1,
        },
    )
    _insert_message(
        client,
        thread_id=thread_id,
        message_id="msg_p27_3",
        answer_mode="low_confidence_answer",
        failure_reason="low_confidence",
        retrieval_summary={
            "kernelPrimaryUsed": False,
            "answerQuality": {"grade": "warn", "officialBoundaryViolation": False, "candidateAsOfficialRisk": False},
            "selectedEvidenceCount": 2,
        },
    )
    _insert_message(
        client,
        thread_id=thread_id,
        message_id="msg_p27_4",
        answer_mode="grounded_answer",
        failure_reason=None,
        retrieval_summary={
            "kernelPrimaryUsed": True,
            "answerQuality": {"grade": "pass", "officialBoundaryViolation": False, "candidateAsOfficialRisk": False},
            "workspaceAnswerFinalization": {
                "content": "可用回答",
                "answerMode": "grounded_answer",
                "userVisibleQualityStatus": "ready",
                "shouldShowRetryBanner": False,
                "qualityGrade": "pass",
                "internalGenerationStatus": "quality_passed",
                "notes": [],
            },
            "selectedEvidenceCount": 3,
        },
    )

    response = client.get(f"/api/v1/runtime/workspace-answer-value-diagnostics?clientId={client_id}&recentMessages=20")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload.get("retryBannerWouldShowCount") == 2
    assert float(payload.get("retryBannerWouldShowRate") or 0.0) == 0.5
    assert payload.get("groundedFallbackCount") == 2
    assert payload.get("lowConfidenceCount") == 1
    assert payload.get("groundedAnswerCount") == 1
    assert float(payload.get("kernelPrimaryUsedRate") or 0.0) > 0.5
    assert float(payload.get("llmTimeoutRate") or 0.0) > 0.0
    assert isinstance(payload.get("recommendedFixes"), list) and payload["recommendedFixes"]
