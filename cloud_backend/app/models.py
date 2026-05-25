from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


AccountStatus = Literal["pending", "approved", "rejected", "disabled"]
MembershipStatus = Literal["none", "pending", "approved", "rejected"]
PrimaryRole = Literal["admin", "employee"]
Priority = Literal["low", "normal", "high"]
TaskProgressStatus = Literal["inbox", "todo", "doing", "done", "rejected"]
CollaboratorInboxStatus = Literal["pending", "accepted", "returned"]
TaskDueDatePreset = Literal["today", "none"]
TaskListSortMode = Literal["dueDate", "priority", "manual"]
TaskViewMode = Literal["inbox", "list", "calendar", "review"]
PlanLevel = Literal["ceo", "director", "manager", "project"]
ReviewScopeType = Literal["employee", "team", "org"]
ContentDomain = Literal["work", "personal"]
VisibilityScope = Literal["self", "team", "department", "org"]
OrgRoleLevel = Literal["employee", "supervisor", "department_lead", "organization_lead"]
OrgReportingLineType = Literal["business", "administrative"]
OrgTaskEditScope = Literal["self", "manager", "department", "organization"]
OrgTaskControlLevel = Literal["normal", "leader_control", "department_control", "organization_control"]
OrgRuleActorScope = Literal["assignee", "manager", "department_lead", "organization_lead", "creator"]
OrgWorkflowTriggerType = Literal["weekly_followup", "task_created", "meeting_closed", "client_update", "manual"]
ConsultationKnowledgeTarget = Literal["vector_memory", "document_archive"]
ConsultationKnowledgeRequestStatus = Literal["pending", "processing", "completed", "failed"]
FeedbackCategory = Literal["bug", "lag", "inaccurate", "suggestion"]
FeedbackSeverity = Literal["low", "medium", "high", "critical"]
FeedbackStatus = Literal["open", "triaging", "in_progress", "resolved", "wontfix"]
ReleaseChannel = Literal["internal", "beta", "stable"]
ReleaseStatus = Literal["draft", "testing", "published", "rolled_back"]
SmartInputIntent = Literal["task_schedule", "record_note", "unknown"]


class SessionUser(BaseModel):
    id: str
    organizationId: str
    organizationName: str | None = None
    email: EmailStr
    phone: str | None = None
    fullName: str
    primaryRole: PrimaryRole
    accountStatus: AccountStatus
    membershipStatus: MembershipStatus = "approved"
    membershipRejectedReason: str | None = None
    departmentId: str | None = None
    departmentName: str | None = None
    avatarUrl: str | None = None
    isDepartmentLead: bool = False


class AuthTokenResponse(BaseModel):
    accessToken: str
    refreshToken: str | None = None
    tokenType: str = "bearer"
    expiresInSeconds: int = 12 * 60 * 60
    user: SessionUser


class RegisterPayload(BaseModel):
    email: EmailStr
    phone: str | None = None
    fullName: str
    password: str = Field(min_length=8)
    organizationName: str | None = None
    inviteCode: str | None = None
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False


class LoginPayload(BaseModel):
    email: EmailStr | None = None
    identifier: str | None = None
    password: str


class ChangePasswordPayload(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8)


class UpdateProfilePayload(BaseModel):
    fullName: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    phone: str | None = None


class AdminResetPasswordPayload(BaseModel):
    newPassword: str = Field(min_length=8)


class RefreshPayload(BaseModel):
    refreshToken: str = Field(min_length=1)


class FeishuBindingRelaySessionCreatePayload(BaseModel):
    state: str = Field(min_length=1)
    expiresAt: str = Field(min_length=1)


class FeishuBindingRelaySessionStatusRecord(BaseModel):
    state: str
    status: Literal["pending", "authorized", "expired", "error"] = "pending"
    expiresAt: str
    authorizedAt: str | None = None
    errorMessage: str | None = None
    code: str | None = None


class OrgMembershipSummaryRecord(BaseModel):
    hasOrganization: bool = False
    organizationId: str | None = None
    organizationName: str | None = None
    organizationSlug: str | None = None
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
    currentUserRole: PrimaryRole | None = None
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


# 手机端"飞书绑定"入口期待的 OAuth 风格响应（mobile FeishuUserBinding 同构）。
# 目前 cloud_backend 上 OAuth 绑定流程未实现，本类型用于 stub 路由，让 mobile
# profile 页一进入不再 404 弹 Alert。后续真正接入 OAuth 时只需替换 stub。
class FeishuUserBindingRecord(BaseModel):
    linked: bool = False
    readyForAuthorization: bool = False
    appId: str = ""
    userId: str
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


class FeishuUserBindingStartResult(BaseModel):
    authorizeUrl: str = ""
    state: str = ""
    expiresAt: str = ""
    callbackUrl: str = ""
    qrReady: bool = False
    qrBlockedReason: str | None = None


class FeishuTaskNotificationRecord(BaseModel):
    id: str
    organizationId: str
    taskId: str
    eventType: Literal["created", "key_fields_changed", "content_fields_changed"]
    recipientUserId: str
    recipientOpenId: str | None = None
    deliveryStatus: Literal["sent", "skipped_unbound", "failed"]
    deliveryMessage: str = ""
    changedFields: list[str] = Field(default_factory=list)
    createdAt: str


class FeishuBadgeNotificationPayload(BaseModel):
    badgeId: str = Field(min_length=1)
    badgeName: str = Field(min_length=1)
    categoryName: str = ""
    badgeDescription: str = ""
    xp: int = 0
    unlockedAt: str | None = None


class FeishuNotificationDispatchRecord(BaseModel):
    id: str
    messageType: str
    objectType: str
    objectId: str
    recipientUserId: str
    deliveryStatus: str
    deliveryChannel: str = ""
    deliveryMessage: str = ""
    dedupeKey: str | None = None
    createdAt: str
    updatedAt: str
    sentAt: str | None = None


FeishuSyncStatus = Literal[
    "idle",
    "not_configured",
    "skipped",
    "time_invalid",
    "queued",
    "syncing",
    "synced",
    "failed",
]


class FeishuSyncStatusRecord(BaseModel):
    localType: str
    localId: str
    remoteType: str
    remoteId: str | None = None
    remoteUrl: str | None = None
    status: FeishuSyncStatus = "idle"
    message: str = ""
    lastSyncedAt: str | None = None
    updatedAt: str
    details: dict[str, object] = Field(default_factory=dict)


class FeishuTaskCalendarSyncPayload(BaseModel):
    notify: bool = False


class FeishuDocumentSyncPayload(BaseModel):
    localType: str = "document"
    localId: str
    title: str
    content: str
    clientId: str | None = None
    triggerSource: str = "document_saved"
    notifyOnCreate: bool = False


