# backend/app/services/analysis_context.py:1-1120

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.db import Database, from_json
from app.models import (
    AnswerPolicyRecord,
    ContextQualityRecord,
    PageContextPackRecord,
    PageIntentRecord,
    RouteDecisionRecord,
    RetrievalTraceRecord,
)
from app.services.query_router import route_page_query
from app.services.retrieval_model_settings import (
    get_retrieval_model_settings,
    retrieval_embedding_signature,
)
from app.services.analysis_center import (
    list_conflict_groups,
    list_judgment_versions,
    list_open_questions,
    list_runtime_run_logs,
    list_theme_clusters,
    resolve_context_pack,
    resolve_judgment_bundle,
)
from app.services.knowledge_v2 import fetch_document_cards, retrieve_knowledge_bundle
from app.services.memory_foundation import (
    get_client_memory_status,
    get_client_notebook_response,
    get_event_line_memory_response,
    get_task_memory_enrichment,
)

_CHAT_PROCESS_LEAK_MARKERS = (
    "analysis-first",
    "[本周动作]",
    "[缺失信息]",
    "state_first_hit_rate",
    "state_only_fallback_rate",
    "candidate_leakage_count",
    "retrievaldeferred",
)

_INTRO_TOKENS = ("介绍", "简介", "概况", "背景", "做什么", "是谁", "机构")
_PROJECT_INTRO_TOKENS = ("项目介绍", "项目背景", "项目概况", "项目是什么")
_MEETING_TOKENS = ("会议", "纪要", "会后", "会谈")
_NEXT_ACTIONS_TOKENS = ("下一步", "接下来", "后续", "待办", "行动")
_OFFICIAL_TOKENS = ("正式判断", "已批准", "已审批", "官方判断", "系统里", "系统内")
_EVIDENCE_TOKENS = ("证据", "依据", "出处", "原文", "哪份资料", "哪篇", "引用")
_STATUS_TOKENS = (
    "当前状态",
    "进展",
    "风险",
    "卡点",
    "阻塞",
    "阻塞点",
    "推进到哪",
    "推进什么",
    "本周重点",
    "最重要",
    "最值得关注",
    "关注",
    "关注事项",
    "事项",
)
_TASK_CONTEXT_TOKENS = ("任务为什么重要", "任务背景", "任务上下文", "这条任务")
_TASK_NEXT_TOKENS = ("任务下一步", "这条任务下一步", "怎么做")


ClientWorkspaceLike = Any


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    try:
        return dict(value)
    except Exception:
        pass
    return {}


def _as_list(items: Any) -> list[Any]:
    if isinstance(items, list):
        return items
    return []


