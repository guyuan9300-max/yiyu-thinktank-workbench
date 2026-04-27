from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import PageContextPackRecord, RetrievalModelSettingsRecord, RetrievalTraceRecord, RouteDecisionRecord
from app.services import data_center_search
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def test_data_center_search_collects_multisource_hits(tmp_path: Path):
    db = Database(tmp_path / "search_multisource.db")
    context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_search",
        clientId="client_search",
        intent="business_profile",
        rawEvidence=[{"id": "raw1", "title": "业务原文", "excerpt": "业务介绍", "sourceType": "knowledge_chunk", "sourceStage": "raw_chunk"}],
        evidenceCards=[{"id": "card1", "title": "证据卡", "excerpt": "证据摘要", "sourceType": "evidence_card"}],
        relatedDocuments=[{"id": "doc1", "title": "文档", "excerpt": "文档正文", "sourceType": "knowledge_document"}],
        relatedMeetings=[{"id": "meeting1", "title": "会议纪要", "summary": "行动项", "sourceType": "meeting_note"}],
        relatedTasks=[{"id": "task1", "title": "任务附件", "summary": "任务背景", "sourceType": "task_attachment"}],
        officialJudgments=[{"id": "oj1", "topic": "正式判断", "summary": "正式结论摘要"}],
        candidateJudgments=[{"id": "cj1", "topic": "候选判断", "summary": "候选结论摘要"}],
        themeClusters=[{"id": "topic1", "title": "主题候选", "summary": "topic 信息"}],
    )
    route = RouteDecisionRecord(
        intent="business_profile",
        routeMode="raw_doc_drilldown",
        dataSources=["raw_docs", "document_cards", "state_pool", "meetings", "tasks"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        rerankNeeded=True,
    )
    settings = RetrievalModelSettingsRecord(updatedAt="")

    hits, _trace = data_center_search.build_data_center_retrieval_items(
        db,
        data_dir=tmp_path,
        client_id=None,
        prompt="核心业务是什么",
        page_context=context,
        route_decision=route,
        settings=settings,
    )
    source_types = {item.sourceType for item in hits}
    assert "knowledge_chunk" in source_types
    assert "meeting_note" in source_types
    assert "task_attachment" in source_types
    assert "official_judgment" in source_types
    assert "candidate_judgment" in source_types
    assert "topic_candidate" in source_types


def test_workspace_chat_main_uses_reading_pack_v2_without_raw_document_pack_fallback(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "search_workspace_v2.db")
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        rerankNeeded=False,
    )
    context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_workspace_v2",
        clientId="client_workspace_v2",
        intent="general",
        rawEvidence=[{"id": "raw1", "title": "旧 rawEvidence 不应进入", "excerpt": "旧原文", "sourceType": "knowledge_chunk"}],
        evidenceCards=[{"id": "card1", "title": "旧 evidenceCard 不应进入", "excerpt": "旧摘要", "sourceType": "evidence_card"}],
        relatedDocuments=[{"id": "doc1", "title": "旧 relatedDocument 不应进入", "excerpt": "旧文档", "sourceType": "knowledge_document"}],
        retrievalTrace=RetrievalTraceRecord(routeDecision=route),
    )

    monkeypatch.setattr(data_center_search, "backfill_client_document_family_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(data_center_search, "materialize_workspace_native_documents", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        data_center_search,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="doc_v2",
                    chunk_id="chunk_v2",
                    title="v2 family 文档",
                    excerpt="两段式阅读包里的连续原文片段",
                    score=0.91,
                    coverage=0.8,
                    section_label="正文",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["CFFC"],
                    path="/tmp/v2.md",
                    document_family_id="raw_file:v2-family",
                    canonical_kind="raw_file",
                    origin_type="file_import",
                    origin_id="doc_v2",
                    is_searchable=True,
                )
            ],
            coverage=0.8,
            retrieval_summary={
                "readingPassCount": 2,
                "selectedDocumentFamilyCount": 1,
                "selectedCanonicalKinds": ["raw_file"],
                "softwareMaterialIncluded": False,
            },
            context_text="",
            matched_terms=["CFFC"],
        ),
    )
    hits, trace = data_center_search.build_data_center_retrieval_items(
        db,
        data_dir=tmp_path,
        client_id="client_workspace_v2",
        prompt="介绍CFFC",
        page_context=context,
        route_decision=route,
        settings=RetrievalModelSettingsRecord(updatedAt=""),
    )

    titles = [item.title for item in hits]
    assert titles == ["v2 family 文档"]
    assert "旧 rawEvidence 不应进入" not in titles
    assert "旧 evidenceCard 不应进入" not in titles
    assert "旧 relatedDocument 不应进入" not in titles
    assert trace is not None
    assert trace.readingPassCount == 2
    assert trace.selectedDocumentFamilyCount == 1
    assert trace.selectedCanonicalKinds == ["raw_file"]


def test_official_registry_search_does_not_trigger_raw_bundle(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "search_registry.db")
    context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_registry",
        clientId="client_registry",
        intent="official_judgment_registry",
        rawEvidence=[{"id": "raw1", "title": "不应触发", "excerpt": "raw", "sourceType": "knowledge_chunk", "sourceStage": "raw_chunk"}],
        officialJudgments=[{"id": "oj1", "topic": "正式判断", "summary": "正式结论摘要"}],
    )
    route = RouteDecisionRecord(
        intent="official_judgment_registry",
        routeMode="registry_only",
        dataSources=["judgment_registry"],
        retrievalMode="state_only",
        shouldUseRawEvidence=False,
        rerankNeeded=False,
    )
    settings = RetrievalModelSettingsRecord(updatedAt="")

    monkeypatch.setattr(
        data_center_search,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("should_not_call_raw_bundle")),
    )

    hits, _trace = data_center_search.build_data_center_retrieval_items(
        db,
        data_dir=tmp_path,
        client_id="client_registry",
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        route_decision=route,
        settings=settings,
    )
    assert hits
    assert all(item.sourceType != "knowledge_chunk" for item in hits)
    assert any(item.sourceType == "official_judgment" for item in hits)
