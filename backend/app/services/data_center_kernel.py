from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import Database
from app.models import (
    AnswerPlanRecord,
    DataCenterCandidateChainRecord,
    DataCenterKernelResultRecord,
    DataCenterRequestRecord,
    DataCenterSearchHitRecord,
    EvidenceItem,
    PageContextPackRecord,
    RetrievalModelSettingsRecord,
    RouteDecisionRecord,
)
from app.services.action_suggestion_service import build_action_suggestions
from app.services.analysis_context import (
    build_client_page_context_pack,
    build_event_line_page_context_pack,
    build_project_flow_page_context_pack,
    build_project_module_page_context_pack,
    build_task_page_context_pack,
    decide_answer_policy,
    infer_page_intent,
)
from app.services.answer_layer import build_answer_material, build_answer_plan
from app.services.data_center_prep import build_data_center_prep_result
from app.services.data_center_profiler import DataCenterProfiler
from app.services.data_center_proposal import (
    build_data_center_proposal_drafts,
    persist_data_center_proposal_drafts,
)
from app.services.data_center_quality import validate_answer_quality
from app.services.data_center_search import (
    build_data_center_retrieval_items,
    run_data_center_search,
)
from app.services.data_center_shadow import create_data_center_shadow_run
from app.services.evidence_quality import classify_evidence_quality
from app.services.evidence_quality_store import persist_evidence_quality_annotations_for_items
from app.services.evidence_quality_feedback import build_evidence_excerpt_hash
from app.services.evidence_selector import select_answer_evidence_with_trace
from app.services.meeting_context import build_meeting_page_context_pack
from app.services.query_router import route_page_query
from app.services.retrieval_model_settings import get_retrieval_model_settings
from app.services.source_reachability import build_source_reachability_audit
from app.services.topic_data_center import build_topic_page_context_pack

def _build_page_context(
    db: Database,
    *,
    data_dir: Path,
    request: DataCenterRequestRecord,
) -> PageContextPackRecord:
    scope = request.scope
    prompt = request.prompt or ""
    intent = infer_page_intent(prompt, scope.page)

    if scope.scopeType == "task" or scope.page in {"task_detail", "task_ai"}:
        task_id = scope.taskId or scope.scopeId
        return build_task_page_context_pack(
            db,
            data_dir=data_dir,
            task_id=task_id,
            prompt=prompt,
            page=scope.page,
            intent=intent,
            include_raw_evidence=request.includeRawEvidence,
        )

    if scope.scopeType == "meeting" or scope.page == "meeting_detail":
        meeting_id = scope.meetingId or scope.scopeId
        return build_meeting_page_context_pack(
            db,
            data_dir=data_dir,
            meeting_id=meeting_id,
            prompt=prompt,
            include_raw_evidence=request.includeRawEvidence,
        )

    if scope.scopeType == "event_line" or scope.page == "event_line_detail":
        event_line_id = scope.eventLineId or scope.scopeId
        return build_event_line_page_context_pack(
            db,
            data_dir=data_dir,
            event_line_id=event_line_id,
            prompt=prompt,
            page=scope.page,
            intent=intent,
            include_raw_evidence=request.includeRawEvidence,
        )

    if scope.scopeType == "project_module" or scope.page == "project_module_detail":
        module_id = scope.projectModuleId or scope.scopeId
        return build_project_module_page_context_pack(
            db,
            data_dir=data_dir,
            module_id=module_id,
            prompt=prompt,
            page=scope.page,
            intent=intent,
            include_raw_evidence=request.includeRawEvidence,
        )

    if scope.scopeType == "project_flow" or scope.page == "project_flow_detail":
        flow_id = scope.projectFlowId or scope.scopeId
        return build_project_flow_page_context_pack(
            db,
            data_dir=data_dir,
            flow_id=flow_id,
            prompt=prompt,
            page=scope.page,
            intent=intent,
            include_raw_evidence=request.includeRawEvidence,
        )

    if scope.scopeType == "topic" or scope.page == "topic_radar":
        topic_id = scope.topicId or scope.scopeId
        return build_topic_page_context_pack(
            db,
            data_dir=data_dir,
            topic_id=topic_id,
            prompt=prompt,
            include_raw_evidence=request.includeRawEvidence,
        )

    client_id = scope.clientId or scope.scopeId
    pack = build_client_page_context_pack(
        db,
        data_dir=data_dir,
        client_id=client_id,
        prompt=prompt,
        page=scope.page,
        intent=intent,
        include_raw_evidence=request.includeRawEvidence,
        workspace=None,
    )
    if scope.page == "strategic_cockpit":
        strategic_summary = {
            "openQuestionCount": len(pack.openQuestions),
            "conflictCount": len(pack.conflicts),
            "officialJudgmentCount": len(pack.officialJudgments),
            "candidateJudgmentCount": len(pack.candidateJudgments),
            "pendingDecisions": len(pack.openQuestions),
            "pendingMaterials": len(pack.missingContext),
        }
        pack.retrievalPlan = {**pack.retrievalPlan, "strategicSummary": strategic_summary}
        pack.stateProjection = {
            **(pack.stateProjection or {}),
            "strategicSnapshot": strategic_summary,
            "readiness": "high" if strategic_summary["officialJudgmentCount"] else "medium",
        }
    return pack


