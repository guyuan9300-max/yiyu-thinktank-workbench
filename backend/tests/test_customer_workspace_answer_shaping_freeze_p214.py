from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    AnswerPolicyRecord,
    PageContextPackRecord,
    RouteDecisionRecord,
)
from app.services.answer_layer import build_answer_material, build_answer_plan, build_grounded_answer_context
from app.services.data_center_quality import validate_answer_quality
from app.services.question_focus import (
    build_question_focus_frame,
    coverage_targets_for_focus,
    score_focus_role_match,
)
from app.services.query_router import route_page_query
from app.services.workspace_data_center_adapter import build_open_workspace_answer_context
from app.services.workspace_query_router import route_workspace_query


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


class _DummyKernelResult:
    def __init__(self, page_context, answer_material):
        self.pageContext = page_context
        self.answerMaterial = answer_material


def test_workspace_chat_general_route_stays_open_and_tool_only() -> None:
    workspace_route = route_workspace_query(
        prompt="最近一次会议讲了什么",
        client_id="client_test",
    )
    assert workspace_route.workflow == "synthesis"
    assert workspace_route.intent == "general"
    assert workspace_route.dataSources == ["raw_docs", "document_cards"]

    page_route = route_page_query(
        None,
        page="workspace_chat",
        prompt="最近一次会议讲了什么",
        page_context=PageContextPackRecord(
            page="workspace_chat",
            scopeType="client",
            scopeId="client_test",
            clientId="client_test",
            intent="meeting_summary",
        ),
    )
    assert page_route.intent == "general"
    assert page_route.dataSources == ["raw_docs", "document_cards"]
    assert page_route.shouldUseStatePool is False
    assert page_route.shouldUseMeetingContext is False


def test_question_focus_is_diagnostic_only_for_workspace_chat() -> None:
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
    )
    frame = build_question_focus_frame(
        prompt="介绍CFFC",
        route_decision=route,
        page_context=PageContextPackRecord(
            page="workspace_chat",
            scopeType="client",
            scopeId="client_test",
            clientId="client_test",
            intent="general",
        ),
    )
    assert frame.goal == "explain"
    assert frame.subjectFacet == "general"
    assert frame.suppressedExpansions == []
    assert frame.preferredRoles == []
    assert frame.discouragedRoles == []
    assert coverage_targets_for_focus(frame) == []
    assert score_focus_role_match(frame, ["institution_identity"]) == (0.0, [])


def test_answer_layer_stays_open_without_shape_scaffolds() -> None:
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="general",
    )
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
    )
    plan = build_answer_plan(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    assert plan.answerShape == "open_answer"
    assert plan.requiredSections == []
    assert plan.mustDiscloseBoundary is False
    assert plan.maxEvidenceItems == 24
    assert plan.maxAnswerChars == 12000

    material = build_answer_material(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        retrieval_evidence=[],
        answer_plan=plan,
    )
    assert "自由组织结构和长度" in material.directAnswerSeed

    context = build_grounded_answer_context(
        answer_plan=plan,
        answer_material=material,
        prompt="介绍日慈基金会",
    )
    assert "【回答结构】" not in context
    assert "【写作要求】" not in context
    assert "【边界说明】" not in context
    assert "previewSummary" not in context
    assert "workTrace" not in context


def test_workspace_document_pack_stays_raw_without_summary_fields() -> None:
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="general",
    )
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
    )
    plan = build_answer_plan(
        prompt="介绍CFFC",
        page_context=page_context,
        route_decision=route,
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    evidence = []
    for doc_index in range(1, 10):
        for seg_index in range(1, 4):
                evidence.append(
                    {
                        "id": f"ev_{doc_index}_{seg_index}",
                        "title": f"文档{doc_index}",
                        "excerpt": f"第{doc_index}份文档的连续内容片段 {seg_index}",
                        "sourceType": "knowledge_chunk",
                        "documentId": f"doc_{doc_index}",
                        "path": f"/tmp/doc_{doc_index}.md",
                        "sectionLabel": f"章节{seg_index}",
                        "retrievalStage": "raw_chunk",
                    }
                )
    from app.models import EvidenceItem

    retrieval_evidence = [EvidenceItem(**item) for item in evidence]
    material = build_answer_material(
        prompt="介绍CFFC",
        page_context=page_context,
        route_decision=route,
        retrieval_evidence=retrieval_evidence,
        answer_plan=plan,
    )
    context = build_open_workspace_answer_context(
        prompt="介绍CFFC",
        kernel_result=_DummyKernelResult(page_context, material),
        workspace_snapshot=None,
        max_chars=64000,
    )
    assert "【原始阅读资料包 v2】" in context
    assert "previewSummary" not in context
    assert "stateAnswerSections" not in context
    assert "contextQuality" not in context
    assert context.count("[文档 ") == 8
    assert "片段 4：" not in context


def test_quality_gate_only_keeps_factual_hard_failures() -> None:
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="general",
    )
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
    )
    plan = build_answer_plan(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    material = build_answer_material(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        retrieval_evidence=[],
        answer_plan=plan,
    )
    report = validate_answer_quality(
        prompt="介绍日慈基金会",
        content="日慈基金会是一家关注儿童与青少年发展的公益机构。",
        answer_plan=plan,
        evidence=[],
        answer_material=material,
    )
    assert report["grade"] == "pass"
    assert report["missingRawEvidenceForIntent"] is False
    assert report["offTopicRisk"] is False
    assert report["factSlotHit"] is True


def test_freeze_markers_exist_for_answer_shaping_half_layer() -> None:
    files = {
        "backend/app/services/analysis_context.py": "P2.14 FREEZE(answer-shaping-workspace-intent)",
        "backend/app/services/query_router.py": "P2.14 FREEZE(answer-shaping-workspace-route)",
        "backend/app/services/question_focus.py": "P2.14 FREEZE(answer-shaping-question-focus)",
        "backend/app/services/data_center_search.py": "P2.14 FREEZE(answer-shaping-retrieval-caps)",
        "backend/app/services/evidence_selector.py": "P2.14 FREEZE(answer-shaping-evidence-selection)",
        "backend/app/services/answer_layer.py": "P2.14 FREEZE(answer-shaping-answer-plan-bounds)",
        "backend/app/services/workspace_data_center_adapter.py": "P2.14 FREEZE(answer-shaping-document-pack-window)",
        "backend/app/services/generation_runtime_policy.py": "P2.14 FREEZE(answer-shaping-open-runtime)",
        "backend/app/services/data_center_quality.py": "P2.14 FREEZE(answer-shaping-quality-gate)",
        "backend/app/main.py": "P2.14 FREEZE(answer-shaping-main-open-path)",
    }
    for path, marker in files.items():
        assert marker in _read(path)


def test_workspace_chat_main_answer_has_no_legacy_raw_document_pack_branch() -> None:
    main_src = _read("backend/app/main.py")
    resolve_body = main_src.split("def resolve_chat_answer(", 1)[1].split(
        "def _assistant_message_has_final_answer",
        1,
    )[0]
    executable_body = "\n".join(line for line in resolve_body.splitlines() if not line.lstrip().startswith("#"))
    assert "REMOVE(raw-document-pack-main-chain)" in resolve_body
    assert "workspace_chat_data_center_primary_enabled" not in executable_body
    assert "build_retrieval_bundle(client_id, prompt" not in executable_body
    assert "generate_chat_response" not in executable_body
    assert "raw_document_pack" not in executable_body
