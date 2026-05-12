"""矛盾检测 + 事实抽取测试（迭代 6）。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.contradiction_detector import (
    detect_and_record_for_fact,
    find_contradictions_for_fact,
    insert_fact,
    list_contradictions,
    persist_chunk_facts,
    update_review_status,
)
from app.services.fact_extractor import AtomicFact, extract_facts_from_chunk


SCHEMA = """
CREATE TABLE clients (id TEXT PRIMARY KEY);
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    title TEXT,
    path TEXT,
    original_source_path TEXT,
    created_at TEXT
);
CREATE TABLE v2_documents (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    file_name TEXT
);
CREATE TABLE v2_chunks (id TEXT PRIMARY KEY, v2_document_id TEXT);
CREATE TABLE entities (id TEXT PRIMARY KEY);
CREATE TABLE atomic_facts (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    subject_entity_id TEXT,
    subject_text TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value_text TEXT NOT NULL,
    value_normalized TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    source_v2_chunk_id TEXT,
    source_v2_document_id TEXT,
    evidence_text TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE fact_contradictions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    fact_a_id TEXT NOT NULL,
    fact_b_id TEXT NOT NULL,
    contradiction_type TEXT NOT NULL DEFAULT 'value_diff',
    severity TEXT NOT NULL DEFAULT 'medium',
    review_status TEXT NOT NULL DEFAULT 'pending',
    resolution_note TEXT,
    detected_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT
);
CREATE UNIQUE INDEX idx_fact_contradictions_pair
    ON fact_contradictions(client_id, fact_a_id, fact_b_id);
