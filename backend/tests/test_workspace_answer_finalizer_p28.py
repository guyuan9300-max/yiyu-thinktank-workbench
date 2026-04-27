from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.workspace_answer_finalizer import (
    finalize_workspace_answer,
    normalize_workspace_evidence_status,
)


def _quality(**overrides):
    payload = {
        'grade': 'pass',
        'hasDirectAnswer': True,
        'evidenceListOnly': False,
        'officialBoundaryViolation': False,
        'candidateAsOfficialRisk': False,
        'missingRawEvidenceForIntent': False,
    }
    payload.update(overrides)
    return payload


def test_finalize_workspace_answer_pass_without_raw_gap_stays_ready():
    result = finalize_workspace_answer(
        content='当前资料足以形成一版可直接使用的业务回答。',
        answer_mode='grounded_fallback',
        failure_reason='llm_timeout',
        fallback_presentation_mode='compact_user_answer',
        kernel_result=None,
        answer_quality=_quality(grade='pass'),
        selected_evidence_count=0,
        llm_error='read timeout',
    )
    assert result.answerMode == 'grounded_answer'
    assert result.userVisibleQualityStatus == 'ready'
    assert result.shouldShowRetryBanner is False


def test_finalize_workspace_answer_warn_stays_usable_with_boundary():
    result = finalize_workspace_answer(
        content='资料已支持方向判断，但时间边界仍待确认。',
        answer_mode='grounded_fallback',
        failure_reason='partial_materials',
        fallback_presentation_mode='compact_user_answer',
        kernel_result=None,
        answer_quality=_quality(grade='warn'),
        selected_evidence_count=1,
        llm_error=None,
    )
    assert result.answerMode == 'grounded_answer'
    assert result.userVisibleQualityStatus == 'usable_with_boundary'
    assert result.shouldShowRetryBanner is False


def test_finalize_workspace_answer_partial_preserved_stays_needs_retry():
    result = finalize_workspace_answer(
        content='已保留部分正文。',
        answer_mode='grounded_fallback',
        failure_reason='llm_partial_preserved_after_retry',
        fallback_presentation_mode='full_answer',
        kernel_result=None,
        answer_quality=_quality(grade='warn'),
        selected_evidence_count=1,
        llm_error='timeout',
    )
    assert result.answerMode == 'grounded_fallback'
    assert result.userVisibleQualityStatus == 'needs_retry'
    assert result.shouldShowRetryBanner is True


def test_normalize_workspace_evidence_status_promotes_partial_to_sufficient_for_ready_grounded_answer():
    finalization = finalize_workspace_answer(
        content='当前资料足以形成一版可直接使用的业务回答。',
        answer_mode='grounded_fallback',
        failure_reason='llm_local_fallback_after_retry',
        fallback_presentation_mode='compact_user_answer',
        kernel_result=None,
        answer_quality=_quality(grade='pass'),
        selected_evidence_count=3,
        llm_error='read timeout',
    )

    evidence_status = normalize_workspace_evidence_status(
        initial_status='partial',
        finalization=finalization,
        answer_quality=_quality(grade='pass'),
        selected_evidence_count=3,
    )

    assert finalization.answerMode == 'grounded_answer'
    assert evidence_status == 'sufficient'


def test_normalize_workspace_evidence_status_keeps_partial_for_state_only_ready_answer():
    finalization = finalize_workspace_answer(
        content='当前资料足以形成一版可直接使用的状态回答。',
        answer_mode='grounded_fallback',
        failure_reason='state_only',
        fallback_presentation_mode='state_cards_only',
        kernel_result=None,
        answer_quality=_quality(grade='pass'),
        selected_evidence_count=0,
        llm_error='read timeout',
    )

    evidence_status = normalize_workspace_evidence_status(
        initial_status='partial',
        finalization=finalization,
        answer_quality=_quality(grade='pass'),
        selected_evidence_count=0,
    )

    assert finalization.answerMode == 'grounded_answer'
    assert evidence_status == 'partial'


def test_normalize_workspace_evidence_status_keeps_none_when_raw_evidence_is_missing():
    finalization = finalize_workspace_answer(
        content='目前只能给出边界明确的说明。',
        answer_mode='grounded_answer',
        failure_reason=None,
        fallback_presentation_mode='full_answer',
        kernel_result=None,
        answer_quality=_quality(grade='warn', missingRawEvidenceForIntent=True),
        selected_evidence_count=0,
        llm_error=None,
    )

    evidence_status = normalize_workspace_evidence_status(
        initial_status='none',
        finalization=finalization,
        answer_quality=_quality(grade='warn', missingRawEvidenceForIntent=True),
        selected_evidence_count=0,
    )

    assert finalization.answerMode == 'grounded_answer'
    assert evidence_status == 'none'
