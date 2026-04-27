from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import WorkspaceAnswerFinalizationRecord  # noqa: E402
from app.services.workspace_answer_experience import build_workspace_answer_experience  # noqa: E402


def test_workspace_answer_experience_no_internal_leak_p210():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='客户当前重点是推进教师赋能与数字化协同。',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='llm_failed_but_kernel_answer_passed',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=None,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
    )

    flattened = ' | '.join(experience.trustSignals)
    assert 'llm_failed_but_kernel_answer_passed' not in flattened
    assert 'generationFailureDetail' not in flattened
    assert 'RouteDecision' not in flattened

