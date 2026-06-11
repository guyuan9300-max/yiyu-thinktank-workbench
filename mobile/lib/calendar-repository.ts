import * as api from "./api";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import {
  buildCanonicalScheduleUpdates,
  buildDueDateForCalendarDrop,
  buildTaskScheduleUpdatesFromPicker,
  decideCalendarWriteMode,
  type CalendarScheduleUpdates,
  type CalendarScheduleValue,
} from "./calendar-repository-core";
import { isCalendarLocalFirstWriteEnabled } from "./runtime-flags";
import {
  emitDataChanged,
  getSyncControlState,
  isSyncPaused,
  updateTaskOfflineFirst,
} from "./sync-engine";
import type { TaskRecord } from "./types";

export async function updateCalendarTaskSchedule(
  taskId: string,
  updates: CalendarScheduleUpdates | Pick<Partial<TaskRecord>, "dueDate" | "durationMinutes" | "deadlineAt" | "scheduledStartAt" | "scheduledEndAt">,
): Promise<TaskRecord> {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法更新排期");
  }
  const normalizedUpdates = Object.prototype.hasOwnProperty.call(updates, "dueDate")
    ? {
        ...buildCanonicalScheduleUpdates(
          updates.dueDate ?? null,
          Object.prototype.hasOwnProperty.call(updates, "durationMinutes")
            ? updates.durationMinutes ?? null
            : existing.durationMinutes ?? null,
        ),
        durationMinutes: Object.prototype.hasOwnProperty.call(updates, "durationMinutes")
          ? updates.durationMinutes ?? null
          : existing.durationMinutes ?? null,
      }
    : {
        ...updates,
        ...(existing.scheduledStartAt && Object.prototype.hasOwnProperty.call(updates, "durationMinutes")
          ? buildCanonicalScheduleUpdates(existing.scheduledStartAt, updates.durationMinutes ?? existing.durationMinutes ?? 60)
          : {}),
      };

  const writeMode = decideCalendarWriteMode({
    calendarLocalFirstWriteEnabled: isCalendarLocalFirstWriteEnabled(),
    hasRemoteId: Boolean(existing.remoteId),
    hasPendingOps: localDb.getPendingOpsForEntity("task", taskId).length > 0,
    isSyncPaused: isSyncPaused(),
    blockedReason: getSyncControlState().blockedReason,
  });

  if (writeMode === "local-first") {
    updateTaskOfflineFirst(taskId, normalizedUpdates);
    return (
      localDb.getTaskById(taskId) ?? {
        ...existing,
        ...normalizedUpdates,
      }
    );
  }

  if (!existing.remoteId) {
    updateTaskOfflineFirst(taskId, normalizedUpdates);
    return (
      localDb.getTaskById(taskId) ?? {
        ...existing,
        ...normalizedUpdates,
      }
    );
  }

  const payload: api.UpdateTaskPayload = {};
  if (Object.prototype.hasOwnProperty.call(normalizedUpdates, "dueDate") && normalizedUpdates.dueDate !== undefined) {
    payload.dueDate = normalizedUpdates.dueDate ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(normalizedUpdates, "durationMinutes") && normalizedUpdates.durationMinutes !== undefined) {
    payload.durationMinutes = normalizedUpdates.durationMinutes ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(normalizedUpdates, "deadlineAt")) {
    payload.deadlineAt = normalizedUpdates.deadlineAt ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(normalizedUpdates, "scheduledStartAt")) {
    payload.scheduledStartAt = normalizedUpdates.scheduledStartAt ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(normalizedUpdates, "scheduledEndAt")) {
    payload.scheduledEndAt = normalizedUpdates.scheduledEndAt ?? null;
  }
  const updatedTask = await api.updateTask(existing.remoteId, payload);
  localDb.replaceTaskWithServerState(taskId, {
    ...updatedTask,
    remoteId: updatedTask.remoteId ?? existing.remoteId,
  });
  emitDataChanged();
  devLog("calendarRepository", "remote_first.schedule_update", {
    taskId,
    remoteId: existing.remoteId,
  });
  return localDb.getTaskById(taskId) ?? updatedTask;
}

export async function moveTaskToCalendarTarget(
  task: Pick<TaskRecord, "id" | "dueDate" | "scheduledStartAt" | "durationMinutes">,
  targetKey: string,
  selectedDateKey: string,
): Promise<TaskRecord> {
  const dueDate = buildDueDateForCalendarDrop(task.scheduledStartAt ?? task.dueDate ?? null, targetKey, selectedDateKey);
  return updateCalendarTaskSchedule(task.id, buildCanonicalScheduleUpdates(dueDate, task.durationMinutes ?? 60));
}

export async function resizeCalendarTaskDuration(
  taskId: string,
  durationMinutes: number,
): Promise<TaskRecord> {
  return updateCalendarTaskSchedule(taskId, { durationMinutes });
}

export async function updateTaskScheduleFromPicker(
  taskId: string,
  value: CalendarScheduleValue,
): Promise<TaskRecord> {
  return updateCalendarTaskSchedule(taskId, buildTaskScheduleUpdatesFromPicker(value));
}
