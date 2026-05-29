"""chunk 语义分类（迭代 4）。

把 v2_chunks 标上 fact / judgment / opinion / action / question /
conclusion / background / unclassified 八档之一，用于：
1. 引证面板让用户看清证据强度
2. evidence_selector 按类型加权（fact > judgment > opinion）

分两层：
- 规则层（先跑、零依赖）：action / question / conclusion / background
  的关键词模式
- LLM 层（可选、可注入）：fact / judgment / opinion 之间的细微区分
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Final, Literal

logger = logging.getLogger(__name__)

SemanticType = Literal[
    "fact",
    "judgment",
    "opinion",
    "action",
    "question",
    "conclusion",
    "background",
    "unclassified",
]

SEMANTIC_TYPES: Final[tuple[SemanticType, ...]] = (
    "fact",
    "judgment",
    "opinion",
    "action",
    "question",
    "conclusion",
    "background",
    "unclassified",
)


@dataclass(frozen=True)
class SemanticLabel:
    """分类产物。"""

    semantic_type: SemanticType
    confidence: float


# `LlmClassifier`：给定 chunk 文本，返回 (semantic_type, confidence)。
# 失败应抛异常，由调用方决定降级策略。
LlmClassifier = Callable[[str], SemanticLabel]


# ---- 规则层 --------------------------------------------------------------

# 优先级：高特征性的（question/conclusion/background）先检，action 兜底。
# 这样可以避免"主要"里的"要"被误匹配为 action。

# question：疑问句——很强的信号（句尾问号 或 疑问代词）
_QUESTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"[？?]\s*$"),
    re.compile(r"(?:为什么|怎么|如何|能否|是否|何时|什么时候|哪些)"),
)

# conclusion：归纳/总结性语词——开头/前导位置最准
_CONCLUSION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?:综上|因此|所以|总之|总而言之|可见|由此可见)"),
    re.compile(r"结论(?:是|：)"),
    re.compile(r"(?:本次|本节)(?:得出|结论)"),
)

# background：交代性介绍——句首"简介/背景"或时间词"历史上/此前"
_BACKGROUND_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^(?:简介|背景|前言|引言|概述|历史)"),
    re.compile(r"(?:历史上|此前|早年|早期|多年来|长期以来|过去几年)"),
    re.compile(r"成立(?:于|时间|背景)|创办于|始建于"),
)

# action：祈使/计划/待办——只在明确上下文里匹配，避免吃"主要/必要"里的"要"
_ACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # 明确标签
    re.compile(r"TODO|待办|action\s*item|跟进事项|下一步[:：]|行动项|action[:：]"),
    # 主语+动词组合
    re.compile(r"(?:我们|你|你们|请|建议)(?:需要|要|应当|应该|得|应|可以)"),
    # 时间锚 + 行动词
    re.compile(r"(?:本周|下周|本月|月底|本季度|月内|周内)(?:内)?(?:需要|要|完成|启动|推进|提交)"),
    # 开头的祈使指令
    re.compile(r"^(?:需要|请|建议|希望)"),
)


def classify_by_rules(text: str) -> SemanticLabel | None:
    """规则层分类。命中返回 SemanticLabel，未命中返回 None。

    优先级：question > conclusion > background > action（特征强的先）。
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()
    for pattern in _QUESTION_PATTERNS:
        if pattern.search(stripped):
            return SemanticLabel("question", 0.85)
    for pattern in _CONCLUSION_PATTERNS:
        if pattern.search(stripped):
            return SemanticLabel("conclusion", 0.8)
    for pattern in _BACKGROUND_PATTERNS:
        if pattern.search(stripped):
            return SemanticLabel("background", 0.75)
    for pattern in _ACTION_PATTERNS:
        if pattern.search(stripped):
            return SemanticLabel("action", 0.8)
    return None


# ---- LLM 层 --------------------------------------------------------------

LLM_SEMANTIC_PROMPT: Final[str] = """你是一位**信息分类专家**。给定一段中文文本，判定它最主要的语义类型：

- fact（事实）：可被外部验证的客观陈述（数字、日期、事件、合同条款等）
- judgment（判断）：基于资料给出的分析性结论或评估
- opinion（观点）：主观看法、立场表达，没有数据支撑
- background（背景）：纯介绍/历史交代

输出严格 JSON：{"semantic_type":"fact","confidence":0.0-1.0}

只输出 JSON，不要其他解释。

---
文本：
"""


def build_llm_prompt(chunk_text: str) -> str:
    """组装 LLM 分类 prompt。"""
    truncated = chunk_text[:2000]
    return LLM_SEMANTIC_PROMPT + truncated


def parse_llm_output(raw: str) -> SemanticLabel | None:
    """解析 LLM JSON 输出。失败返回 None。"""
    text = raw.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    if not text.startswith("{"):
        idx = text.find("{")
        if idx >= 0:
            text = text[idx:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM 语义输出 JSON 解析失败: %s", text[:200])
        return None
    if not isinstance(data, dict):
        return None
    semantic_type = data.get("semantic_type") or data.get("type")
    if semantic_type not in SEMANTIC_TYPES:
        return None
    try:
        confidence = float(data.get("confidence") or 0.5)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    return SemanticLabel(semantic_type, confidence)  # type: ignore[arg-type]


# ---- 主入口 --------------------------------------------------------------


def classify_chunk_semantic(
    chunk_text: str,
    *,
    llm_classifier: LlmClassifier | None = None,
) -> SemanticLabel:
    """主入口：规则层优先，未命中再 LLM。最终都没命中 → unclassified。

    Args:
        chunk_text: chunk 原文。
        llm_classifier: 可选 LLM 分类器。

    Returns:
        SemanticLabel；空文本/全失败 → unclassified, confidence=0.0。
    """
    if not chunk_text or not chunk_text.strip():
        return SemanticLabel("unclassified", 0.0)
    rule_label = classify_by_rules(chunk_text)
    if rule_label is not None:
        return rule_label
    if llm_classifier is None:
        return SemanticLabel("unclassified", 0.0)
    try:
        llm_label = llm_classifier(chunk_text)
    except Exception as exc:
        logger.warning("LLM 语义分类失败，降级到 unclassified: %s", exc)
        return SemanticLabel("unclassified", 0.0)
    return llm_label


# ---- 检索加权 -------------------------------------------------------------

# evidence_selector 按 semantic_type 给的权重乘数。
# 默认 1.0 = 不打扰；> 1.0 = 优先；< 1.0 = 降权。
SEMANTIC_WEIGHT: Final[dict[str, float]] = {
    "fact": 1.2,
    "conclusion": 1.1,
    "action": 1.0,
    "judgment": 1.0,
    "background": 0.9,
    "opinion": 0.7,
    "question": 0.6,
    "unclassified": 1.0,
}


def semantic_weight(semantic_type: str | None) -> float:
    """按语义类型查检索加权乘数。未知类型返回 1.0。"""
    if not semantic_type:
        return 1.0
    return SEMANTIC_WEIGHT.get(semantic_type, 1.0)


__all__ = [
    "SEMANTIC_TYPES",
    "SEMANTIC_WEIGHT",
    "LlmClassifier",
    "SemanticLabel",
    "SemanticType",
    "build_llm_prompt",
    "classify_by_rules",
    "classify_chunk_semantic",
    "parse_llm_output",
    "semantic_weight",
]
