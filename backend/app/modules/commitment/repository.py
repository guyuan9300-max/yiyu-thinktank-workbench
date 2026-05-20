"""CommitmentRepository · 承诺数据的唯一读写入口

W2 范围:核心读方法 + 1 个写方法。
W3-4 把 main.py 里散落的 commitments SQL 全部迁过来。
"""
from __future__ import annotations

import json
from typing import Any

from .types import Commitment


_OPEN_STATUSES = ("pending", "in_progress", "blocked")


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
        self._db = db

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
