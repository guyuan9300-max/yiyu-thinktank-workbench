import test from "node:test";
import assert from "node:assert/strict";

import { createRuntimeController } from "../../.mobile-core-tests/dist/lib/runtime-controller.js";

test("runtime controller initializes once and starts sync once", async () => {
  let initializeCount = 0;
  let startCount = 0;
  let stopCount = 0;
  let resetCount = 0;

  const controller = createRuntimeController({
    initializeBaseUrl: async () => {
      initializeCount += 1;
    },
    startSync: async () => {
      startCount += 1;
    },
    stopSync: async () => {
      stopCount += 1;
    },
    resetSessionState: () => {
      resetCount += 1;
    },
  });

  await Promise.all([controller.start(), controller.start()]);
  assert.equal(initializeCount, 1);
  assert.equal(startCount, 1);
  assert.equal(controller.isSyncRunning(), true);

  await controller.stop();
  assert.equal(stopCount, 1);
  assert.equal(resetCount, 1);
  assert.equal(controller.isSyncRunning(), false);
});

test("runtime controller can stop before sync ever starts", async () => {
  let initializeCount = 0;
  let stopCount = 0;
  let resetCount = 0;

  const controller = createRuntimeController({
    initializeBaseUrl: () => {
      initializeCount += 1;
    },
    startSync: () => {},
    stopSync: () => {
      stopCount += 1;
    },
    resetSessionState: () => {
      resetCount += 1;
    },
  });

  await controller.stop();
  assert.equal(initializeCount, 1);
  assert.equal(stopCount, 0);
  assert.equal(resetCount, 1);
});
