from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (  # noqa: E402
    ActionSuggestionRecord,
    AnswerPolicyRecord,
    AnswerMaterialRecord,
    AnswerPlanRecord,
    ContextQualityRecord,
    DataCenterKernelResultRecord,
    DataCenterProposalDraftRecord,
    DataCenterScopeRecord,
    EvidenceItem,
    PageContextPackRecord,
    RouteDecisionRecord,
)
from app.services.workspace_data_center_adapter import build_open_workspace_answer_context  # noqa: E402
from app.services.workspace_data_center_adapter import (  # noqa: E402
    WORKSPACE_SCOPE_MAPPING,
    build_consultant_synthesis_material_pack,
    build_workspace_data_center_request_from_route,
    build_workspace_dc_response_meta,
    build_workspace_scope,
    build_workspace_event_line_data_center_request,
    build_workspace_meeting_data_center_request,
    build_workspace_project_flow_data_center_request,
    build_workspace_project_module_data_center_request,
    build_workspace_task_data_center_request,
)
from app.services.workspace_query_router import route_workspace_query  # noqa: E402


def _build_kernel_result_with_official_items(
    official_items: list[object],
    *,
    route_intent: str = "general",
    page_intent: str = "general",
    answer_intent: str = "general",
) -> DataCenterKernelResultRecord:
    page_context = PageContextPackRecord.model_construct(
        page="workspace_chat",
        scopeType="client",
        scopeId="client-1",
        clientId="client-1",
        intent=page_intent,
        officialJudgments=official_items,
        candidateJudgments=[],
        overlayJudgments=[],
        evidenceCards=[],
        rawEvidence=[],
        openQuestions=[{"question": "还有哪些资料缺口"}],
        conflicts=[{"summary": "当前推进有品牌侧阻塞"}],
        themeClusters=[],
        relatedTasks=[{"title": "补充项目手册"}],
        relatedMeetings=[{"title": "四月客户会议"}],
        relatedDocuments=[],
        notebookSummary=None,
        memoryFacts=["该机构聚焦儿童青少年心理健康与心理教育。"],
        contextPack=None,
        judgmentBundle=None,
        resolutionTrace=None,
        stateProjection=None,
        missingContext=["仍缺少正式项目手册。"],
        boundaryNotes=["当前部分信息仍来自候选材料。"],
        sourceSummary={},
        answerPolicy=AnswerPolicyRecord(),
        retrievalPlan={},
        quality=ContextQualityRecord(),
        routeDecision=None,
        retrievalTrace=None,
    )
    scope = DataCenterScopeRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client-1",
        clientId="client-1",
    )
    return DataCenterKernelResultRecord.model_construct(
        scope=scope,
        pageContext=page_context,
        routeDecision=RouteDecisionRecord(intent=route_intent),
        retrievalTrace=None,
        answerPlan=AnswerPlanRecord(intent=answer_intent),
        answerMaterial=AnswerMaterialRecord(
            keyFacts=["核心议题是儿童青少年心理健康。"],
            structuredPoints=["近期工作重点是海外资助谈判。"],
            nextActions=["建议先补证据再推进。"],
            sourceLabels=["日慈战略核心思想", "日慈战略结构", "心灵魔法学院项目"],
            evidenceHighlights=[
                EvidenceItem(
                    id="e1",
                    title="客户介绍材料",
                    excerpt="聚焦儿童青少年心理健康与心理教育。",
                    sourceType="document",
                )
            ],
        ),
        searchResult=None,
        prepResult=None,
        proposalDrafts=[
            DataCenterProposalDraftRecord(
                kind="context_refresh",
                title="刷新上下文",
                summary="补充资料后刷新",
                rationale="资料仍不完整",
            )
        ],
        persistedProposalDraftIds=[],
        dedupedDraftIds=[],
        actionSuggestions=[
            ActionSuggestionRecord(
                id="a1",
                actionType="request_evidence",
                title="补资料",
                summary="补项目手册",
                rationale="当前证据不完整",
            )
        ],
        quality=None,
        debug={},
    )


