from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import AnswerPolicyRecord, PageContextPackRecord, RouteDecisionRecord
from app.services.answer_layer import build_answer_material, build_answer_plan
from app.services.data_center_quality import validate_answer_quality
from app.services.query_router import route_page_query


def _official_context(*, has_official: bool) -> PageContextPackRecord:
    return PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_boundary",
        clientId="client_boundary",
        intent="official_judgment_registry",
        officialJudgments=(
            [{"id": "oj_1", "summary": "已批准：当前主线聚焦能力建设与生态协作"}]
            if has_official
            else []
        ),
        candidateJudgments=[{"id": "cj_1", "summary": "候选：数字化方向待确认"}],
        boundaryNotes=["候选判断只能作为待确认线索。"],
    )


def test_official_route_is_registry_only_and_no_raw(tmp_path: Path):
    db = Database(tmp_path / "official_route.db")
    context = _official_context(has_official=True)

    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        settings=None,
        ai_service=None,
    )

    assert decision.intent == "official_judgment_registry"
    assert decision.routeMode == "registry_only"
    assert decision.shouldUseRawEvidence is False


def test_official_answer_without_approved_discloses_candidate_boundary():
    context = _official_context(has_official=False)
    route_decision = RouteDecisionRecord(
        intent="official_judgment_registry",
        routeMode="registry_only",
        dataSources=["judgment_registry"],
        retrievalMode="state_only",
        shouldUseRawEvidence=False,
        rerankNeeded=False,
    )
    plan = build_answer_plan(
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        route_decision=route_decision,
        answer_policy=AnswerPolicyRecord(),
    )
    material = build_answer_material(
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        route_decision=route_decision,
        retrieval_evidence=[],
        answer_plan=plan,
    )

    assert "没有已批准正式判断" in material.directAnswerSeed
    quality = validate_answer_quality(
        prompt="系统里已批准的正式判断有哪些？",
        content=material.directAnswerSeed,
        answer_plan=plan,
        evidence=[],
        answer_material=material,
    )
    assert quality["officialBoundaryViolation"] is False
    assert quality["candidateAsOfficialRisk"] is False


def test_candidate_written_as_official_is_blocked_by_quality_gate():
    context = _official_context(has_official=False)
    route_decision = RouteDecisionRecord(
        intent="official_judgment_registry",
        routeMode="registry_only",
        dataSources=["judgment_registry"],
        retrievalMode="state_only",
        shouldUseRawEvidence=False,
        rerankNeeded=False,
    )
    plan = build_answer_plan(
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        route_decision=route_decision,
        answer_policy=AnswerPolicyRecord(),
    )
    material = build_answer_material(
        prompt="系统里已批准的正式判断有哪些？",
        page_context=context,
        route_decision=route_decision,
        retrieval_evidence=[],
        answer_plan=plan,
    )

    bad_content = "已批准正式判断如下：候选判断A、候选判断B。"
    quality = validate_answer_quality(
        prompt="系统里已批准的正式判断有哪些？",
        content=bad_content,
        answer_plan=plan,
        evidence=[],
        answer_material=material,
    )

    assert quality["officialBoundaryViolation"] is True
    assert quality["grade"] == "fail"
