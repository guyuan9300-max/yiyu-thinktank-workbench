import test from "node:test";
import assert from "node:assert/strict";

import { createTaskBoardStore } from "../../.mobile-core-tests/dist/lib/task-board-store-core.js";

function makeBoard(taskIds) {
  return {
    tasks: taskIds.map((id) => ({ id, title: id })),
    inboxCount: taskIds.length,
    tasksTodayCount: taskIds.length,
  };
}

test("task board store hydrates from local board and reacts to sync events", async () => {
  let initCount = 0;
  let refreshCount = 0;
  let dataListener = () => {};
  let statusListener = () => {};
  let board = makeBoard(["task-1"]);
  let releaseRefresh;

  const store = createTaskBoardStore({
    initDatabase: () => {
      initCount += 1;
    },
    getLocalTaskBoard: () => board,
    onDataChanged: (listener) => {
      dataListener = listener;
      return () => {
        dataListener = () => {};
      };
    },
    onSyncStatusChange: (listener) => {
      statusListener = listener;
      return () => {
        statusListener = () => {};
      };
    },
    getSyncStatus: () => ({ status: "idle", lastSyncTime: null }),
    triggerSync: () => {
      refreshCount += 1;
      return new Promise((resolve) => {
        releaseRefresh = resolve;
      });
    },
  });

  store.ensureInitialized();
  assert.equal(initCount, 1);
  assert.equal(store.getSnapshot().isHydrated, true);
  assert.equal(store.getSnapshot().board.tasks[0].id, "task-1");

  statusListener("syncing", "2026-04-16T10:00:00.000Z");
  assert.equal(store.getSnapshot().syncStatus, "syncing");
  assert.equal(store.getSnapshot().lastSyncTime, "2026-04-16T10:00:00.000Z");

  board = makeBoard(["task-2", "task-3"]);
  dataListener();
  assert.deepEqual(
    store.getSnapshot().board.tasks.map((task) => task.id),
    ["task-2", "task-3"],
  );

  const refreshA = store.refresh();
  const refreshB = store.refresh();
  assert.equal(refreshCount, 1);
  releaseRefresh();
  await Promise.all([refreshA, refreshB]);
});

test("task board store reset clears hydration and sync state", () => {
  const store = createTaskBoardStore({
    initDatabase: () => {},
    getLocalTaskBoard: () => makeBoard(["task-1"]),
    onDataChanged: () => () => {},
    onSyncStatusChange: () => () => {},
    getSyncStatus: () => ({ status: "idle", lastSyncTime: null }),
    triggerSync: async () => {},
  });

  store.ensureInitialized();
  assert.equal(store.getSnapshot().isHydrated, true);
  store.reset();
  assert.equal(store.getSnapshot().isHydrated, false);
  assert.equal(store.getSnapshot().board.tasks.length, 0);
});
