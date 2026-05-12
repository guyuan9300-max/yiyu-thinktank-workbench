"""structured_tables 表的存储 + 查询（Phase 1）。

每个 ParsedSheet 入库为一行 structured_table，rows 序列化为 JSON。
检索时按 client_id 拉所有相关表，在内存里做 pandas 计算（小表性能 OK）。

semantic_role 启发式（Phase 1 规则层 + 列名匹配）：
- budget：headers 含 "预算/金额/经费"
- beneficiary_list：headers 含 "姓名/性别/年龄/受助"
- donation_record：headers 含 "捐赠/捐助/捐方"
- kpi：headers 含 "指标/KPI/目标/完成率"
- schedule：headers 含 "时间/日期/排期/截止"
- project_value：headers 含 "项目/产出/影响"
- unknown：其他
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.structured_table_parser import ParsedSheet

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- 语义角色识别（规则层） ---------------------------------------------


_ROLE_KEYWORDS: dict[str, list[str]] = {
    "budget": ["预算", "金额", "经费", "费用", "支出", "已花费", "剩余", "拨款"],
    "beneficiary_list": ["姓名", "性别", "年龄", "受助", "受益", "学员", "学生", "联系电话", "地区"],
    "donation_record": ["捐赠", "捐助", "捐方", "捐款", "募捐", "募款", "donor", "donation"],
    "kpi": ["指标", "KPI", "目标", "完成率", "达成率", "执行率", "增长率", "覆盖率"],
    "schedule": ["开始时间", "截止时间", "排期", "里程碑", "deadline", "due"],
    "project_value": ["项目代码", "项目名", "项目编号", "影响力", "产出", "outcome", "成果"],
}


def detect_semantic_role(headers: list[str]) -> tuple[str, float]:
    """按列名命中数量返回 (role, confidence)。

    无任何命中时返回 ("unknown", 0.0)。规则层粗筛，未来可叠加 LLM。
    """
    lowered = [h.lower() for h in headers]
    scores: dict[str, int] = {}
    for role, keywords in _ROLE_KEYWORDS.items():
        hits = 0
        for kw in keywords:
            kw_l = kw.lower()
            if any(kw_l in h for h in lowered):
                hits += 1
        if hits:
            scores[role] = hits
    if not scores:
        return ("unknown", 0.0)
    role, top_hits = max(scores.items(), key=lambda kv: kv[1])
    # 简单 confidence：命中越多越高，上限 1.0
    confidence = min(0.5 + 0.15 * top_hits, 1.0)
    return (role, confidence)


# ---- 类型 ----------------------------------------------------------------


@dataclass(frozen=True)
class StructuredTableRow:
    """从 structured_tables SELECT 出的一行（只读）。"""

    id: str
    client_id: str
    v2_document_id: str
    knowledge_document_id: str | None
    sheet_name: str
    sheet_index: int
    headers: list[str]
    column_types: dict[str, str]
    rows: list[dict[str, Any]]
    row_count: int
    column_count: int
    semantic_role: str
    semantic_confidence: float
    parse_notes: list[str]
    created_at: str


def _row_to_record(row: sqlite3.Row) -> StructuredTableRow:
    return StructuredTableRow(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        v2_document_id=str(row["v2_document_id"]),
        knowledge_document_id=str(row["knowledge_document_id"] or "") or None,
        sheet_name=str(row["sheet_name"]),
        sheet_index=int(row["sheet_index"] or 0),
        headers=json.loads(row["headers_json"] or "[]"),
        column_types=json.loads(row["column_types_json"] or "{}"),
        rows=json.loads(row["rows_json"] or "[]"),
        row_count=int(row["row_count"] or 0),
        column_count=int(row["column_count"] or 0),
        semantic_role=str(row["semantic_role"] or "unknown"),
        semantic_confidence=float(row["semantic_confidence"] or 0.0),
        parse_notes=json.loads(row["parse_notes_json"] or "[]"),
        created_at=str(row["created_at"] or ""),
    )


# ---- 写入 ----------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    """把行数据里的 datetime / Decimal 等转成 JSON 可序列化值。"""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def upsert_table_from_parsed_sheet(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    v2_document_id: str,
    knowledge_document_id: str | None,
    sheet_index: int,
    parsed: ParsedSheet,
    now: str | None = None,
) -> str:
    """从 ParsedSheet 写入一行 structured_tables。

    UNIQUE(v2_document_id, sheet_name) 保证幂等——重导同一文件不会产生
    两份记录，会 REPLACE 旧的。
    """
    timestamp = now or _now_iso()
    role, confidence = detect_semantic_role(parsed.headers)
    json_rows = [
        {h: _to_jsonable(row.get(h)) for h in parsed.headers}
        for row in parsed.rows
    ]
    table_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO structured_tables (
            id, client_id, v2_document_id, knowledge_document_id,
            sheet_name, sheet_index, headers_json, column_types_json,
            rows_json, row_count, column_count, semantic_role,
            semantic_confidence, parse_notes_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(v2_document_id, sheet_name) DO UPDATE SET
            headers_json = excluded.headers_json,
            column_types_json = excluded.column_types_json,
            rows_json = excluded.rows_json,
            row_count = excluded.row_count,
            column_count = excluded.column_count,
            semantic_role = excluded.semantic_role,
            semantic_confidence = excluded.semantic_confidence,
            parse_notes_json = excluded.parse_notes_json,
            updated_at = excluded.updated_at
        """,
        (
            table_id,
            client_id,
            v2_document_id,
            knowledge_document_id or "",
            parsed.sheet_name,
            sheet_index,
            json.dumps(parsed.headers, ensure_ascii=False),
            json.dumps(parsed.column_types, ensure_ascii=False),
            json.dumps(json_rows, ensure_ascii=False),
            parsed.row_count,
            parsed.column_count,
            role,
            confidence,
            json.dumps(parsed.notes, ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )
    # 拿回真正落库的 id（可能是 INSERT 新 id，也可能是 ON CONFLICT 后的旧 id）
    existing = conn.execute(
        "SELECT id FROM structured_tables WHERE v2_document_id = ? AND sheet_name = ?",
        (v2_document_id, parsed.sheet_name),
    ).fetchone()
    return str(existing["id"]) if existing else table_id


# ---- 查询 ----------------------------------------------------------------


def list_tables(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    semantic_role: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[StructuredTableRow], int]:
    where = ["client_id = ?"]
    params: list[object] = [client_id]
    if semantic_role:
        where.append("semantic_role = ?")
        params.append(semantic_role)
    where_clause = " AND ".join(where)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM structured_tables WHERE {where_clause}",
        tuple(params),
    ).fetchone()
    total = int(count_row["n"] or 0) if count_row else 0

    rows = conn.execute(
        f"SELECT * FROM structured_tables WHERE {where_clause} "
        "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_row_to_record(r) for r in rows], total


def get_table(conn: sqlite3.Connection, *, table_id: str) -> StructuredTableRow | None:
    row = conn.execute("SELECT * FROM structured_tables WHERE id = ?", (table_id,)).fetchone()
    return _row_to_record(row) if row else None


def find_tables_by_role(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    roles: list[str],
) -> list[StructuredTableRow]:
    """检索时用：拉所有命中 roles 的表。"""
    if not roles:
        return []
    placeholders = ",".join("?" * len(roles))
    rows = conn.execute(
        f"SELECT * FROM structured_tables "
        f"WHERE client_id = ? AND semantic_role IN ({placeholders}) "
        "ORDER BY updated_at DESC",
        (client_id, *roles),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


# ---- 查询路由（轻量） ----------------------------------------------------

# 关键词 → 候选 role 映射；用户提问含这些词时检索对应 role 的表
_QUESTION_ROLE_HINTS: dict[str, list[str]] = {
    "预算": ["budget"],
    "金额": ["budget", "donation_record"],
    "执行率": ["budget", "kpi"],
    "超支": ["budget"],
    "受益": ["beneficiary_list", "project_value"],
    "受助": ["beneficiary_list"],
    "捐赠": ["donation_record"],
    "捐款": ["donation_record"],
    "KPI": ["kpi"],
    "指标": ["kpi"],
    "完成率": ["kpi"],
    "项目": ["project_value", "budget"],
    "进度": ["schedule", "kpi"],
    "截止": ["schedule"],
}


def hint_roles_from_question(question: str) -> list[str]:
    """从问题文本启发式抽取相关 semantic_role 列表。

    Phase 1 简版；Phase 2 可换 LLM 路由。
    """
    if not question or not question.strip():
        return []
    candidates: set[str] = set()
    for keyword, roles in _QUESTION_ROLE_HINTS.items():
        if keyword in question:
            for r in roles:
                candidates.add(r)
    return sorted(candidates)


# ---- pandas 计算包装（Phase 1 最小版） -----------------------------------


def table_to_dataframe(table: StructuredTableRow):
    """把一个 structured_table 转成 pandas DataFrame，供计算路径使用。

    返回 DataFrame 对象（运行时 import pandas，避免单元测试也强制依赖）。
    """
    import pandas as pd  # noqa: PLC0415

    df = pd.DataFrame(table.rows)
    # 按 column_types 转 numeric 列
    for col, col_type in table.column_types.items():
        if col not in df.columns:
            continue
        if col_type == "number":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


__all__ = [
    "StructuredTableRow",
    "detect_semantic_role",
    "find_tables_by_role",
    "get_table",
    "hint_roles_from_question",
    "list_tables",
    "table_to_dataframe",
    "upsert_table_from_parsed_sheet",
]
