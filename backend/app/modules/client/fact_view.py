"""ClientFactView · L2 共识层核心 (Phase 1 F1.2)

服务: V2.2_NORTH_STAR.md 目标 B (机器人能拿全数据流畅回答)
按: docs/V2.2_PHASE1_SPEC_F12.md

设计原则:
- 不动 schema, 只是组合现有 6 表的事实
- 默认轻量 (chips 字段), 大字段按需 lazy load
- 复用 F1.1 ClientRepository + W3 CommitmentRepository
- 复用 W3 _wrap_db 模式兼容 raw sqlite3.Connection

下游 (Phase 1):
- F1.3 ClientScopeFilter 写入前用 can_write check (F1.1 已提供)
- F1.4 main.py top 50 处 client_id 查询切到本类
- F1.5 前端 useClientFact hook 通过 GET /api/v1/clients/{id}/fact-bundle 消费本类
- F1.6 5 个 view 切到 useClientFact

下游 (Phase 2-3):
- Phase 2 F2.1 LLM extractor 写入后 emit_fact_changed
- Phase 3 F3.1 NarrativeKernel 订阅 fact_changed 事件
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.modules.commitment import (
    CommitmentRepository,
    get_commitment_repository,
)

from .facts import (
    AtomicFactRef,
    ClientFactBundle,
    CommitmentFact,
    DnaDocumentRef,
    EventLineFact,
    TaskFact,
)
from .repository import (
    ClientRepository,
    _wrap_db,
    get_client_repository,
)


# ── 事件通知 callback (为 F3 NarrativeKernel 准备) ──
FactChangedCallback = Callable[[str, str, str], None]
"""(client_id, fact_type, change_kind) -> None
fact_type: 'event_line' / 'task' / 'commitment' / 'dna' / 'atomic'
change_kind: 'created' / 'updated' / 'deleted'
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: object, max_chars: int = 200) -> str:
    """长文本截断 (description / intent 等)"""
    if text is None:
        return ""
    s = str(text).strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "..."


