import type { ClientSummaryRecord, EventLineRecord } from "./types";

export type AssociationSource = "default" | "auto" | "manual";

export interface ProjectOption {
  id: string;
  name: string;
  clientId: string | null;
  eventLineIds: string[];
}

export function normalizeSearchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[\s·•,，。！？、:：;；"'“”‘’（）()【】[\]{}<>《》\-_/\\]+/g, "")
    .trim();
}

export function splitSearchFragments(value: string): string[] {
  return value
    .split(/[\s·•,，。！？、:：;；"'“”‘’（）()【】[\]{}<>《》\-_/\\]+/g)
    .map((item) => item.trim())
    .filter((item) => item.length >= 2);
}

export function deriveProjectLabel(eventLine: EventLineRecord): string {
  if (eventLine.primaryClientName?.trim()) {
    return eventLine.primaryClientName.trim();
  }
  const [firstSegment] = eventLine.name.split(/[·•|｜/]/);
  const compact = firstSegment?.trim() || eventLine.name.trim();
  const [firstWord] = compact.split(/\s+/);
  return firstWord?.trim() || compact;
}

export function getProjectKey(eventLine: EventLineRecord): string {
  if (eventLine.primaryClientId) {
    return `client:${eventLine.primaryClientId}`;
  }
  const derived = normalizeSearchText(deriveProjectLabel(eventLine));
  return `event-line:${derived || eventLine.id}`;
}

export function scoreEventLineMatch(searchKey: string, eventLine: EventLineRecord): number {
  if (!searchKey || searchKey.length < 2) {
    return 0;
  }

  const aliases = new Set<string>([
    eventLine.name,
    eventLine.primaryClientName ?? "",
    deriveProjectLabel(eventLine),
    ...splitSearchFragments(eventLine.name),
    ...splitSearchFragments(eventLine.primaryClientName ?? ""),
  ]);

  let bestScore = 0;
  for (const alias of aliases) {
    const normalized = normalizeSearchText(alias);
    if (normalized.length < 2) {
      continue;
    }

    if (searchKey === normalized) {
      bestScore = Math.max(bestScore, 320 + normalized.length);
      continue;
    }
    if (searchKey.includes(normalized)) {
      bestScore = Math.max(bestScore, 220 + normalized.length);
      continue;
    }
    if (normalized.includes(searchKey) && searchKey.length >= 3) {
      bestScore = Math.max(bestScore, 120 + searchKey.length);
    }
  }

  return bestScore;
}

export function scoreClientMatch(searchKey: string, client: ClientSummaryRecord): number {
  if (!searchKey || searchKey.length < 2) {
    return 0;
  }
  const aliases = new Set<string>([
    client.name,
    client.alias ?? "",
    ...splitSearchFragments(client.name),
  ]);
  let bestScore = 0;
  for (const alias of aliases) {
    const normalized = normalizeSearchText(alias);
    if (normalized.length < 2) {
      continue;
    }
    if (searchKey === normalized) {
      bestScore = Math.max(bestScore, 320 + normalized.length);
      continue;
    }
    if (searchKey.includes(normalized)) {
      bestScore = Math.max(bestScore, 220 + normalized.length);
      continue;
    }
    if (normalized.includes(searchKey) && searchKey.length >= 3) {
      bestScore = Math.max(bestScore, 120 + searchKey.length);
    }
  }
  return bestScore;
}

// 标题/描述没命中事件线时，退而匹配客户/组织（用户自己组织的同名客户也走这里命中）。
export function findAutoMatchedClient(
  searchKey: string,
  clients: readonly ClientSummaryRecord[],
): ClientSummaryRecord | null {
  if (searchKey.length < 2) {
    return null;
  }
  let bestMatch: ClientSummaryRecord | null = null;
  let bestScore = 0;
  for (const client of clients) {
    const score = scoreClientMatch(searchKey, client);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = client;
    }
  }
  return bestScore >= 122 ? bestMatch : null;
}

export function buildProjectOptions(
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): ProjectOption[] {
  if (clients.length > 0) {
    return clients.map((client) => ({
      id: `client:${client.id}`,
      name: client.name,
      clientId: client.id,
      eventLineIds: eventLines
        .filter((eventLine) => eventLine.primaryClientId === client.id)
        .map((eventLine) => eventLine.id),
    }));
  }

  const map = new Map<string, ProjectOption>();
  for (const eventLine of eventLines) {
    const key = getProjectKey(eventLine);
    const existing = map.get(key);
    if (existing) {
      if (!existing.eventLineIds.includes(eventLine.id)) {
        existing.eventLineIds.push(eventLine.id);
      }
      if (!existing.clientId && eventLine.primaryClientId) {
        existing.clientId = eventLine.primaryClientId;
      }
      continue;
    }
    map.set(key, {
      id: key,
      name: deriveProjectLabel(eventLine),
      clientId: eventLine.primaryClientId ?? null,
      eventLineIds: [eventLine.id],
    });
  }
  return Array.from(map.values()).sort((left, right) => left.name.localeCompare(right.name, "zh-Hans-CN"));
}

export function filterEventLinesForSelection(
  eventLines: readonly EventLineRecord[],
  selectedClientId: string | null,
  selectedProjectKey: string | null,
): EventLineRecord[] {
  if (selectedClientId) {
    return eventLines.filter((eventLine) => eventLine.primaryClientId === selectedClientId);
  }
  if (!selectedProjectKey) {
    return [...eventLines];
  }
  return eventLines.filter((eventLine) => getProjectKey(eventLine) === selectedProjectKey);
}

export function findAutoMatchedEventLine(
  titleSearchKey: string,
  eventLines: readonly EventLineRecord[],
): EventLineRecord | null {
  if (titleSearchKey.length < 2) {
    return null;
  }

  let bestMatch: EventLineRecord | null = null;
  let bestScore = 0;

  for (const eventLine of eventLines) {
    const score = scoreEventLineMatch(titleSearchKey, eventLine);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = eventLine;
    }
  }

  return bestScore >= 122 ? bestMatch : null;
}

export function shouldApplyAutoAssociation(options: {
  source: AssociationSource;
  lockedTitleKey: string | null;
  titleSearchKey: string;
  selectedEventLineId: string | null;
  autoMatchedEventLineId: string | null;
}): boolean {
  if (!options.autoMatchedEventLineId) {
    return false;
  }
  if (options.source === "manual") {
    return false;
  }
  if (options.lockedTitleKey === options.titleSearchKey) {
    return false;
  }
  return options.selectedEventLineId !== options.autoMatchedEventLineId;
}
