from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (  # noqa: E402
    ActionSuggestionRecord,
    AnswerMaterialRecord,
    DataCenterProposalDraftRecord,
    EvidenceItem,
    WorkspaceAnswerFinalizationRecord,
)
from app.services.workspace_answer_experience import build_workspace_answer_experience  # noqa: E402


def test_workspace_answer_experience_p29_builds_ready_answer_card():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='客户当前核心业务聚焦资源支持与项目服务。',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='quality_passed',
    )
    material = AnswerMaterialRecord(
        directAnswerSeed='客户当前核心业务聚焦资源支持与项目服务。',
        keyFacts=['业务模块包括资源支持', '业务模块包括项目服务'],
        boundaryNotes=['当前结论仅覆盖已入库资料'],
        nextActions=['确认下一步责任人'],
        evidenceHighlights=[
            EvidenceItem(
                id='ev_1',
                title='战略纪要',
                excerpt='明确近期聚焦资源支持与项目服务。',
                sourceType='document',
                documentId='doc_1',
                path='/tmp/doc_1.md',
                sectionLabel='关键依据',
            )
        ],
    )
    draft = DataCenterProposalDraftRecord(
        id='draft_1',
        kind='evidence_request',
        title='补证据提案',
        summary='补齐关键证据',
        rationale='当前需要更多支持材料',
        riskLevel='low',
    )
    suggestion = ActionSuggestionRecord(
        id='suggest_1',
        actionType='create_task',
        title='创建跟进任务',
        summary='跟进客户下一步动作',
        rationale='回答已形成下一步建议',
        riskLevel='low',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=material,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
        proposal_drafts=[draft],
        action_suggestions=[suggestion],
        answer_presentation={'sections': [{'title': '直接回答', 'content': '不应覆盖 directAnswerSeed'}]},
    )

    assert experience.status == 'ready'
    assert experience.directAnswer == '客户当前核心业务聚焦资源支持与项目服务。'
    assert experience.headline == '已形成可用回答'
    assert experience.userMessage == ''
    assert experience.evidenceChips
    assert experience.evidenceChips[0].title == '战略纪要'
    assert experience.evidenceChips[0].excerpt
    assert experience.evidenceChips[0].sourceKind == '关键依据'
    assert {item.actionType for item in experience.actionCards} >= {'request_evidence', 'create_task'}


def test_workspace_answer_experience_p29_filters_template_direct_answer_and_sets_boundary_message():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='\n'.join(
            [
                '基于当前资料，先给出可确认结论与下一步建议',
                '客户最新战略集中在能力建设、生态协作与数字化支持。',
            ]
        ),
        answerMode='grounded_answer',
        userVisibleQualityStatus='usable_with_boundary',
        shouldShowRetryBanner=False,
        qualityGrade='warn',
        internalGenerationStatus='llm_failed_but_kernel_answer_passed',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=None,
        answer_quality={'grade': 'warn', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
        answer_presentation={'sections': [{'title': '直接回答', 'content': '当前资料有限'}]},
    )

    assert experience.status == 'usable_with_boundary'
    assert experience.directAnswer == '客户最新战略集中在能力建设、生态协作与数字化支持。'
    assert experience.userMessage == '以下回答已基于客户资料生成，部分判断仍保留候选或资料边界。'
    assert experience.headline == '已形成可用回答，但部分内容需留意边界'


def test_workspace_answer_experience_p29_needs_retry_message_only_for_retry_state():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='',
        answerMode='grounded_fallback',
        userVisibleQualityStatus='needs_retry',
        shouldShowRetryBanner=True,
        qualityGrade='fail',
        internalGenerationStatus='llm_partial_preserved_after_retry',
    )

    experience = build_workspace_answer_experience(
        content='',
        finalization=finalization,
        answer_material=None,
        answer_quality={'grade': 'fail', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
    )

    assert experience.status == 'needs_retry'
    assert experience.userMessage == '建议重试或补充资料。'
    assert experience.headline == '本轮没有形成可靠答案'


def test_workspace_answer_experience_intro_profile_hides_boundary_actions_and_action_cards():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='日慈基金会是一家聚焦儿童青少年心理健康的公益基金会。',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='quality_passed',
    )
    material = AnswerMaterialRecord(
        directAnswerSeed='日慈基金会是一家聚焦儿童青少年心理健康的公益基金会。',
        keyFacts=['聚焦儿童青少年心理健康'],
        boundaryNotes=['当前仅覆盖已入库资料'],
        nextActions=['补充下一步责任人'],
        evidenceHighlights=[
            EvidenceItem(
                id='ev_1',
                title='机构简介',
                excerpt='日慈聚焦儿童青少年心理健康与心理教育。',
                sourceType='document',
                documentId='doc_1',
            )
        ],
    )
    draft = DataCenterProposalDraftRecord(
        id='draft_1',
        kind='evidence_request',
        title='补证据提案',
        summary='补齐关键证据',
        rationale='当前需要更多支持材料',
        riskLevel='low',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=material,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
        proposal_drafts=[draft],
        answer_intent='intro_profile',
    )

    assert experience.boundaryNotes == []
    assert experience.nextActions == []
    assert experience.actionCards == []
    assert all(signal != '包含下一步建议' for signal in experience.trustSignals)


def test_workspace_answer_experience_skips_intro_instruction_seed_and_uses_content():
    finalization = WorkspaceAnswerFinalizationRecord(
        content='日慈基金会是一家以儿童青少年心理健康与心理教育为核心议题的公益基金会。\n\n1）它主要在解决什么问题',
        answerMode='grounded_answer',
        userVisibleQualityStatus='ready',
        shouldShowRetryBanner=False,
        qualityGrade='pass',
        internalGenerationStatus='quality_passed',
    )
    material = AnswerMaterialRecord(
        directAnswerSeed='请先用一两句话写清这个机构是什么、核心议题是什么；再解释它在解决什么更结构性的问题。',
    )

    experience = build_workspace_answer_experience(
        content=finalization.content,
        finalization=finalization,
        answer_material=material,
        answer_quality={'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
    )

    assert experience.directAnswer.startswith('日慈基金会是一家以儿童青少年心理健康与心理教育为核心议题的公益基金会')
