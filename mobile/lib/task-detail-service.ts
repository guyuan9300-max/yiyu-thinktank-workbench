import {
  fetchClientNarrative,
  fetchTaskActivities,
  fetchTaskById,
  fetchTaskContextPreview,
  fetchTaskUnderstanding,
} from "./api";
import { File } from "expo-file-system";
import * as localDb from "./local-db";
import { getLegacyUploadPseudoOp } from "./legacy-upload-ops";
import {
  attachFileToTask,
  retryLegacyUploadPseudoOp,
  type TaskAttachmentResult,
} from "./record-note-service";
import * as Linking from "expo-linking";
import type { TaskAttachmentRecord, TaskRecord } from "./types";

export {
  fetchClientNarrative,
  fetchTaskActivities,
  fetchTaskById,
  fetchTaskContextPreview,
  fetchTaskUnderstanding,
};

function isTaskAttachmentPickerCancelled(error: unknown): boolean {
  return error instanceof Error && /cancel/i.test(error.message);
}

export async function pickAndUploadTaskAttachment(task: TaskRecord): Promise<TaskAttachmentResult | null> {
  let pickedFile: File | null = null;
  try {
    const selection = await File.pickFileAsync();
    pickedFile = Array.isArray(selection) ? selection[0] ?? null : selection;
  } catch (error) {
    if (isTaskAttachmentPickerCancelled(error)) {
      return null;
    }
    throw error;
  }

  if (!pickedFile) {
    return null;
  }

  return attachFileToTask(task, {
    file: {
      uri: pickedFile.uri,
      name: pickedFile.name || `attachment-${Date.now()}`,
      type: pickedFile.type || "application/octet-stream",
    },
    title: pickedFile.name || null,
  });
}

export async function retryTaskAttachmentTransferOp(
  opId: string,
  taskId: string,
): Promise<{
  ok: boolean;
  task: TaskRecord | null;
  message: string;
  status: "queued" | "processing" | "needs_attention" | "completed";
}> {
  const result = await retryLegacyUploadPseudoOp(opId);
  const latestTask = localDb.getTaskById(taskId) ?? null;
  if ("message" in result) {
    return {
      ok: false,
      task: latestTask,
      message: result.message,
      status: getLegacyUploadPseudoOp(opId)?.status ?? "needs_attention",
    };
  }
  return {
    ok: true,
    task: latestTask,
    message: "附件已重新加入上传链路。",
    status: getLegacyUploadPseudoOp(opId)?.status ?? "completed",
  };
}

function normalizeAttachmentUri(value: string): string {
  if (/^[a-z]+:/i.test(value)) {
    return value;
  }
  if (value.startsWith("/")) {
    return `file://${value}`;
  }
  return value;
}

export async function openTaskAttachment(attachment: TaskAttachmentRecord): Promise<void> {
  const rawUri = attachment.localPath || attachment.url || null;
  if (!rawUri) {
    throw new Error("当前附件还没有可打开的原件地址。");
  }
  const targetUri = encodeURI(normalizeAttachmentUri(rawUri));
  await Linking.openURL(targetUri);
}
