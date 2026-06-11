export interface RuntimeControllerDeps {
  initializeBaseUrl: () => Promise<void> | void;
  startSync: () => Promise<void> | void;
  stopSync: () => Promise<void> | void;
  resetSessionState?: () => Promise<void> | void;
}

export interface StopRuntimeOptions {
  clearSessionState?: boolean;
}

export function createRuntimeController(deps: RuntimeControllerDeps) {
  let initializePromise: Promise<void> | null = null;
  let startPromise: Promise<void> | null = null;
  let stopPromise: Promise<void> | null = null;
  let syncRunning = false;

  const initialize = () => {
    if (!initializePromise) {
      initializePromise = Promise.resolve(deps.initializeBaseUrl());
    }
    return initializePromise;
  };

  const start = async () => {
    await initialize();
    if (stopPromise) {
      await stopPromise;
    }
    if (syncRunning) {
      return;
    }
    if (!startPromise) {
      startPromise = Promise.resolve(deps.startSync())
        .then(() => {
          syncRunning = true;
        })
        .finally(() => {
          startPromise = null;
        });
    }
    await startPromise;
  };

  const stop = async (options: StopRuntimeOptions = {}) => {
    await initialize();
    if (startPromise) {
      await startPromise;
    }
    if (!syncRunning) {
      if (options.clearSessionState !== false) {
        await Promise.resolve(deps.resetSessionState?.());
      }
      return;
    }
    if (!stopPromise) {
      stopPromise = Promise.resolve(deps.stopSync())
        .then(() => {
          syncRunning = false;
          if (options.clearSessionState !== false) {
            return Promise.resolve(deps.resetSessionState?.());
          }
          return undefined;
        })
        .finally(() => {
          stopPromise = null;
        });
    }
    await stopPromise;
  };

  return {
    initialize,
    start,
    stop,
    isSyncRunning: () => syncRunning,
  };
}