class RolePayload(BaseModel):
    role: PrimaryRole


class EmployeeDepartmentPayload(BaseModel):
    departmentId: str | None = None


class RejectPayload(BaseModel):
    reason: str = ""


class EmployeeRecord(BaseModel):
    id: str
    email: EmailStr
    phone: str | None = None
    fullName: str
    primaryRole: PrimaryRole
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
    # 机器人同事: 让 directory 同一接口把 bot 与人一并带出, 两端零额外接入即可见.
    isBot: bool = False
    actorId: str | None = None
    handle: str | None = None


class OrgBotReportingRecord(BaseModel):
    reportToCreator: bool = True
    reportToDepartmentLead: bool = True
    reportToCeo: bool = True
    departmentLeaderUserIds: list[str] = Field(default_factory=list)
    ceoUserIds: list[str] = Field(default_factory=list)
    approvalMode: str = "any_one"


class OrgBotCapabilityRecord(BaseModel):
    capabilityKey: str
    enabled: bool = False
    approvalRequired: bool = True
    approvalPolicy: str = "supervisor_required"


class OrgBotRecord(BaseModel):
    id: str
    displayName: str
    handle: str
    actorId: str
    actorType: str = "internal_ai_agent"
    departmentId: str | None = None
    departmentName: str = ""
    description: str = ""
    status: str = "active"
    createdByUserId: str | None = None
    tokenPrefix: str = ""
    tokenRotatedAt: str | None = None
    hasToken: bool = False
    reporting: OrgBotReportingRecord = Field(default_factory=OrgBotReportingRecord)
    capabilities: list[OrgBotCapabilityRecord] = Field(default_factory=list)
    createdAt: str = ""
    updatedAt: str = ""
    # 仅创建/轮换时返回一次明文 token; 列表/详情恒为 None.
    tokenPlain: str | None = None


class OrgBotCreatePayload(BaseModel):
    displayName: str
    handle: str | None = None
    departmentId: str | None = None
    departmentName: str = ""
    description: str = ""
    reporting: OrgBotReportingRecord | None = None
    capabilities: list[OrgBotCapabilityRecord] | None = None


class OrgBotUpdatePayload(BaseModel):
    displayName: str | None = None
    departmentId: str | None = None
    departmentName: str | None = None
    description: str | None = None
    status: str | None = None
    reporting: OrgBotReportingRecord | None = None
    capabilities: list[OrgBotCapabilityRecord] | None = None
    rotateToken: bool = False


class MaintenanceModeStatus(BaseModel):
    available: bool
    active: bool
    canEnter: bool
    canManagePermissions: bool
    organizationId: str | None = None
    userId: str | None = None
    reason: str | None = None


class MaintenanceMemberPermission(BaseModel):
    userId: str
    fullName: str
    email: str
    primaryRole: PrimaryRole
    authorized: bool
    canManagePermissions: bool


class MaintenancePermissionMemberPayload(BaseModel):
    userId: str
    authorized: bool
    canManagePermissions: bool = False


class MaintenancePermissionUpdatePayload(BaseModel):
    members: list[MaintenancePermissionMemberPayload] = Field(default_factory=list)


class MaintenanceAuditPayload(BaseModel):
    action: str
    detail: dict[str, object] = Field(default_factory=dict)
    targetUserId: str | None = None


class DepartmentOption(BaseModel):
    id: str
    name: str
    color: str


class OrgInviteResolveResult(BaseModel):
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


class ConsultationKnowledgeRequestCreatePayload(BaseModel):
    target: ConsultationKnowledgeTarget
    question: str = ""
    answer: str = Field(min_length=1)
    clientId: str | None = None
    clientName: str | None = None
    taskId: str | None = None
    eventLineId: str | None = None


class ConsultationKnowledgeRequestUpdatePayload(BaseModel):
    status: Literal["processing", "completed", "failed"]
    errorMessage: str = ""
    localDocumentId: str | None = None
    localDocumentPath: str | None = None


class ConsultationKnowledgeRequestRecord(BaseModel):
    id: str
    answerId: str
    organizationId: str
    target: ConsultationKnowledgeTarget
    status: ConsultationKnowledgeRequestStatus = "pending"
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


class SoftwareFeedbackCreatePayload(BaseModel):
    category: FeedbackCategory
    severity: FeedbackSeverity = "medium"
    title: str = Field(min_length=1)
    description: str = ""
    appVersion: str | None = None
    platform: str | None = None
    pageRoute: str | None = None
    deviceInfo: str | None = None
    logExcerpt: str | None = None
    screenshotPath: str | None = None
    clientId: str | None = None
    taskId: str | None = None


class SoftwareFeedbackUpdatePayload(BaseModel):
    status: FeedbackStatus | None = None
    severity: FeedbackSeverity | None = None
    assigneeUserId: str | None = None
    targetVersion: str | None = None
    resolutionNote: str | None = None


class SoftwareFeedbackRecord(BaseModel):
    id: str
    organizationId: str
    reporterUserId: str | None = None
    reporterName: str = ""
    category: FeedbackCategory
    severity: FeedbackSeverity = "medium"
    status: FeedbackStatus = "open"
    title: str = ""
    description: str = ""
    appVersion: str | None = None
    platform: str | None = None
    pageRoute: str | None = None
    deviceInfo: str | None = None
    logExcerpt: str | None = None
    screenshotPath: str | None = None
    clientId: str | None = None
    taskId: str | None = None
    targetVersion: str | None = None
    assigneeUserId: str | None = None
    resolutionNote: str | None = None
    resolvedAt: str | None = None
    createdAt: str
    updatedAt: str


class AppCheckinPayload(BaseModel):
    installId: str = Field(min_length=1)
    platform: str = ""
    arch: str = ""
    appVersion: str = ""
    channel: str = "stable"


class AppInstallRecord(BaseModel):
    installId: str
    organizationId: str
    userId: str | None = None
    platform: str = ""
    arch: str = ""
    appVersion: str = ""
    channel: str = "stable"
    firstSeenAt: str
    lastSeenAt: str


class ReleaseCreatePayload(BaseModel):
    version: str = Field(min_length=1)
    channel: ReleaseChannel = "stable"
    platforms: list[str] = Field(default_factory=list)
    forceUpdate: bool = False
    changelogUser: str = ""
    changelogInternal: str = ""


class ReleaseUpdatePayload(BaseModel):
    status: ReleaseStatus | None = None
    channel: ReleaseChannel | None = None
    platforms: list[str] | None = None
    forceUpdate: bool | None = None
    changelogUser: str | None = None
    changelogInternal: str | None = None


