import type { SmartTaskDraft } from "./types";

export type RecoveryTrigger = "app_active" | "tasks_enter" | "manual";

export interface RecoveryAttemptOptions {
  trigger: RecoveryTrigger;
  queuedCount: number;
  inFlight: boolean;
  nowMs: number;
  lastAttemptAt: number | null;
  minIntervalMs?: number;
}

export interface AutoOpenOptions {
  trigger: RecoveryTrigger;
  isTasksScreenActive: boolean;
  hasBlockingUi: boolean;
  productRequiresAutoOpen?: boolean;
}

const DEFAULT_RECOVERY_INTERVAL_MS = 1200;

export function shouldAttemptSmartInputRecovery(options: RecoveryAttemptOptions): boolean {
  if (options.queuedCount <= 0 || options.inFlight) {
    return false;
  }
  if (options.trigger === "manual") {
    return true;
  }
  const minIntervalMs = options.minIntervalMs ?? DEFAULT_RECOVERY_INTERVAL_MS;
  if (options.lastAttemptAt == null) {
    return true;
  }
  return options.nowMs - options.lastAttemptAt >= minIntervalMs;
}

export function shouldAutoOpenRecoveredDraft(options: AutoOpenOptions): boolean {
  if (options.productRequiresAutoOpen) {
    return true;
  }
  if (options.trigger !== "manual") {
    return false;
  }
  return options.isTasksScreenActive && !options.hasBlockingUi;
}

export function buildRecoveredDraftKey(draft: SmartTaskDraft | null | undefined): string {
  if (!draft) return "";
  return JSON.stringify({
    title: draft.title ?? "",
    dueDate: draft.dueDate ?? "",
    dueTime: draft.dueTime ?? "",
    description: draft.description ?? "",
  });
}

export function shouldUseRecoveredDraft(nextDraftKey: string, lastRecoveredDraftKey: string | null): boolean {
  if (!nextDraftKey) return false;
  return nextDraftKey !== lastRecoveredDraftKey;
}
