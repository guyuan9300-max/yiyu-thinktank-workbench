from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Retrieval stages used by knowledge search / evidence pipelines.
# Centralised here so call sites and validators agree on the white list.
RETRIEVAL_STAGE_VALUES: tuple[str, ...] = (
    "master_index",
    "surrogate",
    "raw_chunk",
    "state_pool",
)


def normalize_retrieval_stage(value: object, default: str = "raw_chunk") -> str:
    """Normalise a retrieval stage value to one of RETRIEVAL_STAGE_VALUES.

    Any input not in the white list (including None, empty string, legacy
    aliases) falls back to ``default``. This keeps Pydantic Literal fields
    from blowing up at runtime when upstream data is missing or stale.
    """
    return value if value in RETRIEVAL_STAGE_VALUES else default


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
# 客户项目情报流。profile_completion 已下线（2026-05-18）→ 由数据中心承接，资讯情报站不再处理。
IntelligenceContentKind = Literal["timely_intelligence", "public_opinion"]
IntelligenceWorkObjectType = Literal["client", "project_module"]
IntelligenceFocusScopeType = Literal["global", "client", "project_module"]
IntelligenceItemUserStatus = Literal["active", "dismissed", "following"]
IntelligenceSearchIntentStatus = Literal["missing", "stale", "ready", "running", "failed"]
IntelligenceSupplyStatus = Literal["missing", "stale", "ready", "running", "failed"]
MeetingStage = Literal["prepared", "ingested", "extracted", "resolved", "published"]
AiProvider = Literal["mock", "openai_compatible", "qwen", "doubao", "openclaw"]
AiModelMode = Literal["auto", "online_first", "local_first", "local_only"]
AiModelProfileKey = Literal["online_primary", "local_text_deep", "local_vision_ocr", "local_fast"]
AiModelCapability = Literal["online_primary", "deep_analysis", "vision_ocr", "fast_structured"]
AccountStatus = Literal["pending", "approved", "rejected", "disabled"]
MembershipStatus = Literal["none", "pending", "approved", "rejected"]
EmployeeRole = Literal["admin", "employee"]
SandboxKind = Literal["local", "organization"]
SandboxStatus = Literal["active", "archived"]
CollaboratorInboxStatus = Literal["pending", "accepted", "returned"]
OrgRoleLevel = Literal["employee", "supervisor", "department_lead", "organization_lead"]
OrgReportingLineType = Literal["business", "administrative"]
OrgTaskEditScope = Literal["self", "manager", "department", "organization"]
OrgTaskControlLevel = Literal["normal", "leader_control", "department_control", "organization_control"]
OrgRuleActorScope = Literal["assignee", "manager", "department_lead", "organization_lead", "creator"]
OrgWorkflowTriggerType = Literal["weekly_followup", "task_created", "meeting_closed", "client_update", "manual"]
DnaSourceLevel = Literal["organization", "client"]
OrganizationDnaModuleKey = Literal["organization_intro", "business_intro", "team_intro", "market_intro"]
OrganizationDnaV2Kind = Literal["stable_dna", "evolving_dna", "gap_dna", "risk_dna"]
OrganizationDnaV2Status = Literal["candidate", "confirmed", "stale", "deprecated"]
OrganizationDnaEvidenceLevel = Literal["L1", "L2", "L3", "internal", "weak"]
DnaToolPurpose = Literal["intro", "strategy", "task_next_action", "asset_gap", "public_material", "risk_check"]
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


class AiModelProfileRecord(BaseModel):
    enabled: bool = False
    provider: AiProvider = "openai_compatible"
    providerLabel: str = ""
    baseUrl: str = ""
    model: str = ""
    capability: AiModelCapability = "deep_analysis"
    isLocal: bool = False


class AppSettingsPayload(BaseModel):
    currentOperatorId: str | None = None
    cloudApiUrl: str | None = None
    aiProvider: AiProvider | None = None
    aiProviderLabel: str | None = None
    aiBaseUrl: str | None = None
    aiModel: str | None = None
    apiKey: str | None = None
    clearApiKey: bool = False
    advancedAiRoutingEnabled: bool | None = None
    aiModelMode: AiModelMode | None = None
    aiModelProfiles: dict[str, AiModelProfileRecord] | None = None
    aiModelProfileApiKeys: dict[str, str] | None = None
    clearAiModelProfileApiKeys: list[str] = Field(default_factory=list)


class AppSettingsResponse(BaseModel):
    currentOperatorId: str
    aiProvider: AiProvider
    aiProviderLabel: str = ""
    aiBaseUrl: str = ""
    aiModel: str
    dataDir: str
    backupDir: str
    cloudApiUrl: str = ""
    lastBackupAt: str | None = None
    foldersRootLabel: str
    aiConfigured: bool
    aiCredentialSource: str
    aiFingerprint: str | None = None
    advancedAiRoutingEnabled: bool = False
    aiModelMode: AiModelMode = "auto"
    aiModelProfiles: dict[str, AiModelProfileRecord] = Field(default_factory=dict)
    demoDataLoaded: bool = False


class SandboxWorkspaceRecord(BaseModel):
    id: str
    kind: SandboxKind
    name: str
    status: SandboxStatus = "active"
    cloudApiUrl: str = ""
    cloudConnected: bool = False
    cloudUserFullName: str | None = None
    cloudUserEmail: str | None = None
    organizationId: str | None = None
    organizationName: str | None = None
    localIdentityId: str | None = None
    isLegacyDefault: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str
    lastActiveAt: str | None = None


class SandboxLocalDraftSummary(BaseModel):
    available: bool = False
    active: bool = False
    hasData: bool = False
    migrated: bool = False
    migratedToSandboxId: str | None = None
    migratedAt: str | None = None
    clients: int = 0
    tasks: int = 0
    taskLists: int = 0
    taskTags: int = 0
    documents: int = 0
    experienceQuotes: int = 0


class SandboxWorkspacesResponse(BaseModel):
    activeSandboxId: str
    workspaces: list[SandboxWorkspaceRecord]
    localDraftSummary: SandboxLocalDraftSummary | None = None


class SandboxWorkspaceCreatePayload(BaseModel):
    kind: SandboxKind = "organization"
    name: str = ""
    cloudApiUrl: str = ""


class SandboxWorkspaceUpdatePayload(BaseModel):
    name: str | None = None
    cloudApiUrl: str | None = None


class HealthAiState(BaseModel):
    provider: AiProvider
    providerLabel: str = ""
    baseUrl: str = ""
    model: str
    ready: bool
    detail: str
    credentialSource: str
    fingerprint: str | None = None
    profileKey: str = "unified"
    mode: AiModelMode = "auto"


class HealthResponse(BaseModel):
    backend: Literal["online"] = "online"
    appName: str
    appVersion: str
    buildVersion: str
    gitCommit: str | None = None
    bundleManifestId: str | None = None
    backendBuildHash: str
    backendSourceHash: str
    frontendRendererEntry: str | None = None
    frontendRendererHash: str | None = None
    backendSchemaVersion: int
    runtimeMode: Literal["packaged", "dev"]
    installPathStatus: Literal["recommended", "unexpected", "dev"]
    startedAt: str
    featureFlags: list[str] = Field(default_factory=list)
    dataDir: str
    stats: dict[str, int]
    ai: HealthAiState
    aiProfiles: dict[str, HealthAiState] = Field(default_factory=dict)
    advancedAiRoutingEnabled: bool = False
    aiModelMode: AiModelMode = "auto"
    linkMaterialDiagnostics: dict[str, object] = Field(default_factory=dict)


class LastCloudAiSyncStatusRecord(BaseModel):
    state: Literal["never", "synced", "uploaded", "failed", "skipped", "proxy_available"] = "never"
    at: str | None = None
    reason: str | None = None
    provider: str | None = None
    providerLabel: str | None = None
    model: str | None = None
    baseUrl: str | None = None
    hasApiKey: bool = False
    fingerprint: str | None = None
    proxyMode: str | None = None


class SettingsResponse(BaseModel):
    settings: AppSettingsResponse
    operators: list[OperatorRecord]
    health: HealthResponse
    lastCloudAiSyncStatus: LastCloudAiSyncStatusRecord = Field(default_factory=LastCloudAiSyncStatusRecord)


class SessionUserRecord(BaseModel):
    id: str
    organizationId: str
    organizationName: str | None = None
    email: str
    phone: str | None = None
    fullName: str
    primaryRole: EmployeeRole
    accountStatus: AccountStatus
    membershipStatus: MembershipStatus = "approved"
    membershipRejectedReason: str | None = None
    departmentId: str | None = None
    departmentName: str | None = None
    isDepartmentLead: bool = False
    pendingInviteCode: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None


class OrganizationCandidateRecord(BaseModel):
    organizationId: str
    organizationName: str | None = None
    organizationSlug: str | None = None
    memberId: str
    fullName: str
    email: str
    primaryRole: EmployeeRole
    accountStatus: AccountStatus
    membershipStatus: MembershipStatus = "approved"
    departmentId: str | None = None
    departmentName: str | None = None


class AuthStateResponse(BaseModel):
    authenticated: bool
    user: SessionUserRecord | None = None
    message: str | None = None
    sessionMode: Literal["local", "cloud"] = "cloud"
    requiresLocalIdentitySetup: bool = False
    localIdentityStatus: Literal["needs_setup", "ready", "none", "draft"] | None = None
    # True 表示这是"网络中断 + 本地缓存"兜底产生的离线降级态(云端没法确认身份/成员资格)。
    # 前端据此把"未确认"当成 last-known-good 处理,而不是当成"被拒绝"去清空本地数据 / 强制身份页。
    degraded: bool = False
    organizationSelectionRequired: bool = False
    organizationSelectionToken: str | None = None
    organizations: list[OrganizationCandidateRecord] = Field(default_factory=list)


class SelectOrganizationPayload(BaseModel):
    organizationSelectionToken: str
    organizationId: str


class CreateOrganizationPayload(BaseModel):
    organizationName: str


class JoinOrganizationPayload(BaseModel):
    inviteCode: str
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None


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


class LinkImportRelayRequestRecord(BaseModel):
    """云端 link_import_requests 队列记录(手机提交→桌面处理的链接转文字中继)。"""

    id: str
    organizationId: str
    url: str
    sourceHint: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    requestedByUserId: str
    requestedByName: str = ""
    errorMessage: str | None = None
    localRunId: str | None = None
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
    phone: str
    fullName: str
    password: str
    inviteCode: str | None = None
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False


class AuthLoginPayload(BaseModel):
    email: str | None = None
    identifier: str | None = None
    password: str
    rememberMe: bool = True


class LocalAuthRegisterPayload(BaseModel):
    email: str
    phone: str
    fullName: str
    password: str
    organizationMode: Literal["create", "join"] = "create"
    organizationName: str | None = None
    inviteCode: str | None = None
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None


class LocalAuthLoginPayload(BaseModel):
    identifier: str
    password: str
    rememberMe: bool = True


class RememberedCloudAuthAccount(BaseModel):
    email: str
    identifier: str | None = None
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
    email: str = ""
    identifier: str | None = None
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
    phone: str | None = None


class EmployeeRecord(BaseModel):
    id: str
    email: str
    phone: str | None = None
    fullName: str
    primaryRole: EmployeeRole
    accountStatus: AccountStatus
    membershipStatus: MembershipStatus = "approved"
    membershipRejectedReason: str | None = None
    membershipSubmittedAt: str | None = None
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


class MaintenanceModeStatusRecord(BaseModel):
    available: bool
    active: bool
    canEnter: bool
    canManagePermissions: bool
    organizationId: str | None = None
    userId: str | None = None
    reason: str | None = None


class MaintenanceMemberPermissionRecord(BaseModel):
    userId: str
    fullName: str
    email: str
    primaryRole: EmployeeRole
    authorized: bool
    canManagePermissions: bool


class MaintenancePermissionMemberPayload(BaseModel):
    userId: str
    authorized: bool
    canManagePermissions: bool = False


class MaintenancePermissionUpdatePayloadRecord(BaseModel):
    members: list[MaintenancePermissionMemberPayload] = Field(default_factory=list)


class MaintenanceAuditPayloadRecord(BaseModel):
    action: str
    detail: dict[str, object] = Field(default_factory=dict)
    targetUserId: str | None = None


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


class OrgInviteResolveResultRecord(BaseModel):
    valid: bool
    organizationId: str | None = None
    organizationName: str | None = None
    departmentId: str | None = None
    departmentName: str | None = None
    message: str | None = None


class OrgProfileRecord(BaseModel):
    organizationId: str
    name: str
    annualGoal: str = ""
    annualStrategyYear: str = ""
    annualStrategy: str = ""
    quarterPlans: list["OrgQuarterPlanRecord"] = Field(default_factory=list)
    quarterlyFocus: list[str] = Field(default_factory=list)
    leaderUserId: str | None = None
    leaderName: str = ""
    introDocument: "OrgIntroDocumentRecord | None" = None
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
    introDocument: "OrgIntroDocumentRecord | None" = None
    parentDepartmentId: str | None = None
    mission: str = ""
    businessContext: str = ""
    teamContext: str = ""
    quarterPlan: OrgDepartmentQuarterPlanRecord = Field(default_factory=OrgDepartmentQuarterPlanRecord)
    quarterlyFocus: list[str] = Field(default_factory=list)
    collaborationDepartmentIds: list[str] = Field(default_factory=list)
    active: bool = True
    updatedAt: str


class OrgIntroDocumentRecord(BaseModel):
    fileName: str = ""
    fileType: str = ""
    markdownContent: str = ""
    normalizedText: str = ""
    summary: str = ""
    contentHash: str = ""
    uploadedBy: str = ""
    uploadedAt: str = ""


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
    # 顾源源 5/24 V2.1 lab: 持岗人为机器人同事时填 bot_member.id; 旧数据无该字段, 按 null 处理.
    holderBotId: str | None = None
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
    # P7：项目编辑弹窗扩展字段
    #   批 1：本地持久化（本期）
    #   批 2：战略陪伴/咨询/情报/任务模块按 isDataCenterIncluded 过滤
    #   批 3：cloud sync 让勾选的同事在他们的电脑上拉到这个项目
    relatedUserIds: list[str] = Field(default_factory=list)
    isDataCenterIncluded: bool = True


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
    # P7：扩展字段同步暴露给前端（旧 client 行默认值：relatedUserIds=[]、isDataCenterIncluded=True）
    relatedUserIds: list[str] = Field(default_factory=list)
    isDataCenterIncluded: bool = True
    # 全局冷冻:用户主动冷冻后,该项目不参与自动 job/计算/资讯/数据中心更新;
    # 所有非工作台 view 的下拉默认不展示;工作台搜索时还能找回
    isFrozen: bool = False
    frozenAt: str | None = None


class ClientFolder(BaseModel):
    id: str
    clientId: str
    label: str
    path: str
    fileCount: int
    lastScannedAt: str | None = None
    folderKind: str = "business"
    sourceType: str = "legacy"
    isSystem: bool = False
    isHidden: bool = False
    sortOrder: int = 100
    createdByRule: str = ""
    suggested: bool = False
    confidence: float = 0.0


class ClientFolderCreatePayload(BaseModel):
    label: str


class ClientFolderUpdatePayload(BaseModel):
    label: str | None = None
    isHidden: bool | None = None
    sortOrder: int | None = None


class ClientDocumentMoveFolderPayload(BaseModel):
    folderId: str | None = None
    folderLabel: str | None = None


class ClientFolderRecommendPayload(BaseModel):
    documentId: str | None = None
    title: str | None = None
    fileName: str | None = None
    contentPreview: str | None = None
    sourceType: str | None = None


class ClientFolderRecommendationRecord(BaseModel):
    targetFolderLabel: str
    confidence: float
    reason: str
    suggestedTags: list[str] = Field(default_factory=list)
    needsReview: bool = False
    documentCount: int = 0
    exampleDocuments: list[str] = Field(default_factory=list)


class ClientFolderRecommendationPlanRecord(BaseModel):
    clientId: str
    generatedAt: str
    visibleFolderLimit: int = 6
    visibleFolderBudget: int = 6
    recommendedVisibleFolders: list[str] = Field(default_factory=list)
    hiddenLegacyFolders: list[str] = Field(default_factory=list)
    pendingReasonCounts: dict[str, int] = Field(default_factory=dict)
    folders: list[ClientFolderRecommendationRecord] = Field(default_factory=list)
    totalDocumentCount: int = 0
    pendingDocumentCount: int = 0
    lowConfidenceDocumentCount: int = 0


class ClientFolderApplyRecommendationPayload(BaseModel):
    targetFolderLabels: list[str] | None = None


class DocumentAutoRepairPreviewPayloadRecord(BaseModel):
    documentIds: list[str] = Field(default_factory=list)
    limit: int = 300
    includeHumanRequired: bool = False


class DocumentAutoRepairApplyPayloadRecord(BaseModel):
    previewId: str | None = None
    documentIds: list[str] = Field(default_factory=list)
    includeHumanRequired: bool = False
    limit: int = 300


class DocumentAutoRepairItemRecord(BaseModel):
    documentId: str
    v2DocumentId: str | None = None
    title: str
    kind: str = "document"
    healthStatus: Literal[
        "v2_ready",
        "original_nonzero_no_v2",
        "zero_byte_original",
        "md_compat_candidate",
        "missing_original",
        "parse_failed",
        "duplicate_candidate",
        "unknown",
    ] = "unknown"
    stage: Literal[
        "ready_classify",
        "repair_ingest",
        "repair_markdown",
        "repair_dedupe",
        "soft_cleanup",
        "minimal_human_check",
        "skip",
    ] = "skip"
    nextSystemAction: str = ""
    targetFolder: str = "待处理"
    tags: list[str] = Field(default_factory=list)
    searchPolicy: Literal["include", "include_low_weight", "exclude_until_repaired", "exclude"] = "exclude_until_repaired"
    requiresHuman: bool = False
    humanQuestion: str | None = None
    confidence: float = 0.0
    reason: str = ""
    sourcePath: str | None = None
    duplicateOfDocumentId: str | None = None


class DocumentAutoRepairPreviewRecord(BaseModel):
    previewId: str
    clientId: str
    generatedAt: str
    visibleFolderBudget: int = 6
    recommendedVisibleFolders: list[str] = Field(default_factory=list)
    pendingReasonCounts: dict[str, int] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
    items: list[DocumentAutoRepairItemRecord] = Field(default_factory=list)


class DocumentAutoRepairApplyResultRecord(BaseModel):
    jobId: str | None = None
    status: Literal["queued", "completed", "failed"] = "queued"
    queuedCount: int = 0
    skippedCount: int = 0
    humanConfirmationCount: int = 0
    message: str = ""


class ImportDocumentRecord(BaseModel):
    documentId: str
    title: str
    fileName: str
    path: str


class ImportRecord(BaseModel):
    id: str
    clientId: str
    sourcePath: str
    mode: Literal["folder", "file"]
    status: Literal["queued", "processing", "completed", "failed", "scanned"]
    importedCount: int
    skippedCount: int
    # 迭代 2 F1+F2：拆分跳过原因
    duplicateCount: int = 0   # 内容重复（同 path 同 hash）
    versionUpgradeCount: int = 0  # 同路径但内容已变 → 自动建版本链
    unsupportedCount: int = 0  # 格式不支持
    createdAt: str
    jobId: str | None = None
    documents: list[ImportDocumentRecord] = Field(default_factory=list)


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
    originalSourcePath: str | None = None
    kind: str
    source: str
    excerpt: str
    tags: list[str]
    importedAt: str