class ReleaseRecord(BaseModel):
    id: str
    version: str
    channel: ReleaseChannel = "stable"
    status: ReleaseStatus = "draft"
    platforms: list[str] = Field(default_factory=list)
    forceUpdate: bool = False
    changelogUser: str = ""
    changelogInternal: str = ""
    createdByUserId: str | None = None
    publishedAt: str | None = None
    createdAt: str
    updatedAt: str


class UpdatePolicyResponse(BaseModel):
    hasUpdate: bool = False
    version: str | None = None
    forceUpdate: bool = False
    changelogUser: str = ""
    publishedAt: str | None = None


class TaskAttachmentTranscriptionResponse(BaseModel):
    attachmentId: str
    transcript: str
    documentRequest: ConsultationKnowledgeRequestRecord


class ConsultationChatPayload(BaseModel):
    message: str
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    taskId: str | None = None
    taskTitle: str | None = None
    taskContext: str | None = None
    workspaceContext: str | None = None
    eventLineContext: str | None = None
    taskBoardContext: str | None = None
    understandingContext: str | None = None
    sourceLabels: list[str] = Field(default_factory=list)
    missingEventLineHint: str | None = None


class ConsultationContextQualityRecord(BaseModel):
    level: Literal["none", "thin", "partial", "rich"] = "none"
    availableSources: list[str] = Field(default_factory=list)
    missingSources: list[str] = Field(default_factory=list)
    staleSources: list[str] = Field(default_factory=list)
    contextBundleHash: str | None = None


class ConsultationEvidenceRecord(BaseModel):
    id: str
    type: Literal[
        "workspace",
        "client_dna",
        "event_line",
        "meeting",
        "task",
        "knowledge_surrogate",
        "cockpit",
        "thread_snapshot",
        "task_board",
        "client_name",
        "understanding",
        "entity",
        "relation",
        "atomic_fact",
        "contradiction",
        "glossary_term",
    ]
    title: str
    updatedAt: str | None = None
    snippet: str | None = None


class ConsultationMissingContextRecord(BaseModel):
    type: Literal[
        "client_dna",
        "workspace",
        "event_line",
        "meeting",
        "person_profile",
        "project_background",
        "strategic_cockpit",
        "knowledge_surrogate",
        "task_board",
        "understanding",
    ]
    message: str


class ConsultationChatResponse(BaseModel):
    reply: str
    model: str | None = None
    answerMode: Literal["grounded", "limited_context", "missing_context", "out_of_scope", "error"] | None = None
    contextQuality: ConsultationContextQualityRecord | None = None
    evidence: list[ConsultationEvidenceRecord] = Field(default_factory=list)
    missingContext: list[ConsultationMissingContextRecord] = Field(default_factory=list)


class MobileCapabilityRecord(BaseModel):
    consultationChat: bool = True
    clientWorkspace: bool = False
    strategicCockpit: bool = False
    knowledgeMirror: bool = False
    contextBundle: bool = False
    understandingMirror: bool = False
    consultationPayloadVersion: str = "v2"
    updatedAt: str


class MobileContextSourceStatusRecord(BaseModel):
    source: str
    available: bool = False
    status: Literal["ready", "partial", "missing", "unavailable"] = "missing"
    detail: str | None = None
    updatedAt: str | None = None


class MobileWorkspaceCompatClientRecord(BaseModel):
    id: str
    name: str
    updatedAt: str | None = None


class MobileWorkspaceCompatItemRecord(BaseModel):
    id: str
    title: str
    summary: str = ""
    subtitle: str = ""
    updatedAt: str | None = None


class MobileWorkspaceCompatTaskRecord(BaseModel):
    id: str
    title: str
    status: str = ""
    clientName: str | None = None
    eventLineName: str | None = None
    nextAction: str | None = None


class MobileWorkspaceKnowledgeStatusRecord(BaseModel):
    status: Literal["ready", "partial", "missing"] = "missing"
    statusLabel: str = "资料未同步"
    summary: str = ""
    missingSources: list[str] = Field(default_factory=list)
    updatedAt: str | None = None


class MobileWorkspaceCompatResponse(BaseModel):
    client: MobileWorkspaceCompatClientRecord
    status: Literal["rich", "partial", "missing"] = "missing"
    updatedAt: str | None = None
    goals: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    meetings: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    documentCards: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    latestOpenQuestions: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    latestConflicts: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    relatedTasks: list[MobileWorkspaceCompatTaskRecord] = Field(default_factory=list)
    knowledgeStatus: MobileWorkspaceKnowledgeStatusRecord | None = None
    missingSources: list[str] = Field(default_factory=list)
    sourceAvailability: list[MobileContextSourceStatusRecord] = Field(default_factory=list)


class MobileCockpitHeadlineRecord(BaseModel):
    summary: str = ""


class MobileCockpitSummaryItemRecord(BaseModel):
    summary: str = ""
    updatedAt: str | None = None


class MobileStrategicCockpitCompatResponse(BaseModel):
    clientId: str
    clientName: str
    status: Literal["rich", "partial", "missing"] = "missing"
    updatedAt: str | None = None
    headline: MobileCockpitHeadlineRecord = Field(default_factory=MobileCockpitHeadlineRecord)
    health: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    twoWeekChanges: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    pendingDecisions: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    pendingMaterials: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    missingSources: list[str] = Field(default_factory=list)
    sourceAvailability: list[MobileContextSourceStatusRecord] = Field(default_factory=list)


class CloudKnowledgeMirrorPublishItemPayload(BaseModel):
    clientId: str
    sourceType: Literal[
        "workspace_snapshot",
        "client_dna",
        "event_line_snapshot",
        "meeting_summary",
        "knowledge_surrogate",
        "strategic_cockpit",
        "client_understanding",
    ]
    sourceId: str
    snapshotVersion: int = 1
    snapshotHash: str
    updatedAt: str
    publishedAt: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    evidenceRefs: list[str] = Field(default_factory=list)


class MobileClientUnderstandingEntityRecord(BaseModel):
    id: str
    name: str
    type: str = ""
    aliases: list[str] = Field(default_factory=list)
    mentions: int = 0
    confidence: float | None = None
    updatedAt: str | None = None


class MobileClientUnderstandingRelationRecord(BaseModel):
    id: str
    subject: str
    predicate: str
    object: str
    confidence: float | None = None
    evidenceCount: int = 0
    updatedAt: str | None = None


class MobileClientUnderstandingFactRecord(BaseModel):
    id: str
    statement: str
    semanticType: str = ""
    confidence: float | None = None
    freshness: float | None = None
    sourceCount: int = 0
    updatedAt: str | None = None


class MobileClientUnderstandingContradictionRecord(BaseModel):
    id: str
    topic: str
    conflictingStatements: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"] | None = None
    updatedAt: str | None = None


class MobileClientUnderstandingGlossaryRecord(BaseModel):
    id: str
    term: str
    definition: str = ""
    aliases: list[str] = Field(default_factory=list)
    updatedAt: str | None = None


