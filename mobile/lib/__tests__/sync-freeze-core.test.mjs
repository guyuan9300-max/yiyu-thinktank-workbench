import test from "node:test";
import assert from "node:assert/strict";

import {
  describeSyncFreezeState,
  isSyncFreezeBlocked,
  isSyncFreezePaused,
} from "../../.mobile-core-tests/dist/lib/sync-freeze-core.js";

test("describeSyncFreezeState returns a user-facing summary for paused sync", () => {
  const descriptor = describeSyncFreezeState("paused_by_user", null);

  assert.equal(descriptor.summary, "同步已暂停");
  assert.equal(descriptor.actionLabel, "恢复同步");
  assert.equal(isSyncFreezePaused("paused_by_user"), true);
  assert.equal(isSyncFreezeBlocked("paused_by_user"), false);
});

test("describeSyncFreezeState keeps blocked states non-resumable", () => {
  const descriptor = describeSyncFreezeState("blocked_by_integrity", "orphan_task_pending_ops");

  assert.equal(descriptor.summary, "同步已冻结，需要处理本地数据完整性");
  assert.equal(descriptor.actionLabel, null);
  assert.equal(descriptor.detail, "orphan_task_pending_ops");
  assert.equal(isSyncFreezeBlocked("blocked_by_integrity"), true);
});