class _JudgmentModel(BaseModel):
    summary: str


def test_open_workspace_answer_context_accepts_pydantic_items():
    kernel_result = _build_kernel_result_with_official_items([_JudgmentModel(summary="正式判断-模型对象")])
    context = build_open_workspace_answer_context(
        prompt="测试问题",
        kernel_result=kernel_result,
        workspace_snapshot=None,
    )
    assert "【原始阅读资料包 v2】" in context
    assert "正式判断：1 条" not in context


def test_open_workspace_answer_context_accepts_dict_items():
    kernel_result = _build_kernel_result_with_official_items([{"summary": "正式判断-dict"}])
    context = build_open_workspace_answer_context(
        prompt="测试问题",
        kernel_result=kernel_result,
        workspace_snapshot=None,
    )
    assert "【原始阅读资料包 v2】" in context
    assert "正式判断：1 条" not in context


def test_open_workspace_answer_context_accepts_string_items():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-string"])
    context = build_open_workspace_answer_context(
        prompt="测试问题",
        kernel_result=kernel_result,
        workspace_snapshot=None,
    )
    assert "【原始阅读资料包 v2】" in context
    assert "正式判断：1 条" not in context


def test_open_workspace_answer_context_intro_profile_hides_operational_sections():
    kernel_result = _build_kernel_result_with_official_items(
        ["正式判断-机构定位"],
        route_intent="intro_profile",
        answer_intent="intro_profile",
    )
    context = build_open_workspace_answer_context(
        prompt="介绍日慈基金会",
        kernel_result=kernel_result,
        workspace_snapshot=None,
    )
    assert "【组织画像目标】" not in context
    assert "【组织画像参考草稿】" not in context
    assert "【相关任务】" not in context
    assert "【相关会议】" not in context
    assert "【风险/冲突】" not in context
    assert "【开放问题】" not in context
    assert "【边界说明】" not in context
    assert "【关键事实】" not in context
    assert "【补充事实】" not in context
    assert "【原始阅读资料包 v2】" in context
    assert "自由组织结构和长度" in context


def test_open_workspace_answer_context_intro_profile_includes_profile_goal_and_draft():
    kernel_result = _build_kernel_result_with_official_items(
        ["正式判断-机构定位"],
        route_intent="intro_profile",
        answer_intent="intro_profile",
    )
    context = build_open_workspace_answer_context(
        prompt="介绍日慈基金会",
        kernel_result=kernel_result,
        workspace_snapshot=None,
        question_focus_frame={
            "goal": "define",
            "subjectFacet": "identity",
        },
        profile_draft="日慈基金会是一家以儿童青少年心理健康与心理教育为核心议题的公益基金会。\n\n1）它主要在解决什么问题\n- 它关注的是结构性心理支持缺口。",
    )
    assert "【组织画像目标】" not in context
    assert "【组织画像参考草稿】" not in context
    assert "1）它主要在解决什么问题" not in context


def test_open_workspace_answer_context_general_keeps_operational_sections():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-常规"])
    context = build_open_workspace_answer_context(
        prompt="当前推进情况如何",
        kernel_result=kernel_result,
        workspace_snapshot=None,
    )
    assert "【相关任务】" not in context
    assert "【相关会议】" not in context
    assert "【风险/冲突】" not in context
    assert "【开放问题】" not in context
    assert "【边界说明】" not in context
    assert "【结构化线索】" not in context
    assert "【建议动作线索】" not in context
    assert "【候选动作】" not in context
    assert "【候选提案草稿】" not in context
    assert "【原始阅读资料包 v2】" in context