class MobileClientUnderstandingFreshnessRecord(BaseModel):
    halfLifeDays: float | None = None
    score: float | None = None


class MobileClientUnderstandingResponse(BaseModel):
    clientId: str
    status: Literal["ready", "partial", "missing"] = "missing"
    updatedAt: str | None = None
    snapshotHash: str | None = None
    entities: list[MobileClientUnderstandingEntityRecord] = Field(default_factory=list)
    relations: list[MobileClientUnderstandingRelationRecord] = Field(default_factory=list)
    atomicFacts: list[MobileClientUnderstandingFactRecord] = Field(default_factory=list)
    contradictions: list[MobileClientUnderstandingContradictionRecord] = Field(default_factory=list)
    glossary: list[MobileClientUnderstandingGlossaryRecord] = Field(default_factory=list)
    freshness: MobileClientUnderstandingFreshnessRecord | None = None


class CloudKnowledgeMirrorPublishPayload(BaseModel):
    items: list[CloudKnowledgeMirrorPublishItemPayload] = Field(default_factory=list)


class CloudKnowledgeMirrorPublishResultRecord(BaseModel):
    publishedCount: int = 0
    clientIds: list[str] = Field(default_factory=list)
    sourceTypes: list[str] = Field(default_factory=list)
    publishedAt: str


class SmartTaskDraftRecord(BaseModel):
    title: str | None = None
    dueDate: str | None = None
    endDate: str | None = None
    dueTime: str | None = None
    durationMinutes: int | None = None
    location: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectQuery: str | None = None
    eventLineQuery: str | None = None


class SmartTaskDraftResponse(BaseModel):
    transcript: str
    intent: SmartInputIntent = "task_schedule"
    draft: SmartTaskDraftRecord = Field(default_factory=SmartTaskDraftRecord)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0


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


class MentionCandidate(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    primaryRole: PrimaryRole
    isSelf: bool = False


class ClientSummaryRecord(BaseModel):
    id: str
    name: str
    alias: str | None = None
    type: str = "client"


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
    defaultReviewScope: ContentDomain = "work"
    autoAssignSelf: bool = True
    updatedAt: str


class TaskCollaboratorRecord(BaseModel):
    userId: str
    fullName: str
    # NOTE: kept as plain str (not EmailStr) because the directory holds placeholder addresses
    # for archived employees like "archived+xxx@klngo.invalid" — RFC reserves ".invalid" TLD so
    # EmailStr would reject them and bubble a 500 to every POST /api/v1/tasks that touches such
    # a collaborator. Display layer should still treat this as best-effort contact info.
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


class TaskRecord(BaseModel):
    id: str
    title: str
    description: str
    creatorId: str
    creatorName: str
    listName: str
    listColor: str
    ownerId: str | None = None
    ownerName: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
    reminderMinutesBefore: int | None = None  # 5/29 任务提醒(跨端共享): 0=准时 5=提前5分 None=不提醒
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    priority: Priority
    listId: str
    progressStatus: TaskProgressStatus
    sourceType: str
    sourceId: str | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    completionNote: str | None = None
    note: str | None = None
    evidenceCount: int = 0
    tags: list[TaskTagRecord]
    attachments: list["TaskAttachmentRecord"] = Field(default_factory=list)
    collaborators: list[TaskCollaboratorRecord]
    collaborationSummary: dict[str, int]
    viewerInboxStatus: CollaboratorInboxStatus | None = None
    orgContext: "TaskOrgContextRecord | None" = None
    createdAt: str
    updatedAt: str


class TaskAttachmentRecord(BaseModel):
    id: str
    taskId: str
    clientId: str | None = None
    eventLineId: str | None = None
    title: str
    summary: str | None = None
    path: str
    kind: str
    source: str
    mimeType: str | None = None
    sizeBytes: int = 0
    durationSeconds: int = 0
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


class TaskBoardResponse(BaseModel):
    tasks: list[TaskRecord]
    lists: list[TaskListRecord]
    tags: list[TaskTagRecord] = Field(default_factory=list)
    commonTags: list[str]


class TaskCreatePayload(BaseModel):
    id: str | None = None
    title: str
    description: str = ""
    priority: Priority = "normal"
    listId: str
    startDate: str | None = None
    dueDate: str | None = None
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
    reminderMinutesBefore: int | None = None  # 5/29 任务提醒(跨端共享): 0=准时 5=提前5分 None=不提醒
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    collaboratorIds: list[str] = Field(default_factory=list)
    ownerId: str | None = None
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
    description: str | None = None
    priority: Priority | None = None
    listId: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
    reminderMinutesBefore: int | None = None  # 5/29 任务提醒(跨端共享): 0=准时 5=提前5分 None=不提醒
    durationMinutes: int | None = None
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] | None = None
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    progressStatus: TaskProgressStatus | None = None
    collaboratorIds: list[str] | None = None
    ownerId: str | None = None
    tagIds: list[str] | None = None
    tags: list[str] | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int | None = None


# P7：clients 云端镜像（multi-tenant）
#   ClientRecord：cloud GET 返回
#   ClientCreatePayload：local _try_cloud_sync_client 上传时用
#   ClientUpdatePayload：local 更新时用
class ClientRecord(BaseModel):
    id: str
    organizationId: str
    creatorId: str
    name: str
    alias: str = ""
    domain: str = "项目"
    type: str = "项目"
    intro: str = ""
    stage: str = "待导入资料"
    color: str = "#5B7BFE"
    relatedUserIds: list[str] = Field(default_factory=list)
    isDataCenterIncluded: bool = True
    createdAt: str
    updatedAt: str


class ClientCreatePayload(BaseModel):
    id: str | None = None  # local 端的 client.id，cloud 复用同一个 id 方便对账
    name: str
    alias: str = ""
    domain: str = "项目"
    type: str = "项目"
    intro: str = ""
    stage: str = "待导入资料"
    color: str = "#5B7BFE"
    relatedUserIds: list[str] = Field(default_factory=list)
    isDataCenterIncluded: bool = True


class ClientUpdatePayload(BaseModel):
    name: str | None = None
    alias: str | None = None
    domain: str | None = None
    type: str | None = None
    intro: str | None = None
    stage: str | None = None
    color: str | None = None
    relatedUserIds: list[str] | None = None
    isDataCenterIncluded: bool | None = None


class TaskPlanLinkUpsertPayload(BaseModel):
    departmentPlanItemId: str | None = None
    focusItemId: str | None = None
    linkedBy: Literal["ai", "manager", "rule"] = "manager"
    confidence: float = 1.0


class TaskReturnPayload(BaseModel):
    reason: str = Field(min_length=1)


