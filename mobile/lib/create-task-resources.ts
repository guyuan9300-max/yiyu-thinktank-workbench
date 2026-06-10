import * as api from "./api";
import * as cache from "./cache";
import type {
  ClientSummaryRecord,
  EventLineRecord,
  TaskListRecord,
  TaskSettingsRecord,
} from "./types";

export type OrgMember = api.OrgMember;

export interface TaskCreationResources {
  settings: TaskSettingsRecord | null;
  taskLists: TaskListRecord[];
  eventLines: EventLineRecord[];
  clients: ClientSummaryRecord[];
}

let resourcesPromise: Promise<TaskCreationResources> | null = null;
let resourcesSnapshot: TaskCreationResources | null = null;

export async function loadTaskCreationResources(): Promise<TaskCreationResources> {
  if (resourcesSnapshot) {
    return resourcesSnapshot;
  }
  if (!resourcesPromise) {
    resourcesPromise = (async () => {
      let settings: TaskSettingsRecord | null = null;
      let taskLists: TaskListRecord[] = [];
      let eventLines: EventLineRecord[] = [];
      let clients: ClientSummaryRecord[] = [];

      await Promise.all([
        cache.loadWithCache(cache.KEYS.taskSettings, api.fetchTaskSettings, (value) => {
          settings = value;
        }).catch(() => {}),
        cache.loadWithCache(cache.KEYS.taskLists, api.fetchTaskLists, (value) => {
          taskLists = value;
        }).catch(() => {}),
        cache.loadWithCache(cache.KEYS.eventLines, api.fetchEventLines, (value) => {
          eventLines = value;
        }).catch(() => {}),
        cache.loadWithCache(cache.KEYS.clients, api.fetchClients, (value) => {
          clients = value;
        }).catch(() => {}),
      ]);

      resourcesSnapshot = {
        settings,
        taskLists,
        eventLines,
        clients,
      };
      return resourcesSnapshot;
    })().finally(() => {
      resourcesPromise = null;
    });
  }

  return resourcesPromise;
}

export function invalidateTaskCreationResources(): void {
  resourcesSnapshot = null;
}

export async function loadEmployeeDirectory(): Promise<OrgMember[]> {
  return api.fetchEmployeeDirectory();
}
