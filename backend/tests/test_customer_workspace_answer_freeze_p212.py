from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import AnswerPolicyRecord, PageContextPackRecord, RouteDecisionRecord
from app.services.answer_layer import build_answer_material, build_answer_plan, build_grounded_answer_context
from app.services.question_focus import build_question_focus_frame


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def test_main_answer_chain_no_longer_uses_profile_frame() -> None:
    page_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_test",
        clientId="client_test",
        intent="general",
    )
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards", "meetings"],
        retrievalMode="hybrid",
    )
    plan = build_answer_plan(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
    )
    assert plan.answerShape == "open_answer"
    assert plan.requiredSections == []
    assert plan.mustDiscloseBoundary is False

    material = build_answer_material(
        prompt="介绍日慈基金会",
        page_context=page_context,
        route_decision=route,
        retrieval_evidence=[],
        answer_plan=plan,
    )
    context = build_grounded_answer_context(
        answer_plan=plan,
        answer_material=material,
        prompt="介绍日慈基金会",
    )
    assert "把答案写成组织画像" not in context
    assert "【回答结构】" not in context
    assert "【写作要求】" not in context
    assert "【边界说明】" not in context


def test_question_focus_can_stay_for_diagnostics_but_not_answer_template() -> None:
    route = RouteDecisionRecord(
        intent="general",
        routeMode="hybrid",
        dataSources=["raw_docs", "document_cards"],
        retrievalMode="hybrid",
    )
    frame = build_question_focus_frame(
        prompt="介绍日慈基金会",
        route_decision=route,
        page_context=None,
    )
    assert frame.goal == "explain"
    assert frame.subjectFacet == "general"


def test_source_files_no_longer_contain_profile_draft_scaffolds() -> None:
    answer_layer = _read("backend/app/services/answer_layer.py")
    adapter = _read("backend/app/services/workspace_data_center_adapter.py")
    main_source = _read("backend/app/main.py")

    assert "【回答结构】" not in answer_layer
    assert "【直接答案种子】" not in answer_layer
    assert "把答案写成组织画像" not in answer_layer

    assert "【组织画像目标】" not in adapter
    assert "【组织画像参考草稿】" not in adapter

    assert "success_path_scaffold" not in main_source
