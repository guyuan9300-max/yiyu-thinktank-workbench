export interface SessionUser {
  id: string;
  fullName: string;
  email: string;
  title?: string | null;
  organizationId?: string | null;
  /** 登录后由云端自动下发的组织展示名。手机端不允许注册/改组织，仅展示。 */
  organizationName?: string | null;
  departmentId?: string | null;
  departmentName?: string | null;
  avatarUrl?: string | null;
}

export interface AuthTokenResponse {
  accessToken: string;
  refreshToken?: string | null;
  user: SessionUser;
}

export type TaskPriority = "low" | "normal" | "high" | string;
export type TaskProgressStatus = "inbox" | "todo" | "doing" | "done" | "rejected" | string;

export interface TaskAttachmentRecord {
  id: string;
  taskId?: string | null;
  clientId?: string | null;
  eventLineId?: string | null;
  title?: string | null;
  summary?: string | null;
  /** 服务端返回的远端路径（cloud_backend TaskAttachmentRecord.path） */
  path?: string | null;
  /** 兼容字段：本地或可下载的 URL；新逻辑请用 path */
  url?: string | null;
  localPath?: string | null;
  /** attachment 类型：document / audio / image / ... */
  kind?: string | null;
  /** 上传来源：manual / recording / extraction / ... */
  source?: string | null;
  mimeType?: string | null;
  sizeBytes?: number | null;
  durationSeconds?: number | null;
  createdAt?: string;
}

export type LocalMutationState = "local_committed" | "local_failed";
export type RemoteMutationState = "queued" | "syncing" | "processing" | "needs_attention" | "synced";
export type SyncReasonCode =
  | "network_unavailable"
  | "auth_expired"
  | "permission_denied"
  | "validation_failed"
  | "version_conflict"
  | "file_missing"
  | "quota_exceeded"
  | "server_rejected"
  | "thermal_blocked"
  | "model_unavailable";
export type PendingOpLane = "interactive" | "transfer" | "derived";
export type PendingOpOperation = "create" | "update" | "delete" | "complete_with_review";
export type PendingOpVisibilityScope = "private_draft" | "team_shared" | "official";

export interface TaskCollaboratorRecord {
  userId: string;
  fullName: string;
  email?: string | null;
  orderIndex?: number | null;
  isOwner: boolean;
  inboxStatus?: string | null;
  returnReason?: string | null;
  handledAt?: string | null;
}

export type TaskOrgControlLevel = "normal" | "managed" | "organization_control" | string;

export interface TaskOrgContextRecord {
  departmentId?: string | null;
  roleTemplateId?: string | null;
  controlRuleId?: string | null;
  controlLevel?: TaskOrgControlLevel | null;
  organizationFocusKey?: string | null;
  departmentFocusKey?: string | null;
  focusItemId?: string | null;
  departmentPlanItemId?: string | null;
  isCrossDepartment?: boolean;
  approvalState?: string | null;
  blockedAtStep?: string | null;
  needsReview?: boolean;
}

export type TaskScopeMode = "COLLAB_SHARED" | "PERSONAL_ONLY";

/** 任务标签：云端真相是 TaskTagRecord，旧版本可能是 string；兼容两种形态 */
export type TaskTagLike = string | TaskTagRecord;

