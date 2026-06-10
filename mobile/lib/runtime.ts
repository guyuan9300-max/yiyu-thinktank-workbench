import * as api from "./api";
import * as cache from "./cache";
import { buildAccountScopeKey } from "./account-scope";
import { clearClientIntelCache } from "./client-intel-store";
import * as localDb from "./local-db";
import { clearAllSmartInputQueueScopes } from "./smart-input-queue";
import {
  setSyncFreezeStateForRuntime,
  startSyncEngine,
  stopSyncEngine,
} from "./sync-engine";
import { resetTaskBoardStore } from "./task-board-store";
import { resetCurrentFocusStore } from "./current-focus-store";
import { devLog } from "./dev-log";
import { createRuntimeController } from "./runtime-controller";
import { initializeRuntimeFlags } from "./runtime-flags";
import { rescheduleAllReminders } from "./task-reminder-scheduler";
import type { SessionUser } from "./types";

async function clearRuntimeSessionArtifacts(): Promise<void> {
  resetTaskBoardStore();
  resetCurrentFocusStore();
  await Promise.allSettled([
    cache.clearAll(),
    clearClientIntelCache({ allScopes: true }),
    clearAllSmartInputQueueScopes(),
  ]);
}

const controller = createRuntimeController({
  initializeBaseUrl: async () => {
    await api.initBaseUrl();
  },
  startSync: async () => {
    devLog("runtime", "start.sync_engine");
    await startSyncEngine();
  },
  stopSync: async () => {
    devLog("runtime", "stop.sync_engine");
    await stopSyncEngine();
  },
  resetSessionState: async () => {
    localDb.clearAllData();
    await clearRuntimeSessionArtifacts();
    devLog("runtime", "session.reset");
  },
});

export async function initializeRuntime(): Promise<void> {
  await controller.initialize();
  await initializeRuntimeFlags();
}

export async function startAuthenticatedRuntime(user: SessionUser): Promise<void> {
  await initializeRuntime();
  let scopePreparation: ReturnType<typeof localDb.prepareDatabaseForAccountScope>;
  try {
    scopePreparation = localDb.prepareDatabaseForAccountScope(buildAccountScopeKey(user));
  } catch (error) {
    const message = error instanceof Error ? error.message : "migration_prepare_failed";
    setSyncFreezeStateForRuntime("blocked_by_migration_failure", message);
    devLog("runtime", "scope.prepare_failed", { message });
    throw error;
  }
  if (scopePreparation.scopeChanged) {
    await clearRuntimeSessionArtifacts();
    devLog("runtime", "scope.changed.cleanup");
  }
  devLog("runtime", "scope.prepared", {
    scopeChanged: scopePreparation.scopeChanged,
    integrityStatus: scopePreparation.integrityStatus,
    integrityReason: scopePreparation.integrityReason,
  });
  await controller.start();
  // 登录后按本地任务全量重排提醒（含提前申请通知权限/建渠道）。fire-and-forget，内部已吞错。
  void rescheduleAllReminders();
}

export async function stopAuthenticatedRuntime(options?: { clearSessionState?: boolean }): Promise<void> {
  await controller.stop(options);
}

export function isRuntimeSyncRunning(): boolean {
  return controller.isSyncRunning();
}
