import * as localDb from "./local-db";
import {
  buildLegacyUploadPseudoOp,
  normalizeLegacyUploadReasonCode,
  normalizeLegacyUploadStatus,
  refreshLegacyUploadPseudoOpAge,
} from "./legacy-upload-pseudo-op-core";
import type { LegacyUploadPseudoOp, LegacyUploadPseudoOpStatus, LegacyUploadReasonCode } from "./types";

const LEGACY_UPLOAD_OPS_KEY = "legacy_upload_ops_v1";

type StoredLegacyUploadPseudoOp = Omit<LegacyUploadPseudoOp, "ageMs">;

function loadStoredLegacyUploadOps(): StoredLegacyUploadPseudoOp[] {
  const raw = localDb.getSyncMeta(LEGACY_UPLOAD_OPS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is StoredLegacyUploadPseudoOp => {
      return Boolean(
        item &&
          typeof item.opId === "string" &&
          typeof item.objectType === "string" &&
          typeof item.objectLocalId === "string" &&
          item.lane === "transfer" &&
          typeof item.taskLocalId === "string" &&
          typeof item.filePath === "string",
      );
    });
  } catch {
    return [];
  }
}

function saveStoredLegacyUploadOps(items: readonly StoredLegacyUploadPseudoOp[]): void {
  localDb.setSyncMeta(LEGACY_UPLOAD_OPS_KEY, JSON.stringify(items));
}

export function getLegacyUploadPseudoOps(now = Date.now()): LegacyUploadPseudoOp[] {
  return loadStoredLegacyUploadOps().map((item) =>
    refreshLegacyUploadPseudoOpAge(
      {
        ...item,
        status: normalizeLegacyUploadStatus(item.status),
        reasonCode: normalizeLegacyUploadReasonCode(item.reasonCode),
      },
      now,
    ),
  );
}

export function getLegacyUploadPseudoOp(opId: string): LegacyUploadPseudoOp | null {
  return getLegacyUploadPseudoOps().find((item) => item.opId === opId) ?? null;
}

export function upsertLegacyUploadPseudoOp(
  input: StoredLegacyUploadPseudoOp,
): LegacyUploadPseudoOp {
  const next = buildLegacyUploadPseudoOp({
    ...input,
    status: normalizeLegacyUploadStatus(input.status),
    reasonCode: normalizeLegacyUploadReasonCode(input.reasonCode),
  });
  const existing = loadStoredLegacyUploadOps().filter((item) => item.opId !== next.opId);
  const { ageMs: _ageMs, ...stored } = next;
  existing.unshift(stored);
  saveStoredLegacyUploadOps(existing);
  return next;
}

export function patchLegacyUploadPseudoOp(
  opId: string,
  patch: Partial<Omit<StoredLegacyUploadPseudoOp, "opId" | "createdAt" | "objectType" | "objectLocalId" | "taskLocalId" | "filePath" | "entityRefLocalId">>,
): LegacyUploadPseudoOp | null {
  const items = loadStoredLegacyUploadOps();
  const index = items.findIndex((item) => item.opId === opId);
  if (index === -1) {
    return null;
  }
  const current = items[index];
  const next: StoredLegacyUploadPseudoOp = {
    ...current,
    ...patch,
    status: normalizeLegacyUploadStatus((patch.status as string | undefined) ?? current.status),
    reasonCode: normalizeLegacyUploadReasonCode((patch.reasonCode as string | undefined) ?? current.reasonCode),
  };
  items[index] = next;
  saveStoredLegacyUploadOps(items);
  return buildLegacyUploadPseudoOp(next);
}

export function markLegacyUploadPseudoOp(
  opId: string,
  params: {
    status: LegacyUploadPseudoOpStatus;
    reasonCode: LegacyUploadReasonCode;
    incrementRetryCount?: boolean;
  },
): LegacyUploadPseudoOp | null {
  const existing = getLegacyUploadPseudoOp(opId);
  if (!existing) {
    return null;
  }
  return patchLegacyUploadPseudoOp(opId, {
    status: params.status,
    reasonCode: params.reasonCode,
    lastAttemptAt: new Date().toISOString(),
    retryCount: params.incrementRetryCount ? existing.retryCount + 1 : existing.retryCount,
  });
}

export function removeLegacyUploadPseudoOp(opId: string): void {
  const next = loadStoredLegacyUploadOps().filter((item) => item.opId !== opId);
  saveStoredLegacyUploadOps(next);
}
