import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRecoveredDraftKey,
  shouldAttemptSmartInputRecovery,
  shouldAutoOpenRecoveredDraft,
  shouldUseRecoveredDraft,
} from "../../.mobile-core-tests/dist/lib/smart-input-recovery.js";

test("non-manual recovery is throttled and respects in-flight guard", () => {
  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "tasks_enter",
    queuedCount: 1,
    inFlight: true,
    nowMs: 2000,
    lastAttemptAt: 1000,
  }), false);

  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "tasks_enter",
    queuedCount: 1,
    inFlight: false,
    nowMs: 1500,
    lastAttemptAt: 1000,
  }), false);
});

test("manual recovery bypasses debounce but auto-open still requires safe UI state", () => {
  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "manual",
    queuedCount: 1,
    inFlight: false,
    nowMs: 1100,
    lastAttemptAt: 1000,
  }), true);

  assert.equal(shouldAutoOpenRecoveredDraft({
    trigger: "manual",
    isTasksScreenActive: true,
    hasBlockingUi: false,
  }), true);

  assert.equal(shouldAutoOpenRecoveredDraft({
    trigger: "app_active",
    isTasksScreenActive: true,
    hasBlockingUi: false,
  }), false);
});

test("recovered draft key prevents reopening same queued draft repeatedly", () => {
  const key = buildRecoveredDraftKey({
    title: "补充会议纪要",
    dueDate: "2026-04-16",
    dueTime: "10:00",
    description: "跟进事项",
  });

  assert.equal(shouldUseRecoveredDraft(key, null), true);
  assert.equal(shouldUseRecoveredDraft(key, key), false);
});
