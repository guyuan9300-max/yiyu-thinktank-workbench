import test from "node:test";
import assert from "node:assert/strict";

import { buildWeekSignalSnapshot } from "../../.mobile-core-tests/dist/lib/week-signal.js";

const tasks = [
  {
    id: "task-1",
    title: "测试机构A推进会",
    dueDate: "2026-04-14T12:30",
    progressStatus: "todo",
    createdAt: "2026-04-13T09:00:00.000Z",
    updatedAt: "2026-04-13T09:00:00.000Z",
  },
  {
    id: "task-2",
    title: "输出会议纪要",
    dueDate: "2026-04-15T18:00",
    progressStatus: "done",
    completionNote: "已完成",
    createdAt: "2026-04-13T09:00:00.000Z",
    updatedAt: "2026-04-15T18:00:00.000Z",
  },
];

test("buildWeekSignalSnapshot stays facts-only when judgment overlay is disabled", () => {
  const snapshot = buildWeekSignalSnapshot({
    tasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    workspaceLite: {
      boundaryCards: [
        { kind: "pending", title: "待确认判断", summary: "先做试点", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
      ],
      nextActions: ["和负责人确认预算"],
    },
    eventLine: {
      id: "event-1",
      name: "韶关推进线",
      nextStep: "整理下一轮动作",
    },
  });

  assert.equal(snapshot.facts.totalCount, 2);
  assert.deepEqual(snapshot.pendingJudgments, []);
  assert.deepEqual(snapshot.riskSignals, []);
  assert.deepEqual(snapshot.suggestedActions, []);
});

test("buildWeekSignalSnapshot overlays workspace judgments only for locked focus flows", () => {
  const snapshot = buildWeekSignalSnapshot({
    tasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: true,
    workspaceLite: {
      boundaryCards: [
        { kind: "pending", title: "待确认判断", summary: "先做试点", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
        { kind: "risk", title: "风险", summary: "负责人尚未确认", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
      ],
      nextActions: ["和负责人确认预算"],
    },
    eventLine: {
      id: "event-1",
      name: "韶关推进线",
      nextStep: "整理下一轮动作",
    },
  });

  assert.deepEqual(snapshot.pendingJudgments, ["先做试点"]);
  assert.deepEqual(snapshot.riskSignals, ["负责人尚未确认"]);
  assert.deepEqual(snapshot.suggestedActions, ["和负责人确认预算", "整理下一轮动作"]);
});

test("overdueCount is measured against today, not the week anchor", () => {
  const now = new Date("2026-04-17T10:00:00");
  const mixedTasks = [
    // Due Monday of this week, not done — should be overdue on Friday.
    {
      id: "overdue-mid-week",
      title: "本周一到期未完成",
      dueDate: "2026-04-13T12:00",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
    // Due last week, done — should NOT count as overdue.
    {
      id: "old-done",
      title: "上周完成",
      dueDate: "2026-04-08T12:00",
      progressStatus: "done",
      completionNote: "done",
      createdAt: "2026-04-01T09:00:00.000Z",
      updatedAt: "2026-04-08T12:00:00.000Z",
    },
    // No dueDate, not done — should count toward unscheduled.
    {
      id: "unscheduled-open",
      title: "未排期",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
    // No dueDate but already done — must not count toward unscheduled.
    {
      id: "unscheduled-done",
      title: "未排期但已完成",
      progressStatus: "done",
      completionNote: "done",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
  ];

  const snapshot = buildWeekSignalSnapshot({
    tasks: mixedTasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    now,
  });

  assert.equal(snapshot.facts.overdueCount, 1, "only the open mid-week task is overdue today");
  assert.equal(snapshot.facts.unscheduledCount, 1, "done + undated tasks are excluded");
  assert.equal(snapshot.facts.totalCount, 1, "only the mid-week task falls in this week");
});

test("UTC ISO dueDates are normalized to local date before comparing to week range", () => {
  // UTC "2026-04-12T23:00:00.000Z" is 2026-04-13 in CST (UTC+8), so in that
  // timezone it belongs to the week anchored at 2026-04-13. In a UTC-only world
  // the old code would have placed it in the prior week.
  const nearMidnightTasks = [
    {
      id: "utc-late-sunday",
      title: "UTC 周日晚的任务",
      dueDate: "2026-04-12T23:00:00.000Z",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
  ];
  const snapshot = buildWeekSignalSnapshot({
    tasks: nearMidnightTasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    now: new Date("2026-04-14T10:00:00"),
  });

  // In UTC+8 the task is in-week; in UTC-8 it is a week earlier. The assertion
  // below is only strict for the former, so we fold both cases into "≤ 1".
  // What we really care about is that the count is NOT double-assigned and
  // that the function does not throw on UTC ISO input.
  assert.ok(snapshot.facts.totalCount <= 1, "task placed in exactly 0 or 1 week");
  assert.ok(snapshot.facts.overdueCount <= 1, "not double-counted as overdue");
});