def _dump_items(items: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(items):
        if isinstance(item, dict):
            result.append(dict(item))
            continue
        dumped = _as_dict(item)
        if dumped:
            result.append(dumped)
    return result


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _contains_any(haystack: str, tokens: tuple[str, ...]) -> bool:
    return any(token in haystack for token in tokens)


def _intent_default_for_page(page: str) -> str:
    if page in {"task_detail", "task_ai"}:
        return "task_context"
    return "general"


def infer_page_intent(prompt: str, page: str) -> PageIntentRecord:
    raw_prompt = str(prompt or "")
    normalized = re.sub(r"\s+", "", raw_prompt.lower())

    intent = _intent_default_for_page(page)
    route_reason = "default"

    if normalized:
        if _contains_any(normalized, _OFFICIAL_TOKENS):
            intent = "official_judgment_registry"
            route_reason = "matched_official_keywords"
        elif _contains_any(normalized, _PROJECT_INTRO_TOKENS):
            intent = "project_intro"
            route_reason = "matched_project_intro_keywords"
        elif _contains_any(normalized, _MEETING_TOKENS):
            intent = "meeting_summary"
            route_reason = "matched_meeting_keywords"
        elif _contains_any(normalized, _EVIDENCE_TOKENS):
            intent = "evidence_question"
            route_reason = "matched_evidence_keywords"
        elif _contains_any(normalized, _TASK_NEXT_TOKENS):
            intent = "task_next_action"
            route_reason = "matched_task_next_keywords"
        elif _contains_any(normalized, _TASK_CONTEXT_TOKENS):
            intent = "task_context"
            route_reason = "matched_task_context_keywords"
        elif _contains_any(normalized, _NEXT_ACTIONS_TOKENS):
            intent = "next_actions"
            route_reason = "matched_next_actions_keywords"
        elif _contains_any(normalized, _STATUS_TOKENS):
            intent = "status_progress"
            route_reason = "matched_status_keywords"
        elif _contains_any(normalized, _INTRO_TOKENS):
            intent = "intro_profile"
            route_reason = "matched_intro_keywords"

    requires_raw = intent in {"intro_profile", "project_intro", "evidence_question"}
    requires_official = intent == "official_judgment_registry"
    requires_next_actions = intent in {"next_actions", "task_next_action"}
    requires_intro = intent in {"intro_profile", "project_intro"}
    requires_task_context = intent in {"task_context", "task_next_action"}

    return PageIntentRecord(
        rawPrompt=raw_prompt,
        intent=intent,
        requiresOfficialJudgment=requires_official,
        requiresRawEvidence=requires_raw,
        requiresNextActions=requires_next_actions,
        requiresIntroProfile=requires_intro,
        requiresTaskContext=requires_task_context,
        routeReason=route_reason,
    )


def _split_judgments(judgments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    official: list[dict[str, Any]] = []
    candidate: list[dict[str, Any]] = []
    for item in judgments:
        status = str(item.get("status") or "").strip().lower()
        authority = str(item.get("authorityLevel") or "").strip().lower()
        if status == "approved" or authority == "approved":
            official.append(item)
        else:
            candidate.append(item)
    return official, candidate


def _build_client_state_projection(pack: PageContextPackRecord) -> dict[str, Any]:
    return {
        "changeCount": len(pack.themeClusters),
        "riskCount": len(pack.conflicts),
        "openQuestionCount": len(pack.openQuestions),
        "taskCount": len(pack.relatedTasks),
        "meetingCount": len(pack.relatedMeetings),
        "stateConfidence": "high" if len(pack.officialJudgments) >= 1 else "medium" if len(pack.candidateJudgments) >= 1 else "low",
    }


def _build_retrieval_trace(
    *,
    context_pack: PageContextPackRecord,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_signature: str,
    vector_collection: str | None = None,
) -> RetrievalTraceRecord:
    route_decision = context_pack.routeDecision
    if route_decision is None:
        route_decision = RouteDecisionRecord(
            intent=context_pack.intent,
            routeMode="state_first",
            dataSources=["state_pool"],
            retrievalMode="deferred",
            routeReason="context_pack_default",
            routerSource="rules",
        )
    return RetrievalTraceRecord(
        routeDecision=route_decision,
        embeddingProvider=embedding_provider,
        embeddingModel=embedding_model,
        embeddingDimension=embedding_dimension,
        embeddingSignature=embedding_signature,
        vectorCollection=vector_collection,
        lexicalHitCount=len(context_pack.relatedDocuments),
        vectorHitCount=len(context_pack.rawEvidence),
        mergedHitCount=len(context_pack.rawEvidence) + len(context_pack.relatedDocuments),
        rerankHitCount=min(30, len(context_pack.rawEvidence)),
        rawChunkHitCount=len(context_pack.rawEvidence),
        fallbackUsed=bool(context_pack.answerPolicy.fallbackToLegacyRetrieval),
        latencyMs={},
    )


def build_client_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    prompt: str = "",
    page: str = "client_workspace",
    intent: PageIntentRecord | None = None,
    include_raw_evidence: bool = False,
    workspace: ClientWorkspaceLike | None = None,
) -> PageContextPackRecord:
    resolved_intent = intent or infer_page_intent(prompt, page)
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)

    analysis_center: dict[str, Any] | None = None
    context_pack: dict[str, Any] | None = None
    judgment_bundle: dict[str, Any] | None = None
    resolution_trace: dict[str, Any] | None = None
    latest_judgments: list[dict[str, Any]] = []
    latest_topics: list[dict[str, Any]] = []
    latest_conflicts: list[dict[str, Any]] = []
    latest_open_questions: list[dict[str, Any]] = []
    latest_run_logs: list[dict[str, Any]] = []
    related_tasks: list[dict[str, Any]] = []
    related_meetings: list[dict[str, Any]] = []
    related_documents: list[dict[str, Any]] = []
    notebook_summary: dict[str, Any] | None = None
    memory_facts: list[str] = []

    if workspace is not None:
        analysis_center = _as_dict(getattr(workspace, "analysisCenter", None)) or None
        context_pack = _as_dict(getattr(workspace, "latestContextPack", None)) or None
        judgment_bundle = _as_dict(getattr(workspace, "judgmentBundle", None)) or None
        resolution_trace = _as_dict(getattr(workspace, "latestResolutionTrace", None)) or None
        compat_judgment_attr = "latest" + "Judgments"
        latest_judgments = _dump_items(getattr(workspace, compat_judgment_attr, []))
        latest_topics = _dump_items(getattr(workspace, "latestTopics", []))
        latest_conflicts = _dump_items(getattr(workspace, "latestConflicts", []))
        latest_open_questions = _dump_items(getattr(workspace, "latestOpenQuestions", []))
        latest_run_logs = _dump_items(getattr(workspace, "latestRunLogs", []))
        related_tasks = _dump_items(getattr(workspace, "relatedTasks", []))
        related_meetings = _dump_items(getattr(workspace, "meetings", []))
        related_documents = _dump_items(getattr(workspace, "documentCards", []))
        notebook_summary = _as_dict(getattr(workspace, "notebookSummary", None)) or None
        memory_status = _as_dict(getattr(workspace, "memoryStatus", None)) or {}
        if memory_status:
            memory_facts.extend(
                [
                    f"notebookCompleteness={memory_status.get('notebookCompleteness')}",
                    f"eventLineCoverage={memory_status.get('eventLineCoverage')}",
                ]
            )
    else:
        notebook_response = get_client_notebook_response(db, client_id)
        notebook_summary = _as_dict(notebook_response.organizationNotebookSnapshot) or None
        memory_status = _as_dict(get_client_memory_status(db, client_id))
        memory_facts = [item.factValue for item in notebook_response.keyFacts[:8] if item.factValue]

        latest_judgments = _dump_items(list_judgment_versions(db, client_id, limit=10))
        latest_topics = _dump_items(list_theme_clusters(db, client_id, limit=8))
        latest_conflicts = _dump_items(list_conflict_groups(db, client_id, limit=8))
        latest_open_questions = _dump_items(list_open_questions(db, client_id, limit=8))
        latest_run_logs = _dump_items(list_runtime_run_logs(db, client_id, limit=8))
        related_documents = [dict(item) for item in fetch_document_cards(db, client_id, data_dir=data_dir, limit=80)]

        task_rows = db.fetchall(
            """
            SELECT t.id, t.title, t.description, t.status, t.updated_at, t.client_id, t.event_line_id
            FROM tasks t
            WHERE t.client_id = ?
            ORDER BY t.updated_at DESC
            LIMIT 30
            """,
            (client_id,),
        )
        related_tasks = [
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "desc": str(row["description"] or ""),
                "status": str(row["status"]),
                "updatedAt": str(row["updated_at"]),
                "clientId": str(row["client_id"] or ""),
                "eventLineId": str(row["event_line_id"] or "") or None,
            }
            for row in task_rows
        ]

        meeting_rows = db.fetchall(
            """
            SELECT id, title, stage, updated_at
            FROM meetings
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (client_id,),
        )
        related_meetings = [
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "stage": str(row["stage"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in meeting_rows
        ]

        resolved_context_pack, _ = resolve_context_pack(
            db,
            client_id=client_id,
            requested_scope_type="client",
            requested_scope_id=client_id,
            intent_profile="client_overview",
            related_refs=None,
            include_fallback=True,
        )
        context_pack = _as_dict(resolved_context_pack) or None
        resolved_judgment_bundle = resolve_judgment_bundle(
            db,
            client_id=client_id,
            requested_scope_type="client",
            requested_scope_id=client_id,
            intent_profile="client_overview",
            related_refs=None,
        )
        judgment_bundle = _as_dict(resolved_judgment_bundle) or None
        resolution_trace = _as_dict(resolved_judgment_bundle.resolutionTrace) if resolved_judgment_bundle.resolutionTrace else None
        analysis_center = {
            "clientId": client_id,
            "evidenceCardCount": int(db.scalar("SELECT COUNT(*) FROM evidence_cards WHERE client_id = ?", (client_id,)) or 0),
            "themeClusterCount": int(db.scalar("SELECT COUNT(*) FROM theme_clusters WHERE client_id = ?", (client_id,)) or 0),
            "conflictGroupCount": int(db.scalar("SELECT COUNT(*) FROM conflict_groups WHERE client_id = ?", (client_id,)) or 0),
            "openQuestionCount": int(db.scalar("SELECT COUNT(*) FROM open_questions WHERE client_id = ?", (client_id,)) or 0),
            "approvedJudgmentCount": int(
                db.scalar(
                    "SELECT COUNT(*) FROM judgment_versions WHERE client_id = ? AND status = 'approved'",
                    (client_id,),
                )
                or 0
            ),
        }

    official_judgments, candidate_judgments = _split_judgments(latest_judgments)
    overlay_judgments = []
    if judgment_bundle and isinstance(judgment_bundle.get("baselineJudgment"), dict):
        baseline = judgment_bundle["baselineJudgment"]
        baseline_id = str(baseline.get("id") or "")
        official_ids = {str(item.get("id") or "") for item in official_judgments}
        candidate_ids = {str(item.get("id") or "") for item in candidate_judgments}
        baseline_status = str(baseline.get("status") or "").strip().lower()
        baseline_authority = str(baseline.get("authorityLevel") or "").strip().lower()
        if baseline_status == "approved" or baseline_authority == "approved":
            if baseline_id not in official_ids:
                official_judgments.append(baseline)
        elif baseline_id and baseline_id not in candidate_ids:
            candidate_judgments.append(baseline)
    if judgment_bundle and isinstance(judgment_bundle.get("overlayDeltas"), list):
        overlay_judgments = [item for item in judgment_bundle.get("overlayDeltas", []) if isinstance(item, dict)]
        for item in overlay_judgments:
            if item not in candidate_judgments:
                candidate_judgments.append(item)

    evidence_cards = _dump_items(
        db.fetchall(
            """
            SELECT id, source_type, source_id, source_ref, normalized_claim, confidence, time_anchor, review_state, updated_at
            FROM evidence_cards
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (client_id,),
        )
    )

    should_pull_raw = bool(include_raw_evidence or resolved_intent.requiresRawEvidence)
    raw_evidence: list[dict[str, Any]] = []
    retrieval_plan: dict[str, Any] = {
        "strategy": "state_first",
        "requestedRawEvidence": should_pull_raw,
    }

    if should_pull_raw and _clean_text(prompt):
        bundle = retrieve_knowledge_bundle(db, data_dir, client_id, prompt)
        raw_evidence = [
            {
                "title": item.title,
                "excerpt": item.excerpt,
                "path": item.path,
                "documentId": item.knowledge_document_id,
                "sectionLabel": item.section_label,
                "score": item.score,
                "sourceStage": item.source_stage,
            }
            for item in bundle.citations[:10]
        ]
        retrieval_plan.update(
            {
                "strategy": "raw_drilldown",
                "rawCitationCount": len(raw_evidence),
                "coverage": bundle.coverage,
            }
        )

    missing_context: list[str] = []
    if not official_judgments and not candidate_judgments:
        missing_context.append("缺少 judgment 对象（approved/candidate）")
    if not related_documents:
        missing_context.append("缺少 document cards")
    if not related_tasks:
        missing_context.append("缺少 related tasks")
    if not evidence_cards and not raw_evidence:
        missing_context.append("缺少可直接引用的证据")

    boundary_notes: list[str] = []
    if not official_judgments and candidate_judgments:
        boundary_notes.append("当前没有已批准正式判断，候选判断仅用于讨论与补证据。")
    if resolution_trace and resolution_trace.get("fallbackUsed"):
        boundary_notes.append("当前 judgment resolution 使用了 fallback 路径。")

    pack = PageContextPackRecord(
        page=page,
        scopeType="client",
        scopeId=client_id,
        clientId=client_id,
        intent=resolved_intent.intent,
        officialJudgments=official_judgments,
        candidateJudgments=candidate_judgments,
        overlayJudgments=overlay_judgments,
        evidenceCards=evidence_cards,
        rawEvidence=raw_evidence,
        openQuestions=latest_open_questions,
        conflicts=latest_conflicts,
        themeClusters=latest_topics,
        relatedTasks=related_tasks,
        relatedMeetings=related_meetings,
        relatedDocuments=related_documents,
        notebookSummary=notebook_summary,
        memoryFacts=list(dict.fromkeys(memory_facts))[:20],
        contextPack=context_pack,
        judgmentBundle=judgment_bundle,
        resolutionTrace=resolution_trace,
        stateProjection=_as_dict(getattr(workspace, "stateProjection", None)) if workspace is not None else None,
        missingContext=missing_context,
        boundaryNotes=boundary_notes,
        sourceSummary={
            "officialJudgmentCount": len(official_judgments),
            "candidateJudgmentCount": len(candidate_judgments),
            "evidenceCardCount": len(evidence_cards),
            "rawEvidenceCount": len(raw_evidence),
            "openQuestionCount": len(latest_open_questions),
            "conflictCount": len(latest_conflicts),
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
            "documentCount": len(related_documents),
            "runLogCount": len(latest_run_logs),
        },
        retrievalPlan=retrieval_plan,
    )

    route_decision = route_page_query(
        db,
        page=page,
        prompt=prompt,
        client_id=client_id,
        page_context=pack,
        settings=retrieval_settings,
        ai_service=None,
    )
    pack.routeDecision = route_decision

    if route_decision.shouldUseRawEvidence and not pack.rawEvidence and _clean_text(prompt):
        bundle = retrieve_knowledge_bundle(db, data_dir, client_id, prompt)
        pack.rawEvidence = [
            {
                "title": item.title,
                "excerpt": item.excerpt,
                "path": item.path,
                "documentId": item.knowledge_document_id,
                "sectionLabel": item.section_label,
                "score": item.score,
                "sourceStage": item.source_stage,
            }
            for item in bundle.citations[:10]
        ]
        pack.retrievalPlan = {
            **pack.retrievalPlan,
            "strategy": "raw_doc_drilldown",
            "rawCitationCount": len(pack.rawEvidence),
            "coverage": bundle.coverage,
            "routerSource": route_decision.routerSource,
            "routeDecision": route_decision.model_dump(mode="json"),
        }
    else:
        pack.retrievalPlan = {
            **pack.retrievalPlan,
            "routerSource": route_decision.routerSource,
            "routeDecision": route_decision.model_dump(mode="json"),
        }

    if pack.stateProjection is None:
        pack.stateProjection = _build_client_state_projection(pack)

    pack.quality = compute_context_quality(pack)
    pack.answerPolicy = decide_answer_policy(pack)
    pack.retrievalTrace = _build_retrieval_trace(
        context_pack=pack,
        embedding_provider=retrieval_settings.embeddingProvider,
        embedding_model=retrieval_settings.embeddingModel,
        embedding_dimension=retrieval_settings.embeddingDimension,
        embedding_signature=embedding_signature,
    )
    return pack


