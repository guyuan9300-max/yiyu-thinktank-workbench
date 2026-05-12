"""客户私有术语库存储层（迭代 7）。

每个客户都可以维护自己的术语表，例如：
- "红队"在客户 X 意指内部审计组；在客户 Y 意指攻防演练
- "曙光计划"对客户而言是 2026 年战略项目代号

这套术语库后续可注入到 RAG prompt 里让 AI 回答时使用正确含义。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_term(term: str) -> str:
    return term.strip().lower()


@dataclass(frozen=True)
class GlossaryEntry:
    id: str
    client_id: str
    term: str
    normalized_term: str
    definition: str
    aliases: list[str]
    category: str
    created_at: str
    updated_at: str


def _row_to_entry(row: sqlite3.Row) -> GlossaryEntry:
    return GlossaryEntry(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        term=str(row["term"]),
        normalized_term=str(row["normalized_term"]),
        definition=str(row["definition"] or ""),
        aliases=json.loads(row["aliases_json"] or "[]"),
        category=str(row["category"] or ""),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def list_glossary(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[GlossaryEntry], int]:
    """分页查询术语。query 模糊匹配 term / aliases。"""
    where = ["client_id = ?"]
    params: list[object] = [client_id]
    if query:
        where.append("(term LIKE ? OR aliases_json LIKE ?)")
        wildcard = f"%{query}%"
        params.append(wildcard)
        params.append(wildcard)
    where_clause = " AND ".join(where)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM client_glossary WHERE {where_clause}",
        tuple(params),
    ).fetchone()
    total = int(count_row["n"] or 0) if count_row else 0

    rows = conn.execute(
        f"SELECT * FROM client_glossary WHERE {where_clause} "
        "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_row_to_entry(r) for r in rows], total


def create_glossary_entry(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    term: str,
    definition: str = "",
    aliases: list[str] | None = None,
    category: str = "",
) -> GlossaryEntry:
    """创建一条术语。UNIQUE 约束保证同客户同归一化名不重复。"""
    if not term or not term.strip():
        raise ValueError("term 不能为空")
    timestamp = _now_iso()
    entry_id = str(uuid.uuid4())
    normalized = _normalize_term(term)
    aliases_list = aliases or []
    conn.execute(
        """
        INSERT INTO client_glossary (
            id, client_id, term, normalized_term, definition,
            aliases_json, category, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            client_id,
            term.strip(),
            normalized,
            definition.strip(),
            json.dumps(aliases_list, ensure_ascii=False),
            category.strip(),
            timestamp,
            timestamp,
        ),
    )
    return get_glossary_entry(conn, entry_id=entry_id)


def get_glossary_entry(conn: sqlite3.Connection, *, entry_id: str) -> GlossaryEntry:
    row = conn.execute(
        "SELECT * FROM client_glossary WHERE id = ?",
        (entry_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"glossary entry not found: {entry_id}")
    return _row_to_entry(row)


def update_glossary_entry(
    conn: sqlite3.Connection,
    *,
    entry_id: str,
    term: str | None = None,
    definition: str | None = None,
    aliases: list[str] | None = None,
    category: str | None = None,
) -> GlossaryEntry:
    """部分更新一条术语。"""
    existing = get_glossary_entry(conn, entry_id=entry_id)
    new_term = term.strip() if term is not None else existing.term
    new_definition = definition.strip() if definition is not None else existing.definition
    new_aliases = aliases if aliases is not None else existing.aliases
    new_category = category.strip() if category is not None else existing.category
    new_normalized = _normalize_term(new_term)
    conn.execute(
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
            entry_id,
        ),
    )
    return get_glossary_entry(conn, entry_id=entry_id)


def delete_glossary_entry(conn: sqlite3.Connection, *, entry_id: str) -> bool:
    cur = conn.execute("DELETE FROM client_glossary WHERE id = ?", (entry_id,))
    return (cur.rowcount or 0) > 0


__all__ = [
    "GlossaryEntry",
    "create_glossary_entry",
    "delete_glossary_entry",
    "get_glossary_entry",
    "list_glossary",
    "update_glossary_entry",
]
