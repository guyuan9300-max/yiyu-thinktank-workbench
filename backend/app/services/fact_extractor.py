"""原子事实抽取（迭代 6）。

从 chunk 文本里识别 (subject, attribute, value) 三元组，例如：
- "客户的预算是 50 万元" → ("客户", "预算", "50万元")
- "项目 X 的上线时间定在 6 月 1 日" → ("项目 X", "上线时间", "2026-06-01")
- "公司位于北京" → ("公司", "位置", "北京")

与 relation_extractor 的区别：
- relation_extractor：实体之间的关系（两个 entity 节点）
- fact_extractor：实体的属性 = 值（值通常是数字/日期/状态/文本）

设计：规则层为主，覆盖中文最高频的"X 的 Y 是 Z"模板。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AtomicFact:
    """单次抽取的原子事实。"""

    subject_text: str
    attribute: str
    value_text: str
    value_normalized: str
    confidence: float
    evidence_text: str = ""


# 主体 + "的" + 属性 + "是/为/在/约/达到" + 值
_SUBJECT = r"[一-龥A-Za-z0-9·]{2,15}?"
_ATTRIBUTE = r"[一-龥A-Za-z0-9]{2,8}"
_VALUE = r"[^，。；\n]{1,40}?"

# 主要的 "X 的 Y 是 Z" 模板
_FACT_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?P<subject>{_SUBJECT})的(?P<attribute>{_ATTRIBUTE})(?:是|为|约|达到|定在|为)(?P<value>{_VALUE})(?=[，。；\n]|$)"
)

# "X 位于/位置在 Y"
_LOCATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?P<subject>{_SUBJECT})\s*(?:位于|总部在|注册地在|位置在|设在)\s*(?P<value>{_VALUE})(?=[，。；\n]|$)"
)

# "X 计划在/将在 时间 Y"
_PLAN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?P<subject>{_SUBJECT})\s*(?:计划在|将在|预计在|定于|预计于|拟于)\s*(?P<value>{_VALUE})(?:上线|发布|启动|完成|交付)"
)


_AMOUNT_NORMALIZE_RE = re.compile(r"[\s,，]")


def _normalize_value(raw_value: str, attribute: str) -> str:
    """把值归一化，便于 contradiction 比对。

    - 金额：去空格/逗号
    - 其他：保留原始 strip
    """
    cleaned = raw_value.strip()
    if attribute in {"预算", "预算额", "金额", "营收", "成本", "费用", "工资", "薪资"}:
        cleaned = _AMOUNT_NORMALIZE_RE.sub("", cleaned)
    return cleaned


def extract_facts_from_chunk(chunk_text: str) -> list[AtomicFact]:
    """抽取一个 chunk 里的原子事实。"""
    if not chunk_text or not chunk_text.strip():
        return []
    seen: set[tuple[str, str, str]] = set()
    out: list[AtomicFact] = []

    # 1. "X 的 Y 是 Z" 模板
    for match in _FACT_PATTERN.finditer(chunk_text):
        subject = match.group("subject").strip()
        attribute = match.group("attribute").strip()
        value_raw = match.group("value").strip()
        if len(subject) < 2 or len(attribute) < 2 or len(value_raw) < 1:
            continue
        value_norm = _normalize_value(value_raw, attribute)
        key = (subject, attribute, value_norm)
        if key in seen:
            continue
        seen.add(key)
        evidence = chunk_text[max(0, match.start() - 5): min(len(chunk_text), match.end() + 5)]
        out.append(
            AtomicFact(
                subject_text=subject,
                attribute=attribute,
                value_text=value_raw,
                value_normalized=value_norm,
                confidence=0.8,
                evidence_text=evidence.strip(),
            )
        )

    # 2. "X 位于 Y" 模板
    for match in _LOCATION_PATTERN.finditer(chunk_text):
        subject = match.group("subject").strip()
        value_raw = match.group("value").strip()
        if len(subject) < 2 or len(value_raw) < 1:
            continue
        key = (subject, "位置", value_raw)
        if key in seen:
            continue
        seen.add(key)
        evidence = chunk_text[max(0, match.start() - 5): min(len(chunk_text), match.end() + 5)]
        out.append(
            AtomicFact(
                subject_text=subject,
                attribute="位置",
                value_text=value_raw,
                value_normalized=value_raw,
                confidence=0.85,
                evidence_text=evidence.strip(),
            )
        )

    # 3. "X 计划在 Y" 模板
    for match in _PLAN_PATTERN.finditer(chunk_text):
        subject = match.group("subject").strip()
        value_raw = match.group("value").strip()
        if len(subject) < 2 or len(value_raw) < 1:
            continue
        key = (subject, "计划时间", value_raw)
        if key in seen:
            continue
        seen.add(key)
        evidence = chunk_text[max(0, match.start() - 5): min(len(chunk_text), match.end() + 5)]
        out.append(
            AtomicFact(
                subject_text=subject,
                attribute="计划时间",
                value_text=value_raw,
                value_normalized=value_raw,
                confidence=0.75,
                evidence_text=evidence.strip(),
            )
        )

    return out


__all__ = ["AtomicFact", "extract_facts_from_chunk"]
