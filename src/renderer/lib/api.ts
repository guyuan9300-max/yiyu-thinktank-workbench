import type {
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
  ClientTemplateFillResponse,
  ClientTemplateFillRun,
  ClientMutationPayload,
  ClientStrategicProfile,
  ClientSummary,
  ClientWorkspace,
  CooperationRelationship,
  WorkspaceImportBackfillResponse,
  ClientWorkspaceSettings,
  ClientWorkspaceSettingsPayload,
  DepartmentOption,
  DeepDnaDraft,
  DeepDnaRecord,
  DnaTerm,
  DemoDataReport,
  EmployeeRecord,
  EmployeeRejectPayload,
  EmployeeDepartmentPayload,
  ExpenseEvidenceImportPayload,
  ExpenseEvidenceImportResult,
  ExpenseEvidenceRecord,
  ExpenseEvidenceUpdatePayload,
  ExpenseImportSearchPayload,
  ExpenseImportSearchResponse,
  FeishuBotSettings,
  FeishuMeetingLaunchResult,
  FeishuBotSettingsPayload,
  FeishuDeliveryProfile,
  FeishuDeliveryProfilePayload,
  FeishuUserBinding,
  FeishuUserBindingStartResult,
  EmployeeRolePayload,
  EventLine,
  EventLineClarificationDraftPayload,
  EventLineClarificationDraftResult,
  EventLineDetail,
  EventLineExpenseEvidenceLink,
  EventLineExpenseEvidenceLinkPayload,
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
  KnowledgeMemoryRecord,
  KnowledgeSearchResult,
  KnowledgeStatus,
  LegacyScanReport,
  MentionCandidate,
  OrganizationDnaModule,
  OrgModelSettings,
  OrganizationDnaResponse,
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
  SettingsPayload,
  SystemAdminSettings,
  SystemAdminSettingsPayload,
  TaskOrgBackfillResult,
  Task,
  TaskActivityRecord,
  TaskContextPreview,
  TaskExpenseEvidenceLink,
  TaskExpenseEvidenceLinkPayload,
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
  ReviewHistoryResponse,
  ReviewGovernanceSettings,
  ReviewGovernanceSettingsPayload,
  RedeemOrgInvitationPayload,
  OrgWritingNorm,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
  OrgDingtalkFinanceIntegration,
  OrgDingtalkFinanceIntegrationPayload,
  RunComparison,
  SupportRequestCreatePayload,
  SupportRequestResolvePayload,
  SupportRequestRecord,
  StrategicCockpitConfirmPayload,
  StrategicCockpitSnapshot,
  StrategicLineDetail,
  ApplyTaskGroupTemplatePayload,
  ApplyTaskGroupTemplateResult,
  TaskViewDefinition,
  TaskViewMutationPayload,
  TaskViewsResponse,
  TaskGroupTemplatePayload,
  TaskGroupTemplateRecord,
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
  UnderstandingSnapshotV1,
  WorkObjectTerminologyState,
  WorkObjectTerminologyUpdatePayload,
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
      detectedAppPaths: [],
      legacyAppPaths: [],
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
    getDroppedFilePath: () => null,
    readTextFile: async () => notAvailable('读取本地文件'),
    openPath: async () => notAvailable('打开本地路径'),
    openExternalUrl: async (targetUrl: string) => {
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
      return true;
    },
    revealInFinder: async () => notAvailable('在 Finder 中显示'),
    saveFileAs: async () => notAvailable('另存为'),
  };
}

if (typeof window !== 'undefined' && !window.yiyuWorkbench) {
  window.yiyuWorkbench = createBrowserWorkbenchFallback();
}

const baseUrl = window.yiyuWorkbench.backendBaseUrl;
type CloudDirectAccess = {
  apiBaseUrl: string;
  accessToken: string;
};

let cachedCloudDirectAccess: CloudDirectAccess | null = null;

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

const WORK_OBJECTS_API_BASE = '/api/v1/work-objects';
const workObjectPath = (suffix = '') => `${WORK_OBJECTS_API_BASE}${suffix}`;

async function getCloudDirectAccess(forceRefresh = false): Promise<CloudDirectAccess> {
  if (!forceRefresh && cachedCloudDirectAccess) {
    return cachedCloudDirectAccess;
  }
  const access = await request<CloudDirectAccess>('/api/v1/cloud/direct-access');
  cachedCloudDirectAccess = access;
  return access;
}

