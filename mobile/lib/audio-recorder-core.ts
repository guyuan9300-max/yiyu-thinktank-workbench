const EXPO_AUDIO_RECORDER_PREPARE_BUSY_PATTERNS = [
  "previous attempt is still ongoing",
  "tried binding to the recording service",
  "already been prepared",
  "release the current session before preparing again",
] as const;

function getAudioRecorderErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "";
}

export function isExpoAudioRecorderPrepareBusyError(error: unknown): boolean {
  const message = getAudioRecorderErrorMessage(error).toLowerCase();
  return EXPO_AUDIO_RECORDER_PREPARE_BUSY_PATTERNS.some((pattern) => message.includes(pattern));
}

export function getAudioRecorderStartFailureMessage(error: unknown): string {
  if (isExpoAudioRecorderPrepareBusyError(error)) {
    return "录音服务还在释放上一次会话，请稍等 1 秒后重试。";
  }
  const message = getAudioRecorderErrorMessage(error).trim();
  return message || "无法开始录音，请稍后重试。";
}
