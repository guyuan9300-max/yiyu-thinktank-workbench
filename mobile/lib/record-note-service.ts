import * as FileSystem from "expo-file-system/legacy";
import * as api from "./api";
import * as localDb from "./local-db";
import { resolveLegacyUploadFailureStatus } from "./legacy-upload-runner-core";
import { inferAttachmentExtension } from "./attachment-extension-core";
import {
  getLegacyUploadPseudoOp,
  getLegacyUploadPseudoOps,
  markLegacyUploadPseudoOp,
  patchLegacyUploadPseudoOp,
  removeLegacyUploadPseudoOp,
  upsertLegacyUploadPseudoOp,
} from "./legacy-upload-ops";
import type { RecordingSegmentDraft } from "./recording-session-core";
import { saveTaskRecording } from "./recording-session-service";
import { getSyncControlState, triggerSync } from "./sync-engine";
import type {
  LegacyUploadPseudoOp,
  LegacyUploadReasonCode,
  TaskRecord,
} from "./types";

interface EnsureRemoteTaskResult {
  task: TaskRecord;
  remoteTaskId: string | null;
}

export interface RecordedAttachmentResult {
  status:
    | "uploaded"
    | "pending_attachment"
    | "needs_attention"
    | "synced"
    | "pending_text_sync"
    | "local_saved";
  task: TaskRecord;
  message: string;
  recordingId?: string;
}

export type TaskAttachmentResult = RecordedAttachmentResult;

export type RecordedUploadableFile = api.UploadableFile;

interface RecordedAudioDraft {
  opId: string;
  objectLocalId: string;
  filePath: string;
  size: number | null;
  mtime: number | null;
  hash: string | null;
  mimeType: string;
}

const RECORD_NOTE_DRAFTS_DIR = `${FileSystem.documentDirectory ?? ""}record-note-drafts/`;
const TASK_ATTACHMENT_DRAFTS_DIR = `${FileSystem.documentDirectory ?? ""}task-attachment-drafts/`;

function normalizeUriUploadableFile(
  file: api.UploadableFile,
  defaults?: {
    name: string;
    type: string;
  },
): { uri: string; name: string; type: string } | null {
  if (!file || typeof file !== "object" || !("uri" in file)) {
    return null;
  }
  if (!file.uri) {
    return null;
  }
  return {
    uri: file.uri,
    name: file.name || defaults?.name || `record-note-${Date.now()}.m4a`,
    type: file.type || defaults?.type || "audio/m4a",
  };
}

// 后缀推断已抽到 lib/attachment-extension-core.ts(纯逻辑+单测), 这里只做别名复用
const inferExtension = inferAttachmentExtension;

function makeTransferDraftId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function ensureRecordNoteDraftDirectory(taskLocalId: string): Promise<string> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持录音原件暂存。");
  }
  const scopeKey = localDb.getActiveAccountScopeKey() ?? "no-org:no-user";
  const scopeDir = encodeURIComponent(scopeKey);
  const directory = `${RECORD_NOTE_DRAFTS_DIR}${scopeDir}/${taskLocalId}/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  return directory;
}

async function ensureTaskAttachmentDraftDirectory(taskLocalId: string): Promise<string> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持附件原件暂存。");
  }
  const scopeKey = localDb.getActiveAccountScopeKey() ?? "no-org:no-user";
  const scopeDir = encodeURIComponent(scopeKey);
  const directory = `${TASK_ATTACHMENT_DRAFTS_DIR}${scopeDir}/${taskLocalId}/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  return directory;
}

async function persistRecordedAudioDraft(
  taskLocalId: string,
  file: api.UploadableFile,
): Promise<RecordedAudioDraft | null> {
  const normalized = normalizeUriUploadableFile(file, {
    name: `record-note-${Date.now()}.m4a`,
    type: "audio/m4a",
  });
  if (!normalized) {
    return null;
  }
  const objectLocalId = makeTransferDraftId("voice_draft");
  const extension = inferExtension(normalized);
  const directory = await ensureRecordNoteDraftDirectory(taskLocalId);
  const destinationPath = `${directory}${objectLocalId}.${extension}`;
  if (normalized.uri !== destinationPath) {
    await FileSystem.copyAsync({ from: normalized.uri, to: destinationPath });
  }
  const info = await FileSystem.getInfoAsync(destinationPath, { md5: true } as any);
  return {
    opId: `legacy_upload_${objectLocalId}`,
    objectLocalId,
    filePath: destinationPath,
    size: typeof (info as any)?.size === "number" ? (info as any).size : null,
    mtime:
      typeof (info as any)?.modificationTime === "number"
        ? Number((info as any).modificationTime)
        : null,
    hash: typeof (info as any)?.md5 === "string" ? (info as any).md5 : null,
    mimeType: normalized.type,
  };
}

