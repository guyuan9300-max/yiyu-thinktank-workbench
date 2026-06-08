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
  LocalAuthLoginPayload,
  LocalAuthRegisterPayload,
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
  OrgAdminClaimStatus,
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
  FeishuDocumentSyncPayload,
  FeishuMemberAuthorization,
  FeishuMemberAuthorizationStartResult,
  FeishuSyncStatusRecord,
  FeishuTaskCalendarSyncPayload,
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
  LocalAsrDownloadCancelResponse,
  LocalAsrDownloadStartResponse,
  LocalAsrModelStatus,
  LocalAsrTestTranscriptionResponse,
  OllamaDeleteModelResponse,
  OllamaHealthResponse,
  OllamaPullCancelResponse,
  OllamaPullStartResponse,
  OllamaPullStatusResponse,
  OllamaRecommendedModelsResponse,
  ObjectStorageSettings,
  ObjectStorageSettingsPayload,
  ObjectStorageTestResult,
  SpeechModelSettings,
  SpeechModelSettingsPayload,
  SpeechModelTestResult,
  TaskList,
  TaskPlanLinkRecord,
  TaskPlanLinkUpsertPayload,
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
  DepartmentSignalsResponse,
  WeeklyOverviewRefreshPayload,
  WeeklyOverviewRefreshStatus,
  ReviewHistoryResponse,
  JudgmentConfirmPayload,
  JudgmentVersion,
  ConflictGroup,
  Entity,
  EntityListResponse,
  EntityMergeCandidate,
  EntityMergeCandidatesResponse,
  EntityMergeResult,
  GlossaryEntry,
  GlossaryListResponse,
  FactContradiction,
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
  EventLineTimelineNarrative,
  // 客户项目情报流类型（2026-05-13 整合同事新版资讯情报站时补回）
  IntelligenceWorkObject,
  IntelligenceItem,
  IntelligenceSourceDiagnosticsResponse,
  IntelligenceFocusDirective,
  IntelligenceFocusDirectivePayload,
  IntelligenceRefreshCycleSettings,
  IntelligenceRefreshCycleSettingsPayload,
  IntelligenceItemsResponse,
  IntelligenceRefreshPayload,
  IntelligenceRefreshResult,
  IntelligenceRefreshRun,
  IntelligenceVerificationRule,
  IntelligenceVerificationRulePayload,
  IntelligenceVerificationFeedbackPayload,
  IntelligenceDismissPayload,
  IntelligenceFollowPayload,
  IntelligenceTaskDraftResponse,
  IntelligenceTaskCreatePayload,
  IntelligenceTaskCreateResponse,
  IntelligenceItemChatResponse,
  IntelligenceContentKind,
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
    setMiniMode: async () => ({ mini: false }),
    setUpdateOrgIdentity: async () => ({ ok: false, reason: 'browser preview' }),
    setUpdateOrgCode: async () => ({ ok: false, reason: 'browser preview' }),
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
    saveRecordingBlob: async () => notAvailable('保存录音文件'),
    readRecordingFile: async () => notAvailable('读取录音文件'),
    setRecordingActive: async () => ({ active: false }),
    setBackgroundTasks: async () => ({ ok: true, count: 0 }),
  };
}

if (typeof window !== 'undefined' && !window.yiyuWorkbench) {
  window.yiyuWorkbench = createBrowserWorkbenchFallback();
}

const baseUrl = window.yiyuWorkbench.backendBaseUrl;

/**
 * 统一 retry 策略：
 *   - 网络层错误（"Failed to fetch" / "Load failed"，覆盖 backend 进程死掉 / reload 切换）
 *     → GET 最多 retry 8 次，POST/其他最多 retry 2 次（写操作避免重复）
 *   - HTTP 5xx → 不论 method 都 retry 3 次（5xx 多数是 backend 临时态：reload / EPIPE / 上游超时）
 *   - HTTP 503 + body.retriable === true → 即使 POST 也 retry（backend 明确告诉我们可以安全重试）
 *   - HTTP 4xx → 直接抛（业务错误）
 *   - 退避：第 1 次立即重试；之后 600ms / 1200ms / 2400ms ...，上限 5s
 * 终极失败时抛用户能理解的文案；UI 层把它当 retriable 收纳到 panel 占位条，不再红字。
 */
const NETWORK_ERROR_PATTERN = /Failed to fetch|Load failed|NetworkError|Network request failed/i;
const RETRIABLE_STATUS = new Set([500, 502, 503, 504]);

function _retryDelayMs(attempt: number): number {
  if (attempt <= 0) return 0;
  return Math.min(5000, 600 * 2 ** (attempt - 1));
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase();
  const isGet = method === 'GET';
  const networkRetryBudget = isGet ? 8 : 2;
  const statusRetryBudget = 3;
  let networkAttempts = 0;
  let statusAttempts = 0;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(options?.headers ?? {}),
        },
        ...options,
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      const isTransient = NETWORK_ERROR_PATTERN.test(detail);
      if (isTransient && networkAttempts < networkRetryBudget) {
        networkAttempts += 1;
        await new Promise((resolve) => setTimeout(resolve, _retryDelayMs(networkAttempts)));
        continue;
      }
      if (isTransient) {
        throw new Error('内置服务暂时未响应，请稍候重试');
      }
      throw new Error(detail || '请求失败');
    }

    if (response.ok) {
      return response.json() as Promise<T>;
    }

    const text = await response.text();
    let detail = text;
    let isRetriablePayload = false;
    try {
      const payload = JSON.parse(text) as { detail?: unknown; retriable?: boolean };
      // FastAPI validation error 时 detail 是数组对象（[{loc, msg, type}, ...]）
      // 不能直接当字符串 throw，否则会变成 "[object Object]"
      if (typeof payload.detail === 'string') {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        detail = payload.detail
          .map((entry) => {
            if (entry && typeof entry === 'object' && 'msg' in entry) {
              const loc = Array.isArray((entry as { loc?: unknown[] }).loc)
                ? ((entry as { loc: unknown[] }).loc).join('.')
                : '';
              return loc ? `${loc}: ${(entry as { msg: string }).msg}` : (entry as { msg: string }).msg;
            }
            return JSON.stringify(entry);
          })
          .join('; ');
      } else if (payload.detail && typeof payload.detail === 'object') {
        detail = JSON.stringify(payload.detail);
      } else {
        detail = text;
      }
      isRetriablePayload = payload.retriable === true;
    } catch {}

    const status = response.status;
    const isRetriableStatus = RETRIABLE_STATUS.has(status);
    const canRetryWrite = !isGet && (isRetriablePayload || status === 503);
    const shouldRetry =
      (isRetriableStatus || isRetriablePayload) &&
      statusAttempts < statusRetryBudget &&
      (isGet || canRetryWrite);

    if (shouldRetry) {
      statusAttempts += 1;
      await new Promise((resolve) => setTimeout(resolve, _retryDelayMs(statusAttempts)));
      continue;
    }

    throw new Error(detail || `HTTP ${status}`);
  }
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
    method: options?.method || 'POST',
    ...options,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const payload = JSON.parse(text) as { detail?: unknown };
      if (typeof payload.detail === 'string') {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        detail = payload.detail
          .map((entry) => {
            if (entry && typeof entry === 'object' && 'msg' in entry) {
              return (entry as { msg: string }).msg;
            }
            return JSON.stringify(entry);
          })
          .join('; ');
      } else if (payload.detail && typeof payload.detail === 'object') {
        detail = JSON.stringify(payload.detail);
      } else {
        detail = text;
      }
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth() {
  return request<HealthResponse>('/api/v1/system/health');
}

// ──────────────────────────────────────────────────────────────────────
// C 审计 P0-3 修复 (2026-05-24) · V3 Agent-Ready endpoint 前端 wrapper
// 让 src/renderer 真消费 V3 M1-M3 endpoint, 满足顾源源硬门槛 9 "前端不可见不算"
// ──────────────────────────────────────────────────────────────────────

export interface AgentStateResponse {
  client_id: string;
  client_profile?: Record<string, unknown>;
  active_projects?: Array<Record<string, unknown>>;
  latest_events?: Array<Record<string, unknown>>;
  file_identities?: Array<Record<string, unknown>>;
  contract_structures?: Array<Record<string, unknown>>;
  historical_reference_links?: Array<Record<string, unknown>>;
  commitments?: Array<Record<string, unknown>>;
  risk_signals?: Array<Record<string, unknown>>;
  clarifications?: Array<Record<string, unknown>>;
  approval_queue?: Array<Record<string, unknown>>;
  data_gaps?: Array<Record<string, unknown>>;
  agent_run_logs?: Array<Record<string, unknown>>;
  recommended_next_actions?: Array<{
    type: string;
    reason: string;
    risk_level?: string;
    approval_required?: boolean;
    evidence_table?: string;
    endpoint_hint?: string;
  }>;
  evidence_summary?: Record<string, number>;
  used_tables?: string[];
}

export async function getClientAgentState(clientId: string): Promise<AgentStateResponse> {
  return request<AgentStateResponse>(`/api/v1/clients/${encodeURIComponent(clientId)}/agent-state`);
}

export interface DataGapItem {
  gap_id: string;
  gap_type: string;
  subject?: string;
  description?: string;
  missing_evidence?: string[];
  suggested_tools?: string[];
  suggested_clarification?: string;
  priority?: 'high' | 'medium' | 'low';
  severity?: string;
  status?: string;
  approval_required?: boolean;
}

export interface DataGapsResponse {
  client_id: string;
  total: number;
  items: DataGapItem[];
  schema_version?: string;
}

export async function getClientDataGaps(
  clientId: string,
  options?: { status?: string; severity?: string; limit?: number },
): Promise<DataGapsResponse> {
  const q = new URLSearchParams();
  if (options?.status) q.set('status_filter', options.status);
  if (options?.severity) q.set('severity', options.severity);
  if (options?.limit) q.set('limit', String(options.limit));
  const suffix = q.toString() ? `?${q}` : '';
  return request<DataGapsResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/data-gaps${suffix}`,
  );
}

export interface AgentRunLogItem {
  id: string;
  tool_name?: string;
  actor_type?: string;
  actor_id?: string;
  client_id?: string | null;
  status?: string;
  triggered_at?: string;
  duration_ms?: number | null;
  idempotency_key?: string | null;
  input_json?: string;
  output_json?: string;
  error_message?: string | null;
}

export interface AgentRunLogsResponse {
  filter: { client_id?: string | null; actor_type?: string | null; limit: number };
  total: number;
  items: AgentRunLogItem[];
}

export async function listAgentRunLogs(options?: {
  clientId?: string;
  actorType?: string;
  limit?: number;
}): Promise<AgentRunLogsResponse> {
  const q = new URLSearchParams();
  if (options?.clientId) q.set('client_id', options.clientId);
  if (options?.actorType) q.set('actor_type', options.actorType);
  if (options?.limit) q.set('limit', String(options.limit));
  const suffix = q.toString() ? `?${q}` : '';
  return request<AgentRunLogsResponse>(`/api/v1/agent-run-logs${suffix}`);
}

export interface ToolRegistryEntry {
  tool_name: string;
  description?: string;
  endpoint?: string;
  when_to_use?: string;
  when_not_to_use?: string;
  risk_level?: 'low' | 'medium' | 'high';
  approval_required?: boolean;
  status?: 'available' | 'partial' | 'missing';
  blocked_by_A?: boolean;
  read_scope?: string;
  write_scope?: string;
  external_side_effect?: string;
  audit_note?: string;
}

export interface ToolRegistryResponse {
  version: string;
  total: number;
  by_status: Record<string, number>;
  tools: ToolRegistryEntry[];
  schema_completeness?: Record<string, boolean>;
}

export async function getToolRegistry(options?: {
  statusFilter?: string;
  riskLevel?: string;
}): Promise<ToolRegistryResponse> {
  const q = new URLSearchParams();
  if (options?.statusFilter) q.set('status_filter', options.statusFilter);
  if (options?.riskLevel) q.set('risk_level', options.riskLevel);
  const suffix = q.toString() ? `?${q}` : '';
  return request<ToolRegistryResponse>(`/api/v1/tool-registry${suffix}`);
}

export interface ApprovalRow {
  id: string;
  client_id?: string | null;
  action_type: string;
  actor_type: string;
  actor_id: string;
  target_resource?: string | null;
  payload?: Record<string, unknown>;
  reason?: string;
  status: string;
  agent_run_id?: string | null;
  created_at: string;
}

export async function listApprovals(options?: {
  clientId?: string;
  limit?: number;
}): Promise<ApprovalRow[]> {
  const q = new URLSearchParams();
  if (options?.clientId) q.set('client_id', options.clientId);
  if (options?.limit) q.set('limit', String(options.limit));
  const suffix = q.toString() ? `?${q}` : '';
  return request<ApprovalRow[]>(`/api/v1/approvals${suffix}`);
}

export async function approveApproval(
  approvalId: string,
  decidedBy: string,
  note?: string,
): Promise<{ id: string; status: string; decided_by: string }> {
  return request(`/api/v1/approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decided_by: decidedBy, note: note ?? '' }),
  });
}

