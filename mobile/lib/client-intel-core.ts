import type { ClientWorkspaceLiteStatus } from "./types";

export type ClientIntelSourceName = "workspace" | "strategic_cockpit";

export interface ClientIntelSourceState {
  source: ClientIntelSourceName;
  ok: boolean;
  status?: "rich" | "partial" | "missing" | "ready" | "unavailable" | string | null;
  missingSources?: readonly string[] | null;
  updatedAt?: string | null;
}

export interface ClientIntelAvailability {
  status: ClientWorkspaceLiteStatus;
  availableSources: string[];
  missingSources: string[];
  staleSources: string[];
  sourceUpdatedAt: Record<string, string | null>;
}

function normalizeMissingSource(source: string): string {
  if (source === "cockpit") {
    return "strategic_cockpit";
  }
  return source;
}

export function deriveClientIntelAvailability(
  sources: readonly ClientIntelSourceState[],
): ClientIntelAvailability {
  const availableSources = new Set<string>();
  const missingSources = new Set<string>();
  const staleSources = new Set<string>();
  const sourceUpdatedAt: Record<string, string | null> = {};

  for (const source of sources) {
    sourceUpdatedAt[source.source] = source.updatedAt ?? null;
    const sourceStatus = source.status ?? null;
    const isAvailable =
      source.ok &&
      sourceStatus !== "missing" &&
      sourceStatus !== "unavailable";

    if (isAvailable) {
      availableSources.add(source.source);
    } else {
      missingSources.add(source.source);
    }

    for (const missing of source.missingSources ?? []) {
      missingSources.add(normalizeMissingSource(missing));
    }

    if (source.ok && !source.updatedAt && isAvailable) {
      staleSources.add(source.source);
    }
  }

  const availableCount = availableSources.size;
  const status: ClientWorkspaceLiteStatus =
    availableCount === 0
      ? "missing"
      : availableCount === sources.length
        ? "rich"
        : "partial";

  return {
    status,
    availableSources: [...availableSources].sort(),
    missingSources: [...missingSources].sort(),
    staleSources: [...staleSources].sort(),
    sourceUpdatedAt,
  };
}
