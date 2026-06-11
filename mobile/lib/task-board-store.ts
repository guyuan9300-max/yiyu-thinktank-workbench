import { useEffect, useMemo, useSyncExternalStore } from "react";
import { devLog, measureDevSync } from "./dev-log";
import * as localDb from "./local-db";
import { getTaskBoardSnapshot } from "./task-query-service";
import {
  getSyncStatus,
  onDataChanged,
  onSyncStatusChange,
  triggerSync,
} from "./sync-engine";
import {
  createTaskBoardStore,
  type TaskBoardStoreState,
} from "./task-board-store-core";

const taskBoardStore = createTaskBoardStore({
  initDatabase: () => {
    localDb.initDatabase();
  },
  getLocalTaskBoard: () =>
    measureDevSync("local-db", "getLocalTaskBoard", () => getTaskBoardSnapshot()),
  onDataChanged,
  onSyncStatusChange,
  getSyncStatus,
  triggerSync,
  log: (message, payload) => {
    devLog("taskBoard", message, payload);
  },
});

export function ensureTaskBoardStoreInitialized(): void {
  taskBoardStore.ensureInitialized();
}

export async function refreshTaskBoard(): Promise<void> {
  await taskBoardStore.refresh();
}

export function resetTaskBoardStore(): void {
  taskBoardStore.reset();
}

export function useTaskBoard(): TaskBoardStoreState & { refresh: () => Promise<void> } {
  const snapshot = useSyncExternalStore(
    taskBoardStore.subscribe,
    taskBoardStore.getSnapshot,
    taskBoardStore.getSnapshot,
  );

  useEffect(() => {
    taskBoardStore.ensureInitialized();
  }, []);

  return useMemo(
    () => ({
      ...snapshot,
      refresh: () => taskBoardStore.refresh(),
    }),
    [snapshot],
  );
}
