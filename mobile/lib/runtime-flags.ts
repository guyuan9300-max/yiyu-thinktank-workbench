import * as storage from "./storage";

export type RuntimeFlagName =
  | "task_local_first_write_enabled"
  | "task_local_first_read_enabled"
  | "calendar_local_first_write_enabled";

export interface RuntimeFlags {
  task_local_first_write_enabled: boolean;
  task_local_first_read_enabled: boolean;
  calendar_local_first_write_enabled: boolean;
}

const STORAGE_KEY = "yiyu_runtime_flags";

const DEFAULT_FLAGS: RuntimeFlags = {
  task_local_first_write_enabled: true,
  task_local_first_read_enabled: true,
  calendar_local_first_write_enabled: true,
};

let runtimeFlags: RuntimeFlags = { ...DEFAULT_FLAGS };
let isHydrated = false;

function sanitizeRuntimeFlags(raw: unknown): RuntimeFlags {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_FLAGS };
  }
  const value = raw as Partial<Record<RuntimeFlagName, unknown>>;
  return {
    task_local_first_write_enabled:
      typeof value.task_local_first_write_enabled === "boolean"
        ? value.task_local_first_write_enabled
        : DEFAULT_FLAGS.task_local_first_write_enabled,
    task_local_first_read_enabled:
      typeof value.task_local_first_read_enabled === "boolean"
        ? value.task_local_first_read_enabled
        : DEFAULT_FLAGS.task_local_first_read_enabled,
    calendar_local_first_write_enabled:
      typeof value.calendar_local_first_write_enabled === "boolean"
        ? value.calendar_local_first_write_enabled
        : DEFAULT_FLAGS.calendar_local_first_write_enabled,
  };
}

async function persistRuntimeFlags(): Promise<void> {
  await storage.setItem(STORAGE_KEY, JSON.stringify(runtimeFlags));
}

export async function initializeRuntimeFlags(): Promise<void> {
  if (isHydrated) {
    return;
  }
  const stored = await storage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      runtimeFlags = sanitizeRuntimeFlags(JSON.parse(stored));
    } catch {
      runtimeFlags = { ...DEFAULT_FLAGS };
    }
  } else {
    runtimeFlags = { ...DEFAULT_FLAGS };
  }
  isHydrated = true;
}

export function getRuntimeFlags(): RuntimeFlags {
  return runtimeFlags;
}

export function isTaskLocalFirstReadEnabled(): boolean {
  return runtimeFlags.task_local_first_read_enabled;
}

export function isTaskLocalFirstWriteEnabled(): boolean {
  return runtimeFlags.task_local_first_write_enabled;
}

export function isCalendarLocalFirstWriteEnabled(): boolean {
  return runtimeFlags.calendar_local_first_write_enabled;
}

export async function setRuntimeFlag(name: RuntimeFlagName, enabled: boolean): Promise<RuntimeFlags> {
  runtimeFlags = {
    ...runtimeFlags,
    [name]: enabled,
  };
  isHydrated = true;
  await persistRuntimeFlags();
  return runtimeFlags;
}

export async function resetRuntimeFlags(): Promise<void> {
  runtimeFlags = { ...DEFAULT_FLAGS };
  isHydrated = true;
  await persistRuntimeFlags();
}
