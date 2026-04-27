from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import ContextQualityRecord, PageContextPackRecord, RetrievalModelSettingsRecord
from app.services.query_router import route_page_query


def build_context_pack(intent: str = "general", quality: str = "weak") -> PageContextPackRecord:
    return PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_router",
        clientId="client_router",
        intent=intent,  # type: ignore[arg-type]
        quality=ContextQualityRecord(contextQuality=quality),  # type: ignore[arg-type]
    )


def test_official_registry_rule_guard(tmp_path: Path):
    db = Database(tmp_path / "router.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="系统里已批准的正式判断有哪些？",
        client_id="client_router",
        page_context=build_context_pack(intent="official_judgment_registry", quality="strong"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.intent == "official_judgment_registry"
    assert decision.judgmentQueryMode == "registry_only"
    assert decision.retrievalMode == "state_only"
    assert decision.shouldUseRawEvidence is False


def test_intro_query_forces_raw_drilldown(tmp_path: Path):
    db = Database(tmp_path / "router_intro.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="请介绍一下这个客户",
        client_id="client_router",
        page_context=build_context_pack(intent="intro_profile", quality="strong"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.intent == "general"
    assert decision.routeMode == "hybrid"
    assert decision.retrievalMode == "hybrid"
    assert decision.shouldUseRawEvidence is True


def test_complex_query_produces_hybrid_plan(tmp_path: Path):
    db = Database(tmp_path / "router_complex.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="这个客户最近推进到哪了，上次会议说了什么，下一步应该谁做？",
        client_id="client_router",
        page_context=build_context_pack(intent="general", quality="weak"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.retrievalMode == "hybrid"
    assert decision.queryPlan == []
    assert decision.dataSources == ["raw_docs", "document_cards"]
    assert decision.shouldUseStatePool is False
    assert decision.shouldUseMeetingContext is False


def test_smart_router_invalid_output_falls_back_to_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "router_fallback.db")
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=256,
        embeddingMode="local",
        routerEnabled=True,
        routerProvider="doubao",
        routerModel="doubao-smart-router",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )

    import app.services.query_router as query_router

    monkeypatch.setattr(query_router, "_invoke_doubao_router_model", lambda **_kwargs: None)
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="这个项目接下来要怎么判断优先级？请给路径",
        client_id="client_router",
        page_context=build_context_pack(intent="general", quality="none"),
        settings=settings,
        ai_service=object(),
    )
    assert decision.routerSource == "rules"
    assert decision.fallbackUsed is False
    assert decision.routeReason == "workspace_chat_open_route"
