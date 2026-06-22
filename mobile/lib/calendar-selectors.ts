import type { TaskRecord } from "./types";
import {
  getTaskCalendarDayKeys,
  isTaskScheduled,
} from "./task-time";

export interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

export function groupTasksByDate(tasks: readonly TaskRecord[]): Map<string, TaskRecord[]> {
  const grouped = new Map<string, TaskRecord[]>();
  for (const task of tasks) {
    // 跨天任务进入它覆盖的每一个自然日桶（开始日..结束日）
    for (const dateKey of getTaskCalendarDayKeys(task)) {
      const existing = grouped.get(dateKey);
      if (existing) {
        existing.push(task);
        continue;
      }
      grouped.set(dateKey, [task]);
    }
  }
  return grouped;
}

export function getTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return grouped.get(dateKey) ?? [];
}

export function getScheduledTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return getTasksForDate(grouped, dateKey).filter((task) => isTaskScheduled(task));
}

export function getAllDayTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return getTasksForDate(grouped, dateKey).filter((task) => !isTaskScheduled(task));
}

export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export function getFirstDayOfWeek(year: number, month: number): number {
  return (new Date(year, month, 1).getDay() + 6) % 7;
}

export function buildMonthCalendarDays(year: number, month: number): readonly CalendarDay[] {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const result: CalendarDay[] = [];

  for (let index = 0; index < firstDay; index += 1) {
    const previousMonth = month === 0 ? 11 : month - 1;
    const previousYear = month === 0 ? year - 1 : year;
    const previousMonthDays = getDaysInMonth(previousYear, previousMonth);
    const day = previousMonthDays - firstDay + 1 + index;
    result.push({
      day,
      dateKey: `${previousYear}-${String(previousMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      isCurrentMonth: false,
    });
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    result.push({
      day,
      dateKey: `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      isCurrentMonth: true,
    });
  }

  const remainder = result.length % 7;
  if (remainder > 0) {
    const nextMonth = month === 11 ? 0 : month + 1;
    const nextYear = month === 11 ? year + 1 : year;
    for (let day = 1; day <= 7 - remainder; day += 1) {
      result.push({
        day,
        dateKey: `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        isCurrentMonth: false,
      });
    }
  }

  return result;
}
