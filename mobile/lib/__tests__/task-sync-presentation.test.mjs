import test from "node:test";
import assert from "node:assert/strict";
import { buildTaskSyncIndicator, formatTaskSyncReasonCode } from "../task-sync-presentation.ts";

test("buildTaskSyncIndicator returns null for synced tasks", () => {
  assert.equal(buildTaskSyncIndicator({ remoteState: "synced", syncReasonCode: null }), null);
});

test("buildTaskSyncIndicator prioritizes version conflicts", () => {
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "needs_attention", syncReasonCode: "version_conflict" }), {
    label: "冲突",
    detail: "服务器版本冲突",
    tone: "danger",
  });
});

test("buildTaskSyncIndicator exposes queued and processing states", () => {
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "queued", syncReasonCode: null }), {
    label: "待同步",
    detail: "本地已保存，等待后台同步",
    tone: "info",
  });
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "processing", syncReasonCode: null }), {
    label: "处理中",
    detail: "后台正在处理本地修改",
    tone: "warning",
  });
});

test("buildTaskSyncIndicator labels needs_attention as 待处理 (统一口径) with danger tone", () => {
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "needs_attention", syncReasonCode: "network_unavailable" }), {
    label: "待处理",
    detail: "网络不可用",
    tone: "danger",
  });
});

test("formatTaskSyncReasonCode falls back safely", () => {
  assert.equal(formatTaskSyncReasonCode("auth_expired"), "登录已过期");
  assert.equal(formatTaskSyncReasonCode("unknown"), "请稍后再试");
});
