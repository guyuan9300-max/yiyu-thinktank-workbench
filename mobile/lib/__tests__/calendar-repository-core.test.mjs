import test from "node:test";
import assert from "node:assert/strict";

import {
  buildDueDateForCalendarDrop,
  buildScheduleFromStartEnd,
  buildTaskScheduleUpdatesFromPicker,
  decideCalendarWriteMode,
} from "../../.mobile-core-tests/dist/lib/calendar-repository-core.js";

test("date drop keeps existing time component when moving between days", () => {
  assert.equal(
    buildDueDateForCalendarDrop("2026-04-18T12:30", "2026-04-20", "2026-04-18"),
    "2026-04-20T12:30",
  );
});

test("hour drop rewrites the selected date with the dropped hour", () => {
  assert.equal(
    buildDueDateForCalendarDrop("2026-04-18T12:30", "hour:9", "2026-04-21"),
    "2026-04-21T09:00",
  );
});

test("hour drop supports the last real hour of the day", () => {
  assert.equal(
    buildDueDateForCalendarDrop("2026-04-18T12:30", "hour:23", "2026-04-21"),
    "2026-04-21T23:00",
  );
});

test("hour drop rejects the 24:00 boundary instead of producing an invalid dueDate", () => {
  assert.throws(
    () => buildDueDateForCalendarDrop("2026-04-18T12:30", "hour:24", "2026-04-21"),
    /Invalid calendar hour/,
  );
});

test("picker updates build a dueDate and preserve explicit duration", () => {
  assert.deepEqual(
    buildTaskScheduleUpdatesFromPicker({
      date: "2026-04-22",
      time: "14:45",
      durationMinutes: 90,
    }),
    {
      dueDate: "2026-04-22T14:45",
      durationMinutes: 90,
      deadlineAt: null,
      scheduledStartAt: "2026-04-22T14:45",
      scheduledEndAt: "2026-04-22T16:15",
    },
  );
});

test("picker date-only updates build a canonical deadline reminder", () => {
  assert.deepEqual(
    buildTaskScheduleUpdatesFromPicker({
      date: "2026-04-22",
      time: null,
      durationMinutes: null,
    }),
    {
      dueDate: "2026-04-22",
      deadlineAt: "2026-04-22",
      scheduledStartAt: null,
      scheduledEndAt: null,
    },
  );
});

test("picker clear builds an explicit dueDate null update", () => {
  assert.deepEqual(
    buildTaskScheduleUpdatesFromPicker({
      date: null,
      time: null,
      durationMinutes: null,
    }),
    {
      dueDate: null,
      deadlineAt: null,
      scheduledStartAt: null,
      scheduledEndAt: null,
    },
  );
});

test("range build: same-day timed range sets start/end and duration", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({
      startDate: "2026-06-01",
      startTime: "22:00",
      endDate: "2026-06-01",
      endTime: "23:30",
    }),
    {
      dueDate: "2026-06-01T22:00",
      deadlineAt: null,
      scheduledStartAt: "2026-06-01T22:00",
      scheduledEndAt: "2026-06-01T23:30",
      durationMinutes: 90,
    },
  );
});

test("range build: cross-day timed range spans into next day, duration may exceed 1440", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({
      startDate: "2026-06-01",
      startTime: "22:00",
      endDate: "2026-06-02",
      endTime: "02:00",
    }),
    {
      dueDate: "2026-06-01T22:00",
      deadlineAt: null,
      scheduledStartAt: "2026-06-01T22:00",
      scheduledEndAt: "2026-06-02T02:00",
      durationMinutes: 240,
    },
  );
});

test("range build: all-day (no start time) is single-day deadline, endDate ignored in v1", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({
      startDate: "2026-06-01",
      startTime: null,
      endDate: "2026-06-03",
      endTime: null,
    }),
    {
      dueDate: "2026-06-01",
      deadlineAt: "2026-06-01",
      scheduledStartAt: null,
      scheduledEndAt: null,
      durationMinutes: null,
    },
  );
});

test("range build: timed start without end time keeps start only, no end", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({
      startDate: "2026-06-01",
      startTime: "09:00",
      endDate: null,
      endTime: null,
    }),
    {
      dueDate: "2026-06-01T09:00",
      deadlineAt: null,
      scheduledStartAt: "2026-06-01T09:00",
      scheduledEndAt: null,
      durationMinutes: null,
    },
  );
});

test("range build: no start date clears all schedule fields", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({ startDate: null, startTime: null, endDate: null, endTime: null }),
    { dueDate: null, deadlineAt: null, scheduledStartAt: null, scheduledEndAt: null, durationMinutes: null },
  );
});

test("range build: end <= start is rejected, keeps start and drops invalid end", () => {
  assert.deepEqual(
    buildScheduleFromStartEnd({
      startDate: "2026-06-01",
      startTime: "10:00",
      endDate: "2026-06-01",
      endTime: "09:00",
    }),
    {
      dueDate: "2026-06-01T10:00",
      deadlineAt: null,
      scheduledStartAt: "2026-06-01T10:00",
      scheduledEndAt: null,
      durationMinutes: null,
    },
  );
});

test("calendar repository only uses remote-first fallback when local-first is disabled and task is clean", () => {
  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: true,
      hasRemoteId: true,
      hasPendingOps: false,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "local-first",
  );

  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: false,
      hasRemoteId: true,
      hasPendingOps: false,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "remote-first",
  );

  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: false,
      hasRemoteId: true,
      hasPendingOps: true,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "local-first",
  );
});
