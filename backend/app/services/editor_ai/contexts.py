"""Editor AI Context Retriever Registry.

每种 context source（资料源）对应一个 retriever 函数：传 client_id + 用户 query/参数，
返回 ContextChunk 列表（可能空）。P13a 只暴露空实现 + 类型，P13b 接入真召回。

设计原则：
- 每个 retriever 自带 token budget，绝不超过 max_tokens。
- 强制 client_id 隔离：retriever 必须以 client_id 限定查询，禁止跨 client 召回。
- 输出统一为 ContextChunk：text 是要塞进 prompt 的内容，sourceRef 是给前端的引证元信息。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 类型定义
# ──────────────────────────────────────────────────────────────────

ContextSourceType = Literal[
    "selection_only",
    "current_doc",
    "client_materials",
    "strategy_dimension",
    "event_timeline",
]


class ContextSourceSpec(BaseModel):
    """前端传给后端的 context source 规格。

    type: 资料源类型。
    query: 给 retriever 的查询关键词（可选，多数 retriever 用它过滤）。
    refId: 用户在 UI 里指定的具体资料 ID（如 strategy dimension id）。
    topK: 召回数量上限。
    params: 其他参数（如 event_timeline 的日期范围）。
    """
    type: ContextSourceType
    query: str = ""
    refId: str | None = None
    topK: int = Field(default=5, ge=1, le=20)
    params: dict[str, Any] = Field(default_factory=dict)


class SourceRef(BaseModel):
    """单个被召回资料的引证元信息，返给前端展示。"""
    type: str  # 与 ContextSourceType 同
    title: str
    snippet: str = ""
    refId: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ContextChunk:
    """单个资料块（要塞进 prompt 的内容 + 给前端的元信息）。"""
    text: str  # 进 prompt 的文本，包含必要的简短头部
    source_ref: SourceRef  # 给前端显示用
    estimated_tokens: int = 0


@dataclass(frozen=True)
class RetrievedContext:
    """单个 context source spec 召回后的产物。"""
    type: str
    label: str  # 给 prompt 用的中文 label，例如「客户资料」「战略锚点」
    chunks: tuple[ContextChunk, ...] = field(default_factory=tuple)


# ──────────────────────────────────────────────────────────────────
# Retriever Registry
# ──────────────────────────────────────────────────────────────────

# Retriever 签名：fn(spec, *, client_id, db, token_budget) -> RetrievedContext
# db 类型故意用 Any，避免在这层强依赖 Database 实现
RetrieverFn = Callable[..., "RetrievedContext"]


def _retrieve_selection_only(
    spec: ContextSourceSpec,
    *,
    client_id: str,
    db: Any,
    token_budget: int,
) -> RetrievedContext:
    """selection_only：不实际召回任何外部资料，标记一下而已。

    用户的选区文本本身是直接通过 payload 传过来的，不通过 retriever。
    """
    return RetrievedContext(type=spec.type, label="选区")


def _retrieve_current_doc(
    spec: ContextSourceSpec,
    *,
    client_id: str,
    db: Any,
    token_budget: int,
) -> RetrievedContext:
    """current_doc：当前文档全文（前端在 payload.fullDocText 里传过来）。

    与 selection_only 一样，文本通过 payload 传，retriever 这里只占位。
    """
    return RetrievedContext(type=spec.type, label="当前文档")


def _retrieve_client_materials(
    spec: ContextSourceSpec,
    *,
    client_id: str,
    db: Any,
    token_budget: int,
) -> RetrievedContext:
    """client_materials：P13a 占位返回空；P13b 接入 data_center_search RAG。"""
    # P13b TODO：from .. import data_center_search; 复用 RAG 召回
    return RetrievedContext(type=spec.type, label="客户资料")


def _retrieve_strategy_dimension(
    spec: ContextSourceSpec,
    *,
    client_id: str,
    db: Any,
    token_budget: int,
) -> RetrievedContext:
    """strategy_dimension：P13a 占位；P13c 接入 strategy_dimensions 表 SELECT。"""
    return RetrievedContext(type=spec.type, label="战略锚点")


def _retrieve_event_timeline(
    spec: ContextSourceSpec,
    *,
    client_id: str,
    db: Any,
    token_budget: int,
) -> RetrievedContext:
    """event_timeline：P13a 占位；P13c 接入 events 表 SELECT。"""
    return RetrievedContext(type=spec.type, label="事件线")


_RETRIEVERS: dict[str, RetrieverFn] = {
    "selection_only": _retrieve_selection_only,
    "current_doc": _retrieve_current_doc,
    "client_materials": _retrieve_client_materials,
    "strategy_dimension": _retrieve_strategy_dimension,
    "event_timeline": _retrieve_event_timeline,
}


def retrieve_contexts(
    specs: list[ContextSourceSpec],
    *,
    client_id: str,
    db: Any,
    total_token_budget: int = 6000,
) -> list[RetrievedContext]:
    """按 specs 依次调对应 retriever，返回 RetrievedContext 列表。

    异常被吞掉只 warn 一下，让 prompt 至少能拼出来；前端能看到 sources 长度为 0。
    """
    if not specs:
        return []

    # 简单均分 token；后续如果有偏好可在 spec.params 里指定权重
    per_source = max(500, total_token_budget // max(1, len(specs)))

    results: list[RetrievedContext] = []
    for spec in specs:
        fn = _RETRIEVERS.get(spec.type)
        if fn is None:
            logger.warning("[editor_ai.contexts] unknown context type: %s", spec.type)
            continue
        try:
            ctx = fn(spec, client_id=client_id, db=db, token_budget=per_source)
            results.append(ctx)
        except Exception as exc:
            logger.warning(
                "[editor_ai.contexts] retriever %s failed for client=%s: %s",
                spec.type, client_id, exc,
            )
    return results
