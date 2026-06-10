import test from "node:test";
import assert from "node:assert/strict";

import { decideTaskServerAckAction } from "../../.mobile-core-tests/dist/lib/task-sync-policy.js";

test("stale ack with newer local version keeps dirty task and promotes pending create", () => {
  const decision = decideTaskServerAckAction({
    localTask: {
      id: "task-1",
      title: "测试任务",
      priority: "normal",
      progressStatus: "todo",
      localVersion: 3,
      remoteState: "queued",
    },
    ackLocalVersion: 1,
    hasPendingOps: true,
    pendingCreateExists: true,
  });

  assert.equal(decision.shouldReplaceLocalTask, false);
  assert.equal(decision.shouldUpdateShadowOnly, true);
  assert.equal(decision.shouldPromotePendingCreate, true);
});

test("clean ack without pending ops can replace local task directly", () => {
  const decision = decideTaskServerAckAction({
    localTask: {
      id: "task-2",
      title: "测试任务",
      priority: "normal",
      progressStatus: "todo",
      localVersion: 2,
      remoteState: "syncing",
    },
    ackLocalVersion: 2,
    hasPendingOps: false,
    pendingCreateExists: false,
  });

  assert.equal(decision.shouldReplaceLocalTask, true);
  assert.equal(decision.shouldUpdateShadowOnly, false);
  assert.equal(decision.shouldPromotePendingCreate, false);
});
