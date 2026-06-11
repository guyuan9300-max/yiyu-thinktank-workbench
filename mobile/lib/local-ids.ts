function randomSegment(): string {
  return Math.random().toString(36).slice(2, 10);
}

function timestampSegment(): string {
  return Date.now().toString(36);
}

export function createLocalEntityId(entityType: string): string {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (randomUuid) {
    return `${entityType}_${randomUuid}`;
  }
  return `${entityType}_${timestampSegment()}_${randomSegment()}`;
}

export function createClientOpId(entityType: string): string {
  return createLocalEntityId(`${entityType}_op`);
}
