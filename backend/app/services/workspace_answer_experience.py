from __future__ import annotations

import re

from app.models import (
    ActionSuggestionRecord,
    AnswerMaterialRecord,
    DataCenterProposalDraftRecord,
    WorkspaceAnswerActionCardRecord,
    WorkspaceAnswerEvidenceChipRecord,
    WorkspaceAnswerExperienceRecord,
    WorkspaceAnswerFinalizationRecord,
)
from app.services.answer_layer import (
    should_include_answer_action_cards,
    should_include_answer_boundary,
    should_include_answer_next_actions,
)


_GENERIC_DIRECT_ANSWER_MARKERS = [
    "基于当前资料，先给出可确认结论与下一步建议",
    "当前资料有限",
    "建议补齐证据",
    "建议补充资料",
    "以下是相关信息",
    "当前仅能确认有限线索",
    "请先用一两句话写清这个机构是什么、核心议题是什么",
]


def _looks_generic_direct_answer(text: str) -> bool:
    compact = _clean_text(text, limit=320)
    if not compact:
        return True
    return any(marker in compact for marker in _GENERIC_DIRECT_ANSWER_MARKERS)


def _clean_text(value: object, *, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _select_direct_answer(
    *,
    content: str,
    answer_material: AnswerMaterialRecord | None,
    answer_presentation: dict[str, object] | None,
) -> str:
    if answer_material is not None:
        candidate = _clean_text(answer_material.directAnswerSeed, limit=320)
        if candidate and not _looks_generic_direct_answer(candidate):
            return candidate
    if isinstance(answer_presentation, dict):
        sections = answer_presentation.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue
                if str(section.get("title") or "").strip() != "直接回答":
                    continue
                candidate = _clean_text(section.get("content") or "", limit=320)
                if candidate and not _looks_generic_direct_answer(candidate):
                    return candidate
    lines = [item.strip() for item in str(content or "").splitlines() if item.strip()]
    for line in lines:
        candidate = _clean_text(line, limit=320)
        if candidate and candidate not in _GENERIC_DIRECT_ANSWER_MARKERS:
            return candidate
    return _clean_text(content, limit=320)


def is_template_like_direct_answer(text: str) -> bool:
    compact = _clean_text(text, limit=320)
    return _looks_generic_direct_answer(compact)


def _chip_quality_label(source_type: str, excerpt: str) -> str:
    normalized = str(source_type or "").strip().lower()
    if normalized in {"judgment", "official_judgment"}:
        return "high"
    if normalized in {"meeting", "knowledge_chunk", "knowledge_document", "document"}:
        return "medium"
    if normalized in {"candidate_judgment", "topic_candidate"}:
        return "low"
    if not str(excerpt or "").strip():
        return "noise"
    return "medium"


def _build_evidence_chips(answer_material: AnswerMaterialRecord | None) -> list[WorkspaceAnswerEvidenceChipRecord]:
    if answer_material is None:
        return []
    chips: list[WorkspaceAnswerEvidenceChipRecord] = []
    for item in answer_material.evidenceHighlights[:5]:
        title = _clean_text(item.title or "", limit=120) or "资料片段"
        excerpt = _clean_text(item.excerpt or "", limit=180)
        source_kind = _clean_text(item.sectionLabel or item.retrievalStage or item.sourceType or "", limit=64)
        chips.append(
            WorkspaceAnswerEvidenceChipRecord(
                id=str(item.id or ""),
                title=title,
                sourceType=str(item.sourceType or ""),
                sourceKind=source_kind,
                excerpt=excerpt,
                qualityLabel=_chip_quality_label(str(item.sourceType or ""), excerpt),  # type: ignore[arg-type]
                documentId=item.documentId,
                path=item.path,
            )
        )
    return chips


def _map_draft_to_action_card(draft: DataCenterProposalDraftRecord) -> WorkspaceAnswerActionCardRecord:
    title = _clean_text(draft.title, limit=80) or "生成提案"
    summary = _clean_text(draft.summary or draft.rationale, limit=140)
    action_type = "create_proposal"
    if draft.kind == "evidence_request":
        action_type = "request_evidence"
    elif draft.kind == "judgment_review":
        action_type = "review_judgment"
    elif draft.kind == "context_refresh":
        action_type = "refresh_context"
    elif draft.kind in {"meeting_prep", "meeting_followup"}:
        action_type = "prepare_meeting"
    return WorkspaceAnswerActionCardRecord(
        actionType=action_type,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        riskLevel=draft.riskLevel,
        draftId=draft.id,
        proposalId=draft.promotedProposalId,
    )


def _map_suggestion_to_action_card(suggestion: ActionSuggestionRecord) -> WorkspaceAnswerActionCardRecord | None:
    action_map = {
        "create_proposal": "create_proposal",
        "create_task": "create_task",
        "request_evidence": "request_evidence",
        "confirm_candidate_judgment": "review_judgment",
        "refresh_context_pack": "refresh_context",
        "prepare_meeting": "prepare_meeting",
    }
    mapped = action_map.get(suggestion.actionType)
    if not mapped:
        return None
    return WorkspaceAnswerActionCardRecord(
        actionType=mapped,  # type: ignore[arg-type]
        title=_clean_text(suggestion.title, limit=80) or suggestion.actionType,
        summary=_clean_text(suggestion.summary or suggestion.rationale, limit=140),
        riskLevel=suggestion.riskLevel,
    )


def _apply_action_card_risk_gate(card: WorkspaceAnswerActionCardRecord) -> WorkspaceAnswerActionCardRecord:
    if card.riskLevel == "high":
        return card.model_copy(
            update={
                "enabled": False,
                "disabledReason": "高风险动作需进入 Proposal Inbox 人工复核。",
            }
        )

    if card.riskLevel == "medium":
        enabled = card.actionType in {"create_proposal", "review_judgment", "prepare_meeting"}
        return card.model_copy(
            update={
                "enabled": enabled,
                "disabledReason": "" if enabled else "中风险动作请先生成 proposal 草稿，再由人工复核。",
            }
        )

    enabled = card.actionType in {"create_task", "request_evidence", "refresh_context", "create_proposal"}
    return card.model_copy(
        update={
            "enabled": enabled,
            "disabledReason": "" if enabled else "该动作需要先进入 proposal 草稿再继续。",
        }
    )


def build_workspace_answer_experience(
    *,
    content: str,
    finalization: WorkspaceAnswerFinalizationRecord,
    answer_material: AnswerMaterialRecord | None,
    answer_quality: dict[str, object] | None,
    proposal_drafts: list[DataCenterProposalDraftRecord] | None = None,
    action_suggestions: list[ActionSuggestionRecord] | None = None,
    answer_presentation: dict[str, object] | None = None,
    answer_intent: str | None = None,
) -> WorkspaceAnswerExperienceRecord:
    status = finalization.userVisibleQualityStatus
    # P2.12 FREEZE(answer-experience): 当前 headline / userMessage / trustSignals
    # 直接决定客户工作台如何解释一条回答的质量状态。
    # 运行态验证期先冻结，避免回答能跑出来但展示语义持续漂移。
    headline_map = {
        "ready": "已形成可用回答",
        "usable_with_boundary": "已形成可用回答，但部分内容需留意边界",
        "degraded": "当前回答可作线索参考",
        "needs_retry": "本轮没有形成可靠答案",
    }
    user_message_map = {
        "ready": "",
        "usable_with_boundary": "以下回答已基于客户资料生成，部分判断仍保留候选或资料边界。",
        "degraded": "证据或上下文仍不足，建议补资料后复核。",
        "needs_retry": "建议重试或补充资料。",
    }

    direct_answer = _select_direct_answer(
        content=content,
        answer_material=answer_material,
        answer_presentation=answer_presentation,
    )
    direct_answer_template_like = is_template_like_direct_answer(direct_answer)
    evidence_chips = _build_evidence_chips(answer_material)
    key_points = []
    if answer_material is not None:
        key_points = [
            _clean_text(item, limit=120)
            for item in [*answer_material.keyFacts[:3], *answer_material.structuredPoints[:3]]
            if _clean_text(item, limit=120)
        ][:5]
    boundary_notes = []
    next_actions = []
    if answer_material is not None:
        if should_include_answer_boundary(answer_intent):
            boundary_notes = [
                _clean_text(item, limit=120)
                for item in [*answer_material.boundaryNotes[:4], *answer_material.missingContext[:4]]
                if _clean_text(item, limit=120)
            ][:6]
        if should_include_answer_next_actions(answer_intent):
            next_actions = [_clean_text(item, limit=120) for item in answer_material.nextActions[:5] if _clean_text(item, limit=120)]

    if direct_answer_template_like:
        direct_answer = ""
        if status in {"ready", "usable_with_boundary"}:
            status = "degraded"
        template_note = "直接回答仍偏模板化，建议补充客户事实或证据后复核。"
        if template_note not in boundary_notes:
            boundary_notes.append(template_note)

    action_cards: list[WorkspaceAnswerActionCardRecord] = []
    seen_cards: set[tuple[str, str, str]] = set()
    if should_include_answer_action_cards(answer_intent):
        for draft in proposal_drafts or []:
            card = _map_draft_to_action_card(draft)
            key = (card.actionType, card.title, card.draftId or "")
            if key in seen_cards:
                continue
            seen_cards.add(key)
            action_cards.append(_apply_action_card_risk_gate(card))
        for suggestion in action_suggestions or []:
            card = _map_suggestion_to_action_card(suggestion)
            if card is None:
                continue
            key = (card.actionType, card.title, card.draftId or "")
            if key in seen_cards:
                continue
            seen_cards.add(key)
            action_cards.append(_apply_action_card_risk_gate(card))

    trust_signals: list[str] = []
    if evidence_chips:
        trust_signals.append("已命中高质量证据")
    if not bool((answer_quality or {}).get("officialBoundaryViolation")) and not bool((answer_quality or {}).get("candidateAsOfficialRisk")):
        trust_signals.append("已通过边界检查")
    if evidence_chips or direct_answer:
        trust_signals.append("已引用客户资料")
    if boundary_notes:
        trust_signals.append("包含候选边界说明")
    if next_actions:
        trust_signals.append("包含下一步建议")

    return WorkspaceAnswerExperienceRecord(
        status=status,
        headline=headline_map.get(status, "已形成可用回答"),
        directAnswer=direct_answer,
        keyPoints=key_points,
        evidenceChips=evidence_chips,
        boundaryNotes=boundary_notes,
        nextActions=next_actions,
        actionCards=action_cards[:6],
        trustSignals=trust_signals[:4],
        userMessage=user_message_map.get(status, ""),
    )
