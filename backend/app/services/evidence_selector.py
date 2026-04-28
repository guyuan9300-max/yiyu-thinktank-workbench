from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.db import Database
from app.models import (
    EvidenceDecisionTraceRecord,
    EvidenceItem,
    PageContextPackRecord,
    PageIntentType,
    QuestionFocusFrameRecord,
    RouteDecisionRecord,
    SemanticSourceRole,
)
from app.services.evidence_quality_feedback import (
    build_evidence_excerpt_hash,
    get_human_quality_adjustment,
)
from app.services.evidence_quality import classify_evidence_quality
from app.services.question_focus import (
    build_question_focus_frame,
    coverage_targets_for_focus,
    score_focus_role_match,
)
from app.services.source_semantics import infer_semantic_source_roles_fields


@dataclass
class SelectedEvidenceAuditResult:
    selected: list[EvidenceItem]
    question_focus_frame: QuestionFocusFrameRecord
    decision_trace: list[EvidenceDecisionTraceRecord]
    selected_roles: list[SemanticSourceRole]
    unselected_high_priority_sources: list[dict[str, object]]


@dataclass
class _CandidateScore:
    item: EvidenceItem
    score: float
    base_score: float
    is_noise: bool
    semantic_roles: list[SemanticSourceRole]
    role_reasons: list[str]
    priority_reasons: list[str]


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


_TARGET_DOCUMENT_GROUPS: dict[str, tuple[str, ...]] = {
    "contract": ("合同", "协议", "报价", "申请书", "标书", "0907"),
}


def _target_document_groups_for_prompt(prompt: str) -> list[str]:
    normalized = _normalize(prompt)
    groups: list[str] = []
    for group, tokens in _TARGET_DOCUMENT_GROUPS.items():
        if _contains_any(normalized, tokens):
            groups.append(group)
    return groups


def _target_document_bonus(item: EvidenceItem, groups: list[str]) -> tuple[float, list[str]]:
    if not groups:
        return 0.0, []
    haystack = _normalize(" ".join([
        str(item.title or ""),
        str(item.path or ""),
        str(item.originalPath or ""),
        str(item.managedPath or ""),
        str(item.sectionLabel or ""),
    ]))
    bonus = 0.0
    reasons: list[str] = []
    for group in groups:
        tokens = _TARGET_DOCUMENT_GROUPS.get(group, ())
        if tokens and _contains_any(haystack, tokens):
            bonus += 1.25
            reasons.append(f"target_document_bonus:{group}")
    return bonus, reasons


def _source_reachability_for_item(item: EvidenceItem) -> str:
    path = str(item.path or "")
    if "/_imports/" in path:
        return "reachable_support"
    if item.retrievalStage == "state_pool" or item.sourceType in {
        "meeting_note",
        "task_attachment",
        "official_judgment",
        "candidate_judgment",
        "topic_candidate",
    }:
        return "state_pool"
    return "indexed_primary"


def _document_group_key(item: EvidenceItem) -> str:
    title_key = re.sub(r"\(\d+\)", "", re.sub(r"\.[a-z0-9]+$", "", _normalize(item.title)))
    if title_key:
        return f"title:{title_key}"
    if item.documentId:
        return f"doc:{item.documentId}"
    if item.path:
        return f"path:{str(item.path).strip().lower()}"
    return f"title:{_normalize(item.title)}"


def _should_augment_with_indexed_primary(focus_frame: QuestionFocusFrameRecord) -> bool:
    return False


