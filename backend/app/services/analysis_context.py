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

# P2.13 FREEZE(restrictive-page-intent-keywords): page intent 推断不是只靠 evidence 词。
# intro/project/business/strategy/meeting/next_actions/status 的关键词集和它们的判断顺序，
# 都会直接决定回答走哪条链。这里整体冻结，不再局部调整个别触发词。
_INTRO_TOKENS = ("介绍", "简介", "概况", "背景", "做什么", "是谁", "机构")
_PROJECT_INTRO_TOKENS = ("项目介绍", "项目背景", "项目概况", "项目是什么")
_BUSINESS_TOKENS = ("核心业务", "主营业务", "业务是什么", "业务模式", "主要服务", "服务对象", "核心产品", "产品服务")
_STRATEGY_TOKENS = ("最新战略", "战略是什么", "战略方向", "未来战略", "发展战略", "战略重点", "战略规划")
_MEETING_TOKENS = ("会议", "纪要", "会后", "会谈")
_NEXT_ACTIONS_TOKENS = ("下一步", "接下来", "后续", "待办", "行动")
_OFFICIAL_TOKENS = ("正式判断", "已批准", "已审批", "官方判断", "系统里", "系统内")
# P2.13 FREEZE(restrictive-page-intent): 这组 evidence 词在 page intent 推断阶段优先级高于 intro/profile。
# 只要 prompt 同时出现“介绍”与“依据/原文/引用”，当前系统会先落到 `evidence_question`。
# 这正是“组织画像请求被压短”的关键上游之一。先冻结，不改行为。
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
_TASK_NEXT_TOKENS = ("任务下一步", "这条任务下一步")
_INTRO_PRIORITY_TOKENS = (
    "介绍",
    "简介",
    "概况",
    "概览",
    "机构",
    "组织",
    "它是什么样的机构",
    "它真正想解决的核心问题",
    "它是怎么做这件事的",
    "它有哪些主要业务线",
    "它正在往什么方向升级",
    "用一句话总结它最核心的优势",
)


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

    if page == "workspace_chat":
        # P2.14 FREEZE(answer-shaping-workspace-intent): workspace/chat 主回答链当前只保留
        # `general` 与显式 `official_judgment_registry` 两种 page intent。
        # 这是在冻结“回答塑形半层”的入口边界：不要再把介绍/会议/任务/状态类词汇重新接回
        # page intent 层，去决定主回答的供料模式或回答形态。
        intent = "official_judgment_registry" if _contains_any(normalized, _OFFICIAL_TOKENS) else "general"
        return PageIntentRecord(
            rawPrompt=raw_prompt,
            intent=intent,
            requiresOfficialJudgment=intent == "official_judgment_registry",
            requiresRawEvidence=False,
            requiresNextActions=False,
            requiresIntroProfile=False,
            requiresTaskContext=False,
            routeReason="workspace_chat_open_intent",
        )

    intent = _intent_default_for_page(page)
    route_reason = "default"

    if normalized:
        intro_priority = _contains_any(normalized, _INTRO_PRIORITY_TOKENS) and not _contains_any(
            normalized,
            _TASK_CONTEXT_TOKENS + _TASK_NEXT_TOKENS,
        )
        # P2.13 FREEZE(restrictive-page-intent-precedence): 当前 page intent 判断顺序也是限制的一部分。
        # 尤其是 official -> evidence -> business -> strategy -> project -> meeting -> task -> next_actions -> status -> intro
        # 这会让“介绍客户 + 会议纪要/状态/依据”类 prompt 优先落入更短、更保守的链路。
        if _contains_any(normalized, _OFFICIAL_TOKENS):
            intent = "official_judgment_registry"
            route_reason = "matched_official_keywords"
        elif _contains_any(normalized, _BUSINESS_TOKENS):
            intent = "business_profile"
            route_reason = "matched_business_profile_keywords"
        elif _contains_any(normalized, _STRATEGY_TOKENS):
            intent = "strategy_profile"
            route_reason = "matched_strategy_profile_keywords"
        elif _contains_any(normalized, _PROJECT_INTRO_TOKENS):
            intent = "project_intro"
            route_reason = "matched_project_intro_keywords"
        elif intro_priority:
            intent = "intro_profile"
            route_reason = "matched_intro_priority_keywords"
        elif _contains_any(normalized, _EVIDENCE_TOKENS):
            intent = "evidence_question"
            route_reason = "matched_evidence_keywords"
        elif _contains_any(normalized, _MEETING_TOKENS):
            intent = "meeting_summary"
            route_reason = "matched_meeting_keywords"
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

    requires_raw = intent in {"intro_profile", "project_intro", "evidence_question", "business_profile", "strategy_profile"}
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


