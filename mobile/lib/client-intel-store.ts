import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, fetchClientUnderstanding, fetchClientWorkspace, fetchStrategicCockpit } from "./api";
import { buildBoundaryCards } from "./boundary-cards";
import {
  deriveClientIntelAvailability,
  type ClientIntelAvailability,
  type ClientIntelSourceName,
  type ClientIntelSourceState,
} from "./client-intel-core";
import { deriveBoundaryState } from "./current-focus-core";
import * as localDb from "./local-db";
import { buildScopedStorageKey, resolveScopedStorageNamespace } from "./scope-storage-core";
import type {
  ClientUnderstandingSnapshot,
  ClientWorkspaceLiteSnapshot,
  WorkspaceLiteItem,
  WorkspaceLiteTaskItem,
} from "./types";

const CACHE_PREFIX = "client_intel_v1:";
const memoryCache = new Map<string, ClientWorkspaceLiteSnapshot>();

function buildClientIntelStorageKey(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): string {
  return buildScopedStorageKey(CACHE_PREFIX, clientId, scopeKey);
}

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

function pickSummaryItem(item: any, fallbackTitle: string): WorkspaceLiteItem {
  return {
    id: toText(item?.id || item?.meetingId || item?.documentId || fallbackTitle),
    title: toText(item?.title || item?.label || item?.name || fallbackTitle),
    summary: toText(item?.summary || item?.description || item?.note || item?.statusLabel || ""),
    subtitle: toText(item?.quarter || item?.updatedAt || item?.meetingDate || item?.sourceType || ""),
    updatedAt: item?.updatedAt ?? item?.createdAt ?? null,
  };
}

function pickTaskItem(item: any): WorkspaceLiteTaskItem {
  return {
    id: toText(item?.id),
    title: toText(item?.title || item?.name || "未命名任务"),
    status: toText(item?.status || item?.progressStatus || ""),
    clientName: item?.clientName ?? null,
    eventLineName: item?.eventLineName ?? null,
  };
}

function pickHeadline(cockpit: any): string | null {
  const headline = cockpit?.headline;
  if (!headline) {
    return null;
  }
  return (
    toText(headline.summary || headline.mainSummary || headline.primaryStatement || headline.title) ||
    null
  );
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => toText(item)).filter(Boolean)
    : [];
}

function sourceStateFromSettled(
  source: ClientIntelSourceName,
  result: PromiseSettledResult<Record<string, unknown>>,
): ClientIntelSourceState {
  if (result.status === "fulfilled") {
    const payload: any = result.value ?? {};
    return {
      source,
      ok: true,
      status: toText(payload.status) || "rich",
      missingSources: stringArray(payload.missingSources),
      updatedAt: payload.updatedAt ?? payload.client?.updatedAt ?? null,
    };
  }
  return {
    source,
    ok: false,
    status: "unavailable",
    missingSources: [source],
    updatedAt: null,
  };
}

function isBlockingSourceFailure(result: PromiseSettledResult<unknown>): boolean {
  return (
    result.status === "rejected" &&
    result.reason instanceof ApiError &&
    (result.reason.status === 401 || result.reason.status === 403)
  );
}

