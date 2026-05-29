from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import (
    AnswerMaterialRecord,
    ContextQualityRecord,
    DataCenterKernelResultRecord,
    DataCenterScopeRecord,
    EvidenceItem,
    PageContextPackRecord,
    RetrievalTraceRecord,
    RouteDecisionRecord,
)
from app.services.ai import AiInvocationError


def _main_py() -> str:
    return (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")


def _function_body(source: str, function_name: str) -> str:
    marker = f"    def {function_name}("
    start = source.index(marker)
    next_function = source.find("\n    def ", start + len(marker))
    assert next_function != -1
    return source[start:next_function]


def test_data_center_primary_never_uses_local_retrieval_fallback() -> None:
    body = _function_body(_main_py(), "resolve_chat_answer_data_center_primary")

    assert "build_local_retrieval_fallback(" not in body
    assert "llm_local_fallback_after_primary_failure" not in body


def test_data_center_primary_llm_failure_is_explicit_system_failure() -> None:
    body = _function_body(_main_py(), "resolve_chat_answer_data_center_primary")

    assert "本轮模型没有成功完成回答。系统已命中相关资料，但没有生成可交付文本。" in body
    assert 'answer_mode = "system_failure"' in body
    assert 'failure_reason = "llm_generation_failed"' in body
    assert 'generation_mode="skipped_system_failure"' in body


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def _create_client_record(client: TestClient) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": "Primary fallback 测试客户",
            "alias": "Primary fallback 测试客户",
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于 data center primary fallback 测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _kernel_result(client_id: str, prompt: str) -> DataCenterKernelResultRecord:
    route = RouteDecisionRecord(
        intent="general",
        routeMode="state_first",
        dataSources=["raw_docs"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        shouldUseStatePool=True,
        confidence=0.9,
        routeReason="test_data_center_primary",
    )
    evidence = EvidenceItem(
        id="ev_primary_1",
        title="客户战略资料.docx",
        excerpt="这是一段真实命中的数据中心证据，用于证明有 evidence 时也不能生成本地伪答案。",
        sourceType="raw_document",
        documentId="doc_primary_1",
        path="/tmp/客户战略资料.docx",
        score=3.0,
        retrievalStage="raw_chunk",
    )
    quality = ContextQualityRecord(
        stateObjectCount=1,
        evidenceCardCount=1,
        rawEvidenceCount=1,
        contextQuality="usable",
        canUseAnalysisFirst=True,
    )
    scope = DataCenterScopeRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId=client_id,
        clientId=client_id,
    )
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId=client_id,
        clientId=client_id,
        intent="general",
        rawEvidence=[evidence.model_dump(mode="json")],
        sourceSummary={"rawEvidence": 1},
        quality=quality,
    )
    return DataCenterKernelResultRecord(
        scope=scope,
        pageContext=page_context,
        routeDecision=route,
        retrievalTrace=RetrievalTraceRecord(
            routeDecision=route,
            mergedHitCount=1,
            rawChunkHitCount=1,
            readingPassCount=1,
            selectedDocumentFamilyCount=1,
            selectedCanonicalKinds=["raw_document"],
            latencyMs={"totalMs": 1.0},
        ),
        answerMaterial=AnswerMaterialRecord(
            directAnswerSeed="测试资料已命中",
            keyFacts=["测试资料已命中"],
            evidenceHighlights=[evidence],
            sourceLabels=["客户战略资料.docx"],
        ),
        quality=quality,
    )


def test_primary_llm_failure_with_evidence_returns_system_failure_without_template(monkeypatch, tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    client_id = _create_client_record(client)

    def fake_kernel(db, *, data_dir, request, ai_service):  # type: ignore[no-untyped-def]
        return _kernel_result(client_id, request.prompt)

    def fake_route_page_query(*args, **kwargs):  # type: ignore[no-untyped-def]
        return RouteDecisionRecord(
            intent="general",
            routeMode="state_first",
            dataSources=["raw_docs"],
            retrievalMode="hybrid",
            shouldUseRawEvidence=True,
            confidence=0.9,
            routeReason="test_route",
        )

    def fail_generation(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AiInvocationError("doubao", "read timeout")

    def fail_followup(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("followup generation should be skipped after system failure")

    monkeypatch.setattr(app_main, "resolve_data_center_kernel", fake_kernel)
    monkeypatch.setattr(app_main, "route_page_query", fake_route_page_query)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_raw_evidence_response", fail_generation)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fail_followup)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请介绍这个客户"},
    )

    assert response.status_code == 200
    payload = response.json()
    summary = payload["retrievalSummary"]
    assert payload["answerMode"] == "system_failure"
    assert payload["failureReason"] == "llm_generation_failed"
    assert payload["evidenceStatus"] == "partial"
    assert payload["evidence"]
    assert "本轮模型没有成功完成回答" in payload["content"]
    assert "根据当前已入库资料" not in payload["content"]
    assert "可以先这样介绍" not in payload["content"]
    assert summary["fallbackTemplateUsed"] is False
    assert summary["finalFailureStage"] == "raw_evidence_generation_failed"
    assert summary["failureReason"] == "llm_generation_failed"
    assert summary["followupGenerationMode"] == "skipped_system_failure"
    assert summary["suggestedFollowups"] == []
    assert summary["answerMaterialSummary"]["evidenceHighlightCount"] == 1
