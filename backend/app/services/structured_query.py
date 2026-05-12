"""结构化表格的查询路径（Phase 1）。

把用户问题路由到 structured_tables：
1. 用 hint_roles_from_question 找候选 role
2. 拉相关表
3. 按问题意图做基础计算（sum / count / mean / 执行率）
4. 返回结构化结果 + 渲染好的 markdown，供答案层引用

为什么不直接喂 LLM 整表：
- 减少 token 占用
- 精确数字（替代 LLM 的"约/大概"）
- 计算可追溯（每个结果带"我跑了这个聚合"）
"""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass

from app.services.structured_table_store import (
    StructuredTableRow,
    find_tables_by_role,
    hint_roles_from_question,
    table_to_dataframe,
)

logger = logging.getLogger(__name__)


# ---- 类型 ----------------------------------------------------------------


@dataclass(frozen=True)
class StructuredQueryResult:
    """单条结构化查询结果，供答案层作为 evidence 引用。"""

    table_id: str
    sheet_name: str
    semantic_role: str
    intent: str                # "list" | "sum" | "execution_rate" | "count"
    summary: str               # 一句话结论（含精确数字）
    markdown: str              # 详细 markdown（含数字、表格、计算说明）


# ---- 意图识别 ------------------------------------------------------------


_SUM_KEYWORDS = ("总额", "总和", "合计", "总计", "加起来")
_RATE_KEYWORDS = ("执行率", "完成率", "达成率", "占比")
_OVERSPEND_KEYWORDS = ("超支", "超出预算", "超过预算")
_COUNT_KEYWORDS = ("多少个", "几个", "多少人", "几人", "数量")


def detect_intent(question: str) -> str:
    """从问题文本识别计算意图。返回 'sum' / 'execution_rate' /
    'overspend' / 'count' / 'list'（默认）。"""
    if not question:
        return "list"
    q = question.strip()
    if any(kw in q for kw in _OVERSPEND_KEYWORDS):
        return "overspend"
    if any(kw in q for kw in _RATE_KEYWORDS):
        return "execution_rate"
    if any(kw in q for kw in _SUM_KEYWORDS):
        return "sum"
    if any(kw in q for kw in _COUNT_KEYWORDS):
        return "count"
    return "list"


# ---- 列识别 --------------------------------------------------------------


_BUDGET_AMOUNT_PATTERNS = ("预算", "金额", "费用")
_SPENT_PATTERNS = ("已花费", "支出", "已支出", "实际", "花费", "已使用")
_BENEFICIARY_PATTERNS = ("受益人", "人数", "学员数")


def _find_column(headers: list[str], patterns: tuple[str, ...]) -> str | None:
    for header in headers:
        for p in patterns:
            if p in header:
                return header
    return None


# ---- 计算 ----------------------------------------------------------------


