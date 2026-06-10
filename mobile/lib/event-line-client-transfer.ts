import * as api from "./api";
import * as cache from "./cache";
import * as localDb from "./local-db";
import { invalidateTaskCreationResources } from "./create-task-resources";
import { emitDataChanged } from "./sync-engine";
import type { EventLineRecord } from "./types";

export async function transferEventLineToClient(
  eventLineId: string,
  clientId: string,
): Promise<EventLineRecord> {
  const updated = await api.updateEventLine(eventLineId, {
    primaryClientId: clientId,
    syncLinkedTaskClientIds: true,
  });

  const [eventLines, taskBoard] = await Promise.all([
    api.fetchEventLines(),
    api.fetchTaskBoard(),
  ]);

  localDb.upsertEventLinesFromCloud(eventLines);
  localDb.upsertTasksFromCloud(taskBoard.tasks);
  invalidateTaskCreationResources();
  cache.invalidate(cache.KEYS.eventLines, cache.KEYS.taskBoard);
  emitDataChanged();

  return updated;
}
