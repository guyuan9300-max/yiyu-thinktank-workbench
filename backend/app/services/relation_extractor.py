"""关系三元组抽取（迭代 5）。

从 chunk 文本里识别 (subject, predicate, object) 三元组。

设计：
- 规则层（先跑、零依赖）：用 RELATION_PATTERNS 的 regex 模板逐个尝试
- LLM 层（可选、可注入）：兜底处理规则未命中的复杂语句
- subject / object 命中后，尝试在已有 entities 表里 lookup 匹配，
  匹配上则关联到 entity_id，否则作为自由文本保留

主语/宾语归一化：strip 标点、limit 长度。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

from app.services.relation_dictionary import RELATION_PATTERNS, RelationPredicate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedRelation:
    """单次抽取的三元组（subject/object 都是文本，由调用方负责映射到 entity_id）。"""

    predicate: RelationPredicate
    subject_text: str
    object_text: str
    confidence: float
    evidence_text: str = ""
    attributes: dict[str, str] = field(default_factory=dict)


# `LlmRelationExtractor`：可注入的 LLM 抽取器
LlmRelationExtractor = Callable[[str], list[ExtractedRelation]]


# ---- 工具 ----------------------------------------------------------------

_NORMALIZE_STRIP_RE = re.compile(r"^[，。、；：\s]+|[，。、；：\s]+$")


def _normalize_term(term: str) -> str:
    """对 subject/object 做基础归一：去除两侧标点空白，限长 30 字。"""
    cleaned = _NORMALIZE_STRIP_RE.sub("", term).strip()
    return cleaned[:30]


def _is_valid_pair(subject: str, obj: str) -> bool:
    if not subject or not obj:
        return False
    if subject == obj:
        return False
    if len(subject) < 2 or len(obj) < 2:
        return False
    return True


# ---- 规则层 --------------------------------------------------------------


def extract_by_rules(text: str) -> list[ExtractedRelation]:
    """规则层一站式抽取。同一 (subject, predicate, object) 在一段内只算一次。"""
    if not text or not text.strip():
        return []
    seen: set[tuple[str, str, str]] = set()
    out: list[ExtractedRelation] = []
    for pattern_def in RELATION_PATTERNS:
        for match in pattern_def.pattern.finditer(text):
            subject = _normalize_term(match.group("subject"))
            obj = _normalize_term(match.group("object"))
            if not _is_valid_pair(subject, obj):
                continue
            key = (subject, pattern_def.predicate, obj)
            if key in seen:
                continue
            seen.add(key)
            evidence_start = max(0, match.start() - 10)
            evidence_end = min(len(text), match.end() + 10)
            evidence = text[evidence_start:evidence_end].strip()
            out.append(
                ExtractedRelation(
                    predicate=pattern_def.predicate,
                    subject_text=subject,
                    object_text=obj,
                    confidence=pattern_def.confidence,
                    evidence_text=evidence,
                )
            )
    return out


# ---- 主入口 --------------------------------------------------------------


def extract_relations_from_chunk(
    chunk_text: str,
    *,
    llm_extractor: LlmRelationExtractor | None = None,
) -> list[ExtractedRelation]:
    """主入口：规则层 + LLM 层合并去重。规则结果优先（confidence 已固定）。"""
    if not chunk_text or not chunk_text.strip():
        return []
    rule_based = extract_by_rules(chunk_text)
    if llm_extractor is None:
        return rule_based
    try:
        llm_based = llm_extractor(chunk_text)
    except Exception as exc:
        logger.warning("LLM 关系抽取失败，降级到规则层: %s", exc)
        return rule_based
    seen: set[tuple[str, str, str]] = {
        (r.subject_text, r.predicate, r.object_text) for r in rule_based
    }
    merged = list(rule_based)
    for rel in llm_based:
        key = (rel.subject_text, rel.predicate, rel.object_text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(rel)
    return merged


__all__ = [
    "ExtractedRelation",
    "LlmRelationExtractor",
    "extract_by_rules",
    "extract_relations_from_chunk",
]