def _route_with_settings(
    db: Database,
    *,
    request: DataCenterRequestRecord,
    page_context: PageContextPackRecord,
    settings: RetrievalModelSettingsRecord,
    ai_service: Any | None,
) -> RouteDecisionRecord:
    return route_page_query(
        db,
        page=request.scope.page,
        prompt=request.prompt,
        client_id=request.scope.clientId,
        task_id=request.scope.taskId,
        page_context=page_context,
        settings=settings,
        ai_service=ai_service,
    )


def _to_search_hit(
    item: EvidenceItem,
    *,
    selected: bool,
    annotation_id: str | None = None,
    human_label: str | None = None,
) -> DataCenterSearchHitRecord:
    signal = classify_evidence_quality(item)
    quality_flags: list[str] = []
    if item.retrievalStage == "raw_chunk":
        quality_flags.append("raw_chunk")
    if item.sectionLabel:
        quality_flags.append("section_labeled")
    if (item.score or 0.0) < 0.2 or signal.qualityScore < 0.0:
        quality_flags.append("low_score")
    quality_flags.extend(signal.noiseReasons)
    quality_flags.append(f"source_kind:{signal.sourceKind}")
    quality_flags.append(f"authority:{signal.authorityHint}")
    return DataCenterSearchHitRecord(
        title=item.title,
        excerpt=item.excerpt,
        sourceType=item.sourceType,
        documentId=item.documentId,
        path=item.path,
        originalPath=item.originalPath,
        managedPath=item.managedPath,
        markdownPath=item.markdownPath,
        openableKind=item.openableKind,
        sourceAvailability=item.sourceAvailability,
        originalAvailable=item.originalAvailable,
        machineReadableAvailable=item.machineReadableAvailable,
        openOriginalDisabledReason=item.openOriginalDisabledReason,
        score=item.score,
        sectionLabel=item.sectionLabel,
        retrievalStage=item.retrievalStage,
        selectedForAnswer=selected,
        qualityFlags=quality_flags,
        annotationId=annotation_id,
        humanLabel=human_label if human_label in {"useful", "noise", "needs_review"} else None,
    )


def _is_markdown_path(value: str | None) -> bool:
    return str(value or "").strip().lower().endswith((".md", ".markdown"))


def _existing_non_markdown_source_path(record: DataCenterSearchHitRecord) -> str | None:
    for raw_path in (record.originalPath, record.managedPath, record.path):
        path_value = str(raw_path or "").strip()
        if not path_value or _is_markdown_path(path_value):
            continue
        try:
            path = Path(path_value)
            if path.is_file():
                return path_value
        except OSError:
            continue
    return None


def _is_file_search_source_hit(record: DataCenterSearchHitRecord) -> bool:
    if record.openableKind != "original_file":
        return False
    if record.sourceAvailability != "original_available":
        return False
    if record.originalAvailable is not True:
        return False
    return bool(_existing_non_markdown_source_path(record))


def _filter_file_search_source_hits(records: list[DataCenterSearchHitRecord]) -> list[DataCenterSearchHitRecord]:
    return [record for record in records if _is_file_search_source_hit(record)]