INSERT INTO clients (id) VALUES ('cli-A');
INSERT INTO v2_documents (id) VALUES ('doc-1');
INSERT INTO v2_chunks (id, v2_document_id) VALUES ('chunk-1', 'doc-1');
INSERT INTO v2_chunks (id, v2_document_id) VALUES ('chunk-2', 'doc-1');
"""


@pytest.fixture()
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


# ---- 事实抽取 ------------------------------------------------------------


@pytest.mark.unit
def test_extract_budget_fact() -> None:
    facts = extract_facts_from_chunk("客户的预算是 50 万元。")
    assert any(f.subject_text == "客户" and f.attribute == "预算" for f in facts)


@pytest.mark.unit
def test_extract_location_fact() -> None:
    facts = extract_facts_from_chunk("日慈科技位于北京中关村。")
    assert any(f.attribute == "位置" and "北京" in f.value_text for f in facts)


@pytest.mark.unit
def test_extract_plan_fact() -> None:
    facts = extract_facts_from_chunk("项目计划在6月1日上线。")
    assert any(f.attribute == "计划时间" for f in facts)


@pytest.mark.unit
def test_extract_no_match_returns_empty() -> None:
    assert extract_facts_from_chunk("普通陈述句无属性。") == []


# ---- 矛盾检测 ------------------------------------------------------------


@pytest.mark.unit
def test_no_contradiction_when_first_fact(conn: sqlite3.Connection) -> None:
    fact = AtomicFact("客户", "预算", "50 万元", "50万元", 0.8)
    fact_id = insert_fact(conn, client_id="cli-A", fact=fact)
    conflicts = find_contradictions_for_fact(
        conn, client_id="cli-A", fact=fact, exclude_fact_id=fact_id
    )
    assert conflicts == []


@pytest.mark.unit
def test_detects_conflicting_budget(conn: sqlite3.Connection) -> None:
    fact_old = AtomicFact("客户", "预算", "50 万元", "50万元", 0.8)
    fact_new = AtomicFact("客户", "预算", "30 万元", "30万元", 0.8)
    old_id = insert_fact(conn, client_id="cli-A", fact=fact_old)
    new_id = insert_fact(conn, client_id="cli-A", fact=fact_new)
    created = detect_and_record_for_fact(
        conn,
        client_id="cli-A",
        new_fact_id=new_id,
        fact=fact_new,
    )
    assert len(created) == 1
    # 验证落库
    pending, total = list_contradictions(conn, client_id="cli-A")
    assert total == 1
    assert pending[0]["subject_text"] == "客户"
    assert pending[0]["attribute"] == "预算"
    assert pending[0]["severity"] == "high"  # 预算属于金额类，high
    # 注意 SQL 顺序与传入参数不一定：值 a/b 都应该不同
    assert pending[0]["value_a"] != pending[0]["value_b"]


@pytest.mark.unit
def test_no_contradiction_when_same_value(conn: sqlite3.Connection) -> None:
    """同 subject+attribute+value（哪怕来源不同）不算矛盾。"""
    fact = AtomicFact("客户", "预算", "50 万元", "50万元", 0.8)
    old_id = insert_fact(conn, client_id="cli-A", fact=fact)
    new_id = insert_fact(conn, client_id="cli-A", fact=fact)
    created = detect_and_record_for_fact(
        conn, client_id="cli-A", new_fact_id=new_id, fact=fact
    )
    assert created == []


@pytest.mark.unit
def test_contradiction_isolated_by_client(conn: sqlite3.Connection) -> None:
    """跨客户同 subject+attr 不同 value → 不算矛盾（客户隔离）。"""
    conn.execute("INSERT INTO clients (id) VALUES ('cli-B')")
    fact_a = AtomicFact("客户", "预算", "50 万元", "50万元", 0.8)
    fact_b = AtomicFact("客户", "预算", "30 万元", "30万元", 0.8)
    insert_fact(conn, client_id="cli-A", fact=fact_a)
    new_id = insert_fact(conn, client_id="cli-B", fact=fact_b)
    created = detect_and_record_for_fact(
        conn, client_id="cli-B", new_fact_id=new_id, fact=fact_b
    )
    assert created == []


@pytest.mark.unit
def test_persist_chunk_facts_round_trip(conn: sqlite3.Connection) -> None:
    """同一个 chunk 抽出多个事实 + 跨 chunk 触发矛盾。"""
    facts_a = extract_facts_from_chunk("客户的预算是 50 万元。项目计划在6月1日上线。")
    inserted_a, contras_a = persist_chunk_facts(
        conn,
        client_id="cli-A",
        v2_document_id="doc-1",
        v2_chunk_id="chunk-1",
        facts=facts_a,
    )
    assert inserted_a >= 2
    assert contras_a == 0

    # 第二个 chunk 改写预算
    facts_b = extract_facts_from_chunk("客户的预算是 30 万元。")
    inserted_b, contras_b = persist_chunk_facts(
        conn,
        client_id="cli-A",
        v2_document_id="doc-1",
        v2_chunk_id="chunk-2",
        facts=facts_b,
    )
    assert inserted_b == 1
    assert contras_b == 1  # 应当与 chunk-1 的 50 万触发一次矛盾


@pytest.mark.unit
def test_dismiss_contradiction(conn: sqlite3.Connection) -> None:
    fact_old = AtomicFact("客户", "预算", "50 万元", "50万元", 0.8)
    fact_new = AtomicFact("客户", "预算", "30 万元", "30万元", 0.8)
    old_id = insert_fact(conn, client_id="cli-A", fact=fact_old)
    new_id = insert_fact(conn, client_id="cli-A", fact=fact_new)
    detect_and_record_for_fact(
        conn, client_id="cli-A", new_fact_id=new_id, fact=fact_new
    )
    pending, total = list_contradictions(conn, client_id="cli-A")
    assert total == 1
    contra_id = str(pending[0]["id"])

    update_review_status(
        conn,
        contradiction_id=contra_id,
        review_status="dismissed",
        resolution_note="客户调整了预算，新值正确",
        reviewed_by="user-1",
    )
    # pending 池清空
    _, after = list_contradictions(conn, client_id="cli-A", review_status="pending")
    assert after == 0
    # dismissed 池有 1 条
    _, dismissed = list_contradictions(conn, client_id="cli-A", review_status="dismissed")
    assert dismissed == 1