async function requestCloud<T>(path: string, options?: RequestInit, attempt = 0): Promise<T> {
  const access = await getCloudDirectAccess(attempt > 0);
  const response = await fetch(`${access.apiBaseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${access.accessToken}`,
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (response.status === 401 && attempt === 0) {
    cachedCloudDirectAccess = null;
    return requestCloud<T>(path, options, 1);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `云端请求失败 (${response.status})`);
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

export async function getTaskContextPreview(taskId: string) {
  return request<TaskContextPreview>(`/api/v1/tasks/${taskId}/context-preview`);
}

export type TaskUnderstandingSnapshot = UnderstandingSnapshotV1 & {
  _pending?: boolean;
};

export async function getTaskUnderstanding(taskId: string) {
  return request<TaskUnderstandingSnapshot>(`/api/v1/tasks/${taskId}/understanding`);
}

export async function getTaskSmartBrief(taskId: string) {
  return request<TaskSmartBrief>(`/api/v1/tasks/${taskId}/smart-brief`);
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

export async function getDepartmentOptions() {
  return request<DepartmentOption[]>('/api/v1/auth/department-options');
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
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings');
}

export async function updateSettings(payload: SettingsPayload) {
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getWorkObjectTerminology() {
  return request<WorkObjectTerminologyState>('/api/v1/settings/work-object-terminology');
}

export async function updateWorkObjectTerminology(payload: WorkObjectTerminologyUpdatePayload) {
  return request<WorkObjectTerminologyState>('/api/v1/settings/work-object-terminology', {
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

export async function getReviewGovernanceSettings() {
  return request<ReviewGovernanceSettings>('/api/v1/settings/review-governance');
}

export async function updateReviewGovernanceSettings(payload: ReviewGovernanceSettingsPayload) {
  return request<ReviewGovernanceSettings>('/api/v1/settings/review-governance', {
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

export async function backfillOrgTaskLinks() {
  return request<TaskOrgBackfillResult>('/api/v1/settings/org-model/backfill-task-links', {
    method: 'POST',
  });
}

export async function getOrganizationDna() {
  return request<OrganizationDnaResponse>('/api/v1/settings/org-dna');
}

export async function updateOrganizationDnaModule(moduleKey: OrganizationDnaModule['moduleKey'], payload: OrganizationDnaUploadPayload) {
  return request<OrganizationDnaModule>(`/api/v1/settings/org-dna/${moduleKey}`, {
    method: 'POST',
    body: JSON.stringify(payload),
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
  keyword?: string;
}) {
  const search = new URLSearchParams();
  if (params?.startDate) search.set('startDate', params.startDate);
  if (params?.endDate) search.set('endDate', params.endDate);
  if (params?.level) search.set('level', params.level);
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
  return request<ClientSummary[]>(workObjectPath());
}

export async function createClient(payload: ClientMutationPayload) {
  return request<ClientSummary>(workObjectPath(), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateClient(id: string, payload: ClientMutationPayload) {
  return request<ClientSummary>(workObjectPath(`/${id}`), {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteClient(id: string) {
  return request<{ deleted: boolean }>(workObjectPath(`/${id}`), {
    method: 'DELETE',
  });
}

export async function deleteClientFolder(clientId: string, folderId: string) {
  return request<{ deleted: boolean }>(workObjectPath(`/${clientId}/folders/${folderId}`), {
    method: 'DELETE',
  });
}

export async function getClientWorkspace(id: string) {
  return request<ClientWorkspace>(workObjectPath(`/${id}/workspace`));
}

export async function getClientDnaDocuments(clientId: string) {
  return request<ClientDnaModulesResponse>(workObjectPath(`/${clientId}/dna-documents`));
}

export async function getClientDnaDocument(clientId: string, moduleKey: ClientDnaModule['moduleKey']) {
  return request<ClientDnaModule>(workObjectPath(`/${clientId}/dna-documents/${moduleKey}`));
}

export async function updateClientDnaDocument(
  clientId: string,
  moduleKey: ClientDnaModule['moduleKey'],
  payload: OrganizationDnaUploadPayload,
) {
  return request<ClientDnaModule>(workObjectPath(`/${clientId}/dna-documents/${moduleKey}`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientProjectStructure(clientId: string) {
  return request<ProjectStructureResponse>(workObjectPath(`/${clientId}/project-structure`));
}

export async function getProjectModuleDetail(clientId: string, moduleId: string) {
  return request<ProjectModuleDetail>(workObjectPath(`/${clientId}/project-modules/${moduleId}`));
}

export async function createProjectModule(clientId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(workObjectPath(`/${clientId}/project-modules`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectModule(clientId: string, moduleId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(workObjectPath(`/${clientId}/project-modules/${moduleId}`), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectModule(clientId: string, moduleId: string) {
  return request<{ status: string }>(workObjectPath(`/${clientId}/project-modules/${moduleId}`), {
    method: 'DELETE',
  });
}

export async function getProjectFlowDetail(clientId: string, flowId: string) {
  return request<ProjectFlowDetail>(workObjectPath(`/${clientId}/project-flows/${flowId}`));
}

export async function createProjectFlow(clientId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(workObjectPath(`/${clientId}/project-flows`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectFlow(clientId: string, flowId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(workObjectPath(`/${clientId}/project-flows/${flowId}`), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getClientKnowledgeStatus(clientId: string) {
  return request<KnowledgeStatus>(workObjectPath(`/${clientId}/knowledge/status`));
}

export async function searchClientKnowledge(clientId: string, prompt: string, threadId?: string) {
  return request<KnowledgeSearchResult>(workObjectPath(`/${clientId}/knowledge/search`), {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId }),
  });
}

export async function rebuildClientKnowledge(clientId: string) {
  return request<KnowledgeJob>(workObjectPath(`/${clientId}/knowledge/rebuild`), {
    method: 'POST',
  });
}

export async function generateClientDnaCandidates(clientId: string, payload?: { refreshGenerated?: boolean }) {
  return request<KnowledgeJob>(workObjectPath(`/${clientId}/dna-documents/generate`), {
    method: 'POST',
    body: JSON.stringify({ refreshGenerated: payload?.refreshGenerated ?? false }),
  });
}

export async function importPaths(clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) {
  return request<ImportRecord[]>('/api/v1/imports', {
    method: 'POST',
    body: JSON.stringify({
      clientId,
      workObjectId: clientId,
      mode,
      paths,
      allowLegacy: options?.allowLegacy ?? false,
    }),
  });
}

export async function startClientMessage(
  clientId: string,
  prompt: string,
  threadId?: string,
  searchId?: string,
  options?: RequestInit,
) {
  return request<ChatStartResponse>(workObjectPath(`/${clientId}/workspace/chat/start`), {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId, searchId }),
    ...options,
  });
}

export async function getClientMessage(clientId: string, messageId: string) {
  return request<ChatMessage>(workObjectPath(`/${clientId}/workspace/chat/messages/${messageId}`));
}

export async function getClientChatThread(clientId: string, threadId: string) {
  return request<ChatThreadDetailResponse>(workObjectPath(`/${clientId}/workspace/chat/threads/${threadId}`));
}

export async function getClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(workObjectPath(`/${clientId}/analysis-runs/${runId}`));
}

export async function cancelClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(workObjectPath(`/${clientId}/analysis-runs/${runId}/cancel`), {
    method: 'POST',
  });
}

export async function vectorizeAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(workObjectPath(`/${clientId}/knowledge/vectorize-answer`), {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function exportAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(workObjectPath(`/${clientId}/knowledge/export-answer`), {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function createClientTextDocument(clientId: string, payload: { title?: string | null; content: string }) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(workObjectPath(`/${clientId}/documents/from-text`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function startClientTemplateFill(clientId: string, templatePath: string) {
  return request<ClientTemplateFillRun>(workObjectPath(`/${clientId}/documents/fill-template/start`), {
    method: 'POST',
    body: JSON.stringify({ templatePath }),
  });
}

export async function getClientTemplateFillRun(clientId: string, runId: string) {
  return request<ClientTemplateFillRun>(workObjectPath(`/${clientId}/template-fill-runs/${runId}`));
}

export async function backfillClientWorkspaceImports(clientId: string) {
  return request<WorkspaceImportBackfillResponse>(workObjectPath(`/${clientId}/workspace/backfill-imports`), {
    method: 'POST',
  });
}

export async function createMeeting(clientId: string, title: string, scheduledAt?: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/meetings`), {
    method: 'POST',
    body: JSON.stringify({ title, scheduledAt }),
  });
}

export async function getStrategicCockpit(clientId: string) {
  return request<StrategicCockpitSnapshot>(workObjectPath(`/${clientId}/strategic-cockpit`));
}

export async function confirmStrategicCockpit(clientId: string, payload: StrategicCockpitConfirmPayload) {
  return request<StrategicCockpitSnapshot>(workObjectPath(`/${clientId}/strategic-cockpit/confirm`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createStrategicMeetingPack(clientId: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/strategic-cockpit/meeting-pack`), {
    method: 'POST',
  });
}

export async function applyStrategicMeetingPack(clientId: string, meetingId: string) {
  return request<StrategicCockpitSnapshot>(workObjectPath(`/${clientId}/strategic-cockpit/meeting-pack/${meetingId}/apply`), {
    method: 'POST',
  });
}

export async function createClientFolder(clientId: string, label: string) {
  return request<{ id: string; label: string; created: boolean }>(workObjectPath(`/${clientId}/folders`), {
    method: 'POST',
    body: JSON.stringify({ label }),
  });
}

export async function renameClientFolder(clientId: string, folderId: string, label: string) {
  return request<{ id: string; label: string }>(workObjectPath(`/${clientId}/folders/${folderId}`), {
    method: 'PUT',
    body: JSON.stringify({ label }),
  });
}

export async function launchFeishuMeeting(clientId: string, payload: { title: string; scheduledAt?: string; sourceTaskId?: string | null }) {
  return request<FeishuMeetingLaunchResult>(workObjectPath(`/${clientId}/meetings/launch-feishu`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function ingestMeeting(clientId: string, meetingId: string, transcriptText: string, notes: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/meetings/${meetingId}/ingest`), {
    method: 'POST',
    body: JSON.stringify({ transcriptText, notes }),
  });
}

export async function extractMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/meetings/${meetingId}/extract`), {
    method: 'POST',
  });
}

export async function resolveMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/meetings/${meetingId}/resolve`), {
    method: 'POST',
  });
}

export async function publishMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(workObjectPath(`/${clientId}/meetings/${meetingId}/publish`), {
    method: 'POST',
  });
}

export async function createGoal(clientId: string, payload: { title: string; quarter: string; progress: number; ownerName: string }) {
  return request<GoalRecord>(workObjectPath(`/${clientId}/goals`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function upsertDna(clientId: string, payload: { category: string; canonicalName: string; aliases: string[]; description: string }) {
  return request<DnaTerm>(workObjectPath(`/${clientId}/dna`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTaskBoard() {
  return request<{ tasks: Task[]; lists: TaskList[]; tags: TaskTag[] }>('/api/v1/tasks');
}

export async function getTaskLists() {
  return request<{ lists: TaskList[] }>('/api/v1/task-lists');
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

export async function listTaskGroupTemplates() {
  return request<{ templates: TaskGroupTemplateRecord[] }>('/api/v1/task-group-templates');
}

export async function createTaskGroupTemplate(payload: TaskGroupTemplatePayload) {
  return request<TaskGroupTemplateRecord>('/api/v1/task-group-templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTaskGroupTemplate(id: string, payload: TaskGroupTemplatePayload) {
  return request<TaskGroupTemplateRecord>(`/api/v1/task-group-templates/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskGroupTemplate(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/task-group-templates/${id}`, {
    method: 'DELETE',
  });
}

export async function applyTaskGroupTemplate(id: string, payload: ApplyTaskGroupTemplatePayload) {
  return request<ApplyTaskGroupTemplateResult>(`/api/v1/task-group-templates/${id}/apply`, {
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
  if (payload.clientId) {
    formData.append('clientId', payload.clientId);
    formData.append('workObjectId', payload.clientId);
  }
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

export async function getOrgDingtalkFinanceIntegration() {
  return request<OrgDingtalkFinanceIntegration>('/api/v1/org-integrations/dingtalk-finance');
}

export async function saveOrgDingtalkFinanceIntegration(payload: OrgDingtalkFinanceIntegrationPayload) {
  return request<OrgDingtalkFinanceIntegration>('/api/v1/org-integrations/dingtalk-finance/validate-and-save', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listExpenseEvidences(workObjectId: string, params?: { query?: string; limit?: number }) {
  const search = new URLSearchParams();
  if (params?.query?.trim()) search.set('query', params.query.trim());
  if (typeof params?.limit === 'number') search.set('limit', String(params.limit));
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<ExpenseEvidenceRecord[]>(`/api/v1/work-objects/${encodeURIComponent(workObjectId)}/expense-evidences${suffix}`);
}

export async function searchExpenseEvidenceImports(workObjectId: string, payload: ExpenseImportSearchPayload) {
  return request<ExpenseImportSearchResponse>(`/api/v1/work-objects/${encodeURIComponent(workObjectId)}/expense-evidences/import-search`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function importExpenseEvidences(workObjectId: string, payload: ExpenseEvidenceImportPayload) {
  return request<ExpenseEvidenceImportResult>(`/api/v1/work-objects/${encodeURIComponent(workObjectId)}/expense-evidences/import`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getExpenseEvidence(evidenceId: string) {
  return request<ExpenseEvidenceRecord>(`/api/v1/expense-evidences/${encodeURIComponent(evidenceId)}`);
}

export async function updateExpenseEvidence(evidenceId: string, payload: ExpenseEvidenceUpdatePayload) {
  return request<ExpenseEvidenceRecord>(`/api/v1/expense-evidences/${encodeURIComponent(evidenceId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function fetchExpenseEvidenceAttachments(evidenceId: string) {
  return request<ExpenseEvidenceRecord>(`/api/v1/expense-evidences/${encodeURIComponent(evidenceId)}/attachments/fetch`, {
    method: 'POST',
  });
}

export async function listEventLineExpenseEvidences(eventLineId: string) {
  return request<EventLineExpenseEvidenceLink[]>(`/api/v1/event-lines/${encodeURIComponent(eventLineId)}/expense-evidences`);
}

export async function linkEventLineExpenseEvidence(eventLineId: string, payload: EventLineExpenseEvidenceLinkPayload) {
  return request<EventLineExpenseEvidenceLink>(`/api/v1/event-lines/${encodeURIComponent(eventLineId)}/expense-evidences/link`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function unlinkEventLineExpenseEvidence(eventLineId: string, evidenceId: string) {
  return request<{ deleted: boolean }>(`/api/v1/event-lines/${encodeURIComponent(eventLineId)}/expense-evidences/${encodeURIComponent(evidenceId)}`, {
    method: 'DELETE',
  });
}

export async function listTaskExpenseEvidences(taskId: string) {
  return request<TaskExpenseEvidenceLink[]>(`/api/v1/tasks/${encodeURIComponent(taskId)}/expense-evidences`);
}

export async function linkTaskExpenseEvidence(taskId: string, payload: TaskExpenseEvidenceLinkPayload) {
  return request<TaskExpenseEvidenceLink>(`/api/v1/tasks/${encodeURIComponent(taskId)}/expense-evidences/link`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function unlinkTaskExpenseEvidence(taskId: string, evidenceId: string) {
  return request<{ deleted: boolean }>(`/api/v1/tasks/${encodeURIComponent(taskId)}/expense-evidences/${encodeURIComponent(evidenceId)}`, {
    method: 'DELETE',
  });
}

export async function getEventLineReportSnapshot(id: string) {
  return request<EventLineReportSnapshot>(`/api/v1/event-lines/${id}/report-snapshot`);
}

export async function getEventLineReportSnapshotDirect(id: string) {
  return requestCloud<EventLineReportSnapshot>(`/api/v1/event-lines/${id}/report-snapshot`);
}

export async function getEventLineReportSnapshotLocalOverrides(id: string) {
  try {
    return await request<EventLineReportSnapshot>(`/api/v1/event-lines/${id}/report-snapshot-overrides`);
  } catch {
    return null;
  }
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

export async function getReviews(weekLabel?: string) {
  const suffix = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : '';
  return request<ReviewDashboard>(`/api/v1/reviews${suffix}`);
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

export async function getTopics() {
  return request<{ radars: TopicRadar[]; candidates: TopicCandidate[] }>('/api/v1/topics');
}

export async function captureTopicRadars() {
  return request<TopicCaptureBatchResult>('/api/v1/topics/capture', {
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

export async function getGrowthWorkbench() {
  return request<GrowthWorkbenchSnapshot>('/api/v1/growth/workbench');
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

export async function previewPullFromMain(repoPath: string) {
  return window.yiyuWorkbench.previewPullFromMain(repoPath) as Promise<PullPreview>;
}

export async function pullSelectedFromMain(payload: PullSelectedFromMainPayload) {
  return window.yiyuWorkbench.pullSelectedFromMain(payload) as Promise<CollabActionResult>;
}

export async function rebuildAndInstallFromRepo(repoPath: string) {
  return window.yiyuWorkbench.rebuildAndInstallFromRepo(repoPath) as Promise<boolean>;
}
