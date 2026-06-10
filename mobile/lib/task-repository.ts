import type { CreateTaskPayload, UpdateTaskPayload } from "./api";
import { buildCanonicalScheduleUpdates } from "./calendar-repository-core";
import { createClientOpId, createLocalEntityId } from "./local-ids";
import * as localDb from "./local-db";
import type { MutationReceipt, TaskRecord } from "./types";

function nowIso(): string {
  return new Date().toISOString();
}

function buildQueuedReceipt(task: TaskRecord, message: string): MutationReceipt {
  return {
    entityType: "task",
    localId: task.id,
    remoteId: task.remoteId ?? null,
    localState: "local_committed",
    remoteState: "queued",
    reasonCode: null,
    updatedAt: task.updatedAt ?? nowIso(),
    message,
  };
}

function normalizeTaskFromCreatePayload(
  localId: string,
  payload: CreateTaskPayload,
): TaskRecord {
  const timestamp = nowIso();
  const canonicalSchedule = payload.dueDate
    ? buildCanonicalScheduleUpdates(payload.dueDate, payload.durationMinutes ?? null)
    : null;
  return {
    id: localId,
    remoteId: null,
    title: payload.title.trim(),
    description: payload.description ?? null,
    dueDate: payload.dueDate ?? null,
    durationMinutes: payload.durationMinutes ?? null,
    deadlineAt: payload.deadlineAt ?? canonicalSchedule?.deadlineAt ?? null,
    scheduledStartAt: payload.scheduledStartAt ?? canonicalSchedule?.scheduledStartAt ?? null,
    scheduledEndAt: payload.scheduledEndAt ?? canonicalSchedule?.scheduledEndAt ?? null,
    completedAt: payload.completedAt ?? null,
    reminderMinutesBefore: payload.reminderMinutesBefore ?? null,
    priority: payload.priority ?? "normal",
    progressStatus: "inbox",
    tags: payload.tags ?? null,
    clientId: payload.clientId ?? null,
    eventLineId: payload.eventLineId ?? null,
    listId: payload.listId ?? null,
    businessCategory: payload.businessCategory ?? null,
    currentBlocker: payload.currentBlocker ?? null,
    nextAction: payload.nextAction ?? null,
    recentDecision: payload.recentDecision ?? null,
    localVersion: 1,
    baseRemoteVersion: null,
    serverVersion: null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    deletedAt: null,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

export function createTaskLocalFirst(payload: CreateTaskPayload): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const localId = createLocalEntityId("task");
  const task = normalizeTaskFromCreatePayload(localId, payload);
  localDb.commitTaskMutation({
    task,
    operation: "create",
    clientOpId: createClientOpId("task"),
    payload: {
      ...payload,
      deadlineAt: task.deadlineAt ?? undefined,
      scheduledStartAt: task.scheduledStartAt ?? undefined,
      scheduledEndAt: task.scheduledEndAt ?? undefined,
      completedAt: task.completedAt ?? undefined,
      clientEntityId: localId,
    },
  });
  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存，等待同步"),
  };
}

