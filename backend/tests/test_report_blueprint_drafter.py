"""R1 · report_blueprint_drafter 单测（mock LLM）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models import ReportBlueprint
from app.services.report_blueprint_drafter import (
    BlueprintDraftError,
    _normalize_blueprint_payload,
    draft_report_blueprint,
)
from app.services.report_context_builder import ReportPromptContext


def _make_ctx(
    *,
    client_id: str = "client-1",
    client_name: str = "客户 A",
    event_line_id: str = "el-1",
    event_line_name: str = "事件线",
    period_start: str = "2026-01-01",
    period_end: str = "2026-03-31",
) -> ReportPromptContext:
    return ReportPromptContext(
        client_id=client_id,
        client_name=client_name,
        client_intro="",
        client_stage="",
        event_line_id=event_line_id,
        event_line_name=event_line_name,
        event_line_kind="custom",
        event_line_business_category="",
        event_line_stage="",
        event_line_summary="",
        event_line_intent="",
        event_line_current_blocker="",
        event_line_recent_decision="",
        event_line_next_step="",
        event_line_owner_name="",
        period_start=period_start,
        period_end=period_end,
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


def _valid_llm_payload(**overrides) -> dict:
    base = {
        "title": "客户 A · 战略陪伴季报",
        "subtitle": "Q1 复盘与下一步",
        "report_kind": "战略陪伴季报",
        "audience": "客户决策层",
        "tone": "客观、克制、可执行",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "inferred_theme": "Q1 重点工作的进展与判断",
        "confidence": 0.82,
        "open_questions_for_human": ["是否要披露具体经费数字？"],
        "sections": [
            {
                "level": 1,
                "title": "总览",
                "goal": "建立全局画像",
                "data_sources": ["events", "snapshot"],
                "chart_hints": [
                    {
                        "kind": "timeline",
                        "title": "Q1 时间线",
                        "caption": "节奏图",
                        "data_source_hint": "event_line_activities",
                    }
                ],
                "citation_budget": 5,
                "estimated_words": 400,
            },
            {
                "level": 1,
                "title": "主理人判断",
                "goal": "提炼洞察",
                "data_sources": ["judgments"],
                "chart_hints": [],
                "citation_budget": 4,
                "estimated_words": 350,
            },
            {
                "level": 1,
                "title": "下一步",
                "goal": "落地建议",
                "data_sources": ["tasks"],
                "chart_hints": [],
                "citation_budget": 3,
                "estimated_words": 250,
            },
        ],
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_happy_path() -> None:
    ai = MagicMock()
    ai._qwen_generate.return_value = _valid_llm_payload()
    ctx = _make_ctx()

    blueprint = draft_report_blueprint(ai, context=ctx)

    assert isinstance(blueprint, ReportBlueprint)
    assert blueprint.title == "客户 A · 战略陪伴季报"
    assert blueprint.client_id == "client-1"
    assert blueprint.event_line_id == "el-1"
    assert len(blueprint.sections) == 3
    assert blueprint.sections[0].chart_hints[0].kind == "timeline"
    assert ai._qwen_generate.call_count == 1


@pytest.mark.unit
def test_retry_on_non_dict_returns() -> None:
    ai = MagicMock()
    ai._qwen_generate.side_effect = [
        "not a dict",
        _valid_llm_payload(),
    ]
    ctx = _make_ctx()

    blueprint = draft_report_blueprint(ai, context=ctx)
    assert blueprint.title == "客户 A · 战略陪伴季报"
    assert ai._qwen_generate.call_count == 2


@pytest.mark.unit
def test_retry_on_call_exception() -> None:
    ai = MagicMock()
    ai._qwen_generate.side_effect = [
        RuntimeError("豆包暂时不可用"),
        _valid_llm_payload(),
    ]
    ctx = _make_ctx()

    blueprint = draft_report_blueprint(ai, context=ctx)
    assert isinstance(blueprint, ReportBlueprint)
    assert ai._qwen_generate.call_count == 2


@pytest.mark.unit
def test_all_retries_fail() -> None:
    ai = MagicMock()
    ai._qwen_generate.side_effect = RuntimeError("一直挂")
    ctx = _make_ctx()

    with pytest.raises(BlueprintDraftError):
        draft_report_blueprint(ai, context=ctx, max_retries=3)
    assert ai._qwen_generate.call_count == 3


@pytest.mark.unit
def test_normalize_clamps_confidence_above_1() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload(confidence=1.7)
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["confidence"] == 1.0


@pytest.mark.unit
def test_normalize_clamps_confidence_below_0() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload(confidence=-0.3)
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["confidence"] == 0.0


@pytest.mark.unit
def test_normalize_handles_string_confidence() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload(confidence="bad")
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["confidence"] == 0.7


@pytest.mark.unit
def test_normalize_drops_invalid_chart_kind() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload()
    payload["sections"][0]["chart_hints"].append(
        {"kind": "rainbow_3d", "title": "玄学", "data_source_hint": "x"}
    )
    norm = _normalize_blueprint_payload(payload, ctx)
    kinds = [c["kind"] for c in norm["sections"][0]["chart_hints"]]
    assert "rainbow_3d" not in kinds
    assert "timeline" in kinds


@pytest.mark.unit
def test_normalize_clamps_estimated_words() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload()
    payload["sections"][0]["estimated_words"] = 5000  # 上限 2000
    payload["sections"][1]["estimated_words"] = 10     # 下限 50
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["sections"][0]["estimated_words"] == 2000
    assert norm["sections"][1]["estimated_words"] == 50


@pytest.mark.unit
def test_normalize_fallback_when_no_sections() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload(sections=[])
    norm = _normalize_blueprint_payload(payload, ctx)
    # 没有 sections 时应该补一个最小骨架
    assert len(norm["sections"]) >= 3
    assert any("概览" in s["title"] for s in norm["sections"])


@pytest.mark.unit
def test_normalize_truncates_more_than_seven_sections() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload()
    payload["sections"] = [
        {
            "level": 1,
            "title": f"章节 {i}",
            "goal": "x",
            "data_sources": [],
            "chart_hints": [],
            "citation_budget": 1,
            "estimated_words": 100,
        }
        for i in range(10)
    ]
    norm = _normalize_blueprint_payload(payload, ctx)
    assert len(norm["sections"]) == 7


@pytest.mark.unit
def test_normalize_drops_section_with_no_title() -> None:
    ctx = _make_ctx()
    payload = _valid_llm_payload()
    payload["sections"][0]["title"] = ""
    norm = _normalize_blueprint_payload(payload, ctx)
    assert all(s["title"] for s in norm["sections"])
    assert len(norm["sections"]) == 2


@pytest.mark.unit
def test_normalize_injects_context_ids() -> None:
    ctx = _make_ctx(client_id="cli-X", event_line_id="el-X")
    payload = _valid_llm_payload()
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["client_id"] == "cli-X"
    assert norm["event_line_id"] == "el-X"
    assert norm["generated_at"]  # ISO 时间戳非空


@pytest.mark.unit
def test_normalize_event_line_id_none_when_empty() -> None:
    ctx = _make_ctx(event_line_id="")
    payload = _valid_llm_payload()
    norm = _normalize_blueprint_payload(payload, ctx)
    assert norm["event_line_id"] is None