def test_consultant_synthesis_material_pack_collects_high_signal_sources_and_filters_noise():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-常规"])
    assert kernel_result.pageContext is not None
    assert kernel_result.answerMaterial is not None
    kernel_result.pageContext.candidateJudgments = [
        {"summary": "日慈正在从课程服务交付转向关系生态建设。"}
    ]
    kernel_result.pageContext.evidenceCards = [
        {"title": "日慈战略升级", "summary": "重点是数字化工具、教师赋能和关系支持网络。"}
    ]
    kernel_result.pageContext.rawEvidence = [
        {"title": "日慈战略资料", "excerpt": "组织希望把心灵魔法学院、心盛计划和教师赋能形成协同。"}
    ]
    kernel_result.answerMaterial.evidenceHighlights.append(
        EvidenceItem(
            id="noise-1",
            title="prog_test_upload.jpeg",
            excerpt="jpeg 已作为任务附件进入项目资料库。",
            sourceType="document",
            retrievalStage="raw_chunk",
        )
    )
    workspace_snapshot = SimpleNamespace(
        client=SimpleNamespace(name="日慈基金会", stage="战略升级期", summary="聚焦儿童青少年心理健康服务。"),
        documents=[
            SimpleNamespace(title="日慈战略规划", excerpt="围绕儿童青少年心理健康、教师赋能和数字化工具推进。", tags=["战略"]),
            SimpleNamespace(title="报销说明", excerpt="报销流程和附件占位说明。", tags=[]),
        ],
        dnaModules=[
            SimpleNamespace(title="客户 DNA", summary="组织强调关系支持、教育合作和场域化服务。")
        ],
        projectModules=[],
        projectFlows=[],
        relatedTasks=[],
    )

    pack = build_consultant_synthesis_material_pack(
        prompt="介绍一下日慈基金会",
        kernel_result=kernel_result,
        workspace_snapshot=workspace_snapshot,  # type: ignore[arg-type]
        max_chars=36000,
    )

    assert pack.profile == "consultant_synthesis_v1"
    assert "日慈基金会" in pack.content
    assert "关系生态建设" in pack.content
    assert "心灵魔法学院" in pack.content
    assert "战略规划" in pack.content
    assert "prog_test_upload" not in pack.content
    assert "报销流程" not in pack.content
    assert pack.excluded_noise_count >= 1
    assert pack.source_counts.get("candidateJudgments", 0) >= 1
    assert pack.context_chars == len(pack.content)


def test_consultant_synthesis_request_uses_candidate_kernel_results():
    route = route_workspace_query(prompt="介绍一下日慈基金会", client_id="client-1")
    request = build_workspace_data_center_request_from_route(
        route=route,
        prompt="介绍一下日慈基金会",
        shadow=True,
    )
    assert route.generationMode == "consultant_synthesis"
    assert request.mode == "answer"
    assert request.includeRawEvidence is True
    assert request.shadow is False


def test_workspace_dc_response_meta_includes_consultant_material_pack_diagnostics():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-常规"])
    response_meta = build_workspace_dc_response_meta(
        kernel_result=kernel_result,
        answer_intent="general",
        retrieval_decision_reason="default_hybrid_evidence",
        data_center_primary_enabled=True,
        legacy_intent="general",
        legacy_retrieval_reason="default_hybrid_evidence",
        llm_attempt_count=1,
        compact_retry_attempted=False,
        fallback_template_used=False,
        final_failure_stage=None,
        route_decision_source="data_center",
        answer_mode="grounded_answer",
        evidence_status="sufficient",
        failure_reason=None,
        fallback_presentation_mode="full_answer",
        should_run_retrieval=True,
        state_confidence="medium",
        state_sources=[],
        state_answer_sections={},
        state_source_summary={},
        total_elapsed_ms=1200.0,
        retrieval_elapsed_ms=140.0,
        llm_elapsed_ms=900.0,
        answer_quality={"grade": "pass"},
        quality_gate_warned=False,
        generation_policy={},
        workspace_workflow="synthesis",
        workspace_generation_mode="consultant_synthesis",
        workspace_route={"generationMode": "consultant_synthesis"},
        primary_sources=["raw_docs", "client_dna"],
        material_access_mode="consultant_synthesis_v1",
        material_pack_profile="consultant_synthesis_v1",
        material_pack_source_counts={"candidateJudgments": 2},
        excluded_noise_count=3,
        consultant_context_chars=32000,
        consultant_boundary_notes=["部分信息仍待确认。"],
    )

    assert response_meta["materialPackProfile"] == "consultant_synthesis_v1"
    assert response_meta["materialPackSourceCounts"] == {"candidateJudgments": 2}
    assert response_meta["excludedNoiseCount"] == 3
    assert response_meta["consultantContextChars"] == 32000
    assert response_meta["consultantBoundaryNotes"] == ["部分信息仍待确认。"]


