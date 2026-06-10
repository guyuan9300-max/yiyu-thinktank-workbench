import test from "node:test";
import assert from "node:assert/strict";

import {
  processQueuedLegacyUploadOps,
  resolveLegacyUploadFailureStatus,
} from "../../.mobile-core-tests/dist/lib/legacy-upload-runner-core.js";

test("resolveLegacyUploadFailureStatus keeps transient failures queued", () => {
  assert.equal(resolveLegacyUploadFailureStatus("network_unavailable"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("bind_pending_remote_id"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("manual_pause"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("upload_failed"), "needs_attention");
  assert.equal(resolveLegacyUploadFailureStatus("file_missing"), "needs_attention");
});

test("processQueuedLegacyUploadOps retries queued items only and stops on auth", async () => {
  const attempted = [];
  const result = await processQueuedLegacyUploadOps(
    [
      { opId: "queued-1", status: "queued" },
      { opId: "processing-1", status: "processing" },
      { opId: "queued-2", status: "queued" },
      { opId: "needs-attention-1", status: "needs_attention" },
    ],
    async (opId) => {
      attempted.push(opId);
      if (opId === "queued-2") {
        return { ok: false, reasonCode: "auth_required", message: "auth expired" };
      }
      return { ok: true };
    },
  );

  assert.deepEqual(attempted, ["queued-1", "queued-2"]);
  assert.deepEqual(result, {
    attempted: 2,
    completed: 1,
    stoppedByAuth: true,
    stoppedByNetwork: false,
  });
});

test("processQueuedLegacyUploadOps stops on network to avoid burning the whole cycle", async () => {
  const attempted = [];
  const result = await processQueuedLegacyUploadOps(
    [
      { opId: "queued-1", status: "queued" },
      { opId: "queued-2", status: "queued" },
    ],
    async (opId) => {
      attempted.push(opId);
      return {
        ok: false,
        reasonCode: "network_unavailable",
        message: `${opId} failed`,
      };
    },
  );

  assert.deepEqual(attempted, ["queued-1"]);
  assert.deepEqual(result, {
    attempted: 1,
    completed: 0,
    stoppedByAuth: false,
    stoppedByNetwork: true,
  });
});
