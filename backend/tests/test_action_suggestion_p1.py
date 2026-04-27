from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    AnswerMaterialRecord,
    AnswerPolicyRecord,
    ContextQualityRecord,
    PageContextPackRecord,
    RouteDecisionRecord,
)
from app.services.action_suggestion_service import build_action_suggestions


def test_action_suggestions_include_request_and_confirm_and_refresh():
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_a",
        clientId="client_a",
        intent="business_profile",
        candidateJudgments=[{"id": "j1", "summary": "候选判断"}],
        officialJudgments=[],
        missingContext=["缺少关键材料"],
        quality=ContextQualityRecord(contextQuality="weak"),
    )
    route = RouteDecisionRecord(intent="business_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid")
    material = AnswerMaterialRecord(missingContext=["缺少关键材料"])
    policy = AnswerPolicyRecord(answerLevel="candidate", shouldCreateProposal=True)

    actions = build_action_suggestions(
        page_context=page_context,
        route_decision=route,
        answer_policy=policy,
        answer_material=material,
    )
    action_types = {item.actionType for item in actions}
    assert "request_evidence" in action_types
    assert "confirm_candidate_judgment" in action_types
    assert "refresh_context_pack" in action_types
