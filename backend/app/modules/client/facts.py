"""client 模块的子事实类型 — ClientFactView 用 (Phase 1 F1.2)

每个子事实是不可变 dataclass, 镜像源表的核心字段, 加 provenance。
长字段 (markdown / normalized_text / 大 description) 默认不放进来,
按需通过 ClientFactView.load_*_full() 单独加载。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .types import ClientRecord


# ── 事件线事实 ─────────────────────────────────────────────────
@dataclass(frozen=True)
class EventLineFact:
    """事件线核心事实 (来自 event_lines 表)"""

    id: str
    name: str
    kind: str  # 'custom' / 'project_line' / etc.
    status: str  # 'active' / 'paused' / 'done' / ...
    stage: str  # '本周推进' 等业务阶段
    summary: str
    intent: str  # 用户对这条事件线的意图原话 (截到 500 字)
    current_blocker: str
    recent_decision: str
    next_step: str
    evidence_count: int
    owner_id: str | None
    owner_name: str | None
    primary_client_id: str
    primary_client_name: str
    created_at: str
    updated_at: str


# ── 任务事实 ───────────────────────────────────────────────────
@dataclass(frozen=True)
class TaskFact:
    """任务核心事实 (来自 tasks 表). description 默认裁到 200 字, 长文要 load_task_full。"""

    id: str
    title: str
    description_preview: str  # 前 200 字截断
    status: str  # 'todo' / 'doing' / 'done' / ...
    priority: str
    progress_status: str
    owner_id: str | None
    owner_name: str
    creator_id: str
    deadline_at: str | None
    due_date: str | None
    scheduled_start_at: str | None
    completed_at: str | None
    event_line_id: str | None
    business_category: str | None
    current_blocker: str
    next_action: str
    recent_decision: str
    evidence_count: int
    source_type: str
    source_id: str | None
    created_at: str
    updated_at: str


# ── 承诺事实 (复用 W3 commitment, 但简化字段) ────────────────
@dataclass(frozen=True)
class CommitmentFact:
    """承诺核心事实 (来自 commitments 表, 通过 W3 CommitmentRepository)"""

    id: str
    committer: str
    recipient: str
    commitment_type: str  # 'delivery' / 'decision' / 'review' / etc.
    content: str
    deadline: str | None
    status: str  # 'pending' / 'fulfilled' / 'overdue' / 'cancelled'
    created_at: str
    updated_at: str


# ── DNA 文档 ref (摘要, 长文按需 load) ─────────────────────────
@dataclass(frozen=True)
class DnaDocumentRef:
    """客户 DNA 模块文档引用 (来自 client_dna_documents 表)

    不带 markdown_content / normalized_text 这两个大字段,
    需要全文要单独调 ClientFactView.load_dna_full(client_id, module_key)。
    """

    module_key: str  # 'organization_intro' / 'business_intro' / etc.
    title: str
    summary: str  # 一行摘要 (db 已有 summary 字段)
    file_name: str
    source_kind: str  # 'manual' / 'generated'
    updated_at: str
    updated_by: str
    has_full_content: bool  # 是否有 markdown_content (UI 决定是否显示"读全文"按钮)


# ── 原子事实 ref ───────────────────────────────────────────────
@dataclass(frozen=True)
class AtomicFactRef:
    """单个 atomic_facts 行 (subject + attribute + value 三元组)"""

    id: str
    subject_text: str
    attribute: str
    value_text: str
    confidence: float
    source_v2_document_id: str | None  # provenance: 哪份 docx 抽出来的
    source_v2_chunk_id: str | None  # 具体哪个 chunk
    evidence_text: str | None
    status: str  # 'active' / 'superseded' / 'rejected'
    updated_at: str


# ── 完整事实包 ──────────────────────────────────────────────────
@dataclass(frozen=True)
class ClientFactBundle:
    """一个客户的全部已知事实 — L2 共识层核心数据结构

    给机器人问答 / 战略陪伴 / 客户档案 / 关系网四面板提供唯一真相源。
    任何上层只读 bundle 不直查表, 保证 4 面板看到的版本一致。
    """

    # 客户基础 (F1.1)
    client: ClientRecord

    # 业务事实 (用 tuple 保证 frozen)
    event_lines: tuple[EventLineFact, ...]
    tasks: tuple[TaskFact, ...]
    commitments: tuple[CommitmentFact, ...]
    dna_documents: tuple[DnaDocumentRef, ...]
    atomic_facts: tuple[AtomicFactRef, ...]

    # Phase 2 才有, Phase 1 留 () 空 tuple 占位
    key_decisions: tuple[object, ...] = field(default_factory=tuple)

    # 元信息
    snapshot_at: str = ""  # 这份 bundle 的快照时间 (ISO)
    sources: dict[str, str] = field(default_factory=dict)
    """每个字段的数据源, 例: {
        'client': 'ClientRepository.get_by_id',
        'event_lines': 'event_lines.primary_client_id',
        ...
    }"""

    # 计数 (用于 UI 显示, 不用每次 len)
    counts: dict[str, int] = field(default_factory=dict)
