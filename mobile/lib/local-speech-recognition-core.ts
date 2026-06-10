export const LOCAL_SPEECH_RECOGNITION_STOP_SETTLE_MS = 3500;

export type LocalSpeechRecognitionStartOptions = {
  readonly persistAudio?: boolean;
  readonly useAppAudioSource?: boolean;
  readonly useSystemMicrophone?: boolean;
};

export function buildLocalSpeechRecognitionStartConfig(
  options: LocalSpeechRecognitionStartOptions = {},
): Record<string, unknown> {
  // 开启实时音量事件：系统语音识别不提供 metering，靠它让录音/速记界面的声波随说话音量跳动。
  const volumeChangeEventOptions = { enabled: true, intervalMillis: 100 };

  if (options.useAppAudioSource) {
    return {
      lang: "zh-CN",
      interimResults: true,
      continuous: false,
      requiresOnDeviceRecognition: false,
      maxAlternatives: 1,
      recordingOptions: { persist: true },
      volumeChangeEventOptions,
    };
  }

  if (options.useSystemMicrophone) {
    return {
      lang: "zh-CN",
      interimResults: true,
      continuous: false,
      requiresOnDeviceRecognition: false,
      maxAlternatives: 1,
      volumeChangeEventOptions,
    };
  }

  return {
    lang: "zh-CN",
    interimResults: true,
    continuous: true,
    requiresOnDeviceRecognition: false,
    addsPunctuation: true,
    contextualStrings: ["任务", "客户", "事件线", "会议纪要", "行动项", "项目"],
    volumeChangeEventOptions,
    ...(options.persistAudio ? { recordingOptions: { persist: true } } : {}),
  };
}

export function getSpeechRecognitionAudioUri(event: unknown): string | null {
  const uri = (event as { uri?: unknown })?.uri;
  if (typeof uri !== "string") {
    return null;
  }
  const trimmed = uri.trim();
  return trimmed ? trimmed : null;
}

type UnknownSpeechResult = {
  transcript?: unknown;
  text?: unknown;
  confidence?: unknown;
  isFinal?: unknown;
  final?: unknown;
};

function readResultAtIndex(results: unknown, index: number): UnknownSpeechResult | null {
  const indexedResults = results as Record<number, unknown> | undefined;
  const candidate = indexedResults?.[index];
  if (!candidate) return null;

  if (Array.isArray(candidate)) {
    return (candidate[0] as UnknownSpeechResult | undefined) ?? null;
  }

  const nestedCandidate = candidate as UnknownSpeechResult & Record<number, unknown>;
  if (nestedCandidate[0]) {
    return nestedCandidate[0] as UnknownSpeechResult;
  }

  return nestedCandidate;
}

function getSpeechRecognitionResult(event: unknown): UnknownSpeechResult | null {
  const eventPayload = event as {
    resultIndex?: unknown;
    results?: unknown;
  };
  const resultIndex = typeof eventPayload.resultIndex === "number" ? eventPayload.resultIndex : 0;
  return readResultAtIndex(eventPayload.results, resultIndex) ?? readResultAtIndex(eventPayload.results, 0);
}

export function getEventTranscript(event: unknown): string {
  const result = getSpeechRecognitionResult(event);
  const eventPayload = event as {
    transcript?: unknown;
    text?: unknown;
  };
  const value = result?.transcript ?? result?.text ?? eventPayload?.transcript ?? eventPayload?.text ?? "";
  return String(value).trim();
}

export function getResultConfidence(event: unknown): number | null {
  const result = getSpeechRecognitionResult(event);
  const eventPayload = event as {
    confidence?: unknown;
  };
  const confidence = result?.confidence ?? eventPayload?.confidence;
  return typeof confidence === "number" && Number.isFinite(confidence) ? confidence : null;
}

export function getResultIsFinal(event: unknown): boolean {
  const result = getSpeechRecognitionResult(event);
  const eventPayload = event as {
    final?: unknown;
    isFinal?: unknown;
  };
  const value = result?.isFinal ?? result?.final ?? eventPayload?.isFinal ?? eventPayload?.final;
  return value !== false;
}

export function getPermissionGranted(permission: unknown): boolean {
  const permissionPayload = permission as {
    granted?: unknown;
    status?: unknown;
  };
  return Boolean(permissionPayload?.granted ?? permissionPayload?.status === "granted");
}

export function buildSpeechRecognitionErrorMessage(error: unknown, fallback: string): string {
  const message = extractSpeechRecognitionMessage(error);
  if (message && isInsufficientPermissionSpeechRecognitionError(message)) {
    return `系统语音识别服务没有拿到麦克风权限，无法转写。请在系统设置里允许语音识别/语音助手的麦克风权限，或切换默认语音识别服务；原始错误：${message}`;
  }

  return message ?? fallback;
}

function extractSpeechRecognitionMessage(error: unknown): string | null {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  const errorPayload = error as {
    error?: unknown;
    message?: unknown;
  };
  const message = errorPayload?.message ?? errorPayload?.error;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }
  if (typeof message === "number" && Number.isFinite(message)) {
    return String(message);
  }
  return null;
}

function isInsufficientPermissionSpeechRecognitionError(message: string): boolean {
  const normalized = message.trim();
  return (
    normalized === "9" ||
    normalized.includes("Insufficient permissions") ||
    normalized.includes("ERROR_INSUFFICIENT_PERMISSIONS")
  );
}
