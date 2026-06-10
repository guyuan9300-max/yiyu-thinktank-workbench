import type {
  HealthLaneDiagnostic,
  LegacyUploadPseudoOp,
  LegacyUploadPseudoOpStatus,
  LegacyUploadReasonCode,
  PendingOpLane,
} from "./types";

type LegacyUploadPseudoOpInput = Omit<LegacyUploadPseudoOp, "ageMs">;

export function buildLegacyUploadPseudoOp(
  input: LegacyUploadPseudoOpInput,
  now = Date.now(),
): LegacyUploadPseudoOp {
  return {
    ...input,
    ageMs: buildPseudoOpAgeMs(input, now),
  };
}

export function refreshLegacyUploadPseudoOpAge(
  op: Omit<LegacyUploadPseudoOp, "ageMs"> | LegacyUploadPseudoOp,
  now = Date.now(),
): LegacyUploadPseudoOp {
  return {
    ...op,
    ageMs: buildPseudoOpAgeMs(op, now),
  };
}

export function buildPseudoOpAgeMs(
  op: Pick<LegacyUploadPseudoOp, "createdAt" | "lastAttemptAt">,
  now = Date.now(),
): number {
  const baseline = op.lastAttemptAt ?? op.createdAt;
  const timestamp = new Date(baseline).getTime();
  if (!Number.isFinite(timestamp)) {
    return 0;
  }
  return Math.max(0, now - timestamp);
}

export function buildTopReasonCode(
  values: readonly (string | null | undefined)[],
): string | null {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  let winner: string | null = null;
  let winnerCount = 0;
  for (const [reasonCode, count] of counts.entries()) {
    if (count > winnerCount) {
      winner = reasonCode;
      winnerCount = count;
    }
  }
  return winner;
}

export function mergeLaneDiagnosticsWithLegacyUploads(
  diagnostics: Record<PendingOpLane, HealthLaneDiagnostic>,
  legacyUploadOps: readonly LegacyUploadPseudoOp[],
): Record<PendingOpLane, HealthLaneDiagnostic> {
  if (legacyUploadOps.length === 0) {
    return diagnostics;
  }
  const transfer = diagnostics.transfer;
  const oldestLegacyAge = legacyUploadOps.reduce<number | null>((oldest, op) => {
    if (oldest == null) return op.ageMs;
    return Math.max(oldest, op.ageMs);
  }, null);
  return {
    ...diagnostics,
    transfer: {
      lane: "transfer",
      total: transfer.total + legacyUploadOps.length,
      oldestAgeMs:
        transfer.oldestAgeMs == null
          ? oldestLegacyAge
          : oldestLegacyAge == null
            ? transfer.oldestAgeMs
            : Math.max(transfer.oldestAgeMs, oldestLegacyAge),
      active:
        transfer.active ||
        legacyUploadOps.some((op) => op.status === "processing"),
      topReasonCode:
        buildTopReasonCode([
          transfer.topReasonCode,
          ...legacyUploadOps.map((op) => op.reasonCode),
        ]) ?? null,
    },
  };
}

export function normalizeLegacyUploadReasonCode(
  value: string | null | undefined,
): LegacyUploadReasonCode {
  switch (value) {
    case "network_unavailable":
    case "auth_required":
    case "scope_mismatch":
    case "file_missing":
    case "file_corrupted":
    case "upload_failed":
    case "bind_pending_remote_id":
    case "integrity_blocked":
    case "manual_pause":
      return value;
    default:
      return "unknown_error";
  }
}

export function normalizeLegacyUploadStatus(
  value: string | null | undefined,
): LegacyUploadPseudoOpStatus {
  switch (value) {
    case "queued":
    case "processing":
    case "needs_attention":
      return value;
    default:
      return "needs_attention";
  }
}
