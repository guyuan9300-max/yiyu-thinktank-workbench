from __future__ import annotations

from pathlib import Path

from app.db import Database
from app.models import (
    DataCenterSearchResultRecord,
    EvidenceItem,
    PageContextPackRecord,
    RetrievalModelSettingsRecord,
    RetrievalTraceRecord,
    RouteDecisionRecord,
)
from app.services.data_center_access import DataCenterAccessContext
from app.services.evidence_quality import classify_evidence_quality
from app.services.knowledge_v2 import (
    CitationMatch,
    backfill_client_document_family_metadata,
    materialize_workspace_native_documents,
    retrieve_knowledge_bundle,
)


def _uses_data_source(route_decision: RouteDecisionRecord, *candidates: str) -> bool:
    enabled = {str(item or "").strip() for item in route_decision.dataSources}
    return any(candidate in enabled for candidate in candidates)


def _workspace_chat_requires_reading_pack_v2(
    *,
    client_id: str | None,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
) -> bool:
    if page_context.page != "workspace_chat":
        return False
    if page_context.scopeType != "client" or not client_id:
        return False
    if route_decision.intent == "official_judgment_registry":
        return False
    if route_decision.retrievalMode not in {"hybrid", "raw_only"}:
        return False
    return True


def _to_evidence_item(index: int, item: dict[str, object], *, prefix: str, source_type: str, stage: str) -> EvidenceItem:
    return EvidenceItem(
        id=f"{prefix}_{index}",
        title=str(item.get("title") or "资料"),
        excerpt=str(item.get("excerpt") or item.get("summary") or item.get("normalized_claim") or ""),
        sourceType=source_type,
        documentId=str(item.get("documentId") or item.get("document_id") or item.get("id") or "") or None,
        path=str(item.get("path") or item.get("sourceUrl") or "") or None,
        originalPath=str(item.get("originalPath") or item.get("original_path") or "") or None,
        managedPath=str(item.get("managedPath") or item.get("managed_path") or "") or None,
        markdownPath=str(item.get("markdownPath") or item.get("markdown_path") or "") or None,
        openableKind=str(item.get("openableKind") or item.get("openable_kind") or "") or None,
        sourceAvailability=str(item.get("sourceAvailability") or item.get("source_availability") or "") or None,
        originalAvailable=bool(item.get("originalAvailable") if item.get("originalAvailable") is not None else item.get("original_available")) if (
            item.get("originalAvailable") is not None or item.get("original_available") is not None
        ) else None,
        machineReadableAvailable=bool(item.get("machineReadableAvailable") if item.get("machineReadableAvailable") is not None else item.get("machine_readable_available")) if (
            item.get("machineReadableAvailable") is not None or item.get("machine_readable_available") is not None
        ) else None,
        openOriginalDisabledReason=str(item.get("openOriginalDisabledReason") or item.get("open_original_disabled_reason") or "") or None,
        score=float(item.get("score") or 0.0) if item.get("score") is not None else None,
        sectionLabel=str(item.get("sectionLabel") or "") or None,
        retrievalStage=str(item.get("sourceStage") or stage),
    )


def _citation_to_evidence_item(index: int, item: CitationMatch) -> EvidenceItem:
    return EvidenceItem(
        id=f"bundle_{index}",
        title=str(item.title or "资料"),
        excerpt=str(item.excerpt or ""),
        sourceType="knowledge_chunk",
        documentId=str(item.knowledge_document_id or "") or None,
        documentFamilyId=str(item.document_family_id or "") or None,
        canonicalKind=str(item.canonical_kind or "") or None,
        originType=str(item.origin_type or "") or None,
        originId=str(item.origin_id or "") or None,
        isSearchable=item.is_searchable,
        path=str(item.path or "") or None,
        originalPath=str(item.original_path or "") or None,
        managedPath=str(item.managed_path or "") or None,
        markdownPath=str(item.markdown_path or "") or None,
        openableKind=str(item.openable_kind or "") or None,
        sourceAvailability=str(item.source_availability or "") or None,
        originalAvailable=item.original_available,
        machineReadableAvailable=item.machine_readable_available,
        openOriginalDisabledReason=str(item.open_original_disabled_reason or "") or None,
        score=float(item.score or 0.0),
        sectionLabel=str(item.section_label or "") or None,
        retrievalStage=str(item.source_stage or "raw_chunk"),
    )


