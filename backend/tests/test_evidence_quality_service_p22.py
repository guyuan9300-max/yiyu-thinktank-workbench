from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import (
    DataCenterRequestRecord,
    EvidenceItem,
    PageContextPackRecord,
    RetrievalModelSettingsRecord,
    RouteDecisionRecord,
)
from app.services import data_center_kernel as kernel
from app.services.evidence_quality import classify_evidence_quality
from app.services.evidence_selector import select_answer_evidence


def test_classify_evidence_quality_noise_and_high_value():
    ppt_noise = EvidenceItem(
        id="e1",
        title="ClickToEditMaster 母版",
        excerpt="模板页",
        sourceType="knowledge_chunk",
        retrievalStage="raw_chunk",
    )
    signal_noise = classify_evidence_quality(ppt_noise)
    assert signal_noise.isNoise is True
    assert signal_noise.sourceKind in {"ppt_master", "template_page", "ppt_visual"}

    memory = EvidenceItem(
        id="e2",
        title="历史回答",
        excerpt="这是之前的回答草稿",
        sourceType="memory_answer",
        retrievalStage="surrogate",
    )
    signal_memory = classify_evidence_quality(memory)
    assert signal_memory.sourceKind == "memory_answer"
    assert signal_memory.demotionScore > 0

    raw = EvidenceItem(
        id="e3",
        title="战略推进纪要",
        excerpt="2026 年战略方向与关键行动计划明确。",
        sourceType="knowledge_chunk",
        sectionLabel="正文",
        retrievalStage="raw_chunk",
    )
    signal_raw = classify_evidence_quality(raw)
    assert signal_raw.isNoise is False
    assert signal_raw.qualityScore > signal_memory.qualityScore


def test_evidence_selector_prefers_high_quality_for_business_profile():
    route = RouteDecisionRecord(
        intent="business_profile",
        routeMode="raw_doc_drilldown",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        rerankNeeded=True,
    )
    context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="c1",
        clientId="c1",
        intent="business_profile",
    )
    noisy = EvidenceItem(
        id="noise",
        title="模板页",
        excerpt="短",
        sourceType="generated_answer",
        retrievalStage="surrogate",
    )
    high = EvidenceItem(
        id="high",
        title="核心业务说明",
        excerpt="客户核心业务包括资源支持、项目服务与平台协作。",
        sourceType="knowledge_chunk",
        sectionLabel="正文",
        retrievalStage="raw_chunk",
    )
    selected = select_answer_evidence(
        prompt="核心业务是什么",
        intent="business_profile",
        route_decision=route,
        evidence=[noisy, high],
        page_context=context,
    )
    assert selected
    assert selected[0].id == "high"


def test_search_quality_flags_include_noise_and_source_kind(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "quality_search.db")

    fake_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_quality",
        clientId="client_quality",
        intent="business_profile",
        rawEvidence=[
            {
                "id": "raw1",
                "title": "核心业务章节",
                "excerpt": "核心业务包含公益服务与资源支持",
                "sourceType": "knowledge_chunk",
                "sectionLabel": "正文",
                "sourceStage": "raw_chunk",
            },
            {
                "id": "raw2",
                "title": "模板页",
                "excerpt": "短",
                "sourceType": "generated_answer",
                "sourceStage": "surrogate",
            },
        ],
    )

    monkeypatch.setattr(kernel, "_build_page_context", lambda *_args, **_kwargs: fake_context.model_copy(deep=True))
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(updatedAt="", routerEnabled=False),
    )
    monkeypatch.setattr(
        kernel,
        "_route_with_settings",
        lambda *_args, **_kwargs: RouteDecisionRecord(
            intent="business_profile",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs"],
            retrievalMode="hybrid",
            shouldUseRawEvidence=True,
            rerankNeeded=True,
            routerSource="rules",
        ),
    )

    request = DataCenterRequestRecord(
        scope={
            "page": "workspace_chat",
            "scopeType": "client",
            "scopeId": "client_quality",
            "clientId": "client_quality",
        },
        prompt="核心业务是什么？",
        mode="search",
        shadow=False,
    )
    result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=None)
    assert result.searchResult is not None
    assert result.searchResult.hits
    flags = result.searchResult.hits[0].qualityFlags
    assert any(flag.startswith("source_kind:") for flag in flags)
    assert any(flag.startswith("authority:") for flag in flags)
    assert any("template" in "|".join(hit.qualityFlags) or "short_excerpt" in "|".join(hit.qualityFlags) for hit in result.searchResult.hits)