class TaskCompletionReviewPayload(BaseModel):
    reviewNote: str = Field(min_length=1)


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


class EventLineDetailRecord(BaseModel):
    eventLine: EventLineRecord
    tasks: list[TaskRecord] = Field(default_factory=list)
    activities: list[EventLineActivityRecord] = Field(default_factory=list)


class EventLineReportAttachmentRecord(BaseModel):
    id: str
    taskId: str
    documentId: str | None = None
    sourceKind: Literal["task_attachment", "event_line_attachment", "meeting_attachment", "calendar_attachment"] | None = None
    title: str
    fileName: str | None = None
    kind: str
    mimeType: str | None = None
    sizeBytes: int = 0
    downloadUrl: str
    openUrl: str | None = None
    actorName: str | None = None
    createdAt: str
    parseStatus: str | None = None
    parsedPreview: str = ""
    chunkCount: int = 0
    sectionCount: int = 0


class EventLineTimelineNodeRecord(BaseModel):
    id: str
    kind: Literal[
        "project_start",
        "material_intake",
        "project_review",
        "continuing_task",
        "admin_archive",
        "needs_review",
        "system_trace",
    ]
    title: str
    time: str
    timeRange: dict[str, str] = Field(default_factory=dict)
    summary: str
    sourceTaskIds: list[str] = Field(default_factory=list)
    sourceTaskId: str = ""
    sourceActivityIds: list[str] = Field(default_factory=list)
    attachments: list[EventLineReportAttachmentRecord] = Field(default_factory=list)
    materialCount: int = 0
    includeInReport: bool = True
    evidenceSummary: str = ""
    warnings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    actorName: str | None = None
    ownerName: str | None = None


class EventLineReportSnapshotRecord(BaseModel):
    eventLine: EventLineRecord
    activities: list[EventLineActivityRecord]
    tasks: list[TaskRecord] = Field(default_factory=list)
    attachments: list[EventLineReportAttachmentRecord] = Field(default_factory=list)
    timelineNodes: list[EventLineTimelineNodeRecord] = Field(default_factory=list)
    participantNames: list[str] = Field(default_factory=list)
    snapshotAt: str


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


class EventLineImportActivityPayload(BaseModel):
    id: str = Field(min_length=1)
    sourceType: Literal["task_activity", "meeting", "support_request", "review", "attachment", "manual_note"]
    sourceId: str = Field(min_length=1)
    happenedAt: str = Field(min_length=1)
    actorId: str | None = None
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class EventLineImportPayload(BaseModel):
    id: str = Field(min_length=1)
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
    evidenceCount: int = 0
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryClientName: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] = Field(default_factory=list)
    closedAt: str | None = None
    closedByUserId: str | None = None
    createdAt: str = Field(min_length=1)
    updatedAt: str = Field(min_length=1)
    activities: list[EventLineImportActivityPayload] = Field(default_factory=list)


class EventLineImportBatchPayload(BaseModel):
    eventLines: list[EventLineImportPayload] = Field(default_factory=list)


class EventLineImportItemResult(BaseModel):
    id: str
    name: str
    status: Literal["imported", "skipped"]
    reason: str | None = None
    importedActivityCount: int = 0


class EventLineImportResultRecord(BaseModel):
    requested: int = 0
    imported: int = 0
    skipped: int = 0
    updatedAt: str
    items: list[EventLineImportItemResult] = Field(default_factory=list)


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


class OrgAiConfigRecord(BaseModel):
    orgId: str
    aiProvider: str
    aiProviderLabel: str = ""
    aiBaseUrl: str = ""
    aiModel: str
    hasApiKey: bool
    configuredBy: str | None = None
    updatedAt: str


class OrgAiConfigUpdatePayload(BaseModel):
    aiProvider: str = Field(min_length=1)
    aiProviderLabel: str = ""
    aiBaseUrl: str = ""
    aiModel: str = ""
    apiKey: str | None = None
    clearApiKey: bool = False


class OrgAiConfigSecretRecord(BaseModel):
    """Only returned to authenticated org members — contains decrypted key."""
    orgId: str
    aiProvider: str
    aiProviderLabel: str = ""
    aiBaseUrl: str = ""
    aiModel: str
    apiKey: str
    updatedAt: str


ObjectStorageProvider = Literal["volcano_tos", "aliyun_oss", "aws_s3"]


class OrgObjectStorageConfigRecord(BaseModel):
    orgId: str
    provider: str = ""
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    hasCredentials: bool = False
    configuredBy: str | None = None
    updatedAt: str


class OrgObjectStorageConfigUpdatePayload(BaseModel):
    provider: ObjectStorageProvider
    credentials: dict[str, str] = Field(default_factory=dict)
    extraConfig: dict[str, str] = Field(default_factory=dict)
    enabled: bool = False
    clearCredentials: bool = False


class OrgObjectStorageConfigSecretRecord(OrgObjectStorageConfigRecord):
    """Only returned to authenticated org members for local backend use."""
    credentials: dict[str, str] = Field(default_factory=dict)


class TaskNotePayload(BaseModel):
    note: str


class TaskTagMutationPayload(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=20)
    color: str | None = None
    scope: Literal["org", "self"] = "org"
    archived: bool | None = None


class TaskListMutationPayload(BaseModel):
    id: str | None = None
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
    defaultReviewScope: ContentDomain | None = None
    autoAssignSelf: bool | None = None


class ReviewDashboardEvidenceRefRecord(BaseModel):
    sourceType: Literal["task", "meeting", "support_request", "attachment", "clarification", "event_line", "notebook", "event_line_memory"]
    sourceId: str
    title: str
    summary: str | None = None


class ReviewDashboardCardTargetRecord(BaseModel):
    targetType: Literal["event_line", "task_view", "meeting", "support_request", "attachment_group"]
    targetId: str
    targetLabel: str | None = None
    targetFilters: dict[str, object] = Field(default_factory=dict)
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


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


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    organizationCount: int
    employeeCount: int
    taskCount: int


class PlanNodeRecord(BaseModel):
    id: str
    level: PlanLevel
    title: str
    summary: str
    status: str
    ownerUserId: str | None = None
    ownerName: str | None = None
    ownerUnitId: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None


class WeeklyReviewEntryRecord(BaseModel):
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
    status: Literal["inbox", "todo", "doing", "done", "rejected"]
    startDate: str | None = None
    dueDate: str | None = None
    deadlineAt: str | None = None
    scheduledStartAt: str | None = None
    scheduledEndAt: str | None = None
    completedAt: str | None = None
    createdAt: str
    completionNote: str | None = None
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


class ManagementSignalCardRecord(BaseModel):
    id: str
    reviewId: str
    userId: str
    userName: str
    weekLabel: str
    contentDomain: ContentDomain
    visibilityScope: VisibilityScope
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
    suggestions: list[str]
    createdAt: str
    updatedAt: str