def _dedupe_items(items: list[EvidenceItem], *, limit: int = 120) -> list[EvidenceItem]:
    deduped: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        key = f"{item.documentId or ''}:{item.path or ''}:{(item.excerpt or '')[:120]}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def build_data_center_retrieval_items(
    db: Database,
    *,
    data_dir: Path,
    client_id: str | None,
    prompt: str,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    settings: RetrievalModelSettingsRecord,
    access_context: DataCenterAccessContext | dict[str, object] | None = None,
    working_document_ids: list[str] | None = None,
) -> tuple[list[EvidenceItem], RetrievalTraceRecord | None]:
    is_client_scope = page_context.scopeType == "client"
    base_items: list[EvidenceItem] = []
    is_official_registry = route_decision.intent == "official_judgment_registry"
    include_raw_docs = _uses_data_source(route_decision, "raw_docs")
    include_document_cards = _uses_data_source(route_decision, "document_cards")
    include_meetings = _uses_data_source(route_decision, "meetings")
    include_tasks = _uses_data_source(route_decision, "tasks")
    include_state_pool = _uses_data_source(route_decision, "state_pool")
    include_judgments = _uses_data_source(route_decision, "judgments", "judgment_registry")
    workspace_chat_requires_v2 = _workspace_chat_requires_reading_pack_v2(
        client_id=client_id,
        page_context=page_context,
        route_decision=route_decision,
    )
    use_reading_pack_v2 = (
        workspace_chat_requires_v2
        or is_client_scope
        and not is_official_registry
        and bool(client_id)
        and route_decision.retrievalMode in {"hybrid", "raw_only"}
        and (include_raw_docs or include_document_cards)
    )
    # P2.14 FREEZE(answer-shaping-retrieval-caps): 下面这组 base evidence 裁剪参数
    # 仍然属于“回答塑形半层”的历史限制，仅允许非 workspace/chat 主回答路径继续使用：
    # raw[:40] / cards[:30] / docs[:30] / meetings[:15] / tasks[:20] / judgments[:20] / themeClusters[:20] / merged limit=120。
    # P2.16 REMOVE(raw-document-pack-retrieval-fallback): workspace/chat 主回答不得再回落到这组旧 raw_document_pack 输入。
    if not use_reading_pack_v2 and not workspace_chat_requires_v2 and not is_official_registry and include_raw_docs:
        for index, item in enumerate(page_context.rawEvidence[:40], start=1):
            if isinstance(item, dict):
                base_items.append(_to_evidence_item(index, item, prefix="raw", source_type="knowledge_chunk", stage="raw_chunk"))
    if not use_reading_pack_v2 and not workspace_chat_requires_v2 and not is_official_registry and include_document_cards:
        for index, item in enumerate(page_context.evidenceCards[:30], start=1):
            if isinstance(item, dict):
                base_items.append(_to_evidence_item(index, item, prefix="card", source_type="evidence_card", stage="surrogate"))
    if not use_reading_pack_v2 and not workspace_chat_requires_v2 and not is_official_registry and (include_raw_docs or include_document_cards):
        for index, item in enumerate(page_context.relatedDocuments[:30], start=1):
            if isinstance(item, dict):
                base_items.append(_to_evidence_item(index, item, prefix="doc", source_type="knowledge_document", stage="master_index"))
    if include_meetings:
        for index, item in enumerate(page_context.relatedMeetings[:15], start=1):
            if isinstance(item, dict):
                base_items.append(_to_evidence_item(index, item, prefix="meeting", source_type="meeting_note", stage="state_pool"))
    if include_tasks:
        for index, item in enumerate(page_context.relatedTasks[:20], start=1):
            if isinstance(item, dict):
                base_items.append(_to_evidence_item(index, item, prefix="task", source_type="task_attachment", stage="state_pool"))
    if include_judgments or include_state_pool:
        for index, item in enumerate(page_context.officialJudgments[:20], start=1):
            if not isinstance(item, dict):
                continue
            base_items.append(
                _to_evidence_item(
                    index,
                    {
                        "id": item.get("id") or item.get("judgmentId") or f"official_{index}",
                        "title": item.get("title") or item.get("topic") or "正式判断",
                        "excerpt": item.get("summary") or item.get("statement") or item.get("rationale") or "",
                        "sourceType": "official_judgment",
                        "score": item.get("score") or 0.88,
                        "sectionLabel": item.get("sectionLabel") or "official_layer",
                        "sourceStage": "state_pool",
                    },
                    prefix="official",
                    source_type="official_judgment",
                    stage="state_pool",
                )
            )
        for index, item in enumerate(page_context.candidateJudgments[:20], start=1):
            if not isinstance(item, dict):
                continue
            base_items.append(
                _to_evidence_item(
                    index,
                    {
                        "id": item.get("id") or item.get("judgmentId") or f"candidate_{index}",
                        "title": item.get("title") or item.get("topic") or "候选判断",
                        "excerpt": item.get("summary") or item.get("statement") or item.get("rationale") or "",
                        "sourceType": "candidate_judgment",
                        "score": item.get("score") or 0.52,
                        "sectionLabel": item.get("sectionLabel") or "candidate_layer",
                        "sourceStage": "state_pool",
                    },
                    prefix="candidate",
                    source_type="candidate_judgment",
                    stage="state_pool",
                )
            )
    if include_state_pool:
        for index, item in enumerate(page_context.themeClusters[:20], start=1):
            if not isinstance(item, dict):
                continue
            base_items.append(
                _to_evidence_item(
                    index,
                    {
                        "id": item.get("id") or item.get("topicId") or f"topic_{index}",
                        "title": item.get("title") or item.get("topic") or "主题线索",
                        "excerpt": item.get("summary") or item.get("insight") or item.get("description") or "",
                        "sourceType": "topic_candidate",
                        "score": item.get("score") or 0.5,
                        "sectionLabel": item.get("sectionLabel") or "topic_radar",
                        "sourceStage": "state_pool",
                    },
                    prefix="topic",
                    source_type="topic_candidate",
                    stage="state_pool",
                )
            )

    bundle_items: list[EvidenceItem] = []
    bundle_summary: dict[str, object] = {}
    if use_reading_pack_v2 and client_id:
        backfill_client_document_family_metadata(db, client_id)
        materialize_workspace_native_documents(db, data_dir=data_dir, client_id=client_id)
        bundle = retrieve_knowledge_bundle(
            db,
            data_dir,
            client_id,
            prompt,
            access_context=access_context,
            priority_document_ids=working_document_ids,
        )
        bundle_summary = bundle.retrieval_summary if isinstance(bundle.retrieval_summary, dict) else {}
        for index, citation in enumerate(bundle.citations, start=1):
            bundle_items.append(_citation_to_evidence_item(index, citation))

    # P2.14 FREEZE(answer-shaping-merged-evidence-limit): 合并后的 evidence pool 当前仍只保留前 120 条。
    merged_limit = 160 if use_reading_pack_v2 else 120
    merged_items = _dedupe_items([*bundle_items, *base_items], limit=merged_limit)
    lexical_hits = len(base_items)
    vector_hits = len(bundle_items)
    raw_chunk_hits = sum(1 for item in merged_items if item.retrievalStage == "raw_chunk")
    rerank_hits = sum(1 for item in merged_items if classify_evidence_quality(item).qualityScore > 0.2)

    trace = page_context.retrievalTrace
    if trace is not None:
        trace = trace.model_copy(
            update={
                "routeDecision": route_decision,
                "embeddingProvider": settings.embeddingProvider,
                "embeddingModel": settings.embeddingModel,
                "embeddingDimension": settings.embeddingDimension,
                "lexicalHitCount": lexical_hits,
                "vectorHitCount": vector_hits,
                "mergedHitCount": len(merged_items),
                "rerankHitCount": rerank_hits,
                "rawChunkHitCount": raw_chunk_hits,
                "readingPassCount": int(bundle_summary.get("readingPassCount") or trace.readingPassCount or 1),
                "selectedDocumentFamilyCount": int(bundle_summary.get("selectedDocumentFamilyCount") or trace.selectedDocumentFamilyCount or 0),
                "selectedCanonicalKinds": [
                    str(item)
                    for item in bundle_summary.get("selectedCanonicalKinds", trace.selectedCanonicalKinds or [])
                    if str(item).strip()
                ],
                "softwareMaterialIncluded": bool(bundle_summary.get("softwareMaterialIncluded", trace.softwareMaterialIncluded)),
                "workingDocumentIds": [
                    str(item)
                    for item in bundle_summary.get("workingDocumentIds", trace.workingDocumentIds or [])
                    if str(item).strip()
                ],
                "workingDocumentHitCount": int(bundle_summary.get("workingDocumentHitCount") or trace.workingDocumentHitCount or 0),
            }
        )
    return merged_items, trace


def run_data_center_search(
    *,
    query: str,
    route_decision: RouteDecisionRecord,
    retrieval_trace: RetrievalTraceRecord | None,
    answer_plan,
    hits,
    selected_hits,
    missing_context: list[str],
    suggested_followups: list[str],
) -> DataCenterSearchResultRecord:
    return DataCenterSearchResultRecord(
        query=query,
        routeDecision=route_decision,
        retrievalTrace=retrieval_trace,
        answerPlan=answer_plan,
        hits=hits,
        selectedHits=selected_hits,
        missingContext=missing_context,
        suggestedFollowups=suggested_followups,
    )
