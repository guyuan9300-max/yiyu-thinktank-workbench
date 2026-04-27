from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import PageContextPackRecord, RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services import query_router


def _context(*, page: str, scope_type: str, intent: str) -> PageContextPackRecord:
    return PageContextPackRecord(
        page=page,  # type: ignore[arg-type]
        scopeType=scope_type,
        scopeId="scope_x",
        clientId="client_x",
        intent=intent,  # type: ignore[arg-type]
    )


def test_business_profile_protected_from_semantic_router_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "router_protected.db")
    context = _context(page="workspace_chat", scope_type="client", intent="business_profile")

    def _should_not_run(**_kwargs):
        raise AssertionError("local semantic router should not run for protected business intent")

    monkeypatch.setattr(query_router, "route_by_local_semantic", _should_not_run)

    decision = query_router.route_page_query(
        db,
        page="workspace_chat",
        prompt="CFFC 核心业务是什么？",
        page_context=context,
        settings=RetrievalModelSettingsRecord(
            updatedAt="",
            routerEnabled=True,
            routerProvider="local_semantic",
            routerMode="semantic",
        ),
        ai_service=None,
    )

    assert decision.intent == "business_profile"
    assert decision.routeMode == "raw_doc_drilldown"
    assert decision.routerSource == "rules"


def test_generic_next_step_question_not_forced_to_task_context(tmp_path: Path):
    db = Database(tmp_path / "router_generic_next_step.db")
    context = _context(page="workspace_chat", scope_type="client", intent="general")

    decision = query_router.route_page_query(
        db,
        page="workspace_chat",
        prompt="这个战略下一步怎么推进？",
        page_context=context,
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )

    assert decision.intent != "task_next_action"
    assert decision.routeMode != "task_context"


def test_task_page_next_step_question_routes_to_task_context(tmp_path: Path):
    db = Database(tmp_path / "router_task_page.db")
    context = _context(page="task_ai", scope_type="task", intent="general")

    decision = query_router.route_page_query(
        db,
        page="task_ai",
        prompt="下一步怎么做？",
        page_context=context,
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )

    assert decision.routeMode == "task_context"
    assert decision.intent in {"task_next_action", "task_context"}
