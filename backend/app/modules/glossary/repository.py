"""GlossaryRepository · 字典/属性数据唯一读写入口

W3 扩容:
- 把 client_glossary 表的 5 个 CRUD 方法补全(list 含分页/查询,create/update/delete/get)
- 接受 sqlite3.Connection 或 Database 两种 db(_DbLike 协议),legacy services 也能调
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from .types import GlossaryAttribute, GlossaryTerm


# ── DB 协议 + Adapter ──────────────────────────────────────────────
# Repository 支持 2 类对象:
# 1. Database wrapper (backend/app/db.py: .fetchone/.fetchall/.execute)
# 2. 直接的 sqlite3.Connection (legacy services 用)
#
# 第 2 类自动包装,这样 legacy 函数签名不用改。


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


class _ConnAdapter:
    """把 sqlite3.Connection 包成 _DbLike 接口(legacy services 用)"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(query, params).fetchall()

    def execute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)


def _wrap_db(db: Any) -> _DbLike:
    """同时支持 Database 包装器 和 raw sqlite3.Connection"""
    if isinstance(db, sqlite3.Connection):
        return _ConnAdapter(db)
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_term(term: str) -> str:
    return term.strip().lower()


# ── Row → Type ──────────────────────────────────────────────────────


def _row_to_term(row: Any) -> GlossaryTerm:
    raw = row["aliases_json"] or "[]"
    try:
        aliases = json.loads(raw)
    except json.JSONDecodeError:
        aliases = []
    if not isinstance(aliases, list):
        aliases = []
    return GlossaryTerm(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        term=str(row["term"] or ""),
        normalized_term=str(row["normalized_term"] or ""),
        definition=str(row["definition"] or ""),
        aliases=tuple(str(a) for a in aliases),
        category=str(row["category"] or ""),
        evidence_tier=str(row["evidence_tier"] or "first_party"),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def _row_to_attribute(row: Any) -> GlossaryAttribute:
    return GlossaryAttribute(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        term_id=str(row["term_id"]),
        attribute_name=str(row["attribute_name"] or ""),
        value_category=str(row["value_category"] or "text"),
        value_text=str(row["value_text"] or ""),
        value_unit=str(row["value_unit"] or ""),
        scope=str(row["scope"] or ""),
        as_of_date=str(row["as_of_date"]) if row["as_of_date"] else None,
        source_type=str(row["source_type"] or "ai_inferred"),
        source_doc_id=str(row["source_doc_id"]) if row["source_doc_id"] else None,
        source_evidence=str(row["source_evidence"] or ""),
        confidence=float(row["confidence"] or 0),
        verification_status=str(row["verification_status"] or "pending"),
        verified_by=str(row["verified_by"]) if row["verified_by"] else None,
        verified_at=str(row["verified_at"]) if row["verified_at"] else None,
        rejection_note=str(row["rejection_note"] or ""),
        # evidence_tier 在 client_glossary 表(term)上,attribute 表无此字段
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


class GlossaryRepository:
    def __init__(self, db: Any):
        self._db = _wrap_db(db)

    # ── Term · read ──────────────────────────────────────────────

    def get_term_by_id(self, term_id: str) -> GlossaryTerm | None:
        if not term_id:
            return None
        row = self._db.fetchone(
            "SELECT * FROM client_glossary WHERE id = ?", (term_id,)
        )
        return _row_to_term(row) if row else None

    def list_terms_for_client(self, client_id: str) -> list[GlossaryTerm]:
        if not client_id:
            return []
        rows = self._db.fetchall(
            "SELECT * FROM client_glossary WHERE client_id = ? ORDER BY term",
            (client_id,),
        )
        return [_row_to_term(r) for r in rows]

    def find_term_by_normalized(
        self, client_id: str, normalized_term: str,
    ) -> GlossaryTerm | None:
        """根据归一化后的术语名查 — 用于去重/合并"""
        if not client_id or not normalized_term:
            return None
        row = self._db.fetchone(
            "SELECT * FROM client_glossary WHERE client_id = ? AND normalized_term = ?",
            (client_id, normalized_term),
        )
        return _row_to_term(row) if row else None

    def list_terms_paginated(
        self,
        client_id: str,
        *,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GlossaryTerm], int]:
        """分页查询术语 + 模糊匹配(term / aliases)。返回 (terms, total)。

        W3 新增:替代 legacy services/glossary_store.list_glossary。
        """
        if not client_id:
            return [], 0
        where = ["client_id = ?"]
        params: list[object] = [client_id]
        if query:
            where.append("(term LIKE ? OR aliases_json LIKE ?)")
            wildcard = f"%{query}%"
            params.append(wildcard)
            params.append(wildcard)
        where_clause = " AND ".join(where)

        count_row = self._db.fetchone(
            f"SELECT COUNT(*) AS n FROM client_glossary WHERE {where_clause}",
            tuple(params),
        )
        total = int(count_row["n"] or 0) if count_row else 0

        rows = self._db.fetchall(
            f"SELECT * FROM client_glossary WHERE {where_clause} "
            "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        return [_row_to_term(r) for r in rows], total

    # ── Term · write ─────────────────────────────────────────────

    def create_term(
        self,
        *,
        client_id: str,
        term: str,
        definition: str = "",
        aliases: list[str] | None = None,
        category: str = "",
        evidence_tier: str = "first_party",
    ) -> GlossaryTerm:
        """创建术语。UNIQUE(client_id, normalized_term) 保护重复。

        W3 新增:替代 legacy services/glossary_store.create_glossary_entry。
        """
        if not term or not term.strip():
            raise ValueError("term 不能为空")
        if not client_id:
            raise ValueError("client_id 不能为空")
        timestamp = _now_iso()
        entry_id = str(uuid.uuid4())
        normalized = _normalize_term(term)
        aliases_list = aliases or []
        self._db.execute(
            """
            INSERT INTO client_glossary (
                id, client_id, term, normalized_term, definition,
                aliases_json, category, evidence_tier, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                client_id,
                term.strip(),
                normalized,
                definition.strip(),
                json.dumps(aliases_list, ensure_ascii=False),
                category.strip(),
                evidence_tier,
                timestamp,
                timestamp,
            ),
        )
        result = self.get_term_by_id(entry_id)
        assert result is not None, "create_term 写入后立即读不到,db 异常"
        return result

    def update_term(
        self,
        term_id: str,
        *,
        term: str | None = None,
        definition: str | None = None,
        aliases: list[str] | None = None,
        category: str | None = None,
    ) -> GlossaryTerm:
        """部分更新术语。term 改动会同步重算 normalized_term。

        W3 新增:替代 legacy services/glossary_store.update_glossary_entry。
        """
        existing = self.get_term_by_id(term_id)
        if existing is None:
            raise ValueError(f"glossary entry not found: {term_id}")
        new_term = term.strip() if term is not None else existing.term
        new_definition = definition.strip() if definition is not None else existing.definition
        new_aliases = list(aliases) if aliases is not None else list(existing.aliases)
        new_category = category.strip() if category is not None else existing.category
        new_normalized = _normalize_term(new_term)
        self._db.execute(
            """
            UPDATE client_glossary
            SET term = ?, normalized_term = ?, definition = ?, aliases_json = ?,
                category = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_term,
                new_normalized,
                new_definition,
                json.dumps(new_aliases, ensure_ascii=False),
                new_category,
                _now_iso(),
                term_id,
            ),
        )
        result = self.get_term_by_id(term_id)
        assert result is not None, "update_term 写入后立即读不到,db 异常"
        return result

    def delete_term(self, term_id: str) -> bool:
        """删除术语。返回是否实际删除(false = 不存在)。

        W3 新增:替代 legacy services/glossary_store.delete_glossary_entry。
        注意:这里通过 _DbLike.execute 走,无法读 rowcount;先 SELECT 再 DELETE 来保留语义。
        """
        if not term_id:
            return False
        existing = self.get_term_by_id(term_id)
        if existing is None:
            return False
        self._db.execute("DELETE FROM client_glossary WHERE id = ?", (term_id,))
        return True

    # ── Attribute ────────────────────────────────────────────────

    def list_attributes_for_term(self, term_id: str) -> list[GlossaryAttribute]:
        if not term_id:
            return []
        rows = self._db.fetchall(
            "SELECT * FROM glossary_attributes WHERE term_id = ? ORDER BY attribute_name",
            (term_id,),
        )
        return [_row_to_attribute(r) for r in rows]

    def list_attributes_for_client(
        self,
        client_id: str,
        *,
        verified_only: bool = False,
    ) -> list[GlossaryAttribute]:
        if not client_id:
            return []
        if verified_only:
            rows = self._db.fetchall(
                "SELECT * FROM glossary_attributes WHERE client_id = ? "
                "AND verification_status = 'verified' "
                "ORDER BY attribute_name",
                (client_id,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM glossary_attributes WHERE client_id = ? "
                "ORDER BY attribute_name",
                (client_id,),
            )
        return [_row_to_attribute(r) for r in rows]

    def count_pending_verifications(self, client_id: str) -> int:
        if not client_id:
            return 0
        row = self._db.fetchone(
            "SELECT COUNT(*) AS n FROM glossary_attributes "
            "WHERE client_id = ? AND verification_status = 'pending'",
            (client_id,),
        )
        return int(row["n"]) if row else 0

    def verify_attribute(
        self,
        attribute_id: str,
        *,
        verified_by: str,
        verified_at: str,
        updated_at: str,
    ) -> bool:
        if not attribute_id:
            return False
        try:
            self._db.execute(
                "UPDATE glossary_attributes "
                "SET verification_status = 'verified', verified_by = ?, verified_at = ?, "
                "    updated_at = ? "
                "WHERE id = ? AND verification_status = 'pending'",
                (verified_by, verified_at, updated_at, attribute_id),
            )
            return True
        except Exception:
            return False


def get_glossary_repository(db: Any) -> GlossaryRepository:
    return GlossaryRepository(db)
