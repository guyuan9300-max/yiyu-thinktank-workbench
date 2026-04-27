# 源码文件：`backend/app/main.py`（分片 01）

- 行号范围：1-2800
- 总行数：   30416
- 导出时间：2026-04-20

```python
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from app.services.system_logger import SystemLogger as _SystemLogger
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from typing import Callable, Literal, cast
from urllib.parse import quote, urlparse, urlunparse
from uuid import uuid4

import httpx
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from docx import Document as WordDocument

from app.db import BACKEND_SCHEMA_VERSION, Database, from_json, to_json
from app.local_request_guard import ALLOWED_LOCAL_ORIGINS, ALLOWED_LOCAL_ORIGIN_REGEX, validate_local_browser_request
from app.models import (
    ActivityLogRecord,
    AgentWeeklyPlanPayload,
    AgentWeeklyPlanRecord,
    AgentWorklogResponse,
    AiTagSuggestionPayload,
    AiTagSuggestionResponse,
    AiStructuredResponse,
    AnalysisRunPayload,
    AnalysisRunRecord,
    AnalysisBackfillMainChainPayload,
    AnalysisBackfillMainChainResultRecord,
    AnalysisCenterSummaryRecord,
    AnalysisJobCreatePayload,
    AnalysisJobRecord,
    AnalysisJobStageRunRecord,
    AnalysisWorkerCounterSnapshotRecord,
    AnalysisWorkbenchSettingsPayload,
    AnalysisWorkbenchSettingsRecord,
    AnalysisTemplateRecord,
    AnalysisToolsResponse,
    CoachCaseRecord,
    CoachCardRecord,
    CoachPayload,
    CoachReminderRule,
    AuthLoginPayload,
    AuthRegisterPayload,
    AuthStateResponse,
    LocalInputMemoryAiSettings,
    LocalInputMemoryCloudAuth,
    LocalInputMemoryFeishuIntegration,
    LocalInputMemoryResponse,
    RememberedCloudAuthAccount,
    SaveAiInputMemoryPayload,
    SaveCloudAuthInputMemoryPayload,
    SaveFeishuInputMemoryPayload,
    UpdateProfilePayload,
    AccountOverviewResponse,
    AmbiguityItem,
    AppSettingsPayload,
    AppSettingsResponse,
    BackupResponse,
    BadgeBoardResponse,
    ChatMessageRecord,
    ChatRequest,
    ChatStartResponse,
    ChatThreadDetailResponse,
    ChatThread,
    ClarificationAnswerPayload,
    ClarificationCreatePayload,
    ClarificationRecord,
    CloudConfigResponse,
    ConsultationKnowledgeProcessSummaryResponse,
    ConsultationKnowledgeRequestRecord,
    ClientDnaGeneratePayload,
    ClientDnaModuleRecord,
    ClientDnaModulesResponse,
    ClientAnalysisEvidenceSummaryRecord,
    ClientAnalysisRunRecord,
    ClientFolder,
    ClientMutationPayload,
    ClientSummary,
    ClientTemplateFillFieldRecord,
    ClientTemplateFillPayload,
    ClientTemplateFillRunRecord,
    ClientTemplateFillResponse,
    ClientTextDocumentPayload,
    ClientTextDocumentResponse,
    ClientNotebookResponse,
    ClientWorkspaceResponse,
    ClientWorkspaceSettingsPayload,
    ClientWorkspaceSettingsRecord,
    DecisionItem,
    DemoDataResponse,
    DnaTerm,
    DnaTermPayload,
    DocumentCardRecord,
    DocumentRecord,
    DeepDnaDraft,
    DeepDnaRecord,
    DeepDnaSourceRecord,
    DiagnosisProfileRecord,
    DnaDeltaCreatePayload,
    DnaDeltaRecord,
    EvidenceItem,
    ExportAnswerPayload,
    JudgmentConfirmPayload,
    JudgmentVersionRecord,
    FileReclassEventRecord,
    GoalPayload,
    GoalRecord,
    GrowthContextLinkRecord,
    GrowthAfterActionCaptureRecord,
    GrowthGenericLessonRecord,
    GrowthLedgerResponse,
    GrowthOverviewRecord,
    GrowthPendingCaptureActionPayload,
    GrowthPendingCaptureActionResponse,
    GrowthProjectGuidanceRecord,
    GrowthReasoningInputRecord,
    GrowthReasoningTraceRecord,
    GrowthRecommendationActionResponse,
    GrowthRecommendationDismissPayload,
    GrowthActionPlanItemRecord,
    GrowthMaterialRefRecord,
    GrowthProjectContextPackRecord,
    GrowthLearningSummaryRecord,
    GrowthRobotAssistRecord,
    GrowthTaskIntentRecord,
    GrowthUniversalSkillItemRecord,
    GrowthValidationActionResponse,
    GrowthValidationPayload,
    GrowthWorkbenchActionRecord,
    GrowthWorkbenchMaterialRecord,
    GrowthWorkbenchSnapshotRecord,
    GrowthWorkbenchStepRecord,
    GrowthWorkbenchSupportCopyRecord,
    GrowthWorkbenchTaskRecord,
    HandbookEntryRecord,
    HandbookEntryDetailRecord,
    HandbookReuseRecord,
    HandbookPayload,
    HandbookSettingsPayload,
    HandbookSettingsRecord,
    HandbookResponse,
    HealthAiState,
    HealthResponse,
    ImportPayload,
    ImportRecord,
    WorkspaceImportBackfillResponse,
    LegacyScanEntry,
    LegacyScanRequest,
    LegacyScanResponse,
    KnowledgeJobRecord,
    KnowledgeSearchHitRecord,
    KnowledgeSearchResponse,
    KnowledgeStatusRecord,
    MemoryStatus,
    DepartmentOptionRecord,
    MentionCandidateRecord,
    MeetingCreatePayload,
    MeetingDetail,
    MeetingIngestPayload,
    MeetingPipelineResponse,
    MeetingSummary,
    EmployeeDepartmentPayload,
    EmployeeRecord,
    EmployeeRejectPayload,
    EmployeeRolePayload,
    FeishuBotSettingsPayload,
    FeishuBotSettingsRecord,
    FeishuMemberAuthorizationRecord,
    FeishuMemberAuthorizationStartResponse,
    FeishuMeetingLaunchPayload,
    FeishuMeetingLaunchResponse,
    FeishuReceiveIdType,
    FeishuUserBindingRecord,
    FeishuUserBindingStartResponse,
    DnaReadinessQuestionRecord,
    EventLineActivityRecord,
    EventLineClarificationDraftPayload,
    EventLineClarificationDraftRecord,
    EventLineContextBundleRecord,
    EventLineContextFactRecord,
    EventLineCreatePayload,
    EventLineDetailRecord,
    EventLineJudgmentRecord,
    EventLineProjectFilterOptionRecord,
    EventLineOpportunityCardRecord,
    EventLineMemoryResponse,
    EventLineRecord,
    EventLineRiskCardRecord,
    EventLineSourceStatusRecord,
    EventLineUpdatePayload,
    OperatorRecord,
    OrgDepartmentRecord,
    OrgEmployeeBindingRecord,
    OrgFeishuIntegrationRecord,
    OrgFeishuIntegrationSavePayload,
    OrgModelProfileRecord,
    OrgMembershipSummaryRecord,
    OrgWritingNorm,
    OrgProfileRecord,
    OrgReportingLineRecord,
    OrgRoleTemplateRecord,
    OrgTaskControlRuleRecord,
    OrganizationDnaModuleRecord,
    OrganizationDnaResponse,
    OrganizationDnaUploadPayload,
    OrganizationNotebookSnapshot,
    ProjectFlowPayload,
    ProjectFlowRecord,
    ProjectFlowDetailRecord,
    ProjectModulePayload,
    ProjectModuleRecord,
    ProjectModuleDetailRecord,
    ProjectStructureResponse,
    ReviewDepartmentConfigRecord,
    ReviewDepartmentMemberRecord,
    ReviewDashboardCardTargetRecord,
    ReviewDashboardEvidenceRefRecord,
    ReviewDashboardDrillTargetResponse,
    ReviewGovernanceSettingsPayload,
    ReviewGovernanceSettingsRecord,
    ReviewHistoryEntryRecord,
    ReviewHistoryResponse,
    ReviewResponse,
    ReviewSimulationBundleRecord,
    RiskItem,
    RunComparison,
    SessionUserRecord,
    SettingsResponse,
    SystemAdminSettingsPayload,
    SystemAdminSettingsRecord,
    TaskActivityRecord,
    TaskAttachmentRecord,
    TaskBoardResponse,
    TaskCollaboratorRecord,
    TaskCompletionReviewPayload,
    TaskContextPreviewRecord,
    PrepPackCardRecord,
    PrepPackMaterialRecord,
    ProposalDecisionPayload,
    ProposalExecutionResponse,
    ProposalRecordRecord,
    ProposalTargetRefRecord,
    ChatRetrievalDecisionReason,
    WorkspaceAnswerIntent,
    JudgmentQueryMode,
    EvidenceSupportMode,
    EvidenceSupportItemRecord,
    ExecutionTicketRecord,
    ExecutionTicketResultRecord,
    ExecutionArtifactRefRecord,
    HybridJudgmentContextPackRecord,
    StateAnswerContextPackRecord,
    StateAnswerSectionsRecord,
    StateQueryHitRecord,
    StateQueryPlanRecord,
    StateSourceSummaryRecord,
    TaskSmartBriefRecord,
    TaskSmartBriefActionItem,
    TaskListLibraryResponse,
    TaskListMutationPayload,
    TaskListRecord,
    MemoryBackfillResultRecord,
    NarrativeAnalysisRecord,
    MainChainStabilitySettingsPayload,
    MainChainStabilitySettingsRecord,
    TaskNotePayload,
    TaskContextRefreshResultRecord,
    TaskEventLineBootstrapResultRecord,
    TaskOrgBackfillResultRecord,
    TaskOrgContextRecord,
    TaskProjectContextRecord,
    TaskPlanLinkRecord,
    TaskPlanLinkUpsertPayload,
    TaskPayload,
    TaskRecord,
    TaskRejectPayload,
    TaskSettingsPayload,
    TaskSettingsRecord,
    TaskViewDefinitionRecord,
    TaskViewMutationPayload,
    TaskViewPresetRecord,
    TaskViewsResponse,
    SupportRequestCreatePayload,
    SupportRequestRecord,
    SupportRequestResolvePayload,
    TaskTagLibraryResponse,
    TaskTagMutationPayload,
    TaskTagRecord,
    TaskUpdatePayload,
    TitleSuggestionResponse,
    TopicRadarAssistPayload,
    TopicRadarAssistResponse,
    TopicRadarPreferredSourceRecord,
    TopicRadarSourceLabelPayload,
    TopicRadarSourceLabelResponse,
    TopicCandidatePayload,
    TopicCandidateChatPayload,
    TopicCandidateChatResponse,
    TopicCandidateChatMessageRecord,
    TopicCandidateInsightRecord,
    TopicCandidateRecord,
    TopicCaptureBatchResponse,
    TopicCaptureRunRecord,
    TopicTaskDraftPayload,
    TopicTaskPlanResponse,
    TopicTaskPromotionPayload,
    TopicTaskPromotionResponse,
    TopicTaskSuggestionRecord,
    TopicsSettingsPayload,
    TopicsSettingsRecord,
    TopicTitlePayload,
    TopicRadarPayload,
    TopicRadarRecord,
    TopicsResponse,
    StrategicAssetCandidateRecord,
    StrategicChangePointRecord,
    StrategicChecklistGroupRecord,
    StrategicChecklistItemRecord,
    StrategicCockpitConfirmPayload,
    StrategicCockpitSnapshotRecord,
    StrategicEvidenceCardRecord,
    StrategicEvidencePreviewRecord,
    StrategicHealthLineRecord,
    StrategicHeadlineRecord,
    StrategicJudgmentRecord,
    StrategicMeetingPackDraftRecord,
    StrategicPermissionRecord,
    StrategicReadinessRecord,
    StrategicThoughtRecord,
    StrategicThoughtReviewPayload,
    StrategicThoughtReviewRecord,
    StrategicThoughtSourceRecord,
    StrategicThoughtsResponseRecord,
    StrategicLineRecord,
    StrategicLineDetailRecord,
    VectorizeAnswerPayload,
    WeeklyReviewAnalysisRecord,
    WeeklyReviewEventLineContextRecord,
    WeeklyReviewPayload,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    UnderstandingSnapshotV1Record,
    WeeklyReviewRecord,
    WeeklyReviewTaskStructuredNoteRecord,
    TrendSignalRecord,
    AgendaItem,
    KnowledgeMemoryRecord,
    LearningRecommendationRecord,
    AnalysisMigrationMetricsRecord,
    ApprovalDecisionPayload,
    ApprovalRecordRecord,
    OpenQuestionRecord,
    ConflictGroupRecord,
    ContextPackRecord,
    RuntimeRunLogRecord,
    ThemeClusterRecord,
    WorkspaceStateItemRecord,
    WorkspaceStateProjectionRecord,
    PageContextPackRecord,
)
from app.services.ai import AiInvocationError, AiService, DEFAULT_MODEL, DEFAULT_PROVIDER
from app.services.analysis_context import (
    build_client_page_context_pack,
    build_task_page_context_pack,
    decide_answer_policy,
    infer_page_intent,
)
from app.services.analysis_center import (
    claim_next_analysis_job,
    confirm_judgment,
    create_analysis_job,
    create_dna_delta,
    decide_approval,
    execute_analysis_job_projection,
    fail_analysis_job,
    get_analysis_migration_metrics,
    get_candidate_review_sla_summary,
    get_client_analysis_bundle,
    get_analysis_job,
    get_runtime_run_log,
    is_analysis_backfill_paused,
    list_analysis_job_stages,
    list_conflict_groups,
    list_dna_deltas,
    list_judgment_versions,
    list_open_questions,
    list_runtime_run_logs,
    list_theme_clusters,
    looks_like_attachment_ingest_boilerplate,
    queue_main_chain_backfill,
    recover_stale_analysis_jobs,
    set_analysis_backfill_paused,
)
from app.services.agent_worklogs import (
    AGENT_AUTO_SOURCE_TYPE,
    build_agent_execution_task_activity,
    build_agent_execution_tasks,
    build_agent_weekly_digests,
    build_agent_weekly_plans,
    build_agent_weekly_review_items,
    build_agent_worklog_response,
    sync_agent_execution_tasks,
    upsert_agent_weekly_plan_override,
)
from app.services.department_catalog import get_department_entry, list_department_catalog
from app.services.knowledge_base import (
    batch_enrich_surrogates,
    create_memory_surrogate_from_answer,
    ensure_source_tree_snapshot,
    ensure_client_workspace,
    fetch_recent_knowledge_jobs,
    fetch_recent_reclass_events,
    is_finance_priority_text,
    is_finance_query,
    is_finance_statement_priority_text,
    is_finance_statement_query,
    sync_master_index_fts,
    sync_qdrant_for_client,
)
from app.services.knowledge_v2 import (
    HUMAN_VISIBLE_CATEGORIES,
    V2_PIPELINE_VERSION,
    backfill_knowledge_documents,
    backfill_workspace_import,
    compute_knowledge_status,
    deserialize_retrieval_bundle,
    fetch_document_cards,
    ingest_document_knowledge,
    is_strategy_analysis_query,
    MAIN_KNOWLEDGE_STATUS_JOB_TYPES,
    refresh_client_folder_counts,
    retrieve_knowledge_bundle,
    safe_filename,
    serialize_retrieval_bundle,
    stage_import_copy,
    tokenize,
)
from app.services.client_profile import backfill_all_clients, build_client_profile
from app.services.memory_foundation import (
    answer_clarification_record,
    backfill_memory_foundation,
    create_clarification_record,
    get_client_memory_status,
    get_client_notebook_response,
    get_event_line_memory_response,
    get_task_memory_enrichment,
    list_linked_event_lines,
    record_imported_document_writeback,
    record_client_dna_writeback,
    record_meeting_publish_writeback,
    record_task_attachment_writeback,
    record_task_writeback,
    record_weekly_review_writeback,
    refresh_event_line_memory_snapshot,
    refresh_organization_notebook_snapshot,
    sanitize_memory_background_text,
)
from app.services.platform_dna import extract_platform_dna_text
from app.services.template_fill import (
    TemplateWebSource,
    apply_docx_template_values,
    build_template_follow_up_question,
    build_template_fill_retrieval_query,
    build_template_suggested_sources,
    extract_docx_attachment_checklist,
    extract_docx_template_fields,
    fetch_template_fill_web_sources,
    infer_template_field_type,
    infer_template_value_kind,
    should_enable_template_fill_web_supplement,
)
from app.services.topic_capture import fetch_topic_candidates_from_web, fetch_topic_source_excerpt
from app.services.review_analysis import _dedupe_texts, _story_evidence_refs, build_weekly_review_analysis
from app.services.review_narrative import build_weekly_overview_draft
from app.services.local_memory import gather_project_context_for_ai, read_project_memory, rehome_event_line_memory, write_project_memory, write_event_line_memory, write_weekly_memory, should_dream, run_dream_cycle
from app.services.review_rollup import build_employee_review_report, build_executive_review_rollup
from app.services.review_simulation import build_review_simulation_bundle
from app.services.feishu import (
    FeishuApiError,
    build_user_authorize_url,
    exchange_authorization_code,
    fetch_app_access_token,
    fetch_tenant_access_token,
    fetch_user_info,
    send_text_message,
)
from app.services.badge_engine import build_badge_board
from app.services.growth_engine import (
    backfill_handbook_entries,
    build_growth_ledger,
    build_generic_learning_fallback,
    build_growth_overview,
    get_pending_capture,
    ingest_meeting_growth_candidate,
    ingest_handbook_codification,
    ingest_strategic_growth_candidate,
    ingest_task_growth_candidate,
    ingest_review_growth,
    list_learning_recommendations,
    mark_handbook_entry_reused,
    mark_recommendation_accepted,
    mark_recommendation_dismissed,
    update_pending_capture_state,
)
from app.services.learning_presets import (
    build_actions_from_presets,
    default_starter_learning_presets,
    match_learning_presets,
    preset_card_to_generic_lesson,
    preset_card_to_support_material,
)
from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore


APP_NAME = "益语智库自用平台"
APP_VERSION = "0.1.0"
APP_BUILD_VERSION = "2026.03.15-v2-migration-1"
LOCAL_INPUT_MEMORY_SETTINGS_KEY = "settings.local_input_memory"
REMEMBERED_CLOUD_AUTH_SERVICE = "com.yiyu.self-workbench.remembered-cloud-auth"
REMEMBERED_AI_INPUT_SERVICE = "com.yiyu.self-workbench.remembered-ai-input"
REMEMBERED_FEISHU_INPUT_SERVICE = "com.yiyu.self-workbench.remembered-feishu-input"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
THREAD_SYNC_DOC_PATH = PROJECT_ROOT / "docs" / "thread-sync.md"
SUPPORTED_IMPORT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".pptx", ".xlsx"}
LEGACY_IMPORT_EXTENSIONS = {".json", ".csv"}
DEMO_CLIENT_IDS = ("client_cffc", "client_star")
DEMO_THREAD_IDS = ("thread_cffc", "thread_star")
DEMO_GOAL_IDS = ("goal_1", "goal_2", "goal_3")
DEMO_DNA_IDS = ("dna_1", "dna_2")
DEMO_DOCUMENT_IDS = ("doc_1", "doc_2", "doc_3")
DEMO_TASK_IDS = ("task_seed_1", "task_seed_2")
DEMO_RADAR_IDS = ("radar_ai", "radar_fund")
DEMO_CANDIDATE_IDS = ("cand_1", "cand_2")
DEMO_HANDBOOK_IDS = ("hb_1",)
DEMO_CHAT_MESSAGE_IDS = ("msg_seed_1",)
BACKEND_FEATURE_FLAGS = [
    "knowledge.vectorize-answer",
    "knowledge.reclass-events",
    "knowledge.surrogate-index",
    "knowledge.search",
    "knowledge.rebuild",
    "chat.general-answer",
    "chat.instant-send",
    "chat.async-status",
    "chat.analysis-runs",
]

ORGANIZATION_DNA_MODULES = [
    ("organization_intro", "组织介绍"),
    ("business_intro", "业务介绍"),
    ("team_intro", "团队介绍"),
    ("market_intro", "市场介绍"),
]

CLIENT_DNA_MODULES = [
    ("organization_intro", "组织介绍"),
    ("business_intro", "项目介绍"),
    ("team_intro", "团队介绍"),
    ("market_intro", "市场背景介绍"),
]

SELF_CLIENT_NAME_CANDIDATES = ["益语智库", "益语"]

DNA_READINESS_RULES: dict[str, list[dict[str, object]]] = {
    "organization_intro": [
        {
            "question": "组织定位是否清楚",
            "contentKeywords": ["定位", "战略陪伴者", "成长合伙人", "可落地的增长咨询"],
            "missingKeywords": [],
        },
        {
            "question": "组织为什么存在、主要解决什么问题是否清楚",
            "contentKeywords": ["使命", "市场不确定性", "组织效率", "数字化焦虑", "穿越不确定期"],
            "missingKeywords": [],
        },
        {
            "question": "当前升级方向或阶段是否清楚",
            "contentKeywords": ["内部引擎", "应用共建", "学习加速", "升级", "转型"],
            "missingKeywords": [],
        },
    ],
    "business_intro": [
        {
            "question": "主要服务或交付内容是否清楚",
            "contentKeywords": ["增长咨询", "战略设计", "流程陪伴", "应用共建", "学习加速", "工作平台"],
            "missingKeywords": [],
        },
        {
            "question": "服务对象和价值是否清楚",
            "contentKeywords": ["适应性组织", "企业", "持续增长", "客户痛点", "解决方案"],
            "missingKeywords": [],
        },
        {
            "question": "当前业务重点或推进路径是否清楚",
            "contentKeywords": ["技术规划", "产品", "0.5", "3.0", "GPT 5.4", "升级"],
            "missingKeywords": [],
        },
    ],
    "team_intro": [
        {
            "question": "关键成员与角色是否清楚",
            "contentKeywords": ["成员", "负责人", "角色", "团队"],
            "missingKeywords": ["成员名单", "创始人", "负责人", "履历"],
        },
        {
            "question": "分工与协作结构是否清楚",
            "contentKeywords": ["分工", "协作", "组织架构", "接口"],
            "missingKeywords": ["组织架构", "分工", "接口"],
        },
        {
            "question": "当前团队能力重点是否清楚",
            "contentKeywords": ["AI 技术", "工作平台", "技术布局", "能力", "升级"],
            "missingKeywords": [],
        },
    ],
}

STRATEGIC_PLACEHOLDER_CONTEXT_PATTERNS = [
    "当前重点仍待补充",
    "建议先明确这一阶段的核心事项",
    "当前没有特别突出的阻塞",
    "仍需盯住推进收束",
    "下一步动作：先补齐项目背景",
    "最近进展仍待补充",
]

STRATEGIC_PLACEHOLDER_THOUGHT_TEXTS = {
    "",
    "当前阻塞仍待澄清",
    "先补下一步动作",
    "暂无",
    "待补充",
    "待确认",
    "待澄清",
    "暂无明确判断",
    "以下内容仅供排查，不代表正式结论",
    "当前还没有稳定识别到这条线最主要的阻塞",
    "最近关键决策仍待补充",
    "先把下一步动作拆清楚再进入会谈推进",
}

STRATEGIC_INTERNAL_TOPIC_KEYS = {
    "client_overview",
    "org_overview",
    "project_overview",
    "main_contradiction",
    "core_breakthrough",
    "pending_material",
    "pending_decision",
}

STRATEGIC_PLACEHOLDER_THOUGHT_TEXTS_NORMALIZED = {
    re.sub(r"\s+", " ", item.strip()).replace("：", ":").replace("，", ",").replace("。", ".").replace(" ", "").lower()
    for item in STRATEGIC_PLACEHOLDER_THOUGHT_TEXTS
}

STRATEGIC_RELATIONSHIP_TASK_KEYWORDS = [
    "吃饭",
    "见面",
    "会面",
    "拜访",
    "约",
    "沟通",
    "介绍",
    "对接",
    "维护关系",
    "关系推进",
]

STRATEGIC_CONTEXTUAL_DESCRIPTION_KEYWORDS = [
    "机构",
    "基金会",
    "负责人",
    "背景",
    "合作",
    "关系",
    "推进",
    "目标",
    "希望",
    "这次",
    "本次",
    "当前",
    "下一步",
    "方案",
]

STRATEGIC_WEEKLY_MEETING_KEYWORDS = ["周会", "周盘点", "周例会", "战略", "经营", "复盘"]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


APP_STARTED_AT = now_iso()


def detect_runtime_mode() -> Literal["packaged", "dev"]:
    source_path = str(Path(__file__).resolve())
    return "packaged" if ".app/Contents/Resources/" in source_path else "dev"


def build_backend_runtime_fingerprint() -> str:
    backend_root = Path(__file__).resolve().parents[1]
    fragments: list[str] = []
    for file_name in ("pyproject.toml", "uv.lock"):
        target = backend_root / file_name
        if not target.exists():
            continue
        stat = target.stat()
        fragments.append(f"{file_name}:{stat.st_size}:{int(stat.st_mtime_ns / 1_000_000)}")
    if not fragments:
        fragments.append(APP_BUILD_VERSION)
    return "|".join(fragments)


BACKEND_RUNTIME_MODE = detect_runtime_mode()
BACKEND_BUILD_HASH = os.getenv("YIYU_BACKEND_BUILD_HASH", build_backend_runtime_fingerprint())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def today_label() -> str:
    return datetime.now().strftime("%m-%d")


def normalize_markdown_text(markdown_content: str) -> str:
    text = markdown_content.replace("\r\n", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"[>*_~#|-]", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def summarize_markdown_document(title: str, normalized_text: str) -> str:
    clean = normalized_text.strip()
    if not clean:
        return f"{title}当前还没有可用内容，请重新上传完整 Markdown 文档。"
    paragraphs = [segment.strip() for segment in re.split(r"\n{2,}", clean) if segment.strip()]
    lead = paragraphs[0] if paragraphs else clean
    detail = paragraphs[1] if len(paragraphs) > 1 else ""
    summary = lead[:160]
    if detail:
        summary = f"{summary} {detail[:120]}".strip()
    if len(summary) < 80 and len(clean) > len(summary):
        summary = f"{summary} {clean[len(summary):len(summary) + 120]}".strip()
    return summary[:320]


@dataclass
class AppState:
    data_dir: Path
    backup_dir: Path
    db: Database
    ai: AiService
    feishu_secret_store: MacOSKeychainSecretStore | MemorySecretStore
    cloud_api_url: str
    job_stop: Event
    job_thread: Thread | None = None
    analysis_job_thread: Thread | None = None
    topic_insight_executor: ThreadPoolExecutor | None = None
    chat_answer_executor: ThreadPoolExecutor | None = None
    template_fill_executor: ThreadPoolExecutor | None = None
    volatile_cloud_access_token: str = ""
    volatile_cloud_refresh_token: str = ""
    volatile_cloud_session_user_json: str = ""
    cloud_session_persistent: bool = False
    consultation_knowledge_sync_running: bool = False
    system_logger: _SystemLogger | None = None


_runtime_state: AppState | None = None
logger = logging.getLogger(__name__)


def _require_runtime_state() -> AppState:
    if _runtime_state is None:
        raise RuntimeError("App state is not initialized")
    return _runtime_state


def _run_chat_fact_extraction(
    db: Database,
    ai_service: AiService | object | None,
    *,
    client_id: str,
    thread_id: str,
    user_prompt: str,
    assistant_content: str,
    answer_mode: str,
) -> None:
    try:
        from app.services.memory_foundation import extract_chat_facts_to_memory

        extract_chat_facts_to_memory(
            db,
            ai_service,
            client_id=client_id,
            thread_id=thread_id,
            user_prompt=user_prompt,
            assistant_content=assistant_content,
            answer_mode=answer_mode,
        )
    except Exception:
        logger.warning("[chat-fact-extract] Background extraction failed", exc_info=True)


def _schedule_chat_fact_extraction(
    state: AppState,
    *,
    client_id: str,
    thread_id: str,
    user_prompt: str,
    assistant_content: str,
    answer_mode: str,
) -> None:
    if answer_mode in ("system_failure", ""):
        return
    if len(user_prompt.strip()) < 10 or len(assistant_content.strip()) < 30:
        return
    target = _run_chat_fact_extraction
    kwargs = {
        "client_id": client_id,
        "thread_id": thread_id,
        "user_prompt": user_prompt,
        "assistant_content": assistant_content,
        "answer_mode": answer_mode,
    }
    executor = state.topic_insight_executor or state.chat_answer_executor
    if executor is not None:
        try:
            executor.submit(target, state.db, state.ai, **kwargs)
            return
        except Exception:
            logger.warning("[chat-fact-extract] Failed to submit background extraction", exc_info=True)
    try:
        Thread(
            target=target,
            args=(state.db, state.ai),
            kwargs=kwargs,
            daemon=True,
        ).start()
    except Exception:
        logger.warning("[chat-fact-extract] Failed to start fallback background thread", exc_info=True)


def _parse_json_list(value: str | None) -> list[str]:
    data = from_json(value, [])
    return [str(item) for item in data] if isinstance(data, list) else []


def _parse_date_only(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _week_bounds(week_label: str) -> tuple[datetime.date, datetime.date] | None:
    match = re.match(r"^(\d{4})-W(\d{2})$", week_label.strip())
    if not match:
        return None
    year = int(match.group(1))
    week = int(match.group(2))
    try:
        start = datetime.fromisocalendar(year, week, 1).date()
    except ValueError:
        return None
    return start, start + timedelta(days=6)


def _task_review_date(task: TaskRecord) -> datetime.date | None:
    due_date = _parse_date_only(task.dueDate)
    if due_date:
        return due_date
    return _parse_date_only(task.createdAt)


def _task_in_week(task: TaskRecord, week_label: str) -> bool:
    bounds = _week_bounds(week_label)
    if not bounds:
        return False
    review_date = _task_review_date(task)
    if not review_date:
        return False
    start, end = bounds
    return start <= review_date <= end


    def _local_task_tag_record(row) -> TaskTagRecord:
        return TaskTagRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            color=str(row["color"] or ("#9CA3AF" if str(row["scope"]) == "self" else "#5B7BFE")),
            scope=str(row["scope"]),
            ownerUserId=str(row["owner_operator_id"]) if str(row["owner_operator_id"]) else None,
            createdBy=str(row["created_by"]) if str(row["created_by"]) else None,
            updatedAt=str(row["updated_at"] or row["created_at"] or now_iso()),
            archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
        )

    def _local_task_list_record(row) -> TaskListRecord:
        return TaskListRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            color=str(row["color"]),
            sortOrder=int(row["sort_order"] or 0),
            isDefault=bool(int(row["is_default"] or 0)),
            scope=str(row["scope"] or "org"),
            archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
        )

    def _local_default_list_id() -> str | None:
        default_row = state.db.fetchone("SELECT id FROM task_lists WHERE is_default = 1 ORDER BY sort_order ASC LIMIT 1")
        if default_row:
            return str(default_row["id"])
        first_row = state.db.fetchone("SELECT id FROM task_lists ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1")
        return str(first_row["id"]) if first_row else None

    def _default_local_task_settings() -> TaskSettingsRecord:
        return TaskSettingsRecord(
            defaultListId=_local_default_list_id(),
            defaultPriority="normal",
            defaultDueDatePreset="today",
            defaultViewMode="calendar",
            listSortMode="manual",
            showCompletedTasks=False,
            defaultReviewScope="work",
            autoAssignSelf=True,
            updatedAt=now_iso(),
        )

    def _local_task_settings_record(row) -> TaskSettingsRecord:
        defaults = _default_local_task_settings()
        return TaskSettingsRecord(
            defaultListId=str(row["default_list_id"]) if row["default_list_id"] else defaults.defaultListId,
            defaultPriority=str(row["default_priority"] or defaults.defaultPriority),  # type: ignore[arg-type]
            defaultDueDatePreset=str(row["default_due_date_preset"] or defaults.defaultDueDatePreset),  # type: ignore[arg-type]
            defaultViewMode=str(row["default_view_mode"] or defaults.defaultViewMode),  # type: ignore[arg-type]
            listSortMode=str(row["list_sort_mode"] or defaults.listSortMode),  # type: ignore[arg-type]
            showCompletedTasks=bool(int(row["show_completed_tasks"] or 0)),
            defaultReviewScope=str(row["default_review_scope"] or defaults.defaultReviewScope),  # type: ignore[arg-type]
            autoAssignSelf=bool(int(row["auto_assign_self"] if row["auto_assign_self"] is not None else 1)),
            updatedAt=str(row["updated_at"] or defaults.updatedAt),
        )

    def _get_local_task_settings(operator_id: str | None = None) -> TaskSettingsRecord:
        resolved_operator_id = operator_id or str(current_operator_row()["id"])
        row = state.db.fetchone("SELECT * FROM task_settings WHERE operator_id = ?", (resolved_operator_id,))
        if row:
            return _local_task_settings_record(row)
        defaults = _default_local_task_settings()
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_settings(
                operator_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_operator_id,
                defaults.defaultListId,
                defaults.defaultPriority,
                defaults.defaultDueDatePreset,
                defaults.defaultViewMode,
                defaults.listSortMode,
                1 if defaults.showCompletedTasks else 0,
                defaults.defaultReviewScope,
                1 if defaults.autoAssignSelf else 0,
                defaults.updatedAt,
            ),
        )
        return defaults

    def _visible_local_task_tag_rows(db: Database, operator_id: str) -> list:
        return db.fetchall(
            """
            SELECT *
            FROM task_tags
            WHERE scope = 'org' OR owner_operator_id = ?
            ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                     CASE scope WHEN 'org' THEN 0 ELSE 1 END,
                     name COLLATE NOCASE ASC
            """,
            (operator_id,),
        )

    def _visible_local_task_tags(db: Database, operator_id: str) -> list[TaskTagRecord]:
        return [_local_task_tag_record(row) for row in _visible_local_task_tag_rows(db, operator_id)]


    def _visible_local_task_tag_rows(db: Database, operator_id: str) -> list:
        return db.fetchall(
            """
            SELECT *
            FROM task_tags
            WHERE scope = 'org' OR owner_operator_id = ?
            ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                     CASE scope WHEN 'org' THEN 0 ELSE 1 END,
                     name COLLATE NOCASE ASC
            """,
            (operator_id,),
        )


def _visible_local_task_tags(db: Database, operator_id: str) -> list[TaskTagRecord]:
    return [_global_local_task_tag_record(row) for row in _visible_local_task_tag_rows(db, operator_id)]


def _local_tag_rows_by_ids(db: Database, tag_ids: list[str]) -> list:
    if not tag_ids:
        return []
    rows = db.fetchall(
        f"SELECT * FROM task_tags WHERE id IN ({_sql_placeholders(tag_ids)})",
        tuple(tag_ids),
    )
    by_id = {str(row["id"]): row for row in rows}
    return [by_id[tag_id] for tag_id in tag_ids if tag_id in by_id]


def _global_local_task_tag_record(row) -> TaskTagRecord:
    return TaskTagRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        color=str(row["color"] or ("#9CA3AF" if str(row["scope"]) == "self" else "#5B7BFE")),
        scope=str(row["scope"]),
        ownerUserId=str(row["owner_operator_id"]) if str(row["owner_operator_id"]) else None,
        createdBy=str(row["created_by"]) if str(row["created_by"]) else None,
        updatedAt=str(row["updated_at"] or row["created_at"] or now_iso()),
        archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
    )

def _ensure_local_tag(
    db: Database,
    operator_id: str,
    name: str,
    scope: str = "org",
    color: str | None = None,
    created_by: str | None = None,
) -> TaskTagRecord:
    trimmed = name.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Tag name is required")
    owner_operator_id = operator_id if scope == "self" else ""
    resolved_color = color or ("#9CA3AF" if scope == "self" else "#5B7BFE")
    operator_row = db.fetchone("SELECT name FROM operators WHERE id = ?", (operator_id,))
    resolved_creator = created_by or (str(operator_row["name"]) if operator_row and operator_row["name"] else "系统")
    existing = db.fetchone(
        "SELECT * FROM task_tags WHERE name = ? AND scope = ? AND owner_operator_id = ?",
        (trimmed, scope, owner_operator_id),
    )
    timestamp = now_iso()
    if existing:
        if not str(existing["updated_at"]) or not str(existing["color"] or ""):
            db.execute(
                """
                UPDATE task_tags
                SET updated_at = ?, created_at = COALESCE(NULLIF(created_at, ''), ?),
                    color = COALESCE(NULLIF(color, ''), ?), created_by = COALESCE(NULLIF(created_by, ''), ?)
                WHERE id = ?
                """,
                (timestamp, timestamp, resolved_color, resolved_creator, str(existing["id"])),
            )
            existing = db.fetchone("SELECT * FROM task_tags WHERE id = ?", (str(existing["id"]),))
        assert existing is not None
        return _global_local_task_tag_record(existing)
    tag_id = new_id("tag")
    db.execute(
        """
        INSERT INTO task_tags(id, name, scope, color, owner_operator_id, created_by, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tag_id, trimmed, scope, resolved_color, owner_operator_id, resolved_creator, timestamp, timestamp),
    )
    row = db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
    assert row is not None
    return _global_local_task_tag_record(row)


def _resolve_local_task_tags(db: Database, operator_id: str, tag_ids: list[str], legacy_names: list[str]) -> list[TaskTagRecord]:
    rows = _local_tag_rows_by_ids(db, tag_ids)
    if rows:
        return [_global_local_task_tag_record(row) for row in rows]
    if not legacy_names:
        return []
    return [_ensure_local_tag(db, operator_id, name, "org") for name in legacy_names if name.strip()]


_event_line_snapshot_cache: dict[str, dict[str, object] | None] = {}


def _invalidate_event_line_snapshot_cache(*event_line_ids: str | None) -> None:
    for event_line_id in event_line_ids:
        normalized_id = str(event_line_id or "").strip()
        if normalized_id:
            _event_line_snapshot_cache.pop(normalized_id, None)


def _event_line_snapshot_context(
    db: Database | None,
    event_line_id: str | None,
    fallback_name: str | None = None,
    *,
    cloud_resolver: Callable[[str, str | None], dict[str, object] | None] | None = None,
) -> dict[str, object] | None:
    normalized_id = (event_line_id or "").strip()
    if normalized_id and normalized_id in _event_line_snapshot_cache:
        return _event_line_snapshot_cache[normalized_id]
    if not normalized_id and not (fallback_name or "").strip():
        return None

    context: dict[str, object] | None = None
    if normalized_id:
        row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (normalized_id,)) if db is not None else None
        if row is not None:
            activity_count = int(db.scalar("SELECT COUNT(1) FROM event_line_activities WHERE event_line_id = ?", (normalized_id,)) or 0) if db is not None else 0
            context = {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "businessCategory": str(row["business_category"]) if row["business_category"] else None,
                "stage": str(row["stage"]) if row["stage"] else None,
                "summary": str(row["summary"]) if row["summary"] else None,
                "intent": str(row["intent"]) if row["intent"] else None,
                "currentBlocker": str(row["current_blocker"]) if row["current_blocker"] else None,
                "recentDecision": str(row["recent_decision"]) if row["recent_decision"] else None,
                "nextStep": str(row["next_step"]) if row["next_step"] else None,
                "evidenceCount": max(int(row["evidence_count"] or 0), activity_count),
                "primaryClientId": str(row["primary_client_id"]) if row["primary_client_id"] else None,
                "primaryClientName": str(row["primary_client_name"]) if row["primary_client_name"] else None,
            }
        elif cloud_resolver is not None:
            context = cloud_resolver(normalized_id, fallback_name)
    if context is None and (fallback_name or "").strip():
        context = {
            "id": normalized_id or None,
            "name": fallback_name.strip(),
        }
    if normalized_id:
        _event_line_snapshot_cache[normalized_id] = context
    return context


def _client_workspace_relative_path(path_value: str | None) -> Path | None:
    normalized_path = str(path_value or "").strip()
    if not normalized_path:
        return None
    try:
        path = Path(normalized_path)
        parts = list(path.parts)
        workspace_index = parts.index("client_workspace")
        if len(parts) <= workspace_index + 2:
            return None
        return Path(*parts[workspace_index + 2 :])
    except ValueError:
        return None


def _resolve_client_folder_ref_by_path(db: Database, client_id: str, path_value: str | None) -> tuple[str | None, str]:
    relative_path = _client_workspace_relative_path(path_value)
    folder_label = relative_path.parts[0] if relative_path and relative_path.parts else "项目与业务"
    folder_row = db.fetchone(
        "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
        (client_id, folder_label),
    )
    return (str(folder_row["id"]) if folder_row and folder_row["id"] else None, folder_label)


def _rehome_client_workspace_path(
    data_dir: Path,
    target_client_id: str,
    current_path: str | None,
    *,
    moved_paths: dict[str, str],
    fallback_label: str = "项目与业务",
) -> str | None:
    normalized_path = str(current_path or "").strip()
    if not normalized_path:
        return None
    if normalized_path in moved_paths:
        return moved_paths[normalized_path]

    ensure_client_workspace(data_dir, target_client_id)
    client_root = data_dir / "client_workspace" / target_client_id
    relative_path = _client_workspace_relative_path(normalized_path)
    if relative_path and relative_path.parts:
        target_path = client_root / relative_path
    else:
        fallback_root = ensure_client_workspace(data_dir, target_client_id).get(fallback_label) or client_root / fallback_label
        target_path = fallback_root / safe_filename(Path(normalized_path).name or "task-attachment")

    source_path = Path(normalized_path)
    final_target = target_path
    final_target.parent.mkdir(parents=True, exist_ok=True)
    if source_path.exists():
        try:
            if source_path.resolve() != target_path.resolve():
                if target_path.exists():
                    stem = safe_filename(target_path.stem or "task-attachment")
                    final_target = target_path.with_name(f"{stem}__{uuid4().hex[:6]}{target_path.suffix.lower()}")
                shutil.move(str(source_path), str(final_target))
        except FileNotFoundError:
            final_target = target_path
    moved_paths[normalized_path] = str(final_target)
    return str(final_target)


def _sync_task_attachment_scope(
    db: Database,
    data_dir: Path,
    build_task_attachment_fn: Callable[[object], TaskAttachmentRecord],
    build_attachment_event_line_activity_fn: Callable[[TaskAttachmentRecord], EventLineActivityRecord],
    ensure_standard_client_folders_fn: Callable[[str], None],
    task_id: str,
    client_id: str | None,
    event_line_id: str | None,
    *,
    cloud: bool,
) -> None:
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return
    normalized_event_line_id = str(event_line_id or "").strip() or None
    table_name = "task_attachments_cloud" if cloud else "task_attachments"
    attachment_rows = db.fetchall(
        f"""
        SELECT
            a.*,
            d.excerpt AS document_excerpt
        FROM {table_name} a
        LEFT JOIN documents d ON d.id = a.document_id
        WHERE a.task_id = ?
        ORDER BY a.created_at DESC
        """,
        (task_id,),
    )
    if not attachment_rows:
        return

    ensure_standard_client_folders_fn(normalized_client_id)
    moved_paths: dict[str, str] = {}
    affected_client_ids: set[str] = {normalized_client_id}
    affected_event_line_ids: set[str] = {normalized_event_line_id} if normalized_event_line_id else set()

    for row in attachment_rows:
        attachment = build_task_attachment_fn(row)
        affected_client_ids.add(attachment.clientId)
        if attachment.eventLineId:
            affected_event_line_ids.add(attachment.eventLineId)

        updated_attachment_path = _rehome_client_workspace_path(
            data_dir,
            normalized_client_id,
            attachment.path,
            moved_paths=moved_paths,
        ) or attachment.path
        db.execute(
            f"UPDATE {table_name} SET client_id = ?, event_line_id = ?, path = ? WHERE id = ?",
            (normalized_client_id, normalized_event_line_id, updated_attachment_path, attachment.id),
        )

        folder_id, folder_label = _resolve_client_folder_ref_by_path(db, normalized_client_id, updated_attachment_path)
        if attachment.documentId:
            document_row = db.fetchone("SELECT * FROM documents WHERE id = ?", (attachment.documentId,))
            if document_row:
                updated_document_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(document_row["path"]),
                    moved_paths=moved_paths,
                ) or str(document_row["path"])
                updated_original_source_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(document_row["original_source_path"]) if document_row["original_source_path"] else None,
                    moved_paths=moved_paths,
                )
                db.execute(
                    """
                    UPDATE documents
                    SET client_id = ?, folder_id = ?, path = ?, original_source_path = ?
                    WHERE id = ?
                    """,
                    (
                        normalized_client_id,
                        folder_id,
                        updated_document_path,
                        updated_original_source_path,
                        attachment.documentId,
                    ),
                )
                db.execute(
                    "UPDATE evidence_refs SET client_id = ?, path = ? WHERE document_id = ?",
                    (normalized_client_id, updated_document_path, attachment.documentId),
                )

            knowledge_row = db.fetchone(
                "SELECT * FROM knowledge_documents WHERE document_id = ?",
                (attachment.documentId,),
            )
            if knowledge_row:
                updated_original_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(knowledge_row["original_path"]),
                    moved_paths=moved_paths,
                ) or str(knowledge_row["original_path"])
                updated_import_source_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(knowledge_row["import_source_path"]) if knowledge_row["import_source_path"] else None,
                    moved_paths=moved_paths,
                )
                updated_current_human_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(knowledge_row["current_human_path"]) if knowledge_row["current_human_path"] else None,
                    moved_paths=moved_paths,
                )
                _, human_folder_category = _resolve_client_folder_ref_by_path(db, normalized_client_id, updated_current_human_path)
                db.execute(
                    """
                    UPDATE knowledge_documents
                    SET client_id = ?, original_path = ?, import_source_path = ?, current_human_path = ?, human_folder_category = ?
                    WHERE document_id = ?
                    """,
                    (
                        normalized_client_id,
                        updated_original_path,
                        updated_import_source_path,
                        updated_current_human_path,
                        human_folder_category,
                        attachment.documentId,
                    ),
                )

            v2_row = db.fetchone("SELECT * FROM v2_documents WHERE document_id = ?", (attachment.documentId,))
            if v2_row:
                updated_v2_original_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(v2_row["original_path"]),
                    moved_paths=moved_paths,
                ) or str(v2_row["original_path"])
                updated_managed_path = _rehome_client_workspace_path(
                    data_dir,
                    normalized_client_id,
                    str(v2_row["managed_path"]),
                    moved_paths=moved_paths,
                ) or str(v2_row["managed_path"])
                db.execute(
                    """
                    UPDATE v2_documents
                    SET client_id = ?, original_path = ?, managed_path = ?
                    WHERE document_id = ?
                    """,
                    (
                        normalized_client_id,
                        updated_v2_original_path,
                        updated_managed_path,
                        attachment.documentId,
                    ),
                )

        db.execute(
            "DELETE FROM event_line_activities WHERE source_type = 'attachment' AND source_id = ?",
            (attachment.id,),
        )
        updated_attachment = TaskAttachmentRecord(
            id=attachment.id,
            taskId=attachment.taskId,
            clientId=normalized_client_id,
            eventLineId=normalized_event_line_id,
            documentId=attachment.documentId,
            title=attachment.title,
            path=updated_attachment_path,
            kind=attachment.kind,
            source=attachment.source,
            sizeBytes=attachment.sizeBytes,
            createdAt=attachment.createdAt,
        )
        if normalized_event_line_id:
            activity = build_attachment_event_line_activity_fn(updated_attachment)
            db.execute(
                """
                INSERT INTO event_line_activities(
                    id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("ela"),
                    activity.eventLineId,
                    activity.sourceType,
                    activity.sourceId,
                    activity.happenedAt,
                    activity.actorId,
                    activity.actorName,
                    activity.title,
                    activity.summary,
                    to_json(activity.metadata),
                    int(activity.isKey),
                    activity.happenedAt,
                ),
            )

        attachment_source_id = f"{task_id}:{attachment.title}"
        db.execute(
            """
            DELETE FROM memory_facts
            WHERE source_type = 'task_attachment'
              AND source_id = ?
              AND scope_type = 'client'
              AND scope_id <> ?
            """,
            (attachment_source_id, normalized_client_id),
        )
        if normalized_event_line_id:
            db.execute(
                """
                DELETE FROM memory_facts
                WHERE source_type = 'task_attachment'
                  AND source_id = ?
                  AND scope_type = 'event_line'
                  AND scope_id <> ?
                """,
                (attachment_source_id, normalized_event_line_id),
            )
        else:
            db.execute(
                """
                DELETE FROM memory_facts
                WHERE source_type = 'task_attachment'
                  AND source_id = ?
                  AND scope_type = 'event_line'
                """,
                (attachment_source_id,),
            )
        record_task_attachment_writeback(
            db,
            task_id=task_id,
            client_id=normalized_client_id,
            event_line_id=normalized_event_line_id,
            attachment_title=attachment.title,
            attachment_path=updated_attachment_path,
        )

    for affected_client_id in sorted(client_id for client_id in affected_client_ids if client_id):
        refresh_client_folder_counts(db, affected_client_id)
        refresh_organization_notebook_snapshot(db, affected_client_id)
    for affected_event_line_id in sorted(event_line_id for event_line_id in affected_event_line_ids if event_line_id):
        refresh_event_line_memory_snapshot(db, affected_event_line_id)
    _invalidate_event_line_snapshot_cache(*affected_event_line_ids)


def _sync_event_line_client_scope_records(
    db: Database,
    *,
    event_line_id: str,
    client_id: str | None,
    client_name: str | None,
    updated_at: str,
) -> None:
    normalized_event_line_id = str(event_line_id or "").strip()
    normalized_client_id = str(client_id or "").strip()
    if not normalized_event_line_id or not normalized_client_id:
        return

    normalized_client_name = str(client_name or "").strip() or None

    db.execute(
        "UPDATE handbook_entries SET client_id = ? WHERE event_line_id = ?",
        (normalized_client_id, normalized_event_line_id),
    )
    db.execute(
        """
        UPDATE learning_recommendations
        SET client_id = ?, client_name = ?, updated_at = ?
        WHERE event_line_id = ?
        """,
        (normalized_client_id, normalized_client_name, updated_at, normalized_event_line_id),
    )
    db.execute(
        """
        UPDATE evidence_cards
        SET client_id = ?, updated_at = ?
        WHERE event_line_id = ?
           OR (scope_type = 'event_line' AND scope_id = ?)
        """,
        (normalized_client_id, updated_at, normalized_event_line_id, normalized_event_line_id),
    )
    for table_name in (
        "analysis_jobs",
        "theme_clusters",
        "conflict_groups",
        "open_questions",
        "sync_memory_records",
    ):
        db.execute(
            f"UPDATE {table_name} SET client_id = ?, updated_at = ? WHERE scope_type = 'event_line' AND scope_id = ?",
            (normalized_client_id, updated_at, normalized_event_line_id),
        )
    db.execute(
        """
        UPDATE context_packs
        SET client_id = ?, updated_at = ?
        WHERE target_type = 'event_line' AND target_id = ?
        """,
        (normalized_client_id, updated_at, normalized_event_line_id),
    )
    db.execute(
        """
        UPDATE judgment_versions
        SET client_id = ?, updated_at = ?
        WHERE target_type = 'event_line' AND target_id = ?
        """,
        (normalized_client_id, updated_at, normalized_event_line_id),
    )

    analysis_job_ids = [
        str(row["id"])
        for row in db.fetchall(
            "SELECT id FROM analysis_jobs WHERE scope_type = 'event_line' AND scope_id = ?",
            (normalized_event_line_id,),
        )
        if row["id"]
    ]
    if analysis_job_ids:
        db.execute(
            f"UPDATE runtime_run_logs SET client_id = ? WHERE job_id IN ({_sql_placeholders(analysis_job_ids)})",
            (normalized_client_id, *analysis_job_ids),
        )

    context_pack_ids = [
        str(row["id"])
        for row in db.fetchall(
            "SELECT id FROM context_packs WHERE target_type = 'event_line' AND target_id = ?",
            (normalized_event_line_id,),
        )
        if row["id"]
    ]
    if context_pack_ids:
        db.execute(
            f"UPDATE dna_deltas SET client_id = ?, updated_at = ? WHERE context_pack_id IN ({_sql_placeholders(context_pack_ids)})",
            (normalized_client_id, updated_at, *context_pack_ids),
        )
        db.execute(
            f"UPDATE approval_records SET client_id = ? WHERE object_type = 'context_pack' AND object_id IN ({_sql_placeholders(context_pack_ids)})",
            (normalized_client_id, *context_pack_ids),
        )

    judgment_ids = [
        str(row["id"])
        for row in db.fetchall(
            "SELECT id FROM judgment_versions WHERE target_type = 'event_line' AND target_id = ?",
            (normalized_event_line_id,),
        )
        if row["id"]
    ]
    if judgment_ids:
        db.execute(
            f"UPDATE approval_records SET client_id = ? WHERE object_type = 'judgment_version' AND object_id IN ({_sql_placeholders(judgment_ids)})",
            (normalized_client_id, *judgment_ids),
        )


def _first_nonempty_text(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _infer_action_os_business_category(
    *,
    title: str = "",
    desc: str = "",
    source_type: str | None = None,
    event_line_name: str | None = None,
    project_module_name: str | None = None,
    project_flow_name: str | None = None,
) -> str:
    normalized = " ".join(
        part.strip()
        for part in [
            title,
            desc,
            event_line_name or "",
            project_module_name or "",
            project_flow_name or "",
            source_type or "",
        ]
        if part and part.strip()
    )
    if not normalized:
        return "专项推进"
    if _contains_any_keyword(normalized, ("模板", "标准", "手册", "知识库", "沉淀", "资料库", "归档", "官网设计", "系统设计")):
        return "产品化沉淀"
    if _contains_any_keyword(normalized, ("审批", "复核", "确认", "对齐", "同步", "协同", "会签", "回收")):
        return "组织协同"
    if _contains_any_keyword(normalized, ("流程", "机制", "规则", "自动汇总", "制度", "治理")):
        return "管理机制"
    if _contains_any_keyword(normalized, ("合作", "拜访", "约见", "介绍", "方案", "报价", "基金会", "客户", "赋能")):
        return "业务扩展"
    if _contains_any_keyword(normalized, ("交付", "上线", "实施", "演示", "需求", "开发", "系统", "网站", "官网")):
        return "项目推进"
    if _contains_any_keyword(normalized, ("伙伴", "联盟", "开源", "外部", "生态")):
        return "外部合作"
    return "专项推进"


def _resolve_task_action_os_fields(
    *,
    title: str,
    desc: str,
    source_type: str | None,
    business_category: str | None,
    current_blocker: str | None,
    next_action: str | None,
    recent_decision: str | None,
    evidence_count: int | None,
    project_context: TaskProjectContextRecord | None = None,
    event_line_context: dict[str, object] | WeeklyReviewEventLineContextRecord | None = None,
    attachment_count: int = 0,
) -> tuple[str | None, str | None, str | None, str | None, int]:
    event_line_name = None
    event_line_business_category = None
    event_line_current_blocker = None
    event_line_recent_decision = None
    event_line_next_step = None
    event_line_evidence_count = 0

    if isinstance(event_line_context, dict):
        event_line_name = _first_nonempty_text(event_line_context.get("name"))
        event_line_business_category = _first_nonempty_text(event_line_context.get("businessCategory"))
        event_line_current_blocker = _first_nonempty_text(event_line_context.get("currentBlocker"))
        event_line_recent_decision = _first_nonempty_text(event_line_context.get("recentDecision"))
        event_line_next_step = _first_nonempty_text(event_line_context.get("nextStep"))
        event_line_evidence_count = int(event_line_context.get("evidenceCount") or 0)
    elif event_line_context is not None:
        event_line_name = _first_nonempty_text(event_line_context.name)
        event_line_business_category = _first_nonempty_text(event_line_context.businessCategory)
        event_line_current_blocker = _first_nonempty_text(event_line_context.currentBlocker)
        event_line_recent_decision = _first_nonempty_text(event_line_context.recentDecision)
        event_line_next_step = _first_nonempty_text(event_line_context.nextStep)
        event_line_evidence_count = int(event_line_context.evidenceCount or 0)

    resolved_business_category = _first_nonempty_text(
        business_category,
        event_line_business_category,
        _infer_action_os_business_category(
            title=title,
            desc=desc,
            source_type=source_type,
            event_line_name=event_line_name,
            project_module_name=project_context.projectModuleName if project_context else None,
            project_flow_name=project_context.projectFlowName if project_context else None,
        ),
    )
    resolved_current_blocker = _first_nonempty_text(
        current_blocker,
        event_line_current_blocker,
        project_context.currentBlocker if project_context else None,
    )
    resolved_next_action = _first_nonempty_text(
        next_action,
        event_line_next_step,
        project_context.nextAction if project_context else None,
    )
    resolved_recent_decision = _first_nonempty_text(
        recent_decision,
        event_line_recent_decision,
        project_context.recentProgress if project_context else None,
    )
    resolved_evidence_count = max(
        int(evidence_count or 0),
        int(attachment_count or 0),
        event_line_evidence_count,
    )
    return (
        resolved_business_category,
        resolved_current_blocker,
        resolved_next_action,
        resolved_recent_decision,
        resolved_evidence_count,
    )


def _task_snapshot_from_task(task: TaskRecord, db: Database | None = None) -> dict[str, object]:
    return {
        "title": task.title,
        "status": task.status,
        "dueDate": task.dueDate,
        "createdAt": task.createdAt,
        "ownerId": task.ownerId,
        "ownerName": task.ownerName,
        "clientId": task.clientId,
        "clientName": task.clientName,
        "eventLineId": task.eventLineId,
        "eventLineName": task.eventLineName,
        "tags": [tag.model_dump() for tag in task.tags],
        "listName": task.listName,
        "listColor": task.listColor,
        "orgContext": task.orgContext.model_dump() if task.orgContext else None,
        "projectContext": task.projectContext.model_dump() if task.projectContext else None,
        "eventLineContext": _event_line_snapshot_context(db, task.eventLineId, task.eventLineName),
    }


def empty_review_structured_note() -> WeeklyReviewTaskStructuredNoteRecord:
    return WeeklyReviewTaskStructuredNoteRecord()


def _derive_reflection_text_from_legacy_structured(parsed: dict[str, object]) -> str:
    candidates = [
        str(parsed.get("reflection") or "").strip(),
        str(parsed.get("successExperience") or "").strip(),
        str(parsed.get("supportNeeded") or "").strip(),
        str(parsed.get("failureInsight") or "").strip(),
        str(parsed.get("blockerReason") or "").strip(),
        str(parsed.get("progress") or "").strip(),
        str(parsed.get("nextAction") or "").strip(),
        str(parsed.get("successReason") or "").strip(),
    ]
    return next((item for item in candidates if item), "")


def coerce_review_structured_note(value: object) -> WeeklyReviewTaskStructuredNoteRecord:
    parsed = value
    if isinstance(value, str):
        parsed = from_json(value, {})
    if isinstance(parsed, WeeklyReviewTaskStructuredNoteRecord):
        return parsed
    if isinstance(parsed, dict):
        return WeeklyReviewTaskStructuredNoteRecord(
            reflection=_derive_reflection_text_from_legacy_structured(parsed),
            lightweightTag=str(parsed.get("lightweightTag") or "").strip(),  # type: ignore[arg-type]
            planCommitment=str(parsed.get("planCommitment") or "").strip(),
            progress=str(parsed.get("progress") or "").strip(),
            completionStatus=str(parsed.get("completionStatus") or "in_progress").strip(),  # type: ignore[arg-type]
            departmentPlanId=str(parsed.get("departmentPlanId")).strip() if parsed.get("departmentPlanId") else None,
            departmentPlanAlignment=str(parsed.get("departmentPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            organizationPlanId=str(parsed.get("organizationPlanId")).strip() if parsed.get("organizationPlanId") else None,
            organizationPlanAlignment=str(parsed.get("organizationPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            successReason=str(parsed.get("successReason") or "").strip(),
            successExperience=str(parsed.get("successExperience") or "").strip(),
            blockerReason=str(parsed.get("blockerReason") or "").strip(),
            failureInsight=str(parsed.get("failureInsight") or "").strip(),
            supportNeeded=str(parsed.get("supportNeeded") or "").strip(),
            nextAction=str(parsed.get("nextAction") or "").strip(),
        )
    return empty_review_structured_note()


def compose_review_note(structured_note: WeeklyReviewTaskStructuredNoteRecord, fallback_note: str = "") -> str:
    reflection = structured_note.reflection.strip()
    if reflection:
        if structured_note.completionStatus in {"done_on_time", "done_late"}:
            return f"任务完成心得：{reflection}"
        if structured_note.lightweightTag:
            return f"需要支持 / 思考：{reflection}（当前卡点：{structured_note.lightweightTag}）"
        return f"需要支持 / 思考：{reflection}"
    if structured_note.lightweightTag and structured_note.completionStatus not in {"done_on_time", "done_late"}:
        return f"需要支持 / 思考：{structured_note.lightweightTag}"
    is_done = structured_note.completionStatus in {"done_on_time", "done_late"}
    simple_text_candidates = (
        [
            structured_note.successExperience.strip(),
            structured_note.successReason.strip(),
            structured_note.progress.strip(),
            structured_note.nextAction.strip(),
        ]
        if is_done
        else [
            structured_note.supportNeeded.strip(),
            structured_note.failureInsight.strip(),
            structured_note.blockerReason.strip(),
            structured_note.progress.strip(),
            structured_note.nextAction.strip(),
        ]
    )
    simple_text = next((item for item in simple_text_candidates if item), "")
    if simple_text:
        prefix = "任务完成心得：" if is_done else "需要支持 / 思考："
        return f"{prefix}{simple_text}"
    return fallback_note.strip()


def _review_entry_from_task(
    *,
    task: TaskRecord,
    week_label: str,
    content_domain: str,
    review_id: str | None = None,
    note: str = "",
    structured_note: WeeklyReviewTaskStructuredNoteRecord | None = None,
    reviewed_at: str | None = None,
    snapshot: dict[str, object] | None = None,
    db: Database | None = None,
) -> WeeklyReviewTaskEntryRecord:
    payload = snapshot or _task_snapshot_from_task(task, db)
    normalized_structured_note = structured_note or empty_review_structured_note()
    return WeeklyReviewTaskEntryRecord(
        id=f"draft_{task.id}" if not review_id and not reviewed_at else f"review_{task.id}_{week_label}",
        reviewId=review_id,
        taskId=task.id,
        weekLabel=week_label,
        contentDomain=content_domain,  # type: ignore[arg-type]
        note=note,
        structuredNote=normalized_structured_note,
        reviewedAt=reviewed_at,
        taskSnapshot=payload,  # type: ignore[arg-type]
    )


def _sql_placeholders(values: tuple[str, ...] | list[str]) -> str:
    return ",".join("?" for _ in values)


def demo_data_loaded(db: Database) -> bool:
    if db.get_setting("demo_data_loaded", "0") != "1":
        return False
    placeholders = _sql_placeholders(DEMO_CLIENT_IDS)
    return bool(db.scalar(f"SELECT COUNT(1) AS count FROM clients WHERE id IN ({placeholders})", DEMO_CLIENT_IDS))


def build_demo_data_response(db: Database) -> DemoDataResponse:
    client_placeholders = _sql_placeholders(DEMO_CLIENT_IDS)
    task_placeholders = _sql_placeholders(DEMO_TASK_IDS)
    radar_placeholders = _sql_placeholders(DEMO_RADAR_IDS)
    handbook_placeholders = _sql_placeholders(DEMO_HANDBOOK_IDS)
    return DemoDataResponse(
        loaded=demo_data_loaded(db),
        clients=int(db.scalar(f"SELECT COUNT(1) AS count FROM clients WHERE id IN ({client_placeholders})", DEMO_CLIENT_IDS)),
        documents=int(db.scalar(f"SELECT COUNT(1) AS count FROM documents WHERE client_id IN ({client_placeholders})", DEMO_CLIENT_IDS)),
        tasks=int(db.scalar(f"SELECT COUNT(1) AS count FROM tasks WHERE id IN ({task_placeholders})", DEMO_TASK_IDS)),
        topics=int(db.scalar(f"SELECT COUNT(1) AS count FROM topic_radars WHERE id IN ({radar_placeholders})", DEMO_RADAR_IDS)),
        handbookEntries=int(db.scalar(f"SELECT COUNT(1) AS count FROM handbook_entries WHERE id IN ({handbook_placeholders})", DEMO_HANDBOOK_IDS)),
    )


def clear_demo_dataset(state: AppState) -> DemoDataResponse:
    meeting_rows = state.db.fetchall(
        f"SELECT id FROM meetings WHERE client_id IN ({_sql_placeholders(DEMO_CLIENT_IDS)})",
        DEMO_CLIENT_IDS,
    )
    meeting_ids = tuple(str(row["id"]) for row in meeting_rows)
    source_ids = tuple([*DEMO_CLIENT_IDS, *DEMO_CANDIDATE_IDS, *meeting_ids])

    state.db.execute(
        f"DELETE FROM tasks WHERE id IN ({_sql_placeholders(DEMO_TASK_IDS)})",
        DEMO_TASK_IDS,
    )
    if source_ids:
        state.db.execute(
            f"DELETE FROM tasks WHERE source_id IN ({_sql_placeholders(source_ids)})",
            source_ids,
        )
    state.db.execute(
        f"DELETE FROM topic_candidates WHERE id IN ({_sql_placeholders(DEMO_CANDIDATE_IDS)})",
        DEMO_CANDIDATE_IDS,
    )
    state.db.execute(
        f"DELETE FROM topic_radars WHERE id IN ({_sql_placeholders(DEMO_RADAR_IDS)})",
        DEMO_RADAR_IDS,
    )
    state.db.execute(
        f"DELETE FROM handbook_entries WHERE id IN ({_sql_placeholders(DEMO_HANDBOOK_IDS)})",
        DEMO_HANDBOOK_IDS,
    )
    state.db.execute(
        f"DELETE FROM chat_messages WHERE id IN ({_sql_placeholders(DEMO_CHAT_MESSAGE_IDS)})",
        DEMO_CHAT_MESSAGE_IDS,
    )
    state.db.execute(
        f"DELETE FROM chat_threads WHERE id IN ({_sql_placeholders(DEMO_THREAD_IDS)})",
        DEMO_THREAD_IDS,
    )
    state.db.execute(
        f"DELETE FROM goal_records WHERE id IN ({_sql_placeholders(DEMO_GOAL_IDS)})",
        DEMO_GOAL_IDS,
    )
    state.db.execute(
        f"DELETE FROM dna_terms WHERE id IN ({_sql_placeholders(DEMO_DNA_IDS)})",
        DEMO_DNA_IDS,
    )
    state.db.execute(
        f"DELETE FROM documents WHERE id IN ({_sql_placeholders(DEMO_DOCUMENT_IDS)})",
        DEMO_DOCUMENT_IDS,
    )
    state.db.execute(
        f"DELETE FROM clients WHERE id IN ({_sql_placeholders(DEMO_CLIENT_IDS)})",
        DEMO_CLIENT_IDS,
    )
    state.db.set_setting("demo_data_loaded", "0")
    return build_demo_data_response(state.db)


def load_demo_dataset(state: AppState) -> DemoDataResponse:
    clear_demo_dataset(state)
    timestamp = now_iso()
    clients = [
        ("client_cffc", "为爱黔行", "黔行公益", "公益教育", "非营利项目", "聚焦山区儿童教育与志愿者体系建设。", "战略陪伴中", "#5B7BFE"),
        ("client_star", "星辰科技", "星辰", "SaaS", "商业化 KA", "营销 SaaS 服务商，正在梳理增长打法。", "方案梳理", "#10B981"),
    ]
    state.db.executemany(
        "INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[7], timestamp, timestamp) for item in clients],
    )
    state.db.executemany(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        [
            ("thread_cffc", "client_cffc", "默认研判线程", timestamp, timestamp),
            ("thread_star", "client_star", "默认研判线程", timestamp, timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO goal_records(id, client_id, title, quarter, progress, owner_name, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("goal_1", "client_cffc", "提升项目传播清晰度", "2026 Q2", 62, "庆华", timestamp, timestamp),
            ("goal_2", "client_cffc", "补齐捐赠人关系素材", "2026 Q2", 40, "嘉宁", timestamp, timestamp),
            ("goal_3", "client_star", "验证销售线索质量", "2026 Q2", 55, "一朔", timestamp, timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO dna_terms(id, client_id, category, canonical_name, aliases_json, description, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("dna_1", "client_cffc", "组织习惯", "田野优先", to_json(["先下场", "先到一线"]), "所有策略判断优先结合一线反馈。", timestamp, timestamp),
            ("dna_2", "client_star", "增长原则", "线索先验", to_json(["先验证线索"]), "任何市场动作都要先验证线索质量。", timestamp, timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at) VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("doc_1", "client_cffc", "项目启动纪要.md", "/mock/client_cffc/项目启动纪要.md", "md", "file", "记录了项目目标、时间表与关键风险。", to_json(["会议", "启动"]), timestamp),
            ("doc_2", "client_cffc", "捐赠人访谈摘要.txt", "/mock/client_cffc/捐赠人访谈摘要.txt", "txt", "file", "汇总了主要捐赠人的关切、信任点与反馈。", to_json(["访谈"]), timestamp),
            ("doc_3", "client_star", "增长诊断报告.pdf", "/mock/client_star/增长诊断报告.pdf", "pdf", "file", "聚焦线索质量、转化链路和销售节奏。", to_json(["诊断"]), timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("task_seed_1", "准备周五跨部门复盘会", "梳理客户推进中的异常转化问题。", "inbox", "high", "list-0", "庆华", "周五", "manual", "client_cffc", to_json(["会议"]), timestamp, timestamp),
            ("task_seed_2", "梳理客户反馈的 10 个核心痛点", "提炼成客户工作台的重点议题。", "doing", "normal", "list-1", "一朔", "今天", "manual", "client_star", to_json(["待跟进"]), timestamp, timestamp),
        ],
    )
    state.db.execute(
        "INSERT INTO task_notes(id, task_id, note, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
        (new_id("tn"), "task_seed_2", "用户反馈集中在试用转化与产品定位不清。", timestamp, timestamp),
    )
    state.db.executemany(
        "INSERT INTO topic_radars(id, title, prompt, time_range, created_at) VALUES(?, ?, ?, ?, ?)",
        [
            ("radar_ai", "大模型应用", "关注公益与咨询行业的大模型落地案例。", "3_days", timestamp),
            ("radar_fund", "筹资趋势", "跟踪基金会筹资、品牌传播与捐赠人运营的最新打法。", "7_days", timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO topic_candidates(id, radar_id, title, summary, source, status, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("cand_1", "radar_ai", "公益组织开始搭建内部 AI 助理", "多个案例开始从内容检索走向流程型工作台。", "行业观察", "candidate", timestamp, timestamp),
            ("cand_2", "radar_fund", "捐赠人分层运营成为主流", "筹资团队开始按关系深浅重新定义触达节奏。", "调研纪要", "tracking", timestamp, timestamp),
        ],
    )
    state.db.executemany(
        "INSERT INTO handbook_entries(id, title, summary, tags_json, source_type, client_id, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        [
            ("hb_1", "会议不要只产纪要", "所有会议结论必须落到负责人与时间点，否则无法闭环。", to_json(["协作规则", "会议"]), "meeting", "client_cffc", timestamp),
        ],
    )
    state.db.execute(
        "INSERT INTO chat_messages(id, thread_id, role, content, structured_data_json, model_route, evidence_json, status, created_at) VALUES(?, ?, 'assistant', ?, ?, ?, ?, 'success', ?)",
        (
            "msg_seed_1",
            "thread_cffc",
            "已为你载入为爱黔行的内部上下文。",
            to_json(
                {
                    "content": "已围绕当前客户整理出一版初始判断。",
                    "judgment": "现阶段关键不在新增素材，而在把现有资料写成推进动作。",
                    "analysis": "1. 项目目标已清楚。2. 捐赠人反馈有基础。3. 缺的是稳定的任务闭环。",
                    "actions": "先从会议发布和任务收件箱打通。",
                    "timeline": "建议本周内先跑通一次完整闭环。",
                }
            ),
            "AI · mock",
            to_json(
                [
                    {
                        "id": "seed_ev",
                        "title": "项目启动纪要.md",
                        "excerpt": "记录了项目目标、时间表与关键风险。",
                        "sourceType": "md",
                        "documentId": "doc_1",
                        "path": "/mock/client_cffc/项目启动纪要.md",
                    }
                ]
            ),
            timestamp,
        ),
    )
    state.db.set_setting("demo_data_loaded", "1")
    return build_demo_data_response(state.db)


def create_pre_migration_backup(data_dir: Path, db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path)
        schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        tag_columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(task_tags)").fetchall()
        }
        needs_migration = schema_version < BACKEND_SCHEMA_VERSION or "operator_id" not in tag_columns
        if not needs_migration:
            return None
    except Exception:
        # 无法安全判定时，保守地先备份。
        pass
    finally:
        if conn is not None:
            conn.close()
    backup_dir = data_dir / "backups" / "migrations"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"app-pre-migrate-{stamp}.db"
    shutil.copy2(db_path, backup_path)
    for suffix in ("-wal", "-shm"):
        shadow = db_path.with_name(f"{db_path.name}{suffix}")
        if shadow.exists():
            shutil.copy2(shadow, backup_dir / f"{backup_path.name}{suffix}")
    return backup_path


def rollback_database_from_backup(db_path: Path, backup_path: Path | None) -> None:
    if not backup_path or not backup_path.exists():
        return
    for suffix in ("", "-wal", "-shm"):
        target = db_path if not suffix else db_path.with_name(f"{db_path.name}{suffix}")
        if target.exists():
            target.unlink()
    shutil.copy2(backup_path, db_path)
    backup_dir = backup_path.parent
    for suffix in ("-wal", "-shm"):
        shadow_backup = backup_dir / f"{backup_path.name}{suffix}"
        if shadow_backup.exists():
            shutil.copy2(shadow_backup, db_path.with_name(f"{db_path.name}{suffix}"))


def init_database_with_migration_guard(data_dir: Path) -> tuple[Database, Path | None]:
    db_path = data_dir / "app.db"
    backup_path = create_pre_migration_backup(data_dir, db_path)
    try:
        return Database(db_path), backup_path
    except Exception:
        rollback_database_from_backup(db_path, backup_path)
        raise


def create_app(data_dir: Path | None = None) -> FastAPI:
    resolved_data_dir = data_dir or Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR") or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
    )
    resolved_data_dir.mkdir(parents=True, exist_ok=True)
    try:
        db, migration_backup_path = init_database_with_migration_guard(resolved_data_dir)
    except Exception as error:
        raise RuntimeError(f"数据库迁移失败，已回滚并阻断启动：{error}") from error
    def build_secret_store(service_name: str, account_name: str = "default"):
        try:
            store = MacOSKeychainSecretStore(service_name=service_name, account_name=account_name)
            store.get_api_key()
            return store
        except Exception:
            return MemorySecretStore()

    qwen_store = build_secret_store("com.yiyu.self-workbench.qwen")
    doubao_store = build_secret_store("com.yiyu.self-workbench.doubao")
    feishu_secret_store = build_secret_store("com.yiyu.self-workbench.feishu")
    ai = AiService(db, {"qwen": qwen_store, "doubao": doubao_store})
    backup_dir = resolved_data_dir / "backups"
    state = AppState(
        data_dir=resolved_data_dir,
        backup_dir=backup_dir,
        db=db,
        ai=ai,
        feishu_secret_store=feishu_secret_store,
        cloud_api_url=os.environ.get("YIYU_CLOUD_API_URL", "http://127.0.0.1:47830").rstrip("/"),
        job_stop=Event(),
        topic_insight_executor=ThreadPoolExecutor(max_workers=3),
        chat_answer_executor=ThreadPoolExecutor(max_workers=2),
        template_fill_executor=ThreadPoolExecutor(max_workers=1),
    )
    state.system_logger = _SystemLogger(resolved_data_dir / "logs")
    state.system_logger.info("system", f"后端启动: data_dir={resolved_data_dir}")
    state.system_logger.info(
        "system",
        (
            f"后端指纹: runtime_mode={BACKEND_RUNTIME_MODE}, "
            f"build_hash={BACKEND_BUILD_HASH}, schema={state.db.get_schema_version()}/{BACKEND_SCHEMA_VERSION}, "
            f"migration_backup={str(migration_backup_path) if migration_backup_path else 'none'}"
        ),
    )

    seed_defaults(state)
    if state.db.get_setting("demo_data_loaded", "0") != "1":
        clear_demo_dataset(state)

    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.state.app_state = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_LOCAL_ORIGINS),
        allow_origin_regex=ALLOWED_LOCAL_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _local_browser_origin_guard(request: Request, call_next):
        rejection_reason = validate_local_browser_request(request.url.path, request.headers, request.method)
        if rejection_reason:
            return JSONResponse(status_code=403, content={"detail": rejection_reason})
        return await call_next(request)

    @app.middleware("http")
    async def _request_logging_middleware(request: Request, call_next):
        if not state.system_logger:
            return await call_next(request)
        path = request.url.path
        method = request.method
        # Skip logging for high-frequency/static endpoints
        if path.startswith("/api/public/") or path in ("/", "/favicon.ico"):
            return await call_next(request)
        start = time.perf_counter()
        error_msg = None
        error_tb = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_msg = str(exc)
            error_tb = traceback.format_exc()
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            user = ""
            try:
                session_user = get_cached_session_user()
                if session_user:
                    user = session_user.fullName
            except Exception:
                pass
            state.system_logger.api_request(
                method=method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                user=user,
                error_msg=error_msg,
                error_traceback=error_tb,
            )

    @app.on_event("startup")
    def _startup_worker() -> None:
        if state.job_thread and state.job_thread.is_alive():
            if state.analysis_job_thread and state.analysis_job_thread.is_alive():
                return
        recover_stale_knowledge_jobs()
        recover_stale_imports()
        recover_stale_template_fill_runs()
        recover_stale_loading_chat_messages()
        recover_stale_analysis_jobs(state.db)
        state.job_stop.clear()
        state.job_thread = Thread(target=knowledge_worker_loop, name="knowledge-worker", daemon=True)
        state.job_thread.start()
        state.analysis_job_thread = Thread(target=analysis_job_worker_loop, name="analysis-job-worker", daemon=True)
        state.analysis_job_thread.start()
        # Probe cloud backend connectivity at startup — clear circuit breaker if reachable
        if get_cloud_token():
            def _probe_cloud():
                import time as _time
                try:
                    httpx.get(f"{state.cloud_api_url}/health", timeout=3.0)
                    _cloud_circuit_breaker["last_failure"] = 0.0  # cloud OK — clear breaker
                except Exception:
                    _cloud_circuit_breaker["last_failure"] = _time.time()  # cloud down — keep breaker
            Thread(target=_probe_cloud, name="cloud-probe", daemon=True).start()

    @app.on_event("shutdown")
    def _shutdown_worker() -> None:
        state.job_stop.set()
        if state.job_thread and state.job_thread.is_alive():
            state.job_thread.join(timeout=1.5)
        if state.analysis_job_thread and state.analysis_job_thread.is_alive():
            state.analysis_job_thread.join(timeout=1.5)
        if state.topic_insight_executor:
            state.topic_insight_executor.shutdown(wait=False, cancel_futures=False)
        if state.chat_answer_executor:
            state.chat_answer_executor.shutdown(wait=False, cancel_futures=False)
        if state.template_fill_executor:
            state.template_fill_executor.shutdown(wait=False, cancel_futures=False)

    def current_operator_row():
        operator_id = state.db.get_setting("current_operator_id", "")
        if operator_id:
            row = state.db.fetchone("SELECT * FROM operators WHERE id = ?", (operator_id,))
            if row:
                return row
        row = state.db.fetchone("SELECT * FROM operators ORDER BY created_at LIMIT 1")
        if not row:
            raise HTTPException(status_code=500, detail="No operator configured")
        state.db.set_setting("current_operator_id", str(row["id"]))
        state.db.execute("UPDATE operators SET is_current = CASE WHEN id = ? THEN 1 ELSE 0 END", (str(row["id"]),))
        return row

    def current_operator_name() -> str:
        row = current_operator_row()
        return str(row["name"]) if row and row["name"] else "系统"

    def _local_task_tag_record(row) -> TaskTagRecord:
        return TaskTagRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            color=str(row["color"] or ("#9CA3AF" if str(row["scope"]) == "self" else "#5B7BFE")),
            scope=str(row["scope"]),
            ownerUserId=str(row["owner_operator_id"]) if str(row["owner_operator_id"]) else None,
            createdBy=str(row["created_by"]) if str(row["created_by"]) else None,
            updatedAt=str(row["updated_at"] or row["created_at"] or now_iso()),
            archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
        )

    def _local_task_list_record(row) -> TaskListRecord:
        return TaskListRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            color=str(row["color"]),
            sortOrder=int(row["sort_order"] or 0),
            isDefault=bool(int(row["is_default"] or 0)),
            scope=str(row["scope"] or "org"),
            archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
        )

    def _local_default_list_id() -> str | None:
        default_row = state.db.fetchone("SELECT id FROM task_lists WHERE is_default = 1 ORDER BY sort_order ASC LIMIT 1")
        if default_row:
            return str(default_row["id"])
        first_row = state.db.fetchone("SELECT id FROM task_lists ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1")
        return str(first_row["id"]) if first_row else None

    def _default_local_task_settings() -> TaskSettingsRecord:
        return TaskSettingsRecord(
            defaultListId=_local_default_list_id(),
            defaultPriority="normal",
            defaultDueDatePreset="today",
            defaultViewMode="calendar",
            listSortMode="manual",
            showCompletedTasks=False,
            defaultReviewScope="work",
            autoAssignSelf=True,
            updatedAt=now_iso(),
        )

    def _local_task_settings_record(row) -> TaskSettingsRecord:
        defaults = _default_local_task_settings()
        return TaskSettingsRecord(
            defaultListId=str(row["default_list_id"]) if row["default_list_id"] else defaults.defaultListId,
            defaultPriority=str(row["default_priority"] or defaults.defaultPriority),  # type: ignore[arg-type]
            defaultDueDatePreset=str(row["default_due_date_preset"] or defaults.defaultDueDatePreset),  # type: ignore[arg-type]
            defaultViewMode=str(row["default_view_mode"] or defaults.defaultViewMode),  # type: ignore[arg-type]
            listSortMode=str(row["list_sort_mode"] or defaults.listSortMode),  # type: ignore[arg-type]
            showCompletedTasks=bool(int(row["show_completed_tasks"] or 0)),
            defaultReviewScope=str(row["default_review_scope"] or defaults.defaultReviewScope),  # type: ignore[arg-type]
            autoAssignSelf=bool(int(row["auto_assign_self"] if row["auto_assign_self"] is not None else 1)),
            updatedAt=str(row["updated_at"] or defaults.updatedAt),
        )

    def _get_local_task_settings(operator_id: str | None = None) -> TaskSettingsRecord:
        resolved_operator_id = operator_id or str(current_operator_row()["id"])
        row = state.db.fetchone("SELECT * FROM task_settings WHERE operator_id = ?", (resolved_operator_id,))
        if row:
            return _local_task_settings_record(row)
        defaults = _default_local_task_settings()
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_settings(
                operator_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_operator_id,
                defaults.defaultListId,
                defaults.defaultPriority,
                defaults.defaultDueDatePreset,
                defaults.defaultViewMode,
                defaults.listSortMode,
                1 if defaults.showCompletedTasks else 0,
                defaults.defaultReviewScope,
                1 if defaults.autoAssignSelf else 0,
                defaults.updatedAt,
            ),
        )
        return defaults

    def _visible_local_task_tag_rows(db: Database, operator_id: str) -> list:
        return db.fetchall(
            """
            SELECT *
            FROM task_tags
            WHERE scope = 'org' OR owner_operator_id = ?
            ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                     CASE scope WHEN 'org' THEN 0 ELSE 1 END,
                     name COLLATE NOCASE ASC
            """,
            (operator_id,),
        )

    def _visible_local_task_tags(db: Database, operator_id: str) -> list[TaskTagRecord]:
        return [_local_task_tag_record(row) for row in _visible_local_task_tag_rows(db, operator_id)]

    def _local_tag_rows_by_ids(db: Database, tag_ids: list[str]) -> list:
        if not tag_ids:
            return []
        rows = db.fetchall(
            f"SELECT * FROM task_tags WHERE id IN ({_sql_placeholders(tag_ids)})",
            tuple(tag_ids),
        )
        by_id = {str(row["id"]): row for row in rows}
        return [by_id[tag_id] for tag_id in tag_ids if tag_id in by_id]

    def _ensure_local_tag(
        db: Database,
        operator_id: str,
        name: str,
        scope: str = "org",
        color: str | None = None,
        created_by: str | None = None,
    ) -> TaskTagRecord:
        trimmed = name.strip()
        if not trimmed:
            raise HTTPException(status_code=400, detail="Tag name is required")
        owner_operator_id = operator_id if scope == "self" else ""
        resolved_color = color or ("#9CA3AF" if scope == "self" else "#5B7BFE")
        resolved_creator = created_by or str(current_operator_row()["name"])
        existing = db.fetchone(
            "SELECT * FROM task_tags WHERE name = ? AND scope = ? AND owner_operator_id = ?",
            (trimmed, scope, owner_operator_id),
        )
        timestamp = now_iso()
        if existing:
            db.execute(
                """
                UPDATE task_tags
                SET color = COALESCE(NULLIF(?, ''), color),
                    archived_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (resolved_color, timestamp, str(existing["id"])),
            )
            row = db.fetchone("SELECT * FROM task_tags WHERE id = ?", (str(existing["id"]),))
            if row:
                return _local_task_tag_record(row)
        tag_id = new_id("tag")
        db.execute(
            """
            INSERT INTO task_tags(
                id, name, color, scope, owner_operator_id, created_by, archived_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (tag_id, trimmed, resolved_color, scope, owner_operator_id, resolved_creator, timestamp, timestamp),
        )
        row = db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create task tag")
        return _local_task_tag_record(row)

    def _resolve_local_task_tags(db: Database, operator_id: str, tag_ids: list[str], legacy_names: list[str]) -> list[TaskTagRecord]:
        rows = _local_tag_rows_by_ids(db, tag_ids)
        if rows:
            return [_local_task_tag_record(row) for row in rows]
        if not legacy_names:
            return []
        return [_ensure_local_tag(db, operator_id, name, "org") for name in legacy_names if name.strip()]

    def log_activity(action: str, entity_type: str, entity_id: str, detail: dict[str, object]) -> None:
        session_user = get_cached_session_user()
        actor_name = session_user.fullName if session_user else current_operator_row()["name"]
        state.db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("log"), actor_name, action, entity_type, entity_id, to_json(detail), now_iso()),
        )
        if state.system_logger:
            state.system_logger.activity(action, entity_type, entity_id, actor_name, detail)

    def append_knowledge_job_event(job_id: str, level: str, message: str, detail: dict[str, object] | None = None) -> None:
        state.db.execute(
            """
            INSERT INTO knowledge_job_events(id, job_id, level, message, detail_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (new_id("kje"), job_id, level, message, to_json(detail or {}), now_iso()),
        )

    def enqueue_knowledge_job(client_id: str, job_type: str, payload: dict[str, object], total_items: int) -> KnowledgeJobRecord:
        job_id = new_id("kjob")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO knowledge_jobs(
                id, client_id, job_type, status, payload_json, total_items, processed_items,
                last_error, created_at, started_at, finished_at, updated_at
            )
            VALUES(?, ?, ?, 'queued', ?, ?, 0, NULL, ?, NULL, NULL, ?)
            """,
            (job_id, client_id, job_type, to_json(payload), total_items, timestamp, timestamp),
        )
        append_knowledge_job_event(job_id, "info", "知识加工任务已入队", {"jobType": job_type, "totalItems": total_items})
        return KnowledgeJobRecord(
            id=job_id,
            clientId=client_id,
            jobType=job_type,
            status="queued",
            totalItems=total_items,
            processedItems=0,
            createdAt=timestamp,
            updatedAt=timestamp,
        )

    def resolve_import_id_for_job(job_row: dict[str, object] | None) -> str | None:
        if not job_row or str(job_row.get("job_type") or "") != "ingest_import":
            return None
        payload = from_json(str(job_row.get("payload_json") or "{}"), {})
        if not isinstance(payload, dict):
            return None
        import_id = payload.get("importId")
        return str(import_id) if import_id else None

    def update_import_status(import_id: str, *, status: str, imported_count: int | None = None, skipped_count: int | None = None) -> None:
        existing = state.db.fetchone("SELECT imported_count, skipped_count FROM imports WHERE id = ?", (import_id,))
        if not existing:
            return
        next_imported = int(imported_count) if imported_count is not None else int(existing["imported_count"] or 0)
        next_skipped = int(skipped_count) if skipped_count is not None else int(existing["skipped_count"] or 0)
        state.db.execute(
            """
            UPDATE imports
            SET status = ?, imported_count = ?, skipped_count = ?
            WHERE id = ?
            """,
            (status, next_imported, next_skipped, import_id),
        )

    def recover_stale_knowledge_jobs() -> None:
        stale_rows = state.db.fetchall(
            """
            SELECT id
            FROM knowledge_jobs
            WHERE status = 'running'
            ORDER BY created_at ASC
            """
        )
        if not stale_rows:
            return
        timestamp = now_iso()
        for row in stale_rows:
            job_id = str(row["id"])
            state.db.execute(
                """
                UPDATE knowledge_jobs
                SET status = 'queued', started_at = NULL, finished_at = NULL, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                ("worker_restart_requeued", timestamp, job_id),
            )
            append_knowledge_job_event(job_id, "warning", "检测到旧的运行中任务，已在启动时重新入队")

    def recover_stale_imports() -> None:
        stale_imports = state.db.fetchall(
            """
            SELECT id, client_id, status
            FROM imports
            WHERE status IN ('queued', 'processing')
            ORDER BY created_at ASC
            """
        )
        for row in stale_imports:
            import_id = str(row["id"])
            jobs = state.db.fetchall(
                """
                SELECT *
                FROM knowledge_jobs
                WHERE client_id = ? AND job_type = 'ingest_import'
                ORDER BY created_at DESC
                """,
                (str(row["client_id"]),),
            )
            matched_job: dict[str, object] | None = None
            for job in jobs:
                if resolve_import_id_for_job(dict(job)) == import_id:
                    matched_job = dict(job)
                    break
            if matched_job is None:
                if str(row["status"]) == "processing":
                    update_import_status(import_id, status="failed")
                continue
            job_status = str(matched_job.get("status") or "")
            processed_items = int(matched_job.get("processed_items") or 0)
            if job_status == "completed":
                update_import_status(import_id, status="completed", imported_count=processed_items)
            elif job_status == "failed":
                update_import_status(import_id, status="failed", imported_count=processed_items)
            elif job_status == "running":
                update_import_status(import_id, status="processing", imported_count=processed_items)
            elif job_status == "queued":
                update_import_status(import_id, status="queued", imported_count=processed_items)

    def recover_stale_template_fill_runs() -> None:
        stale_runs = state.db.fetchall(
            """
            SELECT id
            FROM client_template_fill_runs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at ASC
            """
        )
        if not stale_runs:
            return
        timestamp = now_iso()
        for row in stale_runs:
            state.db.execute(
                """
                UPDATE client_template_fill_runs
                SET status = 'failed',
                    phase = 'failed',
                    progress = CASE
                        WHEN progress IS NULL THEN 8.0
                        WHEN progress > 96.0 THEN 96.0
                        WHEN progress < 8.0 THEN 8.0
                        ELSE progress
                    END,
                    stage_label = '模板填写已中断',
                    error_message = COALESCE(NULLIF(error_message, ''), '应用重启或后台中断，当前填写任务已停止，请重新发起。'),
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, str(row["id"])),
            )

    TEMPLATE_FILL_STALE_IDLE_SECONDS = 180

    def _parse_template_fill_timestamp(value: str | None) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def refresh_template_fill_executor(reason: str = "") -> None:
        if state.template_fill_executor is not None:
            state.template_fill_executor.shutdown(wait=False, cancel_futures=False)
        state.template_fill_executor = ThreadPoolExecutor(max_workers=1)
        if state.system_logger:
            suffix = f" reason={reason}" if reason else ""
            state.system_logger.info("template_fill", f"模板填写执行器已重建{suffix}")

    def expire_stuck_template_fill_runs(max_idle_seconds: int = TEMPLATE_FILL_STALE_IDLE_SECONDS) -> int:
        running_rows = state.db.fetchall(
            """
            SELECT id, phase, progress, current_field_label, updated_at, created_at
            FROM client_template_fill_runs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at ASC
            """
        )
        if not running_rows:
            return 0
        now_dt = datetime.now()
        expired_ids: list[str] = []
        for row in running_rows:
            updated_at = _parse_template_fill_timestamp(str(row["updated_at"] or "")) or _parse_template_fill_timestamp(str(row["created_at"] or ""))
            if updated_at is None:
                continue
            if updated_at.tzinfo is not None:
                updated_at = updated_at.astimezone().replace(tzinfo=None)
            idle_seconds = (now_dt - updated_at).total_seconds()
            if idle_seconds < max_idle_seconds:
                continue
            run_id = str(row["id"])
            update_client_template_fill_run(
                run_id,
                status="failed",
                phase="failed",
                progress=max(8.0, min(float(row["progress"] or 0.0), 96.0)),
                stage_label="模板填写超时，已自动停止",
                clear_current_field_label=True,
                error_message=(
                    f"模板填写在“{str(row['phase'] or 'running')}”阶段超过 {max_idle_seconds} 秒未推进，"
                    "已自动终止，请重新发起。"
                ),
            )
            expired_ids.append(run_id)
            if state.system_logger:
                state.system_logger.error(
                    "template_fill",
                    f"检测到僵尸模板填写任务，已自动终止: {run_id}",
                    phase=str(row["phase"] or ""),
                    current_field=str(row["current_field_label"] or ""),
                    idleSeconds=round(idle_seconds, 2),
                )
        if expired_ids:
            refresh_template_fill_executor(reason=f"expired_runs={len(expired_ids)}")
        return len(expired_ids)

    STALE_LOADING_CHAT_SECONDS = 120

    def recover_stale_loading_chat_messages() -> None:
        stale_rows = state.db.fetchall(
            """
            SELECT id, retrieval_summary_json, created_at
            FROM chat_messages
            WHERE role = 'assistant' AND status = 'loading'
            ORDER BY created_at ASC
            """
        )
        if not stale_rows:
            return
        now = datetime.now()
        for row in stale_rows:
            created_at_raw = str(row["created_at"] or "")
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = now - timedelta(minutes=10)
            age_seconds = max((now - created_at).total_seconds(), 0.0)
            if age_seconds < STALE_LOADING_CHAT_SECONDS:
                continue
            summary = from_json(str(row["retrieval_summary_json"] or "{}"), {})
            if not isinstance(summary, dict):
                summary = {}
            summary.update(
                {
                    "phase": "failed",
                    "progress": 100.0,
                    "progressFloor": 100.0,
                    "progressCeiling": 100.0,
                    "stageLabel": "回答生成失败",
                    "failureReason": "后台回答任务中断或超时，已自动收口。",
                    "lastUpdatedAt": now_iso(),
                }
            )
            state.db.execute(
                """
                UPDATE chat_messages
                SET content = ?, structured_data_json = ?, model_route = ?, llm_invoked = 0, provider_used = COALESCE(provider_used, ?),
                    answer_mode = 'system_failure', evidence_status = 'none', failure_reason = ?, timing_json = ?,
                    retrieval_summary_json = ?, evidence_json = COALESCE(evidence_json, '[]'), status = 'success', created_at = ?
                WHERE id = ? AND status = 'loading'
                """,
                (
                    "庆华暂时没能完成这次回答。",
                    to_json(
                        AiStructuredResponse(
                            content="庆华暂时没能完成这次回答。",
                            judgment="后台回答任务中断或超时，本次回答已自动收口为失败态。",
                            analysis="该消息此前一直停留在生成中，没有成功写回最终结果。系统已自动把它标记为失败，避免前端一直卡在加载状态。",
                            actions="请直接重试这个问题；如果反复出现，请检查本地后端与千问配置。",
                            timeline="修复后可立即重新生成。",
                        ).model_dump()
                    ),
                    "AI 调用失败",
                    state.ai.current_provider(),
                    "stale_loading_message_recovered",
                    to_json({"totalMs": round(age_seconds * 1000, 2), "retrievalMs": 0.0, "llmMs": 0.0}),
                    to_json(summary),
                    now_iso(),
                    str(row["id"]),
                ),
            )
            state.db.execute(
                """
                UPDATE client_analysis_runs
                SET status = 'failed',
                    phase = 'failed',
                    progress = 100.0,
                    progress_floor = 100.0,
                    progress_ceiling = 100.0,
                    stage_label = '回答生成失败',
                    long_answer_status = 'failed',
                    summary_status = 'failed',
                    failure_reason = 'stale_loading_message_recovered',
                    elapsed_ms = ?,
                    timing_json = ?,
                    updated_at = ?
                WHERE assistant_message_id = ? AND status IN ('queued', 'running')
                """,
                (
                    round(age_seconds * 1000, 2),
                    to_json({"totalMs": round(age_seconds * 1000, 2), "retrievalMs": 0.0, "llmMs": 0.0}),
                    now_iso(),
                    str(row["id"]),
                ),
            )

    def claim_next_knowledge_job() -> dict[str, object] | None:
        row = state.db.fetchone(
            """
            SELECT *
            FROM knowledge_jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """,
        )
        if not row:
            return None
        timestamp = now_iso()
        state.db.execute(
            "UPDATE knowledge_jobs SET status = 'running', started_at = ?, updated_at = ? WHERE id = ? AND status = 'queued'",
            (timestamp, timestamp, str(row["id"])),
        )
        claimed = state.db.fetchone("SELECT * FROM knowledge_jobs WHERE id = ?", (str(row["id"]),))
        if not claimed or str(claimed["status"]) != "running":
            return None
        append_knowledge_job_event(str(claimed["id"]), "info", "知识加工任务开始执行")
        return dict(claimed)

    def finish_knowledge_job(job_id: str, *, status: str, processed_items: int, last_error: str | None = None) -> None:
        timestamp = now_iso()
        existing_job = state.db.fetchone("SELECT * FROM knowledge_jobs WHERE id = ?", (job_id,))
        state.db.execute(
            """
            UPDATE knowledge_jobs
            SET status = ?, processed_items = ?, last_error = ?, finished_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, processed_items, last_error, timestamp, timestamp, job_id),
        )
        append_knowledge_job_event(
            job_id,
            "error" if status == "failed" else "info",
            "知识加工任务执行失败" if status == "failed" else "知识加工任务执行完成",
            {"processedItems": processed_items, "lastError": last_error},
        )
        import_id = resolve_import_id_for_job(dict(existing_job)) if existing_job else None
        if import_id:
            update_import_status(import_id, status="failed" if status == "failed" else "completed", imported_count=processed_items)

    def update_knowledge_job_progress(job_id: str, processed_items: int, message: str) -> None:
        state.db.execute(
            "UPDATE knowledge_jobs SET processed_items = ?, updated_at = ? WHERE id = ?",
            (processed_items, now_iso(), job_id),
        )
        append_knowledge_job_event(job_id, "info", message, {"processedItems": processed_items})


```