function adaptClientWorkspaceLite(
  clientId: string,
  workspace: any,
  cockpit: any,
  availability: ClientIntelAvailability = deriveClientIntelAvailability([
    { source: "workspace", ok: Boolean(workspace), status: workspace?.status ?? "missing", missingSources: workspace?.missingSources ?? [], updatedAt: workspace?.updatedAt ?? null },
    { source: "strategic_cockpit", ok: Boolean(cockpit), status: cockpit?.status ?? "missing", missingSources: cockpit?.missingSources ?? [], updatedAt: cockpit?.updatedAt ?? null },
  ]),
  understanding: ClientUnderstandingSnapshot | null = null,
): ClientWorkspaceLiteSnapshot {
  const boundaryCards = buildBoundaryCards(workspace, cockpit);
  return {
    clientId,
    clientName: toText(workspace?.client?.name || cockpit?.clientName || "客户"),
    status: availability.status,
    availableSources: availability.availableSources,
    missingSources: availability.missingSources,
    staleSources: availability.staleSources,
    sourceUpdatedAt: availability.sourceUpdatedAt,
    boundaryCards,
    boundaryState: deriveBoundaryState(boundaryCards),
    goals: Array.isArray(workspace?.goals) ? workspace.goals.slice(0, 4).map((item: any) => pickSummaryItem(item, "目标")) : [],
    latestMeetings: Array.isArray(workspace?.meetings) ? workspace.meetings.slice(0, 4).map((item: any) => pickSummaryItem(item, "会议")) : [],
    knowledgeStatus:
      toText(workspace?.knowledgeStatus?.summary || workspace?.knowledgeStatus?.statusLabel || workspace?.knowledgeStatus?.status) || null,
    recentDocuments: Array.isArray(workspace?.documentCards)
      ? workspace.documentCards.slice(0, 4).map((item: any) => pickSummaryItem(item, "资料"))
      : Array.isArray(workspace?.documents)
        ? workspace.documents.slice(0, 4).map((item: any) => pickSummaryItem(item, "资料"))
        : [],
    openQuestions: Array.isArray(workspace?.latestOpenQuestions)
      ? workspace.latestOpenQuestions.slice(0, 4).map((item: any) => pickSummaryItem(item, "开放问题"))
      : [],
    conflicts: Array.isArray(workspace?.latestConflicts)
      ? workspace.latestConflicts.slice(0, 4).map((item: any) => pickSummaryItem(item, "冲突"))
      : [],
    relatedTasks: Array.isArray(workspace?.relatedTasks)
      ? workspace.relatedTasks.slice(0, 6).map((item: any) => pickTaskItem(item))
      : [],
    nextActions: [
      ...(Array.isArray(cockpit?.pendingDecisions)
        ? cockpit.pendingDecisions.map((item: any) => toText(item?.summary || item?.title || item?.label))
        : []),
      ...(Array.isArray(workspace?.relatedTasks)
        ? workspace.relatedTasks
            .map((item: any) => toText(item?.nextAction || item?.title))
            .filter(Boolean)
            .slice(0, 2)
        : []),
    ].filter(Boolean).slice(0, 5),
    headline: pickHeadline(cockpit),
    health: Array.isArray(cockpit?.health)
      ? cockpit.health.map((item: any) => toText(item?.summary || item?.label || item?.value)).filter(Boolean).slice(0, 4)
      : [],
    twoWeekChanges: Array.isArray(cockpit?.twoWeekChanges)
      ? cockpit.twoWeekChanges.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    pendingDecisions: Array.isArray(cockpit?.pendingDecisions)
      ? cockpit.pendingDecisions.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    pendingMaterials: Array.isArray(cockpit?.pendingMaterials)
      ? cockpit.pendingMaterials.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    updatedAt: cockpit?.updatedAt ?? workspace?.client?.updatedAt ?? new Date().toISOString(),
    understanding: understanding && understanding.status !== "missing" ? understanding : null,
  };
}

async function loadCachedSnapshot(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<ClientWorkspaceLiteSnapshot | null> {
  const storageKey = buildClientIntelStorageKey(clientId, scopeKey);
  if (memoryCache.has(storageKey)) {
    return memoryCache.get(storageKey) ?? null;
  }
  const rawValue = await AsyncStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawValue) as ClientWorkspaceLiteSnapshot;
    memoryCache.set(storageKey, parsed);
    return parsed;
  } catch {
    return null;
  }
}

