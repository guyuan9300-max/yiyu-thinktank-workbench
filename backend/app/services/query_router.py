from __future__ import annotations

import json
import re
from typing import Any

from app.db import Database
from app.models import PageContextPackRecord, RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services.embedding_provider import build_embedding_provider
from app.services.local_semantic_router import route_by_local_semantic

# P2.13 FREEZE(restrictive-route-keywords): route decision 阶段的整组关键词和它们的组合规则
# 会直接决定 routeMode / retrievalMode / shouldUseRawEvidence / shouldUseMeetingContext 等。
# 先整体冻结，不再局部微调触发词。
_OFFICIAL_TOKENS = ("系统里", "系统内", "已批准", "正式判断", "官方判断")
_INTRO_TOKENS = ("介绍", "简介", "背景", "机构", "是谁", "做什么")
_BUSINESS_TOKENS = ("核心业务", "主营业务", "业务是什么", "业务模式", "主要服务", "服务对象", "核心产品", "产品服务")
_STRATEGY_TOKENS = ("最新战略", "战略是什么", "战略方向", "未来战略", "发展战略", "战略重点", "战略规划")
# P2.13 FREEZE(restrictive-route-decision): 这组 evidence 词在 route decision 阶段优先把问题打到
# `intent=evidence_question + routeMode=raw_doc_drilldown`。当前它会覆盖介绍类问题的长画像路径。
# 先冻结，避免运行中继续漂移。
_EVIDENCE_TOKENS = ("证据", "出处", "依据", "原文", "引用")
_MEETING_TOKENS = ("会议", "纪要", "会后")
_TASK_CONTEXT_EXPLICIT_TOKENS = ("这条任务", "当前任务", "任务本身", "任务背景", "任务上下文")
_TASK_NEXT_EXPLICIT_TOKENS = ("任务下一步", "这条任务下一步", "当前任务下一步")
_STATUS_TOKENS = ("推进到哪", "当前状态", "风险", "卡点", "本周重点")
_IDENTITY_TOKENS = ("创始人", "负责人", "谁负责", "角色")
_MULTI_OBJECT_TOKENS = ("客户", "任务", "会议", "下一步", "风险", "判断", "推进")


def _normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", "", str(prompt or "")).lower()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _looks_task_specific_query(normalized: str, page_context: PageContextPackRecord | None) -> bool:
    if _contains_any(normalized, _TASK_CONTEXT_EXPLICIT_TOKENS + _TASK_NEXT_EXPLICIT_TOKENS):
        return True
    page = str(page_context.page if page_context else "")
    if page in {"task_detail", "task_ai"} and any(token in normalized for token in ("下一步", "怎么做", "阻塞", "卡点")):
        return True
    return False


