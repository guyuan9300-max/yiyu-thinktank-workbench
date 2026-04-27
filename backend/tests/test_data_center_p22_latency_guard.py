from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import pytest

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


def _base_context() -> PageContextPackRecord:
    return PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_latency",
        clientId="client_latency",
        intent="business_profile",
        relatedTasks=[{"id": "task_1", "title": "资源支持与项目服务"}],
        openQuestions=[{"id": "q_1", "question": "服务对象是否已确认"}],
    )


def test_kernel_answer_latency_guard_under_small_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "p22_latency.db")

    monkeypatch.setattr(kernel, "_build_page_context", lambda *_args, **_kwargs: _base_context().model_copy(deep=True))
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(updatedAt="", routerEnabled=False, shadowMode=True),
    )

    def _fake_route(*_args, **_kwargs):
        return RouteDecisionRecord(
            intent="business_profile",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs", "document_cards", "state_pool"],
            retrievalMode="hybrid",
            shouldUseRawEvidence=True,
            shouldUseStatePool=True,
            rerankNeeded=True,
        )

    monkeypatch.setattr(kernel, "_route_with_settings", _fake_route)
    monkeypatch.setattr(
        kernel,
        "build_data_center_retrieval_items",
        lambda *_args, **_kwargs: (
            [
                EvidenceItem(
                    id="e_latency",
                    title="CFFC 业务原文",
                    excerpt="核心业务包括资源支持、项目服务与平台协作。",
                    sourceType="knowledge_chunk",
                    retrievalStage="raw_chunk",
                    sectionLabel="正文",
                )
            ],
            None,
        ),
    )

    request = DataCenterRequestRecord(
        scope={"page": "workspace_chat", "scopeType": "client", "scopeId": "client_latency", "clientId": "client_latency"},
        prompt="CFFC 核心业务是什么？",
        mode="answer",
        shadow=True,
    )

    started = perf_counter()
    result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=None)
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.answerPlan is not None
    assert result.answerPlan.intent == "business_profile"
    assert elapsed_ms < 1200


class _PanicAiService:
    def __getattr__(self, _name: str):
        raise AssertionError("LLM should not be invoked for search/prep/proposal kernel modes")


def test_search_prep_proposal_modes_skip_llm_and_keep_official_registry_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "p22_modes_guard.db")
    retrieval_routes: list[RouteDecisionRecord] = []

    monkeypatch.setattr(kernel, "_build_page_context", lambda *_args, **_kwargs: _base_context().model_copy(deep=True))
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(updatedAt="", routerEnabled=False, shadowMode=True),
    )

    def _official_route(*_args, **_kwargs):
        return RouteDecisionRecord(
            intent="official_judgment_registry",
            routeMode="registry_only",
            dataSources=["judgment_registry"],
            retrievalMode="state_only",
            shouldUseRawEvidence=False,
            rerankNeeded=False,
            judgmentQueryMode="registry_only",
        )

    monkeypatch.setattr(kernel, "_route_with_settings", _official_route)

    def _fake_retrieval(*_args, route_decision: RouteDecisionRecord, **_kwargs):
        retrieval_routes.append(route_decision)
        return (
            [
                EvidenceItem(
                    id="e_registry",
                    title="已批准判断",
                    excerpt="已批准：当前主线聚焦能力建设与生态协作。",
                    sourceType="official_judgment",
                    retrievalStage="state_pool",
                )
            ],
            None,
        )

    monkeypatch.setattr(kernel, "build_data_center_retrieval_items", _fake_retrieval)

    for mode in ("search", "prep", "proposal"):
        request = DataCenterRequestRecord(
            scope={"page": "workspace_chat", "scopeType": "client", "scopeId": "client_latency", "clientId": "client_latency"},
            prompt="系统里已批准的正式判断有哪些？",
            mode=mode,  # type: ignore[arg-type]
            shadow=True,
            persistDrafts=False,
        )
        result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=_PanicAiService())
        assert result.routeDecision is not None
        assert result.routeDecision.routeMode == "registry_only"
        assert result.routeDecision.shouldUseRawEvidence is False

    assert retrieval_routes, "retrieval should be called"
    assert all(route.shouldUseRawEvidence is False for route in retrieval_routes)
