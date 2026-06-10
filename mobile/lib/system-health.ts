import { useEffect, useMemo, useState } from "react";
import * as FileSystem from "expo-file-system/legacy";
import * as localDb from "./local-db";
import { fetchMobileCapabilities, getBaseUrl } from "./api";
import { getLegacyUploadPseudoOps } from "./legacy-upload-ops";
import { mergeLaneDiagnosticsWithLegacyUploads } from "./legacy-upload-pseudo-op-core";
import {
  retryAllLegacyUploadPseudoOps,
  retryLegacyUploadPseudoOp,
} from "./record-note-service";
import {
  getRecordingDiagnosticsSnapshot,
  retryPendingRecordingTextSync,
  type RecordingDiagnosticsSnapshot,
} from "./recording-session-service";
import { describeSyncFreezeState } from "./sync-freeze-core";
import {
  getSyncControlState,
  getSyncStatus,
  isSyncPaused,
  onDataChanged,
  onSyncStatusChange,
  setSyncPaused,
  triggerSync,
  getRecentSyncEvents,
} from "./sync-engine";
import { getRuntimeFlags, setRuntimeFlag, type RuntimeFlagName } from "./runtime-flags";
import type {
  HealthLaneDiagnostic,
  LegacyUploadPseudoOp,
  MobileCapabilityRecord,
  PendingOpLane,
  PendingOpRecord,
  PendingOpSummary,
  SyncFreezeState,
  TaskConflictDiagnostic,
} from "./types";

export interface SystemHealthSnapshot {
  syncStatus: "idle" | "syncing" | "error";
  lastSyncTime: string | null;
  syncFreezeState: SyncFreezeState;
  syncFreezeDetail: string | null;
  isSyncPaused: boolean;
  blockedReason: string | null;
  freezeSummary: string;
  freezeActionLabel: string | null;
  pendingSummary: PendingOpSummary;
  recentPendingOps: PendingOpRecord[];
  taskConflicts: TaskConflictDiagnostic[];
  legacyUploadOps: LegacyUploadPseudoOp[];
  laneDiagnostics: Record<PendingOpLane, HealthLaneDiagnostic>;
  taskServerShadowCount: number;
  staleTaskServerShadowCount: number;
  accountScopeKey: string;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
  runtimeFlags: ReturnType<typeof getRuntimeFlags>;
  backendBaseUrl: string;
  backendCapabilities: MobileCapabilityRecord | null;
  backendCapabilitiesError: string | null;
  lastCapabilityProbeAt: string | null;
  recordings: RecordingDiagnosticsSnapshot;
}

export interface SystemHealthDiagnosticBundle {
  schemaVersion: 1;
  generatedAt: string;
  sync: {
    status: SystemHealthSnapshot["syncStatus"];
    lastSyncTime: string | null;
    freezeState: SyncFreezeState;
    freezeDetail: string | null;
    isPaused: boolean;
    blockedReason: string | null;
    freezeSummary: string;
  };
  pendingSummary: PendingOpSummary;
  recentPendingOps: PendingOpRecord[];
  taskConflicts: TaskConflictDiagnostic[];
  laneDiagnostics: Record<PendingOpLane, HealthLaneDiagnostic>;
  remoteStateSummary: ReturnType<typeof localDb.getTaskRemoteStateSummary>;
  legacyUploadOps: LegacyUploadPseudoOp[];
  taskServerShadow: {
    total: number;
    stale: number;
  };
  account: {
    scopeKey: string;
    integrityStatus: "ok" | "blocked";
    integrityReason: string | null;
  };
  runtimeFlags: ReturnType<typeof getRuntimeFlags>;
  recentSyncEvents: ReturnType<typeof getRecentSyncEvents>;
  backend: {
    baseUrl: string;
    capabilities: MobileCapabilityRecord | null;
    capabilityError: string | null;
    lastProbeAt: string | null;
  };
  recordings: RecordingDiagnosticsSnapshot;
}

const SYSTEM_HEALTH_EXPORT_DIR = `${FileSystem.documentDirectory ?? ""}system-health-exports/`;

