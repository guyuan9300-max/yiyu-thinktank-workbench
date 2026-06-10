import * as storage from "./storage";
import * as cache from "./cache";
import { devLog } from "./dev-log";
import { normalizeBaseUrl, resolveStoredBaseUrl } from "./base-url";
import type {
  AuthTokenResponse,
  TaskBoardResponse,
  TaskRecord,
  TaskListRecord,
  TaskTagRecord,
  EventLineRecord,
  ClientSummaryRecord,
  SupportRequestRecord,
  EmployeeRecord,
  TaskActivityRecord,
  TaskSettingsRecord,
  SmartTaskDraftResponse,
  ConsultationChatResponse,
  MobileCapabilityRecord,
  TaskContextPreviewRecord,
  TaskUnderstandingRecord,
  ClientUnderstandingSnapshot,
  ClientNarrativeRecord,
} from "./types";

const TOKEN_KEY = "yiyu_access_token";
const REFRESH_KEY = "yiyu_refresh_token";
const SERVER_URL_KEY = "yiyu_server_url";
export const CLOUD_PRIMARY_BASE_URL = process.env.EXPO_PUBLIC_YIYU_CLOUD_API_URL?.trim() || "";
export const CLOUD_FALLBACK_BASE_URL = "";
export const DEFAULT_BASE_URL =
  process.env.EXPO_PUBLIC_YIYU_SERVER_URL?.trim() || CLOUD_PRIMARY_BASE_URL || CLOUD_FALLBACK_BASE_URL;
export const DEFAULT_BASE_URL_PLACEHOLDER = "https://your-cloud.example.com";

let baseUrl = DEFAULT_BASE_URL;
// 语音→任务草稿/录音入库都要在服务端跑「豆包 ASR(异步轮询) + AI 解析」,实测整链路 ~20s
// (AI 可用时更久)。原来 12s 必然在服务端返回前就 abort → 前端永远报「云端转写失败」。
// 放宽到 45s,给 ASR+AI 足够余量;期间有 loading 态,失败仍保留原音频。
const SMART_TASK_DRAFT_TIMEOUT_MS = 45000;

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export async function initBaseUrl(): Promise<void> {
  const saved = await storage.getItem(SERVER_URL_KEY);
  const resolved = resolveStoredBaseUrl(saved, DEFAULT_BASE_URL);
  baseUrl = resolved.baseUrl;

  if (resolved.shouldDeleteSaved) {
    await storage.deleteItem(SERVER_URL_KEY);
  }

  devLog("baseUrl", "initialized", {
    savedUrl: saved ?? null,
    resolvedBaseUrl: baseUrl,
    source: resolved.source,
  });
}

export function setBaseUrl(url: string): void {
  baseUrl = normalizeBaseUrl(url);
}

export function getBaseUrl(): string {
  return baseUrl;
}

export async function setAndSaveBaseUrl(url: string): Promise<void> {
  const trimmed = normalizeBaseUrl(url);
  baseUrl = trimmed;
  await storage.setItem(SERVER_URL_KEY, trimmed);
  devLog("baseUrl", "saved", { baseUrl });
}

async function getToken(): Promise<string | null> {
  return storage.getItem(TOKEN_KEY);
}

export async function saveTokens(auth: AuthTokenResponse): Promise<void> {
  await storage.setItem(TOKEN_KEY, auth.accessToken);
  if (auth.refreshToken) {
    await storage.setItem(REFRESH_KEY, auth.refreshToken);
  }
}

export async function clearTokens(): Promise<void> {
  await storage.deleteItem(TOKEN_KEY);
  await storage.deleteItem(REFRESH_KEY);
}