class KnowledgeStatusRecord(BaseModel):
    totalDocuments: int
    totalChunks: int
    ocrReadyRate: float | None = None  # R13: OCR 完整识别率（加权 % · ready=100/partial=70/failed=0）
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
    embeddingProvider: str | None = None
    embeddingDimension: int | None = None
    embeddingSignature: str | None = None
    activeVectorCollection: str | None = None
    vectorIndexStatus: Literal["ready", "stale", "building", "failed"] | None = None
    routerEnabled: bool | None = None
    routerModel: str | None = None
    rerankEnabled: bool | None = None


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
    documentFamilyId: str | None = None
    canonicalKind: str | None = None
    originType: str | None = None
    originId: str | None = None
    isSearchable: bool | None = None
    path: str | None = None
    originalPath: str | None = None
    managedPath: str | None = None
    markdownPath: str | None = None
    openableKind: Literal["original_file", "machine_markdown", "system_card", "unknown"] | None = None
    sourceAvailability: Literal["original_available", "machine_readable_only", "invalid_source", "unknown"] | None = None
    originalAvailable: bool | None = None
    machineReadableAvailable: bool | None = None
    openOriginalDisabledReason: str | None = None
    score: float | None = None
    coverage: float | None = None
    sectionLabel: str | None = None
    retrievalStage: Literal["master_index", "surrogate", "raw_chunk", "state_pool"] | None = None
    isFallback: bool = False
    matchedTerms: list[str] = Field(default_factory=list)
    citationRole: Literal["direct_quote", "direct_support", "background"] | None = None
    citationPriority: int | None = None
    citationReason: str | None = None
    # 迭代 1（鲜度衰减）：携带文档创建时间，供 evidence_quality 做时间衰减。
    # ISO 8601 字符串；None 表示该构造点未提供（向后兼容，evidence_quality
    # 会降级到旧的 year-regex 启发式）。
    createdAt: str | None = None
    # 文档类型键，对应 freshness_decay.HALF_LIFE_BY_TYPE。None → default。
    docType: str | None = None


class AiStructuredResponse(BaseModel):
    content: str
    judgment: str
    analysis: str
    actions: str
    timeline: str


class GroundedAnswerResult(BaseModel):
    """Pure result of grounded answer generation — no DB side effects.

    inline AI / document_ai_action 用这个类型,复用 chat 主链路的 RAG + grounding +
    校验,但不创建 chat thread / chat_messages 行。chat 路径仍然返回 ChatMessageRecord
    (内部走 UPDATE chat_messages 后 fetchone 再 build_chat_message)。

    state_answer_sections 字段值得注意:Q&A 链路有个已知的 finalize bug,当
    primary_generation_partial_preserved 触发时,真实答案被写到 state_answer_sections.official
    而不是 content 字段。inline AI 应该优先读 state_answer_sections.official 作为真答案。
    """
    content: str
    structured: AiStructuredResponse
    answer_mode: str
    evidence_status: str
    failure_reason: str | None = None
    evidence: list[dict] = Field(default_factory=list)
    retrieval_summary: dict = Field(default_factory=dict)
    state_answer_sections: dict = Field(default_factory=dict)


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
    "business_profile",
    "strategy_profile",
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

PageContextPage = Literal[
    "client_workspace",
    "workspace_chat",
    "task_detail",
    "task_ai",
    "meeting_detail",
    "event_line_detail",
    "project_module_detail",
    "project_flow_detail",
    "mobile_consult",
    "topic_radar",
    "strategic_cockpit",
]

PageIntentType = Literal[
    "intro_profile",
    "business_profile",
    "strategy_profile",
    "project_intro",
    "meeting_summary",
    "next_actions",
    "official_judgment_registry",
    "evidence_question",
    "status_progress",
    "task_context",
    "task_next_action",
    "proposal_gap",
    "general",
]

SemanticSourceRole = Literal[
    "institution_identity",
    "problem_definition",
    "program_overview",
    "method_or_model",
    "strategy_direction",
    "operational_update",
    "risk_or_open_issue",
    "financial_or_admin",
    "derived_profile_support",
    "noise_or_template",
]

QuestionFocusGoal = Literal["define", "explain", "status", "evidence", "judgment", "risk", "advice"]
QuestionFocusFacet = Literal["identity", "method", "project", "strategy", "progress", "risk", "action", "general"]
QuestionFocusDepth = Literal["concise", "focused", "expanded", "advisory"]