export function loadSystemHealthSnapshot(): SystemHealthSnapshot {
  const syncStatus = getSyncStatus();
  const controlState = getSyncControlState();
  const integrityState = localDb.getDataIntegrityState();
  const shadowDiagnostics = localDb.getTaskServerShadowDiagnostics();
  const freezeDescriptor = describeSyncFreezeState(controlState.freezeState, controlState.detail);
  const legacyUploadOps = getLegacyUploadPseudoOps();
  const recordingDiagnostics = getRecordingDiagnosticsSnapshot();
  return {
    syncStatus: syncStatus.status,
    lastSyncTime: syncStatus.lastSyncTime,
    syncFreezeState: controlState.freezeState,
    syncFreezeDetail: controlState.detail,
    isSyncPaused: isSyncPaused(),
    blockedReason: controlState.blockedReason,
    freezeSummary: freezeDescriptor.summary,
    freezeActionLabel: freezeDescriptor.actionLabel,
    pendingSummary: localDb.getPendingOpsSummary(),
    recentPendingOps: localDb.getPendingOpsDebugList(8),
    taskConflicts: localDb.getTaskConflictDiagnostics(8),
    legacyUploadOps,
    laneDiagnostics: mergeLaneDiagnosticsWithLegacyUploads(
      localDb.getPendingOpsLaneDiagnostics(),
      legacyUploadOps,
    ),
    taskServerShadowCount: shadowDiagnostics.total,
    staleTaskServerShadowCount: shadowDiagnostics.stale,
    accountScopeKey: integrityState.accountScopeKey,
    integrityStatus: integrityState.integrityStatus,
    integrityReason: integrityState.integrityReason,
    runtimeFlags: getRuntimeFlags(),
    backendBaseUrl: getBaseUrl(),
    backendCapabilities: null,
    backendCapabilitiesError: null,
    lastCapabilityProbeAt: null,
    recordings: recordingDiagnostics,
  };
}

export function buildSystemHealthDiagnosticBundle(
  snapshot: SystemHealthSnapshot = loadSystemHealthSnapshot(),
): SystemHealthDiagnosticBundle {
  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    sync: {
      status: snapshot.syncStatus,
      lastSyncTime: snapshot.lastSyncTime,
      freezeState: snapshot.syncFreezeState,
      freezeDetail: snapshot.syncFreezeDetail,
      isPaused: snapshot.isSyncPaused,
      blockedReason: snapshot.blockedReason,
      freezeSummary: snapshot.freezeSummary,
    },
    pendingSummary: snapshot.pendingSummary,
    recentPendingOps: snapshot.recentPendingOps,
    taskConflicts: snapshot.taskConflicts,
    laneDiagnostics: snapshot.laneDiagnostics,
    remoteStateSummary: localDb.getTaskRemoteStateSummary(),
    legacyUploadOps: snapshot.legacyUploadOps,
    taskServerShadow: {
      total: snapshot.taskServerShadowCount,
      stale: snapshot.staleTaskServerShadowCount,
    },
    account: {
      scopeKey: snapshot.accountScopeKey,
      integrityStatus: snapshot.integrityStatus,
      integrityReason: snapshot.integrityReason,
    },
    runtimeFlags: snapshot.runtimeFlags,
    recentSyncEvents: getRecentSyncEvents(20),
    backend: {
      baseUrl: snapshot.backendBaseUrl,
      capabilities: snapshot.backendCapabilities,
      capabilityError: snapshot.backendCapabilitiesError,
      lastProbeAt: snapshot.lastCapabilityProbeAt,
    },
    recordings: snapshot.recordings,
  };
}

export async function exportSystemHealthDiagnosticBundle(
  snapshot: SystemHealthSnapshot = loadSystemHealthSnapshot(),
): Promise<{ filePath: string; bundle: SystemHealthDiagnosticBundle }> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持导出诊断文件。");
  }
  const bundle = buildSystemHealthDiagnosticBundle(snapshot);
  await FileSystem.makeDirectoryAsync(SYSTEM_HEALTH_EXPORT_DIR, { intermediates: true });
  const filePath = `${SYSTEM_HEALTH_EXPORT_DIR}diagnostic-${Date.now()}.json`;
  await FileSystem.writeAsStringAsync(filePath, JSON.stringify(bundle, null, 2), {
    encoding: FileSystem.EncodingType.UTF8,
  });
  return { filePath, bundle };
}

