from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import (
    AiStructuredResponse,
    DataCenterKernelResultRecord,
    DataCenterSearchResultRecord,
    RetrievalTraceRecord,
    RouteDecisionRecord,
)
from app.services.ai import AiInvocationError


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "dc-primary") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "data center primary regression",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _enable_dc_primary(client: TestClient) -> None:
    db = client.app.state.app_state.db
    db.set_setting("workspace_chat_data_center_primary", "1")
    db.set_setting("workspace_chat_use_legacy_fallback", "0")


def test_workspace_chat_uses_data_center_kernel_by_default(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-default")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="这是数据中心主链下生成的回答。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍一下这个客户"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert retrieval_summary.get("dataCenterPrimaryEnabled") is True
    assert retrieval_summary.get("kernelResultUsed") is True
    assert isinstance(retrieval_summary.get("legacyIntent"), str)
    assert isinstance(retrieval_summary.get("legacyRetrievalReason"), str)
    assert retrieval_summary.get("llmAttemptCount") == 1
    assert retrieval_summary.get("compactRetryAttempted") is False
    assert retrieval_summary.get("fallbackTemplateUsed") is False
    assert retrieval_summary.get("finalFailureStage") in {None, ""}
    assert retrieval_summary.get("routeDecisionSource") == "data_center"
    assert isinstance(retrieval_summary.get("routeDecision"), dict)
    assert "这是数据中心主链下生成的回答" in payload.get("content", "")


def test_workspace_chat_fails_open_without_compact_retry_or_template_fallback(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-retry")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "read timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户现在最值得关注的变化是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert payload.get("answerMode") == "system_failure"
    assert retrieval_summary.get("llmAttemptCount") == 1
    assert retrieval_summary.get("compactRetryAttempted") is False
    assert retrieval_summary.get("fallbackTemplateUsed") is False
    assert retrieval_summary.get("finalFailureStage") == "raw_evidence_generation_failed"
    assert retrieval_summary.get("llmErrorKind") == "read_timeout"
    assert "根据当前已入库资料" not in payload.get("content", "")
    assert "可以先这样介绍" not in payload.get("content", "")


def test_workspace_chat_preserves_partial_generation_without_template_fallback(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-partial")

    def _partial_then_timeout(_prompt, _instruction, _context, on_partial=None, **_kwargs):
        if on_partial is not None:
            on_partial(
                {
                    "stageLabel": "正在生成回答",
                    "progress": 74.0,
                    "content": "这是已保留的部分回答。",
                    "structured": {
                        "content": "这是已保留的部分回答。",
                        "judgment": "",
                        "analysis": "",
                        "actions": "",
                        "timeline": "",
                    },
                }
            )
        raise AiInvocationError("doubao", "The read operation timed out")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        _partial_then_timeout,
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请解释这个客户的核心变化"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert payload.get("answerMode") == "grounded_fallback"
    assert payload.get("content", "").startswith("这是已保留的部分回答")
    assert retrieval_summary.get("fallbackTemplateUsed") is False
    assert retrieval_summary.get("partialGenerationPreserved") is True
    assert retrieval_summary.get("failureReason") == "llm_partial_preserved_after_retry"


def test_workspace_chat_ignores_placeholder_partial_without_compact_retry(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-placeholder-partial")
    call_count = 0

    def _placeholder_then_failure(_prompt, _instruction, _context, on_partial=None, **_kwargs):
        nonlocal call_count
        call_count += 1
        if on_partial is not None:
            on_partial(
                {
                    "stageLabel": "正在直接生成长文回答",
                    "progress": 62.0,
                    "content": "千问正在基于完整材料直接生成长文回答。",
                    "structured": {
                        "content": "千问正在基于完整材料直接生成长文回答。",
                        "judgment": "",
                        "analysis": "",
                        "actions": "",
                        "timeline": "",
                    },
                }
            )
        raise AiInvocationError("doubao", "The read operation timed out")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        _placeholder_then_failure,
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "帮我总结最近一次会议"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert payload.get("answerMode") == "system_failure"
    assert payload.get("failureReason") == "llm_generation_failed"
    assert retrieval_summary.get("compactRetryAttempted") is False
    assert retrieval_summary.get("partialGenerationPreserved") is False
    assert call_count == 1
    assert "千问正在基于完整材料直接生成长文回答" not in payload.get("content", "")


def test_workspace_chat_quality_gate_warn_does_not_rewrite_answer(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-quality-warn")

    settings_response = client.post(
        "/api/v1/retrieval/settings",
        json={"qualityGateMode": "warn"},
    )
    assert settings_response.status_code == 200, settings_response.text

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="保留这段回答正文，不允许被 warn 模式改写。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )
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
            "grade": "warn",
            "reason": "unit-test",
        },
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户当前核心业务是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert payload.get("content", "").startswith("保留这段回答正文")
    assert payload.get("answerMode") != "grounded_fallback"
    assert retrieval_summary.get("qualityGateWarned") is True
    answer_quality = retrieval_summary.get("answerQuality") or {}
    assert answer_quality.get("grade") == "warn"


def test_workspace_chat_include_raw_evidence_for_intro_question(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-raw-evidence")

    captured: dict[str, object] = {}
    original_builder = app_main.build_workspace_data_center_request_from_route

    def _wrapped_builder(*, route, prompt: str, shadow: bool = True, persist_drafts: bool = False):
        captured["include_raw_evidence"] = route.includeRawEvidence
        captured["workflow"] = route.workflow
        return original_builder(
            route=route,
            prompt=prompt,
            shadow=shadow,
            persist_drafts=persist_drafts,
        )

    monkeypatch.setattr(app_main, "build_workspace_data_center_request_from_route", _wrapped_builder)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="介绍回答",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍一下这个客户"},
    )
    assert response.status_code == 200, response.text
    assert captured.get("include_raw_evidence") is True
    assert captured.get("workflow") == "synthesis"


def test_workspace_chat_prefers_data_center_route_decision_in_metadata(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-route-source")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="路由检查回答",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "最新会议纪要有哪些要点？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}
    route_decision = retrieval_summary.get("routeDecision") or {}

    assert retrieval_summary.get("routeDecisionSource") == "data_center"
    assert isinstance(route_decision, dict)
    assert isinstance(route_decision.get("intent"), str)


def test_workspace_chat_followups_are_consulting_and_ignore_search_suggestions_for_synthesis(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    _enable_dc_primary(client)
    client_id = create_client_record(client, "dc-primary-followups")

    def _fake_kernel(_db, *, request, **_kwargs):
        route = RouteDecisionRecord(intent="general", routeReason="unit-test")
        return DataCenterKernelResultRecord(
            scope=request.scope,
            routeDecision=route,
            retrievalTrace=RetrievalTraceRecord(routeDecision=route),
            searchResult=DataCenterSearchResultRecord(
                query=request.prompt,
                routeDecision=route,
                retrievalTrace=RetrievalTraceRecord(routeDecision=route),
                suggestedFollowups=["这个判断出自哪份原文？"],
            ),
        )

    monkeypatch.setattr(app_main, "resolve_data_center_kernel", _fake_kernel)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="日慈正在推进从项目服务交付转向关系生态建设的战略升级。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content=(
                "官方稿什么时候完成？\n"
                "这个战略落地时最可能卡在哪个组织能力上？\n"
                "这个判断出自哪份原文？"
            ),
            judgment="",
            analysis="",
            actions="",
            timeline="",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "日慈战略重点是什么？"},
    )
    assert response.status_code == 200, response.text
    retrieval_summary = response.json().get("retrievalSummary") or {}
    followups = retrieval_summary.get("suggestedFollowups") or []

    assert retrieval_summary.get("followupScenario") == "strategy_judgment"
    assert retrieval_summary.get("followupGenerationMode") == "consulting"
    assert retrieval_summary.get("followupRejectedCount") == 2
    assert len(followups) == 3
    assert any("组织能力" in item for item in followups)
    assert all("哪份原文" not in item and "官方稿" not in item for item in followups)