class ClientFactView:
    """L2 共识层: 所有 client_id 相关查询走这层

    构造时注入 repo (而不是 new), 方便 F1.4 main.py 切迁时复用相同实例。
    """

    def __init__(
        self,
        db: Any,
        client_repo: ClientRepository | None = None,
        commitment_repo: CommitmentRepository | None = None,
    ) -> None:
        self._db = _wrap_db(db)
        # 注入或自动 new (跟 W1 organization 模式一致)
        self._client_repo = client_repo or get_client_repository(db)
        self._commitment_repo = commitment_repo or get_commitment_repository(db)
        self._fact_changed_callbacks: list[FactChangedCallback] = []

    # ── 核心方法 · 完整 bundle ─────────────────────────────────
    def get_fact_bundle(
        self,
        client_id: str,
        *,
        include_archived: bool = False,
    ) -> ClientFactBundle | None:
        """一个客户的全部事实。不存在返回 None。"""
        client = self._client_repo.get_by_id(client_id)
        if client is None:
            return None
        if not include_archived and self._client_repo.is_archived(client_id):
            return None

        event_lines = self.list_event_lines(client_id)
        tasks = self.list_tasks(client_id, include_done=False)
        commitments = self.list_commitments(client_id)
        dna_documents = self.list_dna_documents(client_id)
        atomic_facts = self.list_atomic_facts(client_id, limit=200)

        return ClientFactBundle(
            client=client,
            event_lines=tuple(event_lines),
            tasks=tuple(tasks),
            commitments=tuple(commitments),
            dna_documents=tuple(dna_documents),
            atomic_facts=tuple(atomic_facts),
            key_decisions=(),  # Phase 2 才有
            snapshot_at=_now_iso(),
            sources={
                "client": "ClientRepository.get_by_id (F1.1)",
                "event_lines": "event_lines.primary_client_id",
                "tasks": "tasks.client_id",
                "commitments": "CommitmentRepository.list_for_client (W3)",
                "dna_documents": "client_dna_documents.client_id",
                "atomic_facts": "atomic_facts.client_id WHERE status='active'",
            },
            counts={
                "event_lines": len(event_lines),
                "tasks": len(tasks),
                "commitments": len(commitments),
                "dna_documents": len(dna_documents),
                "atomic_facts": len(atomic_facts),
            },
        )

    def get_fact_bundle_lite(
        self, client_id: str
    ) -> ClientFactBundle | None:
        """轻量版 — 只返回 counts + client 基础,不返回事实 list。

        给客户列表用,避免每次都拉 200 条 atomic_facts。
        """
        client = self._client_repo.get_by_id(client_id)
        if client is None:
            return None
        if self._client_repo.is_archived(client_id):
            return None

        # 用 COUNT 查询代替全量 fetch
        counts = {
            "event_lines": self._count(
                "SELECT COUNT(*) AS n FROM event_lines WHERE primary_client_id = ?",
                (client_id,),
            ),
            "tasks": self._count(
                "SELECT COUNT(*) AS n FROM tasks WHERE client_id = ? "
                "AND status NOT IN ('done', 'completed', 'cancelled', 'archived')",
                (client_id,),
            ),
            "commitments": len(
                self._commitment_repo.list_for_client_status_grouped(client_id)
            ),
            "dna_documents": self._count(
                "SELECT COUNT(*) AS n FROM client_dna_documents WHERE client_id = ?",
                (client_id,),
            ),
            "atomic_facts": self._count(
                "SELECT COUNT(*) AS n FROM atomic_facts "
                "WHERE client_id = ? AND status = 'active'",
                (client_id,),
            ),
        }

        return ClientFactBundle(
            client=client,
            event_lines=(),
            tasks=(),
            commitments=(),
            dna_documents=(),
            atomic_facts=(),
            key_decisions=(),
            snapshot_at=_now_iso(),
            sources={"lite": "counts only, call get_fact_bundle for full"},
            counts=counts,
        )

    def _count(self, sql: str, params: tuple) -> int:
        try:
            row = self._db.fetchone(sql, params)
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    # ── 细粒度查询 ────────────────────────────────────────────
    def list_event_lines(self, client_id: str) -> list[EventLineFact]:
        """客户的事件线列表 (按 updated_at DESC)"""
        if not client_id:
            return []
        try:
            rows = self._db.fetchall(
                """
                SELECT id, name, kind, status, stage, summary, intent,
                       current_blocker, recent_decision, next_step,
                       evidence_count, owner_id, owner_name,
                       primary_client_id, primary_client_name,
                       created_at, updated_at
                FROM event_lines
                WHERE primary_client_id = ?
                ORDER BY updated_at DESC
                """,
                (client_id,),
            )
        except Exception:
            return []
        return [
            EventLineFact(
                id=str(r["id"]),
                name=str(r["name"]),
                kind=str(r["kind"] or "custom"),
                status=str(r["status"] or "active"),
                stage=str(r["stage"] or ""),
                summary=str(r["summary"] or ""),
                intent=_truncate(r["intent"], 500),
                current_blocker=str(r["current_blocker"] or ""),
                recent_decision=str(r["recent_decision"] or ""),
                next_step=str(r["next_step"] or ""),
                evidence_count=int(r["evidence_count"] or 0),
                owner_id=str(r["owner_id"]) if r["owner_id"] else None,
                owner_name=str(r["owner_name"]) if r["owner_name"] else None,
                primary_client_id=str(r["primary_client_id"] or ""),
                primary_client_name=str(r["primary_client_name"] or ""),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
            for r in rows
        ]

    def list_tasks(
        self,
        client_id: str,
        *,
        include_done: bool = False,
        limit: int = 200,
    ) -> list[TaskFact]:
        """客户的任务列表 (按 deadline ASC, 然后 updated_at DESC)"""
        if not client_id:
            return []
        if include_done:
            status_clause = ""
        else:
            status_clause = (
                "AND status NOT IN ('done', 'completed', 'cancelled', 'archived')"
            )
        try:
            rows = self._db.fetchall(
                f"""
                SELECT id, title, description, status, priority, progress_status,
                       owner_id, owner_name, creator_id,
                       deadline_at, due_date, scheduled_start_at, completed_at,
                       event_line_id, business_category,
                       current_blocker, next_action, recent_decision,
                       evidence_count, source_type, source_id,
                       created_at, updated_at
                FROM tasks
                WHERE client_id = ? {status_clause}
                ORDER BY COALESCE(deadline_at, due_date) ASC,
                         updated_at DESC
                LIMIT ?
                """,
                (client_id, limit),
            )
        except Exception:
            return []
        return [
            TaskFact(
                id=str(r["id"]),
                title=str(r["title"]),
                description_preview=_truncate(r["description"], 200),
                status=str(r["status"]),
                priority=str(r["priority"]),
                progress_status=str(r["progress_status"] or "todo"),
                owner_id=str(r["owner_id"]) if r["owner_id"] else None,
                owner_name=str(r["owner_name"] or ""),
                creator_id=str(r["creator_id"] or ""),
                deadline_at=str(r["deadline_at"]) if r["deadline_at"] else None,
                due_date=str(r["due_date"]) if r["due_date"] else None,
                scheduled_start_at=(
                    str(r["scheduled_start_at"]) if r["scheduled_start_at"] else None
                ),
                completed_at=str(r["completed_at"]) if r["completed_at"] else None,
                event_line_id=str(r["event_line_id"]) if r["event_line_id"] else None,
                business_category=(
                    str(r["business_category"]) if r["business_category"] else None
                ),
                current_blocker=str(r["current_blocker"] or ""),
                next_action=str(r["next_action"] or ""),
                recent_decision=str(r["recent_decision"] or ""),
                evidence_count=int(r["evidence_count"] or 0),
                source_type=str(r["source_type"] or ""),
                source_id=str(r["source_id"]) if r["source_id"] else None,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
            for r in rows
        ]

    def list_commitments(self, client_id: str) -> list[CommitmentFact]:
        """复用 W3 CommitmentRepository"""
        if not client_id:
            return []
        try:
            commitments = self._commitment_repo.list_for_client_status_grouped(
                client_id
            )
        except Exception:
            return []
        return [
            CommitmentFact(
                id=c.id,
                committer=c.committer,
                recipient=c.recipient,
                commitment_type=c.commitment_type or "delivery",
                content=c.content,
                deadline=c.deadline or None,
                status=c.status or "pending",
                created_at=c.created_at or "",
                updated_at=c.updated_at or "",
            )
            for c in commitments
        ]

    def list_dna_documents(self, client_id: str) -> list[DnaDocumentRef]:
        """客户 DNA 模块列表 (轻量, 不带 markdown_content)"""
        if not client_id:
            return []
        try:
            rows = self._db.fetchall(
                """
                SELECT module_key, title, summary, file_name, source_kind,
                       updated_at, updated_by,
                       length(markdown_content) AS has_md_content
                FROM client_dna_documents
                WHERE client_id = ?
                ORDER BY updated_at DESC
                """,
                (client_id,),
            )
        except Exception:
            return []
        return [
            DnaDocumentRef(
                module_key=str(r["module_key"]),
                title=str(r["title"]),
                summary=str(r["summary"] or ""),
                file_name=str(r["file_name"] or ""),
                source_kind=str(r["source_kind"] or "manual"),
                updated_at=str(r["updated_at"]),
                updated_by=str(r["updated_by"] or ""),
                has_full_content=int(r["has_md_content"] or 0) > 0,
            )
            for r in rows
        ]

    def list_atomic_facts(
        self, client_id: str, *, limit: int = 200
    ) -> list[AtomicFactRef]:
        """客户的原子事实 (按 confidence DESC, status='active')"""
        if not client_id:
            return []
        try:
            rows = self._db.fetchall(
                """
                SELECT id, subject_text, attribute, value_text, confidence,
                       source_v2_chunk_id, source_v2_document_id, evidence_text,
                       status, updated_at
                FROM atomic_facts
                WHERE client_id = ? AND status = 'active'
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (client_id, limit),
            )
        except Exception:
            return []
        return [
            AtomicFactRef(
                id=str(r["id"]),
                subject_text=str(r["subject_text"]),
                attribute=str(r["attribute"]),
                value_text=str(r["value_text"]),
                confidence=float(r["confidence"] or 0.0),
                source_v2_document_id=(
                    str(r["source_v2_document_id"])
                    if r["source_v2_document_id"]
                    else None
                ),
                source_v2_chunk_id=(
                    str(r["source_v2_chunk_id"]) if r["source_v2_chunk_id"] else None
                ),
                evidence_text=str(r["evidence_text"]) if r["evidence_text"] else None,
                status=str(r["status"]),
                updated_at=str(r["updated_at"]),
            )
            for r in rows
        ]

    # ── 大字段 lazy load ────────────────────────────────────────
    def load_dna_full(self, client_id: str, module_key: str) -> str | None:
        """按需加载 DNA 模块的 markdown_content (大字段)"""
        if not client_id or not module_key:
            return None
        try:
            row = self._db.fetchone(
                "SELECT markdown_content FROM client_dna_documents "
                "WHERE client_id = ? AND module_key = ?",
                (client_id, module_key),
            )
        except Exception:
            return None
        return str(row["markdown_content"]) if row else None

    def load_task_full(self, task_id: str) -> str | None:
        """按需加载 task 的完整 description (大字段)"""
        if not task_id:
            return None
        try:
            row = self._db.fetchone(
                "SELECT description FROM tasks WHERE id = ?", (task_id,)
            )
        except Exception:
            return None
        return str(row["description"]) if row else None

    # ── 事件通知 (为 F3 NarrativeKernel 准备) ───────────────────
    def on_fact_changed(self, callback: FactChangedCallback) -> None:
        """订阅事实变更通知. Phase 3 F3.1 NarrativeKernel 用这个挂钩."""
        self._fact_changed_callbacks.append(callback)

    def emit_fact_changed(
        self, client_id: str, fact_type: str, change_kind: str
    ) -> None:
        """供 F1.4 切迁 main.py 时, 写入操作完成后调用通知"""
        for cb in self._fact_changed_callbacks:
            try:
                cb(client_id, fact_type, change_kind)
            except Exception:
                # 通知失败不阻塞主链
                pass

    # ── 列表汇总 (给客户列表页用) ───────────────────────────────
    def list_bundles_for_active_clients(
        self, *, limit: int = 50, lite: bool = True
    ) -> list[ClientFactBundle]:
        """所有活跃客户的 fact bundle (默认轻量, 给客户列表)"""
        clients = self._client_repo.list_active()[:limit]
        bundles: list[ClientFactBundle] = []
        getter = self.get_fact_bundle_lite if lite else self.get_fact_bundle
        for c in clients:
            b = getter(c.id)
            if b is not None:
                bundles.append(b)
        return bundles


def get_client_fact_view(db: Any) -> ClientFactView:
    """工厂 (跟 W1 / W3 工厂模式一致)"""
    return ClientFactView(db)
