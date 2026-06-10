import test from "node:test";
import assert from "node:assert/strict";

import {
  buildLocalSmartTaskDraftFromTranscript,
  buildRecordingPaths,
  buildRecordingTextIngestPayload,
  cleanTranscriptText,
  normalizeRecordingSegments,
} from "../../.mobile-core-tests/dist/lib/recording-session-core.js";

test("recording paths stay under the scoped local document directory", () => {
  const paths = buildRecordingPaths("file:///app/docs/", "account:abc/def", "rec 1");

  assert.equal(paths.directory, "file:///app/docs/recordings/account_abc_def/rec_1");
  assert.equal(paths.audioPath, `${paths.directory}/audio.m4a`);
  assert.equal(paths.rawTranscriptPath, `${paths.directory}/raw-transcript.txt`);
  assert.equal(paths.cleanTranscriptPath, `${paths.directory}/clean-transcript.txt`);
  assert.equal(paths.summaryPath, `${paths.directory}/summary.json`);
});

test("recording text cleanup adds lightweight punctuation and section breaks", () => {
  assert.equal(
    cleanTranscriptText("老师赋能项目设计待补完善 下一步整理项目复盘结论"),
    "老师赋能项目设计待补完善\n下一步整理项目复盘结论。",
  );
});

test("recording segments are normalized and fall back to clean text", () => {
  const createdAt = "2026-05-07T10:00:00.000Z";
  const segments = normalizeRecordingSegments(
    [
      { startMs: 800.4, endMs: 1234.7, text: "  第一段  ", confidence: 0.92 },
      { segmentIndex: 3, text: "" },
      { startMs: -20, endMs: null, text: "第二段", isFinal: false },
    ],
    "兜底文本",
    "rec-a",
    createdAt,
  );

  assert.deepEqual(
    segments.map((segment) => ({
      id: segment.id,
      index: segment.segmentIndex,
      startMs: segment.startMs,
      endMs: segment.endMs,
      text: segment.text,
      confidence: segment.confidence,
      isFinal: segment.isFinal,
      createdAt: segment.createdAt,
    })),
    [
      {
        id: "rec-a-segment-0000",
        index: 0,
        startMs: 800,
        endMs: 1235,
        text: "第一段",
        confidence: 0.92,
        isFinal: true,
        createdAt,
      },
      {
        id: "rec-a-segment-0002",
        index: 2,
        startMs: 0,
        endMs: null,
        text: "第二段",
        confidence: null,
        isFinal: false,
        createdAt,
      },
    ],
  );

  assert.equal(
    normalizeRecordingSegments([], "兜底文本", "rec-b", createdAt)[0].text,
    "兜底文本",
  );
});

test("recording text ingest payload excludes local audio fields", () => {
  const createdAt = "2026-05-07T10:00:00.000Z";
  const session = {
    id: "rec-1",
    scopeKey: "account-1",
    source: "task_detail",
    targetType: "task",
    targetLocalId: "task-local",
    targetRemoteId: "task-cloud",
    clientId: "client-1",
    eventLineId: "line-1",
    taskId: "task-cloud",
    meetingId: null,
    audioPath: "file:///app/docs/recordings/account-1/rec-1/audio.m4a",
    durationSeconds: 18,
    mimeType: "audio/m4a",
    audioHash: "hash",
    rawTranscriptPath: "file:///raw.txt",
    cleanTranscriptPath: "file:///clean.txt",
    summaryJson: "{\"brief\":\"摘要\"}",
    status: "local_saved",
    syncStatus: "pending",
    lastError: null,
    createdAt,
    updatedAt: createdAt,
  };
  const payload = buildRecordingTextIngestPayload({
    session,
    rawTranscript: "原始文本",
    cleanTranscript: "整理文本。",
    summary: { brief: "摘要" },
    segments: normalizeRecordingSegments(
      [{ text: "整理文本", startMs: 0, endMs: 18000 }],
      "",
      "rec-1",
      createdAt,
    ),
  });

  assert.equal(payload.recordingId, "rec-1");
  assert.equal(payload.taskId, "task-cloud");
  assert.equal(payload.clientId, "client-1");
  assert.equal(payload.durationSeconds, 18);
  assert.equal(payload.segments[0].text, "整理文本");
  assert.equal(Object.hasOwn(payload, "audioPath"), false);
  assert.equal(Object.hasOwn(payload, "audio"), false);
});

test("local smart task draft is built from transcript without cloud drafting", () => {
  const draft = buildLocalSmartTaskDraftFromTranscript(
    "明天整理项目复盘结论",
    "2026-05-07",
  );

  assert.equal(draft.intent, "task_schedule");
  assert.equal(draft.draft.dueDate, "2026-05-08");
  assert.equal(draft.draft.dueTime, null);
  assert.equal(draft.draft.title, "整理项目复盘结论");
  assert.deepEqual(draft.draft.tags, ["录音转写"]);
});

test("local smart task draft extracts spoken schedule time and action title", () => {
  const draft = buildLocalSmartTaskDraftFromTranscript(
    "今天下午帮我设定一条任务，下午7点半去看话剧",
    "2026-05-08",
  );

  assert.equal(draft.intent, "task_schedule");
  assert.equal(draft.draft.dueDate, "2026-05-08");
  assert.equal(draft.draft.dueTime, "19:30");
  assert.equal(draft.draft.title, "看话剧");
});
