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
WorkObjectMode = Literal["client", "project"]
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
    localWorkObjectMode: WorkObjectMode | None = None
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


class CloudDirectAccessResponse(BaseModel):
    apiBaseUrl: str
    accessToken: str


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
    workObjectMode: WorkObjectMode = "project"
    annualGoal: str = ""
    annualStrategyYear: str = ""
    annualStrategy: str = ""
    quarterPlans: list["OrgQuarterPlanRecord"] = Field(default_factory=list)
    quarterlyFocus: list[str] = Field(default_factory=list)
    leaderUserId: str | None = None
    managementUserIds: list[str] = Field(default_factory=list)
    updatedAt: str


class WorkObjectTerminologyStateRecord(BaseModel):
    localMode: WorkObjectMode | None = None
    organizationMode: WorkObjectMode | None = None
    effectiveMode: WorkObjectMode = "project"
    source: Literal["default", "local", "organization"] = "default"
    lockedByOrganization: bool = False
    needsOnboarding: bool = False
    updatedAt: str


class WorkObjectTerminologyUpdatePayload(BaseModel):
    mode: WorkObjectMode
    target: Literal["local", "organization"] = "local"


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


class WorkObjectMutationPayload(BaseModel):
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: str


ClientMutationPayload = WorkObjectMutationPayload


class WorkObjectRecord(BaseModel):
    id: str
    name: str
    alias: str
    domain: str
    type: str
    intro: str
    stage: str
    folderCount: int
    documentCount: int
    taskCount: int
    lastActivityAt: str | None = None


ClientSummary = WorkObjectRecord


class WorkObjectFolder(BaseModel):
    id: str
    workObjectId: str
    clientId: str
    label: str
    path: str
    fileCount: int
    lastScannedAt: str | None = None


ClientFolder = WorkObjectFolder


class ImportRecord(BaseModel):
    id: str
    workObjectId: str
    clientId: str
    sourcePath: str
    mode: Literal["folder", "file"]
    status: Literal["queued", "processing", "completed", "failed", "scanned"]
    importedCount: int
    skippedCount: int
    createdAt: str


class ImportPayload(BaseModel):
    workObjectId: str | None = None
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
    workObjectId: str
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
    workObjectId: str
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
    workObjectId: str
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
    workObjectId: str
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
    creatorDisplayName: str | None = None
    priority: Priority
    listId: str
    listName: str
    listColor: str
    listIds: list[str] = Field(default_factory=list)
    listNames: list[str] = Field(default_factory=list)
    ddl: str
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    workObjectId: str | None = None
    workObjectName: str | None = None
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
    ownerDisplayName: str | None = None
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
    expenseEvidenceLinks: list["TaskExpenseEvidenceLinkRecord"] = Field(default_factory=list)
    collaborators: list["TaskCollaboratorRecord"] = Field(default_factory=list)
    collaborationSummary: dict[str, int] = Field(default_factory=dict)
    pendingParticipantNames: list[str] = Field(default_factory=list)
    viewerInboxStatus: CollaboratorInboxStatus | None = None
    viewerCanConfirm: bool = False
    viewerCanReject: bool = False
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
    workObjectId: str
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
    workObjectId: str
    workObjectName: str
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
    workObjectId: str
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
    workObjectId: str
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


class TaskGroupTemplateStepAttachment(BaseModel):
    name: str
    size: int | None = None


class TaskGroupTemplateStep(BaseModel):
    title: str
    description: str = ""
    daysAfterPrevious: int = 0
    durationDays: float = 1.0
    priority: Priority = "normal"
    ownerId: str | None = None
    ownerName: str | None = None
    collaboratorIds: list[str] = Field(default_factory=list)
    collaboratorNames: list[str] = Field(default_factory=list)
    attachments: list[TaskGroupTemplateStepAttachment] = Field(default_factory=list)


