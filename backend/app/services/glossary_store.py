"""客户私有术语库存储层(迭代 7)。

每个客户都可以维护自己的术语表,例如:
- "红队"在客户 X 意指内部审计组;在客户 Y 意指攻防演练
- "曙光计划"对客户而言是 2026 年战略项目代号

这套术语库后续可注入到 RAG prompt 里让 AI 回答时使用正确含义。

W3 重构:本文件已不再裸写 SQL,转为 GlossaryRepository 的薄包装,保留 GlossaryEntry
对外接口供 main.py / glossary_candidate_generator.py 等 caller 不变。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.modules.glossary import GlossaryRepository, GlossaryTerm


@dataclass(frozen=True)
class GlossaryEntry:
    """对外的术语记录类型 — 与 client_glossary 表行结构对齐。

    跟 GlossaryTerm 的区别:
    - aliases: list[str](legacy 用列表,GlossaryTerm 用 tuple)
    - 不暴露 evidence_tier(legacy caller 没用到)
    """

    id: str
    client_id: str
    term: str
    normalized_term: str
    definition: str
    aliases: list[str]
    category: str
    created_at: str
    updated_at: str


def _to_entry(term: GlossaryTerm) -> GlossaryEntry:
    return GlossaryEntry(
        id=term.id,
        client_id=term.client_id,
        term=term.term,
        normalized_term=term.normalized_term,
        definition=term.definition,
        aliases=list(term.aliases),
        category=term.category,
        created_at=term.created_at,
        updated_at=term.updated_at,
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
    repo = GlossaryRepository(conn)
    terms, total = repo.list_terms_paginated(
        client_id, query=query, limit=limit, offset=offset
    )
    return [_to_entry(t) for t in terms], total


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
    repo = GlossaryRepository(conn)
    created = repo.create_term(
        client_id=client_id,
        term=term,
        definition=definition,
        aliases=aliases,
        category=category,
    )
    return _to_entry(created)


def get_glossary_entry(conn: sqlite3.Connection, *, entry_id: str) -> GlossaryEntry:
    repo = GlossaryRepository(conn)
    term = repo.get_term_by_id(entry_id)
    if term is None:
        raise ValueError(f"glossary entry not found: {entry_id}")
    return _to_entry(term)


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
    repo = GlossaryRepository(conn)
    updated = repo.update_term(
        entry_id,
        term=term,
        definition=definition,
        aliases=aliases,
        category=category,
    )
    return _to_entry(updated)


def delete_glossary_entry(conn: sqlite3.Connection, *, entry_id: str) -> bool:
    repo = GlossaryRepository(conn)
    return repo.delete_term(entry_id)


__all__ = [
    "GlossaryEntry",
    "create_glossary_entry",
    "delete_glossary_entry",
    "get_glossary_entry",
    "list_glossary",
    "update_glossary_entry",
]