def _analysis_scope_type_for_page_scope(scope_type: str) -> str:
    normalized = str(scope_type or "").strip().lower()
    if normalized == "project_module":
        return "module"
    if normalized == "project_flow":
        return "flow"
    return normalized


def _serialize_retrieval_citations(bundle, *, limit: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "title": item.title,
            "excerpt": item.excerpt,
            "path": item.path,
            "documentId": item.knowledge_document_id,
            "sectionLabel": item.section_label,
            "score": item.score,
            "sourceStage": item.source_stage,
        }
        for item in bundle.citations[:limit]
    ]


def _build_raw_evidence_for_scope(
    db: Database,
    *,
    data_dir: Path,
    client_id: str | None,
    prompt: str,
    include_raw_evidence: bool,
    requires_raw_evidence: bool,
    extra_query_lines: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not client_id:
        return [], {}
    should_pull_raw = bool(include_raw_evidence or requires_raw_evidence)
    if not should_pull_raw:
        return [], {}
    query_parts = [_clean_text(prompt)]
    for item in extra_query_lines or []:
        text = _clean_text(item)
        if text:
            query_parts.append(text)
    retrieval_query = "\n".join(part for part in query_parts if part).strip()
    if not retrieval_query:
        return [], {}
    bundle = retrieve_knowledge_bundle(db, data_dir, client_id, retrieval_query)
    return _serialize_retrieval_citations(bundle), {"rawCitationCount": len(bundle.citations), "coverage": bundle.coverage}


def _scope_related_refs(scope_type: str, scope_id: str, client_id: str | None) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    normalized_scope_type = _analysis_scope_type_for_page_scope(scope_type)
    if normalized_scope_type and scope_id:
        refs[normalized_scope_type] = [scope_id]
    if client_id:
        refs["client"] = [client_id]
    return refs


def _scoped_judgment_pack(
    db: Database,
    *,
    client_id: str | None,
    scope_type: str,
    scope_id: str,
    intent_profile: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    if not client_id:
        return [], [], None, None
    analysis_scope_type = _analysis_scope_type_for_page_scope(scope_type)
    latest_judgments = _dump_items(
        list_judgment_versions(
            db,
            client_id,
            limit=12,
            target_type=analysis_scope_type,  # type: ignore[arg-type]
            target_id=scope_id,
        )
    )
    official_judgments, candidate_judgments = _split_judgments(latest_judgments)
    context_pack_row, _context_trace = resolve_context_pack(
        db,
        client_id=client_id,
        requested_scope_type=analysis_scope_type,  # type: ignore[arg-type]
        requested_scope_id=scope_id,
        intent_profile=intent_profile,  # type: ignore[arg-type]
        related_refs=_scope_related_refs(scope_type, scope_id, client_id),
        include_fallback=True,
    )
    context_pack = _as_dict(context_pack_row) if context_pack_row else None
    judgment_bundle_row = resolve_judgment_bundle(
        db,
        client_id=client_id,
        requested_scope_type=analysis_scope_type,  # type: ignore[arg-type]
        requested_scope_id=scope_id,
        intent_profile=intent_profile,  # type: ignore[arg-type]
        related_refs=_scope_related_refs(scope_type, scope_id, client_id),
    )
    judgment_bundle = _as_dict(judgment_bundle_row) if judgment_bundle_row else None
    resolution_trace = (
        _as_dict(judgment_bundle_row.resolutionTrace)
        if judgment_bundle_row and judgment_bundle_row.resolutionTrace
        else None
    )
    if judgment_bundle and isinstance(judgment_bundle.get("baselineJudgment"), dict):
        baseline = judgment_bundle["baselineJudgment"]
        baseline_id = str(baseline.get("id") or "")
        baseline_status = str(baseline.get("status") or "").strip().lower()
        baseline_authority = str(baseline.get("authorityLevel") or "").strip().lower()
        if baseline_status == "approved" or baseline_authority == "approved":
            if baseline_id and all(str(item.get("id") or "") != baseline_id for item in official_judgments):
                official_judgments.append(baseline)
        elif baseline_id and all(str(item.get("id") or "") != baseline_id for item in candidate_judgments):
            candidate_judgments.append(baseline)
    if judgment_bundle and isinstance(judgment_bundle.get("overlayDeltas"), list):
        for item in judgment_bundle.get("overlayDeltas", []):
            if isinstance(item, dict) and item not in candidate_judgments:
                candidate_judgments.append(item)
    return official_judgments, candidate_judgments, context_pack, resolution_trace


def _scoped_analysis_objects(
    db: Database,
    *,
    client_id: str | None,
    scope_type: str,
    scope_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not client_id:
        return [], [], []
    analysis_scope_type = _analysis_scope_type_for_page_scope(scope_type)
    open_questions = _dump_items(
        list_open_questions(
            db,
            client_id,
            limit=10,
            scope_type=analysis_scope_type,  # type: ignore[arg-type]
            scope_id=scope_id,
        )
    )
    conflicts = _dump_items(
        list_conflict_groups(
            db,
            client_id,
            limit=10,
            scope_type=analysis_scope_type,  # type: ignore[arg-type]
            scope_id=scope_id,
        )
    )
    theme_clusters = _dump_items(
        list_theme_clusters(
            db,
            client_id,
            limit=10,
            scope_type=analysis_scope_type,  # type: ignore[arg-type]
            scope_id=scope_id,
        )
    )
    return open_questions, conflicts, theme_clusters


def build_event_line_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    event_line_id: str,
    prompt: str = "",
    page: str = "event_line_detail",
    intent: PageIntentRecord | None = None,
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    resolved_intent = intent or infer_page_intent(prompt, page)
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)
    row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
    if not row:
        raise ValueError("Event line not found")

    client_id = str(row["primary_client_id"] or "").strip() or None
    if not client_id:
        task_client = db.fetchone(
            "SELECT client_id FROM tasks WHERE event_line_id = ? AND COALESCE(client_id, '') != '' ORDER BY updated_at DESC LIMIT 1",
            (event_line_id,),
        )
        if task_client and task_client["client_id"]:
            client_id = str(task_client["client_id"]).strip() or None

    related_tasks = _dump_items(
        db.fetchall(
            """
            SELECT id, title, description, status, owner_name, due_date, updated_at, client_id
            FROM tasks
            WHERE event_line_id = ?
            ORDER BY updated_at DESC
            LIMIT 30
            """,
            (event_line_id,),
        )
    )

    meeting_rows = db.fetchall(
        """
        SELECT m.id, m.title, m.stage, m.updated_at
        FROM event_line_activities a
        JOIN meetings m ON m.id = a.source_id
        WHERE a.event_line_id = ? AND a.source_type = 'meeting'
        ORDER BY a.happened_at DESC
        LIMIT 20
        """,
        (event_line_id,),
    )
    related_meetings = _dump_items(meeting_rows)

    attachment_rows = db.fetchall(
        """
        SELECT id, title, path, kind, source, document_id, created_at
        FROM task_attachments
        WHERE event_line_id = ?
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (event_line_id,),
    )
    related_documents = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "path": str(item.get("path") or ""),
            "kind": str(item.get("kind") or ""),
            "source": str(item.get("source") or "task_attachment"),
            "documentId": str(item.get("document_id") or "") or None,
            "createdAt": str(item.get("created_at") or ""),
        }
        for item in attachment_rows
    ]
    if client_id:
        for card in fetch_document_cards(db, client_id, data_dir=data_dir, limit=24):
            related_documents.append(dict(card))

    raw_evidence, raw_meta = _build_raw_evidence_for_scope(
        db,
        data_dir=data_dir,
        client_id=client_id,
        prompt=prompt,
        include_raw_evidence=include_raw_evidence,
        requires_raw_evidence=resolved_intent.requiresRawEvidence,
        extra_query_lines=[
            str(row["name"] or ""),
            str(row["summary"] or ""),
            str(row["intent"] or ""),
            str(row["next_step"] or ""),
        ],
    )

    official_judgments, candidate_judgments, context_pack, resolution_trace = _scoped_judgment_pack(
        db,
        client_id=client_id,
        scope_type="event_line",
        scope_id=event_line_id,
        intent_profile="event_line_progress",
    )
    open_questions, conflicts, theme_clusters = _scoped_analysis_objects(
        db,
        client_id=client_id,
        scope_type="event_line",
        scope_id=event_line_id,
    )
    memory_snapshot = _as_dict(get_event_line_memory_response(db, event_line_id).eventLineMemorySnapshot)

    missing_context: list[str] = []
    if not client_id:
        missing_context.append("事件线缺少关联 client")
    if not related_tasks:
        missing_context.append("事件线缺少关联任务")
    if not related_documents and not raw_evidence:
        missing_context.append("事件线缺少可引用资料/原文")
    if not official_judgments and not candidate_judgments:
        missing_context.append("缺少事件线 judgment 对象")

    boundary_notes: list[str] = []
    if candidate_judgments and not official_judgments:
        boundary_notes.append("当前仅有候选判断，尚未形成已批准正式判断。")
    if not context_pack:
        boundary_notes.append("当前事件线尚未沉淀稳定 context pack。")

    pack = PageContextPackRecord(
        page=page,  # type: ignore[arg-type]
        scopeType="event_line",
        scopeId=event_line_id,
        clientId=client_id,
        intent=resolved_intent.intent,
        officialJudgments=official_judgments,
        candidateJudgments=candidate_judgments,
        overlayJudgments=[],
        evidenceCards=[],
        rawEvidence=raw_evidence,
        openQuestions=open_questions,
        conflicts=conflicts,
        themeClusters=theme_clusters,
        relatedTasks=related_tasks,
        relatedMeetings=related_meetings,
        relatedDocuments=related_documents[:40],
        notebookSummary=None,
        memoryFacts=[item for item in [str(row["summary"] or "").strip(), str(row["current_blocker"] or "").strip(), str(row["next_step"] or "").strip()] if item],
        contextPack={"eventLine": _as_dict(row), "eventLineMemory": memory_snapshot, "analysisContextPack": context_pack},
        judgmentBundle=None,
        resolutionTrace=resolution_trace,
        stateProjection={
            "eventLineStatus": str(row["status"] or ""),
            "eventLineStage": str(row["stage"] or ""),
            "eventLineCurrentBlocker": str(row["current_blocker"] or "") or None,
            "eventLineNextStep": str(row["next_step"] or "") or None,
            "eventLineRecentDecision": str(row["recent_decision"] or "") or None,
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
        },
        missingContext=missing_context,
        boundaryNotes=boundary_notes,
        sourceSummary={
            "officialJudgmentCount": len(official_judgments),
            "candidateJudgmentCount": len(candidate_judgments),
            "rawEvidenceCount": len(raw_evidence),
            "openQuestionCount": len(open_questions),
            "conflictCount": len(conflicts),
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
            "documentCount": len(related_documents),
        },
        retrievalPlan={
            "strategy": "event_line_context",
            "requestedRawEvidence": bool(include_raw_evidence or resolved_intent.requiresRawEvidence),
            "eventLineId": event_line_id,
            "clientId": client_id,
            **raw_meta,
        },
    )
    route_decision = route_page_query(
        db,
        page=page,  # type: ignore[arg-type]
        prompt=prompt,
        client_id=client_id,
        page_context=pack,
        settings=retrieval_settings,
        ai_service=None,
    )
    pack.routeDecision = route_decision
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


def build_project_module_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    module_id: str,
    prompt: str = "",
    page: str = "project_module_detail",
    intent: PageIntentRecord | None = None,
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    resolved_intent = intent or infer_page_intent(prompt, page)
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)
    row = db.fetchone("SELECT * FROM project_modules WHERE id = ?", (module_id,))
    if not row:
        raise ValueError("Project module not found")
    client_id = str(row["client_id"] or "").strip() or None
    flow_rows = db.fetchall(
        "SELECT id, name, scenario, trigger_condition, updated_at FROM project_flows WHERE module_id = ? ORDER BY updated_at DESC LIMIT 20",
        (module_id,),
    )
    related_tasks = _dump_items(
        db.fetchall(
            """
            SELECT id, title, description, status, owner_name, due_date, updated_at, event_line_id
            FROM tasks
            WHERE project_module_id = ?
            ORDER BY updated_at DESC
            LIMIT 30
            """,
            (module_id,),
        )
    )
    meeting_rows = db.fetchall(
        """
        SELECT DISTINCT m.id, m.title, m.stage, m.updated_at
        FROM tasks t
        JOIN meetings m ON m.id = t.source_id
        WHERE t.project_module_id = ? AND t.source_type = 'meeting'
        ORDER BY m.updated_at DESC
        LIMIT 20
        """,
        (module_id,),
    )
    related_meetings = _dump_items(meeting_rows)
    related_documents = [dict(item) for item in fetch_document_cards(db, client_id, data_dir=data_dir, limit=30)] if client_id else []
    raw_evidence, raw_meta = _build_raw_evidence_for_scope(
        db,
        data_dir=data_dir,
        client_id=client_id,
        prompt=prompt,
        include_raw_evidence=include_raw_evidence,
        requires_raw_evidence=resolved_intent.requiresRawEvidence,
        extra_query_lines=[str(row["name"] or ""), str(row["goal"] or ""), str(row["description"] or "")],
    )
    official_judgments, candidate_judgments, context_pack, resolution_trace = _scoped_judgment_pack(
        db,
        client_id=client_id,
        scope_type="project_module",
        scope_id=module_id,
        intent_profile="module_focus",
    )
    open_questions, conflicts, theme_clusters = _scoped_analysis_objects(
        db,
        client_id=client_id,
        scope_type="project_module",
        scope_id=module_id,
    )
    missing_context: list[str] = []
    if not client_id:
        missing_context.append("模块缺少关联 client")
    if not related_tasks:
        missing_context.append("模块缺少关联任务")
    if not flow_rows:
        missing_context.append("模块尚未定义流程")
    if not official_judgments and not candidate_judgments:
        missing_context.append("模块缺少 judgment 对象")
    if not related_documents and not raw_evidence:
        missing_context.append("模块缺少可引用资料/原文")

    boundary_notes: list[str] = []
    if candidate_judgments and not official_judgments:
        boundary_notes.append("当前模块只有候选判断，尚未形成已批准正式判断。")
    if not context_pack:
        boundary_notes.append("当前模块尚未沉淀稳定 context pack。")

    pack = PageContextPackRecord(
        page=page,  # type: ignore[arg-type]
        scopeType="project_module",
        scopeId=module_id,
        clientId=client_id,
        intent=resolved_intent.intent,
        officialJudgments=official_judgments,
        candidateJudgments=candidate_judgments,
        overlayJudgments=[],
        evidenceCards=[],
        rawEvidence=raw_evidence,
        openQuestions=open_questions,
        conflicts=conflicts,
        themeClusters=theme_clusters,
        relatedTasks=related_tasks,
        relatedMeetings=related_meetings,
        relatedDocuments=related_documents,
        notebookSummary=None,
        memoryFacts=[item for item in [str(row["goal"] or "").strip(), str(row["description"] or "").strip()] if item],
        contextPack={"projectModule": _as_dict(row), "relatedFlows": _dump_items(flow_rows), "analysisContextPack": context_pack},
        judgmentBundle=None,
        resolutionTrace=resolution_trace,
        stateProjection={
            "moduleName": str(row["name"] or ""),
            "moduleGoal": str(row["goal"] or "") or None,
            "flowCount": len(flow_rows),
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
        },
        missingContext=missing_context,
        boundaryNotes=boundary_notes,
        sourceSummary={
            "officialJudgmentCount": len(official_judgments),
            "candidateJudgmentCount": len(candidate_judgments),
            "rawEvidenceCount": len(raw_evidence),
            "openQuestionCount": len(open_questions),
            "conflictCount": len(conflicts),
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
            "documentCount": len(related_documents),
            "flowCount": len(flow_rows),
        },
        retrievalPlan={
            "strategy": "project_module_context",
            "requestedRawEvidence": bool(include_raw_evidence or resolved_intent.requiresRawEvidence),
            "projectModuleId": module_id,
            "clientId": client_id,
            **raw_meta,
        },
    )
    route_decision = route_page_query(
        db,
        page=page,  # type: ignore[arg-type]
        prompt=prompt,
        client_id=client_id,
        page_context=pack,
        settings=retrieval_settings,
        ai_service=None,
    )
    pack.routeDecision = route_decision
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


def build_project_flow_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    flow_id: str,
    prompt: str = "",
    page: str = "project_flow_detail",
    intent: PageIntentRecord | None = None,
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    resolved_intent = intent or infer_page_intent(prompt, page)
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)
    row = db.fetchone(
        """
        SELECT f.*, m.client_id AS client_id, m.name AS module_name
        FROM project_flows f
        LEFT JOIN project_modules m ON m.id = f.module_id
        WHERE f.id = ?
        """,
        (flow_id,),
    )
    if not row:
        raise ValueError("Project flow not found")
    client_id = str(row["client_id"] or "").strip() or None
    related_tasks = _dump_items(
        db.fetchall(
            """
            SELECT id, title, description, status, owner_name, due_date, updated_at, event_line_id
            FROM tasks
            WHERE project_flow_id = ?
            ORDER BY updated_at DESC
            LIMIT 30
            """,
            (flow_id,),
        )
    )
    meeting_rows = db.fetchall(
        """
        SELECT DISTINCT m.id, m.title, m.stage, m.updated_at
        FROM tasks t
        JOIN meetings m ON m.id = t.source_id
        WHERE t.project_flow_id = ? AND t.source_type = 'meeting'
        ORDER BY m.updated_at DESC
        LIMIT 20
        """,
        (flow_id,),
    )
    related_meetings = _dump_items(meeting_rows)
    related_documents = [dict(item) for item in fetch_document_cards(db, client_id, data_dir=data_dir, limit=30)] if client_id else []
    raw_evidence, raw_meta = _build_raw_evidence_for_scope(
        db,
        data_dir=data_dir,
        client_id=client_id,
        prompt=prompt,
        include_raw_evidence=include_raw_evidence,
        requires_raw_evidence=resolved_intent.requiresRawEvidence,
        extra_query_lines=[str(row["name"] or ""), str(row["description"] or ""), str(row["scenario"] or ""), str(row["trigger_condition"] or "")],
    )
    official_judgments, candidate_judgments, context_pack, resolution_trace = _scoped_judgment_pack(
        db,
        client_id=client_id,
        scope_type="project_flow",
        scope_id=flow_id,
        intent_profile="flow_execution",
    )
    open_questions, conflicts, theme_clusters = _scoped_analysis_objects(
        db,
        client_id=client_id,
        scope_type="project_flow",
        scope_id=flow_id,
    )

    missing_context: list[str] = []
    if not client_id:
        missing_context.append("流程缺少关联 client")
    if not related_tasks:
        missing_context.append("流程缺少关联任务")
    if not official_judgments and not candidate_judgments:
        missing_context.append("流程缺少 judgment 对象")
    if not related_documents and not raw_evidence:
        missing_context.append("流程缺少可引用资料/原文")

    boundary_notes: list[str] = []
    if candidate_judgments and not official_judgments:
        boundary_notes.append("当前流程只有候选判断，尚未形成已批准正式判断。")
    if not context_pack:
        boundary_notes.append("当前流程尚未沉淀稳定 context pack。")

    pack = PageContextPackRecord(
        page=page,  # type: ignore[arg-type]
        scopeType="project_flow",
        scopeId=flow_id,
        clientId=client_id,
        intent=resolved_intent.intent,
        officialJudgments=official_judgments,
        candidateJudgments=candidate_judgments,
        overlayJudgments=[],
        evidenceCards=[],
        rawEvidence=raw_evidence,
        openQuestions=open_questions,
        conflicts=conflicts,
        themeClusters=theme_clusters,
        relatedTasks=related_tasks,
        relatedMeetings=related_meetings,
        relatedDocuments=related_documents,
        notebookSummary=None,
        memoryFacts=[item for item in [str(row["description"] or "").strip(), str(row["scenario"] or "").strip(), str(row["trigger_condition"] or "").strip()] if item],
        contextPack={"projectFlow": _as_dict(row), "analysisContextPack": context_pack},
        judgmentBundle=None,
        resolutionTrace=resolution_trace,
        stateProjection={
            "flowName": str(row["name"] or ""),
            "moduleName": str(row["module_name"] or "") or None,
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
            "riskPointCount": len(from_json(str(row["risk_points_json"] or "[]"), [])),
        },
        missingContext=missing_context,
        boundaryNotes=boundary_notes,
        sourceSummary={
            "officialJudgmentCount": len(official_judgments),
            "candidateJudgmentCount": len(candidate_judgments),
            "rawEvidenceCount": len(raw_evidence),
            "openQuestionCount": len(open_questions),
            "conflictCount": len(conflicts),
            "taskCount": len(related_tasks),
            "meetingCount": len(related_meetings),
            "documentCount": len(related_documents),
        },
        retrievalPlan={
            "strategy": "project_flow_context",
            "requestedRawEvidence": bool(include_raw_evidence or resolved_intent.requiresRawEvidence),
            "projectFlowId": flow_id,
            "clientId": client_id,
            **raw_meta,
        },
    )
    route_decision = route_page_query(
        db,
        page=page,  # type: ignore[arg-type]
        prompt=prompt,
        client_id=client_id,
        page_context=pack,
        settings=retrieval_settings,
        ai_service=None,
    )
    pack.routeDecision = route_decision
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

    if intent in {"intro_profile", "project_intro", "evidence_question", "business_profile", "strategy_profile"}:
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
            shouldCreateProposal=False,
            fallbackToLegacyRetrieval=False,
            reason="state_pool_sufficient",
        )

    if approved_count == 0 and candidate_count > 0 and (has_structured_evidence or has_raw_evidence):
        return AnswerPolicyRecord(
            canAnswer=True,
            answerLevel="candidate",
            mustDiscloseCandidateBoundary=True,
            mustUseRawEvidence=False,
            shouldCreateProposal=False,
            fallbackToLegacyRetrieval=False,
            reason="candidate_judgment_with_evidence",
        )

    if has_structured_evidence or has_raw_evidence:
        return AnswerPolicyRecord(
            canAnswer=True,
            answerLevel="evidence_based",
            mustDiscloseCandidateBoundary=False,
            mustUseRawEvidence=has_raw_evidence,
            shouldCreateProposal=False,
            fallbackToLegacyRetrieval=True,
            reason="state_pool_insufficient_fallback_to_evidence",
        )

    return AnswerPolicyRecord(
        canAnswer=False,
        answerLevel="insufficient",
        mustDiscloseCandidateBoundary=False,
        mustUseRawEvidence=False,
        shouldCreateProposal=True,
        fallbackToLegacyRetrieval=True,
        reason="insufficient_state_and_evidence",
    )


def _strip_internal_markers(value: str) -> str:
    text = str(value or "")
    for marker in _CHAT_PROCESS_LEAK_MARKERS:
        text = re.sub(re.escape(marker), "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _collect_user_lines(context_pack: PageContextPackRecord) -> list[str]:
    lines: list[str] = []

    if context_pack.officialJudgments:
        lines.append("正式判断：")
        for index, item in enumerate(context_pack.officialJudgments[:4], start=1):
            summary = _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
            if summary:
                lines.append(f"{index}. {summary}")

    if context_pack.candidateJudgments:
        lines.append("候选判断（待审批）：")
        for index, item in enumerate(context_pack.candidateJudgments[:4], start=1):
            summary = _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
            if summary:
                lines.append(f"{index}. {summary}")

    if context_pack.evidenceCards:
        lines.append("支撑证据：")
        for index, item in enumerate(context_pack.evidenceCards[:4], start=1):
            claim = _strip_internal_markers(str(item.get("normalized_claim") or item.get("source_ref") or ""))
            if claim:
                lines.append(f"{index}. {claim}")

    if context_pack.rawEvidence:
        lines.append("原文片段：")
        for index, item in enumerate(context_pack.rawEvidence[:4], start=1):
            excerpt = _strip_internal_markers(str(item.get("excerpt") or ""))
            title = _strip_internal_markers(str(item.get("title") or "相关资料"))
            if excerpt:
                lines.append(f"{index}. {title}：{excerpt}")

    if context_pack.relatedTasks:
        lines.append("相关任务：")
        for index, item in enumerate(context_pack.relatedTasks[:4], start=1):
            title = _strip_internal_markers(str(item.get("title") or ""))
            status = _strip_internal_markers(str(item.get("status") or ""))
            if title:
                lines.append(f"{index}. {title}{f'（{status}）' if status else ''}")

    if context_pack.openQuestions:
        lines.append("未决问题：")
        for index, item in enumerate(context_pack.openQuestions[:4], start=1):
            text = _strip_internal_markers(str(item.get("question") or item.get("summary") or ""))
            if text:
                lines.append(f"{index}. {text}")

    if context_pack.conflicts:
        lines.append("当前风险/冲突：")
        for index, item in enumerate(context_pack.conflicts[:4], start=1):
            text = _strip_internal_markers(str(item.get("summary") or item.get("title") or ""))
            if text:
                lines.append(f"{index}. {text}")

    if context_pack.boundaryNotes:
        lines.append("边界说明：")
        for index, item in enumerate(context_pack.boundaryNotes[:4], start=1):
            text = _strip_internal_markers(item)
            if text:
                lines.append(f"{index}. {text}")

    return lines


def build_answer_material(context_pack: PageContextPackRecord) -> str:
    lines = _collect_user_lines(context_pack)
    if not lines:
        return "当前可直接引用的判断与证据不足。"
    return "\n".join(lines).strip()


def build_fallback_user_answer(
    context_pack: PageContextPackRecord,
    *,
    prompt: str = "",
    error_detail: str | None = None,
) -> str:
    policy = context_pack.answerPolicy or decide_answer_policy(context_pack)

    known_lines: list[str] = []
    unknown_lines: list[str] = []
    action_lines: list[str] = []

    if context_pack.officialJudgments:
        known_lines.extend(
            [
                _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
                for item in context_pack.officialJudgments[:3]
                if _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
            ]
        )

    if policy.answerLevel == "candidate" or policy.mustDiscloseCandidateBoundary:
        if not known_lines:
            known_lines.extend(
                [
                    _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
                    for item in context_pack.candidateJudgments[:3]
                    if _strip_internal_markers(str(item.get("summary") or item.get("topic") or ""))
                ]
            )
        unknown_lines.append("当前还没有已批准的正式判断。以下结论属于候选判断，需后续审批确认。")

    if not known_lines and context_pack.rawEvidence:
        known_lines.extend(
            [
                _strip_internal_markers(str(item.get("excerpt") or ""))
                for item in context_pack.rawEvidence[:2]
                if _strip_internal_markers(str(item.get("excerpt") or ""))
            ]
        )

    if context_pack.missingContext:
        unknown_lines.extend([_strip_internal_markers(item) for item in context_pack.missingContext[:4]])

    if context_pack.relatedTasks:
        first_task = context_pack.relatedTasks[0]
        title = _strip_internal_markers(str(first_task.get("title") or ""))
        if title:
            action_lines.append(f"先推进“{title}”，并同步负责人与截止时间。")

    if context_pack.openQuestions:
        first_open = _strip_internal_markers(
            str(context_pack.openQuestions[0].get("question") or context_pack.openQuestions[0].get("summary") or "")
        )
        if first_open:
            action_lines.append(f"优先补齐未决问题：{first_open}")

    if not action_lines:
        if policy.shouldCreateProposal:
            action_lines.append("建议创建一条 proposal，用于补充关键证据和审批路径。")
        else:
            action_lines.append("建议补充一份可引用资料或会议纪要，再继续推进。")

    response_lines: list[str] = []
    if error_detail:
        response_lines.append("本轮模型生成未完成，已切换到稳态回退回答。")

    response_lines.append("已知信息：")
    response_lines.extend([f"- {item}" for item in known_lines[:4]] or ["- 当前可确认信息较少。"])

    response_lines.append("\n仍待确认：")
    response_lines.extend([f"- {item}" for item in unknown_lines[:4]] or ["- 暂无明显缺口。"])

    response_lines.append("\n建议下一步：")
    response_lines.extend([f"- {item}" for item in action_lines[:3]])

    final_text = "\n".join(response_lines).strip()
    return _strip_internal_markers(final_text)
