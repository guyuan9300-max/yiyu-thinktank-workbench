export type EventLineListItem = {
  status: string;
  primaryClientId?: string | null;
};

export type EventLineListSelection<T extends EventLineListItem> = {
  visible: T[];
  archivedCount: number;
};

/**
 * Applies the project scope first, then hides archived lines unless the user
 * explicitly asks to recover them. The original list order is preserved.
 */
export function selectEventLinesForList<T extends EventLineListItem>(
  eventLines: readonly T[],
  projectFilterId: string,
  showArchived: boolean,
): EventLineListSelection<T> {
  const projectScoped = projectFilterId === '__all__'
    ? [...eventLines]
    : eventLines.filter((item) => (item.primaryClientId || '').trim() === projectFilterId);
  const archivedCount = projectScoped.reduce(
    (count, item) => count + (item.status === 'archived' ? 1 : 0),
    0,
  );

  return {
    visible: showArchived
      ? projectScoped
      : projectScoped.filter((item) => item.status !== 'archived'),
    archivedCount,
  };
}
