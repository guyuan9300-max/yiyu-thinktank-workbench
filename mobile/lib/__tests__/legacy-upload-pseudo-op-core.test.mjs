import test from "node:test";
import assert from "node:assert/strict";

import {
  buildLegacyUploadPseudoOp,
  mergeLaneDiagnosticsWithLegacyUploads,
  normalizeLegacyUploadReasonCode,
  normalizeLegacyUploadStatus,
} from "../../.mobile-core-tests/dist/lib/legacy-upload-pseudo-op-core.js";

test("buildLegacyUploadPseudoOp derives age from the latest attempt", () => {
  const op = buildLegacyUploadPseudoOp(
    {
      opId: "legacy_upload_1",
      objectType: "recorded_audio_attachment",
      objectLocalId: "voice-1",
      objectRemoteId: null,
      lane: "transfer",
      status: "queued",
      retryCount: 1,
      reasonCode: "bind_pending_remote_id",
      createdAt: "2026-04-18T00:00:00.000Z",
      lastAttemptAt: "2026-04-18T00:30:00.000Z",
      displayTitle: "测试录音",
      taskLocalId: "task-1",
      filePath: "/tmp/voice.m4a",
      size: 1024,
      mtime: 123,
      hash: null,
      entityRefLocalId: "task-1",
      mimeType: "audio/m4a",
      durationSeconds: 12,
    },
    Date.parse("2026-04-18T01:00:00.000Z"),
  );

  assert.equal(op.ageMs, 30 * 60 * 1000);
});

test("normalizeLegacyUploadReasonCode and status fall back to safe defaults", () => {
  assert.equal(normalizeLegacyUploadReasonCode("file_missing"), "file_missing");
  assert.equal(normalizeLegacyUploadReasonCode("not_real_reason"), "unknown_error");
  assert.equal(normalizeLegacyUploadStatus("processing"), "processing");
  assert.equal(normalizeLegacyUploadStatus("anything"), "needs_attention");
});

test("mergeLaneDiagnosticsWithLegacyUploads folds legacy transfer ops into diagnostics", () => {
  const merged = mergeLaneDiagnosticsWithLegacyUploads(
    {
      interactive: {
        lane: "interactive",
        total: 1,
        oldestAgeMs: 10,
        active: false,
        topReasonCode: null,
      },
      transfer: {
        lane: "transfer",
        total: 2,
        oldestAgeMs: 5_000,
        active: false,
        topReasonCode: "network_unavailable",
      },
      derived: {
        lane: "derived",
        total: 0,
        oldestAgeMs: null,
        active: false,
        topReasonCode: null,
      },
    },
    [
      buildLegacyUploadPseudoOp(
        {
          opId: "legacy_upload_1",
          objectType: "recorded_audio_attachment",
          objectLocalId: "voice-1",
          objectRemoteId: null,
          lane: "transfer",
          status: "queued",
          retryCount: 0,
          reasonCode: "file_missing",
          createdAt: "2026-04-18T00:00:00.000Z",
          lastAttemptAt: null,
          displayTitle: "录音 A",
          taskLocalId: "task-1",
          filePath: "/tmp/a.m4a",
          size: null,
          mtime: null,
          hash: null,
          entityRefLocalId: "task-1",
          mimeType: "audio/m4a",
          durationSeconds: 10,
        },
        Date.parse("2026-04-18T01:00:00.000Z"),
      ),
      buildLegacyUploadPseudoOp(
        {
          opId: "legacy_upload_2",
          objectType: "recorded_audio_attachment",
          objectLocalId: "voice-2",
          objectRemoteId: null,
          lane: "transfer",
          status: "processing",
          retryCount: 1,
          reasonCode: "file_missing",
          createdAt: "2026-04-18T00:10:00.000Z",
          lastAttemptAt: "2026-04-18T00:40:00.000Z",
          displayTitle: "录音 B",
          taskLocalId: "task-2",
          filePath: "/tmp/b.m4a",
          size: null,
          mtime: null,
          hash: null,
          entityRefLocalId: "task-2",
          mimeType: "audio/m4a",
          durationSeconds: 15,
        },
        Date.parse("2026-04-18T01:00:00.000Z"),
      ),
    ],
  );

  assert.equal(merged.transfer.total, 4);
  assert.equal(merged.transfer.active, true);
  assert.equal(merged.transfer.oldestAgeMs, 60 * 60 * 1000);
  assert.equal(merged.transfer.topReasonCode, "file_missing");
});
