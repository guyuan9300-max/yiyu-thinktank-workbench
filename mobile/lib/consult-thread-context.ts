import type {
  ConsultThreadContextSnapshot,
} from "./types";

export interface FreezableConsultContext {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  understandingContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
}

function toStableSnapshotSeed(context: FreezableConsultContext): string {
  return [
    context.clientId ?? "",
    context.clientName ?? "",
    context.eventLineId ?? "",
    context.eventLineName ?? "",
    context.taskId ?? "",
    context.taskTitle ?? "",
    context.taskContext ?? "",
    context.workspaceContext ?? "",
    context.eventLineContext ?? "",
    context.taskBoardContext ?? "",
    context.understandingContext ?? "",
    context.sourceLabels.join("|"),
    context.missingEventLineHint ?? "",
  ].join("\n");
}

export function buildConsultThreadSnapshotHash(
  context: FreezableConsultContext,
): string {
  const seed = toStableSnapshotSeed(context);
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `ctx_${(hash >>> 0).toString(36)}`;
}

export function freezeConsultThreadContext(
  context: FreezableConsultContext,
  frozenAt = new Date().toISOString(),
  previousSnapshot?: Pick<ConsultThreadContextSnapshot, "snapshotVersion"> | null,
): ConsultThreadContextSnapshot {
  return {
    clientId: context.clientId,
    clientName: context.clientName,
    eventLineId: context.eventLineId,
    eventLineName: context.eventLineName,
    taskId: context.taskId,
    taskTitle: context.taskTitle,
    taskContext: context.taskContext,
    workspaceContext: context.workspaceContext,
    eventLineContext: context.eventLineContext,
    taskBoardContext: context.taskBoardContext,
    understandingContext: context.understandingContext,
    sourceLabels: [...context.sourceLabels],
    missingEventLineHint: context.missingEventLineHint,
    frozenAt,
    snapshotHash: buildConsultThreadSnapshotHash(context),
    snapshotVersion: Math.max(1, (previousSnapshot?.snapshotVersion ?? 0) + 1),
  };
}

export function refreshConsultThreadContext(
  previousSnapshot: Pick<ConsultThreadContextSnapshot, "snapshotVersion"> | null,
  context: FreezableConsultContext,
  frozenAt = new Date().toISOString(),
): ConsultThreadContextSnapshot {
  return freezeConsultThreadContext(context, frozenAt, previousSnapshot);
}

export function hasConsultThreadContextDrift(
  snapshot: Pick<ConsultThreadContextSnapshot, "snapshotHash">,
  nextContext: FreezableConsultContext,
): boolean {
  return snapshot.snapshotHash !== buildConsultThreadSnapshotHash(nextContext);
}

export function shouldResetConsultThreadContext(params: {
  readonly hadMessages: boolean;
  readonly nextContextChanged: boolean;
}): boolean {
  return params.hadMessages && params.nextContextChanged;
}
