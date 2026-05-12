"""实体抽取服务（迭代 2）。

设计意图：
- 把 chunk 文本拆成结构化实体（person / company / project / product /
  competitor / amount / date）。
- 分层架构：
  * 规则层（先跑、零依赖）：amount（金额）、date（日期）、person 称谓、
    company 后缀。确定性高、可单元测试。
  * LLM 层（兜底、可选）：project / product / competitor 等没有强 pattern
    的类型，加上对 person / company 的更精细识别。
- LLM 入口设计为**可注入的 callable**，便于：
  * 测试时用 stub
  * 生产 AI 不可用时降级到纯规则
  * 切换不同模型不污染主逻辑
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Final, Literal

logger = logging.getLogger(__name__)

# ---- 类型 ----------------------------------------------------------------

EntityType = Literal[
    "person",
    "company",
    "project",
    "product",
    "competitor",
    "amount",
    "date",
]

ENTITY_TYPES: Final[tuple[EntityType, ...]] = (
    "person",
    "company",
    "project",
    "product",
    "competitor",
    "amount",
    "date",
)


@dataclass(frozen=True)
class ExtractedEntity:
    """单次抽取产物。

    `normalized_name` 用于跨文档归一化（dedupe key）；`display_name` 是
    展示用的原文形式。`position_start/end` 是 chunk 内字符位置（best-effort）。
    """

    entity_type: EntityType
    text: str
    normalized_name: str
    display_name: str
    confidence: float
    position_start: int | None = None
    position_end: int | None = None
    attributes: dict[str, str] = field(default_factory=dict)


# `LlmExtractor` 是注入点：给定 chunk 文本，返回 LLM 抽出的实体列表。
# 失败应当抛异常，由调用方决定降级策略。
LlmExtractor = Callable[[str], list[ExtractedEntity]]


# ---- 规则层 --------------------------------------------------------------

# 金额：数字（可带千分位/小数）+ 单位 + 货币词
_AMOUNT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<amount>\d+(?:[\.,]\d+)*)\s*(?P<scale>万|千|百万|亿|k|w|M)?\s*(?P<unit>元|美元|美刀|刀|RMB|USD|¥|￥|\$)",
    re.IGNORECASE,
)

# 日期：YYYY-MM-DD / YYYY年M月D日 / YYYY年M月 / M月D日
_DATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<date>"
    r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?"
    r"|\d{4}[-/年]\d{1,2}月?"
    r"|\d{1,2}月\d{1,2}日"
    r")"
)

# 常见中文单字姓氏白名单——用作 person 抽取的"起始锚点"，避免中文无空格
# 导致正则贪心吃掉前面的字（如 "今天和张总" 误抓为 "天和张"）。
# 覆盖约 100 个最常见姓氏，命中率 ~95%。
_CHINESE_SURNAMES: Final[str] = (
    "王李张刘陈杨黄赵吴周徐孙马朱胡林郭何高罗郑梁谢宋唐许韩冯邓曹彭"
    "曾田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖"
    "贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱"
    "严覃武戴莫孔向汤欧阮施童易聂文季"
)

# 人物称谓：姓（必须在白名单）+ 0-2 字名 + 称谓（长后缀优先）
_PERSON_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<name>[" + _CHINESE_SURNAMES + r"][一-龥]{0,2}?)"
    r"(?P<title>总监|总裁|总经理|董事长|经理|老板|老师|教授|总|工|CEO|CTO|CFO|COO)"
)

# 公司后缀：1-15 个汉字/字母/数字 + 后缀。长后缀优先（科技有限公司 > 有限公司 > 公司）。
_COMPANY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<name>[一-龥A-Za-z0-9]{1,15}?)"
    r"(?P<suffix>科技有限公司|股份有限公司|有限公司|集团|科技|公司|网络|信息|咨询|实验室)"
)

# 公司名前面常出现的中文虚词/动词 → 需从抓到的 name 里剥离
# 例如 "和阿里集团" → regex 抓到 "和阿里" → 剥离后 "阿里"
_COMPANY_NAME_STOPCHARS: Final[frozenset[str]] = frozenset(
    "和与的了是有跟同到从在做就要把使让给帮替我你他她它对手有还于及或"
)


def _normalize_amount(raw_amount: str, scale: str, unit: str) -> str:
    """归一化金额：把不同写法统一为 '50万元' / '100美元' 形式。"""
    clean_amount = raw_amount.replace(",", "")
    scale_norm = {
        "k": "千",
        "w": "万",
        "M": "百万",
    }.get(scale.lower() if scale else "", scale or "")
    unit_norm = {
        "美刀": "美元",
        "刀": "美元",
        "USD": "美元",
        "$": "美元",
        "RMB": "元",
        "¥": "元",
        "￥": "元",
    }.get(unit, unit)
    return f"{clean_amount}{scale_norm}{unit_norm}"


def _normalize_date(raw_date: str) -> str:
    """归一化日期：尽量统一到 YYYY-MM-DD 或 MM-DD 形式。"""
    text = raw_date.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    parts = [p for p in text.split("-") if p]
    if len(parts) == 3:
        year, month, day = parts
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    if len(parts) == 2:
        a, b = parts
        if len(a) == 4:  # YYYY-MM
            return f"{int(a):04d}-{int(b):02d}"
        return f"{int(a):02d}-{int(b):02d}"  # MM-DD
    return raw_date


def extract_amounts(text: str) -> list[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for match in _AMOUNT_PATTERN.finditer(text):
        raw_amount = match.group("amount")
        scale = match.group("scale") or ""
        unit = match.group("unit") or ""
        normalized = _normalize_amount(raw_amount, scale, unit)
        out.append(
            ExtractedEntity(
                entity_type="amount",
                text=match.group(0),
                normalized_name=normalized,
                display_name=match.group(0),
                confidence=0.95,  # 规则级，置信度高
                position_start=match.start(),
                position_end=match.end(),
                attributes={"raw_amount": raw_amount, "scale": scale, "unit": unit},
            )
        )
    return out


def extract_dates(text: str) -> list[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for match in _DATE_PATTERN.finditer(text):
        raw_date = match.group("date")
        normalized = _normalize_date(raw_date)
        out.append(
            ExtractedEntity(
                entity_type="date",
                text=raw_date,
                normalized_name=normalized,
                display_name=raw_date,
                confidence=0.9,
                position_start=match.start(),
                position_end=match.end(),
            )
        )
    return out


def extract_persons_by_title(text: str) -> list[ExtractedEntity]:
    """规则层 person 抽取：仅识别"姓 + 称谓"形式（张总、李工、王经理）。

    不带称谓的人名（全名 / 英文名）留给 LLM 层。
    """
    out: list[ExtractedEntity] = []
    seen_names: set[str] = set()
    for match in _PERSON_PATTERN.finditer(text):
        name = match.group("name")
        title = match.group("title")
        full = f"{name}{title}"
        if full in seen_names:
            continue
        seen_names.add(full)
        out.append(
            ExtractedEntity(
                entity_type="person",
                text=full,
                normalized_name=full,  # 称谓形式自带消歧
                display_name=full,
                confidence=0.75,
                position_start=match.start(),
                position_end=match.end(),
                attributes={"title": title},
            )
        )
    return out


def extract_companies_by_suffix(text: str) -> list[ExtractedEntity]:
    """规则层 company 抽取：识别"名+后缀"（XX 科技 / XX 公司 / XX 集团）。

    后处理：剥离 name 开头的中文虚词（"和"、"对手是" 等），避免误抓相邻字。
    """
    out: list[ExtractedEntity] = []
    seen_names: set[str] = set()
    for match in _COMPANY_PATTERN.finditer(text):
        raw_name = match.group("name").strip()
        suffix = match.group("suffix")
        # 剥离开头的中文虚词
        name = raw_name
        while name and name[0] in _COMPANY_NAME_STOPCHARS:
            name = name[1:]
        if len(name) < 2:
            continue
        full = f"{name}{suffix}"
        if full in seen_names:
            continue
        seen_names.add(full)
        # 重新计算 position（剥离了几个前缀字符）
        offset_correction = len(raw_name) - len(name)
        out.append(
            ExtractedEntity(
                entity_type="company",
                text=full,
                normalized_name=full,
                display_name=full,
                confidence=0.7,
                position_start=match.start() + offset_correction,
                position_end=match.end(),
                attributes={"suffix": suffix},
            )
        )
    return out


def extract_by_rules(text: str) -> list[ExtractedEntity]:
    """规则层一站式：amount + date + person(称谓) + company(后缀)。"""
    return [
        *extract_amounts(text),
        *extract_dates(text),
        *extract_persons_by_title(text),
        *extract_companies_by_suffix(text),
    ]


# ---- LLM 层 --------------------------------------------------------------

LLM_ENTITY_PROMPT: Final[str] = """你是一个**实体抽取专家**。从下面这段中文文本里抽出以下类型的实体：

