from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.db import Database
from app.models import RetrievalModelSettingsRecord
from app.services.evidence_quality_feedback import (
    build_evidence_excerpt_hash,
    get_human_quality_adjustment,
)
from app.services.evidence_quality import classify_evidence_quality_fields


@dataclass
class RerankMeta:
    provider: str
    rerankUsed: bool
    candidateCount: int
    outputCount: int
    error: str | None = None


class RerankProvider(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[Any],
        *,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> tuple[list[Any], RerankMeta]:
        ...


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


@dataclass
class RuleRerankProvider:
    db: Database | None = None
    limit: int = 30

    def rerank(
        self,
        query: str,
        candidates: list[Any],
        *,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> tuple[list[Any], RerankMeta]:
        normalized_query = _normalize(query)
        feedback_enabled = bool(self.db is not None and source_type and source_id)
        scored: list[tuple[float, Any]] = []
        for item in candidates:
            base_score = float(getattr(item, "score", 0.0) or 0.0)
            source_stage = str(getattr(item, "source_stage", "") or "")
            section_label = str(getattr(item, "section_label", "") or "")
            title = str(getattr(item, "title", "") or "")
            excerpt = str(getattr(item, "excerpt", "") or "")
            haystack = _normalize(f"{title} {section_label} {excerpt}")

            score = base_score
            if source_stage == "raw_chunk":
                score += 0.15
            if section_label:
                score += 0.05
            quality = classify_evidence_quality_fields(
                title=title,
                excerpt=excerpt,
                source_type=str(getattr(item, "source_type", "") or ""),
                section_label=section_label,
                retrieval_stage=source_stage,
                path=str(getattr(item, "path", "") or ""),
            )
            score += float(quality.qualityScore) * 0.08
            if quality.isNoise:
                score -= max(0.2, float(quality.demotionScore) * 0.4)
            if quality.sourceKind in {"generated_answer", "memory_answer", "ppt_master", "template_page", "short_excerpt"}:
                score -= 0.32
            if quality.sourceKind in {"meeting_decision", "meeting_action", "meeting_risk"}:
                score += 0.22
            if any(token in haystack for token in ("介绍", "简介", "背景", "项目")) and any(token in normalized_query for token in ("介绍", "简介", "背景")):
                score += 0.18
            if any(token in haystack for token in ("会议", "纪要", "行动项")) and "会议" in normalized_query:
                score += 0.2
            if any(token in haystack for token in ("财务", "年报", "审计", "预算")) and any(token in normalized_query for token in ("财务", "报表", "预算", "审计")):
                score += 0.22
            if any(token in haystack for token in ("模板", "clicktoeditmaster", "演示文稿")):
                score -= 0.35
            if feedback_enabled:
                excerpt_hash = build_evidence_excerpt_hash(
                    title=title,
                    excerpt=excerpt,
                    path=str(getattr(item, "path", "") or ""),
                )
                score += get_human_quality_adjustment(
                    self.db,
                    source_type=str(source_type or ""),
                    source_id=str(source_id or ""),
                    document_id=str(getattr(item, "document_id", "") or "") or None,
                    excerpt_hash=excerpt_hash,
                )
            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        output = [item for _, item in scored[: self.limit]]
        meta = RerankMeta(
            provider="rules",
            rerankUsed=True,
            candidateCount=len(candidates),
            outputCount=len(output),
        )
        return output, meta


@dataclass
class FutureExternalRerankProvider:
    def rerank(
        self,
        query: str,
        candidates: list[Any],
        *,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> tuple[list[Any], RerankMeta]:
        del query, source_type, source_id
        return candidates, RerankMeta(
            provider="external_reserved",
            rerankUsed=False,
            candidateCount=len(candidates),
            outputCount=len(candidates),
        )


def build_rerank_provider(settings: RetrievalModelSettingsRecord, *, db: Database | None = None) -> RerankProvider:
    if settings.rerankEnabled and settings.rerankProvider not in {"rules", ""}:
        return FutureExternalRerankProvider()
    return RuleRerankProvider(db=db)
