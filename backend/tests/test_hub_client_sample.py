"""
第 6 段：B客户 联合样本验证 — 验证"理解优先"

用 B客户 样本验证系统已经从"单任务浅分析"进入"长时间线理解"。

输入：
- 示例团队背景卡（组织介绍）
- B客户 客户背景卡
- 季度主线（推进战略陪伴客户合作）
- 同一事件线下 3 条任务
- 1 条任务复盘
- 1 次会议结构结果
- 事件线历史 2 周

验证要求：
1. 输出不能先写风险或动作
2. 必须先稳定输出 4 个主问题
3. whyItMatters 必须体现高杠杆合作判断，不只是普通任务
4. optionalAdvice 只在证据足够时出现
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
    TaskOrgContextRecord,
)
from app.services.understanding_builder import build_understanding_basic, build_understanding_enhanced


# ── 构造 B客户 样本 ──

YIYU_ORG_DNA = [
    OrganizationDnaModuleRecord(
        moduleKey="organization_intro",
        title="组织介绍",
        markdownContent="",
        normalizedText=(
            "示例工作台是一家专注于公益行业的咨询公司，为基金会和公益组织提供战略咨询、"
            "数字化转型和研究服务。当前重点方向是通过战略陪伴模式，帮助公益组织建立"
            "长期能力，同时通过行业枢纽型客户扩大市场覆盖。"
        ),
        summary="示例工作台是公益行业咨询公司，通过战略陪伴帮助公益组织建立长期能力。",
    ),
    OrganizationDnaModuleRecord(
        moduleKey="business_intro",
        title="业务介绍",
        markdownContent="",
        normalizedText="示例团队的核心业务包括：战略咨询、数字化转型咨询、行业研究报告、AI赋能方案。收入主要来自长期战略陪伴合同。",
        summary="核心业务：战略咨询、数字化转型、行业研究、AI赋能。",
    ),
]

B客户_PROJECT_CONTEXT = TaskProjectContextRecord(
    clientId="client_demo_hub",
    clientName="B客户（行业协作平台）",
    backgroundSummary="B客户是公益行业的重要枢纽组织，连接300+基金会，在行业内有广泛影响力和号召力。",
    goalSummary="推进AI技术合作工作坊，探索数字化战略陪伴合作模式。",
    riskSummary="B客户内部决策链较长，需要多层审批；双方在具体合作形式上还未完全对齐。",
    infoCompleteness="medium",
)

B客户_ORG_CONTEXT = TaskOrgContextRecord(
    departmentId="dept_strategy",
    departmentName="战略合作部",
)

# 3 条任务
TASK_1_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="和联系人甲老师沟通B客户的战略说明迭代",
    status="done",
    createdAt="2026-03-18T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="管理员甲",
    eventLineId="el_demo_hub_001",
    eventLineName="联系人乙讨论赋能合作",
    projectContext=B客户_PROJECT_CONTEXT,
    orgContext=B客户_ORG_CONTEXT,
)

TASK_2_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="准备B客户 AI赋能工作坊方案",
    status="doing",
    createdAt="2026-03-20T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="管理员甲",
    eventLineId="el_demo_hub_001",
    eventLineName="联系人乙讨论赋能合作",
    projectContext=B客户_PROJECT_CONTEXT,
    orgContext=B客户_ORG_CONTEXT,
)

TASK_3_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="向光奖联系人丙老师（数字化战略协作）",
    status="done",
    createdAt="2026-03-15T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="管理员甲",
    eventLineId="el_demo_hub_001",
    eventLineName="联系人乙讨论赋能合作",
    projectContext=B客户_PROJECT_CONTEXT,
    orgContext=B客户_ORG_CONTEXT,
)

TASK_1_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_demo_hub_1",
    reviewId="review_w13",
    taskId="task_demo_hub_1",
    weekLabel="2026-W13",
    contentDomain="work",
    note="本周和联系人甲老师确认了工作坊的形式和方向，她很认可AI+公益的切入点，下周准备正式提案。",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
        reflection="联系人甲老师的反馈比预期积极，B客户内部对AI话题很感兴趣",
        completionStatus="done_on_time",
        successExperience="通过具体案例展示打动了对方",
        nextAction="下周发送正式提案",
    ),
    taskSnapshot=TASK_1_SNAPSHOT,
)

TASK_2_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_demo_hub_2",
    reviewId="review_w13",
    taskId="task_demo_hub_2",
    weekLabel="2026-W13",
    contentDomain="work",
    note="",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(),
    taskSnapshot=TASK_2_SNAPSHOT,
)

TASK_3_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_demo_hub_3",
    reviewId="review_w13",
    taskId="task_demo_hub_3",
    weekLabel="2026-W13",
    contentDomain="work",
    note="",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
        completionStatus="done_on_time",
    ),
    taskSnapshot=TASK_3_SNAPSHOT,
)

# 会议
B客户_MEETING = {
    "title": "B客户初次战略沟通会",
    "summary": "与联系人甲老师和联系人乙讨论了AI技术在公益行业的应用场景，确认了工作坊形式的合作切入点，双方同意先做一次小范围试点。",
}

# 事件线历史
B客户_EVENT_LINE_HISTORY = [
    {"weekLabel": "2026-W12", "stage": "方向确认", "taskCount": 2, "completedCount": 1, "keyDecisions": ["确认AI工作坊作为切入形式"]},
    {"weekLabel": "2026-W11", "stage": "初步接触", "taskCount": 1, "completedCount": 1, "keyDecisions": ["联系人甲老师引荐，建立联系"]},
]


class TestB客户Sample:

    def test_basic_mode_four_outputs_present(self):
        """basic 模式下 4 个主输出必须存在。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert result.progressNow
        assert result.unknowns

    def test_basic_mode_mentions_hub(self):
        """basic 模式就应该识别出 B客户 客户。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert "B客户" in result.whatIsThis or "B客户" in result.whyItMatters

    def test_enhanced_mode_deeper_understanding(self):
        """enhanced 模式应该比 basic 有更深的理解。"""
        basic = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        enhanced = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="联系人乙讨论赋能合作",
            event_line_stage="方案落地",
            event_line_summary="示例团队与B客户探索AI赋能合作，从工作坊切入",
            event_line_history=B客户_EVENT_LINE_HISTORY,
            meetings=[B客户_MEETING],
        )
        assert enhanced.mode == "enhanced"
        # enhanced 应该有更多可用源（coverage 可能因分母变大而不严格更高）
        enhanced_available = sum(1 for s in enhanced.sourceBreakdown if s.available)
        basic_available = sum(1 for s in basic.sourceBreakdown if s.available)
        assert enhanced_available > basic_available

    def test_enhanced_no_premature_advice(self):
        """LLM 不可用时，enhanced 也不硬写 optionalAdvice。"""
        result = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="联系人乙讨论赋能合作",
            event_line_history=B客户_EVENT_LINE_HISTORY,
        )
        assert result.optionalAdvice is None

    def test_basic_never_starts_with_risk(self):
        """输出不能先写风险或动作 — whatIsThis 不应该包含'风险'或'阻碍'。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        first_output = result.whatIsThis
        assert "风险" not in first_output
        assert "阻碍" not in first_output
        assert "建议" not in first_output

    def test_task_without_review_still_produces_result(self):
        """没有复盘资料的任务也必须产出结果。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_2_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert "B客户" in result.whatIsThis or "B客户" in result.whyItMatters

    def test_source_breakdown_reflects_actual_inputs(self):
        """sourceBreakdown 应该准确反映哪些输入可用。"""
        result = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="联系人乙讨论赋能合作",
            meetings=[B客户_MEETING],
        )
        source_map = {s.sourceType: s.available for s in result.sourceBreakdown}
        assert source_map["org_dna"] is True
        assert source_map["client_background"] is True
        assert source_map["task_title"] is True
        assert source_map["review_note"] is True
        assert source_map["event_line_memory"] is True
        assert source_map["meeting"] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
