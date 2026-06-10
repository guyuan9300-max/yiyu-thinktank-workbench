import type { CurrentFocus, TaskRecord } from "./types";
import { getTaskCalendarDateKey } from "./task-time";

export interface FocusTaskStats {
  matchedCount: number;
  scheduledCount: number;
  unscheduledCount: number;
  doneCount: number;
}

export function isLockedFocus(currentFocus: CurrentFocus): boolean {
  return currentFocus.lockMode === "client" || currentFocus.lockMode === "client_event_line";
}

export function matchesTaskAgainstFocus(task: TaskRecord, currentFocus: CurrentFocus): boolean {
  if (currentFocus.eventLineId) {
    return task.eventLineId === currentFocus.eventLineId;
  }
  if (currentFocus.clientId) {
    return task.clientId === currentFocus.clientId;
  }
  return false;
}

export function filterTasksByFocus(tasks: readonly TaskRecord[], currentFocus: CurrentFocus): TaskRecord[] {
  if (!isLockedFocus(currentFocus)) {
    return [...tasks];
  }
  return tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus));
}

export function buildFocusMatchedTaskIds(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): ReadonlySet<string> {
  return new Set(
    tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus)).map((task) => task.id),
  );
}

export function sortTasksByFocusPriority(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): TaskRecord[] {
  return tasks
    .map((task, index) => ({
      task,
      index,
      matched: matchesTaskAgainstFocus(task, currentFocus),
    }))
    .sort((left, right) => {
      if (left.matched !== right.matched) {
        return left.matched ? -1 : 1;
      }
      return left.index - right.index;
    })
    .map((entry) => entry.task);
}

export function buildFocusTaskStats(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): FocusTaskStats {
  const matchedTasks = tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus));
  return {
    matchedCount: matchedTasks.length,
    scheduledCount: matchedTasks.filter((task) => Boolean(getTaskCalendarDateKey(task))).length,
    unscheduledCount: matchedTasks.filter((task) => !getTaskCalendarDateKey(task)).length,
    doneCount: matchedTasks.filter((task) => task.progressStatus === "done").length,
  };
}
