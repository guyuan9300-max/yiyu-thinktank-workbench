"""GlossaryRepository · 字典/属性数据唯一读写入口

W2 范围:核心读 + 1 个写(verification)。
W3 把 services/glossary_*.py 6 个文件全切到本 Repository。
"""
from __future__ import annotations

import json
from typing import Any

from .types import GlossaryAttribute, GlossaryTerm


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
        self._db = db

    # ── Term ──

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

    # ── Attribute ──

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

    # ── Write ──

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
