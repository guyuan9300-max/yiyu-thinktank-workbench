"""战略陪伴 · 统一叙事取材层 (语义检索 + LIKE 兜底).

背景 (见桌面 49-E / docs/E_STRATEGIC_NARRATIVE_M0_BASELINE_REPRO_REPORT.md):
现状 narrative 取材走 SQL `content LIKE '%kw%'` + 每维度只取 2 chunk, 覆盖率 0.1%-0.4%,
完全不用已建好的 Qdrant 语义检索。本服务把取材统一为:

    dimension 语义意图 → knowledge_v2.retrieve_knowledge_bundle (v2 文档级检索, client 隔离)
    → top-K 最相关 chunk + 来源标注 → 不行才 LIKE 兜底

设计约束:
- 不重造向量检索, 复用 knowledge_v2.retrieve_knowledge_bundle。
  (历史 5/28: 原走 knowledge_base 版, 但其 citation grounding 需要 document_chunks;
   而 v2 ingest 经 _sync_legacy_knowledge_document 只建 knowledge_documents 占位,
   不建 document_chunks → 除 B客户 早期 v1 ingest 外, 所有客户 coverage=0、citations=0,
   失败原因 no_grounded_citations。切到 v2 版后走 v2_sections + preview_text 做 excerpt,
   不再依赖 document_chunks; 实测A组织 6 维度 coverage 0.55-0.70、cits 131、B客户 持平 v1。)
- 保留 LIKE fallback (通过回调注入, 避免与 narrative_collector 循环 import)。
- 强制 client_id 隔离 (retrieve_knowledge_bundle 内部 WHERE client_id=?; LIKE 回调同样带 client)。
- 每段 fallback_used / source_breakdown / warnings 可追踪。
- top-K 候选, 实际入 prompt 的裁剪交给上层 token budget (M5)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from app.db import Database

# ---- M2: 6 维度语义意图 query (不是固定关键词, 是"想知道什么") ----
DIMENSION_SEMANTIC_QUERIES: dict[str, str] = {
    "essence": (
        "这家机构是谁，它的核心定位、服务对象、长期关注的议题、"
        "独特价值、行业角色和影响力是什么？"
    ),
    "cooperation": (
        "益语与该客户之间是什么服务关系，合作周期、交付物、服务边界、"
        "关键对齐会议、合作演进过程和当前合作状态是什么？"
    ),
    "business_intro": (
        "该客户有哪些主要项目或业务，各自的服务对象、服务方法、规模、"
        "所处阶段、信息来源和当前进展是什么？"
    ),
    "people": (
        "该客户涉及哪些关键人物，他们分别承担什么角色、负责哪些项目、"
        "在合作中做过哪些关键承诺或决策？"
    ),
    "timeline": (
        "该客户合作或组织发展有哪些关键阶段与重要转折：签约、预算变化、"
        "负责人变化、项目启动、复盘、重大风险，以及当前所处状态？"
    ),
    "next_steps": (
        "基于该客户当前状态、未完成的承诺、待澄清事项、风险信号、"
        "数据缺口和近期任务，下一阶段最应该推进什么？"
    ),
}

# 默认每维度语义候选上限 (实际入 prompt 由上层 token budget 决定, M5)。
DEFAULT_TOP_K = 20
MIN_CHUNKS_PER_DIMENSION = 8
# bundle 覆盖率低于此值时, 追加 LIKE 兜底以补面 (不是替换, 是补充)。
LOW_COVERAGE_THRESHOLD = 0.15


@dataclass(frozen=True)
class RetrievedChunk:
    """统一取材产物。语义 / LIKE 两条路径都映射成它, 带来源标注。"""

    dimension: str
    matched_term: str            # 语义路径=维度/项目名; LIKE 路径=命中词
    doc_title: str
    excerpt: str
    score: float = 0.0
    source_doc_id: str = ""      # knowledge_document_id / v2_document_id
    source_chunk_id: str = ""
    source_path: str = ""
    retrieval_path: str = "semantic"   # 'semantic' | 'like_fallback'
    # confidence_label 为 3.0 / candidate_facts 预留, 默认确认态。
    confidence_label: str = "confirmed"


@dataclass
class DimensionRetrieval:
    """单维度取材结果 + 可追踪元数据 (供 M6 报告 / 调试)。"""

    dimension: str
    semantic_query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    candidate_count: int = 0          # 裁剪前候选总数
    fallback_used: bool = False
    coverage: float = 0.0             # 来自 retrieve_knowledge_bundle.coverage
    source_breakdown: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # M1 回滚开关可观测: semantic | semantic+fallback | fallback_only | legacy_like_only
    retrieval_mode: str = ""
    semantic_enabled: bool = True
    fallback_reason: str = ""


# LIKE 兜底回调签名: (db, client_id, keywords, limit, viewer_user_id) -> [(matched_term, doc_title, excerpt), ...]
LikeFallbackFn = Callable[..., list[tuple[str, str, str]]]


class _BundleLike(Protocol):
    citations: list
    coverage: float
    failure_reason: str | None


def data_dir_for(db: Database) -> Path | None:
    """从 Database 自身推导 data_dir (= app.db 所在目录), 避免改 main.py 传参。"""
    raw = getattr(db, "db_path", None)
    if not raw:
        return None
    try:
        return Path(raw).parent
    except (TypeError, ValueError):
        return None


def semantic_retrieval_enabled() -> bool:
    """M1 回滚开关。STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED=0/false/no/off → 关。
    默认开 (dev/lab); 生产打包可由环境关闭, 关闭后只走 LIKE, 不依赖 Qdrant/embedding。"""
    import os
    v = os.environ.get("STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED", "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _semantic_chunks(
    db: Database,
    data_dir: Path,
    client_id: str,
    dimension: str,
    query: str,
    *,
    top_k: int,
) -> tuple[list[RetrievedChunk], float, str | None]:
    """走 knowledge_v2.retrieve_knowledge_bundle 取语义最相关 chunk(5/28 切;见模块 docstring)。

    返回 (chunks, coverage, failure_reason)。任何异常都降级为空 + 原因, 由上层兜底。
    """
    try:
        # 延迟 import: 避免模块级循环依赖, 也让无 qdrant 环境不在 import 期炸。
        from app.services.knowledge_v2 import retrieve_knowledge_bundle
    except Exception as exc:  # pragma: no cover - 环境缺失
        return [], 0.0, f"import_failed: {exc}"

    try:
        bundle = retrieve_knowledge_bundle(db, data_dir, client_id, query)
    except Exception as exc:
        return [], 0.0, f"retrieve_failed: {exc}"

    citations = list(getattr(bundle, "citations", []) or [])
    coverage = float(getattr(bundle, "coverage", 0.0) or 0.0)
    failure = getattr(bundle, "failure_reason", None)

    out: list[RetrievedChunk] = []
    for c in citations[:top_k]:
        excerpt = str(getattr(c, "excerpt", "") or "").strip()
        if not excerpt:
            continue
        out.append(
            RetrievedChunk(
                dimension=dimension,
                matched_term=dimension,
                doc_title=str(getattr(c, "title", "") or ""),
                excerpt=excerpt,
                score=float(getattr(c, "score", 0.0) or 0.0),
                source_doc_id=str(getattr(c, "knowledge_document_id", "") or ""),
                source_chunk_id=str(getattr(c, "chunk_id", "") or ""),
                source_path=str(getattr(c, "path", "") or ""),
                retrieval_path="semantic",
            )
        )
    return out, coverage, failure


def _like_chunks(
    db: Database,
    client_id: str,
    dimension: str,
    keywords: tuple[str, ...],
    *,
    limit: int,
    viewer_user_id: str,
    like_fallback_fn: LikeFallbackFn | None,
) -> list[RetrievedChunk]:
    """LIKE 兜底: 复用 narrative_collector 的 _retrieve_top_chunks (回调注入)。"""
    if like_fallback_fn is None or not keywords:
        return []
    try:
        rows = like_fallback_fn(
            db, client_id, keywords, limit=limit, viewer_user_id=viewer_user_id
        )
    except Exception:
        return []
    out: list[RetrievedChunk] = []
    for matched_term, doc_title, excerpt in rows:
        text = str(excerpt or "").strip()
        if not text:
            continue
        out.append(
            RetrievedChunk(
                dimension=dimension,
                matched_term=str(matched_term or dimension),
                doc_title=str(doc_title or ""),
                excerpt=text,
                retrieval_path="like_fallback",
            )
        )
    return out


def _dedup(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    out: list[RetrievedChunk] = []
    for c in chunks:
        key = f"{c.doc_title[:30]}::{c.excerpt[:80]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def retrieve_dimension(
    db: Database,
    client_id: str,
    dimension: str,
    *,
    query: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    viewer_user_id: str = "",
    like_keywords: tuple[str, ...] = (),
    like_fallback_fn: LikeFallbackFn | None = None,
    data_dir: Path | None = None,
    semantic_enabled: bool | None = None,
) -> DimensionRetrieval:
    """单维度统一取材: 语义优先, 覆盖率低或失败时 LIKE 补面。

    - query 缺省用 DIMENSION_SEMANTIC_QUERIES[dimension]。
    - like_keywords / like_fallback_fn 来自调用方 (narrative_collector), 用于兜底。
    - data_dir 缺省从 db 推导 (避免改 main.py)。
    - semantic_enabled 缺省读环境开关 (M1 回滚): 关闭则只走 LIKE, 不碰 Qdrant/embedding。
    """
    sem_query = (query or DIMENSION_SEMANTIC_QUERIES.get(dimension) or dimension).strip()
    enabled = semantic_retrieval_enabled() if semantic_enabled is None else semantic_enabled
    result = DimensionRetrieval(dimension=dimension, semantic_query=sem_query)
    result.semantic_enabled = enabled

    dd = data_dir or data_dir_for(db)
    semantic: list[RetrievedChunk] = []
    if not enabled:
        result.fallback_reason = "semantic_disabled_by_flag"
        result.warnings.append("语义检索开关关闭 (回滚态), 只走 LIKE")
    elif dd is None:
        result.fallback_reason = "data_dir_unresolved"
        result.warnings.append("data_dir 推导失败, 跳过语义检索直接 LIKE 兜底")
    else:
        semantic, coverage, failure = _semantic_chunks(
            db, dd, client_id, dimension, sem_query, top_k=top_k
        )
        result.coverage = coverage
        if failure:
            result.fallback_reason = failure
            result.warnings.append(f"语义检索降级: {failure}")

    # 兜底条件: 语义为空 / 覆盖率过低 / data_dir 失败。
    need_fallback = (
        not semantic
        or result.coverage < LOW_COVERAGE_THRESHOLD
        or len(semantic) < MIN_CHUNKS_PER_DIMENSION
    )
    like: list[RetrievedChunk] = []
    if need_fallback:
        like = _like_chunks(
            db, client_id, dimension, like_keywords,
            limit=max(top_k - len(semantic), MIN_CHUNKS_PER_DIMENSION),
            viewer_user_id=viewer_user_id, like_fallback_fn=like_fallback_fn,
        )

    merged = _dedup(semantic + like)
    result.chunks = merged[:top_k]
    result.candidate_count = len(semantic) + len(like)
    result.fallback_used = bool(like)
    sem_n = sum(1 for c in result.chunks if c.retrieval_path == "semantic")
    fb_n = sum(1 for c in result.chunks if c.retrieval_path == "like_fallback")
    result.source_breakdown = {"semantic": sem_n, "like_fallback": fb_n}
    if not enabled:
        result.retrieval_mode = "legacy_like_only"
    elif sem_n and fb_n:
        result.retrieval_mode = "semantic+fallback"
    elif sem_n:
        result.retrieval_mode = "semantic"
    elif fb_n:
        result.retrieval_mode = "fallback_only"
    else:
        result.retrieval_mode = "empty"
    if not result.chunks:
        result.warnings.append("语义 + LIKE 均无召回 (该客户该维度可能无相关资料或未索引)")
    return result
