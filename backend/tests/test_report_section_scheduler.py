"""R2 · section_scheduler 单测。

scheduler 内部调 draft_section，这里 monkeypatch 它替换为 stub，
专注测试调度行为（并行/失败回调/section_indices 子集/状态回调顺序）。
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models import (
    ChartHint,
    ReportBlueprint,
    SectionContent,
    SectionPlan,
)
from app.services import report_section_scheduler as scheduler_mod
from app.services.report_context_builder import ReportPromptContext
from app.services.report_section_drafter import SectionDraftError


def _ctx() -> ReportPromptContext:
    return ReportPromptContext(
        client_id="c", client_name="", client_intro="", client_stage="",
        event_line_id="e", event_line_name="", event_line_kind="",
        event_line_business_category="", event_line_stage="",
        event_line_summary="", event_line_intent="",
        event_line_current_blocker="", event_line_recent_decision="",
        event_line_next_step="", event_line_owner_name="",
        period_start="", period_end="", intent_hint="", audience_hint="",
        tone_hint="", entries=(), entries_truncated=False,
        total_activities=0, org_intro="", org_collaboration_relationship="",
        org_current_stage="", org_business_modules=(), org_key_people=(),
        org_current_challenges=(), org_collaboration_goals=(),
        snapshot_current_stage="", snapshot_current_work="",
        snapshot_current_blocker="", snapshot_recent_decision="",
        snapshot_next_step="",
    )


def _plan(title: str) -> SectionPlan:
    return SectionPlan(
        level=1,
        title=title,
        goal="x",
        data_sources=[],
        chart_hints=[],
        citation_budget=1,
        estimated_words=200,
    )


def _blueprint(n: int = 4) -> ReportBlueprint:
    return ReportBlueprint(
        title="测试报告",
        subtitle=None,
        report_kind="x",
        audience="x",
        tone="x",
        period_start="2026-01-01",
        period_end="2026-03-31",
        sections=[_plan(f"节 {i}") for i in range(n)],
        inferred_theme="x",
        confidence=0.8,
        open_questions_for_human=[],
        event_line_id="e",
        client_id="c",
        generated_at="2026-01-01T00:00:00Z",
    )


def _make_section_content(plan: SectionPlan) -> SectionContent:
    return SectionContent(
        plan=plan,
        markdown=f"# {plan.title}\n正文",
        citations=[],
        charts=[],
        data_source_annotation="测试",
        confidence=0.8,
        warnings=[],
    )


@pytest.mark.unit
def test_all_sections_done(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    bp = _blueprint(3)
    results = scheduler_mod.draft_sections_parallel(
        MagicMock(), blueprint=bp, context=_ctx(), max_workers=2
    )
    assert set(results.keys()) == {0, 1, 2}
    for v in results.values():
        assert isinstance(v, SectionContent)


@pytest.mark.unit
def test_partial_failure_returns_error_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        if section_idx == 1:
            raise SectionDraftError("假装挂了")
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(), blueprint=_blueprint(3), context=_ctx(), max_workers=2
    )
    assert isinstance(results[0], SectionContent)
    assert results[1] == "假装挂了"
    assert isinstance(results[2], SectionContent)


@pytest.mark.unit
def test_section_indices_subset(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(5),
        context=_ctx(),
        section_indices=[1, 3],
    )
    assert set(results.keys()) == {1, 3}


@pytest.mark.unit
def test_section_indices_out_of_range_filtered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(3),
        context=_ctx(),
        section_indices=[0, 99, -1, 2],
    )
    assert set(results.keys()) == {0, 2}


@pytest.mark.unit
def test_empty_section_indices(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(3),
        context=_ctx(),
        section_indices=[],
    )
    assert results == {}


@pytest.mark.unit
def test_progress_callback_called_for_each_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        if section_idx == 1:
            raise SectionDraftError("挂")
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    events: list[tuple[int, str]] = []

    def cb(idx, status, content, err):
        events.append((idx, status))

    scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(3),
        context=_ctx(),
        progress_cb=cb,
        max_workers=2,
    )

    drafting = [e for e in events if e[1] == "drafting"]
    done = [e for e in events if e[1] == "done"]
    failed = [e for e in events if e[1] == "failed"]
    assert {e[0] for e in drafting} == {0, 1, 2}
    assert {e[0] for e in done} == {0, 2}
    assert {e[0] for e in failed} == {1}


@pytest.mark.unit
def test_progress_cb_exception_doesnt_break_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    def bad_cb(idx, status, content, err):
        raise RuntimeError("回调挂了")

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(2),
        context=_ctx(),
        progress_cb=bad_cb,
    )
    assert set(results.keys()) == {0, 1}
    for v in results.values():
        assert isinstance(v, SectionContent)


@pytest.mark.unit
def test_max_workers_capped_by_target_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_workers=10 但只有 2 节，不应炸 thread pool。"""
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        return _make_section_content(plan)

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(2),
        context=_ctx(),
        max_workers=8,
    )
    assert set(results.keys()) == {0, 1}


@pytest.mark.unit
def test_unexpected_exception_caught_and_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 SectionDraftError 也应被接住，不让整个 scheduler 崩。"""
    def fake_draft(ai, *, plan, context, section_idx, **kwargs):
        raise ValueError("莫名其妙的错")

    monkeypatch.setattr(scheduler_mod, "draft_section", fake_draft)

    results = scheduler_mod.draft_sections_parallel(
        MagicMock(),
        blueprint=_blueprint(2),
        context=_ctx(),
    )
    assert all(isinstance(v, str) and "未预期" in v for v in results.values())