AnswerLevel = Literal["official", "candidate", "evidence_based", "fallback", "insufficient"]
ContextQualityLevel = Literal["none", "weak", "usable", "strong"]
RouteMode = Literal[
    "state_first",
    "registry_only",
    "raw_doc_drilldown",
    "meeting_evidence",
    "task_context",
    "hybrid",
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
    deepThinkingRequested: bool = False
    activeSkillId: str | None = None
    creativityMode: CreativityMode | None = None
    # R4-P0-1+P0-2 · 公司大脑上下文摘要 (前端 evidence UI 用)
    companyBrainSummary: dict | None = None
    # R4-P0-2 fix (B 5/23 16:46 钦定): response 顶层 5 字段 (不只是子字段)
    evidenceTypes: list[str] = Field(default_factory=list)
    usedTables: list[str] = Field(default_factory=list)
    singleFileOnly: bool = False
    uncertaintyItems: list[dict] = Field(default_factory=list)
    proposedClarifications: list[dict] = Field(default_factory=list)


class ChatThread(BaseModel):
    id: str
    clientId: str
    title: str
    createdAt: str
    updatedAt: str


CreativityMode = Literal["creative", "balanced", "strict"]


class ChatRequest(BaseModel):
    threadId: str | None = None
    prompt: str
    searchId: str | None = None
    workingDocumentIds: list[str] = Field(default_factory=list)
    deepThinking: bool = False
    activeSkillId: str | None = None
    creativityMode: CreativityMode = "balanced"


class WritingSkillRecord(BaseModel):
    id: str
    name: str
    description: str = ""
    distilledMd: str = ""
    isBuiltin: bool = False
    sortOrder: int = 100
    createdAt: str
    updatedAt: str


class WritingSkillCreatePayload(BaseModel):
    name: str
    description: str = ""
    distilledMd: str
    sortOrder: int = 100


class WritingSkillUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    distilledMd: str | None = None
    sortOrder: int | None = None


class WritingSkillDistillPayload(BaseModel):
    samples: list[str]
    skillName: str = ""


class WritingSkillDistillResult(BaseModel):
    distilledMd: str
    samplesProcessed: int
    suggestedName: str = ""


class ChatStartResponse(BaseModel):
    threadId: str
    userMessage: ChatMessageRecord
    assistantMessage: ChatMessageRecord
    analysisRun: "ClientAnalysisRunRecord"
    reusedActiveRun: bool = False
    dedupeReason: Literal["client_active_run"] | None = None


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
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
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


class TaskTagLibraryResponse(BaseModel):
    tags: list[TaskTagRecord]


class TaskListLibraryResponse(BaseModel):
    lists: list[TaskListRecord]


class TaskListDuplicateRepairGroupRecord(BaseModel):
    organizationId: str | None = None
    scope: Literal["org", "personal"]
    name: str
    canonicalId: str
    mergedIds: list[str] = Field(default_factory=list)
    movedTaskCount: int = 0
    deletedListCount: int = 0
    skippedIds: list[str] = Field(default_factory=list)


class TaskListDuplicateRepairResponse(BaseModel):
    groups: list[TaskListDuplicateRepairGroupRecord] = Field(default_factory=list)
    movedTaskCount: int = 0
    deletedListCount: int = 0
    skippedListCount: int = 0
    updatedSettingsCount: int = 0
    updatedAt: str


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
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
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
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
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


class OrgIntroDocumentUploadPayload(BaseModel):
    filePath: str | None = None
    markdownContent: str | None = None
    fileName: str | None = None
    title: str | None = None


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
    meetingPublishDefaultListId: str | None = None
    meetingPublishDefaultPriority: Priority = "normal"
    defaultGoalQuarter: str = ""
    defaultMeetingTitlePrefix: str = "客户会议"
    clientDnaModeLabel: str = "DNA"
    updatedAt: str


class ClientWorkspaceSettingsPayload(BaseModel):
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
    updatedAt: str


class TopicsSettingsPayload(BaseModel):
    chineseOnly: bool | None = None
    requireInsightBeforeActions: bool | None = None
    defaultTaskOwnerMode: TopicTaskOwnerMode | None = None
    defaultTimeRange: str | None = None
    defaultSourceStrategy: str | None = None


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
    updatedAt: str


class SystemAdminSettingsPayload(BaseModel):
    allowBusinessSettingsForEmployees: bool | None = None
    allowOrgDnaForEmployees: bool | None = None
    protectEmployeeAdmin: bool | None = None
    protectAiAndCloud: bool | None = None
    protectCloudSecurity: bool | None = None


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
    departmentId: str | None = None
    departmentName: str | None = None
    membershipStatus: MembershipStatus = "none"
    membershipSubmittedAt: str | None = None
    membershipRejectedReason: str | None = None
    organizationWorkspaceClientId: str | None = None


class OrgMembershipApplyPayload(BaseModel):
    inviteCode: str | None = None
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None


class OrgAdminClaimStatusRecord(BaseModel):
    hasOrganization: bool = False
    organizationId: str | None = None
    organizationName: str | None = None
    hasAdmin: bool = False
    canClaim: bool = False
    reason: str | None = None
    currentUserRole: EmployeeRole | None = None
    currentUserMembershipStatus: MembershipStatus | None = None


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


class FeishuSyncStatusRecord(BaseModel):
    localType: str
    localId: str
    remoteType: str
    remoteId: str | None = None
    remoteUrl: str | None = None
    status: str = "idle"
    message: str = ""
    lastSyncedAt: str | None = None
    updatedAt: str
    details: dict[str, object] = Field(default_factory=dict)


class FeishuDocImportStatusRecord(BaseModel):
    ready: bool = False
    linked: bool = False
    reason: str | None = None
    organizationId: str | None = None
    userId: str | None = None
    boundAt: str | None = None


class FeishuDocImportCandidateRecord(BaseModel):
    token: str
    type: str = "docx"
    title: str
    url: str = ""
    ownerName: str | None = None
    updatedAt: str | None = None
    source: Literal["search", "link"] = "search"


class FeishuDocImportSearchPayload(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    pageSize: int = Field(default=20, ge=1, le=50)


class FeishuDocImportSearchResultRecord(BaseModel):
    items: list[FeishuDocImportCandidateRecord] = Field(default_factory=list)
    message: str = ""


class FeishuDocImportResolveLinksPayload(BaseModel):
    links: list[str] = Field(default_factory=list, max_length=50)


class FeishuDocImportSelectionPayload(BaseModel):
    token: str = Field(min_length=1)
    type: str = "docx"
    title: str = "飞书文档"
    url: str = ""


class FeishuDocImportRequestPayload(BaseModel):
    items: list[FeishuDocImportSelectionPayload] = Field(default_factory=list, min_length=1, max_length=20)


class FeishuDocImportImportedItemRecord(BaseModel):
    token: str
    title: str
    status: Literal["imported", "failed"]
    documentId: str | None = None
    fileName: str | None = None
    path: str | None = None
    remoteUrl: str = ""
    message: str = ""


class FeishuDocImportResultRecord(BaseModel):
    clientId: str
    importedCount: int = 0
    failedCount: int = 0
    items: list[FeishuDocImportImportedItemRecord] = Field(default_factory=list)


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
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
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
    primaryDepartmentId: str | None = None
    primaryDepartmentName: str | None = None


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
    syncStatus: Literal["local", "syncing", "synced", "pending", "error"] | None = None
    cloudId: str | None = None
    pendingSyncAction: Literal["create", "update", "archive"] | None = None
    lastSyncError: str | None = None
    completenessScore: int = 0
    completenessStatus: Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"] = "insufficient"
    completenessMissingSlots: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class EventLineActivityRecord(BaseModel):
    id: str
    eventLineId: str
    sourceType: Literal["task_activity", "meeting", "support_request", "review", "attachment", "manual_note", "merge", "document_ingest", "atomic_fact"]
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
    id: str | None = None
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


class EventLineMergePayload(BaseModel):
    sourceIds: list[str] = Field(min_length=1)


class EventLineMergePreviewItemRecord(BaseModel):
    table: str
    rows: int


class EventLineMergePreviewRecord(BaseModel):
    targetId: str
    targetName: str
    sources: list[dict]  # [{id, name, status}] for UI listing
    impact: list[EventLineMergePreviewItemRecord]
    totalRows: int


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
    userId: str | None = None
    userName: str | None = None
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


class WeeklyMainlineCardRecord(BaseModel):
    id: str = ""
    title: str
    taskCount: int = 0
    completedCount: int = 0
    pendingCount: int = 0
    progressText: str = ""
    nextGoalText: str = ""


class WeeklyMainlineCardsRecord(BaseModel):
    summaryText: str = ""
    mainlines: list[WeeklyMainlineCardRecord] = Field(default_factory=list)
    generatedBy: Literal["ai", "fallback"] = "fallback"
    evidenceMeta: dict[str, object] = Field(default_factory=dict)


class WeeklyEventReviewCardRecord(BaseModel):
    id: str = ""
    title: str
    cardKind: Literal["event_line", "task_cluster", "single_task", "needs_assignment"] = "single_task"
    taskIds: list[str] = Field(default_factory=list)
    taskTitles: list[str] = Field(default_factory=list)
    reflectionPromptText: str = ""
    progressText: str = ""
    nextActionText: str = ""
    materialSuggestionText: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"
    generatedBy: Literal["ai", "fallback"] = "fallback"


class WeeklyEventReviewCardsRecord(BaseModel):
    cards: list[WeeklyEventReviewCardRecord] = Field(default_factory=list)
    generatedBy: Literal["ai", "fallback"] = "fallback"
    evidenceMeta: dict[str, object] = Field(default_factory=dict)


class WeeklyOverviewRefreshPayloadRecord(BaseModel):
    weekLabel: str | None = None
    perspective: Literal["organization", "department", "mine"] | None = None
    departmentId: str | None = None
    force: bool = False


class WeeklyOverviewRefreshStatusRecord(BaseModel):
    weekLabel: str = ""
    perspective: Literal["organization", "department", "mine"] = "mine"
    departmentId: str | None = None
    viewerUserId: str = ""
    status: Literal["idle", "running", "succeeded", "failed"] = "idle"
    startedAt: str | None = None
    generatedAt: str | None = None
    failureReason: str = ""
    sourceCounts: dict[str, object] = Field(default_factory=dict)
    cacheKey: str = ""


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


class TaskContextBriefRecord(BaseModel):
    id: str | None = None
    taskId: str
    clientId: str | None = None
    eventLineId: str | None = None
    brief: str = ""
    shouldDisplay: bool = False
    materialPackHash: str = ""
    usedProjectSignals: list[str] = Field(default_factory=list)
    materialBoundary: str = ""
    qualityFlags: list[str] = Field(default_factory=list)
    generationModel: str = ""
    generationPromptVersion: str = ""
    updatedAt: str = ""


class TaskContextBriefBatchPayload(BaseModel):
    taskIds: list[str] = Field(default_factory=list)


class TaskContextBriefBatchResponse(BaseModel):
    briefs: list[TaskContextBriefRecord] = Field(default_factory=list)


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


class PageScopeRecord(BaseModel):
    page: PageContextPage
    scopeType: str
    scopeId: str
    clientId: str | None = None
    eventLineId: str | None = None
    taskId: str | None = None
    meetingId: str | None = None


class PageIntentRecord(BaseModel):
    rawPrompt: str = ""
    intent: PageIntentType = "general"
    requiresOfficialJudgment: bool = False
    requiresRawEvidence: bool = False
    requiresNextActions: bool = False
    requiresIntroProfile: bool = False
    requiresTaskContext: bool = False
    routeReason: str = ""


class ContextQualityRecord(BaseModel):
    stateObjectCount: int = 0
    approvedJudgmentCount: int = 0
    candidateJudgmentCount: int = 0
    evidenceCardCount: int = 0
    rawEvidenceCount: int = 0
    openQuestionCount: int = 0
    taskCount: int = 0
    meetingCount: int = 0
    contextQuality: ContextQualityLevel = "none"
    canUseAnalysisFirst: bool = False
    mustFallbackToLegacy: bool = False


class AnswerPolicyRecord(BaseModel):
    canAnswer: bool = True
    answerLevel: AnswerLevel = "insufficient"
    mustDiscloseCandidateBoundary: bool = False
    mustUseRawEvidence: bool = False
    shouldCreateProposal: bool = False
    fallbackToLegacyRetrieval: bool = False
    reason: str = ""


class RetrievalModelSettingsRecord(BaseModel):
    embeddingProvider: str = "local_fastembed"
    embeddingModel: str = "BAAI/bge-small-zh-v1.5"
    embeddingDimension: int = 256
    embeddingMode: Literal["local", "doubao", "hash_fallback"] = "local"
    embeddingProfile: Literal["legacy_fastembed_256", "bge_small_native", "bge_m3_dense"] = "legacy_fastembed_256"
    embeddingProjection: bool = True
    routerEnabled: bool = False
    routerProvider: Literal["rules", "local_semantic", "local_llm", "doubao"] = "rules"
    routerMode: Literal["rules", "semantic_shadow", "semantic", "semantic_plus_llm"] = "rules"
    routerModel: str = ""
    routerConfidenceThreshold: float = 0.72
    rerankEnabled: bool = False
    rerankProvider: Literal["rules", "bge_reranker", "reserved"] = "rules"
    rerankModel: str = ""
    answerLayerEnabled: bool = True
    dataCenterKernelEnabled: bool = True
    chatKernelPrimaryEnabled: bool = False
    chatKernelPrimaryClientAllowlist: list[str] = Field(default_factory=list)
    qualityGateMode: Literal["observe", "warn", "block"] = "observe"
    shadowMode: bool = True
    updatedAt: str = ""


class RetrievalModelSettingsPayload(BaseModel):
    embeddingProvider: str | None = None
    embeddingModel: str | None = None
    embeddingDimension: int | None = None
    embeddingMode: Literal["local", "doubao", "hash_fallback"] | None = None
    embeddingProfile: Literal["legacy_fastembed_256", "bge_small_native", "bge_m3_dense"] | None = None
    embeddingProjection: bool | None = None
    routerEnabled: bool | None = None
    routerProvider: Literal["rules", "local_semantic", "local_llm", "doubao"] | None = None
    routerMode: Literal["rules", "semantic_shadow", "semantic", "semantic_plus_llm"] | None = None
    routerModel: str | None = None
    routerConfidenceThreshold: float | None = None
    rerankEnabled: bool | None = None
    rerankProvider: Literal["rules", "bge_reranker", "reserved"] | None = None
    rerankModel: str | None = None
    answerLayerEnabled: bool | None = None
    dataCenterKernelEnabled: bool | None = None
    chatKernelPrimaryEnabled: bool | None = None
    chatKernelPrimaryClientAllowlist: list[str] | None = None
    qualityGateMode: Literal["observe", "warn", "block"] | None = None
    shadowMode: bool | None = None


class RouteDecisionRecord(BaseModel):
    intent: PageIntentType = "general"
    routeMode: RouteMode = "state_first"
    dataSources: list[str] = Field(default_factory=list)
    retrievalMode: Literal["state_only", "raw_only", "hybrid", "deferred"] = "deferred"
    judgmentQueryMode: JudgmentQueryMode | None = None
    evidenceSupportMode: EvidenceSupportMode | None = None
    shouldUseRawEvidence: bool = False
    shouldUseStatePool: bool = True
    shouldUseTaskContext: bool = False
    shouldUseMeetingContext: bool = False
    shouldCreateProposal: bool = False
    queryPlan: list[str] = Field(default_factory=list)
    embeddingProfile: str = "default"
    rerankNeeded: bool = False
    answerLevelHint: Literal["auto", "official", "candidate", "evidence_based", "fallback", "insufficient"] = "auto"
    confidence: float = 0.0
    routeReason: str = ""
    routerSource: Literal["rules", "local_semantic", "local_llm", "smart_router", "fallback"] = "rules"
    fallbackUsed: bool = False


class RetrievalTraceRecord(BaseModel):
    routeDecision: RouteDecisionRecord
    embeddingProvider: str = "local_fastembed"
    embeddingModel: str = "BAAI/bge-small-zh-v1.5"
    embeddingDimension: int = 256
    embeddingSignature: str = "local_fastembed:BAAI/bge-small-zh-v1.5:256"
    vectorCollection: str | None = None
    lexicalHitCount: int = 0
    vectorHitCount: int = 0
    mergedHitCount: int = 0
    rerankHitCount: int = 0
    rawChunkHitCount: int = 0
    readingPassCount: int = 1
    selectedDocumentFamilyCount: int = 0
    selectedCanonicalKinds: list[str] = Field(default_factory=list)
    softwareMaterialIncluded: bool = False
    workingDocumentIds: list[str] = Field(default_factory=list)
    workingDocumentHitCount: int = 0
    fallbackUsed: bool = False
    latencyMs: dict[str, float] = Field(default_factory=dict)


class RetrievalHealthComponentRecord(BaseModel):
    provider: str
    model: str
    dimension: int | None = None
    signature: str | None = None
    ready: bool
    error: str | None = None


class RetrievalHealthRecord(BaseModel):
    embedding: RetrievalHealthComponentRecord
    router: RetrievalHealthComponentRecord
    rerank: dict[str, object] = Field(default_factory=dict)
    shadowMode: bool = True


class RetrievalShadowRunRecord(BaseModel):
    id: str
    clientId: str
    page: str
    prompt: str
    baselineSummary: dict[str, object] = Field(default_factory=dict)
    candidateSummary: dict[str, object] = Field(default_factory=dict)
    overlapRate: float = 0.0
    candidateBetter: bool = False
    failureReason: str | None = None
    createdAt: str


class RetrievalShadowSummaryRecord(BaseModel):
    total: int = 0
    candidateBetterRate: float = 0.0
    overlapRateAvg: float = 0.0
    latencyDeltaMsAvg: float = 0.0
    failures: int = 0


class DataCenterShadowRunRecord(BaseModel):
    id: str
    scopeType: str
    scopeId: str
    page: str
    mode: str
    prompt: str
    baseline: dict[str, object] = Field(default_factory=dict)
    candidate: dict[str, object] = Field(default_factory=dict)
    routeDecision: dict[str, object] = Field(default_factory=dict)
    retrievalTrace: dict[str, object] = Field(default_factory=dict)
    answerPlan: dict[str, object] = Field(default_factory=dict)
    answerQuality: dict[str, object] = Field(default_factory=dict)
    actionSuggestion: list[dict[str, object]] = Field(default_factory=list)
    overlapRate: float = 0.0
    candidateFailed: bool = False
    failureReason: str | None = None
    createdAt: str


class DataCenterShadowSummaryRecord(BaseModel):
    total: int = 0
    answerQualityPassRate: float = 0.0
    directAnswerPassRate: float = 0.0
    evidenceListOnlyFailRate: float = 0.0
    candidateBetterRate: float = 0.0
    candidateBetterByGradeRate: float = 0.0
    gradeDeltaAvg: float = 0.0
    independentChainPassRate: float = 0.0
    overlapRateAvg: float = 0.0
    failures: int = 0


class PageContextPackRecord(BaseModel):
    page: PageContextPage
    scopeType: str
    scopeId: str
    clientId: str | None = None
    intent: PageIntentType = "general"
    officialJudgments: list[dict[str, object]] = Field(default_factory=list)
    candidateJudgments: list[dict[str, object]] = Field(default_factory=list)
    overlayJudgments: list[dict[str, object]] = Field(default_factory=list)
    evidenceCards: list[dict[str, object]] = Field(default_factory=list)
    rawEvidence: list[dict[str, object]] = Field(default_factory=list)
    openQuestions: list[dict[str, object]] = Field(default_factory=list)
    conflicts: list[dict[str, object]] = Field(default_factory=list)
    themeClusters: list[dict[str, object]] = Field(default_factory=list)
    relatedTasks: list[dict[str, object]] = Field(default_factory=list)
    relatedMeetings: list[dict[str, object]] = Field(default_factory=list)
    relatedDocuments: list[dict[str, object]] = Field(default_factory=list)
    notebookSummary: dict[str, object] | None = None
    memoryFacts: list[str] = Field(default_factory=list)
    contextPack: dict[str, object] | None = None
    judgmentBundle: dict[str, object] | None = None
    resolutionTrace: dict[str, object] | None = None
    stateProjection: dict[str, object] | None = None
    missingContext: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    sourceSummary: dict[str, int] = Field(default_factory=dict)
    answerPolicy: AnswerPolicyRecord = Field(default_factory=AnswerPolicyRecord)
    retrievalPlan: dict[str, object] = Field(default_factory=dict)
    quality: ContextQualityRecord = Field(default_factory=ContextQualityRecord)
    routeDecision: RouteDecisionRecord | None = None
    retrievalTrace: RetrievalTraceRecord | None = None


class DataCenterScopeRecord(BaseModel):
    page: PageContextPage
    scopeType: Literal[
        "client",
        "task",
        "meeting",
        "event_line",
        "project_module",
        "project_flow",
        "topic",
        "strategic_cockpit",
        "system",
    ]
    scopeId: str
    clientId: str | None = None
    taskId: str | None = None
    meetingId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    topicId: str | None = None


class DataCenterRequestRecord(BaseModel):
    scope: DataCenterScopeRecord
    prompt: str = ""
    mode: Literal["answer", "page_context", "search", "prep", "proposal", "diagnostic"] = "answer"
    includeRawEvidence: bool = False
    includeActionSuggestions: bool = False
    shadow: bool = True
    persistDrafts: bool = False
    persistQuality: bool = False
    workingDocumentIds: list[str] = Field(default_factory=list)


class AnswerPlanRecord(BaseModel):
    intent: PageIntentType = "general"
    answerShape: Literal[
        "open_answer",
        "direct_profile",
        "business_profile",
        "strategy_profile",
        "status_brief",
        "evidence_answer",
        "meeting_summary",
        "task_next_action",
        "official_registry",
        "candidate_judgment",
        "insufficient",
    ] = "open_answer"
    requiredSections: list[str] = Field(default_factory=list)
    mustStartWithDirectAnswer: bool = True
    mustCiteEvidence: bool = True
    mustDiscloseBoundary: bool = False
    allowCandidateJudgment: bool = True
    maxEvidenceItems: int = 12
    maxAnswerChars: int = 4200
    routeReason: str = ""


class AnswerMaterialRecord(BaseModel):
    directAnswerSeed: str = ""
    keyFacts: list[str] = Field(default_factory=list)
    structuredPoints: list[str] = Field(default_factory=list)
    evidenceHighlights: list[EvidenceItem] = Field(default_factory=list)
    stateHighlights: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    missingContext: list[str] = Field(default_factory=list)
    nextActions: list[str] = Field(default_factory=list)
    sourceLabels: list[str] = Field(default_factory=list)
    businessProfile: BusinessProfileSlotsRecord | None = None
    strategyProfile: StrategyProfileSlotsRecord | None = None


class BusinessProfileSlotsRecord(BaseModel):
    businessModules: list[str] = Field(default_factory=list)
    serviceObjects: list[str] = Field(default_factory=list)
    productsOrPrograms: list[str] = Field(default_factory=list)
    deliveryModel: list[str] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class StrategyProfileSlotsRecord(BaseModel):
    strategicDirections: list[str] = Field(default_factory=list)
    keyActions: list[str] = Field(default_factory=list)
    timeBoundary: str = ""
    risks: list[str] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class QuestionFocusFrameRecord(BaseModel):
    goal: QuestionFocusGoal = "explain"
    subjectFacet: QuestionFocusFacet = "general"
    depth: QuestionFocusDepth = "focused"
    suppressedExpansions: list[str] = Field(default_factory=list)
    preferredRoles: list[SemanticSourceRole] = Field(default_factory=list)
    discouragedRoles: list[SemanticSourceRole] = Field(default_factory=list)
    reasonTrace: list[str] = Field(default_factory=list)


class SourceReachabilityRecord(BaseModel):
    title: str
    path: str = ""
    documentId: str | None = None
    semanticRoles: list[SemanticSourceRole] = Field(default_factory=list)
    roleReasons: list[str] = Field(default_factory=list)
    sourcePresence: Literal["present", "missing"] = "present"
    sourceReachability: Literal[
        "indexed_primary",
        "reachable_support",
        "unreachable_local",
        "parse_failed",
        "state_pool",
        "missing",
    ] = "indexed_primary"
    sourceSelectionPool: Literal["included", "excluded", "not_applicable"] = "not_applicable"
    sourcePriorityReason: list[str] = Field(default_factory=list)
    sourceFinalDecision: Literal[
        "selected",
        "not_selected",
        "support_only",
        "parse_failed",
        "unreachable",
        "missing",
    ] = "not_selected"
    matchScore: float = 0.0


class EvidenceDecisionTraceRecord(BaseModel):
    title: str
    path: str = ""
    documentId: str | None = None
    semanticRoles: list[SemanticSourceRole] = Field(default_factory=list)
    roleReasons: list[str] = Field(default_factory=list)
    sourcePresence: Literal["present", "missing"] = "present"
    sourceReachability: Literal[
        "indexed_primary",
        "reachable_support",
        "unreachable_local",
        "parse_failed",
        "state_pool",
        "missing",
    ] = "indexed_primary"
    sourceSelectionPool: Literal["included", "excluded", "not_applicable"] = "included"
    sourcePriorityReason: list[str] = Field(default_factory=list)
    sourceFinalDecision: Literal["selected", "not_selected", "filtered_noise", "filtered_low_relevance"] = "not_selected"
    score: float = 0.0
    baseScore: float = 0.0


class EvidenceQualitySignalRecord(BaseModel):
    isNoise: bool = False
    noiseReasons: list[str] = Field(default_factory=list)
    sourceKind: Literal[
        "raw_document",
        "meeting_note",
        "meeting_decision",
        "meeting_action",
        "meeting_risk",
        "task_attachment",
        "judgment",
        "topic_candidate",
        "generated_answer",
        "memory_answer",
        "ppt_visual",
        "ppt_master",
        "template_page",
        "short_excerpt",
        "unknown",
    ] = "unknown"
    qualityScore: float = 0.0
    demotionScore: float = 0.0
    freshnessScore: float = 0.0
    authorityHint: Literal["raw", "state", "candidate", "generated", "unknown"] = "unknown"
    semanticRoles: list[SemanticSourceRole] = Field(default_factory=list)
    roleReasons: list[str] = Field(default_factory=list)


class EvidenceQualityAnnotationRecord(BaseModel):
    id: str
    sourceType: str
    sourceId: str
    documentId: str | None = None
    path: str | None = None
    excerptHash: str
    sourceKind: Literal[
        "raw_document",
        "meeting_note",
        "meeting_decision",
        "meeting_action",
        "meeting_risk",
        "task_attachment",
        "judgment",
        "topic_candidate",
        "generated_answer",
        "memory_answer",
        "ppt_visual",
        "ppt_master",
        "template_page",
        "short_excerpt",
        "unknown",
    ] = "unknown"
    qualityScore: float = 0.0
    demotionScore: float = 0.0
    noiseReasons: list[str] = Field(default_factory=list)
    authorityHint: Literal["raw", "state", "candidate", "generated", "unknown"] = "unknown"
    humanLabel: Literal["useful", "noise", "needs_review"] | None = None
    humanNote: str = ""
    createdAt: str
    updatedAt: str


class EvidenceQualityAnnotationLabelPayloadRecord(BaseModel):
    label: Literal["useful", "noise", "needs_review"]
    note: str = ""


class ActionSuggestionRecord(BaseModel):
    id: str
    actionType: Literal[
        "create_task",
        "create_proposal",
        "request_evidence",
        "refresh_context_pack",
        "confirm_candidate_judgment",
        "prepare_meeting",
        "record_handbook",
    ]
    title: str
    summary: str
    rationale: str
    riskLevel: Literal["low", "medium", "high"] = "low"
    requiresApproval: bool = False
    sourceRefs: list[str] = Field(default_factory=list)
    targetRefs: list["ProposalTargetRefRecord"] = Field(default_factory=list)


class AnswerQualityReportRecord(BaseModel):
    hasDirectAnswer: bool = False
    evidenceListOnly: bool = False
    evidenceQuoteOnly: bool = False
    leakedInternalMarkers: list[str] = Field(default_factory=list)
    candidateAsOfficialRisk: bool = False
    officialBoundaryViolation: bool = False
    missingRawEvidenceForIntent: bool = False
    offTopicRisk: bool = False
    factSlotHit: bool = False
    factSlotMissingReason: str | None = None
    grade: Literal["pass", "warn", "fail"] = "pass"
    reason: str = ""


class GenerationRuntimeStateRecord(BaseModel):
    clientId: str
    answerIntent: str
    provider: str | None = None
    model: str | None = None
    recentTotal: int = 0
    recentTimeouts: int = 0
    recentLocalFallbacks: int = 0
    recentSuccesses: int = 0
    stableFallbackActive: bool = False
    stableFallbackReason: str | None = None
    cooldownUntil: str | None = None
    updatedAt: str


class GenerationRuntimeDecisionRecord(BaseModel):
    shouldAttemptLlm: bool = True
    shouldUseCompactFirst: bool = False
    shouldUseLocalOnly: bool = False
    shouldQueueLongAnswerRetry: bool = False
    shouldProbeAfterCooldown: bool = False
    reason: str = ""
    cooldownActive: bool = False


class GenerationRuntimeResetPayloadRecord(BaseModel):
    clientId: str
    answerIntent: str = "general"
    provider: str | None = None
    model: str | None = None
    resetScope: Literal["client", "intent", "model"] = "intent"


class LlmHealthcheckPayloadRecord(BaseModel):
    provider: str | None = None
    model: str | None = None
    prompt: str | None = None


class LlmHealthcheckRecord(BaseModel):
    provider: str
    model: str
    success: bool
    latencyMs: int = 0
    error: str | None = None
    errorKind: Literal[
        "connect_timeout",
        "read_timeout",
        "ssl_handshake_timeout",
        "auth_error",
        "rate_limit",
        "unknown",
    ] | None = None


class LlmProviderProbePayloadRecord(BaseModel):
    clientId: str | None = None
    providers: list[str] = Field(default_factory=list)
    prompt: str | None = None


class LlmProviderProbeResultRecord(BaseModel):
    clientId: str | None = None
    prompt: str
    generatedAt: str
    results: list[LlmHealthcheckRecord] = Field(default_factory=list)


class EntityRecord(BaseModel):
    """迭代 2：跨文档实体（person / company / project / product / competitor /
    amount / date）。

    所有实体按 client_id 隔离。同 (client_id, entity_type, normalized_name)
    在 DB 层是 UNIQUE，二次入库只增 mention_count。
    """

    id: str
    clientId: str
    entityType: Literal[
        "person",
        "company",
        "project",
        "product",
        "competitor",
        "amount",
        "date",
    ]
    normalizedName: str
    displayName: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    mentionCount: int = 0
    confidence: float = 0.0
    firstSeenAt: str
    lastSeenAt: str
    status: Literal["active", "merged", "deleted"] = "active"


class EntityListResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/entities 响应。"""

    entities: list[EntityRecord] = Field(default_factory=list)
    total: int = 0


class EntityMergeCandidateRecord(BaseModel):
    """迭代 3：实体合并候选——两个相似实体的对。"""

    entityAId: str
    entityBId: str
    entityType: str
    nameA: str
    nameB: str
    mentionCountA: int = 0
    mentionCountB: int = 0
    similarity: float
    reason: str


class EntityMergeCandidatesResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/entity-merge-candidates 响应。"""

    candidates: list[EntityMergeCandidateRecord] = Field(default_factory=list)


class EntityMergePayload(BaseModel):
    """POST /api/v1/entities/{merged_id}/merge 请求。"""

    survivingEntityId: str
    mergeReason: str | None = None


class EntityMergeResultRecord(BaseModel):
    """POST /api/v1/entities/{merged_id}/merge 响应。"""

    mentionsMoved: int = 0
    triplesMoved: int = 0
    factsMoved: int = 0


class GlossaryEntryRecord(BaseModel):
    """迭代 7：客户私有术语。"""

    id: str
    clientId: str
    term: str
    normalizedTerm: str
    definition: str
    aliases: list[str] = Field(default_factory=list)
    category: str = ""
    createdAt: str
    updatedAt: str


class GlossaryListResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/glossary 响应。"""

    entries: list[GlossaryEntryRecord] = Field(default_factory=list)
    total: int = 0


class GlossaryCreatePayload(BaseModel):
    """POST /api/v1/clients/{id}/glossary 请求。"""

    term: str
    definition: str = ""
    aliases: list[str] = Field(default_factory=list)
    category: str = ""


class GlossaryUpdatePayload(BaseModel):
    """PATCH /api/v1/glossary/{id} 请求。"""

    term: str | None = None
    definition: str | None = None
    aliases: list[str] | None = None
    category: str | None = None


class StructuredTableSummaryRecord(BaseModel):
    """Phase 1：列表用，不含 rows。"""

    id: str
    clientId: str
    v2DocumentId: str
    sheetName: str
    sheetIndex: int
    headers: list[str] = Field(default_factory=list)
    columnTypes: dict[str, str] = Field(default_factory=dict)
    rowCount: int = 0
    columnCount: int = 0
    semanticRole: Literal[
        "budget",
        "beneficiary_list",
        "donation_record",
        "kpi",
        "schedule",
        "project_value",
        "unknown",
    ] = "unknown"
    semanticConfidence: float = 0.0
    parseNotes: list[str] = Field(default_factory=list)
    createdAt: str


class StructuredTableDetailRecord(StructuredTableSummaryRecord):
    """Phase 1：详情，含完整行数据。"""

    rows: list[dict] = Field(default_factory=list)


class StructuredTableListResponseRecord(BaseModel):
    tables: list[StructuredTableSummaryRecord] = Field(default_factory=list)
    total: int = 0


class StructuredQueryResultRecord(BaseModel):
    """Phase 1：对 structured_tables 跑计算后的单条结果。"""

    tableId: str
    sheetName: str
    semanticRole: str
    intent: Literal["list", "sum", "execution_rate", "overspend", "count"]
    summary: str
    markdown: str


class StructuredQueryResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/structured-query?q=... 响应。"""

    question: str
    results: list[StructuredQueryResultRecord] = Field(default_factory=list)


class RelationshipTripleRecord(BaseModel):
    """迭代 5：关系三元组。"""

    id: str
    clientId: str
    subjectEntityId: str
    subjectDisplayName: str
    predicate: str
    predicateLabel: str
    objectEntityId: str | None = None
    objectDisplayName: str | None = None
    objectText: str
    confidence: float = 0.0
    sourceV2ChunkId: str | None = None
    sourceV2DocumentId: str | None = None
    evidenceText: str = ""
    createdAt: str


class RelationshipListResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/relationships 响应。"""

    relationships: list[RelationshipTripleRecord] = Field(default_factory=list)
    total: int = 0


class FactContradictionRecord(BaseModel):
    """迭代 6：矛盾告警记录。"""

    id: str
    clientId: str
    subjectText: str
    attribute: str
    valueA: str
    valueB: str
    evidenceA: str
    evidenceB: str
    factAId: str
    factBId: str
    factAAt: str
    factBAt: str
    # 来源文件元信息（让用户能看清是哪两份资料冲突）
    docAFileName: str | None = None
    docAImportedAt: str | None = None
    docAOriginalPath: str | None = None
    docASizeBytes: int | None = None
    docBFileName: str | None = None
    docBImportedAt: str | None = None
    docBOriginalPath: str | None = None
    docBSizeBytes: int | None = None
    contradictionType: Literal["value_diff", "temporal", "scope"] = "value_diff"
    severity: Literal["low", "medium", "high"] = "medium"
    reviewStatus: Literal["pending", "dismissed", "resolved"] = "pending"
    resolutionNote: str | None = None
    detectedAt: str


class FactContradictionListResponseRecord(BaseModel):
    """GET /api/v1/clients/{id}/contradictions 响应。"""

    contradictions: list[FactContradictionRecord] = Field(default_factory=list)
    total: int = 0


class FactContradictionReviewPayload(BaseModel):
    """POST /api/v1/contradictions/{id}/review 请求。

    - 'resolved' + acceptedFactId：采纳某一份事实，另一份自动归档
    - 'dismissed'（不带 acceptedFactId）：视为误报或暂时忽略
    """

    reviewStatus: Literal["dismissed", "resolved"]
    acceptedFactId: str | None = None
    resolutionNote: str | None = None


class DataCenterSearchHitRecord(BaseModel):
    title: str
    excerpt: str
    sourceType: str
    documentId: str | None = None
    path: str | None = None
    originalPath: str | None = None
    managedPath: str | None = None
    markdownPath: str | None = None
    openableKind: Literal["original_file", "machine_markdown", "system_card", "unknown"] | None = None
    sourceAvailability: Literal["original_available", "machine_readable_only", "invalid_source", "unknown"] | None = None
    originalAvailable: bool | None = None
    machineReadableAvailable: bool | None = None
    openOriginalDisabledReason: str | None = None
    score: float | None = None
    sectionLabel: str | None = None
    retrievalStage: str | None = None
    selectedForAnswer: bool = False
    qualityFlags: list[str] = Field(default_factory=list)
    annotationId: str | None = None
    humanLabel: Literal["useful", "noise", "needs_review"] | None = None
    # 迭代 1 鲜度可视化：把 evidence_quality 算出的衰减后鲜度暴露到前端，
    # 让用户在引证面板就能看到"这条证据有多老/多新"。
    # createdAt 为 ISO 8601；docType 对应 freshness_decay.HALF_LIFE_BY_TYPE。
    freshnessScore: float | None = None
    createdAt: str | None = None
    docType: str | None = None
    # 迭代 2 F3：版本链信息（UI 显示 "v2 · 最新" 徽章）
    versionNumber: int | None = None
    versionChainId: str | None = None
    lifecycleStatus: Literal["current", "superseded", "deleted"] | None = None
    chainTotalVersions: int | None = None
    # 迭代 4：chunk 语义类型聚合到 doc 级（最多/置信度最高的代表性类型）
    semanticType: Literal[
        "fact",
        "judgment",
        "opinion",
        "action",
        "question",
        "conclusion",
        "background",
        "unclassified",
    ] | None = None
    semanticConfidence: float | None = None


class DataCenterSearchResultRecord(BaseModel):
    query: str
    routeDecision: RouteDecisionRecord
    retrievalTrace: RetrievalTraceRecord | None = None
    answerPlan: AnswerPlanRecord | None = None
    hits: list[DataCenterSearchHitRecord] = Field(default_factory=list)
    selectedHits: list[DataCenterSearchHitRecord] = Field(default_factory=list)
    missingContext: list[str] = Field(default_factory=list)
    suggestedFollowups: list[str] = Field(default_factory=list)


class DataCenterPrepSectionRecord(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)


class DataCenterPrepResultRecord(BaseModel):
    prepType: Literal["task", "meeting", "client_conversation"]
    title: str
    objective: str = ""
    knownFacts: list[str] = Field(default_factory=list)
    keyRisks: list[str] = Field(default_factory=list)
    openQuestions: list[str] = Field(default_factory=list)
    recommendedAgenda: list[str] = Field(default_factory=list)
    nextActions: list[str] = Field(default_factory=list)
    materials: list["PrepPackMaterialRecord"] = Field(default_factory=list)
    sections: list[DataCenterPrepSectionRecord] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)


class DataCenterProposalDraftRecord(BaseModel):
    id: str | None = None
    kind: Literal[
        "task_prep",
        "meeting_prep",
        "meeting_followup",
        "evidence_request",
        "judgment_review",
        "context_refresh",
    ]
    title: str
    summary: str
    rationale: str
    riskLevel: Literal["low", "medium", "high"] = "medium"
    targetRefs: list["ProposalTargetRefRecord"] = Field(default_factory=list)
    sourceRefs: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    requiresApproval: bool = True
    status: Literal["draft", "reviewed", "rejected", "promoted", "expired"] = "draft"
    dedupeKey: str | None = None
    sourcePrompt: str = ""
    scopeType: str | None = None
    scopeId: str | None = None
    clientId: str | None = None
    page: str | None = None
    mode: str = "proposal"
    reviewedAt: str | None = None
    rejectedAt: str | None = None
    rejectedReason: str | None = None
    promotedProposalId: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class ExternalEvidenceLiteRecord(BaseModel):
    sourceType: Literal["topic_candidate"] = "topic_candidate"
    sourceId: str
    title: str
    summary: str
    sourceUrl: str | None = None
    publishedAt: str | None = None
    confidence: float = 0.0
    relatedClientIds: list[str] = Field(default_factory=list)


class KnowledgeParseFailureRecord(BaseModel):
    documentId: str
    title: str
    path: str
    kind: str
    parseStatus: str
    error: str
    failureType: str = "unknown"
    recoverable: bool = False
    pageCount: int | None = None
    lastRetryAt: str | None = None
    recommendedAction: str


class KnowledgeParseFailureRetryPayloadRecord(BaseModel):
    documentIds: list[str] = Field(default_factory=list)
    force: bool = False
    ocrMaxPages: int = 60
    ocrBatchSize: int = 8
    ocrContinueToEnd: bool = True
    forceOcr: bool = False


class KnowledgeParseFailureRetryItemRecord(BaseModel):
    documentId: str
    title: str = ""
    status: Literal["succeeded", "failed", "skipped"]
    failureType: Literal[
        "file_missing",
        "empty_text",
        "empty_pdf",
        "unsupported_format",
        "ocr_required",
        "parser_exception",
        "permission_denied",
        "managed_path_missing",
        "unknown",
    ] | None = None
    message: str = ""


class KnowledgeParseFailureRetryResultRecord(BaseModel):
    batchId: str
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    failureBuckets: dict[str, int] = Field(default_factory=dict)
    items: list[KnowledgeParseFailureRetryItemRecord] = Field(default_factory=list)


class WorkspaceDocumentProcessingStatusRecord(BaseModel):
    documentId: str
    v2DocumentId: str | None = None
    knowledgeDocumentId: str | None = None
    title: str
    fileName: str
    kind: str
    materialLayer: str = "evidence"
    parseStatus: str = "queued"
    parseError: str | None = None
    parseErrorCategory: Literal[
        "file_missing",
        "permission_denied",
        "unsupported_format",
        "ocr_required",
        "empty_text",
        "empty_pdf",
        "parser_exception",
        "unknown",
    ] | None = None
    hasDocumentCard: bool = False
    hasSurrogate: bool = False
    hasMasterIndex: bool = False
    vectorStatus: str | None = None
    chunkCount: int = 0
    sectionCount: int = 0
    usedByLatestContextPack: bool = False
    lastHitAt: str | None = None
    updatedAt: str
    sourceAvailability: Literal["original_available", "machine_readable_only", "invalid_source", "unknown"] = "unknown"
    originalAvailable: bool = False
    machineReadableAvailable: bool = False
    openOriginalDisabledReason: str | None = None


class WorkspaceDataCenterReadinessSummaryRecord(BaseModel):
    totalDocuments: int = 0
    readyDocuments: int = 0
    partialReadyDocuments: int = 0
    parsingDocuments: int = 0
    queuedDocuments: int = 0
    runningDocuments: int = 0
    failedDocuments: int = 0
    invalidDocuments: int = 0
    sourceMissingDocuments: int = 0
    placeholderOnlyDocuments: int = 0
    autoRepairableDocuments: int = 0
    zeroByteDocuments: int = 0
    legacyFolderDocumentsWithoutV2: int = 0
    machineReadableOnlyDocuments: int = 0
    dedupeCandidateDocuments: int = 0
    orphanTaskCount: int = 0
    orphanEventLineCount: int = 0
    skippedOrphanClientIngestCount: int = 0
    parseFailureBuckets: dict[str, int] = Field(default_factory=dict)
    ocrRecoverableCount: int = 0
    documentCards: int = 0
    surrogates: int = 0
    masterIndexEntries: int = 0
    vectorReadyDocuments: int = 0
    vectorStatus: str = "unknown"
    vectorMasterIndexed: int = 0
    vectorChunkIndexed: int = 0
    latestContextPackAt: str | None = None
    contextQuality: str = "none"
    missingContextCount: int = 0
    refreshEventQueuedCount: int = 0
    refreshEventRunningCount: int = 0
    refreshEventFailedCount: int = 0
    internetEnrichmentStatus: str = "none"
    internetSourceCount: int = 0
    internetFactCardCount: int = 0
    remainingUserRequiredGaps: list[str] = Field(default_factory=list)
    lastInternetEnrichmentAt: str | None = None


class WorkspaceDataCenterReadinessJobEventRecord(BaseModel):
    jobId: str
    level: str
    message: str
    createdAt: str


class WorkspaceDataCenterReadinessRecentJobRecord(BaseModel):
    id: str
    jobType: str
    status: str
    processedItems: int = 0
    totalItems: int = 0
    lastError: str | None = None
    updatedAt: str


class WorkspaceDataCenterLocalOptimizationStatusRecord(BaseModel):
    enabled: bool = False
    paused: bool = False
    inWindow: bool = False
    nextWindowLabel: str | None = None
    modelProfileId: str = ""
    modelName: str = ""
    concurrency: int = 1
    queueTotal: int = 0
    queuedTasks: int = 0
    runningTasks: int = 0
    completedTasks: int = 0
    failedTasks: int = 0
    pendingDocumentCards: int = 0
    pendingPathOptimizations: int = 0
    appliedPathOptimizations: int = 0
    pendingPathConfirmations: int = 0
    lastCompletedAt: str | None = None
    lastError: str | None = None


class WorkspaceDataCenterReadinessJobsRecord(BaseModel):
    runningKnowledgeJobs: int = 0
    failedKnowledgeJobs: int = 0
    latestJobEvents: list[WorkspaceDataCenterReadinessJobEventRecord] = Field(default_factory=list)
    localOptimization: WorkspaceDataCenterLocalOptimizationStatusRecord | None = None


class WorkspaceDataCenterReadinessFixRecord(BaseModel):
    id: str
    label: str
    actionType: Literal[
        "retry_parse",
        "rebuild_client_knowledge",
        "regenerate_document_cards",
        "sync_master_index",
        "sync_vector_index",
        "refresh_context_pack",
        "inspect_failed_documents",
        "cleanup_invalid_documents",
        "rebind_original_file",
        "auto_repair_documents",
        "enqueue_local_model_optimization",
        "retry_local_model_optimization",
        "internet_enrichment",
    ]
    severity: Literal["info", "warning", "critical"] = "info"
    reason: str = ""
    targetIds: list[str] = Field(default_factory=list)
    estimatedImpact: str = ""


class WorkspaceDataCenterReadinessRecord(BaseModel):
    clientId: str
    generatedAt: str
    summary: WorkspaceDataCenterReadinessSummaryRecord
    documents: list[WorkspaceDocumentProcessingStatusRecord] = Field(default_factory=list)
    jobs: WorkspaceDataCenterReadinessJobsRecord = Field(default_factory=WorkspaceDataCenterReadinessJobsRecord)
    recommendedFixes: list[WorkspaceDataCenterReadinessFixRecord] = Field(default_factory=list)
    recentJobs: list[WorkspaceDataCenterReadinessRecentJobRecord] = Field(default_factory=list)
    recentRefreshEvents: list["WorkspaceContextRefreshEventRecord"] = Field(default_factory=list)


class WorkspaceDataCenterReadinessActionPayloadRecord(BaseModel):
    actionType: Literal[
        "retry_parse",
        "rebuild_client_knowledge",
        "regenerate_document_cards",
        "sync_master_index",
        "sync_vector_index",
        "refresh_context_pack",
        "inspect_failed_documents",
        "cleanup_invalid_documents",
        "rebind_original_file",
        "auto_repair_documents",
        "enqueue_local_model_optimization",
        "retry_local_model_optimization",
        "internet_enrichment",
    ]
    targetIds: list[str] = Field(default_factory=list)
    reason: str = ""
    seedUrls: list[str] = Field(default_factory=list)
    seedQueries: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    maxPages: int = 30
    maxDepth: int = 2
    targetType: str = "client"
    targetId: str | None = None
    title: str = ""
    ocrMaxPages: int = 60
    ocrBatchSize: int = 8
    ocrContinueToEnd: bool = True
    forceOcr: bool = False


class WorkspaceDataCenterReadinessActionResultRecord(BaseModel):
    actionType: str
    status: Literal["queued", "running", "completed", "failed"] = "completed"
    jobId: str | None = None
    refreshEventId: str | None = None
    affectedCount: int = 0
    message: str = ""
    errors: list[str] = Field(default_factory=list)


class WorkspaceContextRefreshEnqueuePayloadRecord(BaseModel):
    sourceType: str
    sourceId: str | None = None
    reason: str
    scopeType: Literal["client", "task", "meeting", "event_line", "project_module", "project_flow", "strategic_cockpit"] = "client"
    scopeId: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"


class WorkspaceContextRefreshEventRecord(BaseModel):
    id: str
    clientId: str
    scopeType: str
    scopeId: str
    sourceType: str
    sourceId: str | None = None
    reason: str
    priority: Literal["low", "normal", "high"] = "normal"
    status: Literal["queued", "running", "completed", "failed", "canceled"] = "queued"
    jobId: str | None = None
    dedupeKey: str
    error: str | None = None
    createdAt: str
    updatedAt: str


class WorkspaceContextRefreshEnqueueResultRecord(BaseModel):
    event: WorkspaceContextRefreshEventRecord
    deduped: bool = False


class WorkspaceProposalDraftCreatePayloadRecord(BaseModel):
    sourceMessageId: str | None = None
    sourceType: Literal["action_suggestion", "proposal_draft", "manual"] = "manual"
    actionSuggestionId: str | None = None
    sourceMessageDraftId: str | None = None
    sourceMessageDraftPayload: dict[str, object] = Field(default_factory=dict)
    kind: Literal[
        "task_prep",
        "meeting_prep",
        "meeting_followup",
        "evidence_request",
        "judgment_review",
        "context_refresh",
    ]
    title: str
    summary: str
    rationale: str = ""
    riskLevel: Literal["low", "medium", "high"] = "medium"
    targetRefs: list["ProposalTargetRefRecord"] = Field(default_factory=list)
    sourceRefs: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    scopeType: Literal["client", "task", "meeting", "event_line", "project_module", "project_flow", "strategic_cockpit"] = "client"
    scopeId: str | None = None


class DiagnosticsBucketRecord(BaseModel):
    status: Literal["ok", "warning", "critical"] = "ok"
    details: dict[str, object] = Field(default_factory=dict)


class WorkspaceChatDiagnosticsRecord(BaseModel):
    clientId: str
    recentMessages: int = 0
    groundedFallbackRate: float = 0.0
    llmTimeoutRate: float = 0.0
    sourceIntegrityMatch: bool | None = None
    runningBuildVersion: str | None = None
    expectedBuildVersion: str | None = None
    dominantLlmErrorKind: str | None = None
    fallbackTemplateUsedRate: float = 0.0
    dataCenterPrimaryEnabledRate: float = 0.0
    partialPreservedRate: float = 0.0
    systemFailureRate: float = 0.0
    stableFallbackActive: bool = False
    stableFallbackReason: str | None = None
    avgRetrievalMs: float = 0.0
    avgLlmMs: float = 0.0
    intentDistribution: dict[str, int] = Field(default_factory=dict)
    materialQuality: dict[str, float] = Field(default_factory=dict)
    dataCenterQuality: dict[str, object] = Field(default_factory=dict)
    breakdown: dict[str, DiagnosticsBucketRecord] = Field(default_factory=dict)
    rootCauseSummary: list[str] = Field(default_factory=list)
    recommendedFixes: list[str] = Field(default_factory=list)
    kernelP95Ms: float = 0.0
    kernelSlowRunCount: int = 0
    kernelSlowestStage: str | None = None


class WorkspaceAnswerFinalizationRecord(BaseModel):
    content: str
    answerMode: Literal["grounded_answer", "grounded_fallback", "low_confidence_answer", "general_answer", "system_failure"]
    failureReason: str | None = None
    fallbackPresentationMode: Literal["state_cards_only", "compact_user_answer", "full_answer"] | None = None
    userVisibleQualityStatus: Literal["ready", "usable_with_boundary", "degraded", "needs_retry"] = "ready"
    shouldShowRetryBanner: bool = False
    qualityGrade: Literal["pass", "warn", "fail"] = "pass"
    internalGenerationStatus: str = ""
    notes: list[str] = Field(default_factory=list)


class WorkspaceAnswerEvidenceChipRecord(BaseModel):
    id: str = ""
    title: str = ""
    sourceType: str = ""
    sourceKind: str = ""
    excerpt: str = ""
    qualityLabel: Literal["high", "medium", "low", "noise"] = "medium"
    documentId: str | None = None
    path: str | None = None


class WorkspaceAnswerActionCardRecord(BaseModel):
    actionType: Literal[
        "create_proposal",
        "create_task",
        "request_evidence",
        "review_judgment",
        "refresh_context",
        "prepare_meeting",
    ]
    title: str
    summary: str = ""
    riskLevel: Literal["low", "medium", "high"] = "medium"
    draftId: str | None = None
    proposalId: str | None = None
    enabled: bool = True
    disabledReason: str = ""


class WorkspaceAnswerExperienceRecord(BaseModel):
    status: Literal["ready", "usable_with_boundary", "degraded", "needs_retry"] = "ready"
    headline: str = ""
    directAnswer: str = ""
    keyPoints: list[str] = Field(default_factory=list)
    evidenceChips: list[WorkspaceAnswerEvidenceChipRecord] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    nextActions: list[str] = Field(default_factory=list)
    actionCards: list[WorkspaceAnswerActionCardRecord] = Field(default_factory=list)
    trustSignals: list[str] = Field(default_factory=list)
    userMessage: str = ""


class WorkspaceAnswerValueTopItemRecord(BaseModel):
    key: str
    count: int = 0


class WorkspaceAnswerValueDiagnosticsRecord(BaseModel):
    clientId: str
    recentMessages: int = 0
    answerModeDistribution: dict[str, int] = Field(default_factory=dict)
    fallbackReasonDistribution: dict[str, int] = Field(default_factory=dict)
    fallbackPresentationModeDistribution: dict[str, int] = Field(default_factory=dict)
    retryBannerWouldShowCount: int = 0
    retryBannerWouldShowRate: float = 0.0
    lowConfidenceCount: int = 0
    groundedFallbackCount: int = 0
    groundedAnswerCount: int = 0
    usableAnswerCount: int = 0
    usableAnswerRate: float = 0.0
    readyOrUsableCount: int = 0
    readyOrUsableRate: float = 0.0
    needsRetryCount: int = 0
    needsRetryRate: float = 0.0
    degradedCount: int = 0
    degradedRate: float = 0.0
    kernelPrimaryUsedCount: int = 0
    kernelPrimaryFallbackUsedCount: int = 0
    kernelPrimaryUsedRate: float = 0.0
    llmTimeoutCount: int = 0
    llmTimeoutRate: float = 0.0
    answerQualityPassCount: int = 0
    answerQualityFailCount: int = 0
    groundedAnswerPassRate: float = 0.0
    officialBoundaryViolationCount: int = 0
    candidateBoundaryViolationCount: int = 0
    avgSelectedEvidenceCount: float = 0.0
    evidenceSupportedCount: int = 0
    evidenceSupportedRate: float = 0.0
    businessSlotAnswerCount: int = 0
    businessSlotAnswerRate: float = 0.0
    strategySlotAnswerCount: int = 0
    strategySlotAnswerRate: float = 0.0
    answerTooShortCount: int = 0
    answerTooShortRate: float = 0.0
    answerTooTemplateLikeCount: int = 0
    answerTooTemplateLikeRate: float = 0.0
    topFailureReasons: list[WorkspaceAnswerValueTopItemRecord] = Field(default_factory=list)
    recommendedFixes: list[str] = Field(default_factory=list)
    metricErrors: list[str] = Field(default_factory=list)


class WorkspaceAnswerValueReviewPayloadRecord(BaseModel):
    clientId: str
    messageId: str
    prompt: str = ""
    answerMode: str = ""
    userVisibleQualityStatus: Literal["ready", "usable_with_boundary", "degraded", "needs_retry"] = "ready"
    shouldShowRetryBanner: bool = False
    usableAnswer: bool | None = None
    reviewerNote: str = ""
    manualBaselineMinutes: float | None = None
    dataCenterReviewMinutes: float | None = None


class WorkspaceAnswerValueReviewRecord(BaseModel):
    id: str
    clientId: str
    messageId: str
    prompt: str
    answerMode: str
    userVisibleQualityStatus: Literal["ready", "usable_with_boundary", "degraded", "needs_retry"] = "ready"
    shouldShowRetryBanner: bool = False
    usableAnswer: bool | None = None
    reviewerNote: str = ""
    manualBaselineMinutes: float | None = None
    dataCenterReviewMinutes: float | None = None
    savedMinutes: float | None = None
    createdAt: str


class WorkspaceAnswerValueSummaryRecord(BaseModel):
    clientId: str
    reviewCount: int = 0
    usableAnswerRate: float = 0.0
    retryBannerRate: float = 0.0
    averageManualBaselineMinutes: float = 0.0
    averageDataCenterReviewMinutes: float = 0.0
    estimatedTimeSavedRate: float = 0.0
    positiveReviewCount: int = 0
    negativeReviewCount: int = 0
    lastReviewedAt: str | None = None
    proposalCreatedFromAnswerCount: int = 0
    executionTicketCreatedFromAnswerCount: int = 0
    metricErrors: list[str] = Field(default_factory=list)


class WorkspaceValueValidationQuestionRecord(BaseModel):
    id: str
    prompt: str


class WorkspaceValueValidationSessionSummaryRecord(BaseModel):
    sessionId: str = ""
    clientId: str = ""
    completed: int = 0
    usableAnswerRate: float = 0.0
    estimatedTimeSavedRate: float = 0.0
    retryBannerRate: float = 0.0
    proposalCreatedCount: int = 0
    executionTicketCreatedCount: int = 0
    verdict: Literal["pass", "hold", "fail"] = "hold"


class WorkspaceValueValidationSessionRecord(BaseModel):
    id: str
    clientId: str
    status: Literal["running", "completed", "failed"] = "running"
    questionSet: list[WorkspaceValueValidationQuestionRecord] = Field(default_factory=list)
    completedQuestionIds: list[str] = Field(default_factory=list)
    summary: WorkspaceValueValidationSessionSummaryRecord = Field(default_factory=WorkspaceValueValidationSessionSummaryRecord)
    createdAt: str
    updatedAt: str


class WorkspaceValueValidationSessionCreatePayloadRecord(BaseModel):
    clientId: str


class WorkspaceValueValidationSessionCompleteQuestionPayloadRecord(BaseModel):
    questionId: str
    reviewId: str | None = None
    messageId: str | None = None
    usableAnswer: bool | None = None
    retryBannerShown: bool | None = None
    manualBaselineMinutes: float | None = None
    dataCenterReviewMinutes: float | None = None
    proposalCreated: bool = False
    executionTicketCreated: bool = False
    reviewerNote: str = ""


class WorkspaceAnswerActionCardResultRecord(BaseModel):
    messageId: str
    actionType: str
    status: Literal["created", "reused"] = "created"
    summary: str = ""
    draftId: str | None = None
    proposalId: str | None = None
    taskId: str | None = None
    autoApproved: bool = False
    autoExecuted: bool = False


class WorkspaceAnswerQualityFailureRecord(BaseModel):
    id: str
    clientId: str
    messageId: str | None = None
    prompt: str = ""
    failureType: Literal[
        "retry_banner",
        "too_template_like",
        "no_evidence",
        "no_direct_answer",
        "boundary_violation",
        "kernel_not_used",
        "answer_too_short",
        "user_marked_not_usable",
    ]
    severity: Literal["low", "medium", "high"] = "medium"
    details: dict[str, object] = Field(default_factory=dict)
    status: Literal["open", "resolved"] = "open"
    createdAt: str
    updatedAt: str


class WorkspaceAnswerQualityFailureResolvePayloadRecord(BaseModel):
    note: str = ""


class DataCenterCandidateChainRecord(BaseModel):
    routeDecision: RouteDecisionRecord
    selectedEvidence: list[EvidenceItem] = Field(default_factory=list)
    searchHits: list[DataCenterSearchHitRecord] = Field(default_factory=list)
    answerPlan: AnswerPlanRecord | None = None
    answerMaterial: AnswerMaterialRecord | None = None
    answerQuality: dict[str, object] = Field(default_factory=dict)
    actionSuggestions: list[ActionSuggestionRecord] = Field(default_factory=list)
    questionFocusFrame: QuestionFocusFrameRecord | None = None
    evidenceDecisionTrace: list[EvidenceDecisionTraceRecord] = Field(default_factory=list)
    selectedEvidenceRoles: list[SemanticSourceRole] = Field(default_factory=list)
    unselectedHighPrioritySources: list[dict[str, object]] = Field(default_factory=list)
    sourceReachability: dict[str, object] = Field(default_factory=dict)
    failed: bool = False
    failureReason: str | None = None


class DataCenterProposalDraftRejectPayloadRecord(BaseModel):
    reason: str = ""


class DataCenterProposalDraftReviewPayloadRecord(BaseModel):
    note: str = ""


class DataCenterProposalDraftPromotePayloadRecord(BaseModel):
    createdBy: str = "data_center"
    note: str = ""
    promoteTo: Literal[
        "proposal",
        "proposal_record",
        "task",
        "evidence_request",
        "meeting_prep",
        "judgment_confirmation",
        "context_refresh",
    ] | None = None
    options: dict[str, object] = Field(default_factory=dict)


class DataCenterProposalDraftPromoteResponseRecord(BaseModel):
    draft: DataCenterProposalDraftRecord
    proposalId: str | None = None
    taskId: str | None = None
    refreshEventId: str | None = None
    effectType: Literal[
        "proposal",
        "proposal_record",
        "task",
        "evidence_request",
        "meeting_prep",
        "judgment_confirmation",
        "context_refresh",
    ] = "proposal_record"


class DataCenterKernelResultRecord(BaseModel):
    scope: DataCenterScopeRecord
    pageContext: PageContextPackRecord | None = None
    routeDecision: RouteDecisionRecord | None = None
    retrievalTrace: RetrievalTraceRecord | None = None
    answerPlan: AnswerPlanRecord | None = None
    answerMaterial: AnswerMaterialRecord | None = None
    searchResult: DataCenterSearchResultRecord | None = None
    prepResult: DataCenterPrepResultRecord | None = None
    proposalDrafts: list[DataCenterProposalDraftRecord] = Field(default_factory=list)
    persistedProposalDraftIds: list[str] = Field(default_factory=list)
    dedupedDraftIds: list[str] = Field(default_factory=list)
    actionSuggestions: list[ActionSuggestionRecord] = Field(default_factory=list)
    quality: ContextQualityRecord | None = None
    debug: dict[str, object] = Field(default_factory=dict)


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


class ExternalEvidenceCardRecord(BaseModel):
    id: str
    sourceUrl: str
    sourceDomain: str
    sourceTier: Literal["official", "trusted_media", "partner", "unknown"] = "unknown"
    title: str
    publishedAt: str | None = None
    factExcerpt: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    relatedScopeType: str
    relatedScopeId: str
    confidence: float = 0.0
    status: Literal["candidate", "accepted", "rejected"] = "candidate"
    reviewedBy: str | None = None
    reviewedAt: str | None = None
    reviewNote: str = ""
    linkedProposalIds: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


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
    kind: Literal[
        "task_prep",
        "meeting_prep",
        "meeting_followup",
        "evidence_request",
        "judgment_review",
        "context_refresh",
    ]
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
    idempotencyKey: str | None = None
    retryCount: int = 0
    maxRetries: int = 3
    lastError: str | None = None
    lastAttemptAt: str | None = None
    errorMessage: str | None = None
    executedAt: str | None = None
    createdAt: str
    updatedAt: str


class ExecutionTicketLogRecord(BaseModel):
    id: str
    ticketId: str
    stage: Literal["validate", "prepare_payload", "execute_action", "write_result", "update_proposal_status", "retry"]
    status: Literal["started", "success", "failed"]
    message: str = ""
    payload: dict[str, object] = Field(default_factory=dict)
    createdAt: str


class ProposalDecisionPayload(BaseModel):
    comment: str = ""


class ProposalApprovalPayloadRecord(BaseModel):
    decidedBy: str = "user"
    note: str = ""
    comment: str | None = None


class ProposalExecutionPayloadRecord(BaseModel):
    requestedBy: str = "user"
    dryRun: bool = False


class ProposalExecutionPreviewRecord(BaseModel):
    proposalId: str
    executionType: str
    riskLevel: Literal["low", "medium", "high"] = "medium"
    willCreateTask: bool = False
    willCreatePrepArtifact: bool = False
    willCreateEvidenceRequest: bool = False
    willUpdateEventLine: bool = False
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class ProposalApprovalResultRecord(BaseModel):
    proposal: ProposalRecordRecord
    executionPreview: ProposalExecutionPreviewRecord | None = None


class ProposalExecutionResultRecord(BaseModel):
    proposal: ProposalRecordRecord
    executionTicket: ExecutionTicketRecord | None = None


class ProposalExecutionResponse(BaseModel):
    proposal: ProposalRecordRecord
    executionTicket: ExecutionTicketRecord | None = None


class ProposalBatchActionPayloadRecord(BaseModel):
    proposalIds: list[str] = Field(default_factory=list)
    decidedBy: str = "user"
    note: str = ""


class ProposalBatchResultRecord(BaseModel):
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    failedIds: list[str] = Field(default_factory=list)


class KernelPrimaryRolloutStartPayloadRecord(BaseModel):
    stage: Literal["stage_1_client", "stage_3_clients", "stage_10_clients"]
    clientIds: list[str] = Field(default_factory=list)
    note: str = ""


class KernelPrimaryRolloutRollbackPayloadRecord(BaseModel):
    reason: str = ""


class KernelPrimaryRolloutRunRecord(BaseModel):
    id: str
    stage: Literal["stage_1_client", "stage_3_clients", "stage_10_clients"]
    clientIds: list[str] = Field(default_factory=list)
    status: Literal["planned", "running", "completed", "rolled_back", "failed"] = "planned"
    metricsBefore: dict[str, object] = Field(default_factory=dict)
    metricsAfter: dict[str, object] = Field(default_factory=dict)
    verdict: Literal["pass", "fail", "watch"] | None = None
    recommendedAction: Literal["keep", "rollback"] | None = None
    note: str = ""
    rollbackReason: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None
    createdAt: str
    updatedAt: str


class ExecutionRetryMetricTopItemRecord(BaseModel):
    key: str
    count: int = 0


class ExecutionRetryMetricAlertRecord(BaseModel):
    level: Literal["info", "warning", "critical"] = "info"
    message: str


class ExecutionRetryMetricsRecord(BaseModel):
    windowDays: int = 7
    totalTickets: int = 0
    failedTickets: int = 0
    retriedTickets: int = 0
    retryExhaustedTickets: int = 0
    retrySuccessRate: float = 0.0
    avgRetryCount: float = 0.0
    oldestFailedTicketAgeHours: float = 0.0
    failureReasonTopN: list[ExecutionRetryMetricTopItemRecord] = Field(default_factory=list)
    failedStageTopN: list[ExecutionRetryMetricTopItemRecord] = Field(default_factory=list)
    alerts: list[ExecutionRetryMetricAlertRecord] = Field(default_factory=list)


class EvidenceQualityFeedbackSnapshotCreatePayloadRecord(BaseModel):
    days: int = Field(default=7, ge=1, le=90)


class EvidenceQualityFeedbackSnapshotRecord(BaseModel):
    id: str
    windowStart: str
    windowEnd: str
    labelCounts: dict[str, int] = Field(default_factory=dict)
    usefulExamples: list[dict[str, object]] = Field(default_factory=list)
    noiseExamples: list[dict[str, object]] = Field(default_factory=list)
    needsReviewExamples: list[dict[str, object]] = Field(default_factory=list)
    recommendedRules: list[str] = Field(default_factory=list)
    createdAt: str


class DataCenterRollbackDrillPayloadRecord(BaseModel):
    clientIds: list[str] = Field(default_factory=list)
    dryRun: bool = True


class DataCenterRollbackDrillResultRecord(BaseModel):
    dryRun: bool = True
    wouldDisableWorkspacePrimary: bool = True
    wouldDisableChatKernelPrimary: bool = True
    wouldClearAllowlist: bool = True
    wouldKeepDrafts: bool = True
    wouldKeepExecutionTickets: bool = True
    wouldKeepEvidenceLabels: bool = True
    warnings: list[str] = Field(default_factory=list)
    affectedClientIds: list[str] = Field(default_factory=list)
    applied: bool = False


class DataCenterOperationalStatusRecord(BaseModel):
    fullRegressionVerdict: Literal["pass", "fail", "hold", "unknown"] = "unknown"
    p22StrictPass: bool = False
    p23StrictPass: bool = False
    rolloutStage: str = "not_started"
    rolloutLatestVerdict: str = "hold"
    retryAlerts: list[str] = Field(default_factory=list)
    latestSnapshotAt: str | None = None
    rollbackDrillPass: bool = False
    releaseReportVerdict: Literal["pass", "fail", "hold", "unknown"] = "unknown"
    blockingIssues: list[str] = Field(default_factory=list)


class DataCenterArtifactStatusItemRecord(BaseModel):
    key: str
    label: str
    path: str = ""
    exists: bool = False
    verdict: Literal["pass", "fail", "hold", "unknown"] = "unknown"
    stale: bool = True
    generatedAt: str | None = None
    gitCommit: str | None = None
    backendBuildHash: str | None = None
    runtimeMode: str | None = None
    dataDir: str | None = None
    sourceRunId: str | None = None
    blockingIssues: list[str] = Field(default_factory=list)


class DataCenterArtifactStatusRecord(BaseModel):
    generatedAt: str
    overallPass: bool = False
    items: list[DataCenterArtifactStatusItemRecord] = Field(default_factory=list)


class DataCenterSchemaStatusRecord(BaseModel):
    generatedAt: str
    ensuredTables: list[str] = Field(default_factory=list)
    missingTables: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    permissionDiagnostics: dict[str, int] = Field(default_factory=dict)


class DigitalAssetMetricRecord(BaseModel):
    key: str
    label: str
    value: int = 0
    hint: str = ""


class DigitalAssetSourceRefRecord(BaseModel):
    sourceType: str
    sourceId: str
    title: str
    excerpt: str = ""
    updatedAt: str | None = None


class DigitalAssetInsightRecord(BaseModel):
    dimensionKey: str
    title: str
    summary: str
    evidenceCount: int = 0


class DigitalAssetDepositSuggestionRecord(BaseModel):
    priority: Literal["high", "medium", "low"] = "medium"
    dimensionKey: str
    title: str
    reason: str
    examples: list[str] = Field(default_factory=list)
    expectedGain: int = 0
    analysisValueUnlocked: str = ""
    suggestedDocumentContent: list[str] = Field(default_factory=list)
    sourceHighlights: list[str] = Field(default_factory=list)


class DigitalAssetScoreBreakdownRecord(BaseModel):
    deposited: int = 0
    understood: int = 0
    computable: int = 0
    compounding: int = 0
    structuralCompleteness: int = 0
    evidenceChain: int = 0
    timeContinuity: int = 0
    resultFeedbackLoop: int = 0


class DigitalAssetMaterialMaturityRowRecord(BaseModel):
    key: str
    label: str
    percent: int = 0
    level: str = "资料归档期"
    seenSummary: str = ""
    missingSummary: str = ""
    suggestedAction: str = ""
    unlockedValue: str = ""
    sourceHighlights: list[str] = Field(default_factory=list)


class DigitalAssetPulseFunnelItemRecord(BaseModel):
    key: str
    label: str
    value: int = 0


class DigitalAssetPulseOrganizationRecord(BaseModel):
    clientId: str
    name: str
    assetProfileType: str = ""
    maturityScore: int = 0
    depositThickness: int = 0
    weeklyNewFacts: int = 0
    weeklyNewDocuments: int = 0
    weeklyNewEvidenceCards: int = 0
    summary: str = ""


class DigitalAssetPulseSignalRecord(BaseModel):
    clientId: str | None = None
    name: str = ""
    title: str = ""
    summary: str = ""
    assetProfileType: str = ""
    maturityScore: int = 0
    severity: Literal["info", "warning", "critical"] = "info"


class DigitalAssetPulseRecord(BaseModel):
    headline: str = ""
    daysAccompanied: int = 0
    weeklyNewFacts: int = 0
    weeklyNewDocuments: int = 0
    weeklyNewEvidenceCards: int = 0
    weeklyNewJudgments: int = 0
    digestionFunnel: list[DigitalAssetPulseFunnelItemRecord] = Field(default_factory=list)
    activeOrganizations: list[DigitalAssetPulseOrganizationRecord] = Field(default_factory=list)
    learningHighlights: list[DigitalAssetPulseSignalRecord] = Field(default_factory=list)
    assetAlerts: list[DigitalAssetPulseSignalRecord] = Field(default_factory=list)


# --- 战略陪伴 · 客户脉搏 (Phase 1 克制版主页) ---

class StrategicPulseEventRecord(BaseModel):
    """本周新动态 - 一条 evidence-driven 事件."""
    title: str
    occurredAt: str = ""
    impact: Literal["advance", "neutral", "block"] = "neutral"
    sourceType: str = ""
    sourceId: str = ""
    sourceLabel: str = ""


class StrategicPulseTodoRecord(BaseModel):
    """你接下来要做 - 待办任务."""
    title: str
    dueDate: str | None = None
    daysUntilDue: int | None = None
    urgency: Literal["overdue", "today", "this_week", "later"] = "later"
    sourceTaskId: str | None = None
    eventLineId: str | None = None
    eventLineName: str = ""


class StrategicPulseBlockerRecord(BaseModel):
    """当前卡点 - 主线层面的阻塞或长期无活动."""
    title: str
    reason: str = ""
    stuckDays: int = 0
    eventLineId: str
    suggestedAction: str = ""


class StrategicPulseRecord(BaseModel):
    """客户战略脉搏 - 战略陪伴克制版主页主数据."""
    clientId: str
    weekStart: str = ""
    weekEnd: str = ""
    weeklyEvents: list[StrategicPulseEventRecord] = Field(default_factory=list)
    upcomingTodos: list[StrategicPulseTodoRecord] = Field(default_factory=list)
    currentBlockers: list[StrategicPulseBlockerRecord] = Field(default_factory=list)
    generatedAt: str = ""


class ClientPulseSummaryRecord(BaseModel):
    """单客户本周脉搏摘要 - 用于本周概览顶部客户脉搏区块."""
    clientId: str
    clientName: str
    clientStage: str = ""
    weeklyNewDocumentCount: int = 0
    weeklyNewTaskCount: int = 0
    weeklyNewEvidenceCount: int = 0
    currentBlockerCount: int = 0
    overdueTodoCount: int = 0
    hasActivity: bool = False
    topSignal: str = ""


class ClientsPulseSummaryResponse(BaseModel):
    """所有客户的本周脉搏摘要列表."""
    summaries: list[ClientPulseSummaryRecord] = Field(default_factory=list)
    generatedAt: str = ""


# --- 软件模块 DNA (Phase 1.5 跨 session 长期记忆) ---

class ModuleDnaEntryRecord(BaseModel):
    """单条 DNA entry. 多条共存不覆盖. isUserQuote=True 表示用户原话引用."""
    id: str
    moduleId: str
    category: str
    content: str
    isUserQuote: bool = False
    sourceThread: str = ""
    sourceSession: str = ""
    confidence: float = 0.7
    tags: list[str] = Field(default_factory=list)
    supersededBy: str | None = None
    createdAt: str


class ModuleDnaRecord(BaseModel):
    """模块定义 (壳) + 该模块下的所有 entries."""
    id: str
    level: int
    parentId: str | None = None
    displayName: str
    summary: str = ""
    entries: list[ModuleDnaEntryRecord] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ModuleDnaListResponse(BaseModel):
    modules: list[ModuleDnaRecord] = Field(default_factory=list)
    generatedAt: str = ""


class ModuleDnaCreateModulePayload(BaseModel):
    id: str
    level: int
    displayName: str
    summary: str = ""
    parentId: str | None = None


class ModuleDnaUpdateModulePayload(BaseModel):
    displayName: str | None = None
    summary: str | None = None


class ModuleDnaAppendEntryPayload(BaseModel):
    category: str
    content: str
    isUserQuote: bool = False
    sourceThread: str = ""
    sourceSession: str = ""
    confidence: float = 0.7
    tags: list[str] = Field(default_factory=list)


# --- 战略陪伴 · 事实澄清面板 (Phase 1.5 升级 ContradictionsTab) ---

class ClarificationProfileRecord(BaseModel):
    name: str = ""
    alias: str = ""
    domain: str = ""
    type: str = ""
    intro: str = ""
    stage: str = ""
    color: str = "#5B7BFE"
    industry: str = ""
    scale: str = ""
    influence: str = ""
    currentNeeds: str = ""
    painPoints: str = ""
    strategicValueToYiyu: str = ""
    decisionChain: str = ""
    cooperationType: str = ""
    relationshipHealth: str = ""
    milestones: str = ""
    cooperationStartedAt: str = ""


class ClarificationEventLineRecord(BaseModel):
    id: str
    name: str
    kind: str = ""
    status: str = ""
    stage: str = ""
    summary: str = ""
    intent: str = ""
    nextStep: str = ""
    currentBlocker: str = ""
    recentDecision: str = ""
    businessCategory: str = ""
    ownerId: str = ""
    ownerName: str = ""
    evidenceCount: int = 0
    createdAt: str = ""
    updatedAt: str = ""
    closedAt: str = ""
    isDirtyName: bool = False


class ClarificationTimelineRecord(BaseModel):
    id: str
    eventLineId: str = ""
    eventLineName: str = ""
    happenedAt: str = ""
    sourceType: str = ""
    actorName: str = ""
    title: str = ""
    summary: str = ""
    isKey: bool = False


class ClarificationPersonRecord(BaseModel):
    name: str
    mentionCount: int = 0
    sources: list[str] = Field(default_factory=list)


class ClarificationCommitmentRecord(BaseModel):
    id: str
    title: str = ""
    ownerName: str = ""
    dueDate: str = ""
    confidence: float = 0.0
    publishStatus: str = ""
    meetingId: str = ""
    meetingTitle: str = ""
    meetingScheduledAt: str = ""
    createdAt: str = ""


class ClarificationNeedRecord(BaseModel):
    eventLineId: str
    eventLineName: str = ""
    missingFields: list[str] = Field(default_factory=list)
    predictionReadiness: float = 0.0
    confidence: float = 0.0
    updatedAt: str = ""


class ClarificationContextResponse(BaseModel):
    clientId: str
    profile: ClarificationProfileRecord
    eventLines: list[ClarificationEventLineRecord] = Field(default_factory=list)
    timeline: list[ClarificationTimelineRecord] = Field(default_factory=list)
    peopleCandidates: list[ClarificationPersonRecord] = Field(default_factory=list)
    commitments: list[ClarificationCommitmentRecord] = Field(default_factory=list)
    clarificationNeeds: list[ClarificationNeedRecord] = Field(default_factory=list)
    generatedAt: str = ""


class DigitalAssetUnitRecord(BaseModel):
    key: str
    label: str
    level: Literal["required", "advanced", "opportunity"] = "required"
    covered: bool = False
    evidenceCount: int = 0


class DigitalAssetMapNodeRecord(BaseModel):
    key: str
    label: str
    description: str = ""
    trackTitle: str = ""
    currentStage: str = "整理"
    stageIndex: int = 0
    coverageScore: int = 0
    maturityPercent: int = 0
    evidenceCount: int = 0
    coveredUnits: list[DigitalAssetUnitRecord] = Field(default_factory=list)
    missingUnits: list[DigitalAssetUnitRecord] = Field(default_factory=list)
    unlockedValue: str = ""
    nextDeposit: str = ""
    seenSummary: str = ""
    missingSummary: str = ""
    suggestedDocumentTitle: str = ""
    suggestedDocumentContent: list[str] = Field(default_factory=list)
    unlockedAnalysisValue: str = ""
    sourceHighlights: list[str] = Field(default_factory=list)
    representativeSources: list[DigitalAssetSourceRefRecord] = Field(default_factory=list)


class DigitalAssetDimensionRecord(BaseModel):
    key: str
    label: str
    description: str
    maturity: int = 0
    scoreBreakdown: DigitalAssetScoreBreakdownRecord = Field(default_factory=DigitalAssetScoreBreakdownRecord)
    evidenceCount: int = 0
    sourceTypes: list[str] = Field(default_factory=list)
    representativeSources: list[DigitalAssetSourceRefRecord] = Field(default_factory=list)
    valueInsights: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    depositSuggestions: list[str] = Field(default_factory=list)
    formedValue: str = ""
    nextBestDeposit: str = ""
    expectedGain: int = 0
    analysisValueUnlocked: str = ""
    statusLabels: list[str] = Field(default_factory=list)


class DigitalAssetClientSummaryRecord(BaseModel):
    id: str
    name: str
    stage: str = ""
    intro: str = ""
    assetCompletionScore: int = 0
    understandingScore: int = 0
    understandingStatement: str = ""
    depositedValueLevel: str = ""
    nextValueSpace: str = ""
    depositXp: int = 0
    assetProfileType: str = "组织战略陪伴型"
    secondaryProfileTypes: list[str] = Field(default_factory=list)
    maturityScore: int = 0
    depositThickness: int = 0
    scoreMethodVersion: str = ""
    scoreBreakdown: DigitalAssetScoreBreakdownRecord = Field(default_factory=DigitalAssetScoreBreakdownRecord)
    scoreRationale: list[str] = Field(default_factory=list)
    materialMaturityRows: list[DigitalAssetMaterialMaturityRowRecord] = Field(default_factory=list)
    assetStage: str = "资料整理期"
    assetTrackTitle: str = "组织资产型"
    growthMode: Literal["均衡成长", "单项突破", "结构偏科"] = "均衡成长"
    stageProgress: int = 0
    nextStage: str = ""
    unlockedCapabilities: list[str] = Field(default_factory=list)
    stageBlockers: list[str] = Field(default_factory=list)
    nextBestDeposits: list[DigitalAssetDepositSuggestionRecord] = Field(default_factory=list)
    assetMapNodes: list[DigitalAssetMapNodeRecord] = Field(default_factory=list)
    assetDimensionCount: int = 0
    strongestDimensions: list[str] = Field(default_factory=list)
    highValueSignals: list[str] = Field(default_factory=list)
    criticalGaps: list[str] = Field(default_factory=list)
    nextDeposits: list[str] = Field(default_factory=list)
    metrics: list[DigitalAssetMetricRecord] = Field(default_factory=list)
    emptyState: bool = False
    updatedAt: str | None = None


class DigitalAssetNarrativeRecord(BaseModel):
    id: str
    clientId: str
    sourceFingerprint: str = ""
    contentMarkdown: str = ""
    materialAudit: dict[str, object] = Field(default_factory=dict)
    qualityWarnings: list[str] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    generatedAt: str
    failureReason: str = ""


class DigitalAssetDashboardRecord(BaseModel):
    generatedAt: str
    pulse: DigitalAssetPulseRecord = Field(default_factory=DigitalAssetPulseRecord)
    clients: list[DigitalAssetClientSummaryRecord] = Field(default_factory=list)


class OrganizationDnaV2ItemRecord(BaseModel):
    id: str
    moduleKind: OrganizationDnaV2Kind
    title: str
    contentMarkdown: str
    summary: str = ""
    status: OrganizationDnaV2Status = "candidate"
    evidenceLevel: OrganizationDnaEvidenceLevel = "internal"
    sourceType: str
    sourceId: str
    sourceLabel: str
    observedAt: str
    sourceCreatedAt: str | None = None
    lastSeenAt: str
    validUntil: str | None = None
    confidenceScore: int = 60
    createdAt: str
    updatedAt: str


class OrganizationDnaRefreshEventRecord(BaseModel):
    id: str
    runId: str
    level: Literal["info", "warning", "error"] = "info"
    message: str
    detail: dict[str, object] = Field(default_factory=dict)
    createdAt: str


class OrganizationDnaRefreshRunRecord(BaseModel):
    id: str
    jobType: Literal["organization_dna_refresh"] = "organization_dna_refresh"
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    triggerSource: str = "manual"
    totalItems: int = 0
    processedItems: int = 0
    error: str | None = None
    createdAt: str
    startedAt: str | None = None
    finishedAt: str | None = None
    updatedAt: str
    events: list[OrganizationDnaRefreshEventRecord] = Field(default_factory=list)


class OrganizationDnaV2SnapshotRecord(BaseModel):
    generatedAt: str
    stableItems: list[OrganizationDnaV2ItemRecord] = Field(default_factory=list)
    evolvingItems: list[OrganizationDnaV2ItemRecord] = Field(default_factory=list)
    gapItems: list[OrganizationDnaV2ItemRecord] = Field(default_factory=list)
    riskItems: list[OrganizationDnaV2ItemRecord] = Field(default_factory=list)
    itemCounts: dict[str, int] = Field(default_factory=dict)
    confirmedCount: int = 0
    candidateCount: int = 0
    staleCount: int = 0
    latestRun: OrganizationDnaRefreshRunRecord | None = None
    updatedAt: str | None = None


class OrganizationDnaToolContextRecord(BaseModel):
    purpose: DnaToolPurpose
    selectedKinds: list[OrganizationDnaV2Kind] = Field(default_factory=list)
    contextText: str = ""
    sourceLevelSummary: dict[str, int] = Field(default_factory=dict)
    timeScopeSummary: str = ""
    warnings: list[str] = Field(default_factory=list)


class DigitalAssetClientDetailRecord(DigitalAssetClientSummaryRecord):
    dimensions: list[DigitalAssetDimensionRecord] = Field(default_factory=list)
    valueInsights: list[DigitalAssetInsightRecord] = Field(default_factory=list)
    depositSuggestions: list[DigitalAssetDepositSuggestionRecord] = Field(default_factory=list)
    sourceMetrics: list[DigitalAssetMetricRecord] = Field(default_factory=list)
    aiNarrative: DigitalAssetNarrativeRecord | None = None


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


StrategicThoughtScope = Literal["client", "project", "system"]
StrategicThoughtStatus = Literal["draft", "confirmed", "dismissed", "task_created", "waiting_evidence"]
StrategicThoughtConfidenceLevel = Literal["low", "medium", "high", "none"]
StrategicInsightType = Literal[
    "strategic_shift",
    "risk_signal",
    "opportunity_window",
    "execution_bottleneck",
    "narrative_upgrade",
    "operating_model",
]

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
    "analysis_run",
    "client_dna",
    "document",
    "task",
    "project_module",
    "project_flow",
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
    projectModuleId: str | None = None
    projectModuleName: str | None = None
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
    insightType: StrategicInsightType | None = None
    insightText: str | None = None
    futureJudgment: str | None = None
    whyItMatters: str | None = None
    recommendedAction: str | None = None
    evidenceSummary: str | None = None
    evidenceLabels: list[str] = Field(default_factory=list)
    signalScore: int = 0
    sourceFingerprint: str | None = None
    isFavorite: bool = False
    isDeleted: bool = False
    review: StrategicThoughtReviewRecord | None = None


class StrategicThoughtsResponseRecord(BaseModel):
    items: list[StrategicThoughtRecord] = Field(default_factory=list)
    total: int = 0
    generatedAt: str
    selectedClientId: str | None = None
    selectedProjectModuleId: str | None = None
    usingMockData: bool = False


class StrategicThoughtRefreshPayload(BaseModel):
    clientId: str | None = None
    projectModuleId: str | None = None
    limit: int = Field(default=8, ge=1, le=12)


class StrategicThoughtStatePayload(BaseModel):
    action: Literal["favorite", "unfavorite", "delete", "restore"]


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
    expWallSignals: int = 0
    memorySignals: int = 0
    documentSignals: int = 0
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


class GrowthSocialFeedbackRecord(BaseModel):
    """H4：让用户看见"努力被看见"的聚合反馈。"""

    handbookReuseCount: int = 0
    handbookEntriesReused: int = 0
    expWallLikeCount: int = 0
    expWallSaveCount: int = 0
    expWallQuoteCount: int = 0
    periodLabel: str = "近 30 天"


class GrowthAbilityTrendPointRecord(BaseModel):
    """L1：能力周快照单点（用于画 mini 折线）。"""

    weekLabel: str
    score: int
    totalXp: int


class GrowthAbilityTrendRecord(BaseModel):
    """L1：单个能力的多周趋势。"""

    abilityKey: str
    label: str
    points: list[GrowthAbilityTrendPointRecord] = Field(default_factory=list)
    scoreDelta: int = 0
    direction: str = "flat"  # up / down / flat


class GrowthDailyActivityRecord(BaseModel):
    """L2：单日工作产出强度。"""

    date: str  # YYYY-MM-DD
    count: int
    level: int = 0  # 0-4 染色等级（react-activity-calendar 期望）


class GrowthDailyActivityResponse(BaseModel):
    """L2：最近 N 天的日历活动 + 总览统计。"""

    days: list[GrowthDailyActivityRecord] = Field(default_factory=list)
    totalDays: int = 0
    activeDays: int = 0
    maxStreak: int = 0


class GrowthCommitmentTrendPointRecord(BaseModel):
    """M2 履约率单周点。"""

    weekLabel: str
    totalCount: int = 0
    fulfilledCount: int = 0
    rate: float = 0.0  # 0-1


class GrowthCommitmentItemRecord(BaseModel):
    """M2 一条待办承诺。"""

    id: str
    content: str
    recipient: str
    deadline: str | None = None
    status: str
    daysOverdue: int = 0  # 负数=离截止还有几天，正数=已超期


class GrowthCommitmentCumulativePointRecord(BaseModel):
    """M2 环比双线单点（本月 vs 上月相同位置的累计件数）。"""

    weekIndex: int  # 0=月初, 3=月末
    weekLabel: str  # 给 x 轴显示
    currentCumulative: int = 0
    previousCumulative: int = 0


class GrowthCommitmentSummaryRecord(BaseModel):
    """M2 承诺履约总览（正向 streak + 环比对比）。"""

    # 旧字段保留 API 兼容（前端不再渲染负向）
    totalCount: int = 0
    fulfilledCount: int = 0
    pendingCount: int = 0
    overdueCount: int = 0
    rate: float = 0.0
    trend: list[GrowthCommitmentTrendPointRecord] = Field(default_factory=list)
    upcomingPending: list[GrowthCommitmentItemRecord] = Field(default_factory=list)

    # 正向指标
    currentStreakDays: int = 0
    longestStreakDays: int = 0
    monthlyFulfilledCount: int = 0
    lastMonthFulfilledCount: int = 0
    growthPercent: int = 0
    cumulativeCurve: list[GrowthCommitmentCumulativePointRecord] = Field(default_factory=list)


class GrowthBusinessCoverageItemRecord(BaseModel):
    """M1 单个客户/项目维度的覆盖。"""

    label: str
    taskCount: int = 0
    documentCount: int = 0
    glossaryTermCount: int = 0
    score: int = 0  # 综合积累分


class GrowthBusinessCoverageRecord(BaseModel):
    """M1 业务覆盖热力图数据。"""

    items: list[GrowthBusinessCoverageItemRecord] = Field(default_factory=list)
    coveredClients: int = 0
    coveredProjects: int = 0  # 字典项目类计数


class GrowthReviewWeekPointRecord(BaseModel):
    """M3 复盘单周聚合（保留兼容，新前端不再用）。"""

    weekLabel: str
    entryCount: int = 0
    charCount: int = 0


class GrowthReviewDayPointRecord(BaseModel):
    """M3 复盘单日聚合（用于 30 天曲线图）。"""

    date: str  # YYYY-MM-DD
    entryCount: int = 0
    charCount: int = 0


class GrowthReviewStreakRecord(BaseModel):
    """M3 复盘沉淀（连续 + 件数 + 字数 + 环比 + 30 天曲线）。"""

    currentStreakWeeks: int = 0
    maxStreakWeeks: int = 0
    totalReviewWeeks: int = 0
    lastReviewedWeekLabel: str = ""

    # 件数维度
    monthlyEntryCount: int = 0
    lastMonthEntryCount: int = 0
    entryGrowthPercent: int = 0

    # 字数维度（鼓励写得多）
    monthlyCharCount: int = 0
    lastMonthCharCount: int = 0
    charGrowthPercent: int = 0

    # 旧字段：按周聚合（保留 API 兼容，新前端用 dailyTrend）
    weeklyTrend: list[GrowthReviewWeekPointRecord] = Field(default_factory=list)
    # 新字段：按天聚合（30 天曲线）
    dailyTrend: list[GrowthReviewDayPointRecord] = Field(default_factory=list)


class GrowthWorkTypeSliceRecord(BaseModel):
    """M4 工作类型饼图一片。"""

    label: str
    count: int = 0


class GrowthWorkTypeRecord(BaseModel):
    """M4 工作类型分布。"""

    slices: list[GrowthWorkTypeSliceRecord] = Field(default_factory=list)
    totalTasks: int = 0
    unlabeledTasks: int = 0  # business_category 为空的


class GrowthImpactCurvePointRecord(BaseModel):
    """M6 累计影响力曲线单点。"""

    monthLabel: str
    cumulativeReuses: int = 0
    cumulativeLikes: int = 0
    cumulativeSaves: int = 0


class GrowthImpactRecord(BaseModel):
    """M6 累计影响力曲线。"""

    points: list[GrowthImpactCurvePointRecord] = Field(default_factory=list)
    totalReuses: int = 0
    totalLikes: int = 0
    totalSaves: int = 0


class GrowthLearningPickRecord(BaseModel):
    """L3 推荐的一条学习内容。"""

    source: str  # handbook / exp_wall
    sourceId: str
    title: str
    detail: str = ""
    authorName: str = ""
    matchedAbility: str = ""
    matchedAbilityLabel: str = ""
    reusedCount: int = 0
    likedCount: int = 0
    savedCount: int = 0


class GrowthLearningRecord(BaseModel):
    """L3 学习推荐 = 内部 + 外部前瞻（外部部分由 L4/L5 填）。"""

    internalPicks: list[GrowthLearningPickRecord] = Field(default_factory=list)
    githubPicks: list[GrowthLearningPickRecord] = Field(default_factory=list)
    frontierPicks: list[GrowthLearningPickRecord] = Field(default_factory=list)
    weakestAbilities: list[str] = Field(default_factory=list)
    externalEnabled: bool = False  # GitHub/Exa 是否就绪
    externalConfigHint: str = ""  # 未就绪时的提示


class GrowthPeerComparisonRecord(BaseModel):
    """H5 同岗位匿名对标。"""

    roleLabel: str = ""  # 你的岗位名
    peerCount: int = 0  # 该岗位人数（含自己）
    rank: int = 0  # 你的排名（1=最高）
    yourTotalXp: int = 0
    peerMedianXp: int = 0
    peerTopXp: int = 0
    perAbilityRank: dict[str, int] = Field(default_factory=dict)  # ability_key -> rank


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
    socialFeedback: GrowthSocialFeedbackRecord = Field(default_factory=GrowthSocialFeedbackRecord)
    abilityTrends: list[GrowthAbilityTrendRecord] = Field(default_factory=list)
    dailyActivity: GrowthDailyActivityResponse = Field(default_factory=GrowthDailyActivityResponse)
    commitmentSummary: GrowthCommitmentSummaryRecord = Field(default_factory=GrowthCommitmentSummaryRecord)
    businessCoverage: GrowthBusinessCoverageRecord = Field(default_factory=GrowthBusinessCoverageRecord)
    reviewStreak: GrowthReviewStreakRecord = Field(default_factory=GrowthReviewStreakRecord)
    workTypeDistribution: GrowthWorkTypeRecord = Field(default_factory=GrowthWorkTypeRecord)
    impactCurve: GrowthImpactRecord = Field(default_factory=GrowthImpactRecord)
    learning: GrowthLearningRecord = Field(default_factory=GrowthLearningRecord)
    peerComparison: GrowthPeerComparisonRecord = Field(default_factory=GrowthPeerComparisonRecord)
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


ReviewPerspectiveKey = Literal["organization", "department", "mine"]


class ReviewPerspectiveOptionRecord(BaseModel):
    key: ReviewPerspectiveKey
    label: str
    departmentId: str | None = None
    departmentName: str | None = None


class ReviewResponse(BaseModel):
    weekLabel: str = ""
    resolvedWeekLabel: str | None = None
    currentReview: WeeklyReviewRecord | None = None
    workItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    personalItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    availablePerspectives: list[ReviewPerspectiveOptionRecord] = Field(default_factory=list)
    activePerspective: ReviewPerspectiveKey = "mine"
    activeDepartmentId: str | None = None
    activeDepartmentName: str | None = None
    workAnalysis: WeeklyReviewAnalysisRecord | None = None
    personalAnalysis: WeeklyReviewAnalysisRecord | None = None
    weeklyMainlineCards: WeeklyMainlineCardsRecord | None = None
    weeklyEventReviewCards: WeeklyEventReviewCardsRecord | None = None
    weeklyOverviewGenerationStatus: WeeklyOverviewRefreshStatusRecord | None = None
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
    deepAnalysis: dict[str, object] = Field(default_factory=dict)
    convertedTaskId: str | None = None
    contentKind: str | None = None
    whyRecommended: str | None = None
    relevanceReason: str | None = None
    suggestedAction: str | None = None
    recommendationBasis: list[str] = Field(default_factory=list)
    groundingFactRefs: list[str] = Field(default_factory=list)
    scopeType: str | None = None
    scopeId: str | None = None
    clientId: str | None = None
    projectModuleId: str | None = None
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
    advisorMemo: str = ""
    createdAt: str
    updatedAt: str


class IntelligenceProfileBackgroundEnrichmentRecord(BaseModel):
    id: str | None = None
    title: str
    sourceUrl: str | None = None
    status: str | None = None


class IntelligenceProfileFetchSummaryRecord(BaseModel):
    status: str | None = None
    failureReason: str | None = None
    completedAt: str | None = None
    createdCount: int = 0
    weakSignalCount: int = 0
    backgroundEnrichmentCount: int = 0


class IntelligenceProfileRecord(BaseModel):
    id: str
    title: str
    radarId: str | None = None
    radarTitle: str | None = None
    profileKind: str = "auto"
    scopeType: str | None = None
    scopeId: str | None = None
    clientId: str | None = None
    projectModuleId: str | None = None
    status: str | None = None
    profileReadiness: str | None = None
    summary: str = ""
    effectiveSummary: str | None = None
    adminSummaryOverride: str | None = None
    adminFocus: list[str] = Field(default_factory=list)
    adminExcludeTerms: list[str] = Field(default_factory=list)
    adminPriorityUrls: list[str] = Field(default_factory=list)
    adminProfileRefreshEnabled: bool = False
    adminProfileRefreshFrequency: str = "manual"
    adminPushEnabled: bool = False
    adminPushFrequency: str = "manual"
    materialSummary: list[str] = Field(default_factory=list)
    workContext: list[str] = Field(default_factory=list)
    priorityNeeds: list[str] = Field(default_factory=list)
    targetBeneficiaries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    opportunityTypes: list[str] = Field(default_factory=list)
    materialGaps: list[str] = Field(default_factory=list)
    groundingFacts: list[str] = Field(default_factory=list)
    backgroundEnrichments: list[IntelligenceProfileBackgroundEnrichmentRecord] = Field(default_factory=list)
    lastFetch: IntelligenceProfileFetchSummaryRecord | None = None
    deletedAt: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class IntelligenceProfileMutationPayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    focus: list[str] | None = None
    excludeTerms: list[str] | None = None
    priorityUrls: list[str] | None = None
    profileRefreshEnabled: bool | None = None
    profileRefreshFrequency: str | None = None
    pushEnabled: bool | None = None
    pushFrequency: str | None = None


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
    intelligenceProfiles: list[IntelligenceProfileRecord] = Field(default_factory=list)


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
    eventLineId: str | None = None
    tags: list[str] = Field(default_factory=list)
    note: str = ""
    ownerRecipient: dict[str, object] | None = None
    collaboratorRecipients: list[dict[str, object]] = Field(default_factory=list)
    actorId: str | None = None
    actorName: str | None = None
    autoShare: bool = False


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


class GrowthExperienceWallItemRecord(BaseModel):
    id: str
    source: Literal["handbook", "exp_wall"]
    text: str
    summary: str = ""
    authorUserId: str | None = None
    authorUserName: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    sourceType: str = ""
    sourceObjectId: str = ""
    sourceTitle: str | None = None
    category: str = ""
    reuseCount: int = 0
    likeCount: int = 0
    saveCount: int = 0
    currentUserLiked: bool = False
    linkedContexts: list[GrowthContextLinkRecord] = Field(default_factory=list)
    createdAt: str


class GrowthExperienceWallResponse(BaseModel):
    items: list[GrowthExperienceWallItemRecord]
    refreshedFromCloud: bool = False
    cloudSyncError: str | None = None


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


class KnowledgeJobEventRecord(BaseModel):
    level: str
    message: str
    processedItems: int | None = None
    itemLabel: str | None = None
    createdAt: str


class KnowledgeJobRecord(BaseModel):
    id: str
    clientId: str
    jobType: str
    status: Literal["queued", "running", "completed", "failed"]
    totalItems: int
    processedItems: int
    lastError: str | None = None
    currentItemLabel: str | None = None
    lastEventMessage: str | None = None
    recentEvents: list[KnowledgeJobEventRecord] = Field(default_factory=list)
    queuedItemLabels: list[str] = Field(default_factory=list)
    createdAt: str
    startedAt: str | None = None
    finishedAt: str | None = None
    updatedAt: str


class KnowledgeProgressRecord(BaseModel):
    knowledgeStatus: KnowledgeStatusRecord
    knowledgeJobs: list[KnowledgeJobRecord] = Field(default_factory=list)


class KnowledgeSearchHitRecord(BaseModel):
    title: str
    excerpt: str
    score: float
    stage: Literal["master_index", "surrogate", "raw_chunk", "state_pool"]
    path: str | None = None
    sectionLabel: str | None = None
    matchedTerms: list[str] = Field(default_factory=list)

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: object) -> str:
        # Defensive: any None / legacy / unknown value falls back to raw_chunk
        # so this record never fails Pydantic validation on upstream gaps.
        return normalize_retrieval_stage(value)


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


class DocumentReadingPreviewRecord(BaseModel):
    documentId: str
    title: str
    parseStatus: str
    folderLabel: str | None = None
    sectionCount: int = 0
    chunkCount: int = 0
    sourceKind: str = "raw_file"
    readSummary: str = ""
    keyHeadings: list[str] = Field(default_factory=list)
    availableForChat: bool = False
    failureReason: str | None = None


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
    memoryCards: list["KnowledgeMemoryRecord"] = Field(default_factory=list)
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
    messageId: str | None = None
    messageIds: list[str] | None = None


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


# P9 / P11：客户工作台 inline 编辑器 AI 助手 action
#   action：要执行的 LLM 任务（扩写 / 改写 / 总结 / 提取 / 翻译 / 风格化）
#   userRequest：用户在 inline 提示框写的具体要求（可空）
#   creativityMode：creative=完全自由 / balanced=兼顾资料（默认）/ strict=严格依据
#   activeSkillId：选中的写作风格 skill id（指向 writing_skills 表）
class DocumentAiActionContextSourceSpec(BaseModel):
    """前端传给后端的 context source 规格（P13b+ 使用）。"""
    type: Literal[
        "selection_only",
        "current_doc",
        "client_materials",
        "strategy_dimension",
        "event_timeline",
    ]
    query: str = ""
    refId: str | None = None
    topK: int = 5
    params: dict = {}


class DocumentAiActionSourceRef(BaseModel):
    """单个被召回资料的引证元信息（返给前端展示用）。"""
    type: str
    title: str
    snippet: str = ""
    refId: str | None = None
    extra: dict = {}


class DocumentAiActionPayload(BaseModel):
    content: str
    action: Literal[
        # A 类 · 纯文本变换
        "expand",
        "rewrite_pro",
        "rewrite_short",
        "summarize",
        "extract",
        "translate",
        "style_distilled",
        # B 类 · 资料增强（P13b/c 接入）
        "insert_from_materials",
        "rewrite_by_strategy",
        "insert_data_table",
    ]
    userRequest: str = ""
    creativityMode: Literal["creative", "balanced", "strict"] = "balanced"
    activeSkillId: str | None = None
    # P13b+：资料源列表。P13a 默认空，行为零变化。
    contextSources: list[DocumentAiActionContextSourceSpec] = []
    # P14a：用户当前选区文本（window.getSelection().toString()）。
    # 非空 → 模型只处理这段；空 → 走全文老行为。
    selectionText: str = ""
    # 用户从右侧文件列表 attach 到对话引用的 document_id 列表。
    # 跟 ChatRequest.workingDocumentIds 同语义,作为 RAG 召回的优先种子。
    workingDocumentIds: list[str] = Field(default_factory=list)


class DocumentAiActionResponse(BaseModel):
    content: str
    action: str
    durationMs: float = 0.0
    # P13b+：本次召回到的资料引证。P13a 一律为空数组。
    sources: list[DocumentAiActionSourceRef] = []
    # 后端实际使用的 creativity 值（faithful 类 op 会被覆盖为 strict）
    effectiveCreativity: str = "balanced"
    # P14a：本次实际作用范围。"selection" = 后端只处理了选区，前端只替换选区；
    # "full_doc" = 处理整篇，前端整篇替换。
    targetScope: Literal["selection", "cursor_insert", "full_doc"] = "full_doc"


class LinkMaterialImportStartPayload(BaseModel):
    url: str
    useBrowserCookies: bool = False
    cookieBrowser: Literal["firefox", "chrome", "edge", "safari"] = "firefox"


class LinkMaterialImportRunRecord(BaseModel):
    runId: str
    clientId: str
    sourcePlatform: Literal["bilibili", "xiaohongshu", "wechat_article"]
    sourceUrl: str
    title: str | None = None
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    stage: str
    progress: float = 0.0
    documentId: str | None = None
    documentPath: str | None = None
    mediaCacheStatus: Literal["not_downloaded", "cleaned", "retained", "failed"] = "not_downloaded"
    error: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


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
    phase: Literal["queued", "parsing", "retrieving", "ai", "writing", "completed", "failed"]
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
    overviewSummary: str = ""
    retrievalSummary: str = ""
    documentRole: str = ""
    sourceLinks: list[dict[str, object]] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    # C 取消收藏：标记这条 memory 来自哪条 chat message,前端据此判断"已收藏"并切换按钮
    chatMessageId: str | None = None


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
    # 修复：commit 0582bd7 引入 humanBrief 概念但只加到了别的 Record 上，
    # V1Record 同步缺失导致多处测试失败。补上向后兼容字段。
    humanBrief: str | None = None


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


# =============================================================================
# 报告生成器（report-gen）· 数据契约
# =============================================================================
# 对应执行计划：docs/报告生成器-Claude-Code执行计划-2026-05-12.md
# 三阶段：阶段一(推导骨架) → 阶段二(分批填充) → 阶段三(排版导出)
# 三角色：A 主理人(决定骨架) / B 起草员(写章节) / C 润色员(风格统一)
# 模型选型：3 角色全部使用豆包 Seed 2.0 Pro（灰度测试主力）
# =============================================================================


ReportChartKind = Literal[
    "pie",                 # 饼图（占比类，commit 类型/资料分类/时间分配）
    "progress_bar_h",      # 横向进度条（前后对比/完成度，可带目标线）
    "timeline",            # 时间线（大事记/里程碑，带状态徽章）
    "grouped_bar",         # 分组柱状图（多周期/多对象对比）
    "risk_bubble",         # 风险矩阵气泡（影响 × 概率，气泡大小为权重）
    "table_only",          # 不画图，仅渲染表格
    "callout_only",        # 不画图，仅渲染引用块
]


class ChartHint(BaseModel):
    """章节内信息图建议（阶段一 LLM A 决定，阶段二渲染时取数生成 PNG）。"""

    kind: ReportChartKind
    title: str
    caption: str | None = None
    # 自然语言描述数据从哪取，如 "git log Q1 commit 类型计数"
    # 阶段二 section_drafter 会解析此字段定位数据
    data_source_hint: str


class SectionPlan(BaseModel):
    """单个章节计划（阶段一产物，章节标题不固定文案，由 LLM A 决定）。"""

    level: int = Field(default=1, ge=1, le=2)  # 1=H1（一级章节）2=H2（subsection）
    title: str
    goal: str  # 这一章要解决什么、读者读完知道什么（≤60 字）
    # 数据源自然语言列举：confirmedJudgments / events / tasks / documents / git_log 等
    data_sources: list[str] = Field(default_factory=list)
    chart_hints: list[ChartHint] = Field(default_factory=list)
    citation_budget: int = Field(default=5, ge=0)  # 期望引用数（短章 2-3 / 深度章 5-8）
    estimated_words: int = Field(default=300, ge=50, le=2000)  # 预估字数


class ReportBlueprint(BaseModel):
    """阶段一产出的完整报告骨架（LLM A 主理人决定）。"""

    title: str  # 报告主标题，要具体（避免"XX 报告"这种笼统标题）
    subtitle: str | None = None
    # LLM 给的报告类型标签——自由文本不枚举（如"战略陪伴季报"/"产品复盘"/"募款汇报"）
    report_kind: str
    audience: str  # 受众："客户决策层" / "集团内部决策层" / "公众" 等
    tone: str      # 语气："专业冷静" / "诚恳坦率" / "鼓舞性" / "数据驱动" 等
    period_start: str  # ISO 日期
    period_end: str
    sections: list[SectionPlan] = Field(default_factory=list)  # 3-9 个为宜（含附录）

    # 元数据
    inferred_theme: str  # LLM 总结这条事件线的主题（1-2 句）
    confidence: float = Field(default=0.8, ge=0, le=1)  # 骨架置信度
    open_questions_for_human: list[str] = Field(default_factory=list)

    # 数据来源元信息
    event_line_id: str | None = None
    client_id: str
    generated_at: str  # ISO 时间戳


# -------- 阶段二产物 --------


ReportCitationType = Literal[
    "judgment",   # 已确认判断
    "event",      # 事件线 entry
    "task",       # 任务
    "document",   # 文档 / 附件
    "metric",     # 数据指标
    "commit",     # git commit (用于产品复盘类报告)
]


class CitationRef(BaseModel):
    """正文内引用的源数据条目（CitationRef.id 用作章节末尾"数据源"标注）。"""

    type: ReportCitationType
    id: str  # 数据库 ID 或 commit hash
    label: str  # 短标签（如 "20fde25" 或 "客户A 战略目标 #3"）
    excerpt: str | None = None  # 可选的引用原文


class GeneratedChart(BaseModel):
    """已生成的信息图（PNG bytes 用 base64 编码方便 JSON 传输）。"""

    hint: ChartHint
    png_bytes_base64: str
    width_cm: float = 14.5


class SectionContent(BaseModel):
    """单章节填充结果（阶段二每章产物）。"""

    plan: SectionPlan
    markdown: str  # 章节正文 Markdown（不含章标题，标题由 plan.title 渲染时给）
    citations: list[CitationRef] = Field(default_factory=list)
    charts: list[GeneratedChart] = Field(default_factory=list)
    data_source_annotation: str = ""  # 章节末尾"数据源"标注内容
    confidence: float = Field(default=0.7, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)  # 起草中遇到的告警


# -------- 阶段三产物 --------


class ReportArtifact(BaseModel):
    """完整生成的报告（阶段三最终产物，写入数据库 + 文件系统）。"""

    blueprint: ReportBlueprint
    sections: list[SectionContent] = Field(default_factory=list)
    # 输出文件路径字典：{"docx": "/path/...", "pdf": "/path/...", "md": "/path/..."}
    output_files: dict[str, str] = Field(default_factory=dict)
    generated_at: str
    total_llm_tokens: int = 0
    total_cost_usd: float = 0.0


# -------- API 请求/响应模型 --------


class DraftBlueprintRequest(BaseModel):
    """POST /api/v1/reports/draft-blueprint 入参。"""

    # 二选一：直接给事件线 id；或给 (client_id, 报告期) 系统聚合
    event_line_id: str | None = None
    client_id: str | None = None
    period_start: str | None = None
    period_end: str | None = None

    # 用户给的报告意图提示（影响骨架）
    intent_hint: str | None = None

    # 受众/语气偏好（可选，让 LLM 优先采纳）
    audience_hint: str | None = None
    tone_hint: str | None = None


class DraftSectionsRequest(BaseModel):
    """POST /api/v1/reports/{report_run_id}/draft-sections 入参。"""

    # 章节索引数组（不填则全部）。支持只重跑指定章节
    section_indices: list[int] | None = None
    # 并行 worker 数（默认 4，触 LLM rate limit 时降）
    max_workers: int = Field(default=4, ge=1, le=8)


ReportRunStatus = Literal[
    "blueprint_pending",     # 刚创建，骨架还没拉出来
    "blueprint_confirmed",   # 骨架确认完，等填章节
    "drafting",              # 填章节中
    "rendered",              # 已渲染到文件
    "published",             # 已通知 + 归档
    "failed",                # 任一阶段失败
]


class ReportRunSummary(BaseModel):
    """GET /api/v1/reports/{report_run_id} 出参。"""

    id: str
    client_id: str
    event_line_id: str | None
    period_start: str | None
    period_end: str | None
    intent_hint: str | None
    status: ReportRunStatus
    blueprint: ReportBlueprint | None
    sections_status: list[Literal["pending", "drafting", "done", "failed"]] = Field(
        default_factory=list,
    )
    output_files: dict[str, str] = Field(default_factory=dict)
    total_llm_tokens: int = 0
    created_at: str
    updated_at: str


# === 输入广度线程（input-breadth）：语音识别模型配置 ===

SpeechProvider = Literal["volcano", "openai_whisper", "aliyun_tongyi", "xunfei"]


class SpeechModelSettingsRecord(BaseModel):
    """单 org 级语音识别模型配置。Provider 抽象，credentials/extra 用 JSON 灵活承载。"""
    provider: str = ""
    credentials: dict[str, str] = Field(default_factory=dict)
    modelId: str = ""
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    updatedAt: str = ""


class SpeechModelSettingsPayload(BaseModel):
    provider: str
    credentials: dict[str, str] = Field(default_factory=dict)
    modelId: str = ""
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False


class SpeechModelTestResult(BaseModel):
    success: bool
    message: str = ""
    detail: str | None = None
    latencyMs: float | None = None


# === I1b-1：对象存储（文件中转/归档）配置 ===

ObjectStorageProvider = Literal["volcano_tos", "aliyun_oss", "aws_s3"]


class ObjectStorageSettingsRecord(BaseModel):
    """组织/本机对象存储配置。Provider 抽象，credentials/extra 用 JSON 灵活承载。"""
    provider: str = ""
    credentials: dict[str, str] = Field(default_factory=dict)
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    updatedAt: str = ""
    hasCredentials: bool = False
    managedByCloud: bool = False
    configuredBy: str | None = None


class ObjectStorageSettingsPayload(BaseModel):
    provider: str
    credentials: dict[str, str] = Field(default_factory=dict)
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False


class ObjectStorageTestResult(BaseModel):
    success: bool
    message: str = ""
    detail: str | None = None
    latencyMs: float | None = None


# === I1b-2：本地 ASR (SenseVoice via sherpa-onnx) ===

class LocalAsrModelStatusResponse(BaseModel):
    modelName: str
    installed: bool
    modelDir: str
    sizeBytes: int = 0
    downloadInProgress: bool = False
    downloadBytesDownloaded: int = 0
    downloadBytesTotal: int = 0
    downloadCurrentFile: str = ""
    downloadCompleted: bool = False
    downloadError: str | None = None
    downloadElapsedSeconds: float = 0.0


class DiarizationModelStatusResponse(BaseModel):
    """说话人分离的两个模型：segmentation + embedding 的合并状态。"""
    segmentationModelName: str
    embeddingModelName: str
    segmentationInstalled: bool = False
    embeddingInstalled: bool = False
    bothInstalled: bool = False
    sizeBytes: int = 0
    # 与 SenseVoice 共享的单例下载 manager 状态
    downloadInProgress: bool = False
    downloadBytesDownloaded: int = 0
    downloadBytesTotal: int = 0
    downloadCurrentFile: str = ""
    downloadCurrentModel: str = ""
    downloadPendingModels: list[str] = Field(default_factory=list)
    downloadCompletedModels: list[str] = Field(default_factory=list)
    downloadCompleted: bool = False
    downloadError: str | None = None
    downloadElapsedSeconds: float = 0.0


class LocalAsrDownloadStartPayload(BaseModel):
    preferMirror: bool = True


class LocalAsrDownloadStartResponse(BaseModel):
    started: bool
    message: str = ""


class LocalAsrDownloadCancelResponse(BaseModel):
    cancelled: bool


class LocalAsrTestTranscriptionPayload(BaseModel):
    audioPath: str


class LocalAsrTranscriptionSegmentRecord(BaseModel):
    startMs: int
    endMs: int
    text: str
    emotion: str | None = None
    event: str | None = None
    speakerId: str | None = None


class LocalAsrTestTranscriptionResponse(BaseModel):
    success: bool
    text: str = ""
    durationMs: int = 0
    elapsedMs: float = 0.0
    language: str = ""
    segments: list[LocalAsrTranscriptionSegmentRecord] = Field(default_factory=list)
    errorMessage: str | None = None


# === I1b-3：录音 ingest（前端把录音文件落到 userData，后端从本地路径直接转写）===
# 当前只实现 source = local_path；将来加对象存储后扩展 source = remote_url。


class RecordingTranscribeLocalPayload(BaseModel):
    """前端通过 IPC 把录音文件落到 userData 后，传文件绝对路径给后端转写。"""
    audioPath: str
    language: str = "auto"


class RecordingTranscribeLocalResponse(BaseModel):
    success: bool
    text: str = ""
    durationMs: int = 0
    elapsedMs: float = 0.0
    language: str = ""
    segments: list[LocalAsrTranscriptionSegmentRecord] = Field(default_factory=list)
    sourceFormat: str = ""  # 原始音频格式（webm / wav / mp3 ...）
    transcodedToWav: bool = False
    # 含说话人前缀的对话稿（"说话人A：xxx\n说话人B：xxx\n…"），diarization 启用时填
    dialogueText: str = ""
    numSpeakers: int = 0
    diarizationUsed: bool = False
    diarizationError: str | None = None
    errorMessage: str | None = None


class RecordingSummarizeMeetingMinutesPayload(BaseModel):
    """把录音 transcript 摘要成会议纪要 + 标题。

    若提供 dialogueText（"说话人A：…\\n说话人B：…"），LLM 会优先用对话稿生成
    含具体说话人的纪要；否则降级到 transcript。
    """
    transcript: str
    taskTitleHint: str = ""
    languageHint: str = ""
    dialogueText: str = ""
    numSpeakers: int = 0


class RecordingSummarizeMeetingMinutesResponse(BaseModel):
    success: bool
    title: str = ""
    minutesMd: str = ""
    errorMessage: str | None = None


# === P0-②：Ollama 本地 LLM 管理 ===

class OllamaInstalledModelRecord(BaseModel):
    name: str
    sizeBytes: int = 0
    digest: str = ""
    modifiedAt: str = ""


class OllamaHealthResponse(BaseModel):
    running: bool
    baseUrl: str
    installedModels: list[OllamaInstalledModelRecord] = Field(default_factory=list)
    error: str | None = None
    version: str | None = None


class OllamaRecommendedModelRecord(BaseModel):
    name: str
    sizeGb: float
    description: str
    default: bool = False


class OllamaRecommendedModelsResponse(BaseModel):
    capability: str
    models: list[OllamaRecommendedModelRecord] = Field(default_factory=list)


class OllamaPullPayload(BaseModel):
    modelName: str
    baseUrl: str | None = None


class OllamaPullStartResponse(BaseModel):
    started: bool
    message: str = ""


class OllamaPullStatusResponse(BaseModel):
    inProgress: bool
    modelName: str
    status: str
    bytesDownloaded: int
    bytesTotal: int
    elapsedSeconds: float
    completed: bool
    error: str | None = None


class OllamaPullCancelResponse(BaseModel):
    cancelled: bool


class OllamaDeleteModelPayload(BaseModel):
    modelName: str
    baseUrl: str | None = None


class OllamaDeleteModelResponse(BaseModel):
    success: bool
    message: str = ""

# ─────────────────────────────────────────────────────────────────────
# 客户项目情报流 Pydantic 类（同事新版资讯情报站）— 2026-05-13 补回
# 来源：origin-main-backup-before-force-push-2026-05-13 tag
# ─────────────────────────────────────────────────────────────────────

class IntelligenceWorkObjectRecord(BaseModel):
    type: IntelligenceWorkObjectType
    id: str
    clientId: str
    projectModuleId: str | None = None
    name: str
    subtitle: str = ""
    color: str = "#5B7BFE"
    updatedAt: str | None = None
    searchIntentStatus: IntelligenceSearchIntentStatus = "missing"
    searchIntentHint: str | None = None
    sourceCoverageStatus: IntelligenceSupplyStatus = "missing"
    candidateRefreshStatus: IntelligenceSupplyStatus = "missing"
    candidateRefreshHint: str | None = None
    lastCandidateFetchAt: str | None = None
    candidateCounts: dict[str, int] = Field(default_factory=dict)


class IntelligenceSourceDiagnosticSourceRecord(BaseModel):
    id: str
    sourceType: str
    sourceName: str
    sourceUrlTemplate: str
    contentKinds: list[str] = Field(default_factory=list)
    region: str = "全国"
    reliabilityTier: str = "standard"
    priority: int = 50
    enabled: bool = True
    discoverySource: str = "default_template"
    discoveryReason: str = ""
    discoverySamples: list[dict[str, str]] = Field(default_factory=list)
    healthScore: float = 70
    successCount: int = 0
    failureCount: int = 0
    candidateCount: int = 0
    promotedCount: int = 0
    duplicateCount: int = 0
    lastStatus: str = "unknown"
    lastCheckedAt: str | None = None
    lastSuccessAt: str | None = None
    lastFailureAt: str | None = None
    nextDueAt: str | None = None


class IntelligenceSourceDiagnosticFetchJobRecord(BaseModel):
    id: str
    contentKind: str
    provider: str
    sourceConfigId: str | None = None
    query: str
    status: str
    rawCount: int = 0
    dedupedCount: int = 0
    candidateCount: int = 0
    sampleHits: list[dict[str, str]] = Field(default_factory=list)
    failureReason: str = ""
    durationMs: int = 0
    createdAt: str


class IntelligenceSourceDiagnosticsResponse(BaseModel):
    scopeType: str
    scopeId: str
    contentKind: IntelligenceContentKind | None = None
    sourceCoverageStatus: IntelligenceSupplyStatus = "missing"
    candidateRefreshStatus: IntelligenceSupplyStatus = "missing"
    candidateRefreshHint: str | None = None
    lastCandidateFetchAt: str | None = None
    candidateCounts: dict[str, int] = Field(default_factory=dict)
    officialSiteDiscoveredCount: int = 0
    coverageGaps: list[str] = Field(default_factory=list)
    sources: list[IntelligenceSourceDiagnosticSourceRecord] = Field(default_factory=list)
    recentFetchJobs: list[IntelligenceSourceDiagnosticFetchJobRecord] = Field(default_factory=list)
    officialSiteDiscoverySamples: list[IntelligenceSourceDiagnosticFetchJobRecord] = Field(default_factory=list)


class IntelligenceFocusDirectiveRecord(BaseModel):
    id: str
    scopeType: IntelligenceFocusScopeType
    scopeId: str | None = None
    profileCompletionFocus: list[str] = Field(default_factory=list)
    timelyIntelligenceFocus: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class IntelligenceFocusDirectivePayload(BaseModel):
    scopeType: IntelligenceFocusScopeType = "global"
    scopeId: str | None = None
    profileCompletionFocus: list[str] = Field(default_factory=list)
    timelyIntelligenceFocus: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class IntelligenceRefreshCycleSettingsRecord(BaseModel):
    profileCompletionHours: int = 72
    timelyIntelligenceHours: int = 24


class IntelligenceRefreshCycleSettingsPayload(BaseModel):
    profileCompletionHours: int | None = Field(default=None, ge=1, le=8760)
    timelyIntelligenceHours: int | None = Field(default=None, ge=1, le=8760)


class IntelligenceItemRecord(BaseModel):
    id: str
    contentKind: IntelligenceContentKind
    scopeType: str | None = None
    scopeId: str | None = None
    clientId: str | None = None
    projectModuleId: str | None = None
    title: str
    summary: str = ""
    keyPoints: list[str] = Field(default_factory=list)
    analysis: str = ""
    impact: str = ""
    intelligenceType: str | None = None
    timelinessLabel: str | None = None
    relevanceReason: str = ""
    suggestedAction: str = ""
    followupQuestions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    sourceUrl: str | None = None
    publishedAt: str | None = None
    capturedAt: str
    verifiedAt: str | None = None
    dataCenterIngestEventId: str | None = None
    externalEvidenceCardId: str | None = None
    topicCandidateId: str | None = None
    convertedTaskId: str | None = None
    verificationStatus: str = "verified"
    verificationReason: str = ""
    userStatus: IntelligenceItemUserStatus = "active"
    createdAt: str
    updatedAt: str


class IntelligenceCandidateSample(BaseModel):
    id: str
    contentKind: IntelligenceContentKind
    scopeType: str
    scopeId: str
    clientId: str | None = None
    projectModuleId: str | None = None
    title: str
    url: str | None = None
    snippet: str = ""
    source: str = ""
    publishedAt: str | None = None
    capturedAt: str
    confidenceScore: float = 0
    classificationStatus: str = "candidate"
    promotionReason: str = ""
    verificationStatus: str = "pending"
    verificationReason: str = ""
    bodyFetchStatus: str = "not_attempted"
    summaryStatus: str = "not_attempted"
    mappedTags: list[str] = Field(default_factory=list)
    isUserVisibleCandidate: bool = True


class IntelligenceItemsResponse(BaseModel):
    items: list[IntelligenceItemRecord] = Field(default_factory=list)
    candidateSamples: list[IntelligenceCandidateSample] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    pageSize: int = 10


class IntelligenceRefreshPayload(BaseModel):
    scopeType: Literal["all", "client", "project_module"] = "all"
    scopeId: str | None = None
    contentKind: str
    force: bool = True
    triggerSource: str = "manual"


class IntelligenceAutoRefreshDuePayload(BaseModel):
    contentKinds: list[Literal["profile_completion", "timely_intelligence"]] = Field(
        default_factory=lambda: ["profile_completion", "timely_intelligence"]
    )
    scopeType: Literal["all", "client"] = "all"
    scopeId: str | None = None


class IntelligenceRefreshObjectResult(BaseModel):
    scopeType: IntelligenceWorkObjectType
    scopeId: str
    clientId: str
    projectModuleId: str | None = None
    name: str
    contentKind: IntelligenceContentKind
    status: Literal["completed", "no_results", "failed"] = "completed"
    intentCount: int = 0
    diagnosticRunCount: int = 0
    diagnosticSuccessCount: int = 0
    fetchJobCount: int = 0
    candidateCount: int = 0
    promotedCount: int = 0
    duplicateCount: int = 0
    failedCount: int = 0
    bodyFetchedCount: int = 0
    verifiedCount: int = 0
    summarySuccessCount: int = 0
    rejectionCounts: dict[str, int] = Field(default_factory=dict)
    sourceCoverageStatus: IntelligenceSupplyStatus = "missing"
    candidateRefreshStatus: IntelligenceSupplyStatus = "missing"
    lastCandidateFetchAt: str | None = None
    candidateCounts: dict[str, int] = Field(default_factory=dict)
    candidateSamples: list[IntelligenceCandidateSample] = Field(default_factory=list)
    queuedJobId: str | None = None
    message: str = ""
    errors: list[str] = Field(default_factory=list)


class IntelligenceRefreshTotals(BaseModel):
    objectCount: int = 0
    completedCount: int = 0
    noResultCount: int = 0
    failedCount: int = 0
    intentCount: int = 0
    fetchJobCount: int = 0
    candidateCount: int = 0
    promotedCount: int = 0
    duplicateCount: int = 0
    bodyFetchedCount: int = 0
    verifiedCount: int = 0
    summarySuccessCount: int = 0
    rejectionCounts: dict[str, int] = Field(default_factory=dict)


class IntelligenceRefreshResult(BaseModel):
    status: Literal["completed", "no_results", "failed", "partial_failed"] = "completed"
    contentKind: IntelligenceContentKind
    scopeType: Literal["all", "client", "project_module"] = "all"
    scopeId: str | None = None
    results: list[IntelligenceRefreshObjectResult] = Field(default_factory=list)
    totals: IntelligenceRefreshTotals = Field(default_factory=IntelligenceRefreshTotals)
    message: str = ""
    generatedAt: str


class IntelligenceRefreshRunRecord(BaseModel):
    id: str
    scopeType: Literal["client", "project_module", "all", ""]
    scopeId: str | None = None
    clientId: str | None = None
    projectModuleId: str | None = None
    contentKind: IntelligenceContentKind
    triggerSource: str = ""
    status: Literal["queued", "running", "completed", "failed"]
    stage: str = ""
    message: str = ""
    result: dict[str, object] = Field(default_factory=dict)
    rejectionSummary: dict[str, int] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str
    startedAt: str | None = None
    finishedAt: str | None = None


class IntelligenceDismissPayload(BaseModel):
    reasonCode: Literal["irrelevant", "inaccurate", "duplicate", "outdated", "low_value"] = "irrelevant"
    note: str = ""


class IntelligenceFollowPayload(BaseModel):
    followMode: Literal["same_theme", "same_source", "same_work_object"] = "same_theme"
    note: str = ""


class IntelligenceVerificationRuleRecord(BaseModel):
    id: str
    scopeType: IntelligenceFocusScopeType = "global"
    scopeId: str | None = None
    positiveRules: list[str] = Field(default_factory=list)
    excludeRules: list[str] = Field(default_factory=list)
    identityAnchors: list[str] = Field(default_factory=list)
    clarificationExamples: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class IntelligenceVerificationRulePayload(BaseModel):
    scopeType: IntelligenceFocusScopeType = "global"
    scopeId: str | None = None
    positiveRules: list[str] = Field(default_factory=list)
    excludeRules: list[str] = Field(default_factory=list)
    identityAnchors: list[str] = Field(default_factory=list)


class IntelligenceVerificationFeedbackPayload(BaseModel):
    targetType: Literal["item", "candidate"]
    targetId: str
    scopeType: IntelligenceFocusScopeType
    scopeId: str | None = None
    note: str


class IntelligenceTaskDraftPayload(BaseModel):
    title: str | None = None
    desc: str | None = None
    priority: Priority = "normal"
    listId: str | None = None
    dueDate: str | None = None
    ddl: str = "本周"
    ownerId: str | None = None
    ownerName: str = ""
    collaboratorIds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    note: str = ""
    ownerRoleHint: str = ""
    collaboratorRoleHints: list[str] = Field(default_factory=list)


class IntelligenceTaskDraftResponse(BaseModel):
    itemId: str
    draft: IntelligenceTaskDraftPayload


class IntelligenceTaskCreatePayload(IntelligenceTaskDraftPayload):
    title: str


class IntelligenceTaskCreateResponse(BaseModel):
    item: IntelligenceItemRecord
    task: TaskRecord


class TopicCandidateChatMessageRecord(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    createdAt: str


class IntelligenceItemChatResponse(BaseModel):
    itemId: str
    question: str
    answer: str
    generatedAt: str
    message: TopicCandidateChatMessageRecord


class IntelligenceFeedbackSummaryRecord(BaseModel):
    targetType: str
    targetLabel: str
    positiveCount: int = 0
    negativeCount: int = 0
    neutralCount: int = 0
    score: float = 0
    lastEventAt: str | None = None


class IntelligenceFeedbackEventRecord(BaseModel):
    id: str
    contentKind: str
    itemId: str | None = None
    candidateId: str | None = None
    actionType: str
    reasonCode: str = ""
    note: str = ""
    extractedTopics: list[str] = Field(default_factory=list)
    source: str = ""
    sourceDomain: str = ""
    scoreDelta: float = 0
    createdAt: str


class IntelligenceFeedbackDiagnosticsResponse(BaseModel):
    scopeType: str
    scopeId: str
    contentKind: IntelligenceContentKind | None = None
    summaries: list[IntelligenceFeedbackSummaryRecord] = Field(default_factory=list)
    events: list[IntelligenceFeedbackEventRecord] = Field(default_factory=list)


class TopicCandidateChatPayload(BaseModel):
    question: str
    history: list[TopicCandidateChatMessageRecord] = Field(default_factory=list)


class TaskAiParsePayload(BaseModel):
    """智能新建任务 — 用户粘贴自然语言文本,由 LLM 抽成结构化任务字段。

    currentDate: 前端按本地时区算的今天 YYYY-MM-DD,用于让 LLM 解算"今天/明天/下周三"。
    """

    text: str
    currentDate: str


class TaskAiParseClientCandidate(BaseModel):
    """模糊匹配到的客户候选(展示+审计用,前端目前只取首位填入)。"""

    id: str
    name: str
    score: float = 0.0


class TaskAiParseResult(BaseModel):
    """智能新建任务返回的结构化字段。

    严格约束:
    - dueDate / dueTime 只有在文本明确给出时才填,否则为 None;不按语气推断
    - clientId 仅当 fuzzy 匹配置信度足够时才填,否则保留 None 让用户手动选
    """

    title: str
    desc: str = ""
    dueDate: str | None = None
    dueTime: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    clientId: str | None = None
    clientName: str | None = None
    clientCandidates: list[TaskAiParseClientCandidate] = Field(default_factory=list)
    rawLlmGuessClientName: str | None = None


class ClientDeletePreview(BaseModel):
    """删除客户前的影响预览,让前端显示二次确认弹窗."""

    clientId: str
    name: str
    threadCount: int = 0
    messageCount: int = 0
    documentCount: int = 0
    dnaCount: int = 0
    goalCount: int = 0
    meetingCount: int = 0
    eventLineCount: int = 0
    taskCount: int = 0
    isDemoClient: bool = False


# ── v2.2 Phase 1 F1.4a · ClientFactBundle 响应模型 ──
# 镜像 backend/app/modules/client/facts.py 里的 dataclass
# 供 GET /api/v1/clients/{client_id}/fact-bundle 用


class EventLineFactResponse(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    stage: str
    summary: str
    intent: str
    current_blocker: str
    recent_decision: str
    next_step: str
    evidence_count: int
    owner_id: str | None = None
    owner_name: str | None = None
    primary_client_id: str
    primary_client_name: str
    created_at: str
    updated_at: str


class TaskFactResponse(BaseModel):
    id: str
    title: str
    description_preview: str
    status: str
    priority: str
    progress_status: str
    owner_id: str | None = None
    owner_name: str
    creator_id: str
    deadline_at: str | None = None
    due_date: str | None = None
    scheduled_start_at: str | None = None
    completed_at: str | None = None
    event_line_id: str | None = None
    business_category: str | None = None
    current_blocker: str
    next_action: str
    recent_decision: str
    evidence_count: int
    source_type: str
    source_id: str | None = None
    created_at: str
    updated_at: str


class CommitmentFactResponse(BaseModel):
    id: str
    committer: str
    recipient: str
    commitment_type: str
    content: str
    deadline: str | None = None
    status: str
    created_at: str
    updated_at: str


class DnaDocumentRefResponse(BaseModel):
    module_key: str
    title: str
    summary: str
    file_name: str
    source_kind: str
    updated_at: str
    updated_by: str
    has_full_content: bool


class AtomicFactRefResponse(BaseModel):
    id: str
    subject_text: str
    attribute: str
    value_text: str
    confidence: float
    source_v2_document_id: str | None = None
    source_v2_chunk_id: str | None = None
    evidence_text: str | None = None
    status: str
    updated_at: str


class ClientRecordResponse(BaseModel):
    """v2.2 F1.4a · 客户基础记录响应 (跟 backend/app/modules/client/types.py 对齐)"""

    id: str
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: str
    color: str
    created_at: str
    updated_at: str


class ClientFactBundleResponse(BaseModel):
    """v2.2 F1.4a · 客户完整事实包响应 — L2 共识层 endpoint 返回类型"""

    client: ClientRecordResponse
    event_lines: list[EventLineFactResponse]
    tasks: list[TaskFactResponse]
    commitments: list[CommitmentFactResponse]
    dna_documents: list[DnaDocumentRefResponse]
    atomic_facts: list[AtomicFactRefResponse]
    key_decisions: list[dict[str, object]] = Field(default_factory=list)
    snapshot_at: str
    sources: dict[str, str]
    counts: dict[str, int]