- person（人物）：姓名（含全名、英文名、外号）
- company（公司）：公司、组织、机构名
- project（项目）：项目名、产品代号、合同编号
- product（产品）：商品、服务、解决方案的名字
- competitor（竞品）：明显被对比或竞争的对手公司/产品

**不要**抽 amount（金额）和 date（日期）——它们由规则层处理。

输出严格的 JSON 数组，每个元素：
{"entity_type": "...", "text": "原文", "normalized_name": "归一化名", "confidence": 0.0-1.0}

如果没有抽到任何实体，输出空数组 []。

---
文本：
"""


def build_llm_prompt(chunk_text: str) -> str:
    """组装 LLM 抽取 prompt。"""
    truncated = chunk_text[:3000]  # 防止 chunk 异常巨大
    return LLM_ENTITY_PROMPT + truncated


def parse_llm_output(raw: str) -> list[ExtractedEntity]:
    """把 LLM 返回的 JSON 字符串解析成 ExtractedEntity 列表。

    容错：尝试找 JSON 数组，失败返回空列表（不抛错——保证降级到规则层）。
    """
    text = raw.strip()
    # 兼容 LLM 在 JSON 外面包裹 ```json ... ``` 的情况
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    # 兜底：找第一个 [
    if not text.startswith("["):
        idx = text.find("[")
        if idx >= 0:
            text = text[idx:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM 实体输出 JSON 解析失败: %s", text[:200])
        return []
    if not isinstance(data, list):
        return []
    out: list[ExtractedEntity] = []
    for raw_item in data:
        if not isinstance(raw_item, dict):
            continue
        entity_type_raw = raw_item.get("entity_type") or raw_item.get("type")
        if entity_type_raw not in ENTITY_TYPES:
            continue
        text_value = str(raw_item.get("text") or "").strip()
        if not text_value:
            continue
        normalized = str(raw_item.get("normalized_name") or text_value).strip()
        try:
            confidence = float(raw_item.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        out.append(
            ExtractedEntity(
                entity_type=entity_type_raw,  # type: ignore[arg-type]
                text=text_value,
                normalized_name=normalized,
                display_name=text_value,
                confidence=confidence,
            )
        )
    return out


# ---- 合并主入口 ----------------------------------------------------------


def merge_extractions(
    primary: list[ExtractedEntity],
    secondary: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    """以 (entity_type, normalized_name) 为键合并；primary 优先。"""
    seen: set[tuple[str, str]] = set()
    out: list[ExtractedEntity] = []
    for entity in primary:
        key = (entity.entity_type, entity.normalized_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(entity)
    for entity in secondary:
        key = (entity.entity_type, entity.normalized_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(entity)
    return out


def extract_entities_from_chunk(
    chunk_text: str,
    *,
    llm_extractor: LlmExtractor | None = None,
) -> list[ExtractedEntity]:
    """主入口：规则层 + LLM 层合并。

    Args:
        chunk_text: 一个 chunk 的原文。
        llm_extractor: 可选 LLM 抽取器。``None`` → 仅跑规则。

    Returns:
        合并去重后的实体列表。规则层优先（金额/日期/称谓/后缀这种确定性
        高的不被 LLM 改写）。
    """
    if not chunk_text or not chunk_text.strip():
        return []
    rule_based = extract_by_rules(chunk_text)
    if llm_extractor is None:
        return rule_based
    try:
        llm_based = llm_extractor(chunk_text)
    except Exception as exc:
        logger.warning("LLM 实体抽取失败，降级到规则层: %s", exc)
        return rule_based
    return merge_extractions(rule_based, llm_based)


__all__ = [
    "ENTITY_TYPES",
    "EntityType",
    "ExtractedEntity",
    "LlmExtractor",
    "build_llm_prompt",
    "extract_amounts",
    "extract_by_rules",
    "extract_companies_by_suffix",
    "extract_dates",
    "extract_entities_from_chunk",
    "extract_persons_by_title",
    "merge_extractions",
    "parse_llm_output",
]
