"""v2.2 N2 · GET /api/v1/clients/{client_id}/full-narrative

外壳 by B (任务 1 接力指令 2026-05-22).
内核 by A (backend/app/services/narrative_kernel.py · NarrativeKernel).

服务: 顾源源 5/22 关键洞察
    "AI 把碎片拼成完整故事网, 从任意入口看到全局, 才是 N2 真目标。"

→ 前端 3 个入口 (客户档案 / 战略陪伴 / 任务详情) 调本 endpoint
→ 拿到同一个 ClientNarrative (8 段, 引用 atomic_facts/v2_documents)
→ "任意入口看全局" 全栈对齐

B 层职责 (不进 NarrativeKernel):
    1. Idempotency-Key (F2.8 复用) — AI agent 自动调用时防重复生成
    2. 5 维 acceptance 校验 (story_sections 字段齐全性)
    3. actor 鉴权 / 日志 / 错误转 HTTP code
    4. response 序列化 (dataclass → pydantic)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_app_state
from app.services.narrative_kernel import (
    SECTION_KEYS,
    ClientNarrative,
    StorySection,
    get_narrative_kernel,
)

router = APIRouter(prefix="/api/v1", tags=["v2.2-full-narrative"])

_METHOD = "GET"
_PATH = "/api/v1/clients/{client_id}/full-narrative"


# ── Response model (pydantic) ─────────────────────────────────


class StorySectionResponse(BaseModel):
    """1 段故事 — 跟 NarrativeKernel.StorySection 1:1 字段对齐."""
    section_key: str
    title: str
    body_markdown: str
    cited_fact_ids: list[str] = Field(default_factory=list)
    cited_doc_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    source_count_by_tier: dict[str, int] = Field(default_factory=dict)


class FullNarrativeResponse(BaseModel):
    """完整故事全景. 任意入口 (StrategicClarification / StrategicBrain / TaskDetail) 拿到的 shape 一致."""
    client_id: str
    client_name: str
    story_sections: list[StorySectionResponse]
    generated_at: str
    generation_session_id: str
    total_facts_consulted: int = 0
    facts_excluded_by_tier: int = 0
    reasoning_trace_id: str | None = None
    # B 层加: acceptance meta
    acceptance_status: str = "passed"  # "passed" | "warning"
    acceptance_notes: list[str] = Field(default_factory=list)


# ── 5 维 acceptance 校验 (B 层) ─────────────────────────────────


class AcceptanceResult:
    """5 维校验结果 — endpoint 不抛 422 时也会附在 response.acceptance_notes 里."""

    def __init__(self) -> None:
        self.errors: list[str] = []    # 抛 422
        self.warnings: list[str] = []  # 进 response notes


def run_acceptance(narrative: ClientNarrative) -> AcceptanceResult:
    """B 的 5 维 acceptance.

    必过 (errors → 422):
        1. story_sections 长度 = 8
        2. section_key 全部在 SECTION_KEYS 且无重复
        3. 每段 title / body_markdown 非空
        4. confidence ∈ [0, 1]
        5. client_id / generation_session_id 非空

    软约束 (warnings → response.acceptance_notes):
        6. citations 覆盖 < 4/8 段 (数据稀疏预警)
        7. total_facts_consulted == 0 (该客户没事实, 提示先跑 F2.1 抽取)
    """
    r = AcceptanceResult()
    sections = narrative.story_sections

    # 1
    if len(sections) != len(SECTION_KEYS):
        r.errors.append(
            f"story_sections count {len(sections)} != expected {len(SECTION_KEYS)}"
        )
        return r

    # 2
    seen: set[str] = set()
    valid = set(SECTION_KEYS)
    for i, s in enumerate(sections):
        if s.section_key not in valid:
            r.errors.append(f"section[{i}].section_key '{s.section_key}' invalid")
        if s.section_key in seen:
            r.errors.append(f"section[{i}].section_key '{s.section_key}' duplicated")
        seen.add(s.section_key)
        # 3
        if not s.title:
            r.errors.append(f"section[{i}].title empty")
        if not s.body_markdown:
            r.errors.append(f"section[{i}].body_markdown empty")
        # 4
        if not (0.0 <= s.confidence <= 1.0):
            r.errors.append(f"section[{i}].confidence={s.confidence} out of [0,1]")

    # 5
    if not narrative.client_id:
        r.errors.append("client_id empty")
    if not narrative.generation_session_id:
        r.errors.append("generation_session_id empty")

    # 6
    cited = sum(1 for s in sections if s.cited_fact_ids)
    if cited < 4:
        r.warnings.append(
            f"only {cited}/8 sections have citations — data sparse, "
            f"run F2.1 extraction to densify"
        )

    # 7
    if narrative.total_facts_consulted == 0:
        r.warnings.append(
            "total_facts_consulted=0 — no atomic_facts for this client. "
            "Run scripts/run_f21_upbatch_extraction.py to seed."
        )

    return r


# ── dataclass → pydantic 转换 ──────────────────────────────────


def _section_to_response(s: StorySection) -> StorySectionResponse:
    return StorySectionResponse(
        section_key=s.section_key,
        title=s.title,
        body_markdown=s.body_markdown,
        cited_fact_ids=list(s.cited_fact_ids),
        cited_doc_ids=list(s.cited_doc_ids),
        confidence=s.confidence,
        source_count_by_tier=dict(s.source_count_by_tier or {}),
    )


def _narrative_to_response(
    narrative: ClientNarrative,
    acceptance: AcceptanceResult,
) -> FullNarrativeResponse:
    return FullNarrativeResponse(
        client_id=narrative.client_id,
        client_name=narrative.client_name,
        story_sections=[_section_to_response(s) for s in narrative.story_sections],
        generated_at=narrative.generated_at,
        generation_session_id=narrative.generation_session_id,
        total_facts_consulted=narrative.total_facts_consulted,
        facts_excluded_by_tier=narrative.facts_excluded_by_tier,
        reasoning_trace_id=narrative.reasoning_trace_id,
        acceptance_status="passed" if not acceptance.warnings else "warning",
        acceptance_notes=list(acceptance.warnings),
    )


# ── endpoint ──────────────────────────────────────────────────


@router.get(
    "/clients/{client_id}/full-narrative",
    response_model=FullNarrativeResponse,
)
def get_client_full_narrative(
    client_id: str,
    force_refresh: bool = Query(
        False,
        description="目前 NarrativeKernel v0 是 deterministic, 无缓存; v1 引入 LLM 缓存后此参数生效",
    ),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    actor_type: str = Header("human", alias="X-Actor-Type"),
    actor_id: str = Header("", alias="X-Actor-Id"),
    app_state: Any = Depends(get_app_state),
) -> FullNarrativeResponse:
    """v2.2 N2 · GET 客户完整故事全景 (8 段, 任意入口看全局).

    Idempotency-Key (F2.8 复用):
        AI agent 自动调用本 endpoint 时建议带 Idempotency-Key.
        同 key + 同 (client_id) → 返回缓存 (避免重复 LLM 调用).
        同 key + 不同 client_id → 422 (防攻击).
        无 key → 100% 向后兼容, 每次重新生成.

    NarrativeKernel 调用契约 (A 定义):
        narrative = kernel.generate(client_id, actor_id=actor_id)
        kernel v0: deterministic, 不调 LLM, 立即返回 (~50-200ms)
        kernel v1 (TODO A): LLM 编排, 慢 (~30-90s), 建议加缓存

    Acceptance (B 加):
        5 维必过 → 不过抛 422
        2 软约束 → 警告进 response.acceptance_notes
    """
    # ── F2.8 Idempotency-Key 检查 ─────────────────────
    _idemp = None
    if idempotency_key:
        from app.services.idempotency_store import (
            IdempotencyKeyMismatchError,
            get_idempotency_store,
        )
        _idemp = get_idempotency_store(app_state.db)
        _payload = {"client_id": client_id, "force_refresh": force_refresh}
        try:
            cached = _idemp.find(
                idempotency_key, _METHOD, _PATH,
                payload=_payload,
            )
        except IdempotencyKeyMismatchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if cached and cached.status == "completed":
            return FullNarrativeResponse.model_validate_json(cached.response_body)
        if cached and cached.status == "in_progress":
            raise HTTPException(
                status_code=409,
                detail="Narrative generation in progress, retry after a brief wait",
            )
        _idemp.start(
            idempotency_key, _METHOD, _PATH,
            payload=_payload,
            actor_type=actor_type, actor_id=actor_id,
        )

    # ── 调 NarrativeKernel ────────────────────────────
    kernel = get_narrative_kernel(app_state.db, getattr(app_state, "ai", None))
    try:
        narrative = kernel.generate(client_id, actor_id=actor_id or "user")
    except ValueError as exc:
        # NarrativeKernel raises ValueError("client not found: ...")
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ── B 的 5 维 acceptance ─────────────────────────
    acceptance = run_acceptance(narrative)
    if acceptance.errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "narrative_acceptance_failed",
                "errors": acceptance.errors,
            },
        )

    # ── 序列化 ─────────────────────────────────────
    response = _narrative_to_response(narrative, acceptance)

    # ── 缓存到 idempotency store ─────────────────────
    if _idemp and idempotency_key:
        _idemp.complete(
            idempotency_key, _METHOD, _PATH,
            status=200,
            response_body=response.model_dump(mode="json"),
        )

    return response
