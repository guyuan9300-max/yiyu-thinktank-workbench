import test from "node:test";
import assert from "node:assert/strict";

import {
  buildFocusMatchedTaskIds,
  buildFocusTaskStats,
  filterTasksByFocus,
  isLockedFocus,
  sortTasksByFocusPriority,
} from "../../.mobile-core-tests/dist/lib/focus-selectors.js";

test("isLockedFocus only returns true for locked client scopes", () => {
  assert.equal(isLockedFocus({ lockMode: "browse" }), false);
  assert.equal(isLockedFocus({ lockMode: "client" }), true);
  assert.equal(isLockedFocus({ lockMode: "client_event_line" }), true);
});

test("filterTasksByFocus narrows to event line first when present", () => {
  const focus = {
    lockMode: "client_event_line",
    clientId: "client-1",
    eventLineId: "event-2",
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-1" },
    { id: "task-2", clientId: "client-1", eventLineId: "event-2" },
    { id: "task-3", clientId: "client-2", eventLineId: "event-2" },
  ];

  assert.deepEqual(
    filterTasksByFocus(tasks, focus).map((task) => task.id),
    ["task-2", "task-3"],
  );
});

test("buildFocusMatchedTaskIds returns the ids that match the current client lock", () => {
  const focus = {
    lockMode: "client",
    clientId: "client-1",
    eventLineId: null,
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-1" },
    { id: "task-2", clientId: "client-1", eventLineId: null },
    { id: "task-3", clientId: "client-2", eventLineId: "event-1" },
  ];

  const matched = buildFocusMatchedTaskIds(tasks, focus);
  assert.equal(matched.has("task-1"), true);
  assert.equal(matched.has("task-2"), true);
  assert.equal(matched.has("task-3"), false);
});

test("sortTasksByFocusPriority lifts matched tasks ahead of the rest while keeping stable order", () => {
  const focus = {
    lockMode: "client",
    clientId: "client-1",
    eventLineId: null,
  };
  const tasks = [
    { id: "task-1", clientId: "client-2", eventLineId: null },
    { id: "task-2", clientId: "client-1", eventLineId: null },
    { id: "task-3", clientId: "client-2", eventLineId: null },
    { id: "task-4", clientId: "client-1", eventLineId: null },
  ];

  assert.deepEqual(
    sortTasksByFocusPriority(tasks, focus).map((task) => task.id),
    ["task-2", "task-4", "task-1", "task-3"],
  );
});

test("buildFocusTaskStats counts scheduled, unscheduled, and completed matches", () => {
  const focus = {
    lockMode: "client_event_line",
    clientId: "client-1",
    eventLineId: "event-2",
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-2", dueDate: "2026-04-19", progressStatus: "todo" },
    { id: "task-2", clientId: "client-1", eventLineId: "event-2", dueDate: null, progressStatus: "done" },
    { id: "task-3", clientId: "client-1", eventLineId: "event-1", dueDate: "2026-04-20", progressStatus: "todo" },
  ];

  assert.deepEqual(buildFocusTaskStats(tasks, focus), {
    matchedCount: 2,
    scheduledCount: 1,
    unscheduledCount: 1,
    doneCount: 1,
  });
});