async function persistTaskAttachmentDraft(
  taskLocalId: string,
  file: api.UploadableFile,
): Promise<RecordedAudioDraft | null> {
  const normalized = normalizeUriUploadableFile(file, {
    name: `attachment-${Date.now()}`,
    type: "application/octet-stream",
  });
  if (!normalized) {
    return null;
  }
  const objectLocalId = makeTransferDraftId("file_draft");
  const extension = inferExtension(normalized);
  const directory = await ensureTaskAttachmentDraftDirectory(taskLocalId);
  const destinationPath = `${directory}${objectLocalId}.${extension}`;
  if (normalized.uri !== destinationPath) {
    await FileSystem.copyAsync({ from: normalized.uri, to: destinationPath });
  }
  const info = await FileSystem.getInfoAsync(destinationPath, { md5: true } as any);
  return {
    opId: `legacy_upload_${objectLocalId}`,
    objectLocalId,
    filePath: destinationPath,
    size: typeof (info as any)?.size === "number" ? (info as any).size : null,
    mtime:
      typeof (info as any)?.modificationTime === "number"
        ? Number((info as any).modificationTime)
        : null,
    hash: typeof (info as any)?.md5 === "string" ? (info as any).md5 : null,
    mimeType: normalized.type || "application/octet-stream",
  };
}

async function removePersistedRecordedAudio(path: string): Promise<void> {
  try {
    await FileSystem.deleteAsync(path, { idempotent: true });
  } catch {}
}

function mapLegacyUploadErrorReasonCode(error: unknown): LegacyUploadReasonCode {
  if (error instanceof api.ApiError) {
    if (error.status === 401) return "auth_required";
    if (error.status === 408 || error.status === 429 || error.status >= 500) {
      return "network_unavailable";
    }
    return "upload_failed";
  }
  if (error instanceof Error) {
    const lowered = error.message.toLowerCase();
    if (lowered.includes("network")) return "network_unavailable";
    return "unknown_error";
  }
  return "unknown_error";
}

function getPendingBindReasonCode(): LegacyUploadReasonCode {
  const syncControl = getSyncControlState();
  if (syncControl.freezeState === "paused_by_user") {
    return "manual_pause";
  }
  if (syncControl.freezeState === "blocked_by_integrity") {
    return "integrity_blocked";
  }
  if (syncControl.freezeState === "blocked_by_scope_mismatch") {
    return "scope_mismatch";
  }
  return "bind_pending_remote_id";
}

function buildPendingAttachmentMessage(
  reasonCode: LegacyUploadReasonCode,
  objectLabel = "录音",
): string {
  switch (reasonCode) {
    case "manual_pause":
      return `任务已保存，${objectLabel}待挂接。当前同步已暂停，请恢复同步后重试。`;
    case "integrity_blocked":
      return `任务已保存，${objectLabel}待挂接。当前同步因本地完整性问题被冻结，请先在系统健康中处理。`;
    case "scope_mismatch":
      return `任务已保存，${objectLabel}待挂接。当前账号作用域未就绪，请重新登录后重试。`;
    default:
      return `任务已保存，${objectLabel}待挂接。可在系统健康中继续重试上传。`;
  }
}

function isPendingAttachmentReasonCode(reasonCode: LegacyUploadReasonCode): boolean {
  return (
    reasonCode === "bind_pending_remote_id" ||
    reasonCode === "manual_pause" ||
    reasonCode === "integrity_blocked" ||
    reasonCode === "scope_mismatch"
  );
}

async function ensureRemoteTaskId(task: TaskRecord): Promise<EnsureRemoteTaskResult> {
  const initialSnapshot = localDb.getTaskById(task.id) ?? task;
  if (initialSnapshot.remoteId) {
    return {
      task: initialSnapshot,
      remoteTaskId: initialSnapshot.remoteId,
    };
  }

  try {
    await triggerSync();
  } catch {}

  const nextSnapshot = localDb.getTaskById(task.id) ?? initialSnapshot;
  return {
    task: nextSnapshot,
    remoteTaskId: nextSnapshot.remoteId ?? null,
  };
}

