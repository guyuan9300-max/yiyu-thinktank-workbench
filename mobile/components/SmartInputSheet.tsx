import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  AppState,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { BlurView } from "expo-blur";
import {
  AudioModule,
  AudioQuality,
  IOSOutputFormat,
  RecordingPresets,
  type RecordingOptions,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import * as Haptics from "expo-haptics";
import { Mic, Square, WifiOff, X } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { palette } from "../lib/theme";
import { getAudioRecorderStartFailureMessage } from "../lib/audio-recorder-core";
import { prepareAudioRecorderWithGuard } from "../lib/audio-recorder-prepare-guard";
import { useSpeechRecognitionEvent } from "expo-speech-recognition";
import type { UploadableFile } from "../lib/api";
import { generateSmartTaskDraft } from "../lib/api";
import { buildLocalSmartTaskDraftFromTranscript } from "../lib/recording-session-core";
import { saveUnboundRecording } from "../lib/recording-session-service";
import {
  clearSmartInputQueue,
  getQueuedSmartInputCount,
} from "../lib/smart-input-queue";
import type { SmartTaskDraft, SmartTaskDraftResponse } from "../lib/types";
import {
  useLocalSpeechRecognition,
  type LocalSpeechRecognitionSnapshot,
} from "../lib/use-local-speech-recognition";

interface Props {
  readonly onClose: () => void;
  readonly onApplyDraft: (draft: SmartTaskDraft) => void;
  readonly referenceDate?: string | null;
  readonly autoStart?: boolean;
}

const METER_BAR_MULTIPLIERS = [0.52, 0.78, 1.1, 1.42, 1.1, 0.78, 0.52] as const;
const SMART_INPUT_RECORDING_PRESET: RecordingOptions = {
  ...RecordingPresets.HIGH_QUALITY,
  extension: ".m4a",
  sampleRate: 16000,
  numberOfChannels: 1,
  bitRate: 32000,
  android: {
    extension: ".m4a",
    outputFormat: "mpeg4",
    audioEncoder: "aac",
  },
  ios: {
    outputFormat: IOSOutputFormat.MPEG4AAC,
    audioQuality: AudioQuality.MEDIUM,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {
    mimeType: "audio/webm",
    bitsPerSecond: 48000,
  },
};
const SPEECH_DETECTED_THRESHOLD = 0.24;
const AUTO_STOP_SILENCE_THRESHOLD = 0.14;
// 自动停止仅作兜底：放宽到 2.5s，避免用户说话中途思考停顿(>1.1s)被误截断。
// 验收口径「带 2 秒停顿不被截断」要求该值 > 2000ms。手动停止/松手仍是主要结束信号。
const AUTO_STOP_SILENCE_MS = 2500;
const AUTO_STOP_MIN_SECONDS = 1;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function formatTime(seconds: number): string {
  const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
  const secs = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${secs}`;
}

function tailText(value: string, maxChars: number): string {
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (trimmed.length <= maxChars) {
    return trimmed;
  }
  return `…${trimmed.slice(-maxChars)}`;
}

function inferMimeTypeFromUri(uri: string): string {
  const lower = uri.split("?")[0].toLowerCase();
  if (lower.endsWith(".wav")) return "audio/wav";
  if (lower.endsWith(".mp3")) return "audio/mpeg";
  if (lower.endsWith(".ogg")) return "audio/ogg";
  if (lower.endsWith(".aac")) return "audio/aac";
  if (lower.endsWith(".caf")) return "audio/x-caf";
  if (lower.endsWith(".webm")) return "audio/webm";
  return "audio/m4a";
}

export default function SmartInputSheet({
  onClose,
  onApplyDraft,
  referenceDate,
  autoStart = true,
}: Props) {
  const chrome = useAppChromeInsets();
  const [transcript, setTranscript] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [liveHint, setLiveHint] = useState("正在聆听...");
  const [queuedCount, setQueuedCount] = useState(0);
  const [androidSpeechRecordingActive, setAndroidSpeechRecordingActive] = useState(false);
  const [androidSpeechDurationSeconds, setAndroidSpeechDurationSeconds] = useState(0);
  const [speechVolume, setSpeechVolume] = useState(0);
  // 静音自动停止的低频驱动:Android 系统识别在完全静音时不再发 volumechange，
  // normalizedMeter 不更新会让静音判定 effect 不再触发(卡"正在聆听")。用一个
  // 每 500ms 自增的 tick 强制 effect 重新评估，不依赖音量事件。
  const [autoStopTick, setAutoStopTick] = useState(0);
  const {
    startLocalSpeechRecognition,
    stopLocalSpeechRecognition,
    cancelLocalSpeechRecognition,
  } = useLocalSpeechRecognition();
  // 系统语音识别(Android)无 metering，订阅实时音量事件驱动声波随说话跳动。
  useSpeechRecognitionEvent("volumechange", (event: { value?: number }) => {
    setSpeechVolume(typeof event?.value === "number" ? event.value : 0);
  });

  const recorder = useAudioRecorder({ ...SMART_INPUT_RECORDING_PRESET, isMeteringEnabled: true });
  const recorderState = useAudioRecorderState(recorder, 120);
  const autoStartedRef = useRef(false);
  const startInFlightRef = useRef(false);
  const waveValues = useRef(METER_BAR_MULTIPLIERS.map(() => new Animated.Value(0.2))).current;
  const pulseScale = useRef(new Animated.Value(1)).current;
  const pulseOpacity = useRef(new Animated.Value(0.18)).current;
  const panelScale = useRef(new Animated.Value(0.9)).current;
  const panelOpacity = useRef(new Animated.Value(0)).current;
  const pulseLoopRef = useRef<Animated.CompositeAnimation | null>(null);
  const pendingAudioRef = useRef<UploadableFile | null>(null);
  const pendingSpeechRef = useRef<LocalSpeechRecognitionSnapshot | null>(null);
  const pendingDurationSecondsRef = useRef<number | null>(null);
  const appStateRef = useRef(AppState.currentState);
  const speechDetectedRef = useRef(false);
  const silenceStartedAtRef = useRef<number | null>(null);
  const autoStopInFlightRef = useRef(false);

  const isRecording = recorderState.isRecording || androidSpeechRecordingActive;
  const recordingSeconds = androidSpeechRecordingActive
    ? androidSpeechDurationSeconds
    : Math.max(0, Math.floor(recorderState.durationMillis / 1000));

  const normalizedMeter = useMemo(() => {
    if (!isRecording) {
      return 0.08;
    }
    if (androidSpeechRecordingActive) {
      // 系统语音识别无 metering，用 volumechange 事件的实时音量(value≈-2~10)驱动声波。
      return clamp(speechVolume / 7, 0.12, 1);
    }
    const rawMeter = typeof recorderState.metering === "number" ? recorderState.metering : -60;
    return clamp((rawMeter + 60) / 60, 0.08, 1);
  }, [androidSpeechRecordingActive, isRecording, recorderState.metering, speechVolume]);

  const displayText = useMemo(() => {
    if (isGenerating) {
      return "正在整理本地转写，请稍等…";
    }
    if (transcript.trim()) {
      return transcript.trim();
    }
    if (warnings.length > 0) {
      return warnings[warnings.length - 1];
    }
    return liveHint;
  }, [isGenerating, liveHint, transcript, warnings]);

  const transcriptTail = useMemo(() => {
    if (isGenerating) {
      return tailText(displayText, 36);
    }
    if (isRecording && !transcript.trim()) {
      return "正在聆听你的语音…";
    }
    return tailText(displayText, 42);
  }, [displayText, isGenerating, isRecording, transcript]);

  useEffect(() => {
    Animated.parallel([
      Animated.spring(panelScale, { toValue: 1, useNativeDriver: true, speed: 16, bounciness: 7 }),
      Animated.timing(panelOpacity, { toValue: 1, duration: 220, useNativeDriver: true }),
    ]).start();
  }, [panelOpacity, panelScale]);

  useEffect(() => {
    waveValues.forEach((value, index) => {
      const nextValue = isRecording
        ? clamp(0.18 + normalizedMeter * 1.6 * METER_BAR_MULTIPLIERS[index], 0.22, 2.2)
        : 0.22;
      Animated.spring(value, {
        toValue: nextValue,
        useNativeDriver: true,
        speed: 18,
        bounciness: isRecording ? 8 : 4,
      }).start();
    });
  }, [isRecording, normalizedMeter, waveValues]);

  useEffect(() => {
    pulseLoopRef.current?.stop();
    if (!isRecording) {
      Animated.parallel([
        Animated.spring(pulseScale, { toValue: 1, useNativeDriver: true, speed: 18, bounciness: 5 }),
        Animated.timing(pulseOpacity, { toValue: 0.18, duration: 160, useNativeDriver: true }),
      ]).start();
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(pulseScale, { toValue: 1.08, duration: 320, useNativeDriver: true }),
          Animated.timing(pulseOpacity, { toValue: 0.38, duration: 320, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(pulseScale, { toValue: 0.98, duration: 280, useNativeDriver: true }),
          Animated.timing(pulseOpacity, { toValue: 0.14, duration: 280, useNativeDriver: true }),
        ]),
      ]),
    );
    pulseLoopRef.current = loop;
    loop.start();
    return () => loop.stop();
  }, [isRecording, pulseOpacity, pulseScale]);

  useEffect(() => {
    if (!isRecording) {
      speechDetectedRef.current = false;
      silenceStartedAtRef.current = null;
      autoStopInFlightRef.current = false;
    }
  }, [isRecording]);

  useEffect(() => {
    if (!androidSpeechRecordingActive) {
      return;
    }
    const interval = setInterval(() => {
      setAndroidSpeechDurationSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [androidSpeechRecordingActive]);

  const resetAudioMode = useCallback(async () => {
    if (Platform.OS === "web") {
      return;
    }
    try {
      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: false,
        shouldRouteThroughEarpiece: false,
        shouldPlayInBackground: false,
        allowsBackgroundRecording: false,
        interruptionMode: "mixWithOthers",
      });
    } catch {}
  }, []);

  const releaseRecorderSafely = useCallback(async () => {
    if (Platform.OS === "web") {
      return;
    }
    try {
      await recorder.stop();
    } catch {}
  }, [recorder]);

  useEffect(() => {
    return () => {
      pulseLoopRef.current?.stop();
      void releaseRecorderSafely();
      void cancelLocalSpeechRecognition();
      void resetAudioMode();
    };
  }, [cancelLocalSpeechRecognition, releaseRecorderSafely, resetAudioMode]);

  const buildPendingAudio = useCallback((audioUri?: string | null): UploadableFile | null => {
    const uri = audioUri?.trim() || recorder.uri || recorderState.url;
    if (!uri) {
      return null;
    }
    const cleanUri = uri.split("?")[0];
    const extension = (cleanUri.split(".").pop() || "m4a").toLowerCase();
    return {
      uri,
      name: `smart-input-${Date.now()}.${extension}`,
      type: inferMimeTypeFromUri(cleanUri),
    };
  }, [recorder, recorderState.url]);

  const applyDraftResponse = useCallback((response: SmartTaskDraftResponse) => {
    setTranscript(response.transcript || "");
    setWarnings(response.warnings);
    onApplyDraft(response.draft);
  }, [onApplyDraft]);

  const refreshQueuedCount = useCallback(async () => {
    try {
      setQueuedCount(await getQueuedSmartInputCount());
    } catch {}
  }, []);

  const generateFromCurrentInput = useCallback(async () => {
    const speechSnapshot = pendingSpeechRef.current;
    const trimmedTranscript = (transcript.trim() || speechSnapshot?.transcript.trim() || "").trim();
    const audioFile = pendingAudioRef.current;
    if (!trimmedTranscript && !audioFile) {
      Alert.alert("提示", "先说一段话，再生成任务草稿。");
      return false;
    }

    pendingAudioRef.current = null;
    pendingSpeechRef.current = null;
    const durationSeconds = pendingDurationSecondsRef.current;
    pendingDurationSecondsRef.current = null;
    setIsGenerating(true);

    let savedSession: Awaited<ReturnType<typeof saveUnboundRecording>> | null = null;
    try {
      if (audioFile) {
        savedSession = await saveUnboundRecording({
          file: audioFile,
          title: "智能输入录音",
          durationSeconds,
          rawTranscript: trimmedTranscript,
          cleanTranscript: trimmedTranscript,
          segments: speechSnapshot?.segments ?? [],
          asrError: speechSnapshot?.error ?? (trimmedTranscript ? null : "本地语音识别没有返回文本。"),
          source: "smart_input",
        });
      }
      if (!trimmedTranscript) {
        // 本地识别没出文字 → 云端 ASR 兜底:音频交给后端(豆包转写 + 结构化一步到位)。
        // 关键:上传用 saveUnboundRecording 已落盘的稳定副本 audioPath,而不是语音识别的临时 uri
        // (后者在上传前常被系统清掉 → 上传失败、请求都发不出去)。
        const audioFileUri = audioFile && "uri" in audioFile ? audioFile.uri : null;
        const audioFileType = audioFile && "uri" in audioFile ? audioFile.type : null;
        const stableUri = savedSession?.audioPath ?? audioFileUri;
        if (stableUri) {
          const ext = (stableUri.split("?")[0].split(".").pop() || "m4a").toLowerCase();
          const cloudAudio: UploadableFile = {
            uri: stableUri,
            name: `smart-input-${Date.now()}.${ext}`,
            type: audioFileType ?? `audio/${ext}`,
          };
          try {
            const cloudResponse = await generateSmartTaskDraft({
              audioFile: cloudAudio,
              referenceDate: referenceDate ?? undefined,
            });
            applyDraftResponse(cloudResponse);
            onClose();
            return true;
          } catch (cloudError) {
            console.warn("[smartInput] 云端转写失败", cloudError);
            Alert.alert("录音已保存", "本地与云端转写都没成功，原音频已保留，可稍后补文字。");
            onClose();
            return false;
          }
        }
        Alert.alert("录音已保存", "本地语音识别没有返回文本，原音频已保留，可稍后补文字。");
        onClose();
        return false;
      }
      const response = buildLocalSmartTaskDraftFromTranscript(trimmedTranscript, referenceDate ?? undefined);
      applyDraftResponse(response);
      onClose();
      return true;
    } catch (error) {
      Alert.alert("智能输入失败", error instanceof Error ? error.message : "请稍后再试。");
      return false;
    } finally {
      setIsGenerating(false);
    }
  }, [applyDraftResponse, onClose, referenceDate, transcript]);

  const startRecording = useCallback(async () => {
    if (isGenerating || isRecording || startInFlightRef.current) {
      return;
    }
    startInFlightRef.current = true;
    setWarnings([]);
    setTranscript("");
    pendingAudioRef.current = null;
    pendingSpeechRef.current = null;
    pendingDurationSecondsRef.current = null;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        throw new Error("请先允许麦克风权限。");
      }
      if (Platform.OS === "android") {
        const speechSnapshot = await startLocalSpeechRecognition({ useAppAudioSource: true });
        if (!speechSnapshot.isAvailable) {
          throw new Error(speechSnapshot.error ?? "本地语音识别启动失败。");
        }
        setAndroidSpeechRecordingActive(true);
        setAndroidSpeechDurationSeconds(0);
        setLiveHint("正在聆听…");
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        return;
      }
      if (Platform.OS !== "web") {
        await releaseRecorderSafely();
        await setAudioModeAsync({
          playsInSilentMode: true,
          allowsRecording: true,
          shouldRouteThroughEarpiece: false,
          shouldPlayInBackground: true,
          allowsBackgroundRecording: true,
          interruptionMode: "doNotMix",
        });
      }
      await prepareAudioRecorderWithGuard(
        () => recorder.prepareToRecordAsync({ ...SMART_INPUT_RECORDING_PRESET, isMeteringEnabled: true }),
        { beforeRetry: releaseRecorderSafely },
      );
      recorder.record();
      void startLocalSpeechRecognition();
      setLiveHint("正在聆听…");
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      setAndroidSpeechRecordingActive(false);
      setAndroidSpeechDurationSeconds(0);
      await releaseRecorderSafely();
      await resetAudioMode();
      Alert.alert("开始录音失败", getAudioRecorderStartFailureMessage(error));
    } finally {
      startInFlightRef.current = false;
    }
  }, [
    isGenerating,
    isRecording,
    recorder,
    releaseRecorderSafely,
    resetAudioMode,
    startLocalSpeechRecognition,
  ]);

  const stopRecording = useCallback(async (generateImmediately: boolean) => {
    if (!isRecording) {
      return;
    }
    try {
      const durationSeconds = recordingSeconds;
      let speechSnapshot: LocalSpeechRecognitionSnapshot;
      if (androidSpeechRecordingActive) {
        speechSnapshot = await stopLocalSpeechRecognition();
        setAndroidSpeechRecordingActive(false);
        pendingAudioRef.current = buildPendingAudio(speechSnapshot.audioUri);
      } else {
        // 与 RecordNote 同源:stop 之后 recorder.uri 在部分版本会被清空、recorderState.url
        // 又是节流 state，故在 stop 之前先抓住 uri 传入，避免速记音频"白录"。
        const preStopUri = recorder.uri;
        await releaseRecorderSafely();
        await resetAudioMode();
        speechSnapshot = await stopLocalSpeechRecognition();
        pendingAudioRef.current = buildPendingAudio(preStopUri);
      }
      pendingSpeechRef.current = speechSnapshot;
      pendingDurationSecondsRef.current = durationSeconds;
      if (speechSnapshot.transcript.trim()) {
        setTranscript(speechSnapshot.transcript.trim());
      }
      setLiveHint(
        generateImmediately
          ? "正在本地整理语音…"
          : "收音完成，可重新开始，或继续整理成任务草稿。",
      );
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      if (generateImmediately) {
        await generateFromCurrentInput();
      }
    } catch (error) {
      setAndroidSpeechRecordingActive(false);
      Alert.alert("停止录音失败", error instanceof Error ? error.message : "请重试");
    } finally {
      setAndroidSpeechRecordingActive(false);
      setAndroidSpeechDurationSeconds(0);
      speechDetectedRef.current = false;
      silenceStartedAtRef.current = null;
      autoStopInFlightRef.current = false;
    }
  }, [
    androidSpeechRecordingActive,
    buildPendingAudio,
    generateFromCurrentInput,
    isRecording,
    releaseRecorderSafely,
    recordingSeconds,
    resetAudioMode,
    stopLocalSpeechRecognition,
  ]);

  // 静音兜底 tick:录音中每 500ms 触发一次重新评估，确保即使音量事件停发
  // (Android 完全静音时 volumechange 不再来),静音自动停止计时仍能推进到点。
  useEffect(() => {
    if (!isRecording || isGenerating) {
      return;
    }
    const ticker = setInterval(() => {
      setAutoStopTick((value) => value + 1);
    }, 500);
    return () => clearInterval(ticker);
  }, [isRecording, isGenerating]);

  useEffect(() => {
    if (!isRecording || isGenerating) {
      return;
    }
    const now = Date.now();
    if (normalizedMeter >= SPEECH_DETECTED_THRESHOLD) {
      speechDetectedRef.current = true;
      silenceStartedAtRef.current = null;
      return;
    }
    if (!speechDetectedRef.current || recordingSeconds < AUTO_STOP_MIN_SECONDS || autoStopInFlightRef.current) {
      return;
    }
    if (normalizedMeter <= AUTO_STOP_SILENCE_THRESHOLD) {
      if (!silenceStartedAtRef.current) {
        silenceStartedAtRef.current = now;
        return;
      }
      if (now - silenceStartedAtRef.current >= AUTO_STOP_SILENCE_MS) {
        autoStopInFlightRef.current = true;
        setLiveHint("检测到停顿，正在整理语音…");
        void stopRecording(true);
      }
      return;
    }
    silenceStartedAtRef.current = null;
  }, [autoStopTick, isGenerating, isRecording, normalizedMeter, recordingSeconds, stopRecording]);

  const handleClose = useCallback(async () => {
    if (isGenerating) {
      return;
    }
    try {
      if (isRecording) {
        await releaseRecorderSafely();
      }
    } catch {}
    await cancelLocalSpeechRecognition();
    setAndroidSpeechRecordingActive(false);
    setAndroidSpeechDurationSeconds(0);
    await resetAudioMode();
    onClose();
  }, [cancelLocalSpeechRecognition, isGenerating, isRecording, onClose, releaseRecorderSafely, resetAudioMode]);

  useEffect(() => {
    void refreshQueuedCount();
  }, [refreshQueuedCount]);

  useEffect(() => {
    if (!autoStart || autoStartedRef.current) {
      return;
    }
    autoStartedRef.current = true;
    void startRecording();
  }, [autoStart, startRecording]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasInactive = appStateRef.current !== "active";
      appStateRef.current = nextState;
      if (nextState === "active" && wasInactive) {
        void refreshQueuedCount();
      }
    });

    return () => {
      subscription.remove();
    };
  }, [refreshQueuedCount]);

  return (
    <View style={s.overlay} pointerEvents="box-none">
      <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={() => { void handleClose(); }} />

      <View
        pointerEvents="box-none"
        style={[
          s.contentLayer,
          {
            paddingTop: chrome.headerTopPadding + 124,
            paddingBottom: chrome.overlayBottomPadding + 24,
          },
        ]}
      >
        {queuedCount > 0 ? (
          <TouchableOpacity
            style={s.queueBadge}
            activeOpacity={0.7}
            onPress={() => {
              Alert.alert("清理暂存语音", `确定清除 ${queuedCount} 条暂存语音？`, [
                { text: "取消", style: "cancel" },
                {
                  text: "清除",
                  style: "destructive",
                  onPress: async () => {
                    await clearSmartInputQueue();
                    void refreshQueuedCount();
                  },
                },
              ]);
            }}
          >
            <WifiOff size={14} color={palette.reedYellow} />
            <Text style={s.queueBadgeText}>本机还有 {queuedCount} 条暂存语音。点击清除。</Text>
          </TouchableOpacity>
        ) : null}

        <Animated.View
          style={[
            s.panelShell,
            {
              opacity: panelOpacity,
              transform: [{ scale: panelScale }],
            },
          ]}
        >
          <BlurView intensity={32} tint="dark" style={StyleSheet.absoluteFillObject} />
          <View style={s.panelTint} />
          <TouchableOpacity style={s.closeBtn} onPress={() => { void handleClose(); }} activeOpacity={0.8}>
            <X size={18} color="rgba(255,255,255,0.82)" />
          </TouchableOpacity>

          <View style={s.panelContent}>
            <Text style={s.panelEyebrow}>智能输入</Text>

            <View style={s.recorderStage}>
              <View style={s.waveRow}>
                {waveValues.map((value, index) => (
                  <Animated.View
                    key={`wave-${index}`}
                    style={[
                      s.waveBar,
                      index === 3 && s.waveBarAccent,
                      {
                        opacity: isRecording ? 1 : 0.58,
                        transform: [{ scaleY: value }],
                      },
                    ]}
                  />
                ))}
              </View>

              <Animated.View
                pointerEvents="none"
                style={[
                  s.micPulseRing,
                  {
                    opacity: pulseOpacity,
                    transform: [{ scale: pulseScale }],
                  },
                ]}
              />
              <View style={s.transcriptShell}>
                <Text numberOfLines={3} ellipsizeMode="head" style={s.liveText}>
                  {transcriptTail}
                </Text>
              </View>

              <View style={s.controlRow}>
                <TouchableOpacity
                  style={[s.micCircle, isRecording && s.micCircleRecording, isGenerating && s.micCircleBusy]}
                  activeOpacity={0.88}
                  disabled={isGenerating}
                  onPressIn={() => {
                    if (!isGenerating && !isRecording) {
                      void startRecording();
                    }
                  }}
                  onPressOut={() => {
                    if (isRecording) {
                      void stopRecording(true);
                    }
                  }}
                  onPress={() => {
                    if (isRecording) {
                      void stopRecording(true);
                    }
                  }}
                >
                  {isGenerating ? (
                    <ActivityIndicator color={palette.paperRice} />
                  ) : isRecording ? (
                    <Square size={20} color={palette.paperRice} fill={palette.paperRice} />
                  ) : (
                    <Mic size={22} color={palette.paperRice} />
                  )}
                </TouchableOpacity>
                <Text style={s.timerText}>{isRecording ? formatTime(recordingSeconds) : isGenerating ? "整理中..." : "按住说话"}</Text>
              </View>
            </View>

            {warnings.length > 0 ? (
              <ScrollView style={s.warningScroll} contentContainerStyle={s.warningContent}>
                {warnings.map((warning, index) => (
                  <Text key={`${warning}-${index}`} style={s.warningText}>
                    • {warning}
                  </Text>
                ))}
              </ScrollView>
            ) : null}

            <Text style={s.footerHint}>
              {isGenerating
                ? "正在整理本地转写文本。"
                : isRecording
                  ? "波形会跟着音量变化。松手即可结束。"
                  : "按住麦克风说话，松手本地整理。"}
            </Text>
          </View>
        </Animated.View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 60,
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15,23,42,0.14)",
  },
  contentLayer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-start",
    paddingHorizontal: 18,
  },
  queueBadge: {
    width: "100%",
    maxWidth: 336,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "rgba(69,47,15,0.88)",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(248,210,106,0.24)",
    paddingHorizontal: 14,
    paddingVertical: 11,
    marginBottom: 14,
  },
  queueBadgeText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 18,
    color: palette.paperMoon,
    fontWeight: "600",
  },
  panelShell: {
    width: "100%",
    maxWidth: 344,
    borderRadius: 34,
    overflow: "hidden",
    borderWidth: 1.2,
    borderColor: "rgba(255,255,255,0.14)",
    shadowColor: palette.inkBlack,
    shadowOffset: { width: 0, height: 24 },
    shadowOpacity: 0.22,
    shadowRadius: 36,
    elevation: 12,
  },
  panelTint: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(63,69,81,0.88)",
  },
  closeBtn: {
    position: "absolute",
    top: 14,
    right: 14,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.08)",
    zIndex: 2,
  },
  panelContent: {
    paddingHorizontal: 28,
    paddingTop: 20,
    paddingBottom: 22,
    alignItems: "center",
  },
  panelEyebrow: {
    fontSize: 14,
    lineHeight: 17,
    fontWeight: "800",
    color: "rgba(255,255,255,0.94)",
    letterSpacing: 0.3,
    marginBottom: 10,
  },
  recorderStage: {
    width: "100%",
    alignItems: "center",
  },
  micPulseRing: {
    position: "absolute",
    bottom: 14,
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: "rgba(139,132,250,0.18)",
  },
  micCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.inkBlack,
    shadowColor: palette.inkBlack,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.28,
    shadowRadius: 20,
    elevation: 8,
  },
  micCircleRecording: {
    backgroundColor: palette.cinnabar,
    shadowColor: palette.cinnabar,
  },
  micCircleBusy: {
    opacity: 0.9,
  },
  waveRow: {
    height: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 8,
    marginBottom: 18,
  },
  waveBar: {
    width: 7,
    height: 32,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.86)",
  },
  waveBarAccent: {
    backgroundColor: palette.inkBronze,
    shadowColor: palette.inkBronze,
    shadowOpacity: 0.55,
    shadowRadius: 10,
    elevation: 2,
  },
  timerText: {
    fontSize: 13,
    lineHeight: 16,
    fontWeight: "700",
    color: "rgba(226,232,240,0.82)",
    letterSpacing: 1,
  },
  transcriptShell: {
    width: "100%",
    minHeight: 170,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingBottom: 18,
  },
  liveText: {
    minHeight: 116,
    fontSize: 24,
    lineHeight: 42,
    color: "rgba(255,255,255,0.96)",
    textAlign: "center",
    fontWeight: "800",
    letterSpacing: 0.25,
  },
  controlRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    marginTop: 4,
    marginBottom: 8,
  },
  warningScroll: {
    width: "100%",
    maxHeight: 96,
    marginTop: 4,
  },
  warningContent: {
    gap: 6,
  },
  warningText: {
    fontSize: 12,
    lineHeight: 18,
    color: palette.reedYellow,
    textAlign: "center",
  },
  footerHint: {
    marginTop: 12,
    fontSize: 11.5,
    lineHeight: 18,
    color: "rgba(226,232,240,0.72)",
    textAlign: "center",
  },
});
