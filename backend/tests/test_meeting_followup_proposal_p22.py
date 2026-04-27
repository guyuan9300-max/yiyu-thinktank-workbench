from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import PageContextPackRecord
from app.services.meeting_followup import build_meeting_followup_proposal_drafts


def test_meeting_followup_proposals_from_context_signals():
    meeting_context = PageContextPackRecord(
        page="meeting_detail",
        scopeType="meeting",
        scopeId="meeting_x",
        clientId="client_x",
        intent="meeting_summary",
        relatedTasks=[{"id": "task_1", "title": "整理会议纪要行动项"}],
        conflicts=[{"id": "risk_1", "summary": "负责人未明确"}],
        openQuestions=[{"id": "q_1", "question": "预算来源待确认"}],
        candidateJudgments=[{"id": "j_1", "summary": "建议优先推进A路线"}],
        officialJudgments=[],
        boundaryNotes=["会后建议需审批后执行"],
    )

    drafts = build_meeting_followup_proposal_drafts(meeting_context=meeting_context)
    kinds = {item.kind for item in drafts}
    assert "meeting_followup" in kinds
    assert "evidence_request" in kinds
    assert "judgment_review" in kinds

    for draft in drafts:
        assert draft.requiresApproval is True
        assert draft.targetRefs