export function useSystemHealth() {
  const [snapshot, setSnapshot] = useState<SystemHealthSnapshot>(() => loadSystemHealthSnapshot());

  const refreshCapabilities = useMemo(
    () => async () => {
      try {
        const capabilities = await fetchMobileCapabilities();
        setSnapshot((current) => ({
          ...current,
          backendBaseUrl: getBaseUrl(),
          backendCapabilities: capabilities,
          backendCapabilitiesError: null,
          lastCapabilityProbeAt: new Date().toISOString(),
        }));
      } catch (error) {
        setSnapshot((current) => ({
          ...current,
          backendBaseUrl: getBaseUrl(),
          backendCapabilities: null,
          backendCapabilitiesError: error instanceof Error ? error.message : "能力探测失败",
          lastCapabilityProbeAt: new Date().toISOString(),
        }));
      }
    },
    [],
  );

  useEffect(() => {
    const refresh = () =>
      setSnapshot((current) => ({
        ...loadSystemHealthSnapshot(),
        backendCapabilities: current.backendCapabilities,
        backendCapabilitiesError: current.backendCapabilitiesError,
        lastCapabilityProbeAt: current.lastCapabilityProbeAt,
      }));
    const releaseData = onDataChanged(refresh);
    const releaseStatus = onSyncStatusChange(() => refresh());
    refresh();
    void refreshCapabilities();
    return () => {
      releaseData();
      releaseStatus();
    };
  }, [refreshCapabilities]);

  return useMemo(
    () => ({
      ...snapshot,
      pauseSync: () => {
        setSyncPaused(true);
        setSnapshot(loadSystemHealthSnapshot());
      },
      resumeSync: () => {
        setSyncPaused(false);
        setSnapshot(loadSystemHealthSnapshot());
      },
      retryAllFailed: async () => {
        localDb.requeueAllNeedsAttentionOps();
        try {
          await retryPendingRecordingTextSync();
          await retryAllLegacyUploadPseudoOps();
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryOne: async (opId: number) => {
        try {
          localDb.requeueOp(opId);
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryLegacyUploadOp: async (opId: string) => {
        try {
          await retryLegacyUploadPseudoOp(opId);
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryTaskConflict: async (taskId: string) => {
        try {
          const requeued = localDb.requeueNeedsAttentionOpsForEntity("task", taskId);
          if (requeued > 0) {
            await triggerSync();
          }
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      restoreTaskConflict: async (taskId: string) => {
        try {
          return localDb.restoreTaskFromServerShadow(taskId);
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      clearSafeArtifacts: async () => {
        const result = localDb.cleanupSafeSyncArtifacts();
        setSnapshot(loadSystemHealthSnapshot());
        return result;
      },
      setRuntimeFlag: async (name: RuntimeFlagName, enabled: boolean) => {
        await setRuntimeFlag(name, enabled);
        setSnapshot(loadSystemHealthSnapshot());
      },
      refresh: () => setSnapshot(loadSystemHealthSnapshot()),
      exportDiagnostics: async () => {
        const nextSnapshot = loadSystemHealthSnapshot();
        try {
          const capabilities = await fetchMobileCapabilities();
          nextSnapshot.backendCapabilities = capabilities;
          nextSnapshot.backendCapabilitiesError = null;
        } catch (error) {
          nextSnapshot.backendCapabilitiesError = error instanceof Error ? error.message : "能力探测失败";
          nextSnapshot.backendCapabilities = null;
        }
        nextSnapshot.backendBaseUrl = getBaseUrl();
        nextSnapshot.lastCapabilityProbeAt = new Date().toISOString();
        setSnapshot(nextSnapshot);
        return exportSystemHealthDiagnosticBundle(nextSnapshot);
      },
      refreshBackendCapabilities: async () => {
        await refreshCapabilities();
      },
    }),
    [refreshCapabilities, snapshot],
  );
}
