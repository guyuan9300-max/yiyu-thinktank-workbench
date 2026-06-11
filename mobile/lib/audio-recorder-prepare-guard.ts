import { isExpoAudioRecorderPrepareBusyError } from "./audio-recorder-core";

const DEFAULT_RETRY_DELAY_MS = 900;
const DEFAULT_MIN_PREPARE_GAP_MS = 700;

let prepareQueue: Promise<void> = Promise.resolve();
let lastPrepareAttemptAt = 0;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function prepareAudioRecorderWithGuard(
  prepare: () => Promise<void>,
  options: {
    beforeRetry?: () => Promise<void> | void;
    retryDelayMs?: number;
    minPrepareGapMs?: number;
  } = {},
): Promise<void> {
  const run = async () => {
    const minPrepareGapMs = options.minPrepareGapMs ?? DEFAULT_MIN_PREPARE_GAP_MS;
    const elapsed = Date.now() - lastPrepareAttemptAt;
    if (lastPrepareAttemptAt > 0 && elapsed < minPrepareGapMs) {
      await delay(minPrepareGapMs - elapsed);
    }
    lastPrepareAttemptAt = Date.now();

    try {
      await prepare();
    } catch (error) {
      if (!isExpoAudioRecorderPrepareBusyError(error)) {
        throw error;
      }
      await options.beforeRetry?.();
      await delay(options.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS);
      lastPrepareAttemptAt = Date.now();
      await prepare();
    }
  };

  const previous = prepareQueue.catch(() => {});
  const current = previous.then(run);
  prepareQueue = current.catch(() => {});
  return current;
}
