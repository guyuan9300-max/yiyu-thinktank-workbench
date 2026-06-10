import * as FileSystem from "expo-file-system/legacy";
import { NO_ACCOUNT_SCOPE_KEY } from "./account-scope";
import * as api from "./api";
import * as localDb from "./local-db";
import {
  buildRecordingPaths,
  buildRecordingSummary,
  buildRecordingTextIngestPayload,
  cleanTranscriptText,
  normalizeRecordingSegments,
  type RecordingSegmentDraft,
  type RecordingSession,
  type RecordingSource,
  type RecordingTargetType,
} from "./recording-session-core";
import type { TaskRecord } from "./types";

export interface SaveRecordingSessionInput {
  file: api.UploadableFile;
  title?: string | null;
  durationSeconds?: number | null;
  rawTranscript?: string | null;
  cleanTranscript?: string | null;
  segments?: RecordingSegmentDraft[];
  asrError?: string | null;
  source?: RecordingSource;
  targetType?: RecordingTargetType;
  targetLocalId?: string | null;
  targetRemoteId?: string | null;
  clientId?: string | null;
  eventLineId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  placeLabel?: string | null;
}

export interface RecordingDiagnosticsSnapshot {
  localDirectory: string | null;
  total: number;
  pendingTextSync: number;
  failedTextSync: number;
  needsAction: number;
  latestError: string | null;
}

