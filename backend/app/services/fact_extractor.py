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

from app.services.text_normalizer import normalize_text

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
    "才也不认正将没否已又都就能可必应必须就要在还连而且但或乃从对被让使"
    "去到起开来下"  # 动词补语 (去除"会/出/上" — 这些常在名词中: 基金会/支出/线上)
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
    """post-filter：拒绝空白 / 全标点 / 长度异常 / 残尾虚词的值。"""
    if not value:
        return False
    cleaned = value.strip()
    # P1: value 长度收紧 60 → 25。真权威值（金额/日期/人名/地点）通常短，
    # >25 字基本是 regex 把整段口语吃进 value。
    if len(cleaned) < 1 or len(cleaned) > 25:
        return False
    # 全是标点/空白
    if not any(c.isalnum() or "一" <= c <= "鿿" for c in cleaned):
        return False
    # P1: value 含问号/感叹号 → 录音转写口语句残片，拒收。
    # 例：日慈"什么？对吧？他们在讨论什么话题" — 经典噪声
    if any(ch in cleaned for ch in "?？!！"):
        return False
    # P1: value 含中文逗号/分号/句号 → 切到了下一句，拒收（数字千分位 "," 已被 _normalize_value 处理过）
    if any(ch in cleaned for ch in "，；。"):
        return False
    # Codex 实测发现的尾巴噪声: 值是从原句尾巴切出来的虚词
    last_char = cleaned[-1]
    if last_char in "的吗了呢吧啊呀哇么哪？?不没未未必应该可能或也都还又":
        return False
    # 末字是连接词/虚词起头 — 说明 regex 切在了句子中间
    if last_char in "和与在为对于由":
        return False
    # value 含有"是/为/这是/那是" 起头说明 regex 把动词吃进 value 了
    if cleaned.startswith(("是", "为", "这是", "那是", "在", "为了", "由于")):
        return False
    return True


# Subject 不能是太抽象/代词/限定词的 (这类是被切断的句子残片)
_SUBJECT_TOO_ABSTRACT: Final[frozenset[str]] = frozenset({
    "待确认", "未知", "无", "这", "那", "此", "其", "之",
    "我们", "他们", "你们", "她们",
    "其他", "这些", "那些", "这个", "那个",
    "项目", "活动", "情况", "事情", "问题", "内容", "东西",  # 太宽泛的名词
})


# Codex 实测发现的 subject 残尾噪声: 抽断在词语中间
# 例: "团队已经把行动营理解为一个" / "值增值结果确认依据审计机构出具"
# 注: 移除 "会" — 因为 "基金会/委员会/协会" 都是合法 subject 末字
_SUBJECT_BAD_END: Final[frozenset[str]] = frozenset(
    "的了着把被让使将能可应一个为说要去到对在与和"
)

# subject 不能以这些副词/助词起头 (说明抽断在句子中间)
_SUBJECT_BAD_START: Final[frozenset[str]] = frozenset(
    "已正将又才也都就把被让使的了么哪那这若如或而但所"
)

# subject 包含这些助动词说明吃进了完整句子片段
_SUBJECT_FORBIDDEN_SUBSTR: Final[tuple[str, ...]] = (
    "已经", "正在", "把", "将要", "能够", "可以", "应该",
    "理解为", "认为", "确认依据", "期待说",
    # P1: 录音转写常见的口语化代词/动词组合
    "我们", "你们", "他们", "她们", "咱们",
    "看到", "听到", "讨论", "谈论", "分享", "说到",
    "证明你", "证明我", "证明他",
    "怎么", "为什么", "如何",
)


def _is_valid_subject(subject: str) -> bool:
    """Codex 实测加强: 拒绝抽断在句子中间的 subject."""
    if not subject:
        return False
    cleaned = subject.strip()
    if len(cleaned) < 2 or len(cleaned) > 25:
        return False
    # 末字不能是助词/动词残尾
    if cleaned[-1] in _SUBJECT_BAD_END:
        return False
    # 首字不能是副词/助词
    if cleaned[0] in _SUBJECT_BAD_START:
        return False
    # 不能含助动词 (说明是句子片段)
    for bad in _SUBJECT_FORBIDDEN_SUBSTR:
        if bad in cleaned:
            return False
    # 不能是太抽象/代词性 subject (例: "待确认" / "我们" / "项目")
    if cleaned in _SUBJECT_TOO_ABSTRACT:
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


def _looks_like_transcript(text: str) -> bool:
    """P1: 启发式判断这段文本是不是录音转写。

    录音转写特征：问号密度高、说话人标记、长口语句。
    符合任一即跳过事实抽取（这种文本抽出的全是句子碎片，不是事实）。
    """
    if not text or len(text) < 50:
        return False
    n = len(text)
    # 问号密度（中英文）
    q_count = text.count("?") + text.count("？")
    if q_count >= 3 and q_count / n > 0.01:  # 每 100 字 ≥1 个问号
        return True
    # 说话人标记
    if "说话人" in text or text.count("：") + text.count(":") > n // 30:
        return True
    # 口语化高频词密度
    oral_markers = ["对吧", "嗯", "然后", "其实", "我觉得", "我们就", "大家", "我想说"]
    oral_hits = sum(text.count(m) for m in oral_markers)
    if oral_hits >= 3:
        return True
    return False


def extract_facts_from_chunk(chunk_text: str) -> list[AtomicFact]:
    """抽取一个 chunk 里的原子事实。"""
    if not chunk_text or not chunk_text.strip():
        return []
    # Codex 实测发现的 OCR 噪声前置清理 (^A 控制字符 / 全角空格 / 多余空白)
    chunk_text = normalize_text(chunk_text)
    if not chunk_text:
        return []
    # P1: 录音转写跳过 — 这种文档抽出的全是句子碎片，无意义。
    if _looks_like_transcript(chunk_text):
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
        # Codex 加强: subject 必须是完整名词, 不能是抽断的句子片段
        if not _is_valid_subject(subject):
            continue
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
        if not _is_valid_subject(subject) or not _is_valid_value(value_raw):
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
        if not _is_valid_subject(subject) or not _is_valid_value(value_raw):
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
