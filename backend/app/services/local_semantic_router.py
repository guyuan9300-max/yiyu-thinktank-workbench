from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services.embedding_provider import EmbeddingProvider, EmbeddingProviderMeta


@dataclass
class _CatalogEntry:
    id: str
    utterances: list[str]
    intent: str
    routeMode: str
    dataSources: list[str]
    retrievalMode: str = "hybrid"
    shouldUseRawEvidence: bool = True
    shouldUseStatePool: bool = True
    rerankNeeded: bool = True
    queryPlan: list[str] | None = None


# P2.13 FREEZE(restrictive-local-semantic-catalog): 本地语义路由目录里的示例问法
# 会把 general prompt 拉向 business/strategy/intro/status/task 等意图。先冻结，不在运行中继续扩词。
ROUTE_CATALOG: list[_CatalogEntry] = [
    _CatalogEntry(
        id="business_profile",
        utterances=[
            "核心业务是什么",
            "主营业务是什么",
            "主要服务对象是谁",
            "这家机构主要做什么",
            "有哪些核心产品或服务",
        ],
        intent="business_profile",
        routeMode="raw_doc_drilldown",
        dataSources=["raw_docs", "document_cards", "state_pool"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        shouldUseStatePool=True,
        rerankNeeded=True,
        queryPlan=["客户核心业务和服务对象", "客户产品服务或项目结构", "客户当前业务重点和战略方向"],
    ),
    _CatalogEntry(
        id="strategy_profile",
        utterances=[
            "最新战略是什么",
            "战略方向是什么",
            "未来发展重点是什么",
            "2026 年战略重点是什么",
            "当前战略规划是什么",
        ],
        intent="strategy_profile",
        routeMode="hybrid",
        dataSources=["state_pool", "raw_docs", "meetings"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        shouldUseStatePool=True,
        rerankNeeded=True,
        queryPlan=["最新战略方向", "战略重点和行动计划", "会议或材料中的时间边界"],
    ),
    _CatalogEntry(
        id="intro_profile",
        utterances=["请介绍一下这个客户", "这个机构是什么", "客户背景是什么", "这家机构是谁"],
        intent="intro_profile",
        routeMode="raw_doc_drilldown",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="raw_only",
        shouldUseRawEvidence=True,
        shouldUseStatePool=False,
        rerankNeeded=True,
        queryPlan=["机构介绍", "业务与项目背景", "当前合作关注点"],
    ),
    _CatalogEntry(
        id="official_judgment_registry",
        utterances=["系统里有哪些正式判断", "已批准判断有哪些", "当前官方结论是什么"],
        intent="official_judgment_registry",
        routeMode="registry_only",
        dataSources=["judgment_registry"],
        retrievalMode="state_only",
        shouldUseRawEvidence=False,
        shouldUseStatePool=True,
        rerankNeeded=False,
        queryPlan=["已批准判断列表"],
    ),
    _CatalogEntry(
        id="status_progress",
        utterances=["现在推进到哪了", "当前状态是什么", "有什么风险和卡点", "本周重点是什么"],
        intent="status_progress",
        routeMode="state_first",
        dataSources=["state_pool", "tasks", "meetings"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=False,
        shouldUseStatePool=True,
        rerankNeeded=False,
        queryPlan=["当前推进状态", "风险与卡点", "本周优先动作"],
    ),
    _CatalogEntry(
        id="task_next_action",
        utterances=["这条任务下一步怎么做", "这条任务为什么重要", "任务缺什么背景", "任务现在卡在哪里"],
        intent="task_next_action",
        routeMode="task_context",
        dataSources=["task", "client", "event_line", "raw_docs"],
        retrievalMode="hybrid",
        shouldUseRawEvidence=True,
        shouldUseStatePool=True,
        rerankNeeded=True,
        queryPlan=["任务当前状态", "任务阻塞与缺口", "任务下一步与责任人"],
    ),
]


# P2.13 FREEZE(restrictive-local-semantic-protected-intents): 这组受保护意图决定
# 本地语义路由是否还能覆盖基础规则路由。先冻结，避免绕开主限制链。
_PROTECTED_INTENTS = {
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

_EMBED_CACHE: dict[str, tuple[list[list[float]], EmbeddingProviderMeta]] = {}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    if size <= 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for idx in range(size):
        va = float(a[idx])
        vb = float(b[idx])
        dot += va * vb
        na += va * va
        nb += vb * vb
    if na <= 1e-9 or nb <= 1e-9:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _catalog_utterances() -> list[str]:
    values: list[str] = []
    for item in ROUTE_CATALOG:
        values.extend(item.utterances)
    return values


def _entry_for_index(index: int) -> _CatalogEntry:
    cursor = 0
    for item in ROUTE_CATALOG:
        next_cursor = cursor + len(item.utterances)
        if cursor <= index < next_cursor:
            return item
        cursor = next_cursor
    return ROUTE_CATALOG[0]


def route_by_local_semantic(
    *,
    prompt: str,
    base_decision: RouteDecisionRecord,
    settings: RetrievalModelSettingsRecord,
    embedding_provider: EmbeddingProvider,
) -> RouteDecisionRecord:
    if not str(prompt or "").strip():
        return base_decision
    # P2.13 FREEZE(restrictive-local-semantic-precedence): 当前本地语义路由先看
    # base_decision 是否已落入 protected intents；一旦命中就不再覆盖。先冻结。
    if base_decision.intent in _PROTECTED_INTENTS:
        return base_decision

    threshold = float(settings.routerConfidenceThreshold or 0.72)
    threshold = max(0.0, min(1.0, threshold))

    utterances = _catalog_utterances()
    cache_key = f"{getattr(settings, 'embeddingProfile', 'legacy_fastembed_256')}::{len(utterances)}"
    cached = _EMBED_CACHE.get(cache_key)
    if cached is None:
        vectors, meta = embedding_provider.embed_texts(utterances)
        _EMBED_CACHE[cache_key] = (vectors, meta)
    else:
        vectors, meta = cached

    prompt_vectors, _ = embedding_provider.embed_texts([prompt])
    if not prompt_vectors:
        return base_decision
    prompt_vector = prompt_vectors[0]

    best_index = -1
    best_score = -1.0
    for idx, candidate in enumerate(vectors):
        score = _cosine(prompt_vector, candidate)
        if score > best_score:
            best_score = score
            best_index = idx

    if best_index < 0 or best_score < threshold:
        return base_decision

    entry = _entry_for_index(best_index)
    if entry.intent in _PROTECTED_INTENTS and base_decision.intent in _PROTECTED_INTENTS:
        return base_decision

    retrieval_mode = entry.retrievalMode
    return base_decision.model_copy(
        update={
            "intent": entry.intent,
            "routeMode": entry.routeMode,
            "dataSources": entry.dataSources,
            "retrievalMode": retrieval_mode,
            "shouldUseRawEvidence": bool(entry.shouldUseRawEvidence),
            "shouldUseStatePool": bool(entry.shouldUseStatePool),
            "shouldUseTaskContext": entry.routeMode == "task_context",
            "shouldUseMeetingContext": "meetings" in entry.dataSources,
            "queryPlan": list(entry.queryPlan or []),
            "rerankNeeded": bool(entry.rerankNeeded),
            "routerSource": "local_semantic",
            "fallbackUsed": False,
            "confidence": round(float(best_score), 4),
            "routeReason": f"local_semantic_match:{entry.id}",
            "embeddingProfile": getattr(settings, "embeddingProfile", "legacy_fastembed_256") or "legacy_fastembed_256",
            "evidenceSupportMode": "raw_doc_drilldown" if bool(entry.shouldUseRawEvidence) else base_decision.evidenceSupportMode,
        }
    )
