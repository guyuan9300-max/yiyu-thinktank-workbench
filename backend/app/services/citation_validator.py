"""引用校验器（P-C）— 解析 LLM 输出里的字典 cite，物理性校验。

格式：`[📚 term.attribute_name]`

解析规则：
1. 找全文所有 cite 标记
2. 每个 (term, attribute) → 查 client_glossary_attributes verified
3. 找到 → 保留 cite，附加权威性标记
4. 找不到 → 替换为「⚠️ 引用失效（X.Y 不在字典 verified 列表）」

这是「物理性防编造」的最后一环 — LLM 编造的 cite 会被替换，无法靠"看起来合理"骗过用户。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# `[📚 term.attribute_name]` 或 `[📚 term · attribute_name]` 两种格式都支持
_CITE_PATTERN = re.compile(
    r"\[📚\s*([^\]·.]+?)\s*[·.]\s*([^\]]+?)\]",
    re.UNICODE,
)


@dataclass(frozen=True)
class CitationCheck:
    raw: str  # 原始引用文本，如 "[📚 缘救宝贝.项目启动时间]"
    term: str
    attribute_name: str
    valid: bool
    verified_value: str | None  # db 中 verified 的实际值（仅 valid 时有）
    verified_at: str | None
    as_of_date: str | None
    scope: str | None


def validate_citations(
    answer_text: str,
    db: Any,
    client_id: str,
) -> tuple[str, list[CitationCheck], dict[str, int]]:
    """解析 LLM 输出里的 cite 并校验。

    返回:
      - clean_text: 替换无效 cite 后的文本
      - checks: 所有 cite 的校验结果（含合法 + 不合法）
      - stats: {'total': N, 'valid': X, 'invalid': Y}
    """
    if not answer_text or "[📚" not in answer_text:
        return answer_text, [], {"total": 0, "valid": 0, "invalid": 0}

    checks: list[CitationCheck] = []
    invalid_replacements: list[tuple[str, str]] = []

    seen_keys: set[tuple[str, str]] = set()
    for match in _CITE_PATTERN.finditer(answer_text):
        raw = match.group(0)
        term = match.group(1).strip()
        attribute_name = match.group(2).strip()
        key = (term.lower(), attribute_name.lower())
        if key in seen_keys:
            continue  # 同一对 cite 重复出现只查一次
        seen_keys.add(key)

        # 查 db — 必须是该客户 + verified 状态
        row = db.fetchone(
            """SELECT ga.value_text, ga.verified_at, ga.as_of_date, ga.scope, ga.verification_status
               FROM glossary_attributes ga
               JOIN client_glossary cg ON cg.id = ga.term_id
               WHERE ga.client_id = ?
                 AND cg.term = ?
                 AND ga.attribute_name = ?
                 AND ga.verification_status = 'verified'
               LIMIT 1""",
            (client_id, term, attribute_name),
        )
        if row:
            checks.append(
                CitationCheck(
                    raw=raw,
                    term=term,
                    attribute_name=attribute_name,
                    valid=True,
                    verified_value=str(row["value_text"]),
                    verified_at=str(row["verified_at"]) if row["verified_at"] else None,
                    as_of_date=str(row["as_of_date"]) if row["as_of_date"] else None,
                    scope=str(row["scope"]) if row["scope"] else None,
                )
            )
        else:
            checks.append(
                CitationCheck(
                    raw=raw,
                    term=term,
                    attribute_name=attribute_name,
                    valid=False,
                    verified_value=None,
                    verified_at=None,
                    as_of_date=None,
                    scope=None,
                )
            )
            invalid_replacements.append(
                (raw, f"[⚠️ 引用失效：「{term}.{attribute_name}」不在字典 verified 列表，请在字典审核此项]")
            )

    # 替换无效引用
    clean_text = answer_text
    for old, new in invalid_replacements:
        clean_text = clean_text.replace(old, new)

    valid_count = sum(1 for c in checks if c.valid)
    invalid_count = sum(1 for c in checks if not c.valid)
    stats = {
        "total": len(checks),
        "valid": valid_count,
        "invalid": invalid_count,
    }
    return clean_text, checks, stats


__all__ = ["validate_citations", "CitationCheck"]
