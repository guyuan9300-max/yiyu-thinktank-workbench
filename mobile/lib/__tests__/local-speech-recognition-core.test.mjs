import assert from "node:assert/strict";
import test from "node:test";

import {
  buildLocalSpeechRecognitionStartConfig,
  buildSpeechRecognitionErrorMessage,
  getEventTranscript,
  getPermissionGranted,
  getResultConfidence,
  getResultIsFinal,
  getSpeechRecognitionAudioUri,
} from "../../.mobile-core-tests/dist/lib/local-speech-recognition-core.js";

test("parses Android nested speech recognition results at resultIndex", () => {
  const event = {
    resultIndex: 1,
    results: [
      [{ transcript: "旧文本", confidence: 0.4, isFinal: true }],
      [{ transcript: "新的日程文本", confidence: 0.91, isFinal: false }],
    ],
  };

  assert.equal(getEventTranscript(event), "新的日程文本");
  assert.equal(getResultConfidence(event), 0.91);
  assert.equal(getResultIsFinal(event), false);
});

test("parses flat native speech recognition result", () => {
  const event = {
    results: [{ transcript: "会议安排", confidence: 0.72, final: true }],
  };

  assert.equal(getEventTranscript(event), "会议安排");
  assert.equal(getResultConfidence(event), 0.72);
  assert.equal(getResultIsFinal(event), true);
});

test("handles top-level transcript and permission shapes", () => {
  assert.equal(getEventTranscript({ transcript: "直接文本" }), "直接文本");
  assert.equal(getPermissionGranted({ status: "granted" }), true);
  assert.equal(getPermissionGranted({ granted: false }), false);
});

test("builds persistent speech recognition recording config only when requested", () => {
  assert.equal(buildLocalSpeechRecognitionStartConfig().recordingOptions, undefined);
  assert.deepEqual(
    buildLocalSpeechRecognitionStartConfig({ persistAudio: true }).recordingOptions,
    { persist: true },
  );
  assert.equal(buildLocalSpeechRecognitionStartConfig({ persistAudio: true }).lang, "zh-CN");
});

test("builds system microphone recognition config without app-provided audio source", () => {
  const config = buildLocalSpeechRecognitionStartConfig({
    persistAudio: true,
    useSystemMicrophone: true,
  });

  assert.equal(config.lang, "zh-CN");
  assert.equal(config.continuous, false);
  assert.equal(config.recordingOptions, undefined);
  assert.equal(config.addsPunctuation, undefined);
  assert.equal(config.contextualStrings, undefined);
  assert.equal(config.maxAlternatives, 1);
});

test("builds app audio source recognition config with persisted input audio", () => {
  const config = buildLocalSpeechRecognitionStartConfig({
    useAppAudioSource: true,
  });

  assert.equal(config.lang, "zh-CN");
  assert.equal(config.continuous, false);
  assert.deepEqual(config.recordingOptions, { persist: true });
  assert.equal(config.addsPunctuation, undefined);
  assert.equal(config.contextualStrings, undefined);
  assert.equal(config.maxAlternatives, 1);
});

test("reads persisted speech recognition audio uri from native events", () => {
  assert.equal(getSpeechRecognitionAudioUri({ uri: " file:///tmp/asr.m4a " }), "file:///tmp/asr.m4a");
  assert.equal(getSpeechRecognitionAudioUri({ uri: "" }), null);
  assert.equal(getSpeechRecognitionAudioUri({ uri: 123 }), null);
});

test("uses native speech recognition error payloads", () => {
  const message = buildSpeechRecognitionErrorMessage({ error: "Insufficient permissions" }, "fallback");
  assert.match(message, /系统语音识别服务没有拿到麦克风权限/);
  assert.match(message, /Insufficient permissions/);
  assert.match(
    buildSpeechRecognitionErrorMessage({ error: 9 }, "fallback"),
    /系统语音识别服务没有拿到麦克风权限/,
  );
  assert.equal(buildSpeechRecognitionErrorMessage({}, "fallback"), "fallback");
});
