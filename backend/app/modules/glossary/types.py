"""glossary 类型"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GlossaryTerm:
    id: str
    client_id: str
    term: str
    normalized_term: str
    definition: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    category: str = ""
    evidence_tier: str = "first_party"
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class GlossaryAttribute:
    id: str
    client_id: str
    term_id: str
    attribute_name: str
    value_category: str = "text"      # text / number / date / boolean
    value_text: str = ""
    value_unit: str = ""
    scope: str = ""
    as_of_date: str | None = None
    source_type: str = "ai_inferred"
    source_doc_id: str | None = None
    source_evidence: str = ""
    confidence: float = 0.0
    verification_status: str = "pending"   # pending / verified / rejected
    verified_by: str | None = None
    verified_at: str | None = None
    rejection_note: str = ""
    # 注:evidence_tier 在 client_glossary(term)表上,不在 glossary_attributes 表
    created_at: str = ""
    updated_at: str = ""
