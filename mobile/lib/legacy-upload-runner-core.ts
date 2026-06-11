import type {
  LegacyUploadPseudoOp,
  LegacyUploadPseudoOpStatus,
  LegacyUploadReasonCode,
} from "./types";

export interface LegacyUploadAutoProcessResult {
  attempted: number;
  completed: number;
  stoppedByAuth: boolean;
  stoppedByNetwork: boolean;
}

export type LegacyUploadRetryResult =
  | { ok: true }
  | { ok: false; reasonCode: LegacyUploadReasonCode; message: string };

export function resolveLegacyUploadFailureStatus(
  reasonCode: LegacyUploadReasonCode,
): LegacyUploadPseudoOpStatus {
  switch (reasonCode) {
    case "network_unavailable":
    case "bind_pending_remote_id":
    case "integrity_blocked":
    case "manual_pause":
    case "scope_mismatch":
      return "queued";
    default:
      return "needs_attention";
  }
}

export async function processQueuedLegacyUploadOps(
  ops: readonly Pick<LegacyUploadPseudoOp, "opId" | "status">[],
  retry: (opId: string) => Promise<LegacyUploadRetryResult>,
): Promise<LegacyUploadAutoProcessResult> {
  const result: LegacyUploadAutoProcessResult = {
    attempted: 0,
    completed: 0,
    stoppedByAuth: false,
    stoppedByNetwork: false,
  };

  for (const op of ops) {
    if (op.status !== "queued") {
      continue;
    }
    result.attempted += 1;
    const retryResult = await retry(op.opId);
    if (retryResult.ok) {
      result.completed += 1;
      continue;
    }
    const reasonCode =
      "reasonCode" in retryResult ? retryResult.reasonCode : "unknown_error";
    if (reasonCode === "auth_required") {
      result.stoppedByAuth = true;
      break;
    }
    if (reasonCode === "network_unavailable") {
      result.stoppedByNetwork = true;
      break;
    }
  }

  return result;
}
