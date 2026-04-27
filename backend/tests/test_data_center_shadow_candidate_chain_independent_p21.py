from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import (
    DataCenterCandidateChainRecord,
    DataCenterRequestRecord,
    DataCenterSearchHitRecord,
    PageContextPackRecord,
    RetrievalModelSettingsRecord,
    RouteDecisionRecord,
)
from app.services import data_center_kernel as kernel
from app.services.data_center_shadow import get_data_center_shadow_summary, list_data_center_shadow_runs


def test_data_center_shadow_candidate_chain_independent(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "shadow_independent.db")

    fake_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_shadow",
        clientId="client_shadow",
        intent="general",
    )
    monkeypatch.setattr(
        kernel,
        "_build_page_context",
        lambda *_args, **_kwargs: fake_context.model_copy(deep=True),
    )
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(routerEnabled=True, routerProvider="rules"),
    )

    def fake_route(*_args, settings, **_kwargs):
        if settings.routerEnabled:
            return RouteDecisionRecord(
                intent="business_profile",
                routeMode="hybrid",
                dataSources=["raw_docs"],
                retrievalMode="hybrid",
                shouldUseRawEvidence=True,
                routerSource="rules",
            )
        return RouteDecisionRecord(
            intent="general",
            routeMode="state_first",
            dataSources=["state_pool"],
            retrievalMode="state_only",
            routerSource="rules",
        )

    monkeypatch.setattr(kernel, "_route_with_settings", fake_route)

    def fake_chain(*, route_decision, **_kwargs):
        if route_decision.intent == "business_profile":
            return DataCenterCandidateChainRecord(
                routeDecision=route_decision,
                searchHits=[
                    DataCenterSearchHitRecord(
                        title="业务资料",
                        excerpt="核心业务说明",
                        sourceType="knowledge_chunk",
                        selectedForAnswer=True,
                        qualityFlags=["raw_chunk"],
                    )
                ],
                answerQuality={"grade": "pass", "hasDirectAnswer": True, "evidenceListOnly": False},
            )
        return DataCenterCandidateChainRecord(
            routeDecision=route_decision,
            searchHits=[
                DataCenterSearchHitRecord(
                    title="状态卡片",
                    excerpt="状态不足",
                    sourceType="state",
                    selectedForAnswer=True,
                    qualityFlags=["low_score"],
                )
            ],
            answerQuality={"grade": "fail", "hasDirectAnswer": False, "evidenceListOnly": True},
        )

    monkeypatch.setattr(kernel, "compute_data_center_candidate_chain", fake_chain)

    request = DataCenterRequestRecord(
        scope={
            "page": "workspace_chat",
            "scopeType": "client",
            "scopeId": "client_shadow",
            "clientId": "client_shadow",
        },
        prompt="CFFC 核心业务是什么？",
        mode="answer",
        shadow=True,
        includeActionSuggestions=False,
    )
    result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=None)
    assert result.routeDecision is not None
    assert result.routeDecision.intent == "general"

    runs = list_data_center_shadow_runs(db, scope_type="client", scope_id="client_shadow", limit=10)
    assert len(runs) >= 1
    run = runs[0]
    assert run.baseline.get("answerQuality") != run.candidate.get("answerQuality")
    summary = get_data_center_shadow_summary(db, scope_type="client", scope_id="client_shadow")
    assert summary.total >= 1
    assert summary.candidateBetterRate >= 1.0
