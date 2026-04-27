from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.ai import AiInvocationError


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "dc-primary-finalizer-p27") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "data center primary finalizer p27",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _enable_dc_primary(client: TestClient) -> None:
    db = client.app.state.app_state.db
    db.set_setting("workspace_chat_data_center_primary", "1")
    db.set_setting("workspace_chat_use_legacy_fallback", "0")


def test_workspace_chat_data_center_primary_applies_finalizer_after_timeout(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client)

    call_counter = {"count": 0}

    def _generate_chat_response(*_args, **_kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            raise AiInvocationError("doubao", "read timeout")
        return AiStructuredResponse(
            content="基于现有资料，客户核心业务聚焦资源支持与项目服务。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", _generate_chat_response)
    monkeypatch.setattr(
        app_main,
        "validate_answer_quality",
        lambda **_kwargs: {
            "hasDirectAnswer": True,
            "evidenceListOnly": False,
            "evidenceQuoteOnly": False,
            "leakedInternalMarkers": [],
            "candidateAsOfficialRisk": False,
            "officialBoundaryViolation": False,
            "missingRawEvidenceForIntent": False,
            "offTopicRisk": False,
            "factSlotHit": True,
            "factSlotMissingReason": None,
            "grade": "pass",
            "reason": "unit-test",
        },
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 核心业务是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}
    finalization = retrieval_summary.get("workspaceAnswerFinalization") or {}

    assert payload.get("answerMode") == "grounded_answer"
    assert finalization.get("shouldShowRetryBanner") is False
    assert finalization.get("userVisibleQualityStatus") in {"ready", "usable_with_boundary"}
    assert retrieval_summary.get("llmErrorHiddenFromUserBecauseAnswerPassedQuality") is True
