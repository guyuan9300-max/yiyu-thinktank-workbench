import { useEffect, useMemo, useSyncExternalStore } from "react";
import * as storage from "./storage";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import { onDataChanged } from "./sync-engine";
import {
  clearCurrentFocus,
  createBrowseFocusFromCalendar,
  createBrowseFocusFromEventLine,
  createBrowseFocusFromTask,
  createEmptyCurrentFocus,
  createManualClientEventLineFocus,
  createManualClientFocus,
  reconcileCurrentFocus,
  restoreCurrentFocus,
  serializeCurrentFocus,
  updateCurrentFocusBoundaryState as applyBoundaryState,
  updateCurrentFocusWeek as applyWeekUpdate,
} from "./current-focus-core";
import type {
  ClientSummaryRecord,
  CurrentFocus,
  CurrentFocusBoundaryState,
  EventLineRecord,
  TaskRecord,
} from "./types";

const STORAGE_KEY = "yiyu_current_focus";

interface CurrentFocusStoreSnapshot {
  readonly focus: CurrentFocus;
  readonly clients: readonly ClientSummaryRecord[];
  readonly eventLines: readonly EventLineRecord[];
  readonly isHydrated: boolean;
}

let snapshot: CurrentFocusStoreSnapshot = {
  focus: createEmptyCurrentFocus(),
  clients: [],
  eventLines: [],
  isHydrated: false,
};
let initializePromise: Promise<void> | null = null;
let releaseDataChanged: (() => void) | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function readCatalogs() {
  localDb.initDatabase();
  return {
    clients: localDb.getAllClients(),
    eventLines: localDb.getAllEventLines(),
  };
}

async function persistFocus(nextFocus: CurrentFocus) {
  const serialized = serializeCurrentFocus(nextFocus);
  const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
  if (!serialized) {
    await storage.deleteItem(storageKey);
    return;
  }
  await storage.setItem(storageKey, serialized);
}

function setSnapshot(nextSnapshot: CurrentFocusStoreSnapshot) {
  snapshot = nextSnapshot;
  emit();
}

function setFocus(nextFocus: CurrentFocus) {
  const reconciled = reconcileCurrentFocus(nextFocus, snapshot.clients, snapshot.eventLines);
  setSnapshot({
    ...snapshot,
    focus: reconciled,
  });
  void persistFocus(reconciled);
  devLog("focus", "updated", {
    clientId: reconciled.clientId,
    eventLineId: reconciled.eventLineId,
    lockMode: reconciled.lockMode,
    source: reconciled.source,
    weekLabel: reconciled.weekLabel,
  });
}

function refreshCatalogsFromLocal() {
  const { clients, eventLines } = readCatalogs();
  const nextFocus = reconcileCurrentFocus(snapshot.focus, clients, eventLines);
  setSnapshot({
    focus: nextFocus,
    clients,
    eventLines,
    isHydrated: snapshot.isHydrated,
  });
  void persistFocus(nextFocus);
}

export async function ensureCurrentFocusStoreInitialized(): Promise<void> {
  if (snapshot.isHydrated) {
    return;
  }
  if (initializePromise) {
    return initializePromise;
  }
  initializePromise = (async () => {
    const { clients, eventLines } = readCatalogs();
    const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
    const stored = await storage.getItem(storageKey);
    const focus = restoreCurrentFocus(stored, { clients, eventLines });
    setSnapshot({
      focus,
      clients,
      eventLines,
      isHydrated: true,
    });
    if (!releaseDataChanged) {
      releaseDataChanged = onDataChanged(() => {
        refreshCatalogsFromLocal();
      });
    }
  })().finally(() => {
    initializePromise = null;
  });
  return initializePromise;
}

export function resetCurrentFocusStore(): void {
  const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
  setSnapshot({
    focus: createEmptyCurrentFocus(),
    clients: [],
    eventLines: [],
    isHydrated: false,
  });
  void storage.deleteItem(STORAGE_KEY);
  void storage.deleteItem(storageKey);
}

export function setManualClientFocus(clientId: string): void {
  const client = snapshot.clients.find((item) => item.id === clientId);
  if (!client) {
    return;
  }
  setFocus(createManualClientFocus(client, snapshot.focus));
}

export function setManualClientEventLineFocus(clientId: string, eventLineId: string): void {
  const client = snapshot.clients.find((item) => item.id === clientId);
  const eventLine = snapshot.eventLines.find((item) => item.id === eventLineId);
  if (!client || !eventLine) {
    return;
  }
  setFocus(createManualClientEventLineFocus(client, eventLine, snapshot.focus));
}

export function setCurrentFocusBrowseFromTask(task: TaskRecord): void {
  setFocus(createBrowseFocusFromTask(task, snapshot.focus));
}

export function setCurrentFocusBrowseFromCalendar(task: TaskRecord): void {
  setFocus(createBrowseFocusFromCalendar(task, snapshot.focus));
}

export function setCurrentFocusBrowseFromEventLine(eventLineId: string): void {
  const eventLine = snapshot.eventLines.find((item) => item.id === eventLineId);
  if (!eventLine) {
    return;
  }
  setFocus(createBrowseFocusFromEventLine(eventLine, snapshot.focus));
}

export function setCurrentFocusWeek(weekAnchorDate: string): void {
  setFocus(applyWeekUpdate(snapshot.focus, weekAnchorDate));
}

export function setCurrentFocusBoundaryState(boundaryState: CurrentFocusBoundaryState): void {
  setFocus(applyBoundaryState(snapshot.focus, boundaryState));
}

export function clearStoredCurrentFocus(): void {
  setFocus(clearCurrentFocus(snapshot.focus));
}

export function useCurrentFocus() {
  const state = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => snapshot,
    () => snapshot,
  );

  useEffect(() => {
    void ensureCurrentFocusStoreInitialized();
  }, []);

  return useMemo(
    () => ({
      ...state,
      setManualClientFocus,
      setManualClientEventLineFocus,
      setCurrentFocusBrowseFromTask,
      setCurrentFocusBrowseFromCalendar,
      setCurrentFocusBrowseFromEventLine,
      setCurrentFocusWeek,
      setCurrentFocusBoundaryState,
      clearStoredCurrentFocus,
    }),
    [state],
  );
}
