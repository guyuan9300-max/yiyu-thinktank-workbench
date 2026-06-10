import {
  buildWeekInfo,
  parseLocalDateKey,
  weekLabelForDateKey,
} from "./date";
import type {
  BoundaryCard,
  CurrentFocus,
  CurrentFocusBoundaryState,
  CurrentFocusLockMode,
  CurrentFocusSource,
  ClientSummaryRecord,
  EventLineRecord,
  TaskRecord,
} from "./types";

interface FocusSeed {
  readonly clientId?: string | null;
  readonly clientName?: string | null;
  readonly eventLineId?: string | null;
  readonly eventLineName?: string | null;
  readonly taskId?: string | null;
  readonly taskTitle?: string | null;
  readonly source?: CurrentFocusSource;
  readonly lockMode?: CurrentFocusLockMode;
  readonly boundaryState?: CurrentFocusBoundaryState;
  readonly weekAnchorDate?: string | null;
  readonly updatedAt?: string | null;
}

interface RestoreOptions {
  readonly now?: Date;
  readonly clients?: readonly ClientSummaryRecord[];
  readonly eventLines?: readonly EventLineRecord[];
}

export function createEmptyCurrentFocus(now = new Date()): CurrentFocus {
  const week = buildWeekInfo(now);
  return {
    clientId: null,
    clientName: null,
    eventLineId: null,
    eventLineName: null,
    taskId: null,
    taskTitle: null,
    weekAnchorDate: week.weekAnchorDate,
    weekLabel: week.weekLabel,
    source: "auto",
    lockMode: "browse",
    boundaryState: "none",
    updatedAt: now.toISOString(),
  };
}

export function createCurrentFocus(seed: FocusSeed = {}, now = new Date()): CurrentFocus {
  const base = createEmptyCurrentFocus(now);
  const weekAnchorDate = seed.weekAnchorDate ?? base.weekAnchorDate;
  return {
    clientId: seed.clientId ?? null,
    clientName: seed.clientName ?? null,
    eventLineId: seed.eventLineId ?? null,
    eventLineName: seed.eventLineName ?? null,
    taskId: seed.taskId ?? null,
    taskTitle: seed.taskTitle ?? null,
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
    source: seed.source ?? base.source,
    lockMode: seed.lockMode ?? base.lockMode,
    boundaryState: seed.boundaryState ?? "none",
    updatedAt: seed.updatedAt ?? now.toISOString(),
  };
}

