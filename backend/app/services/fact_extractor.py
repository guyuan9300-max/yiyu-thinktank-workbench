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
# attribute 收紧到 2-5 字 —— 真实业务属性几乎不超过 5 字（预算/计划时间/
# 主要负责人 等），>5 字基本是 regex 误抓了句子中的动词短语。
_ATTRIBUTE = r"[一-龥A-Za-z0-9]{2,5}"
_VALUE = r"[^，。；\n]{1,40}?"

# attribute 末尾不能是这些字符 —— 否则会抓到"专业关系才"、"学员认"、"升级不"
# 这种把后面句子的虚词吃进 attribute 的错误。
# 这些字 = 副词/否定/连接词/动词后缀，不应作为名词属性的末字。
_ATTRIBUTE_TRAIL_STOPCHARS: Final[frozenset[str]] = frozenset(
    "才也不认正将没否已又都就会能可必应必须就要在还连而且但或乃从对被让使"
    "去出到起开来下上"  # 动词补语
)

# attribute 首字不能是这些（副词/限定词，attribute 应当是名词起头）
_ATTRIBUTE_LEAD_STOPCHARS: Final[frozenset[str]] = frozenset(
    "已正将又才也都就全凡或若连而但所"
)

# attribute 整体不能是常见动词短语（"建立起良好"这种 subject 的尾巴）
_ATTRIBUTE_BLACKLIST: Final[frozenset[str]] = frozenset({
    "建立", "建立起", "建立良好", "建立起良好",
    "做好", "尊重", "他们", "肯定", "已经",
    "释放", "全都", "全部",
})

# 主要的 "X 的 Y 是 Z" 模板
_FACT_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?P<subject>{_SUBJECT})的(?P<attribute>{_ATTRIBUTE})(?:是|为|约|达到|定在|为)(?P<value>{_VALUE})(?=[，。；\n]|$)"
)


def _is_valid_attribute(attribute: str) -> bool:
    """post-filter：拒绝末尾是虚词/否定/连接词的 attribute。

    例：
    - "专业关系才" → False（末字 "才"）
    - "学员认" → False（末字 "认"）
    - "升级不" → False（末字 "不"）
    - "已经" → False（黑名单）
    - "释放出去" → False（末字 "去"）
    - "预算" → True
    - "计划时间" → True
    """
    if not attribute or len(attribute.strip()) < 2:
        return False
    cleaned = attribute.strip()
    if cleaned in _ATTRIBUTE_BLACKLIST:
        return False
    if cleaned[-1] in _ATTRIBUTE_TRAIL_STOPCHARS:
        return False
    if cleaned[0] in _ATTRIBUTE_LEAD_STOPCHARS:
        return False
    # attribute 不应当含"是/为"（这些是连接动词）
    if "是" in cleaned or "为" in cleaned:
        return False
    return True


def _is_valid_value(value: str) -> bool:
    """post-filter：拒绝空白 / 全标点 / 长度异常的值。"""
    if not value:
        return False
    cleaned = value.strip()
    if len(cleaned) < 1 or len(cleaned) > 60:
        return False
    # 全是标点/空白
    if not any(c.isalnum() or "一" <= c <= "鿿" for c in cleaned):
        return False
    return True

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
        # 严格 post-validation 拒绝噪音：
        # - attribute 末尾是虚词/否定/连接词（"才/认/不/正/将/又/也/都/就..."）
        # - value 全标点/空白/过长
        # - attribute 在黑名单里（"建立起良好"这种 subject 残尾）
        if not _is_valid_attribute(attribute):
            continue
        if not _is_valid_value(value_raw):
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
