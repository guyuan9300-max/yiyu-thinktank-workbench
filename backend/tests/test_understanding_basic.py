"""
测试 basic 模式构建器：
- 只有最小输入时也能得到 basic 结果
- 结果中必须包含 humanBrief 和 4 个兼容主输出
- 不会生成假精细的建议字段
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    TaskProjectContextRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.understanding_builder import build_understanding_basic, build_understanding_content_hash


FORBIDDEN_BRIEF_FRAGMENTS = ["这是一条", "状态的工作任务", "系统尚未看到"]


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "和冯梅老师沟通测试论坛A的战略说明迭代",
        "status": "doing",
        "createdAt": "2026-03-20T10:00:00Z",
        "listName": "战略合作",
        "listColor": "#5B7BFE",
        "ownerName": "顾源源",
        "eventLineId": "",
        "eventLineName": "",
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
            markdownContent="益语智库是一家专注于公益行业的咨询公司",
            normalizedText="益语智库是一家专注于公益行业的咨询公司，为基金会和公益组织提供战略咨询、数字化转型和研究服务。",
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


class _FakeBadBriefAi:
    def _qwen_generate(self, **kwargs):
        return {
            "humanBrief": "这是一条 todo 状态任务，与客户 测试论坛A 相关。",
            "whatIsThis": "旧模板",
            "whyItMatters": "旧模板",
            "progressNow": "旧模板",
            "unknowns": "旧模板",
            "knownFacts": ["事实"],
            "confidence": 80,
        }


class TestBasicModeMinimalInput:
    """只有最小输入时也能得到 basic 结果。"""

    def test_minimal_input_produces_result(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result is not None
        assert result.mode == "basic"
        _assert_human_brief_quality(result.humanBrief)

    def test_four_main_outputs_always_present(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result.humanBrief, "humanBrief must not be empty"
        assert result.whatIsThis, "whatIsThis must not be empty"
        assert result.whyItMatters, "whyItMatters must not be empty"
        assert result.progressNow, "progressNow must not be empty"
        assert result.unknowns, "unknowns must not be empty"

    def test_no_false_advice_in_basic(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result.optionalAdvice is None, "basic mode should not produce optional advice"

    def test_with_org_dna_improves_coverage(self):
        entry = _make_entry()
        result_no_dna = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        result_with_dna = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert result_with_dna.coverage > result_no_dna.coverage

    def test_with_client_background(self):
        pc = TaskProjectContextRecord(
            clientId="client_cffc",
            clientName="测试论坛A",
            backgroundSummary="测试论坛A是公益行业的重要枢纽组织",
            goalSummary="推进数字化转型合作",
            riskSummary="决策链较长",
        )
        snapshot = _make_snapshot(projectContext=pc)
        entry = _make_entry(snapshot=snapshot)
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert "测试论坛A" in result.whatIsThis or "测试论坛A" in result.whyItMatters
        assert result.coverage >= 50

    def test_with_review_note(self):
        entry = _make_entry(note="本周和冯梅老师确认了工作坊方向，下周准备正式提案。")
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert "复盘" in result.progressNow or "冯梅" in result.progressNow or "说明" in result.progressNow

    def test_human_brief_for_ppt_matches_user_value_shape(self):
        pc = TaskProjectContextRecord(
            clientId="client_yiyu",
            clientName="益语智库",
            backgroundSummary="内部报告生成能力优化",
            goalSummary="让任务理解能指导下一步工作",
            riskSummary="只给诊断标签会降低人类可用价值",
        )
        snapshot = _make_snapshot(
            title="完成研究报告的新报告的PPT",
            status="todo",
            desc="一线复盘说明：我来生成PPT的架构说明，你来用GPT来生成高精度的PPT，整个PPT控制在35页以内",
            projectContext=pc,
        )
        entry = _make_entry(snapshot=snapshot)
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        _assert_human_brief_quality(result.humanBrief)
        assert "给谁看" in result.humanBrief or "目标受众" in result.humanBrief
        assert "35" in result.humanBrief or "页数上限" in result.humanBrief
        assert "章节框架" in result.humanBrief

    def test_content_hash_changes_with_prompt_version(self):
        args = {
            "title": "完成研究报告的新报告的PPT",
            "desc": "控制在35页以内",
            "status": "todo",
            "client_id": "client_yiyu",
            "event_line_id": "line_yiyu",
        }
        legacy = build_understanding_content_hash(**args, prompt_version="v1")
        current = build_understanding_content_hash(**args)
        explicit = build_understanding_content_hash(**args, prompt_version="v2-human-brief")
        assert current == explicit
        assert legacy != current

    def test_ai_forbidden_human_brief_falls_back(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=_FakeBadBriefAi(), task_entry=entry, org_dna_modules=[])
        _assert_human_brief_quality(result.humanBrief)
        assert "这是一条" not in result.humanBrief
        assert "与客户" not in result.humanBrief

    def test_never_returns_cannot_judge(self):
        """即使输入几乎为空，也不能返回"无法判断"。"""
        snapshot = _make_snapshot(title="测试任务", desc="")
        entry = _make_entry(snapshot=snapshot)
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert "无法判断" not in result.whatIsThis
        assert "无法判断" not in result.whyItMatters
        assert result.whatIsThis  # 不为空

    def test_known_facts_populated(self):
        entry = _make_entry(note="已完成初步沟通")
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert len(result.knownFacts) >= 2

    def test_source_breakdown_complete(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "org_dna" in source_types
        assert "client_background" in source_types
        assert "task_title" in source_types
        assert "review_note" in source_types


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
