import * as localDb from "./local-db";
import { isTaskLocalFirstReadEnabled } from "./runtime-flags";
import { getTaskCalendarDateKey } from "./task-time";
import type { TaskBoardResponse, TaskRecord } from "./types";

function compareDateValue(left: string | null | undefined, right: string | null | undefined): number {
  if (left && right) {
    return left.localeCompare(right);
  }
  if (left) {
    return -1;
  }
  if (right) {
    return 1;
  }
  return 0;
}

export function compareTasksForBoard(left: TaskRecord, right: TaskRecord): number {
  return (
    compareDateValue(getTaskCalendarDateKey(left), getTaskCalendarDateKey(right)) ||
    compareDateValue(left.updatedAt, right.updatedAt) ||
    compareDateValue(left.createdAt, right.createdAt) ||
    left.id.localeCompare(right.id)
  );
}

export function getTaskBoardSnapshot(): TaskBoardResponse {
  const syncedOnly = !isTaskLocalFirstReadEnabled();
  const board = localDb.getLocalTaskBoard({ syncedOnly });
  return {
    ...board,
    tasks: [...board.tasks].sort(compareTasksForBoard),
  };
}

export function getTaskSnapshot(taskId: string): TaskRecord | null {
  return localDb.getTaskById(taskId);
}
