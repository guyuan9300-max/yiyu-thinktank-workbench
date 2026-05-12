import type {
  AnalysisJob,
  AnalysisBackfillMainChainPayload,
  AnalysisBackfillMainChainResult,
  AnalysisJobCreatePayload,
  AnalysisJobStageRun,
  AnalysisRunPayload,
  AgentWeeklyPlan,
  AgentWeeklyPlanPayload,
  AgentWorklogResponse,
  AnalysisRun,
  AnalysisWorkbenchSettings,
  AnalysisWorkbenchSettingsPayload,
  AnalysisTemplate,
  AppSettings,
  AdminResetPasswordPayload,
  LastCloudAiSyncStatus,
  AuthLoginPayload,
  AuthRegisterPayload,
  ChangePasswordPayload,
  ConsultationKnowledgeProcessSummary,
  ConsultationKnowledgeRequestRecord,
  ConsultationKnowledgeRequestStatus,
  BadgeBoard,
  AuthState,
  ChatMessage,
  ChatStartResponse,
  ChatThreadDetailResponse,
  ClientDnaModule,
  ClientDnaModulesResponse,
  ClientAnalysisRun,
  ClientFolder,
  ClientFolderRecommendation,
  ClientFolderRecommendationPlan,
  DocumentAutoRepairApplyPayload,
  DocumentAutoRepairApplyResult,
  DocumentAutoRepairPreview,
  DocumentAutoRepairPreviewPayload,
  DocumentReadingPreview,
  ClientTemplateFillResponse,
  ClientTemplateFillRun,
  ClientMutationPayload,
  ClientStrategicProfile,
  ClientSummary,
  ClientWorkspace,
  CooperationRelationship,
  WorkspaceImportBackfillResponse,
  AnalysisMigrationMetrics,
  MainChainStabilitySettings,
  MainChainStabilitySettingsPayload,
  ApprovalDecisionPayload,
  ApprovalRecord,
  ClientWorkspaceSettings,
  ClientWorkspaceSettingsPayload,
  DepartmentOption,
  OrgInviteResolveResult,
  DeepDnaDraft,
  DeepDnaRecord,
  DnaDelta,
  DnaDeltaCreatePayload,
  DnaTerm,
  DocumentRecord,
  DemoDataReport,
  EmployeeRecord,
  EmployeeRejectPayload,
  EmployeeDepartmentPayload,
  FeishuBotSettings,
  FeishuMeetingLaunchResult,
  FeishuBotSettingsPayload,
  FeishuDeliveryProfile,
  FeishuDeliveryProfilePayload,
  FeishuMemberAuthorization,
  FeishuMemberAuthorizationStartResult,
  FeishuUserBinding,
  FeishuUserBindingStartResult,
  EmployeeRolePayload,
  EventLine,
  EventLineClarificationDraftPayload,
  EventLineClarificationDraftResult,
  EventLineDetail,
  EventLineMutationPayload,
  GoalRecord,
  GrowthLedgerResponse,
  GrowthOverview,
  GrowthPendingCaptureActionPayload,
  GrowthPendingCaptureActionResponse,
  GrowthRecommendationActionResponse,
  GrowthRecommendationDismissPayload,
  GrowthWorkbenchSnapshot,
  GrowthValidationActionResponse,
  GrowthValidationPayload,
  HandbookEntry,
  HandbookEntryDetail,
  HandbookEntryPayload,
  HealthResponse,
  ImportRecord,
  KnowledgeJob,
  KnowledgeProgress,
  KnowledgeMemoryRecord,
  KnowledgeSearchResult,
  KnowledgeStatus,
  LegacyScanReport,
  IntelligenceProfile,
  LinkMaterialImportRun,
  MaintenanceMemberPermission,
  MaintenanceModeStatus,
  MaintenancePermissionUpdatePayload,
  MentionCandidate,
  OrgIntroDocumentSettings,
  OrgIntroDocumentUploadPayload,
  OrgModelSettings,
  OrganizationDnaUploadPayload,
  MeetingPipelineResult,
  Operator,
  ProjectFlow,
  ProjectFlowDetail,
  ProjectFlowPayload,
  ProjectModule,
  ProjectModuleDetail,
  ProjectModulePayload,
  ProjectStructureResponse,
  PrepPackCard,
  ProposalApprovalPayload,
  ProposalExecutionPayload,
  ProposalExecutionPreview,
  ProposalExecutionResult,
  ProposalExecutionResponse,
  ProposalBatchActionPayload,
  ProposalBatchResult,
  ProposalRecord,
  KernelPrimaryRolloutRun,
  KernelPrimaryRolloutStartPayload,
  KernelPrimaryRolloutRollbackPayload,
  ExecutionTicket,
  ExecutionTicketLog,
  ExecutionRetryMetrics,
  EvidenceQualityFeedbackSnapshot,
  DataCenterArtifactStatus,
  DataCenterOperationalStatus,
  DataCenterSchemaStatus,
  RollbackDrillPayload,
  RollbackDrillResult,
  MobileDataCenterSnapshotSummary,
  EvidenceQualityAnnotation,
  SettingsPayload,
  SystemAdminSettings,
  SystemAdminSettingsPayload,
  TaskOrgBackfillResult,
  Task,
  TaskActivityRecord,
  TaskContextPreview,
  PageContextPack,
  DataCenterRequest,
  DataCenterKernelResult,
  DataCenterProposalDraft,
  DataCenterProposalDraftPromoteResponse,
  DataCenterShadowRun,
  DataCenterShadowSummary,
  ExternalEvidenceCard,
  GenerationRuntimeState,
  LlmHealthcheckResult,
  LlmProviderProbeResult,
  KnowledgeParseFailure,
  KnowledgeParseFailureRetryResult,
  WorkspaceDataCenterReadiness,
  WorkspaceDataCenterReadinessActionPayload,
  WorkspaceDataCenterReadinessActionResult,
  WorkspaceContextRefreshEnqueuePayload,
  WorkspaceContextRefreshEnqueueResult,
  WorkspaceContextRefreshEvent,
  WorkspaceProposalDraftCreatePayload,
  RetrievalHealth,
  RetrievalModelSettings,
  RetrievalShadowRun,
  RetrievalShadowSummary,
  SourceIntegrityReport,
  WorkspaceChatDiagnostics,
  WorkspaceAnswerValueDiagnostics,
  WorkspaceAnswerActionCardResult,
  WorkspaceAnswerQualityFailure,
  WorkspaceAnswerValueReview,
  WorkspaceAnswerValueSummary,
  WorkspaceAnswerExperience,
  WorkspaceAnswerFinalization,
  WorkspaceValueValidationSession,
  TaskContextBrief,
  TaskSmartBrief,
  TaskTag,
  TaskTagMutationPayload,
  TaskTagSuggestionPayload,
  TaskMutationPayload,
  TaskListMutationPayload,
  TaskList,
  TaskSettings,
  TaskSettingsPayload,
  TopicsSettings,
  TopicsSettingsPayload,
  UpdateProfilePayload,
  HandbookSettings,
  HandbookSettingsPayload,
  CoachCaseRecord,
  CoachReminderRule,
  TopicCaptureBatchResult,
  TopicCandidate,
  TopicCandidateChatPayload,
  TopicCandidateChatResponse,
  TopicCandidateInsight,
  TopicCandidatePayload,
  TopicTaskPlanResult,
  TopicTaskPromotionDraft,
  TopicTaskPromotionResult,
  TopicRadar,
  TopicRadarPayload,
  ReviewDashboard,
  ReviewPerspectiveKey,
  WeeklyOverviewRefreshPayload,
  WeeklyOverviewRefreshStatus,
  ReviewHistoryResponse,
  JudgmentConfirmPayload,
  JudgmentVersion,
  ConflictGroup,
  Entity,
  EntityListResponse,
  FactContradiction,
  FactContradictionListResponse,
  OpenQuestion,
  OrgWritingNorm,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipApplyPayload,
  OrgMembershipSummary,
  RunComparison,
  RuntimeRunLog,
  SupportRequestCreatePayload,
  SupportRequestResolvePayload,
  SupportRequestRecord,
  StrategicCockpitConfirmPayload,
  StrategicCockpitSnapshot,
  StrategicThought,
  StrategicThoughtRefreshPayload,
  StrategicThoughtReview,
  StrategicThoughtReviewPayload,
  StrategicThoughtStatePayload,
  StrategicThoughtsResponse,
  StrategicLineDetail,
  ThemeCluster,
  TaskViewDefinition,
  TaskViewMutationPayload,
  TaskViewsResponse,
  WeeklyReviewPayload,
  LearningRecommendation,
  LocalInputMemory,
  ReviewDashboardDrillTargetResponse,
  SaveAiInputMemoryPayload,
  SaveCloudAuthInputMemoryPayload,
  SaveFeishuInputMemoryPayload,
  CollabActionResult,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
  EventLineReportSnapshot,
} from '../../shared/types';

export type {
  ProjectModule,
  StrategicThought,
  StrategicThoughtRefreshPayload,
  StrategicThoughtReview,
  StrategicThoughtReviewPayload,
  StrategicThoughtStatePayload,
  StrategicThoughtsResponse,
} from '../../shared/types';

function createBrowserWorkbenchFallback(): Window['yiyuWorkbench'] {
  const backendBaseUrl = 'http://127.0.0.1:47829';
  const notAvailable = async (action: string) => {
    throw new Error(`${action} 仅在桌面版可用，请在 Electron 应用中打开。`);
  };

  return {
    backendBaseUrl,
    getDesktopAppInfo: async () => ({
      appVersion: 'browser-preview',
      isPackaged: false,
      platform: 'browser',
      arch: 'browser',
      appBundlePath: '',
      executablePath: '',
      releasePlanPath: '',
      releaseArtifactsPath: '',
      updateChannel: 'beta',
      updaterPhase: 'planning',
      recommendedInstallPath: '',
      installStatus: 'warning',
      installWarning: '当前为浏览器预览模式，文件选择、协作同步和本地安装能力不可用。',
      currentRendererEntry: null,
      currentRendererHash: null,
      backendSourceHash: null,
      startupGateStatus: 'warning',
      startupGateReason: '当前为浏览器预览模式，没有桌面安装态校验。',
      installReceiptStatus: 'missing',
      installSmokeStatus: 'missing',
      detectedAppPaths: [],
      legacyAppPaths: [],
    }),
    resumeFromStartupGate: async () => ({
      resumed: false,
      loadMode: 'blocked',
      appInfo: {
        appVersion: 'browser-preview',
        isPackaged: false,
        platform: 'browser',
        arch: 'browser',
        appBundlePath: '',
        executablePath: '',
        releasePlanPath: '',
        releaseArtifactsPath: '',
        updateChannel: 'beta',
        updaterPhase: 'planning',
        recommendedInstallPath: '',
        installStatus: 'warning',
        installWarning: '当前为浏览器预览模式，没有桌面启动门禁恢复能力。',
        currentRendererEntry: null,
        currentRendererHash: null,
        backendSourceHash: null,
        startupGateStatus: 'warning',
        startupGateReason: '当前为浏览器预览模式，没有桌面安装态校验。',
        installReceiptStatus: 'missing',
        installSmokeStatus: 'missing',
        detectedAppPaths: [],
        legacyAppPaths: [],
      },
    }),
    selectFiles: async () => [],
    selectFolder: async () => null,
    selectCollabRepo: async () => null,
    getCollabRepoStatus: async () => ({
      repoPath: null,
      repoName: null,
      suggestedRepoPath: null,
      isConfigured: false,
      isValid: false,
      branch: null,
      isMainBranch: false,
      hasLocalChanges: false,
      hasUnmergedPaths: false,
      aheadCount: 0,
      behindCount: 0,
      localChangeCount: 0,
      remoteChangeCount: 0,
      statusText: '当前为浏览器预览模式，Git 协作能力不可用。',
    }),
    previewPushToMain: async () => notAvailable('推送到 main'),
    commitAndPushToMain: async () => notAvailable('推送到 main'),
    previewPullFromMain: async () => notAvailable('从 main 拉取'),
    pullSelectedFromMain: async () => notAvailable('从 main 拉取'),
    rebuildAndInstallFromRepo: async () => notAvailable('重装应用'),
    setWorkspaceInteractionState: async (payload: { active: boolean; source: string; detail?: string | null }) => ({
      active: payload.active,
      source: payload.source,
      detail: payload.detail ?? null,
      updatedAt: new Date().toISOString(),
    }),
    getDroppedFilePath: () => null,
    readTextFile: async () => notAvailable('读取本地文件'),
    openPath: async () => notAvailable('打开本地路径'),
    openExternalUrl: async (targetUrl: string) => {
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
      return true;
    },
    revealInFinder: async () => notAvailable('在 Finder 中显示'),
    saveFileAs: async () => notAvailable('另存为'),
    quitApp: async () => notAvailable('退出应用'),
  };
}

