"""R2 · section_drafter 单测（mock LLM + 真实 chart_materializer）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models import ChartHint, SectionContent, SectionPlan
from app.services.report_context_builder import ReportPromptContext
from app.services.report_section_drafter import (
    SectionDraftError,
    draft_section,
)


def _empty_context() -> ReportPromptContext:
    return ReportPromptContext(
        client_id="cli-1",
        client_name="客户 A",
        client_intro="",
        client_stage="",
        event_line_id="el-1",
        event_line_name="事件线",
        event_line_kind="",
        event_line_business_category="",
        event_line_stage="",
        event_line_summary="",
        event_line_intent="",
        event_line_current_blocker="",
        event_line_recent_decision="",
        event_line_next_step="",
        event_line_owner_name="",
        period_start="2026-01-01",
        period_end="2026-03-31",
        intent_hint="",
        audience_hint="",
        tone_hint="",
        entries=(),
        entries_truncated=False,
        total_activities=0,
        org_intro="",
        org_collaboration_relationship="",
        org_current_stage="",
        org_business_modules=(),
        org_key_people=(),
        org_current_challenges=(),
        org_collaboration_goals=(),
        snapshot_current_stage="",
        snapshot_current_work="",
        snapshot_current_blocker="",
        snapshot_recent_decision="",
        snapshot_next_step="",
    )


def _plan_with_timeline() -> SectionPlan:
    return SectionPlan(
        level=1,
        title="Q1 总览",
        goal="梳理本期事件线的整体进展与关键节点",
        data_sources=["events"],
        chart_hints=[
            ChartHint(
                kind="timeline",
                title="Q1 时间线",
                caption="节奏图",
                data_source_hint="events",
            )
        ],
        citation_budget=3,
        estimated_words=300,
    )


def _valid_llm_section_payload() -> dict:
    return {
        "markdown": (
            "本季事件线整体推进顺利。\n\n[CHART:0]\n\n"
            "重点节点已 100% 完成，下一步聚焦 Q2 规划。"
        ),
        "citations": [
            {
                "type": "event",
                "id": "act-001",
                "label": "1月10日 Q1 启动会",
                "excerpt": "确定 Q1 三大主题",
            }
        ],
        "charts": [
            {
                "chart_hint_idx": 0,
                "data": {
                    "events": [
                        ["2026-01-10", "启动会", "done"],
                        ["2026-02-15", "中期检视", "done"],
                        ["2026-03-25", "Q1 收尾", "in_progress"],
                    ]
                },
            }
        ],
        "data_source_annotation": "本节数据源：事件线活动 act-001..act-024",
        "confidence": 0.85,
        "warnings": [],
    }


@pytest.mark.unit
def test_happy_path_with_chart() -> None:
    ai = MagicMock()
    ai._qwen_generate.return_value = _valid_llm_section_payload()

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="报告",
        blueprint_audience="决策层",
        blueprint_tone="客观",
        section_idx=0,
    )

    assert isinstance(content, SectionContent)
    assert "[CHART:0]" in content.markdown
    assert len(content.citations) == 1
    assert content.citations[0].type == "event"
    assert len(content.charts) == 1
    assert content.charts[0].png_bytes_base64
    assert content.confidence == 0.85
    assert content.warnings == []
    assert "事件线活动" in content.data_source_annotation


@pytest.mark.unit
def test_retry_on_empty_markdown() -> None:
    ai = MagicMock()
    bad = _valid_llm_section_payload()
    bad["markdown"] = ""
    ai._qwen_generate.side_effect = [bad, _valid_llm_section_payload()]

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="报告",
        blueprint_audience="决策层",
        blueprint_tone="客观",
        section_idx=0,
    )
    assert content.markdown
    assert ai._qwen_generate.call_count == 2


@pytest.mark.unit
def test_retry_on_call_exception() -> None:
    ai = MagicMock()
    ai._qwen_generate.side_effect = [
        RuntimeError("豆包暂时不可用"),
        _valid_llm_section_payload(),
    ]

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="报告",
        blueprint_audience="决策层",
        blueprint_tone="客观",
        section_idx=0,
    )
    assert isinstance(content, SectionContent)
    assert ai._qwen_generate.call_count == 2


@pytest.mark.unit
def test_all_retries_fail() -> None:
    ai = MagicMock()
    ai._qwen_generate.side_effect = RuntimeError("一直挂")

    with pytest.raises(SectionDraftError):
        draft_section(
            ai,
            plan=_plan_with_timeline(),
            context=_empty_context(),
            blueprint_title="x",
            blueprint_audience="x",
            blueprint_tone="x",
            section_idx=2,
            max_retries=3,
        )
    assert ai._qwen_generate.call_count == 3


@pytest.mark.unit
def test_chart_data_missing_records_warning_but_returns_section() -> None:
    """LLM 写了 markdown 但漏给某个 chart_hint 的数据，
    不应让整节失败，应记 warning 并留空 base64。"""
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["charts"] = []  # 漏了 chart
    ai._qwen_generate.return_value = payload

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    assert len(content.charts) == 1
    assert content.charts[0].png_bytes_base64 == ""
    assert any("缺少 LLM 数据" in w for w in content.warnings)


@pytest.mark.unit
def test_chart_generation_failure_records_warning() -> None:
    """LLM 给的数据形状不对（pie counts 全 0），应记 warning，不让整节失败。"""
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["charts"] = [
        {"chart_hint_idx": 0, "data": {"labels": ["A"], "counts": [0]}}
    ]
    ai._qwen_generate.return_value = payload

    plan_with_pie = SectionPlan(
        level=1,
        title="占比",
        goal="X",
        data_sources=[],
        chart_hints=[
            ChartHint(
                kind="pie",
                title="占比",
                caption=None,
                data_source_hint="x",
            )
        ],
        citation_budget=2,
        estimated_words=200,
    )

    content = draft_section(
        ai,
        plan=plan_with_pie,
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    assert content.charts[0].png_bytes_base64 == ""
    assert any("生成失败" in w for w in content.warnings)


@pytest.mark.unit
def test_invalid_citation_type_dropped() -> None:
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["citations"] = [
        {"type": "rumor", "id": "x", "label": "y"},  # 非法 type 应被丢
        {"type": "event", "id": "a", "label": "A"},
    ]
    ai._qwen_generate.return_value = payload

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    types = [c.type for c in content.citations]
    assert "rumor" not in types
    assert "event" in types


@pytest.mark.unit
def test_confidence_clamped_to_unit_interval() -> None:
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["confidence"] = 1.6
    ai._qwen_generate.return_value = payload

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    assert content.confidence == 1.0


@pytest.mark.unit
def test_no_chart_hints_no_charts_returned() -> None:
    plan = SectionPlan(
        level=1,
        title="纯文本节",
        goal="X",
        data_sources=[],
        chart_hints=[],
        citation_budget=1,
        estimated_words=200,
    )
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["charts"] = []
    ai._qwen_generate.return_value = payload

    content = draft_section(
        ai,
        plan=plan,
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    assert content.charts == []
    assert all("chart" not in w.lower() for w in content.warnings)


@pytest.mark.unit
def test_chart_hint_idx_out_of_range_ignored() -> None:
    """LLM 给了 chart_hint_idx=5 但只有 1 个 hint，应忽略不报错。"""
    ai = MagicMock()
    payload = _valid_llm_section_payload()
    payload["charts"].append(
        {"chart_hint_idx": 99, "data": {"events": [["d", "l", "done"]]}}
    )
    ai._qwen_generate.return_value = payload

    content = draft_section(
        ai,
        plan=_plan_with_timeline(),
        context=_empty_context(),
        blueprint_title="x",
        blueprint_audience="x",
        blueprint_tone="x",
        section_idx=0,
    )
    assert len(content.charts) == 1  # 仍只 materialize 第一个
