from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import WorkspaceAnswerFinalizationRecord  # noqa: E402
from app.services.workspace_answer_experience import build_workspace_answer_experience  # noqa: E402


def test_workspace_answer_direct_answer_contract_p210_rejects_template_only_answer():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='基于当前资料，先给出可确认结论与下一步建议\n当前资料有限\n建议补齐证据',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='quality_passed',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=None,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
    )

    assert experience.directAnswer == ''
    assert experience.status == 'degraded'
    assert any('模板化' in item for item in experience.boundaryNotes)