def _query_budget_table(question: str, intent: str, table: StructuredTableRow) -> StructuredQueryResult | None:
    df = table_to_dataframe(table)
    amount_col = _find_column(table.headers, _BUDGET_AMOUNT_PATTERNS)
    spent_col = _find_column(table.headers, _SPENT_PATTERNS)

    if intent == "sum" and amount_col:
        total = float(df[amount_col].sum())
        summary = f"{table.sheet_name} 的「{amount_col}」总额：**{total:,.0f}**"
        markdown = f"## 计算结果\n\n{summary}\n\n基于表 「{table.sheet_name}」 · {len(df)} 行。"
        return StructuredQueryResult(
            table_id=table.id,
            sheet_name=table.sheet_name,
            semantic_role=table.semantic_role,
            intent="sum",
            summary=summary,
            markdown=markdown,
        )

    if intent in {"execution_rate", "overspend"} and amount_col and spent_col:
        df = df[df[amount_col].notna() & df[spent_col].notna()].copy()
        if df.empty:
            return None
        df["执行率"] = (df[spent_col] / df[amount_col]).round(4)
        if intent == "overspend":
            over = df[df["执行率"] > 1.0]
            if over.empty:
                summary = f"{table.sheet_name}：无超支项目。"
            else:
                items = ", ".join(
                    f"{row.iloc[0]}（{row['执行率']:.0%}）" for _, row in over.iterrows()
                )
                summary = f"{table.sheet_name} 超支项目 **{len(over)}** 个：{items}"
        else:
            high = df[df["执行率"] >= 0.8]
            if high.empty:
                summary = f"{table.sheet_name}：执行率均低于 80%。"
            else:
                items = ", ".join(
                    f"{row.iloc[0]}（{row['执行率']:.0%}）" for _, row in high.iterrows()
                )
                summary = (
                    f"{table.sheet_name} 执行率 ≥80% 的项目 **{len(high)}** 个："
                    f"{items}"
                )
        # 渲染明细 markdown
        df_preview = df[[df.columns[0], amount_col, spent_col, "执行率"]].copy()
        df_preview["执行率"] = df_preview["执行率"].apply(lambda v: f"{v:.0%}")
        markdown_lines = [
            "## 执行率计算",
            "",
            summary,
            "",
            "| " + " | ".join(df_preview.columns) + " |",
            "| " + " | ".join(["---"] * len(df_preview.columns)) + " |",
        ]
        for _, row in df_preview.iterrows():
            markdown_lines.append("| " + " | ".join(str(v) for v in row.tolist()) + " |")
        markdown = "\n".join(markdown_lines)
        return StructuredQueryResult(
            table_id=table.id,
            sheet_name=table.sheet_name,
            semantic_role=table.semantic_role,
            intent=intent,
            summary=summary,
            markdown=markdown,
        )

    return None


def _query_count_table(table: StructuredTableRow) -> StructuredQueryResult | None:
    summary = f"{table.sheet_name}：共 **{table.row_count}** 行"
    markdown = f"## 行数统计\n\n{summary}\n\n表头：{', '.join(table.headers)}"
    return StructuredQueryResult(
        table_id=table.id,
        sheet_name=table.sheet_name,
        semantic_role=table.semantic_role,
        intent="count",
        summary=summary,
        markdown=markdown,
    )


# ---- 主入口 --------------------------------------------------------------


def query_structured_tables(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    question: str,
    max_results: int = 5,
) -> list[StructuredQueryResult]:
    """对客户的 structured_tables 做问题级查询。

    流程：
    1. 用 hint_roles_from_question 找候选 role
    2. find_tables_by_role 拉对应表
    3. detect_intent 识别意图
    4. 每张候选表跑对应计算
    5. 返回最多 max_results 个结果

    Returns:
        StructuredQueryResult 列表（可能为空 = 问题不涉及结构化数据）
    """
    if not question or not question.strip():
        return []
    roles = hint_roles_from_question(question)
    if not roles:
        return []
    tables = find_tables_by_role(conn, client_id=client_id, roles=roles)
    if not tables:
        return []
    intent = detect_intent(question)
    results: list[StructuredQueryResult] = []
    for table in tables[:max_results]:
        try:
            if table.semantic_role == "budget":
                if intent in {"sum", "execution_rate", "overspend"}:
                    result = _query_budget_table(question, intent, table)
                    if result:
                        results.append(result)
                        continue
            if intent == "count":
                result = _query_count_table(table)
                if result:
                    results.append(result)
                    continue
            # 默认：列表型结果
            preview_rows = min(table.row_count, 10)
            summary = (
                f"{table.sheet_name}（{table.semantic_role}）· "
                f"{table.row_count} 行，前 {preview_rows} 行可读"
            )
            results.append(
                StructuredQueryResult(
                    table_id=table.id,
                    sheet_name=table.sheet_name,
                    semantic_role=table.semantic_role,
                    intent="list",
                    summary=summary,
                    markdown=f"## {table.sheet_name}\n\n{summary}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("structured query failed for table %s: %s", table.id, exc)
    return results


__all__ = [
    "StructuredQueryResult",
    "detect_intent",
    "query_structured_tables",
]