function makeRecordingId(): string {
  return `rec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function getActiveScopeKey(): string {
  return localDb.getActiveAccountScopeKey() ?? NO_ACCOUNT_SCOPE_KEY;
}

export function getRecordingRootDirectory(): string | null {
  if (!FileSystem.documentDirectory) {
    return null;
  }
  return `${FileSystem.documentDirectory.replace(/\/+$/g, "")}/recordings`;
}

function normalizeUriUploadableFile(file: api.UploadableFile): { uri: string; name: string; type: string } | null {
  if (!file || typeof file !== "object" || !("uri" in file) || !file.uri) {
    return null;
  }
  return {
    uri: file.uri,
    name: file.name || `recording-${Date.now()}.m4a`,
    type: file.type || "audio/m4a",
  };
}

// 系统语音识别(Android useAppAudioSource)的音频常异步落盘, 事件回调时文件可能还没写完,
// 直接 copyAsync 会 FileNotFoundException → 整个录音流程裸崩。等文件就绪再复制。
async function waitForUploadableFileReady(uri: string, attempts: number = 10, delayMs: number = 150): Promise<boolean> {
  for (let i = 0; i < attempts; i++) {
    try {
      const info = await FileSystem.getInfoAsync(uri);
      if ((info as any)?.exists && ((info as any)?.size ?? 1) > 0) {
        return true;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  return false;
}

async function copyUploadableFileToPath(file: api.UploadableFile, destinationPath: string): Promise<void> {
  const normalized = normalizeUriUploadableFile(file);
  if (!normalized) {
    throw new Error("当前录音文件格式无法保存到本地目录。");
  }
  const ready = await waitForUploadableFileReady(normalized.uri);
  if (!ready) {
    throw new Error("录音音频尚未就绪或未生成（系统语音识别可能未持久化音频）。");
  }
  await FileSystem.copyAsync({
    from: normalized.uri,
    to: destinationPath,
  });
}

async function readTextFile(path: string | null | undefined): Promise<string> {
  if (!path) {
    return "";
  }
  try {
    return await FileSystem.readAsStringAsync(path, { encoding: FileSystem.EncodingType.UTF8 });
  } catch {
    return "";
  }
}

async function writeTextFile(path: string, content: string): Promise<void> {
  await FileSystem.writeAsStringAsync(path, content, { encoding: FileSystem.EncodingType.UTF8 });
}

function parseSummaryJson(value: string | null | undefined): Record<string, unknown> | null {
  if (!value?.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export async function saveRecordingSession(input: SaveRecordingSessionInput): Promise<RecordingSession> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持本地录音目录。");
  }

  const recordingId = makeRecordingId();
  const scopeKey = getActiveScopeKey();
  const paths = buildRecordingPaths(FileSystem.documentDirectory, scopeKey, recordingId);
  const createdAt = new Date().toISOString();
  const rawTranscript = input.rawTranscript?.trim() ?? "";
  const cleanTranscript = (input.cleanTranscript?.trim() || cleanTranscriptText(rawTranscript)).trim();
  const summary = buildRecordingSummary({
    cleanTranscript,
    durationSeconds: input.durationSeconds ?? null,
    title: input.title ?? null,
    generatedAt: createdAt,
  });
  const segments = normalizeRecordingSegments(input.segments, rawTranscript || cleanTranscript, recordingId, createdAt);
  const targetType = input.targetType ?? "unbound";
  const canSyncText = targetType !== "unbound" && cleanTranscript.length > 0;
  const asrFailed = cleanTranscript.length === 0 || Boolean(input.asrError?.trim());

  await FileSystem.makeDirectoryAsync(paths.directory, { intermediates: true });
  await copyUploadableFileToPath(input.file, paths.audioPath);
  await writeTextFile(paths.rawTranscriptPath, rawTranscript);
  await writeTextFile(paths.cleanTranscriptPath, cleanTranscript);
  await writeTextFile(paths.summaryPath, JSON.stringify(summary, null, 2));

  let audioHash: string | null = null;
  try {
    const info = await FileSystem.getInfoAsync(paths.audioPath, { md5: true } as any);
    audioHash = typeof (info as any)?.md5 === "string" ? (info as any).md5 : null;
  } catch {}

  const session: RecordingSession = {
    id: recordingId,
    scopeKey,
    source: input.source ?? "manual",
    targetType,
    targetLocalId: input.targetLocalId ?? null,
    targetRemoteId: input.targetRemoteId ?? null,
    clientId: input.clientId ?? null,
    eventLineId: input.eventLineId ?? null,
    taskId: input.taskId ?? null,
    meetingId: input.meetingId ?? null,
    audioPath: paths.audioPath,
    durationSeconds: input.durationSeconds ?? null,
    mimeType: normalizeUriUploadableFile(input.file)?.type ?? "audio/m4a",
    audioHash,
    rawTranscriptPath: paths.rawTranscriptPath,
    cleanTranscriptPath: paths.cleanTranscriptPath,
    summaryJson: JSON.stringify(summary),
    status: asrFailed ? "asr_failed" : "local_saved",
    syncStatus: canSyncText ? "pending" : "local_only",
    lastError: input.asrError?.trim() || (asrFailed ? "本地语音识别没有返回文本。" : null),
    latitude: input.latitude ?? null,
    longitude: input.longitude ?? null,
    placeLabel: input.placeLabel ?? null,
    createdAt,
    updatedAt: createdAt,
  };

  localDb.upsertRecordingSession(session);
  localDb.replaceRecordingSegments(recordingId, segments);
  return session;
}

export async function syncRecordingSessionText(recordingId: string): Promise<api.MobileRecordingTextIngestResponse> {
  const session = localDb.getRecordingSessionById(recordingId);
  if (!session) {
    throw new Error("录音会话不存在。");
  }
  if (session.targetType === "unbound") {
    throw new Error("未选择挂载目标的录音不会同步到云端。");
  }

  let workingSession = session;
  if (session.targetType === "task" && session.targetLocalId) {
    const task = localDb.getTaskById(session.targetLocalId);
    if (task?.remoteId && (!session.taskId || !session.targetRemoteId)) {
      workingSession =
        localDb.patchRecordingSession(recordingId, {
          targetRemoteId: task.remoteId,
          taskId: task.remoteId,
          clientId: session.clientId ?? task.clientId ?? null,
          eventLineId: session.eventLineId ?? task.eventLineId ?? null,
        }) ?? session;
    }
  }

  const rawTranscript = await readTextFile(workingSession.rawTranscriptPath);
  const cleanTranscript = await readTextFile(workingSession.cleanTranscriptPath);
  if (!cleanTranscript.trim()) {
    localDb.patchRecordingSession(recordingId, {
      status: "needs_action",
      syncStatus: "local_only",
      lastError: "录音没有可同步的转写文本。",
    });
    throw new Error("录音没有可同步的转写文本。");
  }

  const segments = localDb.getRecordingSegments(recordingId);
  const summary = parseSummaryJson(workingSession.summaryJson);
  const payload = buildRecordingTextIngestPayload({
    session: workingSession,
    segments,
    rawTranscript,
    cleanTranscript,
    summary,
  });

  localDb.markRecordingTextSyncState(recordingId, "syncing", null);
  try {
    const response = await api.ingestMobileRecordingText(payload);
    localDb.patchRecordingSession(recordingId, {
      syncStatus: response.syncStatus === "synced" ? "synced" : "pending",
      lastError: null,
    });
    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "录音文本同步失败。";
    localDb.markRecordingTextSyncState(recordingId, "failed", message);
    throw error;
  }
}

/**
 * 云端 ASR 兜底: 本地语音识别失败(无转写文本)时, 把本地音频上传为任务附件,
 * 调云端豆包 ASR 转写, 把文字回填到录音会话并触发文本同步。
 * 仅适用于已挂到任务、且本地音频仍在的录音。云链路随登录的服务地址走(组织级配一次)。
 */
export async function cloudTranscribeRecordingSession(recordingId: string): Promise<RecordingSession> {
  const session = localDb.getRecordingSessionById(recordingId);
  if (!session) {
    throw new Error("录音会话不存在。");
  }
  if (session.targetType !== "task" || !session.taskId) {
    throw new Error("云端转写需要先把录音挂到任务上。");
  }
  if (!session.audioPath) {
    throw new Error("找不到本地音频文件，无法云端转写。");
  }

  const taskId = session.taskId;
  const ext = (session.audioPath.split("?")[0].split(".").pop() || "m4a").toLowerCase();
  const uploadFile = {
    uri: session.audioPath,
    name: `recording-${recordingId}.${ext}`,
    type: `audio/${ext === "caf" ? "x-caf" : ext}`,
  };

  localDb.markRecordingTextSyncState(recordingId, "syncing", null);
  try {
    // 1) 上传音频为任务附件(云端转写需要云上可访问的音频)
    const task = await api.uploadTaskAttachment(taskId, {
      file: uploadFile,
      title: "云端转写录音",
      durationSeconds: session.durationSeconds ?? undefined,
    });
    // 2) 取刚上传的音频附件(最新一个 audio/*)
    const audioAttachments = (task.attachments ?? []).filter((a) =>
      String(a.mimeType ?? "").startsWith("audio/"),
    );
    const attachment = audioAttachments[audioAttachments.length - 1];
    if (!attachment) {
      throw new Error("音频附件上传后未找到。");
    }
    // 3) 云端转写(豆包 SeedASR)
    const result = await api.transcribeTaskAttachmentToDocument(taskId, attachment.id);
    const transcript = (result.transcript ?? "").trim();
    if (!transcript) {
      throw new Error("云端转写未返回有效文本。");
    }
    // 4) 回填到本地会话 + 触发文本同步
    if (session.cleanTranscriptPath) {
      await writeTextFile(session.cleanTranscriptPath, transcript);
    }
    if (session.rawTranscriptPath) {
      await writeTextFile(session.rawTranscriptPath, transcript);
    }
    localDb.patchRecordingSession(recordingId, {
      status: "local_saved",
      syncStatus: "pending",
      lastError: null,
    });
    await syncRecordingSessionText(recordingId);
    return localDb.getRecordingSessionById(recordingId) ?? session;
  } catch (error) {
    const message = error instanceof Error ? error.message : "云端转写失败。";
    localDb.markRecordingTextSyncState(recordingId, "failed", message);
    throw error;
  }
}

export async function saveTaskRecording(
  task: TaskRecord,
  input: Omit<SaveRecordingSessionInput, "targetType" | "targetLocalId" | "targetRemoteId" | "clientId" | "eventLineId" | "taskId" | "source">,
): Promise<RecordingSession> {
  const latestTask = localDb.getTaskById(task.id) ?? task;
  const session = await saveRecordingSession({
    ...input,
    source: "task_detail",
    targetType: "task",
    targetLocalId: latestTask.id,
    targetRemoteId: latestTask.remoteId ?? null,
    clientId: latestTask.clientId ?? null,
    eventLineId: latestTask.eventLineId ?? null,
    taskId: latestTask.remoteId ?? null,
  });

  if (session.syncStatus === "pending") {
    try {
      await syncRecordingSessionText(session.id);
    } catch (error) {
      // 同步失败不让保存失败：失败态已由 syncRecordingSessionText 内部落库
      // (syncStatus=failed/needs_action + lastError)，任务详情会显示红卡并可重试转写。
      // 这里仅补一条诊断日志，避免完全静默。
      console.warn("[recording] 录音文本同步失败(状态已落库，可在任务内重试)", {
        recordingId: session.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  return localDb.getRecordingSessionById(session.id) ?? session;
}

export async function attachRecordingSessionToTask(
  recordingId: string,
  task: TaskRecord,
): Promise<RecordingSession> {
  const existing = localDb.getRecordingSessionById(recordingId);
  if (!existing) {
    throw new Error("录音会话不存在。");
  }

  const latestTask = localDb.getTaskById(task.id) ?? task;
  const cleanTranscript = await readTextFile(existing.cleanTranscriptPath);
  const hasCleanTranscript = cleanTranscript.trim().length > 0;

  const patched = localDb.patchRecordingSession(recordingId, {
    targetType: "task",
    targetLocalId: latestTask.id,
    targetRemoteId: latestTask.remoteId ?? null,
    clientId: latestTask.clientId ?? null,
    eventLineId: latestTask.eventLineId ?? null,
    taskId: latestTask.remoteId ?? null,
    status: hasCleanTranscript ? "local_saved" : "needs_action",
    syncStatus: hasCleanTranscript ? "pending" : "local_only",
    lastError: hasCleanTranscript ? null : existing.lastError ?? "录音没有可同步的转写文本。",
  });

  if (!patched) {
    throw new Error("录音会话不存在。");
  }

  if (patched.syncStatus === "pending") {
    // 有文字：只把【文字】同步进任务（音频始终留在手机本地，不上电脑端）。
    try {
      await syncRecordingSessionText(patched.id);
    } catch (error) {
      // 同上：失败态已落库，任务详情可见并可重试，这里仅补诊断日志。
      console.warn("[recording] 挂接后录音文本同步失败(状态已落库，可在任务内重试)", {
        recordingId: patched.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  // 没文字时：标记 needs_action 待转写，不在此上传音频（旧的 cloudTranscribe 会把音频变成任务附件、
  // 进而同步到电脑端，违反"本地录音不同步电脑端"）。真正转写应走后端 transcribe-only 接口
  // （音频进、纯文字出、不落任务附件）——见交给电脑端的对接说明。
  return localDb.getRecordingSessionById(patched.id) ?? patched;
}

export async function saveUnboundRecording(
  input: Omit<SaveRecordingSessionInput, "targetType" | "source"> & {
    source?: RecordingSource;
    targetType?: RecordingTargetType;
  },
): Promise<RecordingSession> {
  const session = await saveRecordingSession({
    ...input,
    source: input.source ?? "record_note",
    targetType: input.targetType ?? "unbound",
  });
  if (session.syncStatus === "pending") {
    try {
      await syncRecordingSessionText(session.id);
    } catch (error) {
      // 同步失败不让保存失败：失败态已由 syncRecordingSessionText 内部落库
      // (syncStatus=failed/needs_action + lastError)，任务详情会显示红卡并可重试转写。
      // 这里仅补一条诊断日志，避免完全静默。
      console.warn("[recording] 录音文本同步失败(状态已落库，可在任务内重试)", {
        recordingId: session.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  return localDb.getRecordingSessionById(session.id) ?? session;
}

/**
 * 彻底删除一条录音（孤儿存档左滑删除用）：删 DB 记录 + 段 + 本地音频/转写/摘要文件。
 * 孤儿录音尚未进系统，删了即不可恢复。
 */
export async function deleteRecordingArchive(recordingId: string): Promise<void> {
  const session = localDb.getRecordingSessionById(recordingId);
  localDb.deleteRecordingSession(recordingId);
  if (session?.audioPath) {
    // 音频/转写/摘要同在一个录音目录下，删整个目录即可。
    // 守卫 lastIndexOf > 0：没有 "/"(返回 -1) 时 slice(0,-1) 会截出错误路径误删；
    // "/" 在首位(返回 0) 时不该删根。两种情况都跳过。
    const slashIndex = session.audioPath.lastIndexOf("/");
    if (slashIndex > 0) {
      const directory = session.audioPath.slice(0, slashIndex);
      try {
        await FileSystem.deleteAsync(directory, { idempotent: true });
      } catch {}
    }
  }
}

export async function retryPendingRecordingTextSync(limit: number = 20): Promise<void> {
  const sessions = localDb.listPendingRecordingTextSync(limit);
  for (const session of sessions) {
    try {
      await syncRecordingSessionText(session.id);
    } catch {}
  }
}

export function getRecordingDiagnosticsSnapshot(): RecordingDiagnosticsSnapshot {
  const diagnostics = localDb.getRecordingDiagnostics();
  return {
    localDirectory: getRecordingRootDirectory(),
    ...diagnostics,
  };
}
