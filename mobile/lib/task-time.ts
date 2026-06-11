import { formatLocalDateKey, getLocalWeekRangeKeys, parseLocalDateKey } from "./date";
import type { TaskRecord } from "./types";

export interface TaskScheduleDateTime {
  value: Date;
  dateKey: string;
  timeLabel: string;
}

function splitTaskDateTime(value: string | null | undefined): { date: string; time: string } {
  const text = (value ?? "").trim();
  if (!text) return { date: "", time: "" };
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{1,2}):(\d{2}))?/);
  if (match) {
    return {
      date: match[1],
      time: match[2] && match[3] ? `${String(Number(match[2])).padStart(2, "0")}:${match[3]}` : "",
    };
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return { date: "", time: "" };
  return {
    date: formatLocalDateKey(parsed),
    time: `${String(parsed.getHours()).padStart(2, "0")}:${String(parsed.getMinutes()).padStart(2, "0")}`,
  };
}

export function hasExplicitTaskTime(value: string | null | undefined): boolean {
  return Boolean(splitTaskDateTime(value).time);
}

function parseTaskDate(value: string | null | undefined): Date | null {
  const { date } = splitTaskDateTime(value);
  if (!date) return null;
  const parsed = parseLocalDateKey(date);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function parseTaskDateTime(value: string | null | undefined): TaskScheduleDateTime | null {
  const { date, time } = splitTaskDateTime(value);
  if (!date) return null;
  const base = parseLocalDateKey(date);
  if (Number.isNaN(base.getTime())) return null;
  const [hoursText, minutesText] = (time || "00:00").split(":");
  const hours = Number(hoursText);
  const minutes = Number(minutesText);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null;
  const valueDate = new Date(base.getFullYear(), base.getMonth(), base.getDate(), hours, minutes);
  return {
    value: valueDate,
    dateKey: formatLocalDateKey(valueDate),
    timeLabel: `${String(valueDate.getHours()).padStart(2, "0")}:${String(valueDate.getMinutes()).padStart(2, "0")}`,
  };
}

function legacyDateOnlyDeadline(task: Pick<TaskRecord, "dueDate" | "scheduledStartAt" | "scheduledEndAt">): Date | null {
  if (!task.dueDate || hasExplicitTaskTime(task.dueDate)) return null;
  if (task.scheduledStartAt || task.scheduledEndAt) return null;
  return parseTaskDate(task.dueDate);
}

function legacyScheduleDateTime(task: Pick<TaskRecord, "dueDate">): TaskScheduleDateTime | null {
  if (!task.dueDate || !hasExplicitTaskTime(task.dueDate)) return null;
  return parseTaskDateTime(task.dueDate);
}

export function getTaskScheduleDateTime(
  task: Pick<TaskRecord, "scheduledStartAt" | "dueDate">,
): TaskScheduleDateTime | null {
  return parseTaskDateTime(task.scheduledStartAt) || legacyScheduleDateTime(task);
}

/** 计划结束时刻（仅"带时间"的任务有；跨天时与开始不在同一天）。 */
export function getTaskScheduleEndDateTime(
  task: Pick<TaskRecord, "scheduledEndAt">,
): TaskScheduleDateTime | null {
  return parseTaskDateTime(task.scheduledEndAt);
}

/**
 * 计划结束的真实时刻 = 开始 + durationMinutes。
 * 注意：用 durationMinutes 推导而非 scheduledEndAt——后者未必经云端往返存活，duration 才是可靠载体。
 */
export function getTaskScheduleEndValue(
  task: Pick<TaskRecord, "scheduledStartAt" | "dueDate" | "durationMinutes">,
): Date | null {
  const start = getTaskScheduleDateTime(task)?.value;
  if (!start) return null;
  const dur = task.durationMinutes ?? 0;
  return dur > 0 ? new Date(start.getTime() + dur * 60_000) : start;
}

/**
 * 任务在日历上应出现的所有自然日 key（升序）。
 * 带时间的跨天任务 → [开始日 .. 结束日]；其余 → 单日（计划日或截止日）。
 * 结束恰好落在某日 00:00 时不计入该日（无可见时段）。
 */
export function getTaskCalendarDayKeys(
  task: Pick<TaskRecord, "scheduledStartAt" | "scheduledEndAt" | "deadlineAt" | "dueDate" | "durationMinutes">,
): string[] {
  const start = getTaskScheduleDateTime(task)?.value;
  if (start) {
    const end = getTaskScheduleEndValue(task);
    const endMs = end ? end.getTime() : start.getTime();
    const keys: string[] = [];
    let cur = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    do {
      keys.push(formatLocalDateKey(cur));
      cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
    } while (cur.getTime() < endMs);
    return keys;
  }
  const dateKey = getTaskCalendarDateKey(task);
  return dateKey ? [dateKey] : [];
}

export function getTaskDeadlineDate(
  task: Pick<TaskRecord, "deadlineAt" | "dueDate" | "scheduledStartAt" | "scheduledEndAt">,
): Date | null {
  return parseTaskDate(task.deadlineAt) || legacyDateOnlyDeadline(task);
}

export function getTaskDeadlineDateKey(task: Pick<TaskRecord, "deadlineAt" | "dueDate" | "scheduledStartAt" | "scheduledEndAt">): string | null {
  const date = getTaskDeadlineDate(task);
  return date ? formatLocalDateKey(date) : null;
}

export function getTaskCalendarDateKey(
  task: Pick<TaskRecord, "scheduledStartAt" | "deadlineAt" | "dueDate">,
): string | null {
  const scheduled = getTaskScheduleDateTime(task);
  if (scheduled) return scheduled.dateKey;
  return getTaskDeadlineDateKey(task);
}

export function getTaskScheduleTimeLabel(task: Pick<TaskRecord, "scheduledStartAt" | "dueDate">): string | null {
  return getTaskScheduleDateTime(task)?.timeLabel ?? null;
}

export function isTaskScheduled(task: Pick<TaskRecord, "scheduledStartAt" | "dueDate">): boolean {
  return Boolean(getTaskScheduleDateTime(task));
}

export function isTaskDone(task: Pick<TaskRecord, "progressStatus">): boolean {
  return task.progressStatus === "done";
}

export function isTaskOverdue(
  task: Pick<TaskRecord, "progressStatus" | "deadlineAt" | "dueDate" | "scheduledStartAt" | "scheduledEndAt">,
  now: Date = new Date(),
): boolean {
  if (isTaskDone(task)) return false;
  const deadline = getTaskDeadlineDate(task);
  if (!deadline) return false;
  return formatLocalDateKey(deadline) < formatLocalDateKey(now);
}

export function getTaskOverdueDays(
  task: Pick<TaskRecord, "progressStatus" | "deadlineAt" | "dueDate" | "scheduledStartAt" | "scheduledEndAt">,
  now: Date = new Date(),
): number {
  if (!isTaskOverdue(task, now)) return 0;
  const deadline = getTaskDeadlineDate(task);
  if (!deadline) return 0;
  const today = parseLocalDateKey(formatLocalDateKey(now));
  const dueDay = parseLocalDateKey(formatLocalDateKey(deadline));
  return Math.ceil((today.getTime() - dueDay.getTime()) / 86_400_000);
}

export function isTaskInWeek(
  task: Pick<TaskRecord, "scheduledStartAt" | "deadlineAt" | "dueDate">,
  weekAnchorDate: string,
): boolean {
  const dateKey = getTaskCalendarDateKey(task);
  if (!dateKey) return false;
  const { startKey, endKey } = getLocalWeekRangeKeys(parseLocalDateKey(weekAnchorDate));
  return dateKey >= startKey && dateKey <= endKey;
}

export function isTaskToday(
  task: Pick<TaskRecord, "scheduledStartAt" | "deadlineAt" | "dueDate">,
  todayKey = formatLocalDateKey(new Date()),
): boolean {
  return getTaskCalendarDateKey(task) === todayKey;
}

export function formatTaskDisplayDate(
  task: Pick<TaskRecord, "scheduledStartAt" | "scheduledEndAt" | "deadlineAt" | "dueDate">,
  now: Date = new Date(),
): string {
  const scheduled = getTaskScheduleDateTime(task);
  const date = scheduled?.value || getTaskDeadlineDate(task);
  if (!date) return "未设定";
  const dateKey = formatLocalDateKey(date);
  const todayKey = formatLocalDateKey(now);
  if (dateKey === todayKey && scheduled) return scheduled.timeLabel;
  if (dateKey === todayKey) return "今天";
  const base = `${date.getMonth() + 1}月${date.getDate()}日`;
  return scheduled ? `${base} ${scheduled.timeLabel}` : base;
}
