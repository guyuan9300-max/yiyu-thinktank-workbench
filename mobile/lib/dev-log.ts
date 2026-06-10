type LogPayload = Record<string, unknown> | undefined;

function nowMs(): number {
  if (typeof globalThis.performance?.now === "function") {
    return globalThis.performance.now();
  }
  return Date.now();
}

export function devLog(scope: string, message: string, payload?: LogPayload): void {
  if (!__DEV__) return;
  if (payload && Object.keys(payload).length > 0) {
    console.log(`[${scope}] ${message}`, payload);
    return;
  }
  console.log(`[${scope}] ${message}`);
}

export function measureDevSync<T>(scope: string, message: string, fn: () => T): T {
  const startedAt = nowMs();
  try {
    return fn();
  } finally {
    if (__DEV__) {
      devLog(scope, message, { durationMs: Math.round(nowMs() - startedAt) });
    }
  }
}

export async function measureDevAsync<T>(scope: string, message: string, fn: () => Promise<T>): Promise<T> {
  const startedAt = nowMs();
  try {
    return await fn();
  } finally {
    if (__DEV__) {
      devLog(scope, message, { durationMs: Math.round(nowMs() - startedAt) });
    }
  }
}
