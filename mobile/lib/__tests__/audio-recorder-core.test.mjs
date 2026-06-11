import assert from "node:assert/strict";
import test from "node:test";

import {
  getAudioRecorderStartFailureMessage,
  isExpoAudioRecorderPrepareBusyError,
} from "../../.mobile-core-tests/dist/lib/audio-recorder-core.js";

test("classifies an ongoing Android recording-service bind as a prepare-busy error", () => {
  const error = new Error(
    "Call to function 'AudioRecorder.prepareToRecordAsync' has been rejected. " +
      "Caused by: Tried binding to the recording service while the previous attempt is still ongoing.",
  );

  assert.equal(isExpoAudioRecorderPrepareBusyError(error), true);
  assert.equal(
    getAudioRecorderStartFailureMessage(error),
    "录音服务还在释放上一次会话，请稍等 1 秒后重试。",
  );
});

test("classifies an already prepared recorder as a prepare-busy error", () => {
  const error = new Error(
    "AudioRecorder has already been prepared. Stop or release the current session before preparing again.",
  );

  assert.equal(isExpoAudioRecorderPrepareBusyError(error), true);
  assert.equal(
    getAudioRecorderStartFailureMessage(error),
    "录音服务还在释放上一次会话，请稍等 1 秒后重试。",
  );
});

test("keeps non-prepare recording errors visible", () => {
  assert.equal(isExpoAudioRecorderPrepareBusyError(new Error("请先允许麦克风权限。")), false);
  assert.equal(getAudioRecorderStartFailureMessage(new Error("请先允许麦克风权限。")), "请先允许麦克风权限。");
  assert.equal(getAudioRecorderStartFailureMessage({}), "无法开始录音，请稍后重试。");
});
