export type EventLineDirectoryState = 'loading' | 'ready' | 'error';

export interface BatchEventLineCandidate {
  eventLineName: string | null;
  eventLineId: string | null;
}

export type BatchEventLineDecision = 'reuse' | 'create' | 'unmatched' | 'unverified';

export interface BatchEventLinePlanItem {
  key: string;
  name: string;
  eventLineId: string | null;
  taskCount: number;
  decision: BatchEventLineDecision;
}

export function normalizeBatchEventLineName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '');
}

function stableKeyHash(value: string, seed: number): string {
  let hash = seed >>> 0;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

export function buildBatchEventLineIdempotencyKey(sessionId: string, name: string): string {
  const normalizedSession = sessionId.trim();
  const normalizedName = normalizeBatchEventLineName(name);
  const sessionHash = `${stableKeyHash(normalizedSession, 2166136261)}${stableKeyHash(normalizedSession, 2246822519)}`;
  const nameHash = `${stableKeyHash(normalizedName, 2166136261)}${stableKeyHash(normalizedName, 3266489917)}`;
  return `batch-event-line:${sessionHash}:${nameHash}`;
}

function normalizedApprovedNames(names: ReadonlySet<string>): Set<string> {
  return new Set(Array.from(names, normalizeBatchEventLineName).filter(Boolean));
}

export function buildBatchEventLinePlan(
  candidates: BatchEventLineCandidate[],
  approvedCreateNames: ReadonlySet<string>,
  directoryState: EventLineDirectoryState,
): BatchEventLinePlanItem[] {
  const approved = normalizedApprovedNames(approvedCreateNames);
  const grouped = new Map<string, BatchEventLinePlanItem>();

  for (const candidate of candidates) {
    const name = (candidate.eventLineName || '').trim();
    const normalizedName = normalizeBatchEventLineName(name);
    if (!normalizedName) continue;

    const ready = directoryState === 'ready';
    const eventLineId = ready ? candidate.eventLineId : null;
    const key = eventLineId ? `id:${eventLineId}` : `name:${normalizedName}`;
    const decision: BatchEventLineDecision = !ready
      ? 'unverified'
      : eventLineId
        ? 'reuse'
        : approved.has(normalizedName)
          ? 'create'
          : 'unmatched';
    const existing = grouped.get(key);
    if (existing) {
      existing.taskCount += 1;
      continue;
    }
    grouped.set(key, {
      key,
      name,
      eventLineId,
      taskCount: 1,
      decision,
    });
  }

  return Array.from(grouped.values());
}

export function canSubmitBatchImport(
  directoryState: EventLineDirectoryState,
  plan: BatchEventLinePlanItem[],
  creationConfirmed: boolean,
): boolean {
  if (directoryState !== 'ready') return false;
  return !plan.some((item) => item.decision === 'create') || creationConfirmed;
}

interface ResolveEventLineIdForSaveOptions {
  candidate: BatchEventLineCandidate;
  directoryState: EventLineDirectoryState;
  approvedCreateNames: ReadonlySet<string>;
  creationConfirmed: boolean;
  cache: Map<string, string>;
  createEventLine: (payload: { name: string }) => Promise<{ id: string }>;
}

export async function resolveEventLineIdForSave({
  candidate,
  directoryState,
  approvedCreateNames,
  creationConfirmed,
  cache,
  createEventLine,
}: ResolveEventLineIdForSaveOptions): Promise<string | null> {
  if (directoryState !== 'ready') return null;
  if (candidate.eventLineId) return candidate.eventLineId;
  if (!creationConfirmed) return null;

  const name = (candidate.eventLineName || '').trim();
  const key = normalizeBatchEventLineName(name);
  if (!key || !normalizedApprovedNames(approvedCreateNames).has(key)) return null;

  const cached = cache.get(key);
  if (cached) return cached;
  const created = await createEventLine({ name });
  cache.set(key, created.id);
  return created.id;
}

export function appendUnmatchedEventLineToDesc(desc: string, eventLineName: string | null): string {
  const name = (eventLineName || '').trim();
  if (!name) return desc;
  const note = `未关联事件线：${name}`;
  if (desc.includes(note)) return desc;
  return desc ? `${desc}\n\n${note}` : note;
}
