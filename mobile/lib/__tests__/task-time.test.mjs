import test from "node:test";
import assert from "node:assert/strict";

import {
  formatTaskDisplayDate,
  getTaskCalendarDateKey,
  getTaskCalendarDayKeys,
  getTaskDeadlineDateKey,
  getTaskScheduleDateTime,
  getTaskScheduleTimeLabel,
  isTaskOverdue,
  isTaskScheduled,
  isTaskInWeek,
} from "../../.mobile-core-tests/dist/lib/task-time.js";

test("calendar day keys: same-day timed task spans a single day", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ scheduledStartAt: "2026-06-01T09:00", durationMinutes: 90 }),
    ["2026-06-01"],
  );
});

test("calendar day keys: cross-day task spans start..end days", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ scheduledStartAt: "2026-06-01T22:00", durationMinutes: 240 }),
    ["2026-06-01", "2026-06-02"],
  );
});

test("calendar day keys: multi-day task includes every middle day", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ scheduledStartAt: "2026-06-01T10:00", durationMinutes: 60 * 24 * 2 + 120 }),
    ["2026-06-01", "2026-06-02", "2026-06-03"],
  );
});

test("calendar day keys: end exactly at midnight does not add the next day", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ scheduledStartAt: "2026-06-01T22:00", durationMinutes: 120 }),
    ["2026-06-01"],
  );
});

test("calendar day keys: timed task without duration is single day", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ scheduledStartAt: "2026-06-01T09:00", durationMinutes: null }),
    ["2026-06-01"],
  );
});

test("calendar day keys: unscheduled deadline task falls back to its single calendar day", () => {
  assert.deepEqual(
    getTaskCalendarDayKeys({ deadlineAt: "2026-06-05", dueDate: "2026-06-05" }),
    ["2026-06-05"],
  );
});

test("canonical scheduled time drives calendar placement before legacy dueDate", () => {
  const task = {
    id: "task-scheduled",
    title: "排程任务",
    dueDate: "2026-04-20",
    deadlineAt: "2026-04-30",
    scheduledStartAt: "2026-04-22T14:30",
    scheduledEndAt: "2026-04-22T15:30",
    durationMinutes: 60,
    progressStatus: "todo",
  };

  assert.equal(getTaskCalendarDateKey(task), "2026-04-22");
  assert.equal(getTaskScheduleDateTime(task)?.dateKey, "2026-04-22");
  assert.equal(getTaskScheduleTimeLabel(task), "14:30");
  assert.equal(isTaskScheduled(task), true);
});

test("legacy date-only dueDate is not a deadline when canonical schedule exists", () => {
  const task = {
    id: "task-scheduled-no-deadline",
    title: "只有计划时间",
    dueDate: "2026-04-20",
    deadlineAt: null,
    scheduledStartAt: "2026-04-22T14:30",
    scheduledEndAt: "2026-04-22T15:30",
    progressStatus: "todo",
  };

  assert.equal(getTaskCalendarDateKey(task), "2026-04-22");
  assert.equal(getTaskDeadlineDateKey(task), null);
  assert.equal(isTaskOverdue(task, new Date("2026-05-03T10:00:00")), false);
});

test("deadline-only task is not scheduled but can be overdue", () => {
  const task = {
    id: "task-deadline",
    title: "截止任务",
    deadlineAt: "2026-04-20",
    dueDate: "2026-04-20",
    progressStatus: "todo",
  };

  assert.equal(getTaskCalendarDateKey(task), "2026-04-20");
  assert.equal(getTaskDeadlineDateKey(task), "2026-04-20");
  assert.equal(isTaskScheduled(task), false);
  assert.equal(isTaskOverdue(task, new Date("2026-04-21T10:00:00")), true);
  assert.equal(formatTaskDisplayDate(task, new Date("2026-04-21T10:00:00")), "4月20日");
});

test("done tasks are never overdue and week membership uses execution date", () => {
  const task = {
    id: "task-done",
    title: "完成任务",
    deadlineAt: "2026-04-13",
    completedAt: "2026-04-14T09:00:00",
    progressStatus: "done",
  };

  assert.equal(isTaskOverdue(task, new Date("2026-04-17T10:00:00")), false);
  assert.equal(isTaskInWeek(task, "2026-04-13"), true);
});
