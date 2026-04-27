# src/shared/types.ts

```ts
export type Priority = 'low' | 'normal' | 'high';
export type TaskStatus = 'inbox' | 'todo' | 'doing' | 'done' | 'rejected';
export type TaskDueDatePreset = 'today' | 'none';
export type TaskListSortMode = 'dueDate' | 'priority' | 'manual';
export type TaskViewPreference = 'inbox' | 'list' | 'calendar' | 'review';
export type TaskReviewScope = 'work' | 'personal';
export type TaskScopeMode = 'COLLAB_SHARED' | 'PERSONAL_ONLY';
export type ReviewCompletionStatus = 'done_on_time' | 'done_late' | 'in_progress' | 'not_done';
export type ReviewAlignmentStatus = 'aligned' | 'partial' | 'misaligned' | 'unknown';
export type ReviewLightweightTag = '' | '资料不足' | '等待他人' | '方向不清' | '资源不够' | '工作过度饱和';
export type AgentDepartmentKey = 'strategy_design' | 'tech_development' | 'info_data';
export type AgentPlanStatus = 'planned' | 'doing' | 'done' | 'blocked';
export type TopicTaskOwnerMode = 'self' | 'empty';
export type TopicCandidateStatus = 'candidate' | 'tracking' | 'promoted' | 'archived';
export type TopicCandidateInsightStatus = 'pending' | 'ready' | 'failed';
export type MeetingStage = 'prepared' | 'ingested' | 'extracted' | 'resolved' | 'published';
export type AiProvider = 'mock' | 'qwen' | 'doubao';
export type AccountStatus = 'pending' | 'approved' | 'rejected' | 'disabled';
export type EmployeeRole = 'admin' | 'employee';
export type CollaboratorInboxStatus = 'pending' | 'accepted' | 'returned';
export type OrgRoleLevel = 'employee' | 'supervisor' | 'department_lead' | 'organization_lead';
export type OrgReportingLineType = 'business' | 'administrative';
export type OrgTaskEditScope = 'self' | 'manager' | 'department' | 'organization';
export type OrgTaskControlLevel = 'normal' | 'leader_control' | 'department_control' | 'organization_control';
export type OrgRuleActorScope = 'assignee' | 'manager' | 'department_lead' | 'organization_lead' | 'creator';
export type OrgWorkflowTriggerType = 'weekly_followup' | 'task_created' | 'meeting_closed' | 'client_update' | 'manual';
export type OrgFocusPriority = 'high' | 'medium' | 'low';
export type OrgFocusStatus = 'draft' | 'active' | 'paused' | 'done';
export type OrgDepartmentPlanStatus = 'draft' | 'active' | 'closed';
export type OrgDepartmentPlanItemStatus = 'active' | 'paused' | 'done' | 'dropped';
export type TaskPlanLinkSource = 'ai' | 'manager' | 'rule';
export type SupportRequestTargetScope = 'manager' | 'department' | 'organization' | 'cross_department';
export type SupportRequestType = 'resource' | 'decision' | 'collaboration' | 'workload' | 'clarification';
export type SupportRequestStatus = 'open' | 'accepted' | 'resolved' | 'dismissed';
export type DnaSourceLevel = 'organization' | 'client';
export type OrganizationDnaModuleKey = 'organization_intro' | 'business_intro' | 'team_intro' | 'market_intro';
export type FeishuReceiveIdType = 'open_id' | 'user_id' | 'email' | 'chat_id';
export type GrowthAbilityKey = 'exec' | 'collab' | 'analyze' | 'insight' | 'risk' | 'write';
export type GrowthEvidenceType = 'reflection' | 'codification' | 'reuse' | 'improvement';
export type GrowthConfidence = 'high' | 'medium' | 'low';
export type LearningContentType = 'method_card' | 'practice_card' | 'correction_card';
export type LearningRecommendationStatus = 'active' | 'accepted' | 'dismissed';
export type GrowthContributionTag = 'knowledge_asset' | 'critical_resolution' | 'collaboration_enablement' | 'risk_alignment' | 'mechanism_building';
export type GrowthValidationState = 'candidate' | 'observed' | 'validated' | 'institutionalized';
export type GrowthPendingCaptureState = 'open' | 'dismissed' | 'reviewed' | 'promoted';
export type BadgeState = 'locked' | 'progress' | 'ready' | 'lit' | 'mastered';
export type AnalysisScopeType = 'client' | 'event_line' | 'meeting' | 'task' | 'module' | 'flow';
export type AnalysisJobType = 'asset_ingest' | 'evidence_extract' | 'customer_compare' | 'meeting_enhance' | 'dna_refresh' | 'strategy_pack';
export type AnalysisJobStatus =
  | 'queued'
  | 'running'
  | 'preparing'
  | 'extracting'
  | 'clustering'
  | 'comparing'
  | 'drafting'
  | 'awaiting_review'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rolled_back';
export type AnalysisReviewState = 'draft' | 'awaiting_review' | 'awaiting_revision' | 'approved' | 'rejected' | 'superseded';
export type AnalysisStageStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';
export type AnalysisOriginType = 'projection' | 'analysis' | 'human_override';
export type AnalysisAuthorityLevel = 'fallback' | 'candidate' | 'approved';
export type AnalysisQualityTier = 'legacy' | 'normalized' | 'reviewed';
export type AnalysisIntentProfile = 'task_ai' | 'weekly_review' | 'meeting_enhance' | 'client_overview' | 'strategic_cockpit' | 'dna_summary';
export type AnalysisStaleReason =
  | 'superseded_by_newer_judgment'
  | 'source_snapshot_changed'
  | 'approval_revoked'
  | 'scope_no_longer_primary'
  | 'insufficient_evidence'
  | 'manual_invalidation';
export type AnalysisRejectedReason =
  | 'authority_too_low'
  | 'scope_less_relevant'
  | 'stale'
  | 'superseded'
  | 'insufficient_evidence'
  | 'not_approved_for_official_use';
export type ApprovalDecision = 'approved' | 'rejected' | 'returned_for_revision';
export type ApprovalTargetType = 'judgment_version' | 'dna_delta' | 'conflict_group' | 'proposal_record';
export type AnalysisLane = 'light_extractor' | 'local_deep' | 'cloud_final';

export interface Operator {
  id: string;
  name: string;
  role: string;
  team: string;
  color: string;
  isCurrent: boolean;
}

export interface AppSettings {
  currentOperatorId: string;
  aiProvider: AiProvider;
  aiModel: string;
  dataDir: string;
  backupDir: string;
  cloudApiUrl: string;
  lastBackupAt?: string | null;
  foldersRootLabel: string;
  aiConfigured: boolean;
  aiCredentialSource: string;
  aiFingerprint?: string | null;
  demoDataLoaded: boolean;
}

export interface SessionUser {
  id: string;
  organizationId: string;
  email: string;
  fullName: string;
  primaryRole: EmployeeRole;
  accountStatus: AccountStatus;
}

export interface AuthState {
  authenticated: boolean;
  user?: SessionUser | null;
  message?: string | null;
  sessionMode?: 'local' | 'cloud';
}

export type ConsultationKnowledgeTarget = 'vector_memory' | 'document_archive';
export type ConsultationKnowledgeRequestStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId: string;
  organizationId: string;
  target: ConsultationKnowledgeTarget;
  status: ConsultationKnowledgeRequestStatus;
  requestedByUserId: string;
  requestedByName: string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
  question: string;
  answer: string;
  errorMessage?: string | null;
  localDocumentId?: string | null;
  localDocumentPath?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConsultationKnowledgeProcessSummary {
  totalPending: number;
  processedCount: number;
  completedCount: number;
  failedCount: number;
  skippedCount: number;
  updatedAt: string;
  items: ConsultationKnowledgeRequestRecord[];
}

export interface EmployeeRecord {
  id: string;
  email: string;
  fullName: string;
  primaryRole: EmployeeRole;
  accountStatus: AccountStatus;
  departmentId?: string | null;
  departmentName?: string | null;
  jobTitle?: string | null;
  managerName?: string | null;
  currentFocus?: string | null;
  isDepartmentLead?: boolean;
  approvedAt?: string | null;
  rejectedReason?: string | null;
  disabledAt?: string | null;
  lastLoginAt?: string | null;
  createdAt: string;
}

export interface DepartmentOption {
  id: string;
  name: string;
  color: string;
}

export interface OrgProfileSettings {
  organizationId: string;
  name: string;
  annualGoal: string;
  annualStrategyYear: string;
  annualStrategy: string;
  quarterPlans: OrgQuarterPlanSettings[];
  quarterlyFocus: string[];
  leaderUserId?: string | null;
  managementUserIds: string[];
  updatedAt: string;
}

export type OrgQuarterKey = 'Q1' | 'Q2' | 'Q3' | 'Q4';

export interface OrgQuarterPlanSettings {
  id: string;
  year: string;
  quarter: OrgQuarterKey;
  theme: string;
  objective: string;
  keyResults: string[];
  keyActions: string[];
  majorRisks: string[];
  updatedAt: string;
}

export interface OrgDepartmentQuarterPlanSettings {
  year: string;
  quarter: OrgQuarterKey;
  objective: string;
  deliverables: string[];
  successMetrics: string[];
  majorRisks: string[];
  updatedAt: string;
}

export interface OrgDepartmentSettings {
  id: string;
  name: string;
  color: string;
  leaderUserId?: string | null;
  leaderName?: string;
  parentDepartmentId?: string | null;
  mission: string;
  businessContext: string;
  teamContext: string;
  quarterPlan: OrgDepartmentQuarterPlanSettings;
  quarterlyFocus: string[];
  collaborationDepartmentIds: string[];
  active: boolean;
  updatedAt: string;
}

export interface OrgRoleTemplateSettings {
  id: string;
  departmentId?: string | null;
  name: string;
  level: OrgRoleLevel;
  managerRoleId?: string | null;
  isManager: boolean;
  goal: string;
  responsibilities: string[];
  shouldAvoid: string[];
  collaborationRoleIds: string[];
  taskEditScope: OrgTaskEditScope;
  canApproveTasks: boolean;
  canReassignTasks: boolean;
  canChangeDeadline: boolean;
  sortOrder: number;
  active: boolean;
  updatedAt: string;
}

export interface OrgEmployeeBindingSettings {
  userId: string;
  departmentId?: string | null;
  primaryRoleId?: string | null;
  managerUserId?: string | null;
  isManager: boolean;
  projectRoleLabels: string[];
  currentFocus: string;
  taskEditScope: OrgTaskEditScope;
  canApproveTasks: boolean;
  canReassignTasks: boolean;
  canChangeDeadline: boolean;
  updatedAt: string;
}

export interface OrgReportingLineSettings {
  id: string;
  managerUserId: string;
  reportUserId: string;
  lineType: OrgReportingLineType;
  approvesTasks: boolean;
  canAdjustTasks: boolean;
  canChangeDeadline: boolean;
  canReassignTasks: boolean;
  isCrossDepartmentApprover: boolean;
  active: boolean;
  updatedAt: string;
}

export interface OrgTaskControlRuleSettings {
  id: string;
  name: string;
  controlLevel: OrgTaskControlLevel;
  departmentId?: string | null;
  roleTemplateId?: string | null;
  contentEditableBy: OrgRuleActorScope;
  deadlineEditableBy: OrgRuleActorScope;
  ownerEditableBy: OrgRuleActorScope;
  cancellableBy: OrgRuleActorScope;
  requireCollabConfirmation: boolean;
  defaultApproverUserId?: string | null;
  active: boolean;
  updatedAt: string;
}

export interface OrgRoleProcessTemplateSettings {
  id: string;
  roleTemplateId?: string | null;
  name: string;
  triggerType: OrgWorkflowTriggerType;
  triggerCondition: string;
  keySteps: string[];
  collaborationStep: string;
  approvalStep: string;
  outputArtifact: string;
  commonBlockers: string[];
  active: boolean;
  updatedAt: string;
}

export interface OrgFocusItemSettings {
  id: string;
  periodKey: string;
  title: string;
  statement: string;
  ownerUserId?: string | null;
  priority: OrgFocusPriority;
  status: OrgFocusStatus;
  evidenceKeywords: string[];
  updatedAt: string;
}

export interface OrgDepartmentPlanItemSettings {
  id: string;
  focusItemId?: string | null;
  title: string;
  statement: string;
  ownerUserId?: string | null;
  status: OrgDepartmentPlanItemStatus;
  expectedOutput: string;
  sortOrder: number;
  updatedAt: string;
}

export interface OrgDepartmentPlanSettings {
  id: string;
  departmentId?: string | null;
  weekLabel: string;
  ownerUserId?: string | null;
  summary: string;
  majorRisks: string[];
  dependencies: string[];
  status: OrgDepartmentPlanStatus;
  items: OrgDepartmentPlanItemSettings[];
  updatedAt: string;
}

export interface TaskPlanLinkRecord {
  taskId: string;
  departmentPlanItemId?: string | null;
  focusItemId?: string | null;
  linkedBy: TaskPlanLinkSource;
  confidence: number;
  updatedAt: string;
}

export interface SupportRequestRecord {
  id: string;
  taskId?: string | null;
  requesterUserId: string;
  targetScope: SupportRequestTargetScope;
  targetRefId?: string | null;
  requestType: SupportRequestType;
  urgency: OrgFocusPriority;
  summary: string;
  status: SupportRequestStatus;
  resolutionNote: string;
  createdAt: string;
  updatedAt: string;
}

export interface SupportRequestCreatePayload {
  taskId?: string | null;
  eventLineId?: string | null;
  targetScope: SupportRequestTargetScope;
  targetRefId?: string | null;
  requestType: SupportRequestType;
  urgency: OrgFocusPriority;
  summary: string;
}

export interface SupportRequestResolvePayload {
  resolutionNote?: string;
  status?: 'accepted' | 'resolved' | 'dismissed';
}

export interface TaskOrgBackfillResult {
  organizationId: string;
  totalTasks: number;
  linkedTasks: number;
  createdLinks: number;
  updatedLinks: number;
  updatedAt: string;
}

export interface OrgModelSettings {
  organization: OrgProfileSettings;
  departments: OrgDepartmentSettings[];
  roles: OrgRoleTemplateSettings[];
  bindings: OrgEmployeeBindingSettings[];
  reportingLines: OrgReportingLineSettings[];
  taskControlRules: OrgTaskControlRuleSettings[];
  roleProcessTemplates: OrgRoleProcessTemplateSettings[];
  focusItems: OrgFocusItemSettings[];
  departmentPlans: OrgDepartmentPlanSettings[];
  updatedAt: string;
}

export interface MentionCandidate {
  id: string;
  fullName: string;
  email: string;
  primaryRole: EmployeeRole;
  isSelf: boolean;
}

export interface HealthResponse {
  backend: 'online';
  appName: string;
  appVersion: string;
  buildVersion: string;
  backendBuildHash?: string;
  backendSchemaVersion?: number;
  runtimeMode?: 'packaged' | 'dev';
  startedAt: string;
  featureFlags: string[];
  dataDir: string;
  stats: {
    clients: number;
    tasks: number;
    topics: number;
    handbookEntries: number;
    analysisRuns: number;
  };
  ai: {
    provider: AiProvider;
    model: string;
    ready: boolean;
    detail: string;
    credentialSource: string;
    fingerprint?: string | null;
  };
}

export interface ClientSummary {
  id: string;
  name: string;
  alias: string;
  domain: string;
  type: string;
  intro: string;
  stage: string;
  color?: string;
  folderCount: number;
  documentCount: number;
  taskCount: number;
  lastActivityAt?: string | null;
}

export interface ClientFolder {
  id: string;
  clientId: string;
  label: string;
  path: string;
  fileCount: number;
  lastScannedAt?: string | null;
}

export interface DocumentRecord {
  id: string;
  clientId: string;
  folderId?: string | null;
  title: string;
  path: string;
  kind: string;
  source: 'folder' | 'file' | 'meeting';
  excerpt: string;
  tags: string[];
  importedAt: string;
}

export interface KnowledgeStatus {
  totalDocuments: number;
  totalChunks: number;
  vectorizedDocuments: number;
  dedupedDocuments: number;
  reviewPendingDocuments: number;
  surrogateCount: number;
  memoryDocCount: number;
  masterIndexCount: number;
  reclassifiedDocumentCount: number;
  qdrantReady: boolean;
  lastUpdatedAt?: string | null;
  pendingJobs: number;
  runningJobs: number;
  lastJobStatus: 'idle' | 'queued' | 'running' | 'completed' | 'failed';
  lastJobError?: string | null;
  lastSuccessfulRunAt?: string | null;
  embeddingMode: string;
  embeddingModel?: string | null;
  embeddingError?: string | null;
  embeddingProvider?: string | null;
  embeddingDimension?: number | null;
  embeddingSignature?: string | null;
  activeVectorCollection?: string | null;
  vectorIndexStatus?: 'ready' | 'stale' | 'building' | 'failed' | null;
  routerEnabled?: boolean;
  routerModel?: string | null;
  rerankEnabled?: boolean;
}

export interface OrganizationNotebookSnapshot {
  id: string;
  clientId: string;
  organizationIntro: string;
  collaborationRelationship: string;
  currentStage: string;
  businessModules: string[];
  keyPeople: string[];
  keyProducts: string[];
  currentChallenges: string[];
  collaborationGoals: string[];
  recentFacts: string[];
  informationGaps: string[];
  updatedAt: string;
  confidence: number;
}

export interface EventLineMemorySnapshot {
  id: string;
  eventLineId: string;
  lineName: string;
  currentStage: string;
  currentWork: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  evidenceRefs: string[];
  clarificationNeeds: string[];
  analysisSignals: string[];
  predictionReadiness: number;
  updatedAt: string;
  confidence: number;
}

export interface MemoryFact {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  factKey: string;
  factValue: string;
  sourceType: string;
  sourceId: string;
  confidence: number;
  freshness: number;
  evidenceRefs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ClarificationRecord {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  slotKey: string;
  question: string;
  status: 'pending' | 'answered';
  answerText?: string | null;
  writeScope: string[];
  resolvedFactIds: string[];
  reusable: boolean;
  createdAt: string;
  answeredAt?: string | null;
  updatedAt: string;
}

export interface MemoryStatus {
  clientId: string;
  notebookCompleteness: number;
  notebookConfidence: number;
  eventLineCoverage: number;
  totalEventLines: number;
  coveredEventLines: number;
  pendingClarifications: number;
  lowEvidenceJudgments: number;
  updatedAt: string;
}

export interface BackgroundReadiness {
  score: number;
  level: 'low' | 'medium' | 'high';
  missingSlots: string[];
  backgroundSources: string[];
}

export interface DocumentCard {
  id: string;
  docId: string;
  clientId: string;
  documentId: string;
  title: string;
  originalPath: string;
  sourcePath: string;
  logicalCategory?: string | null;
  logicalSubcategory?: string | null;
  classificationReason?: string | null;
  importSourcePath?: string | null;
  currentHumanPath?: string | null;
  humanFolderCategory?: string | null;
  normalizedPath?: string | null;
  surrogateMdPath?: string | null;
  kind: string;
  primaryCategory: string;
  secondaryCategory: string;
  shortSummary: string;
  summary: string;
  retrievalSummary: string;
  documentRole: string;
  queryHints: string[];
  distinctFindings: string[];
  coreQuestions: string[];
  keywords: string[];
  tags: string[];
  entities: string[];
  dateRange?: string | null;
  classificationConfidence: number;
  needsReview: boolean;
  deepRead: boolean;
  lastHitQuestion?: string | null;
  dedupStatus: string;
  vectorStatus: string;
  version: number;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ImportRecord {
  id: string;
  clientId: string;
  sourcePath: string;
  mode: 'folder' | 'file';
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'scanned';
  importedCount: number;
  skippedCount: number;
  createdAt: string;
}

export interface WorkspaceImportBackfillResponse {
  importId: string;
  jobId: string;
  sourceRoot: string;
  discovered: number;
  imported: number;
  skipped: number;
}

export interface ClientTemplateFillField {
  label: string;
  value: string;
  status: 'filled' | 'missing';
  evidenceTitles: string[];
  webSourceTitles?: string[];
  fieldType?: 'precise_fact' | 'structural_summary' | 'governance_mechanism' | 'quantitative_result' | 'attachment_material' | 'general' | null;
  valueKind?: 'fact' | 'summary' | 'inference' | 'missing' | null;
  confidence?: number | null;
  basisSummary?: string | null;
  followUpQuestion?: string | null;
  suggestedSources?: string[];
  reviewRequired?: boolean;
}

export interface ClientTemplateFillResponse {
  path: string;
  fileName: string;
  fieldCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
}

export interface ClientTemplateFillRun {
  id: string;
  clientId: string;
  templateName: string;
  templatePath: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: 'queued' | 'parsing' | 'retrieving' | 'writing' | 'completed' | 'failed';
  progress: number;
  stageLabel?: string | null;
  elapsedMs: number;
  fieldCount: number;
  processedCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  currentFieldLabel?: string | null;
  evidenceTitles: string[];
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
  outputPath?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GoalRecord {
  id: string;
  clientId: string;
  title: string;
  quarter: string;
  progress: number;
  ownerName: string;
}

export interface DnaTerm {
  id: string;
  clientId: string;
  category: string;
  canonicalName: string;
  aliases: string[];
  description: string;
  sourceLevel: DnaSourceLevel;
}

export interface EvidenceItem {
  id: string;
  title: string;
  excerpt: string;
  sourceType: string;
  documentId?: string | null;
  path?: string | null;
  score?: number | null;
  coverage?: number | null;
  sectionLabel?: string | null;
  retrievalStage?: 'master_index' | 'surrogate' | 'raw_chunk' | null;
  isFallback?: boolean;
  matchedTerms: string[];
}

export interface AiStructuredResponse {
  content: string;
  judgment: string;
  analysis: string;
  actions: string;
  timeline: string;
}

export type JudgmentQueryMode = 'registry_only' | 'hybrid' | 'evidence_based_synthesis';

export type EvidenceSupportMode =
  | 'none'
  | 'linked_state_evidence'
  | 'evidence_cards'
  | 'raw_doc_drilldown'
  | 'generic_retrieval_fallback';

export type WorkspaceAnswerIntent =
  | 'intro_profile'
  | 'project_intro'
  | 'meeting_summary'
  | 'next_actions'
  | 'official_judgment_registry'
  | 'evidence_question'
  | 'status_progress'
  | 'general';

export type RetrievalDecisionReason =
  | 'state_first_default'
  | 'document_drilldown_requested'
  | 'search_cache_requested'
  | 'intro_query_needs_evidence'
  | 'identity_query_needs_evidence'
  | 'project_intro_needs_evidence'
  | 'meeting_summary_needs_evidence'
  | 'next_actions_needs_evidence'
  | 'evidence_question_needs_evidence'
  | 'official_registry_requested'
  | 'status_progress_needs_hybrid_evidence'
  | 'default_hybrid_evidence'
  | 'state_pool_insufficient'
  | 'state_pool_empty';

export type PageContextPage =
  | 'client_workspace'
  | 'workspace_chat'
  | 'task_detail'
  | 'task_ai'
  | 'meeting_detail'
  | 'mobile_consult'
  | 'topic_radar'
  | 'strategic_cockpit';

export type PageIntentType =
  | 'intro_profile'
  | 'project_intro'
  | 'meeting_summary'
  | 'next_actions'
  | 'official_judgment_registry'
  | 'evidence_question'
  | 'status_progress'
  | 'task_context'
  | 'task_next_action'
  | 'general';

export type AnswerLevel = 'official' | 'candidate' | 'evidence_based' | 'fallback' | 'insufficient';
export type ContextQualityLevel = 'none' | 'weak' | 'usable' | 'strong';

export interface PageIntent {
  rawPrompt: string;
  intent: PageIntentType;
  requiresOfficialJudgment: boolean;
  requiresRawEvidence: boolean;
  requiresNextActions: boolean;
  requiresIntroProfile: boolean;
  requiresTaskContext: boolean;
  routeReason: string;
}

export interface ContextQuality {
  stateObjectCount: number;
  approvedJudgmentCount: number;
  candidateJudgmentCount: number;
  evidenceCardCount: number;
  rawEvidenceCount: number;
  openQuestionCount: number;
  taskCount: number;
  meetingCount: number;
  contextQuality: ContextQualityLevel;
  canUseAnalysisFirst: boolean;
  mustFallbackToLegacy: boolean;
}

export type RouteMode =
  | 'registry_only'
  | 'raw_doc_drilldown'
  | 'meeting_evidence'
  | 'task_context'
  | 'state_first'
  | 'hybrid';

export interface RetrievalModelSettings {
  embeddingProvider: string;
  embeddingModel: string;
  embeddingDimension: number;
  embeddingMode: 'local' | 'doubao' | 'hash_fallback';
  routerEnabled: boolean;
  routerProvider: string;
  routerModel: string;
  rerankEnabled: boolean;
  rerankProvider: string;
  shadowMode: boolean;
  updatedAt: string;
}

export type RetrievalMode = 'state_only' | 'raw_only' | 'hybrid' | 'deferred';

export interface RouteDecision {
  intent: PageIntentType;
  routeMode: RouteMode;
  dataSources: string[];
  retrievalMode: RetrievalMode;
  judgmentQueryMode?: JudgmentQueryMode | null;
  evidenceSupportMode?: EvidenceSupportMode | null;
  shouldUseRawEvidence: boolean;
  shouldUseStatePool: boolean;
  shouldUseTaskContext: boolean;
  shouldUseMeetingContext: boolean;
  shouldCreateProposal: boolean;
  queryPlan: string[];
  embeddingProfile: string;
  rerankNeeded: boolean;
  answerLevelHint: 'auto' | AnswerLevel;
  confidence: number;
  routeReason: string;
  routerSource: 'rules' | 'smart_router' | 'fallback';
  fallbackUsed: boolean;
}

export interface RetrievalTrace {
  routeDecision: RouteDecision;
  embeddingProvider: string;
  embeddingModel: string;
  embeddingDimension: number;
  embeddingSignature: string;
  vectorCollection?: string | null;
  lexicalHitCount: number;
  vectorHitCount: number;
  mergedHitCount: number;
  rerankHitCount: number;
  rawChunkHitCount: number;
  fallbackUsed: boolean;
  latencyMs: Record<string, number>;
}

export interface RetrievalHealthComponent {
  provider: string;
  model: string;
  dimension?: number | null;
  signature?: string | null;
  ready: boolean;
  error?: string | null;
}

export interface RetrievalHealth {
  embedding: RetrievalHealthComponent;
  router: RetrievalHealthComponent;
  rerank: {
    enabled?: boolean;
    provider?: string;
  };
  shadowMode: boolean;
}

export interface RetrievalShadowRun {
  id: string;
  clientId: string;
  page: string;
  prompt: string;
  baselineSummary: Record<string, unknown>;
  candidateSummary: Record<string, unknown>;
  overlapRate: number;
  candidateBetter: boolean;
  failureReason?: string | null;
  createdAt: string;
}

export interface RetrievalShadowSummary {
  total: number;
  candidateBetterRate: number;
  overlapRateAvg: number;
  latencyDeltaMsAvg: number;
  failures: number;
}

export interface AnswerPolicy {
  canAnswer: boolean;
  answerLevel: AnswerLevel;
  mustDiscloseCandidateBoundary: boolean;
  mustUseRawEvidence: boolean;
  shouldCreateProposal: boolean;
  fallbackToLegacyRetrieval: boolean;
  reason: string;
}

export interface PageContextPack {
  page: PageContextPage;
  scopeType: string;
  scopeId: string;
  clientId?: string | null;
  intent: PageIntentType;
  officialJudgments: Array<Record<string, unknown>>;
  candidateJudgments: Array<Record<string, unknown>>;
  overlayJudgments: Array<Record<string, unknown>>;
  evidenceCards: Array<Record<string, unknown>>;
  rawEvidence: Array<Record<string, unknown>>;
  openQuestions: Array<Record<string, unknown>>;
  conflicts: Array<Record<string, unknown>>;
  themeClusters: Array<Record<string, unknown>>;
  relatedTasks: Array<Record<string, unknown>>;
  relatedMeetings: Array<Record<string, unknown>>;
  relatedDocuments: Array<Record<string, unknown>>;
  notebookSummary?: Record<string, unknown> | null;
  memoryFacts: string[];
  contextPack?: Record<string, unknown> | null;
  judgmentBundle?: Record<string, unknown> | null;
  resolutionTrace?: Record<string, unknown> | null;
  stateProjection?: Record<string, unknown> | null;
  missingContext: string[];
  boundaryNotes: string[];
  sourceSummary: Record<string, number>;
  answerPolicy: AnswerPolicy;
  retrievalPlan: Record<string, unknown>;
  quality: ContextQuality;
  routeDecision?: RouteDecision | null;
  retrievalTrace?: RetrievalTrace | null;
}

export type FallbackPresentationMode = 'state_cards_only' | 'compact_user_answer' | 'full_answer';

export interface StateAnswerSections {
  official: string[];
  candidate: string[];
  draftFindings: string[];
  evidenceSupport: string[];
  actions: string[];
  risks: string[];
  unknowns: string[];
}

export interface StateSourceSummary {
  judgments: number;
  meetings: number;
  tasks: number;
  openQuestions: number;
  conflicts: number;
  documents: number;
}

export interface ChatMessage {
  id: string;
  threadId: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  status: 'success' | 'loading';
  modelRoute?: string | null;
  llmInvoked?: boolean;
  providerUsed?: string | null;
  answerMode?: 'grounded_answer' | 'grounded_fallback' | 'low_confidence_answer' | 'general_answer' | 'system_failure' | null;
  evidenceStatus?: 'sufficient' | 'partial' | 'none' | null;
  failureReason?: string | null;
  fallbackReason?: string | null;
  fallbackPresentationMode?: FallbackPresentationMode | null;
  stateConfidence?: 'low' | 'medium' | 'high' | null;
  stateSources?: string[];
  boundaryNotes?: string[];
  answerIntent?: WorkspaceAnswerIntent | null;
  retrievalDecisionReason?: RetrievalDecisionReason | null;
  judgmentQueryMode?: JudgmentQueryMode | null;
  evidenceSupportMode?: EvidenceSupportMode | null;
  stateAnswerSections?: StateAnswerSections | null;
  stateSourceSummary?: StateSourceSummary | null;
  timing?: Record<string, number>;
  retrievalSummary?: Record<string, unknown>;
  structuredData?: AiStructuredResponse | null;
  evidence: EvidenceItem[];
}

export interface ChatThread {
  id: string;
  clientId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatStartResponse {
  threadId: string;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
  analysisRun: ClientAnalysisRun;
}

export interface ChatThreadDetailResponse {
  thread: ChatThread;
  messages: ChatMessage[];
}

export interface WorkspaceStateItem {
  id: string;
  signalType: 'change' | 'progress' | 'risk' | 'question' | 'judgment' | 'meeting' | 'task' | 'noise';
  sourceType: string;
  sourceId: string;
  title: string;
  summary: string;
  authority: 'approved' | 'candidate' | 'informational' | 'warning';
  updatedAt?: string | null;
}

export interface WorkspaceStateProjection {
  changeItems: WorkspaceStateItem[];
  progressItems: WorkspaceStateItem[];
  signalNoiseFlags: string[];
  boundaryNotes: string[];
  stateConfidence: 'low' | 'medium' | 'high';
}

export interface StateQueryPlan {
  primaryIntent: 'overview' | 'changes' | 'progress' | 'risk' | 'questions' | 'judgment' | 'timeline';
  focusAreas: string[];
  needsBoundaryGuard: boolean;
}

export interface StateQueryHit {
  sourceType: string;
  sourceId: string;
  label: string;
  summary: string;
  signalKind: 'change' | 'progress' | 'risk' | 'question' | 'judgment' | 'timeline';
  authorityLevel: 'approved' | 'candidate' | 'informational' | 'warning';
}

export interface StateAnswerContextPack {
  plan: StateQueryPlan;
  summary: string;
  stateSources: string[];
  boundaryNotes: string[];
  stateConfidence: 'low' | 'medium' | 'high';
  hits: StateQueryHit[];
  sections: StateAnswerSections;
  sourceSummary: StateSourceSummary;
  candidateLeakageCount: number;
  fallbackReason?: string | null;
}

export interface AgendaItem {
  id: string;
  title: string;
  description: string;
}

export interface DecisionItem {
  id: string;
  summary: string;
}

export interface RiskItem {
  id: string;
  summary: string;
  severity: Priority;
}

export interface AmbiguityItem {
  id: string;
  rawText: string;
  candidates: string[];
  status: 'pending' | 'resolved';
}

export interface MeetingSummary {
  id: string;
  clientId: string;
  title: string;
  stage: MeetingStage;
  scheduledAt?: string | null;
  updatedAt: string;
}

export interface MeetingDetail extends MeetingSummary {
  transcriptText: string;
  notes: string;
  agendaItems: AgendaItem[];
  decisions: DecisionItem[];
  actionItems: Task[];
  risks: RiskItem[];
  ambiguities: AmbiguityItem[];
}

export interface FeishuMeetingLaunchResult {
  meeting: MeetingDetail;
  deliveryStatus: 'sent' | 'skipped' | 'failed';
  deliveryMessage: string;
  commandHint: string;
  noticeText: string;
  deliveryMode: 'bound_user' | 'configured_receiver' | 'none';
  deliveryTarget?: string | null;
}

export interface TaskList {
  id: string;
  name: string;
  color: string;
  sortOrder: number;
  isDefault: boolean;
  scope?: 'org' | 'personal';
  archivedAt?: string | null;
}

export interface TaskTag {
  id: string;
  name: string;
  color: string;
  scope: 'org' | 'self';
  ownerUserId?: string | null;
  createdBy?: string | null;
  updatedAt: string;
  archivedAt?: string | null;
}

export interface Task {
  id: string;
  title: string;
  desc: string;
  status: TaskStatus;
  creatorId?: string | null;
  creatorName?: string | null;
  priority: Priority;
  listId: string;
  listName: string;
  listColor: string;
  ddl: string;
  startDate?: string | null;
  dueDate?: string | null;
  durationMinutes?: number;
  scopeMode?: TaskScopeMode;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  ownerId?: string | null;
  ownerName: string;
  sourceType: string;
  sourceId?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  evidenceCount: number;
  tags: TaskTag[];
  note?: string | null;
  attachments: TaskAttachment[];
  collaborators: TaskCollaborator[];
  collaborationSummary: Record<string, number>;
  viewerInboxStatus?: CollaboratorInboxStatus | null;
  orgContext?: TaskOrgContext | null;
  projectContext?: TaskProjectContext | null;
  memoryHints?: string[];
  backgroundReadiness?: BackgroundReadiness | null;
  linkedFactsPreview?: MemoryFact[];
  syncStatus?: 'local' | 'syncing' | 'synced' | 'pending' | 'error' | null;
  createdAt: string;
  updatedAt: string;
}

export interface TaskAttachment {
  id: string;
  taskId: string;
  clientId: string;
  eventLineId?: string | null;
  documentId?: string | null;
  title: string;
  summary?: string | null;
  path: string;
  kind: string;
  source: string;
  sizeBytes: number;
  createdAt: string;
}

export type TaskAttachmentRecord = TaskAttachment;

export interface TaskOrgContext {
  departmentId?: string | null;
  roleTemplateId?: string | null;
  controlRuleId?: string | null;
  controlLevel?: OrgTaskControlLevel | null;
  organizationFocusKey?: string | null;
  departmentFocusKey?: string | null;
  focusItemId?: string | null;
  departmentPlanItemId?: string | null;
  isCrossDepartment: boolean;
  approvalState?: string | null;
  blockedAtStep?: string | null;
  needsReview: boolean;
}

export interface TaskProjectContext {
  clientId: string;
  clientName: string;
  stage?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectModuleSummary?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectFlowSummary?: string | null;
  backgroundSummary: string;
  goalSummary: string;
  riskSummary: string;
  currentFocus?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentProgress?: string | null;
  infoCompleteness: 'low' | 'medium' | 'high';
  sourceEvidence: string[];
}

export type EventLineKind = 'project_line' | 'issue_line' | 'coordination_line' | 'case_line' | 'custom';
export type EventLineStatus = 'active' | 'blocked' | 'paused' | 'done' | 'archived';
export type EventLineVisibilityScope = 'private' | 'project_public';

export interface EventLine {
  id: string;
  name: string;
  kind: EventLineKind;
  status: EventLineStatus;
  visibilityScope: EventLineVisibilityScope;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount: number;
  ownerId?: string | null;
  ownerName?: string | null;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
  primaryDepartmentId?: string | null;
  primaryDepartmentName?: string | null;
  participantIds: string[];
  closedAt?: string | null;
  closedByUserId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface EventLineActivity {
  id: string;
  eventLineId: string;
  sourceType: 'task_activity' | 'meeting' | 'support_request' | 'review' | 'attachment' | 'manual_note';
  sourceId: string;
  happenedAt: string;
  actorId?: string | null;
  actorName?: string | null;
  title: string;
  summary: string;
  metadata?: Record<string, unknown>;
  isKey?: boolean;
}

export interface EventLineDetail {
  eventLine: EventLine;
  tasks: Task[];
  activities: EventLineActivity[];
  memorySnapshot?: EventLineMemorySnapshot | null;
  predictionReadiness?: number | null;
  clarificationNeeds?: string[];
}

export interface TaskSmartBriefActionItem {
  text: string;
  sourceLabel: string;
  internalSuggestedOwner?: string;
  actionKind?: string;
  dueHint?: string;
  deliverable?: string;
  actionKey?: string;
  taskTitleSuggestion?: string;
  taskDescriptionSuggestion?: string;
}

export interface TaskSmartBrief {
  taskId: string;
  summary: string;
  summarySourceLabels: string[];
  actionItems: TaskSmartBriefActionItem[];
}

export interface PrepPackMaterial {
  sourceType: string;
  sourceId: string;
  title: string;
  summary: string;
  authorityLevel?: string;
}

export interface PrepPackCard {
  taskId: string;
  title: string;
  summary: string;
  materials: PrepPackMaterial[];
  openQuestions: string[];
  judgments: string[];
  risks: string[];
  boundaryNotes: string[];
  sourceLabels: string[];
  proposalId?: string | null;
}

export interface ProposalTargetRef {
  targetType: 'client' | 'task' | 'meeting' | 'event_line' | 'judgment';
  targetId: string;
  label: string;
}

export interface ProposalRecord {
  id: string;
  clientId: string;
  kind: 'task_prep' | 'meeting_prep' | 'meeting_followup';
  status: 'draft' | 'pending_review' | 'approved' | 'rejected' | 'execution_pending' | 'executed' | 'failed';
  riskLevel: 'low' | 'medium' | 'high';
  title: string;
  summary: string;
  rationale: string;
  targetRefs: ProposalTargetRef[];
  sourceRefs: string[];
  boundaryNotes: string[];
  payload: Record<string, unknown>;
  createdBy: string;
  decidedBy?: string | null;
  decidedAt?: string | null;
  rejectedReason?: string | null;
  executionTicketId?: string | null;
  executionTicket?: ExecutionTicket | null;
  createdAt: string;
  updatedAt: string;
}

export type ExecutionTicketResultType = 'recorded_only' | 'prep_artifact_ready' | 'followup_task_created' | 'failed';

export interface ExecutionTicketArtifactRef {
  artifactType: string;
  refId: string;
  title: string;
}

export interface ExecutionTicketResult {
  resultType: ExecutionTicketResultType;
  summary: string;
  createdTaskIds: string[];
  artifactRefs: ExecutionTicketArtifactRef[];
}

export interface ExecutionTicket {
  id: string;
  proposalId: string;
  clientId: string;
  executionType: string;
  status: 'pending' | 'running' | 'executed' | 'failed';
  payload: Record<string, unknown>;
  result: ExecutionTicketResult;
  errorMessage?: string | null;
  executedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProposalExecutionResponse {
  proposal: ProposalRecord;
  executionTicket?: ExecutionTicket | null;
}

export interface EventLineReportAttachment {
  id: string;
  taskId: string;
  title: string;
  kind: string;
  mimeType?: string | null;
  sizeBytes: number;
  downloadUrl: string;
  actorName?: string | null;
  createdAt: string;
}

export interface EventLineReportSnapshot {
  eventLine: EventLine;
  activities: EventLineActivity[];
  tasks: Task[];
  attachments: EventLineReportAttachment[];
  participantNames: string[];
  snapshotAt: string;
}

/** 事件线文档附件 — 为 PDF 汇报功能预留 */
export type EventLineAttachmentDisplayMode = 'expanded' | 'collapsed';

export interface EventLineAttachment {
  id: string;
  eventLineId: string;
  fileName: string;
  fileType: string;
  displayMode: EventLineAttachmentDisplayMode;
  description: string;
  uploadedBy: string;
  uploadedAt: string;
  /** 本地文件路径（不同步到云端） */
  localPath?: string | null;
  /** 票据/图片预览 URL */
  previewUrl?: string | null;
}

/** 事件线审批节点 */
export type EventLineApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface EventLineApprovalNode {
  id: string;
  eventLineId: string;
  title: string;
  requestedBy: string;
  approverName: string;
  status: EventLineApprovalStatus;
  note: string;
  createdAt: string;
  resolvedAt?: string | null;
}

export interface EventLineMutationPayload {
  name: string;
  kind?: EventLineKind;
  status?: EventLineStatus;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount?: number | null;
  ownerId?: string | null;
  primaryClientId?: string | null;
  primaryDepartmentId?: string | null;
  participantIds?: string[];
  syncLinkedTaskClientIds?: boolean;
}

export interface EventLineClarificationDraftPayload {
  conversationText: string;
}

export interface EventLineClarificationDraftResult {
  summary: string;
  stage: string;
  intent: string;
  currentBlocker: string;
  nextStep: string;
  recentDecision: string;
  missingInfo: string[];
  confidence: 'low' | 'medium' | 'high';
}

export interface ProjectModule {
  id: string;
  clientId: string;
  name: string;
  alias?: string | null;
  goal: string;
  description: string;
  ownerName?: string | null;
  deliverables: string[];
  keywords: string[];
  templateTasksJson?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectFlow {
  id: string;
  clientId: string;
  moduleId: string;
  moduleName?: string | null;
  name: string;
  description: string;
  scenario: string;
  triggerCondition: string;
  steps: string[];
  inputs: string[];
  outputs: string[];
  collaborators: string[];
  riskPoints: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ProjectStructureResponse {
  modules: ProjectModule[];
  flows: ProjectFlow[];
}

export interface ProjectModuleDetail extends ProjectModule {
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  flowIds: string[];
  flowNames: string[];
  contextSummary: string;
}

export interface ProjectFlowDetail extends ProjectFlow {
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  contextSummary: string;
}

export interface TaskCollaborator {
  userId: string;
  fullName: string;
  email: string;
  orderIndex: number;
  isOwner: boolean;
  inboxStatus: CollaboratorInboxStatus;
  returnReason?: string | null;
  handledAt?: string | null;
}

export interface TaskActivityRecord {
  id: string;
  taskId: string;
  actorId: string;
  actorName: string;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface WeeklyReview {
  id: string;
  userId: string;
  userName: string;
  weekLabel: string;
  workProgress?: string;
  workBlocker?: string;
  blockerType?: string;
  workDirection?: string;
  nextWeekFocus?: string;
  supportNeeded?: string;
  relatedPlanIds?: string[];
  workFreeNote?: string;
  personalGrowthNote?: string;
  personalPrivateNote?: string;
  personalVisibility?: 'self';
  submittedAt: string;
  createdAt: string;
  updatedAt: string;
}

export interface AgentWorklog {
  id: string;
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  date: string;
  weekLabel: string;
  title: string;
  summary: string;
  detailLines: string[];
  sourceType: 'activity_log' | 'topic_capture' | 'workspace_sync';
  createdAt: string;
}

export interface AgentWeeklyDigest {
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  weekLabel: string;
  summary: string;
  focusItems: string[];
  evidenceCount: number;
  sourcePolicy: Record<string, unknown>;
}

export interface AgentWeeklyPlanItem {
  id: string;
  title: string;
  rationale: string;
  scheduleHint: string;
  status: AgentPlanStatus;
}

export interface AgentWeeklyPlan {
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  weekLabel: string;
  summary: string;
  planItems: AgentWeeklyPlanItem[];
  sourcePolicy: Record<string, unknown>;
}

export interface AgentWorklogResponse {
  month: string;
  worklogs: AgentWorklog[];
  weeklyDigests: AgentWeeklyDigest[];
  weeklyPlans: AgentWeeklyPlan[];
}

export interface AgentWeeklyPlanItemPayload {
  title: string;
  rationale: string;
  scheduleHint: string;
  status: AgentPlanStatus;
}

export interface AgentWeeklyPlanPayload {
  weekLabel: string;
  agentKey: AgentDepartmentKey;
  summary: string;
  planItems: AgentWeeklyPlanItemPayload[];
}

export interface WeeklyReviewTaskSnapshot {
  title: string;
  status: TaskStatus;
  startDate?: string | null;
  dueDate?: string | null;
  createdAt: string;
  ownerId?: string | null;
  ownerName?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  tags: TaskTag[];
  listName: string;
  listColor: string;
  orgContext?: TaskOrgContext | null;
  projectContext?: TaskProjectContext | null;
  eventLineContext?: WeeklyReviewEventLineContext | null;
}

export interface WeeklyReviewEventLineContext {
  id?: string | null;
  name?: string | null;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount: number;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
}

export interface WeeklyReviewTaskStructuredNote {
  reflection: string;
  lightweightTag: ReviewLightweightTag;
  planCommitment: string;
  progress: string;
  completionStatus: ReviewCompletionStatus;
  departmentPlanId?: string | null;
  departmentPlanAlignment: ReviewAlignmentStatus;
  organizationPlanId?: string | null;
  organizationPlanAlignment: ReviewAlignmentStatus;
  successReason: string;
  successExperience: string;
  blockerReason: string;
  failureInsight: string;
  supportNeeded: string;
  nextAction: string;
}

export interface ReviewMetricCard {
  key: 'timely_completion' | 'department_alignment' | 'strategy_alignment' | 'reflection_capture';
  label: string;
  valueText: string;
  numerator: number;
  denominator: number;
  rate: number;
  description: string;
  tone: 'positive' | 'neutral' | 'warning' | 'risk';
}

export interface WeeklyReviewTaskEntry {
  id: string;
  reviewId?: string | null;
  taskId: string;
  weekLabel: string;
  contentDomain: 'work' | 'personal';
  note: string;
  structuredNote: WeeklyReviewTaskStructuredNote;
  reviewedAt?: string | null;
  taskSnapshot: WeeklyReviewTaskSnapshot;
}

export interface ReviewEvidenceWeight {
  sourceType: 'user_note' | 'task_fact' | 'organization_dna' | 'team_plan' | 'focus_plan' | 'project_context' | 'external_context';
  label: string;
  weight: 'high' | 'medium' | 'low';
  rationale: string;
}

export interface ReviewHypothesis {
  id: string;
  lens: 'execution' | 'organization' | 'business' | 'team' | 'market' | 'growth';
  title: string;
  statement: string;
  confidence: 'high' | 'medium' | 'low';
  reason: string;
  relatedTaskIds: string[];
  evidenceSources: string[];
  assumptionNote: string;
}

export interface EventLineEvidenceSlot {
  key:
    | 'stage'
    | 'goal'
    | 'blocker'
    | 'next_action'
    | 'recent_change'
    | 'owner_chain'
    | 'recent_decision'
    | 'project_link';
  label: string;
  coverage: 'full' | 'partial' | 'missing';
  evidenceStrength: 'strong' | 'medium' | 'weak' | 'none';
  sourceTypes: Array<'event_line' | 'task_fact' | 'project_context' | 'user_note' | 'uploaded_doc' | 'manual_clarification'>;
  summary: string;
  recommendedFix: 'upload_docs' | 'clarify_now' | 'wait_for_more_trace';
}

export interface EventLineCompleteness {
  eventLineId: string;
  title: string;
  score: number;
  status: 'insufficient' | 'summary_ready' | 'forecast_ready' | 'high_confidence';
  missingSlots: string[];
  strongestSlots: string[];
  memoryConfidence?: number | null;
  backgroundSources?: string[];
  slots: EventLineEvidenceSlot[];
}

export interface ReviewDashboardEvidenceRef {
  sourceType: 'task' | 'meeting' | 'support_request' | 'attachment' | 'clarification' | 'event_line' | 'notebook' | 'event_line_memory';
  sourceId: string;
  title: string;
  summary?: string;
}

export interface ReviewDashboardCardTarget {
  targetType: 'event_line' | 'task_view' | 'meeting' | 'support_request' | 'attachment_group' | 'task';
  targetId: string;
  targetLabel?: string;
  targetFilters?: Record<string, unknown>;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineContextFact {
  sourceType: 'task' | 'meeting' | 'attachment' | 'support_request' | 'clarification' | 'notebook' | 'event_line_memory';
  sourceId: string;
  title: string;
  summary: string;
  happenedAt?: string | null;
}

export interface EventLineJudgment {
  eventLineId: string;
  title: string;
  viewerRole: 'employee' | 'department_lead' | 'admin';
  judgmentVersion: string;
  bundleFingerprint: string;
  coverageScore: number;
  confidenceScore: number;
  safeOutputMode: 'needs_input' | 'summary_only' | 'full_judgment';
  publishState: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  whatHappened: string;
  whyItMatters: string;
  coreBlocker: string;
  blockerType: 'business' | 'collaboration' | 'decision' | 'structure' | 'capacity' | 'evidence';
  evidenceSummary: string;
  managerImplication: string;
  nextWeekFocus: string;
  minimumAction: string;
  riskIfIgnored: string;
  opportunityIfAmplified: string;
  evidenceRefs: ReviewDashboardEvidenceRef[];
  target?: ReviewDashboardCardTarget | null;
}

export interface EventLineContextBundle {
  eventLineId: string;
  lineName: string;
  businessCategory: string;
  stage: string;
  summary: string;
  intent: string;
  currentWork: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  recentProgress: string;
  projectName: string;
  collaborationRelationship: string;
  organizationIntro: string;
  currentChallenges: string[];
  collaborationGoals: string[];
  keyPeople: string[];
  keyProducts: string[];
  recentFacts: string[];
  taskFacts: EventLineContextFact[];
  meetingFacts: EventLineContextFact[];
  attachmentFacts: EventLineContextFact[];
  clarificationFacts: EventLineContextFact[];
  evidenceRefs: ReviewDashboardEvidenceRef[];
  trendSignals: TrendSignal[];
  taskCount: number;
  meetingCount: number;
  attachmentCount: number;
  supportRequestCount: number;
  readiness: 'low' | 'medium' | 'high';
}

export interface EventLineSummaryCard {
  eventLineId: string;
  title: string;
  kind: 'project_line' | 'issue_line' | 'coordination_line' | 'case_line' | 'custom';
  status: 'active' | 'blocked' | 'paused' | 'done' | 'archived';
  projectName?: string | null;
  moduleName?: string | null;
  flowName?: string | null;
  whatThisLineIs: string;
  whatHappenedThisWeek: string;
  currentState: string;
  mainBlocker: string;
  nextCriticalMove: string;
  ownerNames: string[];
  completenessScore: number;
  predictionReadiness: 'not_ready' | 'summary_only' | 'conservative_forecast' | 'strong_forecast';
  missingSlots: string[];
  memoryConfidence?: number | null;
  backgroundSources?: string[];
  evidencePreview: string[];
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineRiskCard {
  eventLineId: string;
  title: string;
  riskType: 'schedule_drift' | 'collaboration_friction' | 'decision_lag' | 'goal_drift' | 'workflow_breakdown' | 'overload';
  statement: string;
  forecastWindow: '1w' | '2w' | '3w';
  probability: 'high' | 'medium' | 'low';
  impactScope: 'person' | 'team' | 'project' | 'org';
  triggerSignals: string[];
  whyNow: string;
  ifIgnored: string;
  suggestedAction: string;
  ownerRole: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineOpportunityCard {
  eventLineId: string;
  title: string;
  opportunityType: 'repeatable_pattern' | 'momentum_building' | 'process_upgrade' | 'capability_signal' | 'leverage_point';
  statement: string;
  forecastWindow: '1w' | '2w' | '3w';
  confidence: 'high' | 'medium' | 'low';
  upside: string;
  supportingSignals: string[];
  recommendedAmplifier: string;
  ownerRole: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface TrendSignal {
  key: string;
  title: string;
  statement: string;
  signalType:
    | 'repeat_reschedule'
    | 'repeat_review_pending'
    | 'repeat_support_request'
    | 'stalled_event_line'
    | 'escalating_blocker'
    | 'thin_evidence';
  severity: 'high' | 'medium' | 'low';
  windowLabel: string;
  relatedEventLineId?: string | null;
  relatedTaskIds: string[];
  evidenceRefs: ReviewDashboardEvidenceRef[];
  target?: ReviewDashboardCardTarget | null;
}

export interface WeeklyReviewAnalysis {
  scope: TaskReviewScope;
  emphasis: 'summary' | 'analysis';
  headline: string;
  caution: string;
  weeklyOverview: string;
  weeklyFocusLines: string[];
  weeklyNextFocus: string[];
  dnaModuleTitles: string[];
  metricCards: ReviewMetricCard[];
  evidenceWeights: ReviewEvidenceWeight[];
  confirmedFacts: string[];
  hypothesisHighlights: ReviewHypothesis[];
  nextWeekFocus: string[];
  eventLineSummaries: EventLineSummaryCard[];
  eventLineCompleteness: EventLineCompleteness[];
  eventLineContextBundles: EventLineContextBundle[];
  eventLineJudgments: EventLineJudgment[];
  riskCards: EventLineRiskCard[];
  opportunityCards: EventLineOpportunityCard[];
  trendSignals: TrendSignal[];
  narrativeAnalyses: NarrativeAnalysis[];
}

export interface TaskContextPreview {
  taskId: string;
  clientId?: string | null;
  clientName?: string | null;
  contextBundle: EventLineContextBundle;
  judgment: EventLineJudgment;
  judgmentVersion: string;
  bundleFingerprint: string;
  coverageScore: number;
  confidenceScore: number;
  safeOutputMode: 'needs_input' | 'summary_only' | 'full_judgment';
  publishState: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  summaryChips: string[];
  readiness: 'low' | 'medium' | 'high';
}

export interface PlanNode {
  id: string;
  level: 'ceo' | 'director' | 'manager' | 'project';
  title: string;
  summary: string;
  status: string;
  ownerUserId?: string | null;
  ownerName?: string | null;
  ownerUnitId?: string | null;
  startsAt?: string | null;
  endsAt?: string | null;
}

export interface ManagementSignalCard {
  id: string;
  reviewId: string;
  userId: string;
  userName: string;
  weekLabel: string;
  contentDomain: 'work';
  visibilityScope: 'team' | 'department' | 'org';
  eligibleForAggregation: boolean;
  eligibleForManagerRetrieval: boolean;
  signals: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface PersonalGrowthCard {
  id: string;
  reviewId: string;
  userId: string;
  contentDomain: 'personal';
  visibilityScope: 'self';
  summary: string;
  suggestions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ReviewActionCard {
  id: string;
  actionType: 'task' | 'support_request' | 'resource_request' | 'meeting' | 'one_on_one';
  title: string;
  payload: Record<string, unknown>;
  status: string;
  createdAt: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface ReviewActionExecutionResult {
  objectType: 'task' | 'support_request' | 'meeting';
  objectId: string;
  objectLabel: string;
  targetClientId?: string | null;
  targetClientName?: string | null;
  targetEventLineId?: string | null;
  targetEventLineName?: string | null;
  canOpen?: boolean;
  supportRequest?: SupportRequestRecord;
}

export interface HierarchyReport {
  id: string;
  scopeType: 'employee' | 'team' | 'org';
  scopeRefId: string;
  weekLabel: string;
  logicMode: string;
  judgmentVersion?: string | null;
  bundleFingerprint?: string | null;
  coverageScore?: number | null;
  confidenceScore?: number | null;
  safeOutputMode?: 'needs_input' | 'summary_only' | 'full_judgment' | null;
  headline: string;
  summary: string;
  summaryMetrics: ReviewMetricCard[];
  focusAreas: string[];
  supportSignals: string[];
  suggestedActions: string[];
  anonymousInsights: string[];
  sourcePolicy: Record<string, unknown>;
  actions: ReviewActionCard[];
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface TaskViewFilterSet {
  sourceTypes?: string[];
  businessCategories?: string[];
  eventLineIds?: string[];
  onlyRisky?: boolean;
  onlyWithEventLine?: boolean;
  needsReview?: boolean | null;
  minimumEvidenceCount?: number | null;
}

export interface TaskViewDefinition {
  id: string;
  name: string;
  kind: 'event_line' | 'risk' | 'source' | 'business_category' | 'custom';
  description: string;
  calendarScope: 'all' | 'event_line' | 'risk' | 'source' | 'business_category';
  shareability: 'private' | 'org';
  sortBy: 'updatedAt' | 'dueDate' | 'priority' | 'evidenceCount';
  sortDirection: 'asc' | 'desc';
  visibleFields: string[];
  filterSet: TaskViewFilterSet;
  builtIn: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TaskViewPreset {
  key: 'event_line' | 'risk' | 'source' | 'business_category';
  label: string;
  description: string;
  viewId: string;
}

export interface TaskViewsResponse {
  views: TaskViewDefinition[];
  presets: TaskViewPreset[];
}

export interface TaskViewMutationPayload {
  name: string;
  kind?: 'event_line' | 'risk' | 'source' | 'business_category' | 'custom';
  description?: string;
  calendarScope?: 'all' | 'event_line' | 'risk' | 'source' | 'business_category';
  shareability?: 'private' | 'org';
  sortBy?: 'updatedAt' | 'dueDate' | 'priority' | 'evidenceCount';
  sortDirection?: 'asc' | 'desc';
  visibleFields?: string[];
  filterSet?: TaskViewFilterSet;
}

export interface ReviewDashboardDrillTargetResponse {
  target: ReviewDashboardCardTarget;
  eventLineDetail?: EventLineDetail | null;
  eventLineMemory?: EventLineMemorySnapshot | null;
  tasks: Task[];
  meetings: MeetingSummary[];
  supportRequests: SupportRequestRecord[];
  attachments: TaskAttachmentRecord[];
}

export interface ReviewSimulationBundle {
  sampleSize: number;
  label: string;
  orgReport?: HierarchyReport | null;
  departmentReports: HierarchyReport[];
}

export interface ReviewDashboard {
  currentReview?: WeeklyReview | null;
  workItems: WeeklyReviewTaskEntry[];
  personalItems: WeeklyReviewTaskEntry[];
  workAnalysis?: WeeklyReviewAnalysis | null;
  personalAnalysis?: WeeklyReviewAnalysis | null;
  selfReport?: HierarchyReport | null;
  workSignalCard?: ManagementSignalCard | null;
  personalGrowthCard?: PersonalGrowthCard | null;
  teamReport?: HierarchyReport | null;
  orgReport?: HierarchyReport | null;
  executiveOrgReport?: HierarchyReport | null;
  departmentReports: HierarchyReport[];
  agentDepartmentDigests: AgentWeeklyDigest[];
  agentDepartmentPlans: AgentWeeklyPlan[];
  simulationBundle?: ReviewSimulationBundle | null;
  plans: PlanNode[];
}

// ── UnderstandingSnapshotV1: 统一理解输出对象 ──

export type UnderstandingMode = 'basic' | 'enhanced';

export interface UnderstandingSourceBreakdown {
  sourceType: 'org_dna' | 'client_background' | 'quarterly_focus' | 'task_title' | 'task_desc' | 'review_note' | 'event_line_memory' | 'meeting' | 'support_request' | 'calendar' | 'attachment';
  available: boolean;
  label: string;
}

export interface UnderstandingOptionalAdvice {
  realBlocker?: string | null;
  timeGate?: string | null;
  minimumAction?: string | null;
  supportAsk?: string | null;
}

export interface UnderstandingSnapshotV1 {
  taskId: string;
  mode: UnderstandingMode;
  coverage: number;
  confidence: number;
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  optionalAdvice?: UnderstandingOptionalAdvice | null;
  sourceBreakdown: UnderstandingSourceBreakdown[];
}

// ── Phase 1: 客户战略画像 + 合作关系 + 事件线周历史 ──

export type CooperationType = 'strategic_companion' | 'single_project' | 'exploring' | 'dormant';
export type RelationshipHealth = 'thriving' | 'steady' | 'cooling' | 'at_risk';

/** 客户战略画像 — 补充 ClientSummary 中缺失的深层信息 */
export interface ClientStrategicProfile {
  clientId: string;
  industry: string;
  scale: string;
  influence: string;
  currentNeeds: string;
  painPoints: string;
  strategicValueToYiyu: string;
  decisionChain: string;
  updatedAt: string;
}

/** 益语与客户的合作关系 */
export interface CooperationRelationship {
  id: string;
  clientId: string;
  clientName: string;
  whyConnected: string;
  meaningToYiyu: string;
  meaningToClient: string;
  cooperationType: CooperationType;
  relationshipHealth: RelationshipHealth;
  keyStakeholders: CooperationStakeholder[];
  milestones: string;
  startedAt: string;
  updatedAt: string;
}

export interface CooperationStakeholder {
  name: string;
  role: string;
  relationship: string;
}

/** 事件线周快照历史 — 每周复盘时自动归档 */
export interface EventLineWeeklySnapshot {
  id: string;
  eventLineId: string;
  eventLineName: string;
  weekLabel: string;
  stageAtThatTime: string;
  keyDecisions: string[];
  turningPoints: string[];
  blockersThen: string[];
  progressDelta: string;
  taskCount: number;
  completedCount: number;
  createdAt: string;
}

/** 五层上下文叙事分析 — LLM 生成 */
export interface NarrativeAnalysis {
  eventLineId: string;
  eventLineName: string;
  clientId?: string | null;
  clientName?: string | null;
  whatThisIs: string;
  whyImportant: string;
  currentProgress: string;
  missingUnderstanding: string;
  riskNote?: string | null;
  timeGate?: string | null;
  minimumAction?: string | null;
  managementAdvice?: string | null;
  contextLayersUsed: string[];
  confidenceLevel: 'low' | 'medium' | 'high';
}

export type StrategicJudgmentStatus = 'system_draft' | 'confirmed' | 'waiting';
export type StrategicHealthStatus = 'healthy' | 'watch' | 'risk' | 'uncalibrated';
export type StrategicLineMomentum = '加码' | '稳住' | '收口' | '暂停';
export type StrategicItemPriority = 'high' | 'medium' | 'low';

export interface StrategicPermission {
  canEdit: boolean;
  isCeo: boolean;
  leaderUserId?: string | null;
  notice?: string | null;
}

export interface StrategicReadiness {
  status: 'ready' | 'insufficient';
  score: number;
  summary: string;
  gaps: string[];
}

export interface StrategicJudgment {
  value: string;
  status: StrategicJudgmentStatus;
  sources: string[];
}

export interface StrategicHeadline {
  weekSummary: StrategicJudgment;
  mainContradiction: StrategicJudgment;
  coreBreakthrough: StrategicJudgment;
  focusItems: string[];
  focusStatus: StrategicJudgmentStatus;
  freshness: string;
}

export interface StrategicHealthLine {
  key: string;
  title: string;
  status: StrategicHealthStatus;
  trend: string;
  summary: string;
  evidence: string[];
}

export interface StrategicLine {
  id: string;
  title: string;
  summary: string;
  module?: string | null;
  flow?: string | null;
  stage?: string | null;
  blocker: string;
  decision: string;
  nextStep: string;
  momentum: StrategicLineMomentum;
  evidence: string[];
  memoryConfidence?: number | null;
  predictionReadiness?: number | null;
  clarificationNeeds?: string[];
}

export interface StrategicLineDetail extends StrategicLine {
  clientId: string;
  clientName: string;
  stageLabel: string;
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  contextSummary: string;
}

export interface StrategicChecklistItem {
  title: string;
  detail: string;
  source: string;
  priority: StrategicItemPriority;
}

export interface StrategicChecklistGroup {
  key: string;
  title: string;
  description: string;
  items: StrategicChecklistItem[];
}

export interface StrategicChangePoint {
  title: string;
  summary: string;
  confidence: string;
  signals: string[];
}

export interface StrategicEvidenceCard {
  label: string;
  value: string;
}

export interface StrategicEvidencePreview {
  summary: string;
  cards: StrategicEvidenceCard[];
  boundaries: string[];
  keyFacts: string[];
  keyWarnings: string[];
}

export interface StrategicAssetCandidate {
  title: string;
  source: string;
  summary: string;
  nextAction: string;
}

export interface StrategicMeetingPackDraft {
  title: string;
  agenda: string[];
  groups: StrategicChecklistGroup[];
}

export interface StrategicCockpitSnapshot {
  clientId: string;
  clientName: string;
  clientTagline: string;
  stageLabel: string;
  permission: StrategicPermission;
  readiness: StrategicReadiness;
  headline: StrategicHeadline;
  health: StrategicHealthLine[];
  strategicLines: StrategicLine[];
  twoWeekChanges: StrategicChangePoint[];
  pendingDecisions: StrategicChecklistItem[];
  pendingMaterials: StrategicChecklistItem[];
  meetingPackDraft: StrategicMeetingPackDraft;
  evidencePreview: StrategicEvidencePreview;
  assetCandidates: StrategicAssetCandidate[];
  officialLayer: Record<string, unknown>;
  radarLayer: Record<string, unknown>;
  officialLayerStatus: 'ready' | 'empty';
  officialEmptyReason?: string | null;
  resolutionTrace: Record<string, unknown>;
  notebookSummary?: OrganizationNotebookSnapshot | null;
  memoryStatus?: MemoryStatus | null;
  linkedEventLineMemories?: EventLineMemorySnapshot[];
}

export interface StrategicCockpitConfirmPayload {
  weekSummary: string;
  mainContradiction: string;
  coreBreakthrough: string;
  focusItems: string[];
}

export type StrategicThoughtScope = 'client' | 'system';
export type StrategicThoughtStatus = 'draft' | 'confirmed' | 'dismissed' | 'task_created' | 'waiting_evidence';
export type StrategicThoughtConfidenceLevel = 'low' | 'medium' | 'high' | 'none';

export type StrategicThoughtSourceType =
  | 'strategic_cockpit'
  | 'strategic_line'
  | 'headline'
  | 'pending_decision'
  | 'pending_material'
  | 'brain_dashboard'
  | 'judgment_version'
  | 'theme_cluster'
  | 'conflict_group'
  | 'open_question'
  | 'event_line'
  | 'meeting'
  | 'review'
  | 'knowledge'
  | 'system';

export interface StrategicThoughtSource {
  sourceType: StrategicThoughtSourceType;
  sourceId?: string | null;
  label: string;
  detail?: string | null;
}

export interface StrategicThoughtReview {
  thoughtId: string;
  status: StrategicThoughtStatus;
  note: string;
  taskId?: string | null;
  judgmentId?: string | null;
  reviewedAt?: string | null;
  reviewedBy?: string | null;
}

export interface StrategicThought {
  id: string;
  scope: StrategicThoughtScope;
  clientId?: string | null;
  clientName: string;
  line: string;
  observation: string;
  suggestion: string;
  confidence?: number | null;
  confidenceLevel: StrategicThoughtConfidenceLevel;
  status: StrategicThoughtStatus;
  isSystem: boolean;
  dueDateHint: string;
  tags: string[];
  sources: StrategicThoughtSource[];
  evidenceCount: number;
  generatedAt: string;
  staleReason?: string | null;
  evidenceLevel?: 'none' | 'weak' | 'medium' | 'strong' | null;
  reason?: string | null;
  review?: StrategicThoughtReview | null;
}

export interface StrategicThoughtsResponse {
  items: StrategicThought[];
  total: number;
  generatedAt: string;
  selectedClientId?: string | null;
  usingMockData?: boolean;
}

export interface StrategicThoughtReviewPayload {
  action: 'confirm' | 'dismiss' | 'mark_task_created';
  note?: string;
  taskId?: string | null;
  createJudgment?: boolean;
}

export interface ReviewHistoryEntry {
  weekLabel: string;
  submittedAt: string;
  workItemCount: number;
  personalItemCount: number;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryEntry[];
}

export interface TaskSettings {
  defaultListId?: string | null;
  defaultPriority: Priority;
  defaultDueDatePreset: TaskDueDatePreset;
  defaultViewMode: TaskViewPreference;
  listSortMode: TaskListSortMode;
  showCompletedTasks: boolean;
  defaultReviewScope: TaskReviewScope;
  autoAssignSelf: boolean;
  updatedAt: string;
}

export interface ReviewDepartmentMember {
  id: string;
  fullName: string;
  email?: string | null;
}

export interface ReviewDepartmentConfig {
  id: string;
  name: string;
  color: string;
  monthlyDna: string;
  weeklyFocus: string;
  leaders: ReviewDepartmentMember[];
  members: ReviewDepartmentMember[];
}

export interface ReviewGovernanceSettings {
  departments: ReviewDepartmentConfig[];
  updatedAt: string;
}

export interface OrganizationDnaModule {
  moduleKey: OrganizationDnaModuleKey;
  title: string;
  markdownContent: string;
  normalizedText: string;
  summary: string;
  fileName?: string | null;
  contentHash?: string | null;
  updatedAt?: string | null;
  updatedBy?: string | null;
  hasDocument: boolean;
  readinessStatus: 'ready' | 'missing';
  readinessAnsweredCount: number;
  readinessQuestionCount: number;
  readinessSource: 'client_dna' | 'manual_document' | 'auto_enqueued' | 'none';
  readinessSummary: string;
  readinessQuestions: DnaReadinessQuestion[];
}

export interface OrganizationDnaResponse {
  modules: OrganizationDnaModule[];
}

export interface DnaReadinessQuestion {
  question: string;
  answered: boolean;
  evidence?: string | null;
}

export interface ClientDnaModule {
  clientId: string;
  moduleKey: OrganizationDnaModuleKey;
  title: string;
  markdownContent: string;
  normalizedText: string;
  summary: string;
  fileName?: string | null;
  contentHash?: string | null;
  sourceKind: 'manual' | 'generated';
  missingInfo: string[];
  updatedAt?: string | null;
  updatedBy?: string | null;
  hasDocument: boolean;
}

export interface ClientDnaModulesResponse {
  modules: ClientDnaModule[];
}

export interface ClientDnaGeneratePayload {
  refreshGenerated?: boolean;
}

export interface ClientWorkspaceSettings {
  useOrgDnaInChat: boolean;
  useOrgDnaInKnowledgeQa: boolean;
  meetingPublishDefaultListId?: string | null;
  meetingPublishDefaultPriority: Priority;
  defaultGoalQuarter: string;
  defaultMeetingTitlePrefix: string;
  clientDnaModeLabel: string;
  updatedAt: string;
}

export interface TopicsSettings {
  chineseOnly: boolean;
  requireInsightBeforeActions: boolean;
  defaultTaskOwnerMode: TopicTaskOwnerMode;
  defaultTimeRange: string;
  defaultSourceStrategy: string;
  useOrgDnaForInsight: boolean;
  useOrgDnaForTaskPlan: boolean;
  updatedAt: string;
}

export interface DiagnosisProfileRecord {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  deepDnaId?: string | null;
  label: string;
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  corePreferences: string[];
  riskTriggers: string[];
  tonePreference?: string;
  updatedAt: string;
}

export interface OrganizationRiskDnaDocument {
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  coreRisks: string[];
  sensitiveScenarios: string[];
  tonePreference?: string;
  updatedAt: string;
}

export interface FundraisingKnowledgeDocument {
  id: string;
  title: string;
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  scenes: string[];
  tags: string[];
  principles: string[];
  riskSignals: string[];
  updatedAt: string;
}

export interface DeepDnaSourceRecord {
  id: string;
  kind: 'manual' | 'import' | 'web';
  title: string;
  excerpt: string;
  sourceUrl?: string | null;
  fileName?: string | null;
  filePath?: string | null;
  createdAt: string;
}

export interface DeepDnaRecord {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  status: 'draft' | 'published';
  sourceKind: 'manual' | 'import' | 'web';
  identitySummary: string;
  corePreferences: string[];
  supportTriggers: string[];
  redFlags: string[];
  evidencePreferences: string[];
  voiceStyle: string[];
  commonQuestions: string[];
  sources: DeepDnaSourceRecord[];
  confidenceScore: number;
  confidenceLevel: 'low' | 'medium' | 'high';
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
  rawContent: string;
  searchQuery?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeepDnaDraft {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  searchQuery: string;
  draftRecord: DeepDnaRecord;
  previewSources: DeepDnaSourceRecord[];
  createdAt: string;
  updatedAt: string;
}

export interface CoachCaseRecord {
  id: string;
  title: string;
  summary: string;
  whyEffective: string;
  takeaways: string[];
  keyExcerpt: string;
  scenes: string[];
  tags: string[];
  issueTypes: string[];
  sourceType: 'system' | 'organization';
  sourceLabel: string;
  createdAt: string;
  updatedAt: string;
}

export interface CoachReminderRule {
  id: string;
  title: string;
  modeIds: string[];
  knowledgeKey: string;
  issuePattern: string;
  message: string;
  createdAt: string;
  updatedAt: string;
}

export interface OrgWritingNorm {
  id: string;
  title: string;
  description: string;
  instruction: string;
  modeIds: string[];
  triggerKeywords: string[];
  createdAt: string;
  updatedAt: string;
}

export interface CoachCardRecord {
  id: string;
  issueKey: string;
  insightTitle: string;
  issueWhat: string;
  whyImportant: string;
  knowledgePointTitle: string;
  knowledgePointBody: string;
  caseIds: string[];
  selfRewriteHint: string;
  learningAction: string;
  referenceDraft?: string | null;
}

export interface CoachPayload {
  cards: CoachCardRecord[];
  triggeredReminders: CoachReminderRule[];
  appliedNorms: OrgWritingNorm[];
}

export interface RunComparison {
  currentRunId: string;
  previousRunId?: string | null;
  resultChanges: string[];
  learningChanges: string[];
  resolvedIssues: string[];
  newIssues: string[];
  repeatedIssues: string[];
}

export interface AnalysisWorkbenchSettings {
  enabledTemplateIds: string[];
  defaultTemplateId?: string | null;
  defaultTitlePrefix: string;
  useOrgDna: boolean;
  allowEmployeeTemplateEditing: boolean;
  diagnosisProfiles: DiagnosisProfileRecord[];
  organizationRiskDna?: OrganizationRiskDnaDocument | null;
  fundraisingKnowledgeLibrary: FundraisingKnowledgeDocument[];
  deepDnaLibrary: DeepDnaRecord[];
  coachCaseLibrary: CoachCaseRecord[];
  coachReminderRules: CoachReminderRule[];
  orgWritingNorms: OrgWritingNorm[];
  updatedAt: string;
}

export interface HandbookSettings {
  defaultTags: string[];
  defaultCategory: string;
  allowTaskSource: boolean;
  allowAnalysisSource: boolean;
  visibilityBoundary: string;
  updatedAt: string;
}

export interface SystemAdminSettings {
  allowBusinessSettingsForEmployees: boolean;
  allowOrgDnaForEmployees: boolean;
  protectEmployeeAdmin: boolean;
  protectAiAndCloud: boolean;
  protectCloudSecurity: boolean;
  brandLogoDataUrl?: string | null;
  updatedAt: string;
}

export interface FeishuBotSettings {
  appId: string;
  receiveIdType: FeishuReceiveIdType;
  receiverId: string;
  botName: string;
  userBindingCallbackUrl: string;
  ready: boolean;
  hasAppSecret: boolean;
  secretSource: string;
  secretFingerprint?: string | null;
  lastConnectionStatus: 'idle' | 'success' | 'failed';
  lastConnectionMessage?: string | null;
  lastConnectedAt?: string | null;
  lastTestMessageAt?: string | null;
  updatedAt: string;
}

export interface FeishuUserBinding {
  linked: boolean;
  readyForAuthorization: boolean;
  appId: string;
  userId: string;
  openId?: string | null;
  unionId?: string | null;
  feishuUserId?: string | null;
  name?: string | null;
  enName?: string | null;
  avatarUrl?: string | null;
  email?: string | null;
  tenantKey?: string | null;
  boundAt?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
}

export interface FeishuUserBindingStartResult {
  authorizeUrl: string;
  state: string;
  expiresAt: string;
  callbackUrl: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
}

export interface OrgMembershipSummary {
  hasOrganization: boolean;
  organizationId?: string | null;
  organizationName?: string | null;
}

export interface OrgFeishuIntegrationAuditRecord {
  id: string;
  organizationId: string;
  actorUserId?: string | null;
  actorName?: string | null;
  appId: string;
  validationStatus: 'success' | 'failed';
  validationMessage: string;
  createdAt: string;
}

export interface OrgFeishuIntegration {
  organizationId?: string | null;
  organizationName?: string | null;
  appId: string;
  enabled: boolean;
  hasAppSecret: boolean;
  configuredBy?: string | null;
  configuredAt?: string | null;
  updatedAt: string;
  lastValidationStatus: 'idle' | 'success' | 'failed';
  lastValidationMessage?: string | null;
  recentAudits: OrgFeishuIntegrationAuditRecord[];
}

export interface OrgFeishuIntegrationPayload {
  appId?: string;
  appSecret?: string;
  clearAppSecret?: boolean;
}

export interface FeishuDeliveryProfile {
  userId: string;
  organizationId?: string | null;
  organizationName?: string | null;
  mobile: string;
  normalizedMobile?: string | null;
  deliveryStatus: 'missing_org' | 'integration_pending' | 'missing_mobile' | 'matched' | 'not_found' | 'failed';
  deliveryStatusLabel: string;
  readyForNotifications: boolean;
  receiveId?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
  blockedReason?: string | null;
}

export interface FeishuDeliveryProfilePayload {
  mobile?: string | null;
}

export interface FeishuMemberAuthorization {
  linked: boolean;
  readyForAuthorization: boolean;
  organizationId?: string | null;
  organizationName?: string | null;
  appId: string;
  userId: string;
  openId?: string | null;
  unionId?: string | null;
  feishuUserId?: string | null;
  name?: string | null;
  enName?: string | null;
  avatarUrl?: string | null;
  email?: string | null;
  tenantKey?: string | null;
  boundAt?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
  blockedReason?: string | null;
}

export interface FeishuMemberAuthorizationStartResult {
  authorizeUrl: string;
  state: string;
  expiresAt: string;
  callbackUrl: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
}

export interface TopicRadar {
  id: string;
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
  createdAt: string;
}

export interface TopicRadarPreferredSource {
  url: string;
  label: string;
}

export interface TopicCandidate {
  id: string;
  radarId: string;
  title: string;
  summary: string;
  source: string;
  sourceUrl?: string | null;
  publishedAt?: string | null;
  captureMethod: string;
  capturedBy?: string | null;
  status: TopicCandidateStatus;
  insightStatus: TopicCandidateInsightStatus;
  insightUpdatedAt?: string | null;
  createdAt: string;
}

export interface TopicCandidateInsight {
  candidateId: string;
  overview: string;
  keyPoints: string[];
  recommendationReasons: string[];
  practicalUses: string[];
  editorialNote: string;
  discussionPrompts: string[];
  createdAt: string;
  updatedAt: string;
}

export interface TopicCandidateChatMessage {
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export interface TopicCandidateChatPayload {
  question: string;
  history?: TopicCandidateChatMessage[];
}

export interface TopicCandidateChatResponse {
  candidateId: string;
  question: string;
  answer: string;
  generatedAt: string;
  message: TopicCandidateChatMessage;
}

export interface TopicCaptureRun {
  radarId: string;
  radarTitle: string;
  query: string;
  fetchedCount: number;
  createdCount: number;
  skippedCount: number;
  candidates: TopicCandidate[];
}

export interface TopicCaptureBatchResult {
  runs: TopicCaptureRun[];
  totalCreated: number;
  totalSkipped: number;
}

export interface TopicTaskSuggestion {
  title: string;
  desc: string;
  dueDate?: string | null;
  ddl: string;
  note: string;
  priority: Priority;
  tags: string[];
}

export interface TopicTaskPlanResult {
  candidateId: string;
  candidateTitle: string;
  candidateSummary: string;
  candidateSource: string;
  candidateSourceUrl?: string | null;
  overview: string;
  tasks: TopicTaskSuggestion[];
}

export interface TopicTaskPromotionDraft {
  title: string;
  desc: string;
  priority: Priority;
  listId: string;
  dueDate?: string | null;
  ddl: string;
  ownerId?: string | null;
  ownerName: string;
  collaboratorIds: string[];
  tagIds?: string[];
  tags: string[];
  note: string;
}

export interface TopicTaskPromotionResult {
  tasks: Task[];
  createdCount: number;
}

export interface AnalysisTemplate {
  id: string;
  title: string;
  description: string;
  templateKey: string;
}

export interface AnalysisRun {
  id: string;
  templateId: string;
  title: string;
  inputText: string;
  output: AiStructuredResponse;
  parentRunId?: string | null;
  coachPayload?: CoachPayload | null;
  createdAt: string;
  status: 'success' | 'failed';
}

export interface HandbookEntry {
  id: string;
  title: string;
  summary: string;
  tags: string[];
  sourceType: string;
  clientName?: string | null;
  clientId?: string | null;
  authorUserId?: string | null;
  authorUserName?: string | null;
  sourceObjectType?: string | null;
  sourceObjectId?: string | null;
  sourceTitle?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  abilityKeys: GrowthAbilityKey[];
  evidenceRefs: string[];
  contextSummary: string;
  reuseCount: number;
  lastReusedAt?: string | null;
  linkedContexts: GrowthContextLink[];
  createdAt: string;
}

export interface GrowthContextLink {
  objectType: string;
  objectId: string;
  label: string;
  subtitle: string;
  tab: string;
  statusLabel: string;
}

export interface HandbookEntryDetail extends HandbookEntry {
  relatedLedgerEntries: XpLedgerEntry[];
  originContexts: GrowthContextLink[];
  reuseHistory: HandbookReuseRecord[];
}

export interface HandbookReuseRecord {
  id: string;
  sourceType: string;
  sourceId: string;
  sourceLabel: string;
  note: string;
  contextSummary: string;
  gainedXp: number;
  createdAt: string;
  linkedContexts: GrowthContextLink[];
}

export interface XpLedgerEntry {
  id: string;
  userId: string;
  userName: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  evidenceId: string;
  xpType: GrowthEvidenceType;
  delta: number;
  baseXp: number;
  premiumRate: number;
  premiumXp: number;
  totalXp: number;
  reason: string;
  sourceType: string;
  sourceId: string;
  sourceTitle?: string | null;
  handbookEntryId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  reviewId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  businessCategory?: string | null;
  projectStage?: string | null;
  sourceRoute: string[];
  evidenceRefs: string[];
  contextSummary: string;
  strategicLink?: string | null;
  linkedContexts: GrowthContextLink[];
  contributionTags: GrowthContributionTag[];
  validationState: GrowthValidationState;
  orgContributionScore: number;
  weekLabel: string;
  createdAt: string;
  reversedAt?: string | null;
}

export interface GrowthAbilityScore {
  abilityKey: GrowthAbilityKey;
  label: string;
  currentScore: number;
  previousScore: number;
  totalXp: number;
  weeklyXp: number;
  stage: string;
  nextStage: string;
  evidence: string;
}

export interface GrowthRank {
  key: string;
  name: string;
  division?: string | null;
  fullLabel: string;
  progress: number;
  nextName?: string | null;
  xpToNext: number;
}

export interface LearningRecommendation {
  id: string;
  userId: string;
  userName: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  contentItemId: string;
  contentType: LearningContentType;
  title: string;
  summary: string;
  body: string;
  practiceTask: string;
  reason: string;
  linkedTaskId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  whyNow: string;
  linkedContexts: GrowthContextLink[];
  priority: 'high' | 'normal' | 'low';
  status: LearningRecommendationStatus;
  acceptedTaskId?: string | null;
  dismissedReason?: string | null;
  dedupeKey: string;
  createdAt: string;
  updatedAt: string;
}

export interface GrowthOverview {
  userId: string;
  userName: string;
  totalXp: number;
  weeklyXp: number;
  weeklyBaseXp: number;
  weeklyPremiumXp: number;
  level: number;
  stageLabel: string;
  xpToNext: number;
  rank: GrowthRank;
  abilities: GrowthAbilityScore[];
  recentEntries: XpLedgerEntry[];
  recommendations: LearningRecommendation[];
  sourceCoverage: GrowthSourceCoverage;
  projectGrowthHighlights: GrowthProjectHighlight[];
  eventLineGrowthHighlights: GrowthProjectHighlight[];
  strategicAlignmentHighlights: GrowthProjectHighlight[];
  pendingCaptures: GrowthPendingCapture[];
  currentFocusActions: GrowthFocusAction[];
  abilityGaps: GrowthAbilityGap[];
  updatedAt: string;
}

export interface GrowthSourceCoverage {
  taskSignals: number;
  meetingSignals: number;
  strategicSignals: number;
  reviewSignals: number;
  handbookSignals: number;
  clientCount: number;
  eventLineCount: number;
}

export interface GrowthProjectHighlight {
  id: string;
  label: string;
  type: string;
  weeklyXp: number;
  entryCount: number;
  summary: string;
  abilityKeys: GrowthAbilityKey[];
  contexts: GrowthContextLink[];
}

export interface GrowthPendingCapture {
  id: string;
  sourceType: string;
  sourceId: string;
  status: GrowthPendingCaptureState;
  title: string;
  summary: string;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  nextActionText: string;
  missingReasons: string[];
  abilityKeys: GrowthAbilityKey[];
  linkedContexts: GrowthContextLink[];
  stateReason: string;
  promotedHandbookEntryId?: string | null;
  updatedAt: string;
}

export interface GrowthFocusAction {
  id: string;
  title: string;
  summary: string;
  whyNow: string;
  linkedTaskId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  linkedContexts: GrowthContextLink[];
}

export interface GrowthAbilityGap {
  abilityKey: GrowthAbilityKey;
  label: string;
  currentScore: number;
  requiredScore: number;
  gap: number;
  reason: string;
  sourceLabel: string;
  sourceType: string;
  sourceId: string;
}

export interface GrowthTaskIntent {
  taskKind: string;
  goal: string;
  deliverable: string;
  riskTypes: string[];
  requiredAbilities: GrowthAbilityKey[];
  confidence: number;
  whyRelevant: string;
}

export interface GrowthUniversalSkillItem {
  id: string;
  cardType: '动作卡' | '检查卡' | '话术卡' | '模板卡';
  title: string;
  summary: string;
  whyRelevant: string;
  checklist: string[];
  talkTrack: string[];
  templateHint: string;
  sourceKind: 'rule' | 'project_context' | 'ai_supplement';
  expectedOutput: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthProjectContextPack {
  title: string;
  taskNotes: string[];
  attachments: string[];
  memoryHints: string[];
  linkedFacts: string[];
  clientSummary: string;
  recentMeetings: string[];
  eventLineSummary: string;
  strategicFocus: string[];
  keyWarnings: string[];
  contextGaps: string[];
}

export interface GrowthActionPlanItem {
  id: string;
  phaseGroup: 'before' | 'during' | 'after';
  title: string;
  purpose: string;
  expectedOutput: string;
  ifMissing: string;
  actionLabel: string;
  sourceKind: 'rule' | 'project_context' | 'ai_supplement';
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthMaterialRef {
  id: string;
  title: string;
  summary: string;
  sourceKind: 'task_material' | 'project_context' | 'client_workspace' | 'event_line' | 'strategic_focus' | 'rule' | 'ai_supplement';
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthWorkbenchStep {
  id: string;
  name: string;
  output: string;
  bottlenecks: string[];
}

export interface GrowthWorkbenchTask {
  id: string;
  title: string;
  project: string;
  clientName?: string | null;
  eventLineName?: string | null;
  deadline: string;
  urgency: string;
  urgencyColor: string;
  phase: string;
  risks: string[];
  nextAdvice: string;
  robotReady: boolean;
  robotReasons: string[];
  recommendationId?: string | null;
  linkedTaskId?: string | null;
  linkedContexts: GrowthContextLink[];
  xpReward: number;
  contextSummary: string;
  projectModuleName?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  sourceEvidence: string[];
  currentBlocker?: string | null;
  missingSignals: string[];
  hasBackground: boolean;
  hasDeadline: boolean;
  isCrossDepartment: boolean;
  needsReview: boolean;
  evidenceCount: number;
  pendingCollaborations: number;
  taskIntent: GrowthTaskIntent;
  universalSkills: GrowthUniversalSkillItem[];
  projectContextPack: GrowthProjectContextPack;
  actionPlan: GrowthActionPlanItem[];
  materialRefs: GrowthMaterialRef[];
}

export interface GrowthWorkbenchAction {
  id: string;
  title: string;
  output: string;
  scenario: string;
  actionLabel: string;
  supportTitle: string;
  detail: string;
  kind: 'schedule' | 'support' | 'process' | 'compose' | 'task';
  recommendationId?: string | null;
  linkedContext?: GrowthContextLink | null;
  seedTitle?: string | null;
  seedSummary?: string | null;
}

export interface GrowthWorkbenchMaterial {
  id: string;
  title: string;
  type: '流程说明' | '经验案例' | '模板工具';
  scenario: string;
  summary: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthLearningSummary {
  headline: string;
  whyItMatters: string;
  immediateMove: string;
  generator: 'rules' | 'ai';
  confidence: GrowthConfidence;
}

export interface GrowthGenericLesson {
  id: string;
  title: string;
  judgment: string;
  applicableScene: string;
  whyItWorks: string;
  reuseHint: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthProjectGuidance {
  id: string;
  title: string;
  judgment: string;
  whySpecial: string;
  guidanceType: 'project_specific' | 'stage_risk' | 'context_gap';
  linkedContexts: GrowthContextLink[];
  evidenceRefs: string[];
}

export interface GrowthReasoningInput {
  id: string;
  sourceType: 'task' | 'event_line' | 'client' | 'project_module' | 'project_flow' | 'focus_action' | 'pending_capture' | 'recommendation' | 'rule';
  label: string;
  detail: string;
}

export interface GrowthReasoningTrace {
  mode: 'rules_only' | 'ai_synthesized';
  usedInputs: GrowthReasoningInput[];
  evidenceRefs: string[];
  missingContext: string[];
  aiContribution: string[];
  modelLabel?: string | null;
  confidence: GrowthConfidence;
}

export interface GrowthRobotAssist {
  ready: boolean;
  canDelegate: string[];
  mustStayHuman: string[];
  why: string[];
}

export interface GrowthAfterActionCapture {
  title: string;
  summary: string;
  experienceType: string;
  recommendedWriteback: string;
}

export interface GrowthWorkbenchSupportCopy {
  title: string;
  intro: string;
  bullets: string[];
}

export interface GrowthWorkbenchSnapshot {
  tasks: GrowthWorkbenchTask[];
  activeTaskId?: string | null;
  learningSummary: GrowthLearningSummary;
  genericLessons: GrowthGenericLesson[];
  projectGuidance: GrowthProjectGuidance[];
  reasoningTrace: GrowthReasoningTrace;
  robotAssist: GrowthRobotAssist;
  afterActionCapture: GrowthAfterActionCapture;
  processSteps: GrowthWorkbenchStep[];
  activeProcessId?: string | null;
  actionsBefore: GrowthWorkbenchAction[];
  actionsDuring: GrowthWorkbenchAction[];
  actionsAfter: GrowthWorkbenchAction[];
  supportMaterials: GrowthWorkbenchMaterial[];
  checklistItems: string[];
  supportCopy: GrowthWorkbenchSupportCopy;
  robotPlan: string[];
  sourceMode: 'task' | 'growth_seed' | 'empty';
  scopeMode?: 'global' | 'strategic';
  scopeClientId?: string | null;
  scopeClientName?: string | null;
  updatedAt: string;
}

export interface GrowthLedgerResponse {
  entries: XpLedgerEntry[];
}

export interface GrowthRecommendationDismissPayload {
  reason?: string;
}

export interface GrowthRecommendationActionResponse {
  recommendation: LearningRecommendation;
  task?: Task | null;
}

export interface BadgeActionLink {
  label: string;
  tab: string;
}

export interface BadgeEvidence {
  id: string;
  title: string;
  sourceType: string;
  sourceId: string;
  subtitle: string;
  occurredAt: string;
}

export interface BadgeProgress {
  id: string;
  code: string;
  name: string;
  categoryId: string;
  categoryLabel: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  roles: string[];
  xp: number;
  iconMotif: string;
  description: string;
  whyItMatters: string;
  systemHowText: string;
  state: BadgeState;
  progressValue: number;
  progressTarget: number;
  progressPercent: number;
  progressText: string;
  nextActionText: string;
  actionLinks: BadgeActionLink[];
  evidence: BadgeEvidence[];
  linkedContexts: GrowthContextLink[];
  missingSignals: string[];
  unlockedAt?: string | null;
  masteryLevel: number;
  historical: boolean;
}

export interface BadgeCategory {
  id: string;
  label: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  litCount: number;
  totalCount: number;
  badges: BadgeProgress[];
}

export interface BadgeBoardOverview {
  totalBadges: number;
  litBadges: number;
  readyBadges: number;
  inProgressBadges: number;
  monthlyNewBadges: number;
  totalXp: number;
  upcomingBadgeIds: string[];
}

export interface BadgeBoard {
  overview: BadgeBoardOverview;
  categories: BadgeCategory[];
  updatedAt: string;
}

export interface GrowthValidationPayload {
  note?: string;
  sourceType?: string;
  sourceId?: string | null;
  sourceLabel?: string;
  contextSummary?: string;
  linkedContexts?: GrowthContextLink[];
}

export interface GrowthPendingCaptureActionPayload {
  status: GrowthPendingCaptureState;
  reason?: string;
  handbookEntryId?: string | null;
}

export interface GrowthPendingCaptureActionResponse {
  capture: GrowthPendingCapture;
}

export interface GrowthValidationActionResponse {
  entryId: string;
  eventType: 'handbook_reused';
  gainedXp: number;
  createdEntries: number;
  validationState: GrowthValidationState;
  duplicate: boolean;
  sourceId: string;
  createdAt: string;
}

export interface ClientAnalysisEvidenceSummary {
  summaryText: string;
  masterHitCount: number;
  surrogateHitCount: number;
  rawChunkHitCount: number;
  drillthroughUsed: boolean;
  coveredCategories: string[];
  missingCategories: string[];
  evidenceList: KnowledgeSearchHit[];
}

export interface ClientAnalysisRun {
  id: string;
  clientId: string;
  threadId: string;
  userMessageId: string;
  assistantMessageId: string;
  question: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
  phase: 'queued' | 'retrieving' | 'evidence_ready' | 'generating_long_answer' | 'generating_summary' | 'completed' | 'failed' | 'canceled';
  progress: number;
  progressFloor: number;
  progressCeiling: number;
  stageLabel?: string | null;
  elapsedMs: number;
  evidenceSummary: ClientAnalysisEvidenceSummary;
  longAnswerStatus: 'pending' | 'ready' | 'fallback' | 'failed';
  summaryStatus: 'pending' | 'ready' | 'fallback' | 'failed';
  longAnswer?: string | null;
  structuredSummary?: AiStructuredResponse | null;
  answerMode?: 'grounded_answer' | 'grounded_fallback' | 'low_confidence_answer' | 'general_answer' | 'system_failure' | null;
  llmInvoked: boolean;
  providerUsed?: string | null;
  failureReason?: string | null;
  timing: Record<string, number>;
  assistantMessage?: ChatMessage | null;
  createdAt: string;
  updatedAt: string;
}

export interface AnalysisJobCreatePayload {
  jobType: AnalysisJobType;
  clientId: string;
  scopeType?: AnalysisScopeType;
  scopeId: string;
  priority?: Priority;
  triggerType?: string;
  intentProfile?: AnalysisIntentProfile;
  question?: string;
  sourceScope?: Record<string, string[]>;
  featureFlags?: Record<string, boolean>;
}

export interface AnalysisJob {
  id: string;
  jobType: AnalysisJobType;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  status: AnalysisJobStatus;
  priority: Priority;
  triggerType: string;
  intentProfile: AnalysisIntentProfile;
  question: string;
  sourceSnapshot: string;
  sourceSnapshotHash: string;
  dedupeKey: string;
  featureFlags: Record<string, boolean>;
  progress: number;
  stageLabel?: string | null;
  runLogId?: string | null;
  error?: string | null;
  lockedBy?: string | null;
  lockedAt?: string | null;
  lockExpiresAt?: string | null;
  attemptCount: number;
  lastError?: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
}

export interface AnalysisJobStageRun {
  id: string;
  jobId: string;
  stageName: string;
  status: AnalysisStageStatus;
  provider?: string | null;
  modelName?: string | null;
  lane: AnalysisLane;
  cacheKey?: string | null;
  cacheHit: boolean;
  degraded: boolean;
  evidenceCount: number;
  topicCount: number;
  conflictCount: number;
  contextTimeRange?: string | null;
  metrics: Record<string, number | string>;
  detail?: string | null;
  correlationId?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RuntimeRunLog {
  id: string;
  clientId: string;
  jobId?: string | null;
  analysisJobId?: string | null;
  stageRunId?: string | null;
  contextPackId?: string | null;
  judgmentVersionId?: string | null;
  correlationId?: string | null;
  provider?: string | null;
  model?: string | null;
  lane: AnalysisLane;
  cacheHit: boolean;
  degraded: boolean;
  documentCount: number;
  evidenceCount: number;
  conflictCount: number;
  contextTimeRange?: string | null;
  promptVersion?: string | null;
  schemaVersion?: string | null;
  summary: string;
  detail: Record<string, unknown>;
  createdAt: string;
}

export interface ThemeCluster {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  themeKey: string;
  title: string;
  supportIds: string[];
  opposeIds: string[];
  gapSummary: string;
  latestChangeSummary: string;
  evidenceCount: number;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface ConflictGroup {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  conflictType: string;
  title: string;
  summary: string;
  evidenceIds: string[];
  unresolvedQuestionIds: string[];
  resolutionStatus: AnalysisReviewState;
  severity: 'low' | 'medium' | 'high';
  createdAt: string;
  updatedAt: string;
}

export interface OpenQuestion {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  themeKey: string;
  question: string;
  reason: string;
  blockerLevel: 'low' | 'medium' | 'high';
  status: AnalysisReviewState;
  createdAt: string;
  updatedAt: string;
}

export interface ContextPack {
  id: string;
  clientId: string;
  jobId?: string | null;
  targetType: AnalysisScopeType;
  targetId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  promptVersion: string;
  sourceCount: number;
  evidenceCount: number;
  payload: Record<string, unknown>;
  staleAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DnaDelta {
  id: string;
  clientId: string;
  dimension: string;
  previousVersion?: string | null;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  proposedChange: string;
  summary: string;
  evidenceIds: string[];
  confidence: GrowthConfidence;
  status: AnalysisReviewState;
  contextPackId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DnaDeltaCreatePayload {
  clientId: string;
  dimension: string;
  proposedChange: string;
  summary?: string;
  evidenceIds?: string[];
  confidence?: GrowthConfidence;
  contextPackId?: string | null;
}

export interface JudgmentVersion {
  id: string;
  clientId: string;
  targetType: AnalysisScopeType;
  targetId: string;
  topic: string;
  version: number;
  status: AnalysisReviewState;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  summary: string;
  evidenceIds: string[];
  contextPackId?: string | null;
  riskLevel: 'low' | 'medium' | 'high';
  confidence: GrowthConfidence;
  createdAt: string;
  updatedAt: string;
}

export interface JudgmentConfirmPayload {
  judgmentId: string;
  action: ApprovalDecision;
  note?: string;
}

export interface ApprovalDecisionPayload {
  targetType: ApprovalTargetType;
  targetId: string;
  decision: ApprovalDecision;
  comment?: string;
  policyType?: string;
  metadata?: Record<string, unknown>;
}

export interface ApprovalRecord {
  id: string;
  approvalTargetType: ApprovalTargetType;
  approvalTargetId: string;
  clientId: string;
  policyType: string;
  decision: ApprovalDecision;
  comment: string;
  decidedBy: string;
  decidedAt: string;
  metadata: Record<string, unknown>;
}

export interface ApprovalState {
  targetType: ApprovalTargetType;
  targetId: string;
  currentDecision?: ApprovalDecision | null;
  currentStatus?: AnalysisReviewState | null;
  lastApproval?: ApprovalRecord | null;
}

export interface ResolutionScope {
  scopeType: AnalysisScopeType;
  scopeId: string;
}

export interface ResolutionCandidate {
  objectId?: string | null;
  topic?: string | null;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType?: AnalysisOriginType | null;
  authorityLevel?: AnalysisAuthorityLevel | null;
  qualityTier?: AnalysisQualityTier | null;
  staleReason?: AnalysisStaleReason | null;
  status?: AnalysisReviewState | null;
  rejectedReason?: AnalysisRejectedReason | null;
}

export interface ResolutionTrace {
  selectedCandidate?: ResolutionCandidate | null;
  consideredCandidates: ResolutionCandidate[];
  requestedScope: ResolutionScope;
  resolvedScope?: ResolutionScope | null;
  writebackScope: ResolutionScope;
  fallbackUsed: boolean;
  fallbackReason?: string | null;
}

export interface JudgmentBundle {
  baselineJudgment?: JudgmentVersion | null;
  overlayDeltas: JudgmentVersion[];
  resolutionTrace: ResolutionTrace;
}

export interface AnalysisMigrationMetrics {
  windowDays: number;
  newObjectHitRate: number;
  fallbackRate: number;
  approvalBacklog: number;
  approvalLagHoursMedian: number;
  candidateReviewWarningCount: number;
  candidateReviewOverdueCount: number;
  newCandidateUnreviewed24h: number;
  candidateToApprovedConversionRate: number;
  staleApprovedJudgmentCount: number;
  resolverMismatchRate: number;
  pageBreakdown: Record<string, AnalysisMigrationMetricBucket>;
}

export interface AnalysisMigrationMetricBucket {
  newObjectHitRate: number;
  fallbackRate: number;
  resolverMismatchRate: number;
  totalRuns: number;
}

export interface AnalysisWorkerCounterSnapshot {
  claimCounts: Record<string, number>;
  lockContention: Record<string, number>;
  backfillThrottle: Record<string, number>;
}

export interface MainChainCanaryObservation {
  recordedAt: string;
  timeRange: string;
  clientCount: number;
  enqueuedJobs: number;
  completedJobs: number;
  failedJobs: number;
  newObjectHitRateBefore: number;
  newObjectHitRateAfter: number;
  fallbackRateBefore: number;
  fallbackRateAfter: number;
  resolverMismatchRateBefore: number;
  resolverMismatchRateAfter: number;
  approvalBacklog: number;
  approvalLagHoursMedian: number;
  claimCounts: Record<string, number>;
  lockContention: Record<string, number>;
  backfillThrottle: Record<string, number>;
  impactedRealtimeTasks: boolean;
  latestJudgmentsShadowOff: boolean;
  verdict: 'pass' | 'watch' | 'fail';
  conclusion: string;
}

export interface MainChainCanaryObservationPayload {
  timeRange?: string | null;
  clientCount?: number | null;
  enqueuedJobs?: number | null;
  completedJobs?: number | null;
  failedJobs?: number | null;
  newObjectHitRateBefore?: number | null;
  newObjectHitRateAfter?: number | null;
  fallbackRateBefore?: number | null;
  fallbackRateAfter?: number | null;
  resolverMismatchRateBefore?: number | null;
  resolverMismatchRateAfter?: number | null;
  approvalBacklog?: number | null;
  approvalLagHoursMedian?: number | null;
  claimCounts?: Record<string, number> | null;
  lockContention?: Record<string, number> | null;
  backfillThrottle?: Record<string, number> | null;
  impactedRealtimeTasks?: boolean | null;
  latestJudgmentsShadowOff?: boolean | null;
  verdict?: 'pass' | 'watch' | 'fail' | null;
  conclusion?: string | null;
}

export interface MainChainStabilitySettings {
  latestJudgmentsShadowOff: boolean;
  backfillPaused: boolean;
  workerCounters: AnalysisWorkerCounterSnapshot;
  lastCanaryObservation?: MainChainCanaryObservation | null;
  updatedAt: string;
}

export interface MainChainStabilitySettingsPayload {
  latestJudgmentsShadowOff?: boolean | null;
  backfillPaused?: boolean | null;
  lastCanaryObservation?: MainChainCanaryObservationPayload | null;
}

export interface AnalysisCenterSummary {
  clientId: string;
  evidenceCardCount: number;
  themeClusterCount: number;
  conflictGroupCount: number;
  openQuestionCount: number;
  draftJudgmentCount: number;
  approvedJudgmentCount: number;
  analysisJobCount: number;
  latestJobStatus?: AnalysisJobStatus | null;
  latestJobLabel?: string | null;
  latestContextPackUpdatedAt?: string | null;
  latestRunLogId?: string | null;
  latestRunSummary?: string | null;
}

export interface ClientWorkspace {
  client: ClientSummary;
  folders: ClientFolder[];
  documents: DocumentRecord[];
  documentCards: DocumentCard[];
  imports: ImportRecord[];
  knowledgeStatus?: KnowledgeStatus | null;
  knowledgeJobs: KnowledgeJob[];
  recentReclassEvents: FileReclassEvent[];
  surrogateCount: number;
  memoryDocCount: number;
  threads: ChatThread[];
  recentMessages: ChatMessage[];
  analysisRuns: ClientAnalysisRun[];
  meetings: MeetingSummary[];
  goals: GoalRecord[];
  dnaModules: ClientDnaModule[];
  projectModules: ProjectModule[];
  projectFlows: ProjectFlow[];
  dnaTerms: DnaTerm[];
  relatedTasks: Task[];
  notebookSummary?: OrganizationNotebookSnapshot | null;
  memoryStatus?: MemoryStatus | null;
  analysisCenter?: AnalysisCenterSummary | null;
  latestContextPack?: ContextPack | null;
  judgmentBundle?: JudgmentBundle | null;
  latestResolutionTrace?: ResolutionTrace | null;
  latestJudgments: JudgmentVersion[];
  latestTopics: ThemeCluster[];
  latestConflicts: ConflictGroup[];
  latestOpenQuestions: OpenQuestion[];
  latestRunLogs: RuntimeRunLog[];
  stateProjection?: WorkspaceStateProjection | null;
}

export interface AnalysisBackfillMainChainJob {
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  jobType: AnalysisJobType;
  triggerType: string;
  intentProfile: AnalysisIntentProfile;
}

export interface AnalysisBackfillMainChainPayload {
  clientIds?: string[];
  dryRun?: boolean;
  batchSize?: number;
  maxJobs?: number;
  pauseRequested?: boolean;
}

export interface AnalysisBackfillMainChainResult {
  dryRun: boolean;
  pauseRequested: boolean;
  paused: boolean;
  scannedClients: number;
  queuedJobs: number;
  skippedJobs: number;
  candidates: AnalysisBackfillMainChainJob[];
}

export interface FileReclassEvent {
  id: string;
  knowledgeDocumentId: string;
  fromPath: string;
  toPath: string;
  fromCategory?: string | null;
  toCategory: string;
  reason: string;
  confidence: number;
  createdAt: string;
}

export interface KnowledgeJob {
  id: string;
  clientId: string;
  jobType: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  totalItems: number;
  processedItems: number;
  lastError?: string | null;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  updatedAt: string;
}

export interface KnowledgeSearchHit {
  title: string;
  excerpt: string;
  score?: number | null;
  stage: 'master_index' | 'surrogate' | 'raw_chunk';
  path?: string | null;
  sectionLabel?: string | null;
  matchedTerms: string[];
}

export interface KnowledgeSearchResult {
  searchId: string;
  clientId: string;
  query: string;
  coverage: number;
  matchedTerms: string[];
  masterHitCount: number;
  surrogateHitCount: number;
  rawChunkHitCount: number;
  drillthroughUsed: boolean;
  strategicMode?: boolean;
  categoryCoverage?: string[];
  preferredCategories?: string[];
  phase?: 'retrieving' | 'grounding' | 'generating' | 'completed' | 'failed';
  progress?: number;
  progressFloor?: number;
  progressCeiling?: number;
  stageLabel?: string | null;
  lastUpdatedAt?: string | null;
  failureReason?: string | null;
  hits: KnowledgeSearchHit[];
  previewSummary?: string | null;
}

export interface KnowledgeMemoryRecord {
  id: string;
  clientId: string;
  sourceType: string;
  title: string;
  folderCategory: string;
  surrogateMdPath: string;
  createdAt: string;
  updatedAt: string;
}

export interface SettingsPayload {
  currentOperatorId?: string;
  aiProvider?: AiProvider;
  aiModel?: string;
  apiKey?: string;
  clearApiKey?: boolean;
}

export interface LegacyScanReport {
  path: string;
  found: string[];
  entries: Array<{
    path: string;
    kind: string;
    importable: boolean;
  }>;
  message: string;
}

export interface DemoDataReport {
  loaded: boolean;
  clients: number;
  documents: number;
  tasks: number;
  topics: number;
  handbookEntries: number;
}

export interface ClientMutationPayload {
  name: string;
  alias: string;
  domain: string;
  type: string;
  intro: string;
  stage: string;
  color?: string;
}

export interface TaskMutationPayload {
  title: string;
  desc: string;
  priority: Priority;
  listId: string;
  startDate?: string | null;
  dueDate?: string | null;
  durationMinutes?: number;
  scopeMode?: TaskScopeMode;
  clientId?: string | null;
  eventLineId?: string | null;
  projectModuleId?: string | null;
  projectFlowId?: string | null;
  ddl: string;
  ownerId?: string | null;
  ownerName: string;
  collaboratorIds: string[];
  tagIds: string[];
  tags?: string[];
  sourceType?: string;
  sourceId?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  evidenceCount?: number | null;
}

export interface AuthRegisterPayload {
  email: string;
  fullName: string;
  password: string;
  departmentId?: string | null;
  jobTitle?: string | null;
  managerName?: string | null;
  currentFocus?: string | null;
  isDepartmentLead?: boolean;
}

export interface AuthLoginPayload {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RememberedCloudAuthAccount {
  email: string;
  fullName: string;
  password: string;
  updatedAt: string;
}

export interface LocalInputMemoryCloudAuth {
  rememberInputs: boolean;
  lastEmail?: string | null;
  accounts: RememberedCloudAuthAccount[];
}

export interface LocalInputMemoryAiSettings {
  rememberApiKey: boolean;
  apiKey: string;
}

export interface LocalInputMemoryFeishuIntegration {
  rememberInputs: boolean;
  appId: string;
  callbackMode: string;
  customCallbackUrl: string;
  appSecret: string;
}

export interface LocalInputMemory {
  cloudAuth: LocalInputMemoryCloudAuth;
  aiSettings: LocalInputMemoryAiSettings;
  feishuIntegration: LocalInputMemoryFeishuIntegration;
}

export interface SaveCloudAuthInputMemoryPayload {
  rememberInputs: boolean;
  email: string;
  fullName?: string | null;
  password?: string | null;
}

export interface SaveAiInputMemoryPayload {
  rememberApiKey: boolean;
  apiKey?: string | null;
}

export interface SaveFeishuInputMemoryPayload {
  rememberInputs: boolean;
  appId?: string | null;
  callbackMode?: string | null;
  customCallbackUrl?: string | null;
  appSecret?: string | null;
}

export interface EmployeeRolePayload {
  role: EmployeeRole;
}

export interface EmployeeDepartmentPayload {
  departmentId?: string | null;
}

export interface EmployeeRejectPayload {
  reason: string;
}

export interface ChangePasswordPayload {
  currentPassword: string;
  newPassword: string;
}

export interface UpdateProfilePayload {
  fullName?: string;
  email?: string;
}

export interface AdminResetPasswordPayload {
  newPassword: string;
}

export interface TaskTagSuggestionPayload {
  title: string;
  desc: string;
  collaboratorNames: string[];
  dueDate?: string | null;
  module: string;
}

export interface TaskTagMutationPayload {
  name: string;
  color?: string;
  scope: 'org' | 'self';
  archived?: boolean;
}

export interface TaskListMutationPayload {
  name: string;
  color: string;
  isDefault?: boolean;
  scope?: 'org' | 'personal';
  archived?: boolean;
  sortOrder?: number;
}

export interface TaskSettingsPayload {
  defaultListId?: string | null;
  defaultPriority?: Priority;
  defaultDueDatePreset?: TaskDueDatePreset;
  defaultViewMode?: TaskViewPreference;
  listSortMode?: TaskListSortMode;
  showCompletedTasks?: boolean;
  defaultReviewScope?: TaskReviewScope;
  autoAssignSelf?: boolean;
}

export interface ReviewGovernanceSettingsPayload {
  departments: ReviewDepartmentConfig[];
}

export interface OrganizationDnaUploadPayload {
  filePath?: string;
  markdownContent?: string;
  fileName?: string;
}

export interface ProjectModulePayload {
  name: string;
  alias?: string | null;
  goal?: string | null;
  description?: string | null;
  ownerName?: string | null;
  deliverables?: string[];
  keywords?: string[];
  templateTasksJson?: string | null;
}

export interface ProjectFlowPayload {
  moduleId: string;
  name: string;
  description?: string | null;
  scenario?: string | null;
  triggerCondition?: string | null;
  steps?: string[];
  inputs?: string[];
  outputs?: string[];
  collaborators?: string[];
  riskPoints?: string[];
}

export interface ClientWorkspaceSettingsPayload {
  useOrgDnaInChat?: boolean;
  useOrgDnaInKnowledgeQa?: boolean;
  meetingPublishDefaultListId?: string | null;
  meetingPublishDefaultPriority?: Priority;
  defaultGoalQuarter?: string;
  defaultMeetingTitlePrefix?: string;
  clientDnaModeLabel?: string;
}

export interface TopicsSettingsPayload {
  chineseOnly?: boolean;
  requireInsightBeforeActions?: boolean;
  defaultTaskOwnerMode?: TopicTaskOwnerMode;
  defaultTimeRange?: string;
  defaultSourceStrategy?: string;
  useOrgDnaForInsight?: boolean;
  useOrgDnaForTaskPlan?: boolean;
}

export interface AnalysisWorkbenchSettingsPayload {
  enabledTemplateIds?: string[];
  defaultTemplateId?: string | null;
  defaultTitlePrefix?: string;
  useOrgDna?: boolean;
  allowEmployeeTemplateEditing?: boolean;
  diagnosisProfiles?: DiagnosisProfileRecord[];
  organizationRiskDna?: OrganizationRiskDnaDocument | null;
  fundraisingKnowledgeLibrary?: FundraisingKnowledgeDocument[];
  deepDnaLibrary?: DeepDnaRecord[];
  coachCaseLibrary?: CoachCaseRecord[];
  coachReminderRules?: CoachReminderRule[];
  orgWritingNorms?: OrgWritingNorm[];
}

export interface HandbookSettingsPayload {
  defaultTags?: string[];
  defaultCategory?: string;
  allowTaskSource?: boolean;
  allowAnalysisSource?: boolean;
  visibilityBoundary?: string;
}

export interface SystemAdminSettingsPayload {
  allowBusinessSettingsForEmployees?: boolean;
  allowOrgDnaForEmployees?: boolean;
  protectEmployeeAdmin?: boolean;
  protectAiAndCloud?: boolean;
  protectCloudSecurity?: boolean;
  brandLogoDataUrl?: string | null;
}

export interface FeishuBotSettingsPayload {
  appId?: string;
  receiveIdType?: FeishuReceiveIdType;
  receiverId?: string;
  botName?: string;
  userBindingCallbackUrl?: string;
  appSecret?: string;
  clearAppSecret?: boolean;
  sendTestMessage?: boolean;
  testMessage?: string;
}

export interface WeeklyReviewPayload {
  weekLabel: string;
  taskEntries: Array<{
    taskId: string;
    contentDomain: 'work' | 'personal';
    note: string;
    structuredNote?: WeeklyReviewTaskStructuredNote;
  }>;
  workProgress?: string;
  workBlocker?: string;
  blockerType?: string;
  workDirection?: string;
  nextWeekFocus?: string;
  supportNeeded?: string;
  relatedPlanIds?: string[];
  workFreeNote?: string;
  personalGrowthNote?: string;
  personalPrivateNote?: string;
}

export interface TopicRadarPayload {
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
}

export interface MeetingPipelineResult {
  meeting: MeetingDetail;
  message: string;
}

export interface TopicCandidatePayload {
  radarId: string;
  title: string;
  summary: string;
  source: string;
}

export interface HandbookEntryPayload {
  title: string;
  summary: string;
  tags: string[];
  sourceType: string;
  clientId?: string | null;
  sourceObjectType?: string | null;
  sourceObjectId?: string | null;
  sourceTitle?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  abilityKeys?: GrowthAbilityKey[];
  evidenceRefs?: string[];
  contextSummary?: string;
}

export interface AnalysisRunPayload {
  templateId: string;
  title: string;
  inputText: string;
  parentRunId?: string | null;
}

export type DiagnosisScene = 'fundraising' | 'pr' | 'project';
export type DiagnosisAudienceType = 'donor' | 'media' | 'public' | 'key_person' | 'beneficiary' | 'partner';
export type DiagnosisEngineMode = 'fast' | 'standard' | 'deep';

export interface DiagnosisContextReference {
  title: string;
  summary: string;
}

export interface ExternalDiagnosisRequest {
  scene: DiagnosisScene;
  audienceType: DiagnosisAudienceType;
  title: string;
  content: string;
  workspaceLabel?: string;
  modeLabel?: string;
  focusPoints?: string[];
  organizationContext?: {
    name?: string;
    mission?: string;
    projectType?: string;
    sensitivePoints?: string[];
  };
  dnaSummary?: {
    corePreferences?: string[];
    riskTriggers?: string[];
    tonePreference?: string;
  };
  knowledgeRefs?: DiagnosisContextReference[];
  caseRefs?: DiagnosisContextReference[];
  analysisOptions?: {
    engineMode: DiagnosisEngineMode;
    needEmotion?: boolean;
    needRiskPoints?: boolean;
    needMisunderstanding?: boolean;
    needSimulation?: boolean;
  };
}

export interface DiagnosisEngineHealth {
  engineKey: 'bettafish' | 'mirofish';
  enabled: boolean;
  reachable: boolean;
  status: 'healthy' | 'disabled' | 'not_configured' | 'not_installed' | 'unreachable' | 'error';
  detail: string;
  baseUrl: string;
  latencyMs?: number | null;
}

export interface BettaFishSignal {
  engineKey: 'bettafish';
  emotion: string;
  credibility: string;
  riskPoints: string[];
  misunderstandingPoints: string[];
  generatedAt: string;
  mode: DiagnosisEngineMode;
}

export interface DesktopAppInfo {
  appVersion: string;
  isPackaged: boolean;
  platform: string;
  arch: string;
  appBundlePath: string;
  executablePath: string;
  releasePlanPath: string;
  releaseArtifactsPath: string;
  updateChannel: 'stable' | 'beta';
  updaterPhase: 'planning' | 'preparing_release' | 'ready_for_feed' | 'ready_for_in_app_update';
  recommendedInstallPath: string;
  installStatus: 'ok' | 'warning';
  installWarning: string | null;
  detectedAppPaths: string[];
  legacyAppPaths: string[];
}

export type CollabChangeGroupKey =
  | 'shared_settings'
  | 'renderer'
  | 'desktop_shell'
  | 'local_backend'
  | 'cloud_backend'
  | 'scripts_docs'
  | 'other';

export type CollabFileChangeType = 'modified' | 'added' | 'deleted' | 'renamed' | 'untracked';

export type CollabConflictRiskKind = 'overlap' | 'unmerged' | 'binary' | 'rename' | 'delete_replace';

export interface CollabConflictRisk {
  kind: CollabConflictRiskKind;
  message: string;
}

export interface CollabFileChange {
  path: string;
  previousPath?: string | null;
  type: CollabFileChangeType;
  groupKey: CollabChangeGroupKey;
  groupLabel: string;
  summary: string;
  risk?: CollabConflictRisk | null;
}

export interface CollabChangeGroup {
  key: CollabChangeGroupKey;
  label: string;
  fileCount: number;
}

export type CollabEffectVisibility = 'visible' | 'mixed' | 'background';

export interface CollabEffectPreview {
  id: string;
  title: string;
  summary: string;
  visibility: CollabEffectVisibility;
  scopeLabel: string;
  details: string[];
  relatedPaths: string[];
  beforeLabel?: string | null;
  afterLabel?: string | null;
  beforeImageDataUrl?: string | null;
  afterImageDataUrl?: string | null;
}

export interface CollabRepoStatus {
  repoPath: string | null;
  repoName: string | null;
  suggestedRepoPath?: string | null;
  workingRepoPath?: string | null;
  workingBranch?: string | null;
  workingChangeCount?: number;
  isConfigured: boolean;
  isValid: boolean;
  branch: string | null;
  isMainBranch: boolean;
  hasLocalChanges: boolean;
  hasUnmergedPaths: boolean;
  aheadCount: number;
  behindCount: number;
  localChangeCount: number;
  remoteChangeCount: number;
  statusText: string;
}

export interface PushPreview {
  status: CollabRepoStatus;
  suggestedMessage: string;
  effects: CollabEffectPreview[];
  groups: CollabChangeGroup[];
  files: CollabFileChange[];
  notice?: string | null;
  executionBlockReason?: string | null;
}

export interface PullPreview {
  status: CollabRepoStatus;
  suggestedMessage: string;
  commitSummaries: string[];
  effects: CollabEffectPreview[];
  groups: CollabChangeGroup[];
  files: CollabFileChange[];
  notice?: string | null;
  executionBlockReason?: string | null;
}

export interface CommitAndPushToMainPayload {
  repoPath: string;
  selectedPaths: string[];
  confirmedRiskPaths: string[];
  message: string;
}

export interface PullSelectedFromMainPayload {
  repoPath: string;
  selectedPaths: string[];
  confirmedRiskPaths: string[];
  message: string;
}

export interface CollabActionResult {
  status: CollabRepoStatus;
  changedPaths: string[];
  createdCommit: boolean;
  commitMessage?: string | null;
}

declare global {
  interface Window {
    __YIYU_TEST_DIALOGS__?: {
      selectFiles?: () => Promise<string[]>;
      selectFolder?: () => Promise<string | null>;
      selectCollabRepo?: () => Promise<string | null>;
      openPath?: (targetPath: string) => Promise<boolean>;
      revealInFinder?: (targetPath: string) => Promise<boolean>;
      saveFileAs?: (sourcePath: string, suggestedName?: string) => Promise<string | null>;
    };
    yiyuWorkbench: {
      backendBaseUrl: string;
      getDesktopAppInfo(): Promise<DesktopAppInfo>;
      selectFiles(): Promise<string[]>;
      selectFolder(): Promise<string | null>;
      selectCollabRepo(): Promise<string | null>;
      getCollabRepoStatus(repoPath?: string | null): Promise<CollabRepoStatus>;
      previewPushToMain(repoPath: string): Promise<PushPreview>;
      commitAndPushToMain(payload: CommitAndPushToMainPayload): Promise<CollabActionResult>;
      previewPullFromMain(repoPath: string): Promise<PullPreview>;
      pullSelectedFromMain(payload: PullSelectedFromMainPayload): Promise<CollabActionResult>;
      rebuildAndInstallFromRepo(repoPath: string): Promise<boolean>;
      getDroppedFilePath(file: File): string | null;
      readTextFile(targetPath: string): Promise<string>;
      openPath(targetPath: string): Promise<boolean>;
      openExternalUrl(targetUrl: string): Promise<boolean>;
      revealInFinder(targetPath: string): Promise<boolean>;
      saveFileAs(sourcePath: string, suggestedName?: string): Promise<string | null>;
    };
  }
}
```
