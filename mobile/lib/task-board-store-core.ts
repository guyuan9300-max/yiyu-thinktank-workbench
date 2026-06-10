import type { TaskBoardResponse } from "./types";

export type TaskBoardSyncStatus = "idle" | "syncing" | "error";

export interface TaskBoardStoreState {
  board: TaskBoardResponse;
  syncStatus: TaskBoardSyncStatus;
  lastSyncTime: string | null;
  isHydrated: boolean;
}

export interface TaskBoardStoreDeps {
  initDatabase: () => void;
  getLocalTaskBoard: () => TaskBoardResponse;
  onDataChanged: (listener: () => void) => () => void;
  onSyncStatusChange: (
    listener: (status: TaskBoardSyncStatus, lastSyncTime: string | null) => void,
  ) => () => void;
  getSyncStatus: () => { status: TaskBoardSyncStatus; lastSyncTime: string | null };
  triggerSync: () => Promise<void>;
  log?: (message: string, payload?: Record<string, unknown>) => void;
}

const EMPTY_BOARD: TaskBoardResponse = {
  tasks: [],
  inboxCount: 0,
  tasksTodayCount: 0,
};

export function createTaskBoardStore(deps: TaskBoardStoreDeps) {
  let state: TaskBoardStoreState = {
    board: EMPTY_BOARD,
    syncStatus: deps.getSyncStatus().status,
    lastSyncTime: deps.getSyncStatus().lastSyncTime,
    isHydrated: false,
  };
  let initialized = false;
  let refreshPromise: Promise<void> | null = null;
  let cleanupDataListener: (() => void) | null = null;
  let cleanupStatusListener: (() => void) | null = null;
  const listeners = new Set<() => void>();

  const emit = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  const setState = (next: TaskBoardStoreState) => {
    state = next;
    emit();
  };

  const hydrateBoard = () => {
    const board = deps.getLocalTaskBoard();
    setState({
      ...state,
      board,
      isHydrated: true,
    });
  };

  const ensureInitialized = () => {
    if (initialized) {
      return;
    }
    initialized = true;
    deps.initDatabase();
    hydrateBoard();
    cleanupDataListener = deps.onDataChanged(() => {
      deps.log?.("board.updated");
      hydrateBoard();
    });
    cleanupStatusListener = deps.onSyncStatusChange((status, lastSyncTime) => {
      setState({
        ...state,
        syncStatus: status,
        lastSyncTime,
      });
    });
  };

  const refresh = async () => {
    ensureInitialized();
    if (!refreshPromise) {
      deps.log?.("refresh.requested");
      refreshPromise = deps.triggerSync().finally(() => {
        refreshPromise = null;
      });
    } else {
      deps.log?.("refresh.reused_inflight");
    }
    await refreshPromise;
  };

  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  const reset = () => {
    cleanupDataListener?.();
    cleanupStatusListener?.();
    cleanupDataListener = null;
    cleanupStatusListener = null;
    initialized = false;
    refreshPromise = null;
    state = {
      board: EMPTY_BOARD,
      syncStatus: "idle",
      lastSyncTime: null,
      isHydrated: false,
    };
    emit();
  };

  return {
    ensureInitialized,
    getSnapshot: () => state,
    subscribe,
    refresh,
    reset,
  };
}
