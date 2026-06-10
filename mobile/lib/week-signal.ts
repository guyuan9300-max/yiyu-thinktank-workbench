import { formatLocalDateKey, getLocalWeekRangeKeys, parseLocalDateKey } from "./date";
import {
  getTaskCalendarDateKey,
  getTaskDeadlineDateKey,
} from "./task-time";
import type {
  ClientWorkspaceLiteSnapshot,
  EventLineRecord,
  TaskRecord,
  WeekSignalFactSummary,
  WeekSignalSnapshot,
} from "./types";

/**
 * Normalize a task `dueDate` (which may be UTC ISO with `Z`, wall-clock ISO without
 * timezone, or a bare `YYYY-MM-DD`) into a local-calendar date key.
 *
 * Old code did `dueDate.slice(0, 10)`, which for UTC ISO strings returned the UTC
 * date — that mismatches the local week boundaries used everywhere else and made
 * tasks near midnight slip into the wrong week (Bug 1).
 */
function toLocalDateKey(value: string | null | undefined): string | null {
  if (!value) return null;
  // Already a date key like "2026-04-14".
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  // Wall-clock ISO without timezone (e.g. "2026-04-14T12:30") — date portion is
  // already in the local calendar, just slice it off.
  const wallClockMatch = value.match(/^(\d{4}-\d{2}-\d{2})T[\d:.]+$/);
  if (wallClockMatch) {
    return wallClockMatch[1];
  }
  // ISO with Z or explicit offset — parse and convert to the local date.
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }
  return formatLocalDateKey(parsed);
}

function isTaskInWeek(task: TaskRecord, weekAnchorDate: string): boolean {
  const taskDateKey = getTaskCalendarDateKey(task) || toLocalDateKey(task.dueDate);
  if (!taskDateKey) {
    return false;
  }
  const { startKey, endKey } = getLocalWeekRangeKeys(parseLocalDateKey(weekAnchorDate));
  return taskDateKey >= startKey && taskDateKey <= endKey;
}

export function buildWeekSignalFacts(
  tasks: readonly TaskRecord[],
  weekAnchorDate: string,
  now: Date = new Date(),
): WeekSignalFactSummary {
  const weekTasks = tasks.filter((task) => isTaskInWeek(task, weekAnchorDate));
  const todayKey = formatLocalDateKey(now);

  // Counters that describe "this week" — must be scoped to weekTasks (Bug 2).
  const totalCount = weekTasks.length;
  const completedCount = weekTasks.filter((task) => task.progressStatus === "done").length;
  const rescheduledCount = weekTasks.filter((task) => {
    if (!task.updatedAt || !task.createdAt) {
      return false;
    }
    return task.updatedAt !== task.createdAt;
  }).length;
  const awaitingReviewCount = weekTasks.filter(
    (task) => task.progressStatus === "done" && !task.completionNote,
  ).length;

  // Counters that describe "right now" across the whole inbox — kept global on
  // purpose (an unscheduled task is unscheduled regardless of week). They now
  // exclude finished tasks, and `overdue` is measured against today rather than
  // the week anchor so a task due Monday this week shows as overdue on Friday
  // (Bug 2 follow-on).
  const unscheduledCount = tasks.filter(
    (task) => !getTaskCalendarDateKey(task) && task.progressStatus !== "done",
  ).length;
  const overdueCount = tasks.filter((task) => {
    if (task.progressStatus === "done") return false;
    const dueKey = getTaskDeadlineDateKey(task) || toLocalDateKey(task.dueDate);
    if (!dueKey) return false;
    return dueKey < todayKey;
  }).length;

  return {
    totalCount,
    completedCount,
    rescheduledCount,
    unscheduledCount,
    overdueCount,
    awaitingReviewCount,
  };
}

export function buildWeekSignalSnapshot(params: {
  readonly tasks: readonly TaskRecord[];
  readonly weekAnchorDate: string;
  readonly workspaceLite?: ClientWorkspaceLiteSnapshot | null;
  readonly eventLine?: EventLineRecord | null;
  readonly allowJudgmentOverlay?: boolean;
  readonly now?: Date;
}): WeekSignalSnapshot {
  const facts = buildWeekSignalFacts(params.tasks, params.weekAnchorDate, params.now);
  if (!params.allowJudgmentOverlay) {
    return {
      facts,
      pendingJudgments: [],
      riskSignals: [],
      suggestedActions: [],
    };
  }
  const pending = params.workspaceLite?.boundaryCards
    .filter((card) => card.kind === "pending" && !card.isEmpty)
    .map((card) => card.summary)
    .filter(Boolean) ?? [];
  const risks = params.workspaceLite?.boundaryCards
    .filter((card) => card.kind === "risk" && !card.isEmpty)
    .map((card) => card.summary)
    .filter(Boolean) ?? [];
  const actions = [
    ...(params.workspaceLite?.nextActions ?? []).slice(0, 3),
    ...(params.eventLine?.nextStep ? [params.eventLine.nextStep] : []),
  ].filter(Boolean) as string[];

  return {
    facts,
    pendingJudgments: pending.slice(0, 3),
    riskSignals: risks.slice(0, 3),
    suggestedActions: actions.slice(0, 3),
  };
}
