# 益语软件平台源码导出（第003卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `backend/app/models.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Priority = Literal["low", "normal", "high"]
TaskStatus = Literal["inbox", "todo", "doing", "done", "rejected"]
TaskDueDatePreset = Literal["today", "none"]
TaskListSortMode = Literal["dueDate", "priority", "manual"]
TaskViewMode = Literal["inbox", "list", "calendar", "review"]
TaskReviewScope = Literal["work", "personal"]
AgentDepartmentKey = Literal["strategy_design", "tech_development", "info_data"]
TopicTaskOwnerMode = Literal["self", "empty"]
TopicCandidateStatus = Literal["candidate", "tracking", "promoted", "archived"]
TopicCandidateInsightStatus = Literal["pending", "ready", "failed"]
MeetingStage = Literal["prepared", "ingested", "extracted", "resolved", "published"]
AiProvider = Literal["mock", "qwen", "doubao"]
AccountStatus = Literal["pending", "approved", "rejected", "disabled"]
EmployeeRole = Literal["admin", "employee"]
CollaboratorInboxStatus = Literal["pending", "accepted", "returned"]
OrgRoleLevel = Literal["employee", "supervisor", "department_lead", "organization_lead"]
OrgReportingLineType = Literal["business", "administrative"]
OrgTaskEditScope = Literal["self", "manager", "department", "organization"]
OrgTaskControlLevel = Literal["normal", "leader_control", "department_control", "organization_control"]
OrgRuleActorScope = Literal["assignee", "manager", "department_lead", "organization_lead", "creator"]
OrgWorkflowTriggerType = Literal["weekly_followup", "task_created", "meeting_closed", "client_update", "manual"]
DnaSourceLevel = Literal["organization", "client"]
OrganizationDnaModuleKey = Literal["organization_intro", "business_intro", "team_intro", "market_intro"]
FeishuReceiveIdType = Literal["open_id", "user_id", "email", "chat_id"]
GrowthAbilityKey = Literal["exec", "collab", "analyze", "insight", "risk", "write"]
GrowthEvidenceType = Literal["reflection", "codification", "reuse", "improvement"]
GrowthEvidenceLevel = Literal["l1", "l2", "l3"]
GrowthConfidence = Literal["high", "medium", "low"]
LearningContentType = Literal["method_card", "practice_card", "correction_card"]
LearningRecommendationStatus = Literal["active", "accepted", "dismissed"]
GrowthContributionTag = Literal["knowledge_asset", "critical_resolution", "collaboration_enablement", "risk_alignment", "mechanism_building"]
GrowthValidationState = Literal["candidate", "observed", "validated", "institutionalized"]
BadgeState = Literal["locked", "progress", "ready", "lit", "mastered"]
MemoryScopeType = Literal["client", "person", "product", "event_line", "task"]
ClarificationStatus = Literal["pending", "answered", "dismissed"]
AnalysisScopeType = Literal["client", "event_line", "meeting", "task", "module", "flow"]
AnalysisJobType = Literal["asset_ingest", "evidence_extract", "customer_compare", "meeting_enhance", "dna_refresh", "strategy_pack"]
AnalysisJobStatus = Literal["queued", "running", "preparing", "extracting", "clustering", "comparing", "drafting", "awaiting_review", "completed", "failed", "cancelled", "rolled_back"]
AnalysisStageStatus = Literal["queued", "running", "completed", "failed", "skipped"]
AnalysisReviewState = Literal["draft", "awaiting_review", "awaiting_revision", "approved", "rejected", "superseded"]
AnalysisLane = Literal["light_extractor", "local_deep", "cloud_final"]
AnalysisOriginType = Literal["projection", "analysis", "human_override"]
AnalysisAuthorityLevel = Literal["fallback", "candidate", "approved"]
AnalysisQualityTier = Literal["legacy", "normalized", "reviewed"]
AnalysisIntentProfile = Literal["task_ai", "weekly_review", "meeting_enhance", "client_overview", "strategic_cockpit", "dna_summary"]
AnalysisStaleReason = Literal[
    "superseded_by_newer_judgment",
    "source_snapshot_changed",
    "approval_revoked",
    "scope_no_longer_primary",
    "insufficient_evidence",
    "manual_invalidation",
]
AnalysisRejectedReason = Literal[
    "authority_too_low",
    "scope_less_relevant",
    "stale",
    "superseded",
    "insufficient_evidence",
    "not_approved_for_official_use",
]
ApprovalDecision = Literal["approved", "rejected", "returned_for_revision"]
ApprovalTargetType = Literal["judgment_version", "dna_delta", "conflict_group", "proposal_record"]


class OperatorRecord(BaseModel):
    id: str
    name: str
    role: str
    team: str
    color: str
    isCurrent: bool


class AppSettingsPayload(BaseModel):
    currentOperatorId: str | None = None
    aiProvider: AiProvider | None = None
    aiModel: str | None = None
    apiKey: str | None = None
    clearApiKey: bool = False


class AppSettingsResponse(BaseModel):
    currentOperatorId: str
    aiProvider: AiProvider
    aiModel: str
    dataDir: str
    backupDir: str
    cloudApiUrl: str = "http://127.0.0.1:47830"
    lastBackupAt: str | None = None
    foldersRootLabel: str
    aiConfigured: bool
    aiCredentialSource: str
    aiFingerprint: str | None = None
    demoDataLoaded: bool = False


class HealthAiState(BaseModel):
    provider: AiProvider
    model: str
    ready: bool
    detail: str
    credentialSource: str
    fingerprint: str | None = None


class HealthResponse(BaseModel):
    backend: Literal["online"] = "online"
    appName: str
    appVersion: str
    buildVersion: str
    backendBuildHash: str
    backendSchemaVersion: int
    runtimeMode: Literal["packaged", "dev"]
    startedAt: str
    featureFlags: list[str] = Field(default_factory=list)
    dataDir: str
    stats: dict[str, int]
    ai: HealthAiState


class SettingsResponse(BaseModel):
    settings: AppSettingsResponse
    operators: list[OperatorRecord]
    health: HealthResponse


class SessionUserRecord(BaseModel):
    id: str
    organizationId: str
    email: str
    fullName: str
    primaryRole: EmployeeRole
    accountStatus: AccountStatus


class AuthStateResponse(BaseModel):
    authenticated: bool
    user: SessionUserRecord | None = None
    message: str | None = None
    sessionMode: Literal["local", "cloud"] = "cloud"


class CloudConfigResponse(BaseModel):
    mode: Literal["disabled", "official_test", "custom"] = "disabled"
    apiBaseUrl: str | None = None


class AccountOverviewResponse(BaseModel):
    sessionMode: Literal["local", "cloud"]
    cloudConnected: bool
    cloudConfig: CloudConfigResponse
    user: SessionUserRecord | None = None


class ConsultationKnowledgeRequestRecord(BaseModel):
    id: str
    answerId: str
    organizationId: str
    target: Literal["vector_memory", "document_archive"]
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    requestedByUserId: str
    requestedByName: str
    clientId: str | None = None
    clientName: str | None = None
    taskId: str | None = None
    eventLineId: str | None = None
    question: str = ""
    answer: str
    errorMessage: str | None = None
    localDocumentId: str | None = None
    localDocumentPath: str | None = None
    completedAt: str | None = None
    createdAt: str
    updatedAt: str


class ConsultationKnowledgeProcessSummaryResponse(BaseModel):
    totalPending: int = 0
    processedCount: int = 0
    completedCount: int = 0
    failedCount: int = 0
    skippedCount: int = 0
    updatedAt: str
    items: list[ConsultationKnowledgeRequestRecord] = Field(default_factory=list)


class AuthRegisterPayload(BaseModel):
    email: str
    fullName: str
    password: str
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False


class AuthLoginPayload(BaseModel):
    email: str
    password: str
    rememberMe: bool = True


class RememberedCloudAuthAccount(BaseModel):
    email: str
    fullName: str = ""
    password: str = ""
    updatedAt: str


class LocalInputMemoryCloudAuth(BaseModel):
    rememberInputs: bool = True
    lastEmail: str | None = None
    accounts: list[RememberedCloudAuthAccount] = Field(default_factory=list)


class LocalInputMemoryAiSettings(BaseModel):
    rememberApiKey: bool = False
    apiKey: str = ""


class LocalInputMemoryFeishuIntegration(BaseModel):
    rememberInputs: bool = False
    appId: str = ""
    callbackMode: str = "cloud_relay"
    customCallbackUrl: str = ""
    appSecret: str = ""


class LocalInputMemoryResponse(BaseModel):
    cloudAuth: LocalInputMemoryCloudAuth = Field(default_factory=LocalInputMemoryCloudAuth)
    aiSettings: LocalInputMemoryAiSettings = Field(default_factory=LocalInputMemoryAiSettings)
    feishuIntegration: LocalInputMemoryFeishuIntegration = Field(default_factory=LocalInputMemoryFeishuIntegration)


class SaveCloudAuthInputMemoryPayload(BaseModel):
    rememberInputs: bool = True
    email: str
    fullName: str | None = None
    password: str | None = None


class SaveAiInputMemoryPayload(BaseModel):
    rememberApiKey: bool = False
    apiKey: str | None = None


class SaveFeishuInputMemoryPayload(BaseModel):
    rememberInputs: bool = False
    appId: str | None = None
    callbackMode: str | None = None
    customCallbackUrl: str | None = None
    appSecret: str | None = None


class UpdateProfilePayload(BaseModel):
    fullName: str | None = None
    email: str | None = None


class EmployeeRecord(BaseModel):
    id: str
    email: str
    fullName: str
    primaryRole: EmployeeRole
    accountStatus: AccountStatus
    departmentId: str | None = None
    departmentName: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False
    approvedAt: str | None = None
    rejectedReason: str | None = None
    disabledAt: str | None = None
    lastLoginAt: str | None = None
    createdAt: str


class EmployeeRolePayload(BaseModel):
    role: EmployeeRole


class EmployeeDepartmentPayload(BaseModel):
    departmentId: str | None = None


class EmployeeRejectPayload(BaseModel):
    reason: str = ""


class DepartmentOptionRecord(BaseModel):
    id: str
    name: str
    color: str


class OrgProfileRecord(BaseModel):
    organizationId: str
    name: str
    annualGoal: str = ""
    annualStrategyYear: str = ""
    annualStrategy: str = ""
    quarterPlans: list["OrgQuarterPlanRecord"] = Field(default_factory=list)
    quarterlyFocus: list[str] = Field(default_factory=list)
    leaderUserId: str | None = None
    managementUserIds: list[str] = Field(default_factory=list)
    updatedAt: str


class OrgQuarterPlanRecord(BaseModel):
    id: str
    year: str = ""
    quarter: Literal["Q1", "Q2", "Q3", "Q4"] = "Q1"
    theme: str = ""
    objective: str = ""
    keyResults: list[str] = Field(default_factory=list)
    keyActions: list[str] = Field(default_factory=list)
    majorRisks: list[str] = Field(default_factory=list)
    updatedAt: str = ""


class OrgDepartmentQuarterPlanRecord(BaseModel):
    year: str = ""
    quarter: Literal["Q1", "Q2", "Q3", "Q4"] = "Q1"
    objective: str = ""
    deliverables: list[str] = Field(default_factory=list)
    successMetrics: list[str] = Field(default_factory=list)
    majorRisks: list[str] = Field(default_factory=list)
    updatedAt: str = ""


class OrgDepartmentRecord(BaseModel):
    id: str
    name: str
    color: str
    leaderUserId: str | None = None
    leaderName: str = ""
    parentDepartmentId: str | None = None
    mission: str = ""
    businessContext: str = ""
    teamContext: str = ""
    quarterPlan: OrgDepartmentQuarterPlanRecord = Field(default_factory=OrgDepartmentQuarterPlanRecord)
    quarterlyFocus: list[str] = Field(default_factory=list)
    collaborationDepartmentIds: list[str] = Field(default_factory=list)
    active: bool = True
    updatedAt: str


class OrgRoleTemplateRecord(BaseModel):
    id: str
    departmentId: str | None = None
    name: str
    level: OrgRoleLevel
    managerRoleId: str | None = None
    isManager: bool = False
    goal: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    shouldAvoid: list[str] = Field(default_factory=list)
    collaborationRoleIds: list[str] = Field(default_factory=list)
    taskEditScope: OrgTaskEditScope = "self"
    canApproveTasks: bool = False
    canReassignTasks: bool = False
    canChangeDeadline: bool = False
    sortOrder: int = 0
    active: bool = True
    updatedAt: str


class OrgEmployeeBindingRecord(BaseModel):
    userId: str
    departmentId: str | None = None
    primaryRoleId: str | None = None
    managerUserId: str | None = None
    isManager: bool = False
    projectRoleLabels: list[str] = Field(default_factory=list)
    currentFocus: str = ""
    taskEditScope: OrgTaskEditScope = "self"
    canApproveTasks: bool = False
    canReassignTasks: bool = False
    canChangeDeadline: bool = False
    updatedAt: str


class OrgReportingLineRecord(BaseModel):
    id: str
    managerUserId: str
    reportUserId: str
    lineType: OrgReportingLineType = "business"
    approvesTasks: bool = False
    canAdjustTasks: bool = False
    canChangeDeadline: bool = False
    canReassignTasks: bool = False
    isCrossDepartmentApprover: bool = False
    active: bool = True
    updatedAt: str


class OrgTaskControlRuleRecord(BaseModel):
    id: str
    name: str
    controlLevel: OrgTaskControlLevel = "normal"
    departmentId: str | None = None
    roleTemplateId: str | None = None
    contentEditableBy: OrgRuleActorScope = "assignee"
    deadlineEditableBy: OrgRuleActorScope = "manager"
    ownerEditableBy: OrgRuleActorScope = "manager"
    cancellableBy: OrgRuleActorScope = "manager"
    requireCollabConfirmation: bool = False
    defaultApproverUserId: str | None = None
    active: bool = True
    updatedAt: str


class OrgRoleProcessTemplateRecord(BaseModel):
    id: str
    roleTemplateId: str | None = None
    name: str
    triggerType: OrgWorkflowTriggerType = "manual"
    triggerCondition: str = ""
    keySteps: list[str] = Field(default_factory=list)
    collaborationStep: str = ""
    approvalStep: str = ""
    outputArtifact: str = ""
    commonBlockers: list[str] = Field(default_factory=list)
    active: bool = True
    updatedAt: str


class OrgFocusItemRecord(BaseModel):
    id: str
    periodKey: str
    title: str
    statement: str = ""
    ownerUserId: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["draft", "active", "paused", "done"] = "active"
    evidenceKeywords: list[str] = Field(default_factory=list)
    updatedAt: str


class OrgDepartmentPlanItemRecord(BaseModel):
    id: str
    focusItemId: str | None = None
    title: str
    statement: str = ""
    ownerUserId: str | None = None
    status: Literal["active", "paused", "done", "dropped"] = "active"
    expectedOutput: str = ""
    sortOrder: int = 0
    updatedAt: str


class OrgDepartmentPlanRecord(BaseModel):
    id: str
    departmentId: str | None = None
    weekLabel: str
    ownerUserId: str | None = None
    summary: str = ""
    majorRisks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "closed"] = "draft"
    items: list[OrgDepartmentPlanItemRecord] = Field(default_factory=list)
    updatedAt: str


class TaskPlanLinkRecord(BaseModel):
    taskId: str
    departmentPlanItemId: str | None = None
    focusItemId: str | None = None
    linkedBy: Literal["ai", "manager", "rule"] = "ai"
    confidence: float = 0
    updatedAt: str


class SupportRequestRecord(BaseModel):
    id: str
    taskId: str | None = None
    requesterUserId: str
    targetScope: Literal["manager", "department", "organization", "cross_department"]
    targetRefId: str | None = None
    requestType: Literal["resource", "decision", "collaboration", "workload", "clarification"]
    urgency: Literal["high", "medium", "low"] = "medium"
    summary: str
    status: Literal["open", "accepted", "resolved", "dismissed"] = "open"
    resolutionNote: str = ""
    createdAt: str
    updatedAt: str


class OrgModelProfileRecord(BaseModel):
    organization: OrgProfileRecord
    departments: list[OrgDepartmentRecord] = Field(default_factory=list)
    roles: list[OrgRoleTemplateRecord] = Field(default_factory=list)
    bindings: list[OrgEmployeeBindingRecord] = Field(default_factory=list)
    reportingLines: list[OrgReportingLineRecord] = Field(default_factory=list)
    taskControlRules: list[OrgTaskControlRuleRecord] = Field(default_factory=list)
    roleProcessTemplates: list[OrgRoleProcessTemplateRecord] = Field(default_factory=list)
    focusItems: list[OrgFocusItemRecord] = Field(default_factory=list)
    departmentPlans: list[OrgDepartmentPlanRecord] = Field(default_factory=list)
    updatedAt: str


class TaskOrgBackfillResultRecord(BaseModel):
    organizationId: str
    totalTasks: int
    linkedTasks: int
    createdLinks: int
    updatedLinks: int
    updatedAt: str


class TaskContextRefreshResultRecord(BaseModel):
    totalTasks: int
    updatedTasks: int
    unchangedTasks: int
    failedTasks: int
    clientUpdatedTasks: int
    eventLineUpdatedTasks: int
    moduleUpdatedTasks: int
    flowUpdatedTasks: int
    updatedAt: str


class TaskEventLineBootstrapResultRecord(BaseModel):
    totalTasks: int
    createdEventLines: int
    linkedTasks: int
    skippedTasks: int
    failedTasks: int
    updatedAt: str


class MemoryBackfillResultRecord(BaseModel):
    totalTasks: int
    taskFactsBackfilled: int
    totalAttachments: int
    attachmentFactsBackfilled: int
    totalReviews: int
    reviewSignalsBackfilled: int
    totalClients: int
    notebooksRefreshed: int
    totalEventLines: int
    eventLineSnapshotsRefreshed: int
    updatedAt: str


class MentionCandidateRecord(BaseModel):
    id: str
    fullName: str
    email: str
    primaryRole: EmployeeRole
    isSelf: bool = False


class DemoDataResponse(BaseModel):
    loaded: bool
    clients: int
    documents: int
    tasks: int
    topics: int
    handbookEntries: int


class ActivityLogRecord(BaseModel):
    id: str
    actorName: str
    action: str
    entityType: str
    entityId: str
    detail: dict[str, object]
    createdAt: str


class BackupResponse(BaseModel):
    backupPath: str
    createdAt: str


class LegacyScanRequest(BaseModel):
    path: str


class LegacyScanEntry(BaseModel):
    path: str
    kind: str
    importable: bool


class LegacyScanResponse(BaseModel):
    path: str
    found: list[str]
    entries: list[LegacyScanEntry]
    message: str


class ClientMutationPayload(BaseModel):
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: str
    color: str | None = None


class ClientSummary(BaseModel):
    id: str
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: str
    color: str = "#5B7BFE"
    folderCount: int
    documentCount: int
    taskCount: int
    lastActivityAt: str | None = None


class ClientFolder(BaseModel):
    id: str
    clientId: str
    label: str
    path: str
    fileCount: int
    lastScannedAt: str | None = None


class ImportRecord(BaseModel):
    id: str
    clientId: str
    sourcePath: str
    mode: Literal["folder", "file"]
    status: Literal["queued", "processing", "completed", "failed", "scanned"]
    importedCount: int
    skippedCount: int
    createdAt: str


class ImportPayload(BaseModel):
    clientId: str
    mode: Literal["folder", "file"]
    paths: list[str]
    allowLegacy: bool = False


class WorkspaceImportBackfillResponse(BaseModel):
    importId: str
    jobId: str
    sourceRoot: str
    discovered: int
    imported: int
    skipped: int


class DocumentRecord(BaseModel):
    id: str
    clientId: str
    folderId: str | None = None
    title: str
    path: str
    kind: str
    source: str
    excerpt: str
    tags: list[str]
    importedAt: str


class KnowledgeStatusRecord(BaseModel):
    totalDocuments: int
    totalChunks: int
    vectorizedDocuments: int
    dedupedDocuments: int
    reviewPendingDocuments: int
    surrogateCount: int = 0
    memoryDocCount: int = 0
    masterIndexCount: int = 0
    reclassifiedDocumentCount: int = 0
    qdrantReady: bool = False
    lastUpdatedAt: str | None = None
    pendingJobs: int = 0
    runningJobs: int = 0
    lastJobStatus: Literal["idle", "queued", "running", "completed", "failed"] = "idle"
    lastJobError: str | None = None
    lastSuccessfulRunAt: str | None = None
    embeddingMode: str = "hash_fallback"
    embeddingModel: str | None = None
    embeddingError: str | None = None


class DocumentCardRecord(BaseModel):
    id: str
    docId: str
    clientId: str
    documentId: str
    title: str
    originalPath: str
    importSourcePath: str | None = None
    currentHumanPath: str | None = None
    humanFolderCategory: str | None = None
    sourcePath: str
    logicalCategory: str | None = None
    logicalSubcategory: str | None = None
    classificationReason: str | None = None
    normalizedPath: str | None = None
    surrogateMdPath: str | None = None
    kind: str
    primaryCategory: str
    secondaryCategory: str
    shortSummary: str
    summary: str
    retrievalSummary: str = ""
    documentRole: str = "资料"
    queryHints: list[str] = Field(default_factory=list)
    distinctFindings: list[str] = Field(default_factory=list)
    coreQuestions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    dateRange: str | None = None
    classificationConfidence: float
    needsReview: bool
    deepRead: bool
    lastHitQuestion: str | None = None
    dedupStatus: str
    vectorStatus: str
    version: int
    chunkCount: int = 0
    createdAt: str
    updatedAt: str


class GoalRecord(BaseModel):
    id: str
    clientId: str
    title: str
    quarter: str
    progress: int
    ownerName: str


class GoalPayload(BaseModel):
    title: str
    quarter: str
    progress: int = Field(default=0, ge=0, le=100)
    ownerName: str


class DnaTerm(BaseModel):
    id: str
    clientId: str
    category: str
    canonicalName: str
    aliases: list[str]
    description: str
    sourceLevel: DnaSourceLevel = "client"


class DnaTermPayload(BaseModel):
    category: str
    canonicalName: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""


class EvidenceItem(BaseModel):
    id: str
    title: str
    excerpt: str
    sourceType: str
    documentId: str | None = None
    path: str | None = None
    score: float | None = None
    coverage: float | None = None
    sectionLabel: str | None = None
    retrievalStage: Literal["master_index", "surrogate", "raw_chunk"] | None = None
    isFallback: bool = False
    matchedTerms: list[str] = Field(default_factory=list)


class AiStructuredResponse(BaseModel):
    content: str
    judgment: str
    analysis: str
    actions: str
    timeline: str


ChatRetrievalDecisionReason = Literal[
    "state_first_default",
    "document_drilldown_requested",
    "search_cache_requested",
    "intro_query_needs_evidence",
    "identity_query_needs_evidence",
    "project_intro_needs_evidence",
    "meeting_summary_needs_evidence",
    "next_actions_needs_evidence",
    "evidence_question_needs_evidence",
    "official_registry_requested",
    "status_progress_needs_hybrid_evidence",
    "default_hybrid_evidence",
    "state_pool_insufficient",
    "state_pool_empty",
]

JudgmentQueryMode = Literal["registry_only", "hybrid", "evidence_based_synthesis"]

WorkspaceAnswerIntent = Literal[
    "intro_profile",
    "project_intro",
    "meeting_summary",
    "next_actions",
    "official_judgment_registry",
    "evidence_question",
    "status_progress",
    "general",
]

EvidenceSupportMode = Literal[
    "none",
    "linked_state_evidence",
    "evidence_cards",
    "raw_doc_drilldown",
    "generic_retrieval_fallback",
]


class EvidenceSupportItemRecord(BaseModel):
    title: str
    summary: str
    sourceType: Literal["judgment", "dna", "meeting", "task", "open_question", "conflict", "evidence_card", "raw_doc", "context_pack"]
    sourceId: str | None = None
    sourceRef: str | None = None
    authority: Literal["approved", "candidate", "radar", "raw"] = "radar"
    timeAnchor: str | None = None
    confidence: float | None = None
    linkedFindingId: str | None = None


class StateAnswerSectionsRecord(BaseModel):
    official: list[str] = Field(default_factory=list)
    candidate: list[str] = Field(default_factory=list)
    draftFindings: list[str] = Field(default_factory=list)
    evidenceSupport: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class StateSourceSummaryRecord(BaseModel):
    judgments: int = 0
    meetings: int = 0
    tasks: int = 0
    openQuestions: int = 0
    conflicts: int = 0
    documents: int = 0


class ChatMessageRecord(BaseModel):
    id: str
    threadId: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str
    status: Literal["success", "loading"]
    modelRoute: str | None = None
    llmInvoked: bool = False
    providerUsed: str | None = None
    answerMode: Literal["grounded_answer", "grounded_fallback", "low_confidence_answer", "general_answer", "system_failure"] | None = None
    evidenceStatus: Literal["sufficient", "partial", "none"] | None = None
    failureReason: str | None = None
    fallbackReason: str | None = None
    fallbackPresentationMode: Literal["state_cards_only", "compact_user_answer", "full_answer"] | None = None
    stateConfidence: Literal["low", "medium", "high"] | None = None
    stateSources: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    answerIntent: WorkspaceAnswerIntent | None = None
    retrievalDecisionReason: ChatRetrievalDecisionReason | None = None
    judgmentQueryMode: JudgmentQueryMode | None = None
    evidenceSupportMode: EvidenceSupportMode | None = None
    stateAnswerSections: StateAnswerSectionsRecord | None = None
    stateSourceSummary: StateSourceSummaryRecord | None = None
    timing: dict[str, float] = Field(default_factory=dict)
    retrievalSummary: dict[str, object] = Field(default_factory=dict)
    structuredData: AiStructuredResponse | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ChatThread(BaseModel):
    id: str
    clientId: str
    title: str
    createdAt: str
    updatedAt: str


class ChatRequest(BaseModel):
    threadId: str | None = None
    prompt: str
    searchId: str | None = None


class ChatStartResponse(BaseModel):
    threadId: str
    userMessage: ChatMessageRecord
    assistantMessage: ChatMessageRecord
    analysisRun: "ClientAnalysisRunRecord"


class ChatThreadDetailResponse(BaseModel):
    thread: ChatThread
    messages: list[ChatMessageRecord] = Field(default_factory=list)


class AgendaItem(BaseModel):
    id: str
    title: str
    description: str


class DecisionItem(BaseModel):
    id: str
    summary: str


class RiskItem(BaseModel):
    id: str
    summary: str
    severity: Priority


class AmbiguityItem(BaseModel):
    id: str
    rawText: str
    candidates: list[str]
    status: Literal["pending", "resolved"]


class OrganizationNotebookSnapshot(BaseModel):
    id: str
    clientId: str
    organizationIntro: str = ""
    collaborationRelationship: str = ""
    currentStage: str = ""
    businessModules: list[str] = Field(default_factory=list)
    keyPeople: list[str] = Field(default_factory=list)
    keyProducts: list[str] = Field(default_factory=list)
    currentChallenges: list[str] = Field(default_factory=list)
    collaborationGoals: list[str] = Field(default_factory=list)
    recentFacts: list[str] = Field(default_factory=list)
    informationGaps: list[str] = Field(default_factory=list)
    updatedAt: str
    confidence: float = 0.0


class EventLineMemorySnapshot(BaseModel):
    id: str
    eventLineId: str
    lineName: str
    currentStage: str = ""
    currentWork: str = ""
    currentBlocker: str = ""
    recentDecision: str = ""
    nextStep: str = ""
    evidenceRefs: list[str] = Field(default_factory=list)
    clarificationNeeds: list[str] = Field(default_factory=list)
    analysisSignals: list[str] = Field(default_factory=list)
    predictionReadiness: float = 0.0
    updatedAt: str
    confidence: float = 0.0


class MemoryFact(BaseModel):
    id: str
    scopeType: MemoryScopeType
    scopeId: str
    factKey: str
    factValue: str
    sourceType: str
    sourceId: str
    confidence: float = 0.0
    freshness: float = 0.0
    evidenceRefs: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ClarificationRecord(BaseModel):
    id: str
    scopeType: MemoryScopeType
    scopeId: str
    slotKey: str
    question: str
    status: ClarificationStatus = "pending"
    answerText: str | None = None
    writeScope: list[str] = Field(default_factory=list)
    resolvedFactIds: list[str] = Field(default_factory=list)
    reusable: bool = True
    createdAt: str
    answeredAt: str | None = None
    updatedAt: str


class MemoryStatus(BaseModel):
    clientId: str
    notebookCompleteness: float = 0.0
    notebookConfidence: float = 0.0
    eventLineCoverage: float = 0.0
    totalEventLines: int = 0
    coveredEventLines: int = 0
    pendingClarifications: int = 0
    lowEvidenceJudgments: int = 0
    updatedAt: str


class BackgroundReadiness(BaseModel):
    score: float = 0.0
    level: Literal["low", "medium", "high"] = "low"
    missingSlots: list[str] = Field(default_factory=list)
    backgroundSources: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    id: str
    title: str
    desc: str
    status: TaskStatus
    creatorId: str | None = None
    creatorName: str | None = None
    priority: Priority
    listId: str
    listName: str
    listColor: str
    ddl: str
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectModuleId: str | None = None
    projectModuleName: str | None = None
    projectFlowId: str | None = None
    projectFlowName: str | None = None
    ownerId: str | None = None
    ownerName: str
    sourceType: str
    sourceId: str | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int = 0
    tags: list["TaskTagRecord"] = Field(default_factory=list)
    note: str | None = None
    attachments: list["TaskAttachmentRecord"] = Field(default_factory=list)
    collaborators: list["TaskCollaboratorRecord"] = Field(default_factory=list)
    collaborationSummary: dict[str, int] = Field(default_factory=dict)
    viewerInboxStatus: CollaboratorInboxStatus | None = None
    orgContext: "TaskOrgContextRecord | None" = None
    projectContext: "TaskProjectContextRecord | None" = None
    memoryHints: list[str] = Field(default_factory=list)
    backgroundReadiness: BackgroundReadiness | None = None
    linkedFactsPreview: list[MemoryFact] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class TaskAttachmentRecord(BaseModel):
    id: str
    taskId: str
    clientId: str
    eventLineId: str | None = None
    documentId: str | None = None
    title: str
    summary: str | None = None
    path: str
    kind: str
    source: str
    sizeBytes: int = 0
    createdAt: str


class TaskOrgContextRecord(BaseModel):
    departmentId: str | None = None
    roleTemplateId: str | None = None
    controlRuleId: str | None = None
    controlLevel: OrgTaskControlLevel | None = None
    organizationFocusKey: str | None = None
    departmentFocusKey: str | None = None
    focusItemId: str | None = None
    departmentPlanItemId: str | None = None
    isCrossDepartment: bool = False
    approvalState: str | None = None
    blockedAtStep: str | None = None
    needsReview: bool = False


class TaskProjectContextRecord(BaseModel):
    clientId: str
    clientName: str
    stage: str | None = None
    projectModuleId: str | None = None
    projectModuleName: str | None = None
    projectModuleSummary: str | None = None
    projectFlowId: str | None = None
    projectFlowName: str | None = None
    projectFlowSummary: str | None = None
    backgroundSummary: str = ""
    goalSummary: str = ""
    riskSummary: str = ""
    currentFocus: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentProgress: str | None = None
    infoCompleteness: Literal["low", "medium", "high"] = "low"
    sourceEvidence: list[str] = Field(default_factory=list)


class ProjectModuleRecord(BaseModel):
    id: str
    clientId: str
    name: str
    alias: str | None = None
    goal: str = ""
    description: str = ""
    ownerName: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    templateTasksJson: str | None = None
    createdAt: str
    updatedAt: str


class ProjectFlowRecord(BaseModel):
    id: str
    clientId: str
    moduleId: str
    moduleName: str | None = None
    name: str
    description: str = ""
    scenario: str = ""
    triggerCondition: str = ""
    steps: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    riskPoints: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ProjectStructureResponse(BaseModel):
    modules: list[ProjectModuleRecord] = Field(default_factory=list)
    flows: list[ProjectFlowRecord] = Field(default_factory=list)


class ProjectModuleDetailRecord(ProjectModuleRecord):
    relatedTaskIds: list[str] = Field(default_factory=list)
    relatedTaskTitles: list[str] = Field(default_factory=list)
    flowIds: list[str] = Field(default_factory=list)
    flowNames: list[str] = Field(default_factory=list)
    contextSummary: str = ""


class ProjectFlowDetailRecord(ProjectFlowRecord):
    relatedTaskIds: list[str] = Field(default_factory=list)
    relatedTaskTitles: list[str] = Field(default_factory=list)
    contextSummary: str = ""


class MeetingSummary(BaseModel):
    id: str
    clientId: str
    title: str
    stage: MeetingStage
    scheduledAt: str | None = None
    updatedAt: str


class MeetingDetail(MeetingSummary):
    transcriptText: str
    notes: str
    agendaItems: list[AgendaItem] = Field(default_factory=list)
    decisions: list[DecisionItem] = Field(default_factory=list)
    actionItems: list[TaskRecord] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    ambiguities: list[AmbiguityItem] = Field(default_factory=list)


class MeetingCreatePayload(BaseModel):
    title: str
    scheduledAt: str | None = None


class MeetingIngestPayload(BaseModel):
    transcriptText: str = ""
    notes: str = ""


class MeetingPipelineResponse(BaseModel):
    meeting: MeetingDetail
    message: str


class FeishuMeetingLaunchPayload(BaseModel):
    title: str
    scheduledAt: str | None = None
    sourceTaskId: str | None = None


class FeishuMeetingLaunchResponse(BaseModel):
    meeting: MeetingDetail
    deliveryStatus: Literal["sent", "skipped", "failed"]
    deliveryMessage: str
    commandHint: str
    noticeText: str
    deliveryMode: Literal["bound_user", "configured_receiver", "none"]
    deliveryTarget: str | None = None


class TaskListRecord(BaseModel):
    id: str
    name: str
    color: str
    sortOrder: int = 0
    isDefault: bool = False
    scope: Literal["org", "personal"] = "org"
    archivedAt: str | None = None


class TaskTagRecord(BaseModel):
    id: str
    name: str
    color: str
    scope: Literal["org", "self"] = "org"
    ownerUserId: str | None = None
    createdBy: str | None = None
    updatedAt: str
    archivedAt: str | None = None


class TaskSettingsRecord(BaseModel):
    defaultListId: str | None = None
    defaultPriority: Priority = "normal"
    defaultDueDatePreset: TaskDueDatePreset = "today"
    defaultViewMode: TaskViewMode = "list"
    listSortMode: TaskListSortMode = "manual"
    showCompletedTasks: bool = False
    defaultReviewScope: TaskReviewScope = "work"
    autoAssignSelf: bool = True
    updatedAt: str


class ReviewDepartmentMemberRecord(BaseModel):
    id: str = ""
    fullName: str
    email: str | None = None


class ReviewDepartmentConfigRecord(BaseModel):
    id: str
    name: str
    color: str = "#5B7BFE"
    monthlyDna: str = ""
    weeklyFocus: str = ""
    leaders: list[ReviewDepartmentMemberRecord] = Field(default_factory=list)
    members: list[ReviewDepartmentMemberRecord] = Field(default_factory=list)


class ReviewGovernanceSettingsRecord(BaseModel):
    departments: list[ReviewDepartmentConfigRecord] = Field(default_factory=list)
    updatedAt: str


class ReviewGovernanceSettingsPayload(BaseModel):
    departments: list[ReviewDepartmentConfigRecord] = Field(default_factory=list)


class TaskTagLibraryResponse(BaseModel):
    tags: list[TaskTagRecord]


class TaskListLibraryResponse(BaseModel):
    lists: list[TaskListRecord]


class TaskBoardResponse(BaseModel):
    tasks: list[TaskRecord]
    lists: list[TaskListRecord]
    tags: list[TaskTagRecord]
    commonTags: list[str] = Field(default_factory=list)


class TaskCollaboratorRecord(BaseModel):
    userId: str
    fullName: str
    email: str
    orderIndex: int
    isOwner: bool
    inboxStatus: CollaboratorInboxStatus
    returnReason: str | None = None
    handledAt: str | None = None


class TaskActivityRecord(BaseModel):
    id: str
    taskId: str
    actorId: str
    actorName: str
    eventType: str
    payload: dict[str, object]
    createdAt: str


class TaskPayload(BaseModel):
    title: str
    desc: str = ""
    priority: Priority = "normal"
    listId: str
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    ddl: str = ""
    ownerId: str | None = None
    ownerName: str = ""
    collaboratorIds: list[str] = Field(default_factory=list)
    tagIds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sourceType: str = "manual"
    sourceId: str | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int | None = None


class TaskUpdatePayload(BaseModel):
    title: str | None = None
    desc: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    listId: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int | None = None
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] | None = None
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    ddl: str | None = None
    ownerId: str | None = None
    ownerName: str | None = None
    collaboratorIds: list[str] | None = None
    tagIds: list[str] | None = None
    tags: list[str] | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int | None = None


class TaskNotePayload(BaseModel):
    note: str


class TaskCompletionReviewPayload(BaseModel):
    reviewNote: str = Field(min_length=1)


class TaskPlanLinkUpsertPayload(BaseModel):
    departmentPlanItemId: str | None = None
    focusItemId: str | None = None
    linkedBy: Literal["ai", "manager", "rule"] = "manager"
    confidence: float = 1.0


class TaskRejectPayload(BaseModel):
    reason: str


class SupportRequestCreatePayload(BaseModel):
    taskId: str | None = None
    eventLineId: str | None = None
    targetScope: Literal["manager", "department", "organization", "cross_department"]
    targetRefId: str | None = None
    requestType: Literal["resource", "decision", "collaboration", "workload", "clarification"]
    urgency: Literal["high", "medium", "low"] = "medium"
    summary: str = Field(min_length=1)


class SupportRequestResolvePayload(BaseModel):
    resolutionNote: str = ""
    status: Literal["accepted", "resolved", "dismissed"] = "resolved"


class TaskTagMutationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    color: str | None = None
    scope: Literal["org", "self"] = "org"
    archived: bool | None = None


class TaskListMutationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    color: str = Field(min_length=4, max_length=16)
    isDefault: bool | None = None
    scope: Literal["org", "personal"] | None = None
    archived: bool | None = None
    sortOrder: int | None = None


class TaskSettingsPayload(BaseModel):
    defaultListId: str | None = None
    defaultPriority: Priority | None = None
    defaultDueDatePreset: TaskDueDatePreset | None = None
    defaultViewMode: TaskViewMode | None = None
    listSortMode: TaskListSortMode | None = None
    showCompletedTasks: bool | None = None
    defaultReviewScope: TaskReviewScope | None = None
    autoAssignSelf: bool | None = None


class DnaReadinessQuestionRecord(BaseModel):
    question: str
    answered: bool = False
    evidence: str | None = None


class OrganizationDnaModuleRecord(BaseModel):
    moduleKey: OrganizationDnaModuleKey
    title: str
    markdownContent: str = ""
    normalizedText: str = ""
    summary: str = ""
    fileName: str | None = None
    contentHash: str | None = None
    updatedAt: str | None = None
    updatedBy: str | None = None
    hasDocument: bool = False
    readinessStatus: Literal["ready", "missing"] = "missing"
    readinessAnsweredCount: int = 0
    readinessQuestionCount: int = 0
    readinessSource: Literal["client_dna", "manual_document", "auto_enqueued", "none"] = "none"
    readinessSummary: str = ""
    readinessQuestions: list[DnaReadinessQuestionRecord] = Field(default_factory=list)


class OrganizationDnaResponse(BaseModel):
    modules: list[OrganizationDnaModuleRecord]


class OrganizationDnaUploadPayload(BaseModel):
    filePath: str | None = None
    markdownContent: str | None = None
    fileName: str | None = None


class ProjectModulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    alias: str | None = None
    goal: str | None = None
    description: str | None = None
    ownerName: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    templateTasksJson: str | None = None


class ProjectFlowPayload(BaseModel):
    moduleId: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    scenario: str | None = None
    triggerCondition: str | None = None
    steps: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    riskPoints: list[str] = Field(default_factory=list)


class ClientDnaModuleRecord(BaseModel):
    clientId: str
    moduleKey: OrganizationDnaModuleKey
    title: str
    markdownContent: str = ""
    normalizedText: str = ""
    summary: str = ""
    fileName: str | None = None
    contentHash: str | None = None
    sourceKind: Literal["manual", "generated"] = "manual"
    missingInfo: list[str] = Field(default_factory=list)
    updatedAt: str | None = None
    updatedBy: str | None = None
    hasDocument: bool = False


class ClientDnaGeneratePayload(BaseModel):
    refreshGenerated: bool = False


class ClientDnaModulesResponse(BaseModel):
    modules: list[ClientDnaModuleRecord]


class ClientWorkspaceSettingsRecord(BaseModel):
    useOrgDnaInChat: bool = False
    useOrgDnaInKnowledgeQa: bool = False
    meetingPublishDefaultListId: str | None = None
    meetingPublishDefaultPriority: Priority = "normal"
    defaultGoalQuarter: str = ""
    defaultMeetingTitlePrefix: str = "客户会议"
    clientDnaModeLabel: str = "DNA"
    updatedAt: str


class ClientWorkspaceSettingsPayload(BaseModel):
    useOrgDnaInChat: bool | None = None
    useOrgDnaInKnowledgeQa: bool | None = None
    meetingPublishDefaultListId: str | None = None
    meetingPublishDefaultPriority: Priority | None = None
    defaultGoalQuarter: str | None = None
    defaultMeetingTitlePrefix: str | None = None
    clientDnaModeLabel: str | None = None


class TopicsSettingsRecord(BaseModel):
    chineseOnly: bool = True
    requireInsightBeforeActions: bool = True
    defaultTaskOwnerMode: TopicTaskOwnerMode = "self"
    defaultTimeRange: str = "3_days"
    defaultSourceStrategy: str = "google_bing_news"
    useOrgDnaForInsight: bool = True
    useOrgDnaForTaskPlan: bool = True
    updatedAt: str


class TopicsSettingsPayload(BaseModel):
    chineseOnly: bool | None = None
    requireInsightBeforeActions: bool | None = None
    defaultTaskOwnerMode: TopicTaskOwnerMode | None = None
    defaultTimeRange: str | None = None
    defaultSourceStrategy: str | None = None
    useOrgDnaForInsight: bool | None = None
    useOrgDnaForTaskPlan: bool | None = None


class DiagnosisProfileRecord(BaseModel):
    id: str
    groupKey: Literal["platform_fundraising", "monthly_donor", "key_person"]
    deepDnaId: str | None = None
    label: str
    fileName: str
    filePath: str
    markdownContent: str
    summary: str
    corePreferences: list[str] = Field(default_factory=list)
    riskTriggers: list[str] = Field(default_factory=list)
    tonePreference: str | None = None
    updatedAt: str


class OrganizationRiskDnaDocument(BaseModel):
    fileName: str
    filePath: str
    markdownContent: str
    summary: str
    coreRisks: list[str] = Field(default_factory=list)
    sensitiveScenarios: list[str] = Field(default_factory=list)
    tonePreference: str | None = None
    updatedAt: str


class FundraisingKnowledgeDocument(BaseModel):
    id: str
    title: str
    fileName: str
    filePath: str
    markdownContent: str
    summary: str
    scenes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    riskSignals: list[str] = Field(default_factory=list)
    updatedAt: str


class DeepDnaSourceRecord(BaseModel):
    id: str
    kind: Literal["manual", "import", "web"]
    title: str
    excerpt: str
    sourceUrl: str | None = None
    fileName: str | None = None
    filePath: str | None = None
    createdAt: str


class DeepDnaRecord(BaseModel):
    id: str
    groupKey: Literal["platform_fundraising", "monthly_donor", "key_person"]
    label: str
    status: Literal["draft", "published"] = "published"
    sourceKind: Literal["manual", "import", "web"] = "manual"
    identitySummary: str = ""
    corePreferences: list[str] = Field(default_factory=list)
    supportTriggers: list[str] = Field(default_factory=list)
    redFlags: list[str] = Field(default_factory=list)
    evidencePreferences: list[str] = Field(default_factory=list)
    voiceStyle: list[str] = Field(default_factory=list)
    commonQuestions: list[str] = Field(default_factory=list)
    sources: list[DeepDnaSourceRecord] = Field(default_factory=list)
    confidenceScore: int = 60
    confidenceLevel: Literal["low", "medium", "high"] = "medium"
    authorizationStatus: Literal["public", "authorized_internal", "restricted"] = "public"
    rawContent: str = ""
    searchQuery: str | None = None
    createdAt: str
    updatedAt: str


class DeepDnaDraft(BaseModel):
    id: str
    groupKey: Literal["platform_fundraising", "monthly_donor", "key_person"]
    label: str
    searchQuery: str
    draftRecord: DeepDnaRecord
    previewSources: list[DeepDnaSourceRecord] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CoachCaseRecord(BaseModel):
    id: str
    title: str
    summary: str
    whyEffective: str
    takeaways: list[str] = Field(default_factory=list)
    keyExcerpt: str
    scenes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    issueTypes: list[str] = Field(default_factory=list)
    sourceType: Literal["system", "organization"] = "organization"
    sourceLabel: str = ""
    createdAt: str
    updatedAt: str


class CoachReminderRule(BaseModel):
    id: str
    title: str
    modeIds: list[str] = Field(default_factory=list)
    knowledgeKey: str
    issuePattern: str
    message: str
    createdAt: str
    updatedAt: str


class OrgWritingNorm(BaseModel):
    id: str
    title: str
    description: str = ""
    instruction: str
    modeIds: list[str] = Field(default_factory=list)
    triggerKeywords: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CoachCardRecord(BaseModel):
    id: str
    issueKey: str
    insightTitle: str
    issueWhat: str
    whyImportant: str
    knowledgePointTitle: str
    knowledgePointBody: str
    caseIds: list[str] = Field(default_factory=list)
    selfRewriteHint: str
    learningAction: str
    referenceDraft: str | None = None


class CoachPayload(BaseModel):
    cards: list[CoachCardRecord] = Field(default_factory=list)
    triggeredReminders: list[CoachReminderRule] = Field(default_factory=list)
    appliedNorms: list[OrgWritingNorm] = Field(default_factory=list)


class RunComparison(BaseModel):
    currentRunId: str
    previousRunId: str | None = None
    resultChanges: list[str] = Field(default_factory=list)
    learningChanges: list[str] = Field(default_factory=list)
    resolvedIssues: list[str] = Field(default_factory=list)
    newIssues: list[str] = Field(default_factory=list)
    repeatedIssues: list[str] = Field(default_factory=list)


class AnalysisWorkbenchSettingsRecord(BaseModel):
    enabledTemplateIds: list[str] = Field(default_factory=list)
    defaultTemplateId: str | None = None
    defaultTitlePrefix: str = "系统分析"
    useOrgDna: bool = True
    allowEmployeeTemplateEditing: bool = True
    diagnosisProfiles: list[DiagnosisProfileRecord] = Field(default_factory=list)
    organizationRiskDna: OrganizationRiskDnaDocument | None = None
    fundraisingKnowledgeLibrary: list[FundraisingKnowledgeDocument] = Field(default_factory=list)
    deepDnaLibrary: list[DeepDnaRecord] = Field(default_factory=list)
    coachCaseLibrary: list[CoachCaseRecord] = Field(default_factory=list)
    coachReminderRules: list[CoachReminderRule] = Field(default_factory=list)
    orgWritingNorms: list[OrgWritingNorm] = Field(default_factory=list)
    updatedAt: str


class AnalysisWorkbenchSettingsPayload(BaseModel):
    enabledTemplateIds: list[str] | None = None
    defaultTemplateId: str | None = None
    defaultTitlePrefix: str | None = None
    useOrgDna: bool | None = None
    allowEmployeeTemplateEditing: bool | None = None
    diagnosisProfiles: list[DiagnosisProfileRecord] | None = None
    organizationRiskDna: OrganizationRiskDnaDocument | None = None
    fundraisingKnowledgeLibrary: list[FundraisingKnowledgeDocument] | None = None
    deepDnaLibrary: list[DeepDnaRecord] | None = None
    coachCaseLibrary: list[CoachCaseRecord] | None = None
    coachReminderRules: list[CoachReminderRule] | None = None
    orgWritingNorms: list[OrgWritingNorm] | None = None


class HandbookSettingsRecord(BaseModel):
    defaultTags: list[str] = Field(default_factory=list)
    defaultCategory: str = "组织沉淀"
    allowTaskSource: bool = True
    allowAnalysisSource: bool = True
    visibilityBoundary: str = "organization_and_personal"
    updatedAt: str


class HandbookSettingsPayload(BaseModel):
    defaultTags: list[str] | None = None
    defaultCategory: str | None = None
    allowTaskSource: bool | None = None
    allowAnalysisSource: bool | None = None
    visibilityBoundary: str | None = None


class SystemAdminSettingsRecord(BaseModel):
    allowBusinessSettingsForEmployees: bool = True
    allowOrgDnaForEmployees: bool = True
    protectEmployeeAdmin: bool = True
    protectAiAndCloud: bool = True
    protectCloudSecurity: bool = True
    brandLogoDataUrl: str | None = None
    updatedAt: str


class SystemAdminSettingsPayload(BaseModel):
    allowBusinessSettingsForEmployees: bool | None = None
    allowOrgDnaForEmployees: bool | None = None
    protectEmployeeAdmin: bool | None = None
    protectAiAndCloud: bool | None = None
    protectCloudSecurity: bool | None = None
    brandLogoDataUrl: str | None = None


class AnalysisWorkerCounterSnapshotRecord(BaseModel):
    claimCounts: dict[str, int] = Field(default_factory=dict)
    lockContention: dict[str, int] = Field(default_factory=dict)
    backfillThrottle: dict[str, int] = Field(default_factory=dict)


class MainChainCanaryObservationRecord(BaseModel):
    recordedAt: str
    timeRange: str = ""
    clientCount: int = 0
    enqueuedJobs: int = 0
    completedJobs: int = 0
    failedJobs: int = 0
    newObjectHitRateBefore: float = 0.0
    newObjectHitRateAfter: float = 0.0
    fallbackRateBefore: float = 0.0
    fallbackRateAfter: float = 0.0
    resolverMismatchRateBefore: float = 0.0
    resolverMismatchRateAfter: float = 0.0
    approvalBacklog: int = 0
    approvalLagHoursMedian: float = 0.0
    claimCounts: dict[str, int] = Field(default_factory=dict)
    lockContention: dict[str, int] = Field(default_factory=dict)
    backfillThrottle: dict[str, int] = Field(default_factory=dict)
    impactedRealtimeTasks: bool = False
    latestJudgmentsShadowOff: bool = False
    verdict: Literal["pass", "watch", "fail"] = "watch"
    conclusion: str = ""


class MainChainCanaryObservationPayload(BaseModel):
    timeRange: str | None = None
    clientCount: int | None = None
    enqueuedJobs: int | None = None
    completedJobs: int | None = None
    failedJobs: int | None = None
    newObjectHitRateBefore: float | None = None
    newObjectHitRateAfter: float | None = None
    fallbackRateBefore: float | None = None
    fallbackRateAfter: float | None = None
    resolverMismatchRateBefore: float | None = None
    resolverMismatchRateAfter: float | None = None
    approvalBacklog: int | None = None
    approvalLagHoursMedian: float | None = None
    claimCounts: dict[str, int] | None = None
    lockContention: dict[str, int] | None = None
    backfillThrottle: dict[str, int] | None = None
    impactedRealtimeTasks: bool | None = None
    latestJudgmentsShadowOff: bool | None = None
    verdict: Literal["pass", "watch", "fail"] | None = None
    conclusion: str | None = None


class MainChainStabilitySettingsRecord(BaseModel):
    latestJudgmentsShadowOff: bool = False
    backfillPaused: bool = False
    workerCounters: AnalysisWorkerCounterSnapshotRecord = Field(default_factory=AnalysisWorkerCounterSnapshotRecord)
    lastCanaryObservation: MainChainCanaryObservationRecord | None = None
    updatedAt: str


class MainChainStabilitySettingsPayload(BaseModel):
    latestJudgmentsShadowOff: bool | None = None
    backfillPaused: bool | None = None
    lastCanaryObservation: MainChainCanaryObservationPayload | None = None


class FeishuBotSettingsRecord(BaseModel):
    appId: str = ""
    receiveIdType: FeishuReceiveIdType = "open_id"
    receiverId: str = ""
    botName: str = "罗茜茜"
    userBindingCallbackUrl: str = ""
    ready: bool = False
    hasAppSecret: bool = False
    secretSource: str = "unconfigured"
    secretFingerprint: str | None = None
    lastConnectionStatus: Literal["idle", "success", "failed"] = "idle"
    lastConnectionMessage: str | None = None
    lastConnectedAt: str | None = None
    lastTestMessageAt: str | None = None
    updatedAt: str


class FeishuBotSettingsPayload(BaseModel):
    appId: str | None = None
    receiveIdType: FeishuReceiveIdType | None = None
    receiverId: str | None = None
    botName: str | None = None
    userBindingCallbackUrl: str | None = None
    appSecret: str | None = None
    clearAppSecret: bool = False
    sendTestMessage: bool = False
    testMessage: str | None = None


class FeishuUserBindingRecord(BaseModel):
    linked: bool = False
    readyForAuthorization: bool = False
    appId: str = ""
    userId: str = ""
    openId: str | None = None
    unionId: str | None = None
    feishuUserId: str | None = None
    name: str | None = None
    enName: str | None = None
    avatarUrl: str | None = None
    email: str | None = None
    tenantKey: str | None = None
    boundAt: str | None = None
    lastVerifiedAt: str | None = None
    lastError: str | None = None


class FeishuUserBindingStartResponse(BaseModel):
    authorizeUrl: str
    state: str
    expiresAt: str
    callbackUrl: str
    qrReady: bool = False
    qrBlockedReason: str | None = None


class OrgMembershipSummaryRecord(BaseModel):
    hasOrganization: bool = False
    organizationId: str | None = None
    organizationName: str | None = None


class OrgFeishuIntegrationAuditRecord(BaseModel):
    id: str
    organizationId: str
    actorUserId: str | None = None
    actorName: str | None = None
    appId: str = ""
    validationStatus: Literal["success", "failed"] = "failed"
    validationMessage: str = ""
    createdAt: str


class OrgFeishuIntegrationRecord(BaseModel):
    organizationId: str | None = None
    organizationName: str | None = None
    appId: str = ""
    enabled: bool = False
    hasAppSecret: bool = False
    configuredBy: str | None = None
    configuredAt: str | None = None
    updatedAt: str
    lastValidationStatus: Literal["idle", "success", "failed"] = "idle"
    lastValidationMessage: str | None = None
    recentAudits: list[OrgFeishuIntegrationAuditRecord] = Field(default_factory=list)


class OrgFeishuIntegrationSavePayload(BaseModel):
    appId: str | None = None
    appSecret: str | None = None
    clearAppSecret: bool = False


class FeishuDeliveryProfileRecord(BaseModel):
    userId: str
    organizationId: str | None = None
    organizationName: str | None = None
    mobile: str = ""
    normalizedMobile: str | None = None
    deliveryStatus: Literal["missing_org", "integration_pending", "missing_mobile", "matched", "not_found", "failed"] = "missing_mobile"
    deliveryStatusLabel: str = "未填写飞书手机号"
    readyForNotifications: bool = False
    receiveId: str | None = None
    lastVerifiedAt: str | None = None
    lastError: str | None = None
    blockedReason: str | None = None


class FeishuDeliveryProfileSavePayload(BaseModel):
    mobile: str | None = None


class FeishuMemberAuthorizationRecord(BaseModel):
    linked: bool = False
    readyForAuthorization: bool = False
    organizationId: str | None = None
    organizationName: str | None = None
    appId: str = ""
    userId: str = ""
    openId: str | None = None
    unionId: str | None = None
    feishuUserId: str | None = None
    name: str | None = None
    enName: str | None = None
    avatarUrl: str | None = None
    email: str | None = None
    tenantKey: str | None = None
    boundAt: str | None = None
    lastVerifiedAt: str | None = None
    lastError: str | None = None
    blockedReason: str | None = None


class FeishuMemberAuthorizationStartResponse(BaseModel):
    authorizeUrl: str
    state: str
    expiresAt: str
    callbackUrl: str
    qrReady: bool = False
    qrBlockedReason: str | None = None


class AiTagSuggestionPayload(BaseModel):
    title: str
    desc: str = ""
    collaboratorNames: list[str] = Field(default_factory=list)
    dueDate: str | None = None
    module: str = "任务与日程"


class AiTagSuggestionResponse(BaseModel):
    suggestedTags: list[str]


class PlanNodeRecord(BaseModel):
    id: str
    level: Literal["ceo", "director", "manager", "project"]
    title: str
    summary: str
    status: str
    ownerUserId: str | None = None
    ownerName: str | None = None
    ownerUnitId: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None


class WeeklyReviewRecord(BaseModel):
    id: str
    userId: str
    userName: str
    weekLabel: str
    workProgress: str = ""
    workBlocker: str = ""
    blockerType: str = ""
    workDirection: str = ""
    nextWeekFocus: str = ""
    supportNeeded: str = ""
    relatedPlanIds: list[str] = Field(default_factory=list)
    workFreeNote: str = ""
    personalGrowthNote: str = ""
    personalPrivateNote: str = ""
    personalVisibility: Literal["self"] = "self"
    submittedAt: str
    createdAt: str
    updatedAt: str


class WeeklyReviewTaskSnapshotRecord(BaseModel):
    title: str
    status: TaskStatus
    startDate: str | None = None
    dueDate: str | None = None
    createdAt: str
    ownerId: str | None = None
    ownerName: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    tags: list[TaskTagRecord] = Field(default_factory=list)
    listName: str
    listColor: str
    orgContext: TaskOrgContextRecord | None = None
    projectContext: TaskProjectContextRecord | None = None
    eventLineContext: "WeeklyReviewEventLineContextRecord | None" = None


class WeeklyReviewEventLineContextRecord(BaseModel):
    id: str | None = None
    name: str | None = None
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int = 0
    primaryClientId: str | None = None
    primaryClientName: str | None = None


class EventLineProjectFilterOptionRecord(BaseModel):
    id: str
    label: str
    kind: str = "client"
    lineCount: int = 0


class EventLineSourceStatusRecord(BaseModel):
    mode: str = "cloud_only"
    cloudAvailable: bool = False
    organizationId: str | None = None
    organizationName: str | None = None
    cloudApiUrl: str | None = None
    detail: str | None = None
    projectOptions: list[EventLineProjectFilterOptionRecord] = []


class EventLineRecord(BaseModel):
    id: str
    name: str
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    visibilityScope: Literal["private", "project_public"] = "project_public"
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int = 0
    ownerId: str | None = None
    ownerName: str | None = None
    primaryClientId: str | None = None
    primaryClientName: str | None = None
    primaryDepartmentId: str | None = None
    primaryDepartmentName: str | None = None
    participantIds: list[str] = Field(default_factory=list)
    closedAt: str | None = None
    closedByUserId: str | None = None
    createdAt: str
    updatedAt: str


class EventLineActivityRecord(BaseModel):
    id: str
    eventLineId: str
    sourceType: Literal["task_activity", "meeting", "support_request", "review", "attachment", "manual_note"]
    sourceId: str
    happenedAt: str
    actorId: str | None = None
    actorName: str | None = None
    title: str
    summary: str
    metadata: dict[str, object] = Field(default_factory=dict)
    isKey: bool = False


class EventLineDetailRecord(BaseModel):
    eventLine: EventLineRecord
    tasks: list[TaskRecord] = Field(default_factory=list)
    activities: list[EventLineActivityRecord] = Field(default_factory=list)
    memorySnapshot: EventLineMemorySnapshot | None = None
    predictionReadiness: float | None = None
    clarificationNeeds: list[str] = Field(default_factory=list)


class EventLineAttachmentRecord(BaseModel):
    id: str
    eventLineId: str
    fileName: str = ""
    fileType: str = ""
    displayMode: Literal["expanded", "collapsed"] = "collapsed"
    description: str = ""
    uploadedBy: str = ""
    uploadedAt: str = ""
    localPath: str | None = None
    previewUrl: str | None = None


class EventLineApprovalNodeRecord(BaseModel):
    id: str
    eventLineId: str
    title: str = ""
    requestedBy: str = ""
    approverName: str = ""
    status: Literal["pending", "approved", "rejected"] = "pending"
    note: str = ""
    createdAt: str = ""
    resolvedAt: str | None = None


class EventLineCreatePayload(BaseModel):
    name: str = Field(min_length=1)
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    visibilityScope: Literal["private", "project_public"] = "project_public"
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int | None = None
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] = Field(default_factory=list)


class EventLineUpdatePayload(BaseModel):
    name: str | None = None
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] | None = None
    status: Literal["active", "blocked", "paused", "done", "archived"] | None = None
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int | None = None
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] | None = None
    syncLinkedTaskClientIds: bool | None = None


class EventLineClarificationDraftPayload(BaseModel):
    conversationText: str = Field(min_length=1)


class EventLineClarificationDraftRecord(BaseModel):
    summary: str = ""
    stage: str = ""
    intent: str = ""
    currentBlocker: str = ""
    nextStep: str = ""
    recentDecision: str = ""
    missingInfo: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class WeeklyReviewTaskStructuredNoteRecord(BaseModel):
    reflection: str = ""
    lightweightTag: Literal["", "资料不足", "等待他人", "方向不清", "资源不够", "工作过度饱和"] = ""
    planCommitment: str = ""
    progress: str = ""
    completionStatus: Literal["done_on_time", "done_late", "in_progress", "not_done"] = "in_progress"
    departmentPlanId: str | None = None
    departmentPlanAlignment: Literal["aligned", "partial", "misaligned", "unknown"] = "unknown"
    organizationPlanId: str | None = None
    organizationPlanAlignment: Literal["aligned", "partial", "misaligned", "unknown"] = "unknown"
    successReason: str = ""
    successExperience: str = ""
    blockerReason: str = ""
    failureInsight: str = ""
    supportNeeded: str = ""
    nextAction: str = ""


class ReviewMetricCardRecord(BaseModel):
    key: Literal["timely_completion", "department_alignment", "strategy_alignment", "reflection_capture"]
    label: str
    valueText: str
    numerator: int
    denominator: int
    rate: float
    description: str
    tone: Literal["positive", "neutral", "warning", "risk"]


class WeeklyReviewTaskEntryRecord(BaseModel):
    id: str
    reviewId: str | None = None
    taskId: str
    weekLabel: str
    contentDomain: Literal["work", "personal"]
    note: str = ""
    structuredNote: WeeklyReviewTaskStructuredNoteRecord = Field(default_factory=WeeklyReviewTaskStructuredNoteRecord)
    reviewedAt: str | None = None
    taskSnapshot: WeeklyReviewTaskSnapshotRecord


class ReviewEvidenceWeightRecord(BaseModel):
    sourceType: Literal["user_note", "task_fact", "organization_dna", "team_plan", "focus_plan", "project_context", "external_context"]
    label: str
    weight: Literal["high", "medium", "low"]
    rationale: str


class ReviewHypothesisRecord(BaseModel):
    id: str
    lens: Literal["execution", "organization", "business", "team", "market", "growth"]
    title: str
    statement: str
    confidence: Literal["high", "medium", "low"]
    reason: str
    relatedTaskIds: list[str] = Field(default_factory=list)
    evidenceSources: list[str] = Field(default_factory=list)
    assumptionNote: str = ""


class EventLineEvidenceSlotRecord(BaseModel):
    key: Literal["stage", "goal", "blocker", "next_action", "recent_change", "owner_chain", "recent_decision", "project_link"]
    label: str
    coverage: Literal["full", "partial", "missing"]
    evidenceStrength: Literal["strong", "medium", "weak", "none"]
    sourceTypes: list[Literal["event_line", "task_fact", "project_context", "user_note", "uploaded_doc", "manual_clarification"]] = Field(default_factory=list)
    summary: str
    recommendedFix: Literal["upload_docs", "clarify_now", "wait_for_more_trace"]


class EventLineCompletenessRecord(BaseModel):
    eventLineId: str
    title: str
    score: int
    status: Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"]
    missingSlots: list[str] = Field(default_factory=list)
    strongestSlots: list[str] = Field(default_factory=list)
    memoryConfidence: float | None = None
    backgroundSources: list[str] = Field(default_factory=list)
    slots: list[EventLineEvidenceSlotRecord] = Field(default_factory=list)


class ReviewDashboardEvidenceRefRecord(BaseModel):
    sourceType: Literal["task", "meeting", "support_request", "attachment", "clarification", "event_line", "notebook", "event_line_memory"]
    sourceId: str
    title: str
    summary: str | None = None


class ReviewDashboardCardTargetRecord(BaseModel):
    targetType: Literal["event_line", "task_view", "meeting", "support_request", "attachment_group", "task"]
    targetId: str
    targetLabel: str | None = None
    targetFilters: dict[str, object] = Field(default_factory=dict)
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class EventLineContextFactRecord(BaseModel):
    sourceType: Literal["task", "meeting", "attachment", "support_request", "clarification", "notebook", "event_line_memory"]
    sourceId: str
    title: str
    summary: str
    happenedAt: str | None = None


class EventLineJudgmentRecord(BaseModel):
    eventLineId: str
    title: str
    viewerRole: Literal["employee", "department_lead", "admin"]
    judgmentVersion: str = "event_line_judgment_v1"
    bundleFingerprint: str = ""
    coverageScore: int = 0
    confidenceScore: int = 0
    safeOutputMode: Literal["needs_input", "summary_only", "full_judgment"] = "needs_input"
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    whatHappened: str
    whyItMatters: str
    coreBlocker: str
    blockerType: Literal["business", "collaboration", "decision", "structure", "capacity", "evidence"]
    evidenceSummary: str
    managerImplication: str
    nextWeekFocus: str
    minimumAction: str
    riskIfIgnored: str
    opportunityIfAmplified: str
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)
    target: ReviewDashboardCardTargetRecord | None = None


class EventLineContextBundleRecord(BaseModel):
    eventLineId: str
    lineName: str
    businessCategory: str = ""
    stage: str = ""
    summary: str = ""
    intent: str = ""
    currentWork: str = ""
    currentBlocker: str = ""
    recentDecision: str = ""
    nextStep: str = ""
    recentProgress: str = ""
    projectName: str = ""
    collaborationRelationship: str = ""
    organizationIntro: str = ""
    currentChallenges: list[str] = Field(default_factory=list)
    collaborationGoals: list[str] = Field(default_factory=list)
    keyPeople: list[str] = Field(default_factory=list)
    keyProducts: list[str] = Field(default_factory=list)
    recentFacts: list[str] = Field(default_factory=list)
    taskFacts: list[EventLineContextFactRecord] = Field(default_factory=list)
    meetingFacts: list[EventLineContextFactRecord] = Field(default_factory=list)
    attachmentFacts: list[EventLineContextFactRecord] = Field(default_factory=list)
    clarificationFacts: list[EventLineContextFactRecord] = Field(default_factory=list)
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)
    trendSignals: list[TrendSignalRecord] = Field(default_factory=list)
    taskCount: int = 0
    meetingCount: int = 0
    attachmentCount: int = 0
    supportRequestCount: int = 0
    readiness: Literal["low", "medium", "high"] = "low"


class EventLineSummaryCardRecord(BaseModel):
    eventLineId: str
    title: str
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    projectName: str | None = None
    moduleName: str | None = None
    flowName: str | None = None
    whatThisLineIs: str
    whatHappenedThisWeek: str
    currentState: str
    mainBlocker: str
    nextCriticalMove: str
    ownerNames: list[str] = Field(default_factory=list)
    completenessScore: int
    predictionReadiness: Literal["not_ready", "summary_only", "conservative_forecast", "strong_forecast"]
    missingSlots: list[str] = Field(default_factory=list)
    memoryConfidence: float | None = None
    backgroundSources: list[str] = Field(default_factory=list)
    evidencePreview: list[str] = Field(default_factory=list)
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class EventLineRiskCardRecord(BaseModel):
    eventLineId: str
    title: str
    riskType: Literal["schedule_drift", "collaboration_friction", "decision_lag", "goal_drift", "workflow_breakdown", "overload"]
    statement: str
    forecastWindow: Literal["1w", "2w", "3w"]
    probability: Literal["high", "medium", "low"]
    impactScope: Literal["person", "team", "project", "org"]
    triggerSignals: list[str] = Field(default_factory=list)
    whyNow: str
    ifIgnored: str
    suggestedAction: str
    ownerRole: str
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class EventLineOpportunityCardRecord(BaseModel):
    eventLineId: str
    title: str
    opportunityType: Literal["repeatable_pattern", "momentum_building", "process_upgrade", "capability_signal", "leverage_point"]
    statement: str
    forecastWindow: Literal["1w", "2w", "3w"]
    confidence: Literal["high", "medium", "low"]
    upside: str
    supportingSignals: list[str] = Field(default_factory=list)
    recommendedAmplifier: str
    ownerRole: str
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class TrendSignalRecord(BaseModel):
    key: str
    title: str
    statement: str
    signalType: Literal[
        "repeat_reschedule",
        "repeat_review_pending",
        "repeat_support_request",
        "stalled_event_line",
        "escalating_blocker",
        "thin_evidence",
    ]
    severity: Literal["high", "medium", "low"]
    windowLabel: str
    relatedEventLineId: str | None = None
    relatedTaskIds: list[str] = Field(default_factory=list)
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)
    target: ReviewDashboardCardTargetRecord | None = None


class WeeklyReviewAnalysisRecord(BaseModel):
    scope: TaskReviewScope
    emphasis: Literal["summary", "analysis"]
    headline: str
    caution: str
    weeklyOverview: str = ""
    weeklyFocusLines: list[str] = Field(default_factory=list)
    weeklyNextFocus: list[str] = Field(default_factory=list)
    dnaModuleTitles: list[str] = Field(default_factory=list)
    metricCards: list[ReviewMetricCardRecord] = Field(default_factory=list)
    evidenceWeights: list[ReviewEvidenceWeightRecord] = Field(default_factory=list)
    confirmedFacts: list[str] = Field(default_factory=list)
    hypothesisHighlights: list[ReviewHypothesisRecord] = Field(default_factory=list)
    nextWeekFocus: list[str] = Field(default_factory=list)
    eventLineSummaries: list[EventLineSummaryCardRecord] = Field(default_factory=list)
    eventLineCompleteness: list[EventLineCompletenessRecord] = Field(default_factory=list)
    eventLineContextBundles: list[EventLineContextBundleRecord] = Field(default_factory=list)
    eventLineJudgments: list[EventLineJudgmentRecord] = Field(default_factory=list)
    riskCards: list[EventLineRiskCardRecord] = Field(default_factory=list)
    opportunityCards: list[EventLineOpportunityCardRecord] = Field(default_factory=list)
    trendSignals: list[TrendSignalRecord] = Field(default_factory=list)
    narrativeAnalyses: list[NarrativeAnalysisRecord] = Field(default_factory=list)


class TaskContextPreviewRecord(BaseModel):
    taskId: str
    clientId: str | None = None
    clientName: str | None = None
    contextBundle: EventLineContextBundleRecord
    judgment: EventLineJudgmentRecord
    judgmentVersion: str = "event_line_judgment_v1"
    bundleFingerprint: str = ""
    coverageScore: int = 0
    confidenceScore: int = 0
    safeOutputMode: Literal["needs_input", "summary_only", "full_judgment"] = "needs_input"
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    summaryChips: list[str] = Field(default_factory=list)
    readiness: Literal["low", "medium", "high"] = "low"


class TaskSmartBriefActionItem(BaseModel):
    text: str
    sourceLabel: str = ""
    internalSuggestedOwner: str = ""
    actionKind: str = ""
    dueHint: str = ""
    deliverable: str = ""
    actionKey: str = ""
    taskTitleSuggestion: str = ""
    taskDescriptionSuggestion: str = ""


class TaskSmartBriefRecord(BaseModel):
    taskId: str
    summary: str
    summarySourceLabels: list[str] = Field(default_factory=list)
    actionItems: list[TaskSmartBriefActionItem] = Field(default_factory=list)


class WorkspaceStateItemRecord(BaseModel):
    id: str
    signalType: Literal["change", "progress", "risk", "question", "judgment", "meeting", "task", "noise"]
    sourceType: str
    sourceId: str
    title: str
    summary: str
    authority: Literal["approved", "candidate", "informational", "warning"] = "informational"
    updatedAt: str | None = None


class WorkspaceStateProjectionRecord(BaseModel):
    changeItems: list[WorkspaceStateItemRecord] = Field(default_factory=list)
    progressItems: list[WorkspaceStateItemRecord] = Field(default_factory=list)
    signalNoiseFlags: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    stateConfidence: Literal["low", "medium", "high"] = "low"


class StateQueryPlanRecord(BaseModel):
    primaryIntent: Literal["overview", "changes", "progress", "risk", "questions", "judgment", "timeline"] = "overview"
    focusAreas: list[str] = Field(default_factory=list)
    needsBoundaryGuard: bool = True


class StateQueryHitRecord(BaseModel):
    sourceType: str
    sourceId: str
    label: str
    summary: str
    signalKind: Literal["change", "progress", "risk", "question", "judgment", "timeline"]
    authorityLevel: Literal["approved", "candidate", "informational", "warning"] = "informational"


class StateAnswerContextPackRecord(BaseModel):
    plan: StateQueryPlanRecord
    summary: str
    stateSources: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    stateConfidence: Literal["low", "medium", "high"] = "low"
    hits: list[StateQueryHitRecord] = Field(default_factory=list)
    sections: StateAnswerSectionsRecord = Field(default_factory=StateAnswerSectionsRecord)
    sourceSummary: StateSourceSummaryRecord = Field(default_factory=StateSourceSummaryRecord)
    candidateLeakageCount: int = 0
    fallbackReason: str | None = None


class HybridJudgmentContextPackRecord(BaseModel):
    judgmentQueryMode: JudgmentQueryMode = "hybrid"
    evidenceSupportMode: EvidenceSupportMode = "none"
    summary: str
    stateSources: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    stateConfidence: Literal["low", "medium", "high"] = "low"
    sections: StateAnswerSectionsRecord = Field(default_factory=StateAnswerSectionsRecord)
    sourceSummary: StateSourceSummaryRecord = Field(default_factory=StateSourceSummaryRecord)
    evidenceSupportItems: list[EvidenceSupportItemRecord] = Field(default_factory=list)
    approvedJudgments: list[str] = Field(default_factory=list)
    registeredCandidateJudgments: list[str] = Field(default_factory=list)
    synthesizedCandidateFindings: list[str] = Field(default_factory=list)
    dnaSignals: list[str] = Field(default_factory=list)
    meetingSignals: list[str] = Field(default_factory=list)
    taskSignals: list[str] = Field(default_factory=list)
    openQuestionSignals: list[str] = Field(default_factory=list)
    conflictSignals: list[str] = Field(default_factory=list)
    rawExcerpts: list[str] = Field(default_factory=list)
    unknownsAndNextSteps: list[str] = Field(default_factory=list)
    fallbackReason: str | None = None


class PrepPackMaterialRecord(BaseModel):
    sourceType: str
    sourceId: str
    title: str
    summary: str
    authorityLevel: str = ""


class PrepPackCardRecord(BaseModel):
    taskId: str
    title: str
    summary: str
    materials: list[PrepPackMaterialRecord] = Field(default_factory=list)
    openQuestions: list[str] = Field(default_factory=list)
    judgments: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    sourceLabels: list[str] = Field(default_factory=list)
    proposalId: str | None = None


class ProposalTargetRefRecord(BaseModel):
    targetType: Literal["client", "task", "meeting", "event_line", "judgment"]
    targetId: str
    label: str = ""


class ExecutionArtifactRefRecord(BaseModel):
    artifactType: str
    refId: str
    title: str


class ExecutionTicketResultRecord(BaseModel):
    resultType: Literal["recorded_only", "prep_artifact_ready", "followup_task_created", "failed"] = "recorded_only"
    summary: str = ""
    createdTaskIds: list[str] = Field(default_factory=list)
    artifactRefs: list[ExecutionArtifactRefRecord] = Field(default_factory=list)


class ProposalRecordRecord(BaseModel):
    id: str
    clientId: str
    kind: Literal["task_prep", "meeting_prep", "meeting_followup"]
    status: Literal["draft", "pending_review", "approved", "rejected", "execution_pending", "executed", "failed"]
    riskLevel: Literal["low", "medium", "high"] = "medium"
    title: str
    summary: str = ""
    rationale: str = ""
    targetRefs: list[ProposalTargetRefRecord] = Field(default_factory=list)
    sourceRefs: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    createdBy: str = ""
    decidedBy: str | None = None
    decidedAt: str | None = None
    rejectedReason: str | None = None
    executionTicketId: str | None = None
    executionTicket: ExecutionTicketRecord | None = None
    createdAt: str
    updatedAt: str


class ExecutionTicketRecord(BaseModel):
    id: str
    proposalId: str
    clientId: str
    executionType: str
    status: Literal["pending", "running", "executed", "failed"] = "pending"
    payload: dict[str, object] = Field(default_factory=dict)
    result: ExecutionTicketResultRecord = Field(default_factory=ExecutionTicketResultRecord)
    errorMessage: str | None = None
    executedAt: str | None = None
    createdAt: str
    updatedAt: str


class ProposalDecisionPayload(BaseModel):
    comment: str = ""


class ProposalExecutionResponse(BaseModel):
    proposal: ProposalRecordRecord
    executionTicket: ExecutionTicketRecord | None = None


class StrategicPermissionRecord(BaseModel):
    canEdit: bool = False
    isCeo: bool = False
    leaderUserId: str | None = None
    notice: str | None = None


class StrategicReadinessRecord(BaseModel):
    status: Literal["ready", "insufficient"] = "insufficient"
    score: int = 0
    summary: str
    gaps: list[str] = Field(default_factory=list)


class StrategicJudgmentRecord(BaseModel):
    value: str
    status: Literal["system_draft", "confirmed", "waiting"] = "system_draft"
    sources: list[str] = Field(default_factory=list)


class StrategicHeadlineRecord(BaseModel):
    weekSummary: StrategicJudgmentRecord
    mainContradiction: StrategicJudgmentRecord
    coreBreakthrough: StrategicJudgmentRecord
    focusItems: list[str] = Field(default_factory=list)
    focusStatus: Literal["system_draft", "confirmed", "waiting"] = "system_draft"
    freshness: str = ""


class StrategicHealthLineRecord(BaseModel):
    key: str
    title: str
    status: Literal["healthy", "watch", "risk", "uncalibrated"] = "uncalibrated"
    trend: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


class StrategicLineRecord(BaseModel):
    id: str
    title: str
    summary: str
    module: str | None = None
    flow: str | None = None
    stage: str | None = None
    blocker: str
    decision: str
    nextStep: str
    momentum: Literal["加码", "稳住", "收口", "暂停"] = "稳住"
    evidence: list[str] = Field(default_factory=list)
    memoryConfidence: float | None = None
    predictionReadiness: float | None = None
    clarificationNeeds: list[str] = Field(default_factory=list)


class StrategicChecklistItemRecord(BaseModel):
    title: str
    detail: str
    source: str
    priority: Literal["high", "medium", "low"] = "medium"


class StrategicChecklistGroupRecord(BaseModel):
    key: str
    title: str
    description: str
    items: list[StrategicChecklistItemRecord] = Field(default_factory=list)


class StrategicChangePointRecord(BaseModel):
    title: str
    summary: str
    confidence: str
    signals: list[str] = Field(default_factory=list)


class StrategicEvidenceCardRecord(BaseModel):
    label: str
    value: str


class StrategicEvidencePreviewRecord(BaseModel):
    summary: str
    cards: list[StrategicEvidenceCardRecord] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    keyFacts: list[str] = Field(default_factory=list)
    keyWarnings: list[str] = Field(default_factory=list)


class StrategicAssetCandidateRecord(BaseModel):
    title: str
    source: str
    summary: str
    nextAction: str


class StrategicMeetingPackDraftRecord(BaseModel):
    title: str
    agenda: list[str] = Field(default_factory=list)
    groups: list[StrategicChecklistGroupRecord] = Field(default_factory=list)


class StrategicCockpitSnapshotRecord(BaseModel):
    clientId: str
    clientName: str
    clientTagline: str
    stageLabel: str
    permission: StrategicPermissionRecord
    readiness: StrategicReadinessRecord
    headline: StrategicHeadlineRecord
    health: list[StrategicHealthLineRecord] = Field(default_factory=list)
    strategicLines: list[StrategicLineRecord] = Field(default_factory=list)
    twoWeekChanges: list[StrategicChangePointRecord] = Field(default_factory=list)
    pendingDecisions: list[StrategicChecklistItemRecord] = Field(default_factory=list)
    pendingMaterials: list[StrategicChecklistItemRecord] = Field(default_factory=list)
    meetingPackDraft: StrategicMeetingPackDraftRecord
    evidencePreview: StrategicEvidencePreviewRecord
    assetCandidates: list[StrategicAssetCandidateRecord] = Field(default_factory=list)
    officialLayer: dict[str, object] = Field(default_factory=dict)
    radarLayer: dict[str, object] = Field(default_factory=dict)
    officialLayerStatus: Literal["ready", "empty"] = "empty"
    officialEmptyReason: str | None = None
    resolutionTrace: dict[str, object] = Field(default_factory=dict)
    notebookSummary: OrganizationNotebookSnapshot | None = None
    memoryStatus: MemoryStatus | None = None
    linkedEventLineMemories: list[EventLineMemorySnapshot] = Field(default_factory=list)


class StrategicLineDetailRecord(StrategicLineRecord):
    clientId: str
    clientName: str
    stageLabel: str = ""
    relatedTaskIds: list[str] = Field(default_factory=list)
    relatedTaskTitles: list[str] = Field(default_factory=list)
    contextSummary: str = ""


class StrategicCockpitConfirmPayload(BaseModel):
    weekSummary: str = ""
    mainContradiction: str = ""
    coreBreakthrough: str = ""
    focusItems: list[str] = Field(default_factory=list)


StrategicThoughtScope = Literal["client", "system"]
StrategicThoughtStatus = Literal["draft", "confirmed", "dismissed", "task_created", "waiting_evidence"]
StrategicThoughtConfidenceLevel = Literal["low", "medium", "high", "none"]

StrategicThoughtSourceType = Literal[
    "strategic_cockpit",
    "strategic_line",
    "headline",
    "pending_decision",
    "pending_material",
    "brain_dashboard",
    "judgment_version",
    "theme_cluster",
    "conflict_group",
    "open_question",
    "event_line",
    "meeting",
    "review",
    "knowledge",
    "system",
]


class StrategicThoughtSourceRecord(BaseModel):
    sourceType: StrategicThoughtSourceType
    sourceId: str | None = None
    label: str
    detail: str | None = None


class StrategicThoughtReviewRecord(BaseModel):
    thoughtId: str
    status: StrategicThoughtStatus
    note: str = ""
    taskId: str | None = None
    judgmentId: str | None = None
    reviewedAt: str | None = None
    reviewedBy: str | None = None


class StrategicThoughtRecord(BaseModel):
    id: str
    scope: StrategicThoughtScope
    clientId: str | None = None
    clientName: str = ""
    line: str
    observation: str
    suggestion: str
    confidence: int | None = None
    confidenceLevel: StrategicThoughtConfidenceLevel = "none"
    status: StrategicThoughtStatus = "draft"
    isSystem: bool = False
    dueDateHint: str = ""
    tags: list[str] = Field(default_factory=list)
    sources: list[StrategicThoughtSourceRecord] = Field(default_factory=list)
    evidenceCount: int = 0
    generatedAt: str
    staleReason: str | None = None
    evidenceLevel: Literal["none", "weak", "medium", "strong"] | None = None
    reason: str | None = None
    review: StrategicThoughtReviewRecord | None = None


class StrategicThoughtsResponseRecord(BaseModel):
    items: list[StrategicThoughtRecord] = Field(default_factory=list)
    total: int = 0
    generatedAt: str
    selectedClientId: str | None = None
    usingMockData: bool = False


class StrategicThoughtReviewPayload(BaseModel):
    action: Literal["confirm", "dismiss", "mark_task_created"]
    note: str = ""
    taskId: str | None = None
    createJudgment: bool = True


class ManagementSignalCardRecord(BaseModel):
    id: str
    reviewId: str
    userId: str
    userName: str
    weekLabel: str
    contentDomain: Literal["work"]
    visibilityScope: Literal["team", "department", "org"]
    eligibleForAggregation: bool
    eligibleForManagerRetrieval: bool
    signals: dict[str, object]
    createdAt: str
    updatedAt: str


class PersonalGrowthCardRecord(BaseModel):
    id: str
    reviewId: str
    userId: str
    contentDomain: Literal["personal"]
    visibilityScope: Literal["self"]
    summary: str
    suggestions: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ReviewActionCardRecord(BaseModel):
    id: str
    actionType: Literal["task", "support_request", "resource_request", "meeting", "one_on_one"]
    title: str
    payload: dict[str, object]
    status: str
    createdAt: str
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class HierarchyReportRecord(BaseModel):
    id: str
    scopeType: Literal["employee", "team", "org"]
    scopeRefId: str
    weekLabel: str
    logicMode: str
    judgmentVersion: str | None = None
    bundleFingerprint: str | None = None
    coverageScore: int | None = None
    confidenceScore: int | None = None
    safeOutputMode: Literal["needs_input", "summary_only", "full_judgment"] | None = None
    headline: str
    summary: str
    summaryMetrics: list[ReviewMetricCardRecord] = Field(default_factory=list)
    focusAreas: list[str] = Field(default_factory=list)
    supportSignals: list[str] = Field(default_factory=list)
    suggestedActions: list[str] = Field(default_factory=list)
    anonymousInsights: list[str] = Field(default_factory=list)
    sourcePolicy: dict[str, object] = Field(default_factory=dict)
    actions: list[ReviewActionCardRecord] = Field(default_factory=list)
    publishState: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    publishedAt: str | None = None
    publishedBy: str | None = None
    invalidatedAt: str | None = None
    createdAt: str
    updatedAt: str


class ReviewSimulationBundleRecord(BaseModel):
    sampleSize: int
    label: str
    orgReport: HierarchyReportRecord | None = None
    departmentReports: list[HierarchyReportRecord] = Field(default_factory=list)


class GrowthAbilityProfileRecord(BaseModel):
    id: str
    abilityKey: GrowthAbilityKey
    label: str
    description: str = ""
    stageRules: list[dict[str, object]] = Field(default_factory=list)
    positiveSignals: list[str] = Field(default_factory=list)
    negativeSignals: list[str] = Field(default_factory=list)
    weights: dict[str, object] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class GrowthSignalEventRecord(BaseModel):
    id: str
    userId: str
    userName: str = ""
    sourceType: str
    sourceId: str
    reviewId: str | None = None
    taskId: str | None = None
    weekLabel: str = ""
    rawText: str = ""
    context: dict[str, object] = Field(default_factory=dict)
    dedupeKey: str
    createdAt: str


class GrowthEvidenceRecord(BaseModel):
    id: str
    signalId: str
    userId: str
    userName: str = ""
    abilityKey: GrowthAbilityKey
    evidenceType: GrowthEvidenceType
    level: GrowthEvidenceLevel
    confidence: GrowthConfidence = "medium"
    reason: str = ""
    reviewId: str | None = None
    taskId: str | None = None
    handbookEntryId: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    contributionTags: list[GrowthContributionTag] = Field(default_factory=list)
    orgContributionScore: int = 0
    suggestedPremiumRate: float = 0.0
    validationState: GrowthValidationState = "candidate"
    aiReason: str = ""
    aiConfidence: float = 0.0
    createdAt: str


class GrowthContextLinkRecord(BaseModel):
    objectType: str
    objectId: str
    label: str
    subtitle: str = ""
    tab: str = ""
    statusLabel: str = ""


class XpLedgerEntryRecord(BaseModel):
    id: str
    userId: str
    userName: str = ""
    abilityKey: GrowthAbilityKey
    abilityLabel: str
    evidenceId: str
    xpType: GrowthEvidenceType
    delta: int
    baseXp: int = 0
    premiumRate: float = 0.0
    premiumXp: int = 0
    totalXp: int = 0
    reason: str = ""
    sourceType: str = ""
    sourceId: str = ""
    sourceTitle: str | None = None
    handbookEntryId: str | None = None
    taskId: str | None = None
    meetingId: str | None = None
    reviewId: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    businessCategory: str | None = None
    projectStage: str | None = None
    sourceRoute: list[str] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    contextSummary: str = ""
    strategicLink: str | None = None
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    contributionTags: list[GrowthContributionTag] = Field(default_factory=list)
    validationState: GrowthValidationState = "candidate"
    orgContributionScore: int = 0
    weekLabel: str = ""
    createdAt: str
    reversedAt: str | None = None


class LearningContentItemRecord(BaseModel):
    id: str
    contentType: LearningContentType
    abilityKey: GrowthAbilityKey
    title: str
    summary: str
    body: str
    practiceTask: str = ""
    acceptanceCriteria: list[str] = Field(default_factory=list)
    sourceKind: str = "system_rule"
    sourceRefId: str | None = None
    status: str = "active"
    createdAt: str
    updatedAt: str


class LearningRecommendationRecord(BaseModel):
    id: str
    userId: str
    userName: str = ""
    abilityKey: GrowthAbilityKey
    abilityLabel: str
    contentItemId: str
    contentType: LearningContentType
    title: str
    summary: str
    body: str
    practiceTask: str = ""
    reason: str = ""
    linkedTaskId: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectStage: str | None = None
    triggerNode: str | None = None
    whyNow: str = ""
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    priority: Literal["high", "normal", "low"] = "normal"
    status: LearningRecommendationStatus = "active"
    acceptedTaskId: str | None = None
    dismissedReason: str | None = None
    dedupeKey: str
    createdAt: str
    updatedAt: str


class GrowthAbilityScoreRecord(BaseModel):
    abilityKey: GrowthAbilityKey
    label: str
    currentScore: int
    previousScore: int
    totalXp: int
    weeklyXp: int
    stage: str
    nextStage: str
    evidence: str = ""


class GrowthRankRecord(BaseModel):
    key: str
    name: str
    division: str | None = None
    fullLabel: str
    progress: float = 0.0
    nextName: str | None = None
    xpToNext: int = 0


class GrowthSourceCoverageRecord(BaseModel):
    taskSignals: int = 0
    meetingSignals: int = 0
    strategicSignals: int = 0
    reviewSignals: int = 0
    handbookSignals: int = 0
    clientCount: int = 0
    eventLineCount: int = 0


class GrowthProjectHighlightRecord(BaseModel):
    id: str
    label: str
    type: str
    weeklyXp: int = 0
    entryCount: int = 0
    summary: str = ""
    abilityKeys: list[GrowthAbilityKey] = Field(default_factory=list)
    contexts: list[GrowthContextLinkRecord] = Field(default_factory=list)


class GrowthPendingCaptureRecord(BaseModel):
    id: str
    sourceType: str
    sourceId: str
    status: GrowthPendingCaptureState = "open"
    title: str
    summary: str = ""
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectStage: str | None = None
    nextActionText: str = ""
    missingReasons: list[str] = Field(default_factory=list)
    abilityKeys: list[GrowthAbilityKey] = Field(default_factory=list)
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    stateReason: str = ""
    promotedHandbookEntryId: str | None = None
    updatedAt: str = ""


class GrowthFocusActionRecord(BaseModel):
    id: str
    title: str
    summary: str = ""
    whyNow: str = ""
    linkedTaskId: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectStage: str | None = None
    triggerNode: str | None = None
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)


class GrowthAbilityGapRecord(BaseModel):
    abilityKey: GrowthAbilityKey
    label: str
    currentScore: int
    requiredScore: int
    gap: int
    reason: str = ""
    sourceLabel: str = ""
    sourceType: str = ""
    sourceId: str = ""


class GrowthTaskIntentRecord(BaseModel):
    taskKind: str = "general_execution"
    goal: str = ""
    deliverable: str = ""
    riskTypes: list[str] = Field(default_factory=list)
    requiredAbilities: list[GrowthAbilityKey] = Field(default_factory=list)
    confidence: float = 0.0
    whyRelevant: str = ""


class GrowthUniversalSkillItemRecord(BaseModel):
    id: str
    cardType: Literal["动作卡", "检查卡", "话术卡", "模板卡"] = "动作卡"
    title: str
    summary: str = ""
    whyRelevant: str = ""
    checklist: list[str] = Field(default_factory=list)
    talkTrack: list[str] = Field(default_factory=list)
    templateHint: str = ""
    sourceKind: Literal["rule", "project_context", "ai_supplement"] = "rule"
    expectedOutput: str = ""
    linkedContext: GrowthContextLinkRecord | None = None


class GrowthProjectContextPackRecord(BaseModel):
    title: str = ""
    taskNotes: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    memoryHints: list[str] = Field(default_factory=list)
    linkedFacts: list[str] = Field(default_factory=list)
    clientSummary: str = ""
    recentMeetings: list[str] = Field(default_factory=list)
    eventLineSummary: str = ""
    strategicFocus: list[str] = Field(default_factory=list)
    keyWarnings: list[str] = Field(default_factory=list)
    contextGaps: list[str] = Field(default_factory=list)


class GrowthActionPlanItemRecord(BaseModel):
    id: str
    phaseGroup: Literal["before", "during", "after"] = "before"
    title: str
    purpose: str = ""
    expectedOutput: str = ""
    ifMissing: str = ""
    actionLabel: str = ""
    sourceKind: Literal["rule", "project_context", "ai_supplement"] = "rule"
    linkedContext: GrowthContextLinkRecord | None = None


class GrowthMaterialRefRecord(BaseModel):
    id: str
    title: str
    summary: str = ""
    sourceKind: Literal["task_material", "project_context", "client_workspace", "event_line", "strategic_focus", "rule", "ai_supplement"] = "project_context"
    linkedContext: GrowthContextLinkRecord | None = None


class GrowthWorkbenchStepRecord(BaseModel):
    id: str
    name: str
    output: str = ""
    bottlenecks: list[str] = Field(default_factory=list)


class GrowthWorkbenchTaskRecord(BaseModel):
    id: str
    title: str
    project: str = ""
    clientName: str | None = None
    eventLineName: str | None = None
    deadline: str = ""
    urgency: str = ""
    urgencyColor: str = ""
    phase: str = ""
    risks: list[str] = Field(default_factory=list)
    nextAdvice: str = ""
    robotReady: bool = False
    robotReasons: list[str] = Field(default_factory=list)
    recommendationId: str | None = None
    linkedTaskId: str | None = None
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    xpReward: int = 0
    contextSummary: str = ""
    projectModuleName: str | None = None
    projectFlowName: str | None = None
    projectStage: str | None = None
    businessCategory: str | None = None
    sourceEvidence: list[str] = Field(default_factory=list)
    currentBlocker: str | None = None
    missingSignals: list[str] = Field(default_factory=list)
    hasBackground: bool = False
    hasDeadline: bool = False
    isCrossDepartment: bool = False
    needsReview: bool = False
    evidenceCount: int = 0
    pendingCollaborations: int = 0
    taskIntent: GrowthTaskIntentRecord = Field(default_factory=GrowthTaskIntentRecord)
    universalSkills: list[GrowthUniversalSkillItemRecord] = Field(default_factory=list)
    projectContextPack: GrowthProjectContextPackRecord = Field(default_factory=GrowthProjectContextPackRecord)
    actionPlan: list[GrowthActionPlanItemRecord] = Field(default_factory=list)
    materialRefs: list[GrowthMaterialRefRecord] = Field(default_factory=list)


class GrowthWorkbenchActionRecord(BaseModel):
    id: str
    title: str
    output: str = ""
    scenario: str = ""
    actionLabel: str = ""
    supportTitle: str = ""
    detail: str = ""
    kind: Literal["schedule", "support", "process", "compose", "task"] = "task"
    recommendationId: str | None = None
    linkedContext: GrowthContextLinkRecord | None = None
    seedTitle: str | None = None
    seedSummary: str | None = None


class GrowthWorkbenchMaterialRecord(BaseModel):
    id: str
    title: str
    type: Literal["流程说明", "经验案例", "模板工具"] = "流程说明"
    scenario: str = ""
    summary: str = ""
    linkedContext: GrowthContextLinkRecord | None = None


class GrowthLearningSummaryRecord(BaseModel):
    headline: str = ""
    whyItMatters: str = ""
    immediateMove: str = ""
    generator: Literal["rules", "ai"] = "rules"
    confidence: GrowthConfidence = "low"


class GrowthGenericLessonRecord(BaseModel):
    id: str
    title: str
    judgment: str = ""
    applicableScene: str = ""
    whyItWorks: str = ""
    reuseHint: str = ""
    linkedContext: GrowthContextLinkRecord | None = None


class GrowthProjectGuidanceRecord(BaseModel):
    id: str
    title: str
    judgment: str = ""
    whySpecial: str = ""
    guidanceType: Literal["project_specific", "stage_risk", "context_gap"] = "project_specific"
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)


class GrowthReasoningInputRecord(BaseModel):
    id: str
    sourceType: Literal["task", "event_line", "client", "project_module", "project_flow", "focus_action", "pending_capture", "recommendation", "rule"] = "rule"
    label: str
    detail: str = ""


class GrowthReasoningTraceRecord(BaseModel):
    mode: Literal["rules_only", "ai_synthesized"] = "rules_only"
    usedInputs: list[GrowthReasoningInputRecord] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    missingContext: list[str] = Field(default_factory=list)
    aiContribution: list[str] = Field(default_factory=list)
    modelLabel: str | None = None
    confidence: GrowthConfidence = "low"


class GrowthRobotAssistRecord(BaseModel):
    ready: bool = False
    canDelegate: list[str] = Field(default_factory=list)
    mustStayHuman: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)


class GrowthAfterActionCaptureRecord(BaseModel):
    title: str = ""
    summary: str = ""
    experienceType: str = ""
    recommendedWriteback: str = ""


class GrowthWorkbenchSupportCopyRecord(BaseModel):
    title: str = ""
    intro: str = ""
    bullets: list[str] = Field(default_factory=list)


class GrowthWorkbenchSnapshotRecord(BaseModel):
    tasks: list[GrowthWorkbenchTaskRecord] = Field(default_factory=list)
    activeTaskId: str | None = None
    learningSummary: GrowthLearningSummaryRecord = Field(default_factory=GrowthLearningSummaryRecord)
    genericLessons: list[GrowthGenericLessonRecord] = Field(default_factory=list)
    projectGuidance: list[GrowthProjectGuidanceRecord] = Field(default_factory=list)
    reasoningTrace: GrowthReasoningTraceRecord = Field(default_factory=GrowthReasoningTraceRecord)
    robotAssist: GrowthRobotAssistRecord = Field(default_factory=GrowthRobotAssistRecord)
    afterActionCapture: GrowthAfterActionCaptureRecord = Field(default_factory=GrowthAfterActionCaptureRecord)
    processSteps: list[GrowthWorkbenchStepRecord] = Field(default_factory=list)
    activeProcessId: str | None = None
    actionsBefore: list[GrowthWorkbenchActionRecord] = Field(default_factory=list)
    actionsDuring: list[GrowthWorkbenchActionRecord] = Field(default_factory=list)
    actionsAfter: list[GrowthWorkbenchActionRecord] = Field(default_factory=list)
    supportMaterials: list[GrowthWorkbenchMaterialRecord] = Field(default_factory=list)
    checklistItems: list[str] = Field(default_factory=list)
    supportCopy: GrowthWorkbenchSupportCopyRecord = Field(default_factory=GrowthWorkbenchSupportCopyRecord)
    robotPlan: list[str] = Field(default_factory=list)
    sourceMode: Literal["task", "growth_seed", "empty"] = "empty"
    scopeMode: Literal["global", "strategic"] | None = None
    scopeClientId: str | None = None
    scopeClientName: str | None = None
    updatedAt: str


class GrowthOverviewRecord(BaseModel):
    userId: str
    userName: str = ""
    totalXp: int
    weeklyXp: int
    weeklyBaseXp: int = 0
    weeklyPremiumXp: int = 0
    level: int
    stageLabel: str
    xpToNext: int
    rank: GrowthRankRecord
    abilities: list[GrowthAbilityScoreRecord] = Field(default_factory=list)
    recentEntries: list[XpLedgerEntryRecord] = Field(default_factory=list)
    recommendations: list[LearningRecommendationRecord] = Field(default_factory=list)
    sourceCoverage: GrowthSourceCoverageRecord = Field(default_factory=GrowthSourceCoverageRecord)
    projectGrowthHighlights: list[GrowthProjectHighlightRecord] = Field(default_factory=list)
    eventLineGrowthHighlights: list[GrowthProjectHighlightRecord] = Field(default_factory=list)
    strategicAlignmentHighlights: list[GrowthProjectHighlightRecord] = Field(default_factory=list)
    pendingCaptures: list[GrowthPendingCaptureRecord] = Field(default_factory=list)
    currentFocusActions: list[GrowthFocusActionRecord] = Field(default_factory=list)
    abilityGaps: list[GrowthAbilityGapRecord] = Field(default_factory=list)
    updatedAt: str


class GrowthLedgerResponse(BaseModel):
    entries: list[XpLedgerEntryRecord] = Field(default_factory=list)


class GrowthRecommendationDismissPayload(BaseModel):
    reason: str = ""


class GrowthRecommendationActionResponse(BaseModel):
    recommendation: LearningRecommendationRecord
    task: TaskRecord | None = None


class GrowthValidationPayload(BaseModel):
    note: str = ""
    sourceType: str = "handbook_manual_reuse"
    sourceId: str | None = None
    sourceLabel: str = ""
    contextSummary: str = ""
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)


class GrowthValidationActionResponse(BaseModel):
    entryId: str
    eventType: Literal["handbook_reused"] = "handbook_reused"
    gainedXp: int = 0
    createdEntries: int = 0
    validationState: GrowthValidationState = "candidate"
    duplicate: bool = False
    sourceId: str
    createdAt: str


GrowthPendingCaptureState = Literal["open", "dismissed", "reviewed", "promoted"]


class GrowthPendingCaptureActionPayload(BaseModel):
    status: GrowthPendingCaptureState
    reason: str = ""
    handbookEntryId: str | None = None


class GrowthPendingCaptureActionResponse(BaseModel):
    capture: GrowthPendingCaptureRecord


class BadgeActionLinkRecord(BaseModel):
    label: str
    tab: str


class BadgeEvidenceRecord(BaseModel):
    id: str
    title: str
    sourceType: str
    sourceId: str
    subtitle: str = ""
    occurredAt: str


class BadgeProgressRecord(BaseModel):
    id: str
    code: str
    name: str
    categoryId: str
    categoryLabel: str
    abilityKey: GrowthAbilityKey
    abilityLabel: str
    roles: list[str] = Field(default_factory=list)
    xp: int
    iconMotif: str
    description: str
    whyItMatters: str
    systemHowText: str
    state: BadgeState
    progressValue: float = 0
    progressTarget: float = 0
    progressPercent: int = 0
    progressText: str = ""
    nextActionText: str = ""
    actionLinks: list[BadgeActionLinkRecord] = Field(default_factory=list)
    evidence: list[BadgeEvidenceRecord] = Field(default_factory=list)
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    missingSignals: list[str] = Field(default_factory=list)
    unlockedAt: str | None = None
    masteryLevel: int = 0
    historical: bool = False


class BadgeCategoryRecord(BaseModel):
    id: str
    label: str
    abilityKey: GrowthAbilityKey
    abilityLabel: str
    litCount: int = 0
    totalCount: int = 0
    badges: list[BadgeProgressRecord] = Field(default_factory=list)


class BadgeBoardOverviewRecord(BaseModel):
    totalBadges: int
    litBadges: int
    readyBadges: int
    inProgressBadges: int
    monthlyNewBadges: int
    totalXp: int
    upcomingBadgeIds: list[str] = Field(default_factory=list)


class BadgeBoardResponse(BaseModel):
    overview: BadgeBoardOverviewRecord
    categories: list[BadgeCategoryRecord] = Field(default_factory=list)
    updatedAt: str


class WeeklyReviewPayload(BaseModel):
    weekLabel: str
    taskEntries: list[dict[str, object]] = Field(default_factory=list)
    workProgress: str = ""
    workBlocker: str = ""
    blockerType: str = ""
    workDirection: str = ""
    nextWeekFocus: str = ""
    supportNeeded: str = ""
    relatedPlanIds: list[str] = Field(default_factory=list)
    workFreeNote: str = ""
    personalGrowthNote: str = ""
    personalPrivateNote: str = ""


class AgentWorklogRecord(BaseModel):
    id: str
    agentKey: AgentDepartmentKey
    agentName: str
    departmentName: str
    color: str
    date: str
    weekLabel: str
    title: str
    summary: str
    detailLines: list[str] = Field(default_factory=list)
    sourceType: Literal["activity_log", "topic_capture", "workspace_sync"]
    createdAt: str


class AgentWeeklyDigestRecord(BaseModel):
    agentKey: AgentDepartmentKey
    agentName: str
    departmentName: str
    color: str
    weekLabel: str
    summary: str
    focusItems: list[str] = Field(default_factory=list)
    evidenceCount: int = 0
    sourcePolicy: dict[str, object] = Field(default_factory=dict)


class AgentWeeklyPlanItemRecord(BaseModel):
    id: str
    title: str
    rationale: str = ""
    scheduleHint: str = ""
    status: Literal["planned", "doing", "done", "blocked"] = "planned"


class AgentWeeklyPlanRecord(BaseModel):
    agentKey: AgentDepartmentKey
    agentName: str
    departmentName: str
    color: str
    weekLabel: str
    summary: str
    planItems: list[AgentWeeklyPlanItemRecord] = Field(default_factory=list)
    sourcePolicy: dict[str, object] = Field(default_factory=dict)


class AgentWeeklyPlanItemPayload(BaseModel):
    title: str
    rationale: str = ""
    scheduleHint: str = ""
    status: Literal["planned", "doing", "done", "blocked"] = "planned"


class AgentWeeklyPlanPayload(BaseModel):
    weekLabel: str
    agentKey: AgentDepartmentKey
    summary: str = ""
    planItems: list[AgentWeeklyPlanItemPayload] = Field(default_factory=list)


class AgentWorklogResponse(BaseModel):
    month: str
    worklogs: list[AgentWorklogRecord] = Field(default_factory=list)
    weeklyDigests: list[AgentWeeklyDigestRecord] = Field(default_factory=list)
    weeklyPlans: list[AgentWeeklyPlanRecord] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    currentReview: WeeklyReviewRecord | None = None
    workItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    personalItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    workAnalysis: WeeklyReviewAnalysisRecord | None = None
    personalAnalysis: WeeklyReviewAnalysisRecord | None = None
    selfReport: HierarchyReportRecord | None = None
    workSignalCard: ManagementSignalCardRecord | None = None
    personalGrowthCard: PersonalGrowthCardRecord | None = None
    teamReport: HierarchyReportRecord | None = None
    orgReport: HierarchyReportRecord | None = None
    executiveOrgReport: HierarchyReportRecord | None = None
    departmentReports: list[HierarchyReportRecord] = Field(default_factory=list)
    agentDepartmentDigests: list[AgentWeeklyDigestRecord] = Field(default_factory=list)
    agentDepartmentPlans: list[AgentWeeklyPlanRecord] = Field(default_factory=list)
    simulationBundle: ReviewSimulationBundleRecord | None = None
    plans: list[PlanNodeRecord] = Field(default_factory=list)


class ReviewHistoryEntryRecord(BaseModel):
    weekLabel: str
    submittedAt: str
    workItemCount: int = 0
    personalItemCount: int = 0


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryEntryRecord] = Field(default_factory=list)


class TopicRadarRecord(BaseModel):
    id: str
    title: str
    prompt: str
    timeRange: str
    preferredSources: list["TopicRadarPreferredSourceRecord"] = Field(default_factory=list)
    createdAt: str


class TopicRadarPreferredSourceRecord(BaseModel):
    url: str
    label: str


class TopicRadarPayload(BaseModel):
    title: str
    prompt: str
    timeRange: str = "3_days"
    preferredSources: list[TopicRadarPreferredSourceRecord] = Field(default_factory=list)


class TopicTitlePayload(BaseModel):
    prompt: str


class TitleSuggestionResponse(BaseModel):
    title: str


class TopicRadarAssistPayload(BaseModel):
    prompt: str
    timeRange: str = "3_days"


class TopicRadarAssistResponse(BaseModel):
    title: str
    prompt: str
    queries: list[str] = Field(default_factory=list)


class TopicRadarSourceLabelPayload(BaseModel):
    url: str


class TopicRadarSourceLabelResponse(BaseModel):
    url: str
    label: str


class TopicCandidateRecord(BaseModel):
    id: str
    radarId: str
    title: str
    summary: str
    source: str
    sourceUrl: str | None = None
    publishedAt: str | None = None
    captureMethod: str = "manual"
    capturedBy: str | None = None
    status: TopicCandidateStatus
    insightStatus: TopicCandidateInsightStatus = "pending"
    insightUpdatedAt: str | None = None
    createdAt: str


class TopicCandidatePayload(BaseModel):
    radarId: str
    title: str
    summary: str
    source: str


class TopicCandidateInsightRecord(BaseModel):
    candidateId: str
    overview: str = ""
    keyPoints: list[str] = Field(default_factory=list)
    recommendationReasons: list[str] = Field(default_factory=list)
    practicalUses: list[str] = Field(default_factory=list)
    editorialNote: str = ""
    discussionPrompts: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class TopicCandidateChatMessageRecord(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    createdAt: str


class TopicCandidateChatPayload(BaseModel):
    question: str
    history: list[TopicCandidateChatMessageRecord] = Field(default_factory=list)


class TopicCandidateChatResponse(BaseModel):
    candidateId: str
    question: str
    answer: str
    generatedAt: str
    message: TopicCandidateChatMessageRecord


class TopicsResponse(BaseModel):
    radars: list[TopicRadarRecord]
    candidates: list[TopicCandidateRecord]


class TopicCaptureRunRecord(BaseModel):
    radarId: str
    radarTitle: str
    query: str
    fetchedCount: int
    createdCount: int
    skippedCount: int
    candidates: list[TopicCandidateRecord] = Field(default_factory=list)


class TopicCaptureBatchResponse(BaseModel):
    runs: list[TopicCaptureRunRecord] = Field(default_factory=list)
    totalCreated: int = 0
    totalSkipped: int = 0


class TopicTaskSuggestionRecord(BaseModel):
    title: str
    desc: str = ""
    dueDate: str | None = None
    ddl: str = ""
    note: str = ""
    priority: Priority = "normal"
    tags: list[str] = Field(default_factory=list)


class TopicTaskPlanResponse(BaseModel):
    candidateId: str
    candidateTitle: str
    candidateSummary: str
    candidateSource: str
    candidateSourceUrl: str | None = None
    overview: str = ""
    tasks: list[TopicTaskSuggestionRecord] = Field(default_factory=list)


class TopicTaskDraftPayload(BaseModel):
    title: str
    desc: str = ""
    priority: Priority = "normal"
    listId: str
    dueDate: str | None = None
    ddl: str = ""
    ownerId: str | None = None
    ownerName: str = ""
    collaboratorIds: list[str] = Field(default_factory=list)
    tagIds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    note: str = ""


class TopicTaskPromotionPayload(BaseModel):
    tasks: list[TopicTaskDraftPayload] = Field(default_factory=list)


class TopicTaskPromotionResponse(BaseModel):
    tasks: list[TaskRecord] = Field(default_factory=list)
    createdCount: int = 0


class AnalysisTemplateRecord(BaseModel):
    id: str
    title: str
    description: str
    templateKey: str


class AnalysisRunRecord(BaseModel):
    id: str
    templateId: str
    title: str
    inputText: str
    output: AiStructuredResponse
    parentRunId: str | None = None
    coachPayload: CoachPayload | None = None
    createdAt: str
    status: Literal["success", "failed"]


class AnalysisToolsResponse(BaseModel):
    templates: list[AnalysisTemplateRecord]
    runs: list[AnalysisRunRecord]


class AnalysisRunPayload(BaseModel):
    templateId: str
    title: str
    inputText: str
    parentRunId: str | None = None


class HandbookEntryRecord(BaseModel):
    id: str
    title: str
    summary: str
    tags: list[str]
    sourceType: str
    clientId: str | None = None
    clientName: str | None = None
    authorUserId: str | None = None
    authorUserName: str | None = None
    sourceObjectType: str | None = None
    sourceObjectId: str | None = None
    sourceTitle: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectModuleId: str | None = None
    projectModuleName: str | None = None
    projectFlowId: str | None = None
    projectFlowName: str | None = None
    projectStage: str | None = None
    businessCategory: str | None = None
    abilityKeys: list[GrowthAbilityKey] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    contextSummary: str = ""
    reuseCount: int = 0
    lastReusedAt: str | None = None
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    createdAt: str


class HandbookPayload(BaseModel):
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    sourceType: str
    clientId: str | None = None
    sourceObjectType: str | None = None
    sourceObjectId: str | None = None
    sourceTitle: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectModuleId: str | None = None
    projectModuleName: str | None = None
    projectFlowId: str | None = None
    projectFlowName: str | None = None
    projectStage: str | None = None
    businessCategory: str | None = None
    abilityKeys: list[GrowthAbilityKey] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    contextSummary: str = ""


class HandbookResponse(BaseModel):
    entries: list[HandbookEntryRecord]


class HandbookReuseRecord(BaseModel):
    id: str
    sourceType: str
    sourceId: str
    sourceLabel: str
    note: str = ""
    contextSummary: str = ""
    gainedXp: int = 0
    createdAt: str
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)


class HandbookEntryDetailRecord(HandbookEntryRecord):
    relatedLedgerEntries: list[XpLedgerEntryRecord] = Field(default_factory=list)
    originContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    reuseHistory: list[HandbookReuseRecord] = Field(default_factory=list)


class FileReclassEventRecord(BaseModel):
    id: str
    knowledgeDocumentId: str
    fromPath: str
    toPath: str
    fromCategory: str | None = None
    toCategory: str
    reason: str
    confidence: float
    createdAt: str


class KnowledgeJobRecord(BaseModel):
    id: str
    clientId: str
    jobType: str
    status: Literal["queued", "running", "completed", "failed"]
    totalItems: int
    processedItems: int
    lastError: str | None = None
    createdAt: str
    startedAt: str | None = None
    finishedAt: str | None = None
    updatedAt: str


class KnowledgeSearchHitRecord(BaseModel):
    title: str
    excerpt: str
    score: float
    stage: Literal["master_index", "surrogate", "raw_chunk"]
    path: str | None = None
    sectionLabel: str | None = None
    matchedTerms: list[str] = Field(default_factory=list)


class KnowledgeSearchResponse(BaseModel):
    searchId: str
    clientId: str
    query: str
    coverage: float
    matchedTerms: list[str] = Field(default_factory=list)
    masterHitCount: int = 0
    surrogateHitCount: int = 0
    rawChunkHitCount: int = 0
    drillthroughUsed: bool = False
    strategicMode: bool = False
    categoryCoverage: list[str] = Field(default_factory=list)
    preferredCategories: list[str] = Field(default_factory=list)
    phase: Literal["retrieving", "grounding", "generating", "completed", "failed"] = "retrieving"
    progress: float = 0.0
    progressFloor: float = 0.0
    progressCeiling: float = 25.0
    stageLabel: str | None = None
    lastUpdatedAt: str | None = None
    failureReason: str | None = None
    hits: list[KnowledgeSearchHitRecord] = Field(default_factory=list)
    previewSummary: str | None = None


class ClientAnalysisEvidenceSummaryRecord(BaseModel):
    summaryText: str = ""
    masterHitCount: int = 0
    surrogateHitCount: int = 0
    rawChunkHitCount: int = 0
    drillthroughUsed: bool = False
    coveredCategories: list[str] = Field(default_factory=list)
    missingCategories: list[str] = Field(default_factory=list)
    evidenceList: list[KnowledgeSearchHitRecord] = Field(default_factory=list)


class ClientAnalysisRunRecord(BaseModel):
    id: str
    clientId: str
    threadId: str
    userMessageId: str
    assistantMessageId: str
    question: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    phase: Literal["queued", "retrieving", "evidence_ready", "generating_long_answer", "generating_summary", "completed", "failed", "canceled"]
    progress: float = 0.0
    progressFloor: float = 0.0
    progressCeiling: float = 25.0
    stageLabel: str | None = None
    elapsedMs: float = 0.0
    evidenceSummary: ClientAnalysisEvidenceSummaryRecord = Field(default_factory=ClientAnalysisEvidenceSummaryRecord)
    longAnswerStatus: Literal["pending", "ready", "fallback", "failed"] = "pending"
    summaryStatus: Literal["pending", "ready", "fallback", "failed"] = "pending"
    longAnswer: str | None = None
    structuredSummary: AiStructuredResponse | None = None
    answerMode: Literal["grounded_answer", "grounded_fallback", "low_confidence_answer", "general_answer", "system_failure"] | None = None
    llmInvoked: bool = False
    providerUsed: str | None = None
    failureReason: str | None = None
    timing: dict[str, float] = Field(default_factory=dict)
    assistantMessage: ChatMessageRecord | None = None
    createdAt: str
    updatedAt: str


class AnalysisJobCreatePayload(BaseModel):
    jobType: AnalysisJobType
    clientId: str
    scopeType: AnalysisScopeType = "client"
    scopeId: str
    priority: Priority = "normal"
    triggerType: str = "manual"
    question: str = ""
    sourceScope: dict[str, list[str]] = Field(default_factory=dict)
    featureFlags: dict[str, bool] = Field(default_factory=dict)
    intentProfile: AnalysisIntentProfile = "client_overview"


class AnalysisJobStageRunRecord(BaseModel):
    id: str
    jobId: str
    stageName: str
    status: AnalysisStageStatus
    provider: str | None = None
    modelName: str | None = None
    lane: AnalysisLane = "cloud_final"
    cacheKey: str | None = None
    cacheHit: bool = False
    degraded: bool = False
    evidenceCount: int = 0
    topicCount: int = 0
    conflictCount: int = 0
    contextTimeRange: str | None = None
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    detail: str | None = None
    correlationId: str | None = None
    startedAt: str | None = None
    finishedAt: str | None = None
    createdAt: str
    updatedAt: str


class RuntimeRunLogRecord(BaseModel):
    id: str
    clientId: str
    jobId: str | None = None
    analysisJobId: str | None = None
    stageRunId: str | None = None
    contextPackId: str | None = None
    judgmentVersionId: str | None = None
    correlationId: str | None = None
    provider: str | None = None
    model: str | None = None
    lane: AnalysisLane = "cloud_final"
    cacheHit: bool = False
    degraded: bool = False
    documentCount: int = 0
    evidenceCount: int = 0
    conflictCount: int = 0
    contextTimeRange: str | None = None
    promptVersion: str | None = None
    schemaVersion: str | None = None
    summary: str = ""
    detail: dict[str, object] = Field(default_factory=dict)
    createdAt: str


class AnalysisJobRecord(BaseModel):
    id: str
    jobType: AnalysisJobType
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    status: AnalysisJobStatus
    priority: Priority = "normal"
    triggerType: str = "manual"
    intentProfile: AnalysisIntentProfile = "client_overview"
    question: str = ""
    sourceSnapshot: str = ""
    sourceSnapshotHash: str = ""
    dedupeKey: str = ""
    featureFlags: dict[str, bool] = Field(default_factory=dict)
    progress: float = 0.0
    stageLabel: str | None = None
    runLogId: str | None = None
    error: str | None = None
    lockedBy: str | None = None
    lockedAt: str | None = None
    lockExpiresAt: str | None = None
    attemptCount: int = 0
    lastError: str | None = None
    createdAt: str
    updatedAt: str
    startedAt: str | None = None
    finishedAt: str | None = None


class DocSkeletonRecord(BaseModel):
    id: str
    clientId: str
    documentId: str
    title: str
    outline: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    timeRange: str | None = None
    parserVersion: str = "analysis-center-v1"
    sourceSnapshot: str = ""
    createdAt: str
    updatedAt: str


class EvidenceCardRecord(BaseModel):
    id: str
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    sourceType: str
    sourceId: str
    sourceRef: str = ""
    quote: str
    normalizedClaim: str
    evidenceType: str = "general"
    polarity: Literal["support", "oppose", "neutral"] = "neutral"
    tags: list[str] = Field(default_factory=list)
    topicKeys: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    timeAnchor: str | None = None
    documentId: str | None = None
    eventLineId: str | None = None
    taskId: str | None = None
    meetingId: str | None = None
    moduleId: str | None = None
    flowId: str | None = None
    reviewState: AnalysisReviewState = "draft"
    fingerprint: str
    normalizedClaimHash: str = ""
    sourceRefHash: str = ""
    evidenceFingerprint: str = ""
    normalizerVersion: str = "analysis-center-v0.3.3"
    createdAt: str
    updatedAt: str


class ThemeClusterRecord(BaseModel):
    id: str
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    themeKey: str
    title: str
    supportIds: list[str] = Field(default_factory=list)
    opposeIds: list[str] = Field(default_factory=list)
    gapSummary: str = ""
    latestChangeSummary: str = ""
    evidenceCount: int = 0
    version: int = 1
    createdAt: str
    updatedAt: str


class ConflictGroupRecord(BaseModel):
    id: str
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    conflictType: str
    title: str
    summary: str
    evidenceIds: list[str] = Field(default_factory=list)
    unresolvedQuestionIds: list[str] = Field(default_factory=list)
    resolutionStatus: AnalysisReviewState = "draft"
    severity: Literal["low", "medium", "high"] = "medium"
    createdAt: str
    updatedAt: str


class OpenQuestionRecord(BaseModel):
    id: str
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    themeKey: str
    question: str
    reason: str = ""
    blockerLevel: Literal["low", "medium", "high"] = "medium"
    status: AnalysisReviewState = "draft"
    createdAt: str
    updatedAt: str


class ContextPackRecord(BaseModel):
    id: str
    clientId: str
    jobId: str | None = None
    targetType: AnalysisScopeType
    targetId: str
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    supersedesId: str | None = None
    sourceSnapshotHash: str = ""
    staleReason: AnalysisStaleReason | None = None
    invalidatedBy: str | None = None
    promptVersion: str = "analysis-center-v1"
    sourceCount: int = 0
    evidenceCount: int = 0
    payload: dict[str, object] = Field(default_factory=dict)
    staleAt: str | None = None
    createdAt: str
    updatedAt: str


class DnaDeltaRecord(BaseModel):
    id: str
    clientId: str
    dimension: str
    previousVersion: str | None = None
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    supersedesId: str | None = None
    sourceSnapshotHash: str = ""
    staleReason: AnalysisStaleReason | None = None
    invalidatedBy: str | None = None
    proposedChange: str
    summary: str = ""
    evidenceIds: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    status: AnalysisReviewState = "draft"
    contextPackId: str | None = None
    createdAt: str
    updatedAt: str


class DnaDeltaCreatePayload(BaseModel):
    clientId: str
    dimension: str
    proposedChange: str
    summary: str = ""
    evidenceIds: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    contextPackId: str | None = None


class JudgmentVersionRecord(BaseModel):
    id: str
    clientId: str
    targetType: AnalysisScopeType
    targetId: str
    topic: str
    version: int = 1
    status: AnalysisReviewState = "draft"
    originType: AnalysisOriginType = "projection"
    authorityLevel: AnalysisAuthorityLevel = "fallback"
    qualityTier: AnalysisQualityTier = "legacy"
    supersedesId: str | None = None
    sourceSnapshotHash: str = ""
    staleReason: AnalysisStaleReason | None = None
    invalidatedBy: str | None = None
    summary: str
    evidenceIds: list[str] = Field(default_factory=list)
    contextPackId: str | None = None
    riskLevel: Literal["low", "medium", "high"] = "medium"
    confidence: Literal["low", "medium", "high"] = "medium"
    createdAt: str
    updatedAt: str


class JudgmentConfirmPayload(BaseModel):
    judgmentId: str
    action: ApprovalDecision
    note: str = ""


class ApprovalDecisionPayload(BaseModel):
    targetType: ApprovalTargetType
    targetId: str
    decision: ApprovalDecision
    comment: str = ""
    policyType: str = "analysis_review"
    metadata: dict[str, object] = Field(default_factory=dict)


class ApprovalRecordRecord(BaseModel):
    id: str
    approvalTargetType: ApprovalTargetType
    approvalTargetId: str
    clientId: str
    policyType: str = "analysis_review"
    decision: ApprovalDecision
    comment: str = ""
    decidedBy: str = ""
    decidedAt: str
    metadata: dict[str, object] = Field(default_factory=dict)


class ApprovalStateRecord(BaseModel):
    targetType: ApprovalTargetType
    targetId: str
    currentDecision: ApprovalDecision | None = None
    currentStatus: AnalysisReviewState | None = None
    lastApproval: ApprovalRecordRecord | None = None


class ResolutionScopeRecord(BaseModel):
    scopeType: AnalysisScopeType
    scopeId: str


class ResolutionCandidateRecord(BaseModel):
    objectId: str | None = None
    topic: str | None = None
    scopeType: AnalysisScopeType
    scopeId: str
    originType: AnalysisOriginType | None = None
    authorityLevel: AnalysisAuthorityLevel | None = None
    qualityTier: AnalysisQualityTier | None = None
    staleReason: AnalysisStaleReason | None = None
    status: AnalysisReviewState | None = None
    rejectedReason: AnalysisRejectedReason | None = None


class ResolutionTraceRecord(BaseModel):
    selectedCandidate: ResolutionCandidateRecord | None = None
    consideredCandidates: list[ResolutionCandidateRecord] = Field(default_factory=list)
    requestedScope: ResolutionScopeRecord
    resolvedScope: ResolutionScopeRecord | None = None
    writebackScope: ResolutionScopeRecord
    fallbackUsed: bool = False
    fallbackReason: str | None = None


class JudgmentBundleRecord(BaseModel):
    baselineJudgment: JudgmentVersionRecord | None = None
    overlayDeltas: list[JudgmentVersionRecord] = Field(default_factory=list)
    resolutionTrace: ResolutionTraceRecord


class AnalysisMigrationMetricsRecord(BaseModel):
    windowDays: int = 7
    newObjectHitRate: float = 0.0
    fallbackRate: float = 0.0
    approvalBacklog: int = 0
    approvalLagHoursMedian: float = 0.0
    candidateReviewWarningCount: int = 0
    candidateReviewOverdueCount: int = 0
    newCandidateUnreviewed24h: int = 0
    candidateToApprovedConversionRate: float = 0.0
    staleApprovedJudgmentCount: int = 0
    resolverMismatchRate: float = 0.0
    pageBreakdown: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class AnalysisCenterSummaryRecord(BaseModel):
    clientId: str
    evidenceCardCount: int = 0
    themeClusterCount: int = 0
    conflictGroupCount: int = 0
    openQuestionCount: int = 0
    draftJudgmentCount: int = 0
    approvedJudgmentCount: int = 0
    analysisJobCount: int = 0
    latestJobStatus: AnalysisJobStatus | None = None
    latestJobLabel: str | None = None
    latestContextPackUpdatedAt: str | None = None
    latestRunLogId: str | None = None
    latestRunSummary: str | None = None


class AnalysisBackfillMainChainPayload(BaseModel):
    clientIds: list[str] = Field(default_factory=list)
    dryRun: bool = False
    batchSize: int = 20
    maxJobs: int = 100
    pauseRequested: bool = False


class AnalysisBackfillMainChainJobRecord(BaseModel):
    clientId: str
    scopeType: AnalysisScopeType
    scopeId: str
    jobType: AnalysisJobType = "strategy_pack"
    triggerType: str = "backfill"
    intentProfile: AnalysisIntentProfile = "client_overview"


class AnalysisBackfillMainChainResultRecord(BaseModel):
    dryRun: bool = False
    pauseRequested: bool = False
    paused: bool = False
    scannedClients: int = 0
    queuedJobs: int = 0
    skippedJobs: int = 0
    candidates: list[AnalysisBackfillMainChainJobRecord] = Field(default_factory=list)


class ClientWorkspaceResponse(BaseModel):
    client: ClientSummary
    folders: list[ClientFolder]
    documents: list[DocumentRecord]
    documentCards: list[DocumentCardRecord] = Field(default_factory=list)
    imports: list[ImportRecord]
    knowledgeStatus: KnowledgeStatusRecord | None = None
    knowledgeJobs: list[KnowledgeJobRecord] = Field(default_factory=list)
    recentReclassEvents: list[FileReclassEventRecord] = Field(default_factory=list)
    surrogateCount: int = 0
    memoryDocCount: int = 0
    threads: list[ChatThread]
    recentMessages: list[ChatMessageRecord]
    analysisRuns: list[ClientAnalysisRunRecord] = Field(default_factory=list)
    meetings: list[MeetingSummary]
    goals: list[GoalRecord]
    dnaModules: list[ClientDnaModuleRecord] = Field(default_factory=list)
    projectModules: list[ProjectModuleRecord] = Field(default_factory=list)
    projectFlows: list[ProjectFlowRecord] = Field(default_factory=list)
    dnaTerms: list[DnaTerm]
    relatedTasks: list[TaskRecord]
    notebookSummary: OrganizationNotebookSnapshot | None = None
    memoryStatus: MemoryStatus | None = None
    analysisCenter: AnalysisCenterSummaryRecord | None = None
    latestContextPack: ContextPackRecord | None = None
    judgmentBundle: JudgmentBundleRecord | None = None
    latestResolutionTrace: ResolutionTraceRecord | None = None
    latestJudgments: list[JudgmentVersionRecord] = Field(default_factory=list)
    latestTopics: list[ThemeClusterRecord] = Field(default_factory=list)
    latestConflicts: list[ConflictGroupRecord] = Field(default_factory=list)
    latestOpenQuestions: list[OpenQuestionRecord] = Field(default_factory=list)
    latestRunLogs: list[RuntimeRunLogRecord] = Field(default_factory=list)
    stateProjection: WorkspaceStateProjectionRecord | None = None


class ClientNotebookResponse(BaseModel):
    organizationNotebookSnapshot: OrganizationNotebookSnapshot | None = None
    keyFacts: list[MemoryFact] = Field(default_factory=list)
    missingFacts: list[str] = Field(default_factory=list)
    linkedEventLines: list[EventLineRecord] = Field(default_factory=list)


class EventLineMemoryResponse(BaseModel):
    eventLineMemorySnapshot: EventLineMemorySnapshot | None = None
    evidenceRefs: list[str] = Field(default_factory=list)
    clarificationNeeds: list[str] = Field(default_factory=list)


class TaskViewFilterSetRecord(BaseModel):
    sourceTypes: list[str] = Field(default_factory=list)
    businessCategories: list[str] = Field(default_factory=list)
    eventLineIds: list[str] = Field(default_factory=list)
    onlyRisky: bool = False
    onlyWithEventLine: bool = False
    needsReview: bool | None = None
    minimumEvidenceCount: int | None = None


class TaskViewDefinitionRecord(BaseModel):
    id: str
    name: str
    kind: Literal["event_line", "risk", "source", "business_category", "custom"] = "custom"
    description: str
    calendarScope: Literal["all", "event_line", "risk", "source", "business_category"] = "all"
    shareability: Literal["private", "org"] = "private"
    sortBy: Literal["updatedAt", "dueDate", "priority", "evidenceCount"] = "updatedAt"
    sortDirection: Literal["asc", "desc"] = "desc"
    visibleFields: list[str] = Field(default_factory=list)
    filterSet: TaskViewFilterSetRecord = Field(default_factory=TaskViewFilterSetRecord)
    builtIn: bool = False
    createdAt: str
    updatedAt: str


class TaskViewPresetRecord(BaseModel):
    key: Literal["event_line", "risk", "source", "business_category"]
    label: str
    description: str
    viewId: str


class TaskViewsResponse(BaseModel):
    views: list[TaskViewDefinitionRecord] = Field(default_factory=list)
    presets: list[TaskViewPresetRecord] = Field(default_factory=list)


class TaskViewMutationPayload(BaseModel):
    name: str
    kind: Literal["event_line", "risk", "source", "business_category", "custom"] = "custom"
    description: str = ""
    calendarScope: Literal["all", "event_line", "risk", "source", "business_category"] = "all"
    shareability: Literal["private", "org"] = "private"
    sortBy: Literal["updatedAt", "dueDate", "priority", "evidenceCount"] = "updatedAt"
    sortDirection: Literal["asc", "desc"] = "desc"
    visibleFields: list[str] = Field(default_factory=list)
    filterSet: TaskViewFilterSetRecord = Field(default_factory=TaskViewFilterSetRecord)


class ReviewDashboardDrillTargetResponse(BaseModel):
    target: ReviewDashboardCardTargetRecord
    eventLineDetail: EventLineDetailRecord | None = None
    eventLineMemory: EventLineMemorySnapshot | None = None
    tasks: list[TaskRecord] = Field(default_factory=list)
    meetings: list[MeetingSummary] = Field(default_factory=list)
    supportRequests: list[SupportRequestRecord] = Field(default_factory=list)
    attachments: list[TaskAttachmentRecord] = Field(default_factory=list)


class ClarificationCreatePayload(BaseModel):
    scopeType: MemoryScopeType
    scopeId: str
    slotKey: str
    question: str
    writeScope: list[str] = Field(default_factory=list)
    reusable: bool = True


class ClarificationAnswerPayload(BaseModel):
    answer: str = ""


class VectorizeAnswerPayload(BaseModel):
    messageId: str


class ExportAnswerPayload(BaseModel):
    messageId: str


class ClientTemplateFillPayload(BaseModel):
    templatePath: str


class ClientTextDocumentPayload(BaseModel):
    title: str = ""
    content: str


class ClientTextDocumentResponse(BaseModel):
    clientId: str
    documentId: str
    title: str
    fileName: str
    path: str


class ClientTemplateFillFieldRecord(BaseModel):
    label: str
    value: str
    status: Literal["filled", "missing"]
    evidenceTitles: list[str] = Field(default_factory=list)
    webSourceTitles: list[str] = Field(default_factory=list)
    fieldType: Literal["precise_fact", "structural_summary", "governance_mechanism", "quantitative_result", "attachment_material", "general"] | None = None
    valueKind: Literal["fact", "summary", "inference", "missing"] | None = None
    confidence: float | None = None
    basisSummary: str | None = None
    followUpQuestion: str | None = None
    suggestedSources: list[str] = Field(default_factory=list)
    reviewRequired: bool = False


class ClientTemplateFillResponse(BaseModel):
    path: str
    fileName: str
    fieldCount: int
    filledCount: int
    missingCount: int
    reviewFieldCount: int = 0
    attachmentChecklist: list[str] = Field(default_factory=list)
    fields: list[ClientTemplateFillFieldRecord] = Field(default_factory=list)


class ClientTemplateFillRunRecord(BaseModel):
    id: str
    clientId: str
    templateName: str
    templatePath: str
    status: Literal["queued", "running", "completed", "failed"]
    phase: Literal["queued", "parsing", "retrieving", "writing", "completed", "failed"]
    progress: float = 0.0
    stageLabel: str | None = None
    elapsedMs: float = 0.0
    fieldCount: int = 0
    processedCount: int = 0
    filledCount: int = 0
    missingCount: int = 0
    reviewFieldCount: int = 0
    currentFieldLabel: str | None = None
    evidenceTitles: list[str] = Field(default_factory=list)
    attachmentChecklist: list[str] = Field(default_factory=list)
    fields: list[ClientTemplateFillFieldRecord] = Field(default_factory=list)
    outputPath: str | None = None
    errorMessage: str | None = None
    createdAt: str
    updatedAt: str


class KnowledgeMemoryRecord(BaseModel):
    id: str
    clientId: str
    sourceType: str
    title: str
    folderCategory: str
    surrogateMdPath: str
    createdAt: str
    updatedAt: str


# ── UnderstandingSnapshotV1: 统一理解输出对象 ──


class UnderstandingSourceBreakdownRecord(BaseModel):
    sourceType: str
    available: bool = False
    label: str = ""


class UnderstandingOptionalAdviceRecord(BaseModel):
    realBlocker: str | None = None
    timeGate: str | None = None
    minimumAction: str | None = None
    supportAsk: str | None = None


class UnderstandingSnapshotV1Record(BaseModel):
    taskId: str
    mode: Literal["basic", "enhanced"] = "basic"
    coverage: int = 0
    confidence: int = 0
    whatIsThis: str = ""
    whyItMatters: str = ""
    progressNow: str = ""
    unknowns: str = ""
    knownFacts: list[str] = Field(default_factory=list)
    optionalAdvice: UnderstandingOptionalAdviceRecord | None = None
    sourceBreakdown: list[UnderstandingSourceBreakdownRecord] = Field(default_factory=list)


# ── Phase 1: 客户战略画像 + 合作关系 + 事件线周历史 ──


class ClientStrategicProfileRecord(BaseModel):
    clientId: str
    industry: str = ""
    scale: str = ""
    influence: str = ""
    currentNeeds: str = ""
    painPoints: str = ""
    strategicValueToYiyu: str = ""
    decisionChain: str = ""
    updatedAt: str = ""


class CooperationStakeholderRecord(BaseModel):
    name: str
    role: str = ""
    relationship: str = ""


class CooperationRelationshipRecord(BaseModel):
    id: str
    clientId: str
    clientName: str = ""
    whyConnected: str = ""
    meaningToYiyu: str = ""
    meaningToClient: str = ""
    cooperationType: Literal["strategic_companion", "single_project", "exploring", "dormant"] = "exploring"
    relationshipHealth: Literal["thriving", "steady", "cooling", "at_risk"] = "steady"
    keyStakeholders: list[CooperationStakeholderRecord] = Field(default_factory=list)
    milestones: str = ""
    startedAt: str = ""
    updatedAt: str = ""


class EventLineWeeklySnapshotRecord(BaseModel):
    id: str
    eventLineId: str
    eventLineName: str = ""
    weekLabel: str
    stageAtThatTime: str = ""
    keyDecisions: list[str] = Field(default_factory=list)
    turningPoints: list[str] = Field(default_factory=list)
    blockersThen: list[str] = Field(default_factory=list)
    progressDelta: str = ""
    taskCount: int = 0
    completedCount: int = 0
    createdAt: str = ""


class NarrativeAnalysisRecord(BaseModel):
    eventLineId: str
    eventLineName: str = ""
    clientId: str | None = None
    clientName: str | None = None
    whatThisIs: str = ""
    whyImportant: str = ""
    currentProgress: str = ""
    missingUnderstanding: str = ""
    riskNote: str | None = None
    timeGate: str | None = None
    minimumAction: str | None = None
    managementAdvice: str | None = None
    contextLayersUsed: list[str] = Field(default_factory=list)
    confidenceLevel: Literal["low", "medium", "high"] = "low"
~~~

## `backend/app/services/__init__.py`

- 编码: `utf-8`

~~~python
"""服务层包。"""

~~~

## `backend/app/services/agent_worklogs.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from app.db import Database
from app.services.knowledge_base import tokenize
from app.models import (
    TaskTagRecord,
    TaskRecord,
    TaskCollaboratorRecord,
    TaskActivityRecord,
    AgentWeeklyPlanItemPayload,
    AgentWeeklyPlanItemRecord,
    AgentWeeklyPlanPayload,
    AgentWeeklyPlanRecord,
    AgentWorklogRecord,
    AgentWorklogResponse,
    AgentWeeklyDigestRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)


AGENT_DEPARTMENTS = {
    "strategy_design": {
        "agentName": "庆华",
        "departmentName": "咨询策略部",
        "color": "#5B7BFE",
        "sourceType": "activity_log",
    },
    "tech_development": {
        "agentName": "佳乐",
        "departmentName": "科技发展部",
        "color": "#F59E0B",
        "sourceType": "workspace_sync",
    },
    "info_data": {
        "agentName": "大周",
        "departmentName": "信息数据部",
        "color": "#10B981",
        "sourceType": "topic_capture",
    },
}

DONE_KEYWORDS = ("已完成", "完成", "收束", "发布", "提交", "验收通过", "关闭", "解决")
BLOCKER_KEYWORDS = ("风险", "阻塞", "卡住", "未完成", "待确认", "仍需", "问题", "阻力", "失败", "回退")

AGENT_TASK_TAGS = {
    "strategy_design": ("战略设计", "#5B7BFE"),
    "tech_development": ("软件系统", "#F59E0B"),
    "info_data": ("信息情报", "#10B981"),
}

AGENT_AUTO_SOURCE_TYPE = "agent_auto"


def _month_bounds(month_label: str) -> tuple[date, date]:
    try:
        year, month = month_label.split("-", 1)
        month_start = date(int(year), int(month), 1)
    except Exception as exc:
        raise ValueError(f"Invalid month label: {month_label}") from exc
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month - timedelta(days=1)


def _week_bounds(week_label: str) -> tuple[date, date]:
    match = re.match(r"^(\d{4})-W(\d{2})$", week_label.strip())
    if not match:
        raise ValueError(f"Invalid week label: {week_label}")
    year = int(match.group(1))
    week = int(match.group(2))
    week_start = date.fromisocalendar(year, week, 1)
    return week_start, week_start + timedelta(days=6)


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _week_label(value: date) -> str:
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _humanize_action(action: str) -> str:
    mapping = {
        "task.create": "新建任务",
        "task.update": "更新任务",
        "task.confirm": "确认任务",
        "task.note.update": "补充任务说明",
        "review.create": "提交周复盘",
        "meeting.publish": "发布会议任务",
        "meeting.resolve": "整理会议结论",
        "settings.review_governance.update": "调整复盘治理",
        "settings.tasks.update": "调整任务设置",
    }
    return mapping.get(action, action.replace(".", " / "))


def _parse_json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _status_keyword_match(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _clean_text(text)
    return any(keyword in normalized for keyword in keywords)


def _entry_match_score(item_tokens: set[str], entry: AgentWorklogRecord) -> int:
    if not item_tokens:
        return 0
    entry_tokens = set(tokenize(" ".join([entry.title, entry.summary, *entry.detailLines])))
    overlap = item_tokens & entry_tokens
    if overlap:
        return len(overlap)
    normalized_item = re.sub(r"\s+", "", " ".join(item_tokens))
    normalized_entry = re.sub(r"\s+", "", " ".join([entry.title, entry.summary, *entry.detailLines]))
    if normalized_item and normalized_item in normalized_entry:
        return 1
    return 0


def _infer_plan_item_status(item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord]) -> str:
    item_tokens = set(tokenize(" ".join([item.title, item.rationale, item.scheduleHint])))
    matched_entries = [
        entry for entry in entries
        if _entry_match_score(item_tokens, entry) > 0
    ]
    if not matched_entries:
        return item.status
    joined_text = " ".join(
        " ".join([entry.title, entry.summary, *entry.detailLines])
        for entry in matched_entries
    )
    if _status_keyword_match(joined_text, BLOCKER_KEYWORDS):
        return "blocked"
    if _status_keyword_match(joined_text, DONE_KEYWORDS):
        return "done"
    return "doing"


def _agent_task_tag(agent_key: str) -> TaskTagRecord:
    label, color = AGENT_TASK_TAGS.get(agent_key, ("机器人工作", "#64748B"))
    return TaskTagRecord(
        id=f"agent_tag_{agent_key}",
        name=label,
        color=color,
        scope="org",
        updatedAt=datetime.now().replace(microsecond=0).isoformat(),
    )


def _plan_status_to_task_status(status: str) -> str:
    if status == "done":
        return "done"
    if status in {"doing", "blocked"}:
        return "doing"
    return "todo"


def _plan_status_to_completion_status(status: str) -> str:
    if status == "done":
        return "done_on_time"
    if status == "blocked":
        return "not_done"
    if status == "doing":
        return "in_progress"
    return "in_progress"


def _compose_agent_progress(plan_item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord], digest: AgentWeeklyDigestRecord) -> str:
    if entries:
        evidence_titles = "、".join(entry.title for entry in entries[:2])
        return f"本周围绕「{plan_item.title}」已有自动工作痕迹：{evidence_titles}。"
    return digest.summary


def _compose_agent_success_experience(entries: list[AgentWorklogRecord]) -> str:
    if not entries:
        return ""
    for entry in entries:
        joined = " ".join([entry.title, entry.summary, *entry.detailLines])
        if _status_keyword_match(joined, DONE_KEYWORDS):
            return _clean_text(entry.summary or entry.title)
    return _clean_text(entries[0].summary)


def _compose_agent_failure_insight(entries: list[AgentWorklogRecord]) -> str:
    if not entries:
        return ""
    for entry in entries:
        joined = " ".join([entry.title, entry.summary, *entry.detailLines])
        if _status_keyword_match(joined, BLOCKER_KEYWORDS):
            return _clean_text(entry.summary or entry.title)
    return _clean_text(entries[0].summary)


def _agent_due_label(week_end: date, schedule_hint: str) -> str:
    hint = _clean_text(schedule_hint)
    return hint or week_end.isoformat()


def _default_task_list_id(db: Database) -> str:
    row = db.fetchone(
        "SELECT id FROM task_lists WHERE is_default = 1 ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1"
    )
    if row:
        return str(row["id"])
    fallback = db.fetchone("SELECT id FROM task_lists ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1")
    if fallback:
        return str(fallback["id"])
    raise ValueError("No task list configured for agent tasks")


def _parse_agent_task_identity(task_id: str) -> tuple[str, str, int] | None:
    match = re.match(r"^agent_task_([a-z_]+)_(\d{4}-W\d{2})_(\d+)$", task_id)
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _agent_auto_source_id(week_label: str, agent_key: str, item_index: int) -> str:
    return f"{week_label}::{agent_key}::{item_index}"


def _matched_entries_for_plan_item(plan_item: AgentWeeklyPlanItemRecord, entries: list[AgentWorklogRecord]) -> list[AgentWorklogRecord]:
    item_tokens = set(tokenize(" ".join([plan_item.title, plan_item.rationale, plan_item.scheduleHint])))
    return [
        entry for entry in entries
        if _entry_match_score(item_tokens, entry) > 0
    ]


def _build_qinghua_logs(db: Database, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    rows = db.fetchall(
        """
        SELECT created_at, action, entity_type, detail_json
        FROM activity_logs
        WHERE actor_name = ?
        ORDER BY created_at DESC
        """,
        ("庆华",),
    )
    grouped: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        created_on = _to_date(str(row["created_at"]))
        if not created_on or created_on < month_start or created_on > month_end:
            continue
        grouped[created_on.isoformat()].append(row)

    config = AGENT_DEPARTMENTS["strategy_design"]
    entries: list[AgentWorklogRecord] = []
    for day in sorted(grouped.keys(), reverse=True):
        day_rows = grouped[day]
        action_labels = []
        for row in day_rows[:4]:
            detail = _parse_json_object(row["detail_json"])
            detail_title = _clean_text(str(detail.get("title") or detail.get("taskTitle") or ""))
            label = _humanize_action(str(row["action"]))
            action_labels.append(f"{label}：{detail_title}" if detail_title else label)
        summary = f"庆华这一天处理了 {len(day_rows)} 条战略侧内部动作，重点包括：{'、'.join(action_labels)}。"
        entries.append(
            AgentWorklogRecord(
                id=f"agent_qinghua_{day}",
                agentKey="strategy_design",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=day,
                weekLabel=_week_label(date.fromisoformat(day)),
                title=f"庆华当日处理了 {len(day_rows)} 条战略动作",
                summary=summary,
                detailLines=action_labels,
                sourceType="activity_log",
                createdAt=str(day_rows[0]["created_at"]),
            )
        )
    return entries


def _build_dazhou_logs(db: Database, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    rows = db.fetchall(
        """
        SELECT c.id, c.title, c.source, c.created_at, r.title AS radar_title
        FROM topic_candidates c
        LEFT JOIN topic_radars r ON r.id = c.radar_id
        WHERE c.captured_by = ?
        ORDER BY c.created_at DESC
        """,
        ("大周",),
    )
    grouped: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        created_on = _to_date(str(row["created_at"]))
        if not created_on or created_on < month_start or created_on > month_end:
            continue
        grouped[created_on.isoformat()].append(row)

    config = AGENT_DEPARTMENTS["info_data"]
    entries: list[AgentWorklogRecord] = []
    for day in sorted(grouped.keys(), reverse=True):
        day_rows = grouped[day]
        radar_titles = sorted({str(row["radar_title"] or "") for row in day_rows if str(row["radar_title"] or "").strip()})
        source_titles = [str(row["title"]) for row in day_rows[:3]]
        summary = (
            f"大周这一天新增 {len(day_rows)} 条情报线索。"
            + (f" 主要覆盖：{'、'.join(radar_titles[:3])}。" if radar_titles else "")
        )
        entries.append(
            AgentWorklogRecord(
                id=f"agent_dazhou_{day}",
                agentKey="info_data",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=day,
                weekLabel=_week_label(date.fromisoformat(day)),
                title=f"大周当日新增 {len(day_rows)} 条情报线索",
                summary=summary,
                detailLines=source_titles,
                sourceType="topic_capture",
                createdAt=str(day_rows[0]["created_at"]),
            )
        )
    return entries


def _extract_thread_sync_sections(path: Path) -> list[tuple[date, str, list[str]]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    sections: list[tuple[date, str, list[str]]] = []
    current_date: date | None = None
    current_title = ""
    current_lines: list[str] = []
    heading_pattern = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(.*)$")

    def flush() -> None:
        nonlocal current_date, current_title, current_lines
        if current_date is not None and current_lines:
            sections.append((current_date, current_title, current_lines[:]))
        current_date = None
        current_title = ""
        current_lines = []

    for line in content:
        heading_match = heading_pattern.match(line.strip())
        if heading_match:
            flush()
            current_date = date.fromisoformat(heading_match.group(1))
            current_title = heading_match.group(2).strip() or "系统同步"
            continue
        if current_date is not None:
            current_lines.append(line.rstrip())
    flush()
    return sections


def _section_summary_lines(lines: list[str]) -> tuple[str, list[str]]:
    cleaned = [
        _clean_text(re.sub(r"^-\s*", "", line.strip()))
        for line in lines
        if line.strip().startswith("- ")
    ]
    preferred = [
        item for item in cleaned
        if ("当前状态" in item or "已完成" in item or "开始" in item or "风险点" in item)
        and "验证结果" not in item
    ]
    detail_lines = preferred[:4] or cleaned[:4]
    summary = " ".join(detail_lines[:2]) if detail_lines else "今天有系统开发同步，但还没有整理成结构化说明。"
    return summary, detail_lines


def _build_jiale_logs(thread_sync_path: Path, month_start: date, month_end: date) -> list[AgentWorklogRecord]:
    sections = _extract_thread_sync_sections(thread_sync_path)
    config = AGENT_DEPARTMENTS["tech_development"]
    entries: list[AgentWorklogRecord] = []
    for section_date, title, lines in sections:
        if section_date < month_start or section_date > month_end:
            continue
        summary, detail_lines = _section_summary_lines(lines)
        entries.append(
            AgentWorklogRecord(
                id=f"agent_jiale_{section_date.isoformat()}_{abs(hash(title)) % 10000}",
                agentKey="tech_development",
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                date=section_date.isoformat(),
                weekLabel=_week_label(section_date),
                title=title,
                summary=summary,
                detailLines=detail_lines,
                sourceType="workspace_sync",
                createdAt=section_date.isoformat(),
            )
        )
    return entries


def _build_focus_items(
    *,
    db: Database,
    agent_key: str,
    week_label: str,
    week_entries: list[AgentWorklogRecord],
) -> list[str]:
    if agent_key == "strategy_design":
        rows = db.fetchall(
            """
            SELECT title
            FROM tasks
            WHERE owner_name = ? AND status != 'done'
            ORDER BY updated_at DESC
            LIMIT 3
            """,
            ("庆华",),
        )
        items = [f"继续推进「{str(row['title'])}」" for row in rows]
        return items or ["继续处理战略问答与关键判断类任务。"]
    if agent_key == "info_data":
        rows = db.fetchall(
            """
            SELECT title
            FROM topic_radars
            ORDER BY created_at ASC
            LIMIT 3
            """
        )
        items = [f"继续跟进「{str(row['title'])}」雷达" for row in rows]
        return items or ["继续补抓高相关情报，并把可执行线索转成任务。"]
    section_titles = [entry.title for entry in week_entries[:3] if entry.title.strip()]
    return [f"继续推进「{title}」" for title in section_titles] or ["继续推进软件系统主线改动，并同步风险和验收结果。"]


def _build_weekly_digests(db: Database, worklogs: list[AgentWorklogRecord]) -> list[AgentWeeklyDigestRecord]:
    grouped: dict[tuple[str, str], list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        grouped[(entry.agentKey, entry.weekLabel)].append(entry)

    digests: list[AgentWeeklyDigestRecord] = []
    for (agent_key, week_label), entries in grouped.items():
        config = AGENT_DEPARTMENTS[agent_key]
        entries.sort(key=lambda item: (item.date, item.createdAt), reverse=True)
        summary = f"{config['agentName']} 本周累计记录 {len(entries)} 条工作日志，主要围绕：{'、'.join(entry.title for entry in entries[:2])}。"
        digests.append(
            AgentWeeklyDigestRecord(
                agentKey=agent_key,  # type: ignore[arg-type]
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                weekLabel=week_label,
                summary=summary,
                focusItems=_build_focus_items(db=db, agent_key=agent_key, week_label=week_label, week_entries=entries),
                evidenceCount=len(entries),
                sourcePolicy={
                    "sourceType": config["sourceType"],
                    "realLogMode": True,
                    "evidenceCount": len(entries),
                },
            )
        )
    digests.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return digests


def _plan_schedule_hint(agent_key: str, index: int) -> str:
    if agent_key == "strategy_design":
        hints = ["周一先校准重点判断", "周中持续验证问答与策略输出", "周末前完成重点结论收束"]
    elif agent_key == "info_data":
        hints = ["每天巡检新增信号", "周中补抓高相关线索", "周末前整理可转任务的情报"]
    else:
        hints = ["周初推进主线改动接线", "周中同步风险与验证结果", "周末前收束系统验收与文档同步"]
    return hints[min(index, len(hints) - 1)]


def _plan_status(value: object) -> str:
    text = str(value or "planned").strip().lower()
    return text if text in {"planned", "doing", "done", "blocked"} else "planned"


def _normalize_plan_items(
    *,
    week_label: str,
    agent_key: str,
    raw_items: list[object],
) -> list[AgentWeeklyPlanItemRecord]:
    items: list[AgentWeeklyPlanItemRecord] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            continue
        title = _clean_text(str(raw_item.get("title") or ""))
        if not title:
            continue
        items.append(
            AgentWeeklyPlanItemRecord(
                id=f"{agent_key}_{week_label}_{index}",
                title=title,
                rationale=_clean_text(str(raw_item.get("rationale") or "")),
                scheduleHint=_clean_text(str(raw_item.get("scheduleHint") or "")),
                status=_plan_status(raw_item.get("status")),
            )
        )
    return items


def _load_plan_override_rows(db: Database, week_label: str) -> dict[str, object]:
    rows = db.fetchall(
        """
        SELECT *
        FROM agent_weekly_plan_overrides
        WHERE week_label = ?
        ORDER BY updated_at DESC
        """,
        (week_label,),
    )
    return {str(row["agent_key"]): row for row in rows}


def _apply_plan_overrides(
    *,
    db: Database,
    week_label: str,
    derived_plans: list[AgentWeeklyPlanRecord],
) -> list[AgentWeeklyPlanRecord]:
    override_rows = _load_plan_override_rows(db, week_label)
    derived_by_agent = {plan.agentKey: plan for plan in derived_plans}
    merged: list[AgentWeeklyPlanRecord] = []

    for agent_key, config in AGENT_DEPARTMENTS.items():
        derived_plan = derived_by_agent.get(agent_key)
        override_row = override_rows.get(agent_key)
        if override_row is None and derived_plan is None:
            continue
        if override_row is None and derived_plan is not None:
            merged.append(derived_plan)
            continue

        raw_items = []
        try:
            raw_items = json.loads(str(override_row["plan_items_json"] or "[]"))
        except Exception:
            raw_items = []
        override_items = _normalize_plan_items(
            week_label=week_label,
            agent_key=agent_key,
            raw_items=raw_items if isinstance(raw_items, list) else [],
        )
        summary = _clean_text(str(override_row["summary"] or ""))
        base_summary = derived_plan.summary if derived_plan else f"{config['agentName']} 本周正式计划。"
        merged.append(
            AgentWeeklyPlanRecord(
                agentKey=agent_key,  # type: ignore[arg-type]
                agentName=str(config["agentName"]),
                departmentName=str(config["departmentName"]),
                color=str(config["color"]),
                weekLabel=week_label,
                summary=summary or base_summary,
                planItems=override_items or (derived_plan.planItems if derived_plan else []),
                sourcePolicy={
                    **(derived_plan.sourcePolicy if derived_plan else {"planMode": "manual_override"}),
                    "manualOverride": True,
                    "updatedBy": str(override_row["updated_by"] or ""),
                    "updatedAt": str(override_row["updated_at"] or ""),
                    "sourceType": config["sourceType"],
                },
            )
        )

    merged.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return merged


def _build_weekly_plans(
    db: Database,
    worklogs: list[AgentWorklogRecord],
    weekly_digests: list[AgentWeeklyDigestRecord] | None = None,
) -> list[AgentWeeklyPlanRecord]:
    grouped: dict[tuple[str, str], list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        grouped[(entry.agentKey, entry.weekLabel)].append(entry)

    digests = weekly_digests if weekly_digests is not None else _build_weekly_digests(db, worklogs)
    plans: list[AgentWeeklyPlanRecord] = []
    for digest in digests:
        entries = grouped.get((digest.agentKey, digest.weekLabel), [])
        entries = sorted(entries, key=lambda item: (item.date, item.createdAt), reverse=True)
        plan_items: list[AgentWeeklyPlanItemRecord] = []
        focus_items = digest.focusItems[:3]
        for index, item in enumerate(focus_items):
            evidence_title = entries[index].title if index < len(entries) else digest.summary
            draft_item = AgentWeeklyPlanItemRecord(
                id=f"{digest.agentKey}_{digest.weekLabel}_{index}",
                title=item,
                rationale=f"基于最近的真实工作痕迹推演：{evidence_title}",
                scheduleHint=_plan_schedule_hint(digest.agentKey, index),
            )
            plan_items.append(
                draft_item.model_copy(update={"status": _infer_plan_item_status(draft_item, entries)})
            )
        if not plan_items:
            draft_item = AgentWeeklyPlanItemRecord(
                id=f"{digest.agentKey}_{digest.weekLabel}_default",
                title=f"维持{digest.departmentName}当前主线推进",
                rationale=digest.summary,
                scheduleHint=_plan_schedule_hint(digest.agentKey, 0),
            )
            plan_items.append(
                draft_item.model_copy(update={"status": _infer_plan_item_status(draft_item, entries)})
            )
        plans.append(
            AgentWeeklyPlanRecord(
                agentKey=digest.agentKey,
                agentName=digest.agentName,
                departmentName=digest.departmentName,
                color=digest.color,
                weekLabel=digest.weekLabel,
                summary=f"{digest.agentName} 本周计划由 {digest.evidenceCount} 条真实日志推演而来，优先围绕：{'、'.join(item.title for item in plan_items[:2])}。",
                planItems=plan_items,
                sourcePolicy={
                    "planMode": "derived_from_real_logs",
                    "evidenceCount": digest.evidenceCount,
                    "sourceType": digest.sourcePolicy.get("sourceType"),
                    "autoStatus": True,
                },
            )
        )
    plans.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return plans


def _build_agent_worklogs_for_range(
    *,
    db: Database,
    range_start: date,
    range_end: date,
    thread_sync_path: Path,
) -> list[AgentWorklogRecord]:
    worklogs = [
        *_build_qinghua_logs(db, range_start, range_end),
        *_build_dazhou_logs(db, range_start, range_end),
        *_build_jiale_logs(thread_sync_path, range_start, range_end),
    ]
    worklogs.sort(key=lambda item: (item.date, item.createdAt, item.agentName), reverse=True)
    return worklogs


def build_agent_weekly_digests(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[AgentWeeklyDigestRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    return _build_weekly_digests(db, worklogs)


def build_agent_weekly_plans(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[AgentWeeklyPlanRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_digests = _build_weekly_digests(db, worklogs)
    derived_plans = _build_weekly_plans(db, worklogs, weekly_digests)
    return _apply_plan_overrides(db=db, week_label=week_label, derived_plans=derived_plans)


def build_agent_weekly_review_items(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[WeeklyReviewTaskEntryRecord]:
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_digests = _build_weekly_digests(db, worklogs)
    weekly_plans = _apply_plan_overrides(
        db=db,
        week_label=week_label,
        derived_plans=_build_weekly_plans(db, worklogs, weekly_digests),
    )
    digest_by_agent = {item.agentKey: item for item in weekly_digests}
    worklogs_by_agent = defaultdict(list)
    for log in worklogs:
        worklogs_by_agent[log.agentKey].append(log)

    review_items: list[WeeklyReviewTaskEntryRecord] = []
    for plan in weekly_plans:
        digest = digest_by_agent.get(plan.agentKey)
        if digest is None:
            continue
        week_entries = sorted(
            worklogs_by_agent.get(plan.agentKey, []),
            key=lambda item: (item.date, item.createdAt),
            reverse=True,
        )
        tag = _agent_task_tag(plan.agentKey)
        for index, plan_item in enumerate(plan.planItems):
            matched_entries = _matched_entries_for_plan_item(plan_item, week_entries)
            status = _plan_status(plan_item.status)
            progress = _compose_agent_progress(plan_item, matched_entries or week_entries[:2], digest)
            success_experience = _compose_agent_success_experience(matched_entries) if status == "done" else ""
            failure_insight = _compose_agent_failure_insight(matched_entries) if status == "blocked" else ""
            blocker_reason = failure_insight if status == "blocked" else ""
            next_action = plan_item.scheduleHint or (digest.focusItems[index + 1] if index + 1 < len(digest.focusItems) else "")
            created_at = matched_entries[0].createdAt if matched_entries else (week_entries[0].createdAt if week_entries else week_start.isoformat())
            review_items.append(
                WeeklyReviewTaskEntryRecord(
                    id=f"agent_review_{plan.agentKey}_{plan.weekLabel}_{index}",
                    reviewId=f"agent_review_{plan.agentKey}_{plan.weekLabel}",
                    taskId=f"agent_task_{plan.agentKey}_{plan.weekLabel}_{index}",
                    weekLabel=plan.weekLabel,
                    contentDomain="work",
                    note="",
                    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
                        reflection=success_experience or failure_insight or blocker_reason or next_action,
                        lightweightTag="等待他人" if status == "blocked" else "",
                        planCommitment=plan_item.title,
                        progress=progress,
                        completionStatus=_plan_status_to_completion_status(status),  # type: ignore[arg-type]
                        departmentPlanId=plan_item.id,
                        departmentPlanAlignment="aligned",
                        organizationPlanId=None,
                        organizationPlanAlignment="unknown",
                        successReason=success_experience,
                        successExperience=success_experience,
                        blockerReason=blocker_reason,
                        failureInsight=failure_insight,
                        supportNeeded="需要 CEO 或跨部门支持" if status == "blocked" else "",
                        nextAction=next_action,
                    ),
                    reviewedAt=created_at,
                    taskSnapshot=WeeklyReviewTaskSnapshotRecord(
                        title=plan_item.title,
                        status=_plan_status_to_task_status(status),  # type: ignore[arg-type]
                        dueDate=week_end.isoformat(),
                        createdAt=created_at,
                        ownerId=f"agent:{plan.agentKey}",
                        ownerName=plan.agentName,
                        tags=[tag],
                        listName=plan.departmentName,
                        listColor=plan.color,
                    ),
                )
            )
    review_items.sort(key=lambda item: (item.taskSnapshot.ownerName or "", item.taskId))
    return review_items


def sync_agent_execution_tasks(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[str]:
    week_start, week_end = _week_bounds(week_label)
    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label=week_label,
        thread_sync_path=thread_sync_path,
    )
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    worklogs_by_agent: dict[str, list[AgentWorklogRecord]] = defaultdict(list)
    for entry in worklogs:
        worklogs_by_agent[entry.agentKey].append(entry)

    task_list_id = _default_task_list_id(db)
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    expected_ids: list[str] = []

    for plan in weekly_plans:
        tag_names = [plan.departmentName, "机器人任务"]
        for index, plan_item in enumerate(plan.planItems):
            task_id = f"agent_task_{plan.agentKey}_{plan.weekLabel}_{index}"
            expected_ids.append(task_id)
            matched_entries = _matched_entries_for_plan_item(plan_item, worklogs_by_agent.get(plan.agentKey, []))
            status = _plan_status_to_task_status(_plan_status(plan_item.status))
            description = _compose_agent_progress(plan_item, matched_entries or worklogs_by_agent.get(plan.agentKey, [])[:2], next(
                (item for item in _build_weekly_digests(db, worklogs) if item.agentKey == plan.agentKey and item.weekLabel == plan.weekLabel),
                AgentWeeklyDigestRecord(
                    agentKey=plan.agentKey,
                    agentName=plan.agentName,
                    departmentName=plan.departmentName,
                    color=plan.color,
                    weekLabel=plan.weekLabel,
                    summary=plan.summary,
                    focusItems=[],
                    evidenceCount=0,
                    sourcePolicy={},
                ),
            ))
            created_at = matched_entries[0].createdAt if matched_entries else timestamp
            db.execute(
                """
                INSERT INTO tasks(
                    id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    priority = excluded.priority,
                    list_id = excluded.list_id,
                    owner_name = excluded.owner_name,
                    ddl = excluded.ddl,
                    source_type = excluded.source_type,
                    source_id = excluded.source_id,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    plan_item.title,
                    description,
                    status,
                    "normal",
                    task_list_id,
                    plan.agentName,
                    _agent_due_label(week_end, plan_item.scheduleHint),
                    AGENT_AUTO_SOURCE_TYPE,
                    _agent_auto_source_id(plan.weekLabel, plan.agentKey, index),
                    json.dumps(tag_names, ensure_ascii=False),
                    "[]",
                    created_at,
                    timestamp,
                ),
            )
            note_content = "\n".join(
                part for part in [
                    f"部门：{plan.departmentName}",
                    f"计划说明：{plan_item.rationale}",
                    f"调度提示：{plan_item.scheduleHint}",
                    f"本周自动进展：{description}",
                    f"状态：{_plan_status(plan_item.status)}",
                ] if _clean_text(part)
            )
            existing_note = db.fetchone("SELECT id FROM task_notes WHERE task_id = ?", (task_id,))
            if existing_note:
                db.execute(
                    "UPDATE task_notes SET note = ?, updated_at = ? WHERE task_id = ?",
                    (note_content, timestamp, task_id),
                )
            else:
                db.execute(
                    "INSERT INTO task_notes(id, task_id, note, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                    (f"agent_note_{task_id}", task_id, note_content, timestamp, timestamp),
                )

    if expected_ids:
        placeholders = ",".join("?" for _ in expected_ids)
        db.execute(
            f"DELETE FROM tasks WHERE source_type = ? AND source_id LIKE ? AND id NOT IN ({placeholders})",
            (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%", *expected_ids),
        )
    else:
        db.execute(
            "DELETE FROM tasks WHERE source_type = ? AND source_id LIKE ?",
            (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%"),
        )
    return expected_ids


def build_agent_execution_tasks(
    *,
    db: Database,
    week_label: str,
    thread_sync_path: Path,
) -> list[TaskRecord]:
    sync_agent_execution_tasks(db=db, week_label=week_label, thread_sync_path=thread_sync_path)
    rows = db.fetchall(
        """
        SELECT t.*, l.name AS list_name, l.color AS list_color
        FROM tasks t
        JOIN task_lists l ON l.id = t.list_id
        WHERE t.source_type = ? AND t.source_id LIKE ?
        ORDER BY t.owner_name COLLATE NOCASE ASC, t.updated_at DESC
        """,
        (AGENT_AUTO_SOURCE_TYPE, f"{week_label}::%"),
    )
    tasks: list[TaskRecord] = []
    for row in rows:
        note_row = db.fetchone("SELECT note FROM task_notes WHERE task_id = ?", (str(row["id"]),))
        identity = _parse_agent_task_identity(str(row["id"]))
        agent_key = identity[0] if identity else "strategy_design"
        tasks.append(
            TaskRecord(
                id=str(row["id"]),
                title=str(row["title"]),
                desc=str(row["description"]),
                status=str(row["status"]),  # type: ignore[arg-type]
                creatorId=f"agent:{agent_key}",
                creatorName=str(row["owner_name"]),
                priority=str(row["priority"]),  # type: ignore[arg-type]
                listId=str(row["list_id"]),
                listName=str(row["list_name"]),
                listColor=str(row["list_color"]),
                ddl=str(row["ddl"]),
                ownerId=f"agent:{agent_key}",
                ownerName=str(row["owner_name"]),
                sourceType=str(row["source_type"]),
                sourceId=str(row["source_id"]) if row["source_id"] else None,
                tags=[
                    _agent_task_tag(agent_key),
                    TaskTagRecord(
                        id=f"agent_dept_{agent_key}",
                        name=str(next((meta["departmentName"] for key, meta in AGENT_DEPARTMENTS.items() if key == agent_key), "机器人部门")),
                        color=str(next((meta["color"] for key, meta in AGENT_DEPARTMENTS.items() if key == agent_key), "#64748B")),
                        scope="org",
                        updatedAt=str(row["updated_at"]),
                    ),
                ],
                note=str(note_row["note"]) if note_row else None,
                collaborators=[],
                collaborationSummary={},
                viewerInboxStatus=None,
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
        )
    return tasks


def build_agent_execution_task_activity(
    *,
    db: Database,
    task_id: str,
    thread_sync_path: Path,
) -> list[TaskActivityRecord]:
    identity = _parse_agent_task_identity(task_id)
    if identity is None:
        return []
    agent_key, week_label, item_index = identity
    week_start, week_end = _week_bounds(week_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=week_start,
        range_end=week_end,
        thread_sync_path=thread_sync_path,
    )
    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label=week_label,
        thread_sync_path=thread_sync_path,
    )
    plan = next((item for item in weekly_plans if item.agentKey == agent_key), None)
    if plan is None or item_index >= len(plan.planItems):
        return []
    plan_item = plan.planItems[item_index]
    matched_entries = _matched_entries_for_plan_item(
        plan_item,
        [entry for entry in worklogs if entry.agentKey == agent_key],
    )
    actor_id = f"agent:{agent_key}"
    actor_name = plan.agentName
    activities: list[TaskActivityRecord] = [
        TaskActivityRecord(
            id=f"agent_activity_created_{task_id}",
            taskId=task_id,
            actorId=actor_id,
            actorName=actor_name,
            eventType="agent.plan_synced",
            payload={
                "weekLabel": week_label,
                "planTitle": plan_item.title,
                "status": plan_item.status,
                "scheduleHint": plan_item.scheduleHint,
            },
            createdAt=week_start.isoformat(),
        )
    ]
    for index, entry in enumerate(matched_entries):
        activities.append(
            TaskActivityRecord(
                id=f"agent_activity_{task_id}_{index}",
                taskId=task_id,
                actorId=actor_id,
                actorName=actor_name,
                eventType="agent.worklog",
                payload={
                    "title": entry.title,
                    "summary": entry.summary,
                    "detailLines": entry.detailLines,
                    "sourceType": entry.sourceType,
                    "departmentName": entry.departmentName,
                },
                createdAt=entry.createdAt,
            )
        )
    activities.sort(key=lambda item: item.createdAt, reverse=True)
    return activities


def upsert_agent_weekly_plan_override(
    *,
    db: Database,
    payload: AgentWeeklyPlanPayload,
    updated_by: str,
) -> None:
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    plan_items = [
        AgentWeeklyPlanItemRecord(
            id=f"{payload.agentKey}_{payload.weekLabel}_{index}",
            title=_clean_text(item.title),
            rationale=_clean_text(item.rationale),
            scheduleHint=_clean_text(item.scheduleHint),
            status=_plan_status(item.status),
        )
        for index, item in enumerate(payload.planItems)
        if _clean_text(item.title)
    ]
    row = db.fetchone(
        """
        SELECT id, created_at
        FROM agent_weekly_plan_overrides
        WHERE week_label = ? AND agent_key = ?
        """,
        (payload.weekLabel, payload.agentKey),
    )
    serialized_items = json.dumps(
        [
            {
                "title": item.title,
                "rationale": item.rationale,
                "scheduleHint": item.scheduleHint,
                "status": item.status,
            }
            for item in plan_items
        ],
        ensure_ascii=False,
    )
    if row:
        db.execute(
            """
            UPDATE agent_weekly_plan_overrides
            SET summary = ?, plan_items_json = ?, updated_by = ?, updated_at = ?
            WHERE week_label = ? AND agent_key = ?
            """,
            (
                _clean_text(payload.summary),
                serialized_items,
                updated_by,
                timestamp,
                payload.weekLabel,
                payload.agentKey,
            ),
        )
        return
    db.execute(
        """
        INSERT INTO agent_weekly_plan_overrides(
            id, week_label, agent_key, summary, plan_items_json, updated_by, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"agent_plan_override_{payload.agentKey}_{payload.weekLabel}",
            payload.weekLabel,
            payload.agentKey,
            _clean_text(payload.summary),
            serialized_items,
            updated_by,
            timestamp,
            timestamp,
        ),
    )


def build_agent_worklog_response(
    *,
    db: Database,
    month_label: str,
    thread_sync_path: Path,
) -> AgentWorklogResponse:
    month_start, month_end = _month_bounds(month_label)
    worklogs = _build_agent_worklogs_for_range(
        db=db,
        range_start=month_start,
        range_end=month_end,
        thread_sync_path=thread_sync_path,
    )
    represented_weeks = sorted({item.weekLabel for item in worklogs}, reverse=True)
    weekly_digests: list[AgentWeeklyDigestRecord] = []
    weekly_plans: list[AgentWeeklyPlanRecord] = []
    for week_label in represented_weeks:
        week_digests = build_agent_weekly_digests(
            db=db,
            week_label=week_label,
            thread_sync_path=thread_sync_path,
        )
        weekly_digests.extend(week_digests)
        weekly_plans.extend(
            build_agent_weekly_plans(
                db=db,
                week_label=week_label,
                thread_sync_path=thread_sync_path,
            )
        )
    weekly_digests.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    weekly_plans.sort(key=lambda item: (item.weekLabel, item.departmentName), reverse=True)
    return AgentWorklogResponse(
        month=month_label,
        worklogs=worklogs,
        weeklyDigests=weekly_digests,
        weeklyPlans=weekly_plans,
    )
~~~

## `backend/app/services/ai.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import httpx

from app.db import Database
from app.models import AiStructuredResponse


DEFAULT_PROVIDER = "doubao"
DEFAULT_MODELS = {
    "mock": "mock-summarizer",
    "qwen": "qwen3.5-plus",
    "doubao": "doubao-seed-2-0-pro-260215",
}
DEFAULT_MODEL = DEFAULT_MODELS[DEFAULT_PROVIDER]
QWEN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
PROVIDER_LABELS = {"qwen": "Qwen 3.5", "doubao": "豆包 Seed 2.0 Pro", "mock": "Mock"}


@dataclass
class AiHealth:
    provider: str
    model: str
    ready: bool
    detail: str
    credential_source: str
    fingerprint: str | None = None


class AiInvocationError(RuntimeError):
    def __init__(self, provider: str, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


@dataclass(frozen=True)
class ChatGenerationProfile:
    primary_context: str
    primary_timeout_seconds: float
    primary_max_tokens: int
    primary_enable_thinking: bool
    fallback_context: str
    fallback_timeout_seconds: float
    fallback_max_tokens: int
    fallback_enable_thinking: bool


class AiService:
    def __init__(self, db: Database, secret_stores: dict[str, object]):
        self.db = db
        self.secret_stores = secret_stores
        provider = self.db.get_setting("ai_provider", DEFAULT_PROVIDER)
        if provider not in DEFAULT_MODELS:
            provider = DEFAULT_PROVIDER
        self.db.set_setting("ai_provider", provider)
        self.db.set_setting("ai_model", self.db.get_setting("ai_model", DEFAULT_MODELS[provider]) or DEFAULT_MODELS[provider])

    def current_provider(self) -> str:
        provider = self.db.get_setting("ai_provider", DEFAULT_PROVIDER)
        return provider if provider in DEFAULT_MODELS else DEFAULT_PROVIDER

    def current_model(self) -> str:
        model = self.db.get_setting("ai_model", "")
        return model or DEFAULT_MODELS[self.current_provider()]

    def configure(self, provider: str | None, model: str | None, api_key: str | None, clear_api_key: bool) -> None:
        target_provider = provider or self.current_provider()
        if target_provider not in DEFAULT_MODELS:
            target_provider = DEFAULT_PROVIDER
        if provider:
            self.db.set_setting("ai_provider", target_provider)
            if not model:
                self.db.set_setting("ai_model", DEFAULT_MODELS[target_provider])
        if model:
            self.db.set_setting("ai_model", model)
        store = self._store_for(target_provider)
        if clear_api_key and store:
            store.delete_api_key()
        if api_key and store:
            store.set_api_key(api_key)

    def get_health(self) -> AiHealth:
        provider = self.current_provider()
        model = self.current_model()
        if provider == "mock":
            return AiHealth(
                provider=provider,
                model=DEFAULT_MODELS["mock"],
                ready=True,
                detail="当前使用本地 mock 推演器，可稳定支撑桌面端流程联调。",
                credential_source="local",
                fingerprint=None,
            )
        store = self._store_for(provider)
        source = store.get_source_label() if store else "unavailable"
        fingerprint = store.get_api_key_fingerprint() if store else None
        api_key = store.get_api_key() if store else ""
        label = PROVIDER_LABELS.get(provider, provider)
        if not api_key:
            return AiHealth(
                provider=provider,
                model=model,
                ready=False,
                detail=f"{label} 未配置 API Key，当前只能切回 mock。",
                credential_source=source,
                fingerprint=fingerprint,
            )
        return AiHealth(
            provider=provider,
            model=model,
            ready=True,
            detail=f"{label} 凭证已配置，可用于结构化问答与分析。",
            credential_source=source,
            fingerprint=fingerprint,
        )

    def test_connection(self) -> AiHealth:
        health = self.get_health()
        if health.provider == "mock" or not health.ready:
            return health
        self._qwen_generate(
            prompt="请用一句中文确认连接成功。",
            system_instruction="你是系统健康检查助手。只返回纯文本。",
            response_schema=None,
        )
        return AiHealth(
            provider=health.provider,
            model=health.model,
            ready=True,
            detail=f"{PROVIDER_LABELS.get(health.provider, health.provider)} 联通测试成功。",
            credential_source=health.credential_source,
            fingerprint=health.fingerprint,
        )

    def generate_structured(self, prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider in ("qwen", "doubao") and health.ready:
            return self._qwen_generate_structured_with_retry(prompt, system_instruction, context_summary)
        return self._mock_generate(prompt, context_summary)

    def generate_general_fallback(self, prompt: str, note: str = "", *, subject_name: str = "") -> AiStructuredResponse:
        health = self.get_health()
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                return self._qwen_generate_general_fallback(prompt, note, subject_name=subject_name)
            except Exception:
                subject_hint = f"{subject_name} 的通用背景初步判断。" if subject_name else "当前问题的通用背景初步判断。"
                background_note = (
                    f"{subject_hint} "
                    + (
                        note.strip()
                        if note and note.strip()
                        else "当前没有命中足够的原始材料，以下只保留保守、非正式的背景判断。"
                    )
                )
                return self._mock_generate(prompt, background_note)
        return self._mock_generate(prompt, note or "当前资料回答阶段失败，以下为本地保守兜底判断。")

    def generate_workspace_state_response(
        self,
        prompt: str,
        state_context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        health = self.get_health()
        compact_context = self._compact_context_summary(state_context_summary, max_chars=2600)
        if health.provider in ("qwen", "doubao") and health.ready:
            if on_partial is not None:
                opening = "正在优先整理客户状态池，先生成一版边界清晰的结构化状态回答。"
                on_partial(
                    {
                        "stageLabel": "正在生成状态回答",
                        "progress": 54.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            instruction = (
                "你是益语智库的客户状态顾问。"
                "请优先基于客户状态池直接回答，不要退回成资料摘要。"
                "回答必须明确区分：正式判断、待确认判断、本周动作、风险提醒、缺失信息。"
                "candidate、risk、unknown 不能改写成已证实事实。"
                "不要解释系统过程，不要输出 JSON，不要输出 Markdown 代码块。"
                "先求稳定、清楚、可执行，再求长。"
            )
            prompt_text = (
                f"用户问题：{prompt}\n\n"
                f"客户状态池：\n{compact_context or state_context_summary}\n\n"
                "请直接给出一版可展示的状态回答。"
            )
            first_error: Exception | None = None
            try:
                text = self._qwen_generate(
                    prompt=prompt_text,
                    system_instruction=instruction,
                    response_schema=None,
                    timeout_seconds=14.0,
                    max_tokens=1400,
                    temperature=0.22,
                    top_p=0.88,
                    enable_thinking=False,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as error:
                first_error = error
            retry_context = self._compact_context_summary(state_context_summary, max_chars=1600)
            try:
                text = self._qwen_generate(
                    prompt=(
                        f"用户问题：{prompt}\n\n"
                        f"客户状态池：\n{retry_context or compact_context or state_context_summary}\n\n"
                        "请只保留最重要的状态判断和下一步动作，直接回答。"
                    ),
                    system_instruction=instruction,
                    response_schema=None,
                    timeout_seconds=10.0,
                    max_tokens=900,
                    temperature=0.18,
                    top_p=0.85,
                    enable_thinking=False,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as retry_error:
                detail = "；".join(
                    part
                    for part in (
                        f"状态回答主调用失败：{self._format_provider_error(first_error)}" if first_error else "",
                        f"状态回答紧凑重试失败：{self._format_provider_error(retry_error)}",
                    )
                    if part
                )
                raise AiInvocationError(health.provider, detail) from retry_error
        return self._mock_generate(prompt, compact_context or state_context_summary)

    def generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider in ("qwen", "doubao") and health.ready:
            provider = health.provider
            chat_profile = self._build_chat_generation_profile(context_summary)
            if on_partial is not None:
                opening = "正在围绕核心判断、关键张力和潜在风险整合原始证据，准备输出连续长文分析。"
                on_partial(
                    {
                        "stageLabel": "正在整合长文分析",
                        "progress": 58.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            try:
                return self._qwen_generate_chat_response(
                    prompt,
                    system_instruction,
                    chat_profile.primary_context,
                    timeout_seconds=chat_profile.primary_timeout_seconds,
                    max_tokens=chat_profile.primary_max_tokens,
                    enable_thinking=chat_profile.primary_enable_thinking,
                    on_partial=on_partial,
                )
            except Exception as error:
                primary_error = error
                try:
                    return self._qwen_generate_textual_fallback(
                        prompt,
                        system_instruction,
                        chat_profile.fallback_context or chat_profile.primary_context or context_summary,
                        timeout_seconds=chat_profile.fallback_timeout_seconds,
                        max_tokens=chat_profile.fallback_max_tokens,
                        enable_thinking=chat_profile.fallback_enable_thinking,
                    )
                except Exception as retry_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"主长文生成失败：{self._format_provider_error(primary_error)}",
                            f"快速兜底失败：{self._format_provider_error(retry_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError(provider, detail) from retry_error
        return self._mock_generate(prompt, context_summary)

    def _build_chat_generation_profile(self, context_summary: str) -> ChatGenerationProfile:
        context = str(context_summary or "").strip()
        context_length = len(context)
        evidence_count = context.count("[原始证据 ")
        high_load = context_length >= 22000 or evidence_count >= 10
        extreme_load = context_length >= 52000 or evidence_count >= 22

        primary_context = context if not high_load else self._compact_context_summary(context, max_chars=32000)
        primary_timeout_seconds = 20.0
        primary_max_tokens = 2200
        primary_enable_thinking = False

        if high_load:
            primary_timeout_seconds = min(30.0, max(22.0, 20.0 + context_length / 18000.0))
            primary_max_tokens = 1800
            primary_enable_thinking = False
        if extreme_load:
            primary_context = self._compact_context_summary(context, max_chars=22000)
            primary_timeout_seconds = max(primary_timeout_seconds, 24.0)
            primary_max_tokens = 1400
            primary_enable_thinking = False

        fallback_context = self._compact_context_summary(context, max_chars=9000 if high_load else 7000)
        fallback_timeout_seconds = 14.0 if high_load else 12.0
        fallback_max_tokens = 1100 if high_load else 900

        return ChatGenerationProfile(
            primary_context=primary_context or context,
            primary_timeout_seconds=primary_timeout_seconds,
            primary_max_tokens=primary_max_tokens,
            primary_enable_thinking=primary_enable_thinking,
            fallback_context=fallback_context,
            fallback_timeout_seconds=fallback_timeout_seconds,
            fallback_max_tokens=fallback_max_tokens,
            fallback_enable_thinking=False,
        )

    def generate_topic_candidate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        health = self.get_health()
        compact_context = self._compact_context_summary(context_summary, max_chars=8000)
        quick_instruction = (
            f"{system_instruction}\n"
            "请先直接回答用户最关心的问题，再展开解释。"
            "根据问题复杂度自由决定回答长度。"
            "优先讲清楚：它解决什么问题、对谁有用、为什么值得关心、落地会卡在哪。"
            "少讲空泛趋势，少做宏大评论，不要写成长文分析。"
            "不要输出 JSON 或 Markdown 代码块。"
        )
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=f"用户问题：{prompt}\n\n当前情报背景：\n{compact_context}",
                    system_instruction=quick_instruction,
                    response_schema=None,
                    timeout_seconds=16.0,
                    max_tokens=3000,
                    temperature=0.5,
                    top_p=0.9,
                    enable_thinking=True,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as error:
                try:
                    return self._qwen_generate_brief_grounded_rescue(prompt, compact_context or context_summary)
                except Exception as rescue_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"资讯快答失败：{self._format_provider_error(error)}",
                            f"简短兜底失败：{self._format_provider_error(rescue_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError("qwen", detail) from rescue_error
        return self._mock_generate(prompt, compact_context or context_summary)

    def generate_template_field_value(
        self,
        *,
        field_label: str,
        template_name: str,
        client_name: str,
        context_summary: str,
        field_type: str | None = None,
    ) -> str:
        health = self.get_health()
        field_rule = self._template_field_rule(field_type)
        system_instruction = (
            "你正在为客户资料模板填写单个字段。"
            "请只输出可以直接粘贴进 Word 文档的最终内容，不要解释过程，不要写'根据资料'、'建议填写'、'可写为'这类前缀。"
            "如果资料不足，请只输出“【待确认】”开头的一句简短提示。"
            "不要输出“可从……进一步梳理”“建议补充”“可填写为”这类过程性提示。"
            "不要输出 Markdown 代码块，不要输出 JSON。"
        )
        prompt = (
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"待填写字段：{field_label}\n\n"
            f"字段类型：{field_type or 'general'}\n"
            f"字段要求：{field_rule}\n\n"
            f"可参考材料：\n{context_summary.strip()}\n\n"
            "请直接给出这个字段应填写的内容。"
        )
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=None,
                    timeout_seconds=26.0,
                    max_tokens=700,
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=False,
                )
                return self._clean_template_field_value(str(text), field_type=field_type)
            except Exception as first_error:
                compact_context = context_summary.strip()[:2400]
                try:
                    text = self._qwen_generate(
                        prompt=(
                            f"客户：{client_name}\n"
                            f"模板：{template_name}\n"
                            f"待填写字段：{field_label}\n\n"
                            f"字段类型：{field_type or 'general'}\n"
                            f"字段要求：{field_rule}\n\n"
                            f"可参考材料：\n{compact_context}\n\n"
                            "请直接给出这个字段应填写的内容。"
                        ),
                        system_instruction=system_instruction,
                        response_schema=None,
                        timeout_seconds=14.0,
                        max_tokens=420,
                        temperature=0.22,
                        top_p=0.88,
                        enable_thinking=False,
                    )
                    return self._clean_template_field_value(str(text), field_type=field_type)
                except Exception as second_error:
                    raise AiInvocationError(
                        "qwen",
                        "；".join(
                            part
                            for part in (
                                f"字段填写主调用失败：{self._format_provider_error(first_error)}",
                                f"字段填写紧凑重试失败：{self._format_provider_error(second_error)}",
                            )
                            if part
                        ),
                    ) from second_error
        fallback = context_summary.strip().splitlines()
        best_line = next((line.strip() for line in fallback if line.strip()), "")
        return self._clean_template_field_value(best_line or "【待确认】当前缺少可直接填写该字段的资料。", field_type=field_type)

    def generate_template_field_values_batch(
        self,
        *,
        template_name: str,
        client_name: str,
        field_contexts: list[tuple[str, str]],
        field_types: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not field_contexts:
            return {}
        health = self.get_health()
        labels = [label for label, _ in field_contexts]
        schema = {
            "type": "OBJECT",
            "properties": {label: {"type": "STRING"} for label in labels},
            "required": labels,
        }
        system_instruction = (
            "你正在为客户资料模板批量填写多个字段。"
            "每个字段都带有它自己的参考材料。"
            "请严格返回一个 JSON 对象，键必须和字段名完全一致。"
            "每个值都必须是可直接粘贴进 Word 文档的最终内容，不要加解释或前缀。"
            "如果资料不足，该字段值只输出“【待确认】”开头的一句简短提示。"
            "不要输出 Markdown 代码块，不要输出 JSON 以外的任何内容。"
        )
        prompt_blocks: list[str] = []
        for index, (label, context_summary) in enumerate(field_contexts, start=1):
            current_type = str((field_types or {}).get(label) or "general")
            prompt_blocks.append(
                (
                    f"[字段 {index}]\n"
                    f"字段名：{label}\n"
                    f"字段类型：{current_type}\n"
                    f"字段要求：{self._template_field_rule(current_type)}\n"
                    "只填写这个字段，不要引用其他字段。\n"
                    f"{context_summary.strip()}"
                ).strip()
            )
        prompt = (
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"字段总数：{len(field_contexts)}\n\n"
            "请分别填写以下字段，并返回 JSON 对象：\n\n"
            + "\n\n".join(prompt_blocks)
        )
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                payload = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=schema,
                    timeout_seconds=min(18.0, max(10.0, 6.0 + 1.8 * len(field_contexts))),
                    max_tokens=min(3200, max(1200, 360 * len(field_contexts))),
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=False,
                )
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
            if isinstance(payload, dict):
                return {
                    label: self._clean_template_field_value(
                        str(payload.get(label) or "【待确认】当前缺少可直接填写该字段的资料。"),
                        field_type=str((field_types or {}).get(label) or "general"),
                    )
                    for label in labels
                }
        return {
            label: self.generate_template_field_value(
                field_label=label,
                template_name=template_name,
                client_name=client_name,
                context_summary=context_summary,
                field_type=str((field_types or {}).get(label) or "general"),
            )
            for label, context_summary in field_contexts
        }

    def _qwen_generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 22.0,
        max_tokens: int = 3600,
        enable_thinking: bool = True,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        detailed_context = str(context_summary or "").strip()
        base_instruction = (
            f"{system_instruction}\n"
            "你现在是在直接回答用户，不要把答案写成系统产物。"
            "请把后面的原始材料当作你已经完整读过的材料直接使用。"
            "不要解释检索过程、系统过程、命中规则或技术细节。"
            "优先输出可执行、可读的回答，不要凑篇幅。"
            "可以做综合判断，但不要把未证实事实写成确定结论。\n\n"
            "【输出约束】\n"
            "1. 用 3-4 个小节组织回答，先结论再展开。\n"
            "2. 每节 2-4 句话，必要时用「- 」列要点。\n"
            "3. 默认 400-900 字；用户明确要简短时可更短。\n"
            "4. 涉及风险或待确认信息时必须单列说明。\n"
        )
        try:
            if on_partial is not None:
                on_partial(
                    {
                        "stageLabel": "正在直接生成长文回答",
                        "progress": 62.0,
                        "content": "千问正在基于完整材料直接生成长文回答。",
                        "structured": {
                            "content": "千问正在基于完整材料直接生成长文回答。",
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            text = self._qwen_generate(
                prompt=f"用户问题：{prompt}\n\n参考材料：\n{detailed_context}",
                system_instruction=base_instruction,
                response_schema=None,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                temperature=0.48,
                top_p=0.96,
                enable_thinking=enable_thinking,
            )
            return self._structured_from_plain_answer(str(text))
        except Exception as error:
            raise AiInvocationError(self.current_provider(), self._format_provider_error(error)) from error

    def _qwen_generate_progressive_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        focus_context = self._compact_context_summary(context_summary, max_chars=20000)
        analysis_context = self._compact_context_summary(context_summary, max_chars=40000)
        action_context = self._compact_context_summary(context_summary, max_chars=20000)
        base_instruction = (
            f"{system_instruction}\n"
            "你现在要分阶段写成一版完整顾问回答。"
            "每个阶段都直接服务最终成文，不要解释系统过程，也不要输出技术细节。"
            "优先写得深、清楚、有判断。\n"
            "【排版规则——必须严格遵守】\n"
            "1. 用「一、二、三」作为一级小标题分层\n"
            "2. 并列要点用「- 」列表\n"
            "3. 关键结论用 **加粗**\n"
            "4. 禁止全篇连续长段落\n"
            "5. 多用「不是X，而是Y」「核心在于」等判断句式\n"
        )

        def emit_partial(stage_label: str, progress: float, content: str, *, judgment: str = "", analysis: str = "", actions: str = "") -> None:
            if on_partial is None:
                return
            on_partial(
                {
                    "stageLabel": stage_label,
                    "progress": progress,
                    "content": content.strip(),
                    "structured": {
                        "content": content.strip(),
                        "judgment": judgment.strip(),
                        "analysis": analysis.strip(),
                        "actions": actions.strip(),
                        "timeline": "",
                    },
                }
            )

        errors: list[str] = []
        opener_text = ""
        title = ""
        judgment = ""
        analysis_text = ""
        actions_text = ""

        try:
            opener_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{focus_context}\n\n"
                        "请先写出回答的开场部分。"
                        "如果你觉得需要标题就写，不需要就直接进入正文。"
                        "这部分要直接回答问题，并自然点出最重要的主线、判断或观察。不要为了格式而格式化。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把回答开头写出来。"
                    ),
                    response_schema=None,
                    timeout_seconds=12.0,
                    max_tokens=1200,
                    temperature=0.42,
                    top_p=0.96,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"开场判断失败：{self._format_provider_error(error)}")
        if not opener_text:
            raise AiInvocationError("qwen", "；".join(errors) or "分阶段生成未返回开场判断")

        extracted_title = self._extract_segment_field(opener_text, ("标题", "题目"))
        title = re.sub(r"\s+", " ", extracted_title or "").strip()[:24]
        judgment = self._extract_segment_field(opener_text, ("总判断", "判断")) or opener_text
        partial_content = "\n\n".join(part for part in [title, judgment] if part.strip())
        emit_partial("正在形成开场判断", 62.0, partial_content, judgment=judgment)

        try:
            analysis_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{analysis_context}\n\n"
                        f"当前总判断：\n{judgment}\n\n"
                        "请继续完成主体分析。"
                        "由你自己判断最适合这道问题的展开方式，可以用自然段，也可以用小标题。"
                        "尽量把真正值得展开的部分讲透，而不是把所有可能方向平均铺开。"
                        "不要复述材料标题，不要把回答写成资料摘要。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把主体内容写深、写透。"
                    ),
                    response_schema=None,
                    timeout_seconds=30.0,
                    max_tokens=3200,
                    temperature=0.42,
                    top_p=0.95,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"主体分析失败：{self._format_provider_error(error)}")

        analysis_density = len(re.sub(r"\s+", "", analysis_text))
        if analysis_density < 260:
            try:
                rescue_text = str(
                    self._qwen_generate(
                        prompt=(
                            f"问题：{prompt}\n\n"
                            f"顾问底稿：\n{analysis_context}\n\n"
                            f"已有总判断：\n{judgment}\n\n"
                        "请补写主体分析。"
                        "如果已有主体内容偏短，就继续把最值得展开的部分补深。"
                        "不需要机械补齐固定小节，也不要反复围绕同一个判断来回改写。"
                        "你可以自由决定是继续展开已有主线，还是补进新的关键分析面。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段是主体内容补写。"
                    ),
                    response_schema=None,
                    timeout_seconds=10.0,
                    max_tokens=1200,
                    temperature=0.4,
                    top_p=0.95,
                    enable_thinking=False,
                )
            ).strip()
                if len(re.sub(r"\s+", "", rescue_text)) > analysis_density:
                    analysis_text = rescue_text
                    analysis_density = len(re.sub(r"\s+", "", analysis_text))
            except Exception as error:
                errors.append(f"主体分析补写失败：{self._format_provider_error(error)}")

        if analysis_text:
            partial_content = "\n\n".join(part for part in [title, judgment, analysis_text] if part.strip())
            emit_partial("正在展开主体分析", 79.0, partial_content, judgment=judgment, analysis=analysis_text)

        try:
            actions_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{action_context}\n\n"
                        f"已有总判断：\n{judgment}\n\n"
                        "请完成回答的收束部分。"
                        "由你自己判断最自然的结束方式。"
                        "如果适合给建议、优先级或下一步，就写出来；如果不适合，就自然收束，不要强行加动作。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责完成回答的结尾。"
                    ),
                    response_schema=None,
                    timeout_seconds=14.0,
                    max_tokens=1200,
                    temperature=0.38,
                    top_p=0.94,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"建议动作失败：{self._format_provider_error(error)}")

        if not analysis_text and not actions_text:
            raise AiInvocationError("qwen", "；".join(errors) or "分阶段生成只返回了开场判断")

        assembled_parts = [title, judgment]
        if analysis_text:
            assembled_parts.append(analysis_text)
        if actions_text:
            assembled_parts.append(actions_text)
        content = "\n\n".join(part.strip() for part in assembled_parts if part and part.strip())
        emit_partial("正在整理最终成文", 91.0, content, judgment=judgment, analysis=analysis_text, actions=actions_text)
        return self._structured_from_plain_answer(content)

    def generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                return self._qwen_generate_compact_grounded_fallback(prompt, note)
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的紧凑综述。")

    def generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider in ("qwen", "doubao") and health.ready:
            try:
                return self._qwen_generate_brief_grounded_rescue(prompt, note)
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的一版简短保守回答。")

    def suggest_short_title(self, prompt: str) -> str:
        health = self.get_health()
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt=f"请将以下追踪规则提炼为 3 到 6 个字的中文标签，只返回标签本身：{prompt}",
                    system_instruction="你是中文编辑，擅长压缩标题。",
                    response_schema=None,
                    timeout_seconds=12.0,
                )
                title = str(result).strip().replace("“", "").replace("”", "")
                if title:
                    return title[:8]
        except Exception:
            pass
        cleaned = re.sub(r"[，。；：、,.!?！？\\s]+", "", prompt)
        cleaned = re.sub(r"^(关注|跟踪|追踪|围绕|关于)", "", cleaned)
        return (cleaned[:6] or "自定义雷达").strip()

    def suggest_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        health = self.get_health()
        fallback = self._fallback_topic_search_queries(title=title, prompt=prompt, time_range=time_range)
        schema = {
            "type": "OBJECT",
            "properties": {
                "queries": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                }
            },
        }
        query_prompt = (
            "请把下面的资讯追踪需求提炼成 2 到 3 条适合新闻/信息搜索的中文查询词。"
            "要求：保留核心对象、行业和技术关键词，避免空泛词。"
            "返回 JSON：{\"queries\": [\"查询1\", \"查询2\"]}。\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"时间范围：{time_range}\n"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    query_prompt,
                    "你是检索词生成助手。只返回 JSON。",
                    schema,
                    timeout_seconds=18.0,
                    max_tokens=600,
                )
                if isinstance(result, dict):
                    queries = [str(item).strip() for item in result.get("queries", []) if str(item).strip()]
                    if queries:
                        return queries[:3]
        except Exception:
            pass
        return fallback

    def shortlist_topic_search_hits(
        self,
        *,
        title: str,
        prompt: str,
        hits: list[dict[str, str]],
        max_items: int = 4,
    ) -> list[dict[str, object]]:
        if not hits:
            return []
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "index": {"type": "INTEGER"},
                            "title": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                        },
                    },
                }
            },
        }
        entries = []
        for index, hit in enumerate(hits, start=1):
            entries.append(
                "\n".join(
                    [
                        f"[{index}] 标题：{hit.get('title', '')}",
                        f"来源：{hit.get('source', '')}",
                        f"发布时间：{hit.get('publishedAt', '') or '未知'}",
                        f"摘要：{hit.get('summary', '')}",
                    ]
                )
            )
        joined_entries = "\n\n".join(entries)
        screening_prompt = (
            "你是资讯情报筛选助手。请根据雷达标题和追踪说明，从候选结果中挑选最相关的结果。"
            f"最多返回 {max_items} 条，优先保留真正相关、可转成选题候选的条目，明显跑题的不要选。"
            "title 要写成 10 到 28 个字的中文标题；如果原文不是中文，要准确翻译成中文。"
            "summary 要写成 40 到 90 字的中文摘要，适合直接落到候选池。"
            "返回 JSON：{\"items\": [{\"index\": 1, \"title\": \"...\", \"summary\": \"...\"}]}\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"候选结果：\n{joined_entries}"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    screening_prompt,
                    "你是资讯情报筛选助手。只返回 JSON。",
                    schema,
                    timeout_seconds=25.0,
                    max_tokens=1400,
                )
                if isinstance(result, dict):
                    items = result.get("items", [])
                    if isinstance(items, list):
                        return [item for item in items if isinstance(item, dict)][:max_items]
        except Exception:
            pass
        return []

    def localize_topic_hit(
        self,
        *,
        title: str,
        summary: str,
        radar_title: str,
        radar_prompt: str,
    ) -> dict[str, str]:
        cleaned_title = str(title or "").strip()
        cleaned_summary = str(summary or cleaned_title).strip() or cleaned_title
        if self._has_sufficient_cjk(cleaned_title) and self._has_sufficient_cjk(cleaned_summary):
            return {
                "title": cleaned_title[:60],
                "summary": cleaned_summary[:140],
            }
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "summary": {"type": "STRING"},
            },
        }
        prompt = (
            "请把下面这条资讯候选整理成适合内部候选池展示的中文标题和中文摘要。"
            "如果原文不是中文，请准确翻译成中文；不要编造没有出现过的事实。"
            "title 保持 10 到 28 个中文字符；summary 保持 40 到 90 个中文字符。"
            "返回 JSON：{\"title\": \"中文标题\", \"summary\": \"中文摘要\"}\n"
            f"雷达标题：{radar_title}\n"
            f"雷达说明：{radar_prompt}\n"
            f"原始标题：{cleaned_title}\n"
            f"原始摘要：{cleaned_summary}\n"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是资讯翻译编辑助手。只返回 JSON。",
                    schema,
                    timeout_seconds=20.0,
                    max_tokens=800,
                )
                if isinstance(result, dict):
                    localized_title = str(result.get("title") or "").strip()
                    localized_summary = str(result.get("summary") or "").strip()
                    if localized_title and localized_summary:
                        return {
                            "title": localized_title[:60],
                            "summary": localized_summary[:140],
                        }
        except Exception:
            pass
        fallback_title = cleaned_title[:60]
        if not self._has_sufficient_cjk(fallback_title):
            fallback_title = f"{radar_title}相关机会"
        fallback_summary = cleaned_summary[:140]
        if not self._has_sufficient_cjk(fallback_summary):
            fallback_summary = f"原始来源提到“{cleaned_title[:40]}”，建议打开原文核对后再决定是否跟进。"
        return {"title": fallback_title, "summary": fallback_summary}

    def build_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "keyPoints": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "recommendationReasons": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "practicalUses": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "editorialNote": {"type": "STRING"},
                "discussionPrompts": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
            },
        }
        prompt = (
            "请把下面这条资讯候选整理成适合内部团队阅读的中文解析。"
            "输出要求：\n"
            "1. overview 用 140 到 220 字中文，聚焦“文章本身在讲什么”，必须讲清楚文章主线、它明确提出的关键观点，以及文中出现的事实或案例线索；不要把你的评论混进这一段。\n"
            "2. keyPoints 返回 3 到 5 条，每条都是清晰完整的一句话，提炼文章作者真正表达的核心观点、方法、信号或判断，不要泛泛复述主题。\n"
            "3. recommendationReasons 返回 2 到 4 条，直接说明这东西到底解决什么问题、对谁有用、能省哪一步、能创造什么具体价值。少写空泛大词，少写“值得关注”“可以参考”。\n"
            "4. editorialNote 用 180 到 320 字中文，写成“大周自己的判断”，但口气要像一个懂产品的人在给同事讲这东西到底有什么用。先讲清楚它解决什么问题，再讲它创造什么价值，最后点出真正值得继续看的地方或局限。语气口语化、直接，不要写成新闻评论、官方口径或行业社论；少用“这反映出”“结构性变化”“专业能力民主化”这种宏大套话。\n"
            "4a. 如果材料是 GitHub 开源项目、产品 demo、工具发布或技术案例，优先回答 4 个问题：它到底替谁省事、具体省掉哪一步、为什么这一步值钱、什么情况下才真的能用。不要先从行业趋势和组织变革讲起。\n"
            "5. practicalUses 返回 2 到 4 条，改写成“可直接展开成文的角度”。每条都应该像文章切口、评论角度或分享主题，而不是待办动作。\n"
            "6. discussionPrompts 返回 2 到 4 条，写成值得继续追问的问题句，优先从产品价值、用户场景、落地门槛、替代关系和真实使用条件继续追问。\n"
            "7. 只根据现有材料输出，不要编造文章里没有出现过的事实；如果材料有限，可以做克制推断，但要避免装作已经证实。\n"
            "8. 即使原文是英文，overview、keyPoints、recommendationReasons、editorialNote、practicalUses、discussionPrompts 也必须全部输出中文。\n"
            "9. 优先提炼文章里的关键事实、方法变化、商业机会、行业门槛、组织能力要求或资源线索；不要只写“值得关注”“可以参考”这种空话。\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"组织 DNA：{organization_context[:1400] or '未提供'}\n"
            f"原文摘录：{(source_content or '未抓到原文全文，只有标题和摘要。')[:4200]}"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是资讯研判助手。只返回 JSON。",
                    schema,
                    timeout_seconds=28.0,
                    max_tokens=1800,
                )
                if isinstance(result, dict):
                    normalized = self._normalize_topic_candidate_insight_payload(result)
                    if normalized["keyPoints"]:
                        return self._localize_topic_insight_payload(
                            normalized,
                            candidate_title=candidate_title,
                            candidate_summary=candidate_summary,
                            source=source,
                            published_at=published_at,
                            source_url=source_url,
                            source_content=source_content,
                        )
        except Exception:
            pass
        fallback = self._fallback_topic_candidate_insight(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )
        return self._localize_topic_insight_payload(
            fallback,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )

    # ── Growth insight quote distillation ────────────────────────────────
    def distill_growth_insight_quote(
        self,
        *,
        task_title: str,
        task_desc: str = "",
        client_name: str = "",
        event_line_name: str = "",
        blocker: str = "",
        next_action: str = "",
        recent_decision: str = "",
        context_summary: str = "",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, str]:
        """Distil raw task/review context into a concise, quotable 金句 (insight quote).

        Returns {"quote": "...", "source_label": "..."}.
        The quote should be a standalone insight sentence (≤80 chars ideally)
        that captures transferable work wisdom — like the preview mock data:
          "让客户先交完整方案再提问题，比直接帮改方案更有效——陪伴的核心是不代偿。"
        """
        health = self.get_health()
        raw_material = "\n".join(
            part
            for part in [
                f"任务标题：{task_title}",
                f"任务描述：{task_desc}" if task_desc else "",
                f"客户名称：{client_name}" if client_name else "",
                f"事件线名称：{event_line_name}" if event_line_name else "",
                f"当前阻碍：{blocker}" if blocker else "",
                f"下一步行动：{next_action}" if next_action else "",
                f"最近判断：{recent_decision}" if recent_decision else "",
                f"背景摘要：{context_summary}" if context_summary else "",
                f"证据参考：{'、'.join(evidence_refs)}" if evidence_refs else "",
            ]
            if part
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "quote": {"type": "STRING"},
                "sourceLabel": {"type": "STRING"},
            },
        }

        prompt = (
            "你是一位经验萃取专家。请从下面的任务工作材料中，提炼出一句经验金句。\n\n"
            "要求：\n"
            "1. 金句必须是一句完整的、可独立引用的话，30~80个字为佳，最多不超过100字。\n"
            '2. 金句要传达一个可迁移的工作智慧或判断，而非陈述事实（不要写「完成了XX」「推进了XX」）。\n'
            "3. 风格参考：\n"
            "   - 让客户先交完整方案再提问题，比直接帮改方案更有效——陪伴的核心是不代偿。\n"
            "   - 数字化理解快的客户，效率瓶颈往往不在技术而在项目设计。\n"
            "   - 月捐人流失率最高的阶段不是首月，而是第三个月——这是承诺感消退的临界点。\n"
            "   - 合作方的节奏感比能力更重要，节奏对不上的合作最终都会变成消耗。\n"
            "4. 金句应该像一个有经验的从业者的口头心得，朴实直接，不要写成口号或鸡汤。\n"
            "5. 如果材料信息不足以提炼出有价值的洞察，就从任务的核心动作中找到一个可迁移的方法论视角。\n"
            "6. sourceLabel 写一个简短的来源标注，格式如「客户名·阶段」或「事件线名·W周数」，5~15字。\n\n"
            f"原始工作材料：\n{raw_material}"
        )

        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是组织经验萃取助手。只返回 JSON。",
                    schema,
                    timeout_seconds=15.0,
                    max_tokens=300,
                    temperature=0.7,
                )
                if isinstance(result, dict):
                    quote = str(result.get("quote") or "").strip().strip('"')
                    source_label = str(result.get("sourceLabel") or "").strip()
                    if quote and len(quote) >= 10:
                        return {"quote": quote, "sourceLabel": source_label}
        except Exception:
            pass

        # Fallback: use task_title as-is
        return {"quote": "", "sourceLabel": ""}

    def build_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        today_iso = datetime.now().date().isoformat()
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "tasks": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "desc": {"type": "STRING"},
                            "dueDate": {"type": "STRING"},
                            "ddl": {"type": "STRING"},
                            "note": {"type": "STRING"},
                            "priority": {"type": "STRING"},
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            },
                        },
                    },
                },
            },
        }
        prompt = (
            "请根据下面的资讯候选，拆成可以直接派给同事执行的中文任务清单。"
            "输出要求：\n"
            "1. overview 用 40 到 90 字中文说明这条机会为什么值得跟进。\n"
            "2. tasks 返回 1 到 6 条可执行任务，title 必须是具体动作，不要写空泛标题。\n"
            "3. desc 用一句中文说明交付物或动作标准。\n"
            "4. dueDate 只有在材料里出现明确截止日期或时间时才填写 YYYY-MM-DD，否则留空字符串。\n"
            "5. ddl 用中文简短表达，如“3月17日前”“本周内”“待确认”。\n"
            "6. note 写补充说明，包含来源线索、限制条件或需要特别注意的点，并明确这条任务对应的推荐理由或判断依据。\n"
            "7. priority 只能是 low、normal、high。\n"
            "8. tags 返回 1 到 3 个中文标签。\n"
            "9. 任务优先从 recommendationReasons 和 practicalUses 延展开来，避免与推荐理由无关的空泛动作。\n"
            "请只根据已知材料输出，不要编造不存在的要求。\n"
            f"今天日期：{today_iso}\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"组织 DNA：{organization_context[:1400] or '未提供'}\n"
            f"候选解析综述：{str((candidate_insight or {}).get('overview') or '无')}\n"
            f"主要内涵：{'；'.join(str(item) for item in (candidate_insight or {}).get('keyPoints', [])[:6]) or '无'}\n"
            f"推荐理由：{'；'.join(str(item) for item in (candidate_insight or {}).get('recommendationReasons', [])[:4]) or '无'}\n"
            f"实用方向：{'；'.join(str(item) for item in (candidate_insight or {}).get('practicalUses', [])[:4]) or '无'}\n"
            f"原文摘录：{(source_content or '未抓到原文全文，只有标题和摘要。')[:3600]}"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是项目执行拆解助手。只返回 JSON。",
                    schema,
                    timeout_seconds=28.0,
                    max_tokens=1800,
                )
                if isinstance(result, dict):
                    normalized = self._normalize_topic_task_plan_payload(result)
                    if normalized["tasks"]:
                        return normalized
        except Exception:
            pass
        return self._fallback_topic_task_plan(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
            candidate_insight=candidate_insight,
        )

    def suggest_task_tags(
        self,
        *,
        title: str,
        desc: str,
        collaborator_names: list[str],
        due_date: str | None,
        module: str,
    ) -> list[str]:
        health = self.get_health()
        prompt = (
            "请根据下面的任务信息，提炼 1 到 3 个简短中文标签。"
            "标签必须具体可读，不要输出“事务、工作、内容、处理”这种空泛词。"
            "只返回 JSON，格式为 {\"tags\": [\"标签1\", \"标签2\"]}。\n"
            f"标题：{title}\n"
            f"描述：{desc or '无'}\n"
            f"协作对象：{'、'.join(collaborator_names) or '无'}\n"
            f"截止日期：{due_date or '未设置'}\n"
            f"所属模块：{module}\n"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt=prompt,
                    system_instruction="你是任务标签编辑助手。只返回 JSON。",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            }
                        },
                    },
                    timeout_seconds=18.0,
                )
                if isinstance(result, dict):
                    tags = [str(item).strip() for item in result.get("tags", []) if str(item).strip()]
                    if tags:
                        return tags[:3]
        except Exception:
            pass

        fallback_tags: list[str] = []
        text = f"{title} {desc}"
        mapping = [
            ("会议", ["会议", "复盘", "纪要"]),
            ("客户沟通", ["客户", "沟通", "访谈"]),
            ("材料整理", ["材料", "文档", "整理", "汇总"]),
            ("审核", ["审核", "审批", "确认"]),
            ("汇报", ["汇报", "报告", "简报", "ppt"]),
            ("高优先级", ["紧急", "高优", "优先"]),
            ("本周完成", ["本周", "周五", "周内"]),
        ]
        for label, keywords in mapping:
            if any(keyword.lower() in text.lower() for keyword in keywords) and label not in fallback_tags:
                fallback_tags.append(label)
        if due_date and not fallback_tags:
            fallback_tags.append("待确认")
        if not fallback_tags:
            fallback_tags = ["跟进中"]
        return fallback_tags[:3]

    def _normalize_topic_task_plan_payload(self, payload: dict[str, object]) -> dict[str, object]:
        overview = str(payload.get("overview") or "").strip()
        raw_tasks = payload.get("tasks", [])
        tasks: list[dict[str, object]] = []
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                due_date = self._normalize_due_date_value(item.get("dueDate"))
                ddl = str(item.get("ddl") or "").strip()
                tasks.append(
                    {
                        "title": title[:60],
                        "desc": str(item.get("desc") or "").strip()[:180],
                        "dueDate": due_date,
                        "ddl": ddl or (self._label_due_date(due_date) if due_date else "待确认"),
                        "note": str(item.get("note") or "").strip()[:280],
                        "priority": self._normalize_priority(item.get("priority")),
                        "tags": [
                            str(tag).strip()[:16]
                            for tag in item.get("tags", [])
                            if str(tag).strip()
                        ][:3]
                        if isinstance(item.get("tags"), list)
                        else [],
                    }
                )
        return {
            "overview": overview[:140],
            "tasks": tasks,
        }

    def _normalize_topic_candidate_insight_payload(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "overview": str(payload.get("overview") or "").strip()[:420],
            "keyPoints": self._normalize_string_list(payload.get("keyPoints"), max_items=6, max_length=220),
            "recommendationReasons": self._normalize_string_list(payload.get("recommendationReasons"), max_items=4, max_length=180),
            "practicalUses": self._normalize_string_list(payload.get("practicalUses"), max_items=4, max_length=160),
            "editorialNote": str(payload.get("editorialNote") or "").strip()[:520],
            "discussionPrompts": self._normalize_string_list(payload.get("discussionPrompts"), max_items=4, max_length=180),
        }

    def _enrich_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._looks_like_weak_topic_material(candidate_title, candidate_summary, source_content):
            source_hint = self._extract_topic_source_hint(candidate_title, candidate_summary)
            normalized["overview"] = (
                f"一、当前判断：这条候选暂时不能被当成一篇有效行业文章来解读。现有材料只显示原始来源提到了“{source_hint}”，"
                "更像是搜索结果误抓到的索引页、行情页或无关网页，而不是围绕当前雷达主题展开的正文内容。\n"
                "二、为什么不能直接使用：现在没有足够可靠的正文信息可供提炼，因此无法负责任地总结它的主要观点，也无法证明它对团队真的有实际价值。"
                "如果继续基于这条候选拆任务，后续执行方向很容易被带偏。\n"
                "三、对团队最有价值的动作：先复核来源链接、确认是否误抓取，并在必要时删除、归档或重新抓取更相关的中文文章；这比继续围绕一条错候选展开讨论更重要。"
            )[:420]
            normalized["keyPoints"] = [
                "当前没有抓到足够可靠的正文内容，现有信息不足以支持严肃的主题研判。",
                "候选里出现的线索更像搜索误抓到的索引页或无关页面，不像真正围绕雷达主题展开的文章。",
                "如果继续基于这条结果拆任务，后续执行方向很容易被带偏。",
            ]
            normalized["recommendationReasons"] = [
                "先识别并拦住误抓取结果，本身就是保证情报质量的重要一步。",
                "这条结果反过来说明当前雷达关键词或过滤规则还需要继续收紧。",
            ]
            normalized["practicalUses"] = [
                "把这次误抓取写成一篇“为什么情报系统容易被噪音带偏”的方法反思。",
                "围绕“如何判断一条线索是否值得进入候选池”整理一套内部筛选标准。",
                "把这条错候选当成案例，讨论应该怎样收紧雷达描述、时间窗和优先网址策略。",
            ]
            normalized["editorialNote"] = (
                "真正值得警惕的不是这条候选本身，而是它暴露出的情报系统误抓风险。"
                "当抓取链路把索引页、无关页或弱线索误当成正文时，团队后续的判断、讨论甚至任务安排都会建立在错误底稿上。"
                "这提醒我们：高质量情报站不仅要会抓，还要会及时识别噪音、收紧规则，并把“为什么这条内容不值得看”也沉淀成方法论。"
            )[:520]
            normalized["discussionPrompts"] = [
                "这条候选是因为搜索词过宽、时间窗失效，还是站点解析规则不准才进入候选池？",
                "如果以后再遇到类似噪音，系统应该在哪一层把它挡掉，而不是等人工兜底？",
                "哪些判断信号可以帮助我们更早识别“看起来像资讯、其实不是正文”的结果？",
            ]
            return normalized

        overview = str(normalized.get("overview") or "").strip()
        filtered_key_points = [
            item for item in normalized["keyPoints"]
            if not self._looks_like_topic_noise(item, candidate_title)
        ]
        if not filtered_key_points:
            filtered_key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if filtered_key_points:
            normalized["keyPoints"] = filtered_key_points[:6]

        summary_text = ""
        if self._has_sufficient_cjk(candidate_summary) and not self._looks_like_topic_noise(candidate_summary, candidate_title):
            summary_text = self._compact_topic_sentence(candidate_summary, 180)
        elif filtered_key_points:
            summary_text = "；".join(self._compact_topic_sentence(item, 90) for item in filtered_key_points[:2])
        elif overview and not self._looks_generic_topic_overview(overview):
            summary_text = self._compact_topic_sentence(overview, 180)
        else:
            summary_text = f"这篇内容围绕“{candidate_title[:32]}”展开，当前抓到的材料显示它更关注该主题背后的关键事实、方法线索或可执行信息。"

        key_points = normalized["keyPoints"][:3]
        point_text = "；".join(self._compact_topic_sentence(item, 110) for item in key_points) if key_points else "当前提炼结果尚未形成足够具体的文章观点。"

        reasons = normalized["recommendationReasons"][:2]
        reason_text = "；".join(self._compact_topic_sentence(item, 90) for item in reasons) if reasons else "需要进一步核对原文后再决定是否值得跟进。"

        normalized["overview"] = (
            f"一、这篇内容主要讲什么：{summary_text}\n"
            f"二、文章里最值得抓住的观点：{point_text}\n"
            f"三、它对团队的实际价值：{reason_text}"
        )[:420]
        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        source_sentences = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        editorial_note = str(normalized.get("editorialNote") or "").strip()
        generic_editorial_note = self._looks_generic_topic_editorial_note(editorial_note)
        needs_grounded_editorial_note = not editorial_note or len(editorial_note) < 120 or generic_editorial_note
        if needs_grounded_editorial_note:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                editorial_note = (
                    "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                    "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                    "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
                )
            elif re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                    "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                    "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
                )
            elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
                editorial_note = (
                    "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                    "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                    "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
                )
                discussion_prompts = [
                    "这个项目最核心是在替用户省哪一步麻烦？",
                    "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                    "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                    "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                    "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
                )
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                    "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                    "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
                )
                discussion_prompts = [
                    "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                    "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                    "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
                ]
            else:
                editorial_note = (
                    "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                    "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                    "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
                )
        if needs_grounded_editorial_note:
            editorial_note = self._build_grounded_topic_editorial_note(
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
                fallback=editorial_note,
            )
        normalized["editorialNote"] = editorial_note[:520]

        writing_angles = normalized["practicalUses"][:4]
        if not writing_angles:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                writing_angles = [
                    "从这篇文章切入，讨论资助方正在通过哪些信号重新定义“值得支持的机构能力”。",
                    "围绕机会线索背后的门槛变化，写一篇“为什么现在的申报竞争越来越像能力审计”的评论。",
                    "把文章中的项目要求、叙事方式和材料标准拆开，整理成机构如何准备外部合作窗口的参考框架。",
                ]
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                writing_angles = [
                    "以这篇案例为切口，分析 AI 工具正在怎样改写咨询、研发或知识工作的专业分工。",
                    "围绕“从提效工具到业务机会”的跃迁，写一篇 AI 落地为何开始重塑服务边界的评论。",
                    "把文中的落地案例拆成组织能力、流程变化和商业价值三层，形成内部分享主题。",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                writing_angles = [
                    "围绕文章中的筹资或传播案例，写一篇公众注意力变化如何倒逼组织改写叙事方式的评论。",
                    "把文中方法放进更长的品牌建设周期里，讨论短期转化与长期关系之间的张力。",
                    "从捐赠人或公众视角重写这篇内容，分析他们真正被什么样的组织表达打动。",
                ]
            else:
                writing_angles = [
                    "以这篇文章为起点，写一篇“表面信息之下更值得关注的结构性变化”评论。",
                    "把文章中的案例、判断和门槛拆开，形成一篇更适合团队内部讨论的前哨短文。",
                    "围绕文中最容易被忽略的一条信号，展开成更完整的行业观察或方法反思。",
                ]
        normalized["practicalUses"] = writing_angles[:4]

        discussion_prompts = normalized["discussionPrompts"][:4]
        if not discussion_prompts or generic_editorial_note:
            if re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                discussion_prompts = [
                    "这篇文章提到的能力变化，哪些会真正改变团队的服务方式，哪些只是表层提效？",
                    "如果这些案例持续增多，团队的专业壁垒未来应该建立在什么地方？",
                    "文章里的落地路径是否依赖特定组织条件，还是已经具备可迁移性？",
                ]
            elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                discussion_prompts = [
                    "这篇内容反映的资助偏好变化，和我们当前项目准备方式之间有哪些错位？",
                    "如果要把这类窗口真正抓住，机构最缺的是材料、证据、叙事能力还是执行能力？",
                    "文章里的要求是一次性门槛，还是说明外部评估标准正在长期变化？",
                ]
            else:
                discussion_prompts = [
                    "这篇文章表面的信息背后，真正值得继续追问的结构性变化是什么？",
                    "如果把这条线索放进更长的时间线上看，它说明判断标准正在怎样变化？",
                    "文章里的观点对团队当前工作最有启发的一层，不是事实本身，而是什么？",
                ]
        if generic_editorial_note or not discussion_prompts:
            discussion_prompts = self._build_grounded_topic_discussion_prompts(
                candidate_title=candidate_title,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
            )
        normalized["discussionPrompts"] = discussion_prompts[:4]
        return normalized

    def _localize_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._topic_insight_is_chinese(normalized):
            return self._enrich_topic_insight_payload(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        health = self.get_health()
        if not health.ready or health.provider == "mock":
            return self._fallback_localized_topic_insight(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "keyPoints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "recommendationReasons": {"type": "ARRAY", "items": {"type": "STRING"}},
                "practicalUses": {"type": "ARRAY", "items": {"type": "STRING"}},
                "editorialNote": {"type": "STRING"},
                "discussionPrompts": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        prompt = (
            "请把下面这份资讯解析改写成自然、准确、完整的中文版本。"
            "要求：\n"
            "1. overview、keyPoints、recommendationReasons、practicalUses、editorialNote、discussionPrompts 必须全部是中文。\n"
            "1a. overview 必须展开写，至少 140 字，清楚交代文章主旨、主要观点和对团队的价值，不要只写一句结论。\n"
            "1b. editorialNote 必须改成口语化、像产品经理跟同事解释价值的说法。至少 180 字，优先讲清楚它解决什么问题、给谁省了什么、为什么现在值得看，以及落地会卡在哪。不要写成新闻评论、官样文章或宏大社论。\n"
            "1c. 如果内容是 GitHub 开源项目、技术工具或新产品，直接用“它到底替用户省了哪一步麻烦、为什么这一步值钱”来改写，不要先讲行业趋势或大词判断。\n"
            "2. 可以结合候选标题、摘要和原文摘录，把过于泛的地方改得更具体，但不能编造事实。\n"
            "3. keyPoints 重点提炼文章真正有价值的信息点；recommendationReasons 要写得更像“这个东西到底有啥用”；practicalUses 改写成可直接成文的角度；discussionPrompts 改写成值得继续追问的问题。\n"
            "4. 返回 JSON，不要输出解释。\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"原文摘录：{(source_content or '暂无原文摘录。')[:3600]}\n"
            f"当前解析 overview：{normalized['overview']}\n"
            f"当前解析 keyPoints：{'；'.join(normalized['keyPoints']) or '无'}\n"
            f"当前解析 recommendationReasons：{'；'.join(normalized['recommendationReasons']) or '无'}\n"
            f"当前解析 practicalUses：{'；'.join(normalized['practicalUses']) or '无'}\n"
            f"当前解析 editorialNote：{normalized['editorialNote'] or '无'}\n"
            f"当前解析 discussionPrompts：{'；'.join(normalized['discussionPrompts']) or '无'}"
        )
        try:
            result = self._qwen_generate(
                prompt,
                "你是资讯翻译与提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=24.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                localized = self._normalize_topic_candidate_insight_payload(result)
                if self._topic_insight_is_chinese(localized):
                    return self._enrich_topic_insight_payload(
                        localized,
                        candidate_title=candidate_title,
                        candidate_summary=candidate_summary,
                        source=source,
                        source_content=source_content,
                    )
        except Exception:
            pass
        return self._fallback_localized_topic_insight(
            normalized,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _normalize_string_list(self, value: object, *, max_items: int, max_length: int) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text or text in items:
                continue
            items.append(text[:max_length])
            if len(items) >= max_items:
                break
        return items

    def _fallback_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        raw_text = "\n".join(part for part in [candidate_summary, source_content] if part).strip() or candidate_title
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", raw_text)
            if segment.strip()
        ]
        key_points: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 8:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text not in key_points:
                key_points.append(text[:150])
            if len(key_points) >= 4:
                break
        if not key_points:
            key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if not key_points:
            summary_candidate = candidate_summary[:150] if candidate_summary and not self._looks_like_topic_noise(candidate_summary, candidate_title) else ""
            key_points = [summary_candidate or candidate_title]

        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        recommendation_reasons: list[str] = []
        practical_uses: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容直接对应大模型落地中的真实安全与合规问题，适合帮助团队判断哪些风险需要在项目推进前就前置处理。",
                "如果文章把风险场景、防护机制和治理路径讲得足够具体，就能为团队制定内部安全要求、供应商评估标准或试点边界提供参考。",
            ]
            practical_uses = [
                "围绕风险治理前置这件事，写一篇大模型项目为何不能只看功能上线的评论。",
                "把文章中的风险案例拆成“场景、后果、治理动作”，形成一篇安全观察短文。",
                "从供应商评估或项目边界切入，讨论安全要求如何变成业务落地门槛。",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能对应真实的资金、合作或项目申报窗口，值得尽快判断是否匹配当前机构需求。",
                "文章里通常会带出申请条件、截止时间或所需资料，对团队推进资源争取有直接帮助。",
            ]
            practical_uses = [
                "从这条线索切入，写一篇资助窗口背后正在怎样重写机构能力评估标准的评论。",
                "把文中的门槛、主题和材料要求拆开，形成一篇“为什么申报越来越像能力审计”的文章提纲。",
                "围绕外部机会与内部准备之间的错位，整理成一次团队内部讨论分享。",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容更像方法或案例信号，可以帮助团队快速理解同类组织在技术上的真实落地方式。",
                "如果文章提到具体做法、流程或产品选择，适合沉淀成内部学习资料或试点清单。",
            ]
            practical_uses = [
                "以这篇案例为切口，分析 AI 工具为什么开始改变专业工作的交付边界。",
                "把文中的落地路径拆成能力变化、流程变化和商业变化，形成一篇前哨观察。",
                "围绕“AI 从提效走向重构工作流”写一篇更适合对外分享的评论框架。",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能反映筹资或传播领域的新打法，适合用于调整当前团队的外部沟通策略。",
                "如果文章包含案例和结果数据，能直接帮助判断哪些动作值得试做或复盘。",
            ]
            practical_uses = [
                "从公众注意力变化切入，写一篇筹资与传播为什么正在失去旧有默认打法的评论。",
                "把文章中的案例放进更长的品牌建设周期里，形成一篇方法反思。",
                "围绕捐赠人关系如何被重新定义，整理成团队内部研讨的切口。",
            ]
        else:
            recommendation_reasons = [
                "这条内容提供了可继续追踪的行业线索，值得先判断它是否与当前项目方向相关。",
                "如果文中包含可验证的信息点或案例，适合先沉淀成内部参考，再决定是否进一步投入。",
            ]
            practical_uses = [
                "把文章里最值得抓住的一条变化展开，写成一篇前哨式短评。",
                "从案例背后的结构性变化切入，整理成一次团队内部讨论发言。",
                "围绕文中最容易被忽略的一条判断，形成后续选题角度。",
            ]

        overview_seed = ""
        if self._has_sufficient_cjk(candidate_summary):
            overview_seed = candidate_summary[:90]
        elif key_points and self._has_sufficient_cjk(key_points[0]):
            overview_seed = key_points[0][:90]

        if overview_seed:
            overview = f"这篇内容主要围绕“{candidate_title[:28]}”展开，重点提到：{overview_seed}"
        else:
            overview = (
                f"这条内容来自 {source}，核心价值在于它不只是提供资讯本身，"
                f"还带出了可供团队学习、判断机会或补充资源的具体线索。"
            )
            if published_at:
                overview += f" 发布时间为 {published_at[:10]}。"
        if source_url and not practical_uses:
            practical_uses.append("把原文里的关键信号和边界条件拆开，形成一篇更完整的评论角度。")

        editorial_note = ""
        discussion_prompts: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
            )
            discussion_prompts = [
                "这里提到的风险，哪些已经是我们当前项目必须先回答的？",
                "如果真要落地，最容易卡住的会是权限、流程还是责任归属？",
                "哪些治理要求应该在项目启动前就讲清楚，而不是等出事后再补？",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            editorial_note = (
                "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
            )
            discussion_prompts = [
                "这篇内容真正告诉我们的，是机会本身，还是资方的筛选标准？",
                "如果要去争取这类窗口，我们最缺的是材料、证据，还是项目逻辑？",
                "这里面哪些要求是一次性门槛，哪些是长期的能力要求？",
            ]
        elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
            editorial_note = (
                "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
            )
            discussion_prompts = [
                "这个项目最核心是在替用户省哪一步麻烦？",
                "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
            )
            discussion_prompts = [
                "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            editorial_note = (
                "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
            )
            discussion_prompts = [
                "它解决的更像短期转化问题，还是长期关系问题？",
                "如果真照着做，最先要改的是内容、渠道，还是关系维护方式？",
                "这篇内容背后真正变了的，是传播动作，还是公众判断标准？",
            ]
        else:
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
            )
            discussion_prompts = [
                "它真正解决的问题到底是什么，而不是表面在说什么？",
                "如果真把它用起来，最先会改掉的是哪一步旧流程？",
                "这条线索最值得继续核实的，不是新闻本身，而是哪种实际价值？",
            ]

        return {
            "overview": overview[:180],
            "keyPoints": key_points[:4],
            "recommendationReasons": recommendation_reasons[:4],
            "practicalUses": practical_uses[:4],
            "editorialNote": editorial_note[:520],
            "discussionPrompts": discussion_prompts[:4],
        }

    def _fallback_localized_topic_insight(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        overview = normalized["overview"]
        if not self._has_sufficient_cjk(overview):
            summary_hint = candidate_summary if self._has_sufficient_cjk(candidate_summary) else ""
            overview = (
                summary_hint
                or f"这条内容来自 {source}，主题围绕“{candidate_title[:40]}”，建议结合原文继续核对关键细节与可执行线索。"
            )[:180]

        key_points = [item for item in normalized["keyPoints"] if self._has_sufficient_cjk(item)]
        if not key_points:
            if self._has_sufficient_cjk(candidate_summary):
                key_points = [candidate_summary[:150]]
            else:
                key_points = [f"文章主要围绕“{candidate_title[:40]}”展开，建议结合原文核对更具体的信息点。"]

        recommendation_reasons = [item for item in normalized["recommendationReasons"] if self._has_sufficient_cjk(item)]
        if not recommendation_reasons:
            recommendation_reasons = [
                "这条内容提到了值得继续核实的信息点，适合先判断是否与当前工作方向相关。",
                "如果原文包含具体案例、门槛或资源线索，适合沉淀成内部参考后再决定是否推进。",
            ]

        practical_uses = [item for item in normalized["practicalUses"] if self._has_sufficient_cjk(item)]
        if not practical_uses:
            practical_uses = [
                "把文章里最有价值的一条观点展开成一篇短评，解释它为什么不只是个案。",
                "围绕文中提到的方法或案例，写一篇更适合团队内部分享的前哨观察。",
                "从文章最容易被忽略的一条信号切入，形成一个可继续讨论的写作角度。",
            ]

        editorial_note = str(normalized.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最有用的地方不是再复述一遍新闻，而是先说清楚它到底解决什么问题。"
                "它有没有帮人省步骤、降门槛、提效率，或者把原来很难做的一件事变得更容易，这些才是大周更在意的。"
                "所以比起写成评论稿，我更想把它讲成人话：这东西值不值得看，关键就看它到底有没有把某个具体麻烦真的做薄。"
            )[:520]

        discussion_prompts = [item for item in normalized["discussionPrompts"] if self._has_sufficient_cjk(item)]
        if not discussion_prompts:
            discussion_prompts = [
                "这篇文章最值得继续追问的变化，不是事实本身，而是什么？",
                "如果把文章里的案例放进更长时间线里看，它预示了怎样的结构性变化？",
                "文中的观点对团队当前判断最有用的一层，究竟是方法、趋势，还是门槛变化？",
            ]

        return self._enrich_topic_insight_payload(
            {
                "overview": overview,
                "keyPoints": key_points[:6],
                "recommendationReasons": recommendation_reasons[:4],
                "practicalUses": practical_uses[:4],
                "editorialNote": editorial_note,
                "discussionPrompts": discussion_prompts[:4],
            },
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _fallback_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_text = "\n".join(
            part for part in [candidate_title, candidate_summary, source_content] if part
        )
        due_date = self._extract_due_date_from_text(raw_text)
        deadline_label = self._label_due_date(due_date) if due_date else ("待确认" if re.search(r"(截止|deadline|due|截至|报名时间)", raw_text, re.I) else "本周内")
        insight_overview = str((candidate_insight or {}).get("overview") or "").strip()
        recommendation_reasons = self._normalize_string_list((candidate_insight or {}).get("recommendationReasons"), max_items=4, max_length=160)
        practical_uses = self._normalize_string_list((candidate_insight or {}).get("practicalUses"), max_items=4, max_length=100)
        overview = insight_overview or f"这条线索来自 {source}，建议先核对机会要求、准备材料，并尽快确认是否进入正式推进。"
        note_prefix = f"来源：{source}"
        if published_at:
            note_prefix += f"；发布时间：{published_at[:10]}"
        if source_url:
            note_prefix += f"；链接：{source_url}"

        if practical_uses:
            tasks: list[dict[str, object]] = []
            for index, action in enumerate(practical_uses[:3]):
                reason = recommendation_reasons[min(index, len(recommendation_reasons) - 1)] if recommendation_reasons else "这条内容值得继续跟进。"
                due = due_date if index == len(practical_uses[:3]) - 1 else None
                tasks.append(
                    {
                        "title": action[:60],
                        "desc": f"围绕“{reason[:36]}”完成这项动作，并把结论回写到任务记录里。",
                        "dueDate": due,
                        "ddl": deadline_label if due else ("今天" if index == 0 else "本周内"),
                        "note": f"{note_prefix}；关联理由：{reason}",
                        "priority": "high" if index == 0 else "normal",
                        "tags": ["资讯跟进", "选题解析"][:2],
                    }
                )
            return {
                "overview": overview,
                "tasks": tasks,
            }

        funding_like = bool(re.search(r"(资助|申报|申请|基金|grant|征集|招募|报名)", raw_text, re.I))
        if funding_like:
            tasks = [
                {
                    "title": "核对资助要求并确认申报策略",
                    "desc": "确认申请条件、资助方向、所需材料和内部是否值得申报。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先判断这条机会与机构当前项目是否匹配。",
                    "priority": "high",
                    "tags": ["机会评估", "资助申报"],
                },
                {
                    "title": "整理机构资料与证明材料",
                    "desc": "准备机构简介、项目案例、预算说明和过往成果等申报材料。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把历史案例和证明文件统一整理成可提交版本。",
                    "priority": "normal",
                    "tags": ["材料准备"],
                },
                {
                    "title": "撰写并提交申请材料",
                    "desc": "根据要求完成申请表和附件填写，并在截止前完成提交。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；若原文有明确截止时间，请以原文时间为准。",
                    "priority": "high",
                    "tags": ["申请提交"],
                },
            ]
        else:
            tasks = [
                {
                    "title": "确认这条机会的适配性与优先级",
                    "desc": "梳理核心要求、适用对象和推进价值，判断是否值得继续投入。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先完成机会评估，再决定后续动作。",
                    "priority": "normal",
                    "tags": ["机会评估"],
                },
                {
                    "title": "整理对外沟通或执行所需材料",
                    "desc": "准备介绍材料、案例、联系人信息或内部决策依据，形成可执行包。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把分散资料归并成一份可交接材料。",
                    "priority": "normal",
                    "tags": ["材料整理"],
                },
                {
                    "title": "安排后续跟进并记录下一步",
                    "desc": "明确谁来推进、何时反馈，以及是否需要在截止前提交或报名。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；如果原文没有明确截止时间，请在备注里补齐。",
                    "priority": "normal",
                    "tags": ["后续跟进"],
                },
            ]
        return {
            "overview": overview,
            "tasks": tasks,
        }

    def _normalize_due_date_value(self, value: object) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text
        return self._extract_due_date_from_text(text)

    def _extract_due_date_from_text(self, text: str) -> str | None:
        today = datetime.now().date()
        direct = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if direct:
            return direct.group(1)
        zh_match = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", text)
        if zh_match:
            year = int(zh_match.group(1) or today.year)
            month = int(zh_match.group(2))
            day = int(zh_match.group(3))
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        en_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:,\s*(20\d{2}))?",
            text,
            re.I,
        )
        if en_match:
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "sept": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map[en_match.group(1).lower()]
            day = int(en_match.group(2))
            year = int(en_match.group(3) or today.year)
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        return None

    def _label_due_date(self, due_date: str | None) -> str:
        if not due_date:
            return "待确认"
        try:
            date = datetime.fromisoformat(due_date).date()
        except ValueError:
            return due_date
        return f"{date.month}月{date.day}日前"

    def _normalize_priority(self, value: object) -> str:
        text = str(value or "normal").strip().lower()
        return text if text in {"low", "normal", "high"} else "normal"

    def _has_sufficient_cjk(self, text: str) -> bool:
        matches = re.findall(r"[\u4e00-\u9fff]", text or "")
        return len(matches) >= 4

    def _topic_insight_is_chinese(self, payload: dict[str, object]) -> bool:
        overview = str(payload.get("overview") or "").strip()
        if not self._has_sufficient_cjk(overview):
            return False
        editorial_note = str(payload.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            return False
        for key in ("keyPoints", "recommendationReasons", "practicalUses", "discussionPrompts"):
            values = payload.get(key)
            if not isinstance(values, list) or not values:
                return False
            if any(not self._has_sufficient_cjk(str(item)) for item in values):
                return False
        return True

    def _looks_like_topic_noise(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        noise_patterns = (
            "点赞",
            "收藏",
            "评论",
            "关注",
            "打开知乎",
            "下载app",
            "下载App",
            "APP",
            "上一页",
            "下一页",
        )
        if self._is_title_like_topic_text(text, candidate_title):
            return True
        if any(pattern.lower() in compact.lower() for pattern in noise_patterns):
            return True
        if re.search(r"(?:https?://|www\.|\.com\b|\.net\b|\.cn\b)", text.lower()) and len(compact) < 140:
            return True
        if title_compact and compact.count(title_compact[:12]) >= 2:
            return True
        return False

    def _is_title_like_topic_text(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        if not compact or not title_compact:
            return False
        if compact == title_compact:
            return True
        if title_compact in compact and abs(len(compact) - len(title_compact)) <= 18:
            return True
        return False

    def _extract_topic_source_sentences(self, source_content: str, candidate_title: str, *, max_items: int) -> list[str]:
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", source_content or "")
            if segment.strip()
        ]
        items: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 10:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text in items:
                continue
            items.append(text[:180])
            if len(items) >= max_items:
                break
        return items

    def _looks_like_weak_topic_material(self, candidate_title: str, candidate_summary: str, source_content: str) -> bool:
        summary = (candidate_summary or "").strip()
        title = (candidate_title or "").strip()
        if "原始来源提到" in summary:
            return True
        if "相关机会" in title and not source_content:
            return True
        if not source_content and not self._has_sufficient_cjk(summary) and re.search(r"[A-Za-z]{8,}", title):
            return True
        return False

    def _extract_topic_source_hint(self, candidate_title: str, candidate_summary: str) -> str:
        match = re.search(r"原始来源提到“([^”]+)”", candidate_summary or "")
        if match:
            return match.group(1).strip()[:80]
        return (candidate_title or "未知来源").strip()[:80]

    def _looks_generic_topic_overview(self, overview: str) -> bool:
        text = (overview or "").strip()
        generic_phrases = (
            "核心价值在于它不只是提供资讯本身",
            "带出了可供团队学习",
            "建议结合原文继续核对关键细节",
            "值得继续跟进",
        )
        if len(text) < 90:
            return True
        return any(phrase in text for phrase in generic_phrases)

    def _looks_generic_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        if not text:
            return True
        generic_phrases = (
            "如果把这个 GitHub 项目当成一个产品来看",
            "如果把这篇东西当成产品在看",
            "如果把这篇内容当成一个产品线索来看",
            "如果把这类信息当成一个产品线索来看",
            "如果把这篇内容当成一个增长问题来看",
            "如果把这篇东西当成产品问题来看",
            "它真正值钱的地方，通常也不是功能清单有多长",
            "它最值得看的价值，也不是多了一个新功能",
            "对大周来说，这才是它的实用价值",
        )
        return any(phrase in text for phrase in generic_phrases)

    def _looks_stale_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        stale_phrases = (
            "这篇内容背后更重要的信号",
            "真正值得深想的",
            "更深层的意义",
            "结构性变化",
            "默认做法正在被重写",
            "专业能力民主化",
            "大周自己的写作因此不会停留在复述新闻",
            "背后不仅是工具的流行",
            "更折射出",
            "深层趋势",
            "意味着双重挑战",
            "我们不应只关注工具本身",
            "组织的竞争壁垒",
            "组织需要重新审视",
        )
        if len(text) < 120:
            return True
        return self._looks_generic_topic_editorial_note(text) or any(phrase in text for phrase in stale_phrases)

    def _build_grounded_topic_editorial_note(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
        fallback: str = "",
    ) -> str:
        material_facts: list[str] = []
        for item in list(key_points or []) + list(source_sentences or []):
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in material_facts:
                continue
            material_facts.append(text)
            if len(material_facts) >= 3:
                break

        value_points: list[str] = []
        for item in recommendation_reasons or []:
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in value_points:
                continue
            value_points.append(text)
            if len(value_points) >= 2:
                break

        lead_fact = material_facts[0] if material_facts else self._compact_topic_sentence(candidate_summary or candidate_title, 96)
        value_fact = value_points[0] if value_points else (material_facts[1] if len(material_facts) > 1 else "")
        follow_fact = material_facts[1] if len(material_facts) > 1 else ""

        note_parts = [
            f"先别把它当成一条泛新闻，这篇材料真正值得抓住的是：{lead_fact or candidate_title[:48]}。",
        ]
        if value_fact:
            note_parts.append(f"对团队来说，它有用不是因为“又多了一条资讯”，而是因为{value_fact}。")
        elif fallback.strip():
            note_parts.append(self._compact_topic_sentence(fallback.strip(), 120) + "。")
        else:
            note_parts.append("对团队来说，更重要的是先把它到底解决了什么问题、能给谁省事这件事讲具体。")
        if follow_fact:
            note_parts.append(
                f"接下来最该继续核对的是：{follow_fact}。这部分如果原文里讲得足够具体，才能判断它到底只是热度信号，还是已经能接进真实工作流。"
            )
        else:
            note_parts.append("接下来最该继续核对的，是它的适用场景、落地门槛和边界条件有没有被原文讲清楚；这决定了它到底能不能真的拿来用。")
        return "".join(note_parts)[:520]

    def _build_grounded_topic_discussion_prompts(
        self,
        *,
        candidate_title: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
    ) -> list[str]:
        prompts: list[str] = []

        fact = self._compact_topic_sentence((key_points or source_sentences or [candidate_title])[0], 32)
        if fact:
            prompts.append(f"文里提到的“{fact}”到底已经在哪些真实场景里成立了？")

        reason = self._compact_topic_sentence((recommendation_reasons or [candidate_title])[0], 32)
        if reason:
            prompts.append(f"如果它最有价值的是“{reason}”，那这件事对我们现在哪类项目最直接？")

        follow = self._compact_topic_sentence((source_sentences[1] if len(source_sentences) > 1 else key_points[1] if len(key_points) > 1 else candidate_title), 32)
        if follow:
            prompts.append(f"原文里还没讲透的“{follow}”，会不会正好就是它能不能落地的关键门槛？")

        if len(prompts) < 3:
            prompts.append("如果把这条线索真的拿来用，最先需要补证据、补案例，还是补具体使用条件？")
        return prompts[:4]

    def _compact_topic_sentence(self, text: str, max_length: int) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        cleaned = cleaned.rstrip("。；;，,、")
        return cleaned[:max_length]

    def generate_knowledge_surrogate(
        self,
        *,
        title: str,
        kind: str,
        primary_category: str,
        secondary_category: str,
        raw_text: str,
        source_path: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请为知识底座生成一个给 AI 检索使用的代理文档摘要。"
            "不要写空泛总结，必须突出未来搜索时最可能使用的线索。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n类型：{kind}\n一级分类：{primary_category}\n二级分类：{secondary_category}\n原路径：{source_path}\n正文：{raw_text[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(prompt, "你是知识底座加工助手。只返回 JSON。", schema, timeout_seconds=25.0)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def generate_memory_surrogate(
        self,
        *,
        title: str,
        content: str,
        analysis: str,
        actions: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请把下面这条 AI 回答沉淀为可复用的战略陪伴记忆。"
            "输出必须适合未来检索和复用，不要写空话。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n回答内容：{content}\n分析：{analysis}\n建议动作：{actions}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(prompt, "你是战略陪伴记忆整理助手。只返回 JSON。", schema, timeout_seconds=25.0)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def enrich_retrieval_summary(
        self,
        *,
        title: str,
        overview_summary: str,
        distinct_findings: list[str],
        document_role: str,
        folder_category: str,
    ) -> str | None:
        """Rewrite a template-based retrieval_summary into a semantic, use-case oriented description."""
        health = self.get_health()
        findings_text = "\n".join(f"- {f}" for f in distinct_findings) if distinct_findings else "无"
        prompt = (
            "请为以下文档重写一段检索摘要（retrieval_summary），200字以内。\n"
            "要求：\n"
            "1. 描述这份文档能回答什么类型的问题，而不是描述它属于什么分类\n"
            "2. 用具体的场景和关键词，不要用“相关的问题”这类泛化表述\n"
            "3. 让向量嵌入能捕捉到这份文档的核心语义\n\n"
            f"标题：{title}\n"
            f"分类：{folder_category}\n"
            f"角色：{document_role}\n"
            f"概要：{overview_summary[:1200]}\n"
            f"关键发现：\n{findings_text}\n\n"
            "请直接输出检索摘要文本，不要包裹引号或其他格式。"
        )
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是知识检索优化助手。只输出检索摘要文本，不要加任何前缀或解释。",
                    None,
                    timeout_seconds=20.0,
                    max_tokens=300,
                )
                if isinstance(result, str) and len(result.strip()) > 20:
                    return result.strip()[:220]
        except Exception:
            pass
        return None

    def diagnose_profile_dimensions(
        self,
        *,
        client_name: str,
        client_type: str,
        client_stage: str,
        category_distribution: dict[str, int],
        top_titles_per_category: dict[str, list[str]],
        existing_memory_count: int,
    ) -> dict[str, Any] | None:
        """Analyze client data and recommend which profile blocks to generate."""
        health = self.get_health()
        dist_text = "\n".join(f"- {cat}: {count}份" for cat, count in category_distribution.items())
        titles_text = "\n".join(
            f"- {cat}: {', '.join(titles[:3])}"
            for cat, titles in top_titles_per_category.items()
            if titles
        )
        total_docs = sum(category_distribution.values())
        prompt = (
            "请根据以下客户资料盘点，判断应该生成哪些客户画像块。\n\n"
            "规则：\n"
            "1. 只建议有充分数据支撑的画像块，不要凭空生成\n"
            "2. 每个块必须标注依据哪些分类的资料\n"
            "3. 块数量根据资料丰富度自适应：\n"
            f"   - 资料 < 10 份：最多 1-2 块\n"
            f"   - 资料 10-50 份：最多 3-4 块\n"
            f"   - 资料 > 50 份：最多 5-7 块\n"
            "4. 可选的画像维度（根据数据决定，不是必选）：\n"
            "   客户概览、核心业务与项目、战略定位与转型、治理与组织结构、"
            "   财务与可持续性、品牌与对外传播、合作关系与生态位、关键风险与挑战\n\n"
            f"客户名称：{client_name}\n"
            f"客户类型：{client_type}\n"
            f"当前阶段：{client_stage}\n"
            f"文档总数：{total_docs}份\n"
            f"分类分布：\n{dist_text}\n"
            f"各分类代表性文档：\n{titles_text}\n"
            f"已有记忆块：{existing_memory_count}条\n"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "recommended_blocks": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "dimension": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                            "source_categories": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "priority": {"type": "INTEGER"},
                        },
                    },
                },
                "skipped_dimensions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "dimension": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                        },
                    },
                },
            },
        }
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是客户知识架构师。只返回 JSON。",
                    schema,
                    timeout_seconds=30.0,
                    max_tokens=1500,
                )
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return None

    def generate_profile_block(
        self,
        *,
        client_name: str,
        dimension: str,
        aggregated_summaries: str,
    ) -> dict[str, object] | None:
        """Generate a single client profile block from aggregated surrogate summaries."""
        health = self.get_health()
        prompt = (
            f"请基于以下 {client_name} 的「{dimension}」相关资料摘要，"
            "生成一条可复用的客户画像记忆块。\n\n"
            "要求：\n"
            "- overview_summary：面向咨询场景的综合叙述（200-400字），不是文档摘录\n"
            "- retrieval_summary：列出这个块能回答哪些类型的问题（200字以内）\n"
            "- document_role：这个画像块的角色定位（一句话）\n"
            "- core_questions：3-5个这个维度最关键的问题\n"
            "- distinct_findings：从资料中提炼的关键结论（3-7条）\n"
            "- entities：涉及的关键实体（组织、人物、项目等）\n"
            "- time_markers：涉及的时间节点\n\n"
            f"资料摘要：\n{aggregated_summaries[:4000]}\n"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider in ("qwen", "doubao") and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是客户知识整理专家。只返回 JSON。",
                    schema,
                    timeout_seconds=30.0,
                    max_tokens=2000,
                )
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return None

    def generate_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str = "",
        current_stage: str = "",
        current_intent: str = "",
        current_blocker: str = "",
        current_next_step: str = "",
        current_recent_decision: str = "",
        recent_activity_lines: list[str] | None = None,
    ) -> dict[str, object]:
        cleaned_conversation = str(conversation_text or "").strip()
        fallback = self._fallback_event_line_clarification_draft(
            event_line_name=event_line_name,
            conversation_text=cleaned_conversation,
            current_summary=current_summary,
            current_stage=current_stage,
            current_intent=current_intent,
            current_blocker=current_blocker,
            current_next_step=current_next_step,
            current_recent_decision=current_recent_decision,
        )
        health = self.get_health()
        if not cleaned_conversation or not health.ready or health.provider == "mock":
            return fallback

        activity_summary = "；".join(str(item).strip() for item in (recent_activity_lines or []) if str(item).strip())[:1200]
        prompt = (
            "请把下面这段和客户相关的聊天记录、会议纪要或沟通摘录，整理成事件线当前态草稿。"
            "目标不是逐句复述，而是提炼出这条线现在在推进什么、卡在哪、下一步是什么、最近哪次决定改变了走向。"
            "请返回 JSON，对象字段固定为：summary, stage, intent, currentBlocker, nextStep, recentDecision, missingInfo, confidence。\n"
            "输出约束：\n"
            "1. summary 用 60-120 字中文概括这条线当前在发生什么。\n"
            "2. stage 只写一句当前阶段，如“等待确认”“资料补齐中”“执行推进中”“复盘沉淀中”。\n"
            "3. intent 用 1-3 句说明这条线当前到底在推进什么。\n"
            "4. currentBlocker 只写最关键阻塞；如果没有明确阻塞，可写空字符串。\n"
            "5. nextStep 只写最关键的一步动作；如果聊天里没有明确下一步，可写空字符串。\n"
            "6. recentDecision 只写最近真正改变走向的决定；如果没有明确决定，可写空字符串。\n"
            "7. missingInfo 返回还缺哪些信息，使用中文短句数组。\n"
            "8. confidence 只能是 low、medium、high。\n"
            "9. 不要编造没有出现的事实；不确定就放进 missingInfo。\n\n"
            f"事件线名称：{event_line_name}\n"
            f"当前已有摘要：{current_summary or '无'}\n"
            f"当前已有阶段：{current_stage or '无'}\n"
            f"当前已有事项：{current_intent or '无'}\n"
            f"当前已有阻塞：{current_blocker or '无'}\n"
            f"当前已有下一步：{current_next_step or '无'}\n"
            f"当前已有关键决策：{current_recent_decision or '无'}\n"
            f"最近活动摘要：{activity_summary or '无'}\n"
            f"聊天记录：\n{cleaned_conversation[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING"},
                "stage": {"type": "STRING"},
                "intent": {"type": "STRING"},
                "currentBlocker": {"type": "STRING"},
                "nextStep": {"type": "STRING"},
                "recentDecision": {"type": "STRING"},
                "missingInfo": {"type": "ARRAY", "items": {"type": "STRING"}},
                "confidence": {"type": "STRING", "enum": ["low", "medium", "high"]},
            },
        }
        try:
            result = self._qwen_generate(
                prompt,
                "你是事件线当前态提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=28.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                normalized = self._normalize_event_line_clarification_draft_payload(result, fallback)
                if any(
                    normalized.get(key)
                    for key in ("summary", "stage", "intent", "currentBlocker", "nextStep", "recentDecision")
                ):
                    return normalized
        except Exception:
            pass
        return fallback

    def _normalize_event_line_clarification_draft_payload(
        self,
        payload: dict[str, object],
        fallback: dict[str, object],
    ) -> dict[str, object]:
        confidence_raw = str(payload.get("confidence") or "").strip().lower()
        confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else str(fallback.get("confidence") or "medium")
        return {
            "summary": str(payload.get("summary") or fallback.get("summary") or "").strip()[:180],
            "stage": str(payload.get("stage") or fallback.get("stage") or "").strip()[:40],
            "intent": str(payload.get("intent") or fallback.get("intent") or "").strip()[:240],
            "currentBlocker": str(payload.get("currentBlocker") or fallback.get("currentBlocker") or "").strip()[:240],
            "nextStep": str(payload.get("nextStep") or fallback.get("nextStep") or "").strip()[:240],
            "recentDecision": str(payload.get("recentDecision") or fallback.get("recentDecision") or "").strip()[:240],
            "missingInfo": self._normalize_string_list(payload.get("missingInfo"), max_items=5, max_length=80)
            or list(fallback.get("missingInfo") or []),
            "confidence": confidence,
        }

    def _fallback_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str,
        current_stage: str,
        current_intent: str,
        current_blocker: str,
        current_next_step: str,
        current_recent_decision: str,
    ) -> dict[str, object]:
        lines = [
            re.sub(r"\s+", " ", segment).strip(" -•\t")
            for segment in re.split(r"[\n\r]+", conversation_text)
            if segment.strip()
        ]
        sentences: list[str] = []
        for line in lines:
            for segment in re.split(r"[。！？!?；;]+", line):
                text = re.sub(r"\s+", " ", segment).strip(" -•\t")
                if text:
                    sentences.append(text)

        def pick_sentence(keywords: list[str]) -> str:
            for sentence in sentences:
                if any(keyword in sentence for keyword in keywords):
                    return sentence[:220]
            return ""

        def pick_sentence_prefix(prefixes: list[str]) -> str:
            for sentence in sentences:
                normalized = sentence.lstrip("：:，,。 ")
                if any(normalized.startswith(prefix) for prefix in prefixes):
                    return sentence[:220]
            return ""

        stage = current_stage.strip()
        if not stage:
            if re.search(r"(等待|确认|审批|口径|回复|定稿)", conversation_text):
                stage = "等待确认"
            elif re.search(r"(补齐|整理|收集|导入|扫描|资料)", conversation_text):
                stage = "资料补齐中"
            elif re.search(r"(执行|推进|落地|跟进|排期)", conversation_text):
                stage = "执行推进中"
            elif re.search(r"(复盘|总结|沉淀)", conversation_text):
                stage = "复盘沉淀中"

        intent = pick_sentence(["推进", "沟通", "确认", "整理", "补齐", "梳理", "对齐", "发送"])
        if not intent:
            intent = current_intent.strip() or "；".join(lines[:2])[:220]

        blocker = pick_sentence(["卡", "阻塞", "等待", "没", "未", "缺", "无法", "来不及", "拖", "确认"])
        if not blocker:
            blocker = current_blocker.strip()

        next_step = (
            pick_sentence_prefix(["下一步", "接下来", "后续"])
            or pick_sentence(["安排", "同步", "跟进", "推进"])
            or pick_sentence(["需要", "先", "再"])
        )
        if not next_step:
            next_step = current_next_step.strip()

        recent_decision = (
            pick_sentence(["决定", "确定", "改成", "暂定", "拍板"])
            or pick_sentence(["统一"])
            or pick_sentence(["先"])
        )
        if not recent_decision:
            recent_decision = current_recent_decision.strip()

        summary_parts = [part for part in [intent, blocker and f"当前卡在：{blocker}", next_step and f"下一步：{next_step}"] if part]
        summary = current_summary.strip() or "；".join(summary_parts)[:160]
        if not summary:
            summary = f"{event_line_name} 当前聊天记录已导入，但还需要继续补足当前态信息。"

        missing_info: list[str] = []
        if not stage:
            missing_info.append("当前阶段还不清楚")
        if not blocker:
            missing_info.append("当前阻塞还不清楚")
        if not next_step:
            missing_info.append("下一步动作还不清楚")
        if not recent_decision:
            missing_info.append("最近关键决策还不清楚")

        filled_slots = sum(1 for item in [summary, stage, intent, blocker, next_step, recent_decision] if item)
        confidence = "high" if filled_slots >= 5 else "medium" if filled_slots >= 3 else "low"
        return {
            "summary": summary[:180],
            "stage": stage[:40],
            "intent": intent[:240],
            "currentBlocker": blocker[:240],
            "nextStep": next_step[:240],
            "recentDecision": recent_decision[:240],
            "missingInfo": missing_info[:5],
            "confidence": confidence,
        }

    def _store_for(self, provider: str) -> Any | None:
        return self.secret_stores.get(provider)

    def _mock_generate(self, prompt: str, context_summary: str) -> AiStructuredResponse:
        topic = self._short_topic(prompt)
        signals = context_summary or "当前上下文中尚无完整材料，以下为保守推演。"
        return AiStructuredResponse(
            content=f"已围绕“{topic}”整理出一版可执行的内部判断。",
            judgment=f"{topic}当前最需要的是把零散线索整合成可落地动作，而不是继续堆信息。",
            analysis="\n".join(
                [
                    f"1. 已知上下文：{signals}",
                    f"2. 问题本质：{topic}涉及客户推进、证据沉淀与任务闭环的联动。",
                    "3. 风险提醒：如果没有明确负责人和时间点，后续行动会再次散掉。",
                ]
            ),
            actions="先确认负责人，再补关键材料，最后将结论写回任务与手册。",
            timeline="建议今天完成判断，48 小时内完成任务拆解，一周内复盘一次。",
        )

    def _short_topic(self, prompt: str) -> str:
        compact = re.sub(r"\s+", "", prompt)
        return compact[:16] or "当前议题"

    def _qwen_generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 60.0,
        max_tokens: int = 3500,
    ) -> AiStructuredResponse:
        payload = self._qwen_generate(
            prompt=f"问题：{prompt}\n\n上下文：{context_summary}",
            system_instruction=system_instruction,
            response_schema=self._structured_schema(),
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Qwen 返回了非结构化数据。")
        return self._structured_from_payload(payload)

    def _structured_schema(self) -> dict[str, object]:
        return {
            "type": "OBJECT",
            "properties": {
                "content": {"type": "STRING"},
                "judgment": {"type": "STRING"},
                "analysis": {"type": "STRING"},
                "actions": {"type": "STRING"},
                "timeline": {"type": "STRING"},
            },
        }

    def _structured_from_payload(self, payload: dict[str, object]) -> AiStructuredResponse:
        return AiStructuredResponse(
            content=str(payload.get("content", "")),
            judgment=str(payload.get("judgment", "")),
            analysis=str(payload.get("analysis", "")),
            actions=str(payload.get("actions", "")),
            timeline=str(payload.get("timeline", "")),
        )

    def _build_http_timeout(self, read_timeout_seconds: float) -> httpx.Timeout:
        read_timeout = max(4.0, float(read_timeout_seconds))
        connect_timeout = min(10.0, max(5.0, read_timeout / 3))
        write_timeout = min(20.0, max(8.0, read_timeout))
        pool_timeout = min(10.0, max(5.0, read_timeout / 2))
        # 硬上限：总超时 = read_timeout + 15秒缓冲，防止 TCP 连接永久挂死
        total_timeout = read_timeout + 15.0
        return httpx.Timeout(timeout=total_timeout, connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout)

    def _resolve_llm_config(self) -> tuple[str, str, str]:
        """Returns (base_url, api_key, model) for the current provider."""
        provider = self.current_provider()
        if provider == "doubao":
            store = self._store_for("doubao")
            api_key = store.get_api_key() if store else ""
            if not api_key:
                raise RuntimeError("豆包 API Key 未配置。")
            return DOUBAO_BASE_URL, api_key, self.current_model()
        store = self._store_for("qwen")
        api_key = store.get_api_key() if store else ""
        if not api_key:
            raise RuntimeError("Qwen API Key 未配置。")
        return QWEN_BASE_URL, api_key, self.current_model()

    def _qwen_generate(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: dict | None,
        timeout_seconds: float = 60.0,
        max_tokens: int = 3500,
        *,
        temperature: float = 0.45,
        top_p: float = 0.9,
        enable_thinking: bool = False,
    ) -> object:
        base_url, api_key, model = self._resolve_llm_config()
        user_prompt = prompt
        if response_schema:
            user_prompt = (
                "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                "请确保返回结构满足下面这个 JSON Schema。\n"
                f"{json.dumps(response_schema, ensure_ascii=False)}\n\n"
                f"{prompt}"
            )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction or "你是系统助手。"},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if enable_thinking:
            payload["enable_thinking"] = True
        def _do_request():
            with httpx.Client(timeout=self._build_http_timeout(timeout_seconds)) as _client:
                _resp = _client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                _resp.raise_for_status()
                return _resp.json()
        # 硬超时：用线程池确保不会永久挂死
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
        hard_limit = timeout_seconds + 15.0
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_do_request)
        try:
            result = future.result(timeout=hard_limit)
        except FutureTimeout:
            future.cancel()
            raise RuntimeError(f"AI 调用硬超时（{hard_limit:.0f}秒），服务可能不可用")
        finally:
            # 不要在超时后等待工作线程自然结束，否则外层调用会被 shutdown(wait=True)
            # 卡死，自动填表 run 会永久停在 running。
            pool.shutdown(wait=False, cancel_futures=True)
        text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if response_schema:
            return self._load_relaxed_json(text)
        return text

    def _qwen_generate_structured_with_retry(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        first_error: Exception | None = None
        second_error: Exception | None = None
        try:
            return self._qwen_generate_structured(
                prompt,
                system_instruction,
                context_summary,
                timeout_seconds=18.0,
                max_tokens=1400,
            )
        except Exception as error:
            first_error = error
        compact_context = self._compact_context_summary(context_summary)
        if compact_context:
            try:
                return self._qwen_generate_structured(
                    prompt,
                    system_instruction,
                    compact_context,
                    timeout_seconds=10.0,
                    max_tokens=900,
                )
            except Exception as error:
                second_error = error
        try:
            return self._qwen_generate_textual_fallback(prompt, system_instruction, compact_context or context_summary)
        except Exception as third_error:
            detail_parts = [self._format_provider_error(first_error)]
            if second_error is not None:
                detail_parts.append(f"缩上下文重试后仍失败：{self._format_provider_error(second_error)}")
            detail_parts.append(f"文本结构化降级仍失败：{self._format_provider_error(third_error)}")
            raise AiInvocationError("qwen", "；".join(part for part in detail_parts if part)) from third_error
        raise AiInvocationError("qwen", self._format_provider_error(first_error)) from first_error

    def _qwen_generate_general_fallback(self, prompt: str, note: str, *, subject_name: str = "") -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"补充说明：{note or '当前本地背景回答阶段失败，请直接给出通用知识下的初步回答。'}\n\n"
                f"当前讨论对象：{subject_name or '当前客户'}\n\n"
                "请直接输出一篇完整、自然、专业的中文回答。"
            ),
            system_instruction=(
                "你是益语智库的资深战略顾问。请基于通用知识给出完整、专业的初步回答。\n"
                "你面对的是一个希望迅速、全面了解这家公司的人，而不是系统管理员。\n"
                "除非问题明确问益语智库、你们、顾问方或服务方式，否则默认回答对象是当前客户。\n"
                "不要把益语智库、顾问机构、外部服务方的人名或业务介绍当成当前客户本身。\n"
                "如果确实需要，只能用一句极轻的过渡说明本地背景没有直接覆盖这个问题。\n"
                "请减少寒暄和重复句，直接进入结论与分析。\n"
                "第一段必须明确提醒：以下不是基于当前客户原始资料的正式分析，而是通用背景下的初步判断。\n\n"
                "【排版规则——必须严格遵守】\n"
                "1. 用「一、二、三、四」作为一级小标题分层\n"
                "2. 并列要点用「- 」列表\n"
                "3. 关键结论用 **双星号加粗**\n"
                "4. 每段不超过 4 句话，禁止全篇连续长段落\n"
                "5. 多用判断句：「不是X，而是Y」「核心在于」\n"
            ),
            response_schema=None,
            timeout_seconds=12.0,
            max_tokens=1200,
            temperature=0.35,
            top_p=0.92,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"内部观察摘要：\n{note or '当前已有部分内部观察，请基于这些观察先形成紧凑但完整的一版说明。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察摘要回答。"
                "不要编造观察摘要里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=10.0,
            max_tokens=1200,
            temperature=0.42,
            top_p=0.96,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"顾问观察要点：\n{note or '当前已有部分观察，请基于这些要点给出一版简洁保守的回答。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察要点回答。"
                "不要编造观察要点里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=8.0,
            max_tokens=900,
            temperature=0.4,
            top_p=0.95,
        )
        return self._structured_from_plain_answer(str(text))

    def _extract_segment_field(self, text: str, labels: tuple[str, ...]) -> str:
        for label in labels:
            match = re.search(
                rf"(?:^|\n){re.escape(label)}[:：]\s*([\s\S]+?)(?=\n(?:{'|'.join(re.escape(item) for item in labels)}|标题|题目|总判断|判断)[:：]|\Z)",
                str(text),
            )
            if match:
                return match.group(1).strip()
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        for line in lines:
            for label in labels:
                prefix = f"{label}:"
                alt_prefix = f"{label}："
                if line.startswith(prefix):
                    return line[len(prefix) :].strip()
                if line.startswith(alt_prefix):
                    return line[len(alt_prefix) :].strip()
        return ""

    def _qwen_generate_textual_fallback(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 18.0,
        max_tokens: int = 2400,
        enable_thinking: bool = False,
    ) -> AiStructuredResponse:
        fallback_instruction = (
            f"{system_instruction}\n"
            "请继续直接回答用户，不要退化成摘要、说明书或系统提示。"
            "不要使用 JSON 或 Markdown 代码块。"
            "如果完整材料过长，请优先保留最关键的判断、推理链和支撑证据，不要把回答压扁成几段概述。"
            "除非用户明确要求简短，否则请保持足够展开。"
        )
        text = self._qwen_generate(
            prompt=f"用户问题：{prompt}\n\n参考材料：\n{context_summary}",
            system_instruction=fallback_instruction,
            response_schema=None,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.4,
            top_p=0.95,
            enable_thinking=enable_thinking,
        )
        return self._structured_from_plain_answer(str(text))

    def _compact_context_summary(self, context_summary: str, max_chars: int = 1800) -> str:
        text = (context_summary or "").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return text[:max_chars]
        pinned: list[str] = []
        markers = ("客户背景=", "背景底稿（仅用于理解客户）", "原始证据包（可用于正式判断）", "[证据", "顾问角色口径=", "重点维度=")
        for index, line in enumerate(lines):
            if not any(marker in line for marker in markers):
                continue
            block_end = min(len(lines), index + (5 if "[证据" in line else 2))
            for block_line in lines[index:block_end]:
                compact_line = block_line[:960]
                if compact_line not in pinned:
                    pinned.append(compact_line)
        head = [line[:960] for line in lines[:14]]
        tail = [line[:960] for line in lines[-12:]]
        compact_lines = []
        for line in head + pinned[:36]:
            if line not in compact_lines:
                compact_lines.append(line)
        for line in tail:
            if line not in compact_lines:
                compact_lines.append(line)
        compact = "\n".join(compact_lines).strip()
        if not compact:
            compact = text
        compact = compact[:max_chars]
        if compact == text[:max_chars]:
            focus = tail[0] if tail else ""
            fallback_excerpt = "\n".join(compact_lines[:8])[:max_chars]
            compact = "\n".join(part for part in [fallback_excerpt, focus] if part).strip() or text[:max_chars]
        return compact[:max_chars]

    def _structured_from_plain_answer(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", cleaned) if item.strip()]
        if not paragraphs:
            paragraphs = [cleaned]
        def is_heading_like(value: str) -> bool:
            candidate = value.strip()
            if not candidate:
                return False
            if re.match(r"^#{1,6}\s+", candidate):
                return True
            if re.match(r"^\d+\.\s+[^\n]{2,42}$", candidate):
                return True
            if re.match(r"^[一二三四五六七八九十]+、", candidate):
                return False
            return len(candidate) <= 42 and not re.search(r"[。！？!?]", candidate)

        judgment_paragraph_index = 1 if len(paragraphs) >= 2 and is_heading_like(paragraphs[0]) else 0
        first_paragraph = paragraphs[judgment_paragraph_index]
        first_sentence_match = re.search(r"(.+?[。！？!?])", first_paragraph)
        judgment = first_sentence_match.group(1).strip() if first_sentence_match else first_paragraph[:180]
        analysis_source = paragraphs[judgment_paragraph_index + 1 :] if len(paragraphs) > judgment_paragraph_index + 1 else paragraphs[judgment_paragraph_index : judgment_paragraph_index + 1]
        analysis_parts = analysis_source[:4] if analysis_source else paragraphs[:1]
        analysis = "\n\n".join(analysis_parts)
        if not analysis.strip():
            analysis = cleaned[:1800]
        actions = "如有需要，可继续围绕当前判断往下追问或展开。"
        suggestion_match = re.search(r"(?:^|\n)\s*(下一步建议|建议动作)[:：]\s*([\s\S]+)$", cleaned, re.IGNORECASE)
        if suggestion_match:
            actions = suggestion_match.group(2).strip() or actions
        return AiStructuredResponse(
            content=cleaned,
            judgment=judgment,
            analysis=analysis,
            actions=actions or "如有需要，可继续围绕当前判断往下追问或展开。",
            timeline="后续可随资料和讨论继续迭代。",
        )

    def _clean_template_field_value(self, text: str, *, field_type: str | None = None) -> str:
        cleaned = str(text or "").strip()
        if cleaned.startswith("```"):
            inline_fence = re.match(r"^```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
            if inline_fence:
                cleaned = inline_fence.group(1).strip()
            else:
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        cleaned = re.sub(r"^(?:字段(?:填写)?(?:内容)?|答案|建议填写|可填写为|可直接填写为)[:：]\s*", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        return self._enforce_template_field_constraints(cleaned[:1200], field_type=field_type)

    def _template_field_rule(self, field_type: str | None) -> str:
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            return "只能填写可直接核验的精确事实；资料不够时直接输出【待确认】。"
        if normalized == "structural_summary":
            return "允许基于多份材料压缩概括，但不要夹带如何填写的解释。"
        if normalized == "governance_mechanism":
            return "强依赖章程、制度、会议纪要或党组织记录；资料不足时宁可输出【待确认】，不要写空泛套话。"
        if normalized == "quantitative_result":
            return "优先填写可引用数字；如果没有明确数字，不要用模糊描述凑数，直接输出【待确认】。"
        if normalized == "attachment_material":
            return "只判断材料是否已具备或缺失，不要输出解释性文字。"
        return "请尽量保守、可复核地填写，不要输出过程性提示。"

    def _enforce_template_field_constraints(self, text: str, *, field_type: str | None) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        process_hint_markers = (
            "可从",
            "进一步梳理",
            "建议补",
            "建议补充",
            "建议内部核验",
            "可填写",
            "如何填写",
        )
        if cleaned.startswith("【待确认】"):
            return cleaned
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            if any(marker in cleaned for marker in process_hint_markers) or any(marker in cleaned for marker in ("可能", "大约", "约", "左右", "公开招聘页面显示", "建设中")):
                return "【待确认】当前资料不足以直接确认该精确事实字段。"
        if normalized == "governance_mechanism":
            if any(marker in cleaned for marker in process_hint_markers):
                return "【待确认】当前缺少可直接支撑该治理/党建字段的章程、制度或会议记录。"
        if normalized == "quantitative_result":
            if not re.search(r"\d", cleaned):
                return "【待确认】当前缺少可直接引用的数量或统计口径。"
        if normalized == "attachment_material":
            if "已备" in cleaned or "待补" in cleaned:
                return cleaned
            return "【待确认】当前需进一步核验该材料是否已备齐。"
        return cleaned

    def _soften_caveat_heavy_opening(self, text: str) -> str:
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", str(text).strip()) if item.strip()]
        if not paragraphs:
            return str(text).strip()
        target_index = 0
        if len(paragraphs) >= 2 and len(paragraphs[0]) <= 36 and not re.search(r"[。！？!?]", paragraphs[0]):
            target_index = 1
        first = paragraphs[target_index]
        if not any(
            marker in first
            for marker in (
                "需要首先明确",
                "需要首先说明",
                "资料主要聚焦于",
                "暂时无法确认",
                "以下分析将",
                "事实边界",
            )
        ):
            return "\n\n".join(paragraphs).strip()
        softened = first
        softened = re.sub(r"需要首先(?:明确|说明)的是，?", "", softened)
        softened = re.sub(r"现有资料主要聚焦于[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"且多呈现为[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"这意味着[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"关于[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"以下分析将[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"就事实边界而言，?[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"\s+", " ", softened).strip(" ，,。")
        if len(softened) < 24:
            softened = "已经能够勾勒出该对象当前的机构定位、战略意图与核心工作脉络，以下重点展开其中最有判断价值的部分。"
        if not re.search(r"[。！？!?]$", softened):
            softened = f"{softened}。"
        paragraphs[target_index] = softened
        refined = "\n\n".join(paragraphs).strip()
        refined = re.sub(r"基于益语智库当前掌握的[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"根据现有[^。！？!?]*(?:观察|背景|底稿)[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"从现有(?:资料|材料|观察)(?:交叉)?来看，?", "", refined)
        refined = re.sub(r"资料中反复出现的", "", refined)
        refined = re.sub(r"文档中(?:反复)?出现的", "", refined)
        refined = re.sub(r"工作坊记录显示", "", refined)
        refined = re.sub(r"\n{3,}", "\n\n", refined).strip()
        return refined

    def _format_provider_error(self, error: Exception | None) -> str:
        if error is None:
            return "未知模型错误"
        if isinstance(error, AiInvocationError):
            return error.detail
        message = str(error).strip() or error.__class__.__name__
        if isinstance(error, httpx.ReadTimeout):
            return f"读取超时：{message}"
        if isinstance(error, httpx.TimeoutException):
            return f"请求超时：{message}"
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code if error.response is not None else "unknown"
            return f"上游状态异常 {status}：{message}"
        return message

    def _structured_from_text_sections(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        sections = self._extract_section_blocks(cleaned)
        content = sections.get("内容综述", cleaned[:900]).strip()
        analysis = sections.get("结构化分析", sections.get("支持判断的要点", cleaned[:1500])).strip()
        actions = sections.get("建议动作", sections.get("下一步建议", "建议先确认当前资料能支撑的事实，再决定下一步动作。")).strip()
        judgment = sections.get("核心判断", "").strip()
        if not judgment:
            first_line = next((line.strip(" -") for line in analysis.splitlines() if line.strip()), "")
            judgment = first_line or content[:180]
        timeline = sections.get("关键时间线", "建议今天先形成初判，后续随资料补充再更新。").strip()
        return AiStructuredResponse(
            content=content or cleaned[:900],
            judgment=judgment or content[:180],
            analysis=analysis or cleaned[:1500],
            actions=actions,
            timeline=timeline,
        )

    def _extract_section_blocks(self, text: str) -> dict[str, str]:
        pattern = re.compile(r"【(内容综述|核心判断|结构化分析|建议动作|关键时间线|支持判断的要点|下一步建议)】")
        matches = list(pattern.finditer(text))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            label = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections[label] = text[start:end].strip()
        return sections

    def _load_relaxed_json(self, text: str) -> dict[str, object]:
        stripped = str(text).strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end <= start:
                raise RuntimeError("模型返回了不可解析的 JSON。")
            payload = json.loads(stripped[start : end + 1])
        if not isinstance(payload, dict):
            raise RuntimeError("模型返回了非对象 JSON。")
        return payload

    def _fallback_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        merged = f"{title} {prompt}".strip()
        for phrase in ("关注", "跟踪", "追踪", "最新", "案例", "信息", "新闻", "如何", "怎么", "打法"):
            merged = merged.replace(phrase, " ")
        merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）]+", " ", merged)
        merged = re.sub(r"\s+", " ", merged).strip()
        parts = [part.strip() for part in merged.split(" ") if part.strip()]
        base = " ".join(parts[:6]).strip() or title.strip() or prompt.strip() or "行业资讯"
        compact_title = title.strip()
        window_label = {"1_day": "近一天", "3_days": "近三天", "7_days": "近七天"}.get(time_range, "")
        queries = [base]
        if compact_title and compact_title not in base:
            queries.append(f"{compact_title} {base}".strip())
        if compact_title:
            queries.append(f"{compact_title} {window_label}".strip())
        deduped: list[str] = []
        for item in queries:
            normalized = item.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized[:72])
        return deduped[:3] or ["行业资讯"]
~~~

## `backend/app/services/analysis_center.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    AnalysisAuthorityLevel,
    AnalysisBackfillMainChainJobRecord,
    AnalysisBackfillMainChainPayload,
    AnalysisBackfillMainChainResultRecord,
    AnalysisCenterSummaryRecord,
    AnalysisIntentProfile,
    AnalysisJobCreatePayload,
    AnalysisJobRecord,
    AnalysisJobStageRunRecord,
    AnalysisLane,
    AnalysisMigrationMetricsRecord,
    AnalysisOriginType,
    AnalysisQualityTier,
    AnalysisRejectedReason,
    AnalysisReviewState,
    AnalysisScopeType,
    AnalysisStaleReason,
    ApprovalDecisionPayload,
    ApprovalStateRecord,
    ApprovalRecordRecord,
    ClientAnalysisRunRecord,
    ClientDnaModuleRecord,
    ClientWorkspaceResponse,
    ConflictGroupRecord,
    ContextPackRecord,
    DnaDeltaCreatePayload,
    DnaDeltaRecord,
    DocumentCardRecord,
    EventLineMemorySnapshot,
    JudgmentBundleRecord,
    JudgmentConfirmPayload,
    JudgmentVersionRecord,
    MemoryStatus,
    OpenQuestionRecord,
    OrganizationNotebookSnapshot,
    ProjectFlowRecord,
    ProjectModuleRecord,
    RuntimeRunLogRecord,
    ResolutionCandidateRecord,
    ResolutionScopeRecord,
    ResolutionTraceRecord,
    TaskRecord,
    ThemeClusterRecord,
)


@dataclass
class AnalysisCenterProjectionBundle:
    summary: AnalysisCenterSummaryRecord
    latest_context_pack: ContextPackRecord | None
    judgment_bundle: JudgmentBundleRecord | None
    latest_resolution_trace: ResolutionTraceRecord | None
    latest_judgments: list[JudgmentVersionRecord]
    latest_topics: list[ThemeClusterRecord]
    latest_conflicts: list[ConflictGroupRecord]
    latest_open_questions: list[OpenQuestionRecord]
    latest_run_logs: list[RuntimeRunLogRecord]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "::".join(part.strip() for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _parse_json_list(value: str | None) -> list[str]:
    data = from_json(value, [])
    return [str(item) for item in data] if isinstance(data, list) else []


def _parse_json_dict(value: str | None) -> dict[str, Any]:
    data = from_json(value, {})
    return data if isinstance(data, dict) else {}


def _first_non_empty(*values: str | None, fallback: str = "") -> str:
    for value in values:
        text = (value or "").strip()
        if text:
            return text
    return fallback


_ATTACHMENT_INGEST_BOILERPLATE_MARKERS = (
    "已作为任务附件进入项目资料库",
    "可用于后续检索、问答与事件线证据引用",
    "任务附件已进入项目资料库",
)


def looks_like_attachment_ingest_boilerplate(value: str | None) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return False
    if any(marker in text for marker in _ATTACHMENT_INGEST_BOILERPLATE_MARKERS):
        return True
    lowered = text.lower()
    file_name_like = re.match(r"^[^\s]+\.(?:jpg|jpeg|png|gif|pdf|doc|docx|ppt|pptx|xls|xlsx|txt|md)\b", lowered)
    return bool(file_name_like and ("项目资料库" in text or "后续检索" in text or "问答" in text))


def _first_non_empty_non_boilerplate(*values: str | None, fallback: str = "") -> str:
    for value in values:
        text = (value or "").strip()
        if text and not looks_like_attachment_ingest_boilerplate(text):
            return text
    return fallback


def _truncate(value: str | None, limit: int = 160) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1]}…"


def _unique(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        text = (raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


_MAIN_CHAIN_CANARY_FEATURE_FLAG = "main-chain-canary"


_AUTHORITY_RANK: dict[AnalysisAuthorityLevel, int] = {
    "fallback": 0,
    "candidate": 1,
    "approved": 2,
}

_STALE_REASON_MAP: dict[str, AnalysisStaleReason] = {
    "new_document": "source_snapshot_changed",
    "scope_changed": "scope_no_longer_primary",
    "manual_override": "manual_invalidation",
    "superseded_by_newer_record": "superseded_by_newer_judgment",
    "source_snapshot_changed": "source_snapshot_changed",
    "approval_revoked": "approval_revoked",
    "scope_no_longer_primary": "scope_no_longer_primary",
    "insufficient_evidence": "insufficient_evidence",
    "manual_invalidation": "manual_invalidation",
    "superseded_by_newer_judgment": "superseded_by_newer_judgment",
}

_INTENT_SCOPE_ORDER: dict[AnalysisIntentProfile, tuple[AnalysisScopeType, ...]] = {
    "task_ai": ("event_line", "flow", "module", "client"),
    "weekly_review": ("event_line", "flow", "module", "client"),
    "meeting_enhance": ("event_line", "flow", "module", "client"),
    "client_overview": ("client", "module", "flow", "event_line"),
    "dna_summary": ("client", "module", "flow", "event_line"),
    "strategic_cockpit": ("client", "event_line", "module", "flow"),
}

_SCOPE_GRANULARITY: dict[AnalysisScopeType, int] = {
    "task": 0,
    "meeting": 1,
    "event_line": 2,
    "flow": 3,
    "module": 4,
    "client": 5,
}

_CANDIDATE_REVIEW_WARNING_AFTER_HOURS = 24
_CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS = 72
_ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT = 2
_ANALYSIS_WORKER_BUCKETS = ("interactive", "system", "backfill", "unknown")


def _hash_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _normalize_stale_reason(value: str | None) -> AnalysisStaleReason | None:
    text = (value or "").strip()
    if not text:
        return None
    return _STALE_REASON_MAP.get(text, "manual_invalidation")


def _parse_dt(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _serialize_snapshot(value: Any) -> str:
    if isinstance(value, str):
        return value
    return to_json(value)


def _build_snapshot_hash(value: Any) -> str:
    return _hash_text(_serialize_snapshot(value))


def _build_canary_exclusion_scope(db: Database) -> dict[str, set[str]]:
    canary_job_ids: set[str] = set()
    for row in db.fetchall("SELECT id, feature_flags_json FROM analysis_jobs"):
        feature_flags = _parse_json_dict(row["feature_flags_json"])
        if bool(feature_flags.get(_MAIN_CHAIN_CANARY_FEATURE_FLAG)):
            canary_job_ids.add(str(row["id"]))
    if not canary_job_ids:
        return {
            "judgment_versions": set(),
            "dna_deltas": set(),
            "conflict_groups": set(),
        }

    placeholders = ",".join("?" for _ in canary_job_ids)
    context_pack_ids = {
        str(row["id"])
        for row in db.fetchall(
            f"SELECT id FROM context_packs WHERE job_id IN ({placeholders})",
            tuple(canary_job_ids),
        )
    }
    if not context_pack_ids:
        return {
            "judgment_versions": set(),
            "dna_deltas": set(),
            "conflict_groups": set(),
        }

    context_placeholders = ",".join("?" for _ in context_pack_ids)

    def list_ids(table_name: str) -> set[str]:
        return {
            str(row["id"])
            for row in db.fetchall(
                f"SELECT id FROM {table_name} WHERE context_pack_id IN ({context_placeholders})",
                tuple(context_pack_ids),
            )
        }

    return {
        "judgment_versions": list_ids("judgment_versions"),
        "dna_deltas": list_ids("dna_deltas"),
        "conflict_groups": list_ids("conflict_groups"),
    }


def _validate_truth_boundary(
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> None:
    if origin_type == "human_override" and authority_level == "fallback":
        raise ValueError("human_override 不能保持 fallback 权威级别")
    if authority_level == "approved" and quality_tier != "reviewed":
        raise ValueError("approved 对象必须是 reviewed")
    if origin_type == "projection" and authority_level == "approved":
        raise ValueError("projection 不能直接成为 approved")


def _derive_child_authority(*parents: AnalysisAuthorityLevel | None) -> AnalysisAuthorityLevel:
    ordered = [parent for parent in parents if parent]
    if any(parent == "fallback" for parent in ordered):
        return "fallback"
    if any(parent == "candidate" for parent in ordered):
        return "candidate"
    return "approved"


def _truth_fields(
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> dict[str, str]:
    _validate_truth_boundary(
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    return {
        "origin_type": origin_type,
        "authority_level": authority_level,
        "quality_tier": quality_tier,
    }


def _compute_scope_snapshot_hash(
    workspace: ClientWorkspaceResponse,
    *,
    scope_type: AnalysisScopeType,
    scope_id: str,
) -> str:
    payload: dict[str, Any] = {
        "clientId": workspace.client.id,
        "scopeType": scope_type,
        "scopeId": scope_id,
        "documents": [(item.id, item.updatedAt) for item in workspace.documentCards[:40]],
        "meetings": [(item.id, item.updatedAt, item.stage) for item in workspace.meetings[:24]],
        "tasks": [
            (
                item.id,
                item.updatedAt,
                item.status,
                item.eventLineId,
                item.projectModuleId,
                item.projectFlowId,
            )
            for item in workspace.relatedTasks[:80]
            if scope_type == "client"
            or (scope_type == "event_line" and item.eventLineId == scope_id)
            or (scope_type == "module" and item.projectModuleId == scope_id)
            or (scope_type == "flow" and item.projectFlowId == scope_id)
        ],
        "dnaModules": [(item.moduleKey, item.updatedAt, item.hasDocument) for item in workspace.dnaModules],
    }
    return _build_snapshot_hash(payload)


def _mark_previous_record_stale(
    db: Database,
    table_name: str,
    previous_id: str | None,
    *,
    invalidated_by: str,
    stale_reason: str,
    now: str,
) -> None:
    if not previous_id:
        return
    normalized_reason = _normalize_stale_reason(stale_reason)
    db.execute(
        f"""
        UPDATE {table_name}
        SET invalidated_by = ?, stale_reason = ?, updated_at = ?
        WHERE id = ? AND COALESCE(invalidated_by, '') = ''
        """,
        (invalidated_by, normalized_reason, now, previous_id),
    )


class DerivedSyncSerializer:
    @staticmethod
    def serialize_context_pack(
        context_pack: ContextPackRecord,
        themes: list[ThemeClusterRecord],
        conflicts: list[ConflictGroupRecord],
        open_questions: list[OpenQuestionRecord],
    ) -> dict[str, Any]:
        return {
            "contextPackId": context_pack.id,
            "targetType": context_pack.targetType,
            "targetId": context_pack.targetId,
            "originType": context_pack.originType,
            "authorityLevel": context_pack.authorityLevel,
            "qualityTier": context_pack.qualityTier,
            "sourceSnapshotHash": context_pack.sourceSnapshotHash,
            "promptVersion": context_pack.promptVersion,
            "evidenceCount": context_pack.evidenceCount,
            "themeTitles": [item.title for item in themes[:6]],
            "conflictTitles": [item.title for item in conflicts[:4]],
            "openQuestions": [item.question for item in open_questions[:6]],
            "themeRefs": [item.id for item in themes[:6]],
            "conflictRefs": [item.id for item in conflicts[:4]],
            "questionRefs": [item.id for item in open_questions[:6]],
            "updatedAt": context_pack.updatedAt,
        }


def _upsert(db: Database, table: str, payload: dict[str, Any], conflict_columns: tuple[str, ...] = ("id",)) -> None:
    columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in conflict_columns)
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT({", ".join(conflict_columns)}) DO UPDATE SET {updates}
    """
    db.execute(sql, tuple(payload[column] for column in columns))


def _upsert_stage_run(db: Database, stage: AnalysisJobStageRunRecord) -> None:
    _upsert(
        db,
        "job_stage_runs",
        {
            "id": stage.id,
            "job_id": stage.jobId,
            "stage_name": stage.stageName,
            "status": stage.status,
            "provider": stage.provider,
            "model_name": stage.modelName,
            "lane": stage.lane,
            "cache_key": stage.cacheKey,
            "cache_hit": int(stage.cacheHit),
            "degraded": int(stage.degraded),
            "evidence_count": stage.evidenceCount,
            "topic_count": stage.topicCount,
            "conflict_count": stage.conflictCount,
            "context_time_range": stage.contextTimeRange,
            "metrics_json": to_json(stage.metrics),
            "detail": stage.detail,
            "correlation_id": stage.correlationId,
            "started_at": stage.startedAt,
            "finished_at": stage.finishedAt,
            "created_at": stage.createdAt,
            "updated_at": stage.updatedAt,
        },
    )


def _upsert_analysis_job(db: Database, job: AnalysisJobRecord) -> None:
    _upsert(
        db,
        "analysis_jobs",
        {
            "id": job.id,
            "job_type": job.jobType,
            "client_id": job.clientId,
            "scope_type": job.scopeType,
            "scope_id": job.scopeId,
            "status": job.status,
            "priority": job.priority,
            "trigger_type": job.triggerType,
            "intent_profile": job.intentProfile,
            "question": job.question,
            "source_snapshot": job.sourceSnapshot,
            "source_snapshot_hash": job.sourceSnapshotHash,
            "dedupe_key": job.dedupeKey,
            "feature_flags_json": to_json(job.featureFlags),
            "progress": job.progress,
            "stage_label": job.stageLabel,
            "run_log_id": job.runLogId,
            "error": job.error,
            "locked_by": job.lockedBy,
            "locked_at": job.lockedAt,
            "lock_expires_at": job.lockExpiresAt,
            "attempt_count": job.attemptCount,
            "last_error": job.lastError,
            "created_at": job.createdAt,
            "updated_at": job.updatedAt,
            "started_at": job.startedAt,
            "finished_at": job.finishedAt,
        },
    )


def _upsert_runtime_run_log(db: Database, record: RuntimeRunLogRecord) -> None:
    _upsert(
        db,
        "runtime_run_logs",
        {
            "id": record.id,
            "client_id": record.clientId,
            "job_id": record.jobId,
            "analysis_job_id": record.analysisJobId,
            "stage_run_id": record.stageRunId,
            "context_pack_id": record.contextPackId,
            "judgment_version_id": record.judgmentVersionId,
            "correlation_id": record.correlationId,
            "provider": record.provider,
            "model": record.model,
            "lane": record.lane,
            "cache_hit": int(record.cacheHit),
            "degraded": int(record.degraded),
            "document_count": record.documentCount,
            "evidence_count": record.evidenceCount,
            "conflict_count": record.conflictCount,
            "context_time_range": record.contextTimeRange,
            "prompt_version": record.promptVersion,
            "schema_version": record.schemaVersion,
            "summary": record.summary,
            "detail_json": to_json(record.detail),
            "created_at": record.createdAt,
        },
    )


def _upsert_doc_skeleton(db: Database, record: dict[str, Any]) -> None:
    _upsert(
        db,
        "doc_skeletons",
        {
            "id": record["id"],
            "client_id": record["client_id"],
            "document_id": record["document_id"],
            "title": record["title"],
            "outline_json": to_json(record["outline"]),
            "entities_json": to_json(record["entities"]),
            "time_range": record["time_range"],
            "parser_version": record["parser_version"],
            "source_snapshot": record["source_snapshot"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        },
    )


def _upsert_evidence_card(db: Database, record: dict[str, Any]) -> None:
    _validate_truth_boundary(
        origin_type=record["origin_type"],
        authority_level=record["authority_level"],
        quality_tier=record["quality_tier"],
    )
    _upsert(
        db,
        "evidence_cards",
        {
            "id": record["id"],
            "client_id": record["client_id"],
            "scope_type": record["scope_type"],
            "scope_id": record["scope_id"],
            "origin_type": record["origin_type"],
            "authority_level": record["authority_level"],
            "quality_tier": record["quality_tier"],
            "source_type": record["source_type"],
            "source_id": record["source_id"],
            "source_ref": record["source_ref"],
            "quote": record["quote"],
            "normalized_claim": record["normalized_claim"],
            "evidence_type": record["evidence_type"],
            "polarity": record["polarity"],
            "tags_json": to_json(record["tags"]),
            "topic_keys_json": to_json(record["topic_keys"]),
            "confidence": record["confidence"],
            "time_anchor": record["time_anchor"],
            "document_id": record["document_id"],
            "event_line_id": record["event_line_id"],
            "task_id": record["task_id"],
            "meeting_id": record["meeting_id"],
            "module_id": record["module_id"],
            "flow_id": record["flow_id"],
            "review_state": record["review_state"],
            "fingerprint": record["fingerprint"],
            "normalized_claim_hash": record["normalized_claim_hash"],
            "source_ref_hash": record["source_ref_hash"],
            "evidence_fingerprint": record["evidence_fingerprint"],
            "normalizer_version": record["normalizer_version"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        },
    )


def _upsert_theme_cluster(db: Database, record: ThemeClusterRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "theme_clusters",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "theme_key": record.themeKey,
            "title": record.title,
            "support_ids_json": to_json(record.supportIds),
            "oppose_ids_json": to_json(record.opposeIds),
            "gap_summary": record.gapSummary,
            "latest_change_summary": record.latestChangeSummary,
            "evidence_count": record.evidenceCount,
            "version": record.version,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
        conflict_columns=("client_id", "scope_type", "scope_id", "theme_key"),
    )


def _upsert_conflict_group(db: Database, record: ConflictGroupRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "conflict_groups",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "conflict_type": record.conflictType,
            "title": record.title,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "unresolved_question_ids_json": to_json(record.unresolvedQuestionIds),
            "resolution_status": record.resolutionStatus,
            "severity": record.severity,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_open_question(db: Database, record: OpenQuestionRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "open_questions",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "theme_key": record.themeKey,
            "question": record.question,
            "reason": record.reason,
            "blocker_level": record.blockerLevel,
            "status": record.status,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_context_pack(db: Database, record: ContextPackRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "context_packs",
        {
            "id": record.id,
            "client_id": record.clientId,
            "job_id": record.jobId,
            "target_type": record.targetType,
            "target_id": record.targetId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "prompt_version": record.promptVersion,
            "source_count": record.sourceCount,
            "evidence_count": record.evidenceCount,
            "payload_json": to_json(record.payload),
            "stale_at": record.staleAt,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_dna_delta(db: Database, record: DnaDeltaRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "dna_deltas",
        {
            "id": record.id,
            "client_id": record.clientId,
            "dimension": record.dimension,
            "previous_version": record.previousVersion,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "proposed_change": record.proposedChange,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "confidence": record.confidence,
            "status": record.status,
            "context_pack_id": record.contextPackId,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_judgment_version(db: Database, record: JudgmentVersionRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "judgment_versions",
        {
            "id": record.id,
            "client_id": record.clientId,
            "target_type": record.targetType,
            "target_id": record.targetId,
            "topic": record.topic,
            "version": record.version,
            "status": record.status,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "context_pack_id": record.contextPackId,
            "risk_level": record.riskLevel,
            "confidence": record.confidence,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_sync_memory_record(
    db: Database,
    *,
    client_id: str,
    scope_type: AnalysisScopeType,
    scope_id: str,
    payload: dict[str, Any],
    source_fingerprint: str,
    synced_at: str | None,
    now: str,
) -> None:
    record_id = _stable_id("syncmem", client_id, scope_type, scope_id)
    _upsert(
        db,
        "sync_memory_records",
        {
            "id": record_id,
            "client_id": client_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "sync_mode": "derived_only",
            "payload_json": to_json(payload),
            "source_fingerprint": source_fingerprint,
            "synced_at": synced_at,
            "created_at": now,
            "updated_at": now,
        },
    )


def _build_analysis_job_record(row: Any) -> AnalysisJobRecord:
    return AnalysisJobRecord(
        id=str(row["id"]),
        jobType=str(row["job_type"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        status=str(row["status"]),
        priority=str(row["priority"]),
        triggerType=str(row["trigger_type"]),
        intentProfile=str(row["intent_profile"] or "client_overview"),
        question=str(row["question"] or ""),
        sourceSnapshot=str(row["source_snapshot"] or ""),
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        dedupeKey=str(row["dedupe_key"] or ""),
        featureFlags=_parse_json_dict(row["feature_flags_json"]),
        progress=float(row["progress"] or 0.0),
        stageLabel=str(row["stage_label"]) if row["stage_label"] else None,
        runLogId=str(row["run_log_id"]) if row["run_log_id"] else None,
        error=str(row["error"]) if row["error"] else None,
        lockedBy=str(row["locked_by"]) if row["locked_by"] else None,
        lockedAt=str(row["locked_at"]) if row["locked_at"] else None,
        lockExpiresAt=str(row["lock_expires_at"]) if row["lock_expires_at"] else None,
        attemptCount=int(row["attempt_count"] or 0),
        lastError=str(row["last_error"]) if row["last_error"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        finishedAt=str(row["finished_at"]) if row["finished_at"] else None,
    )


def _build_stage_run_record(row: Any) -> AnalysisJobStageRunRecord:
    return AnalysisJobStageRunRecord(
        id=str(row["id"]),
        jobId=str(row["job_id"]),
        stageName=str(row["stage_name"]),
        status=str(row["status"]),
        provider=str(row["provider"]) if row["provider"] else None,
        modelName=str(row["model_name"]) if row["model_name"] else None,
        lane=str(row["lane"]),
        cacheKey=str(row["cache_key"]) if row["cache_key"] else None,
        cacheHit=bool(row["cache_hit"]),
        degraded=bool(row["degraded"]),
        evidenceCount=int(row["evidence_count"] or 0),
        topicCount=int(row["topic_count"] or 0),
        conflictCount=int(row["conflict_count"] or 0),
        contextTimeRange=str(row["context_time_range"]) if row["context_time_range"] else None,
        metrics=_parse_json_dict(row["metrics_json"]),
        detail=str(row["detail"]) if row["detail"] else None,
        correlationId=str(row["correlation_id"]) if row["correlation_id"] else None,
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        finishedAt=str(row["finished_at"]) if row["finished_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_runtime_run_log_record(row: Any) -> RuntimeRunLogRecord:
    return RuntimeRunLogRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        jobId=str(row["job_id"]) if row["job_id"] else None,
        analysisJobId=str(row["analysis_job_id"]) if row["analysis_job_id"] else None,
        stageRunId=str(row["stage_run_id"]) if row["stage_run_id"] else None,
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        judgmentVersionId=str(row["judgment_version_id"]) if row["judgment_version_id"] else None,
        correlationId=str(row["correlation_id"]) if row["correlation_id"] else None,
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        lane=str(row["lane"]),
        cacheHit=bool(row["cache_hit"]),
        degraded=bool(row["degraded"]),
        documentCount=int(row["document_count"] or 0),
        evidenceCount=int(row["evidence_count"] or 0),
        conflictCount=int(row["conflict_count"] or 0),
        contextTimeRange=str(row["context_time_range"]) if row["context_time_range"] else None,
        promptVersion=str(row["prompt_version"]) if row["prompt_version"] else None,
        schemaVersion=str(row["schema_version"]) if row["schema_version"] else None,
        summary=str(row["summary"] or ""),
        detail=_parse_json_dict(row["detail_json"]),
        createdAt=str(row["created_at"]),
    )


def _build_theme_cluster_record(row: Any) -> ThemeClusterRecord:
    return ThemeClusterRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        themeKey=str(row["theme_key"]),
        title=str(row["title"]),
        supportIds=_parse_json_list(row["support_ids_json"]),
        opposeIds=_parse_json_list(row["oppose_ids_json"]),
        gapSummary=str(row["gap_summary"] or ""),
        latestChangeSummary=str(row["latest_change_summary"] or ""),
        evidenceCount=int(row["evidence_count"] or 0),
        version=int(row["version"] or 1),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_conflict_group_record(row: Any) -> ConflictGroupRecord:
    return ConflictGroupRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        conflictType=str(row["conflict_type"]),
        title=str(row["title"]),
        summary=str(row["summary"]),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        unresolvedQuestionIds=_parse_json_list(row["unresolved_question_ids_json"]),
        resolutionStatus=str(row["resolution_status"]),
        severity=str(row["severity"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_open_question_record(row: Any) -> OpenQuestionRecord:
    return OpenQuestionRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        themeKey=str(row["theme_key"]),
        question=str(row["question"]),
        reason=str(row["reason"] or ""),
        blockerLevel=str(row["blocker_level"]),
        status=str(row["status"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_context_pack_record(row: Any) -> ContextPackRecord:
    return ContextPackRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        jobId=str(row["job_id"]) if row["job_id"] else None,
        targetType=str(row["target_type"]),
        targetId=str(row["target_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        promptVersion=str(row["prompt_version"]),
        sourceCount=int(row["source_count"] or 0),
        evidenceCount=int(row["evidence_count"] or 0),
        payload=_parse_json_dict(row["payload_json"]),
        staleAt=str(row["stale_at"]) if row["stale_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_dna_delta_record(row: Any) -> DnaDeltaRecord:
    return DnaDeltaRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        dimension=str(row["dimension"]),
        previousVersion=str(row["previous_version"]) if row["previous_version"] else None,
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        proposedChange=str(row["proposed_change"]),
        summary=str(row["summary"] or ""),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        confidence=str(row["confidence"]),
        status=str(row["status"]),
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_judgment_version_record(row: Any) -> JudgmentVersionRecord:
    return JudgmentVersionRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        targetType=str(row["target_type"]),
        targetId=str(row["target_id"]),
        topic=str(row["topic"]),
        version=int(row["version"] or 1),
        status=str(row["status"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        summary=str(row["summary"]),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        riskLevel=str(row["risk_level"]),
        confidence=str(row["confidence"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def list_analysis_jobs(db: Database, client_id: str, limit: int = 12) -> list[AnalysisJobRecord]:
    return [
        _build_analysis_job_record(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_jobs WHERE client_id = ? ORDER BY updated_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def get_analysis_job(db: Database, job_id: str) -> AnalysisJobRecord | None:
    row = db.fetchone("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
    return _build_analysis_job_record(row) if row else None


def list_analysis_job_stages(db: Database, job_id: str) -> list[AnalysisJobStageRunRecord]:
    return [
        _build_stage_run_record(row)
        for row in db.fetchall(
            "SELECT * FROM job_stage_runs WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,),
        )
    ]


def get_runtime_run_log(db: Database, run_id: str) -> RuntimeRunLogRecord | None:
    row = db.fetchone("SELECT * FROM runtime_run_logs WHERE id = ?", (run_id,))
    return _build_runtime_run_log_record(row) if row else None


def list_runtime_run_logs(db: Database, client_id: str, limit: int = 8) -> list[RuntimeRunLogRecord]:
    return [
        _build_runtime_run_log_record(row)
        for row in db.fetchall(
            "SELECT * FROM runtime_run_logs WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def list_theme_clusters(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[ThemeClusterRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM theme_clusters WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_theme_cluster_record(row) for row in db.fetchall(query, tuple(params))]


def list_conflict_groups(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[ConflictGroupRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM conflict_groups WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_conflict_group_record(row) for row in db.fetchall(query, tuple(params))]


def list_open_questions(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[OpenQuestionRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM open_questions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_open_question_record(row) for row in db.fetchall(query, tuple(params))]


def list_judgment_versions(
    db: Database,
    client_id: str,
    limit: int = 12,
    target_type: AnalysisScopeType | None = None,
    target_id: str | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
) -> list[JudgmentVersionRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    authority_clause = """
        CASE authority_level
            WHEN 'approved' THEN 2
            WHEN 'candidate' THEN 1
            ELSE 0
        END
    """
    clauses.append(f"{authority_clause} >= ?")
    params.append(_AUTHORITY_RANK[minimum_authority])
    if not include_fallback:
        clauses.append("authority_level != 'fallback'")
    params.append(limit)
    query = f"""
        SELECT *
        FROM judgment_versions
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE WHEN COALESCE(invalidated_by, '') = '' THEN 0 ELSE 1 END ASC,
            {authority_clause} DESC,
            updated_at DESC
        LIMIT ?
    """
    return [_build_judgment_version_record(row) for row in db.fetchall(query, tuple(params))]


def list_dna_deltas(db: Database, client_id: str, limit: int = 12) -> list[DnaDeltaRecord]:
    return [
        _build_dna_delta_record(row)
        for row in db.fetchall(
            "SELECT * FROM dna_deltas WHERE client_id = ? ORDER BY updated_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def resolve_analysis_scope(
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    *,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    client_id: str,
) -> list[tuple[AnalysisScopeType, str]]:
    refs = related_refs or {}
    order = _INTENT_SCOPE_ORDER[intent_profile]
    requested_by_type: dict[AnalysisScopeType, list[str]] = {
        requested_scope_type: [requested_scope_id],
        "client": [client_id],
        "event_line": refs.get("event_line", []),
        "flow": refs.get("flow", []),
        "module": refs.get("module", []),
        "meeting": refs.get("meeting", []),
        "task": refs.get("task", []),
    }
    if requested_scope_id not in requested_by_type.get(requested_scope_type, []):
        requested_by_type.setdefault(requested_scope_type, []).insert(0, requested_scope_id)

    seen: set[tuple[AnalysisScopeType, str]] = set()
    resolved: list[tuple[AnalysisScopeType, str]] = []
    for scope_type in order:
        for scope_id in requested_by_type.get(scope_type, []):
            key = (scope_type, scope_id)
            if not scope_id or key in seen:
                continue
            seen.add(key)
            resolved.append(key)
    fallback_client = ("client", client_id)
    if fallback_client not in seen:
        resolved.append(fallback_client)
    return resolved


def _scope_ref(scope_type: AnalysisScopeType, scope_id: str) -> ResolutionScopeRecord:
    return ResolutionScopeRecord(scopeType=scope_type, scopeId=scope_id)


def _ensure_writeback_scope(
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    *,
    writeback_scope_type: AnalysisScopeType | None = None,
    writeback_scope_id: str | None = None,
    allow_scope_upgrade: bool = False,
) -> ResolutionScopeRecord:
    resolved_scope_type = writeback_scope_type or requested_scope_type
    resolved_scope_id = writeback_scope_id or requested_scope_id
    requested_rank = _SCOPE_GRANULARITY.get(requested_scope_type, 0)
    writeback_rank = _SCOPE_GRANULARITY.get(resolved_scope_type, 0)
    if not allow_scope_upgrade and writeback_rank > requested_rank:
        raise ValueError("writeback scope cannot automatically broaden beyond requested scope")
    return _scope_ref(resolved_scope_type, resolved_scope_id)


def _resolve_rejected_reason(
    judgment: JudgmentVersionRecord,
    *,
    topic: str | None,
    minimum_authority: AnalysisAuthorityLevel,
    include_fallback: bool,
    already_selected: bool,
) -> AnalysisRejectedReason | None:
    if topic and judgment.topic != topic:
        return "scope_less_relevant"
    if judgment.staleReason == "superseded_by_newer_judgment":
        return "superseded"
    if judgment.invalidatedBy or judgment.staleReason:
        return "stale"
    if judgment.status in {"awaiting_revision", "rejected"}:
        return "insufficient_evidence"
    if _AUTHORITY_RANK[judgment.authorityLevel] < _AUTHORITY_RANK[minimum_authority]:
        return "authority_too_low"
    if not include_fallback and judgment.authorityLevel != "approved":
        return "not_approved_for_official_use"
    if already_selected:
        return "scope_less_relevant"
    return None


def _candidate_from_judgment(
    judgment: JudgmentVersionRecord,
    *,
    rejected_reason: AnalysisRejectedReason | None = None,
) -> ResolutionCandidateRecord:
    return ResolutionCandidateRecord(
        objectId=judgment.id,
        topic=judgment.topic,
        scopeType=judgment.targetType,
        scopeId=judgment.targetId,
        originType=judgment.originType,
        authorityLevel=judgment.authorityLevel,
        qualityTier=judgment.qualityTier,
        staleReason=judgment.staleReason,
        status=judgment.status,
        rejectedReason=rejected_reason,
    )


def resolve_current_approval_state(
    db: Database,
    target_type: str,
    target_id: str,
) -> ApprovalStateRecord:
    row = db.fetchone(
        """
        SELECT *
        FROM approval_records
        WHERE approval_target_type = ? AND approval_target_id = ?
        ORDER BY COALESCE(decided_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (target_type, target_id),
    )
    if not row:
        return ApprovalStateRecord(targetType=target_type, targetId=target_id)
    approval = _build_approval_record(row)
    current_status: AnalysisReviewState | None = {
        "approved": "approved",
        "rejected": "rejected",
        "returned_for_revision": "awaiting_revision",
    }.get(approval.decision)
    return ApprovalStateRecord(
        targetType=target_type,
        targetId=target_id,
        currentDecision=approval.decision,
        currentStatus=current_status,
        lastApproval=approval,
    )


def resolve_best_judgment(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    topic: str | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
    restrict_to_requested_scope: bool = False,
) -> tuple[JudgmentVersionRecord | None, ResolutionTraceRecord]:
    candidates = (
        [(requested_scope_type, requested_scope_id)]
        if restrict_to_requested_scope
        else resolve_analysis_scope(
            requested_scope_type,
            requested_scope_id,
            intent_profile=intent_profile,
            related_refs=related_refs,
            client_id=client_id,
        )
    )
    considered: list[ResolutionCandidateRecord] = []
    selected: JudgmentVersionRecord | None = None
    resolved_scope: ResolutionScopeRecord | None = None
    for scope_type, scope_id in candidates:
        items = list_judgment_versions(
            db,
            client_id,
            limit=8,
            target_type=scope_type,
            target_id=scope_id,
            minimum_authority="fallback",
            include_fallback=True,
        )
        if not items:
            considered.append(
                ResolutionCandidateRecord(
                    scopeType=scope_type,
                    scopeId=scope_id,
                    rejectedReason="insufficient_evidence",
                )
            )
            continue
        for item in items:
            rejected_reason = _resolve_rejected_reason(
                item,
                topic=topic,
                minimum_authority=minimum_authority,
                include_fallback=include_fallback,
                already_selected=selected is not None,
            )
            if rejected_reason is None:
                selected = item
                resolved_scope = _scope_ref(scope_type, scope_id)
                considered.append(_candidate_from_judgment(item))
            else:
                considered.append(_candidate_from_judgment(item, rejected_reason=rejected_reason))
    fallback_reason: str | None = None
    if selected is None:
        fallback_reason = "no_judgment_found"
    elif selected.authorityLevel == "fallback":
        fallback_reason = "resolved_to_fallback_authority"
    return selected, ResolutionTraceRecord(
        selectedCandidate=_candidate_from_judgment(selected) if selected else None,
        consideredCandidates=considered,
        requestedScope=_scope_ref(requested_scope_type, requested_scope_id),
        resolvedScope=resolved_scope,
        writebackScope=_ensure_writeback_scope(requested_scope_type, requested_scope_id),
        fallbackUsed=selected is None or selected.authorityLevel == "fallback",
        fallbackReason=fallback_reason,
    )


def resolve_judgment_bundle(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    topic: str | None = None,
) -> JudgmentBundleRecord:
    baseline, trace = resolve_best_judgment(
        db,
        client_id=client_id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=requested_scope_id,
        intent_profile=intent_profile,
        related_refs=None,
        topic=topic,
        minimum_authority="fallback",
        include_fallback=True,
        restrict_to_requested_scope=True,
    )
    overlays: list[JudgmentVersionRecord] = []
    seen_ids: set[str] = {baseline.id} if baseline else set()
    for scope_type, scope_id in resolve_analysis_scope(
        requested_scope_type,
        requested_scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        client_id=client_id,
    ):
        if scope_type == "client":
            continue
        for item in list_judgment_versions(
            db,
            client_id,
            limit=4,
            target_type=scope_type,
            target_id=scope_id,
            minimum_authority="candidate",
            include_fallback=False,
        ):
            if topic and item.topic != topic:
                continue
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            overlays.append(item)
    overlays.sort(
        key=lambda item: (
            _AUTHORITY_RANK[item.authorityLevel],
            0 if item.targetType == "event_line" else 1,
            item.updatedAt,
        ),
        reverse=True,
    )
    return JudgmentBundleRecord(
        baselineJudgment=baseline,
        overlayDeltas=overlays[:8],
        resolutionTrace=trace,
    )


def resolve_context_pack(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
) -> tuple[ContextPackRecord | None, dict[str, Any]]:
    candidates = resolve_analysis_scope(
        requested_scope_type,
        requested_scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        client_id=client_id,
    )
    for scope_type, scope_id in candidates:
        rows = db.fetchall(
            """
            SELECT *
            FROM context_packs
            WHERE client_id = ? AND target_type = ? AND target_id = ?
            ORDER BY
                CASE WHEN COALESCE(invalidated_by, '') = '' THEN 0 ELSE 1 END ASC,
                CASE authority_level WHEN 'approved' THEN 2 WHEN 'candidate' THEN 1 ELSE 0 END DESC,
                updated_at DESC
            LIMIT 8
            """,
            (client_id, scope_type, scope_id),
        )
        packs = [_build_context_pack_record(row) for row in rows]
        packs = [
            item for item in packs
            if _AUTHORITY_RANK[item.authorityLevel] >= _AUTHORITY_RANK[minimum_authority]
            and (include_fallback or item.authorityLevel != "fallback")
        ]
        if not packs:
            continue
        chosen = packs[0]
        return chosen, {
            "objectId": chosen.id,
            "scopeType": scope_type,
            "scopeId": scope_id,
            "originType": chosen.originType,
            "authorityLevel": chosen.authorityLevel,
            "qualityTier": chosen.qualityTier,
            "fallbackUsed": chosen.authorityLevel == "fallback",
            "requestedScopeType": requested_scope_type,
            "requestedScopeId": requested_scope_id,
            "intentProfile": intent_profile,
            "reason": "resolved_by_priority_chain",
        }
    return None, {
        "scopeType": requested_scope_type,
        "scopeId": requested_scope_id,
        "requestedScopeType": requested_scope_type,
        "requestedScopeId": requested_scope_id,
        "intentProfile": intent_profile,
        "fallbackUsed": True,
        "reason": "no_context_pack_found",
    }


def _build_related_refs(workspace: ClientWorkspaceResponse) -> dict[str, list[str]]:
    return {
        "event_line": _unique([item.eventLineId for item in workspace.relatedTasks if item.eventLineId]),
        "flow": [item.id for item in workspace.projectFlows[:12]],
        "module": [item.id for item in workspace.projectModules[:12]],
        "meeting": [item.id for item in workspace.meetings[:12]],
        "task": [item.id for item in workspace.relatedTasks[:24]],
    }


def _build_analysis_center_summary(db: Database, client_id: str) -> AnalysisCenterSummaryRecord:
    latest_job = db.fetchone("SELECT * FROM analysis_jobs WHERE client_id = ? ORDER BY updated_at DESC LIMIT 1", (client_id,))
    latest_context_pack = db.fetchone(
        "SELECT updated_at FROM context_packs WHERE client_id = ? ORDER BY updated_at DESC LIMIT 1",
        (client_id,),
    )
    latest_run_log = db.fetchone(
        "SELECT id, summary FROM runtime_run_logs WHERE client_id = ? ORDER BY created_at DESC LIMIT 1",
        (client_id,),
    )
    return AnalysisCenterSummaryRecord(
        clientId=client_id,
        evidenceCardCount=db.scalar("SELECT COUNT(*) AS count FROM evidence_cards WHERE client_id = ?", (client_id,)),
        themeClusterCount=db.scalar("SELECT COUNT(*) AS count FROM theme_clusters WHERE client_id = ?", (client_id,)),
        conflictGroupCount=db.scalar("SELECT COUNT(*) AS count FROM conflict_groups WHERE client_id = ?", (client_id,)),
        openQuestionCount=db.scalar("SELECT COUNT(*) AS count FROM open_questions WHERE client_id = ?", (client_id,)),
        draftJudgmentCount=db.scalar(
            "SELECT COUNT(*) AS count FROM judgment_versions WHERE client_id = ? AND status IN ('draft', 'awaiting_review', 'awaiting_revision')",
            (client_id,),
        ),
        approvedJudgmentCount=db.scalar(
            "SELECT COUNT(*) AS count FROM judgment_versions WHERE client_id = ? AND status = 'approved'",
            (client_id,),
        ),
        analysisJobCount=db.scalar("SELECT COUNT(*) AS count FROM analysis_jobs WHERE client_id = ?", (client_id,)),
        latestJobStatus=str(latest_job["status"]) if latest_job and latest_job["status"] else None,
        latestJobLabel=str(latest_job["stage_label"]) if latest_job and latest_job["stage_label"] else None,
        latestContextPackUpdatedAt=str(latest_context_pack["updated_at"]) if latest_context_pack else None,
        latestRunLogId=str(latest_run_log["id"]) if latest_run_log and latest_run_log["id"] else None,
        latestRunSummary=str(latest_run_log["summary"]) if latest_run_log and latest_run_log["summary"] else None,
    )


def _pick_topic_keys(card: DocumentCardRecord) -> list[str]:
    return _unique(
        [
            card.primaryCategory,
            card.secondaryCategory,
            *card.keywords[:3],
            *card.tags[:2],
        ]
    )[:4]


def _sync_doc_skeletons(db: Database, workspace: ClientWorkspaceResponse, now: str) -> None:
    for card in workspace.documentCards:
        outline = _unique(
            [
                card.primaryCategory,
                card.secondaryCategory,
                *card.coreQuestions[:3],
                *card.distinctFindings[:2],
            ]
        )[:6]
        entities = _unique(card.entities + card.keywords)[:8]
        record_id = _stable_id("docskeleton", workspace.client.id, card.documentId)
        _upsert_doc_skeleton(
            db,
            {
                "id": record_id,
                "client_id": workspace.client.id,
                "document_id": card.documentId,
                "title": card.title,
                "outline": outline,
                "entities": entities,
                "time_range": card.dateRange,
                "parser_version": "analysis-center-v1",
                "source_snapshot": to_json(
                    {
                        "docId": card.docId,
                        "documentRole": card.documentRole,
                        "summary": card.shortSummary,
                        "queryHints": card.queryHints[:4],
                    }
                ),
                "created_at": now,
                "updated_at": now,
            },
        )


def _event_line_groups(tasks: list[TaskRecord]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not task.eventLineId:
            continue
        group = groups.setdefault(
            task.eventLineId,
            {
                "id": task.eventLineId,
                "name": task.eventLineName or task.title,
                "tasks": [],
            },
        )
        group["tasks"].append(task)
        if task.eventLineName:
            group["name"] = task.eventLineName
    return groups


def _sync_evidence_cards(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[str]:
    evidence_ids: list[str] = []

    def create_card(
        *,
        scope_type: AnalysisScopeType,
        scope_id: str,
        source_type: str,
        source_id: str,
        source_ref: str,
        quote: str,
        normalized_claim: str,
        evidence_type: str,
        tags: list[str] | None = None,
        topic_keys: list[str] | None = None,
        confidence: float = 0.55,
        time_anchor: str | None = None,
        document_id: str | None = None,
        event_line_id: str | None = None,
        task_id: str | None = None,
        meeting_id: str | None = None,
        module_id: str | None = None,
        flow_id: str | None = None,
        review_state: AnalysisReviewState = "draft",
    ) -> None:
        clean_quote = _truncate(quote, 320)
        clean_claim = _truncate(normalized_claim, 240)
        if not clean_quote or not clean_claim:
            return
        normalized_claim_hash = _hash_text(clean_claim.lower())
        source_ref_hash = _hash_text((source_ref or "").strip().lower())
        evidence_fingerprint = hashlib.sha1(
            "::".join(
                [
                    normalized_claim_hash,
                    evidence_type,
                    "neutral",
                    time_anchor or "",
                    scope_type,
                    scope_id,
                    source_ref_hash,
                ]
            ).encode("utf-8")
        ).hexdigest()
        fingerprint = hashlib.sha1(
            "::".join(
                [
                    workspace.client.id,
                    scope_type,
                    scope_id,
                    source_type,
                    source_id,
                    clean_claim,
                    evidence_fingerprint,
                ]
            ).encode("utf-8")
        ).hexdigest()
        record_id = _stable_id("evidence", workspace.client.id, scope_type, scope_id, source_type, source_id, clean_claim[:80])
        _upsert_evidence_card(
            db,
            {
                "id": record_id,
                "client_id": workspace.client.id,
                "scope_type": scope_type,
                "scope_id": scope_id,
                **_truth_fields(
                    origin_type=origin_type,
                    authority_level=authority_level,
                    quality_tier=quality_tier,
                ),
                "source_type": source_type,
                "source_id": source_id,
                "source_ref": source_ref,
                "quote": clean_quote,
                "normalized_claim": clean_claim,
                "evidence_type": evidence_type,
                "polarity": "neutral",
                "tags": _unique(tags or [])[:8],
                "topic_keys": _unique(topic_keys or [])[:6],
                "confidence": confidence,
                "time_anchor": time_anchor,
                "document_id": document_id,
                "event_line_id": event_line_id,
                "task_id": task_id,
                "meeting_id": meeting_id,
                "module_id": module_id,
                "flow_id": flow_id,
                "review_state": review_state,
                "fingerprint": fingerprint,
                "normalized_claim_hash": normalized_claim_hash,
                "source_ref_hash": source_ref_hash,
                "evidence_fingerprint": evidence_fingerprint,
                "normalizer_version": "analysis-center-v0.3.3",
                "created_at": now,
                "updated_at": now,
            },
        )
        evidence_ids.append(record_id)

    for card in workspace.documentCards[:24]:
        claim = _first_non_empty(
            card.shortSummary,
            card.summary,
            card.retrievalSummary,
            fallback=card.title,
        )
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="document_card",
            source_id=card.id,
            source_ref=card.title,
            quote=claim,
            normalized_claim=claim,
            evidence_type="document_summary",
            tags=card.tags + [card.documentRole],
            topic_keys=_pick_topic_keys(card),
            confidence=max(card.classificationConfidence, 0.45),
            time_anchor=card.dateRange,
            document_id=card.documentId,
            review_state="awaiting_review" if card.needsReview else "draft",
        )
        for finding in card.distinctFindings[:2]:
            create_card(
                scope_type="client",
                scope_id=workspace.client.id,
                source_type="document_finding",
                source_id=f"{card.id}:{finding[:36]}",
                source_ref=card.title,
                quote=finding,
                normalized_claim=finding,
                evidence_type="finding",
                tags=card.tags,
                topic_keys=_pick_topic_keys(card),
                confidence=max(card.classificationConfidence, 0.52),
                time_anchor=card.dateRange,
                document_id=card.documentId,
            )

    for module in workspace.dnaModules:
        if not module.hasDocument:
            continue
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="dna_module",
            source_id=module.moduleKey,
            source_ref=module.title,
            quote=_first_non_empty(module.summary, module.normalizedText, fallback=module.title),
            normalized_claim=_first_non_empty(module.summary, fallback=f"{module.title} 已接入"),
            evidence_type="dna_module",
            tags=[module.moduleKey, "dna"],
            topic_keys=[module.moduleKey, module.title],
            confidence=0.72,
            time_anchor=module.updatedAt,
        )

    for goal in workspace.goals[:4]:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="goal",
            source_id=goal.id,
            source_ref=goal.title,
            quote=goal.title,
            normalized_claim=f"{goal.title} 当前进度 {goal.progress}%，负责人 {goal.ownerName}",
            evidence_type="goal_anchor",
            tags=["goal", goal.quarter],
            topic_keys=["goal", goal.title],
            confidence=0.7,
            time_anchor=goal.quarter,
        )

    for meeting in workspace.meetings[:4]:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="meeting",
            source_id=meeting.id,
            source_ref=meeting.title,
            quote=f"{meeting.title} 当前处于 {meeting.stage} 阶段",
            normalized_claim=f"会议 {meeting.title} 已沉淀到 {meeting.stage} 阶段",
            evidence_type="meeting_signal",
            tags=["meeting", meeting.stage],
            topic_keys=["meeting", meeting.title],
            confidence=0.62,
            time_anchor=meeting.updatedAt,
            meeting_id=meeting.id,
        )

    for task in workspace.relatedTasks[:40]:
        scope_type: AnalysisScopeType = "event_line" if task.eventLineId else "client"
        scope_id = task.eventLineId or workspace.client.id
        task_claim = _first_non_empty(
            task.projectContext.currentBlocker if task.projectContext else None,
            task.projectContext.recentProgress if task.projectContext else None,
            task.desc,
            fallback=task.title,
        )
        create_card(
            scope_type=scope_type,
            scope_id=scope_id,
            source_type="task",
            source_id=task.id,
            source_ref=task.title,
            quote=task_claim,
            normalized_claim=f"{task.title}：{task.status}，负责人 {task.ownerName}",
            evidence_type="task_signal",
            tags=[
                task.status,
                task.priority,
                task.projectModuleName or "",
                task.projectFlowName or "",
            ],
            topic_keys=_unique(
                [
                    task.eventLineName,
                    task.projectModuleName,
                    task.projectFlowName,
                    task.clientName,
                ]
            )[:4],
            confidence=max(task.backgroundReadiness.score, 0.35) if task.backgroundReadiness else 0.35,
            time_anchor=task.updatedAt,
            event_line_id=task.eventLineId,
            task_id=task.id,
            module_id=task.projectModuleId,
            flow_id=task.projectFlowId,
            review_state="awaiting_review" if task.backgroundReadiness and task.backgroundReadiness.level == "low" else "draft",
        )

    for module in workspace.projectModules:
        create_card(
            scope_type="module",
            scope_id=module.id,
            source_type="project_module",
            source_id=module.id,
            source_ref=module.name,
            quote=_first_non_empty(module.goal, module.description, fallback=module.name),
            normalized_claim=f"模块 {module.name} 目标：{_first_non_empty(module.goal, module.description, fallback='待补')}",
            evidence_type="module_definition",
            tags=["module", module.ownerName or ""],
            topic_keys=[module.name, "module"],
            confidence=0.66,
            time_anchor=module.updatedAt,
            module_id=module.id,
        )

    for flow in workspace.projectFlows:
        create_card(
            scope_type="flow",
            scope_id=flow.id,
            source_type="project_flow",
            source_id=flow.id,
            source_ref=flow.name,
            quote=_first_non_empty(flow.description, flow.scenario, fallback=flow.name),
            normalized_claim=f"流程 {flow.name} 适用于 {flow.scenario or '待补'}",
            evidence_type="flow_definition",
            tags=["flow", flow.moduleName or ""],
            topic_keys=[flow.name, flow.moduleName or "", "flow"],
            confidence=0.64,
            time_anchor=flow.updatedAt,
            module_id=flow.moduleId,
            flow_id=flow.id,
        )

    if notebook_summary:
        for fact in notebook_summary.recentFacts[:3]:
            create_card(
                scope_type="client",
                scope_id=workspace.client.id,
                source_type="organization_notebook",
                source_id=notebook_summary.id,
                source_ref="organization_notebook",
                quote=fact,
                normalized_claim=fact,
                evidence_type="notebook_fact",
                tags=["notebook"],
                topic_keys=notebook_summary.businessModules[:3] or [workspace.client.name],
                confidence=max(notebook_summary.confidence, 0.55),
                time_anchor=notebook_summary.updatedAt,
            )

    if memory_status and memory_status.lowEvidenceJudgments:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="memory_status",
            source_id=workspace.client.id,
            source_ref="memory_status",
            quote=f"当前仍有 {memory_status.lowEvidenceJudgments} 条低证据判断待补强。",
            normalized_claim="当前客户判断层还有低证据区域，需要进一步补材料或补会议。",
            evidence_type="memory_gap",
            tags=["memory", "low_evidence"],
            topic_keys=["memory_gap"],
            confidence=0.7,
            time_anchor=memory_status.updatedAt,
            review_state="awaiting_review",
        )

    return evidence_ids


def _evidence_cluster_key(row: Any) -> tuple[str, str]:
    return (
        str(row["evidence_fingerprint"] or row["fingerprint"] or row["id"]),
        str(row["normalizer_version"] or ""),
    )


def _list_evidence_ids_by_scope(
    db: Database,
    client_id: str,
    scope_type: AnalysisScopeType,
    scope_id: str,
    *,
    dedupe_by_cluster_key: bool = False,
) -> list[str]:
    rows = db.fetchall(
        """
        SELECT id, evidence_fingerprint, fingerprint, normalizer_version
        FROM evidence_cards
        WHERE client_id = ? AND scope_type = ? AND scope_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id, scope_type, scope_id),
    )
    if not dedupe_by_cluster_key:
        return [str(row["id"]) for row in rows]
    deduped_ids: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = _evidence_cluster_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped_ids.append(str(row["id"]))
    return deduped_ids


def _sync_theme_clusters(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[ThemeClusterRecord]:
    records: list[ThemeClusterRecord] = []
    client_scope_ids = _list_evidence_ids_by_scope(
        db,
        workspace.client.id,
        "client",
        workspace.client.id,
        dedupe_by_cluster_key=True,
    )

    for module in workspace.dnaModules:
        if not module.hasDocument:
            continue
        evidence_ids = [
            evidence_id
            for evidence_id in client_scope_ids
            if module.moduleKey in evidence_id or module.title[:12] in evidence_id
        ][:4]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "client", workspace.client.id, module.moduleKey),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=module.moduleKey,
                title=module.title,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(module.missingInfo[:3]),
                latestChangeSummary=_first_non_empty(module.summary, fallback=f"{module.title} 已接入项目公共上下文"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for module in workspace.projectModules:
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "module",
            module.id,
            dedupe_by_cluster_key=True,
        )[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "module", module.id, module.name),
                clientId=workspace.client.id,
                scopeType="module",
                scopeId=module.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=module.name,
                title=module.name,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="" if module.description or module.goal else "当前模块还没有明确目标和说明。",
                latestChangeSummary=_first_non_empty(module.goal, module.description, fallback="模块已建立，但目标仍待补充。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for flow in workspace.projectFlows:
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "flow",
            flow.id,
            dedupe_by_cluster_key=True,
        )[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "flow", flow.id, flow.name),
                clientId=workspace.client.id,
                scopeType="flow",
                scopeId=flow.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=flow.name,
                title=flow.name,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="" if flow.description or flow.steps else "当前流程还没有足够细的说明。",
                latestChangeSummary=_first_non_empty(flow.description, flow.scenario, fallback="流程已建立，但应用场景仍待补齐。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for event_line_id, group in _event_line_groups(workspace.relatedTasks).items():
        tasks: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        task_titles = [task.title for task in tasks[:2]]
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "event_line",
            event_line_id,
            dedupe_by_cluster_key=True,
        )[:8]
        missing_parts = [
            "缺当前阻塞" if not any((task.currentBlocker or (task.projectContext.currentBlocker if task.projectContext else "")) for task in tasks) else "",
            "缺下一步" if not any((task.nextAction or (task.projectContext.nextAction if task.projectContext else "")) for task in tasks) else "",
        ]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "event_line", event_line_id, group["name"]),
                clientId=workspace.client.id,
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=group["name"],
                title=group["name"],
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(_unique(missing_parts)),
                latestChangeSummary=_first_non_empty(*task_titles, fallback="事件线已建立，但最近推进记录仍偏少。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    if notebook_summary and notebook_summary.businessModules:
        evidence_ids = client_scope_ids[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "client", workspace.client.id, "organization_notebook"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="organization_notebook",
                title="组织与合作理解",
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(notebook_summary.informationGaps[:3]),
                latestChangeSummary=_first_non_empty(
                    notebook_summary.currentStage,
                    notebook_summary.collaborationRelationship,
                    fallback="组织级协作关系已进入统一认知层。",
                ),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for record in records:
        _upsert_theme_cluster(db, record)
    return records


def _build_event_line_question(
    task_group: list[TaskRecord],
    event_line_id: str,
    event_line_name: str,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[OpenQuestionRecord]:
    questions: list[OpenQuestionRecord] = []
    if not any((task.desc or "").strip() for task in task_group):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", event_line_id, "desc"),
                clientId=task_group[0].clientId or "",
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=event_line_name,
                question=f"{event_line_name} 还缺少完整背景描述，这条线到底在推进什么？",
                reason="事件线下的任务标题存在，但缺少连续背景。",
                blockerLevel="medium",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )
    if not any((task.nextAction or (task.projectContext.nextAction if task.projectContext else "")) for task in task_group):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", event_line_id, "next"),
                clientId=task_group[0].clientId or "",
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=event_line_name,
                question=f"{event_line_name} 的下一步动作还没有被结构化记录。",
                reason="任务有推进，但未形成统一下一步。",
                blockerLevel="high",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )
    return questions


def _sync_open_questions_and_conflicts(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> tuple[list[OpenQuestionRecord], list[ConflictGroupRecord]]:
    questions: list[OpenQuestionRecord] = []
    conflicts: list[ConflictGroupRecord] = []

    for gap in (notebook_summary.informationGaps[:4] if notebook_summary else []):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", workspace.client.id, "client", gap),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="client_notebook",
                question=gap,
                reason="当前客户背景资料里还缺少这部分信息。",
                blockerLevel="medium",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )

    if memory_status and memory_status.lowEvidenceJudgments:
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", workspace.client.id, "client", "low_evidence"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="evidence_gap",
                question="当前有哪些客户判断仍然建立在低证据基础上？",
                reason=f"系统识别到 {memory_status.lowEvidenceJudgments} 条低证据判断。",
                blockerLevel="high",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )

    if memory_status and memory_status.pendingClarifications:
        conflicts.append(
            ConflictGroupRecord(
                id=_stable_id("conflict", workspace.client.id, "clarification"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                conflictType="pending_clarification",
                title="客户主判断仍受待澄清问题影响",
                summary=f"当前还有 {memory_status.pendingClarifications} 个待澄清问题，不能直接把现有结论抬成正式判断。",
                evidenceIds=[],
                unresolvedQuestionIds=[],
                resolutionStatus="awaiting_review",
                severity="high",
                createdAt=now,
                updatedAt=now,
            )
        )

    event_line_groups = _event_line_groups(workspace.relatedTasks)
    for event_line_id, group in event_line_groups.items():
        task_group: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        questions.extend(
            _build_event_line_question(
                task_group,
                event_line_id,
                group["name"],
                now,
                origin_type=origin_type,
                authority_level=authority_level,
                quality_tier=quality_tier,
            )
        )
        blocked_titles = [
            _first_non_empty(task.currentBlocker, task.projectContext.currentBlocker if task.projectContext else None)
            for task in task_group
        ]
        blockers = _unique(blocked_titles)
        if blockers:
            conflicts.append(
                ConflictGroupRecord(
                    id=_stable_id("conflict", workspace.client.id, event_line_id, "blocker"),
                    clientId=workspace.client.id,
                    scopeType="event_line",
                    scopeId=event_line_id,
                    originType=origin_type,
                    authorityLevel=authority_level,
                    qualityTier=quality_tier,
                    conflictType="blocker_cluster",
                    title=f"{group['name']} 当前卡点",
                    summary="；".join(blockers[:3]),
                    evidenceIds=_list_evidence_ids_by_scope(
                        db,
                        workspace.client.id,
                        "event_line",
                        event_line_id,
                        dedupe_by_cluster_key=True,
                    )[:4],
                    unresolvedQuestionIds=[item.id for item in questions if item.scopeType == "event_line" and item.scopeId == event_line_id][:3],
                    resolutionStatus="awaiting_review",
                    severity="high" if len(blockers) > 1 else "medium",
                    createdAt=now,
                    updatedAt=now,
                )
            )

    for question in questions:
        _upsert_open_question(db, question)
    for conflict in conflicts:
        _upsert_conflict_group(db, conflict)
    return questions, conflicts


def _sync_context_pack(
    db: Database,
    workspace: ClientWorkspaceResponse,
    target_type: AnalysisScopeType,
    target_id: str,
    theme_clusters: list[ThemeClusterRecord],
    conflict_groups: list[ConflictGroupRecord],
    open_questions: list[OpenQuestionRecord],
    job_id: str | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> ContextPackRecord:
    target_themes = [
        item
        for item in theme_clusters
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    target_conflicts = [
        item
        for item in conflict_groups
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    target_questions = [
        item
        for item in open_questions
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    evidence_ids = _list_evidence_ids_by_scope(db, workspace.client.id, target_type, target_id)
    if target_type != "client":
        evidence_ids = evidence_ids + _list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)
    current_row = db.fetchone(
        """
        SELECT id
        FROM context_packs
        WHERE client_id = ? AND target_type = ? AND target_id = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, target_type, target_id, source_snapshot_hash),
    )
    previous_row = db.fetchone(
        """
        SELECT id
        FROM context_packs
        WHERE client_id = ? AND target_type = ? AND target_id = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, target_type, target_id),
    )
    context_pack_id = str(current_row["id"]) if current_row else _new_id("ctx")
    context_pack = ContextPackRecord(
        id=context_pack_id,
        clientId=workspace.client.id,
        jobId=job_id,
        targetType=target_type,
        targetId=target_id,
        originType=origin_type,
        authorityLevel=authority_level,
        qualityTier=quality_tier,
        supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        promptVersion="analysis-center-v1",
        sourceCount=len(workspace.documentCards) + len(workspace.meetings) + len(workspace.relatedTasks),
        evidenceCount=len(_unique(evidence_ids)),
        payload={
            "client": {
                "id": workspace.client.id,
                "name": workspace.client.name,
                "stage": workspace.client.stage,
                "intro": workspace.client.intro,
            },
            "scope": {"type": target_type, "id": target_id},
            "goals": [goal.title for goal in workspace.goals[:4]],
            "dnaModules": [
                {
                    "key": module.moduleKey,
                    "title": module.title,
                    "summary": module.summary,
                    "missingInfo": module.missingInfo[:3],
                }
                for module in workspace.dnaModules
                if module.hasDocument
            ],
            "projectModules": [
                {
                    "id": module.id,
                    "name": module.name,
                    "goal": module.goal,
                    "ownerName": module.ownerName,
                }
                for module in workspace.projectModules[:6]
            ],
            "projectFlows": [
                {
                    "id": flow.id,
                    "name": flow.name,
                    "moduleName": flow.moduleName,
                    "scenario": flow.scenario,
                    "riskPoints": flow.riskPoints[:3],
                }
                for flow in workspace.projectFlows[:6]
            ],
            "themes": [_model_dump(item) for item in target_themes[:8]],
            "conflicts": [_model_dump(item) for item in target_conflicts[:6]],
            "openQuestions": [_model_dump(item) for item in target_questions[:8]],
            "latestMeetings": [
                {
                    "id": meeting.id,
                    "title": meeting.title,
                    "stage": meeting.stage,
                    "updatedAt": meeting.updatedAt,
                }
                for meeting in workspace.meetings[:5]
            ],
            "relatedTasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "ownerName": task.ownerName,
                    "eventLineId": task.eventLineId,
                    "eventLineName": task.eventLineName,
                    "moduleName": task.projectModuleName,
                    "flowName": task.projectFlowName,
                }
                for task in workspace.relatedTasks[:12]
                if target_type == "client"
                or (target_type == "event_line" and task.eventLineId == target_id)
                or (target_type == "module" and task.projectModuleId == target_id)
                or (target_type == "flow" and task.projectFlowId == target_id)
            ],
        },
        staleAt=None,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_context_pack(db, context_pack)
    if not current_row:
        _mark_previous_record_stale(
            db,
            "context_packs",
            str(previous_row["id"]) if previous_row else None,
            invalidated_by=context_pack.id,
            stale_reason="scope_changed" if target_type != "client" else "new_document",
            now=now,
        )
    _upsert_sync_memory_record(
        db,
        client_id=workspace.client.id,
        scope_type=target_type,
        scope_id=target_id,
        payload=DerivedSyncSerializer.serialize_context_pack(
            context_pack,
            target_themes,
            target_conflicts,
            target_questions,
        ),
        source_fingerprint=_stable_id("memfp", context_pack.id, str(context_pack.evidenceCount)),
        synced_at=now,
        now=now,
    )
    return context_pack


def _sync_dna_delta(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    context_pack: ContextPackRecord,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> DnaDeltaRecord | None:
    missing_modules = [module.title for module in workspace.dnaModules if not module.hasDocument]
    gaps = list(notebook_summary.informationGaps[:2] if notebook_summary else [])
    if not missing_modules and not gaps and not (memory_status and memory_status.lowEvidenceJudgments):
        return None
    summary_parts = []
    if missing_modules:
        summary_parts.append(f"待补模块：{'、'.join(missing_modules[:3])}")
    if gaps:
        summary_parts.append(f"信息缺口：{'；'.join(gaps[:2])}")
    if memory_status and memory_status.lowEvidenceJudgments:
        summary_parts.append(f"低证据判断 {memory_status.lowEvidenceJudgments} 条")
    current_row = db.fetchone(
        """
        SELECT id, previous_version
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, "organization_context", source_snapshot_hash),
    )
    previous_row = db.fetchone(
        """
        SELECT id
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, "organization_context"),
    )
    record = DnaDeltaRecord(
        id=str(current_row["id"]) if current_row else _new_id("dnadelta"),
        clientId=workspace.client.id,
        dimension="organization_context",
        previousVersion=None,
        originType=origin_type,
        authorityLevel=authority_level,
        qualityTier=quality_tier,
        supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        proposedChange="需要先补齐项目底稿和低证据信号，再把客户判断升格为正式 DNA。",
        summary="；".join(summary_parts),
        evidenceIds=_list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)[:6],
        confidence="medium" if missing_modules or gaps else "low",
        status="awaiting_review",
        contextPackId=context_pack.id,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_dna_delta(db, record)
    if not current_row:
        _mark_previous_record_stale(
            db,
            "dna_deltas",
            str(previous_row["id"]) if previous_row else None,
            invalidated_by=record.id,
            stale_reason="new_document",
            now=now,
        )
    return record


def _sync_judgment_versions(
    db: Database,
    workspace: ClientWorkspaceResponse,
    context_pack: ContextPackRecord,
    conflict_groups: list[ConflictGroupRecord],
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> list[JudgmentVersionRecord]:
    records: list[JudgmentVersionRecord] = []
    client_conflicts = [
        item for item in conflict_groups if item.scopeType == "client" and item.scopeId == workspace.client.id
    ]
    client_evidence = _list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)[:8]
    client_summary = _first_non_empty_non_boilerplate(
        workspace.goals[0].title if workspace.goals else None,
        workspace.documentCards[0].shortSummary if workspace.documentCards else None,
        workspace.client.intro,
        fallback=f"{workspace.client.name} 当前还处于资料与判断收束阶段。",
    )
    current_client_row = db.fetchone(
        """
        SELECT id, version
        FROM judgment_versions
        WHERE client_id = ? AND target_type = 'client' AND target_id = ? AND topic = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, workspace.client.id, "client_overview", source_snapshot_hash),
    )
    previous_client_row = db.fetchone(
        """
        SELECT id, version
        FROM judgment_versions
        WHERE client_id = ? AND target_type = 'client' AND target_id = ? AND topic = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, workspace.client.id, "client_overview"),
    )
    client_record = JudgmentVersionRecord(
            id=str(current_client_row["id"]) if current_client_row else _new_id("judgment"),
            clientId=workspace.client.id,
            targetType="client",
            targetId=workspace.client.id,
            topic="client_overview",
            version=int(current_client_row["version"] or 1) if current_client_row else int(previous_client_row["version"] or 0) + 1 if previous_client_row else 1,
            status="awaiting_review",
            originType=origin_type,
            authorityLevel=authority_level,
            qualityTier=quality_tier,
            supersedesId=None if current_client_row else (str(previous_client_row["id"]) if previous_client_row else None),
            sourceSnapshotHash=source_snapshot_hash,
            staleReason=None,
            invalidatedBy=None,
            summary=client_summary,
            evidenceIds=client_evidence,
            contextPackId=context_pack.id,
            riskLevel="high" if client_conflicts else "medium",
            confidence="medium" if len(client_evidence) >= 3 else "low",
            createdAt=now,
            updatedAt=now,
        )
    records.append(client_record)

    for event_line_id, group in _event_line_groups(workspace.relatedTasks).items():
        tasks: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        blockers = _unique(
            [
                item
                for task in tasks
                for item in (
                    task.currentBlocker,
                    task.projectContext.currentBlocker if task.projectContext else None,
                    task.nextAction,
                )
            ]
        )
        summary = _first_non_empty(
            tasks[0].desc if tasks else None,
            tasks[0].projectContext.recentProgress if tasks and tasks[0].projectContext else None,
            tasks[0].title if tasks else None,
            fallback=f"{group['name']} 当前还缺少稳定的事件线判断。",
        )
        current_row = db.fetchone(
            """
            SELECT id, version
            FROM judgment_versions
            WHERE client_id = ? AND target_type = 'event_line' AND target_id = ? AND topic = ? AND source_snapshot_hash = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (workspace.client.id, event_line_id, group["name"], source_snapshot_hash),
        )
        previous_row = db.fetchone(
            """
            SELECT id, version
            FROM judgment_versions
            WHERE client_id = ? AND target_type = 'event_line' AND target_id = ? AND topic = ? AND COALESCE(invalidated_by, '') = ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (workspace.client.id, event_line_id, group["name"]),
        )
        records.append(
            JudgmentVersionRecord(
                id=str(current_row["id"]) if current_row else _new_id("judgment"),
                clientId=workspace.client.id,
                targetType="event_line",
                targetId=event_line_id,
                topic=group["name"],
                version=int(current_row["version"] or 1) if current_row else int(previous_row["version"] or 0) + 1 if previous_row else 1,
                status="awaiting_review" if blockers else "draft",
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
                sourceSnapshotHash=source_snapshot_hash,
                staleReason=None,
                invalidatedBy=None,
                summary=summary,
                evidenceIds=_list_evidence_ids_by_scope(db, workspace.client.id, "event_line", event_line_id)[:8],
                contextPackId=context_pack.id,
                riskLevel="high" if blockers else "medium",
                confidence="medium" if len(tasks) >= 2 else "low",
                createdAt=now,
                updatedAt=now,
            )
    )

    for record in records:
        _upsert_judgment_version(db, record)
        if not record.supersedesId:
            continue
        _mark_previous_record_stale(
            db,
            "judgment_versions",
            record.supersedesId,
            invalidated_by=record.id,
            stale_reason="new_document" if record.targetType == "client" else "scope_changed",
            now=now,
        )
    return records


def _sync_runtime_logs_from_legacy_runs(db: Database, workspace: ClientWorkspaceResponse) -> list[RuntimeRunLogRecord]:
    records: list[RuntimeRunLogRecord] = []
    for run in workspace.analysisRuns[:8]:
        legacy_summary = _first_non_empty(
            run.structuredSummary.content if run.structuredSummary else None,
            run.structuredSummary.judgment if run.structuredSummary else None,
            run.structuredSummary.analysis if run.structuredSummary else None,
            run.question,
            fallback="历史分析运行",
        )
        record = RuntimeRunLogRecord(
            id=_stable_id("runlog", workspace.client.id, "legacy", run.id),
            clientId=workspace.client.id,
            jobId=None,
            provider=run.providerUsed,
            model=None,
            lane="cloud_final",
            cacheHit=False,
            degraded=run.answerMode in {"grounded_fallback", "system_failure"} or run.longAnswerStatus == "fallback",
            documentCount=run.evidenceSummary.masterHitCount + run.evidenceSummary.surrogateHitCount,
            evidenceCount=len(run.evidenceSummary.evidenceList),
            conflictCount=0,
            contextTimeRange=None,
            promptVersion="legacy-analysis-run",
            schemaVersion="legacy-analysis-run",
            summary=legacy_summary,
            detail={
                "phase": run.phase,
                "status": run.status,
                "llmInvoked": run.llmInvoked,
                "timing": run.timing,
                "latestRunSummary": legacy_summary,
            },
            createdAt=run.updatedAt,
        )
        _upsert_runtime_run_log(db, record)
        records.append(record)
    return records


def refresh_client_analysis_projection(
    db: Database,
    workspace: ClientWorkspaceResponse,
    *,
    notebook_summary: OrganizationNotebookSnapshot | None = None,
    memory_status: MemoryStatus | None = None,
    target_type: AnalysisScopeType = "client",
    target_id: str | None = None,
    job_id: str | None = None,
    origin_type: AnalysisOriginType = "projection",
    authority_level: AnalysisAuthorityLevel = "fallback",
    quality_tier: AnalysisQualityTier = "normalized",
) -> AnalysisCenterProjectionBundle:
    now = _now_iso()
    scope_id = target_id or workspace.client.id
    source_snapshot_hash = _compute_scope_snapshot_hash(workspace, scope_type=target_type, scope_id=scope_id)
    _sync_doc_skeletons(db, workspace, now)
    _sync_evidence_cards(
        db,
        workspace,
        notebook_summary,
        memory_status,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    theme_clusters = _sync_theme_clusters(
        db,
        workspace,
        notebook_summary,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    open_questions, conflict_groups = _sync_open_questions_and_conflicts(
        db,
        workspace,
        notebook_summary,
        memory_status,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    context_pack = _sync_context_pack(
        db,
        workspace,
        target_type=target_type,
        target_id=scope_id,
        theme_clusters=theme_clusters,
        conflict_groups=conflict_groups,
        open_questions=open_questions,
        job_id=job_id,
        now=now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    for conflict in conflict_groups:
        db.execute(
            "UPDATE conflict_groups SET context_pack_id = ? WHERE id = ?",
            (context_pack.id, conflict.id),
        )
    _sync_dna_delta(
        db,
        workspace,
        notebook_summary,
        memory_status,
        context_pack,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    judgments = _sync_judgment_versions(
        db,
        workspace,
        context_pack,
        conflict_groups,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    run_logs = _sync_runtime_logs_from_legacy_runs(db, workspace)
    summary = _build_analysis_center_summary(db, workspace.client.id)
    return AnalysisCenterProjectionBundle(
        summary=summary,
        latest_context_pack=context_pack,
        judgment_bundle=None,
        latest_resolution_trace=None,
        latest_judgments=judgments[:6],
        latest_topics=theme_clusters[:8],
        latest_conflicts=conflict_groups[:6],
        latest_open_questions=open_questions[:8],
        latest_run_logs=run_logs[:6] or list_runtime_run_logs(db, workspace.client.id, limit=6),
    )


def get_client_analysis_bundle(
    db: Database,
    workspace: ClientWorkspaceResponse,
    *,
    requested_scope_type: AnalysisScopeType = "client",
    requested_scope_id: str | None = None,
    intent_profile: AnalysisIntentProfile = "client_overview",
) -> AnalysisCenterProjectionBundle:
    scope_id = requested_scope_id or workspace.client.id
    related_refs = _build_related_refs(workspace)
    latest_context_pack, _ = resolve_context_pack(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        include_fallback=True,
    )
    latest_judgment, _ = resolve_best_judgment(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        include_fallback=True,
    )
    judgments = list_judgment_versions(db, workspace.client.id, limit=6)
    if latest_judgment and latest_judgment.id not in {item.id for item in judgments}:
        judgments = [latest_judgment, *judgments][:6]
    judgment_bundle = resolve_judgment_bundle(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
    )
    return AnalysisCenterProjectionBundle(
        summary=_build_analysis_center_summary(db, workspace.client.id),
        latest_context_pack=latest_context_pack,
        judgment_bundle=judgment_bundle,
        latest_resolution_trace=judgment_bundle.resolutionTrace,
        latest_judgments=judgments[:6],
        latest_topics=list_theme_clusters(db, workspace.client.id, limit=8),
        latest_conflicts=list_conflict_groups(db, workspace.client.id, limit=6),
        latest_open_questions=list_open_questions(db, workspace.client.id, limit=8),
        latest_run_logs=list_runtime_run_logs(db, workspace.client.id, limit=6),
    )


def create_analysis_job(
    db: Database,
    payload: AnalysisJobCreatePayload,
    *,
    source_snapshot: dict[str, Any] | None = None,
) -> AnalysisJobRecord:
    scope_type = payload.scopeType or "client"
    now = _now_iso()
    snapshot_payload = source_snapshot or {
        "question": payload.question,
        "sourceScope": payload.sourceScope,
        "featureFlags": payload.featureFlags,
    }
    source_snapshot_hash = _build_snapshot_hash(snapshot_payload)
    dedupe_key = _stable_id(
        "analysisdedupe",
        payload.jobType,
        payload.clientId,
        scope_type,
        payload.scopeId,
        payload.triggerType,
        payload.intentProfile,
        source_snapshot_hash,
    )
    existing_row = db.fetchone(
        """
        SELECT *
        FROM analysis_jobs
        WHERE dedupe_key = ? AND status IN ('queued', 'running')
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (dedupe_key,),
    )
    if existing_row:
        return _build_analysis_job_record(existing_row)

    job_id = _new_id("analysisjob")
    job = AnalysisJobRecord(
        id=job_id,
        jobType=payload.jobType,
        clientId=payload.clientId,
        scopeType=scope_type,
        scopeId=payload.scopeId,
        status="queued",
        priority=payload.priority,
        triggerType=payload.triggerType,
        intentProfile=payload.intentProfile,
        question=payload.question,
        sourceSnapshot=_serialize_snapshot(snapshot_payload),
        sourceSnapshotHash=source_snapshot_hash,
        dedupeKey=dedupe_key,
        featureFlags=payload.featureFlags,
        progress=0.0,
        stageLabel="已进入分析队列",
        runLogId=None,
        error=None,
        lockedBy=None,
        lockedAt=None,
        lockExpiresAt=None,
        attemptCount=0,
        lastError=None,
        createdAt=now,
        updatedAt=now,
        startedAt=None,
        finishedAt=None,
    )
    _upsert_analysis_job(db, job)
    queued_stage = AnalysisJobStageRunRecord(
        id=_stable_id("analysisstage", job.id, "queued"),
        jobId=job.id,
        stageName="queued",
        status="queued",
        provider=None,
        modelName=None,
        lane="cloud_final",
        cacheKey=None,
        cacheHit=False,
        degraded=False,
        evidenceCount=0,
        topicCount=0,
        conflictCount=0,
        contextTimeRange=None,
        metrics={},
        detail="等待进入分析中心",
        correlationId=None,
        startedAt=None,
        finishedAt=None,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_stage_run(db, queued_stage)
    return job


def _read_setting(db: Database, key: str, default: str = "") -> str:
    row = db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return str(row["value"]) if row and row["value"] is not None else default


def _write_setting(db: Database, key: str, value: str) -> None:
    _upsert(db, "settings", {"key": key, "value": value}, conflict_columns=("key",))


def _increment_json_counter_setting(db: Database, key: str, bucket: str) -> None:
    normalized_bucket = bucket if bucket in _ANALYSIS_WORKER_BUCKETS else "unknown"
    payload = _parse_json_dict(_read_setting(db, key, "{}"))
    payload[normalized_bucket] = int(payload.get(normalized_bucket, 0) or 0) + 1
    payload["updatedAt"] = _now_iso()
    _write_setting(db, key, to_json(payload))


def _worker_backfill_streak_key(worker_id: str) -> str:
    return f"analysis.worker.backfill_streak.{worker_id}"


def _get_worker_backfill_streak(db: Database, worker_id: str) -> int:
    try:
        return int(_read_setting(db, _worker_backfill_streak_key(worker_id), "0") or 0)
    except ValueError:
        return 0


def _set_worker_backfill_streak(db: Database, worker_id: str, streak: int) -> None:
    _write_setting(db, _worker_backfill_streak_key(worker_id), str(max(streak, 0)))


def _record_analysis_job_bucket_claim(db: Database, bucket: str) -> None:
    _increment_json_counter_setting(db, "analysis.worker.claim_counts", bucket)


def _record_analysis_job_lock_contention(db: Database, bucket: str) -> None:
    _increment_json_counter_setting(db, "analysis.worker.lock_contention", bucket)


def renew_analysis_job_lock(
    db: Database,
    job_id: str,
    worker_id: str,
    *,
    ttl_minutes: int = 10,
) -> None:
    now = _now_iso()
    lock_expires_at = (datetime.now() + timedelta(minutes=ttl_minutes)).replace(microsecond=0).isoformat()
    db.execute(
        """
        UPDATE analysis_jobs
        SET locked_at = ?,
            lock_expires_at = ?,
            updated_at = ?
        WHERE id = ? AND status = 'running' AND COALESCE(locked_by, '') = ?
        """,
        (now, lock_expires_at, now, job_id, worker_id),
    )


def get_candidate_review_sla_summary(db: Database, *, client_id: str | None = None) -> dict[str, int]:
    exclude_ids = _build_canary_exclusion_scope(db)
    recent_cutoff = (datetime.now() - timedelta(hours=24)).replace(microsecond=0).isoformat()
    warning_cutoff = (datetime.now() - timedelta(hours=_CANDIDATE_REVIEW_WARNING_AFTER_HOURS)).replace(microsecond=0).isoformat()
    overdue_cutoff = (datetime.now() - timedelta(hours=_CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS)).replace(microsecond=0).isoformat()
    new_unreviewed_24h_count = 0
    warning_count = 0
    overdue_count = 0
    for table_name, status_column in (
        ("judgment_versions", "status"),
        ("dna_deltas", "status"),
        ("conflict_groups", "resolution_status"),
    ):
        rows = db.fetchall(
            f"""
            SELECT id, created_at
            FROM {table_name}
            WHERE {status_column} IN ('awaiting_review', 'awaiting_revision')
            {" AND client_id = ?" if client_id else ""}
            """,
            tuple([client_id] if client_id else []),
        )
        excluded_for_table = exclude_ids.get(table_name, set())
        for row in rows:
            row_id = str(row["id"] or "")
            if row_id in excluded_for_table:
                continue
            created_at = _parse_dt(str(row["created_at"] or ""))
            if created_at is None:
                continue
            created_iso = created_at.replace(microsecond=0).isoformat()
            if created_iso >= recent_cutoff:
                new_unreviewed_24h_count += 1
            if created_iso <= warning_cutoff:
                warning_count += 1
            if created_iso <= overdue_cutoff:
                overdue_count += 1
    return {
        "warningAfterHours": _CANDIDATE_REVIEW_WARNING_AFTER_HOURS,
        "overdueAfterHours": _CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS,
        "newUnreviewed24hCount": new_unreviewed_24h_count,
        "warningCount": warning_count,
        "overdueCount": overdue_count,
    }


def is_analysis_backfill_paused(db: Database) -> bool:
    return _read_setting(db, "analysis.backfill.paused", "0") == "1"


def set_analysis_backfill_paused(db: Database, paused: bool) -> bool:
    _write_setting(db, "analysis.backfill.paused", "1" if paused else "0")
    return paused


def queue_main_chain_backfill(
    db: Database,
    payload: AnalysisBackfillMainChainPayload,
) -> AnalysisBackfillMainChainResultRecord:
    paused = set_analysis_backfill_paused(db, payload.pauseRequested) if payload.pauseRequested else is_analysis_backfill_paused(db)
    client_ids = payload.clientIds or [str(row["id"]) for row in db.fetchall("SELECT id FROM clients ORDER BY updated_at DESC")]
    max_jobs = max(1, min(payload.maxJobs, 500))
    batch_size = max(1, min(payload.batchSize, max_jobs))
    candidates: list[AnalysisBackfillMainChainJobRecord] = []
    for client_id in client_ids:
        for intent_profile in ("client_overview", "dna_summary", "strategic_cockpit"):
            if len(candidates) >= max_jobs:
                break
            candidates.append(
                AnalysisBackfillMainChainJobRecord(
                    clientId=client_id,
                    scopeType="client",
                    scopeId=client_id,
                    jobType="strategy_pack",
                    triggerType="backfill",
                    intentProfile=intent_profile,
                )
            )
        if len(candidates) >= max_jobs:
            break
    if payload.dryRun:
        return AnalysisBackfillMainChainResultRecord(
            dryRun=True,
            pauseRequested=payload.pauseRequested,
            paused=paused,
            scannedClients=len(client_ids),
            queuedJobs=0,
            skippedJobs=0,
            candidates=candidates[:batch_size],
        )
    queued_jobs = 0
    skipped_jobs = 0
    for candidate in candidates[:batch_size]:
        existing_active = db.fetchone(
            """
            SELECT id
            FROM analysis_jobs
            WHERE client_id = ? AND scope_type = ? AND scope_id = ? AND trigger_type = ? AND intent_profile = ?
              AND status IN ('queued', 'running')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                candidate.clientId,
                candidate.scopeType,
                candidate.scopeId,
                candidate.triggerType,
                candidate.intentProfile,
            ),
        )
        if existing_active:
            skipped_jobs += 1
            continue
        create_analysis_job(
            db,
            AnalysisJobCreatePayload(
                jobType=candidate.jobType,
                clientId=candidate.clientId,
                scopeType=candidate.scopeType,
                scopeId=candidate.scopeId,
                priority="low",
                triggerType=candidate.triggerType,
                question="主链 backfill",
                intentProfile=candidate.intentProfile,
            ),
            source_snapshot={
                "clientId": candidate.clientId,
                "scopeType": candidate.scopeType,
                "scopeId": candidate.scopeId,
                "triggerType": candidate.triggerType,
                "intentProfile": candidate.intentProfile,
            },
        )
        queued_jobs += 1
    return AnalysisBackfillMainChainResultRecord(
        dryRun=False,
        pauseRequested=payload.pauseRequested,
        paused=paused,
        scannedClients=len(client_ids),
        queuedJobs=queued_jobs,
        skippedJobs=skipped_jobs,
        candidates=candidates[:batch_size],
    )


def recover_stale_analysis_jobs(db: Database) -> None:
    now = _now_iso()
    db.execute(
        """
        UPDATE analysis_jobs
        SET status = 'queued',
            stage_label = '检测到中断，已重新入队',
            locked_by = NULL,
            locked_at = NULL,
            lock_expires_at = NULL,
            updated_at = ?
        WHERE status IN ('running', 'preparing', 'extracting', 'clustering', 'comparing', 'drafting')
        """,
        (now,),
    )


def claim_next_analysis_job(db: Database, worker_id: str) -> AnalysisJobRecord | None:
    now = _now_iso()
    lock_expires_at = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    backfill_paused = is_analysis_backfill_paused(db)
    backfill_streak = _get_worker_backfill_streak(db, worker_id)

    bucket_queries = {
        "interactive": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') != 'backfill'
              AND (
                priority = 'high'
                OR COALESCE(trigger_type, 'manual') = 'manual'
                OR intent_profile IN ('task_ai', 'meeting_enhance')
              )
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
        "system": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') != 'backfill'
              AND NOT (
                priority = 'high'
                OR COALESCE(trigger_type, 'manual') = 'manual'
                OR intent_profile IN ('task_ai', 'meeting_enhance')
              )
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
        "backfill": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') = 'backfill'
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
    }

    def _claim(conn):
        bucket_order = ["interactive", "system"]
        if not backfill_paused and backfill_streak < _ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT:
            bucket_order.append("backfill")
        for bucket in bucket_order:
            query, params = bucket_queries[bucket]
            row = conn.execute(query, params).fetchone()
            if not row:
                continue
            updated = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'running',
                    stage_label = '正在执行分析任务',
                    locked_by = ?,
                    locked_at = ?,
                    lock_expires_at = ?,
                    attempt_count = COALESCE(attempt_count, 0) + 1,
                    updated_at = ?,
                    started_at = COALESCE(started_at, ?)
                WHERE id = ?
                  AND status = 'queued'
                  AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
                """,
                (worker_id, now, lock_expires_at, now, now, str(row["id"]), now),
            )
            if updated.rowcount != 1:
                return {"jobId": None, "bucket": bucket, "contention": True}
            return {"jobId": str(row["id"]), "bucket": bucket, "contention": False}
        return {"jobId": None, "bucket": "backfill", "contention": False}

    claim_result = db.run_in_transaction(_claim)
    claimed_job_id = str(claim_result.get("jobId") or "")
    claimed_bucket = str(claim_result.get("bucket") or "unknown")
    if claim_result.get("contention"):
        _record_analysis_job_lock_contention(db, claimed_bucket)
    if not claimed_job_id:
        if not backfill_paused and backfill_streak >= _ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT:
            _increment_json_counter_setting(db, "analysis.worker.backfill_throttle", "backfill")
            _set_worker_backfill_streak(db, worker_id, 0)
        return None
    _record_analysis_job_bucket_claim(db, claimed_bucket)
    if claimed_bucket == "backfill":
        _set_worker_backfill_streak(db, worker_id, backfill_streak + 1)
    else:
        _set_worker_backfill_streak(db, worker_id, 0)
    return get_analysis_job(db, claimed_job_id)


def fail_analysis_job(
    db: Database,
    job_id: str,
    *,
    stage_name: str,
    error: str,
    correlation_id: str | None = None,
) -> AnalysisJobRecord | None:
    job = get_analysis_job(db, job_id)
    if job is None:
        return None
    now_dt = datetime.now().replace(microsecond=0)
    now = now_dt.isoformat()
    retry_schedule = [30, 120, 600]
    should_retry = job.attemptCount <= len(retry_schedule)
    retry_delay = retry_schedule[job.attemptCount - 1] if should_retry and job.attemptCount > 0 else None
    retry_at = (now_dt + timedelta(seconds=retry_delay)).isoformat() if retry_delay is not None else None
    _upsert_stage_run(
        db,
        AnalysisJobStageRunRecord(
            id=_stable_id("analysisstage", job.id, stage_name, str(job.attemptCount), "failed"),
            jobId=job.id,
            stageName=stage_name,
            status="failed",
            provider="analysis-center",
            modelName="analysis-center-v0.3.2",
            lane="cloud_final",
            cacheKey=None,
            cacheHit=False,
            degraded=False,
            evidenceCount=0,
            topicCount=0,
            conflictCount=0,
            contextTimeRange=None,
            metrics={"attempt": job.attemptCount},
            detail=_truncate(error, 280),
            correlationId=correlation_id,
            startedAt=job.startedAt,
            finishedAt=now,
            createdAt=now,
            updatedAt=now,
        ),
    )
    failed_or_queued = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "queued" if should_retry else "failed",
            "progress": max(float(job.progress or 0.0), 1.0),
            "stageLabel": f"执行失败，{retry_delay}s 后重试" if should_retry and retry_delay is not None else "执行失败",
            "error": error if not should_retry else None,
            "lastError": error,
            "lockedBy": None,
            "lockedAt": None,
            "lockExpiresAt": retry_at if should_retry else None,
            "updatedAt": now,
            "finishedAt": None if should_retry else now,
        }
    )
    _upsert_analysis_job(db, failed_or_queued)
    return failed_or_queued


def execute_analysis_job_projection(
    db: Database,
    job: AnalysisJobRecord,
    workspace: ClientWorkspaceResponse,
    *,
    notebook_summary: OrganizationNotebookSnapshot | None = None,
    memory_status: MemoryStatus | None = None,
    lane: AnalysisLane = "cloud_final",
) -> AnalysisJobRecord:
    started_at = _now_iso()
    correlation_id = _stable_id("analysiscorr", job.id, str(job.attemptCount or 0), started_at)
    running_stage = AnalysisJobStageRunRecord(
        id=_stable_id("analysisstage", job.id, "analysis_pipeline", str(job.attemptCount or 0)),
        jobId=job.id,
        stageName="analysis_pipeline",
        status="running",
        provider="analysis-center",
        modelName="analysis-center-v0.3.2",
        lane=lane,
        cacheKey=job.sourceSnapshotHash or None,
        cacheHit=False,
        degraded=False,
        evidenceCount=0,
        topicCount=0,
        conflictCount=0,
        contextTimeRange=None,
        metrics={"attempt": job.attemptCount},
        detail="正在执行证据提取、主题归并和判断生成",
        correlationId=correlation_id,
        startedAt=started_at,
        finishedAt=None,
        createdAt=started_at,
        updatedAt=started_at,
    )
    _upsert_stage_run(db, running_stage)
    started_summary = f"{job.scopeType} 级分析任务已启动"
    run_log = RuntimeRunLogRecord(
        id=_stable_id("runlog", workspace.client.id, "analysis_job", job.id, str(job.attemptCount or 0)),
        clientId=workspace.client.id,
        jobId=job.id,
        analysisJobId=job.id,
        stageRunId=running_stage.id,
        contextPackId=None,
        judgmentVersionId=None,
        correlationId=correlation_id,
        provider="analysis-center",
        model="analysis-center-v0.3.2",
        lane=lane,
        cacheHit=False,
        degraded=False,
        documentCount=len(workspace.documentCards),
        evidenceCount=0,
        conflictCount=0,
        contextTimeRange=None,
        promptVersion="analysis-center-v0.3",
        schemaVersion="analysis-center-v0.3",
        summary=started_summary,
        detail={
            "jobType": job.jobType,
            "scopeId": job.scopeId,
            "scopeType": job.scopeType,
            "question": job.question,
            "intentProfile": job.intentProfile,
            "sourceSnapshotHash": job.sourceSnapshotHash,
            "latestRunSummary": started_summary,
        },
        createdAt=started_at,
    )
    _upsert_runtime_run_log(db, run_log)

    running_job = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "running",
            "progress": 18.0,
            "stageLabel": "正在生成证据与主题对象",
            "runLogId": run_log.id,
            "updatedAt": started_at,
            "startedAt": started_at,
        }
    )
    _upsert_analysis_job(db, running_job)
    if running_job.lockedBy:
        renew_analysis_job_lock(db, running_job.id, running_job.lockedBy)

    bundle = refresh_client_analysis_projection(
        db,
        workspace,
        notebook_summary=notebook_summary,
        memory_status=memory_status,
        target_type=job.scopeType,
        target_id=job.scopeId,
        job_id=job.id,
        origin_type="analysis",
        authority_level="candidate",
        quality_tier="normalized",
    )
    if running_job.lockedBy:
        renew_analysis_job_lock(db, running_job.id, running_job.lockedBy)
    best_judgment, resolution_trace = resolve_best_judgment(
        db,
        client_id=workspace.client.id,
        requested_scope_type=job.scopeType,
        requested_scope_id=job.scopeId,
        intent_profile=job.intentProfile,
        related_refs=_build_related_refs(workspace),
        include_fallback=True,
    )

    finished_at = _now_iso()
    _upsert_stage_run(
        db,
        AnalysisJobStageRunRecord(
            id=_stable_id("analysisstage", job.id, "analysis_pipeline", str(job.attemptCount or 0), "completed"),
            jobId=job.id,
            stageName="analysis_pipeline",
            status="completed",
            provider="analysis-center",
            modelName="analysis-center-v0.3.2",
            lane=lane,
            cacheKey=job.sourceSnapshotHash or None,
            cacheHit=False,
            degraded=False,
            evidenceCount=bundle.summary.evidenceCardCount,
            topicCount=bundle.summary.themeClusterCount,
            conflictCount=bundle.summary.conflictGroupCount,
            contextTimeRange=bundle.latest_context_pack.updatedAt if bundle.latest_context_pack else None,
            metrics={
                "evidenceCount": bundle.summary.evidenceCardCount,
                "topicCount": bundle.summary.themeClusterCount,
                "conflictCount": bundle.summary.conflictGroupCount,
                "draftJudgmentCount": bundle.summary.draftJudgmentCount,
            },
            detail="主链投影完成，已生成 context pack 与 judgment draft",
            correlationId=correlation_id,
            startedAt=started_at,
            finishedAt=finished_at,
            createdAt=finished_at,
            updatedAt=finished_at,
        ),
    )

    finished_summary = f"{job.scopeType} 级分析投影已完成"
    _upsert_runtime_run_log(
        db,
        RuntimeRunLogRecord(
            id=run_log.id,
            clientId=run_log.clientId,
            jobId=run_log.jobId,
            analysisJobId=job.id,
            stageRunId=running_stage.id,
            contextPackId=bundle.latest_context_pack.id if bundle.latest_context_pack else None,
            judgmentVersionId=best_judgment.id if best_judgment else None,
            correlationId=correlation_id,
            provider=run_log.provider,
            model=run_log.model,
            lane=run_log.lane,
            cacheHit=False,
            degraded=False,
            documentCount=len(workspace.documentCards),
            evidenceCount=bundle.summary.evidenceCardCount,
            conflictCount=bundle.summary.conflictGroupCount,
            contextTimeRange=bundle.latest_context_pack.updatedAt if bundle.latest_context_pack else None,
            promptVersion=run_log.promptVersion,
            schemaVersion=run_log.schemaVersion,
            summary=finished_summary,
            detail={
                "latestContextPackId": bundle.latest_context_pack.id if bundle.latest_context_pack else None,
                "latestJudgmentId": best_judgment.id if best_judgment else None,
                "draftJudgmentCount": bundle.summary.draftJudgmentCount,
                "latestRunSummary": bundle.summary.latestRunSummary or finished_summary,
                "intentProfile": job.intentProfile,
                "sourceSnapshotHash": job.sourceSnapshotHash,
                "resolutionTrace": resolution_trace.model_dump(mode="json"),
            },
            createdAt=run_log.createdAt,
        ),
    )

    completed_job = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "completed",
            "progress": 100.0,
            "stageLabel": "已生成 judgment draft，等待人工确认",
            "runLogId": run_log.id,
            "error": None,
            "lastError": None,
            "lockedBy": None,
            "lockedAt": None,
            "lockExpiresAt": None,
            "updatedAt": finished_at,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    _upsert_analysis_job(db, completed_job)
    return completed_job


def create_dna_delta(db: Database, payload: DnaDeltaCreatePayload) -> DnaDeltaRecord:
    now = _now_iso()
    source_snapshot_hash = _build_snapshot_hash(
        {
            "clientId": payload.clientId,
            "dimension": payload.dimension,
            "proposedChange": payload.proposedChange,
            "summary": payload.summary,
            "evidenceIds": payload.evidenceIds,
            "contextPackId": payload.contextPackId,
        }
    )
    current_row = db.fetchone(
        """
        SELECT id
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (payload.clientId, payload.dimension),
    )
    record = DnaDeltaRecord(
        id=_new_id("dnadelta"),
        clientId=payload.clientId,
        dimension=payload.dimension,
        previousVersion=None,
        originType="human_override",
        authorityLevel="candidate",
        qualityTier="reviewed",
        supersedesId=str(current_row["id"]) if current_row else None,
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        proposedChange=payload.proposedChange,
        summary=payload.summary,
        evidenceIds=payload.evidenceIds,
        confidence=payload.confidence,
        status="awaiting_review",
        contextPackId=payload.contextPackId,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_dna_delta(db, record)
    _mark_previous_record_stale(
        db,
        "dna_deltas",
        str(current_row["id"]) if current_row else None,
        invalidated_by=record.id,
        stale_reason="manual_override",
        now=now,
    )
    return record


def _build_approval_record(row: Any) -> ApprovalRecordRecord:
    return ApprovalRecordRecord(
        id=str(row["id"]),
        approvalTargetType=str(row["approval_target_type"] or row["object_type"]),
        approvalTargetId=str(row["approval_target_id"] or row["object_id"]),
        clientId=str(row["client_id"]),
        policyType=str(row["policy_type"] or "analysis_review"),
        decision=str(row["decision"] or row["status"]),
        comment=str(row["comment"] or row["note"] or ""),
        decidedBy=str(row["decided_by"] or row["actor_name"] or ""),
        decidedAt=str(row["decided_at"] or row["created_at"]),
        metadata=_parse_json_dict(row["metadata_json"]),
    )


def decide_approval(
    db: Database,
    payload: ApprovalDecisionPayload,
    *,
    actor_id: str = "",
    actor_name: str = "",
) -> ApprovalRecordRecord:
    now = _now_iso()
    target_table = {
        "judgment_version": ("judgment_versions", _build_judgment_version_record, _upsert_judgment_version, "status"),
        "dna_delta": ("dna_deltas", _build_dna_delta_record, _upsert_dna_delta, "status"),
        "conflict_group": ("conflict_groups", _build_conflict_group_record, _upsert_conflict_group, "resolutionStatus"),
    }.get(payload.targetType)
    if target_table is None:
        raise ValueError("不支持的审批目标类型")
    table_name, row_builder, upsert_fn, status_field = target_table
    row = db.fetchone(f"SELECT * FROM {table_name} WHERE id = ?", (payload.targetId,))
    if not row:
        raise ValueError("审批目标不存在")
    record = row_builder(row)
    next_state: AnalysisReviewState = {
        "approved": "approved",
        "rejected": "rejected",
        "returned_for_revision": "awaiting_revision",
    }[payload.decision]
    updates = {
        **_model_dump(record),
        status_field: next_state,
        "updatedAt": now,
    }
    if hasattr(record, "authorityLevel"):
        updates["authorityLevel"] = "approved" if payload.decision == "approved" else record.authorityLevel
    if hasattr(record, "qualityTier") and payload.decision == "approved":
        updates["qualityTier"] = "reviewed"
    updated_record = type(record)(**updates)
    upsert_fn(db, updated_record)
    approval_id = _new_id("approval")
    _upsert(
        db,
        "approval_records",
        {
            "id": approval_id,
            "object_type": payload.targetType,
            "object_id": payload.targetId,
            "client_id": getattr(record, "clientId", ""),
            "status": payload.decision,
            "note": payload.comment,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "created_at": now,
            "approval_target_type": payload.targetType,
            "approval_target_id": payload.targetId,
            "policy_type": payload.policyType,
            "decision": payload.decision,
            "comment": payload.comment,
            "decided_by": actor_name or actor_id,
            "decided_at": now,
            "metadata_json": to_json(payload.metadata),
        },
    )
    approval_row = db.fetchone("SELECT * FROM approval_records WHERE id = ?", (approval_id,))
    if not approval_row:
        raise ValueError("审批记录写入失败")
    return _build_approval_record(approval_row)


def confirm_judgment(db: Database, payload: JudgmentConfirmPayload, *, actor_id: str = "", actor_name: str = "") -> JudgmentVersionRecord:
    decide_approval(
        db,
        ApprovalDecisionPayload(
            targetType="judgment_version",
            targetId=payload.judgmentId,
            decision=payload.action,
            comment=payload.note,
        ),
        actor_id=actor_id,
        actor_name=actor_name,
    )
    row = db.fetchone("SELECT * FROM judgment_versions WHERE id = ?", (payload.judgmentId,))
    if not row:
        raise ValueError("目标 judgment 不存在")
    return _build_judgment_version_record(row)


def get_analysis_migration_metrics(db: Database, *, window_days: int = 7) -> AnalysisMigrationMetricsRecord:
    cutoff = (datetime.now() - timedelta(days=window_days)).replace(microsecond=0).isoformat()
    rows = db.fetchall(
        "SELECT * FROM runtime_run_logs WHERE created_at >= ? ORDER BY created_at DESC",
        (cutoff,),
    )
    page_bucket_map = {
        "task_ai": "task_ai",
        "weekly_review": "weekly_review",
        "meeting_enhance": "meeting_enhance",
        "client_overview": "client_overview",
        "dna_summary": "dna_summary",
        "strategic_cockpit": "strategic_cockpit",
    }
    page_counts: dict[str, dict[str, float | int]] = {}
    resolver_groups: dict[tuple[str, str, str, str, str], set[str]] = {}
    total = 0
    new_object_hits = 0
    fallback_hits = 0
    for row in rows:
        detail = _parse_json_dict(row["detail_json"])
        trace = detail.get("resolutionTrace") if isinstance(detail.get("resolutionTrace"), dict) else {}
        selected = trace.get("selectedCandidate") if isinstance(trace.get("selectedCandidate"), dict) else {}
        requested_scope = trace.get("requestedScope") if isinstance(trace.get("requestedScope"), dict) else {}
        intent_profile = str(detail.get("intentProfile") or "client_overview")
        page_key = page_bucket_map.get(intent_profile, intent_profile)
        page_counts.setdefault(page_key, {"total": 0, "newHits": 0, "fallbackHits": 0, "mismatchGroups": 0})
        page_counts[page_key]["total"] = int(page_counts[page_key]["total"]) + 1
        total += 1
        fallback_used = bool(trace.get("fallbackUsed"))
        origin_type = str(selected.get("originType") or trace.get("originType") or "")
        if fallback_used:
            fallback_hits += 1
            page_counts[page_key]["fallbackHits"] = int(page_counts[page_key]["fallbackHits"]) + 1
        elif origin_type and origin_type != "projection":
            new_object_hits += 1
            page_counts[page_key]["newHits"] = int(page_counts[page_key]["newHits"]) + 1
        selected_object_id = str(
            selected.get("objectId")
            or trace.get("objectId")
            or detail.get("judgmentVersionId")
            or ""
        )
        requested_scope_type = str(
            requested_scope.get("scopeType")
            or trace.get("requestedScopeType")
            or "client"
        )
        requested_scope_id = str(
            requested_scope.get("scopeId")
            or trace.get("requestedScopeId")
            or row["client_id"]
            or ""
        )
        source_snapshot_hash = str(detail.get("sourceSnapshotHash") or "")
        if selected_object_id:
            resolver_groups.setdefault(
                (str(row["client_id"]), requested_scope_type, requested_scope_id, intent_profile, source_snapshot_hash),
                set(),
            ).add(selected_object_id)

    canary_exclusion_ids = _build_canary_exclusion_scope(db)
    target_type_to_table = {
        "judgment_version": "judgment_versions",
        "dna_delta": "dna_deltas",
        "conflict_group": "conflict_groups",
    }

    approval_rows = db.fetchall(
        """
        SELECT approval_target_type, approval_target_id, decision, decided_at
        FROM approval_records
        WHERE decided_at >= ?
        ORDER BY decided_at DESC
        """,
        (cutoff,),
    )
    approval_lags: list[float] = []
    for row in approval_rows:
        target_type = str(row["approval_target_type"] or "")
        target_id = str(row["approval_target_id"] or "")
        decided_at = _parse_dt(str(row["decided_at"] or ""))
        if not target_type or not target_id or decided_at is None:
            continue
        table_name = target_type_to_table.get(target_type)
        if not table_name:
            continue
        if target_id in canary_exclusion_ids.get(table_name, set()):
            continue
        target_row = db.fetchone(f"SELECT created_at FROM {table_name} WHERE id = ?", (target_id,))
        created_at = _parse_dt(str(target_row["created_at"] or "")) if target_row else None
        if created_at is None:
            continue
        approval_lags.append(max((decided_at - created_at).total_seconds() / 3600.0, 0.0))
    approval_lags.sort()
    median_approval_lag = approval_lags[len(approval_lags) // 2] if approval_lags else 0.0
    approval_backlog_queries = (
        (
            "judgment_versions",
            "status",
        ),
        (
            "dna_deltas",
            "status",
        ),
        (
            "conflict_groups",
            "resolution_status",
        ),
    )
    approval_backlog = 0
    for table_name, status_column in approval_backlog_queries:
        rows = db.fetchall(
            f"""
            SELECT id
            FROM {table_name}
            WHERE {status_column} IN ('awaiting_review', 'awaiting_revision')
            """
        )
        excluded_for_table = canary_exclusion_ids.get(table_name, set())
        approval_backlog += sum(1 for row in rows if str(row["id"] or "") not in excluded_for_table)
    candidate_review_sla = get_candidate_review_sla_summary(db)

    candidate_total = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'candidate' AND created_at >= ?",
        (cutoff,),
    )
    approved_total = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'approved' AND updated_at >= ?",
        (cutoff,),
    )
    stale_approved_count = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'approved' AND COALESCE(invalidated_by, '') != ''",
    )
    mismatch_count_by_page: dict[str, int] = defaultdict(int)
    for (_, _, _, intent_profile, _), selected_ids in resolver_groups.items():
        if len(selected_ids) > 1:
            mismatch_count_by_page[page_bucket_map.get(intent_profile, intent_profile)] += 1
    resolver_mismatch_groups = sum(1 for selected_ids in resolver_groups.values() if len(selected_ids) > 1)
    resolver_mismatch_rate = (resolver_mismatch_groups / len(resolver_groups)) if resolver_groups else 0.0
    page_breakdown: dict[str, dict[str, float | int]] = {}
    for page_key, bucket in page_counts.items():
        bucket_total = int(bucket["total"])
        mismatch_groups = mismatch_count_by_page.get(page_key, 0)
        page_breakdown[page_key] = {
            "newObjectHitRate": round((int(bucket["newHits"]) / bucket_total) if bucket_total else 0.0, 4),
            "fallbackRate": round((int(bucket["fallbackHits"]) / bucket_total) if bucket_total else 0.0, 4),
            "resolverMismatchRate": round((mismatch_groups / bucket_total) if bucket_total else 0.0, 4),
            "totalRuns": bucket_total,
        }
    return AnalysisMigrationMetricsRecord(
        windowDays=window_days,
        newObjectHitRate=round((new_object_hits / total) if total else 0.0, 4),
        fallbackRate=round((fallback_hits / total) if total else 0.0, 4),
        approvalBacklog=approval_backlog,
        approvalLagHoursMedian=round(median_approval_lag, 2),
        candidateReviewWarningCount=int(candidate_review_sla["warningCount"]),
        candidateReviewOverdueCount=int(candidate_review_sla["overdueCount"]),
        newCandidateUnreviewed24h=int(candidate_review_sla["newUnreviewed24hCount"]),
        candidateToApprovedConversionRate=round((approved_total / candidate_total) if candidate_total else 0.0, 4),
        staleApprovedJudgmentCount=stale_approved_count,
        resolverMismatchRate=round(resolver_mismatch_rate, 4),
        pageBreakdown=page_breakdown,
    )
~~~

## `backend/app/services/badge_engine.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    BadgeActionLinkRecord,
    BadgeBoardOverviewRecord,
    BadgeBoardResponse,
    BadgeCategoryRecord,
    BadgeEvidenceRecord,
    BadgeProgressRecord,
    BadgeState,
    GrowthAbilityKey,
    GrowthContextLinkRecord,
)

AbilityLabel = Literal["沟通协作", "客户导向", "执行推进", "组织管理", "经营意识", "学习沉淀"]
RuleType = Literal["count", "consecutive", "ratio", "sequence", "composite"]

ABILITY_LABELS: dict[GrowthAbilityKey, str] = {
    "collab": "沟通协作",
    "insight": "客户导向",
    "exec": "执行推进",
    "write": "组织管理",
    "risk": "经营意识",
    "analyze": "学习沉淀",
}

CATEGORY_DEFINITIONS: list[dict[str, Any]] = [
    {"id": "task_progress", "label": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "color": "#E8913A", "order": 1},
    {"id": "calendar_rhythm", "label": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "color": "#4A9CC7", "order": 2},
    {"id": "meeting_notes", "label": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#5BA8C8", "order": 3},
    {"id": "customer_insight", "label": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "color": "#3F51B5", "order": 4},
    {"id": "relationship_collab", "label": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#2E7D32", "order": 5},
    {"id": "research_intel", "label": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "color": "#546E7A", "order": 6},
    {"id": "judgment_strategy", "label": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "color": "#6A1B9A", "order": 7},
    {"id": "delivery_product", "label": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "color": "#E57373", "order": 8},
    {"id": "team_management", "label": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#1A237E", "order": 9},
    {"id": "ai_digital", "label": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "color": "#263238", "order": 10},
]


@dataclass(frozen=True)
class WorkEvent:
    event_id: str
    module: str
    event_type: str
    object_type: str
    object_id: str
    occurred_at: str
    title: str
    payload: dict[str, Any]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _week_label(value: str) -> str:
    dt = _parse_dt(value)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _period_key(value: str, unit: str) -> str:
    dt = _parse_dt(value)
    if unit == "day":
        return dt.strftime("%Y-%m-%d")
    if unit == "month":
        return dt.strftime("%Y-%m")
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _period_order(key: str, unit: str) -> int:
    if unit == "day":
        return int(key.replace("-", ""))
    if unit == "month":
        year, month = key.split("-")
        return int(year) * 12 + int(month)
    year, week = key.split("-W")
    return int(year) * 53 + int(week)


def _matches_filters(payload: dict[str, Any], filters: dict[str, Any] | None = None, required_fields: list[str] | None = None) -> bool:
    if filters:
        for key, expected in filters.items():
            actual = payload.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
    if required_fields:
        for field in required_fields:
            value = payload.get(field)
            if value in (None, "", False, 0, [], {}):
                return False
    return True


def _unique_events(events: list[WorkEvent]) -> list[WorkEvent]:
    bucket: dict[tuple[str, str], WorkEvent] = {}
    for event in sorted(events, key=lambda item: (_parse_dt(item.occurred_at), item.event_id), reverse=True):
        key = (event.object_type, event.object_id)
        bucket.setdefault(key, event)
    return list(bucket.values())


def _event_to_evidence(event: WorkEvent) -> BadgeEvidenceRecord:
    subtitle_parts = [event.module, event.event_type]
    if event.payload.get("summary"):
        subtitle_parts.insert(0, str(event.payload["summary"]))
    return BadgeEvidenceRecord(
        id=event.event_id,
        title=event.title,
        sourceType=event.event_type,
        sourceId=event.object_id,
        subtitle=" · ".join(part for part in subtitle_parts if part),
        occurredAt=event.occurred_at,
    )


def _context_tab_for_event_type(event_type: str) -> str:
    if event_type.startswith("meeting.") or event_type.startswith("client."):
        return "client_workspace"
    if event_type.startswith("analysis.") or event_type.startswith("improvement."):
        return "topics_management"
    if event_type.startswith("knowledge.") or event_type.startswith("learning."):
        return "growth_handbook"
    if event_type.startswith("finance.") or event_type.startswith("approval.") or event_type.startswith("expense."):
        return "settings"
    return "tasks"


def _context_object_type_for_event_type(event_type: str) -> str:
    if event_type.startswith("meeting.") or event_type.startswith("client."):
        return "meeting"
    if event_type.startswith("analysis.") or event_type.startswith("improvement."):
        return "analysis"
    if event_type.startswith("knowledge.") or event_type.startswith("learning."):
        return "handbook"
    if event_type.startswith("finance.") or event_type.startswith("approval.") or event_type.startswith("expense."):
        return "settings_object"
    return "task"


def _linked_contexts_from_evidences(evidences: list[BadgeEvidenceRecord]) -> list[GrowthContextLinkRecord]:
    seen: set[tuple[str, str]] = set()
    items: list[GrowthContextLinkRecord] = []
    for evidence in evidences:
        key = (evidence.sourceType, evidence.sourceId)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            GrowthContextLinkRecord(
                objectType=_context_object_type_for_event_type(evidence.sourceType),
                objectId=evidence.sourceId,
                label=evidence.title,
                subtitle=evidence.subtitle,
                tab=_context_tab_for_event_type(evidence.sourceType),
                statusLabel=evidence.sourceType,
            )
        )
    return items


def _event_type_labels_for_rule(rule: dict[str, Any]) -> list[str]:
    rule_type = str(rule.get("type") or "")
    if rule_type == "composite":
        labels: list[str] = []
        for condition in list(rule.get("conditions") or []):
            label = str(condition.get("label") or condition.get("eventType") or "").strip()
            if label:
                labels.append(label)
        return labels
    value = str(rule.get("eventType") or rule.get("numeratorEventType") or rule.get("denominatorEventType") or "").strip()
    return [value] if value else []


def _is_unconnected_event_type(value: str) -> bool:
    if value.startswith(("approval.", "expense.", "finance.")):
        return True
    return value in {
        "project.kickoff_clear",
        "learning.mentorship_completed",
    }


def _missing_signals_for_badge(rule: dict[str, Any], evidences: list[BadgeEvidenceRecord], progress_value: float, progress_target: float) -> list[str]:
    if progress_target > 0 and progress_value >= progress_target:
        return []
    expected_labels = _event_type_labels_for_rule(rule)
    if not expected_labels:
        return []
    missing: list[str] = []
    for label in expected_labels[:3]:
        if _is_unconnected_event_type(label):
            missing.append(f"{label}：当前模块未接通")
        else:
            missing.append(f"{label}：还缺真实业务信号")
    if evidences:
        missing.append("继续补齐动作、负责人、资料或闭环证据")
    return missing[:4]


def _is_method_like(text: str) -> bool:
    return any(keyword in text for keyword in ("模板", "方法", "清单", "SOP", "规范", "步骤", "复用", "流程"))


def _contains_all(text: str, keywords: list[str]) -> bool:
    return all(keyword in text for keyword in keywords)


def _collect_work_events(db: Database, *, user_name: str) -> list[WorkEvent]:
    events: list[WorkEvent] = []

    meeting_rows = db.fetchall(
        """
        SELECT
            m.*,
            (SELECT COUNT(*) FROM decisions d WHERE d.meeting_id = m.id) AS decision_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id) AS action_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.owner_name) != '') AS owner_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.due_date) != '') AS due_count,
            (SELECT COUNT(DISTINCT a.owner_name) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.owner_name) != '') AS owner_distinct_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.source_type = 'meeting' AND t.source_id = m.id) AS linked_task_count,
            (SELECT COUNT(*) FROM risks r WHERE r.meeting_id = m.id) AS risk_count,
            (SELECT COUNT(*) FROM ambiguities am WHERE am.meeting_id = m.id AND COALESCE(am.status, '') != 'ignored') AS ambiguity_count
        FROM meetings m
        ORDER BY m.updated_at DESC
        """
    )
    for row in meeting_rows:
        occurred_at = str(row["updated_at"] or row["created_at"])
        title = str(row["title"] or "未命名会议")
        notes = str(row["notes"] or "")
        stage = str(row["stage"] or "")
        payload = {
            "stage": stage,
            "decisionCount": int(row["decision_count"] or 0),
            "actionCount": int(row["action_count"] or 0),
            "ownerCount": int(row["owner_count"] or 0),
            "dueCount": int(row["due_count"] or 0),
            "ownerDistinctCount": int(row["owner_distinct_count"] or 0),
            "linkedTaskCount": int(row["linked_task_count"] or 0),
            "riskCount": int(row["risk_count"] or 0),
            "ambiguityCount": int(row["ambiguity_count"] or 0),
            "summary": "会议沉淀",
        }
        if stage == "published":
            events.append(WorkEvent(f"meeting_published_{row['id']}", "meeting", "meeting.published", "meeting", str(row["id"]), occurred_at, title, payload))
        if stage == "published" and payload["decisionCount"] >= 1 and payload["actionCount"] >= 1 and payload["ownerCount"] >= 1 and payload["dueCount"] >= 1 and payload["linkedTaskCount"] >= 1:
            events.append(WorkEvent(f"meeting_closed_loop_{row['id']}", "meeting", "meeting.closed_loop", "meeting", str(row["id"]), occurred_at, title, payload))
        if stage == "published" and (payload["ownerDistinctCount"] >= 2 or any(keyword in f"{title} {notes}" for keyword in ("跨组", "协作", "对齐", "联动"))):
            events.append(WorkEvent(f"meeting_cross_{row['id']}", "meeting", "meeting.cross_function", "meeting", str(row["id"]), occurred_at, title, payload))
        if payload["riskCount"] >= 1:
            events.append(WorkEvent(f"meeting_risk_{row['id']}", "meeting", "project.risk_flagged", "meeting", str(row["id"]), occurred_at, title, payload))
        if payload["ambiguityCount"] >= 1:
            events.append(WorkEvent(f"meeting_clarity_{row['id']}", "meeting", "client.requirement_clarified", "meeting", str(row["id"]), occurred_at, title, payload))

    review_rows = db.fetchall(
        """
        SELECT wr.id AS review_id, wr.week_label, wr.summary, wr.work_free_note, wr.created_at, wr.updated_at,
               we.id AS entry_id, we.task_id, we.note, we.structured_note_json, we.task_snapshot_json
        FROM weekly_reviews wr
        LEFT JOIN weekly_review_task_entries we ON we.review_id = wr.id
        ORDER BY wr.updated_at DESC, we.reviewed_at DESC
        """
    )
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for row in review_rows:
        review_id = str(row["review_id"])
        record = reviews_by_id.setdefault(
            review_id,
            {
                "reviewId": review_id,
                "weekLabel": str(row["week_label"] or ""),
                "summary": str(row["summary"] or row["work_free_note"] or ""),
                "updatedAt": str(row["updated_at"] or row["created_at"]),
                "entries": [],
            },
        )
        if row["entry_id"]:
            structured = from_json(row["structured_note_json"], {})
            snapshot = from_json(row["task_snapshot_json"], {})
            record["entries"].append(
                {
                    "id": str(row["entry_id"]),
                    "taskId": str(row["task_id"] or ""),
                    "note": str(row["note"] or ""),
                    "structured": structured,
                    "snapshot": snapshot,
                }
            )
    for review in reviews_by_id.values():
        if review["summary"] or review["entries"]:
            events.append(
                WorkEvent(
                    f"review_submitted_{review['reviewId']}",
                    "review",
                    "review.submitted",
                    "weekly_review",
                    review["reviewId"],
                    review["updatedAt"],
                    f"{review['weekLabel']} 周报",
                    {"weekLabel": review["weekLabel"], "summary": "周报提交"},
                )
            )
        for entry in review["entries"]:
            structured = entry["structured"]
            snapshot = entry["snapshot"] or {}
            task_title = str(snapshot.get("title") or "任务复盘")
            joined_text = " ".join(
                [
                    task_title,
                    str(entry["note"] or ""),
                    str(structured.get("reflection") or ""),
                    str(structured.get("progress") or ""),
                    str(structured.get("successExperience") or ""),
                    str(structured.get("successReason") or ""),
                    str(structured.get("failureInsight") or ""),
                    str(structured.get("blockerReason") or ""),
                    str(structured.get("supportNeeded") or ""),
                    str(structured.get("nextAction") or ""),
                ]
            )
            payload = {
                "hasConclusion": bool(structured.get("successExperience") or structured.get("successReason") or structured.get("failureInsight")),
                "hasNextAction": bool(structured.get("nextAction")),
                "hasRisk": bool(structured.get("blockerReason") or structured.get("supportNeeded") or structured.get("lightweightTag")),
                "hasAcceptanceTrace": _contains_all(joined_text, ["验收", "责任"]) and ("复测" in joined_text or "问题" in joined_text),
                "hasHandoffTrace": _contains_all(joined_text, ["背景", "风险", "下一步"]),
                "summary": "周复盘条目",
            }
            if payload["hasConclusion"] and payload["hasNextAction"]:
                events.append(
                    WorkEvent(
                        f"review_structured_{entry['id']}",
                        "review",
                        "review.structured_entry",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasConclusion"] and ("原因" in joined_text or "为什么" in joined_text or "改进" in joined_text):
                events.append(
                    WorkEvent(
                        f"review_retrospective_{entry['id']}",
                        "review",
                        "review.retrospective_completed",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasRisk"]:
                events.append(
                    WorkEvent(
                        f"review_risk_{entry['id']}",
                        "review",
                        "project.risk_flagged",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasAcceptanceTrace"]:
                events.append(
                    WorkEvent(
                        f"review_acceptance_{entry['id']}",
                        "review",
                        "project.acceptance_closed",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasHandoffTrace"]:
                events.append(
                    WorkEvent(
                        f"review_handoff_{entry['id']}",
                        "review",
                        "task.clear_handoff",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )

    handbook_rows = db.fetchall("SELECT * FROM handbook_entries ORDER BY created_at DESC")
    for row in handbook_rows:
        title = str(row["title"] or "经验沉淀")
        summary = str(row["summary"] or "")
        tags = from_json(row["tags_json"], [])
        text = " ".join([title, summary, " ".join(str(tag) for tag in tags)])
        occurred_at = str(row["created_at"])
        payload = {
            "sourceType": str(row["source_type"] or ""),
            "isMethodLike": _is_method_like(text),
            "tagCount": len(tags),
            "summary": "成长手册",
        }
        events.append(WorkEvent(f"handbook_entry_{row['id']}", "handbook", "knowledge.experience_published", "handbook_entry", str(row["id"]), occurred_at, title, payload))
        if payload["isMethodLike"]:
            events.append(WorkEvent(f"handbook_sop_{row['id']}", "handbook", "knowledge.sop_published", "handbook_entry", str(row["id"]), occurred_at, title, payload))
        if any(keyword in text for keyword in ("分享", "培训", "讲解", "课程")):
            events.append(WorkEvent(f"handbook_share_{row['id']}", "handbook", "learning.knowledge_share", "handbook_entry", str(row["id"]), occurred_at, title, payload))

    analysis_rows = db.fetchall("SELECT * FROM analysis_runs ORDER BY created_at DESC")
    for row in analysis_rows:
        title = str(row["title"] or "分析产出")
        occurred_at = str(row["created_at"])
        payload = {"status": str(row["status"] or ""), "summary": "分析工作台"}
        events.append(WorkEvent(f"analysis_dashboard_{row['id']}", "analysis", "analysis.dashboard_updated", "analysis_run", str(row["id"]), occurred_at, title, payload))
        if any(keyword in title for keyword in ("方案", "报价", "提案")):
            events.append(WorkEvent(f"analysis_proposal_{row['id']}", "analysis", "analysis.proposal_advanced", "analysis_run", str(row["id"]), occurred_at, title, payload))

    validation_rows = db.fetchall(
        """
        SELECT
            v.id,
            v.event_type,
            v.source_type,
            v.source_id,
            v.created_at,
            e.metadata_json
        FROM growth_validation_events v
        INNER JOIN growth_evidence_records e ON e.id = v.evidence_id
        ORDER BY v.created_at DESC
        """
    )
    for row in validation_rows:
        metadata = from_json(row["metadata_json"], {})
        title = str(metadata.get("sourceTitle") or "方法复用")
        payload = {"summary": "方法复用"}
        events.append(
            WorkEvent(
                f"validation_reuse_{row['id']}",
                "growth",
                "knowledge.reused",
                "growth_validation",
                str(row["id"]),
                str(row["created_at"]),
                title,
                payload,
            )
        )

    task_rows = db.fetchall("SELECT * FROM tasks ORDER BY updated_at DESC")
    for row in task_rows:
        title = str(row["title"] or "任务")
        created_at_str = str(row["created_at"] or "")
        occurred_at = str(row["updated_at"] or created_at_str)
        ddl = str(row["ddl"] or "")
        status = str(row["status"] or "")
        description = str(row["description"] or "")
        priority = str(row["priority"] or "")
        payload = {
            "status": status,
            "hasDeadline": bool(ddl),
            "sourceType": str(row["source_type"] or ""),
            "priority": priority,
            "summary": "任务推进",
        }
        # task.created — 每条任务都算一次创建事件
        events.append(WorkEvent(f"task_created_{row['id']}", "task", "task.created", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        # task.with_deadline / task.deadline_set — 有截止日的任务
        if ddl:
            events.append(WorkEvent(f"task_deadline_{row['id']}", "task", "task.with_deadline", "task", str(row["id"]), occurred_at, title, payload))
            events.append(WorkEvent(f"task_ddl_set_{row['id']}", "task", "task.deadline_set", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        if ddl and status == "done" and _parse_dt(occurred_at) <= _parse_dt(ddl):
            events.append(WorkEvent(f"task_done_on_time_{row['id']}", "task", "task.done_on_time", "task", str(row["id"]), occurred_at, title, payload))
        # task.closed_loop — 已完成的任务
        if status == "done":
            events.append(WorkEvent(f"task_closed_{row['id']}", "task", "task.closed_loop", "task", str(row["id"]), occurred_at, title, payload))
        # task.done_same_day — 当天创建当天完成
        if status == "done" and created_at_str and occurred_at:
            created_dt = _parse_dt(created_at_str)
            updated_dt = _parse_dt(occurred_at)
            if created_dt != datetime.min and updated_dt != datetime.min and created_dt.date() == updated_dt.date():
                events.append(WorkEvent(f"task_same_day_{row['id']}", "task", "task.done_same_day", "task", str(row["id"]), occurred_at, title, payload))
        # task.description_complete — 说明写得充分的任务（>30字符）
        if len(description) >= 30:
            events.append(WorkEvent(f"task_desc_ok_{row['id']}", "task", "task.description_complete", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        if str(row["source_type"] or "") == "growth_recommendation" and status == "done":
            events.append(WorkEvent(f"task_learning_done_{row['id']}", "task", "learning.path_completed", "task", str(row["id"]), occurred_at, title, payload))

    logs = db.fetchall(
        """
        SELECT id, action, entity_type, entity_id, detail_json, created_at
        FROM activity_logs
        ORDER BY created_at DESC
        """
    )
    create_times: dict[str, str] = {}
    for row in sorted(logs, key=lambda item: _parse_dt(str(item["created_at"] or ""))):
        action = str(row["action"] or "")
        entity_type = str(row["entity_type"] or "")
        entity_id = str(row["entity_id"] or "")
        detail = from_json(row["detail_json"], {})
        created_at = str(row["created_at"])
        if action == "task.create" and entity_type == "task":
            create_times[entity_id] = created_at
        if action == "task.confirm" and entity_type == "task":
            start = _parse_dt(create_times.get(entity_id))
            end = _parse_dt(created_at)
            if start != datetime.min and end != datetime.min and end - start <= timedelta(hours=24):
                events.append(
                    WorkEvent(
                        f"task_quick_confirm_{row['id']}",
                        "task",
                        "task.quick_response",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "事项已快速响应"),
                        {"summary": "任务快速接收"},
                    )
                )
        # task.status_updated — 任务状态变更
        if action == "task.update" and entity_type == "task":
            events.append(
                WorkEvent(
                    f"task_updated_{row['id']}",
                    "task",
                    "task.status_updated",
                    "task",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "任务已更新"),
                    {"summary": "任务状态更新"},
                )
            )
        # task.attachment_uploaded — 附件上传
        if action == "task.attachment.upload" and entity_type == "task":
            events.append(
                WorkEvent(
                    f"task_attach_{row['id']}",
                    "task",
                    "task.attachment_uploaded",
                    "task",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "附件已上传"),
                    {"summary": "任务附件上传"},
                )
            )
        # task.deadline_adjusted — 截止日调整（task.update 中 ddl 变化）
        if action == "task.update" and entity_type == "task":
            changes = detail.get("changes") or detail
            if changes.get("ddl") or changes.get("due_date"):
                events.append(
                    WorkEvent(
                        f"task_ddl_adj_{row['id']}",
                        "task",
                        "task.deadline_adjusted",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "截止日已调整"),
                        {"summary": "截止日调整"},
                    )
                )
        # task.assigned — 任务指派
        if action in ("task.create", "task.update") and entity_type == "task":
            owner = str(detail.get("owner_name") or detail.get("ownerName") or "")
            if owner:
                events.append(
                    WorkEvent(
                        f"task_assigned_{row['id']}",
                        "task",
                        "task.assigned",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "任务已指派"),
                        {"summary": "任务指派", "ownerName": owner},
                    )
                )
        if action == "analysis.run" and entity_type == "analysis_run":
            events.append(
                WorkEvent(
                    f"analysis_share_{row['id']}",
                    "analysis",
                    "learning.knowledge_share",
                    "analysis_run",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "分析产出"),
                    {"summary": "分析产出"},
                )
            )
        if action == "topic.promote.task" and entity_type == "topic_candidate":
            events.append(
                WorkEvent(
                    f"topic_promote_{row['id']}",
                    "topic",
                    "improvement.proposal_adopted",
                    "topic_candidate",
                    entity_id,
                    created_at,
                    "改进提案进入执行",
                    {"summary": "情报推动行动"},
                )
            )
        # AI 事件：chat.reply → ai.prompt_used + ai.assist_used
        if action == "chat.reply":
            events.append(WorkEvent(f"ai_prompt_{row['id']}", "ai", "ai.prompt_used", "chat", entity_id, created_at, str(detail.get("title") or "AI对话"), {"summary": "AI 对话"}))
            events.append(WorkEvent(f"ai_assist_{row['id']}", "ai", "ai.assist_used", "chat", entity_id, created_at, str(detail.get("title") or "AI协助"), {"summary": "AI 协助"}))
        # AI 事件：topic.candidate.insight → ai.assist_used + ai.result_reviewed
        if action == "topic.candidate.insight":
            events.append(WorkEvent(f"ai_insight_{row['id']}", "ai", "ai.assist_used", "topic_candidate", entity_id, created_at, str(detail.get("title") or "AI提炼洞察"), {"summary": "AI 提炼"}))
            events.append(WorkEvent(f"ai_reviewed_{row['id']}", "ai", "ai.result_reviewed", "topic_candidate", entity_id, created_at, str(detail.get("title") or "AI结果校对"), {"summary": "AI 校对"}))
        # 客户事件：client.update / client.dna_document.update → client.profile_enriched
        if action in ("client.update", "client.dna_document.update"):
            events.append(WorkEvent(f"client_enriched_{row['id']}", "client", "client.profile_enriched", "client", entity_id, created_at, str(detail.get("name") or "客户画像更新"), {"summary": "客户画像"}))
        # 客户事件：client.dna_document.update → client.key_person_identified
        if action == "client.dna_document.update":
            events.append(WorkEvent(f"client_key_person_{row['id']}", "client", "client.key_person_identified", "client", entity_id, created_at, str(detail.get("name") or "关键人识别"), {"summary": "关键人"}))
        # CRM事件：client.create → crm.lead_followed
        if action == "client.create":
            events.append(WorkEvent(f"crm_lead_{row['id']}", "crm", "crm.lead_followed", "client", entity_id, created_at, str(detail.get("name") or "新客户触达"), {"summary": "线索跟进"}))
        # CRM事件：client.document.create_from_text → crm.followup_completed
        if action == "client.document.create_from_text":
            events.append(WorkEvent(f"crm_followup_{row['id']}", "crm", "crm.followup_completed", "client", entity_id, created_at, str(detail.get("name") or "客户跟进"), {"summary": "客户跟进"}))
        # 模板事件：document.template_fill → task.template_used
        if action == "document.template_fill":
            events.append(WorkEvent(f"template_used_{row['id']}", "task", "task.template_used", "document", entity_id, created_at, str(detail.get("title") or "模板使用"), {"summary": "模板使用"}))

    candidate_rows = db.fetchall("SELECT * FROM topic_candidates ORDER BY updated_at DESC")
    for row in candidate_rows:
        title = str(row["title"] or "情报候选")
        occurred_at = str(row["updated_at"] or row["created_at"])
        status = str(row["status"] or "")
        payload = {"status": status, "summary": "情报候选"}
        events.append(WorkEvent(f"topic_candidate_{row['id']}", "topic", "improvement.proposal_submitted", "topic_candidate", str(row["id"]), occurred_at, title, payload))

    # 事件线活动 → crm.followup_completed + crm.opportunity_stage
    eline_rows = db.fetchall("SELECT * FROM event_line_activities ORDER BY happened_at DESC")
    for row in eline_rows:
        title = str(row["title"] or "事件线活动")
        occurred_at = str(row["happened_at"] or row["created_at"])
        eline_id = str(row["event_line_id"] or "")
        payload = {"sourceType": str(row["source_type"] or ""), "summary": "事件线推进"}
        events.append(WorkEvent(f"eline_followup_{row['id']}", "crm", "crm.followup_completed", "event_line", eline_id, occurred_at, title, payload))
        events.append(WorkEvent(f"eline_stage_{row['id']}", "crm", "crm.opportunity_stage", "event_line", eline_id, occurred_at, title, payload))

    return events


def _events_for_rule(events: list[WorkEvent], *, event_type: str, window_days: int | None = None, filters: dict[str, Any] | None = None, required_fields: list[str] | None = None) -> list[WorkEvent]:
    cutoff = datetime.now() - timedelta(days=window_days or 3650)
    matched = [
        event
        for event in events
        if event.event_type == event_type and _parse_dt(event.occurred_at) >= cutoff and _matches_filters(event.payload, filters, required_fields)
    ]
    return _unique_events(matched)


def _evaluate_count(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(
        events,
        event_type=str(rule["eventType"]),
        window_days=int(rule.get("windowDays") or 3650),
        filters=rule.get("filters"),
        required_fields=rule.get("requiredFields"),
    )
    target = float(rule.get("targetCount") or 1)
    progress = float(len(matched))
    percent = 0 if target <= 0 else min(100, int(round((progress / target) * 100)))
    remaining = max(0, int(target - progress))
    next_action = f"再完成 1 次就会点亮【{rule['badgeName']}】" if remaining == 1 else f"还差 {remaining} 次：{rule['hintTemplate']}"
    return progress, target, percent, f"{int(progress)} / {int(target)}", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_consecutive(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(
        events,
        event_type=str(rule["eventType"]),
        window_days=int(rule.get("windowDays") or 3650),
        filters=rule.get("filters"),
        required_fields=rule.get("requiredFields"),
    )
    unit = str(rule.get("unit") or "week")
    period_keys = sorted({_period_key(event.occurred_at, unit) for event in matched}, key=lambda item: _period_order(item, unit))
    longest = 0
    current = 0
    previous_order: int | None = None
    for key in period_keys:
        order = _period_order(key, unit)
        if previous_order is None or order == previous_order + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous_order = order
    target = float(rule.get("targetStreak") or 1)
    percent = 0 if target <= 0 else min(100, int(round((longest / target) * 100)))
    remaining = max(0, int(target - longest))
    next_action = f"再连续 1 个{ '周' if unit == 'week' else '周期' }就会点亮【{rule['badgeName']}】" if remaining == 1 else f"还差 {remaining} 个连续{ '周' if unit == 'week' else '周期' }：{rule['hintTemplate']}"
    return float(longest), target, percent, f"连续 {longest} / {int(target)}", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_ratio(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    numerator = _events_for_rule(events, event_type=str(rule["numeratorEventType"]), window_days=int(rule.get("windowDays") or 3650))
    denominator = _events_for_rule(events, event_type=str(rule["denominatorEventType"]), window_days=int(rule.get("windowDays") or 3650))
    numerator_count = len(numerator)
    denominator_count = len(denominator)
    min_base = int(rule.get("minBaseCount") or 1)
    ratio = (numerator_count / denominator_count) if denominator_count else 0.0
    target_ratio = float(rule.get("minRatio") or 1.0)
    if denominator_count < min_base:
        percent = int(round((denominator_count / max(1, min_base)) * 100))
    else:
        percent = min(100, int(round((ratio / max(target_ratio, 0.01)) * 100)))
    next_action = f"把当前达成率提升到 {int(target_ratio * 100)}%，并至少形成 {min_base} 条有效样本。"
    return float(numerator_count), float(max(denominator_count, min_base)), percent, f"{numerator_count} / {denominator_count}，当前 {int(ratio * 100)}%", [_event_to_evidence(item) for item in (numerator or denominator)[:4]], next_action


def _evaluate_sequence(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(events, event_type=str(rule["eventType"]), window_days=int(rule.get("windowDays") or 3650))
    completed_stage = str(rule.get("completedStage") or "")
    completed = [event for event in matched if str(event.payload.get("stage") or event.payload.get("status") or "") == completed_stage]
    progress = float(len(_unique_events(completed)))
    target = 1.0
    percent = 100 if progress >= target else 0
    next_action = f"继续把事项推进到【{completed_stage}】。"
    return progress, target, percent, f"{int(progress)} / 1", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_composite(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    conditions = list(rule.get("conditions") or [])
    satisfied = 0
    texts: list[str] = []
    evidences: list[BadgeEvidenceRecord] = []
    next_action = str(rule.get("hintTemplate") or "")
    for condition in conditions:
        matched = _events_for_rule(
            events,
            event_type=str(condition.get("eventType") or ""),
            window_days=int(rule.get("windowDays") or 3650),
            filters=condition.get("filters"),
            required_fields=condition.get("requiredFields"),
        )
        target = int(condition.get("targetCount") or 1)
        count = len(matched)
        texts.append(f"{condition.get('label') or condition.get('eventType')}: {count}/{target}")
        evidences.extend(_event_to_evidence(item) for item in matched[:2])
        if count >= target:
            satisfied += 1
        elif not next_action:
            next_action = str(condition.get("hint") or "")
    target_total = float(len(conditions) or 1)
    percent = int(round((satisfied / target_total) * 100))
    if target_total - satisfied == 1:
        next_action = f"再补齐 1 项条件就会点亮【{rule['badgeName']}】"
    elif not next_action:
        next_action = str(rule.get("hintTemplate") or "")
    return float(satisfied), target_total, percent, " / ".join(texts), list({item.id: item for item in evidences}.values())[:4], next_action


def _evaluate_rule(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    rule_type: RuleType = rule["type"]
    if rule_type == "count":
        return _evaluate_count(rule, events)
    if rule_type == "consecutive":
        return _evaluate_consecutive(rule, events)
    if rule_type == "ratio":
        return _evaluate_ratio(rule, events)
    if rule_type == "sequence":
        return _evaluate_sequence(rule, events)
    return _evaluate_composite(rule, events)


def _badge_definitions() -> list[dict[str, Any]]:
    def link(label: str, tab: str) -> dict[str, str]:
        return {"label": label, "tab": tab}

    return [
        # ── 任务推进系 (1-10) ──────────────────────────────────────────
        {"id": "spark_start", "code": "task_progress.spark_start", "name": "开工火花", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 10, "iconMotif": "spark_card", "description": "首次主动新建并推进一条任务线。", "whyItMatters": "第一次自发启动是自驱力的起点。", "systemHowText": "系统会识别用户是否主动创建并推进过至少一条任务。", "hintTemplate": "新建一条任务并推进到下一步。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 365, "eventType": "task.created", "targetCount": 1}},
        {"id": "closer_hand", "code": "task_progress.closer_hand", "name": "收口手", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "converge_box", "description": "把零散事项收成一条清楚的任务。", "whyItMatters": "收口能力是推进力最直接的表现。", "systemHowText": "系统会识别零散事项被合并或归纳为结构化任务。", "hintTemplate": "把散落的待办整理成一条有说明的任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.created", "targetCount": 5}},
        {"id": "one_shot_clear", "code": "task_progress.one_shot_clear", "name": "一次到位", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "check_list", "description": "任务说明写得清楚，减少反复追问。", "whyItMatters": "说清楚减少 80% 的沟通成本。", "systemHowText": "系统会识别任务说明字数和后续追问频率。", "hintTemplate": "创建任务时把目标、步骤和完成标准写清楚。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.description_complete", "targetCount": 5}},
        {"id": "continuous_push", "code": "task_progress.continuous_push", "name": "连续推进", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "steps_forward", "description": "连续多天让同一事项持续往前走。", "whyItMatters": "持续推进比间歇爆发更能把事做完。", "systemHowText": "系统会识别连续多天有任务状态更新。", "hintTemplate": "连续三天更新同一任务的进展。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 3, "windowDays": 30, "eventType": "task.status_updated"}},
        {"id": "breakdown_master", "code": "task_progress.breakdown_master", "name": "拆解高手", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "split_blocks", "description": "把大事拆成可执行的小步。", "whyItMatters": "好的拆解是执行力最直接的表现。", "systemHowText": "系统会识别父任务和可执行子项之间的结构关系。", "hintTemplate": "把大任务拆成可执行小任务，再分责任人。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.created", "targetCount": 5}},
        {"id": "blocker_spotter", "code": "task_progress.blocker_spotter", "name": "卡点识别", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "roadblock_light", "description": "能及时说清楚事情卡在哪里。", "whyItMatters": "说清卡点比埋头硬做更有效。", "systemHowText": "系统会识别任务或复盘中标记的卡点与阻碍。", "hintTemplate": "遇到阻碍时在任务里写清卡点原因。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 3}},
        {"id": "today_zero", "code": "task_progress.today_zero", "name": "今日清零", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "calendar_zero", "description": "当天关键事项当天收口。", "whyItMatters": "日清能力让整体节奏不拖沓。", "systemHowText": "系统会识别当天创建且当天完成的任务数。", "hintTemplate": "今天的关键事项今天收口。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 14, "eventType": "task.done_same_day", "targetCount": 5}},
        {"id": "week_target_hit", "code": "task_progress.week_target_hit", "name": "周目标命中", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 20, "iconMotif": "bullseye_arrow", "description": "一周里把最重要的事项按时推进。", "whyItMatters": "周目标命中率是执行节奏的真实度量。", "systemHowText": "系统会识别有截止日的任务中按时完成的比例。", "hintTemplate": "更新本周重点任务状态，确保按时完成。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "ratio", "windowDays": 14, "numeratorEventType": "task.done_on_time", "denominatorEventType": "task.with_deadline", "minRatio": 0.8, "minBaseCount": 3}},
        {"id": "key_task_guardian", "code": "task_progress.key_task_guardian", "name": "关键任务守护者", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 22, "iconMotif": "shield_card", "description": "把高优任务稳稳盯住不丢。", "whyItMatters": "关键任务不能掉是组织信任的基础。", "systemHowText": "系统会识别高优先级任务是否持续被跟进。", "hintTemplate": "确保高优任务每周至少更新一次进展。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 3, "windowDays": 60, "eventType": "task.status_updated"}},
        {"id": "closed_loop_exec", "code": "task_progress.closed_loop_exec", "name": "闭环执行官", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 25, "iconMotif": "loop_flag", "description": "从开始、推进到交付形成闭环。", "whyItMatters": "闭环是推进力最高形态。", "systemHowText": "系统会识别从创建到完成的完整任务闭环。", "hintTemplate": "完成一条从创建到交付的完整任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.closed_loop", "targetCount": 5}},
        # ── 日历与节奏系 (11-20) ──────────────────────────────────────────
        {"id": "time_arranger", "code": "calendar_rhythm.time_arranger", "name": "时间编排师", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "time_blocks", "description": "能把任务安排进合理时间段。", "whyItMatters": "时间编排是节奏感的第一步。", "systemHowText": "系统会识别任务是否设置了截止日期。", "hintTemplate": "给任务设定合理的截止时间。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.deadline_set", "targetCount": 10}},
        {"id": "focus_guard", "code": "calendar_rhythm.focus_guard", "name": "专注时段守门员", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "door_focus", "description": "为重要工作留出完整专注时间。", "whyItMatters": "深度工作需要不被打断的整块时间。", "systemHowText": "系统会识别是否有集中时段的任务推进记录。", "hintTemplate": "为本周最重要的事留出一段不被打断的时间。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.closed_loop", "targetCount": 4}},
        {"id": "early_preparer", "code": "calendar_rhythm.early_preparer", "name": "提前准备者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "bell_early", "description": "在会议或截止前完成准备。", "whyItMatters": "提前准备让会议效率翻倍。", "systemHowText": "系统会识别会议前是否有任务或文档准备记录。", "hintTemplate": "在会议前准备好所需材料和议程。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.published", "targetCount": 5}},
        {"id": "post_meeting_closer", "code": "calendar_rhythm.post_meeting_closer", "name": "会后收口者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "bubble_basket", "description": "会后能迅速把行动项接住。", "whyItMatters": "会后收口速度决定会议价值转化率。", "systemHowText": "系统会识别会议发布后24小时内是否有关联任务创建。", "hintTemplate": "会后当天把行动项转成任务。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 3}},
        {"id": "rhythm_calibrator", "code": "calendar_rhythm.rhythm_calibrator", "name": "节奏校准者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "dial_clock", "description": "发现任务与时间安排不匹配并纠正。", "whyItMatters": "及时校准比死守计划更智慧。", "systemHowText": "系统会识别截止日调整后是否仍按时完成。", "hintTemplate": "检查本周任务时间安排，调整不合理的排期。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 3}},
        {"id": "schedule_predictor", "code": "calendar_rhythm.schedule_predictor", "name": "预判排期者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "timeline_split", "description": "提前看到时间冲突并调整。", "whyItMatters": "预判能把冲突消灭在发生之前。", "systemHowText": "系统会识别是否在截止日前提前调整过排期。", "hintTemplate": "提前检查下周日程，识别可能的冲突。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 3}},
        {"id": "morning_starter", "code": "calendar_rhythm.morning_starter", "name": "清晨启动器", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "sunrise_card", "description": "早上迅速进入工作状态。", "whyItMatters": "早启动决定一天的节奏感。", "systemHowText": "系统会识别每天第一次任务操作的时间。", "hintTemplate": "每天上午完成第一个任务动作。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 5, "windowDays": 14, "eventType": "task.status_updated"}},
        {"id": "evening_reviewer", "code": "calendar_rhythm.evening_reviewer", "name": "晚间复盘人", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "lamp_notebook", "description": "当天结束前会回看并补判断。", "whyItMatters": "日清复盘让经验不隔夜。", "systemHowText": "系统会识别一天结束时的复盘或状态更新行为。", "hintTemplate": "下班前回看今天的任务，补上判断和备注。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 3, "windowDays": 14, "eventType": "review.submitted"}},
        {"id": "conflict_resolver", "code": "calendar_rhythm.conflict_resolver", "name": "冲突化解师", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "parallel_lines", "description": "把会议、任务、出行等冲突排顺。", "whyItMatters": "化解冲突让并行事务不打架。", "systemHowText": "系统会识别时间冲突后的任务重新排期行为。", "hintTemplate": "遇到时间冲突时及时调整优先级和排期。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 5}},
        {"id": "week_rhythm_director", "code": "calendar_rhythm.week_rhythm_director", "name": "周节奏导演", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 22, "iconMotif": "week_baton", "description": "能把一周安排出起承转合。", "whyItMatters": "周节奏稳定是高效能的底层操作系统。", "systemHowText": "系统会识别连续周的任务完成率和复盘提交。", "hintTemplate": "保持连续四周稳定的工作节奏。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "review.submitted"}},
        # ── 会议与纪要系 (21-30) ──────────────────────────────────────────
        {"id": "meeting_catcher", "code": "meeting_notes.meeting_catcher", "name": "会议捕手", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "hand_card", "description": "能把会里的关键内容及时接住。", "whyItMatters": "接住关键信息是会议价值的起点。", "systemHowText": "系统会识别已发布的会议纪要数量。", "hintTemplate": "会后及时发布会议纪要。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "key_point_distiller", "code": "meeting_notes.key_point_distiller", "name": "要点提炼师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "highlight_lines", "description": "能把一场会收成几条重点。", "whyItMatters": "提炼能力决定信息传递效率。", "systemHowText": "系统会识别纪要中是否有清晰的结论和决议。", "hintTemplate": "纪要里把最关键的三条重点标出来。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 5}},
        {"id": "action_translator", "code": "meeting_notes.action_translator", "name": "行动项翻译官", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "bubble_to_list", "description": "把讨论翻译成可执行事项。", "whyItMatters": "讨论不转行动等于没开会。", "systemHowText": "系统会识别会议中的行动项是否有责任人和截止日。", "hintTemplate": "会后把讨论转成带责任人的行动项。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 3}},
        {"id": "risk_recorder", "code": "meeting_notes.risk_recorder", "name": "风险记录员", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "flag_margin", "description": "能及时记下风险和模糊点。", "whyItMatters": "记录风险是防御性推进的起点。", "systemHowText": "系统会识别会议中标记的风险和待澄清项。", "hintTemplate": "会议中及时记录风险和模糊点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "project.risk_flagged", "targetCount": 5}},
        {"id": "consensus_anchor", "code": "meeting_notes.consensus_anchor", "name": "共识锚定者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "anchor_bubbles", "description": "会议中能抓住已形成的共识。", "whyItMatters": "锚定共识让后续推进有根据。", "systemHowText": "系统会识别纪要中是否明确标注了共识和决议。", "hintTemplate": "纪要里把达成的共识和决议明确写出来。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 8}},
        {"id": "decision_tracker", "code": "meeting_notes.decision_tracker", "name": "决议追踪者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "stamp_card", "description": "不让会里的决定落空。", "whyItMatters": "追踪决议是闭环文化的核心。", "systemHowText": "系统会识别会议决议是否在后续被关联到任务。", "hintTemplate": "检查上次会议的决议是否都已落实。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 5}},
        {"id": "recording_organizer", "code": "meeting_notes.recording_organizer", "name": "录音整理者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "wave_to_text", "description": "把录音快速转成可读内容。", "whyItMatters": "录音转文字让信息不再只存在记忆中。", "systemHowText": "系统会识别会议中是否有附件上传和转写记录。", "hintTemplate": "会后上传录音或整理录音要点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "one_page_noter", "code": "meeting_notes.one_page_noter", "name": "一页纪要师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "page_sections", "description": "能把复杂会议收成一页就看懂。", "whyItMatters": "简洁的纪要传播效率最高。", "systemHowText": "系统会识别纪要结构完整度和阅读友好度。", "hintTemplate": "把下一场会的纪要控制在一页以内。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "meeting.published", "targetCount": 10}},
        {"id": "post_meeting_driver", "code": "meeting_notes.post_meeting_driver", "name": "会后推进官", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "table_path", "description": "会后能持续盯住推进。", "whyItMatters": "会后推进是会议价值兑现的最后一环。", "systemHowText": "系统会识别会议后的行动项是否有持续更新。", "hintTemplate": "会后持续跟进行动项直到完成。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 8}},
        {"id": "meeting_to_task_master", "code": "meeting_notes.meeting_to_task_master", "name": "会议转任务大师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 25, "iconMotif": "card_to_box", "description": "会后事项能一键进系统。", "whyItMatters": "会议到任务的转化率决定组织执行效率。", "systemHowText": "系统会识别会议中关联任务的完整度。", "hintTemplate": "会后把所有行动项转成系统任务。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.closed_loop", "targetCount": 10}},
        # ── 客户理解系 (31-40) ──────────────────────────────────────────
        {"id": "client_speed_reader", "code": "customer_insight.speed_reader", "name": "客户速读者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 12, "iconMotif": "person_lens", "description": "能快速抓住客户是谁、在乎什么。", "whyItMatters": "快速理解客户是有效合作的前提。", "systemHowText": "系统会识别客户相关任务中是否有背景说明。", "hintTemplate": "在客户相关任务中补上客户背景描述。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "client.requirement_clarified", "targetCount": 2}},
        {"id": "background_puzzler", "code": "customer_insight.background_puzzler", "name": "背景拼图师", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 15, "iconMotif": "puzzle_outline", "description": "能把客户背景拼成整体理解。", "whyItMatters": "拼完整背景才能看到全貌。", "systemHowText": "系统会识别客户工作台中背景资料的丰富度。", "hintTemplate": "把客户的组织背景、核心诉求和关键人梳理一遍。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.profile_enriched", "targetCount": 3}},
        {"id": "scene_observer", "code": "customer_insight.scene_observer", "name": "场景洞察员", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 18, "iconMotif": "scene_frame", "description": "能看到客户问题发生在哪个场景。", "whyItMatters": "理解场景比只理解问题更深一层。", "systemHowText": "系统会识别复盘或纪要中是否有场景分析描述。", "hintTemplate": "在下次客户复盘中写清问题发生的具体场景。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 3}},
        {"id": "need_translator", "code": "customer_insight.need_translator", "name": "需求翻译官", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "cloud_to_tag", "description": "能把模糊表达翻成真实需求。", "whyItMatters": "翻译需求是避免做错事的关键能力。", "systemHowText": "系统会识别会议中待澄清问题被消解的记录。", "hintTemplate": "把客户的模糊表达翻译成具体需求条目。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 120, "eventType": "client.requirement_clarified", "targetCount": 5}},
        {"id": "relation_thermometer", "code": "customer_insight.relation_thermometer", "name": "关系温度计", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 18, "iconMotif": "thermometer_hand", "description": "能感知合作关系冷暖变化。", "whyItMatters": "关系温度变化往往是风险的先兆。", "systemHowText": "系统会识别客户相关活动的频率变化。", "hintTemplate": "定期检查客户互动频率，留意关系温度变化。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "crm.followup_completed", "targetCount": 5}},
        {"id": "pain_point_lighter", "code": "customer_insight.pain_point_lighter", "name": "痛点照明者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "spotlight_crack", "description": "能照出客户真正难受的地方。", "whyItMatters": "找到真痛点才能提供真价值。", "systemHowText": "系统会识别复盘中是否有客户痛点分析。", "hintTemplate": "在复盘中明确写出客户最核心的痛点。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "client_dna_keeper", "code": "customer_insight.dna_keeper", "name": "客户DNA守护者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 22, "iconMotif": "helix_card", "description": "能持续维护客户画像与核心判断。", "whyItMatters": "持续维护的客户画像是团队共享资产。", "systemHowText": "系统会识别客户资料的持续更新频率。", "hintTemplate": "每月更新一次核心客户的画像和判断。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 3, "windowDays": 120, "eventType": "client.profile_enriched"}},
        {"id": "stage_judge", "code": "customer_insight.stage_judge", "name": "阶段判断员", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "milestone_steps", "description": "能看出合作到了哪个阶段。", "whyItMatters": "阶段判断决定下一步该做什么。", "systemHowText": "系统会识别商机阶段推进记录。", "hintTemplate": "更新当前客户合作的阶段判断。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "crm.opportunity_stage", "targetCount": 3}},
        {"id": "key_person_spotter", "code": "customer_insight.key_person_spotter", "name": "关键人识别者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 22, "iconMotif": "person_highlight", "description": "能识别谁是真正关键对象。", "whyItMatters": "找对人比做对事更重要。", "systemHowText": "系统会识别客户工作台中关键人的标注记录。", "hintTemplate": "在客户工作台中标注出关键决策人。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.key_person_identified", "targetCount": 3}},
        {"id": "client_mirror", "code": "customer_insight.client_mirror", "name": "客户镜像师", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 25, "iconMotif": "mirror_outline", "description": "能把客户现状映照得清楚。", "whyItMatters": "清晰映照是方案力的前提。", "systemHowText": "系统会识别客户分析报告的完整度和质量。", "hintTemplate": "输出一份完整的客户现状分析。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        # ── 关系与合作系 (41-50) ──────────────────────────────────────────
        {"id": "ice_breaker", "code": "relationship_collab.ice_breaker", "name": "首次破冰者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "ice_warm", "description": "让初次接触自然地开始。", "whyItMatters": "好的开始是成功的一半。", "systemHowText": "系统会识别首次客户或合作方的互动记录。", "hintTemplate": "主动完成一次新客户或新合作方的首次接触。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "crm.lead_followed", "targetCount": 3}},
        {"id": "trust_builder", "code": "relationship_collab.trust_builder", "name": "信任累积者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "stacked_stones", "description": "通过稳定互动积累信任。", "whyItMatters": "信任是长期合作的基石。", "systemHowText": "系统会识别对同一客户的持续跟进记录。", "hintTemplate": "对同一客户保持每月至少一次稳定互动。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 3, "windowDays": 120, "eventType": "crm.followup_completed"}},
        {"id": "no_drop_followup", "code": "relationship_collab.no_drop_followup", "name": "跟进不掉线", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "thread_nodes", "description": "跟进过程中不让合作线断掉。", "whyItMatters": "持续跟进比爆发式沟通更有效。", "systemHowText": "系统会识别客户跟进的连续性。", "hintTemplate": "确保每个活跃客户都有持续的跟进记录。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "crm.followup_completed", "targetCount": 8}},
        {"id": "boundary_clarifier", "code": "relationship_collab.boundary_clarifier", "name": "边界澄清者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "boundary_blocks", "description": "能把合作边界讲清楚。", "whyItMatters": "清晰边界减少后续扯皮。", "systemHowText": "系统会识别合作范围和边界的文档记录。", "hintTemplate": "在合作启动时把边界和范围写清楚。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.requirement_clarified", "targetCount": 3}},
        {"id": "co_creation_inviter", "code": "relationship_collab.co_creation_inviter", "name": "共创邀请者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "dual_pens", "description": "能把对方拉进共同设计。", "whyItMatters": "共创让合作从供需变成伙伴。", "systemHowText": "系统会识别跨角色协作会议或共创工作坊。", "hintTemplate": "邀请客户或合作方参与一次共创讨论。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "collab_closer", "code": "relationship_collab.collab_closer", "name": "合作收束者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "knot_hand", "description": "把泛意向收束成具体合作。", "whyItMatters": "收束是把机会变成现实的关键动作。", "systemHowText": "系统会识别商机从意向推进到合作的记录。", "hintTemplate": "把当前意向推进到具体合作方案。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "crm.opportunity_stage", "targetCount": 2}},
        {"id": "external_interface", "code": "relationship_collab.external_interface", "name": "外部接口人", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "connector_dual", "description": "对外沟通稳定、清楚、有承接。", "whyItMatters": "稳定的外部接口降低合作摩擦。", "systemHowText": "系统会识别外部会议和跟进的稳定频率。", "hintTemplate": "保持外部沟通的稳定节奏。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "crm.followup_completed"}},
        {"id": "network_weaver", "code": "relationship_collab.network_weaver", "name": "网络编织者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "web_nodes", "description": "把零散关系编成更大的网。", "whyItMatters": "网络效应让每段关系都更有价值。", "systemHowText": "系统会识别多客户之间的跨线索联动。", "hintTemplate": "把相关客户或合作方的信息进行交叉引用。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "crm.lead_followed", "targetCount": 10}},
        {"id": "hub_connector", "code": "relationship_collab.hub_connector", "name": "枢纽连接者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 25, "iconMotif": "bridge_platforms", "description": "打通关键枢纽组织或关键人。", "whyItMatters": "枢纽连接能撬动整个网络。", "systemHowText": "系统会识别关键合作节点的建立记录。", "hintTemplate": "识别并连接一个关键枢纽组织或人。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "client.key_person_identified", "targetCount": 5}},
        {"id": "long_term_partner", "code": "relationship_collab.long_term_partner", "name": "长期伙伴建造者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 28, "iconMotif": "dual_rings", "description": "把合作从项目做成长期关系。", "whyItMatters": "长期伙伴是组织最稳定的增长来源。", "systemHowText": "系统会识别同一客户超过6个月的持续合作记录。", "hintTemplate": "维护一段超过半年的持续合作关系。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 6, "windowDays": 365, "eventType": "crm.followup_completed"}},
        # ── 研究与情报系 (51-60) ──────────────────────────────────────────
        {"id": "clue_catcher", "code": "research_intel.clue_catcher", "name": "线索捕手", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "net_sparkle", "description": "能从杂音里抓住有用线索。", "whyItMatters": "有效的线索是判断的原材料。", "systemHowText": "系统会识别情报候选条目的创建记录。", "hintTemplate": "记录一条从外部信息中发现的有用线索。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 90, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "material_checker", "code": "research_intel.material_checker", "name": "资料清点师", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "folder_stack", "description": "能把资料盘清楚不遗漏。", "whyItMatters": "盘清资料是研究的起点。", "systemHowText": "系统会识别附件上传和整理的完整度。", "hintTemplate": "把项目相关资料整理上传到系统。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.attachment_uploaded", "targetCount": 5}},
        {"id": "noise_filter", "code": "research_intel.noise_filter", "name": "信息去噪者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "filter_clean", "description": "能把杂乱信息理干净。", "whyItMatters": "去噪让关键信息更容易被看到。", "systemHowText": "系统会识别复盘或分析中信息提炼的质量。", "hintTemplate": "在下次分析中把噪音信息过滤掉，只留关键点。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "evidence_tagger", "code": "research_intel.evidence_tagger", "name": "证据标注员", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "pin_evidence", "description": "能给观点找到清楚出处。", "whyItMatters": "有证据支撑的判断更可靠。", "systemHowText": "系统会识别复盘中是否有引用来源或附件支撑。", "hintTemplate": "在分析中标注证据来源。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "task.attachment_uploaded", "targetCount": 8}},
        {"id": "case_gold_panner", "code": "research_intel.case_gold_panner", "name": "案例淘金者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "pan_gold", "description": "能从案例中捞出有用模式。", "whyItMatters": "案例模式是经验的结晶。", "systemHowText": "系统会识别经验卡片的沉淀数量和质量。", "hintTemplate": "从一个成功案例中提炼出可复用的模式。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 3}},
        {"id": "trend_sniffer", "code": "research_intel.trend_sniffer", "name": "趋势嗅探者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "radar_waves", "description": "能提前闻到外部变化。", "whyItMatters": "提前嗅到变化就是提前赢得窗口。", "systemHowText": "系统会识别情报和分析输出的频率。", "hintTemplate": "记录一条你观察到的行业趋势变化。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 180, "eventType": "improvement.proposal_submitted", "targetCount": 5}},
        {"id": "industry_puzzler", "code": "research_intel.industry_puzzler", "name": "行业拼图师", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "map_pieces", "description": "把行业现状拼成一张大图。", "whyItMatters": "行业大图是战略判断的基础。", "systemHowText": "系统会识别综合性分析报告的产出。", "hintTemplate": "输出一份行业或领域的综合分析。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 2}},
        {"id": "problem_definer", "code": "research_intel.problem_definer", "name": "问题定义者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "question_frame", "description": "能把模糊困境说成清楚问题。", "whyItMatters": "问题定义清楚了，解法自然浮现。", "systemHowText": "系统会识别复盘或分析中问题定义的清晰度。", "hintTemplate": "把一个模糊的困境重新定义成清晰的问题。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 3}},
        {"id": "source_gatekeeper", "code": "research_intel.source_gatekeeper", "name": "可靠来源守门员", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "door_source", "description": "能分辨什么能信、什么不能信。", "whyItMatters": "来源可靠性决定判断质量。", "systemHowText": "系统会识别引用和来源的标注规范度。", "hintTemplate": "在研究中标注每个关键信息的来源可靠度。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 5}},
        {"id": "intel_to_task", "code": "research_intel.intel_to_task", "name": "情报转任务者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 22, "iconMotif": "news_to_task", "description": "把外部信息转成内部行动。", "whyItMatters": "情报只有转化为行动才有价值。", "systemHowText": "系统会识别改进建议进入任务执行的记录。", "hintTemplate": "把一条外部情报转化成一个具体的内部任务。", "actionLinks": [link("去话题情报", "topics_management"), link("去任务与日程", "tasks")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "情报收集", "eventType": "improvement.proposal_submitted", "targetCount": 3, "hint": "先收集 3 条情报。"}, {"label": "转化执行", "eventType": "improvement.proposal_adopted", "targetCount": 1, "hint": "至少推动 1 条情报进入执行。"}]}},
        # ── 判断与策略系 (61-70) ──────────────────────────────────────────
        {"id": "mainline_spotter", "code": "judgment_strategy.mainline_spotter", "name": "主线辨识者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 15, "iconMotif": "thick_line", "description": "能看出真正该盯的主线。", "whyItMatters": "抓主线是避免无效忙碌的关键。", "systemHowText": "系统会识别复盘中是否有清晰的主线判断。", "hintTemplate": "在周复盘中写出本周最该盯的主线。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "priority_officer", "code": "judgment_strategy.priority_officer", "name": "轻重缓急官", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "stone_stairs", "description": "能把先后顺序排出来。", "whyItMatters": "排对优先级比多做事更重要。", "systemHowText": "系统会识别任务优先级设置和调整记录。", "hintTemplate": "给本周任务重新排一次优先级。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.status_updated", "targetCount": 10}},
        {"id": "variable_watcher", "code": "judgment_strategy.variable_watcher", "name": "变量观察者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "eye_dials", "description": "能留意哪些条件在改变。", "whyItMatters": "变量感知是风险前置的基础。", "systemHowText": "系统会识别复盘或会议中对变量和变化的记录。", "hintTemplate": "在复盘中记录本周发生了哪些关键变量变化。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 90, "eventType": "review.structured_entry", "targetCount": 3}},
        {"id": "risk_predictor", "code": "judgment_strategy.risk_predictor", "name": "风险预判者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "warning_crack", "description": "提前看到可能出问题的地方。", "whyItMatters": "预判风险是最高效的风控手段。", "systemHowText": "系统会识别会议和复盘里标记的风险与预警。", "hintTemplate": "提前标出可能出问题的地方和应对方案。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 5}},
        {"id": "hypothesis_maker", "code": "judgment_strategy.hypothesis_maker", "name": "假设提出者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "bulb_question", "description": "能提出值得验证的判断假设。", "whyItMatters": "好假设加速决策质量。", "systemHowText": "系统会识别复盘中是否有假设和验证记录。", "hintTemplate": "在复盘中提出一个待验证的判断假设。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 3}},
        {"id": "counter_questioner", "code": "judgment_strategy.counter_questioner", "name": "反例质询者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "dialog_reverse", "description": "能反问系统和自己是否想偏了。", "whyItMatters": "自我质疑是深度判断的标志。", "systemHowText": "系统会识别复盘中是否有反思和质疑记录。", "hintTemplate": "在复盘中对自己的判断提出一次反面质询。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 5}},
        {"id": "direction_calibrator", "code": "judgment_strategy.direction_calibrator", "name": "方向校准者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "compass_correct", "description": "能及时把偏航的线拉回主线。", "whyItMatters": "及时校正比死守旧方向更重要。", "systemHowText": "系统会识别项目方向调整和校正的记录。", "hintTemplate": "发现偏离时及时校准方向并记录。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 120, "eventType": "task.deadline_adjusted", "targetCount": 5}},
        {"id": "leverage_finder", "code": "judgment_strategy.leverage_finder", "name": "杠杆点发现者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 22, "iconMotif": "lever_rock", "description": "能发现小投入大回报的位置。", "whyItMatters": "杠杆思维是策略力的核心。", "systemHowText": "系统会识别改进提案中的杠杆性建议。", "hintTemplate": "找到一个小投入大回报的改进点并记录。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "opportunity_amplifier", "code": "judgment_strategy.opportunity_amplifier", "name": "机会放大者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 22, "iconMotif": "lens_seed", "description": "能把好机会看深一步。", "whyItMatters": "放大机会比发现机会更稀缺。", "systemHowText": "系统会识别商机深度推进和方案升级记录。", "hintTemplate": "把一个发现的机会进一步深挖和扩展。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        {"id": "strategy_translator", "code": "judgment_strategy.strategy_translator", "name": "战略翻译官", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员", "管理"], "xp": 25, "iconMotif": "map_to_cards", "description": "把大方向翻成能执行的话。", "whyItMatters": "战略落地的关键是翻译成可执行动作。", "systemHowText": "系统会识别战略目标分解为具体任务的记录。", "hintTemplate": "把一个大方向分解成三个以上可执行的任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.created", "targetCount": 10}},
        # ── 交付与产品化系 (71-80) ──────────────────────────────────────────
        {"id": "one_page_planner", "code": "delivery_product.one_page_planner", "name": "一页方案师", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 15, "iconMotif": "page_structure", "description": "能把复杂事情收成一页讲清楚。", "whyItMatters": "一页方案是方案力的极致表现。", "systemHowText": "系统会识别方案型输出的产出记录。", "hintTemplate": "用一页纸把当前最重要的方案讲清楚。", "actionLinks": [link("去成长手册", "growth_handbook"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        {"id": "template_forger", "code": "delivery_product.template_forger", "name": "模板锻造者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 18, "iconMotif": "mold_cards", "description": "把反复做的事打成模板。", "whyItMatters": "模板是效率杠杆的基础设施。", "systemHowText": "系统会识别方法型成长手册条目。", "hintTemplate": "把一个反复做的事情整理成模板。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 2}},
        {"id": "sop_seed", "code": "delivery_product.sop_seed", "name": "SOP种子手", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 18, "iconMotif": "sprout_flow", "description": "能把流程长成 SOP 雏形。", "whyItMatters": "SOP 是组织可复制性的底层资产。", "systemHowText": "系统会识别 SOP 类手册条目的发布。", "hintTemplate": "把一个流程写成 SOP 发布到系统。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 3}},
        {"id": "toolkit_assembler", "code": "delivery_product.toolkit_assembler", "name": "工具包拼装师", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 20, "iconMotif": "toolbox_docs", "description": "把零散材料组装成工具包。", "whyItMatters": "工具包让团队效率成倍提升。", "systemHowText": "系统会识别多个相关经验卡片或模板的集合。", "hintTemplate": "把相关的模板和经验整理成一个工具包。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.experience_published", "targetCount": 5}},
        {"id": "workshop_director", "code": "delivery_product.workshop_director", "name": "工作坊导演", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 20, "iconMotif": "whiteboard_spot", "description": "能把内容排成有节奏的现场。", "whyItMatters": "好的工作坊让共创效率最大化。", "systemHowText": "系统会识别跨角色会议和协作的组织记录。", "hintTemplate": "组织一次有明确产出的工作坊或研讨会。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "experience_to_product", "code": "delivery_product.experience_to_product", "name": "从经验到产品", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "footprint_box", "description": "把一次经验变成可复用产品。", "whyItMatters": "经验产品化是组织增长的加速器。", "systemHowText": "系统会识别经验卡片被后续复用的记录。", "hintTemplate": "把一次成功经验包装成可复用的产品或方法。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "经验沉淀", "eventType": "knowledge.experience_published", "targetCount": 3, "hint": "先沉淀 3 条经验。"}, {"label": "被复用", "eventType": "knowledge.reused", "targetCount": 3, "hint": "让经验被后续任务复用。"}]}},
        {"id": "reuse_designer", "code": "delivery_product.reuse_designer", "name": "复用设计者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "center_copy", "description": "做出来的东西别人也能用。", "whyItMatters": "可复用是交付物的最高标准。", "systemHowText": "系统会识别知识条目的复用频次。", "hintTemplate": "改进一份已有的产出，让它更容易被复用。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.reused", "targetCount": 5}},
        {"id": "delivery_closer", "code": "delivery_product.delivery_closer", "name": "交付收束官", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "zip_folder", "description": "把交付物收得完整可用。", "whyItMatters": "交付收束质量决定客户体验。", "systemHowText": "系统会识别项目验收和闭环的记录。", "hintTemplate": "把当前交付物整理完整，确认可以交出去。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "project.acceptance_closed", "targetCount": 2}},
        {"id": "version_iterator", "code": "delivery_product.version_iterator", "name": "版本迭代者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "version_up", "description": "能在已有基础上持续升级。", "whyItMatters": "持续迭代比从零开始更高效。", "systemHowText": "系统会识别经验卡片的更新和迭代记录。", "hintTemplate": "更新一份已有的方案或产出到新版本。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.experience_published", "targetCount": 8}},
        {"id": "standard_part_builder", "code": "delivery_product.standard_part_builder", "name": "标准件建造者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 25, "iconMotif": "part_slot", "description": "能把共性问题做成标准件。", "whyItMatters": "标准件是组织能力的模块化基础。", "systemHowText": "系统会识别标准化产出的发布和复用记录。", "hintTemplate": "把一个共性问题的解法做成标准件。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "SOP发布", "eventType": "knowledge.sop_published", "targetCount": 3, "hint": "先发布 3 条标准流程。"}, {"label": "被复用", "eventType": "knowledge.reused", "targetCount": 5, "hint": "让标准件真正被复用。"}]}},
        # ── 协作与管理系 (81-90) ──────────────────────────────────────────
        {"id": "collab_responder", "code": "team_management.collab_responder", "name": "协作响应者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "reply_bubble", "description": "能及时回应别人的协作请求。", "whyItMatters": "快速响应降低协作摩擦。", "systemHowText": "系统会识别任务接收后的响应速度。", "hintTemplate": "收到协作请求后24小时内回应。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.quick_response", "targetCount": 10}},
        {"id": "support_router", "code": "team_management.support_router", "name": "支持请求分流员", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "split_arrows", "description": "能判断该向谁求助。", "whyItMatters": "找对人就是最大的效率杠杆。", "systemHowText": "系统会识别任务指派和分流的记录。", "hintTemplate": "遇到问题时找到最合适的人寻求帮助。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.assigned", "targetCount": 5}},
        {"id": "task_dispatcher", "code": "team_management.task_dispatcher", "name": "任务分配师", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 18, "iconMotif": "card_to_people", "description": "能把事情交给更合适的人。", "whyItMatters": "合适的人做合适的事让效率翻倍。", "systemHowText": "系统会识别任务分配和指派的记录。", "hintTemplate": "把手头的任务分配给最合适的责任人。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.assigned", "targetCount": 10}},
        {"id": "role_coordinator", "code": "team_management.role_coordinator", "name": "角色协调官", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 20, "iconMotif": "gears_people", "description": "能把角色之间的关系理顺。", "whyItMatters": "角色清晰让协作不打架。", "systemHowText": "系统会识别跨角色协作会议和任务分工的记录。", "hintTemplate": "在下次协作中明确每个人的角色和职责。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "overload_warner", "code": "team_management.overload_warner", "name": "过载预警者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 18, "iconMotif": "gauge_red", "description": "能看出谁已经太满。", "whyItMatters": "预警过载是管理者的基本职责。", "systemHowText": "系统会识别团队任务负载的均衡度。", "hintTemplate": "检查团队成员的任务量，预警可能过载的情况。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 3}},
        {"id": "approval_smoother", "code": "team_management.approval_smoother", "name": "审批减摩者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "stamp_smooth", "description": "能减少审批和确认的摩擦。", "whyItMatters": "审批顺滑让组织速度更快。", "systemHowText": "系统会识别流程优化和审批简化的记录。", "hintTemplate": "优化一个审批流程，减少不必要的确认环节。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "improvement.proposal_submitted", "targetCount": 2}},
        {"id": "dept_bridge", "code": "team_management.dept_bridge", "name": "部门桥梁", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "bridge_depts", "description": "能把两个部门搭起来。", "whyItMatters": "跨部门桥梁是组织效率的关键通道。", "systemHowText": "系统会识别跨部门会议和协作的记录。", "hintTemplate": "促成一次跨部门的协作或对齐会议。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "meeting.cross_function", "targetCount": 5}},
        {"id": "feedback_coach", "code": "team_management.feedback_coach", "name": "反馈教练", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "资深员工"], "xp": 22, "iconMotif": "card_up_arrow", "description": "能给出让人用得上的反馈。", "whyItMatters": "有效反馈是团队成长的催化剂。", "systemHowText": "系统会识别复盘中是否有给同事的反馈和建议。", "hintTemplate": "在下次复盘中给一位同事写一条可操作的反馈。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "one_on_one_observer", "code": "team_management.one_on_one_observer", "name": "一对一观察者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理"], "xp": 22, "iconMotif": "chairs_lamp", "description": "能通过一对一发现问题和成长点。", "whyItMatters": "一对一是最深度的管理工具。", "systemHowText": "系统会识别一对一会议和跟进记录。", "hintTemplate": "安排一次一对一谈话，发现团队成员的成长点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "squad_navigator", "code": "team_management.squad_navigator", "name": "小队领航员", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 28, "iconMotif": "flag_people", "description": "能带着一个小队稳步往前。", "whyItMatters": "小队领航是管理力的基础证明。", "systemHowText": "系统会识别团队任务完成率和协作闭环的稳定性。", "hintTemplate": "带领小队连续四周保持稳定的推进节奏。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "review.submitted"}},
        # ── AI与数字化共创系 (91-100) ──────────────────────────────────────────
        {"id": "prompt_bridger", "code": "ai_digital.prompt_bridger", "name": "Prompt架桥者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "bridge_bubble_gear", "description": "会把需求翻成 AI 听得懂的话。", "whyItMatters": "好的 Prompt 是 AI 协作效率的倍增器。", "systemHowText": "系统会识别 AI 功能的使用频率。", "hintTemplate": "尝试用 AI 辅助完成一项工作。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "ai.prompt_used", "targetCount": 5}},
        {"id": "ai_copilot_tester", "code": "ai_digital.copilot_tester", "name": "AI陪做试验员", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "hand_light_path", "description": "敢把 AI 拉进真实工作试跑。", "whyItMatters": "真实场景试跑是 AI 落地的起点。", "systemHowText": "系统会识别 AI 辅助功能的实际调用记录。", "hintTemplate": "在一个真实任务中使用 AI 辅助并记录效果。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "ai.assist_used", "targetCount": 10}},
        {"id": "automation_assembler", "code": "ai_digital.automation_assembler", "name": "自动化拼装师", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "modules_chain", "description": "能把几个步骤串成自动链。", "whyItMatters": "自动化让重复劳动消失。", "systemHowText": "系统会识别模板任务或批量操作的使用记录。", "hintTemplate": "用任务模板或自动化串联一个多步骤流程。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.template_used", "targetCount": 3}},
        {"id": "data_backfiller", "code": "ai_digital.data_backfiller", "name": "数据回填者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "arrow_db_return", "description": "会把结果写回系统形成闭环。", "whyItMatters": "回填数据让系统记忆持续增长。", "systemHowText": "系统会识别任务完成后是否有结果回填记录。", "hintTemplate": "完成任务后把结果和关键数据回填到系统。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.status_updated", "targetCount": 15}},
        {"id": "human_ai_proofer", "code": "ai_digital.human_ai_proofer", "name": "人机协作校对官", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "pen_screen_correct", "description": "能判断 AI 结果哪里要改。", "whyItMatters": "校对能力是 AI 可靠落地的安全网。", "systemHowText": "系统会识别 AI 生成内容被人工修改的记录。", "hintTemplate": "校对一份 AI 生成的内容并标注需要修改的地方。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "ai.result_reviewed", "targetCount": 5}},
        {"id": "digital_flow_translator", "code": "ai_digital.digital_flow_translator", "name": "数字流程翻译官", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "flow_to_ui", "description": "把业务流程翻成系统逻辑。", "whyItMatters": "翻译能力是数字化落地的关键。", "systemHowText": "系统会识别 SOP 和流程文档的数字化记录。", "hintTemplate": "把一个业务流程翻译成系统可执行的步骤。", "actionLinks": [link("去成长手册", "growth_handbook"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 2}},
        {"id": "knowledge_feeder", "code": "ai_digital.knowledge_feeder", "name": "知识库喂养者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "doc_shelf_light", "description": "持续给系统喂真实资料。", "whyItMatters": "喂养质量决定系统智能水平。", "systemHowText": "系统会识别附件上传和知识条目的持续贡献。", "hintTemplate": "上传一份有价值的工作资料到系统。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.attachment_uploaded", "targetCount": 10}},
        {"id": "corpus_gardener", "code": "ai_digital.corpus_gardener", "name": "语料园丁", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "scissors_vine", "description": "会修剪、整理和维护语料。", "whyItMatters": "语料质量决定 AI 输出质量。", "systemHowText": "系统会识别知识库条目的维护和更新频率。", "hintTemplate": "清理和更新知识库中过时的内容。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 10}},
        {"id": "local_co_creator", "code": "ai_digital.local_co_creator", "name": "本地化共创者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 22, "iconMotif": "wrench_module", "description": "会按团队实际场景改工具。", "whyItMatters": "本地化是工具真正落地的关键。", "systemHowText": "系统会识别改进提案和本地化适配的记录。", "hintTemplate": "提出一条让工具更适合团队实际场景的改进建议。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 365, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "interface_future_designer", "code": "ai_digital.interface_future_designer", "name": "界面未来设计师", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 25, "iconMotif": "window_path_stars", "description": "能把工具做成人人敢用的入口。", "whyItMatters": "好的界面让工具触达每一个人。", "systemHowText": "系统会识别改进提案被采纳并落地的记录。", "hintTemplate": "提出一条改善系统使用体验的建议并推动落地。", "actionLinks": [link("去话题情报", "topics_management"), link("去任务与日程", "tasks")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "建议提出", "eventType": "improvement.proposal_submitted", "targetCount": 3, "hint": "先提出 3 条改进建议。"}, {"label": "被采纳", "eventType": "improvement.proposal_adopted", "targetCount": 1, "hint": "至少推动 1 条建议落地。"}]}},
    ]


def _fetch_unlock_map(db: Database, user_id: str) -> dict[str, dict[str, Any]]:
    rows = db.fetchall("SELECT * FROM badge_unlock_records WHERE user_id = ?", (user_id,))
    return {str(row["badge_id"]): dict(row) for row in rows}


def _build_badge_progress(definition: dict[str, Any], events: list[WorkEvent], unlock_map: dict[str, dict[str, Any]]) -> BadgeProgressRecord:
    rule = dict(definition["rule"])
    rule["badgeName"] = definition["name"]
    rule["hintTemplate"] = definition["hintTemplate"]
    progress_value, progress_target, progress_percent, progress_text, evidences, next_action = _evaluate_rule(rule, events)
    unlocked_row = unlock_map.get(definition["id"])
    raw_ratio = (progress_value / progress_target) if progress_target else 0.0
    mastery_level = 1 if unlocked_row and raw_ratio >= 1.5 else 0
    state: BadgeState
    if unlocked_row:
        state = "mastered" if mastery_level > 0 else "lit"
    elif progress_percent <= 0:
        state = "locked"
    elif progress_percent >= 85:
        state = "ready"
    else:
        state = "progress"
    if unlocked_row:
        next_action = f"你已经连续做到这件事，系统已自动点亮【{definition['name']}】"
    linked_contexts = _linked_contexts_from_evidences(evidences)
    missing_signals = _missing_signals_for_badge(rule, evidences, progress_value, progress_target)
    return BadgeProgressRecord(
        id=str(definition["id"]),
        code=str(definition["code"]),
        name=str(definition["name"]),
        categoryId=str(definition["categoryId"]),
        categoryLabel=str(definition["categoryLabel"]),
        abilityKey=str(definition["abilityKey"]),  # type: ignore[arg-type]
        abilityLabel=str(definition["abilityLabel"]),
        roles=list(definition.get("roles") or []),
        xp=int(definition["xp"]),
        iconMotif=str(definition["iconMotif"]),
        description=str(definition["description"]),
        whyItMatters=str(definition["whyItMatters"]),
        systemHowText=str(definition["systemHowText"]),
        state=state,
        progressValue=progress_value,
        progressTarget=progress_target,
        progressPercent=progress_percent,
        progressText=progress_text,
        nextActionText=next_action,
        actionLinks=[BadgeActionLinkRecord(**item) for item in definition.get("actionLinks") or []],
        evidence=evidences,
        linkedContexts=linked_contexts,
        missingSignals=missing_signals,
        unlockedAt=str(unlocked_row["unlocked_at"]) if unlocked_row else None,
        masteryLevel=mastery_level,
        historical=bool(int(unlocked_row["historical"])) if unlocked_row and unlocked_row.get("historical") is not None else False,
    )


def _award_badge_xp(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    badge: BadgeProgressRecord,
    unlocked_at: str,
) -> None:
    dedupe_key = f"badge_unlock:{user_id}:{badge.id}"
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return
    signal_id = _new_id("gse")
    evidence_id = _new_id("gev")
    created_at = unlocked_at or _now_iso()
    reason = f"已自动点亮成长勋章【{badge.name}】"
    db.execute(
        """
        INSERT INTO growth_signal_events(
            id, user_id, user_name, source_type, source_id, review_id, task_id, week_label, raw_text, context_json, dedupe_key, created_at
        ) VALUES(?, ?, ?, 'badge_unlock', ?, NULL, NULL, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            user_id,
            user_name,
            badge.id,
            _week_label(created_at),
            reason,
            to_json({"badgeId": badge.id, "badgeName": badge.name, "categoryId": badge.categoryId}),
            dedupe_key,
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO growth_evidence_records(
            id, signal_id, user_id, user_name, ability_key, evidence_type, level, confidence, reason, review_id, task_id, handbook_entry_id, metadata_json, contribution_tags_json, org_contribution_score, suggested_premium_rate, validation_state, ai_reason, ai_confidence, created_at
        ) VALUES(?, ?, ?, ?, ?, 'improvement', 'l3', 'high', ?, NULL, NULL, NULL, ?, '[]', 0, 0, 'validated', ?, 0, ?)
        """,
        (
            evidence_id,
            signal_id,
            user_id,
            user_name,
            badge.abilityKey,
            reason,
            to_json({"sourceTitle": badge.name}),
            reason,
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO xp_ledger(
            id, user_id, user_name, ability_key, evidence_id, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp, contribution_tags_json, validation_state, org_contribution_score, dedupe_key, week_label, created_at, reversed_at
        ) VALUES(?, ?, ?, ?, ?, 'improvement', ?, ?, 0, 0, ?, '[]', 'validated', 0, ?, ?, ?, NULL)
        """,
        (
            _new_id("xp"),
            user_id,
            user_name,
            badge.abilityKey,
            evidence_id,
            badge.xp,
            badge.xp,
            badge.xp,
            dedupe_key,
            _week_label(created_at),
            created_at,
        ),
    )


def _sync_badge_unlocks(db: Database, *, user_id: str, user_name: str, badges: list[BadgeProgressRecord]) -> None:
    unlock_map = _fetch_unlock_map(db, user_id)
    now_value = _now_iso()
    for badge in badges:
        if badge.id in unlock_map:
            continue
        if badge.progressTarget <= 0 or badge.progressValue < badge.progressTarget:
            continue
        unlocked_at = badge.evidence[0].occurredAt if badge.evidence else now_value
        historical = 1 if _parse_dt(unlocked_at) <= datetime.now() - timedelta(days=30) else 0
        db.execute(
            """
            INSERT INTO badge_unlock_records(
                id, user_id, user_name, badge_id, badge_code, badge_name, category_id, ability_key, xp, evidence_ids_json, unlocked_at, historical, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("bud"),
                user_id,
                user_name,
                badge.id,
                badge.code,
                badge.name,
                badge.categoryId,
                badge.abilityKey,
                badge.xp,
                to_json([item.id for item in badge.evidence]),
                unlocked_at,
                historical,
                now_value,
            ),
        )
        _award_badge_xp(db, user_id=user_id, user_name=user_name, badge=badge, unlocked_at=unlocked_at)


def build_badge_board(db: Database, *, user_id: str, user_name: str, auto_sync: bool = True) -> BadgeBoardResponse:
    events = _collect_work_events(db, user_name=user_name)
    unlock_map = _fetch_unlock_map(db, user_id)
    badges = [_build_badge_progress(definition, events, unlock_map) for definition in _badge_definitions()]
    if auto_sync:
        _sync_badge_unlocks(db, user_id=user_id, user_name=user_name, badges=badges)
        unlock_map = _fetch_unlock_map(db, user_id)
        badges = [_build_badge_progress(definition, events, unlock_map) for definition in _badge_definitions()]

    categories: list[BadgeCategoryRecord] = []
    for category in CATEGORY_DEFINITIONS:
        category_badges = [badge for badge in badges if badge.categoryId == category["id"]]
        categories.append(
            BadgeCategoryRecord(
                id=str(category["id"]),
                label=str(category["label"]),
                abilityKey=str(category["abilityKey"]),  # type: ignore[arg-type]
                abilityLabel=str(category["abilityLabel"]),
                litCount=sum(1 for badge in category_badges if badge.state in {"lit", "mastered"}),
                totalCount=len(category_badges),
                badges=category_badges,
            )
        )

    lit_badges = [badge for badge in badges if badge.state in {"lit", "mastered"}]
    ready_badges = [badge for badge in badges if badge.state == "ready"]
    in_progress_badges = [badge for badge in badges if badge.state in {"progress", "ready"}]
    monthly_new = sum(1 for badge in lit_badges if badge.unlockedAt and _parse_dt(badge.unlockedAt) >= datetime.now() - timedelta(days=30))
    upcoming = sorted(
        [badge for badge in badges if badge.state in {"progress", "ready"}],
        key=lambda item: (-item.progressPercent, item.name),
    )[:3]

    return BadgeBoardResponse(
        overview=BadgeBoardOverviewRecord(
            totalBadges=len(badges),
            litBadges=len(lit_badges),
            readyBadges=len(ready_badges),
            inProgressBadges=len(in_progress_badges),
            monthlyNewBadges=monthly_new,
            totalXp=sum(badge.xp for badge in lit_badges),
            upcomingBadgeIds=[badge.id for badge in upcoming],
        ),
        categories=categories,
        updatedAt=_now_iso(),
    )
~~~

## `backend/app/services/client_profile.py`

- 编码: `utf-8`

~~~python
"""Client profile block generation — Phase 2 of the dual-layer vector architecture.

This module generates high-level "profile blocks" (画像卡片) for a client by:
1. Inventorying the client's existing surrogates and their category distribution
2. Using AI to diagnose which profile dimensions are supported by the data
3. Generating one memory_answer block per recommended dimension
4. Writing each block to disk, DB, and Qdrant
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db import Database, from_json
from app.services.knowledge_base import (
    upsert_master_index_record,
    upsert_surrogate_record,
    write_surrogate_markdown,
)

logger = logging.getLogger(__name__)


def _inventory_client(db: Database, client_id: str) -> dict[str, Any]:
    """Gather statistics about a client's surrogates for AI diagnosis."""
    client_row = db.fetchone("SELECT name, type, stage FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else client_id
    client_type = str(client_row["type"]) if client_row else "未知"
    client_stage = str(client_row["stage"]) if client_row else "未知"

    rows = db.fetchall(
        """
        SELECT title, folder_category, overview_summary, distinct_findings_json, source_type
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )

    category_counter: Counter[str] = Counter()
    titles_by_category: dict[str, list[str]] = {}
    memory_count = 0

    for row in rows:
        source_type = str(row["source_type"] or "document")
        if source_type == "memory_answer":
            memory_count += 1
            continue
        cat = str(row["folder_category"] or "其他资料")
        category_counter[cat] += 1
        titles_by_category.setdefault(cat, []).append(str(row["title"]))

    return {
        "client_name": client_name,
        "client_type": client_type,
        "client_stage": client_stage,
        "category_distribution": dict(category_counter),
        "top_titles_per_category": {cat: titles[:3] for cat, titles in titles_by_category.items()},
        "existing_memory_count": memory_count,
        "all_rows": rows,
    }


def _aggregate_summaries_for_dimension(
    rows: list[dict[str, Any]],
    source_categories: list[str],
) -> str:
    """Collect overview_summary + distinct_findings from surrogates matching the given categories."""
    parts: list[str] = []
    total_chars = 0
    for row in rows:
        if str(row["source_type"] or "document") == "memory_answer":
            continue
        cat = str(row["folder_category"] or "其他资料")
        if cat not in source_categories:
            continue
        title = str(row["title"])
        overview = str(row["overview_summary"] or "")
        findings_raw = from_json(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
        findings = [str(f) for f in findings_raw] if isinstance(findings_raw, list) else []

        part = f"【{title}】\n{overview}"
        if findings:
            part += "\n关键发现：" + "；".join(findings)
        parts.append(part)
        total_chars += len(part)
        if total_chars > 4000:
            break
    return "\n\n".join(parts)


def build_client_profile(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any,
) -> dict[str, Any]:
    """Generate adaptive client profile blocks based on the client's actual data.

    Returns a summary dict with the list of generated blocks.
    """
    inventory = _inventory_client(db, client_id)
    client_name = inventory["client_name"]

    # Step 1: AI diagnosis — which dimensions to generate
    diagnosis = ai_service.diagnose_profile_dimensions(
        client_name=client_name,
        client_type=inventory["client_type"],
        client_stage=inventory["client_stage"],
        category_distribution=inventory["category_distribution"],
        top_titles_per_category=inventory["top_titles_per_category"],
        existing_memory_count=inventory["existing_memory_count"],
    )
    if not diagnosis or not diagnosis.get("recommended_blocks"):
        return {
            "clientId": client_id,
            "clientName": client_name,
            "generated": [],
            "skipped": diagnosis.get("skipped_dimensions", []) if diagnosis else [],
            "error": "AI diagnosis returned no recommendations" if not diagnosis else None,
        }

    recommended = diagnosis["recommended_blocks"]
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    generated: list[dict[str, Any]] = []

    # Step 2: Generate each profile block
    for block_spec in recommended:
        dimension = str(block_spec.get("dimension", ""))
        source_categories = block_spec.get("source_categories", [])
        if not dimension:
            continue

        aggregated = _aggregate_summaries_for_dimension(inventory["all_rows"], source_categories)
        if len(aggregated.strip()) < 50:
            continue

        payload_result = ai_service.generate_profile_block(
            client_name=client_name,
            dimension=dimension,
            aggregated_summaries=aggregated,
        )
        if not payload_result:
            continue

        # Build surrogate payload with defaults for missing fields
        payload: dict[str, Any] = {
            "overview_summary": payload_result.get("overview_summary", ""),
            "retrieval_summary": payload_result.get("retrieval_summary", ""),
            "document_role": payload_result.get("document_role", f"{client_name}客户画像·{dimension}"),
            "core_questions": payload_result.get("core_questions", []),
            "query_hints": payload_result.get("query_hints", [dimension, client_name]),
            "distinct_findings": payload_result.get("distinct_findings", []),
            "entities": payload_result.get("entities", []),
            "time_markers": payload_result.get("time_markers", []),
            "source_links": [],
        }

        doc_uid = f"prof_{hashlib.sha1(f'{client_id}:{dimension}'.encode('utf-8')).hexdigest()[:12]}"
        title = f"{client_name} · {dimension}"

        # Write .md file
        surrogate_md_path = write_surrogate_markdown(
            data_dir,
            client_id=client_id,
            doc_uid=doc_uid,
            folder_category="客户画像",
            title=title,
            source_type="memory_answer",
            source_path=None,
            payload=payload,
        )

        # Write DB surrogate record
        surrogate_id = f"sur_{doc_uid}"
        upsert_surrogate_record(
            db,
            surrogate_id=surrogate_id,
            knowledge_document_id=None,
            client_id=client_id,
            source_type="memory_answer",
            title=title,
            folder_category="客户画像",
            surrogate_md_path=surrogate_md_path,
            payload=payload,
            timestamp=timestamp,
        )

        # Write master index + Qdrant vector
        searchable_text = "\n".join([
            title,
            str(payload.get("retrieval_summary", "")),
            " ".join(str(q) for q in payload.get("core_questions", [])),
            " ".join(str(h) for h in payload.get("query_hints", [])),
            " ".join(str(f) for f in payload.get("distinct_findings", [])),
            "客户画像",
        ])
        entry_id = f"midx_{doc_uid}"
        upsert_master_index_record(
            db,
            data_dir=data_dir,
            entry_id=entry_id,
            client_id=client_id,
            surrogate_id=surrogate_id,
            title=title,
            folder_category="客户画像",
            document_role=str(payload.get("document_role", "")),
            retrieval_summary=str(payload.get("retrieval_summary", "")),
            searchable_text=searchable_text,
            source_path=None,
            surrogate_md_path=surrogate_md_path,
            timestamp=timestamp,
        )

        generated.append({
            "dimension": dimension,
            "surrogateId": surrogate_id,
            "title": title,
            "mdPath": surrogate_md_path,
            "priority": block_spec.get("priority", 99),
        })

    return {
        "clientId": client_id,
        "clientName": client_name,
        "generated": generated,
        "skipped": diagnosis.get("skipped_dimensions", []),
    }


def backfill_all_clients(
    db: Database,
    *,
    data_dir: Path,
    ai_service: Any,
) -> dict[str, Any]:
    """One-time backfill: enrich surrogates + build profile blocks for ALL clients with existing surrogates."""
    from app.services.knowledge_base import batch_enrich_surrogates

    client_rows = db.fetchall("SELECT id, name FROM clients ORDER BY name")
    results: list[dict[str, Any]] = []

    for row in client_rows:
        client_id = str(row["id"])
        client_name = str(row["name"])

        # Count existing surrogates
        surrogate_count = db.fetchone(
            "SELECT COUNT(*) AS cnt FROM knowledge_surrogates WHERE client_id = ? AND source_type = 'document'",
            (client_id,),
        )
        count = int(surrogate_count["cnt"]) if surrogate_count else 0
        if count == 0:
            results.append({"clientId": client_id, "clientName": client_name, "skipped": True, "reason": "no surrogates"})
            continue

        # Step 1: Enrich existing surrogates
        enrich_result = batch_enrich_surrogates(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)

        # Step 2: Build profile blocks
        profile_result = build_client_profile(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)

        results.append({
            "clientId": client_id,
            "clientName": client_name,
            "skipped": False,
            "enriched": enrich_result.get("enriched", 0),
            "profileBlocksGenerated": len(profile_result.get("generated", [])),
        })

    return {"clients": results, "totalProcessed": sum(1 for r in results if not r.get("skipped"))}


def _sync_to_cloud(db: Database, client_id: str) -> dict[str, Any]:
    """Sync a client's surrogates and profile blocks directly into the shared ChromaDB.

    Both desktop and cloud processes use the same ChromaDB directory, so we write
    directly using chromadb without needing to import from cloud_backend.
    """
    import json as _json
    import os

    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else client_id

    org_row = db.fetchone("SELECT organization_id FROM consultation_answers WHERE client_id = ? LIMIT 1", (client_id,))
    organization_id = str(org_row["organization_id"]) if org_row else "default"

    # Use the same ChromaDB path as cloud_backend
    chroma_dir = os.path.join(
        os.path.expanduser("~"),
        "Library", "Application Support", "YiyuThinkTankCloud", "chromadb",
    )
    os.makedirs(chroma_dir, exist_ok=True)

    try:
        import chromadb
    except ImportError:
        logger.warning("chromadb not installed in desktop env, skipping cloud sync")
        return {"clientId": client_id, "clientName": client_name, "synced": 0, "error": "chromadb not installed"}

    try:
        chroma_client = chromadb.PersistentClient(path=chroma_dir)
        collection = chroma_client.get_or_create_collection(
            name="yiyu_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        logger.warning("ChromaDB init failed: %s", exc)
        return {"clientId": client_id, "clientName": client_name, "synced": 0, "error": str(exc)}

    rows = db.fetchall(
        """
        SELECT id, title, folder_category, source_type, overview_summary,
               retrieval_summary, document_role, distinct_findings_json
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )

    synced = 0
    ids_batch: list[str] = []
    docs_batch: list[str] = []
    metas_batch: list[dict[str, str]] = []

    for row in rows:
        title = str(row["title"] or "")
        overview = str(row["overview_summary"] or "")
        retrieval = str(row["retrieval_summary"] or "")
        category = str(row["folder_category"] or "")
        role = str(row["document_role"] or "")
        source_type = str(row["source_type"] or "document")

        content_parts = [f"【{title}】"]
        if role:
            content_parts.append(f"角色：{role}")
        if overview:
            content_parts.append(overview[:1500])
        if retrieval:
            content_parts.append(f"检索摘要：{retrieval}")
        try:
            findings = _json.loads(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
            if isinstance(findings, list) and findings:
                content_parts.append("关键发现：" + "；".join(str(f) for f in findings[:5]))
        except Exception:
            pass

        content = "\n".join(content_parts)
        if len(content.strip()) < 50:
            continue

        doc_type = "profile_block" if source_type == "memory_answer" else "surrogate"
        doc_id_hash = hashlib.sha256(f"{organization_id}:desktop_{doc_type}:{content}".encode()).hexdigest()[:16]
        doc_id = f"{organization_id}-desktop_{doc_type}-{doc_id_hash}"

        ids_batch.append(doc_id)
        docs_batch.append(content)
        metas_batch.append({
            "organization_id": organization_id,
            "source": f"desktop_{doc_type}",
            "client_id": client_id,
            "client_name": client_name,
            "type": doc_type,
            "category": category,
        })

        if len(ids_batch) >= 20:
            try:
                collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
                synced += len(ids_batch)
            except Exception as exc:
                logger.warning("ChromaDB batch upsert failed: %s", exc)
            ids_batch, docs_batch, metas_batch = [], [], []

    if ids_batch:
        try:
            collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
            synced += len(ids_batch)
        except Exception as exc:
            logger.warning("ChromaDB final batch upsert failed: %s", exc)

    return {"clientId": client_id, "clientName": client_name, "synced": synced, "total": len(rows)}
~~~

## `backend/app/services/department_catalog.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentCatalogEntry:
    id: str
    name: str
    color: str
    aliases: tuple[str, ...] = ()


DEPARTMENT_CATALOG: tuple[DepartmentCatalogEntry, ...] = (
    DepartmentCatalogEntry(
        id="dept_consult_strategy",
        name="咨询策略部",
        color="#5B7BFE",
        aliases=("咨询策略", "咨询策略部", "战略设计部", "战略设计", "战略陪伴组"),
    ),
    DepartmentCatalogEntry(
        id="dept_tech_development",
        name="科技发展部",
        color="#F59E0B",
        aliases=("科技发展部", "科技发展"),
    ),
    DepartmentCatalogEntry(
        id="dept_info_data",
        name="信息数据部",
        color="#10B981",
        aliases=("信息数据部", "信息数据", "洞察研究", "洞察研究部"),
    ),
    DepartmentCatalogEntry(
        id="dept_customer_service",
        name="客户服务部",
        color="#14B8A6",
        aliases=("客户服务部", "客户服务", "交付协同", "交付协同部"),
    ),
)

_ALIAS_LOOKUP: dict[str, DepartmentCatalogEntry] = {}
for _entry in DEPARTMENT_CATALOG:
    _ALIAS_LOOKUP[_entry.id.lower()] = _entry
    _ALIAS_LOOKUP[_entry.name.lower()] = _entry
    for _alias in _entry.aliases:
        _ALIAS_LOOKUP[_alias.lower()] = _entry


def list_department_catalog() -> list[DepartmentCatalogEntry]:
    return list(DEPARTMENT_CATALOG)


def get_department_entry(raw_id: str | None = None, raw_name: str | None = None) -> DepartmentCatalogEntry | None:
    for value in (raw_id, raw_name):
        key = (value or "").strip().lower()
        if key and key in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[key]
    return None
~~~

## `backend/app/services/diagnosis_engines.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

import httpx


EngineKey = Literal["bettafish", "mirofish"]
DiagnosisScene = Literal["fundraising", "pr", "project"]
DiagnosisAudienceType = Literal["donor", "media", "public", "key_person", "partner", "beneficiary", "staff"]


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _trim_text(value: str, *, limit: int) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _trim_record_list(records: list[dict[str, str]] | None, *, max_items: int, text_limit: int) -> list[dict[str, str]]:
    trimmed: list[dict[str, str]] = []
    for item in (records or [])[:max_items]:
        next_item = {
            "title": _trim_text(item.get("title", ""), limit=min(text_limit, 80)),
            "summary": _trim_text(item.get("summary", ""), limit=text_limit),
        }
        if next_item["title"] or next_item["summary"]:
            trimmed.append(next_item)
    return trimmed


def _extract_payload(data: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = data.get("data")
    if isinstance(nested, Mapping):
        return nested
    nested = data.get("result")
    if isinstance(nested, Mapping):
        return nested
    return data


@dataclass(frozen=True)
class DiagnosisEngineEndpoint:
    engine_key: EngineKey
    enabled: bool
    base_url: str
    analyze_path: str
    health_path: str
    timeout_seconds: float = 8.0
    connect_timeout_seconds: float = 2.0
    max_payload_chars: int = 12000
    max_response_bytes: int = 256 * 1024
    max_context_items: int = 6


@dataclass(frozen=True)
class DiagnosisEngineRequest:
    scene: DiagnosisScene
    audience_type: DiagnosisAudienceType | str
    content: str
    organization_context: dict[str, Any] | None = None
    dna_summary: dict[str, Any] | None = None
    knowledge_refs: list[dict[str, str]] | None = None
    case_refs: list[dict[str, str]] | None = None
    analysis_options: dict[str, Any] | None = None

    def to_payload(self, *, max_payload_chars: int, max_context_items: int) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "audience_type": self.audience_type,
            "content": _trim_text(self.content, limit=max_payload_chars),
            "organization_context": self.organization_context or {},
            "dna_summary": self.dna_summary or {},
            "knowledge_refs": _trim_record_list(self.knowledge_refs, max_items=max_context_items, text_limit=280),
            "case_refs": _trim_record_list(self.case_refs, max_items=max_context_items, text_limit=280),
            "analysis_options": self.analysis_options or {},
        }


@dataclass(frozen=True)
class DiagnosisEngineHealth:
    engine_key: EngineKey
    enabled: bool
    reachable: bool
    status: Literal["disabled", "healthy", "unreachable", "invalid_response"]
    detail: str
    base_url: str
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BettaFishAnalysis:
    emotion: str | None
    credibility: str | None
    risk_points: list[str]
    misunderstanding_points: list[str]
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotion": self.emotion,
            "credibility": self.credibility,
            "risk_points": self.risk_points,
            "misunderstanding_points": self.misunderstanding_points,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class MiroFishSimulation:
    audiences: list[dict[str, str]]
    scenarios: list[dict[str, str]]
    summary: str | None
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "audiences": self.audiences,
            "scenarios": self.scenarios,
            "summary": self.summary,
            "raw": dict(self.raw),
        }


class DiagnosisEngineError(RuntimeError):
    pass


def load_diagnosis_engine_endpoints() -> dict[EngineKey, DiagnosisEngineEndpoint]:
    return {
        "bettafish": DiagnosisEngineEndpoint(
            engine_key="bettafish",
            enabled=_env_flag("YIYU_BETTAFISH_ENABLED", False),
            base_url=os.getenv("YIYU_BETTAFISH_BASE_URL", "http://127.0.0.1:18101").strip(),
            analyze_path=os.getenv("YIYU_BETTAFISH_ANALYZE_PATH", "/analyze").strip() or "/analyze",
            health_path=os.getenv("YIYU_BETTAFISH_HEALTH_PATH", "/health").strip() or "/health",
            timeout_seconds=float(os.getenv("YIYU_BETTAFISH_TIMEOUT_SECONDS", "8")),
            connect_timeout_seconds=float(os.getenv("YIYU_BETTAFISH_CONNECT_TIMEOUT_SECONDS", "2")),
            max_payload_chars=int(os.getenv("YIYU_BETTAFISH_MAX_PAYLOAD_CHARS", "12000")),
            max_response_bytes=int(os.getenv("YIYU_BETTAFISH_MAX_RESPONSE_BYTES", str(256 * 1024))),
            max_context_items=int(os.getenv("YIYU_BETTAFISH_MAX_CONTEXT_ITEMS", "6")),
        ),
        "mirofish": DiagnosisEngineEndpoint(
            engine_key="mirofish",
            enabled=_env_flag("YIYU_MIROFISH_ENABLED", False),
            base_url=os.getenv("YIYU_MIROFISH_BASE_URL", "http://127.0.0.1:18102").strip(),
            analyze_path=os.getenv("YIYU_MIROFISH_SIMULATE_PATH", "/simulate").strip() or "/simulate",
            health_path=os.getenv("YIYU_MIROFISH_HEALTH_PATH", "/health").strip() or "/health",
            timeout_seconds=float(os.getenv("YIYU_MIROFISH_TIMEOUT_SECONDS", "20")),
            connect_timeout_seconds=float(os.getenv("YIYU_MIROFISH_CONNECT_TIMEOUT_SECONDS", "2")),
            max_payload_chars=int(os.getenv("YIYU_MIROFISH_MAX_PAYLOAD_CHARS", "12000")),
            max_response_bytes=int(os.getenv("YIYU_MIROFISH_MAX_RESPONSE_BYTES", str(512 * 1024))),
            max_context_items=int(os.getenv("YIYU_MIROFISH_MAX_CONTEXT_ITEMS", "6")),
        ),
    }


class _BaseDiagnosisEngineAdapter:
    def __init__(self, endpoint: DiagnosisEngineEndpoint, *, transport: httpx.BaseTransport | None = None):
        self.endpoint = endpoint
        self.transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.endpoint.base_url,
            timeout=httpx.Timeout(self.endpoint.timeout_seconds, connect=self.endpoint.connect_timeout_seconds),
            transport=self.transport,
            headers={"Content-Type": "application/json"},
        )

    def healthcheck(self) -> DiagnosisEngineHealth:
        if not self.endpoint.enabled:
            return DiagnosisEngineHealth(
                engine_key=self.endpoint.engine_key,
                enabled=False,
                reachable=False,
                status="disabled",
                detail="Engine disabled by configuration",
                base_url=self.endpoint.base_url,
                latency_ms=None,
            )

        started_at = time.perf_counter()
        try:
            with self._client() as client:
                response = client.get(self.endpoint.health_path)
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                if response.status_code >= 400:
                    return DiagnosisEngineHealth(
                        engine_key=self.endpoint.engine_key,
                        enabled=True,
                        reachable=False,
                        status="unreachable",
                        detail=f"HTTP {response.status_code}",
                        base_url=self.endpoint.base_url,
                        latency_ms=latency_ms,
                    )
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    payload = None
                if payload is not None and not isinstance(payload, Mapping):
                    return DiagnosisEngineHealth(
                        engine_key=self.endpoint.engine_key,
                        enabled=True,
                        reachable=False,
                        status="invalid_response",
                        detail="Health endpoint returned non-object JSON",
                        base_url=self.endpoint.base_url,
                        latency_ms=latency_ms,
                    )
                detail = "ok"
                if isinstance(payload, Mapping):
                    detail = str(payload.get("detail") or payload.get("status") or "ok")
                return DiagnosisEngineHealth(
                    engine_key=self.endpoint.engine_key,
                    enabled=True,
                    reachable=True,
                    status="healthy",
                    detail=detail,
                    base_url=self.endpoint.base_url,
                    latency_ms=latency_ms,
                )
        except httpx.HTTPError as error:
            return DiagnosisEngineHealth(
                engine_key=self.endpoint.engine_key,
                enabled=True,
                reachable=False,
                status="unreachable",
                detail=str(error),
                base_url=self.endpoint.base_url,
                latency_ms=None,
            )

    def _post(self, payload: DiagnosisEngineRequest) -> Mapping[str, Any]:
        if not self.endpoint.enabled:
            raise DiagnosisEngineError(f"{self.endpoint.engine_key} is disabled by configuration")

        normalized_payload = payload.to_payload(
            max_payload_chars=self.endpoint.max_payload_chars,
            max_context_items=self.endpoint.max_context_items,
        )
        with self._client() as client:
            response = client.post(self.endpoint.analyze_path, json=normalized_payload)
            response.raise_for_status()
            response_bytes = len(response.content or b"")
            if response_bytes > self.endpoint.max_response_bytes:
                raise DiagnosisEngineError(
                    f"{self.endpoint.engine_key} response too large: {response_bytes} bytes > {self.endpoint.max_response_bytes}"
                )
            try:
                data = response.json()
            except json.JSONDecodeError as error:
                raise DiagnosisEngineError(f"{self.endpoint.engine_key} returned invalid JSON") from error
        if not isinstance(data, Mapping):
            raise DiagnosisEngineError(f"{self.endpoint.engine_key} returned non-object JSON")
        return _extract_payload(data)


class BettaFishAdapter(_BaseDiagnosisEngineAdapter):
    def analyze(self, payload: DiagnosisEngineRequest) -> BettaFishAnalysis:
        data = self._post(payload)
        risk_points = [
            _trim_text(str(item), limit=180)
            for item in (data.get("risk_points") or data.get("riskPoints") or [])
            if str(item).strip()
        ][:8]
        misunderstanding_points = [
            _trim_text(str(item), limit=180)
            for item in (data.get("misunderstanding_points") or data.get("misunderstandingPoints") or [])
            if str(item).strip()
        ][:8]
        return BettaFishAnalysis(
            emotion=str(data.get("emotion")).strip() if data.get("emotion") else None,
            credibility=str(data.get("credibility")).strip() if data.get("credibility") else None,
            risk_points=risk_points,
            misunderstanding_points=misunderstanding_points,
            raw=data,
        )


class MiroFishAdapter(_BaseDiagnosisEngineAdapter):
    def simulate(self, payload: DiagnosisEngineRequest) -> MiroFishSimulation:
        data = self._post(payload)
        audiences: list[dict[str, str]] = []
        for item in (data.get("audiences") or []):
            if not isinstance(item, Mapping):
                continue
            audiences.append(
                {
                    "role": _trim_text(str(item.get("role", "")), limit=60),
                    "reaction": _trim_text(str(item.get("reaction", "")), limit=240),
                    "risk_level": _trim_text(str(item.get("risk_level") or item.get("riskLevel") or ""), limit=40),
                }
            )
        scenarios: list[dict[str, str]] = []
        for item in (data.get("scenarios") or []):
            if not isinstance(item, Mapping):
                continue
            scenarios.append(
                {
                    "strategy": _trim_text(str(item.get("strategy", "")), limit=80),
                    "outcome": _trim_text(str(item.get("outcome", "")), limit=240),
                }
            )
        return MiroFishSimulation(
            audiences=audiences[:8],
            scenarios=scenarios[:8],
            summary=_trim_text(str(data.get("summary", "")), limit=400) if data.get("summary") else None,
            raw=data,
        )


def collect_diagnosis_engine_health(*, transport: httpx.BaseTransport | None = None) -> list[DiagnosisEngineHealth]:
    endpoints = load_diagnosis_engine_endpoints()
    return [
        BettaFishAdapter(endpoints["bettafish"], transport=transport).healthcheck(),
        MiroFishAdapter(endpoints["mirofish"], transport=transport).healthcheck(),
    ]
~~~

## `backend/app/services/feishu.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
from urllib.parse import urlencode
from typing import Literal

import httpx


FeishuReceiveIdType = Literal["open_id", "user_id", "email", "chat_id"]

_OPEN_FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuApiError(RuntimeError):
    pass


def _parse_response_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise FeishuApiError("飞书返回了无法解析的响应。") from exc
    if not isinstance(payload, dict):
        raise FeishuApiError("飞书返回了无效的响应结构。")
    return payload


def _raise_for_feishu_error(payload: dict, fallback_message: str) -> None:
    code = payload.get("code", 0)
    if code == 0:
        return
    message = str(payload.get("msg") or payload.get("message") or fallback_message)
    raise FeishuApiError(message)


def fetch_tenant_access_token(
    *,
    app_id: str,
    app_secret: str,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, dict]:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书租户令牌获取失败。")
    token = str(payload.get("tenant_access_token") or "").strip()
    if not token:
        raise FeishuApiError("飞书没有返回 tenant access token。")
    return token, payload


def fetch_app_access_token(
    *,
    app_id: str,
    app_secret: str,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, dict]:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/auth/v3/app_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书应用令牌获取失败。")
    token = str(payload.get("app_access_token") or "").strip()
    if not token:
        raise FeishuApiError("飞书没有返回 app access token。")
    return token, payload


def build_user_authorize_url(
    *,
    app_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    query = urlencode(
        {
            "app_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{_OPEN_FEISHU_BASE_URL}/authen/v1/index?{query}"


def exchange_authorization_code(
    *,
    app_access_token: str,
    app_id: str,
    app_secret: str,
    code: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/authen/v1/access_token",
            headers={"Authorization": f"Bearer {app_access_token}"},
            json={
                "grant_type": "authorization_code",
                "code": code,
                "app_id": app_id,
                "app_secret": app_secret,
            },
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书授权码换取用户令牌失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuApiError("飞书用户令牌响应缺少 data。")
    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise FeishuApiError("飞书没有返回用户 access token。")
    return data


def fetch_user_info(
    *,
    user_access_token: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.get(
            f"{_OPEN_FEISHU_BASE_URL}/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书用户信息获取失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuApiError("飞书用户信息响应缺少 data。")
    return data


def send_text_message(
    *,
    tenant_access_token: str,
    receive_id_type: FeishuReceiveIdType,
    receive_id: str,
    text: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    content = json.dumps({"text": text}, ensure_ascii=False)
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": content,
            },
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书消息发送失败。")
    return payload
~~~

## `backend/app/services/feishu_sync.py`

- 编码: `utf-8`

~~~python
"""
飞书同步引擎 (Feishu Sync Engine)
==================================
基于现有 feishu.py 的认证基础，扩展四大同步模块：
1. 妙记 → 会议纪要
2. 任务双向同步
3. 日历联动
4. 增强消息卡片

所有函数遵循现有 feishu.py 的风格：
- 使用 httpx 同步客户端
- 统一错误处理 (_raise_for_feishu_error)
- tenant_access_token 由调用方传入
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from app.services.feishu import (
    FeishuApiError,
    FeishuReceiveIdType,
    _OPEN_FEISHU_BASE_URL,
    _parse_response_json,
    _raise_for_feishu_error,
)

_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _api_get(token: str, path: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 GET {path} 失败")
    return payload


def _api_post(token: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), json=body or {}, params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 POST {path} 失败")
    return payload


def _api_patch(token: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.patch(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), json=body or {}, params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 PATCH {path} 失败")
    return payload


def _api_delete(token: str, path: str) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.delete(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token))
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 DELETE {path} 失败")
    return payload


# =====================================================================
# 1. 妙记 (Minutes) → 会议纪要
# =====================================================================

def list_minutes(
    *,
    user_access_token: str,
    start_time: int | None = None,
    end_time: int | None = None,
    page_size: int = 20,
    page_token: str = "",
) -> dict:
    """获取用户的妙记列表
    注意: 妙记 API 需要 user_access_token (用户身份)
    """
    params: dict[str, Any] = {"page_size": page_size}
    if start_time:
        params["start_time"] = str(start_time)
    if end_time:
        params["end_time"] = str(end_time)
    if page_token:
        params["page_token"] = page_token
    return _api_get(user_access_token, "/minutes/v1/minutes", params)


def get_minute_detail(
    *,
    user_access_token: str,
    minute_token: str,
) -> dict:
    """获取妙记详情（元信息 + 统计）"""
    return _api_get(user_access_token, f"/minutes/v1/minutes/{minute_token}")


def get_minute_transcript(
    *,
    user_access_token: str,
    minute_token: str,
) -> list[dict]:
    """获取妙记转写全文（按发言段落）"""
    all_paragraphs: list[dict] = []
    page_token = ""
    for _ in range(50):  # 安全上限
        params: dict[str, Any] = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        payload = _api_get(user_access_token, f"/minutes/v1/minutes/{minute_token}/transcripts", params)
        data = payload.get("data", {})
        paragraphs = data.get("paragraphs") or data.get("items") or []
        all_paragraphs.extend(paragraphs)
        page_token = str(data.get("page_token") or "")
        if not data.get("has_more") or not page_token:
            break
    return all_paragraphs


def parse_minute_to_meeting_notes(detail: dict, paragraphs: list[dict]) -> dict:
    """将飞书妙记数据解析为益语会议纪要格式"""
    data = detail.get("data", {}) if "data" in detail else detail
    minute = data.get("minute", data)

    title = str(minute.get("title") or "飞书妙记")
    create_time = int(minute.get("create_time") or 0)
    duration = int(minute.get("duration") or 0)

    # 拼接转写文本
    transcript_lines: list[str] = []
    speakers: set[str] = set()
    for para in paragraphs:
        speaker = str(para.get("speaker", {}).get("user_name", "") if isinstance(para.get("speaker"), dict) else "")
        text = str(para.get("text") or para.get("content") or "")
        if speaker:
            speakers.add(speaker)
            transcript_lines.append(f"【{speaker}】{text}")
        elif text:
            transcript_lines.append(text)

    full_transcript = "\n".join(transcript_lines)

    # 提取 AI 摘要（如果有）
    ai_summary = str(minute.get("ai_summary") or minute.get("summary") or "")
    ai_todo_items = minute.get("todo_items") or minute.get("action_items") or []

    return {
        "title": title,
        "source": "feishu_minutes",
        "transcript": full_transcript,
        "speakers": list(speakers),
        "aiSummary": ai_summary,
        "aiTodoItems": [
            {
                "content": str(item.get("content") or item.get("text") or ""),
                "owner": str(item.get("user_name") or item.get("owner") or ""),
            }
            for item in ai_todo_items
            if isinstance(item, dict)
        ],
        "durationSeconds": duration,
        "feishuCreateTime": datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat() if create_time else None,
        "minuteToken": str(minute.get("token") or ""),
    }


# =====================================================================
# 2. 任务 (Task v2) 双向同步
# =====================================================================

def list_tasks(
    *,
    tenant_access_token: str,
    page_size: int = 50,
    page_token: str = "",
    completed: bool | None = None,
) -> dict:
    """获取任务列表"""
    params: dict[str, Any] = {"page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    if completed is not None:
        params["completed"] = str(completed).lower()
    return _api_get(tenant_access_token, "/task/v2/tasks", params)


def get_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """获取单个任务详情"""
    return _api_get(tenant_access_token, f"/task/v2/tasks/{task_guid}")


def create_task(
    *,
    tenant_access_token: str,
    summary: str,
    description: str = "",
    due_timestamp: int | None = None,
    members: list[dict] | None = None,
    origin_href: str = "",
    origin_title: str = "益语智库",
) -> dict:
    """在飞书创建任务"""
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "origin": {
            "platform_i18n_name": {"zh_cn": origin_title},
        },
    }
    if origin_href:
        body["origin"]["href"] = {"url": origin_href}
    if due_timestamp:
        body["due"] = {"timestamp": str(due_timestamp), "is_all_day": False}
    if members:
        body["members"] = members
    return _api_post(tenant_access_token, "/task/v2/tasks", body)


def update_task(
    *,
    tenant_access_token: str,
    task_guid: str,
    summary: str | None = None,
    description: str | None = None,
    due_timestamp: int | None = None,
    completed_at: str | None = None,
) -> dict:
    """更新飞书任务"""
    body: dict[str, Any] = {}
    update_fields: list[str] = []
    if summary is not None:
        body["summary"] = summary
        update_fields.append("summary")
    if description is not None:
        body["description"] = description
        update_fields.append("description")
    if due_timestamp is not None:
        body["due"] = {"timestamp": str(due_timestamp), "is_all_day": False}
        update_fields.append("due")
    if completed_at is not None:
        body["completed_at"] = completed_at
        update_fields.append("completed_at")
    params = {"update_fields": ",".join(update_fields)} if update_fields else None
    return _api_patch(tenant_access_token, f"/task/v2/tasks/{task_guid}", body, params)


def complete_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """完成飞书任务"""
    return _api_post(tenant_access_token, f"/task/v2/tasks/{task_guid}/complete")


def uncomplete_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """恢复飞书任务为未完成"""
    return _api_post(tenant_access_token, f"/task/v2/tasks/{task_guid}/uncomplete")


# =====================================================================
# 3. 日历 (Calendar v4)
# =====================================================================

def get_primary_calendar(*, tenant_access_token: str) -> dict:
    """获取主日历"""
    return _api_get(tenant_access_token, "/calendar/v4/calendars/primary")


def list_calendar_events(
    *,
    tenant_access_token: str,
    calendar_id: str = "primary",
    start_time: str | None = None,
    end_time: str | None = None,
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取日历事件列表"""
    params: dict[str, Any] = {"page_size": page_size}
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, f"/calendar/v4/calendars/{calendar_id}/events", params)


def create_calendar_event(
    *,
    tenant_access_token: str,
    calendar_id: str = "primary",
    summary: str,
    description: str = "",
    start_time: str = "",
    end_time: str = "",
    attendees: list[dict] | None = None,
) -> dict:
    """创建日历事件"""
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start_time": {"timestamp": start_time} if start_time else {},
        "end_time": {"timestamp": end_time} if end_time else {},
    }
    if attendees:
        body["attendees"] = attendees
    return _api_post(tenant_access_token, f"/calendar/v4/calendars/{calendar_id}/events", body)


def get_freebusy(
    *,
    tenant_access_token: str,
    user_ids: list[str],
    start_time: str,
    end_time: str,
) -> dict:
    """查询用户忙闲状态"""
    body = {
        "time_min": start_time,
        "time_max": end_time,
        "user_ids": user_ids,
    }
    return _api_post(tenant_access_token, "/calendar/v4/freebusy/list", body)


# =====================================================================
# 4. 增强消息 (Rich Messages)
# =====================================================================

def send_interactive_card(
    *,
    tenant_access_token: str,
    receive_id_type: FeishuReceiveIdType,
    receive_id: str,
    card: dict,
) -> dict:
    """发送交互式卡片消息"""
    content = json.dumps(card, ensure_ascii=False)
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers=_auth_headers(tenant_access_token),
            json={
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": content,
            },
        )
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, "飞书卡片消息发送失败")
    return payload


def build_weekly_review_card(
    *,
    week_label: str,
    headline: str,
    highlights: list[str],
    blockers: list[str],
    next_focus: str,
) -> dict:
    """构建周复盘摘要卡片"""
    elements: list[dict] = []

    # 标题
    elements.append({
        "tag": "markdown",
        "content": f"**{headline}**",
    })

    # 亮点
    if highlights:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "**本周亮点**\n" + "\n".join(f"• {h}" for h in highlights[:5]),
        })

    # 卡点
    if blockers:
        elements.append({
            "tag": "markdown",
            "content": "**卡点关注**\n" + "\n".join(f"⚠️ {b}" for b in blockers[:3]),
        })

    # 下周重点
    if next_focus:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": f"**下周重点：** {next_focus}",
        })

    return {
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"📋 {week_label} 周复盘"},
        },
        "elements": elements,
    }


def build_badge_unlock_card(
    *,
    badge_name: str,
    badge_description: str,
    category_name: str,
    xp: int,
    user_name: str,
) -> dict:
    """构建徽章点亮通知卡片"""
    return {
        "header": {
            "template": "turquoise",
            "title": {"tag": "plain_text", "content": f"🏅 {user_name} 点亮了新徽章"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": f"**{badge_name}** ({category_name})\n{badge_description}\n\n获得 **+{xp} XP**",
            },
        ],
    }


def build_task_overdue_card(
    *,
    tasks: list[dict],
    user_name: str,
) -> dict:
    """构建任务逾期提醒卡片"""
    lines = []
    for t in tasks[:5]:
        lines.append(f"• **{t.get('title', '未命名')}** — 截止 {t.get('ddl', '未设定')}")
    return {
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": f"⏰ {user_name}，有 {len(tasks)} 项任务已逾期"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(lines),
            },
            {
                "tag": "markdown",
                "content": "请尽快处理或调整截止日期。",
            },
        ],
    }


# =====================================================================
# 5. 通讯录 (Contact v3) — 组织架构
# =====================================================================

def get_department_children(
    *,
    tenant_access_token: str,
    department_id: str = "0",
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取子部门列表 (department_id=0 为根部门)"""
    params: dict[str, Any] = {"department_id": department_id, "page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, "/contact/v3/departments", params)


def get_department_users(
    *,
    tenant_access_token: str,
    department_id: str,
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取部门直属用户列表"""
    params: dict[str, Any] = {"department_id": department_id, "page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, "/contact/v3/users/find_by_department", params)


# =====================================================================
# 6. 审批 (Approval v4)
# =====================================================================

def get_approval_instance(
    *,
    tenant_access_token: str,
    instance_id: str,
) -> dict:
    """获取审批实例详情"""
    return _api_get(tenant_access_token, f"/approval/v4/instances/{instance_id}")


def list_approval_instances(
    *,
    tenant_access_token: str,
    approval_code: str,
    start_time: int,
    end_time: int,
    page_size: int = 20,
    page_token: str = "",
) -> dict:
    """查询审批实例列表"""
    body: dict[str, Any] = {
        "approval_code": approval_code,
        "start_time": str(start_time),
        "end_time": str(end_time),
        "page_size": page_size,
    }
    if page_token:
        body["page_token"] = page_token
    return _api_post(tenant_access_token, "/approval/v4/instances/query", body)


# =====================================================================
# 辅助：同步状态管理
# =====================================================================

class FeishuSyncState:
    """管理飞书同步的状态和 token 缓存"""

    def __init__(self, db: Any, feishu_secret_store: Any):
        self.db = db
        self.secret_store = feishu_secret_store
        self._cached_token: str | None = None
        self._token_expires_at: float = 0

    def _get_bot_config(self) -> tuple[str, str]:
        """获取飞书 App ID 和 Secret"""
        raw = self.db.get_setting("feishu_bot", "{}")
        import json as _json
        config = _json.loads(raw) if isinstance(raw, str) else {}
        app_id = str(config.get("appId") or "").strip()
        app_secret = ""
        if self.secret_store:
            try:
                app_secret = self.secret_store.get_api_key() or ""
            except Exception:
                pass
        return app_id, app_secret

    def get_tenant_token(self) -> str:
        """获取 tenant_access_token（有2小时缓存）"""
        import time
        if self._cached_token and time.time() < self._token_expires_at:
            return self._cached_token
        app_id, app_secret = self._get_bot_config()
        if not app_id or not app_secret:
            raise FeishuApiError("飞书应用未配置 App ID 或 App Secret")
        from app.services.feishu import fetch_tenant_access_token
        token, payload = fetch_tenant_access_token(app_id=app_id, app_secret=app_secret)
        expire = int(payload.get("expire", 7200))
        self._cached_token = token
        self._token_expires_at = time.time() + expire - 300  # 提前5分钟刷新
        return token

    def get_user_binding(self, user_id: str) -> dict | None:
        """获取用户的飞书绑定信息"""
        import json as _json
        raw = self.db.get_setting(f"feishu_user_binding:{user_id}", "")
        if not raw:
            return None
        try:
            data = _json.loads(raw)
            if data.get("linked"):
                return data
        except Exception:
            pass
        return None

    def get_receiver_config(self) -> tuple[str, str]:
        """获取全局消息接收者配置"""
        import json as _json
        raw = self.db.get_setting("feishu_bot", "{}")
        config = _json.loads(raw) if isinstance(raw, str) else {}
        return str(config.get("receiveIdType") or "open_id"), str(config.get("receiverId") or "")

    def is_configured(self) -> bool:
        """检查飞书是否已配置"""
        app_id, app_secret = self._get_bot_config()
        return bool(app_id and app_secret)
~~~

## `backend/app/services/growth_engine.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    GrowthAbilityProfileRecord,
    GrowthAbilityScoreRecord,
    GrowthAbilityGapRecord,
    GrowthConfidence,
    GrowthContextLinkRecord,
    GrowthContributionTag,
    GrowthEvidenceLevel,
    GrowthEvidenceRecord,
    GrowthEvidenceType,
    GrowthFocusActionRecord,
    GrowthLedgerResponse,
    GrowthOverviewRecord,
    GrowthPendingCaptureRecord,
    GrowthPendingCaptureState,
    GrowthProjectHighlightRecord,
    GrowthRankRecord,
    GrowthSourceCoverageRecord,
    GrowthValidationActionResponse,
    GrowthValidationState,
    HandbookEntryRecord,
    HandbookReuseRecord,
    LearningContentItemRecord,
    LearningRecommendationRecord,
    MeetingDetail,
    StrategicCockpitSnapshotRecord,
    TaskRecord,
    WeeklyReviewRecord,
    WeeklyReviewTaskEntryRecord,
    XpLedgerEntryRecord,
)

ABILITY_ORDER = ("exec", "collab", "analyze", "insight", "risk", "write")

ABILITY_DEFAULTS = {
    "exec": {
        "label": "推进执行",
        "description": "把任务拆清楚、推动起来、按节点闭环。",
        "positive": ["主动推进", "闭环", "行动项清晰", "依赖提前处理"],
        "negative": ["长期卡住", "等别人推动", "没有下一步动作"],
    },
    "collab": {
        "label": "协作沟通",
        "description": "把多人协作中的理解、边界和行动方式说清楚。",
        "positive": ["会议闭环", "跨组对齐", "责任明确", "沟通节奏清晰"],
        "negative": ["边界不清", "返工", "理解偏差"],
    },
    "analyze": {
        "label": "分析判断",
        "description": "能解释原因、提炼规律、做出可执行判断。",
        "positive": ["原因判断", "规律提炼", "结论清楚", "能解释得失"],
        "negative": ["只报结果", "没有因果", "缺少判断"],
    },
    "insight": {
        "label": "客户洞察",
        "description": "识别客户真实顾虑、动机、限制与机会。",
        "positive": ["深层诉求", "真实顾虑", "对象理解", "使用场景"],
        "negative": ["只看表面需求", "忽略顾虑", "洞察停在表层"],
    },
    "risk": {
        "label": "风险识别",
        "description": "提前识别卡点、依赖与风险，而不是事后补救。",
        "positive": ["提前预警", "识别阻碍", "暴露依赖", "降低风险"],
        "negative": ["事后才发现", "风险未说明", "依赖不透明"],
    },
    "write": {
        "label": "写作表达",
        "description": "把经验沉淀成别人能看懂、能复用的表达。",
        "positive": ["方法卡", "模板", "话术", "可复用表达"],
        "negative": ["流水账", "表达空泛", "无法复用"],
    },
}

ABILITY_STAGE_RULES = [
    {"label": "见习", "minXp": 0},
    {"label": "上手", "minXp": 24},
    {"label": "稳态", "minXp": 54},
    {"label": "独立", "minXp": 96},
    {"label": "带动", "minXp": 150},
]

ABILITY_STAGE_SCORE_RULES = [
    {"label": "见习", "minScore": 0},
    {"label": "上手", "minScore": 20},
    {"label": "稳态", "minScore": 40},
    {"label": "独立", "minScore": 60},
    {"label": "带动", "minScore": 80},
]

ABILITY_SCORE_HALF_SATURATION_XP = 96

ABILITY_WEIGHTS = {
    "reflection": {"l1": 5, "l2": 10, "l3": 14},
    "codification": {"l1": 8, "l2": 12, "l3": 16},
    "reuse": {"l1": 12, "l2": 18, "l3": 24},
    "improvement": {"l1": 8, "l2": 12, "l3": 16},
}

PREMIUM_RATE_THRESHOLDS = [
    (85, 0.5),
    (70, 0.4),
    (55, 0.3),
    (40, 0.2),
]

VALIDATION_RATE_CAPS: dict[GrowthValidationState, float] = {
    "candidate": 0.2,
    "observed": 0.3,
    "validated": 0.4,
    "institutionalized": 0.5,
}

VALIDATION_STATE_ORDER: dict[GrowthValidationState, int] = {
    "candidate": 0,
    "observed": 1,
    "validated": 2,
    "institutionalized": 3,
}

RANK_DIVISIONS = ("一阶", "二阶", "三阶", "四阶", "五阶")

RANK_TIERS = [
    {"key": "t01_starter", "name": "启程见习者", "min_xp": 0, "show_division": True},
    {"key": "t02_task_apprentice", "name": "任务学徒", "min_xp": 50, "show_division": True},
    {"key": "t03_rhythm_walker", "name": "节奏行者", "min_xp": 120, "show_division": True},
    {"key": "t04_collab_branch", "name": "协作新枝", "min_xp": 210, "show_division": True},
    {"key": "t05_review_lighter", "name": "复盘点灯人", "min_xp": 320, "show_division": True},
    {"key": "t06_client_walker", "name": "客户随行者", "min_xp": 450, "show_division": True},
    {"key": "t07_thread_weaver", "name": "线索编织者", "min_xp": 600, "show_division": True},
    {"key": "t08_delivery_pusher", "name": "交付推进者", "min_xp": 780, "show_division": True},
    {"key": "t09_judgment_smith", "name": "判断工匠", "min_xp": 980, "show_division": True},
    {"key": "t10_solution_forger", "name": "方案锻造者", "min_xp": 1200, "show_division": True},
    {"key": "t11_system_builder", "name": "系统搭手", "min_xp": 1450, "show_division": True},
    {"key": "t12_dept_pivot", "name": "部门支点", "min_xp": 1730, "show_division": True},
    {"key": "t13_project_navigator", "name": "项目领航者", "min_xp": 2040, "show_division": True},
    {"key": "t14_org_pathfinder", "name": "组织通路者", "min_xp": 2380, "show_division": True},
    {"key": "t15_growth_advisor", "name": "增长参谋", "min_xp": 2750, "show_division": True},
    {"key": "t16_strategic_partner", "name": "战略合伙人", "min_xp": 3150, "show_division": True},
    {"key": "t17_framework_architect", "name": "体系构造者", "min_xp": 3600, "show_division": True},
    {"key": "t18_network_hub", "name": "网络中枢者", "min_xp": 4100, "show_division": True},
    {"key": "t19_interface_bridge", "name": "界面引桥者", "min_xp": 4650, "show_division": True},
    {"key": "t20_symbiosis_designer", "name": "共生设计师", "min_xp": 5250, "show_division": True},
]

CONTRIBUTION_TAG_CONFIG: dict[GrowthContributionTag, dict[str, object]] = {
    "knowledge_asset": {
        "keywords": ["模板", "清单", "方法", "复用", "经验", "手册", "规则", "话术", "框架"],
        "score": 18,
    },
    "critical_resolution": {
        "keywords": ["关键", "解决", "收口", "恢复", "闭环", "卡点", "问题", "阻塞"],
        "score": 18,
    },
    "collaboration_enablement": {
        "keywords": ["协作", "跨组", "对齐", "支持", "帮助", "负责人", "同步", "边界", "会议"],
        "score": 16,
    },
    "risk_alignment": {
        "keywords": ["风险", "依赖", "预警", "时间点", "责任", "边界", "阻碍", "返工"],
        "score": 15,
    },
    "mechanism_building": {
        "keywords": ["机制", "流程", "规范", "制度", "模板", "标准", "规则", "长期"],
        "score": 18,
    },
}

ABILITY_KEYWORDS = {
    "exec": ["推进", "闭环", "行动项", "排期", "拆解", "跟进", "收口", "完成", "延期", "推进完"],
    "collab": ["协作", "沟通", "对齐", "会议", "负责人", "跨组", "边界", "配合", "同步", "话术"],
    "analyze": ["分析", "判断", "原因", "本质", "结论", "规律", "假设", "洞察", "推演", "说明"],
    "insight": ["客户", "用户", "访谈", "需求", "顾虑", "诉求", "对象", "场景", "反馈", "审计客户"],
    "risk": ["风险", "阻碍", "卡点", "依赖", "预警", "问题", "延误", "退回", "不确定", "失败"],
    "write": ["写", "表达", "文档", "模板", "方法", "清单", "沉淀", "复用", "记录", "总结"],
}

DEFAULT_LEARNING_CONTENT = [
    {
        "id": "learn_exec_practice",
        "contentType": "practice_card",
        "abilityKey": "exec",
        "title": "会议闭环四要素",
        "summary": "把会议结论变成负责人、时间点、依赖项和跟进方式。",
        "body": "开会不是为了产纪要，而是为了产下一步动作。每次会议结束前，必须确认负责人、时间点、依赖项和跟进方式。",
        "practiceTask": "下次协作会结束前，用四要素生成 3 条行动项并写进任务系统。",
        "acceptanceCriteria": ["每条行动项都有负责人", "每条行动项都有时间点", "至少 1 条行动项进入任务系统"],
    },
    {
        "id": "learn_collab_correction",
        "contentType": "correction_card",
        "abilityKey": "collab",
        "title": "边界不清先补对齐话术",
        "summary": "跨组任务卡住时，先把目标、交付边界和依赖说清楚。",
        "body": "很多协作问题不是执行差，而是边界没说清。先确认目标、接口、输出格式、依赖人和时间点，再进入推进。",
        "practiceTask": "下次跨组沟通前，先写 3 句澄清话术并带着去对齐。",
        "acceptanceCriteria": ["至少写 3 句澄清问题", "会后形成清晰边界说明"],
    },
    {
        "id": "learn_analyze_method",
        "contentType": "method_card",
        "abilityKey": "analyze",
        "title": "不要只写结果，要写为什么",
        "summary": "每次复盘至少回答：发生了什么、为什么、下次怎么做。",
        "body": "分析判断的关键，不是堆信息，而是把因果链说明白。没有“为什么”的总结，很难沉淀成方法。",
        "practiceTask": "下一次复盘时，把一个结论拆成“现象 / 原因 / 建议”三段。",
        "acceptanceCriteria": ["复盘中出现 1 条明确原因判断", "复盘中出现 1 条下次建议"],
    },
    {
        "id": "learn_insight_practice",
        "contentType": "practice_card",
        "abilityKey": "insight",
        "title": "客户说“快一点”时先追问真实顾虑",
        "summary": "表层需求后面往往是协调成本、风险和不确定性。",
        "body": "客户原话不能直接当作真实需求。先问清目标、约束、担心点和当前阻力，再进入方案。",
        "practiceTask": "下一次客户沟通前，先写出 3 个追问顾虑的问题。",
        "acceptanceCriteria": ["至少准备 3 个追问问题", "复盘里写出客户真实顾虑"],
    },
    {
        "id": "learn_risk_correction",
        "contentType": "correction_card",
        "abilityKey": "risk",
        "title": "风险不要事后补，提前写在周内推进里",
        "summary": "真正有价值的风险识别，是在任务还没彻底卡死前说出来。",
        "body": "风险识别不是复盘时追认失败，而是在推进中提前把依赖、阻碍和不可控点暴露出来。",
        "practiceTask": "给一个本周任务补 1 条提前预警，并明确需要谁支持。",
        "acceptanceCriteria": ["任务备注里出现 1 条风险预警", "说明具体支持对象或依赖项"],
    },
    {
        "id": "learn_write_method",
        "contentType": "method_card",
        "abilityKey": "write",
        "title": "把经验写成可复用的方法卡",
        "summary": "好经验至少要写清结论、适用场景、成立原因和复用方式。",
        "body": "沉淀不是记流水账，而是把别人下次也能拿来用的方法写出来。要尽量做到一句标题能说清价值。",
        "practiceTask": "把本周一条复盘内容整理成一张方法卡，补上适用边界。",
        "acceptanceCriteria": ["标题能独立表达价值", "正文包含适用场景与复用方式"],
    },
]

TASK_CANDIDATE_SOURCE_TYPES = {"task_context_candidate", "task_attachment_candidate"}
MEETING_SOURCE_TYPES = {"meeting_publish"}
STRATEGIC_SOURCE_TYPES = {"strategic_confirm", "strategic_meeting_apply"}


def build_generic_learning_fallback(ability_keys: list[GrowthAbilityKey] | None = None, *, limit: int = 3) -> list[LearningContentItemRecord]:
    ordered_keys = [key for key in dict.fromkeys(ability_keys or []) if key in ABILITY_DEFAULTS]
    prioritized_items: list[dict[str, object]] = []
    if ordered_keys:
        for ability_key in ordered_keys:
            prioritized_items.extend(item for item in DEFAULT_LEARNING_CONTENT if item.get("abilityKey") == ability_key)
    prioritized_items.extend(DEFAULT_LEARNING_CONTENT)

    selected: list[LearningContentItemRecord] = []
    seen_ids: set[str] = set()
    timestamp = datetime.now().isoformat()
    for item in prioritized_items:
        item_id = str(item.get("id") or "").strip()
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        selected.append(
            LearningContentItemRecord(
                id=item_id,
                contentType=str(item.get("contentType") or "method_card"),
                abilityKey=str(item.get("abilityKey") or "exec"),
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
                body=str(item.get("body") or ""),
                practiceTask=str(item.get("practiceTask") or ""),
                acceptanceCriteria=[str(value).strip() for value in item.get("acceptanceCriteria") or [] if str(value).strip()],
                sourceKind="system_rule",
                sourceRefId=None,
                status="active",
                createdAt=timestamp,
                updatedAt=timestamp,
            )
        )
        if len(selected) >= limit:
            break
    return selected


def _as_str(value: object | None) -> str:
    return str(value).strip() if value is not None else ""


def _list_of_strings(value: object | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _safe_context_value(context: dict[str, object], key: str) -> str | None:
    value = context.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_context_list(context: dict[str, object], key: str) -> list[str]:
    return _list_of_strings(context.get(key))


def _json_ready_context(value: object) -> object:
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        return _json_ready_context(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_ready_context(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready_context(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _fact_preview_label(fact: object) -> str:
    if hasattr(fact, "factValue") and _as_str(getattr(fact, "factValue", None)):
        return _as_str(getattr(fact, "factValue", None))
    if hasattr(fact, "title") and _as_str(getattr(fact, "title", None)):
        return _as_str(getattr(fact, "title", None))
    if hasattr(fact, "factKey") and _as_str(getattr(fact, "factKey", None)):
        return _as_str(getattr(fact, "factKey", None))
    return _as_str(fact)


def _context_link_dict(
    object_type: str,
    object_id: str | None,
    label: str | None,
    *,
    subtitle: str = "",
    tab: str = "",
    status_label: str = "",
) -> dict[str, object]:
    normalized_id = _as_str(object_id)
    normalized_label = _as_str(label)
    if not normalized_id or not normalized_label:
        return {}
    return {
        "objectType": object_type,
        "objectId": normalized_id,
        "label": normalized_label,
        "subtitle": subtitle.strip(),
        "tab": tab.strip(),
        "statusLabel": status_label.strip(),
    }


def _context_links_from_context(context: dict[str, object]) -> list[GrowthContextLinkRecord]:
    raw_links = context.get("linkedContexts")
    links: list[GrowthContextLinkRecord] = []
    if isinstance(raw_links, list):
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            object_id = _as_str(item.get("objectId"))
            label = _as_str(item.get("label"))
            if not object_id or not label:
                continue
            links.append(
                GrowthContextLinkRecord(
                    objectType=_as_str(item.get("objectType")) or "unknown",
                    objectId=object_id,
                    label=label,
                    subtitle=_as_str(item.get("subtitle")),
                    tab=_as_str(item.get("tab")),
                    statusLabel=_as_str(item.get("statusLabel")),
                )
            )
    strategic_link = _safe_context_value(context, "strategicLink")
    strategic_client_id = _safe_context_value(context, "clientId")
    if strategic_link and strategic_client_id and not any(link.objectType == "strategic_focus" for link in links):
        links.append(
            GrowthContextLinkRecord(
                objectType="strategic_focus",
                objectId=strategic_client_id,
                label=strategic_link,
                subtitle=_safe_context_value(context, "projectStage") or _safe_context_value(context, "clientName"),
                tab="strategic_accompaniment",
                statusLabel="战略呼应",
            )
        )
    return links


def _normalize_match_text(value: str | None) -> str:
    return re.sub(r"\s+", "", _as_str(value).lower())


def _find_best_matching_strategic_line(
    snapshot: StrategicCockpitSnapshotRecord,
    strategic_link: str | None,
) -> object | None:
    target = _normalize_match_text(strategic_link)
    if not target or not snapshot.strategicLines:
        return None
    scored: list[tuple[int, object]] = []
    for line in snapshot.strategicLines:
        texts = [
            _normalize_match_text(line.title),
            _normalize_match_text(line.summary),
            _normalize_match_text(line.decision),
            _normalize_match_text(line.nextStep),
            _normalize_match_text(line.blocker),
        ]
        score = 0
        for text in texts:
            if not text:
                continue
            if text == target:
                score = max(score, 100)
            elif target in text or text in target:
                score = max(score, 70)
            else:
                overlap = len(set(target) & set(text))
                score = max(score, overlap)
        if score > 0:
            scored.append((score, line))
    if not scored:
        return snapshot.strategicLines[0] if snapshot.strategicLines else None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _week_label_from_timestamp(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return ""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _lookup_client_name(db: Database, client_id: str | None) -> str | None:
    normalized_id = _as_str(client_id)
    if not normalized_id:
        return None
    row = db.fetchone("SELECT name FROM clients WHERE id = ?", (normalized_id,))
    return _as_str(row["name"]) if row and row["name"] else None


def _lookup_event_line_name(db: Database, event_line_id: str | None) -> str | None:
    normalized_id = _as_str(event_line_id)
    if not normalized_id:
        return None
    row = db.fetchone("SELECT name FROM event_lines WHERE id = ?", (normalized_id,))
    return _as_str(row["name"]) if row and row["name"] else None


def _derive_context_summary(
    *,
    client_name: str | None = None,
    event_line_name: str | None = None,
    project_stage: str | None = None,
    business_category: str | None = None,
    strategic_link: str | None = None,
    source_title: str | None = None,
    next_action: str | None = None,
) -> str:
    parts = [part for part in [client_name, event_line_name, project_stage, business_category, strategic_link, source_title] if _as_str(part)]
    summary = " / ".join(parts[:4])
    if next_action and _as_str(next_action):
        return f"{summary} · 下一步：{_as_str(next_action)}" if summary else f"下一步：{_as_str(next_action)}"
    return summary


def _build_source_route(context: dict[str, object]) -> list[str]:
    route = _safe_context_list(context, "sourceRoute")
    if route:
        return route
    items = [
        _safe_context_value(context, "sourceLabel"),
        _safe_context_value(context, "clientName"),
        _safe_context_value(context, "eventLineName"),
        _safe_context_value(context, "projectStage"),
        _safe_context_value(context, "strategicLink"),
    ]
    return [item for item in items if item]


def _build_task_signal_context(db: Database, task: TaskRecord, *, source_type: str) -> dict[str, object]:
    project_context = task.projectContext
    client_name = _as_str(task.clientName) or (project_context.clientName if project_context else "") or _as_str(_lookup_client_name(db, task.clientId))
    event_line_name = _as_str(task.eventLineName) or _as_str(_lookup_event_line_name(db, task.eventLineId))
    project_stage = project_context.stage if project_context else None
    evidence_refs = [_fact_preview_label(fact) for fact in task.linkedFactsPreview[:4] if _fact_preview_label(fact)] if task.linkedFactsPreview else []
    if task.attachments:
        evidence_refs.extend([attachment.title for attachment in task.attachments[:3] if _as_str(attachment.title)])
    evidence_refs = list(dict.fromkeys(evidence_refs))
    missing_reasons: list[str] = []
    if not task.eventLineId:
        missing_reasons.append("缺少事件线归属")
    if not (task.currentBlocker or task.nextAction or task.recentDecision):
        missing_reasons.append("缺少 blocker / 下一步 / 最近判断")
    if (task.evidenceCount or 0) <= 0 and not evidence_refs:
        missing_reasons.append("缺少附件或事实证据")
    missing_reasons.append("还没有在周复盘或成长沉淀里解释这次动作")

    linked_contexts = [
        _context_link_dict("task", task.id, task.title, subtitle=_as_str(task.status), tab="tasks", status_label=_as_str(task.priority)),
        _context_link_dict("client", task.clientId, client_name, tab="client_workspace", subtitle=project_stage or ""),
        _context_link_dict("event_line", task.eventLineId, event_line_name, tab="tasks", subtitle=_as_str(task.businessCategory)),
    ]
    if project_context and project_context.projectModuleId and project_context.projectModuleName:
        linked_contexts.append(
            _context_link_dict(
                "project_module",
                project_context.projectModuleId,
                project_context.projectModuleName,
                tab="tasks",
                subtitle=project_stage or _as_str(task.businessCategory),
            )
        )
    if project_context and project_context.projectFlowId and project_context.projectFlowName:
        linked_contexts.append(
            _context_link_dict(
                "project_flow",
                project_context.projectFlowId,
                project_context.projectFlowName,
                tab="tasks",
                subtitle=_as_str(project_context.projectModuleName),
            )
        )

    context_summary = _derive_context_summary(
        client_name=client_name,
        event_line_name=event_line_name,
        project_stage=project_stage,
        business_category=task.businessCategory,
        source_title=task.title,
        next_action=task.nextAction,
    )
    return {
        "sourceLabel": "任务候选成长",
        "taskId": task.id,
        "taskTitle": task.title,
        "taskStatus": task.status,
        "clientId": task.clientId or (project_context.clientId if project_context else None),
        "clientName": client_name,
        "eventLineId": task.eventLineId,
        "eventLineName": event_line_name,
        "projectModuleId": project_context.projectModuleId if project_context else task.projectModuleId,
        "projectModuleName": project_context.projectModuleName if project_context else task.projectModuleName,
        "projectFlowId": project_context.projectFlowId if project_context else task.projectFlowId,
        "projectFlowName": project_context.projectFlowName if project_context else task.projectFlowName,
        "projectStage": project_stage,
        "businessCategory": task.businessCategory,
        "sourceRoute": ["任务", client_name, event_line_name, project_stage],
        "currentBlocker": task.currentBlocker,
        "nextAction": task.nextAction,
        "recentDecision": task.recentDecision,
        "evidenceRefs": evidence_refs,
        "contextSummary": context_summary,
        "memoryHints": list(task.memoryHints or []),
        "backgroundReadiness": task.backgroundReadiness,
        "missingReasons": missing_reasons,
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": project_context.projectFlowName if project_context and project_context.projectFlowName else "任务推进",
        "sourceTypeLabel": source_type,
    }


def _build_meeting_signal_context(
    db: Database,
    *,
    client_id: str,
    meeting: MeetingDetail,
    event_line_ids: list[str] | None = None,
) -> dict[str, object]:
    client_name = _lookup_client_name(db, client_id) or ""
    event_line_names = [name for name in (_lookup_event_line_name(db, item) for item in (event_line_ids or [])) if name]
    evidence_refs = [item.summary for item in meeting.decisions[:3] if _as_str(item.summary)]
    evidence_refs.extend([item.title for item in meeting.actionItems[:3] if _as_str(item.title)])
    evidence_refs = list(dict.fromkeys(evidence_refs))
    linked_contexts = [
        _context_link_dict("meeting", meeting.id, meeting.title, subtitle=_as_str(meeting.stage), tab="client_workspace"),
        _context_link_dict("client", client_id, client_name, tab="client_workspace"),
    ]
    for event_line_id, event_line_name in zip(event_line_ids or [], event_line_names):
        linked_contexts.append(_context_link_dict("event_line", event_line_id, event_line_name, tab="tasks", subtitle="会议联动"))
    return {
        "sourceLabel": "会议发布",
        "meetingId": meeting.id,
        "meetingTitle": meeting.title,
        "clientId": client_id,
        "clientName": client_name,
        "eventLineId": event_line_ids[0] if event_line_ids else None,
        "eventLineName": event_line_names[0] if event_line_names else None,
        "projectStage": meeting.stage,
        "businessCategory": "meeting",
        "sourceRoute": ["会议", client_name, event_line_names[0] if event_line_names else "", "行动项发布"],
        "evidenceRefs": evidence_refs,
        "contextSummary": _derive_context_summary(
            client_name=client_name,
            event_line_name=event_line_names[0] if event_line_names else None,
            project_stage=_as_str(meeting.stage),
            source_title=meeting.title,
        ),
        "missingReasons": ["还没有在周复盘里解释这次会议动作的成效"],
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": "会议发布",
    }


def _build_strategic_signal_context(
    snapshot: StrategicCockpitSnapshotRecord,
    *,
    source_type: str,
    meeting_id: str | None = None,
) -> dict[str, object]:
    strategic_link = _as_str(snapshot.headline.coreBreakthrough.value) or _as_str(snapshot.headline.mainContradiction.value)
    focus_texts = [_as_str(item.title) for item in snapshot.pendingDecisions[:2] if _as_str(item.title)]
    matched_line = _find_best_matching_strategic_line(snapshot, strategic_link)
    linked_contexts = [
        _context_link_dict("client", snapshot.clientId, snapshot.clientName, tab="client_workspace", subtitle=snapshot.stageLabel),
    ]
    if matched_line:
        linked_contexts.append(
            _context_link_dict(
                "strategic_focus",
                f"{snapshot.clientId}:{matched_line.id}",
                matched_line.title,
                tab="strategic_accompaniment",
                subtitle=matched_line.stage or snapshot.stageLabel,
                status_label="战略呼应",
            )
        )
    if meeting_id:
        linked_contexts.append(_context_link_dict("meeting", meeting_id, "战略周会", tab="client_workspace", subtitle="战略陪伴"))
    return {
        "sourceLabel": "战略陪伴",
        "clientId": snapshot.clientId,
        "clientName": snapshot.clientName,
        "projectStage": snapshot.stageLabel,
        "businessCategory": "strategic",
        "strategicLink": strategic_link,
        "sourceRoute": ["战略陪伴", snapshot.clientName, snapshot.stageLabel, strategic_link],
        "evidenceRefs": focus_texts,
        "contextSummary": _derive_context_summary(
            client_name=snapshot.clientName,
            project_stage=snapshot.stageLabel,
            strategic_link=strategic_link,
        ),
        "missingReasons": ["还没有在任务或复盘里证明本次战略判断被实际执行"],
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": "战略判断确认" if source_type == "strategic_confirm" else "战略周会应用",
        "strategicLineId": matched_line.id if matched_line else None,
        "strategicLineTitle": matched_line.title if matched_line else strategic_link,
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_method_like(text: str) -> bool:
    return bool(re.search(r"(模板|方法|清单|话术|框架|适用|复用|以后|下次|边界)", text))


def _contains_reasoning(text: str) -> bool:
    return bool(re.search(r"(因为|所以|导致|说明|本质|原因|判断|结论|规律|为什么)", text))


def _derive_level(text: str, *, source_type: str) -> GrowthEvidenceLevel:
    normalized = _normalize_text(text)
    if source_type == "handbook_entry" or _is_method_like(normalized):
        return "l3"
    if len(normalized) >= 40 or _contains_reasoning(normalized):
        return "l2"
    return "l1"


def _ability_stage(total_xp: int) -> tuple[str, str]:
    score = _current_score(total_xp)
    stage = ABILITY_STAGE_SCORE_RULES[0]["label"]
    next_stage = ABILITY_STAGE_SCORE_RULES[-1]["label"]
    for index, rule in enumerate(ABILITY_STAGE_SCORE_RULES):
        if score >= int(rule["minScore"]):
            stage = str(rule["label"])
            next_stage = str(ABILITY_STAGE_SCORE_RULES[min(index + 1, len(ABILITY_STAGE_SCORE_RULES) - 1)]["label"])
    return stage, next_stage


def _current_score(total_xp: int) -> int:
    if total_xp <= 0:
        return 8
    # Use a saturating curve instead of a hard linear cap so mature abilities do not all
    # collapse to 100 once cumulative XP crosses an early milestone.
    normalized = (total_xp / (total_xp + ABILITY_SCORE_HALF_SATURATION_XP)) * 100
    return max(8, min(100, int(round(normalized))))


def _score_delta(evidence_type: GrowthEvidenceType, level: GrowthEvidenceLevel, confidence: GrowthConfidence) -> int:
    base = ABILITY_WEIGHTS[evidence_type][level]
    if confidence == "high":
        return base + 2
    if confidence == "low":
        return max(3, base - 2)
    return base


def _infer_contribution_tags(text: str, *, source_type: str, ability_key: str) -> list[GrowthContributionTag]:
    normalized = _normalize_text(text)
    matched: list[GrowthContributionTag] = []
    for tag, config in CONTRIBUTION_TAG_CONFIG.items():
        keywords = config["keywords"]
        if any(keyword in normalized for keyword in keywords):
            matched.append(tag)
    if source_type == "handbook_entry" and "knowledge_asset" not in matched:
        matched.append("knowledge_asset")
    if source_type == "handbook_entry" and _is_method_like(normalized) and "mechanism_building" not in matched:
        matched.append("mechanism_building")
    if ability_key == "collab" and "collaboration_enablement" not in matched:
        matched.append("collaboration_enablement")
    if ability_key == "risk" and "risk_alignment" not in matched:
        matched.append("risk_alignment")
    if ability_key == "write" and "knowledge_asset" not in matched:
        matched.append("knowledge_asset")
    return matched


def _max_validation_state(*states: GrowthValidationState) -> GrowthValidationState:
    return max(states, key=lambda item: VALIDATION_STATE_ORDER[item])


def _build_rank_record(total_xp: int) -> GrowthRankRecord:
    current_index = 0
    for index, tier in enumerate(RANK_TIERS):
        if total_xp >= int(tier["min_xp"]):
            current_index = index
    current_tier = RANK_TIERS[current_index]
    next_tier = RANK_TIERS[current_index + 1] if current_index + 1 < len(RANK_TIERS) else None
    current_min_xp = int(current_tier["min_xp"])
    tier_span = (int(next_tier["min_xp"]) - current_min_xp) if next_tier else 600
    progress = 1.0 if not next_tier else max(0.0, min(1.0, (total_xp - current_min_xp) / max(1, tier_span)))
    division: str | None = None
    if bool(current_tier["show_division"]):
        bucket = min(len(RANK_DIVISIONS) - 1, int(progress * len(RANK_DIVISIONS)))
        division = RANK_DIVISIONS[max(0, bucket)]
    full_label = f"{current_tier['name']}\u00b7{division}" if division else str(current_tier["name"])
    xp_to_next = max(0, int(next_tier["min_xp"]) - total_xp) if next_tier else 0
    return GrowthRankRecord(
        key=str(current_tier["key"]),
        name=str(current_tier["name"]),
        division=division,
        fullLabel=full_label,
        progress=progress,
        nextName=str(next_tier["name"]) if next_tier else None,
        xpToNext=xp_to_next,
    )


def _infer_validation_state(
    *,
    source_type: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    contribution_tags: list[GrowthContributionTag],
    text: str,
) -> GrowthValidationState:
    normalized = _normalize_text(text)
    if evidence_type == "reuse":
        return "institutionalized" if any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")) else "validated"
    if evidence_type == "improvement":
        return "validated"
    if source_type == "handbook_entry":
        return "observed"
    if level == "l3" and any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")):
        return "observed"
    if any(keyword in normalized for keyword in ("被复用", "标准", "统一", "大家", "团队", "跨组")):
        return "observed"
    return "candidate"


def _score_org_contribution(
    text: str,
    *,
    source_type: str,
    ability_key: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    confidence: GrowthConfidence,
    contribution_tags: list[GrowthContributionTag],
    validation_state: GrowthValidationState,
) -> tuple[int, float]:
    normalized = _normalize_text(text)
    leverage = 0
    if source_type == "handbook_entry":
        leverage += 8
    if any(tag in contribution_tags for tag in ("critical_resolution", "mechanism_building")):
        leverage += 10
    if any(keyword in normalized for keyword in ("团队", "组织", "跨组", "大家")):
        leverage += 7
    leverage = min(25, leverage)

    reusability = 0
    if _is_method_like(normalized):
        reusability += 8
    if any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")):
        reusability += 8
    if any(keyword in normalized for keyword in ("复用", "模板", "清单", "以后", "下次", "适用")):
        reusability += 6
    reusability = min(20, reusability)

    collaboration_value = 0
    if ability_key == "collab":
        collaboration_value += 5
    if any(tag == "collaboration_enablement" for tag in contribution_tags):
        collaboration_value += 8
    if any(keyword in normalized for keyword in ("支持", "帮助", "负责人", "时间点", "边界", "会议", "同步")):
        collaboration_value += 7
    collaboration_value = min(20, collaboration_value)

    risk_reduction = 0
    if ability_key == "risk":
        risk_reduction += 4
    if any(tag == "risk_alignment" for tag in contribution_tags):
        risk_reduction += 6
    if any(keyword in normalized for keyword in ("风险", "预警", "依赖", "返工", "阻碍", "卡点")):
        risk_reduction += 5
    risk_reduction = min(15, risk_reduction)

    mechanism_value = 0
    if any(tag == "mechanism_building" for tag in contribution_tags):
        mechanism_value += 6
    if source_type == "handbook_entry":
        mechanism_value += 2
    if any(keyword in normalized for keyword in ("规则", "流程", "规范", "机制", "模板")):
        mechanism_value += 4
    mechanism_value = min(10, mechanism_value)

    validation_strength = 0
    if validation_state == "observed":
        validation_strength = 4
    elif validation_state == "validated":
        validation_strength = 7
    elif validation_state == "institutionalized":
        validation_strength = 10
    if evidence_type in {"reuse", "improvement"}:
        validation_strength = max(validation_strength, 7)
    if level == "l3":
        validation_strength = min(10, validation_strength + 1)
    if confidence == "high":
        validation_strength = min(10, validation_strength + 1)

    score = min(100, leverage + reusability + collaboration_value + risk_reduction + mechanism_value + validation_strength)
    premium_rate = 0.0
    for threshold, rate in PREMIUM_RATE_THRESHOLDS:
        if score >= threshold:
            premium_rate = rate
            break
    premium_rate = min(premium_rate, VALIDATION_RATE_CAPS[validation_state])
    return score, premium_rate


def _build_profile_record(ability_key: str, timestamp: str) -> GrowthAbilityProfileRecord:
    config = ABILITY_DEFAULTS[ability_key]
    return GrowthAbilityProfileRecord(
        id=f"gap_{ability_key}",
        abilityKey=ability_key,  # type: ignore[arg-type]
        label=str(config["label"]),
        description=str(config["description"]),
        stageRules=list(ABILITY_STAGE_RULES),
        positiveSignals=list(config["positive"]),
        negativeSignals=list(config["negative"]),
        weights={"xp": ABILITY_WEIGHTS},
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def ensure_growth_catalog(db: Database, timestamp: str | None = None) -> None:
    now_value = timestamp or _now_iso()
    for ability_key in ABILITY_ORDER:
        profile = _build_profile_record(ability_key, now_value)
        db.execute(
            """
            INSERT OR IGNORE INTO growth_ability_profiles(
                id, ability_key, label, description, stage_rules_json, positive_signals_json, negative_signals_json, weights_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id,
                profile.abilityKey,
                profile.label,
                profile.description,
                to_json(profile.stageRules),
                to_json(profile.positiveSignals),
                to_json(profile.negativeSignals),
                to_json(profile.weights),
                profile.createdAt,
                profile.updatedAt,
            ),
        )
    for item in DEFAULT_LEARNING_CONTENT:
        db.execute(
            """
            INSERT OR IGNORE INTO learning_content_items(
                id, content_type, ability_key, title, summary, body, practice_task, acceptance_criteria_json, source_kind, source_ref_id, status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'system_rule', NULL, 'active', ?, ?)
            """,
            (
                item["id"],
                item["contentType"],
                item["abilityKey"],
                item["title"],
                item["summary"],
                item["body"],
                item["practiceTask"],
                to_json(item["acceptanceCriteria"]),
                now_value,
                now_value,
            ),
        )


def _fetch_profile_map(db: Database) -> dict[str, GrowthAbilityProfileRecord]:
    ensure_growth_catalog(db)
    rows = db.fetchall("SELECT * FROM growth_ability_profiles ORDER BY rowid ASC")
    profile_map: dict[str, GrowthAbilityProfileRecord] = {}
    for row in rows:
        profile = GrowthAbilityProfileRecord(
            id=str(row["id"]),
            abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
            label=str(row["label"]),
            description=str(row["description"] or ""),
            stageRules=from_json(row["stage_rules_json"], []),  # type: ignore[arg-type]
            positiveSignals=from_json(row["positive_signals_json"], []),  # type: ignore[arg-type]
            negativeSignals=from_json(row["negative_signals_json"], []),  # type: ignore[arg-type]
            weights=from_json(row["weights_json"], {}),  # type: ignore[arg-type]
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )
        profile_map[str(row["ability_key"])] = profile
    return profile_map


def _keyword_hits(text: str) -> dict[str, int]:
    normalized = _normalize_text(text)
    scores = defaultdict(int)
    for ability_key, keywords in ABILITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword and keyword in normalized:
                scores[ability_key] += 1
    return scores


def _infer_general_hits(
    text: str,
    *,
    source_type: str,
    preferred: list[str] | None = None,
) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    scores = _keyword_hits(normalized)
    for ability_key in preferred or []:
        scores[ability_key] += 2
    if source_type == "handbook_entry":
        scores["write"] += 3
    if _is_method_like(normalized):
        scores["write"] += 2

    ordered = sorted(scores.items(), key=lambda item: (-item[1], ABILITY_ORDER.index(item[0]) if item[0] in ABILITY_ORDER else 99))
    if not ordered and len(normalized) >= 24:
        ordered = [("analyze", 1)]

    level = _derive_level(normalized, source_type=source_type)
    results: list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]] = []
    for ability_key, score in ordered[:3]:
        if score <= 0:
            continue
        confidence: GrowthConfidence = "high" if score >= 3 else "medium" if score == 2 else "low"
        matched_keywords = [keyword for keyword in ABILITY_KEYWORDS.get(ability_key, []) if keyword in normalized][:3]
        reason = "命中了成长信号"
        if matched_keywords:
            reason = f"提到了{'、'.join(matched_keywords)}"
        results.append((ability_key, level, confidence, reason))
    return results


def infer_review_hits(entry: WeeklyReviewTaskEntryRecord) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    structured = entry.structuredNote
    preferred: list[str] = []
    if structured.reflection.strip() or structured.successExperience.strip() or structured.progress.strip() or entry.taskSnapshot.status == "done":
        preferred.append("exec")
    if structured.reflection.strip() or structured.successReason.strip() or structured.failureInsight.strip():
        preferred.append("analyze")
    if structured.lightweightTag.strip() or structured.blockerReason.strip() or structured.supportNeeded.strip():
        preferred.extend(["risk", "collab"])
    joined_text = " ".join(
        [
            entry.taskSnapshot.title,
            entry.note,
            structured.reflection,
            structured.lightweightTag,
            structured.progress,
            structured.successReason,
            structured.successExperience,
            structured.blockerReason,
            structured.failureInsight,
            structured.supportNeeded,
            structured.nextAction,
            " ".join(tag.name for tag in entry.taskSnapshot.tags),
        ]
    )
    hits = _infer_general_hits(joined_text, source_type="weekly_review_task_entry", preferred=preferred)
    unique: list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]] = []
    seen: set[str] = set()
    for hit in hits:
        if hit[0] in seen:
            continue
        seen.add(hit[0])
        unique.append(hit)
    return unique


def infer_handbook_hits(entry: HandbookEntryRecord) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    text = " ".join([entry.title, entry.summary, " ".join(entry.tags), entry.sourceType])
    preferred = ["write"]
    if entry.sourceType == "meeting":
        preferred.append("collab")
    if entry.sourceType == "task":
        preferred.append("exec")
    if entry.sourceType == "analysis":
        preferred.append("analyze")
    hits = _infer_general_hits(text, source_type="handbook_entry", preferred=preferred)
    if not any(item[0] == "write" for item in hits):
        hits.insert(0, ("write", "l3", "high", "已将经验整理成正式成长手册条目"))
    return hits[:3]


def _upsert_signal(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    source_type: str,
    source_id: str,
    review_id: str | None,
    task_id: str | None,
    week_label: str,
    raw_text: str,
    context: dict[str, object],
    dedupe_key: str,
    created_at: str,
) -> str:
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        signal_id = str(existing["id"])
        db.execute(
            """
            UPDATE growth_signal_events
            SET user_id = ?, user_name = ?, source_type = ?, source_id = ?, review_id = ?, task_id = ?, week_label = ?, raw_text = ?, context_json = ?, created_at = ?
            WHERE id = ?
            """,
            (
                user_id,
                user_name,
                source_type,
                source_id,
                review_id,
                task_id,
                week_label,
                raw_text,
                to_json(_json_ready_context(context)),
                created_at,
                signal_id,
            ),
        )
        return signal_id
    return _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=source_id,
        review_id=review_id,
        task_id=task_id,
        week_label=week_label,
        raw_text=raw_text,
        context=context,
        dedupe_key=dedupe_key,
        created_at=created_at,
    )


def ingest_task_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    task: TaskRecord,
    source_type: str = "task_context_candidate",
    created_at: str | None = None,
    ai_service: object | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_task_signal_context(db, task, source_type=source_type)
    raw_text = _normalize_text(
        " ".join(
            [
                task.title,
                task.desc,
                _as_str(task.currentBlocker),
                _as_str(task.nextAction),
                _as_str(task.recentDecision),
                _as_str(context.get("contextSummary")),
                " ".join(_safe_context_list(context, "evidenceRefs")),
                " ".join(_safe_context_list(context, "memoryHints")),
            ]
        )
    )
    meaningful = bool(task.eventLineId or task.projectContext or task.clientId or task.currentBlocker or task.nextAction or task.recentDecision or (task.evidenceCount or 0) > 0 or task.attachments)
    if not meaningful or not raw_text:
        return

    # ── AI insight quote distillation ──────────────────────────
    if ai_service is not None:
        try:
            result = ai_service.distill_growth_insight_quote(
                task_title=task.title,
                task_desc=task.desc or "",
                client_name=_as_str(context.get("clientName")) or "",
                event_line_name=_as_str(context.get("eventLineName")) or "",
                blocker=_as_str(task.currentBlocker) or "",
                next_action=_as_str(task.nextAction) or "",
                recent_decision=_as_str(task.recentDecision) or "",
                context_summary=_as_str(context.get("contextSummary")) or "",
                evidence_refs=_safe_context_list(context, "evidenceRefs"),
            )
            if result.get("quote"):
                context["insightQuote"] = result["quote"]
            if result.get("sourceLabel"):
                context["insightSourceLabel"] = result["sourceLabel"]
        except Exception:
            pass  # Non-critical: fall back to raw title/summary

    _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=task.id,
        review_id=None,
        task_id=task.id,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"task-candidate:{task.id}",
        created_at=timestamp,
    )


def ingest_meeting_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    client_id: str,
    meeting: MeetingDetail,
    event_line_ids: list[str] | None = None,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_meeting_signal_context(db, client_id=client_id, meeting=meeting, event_line_ids=event_line_ids)
    raw_text = _normalize_text(
        " ".join(
            [
                meeting.title,
                meeting.notes,
                meeting.transcriptText[:280],
                " ".join(item.summary for item in meeting.decisions[:3]),
                " ".join(item.title for item in meeting.actionItems[:3]),
                " ".join(item.summary for item in meeting.risks[:2]),
            ]
        )
    )
    if not raw_text:
        return
    signal_id = _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="meeting_publish",
        source_id=meeting.id,
        review_id=None,
        task_id=None,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"meeting-publish:{meeting.id}",
        created_at=timestamp,
    )
    preferred = ["collab", "risk", "exec", "write"]
    if client_id:
        preferred.append("insight")
    for ability_key, level, confidence, reason in _infer_general_hits(raw_text, source_type="meeting_publish", preferred=preferred):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reflection",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=None,
            source_title=meeting.title,
            week_label=_week_label_from_timestamp(timestamp),
            source_type="meeting_publish",
            raw_text=raw_text,
            context=context,
            created_at=timestamp,
        )


def ingest_strategic_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    snapshot: StrategicCockpitSnapshotRecord,
    source_type: str,
    source_id: str,
    meeting_id: str | None = None,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_strategic_signal_context(snapshot, source_type=source_type, meeting_id=meeting_id)
    raw_text = _normalize_text(
        " ".join(
            [
                snapshot.headline.weekSummary.value,
                snapshot.headline.mainContradiction.value,
                snapshot.headline.coreBreakthrough.value,
                snapshot.stageLabel,
                " ".join(item.title for item in snapshot.pendingDecisions[:3] if _as_str(item.title)),
                " ".join(item.title for item in snapshot.pendingMaterials[:3] if _as_str(item.title)),
                " ".join(item for item in snapshot.meetingPackDraft.agenda[:3] if _as_str(item)),
            ]
        )
    )
    if not raw_text:
        return
    signal_id = _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=source_id,
        review_id=None,
        task_id=None,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"{source_type}:{source_id}",
        created_at=timestamp,
    )
    for ability_key, level, confidence, reason in _infer_general_hits(raw_text, source_type=source_type, preferred=["analyze", "collab", "exec", "write"]):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reflection",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=None,
            source_title=_as_str(snapshot.headline.coreBreakthrough.value) or _as_str(snapshot.headline.mainContradiction.value) or snapshot.clientName,
            week_label=_week_label_from_timestamp(timestamp),
            source_type=source_type,
            raw_text=raw_text,
            context=context,
            created_at=timestamp,
        )


def _insert_signal(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    source_type: str,
    source_id: str,
    review_id: str | None,
    task_id: str | None,
    week_label: str,
    raw_text: str,
    context: dict[str, object],
    dedupe_key: str,
    created_at: str,
) -> str:
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return str(existing["id"])
    signal_id = _new_id("gse")
    db.execute(
        """
        INSERT INTO growth_signal_events(
            id, user_id, user_name, source_type, source_id, review_id, task_id, week_label, raw_text, context_json, dedupe_key, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            user_id,
            user_name,
            source_type,
            source_id,
            review_id,
            task_id,
            week_label,
            raw_text,
            to_json(_json_ready_context(context)),
            dedupe_key,
            created_at,
        ),
    )
    return signal_id


def _has_prior_context_chain(
    db: Database,
    *,
    user_id: str,
    task_id: str | None,
    event_line_id: str | None,
    client_id: str | None,
    source_types: set[str] | None = None,
) -> bool:
    clauses = ["user_id = ?"]
    params: list[object] = [user_id]
    if source_types:
        placeholders = ", ".join("?" for _ in source_types)
        clauses.append(f"source_type IN ({placeholders})")
        params.extend(list(source_types))
    id_clauses: list[str] = []
    if _as_str(task_id):
        id_clauses.append("task_id = ?")
        params.append(_as_str(task_id))
    if _as_str(event_line_id):
        id_clauses.append("json_extract(context_json, '$.eventLineId') = ?")
        params.append(_as_str(event_line_id))
    if _as_str(client_id):
        id_clauses.append("json_extract(context_json, '$.clientId') = ?")
        params.append(_as_str(client_id))
    if not id_clauses:
        return False
    row = db.fetchone(
        f"SELECT 1 FROM growth_signal_events WHERE {' AND '.join(clauses)} AND ({' OR '.join(id_clauses)}) LIMIT 1",
        tuple(params),
    )
    return row is not None


def _continuity_weight(
    db: Database,
    *,
    user_id: str,
    task_id: str | None,
    context: dict[str, object],
) -> float:
    event_line_id = _safe_context_value(context, "eventLineId")
    client_id = _safe_context_value(context, "clientId")
    has_chain = _has_prior_context_chain(
        db,
        user_id=user_id,
        task_id=task_id,
        event_line_id=event_line_id,
        client_id=client_id,
        source_types=TASK_CANDIDATE_SOURCE_TYPES | MEETING_SOURCE_TYPES | STRATEGIC_SOURCE_TYPES,
    )
    return 1.15 if has_chain else 1.0


def _strategic_alignment_weight(context: dict[str, object]) -> float:
    if _safe_context_value(context, "strategicLink"):
        return 1.12
    if _safe_context_value(context, "projectStage") and "战略" in (_safe_context_value(context, "sourceLabel") or ""):
        return 1.08
    return 1.0


def _insert_evidence_and_xp(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    signal_id: str,
    ability_key: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    confidence: GrowthConfidence,
    reason: str,
    review_id: str | None,
    task_id: str | None,
    handbook_entry_id: str | None,
    source_title: str | None,
    week_label: str,
    source_type: str,
    raw_text: str,
    context: dict[str, object] | None = None,
    created_at: str,
) -> tuple[str, int, GrowthValidationState]:
    normalized_context = context or {}
    contribution_tags = _infer_contribution_tags(raw_text, source_type=source_type, ability_key=ability_key)
    validation_state = _infer_validation_state(
        source_type=source_type,
        evidence_type=evidence_type,
        level=level,
        contribution_tags=contribution_tags,
        text=raw_text,
    )
    continuity_weight = _continuity_weight(
        db,
        user_id=user_id,
        task_id=task_id,
        context=normalized_context,
    )
    strategic_alignment_weight = _strategic_alignment_weight(normalized_context)
    org_contribution_score, premium_rate = _score_org_contribution(
        raw_text,
        source_type=source_type,
        ability_key=ability_key,
        evidence_type=evidence_type,
        level=level,
        confidence=confidence,
        contribution_tags=contribution_tags,
        validation_state=validation_state,
    )
    evidence_id = _new_id("gev")
    db.execute(
        """
        INSERT INTO growth_evidence_records(
            id, signal_id, user_id, user_name, ability_key, evidence_type, level, confidence, reason, review_id, task_id, handbook_entry_id, metadata_json, contribution_tags_json, org_contribution_score, suggested_premium_rate, validation_state, ai_reason, ai_confidence, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            signal_id,
            user_id,
            user_name,
            ability_key,
            evidence_type,
            level,
            confidence,
            reason,
            review_id,
            task_id,
            handbook_entry_id,
            to_json(
                {
                    "sourceTitle": source_title or "",
                    "contextSummary": _safe_context_value(normalized_context, "contextSummary") or "",
                    "sourceRoute": _build_source_route(normalized_context),
                    "evidenceRefs": _safe_context_list(normalized_context, "evidenceRefs"),
                    "clientId": _safe_context_value(normalized_context, "clientId"),
                    "clientName": _safe_context_value(normalized_context, "clientName"),
                    "eventLineId": _safe_context_value(normalized_context, "eventLineId"),
                    "eventLineName": _safe_context_value(normalized_context, "eventLineName"),
                    "meetingId": _safe_context_value(normalized_context, "meetingId"),
                    "reviewId": review_id,
                    "taskId": task_id,
                    "projectStage": _safe_context_value(normalized_context, "projectStage"),
                    "businessCategory": _safe_context_value(normalized_context, "businessCategory"),
                    "strategicLink": _safe_context_value(normalized_context, "strategicLink"),
                    "linkedContexts": normalized_context.get("linkedContexts") if isinstance(normalized_context.get("linkedContexts"), list) else [],
                    "continuityWeight": continuity_weight,
                    "strategicAlignmentWeight": strategic_alignment_weight,
                }
            ),
            to_json(contribution_tags),
            org_contribution_score,
            premium_rate,
            validation_state,
            reason,
            0.0,
            created_at,
        ),
    )
    base_xp = int(round(_score_delta(evidence_type, level, confidence) * continuity_weight * strategic_alignment_weight))
    base_xp = max(1, base_xp)
    premium_xp = int(round(base_xp * premium_rate))
    total_xp = base_xp + premium_xp
    xp_dedupe_key = f"{signal_id}:{ability_key}:{evidence_type}"
    db.execute(
        """
        INSERT INTO xp_ledger(
            id, user_id, user_name, ability_key, evidence_id, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp, contribution_tags_json, validation_state, org_contribution_score, dedupe_key, week_label, created_at, reversed_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            _new_id("xp"),
            user_id,
            user_name,
            ability_key,
            evidence_id,
            evidence_type,
            total_xp,
            base_xp,
            premium_rate,
            premium_xp,
            total_xp,
            to_json(contribution_tags),
            validation_state,
            org_contribution_score,
            xp_dedupe_key,
            week_label,
            created_at,
        ),
    )
    return evidence_id, total_xp, validation_state


def _record_validation_event(
    db: Database,
    *,
    user_id: str,
    evidence_id: str,
    event_type: str,
    actor_id: str,
    actor_name: str,
    source_type: str,
    source_id: str,
    detail: dict[str, object],
    created_at: str,
) -> bool:
    existing = db.fetchone(
        """
        SELECT id
        FROM growth_validation_events
        WHERE user_id = ? AND evidence_id = ? AND event_type = ? AND source_type = ? AND source_id = ?
        """,
        (user_id, evidence_id, event_type, source_type, source_id),
    )
    if existing:
        return False
    db.execute(
        """
        INSERT INTO growth_validation_events(
            id, user_id, evidence_id, event_type, actor_id, actor_name, source_type, source_id, detail_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _new_id("gve"),
            user_id,
            evidence_id,
            event_type,
            actor_id,
            actor_name,
            source_type,
            source_id,
            to_json(detail),
            created_at,
        ),
    )
    return True


def reset_review_growth(db: Database, review_id: str) -> None:
    evidence_rows = db.fetchall("SELECT id FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    if evidence_rows:
        db.executemany("DELETE FROM xp_ledger WHERE evidence_id = ?", [(str(row["id"]),) for row in evidence_rows])
    db.execute("DELETE FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    db.execute("DELETE FROM growth_signal_events WHERE review_id = ?", (review_id,))


def ingest_review_growth(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    review: WeeklyReviewRecord,
    task_entries: list[WeeklyReviewTaskEntryRecord],
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    reset_review_growth(db, review.id)

    for entry in task_entries:
        signal_text = _normalize_text(
            " ".join(
                [
                    entry.note,
                    entry.structuredNote.progress,
                    entry.structuredNote.successReason,
                    entry.structuredNote.successExperience,
                    entry.structuredNote.blockerReason,
                    entry.structuredNote.failureInsight,
                    entry.structuredNote.supportNeeded,
                    entry.structuredNote.nextAction,
                ]
            )
        )
        if not signal_text:
            continue
        review_context = {
            "sourceLabel": "周复盘",
            "taskId": entry.taskId,
            "taskTitle": entry.taskSnapshot.title,
            "taskStatus": entry.taskSnapshot.status,
            "contentDomain": entry.contentDomain,
            "clientId": entry.taskSnapshot.clientId,
            "clientName": entry.taskSnapshot.clientName,
            "eventLineId": entry.taskSnapshot.eventLineId,
            "eventLineName": entry.taskSnapshot.eventLineName,
            "projectModuleId": entry.taskSnapshot.projectContext.projectModuleId if entry.taskSnapshot.projectContext else None,
            "projectModuleName": entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else None,
            "projectFlowId": entry.taskSnapshot.projectContext.projectFlowId if entry.taskSnapshot.projectContext else None,
            "projectFlowName": entry.taskSnapshot.projectContext.projectFlowName if entry.taskSnapshot.projectContext else None,
            "projectStage": entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
            "businessCategory": entry.taskSnapshot.eventLineContext.businessCategory if entry.taskSnapshot.eventLineContext else None,
            "evidenceRefs": [_fact_preview_label(fact) for fact in entry.taskSnapshot.projectContext.sourceEvidence[:3]] if entry.taskSnapshot.projectContext else [],
            "contextSummary": _derive_context_summary(
                client_name=entry.taskSnapshot.clientName,
                event_line_name=entry.taskSnapshot.eventLineName,
                project_stage=entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
                business_category=entry.taskSnapshot.eventLineContext.businessCategory if entry.taskSnapshot.eventLineContext else None,
                source_title=entry.taskSnapshot.title,
                next_action=entry.structuredNote.nextAction,
            ),
            "strategicLink": "组织重点对齐" if entry.structuredNote.organizationPlanAlignment == "aligned" else "",
            "sourceRoute": [
                "周复盘",
                entry.taskSnapshot.clientName,
                entry.taskSnapshot.eventLineName,
                entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
            ],
            "linkedContexts": [
                item
                for item in (
                    _context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle=entry.contentDomain),
                    _context_link_dict("task", entry.taskId, entry.taskSnapshot.title, tab="tasks", subtitle=_as_str(entry.taskSnapshot.status)),
                    _context_link_dict("client", entry.taskSnapshot.clientId, entry.taskSnapshot.clientName, tab="client_workspace"),
                    _context_link_dict("event_line", entry.taskSnapshot.eventLineId, entry.taskSnapshot.eventLineName, tab="tasks", subtitle=_as_str(entry.taskSnapshot.eventLineContext.stage) if entry.taskSnapshot.eventLineContext else ""),
                    _context_link_dict(
                        "project_module",
                        entry.taskSnapshot.projectContext.projectModuleId if entry.taskSnapshot.projectContext else None,
                        entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else None,
                        tab="tasks",
                        subtitle=entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else "",
                    ),
                    _context_link_dict(
                        "project_flow",
                        entry.taskSnapshot.projectContext.projectFlowId if entry.taskSnapshot.projectContext else None,
                        entry.taskSnapshot.projectContext.projectFlowName if entry.taskSnapshot.projectContext else None,
                        tab="tasks",
                        subtitle=entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else "",
                    ),
                )
                if item
            ],
            "triggerNode": (
                entry.taskSnapshot.projectContext.projectFlowName
                if entry.taskSnapshot.projectContext and entry.taskSnapshot.projectContext.projectFlowName
                else entry.taskSnapshot.eventLineContext.stage
                if entry.taskSnapshot.eventLineContext
                else "周复盘解释"
            ),
        }
        signal_id = _insert_signal(
            db,
            user_id=user_id,
            user_name=user_name,
            source_type="weekly_review_task_entry",
            source_id=entry.id,
            review_id=review.id,
            task_id=entry.taskId,
            week_label=review.weekLabel,
            raw_text=signal_text,
            context=review_context,
            dedupe_key=f"review:{review.id}:task:{entry.taskId}",
            created_at=timestamp,
        )
        for ability_key, level, confidence, reason in infer_review_hits(entry):
            _insert_evidence_and_xp(
                db,
                user_id=user_id,
                user_name=user_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reflection",
                level=level,
                confidence=confidence,
                reason=reason,
                review_id=review.id,
                task_id=entry.taskId,
                handbook_entry_id=None,
                source_title=entry.taskSnapshot.title,
                week_label=review.weekLabel,
                source_type="weekly_review_task_entry",
                raw_text=signal_text,
                context=review_context,
                created_at=timestamp,
            )

    for note_key, text in (
        ("work_free_note", review.workFreeNote),
        ("personal_growth_note", review.personalGrowthNote),
    ):
        normalized = _normalize_text(text)
        if not normalized:
            continue
        signal_id = _insert_signal(
            db,
            user_id=user_id,
            user_name=user_name,
            source_type="weekly_review_note",
            source_id=f"{review.id}:{note_key}",
            review_id=review.id,
            task_id=None,
            week_label=review.weekLabel,
            raw_text=normalized,
            context={
                "sourceLabel": "周复盘补充说明",
                "noteKey": note_key,
                "contextSummary": "周复盘补充说明",
                "sourceRoute": ["周复盘", "补充说明"],
                "linkedContexts": [_context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle="补充说明")],
                "triggerNode": "周复盘补充说明",
            },
            dedupe_key=f"review:{review.id}:{note_key}",
            created_at=timestamp,
        )
        for ability_key, level, confidence, reason in _infer_general_hits(normalized, source_type="weekly_review_note"):
            _insert_evidence_and_xp(
                db,
                user_id=user_id,
                user_name=user_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reflection",
                level=level,
                confidence=confidence,
                reason=reason,
                review_id=review.id,
                task_id=None,
                handbook_entry_id=None,
                source_title="周复盘补充说明",
                week_label=review.weekLabel,
                source_type="weekly_review_note",
                raw_text=normalized,
                context={
                    "sourceLabel": "周复盘补充说明",
                    "contextSummary": "周复盘补充说明",
                    "sourceRoute": ["周复盘", "补充说明"],
                    "linkedContexts": [_context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle="补充说明")],
                },
                created_at=timestamp,
            )

    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label=review.weekLabel, created_at=timestamp)


def ingest_handbook_codification(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entry: HandbookEntryRecord,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    dedupe_key = f"handbook:{entry.id}"
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return
    signal_id = _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="handbook_entry",
        source_id=entry.id,
        review_id=None,
        task_id=None,
        week_label="",
        raw_text=_normalize_text(f"{entry.title} {entry.summary} {' '.join(entry.tags)}"),
        context={
            "sourceLabel": "成长手册沉淀",
            "sourceType": entry.sourceType,
            "sourceObjectType": entry.sourceObjectType,
            "sourceObjectId": entry.sourceObjectId,
            "sourceTitle": entry.sourceTitle or entry.title,
            "clientId": entry.clientId,
            "clientName": entry.clientName,
            "eventLineId": entry.eventLineId,
            "eventLineName": entry.eventLineName,
            "projectModuleId": entry.projectModuleId,
            "projectModuleName": entry.projectModuleName,
            "projectFlowId": entry.projectFlowId,
            "projectFlowName": entry.projectFlowName,
            "projectStage": entry.projectStage,
            "businessCategory": entry.businessCategory,
            "evidenceRefs": list(entry.evidenceRefs),
            "contextSummary": entry.contextSummary or _derive_context_summary(
                client_name=entry.clientName,
                event_line_name=entry.eventLineName,
                project_stage=entry.projectStage,
                business_category=entry.businessCategory,
                source_title=entry.title,
            ),
            "sourceRoute": ["成长手册", entry.clientName, entry.eventLineName, entry.projectStage],
            "linkedContexts": [link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else [
                item
                for item in (
                    _context_link_dict("handbook", entry.id, entry.title, tab="growth", subtitle=entry.sourceType),
                    _context_link_dict(entry.sourceObjectType or "", entry.sourceObjectId, entry.sourceTitle, tab="growth"),
                    _context_link_dict("client", entry.clientId, entry.clientName, tab="client_workspace"),
                    _context_link_dict("event_line", entry.eventLineId, entry.eventLineName, tab="tasks", subtitle=entry.projectStage or ""),
                )
                if item
            ],
            "strategicLink": entry.contextSummary if "战略" in entry.contextSummary else "",
            "triggerNode": entry.projectFlowName or entry.projectStage or "经验沉淀",
        },
        dedupe_key=dedupe_key,
        created_at=timestamp,
    )
    for ability_key, level, confidence, reason in infer_handbook_hits(entry):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="codification",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=entry.id,
            source_title=entry.title,
            week_label="",
            source_type="handbook_entry",
            raw_text=_normalize_text(f"{entry.title} {entry.summary} {' '.join(entry.tags)}"),
            context={
                "sourceLabel": "成长手册沉淀",
                "sourceObjectType": entry.sourceObjectType,
                "sourceObjectId": entry.sourceObjectId,
                "sourceTitle": entry.sourceTitle or entry.title,
                "clientId": entry.clientId,
                "clientName": entry.clientName,
                "eventLineId": entry.eventLineId,
                "eventLineName": entry.eventLineName,
                "projectStage": entry.projectStage,
                "businessCategory": entry.businessCategory,
                "evidenceRefs": list(entry.evidenceRefs),
                "contextSummary": entry.contextSummary,
                "sourceRoute": ["成长手册", entry.clientName, entry.eventLineName, entry.projectStage],
                "linkedContexts": [link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else [],
                "triggerNode": entry.projectFlowName or entry.projectStage or "经验沉淀",
            },
            created_at=timestamp,
        )
    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label="", created_at=timestamp)


def backfill_handbook_entries(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entries: list[HandbookEntryRecord],
    created_at: str | None = None,
) -> None:
    for entry in entries:
        ingest_handbook_codification(db, user_id=user_id, user_name=user_name, entry=entry, created_at=created_at)


def _build_recommendation_record(db, row) -> LearningRecommendationRecord:
    content = LearningContentItemRecord(
        id=str(row["content_item_id"]),
        contentType=str(row["content_type"]),  # type: ignore[arg-type]
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        title=str(row["title"]),
        summary=str(row["summary"]),
        body=str(row["body"]),
        practiceTask=str(row["practice_task"] or ""),
        acceptanceCriteria=from_json(row["acceptance_criteria_json"], []),  # type: ignore[arg-type]
        sourceKind=str(row["source_kind"] or "system_rule"),
        sourceRefId=str(row["source_ref_id"]) if row["source_ref_id"] else None,
        status=str(row["content_status"] or "active"),
        createdAt=str(row["content_created_at"]),
        updatedAt=str(row["content_updated_at"]),
    )
    profile_map = _fetch_profile_map(db)
    profile = profile_map.get(str(row["ability_key"]))
    linked_contexts = _context_links_from_context({"linkedContexts": from_json(row["linked_contexts_json"], [])})
    return LearningRecommendationRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        userName=str(row["user_name"] or ""),
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        abilityLabel=profile.label if profile else str(row["ability_key"]),
        contentItemId=content.id,
        contentType=content.contentType,
        title=content.title,
        summary=content.summary,
        body=content.body,
        practiceTask=content.practiceTask,
        reason=str(row["reason"] or ""),
        linkedTaskId=str(row["linked_task_id"]) if row["linked_task_id"] else None,
        clientId=str(row["client_id"]) if row["client_id"] else None,
        clientName=str(row["client_name"]) if row["client_name"] else None,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        eventLineName=str(row["event_line_name"]) if row["event_line_name"] else None,
        projectStage=str(row["project_stage"]) if row["project_stage"] else None,
        triggerNode=str(row["trigger_node"]) if row["trigger_node"] else None,
        whyNow=str(row["why_now"] or ""),
        linkedContexts=linked_contexts,
        priority=str(row["priority"] or "normal"),  # type: ignore[arg-type]
        status=str(row["status"] or "active"),  # type: ignore[arg-type]
        acceptedTaskId=str(row["accepted_task_id"]) if row["accepted_task_id"] else None,
        dismissedReason=str(row["dismissed_reason"]) if row["dismissed_reason"] else None,
        dedupeKey=str(row["dedupe_key"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def rebuild_learning_recommendations(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    week_label: str,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    db.execute("DELETE FROM learning_recommendations WHERE user_id = ? AND status = 'active'", (user_id,))

    totals = {str(row["ability_key"]): int(row["xp"] or 0) for row in db.fetchall(
        """
        SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
        FROM xp_ledger
        WHERE user_id = ? AND reversed_at IS NULL
        GROUP BY ability_key
        """,
        (user_id,),
    )}
    recent_evidence = db.fetchall(
        """
        SELECT
            e.ability_key,
            e.reason,
            e.created_at,
            s.source_type,
            s.source_id,
            s.task_id,
            s.context_json
        FROM growth_evidence_records
        e
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE e.user_id = ?
        ORDER BY e.created_at DESC
        LIMIT 12
        """,
        (user_id,),
    )
    blocker_keys = {
        str(row["ability_key"])
        for row in recent_evidence
        if any(token in str(row["reason"] or "") for token in ("阻碍", "支持", "边界", "返工", "风险", "卡点"))
    }

    candidates = sorted(
        ABILITY_ORDER,
        key=lambda key: (0 if key in blocker_keys else 1, totals.get(key, 0), ABILITY_ORDER.index(key)),
    )
    recent_cutoff = (datetime.fromisoformat(timestamp) - timedelta(days=14)).isoformat(timespec="seconds")
    for ability_key in candidates[:3]:
        preferred_type = "correction_card" if ability_key in blocker_keys else "practice_card"
        content_row = db.fetchone(
            """
            SELECT *
            FROM learning_content_items
            WHERE ability_key = ? AND status = 'active'
            ORDER BY CASE content_type
                WHEN ? THEN 0
                WHEN 'practice_card' THEN 1
                WHEN 'method_card' THEN 2
                ELSE 3
            END, created_at ASC
            LIMIT 1
            """,
            (ability_key, preferred_type),
        )
        if not content_row:
            continue
        dedupe_key = f"{ability_key}:{content_row['id']}"
        existing_recent = db.fetchone(
            """
            SELECT 1
            FROM learning_recommendations
            WHERE user_id = ? AND dedupe_key = ? AND status IN ('accepted', 'dismissed') AND updated_at >= ?
            LIMIT 1
            """,
            (user_id, dedupe_key, recent_cutoff),
        )
        if existing_recent:
            continue
        recent_reason_row = next((row for row in recent_evidence if str(row["ability_key"]) == ability_key), None)
        profile = ABILITY_DEFAULTS[ability_key]
        context = from_json(recent_reason_row["context_json"], {}) if recent_reason_row else {}
        reason = (
            f"最近在{profile['label']}上暴露了明显卡点：{recent_reason_row['reason']}"
            if recent_reason_row and str(recent_reason_row["reason"]).strip()
            else f"当前 {profile['label']} 的成长信号偏少，建议补一条针对性练习。"
        )
        why_now = (
            f"当前任务/事件线正处在 {_safe_context_value(context, 'projectStage') or _safe_context_value(context, 'triggerNode') or '关键推进节点'}，如果不补这一步，容易继续拖慢闭环。"
            if context
            else f"当前最容易拖后腿的是 {profile['label']}，建议趁本周任务推进时补一条动作。"
        )
        priority = "high" if ability_key in blocker_keys else "normal"
        linked_contexts = context.get("linkedContexts") if isinstance(context.get("linkedContexts"), list) else []
        db.execute(
            """
            INSERT INTO learning_recommendations(
                id, user_id, user_name, ability_key, content_item_id, trigger_source_type, trigger_source_id, reason, linked_task_id, client_id, client_name, event_line_id, event_line_name, project_stage, trigger_node, why_now, linked_contexts_json, priority, status, accepted_task_id, dismissed_reason, dedupe_key, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, NULL, ?, ?, ?)
            """,
            (
                _new_id("rec"),
                user_id,
                user_name,
                ability_key,
                str(content_row["id"]),
                str(recent_reason_row["source_type"]) if recent_reason_row else "growth_engine",
                str(recent_reason_row["source_id"]) if recent_reason_row else ability_key,
                reason,
                str(recent_reason_row["task_id"]) if recent_reason_row and recent_reason_row["task_id"] else (_safe_context_value(context, "taskId") or None),
                _safe_context_value(context, "clientId"),
                _safe_context_value(context, "clientName"),
                _safe_context_value(context, "eventLineId"),
                _safe_context_value(context, "eventLineName"),
                _safe_context_value(context, "projectStage"),
                _safe_context_value(context, "triggerNode"),
                why_now,
                to_json(linked_contexts),
                priority,
                dedupe_key,
                timestamp,
                timestamp,
            ),
        )


def list_learning_recommendations(db: Database, user_id: str) -> list[LearningRecommendationRecord]:
    ensure_growth_catalog(db)
    rows = db.fetchall(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.user_id = ? AND r.status = 'active'
        ORDER BY CASE r.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, r.created_at DESC
        LIMIT 4
        """,
        (user_id,),
    )
    return [_build_recommendation_record(db, row) for row in rows]


def mark_recommendation_accepted(db: Database, recommendation_id: str, task_id: str, updated_at: str | None = None) -> LearningRecommendationRecord | None:
    timestamp = updated_at or _now_iso()
    row = db.fetchone("SELECT * FROM learning_recommendations WHERE id = ?", (recommendation_id,))
    if not row:
        return None
    db.execute(
        """
        UPDATE learning_recommendations
        SET status = 'accepted', accepted_task_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (task_id, timestamp, recommendation_id),
    )
    updated_row = db.fetchone(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.id = ?
        """,
        (recommendation_id,),
    )
    return _build_recommendation_record(db, updated_row) if updated_row else None


def mark_recommendation_dismissed(db: Database, recommendation_id: str, reason: str = "", updated_at: str | None = None) -> LearningRecommendationRecord | None:
    timestamp = updated_at or _now_iso()
    row = db.fetchone("SELECT * FROM learning_recommendations WHERE id = ?", (recommendation_id,))
    if not row:
        return None
    db.execute(
        """
        UPDATE learning_recommendations
        SET status = 'dismissed', dismissed_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (reason.strip(), timestamp, recommendation_id),
    )
    updated_row = db.fetchone(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.id = ?
        """,
        (recommendation_id,),
    )
    return _build_recommendation_record(db, updated_row) if updated_row else None


def mark_handbook_entry_reused(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entry: HandbookEntryRecord,
    week_label: str,
    source_type: str,
    source_id: str,
    source_label: str = "",
    context_summary: str = "",
    linked_contexts: list[dict[str, object]] | None = None,
    note: str = "",
    created_at: str | None = None,
) -> GrowthValidationActionResponse:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    normalized_source_id = _normalize_text(source_id) or week_label or timestamp[:10]
    reuse_text = _normalize_text(
        " ".join(
            part
            for part in (
                entry.title,
                entry.summary,
                " ".join(entry.tags),
                note.strip(),
                "被复用 团队继续沿用这条方法 模板 规则",
            )
            if part
        )
    )
    dedupe_key = f"handbook_reuse:{entry.id}:{source_type}:{normalized_source_id}"
    existing_signal = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing_signal:
        existing_rows = db.fetchall(
            """
            SELECT validation_state
            FROM growth_evidence_records
            WHERE signal_id = ?
            ORDER BY created_at DESC
            """,
            (str(existing_signal["id"]),),
        )
        validation_state: GrowthValidationState = "institutionalized"
        if existing_rows:
            validation_state = max(
                (str(row["validation_state"] or "candidate") for row in existing_rows),
                key=lambda item: VALIDATION_STATE_ORDER[item],  # type: ignore[index]
            )
        return GrowthValidationActionResponse(
            entryId=entry.id,
            gainedXp=0,
            createdEntries=len(existing_rows),
            validationState=validation_state,
            duplicate=True,
            sourceId=normalized_source_id,
            createdAt=timestamp,
        )

    signal_id = _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="handbook_reuse",
        source_id=f"{entry.id}:{normalized_source_id}",
        review_id=None,
        task_id=None,
        week_label=week_label,
        raw_text=reuse_text,
        context={
            "sourceLabel": "成长手册复用",
            "handbookEntryId": entry.id,
            "entryTitle": entry.title,
            "validationSourceType": source_type,
            "validationSourceId": normalized_source_id,
            "sourceObjectType": entry.sourceObjectType,
            "sourceObjectId": entry.sourceObjectId,
            "sourceTitle": entry.sourceTitle or entry.title,
            "clientId": entry.clientId,
            "clientName": entry.clientName,
            "eventLineId": entry.eventLineId,
            "eventLineName": entry.eventLineName,
            "projectStage": entry.projectStage,
            "businessCategory": entry.businessCategory,
            "evidenceRefs": list(entry.evidenceRefs),
            "contextSummary": context_summary.strip() or entry.contextSummary or _derive_context_summary(
                client_name=entry.clientName,
                event_line_name=entry.eventLineName,
                project_stage=entry.projectStage,
                business_category=entry.businessCategory,
                source_title=entry.title,
            ),
            "sourceRoute": ["成长手册复用", entry.clientName, entry.eventLineName, entry.projectStage],
            "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
            "note": note.strip(),
            "sourceLabel": source_label.strip(),
            "triggerNode": entry.projectFlowName or entry.projectStage or "方法复用",
        },
        dedupe_key=dedupe_key,
        created_at=timestamp,
    )

    gained_xp = 0
    created_entries = 0
    final_state: GrowthValidationState = "candidate"
    for ability_key, level, confidence, reason in infer_handbook_hits(entry):
        evidence_id, total_xp, validation_state = _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reuse",
            level=level,
            confidence=confidence,
            reason=f"{reason}，且本周已被继续复用",
            review_id=None,
            task_id=None,
            handbook_entry_id=entry.id,
            source_title=entry.title,
            week_label=week_label,
            source_type="handbook_entry",
            raw_text=reuse_text,
            context={
                "sourceLabel": "成长手册复用",
                "handbookEntryId": entry.id,
                "sourceObjectType": entry.sourceObjectType,
                "sourceObjectId": entry.sourceObjectId,
                "sourceTitle": entry.sourceTitle or entry.title,
                "clientId": entry.clientId,
                "clientName": entry.clientName,
                "eventLineId": entry.eventLineId,
                "eventLineName": entry.eventLineName,
                "projectStage": entry.projectStage,
                "businessCategory": entry.businessCategory,
                "evidenceRefs": list(entry.evidenceRefs),
                "contextSummary": context_summary.strip() or entry.contextSummary,
                "sourceRoute": ["成长手册复用", entry.clientName, entry.eventLineName, entry.projectStage],
                "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
                "sourceLabel": source_label.strip(),
                "triggerNode": entry.projectFlowName or entry.projectStage or "方法复用",
            },
            created_at=timestamp,
        )
        _record_validation_event(
            db,
            user_id=user_id,
            evidence_id=evidence_id,
            event_type="handbook_reused",
            actor_id=user_id,
            actor_name=user_name,
            source_type=source_type,
            source_id=normalized_source_id,
            detail={
                "entryId": entry.id,
                "entryTitle": entry.title,
                "note": note.strip(),
                "sourceLabel": source_label.strip(),
                "contextSummary": context_summary.strip(),
                "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
            },
            created_at=timestamp,
        )
        gained_xp += total_xp
        created_entries += 1
        final_state = _max_validation_state(final_state, validation_state)

    db.execute(
        """
        UPDATE handbook_entries
        SET reuse_count = COALESCE(reuse_count, 0) + 1,
            last_reused_at = ?
        WHERE id = ?
        """,
        (timestamp, entry.id),
    )

    # Award reuse XP to the original author if different from the current user
    author_row = db.fetchone(
        "SELECT author_user_id, author_user_name FROM handbook_entries WHERE id = ?",
        (entry.id,),
    )
    original_author_id = str(author_row["author_user_id"] or "") if author_row else ""
    original_author_name = str(author_row["author_user_name"] or "") if author_row else ""
    if original_author_id and original_author_id != user_id:
        for ability_key, level, confidence, reason in infer_handbook_hits(entry):
            _insert_evidence_and_xp(
                db,
                user_id=original_author_id,
                user_name=original_author_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reuse",
                level=level,
                confidence=confidence,
                reason=f"{reason}，方法卡被 {user_name} 复用",
                review_id=None,
                task_id=None,
                handbook_entry_id=entry.id,
                source_title=entry.title,
                week_label=week_label,
                source_type="handbook_entry",
                raw_text=reuse_text,
                context={
                    "sourceLabel": "方法卡被他人复用",
                    "handbookEntryId": entry.id,
                    "reusedBy": user_name,
                    "reusedByUserId": user_id,
                },
                created_at=timestamp,
            )

    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label=week_label, created_at=timestamp)
    return GrowthValidationActionResponse(
        entryId=entry.id,
        gainedXp=gained_xp,
        createdEntries=created_entries,
        validationState=final_state,
        duplicate=False,
        sourceId=normalized_source_id,
        createdAt=timestamp,
    )


def _merged_growth_context(row) -> dict[str, object]:
    signal_context = from_json(row["context_json"], {})
    metadata = from_json(row["metadata_json"], {})
    merged: dict[str, object] = {}
    if isinstance(signal_context, dict):
        merged.update(signal_context)
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
    return merged


def _build_ledger_entry(profile_map: dict[str, GrowthAbilityProfileRecord], row) -> XpLedgerEntryRecord:
    context = _merged_growth_context(row)
    ability_label = profile_map.get(str(row["ability_key"])).label if profile_map.get(str(row["ability_key"])) else str(row["ability_key"])
    source_title = (
        _safe_context_value(context, "sourceTitle")
        or _safe_context_value(context, "taskTitle")
        or _safe_context_value(context, "meetingTitle")
        or _safe_context_value(context, "entryTitle")
        or _safe_context_value(context, "sourceLabel")
    )
    return XpLedgerEntryRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        userName=str(row["user_name"] or ""),
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        abilityLabel=ability_label,
        evidenceId=str(row["evidence_id"]),
        xpType=str(row["xp_type"]),  # type: ignore[arg-type]
        delta=int(row["delta"] or row["total_xp"] or 0),
        baseXp=int(row["base_xp"] or 0),
        premiumRate=float(row["premium_rate"] or 0),
        premiumXp=int(row["premium_xp"] or 0),
        totalXp=int(row["total_xp"] or row["delta"] or 0),
        reason=str(row["reason"] or ""),
        sourceType=str(row["source_type"] or ""),
        sourceId=str(row["source_id"] or ""),
        sourceTitle=source_title or None,
        handbookEntryId=str(row["handbook_entry_id"]) if row["handbook_entry_id"] else _safe_context_value(context, "handbookEntryId"),
        taskId=str(row["task_id"]) if row["task_id"] else _safe_context_value(context, "taskId"),
        meetingId=_safe_context_value(context, "meetingId"),
        reviewId=str(row["review_id"]) if row["review_id"] else _safe_context_value(context, "reviewId"),
        clientId=_safe_context_value(context, "clientId"),
        clientName=_safe_context_value(context, "clientName"),
        eventLineId=_safe_context_value(context, "eventLineId"),
        eventLineName=_safe_context_value(context, "eventLineName"),
        businessCategory=_safe_context_value(context, "businessCategory"),
        projectStage=_safe_context_value(context, "projectStage"),
        sourceRoute=_build_source_route(context),
        evidenceRefs=_safe_context_list(context, "evidenceRefs"),
        contextSummary=_safe_context_value(context, "contextSummary") or "",
        strategicLink=_safe_context_value(context, "strategicLink"),
        linkedContexts=_context_links_from_context(context),
        contributionTags=from_json(row["contribution_tags_json"], []),  # type: ignore[arg-type]
        validationState=str(row["validation_state"] or "candidate"),  # type: ignore[arg-type]
        orgContributionScore=int(row["org_contribution_score"] or 0),
        weekLabel=str(row["week_label"] or ""),
        createdAt=str(row["created_at"]),
        reversedAt=str(row["reversed_at"]) if row["reversed_at"] else None,
    )


def _build_source_coverage(db: Database, user_id: str) -> GrowthSourceCoverageRecord:
    rows = db.fetchall(
        """
        SELECT source_type, context_json
        FROM growth_signal_events
        WHERE user_id = ?
        """,
        (user_id,),
    )
    client_ids: set[str] = set()
    event_line_ids: set[str] = set()
    coverage = GrowthSourceCoverageRecord()
    for row in rows:
        source_type = str(row["source_type"] or "")
        context = from_json(row["context_json"], {})
        if source_type in TASK_CANDIDATE_SOURCE_TYPES:
            coverage.taskSignals += 1
        elif source_type in MEETING_SOURCE_TYPES:
            coverage.meetingSignals += 1
        elif source_type in STRATEGIC_SOURCE_TYPES:
            coverage.strategicSignals += 1
        elif source_type.startswith("weekly_review"):
            coverage.reviewSignals += 1
        elif source_type.startswith("handbook"):
            coverage.handbookSignals += 1
        if isinstance(context, dict):
            client_id = _safe_context_value(context, "clientId")
            event_line_id = _safe_context_value(context, "eventLineId")
            if client_id:
                client_ids.add(client_id)
            if event_line_id:
                event_line_ids.add(event_line_id)
    coverage.clientCount = len(client_ids)
    coverage.eventLineCount = len(event_line_ids)
    return coverage


def _aggregate_growth_highlights(
    entries: list[XpLedgerEntryRecord],
    *,
    mode: str,
    limit: int = 4,
) -> list[GrowthProjectHighlightRecord]:
    buckets: dict[str, dict[str, object]] = {}
    for entry in entries:
        if mode == "client":
            bucket_id = entry.clientId or ""
            label = entry.clientName or ""
            context_link = next((link for link in entry.linkedContexts if link.objectType == "client"), None)
        elif mode == "event_line":
            bucket_id = entry.eventLineId or ""
            label = entry.eventLineName or ""
            context_link = next((link for link in entry.linkedContexts if link.objectType == "event_line"), None)
        else:
            strategic_link = entry.strategicLink or ""
            bucket_id = strategic_link
            label = strategic_link
            context_link = next((link for link in entry.linkedContexts if link.objectType in {"meeting", "client"}), None)
        if not bucket_id or not label:
            continue
        bucket = buckets.setdefault(
            bucket_id,
            {
                "id": bucket_id,
                "label": label,
                "type": mode,
                "weeklyXp": 0,
                "entryCount": 0,
                "summary": "",
                "abilityKeys": [],
                "contexts": [],
            },
        )
        bucket["weeklyXp"] = int(bucket["weeklyXp"]) + entry.totalXp
        bucket["entryCount"] = int(bucket["entryCount"]) + 1
        if entry.reason and not bucket["summary"]:
            bucket["summary"] = entry.reason
        ability_keys = set(bucket["abilityKeys"])
        ability_keys.add(entry.abilityKey)
        bucket["abilityKeys"] = list(ability_keys)
        contexts: list[GrowthContextLinkRecord] = bucket["contexts"]
        if context_link and not any(link.objectId == context_link.objectId and link.objectType == context_link.objectType for link in contexts):
            contexts.append(context_link)
    ordered = sorted(buckets.values(), key=lambda item: (-int(item["weeklyXp"]), -int(item["entryCount"]), str(item["label"])))
    return [
        GrowthProjectHighlightRecord(
            id=str(item["id"]),
            label=str(item["label"]),
            type=str(item["type"]),
            weeklyXp=int(item["weeklyXp"]),
            entryCount=int(item["entryCount"]),
            summary=str(item["summary"] or ""),
            abilityKeys=list(item["abilityKeys"]),  # type: ignore[arg-type]
            contexts=list(item["contexts"]),
        )
        for item in ordered[:limit]
    ]


def _build_pending_capture_record(row) -> GrowthPendingCaptureRecord | None:
    context = from_json(row["context_json"], {})
    if not isinstance(context, dict):
        return None
    # Prefer AI-distilled insight quote if available
    insight_quote = _safe_context_value(context, "insightQuote")
    raw_title = _safe_context_value(context, "taskTitle") or _safe_context_value(context, "sourceLabel") or str(row["source_id"])
    if not raw_title and not insight_quote:
        return None
    # If we have an AI-distilled quote, use it as title (the display text);
    # keep raw_title available via summary for source context
    if insight_quote:
        title = insight_quote
        summary = _safe_context_value(context, "insightSourceLabel") or _safe_context_value(context, "contextSummary") or ""
    else:
        title = raw_title
        summary = _safe_context_value(context, "contextSummary") or ""
    return GrowthPendingCaptureRecord(
        id=str(row["id"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        status=str(row["capture_status"] or "open"),  # type: ignore[arg-type]
        title=title,
        summary=summary,
        clientId=_safe_context_value(context, "clientId"),
        clientName=_safe_context_value(context, "clientName"),
        eventLineId=_safe_context_value(context, "eventLineId"),
        eventLineName=_safe_context_value(context, "eventLineName"),
        projectStage=_safe_context_value(context, "projectStage"),
        nextActionText=_safe_context_value(context, "nextAction") or "",
        missingReasons=_safe_context_list(context, "missingReasons"),
        abilityKeys=[ability_key for ability_key, *_ in _infer_general_hits(str(row["raw_text"] or ""), source_type=str(row["source_type"]))],  # type: ignore[list-item]
        linkedContexts=_context_links_from_context(context),
        stateReason=str(row["capture_reason"] or ""),
        promotedHandbookEntryId=str(row["promoted_handbook_entry_id"]) if row["promoted_handbook_entry_id"] else None,
        updatedAt=str(row["capture_updated_at"] or row["created_at"] or ""),
    )


def get_pending_capture(db: Database, user_id: str, capture_id: str) -> GrowthPendingCaptureRecord | None:
    row = db.fetchone(
        """
        SELECT
            s.*,
            cs.status AS capture_status,
            cs.reason AS capture_reason,
            cs.promoted_handbook_entry_id,
            cs.updated_at AS capture_updated_at
        FROM growth_signal_events s
        LEFT JOIN growth_capture_states cs
            ON cs.signal_id = s.id AND cs.user_id = s.user_id
        WHERE s.user_id = ?
          AND s.id = ?
          AND s.source_type IN ('task_context_candidate', 'task_attachment_candidate')
        """,
        (user_id, capture_id),
    )
    if not row:
        return None
    return _build_pending_capture_record(row)


def update_pending_capture_state(
    db: Database,
    *,
    user_id: str,
    capture_id: str,
    status: GrowthPendingCaptureState,
    reason: str = "",
    handbook_entry_id: str | None = None,
    created_at: str | None = None,
) -> GrowthPendingCaptureRecord | None:
    timestamp = created_at or _now_iso()
    row = db.fetchone(
        """
        SELECT id
        FROM growth_signal_events
        WHERE user_id = ?
          AND id = ?
          AND source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
        """,
        (user_id, capture_id),
    )
    # Fallback: try with the cloud session user_id if operator ID didn't match
    if not row:
        row = db.fetchone(
            """
            SELECT id
            FROM growth_signal_events
            WHERE id = ?
              AND source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
            """,
            (capture_id,),
        )
    if not row:
        return None
    existing = db.fetchone(
        "SELECT id, user_id FROM growth_capture_states WHERE signal_id = ?",
        (capture_id,),
    )
    normalized_reason = reason.strip()
    actual_user_id = str(existing["user_id"]) if existing else user_id
    if existing:
        db.execute(
            """
            UPDATE growth_capture_states
            SET status = ?,
                reason = ?,
                promoted_handbook_entry_id = ?,
                updated_at = ?
            WHERE signal_id = ?
            """,
            (status, normalized_reason, handbook_entry_id, timestamp, capture_id),
        )
    else:
        db.execute(
            """
            INSERT INTO growth_capture_states(
                id, user_id, signal_id, status, reason, promoted_handbook_entry_id, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_new_id("gcs"), user_id, capture_id, status, normalized_reason, handbook_entry_id, timestamp, timestamp),
        )
    return get_pending_capture(db, user_id, capture_id)


def _list_pending_captures(db: Database, user_id: str, *, limit: int = 6) -> list[GrowthPendingCaptureRecord]:
    rows = db.fetchall(
        """
        SELECT
            s.*,
            cs.status AS capture_status,
            cs.reason AS capture_reason,
            cs.promoted_handbook_entry_id,
            cs.updated_at AS capture_updated_at
        FROM growth_signal_events s
        LEFT JOIN growth_evidence_records e ON e.signal_id = s.id
        LEFT JOIN growth_capture_states cs
            ON cs.signal_id = s.id AND cs.user_id = s.user_id
        WHERE s.user_id = ? AND e.id IS NULL AND s.source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
          AND COALESCE(cs.status, 'open') = 'open'
        ORDER BY s.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    captures: list[GrowthPendingCaptureRecord] = []
    for row in rows:
        record = _build_pending_capture_record(row)
        if record:
            captures.append(record)
    return captures


def _build_focus_actions(recommendations: list[LearningRecommendationRecord]) -> list[GrowthFocusActionRecord]:
    return [
        GrowthFocusActionRecord(
            id=item.id,
            title=item.title,
            summary=item.summary,
            whyNow=item.whyNow or item.reason,
            linkedTaskId=item.linkedTaskId,
            clientId=item.clientId,
            clientName=item.clientName,
            eventLineId=item.eventLineId,
            eventLineName=item.eventLineName,
            projectStage=item.projectStage,
            triggerNode=item.triggerNode,
            linkedContexts=item.linkedContexts,
        )
        for item in recommendations[:3]
    ]


def _build_ability_gaps(
    ability_scores: list[GrowthAbilityScoreRecord],
    recommendations: list[LearningRecommendationRecord],
    pending_captures: list[GrowthPendingCaptureRecord],
    project_highlights: list[GrowthProjectHighlightRecord],
    event_line_highlights: list[GrowthProjectHighlightRecord],
    strategic_highlights: list[GrowthProjectHighlightRecord],
) -> list[GrowthAbilityGapRecord]:
    score_map = {item.abilityKey: item for item in ability_scores}
    candidates: dict[str, GrowthAbilityGapRecord] = {}

    def push_candidate(
        ability_key: str,
        *,
        required_score: int,
        reason: str,
        source_label: str,
        source_type: str,
        source_id: str,
    ) -> None:
        current = score_map.get(ability_key)
        if not current:
            return
        gap = max(0, required_score - current.currentScore)
        if gap <= 0:
            return
        existing = candidates.get(ability_key)
        candidate = GrowthAbilityGapRecord(
            abilityKey=ability_key,  # type: ignore[arg-type]
            label=current.label,
            currentScore=current.currentScore,
            requiredScore=required_score,
            gap=gap,
            reason=reason,
            sourceLabel=source_label,
            sourceType=source_type,
            sourceId=source_id,
        )
        if existing is None or candidate.gap > existing.gap or (candidate.gap == existing.gap and candidate.requiredScore > existing.requiredScore):
            candidates[ability_key] = candidate

    for recommendation in recommendations:
        push_candidate(
            recommendation.abilityKey,
            required_score=72 if recommendation.priority == "high" else 62,
            reason=recommendation.whyNow or recommendation.reason,
            source_label=recommendation.eventLineName or recommendation.clientName or recommendation.triggerNode or recommendation.title or "",
            source_type="event_line" if recommendation.eventLineId else "client" if recommendation.clientId else "recommendation",
            source_id=recommendation.eventLineId or recommendation.clientId or recommendation.id,
        )
    for capture in pending_captures:
        source_context = next(
            (
                context
                for context in capture.linkedContexts
                if context.objectType in {"task", "event_line", "client", "project_module", "project_flow", "strategic_focus"}
            ),
            None,
        )
        source_type = source_context.objectType if source_context else "capture"
        source_id = source_context.objectId if source_context else capture.id
        source_label = source_context.label if source_context else capture.eventLineName or capture.clientName or capture.title
        reason = "；".join(capture.missingReasons[:2]) or capture.summary or capture.nextActionText or "当前这条成长候选还缺正式闭环"
        for ability_key in capture.abilityKeys[:3]:
            push_candidate(
                ability_key,
                required_score=70 if capture.eventLineId or capture.projectStage else 64,
                reason=reason,
                source_label=source_label or "",
                source_type=source_type,
                source_id=source_id,
            )

    def push_highlights(
        highlights: list[GrowthProjectHighlightRecord],
        *,
        default_type: str,
        required_score: int,
        reason_prefix: str,
    ) -> None:
        for item in highlights:
            source_context = next(
                (
                    context
                    for context in item.contexts
                    if context.objectType in {"client", "event_line", "strategic_focus", "project_module", "project_flow", "task"}
                ),
                None,
            )
            source_type = source_context.objectType if source_context else default_type
            source_id = source_context.objectId if source_context else item.id
            source_label = source_context.label if source_context else item.label
            reason = item.summary or f"{reason_prefix}{item.label}"
            for ability_key in item.abilityKeys[:3]:
                push_candidate(
                    ability_key,
                    required_score=required_score,
                    reason=reason,
                    source_label=source_label,
                    source_type=source_type,
                    source_id=source_id,
                )

    push_highlights(project_highlights, default_type="client", required_score=66, reason_prefix="当前项目正在持续消耗这项能力：")
    push_highlights(event_line_highlights, default_type="event_line", required_score=70, reason_prefix="当前事件线正在持续要求这项能力：")
    push_highlights(strategic_highlights, default_type="strategic_focus", required_score=74, reason_prefix="当前战略线明确要求继续补强这项能力：")

    return sorted(candidates.values(), key=lambda item: (-item.gap, ABILITY_ORDER.index(item.abilityKey)))[:3]


def build_growth_ledger(db: Database, user_id: str, *, ability_key: str | None = None, week_label: str | None = None) -> GrowthLedgerResponse:
    ensure_growth_catalog(db)
    profile_map = _fetch_profile_map(db)
    clauses = ["l.user_id = ?", "l.reversed_at IS NULL"]
    params: list[object] = [user_id]
    if ability_key:
        clauses.append("l.ability_key = ?")
        params.append(ability_key)
    if week_label:
        clauses.append("l.week_label = ?")
        params.append(week_label)
    rows = db.fetchall(
        f"""
        SELECT
            l.*,
            e.reason,
            e.evidence_type,
            e.metadata_json,
            e.contribution_tags_json,
            e.validation_state,
            e.org_contribution_score,
            e.review_id,
            e.task_id,
            e.handbook_entry_id,
            s.source_type,
            s.source_id,
            s.context_json
        FROM xp_ledger l
        INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE {' AND '.join(clauses)}
        ORDER BY l.created_at DESC
        LIMIT 80
        """,
        tuple(params),
    )
    return GrowthLedgerResponse(entries=[_build_ledger_entry(profile_map, row) for row in rows])


def build_growth_overview(db: Database, user_id: str, user_name: str, *, week_label: str = "") -> GrowthOverviewRecord:
    ensure_growth_catalog(db)
    profile_map = _fetch_profile_map(db)
    totals = {
        str(row["ability_key"]): int(row["xp"] or 0)
        for row in db.fetchall(
            """
            SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL
            GROUP BY ability_key
            """,
            (user_id,),
        )
    }
    weekly = {
        str(row["ability_key"]): int(row["xp"] or 0)
        for row in db.fetchall(
            """
            SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL AND week_label = ?
            GROUP BY ability_key
            """,
            (user_id, week_label),
        )
    } if week_label else {}
    weekly_row = db.fetchone(
        """
        SELECT
            SUM(COALESCE(NULLIF(base_xp, 0), CASE WHEN COALESCE(NULLIF(total_xp, 0), delta) > 0 THEN COALESCE(NULLIF(total_xp, 0), delta) ELSE 0 END)) AS base_xp,
            SUM(COALESCE(premium_xp, 0)) AS premium_xp,
            SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS total_xp
        FROM xp_ledger
        WHERE user_id = ? AND reversed_at IS NULL AND week_label = ?
        """,
        (user_id, week_label),
    ) if week_label else None

    recent_entries = build_growth_ledger(db, user_id).entries[:6]
    weekly_entries = build_growth_ledger(db, user_id, week_label=week_label).entries if week_label else recent_entries
    recommendations = list_learning_recommendations(db, user_id)
    pending_captures = _list_pending_captures(db, user_id)

    ability_scores: list[GrowthAbilityScoreRecord] = []
    total_xp = 0
    weekly_xp = 0
    for ability_key in ABILITY_ORDER:
        total = totals.get(ability_key, 0)
        total_xp += total
        week_delta = weekly.get(ability_key, 0)
        weekly_xp += week_delta
        stage, next_stage = _ability_stage(total)
        recent_evidence = next((item.reason for item in recent_entries if item.abilityKey == ability_key and item.reason.strip()), "")
        ability_scores.append(
            GrowthAbilityScoreRecord(
                abilityKey=ability_key,  # type: ignore[arg-type]
                label=profile_map[ability_key].label,
                currentScore=_current_score(total),
                previousScore=max(0, _current_score(max(0, total - week_delta))),
                totalXp=total,
                weeklyXp=week_delta,
                stage=stage,
                nextStage=next_stage,
                evidence=recent_evidence,
            )
        )

    overall_stage, _ = _ability_stage(total_xp)
    level = max(1, total_xp // 100 + 1)
    xp_to_next = 100 - (total_xp % 100) if total_xp % 100 else 100
    rank = _build_rank_record(total_xp)
    project_highlights = _aggregate_growth_highlights(weekly_entries, mode="client")
    event_line_highlights = _aggregate_growth_highlights(weekly_entries, mode="event_line")
    strategic_highlights = _aggregate_growth_highlights(
        [entry for entry in weekly_entries if entry.strategicLink],
        mode="strategic",
        limit=3,
    )
    return GrowthOverviewRecord(
        userId=user_id,
        userName=user_name,
        totalXp=total_xp,
        weeklyXp=weekly_xp,
        weeklyBaseXp=int(weekly_row["base_xp"] or 0) if weekly_row else 0,
        weeklyPremiumXp=int(weekly_row["premium_xp"] or 0) if weekly_row else 0,
        level=level,
        stageLabel=f"{overall_stage}期",
        xpToNext=xp_to_next,
        rank=rank,
        abilities=ability_scores,
        recentEntries=recent_entries,
        recommendations=recommendations,
        sourceCoverage=_build_source_coverage(db, user_id),
        projectGrowthHighlights=project_highlights,
        eventLineGrowthHighlights=event_line_highlights,
        strategicAlignmentHighlights=strategic_highlights,
        pendingCaptures=pending_captures,
        currentFocusActions=_build_focus_actions(recommendations),
        abilityGaps=_build_ability_gaps(ability_scores, recommendations, pending_captures, project_highlights, event_line_highlights, strategic_highlights),
        updatedAt=_now_iso(),
    )
~~~

