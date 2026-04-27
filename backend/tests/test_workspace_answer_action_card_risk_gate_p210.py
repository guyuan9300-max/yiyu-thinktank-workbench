from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import ActionSuggestionRecord, DataCenterProposalDraftRecord, WorkspaceAnswerFinalizationRecord  # noqa: E402
from app.services.workspace_answer_experience import build_workspace_answer_experience  # noqa: E402


def test_workspace_answer_action_card_risk_gate_p210():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='建议先补证据，再形成正式提案。',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='quality_passed',
    )
    low = ActionSuggestionRecord(
        id='low_1',
        actionType='request_evidence',
        title='补证据',
        summary='补齐材料',
        rationale='低风险动作',
        riskLevel='low',
    )
    medium = DataCenterProposalDraftRecord(
        id='draft_medium',
        kind='judgment_review',
        title='生成提案草稿',
        summary='中风险需复核',
        rationale='中风险',
        riskLevel='medium',
    )
    high = ActionSuggestionRecord(
        id='high_1',
        actionType='create_task',
        title='高风险任务',
        summary='高风险动作',
        rationale='高风险',
        riskLevel='high',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=None,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
        proposal_drafts=[medium],
        action_suggestions=[low, high],
    )

    by_title = {item.title: item for item in experience.actionCards}
    assert by_title['补证据'].enabled is True
    assert by_title['生成提案草稿'].enabled is True
    assert by_title['高风险任务'].enabled is False
    assert '人工复核' in by_title['高风险任务'].disabledReason