def _doc_keys(items: list[DataCenterSearchHitRecord]) -> set[str]:
    keys: set[str] = set()
    for item in items:
        keys.add(f"{item.documentId or ''}:{item.path or ''}:{(item.excerpt or '')[:80]}")
    return keys


def _shadow_overlap(baseline_hits: list[DataCenterSearchHitRecord], candidate_hits: list[DataCenterSearchHitRecord]) -> float:
    base_keys = _doc_keys(baseline_hits)
    cand_keys = _doc_keys(candidate_hits)
    if not base_keys or not cand_keys:
        return 0.0
    return round(len(base_keys & cand_keys) / max(len(base_keys), len(cand_keys)), 4)


def _build_annotation_map(annotations: list[object]) -> dict[str, tuple[str, str | None]]:
    annotation_map: dict[str, tuple[str, str | None]] = {}
    for annotation in annotations:
        excerpt_hash = str(getattr(annotation, "excerptHash", "") or "").strip()
        annotation_id = str(getattr(annotation, "id", "") or "").strip()
        if not excerpt_hash or not annotation_id:
            continue
        human_label_raw = str(getattr(annotation, "humanLabel", "") or "").strip()
        human_label = human_label_raw if human_label_raw in {"useful", "noise", "needs_review"} else None
        annotation_map[excerpt_hash] = (annotation_id, human_label)
    return annotation_map


def _annotation_payload_for_item(
    item: EvidenceItem,
    annotation_map: dict[str, tuple[str, str | None]],
) -> tuple[str | None, str | None]:
    excerpt_hash = build_evidence_excerpt_hash(
        title=item.title,
        excerpt=item.excerpt,
        path=item.path,
    )
    return annotation_map.get(excerpt_hash, (None, None))


def compute_data_center_candidate_chain(
    *,
    db: Database,
    request: DataCenterRequestRecord,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    answer_policy,
    evidence_items: list[EvidenceItem],
    include_action_suggestions: bool,
) -> DataCenterCandidateChainRecord:
    try:
        answer_plan: AnswerPlanRecord | None = None
        answer_material = None
        selected_evidence: list[EvidenceItem] = []
        answer_quality: dict[str, object] = {}
        question_focus_frame = None
        evidence_decision_trace: list[dict[str, object]] = []
        selected_evidence_roles: list[str] = []
        unselected_high_priority_sources: list[dict[str, object]] = []
        source_reachability: dict[str, object] = {}

        if request.mode in {"answer", "diagnostic", "search", "prep", "proposal"}:
            answer_plan = build_answer_plan(
                prompt=request.prompt,
                page_context=page_context,
                route_decision=route_decision,
                answer_policy=answer_policy,
            )
            feedback_db = (
                db
                if route_decision.retrievalMode != "state_only"
                and route_decision.judgmentQueryMode != "registry_only"
                else None
            )
            selection_result = select_answer_evidence_with_trace(
                prompt=request.prompt,
                intent=answer_plan.intent,
                route_decision=route_decision,
                evidence=evidence_items,
                page_context=page_context,
                db=feedback_db,
                source_type=request.scope.page,
                source_id=request.scope.scopeId,
            )
            selected_evidence = selection_result.selected
            question_focus_frame = selection_result.question_focus_frame
            evidence_decision_trace = [item.model_dump(mode="json") for item in selection_result.decision_trace[:16]]
            selected_evidence_roles = [str(item) for item in selection_result.selected_roles]
            unselected_high_priority_sources = selection_result.unselected_high_priority_sources[:10]
            source_reachability = build_source_reachability_audit(
                db,
                client_id=page_context.clientId,
                focus_frame=selection_result.question_focus_frame,
                evidence_items=evidence_items,
                selected_evidence=selected_evidence,
            )
            answer_material = build_answer_material(
                prompt=request.prompt,
                page_context=page_context,
                route_decision=route_decision,
                retrieval_evidence=selected_evidence,
                answer_plan=answer_plan,
                question_focus_frame=selection_result.question_focus_frame,
            )
            answer_quality = validate_answer_quality(
                prompt=request.prompt,
                content=answer_material.directAnswerSeed,
                answer_plan=answer_plan,
                evidence=selected_evidence,
                answer_material=answer_material,
            )

        selected_ids = {item.id for item in selected_evidence}
        search_hits = [_to_search_hit(item, selected=item.id in selected_ids) for item in evidence_items[:60]]
        action_suggestions = []
        if answer_material is not None and include_action_suggestions:
            action_suggestions = build_action_suggestions(
                page_context=page_context,
                route_decision=route_decision,
                answer_policy=answer_policy,
                answer_material=answer_material,
            )

        return DataCenterCandidateChainRecord(
            routeDecision=route_decision,
            selectedEvidence=selected_evidence,
            searchHits=search_hits,
            answerPlan=answer_plan,
            answerMaterial=answer_material,
            answerQuality=answer_quality,
            actionSuggestions=action_suggestions,
            questionFocusFrame=question_focus_frame,
            evidenceDecisionTrace=evidence_decision_trace,
            selectedEvidenceRoles=selected_evidence_roles,
            unselectedHighPrioritySources=unselected_high_priority_sources,
            sourceReachability=source_reachability,
            failed=False,
            failureReason=None,
        )
    except Exception as exc:
        return DataCenterCandidateChainRecord(
            routeDecision=route_decision,
            failed=True,
            failureReason=str(exc),
        )