class TaskGroupTemplateRecord(BaseModel):
    id: str
    name: str
    scenarioDesc: str = ""
    scope: Literal["local", "organization"] = "local"
    workObjectId: str | None = None
    clientId: str | None = None
    legacyModuleId: str | None = None
    steps: list[TaskGroupTemplateStep] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ApplyTaskGroupTemplateEventLineDraft(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    primaryWorkObjectId: str | None = None
    primaryClientId: str | None = None
    ownerId: str | None = None
    participantIds: list[str] = Field(default_factory=list)


class TaskGroupTemplateApplyStepOverride(BaseModel):
    stepIndex: int = Field(ge=0)
    title: str | None = None
    description: str | None = None
    ownerId: str | None = None
    ownerName: str | None = None
    collaboratorIds: list[str] | None = None
    collaboratorNames: list[str] | None = None
    priority: Priority | None = None
    durationDays: float | None = Field(default=None, ge=0.5)
    daysAfterPrevious: int | None = Field(default=None, ge=0)


class ApplyTaskGroupTemplatePayload(BaseModel):
    startDateTime: str
    listId: str = ""
    workObjectId: str | None = None
    clientId: str | None = None
    eventLineMode: Literal["none", "existing", "create"] = "none"
    eventLineId: str | None = None
    eventLineDraft: ApplyTaskGroupTemplateEventLineDraft | None = None
    stepOverrides: list[TaskGroupTemplateApplyStepOverride] = Field(default_factory=list)


class ApplyTaskGroupTemplateResult(BaseModel):
    createdTaskIds: list[str] = Field(default_factory=list)
    createdEventLineId: str | None = None
    createdCount: int = 0


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
    workObjectId: str
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
    description: str | None = None
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


class InboxNotificationRecord(BaseModel):
    id: str
    kind: Literal["event_line_operation"] = "event_line_operation"
    eventLineId: str | None = None
    eventLineName: str | None = None
    operationLabel: str
    actorId: str | None = None
    actorName: str
    title: str
    summary: str
    mainOwnerNames: list[str] = Field(default_factory=list)
    participantNames: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    operatedAt: str
    viewerReadAt: str | None = None
    createdAt: str
    updatedAt: str


class InboxNotificationListResponse(BaseModel):
    notifications: list[InboxNotificationRecord] = Field(default_factory=list)


class InboxAggregateResponse(BaseModel):
    pendingTasks: list[TaskRecord] = Field(default_factory=list)
    systemNotifications: list[InboxNotificationRecord] = Field(default_factory=list)
    outboundPendingTasks: list[TaskRecord] = Field(default_factory=list)


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


class TaskNotificationBatchReadPayload(BaseModel):
    taskIds: list[str] = Field(default_factory=list)


class TaskNotificationBatchReadResponse(BaseModel):
    taskIds: list[str] = Field(default_factory=list)
    updatedCount: int = 0


class InboxNotificationBatchReadPayload(BaseModel):
    notificationIds: list[str] = Field(default_factory=list)


class InboxNotificationBatchReadResponse(BaseModel):
    notificationIds: list[str] = Field(default_factory=list)
    updatedCount: int = 0


class TaskPayload(BaseModel):
    title: str
    desc: str = ""
    priority: Priority = "normal"
    listId: str
    listIds: list[str] = Field(default_factory=list)
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
    collaboratorNames: list[str] = Field(default_factory=list)
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
    listIds: list[str] | None = None
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
    collaboratorNames: list[str] | None = None
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
    description: str | None = None
    color: str | None = Field(default=None, min_length=4, max_length=16)
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


class TaskGroupTemplatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scenarioDesc: str = ""
    scope: Literal["local", "organization"] | None = None
    workObjectId: str | None = None
    clientId: str | None = None
    steps: list[TaskGroupTemplateStep] = Field(default_factory=list)


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


class WorkObjectDnaModuleRecord(BaseModel):
    workObjectId: str
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


ClientDnaModuleRecord = WorkObjectDnaModuleRecord


class ClientDnaGeneratePayload(BaseModel):
    refreshGenerated: bool = False


class ClientDnaModulesResponse(BaseModel):
    modules: list[WorkObjectDnaModuleRecord]


class ClientWorkspaceSettingsRecord(BaseModel):
    useOrgDnaInChat: bool = False
    useOrgDnaInKnowledgeQa: bool = False
    meetingPublishDefaultListId: str | None = None
    meetingPublishDefaultPriority: Priority = "normal"
    defaultGoalQuarter: str = ""
    defaultMeetingTitlePrefix: str = "客户会议"
    clientDnaModeLabel: str = "DNA"
    clientEditPermission: Literal["admin_only", "owner", "owner_and_collaborators"] = "owner_and_collaborators"
    clientDnaGenerationMode: Literal["manual", "prompt_on_material_change", "auto_draft_on_material_change"] = "prompt_on_material_change"
    knowledgeIngestMeetingNotes: bool = True
    knowledgeIngestAttachments: bool = True
    knowledgeIngestTaskReviews: bool = False
    meetingActionItemMode: Literal["candidate_only", "pending_tasks", "direct_tasks"] = "candidate_only"
    updatedAt: str


class ClientWorkspaceSettingsPayload(BaseModel):
    useOrgDnaInChat: bool | None = None
    useOrgDnaInKnowledgeQa: bool | None = None
    meetingPublishDefaultListId: str | None = None
    meetingPublishDefaultPriority: Priority | None = None
    defaultGoalQuarter: str | None = None
    defaultMeetingTitlePrefix: str | None = None
    clientDnaModeLabel: str | None = None
    clientEditPermission: Literal["admin_only", "owner", "owner_and_collaborators"] | None = None
    clientDnaGenerationMode: Literal["manual", "prompt_on_material_change", "auto_draft_on_material_change"] | None = None
    knowledgeIngestMeetingNotes: bool | None = None
    knowledgeIngestAttachments: bool | None = None
    knowledgeIngestTaskReviews: bool | None = None
    meetingActionItemMode: Literal["candidate_only", "pending_tasks", "direct_tasks"] | None = None


class TopicFocusDomainRecord(BaseModel):
    id: str
    name: str
    keywords: str = ""
    description: str = ""


class TopicSourcePreferenceRecord(BaseModel):
    id: str
    name: str
    trustLevel: Literal["high", "medium", "low"] = "medium"
    enabled: bool = True


class TopicsSettingsRecord(BaseModel):
    chineseOnly: bool = True
    requireInsightBeforeActions: bool = True
    defaultTaskOwnerMode: TopicTaskOwnerMode = "self"
    defaultTimeRange: str = "3_days"
    defaultSourceStrategy: str = "google_bing_news"
    useOrgDnaForInsight: bool = True
    useOrgDnaForTaskPlan: bool = True
    refreshCadence: Literal["manual", "daily", "weekly"] = "manual"
    focusDomains: list[TopicFocusDomainRecord] = Field(default_factory=list)
    sourcePreferences: list[TopicSourcePreferenceRecord] = Field(default_factory=list)
    candidateRetentionDays: int = 90
    updatedAt: str


class TopicsSettingsPayload(BaseModel):
    chineseOnly: bool | None = None
    requireInsightBeforeActions: bool | None = None
    defaultTaskOwnerMode: TopicTaskOwnerMode | None = None
    defaultTimeRange: str | None = None
    defaultSourceStrategy: str | None = None
    useOrgDnaForInsight: bool | None = None
    useOrgDnaForTaskPlan: bool | None = None
    refreshCadence: Literal["manual", "daily", "weekly"] | None = None
    focusDomains: list[TopicFocusDomainRecord] | None = None
    sourcePreferences: list[TopicSourcePreferenceRecord] | None = None
    candidateRetentionDays: int | None = None


class StrategicSettingsRecord(BaseModel):
    visibilityScope: Literal["admin_only", "admin_and_owner", "admin_owner_collaborators"] = "admin_and_owner"
    snapshotConfirmationEnabled: bool = True
    snapshotConfirmRoles: list[str] = Field(default_factory=lambda: ["admin", "client_owner"])
    stalledDays: int = 14
    stalledRiskLevel: Literal["watch", "risk"] = "watch"
    meetingPackSections: list[str] = Field(default_factory=lambda: [
        "client_background",
        "recent_progress",
        "key_findings",
        "risks",
        "suggested_agenda",
        "pending_decisions",
        "evidence_summary",
    ])
    evidenceMinCount: int = 2
    markUncalibratedWhenEvidenceInsufficient: bool = True
    updatedAt: str


class StrategicSettingsPayload(BaseModel):
    visibilityScope: Literal["admin_only", "admin_and_owner", "admin_owner_collaborators"] | None = None
    snapshotConfirmationEnabled: bool | None = None
    snapshotConfirmRoles: list[str] | None = None
    stalledDays: int | None = None
    stalledRiskLevel: Literal["watch", "risk"] | None = None
    meetingPackSections: list[str] | None = None
    evidenceMinCount: int | None = None
    markUncalibratedWhenEvidenceInsufficient: bool | None = None


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
    experienceVisibility: Literal["personal", "team_requires_confirmation", "team_default"] = "team_requires_confirmation"
    captureSources: dict[str, bool] = Field(default_factory=lambda: {
        "weeklyReview": True,
        "meetingNotes": True,
        "aiOverview": True,
        "taskReview": True,
        "strategicInsight": True,
    })
    handbookSources: dict[str, bool] = Field(default_factory=lambda: {
        "task": True,
        "analysis": True,
        "meeting": True,
        "strategic": True,
    })
    notificationSettings: dict[str, bool] = Field(default_factory=lambda: {
        "badgeToSelf": True,
        "xpToSelf": True,
        "importantBadgeToTeam": False,
    })
    organizationCategories: list[dict[str, str]] = Field(default_factory=lambda: [
        {"id": "experience", "name": "经验卡片", "description": "记录一次有效做法"},
        {"id": "method", "name": "方法卡片", "description": "沉淀可复用步骤"},
        {"id": "correction", "name": "纠偏卡片", "description": "记录错误、教训和修正方式"},
        {"id": "template", "name": "模板/SOP", "description": "可直接复用的流程或模板"},
    ])
    updatedAt: str


class HandbookSettingsPayload(BaseModel):
    defaultTags: list[str] | None = None
    defaultCategory: str | None = None
    allowTaskSource: bool | None = None
    allowAnalysisSource: bool | None = None
    visibilityBoundary: str | None = None
    experienceVisibility: Literal["personal", "team_requires_confirmation", "team_default"] | None = None
    captureSources: dict[str, bool] | None = None
    handbookSources: dict[str, bool] | None = None
    notificationSettings: dict[str, bool] | None = None
    organizationCategories: list[dict[str, str]] | None = None


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


class OrgDingtalkFinanceIntegrationRecord(BaseModel):
    organizationId: str | None = None
    organizationName: str | None = None
    appKey: str = ""
    operatorMobile: str = ""
    resolvedOperatorUserId: str | None = None
    enabled: bool = False
    hasAppSecret: bool = False
    syncEnabled: bool = True
    mappedTemplateNames: list[str] = Field(default_factory=list)
    configuredBy: str | None = None
    configuredAt: str | None = None
    updatedAt: str
    lastValidationStatus: Literal["idle", "success", "failed"] = "idle"
    lastValidationMessage: str | None = None


class OrgDingtalkFinanceIntegrationSavePayload(BaseModel):
    appKey: str | None = None
    appSecret: str | None = None
    operatorMobile: str | None = None
    clearAppSecret: bool = False
    syncEnabled: bool = True
    mappedTemplateNames: list[str] = Field(default_factory=list)


class ExpenseImportSourceRecord(BaseModel):
    id: str
    organizationId: str
    sourceSystem: Literal["dingtalk_finance"] = "dingtalk_finance"
    sourceInstanceId: str
    sourceTemplateCode: str | None = None
    sourceTemplateName: str | None = None
    sourceTitle: str
    applicantUserName: str = ""
    amount: float | None = None
    currency: str = "CNY"
    submittedAt: str | None = None
    approvedAt: str | None = None
    approvalStatus: str = "unknown"
    sourceUrl: str | None = None
    attachments: list["ExpenseEvidenceAttachmentImportPayload"] = Field(default_factory=list)
    rawPayload: dict[str, object] = Field(default_factory=dict)
    importedEvidenceId: str | None = None
    lastImportedAt: str | None = None
    createdAt: str
    updatedAt: str


class ExpenseImportSearchPayload(BaseModel):
    query: str = ""
    applicantUserName: str = ""
    approvalStatus: str | None = None
    submittedFrom: str | None = None
    submittedTo: str | None = None
    includeImported: bool = True
    limit: int = Field(default=20, ge=1, le=100)


class ExpenseImportSearchResponse(BaseModel):
    items: list[ExpenseImportSourceRecord] = Field(default_factory=list)
    total: int = 0
    message: str | None = None


class ExpenseEvidenceAttachmentImportPayload(BaseModel):
    sourceFileId: str | None = None
    sourceSpaceId: str | None = None
    sourceFileType: str | None = None
    fileName: str = Field(min_length=1)
    mimeType: str | None = None
    sizeBytes: int = 0
    previewUrl: str | None = None


class ExpenseEvidenceImportItemPayload(BaseModel):
    sourceInstanceId: str = Field(min_length=1)
    sourceTemplateCode: str | None = None
    sourceTemplateName: str | None = None
    sourceTitle: str = Field(min_length=1)
    applicantUserName: str = ""
    amount: float | None = None
    currency: str = "CNY"
    submittedAt: str | None = None
    approvedAt: str | None = None
    approvalStatus: str = "unknown"
    sourceUrl: str | None = None
    displayTitle: str | None = None
    normalizedCategory: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    attachments: list[ExpenseEvidenceAttachmentImportPayload] = Field(default_factory=list)
    rawPayload: dict[str, object] = Field(default_factory=dict)


class ExpenseEvidenceImportPayload(BaseModel):
    items: list[ExpenseEvidenceImportItemPayload] = Field(default_factory=list)


class ExpenseEvidenceAttachmentRecord(BaseModel):
    id: str
    expenseEvidenceId: str
    sourceFileId: str | None = None
    sourceSpaceId: str | None = None
    sourceFileType: str | None = None
    fileName: str
    mimeType: str | None = None
    sizeBytes: int = 0
    downloadStatus: Literal["not_fetched", "fetched", "failed"] = "not_fetched"
    ocrStatus: Literal["pending", "done", "failed", "skipped"] = "pending"
    ocrSummary: str | None = None
    storagePath: str | None = None
    previewUrl: str | None = None
    createdAt: str
    updatedAt: str


class ExpenseEvidenceRecord(BaseModel):
    id: str
    organizationId: str
    workObjectId: str | None = None
    sourceSystem: Literal["dingtalk_finance"] = "dingtalk_finance"
    sourceInstanceId: str
    sourceTemplateCode: str | None = None
    sourceTemplateName: str | None = None
    sourceTitle: str
    displayTitle: str
    applicantUserName: str = ""
    amount: float | None = None
    currency: str = "CNY"
    submittedAt: str | None = None
    approvedAt: str | None = None
    approvalStatus: str = "unknown"
    sourceUrl: str | None = None
    normalizedCategory: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    lastImportedAt: str | None = None
    createdByUserId: str | None = None
    updatedByUserId: str | None = None
    createdAt: str
    updatedAt: str
    attachments: list[ExpenseEvidenceAttachmentRecord] = Field(default_factory=list)


class ExpenseEvidenceUpdatePayload(BaseModel):
    workObjectId: str | None = None
    displayTitle: str | None = None
    normalizedCategory: str | None = None
    tags: list[str] | None = None
    summary: str | None = None


class ExpenseEvidenceImportResult(BaseModel):
    imported: list[ExpenseEvidenceRecord] = Field(default_factory=list)
    importedCount: int = 0
    skippedCount: int = 0


class EventLineExpenseEvidenceLinkRecord(BaseModel):
    id: str
    eventLineId: str
    evidenceId: str
    note: str = ""
    linkedByUserId: str | None = None
    linkedByUserName: str | None = None
    createdAt: str
    evidence: ExpenseEvidenceRecord | None = None


class EventLineExpenseEvidenceLinkPayload(BaseModel):
    evidenceId: str = Field(min_length=1)
    note: str = ""


class TaskExpenseEvidenceLinkRecord(BaseModel):
    id: str
    taskId: str
    evidenceId: str
    note: str = ""
    linkedByUserId: str | None = None
    linkedByUserName: str | None = None
    createdAt: str
    evidence: ExpenseEvidenceRecord | None = None


class TaskExpenseEvidenceLinkPayload(BaseModel):
    evidenceId: str = Field(min_length=1)
    note: str = ""


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
    desc: str = ""
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
    ownerIds: list[str] = Field(default_factory=list)
    ownerNames: list[str] = Field(default_factory=list)
    primaryWorkObjectId: str | None = None
    primaryWorkObjectName: str | None = None
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
    expenseEvidenceLinks: list["EventLineExpenseEvidenceLinkRecord"] = Field(default_factory=list)
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
    ownerIds: list[str] = Field(default_factory=list)
    primaryWorkObjectId: str | None = None
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
    ownerIds: list[str] | None = None
    primaryWorkObjectId: str | None = None
    primaryClientId: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] | None = None


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
    workObjectId: str
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


