import test from "node:test";
import assert from "node:assert/strict";

import { reconcileQueuedSmartInputItems } from "../../.mobile-core-tests/dist/lib/smart-input-queue-core.js";

test("reconcileQueuedSmartInputItems removes only recovered ids from the latest queue snapshot", () => {
  const nextQueue = reconcileQueuedSmartInputItems(
    [
      { id: "new-item" },
      { id: "recovered-item" },
      { id: "still-pending" },
    ],
    new Set(["recovered-item"]),
  );

  assert.deepEqual(nextQueue, [
    { id: "new-item" },
    { id: "still-pending" },
  ]);
});

test("reconcileQueuedSmartInputItems respects a user clear by not resurrecting stale entries", () => {
  const nextQueue = reconcileQueuedSmartInputItems([], new Set(["old-item"]));
  assert.deepEqual(nextQueue, []);
});