def resolve_data_center_kernel(
    db: Database,
    *,
    data_dir: Path,
    request: DataCenterRequestRecord,
    ai_service: Any | None = None,
) -> DataCenterKernelResultRecord:
    profiler = DataCenterProfiler()
    page_context = _build_page_context(db, data_dir=data_dir, request=request)
    profiler.mark("buildPageContextMs")
    answer_policy = page_context.answerPolicy or decide_answer_policy(page_context)
    retrieval_settings = get_retrieval_model_settings(db)

    baseline_settings = retrieval_settings.model_copy(update={"routerEnabled": False, "routerProvider": "rules", "routerMode": "rules"})
    baseline_route = _route_with_settings(
        db,
        request=request,
        page_context=page_context,
        settings=baseline_settings,
        ai_service=None,
    )
    candidate_route = _route_with_settings(
        db,
        request=request,
        page_context=page_context,
        settings=retrieval_settings,
        ai_service=ai_service,
    )
    profiler.mark("routeMs")

    baseline_evidence_items, baseline_trace = build_data_center_retrieval_items(
        db,
        data_dir=data_dir,
        client_id=request.scope.clientId,
        prompt=request.prompt,
        page_context=page_context,
        route_decision=baseline_route,
        settings=baseline_settings,
        working_document_ids=request.workingDocumentIds,
    )
    candidate_evidence_items, candidate_trace = build_data_center_retrieval_items(
        db,
        data_dir=data_dir,
        client_id=request.scope.clientId,
        prompt=request.prompt,
        page_context=page_context,
        route_decision=candidate_route,
        settings=retrieval_settings,
        working_document_ids=request.workingDocumentIds,
    )
    profiler.mark("retrievalMs")
    include_action_suggestions = bool(request.includeActionSuggestions or request.mode in {"proposal", "prep"})
    baseline_chain = compute_data_center_candidate_chain(
        db=db,
        request=request,
        page_context=page_context,
        route_decision=baseline_route,
        answer_policy=answer_policy,
        evidence_items=baseline_evidence_items,
        include_action_suggestions=include_action_suggestions,
    )
    candidate_chain = compute_data_center_candidate_chain(
        db=db,
        request=request,
        page_context=page_context,
        route_decision=candidate_route,
        answer_policy=answer_policy,
        evidence_items=candidate_evidence_items,
        include_action_suggestions=include_action_suggestions,
    )
    profiler.mark("answerChainMs")

    effective_route = baseline_route if request.shadow else candidate_route
    effective_chain = baseline_chain if request.shadow else candidate_chain
    effective_evidence_items = baseline_evidence_items if request.shadow else candidate_evidence_items
    page_context.routeDecision = effective_route
    page_context.retrievalTrace = baseline_trace if request.shadow else candidate_trace
    if page_context.retrievalTrace is not None:
        page_context.retrievalTrace = page_context.retrievalTrace.model_copy(update={"routeDecision": effective_route})

    answer_plan = effective_chain.answerPlan
    answer_material = effective_chain.answerMaterial
    selected_evidence: list[EvidenceItem] = list(effective_chain.selectedEvidence or [])
    answer_quality: dict[str, object] = dict(effective_chain.answerQuality or {})
    search_result = None
    prep_result = None
    proposal_drafts = []
    persisted_proposal_draft_ids: list[str] = []
    deduped_proposal_draft_ids: list[str] = []
    persisted_quality_count = 0
    annotations: list[object] = []

    if request.mode in {"search", "diagnostic"} or request.persistQuality:
        quality_target = selected_evidence or effective_evidence_items[:30]
        paired_quality = [(item, classify_evidence_quality(item)) for item in quality_target[:40]]
        annotations = persist_evidence_quality_annotations_for_items(
            db,
            source_type=request.scope.page,
            source_id=request.scope.scopeId,
            items=paired_quality,
        )
        persisted_quality_count = len(annotations)

    annotation_map = _build_annotation_map(annotations)

    if request.mode == "search":
        raw_hit_records = [
            _to_search_hit(
                item,
                selected=item in selected_evidence,
                annotation_id=_annotation_payload_for_item(item, annotation_map)[0],
                human_label=_annotation_payload_for_item(item, annotation_map)[1],
            )
            for item in effective_evidence_items[:30]
        ]
        hit_records = _filter_file_search_source_hits(raw_hit_records)
        selected_records = [record for record in hit_records if record.selectedForAnswer]
        followups: list[str] = []
        if page_context.missingContext:
            followups.extend([f"补齐：{item}" for item in page_context.missingContext[:4]])
        if effective_route.intent == "business_profile":
            followups.append("可继续追问：这项业务的服务对象和交付方式是什么？")
        elif effective_route.intent == "strategy_profile":
            followups.append("可继续追问：战略重点的时间边界和执行节奏是什么？")
        search_result = run_data_center_search(
            query=request.prompt,
            route_decision=effective_route,
            retrieval_trace=page_context.retrievalTrace,
            answer_plan=answer_plan,
            hits=hit_records,
            selected_hits=selected_records,
            missing_context=list(page_context.missingContext[:8]),
            suggested_followups=list(dict.fromkeys(followups))[:8],
        )

    action_suggestions = list(effective_chain.actionSuggestions or [])

    if request.mode == "prep" and answer_material is not None:
        prep_result = build_data_center_prep_result(
            request=request,
            page_context=page_context,
            route_decision=effective_route,
            answer_material=answer_material,
        )

    if request.mode == "proposal" and answer_material is not None:
        proposal_drafts = build_data_center_proposal_drafts(
            request=request,
            page_context=page_context,
            route_decision=effective_route,
            action_suggestions=action_suggestions,
        )
        if request.persistDrafts and proposal_drafts:
            proposal_drafts, persisted_proposal_draft_ids, deduped_proposal_draft_ids = persist_data_center_proposal_drafts(
                db,
                request=request,
                route_decision=effective_route,
                answer_plan=answer_plan,
                drafts=proposal_drafts,
            )

    debug: dict[str, object] = {}
    boundary_check = {
        "officialBoundaryViolation": bool(answer_quality.get("officialBoundaryViolation")),
        "candidateAsOfficialRisk": bool(answer_quality.get("candidateAsOfficialRisk")),
    }
    fact_slot_summary = {
        "intent": answer_plan.intent if answer_plan is not None else effective_route.intent,
        "factSlotHit": bool(answer_quality.get("factSlotHit", True)),
        "factSlotMissingReason": answer_quality.get("factSlotMissingReason"),
    }
    meeting_followup_summary = {
        "proposalDraftKinds": [item.kind for item in proposal_drafts[:12]],
        "meetingFollowupCount": sum(1 for item in proposal_drafts if item.kind == "meeting_followup"),
        "evidenceRequestCount": sum(1 for item in proposal_drafts if item.kind == "evidence_request"),
        "judgmentReviewCount": sum(1 for item in proposal_drafts if item.kind == "judgment_review"),
    }
    kernel_consistency = {
        "shadowMode": bool(request.shadow),
        "returnedChain": "baseline" if request.shadow else "candidate",
        "baselineIntent": baseline_route.intent,
        "candidateIntent": candidate_route.intent,
        "effectiveIntent": effective_route.intent,
    }
    audit_summary = {
        "questionFocusFrame": (
            effective_chain.questionFocusFrame.model_dump(mode="json")
            if effective_chain.questionFocusFrame is not None
            else {}
        ),
        "evidenceDecisionTrace": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            for item in effective_chain.evidenceDecisionTrace[:16]
        ],
        "selectedEvidenceRoles": list(effective_chain.selectedEvidenceRoles[:10]),
        "unselectedHighPrioritySources": list(effective_chain.unselectedHighPrioritySources[:10]),
        "sourceReachability": dict(effective_chain.sourceReachability or {}),
        "priorityParseFailures": list((effective_chain.sourceReachability or {}).get("priorityParseFailures", [])[:8]),
        "supportOnlySources": list((effective_chain.sourceReachability or {}).get("supportOnlySources", [])[:8]),
    }
    if request.mode == "diagnostic":
        debug = {
            "routeReason": effective_route.routeReason,
            "dataSources": effective_route.dataSources,
            "retrievalMode": effective_route.retrievalMode,
            "selectedEvidenceCount": len(selected_evidence),
            "missingContext": list(page_context.missingContext[:8]),
            "answerQuality": answer_quality,
            "boundaryCheck": boundary_check,
            "factSlotSummary": fact_slot_summary,
            "meetingFollowupSummary": meeting_followup_summary,
            "kernelConsistency": kernel_consistency,
            "candidateFailed": candidate_chain.failed,
            "candidateFailureReason": candidate_chain.failureReason,
            "persistedEvidenceQualityCount": persisted_quality_count,
            **audit_summary,
        }

    if request.shadow:
        baseline_hits = [item for item in baseline_chain.searchHits if item.selectedForAnswer]
        candidate_hits = [item for item in candidate_chain.searchHits if item.selectedForAnswer]
        overlap = _shadow_overlap(baseline_hits, candidate_hits)
        create_data_center_shadow_run(
            db,
            scope_type=request.scope.scopeType,
            scope_id=request.scope.scopeId,
            page=request.scope.page,
            mode=request.mode,
            prompt=request.prompt,
            baseline={
                "routeDecision": baseline_route.model_dump(mode="json"),
                "selectedHits": [item.model_dump(mode="json") for item in baseline_hits[:12]],
                "answerQuality": baseline_chain.answerQuality,
                "answerPlan": (
                    baseline_chain.answerPlan.model_dump(mode="json")
                    if baseline_chain.answerPlan is not None
                    else {}
                ),
            },
            candidate={
                "routeDecision": candidate_route.model_dump(mode="json"),
                "selectedHits": [item.model_dump(mode="json") for item in candidate_hits[:12]],
                "answerQuality": candidate_chain.answerQuality,
                "answerPlan": (
                    candidate_chain.answerPlan.model_dump(mode="json")
                    if candidate_chain.answerPlan is not None
                    else {}
                ),
            },
            route_decision=effective_route.model_dump(mode="json"),
            retrieval_trace=(page_context.retrievalTrace.model_dump(mode="json") if page_context.retrievalTrace else {}),
            answer_plan=(effective_chain.answerPlan.model_dump(mode="json") if effective_chain.answerPlan else {}),
            answer_quality=answer_quality,
            action_suggestion=[item.model_dump(mode="json") for item in action_suggestions[:8]],
            overlap_rate=overlap,
            candidate_failed=bool(candidate_chain.failed),
            failure_reason=candidate_chain.failureReason,
        )
    profiler.mark("shadowWriteMs")

    profiling_summary = profiler.summary()
    debug.update(audit_summary)
    debug.setdefault("profiling", profiling_summary)
    if request.mode == "diagnostic":
        debug["profiling"] = profiling_summary

    return DataCenterKernelResultRecord(
        scope=request.scope,
        pageContext=page_context,
        routeDecision=effective_route,
        retrievalTrace=page_context.retrievalTrace,
        answerPlan=answer_plan,
        answerMaterial=answer_material,
        searchResult=search_result,
        prepResult=prep_result,
        proposalDrafts=proposal_drafts,
        persistedProposalDraftIds=persisted_proposal_draft_ids,
        dedupedDraftIds=deduped_proposal_draft_ids,
        actionSuggestions=action_suggestions,
        quality=page_context.quality,
        debug=debug,
    )
