export interface QueuedSmartInputRef {
  id: string;
}

export function reconcileQueuedSmartInputItems<T extends QueuedSmartInputRef>(
  currentQueue: readonly T[],
  removeIds: ReadonlySet<string>,
): T[] {
  if (removeIds.size === 0) {
    return [...currentQueue];
  }
  return currentQueue.filter((item) => !removeIds.has(item.id));
}