async function validatePersistedLegacyUploadFile(
  op: LegacyUploadPseudoOp,
): Promise<LegacyUploadReasonCode | null> {
  const info = op.hash
    ? await FileSystem.getInfoAsync(op.filePath, { md5: true } as any)
    : await FileSystem.getInfoAsync(op.filePath);
  if (!(info as any)?.exists) {
    return "file_missing";
  }
  if (
    op.size != null &&
    typeof (info as any)?.size === "number" &&
    (info as any).size !== op.size
  ) {
    return "file_corrupted";
  }
  if (
    op.mtime != null &&
    typeof (info as any)?.modificationTime === "number" &&
    Number((info as any).modificationTime) !== op.mtime
  ) {
    return "file_corrupted";
  }
  if (
    op.hash &&
    typeof (info as any)?.md5 === "string" &&
    (info as any).md5 !== op.hash
  ) {
    return "file_corrupted";
  }
  return null;
}

async function uploadLegacyRecordedAudioOp(
  op: LegacyUploadPseudoOp,
): Promise<TaskRecord> {
  const task = localDb.getTaskById(op.taskLocalId);
  if (!task) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: "scope_mismatch",
      incrementRetryCount: true,
    });
    throw new Error("对应任务不存在，无法恢复录音上传。");
  }

  const resolved = await ensureRemoteTaskId(task);
  patchLegacyUploadPseudoOp(op.opId, {
    objectRemoteId: resolved.remoteTaskId,
  });
  if (!resolved.remoteTaskId) {
    const reasonCode = getPendingBindReasonCode();
    markLegacyUploadPseudoOp(op.opId, {
      status: "queued",
      reasonCode,
    });
    throw new Error(buildPendingAttachmentMessage(reasonCode, "录音"));
  }

  const latestOp = getLegacyUploadPseudoOp(op.opId) ?? op;
  const validationReason = await validatePersistedLegacyUploadFile(latestOp);
  if (validationReason) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: validationReason,
      incrementRetryCount: true,
    });
    throw new Error(validationReason === "file_missing" ? "录音原件丢失。" : "录音原件已损坏。");
  }

  markLegacyUploadPseudoOp(op.opId, {
    status: "processing",
    reasonCode: "unknown_error",
  });

  try {
    // filename 从 filePath 推扩展名生成，绝不用 displayTitle:中文标题含空格/冒号且无扩展名，
    // 当 multipart filename 会丢扩展名 → 后端豆包 ASR 按后缀/MIME 识别失败而拒绝转写。
    // displayTitle 只作为下面的 title 字段。
    const recordExt = (latestOp.filePath.split("?")[0].split(".").pop() || "m4a").toLowerCase();
    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
      file: {
        uri: latestOp.filePath,
        name: `record-note-${latestOp.objectLocalId}.${recordExt}`,
        type: latestOp.mimeType || "audio/m4a",
      },
      clientId: resolved.task.clientId,
      eventLineId: resolved.task.eventLineId,
      title: latestOp.displayTitle ?? null,
      taskTitle: resolved.task.title ?? null,
      durationSeconds: latestOp.durationSeconds ?? null,
    });

    try {
      const latestAttachment = uploadedTask.attachments?.[0];
      if (latestAttachment?.id) {
        await api.transcribeTaskAttachmentToDocument(resolved.remoteTaskId, latestAttachment.id);
      }
    } catch {}

    localDb.reconcileTaskServerAck({
      taskId: resolved.task.id,
      clientOpId: op.opId,
      operation: "update",
      ackLocalVersion: localDb.getTaskById(resolved.task.id)?.localVersion ?? null,
      serverTask: {
        ...uploadedTask,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
    });

    removeLegacyUploadPseudoOp(op.opId);
    await removePersistedRecordedAudio(latestOp.filePath);
    return localDb.getTaskById(resolved.task.id) ?? {
      ...uploadedTask,
      id: resolved.task.id,
      remoteId: uploadedTask.remoteId ?? uploadedTask.id,
    };
  } catch (error) {
    const reasonCode = mapLegacyUploadErrorReasonCode(error);
    markLegacyUploadPseudoOp(op.opId, {
      status: resolveLegacyUploadFailureStatus(reasonCode),
      reasonCode,
      incrementRetryCount: true,
    });
    throw error;
  }
}

