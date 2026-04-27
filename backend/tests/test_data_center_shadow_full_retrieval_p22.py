from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import (
    DataCenterCandidateChainRecord,
    DataCenterRequestRecord,
    DataCenterSearchHitRecord,
    EvidenceItem,
    PageContextPackRecord,
    RetrievalModelSettingsRecord,
    RouteDecisionRecord,
)
from app.services import data_center_kernel as kernel
from app.services.data_center_shadow import list_data_center_shadow_runs


def test_shadow_runs_use_independent_retrieval_chains(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "shadow_full_retrieval.db")

    fake_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_shadow_full",
        clientId="client_shadow_full",
        intent="business_profile",
    )
    monkeypatch.setattr(kernel, "_build_page_context", lambda *_args, **_kwargs: fake_context.model_copy(deep=True))
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(
            updatedAt="",
            routerEnabled=True,
            routerProvider="local_semantic",
            routerMode="semantic",
        ),
    )

    def fake_route(*_args, settings, **_kwargs):
        if settings.routerEnabled:
            return RouteDecisionRecord(
                intent="business_profile",
                routeMode="hybrid",
                dataSources=["raw_docs", "document_cards"],
                retrievalMode="hybrid",
                shouldUseRawEvidence=True,
                rerankNeeded=True,
                routerSource="local_semantic",
            )
        return RouteDecisionRecord(
            intent="general",
            routeMode="state_first",
            dataSources=["state_pool"],
            retrievalMode="state_only",
            shouldUseRawEvidence=False,
            rerankNeeded=False,
            routerSource="rules",
        )

    monkeypatch.setattr(kernel, "_route_with_settings", fake_route)

    retrieval_calls: list[str] = []

    def fake_retrieval(*_args, route_decision, **_kwargs):
        retrieval_calls.append(route_decision.intent)
        if route_decision.intent == "business_profile":
            return (
                [
                    EvidenceItem(
                        id="cand_raw",
                        title="业务原文",
                        excerpt="核心业务包括资源支持与项目服务。",
                        sourceType="knowledge_chunk",
                        retrievalStage="raw_chunk",
                        sectionLabel="正文",
                    )
                ],
                None,
            )
        return (
            [
                EvidenceItem(
                    id="base_state",
                    title="状态摘要",
                    excerpt="当前信息不足。",
                    sourceType="state",
                    retrievalStage="state_pool",
                )
            ],
            None,
        )

    monkeypatch.setattr(kernel, "build_data_center_retrieval_items", fake_retrieval)

    def fake_chain(*, route_decision, evidence_items, **_kwargs):
        if route_decision.intent == "business_profile":
            return DataCenterCandidateChainRecord(
                routeDecision=route_decision,
                selectedEvidence=evidence_items,
                searchHits=[
                    DataCenterSearchHitRecord(
                        title="业务原文",
                        excerpt="核心业务包括资源支持与项目服务。",
                        sourceType="knowledge_chunk",
                        selectedForAnswer=True,
                        qualityFlags=["raw_chunk"],
                    )
                ],
                answerQuality={"grade": "pass", "hasDirectAnswer": True, "evidenceListOnly": False},
            )
        return DataCenterCandidateChainRecord(
            routeDecision=route_decision,
            selectedEvidence=evidence_items,
            searchHits=[
                DataCenterSearchHitRecord(
                    title="状态摘要",
                    excerpt="当前信息不足。",
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
            "scopeId": "client_shadow_full",
            "clientId": "client_shadow_full",
        },
        prompt="核心业务是什么？",
        mode="answer",
        shadow=True,
    )

    result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=None)
    assert result.routeDecision is not None
    assert result.routeDecision.intent == "general"
    assert retrieval_calls.count("general") == 1
    assert retrieval_calls.count("business_profile") == 1

    runs = list_data_center_shadow_runs(db, scope_type="client", scope_id="client_shadow_full", limit=5)
    assert runs
    run = runs[0]
    baseline_hits = run.baseline.get("selectedHits") if isinstance(run.baseline, dict) else []
    candidate_hits = run.candidate.get("selectedHits") if isinstance(run.candidate, dict) else []
    assert baseline_hits != candidate_hits
    assert run.baseline.get("answerQuality") != run.candidate.get("answerQuality")
