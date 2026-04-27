# backend/app/services/query_router.py

```python
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.db import Database
from app.models import PageContextPackRecord, RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services.ai import DOUBAO_BASE_URL

_OFFICIAL_TOKENS = ("系统里", "系统内", "已批准", "正式判断", "官方判断")
_INTRO_TOKENS = ("介绍", "简介", "背景", "是什么", "做什么")
_EVIDENCE_TOKENS = ("证据", "出处", "依据", "原文", "引用")
_MEETING_TOKENS = ("会议", "纪要", "会后")
_TASK_TOKENS = ("任务", "下一步", "怎么做")
_STATUS_TOKENS = ("推进到哪", "当前状态", "风险", "卡点", "本周重点")
_IDENTITY_TOKENS = ("创始人", "负责人", "谁负责", "角色")
_MULTI_OBJECT_TOKENS = ("客户", "任务", "会议", "下一步", "风险", "判断", "推进")


def _normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", "", str(prompt or "")).lower()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _rule_route_decision(
    *,
    prompt: str,
    intent: str,
    page_context: PageContextPackRecord | None,
) -> RouteDecisionRecord:
    normalized = _normalize_prompt(prompt)
    context_quality = page_context.quality.contextQuality if page_context else "none"

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

    if intent in {"intro_profile", "project_intro"} or _contains_any(normalized, _INTRO_TOKENS):
        return RouteDecisionRecord(
            intent="intro_profile" if intent == "general" else intent,
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

    if intent == "task_next_action" or _contains_any(normalized, _TASK_TOKENS):
        return RouteDecisionRecord(
            intent="task_next_action" if intent == "general" else intent,
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


def _invoke_doubao_router_model(
    *,
    ai_service: Any,
    model: str,
    prompt: str,
    base_decision: RouteDecisionRecord,
) -> RouteDecisionRecord | None:
    try:
        store = ai_service._store_for("doubao")  # type: ignore[attr-defined]
        api_key = str(store.get_api_key() or "").strip() if store else ""
    except Exception:
        api_key = ""
    if not api_key or not model:
        return None

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
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": router_instruction},
            {"role": "user", "content": router_prompt},
        ],
        "temperature": 0.0,
        "top_p": 0.5,
        "max_tokens": 600,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.post(
                f"{DOUBAO_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        message = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _safe_json_load(str(message))
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
    base_decision = _rule_route_decision(prompt=prompt, intent=inferred_intent, page_context=page_context)

    # 强保护规则不可被覆盖。
    protected_intents = {"official_judgment_registry", "intro_profile", "project_intro", "evidence_question", "meeting_summary", "task_next_action"}
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
    if not effective_settings.routerEnabled or effective_settings.routerProvider != "doubao":
        return base_decision
    if not _should_call_smart_router(prompt=prompt, intent=inferred_intent, context_quality=context_quality):
        return base_decision
    if ai_service is None:
        return base_decision

    candidate = _invoke_doubao_router_model(
        ai_service=ai_service,
        model=(effective_settings.routerModel or "").strip(),
        prompt=prompt,
        base_decision=base_decision,
    )
    if candidate is None:
        return base_decision.model_copy(
            update={
                "routerSource": "fallback",
                "fallbackUsed": True,
                "routeReason": "smart_router_failed_fallback_to_rules",
            }
        )
    return candidate
```