def _rule_route_decision(
    *,
    prompt: str,
    intent: str,
    page_context: PageContextPackRecord | None,
) -> RouteDecisionRecord:
    normalized = _normalize_prompt(prompt)
    context_quality = page_context.quality.contextQuality if page_context else "none"

    # P2.13 FREEZE(restrictive-route-precedence): 当前 route decision 的先后顺序
    # official -> business -> strategy -> intro/project -> evidence -> meeting -> task -> identity -> status -> default
    # 会直接决定“介绍类问题”是被保留还是被 meeting/evidence/status 覆盖。先冻结。
    if intent == "official_judgment_registry" or _contains_any(normalized, _OFFICIAL_TOKENS):
        return RouteDecisionRecord(
            intent="official_judgment_registry",
            routeMode="registry_only",
            dataSources=["state_pool", "judgment_registry"],
            retrievalMode="state_only",
            judgmentQueryMode="registry_only",
            evidenceSupportMode="none",
            shouldUseRawEvidence=False,
            shouldUseStatePool=True,
            rerankNeeded=False,
            routeReason="official_registry_guard_rule",
            routerSource="rules",
        )

    if intent == "business_profile" or _contains_any(normalized, _BUSINESS_TOKENS):
        return RouteDecisionRecord(
            intent="business_profile",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs", "document_cards", "state_pool"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=True,
            rerankNeeded=True,
            queryPlan=["客户核心业务和服务对象", "客户产品服务或项目结构", "客户当前业务重点和战略方向"],
            routeReason="business_profile_rule",
            routerSource="rules",
        )

    if intent == "strategy_profile" or _contains_any(normalized, _STRATEGY_TOKENS):
        return RouteDecisionRecord(
            intent="strategy_profile",
            routeMode="hybrid",
            dataSources=["state_pool", "raw_docs", "meetings", "document_cards"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=True,
            shouldUseMeetingContext=True,
            rerankNeeded=True,
            queryPlan=["最新战略方向", "战略重点和行动计划", "会议或材料中的时间边界"],
            routeReason="strategy_profile_rule",
            routerSource="rules",
        )

    if intent in {"intro_profile", "project_intro"} or _contains_any(normalized, _INTRO_TOKENS):
        resolved_intro_intent = "project_intro" if intent == "project_intro" else "intro_profile"
        return RouteDecisionRecord(
            intent=resolved_intro_intent,
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs", "document_cards"],
            retrievalMode="raw_only",
            judgmentQueryMode=None,
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=False,
            rerankNeeded=True,
            routeReason="intro_profile_requires_raw_evidence",
            routerSource="rules",
        )

    if intent == "evidence_question" or _contains_any(normalized, _EVIDENCE_TOKENS):
        return RouteDecisionRecord(
            intent="evidence_question",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs", "document_cards"],
            retrievalMode="raw_only",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=False,
            rerankNeeded=True,
            routeReason="evidence_query_requires_citations",
            routerSource="rules",
        )

    if intent == "meeting_summary" or _contains_any(normalized, _MEETING_TOKENS):
        return RouteDecisionRecord(
            intent="meeting_summary",
            routeMode="meeting_evidence",
            dataSources=["meetings", "raw_docs", "state_pool"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseMeetingContext=True,
            shouldUseStatePool=True,
            queryPlan=["最新会议纪要结论", "会议行动项与负责人", "会议风险与未决问题"],
            rerankNeeded=True,
            routeReason="meeting_summary_rule",
            routerSource="rules",
        )

    if intent == "task_next_action" or _looks_task_specific_query(normalized, page_context):
        return RouteDecisionRecord(
            intent="task_next_action" if intent in {"general", "next_actions", "status_progress"} else intent,
            routeMode="task_context",
            dataSources=["tasks", "state_pool", "raw_docs"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseTaskContext=True,
            shouldUseStatePool=True,
            shouldUseRawEvidence=True,
            queryPlan=["任务当前状态与阻塞", "相关客户主线判断", "任务下一步动作与责任人"],
            rerankNeeded=True,
            routeReason="task_context_rule",
            routerSource="rules",
        )

    if _contains_any(normalized, _IDENTITY_TOKENS):
        return RouteDecisionRecord(
            intent="evidence_question",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs", "state_pool"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=True,
            rerankNeeded=True,
            routeReason="identity_evidence_guard_rule",
            routerSource="rules",
        )

    if intent in {"status_progress", "next_actions"} or _contains_any(normalized, _STATUS_TOKENS):
        retrieval_mode = "state_only" if context_quality in {"strong", "usable"} else "hybrid"
        return RouteDecisionRecord(
            intent="status_progress" if intent == "general" else intent,
            routeMode="state_first",
            dataSources=["state_pool", "tasks", "open_questions", "conflicts"],
            retrievalMode=retrieval_mode,
            evidenceSupportMode="none" if retrieval_mode == "state_only" else "raw_doc_drilldown",
            shouldUseRawEvidence=retrieval_mode != "state_only",
            shouldUseStatePool=True,
            shouldUseTaskContext=True,
            rerankNeeded=retrieval_mode != "state_only",
            routeReason="status_progress_rule",
            routerSource="rules",
        )

    return RouteDecisionRecord(
        intent=intent if intent else "general",
        routeMode="state_first",
        dataSources=["state_pool"],
        retrievalMode="state_only" if context_quality in {"strong", "usable"} else "hybrid",
        evidenceSupportMode="none" if context_quality in {"strong", "usable"} else "raw_doc_drilldown",
        shouldUseRawEvidence=context_quality in {"weak", "none"},
        shouldUseStatePool=True,
        rerankNeeded=context_quality in {"weak", "none"},
        routeReason="default_general_rule",
        routerSource="rules",
    )


def _should_call_smart_router(
    *,
    prompt: str,
    intent: str,
    context_quality: str,
) -> bool:
    normalized = _normalize_prompt(prompt)
    long_prompt = len(str(prompt or "")) > 40
    multi_objects = sum(1 for token in _MULTI_OBJECT_TOKENS if token in normalized) >= 3
    strategic_words = any(token in normalized for token in ("怎么判断", "怎么推进", "先做什么", "值不值得"))
    return bool(
        long_prompt
        or multi_objects
        or intent == "general"
        or context_quality in {"weak", "none"}
        or strategic_words
    )


def _safe_json_load(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]+\}", raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _invoke_configured_router_model(
    *,
    ai_service: Any,
    model: str,
    prompt: str,
    base_decision: RouteDecisionRecord,
) -> RouteDecisionRecord | None:
    router_instruction = (
        "你是检索路由器。只输出 JSON，不要解释。"
        "不能输出最终答案，不能声明已批准判断，不能越过审批边界。"
    )
    router_prompt = (
        f"用户问题：{prompt}\n"
        f"基础路由：{json.dumps(base_decision.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        "输出字段必须包含：intent,retrievalMode,dataSources,queryPlan,rerankNeeded,"
        "shouldCreateProposal,confidence,routeReason。"
    )
    try:
        target_model = str(model or "").strip()
        parsed_payload = ai_service._qwen_generate(  # type: ignore[attr-defined]
            prompt=router_prompt,
            system_instruction=router_instruction,
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "intent": {"type": "STRING"},
                    "retrievalMode": {"type": "STRING"},
                    "dataSources": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "queryPlan": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "rerankNeeded": {"type": "BOOLEAN"},
                    "shouldCreateProposal": {"type": "BOOLEAN"},
                    "confidence": {"type": "NUMBER"},
                    "routeReason": {"type": "STRING"},
                },
            },
            timeout_seconds=12.0,
            max_tokens=600,
            temperature=0.0,
            top_p=0.5,
            enable_thinking=False,
            model_override=target_model or None,
            task_kind="fast_structured",
        )
        parsed = parsed_payload if isinstance(parsed_payload, dict) else _safe_json_load(str(parsed_payload))
        if not isinstance(parsed, dict):
            return None
        confidence = float(parsed.get("confidence", 0.0) or 0.0)
        if confidence < 0.35:
            return None
        candidate = base_decision.model_copy(
            update={
                "intent": str(parsed.get("intent") or base_decision.intent),
                "retrievalMode": str(parsed.get("retrievalMode") or base_decision.retrievalMode),
                "dataSources": [str(item) for item in parsed.get("dataSources", []) if str(item).strip()] or base_decision.dataSources,
                "queryPlan": [str(item) for item in parsed.get("queryPlan", []) if str(item).strip()][:3],
                "rerankNeeded": bool(parsed.get("rerankNeeded", base_decision.rerankNeeded)),
                "shouldCreateProposal": bool(parsed.get("shouldCreateProposal", base_decision.shouldCreateProposal)),
                "confidence": confidence,
                "routeReason": str(parsed.get("routeReason") or "smart_router_decision"),
                "routerSource": "smart_router",
                "fallbackUsed": False,
            }
        )
        return candidate
    except Exception:
        return None


