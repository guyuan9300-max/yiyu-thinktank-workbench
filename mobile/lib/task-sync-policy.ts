import type { TaskRecord } from "./types";

export interface TaskServerAckDecision {
  shouldReplaceLocalTask: boolean;
  shouldPromotePendingCreate: boolean;
  shouldUpdateShadowOnly: boolean;
}

export interface TaskServerAckDecisionInput {
  localTask: TaskRecord | null;
  ackLocalVersion: number | null;
  hasPendingOps: boolean;
  pendingCreateExists: boolean;
}

export function decideTaskServerAckAction(
  input: TaskServerAckDecisionInput,
): TaskServerAckDecision {
  if (!input.localTask) {
    return {
      shouldReplaceLocalTask: true,
      shouldPromotePendingCreate: false,
      shouldUpdateShadowOnly: false,
    };
  }

  const currentLocalVersion = input.localTask.localVersion ?? 0;
  const isStaleAck =
    input.ackLocalVersion != null &&
    currentLocalVersion > input.ackLocalVersion;
  const shouldKeepDirtyLocalState = input.hasPendingOps || isStaleAck;

  return {
    shouldReplaceLocalTask: !shouldKeepDirtyLocalState,
    shouldPromotePendingCreate: shouldKeepDirtyLocalState && input.pendingCreateExists,
    shouldUpdateShadowOnly: shouldKeepDirtyLocalState,
  };
}