def _augment_with_indexed_primary_sources(
    *,
    db: Database | None,
    client_id: str | None,
    focus_frame: QuestionFocusFrameRecord,
    evidence: list[EvidenceItem],
) -> list[EvidenceItem]:
    if not db or not client_id or not _should_augment_with_indexed_primary(focus_frame):
        return evidence

    existing_groups = {_document_group_key(item) for item in evidence}
    rows = db.fetchall(
        """
        SELECT
            d.id AS document_id,
            d.title,
            d.path,
            d.excerpt,
            v.preview_text,
            v.visible_category,
            v.secondary_category,
            v.material_layer,
            v.parse_status
        FROM v2_documents v
        JOIN documents d ON d.id = v.document_id
        WHERE v.client_id = ?
          AND v.parse_status = 'ready'
        ORDER BY v.updated_at DESC
        LIMIT 300
        """,
        (client_id,),
    )

    augmented: list[tuple[float, EvidenceItem]] = []
    for row in rows:
        title = str(row["title"] or "").strip()
        path = str(row["path"] or "").strip()
        excerpt = str(row["preview_text"] or row["excerpt"] or "").strip()
        if not title or not excerpt:
            continue
        candidate_item = EvidenceItem(
            id=f"aug_{row['document_id']}",
            title=title,
            excerpt=excerpt[:700],
            sourceType="knowledge_document",
            documentId=str(row["document_id"] or "") or None,
            path=path or None,
            score=0.0,
            sectionLabel="资料摘要",
            retrievalStage="master_index",
            matchedTerms=[],
        )
        group_key = _document_group_key(candidate_item)
        if group_key in existing_groups:
            continue
        roles, _ = infer_semantic_source_roles_fields(
            title=title,
            excerpt=excerpt,
            path=path,
            visible_category=str(row["visible_category"] or ""),
            secondary_category=str(row["secondary_category"] or ""),
            material_layer=str(row["material_layer"] or ""),
            source_type="knowledge_document",
        )
        if not roles or "derived_profile_support" in roles:
            continue
        focus_score, _ = score_focus_role_match(focus_frame, roles)
        if focus_score <= 0:
            continue
        anchor_bonus, _ = _profile_anchor_bonus(candidate_item, roles, focus_frame)
        if "operational_update" in roles and not any(
            role in roles for role in {"institution_identity", "problem_definition", "program_overview", "method_or_model", "strategy_direction"}
        ):
            continue
        rank = focus_score + anchor_bonus
        if any(role in roles for role in {"institution_identity", "problem_definition", "program_overview"}):
            rank += 0.35
        augmented.append((rank, candidate_item))

    augmented.sort(key=lambda item: item[0], reverse=True)
    extras: list[EvidenceItem] = []
    for _, item in augmented[:6]:
        group_key = _document_group_key(item)
        if group_key in existing_groups:
            continue
        existing_groups.add(group_key)
        extras.append(item)
    return [*evidence, *extras]


def _profile_anchor_bonus(item: EvidenceItem, semantic_roles: list[SemanticSourceRole], focus_frame: QuestionFocusFrameRecord) -> tuple[float, list[str]]:
    del item, semantic_roles, focus_frame
    return 0.0, []


def _role_selection_priority(
    candidate: _CandidateScore,
    *,
    role: SemanticSourceRole,
    focus_frame: QuestionFocusFrameRecord,
) -> tuple[float, int, int, float]:
    discouraged_count = sum(1 for item in focus_frame.discouragedRoles if item in candidate.semantic_roles)
    reachability = _source_reachability_for_item(candidate.item)
    reachability_rank = {
        "indexed_primary": 0,
        "state_pool": 1,
        "reachable_support": 2,
    }.get(reachability, 3)
    has_operational_role = 1 if "operational_update" in candidate.semantic_roles else 0
    role_specificity = 1 if candidate.semantic_roles.count(role) == 1 else 0
    return (
        1 if not has_operational_role else 0,
        1 if reachability == "indexed_primary" else 0,
        1 if any(reason.startswith("profile_anchor:") for reason in candidate.priority_reasons) else 0,
        role_specificity,
        -(discouraged_count + has_operational_role),
        candidate.score,
        -float(reachability_rank),
    )