export async function rejectApproval(
  approvalId: string,
  decidedBy: string,
  note?: string,
): Promise<{ id: string; status: string; decided_by: string }> {
  return request(`/api/v1/approvals/${encodeURIComponent(approvalId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decided_by: decidedBy, note: note ?? '' }),
  });
}
// ────────────────────── end V3 P0-3 wrappers ──────────────────────────

// ──────────────────────────────────────────────────────────────────────
// 顾源源 5/24 大型任务 · 组织搭建中心机器人同事 API wrapper
// 6 capability + 8 endpoint, 给 BotMembersPanel.tsx 用
// ──────────────────────────────────────────────────────────────────────

export const BOT_CAPABILITY_KEYS = [
  'workspace_file_write.request',
  'data_center_parse.request',
  'external_material_draft.create',
  'external_send.request',
  'clarification_resolution.propose',
  'inline_approval.allow_from_supervisor',
] as const;

export type BotCapabilityKey = (typeof BOT_CAPABILITY_KEYS)[number];

export interface BotCapability {
  capability_key: BotCapabilityKey;
  enabled: boolean | number;
  approval_required: boolean | number;
  approval_policy: string;
}

export interface BotReporting {
  report_to_creator: boolean | number;
  report_to_department_lead: boolean | number;
  report_to_ceo: boolean | number;
  department_leader_user_ids: string[];
  ceo_user_ids: string[];
  approval_mode: string;
}

export interface BotMemberRecord {
  id: string;
  display_name: string;
  handle: string;
  actor_id: string;
  actor_type: string;
  department_id?: string | null;
  department_name?: string;
  description?: string;
  status: 'active' | 'disabled';
  reporting?: BotReporting;
  capabilities?: BotCapability[];
  /** 顾源源 5/24: 身份启动密钥相关 (db 只存 hash, 这里只暴露 prefix 等 metadata) */
  token_prefix?: string;
  token_rotated_at?: string | null;
  has_token?: boolean;
  /** 仅创建/重置时返一次的明文 token, 关闭弹窗后丢弃, db 永远不再可读 */
  token_plain?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CreateBotPayload {
  display_name: string;
  handle?: string;
  department_id?: string;
  department_name?: string;
  description?: string;
  created_by_user_id?: string;
  report_to_creator?: boolean;
  report_to_department_lead?: boolean;
  report_to_ceo?: boolean;
  department_leader_user_ids?: string[];
  ceo_user_ids?: string[];
  enabled_capabilities?: BotCapabilityKey[];
}

export interface BotPermissionsResponse {
  bot_member_id: string;
  actor_id: string;
  capabilities: BotCapability[];
  hard_denies: string[];
  inline_approval_blocked_actions: string[];
}

export async function createBotMember(payload: CreateBotPayload): Promise<BotMemberRecord> {
  return request<BotMemberRecord>('/api/v1/org/bots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * 重置机器人身份启动密钥. 旧 token 立即作废, 新 token 明文随返一次.
 * 调用方必须立即把 result.token_plain 展示给用户复制保存, 之后 db 不再可读.
 */
export async function rotateBotToken(
  botMemberId: string,
  newToken?: string,
): Promise<BotMemberRecord> {
  return request<BotMemberRecord>(
    `/api/v1/org/bots/${encodeURIComponent(botMemberId)}/rotate-token`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newToken ? { new_token: newToken } : {}),
    },
  );
}

export async function listBotMembers(options?: { status?: string }): Promise<{ total: number; items: BotMemberRecord[] }> {
  const q = new URLSearchParams();
  if (options?.status) q.set('status', options.status);
  const suffix = q.toString() ? `?${q}` : '';
  return request(`/api/v1/org/bots${suffix}`);
}

export async function getBotMember(botMemberId: string): Promise<BotMemberRecord> {
  return request(`/api/v1/org/bots/${encodeURIComponent(botMemberId)}`);
}

export async function updateBotMember(
  botMemberId: string,
  payload: Partial<CreateBotPayload> & { status?: 'active' | 'disabled' },
): Promise<BotMemberRecord> {
  return request(`/api/v1/org/bots/${encodeURIComponent(botMemberId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function resolveBotByHandle(handle: string): Promise<{
  bot_member_id: string;
  display_name: string;
  handle: string;
  actor_type: string;
  actor_id: string;
  department_id?: string | null;
  department_name?: string;
  reporting_approvers: Array<{ user_id: string; role: string }>;
  enabled_capabilities: string[];
  status: string;
}> {
  return request(`/api/v1/org/bots/resolve?handle=${encodeURIComponent(handle)}`);
}

export async function getBotPermissions(botMemberId: string): Promise<BotPermissionsResponse> {
  return request(`/api/v1/org/bots/${encodeURIComponent(botMemberId)}/permissions`);
}

export interface CreateAITaskPlanPayload {
  plan_title: string;
  plan_text?: string;
  client_id?: string;
  event_line_id?: string;
  task_id?: string;
  required_modules?: string[];
  steps?: Array<{ module?: string; action?: string; expected_result?: string }>;
  expected_outputs?: string[];
  write_actions?: Array<Record<string, unknown>>;
  approval_required?: boolean;
  inline_authorization?: boolean;
  inline_authorization_text?: string;
  human_initiator_id?: string;
  action_capability?: BotCapabilityKey;
}

export interface AITaskPlanCreateResponse {
  ai_task_plan_id: string;
  task_id?: string | null;
  approval_id?: string | null;
  approval_status: string;
  approval_source: string;
  approved_by?: string | null;
  status: string;
  pending_reason?: string | null;
}

export async function createBotTaskPlan(
  botMemberId: string,
  payload: CreateAITaskPlanPayload,
): Promise<AITaskPlanCreateResponse> {
  return request(`/api/v1/org/bots/${encodeURIComponent(botMemberId)}/task-plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export interface AITaskPlanRecord {
  id: string;
  bot_member_id: string;
  client_id?: string | null;
  plan_title: string;
  plan_text: string;
  required_modules_json: string;
  steps_json: string;
  expected_outputs_json: string;
  approval_required: number | boolean;
  approval_id?: string | null;
  approval_source: string;
  status: 'pending_approval' | 'approved' | 'needs_revision' | 'rejected' | 'executing' | 'completed';
  human_initiator_id?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  supervisor_feedback?: string | null;
  plan_version: number;
  prev_plan_json?: string | null;
  created_at: string;
}

export async function listBotTaskPlans(
  botMemberId: string,
  options?: { status?: string; limit?: number },
): Promise<{ bot_member_id: string; total: number; items: AITaskPlanRecord[] }> {
  const q = new URLSearchParams();
  if (options?.status) q.set('status', options.status);
  if (options?.limit) q.set('limit', String(options.limit));
  const suffix = q.toString() ? `?${q}` : '';
  return request(`/api/v1/org/bots/${encodeURIComponent(botMemberId)}/task-plans${suffix}`);
}

export async function decideBotTaskPlan(
  aiTaskPlanId: string,
  decision: 'approve' | 'reject' | 'revise',
  decidedBy: string,
  options?: {
    feedback?: string;
    modifiedPlan?: { plan_text?: string; plan_title?: string; steps?: unknown[]; expected_outputs?: string[] };
  },
): Promise<AITaskPlanRecord> {
  const body = {
    decision,
    decided_by: decidedBy,
    feedback: options?.feedback ?? '',
    modified_plan: options?.modifiedPlan,
  };
  return request(`/api/v1/org/bots/task-plans/${encodeURIComponent(aiTaskPlanId)}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// M10 (A, 2026-05-25) · plan 进度可视化
export interface PlanProgressSubtask {
  index: number;
  tool: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  output_summary?: string;
  error?: string;
  duration_ms?: number;
}

export interface PlanProgressRecord {
  plan_id: string;
  plan_status: string;
  execution_status:
    | 'not_started'
    | 'pending_execute'
    | 'running'
    | 'success'
    | 'failed'
    | 'partial';
  started_at: string | null;
  completed_at: string | null;
  progress: {
    total: number;
    completed: number;
    current: string;
    percent: number;
    errors: Array<{ index: number; tool: string; error: string }>;
  };
  subtasks: PlanProgressSubtask[];
  errors: Array<{ index: number; tool: string; error: string }>;
}

export interface AiCommandParsedStep {
  index: number;
  action: string;
  basis: string;
  deliverable: string;
}

export interface AiCommandParseStepsResponse {
  steps: AiCommandParsedStep[];
  model_used?: string;
  fallback_reason?: string;
}

/**
 * [B] 2026-05-25 PM · LLM 真解析自然口语指令 → step 三段式 list.
 * 优先本地 qwen2.5:7b (4-5s), 失败 fallback 豆包 (2-3s).
 */
export async function aiCommandParseSteps(text: string): Promise<AiCommandParseStepsResponse> {
  return request<AiCommandParseStepsResponse>('/api/v1/ai-command/parse-steps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

// [B] 5/25 PM (顾源源 path C) · 双重归属复盘 · 2 个 endpoint
export interface UserAiDelegationsResponse {
  user_id: string;
  week_start: string;
  week_end: string;
  plans: Array<{
    plan_id: string;
    plan_title: string;
    bot_id: string;
    bot_name: string;
    client_id: string;
    status: string;
    execution_status: string;
    created_at: string;
    subtask_count: number;
    success_count: number;
    failed_count: number;
    summary: unknown[];
  }>;
  summary: {
    total_plans: number;
    approved: number;
    executing: number;
    completed: number;
    failed: number;
  };
  ai_collaboration_score: number;
  user_manual_tasks: number;
}

export interface BotWeeklySummaryResponse {
  bot: {
    id: string;
    actor_id: string;
    display_name: string;
    department_id: string;
    department_name: string;
  };
  week_start: string;
  week_end: string;
  plans_received: Array<{
    plan_id: string;
    plan_title: string;
    human_initiator: string;
    status: string;
    execution_status: string;
    client_id: string;
    created_at: string;
    subtask_count: number;
    success_count: number;
  }>;
  actions_summary: Record<string, number>;
  total_actions: number;
  success_count: number;
  failed_count: number;
  success_rate: number;
  avg_duration_ms: number;
}

export async function getUserAiDelegations(userId: string, week?: string): Promise<UserAiDelegationsResponse> {
  const q = week ? `?week=${encodeURIComponent(week)}` : '';
  return request<UserAiDelegationsResponse>(`/api/v1/local/users/${encodeURIComponent(userId)}/ai-delegations${q}`);
}

export async function getBotWeeklySummary(botId: string, week?: string): Promise<BotWeeklySummaryResponse> {
  const q = week ? `?week=${encodeURIComponent(week)}` : '';
  return request<BotWeeklySummaryResponse>(`/api/v1/local/bot-members/${encodeURIComponent(botId)}/weekly-summary${q}`);
}

export async function getBotTaskPlanProgress(planId: string): Promise<PlanProgressRecord> {
  return request<PlanProgressRecord>(
    `/api/v1/org/bots/task-plans/${encodeURIComponent(planId)}/progress`,
  );
}
// ────────────── end 机器人同事 wrappers ──────────────

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

// Stage 2：客户知识库状态 —— 替代百分比成熟度展示的 Karpathy 语义数字。
// 返回 4 个绝对数（已确认事实/待确认思考/矛盾/缺口）+ 本周增量 = "AI 又懂了什么"
export type ClientKnowledgeStatusWeeklyDelta = {
  confirmedFacts: number;
  activeContradictions: number;
  newThoughts: number;
  confirmedJudgments: number;
};

export type PendingFanoutAction = {
  actionType: 'judgment_needs_reevaluation' | 'profile_needs_review' | 'thought_refresh_pending' | string;
  entityId: string;
  entityLabel: string;
  reason: string;
  triggeredAt: string;
};

export type ClientKnowledgeStatus = {
  clientId: string;
  confirmedFacts: number;
  pendingThoughts: number;
  activeContradictions: number;
  knowledgeGaps: number;
  weeklyDelta: ClientKnowledgeStatusWeeklyDelta;
  // Stage B 扇出待办（新资料触发的 AI 标记待用户拍板）
  pendingJudgmentReevaluation: number;
  pendingProfileReview: number;
  pendingThoughtRefresh: number;
  recentFanoutCount: number;
  pendingActions: PendingFanoutAction[];
  generatedAt: string;
};

// Stage 3「矛盾 & 待确认」tab 数据源
export type FactContradictionRow = {
  id: string;
  clientId: string;
  subjectText: string;
  attribute: string;
  valueA: string;
  valueB: string;
  evidenceA: string;
  evidenceB: string;
  factAId: string;
  factBId: string;
  factAAt: string;
  factBAt: string;
  docAFileName?: string | null;
  docAImportedAt?: string | null;
  docAOriginalPath?: string | null;
  docBFileName?: string | null;
  docBImportedAt?: string | null;
  docBOriginalPath?: string | null;
  contradictionType: 'value_diff' | 'temporal' | 'scope';
  severity: 'low' | 'medium' | 'high';
  reviewStatus: 'pending' | 'dismissed' | 'resolved';
  resolutionNote?: string | null;
  detectedAt: string;
};

export type FactContradictionListResponse = {
  contradictions: FactContradictionRow[];
  total: number;
};

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

// ──────────────────────────────────────────────────────────────────
// 智能新建任务 — 把一段自然语言转结构化任务字段
// ──────────────────────────────────────────────────────────────────
export type TaskAiParseClientCandidate = {
  id: string;
  name: string;
  score: number;
};

export type TaskAiParseResult = {
  title: string;
  desc: string;
  dueDate: string | null;
  dueTime: string | null;
  priority: 'low' | 'normal' | 'high';
  clientId: string | null;
  clientName: string | null;
  clientCandidates: TaskAiParseClientCandidate[];
  rawLlmGuessClientName: string | null;
};

export async function aiParseTask(payload: { text: string; currentDate: string }) {
  return request<TaskAiParseResult>('/api/v1/tasks/ai-parse', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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

export async function localRegister(payload: LocalAuthRegisterPayload) {
  // local-auth 已剥离, 统一走云端注册(登录即云端). cloud 忽略 organizationMode, 靠 inviteCode 判断 join/create.
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

export async function localLogin(payload: LocalAuthLoginPayload) {
  // local-auth 已剥离, 统一走云端登录(登录即云端). cloud AuthLoginPayload 兼容 identifier 字段.
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

// === 输入广度线程：语音识别模型配置 ===

export async function getSpeechModelSettings() {
  return request<SpeechModelSettings>('/api/v1/settings/speech-model');
}

export async function updateSpeechModelSettings(payload: SpeechModelSettingsPayload) {
  return request<SpeechModelSettings>('/api/v1/settings/speech-model', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function testSpeechModelSettings(payload: SpeechModelSettingsPayload) {
  return request<SpeechModelTestResult>('/api/v1/settings/speech-model/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// === I1b-1：对象存储 ===

export async function getObjectStorageSettings() {
  return request<ObjectStorageSettings>('/api/v1/settings/object-storage');
}

export async function updateObjectStorageSettings(payload: ObjectStorageSettingsPayload) {
  return request<ObjectStorageSettings>('/api/v1/settings/object-storage', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function testObjectStorageSettings(payload: ObjectStorageSettingsPayload) {
  return request<ObjectStorageTestResult>('/api/v1/settings/object-storage/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// === I1b-2：本地 ASR ===

export async function getLocalAsrModelStatus() {
  return request<LocalAsrModelStatus>('/api/v1/local-asr/model/status');
}

export async function startLocalAsrModelDownload(preferMirror = true) {
  return request<LocalAsrDownloadStartResponse>('/api/v1/local-asr/model/download', {
    method: 'POST',
    body: JSON.stringify({ preferMirror }),
  });
}

export async function cancelLocalAsrModelDownload() {
  return request<LocalAsrDownloadCancelResponse>('/api/v1/local-asr/model/cancel', {
    method: 'POST',
  });
}

export async function transcribeTestLocalAsr(audioPath: string) {
  return request<LocalAsrTestTranscriptionResponse>('/api/v1/local-asr/transcribe-test', {
    method: 'POST',
    body: JSON.stringify({ audioPath }),
  });
}

export type DiarizationModelStatus = {
  segmentationModelName: string;
  embeddingModelName: string;
  segmentationInstalled: boolean;
  embeddingInstalled: boolean;
  bothInstalled: boolean;
  sizeBytes: number;
  downloadInProgress: boolean;
  downloadBytesDownloaded: number;
  downloadBytesTotal: number;
  downloadCurrentFile: string;
  downloadCurrentModel: string;
  downloadPendingModels: string[];
  downloadCompletedModels: string[];
  downloadCompleted: boolean;
  downloadError: string | null;
  downloadElapsedSeconds: number;
};

export async function getDiarizationModelStatus() {
  return request<DiarizationModelStatus>('/api/v1/local-asr/diarization/status');
}

export async function startDiarizationModelDownload(preferMirror = true) {
  return request<LocalAsrDownloadStartResponse>('/api/v1/local-asr/diarization/download', {
    method: 'POST',
    body: JSON.stringify({ preferMirror }),
  });
}

// === P0-②：Ollama 管理 ===

export async function getOllamaHealth() {
  return request<OllamaHealthResponse>('/api/v1/ollama/health');
}

export async function getOllamaRecommendedModels(capability: string) {
  return request<OllamaRecommendedModelsResponse>(
    `/api/v1/ollama/recommended-models?capability=${encodeURIComponent(capability)}`,
  );
}

export async function startOllamaPull(modelName: string, baseUrl?: string) {
  return request<OllamaPullStartResponse>('/api/v1/ollama/pull', {
    method: 'POST',
    body: JSON.stringify({ modelName, baseUrl: baseUrl ?? null }),
  });
}

export async function getOllamaPullStatus() {
  return request<OllamaPullStatusResponse>('/api/v1/ollama/pull/status');
}

export async function cancelOllamaPull() {
  return request<OllamaPullCancelResponse>('/api/v1/ollama/pull/cancel', { method: 'POST' });
}

export async function deleteOllamaModel(modelName: string, baseUrl?: string) {
  return request<OllamaDeleteModelResponse>('/api/v1/ollama/delete', {
    method: 'POST',
    body: JSON.stringify({ modelName, baseUrl: baseUrl ?? null }),
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

export async function getOrgAdminClaimStatus() {
  return request<OrgAdminClaimStatus>('/api/v1/me/org-membership/admin-claim-status');
}

export async function claimOrgAdmin() {
  return request<AuthState>('/api/v1/me/org-membership/admin-claim', {
    method: 'POST',
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

export async function getFeishuSyncStatus(params: { localType: string; localId: string; remoteType?: string }) {
  const search = new URLSearchParams({
    localType: params.localType,
    localId: params.localId,
    remoteType: params.remoteType || 'calendar_event',
  });
  return request<FeishuSyncStatusRecord>(`/api/v1/feishu-sync/status?${search.toString()}`);
}

export async function syncTaskToFeishuCalendar(taskId: string, payload: FeishuTaskCalendarSyncPayload = {}) {
  return request<FeishuSyncStatusRecord>(`/api/v1/feishu-sync/calendar/tasks/${encodeURIComponent(taskId)}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function syncDocumentToFeishuDocx(payload: FeishuDocumentSyncPayload) {
  return request<FeishuSyncStatusRecord>('/api/v1/feishu-sync/documents', {
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

// V2.3 Step 5 · team sync UI api（从主仓库 origin/main 同步补回:本 worktree 落后 V2.3,
// TeamSyncPanel.tsx 引用了这 3 个导出但 api.ts 缺失 → 整个 renderer 模块加载失败白屏）
export interface TeamSyncStats {
  pending: number;
  synced: number;
  failed: number;
  total: number;
}

export interface TeamSyncRunResult {
  status: string;
  count: number;
  accepted?: number;
  duplicates?: number;
  rejected?: number;
  error?: string;
}

export async function getTeamSyncStats(): Promise<TeamSyncStats> {
  return request<TeamSyncStats>('/api/v1/data-center/team-sync/stats');
}

export async function enqueueTeamSyncAll(): Promise<{ inserted: number; total_scanned: number }> {
  return request<{ inserted: number; total_scanned: number }>(
    '/api/v1/data-center/team-sync/enqueue-all',
    { method: 'POST' },
  );
}

export async function runTeamSyncOnce(batchSize = 50): Promise<TeamSyncRunResult> {
  return request<TeamSyncRunResult>(
    `/api/v1/data-center/team-sync/run-once?batch_size=${batchSize}`,
    { method: 'POST' },
  );
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

// ─── v2.2 Phase 1 F1.5 · ClientFactBundle (L2 共识层) ───
import type { ClientFactBundle, FetchClientFactBundleOptions } from './clientFactTypes';
// ─── [DEPRECATED 2026-05-22 · 新计划阶段 0] V2.1 N2 FullNarrative 8 段类型已废弃 ───
// 跟产品手册 §03 钦定 6 段 (essence/cooperation/business_intro/people/timeline/next_steps) 冲突.
// 主仓库 narrative_generator 才是真 endpoint. 见 fullNarrativeTypes.ts.DEPRECATED.
// import type { FullNarrative, FetchFullNarrativeOptions } from './fullNarrativeTypes';

/**
 * v2.2 F1.5 · 拿一个客户的完整事实包 (L2 共识层入口)
 *
 * 后端: backend/app/main.py GET /api/v1/clients/{client_id}/fact-bundle
 * 数据: 跨 6 表合并 (client + event_lines + tasks + commitments + dna_documents + atomic_facts)
 *
 * 用法 (在 React 组件里, 推荐用 useClientFact hook):
 *   const bundle = await fetchClientFactBundle('client_284afd836e');
 *   // bundle.event_lines / bundle.tasks / bundle.counts / ...
 *
 * 404: client 不存在或 archived (用 includeArchived=true 解锁 archived)
 */
export async function fetchClientFactBundle(
  clientId: string,
  options?: FetchClientFactBundleOptions,
): Promise<ClientFactBundle> {
  const params = new URLSearchParams();
  if (options?.includeArchived) params.set('include_archived', 'true');
  if (options?.lite) params.set('lite', 'true');
  const query = params.toString();
  const path = `/api/v1/clients/${encodeURIComponent(clientId)}/fact-bundle${query ? `?${query}` : ''}`;
  return request<ClientFactBundle>(path);
}

/**
 * [DEPRECATED 2026-05-22 · 新计划阶段 0]
 *
 * V2.1 8 段 fetcher 已废弃. 跟产品手册 §03 钦定 6 段 (essence/cooperation/
 * business_intro/people/timeline/next_steps) 冲突. 主仓库现有 getClientNarrative
 * 是真 endpoint (6 段). 见 fullNarrativeTypes.ts.DEPRECATED.
 *
 * 历史 commit: 4b254c1.
 */
// export async function fetchClientFullNarrative(
//   clientId: string,
//   options?: FetchFullNarrativeOptions,
// ): Promise<FullNarrative> {
//   const params = new URLSearchParams();
//   if (options?.forceRefresh) params.set('force_refresh', 'true');
//   const query = params.toString();
//   const path = `/api/v1/clients/${encodeURIComponent(clientId)}/full-narrative${query ? `?${query}` : ''}`;
//   const headers: Record<string, string> = {};
//   if (options?.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;
//   if (options?.actorId) headers['X-Actor-Id'] = options.actorId;
//   return request<FullNarrative>(path, { headers });
// }

export type ClientDeletePreview = {
  clientId: string;
  name: string;
  threadCount: number;
  messageCount: number;
  documentCount: number;
  dnaCount: number;
  goalCount: number;
  meetingCount: number;
  eventLineCount: number;
  taskCount: number;
  isDemoClient: boolean;
};

export async function getClientDeletePreview(id: string) {
  return request<ClientDeletePreview>(`/api/v1/clients/${id}/delete-preview`);
}

// 全局冷冻 / 解冻 — 把项目从所有自动计算/资讯/数据中心 job 里冻结
export async function freezeClient(id: string) {
  return request<ClientSummary>(`/api/v1/clients/${id}/freeze`, { method: 'POST' });
}

export async function unfreezeClient(id: string) {
  return request<ClientSummary>(`/api/v1/clients/${id}/unfreeze`, { method: 'POST' });
}

export async function deleteClientFolder(clientId: string, folderId: string) {
  return request<{ deleted: boolean }>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'DELETE',
  });
}

export async function deleteClientDocument(clientId: string, documentId: string) {
  return request<{
    deleted: boolean;
    documentId: string;
    fileName: string;
    recycledPath: string;
  }>(`/api/v1/clients/${clientId}/documents/${documentId}`, {
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

export async function getClientGlossary(
  clientId: string,
  options: { q?: string; limit?: number; offset?: number } = {},
): Promise<GlossaryListResponse> {
  const params = new URLSearchParams();
  if (options.q) params.set('q', options.q);
  if (typeof options.limit === 'number') params.set('limit', String(options.limit));
  if (typeof options.offset === 'number') params.set('offset', String(options.offset));
  const suffix = params.toString();
  const url = `/api/v1/clients/${clientId}/glossary${suffix ? `?${suffix}` : ''}`;
  return request<GlossaryListResponse>(url);
}

export async function createGlossaryEntry(
  clientId: string,
  payload: { term: string; definition?: string; aliases?: string[]; category?: string },
): Promise<GlossaryEntry> {
  return request<GlossaryEntry>(`/api/v1/clients/${clientId}/glossary`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateGlossaryEntry(
  entryId: string,
  payload: { term?: string; definition?: string; aliases?: string[]; category?: string },
): Promise<GlossaryEntry> {
  return request<GlossaryEntry>(`/api/v1/glossary/${entryId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteGlossaryEntry(entryId: string): Promise<void> {
  await request<{ status: string }>(`/api/v1/glossary/${entryId}`, {
    method: 'DELETE',
  });
}

export async function getEntityMergeCandidates(
  clientId: string,
  limit = 50,
): Promise<EntityMergeCandidatesResponse> {
  return request<EntityMergeCandidatesResponse>(
    `/api/v1/clients/${clientId}/entity-merge-candidates?limit=${limit}`,
  );
}

export async function mergeEntityInto(
  mergedId: string,
  payload: { survivingEntityId: string; mergeReason?: string },
): Promise<EntityMergeResult> {
  return request<EntityMergeResult>(`/api/v1/entities/${mergedId}/merge`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ★ ER v4 · 人工金标 verify (5/28 加, 权重最高的人工裁决)
// status='canonical' = 这是真人物, 永远不被 LLM cluster 覆盖
// status='noise'     = 这是 ASR 错误/不是真人物, 永久过滤
// status='alias_of'  = 这是别名, 合并到 alias_target_id (内部触发 merge_entities)
export interface EntityVerifyResult {
  entityId: string;
  verifiedStatus: string;
  verifiedAt: string;
  mergedInto?: string;
  mentionsMoved?: number;
  factsMoved?: number;
}

export async function verifyEntity(
  entityId: string,
  payload: {
    status: 'canonical' | 'noise' | 'alias_of';
    alias_target_id?: string | null;
    reason?: string;
  },
): Promise<EntityVerifyResult> {
  return request<EntityVerifyResult>(`/api/v1/entities/${entityId}/verify`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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

// 客户级文件重复检测 —— 「矛盾 & 待确认」tab 顶部 section 消费。
// 解决用户直观痛点：同一份文件被上传多次没被发现。
// 用 content_hash 精确匹配（避免被 file(1).docx 这种变体名干扰）+ 同 filename fallback。
export type DuplicateDocumentItem = {
  id: string;
  documentId: string;
  fileName: string;
  kind: string;
  managedPath: string;
  originalPath: string;
  contentHash: string;
  parseStatus: string;
  sectionCount: number;
  chunkCount: number;
  importedAt: string;
  fileSizeBytes: number;
  refTaskAttachmentCount: number;
  refEvidenceCardCount: number;
  refAtomicFactCount: number;
};

export type DuplicateDocumentGroup = {
  groupKey: string;
  groupType: 'same_content_hash' | 'same_filename';
  fileName: string;
  contentHash: string;
  count: number;
  documents: DuplicateDocumentItem[];
};

export async function getClientDuplicateDocuments(clientId: string) {
  return request<DuplicateDocumentGroup[]>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/duplicate-documents`,
  );
}

export type DuplicateDocumentResolveResult = {
  action: string;
  groupKey: string;
  deletedCount: number;
  recycledTo: string;
  migratedTaskAttachments: number;
  migratedEvidenceRefs: number;
  migratedAtomicFacts: number;
  keptDocumentIds: string[];
};

// 用户在「处理重复文件」Modal 里的决定 —— 真正落地到后端：
// action='delete_others'：迁移引用 + 物理文件进回收站（30 天可恢复）
// action='keep_all'：标记 group 已审查，下次扫描跳过
export async function resolveDuplicateDocuments(
  clientId: string,
  payload: {
    groupKey: string;
    action: 'delete_others' | 'keep_all';
    keepV2DocumentIds: string[];
    deleteV2DocumentIds: string[];
    migrateReferences: boolean;
    note?: string;
  },
) {
  return request<DuplicateDocumentResolveResult>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/duplicate-documents/resolve`,
    { method: 'POST', body: JSON.stringify({ ...payload, note: payload.note || '' }) },
  );
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
  // /knowledge-status 端点返回带 confirmedFacts/weeklyDelta 等业务字段的 ClientKnowledgeStatus,
  // 是战略陪伴 hero 区与待办标记需要的视图; 不要回退到 /knowledge/status (totalDocuments 那个).
  return request<ClientKnowledgeStatus>(`/api/v1/clients/${encodeURIComponent(clientId)}/knowledge-status`);
}

// ─── 战略陪伴 · 客户脉搏 (Phase 1 克制版主页) ───────────────────

export type StrategicPulseEvent = {
  title: string;
  occurredAt: string;
  impact: 'advance' | 'neutral' | 'block';
  sourceType: string;
  sourceId: string;
  sourceLabel: string;
};

export type StrategicPulseTodo = {
  title: string;
  dueDate: string | null;
  daysUntilDue: number | null;
  urgency: 'overdue' | 'today' | 'this_week' | 'later';
  sourceTaskId: string | null;
  eventLineId: string | null;
  eventLineName: string;
};

export type StrategicPulseBlocker = {
  title: string;
  reason: string;
  stuckDays: number;
  eventLineId: string;
  suggestedAction: string;
};

export type StrategicPulse = {
  clientId: string;
  weekStart: string;
  weekEnd: string;
  weeklyEvents: StrategicPulseEvent[];
  upcomingTodos: StrategicPulseTodo[];
  currentBlockers: StrategicPulseBlocker[];
  generatedAt: string;
};

export async function getClientStrategicPulse(clientId: string) {
  return request<StrategicPulse>(`/api/v1/clients/${encodeURIComponent(clientId)}/strategic-pulse`);
}

// ─── 战略陪伴 · 事实澄清面板 (Phase 1.5b) ───────────────────
export type ClarificationProfile = {
  name: string; alias: string; domain: string; type: string; intro: string;
  stage: string; color: string; industry: string; scale: string; influence: string;
  currentNeeds: string; painPoints: string; strategicValueToYiyu: string;
  decisionChain: string; cooperationType: string; relationshipHealth: string;
  milestones: string; cooperationStartedAt: string;
};

export type ClarificationEventLine = {
  id: string; name: string; kind: string; status: string; stage: string;
  summary: string; intent: string; nextStep: string; currentBlocker: string;
  recentDecision: string; businessCategory: string; ownerId: string; ownerName: string;
  evidenceCount: number; createdAt: string; updatedAt: string; closedAt: string;
  isDirtyName: boolean;
};

export type ClarificationTimelineItem = {
  id: string; eventLineId: string; eventLineName: string;
  happenedAt: string; sourceType: string; actorName: string;
  title: string; summary: string; isKey: boolean;
};

export type ClarificationPerson = {
  name: string; mentionCount: number; sources: string[];
};

export type ClarificationCommitment = {
  id: string; title: string; ownerName: string; dueDate: string;
  confidence: number; publishStatus: string;
  meetingId: string; meetingTitle: string; meetingScheduledAt: string;
  createdAt: string;
};

export type ClarificationNeed = {
  eventLineId: string; eventLineName: string; missingFields: string[];
  predictionReadiness: number; confidence: number; updatedAt: string;
};

export type ClarificationContext = {
  clientId: string;
  profile: ClarificationProfile;
  eventLines: ClarificationEventLine[];
  timeline: ClarificationTimelineItem[];
  peopleCandidates: ClarificationPerson[];
  commitments: ClarificationCommitment[];
  clarificationNeeds: ClarificationNeed[];
  generatedAt: string;
};

export async function getClientClarificationContext(clientId: string) {
  return request<ClarificationContext>(`/api/v1/clients/${encodeURIComponent(clientId)}/clarification-context`);
}

// ─── Phase 1.5c · 战略陪伴维度故事网 (云端共享, 共同编织) ─────────
export type NarrativeDimensionKey =
  // v1.0 6 层 (云端 storage 真维度)
  | 'essence'
  | 'cooperation'
  | 'business_intro'
  | 'people'
  | 'timeline'
  | 'next_steps'
  // 兼容旧 rev (已废弃)
  | 'history' | 'commitments' | 'risks' | 'next';

// 战略文档 (用户上传 .md, 独立存储, 不进 narrative.dimensions)
export type StrategicDocType = 'strategy' | 'methodology';

export type StrategicDocEntry = {
  fileName: string;
  mdContent: string;
  uploadedAt: string;
  uploadedBy: string;
};

export type StrategicDocsResponse = {
  clientId: string;
  strategy: StrategicDocEntry | null;
  methodology: StrategicDocEntry | null;
  hasStrategy: boolean;
  hasMethodology: boolean;
};

export async function getStrategicDocs(clientId: string): Promise<StrategicDocsResponse> {
  return request<StrategicDocsResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/strategic-docs`,
  );
}

export async function uploadStrategicDoc(
  clientId: string,
  payload: { docType: StrategicDocType; fileName: string; mdContent: string },
): Promise<{ ok: boolean; docType: string; fileName: string }> {
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/strategic-docs`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function deleteStrategicDoc(
  clientId: string,
  docType: StrategicDocType,
): Promise<{ ok: boolean }> {
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/strategic-docs/${docType}`,
    { method: 'DELETE' },
  );
}

export type NarrativeConfidence = 'high' | 'medium' | 'low';

export type NarrativeReference = {
  sourceType: string;
  sourceId: string;
  label: string;
  confidence: NarrativeConfidence;
};

export type NarrativeDimensionRecord = {
  dimension: NarrativeDimensionKey;
  narrative: string;
  confidence: NarrativeConfidence;
  confidenceReason: string;
  references: NarrativeReference[];
  dataLayerGap: string;
  openClarifications: string[];
  // M2 取材来源可见 (后端 narrative_generator emit; 云端 schema 透传后生效, 缺省安全降级)
  retrievalMode?: 'semantic' | 'semantic+fallback' | 'fallback_only' | 'legacy_or_empty' | 'legacy_like_only';
  fallbackUsed?: boolean;
  reindexRequired?: boolean;
};

export type NarrativeContributor = {
  userId: string | null;
  displayName: string;
  dimension: NarrativeDimensionKey;
  answeredAt: string;
};

export type ClientNarrative = {
  id: string;
  clientId: string;
  clientName: string;
  rev: number;
  generator: string;
  generatedAt: string;
  modelName: string;
  dimensions: NarrativeDimensionRecord[];
  overallConfidence: number;
  openClarificationsCount: number;
  dataLayerGaps: string[];
  contributors: NarrativeContributor[];
  updatedAt: string;
};

export type NarrativeClarificationStatus = 'pending' | 'applied' | 'discarded';

export type NarrativeClarification = {
  id: string;
  clientId: string;
  basedOnRev: number;
  dimension: NarrativeDimensionKey;
  question: string;
  askedBy: string;
  answer: string;
  answeredByUserId: string | null;
  answeredByDisplayName: string;
  answeredAt: string;
  resultedInRev: number | null;
  status: NarrativeClarificationStatus;
};

export type NarrativeClarificationsResponse = {
  clarifications: NarrativeClarification[];
};

export type NarrativeClarificationPayload = {
  dimension: NarrativeDimensionKey;
  question?: string;
  answer: string;
  basedOnRev?: number;
};

export type NarrativeRegeneratePayload = {
  trigger?: string;
  force?: boolean;
  /** 单维度模式: 仅刷新指定维度,其他维度保留 cloud 现有内容. 不传 / 空数组 = 全部重生 */
  dimensions?: NarrativeDimensionKey[];
};

export async function getClientNarrative(clientId: string): Promise<ClientNarrative> {
  return request<ClientNarrative>(`/api/v1/clients/${encodeURIComponent(clientId)}/narrative`);
}

export async function listClientNarrativeClarifications(clientId: string): Promise<NarrativeClarificationsResponse> {
  return request<NarrativeClarificationsResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/narrative/clarifications`,
  );
}

export async function submitClientNarrativeClarification(
  clientId: string,
  payload: NarrativeClarificationPayload,
): Promise<NarrativeClarification> {
  return request<NarrativeClarification>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/narrative/clarifications`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export async function regenerateClientNarrative(
  clientId: string,
  payload: NarrativeRegeneratePayload = {},
): Promise<ClientNarrative> {
  return request<ClientNarrative>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/narrative/regenerate`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export type NarrativeStaleStatus = {
  isStale: boolean;
  markedAt: string;
  narrativeGeneratedAt: string;
  lastDocTitle: string;
  reason: string;
};

export async function getNarrativeStaleStatus(clientId: string): Promise<NarrativeStaleStatus> {
  return request<NarrativeStaleStatus>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/narrative/stale-status`,
  );
}

export async function clearNarrativeStale(clientId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/narrative/stale-clear`,
    { method: 'POST' },
  );
}

export type MeetingActionItem = {
  actor: string;
  text: string;
  confidence: 'high' | 'medium';
  sourceDocTitle: string;
  sourceDocId: string;
  sourceChunkIndex: number;
  importedAt: string;
  fingerprint: string;
};

export type SuggestionAction = 'promoted' | 'completed' | 'dismissed';

export type SuggestionLogEntry = {
  fingerprint: string;
  actor: string;
  suggestionText: string;
  sourceDocTitle: string;
  sourceDocId: string;
  createdAt: string;
};

export type SuggestionLogResponse = {
  clientId: string;
  promoted: SuggestionLogEntry[];
  completed: SuggestionLogEntry[];
  dismissed: SuggestionLogEntry[];
};

export async function logSuggestionAction(
  clientId: string,
  payload: {
    fingerprint: string;
    action: SuggestionAction;
    actor: string;
    suggestionText: string;
    sourceDocTitle: string;
    sourceDocId: string;
  },
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/suggestions/log`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function getSuggestionLog(clientId: string): Promise<SuggestionLogResponse> {
  return request<SuggestionLogResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/suggestions/log`,
  );
}

export async function removeSuggestionLogEntry(clientId: string, fingerprint: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/suggestions/log/${encodeURIComponent(fingerprint)}`,
    { method: 'DELETE' },
  );
}

export type MeetingActionItemsResponse = {
  clientId: string;
  high: MeetingActionItem[];
  medium: MeetingActionItem[];
  totalHigh: number;
  totalMedium: number;
};

export async function getMeetingActionItems(clientId: string): Promise<MeetingActionItemsResponse> {
  return request<MeetingActionItemsResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/meeting-action-items`,
  );
}

export type NextStepItem = {
  fingerprint: string;
  kind: 'meeting' | 'commitment' | 'task' | 'meeting_action' | 'event_line';
  actor: string;
  text: string;
  dueDate: string;
  severity: 'high' | 'medium' | 'low';
  rawId: string;
  // 行动闭环对账附加字段(后端 next_step_reconciler 产出,旧前端可忽略)
  ownerSide?: 'us' | 'client' | 'both' | 'unknown';
  actionDirection?: 'do' | 'follow_up' | 'wait_for' | 'confirm' | 'unknown';
  mergedCount?: number;       // 合并了几条改写重复
  matchedTaskTitle?: string;  // 命中的已有任务
};

export type NextStepsResponse = {
  clientId: string;
  items: NextStepItem[];                // 清洗后的干净主候选(candidate_next_steps)
  total: number;
  consumedCount: number;
  // 分层附加(可选):前端不读也不影响
  possibleDuplicates?: NextStepItem[];
  needsReview?: NextStepItem[];
  matchedExistingCount?: number;
  invalidFilteredCount?: number;
  debugSummary?: Record<string, number>;
};

export async function getNextSteps(clientId: string): Promise<NextStepsResponse> {
  return request<NextStepsResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/next-steps`,
  );
}

export type NextStepBackgroundResponse = {
  background: string;
  sourceLabel: string;
  hasSource: boolean;
  fromCache: boolean;
};

export async function getNextStepBackground(
  clientId: string,
  payload: { fingerprint: string; kind: string; actor: string; text: string },
): Promise<NextStepBackgroundResponse> {
  return request<NextStepBackgroundResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/next-steps-background`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

// ──────────────────────────────────────────────────────────────────
// M1 · 字典属性 (glossary_attributes) 审核 API
// ──────────────────────────────────────────────────────────────────
export type GlossaryAttributeRecord = {
  id: string;
  term_id: string;
  term: string;
  attribute_name: string;
  value_category: string;
  value_text: string;
  value_normalized: number | null;
  value_unit: string;
  scope: string;
  as_of_date: string | null;
  source_type: string;
  source_evidence: string;
  source_doc_id: string | null;
  source_doc_title: string | null;
  source_doc_path: string | null;
  confidence: number;
  verification_status: 'pending' | 'verified' | 'rejected';
  verified_by: string | null;
  verified_at: string | null;
  rejection_note: string;
  created_at: string;
  updated_at: string;
};

export async function listGlossaryAttributes(
  clientId: string,
  status?: 'pending' | 'verified' | 'rejected',
): Promise<{ attributes: GlossaryAttributeRecord[] }> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return request<{ attributes: GlossaryAttributeRecord[] }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/glossary-attributes${qs}`,
  );
}

export interface GlossaryAttributeClarifyPayload {
  verifiedBy?: string;
  termId?: string;          // 改归属 term
  attributeName?: string;
  valueText?: string;
  valueUnit?: string;
  scope?: string;
  asOfDate?: string | null;
}

export async function verifyGlossaryAttribute(
  clientId: string,
  attrId: string,
  payload: GlossaryAttributeClarifyPayload = {},
): Promise<{ ok: boolean; id: string; status: string }> {
  const body: Record<string, unknown> = { verifiedBy: payload.verifiedBy ?? 'user' };
  for (const key of ['termId', 'attributeName', 'valueText', 'valueUnit', 'scope', 'asOfDate'] as const) {
    if (payload[key] !== undefined) body[key] = payload[key];
  }
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/glossary-attributes/${encodeURIComponent(attrId)}/verify`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
  );
}

// 统一待办 — 跨 tasks/action_items/commitments union
export interface UnifiedTodo {
  id: string;
  source: 'task' | 'meeting_action' | 'commitment';
  title: string;
  owner: string;
  due_date: string;
  status: string;
  direction: string;
  related_to: string;
  raw_id: string;
  severity: 'high' | 'medium' | 'low';
  /** "下一步要做什么" 区块转任务时, AI 从原文 chunk 总结的 80-100 字背景说明,
   *  promoteHandler 会用此预填任务编辑器 desc 字段, 让接手同事看到上下文 */
  description?: string;
}

export interface UnifiedTodosResponse {
  todos: UnifiedTodo[];
  total: number;
  by_source: { task: number; meeting_action: number; commitment: number };
  by_severity: { high: number; medium: number; low: number };
}

// ──────────────────────────────────────────────────────────────────
// 字典漂移告警 — 字典 verified 值 vs 新文件抽出事实冲突
// ──────────────────────────────────────────────────────────────────
export type GlossaryDriftAlertRecord = {
  id: string;
  client_id: string;
  glossary_attribute_id: string;
  new_fact_id: string;
  verified_value_text: string;
  new_value_text: string;
  severity: 'low' | 'medium' | 'high';
  review_status: 'pending' | 'resolved' | 'dismissed';
  review_note: string;
  detected_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  // JOIN fields
  term: string;
  attribute_name: string;
  scope: string | null;
  as_of_date: string | null;
};

export async function listGlossaryDriftAlerts(
  clientId: string,
  status: 'pending' | 'resolved' | 'dismissed' = 'pending',
): Promise<{ alerts: GlossaryDriftAlertRecord[] }> {
  return request<{ alerts: GlossaryDriftAlertRecord[] }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/glossary-drift-alerts?status=${encodeURIComponent(status)}`,
  );
}

export async function resolveGlossaryDriftAlert(
  clientId: string,
  alertId: string,
  action: 'update_glossary' | 'dismiss',
  note?: string,
): Promise<{ ok: boolean; id: string; action: string }> {
  return request<{ ok: boolean; id: string; action: string }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/glossary-drift-alerts/${encodeURIComponent(alertId)}/resolve`,
    {
      method: 'POST',
      body: JSON.stringify({ action, note: note || '' }),
    },
  );
}

export async function getUnifiedTodos(clientId: string): Promise<UnifiedTodosResponse> {
  return request<UnifiedTodosResponse>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/todos/unified`,
  );
}

export interface PromoteTodoPayload {
  title?: string;
  owner?: string;
  due_date?: string;
  description?: string;
  priority?: 'high' | 'medium' | 'low';
}

export async function promoteTodoToTask(
  clientId: string,
  todoId: string,
  payload: PromoteTodoPayload = {},
): Promise<{ ok: boolean; newTaskId: string; source: string }> {
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/todos/${encodeURIComponent(todoId)}/promote-to-task`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function dismissUnifiedTodo(
  clientId: string,
  todoId: string,
  action: 'complete' | 'cancel' = 'cancel',
): Promise<{ ok: boolean; id: string; source: string; action: string }> {
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/todos/${encodeURIComponent(todoId)}/dismiss`,
    { method: 'POST', body: JSON.stringify({ action }) },
  );
}

export async function rejectGlossaryAttribute(
  clientId: string,
  attrId: string,
  note = '',
): Promise<{ ok: boolean; id: string; status: string }> {
  return request(
    `/api/v1/clients/${encodeURIComponent(clientId)}/glossary-attributes/${encodeURIComponent(attrId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify({ note }),
    },
  );
}

// 本周概览顶部「客户脉搏」区块 - 所有客户的摘要 (用于横向一览谁本周有动态)
export type ClientPulseSummary = {
  clientId: string;
  clientName: string;
  clientStage: string;
  weeklyNewDocumentCount: number;
  weeklyNewTaskCount: number;
  weeklyNewEvidenceCount: number;
  currentBlockerCount: number;
  overdueTodoCount: number;
  hasActivity: boolean;
  topSignal: string;
};

export type ClientsPulseSummary = {
  summaries: ClientPulseSummary[];
  generatedAt: string;
};

export async function getClientsPulseSummary() {
  return request<ClientsPulseSummary>(`/api/v1/reviews/clients-pulse`);
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

// Stage 1：用户在客户工作台问答现场把答案沉淀为客户判断（写 judgment_versions）。
// 不必绕到战略陪伴 tab 再操作 —— 直接在答案下方点「采纳为判断」即可。
export async function promoteWorkspaceAnswerToJudgment(messageId: string, note?: string) {
  return request<WorkspaceAnswerActionCardResult>(
    `/api/v1/workspace-answer/${encodeURIComponent(messageId)}/promote-to-judgment`,
    {
      method: 'POST',
      body: JSON.stringify({ note: note || '' }),
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
  deepThinking?: boolean,
  activeSkillId?: string | null,
  creativityMode?: import('../../shared/types').CreativityMode,
) {
  const workingDocumentIds = Array.isArray(workingDocumentIdsOrOptions) ? workingDocumentIdsOrOptions : [];
  const requestOptions = Array.isArray(workingDocumentIdsOrOptions) ? options : workingDocumentIdsOrOptions;
  return request<ChatStartResponse>(`/api/v1/clients/${clientId}/workspace/chat/start`, {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      threadId,
      searchId,
      workingDocumentIds: workingDocumentIds || [],
      deepThinking: deepThinking === true,
      activeSkillId: activeSkillId || null,
      creativityMode: creativityMode || 'balanced',
    }),
    ...requestOptions,
  });
}

// ---------- R6: writing skills (写作风格 skill) ----------------------

export async function listWritingSkills() {
  return request<import('../../shared/types').WritingSkill[]>('/api/v1/writing-skills');
}

export async function createWritingSkill(payload: {
  name: string;
  description?: string;
  distilledMd: string;
  sortOrder?: number;
}) {
  return request<import('../../shared/types').WritingSkill>('/api/v1/writing-skills', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateWritingSkill(
  skillId: string,
  payload: {
    name?: string;
    description?: string;
    distilledMd?: string;
    sortOrder?: number;
  },
) {
  return request<import('../../shared/types').WritingSkill>(`/api/v1/writing-skills/${skillId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteWritingSkill(skillId: string) {
  return request<{ deleted: boolean; id: string }>(`/api/v1/writing-skills/${skillId}`, {
    method: 'DELETE',
  });
}

export async function distillWritingSkill(payload: { samples: string[]; skillName?: string }) {
  return request<import('../../shared/types').WritingSkillDistillResult>(
    '/api/v1/writing-skills/distill',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export async function getClientMessage(clientId: string, messageId: string) {
  return request<ChatMessage>(`/api/v1/clients/${clientId}/workspace/chat/messages/${messageId}`);
}

export async function getClientChatThread(clientId: string, threadId: string) {
  return request<ChatThreadDetailResponse>(`/api/v1/clients/${clientId}/workspace/chat/threads/${threadId}`);
}

export async function deleteClientChatMessagePair(clientId: string, messageId: string) {
  return request<{
    clientId: string;
    threadId: string;
    deletedIds: string[];
    threadDeleted: boolean;
    alreadyDeleted?: boolean;
  }>(
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

export async function cancelVectorizeAnswer(clientId: string, messageId: string) {
  return request<{ ok: boolean; surrogateId: string }>(
    `/api/v1/clients/${clientId}/knowledge/memory-cards/by-message/${encodeURIComponent(messageId)}`,
    { method: 'DELETE' },
  );
}

export async function getDocumentText(documentId: string) {
  return request<{ content: string; kind: string; title: string }>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/text`,
  );
}

export async function exportAnswer(
  clientId: string,
  messageIdOrIds: string | string[],
) {
  const body = Array.isArray(messageIdOrIds)
    ? { messageIds: messageIdOrIds }
    : { messageId: messageIdOrIds };
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(
    `/api/v1/clients/${clientId}/knowledge/export-answer`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
  );
}

export async function createClientTextDocument(clientId: string, payload: { title?: string | null; content: string }) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/documents/from-text`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// 覆盖式保存:把 markdown 渲染回原 docx 文件,documentId/path 不变。
// 用于「智能编辑器 → 保存」按钮:用户从 docx 打开编辑后期望覆盖原文件。
export async function updateDocumentContent(documentId: string, payload: { title?: string | null; content: string }) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/documents/${encodeURIComponent(documentId)}/content`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

// P9 / P11：客户工作台 inline 编辑器 AI 助手
//   action：7 个任务类型
//   userRequest：用户在 inline 提示框写的具体要求（可空）
//   creativityMode：creative=完全自由 / balanced=兼顾资料（默认）/ strict=严格依据
//   activeSkillId：写作风格 skill id（指向 writing_skills 表）
export type DocumentAiAction =
  // A 类 · 纯文本变换
  | 'expand'
  | 'rewrite_pro'
  | 'rewrite_short'
  | 'summarize'
  | 'extract'
  | 'translate'
  | 'style_distilled'
  // B 类 · 资料增强（P13b/c 接入；前端 UI 暂未暴露这些 op）
  | 'insert_from_materials'
  | 'rewrite_by_strategy'
  | 'insert_data_table';
export type DocumentAiCreativityMode = 'creative' | 'balanced' | 'strict';

// P13b+：资料源类型 + 规格 + 引证回包
export type DocumentAiContextSourceType =
  | 'selection_only'
  | 'current_doc'
  | 'client_materials'
  | 'strategy_dimension'
  | 'event_timeline';
export type DocumentAiContextSourceSpec = {
  type: DocumentAiContextSourceType;
  query?: string;
  refId?: string | null;
  topK?: number;
  params?: Record<string, unknown>;
};
export type DocumentAiSourceRef = {
  type: string;
  title: string;
  snippet?: string;
  refId?: string | null;
  extra?: Record<string, unknown>;
};
export type DocumentAiActionResponse = {
  content: string;
  action: string;
  durationMs: number;
  sources?: DocumentAiSourceRef[];
  effectiveCreativity?: DocumentAiCreativityMode;
  // 后端实际作用范围。
  // "selection"     = 用户框选了一段,生成内容替换选区
  // "cursor_insert" = 用户无选区,生成内容在光标位置插入,不动其他内容
  // "full_doc"      = 替换整篇(老路径,目前后端只在 fallback 用)
  targetScope?: 'selection' | 'cursor_insert' | 'full_doc';
};

export async function documentAiAction(
  clientId: string,
  payload: {
    content: string;
    action: DocumentAiAction;
    userRequest?: string;
    creativityMode?: DocumentAiCreativityMode;
    activeSkillId?: string | null;
    contextSources?: DocumentAiContextSourceSpec[];
    // P14a：用户在编辑器框选的裸文本。空 = 处理整篇。
    selectionText?: string;
    // 用户从右侧文件列表 attach 到对话引用的 document_id 列表(跟 chat 共用 state)。
    // 后端会作为 priority_document_ids 优先召回。
    workingDocumentIds?: string[];
  },
) {
  return request<DocumentAiActionResponse>(
    `/api/v1/clients/${clientId}/documents/ai-action`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
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

export async function listClientLinkMaterialImportRuns(clientId: string, limit = 20) {
  return request<LinkMaterialImportRun[]>(
    `/api/v1/clients/${clientId}/link-materials/import-runs?limit=${limit}`,
  );
}

export async function cancelClientLinkMaterialImportRun(clientId: string, runId: string) {
  return request<LinkMaterialImportRun>(
    `/api/v1/clients/${clientId}/link-materials/import-runs/${runId}/cancel`,
    { method: 'POST' },
  );
}

export interface ActiveBackgroundTask {
  kind: string;
  label: string;
  status?: string;
  severity?: 'loss' | 'queued';
}

export async function getActiveBackgroundTasks() {
  return request<{ tasks: ActiveBackgroundTask[]; count: number }>(
    `/api/v1/system/active-background-tasks`,
  );
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

export type RecordingTranscriptSegment = {
  startMs: number;
  endMs: number;
  text: string;
  emotion?: string | null;
  event?: string | null;
  speakerId?: string | null;
};

export type RecordingTranscribeResponse = {
  success: boolean;
  text: string;
  durationMs: number;
  elapsedMs: number;
  language: string;
  segments: RecordingTranscriptSegment[];
  sourceFormat: string;
  transcodedToWav: boolean;
  /** "说话人A：...\n说话人B：..."；diarization 未启用时为空或与 text 相同 */
  dialogueText: string;
  numSpeakers: number;
  diarizationUsed: boolean;
  diarizationError?: string | null;
  errorMessage?: string | null;
};

export async function transcribeRecordingLocalAudio(payload: {
  audioPath: string;
  language?: string;
}) {
  return request<RecordingTranscribeResponse>(
    '/api/v1/recordings/transcribe-local-audio',
    {
      method: 'POST',
      body: JSON.stringify({
        audioPath: payload.audioPath,
        language: payload.language || 'auto',
      }),
    },
  );
}

export type RecordingMeetingMinutesResponse = {
  success: boolean;
  title: string;
  minutesMd: string;
  errorMessage?: string | null;
};

export async function summarizeRecordingMeetingMinutes(payload: {
  transcript: string;
  taskTitleHint?: string;
  languageHint?: string;
  dialogueText?: string;
  numSpeakers?: number;
}) {
  return request<RecordingMeetingMinutesResponse>(
    '/api/v1/recordings/summarize-meeting-minutes',
    {
      method: 'POST',
      body: JSON.stringify({
        transcript: payload.transcript,
        taskTitleHint: payload.taskTitleHint || '',
        languageHint: payload.languageHint || '',
        dialogueText: payload.dialogueText || '',
        numSpeakers: payload.numSpeakers || 0,
      }),
    },
  );
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

// 删附件：syncKnowledge=true 时连带删除数据中心里的文档行 + 物理文件。
// 用户点附件 × 按钮 → 弹窗里勾选 "同步删除数据中心" 默认勾选 → 调这里。
export async function deleteTaskAttachment(
  taskId: string,
  attachmentId: string,
  syncKnowledge: boolean,
) {
  const qs = syncKnowledge ? '?syncKnowledge=true' : '?syncKnowledge=false';
  return request<{ deleted: boolean; knowledgeDeleted: boolean; fileDeleted: boolean }>(
    `/api/v1/tasks/${taskId}/attachments/${attachmentId}${qs}`,
    { method: 'DELETE' },
  );
}

// 录音会议纪要专用：前端发 markdown 原文，后端用 python-docx 转 .docx 后挂附件。
// 这样用户在任务详情双击附件直接用 Word/Pages 打开，不用面对 .md 源码。
export async function uploadTaskAttachmentFromMarkdown(
  taskId: string,
  payload: {
    title: string;
    markdown: string;
    clientId?: string | null;
    eventLineId?: string | null;
    taskTitle?: string | null;
  },
) {
  return request<Task>(`/api/v1/tasks/${taskId}/attachments/from-markdown`, {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      markdown: payload.markdown,
      clientId: payload.clientId ?? null,
      eventLineId: payload.eventLineId ?? null,
      taskTitle: payload.taskTitle ?? null,
    }),
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

export async function getEventLineTimelineNarrative(id: string) {
  return request<EventLineTimelineNarrative | null>(`/api/v1/event-lines/${id}/timeline-narrative`);
}

export async function regenerateEventLineTimelineNarrative(id: string, trigger: string = 'manual') {
  return request<EventLineTimelineNarrative>(`/api/v1/event-lines/${id}/timeline-narrative/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ trigger }),
  });
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

export async function previewEventLineMerge(targetId: string, sourceIds: string[]) {
  return request<import('../../shared/types').EventLineMergePreview>(
    `/api/v1/event-lines/${targetId}/merge-preview`,
    {
      method: 'POST',
      body: JSON.stringify({ sourceIds }),
    },
  );
}

export async function mergeEventLines(targetId: string, sourceIds: string[]) {
  return request<EventLine>(`/api/v1/event-lines/${targetId}/merge`, {
    method: 'POST',
    body: JSON.stringify({ sourceIds }),
  });
}

export async function getTaskPlanLink(taskId: string) {
  return request<TaskPlanLinkRecord | null>(`/api/v1/tasks/${taskId}/plan-link`);
}

export async function patchTaskPlanLink(taskId: string, payload: TaskPlanLinkUpsertPayload) {
  return request<TaskPlanLinkRecord | null>(`/api/v1/tasks/${taskId}/plan-link`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function recomputeTaskPlanLink(taskId: string) {
  return request<TaskPlanLinkRecord | null>(`/api/v1/tasks/${taskId}/plan-link/recompute`, {
    method: 'POST',
  });
}

// [B] 2026-05-26 · 新建任务时, qwen2.5:7b 闪电预测 plan item.
// 顾源源 5/26 拍板: 7B 模型秒级识别 + 识别不了不挂 (不做 keyword 兜底).
export interface PlanLinkPredictRequest {
  title: string;
  description: string;
  planItems: Array<{ id: string; title: string; statement?: string }>;
}
export interface PlanLinkPredictResponse {
  planItemId: string | null;
  confidence: number;
  model: string;
  reason: string;
}
export async function predictPlanLinkFromText(payload: PlanLinkPredictRequest): Promise<PlanLinkPredictResponse> {
  return request<PlanLinkPredictResponse>('/api/v1/plan-link/predict-from-text', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTasksForPlanItem(itemId: string) {
  return request<Task[]>(`/api/v1/org-model/plan-items/${itemId}/tasks`);
}

export async function getPlanItemTaskCounts(): Promise<Record<string, number>> {
  return request<Record<string, number>>('/api/v1/org-model/plan-item-task-counts');
}

export interface ParsedPlanItem {
  title: string;
  statement: string;
  expectedOutput: string;
}

export interface ParsedPlanResponse {
  items: ParsedPlanItem[];
  summary: string;
  confidence: 'low' | 'medium' | 'high';
}

export async function parseDepartmentPlan(payload: {
  text: string;
  organizationName?: string;
  scopeKind?: 'org' | 'department';
  scopeName?: string;
  periodKey?: string;
  cycleType?: 'month' | 'quarter' | 'year' | 'week' | 'custom';
}) {
  return request<ParsedPlanResponse>('/api/v1/org-model/plans/parse', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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

export async function getDepartmentSignals(params: {
  weekLabel?: string | null;
  perspective?: 'organization' | 'department' | 'mine';
  departmentId?: string | null;
  signal?: AbortSignal;
}) {
  const search = new URLSearchParams();
  if (params.weekLabel) search.set('weekLabel', params.weekLabel);
  if (params.perspective) search.set('perspective', params.perspective);
  if (params.departmentId) search.set('departmentId', params.departmentId);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<DepartmentSignalsResponse>(`/api/v1/reviews/department-signals${suffix}`, {
    signal: params.signal,
  });
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

// ──────────────────────────────────────────────────────────────────────
// 报告生成器 · 5 个 endpoint client
// ──────────────────────────────────────────────────────────────────────

export async function draftReportBlueprint(
  payload: import('../../shared/types.js').DraftBlueprintRequest,
): Promise<import('../../shared/types.js').ReportRunSummary> {
  return request<import('../../shared/types.js').ReportRunSummary>(
    '/api/v1/reports/draft-blueprint',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  );
}

export async function draftReportSections(
  reportRunId: string,
  payload: import('../../shared/types.js').DraftSectionsRequest = {},
): Promise<import('../../shared/types.js').ReportRunSummary> {
  return request<import('../../shared/types.js').ReportRunSummary>(
    `/api/v1/reports/${encodeURIComponent(reportRunId)}/draft-sections`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  );
}

export async function renderReport(
  reportRunId: string,
  format: import('../../shared/types.js').ReportFileFormat = 'docx',
): Promise<import('../../shared/types.js').ReportRunSummary> {
  return request<import('../../shared/types.js').ReportRunSummary>(
    `/api/v1/reports/${encodeURIComponent(reportRunId)}/render?format=${format}`,
    { method: 'POST' },
  );
}

export async function getReportRun(
  reportRunId: string,
): Promise<import('../../shared/types.js').ReportRunSummary> {
  return request<import('../../shared/types.js').ReportRunSummary>(
    `/api/v1/reports/${encodeURIComponent(reportRunId)}`,
  );
}

export function getReportFileDownloadUrl(
  reportRunId: string,
  format: import('../../shared/types.js').ReportFileFormat,
): string {
  return (
    `${baseUrl}/api/v1/reports/${encodeURIComponent(reportRunId)}/files/${format}`
  );
}

// ──────────────────────────────────────────────────────────────────────
// 客户项目情报流（同事 push 的新一代资讯情报 API）—— 2026-05-13 补回
// 来源：origin-main-backup-before-force-push-2026-05-13 tag 中 api.ts L2993-3120
// IntelligenceStationView.tsx 依赖这些函数；force push 时漏带，现在补回
// ──────────────────────────────────────────────────────────────────────

export async function getIntelligenceWorkObjects() {
  return request<IntelligenceWorkObject[]>('/api/v1/intelligence/work-objects');
}

export async function getIntelligenceSourceDiagnostics(params: {
  scopeType: IntelligenceWorkObject['type'];
  scopeId: string;
  contentKind?: IntelligenceItem['contentKind'];
}) {
  const query = new URLSearchParams();
  query.set('scopeType', params.scopeType);
  query.set('scopeId', params.scopeId);
  if (params.contentKind) query.set('contentKind', params.contentKind);
  return request<IntelligenceSourceDiagnosticsResponse>(`/api/v1/intelligence/source-diagnostics?${query.toString()}`);
}

export async function getIntelligenceFocusDirectives() {
  return request<IntelligenceFocusDirective[]>('/api/v1/intelligence/focus-directives');
}

export async function saveIntelligenceFocusDirective(payload: IntelligenceFocusDirectivePayload) {
  return request<IntelligenceFocusDirective>('/api/v1/intelligence/focus-directives', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getIntelligenceItems(params: {
  contentKind?: IntelligenceItem['contentKind'];
  workObjectType?: IntelligenceWorkObject['type'];
  workObjectId?: string;
  sort?: 'published_desc' | 'published_asc' | 'captured_desc' | 'captured_asc';
  page?: number;
  pageSize?: number;
} = {}) {
  const query = new URLSearchParams();
  if (params.contentKind) query.set('contentKind', params.contentKind);
  if (params.workObjectType) query.set('workObjectType', params.workObjectType);
  if (params.workObjectId) query.set('workObjectId', params.workObjectId);
  if (params.sort) query.set('sort', params.sort);
  if (params.page) query.set('page', String(params.page));
  if (params.pageSize) query.set('pageSize', String(params.pageSize));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<IntelligenceItemsResponse>(`/api/v1/intelligence/items${suffix}`);
}

export async function refreshIntelligenceSupply(payload: IntelligenceRefreshPayload) {
  return request<IntelligenceRefreshResult>('/api/v1/intelligence/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getIntelligenceRefreshRuns(params: {
  contentKind?: IntelligenceContentKind;
  workObjectType?: IntelligenceWorkObject['type'];
  workObjectId?: string;
  activeOnly?: boolean;
  limit?: number;
} = {}) {
  const query = new URLSearchParams();
  if (params.contentKind) query.set('contentKind', params.contentKind);
  if (params.workObjectType) query.set('scopeType', params.workObjectType);
  if (params.workObjectId) query.set('scopeId', params.workObjectId);
  if (typeof params.activeOnly === 'boolean') query.set('activeOnly', String(params.activeOnly));
  if (params.limit) query.set('limit', String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<IntelligenceRefreshRun[]>(`/api/v1/intelligence/refresh-runs${suffix}`);
}

export async function getIntelligenceRefreshCycleSettings() {
  return request<IntelligenceRefreshCycleSettings>('/api/v1/intelligence/refresh-cycle-settings');
}

export async function updateIntelligenceRefreshCycleSettings(payload: IntelligenceRefreshCycleSettingsPayload) {
  return request<IntelligenceRefreshCycleSettings>('/api/v1/intelligence/refresh-cycle-settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getIntelligenceVerificationRules(params?: {
  scopeType?: IntelligenceVerificationRulePayload['scopeType'];
  scopeId?: string | null;
}) {
  const query = new URLSearchParams();
  if (params?.scopeType) query.set('scopeType', params.scopeType);
  if (params?.scopeId) query.set('scopeId', params.scopeId);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<IntelligenceVerificationRule[]>(`/api/v1/intelligence/verification-rules${suffix}`);
}

export async function saveIntelligenceVerificationRules(payload: IntelligenceVerificationRulePayload) {
  return request<IntelligenceVerificationRule>('/api/v1/intelligence/verification-rules', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function submitIntelligenceVerificationFeedback(payload: IntelligenceVerificationFeedbackPayload) {
  return request<IntelligenceVerificationRule>('/api/v1/intelligence/verification-feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function dismissIntelligenceItem(id: string, payload: IntelligenceDismissPayload) {
  return request<IntelligenceItem>(`/api/v1/intelligence/items/${id}/dismiss`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function followIntelligenceItem(id: string, payload: IntelligenceFollowPayload) {
  return request<IntelligenceItem>(`/api/v1/intelligence/items/${id}/follow`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getIntelligenceTaskDraft(id: string) {
  return request<IntelligenceTaskDraftResponse>(`/api/v1/intelligence/items/${id}/task-draft`, { method: 'POST' });
}

export async function createIntelligenceTask(id: string, payload: IntelligenceTaskCreatePayload) {
  return request<IntelligenceTaskCreateResponse>(`/api/v1/intelligence/items/${id}/tasks`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function askIntelligenceItemQuestion(id: string, payload: TopicCandidateChatPayload) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 25000);
  try {
    return await request<IntelligenceItemChatResponse>(`/api/v1/intelligence/items/${id}/chat`, {
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

// captureTopicRadars 已在 line 3426 定义，从同事 backup append 段里的重复已删除

// ──────────────────────────────────────────────────────────
// 舆情监控 API（P2-a · 2026-05-17）
// ──────────────────────────────────────────────────────────

export type SentimentItem = {
  id: string;
  title: string;
  summary: string;
  source: string;
  sourceUrl: string;
  capturedAt: string;
  sentimentLabel: 'negative' | 'neutral' | 'positive';
  sentimentReason: string;
  tags: string[];
  userStatus: string;
};

export type SentimentProfile = {
  withinDays: number;
  totalMentions: number;
  sentimentScore: number;
  negativeCount: number;
  neutralCount: number;
  positiveCount: number;
  topNegativeSources: { source: string; count: number }[];
  topSources: { source: string; count: number }[];
};

export type SentimentRefreshResult = {
  targetName: string;
  fetchedCount: number;
  insertedCount: number;
  negativeCount: number;
  neutralCount: number;
  positiveCount: number;
};

export async function refreshSentiment(payload: {
  clientId?: string;
  projectModuleId?: string;
  targetName?: string;
  businessLine?: string;
  maxPerQuery?: number;
}) {
  return request<SentimentRefreshResult>('/api/v1/intelligence/sentiment/refresh', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listSentimentItems(params: {
  clientId?: string;
  projectModuleId?: string;
  withinDays?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params.clientId) query.set('clientId', params.clientId);
  if (params.projectModuleId) query.set('projectModuleId', params.projectModuleId);
  if (params.withinDays) query.set('withinDays', String(params.withinDays));
  if (params.limit) query.set('limit', String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<{ items: SentimentItem[]; total: number }>(`/api/v1/intelligence/sentiment/items${suffix}`);
}

export async function getSentimentProfile(params: {
  clientId?: string;
  projectModuleId?: string;
  withinDays?: number;
}) {
  const query = new URLSearchParams();
  if (params.clientId) query.set('clientId', params.clientId);
  if (params.projectModuleId) query.set('projectModuleId', params.projectModuleId);
  if (params.withinDays) query.set('withinDays', String(params.withinDays));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<SentimentProfile>(`/api/v1/intelligence/sentiment/profile${suffix}`);
}

export type SentimentFeedbackAction =
  | 'confirm_negative'
  | 'mark_misclassified'
  | 'mark_resolved'
  | 'restore';

export type SentimentFeedbackResult = {
  itemId: string;
  action: SentimentFeedbackAction;
  userStatus: string;
  updatedAt: string;
};

export async function sendSentimentFeedback(payload: {
  itemId: string;
  action: SentimentFeedbackAction;
  notes?: string;
}) {
  return request<SentimentFeedbackResult>('/api/v1/intelligence/sentiment/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ──────────────────────────────────────────────────────────
// 印象主题（P5-A）+ 定位差异（P5-B）+ 主题溯源（P5-#4）
// ──────────────────────────────────────────────────────────

export type SentimentTheme = {
  id: string;
  themeLabel: string;
  themeSummary: string;
  sentimentTone: 'negative' | 'neutral' | 'positive';
  itemCount: number;
  representativeQuote: string;
  representativeItemId: string | null;
  itemIds: string[];
  computedAt: string;
  expiresAt: string;
};

export type SentimentThemesResponse = {
  themes: SentimentTheme[];
  total: number;
  recomputeNote: string | null;
};

export type ThemeItemSource = {
  id: string;
  title: string;
  summary: string;
  source: string;
  sourceUrl: string;
  capturedAt: string;
  sentimentLabel: 'negative' | 'neutral' | 'positive';
  sentimentReason: string;
};

export type ThemeItemsResponse = {
  ok: boolean;
  theme: SentimentTheme;
  items: ThemeItemSource[];
};

export type GapAlignmentStatus = 'affirmed' | 'gap' | 'silent';

export type GapAlignment = {
  proposition: string;
  status: GapAlignmentStatus;
  reason: string;
  supportingThemes: { id: string; label: string }[];
  conflictingThemes: { id: string; label: string }[];
};

export type PositioningGapResponse = {
  ok: boolean;
  reason?: string;
  propositions: string[];
  themes: SentimentTheme[];
  alignments: GapAlignment[];
  unexpectedThemes: { id: string; label: string }[];
};

export async function recomputeSentimentThemes(payload: {
  clientId?: string;
  projectModuleId?: string;
  targetName?: string;
  withinDays?: number;
}) {
  return request<{ ok: boolean; reason?: string; themes: SentimentTheme[] }>(
    '/api/v1/intelligence/sentiment/themes/recompute',
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function listSentimentThemes(params: {
  clientId?: string;
  projectModuleId?: string;
  autoRecompute?: boolean;
}) {
  const q = new URLSearchParams();
  if (params.clientId) q.set('clientId', params.clientId);
  if (params.projectModuleId) q.set('projectModuleId', params.projectModuleId);
  if (params.autoRecompute === false) q.set('autoRecompute', 'false');
  const suffix = q.toString() ? `?${q.toString()}` : '';
  return request<SentimentThemesResponse>(`/api/v1/intelligence/sentiment/themes${suffix}`);
}

export async function getThemeItems(themeId: string, limit = 10) {
  return request<ThemeItemsResponse>(
    `/api/v1/intelligence/sentiment/themes/${encodeURIComponent(themeId)}/items?limit=${limit}`,
  );
}

export async function getPositioningGap(params: {
  clientId?: string;
  projectModuleId?: string;
}) {
  const q = new URLSearchParams();
  if (params.clientId) q.set('clientId', params.clientId);
  if (params.projectModuleId) q.set('projectModuleId', params.projectModuleId);
  const suffix = q.toString() ? `?${q.toString()}` : '';
  return request<PositioningGapResponse>(`/api/v1/intelligence/sentiment/gap${suffix}`);
}

export async function getClientBrandProposition(clientId: string) {
  return request<{ clientId: string; brandProposition: string }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/brand-proposition`,
  );
}

export async function updateClientBrandProposition(clientId: string, brandProposition: string) {
  return request<{ clientId: string; brandProposition: string; updatedAt: string }>(
    `/api/v1/clients/${encodeURIComponent(clientId)}/brand-proposition`,
    { method: 'PATCH', body: JSON.stringify({ brandProposition }) },
  );
}

// ──────────────────────────────────────────────────────────
// 品牌印象速读（P6）
// ──────────────────────────────────────────────────────────

export type BrandAuditTension = {
  statement: string;
  selfAnchor: string;
  publicAnchor: string;
};

export type BrandAuditRecommendation = {
  action: string;
  rationale: string;
  priority: 'high' | 'medium' | 'low';
};

export type BrandAuditContentAngles = {
  amplify: string[];
  new: string[];
  // P9 2026-05-19：reduce 已弃用——"让客户少说什么"是高风险判断
  // 保留 optional 字段兼容旧 audit JSON，但新生成不再产出，UI 也不再渲染
  reduce?: string[];
};

export type BrandAudit = {
  id: string;
  scopeType: string;
  scopeId: string;
  headline: string;
  narrativeMd: string;
  tensions: BrandAuditTension[];
  recommendations: BrandAuditRecommendation[];
  contentAngles: BrandAuditContentAngles;
  evidenceThemeIds: string[];
  computedAt: string;
  expiresAt: string;
};

export type BrandAuditResponse = {
  audit: BrandAudit | null;
  recomputeNote: string | null;
};

export async function getBrandAudit(params: {
  clientId?: string;
  projectModuleId?: string;
  autoRecompute?: boolean;
}) {
  const q = new URLSearchParams();
  if (params.clientId) q.set('clientId', params.clientId);
  if (params.projectModuleId) q.set('projectModuleId', params.projectModuleId);
  if (params.autoRecompute === false) q.set('autoRecompute', 'false');
  const suffix = q.toString() ? `?${q.toString()}` : '';
  return request<BrandAuditResponse>(`/api/v1/intelligence/sentiment/audit${suffix}`);
}

export async function recomputeBrandAudit(payload: {
  clientId?: string;
  projectModuleId?: string;
  targetName?: string;
}) {
  return request<{ ok: boolean; reason?: string; audit: BrandAudit | null }>(
    '/api/v1/intelligence/sentiment/audit/recompute',
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

// ──────────────────────────────────────────────────────────
// P13-D 品牌镜子 (brand mirror) - 后端 LLM 画像快照
// ──────────────────────────────────────────────────────────

import type { BrandMirrorSnapshot } from '../../shared/types';

export async function fetchBrandMirrorSnapshot(clientId: string) {
  return request<{ snapshot: BrandMirrorSnapshot | null }>(
    `/api/v1/intelligence/brand-mirror/analyze?clientId=${encodeURIComponent(clientId)}`,
  );
}

export async function triggerBrandMirrorAnalysis(clientId: string) {
  return request<BrandMirrorSnapshot & { snapshotId: string; clientId: string }>(
    '/api/v1/intelligence/brand-mirror/analyze',
    { method: 'POST', body: JSON.stringify({ clientId }) },
  );
}

// P14-D 战略推演树 (从战略陪伴上传的 strategy.md + methodology.md LLM 抽取)
import type { BrandStrategyExtract } from '../../shared/types';
export type { BrandStrategyExtract };

export async function fetchBrandStrategyExtract(clientId: string) {
  return request<{ extract: BrandStrategyExtract | null }>(
    `/api/v1/intelligence/brand-mirror/strategy-extract?clientId=${encodeURIComponent(clientId)}`,
  );
}

export async function triggerBrandStrategyExtraction(clientId: string) {
  return request<BrandStrategyExtract>(
    '/api/v1/intelligence/brand-mirror/strategy-extract',
    { method: 'POST', body: JSON.stringify({ clientId }) },
  );
}

/** 用户手动编辑 LLM 抽取的战略主张 + 方法学 (200 字以内). 不影响 stakeholders / sources / hash. */
export async function updateBrandStrategyExtract(
  clientId: string,
  payload: { strategicObjective: string; methodology: string },
) {
  return request<{ extract: BrandStrategyExtract }>(
    '/api/v1/intelligence/brand-mirror/strategy-extract',
    { method: 'PUT', body: JSON.stringify({ clientId, ...payload }) },
  );
}

// ──────────────────────────────────────────────────────────
// Phase 3：本地 AI 推理调度 health / queue
// ──────────────────────────────────────────────────────────

export type LocalAiHealthRecord = {
  verdict: 'go' | 'wait' | 'skip';
  reason: string;
  retry_after_seconds: number;
  summary: string;
  thermal_state: number;
  cpu_speed_limit: number;
  user_idle_seconds: number;
  battery_percent: number;
  on_ac_power: boolean;
  memory_pressure: 'normal' | 'warn' | 'critical' | 'unknown';
  ollama_reachable: boolean;
  in_run_window: boolean;
  enabled: boolean;
  paused: boolean;
};

export type LocalAiTaskRecord = {
  id: string;
  task_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  priority: number;
  client_id: string | null;
  knowledge_document_id: string | null;
  model_profile_id: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  locked_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  payload_preview: string;
  result_preview: string;
};

export type LocalAiQueueResponse = {
  tasks: LocalAiTaskRecord[];
  totalByStatus: Record<string, number>;
  filter: { status: string | null; task_type: string | null; limit: number };
};

export type LocalAiRunNowResponse = {
  processed: number;
  failed: number;
  skipped: number;
  status: string;
  governor_reason?: string;
  governor_retry_after?: number;
};

export async function getLocalAiHealth(): Promise<LocalAiHealthRecord> {
  return request<LocalAiHealthRecord>('/api/v1/local-ai/health');
}

export async function getLocalAiQueue(params?: {
  status?: string;
  taskType?: string;
  limit?: number;
}): Promise<LocalAiQueueResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.append('status', params.status);
  if (params?.taskType) query.append('task_type', params.taskType);
  if (params?.limit !== undefined) query.append('limit', String(params.limit));
  const qs = query.toString();
  return request<LocalAiQueueResponse>(
    `/api/v1/local-ai/queue${qs ? `?${qs}` : ''}`,
  );
}

export async function runLocalAiNow(force = false): Promise<LocalAiRunNowResponse> {
  return request<LocalAiRunNowResponse>(
    `/api/v1/local-ai/run-now?force=${force ? 'true' : 'false'}`,
    { method: 'POST' },
  );
}

// ── 深度解析(深读)设置 / 覆盖率 / 存量补齐 ────────────────────────
export type LocalAiOptimizationSettings = {
  enabled: boolean;
  paused: boolean;
  manualActive: boolean;
  parseModelMode: 'online' | 'local';
  priorityClientId?: string | null;
  dailyWindows: { start: string; end: string }[];
  autoEnqueueDocumentCards: boolean;
  requireACPower: boolean;
  minIdleSeconds: number;
  [key: string]: unknown;
};

export type LocalAiClientCoverage = {
  clientId: string;
  documents: number;
  deepRead: number;
  coverage: number;
};

export type LocalAiCoverageResponse = {
  perClient: LocalAiClientCoverage[];
  totalDocuments: number;
  totalDeepRead: number;
  overallCoverage: number;
};

export type LocalAiBackfillResponse = {
  scope: string;
  created: number;
  attempted: number;
  documents: number;
  taskTypes: string[];
};

export async function getLocalAiSettings(): Promise<LocalAiOptimizationSettings> {
  return request<LocalAiOptimizationSettings>('/api/v1/local-ai/settings');
}

/** patch 语义：后端会 merge 到当前设置，只传要改的字段即可。 */
export async function updateLocalAiSettings(
  patch: Partial<LocalAiOptimizationSettings>,
): Promise<LocalAiOptimizationSettings> {
  return request<LocalAiOptimizationSettings>('/api/v1/local-ai/settings', {
    method: 'PUT',
    body: JSON.stringify(patch),
  });
}

export async function getLocalAiCoverage(clientId?: string): Promise<LocalAiCoverageResponse> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return request<LocalAiCoverageResponse>(`/api/v1/local-ai/coverage${qs}`);
}

/** 存量补齐：clientId 省略=全库。只入队，不在此跑。 */
export async function backfillLocalAi(clientId?: string): Promise<LocalAiBackfillResponse> {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : '';
  return request<LocalAiBackfillResponse>(`/api/v1/local-ai/backfill${qs}`, { method: 'POST' });
}

// ============================================================
// P15 · 智能文件导入 (Smart File Import / 故事线导入)
// ============================================================

export type SmartImportSessionStatus =
  | 'drafting' | 'parsing' | 'ready_for_review' | 'imported' | 'discarded';

export interface SmartImportSession {
  id: string;
  client_id: string | null;
  project_event_line_id: string | null;
  narrator_user_id: string;
  title: string;
  status: SmartImportSessionStatus;
  total_chunks: number;
  total_files: number;
  created_at: string;
  updated_at: string;
  imported_at: string | null;
}

export interface SmartImportStagedFile {
  id: string;
  session_id: string;
  original_filename: string;
  storage_path: string;
  size_bytes: number;
  mime_type: string;
  assigned_chunk_id: string | null;
  role_override: string | null;
  document_id: string | null;
  document_inserted_at: string | null;
  upload_at: string;
}

export interface SmartImportParsedEntity {
  name?: string;
  kind?: string;
  role_in_project?: string;
}

export interface SmartImportParsedRelationship {
  from?: string;
  to?: string;
  type?: string;
  description?: string;
}

export interface SmartImportParsedFileClassification {
  original_filename?: string;
  role?: string;
  subject_entity_name?: string;
  evidence_tier?: string;
  narrator_hint?: string;
  confidence?: number;
}

export interface SmartImportParsedChunkOutput {
  entities?: SmartImportParsedEntity[];
  relationships?: SmartImportParsedRelationship[];
  events?: Array<{ happened_at?: string; actor?: string; action?: string; target?: string; summary?: string }>;
  opinions?: Array<{ holder?: string; subject?: string; polarity?: string; raw_quote?: string }>;
  files_classified?: SmartImportParsedFileClassification[];
  files_suggested_to_attach?: Array<{ original_filename?: string; reason?: string }>;
  commitments?: Array<{ committer?: string; recipient?: string; content?: string; commitment_type?: string; deadline?: string | null; status?: string }>;
  risk_signals?: Array<{ title?: string; severity?: string; description?: string; subject?: string; signal_kind?: string }>;
  open_questions?: string[];
}

export interface SmartImportChunk {
  id: string;
  session_id: string;
  sequence: number;
  raw_text: string;
  parsed_json: string;
  parsed: SmartImportParsedChunkOutput;
  parse_status: 'pending' | 'parsing' | 'parsed' | 'failed';
  parse_error: string;
  user_edited_parsed: number;
  created_at: string;
  updated_at: string;
}

export interface SmartImportSessionState {
  session: SmartImportSession;
  chunks: SmartImportChunk[];
  staged_files: SmartImportStagedFile[];
}

export interface SmartImportPreviewPlan {
  session_id: string;
  chunks_total: number;
  chunks_parsed: number;
  chunks_failed: Array<{ chunk_id: string; sequence: number }>;
  entities: SmartImportParsedEntity[];
  relationships: SmartImportParsedRelationship[];
  events: SmartImportParsedChunkOutput['events'];
  opinions: SmartImportParsedChunkOutput['opinions'];
  commitments: SmartImportParsedChunkOutput['commitments'];
  risk_signals: SmartImportParsedChunkOutput['risk_signals'];
  files_classified: SmartImportParsedFileClassification[];
  files_suggested_to_attach: Array<{ original_filename?: string; reason?: string }>;
  open_questions: string[];
}

export interface SmartImportCommitStats {
  entities_created: number;
  atomic_facts_created: number;
  commitments_created: number;
  risk_signals_created: number;
  events_created: number;
  documents_created: number;
  errors: string[];
}

export async function createSmartImportSession(payload: {
  clientId?: string;
  projectEventLineId?: string;
  title?: string;
}): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>('/api/v1/smart-import/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSmartImportSession(sessionId: string): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>(`/api/v1/smart-import/sessions/${sessionId}`);
}

export async function updateSmartImportSession(
  sessionId: string,
  payload: { clientId?: string; projectEventLineId?: string; title?: string },
): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>(`/api/v1/smart-import/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function discardSmartImportSession(sessionId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/smart-import/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export async function uploadSmartImportFile(
  sessionId: string,
  file: File,
): Promise<SmartImportStagedFile> {
  const formData = new FormData();
  formData.append('file', file, file.name);
  return requestForm<SmartImportStagedFile>(`/api/v1/smart-import/sessions/${sessionId}/files`, formData);
}

export async function deleteSmartImportFile(fileId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/smart-import/files/${fileId}`, { method: 'DELETE' });
}

export async function assignSmartImportFile(
  fileId: string,
  chunkId: string | null,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/smart-import/files/${fileId}/assign`, {
    method: 'PATCH',
    body: JSON.stringify({ chunkId }),
  });
}

export async function addSmartImportChunk(
  sessionId: string,
  payload: { rawText: string; fileIds?: string[]; autoParse?: boolean },
): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>(`/api/v1/smart-import/sessions/${sessionId}/chunks`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateSmartImportChunk(
  chunkId: string,
  payload: { rawText: string; autoParse?: boolean },
): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>(`/api/v1/smart-import/chunks/${chunkId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteSmartImportChunk(chunkId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/v1/smart-import/chunks/${chunkId}`, { method: 'DELETE' });
}

export async function parseSmartImportChunk(chunkId: string): Promise<{ ok: boolean; parsed: SmartImportParsedChunkOutput }> {
  return request<{ ok: boolean; parsed: SmartImportParsedChunkOutput }>(
    `/api/v1/smart-import/chunks/${chunkId}/parse`,
    { method: 'POST' },
  );
}

export async function patchSmartImportChunkParsed(
  chunkId: string,
  parsed: SmartImportParsedChunkOutput,
): Promise<SmartImportSessionState> {
  return request<SmartImportSessionState>(`/api/v1/smart-import/chunks/${chunkId}/parsed`, {
    method: 'PATCH',
    body: JSON.stringify({ parsed }),
  });
}

export async function getSmartImportPreview(sessionId: string): Promise<SmartImportPreviewPlan> {
  return request<SmartImportPreviewPlan>(`/api/v1/smart-import/sessions/${sessionId}/preview`);
}

export async function commitSmartImportSession(sessionId: string): Promise<{ ok: boolean; stats: SmartImportCommitStats }> {
  return request<{ ok: boolean; stats: SmartImportCommitStats }>(
    `/api/v1/smart-import/sessions/${sessionId}/commit`,
    { method: 'POST' },
  );
}

// ── AI 工作指令 (顾源源 5/24 §4): 复用 A 已写的 resolveBotByHandle /
//    getBotPermissions / createBotTaskPlan 等 (api.ts ~900-1010 行) ──