export interface TaskRecord {
  id: string;
  remoteId?: string | null;
  title: string;
  description?: string | null;
  /** 计划开始日期 */
  startDate?: string | null;
  dueDate?: string | null;
  deadlineAt?: string | null;
  scheduledStartAt?: string | null;
  scheduledEndAt?: string | null;
  completedAt?: string | null;
  durationMinutes?: number | null;
  /** 提醒提前量（分钟）：0=准时, 5=提前5分, null=不提醒。相对 scheduledStartAt(无则 deadlineAt)。跨端共享同一字段。 */
  reminderMinutesBefore?: number | null;
  priority: TaskPriority;
  progressStatus: TaskProgressStatus;
  /** 兼容旧版本 string[]，新版云端返回 TaskTagRecord[] */
  tags?: TaskTagLike[] | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  listId?: string | null;
  listName?: string | null;
  listColor?: string | null;
  creatorId?: string | null;
  creatorName?: string | null;
  ownerId?: string | null;
  ownerName?: string | null;
  /** 协作可见 / 仅个人 */
  scopeMode?: TaskScopeMode | null;
  /** 任务来源（如 manual / smart_input / recording / consultation 等） */
  sourceType?: string | null;
  sourceId?: string | null;
  /** 项目模板模块/流程 */
  projectModuleId?: string | null;
  projectFlowId?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  completionNote?: string | null;
  /** 任务备忘录（独立于 description） */
  note?: string | null;
  /** 证据/复盘材料数量（用于"需复盘"判断） */
  evidenceCount?: number | null;
  attachments?: TaskAttachmentRecord[];
  collaborators?: TaskCollaboratorRecord[];
  /** 协作状态汇总（pending/accepted/returned 计数） */
  collaborationSummary?: Record<string, number> | null;
  viewerInboxStatus?: "pending" | "accepted" | "returned" | null;
  /** 组织上下文（部门、审批、focus item、跨部门、需复盘 等） */
  orgContext?: TaskOrgContextRecord | null;
  localVersion?: number;
  baseRemoteVersion?: number | null;
  serverVersion?: number | null;
  localState?: LocalMutationState;
  remoteState?: RemoteMutationState;
  syncReasonCode?: SyncReasonCode | null;
  deletedAt?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface TaskBoardResponse {
  tasks: TaskRecord[];
  inboxCount?: number;
  tasksTodayCount?: number;
}

export interface TaskListRecord {
  id: string;
  name: string;
  color?: string | null;
  isDefault?: boolean;
}

export interface TaskTagRecord {
  id: string;
  name: string;
  color?: string | null;
}

export interface ClientSummaryRecord {
  id: string;
  name: string;
  alias?: string | null;
}

export interface EventLineRecord {
  id: string;
  name: string;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
  summary?: string | null;
  currentBlocker?: string | null;
  nextStep?: string | null;
  recentDecision?: string | null;
  stage?: string | null;
  status?: string;
}

export type SmartInputIntent = "task_schedule" | "record_note" | "unknown";

export interface SmartTaskDraft {
  title?: string | null;
  dueDate?: string | null;
  endDate?: string | null;
  dueTime?: string | null;
  durationMinutes?: number | null;
  location?: string | null;
  description?: string | null;
  tags?: string[];
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectQuery?: string | null;
  eventLineQuery?: string | null;
}

export interface SmartTaskDraftResponse {
  transcript: string;
  intent: SmartInputIntent;
  draft: SmartTaskDraft;
  warnings: string[];
  confidence?: number | null;
}

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId?: string | null;
  target?: "vector_memory" | "document_archive" | string;
  status?: "pending" | "processing" | "completed" | "failed" | string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
  question?: string | null;
  answer?: string | null;
  errorMessage?: string | null;
  localDocumentId?: string | null;
  localDocumentPath?: string | null;
  completedAt?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface ConsultationChatResponse {
  reply: string;
  model?: string | null;
  answerMode?: "grounded" | "limited_context" | "missing_context" | "error" | null;
  contextQuality?: {
    level?: "none" | "thin" | "partial" | "rich" | string;
    availableSources?: string[];
    missingSources?: string[];
    staleSources?: string[];
    contextBundleHash?: string | null;
  } | null;
  evidence?: Array<{
    id: string;
    type:
      | "workspace"
      | "client_dna"
      | "event_line"
      | "meeting"
      | "task"
      | "knowledge_surrogate"
      | "cockpit"
      | "thread_snapshot"
      | "task_board"
      | "client_name"
      | "understanding"
      | "entity"
      | "relation"
      | "atomic_fact"
      | "contradiction"
      | "glossary_term"
      | string;
    title: string;
    updatedAt?: string | null;
    snippet?: string | null;
  }>;
  missingContext?: Array<{
    type:
      | "client_dna"
      | "workspace"
      | "event_line"
      | "meeting"
      | "person_profile"
      | "project_background"
      | "strategic_cockpit"
      | "knowledge_surrogate"
      | "task_board"
      | "understanding"
      | string;
    message: string;
  }>;
}

export interface MobileCapabilityRecord {
  consultationChat: boolean;
  clientWorkspace: boolean;
  strategicCockpit: boolean;
  knowledgeMirror: boolean;
  contextBundle: boolean;
  understandingMirror?: boolean;
  consultationPayloadVersion: string;
  updatedAt: string;
}

export interface ClientUnderstandingEntity {
  id: string;
  name: string;
  type?: string;
  aliases?: string[];
  mentions?: number;
  confidence?: number | null;
  updatedAt?: string | null;
}

export interface ClientUnderstandingRelation {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  confidence?: number | null;
  evidenceCount?: number;
  updatedAt?: string | null;
}

export interface ClientUnderstandingFact {
  id: string;
  statement: string;
  semanticType?: string;
  confidence?: number | null;
  freshness?: number | null;
  sourceCount?: number;
  updatedAt?: string | null;
}

export interface ClientUnderstandingContradiction {
  id: string;
  topic: string;
  conflictingStatements: string[];
  severity?: "low" | "medium" | "high" | null;
  updatedAt?: string | null;
}

export interface ClientUnderstandingGlossaryTerm {
  id: string;
  term: string;
  definition?: string;
  aliases?: string[];
  updatedAt?: string | null;
}

export interface ClientUnderstandingFreshness {
  halfLifeDays?: number | null;
  score?: number | null;
}

export interface ClientUnderstandingSnapshot {
  clientId: string;
  status: "ready" | "partial" | "missing";
  updatedAt?: string | null;
  snapshotHash?: string | null;
  entities: ClientUnderstandingEntity[];
  relations: ClientUnderstandingRelation[];
  atomicFacts: ClientUnderstandingFact[];
  contradictions: ClientUnderstandingContradiction[];
  glossary: ClientUnderstandingGlossaryTerm[];
  freshness?: ClientUnderstandingFreshness | null;
}

// ─── 客户叙事（cloud_backend ClientNarrativeRecord 镜像）───
export type NarrativeConfidence = "high" | "medium" | "low";

export interface NarrativeReferenceRecord {
  kind: string;
  id?: string;
  label?: string;
  confidence?: NarrativeConfidence;
}

export interface NarrativeDimensionRecord {
  dimension: string;
  narrative: string;
  confidence: NarrativeConfidence;
  confidenceReason?: string;
  references?: NarrativeReferenceRecord[];
  dataLayerGap?: string;
  openClarifications?: string[];
}

export interface ClientNarrativeRecord {
  id: string;
  clientId: string;
  clientName?: string;
  rev: number;
  generator?: string;
  generatedAt: string;
  modelName?: string;
  dimensions: NarrativeDimensionRecord[];
  overallConfidence?: number;
  openClarificationsCount?: number;
  dataLayerGaps?: string[];
  updatedAt: string;
}

export interface MobileContextSourceStatusRecord {
  source: string;
  available: boolean;
  status: "ready" | "partial" | "missing" | "unavailable" | string;
  detail?: string | null;
  updatedAt?: string | null;
}

export type ClientWorkspaceLiteStatus = "rich" | "partial" | "missing";

export interface SupportRequestRecord {
  id: string;
  title: string;
  description?: string | null;
  status?: string;
  requesterName?: string | null;
  createdAt?: string;
}

export interface EmployeeRecord {
  id: string;
  fullName: string;
  email?: string | null;
  title?: string | null;
}

export interface TaskActivityRecord {
  id: string;
  eventType: string;
  actorId?: string | null;
  actorName?: string | null;
  payload?: Record<string, unknown> | null;
  createdAt?: string;
}

export interface TaskSettingsRecord {
  defaultListId?: string | null;
  defaultPriority?: "low" | "normal" | "high";
  defaultDueDatePreset?: "today" | "none";
  defaultViewMode?: "inbox" | "list" | "calendar" | "review";
  listSortMode?: "manual" | "priority" | "dueDate";
  showCompletedTasks?: boolean;
  defaultReviewScope?: "work" | "personal";
  autoAssignSelf?: boolean;
}

export interface MutationReceipt {
  entityType: "task" | "calendar_block" | "attachment" | "voice_draft" | "consult_draft";
  localId: string;
  remoteId: string | null;
  localState: LocalMutationState;
  remoteState: RemoteMutationState;
  reasonCode?: SyncReasonCode | null;
  updatedAt: string;
  message: string;
}

export interface PendingOpRecord {
  id: number;
  clientOpId: string;
  entityType: string;
  entityId: string;
  entityRemoteId?: string | null;
  operation: PendingOpOperation;
  payload: string | null;
  lane: PendingOpLane;
  status: RemoteMutationState;
  visibilityScope: PendingOpVisibilityScope;
  localVersion: number;
  baseRemoteVersion?: number | null;
  createdAt: string;
  updatedAt?: string;
  retryCount: number;
  lastError: string | null;
  reasonCode?: SyncReasonCode | null;
}

export interface TaskServerShadowRecord {
  taskId: string;
  remoteId?: string | null;
  serverVersion?: number | null;
  payload: TaskRecord;
  updatedAt: string;
}

export interface TaskConflictDiagnostic {
  taskId: string;
  title: string;
  remoteState: RemoteMutationState;
  syncReasonCode: SyncReasonCode | null;
  pendingOperation: PendingOpOperation | null;
  pendingUpdatedAt: string | null;
  pendingOpCount: number;
  lastError: string | null;
  hasServerShadow: boolean;
  serverShadowUpdatedAt: string | null;
  serverVersion: number | null;
}

export interface PendingOpSummary {
  total: number;
  queued: number;
  syncing: number;
  processing: number;
  needsAttention: number;
  byLane: Record<PendingOpLane, number>;
  byReasonCode: Partial<Record<SyncReasonCode, number>>;
}

export type LegacyUploadReasonCode =
  | "network_unavailable"
  | "auth_required"
  | "scope_mismatch"
  | "file_missing"
  | "file_corrupted"
  | "upload_failed"
  | "bind_pending_remote_id"
  | "integrity_blocked"
  | "manual_pause"
  | "unknown_error";

export type LegacyUploadPseudoOpStatus = "queued" | "processing" | "needs_attention";

export interface HealthLaneDiagnostic {
  lane: PendingOpLane;
  total: number;
  oldestAgeMs: number | null;
  active: boolean;
  topReasonCode: string | null;
}

export interface LegacyUploadPseudoOp {
  opId: string;
  objectType: string;
  objectLocalId: string;
  objectRemoteId?: string | null;
  lane: "transfer";
  status: LegacyUploadPseudoOpStatus;
  retryCount: number;
  reasonCode: LegacyUploadReasonCode;
  createdAt: string;
  lastAttemptAt: string | null;
  ageMs: number;
  displayTitle?: string | null;
  taskLocalId: string;
  filePath: string;
  size: number | null;
  mtime: number | null;
  hash: string | null;
  entityRefLocalId: string;
  mimeType?: string | null;
  durationSeconds?: number | null;
}

export type SyncFreezeState =
  | "ready"
  | "paused_by_user"
  | "blocked_by_integrity"
  | "blocked_by_scope_mismatch"
  | "blocked_by_migration_failure"
  | "blocked_by_auth";

export type CurrentFocusSource = "manual" | "from_task" | "from_calendar" | "from_meeting" | "auto";
export type CurrentFocusLockMode = "browse" | "client" | "client_event_line";
export type CurrentFocusBoundaryState =
  | "none"
  | "official"
  | "pending"
  | "risk"
  | "reminder"
  | "mixed";

export interface CurrentFocus {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  weekAnchorDate: string;
  weekLabel: string;
  source: CurrentFocusSource;
  lockMode: CurrentFocusLockMode;
  boundaryState: CurrentFocusBoundaryState;
  updatedAt: string;
}

export interface ConsultThreadContextSnapshot {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  understandingContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
  frozenAt: string;
  snapshotHash: string;
  snapshotVersion: number;
}

export interface TaskContextPreviewRecord {
  taskId: string;
  clientId?: string | null;
  clientName?: string | null;
  summaryChips: string[];
  readiness?: "low" | "medium" | "high" | string;
  safeOutputMode?: "needs_input" | "summary_only" | "full_judgment" | string;
  judgment?: {
    summary?: string | null;
    progressNow?: string | null;
    unknowns?: string | null;
  } | null;
}

export interface TaskUnderstandingRecord {
  mode?: "basic" | "enhanced";
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  confidence: number;
  coverage: number;
  _pending?: boolean;
  optionalAdvice?: {
    realBlocker?: string | null;
    timeGate?: string | null;
    minimumAction?: string | null;
    supportAsk?: string | null;
  } | null;
  sourceBreakdown?: Array<{
    sourceType?: string;
    sourceName?: string;
    label?: string;
    available: boolean;
    snippet?: string | null;
  }>;
}

export type BoundaryCardKind = "official" | "pending" | "risk" | "reminder";

export interface BoundaryCard {
  kind: BoundaryCardKind;
  title: string;
  summary: string;
  sourceType: "meeting" | "document" | "ai" | "manual" | "mixed";
  updatedAt?: string | null;
  evidenceCount: number | null;
  isEmpty: boolean;
}

export interface WorkspaceLiteItem {
  id: string;
  title: string;
  summary?: string | null;
  subtitle?: string | null;
  updatedAt?: string | null;
}

export interface WorkspaceLiteTaskItem {
  id: string;
  title: string;
  status?: string | null;
  clientName?: string | null;
  eventLineName?: string | null;
}

export interface ClientWorkspaceLiteSnapshot {
  clientId: string;
  clientName: string;
  status: ClientWorkspaceLiteStatus;
  availableSources: string[];
  missingSources: string[];
  staleSources: string[];
  sourceUpdatedAt: Record<string, string | null>;
  boundaryCards: BoundaryCard[];
  boundaryState: CurrentFocusBoundaryState;
  goals: WorkspaceLiteItem[];
  latestMeetings: WorkspaceLiteItem[];
  knowledgeStatus?: string | null;
  recentDocuments: WorkspaceLiteItem[];
  openQuestions: WorkspaceLiteItem[];
  conflicts: WorkspaceLiteItem[];
  relatedTasks: WorkspaceLiteTaskItem[];
  nextActions: string[];
  headline?: string | null;
  health: string[];
  twoWeekChanges: string[];
  pendingDecisions: string[];
  pendingMaterials: string[];
  updatedAt: string;
  understanding?: ClientUnderstandingSnapshot | null;
}

export interface WeekSignalFactSummary {
  totalCount: number;
  completedCount: number;
  rescheduledCount: number;
  unscheduledCount: number;
  overdueCount: number;
  awaitingReviewCount: number;
}

export interface WeekSignalSnapshot {
  facts: WeekSignalFactSummary;
  pendingJudgments: string[];
  riskSignals: string[];
  suggestedActions: string[];
}

// ─── Tag helpers ─────────────────────────────────
// cloud_backend 返回结构化 TaskTagRecord，但写入 API（CreateTaskPayload/UpdateTaskPayload）
// 仍接受 string[]；读 UI 时也常常只需要 name 文本。

export function tagLikeToName(tag: TaskTagLike | null | undefined): string | null {
  if (tag == null) return null;
  if (typeof tag === "string") return tag.trim() || null;
  const name = (tag.name ?? "").trim();
  return name.length > 0 ? name : null;
}

export function tagsToStringArray(tags: TaskTagLike[] | null | undefined): string[] | undefined {
  if (!tags || tags.length === 0) return undefined;
  const out: string[] = [];
  for (const t of tags) {
    const name = tagLikeToName(t);
    if (name) out.push(name);
  }
  return out.length > 0 ? out : undefined;
}
