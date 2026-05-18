"""字典权威属性包 — 注入 chat raw_evidence_pack 前置.

设计目标: 在 chat 生成回答之前, 把客户字典里 verification_status='verified'
的属性整理成结构化文本块, 让 LLM 优先引用这些经过人审的金标准数据, 防止
在"具体数字 / 姓名 / 日期"等关键事实上编造或选错值。

机制:
- 这是 P0 项目画像的延伸: glossary_relations / risk_signals / commitments
  装的是"边/风险/承诺", glossary_attributes 装的是"term.属性 = 值"。
- 经人审的属性带有 scope + as_of_date, 用于区分"项目累计 vs 机构当前"、
  "2022 底 vs 2025-6" 这类口径冲突。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerifiedAttribute:
    term: str
    attribute_name: str
    value_text: str
    value_unit: str
    scope: str
    as_of_date: str | None
    source_evidence: str


def fetch_verified_attributes(db: Any, client_id: str) -> list[VerifiedAttribute]:
    """读取一个客户所有 verified 字典属性, 按 term/attr 字典序排."""
    rows = db.fetchall(
        """SELECT cg.term, ga.attribute_name, ga.value_text, ga.value_unit,
                  ga.scope, ga.as_of_date, ga.source_evidence
           FROM glossary_attributes ga
           JOIN client_glossary cg ON cg.id = ga.term_id
           WHERE ga.client_id = ?
             AND ga.verification_status = 'verified'
           ORDER BY cg.term ASC, ga.attribute_name ASC""",
        (client_id,),
    )
    return [
        VerifiedAttribute(
            term=r["term"],
            attribute_name=r["attribute_name"],
            value_text=r["value_text"],
            value_unit=r["value_unit"] or "",
            scope=r["scope"] or "",
            as_of_date=r["as_of_date"],
            source_evidence=r["source_evidence"] or "",
        )
        for r in rows
    ]


def build_verified_attributes_pack(db: Any, client_id: str) -> str:
    """构造可注入 chat raw_evidence_pack 的 verified attributes 段."""
    attrs = fetch_verified_attributes(db, client_id)
    if not attrs:
        return ""

    lines: list[str] = []
    lines.append("# ⭐⭐ 字典权威数据档案 (人工审核 verified, 最高引用优先级)")
    lines.append("")
    lines.append("以下是该客户字典已经过人工审核 (verification_status=verified) 的关键属性。")
    lines.append("在回答涉及具体数字 / 姓名 / 日期 / 金额 / 地点 / 评估等级等关键事实时:")
    lines.append("")
    lines.append("1. **必须优先引用本档案的值**, 不得用原始文档中的其它候选值覆盖本档案。")
    lines.append("2. 若同一字段在不同 `scope` 下有多条 verified 值 (例: 覆盖范围-机构当前 vs 覆盖范围-项目累计),")
    lines.append("   **必须同时给出两个值并显式标明 scope**, 不要合并、不要互相替代。")
    lines.append("3. 若本档案未收录该字段, 但原始资料中有, 可引用资料中的值并标 [资料 N];")
    lines.append("   若原始资料也没有, 必须明确写「档案中暂未收录该字段」, 严禁编造。")
    lines.append("4. 数据带 `@日期`, 表示 verified 的时间截止点。回答时建议带上日期范围, 例 '截至 2025-6'。")
    lines.append("")

    # 按 term 分组列出
    by_term: dict[str, list[VerifiedAttribute]] = {}
    for a in attrs:
        by_term.setdefault(a.term, []).append(a)

    for term, items in by_term.items():
        lines.append(f"## {term}")
        for a in items:
            scope_part = f"  [scope={a.scope}]" if a.scope else ""
            asof_part = f"  @{a.as_of_date}" if a.as_of_date else ""
            lines.append(f"- **{a.attribute_name}** = {a.value_text}{scope_part}{asof_part}")
            if a.source_evidence:
                lines.append(f"  · 依据: {a.source_evidence}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("(以上为字典权威数据档案结束, 以下是原始证据资料包)")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)
