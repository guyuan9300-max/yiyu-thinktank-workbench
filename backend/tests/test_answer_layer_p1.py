from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import AnswerPolicyRecord, EvidenceItem, PageContextPackRecord, RouteDecisionRecord
from app.services.answer_layer import (
    build_answer_material,
    build_answer_plan,
    build_grounded_answer_context,
    build_local_answer_fallback,
)


def _evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(id="e1", title="机构资料", excerpt="该机构聚焦儿童与青少年心理支持。", sourceType="knowledge_chunk"),
        EvidenceItem(id="e2", title="项目手册", excerpt="项目覆盖学校、教师与家庭支持场景。", sourceType="knowledge_chunk"),
        EvidenceItem(id="e3", title="战略材料", excerpt="组织在推进数字化能力与数据沉淀。", sourceType="knowledge_chunk"),
        EvidenceItem(id="e4", title="合作材料", excerpt="机构与行业伙伴协作扩大影响。", sourceType="knowledge_chunk"),
    ]


def test_answer_plan_is_open_for_workspace_chat_main_chain():
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="intro_profile",
    )
    route = RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid")
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


def test_answer_material_keeps_facts_and_evidence_but_not_default_boundaries_or_actions():
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="intro_profile",
        relatedTasks=[{"title": "推进合作", "status": "todo"}],
        conflicts=[{"summary": "仍有待确认事项"}],
        boundaryNotes=["当前部分信息来自候选资料"],
    )
    route = RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid")
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
        retrieval_evidence=_evidence(),
        answer_plan=plan,
    )
    assert material.directAnswerSeed
    assert material.keyFacts
    assert material.evidenceHighlights
    assert material.boundaryNotes == []
    assert material.nextActions == []
    assert material.structuredPoints == []


def test_grounded_answer_context_is_minimal_and_not_template_shaped():
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="intro_profile",
    )
    route = RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid")
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
        retrieval_evidence=_evidence(),
        answer_plan=plan,
    )
    context = build_grounded_answer_context(
        answer_plan=plan,
        answer_material=material,
        prompt="介绍日慈基金会",
    )
    assert "【回答结构】" not in context
    assert "【直接答案种子】" not in context
    assert "【写作要求】" not in context
    assert "【边界说明】" not in context
    assert "【下一步建议】" not in context
    assert "【补充事实】" not in context
    assert "【原始文档资料包】" in context
    assert "自由组织结构和长度" in context


def test_local_fallback_is_open_text_not_fixed_sections():
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="business_profile",
    )
    route = RouteDecisionRecord(intent="business_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid")
    plan = build_answer_plan(
        prompt="机构主要业务是什么？",
        page_context=page_context,
        route_decision=route,
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    material = build_answer_material(
        prompt="机构主要业务是什么？",
        page_context=page_context,
        route_decision=route,
        retrieval_evidence=_evidence(),
        answer_plan=plan,
    )
    fallback = build_local_answer_fallback(
        prompt="机构主要业务是什么？",
        answer_plan=plan,
        answer_material=material,
        failure_detail="timeout",
    )
    assert "【直接回答】" not in fallback.content
    assert "【依据】" not in fallback.content
    assert "【边界】" not in fallback.content
    assert "【下一步】" not in fallback.content
    assert "资料包括" in fallback.content or "资料仍然有限" in fallback.content
