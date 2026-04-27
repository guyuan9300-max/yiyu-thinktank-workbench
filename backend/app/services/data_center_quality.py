from __future__ import annotations

import re
from typing import Iterable

from app.models import AnswerMaterialRecord, AnswerPlanRecord, AnswerQualityReportRecord, EvidenceItem

_INTERNAL_MARKERS = (
    "RouteDecision",
    "RetrievalTrace",
    "embeddingSignature",
    "semantic router",
    "analysis-first",
    "state_first_hit_rate",
    "candidate_leakage_count",
    "retrievalDeferred",
)


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token.lower() in text.lower() for token in tokens)


def _looks_like_file_list(content: str) -> bool:
    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    if not lines:
        return False
    file_like = 0
    for line in lines[:10]:
        if re.search(r"\.(md|pdf|docx|pptx|txt)(\b|$)", line, re.IGNORECASE):
            file_like += 1
        if line.startswith("-") and ("文件" in line or "资料" in line):
            file_like += 1
    return file_like >= max(2, min(4, len(lines) // 2))


def _fact_slot_quality(answer_plan: AnswerPlanRecord, answer_material: AnswerMaterialRecord) -> tuple[bool, str | None]:
    intent = str(answer_plan.intent or "")
    if intent == "business_profile":
        business = answer_material.businessProfile
        modules = list(business.businessModules) if business is not None else []
        if not modules:
            return False, "business_modules_empty"
        if not any(module in (answer_material.directAnswerSeed or "") for module in modules):
            return False, "direct_answer_missing_business_module"
        return True, None
    if intent == "strategy_profile":
        strategy = answer_material.strategyProfile
        directions = list(strategy.strategicDirections) if strategy is not None else []
        time_boundary = str(strategy.timeBoundary or "").strip() if strategy is not None else ""
        if not directions:
            return False, "strategy_directions_empty"
        if not time_boundary:
            return False, "strategy_time_boundary_empty"
        if not any(direction in (answer_material.directAnswerSeed or "") for direction in directions):
            return False, "direct_answer_missing_strategy_direction"
        return True, None
    return True, None


def _official_boundary_violation(
    *,
    content: str,
    answer_plan: AnswerPlanRecord,
    answer_material: AnswerMaterialRecord,
) -> bool:
    if answer_plan.intent != "official_judgment_registry":
        return False
    normalized = re.sub(r"\s+", "", str(content or "").lower())
    has_candidate = "候选" in normalized or "candidate" in normalized
    has_official_claim = "已批准" in normalized or "正式判断如下" in normalized or "官方结论" in normalized
    has_disclaimer = "没有已批准" in normalized or "尚未" in normalized or "未形成" in normalized

    if has_candidate and has_official_claim and not has_disclaimer:
        return True

    boundary_text = " ".join(answer_material.boundaryNotes)
    if "候选" in boundary_text and has_official_claim and not has_disclaimer:
        return True
    return False


def validate_answer_quality(
    *,
    prompt: str,
    content: str,
    answer_plan: AnswerPlanRecord,
    evidence: list[EvidenceItem],
    answer_material: AnswerMaterialRecord,
) -> dict[str, object]:
    cleaned = str(content or "").strip()
    normalized = re.sub(r"\s+", "", cleaned)

    # P2.14 FREEZE(answer-shaping-quality-gate): 主回答链质量门禁当前只保留事实性硬失败，
    # 不再做 hasDirectAnswer / factSlotHit / missingRawEvidenceForIntent / offTopicRisk 之类的形态判定。
    # 先冻结这条边界，避免旧摘要质量门禁回流。
    has_direct_answer = bool(cleaned)
    evidence_list_only = False
    evidence_quote_only = False

    leaked = [marker for marker in _INTERNAL_MARKERS if marker.lower() in cleaned.lower()]
    official_boundary_violation = _official_boundary_violation(
        content=cleaned,
        answer_plan=answer_plan,
        answer_material=answer_material,
    )
    candidate_as_official = bool(
        official_boundary_violation
        or (
            "已批准" in normalized
            and ("候选" in "".join(answer_material.boundaryNotes) or "候选" in normalized)
            and "尚未" not in normalized
            and "没有已批准" not in normalized
            and "未形成" not in normalized
        )
    )
    missing_raw_evidence = False
    off_topic = False
    fact_slot_hit = True
    fact_slot_missing_reason = None

    grade = "pass"
    reason = "quality_pass"
    if leaked or candidate_as_official or official_boundary_violation:
        grade = "fail"
        reason = "official_boundary_violation" if official_boundary_violation else "leak_or_boundary_violation"

    report = AnswerQualityReportRecord(
        hasDirectAnswer=has_direct_answer,
        evidenceListOnly=evidence_list_only,
        evidenceQuoteOnly=evidence_quote_only,
        leakedInternalMarkers=leaked,
        candidateAsOfficialRisk=candidate_as_official,
        officialBoundaryViolation=official_boundary_violation,
        missingRawEvidenceForIntent=missing_raw_evidence,
        offTopicRisk=off_topic,
        factSlotHit=fact_slot_hit,
        factSlotMissingReason=fact_slot_missing_reason,
        grade=grade,  # type: ignore[arg-type]
        reason=reason,
    )
    return report.model_dump(mode="json")
