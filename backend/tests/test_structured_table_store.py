"""structured_tables 存储 + 查询测试（Phase 1）。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.structured_table_parser import ParsedSheet
from app.services.structured_table_store import (
    detect_semantic_role,
    find_tables_by_role,
    get_table,
    hint_roles_from_question,
    list_tables,
    table_to_dataframe,
    upsert_table_from_parsed_sheet,
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
INSERT INTO v2_documents (id) VALUES ('doc-2');
"""


def _make_sheet(name: str, headers: list[str], rows: list[dict], col_types: dict | None = None) -> ParsedSheet:
    return ParsedSheet(
        sheet_name=name,
        headers=headers,
        rows=rows,
        column_types=col_types or {},
        markdown="",
        row_count=len(rows),
        column_count=len(headers),
        notes=[],
    )


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


# ---- semantic_role 识别 -------------------------------------------------


@pytest.mark.unit
def test_detect_budget_role() -> None:
    role, conf = detect_semantic_role(["项目类别", "预算金额", "已花费", "剩余"])
    assert role == "budget"
    assert conf > 0.5


@pytest.mark.unit
def test_detect_beneficiary_list_role() -> None:
    role, conf = detect_semantic_role(["姓名", "性别", "年龄", "地区", "受助类型"])
    assert role == "beneficiary_list"
    assert conf > 0.7


@pytest.mark.unit
def test_detect_kpi_role() -> None:
    role, _ = detect_semantic_role(["指标", "目标", "完成率"])
    assert role == "kpi"


@pytest.mark.unit
def test_detect_unknown_role() -> None:
    role, conf = detect_semantic_role(["A", "B", "C"])
    assert role == "unknown"
    assert conf == 0.0


# ---- upsert + 查询 -------------------------------------------------------


@pytest.mark.unit
def test_upsert_table_round_trip(conn) -> None:
    sheet = _make_sheet(
        "Q1预算",
        ["项目", "预算金额", "已花费"],
        [
            {"项目": "调研", "预算金额": 50000, "已花费": 32000},
            {"项目": "培训", "预算金额": 30000, "已花费": 12000},
        ],
        col_types={"项目": "text", "预算金额": "number", "已花费": "number"},
    )
    table_id = upsert_table_from_parsed_sheet(
        conn,
        client_id="cli-A",
        v2_document_id="doc-1",
        knowledge_document_id=None,
        sheet_index=0,
        parsed=sheet,
    )
    fetched = get_table(conn, table_id=table_id)
    assert fetched is not None
    assert fetched.sheet_name == "Q1预算"
    assert fetched.semantic_role == "budget"
    assert fetched.row_count == 2
    assert fetched.rows[0]["项目"] == "调研"
    assert fetched.rows[0]["预算金额"] == 50000


@pytest.mark.unit
def test_upsert_is_idempotent_on_same_doc_sheet(conn) -> None:
    """同 v2_document_id + sheet_name 第二次 upsert 不创建新行，更新内容。"""
    sheet_v1 = _make_sheet("数据", ["A", "B"], [{"A": 1, "B": 2}])
    sheet_v2 = _make_sheet("数据", ["A", "B"], [{"A": 3, "B": 4}, {"A": 5, "B": 6}])

    upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0, parsed=sheet_v1,
    )
    upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0, parsed=sheet_v2,
    )
    tables, total = list_tables(conn, client_id="cli-A")
    assert total == 1
    assert tables[0].row_count == 2
    assert tables[0].rows[0]["A"] == 3


@pytest.mark.unit
def test_find_tables_by_role(conn) -> None:
    upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0,
        parsed=_make_sheet("预算", ["项目", "预算金额"], [{"项目": "A", "预算金额": 1000}]),
    )
    upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-2",
        knowledge_document_id=None, sheet_index=0,
        parsed=_make_sheet("受益人", ["姓名", "年龄", "受助类型"], [{"姓名": "张三", "年龄": 8, "受助类型": "教育"}]),
    )
    budgets = find_tables_by_role(conn, client_id="cli-A", roles=["budget"])
    assert len(budgets) == 1
    assert budgets[0].sheet_name == "预算"

    mixed = find_tables_by_role(conn, client_id="cli-A", roles=["budget", "beneficiary_list"])
    assert len(mixed) == 2


@pytest.mark.unit
def test_list_tables_filters_by_client(conn) -> None:
    conn.execute("INSERT INTO clients (id) VALUES ('cli-B')")
    upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0,
        parsed=_make_sheet("A 的预算", ["项目", "预算"], [{"项目": "x", "预算": 100}]),
    )
    upsert_table_from_parsed_sheet(
        conn, client_id="cli-B", v2_document_id="doc-2",
        knowledge_document_id=None, sheet_index=0,
        parsed=_make_sheet("B 的预算", ["项目", "预算"], [{"项目": "y", "预算": 200}]),
    )
    a_tables, _ = list_tables(conn, client_id="cli-A")
    b_tables, _ = list_tables(conn, client_id="cli-B")
    assert {t.sheet_name for t in a_tables} == {"A 的预算"}
    assert {t.sheet_name for t in b_tables} == {"B 的预算"}


# ---- 问题路由 -----------------------------------------------------------


@pytest.mark.unit
def test_hint_roles_from_question_budget() -> None:
    roles = hint_roles_from_question("A组织 Q1 预算总额是多少？")
    assert "budget" in roles


@pytest.mark.unit
def test_hint_roles_from_question_beneficiary() -> None:
    roles = hint_roles_from_question("受益人有多少？地区分布如何？")
    assert "beneficiary_list" in roles


@pytest.mark.unit
def test_hint_roles_from_question_kpi() -> None:
    roles = hint_roles_from_question("Q1 KPI 完成率怎么样？")
    assert "kpi" in roles


@pytest.mark.unit
def test_hint_roles_from_question_no_hint() -> None:
    assert hint_roles_from_question("今天天气真好") == []


# ---- DataFrame 转换 -----------------------------------------------------


@pytest.mark.unit
def test_table_to_dataframe_aggregation(conn) -> None:
    """DataFrame 转换 + 简单聚合：SUM(预算金额) 应当精确。"""
    sheet = _make_sheet(
        "预算",
        ["项目", "预算金额", "已花费"],
        [
            {"项目": "调研", "预算金额": 50000, "已花费": 32000},
            {"项目": "受益人活动", "预算金额": 80000, "已花费": 45000},
            {"项目": "培训费", "预算金额": 30000, "已花费": 12000},
        ],
        col_types={"项目": "text", "预算金额": "number", "已花费": "number"},
    )
    table_id = upsert_table_from_parsed_sheet(
        conn, client_id="cli-A", v2_document_id="doc-1",
        knowledge_document_id=None, sheet_index=0, parsed=sheet,
    )
    fetched = get_table(conn, table_id=table_id)
    df = table_to_dataframe(fetched)
    assert df["预算金额"].sum() == 160000
    assert df["已花费"].sum() == 89000
    # 计算执行率
    df["执行率"] = df["已花费"] / df["预算金额"]
    # 实际：调研 32000/50000=0.64，受益人活动 45000/80000=0.5625，培训 12000/30000=0.4
    # > 0.6 的只有调研一项
    high_exec = df[df["执行率"] > 0.6]
    assert len(high_exec) == 1
    assert high_exec.iloc[0]["项目"] == "调研"