class WorkObjectAnalysisEvidenceSummaryRecord(BaseModel):
    summaryText: str = ""
    masterHitCount: int = 0
    surrogateHitCount: int = 0
    rawChunkHitCount: int = 0
    drillthroughUsed: bool = False
    coveredCategories: list[str] = Field(default_factory=list)
    missingCategories: list[str] = Field(default_factory=list)
    evidenceList: list[KnowledgeSearchHitRecord] = Field(default_factory=list)


ClientAnalysisEvidenceSummaryRecord = WorkObjectAnalysisEvidenceSummaryRecord


class WorkObjectAnalysisRunRecord(BaseModel):
    id: str
    workObjectId: str
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
    evidenceSummary: WorkObjectAnalysisEvidenceSummaryRecord = Field(default_factory=WorkObjectAnalysisEvidenceSummaryRecord)
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


ClientAnalysisRunRecord = WorkObjectAnalysisRunRecord


class WorkObjectWorkspaceResponse(BaseModel):
    workObject: WorkObjectRecord
    client: WorkObjectRecord
    folders: list[WorkObjectFolder]
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
    analysisRuns: list[WorkObjectAnalysisRunRecord] = Field(default_factory=list)
    meetings: list[MeetingSummary]
    goals: list[GoalRecord]
    dnaModules: list[WorkObjectDnaModuleRecord] = Field(default_factory=list)
    projectModules: list[ProjectModuleRecord] = Field(default_factory=list)
    projectFlows: list[ProjectFlowRecord] = Field(default_factory=list)
    dnaTerms: list[DnaTerm]
    relatedTasks: list[TaskRecord]
    notebookSummary: OrganizationNotebookSnapshot | None = None
    memoryStatus: MemoryStatus | None = None


ClientWorkspaceResponse = WorkObjectWorkspaceResponse


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
    sourceType: str | None = None
    surrogateMdPath: str | None = None


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