def _fill_selection_priority(
    candidate: _CandidateScore,
    *,
    focus_frame: QuestionFocusFrameRecord,
) -> tuple[int, int, int, float]:
    reachability = _source_reachability_for_item(candidate.item)
    return (
        1 if any(reason.startswith("profile_anchor:") for reason in candidate.priority_reasons) else 0,
        1 if "operational_update" not in candidate.semantic_roles else 0,
        1 if reachability == "indexed_primary" else 0,
        candidate.score,
    )


def _score_item(
    intent: PageIntentType,
    item: EvidenceItem,
    *,
    prompt: str,
    focus_frame: QuestionFocusFrameRecord,
    human_adjustment: float = 0.0,
) -> _CandidateScore:
    del intent
    title = _normalize(item.title)
    section = _normalize(item.sectionLabel)
    excerpt = _normalize(item.excerpt)
    merged = f"{title}{section}{excerpt}"
    quality = classify_evidence_quality(item)
    score = float(item.score or 0.0) + float(quality.qualityScore) - float(quality.demotionScore)
    base_score = score + float(human_adjustment)
    score = base_score
    excerpt_text = str(item.excerpt or "").strip()

    priority_reasons: list[str] = []
    if item.retrievalStage == "raw_chunk":
        score += 0.15
        priority_reasons.append("raw_chunk_bonus")
    if item.sectionLabel:
        score += 0.08
        priority_reasons.append("section_label_bonus")
    if human_adjustment:
        score += float(human_adjustment)
        priority_reasons.append(f"human_adjustment:{round(float(human_adjustment), 4)}")
    target_bonus, target_reasons = _target_document_bonus(item, _target_document_groups_for_prompt(prompt))
    if target_bonus:
        score += target_bonus
        priority_reasons.extend(target_reasons)

    if quality.sourceKind in {"generated_answer", "memory_answer", "ppt_master", "template_page", "short_excerpt"}:
        score -= 0.6
        priority_reasons.append(f"source_kind_demote:{quality.sourceKind}")
    if quality.isNoise:
        score -= 0.8
        priority_reasons.append("noise_demote")

    return _CandidateScore(
        item=item,
        score=score,
        base_score=base_score,
        is_noise=quality.isNoise,
        semantic_roles=list(quality.semanticRoles),
        role_reasons=list(quality.roleReasons),
        priority_reasons=priority_reasons,
    )


def _dedup_key(item: EvidenceItem) -> str:
    return f"{item.documentId or ''}:{item.path or ''}:{_normalize(item.excerpt)[:120]}"


def _build_decision_trace(
    scored: list[_CandidateScore],
    *,
    selected_keys: set[str],
) -> list[EvidenceDecisionTraceRecord]:
    trace: list[EvidenceDecisionTraceRecord] = []
    for candidate in scored:
        key = _dedup_key(candidate.item)
        final_decision = "selected" if key in selected_keys else "not_selected"
        if candidate.is_noise and final_decision != "selected":
            final_decision = "filtered_noise"
        elif candidate.score < 0 and final_decision != "selected":
            final_decision = "filtered_low_relevance"
        trace.append(
            EvidenceDecisionTraceRecord(
                title=candidate.item.title,
                path=str(candidate.item.path or ""),
                documentId=candidate.item.documentId,
                semanticRoles=candidate.semantic_roles,
                roleReasons=candidate.role_reasons,
                sourcePresence="present",
                sourceReachability=_source_reachability_for_item(candidate.item),
                sourceSelectionPool="included",
                sourcePriorityReason=candidate.priority_reasons,
                sourceFinalDecision=final_decision,
                score=round(candidate.score, 4),
                baseScore=round(candidate.base_score, 4),
            )
        )
    return trace


