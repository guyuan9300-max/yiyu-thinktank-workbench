"""结构化表格查询路径测试（Phase 1）。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.structured_table_parser import ParsedSheet
from app.services.structured_table_store import upsert_table_from_parsed_sheet
from app.services.structured_query import (
    detect_intent,
    query_structured_tables,
)


SCHEMA = """
CREATE TABLE clients (id TEXT PRIMARY KEY);
CREATE TABLE v2_documents (id TEXT PRIMARY KEY);
CREATE TABLE structured_tables (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    v2_document_id TEXT NOT NULL,
    knowledge_document_id TEXT,
    sheet_name TEXT NOT NULL,
    sheet_index INTEGER NOT NULL DEFAULT 0,
    headers_json TEXT NOT NULL DEFAULT '[]',
    column_types_json TEXT NOT NULL DEFAULT '{}',
    rows_json TEXT NOT NULL DEFAULT '[]',
    row_count INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER NOT NULL DEFAULT 0,
    semantic_role TEXT NOT NULL DEFAULT 'unknown',
    semantic_confidence REAL NOT NULL DEFAULT 0.0,
    parse_notes_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_structured_tables_doc_sheet
    ON structured_tables(v2_document_id, sheet_name);
INSERT INTO clients (id) VALUES ('cli-A');
INSERT INTO v2_documents (id) VALUES ('doc-1');
"""


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _seed_budget(conn) -> str:
    sheet = ParsedSheet(
        sheet_name="Q1预算",
        headers=["项目", "预算金额", "已花费"],
        rows=[
            {"项目": "调研", "预算金额": 50000, "已花费": 32000},
            {"项目": "受益人活动", "预算金额": 80000, "已花费": 45000},
            {"项目": "培训", "预算金额": 30000, "已花费": 35000},  # 超支
        ],
        column_types={"项目": "text", "预算金额": "number", "已花费": "number"},
        markdown="",
        row_count=3,
        column_count=3,
        notes=[],
    )
    return upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0, parsed=sheet,
    )


# ---- intent 识别 ---------------------------------------------------------


@pytest.mark.unit
def test_detect_intent_sum() -> None:
    assert detect_intent("A组织 Q1 预算总额是多少？") == "sum"
    assert detect_intent("把这些预算合计一下") == "sum"


@pytest.mark.unit
def test_detect_intent_execution_rate() -> None:
    assert detect_intent("Q1 预算执行率怎么样") == "execution_rate"
    assert detect_intent("看看完成率") == "execution_rate"


@pytest.mark.unit
def test_detect_intent_overspend() -> None:
    assert detect_intent("有哪些项目超支了？") == "overspend"


@pytest.mark.unit
def test_detect_intent_count() -> None:
    assert detect_intent("受益人有多少人？") == "count"


@pytest.mark.unit
def test_detect_intent_default_list() -> None:
    assert detect_intent("看看预算表") == "list"


# ---- 端到端 sum --------------------------------------------------------


@pytest.mark.unit
def test_query_sum_returns_exact_total(conn) -> None:
    _seed_budget(conn)
    results = query_structured_tables(conn, client_id="cli-A", question="A组织 Q1 预算总额是多少？")
    assert len(results) == 1
    r = results[0]
    assert r.intent == "sum"
    # 50000+80000+30000 = 160000
    assert "160,000" in r.summary
    assert r.sheet_name == "Q1预算"


@pytest.mark.unit
def test_query_overspend_finds_overspent_items(conn) -> None:
    _seed_budget(conn)
    results = query_structured_tables(conn, client_id="cli-A", question="哪些项目超支了？")
    assert len(results) == 1
    r = results[0]
    assert r.intent == "overspend"
    # 培训 35000/30000 = 117%
    assert "培训" in r.summary
    assert "117%" in r.summary


@pytest.mark.unit
def test_query_execution_rate_lists_high_exec(conn) -> None:
    _seed_budget(conn)
    results = query_structured_tables(conn, client_id="cli-A", question="预算执行率怎么样？")
    assert len(results) == 1
    r = results[0]
    assert r.intent == "execution_rate"
    # 培训 117% 是 ≥80% 的
    assert "培训" in r.summary


@pytest.mark.unit
def test_query_returns_empty_when_question_unrelated(conn) -> None:
    _seed_budget(conn)
    results = query_structured_tables(conn, client_id="cli-A", question="今天天气怎么样？")
    assert results == []


@pytest.mark.unit
def test_query_returns_empty_when_no_matching_tables(conn) -> None:
    # 没 seed 任何表
    results = query_structured_tables(conn, client_id="cli-A", question="预算总额多少？")
    assert results == []


@pytest.mark.unit
def test_query_isolates_by_client(conn) -> None:
    """跨客户的表不会出现在查询结果里。"""
    conn.execute("INSERT INTO clients (id) VALUES ('cli-B')")
    conn.execute("INSERT INTO v2_documents (id) VALUES ('doc-2')")
    _seed_budget(conn)  # cli-A
    # cli-B 没数据
    results = query_structured_tables(conn, client_id="cli-B", question="预算总额多少？")
    assert results == []
