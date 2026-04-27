from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import AnswerPolicyRecord, PageContextPackRecord, RouteDecisionRecord
from app.services.analysis_context import infer_page_intent
from app.services.answer_layer import build_answer_plan
from app.services.question_focus import build_question_focus_frame
from app.services.query_router import route_page_query
from app.services.workspace_query_router import route_workspace_query


def test_workspace_query_router_no_longer_forces_work_status_short_synthesis() -> None:
    route = route_workspace_query(
        prompt="介绍日慈基金会，不要展开风险和下一步建议。",
        client_id="client_test",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "consultant_synthesis"
    assert route.intent == "consultant_synthesis"


def test_intro_prompt_with_meeting_words_keeps_intro_for_retrieval_classification() -> None:
    intent = infer_page_intent(
        "介绍日慈基金会，但不要写成会议纪要或状态汇报。",
        "workspace_chat",
    )
    assert intent.intent == "general"
    assert intent.routeReason == "workspace_chat_open_intent"
    assert intent.requiresRawEvidence is False


def test_route_page_query_can_still_classify_intro_but_answer_plan_is_open() -> None:
    decision = route_page_query(
        None,
        page="workspace_chat",
        prompt="介绍日慈基金会，它是怎么做这件事的？",
        page_context=PageContextPackRecord(
            page="workspace_chat",
            scopeType="client",
            scopeId="client_test",
            clientId="client_test",
            intent="task_next_action",
        ),
    )
    assert decision.intent == "general"
    assert decision.routeMode == "hybrid"
    assert decision.retrievalMode == "hybrid"

    plan = build_answer_plan(
        prompt="介绍日慈基金会，它是怎么做这件事的？",
        page_context=PageContextPackRecord(
            page="workspace_chat",
            scopeType="client",
            scopeId="client_test",
            clientId="client_test",
            intent="general",
        ),
        route_decision=RouteDecisionRecord(
            intent="general",
            routeMode="hybrid",
            dataSources=["raw_docs", "document_cards", "meetings", "state_pool"],
            retrievalMode="hybrid",
        ),
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    assert plan.answerShape == "open_answer"
    assert plan.requiredSections == []
    assert plan.maxAnswerChars == 5200


def test_question_focus_remains_diagnostic_not_shortening_switch() -> None:
    frame = build_question_focus_frame(
        prompt="介绍日慈基金会，按顺序回答它是什么样的机构、它是怎么做这件事的、它有哪些主要业务线。",
        route_decision=RouteDecisionRecord(
            intent="general",
            routeMode="hybrid",
            dataSources=["raw_docs", "document_cards"],
            retrievalMode="hybrid",
        ),
        page_context=None,
    )
    assert frame.goal == "explain"
    assert frame.subjectFacet == "general"