def route_page_query(
    db: Database,
    *,
    page: str,
    prompt: str,
    client_id: str | None = None,
    task_id: str | None = None,
    page_context: PageContextPackRecord | None = None,
    settings: RetrievalModelSettingsRecord | None = None,
    ai_service: Any | None = None,
) -> RouteDecisionRecord:
    del db, client_id, task_id
    normalized = _normalize_prompt(prompt)
    inferred_intent = page_context.intent if page_context else "general"
    context_quality = page_context.quality.contextQuality if page_context else "none"

    if page_context is not None and page_context.page == "workspace_chat":
        # P2.14 FREEZE(answer-shaping-workspace-route): workspace/chat 主回答链的 route decision
        # 现在只承担工具分流，不再承担回答塑形。除显式正式判断外，一律保持 `general + raw_docs/document_cards`。
        # 不允许在这里恢复 intro/meeting/status/next_actions 的回答形态锁。
        if inferred_intent == "official_judgment_registry" or _contains_any(normalized, _OFFICIAL_TOKENS):
            return RouteDecisionRecord(
                intent="official_judgment_registry",
                routeMode="registry_only",
                dataSources=["state_pool", "judgment_registry"],
                retrievalMode="state_only",
                judgmentQueryMode="registry_only",
                evidenceSupportMode="none",
                shouldUseRawEvidence=False,
                shouldUseStatePool=True,
                rerankNeeded=False,
                routeReason="workspace_chat_official_registry",
                routerSource="rules",
            )
        return RouteDecisionRecord(
            intent="general",
            routeMode="hybrid",
            dataSources=["raw_docs", "document_cards"],
            retrievalMode="hybrid",
            evidenceSupportMode="raw_doc_drilldown",
            shouldUseRawEvidence=True,
            shouldUseStatePool=False,
            shouldUseMeetingContext=False,
            rerankNeeded=True,
            routeReason="workspace_chat_open_route",
            routerSource="rules",
        )

    base_decision = _rule_route_decision(prompt=prompt, intent=inferred_intent, page_context=page_context)

    # 强保护规则不可被覆盖。
    # P2.13 FREEZE(restrictive-protected-intents): 这组 protected intents 会阻止 smart router 覆盖基础规则。
    # 一旦基础规则把问题打到 meeting/evidence 等意图，这里会把它锁死。先冻结，避免再漂。
    # P2.14 FREEZE(answer-shaping-non-workspace-protected-intents): 这组 protected intents 仍然属于旧回答塑形半层。
    # 当前仅对非 workspace/chat 页面保留；不要再把它们重新接回 workspace/chat 主回答链。
    protected_intents = {
        "official_judgment_registry",
        "intro_profile",
        "project_intro",
        "evidence_question",
        "meeting_summary",
        "task_next_action",
        "task_context",
        "business_profile",
        "strategy_profile",
    }
    if base_decision.intent in protected_intents:
        return base_decision
    if _contains_any(normalized, _OFFICIAL_TOKENS):
        return base_decision.model_copy(
            update={
                "intent": "official_judgment_registry",
                "judgmentQueryMode": "registry_only",
                "retrievalMode": "state_only",
                "shouldUseRawEvidence": False,
                "routeReason": "official_registry_guard_rule",
                "routerSource": "rules",
            }
        )

    effective_settings = settings or RetrievalModelSettingsRecord(updatedAt="")
    if not effective_settings.routerEnabled:
        return base_decision

    candidate_decision = base_decision
    router_mode = effective_settings.routerMode
    if router_mode in {"semantic_shadow", "semantic", "semantic_plus_llm"} or effective_settings.routerProvider == "local_semantic":
        semantic_provider = build_embedding_provider(effective_settings, ai_service=None)
        semantic_decision = route_by_local_semantic(
            prompt=prompt,
            base_decision=base_decision,
            settings=effective_settings,
            embedding_provider=semantic_provider,
        )
        if router_mode == "semantic_shadow":
            candidate_decision = base_decision.model_copy(
                update={
                    "routeReason": (
                        f"{base_decision.routeReason}|semantic_shadow:{semantic_decision.intent}:{round(float(semantic_decision.confidence or 0.0), 3)}"
                        if semantic_decision.intent != base_decision.intent
                        else base_decision.routeReason
                    )
                }
            )
        elif semantic_decision.routerSource == "local_semantic":
            candidate_decision = semantic_decision

    should_try_smart_router = (
        effective_settings.routerProvider == "doubao"
        and router_mode in {"rules", "semantic_plus_llm"}
    )
    if not should_try_smart_router:
        return candidate_decision
    if not _should_call_smart_router(prompt=prompt, intent=inferred_intent, context_quality=context_quality):
        return candidate_decision
    if ai_service is None:
        return candidate_decision

    smart_candidate = _invoke_configured_router_model(
        ai_service=ai_service,
        model=(effective_settings.routerModel or "").strip(),
        prompt=prompt,
        base_decision=candidate_decision,
    )
    if smart_candidate is None:
        return candidate_decision.model_copy(
            update={
                "routerSource": "fallback",
                "fallbackUsed": True,
                "routeReason": "smart_router_failed_fallback_to_rules",
            }
        )
    return smart_candidate
