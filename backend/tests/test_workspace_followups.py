from __future__ import annotations

from app.services.workspace_followups import (
    build_workspace_followup_result_from_candidates,
    classify_workspace_followup_scenario,
)


def test_followup_scenario_strategy_judgment():
    scenario = classify_workspace_followup_scenario(
        prompt="日慈战略重点是什么",
        answer_content="日慈正在从项目交付转向关系生态建设。",
        workspace_workflow="synthesis",
    )
    assert scenario == "strategy_judgment"


def test_followup_scenario_organization_design():
    scenario = classify_workspace_followup_scenario(
        prompt="按现有业务架构，组织怎么调整",
        answer_content="需要重新梳理组织分工和协作机制。",
        workspace_workflow="synthesis",
    )
    assert scenario == "organization_design"


def test_followup_scenario_business_project_design():
    scenario = classify_workspace_followup_scenario(
        prompt="教师赋能项目包含哪些服务内容",
        answer_content="项目包括培训、陪伴和工具支持。",
        workspace_workflow="synthesis",
    )
    assert scenario == "business_project_design"


def test_followup_scenario_action_preparation():
    scenario = classify_workspace_followup_scenario(
        prompt="下周我要见一个资方，帮我准备项目介绍材料",
        answer_content="对外介绍需要突出项目成效和方法论资产。",
        workspace_workflow="synthesis",
    )
    assert scenario == "action_preparation"


def test_followup_scenario_research_upgrade():
    scenario = classify_workspace_followup_scenario(
        prompt="如果要研究这个项目的行业独特性，需要补什么资料",
        answer_content="需要更多同业参照和成效数据。",
        workspace_workflow="synthesis",
    )
    assert scenario == "research_upgrade"


def test_followup_scenario_file_search():
    scenario = classify_workspace_followup_scenario(
        prompt="帮我找战略方案原文",
        answer_content="我找到了这些可能相关的资料。",
        workspace_workflow="file_search",
    )
    assert scenario == "file_search"


def test_non_file_search_filters_overly_narrow_fact_questions_and_tops_up():
    result = build_workspace_followup_result_from_candidates(
        [
            "官方稿什么时候完成？",
            "这个判断出自哪份原文？",
            "这个战略落地时最可能卡在哪个组织能力上？",
        ],
        scenario="strategy_judgment",
        generation_mode="consulting",
        client_name="日慈基金会",
        workspace_workflow="synthesis",
    )

    assert result.rejected_count == 2
    assert "这个战略落地时最可能卡在哪个组织能力上？" in result.questions
    assert all("官方稿" not in item and "哪份原文" not in item for item in result.questions)
    assert len(result.questions) == 3


def test_action_preparation_fallback_focuses_on_meeting_conversion():
    result = build_workspace_followup_result_from_candidates(
        ["下一步应该做什么？"],
        scenario="action_preparation",
        generation_mode="consulting",
        workspace_workflow="synthesis",
    )

    joined = "\n".join(result.questions)
    assert "对方真正关心" in joined
    assert "会后" in joined
    assert len(result.questions) == 3


def test_research_upgrade_fallback_asks_for_material_types():
    result = build_workspace_followup_result_from_candidates(
        [],
        scenario="research_upgrade",
        generation_mode="fallback",
        workspace_workflow="synthesis",
    )

    joined = "\n".join(result.questions)
    assert "哪类同业参照" in joined
    assert "成效数据" in joined
    assert len(result.questions) == 3


def test_file_search_allows_source_and_original_followups():
    result = build_workspace_followup_result_from_candidates(
        [
            "还要继续找哪份原文？",
            "这个结论的出处在哪？",
            "是否要基于这几份原文生成一版综合回答？",
        ],
        scenario="file_search",
        generation_mode="file_search",
        workspace_workflow="file_search",
    )

    joined = "\n".join(result.questions)
    assert "哪份原文" in joined
    assert "出处在哪" in joined
    assert len(result.questions) == 3