class ReportActionCardRecord(BaseModel):
    id: str
    actionType: Literal["task", "support_request", "resource_request", "meeting", "one_on_one"]
    title: str
    payload: dict[str, object]
    status: str
    createdAt: str
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class ReviewMetricCardRecord(BaseModel):
    key: Literal["timely_completion", "department_alignment", "strategy_alignment", "reflection_capture"]
    label: str
    valueText: str
    numerator: int
    denominator: int
    rate: float
    description: str
    tone: Literal["positive", "neutral", "warning", "risk"]


class HierarchyReportRecord(BaseModel):
    id: str
    scopeType: ReviewScopeType
    scopeRefId: str
    weekLabel: str
    logicMode: str
    headline: str
    summary: str
    summaryMetrics: list[ReviewMetricCardRecord] = Field(default_factory=list)
    focusAreas: list[str]
    supportSignals: list[str]
    suggestedActions: list[str]
    anonymousInsights: list[str]
    sourcePolicy: dict[str, object]
    actions: list[ReportActionCardRecord]
    createdAt: str
    updatedAt: str


class ReviewDashboardResponse(BaseModel):
    weekLabel: str = ""
    resolvedWeekLabel: str | None = None
    currentReview: WeeklyReviewEntryRecord | None = None
    workItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    personalItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    workSignalCard: ManagementSignalCardRecord | None = None
    personalGrowthCard: PersonalGrowthCardRecord | None = None
    teamReport: HierarchyReportRecord | None = None
    orgReport: HierarchyReportRecord | None = None
    plans: list[PlanNodeRecord]


class EventLineNarrativeNodeRecord(BaseModel):
    id: str
    time: str = ""
    title: str = ""
    narrative: str = ""
    confidence: str = "medium"
    linkedTaskIds: list[str] = Field(default_factory=list)
    linkedActivityIds: list[str] = Field(default_factory=list)
    linkedAttachmentIds: list[str] = Field(default_factory=list)


class EventLineTimelineNarrativeRecord(BaseModel):
    eventLineId: str
    rev: int = 0
    headline: str = ""
    opening: str = ""
    closing: str = ""
    nodes: list[EventLineNarrativeNodeRecord] = Field(default_factory=list)
    overallConfidence: float = 0.0
    generator: str = ""
    modelName: str = ""
    updatedAt: str = ""
    triggeredByDisplayName: str = ""


class EventLineTimelineNarrativeRegeneratePayload(BaseModel):
    trigger: str = "manual"


class ClientStrategicProfileRecord(BaseModel):
    """「项目本质」维度的结构化骨架。"""

    clientId: str
    projectType: str = ""
    projectGoal: str = ""
    successMetric: str = ""
    currentPhase: str = ""
    cooperationStartDate: str | None = None
    cooperationEndDate: str | None = None
    notes: str = ""
    updatedByDisplayName: str = ""
    updatedAt: str = ""


class ClientStrategicProfileUpdatePayload(BaseModel):
    projectType: str = ""
    projectGoal: str = ""
    successMetric: str = ""
    currentPhase: str = ""
    cooperationStartDate: str | None = None
    cooperationEndDate: str | None = None
    notes: str = ""


class ExternalPersonRecord(BaseModel):
    """「关键人物」维度的花名册条目。"""

    id: str
    clientId: str
    name: str
    roleTitle: str = ""
    affiliation: str = ""
    relationshipType: str = ""
    oneLiner: str = ""
    notes: str = ""
    sortOrder: int = 0
    createdAt: str = ""
    updatedAt: str = ""


class ExternalPersonUpsertPayload(BaseModel):
    name: str
    roleTitle: str = ""
    affiliation: str = ""
    relationshipType: str = ""
    oneLiner: str = ""
    notes: str = ""
    sortOrder: int = 0


class ExternalPersonsListResponse(BaseModel):
    clientId: str
    persons: list[ExternalPersonRecord] = Field(default_factory=list)


class DepartmentSignalActionAlert(BaseModel):
    id: str
    kind: str
    severity: str
    title: str
    advice: str
    involvedDepartmentId: str | None = None
    involvedDepartmentName: str | None = None
    involvedUserIds: list[str] = Field(default_factory=list)
    involvedUserNames: list[str] = Field(default_factory=list)
    metricLabel: str | None = None
    metricValueText: str | None = None
    daysLeft: int | None = None
    sourceQuote: str | None = None


class DepartmentSignalOneOnOneSuggestion(BaseModel):
    userId: str
    userName: str
    departmentId: str | None = None
    departmentName: str | None = None
    reason: str
    questionPrompts: list[str] = Field(default_factory=list)
    weekCreatedCount: int = 0
    weekCompletedCount: int = 0
    trendCompletedByWeek: list[int] = Field(default_factory=list)
    trendCreatedByWeek: list[int] = Field(default_factory=list)


class DepartmentSnapshot(BaseModel):
    departmentId: str
    departmentName: str
    leaderUserId: str | None = None
    leaderName: str | None = None
    status: str = "stable"
    completionRate: float = 0.0
    planTotalCount: int = 0
    planDoneCount: int = 0
    planAssignedCount: int = 0
    planLinkedCount: int = 0
    headlines: list[str] = Field(default_factory=list)
    temperatureLevel: int = 0
    burndownIdeal: list[float] = Field(default_factory=list)
    burndownActual: list[float] = Field(default_factory=list)


class ExecutiveHealthIndicator(BaseModel):
    """One headline number for the org's weekly health bar."""

    key: str
    label: str
    valueText: str
    unitText: str | None = None
    deltaText: str | None = None
    trendDirection: str = "flat"
    accent: str = "neutral"
    helperText: str | None = None


class ExecutiveDecision(BaseModel):
    """A management-level decision recommendation in three parts:
    现状 / 决策 / 代价 (situation / decision / cost-of-inaction).
    """

    id: str
    rank: int
    severity: str
    title: str
    situation: str
    decision: str
    cost: str
    actionLabel: str | None = None
    actionTarget: dict[str, object] | None = None
    sourceRefs: list[dict[str, object]] = Field(default_factory=list)


class DepartmentScoreRow(BaseModel):
    """Horizontal comparison row — one department per cell."""

    departmentId: str
    departmentName: str
    leaderName: str | None = None
    valueProductionScore: int = 0
    fulfillmentRatePct: int = 0
    monthlyProgressPct: int = 0
    humanEfficiencyScore: int = 0
    headlineInsight: str | None = None
    status: str = "stable"


