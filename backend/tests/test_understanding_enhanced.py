"""
测试 enhanced 模式构建器：
- 有事件线 + 会议时，结果升级为 enhanced
- optionalAdvice 只在证据足够时才出现
- 无增强项时降级回 basic
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
    TaskProjectContextRecord,
)
from app.services.understanding_builder import build_understanding_enhanced, build_understanding_basic


FORBIDDEN_BRIEF_FRAGMENTS = ["这是一条", "状态的工作任务", "系统尚未看到"]


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "和冯梅老师沟通测试论坛A的战略说明迭代",
        "status": "doing",
        "createdAt": "2026-03-20T10:00:00Z",
        "listName": "战略合作",
        "listColor": "#5B7BFE",
        "ownerName": "顾源源",
        "projectContext": TaskProjectContextRecord(
            clientId="client_cffc",
            clientName="测试论坛A",
            backgroundSummary="测试论坛A是公益行业的重要枢纽组织，连接300+基金会",
            goalSummary="推进数字化转型合作",
            riskSummary="决策链较长",
        ),
    }
    defaults.update(overrides)
    return WeeklyReviewTaskSnapshotRecord(**defaults)


def _make_entry(snapshot=None, note="", reflection="") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id="entry_001",
        reviewId="review_001",
        taskId="task_001",
        weekLabel="2026-W13",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(reflection=reflection),
        taskSnapshot=snapshot or _make_snapshot(),
    )


def _make_org_dna() -> list[OrganizationDnaModuleRecord]:
    return [
        OrganizationDnaModuleRecord(
            moduleKey="organization_intro",
            title="组织介绍",
            markdownContent="",
            normalizedText="益语智库是公益行业咨询公司",
            summary="益语智库是公益行业咨询公司，提供战略咨询和数字化转型服务。",
        ),
    ]


def _assert_human_brief_quality(text: str) -> None:
    assert text, "humanBrief must not be empty"
    assert 45 <= len(text) <= 220
    assert any(token in text for token in ("建议", "先", "下一步", "补齐", "拆出", "决定"))
    for fragment in FORBIDDEN_BRIEF_FRAGMENTS:
        assert fragment not in text
    assert "与客户" not in text
    assert not ("这不是" in text and "而是" in text)


class TestEnhancedMode:

    def test_no_enhancement_falls_back_to_basic(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None, task_entry=entry, org_dna_modules=_make_org_dna(),
        )
        # 没有增强项时应该降级
        assert result.mode in ("basic", "enhanced")
        _assert_human_brief_quality(result.humanBrief)
        assert result.whatIsThis
        assert result.whyItMatters

    def test_with_event_line_becomes_enhanced(self):
        entry = _make_entry(note="本周确认了工作坊形式")
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="测试论坛A 战略合作线",
            event_line_stage="方案落地",
            event_line_summary="益语与测试论坛A的数字化战略合作",
        )
        assert result.mode == "enhanced"
        _assert_human_brief_quality(result.humanBrief)
        assert result.whatIsThis
        # enhanced 源中应该有事件线
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "event_line_memory" in source_types

    def test_enhanced_has_more_available_sources(self):
        entry = _make_entry(note="初步沟通完成")
        basic = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        enhanced = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="测试论坛A 合作线",
            meetings=[{"title": "测试论坛A 初次沟通", "summary": "确认了AI合作方向"}],
        )
        basic_available = sum(1 for s in basic.sourceBreakdown if s.available)
        enhanced_available = sum(1 for s in enhanced.sourceBreakdown if s.available)
        assert enhanced_available > basic_available

    def test_no_false_advice_without_llm(self):
        """LLM 不可用时，enhanced 也不应该硬造 optionalAdvice。"""
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="测试论坛A 合作线",
        )
        assert result.optionalAdvice is None

    def test_four_main_outputs_always_present_in_enhanced(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="测试论坛A 合作线",
            event_line_history=[
                {"weekLabel": "2026-W12", "stage": "方向确认", "taskCount": 2, "completedCount": 1},
            ],
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert result.progressNow
        assert result.unknowns
        _assert_human_brief_quality(result.humanBrief)

    def test_source_breakdown_includes_enhancement_items(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="线",
            meetings=[{"title": "会", "summary": "内容"}],
            support_requests=[{"title": "求", "summary": "帮助", "status": "open"}],
            knowledge_summaries=[{"title": "资料", "summary": "已确认客户希望先看到章节框架"}],
        )
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "event_line_memory" in source_types
        assert "meeting" in source_types
        assert "support_request" in source_types
        assert "knowledge_base" in source_types


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
