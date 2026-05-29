"""CommitmentRepository · 承诺数据的唯一读写入口

W3 扩容:
- 加 3 个针对 services 层调用 shape 的读方法(todo_aggregator / clarification_context /
  narrative_collector)
- 接受 sqlite3.Connection 或 Database 两种 db(_DbLike 协议),legacy services 也能调
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Protocol

from .types import Commitment


_OPEN_STATUSES = ("pending", "in_progress", "blocked")


# ── DB 协议 + Adapter ─────────────────────────────────────────────
# 与 glossary repository 同一模式:同时支持 Database 包装器 和 raw sqlite3.Connection,
# 让 legacy services 能直接调,无需改函数签名。


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


class _ConnAdapter:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(query, params).fetchall()

    def execute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)


def _wrap_db(db: Any) -> _DbLike:
    if isinstance(db, sqlite3.Connection):
        return _ConnAdapter(db)
    return db


def _row_to_commitment(row: Any) -> Commitment:
    raw = row["related_term_ids_json"] or "[]"
    try:
        terms = json.loads(raw)
    except json.JSONDecodeError:
        terms = []
    if not isinstance(terms, list):
        terms = []
    return Commitment(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        committer=str(row["committer"] or ""),
        recipient=str(row["recipient"] or ""),
        commitment_type=str(row["commitment_type"] or "delivery"),
        content=str(row["content"] or ""),
        deadline=str(row["deadline"]) if row["deadline"] else None,
        status=str(row["status"] or "pending"),
        related_term_ids=tuple(str(t) for t in terms),
        source_type=str(row["source_type"] or ""),
        source_id=str(row["source_id"] or ""),
        fulfilled_at=str(row["fulfilled_at"]) if row["fulfilled_at"] else None,
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


class CommitmentRepository:
    def __init__(self, db: Any):
        self._db = _wrap_db(db)

    def get_by_id(self, commitment_id: str) -> Commitment | None:
        if not commitment_id:
            return None
        row = self._db.fetchone(
            "SELECT * FROM commitments WHERE id = ?", (commitment_id,)
        )
        return _row_to_commitment(row) if row else None

    def list_for_client(self, client_id: str, *, only_open: bool = True) -> list[Commitment]:
        if not client_id:
            return []
        if only_open:
            rows = self._db.fetchall(
                "SELECT * FROM commitments WHERE client_id = ? AND status IN (?, ?, ?) "
                "ORDER BY deadline ASC NULLS LAST, created_at DESC",
                (client_id, *_OPEN_STATUSES),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM commitments WHERE client_id = ? "
                "ORDER BY deadline ASC NULLS LAST, created_at DESC",
                (client_id,),
            )
        return [_row_to_commitment(r) for r in rows]

    def list_overdue(self, *, now_iso: str, client_id: str | None = None) -> list[Commitment]:
        """deadline 已过 + 尚未 fulfilled/cancelled 的承诺"""
        if client_id:
            rows = self._db.fetchall(
                "SELECT * FROM commitments "
                "WHERE deadline IS NOT NULL AND deadline < ? "
                "AND status IN (?, ?, ?) AND client_id = ? "
                "ORDER BY deadline ASC",
                (now_iso, *_OPEN_STATUSES, client_id),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM commitments "
                "WHERE deadline IS NOT NULL AND deadline < ? "
                "AND status IN (?, ?, ?) "
                "ORDER BY deadline ASC",
                (now_iso, *_OPEN_STATUSES),
            )
        return [_row_to_commitment(r) for r in rows]

    def list_for_committer(self, committer: str, *, only_open: bool = True) -> list[Commitment]:
        """某人未完成的承诺(谁欠的债)"""
        if not committer:
            return []
        if only_open:
            rows = self._db.fetchall(
                "SELECT * FROM commitments WHERE committer = ? AND status IN (?, ?, ?) "
                "ORDER BY deadline ASC NULLS LAST",
                (committer, *_OPEN_STATUSES),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM commitments WHERE committer = ? "
                "ORDER BY deadline ASC NULLS LAST",
                (committer,),
            )
        return [_row_to_commitment(r) for r in rows]

    # ── W3 新增 · 替代 services 层裸 SQL ──────────────────────────

    def list_pending_for_client(self, client_id: str) -> list[Commitment]:
        """todo_aggregator 用:严格只取 status='pending' 的承诺,无排序约束。

        与 list_for_client(only_open=True) 区别:
        - only_open 包含 in_progress/blocked,这里只 pending
        - 这里无 ORDER BY(调用方自己排)
        """
        if not client_id:
            return []
        rows = self._db.fetchall(
            "SELECT * FROM commitments WHERE client_id = ? AND status = 'pending'",
            (client_id,),
        )
        return [_row_to_commitment(r) for r in rows]

    def list_for_client_status_grouped(self, client_id: str) -> list[Commitment]:
        """clarification_context 用:按 status 分组排序(pending→fulfilled→其他)→
        deadline ASC → updated_at DESC。返回客户全部承诺。
        """
        if not client_id:
            return []
        rows = self._db.fetchall(
            """
            SELECT * FROM commitments
            WHERE client_id = ?
            ORDER BY
                CASE status WHEN 'pending' THEN 0 WHEN 'fulfilled' THEN 1 ELSE 2 END,
                COALESCE(deadline, '9999') ASC,
                updated_at DESC
            """,
            (client_id,),
        )
        return [_row_to_commitment(r) for r in rows]

    def list_active_for_client(self, client_id: str) -> list[Commitment]:
        """narrative_collector 用:status != cancelled 的承诺,按 overdue→pending→其他、
        deadline ASC 排序。
        """
        if not client_id:
            return []
        rows = self._db.fetchall(
            """
            SELECT * FROM commitments
            WHERE client_id = ? AND status != 'cancelled'
            ORDER BY
                CASE status WHEN 'overdue' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                deadline
            """,
            (client_id,),
        )
        return [_row_to_commitment(r) for r in rows]

    # ── Write ────────────────────────────────────────────────────

    def mark_fulfilled(
        self, commitment_id: str, *, fulfilled_at: str, updated_at: str,
    ) -> bool:
        """标记承诺已完成"""
        if not commitment_id:
            return False
        try:
            self._db.execute(
                "UPDATE commitments SET status = 'fulfilled', fulfilled_at = ?, updated_at = ? "
                "WHERE id = ? AND status NOT IN ('fulfilled', 'cancelled')",
                (fulfilled_at, updated_at, commitment_id),
            )
            return True
        except Exception:
            return False


def get_commitment_repository(db: Any) -> CommitmentRepository:
    return CommitmentRepository(db)