class DepartmentSignalsResponse(BaseModel):
    weekLabel: str
    viewerRole: str = "employee"
    healthIndicators: list[ExecutiveHealthIndicator] = Field(default_factory=list)
    executiveDecisions: list[ExecutiveDecision] = Field(default_factory=list)
    departmentScoreboard: list[DepartmentScoreRow] = Field(default_factory=list)
    # legacy fields kept for transition (frontend stops reading them after P1)
    actionAlerts: list[DepartmentSignalActionAlert] = Field(default_factory=list)
    oneOnOneSuggestions: list[DepartmentSignalOneOnOneSuggestion] = Field(default_factory=list)
    departmentSnapshots: list[DepartmentSnapshot] = Field(default_factory=list)


class ReviewDashboardDrillTargetResponse(BaseModel):
    target: ReviewDashboardCardTargetRecord
    eventLineDetail: EventLineDetailRecord | None = None
    tasks: list[TaskRecord] = Field(default_factory=list)
    meetings: list[dict[str, object]] = Field(default_factory=list)
    supportRequests: list["SupportRequestRecord"] = Field(default_factory=list)
    attachments: list[dict[str, object]] = Field(default_factory=list)


class ReviewHistoryEntryRecord(BaseModel):
    weekLabel: str
    submittedAt: str
    workItemCount: int = 0
    personalItemCount: int = 0


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryEntryRecord] = Field(default_factory=list)


class WeeklyReviewCreatePayload(BaseModel):
    id: str | None = None
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


# ============================================================
# Phase 1.5c · 战略陪伴叙事面板 (云端共享, 组织内 A/B 账号同源)
# 6 维度故事网 + 共同编织澄清 + 历史可溯
# ============================================================

NarrativeDimension = Literal[
    "essence",         # Layer 1 · 项目本质 (机构是谁/赛道/定位)
    "cooperation",     # Layer 2 · 合作关系 (益语跟客户的服务周期+内容)
    "business_intro",  # Layer 3 · 业务介绍 (机构内每个项目详细介绍)
    "people",          # Layer 4 · 关键人物 (益语方+客户方+各项目对应)
    "timeline",        # Layer 5 · 时间线 (合作里程碑)
    "next_steps",      # Layer 6 · 承诺与下一步
    # 已废弃 (兼容旧 rev): "history" / "commitments" / "risks" / "next"
    "history", "commitments", "risks", "next",
]

NarrativeConfidence = Literal["high", "medium", "low"]

NarrativeClarificationStatus = Literal["pending", "applied", "discarded"]


class NarrativeReference(BaseModel):
    """AI 叙事段落引用的原始 db row 钻取链路."""
    sourceType: str          # 'document' / 'event_line' / 'event_line_activity' / 'action_item' / 'memory_fact' / 'chat_message'
    sourceId: str
    label: str = ""           # 显示给用户看的引用标签
    confidence: NarrativeConfidence = "medium"


class NarrativeDimensionRecord(BaseModel):
    """6 个维度中的一个: AI 叙事 + 引用源 + 把握度 + 澄清入口."""
    dimension: NarrativeDimension
    narrative: str = ""                  # AI 写的自然语言叙事
    confidence: NarrativeConfidence = "low"
    confidenceReason: str = ""           # 为什么是这个把握度 (尤其低的)
    references: list[NarrativeReference] = Field(default_factory=list)
    dataLayerGap: str = ""               # 这一维度因为数据中心缺什么导致讲不好
    openClarifications: list[str] = Field(default_factory=list)   # AI 想跟用户澄清的问题
    # S1 取材标签透传(5/29): 本地 narrative_generator 已 emit、前端徽章已写,
    # 此前云端 schema 不接这 3 个字段 → GET 回来恒 undefined → 徽章永不渲染(叙事黑箱)。
    retrievalMode: str | None = None     # semantic / semantic+fallback / fallback_only / legacy_like_only
    fallbackUsed: bool = False           # 本段是否用了关键词兜底
    reindexRequired: bool = False        # 是否建议为该客户补跑语义索引


class NarrativeContributor(BaseModel):
    """谁澄清过这一段 (共同编织追溯)."""
    userId: str | None = None
    displayName: str
    dimension: NarrativeDimension
    answeredAt: str


class ClientNarrativeRecord(BaseModel):
    """战略陪伴 / 事实澄清面板的整页数据."""
    id: str
    clientId: str
    clientName: str = ""
    rev: int
    generator: str = "ai"
    generatedAt: str
    modelName: str = ""
    dimensions: list[NarrativeDimensionRecord]
    overallConfidence: float = 0.0
    openClarificationsCount: int = 0
    dataLayerGaps: list[str] = Field(default_factory=list)
    contributors: list[NarrativeContributor] = Field(default_factory=list)
    updatedAt: str


class NarrativeClarificationRecord(BaseModel):
    id: str
    clientId: str
    basedOnRev: int
    dimension: NarrativeDimension
    question: str = ""
    askedBy: str = "ai"
    answer: str
    answeredByUserId: str | None = None
    answeredByDisplayName: str = ""
    answeredAt: str
    resultedInRev: int | None = None
    status: NarrativeClarificationStatus = "pending"


class NarrativeClarificationCreatePayload(BaseModel):
    dimension: NarrativeDimension
    question: str = ""
    answer: str
    basedOnRev: int | None = None             # 默认基于最新


class NarrativeClarificationsResponse(BaseModel):
    clarifications: list[NarrativeClarificationRecord] = Field(default_factory=list)


class NarrativeRegeneratePayload(BaseModel):
    """触发 LLM 重新生成 6 段叙事 (吸纳新的澄清)."""
    trigger: str = "manual"                   # 'manual' / 'clarification' / 'scheduled'
    force: bool = False                       # true=即使没新澄清也重生


class NarrativeIngestPayload(BaseModel):
    """本地 backend 生成完叙事后, POST 给云端落库 (Plan A 链路核心).

    本地直查 atomic_facts/entities/... 调本地 LLM, 完成生成后把整页 6 维度
    + 元数据塞给云端, 云端只做"持久化 + 多端共享". 不在云端重新调 LLM.
    """
    dimensions: dict[str, dict[str, object]]    # essence/people/.../next → 各 dim 的 payload
    overallConfidence: float = 0.0
    generator: str = "backend_local_ai"
    modelName: str = ""
    dataLayerGaps: list[str] = Field(default_factory=list)
    trigger: str = "manual"
    factBundleSummary: dict[str, object] = Field(default_factory=dict)  # collector 拿了什么的诊断信息
    # v1.0 新增: 客户基本信息, 让 cloud /ingest 在 client_id 不存在时自动创建
    clientName: str = ""
    clientAlias: str = ""


# ──────────────────────────────────────────────────────────────────
# 组织经验墙 (顾源源 5/27 方案 A · 云端同步)
# ──────────────────────────────────────────────────────────────────


