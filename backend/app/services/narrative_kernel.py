"""[A] v2.2 F3 (Phase 3 提前) · NarrativeKernel — 把碎片 atomic_facts 拼成完整故事网

服务: NORTH_STAR N2 真目标 (顾源源 5/22 关键洞察):
"AI 把碎片拼成完整故事网, 从任意入口看到全局, 才是 N2 真目标。"

设计 (参考 DATA-CENTER-RELATIONSHIP-GRAPH-PLAN.md §5.4 客户关系书 8 段结构):

输入:
- client_id
- 该客户的全部 atomic_facts (5 维元数据完整) — 来自 F2.1 上量
- 该客户的 key_decisions / org_events (来自 F2.2)
- event_lines + state_changes (来自 F2.6)

输出 (8 段故事 ClientNarrative):
1. identity      机构身份 (名/性质/规模/愿景/历史)
2. people        关键人物网 (创始人/核心员工/合作伙伴, 含状态变化)
3. main_lines    业务主线 (心盛/兴盛/安心妈妈 等, 含当前阶段)
4. recent_changes 近期变化 (人员变动/法人变更/合作签订/战略调整)
5. risks         风险信号 (资金/人员/业务/合规)
6. our_collab    我方-客户合作历程 (服务历史/反馈/承诺)
7. open_questions 待澄清空白 (低 confidence + 用户没确认的事实)
8. timeline      时间线 (按 time_anchor 排序的关键事件)

8 段引用规则 (NORTH_STAR §4 R1):
- Tier A (优先引用): client_official_doc / client_internal_doc + user_confirmed
- Tier B: collaboration_task / collaboration_review + user_verbal_fact
- Tier C (背景仅引): internet_official, internet_media
- 排除: internet_ugc / internet_ai_inferred / contradicted

每段返回 cited_fact_ids (引用了哪些 atomic_facts) + cited_doc_ids (来源文档),
让 endpoint 调用方能 drill-down 到原文段落。

接入点 (B AI 写 endpoint shell):
- GET /api/v1/clients/{client_id}/full_narrative
- B AI 的 endpoint 调 NarrativeKernel(db, ai).generate(client_id)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol


logger = logging.getLogger(__name__)


# ─── 8 段故事结构 (跟 DATA-CENTER §5.4 8 段对齐) ─────────


SECTION_KEYS: tuple[str, ...] = (
    "identity",          # 1. 机构身份
    "people",            # 2. 关键人物网
    "main_lines",        # 3. 业务主线
    "recent_changes",    # 4. 近期变化
    "risks",             # 5. 风险信号
    "our_collab",        # 6. 我方-客户合作历程
    "open_questions",    # 7. 待澄清空白
    "timeline",          # 8. 时间线
)

SECTION_TITLES: dict[str, str] = {
    "identity": "机构身份 + 历史",
    "people": "关键人物网",
    "main_lines": "业务主线",
    "recent_changes": "近期变化",
    "risks": "风险信号",
    "our_collab": "我方-客户合作历程",
    "open_questions": "待澄清空白",
    "timeline": "关键事件时间线",
}

# 每段抽取的 atomic_facts content_role 过滤
SECTION_ROLE_FILTERS: dict[str, set[str]] = {
    "identity": {"fact"},
    "people": {"fact", "quote"},
    "main_lines": {"plan", "progress", "decision", "fact"},
    "recent_changes": {"decision", "progress"},
    "risks": {"risk", "observation"},
    "our_collab": {"commitment", "lesson", "decision"},
    "open_questions": set(),  # 特殊: 取 verification_status='unverified' + low confidence
    "timeline": set(),  # 特殊: 全部带 time_anchor 的事实
}

# Tier A/B/C 引用规则 (R1)
TIER_A_SOURCE_TYPES = {"client_official_doc", "client_internal_doc", "client_verbal_meeting"}
TIER_B_SOURCE_TYPES = {
    "collaboration_task", "collaboration_review",
    "user_verbal_fact", "user_observation",  # 用户口述 + 主观观察, 都算 Tier B
    "llm_extracted",  # F2.1 LLM 抽出来的也算 Tier B (未验证版)
}
TIER_C_SOURCE_TYPES = {"internet_official", "internet_media", "system_derived"}
EXCLUDED_SOURCE_TYPES = {"internet_ugc", "internet_ai_inferred"}


# ─── 类型 ─────────────────────────────────────────────


@dataclass(frozen=True)
class StorySection:
    section_key: str            # SECTION_KEYS 之一
    title: str                  # SECTION_TITLES 对应
    body_markdown: str          # LLM 生成的 markdown
    cited_fact_ids: list[str]   # 引用的 atomic_facts
    cited_doc_ids: list[str]    # 引用的 v2_documents
    confidence: float           # 段级置信度
    source_count_by_tier: dict[str, int] = field(default_factory=dict)  # {a:N, b:M, c:K}


@dataclass(frozen=True)
class ClientNarrative:
    client_id: str
    client_name: str
    story_sections: list[StorySection]
    generated_at: str
    generation_session_id: str  # 关联 ai_episode_log
    total_facts_consulted: int  # 总共参考了多少条 atomic_facts
    facts_excluded_by_tier: int  # 因为 source_type 被排除的事实数
    reasoning_trace_id: str | None = None


# ─── DB 协议 ─────────────────────────────────────────


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


# ─── NarrativeKernel ─────────────────────────────────


class NarrativeKernel:
    """读 atomic_facts → 拼 8 段故事网"""

    def __init__(self, db: _DbLike, ai_service: object | None = None):
        self._db = db
        self._ai = ai_service

    def generate(
        self,
        client_id: str,
        *,
        actor_id: str = "narrative_kernel",
    ) -> ClientNarrative:
        """生成 8 段故事

        当前版本 (v0):
        - 8 段分头查 atomic_facts (按 content_role + Tier 过滤)
        - body_markdown 简单聚合: 列出每条事实 evidence (不调 LLM, 走 deterministic 模式)
        - 下一步 v1: 调 LLM 把每段事实编排成连贯叙事
        """
        # 找客户
        cli = self._db.fetchone(
            "SELECT id, name FROM clients WHERE id = ?", (client_id,)
        )
        if not cli:
            raise ValueError(f"client not found: {client_id}")

        # 拉客户全部 atomic_facts (排除 EXCLUDED tier + contradicted)
        facts = self._fetch_eligible_facts(client_id)
        total_consulted = len(facts)

        sections: list[StorySection] = []
        for sk in SECTION_KEYS:
            sections.append(self._build_section(sk, facts, client_id))

        session_id = f"nk_{uuid.uuid4().hex[:12]}"
        return ClientNarrative(
            client_id=client_id,
            client_name=str(cli["name"]),
            story_sections=sections,
            generated_at=datetime.now(timezone.utc).isoformat(),
            generation_session_id=session_id,
            total_facts_consulted=total_consulted,
            facts_excluded_by_tier=self._count_excluded(client_id),
        )

    # ─── 内部方法 ────────────────────────────────────

    def _fetch_eligible_facts(self, client_id: str) -> list[sqlite3.Row]:
        """拉客户全部 active + 非 contradicted 事实 (排除 ugc / ai_inferred)"""
        placeholders = ", ".join("?" for _ in EXCLUDED_SOURCE_TYPES)
        return self._db.fetchall(
            f"""
            SELECT id, subject_text, attribute, value_text, content_role,
                   source_type, confidence, time_anchor, speaker_person_id,
                   verification_status, validity_status, evidence_text,
                   source_v2_document_id, created_at
            FROM atomic_facts
            WHERE client_id = ?
              AND status = 'active'
              AND validity_status != 'superseded'
              AND verification_status != 'contradicted'
              AND source_type NOT IN ({placeholders})
            ORDER BY confidence DESC, created_at DESC
            """,
            (client_id, *EXCLUDED_SOURCE_TYPES),
        )

    def _count_excluded(self, client_id: str) -> int:
        placeholders = ", ".join("?" for _ in EXCLUDED_SOURCE_TYPES)
        row = self._db.fetchone(
            f"""
            SELECT COUNT(*) AS n FROM atomic_facts
            WHERE client_id = ? AND source_type IN ({placeholders})
            """,
            (client_id, *EXCLUDED_SOURCE_TYPES),
        )
        return int(row["n"] or 0) if row else 0

    def _build_section(
        self,
        section_key: str,
        all_facts: list[sqlite3.Row],
        client_id: str,
    ) -> StorySection:
        """按 section 类型筛选 facts + 生成 markdown"""
        # 筛选规则
        if section_key == "open_questions":
            section_facts = [
                f for f in all_facts
                if str(f["verification_status"]) == "unverified"
                and float(f["confidence"] or 0) < 0.7
            ]
        elif section_key == "timeline":
            section_facts = [f for f in all_facts if f["time_anchor"]]
            # 按 time_anchor 升序排
            section_facts = sorted(
                section_facts, key=lambda f: str(f["time_anchor"] or ""),
            )
        else:
            roles = SECTION_ROLE_FILTERS.get(section_key, set())
            section_facts = [
                f for f in all_facts if str(f["content_role"] or "") in roles
            ]

        # Tier 分层 (R1)
        tier_a = [f for f in section_facts if str(f["source_type"] or "") in TIER_A_SOURCE_TYPES]
        tier_b = [f for f in section_facts if str(f["source_type"] or "") in TIER_B_SOURCE_TYPES]
        tier_c = [f for f in section_facts if str(f["source_type"] or "") in TIER_C_SOURCE_TYPES]

        # 生成 markdown (v0: deterministic 模式, 列事实)
        body = self._render_section_v0(
            section_key, tier_a, tier_b, tier_c,
        )

        # 收集 cited ids (优先 Tier A, B 次之, C 仅作背景)
        cited_facts: list[str] = []
        cited_docs: set[str] = set()
        for tier_facts in (tier_a, tier_b, tier_c):
            for f in tier_facts[:20]:  # 每个 Tier 最多 20 条防溢出
                cited_facts.append(str(f["id"]))
                if f["source_v2_document_id"]:
                    cited_docs.add(str(f["source_v2_document_id"]))

        # 段级 confidence: Tier A 优先权重高
        if tier_a:
            avg_conf = sum(float(f["confidence"] or 0) for f in tier_a) / len(tier_a)
        elif tier_b:
            avg_conf = sum(float(f["confidence"] or 0) for f in tier_b) / len(tier_b) * 0.85
        elif tier_c:
            avg_conf = sum(float(f["confidence"] or 0) for f in tier_c) / len(tier_c) * 0.6
        else:
            avg_conf = 0.0

        return StorySection(
            section_key=section_key,
            title=SECTION_TITLES[section_key],
            body_markdown=body,
            cited_fact_ids=cited_facts,
            cited_doc_ids=list(cited_docs),
            confidence=round(avg_conf, 3),
            source_count_by_tier={
                "a": len(tier_a),
                "b": len(tier_b),
                "c": len(tier_c),
            },
        )

    def _render_section_v0(
        self,
        section_key: str,
        tier_a: list[sqlite3.Row],
        tier_b: list[sqlite3.Row],
        tier_c: list[sqlite3.Row],
    ) -> str:
        """v0 deterministic 渲染 (不调 LLM, 列事实).

        下一步 v1 用 LLM 编排成自然语言叙事 — 等顾源源对 prompt 设计后做。
        """
        lines: list[str] = []
        title = SECTION_TITLES[section_key]

        total = len(tier_a) + len(tier_b) + len(tier_c)
        if total == 0:
            lines.append(f"*(本段暂无数据 — 等 F2.1 抽取上量补充)*")
            return "\n".join(lines)

        # Tier A: 客户官方资料 (强权威)
        if tier_a:
            lines.append(f"### 客户已确认事实 ({len(tier_a)} 条)")
            for f in tier_a[:15]:
                s = str(f["subject_text"] or "?")
                a = str(f["attribute"] or "?")
                v = str(f["value_text"] or "")[:120]
                t = str(f["time_anchor"] or "")[:10]
                conf = float(f["confidence"] or 0)
                line = f"- **{s}** · {a} = {v}"
                if t:
                    line += f" *(@{t})*"
                line += f" *[conf {conf:.2f}]*"
                lines.append(line)
            if len(tier_a) > 15:
                lines.append(f"- *... 还有 {len(tier_a) - 15} 条 (查 cited_fact_ids 全文)*")
            lines.append("")

        # Tier B: 协作记录 + 用户口述 (中等权威)
        if tier_b:
            lines.append(f"### 我方协作 / 用户口述 ({len(tier_b)} 条)")
            for f in tier_b[:10]:
                s = str(f["subject_text"] or "?")
                a = str(f["attribute"] or "?")
                v = str(f["value_text"] or "")[:100]
                speaker = str(f["speaker_person_id"] or "")
                line = f"- {s} · {a} = {v}"
                if speaker:
                    line += f" *(说话人: {speaker})*"
                lines.append(line)
            if len(tier_b) > 10:
                lines.append(f"- *... 还有 {len(tier_b) - 10} 条*")
            lines.append("")

        # Tier C: 互联网背景 (仅引用, 不当结论)
        if tier_c:
            lines.append(f"### 互联网背景信息 (仅作参考, {len(tier_c)} 条)")
            for f in tier_c[:5]:
                v = str(f["value_text"] or "")[:80]
                lines.append(f"- *{v}*")
            lines.append("")

        return "\n".join(lines)


def get_narrative_kernel(db: _DbLike, ai_service: object | None = None) -> NarrativeKernel:
    return NarrativeKernel(db, ai_service)
