"""本地 narrative collector · 消费数据中心的"预制菜".

定位: 不重新扫描原始资料, 而是从已经预制好的加工层 (atomic_facts /
entities / memory_facts / evidence_cards) 按维度聚合出 fact bundle.

设计原则 (顾源源 2026/5/16 原话):
  "数据中心 = 预制菜中心 / 中央事实库. 扫一遍原始资料, 加工一次, 上层模块按需取用."

→ collector 只 SELECT 已经预制好的事实, 不调 LLM, 不重新扫文档.
→ 拿到的 facts 喂给 generator, generator 调一次 LLM 出 6 段叙事.

诊断报告 (2026-05-16) 暴露的 v0.1 浅显根因:
  - cloud collector 只查了 event_lines (1 条) + activities (5 条流水账) + tasks (0)
  - 完全没消费本地 314 atomic_facts + 645 entities + 152 v2_documents
  - 结果: LLM 看不到张真/高老师 (53 个 person entities), 看不到关键日期/金额, 叙事必然浅显
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.db import Database


# ============================================================
# Dataclasses · 类型化的预制菜
# ============================================================


@dataclass(frozen=True)
class PersonFact:
    """关键人物 — 来自 entities (entity_type='person'), 已 LLM 抽好."""
    name: str
    mention_count: int
    entity_id: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TimeAnchorFact:
    """关键时间锚 — 来自 entities (entity_type='date'), 高提及次数 = 真实承诺/履约日."""
    text: str
    mention_count: int
    entity_id: str


@dataclass(frozen=True)
class MoneyFact:
    """关键金额锚 — 来自 entities (entity_type='amount'), 真实商业承诺金额."""
    text: str
    mention_count: int
    entity_id: str


@dataclass(frozen=True)
class AtomicFactRow:
    """LLM 抽好的高置信度业务事实."""
    id: str
    subject: str
    attribute: str
    value: str
    confidence: float
    source_doc_id: str | None


@dataclass(frozen=True)
class EventLineFact:
    id: str
    name: str
    kind: str
    status: str
    stage: str
    summary: str
    intent: str
    current_blocker: str
    recent_decision: str
    next_step: str
    evidence_count: int
    owner_id: str | None
    updated_at: str


@dataclass(frozen=True)
class ActivityFact:
    id: str
    event_line_id: str
    event_line_name: str
    source_type: str
    source_id: str
    happened_at: str
    actor_name: str
    title: str
    summary: str


@dataclass(frozen=True)
class TaskFact:
    id: str
    title: str
    description: str
    priority: str
    progress_status: str
    deadline_at: str | None
    owner_name: str
    next_action: str
    current_blocker: str
    recent_decision: str
    updated_at: str


@dataclass(frozen=True)
class DocumentSummaryFact:
    """v2_documents 顶层摘要 — 不塞全文, 但暴露每份文档的标题 + summary."""
    id: str
    title: str
    summary: str
    ingested_at: str
    doc_kind: str


@dataclass(frozen=True)
class ProfileFact:
    """client_strategic_profiles (本地手填字段, 可空)."""
    industry: str
    scale: str
    influence: str
    current_needs: str
    pain_points: str
    strategic_value_to_yiyu: str
    decision_chain: str


@dataclass(frozen=True)
class ClarificationFact:
    """从云端拉取的澄清记录 (本地 collector 不直接读云端, 由 caller 传入)."""
    dimension: str
    answer: str
    answered_by: str
    answered_at: str


@dataclass(frozen=True)
class GlossaryRelation:
    """字典 term 之间的关联关系 (P0 项目画像核心 — 节点之间的边)."""
    subject_term: str
    predicate: str
    object_term: str
    confidence: float
    note: str


@dataclass(frozen=True)
class RiskSignalFact:
    """风险信号 (业务环境/关系/交付)."""
    title: str
    signal_kind: str   # business_env | relationship | delivery | other
    severity: str      # low | medium | high | critical
    description: str
    related_terms: list[str]
    status: str


@dataclass(frozen=True)
class CommitmentFact:
    """结构化承诺 (谁向谁承诺什么 + 时间 + 履约状态)."""
    committer: str
    recipient: str
    commitment_type: str
    content: str
    deadline: str
    status: str           # pending | fulfilled | overdue | cancelled
    related_terms: list[str]


@dataclass(frozen=True)
class DimensionChunk:
    """某个 dimension 关联的原文 chunk 摘要 (Phase A · 数据丰富).

    每个 narrative 维度按主题词从 v2_chunks 搜 top 1-3 个最相关的 chunks,
    摘要 ≤500 字, 给 LLM 当具体描述的原料.
    """
    dimension: str          # essence/business_intro/cooperation/...
    matched_term: str       # 匹配的主题词 (例: '心盛计划' 或 '战略陪伴')
    doc_title: str          # 来源文档标题
    excerpt: str            # 摘要 (≤500 字)
    # M1/M2 取材升级新增 (默认值兼容旧构造): 来源标注 + 检索路径
    score: float = 0.0              # 语义相关度分 (LIKE/结构化源为 0)
    source_doc_id: str = ""         # knowledge_document_id / v2_document_id
    source_path: str = ""           # 原文路径
    retrieval_path: str = ""        # 'semantic' | 'like_fallback' | '' (结构化源)


@dataclass(frozen=True)
class GlossaryAttribute:
    """字典属性 (P0.5 防幻觉锚点) — term.attribute = value 这种事实型属性.

    经 verification_status='verified' 人审过的属性才进入这个列表, 是 narrative
    生成时引用具体数字/姓名/日期的最高优先级锚点。
    """
    term: str
    attribute_name: str
    value_text: str
    value_unit: str
    scope: str
    as_of_date: str
    source_evidence: str


@dataclass(frozen=True)
class GlossaryTerm:
    """客户字典条目 (v1.2 新增): canonical_name + aliases + category + definition.

    业界 (Glean/GraphRAG/LightRAG) 共识: 字典是消除 LLM 幻觉的核心锚点。
    narrative_generator 优先用字典 canonical_name, 不再让 LLM 从碎片化 facts 自己拼。
    """
    canonical_name: str
    aliases: list[str]
    category: str
    definition: str


@dataclass(frozen=True)
class BusinessContextSnippet:
    """从 module_definitions DNA 里抽出来的业务上下文, 给 LLM 当『默认常识』."""
    source: str          # module DNA id (e.g. 'module:strategic_accompaniment')
    category: str        # purpose/scope/decision/architecture/...
    body: str            # 内容


@dataclass(frozen=True)
class ClientFactBundle:
    """本地数据中心给上层模块供应的统一 fact bundle.

    Caller (narrative_generator / 其他业务模块) 只读这个 bundle, 不再查原始表。
    """

    client_id: str
    client_name: str
    client_alias: str

    # 加工层 · LLM 已抽好的事实
    persons: list[PersonFact] = field(default_factory=list)
    time_anchors: list[TimeAnchorFact] = field(default_factory=list)
    money_anchors: list[MoneyFact] = field(default_factory=list)
    atomic_facts_by_attribute: dict[str, list[AtomicFactRow]] = field(default_factory=dict)

    # 业务事件层
    event_lines: list[EventLineFact] = field(default_factory=list)
    activities: list[ActivityFact] = field(default_factory=list)
    tasks: list[TaskFact] = field(default_factory=list)

    # 原始资料层 (顶层摘要, 不塞全文)
    documents: list[DocumentSummaryFact] = field(default_factory=list)
    document_count_total: int = 0

    # 用户手填层 (可空)
    profile: ProfileFact | None = None

    # 数据中心健康度 (诚实暴露缺口)
    health: dict[str, Any] = field(default_factory=dict)

    # 从云端注入的澄清记录 (本次生成时要吸纳)
    pending_clarifications: list[ClarificationFact] = field(default_factory=list)
    applied_clarifications: list[ClarificationFact] = field(default_factory=list)

    # 业务上下文 (益语方法论/顾源源身份/战略陪伴定义), 从 module_definitions DNA 抽
    business_context: list[BusinessContextSnippet] = field(default_factory=list)

    # 客户字典 (v1.2 新增): 从 client_glossary 表读, 是 LLM 的锚点
    glossary: list[GlossaryTerm] = field(default_factory=list)

    # P0 项目画像 3 张新表 (v1.5)
    glossary_relations: list[GlossaryRelation] = field(default_factory=list)
    risk_signals: list[RiskSignalFact] = field(default_factory=list)
    commitments: list[CommitmentFact] = field(default_factory=list)

    # P0.5 字典属性 (v1.6) — 防幻觉锚点
    glossary_attributes: list[GlossaryAttribute] = field(default_factory=list)

    # Phase A · 6 维 chunks 原文摘要 (key=dimension, value=list of DimensionChunk)
    dimension_chunks: dict[str, list[DimensionChunk]] = field(default_factory=dict)

    # R4 P0-4 · 顾源源 5/23 钦定: 战略陪伴 6 段叙事必须读 R3 新表
    contracts_r4: list[dict] = field(default_factory=list)            # contract_structures
    historical_links_r4: list[dict] = field(default_factory=list)     # historical_reference_links
    file_identities_r4: list[dict] = field(default_factory=list)      # file_identities
    data_gaps_r4: list[dict] = field(default_factory=list)            # data_gaps
    external_evidence_r4: list[dict] = field(default_factory=list)    # external_evidence_cards

    def is_thin(self) -> bool:
        return (
            not self.persons
            and not self.atomic_facts_by_attribute
            and not self.event_lines
            and not self.documents
        )


# ============================================================
# 噪音过滤 — DNA 已记: memory_facts 90% 是 task_signal / attachment_signal 流水账
# ============================================================

_DIRTY_FACT_KEY_PREFIXES = (
    "task_signal:",
    "attachment_signal:",
    "data_center_ingest:",
    "reference_match:",
)

_DIRTY_CLAIM_SUFFIXES = (
    "已作为任务附件进入项目资料库",
    "已进入项目资料层",
    ".jpeg",
    ".jpg",
    ".png",
    ".pdf",
)


def _is_dirty_evidence_card(claim: str) -> bool:
    text = (claim or "").strip()
    if not text:
        return True
    return any(text.endswith(suffix) or suffix in text for suffix in _DIRTY_CLAIM_SUFFIXES)


def _is_dirty_memory_fact_key(key: str) -> bool:
    return any(key.startswith(p) for p in _DIRTY_FACT_KEY_PREFIXES)


# ============================================================
# 主入口 · 一次性把所有加工层聚合成 ClientFactBundle
# ============================================================


def collect_client_fact_bundle(
    db: Database,
    client_id: str,
    *,
    viewer_user_id: str = "",
    person_limit: int = 60,
    time_anchor_limit: int = 30,
    money_anchor_limit: int = 20,
    atomic_fact_limit: int = 200,
    event_line_limit: int = 24,
    activity_limit: int = 80,
    task_limit: int = 50,
    document_limit: int = 60,
) -> ClientFactBundle:
    """从本地数据中心一次性收齐所有预制菜.

    隔离边界 (机制化):
      - viewer_user_id 非空 → v2_chunks (文档原文层) 只取 viewer 自己上传的 + 空 owner 的历史数据;
        避免 A 写战略时被 B 上传的细碎调研污染思路。
      - 数据中心层 (字典 / 承诺 / 风险 / 事件线 / 事实卡片) 全员共享, 不按 user 过滤 —
        这是众包共建的精髓层, 大家拼拼图。
    """
    client_row = db.fetchone(
        "SELECT id, name, alias FROM clients WHERE id = ?",
        (client_id,),
    )
    if not client_row:
        raise ValueError(f"client not found: {client_id}")

    business_context = _collect_business_context(db)
    glossary = _collect_glossary(db, client_id)
    glossary_relations = _collect_glossary_relations(db, client_id)
    risk_signals = _collect_risk_signals(db, client_id)
    commitments = _collect_commitments(db, client_id)
    glossary_attributes = _collect_glossary_attributes(db, client_id)
    dim_chunks = _collect_dimension_chunks(db, client_id, glossary, viewer_user_id=viewer_user_id)
    persons = _collect_persons(db, client_id, person_limit)
    time_anchors = _collect_time_anchors(db, client_id, time_anchor_limit)
    money_anchors = _collect_money_anchors(db, client_id, money_anchor_limit)
    atomic_by_attr = _collect_atomic_facts(db, client_id, atomic_fact_limit)
    event_lines = _collect_event_lines(db, client_id, event_line_limit)
    activities = _collect_activities(db, client_id, activity_limit)
    tasks = _collect_tasks(db, client_id, task_limit)
    documents, total_docs = _collect_documents(db, client_id, document_limit)
    profile = _collect_profile(db, client_id)
    health = _compute_health(
        atomic_count=sum(len(rows) for rows in atomic_by_attr.values()),
        entity_count=len(persons) + len(time_anchors) + len(money_anchors),
        event_lines=event_lines,
        document_count=total_docs,
        evidence_quality=_assess_evidence_quality(db, client_id),
    )

    # R4 P0-4 · 顾源源 5/23 钦定: 战略陪伴 6 段叙事必须读 R3 新表
    # 加 contracts / historical_links / file_identities / data_gaps / external_evidence
    def _safe_fetch(sql: str, params: tuple = ()) -> list[dict]:
        try:
            return [dict(r) for r in db.fetchall(sql, params)]
        except Exception:
            return []

    contracts_r4 = _safe_fetch(
        """SELECT id, party_a, party_b, project_name, signed_at, effective_period,
                  amount, deliverables_json, responsibilities_json, version
           FROM contract_structures WHERE client_id = ?""", (client_id,),
    )
    historical_links_r4 = _safe_fetch(
        """SELECT ref_text, ref_type, target_table, target_id, match_score, source_doc_type
           FROM historical_reference_links WHERE client_id = ?
           ORDER BY resolved_at DESC LIMIT 30""", (client_id,),
    )
    file_identities_r4 = _safe_fetch(
        """SELECT id, file_name, file_type, file_role, project_name, version, file_time,
                  main_subject, is_authoritative
           FROM file_identities WHERE client_id = ?
           ORDER BY file_time DESC LIMIT 30""", (client_id,),
    )
    data_gaps_r4 = _safe_fetch(
        """SELECT id, gap_type, subject, internal_value, external_value, suggested_action
           FROM data_gaps WHERE client_id = ? AND status = 'open'
           ORDER BY detected_at DESC LIMIT 15""", (client_id,),
    )
    external_evidence_r4 = _safe_fetch(
        """SELECT id, title, summary, source_tier, relation_to_internal, confidence
           FROM external_evidence_cards WHERE client_id = ? AND status = 'active'
           ORDER BY created_at DESC LIMIT 15""", (client_id,),
    )

    return ClientFactBundle(
        client_id=str(client_row["id"]),
        client_name=str(client_row["name"] or ""),
        client_alias=str(client_row["alias"] or ""),
        persons=persons,
        time_anchors=time_anchors,
        money_anchors=money_anchors,
        atomic_facts_by_attribute=atomic_by_attr,
        event_lines=event_lines,
        activities=activities,
        tasks=tasks,
        documents=documents,
        document_count_total=total_docs,
        profile=profile,
        health=health,
        business_context=business_context,
        glossary=glossary,
        glossary_relations=glossary_relations,
        risk_signals=risk_signals,
        commitments=commitments,
        glossary_attributes=glossary_attributes,
        dimension_chunks=dim_chunks,
        # R4 P0-4
        contracts_r4=contracts_r4,
        historical_links_r4=historical_links_r4,
        file_identities_r4=file_identities_r4,
        data_gaps_r4=data_gaps_r4,
        external_evidence_r4=external_evidence_r4,
    )


def _collect_glossary_relations(db: Database, client_id: str) -> list[GlossaryRelation]:
    """字典 term 间关联关系 — P0 项目画像的『边』."""
    try:
        rows = db.fetchall(
            """
            SELECT g1.term AS subject_term, gr.predicate, g2.term AS object_term,
                   gr.confidence, gr.note, gr.status
            FROM glossary_relations gr
            LEFT JOIN client_glossary g1 ON gr.subject_term_id = g1.id
            LEFT JOIN client_glossary g2 ON gr.object_term_id = g2.id
            WHERE gr.client_id = ? AND gr.status != 'rejected'
            """,
            (client_id,),
        )
    except Exception:
        return []
    return [
        GlossaryRelation(
            subject_term=str(r["subject_term"] or ""),
            predicate=str(r["predicate"] or ""),
            object_term=str(r["object_term"] or ""),
            confidence=float(r["confidence"] or 0.0),
            note=str(r["note"] or ""),
        )
        for r in rows
        if str(r["subject_term"] or "").strip()
    ]


def _collect_risk_signals(db: Database, client_id: str) -> list[RiskSignalFact]:
    """风险信号 (业务环境/关系/交付)."""
    try:
        rows = db.fetchall(
            """
            SELECT title, signal_kind, severity, description, related_term_ids_json, status
            FROM risk_signals WHERE client_id = ? AND status = 'active'
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                     captured_at DESC
            """,
            (client_id,),
        )
    except Exception:
        return []
    # P1-4 性能: 原代码 for 循环里逐个 fetchone client_glossary → N+1 查询.
    # 改成一次性 batch fetch 整个 client 的字典, 在 Python 里 dict lookup.
    term_id_to_name = _load_glossary_id_to_term(db, client_id)
    out: list[RiskSignalFact] = []
    for r in rows:
        term_ids_raw = _safe_json(r["related_term_ids_json"], [])
        related_terms = []
        if isinstance(term_ids_raw, list):
            for tid in term_ids_raw:
                if not isinstance(tid, str):
                    continue
                name = term_id_to_name.get(tid)
                if name:
                    related_terms.append(name)
        out.append(RiskSignalFact(
            title=str(r["title"] or ""),
            signal_kind=str(r["signal_kind"] or "other"),
            severity=str(r["severity"] or "medium"),
            description=str(r["description"] or ""),
            related_terms=related_terms,
            status=str(r["status"] or "active"),
        ))
    return out


def _load_glossary_id_to_term(db: Database, client_id: str) -> dict[str, str]:
    """一次性 batch fetch 整个 client 字典 → {id: term}. 避免 risk_signal/commitment 解析时 N+1."""
    try:
        rows = db.fetchall(
            "SELECT id, term FROM client_glossary WHERE client_id = ?",
            (client_id,),
        )
    except Exception:
        return {}
    return {str(r["id"]): str(r["term"] or "") for r in rows if r["id"]}


def _collect_commitments(db: Database, client_id: str) -> list[CommitmentFact]:
    """承诺 (双向结构化, 含履约状态).

    W3:走 CommitmentRepository (SSOT),不再裸 SQL。related_terms 仍在本地解 term_ids→term
    (避免 N+1 提示风险,等 W4 在 Repository 加 join 版本)。
    """
    try:
        from app.modules.commitment import get_commitment_repository
        commitments = get_commitment_repository(db).list_active_for_client(client_id)
    except Exception:
        return []
    # P1-4 性能: 一次性 batch fetch 字典(同 _collect_risk_signals).
    term_id_to_name = _load_glossary_id_to_term(db, client_id)
    out: list[CommitmentFact] = []
    for c in commitments:
        related_terms: list[str] = []
        for tid in c.related_term_ids:
            name = term_id_to_name.get(tid)
            if name:
                related_terms.append(name)
        out.append(CommitmentFact(
            committer=c.committer,
            recipient=c.recipient,
            commitment_type=c.commitment_type or "delivery",
            content=c.content,
            deadline=(c.deadline or "")[:10],
            status=c.status or "pending",
            related_terms=related_terms,
        ))
    return out


def _collect_glossary(db: Database, client_id: str) -> list[GlossaryTerm]:
    """从 client_glossary 表读客户字典 (v1.2 加, 是 LLM narrative 的核心锚点)."""
    try:
        rows = db.fetchall(
            """
            SELECT term, normalized_term, definition, aliases_json, category
            FROM client_glossary WHERE client_id = ?
            ORDER BY category, term
            """,
            (client_id,),
        )
    except Exception:
        return []
    out: list[GlossaryTerm] = []
    for r in rows:
        aliases_raw = _safe_json(r["aliases_json"], [])
        aliases = [str(x) for x in aliases_raw if isinstance(aliases_raw, list) and isinstance(x, str)]
        out.append(GlossaryTerm(
            canonical_name=str(r["term"] or "").strip(),
            aliases=aliases,
            category=str(r["category"] or "").strip(),
            definition=str(r["definition"] or "").strip(),
        ))
    return out


def _collect_glossary_attributes(db: Database, client_id: str) -> list[GlossaryAttribute]:
    """字典属性 (P0.5) — 人审 verified 过的 term.attribute = value, 防幻觉锚点."""
    try:
        rows = db.fetchall(
            """
            SELECT cg.term, ga.attribute_name, ga.value_text, ga.value_unit,
                   ga.scope, ga.as_of_date, ga.source_evidence
            FROM glossary_attributes ga
            JOIN client_glossary cg ON cg.id = ga.term_id
            WHERE ga.client_id = ?
              AND ga.verification_status = 'verified'
            ORDER BY cg.term ASC, ga.attribute_name ASC
            """,
            (client_id,),
        )
    except Exception:
        return []
    return [
        GlossaryAttribute(
            term=str(r["term"] or "").strip(),
            attribute_name=str(r["attribute_name"] or "").strip(),
            value_text=str(r["value_text"] or "").strip(),
            value_unit=str(r["value_unit"] or "").strip(),
            scope=str(r["scope"] or "").strip(),
            as_of_date=str(r["as_of_date"] or "").strip(),
            source_evidence=str(r["source_evidence"] or "").strip(),
        )
        for r in rows
    ]


# Phase A · 6 维 narrative 都按主题词抓 chunks 原文
_DIMENSION_BASE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "essence": ("机构", "使命", "愿景", "成立", "定位", "影响力"),
    "cooperation": ("战略陪伴", "战略咨询", "合作", "服务协议", "陪伴", "对接"),
    "people": ("理事会", "团队", "负责人", "创始人", "秘书长", "成员"),
    "timeline": ("年度", "里程碑", "总结", "启动", "复盘"),
    # next_steps 扩词: 会议纪要里"承诺/行动"的常见表达
    "next_steps": (
        "待办", "deadline", "计划", "下一步", "后续",
        "牵头", "负责", "承诺", "接下来", "需在", "约定",
        "落地", "启动", "推进",
    ),
}

# 会议/对齐会/纪要类文档对 next_steps / cooperation / timeline 维度天然高价值,
# 标题命中下面任意词就给 boost 让它跨过老文档霸屏。
_MEETING_LIKE_TITLE_TOKENS = ("纪要", "对齐会", "会议", "战略对齐", "复盘会", "讨论会", "周会")


def _retrieve_top_chunks(
    db: Database,
    client_id: str,
    keywords: tuple[str, ...] | list[str],
    limit: int = 4,
    excerpt_len: int = 500,
    max_per_doc: int = 2,
    viewer_user_id: str = "",
) -> list[tuple[str, str, str]]:
    """按关键词在 v2_chunks 里搜 top N, 强制文档多样性 (避免某个文档霸屏).

    机制化 per-user 过滤: 当 viewer_user_id 非空时, chunks 只来自 (viewer 自己上传的文档
    + 历史无 owner 的 legacy 文档). 这样 A 写战略时不会被 B 上传的细碎调研污染思路;
    但数据中心层 (字典/承诺/事实/事件线 等其他表) 仍然全员共享.

    排序策略 (从优到劣):
      1) title_match=1 (标题含 keyword) — 强信号, 老逻辑保留
      2) is_meeting_like=1 (标题含 "纪要/对齐会/会议" 等) — 会议纪要对所有维度都高价值
      3) imported_at DESC — 今天上传的纪要要排在去年的资料前面 (recency)
      4) LENGTH(vc.content) DESC — chunk 信息密度

    每个文档最多取 max_per_doc 个 chunk (默认从 1 提到 2, 让一份纪要能贡献多段).
    limit 默认从 2 提到 4 (让会议纪要有机会进 top, 不被老文档完全挤掉).
    返回 [(matched_term, doc_title, excerpt), ...]
    """
    if not keywords:
        return []
    out: list[tuple[str, str, str]] = []
    seen_doc_chunks: set[str] = set()
    docs_count: dict[str, int] = {}

    # 用户视角过滤 SQL 片段 (空 owner 兼容历史导入数据)
    if viewer_user_id:
        owner_filter_sql = " AND (vd.owner_user_id = ? OR vd.owner_user_id = '')"
        owner_filter_params: tuple = (viewer_user_id,)
    else:
        owner_filter_sql = ""
        owner_filter_params = ()

    # 会议类标题 CASE WHEN 片段 — 标题命中任意 token 就 is_meeting_like=1
    meeting_like_clauses = " OR ".join(["d.title LIKE ?"] * len(_MEETING_LIKE_TITLE_TOKENS))
    meeting_like_params = tuple(f"%{tok}%" for tok in _MEETING_LIKE_TITLE_TOKENS)

    for kw in keywords:
        if not kw.strip():
            continue
        # P1-6 修复: LIKE 参数旧版 f"%{kw}%" 直接拼,kw 来自 glossary.canonical_name
        # (用户在 UI 输入). 若用户输入含 % 或 _ (例: "100%公益"),会匹配所有行 →
        # 该客户全部 chunk 进 prompt 超出数据边界 + 全表扫 CPU/内存峰值.
        # SQLite LIKE 支持 ESCAPE 子句, 用 \ 作为转义符.
        kw_escaped = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        try:
            rows = db.fetchall(
                f"""SELECT vc.content, d.title AS doc_title,
                          CASE WHEN d.title LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END AS title_match,
                          CASE WHEN ({meeting_like_clauses}) THEN 1 ELSE 0 END AS is_meeting_like,
                          COALESCE(vd.imported_at, vd.updated_at, '') AS sort_at
                   FROM v2_chunks vc
                   JOIN v2_documents vd ON vd.id = vc.v2_document_id
                   JOIN documents d ON d.id = vd.document_id
                   WHERE vd.client_id = ?
                     AND vc.content LIKE ? ESCAPE '\\'
                     {owner_filter_sql}
                   ORDER BY title_match DESC,
                            is_meeting_like DESC,
                            sort_at DESC,
                            LENGTH(vc.content) DESC
                   LIMIT ?""",
                (
                    f"%{kw_escaped}%",
                    *meeting_like_params,
                    client_id,
                    f"%{kw_escaped}%",
                    *owner_filter_params,
                    limit * 5,
                ),
            )
        except Exception:
            continue
        for r in rows:
            content = str(r["content"] or "")[:excerpt_len]
            doc_title = str(r["doc_title"] or "")
            dedup_key = f"{doc_title[:30]}::{content[:80]}"
            if dedup_key in seen_doc_chunks:
                continue
            # 文档多样性: 同一文档最多取 max_per_doc 个
            if docs_count.get(doc_title, 0) >= max_per_doc:
                continue
            seen_doc_chunks.add(dedup_key)
            docs_count[doc_title] = docs_count.get(doc_title, 0) + 1
            out.append((kw, doc_title, content))
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    return out


def _collect_dimension_chunks(
    db: Database, client_id: str, glossary: list[GlossaryTerm],
    viewer_user_id: str = "",
) -> dict[str, list[DimensionChunk]]:
    """对每个 dimension 取相关 chunks → dimension → list[DimensionChunk].

    M1/M2 升级: 文档原文取材从「固定关键词 LIKE + 每段 2 chunk」改为
    「语义检索 (knowledge_base.retrieve_knowledge_bundle, 按 client 隔离) 优先 +
    LIKE (_retrieve_top_chunks) 兜底」。语义意图见
    strategic_narrative_semantic_retriever.DIMENSION_SEMANTIC_QUERIES。
    business_intro 额外保留 per-project 结构化源 (tasks/复盘/会议);
    全项目覆盖 (去 project_terms[:6]) 留 M3。
    """
    from app.services import strategic_narrative_semantic_retriever as snr

    def _map(retr) -> list[DimensionChunk]:
        return [
            DimensionChunk(
                dimension=c.dimension, matched_term=c.matched_term,
                doc_title=c.doc_title, excerpt=c.excerpt,
                score=c.score, source_doc_id=c.source_doc_id,
                source_path=c.source_path, retrieval_path=c.retrieval_path,
            )
            for c in retr.chunks
        ]

    result: dict[str, list[DimensionChunk]] = {}

    # --- essence/cooperation/people/timeline/next_steps: 语义优先 + LIKE 兜底 ---
    for dim, kws in _DIMENSION_BASE_KEYWORDS.items():
        retr = snr.retrieve_dimension(
            db, client_id, dim,
            like_keywords=kws, like_fallback_fn=_retrieve_top_chunks,
            viewer_user_id=viewer_user_id,
        )
        result[dim] = _map(retr)

    # --- business_intro: 语义总览 (文档 chunk) + per-project 结构化源 ---
    # 文档 chunk 由语义检索统一负责 (替代原 per-project 的 LIKE 源 1);
    # tasks / 复盘 / 会议 这类结构化源仍按项目名抓 (语义层覆盖不到的口语化记录)。
    bi_retr = snr.retrieve_dimension(
        db, client_id, "business_intro",
        like_keywords=("项目", "业务", "服务", "方案"),
        like_fallback_fn=_retrieve_top_chunks,
        viewer_user_id=viewer_user_id,
    )
    bi_list: list[DimensionChunk] = _map(bi_retr)

    project_terms = [g.canonical_name for g in glossary if g.category in ("项目", "项目名")]
    # M3: 全项目覆盖 (去 [:6]) + 每项目语义召回; 预算公平分配, 保证每个项目都进叙事。
    _bi_seen_terms: set[str] = set()
    _per_project_k = max(1, min(3, 60 // max(1, len(project_terms))))
    for term in project_terms:
        # per-project 语义召回 (用项目名做 query, 比纯 LIKE 更准)
        proj_retr = snr.retrieve_dimension(
            db, client_id, "business_intro",
            query=f"{term} 这个项目或业务的服务对象、方法、规模、所处阶段、信息来源和当前进展是什么？",
            top_k=_per_project_k,
            like_keywords=(term,), like_fallback_fn=_retrieve_top_chunks,
            viewer_user_id=viewer_user_id,
        )
        for pc in proj_retr.chunks:
            _bi_seen_terms.add(term)
            bi_list.append(DimensionChunk(
                dimension="business_intro", matched_term=term,
                doc_title=pc.doc_title, excerpt=pc.excerpt, score=pc.score,
                source_doc_id=pc.source_doc_id, source_path=pc.source_path,
                retrieval_path=pc.retrieval_path,
            ))
        # 源: tasks (title + description 含项目名, 体现"日常任务里的项目澄清")
        try:
            task_rows = db.fetchall(
                """SELECT title, description, owner_name, progress_status FROM tasks
                   WHERE client_id=? AND (title LIKE ? OR description LIKE ?)
                   ORDER BY updated_at DESC LIMIT 2""",
                (client_id, f"%{term}%", f"%{term}%"),
            )
            for tr in task_rows:
                snippet = f"任务: {tr['title']}"
                if tr["description"]:
                    snippet += f" — {str(tr['description'])[:200]}"
                snippet += f" (负责人:{tr['owner_name']}, 状态:{tr['progress_status']})"
                bi_list.append(DimensionChunk(
                    dimension="business_intro",
                    matched_term=term,
                    doc_title=f"任务记录 · {tr['title'][:40]}",
                    excerpt=snippet[:300],
                ))
        except Exception:
            pass
        # 源 3: 周复盘 (note + structured_note_json 含项目名)
        try:
            review_rows = db.fetchall(
                """SELECT wrt.note, wrt.week_label, t.title AS task_title
                   FROM weekly_review_task_entries wrt
                   JOIN tasks t ON t.id=wrt.task_id
                   WHERE t.client_id=? AND wrt.note LIKE ?
                   ORDER BY wrt.reviewed_at DESC LIMIT 2""",
                (client_id, f"%{term}%"),
            )
            for rr in review_rows:
                snippet = f"复盘 ({rr['week_label']}): 任务'{rr['task_title']}' — {str(rr['note'] or '')[:250]}"
                bi_list.append(DimensionChunk(
                    dimension="business_intro",
                    matched_term=term,
                    doc_title=f"周复盘 · {rr['week_label']}",
                    excerpt=snippet[:300],
                ))
        except Exception:
            pass
        # 源 4: 会议 transcript (含项目名的会议)
        try:
            meeting_rows = db.fetchall(
                """SELECT title, transcript_text FROM meetings
                   WHERE client_id=?
                     AND transcript_text IS NOT NULL
                     AND transcript_text LIKE ?
                   ORDER BY meeting_date DESC LIMIT 1""",
                (client_id, f"%{term}%"),
            )
            for mr in meeting_rows:
                text = str(mr["transcript_text"] or "")
                idx = text.find(term)
                if idx >= 0:
                    snippet_start = max(0, idx - 100)
                    snippet = f"会议《{mr['title']}》提到 {term}: {text[snippet_start:idx+200]}"
                    bi_list.append(DimensionChunk(
                        dimension="business_intro",
                        matched_term=term,
                        doc_title=f"会议 · {mr['title'][:30]}",
                        excerpt=snippet[:300],
                    ))
        except Exception:
            pass
    # M3: 没拿到任何料的项目留占位, 保证全部项目都出现在叙事里 (不让它消失)
    for term in project_terms:
        if not any(d.matched_term == term for d in bi_list):
            bi_list.append(DimensionChunk(
                dimension="business_intro", matched_term=term,
                doc_title=f"项目 · {term}",
                excerpt=f"项目「{term}」: 数据中心暂未检索到详细资料 (服务对象/方法/规模/阶段/来源待补充)。",
                retrieval_path="",
            ))
    result["business_intro"] = bi_list
    return result


def _collect_business_context(db: Database) -> list[BusinessContextSnippet]:
    """从 module_definitions DNA 抽『顾问默认常识』, 顺序优先抽核心益语方法论 + 顾源源身份."""
    # 这些 module 是 LLM 必须有的『脑子里默认常识』
    target_modules = (
        ("user:profile", ("identity", "purpose", "decision")),
        ("software:root", ("purpose", "architecture", "scope")),
        ("module:strategic_accompaniment", ("purpose", "scope", "decision", "architecture")),
        ("submodule:client_strategic_home", ("purpose", "scope", "decision")),
        ("principle:user_perspective_anchor", ("principle",)),
    )
    out: list[BusinessContextSnippet] = []
    try:
        for module_id, categories in target_modules:
            placeholders = ",".join("?" * len(categories))
            rows = db.fetchall(
                f"""
                SELECT category, content
                FROM module_definition_entries
                WHERE module_id = ?
                  AND category IN ({placeholders})
                  AND superseded_by IS NULL
                ORDER BY created_at DESC
                LIMIT 3
                """,
                (module_id, *categories),
            )
            for r in rows:
                body = str(r["content"] or "").strip()
                if not body:
                    continue
                # 截长 — 单条最多 400 字符, 避免吃光 prompt token
                if len(body) > 400:
                    body = body[:400] + "..."
                out.append(
                    BusinessContextSnippet(
                        source=module_id,
                        category=str(r["category"] or ""),
                        body=body,
                    )
                )
    except Exception:
        # module_definitions 表可能不存在(测试环境), fallback 给空
        return []
    return out


# ============================================================
# 各加工层的私有 collector — 单独可测
# ============================================================


def _safe_json(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _collect_persons(db: Database, client_id: str, limit: int) -> list[PersonFact]:
    # 必须过滤 status='active' — 排除 self_verify 标记为 'merged' 的重复实体
    rows = db.fetchall(
        """
        SELECT id, display_name, mention_count, aliases_json, attributes_json
        FROM entities
        WHERE client_id = ? AND entity_type = 'person'
          AND mention_count >= 2
          AND status = 'active'
        ORDER BY mention_count DESC, confidence DESC
        LIMIT ?
        """,
        (client_id, limit),
    )
    out: list[PersonFact] = []
    for r in rows:
        name = str(r["display_name"] or "").strip()
        if not name or len(name) < 2 or name.endswith("?"):
            continue
        out.append(
            PersonFact(
                name=name,
                mention_count=int(r["mention_count"] or 0),
                entity_id=str(r["id"]),
                aliases=[a for a in _safe_json(r["aliases_json"], []) if isinstance(a, str)],
                attributes=_safe_json(r["attributes_json"], {}) if isinstance(_safe_json(r["attributes_json"], {}), dict) else {},
            )
        )
    return out


def _collect_time_anchors(db: Database, client_id: str, limit: int) -> list[TimeAnchorFact]:
    # 必须过滤 status='active' — 排除 self_verify merged 的实体
    rows = db.fetchall(
        """
        SELECT id, display_name, mention_count
        FROM entities
        WHERE client_id = ? AND entity_type = 'date' AND mention_count >= 2
          AND status = 'active'
        ORDER BY mention_count DESC LIMIT ?
        """,
        (client_id, limit),
    )
    return [
        TimeAnchorFact(
            text=str(r["display_name"] or ""),
            mention_count=int(r["mention_count"] or 0),
            entity_id=str(r["id"]),
        )
        for r in rows
        if str(r["display_name"] or "").strip()
    ]


def _collect_money_anchors(db: Database, client_id: str, limit: int) -> list[MoneyFact]:
    # 必须过滤 status='active' — 排除 self_verify merged 的实体
    rows = db.fetchall(
        """
        SELECT id, display_name, mention_count
        FROM entities
        WHERE client_id = ? AND entity_type = 'amount' AND mention_count >= 1
          AND status = 'active'
        ORDER BY mention_count DESC LIMIT ?
        """,
        (client_id, limit),
    )
    return [
        MoneyFact(
            text=str(r["display_name"] or ""),
            mention_count=int(r["mention_count"] or 0),
            entity_id=str(r["id"]),
        )
        for r in rows
        if str(r["display_name"] or "").strip()
    ]


def _collect_atomic_facts(db: Database, client_id: str, limit: int) -> dict[str, list[AtomicFactRow]]:
    """拉 atomic_facts (顾源源 5/22 M-C.1: 放宽 status 过滤).

    原 query: status='active' AND confidence>=0.6 → 漏掉 503 条 superseded
    实测发现: 503 条 superseded 是"被新版替代的旧版本", N2 跨源印证需要它们
    (用户问"以前 X 是 Y" 也需要旧版本事实).

    改: status IN ('active', 'superseded'), 但 active 优先 + 同 (subject, attribute, value)
    只保留 active 那条 (去重).
    """
    rows = db.fetchall(
        """
        SELECT id, subject_text, attribute, value_text, confidence, source_v2_document_id,
               status, created_at
        FROM atomic_facts
        WHERE client_id = ?
          AND status IN ('active', 'superseded')
          AND confidence >= 0.6
        ORDER BY
          CASE status WHEN 'active' THEN 0 ELSE 1 END,
          confidence DESC,
          created_at DESC
        LIMIT ?
        """,
        (client_id, limit),
    )
    grouped: dict[str, list[AtomicFactRow]] = {}
    seen_sav: set[tuple[str, str, str]] = set()
    for r in rows:
        attr = str(r["attribute"] or "").strip() or "其他"
        subj = str(r["subject_text"] or "").strip()
        value = str(r["value_text"] or "").strip()
        if not subj and not value:
            continue
        sav_key = (subj.lower(), attr.lower(), value.lower())
        if sav_key in seen_sav:
            continue  # active 已写入, 同 SAV 的 superseded 跳过
        seen_sav.add(sav_key)
        fact = AtomicFactRow(
            id=str(r["id"]),
            subject=subj,
            attribute=attr,
            value=value,
            confidence=float(r["confidence"] or 0.0),
            source_doc_id=str(r["source_v2_document_id"]) if r["source_v2_document_id"] else None,
        )
        grouped.setdefault(attr, []).append(fact)
    return grouped


def _collect_event_lines(db: Database, client_id: str, limit: int) -> list[EventLineFact]:
    rows = db.fetchall(
        """
        SELECT id, name, kind, status, stage, summary, intent, current_blocker,
               recent_decision, next_step, evidence_count, owner_id, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC LIMIT ?
        """,
        (client_id, limit),
    )
    return [
        EventLineFact(
            id=str(r["id"]),
            name=str(r["name"] or ""),
            kind=str(r["kind"] or ""),
            status=str(r["status"] or ""),
            stage=str(r["stage"] or ""),
            summary=str(r["summary"] or ""),
            intent=str(r["intent"] or ""),
            current_blocker=str(r["current_blocker"] or ""),
            recent_decision=str(r["recent_decision"] or ""),
            next_step=str(r["next_step"] or ""),
            evidence_count=int(r["evidence_count"] or 0),
            owner_id=str(r["owner_id"]) if r["owner_id"] else None,
            updated_at=str(r["updated_at"] or ""),
        )
        for r in rows
    ]


def _collect_activities(db: Database, client_id: str, limit: int) -> list[ActivityFact]:
    rows = db.fetchall(
        """
        SELECT a.id, a.event_line_id, e.name AS event_line_name,
               a.source_type, a.source_id, a.happened_at,
               COALESCE(a.actor_name, '') AS actor_name,
               a.title, a.summary
        FROM event_line_activities a
        JOIN event_lines e ON e.id = a.event_line_id
        WHERE e.primary_client_id = ?
        ORDER BY a.happened_at DESC LIMIT ?
        """,
        (client_id, limit),
    )
    out: list[ActivityFact] = []
    for r in rows:
        title = str(r["title"] or "")
        summary = str(r["summary"] or "")
        # 过滤纯"新增任务"流水, 这些没有业务价值
        if title.startswith("新增任务：") and not summary.strip().lstrip("创建任务："):
            continue
        out.append(
            ActivityFact(
                id=str(r["id"]),
                event_line_id=str(r["event_line_id"]),
                event_line_name=str(r["event_line_name"] or ""),
                source_type=str(r["source_type"] or ""),
                source_id=str(r["source_id"] or ""),
                happened_at=str(r["happened_at"] or ""),
                actor_name=str(r["actor_name"] or ""),
                title=title,
                summary=summary,
            )
        )
    return out


def _collect_tasks(db: Database, client_id: str, limit: int) -> list[TaskFact]:
    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else ""
    name_like = f"%{client_name}%" if client_name else "%"
    rows = db.fetchall(
        """
        SELECT t.id, t.title, t.description, t.priority, t.progress_status,
               t.deadline_at,
               COALESCE(t.owner_name, '') AS owner_name,
               t.next_action, t.current_blocker, t.recent_decision,
               t.updated_at
        FROM tasks t
        WHERE t.client_id = ?
           OR EXISTS (SELECT 1 FROM event_lines e
                    WHERE e.primary_client_id = ? AND t.event_line_id = e.id)
           OR t.title LIKE ?
        ORDER BY t.updated_at DESC LIMIT ?
        """,
        (client_id, client_id, name_like, limit),
    )
    return [
        TaskFact(
            id=str(r["id"]),
            title=str(r["title"] or ""),
            description=str(r["description"] or ""),
            priority=str(r["priority"] or ""),
            progress_status=str(r["progress_status"] or ""),
            deadline_at=(str(r["deadline_at"]) if r["deadline_at"] else None),
            owner_name=str(r["owner_name"] or ""),
            next_action=str(r["next_action"] or ""),
            current_blocker=str(r["current_blocker"] or ""),
            recent_decision=str(r["recent_decision"] or ""),
            updated_at=str(r["updated_at"] or ""),
        )
        for r in rows
    ]


def _collect_documents(db: Database, client_id: str, limit: int) -> tuple[list[DocumentSummaryFact], int]:
    total_row = db.fetchone(
        "SELECT COUNT(*) AS c FROM v2_documents WHERE client_id = ?",
        (client_id,),
    )
    total = int(total_row["c"]) if total_row else 0

    rows = db.fetchall(
        """
        SELECT id, file_name, preview_text, imported_at, kind
        FROM v2_documents
        WHERE client_id = ?
        ORDER BY imported_at DESC LIMIT ?
        """,
        (client_id, limit),
    )
    docs = [
        DocumentSummaryFact(
            id=str(r["id"]),
            title=str(r["file_name"] or "").strip(),
            summary=str(r["preview_text"] or "").strip()[:600],  # M5: 240→600
            ingested_at=str(r["imported_at"] or ""),
            doc_kind=str(r["kind"] or ""),
        )
        for r in rows
        if str(r["file_name"] or "").strip()
    ]
    return docs, total


def _collect_profile(db: Database, client_id: str) -> ProfileFact | None:
    row = db.fetchone(
        """
        SELECT industry, scale, influence, current_needs, pain_points,
               strategic_value_to_yiyu, decision_chain
        FROM client_strategic_profiles WHERE client_id = ?
        """,
        (client_id,),
    )
    if not row:
        return None
    profile = ProfileFact(
        industry=str(row["industry"] or "").strip(),
        scale=str(row["scale"] or "").strip(),
        influence=str(row["influence"] or "").strip(),
        current_needs=str(row["current_needs"] or "").strip(),
        pain_points=str(row["pain_points"] or "").strip(),
        strategic_value_to_yiyu=str(row["strategic_value_to_yiyu"] or "").strip(),
        decision_chain=str(row["decision_chain"] or "").strip(),
    )
    if not any(
        getattr(profile, f)
        for f in ("industry", "scale", "current_needs", "pain_points", "strategic_value_to_yiyu", "decision_chain")
    ):
        return None
    return profile


def _assess_evidence_quality(db: Database, client_id: str) -> dict[str, int]:
    """诚实评估 evidence_cards 的业务可用度 — 多少是 doc_summary 流水, 多少是真证据."""
    rows = db.fetchall(
        """
        SELECT evidence_type, polarity, normalized_claim
        FROM evidence_cards WHERE client_id = ?
        """,
        (client_id,),
    )
    total = 0
    dirty = 0
    actionable = 0
    polarity_neutral = 0
    for r in rows:
        total += 1
        claim = str(r["normalized_claim"] or "")
        if _is_dirty_evidence_card(claim):
            dirty += 1
        if str(r["polarity"] or "neutral") == "neutral":
            polarity_neutral += 1
        if str(r["evidence_type"]) in ("commitment", "decision", "risk", "blocker"):
            actionable += 1
    return {
        "total": total,
        "dirty_doc_summary": dirty,
        "polarity_neutral": polarity_neutral,
        "business_actionable": actionable,
    }


def _compute_health(
    *,
    atomic_count: int,
    entity_count: int,
    event_lines: list[EventLineFact],
    document_count: int,
    evidence_quality: dict[str, int],
) -> dict[str, Any]:
    """诚实暴露数据中心加工层质量, 给前端做缺口诊断."""
    gaps: list[str] = []
    if not event_lines:
        gaps.append("event_lines 业务主线表 — 当前 0 条, 颗粒度未升级")
    elif len(event_lines) < 3:
        gaps.append(f"event_lines 颗粒度过粗 — 仅 {len(event_lines)} 条主线, 缺 thread_level / parent_thread_id")
    if evidence_quality.get("total", 0) > 0:
        dirty_ratio = evidence_quality["dirty_doc_summary"] / evidence_quality["total"]
        if dirty_ratio > 0.5:
            gaps.append(
                f"evidence_cards 质量低 — {evidence_quality['dirty_doc_summary']}/{evidence_quality['total']} "
                f"是文件入库流水, 不是业务证据; polarity {evidence_quality['polarity_neutral']}/{evidence_quality['total']} 全 neutral"
            )
    if document_count > 30 and atomic_count < 50:
        gaps.append(
            f"atomic_facts 抽取覆盖率低 — {document_count} 份文档只抽出 {atomic_count} 条事实, 平均 < 2 条/文档"
        )
    return {
        "atomic_facts_count": atomic_count,
        "entity_count": entity_count,
        "event_line_count": len(event_lines),
        "document_count": document_count,
        "evidence_quality": evidence_quality,
        "gaps": gaps,
    }