async function fetchLiveSnapshot(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<ClientWorkspaceLiteSnapshot> {
  const [workspaceResult, cockpitResult, understandingResult] = await Promise.allSettled([
    fetchClientWorkspace(clientId),
    fetchStrategicCockpit(clientId),
    fetchClientUnderstanding(clientId),
  ]);
  // understanding 只是丰富 prompt 用的可选数据源——服务端不存在（旧后端、404）、
  // 权限不足（401/403）都不应该拖垮 workspace+cockpit 的主流程，所以它不参与
  // blocking 检查，单独降级为 null。
  if (isBlockingSourceFailure(workspaceResult) || isBlockingSourceFailure(cockpitResult)) {
    throw (
      workspaceResult.status === "rejected"
        ? workspaceResult.reason
        : cockpitResult.status === "rejected"
          ? cockpitResult.reason
          : new Error("工作台权限不足")
    );
  }
  const workspace = workspaceResult.status === "fulfilled" ? workspaceResult.value : null;
  const cockpit = cockpitResult.status === "fulfilled" ? cockpitResult.value : null;
  const understanding =
    understandingResult.status === "fulfilled" ? understandingResult.value : null;
  const availability = deriveClientIntelAvailability([
    sourceStateFromSettled("workspace", workspaceResult),
    sourceStateFromSettled("strategic_cockpit", cockpitResult),
  ]);
  const snapshot = adaptClientWorkspaceLite(clientId, workspace, cockpit, availability, understanding);
  const storageKey = buildClientIntelStorageKey(clientId, scopeKey);
  memoryCache.set(storageKey, snapshot);
  await AsyncStorage.setItem(storageKey, JSON.stringify(snapshot));
  return snapshot;
}

export async function clearClientIntelCache(options?: {
  scopeKey?: string | null;
  allScopes?: boolean;
}): Promise<void> {
  if (options?.allScopes) {
    memoryCache.clear();
    const allKeys = await AsyncStorage.getAllKeys();
    const cachedKeys = allKeys.filter((item) => item.startsWith(CACHE_PREFIX));
    if (cachedKeys.length > 0) {
      await AsyncStorage.multiRemove(cachedKeys);
    }
    return;
  }

  const scopePrefix = `${CACHE_PREFIX}${resolveScopedStorageNamespace(
    options?.scopeKey ?? localDb.getActiveAccountScopeKey(),
  )}:`;
  for (const key of [...memoryCache.keys()]) {
    if (key.startsWith(scopePrefix)) {
      memoryCache.delete(key);
    }
  }
  const allKeys = await AsyncStorage.getAllKeys();
  const cachedKeys = allKeys.filter((item) => item.startsWith(scopePrefix));
  if (cachedKeys.length > 0) {
    await AsyncStorage.multiRemove(cachedKeys);
  }
}

export function useClientIntel(clientId: string | null | undefined) {
  const [snapshot, setSnapshot] = useState<ClientWorkspaceLiteSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!clientId) {
      setSnapshot(null);
      setError(null);
      return null;
    }
    const scopeKey = localDb.getActiveAccountScopeKey();
    setIsRefreshing(true);
    try {
      const next = await fetchLiveSnapshot(clientId, scopeKey);
      setSnapshot(next);
      setError(null);
      return next;
    } catch (currentError) {
      setError(currentError instanceof Error ? currentError.message : "工作台加载失败");
      return null;
    } finally {
      setIsRefreshing(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (!clientId) {
      setSnapshot(null);
      setIsLoading(false);
      setError(null);
      return;
    }
    let cancelled = false;
    const scopeKey = localDb.getActiveAccountScopeKey();
    setIsLoading(true);
    void loadCachedSnapshot(clientId, scopeKey)
      .then((cached) => {
        if (cancelled) {
          return;
        }
        if (cached) {
          setSnapshot(cached);
          setIsLoading(false);
        }
        return fetchLiveSnapshot(clientId, scopeKey);
      })
      .then((live) => {
        if (!cancelled && live) {
          setSnapshot(live);
          setError(null);
        }
      })
      .catch((currentError) => {
        if (!cancelled) {
          setError(currentError instanceof Error ? currentError.message : "工作台加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  return useMemo(
    () => ({
      snapshot,
      isLoading,
      isRefreshing,
      error,
      refresh,
    }),
    [error, isLoading, isRefreshing, refresh, snapshot],
  );
}
