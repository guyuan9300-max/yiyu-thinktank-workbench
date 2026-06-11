import test from "node:test";
import assert from "node:assert/strict";

import { foldPendingOps } from "../../.mobile-core-tests/dist/lib/pending-op-policy.js";

function makeOp(operation, overrides = {}) {
  return {
    clientOpId: `${operation}-op`,
    entityType: "task",
    entityId: "task_1",
    entityRemoteId: overrides.entityRemoteId ?? null,
    operation,
    payload: overrides.payload ?? null,
    lane: overrides.lane ?? "interactive",
    status: overrides.status ?? "queued",
    visibilityScope: overrides.visibilityScope ?? "team_shared",
    localVersion: overrides.localVersion ?? 1,
    baseRemoteVersion: overrides.baseRemoteVersion ?? null,
  };
}

test("create plus updates folds into one final create snapshot", () => {
  const result = foldPendingOps(
    [makeOp("create", { payload: { title: "A" }, localVersion: 1 })],
    makeOp("update", { payload: { dueDate: "2026-04-18" }, localVersion: 2 }),
  );
  assert.equal(result.length, 1);
  assert.equal(result[0].operation, "create");
  assert.deepEqual(result[0].payload, { title: "A", dueDate: "2026-04-18" });
  assert.equal(result[0].localVersion, 2);
});

test("create then delete before remote sync cancels both ops", () => {
  const result = foldPendingOps(
    [makeOp("create", { payload: { title: "A" } })],
    makeOp("delete"),
  );
  assert.deepEqual(result, []);
});

test("update plus update merges into one update", () => {
  const result = foldPendingOps(
    [makeOp("update", { payload: { title: "A" }, localVersion: 2 })],
    makeOp("update", { payload: { priority: "high" }, localVersion: 3 }),
  );
  assert.equal(result.length, 1);
  assert.equal(result[0].operation, "update");
  assert.deepEqual(result[0].payload, { title: "A", priority: "high" });
  assert.equal(result[0].localVersion, 3);
});

test("review op stays behind the folded base mutation", () => {
  const result = foldPendingOps(
    [
      makeOp("create", { payload: { title: "A" }, localVersion: 1 }),
      makeOp("complete_with_review", {
        payload: { reviewNote: "已完成" },
        localVersion: 2,
      }),
    ],
    makeOp("update", { payload: { priority: "high" }, localVersion: 3 }),
  );

  assert.equal(result.length, 2);
  assert.equal(result[0].operation, "create");
  assert.deepEqual(result[0].payload, { title: "A", priority: "high" });
  assert.equal(result[1].operation, "complete_with_review");
  assert.equal(result[1].localVersion, 3);
});
