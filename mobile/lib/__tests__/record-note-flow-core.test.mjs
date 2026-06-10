import test from "node:test";
import assert from "node:assert/strict";

import {
  canTransitionRecordNoteProgress,
  getAllowedRecordNoteTransitions,
} from "../../.mobile-core-tests/dist/lib/record-note-flow-core.js";

test("record-note progress only allows the locked transition graph", () => {
  assert.equal(canTransitionRecordNoteProgress("任务已保存", "录音待挂接"), true);
  assert.equal(canTransitionRecordNoteProgress("任务已保存", "正在恢复暂存语音"), false);
  assert.equal(canTransitionRecordNoteProgress("录音待同步", "完成"), true);
  assert.equal(canTransitionRecordNoteProgress("录音待同步", "正在恢复暂存语音"), false);
  assert.equal(canTransitionRecordNoteProgress("录音需处理", "录音待同步"), false);
});

test("record-note progress exposes the allowed next states for recovery flow", () => {
  assert.deepEqual(getAllowedRecordNoteTransitions("正在恢复暂存语音"), [
    "录音待挂接",
    "录音需处理",
  ]);
});
