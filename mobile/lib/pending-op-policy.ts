import type {
  PendingOpLane,
  PendingOpOperation,
  PendingOpVisibilityScope,
  RemoteMutationState,
} from "./types";

export interface PendingOpDraft {
  clientOpId: string;
  entityType: string;
  entityId: string;
  entityRemoteId?: string | null;
  operation: PendingOpOperation;
  payload: Record<string, unknown> | null;
  lane: PendingOpLane;
  status: RemoteMutationState;
  visibilityScope: PendingOpVisibilityScope;
  localVersion: number;
  baseRemoteVersion?: number | null;
}

function mergePayload(
  first: Record<string, unknown> | null,
  second: Record<string, unknown> | null,
): Record<string, unknown> | null {
  if (!first && !second) return null;
  return {
    ...(first ?? {}),
    ...(second ?? {}),
  };
}

export function foldPendingOps(
  existing: readonly PendingOpDraft[],
  next: PendingOpDraft,
): PendingOpDraft[] {
  const current = [...existing];
  const last = current[current.length - 1] ?? null;

  if (!last) {
    return [next];
  }

  if (last.operation === "create" && next.operation === "update") {
    return [
      {
        ...last,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  if (last.operation === "create" && next.operation === "complete_with_review") {
    return [...current, next];
  }

  if (last.operation === "create" && next.operation === "delete") {
    return last.entityRemoteId ? [{ ...next, entityRemoteId: last.entityRemoteId }] : [];
  }

  if (last.operation === "update" && next.operation === "update") {
    return [
      {
        ...last,
        clientOpId: next.clientOpId,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  if (last.operation === "update" && next.operation === "complete_with_review") {
    return [...current, next];
  }

  if (last.operation === "update" && next.operation === "delete") {
    return [next];
  }

  if (last.operation === "delete" && next.operation === "update") {
    return current;
  }

  if (last.operation === "complete_with_review" && next.operation === "update") {
    const base = current.slice(0, -1);
    const foldedBase = foldPendingOps(base, next);
    return foldedBase.length > 0
      ? [
          ...foldedBase,
          {
            ...last,
            localVersion: next.localVersion,
          },
        ]
      : [next, last];
  }

  if (last.operation === "complete_with_review" && next.operation === "complete_with_review") {
    return [
      ...current.slice(0, -1),
      {
        ...last,
        clientOpId: next.clientOpId,
        entityRemoteId: next.entityRemoteId ?? last.entityRemoteId ?? null,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  return [next];
}

export function comparePendingOpLanePriority(a: PendingOpLane, b: PendingOpLane): number {
  const weights: Record<PendingOpLane, number> = {
    interactive: 0,
    transfer: 1,
    derived: 2,
  };
  return weights[a] - weights[b];
}
