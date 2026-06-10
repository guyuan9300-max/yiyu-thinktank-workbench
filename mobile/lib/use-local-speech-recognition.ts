import { useCallback, useRef } from "react";
import { AudioModule } from "expo-audio";
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from "expo-speech-recognition";
import type { RecordingSegmentDraft } from "./recording-session-core";
import {
  LOCAL_SPEECH_RECOGNITION_STOP_SETTLE_MS,
  buildLocalSpeechRecognitionStartConfig,
  buildSpeechRecognitionErrorMessage,
  getEventTranscript,
  getPermissionGranted,
  getResultConfidence,
  getResultIsFinal,
  getSpeechRecognitionAudioUri,
  type LocalSpeechRecognitionStartOptions,
} from "./local-speech-recognition-core";

export interface LocalSpeechRecognitionSnapshot {
  transcript: string;
  segments: RecordingSegmentDraft[];
  error: string | null;
  isAvailable: boolean;
  audioUri: string | null;
}

export function useLocalSpeechRecognition() {
  const startTimeRef = useRef<number | null>(null);
  const transcriptPartsRef = useRef<string[]>([]);
  const partialTextRef = useRef("");
  const segmentsRef = useRef<RecordingSegmentDraft[]>([]);
  const errorRef = useRef<string | null>(null);
  const audioUriRef = useRef<string | null>(null);
  const activeRef = useRef(false);
  const lastFinalTextRef = useRef("");
  const ownsRecognitionRef = useRef(false);
  const settleResolversRef = useRef<Array<() => void>>([]);

  const snapshot = useCallback((): LocalSpeechRecognitionSnapshot => {
    const parts = [...transcriptPartsRef.current];
    if (partialTextRef.current.trim() && partialTextRef.current !== lastFinalTextRef.current) {
      parts.push(partialTextRef.current.trim());
    }
    return {
      transcript: parts.join("\n").trim(),
      segments: segmentsRef.current,
      error: errorRef.current,
      isAvailable: !errorRef.current,
      audioUri: audioUriRef.current,
    };
  }, []);

  const flushSettleResolvers = useCallback(() => {
    const resolvers = settleResolversRef.current.splice(0);
    resolvers.forEach((resolve) => resolve());
  }, []);

  const waitForRecognitionSettle = useCallback(async () => {
    if (!ownsRecognitionRef.current && !activeRef.current) {
      return;
    }

    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, LOCAL_SPEECH_RECOGNITION_STOP_SETTLE_MS);
      settleResolversRef.current.push(() => {
        clearTimeout(timeout);
        resolve();
      });
    });
  }, []);

  useSpeechRecognitionEvent("start" as any, () => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    activeRef.current = true;
  });

  useSpeechRecognitionEvent("end" as any, () => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    activeRef.current = false;
    flushSettleResolvers();
  });

  useSpeechRecognitionEvent("audiostart" as any, (event: any) => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    const uri = getSpeechRecognitionAudioUri(event);
    if (uri) {
      audioUriRef.current = uri;
    }
  });

  useSpeechRecognitionEvent("audioend" as any, (event: any) => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    const uri = getSpeechRecognitionAudioUri(event);
    if (uri) {
      audioUriRef.current = uri;
    }
    flushSettleResolvers();
  });

  useSpeechRecognitionEvent("error" as any, (event: any) => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    errorRef.current = buildSpeechRecognitionErrorMessage(event, "本地语音识别失败。");
    activeRef.current = false;
    flushSettleResolvers();
  });

  useSpeechRecognitionEvent("result" as any, (event: any) => {
    if (!ownsRecognitionRef.current) {
      return;
    }
    const text = getEventTranscript(event);
    if (!text) {
      return;
    }

    const elapsed = Math.max(0, Date.now() - (startTimeRef.current ?? Date.now()));
    const isFinal = getResultIsFinal(event);
    if (isFinal) {
      if (text !== lastFinalTextRef.current) {
        const previous = segmentsRef.current[segmentsRef.current.length - 1];
        const startMs = previous?.endMs ?? 0;
        segmentsRef.current.push({
          segmentIndex: segmentsRef.current.length,
          startMs,
          endMs: elapsed,
          text,
          confidence: getResultConfidence(event),
          isFinal: true,
        });
        transcriptPartsRef.current.push(text);
        lastFinalTextRef.current = text;
      }
      partialTextRef.current = "";
      flushSettleResolvers();
      return;
    }

    partialTextRef.current = text;
    flushSettleResolvers();
  });

  const reset = useCallback(() => {
    startTimeRef.current = Date.now();
    transcriptPartsRef.current = [];
    partialTextRef.current = "";
    segmentsRef.current = [];
    errorRef.current = null;
    audioUriRef.current = null;
    lastFinalTextRef.current = "";
    activeRef.current = false;
    ownsRecognitionRef.current = false;
    flushSettleResolvers();
  }, [flushSettleResolvers]);

  const markLocalSpeechRecognitionUnavailable = useCallback((message: string) => {
    reset();
    errorRef.current = message;
    activeRef.current = false;
    ownsRecognitionRef.current = false;
    flushSettleResolvers();
  }, [flushSettleResolvers, reset]);

  const supportsPersistentAudio = useCallback((): boolean => {
    try {
      const supportsRecording = (ExpoSpeechRecognitionModule as any).supportsRecording;
      return typeof supportsRecording === "function" && Boolean(supportsRecording());
    } catch {
      return false;
    }
  }, []);

  const startLocalSpeechRecognition = useCallback(async (
    options: LocalSpeechRecognitionStartOptions = {},
  ): Promise<LocalSpeechRecognitionSnapshot> => {
    reset();
    ownsRecognitionRef.current = true;
    try {
      const audioPermission = await AudioModule.requestRecordingPermissionsAsync();
      if (!getPermissionGranted(audioPermission)) {
        throw new Error("请先允许麦克风权限。");
      }
      const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!getPermissionGranted(permission)) {
        throw new Error("请先允许语音识别权限。");
      }
      const canPersistAudio = supportsPersistentAudio();
      if (options.useAppAudioSource && !canPersistAudio) {
        throw new Error("当前设备不支持应用侧音频源语音识别。");
      }
      const persistAudio = Boolean(
        (options.persistAudio || options.useAppAudioSource) &&
          !options.useSystemMicrophone &&
          canPersistAudio,
      );
      ExpoSpeechRecognitionModule.start(
        buildLocalSpeechRecognitionStartConfig({ ...options, persistAudio }) as any,
      );
      activeRef.current = true;
    } catch (error) {
      errorRef.current = buildSpeechRecognitionErrorMessage(error, "本地语音识别启动失败。");
      activeRef.current = false;
      ownsRecognitionRef.current = false;
      flushSettleResolvers();
    }
    return snapshot();
  }, [flushSettleResolvers, reset, snapshot, supportsPersistentAudio]);

  const stopLocalSpeechRecognition = useCallback(async (): Promise<LocalSpeechRecognitionSnapshot> => {
    if (activeRef.current || ownsRecognitionRef.current) {
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch (error) {
        errorRef.current = buildSpeechRecognitionErrorMessage(error, "本地语音识别停止失败。");
      }
    }
    await waitForRecognitionSettle();
    activeRef.current = false;
    ownsRecognitionRef.current = false;
    flushSettleResolvers();
    return snapshot();
  }, [flushSettleResolvers, snapshot, waitForRecognitionSettle]);

  const cancelLocalSpeechRecognition = useCallback(async (): Promise<void> => {
    if (activeRef.current || ownsRecognitionRef.current) {
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {}
    }
    activeRef.current = false;
    ownsRecognitionRef.current = false;
    flushSettleResolvers();
    reset();
  }, [flushSettleResolvers, reset]);

  return {
    startLocalSpeechRecognition,
    stopLocalSpeechRecognition,
    cancelLocalSpeechRecognition,
    markLocalSpeechRecognitionUnavailable,
  };
}