def select_answer_evidence_with_trace(
    *,
    prompt: str,
    intent: PageIntentType,
    route_decision: RouteDecisionRecord,
    evidence: list[EvidenceItem],
    page_context: PageContextPackRecord,
    db: Database | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
) -> SelectedEvidenceAuditResult:
    if not evidence:
        focus_frame = build_question_focus_frame(prompt=prompt, route_decision=route_decision, page_context=page_context)
        return SelectedEvidenceAuditResult(
            selected=[],
            question_focus_frame=focus_frame,
            decision_trace=[],
            selected_roles=[],
            unselected_high_priority_sources=[],
        )

    focus_frame = build_question_focus_frame(prompt=prompt, route_decision=route_decision, page_context=page_context)
    # P2.15 V2(answer-reading-selection): question_focus_frame 仅保留为诊断字段，
    # 不再参与 workspace/chat 主回答供料扩充或排序。
    evidence_pool = list(evidence)
    feedback_enabled = bool(
        db is not None
        and source_type
        and source_id
        and route_decision.retrievalMode != "state_only"
        and route_decision.judgmentQueryMode != "registry_only"
    )

    scored: list[_CandidateScore] = []
    for item in evidence_pool:
        adjustment = 0.0
        if feedback_enabled:
            excerpt_hash = build_evidence_excerpt_hash(
                title=item.title,
                excerpt=item.excerpt,
                path=item.path,
            )
            adjustment = get_human_quality_adjustment(
                db,
                source_type=str(source_type or ""),
                source_id=str(source_id or ""),
                document_id=item.documentId,
                excerpt_hash=excerpt_hash,
            )
        scored.append(_score_item(intent, item, prompt=prompt, focus_frame=focus_frame, human_adjustment=adjustment))

    scored.sort(key=lambda candidate: candidate.score, reverse=True)

    selected: list[EvidenceItem] = []
    seen: set[str] = set()
    # P2.14 FREEZE(answer-shaping-evidence-selection): selected_limit / max_per_doc 仍然是旧回答塑形半层
    # 对“读多少资料”的硬裁剪。当前先冻结为待拆规则，不再继续追加新的 top-N / per-doc 限流口径。
    selected_limit = 10 if route_decision.intent == "official_judgment_registry" else 24

    def _append(candidate: _CandidateScore) -> bool:
        if len(selected) >= selected_limit:
            return False
        key = _dedup_key(candidate.item)
        if key in seen:
            return False
        seen.add(key)
        selected.append(candidate.item)
        return True

    fill_candidates = list(scored)
    fill_candidates.sort(key=lambda candidate: candidate.score, reverse=True)

    for candidate in fill_candidates:
        if len(selected) >= selected_limit:
            break
        if candidate.is_noise and len(selected) >= 2:
            continue
        _append(candidate)

    selected_keys = {_dedup_key(item) for item in selected}
    decision_trace = _build_decision_trace(scored[:24], selected_keys=selected_keys)
    selected_roles = list(
        dict.fromkeys(
            role
            for candidate in scored
            if _dedup_key(candidate.item) in selected_keys
            for role in candidate.semantic_roles
        )
    )
    unselected_high_priority_sources = [
        {
            "title": trace.title,
            "path": trace.path,
            "documentId": trace.documentId,
            "semanticRoles": trace.semanticRoles,
            "sourcePriorityReason": trace.sourcePriorityReason,
            "score": trace.score,
        }
        for trace in decision_trace
        if trace.sourceFinalDecision == "not_selected"
        and trace.score > 0.9
    ][:10]

    return SelectedEvidenceAuditResult(
        selected=selected[:selected_limit],
        question_focus_frame=focus_frame,
        decision_trace=decision_trace,
        selected_roles=selected_roles,
        unselected_high_priority_sources=unselected_high_priority_sources,
    )


def select_answer_evidence(
    *,
    prompt: str,
    intent: PageIntentType,
    route_decision: RouteDecisionRecord,
    evidence: list[EvidenceItem],
    page_context: PageContextPackRecord,
    db: Database | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
) -> list[EvidenceItem]:
    result = select_answer_evidence_with_trace(
        prompt=prompt,
        intent=intent,
        route_decision=route_decision,
        evidence=evidence,
        page_context=page_context,
        db=db,
        source_type=source_type,
        source_id=source_id,
    )
    return result.selected