def test_workspace_dc_response_meta_rejects_removed_raw_document_pack():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-常规"])
    with pytest.raises(ValueError, match="raw_document_pack has been removed"):
        build_workspace_dc_response_meta(
            kernel_result=kernel_result,
            answer_intent="intro_profile",
            retrieval_decision_reason="intro_query_needs_evidence",
            data_center_primary_enabled=True,
            legacy_intent="intro_profile",
            legacy_retrieval_reason="intro_query_needs_evidence",
            llm_attempt_count=1,
            compact_retry_attempted=False,
            fallback_template_used=False,
            final_failure_stage=None,
            route_decision_source="data_center",
            answer_mode="grounded_answer",
            evidence_status="sufficient",
            failure_reason=None,
            fallback_presentation_mode="full_answer",
            should_run_retrieval=True,
            state_confidence="medium",
            state_sources=["document"],
            state_answer_sections={
                "official": [],
                "candidate": [],
                "draftFindings": [],
                "evidenceSupport": [],
                "actions": [],
                "risks": [],
                "unknowns": [],
            },
            state_source_summary={
                "judgments": 0,
                "tasks": 0,
                "meetings": 0,
                "documents": 2,
                "memoryFacts": 1,
                "openQuestions": 0,
                "conflicts": 0,
            },
            total_elapsed_ms=1200.0,
            retrieval_elapsed_ms=140.0,
            llm_elapsed_ms=900.0,
            answer_quality={"grade": "pass"},
            quality_gate_warned=False,
            generation_policy={},
            workspace_workflow="synthesis",
            workspace_generation_mode="focused_profile",
            workspace_route={"intent": "intro_profile"},
            primary_sources=["客户介绍材料"],
            preview_summary="围绕“介绍日慈”，本轮已命中这些高相关资料。",
            work_trace={"rawEvidenceCount": 6},
            master_hit_count=72,
            surrogate_hit_count=4,
            raw_chunk_hit_count=20,
            material_access_mode="raw_document_pack",
        )


