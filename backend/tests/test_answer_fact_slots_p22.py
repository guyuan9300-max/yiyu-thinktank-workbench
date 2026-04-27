from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    AnswerPolicyRecord,
    EvidenceItem,
    PageContextPackRecord,
    RouteDecisionRecord,
)
from app.services.answer_layer import build_answer_material, build_answer_plan


def _base_context(intent: str) -> PageContextPackRecord:
    return PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_slots",
        clientId="client_slots",
        intent=intent,
    )


def test_business_profile_fact_slots_non_template_seed():
    prompt = "CFFC 核心业务是什么？"
    page_context = _base_context("business_profile")
    route_decision = RouteDecisionRecord(
        intent="business_profile",
        routeMode="raw_doc_drilldown",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        rerankNeeded=True,
    )
    answer_plan = build_answer_plan(
        prompt=prompt,
        page_context=page_context,
        route_decision=route_decision,
        answer_policy=AnswerPolicyRecord(),
    )
    evidence = [
        EvidenceItem(
            id="e1",
            title="CFFC 资源支持",
            excerpt="CFFC 通过资源支持与项目服务，为公益机构提供赋能。",
            sourceType="knowledge_chunk",
            sectionLabel="正文",
            retrievalStage="raw_chunk",
        ),
        EvidenceItem(
            id="e2",
            title="CFFC 平台协作",
            excerpt="平台协作是其核心业务之一，服务对象包括基金会与社会组织。",
            sourceType="knowledge_chunk",
            sectionLabel="正文",
            retrievalStage="raw_chunk",
        ),
    ]
    material = build_answer_material(
        prompt=prompt,
        page_context=page_context,
        route_decision=route_decision,
        retrieval_evidence=evidence,
        answer_plan=answer_plan,
    )

    assert material.businessProfile is not None
    assert material.businessProfile.businessModules
    assert "核心业务可归纳为" in material.directAnswerSeed
    assert material.directAnswerSeed != "基于当前资料，核心业务可归纳为以下几个板块。"


def test_strategy_profile_fact_slots_include_time_boundary_or_unknowns():
    prompt = "日慈的最新战略是什么？"
    page_context = _base_context("strategy_profile")
    route_decision = RouteDecisionRecord(
        intent="strategy_profile",
        routeMode="hybrid",
        dataSources=["state_pool", "raw_docs", "meetings"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        rerankNeeded=True,
    )
    answer_plan = build_answer_plan(
        prompt=prompt,
        page_context=page_context,
        route_decision=route_decision,
        answer_policy=AnswerPolicyRecord(),
    )
    evidence = [
        EvidenceItem(
            id="s1",
            title="2026 战略重点",
            excerpt="2026 年战略方向聚焦数字化能力建设与公益协同网络。",
            sourceType="knowledge_chunk",
            sectionLabel="战略方向",
            retrievalStage="raw_chunk",
        ),
        EvidenceItem(
            id="s2",
            title="战略行动计划",
            excerpt="关键行动包括组织能力建设、合作伙伴拓展与资金策略优化。",
            sourceType="knowledge_chunk",
            sectionLabel="行动计划",
            retrievalStage="raw_chunk",
        ),
    ]
    material = build_answer_material(
        prompt=prompt,
        page_context=page_context,
        route_decision=route_decision,
        retrieval_evidence=evidence,
        answer_plan=answer_plan,
    )

    assert material.strategyProfile is not None
    assert material.strategyProfile.strategicDirections or material.strategyProfile.unknowns
    assert material.strategyProfile.timeBoundary or material.strategyProfile.unknowns
    assert "当前资料能确认" in material.directAnswerSeed