function withAuthHeaders(options: RequestInit, token: string | null, json: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// 通用请求的默认超时上限。fetch 默认无限挂起，弱网 / 服务端僵死时会让 pullFromCloud
// 永不返回 → _isSyncing 永久为 true → 同步彻底死锁、UI 停在 syncing。45s 等于本仓
// 已知最长的显式超时(云端 ASR），不会比任何现有请求更激进；需要更长的请求自行覆盖。
const DEFAULT_REQUEST_TIMEOUT_MS = 45_000;

// 认证彻底失效(401 且 refresh 也失败)时的回调。AuthProvider 注册它来把内存 user
// 置空 → 自动跳回登录页。此前 api 层只 throw ApiError(401)、没有任何地方把它转成登出，
// 导致 refresh 过期后 user 仍留在内存 = "假登录"(每个请求都 401 失败却停在 tabs，
// 表现为页面空白 / 一直转圈 / 反复报错，用户必须手动去退出登录)。
let _authFailureHandler: (() => void) | null = null;
export function setAuthFailureHandler(handler: (() => void) | null): void {
  _authFailureHandler = handler;
}
function notifyAuthFailure(): void {
  _authFailureHandler?.();
}

async function fetchWithTimeout(url: string, options: RequestOptions = {}): Promise<Response> {
  const { timeoutMs, ...fetchOptions } = options;
  if (!timeoutMs || timeoutMs <= 0) {
    return fetch(url, fetchOptions);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(url, { ...fetchOptions, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = await getToken();
  const headers = withAuthHeaders(options, token, true);
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;

  const res = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers, timeoutMs });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${refreshed}`;
      const retry = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers, timeoutMs });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json() as Promise<T>;
    }
    notifyAuthFailure();
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData, options: RequestOptions = {}): Promise<T> {
  const token = await getToken();
  const headers = withAuthHeaders(options, token, false);
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;

  const res = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers, body, timeoutMs });
  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const retryHeaders = withAuthHeaders(options, refreshed, false);
      const retry = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers: retryHeaders, body, timeoutMs });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json() as Promise<T>;
    }
    notifyAuthFailure();
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<string | null> {
  const refreshToken = await storage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as AuthTokenResponse;
    await saveTokens(data);
    return data.accessToken;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`API Error ${status}: ${body}`);
  }
}

// ─── Auth ────────────────────────────────────────
export async function login(email: string, password: string): Promise<AuthTokenResponse> {
  const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const data = (await res.json()) as AuthTokenResponse;
  await saveTokens(data);
  return data;
}

export interface HealthResponse {
  service: string;
  organizationCount: number;
  employeeCount: number;
  taskCount: number;
}

export interface MobileBackendContractProbe {
  baseUrl: string;
  health: HealthResponse;
  openapiAvailable: boolean;
  capabilities: MobileCapabilityRecord | null;
  capabilityError: string | null;
  routeAvailability: {
    mobileCapabilities: boolean;
    clientWorkspace: boolean;
    strategicCockpit: boolean;
    consultationChat: boolean;
  };
  chatPayloadFields: string[];
  chatResponseFields: string[];
  supportsConsultV2: boolean;
  status: "full" | "limited";
}

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId: string;
  organizationId: string;
  target: "vector_memory" | "document_archive";
  status: "pending" | "processing" | "completed" | "failed";
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

export interface ConsultationKnowledgeRequestPayload {
  target: "vector_memory" | "document_archive";
  question?: string;
  answer: string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
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

export async function fetchHealth(baseUrlOverride?: string): Promise<HealthResponse> {
  const targetBaseUrl = normalizeBaseUrl(baseUrlOverride ?? baseUrl);
  const res = await fetchWithTimeout(`${targetBaseUrl}/health`, { timeoutMs: 7000 });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<HealthResponse>;
}

async function requestFromBaseUrl<T>(
  targetBaseUrl: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const token = await getToken();
  const headers = withAuthHeaders(options, token, true);
  const normalizedBaseUrl = normalizeBaseUrl(targetBaseUrl);
  const res = await fetchWithTimeout(`${normalizedBaseUrl}${path}`, { ...options, headers });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

function schemaPropertyKeys(schema: unknown, path: string[]): string[] {
  let cursor: any = schema;
  for (const key of path) {
    cursor = cursor?.[key];
  }
  if (!cursor || typeof cursor !== "object") {
    return [];
  }
  return Object.keys(cursor);
}

export async function probeMobileBackendContract(
  baseUrlOverride?: string,
): Promise<MobileBackendContractProbe> {
  const targetBaseUrl = normalizeBaseUrl(baseUrlOverride ?? baseUrl);
  const health = await fetchHealth(targetBaseUrl);
  let openapi: any = null;
  try {
    const res = await fetchWithTimeout(`${targetBaseUrl}/openapi.json`, { timeoutMs: 7000 });
    if (res.ok) {
      openapi = await res.json();
    }
  } catch {}

  let capabilities: MobileCapabilityRecord | null = null;
  let capabilityError: string | null = null;
  if (await getToken()) {
    try {
      capabilities = await fetchMobileCapabilities(targetBaseUrl);
    } catch (error) {
      capabilityError = error instanceof Error ? error.message : "能力探测失败";
    }
  } else {
    capabilityError = "需要登录后确认后端运行时能力";
  }

  const paths = openapi?.paths && typeof openapi.paths === "object" ? openapi.paths : {};
  const routeAvailability = {
    mobileCapabilities: Boolean(paths["/api/v1/mobile/capabilities"] || capabilities),
    clientWorkspace: Boolean(paths["/api/v1/clients/{client_id}/workspace"] || capabilities?.clientWorkspace),
    strategicCockpit: Boolean(paths["/api/v1/clients/{client_id}/strategic-cockpit"] || capabilities?.strategicCockpit),
    consultationChat: Boolean(paths["/api/v1/consultation/chat"] || capabilities?.consultationChat),
  };
  const chatPayloadFields = schemaPropertyKeys(openapi, [
    "components",
    "schemas",
    "ConsultationChatPayload",
    "properties",
  ]);
  const chatResponseFields = schemaPropertyKeys(openapi, [
    "components",
    "schemas",
    "ConsultationChatResponse",
    "properties",
  ]);
  const supportsConsultV2 =
    capabilities?.consultationPayloadVersion === "v2" ||
    (
      chatPayloadFields.includes("workspaceContext") &&
      chatPayloadFields.includes("taskBoardContext") &&
      chatResponseFields.includes("answerMode") &&
      chatResponseFields.includes("contextQuality")
    );
  const hasFullContract =
    routeAvailability.consultationChat &&
    routeAvailability.clientWorkspace &&
    routeAvailability.strategicCockpit &&
    supportsConsultV2;

  return {
    baseUrl: targetBaseUrl,
    health,
    openapiAvailable: Boolean(openapi),
    capabilities,
    capabilityError,
    routeAvailability,
    chatPayloadFields,
    chatResponseFields,
    supportsConsultV2,
    status: hasFullContract ? "full" : "limited",
  };
}

export function formatMobileBackendProbeSummary(probe: MobileBackendContractProbe): string {
  const contractLabel = probe.status === "full" ? "服务连接正常" : "服务已连接";
  return `${contractLabel} · ${probe.health.service}`;
}

export async function getMe() {
  return request<AuthTokenResponse["user"]>("/api/v1/auth/me");
}

export async function updateMe(payload: { fullName?: string; primaryRole?: string }) {
  return request<AuthTokenResponse["user"]>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function uploadMyAvatar(file: UploadableFile): Promise<AuthTokenResponse["user"]> {
  const formData = new FormData();
  formData.append("file", file as any);
  return requestForm<AuthTokenResponse["user"]>("/api/v1/me/avatar", formData, { method: "POST" });
}

/** 把云端返回的相对头像 URL（/api/public/avatars/xxx?v=...）拼成完整 URL。 */
export function resolveAvatarUrl(avatarUrl: string | null | undefined): string | null {
  if (!avatarUrl) return null;
  if (/^https?:\/\//i.test(avatarUrl)) return avatarUrl;
  const base = baseUrl.replace(/\/+$/, "");
  return `${base}${avatarUrl.startsWith("/") ? "" : "/"}${avatarUrl}`;
}

export async function getFeishuUserBinding() {
  return request<FeishuUserBinding>("/api/v1/settings/feishu-user-binding");
}

export async function startFeishuUserBinding() {
  return request<FeishuUserBindingStartResult>("/api/v1/settings/feishu-user-binding/start", {
    method: "POST",
  });
}

export async function clearFeishuUserBinding() {
  return request<FeishuUserBinding>("/api/v1/settings/feishu-user-binding", {
    method: "DELETE",
  });
}

export async function logout(): Promise<void> {
  try {
    await request("/api/v1/auth/logout", { method: "POST" });
  } finally {
    await clearTokens();
    await cache.clearAll();
  }
}

// ─── Tasks ───────────────────────────────────────
export async function fetchTaskBoard(): Promise<TaskBoardResponse> {
  return request<TaskBoardResponse>("/api/v1/tasks");
}

/** 拉取单条任务最新数据（详情页用，避免只能从 board payload 里读旧字段） */
export async function fetchTaskById(taskId: string): Promise<TaskRecord> {
  return request<TaskRecord>(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
}

// ─── Event Lines ─────────────────────────────────
export async function fetchEventLines(): Promise<EventLineRecord[]> {
  return request<EventLineRecord[]>("/api/v1/event-lines");
}

export async function createEventLine(payload: {
  name: string;
  primaryClientId?: string;
  primaryClientName?: string;
  status?: string;
}): Promise<EventLineRecord> {
  const result = await request<EventLineRecord>("/api/v1/event-lines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.eventLines);
  return result;
}

export async function updateEventLine(
  eventLineId: string,
  payload: {
    name?: string;
    primaryClientId?: string | null;
    primaryClientName?: string | null;
    stage?: string | null;
    summary?: string | null;
    currentBlocker?: string | null;
    recentDecision?: string | null;
    nextStep?: string | null;
    status?: string;
    syncLinkedTaskClientIds?: boolean;
  },
): Promise<EventLineRecord> {
  const result = await request<EventLineRecord>(`/api/v1/event-lines/${eventLineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.eventLines, cache.KEYS.taskBoard);
  return result;
}

export async function fetchClients(): Promise<ClientSummaryRecord[]> {
  return request<ClientSummaryRecord[]>("/api/v1/clients");
}

export async function enqueueConsultationKnowledgeRequest(
  payload: ConsultationKnowledgeRequestPayload,
): Promise<ConsultationKnowledgeRequestRecord> {
  return request<ConsultationKnowledgeRequestRecord>("/api/v1/consultation/knowledge-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchConsultationKnowledgeRequests(
  status?: "pending" | "processing" | "completed" | "failed",
): Promise<ConsultationKnowledgeRequestRecord[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<ConsultationKnowledgeRequestRecord[]>(`/api/v1/consultation/knowledge-requests${qs}`);
}

interface ConsultationChatPayload {
  message: string;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  taskId?: string | null;
  taskTitle?: string | null;
  taskContext?: string | null;
  workspaceContext?: string | null;
  eventLineContext?: string | null;
  taskBoardContext?: string | null;
  understandingContext?: string | null;
  sourceLabels?: string[];
  missingEventLineHint?: string | null;
}

export async function sendConsultationChat(
  payload: ConsultationChatPayload,
): Promise<ConsultationChatResponse> {
  return request<ConsultationChatResponse>("/api/v1/consultation/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchMobileCapabilities(baseUrlOverride?: string): Promise<MobileCapabilityRecord> {
  if (!baseUrlOverride || normalizeBaseUrl(baseUrlOverride) === baseUrl) {
    return request<MobileCapabilityRecord>("/api/v1/mobile/capabilities");
  }
  return requestFromBaseUrl<MobileCapabilityRecord>(
    baseUrlOverride,
    "/api/v1/mobile/capabilities",
  );
}

// ─── Task Creation ──────────────────────────────
export interface CreateTaskPayload {
  title: string;
  dueDate?: string | null;
  durationMinutes?: number;
  deadlineAt?: string | null;
  scheduledStartAt?: string | null;
  scheduledEndAt?: string | null;
  completedAt?: string | null;
  // 提醒提前量（分钟）：0=准时, 5=提前5分, null=不提醒。跨端共享同一字段。
  // UpdateTaskPayload 经 Partial<CreateTaskPayload> 继承此字段，无需重复声明。
  reminderMinutesBefore?: number | null;
  assigneeId?: string;
  ownerId?: string;
  priority?: string;
  clientId?: string;
  listId?: string;
  description?: string;
  eventLineId?: string;
  scopeMode?: string;
  tags?: string[];
  collaboratorIds?: string[];
  businessCategory?: string;
  currentBlocker?: string;
  nextAction?: string;
  recentDecision?: string;
}

export interface UpdateTaskPayload extends Omit<Partial<CreateTaskPayload>, "dueDate" | "durationMinutes"> {
  dueDate?: string | null;
  durationMinutes?: number | null;
  deadlineAt?: string | null;
  scheduledStartAt?: string | null;
  scheduledEndAt?: string | null;
  completedAt?: string | null;
  progressStatus?: string;
}

export async function createTask(payload: CreateTaskPayload): Promise<TaskRecord> {
  // 云端 tasks.duration_minutes 是 NOT NULL int(默认 60);durationMinutes 发 null 会被
  // TaskCreatePayload(int=60)以 422 拒收,导致任务永远卡在本地重试同步不上去。
  // 全天/无时段任务的 durationMinutes 本地是 null —— 发送前剥掉,让云端用默认值。
  const body: CreateTaskPayload = { ...payload };
  if (body.durationMinutes == null) {
    delete body.durationMinutes;
  }
  const result = await request<TaskRecord>("/api/v1/tasks", {
    method: "POST",
    body: JSON.stringify(body),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export interface OrgMember {
  id: string;
  fullName: string;
  email?: string | null;
  departmentName?: string | null;
  jobTitle?: string | null;
  primaryRole?: string | null;
}

// 组织成员目录(已批准成员),用于任务负责人/协作人选择。与软件端同一数据源。
export async function fetchEmployeeDirectory(): Promise<OrgMember[]> {
  return request<OrgMember[]>("/api/v1/employees/directory", { method: "GET" });
}

export async function updateTask(taskId: string, payload: UpdateTaskPayload): Promise<TaskRecord> {
  const result = await request<TaskRecord>(`/api/v1/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export async function deleteTask(taskId: string): Promise<{ ok?: boolean; success?: boolean }> {
  const result = await request<{ ok?: boolean; success?: boolean }>(`/api/v1/tasks/${taskId}`, {
    method: "DELETE",
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export async function completeTaskWithReview(taskId: string, reviewNote: string): Promise<TaskRecord> {
  const result = await request<TaskRecord>(`/api/v1/tasks/${taskId}/complete-with-review`, {
    method: "POST",
    body: JSON.stringify({ reviewNote }),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export type UploadableFile =
  | File
  | {
      uri: string;
      name: string;
      type: string;
    };

export interface UploadTaskAttachmentPayload {
  file: UploadableFile;
  clientId?: string | null;
  eventLineId?: string | null;
  title?: string | null;
  taskTitle?: string | null;
  durationSeconds?: number | null;
}

export async function uploadTaskAttachment(taskId: string, payload: UploadTaskAttachmentPayload): Promise<TaskRecord> {
  const formData = new FormData();
  formData.append("file", payload.file as any);
  if (payload.clientId) formData.append("clientId", payload.clientId);
  if (payload.eventLineId) formData.append("eventLineId", payload.eventLineId);
  if (payload.title) formData.append("title", payload.title);
  const taskTitle = payload.taskTitle ?? payload.title;
  if (taskTitle) formData.append("taskTitle", taskTitle);
  if (payload.durationSeconds && payload.durationSeconds > 0) {
    formData.append("durationSeconds", String(payload.durationSeconds));
  }
  const result = await requestForm<TaskRecord>(`/api/v1/tasks/${taskId}/attachments`, formData, {
    method: "POST",
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export interface TaskAttachmentTranscriptionResponse {
  attachmentId: string;
  transcript: string;
  documentRequest: ConsultationKnowledgeRequestRecord;
}

export async function transcribeTaskAttachmentToDocument(
  taskId: string,
  attachmentId: string,
): Promise<TaskAttachmentTranscriptionResponse> {
  return request<TaskAttachmentTranscriptionResponse>(
    `/api/v1/tasks/${taskId}/attachments/${attachmentId}/transcribe-to-document`,
    { method: "POST" },
  );
}

export interface MobileRecordingSegmentPayload {
  segmentIndex: number;
  startMs: number;
  endMs?: number | null;
  text: string;
  confidence?: number | null;
  isFinal: boolean;
}

export interface MobileRecordingTextIngestPayload {
  recordingId: string;
  clientId?: string | null;
  eventLineId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  targetType?: string | null;
  rawTranscript: string;
  cleanTranscript: string;
  summary?: Record<string, unknown> | null;
  segments: MobileRecordingSegmentPayload[];
  recordedAt: string;
  durationSeconds?: number | null;
}

export interface MobileRecordingTextIngestResponse {
  recordingId: string;
  documentId?: string | null;
  evidenceRefId?: string | null;
  taskIds: string[];
  meetingId?: string | null;
  eventLineActivityId?: string | null;
  syncStatus: string;
}

export async function ingestMobileRecordingText(
  payload: MobileRecordingTextIngestPayload,
): Promise<MobileRecordingTextIngestResponse> {
  const result = await request<MobileRecordingTextIngestResponse>("/api/v1/mobile/recordings/text-ingest", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: SMART_TASK_DRAFT_TIMEOUT_MS,
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export interface GenerateSmartTaskDraftPayload {
  transcriptText?: string | null;
  audioFile?: UploadableFile | null;
  referenceDate?: string | null;
  currentEventLineId?: string | null;
}

export async function generateSmartTaskDraft(
  payload: GenerateSmartTaskDraftPayload,
): Promise<SmartTaskDraftResponse> {
  const formData = new FormData();
  if (payload.transcriptText?.trim()) {
    formData.append("transcriptText", payload.transcriptText.trim());
  }
  if (payload.referenceDate?.trim()) {
    formData.append("referenceDate", payload.referenceDate.trim());
  }
  if (payload.currentEventLineId?.trim()) {
    formData.append("currentEventLineId", payload.currentEventLineId.trim());
  }
  if (payload.audioFile) {
    formData.append("audio", payload.audioFile as any);
  }
  return requestForm<SmartTaskDraftResponse>("/api/v1/mobile/smart-input/task-draft", formData, {
    method: "POST",
    timeoutMs: SMART_TASK_DRAFT_TIMEOUT_MS,
  });
}

// ─── Task Lists & Tags ──────────────────────────
export async function fetchTaskLists(): Promise<TaskListRecord[]> {
  const res = await request<{ lists: TaskListRecord[] }>("/api/v1/task-lists");
  return res.lists;
}

// ─── Task Activities ────────────────────────────
export async function fetchTaskActivities(taskId: string): Promise<TaskActivityRecord[]> {
  return request<TaskActivityRecord[]>(`/api/v1/tasks/${taskId}/activity`);
}

export async function fetchTaskUnderstanding(taskId: string): Promise<TaskUnderstandingRecord> {
  return request<TaskUnderstandingRecord>(`/api/v1/tasks/${taskId}/understanding`);
}

export async function fetchTaskContextPreview(taskId: string): Promise<TaskContextPreviewRecord> {
  return request<TaskContextPreviewRecord>(`/api/v1/tasks/${taskId}/context-preview`);
}

export async function fetchClientWorkspace(clientId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/clients/${clientId}/workspace`);
}

export async function fetchStrategicCockpit(clientId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/clients/${clientId}/strategic-cockpit`);
}

export async function fetchClientUnderstanding(clientId: string): Promise<ClientUnderstandingSnapshot> {
  return request<ClientUnderstandingSnapshot>(`/api/v1/clients/${clientId}/understanding`);
}

// P0-3: 接入桌面端"战略陪伴 6 维度叙事"
// endpoint 已在 cloud_backend:11491 存在；如果客户从未生成过 narrative，会返回 dimensions 全空的"诚实空版本"
export async function fetchClientNarrative(clientId: string): Promise<ClientNarrativeRecord> {
  return request<ClientNarrativeRecord>(`/api/v1/clients/${clientId}/narrative`);
}

export async function fetchReviews(weekLabel?: string): Promise<Record<string, unknown>> {
  const suffix = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : "";
  return request<Record<string, unknown>>(`/api/v1/reviews${suffix}`);
}

// ─── Task Settings ─────────────────────────────
interface TaskSettingsPayload {
  defaultListId?: string | null;
  defaultPriority?: "low" | "normal" | "high";
  defaultDueDatePreset?: "today" | "none";
  defaultViewMode?: "inbox" | "list" | "calendar" | "review";
  listSortMode?: "manual" | "priority" | "dueDate";
  showCompletedTasks?: boolean;
  defaultReviewScope?: "work" | "personal";
  autoAssignSelf?: boolean;
}

export async function fetchTaskSettings(): Promise<TaskSettingsRecord> {
  return request<TaskSettingsRecord>("/api/v1/settings/tasks");
}

export async function updateTaskSettings(
  payload: Partial<TaskSettingsPayload>,
): Promise<TaskSettingsRecord> {
  const result = await request<TaskSettingsRecord>("/api/v1/settings/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.taskSettings);
  return result;
}