export function createManualClientFocus(
  client: Pick<ClientSummaryRecord, "id" | "name">,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: client.id,
    clientName: client.name,
    eventLineId: null,
    eventLineName: null,
    taskId: null,
    taskTitle: null,
    source: "manual",
    lockMode: "client",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createManualClientEventLineFocus(
  client: Pick<ClientSummaryRecord, "id" | "name">,
  eventLine: Pick<EventLineRecord, "id" | "name">,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: client.id,
    clientName: client.name,
    eventLineId: eventLine.id,
    eventLineName: eventLine.name,
    taskId: null,
    taskTitle: null,
    source: "manual",
    lockMode: "client_event_line",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromTask(task: TaskRecord, currentFocus?: CurrentFocus | null): CurrentFocus {
  return createCurrentFocus({
    clientId: task.clientId ?? null,
    clientName: task.clientName ?? null,
    eventLineId: task.eventLineId ?? null,
    eventLineName: task.eventLineName ?? null,
    taskId: task.id,
    taskTitle: task.title ?? null,
    source: "from_task",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromEventLine(
  eventLine: EventLineRecord,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: eventLine.primaryClientId ?? null,
    clientName: eventLine.primaryClientName ?? null,
    eventLineId: eventLine.id,
    eventLineName: eventLine.name,
    taskId: null,
    taskTitle: null,
    source: "from_task",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromCalendar(task: TaskRecord, currentFocus?: CurrentFocus | null): CurrentFocus {
  return createCurrentFocus({
    clientId: task.clientId ?? null,
    clientName: task.clientName ?? null,
    eventLineId: task.eventLineId ?? null,
    eventLineName: task.eventLineName ?? null,
    taskId: task.id,
    taskTitle: task.title ?? null,
    source: "from_calendar",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function updateCurrentFocusWeek(
  currentFocus: CurrentFocus,
  weekAnchorDate: string,
): CurrentFocus {
  return {
    ...currentFocus,
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
    updatedAt: new Date().toISOString(),
  };
}

export function updateCurrentFocusBoundaryState(
  currentFocus: CurrentFocus,
  boundaryState: CurrentFocusBoundaryState,
): CurrentFocus {
  if (currentFocus.boundaryState === boundaryState) {
    return currentFocus;
  }
  return {
    ...currentFocus,
    boundaryState,
    updatedAt: new Date().toISOString(),
  };
}

export function clearCurrentFocus(currentFocus?: CurrentFocus | null): CurrentFocus {
  const seedDate = currentFocus?.weekAnchorDate ? parseLocalDateKey(currentFocus.weekAnchorDate) : new Date();
  return createCurrentFocus({
    source: "manual",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  }, seedDate);
}

export function canPersistCurrentFocus(currentFocus: CurrentFocus): boolean {
  return currentFocus.lockMode !== "browse" && Boolean(currentFocus.clientId);
}

export function serializeCurrentFocus(currentFocus: CurrentFocus): string | null {
  if (!canPersistCurrentFocus(currentFocus)) {
    return null;
  }
  return JSON.stringify(currentFocus);
}

function ensureClient(
  currentFocus: CurrentFocus,
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): CurrentFocus {
  if (!currentFocus.clientId) {
    return currentFocus;
  }
  const matchedClient = clients.find((client) => client.id === currentFocus.clientId);
  if (matchedClient) {
    return {
      ...currentFocus,
      clientName: matchedClient.name,
    };
  }
  if (currentFocus.eventLineId) {
    const matchedEventLine = eventLines.find((line) => line.id === currentFocus.eventLineId);
    if (matchedEventLine?.primaryClientId && matchedEventLine.primaryClientName) {
      return {
        ...currentFocus,
        clientId: matchedEventLine.primaryClientId,
        clientName: matchedEventLine.primaryClientName,
      };
    }
  }
  return clearCurrentFocus(currentFocus);
}

export function reconcileCurrentFocus(
  currentFocus: CurrentFocus,
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): CurrentFocus {
  let next = ensureClient(currentFocus, clients, eventLines);
  if (next.eventLineId) {
    const matchedEventLine = eventLines.find((line) => line.id === next.eventLineId);
    if (!matchedEventLine) {
      next = {
        ...next,
        eventLineId: null,
        eventLineName: null,
        lockMode: next.lockMode === "client_event_line" ? "client" : next.lockMode,
      };
    } else {
      next = {
        ...next,
        eventLineName: matchedEventLine.name,
        clientId: matchedEventLine.primaryClientId ?? next.clientId ?? null,
        clientName: matchedEventLine.primaryClientName ?? next.clientName ?? null,
      };
    }
  }
  return {
    ...next,
    weekLabel: weekLabelForDateKey(next.weekAnchorDate),
  };
}

export function restoreCurrentFocus(
  rawValue: string | null | undefined,
  options: RestoreOptions = {},
): CurrentFocus {
  const fallback = createEmptyCurrentFocus(options.now);
  if (!rawValue) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(rawValue) as Partial<CurrentFocus>;
    const restored = createCurrentFocus({
      clientId: parsed.clientId,
      clientName: parsed.clientName,
      eventLineId: parsed.eventLineId,
      eventLineName: parsed.eventLineName,
      taskId: parsed.taskId,
      taskTitle: parsed.taskTitle,
      source: parsed.source,
      lockMode: parsed.lockMode,
      boundaryState: parsed.boundaryState,
      weekAnchorDate: parsed.weekAnchorDate,
      updatedAt: parsed.updatedAt,
    }, options.now);
    return reconcileCurrentFocus(restored, options.clients ?? [], options.eventLines ?? []);
  } catch {
    return fallback;
  }
}

export function deriveBoundaryState(cards: readonly BoundaryCard[]): CurrentFocusBoundaryState {
  const nonEmptyKinds = Array.from(
    new Set(cards.filter((card) => !card.isEmpty).map((card) => card.kind)),
  );
  if (nonEmptyKinds.length === 0) {
    return "none";
  }
  if (nonEmptyKinds.length === 1) {
    return nonEmptyKinds[0];
  }
  return "mixed";
}
