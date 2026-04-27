from __future__ import annotations

from app.services.workspace_query_router import route_workspace_query


def test_route_workspace_query_file_search():
    route = route_workspace_query(
        prompt="帮我找一下日慈战略方案原文",
        client_id="c1",
    )
    assert route.workflow == "file_search"
    assert route.generationMode == "no_generation"
    assert route.shouldGenerateAnswer is False
    assert route.shouldReturnSearchResults is True
    assert route.includeRawEvidence is True
    assert route.routeReason == "workspace_rule_file_search_explicit"


def test_route_workspace_query_file_search_for_origin_document_question():
    route = route_workspace_query(
        prompt="这个结论出自哪份原文",
        client_id="c1",
    )
    assert route.workflow == "file_search"
    assert route.generationMode == "no_generation"


def test_route_workspace_query_file_search_for_open_meeting_minutes():
    route = route_workspace_query(
        prompt="打开上次会议纪要",
        client_id="c1",
    )
    assert route.workflow == "file_search"
    assert route.generationMode == "no_generation"


def test_route_workspace_query_synthesis():
    route = route_workspace_query(
        prompt="介绍一下日慈基金会的核心项目和战略",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "consultant_synthesis"
    assert route.shouldGenerateAnswer is True
    assert route.includeRawEvidence is True
    assert route.intent == "consultant_synthesis"
    assert "raw_docs" in route.dataSources
    assert route.routeReason == "workspace_rule_consultant_synthesis"


def test_route_workspace_query_consultant_synthesis_for_current_change():
    route = route_workspace_query(
        prompt="日慈当前最值得关注的变化是什么",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "consultant_synthesis"
    assert route.routeReason == "workspace_rule_consultant_synthesis"


def test_route_workspace_query_consultant_synthesis_for_core_assets():
    route = route_workspace_query(
        prompt="日慈的核心资产是什么",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "consultant_synthesis"


def test_route_workspace_query_business_question_with_baohanstays_synthesis():
    route = route_workspace_query(
        prompt="教师赋能项目要试点的预防加干预综合服务模式，具体包含哪些面向教师和学生的落地服务内容？",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "long_synthesis"
    assert route.routeReason == "workspace_rule_open_synthesis"


def test_route_workspace_query_module_question_with_baohanstays_synthesis():
    route = route_workspace_query(
        prompt="这个项目包含哪些核心模块",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "long_synthesis"


def test_route_workspace_query_source_question_without_explicit_doc_request_stays_synthesis():
    route = route_workspace_query(
        prompt="这个判断的来源是什么",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "long_synthesis"


def test_route_workspace_query_status_like_prompt_stays_open_synthesis():
    route = route_workspace_query(
        prompt="上次会议达成了什么共识，下一步做什么",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.generationMode == "long_synthesis"
    assert route.shouldGenerateAnswer is True
    assert route.intent == "general"
    assert route.dataSources == ["raw_docs", "document_cards"]


def test_route_workspace_query_open_synthesis_keeps_raw_evidence_enabled_even_when_meeting_like():
    route = route_workspace_query(
        prompt="上次会议达成了什么共识，下一步做什么",
        client_id="c1",
    )
    assert route.workflow == "synthesis"
    assert route.includeRawEvidence is True

    raw_route = route_workspace_query(
        prompt="请根据资料说明上次会议达成了什么共识，下一步做什么",
        client_id="c1",
    )
    assert raw_route.workflow == "synthesis"
    assert raw_route.includeRawEvidence is True