export function updateTaskLocalFirst(taskId: string, updates: UpdateTaskPayload): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法更新");
  }

  const hasDueDate = Object.prototype.hasOwnProperty.call(updates, "dueDate") && updates.dueDate !== undefined;
  const hasDurationMinutes =
    Object.prototype.hasOwnProperty.call(updates, "durationMinutes") && updates.durationMinutes !== undefined;
  const hasDeadlineAt = Object.prototype.hasOwnProperty.call(updates, "deadlineAt") && updates.deadlineAt !== undefined;
  const hasScheduledStartAt =
    Object.prototype.hasOwnProperty.call(updates, "scheduledStartAt") && updates.scheduledStartAt !== undefined;
  const hasScheduledEndAt =
    Object.prototype.hasOwnProperty.call(updates, "scheduledEndAt") && updates.scheduledEndAt !== undefined;
  const hasCompletedAt = Object.prototype.hasOwnProperty.call(updates, "completedAt") && updates.completedAt !== undefined;
  const hasReminder = Object.prototype.hasOwnProperty.call(updates, "reminderMinutesBefore") && updates.reminderMinutesBefore !== undefined;
  const canonicalSchedule = hasDueDate
    ? buildCanonicalScheduleUpdates(updates.dueDate ?? null, hasDurationMinutes ? updates.durationMinutes ?? null : existing.durationMinutes ?? null)
    : null;
  const nextProgressStatus = updates.progressStatus ?? existing.progressStatus;
  const nextCompletedAt = hasCompletedAt
    ? updates.completedAt ?? null
    : nextProgressStatus === "done" && existing.progressStatus !== "done"
      ? nowIso()
      : nextProgressStatus === "done"
        ? existing.completedAt ?? null
        : null;

  const task: TaskRecord = {
    ...existing,
    title: updates.title?.trim() ?? existing.title,
    description: updates.description ?? existing.description ?? null,
    dueDate: hasDueDate ? updates.dueDate ?? null : existing.dueDate ?? null,
    durationMinutes: hasDurationMinutes ? updates.durationMinutes ?? null : existing.durationMinutes ?? null,
    deadlineAt: hasDeadlineAt ? updates.deadlineAt ?? null : canonicalSchedule?.deadlineAt ?? existing.deadlineAt ?? null,
    scheduledStartAt: hasScheduledStartAt ? updates.scheduledStartAt ?? null : canonicalSchedule?.scheduledStartAt ?? existing.scheduledStartAt ?? null,
    scheduledEndAt: hasScheduledEndAt ? updates.scheduledEndAt ?? null : canonicalSchedule?.scheduledEndAt ?? existing.scheduledEndAt ?? null,
    completedAt: nextCompletedAt,
    reminderMinutesBefore: hasReminder ? updates.reminderMinutesBefore ?? null : existing.reminderMinutesBefore ?? null,
    priority: updates.priority ?? existing.priority,
    progressStatus: nextProgressStatus,
    clientId: updates.clientId ?? existing.clientId ?? null,
    eventLineId: updates.eventLineId ?? existing.eventLineId ?? null,
    listId: updates.listId ?? existing.listId ?? null,
    tags: updates.tags ?? existing.tags ?? null,
    businessCategory: updates.businessCategory ?? existing.businessCategory ?? null,
    currentBlocker: updates.currentBlocker ?? existing.currentBlocker ?? null,
    nextAction: updates.nextAction ?? existing.nextAction ?? null,
    recentDecision: updates.recentDecision ?? existing.recentDecision ?? null,
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    updatedAt: nowIso(),
  };

  localDb.commitTaskMutation({
    task,
    operation: "update",
    clientOpId: createClientOpId("task"),
    payload: {
      ...updates,
      ...(canonicalSchedule
        ? {
            deadlineAt: task.deadlineAt,
            scheduledStartAt: task.scheduledStartAt,
            scheduledEndAt: task.scheduledEndAt,
          }
        : {}),
      ...(nextCompletedAt !== (existing.completedAt ?? null) ? { completedAt: nextCompletedAt } : {}),
      clientEntityId: task.id,
    },
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存，等待同步"),
  };
}

export function deleteTaskLocalFirst(taskId: string): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法删除");
  }
  const timestamp = nowIso();
  const task: TaskRecord = {
    ...existing,
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    deletedAt: timestamp,
    updatedAt: timestamp,
  };

  localDb.commitTaskMutation({
    task,
    operation: "delete",
    clientOpId: createClientOpId("task"),
    payload: {
      clientEntityId: task.id,
    },
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已删除，等待同步"),
  };
}

export function completeTaskWithReviewLocalFirst(taskId: string, reviewNote: string): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const trimmedReviewNote = reviewNote.trim();
  if (!trimmedReviewNote) {
    throw new Error("复盘内容不能为空");
  }

  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法完成复盘");
  }

  const task: TaskRecord = {
    ...existing,
    progressStatus: "done",
    completionNote: trimmedReviewNote,
    completedAt: existing.completedAt ?? nowIso(),
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    updatedAt: nowIso(),
  };

  localDb.commitTaskReviewMutation({
    task,
    clientOpId: createClientOpId("task"),
    reviewNote: trimmedReviewNote,
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存复盘，等待同步"),
  };
}