async function uploadLegacyTaskAttachmentOp(
  op: LegacyUploadPseudoOp,
): Promise<TaskRecord> {
  const task = localDb.getTaskById(op.taskLocalId);
  if (!task) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: "scope_mismatch",
      incrementRetryCount: true,
    });
    throw new Error("对应任务不存在，无法恢复附件上传。");
  }

  const resolved = await ensureRemoteTaskId(task);
  patchLegacyUploadPseudoOp(op.opId, {
    objectRemoteId: resolved.remoteTaskId,
  });
  if (!resolved.remoteTaskId) {
    const reasonCode = getPendingBindReasonCode();
    markLegacyUploadPseudoOp(op.opId, {
      status: "queued",
      reasonCode,
    });
    throw new Error(buildPendingAttachmentMessage(reasonCode, "附件"));
  }

  const latestOp = getLegacyUploadPseudoOp(op.opId) ?? op;
  const validationReason = await validatePersistedLegacyUploadFile(latestOp);
  if (validationReason) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: validationReason,
      incrementRetryCount: true,
    });
    throw new Error(validationReason === "file_missing" ? "附件原件丢失。" : "附件原件已损坏。");
  }

  markLegacyUploadPseudoOp(op.opId, {
    status: "processing",
    reasonCode: "unknown_error",
  });

  try {
    // 同上:filename 从 filePath 推扩展名，displayTitle 只作 title 字段，避免非法 filename。
    const attachmentExt = (latestOp.filePath.split("?")[0].split(".").pop() || "bin").toLowerCase();
    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
      file: {
        uri: latestOp.filePath,
        name: `attachment-${latestOp.objectLocalId}.${attachmentExt}`,
        type: latestOp.mimeType || "application/octet-stream",
      },
      clientId: resolved.task.clientId,
      eventLineId: resolved.task.eventLineId,
      title: latestOp.displayTitle ?? null,
      taskTitle: resolved.task.title ?? null,
    });

    localDb.reconcileTaskServerAck({
      taskId: resolved.task.id,
      clientOpId: op.opId,
      operation: "update",
      ackLocalVersion: localDb.getTaskById(resolved.task.id)?.localVersion ?? null,
      serverTask: {
        ...uploadedTask,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
    });

    removeLegacyUploadPseudoOp(op.opId);
    await removePersistedRecordedAudio(latestOp.filePath);
    return localDb.getTaskById(resolved.task.id) ?? {
      ...uploadedTask,
      id: resolved.task.id,
      remoteId: uploadedTask.remoteId ?? uploadedTask.id,
    };
  } catch (error) {
    const reasonCode = mapLegacyUploadErrorReasonCode(error);
    markLegacyUploadPseudoOp(op.opId, {
      status: resolveLegacyUploadFailureStatus(reasonCode),
      reasonCode,
      incrementRetryCount: true,
    });
    throw error;
  }
}

export async function retryLegacyUploadPseudoOp(
  opId: string,
): Promise<{ ok: true } | { ok: false; reasonCode: LegacyUploadReasonCode; message: string }> {
  const op = getLegacyUploadPseudoOp(opId);
  if (!op) {
    return { ok: false, reasonCode: "unknown_error", message: "未找到待重试的上传项。" };
  }

  try {
    if (op.objectType === "task_attachment") {
      await uploadLegacyTaskAttachmentOp(op);
    } else {
      await uploadLegacyRecordedAudioOp(op);
    }
    return { ok: true };
  } catch (error) {
    const next = getLegacyUploadPseudoOp(opId);
    return {
      ok: false,
      reasonCode: next?.reasonCode ?? "unknown_error",
      message: error instanceof Error ? error.message : "附件上传重试失败。",
    };
  }
}

export async function retryAllLegacyUploadPseudoOps(): Promise<void> {
  const ops = getLegacyUploadPseudoOps().filter((item) => item.status !== "processing");
  for (const op of ops) {
    await retryLegacyUploadPseudoOp(op.opId);
  }
}