if (typeof window !== 'undefined' && !window.yiyuWorkbench) {
  window.yiyuWorkbench = createBrowserWorkbenchFallback();
}

const baseUrl = window.yiyuWorkbench.backendBaseUrl;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase();
  const maxRetry = method === 'GET' ? 12 : 0;
  let response: Response | null = null;
  let lastError: unknown = null;
  for (let attempt = 0; attempt <= maxRetry; attempt += 1) {
    try {
      response = await fetch(`${baseUrl}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(options?.headers ?? {}),
        },
        ...options,
      });
      break;
    } catch (error) {
      lastError = error;
      const detail = error instanceof Error ? error.message : String(error);
      const isTransient = /Failed to fetch/i.test(detail) || /Load failed/i.test(detail);
      if (!isTransient || attempt === maxRetry) {
        if (isTransient) {
          throw new Error('无法连接本地服务，请等待应用完成启动，或重启软件后重试。');
        }
        throw new Error(detail || '请求失败');
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  if (!response) {
    const detail = lastError instanceof Error ? lastError.message : String(lastError ?? '');
    throw new Error(detail || '请求失败');
  }
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail || text;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

type FormRequestOptions = Omit<RequestInit, 'body'> & {
  onProgress?: (loaded: number, total: number) => void;
};

async function requestForm<T>(path: string, formData: FormData, options?: FormRequestOptions): Promise<T> {
  const onProgress = options?.onProgress;
  if (onProgress) {
    return new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open((options?.method || 'POST').toUpperCase(), `${baseUrl}${path}`);
      const headers = new Headers(options?.headers || {});
      headers.forEach((value, key) => {
        xhr.setRequestHeader(key, value);
      });
      xhr.upload.onprogress = (event) => {
        onProgress(event.loaded, event.lengthComputable ? event.total : 0);
      };
      xhr.onerror = () => {
        reject(new Error('附件上传失败，请稍后重试。'));
      };
      xhr.onload = () => {
        const text = xhr.responseText || '';
        if (xhr.status < 200 || xhr.status >= 300) {
          let detail = text;
          try {
            const payload = JSON.parse(text) as { detail?: string };
            detail = payload.detail || text;
          } catch {}
          reject(new Error(detail || `HTTP ${xhr.status}`));
          return;
        }
        try {
          resolve(JSON.parse(text) as T);
        } catch (error) {
          reject(error instanceof Error ? error : new Error('附件上传响应解析失败'));
        }
      };
      xhr.send(formData);
    });
  }
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail || text;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth() {
  return request<HealthResponse>('/api/v1/system/health');
}

export type BrainPulse = {
  memoryCount: number;
  docCount: number;
  taskCount: number;
  chatCount: number;
  eventLineCount: number;
  dnaCount: number;
  badgeCount: number;
  handbookCount: number;
  daysAccompanied: number;
  reviewCount: number;
  meetingCount: number;
  weeklyNewFacts: number;
};

export type BrainClientData = {
  id: string;
  name: string;
  confidence: number;
  stage: string;
  intro?: string | null;
  docs: number;
  dna: number;
  eventLines: number;
  memoryFacts: number;
};

export type BrainDashboard = {
  pulse: BrainPulse;
  clients: BrainClientData[];
};

export async function getBrainDashboard() {
  return request<BrainDashboard>('/api/v1/brain/dashboard');
}

export type DigitalAssetMetric = {
  key: string;
  label: string;
  value: number;
  hint?: string;
};

export type DigitalAssetSourceRef = {
  sourceType: string;
  sourceId: string;
  title: string;
  excerpt: string;
  updatedAt?: string | null;
};

export type DigitalAssetInsight = {
  dimensionKey: string;
  title: string;
  summary: string;
  evidenceCount: number;
};

export type DigitalAssetDepositSuggestion = {
  priority: 'high' | 'medium' | 'low';
  dimensionKey: string;
  title: string;
  reason: string;
  examples: string[];
  expectedGain: number;
  analysisValueUnlocked: string;
  suggestedDocumentContent?: string[];
  sourceHighlights?: string[];
};

export type DigitalAssetScoreBreakdown = {
  deposited: number;
  understood: number;
  computable: number;
  compounding: number;
  structuralCompleteness: number;
  evidenceChain: number;
  timeContinuity: number;
  resultFeedbackLoop: number;
};

export type DigitalAssetMaterialMaturityRow = {
  key: string;
  label: string;
  percent: number;
  level: string;
  seenSummary: string;
  missingSummary: string;
  suggestedAction: string;
  unlockedValue: string;
  sourceHighlights: string[];
};

export type DigitalAssetPulseFunnelItem = {
  key: string;
  label: string;
  value: number;
};

export type DigitalAssetPulseOrganization = {
  clientId: string;
  name: string;
  assetProfileType: string;
  maturityScore: number;
  depositThickness: number;
  weeklyNewFacts: number;
  weeklyNewDocuments: number;
  weeklyNewEvidenceCards: number;
  summary: string;
};

export type DigitalAssetPulseSignal = {
  clientId?: string | null;
  name: string;
  title: string;
  summary: string;
  assetProfileType: string;
  maturityScore: number;
  severity: 'info' | 'warning' | 'critical';
};

export type DigitalAssetPulse = {
  headline: string;
  daysAccompanied: number;
  weeklyNewFacts: number;
  weeklyNewDocuments: number;
  weeklyNewEvidenceCards: number;
  weeklyNewJudgments: number;
  digestionFunnel: DigitalAssetPulseFunnelItem[];
  activeOrganizations: DigitalAssetPulseOrganization[];
  learningHighlights: DigitalAssetPulseSignal[];
  assetAlerts: DigitalAssetPulseSignal[];
};

export type DigitalAssetUnit = {
  key: string;
  label: string;
  level: 'required' | 'advanced' | 'opportunity';
  covered: boolean;
  evidenceCount: number;
};

export type DigitalAssetMapNode = {
  key: string;
  label: string;
  description: string;
  trackTitle: string;
  currentStage: string;
  stageIndex: number;
  coverageScore: number;
  maturityPercent?: number;
  evidenceCount: number;
  coveredUnits: DigitalAssetUnit[];
  missingUnits: DigitalAssetUnit[];
  unlockedValue: string;
  nextDeposit: string;
  seenSummary?: string;
  missingSummary?: string;
  suggestedDocumentTitle?: string;
  suggestedDocumentContent?: string[];
  unlockedAnalysisValue?: string;
  sourceHighlights?: string[];
  representativeSources: DigitalAssetSourceRef[];
};

export type DigitalAssetDimension = {
  key: string;
  label: string;
  description: string;
  maturity: number;
  scoreBreakdown: DigitalAssetScoreBreakdown;
  evidenceCount: number;
  sourceTypes: string[];
  representativeSources: DigitalAssetSourceRef[];
  valueInsights: string[];
  gaps: string[];
  depositSuggestions: string[];
  formedValue: string;
  nextBestDeposit: string;
  expectedGain: number;
  analysisValueUnlocked: string;
  statusLabels: string[];
};

export type DigitalAssetClientSummary = {
  id: string;
  name: string;
  stage: string;
  intro: string;
  assetCompletionScore: number;
  understandingScore: number;
  understandingStatement: string;
  depositedValueLevel: string;
  nextValueSpace: string;
  depositXp: number;
  assetProfileType: string;
  secondaryProfileTypes: string[];
  maturityScore: number;
  depositThickness: number;
  scoreMethodVersion: string;
  scoreBreakdown: DigitalAssetScoreBreakdown;
  scoreRationale: string[];
  materialMaturityRows: DigitalAssetMaterialMaturityRow[];
  assetStage: string;
  assetTrackTitle: string;
  growthMode: '均衡成长' | '单项突破' | '结构偏科';
  stageProgress: number;
  nextStage: string;
  unlockedCapabilities: string[];
  stageBlockers: string[];
  nextBestDeposits: DigitalAssetDepositSuggestion[];
  assetMapNodes: DigitalAssetMapNode[];
  assetDimensionCount: number;
  strongestDimensions: string[];
  highValueSignals: string[];
  criticalGaps: string[];
  nextDeposits: string[];
  metrics: DigitalAssetMetric[];
  emptyState: boolean;
  updatedAt?: string | null;
};

export type DigitalAssetNarrative = {
  id: string;
  clientId: string;
  sourceFingerprint: string;
  contentMarkdown: string;
  materialAudit: Record<string, unknown>;
  qualityWarnings: string[];
  provider: string;
  model: string;
  generatedAt: string;
  failureReason?: string;
};

export type DigitalAssetDashboard = {
  generatedAt: string;
  pulse: DigitalAssetPulse;
  clients: DigitalAssetClientSummary[];
};

export type OrganizationDnaV2Kind = 'stable_dna' | 'evolving_dna' | 'gap_dna' | 'risk_dna';
export type OrganizationDnaV2Status = 'candidate' | 'confirmed' | 'stale' | 'deprecated';
export type OrganizationDnaEvidenceLevel = 'L1' | 'L2' | 'L3' | 'internal' | 'weak';

export type OrganizationDnaV2Item = {
  id: string;
  moduleKind: OrganizationDnaV2Kind;
  title: string;
  contentMarkdown: string;
  summary: string;
  status: OrganizationDnaV2Status;
  evidenceLevel: OrganizationDnaEvidenceLevel;
  sourceType: string;
  sourceId: string;
  sourceLabel: string;
  observedAt: string;
  sourceCreatedAt?: string | null;
  lastSeenAt: string;
  validUntil?: string | null;
  confidenceScore: number;
  createdAt: string;
  updatedAt: string;
};

export type OrganizationDnaRefreshEvent = {
  id: string;
  runId: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  detail: Record<string, unknown>;
  createdAt: string;
};

export type OrganizationDnaRefreshRun = {
  id: string;
  jobType: 'organization_dna_refresh';
  status: 'queued' | 'running' | 'completed' | 'failed';
  triggerSource: string;
  totalItems: number;
  processedItems: number;
  error?: string | null;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  updatedAt: string;
  events: OrganizationDnaRefreshEvent[];
};

export type OrganizationDnaV2Snapshot = {
  generatedAt: string;
  stableItems: OrganizationDnaV2Item[];
  evolvingItems: OrganizationDnaV2Item[];
  gapItems: OrganizationDnaV2Item[];
  riskItems: OrganizationDnaV2Item[];
  itemCounts: Record<string, number>;
  confirmedCount: number;
  candidateCount: number;
  staleCount: number;
  latestRun?: OrganizationDnaRefreshRun | null;
  updatedAt?: string | null;
};

export type DigitalAssetClientDetail = DigitalAssetClientSummary & {
  dimensions: DigitalAssetDimension[];
  valueInsights: DigitalAssetInsight[];
  depositSuggestions: DigitalAssetDepositSuggestion[];
  sourceMetrics: DigitalAssetMetric[];
  aiNarrative?: DigitalAssetNarrative | null;
};

export async function getDigitalAssetDashboard() {
  return request<DigitalAssetDashboard>('/api/v1/digital-assets/dashboard');
}

export async function getOrganizationDnaV2Snapshot() {
  return request<OrganizationDnaV2Snapshot>('/api/v1/digital-assets/organization-dna');
}

export async function refreshOrganizationDnaV2(triggerSource = 'manual') {
  return request<OrganizationDnaRefreshRun>('/api/v1/digital-assets/organization-dna/refresh', {
    method: 'POST',
    body: JSON.stringify({ triggerSource }),
  });
}

export async function getClientDigitalAssets(clientId: string) {
  return request<DigitalAssetClientDetail>(`/api/v1/clients/${encodeURIComponent(clientId)}/digital-assets`);
}

export async function refreshClientDigitalAssetNarrative(clientId: string) {
  return request<DigitalAssetNarrative>(`/api/v1/clients/${encodeURIComponent(clientId)}/digital-assets/narrative/refresh`, {
    method: 'POST',
  });
}

export async function getTaskContextPreview(taskId: string) {
  return request<TaskContextPreview>(`/api/v1/tasks/${taskId}/context-preview`);
}

export async function getClientPageContext(
  clientId: string,
  options?: {
    page?: 'client_workspace' | 'workspace_chat' | 'task_detail' | 'task_ai' | 'meeting_detail' | 'event_line_detail' | 'project_module_detail' | 'project_flow_detail' | 'strategic_cockpit';
    prompt?: string;
    includeRawEvidence?: boolean;
    scopeId?: string;
    taskId?: string;
    meetingId?: string;
    eventLineId?: string;
    projectModuleId?: string;
    projectFlowId?: string;
  },
) {
  const query = new URLSearchParams();
  query.set('page', options?.page || 'client_workspace');
  if (options?.prompt?.trim()) query.set('prompt', options.prompt.trim());
  if (options?.includeRawEvidence) query.set('includeRawEvidence', 'true');
  if (options?.scopeId) query.set('scopeId', options.scopeId);
  if (options?.taskId) query.set('taskId', options.taskId);
  if (options?.meetingId) query.set('meetingId', options.meetingId);
  if (options?.eventLineId) query.set('eventLineId', options.eventLineId);
  if (options?.projectModuleId) query.set('projectModuleId', options.projectModuleId);
  if (options?.projectFlowId) query.set('projectFlowId', options.projectFlowId);
  return request<PageContextPack>(`/api/v1/clients/${encodeURIComponent(clientId)}/page-context?${query.toString()}`);
}

export async function getTaskPageContext(taskId: string, prompt = '', includeRawEvidence = false) {
  const query = new URLSearchParams();
  if (prompt.trim()) query.set('prompt', prompt.trim());
  if (includeRawEvidence) query.set('includeRawEvidence', 'true');
  const suffix = query.toString();
  const url = suffix
    ? `/api/v1/tasks/${encodeURIComponent(taskId)}/page-context?${suffix}`
    : `/api/v1/tasks/${encodeURIComponent(taskId)}/page-context`;
  return request<PageContextPack>(url);
}

export type TaskUnderstandingSnapshot = {
  taskId?: string;
  mode?: 'basic' | 'enhanced';
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  confidence: number;
  sourceBreakdown: Array<{
    sourceName?: string;
    sourceType?: string;
    available: boolean;
    label?: string;
    snippet?: string;
  }>;
  coverage: number;
  optionalAdvice?: {
    realBlocker?: string;
    timeGate?: string;
    minimumAction?: string;
    supportAsk?: string;
  } | null;
  _pending?: boolean;
};

export async function getTaskUnderstanding(taskId: string) {
  return request<TaskUnderstandingSnapshot>(`/api/v1/tasks/${taskId}/understanding`);
}

export async function getTaskSmartBrief(taskId: string) {
  return request<TaskSmartBrief>(`/api/v1/tasks/${taskId}/smart-brief`);
}

export async function getTaskContextBrief(taskId: string) {
  return request<TaskContextBrief>(`/api/v1/tasks/${taskId}/context-brief`);
}

export async function getTaskContextBriefsBatch(taskIds: string[]) {
  return request<{ briefs: TaskContextBrief[] }>('/api/v1/tasks/context-briefs/batch', {
    method: 'POST',
    body: JSON.stringify({ taskIds }),
  });
}

export async function getTaskPrepPack(taskId: string) {
  return request<PrepPackCard>(`/api/v1/tasks/${taskId}/prep-pack`);
}

export async function createTaskPrepProposal(taskId: string) {
  return request<ProposalRecord>(`/api/v1/tasks/${taskId}/prep-pack/proposals`, {
    method: 'POST',
  });
}

export async function getTaskSmartBriefsBatch(taskHints: Array<{ id: string; title: string; desc?: string; clientId?: string | null; eventLineId?: string | null; attachmentTitles?: string[] }>) {
  return request<TaskSmartBrief[]>('/api/v1/tasks/smart-briefs', {
    method: 'POST',
    body: JSON.stringify({ tasks: taskHints }),
  });
}

export async function adoptTaskSmartBriefAction(taskId: string, actionKey: string, payload: { createdTaskId: string; actionText?: string }) {
  return request<{ ok: boolean; taskId: string; actionKey: string; createdTaskId: string }>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/smart-brief-actions/${encodeURIComponent(actionKey)}/adopt`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export async function getAuthState() {
  return request<AuthState>('/api/v1/auth/me');
}

export async function register(payload: AuthRegisterPayload) {
  return request<AuthState>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getDepartmentOptions(params?: { organizationId?: string | null; inviteCode?: string | null }) {
  const searchParams = new URLSearchParams();
  if (params?.organizationId) searchParams.set('organizationId', params.organizationId);
  if (params?.inviteCode) searchParams.set('inviteCode', params.inviteCode);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
  return request<DepartmentOption[]>(`/api/v1/auth/department-options${suffix}`);
}

export async function resolveInviteCode(code: string) {
  return request<OrgInviteResolveResult>(`/api/v1/auth/invite-code/resolve?code=${encodeURIComponent(code)}`);
}

export async function login(payload: AuthLoginPayload) {
  return request<AuthState>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function processPendingConsultationKnowledgeRequests() {
  return request<ConsultationKnowledgeProcessSummary>('/api/v1/consultation/knowledge-requests/process-pending', {
    method: 'POST',
  });
}

export async function logout() {
  return request<AuthState>('/api/v1/auth/logout', { method: 'POST' });
}

export async function changePassword(payload: ChangePasswordPayload) {
  return request<{ message: string }>('/api/v1/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProfile(payload: UpdateProfilePayload) {
  return request<AuthState>('/api/v1/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getLocalInputMemory() {
  return request<LocalInputMemory>('/api/v1/local-input-memory');
}

export async function saveCloudAuthInputMemory(payload: SaveCloudAuthInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/cloud-auth', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function saveAiInputMemory(payload: SaveAiInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/ai', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function saveFeishuInputMemory(payload: SaveFeishuInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/feishu', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function adminResetPassword(employeeId: string, payload: AdminResetPasswordPayload) {
  return request<{ message: string }>(`/api/v1/admin/employees/${encodeURIComponent(employeeId)}/reset-password`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSettings() {
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse; lastCloudAiSyncStatus: LastCloudAiSyncStatus }>('/api/v1/settings');
}

export async function syncOrgAiConfigToCloud() {
  return request<LastCloudAiSyncStatus>('/api/v1/settings/org-ai-config/sync-to-cloud', { method: 'POST' });
}

export async function getMaintenanceModeStatus() {
  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/status');
}

export async function enterMaintenanceMode() {
  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/enter', { method: 'POST' });
}

export async function exitMaintenanceMode() {
  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/exit', { method: 'POST' });
}

export async function getMaintenanceModeMembers() {
  return request<MaintenanceMemberPermission[]>('/api/v1/admin/maintenance-mode/members');
}

export async function updateMaintenanceModeMembers(payload: MaintenancePermissionUpdatePayload) {
  return request<MaintenanceMemberPermission[]>('/api/v1/admin/maintenance-mode/members', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function updateSettings(payload: SettingsPayload) {
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse; lastCloudAiSyncStatus: LastCloudAiSyncStatus }>('/api/v1/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTaskSettings() {
  return request<TaskSettings>('/api/v1/settings/tasks');
}

export async function updateTaskSettings(payload: TaskSettingsPayload) {
  return request<TaskSettings>('/api/v1/settings/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getOrgModelProfile() {
  return request<OrgModelSettings>('/api/v1/settings/org-model/profile');
}

export async function updateOrgModelProfile(payload: OrgModelSettings) {
  return request<OrgModelSettings>('/api/v1/settings/org-model/profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function parseOrgIntroDocument(payload: OrgIntroDocumentUploadPayload) {
  return request<OrgIntroDocumentSettings>('/api/v1/settings/org-model/intro-document', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function backfillOrgTaskLinks() {
  return request<TaskOrgBackfillResult>('/api/v1/settings/org-model/backfill-task-links', {
    method: 'POST',
  });
}

export async function getClientWorkspaceSettings() {
  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace');
}

export async function updateClientWorkspaceSettings(payload: ClientWorkspaceSettingsPayload) {
  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTopicsSettings() {
  return request<TopicsSettings>('/api/v1/settings/topics');
}

export async function updateTopicsSettings(payload: TopicsSettingsPayload) {
  return request<TopicsSettings>('/api/v1/settings/topics', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisWorkbenchSettings() {
  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench');
}

export async function updateAnalysisWorkbenchSettings(payload: AnalysisWorkbenchSettingsPayload) {
  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getHandbookSettings() {
  return request<HandbookSettings>('/api/v1/settings/handbook');
}

export async function updateHandbookSettings(payload: HandbookSettingsPayload) {
  return request<HandbookSettings>('/api/v1/settings/handbook', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSystemAdminSettings() {
  return request<SystemAdminSettings>('/api/v1/settings/system-admin');
}

export async function updateSystemAdminSettings(payload: SystemAdminSettingsPayload) {
  return request<SystemAdminSettings>('/api/v1/settings/system-admin', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getMainChainStabilitySettings() {
  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability');
}

export async function updateMainChainStabilitySettings(payload: MainChainStabilitySettingsPayload) {
  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuBotSettings() {
  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot');
}

export async function updateFeishuBotSettings(payload: FeishuBotSettingsPayload) {
  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuUserBinding() {
  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding');
}

export async function startFeishuUserBinding() {
  return request<FeishuUserBindingStartResult>('/api/v1/settings/feishu-user-binding/start', {
    method: 'POST',
  });
}

export async function clearFeishuUserBinding() {
  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding', {
    method: 'DELETE',
  });
}

export async function getOrgMembershipSummary() {
  return request<OrgMembershipSummary>('/api/v1/me/org-membership');
}

export async function applyOrgMembership(payload: OrgMembershipApplyPayload) {
  return request<OrgMembershipSummary>('/api/v1/me/org-membership/apply', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorization>('/api/v1/me/feishu-authorization');
}

export async function startFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorizationStartResult>('/api/v1/me/feishu-authorization/start', {
    method: 'POST',
  });
}

export async function clearFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorization>('/api/v1/me/feishu-authorization', {
    method: 'DELETE',
  });
}

export async function getOrgFeishuIntegration() {
  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu');
}

export async function saveOrgFeishuIntegration(payload: OrgFeishuIntegrationPayload) {
  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu/validate-and-save', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuDeliveryProfile() {
  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile');
}

export async function saveFeishuDeliveryProfile(payload: FeishuDeliveryProfilePayload) {
  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createBackup() {
  return request<{ backupPath: string; createdAt: string }>('/api/v1/settings/backup', { method: 'POST' });
}

export async function scanLegacy(path: string) {
  return request<LegacyScanReport>('/api/v1/settings/legacy-scan', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function loadDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/load', { method: 'POST' });
}

export async function clearDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/clear', { method: 'POST' });
}

export async function getActivityLogs() {
  return request<
    Array<{
      id: string;
      actorName: string;
      action: string;
      entityType: string;
      entityId: string;
      detail: Record<string, unknown>;
      createdAt: string;
    }>
  >('/api/v1/settings/logs');
}

// ── System Logs ───────────────────────────────────────────────
export type SystemLogEntry = {
  ts: string;
  level: string;
  source: string;
  message: string;
  method?: string;
  path?: string;
  status?: number;
  duration_ms?: number;
  user?: string;
  error?: string;
  traceback?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  actor?: string;
  detail?: Record<string, unknown>;
};

export type SystemLogsResponse = {
  entries: SystemLogEntry[];
  dates: string[];
  total: number;
};

export async function getSystemLogs(params?: {
  startDate?: string;
  endDate?: string;
  level?: string;
  source?: string;
  keyword?: string;
  limit?: number;
}) {
  const search = new URLSearchParams();
  if (params?.startDate) search.set('startDate', params.startDate);
  if (params?.endDate) search.set('endDate', params.endDate);
  if (params?.level) search.set('level', params.level);
  if (params?.source) search.set('source', params.source);
  if (params?.keyword) search.set('keyword', params.keyword);
  if (params?.limit) search.set('limit', String(params.limit));
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<SystemLogsResponse>(`/api/v1/logs${suffix}`);
}

export async function exportSystemLogs(params?: {
  startDate?: string;
  endDate?: string;
  level?: string;
  source?: string;
  keyword?: string;
}) {
  const search = new URLSearchParams();
  if (params?.startDate) search.set('startDate', params.startDate);
  if (params?.endDate) search.set('endDate', params.endDate);
  if (params?.level) search.set('level', params.level);
  if (params?.source) search.set('source', params.source);
  if (params?.keyword) search.set('keyword', params.keyword);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${baseUrl}/api/v1/logs/export${suffix}`);
  return res.text();
}

export async function getLogDates() {
  return request<string[]>('/api/v1/logs/dates');
}

export async function getEmployees() {
  return request<EmployeeRecord[]>('/api/v1/admin/employees');
}

export async function approveEmployee(id: string, payload: EmployeeRolePayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function rejectEmployeeReview(id: string, payload: EmployeeRejectPayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function disableEmployee(id: string) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/disable`, {
    method: 'POST',
  });
}

export async function updateEmployeeRole(id: string, payload: EmployeeRolePayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/role`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function updateEmployeeDepartment(id: string, payload: EmployeeDepartmentPayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/department`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getMentionCandidates(query = '') {
  return request<MentionCandidate[]>(`/api/v1/employees/mention-candidates?q=${encodeURIComponent(query)}`);
}

export async function getClients() {
  const clients = await request<ClientSummary[]>('/api/v1/clients');
  return clients.filter((client) => client.alias !== 'workspace-smoke' && client.name !== '安装态冒烟客户');
}

export async function createClient(payload: ClientMutationPayload) {
  return request<ClientSummary>('/api/v1/clients', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateClient(id: string, payload: ClientMutationPayload) {
  return request<ClientSummary>(`/api/v1/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteClient(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/clients/${id}`, {
    method: 'DELETE',
  });
}

export async function deleteClientFolder(clientId: string, folderId: string) {
  return request<{ deleted: boolean }>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'DELETE',
  });
}

export async function getClientWorkspace(id: string) {
  return request<ClientWorkspace>(`/api/v1/clients/${id}/workspace`);
}

export async function createAnalysisJob(payload: AnalysisJobCreatePayload) {
  return request<AnalysisJob>('/api/v1/analysis/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function backfillAnalysisMainChain(payload: AnalysisBackfillMainChainPayload) {
  return request<AnalysisBackfillMainChainResult>('/api/v1/analysis/backfill-main-chain', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisJob(jobId: string) {
  return request<AnalysisJob>(`/api/v1/analysis/jobs/${jobId}`);
}

export async function getAnalysisJobStages(jobId: string) {
  return request<AnalysisJobStageRun[]>(`/api/v1/analysis/jobs/${jobId}/stages`);
}

export async function getRuntimeRunLog(runId: string) {
  return request<RuntimeRunLog>(`/api/v1/runtime/run-log/${runId}`);
}

export async function createDnaDelta(payload: DnaDeltaCreatePayload) {
  return request<DnaDelta>('/api/v1/memory/dna/delta', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function confirmJudgment(payload: JudgmentConfirmPayload) {
  return request<JudgmentVersion>('/api/v1/memory/judgments/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function decideApproval(payload: ApprovalDecisionPayload) {
  return request<ApprovalRecord>('/api/v1/approvals/decide', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientJudgments(clientId: string) {
  return request<JudgmentVersion[]>(`/api/v1/clients/${clientId}/judgments`);
}

export async function getClientTopics(clientId: string) {
  return request<ThemeCluster[]>(`/api/v1/clients/${clientId}/topics`);
}

export async function getClientConflicts(clientId: string) {
  return request<ConflictGroup[]>(`/api/v1/clients/${clientId}/conflicts`);
}

export async function getClientOpenQuestions(clientId: string) {
  return request<OpenQuestion[]>(`/api/v1/clients/${clientId}/open-questions`);
}

export async function getClientRuntimeRunLogs(clientId: string) {
  return request<RuntimeRunLog[]>(`/api/v1/clients/${clientId}/runtime-run-logs`);
}

export async function getClientEntities(
  clientId: string,
  options: {
    type?:
      | 'person'
      | 'company'
      | 'project'
      | 'product'
      | 'competitor'
      | 'amount'
      | 'date';
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<EntityListResponse> {
  const params = new URLSearchParams();
  if (options.type) params.set('type', options.type);
  if (options.q) params.set('q', options.q);
  if (typeof options.limit === 'number') params.set('limit', String(options.limit));
  if (typeof options.offset === 'number') params.set('offset', String(options.offset));
  const suffix = params.toString();
  const url = `/api/v1/clients/${clientId}/entities${suffix ? `?${suffix}` : ''}`;
  return request<EntityListResponse>(url);
}

export async function getClientContradictions(
  clientId: string,
  options: {
    status?: 'pending' | 'dismissed' | 'resolved';
    limit?: number;
    offset?: number;
  } = {},
): Promise<FactContradictionListResponse> {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (typeof options.limit === 'number') params.set('limit', String(options.limit));
  if (typeof options.offset === 'number') params.set('offset', String(options.offset));
  const suffix = params.toString();
  const url = `/api/v1/clients/${clientId}/contradictions${suffix ? `?${suffix}` : ''}`;
  return request<FactContradictionListResponse>(url);
}

export async function reviewContradiction(
  contradictionId: string,
  payload: {
    reviewStatus: 'dismissed' | 'resolved';
    acceptedFactId?: string;
    resolutionNote?: string;
  },
): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/v1/contradictions/${contradictionId}/review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisMigrationMetrics() {
  return request<AnalysisMigrationMetrics>('/api/v1/runtime/analysis-migration-metrics');
}

export async function getClientDnaDocuments(clientId: string) {
  return request<ClientDnaModulesResponse>(`/api/v1/clients/${clientId}/dna-documents`);
}

export async function getClientDnaDocument(clientId: string, moduleKey: ClientDnaModule['moduleKey']) {
  return request<ClientDnaModule>(`/api/v1/clients/${clientId}/dna-documents/${moduleKey}`);
}

export async function updateClientDnaDocument(
  clientId: string,
  moduleKey: ClientDnaModule['moduleKey'],
  payload: OrganizationDnaUploadPayload,
) {
  return request<ClientDnaModule>(`/api/v1/clients/${clientId}/dna-documents/${moduleKey}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientProjectStructure(clientId: string) {
  return request<ProjectStructureResponse>(`/api/v1/clients/${clientId}/project-structure`);
}

export async function getProjectModuleDetail(clientId: string, moduleId: string) {
  return request<ProjectModuleDetail>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`);
}

export async function createProjectModule(clientId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(`/api/v1/clients/${clientId}/project-modules`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectModule(clientId: string, moduleId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectModule(clientId: string, moduleId: string) {
  return request<{ status: string }>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`, {
    method: 'DELETE',
  });
}

export async function getProjectFlowDetail(clientId: string, flowId: string) {
  return request<ProjectFlowDetail>(`/api/v1/clients/${clientId}/project-flows/${flowId}`);
}

export async function createProjectFlow(clientId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectFlow(clientId: string, flowId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows/${flowId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectFlow(clientId: string, flowId: string) {
  return request<{ status: string }>(`/api/v1/clients/${clientId}/project-flows/${flowId}`, {
    method: 'DELETE',
  });
}

export async function getClientKnowledgeStatus(clientId: string) {
  return request<KnowledgeStatus>(`/api/v1/clients/${clientId}/knowledge/status`);
}

export async function getClientKnowledgeProgress(clientId: string) {
  return request<KnowledgeProgress>(`/api/v1/clients/${clientId}/knowledge/progress`);
}

export async function getRetrievalSettings() {
  return request<RetrievalModelSettings>('/api/v1/retrieval/settings');
}

export async function updateRetrievalSettings(payload: Partial<RetrievalModelSettings>) {
  return request<RetrievalModelSettings>('/api/v1/retrieval/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getRetrievalHealth() {
  return request<RetrievalHealth>('/api/v1/retrieval/health');
}

export async function getRetrievalShadowSummary(clientId?: string) {
  const query = new URLSearchParams();
  if (clientId) query.set('clientId', clientId);
  const suffix = query.toString();
  const url = suffix ? `/api/v1/retrieval/shadow-summary?${suffix}` : '/api/v1/retrieval/shadow-summary';
  return request<RetrievalShadowSummary>(url);
}

export async function getRetrievalShadowRuns(clientId?: string, limit = 60) {
  const query = new URLSearchParams();
  if (clientId) query.set('clientId', clientId);
  query.set('limit', String(limit));
  return request<RetrievalShadowRun[]>(`/api/v1/retrieval/shadow-runs?${query.toString()}`);
}

export async function reindexClientVector(clientId: string) {
  return request<{
    clientId: string;
    embeddingSignature: string;
    masterIndexed: number;
    chunkIndexed: number;
    fallbackUsed: boolean;
    status: string;
  }>(`/api/v1/clients/${clientId}/knowledge/reindex-vector`, {
    method: 'POST',
  });
}

export async function getClientVectorIndexStatus(clientId: string) {
  return request<{
    clientId: string;
    embeddingSignature: string;
    activeCollection: string | null;
    legacyCollection?: string | null;
    status: 'ready' | 'stale' | 'building' | 'failed' | string;
    masterIndexed: number;
    chunkIndexed: number;
    error?: string | null;
    updatedAt: string;
  }>(`/api/v1/clients/${clientId}/knowledge/vector-index/status`);
}

export async function resolveDataCenterKernel(payload: DataCenterRequest) {
  return request<DataCenterKernelResult>('/api/v1/data-center/resolve', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function diagnoseDataCenter(params: {
  clientId?: string;
  taskId?: string;
  meetingId?: string;
  topicId?: string;
  page: string;
  prompt: string;
}) {
  const query = new URLSearchParams();
  if (params.clientId) query.set('clientId', params.clientId);
  if (params.taskId) query.set('taskId', params.taskId);
  if (params.meetingId) query.set('meetingId', params.meetingId);
  if (params.topicId) query.set('topicId', params.topicId);
  query.set('page', params.page);
  query.set('prompt', params.prompt);
  return request<DataCenterKernelResult>(`/api/v1/data-center/diagnose?${query.toString()}`);
}

export async function getDataCenterShadowSummary(params?: { scopeType?: string; scopeId?: string }) {
  const query = new URLSearchParams();
  if (params?.scopeType) query.set('scopeType', params.scopeType);
  if (params?.scopeId) query.set('scopeId', params.scopeId);
  const suffix = query.toString();
  const url = suffix ? `/api/v1/data-center/shadow-summary?${suffix}` : '/api/v1/data-center/shadow-summary';
  return request<DataCenterShadowSummary>(url);
}

export async function getDataCenterShadowRuns(params?: { scopeType?: string; scopeId?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.scopeType) query.set('scopeType', params.scopeType);
  if (params?.scopeId) query.set('scopeId', params.scopeId);
  query.set('limit', String(params?.limit ?? 60));
  return request<DataCenterShadowRun[]>(`/api/v1/data-center/shadow-runs?${query.toString()}`);
}

export async function getWorkspaceChatDiagnostics(clientId: string, recentMessages = 20) {
  const query = new URLSearchParams();
  query.set('clientId', clientId);
  query.set('recentMessages', String(recentMessages));
  return request<WorkspaceChatDiagnostics>(`/api/v1/runtime/workspace-chat-diagnostics?${query.toString()}`);
}

export async function getWorkspaceAnswerValueDiagnostics(clientId: string, recentMessages = 50) {
  const query = new URLSearchParams();
  query.set('clientId', clientId);
  query.set('recentMessages', String(recentMessages));
  return request<WorkspaceAnswerValueDiagnostics>(`/api/v1/runtime/workspace-answer-value-diagnostics?${query.toString()}`);
}

export async function createWorkspaceAnswerValueReview(payload: {
  clientId: string;
  messageId: string;
  prompt?: string;
  answerMode?: string;
  userVisibleQualityStatus?: WorkspaceAnswerFinalization['userVisibleQualityStatus'];
  shouldShowRetryBanner?: boolean;
  usableAnswer?: boolean | null;
  reviewerNote?: string;
  manualBaselineMinutes?: number | null;
  dataCenterReviewMinutes?: number | null;
}) {
  return request<WorkspaceAnswerValueReview>('/api/v1/workspace-answer-value-reviews', {
    method: 'POST',
    body: JSON.stringify({
      clientId: payload.clientId,
      messageId: payload.messageId,
      prompt: payload.prompt ?? '',
      answerMode: payload.answerMode ?? '',
      userVisibleQualityStatus: payload.userVisibleQualityStatus ?? 'ready',
      shouldShowRetryBanner: Boolean(payload.shouldShowRetryBanner),
      usableAnswer: payload.usableAnswer ?? null,
      reviewerNote: payload.reviewerNote ?? '',
      manualBaselineMinutes: payload.manualBaselineMinutes ?? null,
      dataCenterReviewMinutes: payload.dataCenterReviewMinutes ?? null,
    }),
  });
}

export async function listWorkspaceAnswerValueReviews(params?: { clientId?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  query.set('limit', String(params?.limit ?? 120));
  return request<WorkspaceAnswerValueReview[]>(`/api/v1/workspace-answer-value-reviews?${query.toString()}`);
}

export async function getWorkspaceAnswerValueSummary(clientId: string) {
  const query = new URLSearchParams();
  query.set('clientId', clientId);
  return request<WorkspaceAnswerValueSummary>(`/api/v1/workspace-answer-value-summary?${query.toString()}`);
}

export async function createWorkspaceValueValidationSession(clientId: string) {
  return request<WorkspaceValueValidationSession>('/api/v1/workspace-value-validation-sessions', {
    method: 'POST',
    body: JSON.stringify({ clientId }),
  });
}

export async function listWorkspaceValueValidationSessions(params?: { clientId?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  query.set('limit', String(params?.limit ?? 20));
  return request<WorkspaceValueValidationSession[]>(`/api/v1/workspace-value-validation-sessions?${query.toString()}`);
}

export async function getWorkspaceValueValidationSession(sessionId: string) {
  return request<WorkspaceValueValidationSession>(`/api/v1/workspace-value-validation-sessions/${encodeURIComponent(sessionId)}`);
}

export async function completeWorkspaceValueValidationQuestion(
  sessionId: string,
  payload: {
    questionId: string;
    reviewId?: string | null;
    messageId?: string | null;
    usableAnswer?: boolean | null;
    retryBannerShown?: boolean | null;
    manualBaselineMinutes?: number | null;
    dataCenterReviewMinutes?: number | null;
    proposalCreated?: boolean;
    executionTicketCreated?: boolean;
    reviewerNote?: string;
  },
) {
  return request<WorkspaceValueValidationSession>(
    `/api/v1/workspace-value-validation-sessions/${encodeURIComponent(sessionId)}/complete-question`,
    {
      method: 'POST',
      body: JSON.stringify({
        questionId: payload.questionId,
        reviewId: payload.reviewId ?? null,
        messageId: payload.messageId ?? null,
        usableAnswer: payload.usableAnswer ?? null,
        retryBannerShown: payload.retryBannerShown ?? null,
        manualBaselineMinutes: payload.manualBaselineMinutes ?? null,
        dataCenterReviewMinutes: payload.dataCenterReviewMinutes ?? null,
        proposalCreated: Boolean(payload.proposalCreated),
        executionTicketCreated: Boolean(payload.executionTicketCreated),
        reviewerNote: payload.reviewerNote ?? '',
      }),
    },
  );
}

export async function finishWorkspaceValueValidationSession(sessionId: string) {
  return request<WorkspaceValueValidationSession>(`/api/v1/workspace-value-validation-sessions/${encodeURIComponent(sessionId)}/finish`, {
    method: 'POST',
  });
}

export async function listWorkspaceAnswerQualityFailures(params?: { clientId?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  query.set('limit', String(params?.limit ?? 80));
  return request<WorkspaceAnswerQualityFailure[]>(`/api/v1/workspace-answer-quality-failures?${query.toString()}`);
}

export async function resolveWorkspaceAnswerQualityFailure(failureId: string, note = '') {
  return request<WorkspaceAnswerQualityFailure>(
    `/api/v1/workspace-answer-quality-failures/${encodeURIComponent(failureId)}/resolve`,
    {
      method: 'POST',
      body: JSON.stringify({ note }),
    },
  );
}

export async function createWorkspaceAnswerActionProposal(messageId: string) {
  return request<WorkspaceAnswerActionCardResult>(
    `/api/v1/workspace-answer-action-cards/${encodeURIComponent(messageId)}/create-proposal`,
    {
      method: 'POST',
    },
  );
}

export async function createWorkspaceAnswerActionTask(messageId: string) {
  return request<WorkspaceAnswerActionCardResult>(
    `/api/v1/workspace-answer-action-cards/${encodeURIComponent(messageId)}/create-task`,
    {
      method: 'POST',
    },
  );
}

export async function createWorkspaceAnswerActionEvidenceRequest(messageId: string) {
  return request<WorkspaceAnswerActionCardResult>(
    `/api/v1/workspace-answer-action-cards/${encodeURIComponent(messageId)}/request-evidence`,
    {
      method: 'POST',
    },
  );
}

export async function getGenerationRuntimeState(
  clientId: string,
  answerIntent = 'general',
  options?: { provider?: string; model?: string },
) {
  const query = new URLSearchParams();
  query.set('clientId', clientId);
  query.set('answerIntent', answerIntent);
  if (options?.provider) query.set('provider', options.provider);
  if (options?.model) query.set('model', options.model);
  return request<GenerationRuntimeState>(`/api/v1/runtime/generation-state?${query.toString()}`);
}

export async function resetGenerationRuntimeState(payload: { clientId: string; answerIntent?: string }) {
  return request<GenerationRuntimeState>('/api/v1/runtime/generation-state/reset', {
    method: 'POST',
    body: JSON.stringify({
      clientId: payload.clientId,
      answerIntent: payload.answerIntent ?? 'general',
      provider: null,
      model: null,
      resetScope: 'intent',
    }),
  });
}

export async function resetGenerationRuntimeStateV2(payload: {
  clientId: string;
  answerIntent?: string;
  provider?: string | null;
  model?: string | null;
  resetScope?: 'client' | 'intent' | 'model';
}) {
  return request<GenerationRuntimeState>('/api/v1/runtime/generation-state/reset', {
    method: 'POST',
    body: JSON.stringify({
      clientId: payload.clientId,
      answerIntent: payload.answerIntent ?? 'general',
      provider: payload.provider ?? null,
      model: payload.model ?? null,
      resetScope: payload.resetScope ?? 'intent',
    }),
  });
}

export async function runLlmHealthcheck(payload?: {
  provider?: string | null;
  model?: string | null;
  prompt?: string | null;
}) {
  return request<LlmHealthcheckResult>('/api/v1/runtime/llm-healthcheck', {
    method: 'POST',
    body: JSON.stringify({
      provider: payload?.provider ?? null,
      model: payload?.model ?? null,
      prompt: payload?.prompt ?? null,
    }),
  });
}

export async function runLlmProviderProbe(payload: {
  clientId?: string | null;
  providers?: string[];
  prompt?: string | null;
}) {
  return request<LlmProviderProbeResult>('/api/v1/runtime/llm-provider-probe', {
    method: 'POST',
    body: JSON.stringify({
      clientId: payload.clientId ?? null,
      providers: payload.providers ?? [],
      prompt: payload.prompt ?? null,
    }),
  });
}

export async function getSourceIntegrity(workspaceBackendRoot?: string, options?: {
  frontendBuildVersion?: string | null;
  frontendGitCommit?: string | null;
}) {
  const query = new URLSearchParams();
  if (workspaceBackendRoot) query.set('workspaceBackendRoot', workspaceBackendRoot);
  if (options?.frontendBuildVersion) query.set('frontendBuildVersion', options.frontendBuildVersion);
  if (options?.frontendGitCommit) query.set('frontendGitCommit', options.frontendGitCommit);
  const suffix = query.toString();
  const url = suffix ? `/api/v1/system/source-integrity?${suffix}` : '/api/v1/system/source-integrity';
  return request<SourceIntegrityReport>(url);
}

export async function getKnowledgeParseFailures(clientId: string) {
  return request<KnowledgeParseFailure[]>(`/api/v1/clients/${clientId}/knowledge/parse-failures`);
}

export async function retryKnowledgeParseFailures(clientId: string, payload?: { documentIds?: string[]; force?: boolean; ocrMaxPages?: number; ocrBatchSize?: number; ocrContinueToEnd?: boolean; forceOcr?: boolean }) {
  return request<KnowledgeParseFailureRetryResult>(`/api/v1/clients/${clientId}/knowledge/parse-failures/retry`, {
    method: 'POST',
    body: JSON.stringify({
      documentIds: payload?.documentIds ?? [],
      force: Boolean(payload?.force),
      ocrMaxPages: payload?.ocrMaxPages,
      ocrBatchSize: payload?.ocrBatchSize,
      ocrContinueToEnd: payload?.ocrContinueToEnd ?? true,
      forceOcr: Boolean(payload?.forceOcr),
    }),
  });
}

export async function getWorkspaceDataCenterReadiness(clientId: string) {
  return request<WorkspaceDataCenterReadiness>(`/api/v1/clients/${clientId}/workspace/data-center-readiness`);
}

export async function runWorkspaceDataCenterReadinessAction(
  clientId: string,
  payload: WorkspaceDataCenterReadinessActionPayload,
) {
  return request<WorkspaceDataCenterReadinessActionResult>(
    `/api/v1/clients/${clientId}/workspace/data-center-readiness/actions`,
    {
      method: 'POST',
      body: JSON.stringify({
        actionType: payload.actionType,
        targetIds: payload.targetIds ?? [],
        reason: payload.reason ?? '',
        ocrMaxPages: payload.ocrMaxPages,
        ocrBatchSize: payload.ocrBatchSize,
        ocrContinueToEnd: payload.ocrContinueToEnd ?? true,
        forceOcr: Boolean(payload.forceOcr),
      }),
    },
  );
}

export async function getWorkspaceContextRefreshEvents(
  clientId: string,
  params?: { activeOnly?: boolean; limit?: number },
) {
  const query = new URLSearchParams();
  if (params?.activeOnly) query.set('activeOnly', '1');
  if (params?.limit) query.set('limit', String(params.limit));
  const suffix = query.toString();
  const url = suffix
    ? `/api/v1/clients/${clientId}/workspace/context-refresh-events?${suffix}`
    : `/api/v1/clients/${clientId}/workspace/context-refresh-events`;
  return request<WorkspaceContextRefreshEvent[]>(url);
}

export async function enqueueWorkspaceContextRefreshEvent(
  clientId: string,
  payload: WorkspaceContextRefreshEnqueuePayload,
) {
  return request<WorkspaceContextRefreshEnqueueResult>(
    `/api/v1/clients/${clientId}/workspace/context-refresh-events`,
    {
      method: 'POST',
      body: JSON.stringify({
        sourceType: payload.sourceType,
        sourceId: payload.sourceId ?? null,
        reason: payload.reason,
        scopeType: payload.scopeType ?? 'client',
        scopeId: payload.scopeId ?? null,
        priority: payload.priority ?? 'normal',
      }),
    },
  );
}

export async function createWorkspaceProposalDraft(
  clientId: string,
  payload: WorkspaceProposalDraftCreatePayload,
) {
  return request<DataCenterProposalDraft>(`/api/v1/clients/${clientId}/workspace/proposal-drafts`, {
    method: 'POST',
    body: JSON.stringify({
      sourceMessageId: payload.sourceMessageId ?? null,
      sourceType: payload.sourceType ?? 'manual',
      actionSuggestionId: payload.actionSuggestionId ?? null,
      sourceMessageDraftId: payload.sourceMessageDraftId ?? null,
      sourceMessageDraftPayload: payload.sourceMessageDraftPayload ?? {},
      kind: payload.kind,
      title: payload.title,
      summary: payload.summary,
      rationale: payload.rationale ?? '',
      riskLevel: payload.riskLevel ?? 'medium',
      targetRefs: payload.targetRefs ?? [],
      sourceRefs: payload.sourceRefs ?? [],
      boundaryNotes: payload.boundaryNotes ?? [],
      payload: payload.payload ?? {},
      scopeType: payload.scopeType ?? 'client',
      scopeId: payload.scopeId ?? null,
    }),
  });
}

export async function getDataCenterProposalDrafts(params?: {
  scopeType?: string;
  scopeId?: string;
  clientId?: string;
  status?: string;
  kind?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.scopeType) query.set('scopeType', params.scopeType);
  if (params?.scopeId) query.set('scopeId', params.scopeId);
  if (params?.clientId) query.set('clientId', params.clientId);
  if (params?.status) query.set('status', params.status);
  if (params?.kind) query.set('kind', params.kind);
  query.set('limit', String(params?.limit ?? 60));
  return request<DataCenterProposalDraft[]>(`/api/v1/data-center/proposal-drafts?${query.toString()}`);
}

export async function markDataCenterProposalDraftReviewed(draftId: string, payload?: { note?: string }) {
  return request<DataCenterProposalDraft>(`/api/v1/data-center/proposal-drafts/${encodeURIComponent(draftId)}/mark-reviewed`, {
    method: 'POST',
    body: JSON.stringify({
      note: payload?.note ?? '',
    }),
  });
}

export async function rejectDataCenterProposalDraft(draftId: string, payload?: { reason?: string }) {
  return request<DataCenterProposalDraft>(`/api/v1/data-center/proposal-drafts/${encodeURIComponent(draftId)}/reject`, {
    method: 'POST',
    body: JSON.stringify({
      reason: payload?.reason ?? '',
    }),
  });
}

export async function promoteDataCenterProposalDraft(
  draftId: string,
  payload?: {
    createdBy?: string;
    note?: string;
    promoteTo?: 'proposal' | 'proposal_record' | 'task' | 'evidence_request' | 'meeting_prep' | 'judgment_confirmation' | 'context_refresh';
    options?: Record<string, unknown>;
  },
) {
  return request<DataCenterProposalDraftPromoteResponse>(
    `/api/v1/data-center/proposal-drafts/${encodeURIComponent(draftId)}/promote`,
    {
      method: 'POST',
      body: JSON.stringify({
        createdBy: payload?.createdBy ?? 'data_center',
        note: payload?.note ?? '',
        promoteTo: payload?.promoteTo ?? null,
        options: payload?.options ?? {},
      }),
    },
  );
}

export async function getExternalEvidenceCards(params?: {
  relatedScopeType?: string;
  relatedScopeId?: string;
  status?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.relatedScopeType) query.set('relatedScopeType', params.relatedScopeType);
  if (params?.relatedScopeId) query.set('relatedScopeId', params.relatedScopeId);
  if (params?.status) query.set('status', params.status);
  query.set('limit', String(params?.limit ?? 60));
  return request<ExternalEvidenceCard[]>(`/api/v1/external-evidence-cards?${query.toString()}`);
}

export async function createExternalEvidenceCardFromTopicCandidate(topicId: string) {
  return request<ExternalEvidenceCard>(`/api/v1/topic-candidates/${encodeURIComponent(topicId)}/external-evidence-card`, {
    method: 'POST',
  });
}

export async function acceptExternalEvidenceCard(cardId: string) {
  return request<ExternalEvidenceCard>(`/api/v1/external-evidence-cards/${encodeURIComponent(cardId)}/accept`, {
    method: 'POST',
  });
}

export async function rejectExternalEvidenceCard(cardId: string) {
  return request<ExternalEvidenceCard>(`/api/v1/external-evidence-cards/${encodeURIComponent(cardId)}/reject`, {
    method: 'POST',
  });
}

export async function createProposalDraftFromExternalEvidence(cardId: string) {
  return request<DataCenterProposalDraft>(
    `/api/v1/external-evidence-cards/${encodeURIComponent(cardId)}/create-proposal-draft`,
    {
      method: 'POST',
    },
  );
}

export async function getDataCenterEvidenceQuality(params?: {
  sourceType?: string;
  sourceId?: string;
  label?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.sourceType) query.set('sourceType', params.sourceType);
  if (params?.sourceId) query.set('sourceId', params.sourceId);
  if (params?.label) query.set('label', params.label);
  query.set('limit', String(params?.limit ?? 120));
  return request<EvidenceQualityAnnotation[]>(`/api/v1/data-center/evidence-quality?${query.toString()}`);
}

export async function labelDataCenterEvidenceQuality(
  annotationId: string,
  payload: { label: 'useful' | 'noise' | 'needs_review'; note?: string },
) {
  return request<EvidenceQualityAnnotation>(
    `/api/v1/data-center/evidence-quality/${encodeURIComponent(annotationId)}/label`,
    {
      method: 'POST',
      body: JSON.stringify({
        label: payload.label,
        note: payload.note ?? '',
      }),
    },
  );
}

export async function getMeetingPageContext(meetingId: string, prompt?: string, includeRawEvidence?: boolean) {
  const query = new URLSearchParams();
  if (prompt) query.set('prompt', prompt);
  if (typeof includeRawEvidence === 'boolean') query.set('includeRawEvidence', String(includeRawEvidence));
  const suffix = query.toString();
  const url = suffix ? `/api/v1/meetings/${meetingId}/page-context?${suffix}` : `/api/v1/meetings/${meetingId}/page-context`;
  return request<PageContextPack>(url);
}

export async function getMobileDataCenterSnapshot(clientId: string) {
  return request<MobileDataCenterSnapshotSummary>(`/api/v1/clients/${clientId}/data-center/mobile-snapshot`);
}

export async function searchClientKnowledge(clientId: string, prompt: string, threadId?: string) {
  return request<KnowledgeSearchResult>(`/api/v1/clients/${clientId}/knowledge/search`, {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId }),
  });
}

export async function rebuildClientKnowledge(clientId: string) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/knowledge/rebuild`, {
    method: 'POST',
  });
}

export async function generateClientDnaCandidates(clientId: string, payload?: { refreshGenerated?: boolean }) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/dna-documents/generate`, {
    method: 'POST',
    body: JSON.stringify({ refreshGenerated: payload?.refreshGenerated ?? false }),
  });
}

export async function importPaths(clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) {
  return request<ImportRecord[]>('/api/v1/imports', {
    method: 'POST',
    body: JSON.stringify({ clientId, mode, paths, allowLegacy: options?.allowLegacy ?? false }),
  });
}

export async function getDocumentReadingPreview(clientId: string, documentId: string) {
  return request<DocumentReadingPreview>(`/api/v1/clients/${clientId}/documents/${documentId}/reading-preview`);
}

export async function startClientMessage(
  clientId: string,
  prompt: string,
  threadId?: string,
  searchId?: string,
  workingDocumentIdsOrOptions?: string[] | RequestInit,
  options?: RequestInit,
) {
  const workingDocumentIds = Array.isArray(workingDocumentIdsOrOptions) ? workingDocumentIdsOrOptions : [];
  const requestOptions = Array.isArray(workingDocumentIdsOrOptions) ? options : workingDocumentIdsOrOptions;
  return request<ChatStartResponse>(`/api/v1/clients/${clientId}/workspace/chat/start`, {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId, searchId, workingDocumentIds: workingDocumentIds || [] }),
    ...requestOptions,
  });
}

export async function getClientMessage(clientId: string, messageId: string) {
  return request<ChatMessage>(`/api/v1/clients/${clientId}/workspace/chat/messages/${messageId}`);
}

export async function getClientChatThread(clientId: string, threadId: string) {
  return request<ChatThreadDetailResponse>(`/api/v1/clients/${clientId}/workspace/chat/threads/${threadId}`);
}

export async function deleteClientChatMessagePair(clientId: string, messageId: string) {
  return request<{ clientId: string; threadId: string; deletedIds: string[]; threadDeleted: boolean }>(
    `/api/v1/clients/${clientId}/workspace/chat/messages/${messageId}`,
    { method: 'DELETE' },
  );
}

export async function getClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(`/api/v1/clients/${clientId}/analysis-runs/${runId}`);
}

export async function cancelClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(`/api/v1/clients/${clientId}/analysis-runs/${runId}/cancel`, {
    method: 'POST',
  });
}

export async function vectorizeAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/knowledge/vectorize-answer`, {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function exportAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/knowledge/export-answer`, {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function createClientTextDocument(clientId: string, payload: { title?: string | null; content: string }) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/documents/from-text`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function startClientLinkMaterialImport(
  clientId: string,
  url: string,
  options: { useBrowserCookies?: boolean; cookieBrowser?: 'firefox' | 'chrome' | 'edge' | 'safari' } = {},
) {
  return request<LinkMaterialImportRun>(`/api/v1/clients/${clientId}/link-materials/import/start`, {
    method: 'POST',
    body: JSON.stringify({
      url,
      useBrowserCookies: Boolean(options.useBrowserCookies),
      cookieBrowser: options.cookieBrowser || 'firefox',
    }),
  });
}

export async function getLatestClientLinkMaterialImportRun(clientId: string) {
  return request<LinkMaterialImportRun | null>(`/api/v1/clients/${clientId}/link-materials/import-runs/latest`);
}

export async function getClientLinkMaterialImportRun(clientId: string, runId: string) {
  return request<LinkMaterialImportRun>(`/api/v1/clients/${clientId}/link-materials/import-runs/${runId}`);
}

export async function startClientTemplateFill(clientId: string, templatePath: string) {
  return request<ClientTemplateFillRun>(`/api/v1/clients/${clientId}/documents/fill-template/start`, {
    method: 'POST',
    body: JSON.stringify({ templatePath }),
  });
}

export async function getClientTemplateFillRun(clientId: string, runId: string) {
  return request<ClientTemplateFillRun>(`/api/v1/clients/${clientId}/template-fill-runs/${runId}`);
}

export async function backfillClientWorkspaceImports(clientId: string) {
  return request<WorkspaceImportBackfillResponse>(`/api/v1/clients/${clientId}/workspace/backfill-imports`, {
    method: 'POST',
  });
}

export async function createMeeting(clientId: string, title: string, scheduledAt?: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings`, {
    method: 'POST',
    body: JSON.stringify({ title, scheduledAt }),
  });
}

export async function getStrategicCockpit(clientId: string) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit`);
}

export async function confirmStrategicCockpit(clientId: string, payload: StrategicCockpitConfirmPayload) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createStrategicMeetingPack(clientId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/strategic-cockpit/meeting-pack`, {
    method: 'POST',
  });
}

export async function applyStrategicMeetingPack(clientId: string, meetingId: string) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit/meeting-pack/${meetingId}/apply`, {
    method: 'POST',
  });
}

export async function getStrategicThoughts(params?: {
  clientId?: string | null;
  projectModuleId?: string | null;
  includeDismissed?: boolean;
  includeDeleted?: boolean;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.clientId) searchParams.set('clientId', params.clientId);
  if (params?.projectModuleId) searchParams.set('projectModuleId', params.projectModuleId);
  if (params?.includeDismissed) searchParams.set('includeDismissed', 'true');
  if (params?.includeDeleted) searchParams.set('includeDeleted', 'true');
  if (typeof params?.limit === 'number') searchParams.set('limit', String(params.limit));
  const query = searchParams.toString();
  return request<StrategicThoughtsResponse>(`/api/v1/strategic/thoughts${query ? `?${query}` : ''}`);
}

export async function refreshStrategicThoughts(payload: StrategicThoughtRefreshPayload) {
  return request<StrategicThoughtsResponse>('/api/v1/strategic/thoughts/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateStrategicThoughtState(thoughtId: string, payload: StrategicThoughtStatePayload) {
  return request<StrategicThought>(`/api/v1/strategic/thoughts/${encodeURIComponent(thoughtId)}/state`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function reviewStrategicThought(thoughtId: string, payload: StrategicThoughtReviewPayload) {
  return request<StrategicThought | StrategicThoughtReview>(`/api/v1/strategic/thoughts/${encodeURIComponent(thoughtId)}/review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createClientFolder(clientId: string, label: string) {
  return request<ClientFolder>(`/api/v1/clients/${clientId}/folders`, {
    method: 'POST',
    body: JSON.stringify({ label }),
  });
}

export async function renameClientFolder(clientId: string, folderId: string, label: string) {
  return request<ClientFolder>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify({ label }),
  });
}

export async function updateClientFolder(clientId: string, folderId: string, payload: { label?: string; isHidden?: boolean; sortOrder?: number }) {
  return request<ClientFolder>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function moveClientDocumentToFolder(clientId: string, documentId: string, payload: { folderId?: string | null; folderLabel?: string | null }) {
  return request<DocumentRecord>(`/api/v1/clients/${clientId}/documents/${documentId}/move-folder`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function recommendClientFolder(
  clientId: string,
  payload: { documentId?: string; title?: string; fileName?: string; contentPreview?: string; sourceType?: string },
) {
  return request<ClientFolderRecommendation>(`/api/v1/clients/${clientId}/folders/recommend`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function recommendClientFolderPlan(clientId: string) {
  return request<ClientFolderRecommendationPlan>(`/api/v1/clients/${clientId}/folders/recommend`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function applyClientFolderRecommendation(clientId: string, payload?: { targetFolderLabels?: string[] }) {
  return request<ClientWorkspace>(`/api/v1/clients/${clientId}/folders/apply-recommendation`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function previewClientDocumentAutoRepair(clientId: string, payload?: DocumentAutoRepairPreviewPayload) {
  return request<DocumentAutoRepairPreview>(`/api/v1/clients/${clientId}/documents/auto-repair/preview`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function applyClientDocumentAutoRepair(clientId: string, payload?: DocumentAutoRepairApplyPayload) {
  return request<DocumentAutoRepairApplyResult>(`/api/v1/clients/${clientId}/documents/auto-repair/apply`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function launchFeishuMeeting(clientId: string, payload: { title: string; scheduledAt?: string; sourceTaskId?: string | null }) {
  return request<FeishuMeetingLaunchResult>(`/api/v1/clients/${clientId}/meetings/launch-feishu`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function ingestMeeting(clientId: string, meetingId: string, transcriptText: string, notes: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/ingest`, {
    method: 'POST',
    body: JSON.stringify({ transcriptText, notes }),
  });
}

export async function extractMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/extract`, {
    method: 'POST',
  });
}

export async function resolveMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/resolve`, {
    method: 'POST',
  });
}

export async function publishMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/publish`, {
    method: 'POST',
  });
}

export async function createMeetingPrepareProposal(clientId: string, meetingId: string) {
  return request<ProposalRecord>(`/api/v1/clients/${clientId}/meetings/${meetingId}/proposals/prepare`, {
    method: 'POST',
  });
}

export async function createMeetingFollowupProposal(clientId: string, meetingId: string) {
  return request<ProposalRecord>(`/api/v1/clients/${clientId}/meetings/${meetingId}/proposals/follow-up`, {
    method: 'POST',
  });
}

export async function getProposals(options?: { status?: string; clientId?: string; kind?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (options?.status) params.set('status', options.status);
  if (options?.clientId) params.set('clientId', options.clientId);
  if (options?.kind) params.set('kind', options.kind);
  if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
  const query = params.toString();
  return request<ProposalRecord[]>(`/api/v1/proposals${query ? `?${query}` : ''}`);
}

export async function getProposal(proposalId: string) {
  return request<ProposalRecord>(`/api/v1/proposals/${encodeURIComponent(proposalId)}`);
}

export async function approveProposal(
  proposalId: string,
  payload: ProposalApprovalPayload = {},
) {
  const decidedBy = payload.decidedBy?.trim() || 'user';
  const note = (payload.note ?? payload.comment ?? '').trim();
  return request<ProposalRecord>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ decidedBy, note }),
  });
}

export async function rejectProposal(
  proposalId: string,
  payload: ProposalApprovalPayload = {},
) {
  const decidedBy = payload.decidedBy?.trim() || 'user';
  const note = (payload.note ?? payload.comment ?? '').trim();
  return request<ProposalRecord>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ decidedBy, note }),
  });
}

export async function getProposalExecutionPreview(proposalId: string) {
  return request<ProposalExecutionPreview>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/execution-preview`);
}

export async function createProposalExecutionTicket(
  proposalId: string,
  payload: ProposalExecutionPayload = {},
) {
  return request<ProposalExecutionResult>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/execution-ticket`, {
    method: 'POST',
    body: JSON.stringify({
      requestedBy: payload.requestedBy ?? 'user',
      dryRun: Boolean(payload.dryRun),
    }),
  });
}

export async function getExecutionTickets(params?: { clientId?: string; status?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  if (params?.status) query.set('status', params.status);
  query.set('limit', String(params?.limit ?? 60));
  return request<ExecutionTicket[]>(`/api/v1/execution-tickets?${query.toString()}`);
}

export async function executeExecutionTicket(ticketId: string, payload: ProposalExecutionPayload = {}) {
  return request<ProposalExecutionResponse>(`/api/v1/execution-tickets/${encodeURIComponent(ticketId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({
      requestedBy: payload.requestedBy ?? 'user',
      dryRun: Boolean(payload.dryRun),
    }),
  });
}

export async function retryExecutionTicket(ticketId: string, payload: ProposalExecutionPayload = {}) {
  return request<ProposalExecutionResponse>(`/api/v1/execution-tickets/${encodeURIComponent(ticketId)}/retry`, {
    method: 'POST',
    body: JSON.stringify({
      requestedBy: payload.requestedBy ?? 'user',
      dryRun: Boolean(payload.dryRun),
    }),
  });
}

export async function getExecutionTicketLogs(ticketId: string, limit = 200) {
  return request<ExecutionTicketLog[]>(
    `/api/v1/execution-tickets/${encodeURIComponent(ticketId)}/logs?limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function batchApproveProposals(payload: ProposalBatchActionPayload) {
  return request<ProposalBatchResult>('/api/v1/proposals/batch-approve', {
    method: 'POST',
    body: JSON.stringify({
      proposalIds: payload.proposalIds ?? [],
      decidedBy: payload.decidedBy ?? 'user',
      note: payload.note ?? '',
    }),
  });
}

export async function batchRejectProposals(payload: ProposalBatchActionPayload) {
  return request<ProposalBatchResult>('/api/v1/proposals/batch-reject', {
    method: 'POST',
    body: JSON.stringify({
      proposalIds: payload.proposalIds ?? [],
      decidedBy: payload.decidedBy ?? 'user',
      note: payload.note ?? '',
    }),
  });
}

export async function startKernelPrimaryRollout(payload: KernelPrimaryRolloutStartPayload) {
  return request<KernelPrimaryRolloutRun>('/api/v1/data-center/kernel-primary-rollout/start', {
    method: 'POST',
    body: JSON.stringify({
      stage: payload.stage,
      clientIds: payload.clientIds ?? [],
      note: payload.note ?? '',
    }),
  });
}

export async function completeKernelPrimaryRollout(runId: string) {
  return request<KernelPrimaryRolloutRun>(`/api/v1/data-center/kernel-primary-rollout/${encodeURIComponent(runId)}/complete`, {
    method: 'POST',
  });
}

export async function rollbackKernelPrimaryRollout(runId: string, payload: KernelPrimaryRolloutRollbackPayload = {}) {
  return request<KernelPrimaryRolloutRun>(`/api/v1/data-center/kernel-primary-rollout/${encodeURIComponent(runId)}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ reason: payload.reason ?? '' }),
  });
}

export async function listKernelPrimaryRollouts(limit = 40) {
  return request<KernelPrimaryRolloutRun[]>(
    `/api/v1/data-center/kernel-primary-rollout?limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function getExecutionRetryMetrics(params?: { clientId?: string; days?: number }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  query.set('days', String(params?.days ?? 7));
  return request<ExecutionRetryMetrics>(`/api/v1/data-center/execution-retry-metrics?${query.toString()}`);
}

export async function createEvidenceQualitySnapshot(days = 7) {
  return request<EvidenceQualityFeedbackSnapshot>('/api/v1/data-center/evidence-quality/snapshots', {
    method: 'POST',
    body: JSON.stringify({ days }),
  });
}

export async function listEvidenceQualitySnapshots(limit = 30) {
  return request<EvidenceQualityFeedbackSnapshot[]>(
    `/api/v1/data-center/evidence-quality/snapshots?limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function runDataCenterRollbackDrill(payload: RollbackDrillPayload) {
  return request<RollbackDrillResult>('/api/v1/data-center/rollback-drill', {
    method: 'POST',
    body: JSON.stringify({
      clientIds: payload.clientIds ?? [],
      dryRun: payload.dryRun ?? true,
    }),
  });
}

export async function getDataCenterOperationalStatus(params?: { clientId?: string }) {
  const query = new URLSearchParams();
  if (params?.clientId) query.set('clientId', params.clientId);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<DataCenterOperationalStatus>(`/api/v1/data-center/operational-status${suffix}`);
}

export async function getDataCenterArtifactStatus() {
  return request<DataCenterArtifactStatus>('/api/v1/data-center/artifact-status');
}

export async function getDataCenterSchemaStatus() {
  return request<DataCenterSchemaStatus>('/api/v1/data-center/schema/status');
}

export async function ensureDataCenterSchema() {
  return request<DataCenterSchemaStatus>('/api/v1/data-center/schema/ensure', {
    method: 'POST',
  });
}

export async function executeProposal(proposalId: string, payload: ProposalApprovalPayload = {}) {
  const comment = (payload.note ?? payload.comment ?? '').trim();
  return request<ProposalExecutionResponse>(`/api/v1/proposals/${encodeURIComponent(proposalId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function createGoal(clientId: string, payload: { title: string; quarter: string; progress: number; ownerName: string }) {
  return request<GoalRecord>(`/api/v1/clients/${clientId}/goals`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function upsertDna(clientId: string, payload: { category: string; canonicalName: string; aliases: string[]; description: string }) {
  return request<DnaTerm>(`/api/v1/clients/${clientId}/dna`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTaskBoard() {
  return request<{ tasks: Task[]; lists: TaskList[]; tags: TaskTag[] }>('/api/v1/tasks');
}

export async function createSupportRequest(payload: SupportRequestCreatePayload) {
  return request<SupportRequestRecord>('/api/v1/support-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSupportRequests(params?: { status?: string; taskId?: string }) {
  const search = new URLSearchParams();
  if (params?.status) search.set('status', params.status);
  if (params?.taskId) search.set('taskId', params.taskId);
  const suffix = search.size > 0 ? `?${search.toString()}` : '';
  return request<SupportRequestRecord[]>(`/api/v1/support-requests${suffix}`);
}

export async function resolveSupportRequest(id: string, payload: SupportRequestResolvePayload) {
  return request<SupportRequestRecord>(`/api/v1/support-requests/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAgentWorklogs(month?: string) {
  const suffix = month ? `?month=${encodeURIComponent(month)}` : '';
  return request<AgentWorklogResponse>(`/api/v1/tasks/agent-worklogs${suffix}`);
}

export async function updateAgentWeeklyPlan(weekLabel: string, agentKey: string, payload: AgentWeeklyPlanPayload) {
  return request<AgentWeeklyPlan>(`/api/v1/tasks/agent-weekly-plans/${encodeURIComponent(weekLabel)}/${encodeURIComponent(agentKey)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getAgentExecutionTasks(weekLabel: string, departmentName?: string) {
  const params = new URLSearchParams({ week: weekLabel });
  if (departmentName?.trim()) {
    params.set('department', departmentName.trim());
  }
  return request<Task[]>(`/api/v1/tasks/agent-execution?${params.toString()}`);
}

export async function createTaskList(payload: TaskListMutationPayload) {
  return request<TaskList>('/api/v1/task-lists', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTaskList(id: string, payload: TaskListMutationPayload) {
  return request<TaskList>(`/api/v1/task-lists/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskList(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/task-lists/${id}`, {
    method: 'DELETE',
  });
}

export async function createTaskTag(payload: TaskTagMutationPayload) {
  return request<TaskTag>('/api/v1/task-tags', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTaskTag(id: string, payload: TaskTagMutationPayload) {
  return request<TaskTag>(`/api/v1/task-tags/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskTag(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/task-tags/${id}`, {
    method: 'DELETE',
  });
}

export async function createTask(payload: TaskMutationPayload) {
  return request<Task>('/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTask(id: string, payload: Partial<TaskMutationPayload> & { status?: string }) {
  return request<Task>(`/api/v1/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTask(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/tasks/${id}`, {
    method: 'DELETE',
  });
}

export async function uploadTaskAttachment(
  taskId: string,
  payload: {
    file: File;
    clientId?: string | null;
    eventLineId?: string | null;
    taskTitle?: string | null;
    onProgress?: (loaded: number, total: number) => void;
  },
) {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.clientId) formData.append('clientId', payload.clientId);
  if (payload.eventLineId) formData.append('eventLineId', payload.eventLineId);
  if (payload.taskTitle) formData.append('taskTitle', payload.taskTitle);
  return requestForm<Task>(`/api/v1/tasks/${taskId}/attachments`, formData, {
    method: 'POST',
    onProgress: payload.onProgress,
  });
}

export async function getEventLines() {
  return request<EventLine[]>('/api/v1/event-lines');
}

export async function createEventLine(payload: EventLineMutationPayload) {
  return request<EventLine>('/api/v1/event-lines', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getEventLine(id: string) {
  return request<EventLineDetail>(`/api/v1/event-lines/${id}`);
}

export async function getEventLineReportSnapshot(id: string) {
  return request<EventLineReportSnapshot>(`/api/v1/event-lines/${id}/report-snapshot`);
}

export async function updateEventLine(id: string, payload: Partial<EventLineMutationPayload>) {
  return request<EventLine>(`/api/v1/event-lines/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function closeEventLine(id: string) {
  return request<{ status: string }>(`/api/v1/event-lines/${id}/close`, {
    method: 'POST',
  });
}

export async function reopenEventLine(id: string) {
  return request<{ status: string }>(`/api/v1/event-lines/${id}/reopen`, {
    method: 'POST',
  });
}

export async function deleteEventLine(id: string) {
  return request<{ status: string; counts?: Record<string, number> }>(`/api/v1/event-lines/${id}`, {
    method: 'DELETE',
  });
}

export async function retryEventLineSync(id: string) {
  return request<{ status: string; syncStatus: string | null; lastSyncError: string | null }>(
    `/api/v1/event-lines/${id}/retry-sync`,
    { method: 'POST' },
  );
}

export async function addEventLineNote(id: string, text: string) {
  return request<{ id: string; eventLineId: string; text: string; createdAt: string }>(`/api/v1/event-lines/${id}/notes`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function generateEventLineClarificationDraft(
  id: string,
  payload: EventLineClarificationDraftPayload,
) {
  return request<EventLineClarificationDraftResult>(`/api/v1/event-lines/${id}/clarification-draft`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function confirmTask(id: string) {
  return request<Task>(`/api/v1/tasks/${id}/confirm`, { method: 'POST' });
}

export async function rejectTask(id: string, reason: string) {
  return request<Task>(`/api/v1/tasks/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function approveTaskReview(id: string) {
  return request<Task>(`/api/v1/tasks/${id}/review/approve`, { method: 'POST' });
}

export async function returnTaskReview(id: string, reason: string) {
  return request<Task>(`/api/v1/tasks/${id}/review/return`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function saveTaskNote(id: string, note: string) {
  return request<Task>(`/api/v1/tasks/${id}/note`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export async function completeTaskWithReview(id: string, reviewNote: string) {
  return request<Task>(`/api/v1/tasks/${id}/complete-with-review`, {
    method: 'POST',
    body: JSON.stringify({ reviewNote }),
  });
}

export async function getTaskViews() {
  return request<TaskViewsResponse>('/api/v1/task-views');
}

export async function getTaskTagSuggestions(payload: TaskTagSuggestionPayload) {
  return request<{ suggestedTags: string[] }>('/api/v1/local/tasks/tag-suggestions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getReviews(weekLabel?: string, options?: { skipAi?: boolean; perspective?: ReviewPerspectiveKey; departmentId?: string | null; signal?: AbortSignal }) {
  const search = new URLSearchParams();
  if (weekLabel) search.set('weekLabel', weekLabel);
  if (options?.skipAi) search.set('skipAi', '1');
  if (options?.perspective) search.set('perspective', options.perspective);
  if (options?.departmentId) search.set('departmentId', options.departmentId);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<ReviewDashboard>(`/api/v1/reviews${suffix}`, { signal: options?.signal });
}

export async function refreshWeeklyOverview(payload: WeeklyOverviewRefreshPayload) {
  return request<WeeklyOverviewRefreshStatus>('/api/v1/reviews/weekly-overview/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getWeeklyOverviewRefreshStatus(params: {
  weekLabel?: string | null;
  perspective?: ReviewPerspectiveKey | null;
  departmentId?: string | null;
}) {
  const search = new URLSearchParams();
  if (params.weekLabel) search.set('weekLabel', params.weekLabel);
  if (params.perspective) search.set('perspective', params.perspective);
  if (params.departmentId) search.set('departmentId', params.departmentId);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<WeeklyOverviewRefreshStatus>(`/api/v1/reviews/weekly-overview/status${suffix}`);
}

export async function getReviewDashboardDrillTarget(params: {
  targetType: string;
  targetId: string;
  targetLabel?: string;
  targetFilters?: Record<string, unknown>;
}) {
  const search = new URLSearchParams({
    targetType: params.targetType,
    targetId: params.targetId,
  });
  if (params.targetLabel?.trim()) {
    search.set('targetLabel', params.targetLabel.trim());
  }
  if (params.targetFilters && Object.keys(params.targetFilters).length > 0) {
    search.set('targetFilters', JSON.stringify(params.targetFilters));
  }
  return request<ReviewDashboardDrillTargetResponse>(`/api/v1/reviews/dashboard/drill-target?${search.toString()}`);
}

export async function getReviewHistory() {
  return request<ReviewHistoryResponse>('/api/v1/reviews/history');
}

export async function createWeeklyReview(payload: WeeklyReviewPayload) {
  return request<ReviewDashboard>('/api/v1/reviews/weekly', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createWeeklyReviewDraft(payload: WeeklyReviewPayload) {
  return request<ReviewDashboard>('/api/v1/reviews/weekly/draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTopics() {
  return request<{ radars: TopicRadar[]; candidates: TopicCandidate[]; intelligenceProfiles?: IntelligenceProfile[] }>('/api/v1/topics');
}

export async function captureTopicRadars() {
  return request<TopicCaptureBatchResult>('/api/v1/topics/capture', {
    method: 'POST',
  });
}

export async function captureIntelligenceRadarTest(id: string) {
  return request<{
    radarId: string;
    radarTitle: string;
    query: string;
    fetchedCount: number;
    createdCount: number;
    skippedCount: number;
    candidates: TopicCandidate[];
  }>(`/api/v1/topics/radars/${id}/capture`, {
    method: 'POST',
  });
}

export async function createRadar(payload: TopicRadarPayload) {
  return request<TopicRadar>('/api/v1/topics/radars', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateRadar(id: string, payload: TopicRadarPayload) {
  return request<TopicRadar>(`/api/v1/topics/radars/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteRadar(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/topics/radars/${id}`, { method: 'DELETE' });
}

export async function suggestRadarTitle(prompt: string) {
  return request<{ title: string }>('/api/v1/topics/radars/generate-title', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

export async function assistRadarDraft(prompt: string, timeRange: string) {
  return request<{ title: string; prompt: string; queries: string[] }>('/api/v1/topics/radars/assist', {
    method: 'POST',
    body: JSON.stringify({ prompt, timeRange }),
  });
}

export async function suggestRadarSourceLabel(url: string) {
  return request<{ url: string; label: string }>('/api/v1/topics/radars/source-label', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function getCandidateInsights(id: string) {
  return request<TopicCandidateInsight>(`/api/v1/topics/candidates/${id}/insights`, { method: 'POST' });
}

export async function askCandidateQuestion(id: string, payload: TopicCandidateChatPayload) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 25000);
  try {
    return await request<TopicCandidateChatResponse>(`/api/v1/topics/candidates/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (/abort|aborted|signal is aborted/i.test(detail)) {
      throw new Error('大周这次追问超时了。可以直接再问一次，或者把问题问得更具体一点。');
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getCandidateTaskPlan(id: string) {
  return request<TopicTaskPlanResult>(`/api/v1/topics/candidates/${id}/task-plan`, { method: 'POST' });
}

export async function promoteCandidateTasks(id: string, tasks: TopicTaskPromotionDraft[]) {
  return request<TopicTaskPromotionResult>(`/api/v1/topics/candidates/${id}/promote-tasks`, {
    method: 'POST',
    body: JSON.stringify({ tasks }),
  });
}

export async function deleteCandidate(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/topics/candidates/${id}`, { method: 'DELETE' });
}

export async function favoriteIntelligenceItem(
  candidateId: string,
  payload: { userId: string; note?: string; tags?: string[] },
) {
  return { candidateId, ...payload, saved: true };
}

export async function unfavoriteIntelligenceItem(candidateId: string, userId: string) {
  return { candidateId, userId, saved: false };
}

export async function shareIntelligenceItem(
  candidateId: string,
  payload: {
    sharedBy: string;
    sharedByName?: string;
    sharedTo: string[];
    sharedToRecipients?: Array<{ userId: string; fullName?: string; email?: string | null }>;
    reason?: string;
  },
) {
  return { candidateId, ...payload, shared: true };
}

export async function runDueIntelligenceProfiles(_options?: { limit?: number }) {
  try {
    return await request<{ triggeredCount?: number; refreshedCount?: number; fetchedCount?: number; results?: unknown[] }>('/api/v1/intelligence/profiles/run-due', {
      method: 'POST',
    });
  } catch {
    return { triggeredCount: 0, refreshedCount: 0, fetchedCount: 0, results: [] };
  }
}

export async function refreshIntelligenceProfile(id: string, payload?: Record<string, unknown>) {
  return request<unknown>(`/api/v1/intelligence/profiles/${id}/refresh`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function trialRunIntelligenceProfile(id: string) {
  return request<{ createdCount: number; failureReason?: string; error?: string }>(`/api/v1/intelligence/profiles/${id}/trial-run`, {
    method: 'POST',
  });
}

export async function updateIntelligenceProfile(id: string, payload: unknown) {
  return request<unknown>(`/api/v1/intelligence/profiles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisTools() {
  return request<{ templates: AnalysisTemplate[]; runs: AnalysisRun[] }>('/api/v1/analysis-tools');
}

export async function runAnalysis(payload: AnalysisRunPayload) {
  return request<AnalysisRun>('/api/v1/analysis-tools/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingDeepDnaLibrary() {
  return request<DeepDnaRecord[]>('/api/v1/analysis-tools/fundraising/dna');
}

export async function upsertFundraisingDeepDna(payload: DeepDnaRecord) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createFundraisingManualDna(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  identitySummary: string;
  corePreferencesText: string;
  supportTriggersText: string;
  redFlagsText: string;
  evidencePreferencesText: string;
  voiceStyleText: string;
  commonQuestionsText: string;
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
}) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna/manual', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function importFundraisingDna(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  fileName: string;
  filePath: string;
  content: string;
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
}) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createFundraisingWebDnaDraft(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  searchQuery: string;
}) {
  return request<DeepDnaDraft>('/api/v1/analysis-tools/fundraising/dna/web-drafts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function publishFundraisingDna(id: string) {
  return request<DeepDnaRecord>(`/api/v1/analysis-tools/fundraising/dna/${encodeURIComponent(id)}/publish`, {
    method: 'POST',
  });
}

export async function getFundraisingCases() {
  return request<CoachCaseRecord[]>('/api/v1/analysis-tools/fundraising/cases');
}

export async function upsertFundraisingCase(payload: CoachCaseRecord) {
  return request<CoachCaseRecord>('/api/v1/analysis-tools/fundraising/cases', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingReminderRules() {
  return request<CoachReminderRule[]>('/api/v1/analysis-tools/fundraising/reminders');
}

export async function upsertFundraisingReminderRule(payload: CoachReminderRule) {
  return request<CoachReminderRule>('/api/v1/analysis-tools/fundraising/reminders', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingWritingNorms() {
  return request<OrgWritingNorm[]>('/api/v1/analysis-tools/fundraising/norms');
}

export async function upsertFundraisingWritingNorm(payload: OrgWritingNorm) {
  return request<OrgWritingNorm>('/api/v1/analysis-tools/fundraising/norms', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingRunComparison(runId: string) {
  return request<RunComparison>(`/api/v1/analysis-tools/fundraising/runs/${encodeURIComponent(runId)}/comparison`);
}

export async function getHandbook() {
  return request<{ entries: HandbookEntry[] }>('/api/v1/handbook');
}

export async function getHandbookEntry(id: string) {
  return request<HandbookEntryDetail>(`/api/v1/handbook/${encodeURIComponent(id)}`);
}

export async function createHandbook(payload: HandbookEntryPayload) {
  return request<HandbookEntry>('/api/v1/handbook', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getGrowthOverview(weekLabel?: string) {
  const search = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : '';
  return request<GrowthOverview>(`/api/v1/growth/overview${search}`);
}

export async function getGrowthWorkbench(params?: {
  weekLabel?: string;
  clientId?: string | null;
  mode?: 'global' | 'strategic';
}) {
  const search = new URLSearchParams();
  if (params?.weekLabel) search.set('weekLabel', params.weekLabel);
  if (params?.clientId) search.set('clientId', params.clientId);
  if (params?.mode) search.set('mode', params.mode);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<GrowthWorkbenchSnapshot>(`/api/v1/growth/workbench${suffix}`);
}

export async function getGrowthBadges() {
  return request<BadgeBoard>('/api/v1/growth/badges');
}

export async function getGrowthLedger(params?: { abilityKey?: string; weekLabel?: string }) {
  const search = new URLSearchParams();
  if (params?.abilityKey) search.set('abilityKey', params.abilityKey);
  if (params?.weekLabel) search.set('weekLabel', params.weekLabel);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<GrowthLedgerResponse>(`/api/v1/growth/ledger${suffix}`);
}

export async function acceptGrowthRecommendation(id: string) {
  return request<GrowthRecommendationActionResponse>(`/api/v1/growth/recommendations/${id}/accept`, {
    method: 'POST',
  });
}

export async function dismissGrowthRecommendation(id: string, payload: GrowthRecommendationDismissPayload = {}) {
  return request<GrowthRecommendationActionResponse>(`/api/v1/growth/recommendations/${id}/dismiss`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function markHandbookEntryReused(id: string, payload: GrowthValidationPayload = {}) {
  return request<GrowthValidationActionResponse>(`/api/v1/growth/handbook/${id}/mark-reused`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateGrowthPendingCapture(id: string, payload: GrowthPendingCaptureActionPayload) {
  return request<GrowthPendingCaptureActionResponse>(`/api/v1/growth/pending-captures/${id}/state`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function selectCollabRepo() {
  return window.yiyuWorkbench.selectCollabRepo() as Promise<string | null>;
}

export async function getCollabRepoStatus(repoPath?: string | null) {
  return window.yiyuWorkbench.getCollabRepoStatus(repoPath) as Promise<CollabRepoStatus>;
}

export async function previewPushToMain(repoPath: string) {
  return window.yiyuWorkbench.previewPushToMain(repoPath) as Promise<PushPreview>;
}

export async function commitAndPushToMain(payload: CommitAndPushToMainPayload) {
  return window.yiyuWorkbench.commitAndPushToMain(payload) as Promise<CollabActionResult>;
}

export async function previewPullFromMain(repoPath: string, targetCommit?: string | null) {
  return window.yiyuWorkbench.previewPullFromMain(repoPath, targetCommit ?? null) as Promise<PullPreview>;
}

export async function pullSelectedFromMain(payload: PullSelectedFromMainPayload) {
  return window.yiyuWorkbench.pullSelectedFromMain(payload) as Promise<CollabActionResult>;
}

export async function rebuildAndInstallFromRepo(repoPath: string) {
  return window.yiyuWorkbench.rebuildAndInstallFromRepo(repoPath) as Promise<boolean>;
}

export async function setWorkspaceInteractionState(payload: { active: boolean; source: string; detail?: string | null }) {
  return window.yiyuWorkbench.setWorkspaceInteractionState(payload);
}
