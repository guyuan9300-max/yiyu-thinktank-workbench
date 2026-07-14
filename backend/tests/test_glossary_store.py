"""客户术语库测试（迭代 7）。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.glossary_store import (
    create_glossary_entry,
    delete_glossary_entry,
    get_glossary_entry,
    list_glossary,
    update_glossary_entry,
)


SCHEMA = """
CREATE TABLE clients (id TEXT PRIMARY KEY);
CREATE TABLE client_glossary (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    definition TEXT NOT NULL DEFAULT '',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    category TEXT NOT NULL DEFAULT '',
    evidence_tier TEXT NOT NULL DEFAULT 'E3',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_client_glossary_client_term
    ON client_glossary(client_id, normalized_term);
INSERT INTO clients (id) VALUES ('cli-A');
INSERT INTO clients (id) VALUES ('cli-B');
"""


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


@pytest.mark.unit
def test_create_glossary_entry_round_trip(conn) -> None:
    entry = create_glossary_entry(
        conn,
        client_id="cli-A",
        term="红队",
        definition="该客户内部审计组的内部称谓",
        aliases=["内审组", "AUD"],
        category="组织黑话",
    )
    assert entry.id
    assert entry.term == "红队"
    assert entry.normalized_term == "红队"
    assert entry.definition == "该客户内部审计组的内部称谓"
    assert entry.aliases == ["内审组", "AUD"]
    assert entry.category == "组织黑话"


@pytest.mark.unit
def test_create_rejects_empty_term(conn) -> None:
    with pytest.raises(ValueError):
        create_glossary_entry(conn, client_id="cli-A", term="")
    with pytest.raises(ValueError):
        create_glossary_entry(conn, client_id="cli-A", term="   ")


@pytest.mark.unit
def test_create_dedupes_within_client(conn) -> None:
    """同客户同归一化名不允许重复（UNIQUE 约束）。"""
    create_glossary_entry(conn, client_id="cli-A", term="红队")
    with pytest.raises(sqlite3.IntegrityError):
        create_glossary_entry(conn, client_id="cli-A", term="红队")


@pytest.mark.unit
def test_create_allowed_across_clients(conn) -> None:
    """跨客户同名是合法的（不同含义）。"""
    e_a = create_glossary_entry(
        conn, client_id="cli-A", term="红队", definition="审计"
    )
    e_b = create_glossary_entry(
        conn, client_id="cli-B", term="红队", definition="攻防演练"
    )
    assert e_a.id != e_b.id
    assert e_a.definition != e_b.definition


@pytest.mark.unit
def test_list_glossary_pagination_and_filter(conn) -> None:
    create_glossary_entry(conn, client_id="cli-A", term="红队")
    create_glossary_entry(conn, client_id="cli-A", term="蓝队")
    create_glossary_entry(conn, client_id="cli-A", term="曙光计划", aliases=["X 计划"])

    rows_all, total_all = list_glossary(conn, client_id="cli-A")
    assert total_all == 3
    assert len(rows_all) == 3

    rows_q, total_q = list_glossary(conn, client_id="cli-A", query="队")
    assert total_q == 2

    rows_x, total_x = list_glossary(conn, client_id="cli-A", query="X 计划")
    assert total_x == 1


@pytest.mark.unit
def test_update_glossary_entry(conn) -> None:
    entry = create_glossary_entry(conn, client_id="cli-A", term="红队", definition="老解释")
    updated = update_glossary_entry(
        conn,
        entry_id=entry.id,
        definition="新解释 · 内审组在 2026 年改名为该称呼",
        aliases=["内审组", "AUD", "Red Team"],
    )
    assert updated.definition == "新解释 · 内审组在 2026 年改名为该称呼"
    assert "Red Team" in updated.aliases
    assert updated.term == "红队"  # 未传 term 不改


@pytest.mark.unit
def test_update_changes_normalized_term_when_term_changes(conn) -> None:
    entry = create_glossary_entry(conn, client_id="cli-A", term="红队")
    updated = update_glossary_entry(conn, entry_id=entry.id, term="红色团队")
    assert updated.term == "红色团队"
    assert updated.normalized_term == "红色团队"


@pytest.mark.unit
def test_delete_glossary_entry(conn) -> None:
    entry = create_glossary_entry(conn, client_id="cli-A", term="红队")
    deleted = delete_glossary_entry(conn, entry_id=entry.id)
    assert deleted is True
    with pytest.raises(ValueError):
        get_glossary_entry(conn, entry_id=entry.id)
