import test from "node:test";
import assert from "node:assert/strict";

import { buildCreateTaskDueDate } from "../../.mobile-core-tests/dist/lib/create-task-due-date-core.js";

test("create task due date stays empty when no date was selected", () => {
  assert.equal(
    buildCreateTaskDueDate({
      customDate: null,
      customTime: null,
      preset: undefined,
      dateCleared: false,
    }),
    undefined,
  );
});

test("create task due date uses calendar preset when not cleared", () => {
  assert.equal(
    buildCreateTaskDueDate({
      customDate: null,
      customTime: null,
      preset: { dueDate: "2026-04-21", dueTime: "09:00" },
      dateCleared: false,
    }),
    "2026-04-21T09:00",
  );
});

test("create task due date remains empty after user clears a preset", () => {
  assert.equal(
    buildCreateTaskDueDate({
      customDate: null,
      customTime: null,
      preset: { dueDate: "2026-04-21", dueTime: "09:00" },
      dateCleared: true,
    }),
    undefined,
  );
});
