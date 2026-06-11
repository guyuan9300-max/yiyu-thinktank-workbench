export interface CalendarWriteModeInput {
  calendarLocalFirstWriteEnabled: boolean;
  hasRemoteId: boolean;
  hasPendingOps: boolean;
  isSyncPaused: boolean;
  blockedReason: string | null;
}

export interface CalendarScheduleValue {
  date: string | null;
  time: string | null;
  durationMinutes: number | null;
}

export interface CalendarScheduleUpdates {
  dueDate: string | null;
  deadlineAt?: string | null;
  scheduledStartAt?: string | null;
  scheduledEndAt?: string | null;
  durationMinutes?: number | null;
}

export function decideCalendarWriteMode(input: CalendarWriteModeInput): "local-first" | "remote-first" {
  if (input.calendarLocalFirstWriteEnabled) {
    return "local-first";
  }
  if (!input.hasRemoteId) {
    return "local-first";
  }
  if (input.hasPendingOps) {
    return "local-first";
  }
  if (input.isSyncPaused || Boolean(input.blockedReason)) {
    return "local-first";
  }
  return "remote-first";
}

export function buildDueDateForCalendarDrop(
  currentDueDate: string | null | undefined,
  targetKey: string,
  selectedDateKey: string,
): string {
  if (targetKey.startsWith("hour:")) {
    const hour = Number.parseInt(targetKey.slice(5), 10);
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
      throw new Error(`Invalid calendar hour target: ${targetKey}`);
    }
    const timeStr = `${String(hour).padStart(2, "0")}:00`;
    return `${selectedDateKey}T${timeStr}`;
  }

  const existingTime = currentDueDate?.includes("T") ? currentDueDate.slice(10) : "";
  return `${targetKey}${existingTime}`;
}

function hasExplicitTime(value: string | null | undefined): boolean {
  return Boolean(value && /^\d{4}-\d{2}-\d{2}[T\s]\d{1,2}:\d{2}/.test(value));
}

function addMinutesToTaskDateTime(value: string, minutes: number): string | null {
  const match = value.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{1,2}):(\d{2})/);
  if (!match) return null;
  const start = new Date(Number(match[1].slice(0, 4)), Number(match[1].slice(5, 7)) - 1, Number(match[1].slice(8, 10)), Number(match[2]), Number(match[3]));
  if (Number.isNaN(start.getTime())) return null;
  const end = new Date(start.getTime() + Math.max(15, minutes) * 60_000);
  return `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, "0")}-${String(end.getDate()).padStart(2, "0")}T${String(end.getHours()).padStart(2, "0")}:${String(end.getMinutes()).padStart(2, "0")}`;
}

export function buildCanonicalScheduleUpdates(
  dueDate: string | null,
  durationMinutes?: number | null,
): CalendarScheduleUpdates {
  const updates: CalendarScheduleUpdates = { dueDate };
  const hasDuration = durationMinutes !== undefined;
  if (hasDuration) {
    updates.durationMinutes = durationMinutes;
  }
  if (!dueDate) {
    updates.deadlineAt = null;
    updates.scheduledStartAt = null;
    updates.scheduledEndAt = null;
    return updates;
  }
  if (hasExplicitTime(dueDate)) {
    updates.deadlineAt = null;
    updates.scheduledStartAt = dueDate;
    updates.scheduledEndAt = typeof durationMinutes === "number"
      ? addMinutesToTaskDateTime(dueDate, durationMinutes)
      : undefined;
    return updates;
  }
  updates.deadlineAt = dueDate;
  updates.scheduledStartAt = null;
  updates.scheduledEndAt = null;
  return updates;
}

export function buildTaskScheduleUpdatesFromPicker(
  value: CalendarScheduleValue,
): CalendarScheduleUpdates {
  let dueDate: string | null = null;
  if (value.date) {
    dueDate = value.time ? `${value.date}T${value.time}` : value.date;
  }
  return buildCanonicalScheduleUpdates(
    dueDate,
    value.durationMinutes === null ? undefined : value.durationMinutes,
  );
}

// ─── 跨天起止（picker"时间段"tab 用） ───────────────
//
// 真相源是 scheduledStartAt / scheduledEndAt 两个完整时间戳；end 可落在不同日期。
// durationMinutes 由 (end - start) 推导，跨天时可 >1440。
// 全天（无开始时间）v1 仅单日，落 deadlineAt（忽略 endDate）。

export interface CalendarRangeValue {
  /** 开始日 "YYYY-MM-DD"；为 null 表示清除排期 */
  startDate: string | null;
  /** 开始时间 "HH:mm"；为 null 表示全天 */
  startTime: string | null;
  /** 结束日 "YYYY-MM-DD"；缺省同开始日 */
  endDate: string | null;
  /** 结束时间 "HH:mm"；为 null 表示不设结束 */
  endTime: string | null;
}

function parseLocalDateTime(value: string): Date | null {
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{1,2}):(\d{2})/);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]));
  return Number.isNaN(d.getTime()) ? null : d;
}

function diffMinutes(startISO: string, endISO: string): number | null {
  const start = parseLocalDateTime(startISO);
  const end = parseLocalDateTime(endISO);
  if (!start || !end) return null;
  return Math.round((end.getTime() - start.getTime()) / 60_000);
}

export function buildScheduleFromStartEnd(value: CalendarRangeValue): CalendarScheduleUpdates {
  const { startDate, startTime, endDate, endTime } = value;

  // 无开始日 → 清空全部排期
  if (!startDate) {
    return { dueDate: null, deadlineAt: null, scheduledStartAt: null, scheduledEndAt: null, durationMinutes: null };
  }

  // 全天（无开始时间）：v1 仅单日，落 deadlineAt，忽略 endDate
  if (!startTime) {
    return { dueDate: startDate, deadlineAt: startDate, scheduledStartAt: null, scheduledEndAt: null, durationMinutes: null };
  }

  // 带时间
  const scheduledStartAt = `${startDate}T${startTime}`;

  // 无结束时间 → 只有开始时刻，不设 end
  if (!endTime) {
    return { dueDate: scheduledStartAt, deadlineAt: null, scheduledStartAt, scheduledEndAt: null, durationMinutes: null };
  }

  const scheduledEndAt = `${endDate ?? startDate}T${endTime}`;
  const durationMinutes = diffMinutes(scheduledStartAt, scheduledEndAt);

  // 结束 <= 开始 视为无效，丢弃 end 防脏数据（picker 已校验，这里兜底）
  if (durationMinutes == null || durationMinutes <= 0) {
    return { dueDate: scheduledStartAt, deadlineAt: null, scheduledStartAt, scheduledEndAt: null, durationMinutes: null };
  }

  return { dueDate: scheduledStartAt, deadlineAt: null, scheduledStartAt, scheduledEndAt, durationMinutes };
}