def _build_lightweight_task_understanding(task_payload: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(str(task_payload.get("title") or "")) or "未命名任务"
    desc = _clean_text(str(task_payload.get("description") or ""))
    status = _clean_text(str(task_payload.get("status") or "todo"))
    due_date = _clean_text(str(task_payload.get("due_date") or ""))
    client_name = _clean_text(str(task_payload.get("client_name") or ""))
    event_line_name = _clean_text(str(task_payload.get("event_line_name") or ""))
    owner_name = _clean_text(str(task_payload.get("owner_name") or ""))

    known_facts = [
        f"任务标题：{title}",
        f"状态：{status}",
        f"负责人：{owner_name or '未指定'}",
    ]
    if due_date:
        known_facts.append(f"截止时间：{due_date}")
    if client_name:
        known_facts.append(f"关联客户：{client_name}")
    if event_line_name:
        known_facts.append(f"关联事件线：{event_line_name}")

    unknowns: list[str] = []
    if not client_name:
        unknowns.append("缺少关联客户")
    if not event_line_name:
        unknowns.append("缺少关联事件线")
    if not desc:
        unknowns.append("任务描述信息偏少")

    source_available = 1
    if desc:
        source_available += 1
    if client_name:
        source_available += 1
    if event_line_name:
        source_available += 1

    coverage = min(100, source_available * 20)
    confidence = max(20, min(60, 18 + source_available * 10))

    why_it_matters = ""
    if client_name and event_line_name:
        why_it_matters = f"这条任务直接关联 {client_name} 的“{event_line_name}”推进，影响当前事件线节奏与后续决策。"
    elif client_name:
        why_it_matters = f"这条任务与客户 {client_name} 相关，会影响该客户线的推进质量。"
    else:
        why_it_matters = "当前缺少客户或事件线上下文，任务重要性判断仍偏保守。"

    progress_now = f"当前状态为 {status}。"
    if due_date:
        progress_now += f" 截止时间：{due_date}。"

    return {
        "taskId": str(task_payload.get("id") or ""),
        "mode": "basic",
        "coverage": coverage,
        "confidence": confidence,
        "whatIsThis": f"任务“{title}”的当前目标是：{desc or '基于已有标题推进执行。'}",
        "whyItMatters": why_it_matters,
        "progressNow": progress_now,
        "unknowns": "；".join(unknowns) if unknowns else "当前关键信息已具备，仍建议补充证据材料。",
        "knownFacts": known_facts,
        "sourceBreakdown": [
            {"sourceType": "task_title", "available": bool(title), "label": "任务标题"},
            {"sourceType": "task_desc", "available": bool(desc), "label": "任务描述"},
            {"sourceType": "client_background", "available": bool(client_name), "label": "客户背景"},
            {"sourceType": "event_line_memory", "available": bool(event_line_name), "label": "事件线"},
        ],
        "optionalAdvice": None,
    }


def build_task_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    task_id: str,
    prompt: str = "",
    page: str = "task_detail",
    intent: PageIntentRecord | None = None,
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    resolved_intent = intent or infer_page_intent(prompt, page)
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)

    task_row = db.fetchone(
        """
        SELECT
            t.*,
            l.name AS list_name,
            l.color AS list_color,
            c.name AS client_name,
            e.name AS event_line_name,
            e.stage AS event_line_stage,
            e.summary AS event_line_summary,
            e.current_blocker AS event_line_blocker,
            e.next_step AS event_line_next_step,
            e.recent_decision AS event_line_recent_decision
        FROM tasks t
        LEFT JOIN task_lists l ON l.id = t.list_id
        LEFT JOIN clients c ON c.id = t.client_id
        LEFT JOIN event_lines e ON e.id = t.event_line_id
        WHERE t.id = ?
        """,
        (task_id,),
    )
    if not task_row:
        raise ValueError("Task not found")

    client_id = str(task_row["client_id"] or "").strip() or None
    event_line_id = str(task_row["event_line_id"] or "").strip() or None

    task_payload = {
        "id": str(task_row["id"]),
        "title": str(task_row["title"]),
        "description": str(task_row["description"] or ""),
        "status": str(task_row["status"]),
        "priority": str(task_row["priority"]),
        "due_date": str(task_row["due_date"] or ""),
        "owner_name": str(task_row["owner_name"] or ""),
        "client_id": client_id,
        "client_name": str(task_row["client_name"] or "") if task_row["client_name"] else "",
        "event_line_id": event_line_id,
        "event_line_name": str(task_row["event_line_name"] or "") if task_row["event_line_name"] else "",
        "event_line_stage": str(task_row["event_line_stage"] or "") if task_row["event_line_stage"] else "",
        "event_line_summary": str(task_row["event_line_summary"] or "") if task_row["event_line_summary"] else "",
        "event_line_blocker": str(task_row["event_line_blocker"] or "") if task_row["event_line_blocker"] else "",
        "event_line_next_step": str(task_row["event_line_next_step"] or "") if task_row["event_line_next_step"] else "",
        "event_line_recent_decision": str(task_row["event_line_recent_decision"] or "") if task_row["event_line_recent_decision"] else "",
        "updated_at": str(task_row["updated_at"] or ""),
    }

    attachment_rows = db.fetchall(
        """
        SELECT id, title, path, kind, source, document_id, created_at
        FROM task_attachments
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (task_id,),
    )
    attachments = [
        {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "path": str(row["path"]),
            "kind": str(row["kind"]),
            "source": str(row["source"]),
            "documentId": str(row["document_id"] or "") or None,
            "createdAt": str(row["created_at"]),
        }
        for row in attachment_rows
    ]

    note_row = db.fetchone("SELECT note FROM task_notes WHERE task_id = ?", (task_id,))
    task_note = str(note_row["note"] or "").strip() if note_row and note_row["note"] else ""

    cached_understanding = db.fetchone("SELECT snapshot_json FROM task_understanding_cache WHERE task_id = ?", (task_id,))
    understanding_snapshot = from_json(cached_understanding["snapshot_json"], {}) if cached_understanding and cached_understanding["snapshot_json"] else {}
    if not isinstance(understanding_snapshot, dict) or not understanding_snapshot:
        understanding_snapshot = _build_lightweight_task_understanding(task_payload)

    context_preview = {
        "taskId": task_id,
        "clientId": client_id,
        "clientName": task_payload["client_name"] or None,
        "eventLineId": event_line_id,
        "eventLineName": task_payload["event_line_name"] or None,
        "summary": _clean_text(task_payload["description"]) or _clean_text(task_payload["title"]),
        "attachmentCount": len(attachments),
    }

    judgment_bundle: dict[str, Any] | None = None
    context_pack: dict[str, Any] | None = None
    resolution_trace: dict[str, Any] | None = None
    official_judgments: list[dict[str, Any]] = []
    candidate_judgments: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    theme_clusters: list[dict[str, Any]] = []
    related_tasks: list[dict[str, Any]] = []
    related_meetings: list[dict[str, Any]] = []
    related_documents: list[dict[str, Any]] = attachments.copy()
    notebook_summary: dict[str, Any] | None = None
    memory_facts: list[str] = []

    memory_hints, _background_readiness, linked_facts = get_task_memory_enrichment(
        db,
        task_id=task_id,
        client_id=client_id,
        event_line_id=event_line_id,
    )
    memory_facts.extend(memory_hints)
    memory_facts.extend([fact.factValue for fact in linked_facts[:6] if fact.factValue])

    event_line_memory = None
    if event_line_id:
        event_line_memory = _as_dict(get_event_line_memory_response(db, event_line_id).eventLineMemorySnapshot) or None
        if event_line_memory:
            related_documents.append({"sourceType": "event_line_memory", "snapshot": event_line_memory})

    if client_id:
        notebook_response = get_client_notebook_response(db, client_id)
        notebook_summary = _as_dict(notebook_response.organizationNotebookSnapshot) or None

        resolved_context_pack, _ = resolve_context_pack(
            db,
            client_id=client_id,
            requested_scope_type="event_line" if event_line_id else "client",
            requested_scope_id=event_line_id or client_id,
            intent_profile="task_ai",
            related_refs={
                "event_line": [event_line_id] if event_line_id else [],
                "task": [task_id],
            },
            include_fallback=True,
        )
        context_pack = _as_dict(resolved_context_pack) or None

        resolved_judgment_bundle = resolve_judgment_bundle(
            db,
            client_id=client_id,
            requested_scope_type="event_line" if event_line_id else "client",
            requested_scope_id=event_line_id or client_id,
            intent_profile="task_ai",
            related_refs={
                "event_line": [event_line_id] if event_line_id else [],
                "task": [task_id],
            },
        )
        judgment_bundle = _as_dict(resolved_judgment_bundle) or None
        resolution_trace = _as_dict(resolved_judgment_bundle.resolutionTrace) if resolved_judgment_bundle.resolutionTrace else None

        judgment_rows = _dump_items(list_judgment_versions(db, client_id, limit=12))
        official_judgments, candidate_judgments = _split_judgments(judgment_rows)
        if judgment_bundle and isinstance(judgment_bundle.get("baselineJudgment"), dict):
            baseline = judgment_bundle["baselineJudgment"]
            baseline_id = str(baseline.get("id") or "")
            official_ids = {str(item.get("id") or "") for item in official_judgments}
            candidate_ids = {str(item.get("id") or "") for item in candidate_judgments}
            baseline_status = str(baseline.get("status") or "").strip().lower()
            baseline_authority = str(baseline.get("authorityLevel") or "").strip().lower()
            if baseline_status == "approved" or baseline_authority == "approved":
                if baseline_id and baseline_id not in official_ids:
                    official_judgments.append(baseline)
            elif baseline_id and baseline_id not in candidate_ids:
                candidate_judgments.append(baseline)

        open_questions = _dump_items(list_open_questions(db, client_id, limit=12))
        conflicts = _dump_items(list_conflict_groups(db, client_id, limit=12))
        theme_clusters = _dump_items(list_theme_clusters(db, client_id, limit=8))

        if event_line_id:
            open_questions = [
                item for item in open_questions
                if str(item.get("scopeType") or item.get("targetType") or "") in {"event_line", "client"}
                and str(item.get("scopeId") or item.get("targetId") or "") in {event_line_id, client_id}
            ]
            conflicts = [
                item for item in conflicts
                if str(item.get("scopeType") or item.get("targetType") or "") in {"event_line", "client"}
                and str(item.get("scopeId") or item.get("targetId") or "") in {event_line_id, client_id}
            ]

        related_task_rows = db.fetchall(
            """
            SELECT id, title, description, status, updated_at, event_line_id
            FROM tasks
            WHERE id != ? AND (client_id = ? OR (? != '' AND event_line_id = ?))
            ORDER BY updated_at DESC
            LIMIT 16
            """,
            (task_id, client_id, event_line_id or "", event_line_id or ""),
        )
        related_tasks = [
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "desc": str(row["description"] or ""),
                "status": str(row["status"]),
                "updatedAt": str(row["updated_at"]),
                "eventLineId": str(row["event_line_id"] or "") or None,
            }
            for row in related_task_rows
        ]

        meeting_rows = db.fetchall(
            """
            SELECT id, title, stage, updated_at
            FROM meetings
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT 12
            """,
            (client_id,),
        )
        related_meetings = [
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "stage": str(row["stage"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in meeting_rows
        ]

        if not attachments:
            related_documents.extend(fetch_document_cards(db, client_id, data_dir=data_dir, limit=10))

    raw_evidence: list[dict[str, Any]] = []
    should_pull_raw = bool(include_raw_evidence or resolved_intent.requiresRawEvidence)
    if should_pull_raw and client_id:
        retrieval_query = "\n".join(
            [
                _clean_text(prompt),
                _clean_text(task_payload["title"]),
                _clean_text(task_payload["description"]),
                _clean_text(task_note),
            ]
        ).strip()
        if retrieval_query:
            bundle = retrieve_knowledge_bundle(db, data_dir, client_id, retrieval_query)
            raw_evidence = [
                {
                    "title": item.title,
                    "excerpt": item.excerpt,
                    "path": item.path,
                    "documentId": item.knowledge_document_id,
                    "sectionLabel": item.section_label,
                    "score": item.score,
                    "sourceStage": item.source_stage,
                }
                for item in bundle.citations[:10]
            ]

    missing_context: list[str] = []
    if not client_id:
        missing_context.append("缺少关联 client")
    if not event_line_id:
        missing_context.append("缺少关联 event line")
    if not attachments and not raw_evidence:
        missing_context.append("缺少可引用附件/原文证据")
    if not official_judgments and not candidate_judgments:
        missing_context.append("缺少 judgment 对象")

    boundary_notes: list[str] = []
    if not official_judgments and candidate_judgments:
        boundary_notes.append("当前只有候选判断，尚未形成已批准正式判断。")
    if not context_pack:
        boundary_notes.append("当前 task 关联范围没有命中稳定 context pack。")

    pack = PageContextPackRecord(
        page=page,
        scopeType="task",
        scopeId=task_id,
        clientId=client_id,
        intent=resolved_intent.intent,
        officialJudgments=official_judgments,
        candidateJudgments=candidate_judgments,
        overlayJudgments=(judgment_bundle or {}).get("overlayDeltas", []) if isinstance(judgment_bundle, dict) else [],
        evidenceCards=[],
        rawEvidence=raw_evidence,
        openQuestions=open_questions,
        conflicts=conflicts,
        themeClusters=theme_clusters,
        relatedTasks=[task_payload, *related_tasks],
        relatedMeetings=related_meetings,
        relatedDocuments=related_documents,
        notebookSummary=notebook_summary,
        memoryFacts=list(dict.fromkeys([*memory_facts, task_note]))[:24],
        contextPack={"taskContextPreview": context_preview, "understanding": understanding_snapshot, "eventLineMemory": event_line_memory},
        judgmentBundle=judgment_bundle,
        resolutionTrace=resolution_trace,
        stateProjection={
            "taskStatus": task_payload["status"],
            "taskDueDate": task_payload["due_date"] or None,
            "taskHasClient": bool(client_id),
            "taskHasEventLine": bool(event_line_id),
            "taskAttachmentCount": len(attachments),
            "eventLineCurrentBlocker": task_payload["event_line_blocker"] or None,
            "eventLineNextStep": task_payload["event_line_next_step"] or None,
            "eventLineRecentDecision": task_payload["event_line_recent_decision"] or None,
        },
        missingContext=missing_context,
        boundaryNotes=boundary_notes,
        sourceSummary={
            "officialJudgmentCount": len(official_judgments),
            "candidateJudgmentCount": len(candidate_judgments),
            "rawEvidenceCount": len(raw_evidence),
            "openQuestionCount": len(open_questions),
            "conflictCount": len(conflicts),
            "taskCount": len(related_tasks) + 1,
            "meetingCount": len(related_meetings),
            "documentCount": len(related_documents),
            "attachmentCount": len(attachments),
        },
        retrievalPlan={
            "strategy": "task_context",
            "requestedRawEvidence": should_pull_raw,
            "taskId": task_id,
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )

    route_decision = route_page_query(
        db,
        page=page,
        prompt=prompt,
        client_id=client_id,
        task_id=task_id,
        page_context=pack,
        settings=retrieval_settings,
        ai_service=None,
    )
    pack.routeDecision = route_decision

    if route_decision.shouldUseRawEvidence and client_id and not pack.rawEvidence:
        retrieval_query = "\n".join(
            [
                _clean_text(prompt),
                _clean_text(task_payload["title"]),
                _clean_text(task_payload["description"]),
                _clean_text(task_note),
            ]
        ).strip()
        if retrieval_query:
            bundle = retrieve_knowledge_bundle(db, data_dir, client_id, retrieval_query)
            pack.rawEvidence = [
                {
                    "title": item.title,
                    "excerpt": item.excerpt,
                    "path": item.path,
                    "documentId": item.knowledge_document_id,
                    "sectionLabel": item.section_label,
                    "score": item.score,
                    "sourceStage": item.source_stage,
                }
                for item in bundle.citations[:10]
            ]
            pack.retrievalPlan = {
                **pack.retrievalPlan,
                "strategy": "task_context_raw_drilldown",
                "rawCitationCount": len(pack.rawEvidence),
                "coverage": bundle.coverage,
            }
    pack.retrievalPlan = {
        **pack.retrievalPlan,
        "routerSource": route_decision.routerSource,
        "routeDecision": route_decision.model_dump(mode="json"),
    }

    pack.quality = compute_context_quality(pack)
    pack.answerPolicy = decide_answer_policy(pack)
    pack.retrievalTrace = _build_retrieval_trace(
        context_pack=pack,
        embedding_provider=retrieval_settings.embeddingProvider,
        embedding_model=retrieval_settings.embeddingModel,
        embedding_dimension=retrieval_settings.embeddingDimension,
        embedding_signature=embedding_signature,
    )
    return pack


def compute_context_quality(context_pack: PageContextPackRecord) -> ContextQualityRecord:
    state_object_count = (
        len(context_pack.officialJudgments)
        + len(context_pack.candidateJudgments)
        + len(context_pack.openQuestions)
        + len(context_pack.conflicts)
        + len(context_pack.themeClusters)
        + len(context_pack.relatedTasks)
        + len(context_pack.relatedMeetings)
    )
    approved_count = len(context_pack.officialJudgments)
    candidate_count = len(context_pack.candidateJudgments)
    evidence_card_count = len(context_pack.evidenceCards)
    raw_evidence_count = len(context_pack.rawEvidence)
    open_question_count = len(context_pack.openQuestions)
    task_count = len(context_pack.relatedTasks)
    meeting_count = len(context_pack.relatedMeetings)

    if approved_count >= 1 and any(value > 0 for value in (evidence_card_count, raw_evidence_count, task_count, meeting_count)):
        context_quality = "strong"
    elif candidate_count >= 1 or (evidence_card_count + raw_evidence_count) >= 2:
        context_quality = "usable"
    elif state_object_count > 0 or len(context_pack.relatedDocuments) > 0:
        context_quality = "weak"
    else:
        context_quality = "none"

    can_use_analysis_first = context_quality in {"strong", "usable"}
    must_fallback_to_legacy = context_quality == "none" or (context_quality == "weak" and raw_evidence_count == 0)

    return ContextQualityRecord(
        stateObjectCount=state_object_count,
        approvedJudgmentCount=approved_count,
        candidateJudgmentCount=candidate_count,
        evidenceCardCount=evidence_card_count,
        rawEvidenceCount=raw_evidence_count,
        openQuestionCount=open_question_count,
        taskCount=task_count,
        meetingCount=meeting_count,
        contextQuality=context_quality,
        canUseAnalysisFirst=can_use_analysis_first,
        mustFallbackToLegacy=must_fallback_to_legacy,
    )


def decide_answer_policy(context_pack: PageContextPackRecord) -> AnswerPolicyRecord:
    intent = context_pack.intent
    approved_count = len(context_pack.officialJudgments)
    candidate_count = len(context_pack.candidateJudgments)
    has_state = bool(
        approved_count
        or candidate_count
        or context_pack.openQuestions
        or context_pack.conflicts
        or context_pack.relatedTasks
        or context_pack.relatedMeetings
    )
    has_structured_evidence = bool(context_pack.evidenceCards or context_pack.relatedDocuments)
    has_raw_evidence = bool(context_pack.rawEvidence)

    if intent == "official_judgment_registry" and approved_count > 0:
        return AnswerPolicyRecord(
            canAnswer=True,
            answerLevel="official",
            mustDiscloseCandidateBoundary=False,
            mustUseRawEvidence=False,
            shouldCreateProposal=False,
            fallbackToLegacyRetrieval=False,
            reason="official_judgment_available",
        )

    if intent in {"intro_profile", "project_intro", "evidence_question"}:
        if has_raw_evidence:
            return AnswerPolicyRecord(
                canAnswer=True,
                answerLevel="evidence_based",
                mustDiscloseCandidateBoundary=False,
                mustUseRawEvidence=True,
                shouldCreateProposal=False,
                fallbackToLegacyRetrieval=True,
                reason="intro_or_evidence_query_requires_raw_evidence",
            )
        if has_structured_evidence:
            return AnswerPolicyRecord(
                canAnswer=True,
                answerLevel="evidence_based",
                mustDiscloseCandidateBoundary=False,
                mustUseRawEvidence=True,
                shouldCreateProposal=False,
                fallbackToLegacyRetrieval=True,
                reason="intro_or_evidence_query_fallback_to_structured_evidence",
            )

    if intent in {"status_progress", "next_actions", "task_context", "task_next_action"} and has_state:
        return AnswerPolicyRecord(
            canAnswer=True,
            answerLevel="official" if approved_count > 0 else "candidate" if candidate_count > 0 else "evidence_based",
            mustDiscloseCandidateBoundary=approved_count == 0 and candidate_count > 0,
            mustUseRawEvidence=False,
```