export async function attachRecordedAudioToTask(
  task: TaskRecord,
  payload: {
    file: api.UploadableFile;
    title?: string | null;
    durationSeconds?: number | null;
    rawTranscript?: string | null;
    cleanTranscript?: string | null;
    segments?: RecordingSegmentDraft[];
    asrError?: string | null;
  },
): Promise<RecordedAttachmentResult> {
  const session = await saveTaskRecording(task, {
    file: payload.file,
    title: payload.title ?? task.title,
    durationSeconds: payload.durationSeconds ?? null,
    rawTranscript: payload.rawTranscript ?? null,
    cleanTranscript: payload.cleanTranscript ?? null,
    segments: payload.segments ?? [],
    asrError: payload.asrError ?? null,
  });
  const latestTask = localDb.getTaskById(task.id) ?? task;

  if (session.syncStatus === "synced") {
    return {
      status: "synced",
      task: latestTask,
      message: "录音文本已同步到云端。",
      recordingId: session.id,
    };
  }
  if (session.syncStatus === "pending" || session.syncStatus === "syncing") {
    return {
      status: "pending_text_sync",
      task: latestTask,
      message: "录音已本地保存，转写文本将继续同步到云端。",
      recordingId: session.id,
    };
  }
  if (session.syncStatus === "failed") {
    return {
      status: "pending_text_sync",
      task: latestTask,
      message: session.lastError ?? "录音已本地保存，文本同步失败，稍后可在诊断页重试。",
      recordingId: session.id,
    };
  }
  if (session.status === "asr_failed" || session.status === "needs_action") {
    return {
      status: "needs_attention",
      task: latestTask,
      message: session.lastError ?? "录音已本地保存，但需要补充转写文本后再同步。",
      recordingId: session.id,
    };
  }
  return {
    status: "local_saved",
    task: latestTask,
    message: "录音已本地保存。",
    recordingId: session.id,
  };
}

export async function attachFileToTask(
  task: TaskRecord,
  payload: {
    file: api.UploadableFile;
    title?: string | null;
  },
): Promise<TaskAttachmentResult> {
  const fallbackTitle =
    normalizeUriUploadableFile(payload.file, {
      name: `attachment-${Date.now()}`,
      type: "application/octet-stream",
    })?.name || "附件";
  const attachmentTitle = payload.title?.trim() || fallbackTitle;
  const draft = await persistTaskAttachmentDraft(task.id, payload.file);
  const resolved = localDb.getTaskById(task.id) ?? task;

  if (!draft) {
    const remote = await ensureRemoteTaskId(resolved);
    if (!remote.remoteTaskId) {
      return {
        status: "pending_attachment",
        task: remote.task,
        message: buildPendingAttachmentMessage(getPendingBindReasonCode(), "附件"),
      };
    }
    const uploadedTask = await api.uploadTaskAttachment(remote.remoteTaskId, {
      file: payload.file,
      clientId: remote.task.clientId,
      eventLineId: remote.task.eventLineId,
      title: attachmentTitle,
      taskTitle: remote.task.title ?? null,
    });
    return {
      status: "uploaded",
      task: {
        ...uploadedTask,
        id: resolved.id,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
      message: "附件已上传",
    };
  }

  const pseudoOp = upsertLegacyUploadPseudoOp({
    opId: draft.opId,
    objectType: "task_attachment",
    objectLocalId: draft.objectLocalId,
    objectRemoteId: resolved.remoteId ?? null,
    lane: "transfer",
    status: "queued",
    retryCount: 0,
    reasonCode: "bind_pending_remote_id",
    createdAt: new Date().toISOString(),
    lastAttemptAt: null,
    displayTitle: attachmentTitle,
    taskLocalId: resolved.id,
    filePath: draft.filePath,
    size: draft.size,
    mtime: draft.mtime,
    hash: draft.hash,
    entityRefLocalId: resolved.id,
    mimeType: draft.mimeType,
  });

  try {
    const uploadedTask = await uploadLegacyTaskAttachmentOp(pseudoOp);
    return {
      status: "uploaded",
      task: uploadedTask as TaskRecord,
      message: "附件已上传",
    };
  } catch {
    const latestOp = getLegacyUploadPseudoOp(pseudoOp.opId);
    const reasonCode = latestOp?.reasonCode ?? getPendingBindReasonCode();
    if (isPendingAttachmentReasonCode(reasonCode)) {
      return {
        status: "pending_attachment",
        task: localDb.getTaskById(resolved.id) ?? resolved,
        message: buildPendingAttachmentMessage(reasonCode, "附件"),
      };
    }
    return {
      status: "needs_attention",
      task: localDb.getTaskById(resolved.id) ?? resolved,
      message: "附件需处理。请在系统健康页重试上传。",
    };
  }
}