class ExpWallQuoteUpsertPayload(BaseModel):
    """本地 push 一条金句 (含 reactions count) 到云端."""
    id: str
    authorUserId: str
    quoteText: str
    sourceExcerpt: str = ""
    sourceType: str
    sourceObjectId: str = ""
    category: str = "方法论"
    status: str = "active"
    deletedByUserId: str | None = None
    deletedAt: str | None = None
    likeCount: int = 0
    saveCount: int = 0
    contributionScore: float = 0.0
    hotScore: float = 0.0
    extractedAt: str
    createdAt: str
    updatedAt: str


class ExpWallQuoteRecord(BaseModel):
    """云端返回的金句记录 (含作者头像/名字, 给前端 GrowthCenterView 直接渲染)."""
    id: str
    organizationId: str
    authorUserId: str
    authorDisplayName: str = ""
    authorAvatarUrl: str = ""
    quoteText: str
    sourceExcerpt: str = ""
    sourceType: str
    sourceObjectId: str = ""
    category: str = "方法论"
    status: str = "active"
    deletedByUserId: str | None = None
    deletedAt: str | None = None
    likeCount: int = 0
    saveCount: int = 0
    contributionScore: float = 0.0
    hotScore: float = 0.0
    extractedAt: str
    createdAt: str
    updatedAt: str


class ExpWallReactionPayload(BaseModel):
    """本地 push 一条 reaction 到云端 (idempotent · UNIQUE(quote_id,user_id,type))."""
    id: str
    quoteId: str
    userId: str
    reactionType: Literal["like", "save"]
    createdAt: str


class ExpWallSyncResponse(BaseModel):
    """云端拉取响应: 增量金句 (合并 reactions 已聚合到 like_count/save_count)."""
    quotes: list[ExpWallQuoteRecord] = Field(default_factory=list)
    serverTimestamp: str


# ──────────────────────────────────────────────────────────────────
# 经验手册条目 (handbook_entries 真前端真当前真用真**经验墙真数据源**)
# ──────────────────────────────────────────────────────────────────


class HandbookEntryUpsertPayload(BaseModel):
    """本地 push 一条 handbook entry 到云端 (含软删除)."""
    id: str
    title: str
    summary: str
    tagsJson: str = "[]"
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
    abilityKeysJson: str = "[]"
    evidenceRefsJson: str = "[]"
    contextSummary: str = ""
    reuseCount: int = 0
    lastReusedAt: str | None = None
    authorUserId: str
    authorUserName: str = ""
    status: str = "active"
    deletedByUserId: str | None = None
    deletedAt: str | None = None
    createdAt: str
    updatedAt: str = ""


class HandbookEntryRecord(BaseModel):
    """云端返回的 handbook entry (跟本地真前端 type 真完全对齐)."""
    id: str
    organizationId: str
    title: str
    summary: str
    tagsJson: str = "[]"
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
    abilityKeysJson: str = "[]"
    evidenceRefsJson: str = "[]"
    contextSummary: str = ""
    reuseCount: int = 0
    lastReusedAt: str | None = None
    authorUserId: str
    authorUserName: str = ""
    status: str = "active"
    deletedByUserId: str | None = None
    deletedAt: str | None = None
    createdAt: str
    updatedAt: str


class HandbookSyncResponse(BaseModel):
    """云端拉取响应 (增量 entries + 服务端时间戳)."""
    entries: list[HandbookEntryRecord] = Field(default_factory=list)
    serverTimestamp: str


# ──────────────────────────────────────────────────────────────────
# 成长积分云端同步 (顾源源 5/27 阶段 1 · "卷"机制核心)
# ──────────────────────────────────────────────────────────────────


class GrowthSignalUpsertPayload(BaseModel):
    """本地 push 一条 signal 事件."""
    id: str
    userId: str
    userName: str = ""
    sourceType: str
    sourceId: str
    reviewId: str | None = None
    taskId: str | None = None
    weekLabel: str = ""
    rawText: str = ""
    contextJson: str = "{}"
    dedupeKey: str
    createdAt: str
    updatedAt: str = ""


class GrowthSignalRecord(BaseModel):
    id: str
    organizationId: str
    userId: str
    userName: str = ""
    sourceType: str
    sourceId: str
    reviewId: str | None = None
    taskId: str | None = None
    weekLabel: str = ""
    rawText: str = ""
    contextJson: str = "{}"
    dedupeKey: str
    createdAt: str
    updatedAt: str


class GrowthEvidenceUpsertPayload(BaseModel):
    id: str
    signalId: str
    userId: str
    userName: str = ""
    abilityKey: str
    evidenceType: str
    level: str
    confidence: str = "medium"
    reason: str = ""
    reviewId: str | None = None
    taskId: str | None = None
    handbookEntryId: str | None = None
    metadataJson: str = "{}"
    contributionTagsJson: str = "[]"
    orgContributionScore: int = 0
    suggestedPremiumRate: float = 0.0
    validationState: str = "candidate"
    aiReason: str = ""
    aiConfidence: float = 0.0
    createdAt: str
    updatedAt: str = ""


class GrowthEvidenceRecord(BaseModel):
    id: str
    organizationId: str
    signalId: str
    userId: str
    userName: str = ""
    abilityKey: str
    evidenceType: str
    level: str
    confidence: str = "medium"
    reason: str = ""
    reviewId: str | None = None
    taskId: str | None = None
    handbookEntryId: str | None = None
    metadataJson: str = "{}"
    contributionTagsJson: str = "[]"
    orgContributionScore: int = 0
    suggestedPremiumRate: float = 0.0
    validationState: str = "candidate"
    aiReason: str = ""
    aiConfidence: float = 0.0
    createdAt: str
    updatedAt: str


class GrowthValidationEventUpsertPayload(BaseModel):
    id: str
    userId: str
    evidenceId: str
    eventType: str
    actorId: str = ""
    actorName: str = ""
    sourceType: str = ""
    sourceId: str | None = None
    detailJson: str = "{}"
    createdAt: str
    updatedAt: str = ""


class GrowthValidationEventRecord(BaseModel):
    id: str
    organizationId: str
    userId: str
    evidenceId: str
    eventType: str
    actorId: str = ""
    actorName: str = ""
    sourceType: str = ""
    sourceId: str | None = None
    detailJson: str = "{}"
    createdAt: str
    updatedAt: str


class GrowthSignalSyncResponse(BaseModel):
    signals: list[GrowthSignalRecord] = Field(default_factory=list)
    serverTimestamp: str


class GrowthEvidenceSyncResponse(BaseModel):
    evidence: list[GrowthEvidenceRecord] = Field(default_factory=list)
    serverTimestamp: str


class GrowthValidationEventSyncResponse(BaseModel):
    events: list[GrowthValidationEventRecord] = Field(default_factory=list)
    serverTimestamp: str