def test_workspace_dc_response_meta_sanitizes_state_metadata_for_reading_pack_v2():
    kernel_result = _build_kernel_result_with_official_items(["正式判断-常规"])
    kernel_result.retrievalTrace = {
        "readingPassCount": 2,
        "selectedDocumentFamilyCount": 12,
        "selectedCanonicalKinds": ["raw_file", "meeting_doc"],
        "softwareMaterialIncluded": True,
    }
    response_meta = build_workspace_dc_response_meta(
        kernel_result=kernel_result,
        answer_intent="general",
        retrieval_decision_reason="default_hybrid_evidence",
        data_center_primary_enabled=True,
        legacy_intent="general",
        legacy_retrieval_reason="default_hybrid_evidence",
        llm_attempt_count=1,
        compact_retry_attempted=False,
        fallback_template_used=False,
        final_failure_stage=None,
        route_decision_source="data_center",
        answer_mode="grounded_answer",
        evidence_status="sufficient",
        failure_reason=None,
        fallback_presentation_mode="full_answer",
        should_run_retrieval=True,
        state_confidence="medium",
        state_sources=["meeting", "task"],
        state_answer_sections={"official": [{"text": "旧状态块"}]},
        state_source_summary={"meetings": 2, "tasks": 1},
        total_elapsed_ms=1200.0,
        retrieval_elapsed_ms=140.0,
        llm_elapsed_ms=900.0,
        answer_quality={"grade": "pass"},
        quality_gate_warned=False,
        generation_policy={},
        workspace_workflow="synthesis",
        workspace_generation_mode="reading_pack_v2",
        workspace_route={"intent": "general"},
        primary_sources=["raw_docs", "document_cards"],
        preview_summary="旧主链摘要说明",
        work_trace={"rawEvidenceCount": 8},
        master_hit_count=60,
        surrogate_hit_count=0,
        raw_chunk_hit_count=18,
        material_access_mode="raw_reading_pack_v2",
    )
    assert response_meta["materialAccessMode"] == "raw_reading_pack_v2"
    assert response_meta["stateSources"] == []
    assert response_meta["stateAnswerSections"] == {}
    assert response_meta["stateSourceSummary"] == {}
    assert response_meta["previewSummary"] == ""
    assert response_meta["workTrace"] == {}
    assert response_meta["readingPassCount"] == 2
    assert response_meta["selectedDocumentFamilyCount"] == 12
    assert response_meta["selectedCanonicalKinds"] == ["raw_file", "meeting_doc"]
    assert response_meta["softwareMaterialIncluded"] is True
    assert response_meta["sourceLabels"] == ["日慈战略核心思想", "日慈战略结构", "心灵魔法学院项目"]


def test_workspace_scope_mapping_contains_expected_keys():
    assert "workspace_chat" in WORKSPACE_SCOPE_MAPPING
    assert "task_detail" in WORKSPACE_SCOPE_MAPPING
    assert "meeting_detail" in WORKSPACE_SCOPE_MAPPING
    assert "event_line_detail" in WORKSPACE_SCOPE_MAPPING
    assert "project_module_detail" in WORKSPACE_SCOPE_MAPPING
    assert "project_flow_detail" in WORKSPACE_SCOPE_MAPPING


def test_workspace_scope_request_builders_generate_stable_scope():
    task_request = build_workspace_task_data_center_request(client_id="client-1", task_id="task-1", prompt="任务详情")
    assert task_request.scope.scopeType == "task"
    assert task_request.scope.scopeId == "task-1"
    assert task_request.scope.taskId == "task-1"

    meeting_request = build_workspace_meeting_data_center_request(client_id="client-1", meeting_id="meeting-1")
    assert meeting_request.scope.scopeType == "meeting"
    assert meeting_request.scope.scopeId == "meeting-1"
    assert meeting_request.scope.meetingId == "meeting-1"

    event_line_request = build_workspace_event_line_data_center_request(client_id="client-1", event_line_id="eline-1")
    assert event_line_request.scope.scopeType == "event_line"
    assert event_line_request.scope.scopeId == "eline-1"
    assert event_line_request.scope.eventLineId == "eline-1"

    module_request = build_workspace_project_module_data_center_request(client_id="client-1", module_id="module-1", prompt="模块")
    assert module_request.scope.scopeType == "project_module"
    assert module_request.scope.scopeId == "module-1"
    assert module_request.scope.projectModuleId == "module-1"

    flow_request = build_workspace_project_flow_data_center_request(client_id="client-1", flow_id="flow-1", prompt="流程")
    assert flow_request.scope.scopeType == "project_flow"
    assert flow_request.scope.scopeId == "flow-1"
    assert flow_request.scope.projectFlowId == "flow-1"


def test_build_workspace_scope_raises_on_missing_scope_id():
    try:
        build_workspace_scope(page="task_detail", client_id="client-1")
    except ValueError as error:
        assert "missing scope id" in str(error)
    else:
        raise AssertionError("expected ValueError for missing task scope id")
