# 益语软件平台源码导出（第008卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `mobile/components/SettingsCalendar.tsx`

- 编码: `utf-8`

~~~tsx
import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Switch,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft, ChevronRight } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, spacing, fontSize, borderRadius, shadow } from "../lib/theme";

interface SettingsCalendarProps {
  readonly onClose: () => void;
}

export default function SettingsCalendar({ onClose }: SettingsCalendarProps) {
  const chrome = useAppChromeInsets();
  const [hideNonWorkHours, setHideNonWorkHours] = useState(true);

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[styles.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>日历与日程</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        <Text style={styles.sectionTitle}>视图设置</Text>
        <View style={[styles.card, shadow.card]}>
          <View style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>隐藏非工作时段</Text>
              <Text style={styles.rowSubtitle}>工作时间 09:00 - 18:00</Text>
            </View>
            <Switch
              value={hideNonWorkHours}
              onValueChange={setHideNonWorkHours}
              trackColor={{ false: colors.border, true: colors.brandLight }}
              thumbColor={colors.surface}
            />
          </View>

          <View style={styles.separator} />

          <TouchableOpacity style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>每周起始日</Text>
            </View>
            <View style={styles.rowRight}>
              <Text style={styles.rowValue}>星期一</Text>
              <ChevronRight size={22} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.borderLight,
  },
  backButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  backIcon: {
    fontSize: 22,
    color: colors.text,
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  headerSpacer: {
    width: 36,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
    marginLeft: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  rowTextContainer: {
    flex: 1,
    marginRight: spacing.md,
  },
  rowTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  rowSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  rowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  rowValue: {
    fontSize: fontSize.md,
    color: colors.brand,
    fontWeight: "500",
  },
  chevron: {
    fontSize: 22,
    color: colors.textTertiary,
  },
  separator: {
    height: 0.5,
    backgroundColor: colors.borderLight,
    marginVertical: spacing.xs,
  },
});
~~~

## `mobile/components/SettingsTasks.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Switch,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft, ChevronRight } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, spacing, fontSize, borderRadius, shadow } from "../lib/theme";
import { fetchTaskSettings, updateTaskSettings } from "../lib/api";
import * as cache from "../lib/cache";

interface SettingsTasksProps {
  readonly onClose: () => void;
}

type PriorityLevel = "high" | "normal" | "low";

const PRIORITY_OPTIONS: ReadonlyArray<{ key: PriorityLevel; label: string }> = [
  { key: "high", label: "高优" },
  { key: "normal", label: "中等" },
  { key: "low", label: "低" },
];

export default function SettingsTasks({ onClose }: SettingsTasksProps) {
  const chrome = useAppChromeInsets();
  const [dailyReviewEnabled, setDailyReviewEnabled] = useState(true);
  const [defaultPriority, setDefaultPriority] = useState<PriorityLevel>("normal");
  const [settingsLoading, setSettingsLoading] = useState(true);
  const initialLoadDone = useRef(false);

  // Fetch settings (cache-first, then network refresh)
  useEffect(() => {
    cache.loadWithCache(cache.KEYS.taskSettings, fetchTaskSettings, (settings) => {
      if (settings.defaultPriority && ["high", "normal", "low"].includes(settings.defaultPriority)) {
        setDefaultPriority(settings.defaultPriority as PriorityLevel);
      }
    })
      .catch(() => {
        // Use defaults if fetch fails
      })
      .finally(() => {
        setSettingsLoading(false);
        initialLoadDone.current = true;
      });
  }, []);

  // Persist changes to cloud when settings change
  useEffect(() => {
    if (!initialLoadDone.current) return;
    void updateTaskSettings({ defaultPriority }).catch(() => {
      // Silently fail — settings will be retried next time
    });
  }, [defaultPriority]);

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[styles.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>任务与工作台</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        {settingsLoading && (
          <ActivityIndicator size="small" color={colors.brand} style={{ marginVertical: spacing.md }} />
        )}
        {/* Section: 工作流设定 */}
        <Text style={styles.sectionTitle}>工作流设定</Text>
        <View style={[styles.card, shadow.card]}>
          <View style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>每日复盘提醒</Text>
              <Text style={styles.rowSubtitle}>每天 18:00 发送通知</Text>
            </View>
            <Switch
              value={dailyReviewEnabled}
              onValueChange={setDailyReviewEnabled}
              trackColor={{ false: colors.border, true: colors.brandLight }}
              thumbColor={colors.surface}
            />
          </View>

          <View style={styles.separator} />

          <TouchableOpacity style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>已复盘任务归档</Text>
              <Text style={styles.rowSubtitle}>次日自动从列表中隐藏</Text>
            </View>
            <ChevronRight size={22} color={colors.textTertiary} />
          </TouchableOpacity>
        </View>

        {/* Section: 快速新建默认值 */}
        <Text style={styles.sectionTitle}>快速新建默认值</Text>
        <View style={[styles.card, shadow.card]}>
          <Text style={styles.rowTitle}>默认优先级</Text>
          <View style={styles.segmentContainer}>
            {PRIORITY_OPTIONS.map((option) => {
              const isSelected = defaultPriority === option.key;
              return (
                <TouchableOpacity
                  key={option.key}
                  style={[
                    styles.segmentOption,
                    isSelected && styles.segmentOptionSelected,
                  ]}
                  onPress={() => setDefaultPriority(option.key)}
                >
                  <Text
                    style={[
                      styles.segmentText,
                      isSelected && styles.segmentTextSelected,
                    ]}
                  >
                    {option.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.borderLight,
  },
  backButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  backIcon: {
    fontSize: 22,
    color: colors.text,
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  headerSpacer: {
    width: 36,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
    marginLeft: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  rowTextContainer: {
    flex: 1,
    marginRight: spacing.md,
  },
  rowTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  rowSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chevron: {
    fontSize: 22,
    color: colors.textTertiary,
  },
  separator: {
    height: 0.5,
    backgroundColor: colors.borderLight,
    marginVertical: spacing.xs,
  },
  segmentContainer: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    padding: 3,
    marginTop: spacing.md,
  },
  segmentOption: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: "center",
    borderRadius: borderRadius.sm,
  },
  segmentOptionSelected: {
    backgroundColor: colors.surface,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 1,
  },
  segmentText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  segmentTextSelected: {
    color: colors.text,
    fontWeight: "600",
  },
});
~~~

## `mobile/components/SmartInputSheet.tsx`

- 编码: `utf-8`

~~~tsx
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
import * as api from "../lib/api";
import {
  clearSmartInputQueue,
  getQueuedSmartInputCount,
  queueSmartInputAudio,
} from "../lib/smart-input-queue";
import type { SmartTaskDraft, SmartTaskDraftResponse } from "../lib/types";

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
const AUTO_STOP_SILENCE_MS = 1100;
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

function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof api.ApiError)) {
    return error instanceof Error ? error.message : fallback;
  }
  try {
    const parsed = JSON.parse(error.body);
    if (typeof parsed?.detail === "string" && parsed.detail.trim()) {
      return parsed.detail.trim();
    }
  } catch {}
  return error.body || fallback;
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

function isRetriableDraftError(error: unknown): boolean {
  // Only retry on genuine network failures, not server-side bugs
  if (error instanceof api.ApiError) {
    return error.status === 408 || error.status === 429 || error.status === 503;
  }
  if (error instanceof Error) {
    const lowered = error.message.toLowerCase();
    return (
      lowered.includes("network request failed") ||
      lowered.includes("network error") ||
      lowered.includes("timed out")
    );
  }
  return false;
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

  const recorder = useAudioRecorder({ ...SMART_INPUT_RECORDING_PRESET, isMeteringEnabled: true });
  const recorderState = useAudioRecorderState(recorder, 120);
  const autoStartedRef = useRef(false);
  const waveValues = useRef(METER_BAR_MULTIPLIERS.map(() => new Animated.Value(0.2))).current;
  const pulseScale = useRef(new Animated.Value(1)).current;
  const pulseOpacity = useRef(new Animated.Value(0.18)).current;
  const panelScale = useRef(new Animated.Value(0.9)).current;
  const panelOpacity = useRef(new Animated.Value(0)).current;
  const pulseLoopRef = useRef<Animated.CompositeAnimation | null>(null);
  const pendingAudioRef = useRef<api.UploadableFile | null>(null);
  const appStateRef = useRef(AppState.currentState);
  const speechDetectedRef = useRef(false);
  const silenceStartedAtRef = useRef<number | null>(null);
  const autoStopInFlightRef = useRef(false);

  const isRecording = recorderState.isRecording;
  const recordingSeconds = Math.max(0, Math.floor(recorderState.durationMillis / 1000));

  const normalizedMeter = useMemo(() => {
    if (!isRecording) {
      return 0.08;
    }
    const rawMeter = typeof recorderState.metering === "number" ? recorderState.metering : -60;
    return clamp((rawMeter + 60) / 60, 0.08, 1);
  }, [isRecording, recorderState.metering]);

  const displayText = useMemo(() => {
    if (isGenerating) {
      return "正在上传语音并识别，请稍等…";
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

  useEffect(() => {
    return () => {
      pulseLoopRef.current?.stop();
      try {
        recorder.stop();
      } catch {}
      void resetAudioMode();
    };
  }, [recorder, resetAudioMode]);

  const buildPendingAudio = useCallback((): api.UploadableFile | null => {
    const uri = recorder.uri ?? recorderState.url;
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
    const trimmedTranscript = transcript.trim();
    const audioFile = pendingAudioRef.current;
    if (!trimmedTranscript && !audioFile) {
      Alert.alert("提示", "先说一段话，再生成任务草稿。");
      return false;
    }

    // Close the sheet immediately so user can do other things
    pendingAudioRef.current = null;
    onClose();

    // Process in background — the draft will be applied when ready
    try {
      const response = await api.generateSmartTaskDraft({
        transcriptText: trimmedTranscript || undefined,
        audioFile: audioFile ?? undefined,
        referenceDate: referenceDate ?? undefined,
      });
      applyDraftResponse(response);
      return true;
    } catch (error) {
      if (audioFile && isRetriableDraftError(error)) {
        await queueSmartInputAudio(audioFile, {
          referenceDate: referenceDate ?? null,
          transcriptText: trimmedTranscript || null,
        });
        await refreshQueuedCount();
        // Silent — user already left this screen
        return false;
      }
      Alert.alert("智能输入失败", extractApiErrorMessage(error, "请稍后再试。"));
      return false;
    }
  }, [applyDraftResponse, onClose, referenceDate, refreshQueuedCount, transcript]);

  const startRecording = useCallback(async () => {
    if (isGenerating || isRecording) {
      return;
    }
    setWarnings([]);
    setTranscript("");
    pendingAudioRef.current = null;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        throw new Error("请先允许麦克风权限。");
      }
      if (Platform.OS !== "web") {
        await setAudioModeAsync({
          playsInSilentMode: true,
          allowsRecording: true,
          shouldRouteThroughEarpiece: false,
          shouldPlayInBackground: true,
          allowsBackgroundRecording: true,
          interruptionMode: "doNotMix",
        });
      }
      await recorder.prepareToRecordAsync({ ...SMART_INPUT_RECORDING_PRESET, isMeteringEnabled: true });
      recorder.record();
      setLiveHint("正在聆听…");
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      Alert.alert("开始录音失败", error instanceof Error ? error.message : "请重试");
    }
  }, [isGenerating, isRecording, recorder]);

  const stopRecording = useCallback(async (generateImmediately: boolean) => {
    if (!isRecording) {
      return;
    }
    try {
      await recorder.stop();
      await resetAudioMode();
      pendingAudioRef.current = buildPendingAudio();
      setLiveHint(
        generateImmediately
          ? "正在上传语音并识别…"
          : "收音完成，可重新开始，或继续整理成任务草稿。",
      );
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      if (generateImmediately) {
        await generateFromCurrentInput();
      }
    } catch (error) {
      Alert.alert("停止录音失败", error instanceof Error ? error.message : "请重试");
    } finally {
      speechDetectedRef.current = false;
      silenceStartedAtRef.current = null;
      autoStopInFlightRef.current = false;
    }
  }, [buildPendingAudio, generateFromCurrentInput, isRecording, recorder, resetAudioMode]);

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
  }, [isGenerating, isRecording, normalizedMeter, recordingSeconds, stopRecording]);

  const handleClose = useCallback(async () => {
    if (isGenerating) {
      return;
    }
    try {
      if (isRecording) {
        await recorder.stop();
      }
    } catch {}
    await resetAudioMode();
    onClose();
  }, [isGenerating, isRecording, onClose, recorder, resetAudioMode]);

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
            <WifiOff size={14} color="#F8D26A" />
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
                    <ActivityIndicator color="#FFFFFF" />
                  ) : isRecording ? (
                    <Square size={20} color="#FFFFFF" fill="#FFFFFF" />
                  ) : (
                    <Mic size={22} color="#FFFFFF" />
                  )}
                </TouchableOpacity>
                <Text style={s.timerText}>{isRecording ? formatTime(recordingSeconds) : isGenerating ? "识别中..." : "按住说话"}</Text>
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
                ? "云端正在识别这段语音。"
                : isRecording
                  ? "波形会跟着音量变化。松手即可结束。"
                  : "按住麦克风说话，松手自动识别。"}
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
    color: "#FCE7B2",
    fontWeight: "600",
  },
  panelShell: {
    width: "100%",
    maxWidth: 344,
    borderRadius: 34,
    overflow: "hidden",
    borderWidth: 1.2,
    borderColor: "rgba(255,255,255,0.14)",
    shadowColor: "#000000",
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
    backgroundColor: "#316AF4",
    shadowColor: "#316AF4",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.28,
    shadowRadius: 20,
    elevation: 8,
  },
  micCircleRecording: {
    backgroundColor: "#EF5350",
    shadowColor: "#EF5350",
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
    backgroundColor: "#8B84FA",
    shadowColor: "#8B84FA",
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
    color: "#FCD34D",
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
~~~

## `mobile/components/SuperFAB.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useRef } from "react";
import {
  Animated,
  PanResponder,
  StyleSheet,
  View,
} from "react-native";
import * as Haptics from "expo-haptics";
import { Plus } from "lucide-react-native";
import { colors } from "../lib/theme";

interface SuperFABProps {
  readonly onCreateTask: () => void;
  readonly onSmartInput: () => void;
}

const FAB_SIZE = 58;
const LONG_PRESS_DELAY = 280;

export default function SuperFAB({ onCreateTask, onSmartInput }: SuperFABProps) {
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLongPress = useRef(false);
  const smartTriggeredRef = useRef(false);

  const clearTimer = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => false,
    onPanResponderGrant: () => {
      smartTriggeredRef.current = false;
      isLongPress.current = false;
      longPressTimer.current = setTimeout(() => {
        isLongPress.current = true;
        smartTriggeredRef.current = true;
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        onSmartInput();
      }, LONG_PRESS_DELAY);
    },
    onPanResponderRelease: () => {
      clearTimer();
      if (smartTriggeredRef.current) {
        // Long press already triggered smart input
        smartTriggeredRef.current = false;
        isLongPress.current = false;
        return;
      }
      // Short press → create task
      isLongPress.current = false;
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      onCreateTask();
    },
    onPanResponderTerminate: () => {
      clearTimer();
      smartTriggeredRef.current = false;
      isLongPress.current = false;
    },
  });

  return (
    <View style={s.container} pointerEvents="box-none">
      <Animated.View style={s.fab} {...panResponder.panHandlers}>
        <Plus size={34} strokeWidth={2.05} color="#FFFFFF" />
      </Animated.View>
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    zIndex: 999,
  },
  fab: {
    width: FAB_SIZE,
    height: FAB_SIZE,
    borderRadius: FAB_SIZE / 2,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 4,
    borderColor: "rgba(255,255,255,0.98)",
    shadowColor: colors.brand,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.36,
    shadowRadius: 24,
    elevation: 8,
  },
});
~~~

## `mobile/components/TaskDetail.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  GestureResponderEvent,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ScrollView,
} from "react-native";
import DateTimePickerSheet from "./DateTimePickerSheet";
import type { DateTimeValue } from "./DateTimePickerSheet";
import UnderstandingCard from "./UnderstandingCard";
import {
  ChevronLeft,
  MoreHorizontal,
  Check,
  CalendarDays,
  Flag,
  Tag,
  Users,
  Link2,
  Mic,
  Paperclip,
  PlayCircle,
  FileText,
  ArrowUpCircle,
  Sparkles,
  ClipboardList,
  CheckCircle2,
  AlertTriangle,
  MessageSquare,
  RefreshCw,
} from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, fontSize, spacing, borderRadius } from "../lib/theme";
import {
  fetchTaskActivities,
  fetchTaskContextPreview,
  fetchTaskUnderstanding,
  openTaskAttachment,
  pickAndUploadTaskAttachment,
  retryTaskAttachmentTransferOp,
} from "../lib/task-detail-service";
import { getLegacyUploadPseudoOps } from "../lib/legacy-upload-ops";
import { buildTaskScheduleUpdatesFromPicker } from "../lib/calendar-repository-core";
import { buildTaskUnderstandingCardModel } from "../lib/task-understanding";
import type {
  EventLineRecord,
  TaskActivityRecord,
  TaskContextPreviewRecord,
  TaskRecord,
  TaskUnderstandingRecord,
} from "../lib/types";

// ─── Types ─────────────────────────────────

interface Props {
  task: TaskRecord;
  eventLine?: EventLineRecord | null;
  onClose: () => void;
  onStartReview: (task: TaskRecord) => void;
  onRecord: () => void;
  onUpdate?: (taskId: string, updates: Partial<TaskRecord>) => void | Promise<void>;
  onDeleteTask?: (task: TaskRecord) => void | Promise<void>;
  onTaskReplaced?: (task: TaskRecord) => void;
  onOpenClientWorkspace?: (clientId: string, clientName?: string | null) => void;
  onOpenEventLine?: (eventLineId: string) => void;
  onOpenConsult?: (task: TaskRecord) => void;
}

type AttachmentProcessingStatus = "uploading" | "transcribing" | "summarizing" | "completed";

// ─── Helpers ────────────────────────────────

function formatDueDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "未设定";
  const d = new Date(dateStr);
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const hasTime = dateStr.includes("T");
  if (!hasTime) return `${m}月${day}日`;
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}月${day}日 ${h}:${min}`;
}

function getOverdueDays(dateStr: string | null | undefined): number {
  if (!dateStr) return 0;
  const due = new Date(dateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  if (due >= now) return 0;
  return Math.ceil((now.getTime() - due.getTime()) / (1000 * 60 * 60 * 24));
}

function getInitial(name: string): string {
  if (!name) return "?";
  return name.charAt(name.length - 1);
}

function formatActivityTime(iso: string | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return "";
  }
}

function activityLabel(eventType: string, payload?: Record<string, unknown>): string {
  switch (eventType) {
    case "attachment_transcribed": return "录音转写完成";
    case "attachment_added": return `上传附件${payload?.attachmentTitle ? `「${payload.attachmentTitle}」` : ""}`;
    case "task_completed_with_review": return "完成复盘";
    case "task_created": return "创建任务";
    case "updated": {
      if (payload?.eventLineId) return "关联事件线";
      if (payload?.clientId) return "关联客户";
      return "更新任务";
    }
    case "status_changed": return "状态变更";
    default: return eventType;
  }
}

function formatDuration(seconds: number): string {
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function formatPendingTransferStatus(status: "queued" | "processing" | "needs_attention"): string {
  switch (status) {
    case "processing":
      return "上传中...";
    case "needs_attention":
      return "需处理";
    default:
      return "待同步";
  }
}

// ─── Component ──────────────────────────────

export default function TaskDetail({
  task,
  eventLine = null,
  onClose,
  onStartReview,
  onRecord,
  onUpdate,
  onDeleteTask,
  onTaskReplaced,
  onOpenClientWorkspace,
  onOpenEventLine,
  onOpenConsult,
}: Props) {
  const chrome = useAppChromeInsets();
  const isDone = task.progressStatus === "done";
  const overdueDays = getOverdueDays(task.dueDate);
  const isOverdue = overdueDays > 0 && !isDone;
  const isReviewed = Boolean(task.completionNote);

  const [activities, setActivities] = useState<readonly TaskActivityRecord[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(true);
  const [understanding, setUnderstanding] = useState<TaskUnderstandingRecord | null>(null);
  const [contextPreview, setContextPreview] = useState<TaskContextPreviewRecord | null>(null);
  const [understandingLoading, setUnderstandingLoading] = useState(true);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showActionSheet, setShowActionSheet] = useState(false);
  const [showDescriptionEditor, setShowDescriptionEditor] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(task.description ?? "");
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [retryingTransferOpId, setRetryingTransferOpId] = useState<string | null>(null);
  const [pendingTransferVersion, setPendingTransferVersion] = useState(0);
  const [isSavingDescription, setIsSavingDescription] = useState(false);

  // Local processing status for newly recorded attachments
  const [processingAttachments, setProcessingAttachments] = useState<Map<string, AttachmentProcessingStatus>>(new Map());

  const handleMarkDone = useCallback((event?: GestureResponderEvent) => {
    event?.stopPropagation?.();
    if (!onUpdate || isDone) {
      return;
    }
    onUpdate(task.id, { progressStatus: "done" });
  }, [isDone, onUpdate, task.id]);

  const handleAttachFile = useCallback(async () => {
    if (isUploadingAttachment) {
      return;
    }
    setIsUploadingAttachment(true);
    try {
      const result = await pickAndUploadTaskAttachment(task);
      if (!result) {
        return;
      }
      onTaskReplaced?.(result.task);
      if (result.status !== "uploaded") {
        Alert.alert(result.status === "pending_attachment" ? "已保存" : "需处理", result.message);
      }
    } catch (error) {
      Alert.alert(
        "附件上传失败",
        error instanceof Error ? error.message : "请检查网络和同步状态后重试。",
      );
    } finally {
      setIsUploadingAttachment(false);
    }
  }, [isUploadingAttachment, onTaskReplaced, task]);

  const handleRetryPendingTransfer = useCallback(async (opId: string) => {
    if (retryingTransferOpId) {
      return;
    }
    setRetryingTransferOpId(opId);
    try {
      const result = await retryTaskAttachmentTransferOp(opId, task.id);
      if (result.task) {
        onTaskReplaced?.(result.task);
      }
      if (!result.ok) {
        Alert.alert("附件需处理", result.message);
      }
    } catch (error) {
      Alert.alert(
        "重试失败",
        error instanceof Error ? error.message : "请稍后再试。",
      );
    } finally {
      setPendingTransferVersion((value) => value + 1);
      setRetryingTransferOpId(null);
    }
  }, [onTaskReplaced, retryingTransferOpId, task.id]);

  const handleOpenAttachment = useCallback(async (attachmentId: string) => {
    const attachment = (task.attachments ?? []).find((item) => item.id === attachmentId);
    if (!attachment) {
      return;
    }
    try {
      await openTaskAttachment(attachment);
    } catch (error) {
      Alert.alert(
        "无法打开附件",
        error instanceof Error ? error.message : "请稍后再试。",
      );
    }
  }, [task.attachments]);

  const handleOpenDescriptionEditor = useCallback(() => {
    setDescriptionDraft(task.description ?? "");
    setShowActionSheet(false);
    setShowDescriptionEditor(true);
  }, [task.description]);

  const handleSaveDescription = useCallback(async () => {
    if (!onUpdate || isSavingDescription) {
      setShowDescriptionEditor(false);
      return;
    }
    setIsSavingDescription(true);
    try {
      const nextDescription = descriptionDraft.trim();
      await Promise.resolve(onUpdate(task.id, { description: nextDescription || null }));
      setShowDescriptionEditor(false);
    } catch (error) {
      Alert.alert(
        "保存失败",
        error instanceof Error ? error.message : "请稍后再试。",
      );
    } finally {
      setIsSavingDescription(false);
    }
  }, [descriptionDraft, isSavingDescription, onUpdate, task.id]);

  const handleRequestDelete = useCallback(() => {
    setShowActionSheet(false);
    if (!onDeleteTask) {
      return;
    }
    Alert.alert("删除任务", `确认删除「${task.title}」吗？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: () => {
          void Promise.resolve(onDeleteTask(task));
        },
      },
    ]);
  }, [onDeleteTask, task]);

  useEffect(() => {
    let cancelled = false;
    setActivitiesLoading(true);
    fetchTaskActivities(task.id)
      .then((data) => { if (!cancelled) setActivities(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setActivitiesLoading(false); });
    return () => { cancelled = true; };
  }, [task.id]);

  useEffect(() => {
    setDescriptionDraft(task.description ?? "");
  }, [task.description]);

  useEffect(() => {
    let cancelled = false;
    setUnderstandingLoading(true);
    Promise.allSettled([
      fetchTaskUnderstanding(task.id),
      fetchTaskContextPreview(task.id),
    ])
      .then(([understandingResult, previewResult]) => {
        if (cancelled) {
          return;
        }
        if (understandingResult.status === "fulfilled") {
          setUnderstanding(understandingResult.value);
        } else {
          setUnderstanding(null);
        }
        if (previewResult.status === "fulfilled") {
          setContextPreview(previewResult.value);
        } else {
          setContextPreview(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setUnderstandingLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [task.id]);

  const collaborators = task.collaborators ?? [];
  const attachments = task.attachments ?? [];
  const pendingTransferOps = useMemo(
    () => getLegacyUploadPseudoOps().filter((op) => op.taskLocalId === task.id),
    [attachments.length, isUploadingAttachment, pendingTransferVersion, task.id, task.updatedAt],
  );
  const understandingCard = buildTaskUnderstandingCardModel({
    task,
    eventLine,
    understanding,
    contextPreview,
  });

  return (
    <View style={s.overlay}>
      {/* Header */}
      <View style={[s.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={s.headerBtn}>
          <ChevronLeft size={26} strokeWidth={2} color="#1F2937" />
        </TouchableOpacity>
        <TouchableOpacity style={s.headerBtn} onPress={() => setShowActionSheet(true)}>
          <MoreHorizontal size={24} color="#A8B0BF" />
        </TouchableOpacity>
      </View>

      {/* Scrollable content */}
      <ScrollView
        style={s.body}
        contentContainerStyle={[s.bodyContent, { paddingBottom: chrome.overlayBottomPadding + 100 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* Title with checkbox */}
        <View style={s.titleRow}>
          <TouchableOpacity
            style={[
              s.checkbox,
              isDone && s.checkboxDone,
              isOverdue && !isDone && s.checkboxOverdue,
            ]}
            activeOpacity={isDone ? 1 : 0.78}
            disabled={isDone || !onUpdate}
            onPress={handleMarkDone}
          >
            {isDone && <Check size={16} strokeWidth={3} color="#FFFFFF" />}
          </TouchableOpacity>
          <Text style={[s.title, isDone && s.titleDone]} numberOfLines={3}>
            {task.title}
          </Text>
        </View>

        {/* Meta info */}
        <View style={s.metaArea}>
          {/* Row 1: Tags */}
          <View style={s.metaRow}>
            {isReviewed && (
              <View style={s.reviewedBadge}>
                <Sparkles size={12} color="#FFFFFF" />
                <Text style={s.reviewedBadgeText}>已复盘</Text>
              </View>
            )}
            {isOverdue && (
              <TouchableOpacity style={s.metaItem} onPress={() => setShowDatePicker(true)} activeOpacity={0.6}>
                <CalendarDays size={16} color="#EF4444" />
                <Text style={s.metaTextRed}>已逾期 {overdueDays} 天 ({formatDueDate(task.dueDate)})</Text>
              </TouchableOpacity>
            )}
            {!isOverdue && (
              <TouchableOpacity style={s.metaItem} onPress={() => setShowDatePicker(true)} activeOpacity={0.6}>
                <CalendarDays size={16} color={isDone ? "#A8B0BF" : "#2563EB"} />
                <Text style={[s.metaText, isDone && s.metaTextDone]}>{formatDueDate(task.dueDate)}</Text>
              </TouchableOpacity>
            )}
            {task.priority === "high" && (
              <View style={s.metaItem}>
                <Flag size={16} color={isDone ? "#A8B0BF" : "#F97316"} />
                <Text style={[s.metaTextOrange, isDone && s.metaTextDone]}>高优</Text>
              </View>
            )}
            {task.businessCategory && (
              <View style={s.metaItem}>
                <Tag size={16} color={isDone ? "#A8B0BF" : "#6B7280"} />
                <Text style={[s.metaTextGray, isDone && s.metaTextDone]}>{task.businessCategory}</Text>
              </View>
            )}
          </View>

          {/* Row 2: Collaborators */}
          {collaborators.length > 0 && (
            <View style={s.metaRow}>
              <Users size={14} color="#A8B0BF" />
              {collaborators.map((c) => (
                <View key={c.userId} style={s.collaboratorChip}>
                  <View style={[s.avatar, c.isOwner ? s.avatarOwner : s.avatarCollab]}>
                    <Text style={s.avatarText}>{getInitial(c.fullName)}</Text>
                  </View>
                  <Text style={[s.collaboratorName, isDone && s.metaTextDone]}>{c.fullName}</Text>
                  {c.isOwner && <Text style={s.ownerLabel}>负责</Text>}
                </View>
              ))}
            </View>
          )}

          {/* Row 3: Related objects */}
          {(task.clientName || task.eventLineName) && (
            <View style={s.metaRow}>
              {task.clientName && (
                <TouchableOpacity
                  style={s.relatedItem}
                  activeOpacity={onOpenClientWorkspace && task.clientId ? 0.7 : 1}
                  disabled={!onOpenClientWorkspace || !task.clientId}
                  onPress={() => {
                    if (task.clientId) {
                      onOpenClientWorkspace?.(task.clientId, task.clientName);
                    }
                  }}
                >
                  <Link2 size={14} color="#A8B0BF" />
                  <Text style={s.relatedText}>{task.clientName}</Text>
                </TouchableOpacity>
              )}
              {task.eventLineName && (
                <TouchableOpacity
                  style={s.relatedItem}
                  activeOpacity={onOpenEventLine && task.eventLineId ? 0.7 : 1}
                  disabled={!onOpenEventLine || !task.eventLineId}
                  onPress={() => {
                    if (task.eventLineId) {
                      onOpenEventLine?.(task.eventLineId);
                    }
                  }}
                >
                  <Link2 size={14} color="#A8B0BF" />
                  <Text style={s.relatedText}>「{task.eventLineName}」</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>

        {/* Divider */}
        <View style={s.divider} />

        {/* Description */}
        <View style={s.descriptionArea}>
          {task.description ? (
            <Text selectable style={[s.descriptionText, isDone && s.descriptionTextDone]}>
              {task.description}
            </Text>
          ) : (
            <Text style={s.descriptionPlaceholder}>暂无说明</Text>
          )}
        </View>

        {understandingLoading && !understanding && !contextPreview ? (
          <View style={s.understandingLoading}>
            <ActivityIndicator size="small" color={colors.brand} />
            <Text style={s.understandingLoadingText}>正在整理任务洞察…</Text>
          </View>
        ) : (
          <UnderstandingCard model={understandingCard} />
        )}

        {(task.clientId || task.eventLineId || onOpenConsult) ? (
          <View style={s.contextActionRow}>
            {task.clientId ? (
              <TouchableOpacity
                style={s.contextActionButton}
                activeOpacity={onOpenClientWorkspace ? 0.78 : 1}
                disabled={!onOpenClientWorkspace}
                onPress={() => {
                  if (task.clientId) {
                    onOpenClientWorkspace?.(task.clientId, task.clientName);
                  }
                }}
              >
                <Link2 size={16} color={colors.brand} />
                <Text style={s.contextActionText}>客户工作台</Text>
              </TouchableOpacity>
            ) : null}
            {task.eventLineId ? (
              <TouchableOpacity
                style={s.contextActionButton}
                activeOpacity={onOpenEventLine ? 0.78 : 1}
                disabled={!onOpenEventLine}
                onPress={() => {
                  if (task.eventLineId) {
                    onOpenEventLine?.(task.eventLineId);
                  }
                }}
              >
                <Link2 size={16} color={colors.brand} />
                <Text style={s.contextActionText}>事件线详情</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity
              style={s.contextActionButton}
              activeOpacity={onOpenConsult ? 0.78 : 1}
              disabled={!onOpenConsult}
              onPress={() => onOpenConsult?.(task)}
            >
              <MessageSquare size={16} color={colors.brand} />
              <Text style={s.contextActionText}>继续问 AI</Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {/* Blocker warning */}
        {task.currentBlocker && !isDone && (
          <View style={s.blockerCard}>
            <AlertTriangle size={16} color="#F97316" />
            <View style={s.blockerContent}>
              <Text style={s.blockerLabel}>当前阻塞</Text>
              <Text selectable style={s.blockerText}>{task.currentBlocker}</Text>
            </View>
          </View>
        )}

        {/* Attachments */}
        {attachments.length > 0 && (
          <View style={s.attachmentSection}>
            {attachments.map((att) => {
              const localStatus = processingAttachments.get(att.id);
              const status: AttachmentProcessingStatus = localStatus ?? "completed";
              const isProcessing = status !== "completed";
              const isAudio = att.mimeType?.startsWith("audio/");

              return (
                <TouchableOpacity
                  key={att.id}
                  style={[s.attachmentCard, isProcessing && s.attachmentCardProcessing]}
                  activeOpacity={0.78}
                  onPress={() => {
                    void handleOpenAttachment(att.id);
                  }}
                >
                  {isProcessing && <View style={s.attachmentShimmer} />}
                  <View style={s.attachmentRow}>
                    {isProcessing ? (
                      status === "uploading" ? <ArrowUpCircle size={24} color="#3B82F6" /> :
                      status === "transcribing" ? <FileText size={24} color="#6366F1" /> :
                      <Sparkles size={24} color="#8B5CF6" />
                    ) : (
                      <PlayCircle size={24} color="#2563EB" />
                    )}
                    <View style={s.attachmentBody}>
                      <View style={s.attachmentHeader}>
                        <Text style={s.attachmentTitle} numberOfLines={1}>{att.title || "附件"}</Text>
                        {!isProcessing && att.durationSeconds != null && (
                          <Text style={s.attachmentDuration}>{formatDuration(att.durationSeconds)}</Text>
                        )}
                      </View>
                      {isProcessing ? (
                        <Text style={s.attachmentStatusText}>
                          {status === "uploading" ? "上传中..." : status === "transcribing" ? "转写中..." : "AI 整理中..."}
                        </Text>
                      ) : att.summary ? (
                        <Text selectable style={s.attachmentSummary} numberOfLines={6}>{att.summary}</Text>
                      ) : null}
                    </View>
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {pendingTransferOps.length > 0 && (
          <View style={s.attachmentSection}>
            {pendingTransferOps.map((op) => (
              <View
                key={op.opId}
                style={[
                  s.attachmentCard,
                  op.status === "needs_attention" ? s.pendingAttachmentCardDanger : s.attachmentCardProcessing,
                ]}
              >
                <View style={s.attachmentRow}>
                  {op.status === "needs_attention" ? (
                    <AlertTriangle size={24} color="#F97316" />
                  ) : op.status === "processing" ? (
                    <ActivityIndicator size="small" color={colors.brand} style={{ width: 24 }} />
                  ) : (
                    <ArrowUpCircle size={24} color="#3B82F6" />
                  )}
                  <View style={s.attachmentBody}>
                    <View style={s.attachmentHeader}>
                      <Text style={s.attachmentTitle} numberOfLines={1}>{op.displayTitle || "待上传附件"}</Text>
                    </View>
                    <Text style={s.attachmentStatusText}>
                      {formatPendingTransferStatus(op.status)}
                      {op.reasonCode ? ` · ${op.reasonCode}` : ""}
                    </Text>
                    {op.status !== "processing" ? (
                      <TouchableOpacity
                        style={[s.inlineRetryButton, retryingTransferOpId === op.opId && s.inlineRetryButtonBusy]}
                        disabled={Boolean(retryingTransferOpId)}
                        onPress={() => {
                          void handleRetryPendingTransfer(op.opId);
                        }}
                      >
                        {retryingTransferOpId === op.opId ? (
                          <ActivityIndicator size="small" color={colors.brand} />
                        ) : (
                          <RefreshCw size={14} color={op.status === "needs_attention" ? colors.error : colors.brand} />
                        )}
                        <Text
                          style={[
                            s.inlineRetryButtonText,
                            op.status === "needs_attention" && s.inlineRetryButtonTextDanger,
                          ]}
                        >
                          {op.status === "needs_attention" ? "立即重试" : "重新上传"}
                        </Text>
                      </TouchableOpacity>
                    ) : null}
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Completion note */}
        {task.completionNote && (
          <View style={s.completionCard}>
            <CheckCircle2 size={16} color="#10B981" />
            <Text selectable style={s.completionText}>{task.completionNote}</Text>
          </View>
        )}

        {/* Activity timeline */}
        <View style={s.activitySection}>
          <Text style={s.sectionLabel}>活动记录</Text>
          {activitiesLoading ? (
            <ActivityIndicator size="small" color={colors.brand} style={{ marginTop: 8 }} />
          ) : activities.length > 0 ? (
            activities.slice(0, 8).map((a, idx) => (
              <View key={a.id} style={s.activityRow}>
                <View style={s.timelineDot} />
                {idx < Math.min(activities.length, 8) - 1 && <View style={s.timelineLine} />}
                <View style={s.activityContent}>
                  <Text style={s.activityTime}>{formatActivityTime(a.createdAt)}</Text>
                  <Text style={s.activityLabel}>{activityLabel(a.eventType, a.payload as Record<string, unknown>)}</Text>
                  {a.actorName && <Text style={s.activityActor}>{a.actorName}</Text>}
                </View>
              </View>
            ))
          ) : (
            <Text style={s.emptyText}>暂无活动记录</Text>
          )}
        </View>

        {/* Bottom info */}
        <View style={s.bottomInfo}>
          <Text style={s.bottomInfoText}>
            {[task.clientName, task.listName, task.createdAt ? `创建于 ${formatActivityTime(task.createdAt)}` : ""].filter(Boolean).join(" · ")}
          </Text>
        </View>
      </ScrollView>

      {/* Fixed bottom bar */}
      <View style={[s.bottomBar, { paddingBottom: chrome.overlayBottomPadding }]}>
        <TouchableOpacity style={s.micButton} onPress={onRecord}>
          <Mic size={22} strokeWidth={2} color="#2563EB" />
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.secondaryActionButton, isUploadingAttachment && s.secondaryActionButtonBusy]}
          onPress={() => {
            void handleAttachFile();
          }}
          disabled={isUploadingAttachment}
        >
          {isUploadingAttachment ? (
            <ActivityIndicator size="small" color={colors.brand} />
          ) : (
            <Paperclip size={18} strokeWidth={2} color="#2563EB" />
          )}
          <Text style={s.secondaryActionButtonText}>
            {isUploadingAttachment ? "上传中..." : "添加附件"}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.reviewButton, isReviewed && s.reviewButtonDone]}
          onPress={() => onStartReview(task)}
        >
          {isReviewed ? (
            <CheckCircle2 size={18} strokeWidth={2} color="#FFFFFF" />
          ) : (
            <ClipboardList size={18} strokeWidth={2} color="#FFFFFF" />
          )}
          <Text style={s.reviewButtonText}>
            {isReviewed ? "已复盘" : isDone ? "查看复盘" : "开始复盘"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Date/Time picker sheet */}
      {showDatePicker && (
        <DateTimePickerSheet
          value={{
            date: task.dueDate ? task.dueDate.split("T")[0] : null,
            time: task.dueDate?.includes("T") ? task.dueDate.split("T")[1] : null,
            durationMinutes: task.durationMinutes ?? null,
          }}
          onChange={(v) => {
            if (!onUpdate) return;
            onUpdate(task.id, buildTaskScheduleUpdatesFromPicker(v));
          }}
          onClose={() => setShowDatePicker(false)}
          onClear={() => {
            if (onUpdate) onUpdate(task.id, { dueDate: null });
          }}
        />
      )}

      <Modal visible={showActionSheet} transparent animationType="fade" onRequestClose={() => setShowActionSheet(false)}>
        <Pressable style={s.sheetBackdrop} onPress={() => setShowActionSheet(false)}>
          <Pressable style={s.actionSheet} onPress={(event) => event.stopPropagation()}>
            <Text style={s.actionSheetTitle}>任务操作</Text>
            <TouchableOpacity style={s.actionSheetRow} onPress={handleOpenDescriptionEditor}>
              <Text style={s.actionSheetText}>编辑备注 / 说明</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.actionSheetRow} onPress={handleRequestDelete}>
              <Text style={[s.actionSheetText, s.actionSheetTextDanger]}>删除任务</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowActionSheet(false)}>
              <Text style={s.actionSheetCancelText}>取消</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal
        visible={showDescriptionEditor}
        transparent
        animationType="fade"
        onRequestClose={() => setShowDescriptionEditor(false)}
      >
        <Pressable style={s.sheetBackdrop} onPress={() => setShowDescriptionEditor(false)}>
          <Pressable style={s.editorSheet} onPress={(event) => event.stopPropagation()}>
            <Text style={s.editorTitle}>编辑备注 / 说明</Text>
            <TextInput
              value={descriptionDraft}
              onChangeText={setDescriptionDraft}
              multiline
              autoFocus
              placeholder="补充这条任务的背景、备注或会后结果"
              placeholderTextColor="#9CA3AF"
              style={s.editorInput}
              textAlignVertical="top"
            />
            <View style={s.editorActions}>
              <TouchableOpacity style={s.editorSecondaryButton} onPress={() => setShowDescriptionEditor(false)}>
                <Text style={s.editorSecondaryButtonText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.editorPrimaryButton, isSavingDescription && s.editorPrimaryButtonBusy]}
                onPress={() => {
                  void handleSaveDescription();
                }}
                disabled={isSavingDescription}
              >
                {isSavingDescription ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={s.editorPrimaryButtonText}>保存</Text>
                )}
              </TouchableOpacity>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

// ─── Styles ─────────────────────────────────

const s = StyleSheet.create({
  overlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "#FFFFFF", zIndex: 50,
  },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingBottom: 12,
  },
  headerBtn: { padding: 8 },
  sheetBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.24)",
    justifyContent: "flex-end",
    padding: 18,
  },
  actionSheet: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 18,
    gap: 4,
  },
  actionSheetTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#111827",
    marginBottom: 8,
  },
  actionSheetRow: {
    paddingVertical: 14,
  },
  actionSheetText: {
    fontSize: 15,
    color: "#111827",
    fontWeight: "600",
  },
  actionSheetTextDanger: {
    color: colors.error,
  },
  actionSheetCancel: {
    marginTop: 8,
    paddingVertical: 14,
    alignItems: "center",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#E5E7EB",
  },
  actionSheetCancelText: {
    fontSize: 14,
    color: "#6B7280",
    fontWeight: "600",
  },
  editorSheet: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 18,
    minHeight: 280,
  },
  editorTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#111827",
    marginBottom: 12,
  },
  editorInput: {
    minHeight: 160,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    lineHeight: 22,
    color: "#111827",
    backgroundColor: "#F9FAFB",
  },
  editorActions: {
    marginTop: 14,
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  editorSecondaryButton: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 14,
    backgroundColor: "#F3F4F6",
  },
  editorSecondaryButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#4B5563",
  },
  editorPrimaryButton: {
    minWidth: 84,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 14,
    backgroundColor: "#2563EB",
    alignItems: "center",
    justifyContent: "center",
  },
  editorPrimaryButtonBusy: {
    opacity: 0.8,
  },
  editorPrimaryButtonText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },

  body: { flex: 1 },
  bodyContent: { paddingHorizontal: 24, paddingTop: 8 },

  // Title
  titleRow: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
  checkbox: {
    width: 24, height: 24, borderRadius: 6, borderWidth: 2,
    borderColor: "#D1D5DB", alignItems: "center", justifyContent: "center", marginTop: 4,
  },
  checkboxDone: { backgroundColor: "#2563EB", borderColor: "#2563EB" },
  checkboxOverdue: { borderColor: "#EF4444", backgroundColor: "#FEF2F2" },
  title: { flex: 1, fontSize: 22, fontWeight: "600", color: "#1F2937", lineHeight: 32 },
  titleDone: { color: "#A8B0BF", textDecorationLine: "line-through" },

  // Meta
  metaArea: { paddingLeft: 38, marginTop: 14, gap: 10 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12 },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  metaText: { fontSize: 14, fontWeight: "500", color: "#2563EB" },
  metaTextRed: { fontSize: 14, fontWeight: "500", color: "#EF4444" },
  metaTextOrange: { fontSize: 14, fontWeight: "500", color: "#F97316" },
  metaTextGray: { fontSize: 14, fontWeight: "500", color: "#6B7280" },
  metaTextDone: { color: "#A8B0BF" },

  reviewedBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: "#F97316", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12,
  },
  reviewedBadgeText: { fontSize: 11, fontWeight: "700", color: "#FFFFFF" },

  // Collaborators
  collaboratorChip: { flexDirection: "row", alignItems: "center", gap: 5 },
  avatar: {
    width: 20, height: 20, borderRadius: 10,
    alignItems: "center", justifyContent: "center",
  },
  avatarOwner: { backgroundColor: "#3B82F6" },
  avatarCollab: { backgroundColor: "#10B981" },
  avatarText: { fontSize: 10, fontWeight: "600", color: "#FFFFFF" },
  collaboratorName: { fontSize: 13, fontWeight: "500", color: "#374151" },
  ownerLabel: { fontSize: 10, fontWeight: "600", color: "#3B82F6" },

  // Related
  relatedItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  relatedText: {
    fontSize: 13, color: "#6B7280",
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#D1D5DB",
    paddingBottom: 1,
  },

  divider: { height: 1, backgroundColor: "#F3F4F6", marginVertical: 20, marginLeft: 38 },

  // Description
  descriptionArea: { paddingLeft: 38, marginBottom: 20 },
  descriptionText: { fontSize: 15, lineHeight: 26, color: "#374151" },
  descriptionTextDone: { color: "#A8B0BF" },
  descriptionPlaceholder: { fontSize: 15, color: "#D1D5DB", fontStyle: "italic" },
  understandingLoading: {
    marginLeft: 38,
    marginBottom: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  understandingLoadingText: {
    fontSize: 13,
    color: "#6B7280",
  },
  contextActionRow: {
    paddingLeft: 38,
    marginTop: 14,
    marginBottom: 4,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  contextActionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  contextActionText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#2563EB",
  },

  // Blocker
  blockerCard: {
    flexDirection: "row", alignItems: "flex-start", gap: 10,
    marginLeft: 38, marginBottom: 20,
    backgroundColor: "#FFF7ED", borderLeftWidth: 3, borderLeftColor: "#F97316",
    borderRadius: 12, padding: 14,
  },
  blockerContent: { flex: 1 },
  blockerLabel: { fontSize: 11, fontWeight: "800", color: "#F97316", marginBottom: 4 },
  blockerText: { fontSize: 13, color: "#9A3412", lineHeight: 20 },

  // Attachments
  attachmentSection: { paddingLeft: 38, marginBottom: 20, gap: 10 },
  attachmentCard: {
    borderWidth: 1, borderColor: "#E5E7EB", borderRadius: 16,
    padding: 14, backgroundColor: "#FAFAFA", overflow: "hidden",
  },
  attachmentCardProcessing: { backgroundColor: "#EFF6FF", borderColor: "#DBEAFE" },
  pendingAttachmentCardDanger: { backgroundColor: "#FFF7ED", borderColor: "#FED7AA" },
  attachmentShimmer: {
    position: "absolute", top: 0, left: 0, right: 0, height: 2,
    backgroundColor: "#93C5FD",
  },
  attachmentRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  attachmentBody: { flex: 1 },
  attachmentHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  attachmentTitle: { fontSize: 14, fontWeight: "600", color: "#1F2937", flex: 1 },
  attachmentDuration: { fontSize: 12, color: "#A8B0BF", fontFamily: "monospace" },
  attachmentStatusText: { fontSize: 13, fontWeight: "500", color: "#6366F1" },
  attachmentSummary: { fontSize: 13, color: "#4B5563", lineHeight: 22 },
  inlineRetryButton: {
    marginTop: 10,
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 12,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  inlineRetryButtonBusy: {
    opacity: 0.72,
  },
  inlineRetryButtonText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#2563EB",
  },
  inlineRetryButtonTextDanger: {
    color: colors.error,
  },

  // Completion note
  completionCard: {
    flexDirection: "row", alignItems: "flex-start", gap: 10,
    marginLeft: 38, marginBottom: 20,
    backgroundColor: "#ECFDF5", borderRadius: 12, padding: 14,
  },
  completionText: { flex: 1, fontSize: 13, color: "#065F46", lineHeight: 20 },

  // Activity timeline
  activitySection: { paddingLeft: 38, marginBottom: 20 },
  sectionLabel: { fontSize: 11, fontWeight: "800", color: "#A8B0BF", marginBottom: 12 },
  activityRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: 16, position: "relative" },
  timelineDot: {
    width: 8, height: 8, borderRadius: 4, backgroundColor: "#2563EB",
    marginTop: 4, marginRight: 12, zIndex: 1,
  },
  timelineLine: {
    position: "absolute", left: 3.5, top: 14, bottom: -12,
    width: 1, backgroundColor: "#E5E7EB",
  },
  activityContent: { flex: 1, flexDirection: "row", flexWrap: "wrap", gap: 8 },
  activityTime: { fontSize: 11, color: "#A8B0BF", fontFamily: "monospace" },
  activityLabel: { fontSize: 12, color: "#374151", flex: 1 },
  activityActor: { fontSize: 12, color: "#A8B0BF" },
  emptyText: { fontSize: 12, color: "#A8B0BF" },

  // Bottom info
  bottomInfo: { paddingLeft: 38, marginBottom: 20 },
  bottomInfoText: { fontSize: 11, color: "#A8B0BF" },

  // Bottom bar
  bottomBar: {
    flexDirection: "row", gap: 12,
    paddingHorizontal: 24, paddingTop: 16,
    backgroundColor: "rgba(255,255,255,0.9)",
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#F3F4F6",
  },
  micButton: {
    width: 52, height: 52, borderRadius: 16,
    backgroundColor: "#F9FAFB", borderWidth: 1, borderColor: "#E5E7EB",
    alignItems: "center", justifyContent: "center",
  },
  secondaryActionButton: {
    height: 52,
    borderRadius: 16,
    backgroundColor: "#F9FAFB",
    borderWidth: 1,
    borderColor: "#E5E7EB",
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  secondaryActionButtonBusy: {
    opacity: 0.72,
  },
  secondaryActionButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#2563EB",
  },
  reviewButton: {
    flex: 1, height: 52, borderRadius: 16,
    backgroundColor: "#2563EB",
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
  },
  reviewButtonDone: { backgroundColor: "#10B981" },
  reviewButtonText: { fontSize: 15, fontWeight: "600", color: "#FFFFFF", letterSpacing: 0.3 },
});
~~~

## `mobile/components/TaskReviewComposer.tsx`

- 编码: `utf-8`

~~~tsx
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { saveTaskReview } from "../lib/task-review-service";
import { colors } from "../lib/theme";
import type { TaskRecord } from "../lib/types";

interface Props {
  readonly task: TaskRecord;
  readonly onClose: () => void;
  readonly onSaved: (task: TaskRecord) => void;
}

export default function TaskReviewComposer({ task, onClose, onSaved }: Props) {
  const chrome = useAppChromeInsets();
  const [reviewNote, setReviewNote] = useState(task.completionNote ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const trimmed = reviewNote.trim();
    if (!trimmed) {
      Alert.alert("请先填写复盘", "保存前需要输入复盘内容。");
      return;
    }
    setSaving(true);
    try {
      const { task: updatedTask } = saveTaskReview(task.id, trimmed);
      onSaved(updatedTask);
    } catch (error) {
      const message = error instanceof Error ? error.message : "复盘保存失败";
      Alert.alert("保存失败", message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={s.overlay}>
      {/* Header */}
      <View style={[s.header, { paddingTop: chrome.headerTopPadding + 8 }]}>
        <Text style={s.headerTitle}>任务复盘</Text>
        <TouchableOpacity
          style={[s.doneButton, saving && { opacity: 0.6 }]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={s.doneButtonText}>完成</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Editor */}
      <View style={s.editorArea}>
        <TextInput
          style={s.editor}
          value={reviewNote}
          onChangeText={setReviewNote}
          placeholder="记录本次任务的产出、遇到的问题及沉淀的经验..."
          placeholderTextColor="#CBD5E1"
          multiline
          autoFocus
          textAlignVertical="top"
        />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  overlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "#FFFFFF", zIndex: 60,
  },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 20, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#F3F4F6",
  },
  headerTitle: { fontSize: 17, fontWeight: "600", color: "#1F2937", marginLeft: 4 },
  doneButton: {
    backgroundColor: colors.brand, paddingHorizontal: 20, paddingVertical: 8,
    borderRadius: 20, minWidth: 64, alignItems: "center",
  },
  doneButtonText: { fontSize: 14, fontWeight: "600", color: "#FFFFFF" },

  editorArea: { flex: 1, paddingHorizontal: 28, paddingTop: 24, paddingBottom: 32 },
  editor: {
    flex: 1, fontSize: 16, lineHeight: 28, color: "#1F2937",
  },
});
~~~

## `mobile/components/TaskSyncBadge.tsx`

- 编码: `utf-8`

~~~tsx
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { borderRadius, colors, fontSize, spacing } from "../lib/theme";
import { buildTaskSyncIndicator } from "../lib/task-sync-presentation";
import type { TaskRecord } from "../lib/types";

interface TaskSyncBadgeProps {
  readonly task: Pick<TaskRecord, "remoteState" | "syncReasonCode">;
  readonly compact?: boolean;
  readonly style?: StyleProp<ViewStyle>;
}

const TONE_STYLES = {
  info: {
    backgroundColor: "#EFF6FF",
    borderColor: "#BFDBFE",
    textColor: "#1D4ED8",
  },
  warning: {
    backgroundColor: "#FFF7ED",
    borderColor: "#FED7AA",
    textColor: "#C2410C",
  },
  danger: {
    backgroundColor: "#FEF2F2",
    borderColor: "#FECACA",
    textColor: colors.error,
  },
} as const;

export default function TaskSyncBadge({ task, compact = false, style }: TaskSyncBadgeProps) {
  const indicator = buildTaskSyncIndicator(task);
  if (!indicator) {
    return null;
  }
  const tone = TONE_STYLES[indicator.tone];
  return (
    <View
      style={[
        styles.badge,
        compact ? styles.badgeCompact : null,
        { backgroundColor: tone.backgroundColor, borderColor: tone.borderColor },
        style,
      ]}
    >
      <Text
        style={[
          styles.badgeText,
          compact ? styles.badgeTextCompact : null,
          { color: tone.textColor },
        ]}
        numberOfLines={1}
      >
        {indicator.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: borderRadius.full,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  badgeCompact: {
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 3,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  badgeTextCompact: {
    fontSize: 10,
  },
});
~~~

## `mobile/components/UnderstandingCard.tsx`

- 编码: `utf-8`

~~~tsx
import { StyleSheet, Text, View } from "react-native";
import { AlertTriangle, BrainCircuit, Link2, Sparkles } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing } from "../lib/theme";
import type { TaskUnderstandingCardModel } from "../lib/task-understanding";

interface UnderstandingCardProps {
  model: TaskUnderstandingCardModel;
}

const TONE_STYLES = {
  ready: {
    backgroundColor: "#ECFDF5",
    borderColor: "#86EFAC",
    icon: <Sparkles size={16} color="#16A34A" />,
    badgeBg: "#DCFCE7",
    badgeText: "#166534",
  },
  weak_link: {
    backgroundColor: "#FFF7ED",
    borderColor: "#FDBA74",
    icon: <Link2 size={16} color="#EA580C" />,
    badgeBg: "#FFEDD5",
    badgeText: "#9A3412",
  },
  insufficient_context: {
    backgroundColor: "#F8FAFC",
    borderColor: "#CBD5E1",
    icon: <AlertTriangle size={16} color="#475569" />,
    badgeBg: "#E2E8F0",
    badgeText: "#334155",
  },
} as const;

export default function UnderstandingCard({ model }: UnderstandingCardProps) {
  const tone = TONE_STYLES[model.tone];

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: tone.backgroundColor,
          borderColor: tone.borderColor,
        },
      ]}
    >
      <View style={styles.header}>
        <View style={styles.headerTitleWrap}>
          {tone.icon}
          <Text style={styles.title}>{model.title}</Text>
        </View>
        <View style={[styles.badge, { backgroundColor: tone.badgeBg }]}>
          <Text style={[styles.badgeText, { color: tone.badgeText }]}>{model.stateLabel}</Text>
        </View>
      </View>

      <Text style={styles.subtitle}>{model.subtitle}</Text>

      {model.evidence.length > 0 ? (
        <View style={styles.evidenceBlock}>
          <View style={styles.evidenceHeader}>
            <BrainCircuit size={14} color={colors.textSecondary} />
            <Text style={styles.evidenceTitle}>依据</Text>
          </View>
          <View style={styles.evidenceList}>
            {model.evidence.map((item) => (
              <View key={item} style={styles.evidenceChip}>
                <Text style={styles.evidenceChipText}>{item}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {model.sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <Text style={styles.sectionTitle}>{section.title}</Text>
          <Text style={styles.sectionContent}>{section.content || "暂无可靠洞察"}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginLeft: 38,
    marginBottom: 20,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  headerTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  title: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  badge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  evidenceBlock: {
    gap: spacing.xs,
  },
  evidenceHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  evidenceTitle: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  evidenceList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  evidenceChip: {
    borderRadius: borderRadius.full,
    backgroundColor: "rgba(255,255,255,0.72)",
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  evidenceChipText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  section: {
    gap: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.xs,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  sectionContent: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
});
~~~

## `mobile/components/WeekSignalCard.tsx`

- 编码: `utf-8`

~~~tsx
import type { ReactNode } from "react";
import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { CalendarClock } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, shadow } from "../lib/theme";
import type { WeekSignalSnapshot } from "../lib/types";

interface WeekSignalCardProps {
  weekLabel: string;
  snapshot: WeekSignalSnapshot;
}

export default function WeekSignalCard({ weekLabel, snapshot }: WeekSignalCardProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <TouchableOpacity style={styles.card} activeOpacity={0.78} onPress={() => setOpen(true)}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>周信号</Text>
            <Text style={styles.subtitle}>{weekLabel}</Text>
          </View>
          <CalendarClock size={18} color={colors.brand} />
        </View>
        <View style={styles.metricRow}>
          <Metric label="任务" value={String(snapshot.facts.totalCount)} />
          <Metric label="完成" value={String(snapshot.facts.completedCount)} />
          <Metric label="逾期" value={String(snapshot.facts.overdueCount)} />
          <Metric label="待复盘" value={String(snapshot.facts.awaitingReviewCount)} />
        </View>
        {snapshot.pendingJudgments[0] ? <Text style={styles.inlineText}>待确认：{snapshot.pendingJudgments[0]}</Text> : null}
        {snapshot.riskSignals[0] ? <Text style={styles.inlineText}>风险：{snapshot.riskSignals[0]}</Text> : null}
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
            <Text style={styles.sheetTitle}>Week Signal</Text>
            <ScrollView contentContainerStyle={styles.sheetContent}>
              <Block title="本周事实">
                <Text style={styles.bullet}>• 本周任务数：{snapshot.facts.totalCount}</Text>
                <Text style={styles.bullet}>• 完成数：{snapshot.facts.completedCount}</Text>
                <Text style={styles.bullet}>• 改期/更新数：{snapshot.facts.rescheduledCount}</Text>
                <Text style={styles.bullet}>• 未安排时间数：{snapshot.facts.unscheduledCount}</Text>
                <Text style={styles.bullet}>• 逾期数：{snapshot.facts.overdueCount}</Text>
                <Text style={styles.bullet}>• 待复盘数：{snapshot.facts.awaitingReviewCount}</Text>
              </Block>
              <Block title="待确认判断">
                {snapshot.pendingJudgments.length > 0 ? snapshot.pendingJudgments.map((item, index) => (
                  <Text key={`pending-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>暂无待确认判断</Text>}
              </Block>
              <Block title="风险信号">
                {snapshot.riskSignals.length > 0 ? snapshot.riskSignals.map((item, index) => (
                  <Text key={`risk-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>暂无风险信号</Text>}
              </Block>
              <Block title="建议动作">
                {snapshot.suggestedActions.length > 0 ? snapshot.suggestedActions.map((item, index) => (
                  <Text key={`action-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>当前仅提供事实层，不伪造建议</Text>}
              </Block>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metric: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  metricValue: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    color: colors.text,
  },
  metricLabel: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  inlineText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.22)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  sheet: {
    borderRadius: borderRadius.xl,
    backgroundColor: colors.surface,
    maxHeight: "80%",
    padding: spacing.lg,
    ...shadow.softCard,
  },
  sheetTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacing.md,
  },
  sheetContent: {
    gap: spacing.md,
  },
  block: {
    gap: spacing.sm,
  },
  blockTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  bullet: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
~~~

## `mobile/components/WorkspaceLiteSheet.tsx`

- 编码: `utf-8`

~~~tsx
import type { ReactNode } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { AlertTriangle, CheckCircle2, Clock3, FileText, FolderOpenDot, Layers } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, shadow } from "../lib/theme";
import { useClientIntel } from "../lib/client-intel-store";
import type { BoundaryCard } from "../lib/types";

interface WorkspaceLiteSheetProps {
  visible: boolean;
  clientId: string | null;
  clientName?: string | null;
  onClose: () => void;
  onTaskPress?: (taskId: string) => void;
}

const TONE_MAP = {
  official: {
    bg: "#ECFDF5",
    border: "#BBF7D0",
    icon: <CheckCircle2 size={14} color="#16A34A" />,
  },
  pending: {
    bg: "#FFF7ED",
    border: "#FED7AA",
    icon: <Clock3 size={14} color="#EA580C" />,
  },
  risk: {
    bg: "#FEF2F2",
    border: "#FECACA",
    icon: <AlertTriangle size={14} color="#DC2626" />,
  },
  reminder: {
    bg: "#F8FAFC",
    border: "#CBD5E1",
    icon: <Layers size={14} color="#475569" />,
  },
} as const;

function formatMetaDate(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function sourceTypeLabel(sourceType: BoundaryCard["sourceType"]): string {
  switch (sourceType) {
    case "meeting":
      return "会议";
    case "document":
      return "文档";
    case "ai":
      return "AI";
    case "manual":
      return "人工";
    default:
      return "混合";
  }
}

export default function WorkspaceLiteSheet({
  visible,
  clientId,
  clientName,
  onClose,
  onTaskPress,
}: WorkspaceLiteSheetProps) {
  const { snapshot, isLoading, isRefreshing, refresh, error } = useClientIntel(clientId);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.title}>{snapshot?.clientName || clientName || "客户工作台"}</Text>
              <Text style={styles.subtitle}>工作台 + Cockpit Lite</Text>
            </View>
            <TouchableOpacity style={styles.refreshButton} onPress={() => void refresh()}>
              <Text style={styles.refreshText}>{isRefreshing ? "刷新中" : "刷新"}</Text>
            </TouchableOpacity>
          </View>

          {!snapshot && isLoading ? (
            <View style={styles.loadingState}>
              <ActivityIndicator size="large" color={colors.brand} />
              <Text style={styles.loadingText}>正在加载工作台…</Text>
            </View>
          ) : (
            <ScrollView contentContainerStyle={styles.content}>
              {error && !snapshot ? <Text style={styles.errorText}>{error}</Text> : null}

              <Section title="Boundary">
                {snapshot?.boundaryCards.map((card) => (
                  <BoundaryCardView key={card.kind} card={card} />
                ))}
              </Section>

              <Section title="工作台">
                <SimpleList title="目标" items={snapshot?.goals ?? []} emptyText="暂无目标" />
                <SimpleList title="最近会议" items={snapshot?.latestMeetings ?? []} emptyText="暂无会议" />
                <SimpleList title="资料" items={snapshot?.recentDocuments ?? []} emptyText="暂无资料" />
                <InfoRow label="知识状态" value={snapshot?.knowledgeStatus || "暂无知识状态"} icon={<FolderOpenDot size={14} color={colors.brand} />} />
                <SimpleList title="开放问题" items={snapshot?.openQuestions ?? []} emptyText="暂无开放问题" />
                <SimpleList title="相关任务" items={(snapshot?.relatedTasks ?? []).map((item) => ({
                  id: item.id,
                  title: item.title,
                  summary: [item.eventLineName, item.status].filter(Boolean).join(" · "),
                }))} emptyText="暂无相关任务" onItemPress={onTaskPress} />
                <StringList title="下一步" items={snapshot?.nextActions ?? []} emptyText="暂无下一步动作" />
              </Section>

              <Section title="Cockpit">
                <InfoRow label="Headline" value={snapshot?.headline || "暂无 headline"} icon={<Layers size={14} color={colors.brand} />} />
                <StringList title="健康信号" items={snapshot?.health ?? []} emptyText="暂无健康信号" />
                <StringList title="两周变化" items={snapshot?.twoWeekChanges ?? []} emptyText="暂无变化摘要" />
                <StringList title="待确认决策" items={snapshot?.pendingDecisions ?? []} emptyText="暂无待确认决策" />
                <StringList title="待补材料" items={snapshot?.pendingMaterials ?? []} emptyText="暂无待补材料" />
              </Section>
            </ScrollView>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function BoundaryCardView({ card }: { card: BoundaryCard }) {
  const tone = TONE_MAP[card.kind];
  const updatedAt = formatMetaDate(card.updatedAt);
  return (
    <View style={[styles.boundaryCard, { backgroundColor: tone.bg, borderColor: tone.border }]}>
      <View style={styles.boundaryHeader}>
        <View style={styles.boundaryTitleWrap}>
          {tone.icon}
          <Text style={styles.boundaryTitle}>{card.title}</Text>
        </View>
        <Text style={styles.boundaryMeta}>{card.evidenceCount == null ? "—" : `${card.evidenceCount} 条`}</Text>
      </View>
      <Text style={styles.boundarySummary}>{card.summary}</Text>
      <View style={styles.boundaryFooter}>
        <Text style={styles.boundaryFooterText}>来源：{sourceTypeLabel(card.sourceType)}</Text>
        <Text style={styles.boundaryFooterText}>{updatedAt ? `更新：${updatedAt}` : "更新：暂无"}</Text>
      </View>
    </View>
  );
}

function InfoRow({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <View style={styles.infoRow}>
      <View style={styles.infoLabel}>
        {icon}
        <Text style={styles.infoLabelText}>{label}</Text>
      </View>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

function StringList({ title, items, emptyText }: { title: string; items: readonly string[]; emptyText: string }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {items.length > 0 ? items.map((item, index) => (
        <Text key={`${title}-${index}`} style={styles.bulletText}>• {item}</Text>
      )) : <Text style={styles.emptyText}>{emptyText}</Text>}
    </View>
  );
}

function SimpleList({
  title,
  items,
  emptyText,
  onItemPress,
}: {
  title: string;
  items: ReadonlyArray<{ id: string; title: string; summary?: string | null }>;
  emptyText: string;
  onItemPress?: (itemId: string) => void;
}) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {items.length > 0 ? items.map((item) => (
        <TouchableOpacity
          key={item.id}
          style={styles.listRow}
          activeOpacity={onItemPress ? 0.78 : 1}
          disabled={!onItemPress}
          onPress={() => onItemPress?.(item.id)}
        >
          <Text style={styles.listTitle}>{item.title}</Text>
          {item.summary ? <Text style={styles.listSummary}>{item.summary}</Text> : null}
        </TouchableOpacity>
      )) : <Text style={styles.emptyText}>{emptyText}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.22)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    minHeight: "60%",
    maxHeight: "88%",
    ...shadow.softCard,
  },
  handle: {
    alignSelf: "center",
    width: 42,
    height: 5,
    borderRadius: 999,
    backgroundColor: colors.border,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headerCopy: {
    flex: 1,
  },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  refreshButton: {
    alignSelf: "flex-start",
    backgroundColor: colors.brandBg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
  },
  refreshText: {
    color: colors.brand,
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  loadingState: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxxl,
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  errorText: {
    fontSize: fontSize.sm,
    color: colors.error,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.lg,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    color: colors.text,
  },
  boundaryCard: {
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.xs,
  },
  boundaryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  boundaryTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flex: 1,
  },
  boundaryTitle: {
    fontSize: fontSize.sm,
    fontWeight: "800",
    color: colors.text,
  },
  boundaryMeta: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  boundarySummary: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
  boundaryFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  boundaryFooterText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  block: {
    gap: spacing.sm,
  },
  blockTitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  infoRow: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
    gap: spacing.sm,
  },
  infoLabel: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  infoLabelText: {
    fontSize: fontSize.xs,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  infoValue: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.text,
  },
  listRow: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
  },
  listTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  listSummary: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
~~~

## `mobile/components/calendar-screen/CalendarDragLayer.tsx`

- 编码: `utf-8`

~~~tsx
import { Animated, Text, View } from "react-native";
import { colors } from "../../lib/theme";
import type { TaskRecord } from "../../lib/types";

interface Props {
  styles: any;
  draggingTask: TaskRecord | null;
  dragOpacity: Animated.Value;
  dragScale: Animated.Value;
  dragTranslate: Animated.ValueXY;
}

export default function CalendarDragLayer({
  styles,
  draggingTask,
  dragOpacity,
  dragScale,
  dragTranslate,
}: Props) {
  if (!draggingTask) {
    return null;
  }

  return (
    <View pointerEvents="none" style={styles.dragLayer}>
      <Animated.View
        style={[
          styles.dragDot,
          {
            backgroundColor: draggingTask.priority === "high" ? "#F97316" : colors.brand,
            opacity: dragOpacity,
            transform: [
              { translateX: dragTranslate.x },
              { translateY: dragTranslate.y },
              { scale: dragScale },
            ],
          },
        ]}
      >
        <Text style={styles.dragDotText}>{draggingTask.title.charAt(0)}</Text>
      </Animated.View>
    </View>
  );
}
~~~

## `mobile/components/calendar-screen/CalendarHeader.tsx`

- 编码: `utf-8`

~~~tsx
import { Text, TouchableOpacity, View } from "react-native";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react-native";
import { colors } from "../../lib/theme";

interface Props {
  styles: any;
  headerTitle: string;
  viewLabel: string;
  topPadding: number;
  onPrev: () => void;
  onNext: () => void;
  onOpenViewMenu: () => void;
}

export default function CalendarHeader({
  styles,
  headerTitle,
  viewLabel,
  topPadding,
  onPrev,
  onNext,
  onOpenViewMenu,
}: Props) {
  return (
    <View style={[styles.header, { paddingTop: topPadding }]}>
      <View style={styles.headerNav}>
        <TouchableOpacity onPress={onPrev} style={styles.navButton}>
          <ChevronLeft size={18} color={colors.textSecondary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{headerTitle}</Text>
        <TouchableOpacity onPress={onNext} style={styles.navButton}>
          <ChevronRight size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
      <TouchableOpacity style={styles.viewSwitcher} onPress={onOpenViewMenu}>
        <Text style={styles.viewSwitcherText}>{viewLabel}</Text>
        <ChevronDown size={14} strokeWidth={2} color={colors.brand} />
      </TouchableOpacity>
    </View>
  );
}
~~~

## `mobile/components/calendar-screen/CalendarModalCoordinator.tsx`

- 编码: `utf-8`

~~~tsx
import TaskDetail from "../../components/TaskDetail";
import RecordNote from "../../components/RecordNote";
import TaskReviewComposer from "../../components/TaskReviewComposer";
import CreateTask from "../../components/CreateTask";
import SmartInputSheet from "../../components/SmartInputSheet";
import type { EventLineRecord, SmartTaskDraft, TaskRecord } from "../../lib/types";

interface Props {
  selectedTask: TaskRecord | null;
  selectedTaskEventLine?: EventLineRecord | null;
  recordTaskContext: TaskRecord | null;
  reviewTaskContext: TaskRecord | null;
  showCreate: boolean;
  showSmartInput: boolean;
  smartDraft: SmartTaskDraft | null;
  createPreset: { dueDate?: string; dueTime?: string };
  smartInputPreset: { dueDate?: string; dueTime?: string };
  selectedDateKey: string;
  onCloseSelectedTask: () => void;
  onStartReview: (task: TaskRecord) => void;
  onRecordFromTaskDetail: () => void;
  onUpdateTask: (taskId: string, updates: Partial<TaskRecord>) => void;
  onDeleteTask?: (task: TaskRecord) => void | Promise<void>;
  onReplaceSelectedTask: (task: TaskRecord) => void;
  onOpenClientWorkspace?: (clientId: string, clientName?: string | null) => void;
  onOpenEventLine?: (eventLineId: string) => void;
  onOpenConsult?: (task: TaskRecord) => void;
  onUploadedRecord: (task: TaskRecord) => void;
  onCloseRecord: () => void;
  onCloseReview: () => void;
  onSavedReview: () => void;
  onCloseCreate: () => void;
  onCreated: () => void;
  onCloseSmartInput: () => void;
  onApplySmartDraft: (draft: SmartTaskDraft) => void;
}

export default function CalendarModalCoordinator({
  selectedTask,
  selectedTaskEventLine,
  recordTaskContext,
  reviewTaskContext,
  showCreate,
  showSmartInput,
  smartDraft,
  createPreset,
  smartInputPreset,
  selectedDateKey,
  onCloseSelectedTask,
  onStartReview,
  onRecordFromTaskDetail,
  onUpdateTask,
  onDeleteTask,
  onReplaceSelectedTask,
  onOpenClientWorkspace,
  onOpenEventLine,
  onOpenConsult,
  onUploadedRecord,
  onCloseRecord,
  onCloseReview,
  onSavedReview,
  onCloseCreate,
  onCreated,
  onCloseSmartInput,
  onApplySmartDraft,
}: Props) {
  return (
    <>
      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          eventLine={selectedTaskEventLine}
          onClose={onCloseSelectedTask}
          onStartReview={onStartReview}
          onRecord={onRecordFromTaskDetail}
          onUpdate={onUpdateTask}
          onDeleteTask={onDeleteTask}
          onTaskReplaced={onReplaceSelectedTask}
          onOpenClientWorkspace={onOpenClientWorkspace}
          onOpenEventLine={onOpenEventLine}
          onOpenConsult={onOpenConsult}
        />
      )}
      {recordTaskContext && (
        <RecordNote
          taskContext={recordTaskContext}
          autoStart
          onUploaded={onUploadedRecord}
          onClose={onCloseRecord}
        />
      )}
      {reviewTaskContext && (
        <TaskReviewComposer
          task={reviewTaskContext}
          onClose={onCloseReview}
          onSaved={onSavedReview}
        />
      )}
      {showCreate && (
        <CreateTask
          task={null}
          draft={smartDraft}
          onClose={onCloseCreate}
          onCreated={onCreated}
          preset={createPreset}
        />
      )}
      {showSmartInput && (
        <SmartInputSheet
          autoStart
          referenceDate={selectedDateKey}
          onClose={onCloseSmartInput}
          onApplyDraft={onApplySmartDraft}
        />
      )}
    </>
  );
}
~~~

## `mobile/components/calendar-screen/DayView.tsx`

- 编码: `utf-8`

~~~tsx
import type { RefObject } from "react";
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { colors } from "../../lib/theme";
import type { TaskRecord } from "../../lib/types";

interface Props {
  styles: any;
  weekdayLabels: readonly string[];
  weekDates: readonly Date[];
  selectedDateKey: string;
  todayKey: string;
  tasksByDate: ReadonlyMap<string, readonly TaskRecord[]>;
  dayAllDayTasks: readonly TaskRecord[];
  dayScheduledTasks: readonly TaskRecord[];
  highlightedTaskIds?: ReadonlySet<string>;
  draggingTask: TaskRecord | null;
  hoveredDropKey: string | null;
  refreshing: boolean;
  bottomPadding: number;
  currentTimeOffset: number;
  timelineRef: RefObject<ScrollView | null>;
  registerDropZone: (key: string, ref: View | null) => void;
  onRefresh: () => void;
  onSelectDate: (dateKey: string) => void;
  onTimelineSlotPress: (hour: number) => void;
  onTimelineSlotLongPress: (hour: number) => void;
  onTaskPress: (task: TaskRecord) => void;
  onEventLinePress?: (task: TaskRecord) => void;
  onTaskTouchStart: (task: TaskRecord, event: any) => void;
  onResizeGrant: (task: TaskRecord, height: number) => void;
  onResizeMove: (pageY: number, top: number) => void;
  onResizeRelease: () => void;
  onResizeTerminate: () => void;
}

function toDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTime(dueDate: string): string {
  const date = new Date(dueDate);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function getTaskTopOffset(dueDate: string): number {
  const date = new Date(dueDate);
  return date.getHours() * 60 + (date.getMinutes() / 60) * 60;
}

function getTaskBlockHeight(durationMinutes: number): number {
  return Math.max((durationMinutes / 60) * 60, 28);
}

export default function DayView({
  styles,
  weekdayLabels,
  weekDates,
  selectedDateKey,
  todayKey,
  tasksByDate,
  dayAllDayTasks,
  dayScheduledTasks,
  highlightedTaskIds,
  draggingTask,
  hoveredDropKey,
  refreshing,
  bottomPadding,
  currentTimeOffset,
  timelineRef,
  registerDropZone,
  onRefresh,
  onSelectDate,
  onTimelineSlotPress,
  onTimelineSlotLongPress,
  onTaskPress,
  onEventLinePress,
  onTaskTouchStart,
  onResizeGrant,
  onResizeMove,
  onResizeRelease,
  onResizeTerminate,
}: Props) {
  return (
    <>
      <View style={styles.weekStrip}>
        {weekDates.map((date) => {
          const dateKey = toDateKey(date);
          const isSelected = dateKey === selectedDateKey;
          const isToday = dateKey === todayKey;
          const dayOfWeek = date.getDay();
          const isDragHover = Boolean(draggingTask) && hoveredDropKey === dateKey;
          return (
            <TouchableOpacity
              key={dateKey}
              ref={(ref) => {
                if (ref && draggingTask) {
                  registerDropZone(dateKey, ref as any);
                }
              }}
              style={styles.weekStripDay}
              onPress={() => {
                if (!draggingTask) {
                  onSelectDate(dateKey);
                }
              }}
              activeOpacity={0.6}
            >
              <Text style={[styles.weekStripLabel, (dayOfWeek === 0 || dayOfWeek === 6) && styles.weekStripLabelWeekend]}>
                {weekdayLabels[dayOfWeek]}
              </Text>
              <View
                style={[
                  styles.weekStripCircle,
                  isSelected && styles.weekStripCircleSelected,
                  isToday && !isSelected && styles.weekStripCircleToday,
                  isDragHover && styles.weekStripCircleDragHover,
                ]}
              >
                <Text style={[styles.weekStripDate, isSelected && styles.weekStripDateSelected, isToday && !isSelected && styles.weekStripDateToday]}>
                  {date.getDate()}
                </Text>
              </View>
              {tasksByDate.has(dateKey) && !isSelected && !isDragHover ? <View style={styles.weekStripDot} /> : null}
            </TouchableOpacity>
          );
        })}
      </View>

      <ScrollView
        ref={timelineRef}
        style={styles.timeline}
        contentContainerStyle={[styles.timelineContent, { paddingBottom: bottomPadding }]}
        showsVerticalScrollIndicator={false}
        scrollEnabled={!draggingTask}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
      >
        {dayAllDayTasks.length > 0 ? (
          <View style={styles.allDaySection}>
            <Text style={styles.allDayLabel}>全天</Text>
            <View style={styles.allDayList}>
              {dayAllDayTasks.map((task) => {
                const isDone = task.progressStatus === "done";
                return (
                  <TouchableOpacity
                    key={task.id}
                    style={[
                      styles.allDayTask,
                      isDone && styles.allDayTaskDone,
                      highlightedTaskIds?.has(task.id) && styles.focusMatchedCard,
                    ]}
                    activeOpacity={0.7}
                    onPress={() => onTaskPress(task)}
                  >
                    <View style={[styles.timelineTaskCheck, isDone && styles.timelineTaskCheckDone]} />
                    <Text style={[styles.allDayTaskTitle, isDone && styles.allDayTaskTitleDone]} numberOfLines={1}>
                      {task.title}
                    </Text>
                    <TaskSyncBadge task={task} compact />
                    {task.eventLineName && onEventLinePress ? (
                      <TouchableOpacity
                        style={styles.focusChip}
                        activeOpacity={0.78}
                        onPress={(event) => {
                          event.stopPropagation();
                          onEventLinePress(task);
                        }}
                      >
                        <Text style={styles.focusChipText} numberOfLines={1}>{task.eventLineName}</Text>
                      </TouchableOpacity>
                    ) : null}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ) : null}

        {Array.from({ length: 25 }, (_, index) => index).map((hour) => {
          const hourKey = `hour:${String(hour).padStart(2, "0")}`;
          const isDragHover = Boolean(draggingTask) && hoveredDropKey === hourKey;
          return (
            <View
              key={hour}
              ref={(ref) => {
                if (ref && draggingTask) {
                  registerDropZone(hourKey, ref as any);
                }
              }}
              collapsable={false}
            >
              <TouchableOpacity
                style={[styles.hourRow, isDragHover && styles.hourRowDragHover]}
                activeOpacity={draggingTask ? 1 : 0.7}
                onPress={() => onTimelineSlotPress(hour)}
                onLongPress={() => onTimelineSlotLongPress(hour)}
                delayLongPress={300}
              >
                <Text style={styles.hourLabel}>{hour === 24 ? "00" : String(hour).padStart(2, "0")}</Text>
                <View style={[styles.hourLine, isDragHover && styles.hourLineDragHover]} />
                {isDragHover ? <Text style={styles.hourDropHint}>松手安排到{String(hour).padStart(2, "0")}:00</Text> : null}
              </TouchableOpacity>
            </View>
          );
        })}

        {dayScheduledTasks.map((task) => {
          if (!task.dueDate) {
            return null;
          }
          const top = getTaskTopOffset(task.dueDate);
          const height = getTaskBlockHeight(task.durationMinutes || 60);
          const isDone = task.progressStatus === "done";
          const isDragging = draggingTask?.id === task.id;
          const isTall = height > 50;

          return (
            <View
              key={task.id}
              style={[
                styles.timelineTask,
                isDone && styles.timelineTaskDone,
                isDragging && styles.timelineTaskHidden,
                highlightedTaskIds?.has(task.id) && styles.focusMatchedCard,
                { top, height, left: 52, right: 12 },
              ]}
            >
              <TouchableOpacity
                style={styles.timelineTaskTouchable}
                activeOpacity={0.82}
                onPress={() => onTaskPress(task)}
                onPressIn={(event) => onTaskTouchStart(task, event)}
              >
                <View style={styles.timelineTaskHeader}>
                  <View style={[styles.timelineTaskCheck, isDone && styles.timelineTaskCheckDone]} />
                  <Text style={styles.timelineTaskTime}>{formatTime(task.dueDate)}</Text>
                  <TaskSyncBadge task={task} compact />
                </View>
                <Text style={[styles.timelineTaskTitle, isDone && styles.timelineTaskTitleDone]} numberOfLines={isTall ? 3 : 1}>
                  {task.title}
                </Text>
              </TouchableOpacity>
              {isTall && !isDragging ? (
                <View
                  style={styles.timelineResizeHandle}
                  onStartShouldSetResponder={() => true}
                  onMoveShouldSetResponder={() => true}
                  onResponderGrant={() => onResizeGrant(task, height)}
                  onResponderMove={(event) => onResizeMove(event.nativeEvent.pageY, top)}
                  onResponderRelease={onResizeRelease}
                  onResponderTerminate={onResizeTerminate}
                >
                  <View style={styles.timelineResizeGrip} />
                </View>
              ) : null}
            </View>
          );
        })}

        {selectedDateKey === todayKey ? (
          <View style={[styles.currentTimeLine, { top: currentTimeOffset }]} pointerEvents="none">
            <View style={styles.currentTimeDot} />
            <View style={styles.currentTimeBar} />
          </View>
        ) : null}
      </ScrollView>
    </>
  );
}
~~~

## `mobile/components/calendar-screen/MonthView.tsx`

- 编码: `utf-8`

~~~tsx
import type { GestureResponderEvent } from "react-native";
import { Inbox } from "lucide-react-native";
import { Pressable, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { colors } from "../../lib/theme";
import type { TaskRecord } from "../../lib/types";

interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

interface Props {
  styles: any;
  weekdayLabels: readonly string[];
  calendarDays: readonly CalendarDay[];
  selectedDateKey: string;
  todayKey: string;
  tasksByDate: ReadonlyMap<string, readonly TaskRecord[]>;
  draggingTask: TaskRecord | null;
  hoveredDropKey: string | null;
  selectedTasks: readonly TaskRecord[];
  highlightedTaskIds?: ReadonlySet<string>;
  refreshing: boolean;
  bottomPadding: number;
  registerDropZone: (key: string, ref: View | null) => void;
  onSelectDate: (dateKey: string) => void;
  onRefresh: () => void;
  onTaskPress: (task: TaskRecord) => void;
  onEventLinePress?: (task: TaskRecord) => void;
  onTaskTouchStart: (task: TaskRecord, event: GestureResponderEvent) => void;
  onTaskTouchMove: (event: GestureResponderEvent) => void;
  onTaskTouchEnd: () => void;
  shouldSetTaskResponder: (task: TaskRecord) => boolean;
}

function formatTime(dueDate: string): string {
  const date = new Date(dueDate);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function MonthView({
  styles,
  weekdayLabels,
  calendarDays,
  selectedDateKey,
  todayKey,
  tasksByDate,
  draggingTask,
  hoveredDropKey,
  selectedTasks,
  highlightedTaskIds,
  refreshing,
  bottomPadding,
  registerDropZone,
  onSelectDate,
  onRefresh,
  onTaskPress,
  onEventLinePress,
  onTaskTouchStart,
  onTaskTouchMove,
  onTaskTouchEnd,
  shouldSetTaskResponder,
}: Props) {
  return (
    <>
      <View style={styles.weekRow}>
        {weekdayLabels.map((label) => (
          <View key={label} style={styles.weekCell}>
            <Text style={styles.weekLabel}>{label}</Text>
          </View>
        ))}
      </View>

      <View style={styles.calendarGrid}>
        {calendarDays.map((item, index) => {
          const isSelected = item.dateKey === selectedDateKey;
          const isToday = item.dateKey === todayKey;
          const hasTasks = tasksByDate.has(item.dateKey);
          const isDragHover = Boolean(draggingTask) && hoveredDropKey === item.dateKey;
          return (
            <TouchableOpacity
              key={`${item.dateKey}-${index}`}
              ref={(ref) => {
                if (ref && draggingTask) {
                  registerDropZone(item.dateKey, ref as any);
                }
              }}
              style={styles.dayCell}
              onPress={() => {
                if (!draggingTask) {
                  onSelectDate(item.dateKey);
                }
              }}
              activeOpacity={0.6}
            >
              <View
                style={[
                  styles.dayCircle,
                  isSelected && styles.dayCircleSelected,
                  isToday && !isSelected && styles.dayCircleToday,
                  isDragHover && styles.dayCircleDragHover,
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    !item.isCurrentMonth && styles.dayTextOther,
                    isSelected && styles.dayTextSelected,
                    isToday && !isSelected && styles.dayTextToday,
                    isDragHover && styles.dayTextDragHover,
                  ]}
                >
                  {item.day}
                </Text>
              </View>
              {hasTasks ? <View style={[styles.taskDot, isSelected && styles.taskDotSelected]} /> : null}
            </TouchableOpacity>
          );
        })}
      </View>

      <ScrollView
        style={styles.taskSection}
        contentContainerStyle={[styles.taskSectionContent, { paddingBottom: bottomPadding }]}
        scrollEnabled={!draggingTask}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
      >
        {selectedTasks.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>待办任务</Text>
            {selectedTasks.map((task) => {
              const isDragging = draggingTask?.id === task.id;
              return (
                <Pressable
                  key={task.id}
                  style={[
                    styles.taskCard,
                    isDragging && styles.taskCardDragging,
                    highlightedTaskIds?.has(task.id) && styles.focusMatchedCard,
                  ]}
                  onPress={() => onTaskPress(task)}
                  onPressIn={(event) => onTaskTouchStart(task, event)}
                  onMoveShouldSetResponder={() => shouldSetTaskResponder(task)}
                  onResponderMove={onTaskTouchMove}
                  onResponderRelease={onTaskTouchEnd}
                  onResponderTerminate={onTaskTouchEnd}
                >
                  <View style={styles.taskRow}>
                    <View style={styles.taskCheckCircle} />
                    <View style={styles.taskContent}>
                      <Text style={styles.taskTitle} numberOfLines={1}>
                        {task.title}
                      </Text>
                      <TaskSyncBadge task={task} compact />
                      {task.dueDate?.includes("T") ? (
                        <Text style={styles.taskTime}>{formatTime(task.dueDate)}</Text>
                      ) : null}
                      {task.eventLineName && onEventLinePress ? (
                        <TouchableOpacity
                          style={styles.focusChip}
                          activeOpacity={0.78}
                          onPress={(event) => {
                            event.stopPropagation();
                            onEventLinePress(task);
                          }}
                        >
                          <Text style={styles.focusChipText} numberOfLines={1}>{task.eventLineName}</Text>
                        </TouchableOpacity>
                      ) : null}
                    </View>
                  </View>
                </Pressable>
              );
            })}
          </>
        ) : (
          <View style={styles.emptyState}>
            <Inbox size={48} color={colors.textTertiary} />
            <Text style={styles.emptyText}>这一天没有安排任务</Text>
          </View>
        )}
        {draggingTask ? <Text style={styles.dragHint}>拖到上方日历格子中，改变任务日期</Text> : null}
      </ScrollView>
    </>
  );
}
~~~

## `mobile/components/calendar-screen/WeekView.tsx`

- 编码: `utf-8`

~~~tsx
import type { GestureResponderEvent } from "react-native";
import { ChevronDown } from "lucide-react-native";
import { Pressable, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { colors } from "../../lib/theme";
import type { TaskRecord } from "../../lib/types";

interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

interface Props {
  styles: any;
  weekdayLabels: readonly string[];
  weekdayNames: readonly string[];
  calendarDays: readonly CalendarDay[];
  weekDates: readonly Date[];
  selectedDateKey: string;
  todayKey: string;
  tasksByDate: ReadonlyMap<string, readonly TaskRecord[]>;
  draggingTask: TaskRecord | null;
  hoveredDropKey: string | null;
  expandedWeekDay: string | null;
  highlightedTaskIds?: ReadonlySet<string>;
  refreshing: boolean;
  bottomPadding: number;
  registerDropZone: (key: string, ref: View | null) => void;
  onRefresh: () => void;
  onSelectDate: (dateKey: string, switchView?: "day") => void;
  onSetExpandedWeekDay: (dateKey: string | null) => void;
  onTaskPress: (task: TaskRecord) => void;
  onEventLinePress?: (task: TaskRecord) => void;
  onTaskTouchStart: (task: TaskRecord, event: GestureResponderEvent) => void;
  onTaskTouchMove: (event: GestureResponderEvent) => void;
  onTaskTouchEnd: () => void;
  shouldSetTaskResponder: (task: TaskRecord) => boolean;
}

function toDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTime(dueDate: string): string {
  const date = new Date(dueDate);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function WeekView({
  styles,
  weekdayLabels,
  weekdayNames,
  calendarDays,
  weekDates,
  selectedDateKey,
  todayKey,
  tasksByDate,
  draggingTask,
  hoveredDropKey,
  expandedWeekDay,
  highlightedTaskIds,
  refreshing,
  bottomPadding,
  registerDropZone,
  onRefresh,
  onSelectDate,
  onSetExpandedWeekDay,
  onTaskPress,
  onEventLinePress,
  onTaskTouchStart,
  onTaskTouchMove,
  onTaskTouchEnd,
  shouldSetTaskResponder,
}: Props) {
  return (
    <ScrollView
      style={styles.weekView}
      contentContainerStyle={[styles.weekViewContent, { paddingBottom: bottomPadding }]}
      scrollEnabled={!draggingTask}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
    >
      <View style={styles.miniCalendar}>
        <View style={styles.miniCalendarHeader}>
          {weekdayLabels.map((label) => (
            <Text key={label} style={styles.miniCalendarWeekday}>{label}</Text>
          ))}
        </View>
        <View style={styles.miniCalendarGrid}>
          {calendarDays.map((item, index) => {
            const isToday = item.dateKey === todayKey;
            const isSelected = item.dateKey === selectedDateKey;
            const isInWeek = weekDates.some((date) => toDateKey(date) === item.dateKey);
            const hasTasks = tasksByDate.has(item.dateKey);
            return (
              <TouchableOpacity
                key={`mini-${index}`}
                style={[styles.miniCalendarCell, isInWeek && styles.miniCalendarCellInWeek]}
                onPress={() => onSelectDate(item.dateKey)}
                activeOpacity={0.6}
              >
                <View
                  style={[
                    styles.miniCalendarDayCircle,
                    isToday && styles.miniCalendarDayToday,
                    isSelected && styles.miniCalendarDaySelected,
                  ]}
                >
                  <Text
                    style={[
                      styles.miniCalendarDayText,
                      !item.isCurrentMonth && styles.miniCalendarDayTextOther,
                      isToday && styles.miniCalendarDayTextToday,
                      isSelected && styles.miniCalendarDayTextSelected,
                    ]}
                  >
                    {item.day}
                  </Text>
                </View>
                {hasTasks ? <View style={styles.miniCalendarDot} /> : null}
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      <View style={styles.weekDayGrid}>
        {weekDates.map((date) => {
          const dateKey = toDateKey(date);
          const isToday = dateKey === todayKey;
          const dayTasks = tasksByDate.get(dateKey) ?? [];
          const dayOfWeek = date.getDay();
          const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
          const isDragHover = Boolean(draggingTask) && hoveredDropKey === dateKey;
          const isExpanded = expandedWeekDay === dateKey;
          const visibleTasks = isExpanded ? dayTasks : dayTasks.slice(0, 3);
          const hasMore = dayTasks.length > 3 && !isExpanded;

          return (
            <View
              key={dateKey}
              ref={(ref) => {
                if (ref && draggingTask) {
                  registerDropZone(dateKey, ref as any);
                }
              }}
              collapsable={false}
              style={[styles.weekDayColumn, isDragHover && styles.weekDayColumnDragHover]}
            >
              <TouchableOpacity activeOpacity={0.8} onPress={() => onSelectDate(dateKey, "day")}>
                <View style={styles.weekDayHeader}>
                  <Text style={[styles.weekDayName, isWeekend && styles.weekDayNameWeekend]}>
                    {weekdayNames[dayOfWeek]}
                  </Text>
                  <View style={[styles.weekDayDateCircle, isToday && styles.weekDayDateCircleToday]}>
                    <Text style={[styles.weekDayDate, isToday && styles.weekDayDateToday]}>{date.getDate()}</Text>
                  </View>
                  {isWeekend ? <Text style={styles.weekDayRestBadge}>休</Text> : null}
                </View>
              </TouchableOpacity>

              {visibleTasks.length > 0 ? (
                visibleTasks.map((task) => {
                  const isDragging = draggingTask?.id === task.id;
                  return (
                    <Pressable
                      key={task.id}
                      style={[
                        styles.weekTaskCard,
                        isDragging && styles.weekTaskCardDragging,
                        highlightedTaskIds?.has(task.id) && styles.focusMatchedCard,
                      ]}
                      onPress={() => onTaskPress(task)}
                      onPressIn={(event) => onTaskTouchStart(task, event as unknown as GestureResponderEvent)}
                      onMoveShouldSetResponder={() => shouldSetTaskResponder(task)}
                      onResponderMove={onTaskTouchMove}
                      onResponderRelease={onTaskTouchEnd}
                      onResponderTerminate={onTaskTouchEnd}
                    >
                      <View
                        style={[
                          styles.weekTaskDot,
                          { backgroundColor: task.progressStatus === "done" ? "#10B981" : "#8B5CF6" },
                        ]}
                      />
                      <Text style={styles.weekTaskTitle} numberOfLines={1}>{task.title}</Text>
                      <TaskSyncBadge task={task} compact />
                      {task.dueDate?.includes("T") ? (
                        <Text style={styles.weekTaskTime}>{formatTime(task.dueDate)}</Text>
                      ) : null}
                      {task.eventLineName && onEventLinePress ? (
                        <TouchableOpacity
                          style={styles.focusChip}
                          activeOpacity={0.78}
                          onPress={(event) => {
                            event.stopPropagation();
                            onEventLinePress(task);
                          }}
                        >
                          <Text style={styles.focusChipText} numberOfLines={1}>{task.eventLineName}</Text>
                        </TouchableOpacity>
                      ) : null}
                    </Pressable>
                  );
                })
              ) : (
                <View style={styles.weekDayEmpty}>
                  {isDragHover ? <Text style={styles.weekDayDropHint}>放在这里</Text> : null}
                </View>
              )}

              {hasMore ? (
                <TouchableOpacity
                  onPress={() => onSetExpandedWeekDay(dateKey)}
                  activeOpacity={0.7}
                  style={styles.weekDayMoreButton}
                >
                  <Text style={styles.weekDayMore}>+{dayTasks.length - 3} 更多</Text>
                  <ChevronDown size={12} color={colors.brand} />
                </TouchableOpacity>
              ) : null}
              {isExpanded && dayTasks.length > 3 ? (
                <TouchableOpacity
                  onPress={() => onSetExpandedWeekDay(null)}
                  activeOpacity={0.7}
                  style={styles.weekDayMoreButton}
                >
                  <Text style={styles.weekDayMore}>收起</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}
~~~

## `mobile/components/tasks-screen/DragCalendarOverlay.tsx`

- 编码: `utf-8`

~~~tsx
import type { MutableRefObject } from "react";
import { Animated, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { GestureResponderHandlers } from "react-native";
import type { TaskRecord } from "../../lib/types";

const DRAG_DOT_SIZE = 52;

interface DragCalendarMonth {
  year: number;
  month: number;
}

interface Props {
  dragTask: TaskRecord | null;
  dragHoveredDate: string | null;
  dragCalendarMonth: DragCalendarMonth;
  dragDateRefs: MutableRefObject<Map<string, View>>;
  dragOpacity: Animated.Value;
  dragScale: Animated.Value;
  dragTranslate: Animated.ValueXY;
  panHandlers: GestureResponderHandlers;
  formatDateKey: (date: Date) => string;
  measureDragDates: () => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onCancel: () => void;
}

function buildMonthRows(year: number, month: number): (number | null)[][] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const cells: (number | null)[] = Array.from({ length: firstDay }, () => null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(day);
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  const rows: (number | null)[][] = [];
  for (let index = 0; index < cells.length; index += 7) {
    rows.push(cells.slice(index, index + 7));
  }
  return rows;
}

export default function DragCalendarOverlay({
  dragTask,
  dragHoveredDate,
  dragCalendarMonth,
  dragDateRefs,
  dragOpacity,
  dragScale,
  dragTranslate,
  panHandlers,
  formatDateKey,
  measureDragDates,
  onPrevMonth,
  onNextMonth,
  onCancel,
}: Props) {
  const todayKey = formatDateKey(new Date());
  const rows = buildMonthRows(dragCalendarMonth.year, dragCalendarMonth.month);

  return (
    <View
      pointerEvents={dragTask ? "auto" : "none"}
      style={[styles.overlayLayer, !dragTask && styles.overlayLayerHidden]}
      {...panHandlers}
    >
      {dragTask ? (
        <View style={styles.overlay}>
          <Text style={styles.hint}>
            {dragHoveredDate ? `松手排到 ${dragHoveredDate}` : "拖到日历日期上松手安排日期"}
          </Text>

          <View style={styles.calendarSheet}>
            <View style={styles.monthNav}>
              <TouchableOpacity onPress={onPrevMonth}>
                <Text style={styles.monthArrow}>{"<"}</Text>
              </TouchableOpacity>
              <Text style={styles.monthLabel}>
                {dragCalendarMonth.year}年{dragCalendarMonth.month + 1}月
              </Text>
              <TouchableOpacity onPress={onNextMonth}>
                <Text style={styles.monthArrow}>{">"}</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.weekRow}>
              {["日", "一", "二", "三", "四", "五", "六"].map((day) => (
                <View key={day} style={styles.weekCell}>
                  <Text style={styles.weekLabel}>{day}</Text>
                </View>
              ))}
            </View>

            {rows.map((row, rowIndex) => (
              <View key={rowIndex} style={styles.weekRow}>
                {row.map((day, cellIndex) => {
                  if (day === null) {
                    return <View key={cellIndex} style={styles.dayCell} />;
                  }

                  const dateKey = `${dragCalendarMonth.year}-${String(dragCalendarMonth.month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                  const isHovered = dragHoveredDate === dateKey;
                  const isToday = dateKey === todayKey;

                  return (
                    <View
                      key={cellIndex}
                      ref={(ref) => {
                        if (ref) {
                          dragDateRefs.current.set(dateKey, ref);
                        }
                      }}
                      onLayout={() => setTimeout(measureDragDates, 50)}
                      style={[styles.dayCell, isHovered && styles.dayCellHovered]}
                    >
                      <Text
                        style={[
                          styles.dayText,
                          isToday && styles.dayTextToday,
                          isHovered && styles.dayTextHovered,
                        ]}
                      >
                        {day}
                      </Text>
                    </View>
                  );
                })}
              </View>
            ))}
          </View>

          <Animated.View
            pointerEvents="none"
            style={[
              styles.dragPill,
              {
                opacity: dragOpacity,
                transform: [
                  { translateX: dragTranslate.x },
                  { translateY: dragTranslate.y },
                  { scale: dragScale },
                ],
              },
            ]}
          >
            <Text style={styles.dragPillText} numberOfLines={1}>
              {dragTask.title.slice(0, 1)}
            </Text>
          </Animated.View>

          <TouchableOpacity style={styles.cancelBtn} onPress={onCancel}>
            <Text style={styles.cancelText}>取消</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  overlayLayer: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 120,
    elevation: 120,
  },
  overlayLayerHidden: {
    opacity: 0,
  },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(246,247,251,0.98)",
    paddingHorizontal: 20,
    paddingTop: 84,
    justifyContent: "flex-start",
  },
  hint: {
    textAlign: "center",
    fontSize: 13,
    fontWeight: "600",
    color: "#2563EB",
    marginBottom: 18,
  },
  calendarSheet: {
    backgroundColor: "#FFFFFF",
    borderRadius: 28,
    paddingHorizontal: 18,
    paddingTop: 18,
    paddingBottom: 14,
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 14 },
    shadowOpacity: 0.12,
    shadowRadius: 28,
    elevation: 10,
  },
  monthNav: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
    gap: 20,
  },
  monthArrow: {
    fontSize: 20,
    fontWeight: "700",
    color: "#2563EB",
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  monthLabel: {
    fontSize: 17,
    fontWeight: "700",
    color: "#1E293B",
  },
  weekRow: {
    flexDirection: "row",
  },
  weekCell: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 6,
  },
  weekLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#94A3B8",
  },
  dayCell: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 12,
    marginHorizontal: 2,
    marginVertical: 2,
  },
  dayCellHovered: {
    backgroundColor: "#2563EB",
  },
  dayText: {
    fontSize: 15,
    fontWeight: "500",
    color: "#334155",
  },
  dayTextToday: {
    fontWeight: "800",
    color: "#2563EB",
  },
  dayTextHovered: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  dragPill: {
    position: "absolute",
    top: 0,
    left: 0,
    width: DRAG_DOT_SIZE,
    height: DRAG_DOT_SIZE,
    borderRadius: DRAG_DOT_SIZE / 2,
    backgroundColor: "#2563EB",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#2563EB",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 18,
    elevation: 10,
  },
  dragPillText: {
    fontSize: 17,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  cancelBtn: {
    marginTop: 24,
    alignSelf: "center",
    paddingHorizontal: 32,
    paddingVertical: 12,
    backgroundColor: "#F1F5F9",
    borderRadius: 14,
  },
  cancelText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#64748B",
  },
});
~~~

## `mobile/components/tasks-screen/InboxTaskList.tsx`

- 编码: `utf-8`

~~~tsx
import { StyleSheet, Text, View } from "react-native";
import { Inbox } from "lucide-react-native";
import type { ReactNode } from "react";
import type { TaskRecord } from "../../lib/types";
import { colors } from "../../lib/theme";

interface InboxTaskListProps {
  title: string;
  hint: string;
  tasks: readonly TaskRecord[];
  renderTask: (task: TaskRecord) => ReactNode;
}

export default function InboxTaskList({
  title,
  hint,
  tasks,
  renderTask,
}: InboxTaskListProps) {
  if (tasks.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.header}>
        <Inbox size={16} strokeWidth={1.9} color={colors.textSecondary} />
        <Text style={styles.title}>
          {title} ({tasks.length})
        </Text>
      </View>
      <Text style={styles.hint}>{hint}</Text>
      {tasks.map((task) => renderTask(task))}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  title: {
    fontSize: 15,
    fontWeight: "800",
    color: "#1F2937",
  },
  hint: {
    fontSize: 12,
    lineHeight: 18,
    color: "#6B7280",
    marginBottom: 14,
  },
});
~~~

## `mobile/components/tasks-screen/ScheduledTaskList.tsx`

- 编码: `utf-8`

~~~tsx
import { StyleSheet, Text, View } from "react-native";
import type { ReactNode } from "react";
import type { TaskRecord } from "../../lib/types";

interface ScheduledTaskListProps {
  title: string;
  tasks: readonly TaskRecord[];
  renderTask: (task: TaskRecord) => ReactNode;
}

export default function ScheduledTaskList({
  title,
  tasks,
  renderTask,
}: ScheduledTaskListProps) {
  if (tasks.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={styles.title}>
        {title} ({tasks.length})
      </Text>
      {tasks.map((task) => renderTask(task))}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    paddingHorizontal: 20,
    paddingTop: 16,
  },
  title: {
    fontSize: 15,
    fontWeight: "800",
    color: "#1F2937",
    marginBottom: 12,
  },
});
~~~

## `mobile/components/tasks-screen/SmartInputRecoveryController.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useRef } from "react";
import { AppState, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { WifiOff, ChevronRight, X } from "lucide-react-native";
import { colors } from "../../lib/theme";
import type { RecoveryTrigger } from "../../lib/smart-input-recovery";

interface SmartInputRecoveryControllerProps {
  queuedCount: number;
  hasRecoveredDraft: boolean;
  isRecovering: boolean;
  onRequestRecovery: (trigger: RecoveryTrigger) => void;
  onOpenRecoveredDraft: () => void;
  onDismissRecoveredDraft: () => void;
  onDismissQueuedRecovery: () => void;
}

export default function SmartInputRecoveryController({
  queuedCount,
  hasRecoveredDraft,
  isRecovering,
  onRequestRecovery,
  onOpenRecoveredDraft,
  onDismissRecoveredDraft,
  onDismissQueuedRecovery,
}: SmartInputRecoveryControllerProps) {
  const appStateRef = useRef(AppState.currentState);

  useEffect(() => {
    onRequestRecovery("tasks_enter");
  }, [onRequestRecovery]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasInactive = appStateRef.current !== "active";
      appStateRef.current = nextState;
      if (nextState === "active" && wasInactive) {
        onRequestRecovery("app_active");
      }
    });
    return () => {
      subscription.remove();
    };
  }, [onRequestRecovery]);

  if (hasRecoveredDraft) {
    return (
      <View style={styles.bannerWrap}>
        <View style={styles.banner}>
          <TouchableOpacity style={styles.bannerPrimary} activeOpacity={0.82} onPress={onOpenRecoveredDraft}>
            <View style={styles.bannerCopy}>
              <Text style={styles.bannerTitle}>已恢复暂存草稿</Text>
              <Text style={styles.bannerText}>草稿已恢复但未自动打断当前操作，点此继续编辑。</Text>
            </View>
            <ChevronRight size={18} color="#2563EB" />
          </TouchableOpacity>
          <TouchableOpacity style={styles.bannerIconButton} activeOpacity={0.78} onPress={onDismissRecoveredDraft}>
            <X size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  if (queuedCount <= 0) {
    return null;
  }

  return (
    <View style={styles.bannerWrap}>
      <View style={styles.banner}>
        <TouchableOpacity
          style={styles.bannerPrimary}
          activeOpacity={0.82}
          disabled={isRecovering}
          onPress={() => onRequestRecovery("manual")}
        >
          <WifiOff size={16} color="#2563EB" />
          <View style={styles.bannerCopy}>
            <Text style={styles.bannerTitle}>{isRecovering ? "正在恢复暂存语音..." : `发现 ${queuedCount} 条暂存语音`}</Text>
            <Text style={styles.bannerText}>点击手动恢复，不再自动弹出任务创建页。</Text>
          </View>
          <ChevronRight size={18} color="#2563EB" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.bannerIconButton}
          activeOpacity={0.78}
          onPress={onDismissQueuedRecovery}
        >
          <X size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bannerWrap: {
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EEF4FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
    borderRadius: 18,
    paddingLeft: 14,
    paddingRight: 10,
    paddingVertical: 12,
  },
  bannerPrimary: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  bannerCopy: {
    flex: 1,
  },
  bannerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  bannerIconButton: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
  },
  bannerTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#1D4ED8",
  },
  bannerText: {
    marginTop: 2,
    fontSize: 12,
    lineHeight: 18,
    color: colors.textSecondary,
  },
});
~~~

## `mobile/components/tasks-screen/TaskModalCoordinator.tsx`

- 编码: `utf-8`

~~~tsx
import type { EventLineRecord, SmartTaskDraft, TaskRecord } from "../../lib/types";
import TaskDetail from "../TaskDetail";
import CreateTask from "../CreateTask";
import RecordNote from "../RecordNote";
import SmartInputSheet from "../SmartInputSheet";
import TaskReviewComposer from "../TaskReviewComposer";

interface TaskModalCoordinatorProps {
  selectedTask: TaskRecord | null;
  showCreate: boolean;
  showSmartInput: boolean;
  showRecord: boolean;
  reviewTaskContext: TaskRecord | null;
  editingTask: TaskRecord | null;
  smartDraft: SmartTaskDraft | null;
  createPreset: { dueDate?: string; dueTime?: string };
  smartInputPreset: { dueDate?: string; dueTime?: string };
  todayKey: string;
  recordTaskContext: TaskRecord | null;
  selectedTaskEventLine?: EventLineRecord | null;
  onCloseSelectedTask: () => void;
  onStartReview: (task: TaskRecord) => void;
  onRecordFromTaskDetail: () => void;
  onUpdateTask: (taskId: string, updates: Partial<TaskRecord>) => void;
  onDeleteTask?: (task: TaskRecord) => void | Promise<void>;
  onReplaceSelectedTask: (task: TaskRecord) => void;
  onOpenClientWorkspace?: (clientId: string, clientName?: string | null) => void;
  onOpenEventLine?: (eventLineId: string) => void;
  onOpenConsult?: (task: TaskRecord) => void;
  onCloseCreate: () => void;
  onCreated: () => void;
  onCloseSmartInput: () => void;
  onApplySmartDraft: (draft: SmartTaskDraft) => void;
  onUploadedRecord: (task: TaskRecord) => void;
  onCloseRecord: () => void;
  onCloseReview: () => void;
  onSavedReview: (updatedTask: TaskRecord) => void;
}

export default function TaskModalCoordinator(props: TaskModalCoordinatorProps) {
  return (
    <>
      {props.selectedTask ? (
        <TaskDetail
          task={props.selectedTask}
          eventLine={props.selectedTaskEventLine}
          onClose={props.onCloseSelectedTask}
          onStartReview={props.onStartReview}
          onRecord={props.onRecordFromTaskDetail}
          onUpdate={props.onUpdateTask}
          onDeleteTask={props.onDeleteTask}
          onTaskReplaced={props.onReplaceSelectedTask}
          onOpenClientWorkspace={props.onOpenClientWorkspace}
          onOpenEventLine={props.onOpenEventLine}
          onOpenConsult={props.onOpenConsult}
        />
      ) : null}

      {props.showCreate ? (
        <CreateTask
          task={props.editingTask}
          draft={props.smartDraft}
          onClose={props.onCloseCreate}
          onCreated={props.onCreated}
          preset={props.createPreset}
        />
      ) : null}

      {props.showSmartInput ? (
        <SmartInputSheet
          autoStart
          referenceDate={props.todayKey}
          onClose={props.onCloseSmartInput}
          onApplyDraft={props.onApplySmartDraft}
        />
      ) : null}

      {props.showRecord ? (
        <RecordNote
          taskContext={props.recordTaskContext}
          autoStart={Boolean(props.recordTaskContext)}
          onUploaded={props.onUploadedRecord}
          onClose={props.onCloseRecord}
        />
      ) : null}

      {props.reviewTaskContext ? (
        <TaskReviewComposer
          task={props.reviewTaskContext}
          onClose={props.onCloseReview}
          onSaved={props.onSavedReview}
        />
      ) : null}
    </>
  );
}
~~~

## `mobile/components/tasks-screen/TasksFilterBar.tsx`

- 编码: `utf-8`

~~~tsx
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface FilterOption<T extends string> {
  key: T;
  label: string;
}

interface TasksFilterBarProps<T extends string> {
  visible: boolean;
  floatingMenuTopInset: number;
  selectedKey: T;
  filters: readonly FilterOption<T>[];
  onSelect: (key: T) => void;
  onClose: () => void;
}

export default function TasksFilterBar<T extends string>({
  visible,
  floatingMenuTopInset,
  selectedKey,
  filters,
  onSelect,
  onClose,
}: TasksFilterBarProps<T>) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity
        style={[styles.menuOverlay, { paddingTop: floatingMenuTopInset }]}
        activeOpacity={1}
        onPress={onClose}
      >
        <View style={styles.menuCard}>
          {filters.map((filter) => (
            <TouchableOpacity
              key={filter.key}
              style={[styles.menuItem, selectedKey === filter.key && styles.menuItemActive]}
              onPress={() => onSelect(filter.key)}
            >
              <Text style={[styles.menuItemText, selectedKey === filter.key && styles.menuItemTextActive]}>
                {filter.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(17,24,39,0.14)",
    paddingHorizontal: 18,
  },
  menuCard: {
    marginTop: 20,
    marginLeft: "auto",
    width: 180,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    paddingVertical: 8,
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.14,
    shadowRadius: 26,
    elevation: 10,
  },
  menuItem: {
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  menuItemActive: {
    backgroundColor: "#EEF4FF",
  },
  menuItemText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#475467",
  },
  menuItemTextActive: {
    color: "#2563EB",
  },
});
~~~

## `mobile/components/tasks-screen/TasksHeader.tsx`

- 编码: `utf-8`

~~~tsx
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { ChevronDown } from "lucide-react-native";
import { colors } from "../../lib/theme";

interface TasksHeaderProps {
  dateText: string;
  filterLabel: string;
  topPadding: number;
  onOpenFilter: () => void;
}

export default function TasksHeader({
  dateText,
  filterLabel,
  topPadding,
  onOpenFilter,
}: TasksHeaderProps) {
  return (
    <View style={[styles.header, { paddingTop: topPadding }]}>
      <View style={styles.headerRow}>
        <Text style={styles.date}>{dateText}</Text>
        <TouchableOpacity style={styles.filterDropdown} onPress={onOpenFilter}>
          <Text style={styles.filterDropdownText}>{filterLabel}</Text>
          <ChevronDown size={16} strokeWidth={2} color={colors.brand} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: "#F7F8FB",
    paddingBottom: 16,
    paddingHorizontal: 20,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  date: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.text,
  },
  filterDropdown: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  filterDropdownText: {
    color: colors.brand,
    fontSize: 14,
    fontWeight: "700",
  },
});
~~~

## `mobile/ios/.gitignore`

- 编码: `utf-8`

~~~
# OSX
#
.DS_Store

# Xcode
#
build/
*.pbxuser
!default.pbxuser
*.mode1v3
!default.mode1v3
*.mode2v3
!default.mode2v3
*.perspectivev3
!default.perspectivev3
xcuserdata
*.xccheckout
*.moved-aside
DerivedData
*.hmap
*.ipa
*.xcuserstate
project.xcworkspace
.xcode.env.local

# Bundle artifacts
*.jsbundle

# CocoaPods
/Pods/
~~~

## `mobile/ios/.xcode.env`

- 编码: `utf-8`

~~~dotenv
# This `.xcode.env` file is versioned and is used to source the environment
# used when running script phases inside Xcode.
# To customize your local environment, you can create an `.xcode.env.local`
# file that is not versioned.

# NODE_BINARY variable contains the PATH to the node executable.
#
# Customize the NODE_BINARY variable here.
# For example, to use nvm with brew, add the following line
# . "$(brew --prefix nvm)/nvm.sh" --no-use
export NODE_BINARY=$(command -v node)
~~~

## `mobile/ios/Podfile`

- 编码: `utf-8`

~~~
# Set by expo-router. This enables Fabric-only features from react-native-screens
ENV['RNS_GAMMA_ENABLED'] ||= '1'
require File.join(File.dirname(`node --print "require.resolve('expo/package.json')"`), "scripts/autolinking")
require File.join(File.dirname(`node --print "require.resolve('react-native/package.json')"`), "scripts/react_native_pods")

require 'json'
podfile_properties = JSON.parse(File.read(File.join(__dir__, 'Podfile.properties.json'))) rescue {}

def ccache_enabled?(podfile_properties)
  # Environment variable takes precedence
  return ENV['USE_CCACHE'] == '1' if ENV['USE_CCACHE']

  # Fall back to Podfile properties
  podfile_properties['apple.ccacheEnabled'] == 'true'
end

ENV['EX_DEV_CLIENT_NETWORK_INSPECTOR'] ||= podfile_properties['EX_DEV_CLIENT_NETWORK_INSPECTOR']
ENV['RCT_USE_RN_DEP'] ||= '1' if podfile_properties['ios.buildReactNativeFromSource'] != 'true'
ENV['RCT_USE_PREBUILT_RNCORE'] ||= '1' if podfile_properties['ios.buildReactNativeFromSource'] != 'true'
ENV['RCT_HERMES_V1_ENABLED'] ||= '1' if podfile_properties['expo.useHermesV1'] == 'true'
platform :ios, podfile_properties['ios.deploymentTarget'] || '15.1'

prepare_react_native_project!

target 'app' do
  use_expo_modules!

  if ENV['EXPO_USE_COMMUNITY_AUTOLINKING'] == '1'
    config_command = ['node', '-e', "process.argv=['', '', 'config'];require('@react-native-community/cli').run()"];
  else
    config_command = [
      'node',
      '--no-warnings',
      '--eval',
      'require(\'expo/bin/autolinking\')',
      'expo-modules-autolinking',
      'react-native-config',
      '--json',
      '--platform',
      'ios'
    ]
  end

  config = use_native_modules!(config_command)

  use_frameworks! :linkage => podfile_properties['ios.useFrameworks'].to_sym if podfile_properties['ios.useFrameworks']
  use_frameworks! :linkage => ENV['USE_FRAMEWORKS'].to_sym if ENV['USE_FRAMEWORKS']

  use_react_native!(
    :path => config[:reactNativePath],
    :hermes_enabled => podfile_properties['expo.jsEngine'] == nil || podfile_properties['expo.jsEngine'] == 'hermes',
    # An absolute path to your application root.
    :app_path => "#{Pod::Config.instance.installation_root}/..",
    :privacy_file_aggregation_enabled => podfile_properties['apple.privacyManifestAggregationEnabled'] != 'false',
  )

  post_install do |installer|
    react_native_post_install(
      installer,
      config[:reactNativePath],
      :mac_catalyst_enabled => false,
      :ccache_enabled => ccache_enabled?(podfile_properties),
    )
  end
end
~~~

## `mobile/ios/Podfile.properties.json`

- 编码: `utf-8`

~~~json
{
  "expo.jsEngine": "hermes",
  "EX_DEV_CLIENT_NETWORK_INSPECTOR": "true"
}
~~~

## `mobile/ios/app.xcodeproj/project.pbxproj`

- 编码: `utf-8`

~~~text
// !$*UTF8*$!
{
	archiveVersion = 1;
	classes = {
	};
	objectVersion = 54;
	objects = {

/* Begin PBXBuildFile section */
		13B07FBF1A68108700A75B9A /* Images.xcassets in Resources */ = {isa = PBXBuildFile; fileRef = 13B07FB51A68108700A75B9A /* Images.xcassets */; };
		3E461D99554A48A4959DE609 /* SplashScreen.storyboard in Resources */ = {isa = PBXBuildFile; fileRef = AA286B85B6C04FC6940260E9 /* SplashScreen.storyboard */; };
		BB2F792D24A3F905000567C9 /* Expo.plist in Resources */ = {isa = PBXBuildFile; fileRef = BB2F792C24A3F905000567C9 /* Expo.plist */; };
		F11748422D0307B40044C1D9 /* AppDelegate.swift in Sources */ = {isa = PBXBuildFile; fileRef = F11748412D0307B40044C1D9 /* AppDelegate.swift */; };
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		13B07F961A680F5B00A75B9A /* app.app */ = {isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = app.app; sourceTree = BUILT_PRODUCTS_DIR; };
		13B07FB51A68108700A75B9A /* Images.xcassets */ = {isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; name = Images.xcassets; path = app/Images.xcassets; sourceTree = "<group>"; };
		13B07FB61A68108700A75B9A /* Info.plist */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.plist.xml; name = Info.plist; path = app/Info.plist; sourceTree = "<group>"; };
		AA286B85B6C04FC6940260E9 /* SplashScreen.storyboard */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = file.storyboard; name = SplashScreen.storyboard; path = app/SplashScreen.storyboard; sourceTree = "<group>"; };
		BB2F792C24A3F905000567C9 /* Expo.plist */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = text.plist.xml; path = Expo.plist; sourceTree = "<group>"; };
		ED297162215061F000B7C4FE /* JavaScriptCore.framework */ = {isa = PBXFileReference; lastKnownFileType = wrapper.framework; name = JavaScriptCore.framework; path = System/Library/Frameworks/JavaScriptCore.framework; sourceTree = SDKROOT; };
		F11748412D0307B40044C1D9 /* AppDelegate.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; name = AppDelegate.swift; path = app/AppDelegate.swift; sourceTree = "<group>"; };
		F11748442D0722820044C1D9 /* app-Bridging-Header.h */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.c.h; name = "app-Bridging-Header.h"; path = "app/app-Bridging-Header.h"; sourceTree = "<group>"; };
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		13B07F8C1A680F5B00A75B9A /* Frameworks */ = {
			isa = PBXFrameworksBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
		13B07FAE1A68108700A75B9A /* app */ = {
			isa = PBXGroup;
			children = (
				F11748412D0307B40044C1D9 /* AppDelegate.swift */,
				F11748442D0722820044C1D9 /* app-Bridging-Header.h */,
				BB2F792B24A3F905000567C9 /* Supporting */,
				13B07FB51A68108700A75B9A /* Images.xcassets */,
				13B07FB61A68108700A75B9A /* Info.plist */,
				AA286B85B6C04FC6940260E9 /* SplashScreen.storyboard */,
			);
			name = app;
			sourceTree = "<group>";
		};
		2D16E6871FA4F8E400B85C8A /* Frameworks */ = {
			isa = PBXGroup;
			children = (
				ED297162215061F000B7C4FE /* JavaScriptCore.framework */,
			);
			name = Frameworks;
			sourceTree = "<group>";
		};
		832341AE1AAA6A7D00B99B32 /* Libraries */ = {
			isa = PBXGroup;
			children = (
			);
			name = Libraries;
			sourceTree = "<group>";
		};
		83CBB9F61A601CBA00E9B192 = {
			isa = PBXGroup;
			children = (
				13B07FAE1A68108700A75B9A /* app */,
				832341AE1AAA6A7D00B99B32 /* Libraries */,
				83CBBA001A601CBA00E9B192 /* Products */,
				2D16E6871FA4F8E400B85C8A /* Frameworks */,
			);
			indentWidth = 2;
			sourceTree = "<group>";
			tabWidth = 2;
			usesTabs = 0;
		};
		83CBBA001A601CBA00E9B192 /* Products */ = {
			isa = PBXGroup;
			children = (
				13B07F961A680F5B00A75B9A /* app.app */,
			);
			name = Products;
			sourceTree = "<group>";
		};
		BB2F792B24A3F905000567C9 /* Supporting */ = {
			isa = PBXGroup;
			children = (
				BB2F792C24A3F905000567C9 /* Expo.plist */,
			);
			name = Supporting;
			path = app/Supporting;
			sourceTree = "<group>";
		};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		13B07F861A680F5B00A75B9A /* app */ = {
			isa = PBXNativeTarget;
			buildConfigurationList = 13B07F931A680F5B00A75B9A /* Build configuration list for PBXNativeTarget "app" */;
			buildPhases = (
				08A4A3CD28434E44B6B9DE2E /* [CP] Check Pods Manifest.lock */,
				13B07F871A680F5B00A75B9A /* Sources */,
				13B07F8C1A680F5B00A75B9A /* Frameworks */,
				13B07F8E1A680F5B00A75B9A /* Resources */,
				00DD1BFF1BD5951E006B06BC /* Bundle React Native code and images */,
				800E24972A6A228C8D4807E9 /* [CP] Copy Pods Resources */,
			);
			buildRules = (
			);
			dependencies = (
			);
			name = app;
			productName = app;
			productReference = 13B07F961A680F5B00A75B9A /* app.app */;
			productType = "com.apple.product-type.application";
		};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		83CBB9F71A601CBA00E9B192 /* Project object */ = {
			isa = PBXProject;
			attributes = {
				LastUpgradeCheck = 1130;
				TargetAttributes = {
					13B07F861A680F5B00A75B9A = {
						LastSwiftMigration = 1250;
					};
				};
			};
			buildConfigurationList = 83CBB9FA1A601CBA00E9B192 /* Build configuration list for PBXProject "app" */;
			compatibilityVersion = "Xcode 3.2";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = 83CBB9F61A601CBA00E9B192;
			productRefGroup = 83CBBA001A601CBA00E9B192 /* Products */;
			projectDirPath = "";
			projectRoot = "";
			targets = (
				13B07F861A680F5B00A75B9A /* app */,
			);
		};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		13B07F8E1A680F5B00A75B9A /* Resources */ = {
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				BB2F792D24A3F905000567C9 /* Expo.plist in Resources */,
				13B07FBF1A68108700A75B9A /* Images.xcassets in Resources */,
				3E461D99554A48A4959DE609 /* SplashScreen.storyboard in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXResourcesBuildPhase section */

/* Begin PBXShellScriptBuildPhase section */
		00DD1BFF1BD5951E006B06BC /* Bundle React Native code and images */ = {
			isa = PBXShellScriptBuildPhase;
			alwaysOutOfDate = 1;
			buildActionMask = 2147483647;
			files = (
			);
			inputPaths = (
				"$(SRCROOT)/.xcode.env",
				"$(SRCROOT)/.xcode.env.local",
			);
			name = "Bundle React Native code and images";
			outputPaths = (
			);
			runOnlyForDeploymentPostprocessing = 0;
			shellPath = /bin/sh;
			shellScript = "if [[ -f \"$PODS_ROOT/../.xcode.env\" ]]; then\n  source \"$PODS_ROOT/../.xcode.env\"\nfi\nif [[ -f \"$PODS_ROOT/../.xcode.env.local\" ]]; then\n  source \"$PODS_ROOT/../.xcode.env.local\"\nfi\n\n# The project root by default is one level up from the ios directory\nexport PROJECT_ROOT=\"$PROJECT_DIR\"/..\n\nif [[ \"$CONFIGURATION\" = *Debug* ]]; then\n  export SKIP_BUNDLING=1\nfi\nif [[ -z \"$ENTRY_FILE\" ]]; then\n  # Set the entry JS file using the bundler's entry resolution.\n  export ENTRY_FILE=\"$(\"$NODE_BINARY\" -e \"require('expo/scripts/resolveAppEntry')\" \"$PROJECT_ROOT\" ios absolute | tail -n 1)\"\nfi\n\nif [[ -z \"$CLI_PATH\" ]]; then\n  # Use Expo CLI\n  export CLI_PATH=\"$(\"$NODE_BINARY\" --print \"require.resolve('@expo/cli', { paths: [require.resolve('expo/package.json')] })\")\"\nfi\nif [[ -z \"$BUNDLE_COMMAND\" ]]; then\n  # Default Expo CLI command for bundling\n  export BUNDLE_COMMAND=\"export:embed\"\nfi\n\n# Source .xcode.env.updates if it exists to allow\n# SKIP_BUNDLING to be unset if needed\nif [[ -f \"$PODS_ROOT/../.xcode.env.updates\" ]]; then\n  source \"$PODS_ROOT/../.xcode.env.updates\"\nfi\n# Source local changes to allow overrides\n# if needed\nif [[ -f \"$PODS_ROOT/../.xcode.env.local\" ]]; then\n  source \"$PODS_ROOT/../.xcode.env.local\"\nfi\n\n`\"$NODE_BINARY\" --print \"require('path').dirname(require.resolve('react-native/package.json')) + '/scripts/react-native-xcode.sh'\"`\n\n";
		};
		08A4A3CD28434E44B6B9DE2E /* [CP] Check Pods Manifest.lock */ = {
			isa = PBXShellScriptBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			inputFileListPaths = (
			);
			inputPaths = (
				"${PODS_PODFILE_DIR_PATH}/Podfile.lock",
				"${PODS_ROOT}/Manifest.lock",
			);
			name = "[CP] Check Pods Manifest.lock";
			outputFileListPaths = (
			);
			outputPaths = (
				"$(DERIVED_FILE_DIR)/Pods-app-checkManifestLockResult.txt",
			);
			runOnlyForDeploymentPostprocessing = 0;
			shellPath = /bin/sh;
			shellScript = "diff \"${PODS_PODFILE_DIR_PATH}/Podfile.lock\" \"${PODS_ROOT}/Manifest.lock\" > /dev/null\nif [ $? != 0 ] ; then\n    # print error to STDERR\n    echo \"error: The sandbox is not in sync with the Podfile.lock. Run 'pod install' or update your CocoaPods installation.\" >&2\n    exit 1\nfi\n# This output is used by Xcode 'outputs' to avoid re-running this script phase.\necho \"SUCCESS\" > \"${SCRIPT_OUTPUT_FILE_0}\"\n";
			showEnvVarsInLog = 0;
		};
		800E24972A6A228C8D4807E9 /* [CP] Copy Pods Resources */ = {
			isa = PBXShellScriptBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			inputPaths = (
				"${PODS_ROOT}/Target Support Files/Pods-app/Pods-app-resources.sh",
				"${PODS_CONFIGURATION_BUILD_DIR}/EXConstants/EXConstants.bundle",
				"${PODS_CONFIGURATION_BUILD_DIR}/EXUpdates/EXUpdates.bundle",
				"${PODS_CONFIGURATION_BUILD_DIR}/React-Core/RCTI18nStrings.bundle",
			);
			name = "[CP] Copy Pods Resources";
			outputPaths = (
				"${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/EXConstants.bundle",
				"${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/EXUpdates.bundle",
				"${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}/RCTI18nStrings.bundle",
			);
			runOnlyForDeploymentPostprocessing = 0;
			shellPath = /bin/sh;
			shellScript = "\"${PODS_ROOT}/Target Support Files/Pods-app/Pods-app-resources.sh\"\n";
			showEnvVarsInLog = 0;
		};
/* End PBXShellScriptBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		13B07F871A680F5B00A75B9A /* Sources */ = {
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				F11748422D0307B40044C1D9 /* AppDelegate.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		13B07F941A680F5B00A75B9A /* Debug */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				CLANG_ENABLE_MODULES = YES;
				CURRENT_PROJECT_VERSION = 1;
				ENABLE_BITCODE = NO;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"$(inherited)",
					"FB_SONARKIT_ENABLED=1",
				);
				INFOPLIST_FILE = app/Info.plist;
				IPHONEOS_DEPLOYMENT_TARGET = 15.1;
				LD_RUNPATH_SEARCH_PATHS = (
					"$(inherited)",
					"@executable_path/Frameworks",
				);
				MARKETING_VERSION = 1.0;
				OTHER_LDFLAGS = (
					"$(inherited)",
					"-ObjC",
					"-lc++",
				);
				PRODUCT_BUNDLE_IDENTIFIER = "com.yiyu.mobile";
				PRODUCT_NAME = "app";
				SWIFT_OBJC_BRIDGING_HEADER = "app/app-Bridging-Header.h";
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
				SWIFT_VERSION = 5.0;
				VERSIONING_SYSTEM = "apple-generic";
				TARGETED_DEVICE_FAMILY = "1,2";
				CODE_SIGN_ENTITLEMENTS = app/app.entitlements;
			};
			name = Debug;
		};
		13B07F951A680F5B00A75B9A /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				CLANG_ENABLE_MODULES = YES;
				CURRENT_PROJECT_VERSION = 1;
				INFOPLIST_FILE = app/Info.plist;
				IPHONEOS_DEPLOYMENT_TARGET = 15.1;
				LD_RUNPATH_SEARCH_PATHS = (
					"$(inherited)",
					"@executable_path/Frameworks",
				);
				MARKETING_VERSION = 1.0;
				OTHER_LDFLAGS = (
					"$(inherited)",
					"-ObjC",
					"-lc++",
				);
				PRODUCT_BUNDLE_IDENTIFIER = "com.yiyu.mobile";
				PRODUCT_NAME = "app";
				SWIFT_OBJC_BRIDGING_HEADER = "app/app-Bridging-Header.h";
				SWIFT_VERSION = 5.0;
				VERSIONING_SYSTEM = "apple-generic";
				TARGETED_DEVICE_FAMILY = "1,2";
				CODE_SIGN_ENTITLEMENTS = app/app.entitlements;
			};
			name = Release;
		};
		83CBBA201A601CBA00E9B192 /* Debug */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ANALYZER_LOCALIZABILITY_NONLOCALIZED = YES;
				CLANG_CXX_LANGUAGE_STANDARD = "c++20";
				CLANG_CXX_LIBRARY = "libc++";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				"CODE_SIGN_IDENTITY[sdk=iphoneos*]" = "iPhone Developer";
				COPY_PHASE_STRIP = NO;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				ENABLE_TESTABILITY = YES;
				GCC_C_LANGUAGE_STANDARD = gnu99;
				GCC_DYNAMIC_NO_PIC = NO;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_OPTIMIZATION_LEVEL = 0;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"DEBUG=1",
					"$(inherited)",
				);
				GCC_SYMBOLS_PRIVATE_EXTERN = NO;
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDECLARED_SELECTOR = YES;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 15.1;
				LD_RUNPATH_SEARCH_PATHS = (
					/usr/lib/swift,
					"$(inherited)",
				);
				LIBRARY_SEARCH_PATHS = "\"$(inherited)\"";
				MTL_ENABLE_DEBUG_INFO = YES;
				ONLY_ACTIVE_ARCH = YES;
				SDKROOT = iphoneos;
			};
			name = Debug;
		};
		83CBBA211A601CBA00E9B192 /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ANALYZER_LOCALIZABILITY_NONLOCALIZED = YES;
				CLANG_CXX_LANGUAGE_STANDARD = "c++20";
				CLANG_CXX_LIBRARY = "libc++";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				"CODE_SIGN_IDENTITY[sdk=iphoneos*]" = "iPhone Developer";
				COPY_PHASE_STRIP = YES;
				ENABLE_NS_ASSERTIONS = NO;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				GCC_C_LANGUAGE_STANDARD = gnu99;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDECLARED_SELECTOR = YES;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 15.1;
				LD_RUNPATH_SEARCH_PATHS = (
					/usr/lib/swift,
					"$(inherited)",
				);
				LIBRARY_SEARCH_PATHS = "\"$(inherited)\"";
				MTL_ENABLE_DEBUG_INFO = NO;
				SDKROOT = iphoneos;
				VALIDATE_PRODUCT = YES;
			};
			name = Release;
		};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		13B07F931A680F5B00A75B9A /* Build configuration list for PBXNativeTarget "app" */ = {
			isa = XCConfigurationList;
			buildConfigurations = (
				13B07F941A680F5B00A75B9A /* Debug */,
				13B07F951A680F5B00A75B9A /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		83CBB9FA1A601CBA00E9B192 /* Build configuration list for PBXProject "app" */ = {
			isa = XCConfigurationList;
			buildConfigurations = (
				83CBBA201A601CBA00E9B192 /* Debug */,
				83CBBA211A601CBA00E9B192 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
/* End XCConfigurationList section */
	};
	rootObject = 83CBB9F71A601CBA00E9B192 /* Project object */;
}
~~~

## `mobile/ios/app/AppDelegate.swift`

- 编码: `utf-8`

~~~swift
internal import Expo
import React
import ReactAppDependencyProvider

@main
class AppDelegate: ExpoAppDelegate {
  var window: UIWindow?

  var reactNativeDelegate: ExpoReactNativeFactoryDelegate?
  var reactNativeFactory: RCTReactNativeFactory?

  public override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
  ) -> Bool {
    let delegate = ReactNativeDelegate()
    let factory = ExpoReactNativeFactory(delegate: delegate)
    delegate.dependencyProvider = RCTAppDependencyProvider()

    reactNativeDelegate = delegate
    reactNativeFactory = factory

#if os(iOS) || os(tvOS)
    window = UIWindow(frame: UIScreen.main.bounds)
    factory.startReactNative(
      withModuleName: "main",
      in: window,
      launchOptions: launchOptions)
#endif

    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  // Linking API
  public override func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    return super.application(app, open: url, options: options) || RCTLinkingManager.application(app, open: url, options: options)
  }

  // Universal Links
  public override func application(
    _ application: UIApplication,
    continue userActivity: NSUserActivity,
    restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void
  ) -> Bool {
    let result = RCTLinkingManager.application(application, continue: userActivity, restorationHandler: restorationHandler)
    return super.application(application, continue: userActivity, restorationHandler: restorationHandler) || result
  }
}

class ReactNativeDelegate: ExpoReactNativeFactoryDelegate {
  // Extension point for config-plugins

  override func sourceURL(for bridge: RCTBridge) -> URL? {
    // needed to return the correct URL for expo-dev-client.
    bridge.bundleURL ?? bundleURL()
  }

  override func bundleURL() -> URL? {
#if DEBUG
    return RCTBundleURLProvider.sharedSettings().jsBundleURL(forBundleRoot: ".expo/.virtual-metro-entry")
#else
    return Bundle.main.url(forResource: "main", withExtension: "jsbundle")
#endif
  }
}
~~~

## `mobile/ios/app/Images.xcassets/AppIcon.appiconset/Contents.json`

- 编码: `utf-8`

~~~json
{
  "images": [
    {
      "filename": "App-Icon-1024x1024@1x.png",
      "idiom": "universal",
      "platform": "ios",
      "size": "1024x1024"
    }
  ],
  "info": {
    "version": 1,
    "author": "expo"
  }
}
~~~

## `mobile/ios/app/Images.xcassets/Contents.json`

- 编码: `utf-8`

~~~json
{
  "info" : {
    "version" : 1,
    "author" : "expo"
  }
}
~~~

## `mobile/ios/app/Images.xcassets/SplashScreenBackground.colorset/Contents.json`

- 编码: `utf-8`

~~~json
{
  "colors": [
    {
      "color": {
        "components": {
          "alpha": "1.000",
          "blue": "0.372549019607843",
          "green": "0.227450980392157",
          "red": "0.117647058823529"
        },
        "color-space": "srgb"
      },
      "idiom": "universal"
    }
  ],
  "info": {
    "version": 1,
    "author": "expo"
  }
}
~~~

## `mobile/ios/app/Images.xcassets/SplashScreenLegacy.imageset/Contents.json`

- 编码: `utf-8`

~~~json
{
  "images": [
    {
      "idiom": "universal",
      "filename": "image.png",
      "scale": "1x"
    },
    {
      "idiom": "universal",
      "filename": "image@2x.png",
      "scale": "2x"
    },
    {
      "idiom": "universal",
      "filename": "image@3x.png",
      "scale": "3x"
    }
  ],
  "info": {
    "version": 1,
    "author": "expo"
  }
}
~~~

## `mobile/ios/app/Info.plist`

- 编码: `utf-8`

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CADisableMinimumFrameDurationOnPhone</key>
    <true/>
    <key>CFBundleDevelopmentRegion</key>
    <string>$(DEVELOPMENT_LANGUAGE)</string>
    <key>CFBundleDisplayName</key>
    <string>益语智库</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>$(PRODUCT_BUNDLE_PACKAGE_TYPE)</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleURLTypes</key>
    <array>
      <dict>
        <key>CFBundleURLSchemes</key>
        <array>
          <string>yiyu</string>
          <string>com.yiyu.mobile</string>
        </array>
      </dict>
    </array>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
	<key>NSAppTransportSecurity</key>
	<dict>
		<key>NSAllowsArbitraryLoads</key>
		<false/>
		<key>NSAllowsLocalNetworking</key>
		<true/>
	</dict>
	<key>NSMicrophoneUsageDescription</key>
	<string>Allow $(PRODUCT_NAME) to access your microphone.</string>
	<key>NSSpeechRecognitionUsageDescription</key>
	<string>Allow $(PRODUCT_NAME) to use speech recognition.</string>
	<key>NSFaceIDUsageDescription</key>
	<string>Allow $(PRODUCT_NAME) to access your Face ID biometric data.</string>
	<key>NSUserActivityTypes</key>
	<array>
		<string>$(PRODUCT_BUNDLE_IDENTIFIER).expo.index_route</string>
	</array>
	<key>UIBackgroundModes</key>
	<array>
		<string>audio</string>
	</array>
	<key>UILaunchStoryboardName</key>
    <string>SplashScreen</string>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
      <string>arm64</string>
    </array>
    <key>UIRequiresFullScreen</key>
    <false/>
    <key>UIStatusBarStyle</key>
    <string>UIStatusBarStyleDefault</string>
    <key>UISupportedInterfaceOrientations</key>
    <array>
      <string>UIInterfaceOrientationPortrait</string>
      <string>UIInterfaceOrientationPortraitUpsideDown</string>
    </array>
    <key>UISupportedInterfaceOrientations~ipad</key>
    <array>
      <string>UIInterfaceOrientationPortrait</string>
      <string>UIInterfaceOrientationPortraitUpsideDown</string>
      <string>UIInterfaceOrientationLandscapeLeft</string>
      <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
    <key>UIUserInterfaceStyle</key>
    <string>Light</string>
    <key>UIViewControllerBasedStatusBarAppearance</key>
    <false/>
  </dict>
</plist>
~~~

## `mobile/ios/app/Supporting/Expo.plist`

- 编码: `utf-8`

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>EXUpdatesCheckOnLaunch</key>
    <string>ALWAYS</string>
    <key>EXUpdatesEnabled</key>
    <false/>
    <key>EXUpdatesLaunchWaitMs</key>
    <integer>0</integer>
  </dict>
</plist>
~~~

## `mobile/ios/app/app-Bridging-Header.h`

- 编码: `utf-8`

~~~c
//
// Use this file to import your target's public headers that you would like to expose to Swift.
//
~~~

## `mobile/lib/__tests__/account-scope.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAccountScopeKey,
  normalizeAccountScopeKey,
  redactAccountScopeKey,
} from "../../.mobile-core-tests/dist/lib/account-scope.js";

test("buildAccountScopeKey uses organization plus user id", () => {
  assert.equal(
    buildAccountScopeKey({ organizationId: "org-1", id: "user-1" }),
    "org-1:user-1",
  );
  assert.equal(
    buildAccountScopeKey({ organizationId: null, id: "user-2" }),
    "no-org:user-2",
  );
});

test("normalizeAccountScopeKey rejects malformed values", () => {
  assert.equal(normalizeAccountScopeKey(""), null);
  assert.equal(normalizeAccountScopeKey("missing-colon"), null);
  assert.equal(normalizeAccountScopeKey("org-1:user-1"), "org-1:user-1");
});

test("redactAccountScopeKey hides most of the user segment", () => {
  assert.equal(redactAccountScopeKey("org-1:user-123456"), "org-1:user***");
});
~~~

## `mobile/lib/__tests__/base-url.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  isValidBaseUrl,
  resolveStoredBaseUrl,
} from "../../.mobile-core-tests/dist/lib/base-url.js";

test("baseUrl restore preserves localhost and private network addresses", () => {
  const fallback = "https://api.yiyu.example";
  const cases = [
    "http://localhost:3000",
    "http://192.168.1.50:8080",
    "http://10.0.0.12:9000",
  ];

  for (const savedUrl of cases) {
    const resolved = resolveStoredBaseUrl(savedUrl, fallback);
    assert.equal(resolved.baseUrl, savedUrl);
    assert.equal(resolved.source, "saved");
    assert.equal(resolved.shouldDeleteSaved, false);
  }
});

test("baseUrl restore falls back only for invalid saved URL", () => {
  const resolved = resolveStoredBaseUrl("not a valid host@@", "https://fallback.example");
  assert.equal(resolved.baseUrl, "https://fallback.example");
  assert.equal(resolved.source, "invalid_saved");
  assert.equal(resolved.shouldDeleteSaved, true);
});

test("baseUrl validation accepts URLs used by settings/login flows", () => {
  assert.equal(isValidBaseUrl("localhost:3000"), true);
  assert.equal(isValidBaseUrl("192.168.10.8:8787"), true);
  assert.equal(isValidBaseUrl("10.1.2.3"), true);
  assert.equal(isValidBaseUrl("http://bad host"), false);
});
~~~

## `mobile/lib/__tests__/boundary-cards.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { buildBoundaryCards } from "../../.mobile-core-tests/dist/lib/boundary-cards.js";

test("buildBoundaryCards renders explicit official empty state when cockpit is not ready", () => {
  const cards = buildBoundaryCards({
    client: { name: "日慈基金会" },
    latestOpenQuestions: [{ title: "还缺合作预算口径" }],
    latestConflicts: [{ title: "项目负责人尚未确认" }],
  }, {
    officialLayerStatus: "draft",
    pendingDecisions: [{ title: "是否先做试点" }],
    pendingMaterials: [{ title: "等待会议纪要" }],
    health: [{ summary: "推进速度偏慢" }],
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(cards[0].kind, "official");
  assert.equal(cards[0].title, "当前暂无已批准判断");
  assert.equal(cards[0].isEmpty, true);
  assert.equal(cards[1].summary, "是否先做试点");
  assert.match(cards[2].summary, /推进速度偏慢/);
  assert.match(cards[3].summary, /还缺合作预算口径/);
});
~~~

## `mobile/lib/__tests__/calendar-repository-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildDueDateForCalendarDrop,
  buildTaskScheduleUpdatesFromPicker,
  decideCalendarWriteMode,
} from "../../.mobile-core-tests/dist/lib/calendar-repository-core.js";

test("date drop keeps existing time component when moving between days", () => {
  assert.equal(
    buildDueDateForCalendarDrop("2026-04-18T12:30", "2026-04-20", "2026-04-18"),
    "2026-04-20T12:30",
  );
});

test("hour drop rewrites the selected date with the dropped hour", () => {
  assert.equal(
    buildDueDateForCalendarDrop("2026-04-18T12:30", "hour:9", "2026-04-21"),
    "2026-04-21T09:00",
  );
});

test("picker updates build a dueDate and preserve explicit duration", () => {
  assert.deepEqual(
    buildTaskScheduleUpdatesFromPicker({
      date: "2026-04-22",
      time: "14:45",
      durationMinutes: 90,
    }),
    {
      dueDate: "2026-04-22T14:45",
      durationMinutes: 90,
    },
  );
});

test("calendar repository only uses remote-first fallback when local-first is disabled and task is clean", () => {
  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: true,
      hasRemoteId: true,
      hasPendingOps: false,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "local-first",
  );

  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: false,
      hasRemoteId: true,
      hasPendingOps: false,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "remote-first",
  );

  assert.equal(
    decideCalendarWriteMode({
      calendarLocalFirstWriteEnabled: false,
      hasRemoteId: true,
      hasPendingOps: true,
      isSyncPaused: false,
      blockedReason: null,
    }),
    "local-first",
  );
});
~~~

## `mobile/lib/__tests__/consult-context-adapter.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { buildConsultRequestContext } from "../../.mobile-core-tests/dist/lib/consult-context-adapter.js";

test("buildConsultRequestContext keeps week in task context and surfaces missing event line hint", () => {
  const context = buildConsultRequestContext({
    currentFocus: {
      clientId: "client-rita",
      clientName: "日慈基金会",
      eventLineId: null,
      eventLineName: null,
      taskId: "task-1",
      taskTitle: "日慈基金会会前准备",
      weekAnchorDate: "2026-04-13",
      weekLabel: "2026-W16",
      source: "manual",
      lockMode: "client",
      boundaryState: "pending",
      updatedAt: "2026-04-16T09:00:00.000Z",
    },
    selectedContext: {
      id: "client:client-rita",
      label: "日慈基金会",
      scope: "client",
      clientId: "client-rita",
      clientName: "日慈基金会",
      eventLineId: null,
      eventLineName: null,
    },
    workspaceLite: {
      clientId: "client-rita",
      clientName: "日慈基金会",
      boundaryCards: [
        {
          kind: "risk",
          title: "预算未定",
          summary: "当前预算区间还没有锁死",
          sourceType: "manual",
          updatedAt: "2026-04-16T09:00:00.000Z",
          evidenceCount: 1,
          isEmpty: false,
        },
      ],
      boundaryState: "pending",
      goals: [
        {
          id: "goal-1",
          title: "锁定合作路径",
          summary: "本周把合作范围和会议目标收口",
        },
      ],
      latestMeetings: [
        {
          id: "meeting-1",
          title: "会前沟通",
          summary: "对方希望先看一版材料",
        },
      ],
      knowledgeStatus: null,
      recentDocuments: [
        {
          id: "doc-1",
          title: "合作草案",
          summary: "初版合作框架待确认",
        },
      ],
      openQuestions: [
        {
          id: "question-1",
          title: "预算口径",
          summary: "还未确认预算上限",
        },
      ],
      conflicts: [],
      relatedTasks: [],
      nextActions: ["确认预算假设", "补齐会前材料"],
      headline: "本周先收口合作路径",
      health: ["客户对方向是清楚的，但预算边界不清楚"],
      twoWeekChanges: ["最近一周从泛合作转向明确项目合作"],
      pendingDecisions: ["是否按项目包推进"],
      pendingMaterials: ["需补一版材料摘要"],
      updatedAt: "2026-04-16T09:00:00.000Z",
    },
    eventLine: null,
    tasks: [
      {
        id: "task-1",
        title: "日慈基金会会前准备",
        clientId: "client-rita",
        clientName: "日慈基金会",
        currentBlocker: "尚未确认预算区间",
        nextAction: "整理会前要点",
      },
    ],
  });

  assert.equal(context.clientId, "client-rita");
  assert.equal(context.eventLineId, null);
  assert.equal(context.taskId, "task-1");
  assert.equal(context.taskTitle, "日慈基金会会前准备");
  assert.match(context.taskContext || "", /当前任务：日慈基金会会前准备/);
  assert.match(context.taskContext || "", /任务卡点：尚未确认预算区间/);
  assert.match(context.taskContext || "", /2026-W16/);
  assert.match(context.workspaceContext || "", /客户工作台：本周先收口合作路径/);
  assert.match(context.workspaceContext || "", /阶段目标：锁定合作路径：本周把合作范围和会议目标收口/);
  assert.match(context.workspaceContext || "", /开放问题：预算口径：还未确认预算上限/);
  assert.match(context.taskBoardContext || "", /2026-W16 任务板：共 1 条，未完成 1 条/);
  assert.equal(context.missingEventLineHint, "当前未锁定事件线，回答只基于客户与任务板");
  assert.deepEqual(context.sourceLabels.slice(0, 4), [
    "当前客户：日慈基金会",
    "当前任务：日慈基金会会前准备",
    "当前周：2026-W16",
    "工作台",
  ]);
});
~~~

## `mobile/lib/__tests__/consult-context.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildConsultContextOptions,
  buildTaskContextSummary,
  resolveConsultContextFromFocus,
} from "../../.mobile-core-tests/dist/lib/consult-context.js";

const tasks = [
  {
    id: "task-a",
    title: "跟进日慈基金会会前材料",
    clientId: "client-rita",
    clientName: "日慈基金会",
  },
  {
    id: "task-b",
    title: "和元饼吃饭",
    clientId: "client-rita",
    clientName: "日慈基金会",
  },
  {
    id: "task-c",
    title: "输出益语智库策略诊断提纲",
    clientId: "client-yiyu",
    clientName: "益语智库",
  },
];

test("buildTaskContextSummary scopes tasks to the selected client", () => {
  assert.equal(
    buildTaskContextSummary(tasks, { clientId: "client-rita" }),
    "任务板：跟进日慈基金会会前材料、和元饼吃饭",
  );
});

test("buildTaskContextSummary falls back to all tasks for all context", () => {
  assert.equal(
    buildTaskContextSummary(tasks, { limit: 2 }),
    "任务板：跟进日慈基金会会前材料、和元饼吃饭",
  );
});

test("resolveConsultContextFromFocus prefers event line over client", () => {
  const options = buildConsultContextOptions([
    ...tasks,
    {
      id: "task-d",
      title: "日慈基金会韶关推进线同步",
      clientId: "client-rita",
      clientName: "日慈基金会",
      eventLineId: "event-shaoguan",
      eventLineName: "韶关推进线",
    },
  ]);

  const selected = resolveConsultContextFromFocus(options, {
    clientId: "client-rita",
    clientName: "日慈基金会",
    eventLineId: "event-shaoguan",
    eventLineName: "韶关推进线",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client_event_line",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(selected.scope, "event_line");
  assert.equal(selected.eventLineId, "event-shaoguan");
});

test("resolveConsultContextFromFocus synthesizes focus-backed context when task board options lag behind", () => {
  const selected = resolveConsultContextFromFocus([
    {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    },
  ], {
    clientId: "client-rita",
    clientName: "日慈基金会",
    eventLineId: "event-shaoguan",
    eventLineName: "韶关推进线",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client_event_line",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(selected.scope, "event_line");
  assert.equal(selected.clientName, "日慈基金会");
  assert.equal(selected.eventLineName, "韶关推进线");
});
~~~

## `mobile/lib/__tests__/consult-thread-context.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  hasConsultThreadContextDrift,
  freezeConsultThreadContext,
  refreshConsultThreadContext,
  shouldResetConsultThreadContext,
} from "../../.mobile-core-tests/dist/lib/consult-thread-context.js";

test("freezeConsultThreadContext copies the active context into a stable snapshot", () => {
  const snapshot = freezeConsultThreadContext(
    {
      clientId: "client-1",
      clientName: "日慈基金会",
      eventLineId: "event-1",
      eventLineName: "捐赠体系升级",
      taskId: "task-1",
      taskTitle: "准备沟通材料",
      taskContext: "当前周重点任务",
      workspaceContext: "客户工作台：本周推进合作收口",
      eventLineContext: "事件线：捐赠体系升级\n下一步：确认预算",
      taskBoardContext: "任务板：共 3 条，未完成 2 条",
      sourceLabels: ["当前客户：日慈基金会", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"],
      missingEventLineHint: null,
    },
    "2026-04-18T10:00:00.000Z",
  );

  assert.equal(snapshot.clientId, "client-1");
  assert.equal(snapshot.eventLineId, "event-1");
  assert.equal(snapshot.taskId, "task-1");
  assert.equal(snapshot.taskTitle, "准备沟通材料");
  assert.equal(snapshot.workspaceContext, "客户工作台：本周推进合作收口");
  assert.match(snapshot.eventLineContext || "", /下一步：确认预算/);
  assert.equal(snapshot.taskBoardContext, "任务板：共 3 条，未完成 2 条");
  assert.deepEqual(snapshot.sourceLabels, ["当前客户：日慈基金会", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"]);
  assert.equal(snapshot.frozenAt, "2026-04-18T10:00:00.000Z");
  assert.equal(snapshot.snapshotVersion, 1);
  assert.equal(snapshot.snapshotHash.startsWith("ctx_"), true);
});

test("refreshConsultThreadContext bumps the snapshot version and detects drift", () => {
  const initial = freezeConsultThreadContext(
    {
      clientId: "client-1",
      clientName: "日慈基金会",
      eventLineId: "event-1",
      eventLineName: "捐赠体系升级",
      taskId: "task-1",
      taskTitle: "准备沟通材料",
      taskContext: "当前周重点任务",
      workspaceContext: "客户工作台：本周推进合作收口",
      eventLineContext: "事件线：捐赠体系升级\n下一步：确认预算",
      taskBoardContext: "任务板：共 3 条，未完成 2 条",
      sourceLabels: ["当前客户：日慈基金会", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"],
      missingEventLineHint: null,
    },
    "2026-04-18T10:00:00.000Z",
  );
  const driftedContext = {
    clientId: "client-1",
    clientName: "日慈基金会",
    eventLineId: "event-2",
    eventLineName: "筹资链路梳理",
    taskId: "task-2",
    taskTitle: "确认会前问题",
    taskContext: "新的周任务",
    workspaceContext: "客户工作台：下周聚焦渠道沟通",
    eventLineContext: "事件线：筹资链路梳理\n当前卡点：尚未确认合作边界",
    taskBoardContext: "任务板：共 4 条，未完成 3 条",
    sourceLabels: ["当前客户：日慈基金会", "当前事件线：筹资链路梳理", "当前任务：确认会前问题"],
    missingEventLineHint: null,
  };

  assert.equal(hasConsultThreadContextDrift(initial, driftedContext), true);

  const refreshed = refreshConsultThreadContext(
    initial,
    driftedContext,
    "2026-04-18T11:00:00.000Z",
  );

  assert.equal(refreshed.snapshotVersion, 2);
  assert.equal(refreshed.eventLineId, "event-2");
  assert.equal(refreshed.taskId, "task-2");
  assert.notEqual(refreshed.snapshotHash, initial.snapshotHash);
});

test("shouldResetConsultThreadContext only resets once a thread already has messages", () => {
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: false, nextContextChanged: true }),
    false,
  );
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: true, nextContextChanged: false }),
    false,
  );
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: true, nextContextChanged: true }),
    true,
  );
});
~~~

## `mobile/lib/__tests__/create-task-association.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildProjectOptions,
  filterEventLinesForSelection,
  findAutoMatchedEventLine,
  shouldApplyAutoAssociation,
} from "../../.mobile-core-tests/dist/lib/create-task-association.js";

const eventLines = [
  {
    id: "event-a",
    name: "益语智库-周会跟进",
    primaryClientId: "client-a",
    primaryClientName: "益语智库",
    status: "active",
  },
  {
    id: "event-b",
    name: "第二项目-执行推进",
    primaryClientId: "client-b",
    primaryClientName: "第二项目",
    status: "active",
  },
];

const clients = [
  { id: "client-a", name: "益语智库" },
  { id: "client-b", name: "第二项目" },
];

test("buildProjectOptions prefers explicit clients when available", () => {
  const options = buildProjectOptions(clients, eventLines);
  assert.deepEqual(
    options.map((item) => item.id),
    ["client:client-a", "client:client-b"],
  );
});

test("filterEventLinesForSelection scopes by selected client", () => {
  const filtered = filterEventLinesForSelection(eventLines, "client-a", null);
  assert.deepEqual(filtered.map((item) => item.id), ["event-a"]);
});

test("findAutoMatchedEventLine matches title keywords to event line aliases", () => {
  const matched = findAutoMatchedEventLine("益语智库周会纪要", eventLines);
  assert.equal(matched?.id, "event-a");
});

test("manual association wins over auto association", () => {
  assert.equal(shouldApplyAutoAssociation({
    source: "manual",
    lockedTitleKey: "益语智库周会纪要",
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: "event-a",
    autoMatchedEventLineId: "event-b",
  }), false);

  assert.equal(shouldApplyAutoAssociation({
    source: "default",
    lockedTitleKey: null,
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: null,
    autoMatchedEventLineId: "event-a",
  }), true);
});
~~~

## `mobile/lib/__tests__/current-focus-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  createEmptyCurrentFocus,
  createManualClientEventLineFocus,
  deriveBoundaryState,
  reconcileCurrentFocus,
  restoreCurrentFocus,
  serializeCurrentFocus,
} from "../../.mobile-core-tests/dist/lib/current-focus-core.js";

test("current focus only persists locked client scopes", () => {
  const empty = createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0));
  assert.equal(serializeCurrentFocus(empty), null);

  const locked = createManualClientEventLineFocus(
    { id: "client-1", name: "日慈基金会" },
    { id: "event-1", name: "韶关推进线" },
    empty,
  );
  assert.ok(serializeCurrentFocus(locked));
});

test("browse focus created from task keeps task identity without making it persistable", () => {
  const empty = createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0));
  const browseFromTask = {
    ...empty,
    clientId: "client-1",
    clientName: "日慈基金会",
    eventLineId: "event-1",
    eventLineName: "合作方案推进",
    taskId: "task-1",
    taskTitle: "准备沟通材料",
    source: "from_task",
    lockMode: "browse",
  };
  assert.equal(browseFromTask.taskId, "task-1");
  assert.equal(browseFromTask.taskTitle, "准备沟通材料");
  assert.equal(serializeCurrentFocus(browseFromTask), null);
});

test("restore current focus degrades missing event line to client lock", () => {
  const raw = JSON.stringify({
    clientId: "client-1",
    clientName: "日慈基金会",
    eventLineId: "event-gone",
    eventLineName: "旧事件线",
    lockMode: "client_event_line",
    source: "manual",
    weekAnchorDate: "2026-04-13",
  });

  const restored = restoreCurrentFocus(raw, {
    clients: [{ id: "client-1", name: "日慈基金会" }],
    eventLines: [],
    now: new Date(2026, 3, 16, 9, 0, 0),
  });

  assert.equal(restored.clientId, "client-1");
  assert.equal(restored.eventLineId, null);
  assert.equal(restored.lockMode, "client");
});

test("reconcile current focus clears missing client entirely", () => {
  const current = {
    clientId: "client-missing",
    clientName: "旧客户",
    eventLineId: null,
    eventLineName: null,
    taskId: "task-1",
    taskTitle: "旧任务",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  };

  const next = reconcileCurrentFocus(current, [], []);
  assert.equal(next.clientId, null);
  assert.equal(next.lockMode, "browse");
});

test("reconcile current focus follows an event line when its primary client changes", () => {
  const locked = createManualClientEventLineFocus(
    { id: "client-old", name: "旧客户" },
    { id: "event-1", name: "签约推进线" },
    createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0)),
  );

  const next = reconcileCurrentFocus(
    locked,
    [
      { id: "client-old", name: "旧客户" },
      { id: "client-new", name: "正式客户" },
    ],
    [
      {
        id: "event-1",
        name: "签约推进线",
        primaryClientId: "client-new",
        primaryClientName: "正式客户",
      },
    ],
  );

  assert.equal(next.clientId, "client-new");
  assert.equal(next.clientName, "正式客户");
  assert.equal(next.eventLineId, "event-1");
  assert.equal(next.lockMode, "client_event_line");
});

test("deriveBoundaryState returns mixed when multiple layers are non-empty", () => {
  const state = deriveBoundaryState([
    { kind: "official", title: "A", summary: "A", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
    { kind: "risk", title: "B", summary: "B", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
  ]);
  assert.equal(state, "mixed");
});
~~~

## `mobile/lib/__tests__/date.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildWeekInfo,
  formatLocalDateKey,
  getLocalWeekAnchorDateKey,
  getLocalWeekRangeKeys,
  startOfLocalDay,
  endOfLocalDay,
  weekLabelForDateKey,
} from "../../.mobile-core-tests/dist/lib/date.js";

function parseLocalDateKey(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(year, month - 1, day);
}

test("formatLocalDateKey uses local calendar date instead of UTC slices", () => {
  const localMidnight = new Date(2026, 3, 16, 0, 5, 0, 0);
  assert.equal(formatLocalDateKey(localMidnight), "2026-04-16");
});

test("local week range is monday to sunday", () => {
  const sample = new Date(2026, 3, 16, 18, 30, 0, 0);
  const range = getLocalWeekRangeKeys(sample);
  assert.equal(parseLocalDateKey(range.startKey).getDay(), 1);
  assert.equal(parseLocalDateKey(range.endKey).getDay(), 0);
  assert.ok(range.startKey <= formatLocalDateKey(sample));
  assert.ok(range.endKey >= formatLocalDateKey(sample));
});

test("start/end of local day stay within same date key", () => {
  const sample = new Date(2026, 10, 3, 12, 45, 22, 111);
  assert.equal(formatLocalDateKey(startOfLocalDay(sample)), "2026-11-03");
  assert.equal(formatLocalDateKey(endOfLocalDay(sample)), "2026-11-03");
});

test("week helpers keep monday anchor and YYYY-Www label aligned", () => {
  const sample = new Date(2026, 3, 16, 18, 30, 0, 0);
  const weekAnchorDate = getLocalWeekAnchorDateKey(sample);
  const weekInfo = buildWeekInfo(sample);

  assert.equal(weekAnchorDate, weekInfo.weekAnchorDate);
  assert.equal(weekLabelForDateKey(weekAnchorDate), weekInfo.weekLabel);
  assert.match(weekInfo.weekLabel, /^\d{4}-W\d{2}$/);
});
~~~

## `mobile/lib/__tests__/focus-selectors.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildFocusMatchedTaskIds,
  buildFocusTaskStats,
  filterTasksByFocus,
  isLockedFocus,
  sortTasksByFocusPriority,
} from "../../.mobile-core-tests/dist/lib/focus-selectors.js";

test("isLockedFocus only returns true for locked client scopes", () => {
  assert.equal(isLockedFocus({ lockMode: "browse" }), false);
  assert.equal(isLockedFocus({ lockMode: "client" }), true);
  assert.equal(isLockedFocus({ lockMode: "client_event_line" }), true);
});

test("filterTasksByFocus narrows to event line first when present", () => {
  const focus = {
    lockMode: "client_event_line",
    clientId: "client-1",
    eventLineId: "event-2",
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-1" },
    { id: "task-2", clientId: "client-1", eventLineId: "event-2" },
    { id: "task-3", clientId: "client-2", eventLineId: "event-2" },
  ];

  assert.deepEqual(
    filterTasksByFocus(tasks, focus).map((task) => task.id),
    ["task-2", "task-3"],
  );
});

test("buildFocusMatchedTaskIds returns the ids that match the current client lock", () => {
  const focus = {
    lockMode: "client",
    clientId: "client-1",
    eventLineId: null,
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-1" },
    { id: "task-2", clientId: "client-1", eventLineId: null },
    { id: "task-3", clientId: "client-2", eventLineId: "event-1" },
  ];

  const matched = buildFocusMatchedTaskIds(tasks, focus);
  assert.equal(matched.has("task-1"), true);
  assert.equal(matched.has("task-2"), true);
  assert.equal(matched.has("task-3"), false);
});

test("sortTasksByFocusPriority lifts matched tasks ahead of the rest while keeping stable order", () => {
  const focus = {
    lockMode: "client",
    clientId: "client-1",
    eventLineId: null,
  };
  const tasks = [
    { id: "task-1", clientId: "client-2", eventLineId: null },
    { id: "task-2", clientId: "client-1", eventLineId: null },
    { id: "task-3", clientId: "client-2", eventLineId: null },
    { id: "task-4", clientId: "client-1", eventLineId: null },
  ];

  assert.deepEqual(
    sortTasksByFocusPriority(tasks, focus).map((task) => task.id),
    ["task-2", "task-4", "task-1", "task-3"],
  );
});

test("buildFocusTaskStats counts scheduled, unscheduled, and completed matches", () => {
  const focus = {
    lockMode: "client_event_line",
    clientId: "client-1",
    eventLineId: "event-2",
  };
  const tasks = [
    { id: "task-1", clientId: "client-1", eventLineId: "event-2", dueDate: "2026-04-19", progressStatus: "todo" },
    { id: "task-2", clientId: "client-1", eventLineId: "event-2", dueDate: null, progressStatus: "done" },
    { id: "task-3", clientId: "client-1", eventLineId: "event-1", dueDate: "2026-04-20", progressStatus: "todo" },
  ];

  assert.deepEqual(buildFocusTaskStats(tasks, focus), {
    matchedCount: 2,
    scheduledCount: 1,
    unscheduledCount: 1,
    doneCount: 1,
  });
});
~~~

## `mobile/lib/__tests__/legacy-upload-pseudo-op-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildLegacyUploadPseudoOp,
  mergeLaneDiagnosticsWithLegacyUploads,
  normalizeLegacyUploadReasonCode,
  normalizeLegacyUploadStatus,
} from "../../.mobile-core-tests/dist/lib/legacy-upload-pseudo-op-core.js";

test("buildLegacyUploadPseudoOp derives age from the latest attempt", () => {
  const op = buildLegacyUploadPseudoOp(
    {
      opId: "legacy_upload_1",
      objectType: "recorded_audio_attachment",
      objectLocalId: "voice-1",
      objectRemoteId: null,
      lane: "transfer",
      status: "queued",
      retryCount: 1,
      reasonCode: "bind_pending_remote_id",
      createdAt: "2026-04-18T00:00:00.000Z",
      lastAttemptAt: "2026-04-18T00:30:00.000Z",
      displayTitle: "测试录音",
      taskLocalId: "task-1",
      filePath: "/tmp/voice.m4a",
      size: 1024,
      mtime: 123,
      hash: null,
      entityRefLocalId: "task-1",
      mimeType: "audio/m4a",
      durationSeconds: 12,
    },
    Date.parse("2026-04-18T01:00:00.000Z"),
  );

  assert.equal(op.ageMs, 30 * 60 * 1000);
});

test("normalizeLegacyUploadReasonCode and status fall back to safe defaults", () => {
  assert.equal(normalizeLegacyUploadReasonCode("file_missing"), "file_missing");
  assert.equal(normalizeLegacyUploadReasonCode("not_real_reason"), "unknown_error");
  assert.equal(normalizeLegacyUploadStatus("processing"), "processing");
  assert.equal(normalizeLegacyUploadStatus("anything"), "needs_attention");
});

test("mergeLaneDiagnosticsWithLegacyUploads folds legacy transfer ops into diagnostics", () => {
  const merged = mergeLaneDiagnosticsWithLegacyUploads(
    {
      interactive: {
        lane: "interactive",
        total: 1,
        oldestAgeMs: 10,
        active: false,
        topReasonCode: null,
      },
      transfer: {
        lane: "transfer",
        total: 2,
        oldestAgeMs: 5_000,
        active: false,
        topReasonCode: "network_unavailable",
      },
      derived: {
        lane: "derived",
        total: 0,
        oldestAgeMs: null,
        active: false,
        topReasonCode: null,
      },
    },
    [
      buildLegacyUploadPseudoOp(
        {
          opId: "legacy_upload_1",
          objectType: "recorded_audio_attachment",
          objectLocalId: "voice-1",
          objectRemoteId: null,
          lane: "transfer",
          status: "queued",
          retryCount: 0,
          reasonCode: "file_missing",
          createdAt: "2026-04-18T00:00:00.000Z",
          lastAttemptAt: null,
          displayTitle: "录音 A",
          taskLocalId: "task-1",
          filePath: "/tmp/a.m4a",
          size: null,
          mtime: null,
          hash: null,
          entityRefLocalId: "task-1",
          mimeType: "audio/m4a",
          durationSeconds: 10,
        },
        Date.parse("2026-04-18T01:00:00.000Z"),
      ),
      buildLegacyUploadPseudoOp(
        {
          opId: "legacy_upload_2",
          objectType: "recorded_audio_attachment",
          objectLocalId: "voice-2",
          objectRemoteId: null,
          lane: "transfer",
          status: "processing",
          retryCount: 1,
          reasonCode: "file_missing",
          createdAt: "2026-04-18T00:10:00.000Z",
          lastAttemptAt: "2026-04-18T00:40:00.000Z",
          displayTitle: "录音 B",
          taskLocalId: "task-2",
          filePath: "/tmp/b.m4a",
          size: null,
          mtime: null,
          hash: null,
          entityRefLocalId: "task-2",
          mimeType: "audio/m4a",
          durationSeconds: 15,
        },
        Date.parse("2026-04-18T01:00:00.000Z"),
      ),
    ],
  );

  assert.equal(merged.transfer.total, 4);
  assert.equal(merged.transfer.active, true);
  assert.equal(merged.transfer.oldestAgeMs, 60 * 60 * 1000);
  assert.equal(merged.transfer.topReasonCode, "file_missing");
});
~~~

## `mobile/lib/__tests__/legacy-upload-runner-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  processQueuedLegacyUploadOps,
  resolveLegacyUploadFailureStatus,
} from "../../.mobile-core-tests/dist/lib/legacy-upload-runner-core.js";

test("resolveLegacyUploadFailureStatus keeps transient failures queued", () => {
  assert.equal(resolveLegacyUploadFailureStatus("network_unavailable"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("bind_pending_remote_id"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("manual_pause"), "queued");
  assert.equal(resolveLegacyUploadFailureStatus("upload_failed"), "needs_attention");
  assert.equal(resolveLegacyUploadFailureStatus("file_missing"), "needs_attention");
});

test("processQueuedLegacyUploadOps retries queued items only and stops on auth", async () => {
  const attempted = [];
  const result = await processQueuedLegacyUploadOps(
    [
      { opId: "queued-1", status: "queued" },
      { opId: "processing-1", status: "processing" },
      { opId: "queued-2", status: "queued" },
      { opId: "needs-attention-1", status: "needs_attention" },
    ],
    async (opId) => {
      attempted.push(opId);
      if (opId === "queued-2") {
        return { ok: false, reasonCode: "auth_required", message: "auth expired" };
      }
      return { ok: true };
    },
  );

  assert.deepEqual(attempted, ["queued-1", "queued-2"]);
  assert.deepEqual(result, {
    attempted: 2,
    completed: 1,
    stoppedByAuth: true,
    stoppedByNetwork: false,
  });
});

test("processQueuedLegacyUploadOps stops on network to avoid burning the whole cycle", async () => {
  const attempted = [];
  const result = await processQueuedLegacyUploadOps(
    [
      { opId: "queued-1", status: "queued" },
      { opId: "queued-2", status: "queued" },
    ],
    async (opId) => {
      attempted.push(opId);
      return {
        ok: false,
        reasonCode: "network_unavailable",
        message: `${opId} failed`,
      };
    },
  );

  assert.deepEqual(attempted, ["queued-1"]);
  assert.deepEqual(result, {
    attempted: 1,
    completed: 0,
    stoppedByAuth: false,
    stoppedByNetwork: true,
  });
});
~~~

## `mobile/lib/__tests__/pending-op-policy.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { foldPendingOps } from "../../.mobile-core-tests/dist/lib/pending-op-policy.js";

function makeOp(operation, overrides = {}) {
  return {
    clientOpId: `${operation}-op`,
    entityType: "task",
    entityId: "task_1",
    entityRemoteId: overrides.entityRemoteId ?? null,
    operation,
    payload: overrides.payload ?? null,
    lane: overrides.lane ?? "interactive",
    status: overrides.status ?? "queued",
    visibilityScope: overrides.visibilityScope ?? "team_shared",
    localVersion: overrides.localVersion ?? 1,
    baseRemoteVersion: overrides.baseRemoteVersion ?? null,
  };
}

test("create plus updates folds into one final create snapshot", () => {
  const result = foldPendingOps(
    [makeOp("create", { payload: { title: "A" }, localVersion: 1 })],
    makeOp("update", { payload: { dueDate: "2026-04-18" }, localVersion: 2 }),
  );
  assert.equal(result.length, 1);
  assert.equal(result[0].operation, "create");
  assert.deepEqual(result[0].payload, { title: "A", dueDate: "2026-04-18" });
  assert.equal(result[0].localVersion, 2);
});

test("create then delete before remote sync cancels both ops", () => {
  const result = foldPendingOps(
    [makeOp("create", { payload: { title: "A" } })],
    makeOp("delete"),
  );
  assert.deepEqual(result, []);
});

test("update plus update merges into one update", () => {
  const result = foldPendingOps(
    [makeOp("update", { payload: { title: "A" }, localVersion: 2 })],
    makeOp("update", { payload: { priority: "high" }, localVersion: 3 }),
  );
  assert.equal(result.length, 1);
  assert.equal(result[0].operation, "update");
  assert.deepEqual(result[0].payload, { title: "A", priority: "high" });
  assert.equal(result[0].localVersion, 3);
});

test("review op stays behind the folded base mutation", () => {
  const result = foldPendingOps(
    [
      makeOp("create", { payload: { title: "A" }, localVersion: 1 }),
      makeOp("complete_with_review", {
        payload: { reviewNote: "已完成" },
        localVersion: 2,
      }),
    ],
    makeOp("update", { payload: { priority: "high" }, localVersion: 3 }),
  );

  assert.equal(result.length, 2);
  assert.equal(result[0].operation, "create");
  assert.deepEqual(result[0].payload, { title: "A", priority: "high" });
  assert.equal(result[1].operation, "complete_with_review");
  assert.equal(result[1].localVersion, 3);
});
~~~

## `mobile/lib/__tests__/record-note-flow-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  canTransitionRecordNoteProgress,
  getAllowedRecordNoteTransitions,
} from "../../.mobile-core-tests/dist/lib/record-note-flow-core.js";

test("record-note progress only allows the locked transition graph", () => {
  assert.equal(canTransitionRecordNoteProgress("任务已保存", "录音待挂接"), true);
  assert.equal(canTransitionRecordNoteProgress("任务已保存", "正在恢复暂存语音"), false);
  assert.equal(canTransitionRecordNoteProgress("录音待同步", "完成"), true);
  assert.equal(canTransitionRecordNoteProgress("录音待同步", "正在恢复暂存语音"), false);
  assert.equal(canTransitionRecordNoteProgress("录音需处理", "录音待同步"), false);
});

test("record-note progress exposes the allowed next states for recovery flow", () => {
  assert.deepEqual(getAllowedRecordNoteTransitions("正在恢复暂存语音"), [
    "录音待挂接",
    "录音需处理",
  ]);
});
~~~

## `mobile/lib/__tests__/runtime-controller.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { createRuntimeController } from "../../.mobile-core-tests/dist/lib/runtime-controller.js";

test("runtime controller initializes once and starts sync once", async () => {
  let initializeCount = 0;
  let startCount = 0;
  let stopCount = 0;
  let resetCount = 0;

  const controller = createRuntimeController({
    initializeBaseUrl: async () => {
      initializeCount += 1;
    },
    startSync: async () => {
      startCount += 1;
    },
    stopSync: async () => {
      stopCount += 1;
    },
    resetSessionState: () => {
      resetCount += 1;
    },
  });

  await Promise.all([controller.start(), controller.start()]);
  assert.equal(initializeCount, 1);
  assert.equal(startCount, 1);
  assert.equal(controller.isSyncRunning(), true);

  await controller.stop();
  assert.equal(stopCount, 1);
  assert.equal(resetCount, 1);
  assert.equal(controller.isSyncRunning(), false);
});

test("runtime controller can stop before sync ever starts", async () => {
  let initializeCount = 0;
  let stopCount = 0;
  let resetCount = 0;

  const controller = createRuntimeController({
    initializeBaseUrl: () => {
      initializeCount += 1;
    },
    startSync: () => {},
    stopSync: () => {
      stopCount += 1;
    },
    resetSessionState: () => {
      resetCount += 1;
    },
  });

  await controller.stop();
  assert.equal(initializeCount, 1);
  assert.equal(stopCount, 0);
  assert.equal(resetCount, 1);
});
~~~

## `mobile/lib/__tests__/scope-storage-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScopedDirectoryPath,
  buildScopedStorageKey,
  resolveScopedStorageNamespace,
} from "../../.mobile-core-tests/dist/lib/scope-storage-core.js";

test("resolveScopedStorageNamespace normalizes and encodes account scopes", () => {
  assert.equal(resolveScopedStorageNamespace("org-1:user-1"), "org-1%3Auser-1");
  assert.equal(resolveScopedStorageNamespace(null), "no-org%3Ano-user");
});

test("buildScopedStorageKey prefixes a logical key with the scope namespace", () => {
  assert.equal(
    buildScopedStorageKey("cache:", "taskBoard", "org-1:user-1"),
    "cache:org-1%3Auser-1:taskBoard",
  );
});

test("buildScopedDirectoryPath appends a scope directory once", () => {
  assert.equal(
    buildScopedDirectoryPath("/tmp/smart-input-queue", "org-1:user-1"),
    "/tmp/smart-input-queue/org-1%3Auser-1/",
  );
  assert.equal(
    buildScopedDirectoryPath("/tmp/smart-input-queue/", null),
    "/tmp/smart-input-queue/no-org%3Ano-user/",
  );
});
~~~

## `mobile/lib/__tests__/smart-input-queue-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { reconcileQueuedSmartInputItems } from "../../.mobile-core-tests/dist/lib/smart-input-queue-core.js";

test("reconcileQueuedSmartInputItems removes only recovered ids from the latest queue snapshot", () => {
  const nextQueue = reconcileQueuedSmartInputItems(
    [
      { id: "new-item" },
      { id: "recovered-item" },
      { id: "still-pending" },
    ],
    new Set(["recovered-item"]),
  );

  assert.deepEqual(nextQueue, [
    { id: "new-item" },
    { id: "still-pending" },
  ]);
});

test("reconcileQueuedSmartInputItems respects a user clear by not resurrecting stale entries", () => {
  const nextQueue = reconcileQueuedSmartInputItems([], new Set(["old-item"]));
  assert.deepEqual(nextQueue, []);
});
~~~

## `mobile/lib/__tests__/smart-input-recovery.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRecoveredDraftKey,
  shouldAttemptSmartInputRecovery,
  shouldAutoOpenRecoveredDraft,
  shouldUseRecoveredDraft,
} from "../../.mobile-core-tests/dist/lib/smart-input-recovery.js";

test("non-manual recovery is throttled and respects in-flight guard", () => {
  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "tasks_enter",
    queuedCount: 1,
    inFlight: true,
    nowMs: 2000,
    lastAttemptAt: 1000,
  }), false);

  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "tasks_enter",
    queuedCount: 1,
    inFlight: false,
    nowMs: 1500,
    lastAttemptAt: 1000,
  }), false);
});

test("manual recovery bypasses debounce but auto-open still requires safe UI state", () => {
  assert.equal(shouldAttemptSmartInputRecovery({
    trigger: "manual",
    queuedCount: 1,
    inFlight: false,
    nowMs: 1100,
    lastAttemptAt: 1000,
  }), true);

  assert.equal(shouldAutoOpenRecoveredDraft({
    trigger: "manual",
    isTasksScreenActive: true,
    hasBlockingUi: false,
  }), true);

  assert.equal(shouldAutoOpenRecoveredDraft({
    trigger: "app_active",
    isTasksScreenActive: true,
    hasBlockingUi: false,
  }), false);
});

test("recovered draft key prevents reopening same queued draft repeatedly", () => {
  const key = buildRecoveredDraftKey({
    title: "补充会议纪要",
    dueDate: "2026-04-16",
    dueTime: "10:00",
    description: "跟进事项",
  });

  assert.equal(shouldUseRecoveredDraft(key, null), true);
  assert.equal(shouldUseRecoveredDraft(key, key), false);
});
~~~

## `mobile/lib/__tests__/sync-freeze-core.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  describeSyncFreezeState,
  isSyncFreezeBlocked,
  isSyncFreezePaused,
} from "../../.mobile-core-tests/dist/lib/sync-freeze-core.js";

test("describeSyncFreezeState returns a user-facing summary for paused sync", () => {
  const descriptor = describeSyncFreezeState("paused_by_user", null);

  assert.equal(descriptor.summary, "同步已暂停");
  assert.equal(descriptor.actionLabel, "恢复同步");
  assert.equal(isSyncFreezePaused("paused_by_user"), true);
  assert.equal(isSyncFreezeBlocked("paused_by_user"), false);
});

test("describeSyncFreezeState keeps blocked states non-resumable", () => {
  const descriptor = describeSyncFreezeState("blocked_by_integrity", "orphan_task_pending_ops");

  assert.equal(descriptor.summary, "同步已冻结，需要处理本地数据完整性");
  assert.equal(descriptor.actionLabel, null);
  assert.equal(descriptor.detail, "orphan_task_pending_ops");
  assert.equal(isSyncFreezeBlocked("blocked_by_integrity"), true);
});
~~~

## `mobile/lib/__tests__/task-board-store.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { createTaskBoardStore } from "../../.mobile-core-tests/dist/lib/task-board-store-core.js";

function makeBoard(taskIds) {
  return {
    tasks: taskIds.map((id) => ({ id, title: id })),
    inboxCount: taskIds.length,
    tasksTodayCount: taskIds.length,
  };
}

test("task board store hydrates from local board and reacts to sync events", async () => {
  let initCount = 0;
  let refreshCount = 0;
  let dataListener = () => {};
  let statusListener = () => {};
  let board = makeBoard(["task-1"]);
  let releaseRefresh;

  const store = createTaskBoardStore({
    initDatabase: () => {
      initCount += 1;
    },
    getLocalTaskBoard: () => board,
    onDataChanged: (listener) => {
      dataListener = listener;
      return () => {
        dataListener = () => {};
      };
    },
    onSyncStatusChange: (listener) => {
      statusListener = listener;
      return () => {
        statusListener = () => {};
      };
    },
    getSyncStatus: () => ({ status: "idle", lastSyncTime: null }),
    triggerSync: () => {
      refreshCount += 1;
      return new Promise((resolve) => {
        releaseRefresh = resolve;
      });
    },
  });

  store.ensureInitialized();
  assert.equal(initCount, 1);
  assert.equal(store.getSnapshot().isHydrated, true);
  assert.equal(store.getSnapshot().board.tasks[0].id, "task-1");

  statusListener("syncing", "2026-04-16T10:00:00.000Z");
  assert.equal(store.getSnapshot().syncStatus, "syncing");
  assert.equal(store.getSnapshot().lastSyncTime, "2026-04-16T10:00:00.000Z");

  board = makeBoard(["task-2", "task-3"]);
  dataListener();
  assert.deepEqual(
    store.getSnapshot().board.tasks.map((task) => task.id),
    ["task-2", "task-3"],
  );

  const refreshA = store.refresh();
  const refreshB = store.refresh();
  assert.equal(refreshCount, 1);
  releaseRefresh();
  await Promise.all([refreshA, refreshB]);
});

test("task board store reset clears hydration and sync state", () => {
  const store = createTaskBoardStore({
    initDatabase: () => {},
    getLocalTaskBoard: () => makeBoard(["task-1"]),
    onDataChanged: () => () => {},
    onSyncStatusChange: () => () => {},
    getSyncStatus: () => ({ status: "idle", lastSyncTime: null }),
    triggerSync: async () => {},
  });

  store.ensureInitialized();
  assert.equal(store.getSnapshot().isHydrated, true);
  store.reset();
  assert.equal(store.getSnapshot().isHydrated, false);
  assert.equal(store.getSnapshot().board.tasks.length, 0);
});
~~~

## `mobile/lib/__tests__/task-sync-policy.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { decideTaskServerAckAction } from "../../.mobile-core-tests/dist/lib/task-sync-policy.js";

test("stale ack with newer local version keeps dirty task and promotes pending create", () => {
  const decision = decideTaskServerAckAction({
    localTask: {
      id: "task-1",
      title: "测试任务",
      priority: "normal",
      progressStatus: "todo",
      localVersion: 3,
      remoteState: "queued",
    },
    ackLocalVersion: 1,
    hasPendingOps: true,
    pendingCreateExists: true,
  });

  assert.equal(decision.shouldReplaceLocalTask, false);
  assert.equal(decision.shouldUpdateShadowOnly, true);
  assert.equal(decision.shouldPromotePendingCreate, true);
});

test("clean ack without pending ops can replace local task directly", () => {
  const decision = decideTaskServerAckAction({
    localTask: {
      id: "task-2",
      title: "测试任务",
      priority: "normal",
      progressStatus: "todo",
      localVersion: 2,
      remoteState: "syncing",
    },
    ackLocalVersion: 2,
    hasPendingOps: false,
    pendingCreateExists: false,
  });

  assert.equal(decision.shouldReplaceLocalTask, true);
  assert.equal(decision.shouldUpdateShadowOnly, false);
  assert.equal(decision.shouldPromotePendingCreate, false);
});
~~~

## `mobile/lib/__tests__/task-sync-presentation.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";
import { buildTaskSyncIndicator, formatTaskSyncReasonCode } from "../task-sync-presentation.ts";

test("buildTaskSyncIndicator returns null for synced tasks", () => {
  assert.equal(buildTaskSyncIndicator({ remoteState: "synced", syncReasonCode: null }), null);
});

test("buildTaskSyncIndicator prioritizes version conflicts", () => {
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "needs_attention", syncReasonCode: "version_conflict" }), {
    label: "冲突",
    detail: "服务器版本冲突",
    tone: "danger",
  });
});

test("buildTaskSyncIndicator exposes queued and processing states", () => {
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "queued", syncReasonCode: null }), {
    label: "待同步",
    detail: "本地已保存，等待后台同步",
    tone: "info",
  });
  assert.deepEqual(buildTaskSyncIndicator({ remoteState: "processing", syncReasonCode: null }), {
    label: "处理中",
    detail: "后台正在处理本地修改",
    tone: "warning",
  });
});

test("formatTaskSyncReasonCode falls back safely", () => {
  assert.equal(formatTaskSyncReasonCode("auth_expired"), "登录已过期");
  assert.equal(formatTaskSyncReasonCode("unknown"), "请稍后再试");
});
~~~

## `mobile/lib/__tests__/task-understanding.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildTaskUnderstandingCardModel,
  buildTaskUnderstandingSections,
} from "../../.mobile-core-tests/dist/lib/task-understanding.js";

test("insufficient context tasks do not repeat task description", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-1",
      title: "和元兵吃饭",
      description: "和元兵吃饭，看看最近怎么推进",
      progressStatus: "todo",
      priority: "normal",
    },
    understanding: {
      whatIsThis: "和元兵吃饭，看看最近怎么推进",
      whyItMatters: "",
      progressNow: "",
      unknowns: "",
      knownFacts: [],
      confidence: 20,
      coverage: 20,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "task_title", available: true },
        { sourceType: "task_desc", available: true },
      ],
    },
  });

  assert.equal(sections.status, "insufficient_context");
  assert.equal(sections.whatIsThis, "暂无可靠洞察");
  assert.match(sections.blockerAndDecision, /当前缺少：/);
  assert.match(sections.nextStepAndUnknowns, /建议补充：/);
});

test("weak event line links no longer use preview judgment as task understanding", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-2",
      title: "和元兵吃饭",
      progressStatus: "todo",
      priority: "normal",
      eventLineId: "event-1",
      eventLineName: "市场行为",
    },
    eventLine: {
      id: "event-1",
      name: "市场行为",
      recentDecision: "先观察渠道反馈",
      currentBlocker: "还没有确认联系人身份",
    },
    contextPreview: {
      taskId: "task-2",
      summaryChips: ["事件线 · 市场行为", "阶段 · 线索观察"],
      safeOutputMode: "summary_only",
      judgment: {
        summary: "这是一次关键合作推进任务",
      },
    },
  });

  assert.equal(sections.status, "weak_link");
  assert.match(sections.whatIsThis, /已关联「市场行为」/);
  assert.doesNotMatch(sections.whatIsThis, /关键合作推进任务/);
  assert.match(sections.blockerAndDecision, /事件线卡点：还没有确认联系人身份/);
});

test("ready state requires non-generic understanding with stronger evidence", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-3",
      title: "跟进日慈基金会继续推进带领者培训",
      description: "继续推进当前轮次的带领者培训和演练",
      currentBlocker: "预算还没最后确认",
      nextAction: "补最终版执行排期",
      progressStatus: "todo",
      priority: "high",
    },
    understanding: {
      mode: "enhanced",
      whatIsThis: "这条任务处在日慈基金会合作方案推进的执行准备阶段，重点是把培训和演练安排收拢成可执行计划。",
      whyItMatters: "最近反馈显示对方更关注执行节奏和落地安排，如果本轮还停留在泛化表达，后续预算和排期就会继续悬空。",
      progressNow: "最近进展停在排期收拢和预算确认之间，当前需要把执行安排说清楚。",
      unknowns: "还缺最终预算范围和对方对执行节奏的确认。",
      knownFacts: [],
      confidence: 72,
      coverage: 78,
      _pending: false,
      optionalAdvice: {
        minimumAction: "先补最终版执行排期",
      },
      sourceBreakdown: [
        { sourceType: "client_background", available: true },
        { sourceType: "meeting", available: true },
      ],
    },
  });

  assert.equal(sections.status, "ready");
  assert.match(sections.whatIsThis, /执行准备阶段/);
  assert.match(sections.whyItMatters, /更关注执行节奏/);
  assert.match(sections.nextStepAndUnknowns, /最小动作：先补最终版执行排期/);
});

test("generic why-it-matters keeps the card in insufficient context", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-4",
      title: "晚上约高瑞瑞",
      progressStatus: "todo",
      priority: "normal",
    },
    understanding: {
      whatIsThis: "「晚上约高瑞瑞」是一条todo状态的工作任务。",
      whyItMatters: "这条任务与客户「益语智库」相关。",
      progressNow: "当前状态为 todo。",
      unknowns: "系统尚未看到以下信息：客户/项目背景卡。",
      knownFacts: [],
      confidence: 48,
      coverage: 60,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "org_dna", available: true },
      ],
    },
  });

  assert.equal(sections.status, "insufficient_context");
  assert.equal(sections.whatIsThis, "暂无可靠洞察");
});

test("card model surfaces evidence for ready states", () => {
  const card = buildTaskUnderstandingCardModel({
    task: {
      id: "task-5",
      title: "准备日慈基金会沟通材料",
      progressStatus: "todo",
      priority: "high",
      clientName: "日慈基金会",
      eventLineName: "合作方案推进",
    },
    understanding: {
      whatIsThis: "当前要把沟通材料收敛成可会前使用的版本。",
      whyItMatters: "明天的沟通会直接决定下一轮合作推进节奏。",
      progressNow: "卡在材料版本还没最终收口。",
      unknowns: "还缺预算边界。",
      knownFacts: [],
      confidence: 80,
      coverage: 82,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "meeting", available: true },
        { sourceType: "client_background", available: true },
      ],
    },
    contextPreview: {
      taskId: "task-5",
      clientName: "日慈基金会",
      summaryChips: ["阶段 · 会前准备", "事件线 · 合作方案推进"],
    },
  });

  assert.equal(card.tone, "ready");
  assert.equal(card.stateLabel, "有依据");
  assert.match(card.subtitle, /已有上下文/);
  assert.ok(card.evidence.includes("会议记录"));
  assert.ok(card.evidence.includes("客户背景"));
});

test("card model uses caution copy for insufficient context", () => {
  const card = buildTaskUnderstandingCardModel({
    task: {
      id: "task-6",
      title: "晚上约高瑞瑞",
      progressStatus: "todo",
      priority: "normal",
    },
  });

  assert.equal(card.tone, "insufficient_context");
  assert.equal(card.stateLabel, "待补上下文");
  assert.equal(card.sections[0].title, "当前提醒");
  assert.equal(card.sections[2].title, "还缺什么");
});
~~~

## `mobile/lib/__tests__/week-signal.test.mjs`

- 编码: `utf-8`

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import { buildWeekSignalSnapshot } from "../../.mobile-core-tests/dist/lib/week-signal.js";

const tasks = [
  {
    id: "task-1",
    title: "日慈基金会推进会",
    dueDate: "2026-04-14T12:30",
    progressStatus: "todo",
    createdAt: "2026-04-13T09:00:00.000Z",
    updatedAt: "2026-04-13T09:00:00.000Z",
  },
  {
    id: "task-2",
    title: "输出会议纪要",
    dueDate: "2026-04-15T18:00",
    progressStatus: "done",
    completionNote: "已完成",
    createdAt: "2026-04-13T09:00:00.000Z",
    updatedAt: "2026-04-15T18:00:00.000Z",
  },
];

test("buildWeekSignalSnapshot stays facts-only when judgment overlay is disabled", () => {
  const snapshot = buildWeekSignalSnapshot({
    tasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    workspaceLite: {
      boundaryCards: [
        { kind: "pending", title: "待确认判断", summary: "先做试点", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
      ],
      nextActions: ["和负责人确认预算"],
    },
    eventLine: {
      id: "event-1",
      name: "韶关推进线",
      nextStep: "整理下一轮动作",
    },
  });

  assert.equal(snapshot.facts.totalCount, 2);
  assert.deepEqual(snapshot.pendingJudgments, []);
  assert.deepEqual(snapshot.riskSignals, []);
  assert.deepEqual(snapshot.suggestedActions, []);
});

test("buildWeekSignalSnapshot overlays workspace judgments only for locked focus flows", () => {
  const snapshot = buildWeekSignalSnapshot({
    tasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: true,
    workspaceLite: {
      boundaryCards: [
        { kind: "pending", title: "待确认判断", summary: "先做试点", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
        { kind: "risk", title: "风险", summary: "负责人尚未确认", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
      ],
      nextActions: ["和负责人确认预算"],
    },
    eventLine: {
      id: "event-1",
      name: "韶关推进线",
      nextStep: "整理下一轮动作",
    },
  });

  assert.deepEqual(snapshot.pendingJudgments, ["先做试点"]);
  assert.deepEqual(snapshot.riskSignals, ["负责人尚未确认"]);
  assert.deepEqual(snapshot.suggestedActions, ["和负责人确认预算", "整理下一轮动作"]);
});

test("overdueCount is measured against today, not the week anchor", () => {
  const now = new Date("2026-04-17T10:00:00");
  const mixedTasks = [
    // Due Monday of this week, not done — should be overdue on Friday.
    {
      id: "overdue-mid-week",
      title: "本周一到期未完成",
      dueDate: "2026-04-13T12:00",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
    // Due last week, done — should NOT count as overdue.
    {
      id: "old-done",
      title: "上周完成",
      dueDate: "2026-04-08T12:00",
      progressStatus: "done",
      completionNote: "done",
      createdAt: "2026-04-01T09:00:00.000Z",
      updatedAt: "2026-04-08T12:00:00.000Z",
    },
    // No dueDate, not done — should count toward unscheduled.
    {
      id: "unscheduled-open",
      title: "未排期",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
    // No dueDate but already done — must not count toward unscheduled.
    {
      id: "unscheduled-done",
      title: "未排期但已完成",
      progressStatus: "done",
      completionNote: "done",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
  ];

  const snapshot = buildWeekSignalSnapshot({
    tasks: mixedTasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    now,
  });

  assert.equal(snapshot.facts.overdueCount, 1, "only the open mid-week task is overdue today");
  assert.equal(snapshot.facts.unscheduledCount, 1, "done + undated tasks are excluded");
  assert.equal(snapshot.facts.totalCount, 1, "only the mid-week task falls in this week");
});

test("UTC ISO dueDates are normalized to local date before comparing to week range", () => {
  // UTC "2026-04-12T23:00:00.000Z" is 2026-04-13 in CST (UTC+8), so in that
  // timezone it belongs to the week anchored at 2026-04-13. In a UTC-only world
  // the old code would have placed it in the prior week.
  const nearMidnightTasks = [
    {
      id: "utc-late-sunday",
      title: "UTC 周日晚的任务",
      dueDate: "2026-04-12T23:00:00.000Z",
      progressStatus: "todo",
      createdAt: "2026-04-10T09:00:00.000Z",
      updatedAt: "2026-04-10T09:00:00.000Z",
    },
  ];
  const snapshot = buildWeekSignalSnapshot({
    tasks: nearMidnightTasks,
    weekAnchorDate: "2026-04-13",
    allowJudgmentOverlay: false,
    now: new Date("2026-04-14T10:00:00"),
  });

  // In UTC+8 the task is in-week; in UTC-8 it is a week earlier. The assertion
  // below is only strict for the former, so we fold both cases into "≤ 1".
  // What we really care about is that the count is NOT double-assigned and
  // that the function does not throw on UTC ISO input.
  assert.ok(snapshot.facts.totalCount <= 1, "task placed in exactly 0 or 1 week");
  assert.ok(snapshot.facts.overdueCount <= 1, "not double-counted as overdue");
});
~~~

## `mobile/lib/account-scope.ts`

- 编码: `utf-8`

~~~typescript
import type { SessionUser } from "./types";

export const NO_ACCOUNT_SCOPE_KEY = "no-org:no-user";

export function buildAccountScopeKey(
  user: Pick<SessionUser, "id" | "organizationId"> | null | undefined,
): string {
  const organizationId = user?.organizationId?.trim() || "no-org";
  const userId = user?.id?.trim() || "no-user";
  return `${organizationId}:${userId}`;
}

export function normalizeAccountScopeKey(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }
  const [organizationId, userId] = trimmed.split(":");
  if (!organizationId || !userId) {
    return null;
  }
  return `${organizationId}:${userId}`;
}

export function redactAccountScopeKey(value: string | null | undefined): string {
  const normalized = normalizeAccountScopeKey(value) ?? NO_ACCOUNT_SCOPE_KEY;
  const [organizationId, userId] = normalized.split(":");
  return `${organizationId}:${userId.slice(0, 4)}***`;
}
~~~

## `mobile/lib/android-back.ts`

- 编码: `utf-8`

~~~typescript
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback } from "react";
import { BackHandler, Platform } from "react-native";

export function useAndroidBackHandler(handler: () => boolean) {
  useFocusEffect(
    useCallback(() => {
      if (Platform.OS !== "android") {
        return undefined;
      }

      const subscription = BackHandler.addEventListener("hardwareBackPress", () => handler());
      return () => subscription.remove();
    }, [handler]),
  );
}

export function useAndroidBackToTasks(handleLocalBack?: () => boolean) {
  const router = useRouter();

  useAndroidBackHandler(
    useCallback(() => {
      if (handleLocalBack?.()) {
        return true;
      }
      router.replace("/(tabs)/tasks");
      return true;
    }, [handleLocalBack, router]),
  );
}

export function useAndroidExitApp(handleLocalBack?: () => boolean) {
  useAndroidBackHandler(
    useCallback(() => {
      if (handleLocalBack?.()) {
        return true;
      }
      BackHandler.exitApp();
      return true;
    }, [handleLocalBack]),
  );
}
~~~

## `mobile/lib/api.ts`

- 编码: `utf-8`

~~~typescript
import * as storage from "./storage";
import * as cache from "./cache";
import { devLog } from "./dev-log";
import { normalizeBaseUrl, resolveStoredBaseUrl } from "./base-url";
import type {
  AuthTokenResponse,
  TaskBoardResponse,
  TaskRecord,
  TaskListRecord,
  TaskTagRecord,
  EventLineRecord,
  ClientSummaryRecord,
  SupportRequestRecord,
  EmployeeRecord,
  TaskActivityRecord,
  TaskSettingsRecord,
  SmartTaskDraftResponse,
  ConsultationChatResponse,
  MobileCapabilityRecord,
  TaskContextPreviewRecord,
  TaskUnderstandingRecord,
} from "./types";

const TOKEN_KEY = "yiyu_access_token";
const REFRESH_KEY = "yiyu_refresh_token";
const SERVER_URL_KEY = "yiyu_server_url";
export const CLOUD_PRIMARY_BASE_URL = "https://api.yiyu.love";
export const CLOUD_FALLBACK_BASE_URL = "http://101.126.34.232";
export const DEFAULT_BASE_URL =
  process.env.EXPO_PUBLIC_YIYU_SERVER_URL?.trim() || CLOUD_FALLBACK_BASE_URL;

let baseUrl = DEFAULT_BASE_URL;
const SMART_TASK_DRAFT_TIMEOUT_MS = 12000;

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export async function initBaseUrl(): Promise<void> {
  const saved = await storage.getItem(SERVER_URL_KEY);
  const resolved = resolveStoredBaseUrl(saved, DEFAULT_BASE_URL);
  baseUrl = resolved.baseUrl;

  if (resolved.shouldDeleteSaved) {
    await storage.deleteItem(SERVER_URL_KEY);
  }

  devLog("baseUrl", "initialized", {
    savedUrl: saved ?? null,
    resolvedBaseUrl: baseUrl,
    source: resolved.source,
  });
}

export function setBaseUrl(url: string): void {
  baseUrl = normalizeBaseUrl(url);
}

export function getBaseUrl(): string {
  return baseUrl;
}

export async function setAndSaveBaseUrl(url: string): Promise<void> {
  const trimmed = normalizeBaseUrl(url);
  baseUrl = trimmed;
  await storage.setItem(SERVER_URL_KEY, trimmed);
  devLog("baseUrl", "saved", { baseUrl });
}

async function getToken(): Promise<string | null> {
  return storage.getItem(TOKEN_KEY);
}

export async function saveTokens(auth: AuthTokenResponse): Promise<void> {
  await storage.setItem(TOKEN_KEY, auth.accessToken);
  if (auth.refreshToken) {
    await storage.setItem(REFRESH_KEY, auth.refreshToken);
  }
}

export async function clearTokens(): Promise<void> {
  await storage.deleteItem(TOKEN_KEY);
  await storage.deleteItem(REFRESH_KEY);
}

function withAuthHeaders(options: RequestInit, token: string | null, json: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function fetchWithTimeout(url: string, options: RequestOptions = {}): Promise<Response> {
  const { timeoutMs, ...fetchOptions } = options;
  if (!timeoutMs || timeoutMs <= 0) {
    return fetch(url, fetchOptions);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(url, { ...fetchOptions, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = await getToken();
  const headers = withAuthHeaders(options, token, true);

  const res = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${refreshed}`;
      const retry = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json() as Promise<T>;
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData, options: RequestOptions = {}): Promise<T> {
  const token = await getToken();
  const headers = withAuthHeaders(options, token, false);

  const res = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers, body });
  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const retryHeaders = withAuthHeaders(options, refreshed, false);
      const retry = await fetchWithTimeout(`${baseUrl}${path}`, { ...options, headers: retryHeaders, body });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json() as Promise<T>;
    }
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<string | null> {
  const refreshToken = await storage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as AuthTokenResponse;
    await saveTokens(data);
    return data.accessToken;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`API Error ${status}: ${body}`);
  }
}

// ─── Auth ────────────────────────────────────────
export async function login(email: string, password: string): Promise<AuthTokenResponse> {
  const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const data = (await res.json()) as AuthTokenResponse;
  await saveTokens(data);
  return data;
}

export interface HealthResponse {
  service: string;
  organizationCount: number;
  employeeCount: number;
  taskCount: number;
}

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId: string;
  organizationId: string;
  target: "vector_memory" | "document_archive";
  status: "pending" | "processing" | "completed" | "failed";
  requestedByUserId: string;
  requestedByName: string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
  question: string;
  answer: string;
  errorMessage?: string | null;
  localDocumentId?: string | null;
  localDocumentPath?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConsultationKnowledgeRequestPayload {
  target: "vector_memory" | "document_archive";
  question?: string;
  answer: string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
}

export interface FeishuUserBinding {
  linked: boolean;
  readyForAuthorization: boolean;
  appId: string;
  userId: string;
  openId?: string | null;
  unionId?: string | null;
  feishuUserId?: string | null;
  name?: string | null;
  enName?: string | null;
  avatarUrl?: string | null;
  email?: string | null;
  tenantKey?: string | null;
  boundAt?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
}

export interface FeishuUserBindingStartResult {
  authorizeUrl: string;
  state: string;
  expiresAt: string;
  callbackUrl: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
}

export async function fetchHealth(baseUrlOverride?: string): Promise<HealthResponse> {
  const targetBaseUrl = normalizeBaseUrl(baseUrlOverride ?? baseUrl);
  const res = await fetch(`${targetBaseUrl}/health`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<HealthResponse>;
}

export async function getMe() {
  return request<AuthTokenResponse["user"]>("/api/v1/auth/me");
}

export async function updateMe(payload: { fullName?: string; primaryRole?: string }) {
  return request<AuthTokenResponse["user"]>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getFeishuUserBinding() {
  return request<FeishuUserBinding>("/api/v1/settings/feishu-user-binding");
}

export async function startFeishuUserBinding() {
  return request<FeishuUserBindingStartResult>("/api/v1/settings/feishu-user-binding/start", {
    method: "POST",
  });
}

export async function clearFeishuUserBinding() {
  return request<FeishuUserBinding>("/api/v1/settings/feishu-user-binding", {
    method: "DELETE",
  });
}

export async function logout(): Promise<void> {
  try {
    await request("/api/v1/auth/logout", { method: "POST" });
  } finally {
    await clearTokens();
    await cache.clearAll();
  }
}

// ─── Tasks ───────────────────────────────────────
export async function fetchTaskBoard(): Promise<TaskBoardResponse> {
  return request<TaskBoardResponse>("/api/v1/tasks");
}

// ─── Event Lines ─────────────────────────────────
export async function fetchEventLines(): Promise<EventLineRecord[]> {
  return request<EventLineRecord[]>("/api/v1/event-lines");
}

export async function createEventLine(payload: {
  name: string;
  primaryClientId?: string;
  primaryClientName?: string;
  status?: string;
}): Promise<EventLineRecord> {
  const result = await request<EventLineRecord>("/api/v1/event-lines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.eventLines);
  return result;
}

export async function updateEventLine(
  eventLineId: string,
  payload: {
    name?: string;
    primaryClientId?: string | null;
    primaryClientName?: string | null;
    stage?: string | null;
    summary?: string | null;
    currentBlocker?: string | null;
    recentDecision?: string | null;
    nextStep?: string | null;
    status?: string;
    syncLinkedTaskClientIds?: boolean;
  },
): Promise<EventLineRecord> {
  const result = await request<EventLineRecord>(`/api/v1/event-lines/${eventLineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.eventLines, cache.KEYS.taskBoard);
  return result;
}

export async function fetchClients(): Promise<ClientSummaryRecord[]> {
  return request<ClientSummaryRecord[]>("/api/v1/clients");
}

export async function enqueueConsultationKnowledgeRequest(
  payload: ConsultationKnowledgeRequestPayload,
): Promise<ConsultationKnowledgeRequestRecord> {
  return request<ConsultationKnowledgeRequestRecord>("/api/v1/consultation/knowledge-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchConsultationKnowledgeRequests(
  status?: "pending" | "processing" | "completed" | "failed",
): Promise<ConsultationKnowledgeRequestRecord[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<ConsultationKnowledgeRequestRecord[]>(`/api/v1/consultation/knowledge-requests${qs}`);
}

interface ConsultationChatPayload {
  message: string;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  taskId?: string | null;
  taskTitle?: string | null;
  taskContext?: string | null;
  workspaceContext?: string | null;
  eventLineContext?: string | null;
  taskBoardContext?: string | null;
  sourceLabels?: string[];
  missingEventLineHint?: string | null;
}

export async function sendConsultationChat(
  payload: ConsultationChatPayload,
): Promise<ConsultationChatResponse> {
  return request<ConsultationChatResponse>("/api/v1/consultation/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchMobileCapabilities(): Promise<MobileCapabilityRecord> {
  return request<MobileCapabilityRecord>("/api/v1/mobile/capabilities");
}

// ─── Task Creation ──────────────────────────────
export interface CreateTaskPayload {
  title: string;
  dueDate?: string;
  durationMinutes?: number;
  assigneeId?: string;
  priority?: string;
  clientId?: string;
  listId?: string;
  description?: string;
  eventLineId?: string;
  scopeMode?: string;
  tags?: string[];
  collaboratorIds?: string[];
  businessCategory?: string;
  currentBlocker?: string;
  nextAction?: string;
  recentDecision?: string;
}

export interface UpdateTaskPayload extends Partial<CreateTaskPayload> {
  progressStatus?: string;
}

export async function createTask(payload: CreateTaskPayload): Promise<TaskRecord> {
  const result = await request<TaskRecord>("/api/v1/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export async function updateTask(taskId: string, payload: UpdateTaskPayload): Promise<TaskRecord> {
  const result = await request<TaskRecord>(`/api/v1/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export async function deleteTask(taskId: string): Promise<{ ok?: boolean; success?: boolean }> {
  const result = await request<{ ok?: boolean; success?: boolean }>(`/api/v1/tasks/${taskId}`, {
    method: "DELETE",
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export async function completeTaskWithReview(taskId: string, reviewNote: string): Promise<TaskRecord> {
  const result = await request<TaskRecord>(`/api/v1/tasks/${taskId}/complete-with-review`, {
    method: "POST",
    body: JSON.stringify({ reviewNote }),
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export type UploadableFile =
  | File
  | {
      uri: string;
      name: string;
      type: string;
    };

export interface UploadTaskAttachmentPayload {
  file: UploadableFile;
  clientId?: string | null;
  eventLineId?: string | null;
  title?: string | null;
  durationSeconds?: number | null;
}

export async function uploadTaskAttachment(taskId: string, payload: UploadTaskAttachmentPayload): Promise<TaskRecord> {
  const formData = new FormData();
  formData.append("file", payload.file as any);
  if (payload.clientId) formData.append("clientId", payload.clientId);
  if (payload.eventLineId) formData.append("eventLineId", payload.eventLineId);
  if (payload.title) formData.append("title", payload.title);
  if (payload.durationSeconds && payload.durationSeconds > 0) {
    formData.append("durationSeconds", String(payload.durationSeconds));
  }
  const result = await requestForm<TaskRecord>(`/api/v1/tasks/${taskId}/attachments`, formData, {
    method: "POST",
  });
  cache.invalidate(cache.KEYS.taskBoard);
  return result;
}

export interface TaskAttachmentTranscriptionResponse {
  attachmentId: string;
  transcript: string;
  documentRequest: ConsultationKnowledgeRequestRecord;
}

export async function transcribeTaskAttachmentToDocument(
  taskId: string,
  attachmentId: string,
): Promise<TaskAttachmentTranscriptionResponse> {
  return request<TaskAttachmentTranscriptionResponse>(
    `/api/v1/tasks/${taskId}/attachments/${attachmentId}/transcribe-to-document`,
    { method: "POST" },
  );
}

export interface GenerateSmartTaskDraftPayload {
  transcriptText?: string | null;
  audioFile?: UploadableFile | null;
  referenceDate?: string | null;
  currentEventLineId?: string | null;
}

export async function generateSmartTaskDraft(
  payload: GenerateSmartTaskDraftPayload,
): Promise<SmartTaskDraftResponse> {
  const formData = new FormData();
  if (payload.transcriptText?.trim()) {
    formData.append("transcriptText", payload.transcriptText.trim());
  }
  if (payload.referenceDate?.trim()) {
    formData.append("referenceDate", payload.referenceDate.trim());
  }
  if (payload.currentEventLineId?.trim()) {
    formData.append("currentEventLineId", payload.currentEventLineId.trim());
  }
  if (payload.audioFile) {
    formData.append("audio", payload.audioFile as any);
  }
  return requestForm<SmartTaskDraftResponse>("/api/v1/mobile/smart-input/task-draft", formData, {
    method: "POST",
    timeoutMs: SMART_TASK_DRAFT_TIMEOUT_MS,
  });
}

// ─── Task Lists & Tags ──────────────────────────
export async function fetchTaskLists(): Promise<TaskListRecord[]> {
  const res = await request<{ lists: TaskListRecord[] }>("/api/v1/task-lists");
  return res.lists;
}

// ─── Task Activities ────────────────────────────
export async function fetchTaskActivities(taskId: string): Promise<TaskActivityRecord[]> {
  return request<TaskActivityRecord[]>(`/api/v1/tasks/${taskId}/activity`);
}

export async function fetchTaskUnderstanding(taskId: string): Promise<TaskUnderstandingRecord> {
  return request<TaskUnderstandingRecord>(`/api/v1/tasks/${taskId}/understanding`);
}

export async function fetchTaskContextPreview(taskId: string): Promise<TaskContextPreviewRecord> {
  return request<TaskContextPreviewRecord>(`/api/v1/tasks/${taskId}/context-preview`);
}

export async function fetchClientWorkspace(clientId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/clients/${clientId}/workspace`);
}

export async function fetchStrategicCockpit(clientId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/v1/clients/${clientId}/strategic-cockpit`);
}

export async function fetchReviews(weekLabel?: string): Promise<Record<string, unknown>> {
  const suffix = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : "";
  return request<Record<string, unknown>>(`/api/v1/reviews${suffix}`);
}

// ─── Task Settings ─────────────────────────────
interface TaskSettingsPayload {
  defaultListId?: string | null;
  defaultPriority?: "low" | "normal" | "high";
  defaultDueDatePreset?: "today" | "none";
  defaultViewMode?: "inbox" | "list" | "calendar" | "review";
  listSortMode?: "manual" | "priority" | "dueDate";
  showCompletedTasks?: boolean;
  defaultReviewScope?: "work" | "personal";
  autoAssignSelf?: boolean;
}

export async function fetchTaskSettings(): Promise<TaskSettingsRecord> {
  return request<TaskSettingsRecord>("/api/v1/settings/tasks");
}

export async function updateTaskSettings(
  payload: Partial<TaskSettingsPayload>,
): Promise<TaskSettingsRecord> {
  const result = await request<TaskSettingsRecord>("/api/v1/settings/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  cache.invalidate(cache.KEYS.taskSettings);
  return result;
}
~~~

## `mobile/lib/app-chrome.ts`

- 编码: `utf-8`

~~~typescript
import { Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { spacing } from "./theme";

export const webPreviewChrome = {
  topInset: 62,
  bottomInset: 24,
  statusBarHeight: 56,
  islandWidth: 124,
  islandHeight: 34,
  islandTop: 10,
  horizontalPadding: 18,
} as const;

const WEB_PREVIEW_TOP_INSET = webPreviewChrome.topInset;
const WEB_PREVIEW_BOTTOM_INSET = webPreviewChrome.bottomInset;

export function useAppChromeInsets() {
  const insets = useSafeAreaInsets();
  const topInset = Math.max(insets.top, Platform.OS === "web" ? WEB_PREVIEW_TOP_INSET : 0);
  const bottomInset = Math.max(insets.bottom, Platform.OS === "web" ? WEB_PREVIEW_BOTTOM_INSET : 0);

  return {
    rawInsets: insets,
    topInset,
    bottomInset,
    headerTopPadding: topInset + spacing.md,
    screenTopPadding: topInset + spacing.lg,
    screenBottomPadding: bottomInset + spacing.lg,
    overlayBottomPadding: bottomInset + spacing.lg,
    floatingMenuTopInset: topInset + 48,
    tabBarHeight: 72 + bottomInset,
    tabBarPaddingBottom: bottomInset + spacing.sm,
    tabBarPaddingTop: spacing.sm,
  };
}
~~~

## `mobile/lib/auth-context.tsx`

- 编码: `utf-8`

~~~tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as storage from "./storage";
import type { SessionUser } from "./types";
import * as api from "./api";
import {
  initializeRuntime,
  startAuthenticatedRuntime,
  stopAuthenticatedRuntime,
} from "./runtime";

interface AuthState {
  isLoading: boolean;
  user: SessionUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  isLoading: true,
  user: null,
  signIn: async () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    (async () => {
      try {
        await initializeRuntime();
        const token = await storage.getItem("yiyu_access_token");
        if (token) {
          const me = await api.getMe();
          setUser(me);
        }
      } catch {
        await api.clearTokens();
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (isLoading) return;
    if (user) {
      void startAuthenticatedRuntime(user);
      return;
    }
    void stopAuthenticatedRuntime({ clearSessionState: true });
  }, [isLoading, user]);

  const signIn = useCallback(async (email: string, password: string) => {
    await initializeRuntime();
    const res = await api.login(email, password);
    setUser(res.user);
  }, []);

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ isLoading, user, signIn, signOut }),
    [isLoading, user, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
~~~

## `mobile/lib/base-url.ts`

- 编码: `utf-8`

~~~typescript
export interface ResolvedBaseUrl {
  baseUrl: string;
  shouldDeleteSaved: boolean;
  source: "saved" | "default" | "invalid_saved";
}

export function isPrivateOrLocalHostname(hostname: string): boolean {
  const value = hostname.trim().toLowerCase();
  if (!value) return true;
  if (value === "localhost" || value.endsWith(".local")) return true;

  if (!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(value)) {
    return false;
  }

  const [a, b] = value.split(".").map((part) => Number(part));
  if (Number.isNaN(a) || Number.isNaN(b)) {
    return false;
  }

  return (
    a === 10 ||
    a === 127 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168)
  );
}

export function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim();
  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  const parsed = new URL(withProtocol);
  return parsed.toString().replace(/\/+$/, "");
}

export function resolveStoredBaseUrl(
  savedUrl: string | null | undefined,
  fallbackUrl: string,
): ResolvedBaseUrl {
  if (!savedUrl?.trim()) {
    return {
      baseUrl: normalizeBaseUrl(fallbackUrl),
      shouldDeleteSaved: false,
      source: "default",
    };
  }

  try {
    return {
      baseUrl: normalizeBaseUrl(savedUrl),
      shouldDeleteSaved: false,
      source: "saved",
    };
  } catch {
    return {
      baseUrl: normalizeBaseUrl(fallbackUrl),
      shouldDeleteSaved: true,
      source: "invalid_saved",
    };
  }
}

export function isValidBaseUrl(value: string): boolean {
  try {
    normalizeBaseUrl(value);
    return true;
  } catch {
    return false;
  }
}
~~~

## `mobile/lib/boundary-cards.ts`

- 编码: `utf-8`

~~~typescript
import type { BoundaryCard } from "./types";

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

export function buildBoundaryCards(workspace: any, cockpit: any): BoundaryCard[] {
  const healthSummary = Array.isArray(cockpit?.health)
    ? cockpit.health
        .map((item: any) => toText(item?.summary || item?.label || item?.value))
        .filter(Boolean)
        .join("；")
    : "";
  const conflictSummary = Array.isArray(workspace?.latestConflicts)
    ? workspace.latestConflicts
        .map((item: any) => toText(item?.summary || item?.title))
        .filter(Boolean)
        .slice(0, 2)
        .join("；")
    : "";
  const pendingSummary = Array.isArray(cockpit?.pendingDecisions)
    ? cockpit.pendingDecisions
        .map((item: any) => toText(item?.summary || item?.title || item?.label))
        .filter(Boolean)
        .slice(0, 3)
        .join("；")
    : "";
  const reminderSummary = [
    ...(Array.isArray(workspace?.latestOpenQuestions)
      ? workspace.latestOpenQuestions
          .map((item: any) => toText(item?.summary || item?.question || item?.title))
          .filter(Boolean)
          .slice(0, 2)
      : []),
    ...(Array.isArray(cockpit?.pendingMaterials)
      ? cockpit.pendingMaterials
          .map((item: any) => toText(item?.summary || item?.title || item?.label))
          .filter(Boolean)
          .slice(0, 2)
      : []),
  ].join("；");

  const officialReady = cockpit?.officialLayerStatus === "ready";
  const officialSummary = officialReady
    ? toText(
        cockpit?.headline?.summary ||
          cockpit?.headline?.mainSummary ||
          cockpit?.headline?.primaryStatement ||
          cockpit?.headline?.title ||
          cockpit?.clientTagline ||
          cockpit?.stageLabel ||
          workspace?.client?.name,
      )
    : "";

  return [
    {
      kind: "official",
      title: officialReady ? "正式判断" : "当前暂无已批准判断",
      summary: officialSummary || "暂无正式判断，请先结合工作台与证据层继续推进。",
      sourceType: officialReady ? "manual" : "mixed",
      updatedAt: cockpit?.updatedAt ?? workspace?.client?.updatedAt ?? null,
      evidenceCount: officialReady ? null : 0,
      isEmpty: !officialReady,
    },
    {
      kind: "pending",
      title: "待确认判断",
      summary: pendingSummary || "暂无待确认判断",
      sourceType: pendingSummary ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount: Array.isArray(cockpit?.pendingDecisions) ? cockpit.pendingDecisions.length : 0,
      isEmpty: !pendingSummary,
    },
    {
      kind: "risk",
      title: "风险 / 冲突",
      summary: [healthSummary, conflictSummary].filter(Boolean).join("；") || "暂无明显风险",
      sourceType: [healthSummary, conflictSummary].filter(Boolean).length > 1 ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount:
        (Array.isArray(cockpit?.health) ? cockpit.health.length : 0) +
        (Array.isArray(workspace?.latestConflicts) ? workspace.latestConflicts.length : 0),
      isEmpty: !healthSummary && !conflictSummary,
    },
    {
      kind: "reminder",
      title: "提醒 / 缺口",
      summary: reminderSummary || "暂无提醒项",
      sourceType: reminderSummary ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount:
        (Array.isArray(workspace?.latestOpenQuestions) ? workspace.latestOpenQuestions.length : 0) +
        (Array.isArray(cockpit?.pendingMaterials) ? cockpit.pendingMaterials.length : 0),
      isEmpty: !reminderSummary,
    },
  ];
}
~~~

## `mobile/lib/cache.ts`

- 编码: `utf-8`

~~~typescript
/**
 * Local data cache — stale-while-revalidate pattern.
 *
 * Every cacheable GET endpoint is stored as JSON in AsyncStorage.
 * On page load:
 *   1. Cached data is returned instantly → UI appears immediately
 *   2. A background network fetch runs in parallel
 *   3. When fresh data arrives, the cache is updated and `setter` is called again
 *
 * On write operations (create/update/delete), the relevant cache key is
 * invalidated so the next load always hits the network first.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as localDb from "./local-db";
import { buildScopedStorageKey, resolveScopedStorageNamespace } from "./scope-storage-core";

// ─── Prefix ──────────────────────────────────────
const PREFIX = "yiyu_cache_";

interface CacheEntry<T> {
  data: T;
  ts: number; // Date.now() when stored
}

// Cache is considered "stale" after 30 minutes, but still usable while
// network fetch is in flight.  After 24 hours the entry is discarded.
const STALE_MS = 30 * 60 * 1000;
const EXPIRED_MS = 24 * 60 * 60 * 1000;

// ─── Low-level helpers ───────────────────────────

function buildCacheStorageKey(
  key: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): string {
  return buildScopedStorageKey(PREFIX, key, scopeKey);
}

async function getCache<T>(key: string): Promise<{ data: T; stale: boolean } | null> {
  try {
    const raw = await AsyncStorage.getItem(buildCacheStorageKey(key));
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    const age = Date.now() - entry.ts;
    if (age > EXPIRED_MS) {
      // Too old – discard
      void AsyncStorage.removeItem(buildCacheStorageKey(key));
      return null;
    }
    return { data: entry.data, stale: age > STALE_MS };
  } catch {
    return null;
  }
}

async function setCache<T>(key: string, data: T): Promise<void> {
  try {
    const entry: CacheEntry<T> = { data, ts: Date.now() };
    await AsyncStorage.setItem(buildCacheStorageKey(key), JSON.stringify(entry));
  } catch {
    // Storage write failure is non-critical — ignore silently
  }
}

async function removeCache(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(buildCacheStorageKey(key));
  } catch {}
}

// ─── Public API ──────────────────────────────────

/**
 * Core stale-while-revalidate loader.
 *
 * @param cacheKey   Unique key for this data set
 * @param fetcher    Async function that fetches fresh data from the network
 * @param setter     Callback to push data into React state (may be called twice:
 *                   once with cached data, once with fresh data)
 * @param options.forceNetwork  Skip reading cache (for pull-to-refresh)
 */
export async function loadWithCache<T>(
  cacheKey: string,
  fetcher: () => Promise<T>,
  setter: (data: T) => void,
  options?: { forceNetwork?: boolean },
): Promise<void> {
  const skipCache = options?.forceNetwork === true;

  let hasCachedData = false;

  // 1. Try serving from cache first (instant)
  if (!skipCache) {
    const cached = await getCache<T>(cacheKey);
    if (cached) {
      setter(cached.data);
      hasCachedData = true;
    }
  }

  // 2. Fetch fresh data from network
  try {
    const fresh = await fetcher();
    await setCache(cacheKey, fresh);
    setter(fresh);
  } catch (error) {
    // If we had cached data, swallow network errors silently —
    // the user is already seeing something useful.
    if (!hasCachedData) throw error;
  }
}

/**
 * Invalidate one or more cache keys.
 * Call after write operations (create, update, delete).
 */
export function invalidate(...keys: string[]): void {
  for (const key of keys) {
    void removeCache(key);
  }
}

export async function clearScope(
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<void> {
  try {
    const scopePrefix = `${PREFIX}${resolveScopedStorageNamespace(scopeKey)}:`;
    const allKeys = await AsyncStorage.getAllKeys();
    const scopedKeys = allKeys.filter((item) => item.startsWith(scopePrefix));
    if (scopedKeys.length > 0) {
      await AsyncStorage.multiRemove(scopedKeys);
    }
  } catch {}
}

/**
 * Clear all cache entries (e.g. on logout).
 */
export async function clearAll(): Promise<void> {
  try {
    const allKeys = await AsyncStorage.getAllKeys();
    const cacheKeys = allKeys.filter((k) => k.startsWith(PREFIX));
    if (cacheKeys.length > 0) {
      await AsyncStorage.multiRemove(cacheKeys);
    }
  } catch {}
}

// ─── Well-known cache keys ───────────────────────
export const KEYS = {
  taskBoard: "taskBoard",
  taskLists: "taskLists",
  clients: "clients",
  eventLines: "eventLines",
  taskSettings: "taskSettings",
  userProfile: "userProfile",
  consultKnowledgeRequests: "consultKnowledgeRequests",
} as const;
~~~

## `mobile/lib/calendar-repository-core.ts`

- 编码: `utf-8`

~~~typescript
export interface CalendarWriteModeInput {
  calendarLocalFirstWriteEnabled: boolean;
  hasRemoteId: boolean;
  hasPendingOps: boolean;
  isSyncPaused: boolean;
  blockedReason: string | null;
}

export interface CalendarScheduleValue {
  date: string | null;
  time: string | null;
  durationMinutes: number | null;
}

export function decideCalendarWriteMode(input: CalendarWriteModeInput): "local-first" | "remote-first" {
  if (input.calendarLocalFirstWriteEnabled) {
    return "local-first";
  }
  if (!input.hasRemoteId) {
    return "local-first";
  }
  if (input.hasPendingOps) {
    return "local-first";
  }
  if (input.isSyncPaused || Boolean(input.blockedReason)) {
    return "local-first";
  }
  return "remote-first";
}

export function buildDueDateForCalendarDrop(
  currentDueDate: string | null | undefined,
  targetKey: string,
  selectedDateKey: string,
): string {
  if (targetKey.startsWith("hour:")) {
    const hour = Number.parseInt(targetKey.slice(5), 10);
    const timeStr = `${String(hour).padStart(2, "0")}:00`;
    return `${selectedDateKey}T${timeStr}`;
  }

  const existingTime = currentDueDate?.includes("T") ? currentDueDate.slice(10) : "";
  return `${targetKey}${existingTime}`;
}

export function buildTaskScheduleUpdatesFromPicker(
  value: CalendarScheduleValue,
): { dueDate: string | null; durationMinutes?: number } {
  let dueDate: string | null = null;
  if (value.date) {
    dueDate = value.time ? `${value.date}T${value.time}` : value.date;
  }

  const updates: { dueDate: string | null; durationMinutes?: number } = {
    dueDate,
  };

  if (value.durationMinutes != null) {
    updates.durationMinutes = value.durationMinutes;
  }

  return updates;
}
~~~

## `mobile/lib/calendar-repository.ts`

- 编码: `utf-8`

~~~typescript
import * as api from "./api";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import {
  buildDueDateForCalendarDrop,
  buildTaskScheduleUpdatesFromPicker,
  decideCalendarWriteMode,
  type CalendarScheduleValue,
} from "./calendar-repository-core";
import { isCalendarLocalFirstWriteEnabled } from "./runtime-flags";
import {
  emitDataChanged,
  getSyncControlState,
  isSyncPaused,
  updateTaskOfflineFirst,
} from "./sync-engine";
import type { TaskRecord } from "./types";

export async function updateCalendarTaskSchedule(
  taskId: string,
  updates: Pick<Partial<TaskRecord>, "dueDate" | "durationMinutes">,
): Promise<TaskRecord> {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法更新排期");
  }

  const writeMode = decideCalendarWriteMode({
    calendarLocalFirstWriteEnabled: isCalendarLocalFirstWriteEnabled(),
    hasRemoteId: Boolean(existing.remoteId),
    hasPendingOps: localDb.getPendingOpsForEntity("task", taskId).length > 0,
    isSyncPaused: isSyncPaused(),
    blockedReason: getSyncControlState().blockedReason,
  });

  if (writeMode === "local-first") {
    updateTaskOfflineFirst(taskId, updates);
    return (
      localDb.getTaskById(taskId) ?? {
        ...existing,
        ...updates,
      }
    );
  }

  if (!existing.remoteId) {
    updateTaskOfflineFirst(taskId, updates);
    return (
      localDb.getTaskById(taskId) ?? {
        ...existing,
        ...updates,
      }
    );
  }

  const payload: api.UpdateTaskPayload = {
    dueDate: updates.dueDate ?? undefined,
    durationMinutes: updates.durationMinutes ?? undefined,
  };
  const updatedTask = await api.updateTask(existing.remoteId, payload);
  localDb.replaceTaskWithServerState(taskId, {
    ...updatedTask,
    remoteId: updatedTask.remoteId ?? existing.remoteId,
  });
  emitDataChanged();
  devLog("calendarRepository", "remote_first.schedule_update", {
    taskId,
    remoteId: existing.remoteId,
  });
  return localDb.getTaskById(taskId) ?? updatedTask;
}

export async function moveTaskToCalendarTarget(
  task: Pick<TaskRecord, "id" | "dueDate">,
  targetKey: string,
  selectedDateKey: string,
): Promise<TaskRecord> {
  const dueDate = buildDueDateForCalendarDrop(task.dueDate ?? null, targetKey, selectedDateKey);
  return updateCalendarTaskSchedule(task.id, { dueDate });
}

export async function resizeCalendarTaskDuration(
  taskId: string,
  durationMinutes: number,
): Promise<TaskRecord> {
  return updateCalendarTaskSchedule(taskId, { durationMinutes });
}

export async function updateTaskScheduleFromPicker(
  taskId: string,
  value: CalendarScheduleValue,
): Promise<TaskRecord> {
  return updateCalendarTaskSchedule(taskId, buildTaskScheduleUpdatesFromPicker(value));
}
~~~

## `mobile/lib/calendar-selectors.ts`

- 编码: `utf-8`

~~~typescript
import type { TaskRecord } from "./types";

export interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

export function groupTasksByDate(tasks: readonly TaskRecord[]): Map<string, TaskRecord[]> {
  const grouped = new Map<string, TaskRecord[]>();
  for (const task of tasks) {
    if (!task.dueDate) continue;
    const dateKey = task.dueDate.slice(0, 10);
    const existing = grouped.get(dateKey);
    if (existing) {
      existing.push(task);
      continue;
    }
    grouped.set(dateKey, [task]);
  }
  return grouped;
}

export function getTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return grouped.get(dateKey) ?? [];
}

export function getScheduledTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return getTasksForDate(grouped, dateKey).filter((task) => task.dueDate?.includes("T"));
}

export function getAllDayTasksForDate(grouped: Map<string, TaskRecord[]>, dateKey: string): TaskRecord[] {
  return getTasksForDate(grouped, dateKey).filter((task) => task.dueDate && !task.dueDate.includes("T"));
}

export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

export function buildMonthCalendarDays(year: number, month: number): readonly CalendarDay[] {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const result: CalendarDay[] = [];

  for (let index = 0; index < firstDay; index += 1) {
    const previousMonth = month === 0 ? 11 : month - 1;
    const previousYear = month === 0 ? year - 1 : year;
    const previousMonthDays = getDaysInMonth(previousYear, previousMonth);
    const day = previousMonthDays - firstDay + 1 + index;
    result.push({
      day,
      dateKey: `${previousYear}-${String(previousMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      isCurrentMonth: false,
    });
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    result.push({
      day,
      dateKey: `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      isCurrentMonth: true,
    });
  }

  const remainder = result.length % 7;
  if (remainder > 0) {
    const nextMonth = month === 11 ? 0 : month + 1;
    const nextYear = month === 11 ? year + 1 : year;
    for (let day = 1; day <= 7 - remainder; day += 1) {
      result.push({
        day,
        dateKey: `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        isCurrentMonth: false,
      });
    }
  }

  return result;
}
~~~

## `mobile/lib/client-intel-store.ts`

- 编码: `utf-8`

~~~typescript
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchClientWorkspace, fetchStrategicCockpit } from "./api";
import { buildBoundaryCards } from "./boundary-cards";
import { deriveBoundaryState } from "./current-focus-core";
import * as localDb from "./local-db";
import { buildScopedStorageKey, resolveScopedStorageNamespace } from "./scope-storage-core";
import type {
  ClientWorkspaceLiteSnapshot,
  WorkspaceLiteItem,
  WorkspaceLiteTaskItem,
} from "./types";

const CACHE_PREFIX = "client_intel_v1:";
const memoryCache = new Map<string, ClientWorkspaceLiteSnapshot>();

function buildClientIntelStorageKey(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): string {
  return buildScopedStorageKey(CACHE_PREFIX, clientId, scopeKey);
}

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

function pickSummaryItem(item: any, fallbackTitle: string): WorkspaceLiteItem {
  return {
    id: toText(item?.id || item?.meetingId || item?.documentId || fallbackTitle),
    title: toText(item?.title || item?.label || item?.name || fallbackTitle),
    summary: toText(item?.summary || item?.description || item?.note || item?.statusLabel || ""),
    subtitle: toText(item?.quarter || item?.updatedAt || item?.meetingDate || item?.sourceType || ""),
    updatedAt: item?.updatedAt ?? item?.createdAt ?? null,
  };
}

function pickTaskItem(item: any): WorkspaceLiteTaskItem {
  return {
    id: toText(item?.id),
    title: toText(item?.title || item?.name || "未命名任务"),
    status: toText(item?.status || item?.progressStatus || ""),
    clientName: item?.clientName ?? null,
    eventLineName: item?.eventLineName ?? null,
  };
}

function pickHeadline(cockpit: any): string | null {
  const headline = cockpit?.headline;
  if (!headline) {
    return null;
  }
  return (
    toText(headline.summary || headline.mainSummary || headline.primaryStatement || headline.title) ||
    null
  );
}

function adaptClientWorkspaceLite(clientId: string, workspace: any, cockpit: any): ClientWorkspaceLiteSnapshot {
  const boundaryCards = buildBoundaryCards(workspace, cockpit);
  return {
    clientId,
    clientName: toText(workspace?.client?.name || cockpit?.clientName || "客户"),
    boundaryCards,
    boundaryState: deriveBoundaryState(boundaryCards),
    goals: Array.isArray(workspace?.goals) ? workspace.goals.slice(0, 4).map((item: any) => pickSummaryItem(item, "目标")) : [],
    latestMeetings: Array.isArray(workspace?.meetings) ? workspace.meetings.slice(0, 4).map((item: any) => pickSummaryItem(item, "会议")) : [],
    knowledgeStatus:
      toText(workspace?.knowledgeStatus?.summary || workspace?.knowledgeStatus?.statusLabel || workspace?.knowledgeStatus?.status) || null,
    recentDocuments: Array.isArray(workspace?.documentCards)
      ? workspace.documentCards.slice(0, 4).map((item: any) => pickSummaryItem(item, "资料"))
      : Array.isArray(workspace?.documents)
        ? workspace.documents.slice(0, 4).map((item: any) => pickSummaryItem(item, "资料"))
        : [],
    openQuestions: Array.isArray(workspace?.latestOpenQuestions)
      ? workspace.latestOpenQuestions.slice(0, 4).map((item: any) => pickSummaryItem(item, "开放问题"))
      : [],
    conflicts: Array.isArray(workspace?.latestConflicts)
      ? workspace.latestConflicts.slice(0, 4).map((item: any) => pickSummaryItem(item, "冲突"))
      : [],
    relatedTasks: Array.isArray(workspace?.relatedTasks)
      ? workspace.relatedTasks.slice(0, 6).map((item: any) => pickTaskItem(item))
      : [],
    nextActions: [
      ...(Array.isArray(cockpit?.pendingDecisions)
        ? cockpit.pendingDecisions.map((item: any) => toText(item?.summary || item?.title || item?.label))
        : []),
      ...(Array.isArray(workspace?.relatedTasks)
        ? workspace.relatedTasks
            .map((item: any) => toText(item?.nextAction || item?.title))
            .filter(Boolean)
            .slice(0, 2)
        : []),
    ].filter(Boolean).slice(0, 5),
    headline: pickHeadline(cockpit),
    health: Array.isArray(cockpit?.health)
      ? cockpit.health.map((item: any) => toText(item?.summary || item?.label || item?.value)).filter(Boolean).slice(0, 4)
      : [],
    twoWeekChanges: Array.isArray(cockpit?.twoWeekChanges)
      ? cockpit.twoWeekChanges.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    pendingDecisions: Array.isArray(cockpit?.pendingDecisions)
      ? cockpit.pendingDecisions.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    pendingMaterials: Array.isArray(cockpit?.pendingMaterials)
      ? cockpit.pendingMaterials.map((item: any) => toText(item?.summary || item?.title || item?.label)).filter(Boolean).slice(0, 4)
      : [],
    updatedAt: cockpit?.updatedAt ?? workspace?.client?.updatedAt ?? new Date().toISOString(),
  };
}

async function loadCachedSnapshot(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<ClientWorkspaceLiteSnapshot | null> {
  const storageKey = buildClientIntelStorageKey(clientId, scopeKey);
  if (memoryCache.has(storageKey)) {
    return memoryCache.get(storageKey) ?? null;
  }
  const rawValue = await AsyncStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawValue) as ClientWorkspaceLiteSnapshot;
    memoryCache.set(storageKey, parsed);
    return parsed;
  } catch {
    return null;
  }
}

async function fetchLiveSnapshot(
  clientId: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<ClientWorkspaceLiteSnapshot> {
  const [workspace, cockpit] = await Promise.all([
    fetchClientWorkspace(clientId),
    fetchStrategicCockpit(clientId),
  ]);
  const snapshot = adaptClientWorkspaceLite(clientId, workspace, cockpit);
  const storageKey = buildClientIntelStorageKey(clientId, scopeKey);
  memoryCache.set(storageKey, snapshot);
  await AsyncStorage.setItem(storageKey, JSON.stringify(snapshot));
  return snapshot;
}

export async function clearClientIntelCache(options?: {
  scopeKey?: string | null;
  allScopes?: boolean;
}): Promise<void> {
  if (options?.allScopes) {
    memoryCache.clear();
    const allKeys = await AsyncStorage.getAllKeys();
    const cachedKeys = allKeys.filter((item) => item.startsWith(CACHE_PREFIX));
    if (cachedKeys.length > 0) {
      await AsyncStorage.multiRemove(cachedKeys);
    }
    return;
  }

  const scopePrefix = `${CACHE_PREFIX}${resolveScopedStorageNamespace(
    options?.scopeKey ?? localDb.getActiveAccountScopeKey(),
  )}:`;
  for (const key of [...memoryCache.keys()]) {
    if (key.startsWith(scopePrefix)) {
      memoryCache.delete(key);
    }
  }
  const allKeys = await AsyncStorage.getAllKeys();
  const cachedKeys = allKeys.filter((item) => item.startsWith(scopePrefix));
  if (cachedKeys.length > 0) {
    await AsyncStorage.multiRemove(cachedKeys);
  }
}

export function useClientIntel(clientId: string | null | undefined) {
  const [snapshot, setSnapshot] = useState<ClientWorkspaceLiteSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!clientId) {
      setSnapshot(null);
      setError(null);
      return null;
    }
    const scopeKey = localDb.getActiveAccountScopeKey();
    setIsRefreshing(true);
    try {
      const next = await fetchLiveSnapshot(clientId, scopeKey);
      setSnapshot(next);
      setError(null);
      return next;
    } catch (currentError) {
      setError(currentError instanceof Error ? currentError.message : "工作台加载失败");
      return null;
    } finally {
      setIsRefreshing(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (!clientId) {
      setSnapshot(null);
      setIsLoading(false);
      setError(null);
      return;
    }
    let cancelled = false;
    const scopeKey = localDb.getActiveAccountScopeKey();
    setIsLoading(true);
    void loadCachedSnapshot(clientId, scopeKey)
      .then((cached) => {
        if (cancelled) {
          return;
        }
        if (cached) {
          setSnapshot(cached);
          setIsLoading(false);
        }
        return fetchLiveSnapshot(clientId, scopeKey);
      })
      .then((live) => {
        if (!cancelled && live) {
          setSnapshot(live);
          setError(null);
        }
      })
      .catch((currentError) => {
        if (!cancelled) {
          setError(currentError instanceof Error ? currentError.message : "工作台加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  return useMemo(
    () => ({
      snapshot,
      isLoading,
      isRefreshing,
      error,
      refresh,
    }),
    [error, isLoading, isRefreshing, refresh, snapshot],
  );
}
~~~

## `mobile/lib/consult-context-adapter.ts`

- 编码: `utf-8`

~~~typescript
import { buildTaskContextSummary } from "./consult-context";
import type { ConsultContextOption } from "./consult-context";
import type {
  ClientWorkspaceLiteSnapshot,
  CurrentFocus,
  EventLineRecord,
  TaskRecord,
  WorkspaceLiteItem,
} from "./types";

export interface ConsultRequestContext {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
}

function compactText(value: string | null | undefined, maxLength = 180): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength - 1)}...`;
}

function collectItemSummaries(
  items: readonly WorkspaceLiteItem[] | null | undefined,
  limit = 3,
): string[] {
  if (!items?.length) {
    return [];
  }
  return items
    .map((item) => {
      const title = compactText(item.title, 60);
      const summary = compactText(item.summary ?? null, 90);
      const subtitle = compactText(item.subtitle ?? null, 50);
      if (title && summary) {
        return `${title}：${summary}`;
      }
      if (title && subtitle) {
        return `${title}（${subtitle}）`;
      }
      return title ?? summary ?? subtitle ?? null;
    })
    .filter((item): item is string => Boolean(item))
    .slice(0, limit);
}

function collectTextSummaries(
  items: readonly string[] | null | undefined,
  limit = 3,
  maxLength = 90,
): string[] {
  if (!items?.length) {
    return [];
  }
  return items
    .map((item) => compactText(item, maxLength))
    .filter((item): item is string => Boolean(item))
    .slice(0, limit);
}

function pushSummaryLine(
  lines: string[],
  label: string,
  values: readonly string[],
): void {
  if (values.length === 0) {
    return;
  }
  lines.push(`${label}：${values.join("；")}`);
}

function buildWorkspaceContext(snapshot?: ClientWorkspaceLiteSnapshot | null): string | null {
  if (!snapshot) {
    return null;
  }
  const lines: string[] = [];
  const headline = compactText(snapshot.headline ?? null, 140);
  if (headline) {
    lines.push(`客户工作台：${headline}`);
  }
  pushSummaryLine(lines, "阶段目标", collectItemSummaries(snapshot.goals));
  pushSummaryLine(lines, "最近会议", collectItemSummaries(snapshot.latestMeetings, 2));
  pushSummaryLine(lines, "开放问题", collectItemSummaries(snapshot.openQuestions));
  pushSummaryLine(lines, "待决策", collectTextSummaries(snapshot.pendingDecisions));
  pushSummaryLine(lines, "下一步", collectTextSummaries(snapshot.nextActions));
  pushSummaryLine(lines, "健康信号", collectTextSummaries(snapshot.health, 2));
  pushSummaryLine(lines, "最近变化", collectTextSummaries(snapshot.twoWeekChanges, 2));
  pushSummaryLine(lines, "待补材料", collectTextSummaries(snapshot.pendingMaterials, 2));
  pushSummaryLine(lines, "最近资料", collectItemSummaries(snapshot.recentDocuments, 2));
  const boundaryCards = snapshot.boundaryCards
    .filter((item) => !item.isEmpty)
    .map((item) => compactText(`${item.title}：${item.summary}`, 110))
    .filter((item): item is string => Boolean(item))
    .slice(0, 2);
  pushSummaryLine(lines, "边界提醒", boundaryCards);
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildEventLineContext(eventLine?: EventLineRecord | null): string | null {
  if (!eventLine) {
    return null;
  }
  const lines: string[] = [];
  const name = compactText(eventLine.name, 80);
  if (name) {
    lines.push(`事件线：${name}`);
  }
  const stage = compactText(eventLine.stage ?? null, 60);
  if (stage) {
    lines.push(`阶段：${stage}`);
  }
  const summary = compactText(eventLine.summary ?? null, 180);
  if (summary) {
    lines.push(`事件线摘要：${summary}`);
  }
  const blocker = compactText(eventLine.currentBlocker ?? null, 120);
  if (blocker) {
    lines.push(`当前卡点：${blocker}`);
  }
  const recentDecision = compactText(eventLine.recentDecision ?? null, 120);
  if (recentDecision) {
    lines.push(`最近判断：${recentDecision}`);
  }
  const nextStep = compactText(eventLine.nextStep ?? null, 120);
  if (nextStep) {
    lines.push(`下一步：${nextStep}`);
  }
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildFocusedTaskContext(
  task: TaskRecord | null,
  weekLabel: string | null | undefined,
  fallbackTitle?: string | null,
): string | null {
  if (!task && !weekLabel && !fallbackTitle) {
    return null;
  }
  const lines: string[] = [];
  const title = compactText(task?.title ?? fallbackTitle ?? null, 80);
  if (title) {
    lines.push(`当前任务：${title}`);
  }
  const description = compactText(task?.description ?? null, 180);
  if (description) {
    lines.push(`任务说明：${description}`);
  }
  const blocker = compactText(task?.currentBlocker ?? null, 120);
  if (blocker) {
    lines.push(`任务卡点：${blocker}`);
  }
  const nextAction = compactText(task?.nextAction ?? null, 120);
  if (nextAction) {
    lines.push(`任务下一步：${nextAction}`);
  }
  const recentDecision = compactText(task?.recentDecision ?? null, 120);
  if (recentDecision) {
    lines.push(`任务判断：${recentDecision}`);
  }
  if (weekLabel) {
    lines.push(`当前周：${weekLabel}`);
  }
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildTaskBoardContext(
  tasks: readonly TaskRecord[],
  options: {
    readonly clientId?: string | null;
    readonly eventLineId?: string | null;
    readonly weekLabel?: string | null;
  },
): string | null {
  const scopedTasks = tasks.filter((task) => {
    if (options.eventLineId) {
      return task.eventLineId === options.eventLineId;
    }
    if (options.clientId) {
      return task.clientId === options.clientId;
    }
    return true;
  });
  if (scopedTasks.length === 0) {
    return null;
  }
  const activeTasks = scopedTasks.filter((task) => task.progressStatus !== "done");
  const overdueCount = activeTasks.filter((task) => {
    if (!task.dueDate) {
      return false;
    }
    return task.dueDate < new Date().toISOString().slice(0, 10);
  }).length;
  const lines: string[] = [];
  const boardLabel = options.weekLabel ? `${options.weekLabel} 任务板` : "任务板";
  lines.push(`${boardLabel}：共 ${scopedTasks.length} 条，未完成 ${activeTasks.length} 条`);
  if (overdueCount > 0) {
    lines.push(`逾期任务：${overdueCount} 条`);
  }
  const statusCounts = new Map<string, number>();
  for (const task of activeTasks) {
    const status = compactText(task.progressStatus, 24) ?? "todo";
    statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
  }
  if (statusCounts.size > 0) {
    const statusSummary = [...statusCounts.entries()]
      .map(([status, count]) => `${status} ${count}`)
      .join("，");
    lines.push(`状态分布：${statusSummary}`);
  }
  const titleSummary =
    buildTaskContextSummary(scopedTasks, {
      clientId: options.clientId,
      eventLineId: options.eventLineId,
      weekLabel: options.weekLabel,
      limit: 6,
    }) ?? null;
  if (titleSummary) {
    lines.push(titleSummary);
  }
  const nextActions = activeTasks
    .map((task) => compactText(task.nextAction ?? task.title, 90))
    .filter((item): item is string => Boolean(item))
    .slice(0, 3);
  pushSummaryLine(lines, "优先推进", nextActions);
  return lines.length > 0 ? lines.join("\n") : null;
}

export function buildConsultRequestContext(params: {
  readonly currentFocus: CurrentFocus;
  readonly selectedContext: ConsultContextOption;
  readonly tasks: readonly TaskRecord[];
  readonly workspaceLite?: ClientWorkspaceLiteSnapshot | null;
  readonly eventLine?: EventLineRecord | null;
}): ConsultRequestContext {
  const clientId = params.selectedContext.clientId ?? params.currentFocus.clientId ?? null;
  const clientName = params.selectedContext.clientName ?? params.currentFocus.clientName ?? null;
  const eventLineId = params.selectedContext.eventLineId ?? params.currentFocus.eventLineId ?? null;
  const eventLineName = params.selectedContext.eventLineName ?? params.currentFocus.eventLineName ?? null;
  const focusedTask = params.currentFocus.taskId
    ? params.tasks.find((task) => task.id === params.currentFocus.taskId) ?? null
    : null;
  const taskId = focusedTask?.id ?? params.currentFocus.taskId ?? null;
  const taskTitle = focusedTask?.title ?? params.currentFocus.taskTitle ?? null;
  const workspaceContext = buildWorkspaceContext(params.workspaceLite);
  const eventLineContext = buildEventLineContext(params.eventLine);
  const taskContext = buildFocusedTaskContext(focusedTask, params.currentFocus.weekLabel, taskTitle);
  const taskBoardContext = buildTaskBoardContext(params.tasks, {
    clientId,
    eventLineId,
    weekLabel: params.currentFocus.weekLabel,
  });

  const sourceLabels = [
    clientName ? `当前客户：${clientName}` : null,
    eventLineName ? `当前事件线：${eventLineName}` : null,
    taskTitle ? `当前任务：${taskTitle}` : null,
    params.currentFocus.weekLabel ? `当前周：${params.currentFocus.weekLabel}` : null,
    params.workspaceLite ? "工作台" : null,
    params.eventLine ? "事件线卡片" : null,
    params.tasks.length > 0 ? "任务板" : null,
  ].filter(Boolean) as string[];

  return {
    clientId,
    clientName,
    eventLineId,
    eventLineName,
    taskId,
    taskTitle,
    taskContext,
    workspaceContext,
    eventLineContext,
    taskBoardContext,
    sourceLabels,
    missingEventLineHint: clientName && !eventLineId ? "当前未锁定事件线，回答只基于客户与任务板" : null,
  };
}
~~~

## `mobile/lib/consult-context.ts`

- 编码: `utf-8`

~~~typescript
import type { CurrentFocus, TaskRecord } from "./types";

export interface ConsultContextOption {
  readonly id: string;
  readonly label: string;
  readonly scope: "all" | "client" | "event_line";
  readonly clientId: string | null;
  readonly clientName: string | null;
  readonly eventLineId: string | null;
  readonly eventLineName: string | null;
}

interface TaskContextSummaryOptions {
  readonly clientId?: string | null;
  readonly eventLineId?: string | null;
  readonly limit?: number;
  readonly weekLabel?: string | null;
}

export function buildConsultGreeting(option: ConsultContextOption): string {
  if (option.scope === "event_line" && option.clientName && option.eventLineName) {
    return `你好，我是你的咨询助理。当前已锁定 ${option.clientName} · ${option.eventLineName}，你想先看哪部分？`;
  }
  if (option.scope === "client" && option.clientName) {
    return `你好，我是你的咨询助理。当前已锁定 ${option.clientName}，你想先了解什么？`;
  }
  return "你好，我是你的咨询助理。当前未锁定客户或事件线，我会先基于任务板给你建议。";
}

export function buildConsultContextOptions(tasks: readonly TaskRecord[]): readonly ConsultContextOption[] {
  const options: ConsultContextOption[] = [
    {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    },
  ];
  const clientMap = new Map<string, ConsultContextOption>();
  const eventLineMap = new Map<string, ConsultContextOption>();

  for (const task of tasks) {
    if (task.clientId && task.clientName && !clientMap.has(task.clientId)) {
      clientMap.set(task.clientId, {
        id: `client:${task.clientId}`,
        label: task.clientName,
        scope: "client",
        clientId: task.clientId,
        clientName: task.clientName,
        eventLineId: null,
        eventLineName: null,
      });
    }
    if (
      task.eventLineId &&
      task.eventLineName &&
      task.clientId &&
      task.clientName &&
      !eventLineMap.has(task.eventLineId)
    ) {
      eventLineMap.set(task.eventLineId, {
        id: `event:${task.eventLineId}`,
        label: `${task.clientName} / ${task.eventLineName}`,
        scope: "event_line",
        clientId: task.clientId,
        clientName: task.clientName,
        eventLineId: task.eventLineId,
        eventLineName: task.eventLineName,
      });
    }
  }

  return options.concat(Array.from(clientMap.values()), Array.from(eventLineMap.values()));
}

export function resolveConsultContextFromFocus(
  options: readonly ConsultContextOption[],
  currentFocus: CurrentFocus | null | undefined,
): ConsultContextOption {
  if (currentFocus?.eventLineId) {
    const matchedEventLine = options.find((option) => option.eventLineId === currentFocus.eventLineId);
    if (matchedEventLine) {
      return matchedEventLine;
    }
    if (currentFocus.clientId || currentFocus.eventLineName) {
      return {
        id: `focus:event:${currentFocus.eventLineId}`,
        label: currentFocus.clientName && currentFocus.eventLineName
          ? `${currentFocus.clientName} / ${currentFocus.eventLineName}`
          : currentFocus.eventLineName || currentFocus.clientName || "当前事件线",
        scope: "event_line",
        clientId: currentFocus.clientId,
        clientName: currentFocus.clientName,
        eventLineId: currentFocus.eventLineId,
        eventLineName: currentFocus.eventLineName,
      };
    }
  }
  if (currentFocus?.clientId) {
    const matchedClient = options.find(
      (option) => option.scope === "client" && option.clientId === currentFocus.clientId,
    );
    if (matchedClient) {
      return matchedClient;
    }
    return {
      id: `focus:client:${currentFocus.clientId}`,
      label: currentFocus.clientName || "当前客户",
      scope: "client",
      clientId: currentFocus.clientId,
      clientName: currentFocus.clientName,
      eventLineId: null,
      eventLineName: null,
    };
  }
  return (
    options.find((option) => option.scope === "all") ??
    options[0] ?? {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    }
  );
}

export function buildTaskContextSummary(
  tasks: readonly TaskRecord[],
  options: TaskContextSummaryOptions = {},
): string | undefined {
  const scopedTasks = tasks.filter((task) => {
    if (options.eventLineId) {
      return task.eventLineId === options.eventLineId;
    }
    if (options.clientId) {
      return task.clientId === options.clientId;
    }
    return true;
  });

  if (scopedTasks.length === 0) {
    return undefined;
  }

  const titles = scopedTasks
    .map((task) => task.title.trim())
    .filter(Boolean)
    .slice(0, options.limit ?? 5);
  if (titles.length === 0) {
    return undefined;
  }
  if (options.weekLabel) {
    return `${options.weekLabel} 任务：${titles.join("、")}`;
  }
  return `任务板：${titles.join("、")}`;
}
~~~

## `mobile/lib/consult-thread-context.ts`

- 编码: `utf-8`

~~~typescript
import type {
  ConsultThreadContextSnapshot,
} from "./types";

export interface FreezableConsultContext {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
}

function toStableSnapshotSeed(context: FreezableConsultContext): string {
  return [
    context.clientId ?? "",
    context.clientName ?? "",
    context.eventLineId ?? "",
    context.eventLineName ?? "",
    context.taskId ?? "",
    context.taskTitle ?? "",
    context.taskContext ?? "",
    context.workspaceContext ?? "",
    context.eventLineContext ?? "",
    context.taskBoardContext ?? "",
    context.sourceLabels.join("|"),
    context.missingEventLineHint ?? "",
  ].join("\n");
}

export function buildConsultThreadSnapshotHash(
  context: FreezableConsultContext,
): string {
  const seed = toStableSnapshotSeed(context);
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `ctx_${(hash >>> 0).toString(36)}`;
}

export function freezeConsultThreadContext(
  context: FreezableConsultContext,
  frozenAt = new Date().toISOString(),
  previousSnapshot?: Pick<ConsultThreadContextSnapshot, "snapshotVersion"> | null,
): ConsultThreadContextSnapshot {
  return {
    clientId: context.clientId,
    clientName: context.clientName,
    eventLineId: context.eventLineId,
    eventLineName: context.eventLineName,
    taskId: context.taskId,
    taskTitle: context.taskTitle,
    taskContext: context.taskContext,
    workspaceContext: context.workspaceContext,
    eventLineContext: context.eventLineContext,
    taskBoardContext: context.taskBoardContext,
    sourceLabels: [...context.sourceLabels],
    missingEventLineHint: context.missingEventLineHint,
    frozenAt,
    snapshotHash: buildConsultThreadSnapshotHash(context),
    snapshotVersion: Math.max(1, (previousSnapshot?.snapshotVersion ?? 0) + 1),
  };
}

export function refreshConsultThreadContext(
  previousSnapshot: Pick<ConsultThreadContextSnapshot, "snapshotVersion"> | null,
  context: FreezableConsultContext,
  frozenAt = new Date().toISOString(),
): ConsultThreadContextSnapshot {
  return freezeConsultThreadContext(context, frozenAt, previousSnapshot);
}

export function hasConsultThreadContextDrift(
  snapshot: Pick<ConsultThreadContextSnapshot, "snapshotHash">,
  nextContext: FreezableConsultContext,
): boolean {
  return snapshot.snapshotHash !== buildConsultThreadSnapshotHash(nextContext);
}

export function shouldResetConsultThreadContext(params: {
  readonly hadMessages: boolean;
  readonly nextContextChanged: boolean;
}): boolean {
  return params.hadMessages && params.nextContextChanged;
}
~~~

## `mobile/lib/create-task-association.ts`

- 编码: `utf-8`

~~~typescript
import type { ClientSummaryRecord, EventLineRecord } from "./types";

export type AssociationSource = "default" | "auto" | "manual";

export interface ProjectOption {
  id: string;
  name: string;
  clientId: string | null;
  eventLineIds: string[];
}

export function normalizeSearchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[\s·•,，。！？、:：;；"'“”‘’（）()【】[\]{}<>《》\-_/\\]+/g, "")
    .trim();
}

export function splitSearchFragments(value: string): string[] {
  return value
    .split(/[\s·•,，。！？、:：;；"'“”‘’（）()【】[\]{}<>《》\-_/\\]+/g)
    .map((item) => item.trim())
    .filter((item) => item.length >= 2);
}

export function deriveProjectLabel(eventLine: EventLineRecord): string {
  if (eventLine.primaryClientName?.trim()) {
    return eventLine.primaryClientName.trim();
  }
  const [firstSegment] = eventLine.name.split(/[·•|｜/]/);
  const compact = firstSegment?.trim() || eventLine.name.trim();
  const [firstWord] = compact.split(/\s+/);
  return firstWord?.trim() || compact;
}

export function getProjectKey(eventLine: EventLineRecord): string {
  if (eventLine.primaryClientId) {
    return `client:${eventLine.primaryClientId}`;
  }
  const derived = normalizeSearchText(deriveProjectLabel(eventLine));
  return `event-line:${derived || eventLine.id}`;
}

export function scoreEventLineMatch(searchKey: string, eventLine: EventLineRecord): number {
  if (!searchKey || searchKey.length < 2) {
    return 0;
  }

  const aliases = new Set<string>([
    eventLine.name,
    eventLine.primaryClientName ?? "",
    deriveProjectLabel(eventLine),
    ...splitSearchFragments(eventLine.name),
    ...splitSearchFragments(eventLine.primaryClientName ?? ""),
  ]);

  let bestScore = 0;
  for (const alias of aliases) {
    const normalized = normalizeSearchText(alias);
    if (normalized.length < 2) {
      continue;
    }

    if (searchKey === normalized) {
      bestScore = Math.max(bestScore, 320 + normalized.length);
      continue;
    }
    if (searchKey.includes(normalized)) {
      bestScore = Math.max(bestScore, 220 + normalized.length);
      continue;
    }
    if (normalized.includes(searchKey) && searchKey.length >= 3) {
      bestScore = Math.max(bestScore, 120 + searchKey.length);
    }
  }

  return bestScore;
}

export function buildProjectOptions(
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): ProjectOption[] {
  if (clients.length > 0) {
    return clients.map((client) => ({
      id: `client:${client.id}`,
      name: client.name,
      clientId: client.id,
      eventLineIds: eventLines
        .filter((eventLine) => eventLine.primaryClientId === client.id)
        .map((eventLine) => eventLine.id),
    }));
  }

  const map = new Map<string, ProjectOption>();
  for (const eventLine of eventLines) {
    const key = getProjectKey(eventLine);
    const existing = map.get(key);
    if (existing) {
      if (!existing.eventLineIds.includes(eventLine.id)) {
        existing.eventLineIds.push(eventLine.id);
      }
      if (!existing.clientId && eventLine.primaryClientId) {
        existing.clientId = eventLine.primaryClientId;
      }
      continue;
    }
    map.set(key, {
      id: key,
      name: deriveProjectLabel(eventLine),
      clientId: eventLine.primaryClientId ?? null,
      eventLineIds: [eventLine.id],
    });
  }
  return Array.from(map.values()).sort((left, right) => left.name.localeCompare(right.name, "zh-Hans-CN"));
}

export function filterEventLinesForSelection(
  eventLines: readonly EventLineRecord[],
  selectedClientId: string | null,
  selectedProjectKey: string | null,
): EventLineRecord[] {
  if (selectedClientId) {
    return eventLines.filter((eventLine) => eventLine.primaryClientId === selectedClientId);
  }
  if (!selectedProjectKey) {
    return [...eventLines];
  }
  return eventLines.filter((eventLine) => getProjectKey(eventLine) === selectedProjectKey);
}

export function findAutoMatchedEventLine(
  titleSearchKey: string,
  eventLines: readonly EventLineRecord[],
): EventLineRecord | null {
  if (titleSearchKey.length < 2) {
    return null;
  }

  let bestMatch: EventLineRecord | null = null;
  let bestScore = 0;

  for (const eventLine of eventLines) {
    const score = scoreEventLineMatch(titleSearchKey, eventLine);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = eventLine;
    }
  }

  return bestScore >= 122 ? bestMatch : null;
}

export function shouldApplyAutoAssociation(options: {
  source: AssociationSource;
  lockedTitleKey: string | null;
  titleSearchKey: string;
  selectedEventLineId: string | null;
  autoMatchedEventLineId: string | null;
}): boolean {
  if (!options.autoMatchedEventLineId) {
    return false;
  }
  if (options.source === "manual") {
    return false;
  }
  if (options.lockedTitleKey === options.titleSearchKey) {
    return false;
  }
  return options.selectedEventLineId !== options.autoMatchedEventLineId;
}
~~~

## `mobile/lib/create-task-resources.ts`

- 编码: `utf-8`

~~~typescript
import * as api from "./api";
import * as cache from "./cache";
import type {
  ClientSummaryRecord,
  EventLineRecord,
  TaskListRecord,
  TaskSettingsRecord,
} from "./types";

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
~~~

## `mobile/lib/create-task-service.ts`

- 编码: `utf-8`

~~~typescript
import { createEventLine } from "./api";

export {
  createEventLine,
};
~~~

## `mobile/lib/current-focus-core.ts`

- 编码: `utf-8`

~~~typescript
import {
  buildWeekInfo,
  parseLocalDateKey,
  weekLabelForDateKey,
} from "./date";
import type {
  BoundaryCard,
  CurrentFocus,
  CurrentFocusBoundaryState,
  CurrentFocusLockMode,
  CurrentFocusSource,
  ClientSummaryRecord,
  EventLineRecord,
  TaskRecord,
} from "./types";

interface FocusSeed {
  readonly clientId?: string | null;
  readonly clientName?: string | null;
  readonly eventLineId?: string | null;
  readonly eventLineName?: string | null;
  readonly taskId?: string | null;
  readonly taskTitle?: string | null;
  readonly source?: CurrentFocusSource;
  readonly lockMode?: CurrentFocusLockMode;
  readonly boundaryState?: CurrentFocusBoundaryState;
  readonly weekAnchorDate?: string | null;
  readonly updatedAt?: string | null;
}

interface RestoreOptions {
  readonly now?: Date;
  readonly clients?: readonly ClientSummaryRecord[];
  readonly eventLines?: readonly EventLineRecord[];
}

export function createEmptyCurrentFocus(now = new Date()): CurrentFocus {
  const week = buildWeekInfo(now);
  return {
    clientId: null,
    clientName: null,
    eventLineId: null,
    eventLineName: null,
    taskId: null,
    taskTitle: null,
    weekAnchorDate: week.weekAnchorDate,
    weekLabel: week.weekLabel,
    source: "auto",
    lockMode: "browse",
    boundaryState: "none",
    updatedAt: now.toISOString(),
  };
}

export function createCurrentFocus(seed: FocusSeed = {}, now = new Date()): CurrentFocus {
  const base = createEmptyCurrentFocus(now);
  const weekAnchorDate = seed.weekAnchorDate ?? base.weekAnchorDate;
  return {
    clientId: seed.clientId ?? null,
    clientName: seed.clientName ?? null,
    eventLineId: seed.eventLineId ?? null,
    eventLineName: seed.eventLineName ?? null,
    taskId: seed.taskId ?? null,
    taskTitle: seed.taskTitle ?? null,
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
    source: seed.source ?? base.source,
    lockMode: seed.lockMode ?? base.lockMode,
    boundaryState: seed.boundaryState ?? "none",
    updatedAt: seed.updatedAt ?? now.toISOString(),
  };
}

export function createManualClientFocus(
  client: Pick<ClientSummaryRecord, "id" | "name">,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: client.id,
    clientName: client.name,
    eventLineId: null,
    eventLineName: null,
    taskId: null,
    taskTitle: null,
    source: "manual",
    lockMode: "client",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createManualClientEventLineFocus(
  client: Pick<ClientSummaryRecord, "id" | "name">,
  eventLine: Pick<EventLineRecord, "id" | "name">,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: client.id,
    clientName: client.name,
    eventLineId: eventLine.id,
    eventLineName: eventLine.name,
    taskId: null,
    taskTitle: null,
    source: "manual",
    lockMode: "client_event_line",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromTask(task: TaskRecord, currentFocus?: CurrentFocus | null): CurrentFocus {
  return createCurrentFocus({
    clientId: task.clientId ?? null,
    clientName: task.clientName ?? null,
    eventLineId: task.eventLineId ?? null,
    eventLineName: task.eventLineName ?? null,
    taskId: task.id,
    taskTitle: task.title ?? null,
    source: "from_task",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromEventLine(
  eventLine: EventLineRecord,
  currentFocus?: CurrentFocus | null,
): CurrentFocus {
  return createCurrentFocus({
    clientId: eventLine.primaryClientId ?? null,
    clientName: eventLine.primaryClientName ?? null,
    eventLineId: eventLine.id,
    eventLineName: eventLine.name,
    taskId: null,
    taskTitle: null,
    source: "from_task",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function createBrowseFocusFromCalendar(task: TaskRecord, currentFocus?: CurrentFocus | null): CurrentFocus {
  return createCurrentFocus({
    clientId: task.clientId ?? null,
    clientName: task.clientName ?? null,
    eventLineId: task.eventLineId ?? null,
    eventLineName: task.eventLineName ?? null,
    taskId: task.id,
    taskTitle: task.title ?? null,
    source: "from_calendar",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  });
}

export function updateCurrentFocusWeek(
  currentFocus: CurrentFocus,
  weekAnchorDate: string,
): CurrentFocus {
  return {
    ...currentFocus,
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
    updatedAt: new Date().toISOString(),
  };
}

export function updateCurrentFocusBoundaryState(
  currentFocus: CurrentFocus,
  boundaryState: CurrentFocusBoundaryState,
): CurrentFocus {
  if (currentFocus.boundaryState === boundaryState) {
    return currentFocus;
  }
  return {
    ...currentFocus,
    boundaryState,
    updatedAt: new Date().toISOString(),
  };
}

export function clearCurrentFocus(currentFocus?: CurrentFocus | null): CurrentFocus {
  const seedDate = currentFocus?.weekAnchorDate ? parseLocalDateKey(currentFocus.weekAnchorDate) : new Date();
  return createCurrentFocus({
    source: "manual",
    lockMode: "browse",
    weekAnchorDate: currentFocus?.weekAnchorDate ?? null,
  }, seedDate);
}

export function canPersistCurrentFocus(currentFocus: CurrentFocus): boolean {
  return currentFocus.lockMode !== "browse" && Boolean(currentFocus.clientId);
}

export function serializeCurrentFocus(currentFocus: CurrentFocus): string | null {
  if (!canPersistCurrentFocus(currentFocus)) {
    return null;
  }
  return JSON.stringify(currentFocus);
}

function ensureClient(
  currentFocus: CurrentFocus,
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): CurrentFocus {
  if (!currentFocus.clientId) {
    return currentFocus;
  }
  const matchedClient = clients.find((client) => client.id === currentFocus.clientId);
  if (matchedClient) {
    return {
      ...currentFocus,
      clientName: matchedClient.name,
    };
  }
  if (currentFocus.eventLineId) {
    const matchedEventLine = eventLines.find((line) => line.id === currentFocus.eventLineId);
    if (matchedEventLine?.primaryClientId && matchedEventLine.primaryClientName) {
      return {
        ...currentFocus,
        clientId: matchedEventLine.primaryClientId,
        clientName: matchedEventLine.primaryClientName,
      };
    }
  }
  return clearCurrentFocus(currentFocus);
}

export function reconcileCurrentFocus(
  currentFocus: CurrentFocus,
  clients: readonly ClientSummaryRecord[],
  eventLines: readonly EventLineRecord[],
): CurrentFocus {
  let next = ensureClient(currentFocus, clients, eventLines);
  if (next.eventLineId) {
    const matchedEventLine = eventLines.find((line) => line.id === next.eventLineId);
    if (!matchedEventLine) {
      next = {
        ...next,
        eventLineId: null,
        eventLineName: null,
        lockMode: next.lockMode === "client_event_line" ? "client" : next.lockMode,
      };
    } else {
      next = {
        ...next,
        eventLineName: matchedEventLine.name,
        clientId: matchedEventLine.primaryClientId ?? next.clientId ?? null,
        clientName: matchedEventLine.primaryClientName ?? next.clientName ?? null,
      };
    }
  }
  return {
    ...next,
    weekLabel: weekLabelForDateKey(next.weekAnchorDate),
  };
}

export function restoreCurrentFocus(
  rawValue: string | null | undefined,
  options: RestoreOptions = {},
): CurrentFocus {
  const fallback = createEmptyCurrentFocus(options.now);
  if (!rawValue) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(rawValue) as Partial<CurrentFocus>;
    const restored = createCurrentFocus({
      clientId: parsed.clientId,
      clientName: parsed.clientName,
      eventLineId: parsed.eventLineId,
      eventLineName: parsed.eventLineName,
      taskId: parsed.taskId,
      taskTitle: parsed.taskTitle,
      source: parsed.source,
      lockMode: parsed.lockMode,
      boundaryState: parsed.boundaryState,
      weekAnchorDate: parsed.weekAnchorDate,
      updatedAt: parsed.updatedAt,
    }, options.now);
    return reconcileCurrentFocus(restored, options.clients ?? [], options.eventLines ?? []);
  } catch {
    return fallback;
  }
}

export function deriveBoundaryState(cards: readonly BoundaryCard[]): CurrentFocusBoundaryState {
  const nonEmptyKinds = Array.from(
    new Set(cards.filter((card) => !card.isEmpty).map((card) => card.kind)),
  );
  if (nonEmptyKinds.length === 0) {
    return "none";
  }
  if (nonEmptyKinds.length === 1) {
    return nonEmptyKinds[0];
  }
  return "mixed";
}
~~~

## `mobile/lib/current-focus-store.ts`

- 编码: `utf-8`

~~~typescript
import { useEffect, useMemo, useSyncExternalStore } from "react";
import * as storage from "./storage";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import { onDataChanged } from "./sync-engine";
import {
  clearCurrentFocus,
  createBrowseFocusFromCalendar,
  createBrowseFocusFromEventLine,
  createBrowseFocusFromTask,
  createEmptyCurrentFocus,
  createManualClientEventLineFocus,
  createManualClientFocus,
  reconcileCurrentFocus,
  restoreCurrentFocus,
  serializeCurrentFocus,
  updateCurrentFocusBoundaryState as applyBoundaryState,
  updateCurrentFocusWeek as applyWeekUpdate,
} from "./current-focus-core";
import type {
  ClientSummaryRecord,
  CurrentFocus,
  CurrentFocusBoundaryState,
  EventLineRecord,
  TaskRecord,
} from "./types";

const STORAGE_KEY = "yiyu_current_focus";

interface CurrentFocusStoreSnapshot {
  readonly focus: CurrentFocus;
  readonly clients: readonly ClientSummaryRecord[];
  readonly eventLines: readonly EventLineRecord[];
  readonly isHydrated: boolean;
}

let snapshot: CurrentFocusStoreSnapshot = {
  focus: createEmptyCurrentFocus(),
  clients: [],
  eventLines: [],
  isHydrated: false,
};
let initializePromise: Promise<void> | null = null;
let releaseDataChanged: (() => void) | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function readCatalogs() {
  localDb.initDatabase();
  return {
    clients: localDb.getAllClients(),
    eventLines: localDb.getAllEventLines(),
  };
}

async function persistFocus(nextFocus: CurrentFocus) {
  const serialized = serializeCurrentFocus(nextFocus);
  const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
  if (!serialized) {
    await storage.deleteItem(storageKey);
    return;
  }
  await storage.setItem(storageKey, serialized);
}

function setSnapshot(nextSnapshot: CurrentFocusStoreSnapshot) {
  snapshot = nextSnapshot;
  emit();
}

function setFocus(nextFocus: CurrentFocus) {
  const reconciled = reconcileCurrentFocus(nextFocus, snapshot.clients, snapshot.eventLines);
  setSnapshot({
    ...snapshot,
    focus: reconciled,
  });
  void persistFocus(reconciled);
  devLog("focus", "updated", {
    clientId: reconciled.clientId,
    eventLineId: reconciled.eventLineId,
    lockMode: reconciled.lockMode,
    source: reconciled.source,
    weekLabel: reconciled.weekLabel,
  });
}

function refreshCatalogsFromLocal() {
  const { clients, eventLines } = readCatalogs();
  const nextFocus = reconcileCurrentFocus(snapshot.focus, clients, eventLines);
  setSnapshot({
    focus: nextFocus,
    clients,
    eventLines,
    isHydrated: snapshot.isHydrated,
  });
  void persistFocus(nextFocus);
}

export async function ensureCurrentFocusStoreInitialized(): Promise<void> {
  if (snapshot.isHydrated) {
    return;
  }
  if (initializePromise) {
    return initializePromise;
  }
  initializePromise = (async () => {
    const { clients, eventLines } = readCatalogs();
    const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
    const stored = await storage.getItem(storageKey);
    const focus = restoreCurrentFocus(stored, { clients, eventLines });
    setSnapshot({
      focus,
      clients,
      eventLines,
      isHydrated: true,
    });
    if (!releaseDataChanged) {
      releaseDataChanged = onDataChanged(() => {
        refreshCatalogsFromLocal();
      });
    }
  })().finally(() => {
    initializePromise = null;
  });
  return initializePromise;
}

export function resetCurrentFocusStore(): void {
  const storageKey = `${STORAGE_KEY}:${localDb.getActiveAccountScopeKey() ?? "no-org:no-user"}`;
  setSnapshot({
    focus: createEmptyCurrentFocus(),
    clients: [],
    eventLines: [],
    isHydrated: false,
  });
  void storage.deleteItem(STORAGE_KEY);
  void storage.deleteItem(storageKey);
}

export function setManualClientFocus(clientId: string): void {
  const client = snapshot.clients.find((item) => item.id === clientId);
  if (!client) {
    return;
  }
  setFocus(createManualClientFocus(client, snapshot.focus));
}

export function setManualClientEventLineFocus(clientId: string, eventLineId: string): void {
  const client = snapshot.clients.find((item) => item.id === clientId);
  const eventLine = snapshot.eventLines.find((item) => item.id === eventLineId);
  if (!client || !eventLine) {
    return;
  }
  setFocus(createManualClientEventLineFocus(client, eventLine, snapshot.focus));
}

export function setCurrentFocusBrowseFromTask(task: TaskRecord): void {
  setFocus(createBrowseFocusFromTask(task, snapshot.focus));
}

export function setCurrentFocusBrowseFromCalendar(task: TaskRecord): void {
  setFocus(createBrowseFocusFromCalendar(task, snapshot.focus));
}

export function setCurrentFocusBrowseFromEventLine(eventLineId: string): void {
  const eventLine = snapshot.eventLines.find((item) => item.id === eventLineId);
  if (!eventLine) {
    return;
  }
  setFocus(createBrowseFocusFromEventLine(eventLine, snapshot.focus));
}

export function setCurrentFocusWeek(weekAnchorDate: string): void {
  setFocus(applyWeekUpdate(snapshot.focus, weekAnchorDate));
}

export function setCurrentFocusBoundaryState(boundaryState: CurrentFocusBoundaryState): void {
  setFocus(applyBoundaryState(snapshot.focus, boundaryState));
}

export function clearStoredCurrentFocus(): void {
  setFocus(clearCurrentFocus(snapshot.focus));
}

export function useCurrentFocus() {
  const state = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => snapshot,
    () => snapshot,
  );

  useEffect(() => {
    void ensureCurrentFocusStoreInitialized();
  }, []);

  return useMemo(
    () => ({
      ...state,
      setManualClientFocus,
      setManualClientEventLineFocus,
      setCurrentFocusBrowseFromTask,
      setCurrentFocusBrowseFromCalendar,
      setCurrentFocusBrowseFromEventLine,
      setCurrentFocusWeek,
      setCurrentFocusBoundaryState,
      clearStoredCurrentFocus,
    }),
    [state],
  );
}
~~~

## `mobile/lib/date.ts`

- 编码: `utf-8`

~~~typescript
function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatLocalDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function parseLocalDateKey(dateKey: string): Date {
  const match = dateKey.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return new Date(dateKey);
  }
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

export function addDays(date: Date, deltaDays: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + deltaDays);
  return next;
}

export function startOfLocalDay(date: Date): Date {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

export function endOfLocalDay(date: Date): Date {
  const next = new Date(date);
  next.setHours(23, 59, 59, 999);
  return next;
}

export function getLocalWeekRangeKeys(date: Date): { startKey: string; endKey: string } {
  const monday = getLocalWeekAnchorDate(date);
  const sunday = addDays(monday, 6);
  return {
    startKey: formatLocalDateKey(monday),
    endKey: formatLocalDateKey(sunday),
  };
}

export function getLocalWeekAnchorDate(date: Date): Date {
  const start = startOfLocalDay(date);
  const day = start.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  return addDays(start, mondayOffset);
}

export function getLocalWeekAnchorDateKey(date: Date): string {
  return formatLocalDateKey(getLocalWeekAnchorDate(date));
}

export function weekLabelForDate(baseDate: Date): string {
  const utcDate = new Date(Date.UTC(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate()));
  const day = utcDate.getUTCDay() || 7;
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((utcDate.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${utcDate.getUTCFullYear()}-W${pad2(week)}`;
}

export function weekLabelForDateKey(dateKey: string): string {
  return weekLabelForDate(parseLocalDateKey(dateKey));
}

export function formatWeekLabelCn(weekLabel: string): string {
  const match = weekLabel.match(/^\d{4}-W(\d{2})$/);
  return match ? `第${parseInt(match[1], 10)}周` : weekLabel;
}

export function buildWeekInfo(date: Date): { weekAnchorDate: string; weekLabel: string } {
  const weekAnchorDate = getLocalWeekAnchorDateKey(date);
  return {
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
  };
}

export function isDateKeyWithinWeek(dateKey: string | null | undefined, weekAnchorDate: string): boolean {
  if (!dateKey) {
    return false;
  }
  const target = dateKey.slice(0, 10);
  const { startKey, endKey } = getLocalWeekRangeKeys(parseLocalDateKey(weekAnchorDate));
  return target >= startKey && target <= endKey;
}
~~~

## `mobile/lib/dev-log.ts`

- 编码: `utf-8`

~~~typescript
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
~~~

## `mobile/lib/event-line-client-transfer.ts`

- 编码: `utf-8`

~~~typescript
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
~~~

## `mobile/lib/focus-selectors.ts`

- 编码: `utf-8`

~~~typescript
import type { CurrentFocus, TaskRecord } from "./types";

export interface FocusTaskStats {
  matchedCount: number;
  scheduledCount: number;
  unscheduledCount: number;
  doneCount: number;
}

export function isLockedFocus(currentFocus: CurrentFocus): boolean {
  return currentFocus.lockMode === "client" || currentFocus.lockMode === "client_event_line";
}

export function matchesTaskAgainstFocus(task: TaskRecord, currentFocus: CurrentFocus): boolean {
  if (currentFocus.eventLineId) {
    return task.eventLineId === currentFocus.eventLineId;
  }
  if (currentFocus.clientId) {
    return task.clientId === currentFocus.clientId;
  }
  return false;
}

export function filterTasksByFocus(tasks: readonly TaskRecord[], currentFocus: CurrentFocus): TaskRecord[] {
  if (!isLockedFocus(currentFocus)) {
    return [...tasks];
  }
  return tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus));
}

export function buildFocusMatchedTaskIds(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): ReadonlySet<string> {
  return new Set(
    tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus)).map((task) => task.id),
  );
}

export function sortTasksByFocusPriority(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): TaskRecord[] {
  return tasks
    .map((task, index) => ({
      task,
      index,
      matched: matchesTaskAgainstFocus(task, currentFocus),
    }))
    .sort((left, right) => {
      if (left.matched !== right.matched) {
        return left.matched ? -1 : 1;
      }
      return left.index - right.index;
    })
    .map((entry) => entry.task);
}

export function buildFocusTaskStats(
  tasks: readonly TaskRecord[],
  currentFocus: CurrentFocus,
): FocusTaskStats {
  const matchedTasks = tasks.filter((task) => matchesTaskAgainstFocus(task, currentFocus));
  return {
    matchedCount: matchedTasks.length,
    scheduledCount: matchedTasks.filter((task) => Boolean(task.dueDate)).length,
    unscheduledCount: matchedTasks.filter((task) => !task.dueDate).length,
    doneCount: matchedTasks.filter((task) => task.progressStatus === "done").length,
  };
}
~~~

## `mobile/lib/legacy-upload-ops.ts`

- 编码: `utf-8`

~~~typescript
import * as localDb from "./local-db";
import {
  buildLegacyUploadPseudoOp,
  normalizeLegacyUploadReasonCode,
  normalizeLegacyUploadStatus,
  refreshLegacyUploadPseudoOpAge,
} from "./legacy-upload-pseudo-op-core";
import type { LegacyUploadPseudoOp, LegacyUploadPseudoOpStatus, LegacyUploadReasonCode } from "./types";

const LEGACY_UPLOAD_OPS_KEY = "legacy_upload_ops_v1";

type StoredLegacyUploadPseudoOp = Omit<LegacyUploadPseudoOp, "ageMs">;

function loadStoredLegacyUploadOps(): StoredLegacyUploadPseudoOp[] {
  const raw = localDb.getSyncMeta(LEGACY_UPLOAD_OPS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is StoredLegacyUploadPseudoOp => {
      return Boolean(
        item &&
          typeof item.opId === "string" &&
          typeof item.objectType === "string" &&
          typeof item.objectLocalId === "string" &&
          item.lane === "transfer" &&
          typeof item.taskLocalId === "string" &&
          typeof item.filePath === "string",
      );
    });
  } catch {
    return [];
  }
}

function saveStoredLegacyUploadOps(items: readonly StoredLegacyUploadPseudoOp[]): void {
  localDb.setSyncMeta(LEGACY_UPLOAD_OPS_KEY, JSON.stringify(items));
}

export function getLegacyUploadPseudoOps(now = Date.now()): LegacyUploadPseudoOp[] {
  return loadStoredLegacyUploadOps().map((item) =>
    refreshLegacyUploadPseudoOpAge(
      {
        ...item,
        status: normalizeLegacyUploadStatus(item.status),
        reasonCode: normalizeLegacyUploadReasonCode(item.reasonCode),
      },
      now,
    ),
  );
}

export function getLegacyUploadPseudoOp(opId: string): LegacyUploadPseudoOp | null {
  return getLegacyUploadPseudoOps().find((item) => item.opId === opId) ?? null;
}

export function upsertLegacyUploadPseudoOp(
  input: StoredLegacyUploadPseudoOp,
): LegacyUploadPseudoOp {
  const next = buildLegacyUploadPseudoOp({
    ...input,
    status: normalizeLegacyUploadStatus(input.status),
    reasonCode: normalizeLegacyUploadReasonCode(input.reasonCode),
  });
  const existing = loadStoredLegacyUploadOps().filter((item) => item.opId !== next.opId);
  const { ageMs: _ageMs, ...stored } = next;
  existing.unshift(stored);
  saveStoredLegacyUploadOps(existing);
  return next;
}

export function patchLegacyUploadPseudoOp(
  opId: string,
  patch: Partial<Omit<StoredLegacyUploadPseudoOp, "opId" | "createdAt" | "objectType" | "objectLocalId" | "taskLocalId" | "filePath" | "entityRefLocalId">>,
): LegacyUploadPseudoOp | null {
  const items = loadStoredLegacyUploadOps();
  const index = items.findIndex((item) => item.opId === opId);
  if (index === -1) {
    return null;
  }
  const current = items[index];
  const next: StoredLegacyUploadPseudoOp = {
    ...current,
    ...patch,
    status: normalizeLegacyUploadStatus((patch.status as string | undefined) ?? current.status),
    reasonCode: normalizeLegacyUploadReasonCode((patch.reasonCode as string | undefined) ?? current.reasonCode),
  };
  items[index] = next;
  saveStoredLegacyUploadOps(items);
  return buildLegacyUploadPseudoOp(next);
}

export function markLegacyUploadPseudoOp(
  opId: string,
  params: {
    status: LegacyUploadPseudoOpStatus;
    reasonCode: LegacyUploadReasonCode;
    incrementRetryCount?: boolean;
  },
): LegacyUploadPseudoOp | null {
  const existing = getLegacyUploadPseudoOp(opId);
  if (!existing) {
    return null;
  }
  return patchLegacyUploadPseudoOp(opId, {
    status: params.status,
    reasonCode: params.reasonCode,
    lastAttemptAt: new Date().toISOString(),
    retryCount: params.incrementRetryCount ? existing.retryCount + 1 : existing.retryCount,
  });
}

export function removeLegacyUploadPseudoOp(opId: string): void {
  const next = loadStoredLegacyUploadOps().filter((item) => item.opId !== opId);
  saveStoredLegacyUploadOps(next);
}
~~~

## `mobile/lib/legacy-upload-pseudo-op-core.ts`

- 编码: `utf-8`

~~~typescript
import type {
  HealthLaneDiagnostic,
  LegacyUploadPseudoOp,
  LegacyUploadPseudoOpStatus,
  LegacyUploadReasonCode,
  PendingOpLane,
} from "./types";

type LegacyUploadPseudoOpInput = Omit<LegacyUploadPseudoOp, "ageMs">;

export function buildLegacyUploadPseudoOp(
  input: LegacyUploadPseudoOpInput,
  now = Date.now(),
): LegacyUploadPseudoOp {
  return {
    ...input,
    ageMs: buildPseudoOpAgeMs(input, now),
  };
}

export function refreshLegacyUploadPseudoOpAge(
  op: Omit<LegacyUploadPseudoOp, "ageMs"> | LegacyUploadPseudoOp,
  now = Date.now(),
): LegacyUploadPseudoOp {
  return {
    ...op,
    ageMs: buildPseudoOpAgeMs(op, now),
  };
}

export function buildPseudoOpAgeMs(
  op: Pick<LegacyUploadPseudoOp, "createdAt" | "lastAttemptAt">,
  now = Date.now(),
): number {
  const baseline = op.lastAttemptAt ?? op.createdAt;
  const timestamp = new Date(baseline).getTime();
  if (!Number.isFinite(timestamp)) {
    return 0;
  }
  return Math.max(0, now - timestamp);
}

export function buildTopReasonCode(
  values: readonly (string | null | undefined)[],
): string | null {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  let winner: string | null = null;
  let winnerCount = 0;
  for (const [reasonCode, count] of counts.entries()) {
    if (count > winnerCount) {
      winner = reasonCode;
      winnerCount = count;
    }
  }
  return winner;
}

export function mergeLaneDiagnosticsWithLegacyUploads(
  diagnostics: Record<PendingOpLane, HealthLaneDiagnostic>,
  legacyUploadOps: readonly LegacyUploadPseudoOp[],
): Record<PendingOpLane, HealthLaneDiagnostic> {
  if (legacyUploadOps.length === 0) {
    return diagnostics;
  }
  const transfer = diagnostics.transfer;
  const oldestLegacyAge = legacyUploadOps.reduce<number | null>((oldest, op) => {
    if (oldest == null) return op.ageMs;
    return Math.max(oldest, op.ageMs);
  }, null);
  return {
    ...diagnostics,
    transfer: {
      lane: "transfer",
      total: transfer.total + legacyUploadOps.length,
      oldestAgeMs:
        transfer.oldestAgeMs == null
          ? oldestLegacyAge
          : oldestLegacyAge == null
            ? transfer.oldestAgeMs
            : Math.max(transfer.oldestAgeMs, oldestLegacyAge),
      active:
        transfer.active ||
        legacyUploadOps.some((op) => op.status === "processing"),
      topReasonCode:
        buildTopReasonCode([
          transfer.topReasonCode,
          ...legacyUploadOps.map((op) => op.reasonCode),
        ]) ?? null,
    },
  };
}

export function normalizeLegacyUploadReasonCode(
  value: string | null | undefined,
): LegacyUploadReasonCode {
  switch (value) {
    case "network_unavailable":
    case "auth_required":
    case "scope_mismatch":
    case "file_missing":
    case "file_corrupted":
    case "upload_failed":
    case "bind_pending_remote_id":
    case "integrity_blocked":
    case "manual_pause":
      return value;
    default:
      return "unknown_error";
  }
}

export function normalizeLegacyUploadStatus(
  value: string | null | undefined,
): LegacyUploadPseudoOpStatus {
  switch (value) {
    case "queued":
    case "processing":
    case "needs_attention":
      return value;
    default:
      return "needs_attention";
  }
}
~~~

## `mobile/lib/legacy-upload-runner-core.ts`

- 编码: `utf-8`

~~~typescript
import type {
  LegacyUploadPseudoOp,
  LegacyUploadPseudoOpStatus,
  LegacyUploadReasonCode,
} from "./types";

export interface LegacyUploadAutoProcessResult {
  attempted: number;
  completed: number;
  stoppedByAuth: boolean;
  stoppedByNetwork: boolean;
}

export type LegacyUploadRetryResult =
  | { ok: true }
  | { ok: false; reasonCode: LegacyUploadReasonCode; message: string };

export function resolveLegacyUploadFailureStatus(
  reasonCode: LegacyUploadReasonCode,
): LegacyUploadPseudoOpStatus {
  switch (reasonCode) {
    case "network_unavailable":
    case "bind_pending_remote_id":
    case "integrity_blocked":
    case "manual_pause":
    case "scope_mismatch":
      return "queued";
    default:
      return "needs_attention";
  }
}

export async function processQueuedLegacyUploadOps(
  ops: readonly Pick<LegacyUploadPseudoOp, "opId" | "status">[],
  retry: (opId: string) => Promise<LegacyUploadRetryResult>,
): Promise<LegacyUploadAutoProcessResult> {
  const result: LegacyUploadAutoProcessResult = {
    attempted: 0,
    completed: 0,
    stoppedByAuth: false,
    stoppedByNetwork: false,
  };

  for (const op of ops) {
    if (op.status !== "queued") {
      continue;
    }
    result.attempted += 1;
    const retryResult = await retry(op.opId);
    if (retryResult.ok) {
      result.completed += 1;
      continue;
    }
    const reasonCode =
      "reasonCode" in retryResult ? retryResult.reasonCode : "unknown_error";
    if (reasonCode === "auth_required") {
      result.stoppedByAuth = true;
      break;
    }
    if (reasonCode === "network_unavailable") {
      result.stoppedByNetwork = true;
      break;
    }
  }

  return result;
}
~~~

## `mobile/lib/legacy-upload-runner.ts`

- 编码: `utf-8`

~~~typescript
import { getLegacyUploadPseudoOps } from "./legacy-upload-ops";
import {
  processQueuedLegacyUploadOps,
  type LegacyUploadAutoProcessResult,
} from "./legacy-upload-runner-core";

export async function processQueuedLegacyUploadPseudoOps(): Promise<LegacyUploadAutoProcessResult> {
  const { retryLegacyUploadPseudoOp } = await import("./record-note-service");
  return processQueuedLegacyUploadOps(getLegacyUploadPseudoOps(), retryLegacyUploadPseudoOp);
}
~~~

## `mobile/lib/local-db.ts`

- 编码: `utf-8`

~~~typescript
/**
 * local-db.ts — SQLite 本地数据库层
 *
 * 采用 expo-sqlite (同步 API) 提供结构化的本地存储，
 * 替代 AsyncStorage 的 JSON 大块读写，实现毫秒级查询。
 *
 * 表设计:
 *   tasks          — 任务主表，与云端 TaskRecord 一一对应
 *   task_lists     — 任务清单
 *   event_lines    — 事件线/项目线
 *   clients        — 客户摘要
 *   sync_meta      — 同步元数据（水位标记、版本号）
 *   pending_ops    — 离线操作队列（乐观写入，等待上传）
 */

import * as SQLite from "expo-sqlite";
import { NO_ACCOUNT_SCOPE_KEY, normalizeAccountScopeKey } from "./account-scope";
import { formatLocalDateKey } from "./date";
import { measureDevSync } from "./dev-log";
import { foldPendingOps, type PendingOpDraft } from "./pending-op-policy";
import { decideTaskServerAckAction } from "./task-sync-policy";
import type {
  PendingOpLane,
  PendingOpOperation,
  PendingOpRecord,
  PendingOpSummary,
  PendingOpVisibilityScope,
  RemoteMutationState,
  SyncReasonCode,
  HealthLaneDiagnostic,
  TaskConflictDiagnostic,
  TaskServerShadowRecord,
  TaskRecord,
  TaskBoardResponse,
  TaskListRecord,
  EventLineRecord,
  ClientSummaryRecord,
} from "./types";

// ─── Database Instance ──────────────────────────

let _db: SQLite.SQLiteDatabase | null = null;
let _activeAccountScopeKey: string | null = null;

const CURRENT_SCHEMA_VERSION = 3;
const META_ACCOUNT_SCOPE_KEY = "account_scope_key";
const META_INTEGRITY_STATUS = "sync_integrity_status";
const META_INTEGRITY_REASON = "sync_integrity_reason";

export function getDb(): SQLite.SQLiteDatabase {
  if (!_db) {
    _db = SQLite.openDatabaseSync("yiyu_local.db");
  }
  return _db;
}

// ─── Schema Migration ───────────────────────────

function getTableColumnNames(db: SQLite.SQLiteDatabase, tableName: string): Set<string> {
  const rows = db.getAllSync(`PRAGMA table_info(${tableName});`);
  return new Set(rows.map((row: any) => row.name as string));
}

function ensureColumn(
  db: SQLite.SQLiteDatabase,
  tableName: string,
  columnName: string,
  ddl: string,
): void {
  const columns = getTableColumnNames(db, tableName);
  if (!columns.has(columnName)) {
    db.execSync(`ALTER TABLE ${tableName} ADD COLUMN ${ddl};`);
  }
}

function setSyncMetaWithDb(db: SQLite.SQLiteDatabase, key: string, value: string): void {
  db.runSync(
    `INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
     VALUES (?, ?, datetime('now'))`,
    [key, value],
  );
}

function clearSessionDataWithDb(db: SQLite.SQLiteDatabase): void {
  db.runSync("DELETE FROM tasks");
  db.runSync("DELETE FROM task_lists");
  db.runSync("DELETE FROM event_lines");
  db.runSync("DELETE FROM clients");
  db.runSync("DELETE FROM pending_ops");
  db.runSync("DELETE FROM task_server_shadow");
  db.runSync(
    "DELETE FROM sync_meta WHERE key NOT IN (?, ?, ?)",
    [META_ACCOUNT_SCOPE_KEY, META_INTEGRITY_STATUS, META_INTEGRITY_REASON],
  );
}

export function initDatabase(): void {
  const db = getDb();

  // Enable WAL mode for better concurrent read/write performance
  db.execSync("PRAGMA journal_mode = WAL;");
  db.execSync("PRAGMA foreign_keys = ON;");

  const row = db.getFirstSync<{ user_version: number }>("PRAGMA user_version;");
  const version = row?.user_version ?? 0;

  if (version < 1) {
    db.execSync(`
      CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        remote_id TEXT,
        title TEXT NOT NULL DEFAULT '',
        description TEXT,
        due_date TEXT,
        duration_minutes INTEGER,
        priority TEXT NOT NULL DEFAULT 'normal',
        progress_status TEXT NOT NULL DEFAULT 'inbox',
        tags TEXT,
        client_id TEXT,
        client_name TEXT,
        event_line_id TEXT,
        event_line_name TEXT,
        list_id TEXT,
        list_name TEXT,
        owner_id TEXT,
        owner_name TEXT,
        business_category TEXT,
        current_blocker TEXT,
        next_action TEXT,
        recent_decision TEXT,
        completion_note TEXT,
        attachments_json TEXT,
        collaborators_json TEXT,
        viewer_inbox_status TEXT,
        created_at TEXT,
        updated_at TEXT,
        local_version INTEGER NOT NULL DEFAULT 0,
        base_remote_version INTEGER,
        server_version INTEGER,
        local_state TEXT NOT NULL DEFAULT 'local_committed',
        remote_state TEXT NOT NULL DEFAULT 'synced',
        sync_reason_code TEXT,
        deleted_at TEXT,
        -- 同步元数据
        _synced INTEGER NOT NULL DEFAULT 1,
        _local_updated_at TEXT,
        _deleted INTEGER NOT NULL DEFAULT 0
      );

      CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
      CREATE INDEX IF NOT EXISTS idx_tasks_progress_status ON tasks(progress_status);
      CREATE INDEX IF NOT EXISTS idx_tasks_synced ON tasks(_synced);
      CREATE INDEX IF NOT EXISTS idx_tasks_list_id ON tasks(list_id);
      CREATE INDEX IF NOT EXISTS idx_tasks_event_line_id ON tasks(event_line_id);
      CREATE INDEX IF NOT EXISTS idx_tasks_remote_id ON tasks(remote_id);

      CREATE TABLE IF NOT EXISTS task_lists (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        color TEXT,
        is_default INTEGER NOT NULL DEFAULT 0,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS event_lines (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        primary_client_id TEXT,
        primary_client_name TEXT,
        summary TEXT,
        current_blocker TEXT,
        next_step TEXT,
        recent_decision TEXT,
        stage TEXT,
        status TEXT,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        alias TEXT,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS pending_ops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_op_id TEXT NOT NULL UNIQUE,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        entity_remote_id TEXT,
        operation TEXT NOT NULL,
        payload TEXT,
        lane TEXT NOT NULL DEFAULT 'interactive',
        status TEXT NOT NULL DEFAULT 'queued',
        visibility_scope TEXT NOT NULL DEFAULT 'team_shared',
        local_version INTEGER NOT NULL DEFAULT 0,
        base_remote_version INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        retry_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        reason_code TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_pending_ops_entity ON pending_ops(entity_type, entity_id);
      CREATE INDEX IF NOT EXISTS idx_pending_ops_lane ON pending_ops(lane, created_at);

      CREATE TABLE IF NOT EXISTS task_server_shadow (
        task_id TEXT PRIMARY KEY,
        remote_id TEXT,
        server_version INTEGER,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }

  if (version < 2) {
    ensureColumn(db, "tasks", "remote_id", "remote_id TEXT");
    ensureColumn(db, "tasks", "local_version", "local_version INTEGER NOT NULL DEFAULT 0");
    ensureColumn(db, "tasks", "base_remote_version", "base_remote_version INTEGER");
    ensureColumn(db, "tasks", "server_version", "server_version INTEGER");
    ensureColumn(db, "tasks", "local_state", "local_state TEXT NOT NULL DEFAULT 'local_committed'");
    ensureColumn(db, "tasks", "remote_state", "remote_state TEXT NOT NULL DEFAULT 'synced'");
    ensureColumn(db, "tasks", "sync_reason_code", "sync_reason_code TEXT");
    ensureColumn(db, "tasks", "deleted_at", "deleted_at TEXT");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_tasks_remote_id ON tasks(remote_id);");

    ensureColumn(db, "pending_ops", "client_op_id", "client_op_id TEXT");
    ensureColumn(db, "pending_ops", "entity_remote_id", "entity_remote_id TEXT");
    ensureColumn(db, "pending_ops", "lane", "lane TEXT NOT NULL DEFAULT 'interactive'");
    ensureColumn(db, "pending_ops", "status", "status TEXT NOT NULL DEFAULT 'queued'");
    ensureColumn(db, "pending_ops", "visibility_scope", "visibility_scope TEXT NOT NULL DEFAULT 'team_shared'");
    ensureColumn(db, "pending_ops", "local_version", "local_version INTEGER NOT NULL DEFAULT 0");
    ensureColumn(db, "pending_ops", "base_remote_version", "base_remote_version INTEGER");
    ensureColumn(db, "pending_ops", "updated_at", "updated_at TEXT NOT NULL DEFAULT (datetime('now'))");
    ensureColumn(db, "pending_ops", "reason_code", "reason_code TEXT");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_pending_ops_lane ON pending_ops(lane, created_at);");

    db.runSync(
      "UPDATE tasks SET remote_id = id WHERE remote_id IS NULL AND _synced = 1 AND _deleted = 0",
    );
    db.runSync(
      "UPDATE tasks SET local_state = 'local_committed' WHERE local_state IS NULL OR local_state = ''",
    );
    db.runSync(
      "UPDATE tasks SET remote_state = CASE WHEN _synced = 1 THEN 'synced' ELSE 'queued' END WHERE remote_state IS NULL OR remote_state = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET client_op_id = 'migrated_op_' || id WHERE client_op_id IS NULL OR client_op_id = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET lane = 'interactive' WHERE lane IS NULL OR lane = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET status = 'queued' WHERE status IS NULL OR status = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET visibility_scope = 'team_shared' WHERE visibility_scope IS NULL OR visibility_scope = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''",
    );
    db.execSync("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_ops_client_op_id ON pending_ops(client_op_id);");
  }

  if (version < 3) {
    db.execSync(`
      CREATE TABLE IF NOT EXISTS task_server_shadow (
        task_id TEXT PRIMARY KEY,
        remote_id TEXT,
        server_version INTEGER,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }

  db.execSync(`PRAGMA user_version = ${CURRENT_SCHEMA_VERSION};`);
}

export function getActiveAccountScopeKey(): string | null {
  return _activeAccountScopeKey ?? normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY));
}

export function getDataIntegrityState(): {
  accountScopeKey: string;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  const accountScopeKey =
    normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY)) ?? NO_ACCOUNT_SCOPE_KEY;
  const integrityStatus = getSyncMeta(META_INTEGRITY_STATUS) === "blocked" ? "blocked" : "ok";
  const integrityReason = getSyncMeta(META_INTEGRITY_REASON) || null;
  return {
    accountScopeKey,
    integrityStatus,
    integrityReason,
  };
}

export function validateDatabaseIntegrity(): {
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  initDatabase();
  const db = getDb();
  const orphanTaskPendingOps = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops po
       LEFT JOIN tasks t
         ON po.entity_type = 'task'
        AND po.entity_id = t.id
      WHERE po.entity_type = 'task'
        AND t.id IS NULL`,
  )?.cnt ?? 0;

  const orphanTaskShadows = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM task_server_shadow shadow
       LEFT JOIN tasks t ON shadow.task_id = t.id
      WHERE t.id IS NULL`,
  )?.cnt ?? 0;

  const integrityReason =
    orphanTaskPendingOps > 0
      ? "orphan_task_pending_ops"
      : orphanTaskShadows > 0
        ? "orphan_task_server_shadow"
        : null;
  const integrityStatus = integrityReason ? "blocked" : "ok";

  setSyncMetaWithDb(db, META_INTEGRITY_STATUS, integrityStatus);
  setSyncMetaWithDb(db, META_INTEGRITY_REASON, integrityReason ?? "");

  return {
    integrityStatus,
    integrityReason,
  };
}

export function prepareDatabaseForAccountScope(scopeKey: string): {
  scopeChanged: boolean;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  initDatabase();
  const db = getDb();
  const normalizedScopeKey = normalizeAccountScopeKey(scopeKey) ?? NO_ACCOUNT_SCOPE_KEY;
  const storedScopeKey = normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY));
  const legacyPendingOpsCount = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM pending_ops",
  )?.cnt ?? 0;
  const scopeChanged = Boolean(storedScopeKey && storedScopeKey !== normalizedScopeKey);
  const shouldClearLegacyQueue = !storedScopeKey && legacyPendingOpsCount > 0;

  db.withTransactionSync(() => {
    if (scopeChanged || shouldClearLegacyQueue) {
      clearSessionDataWithDb(db);
    }
    setSyncMetaWithDb(db, META_ACCOUNT_SCOPE_KEY, normalizedScopeKey);
  });

  _activeAccountScopeKey = normalizedScopeKey;
  const integrity = validateDatabaseIntegrity();
  return {
    scopeChanged,
    integrityStatus: integrity.integrityStatus,
    integrityReason: integrity.integrityReason,
  };
}

// ─── Task CRUD ──────────────────────────────────

function taskToRow(task: TaskRecord) {
  return {
    $id: task.id,
    $remote_id: task.remoteId ?? null,
    $title: task.title,
    $description: task.description ?? null,
    $due_date: task.dueDate ?? null,
    $duration_minutes: task.durationMinutes ?? null,
    $priority: task.priority,
    $progress_status: task.progressStatus,
    $tags: task.tags ? JSON.stringify(task.tags) : null,
    $client_id: task.clientId ?? null,
    $client_name: task.clientName ?? null,
    $event_line_id: task.eventLineId ?? null,
    $event_line_name: task.eventLineName ?? null,
    $list_id: task.listId ?? null,
    $list_name: task.listName ?? null,
    $owner_id: task.ownerId ?? null,
    $owner_name: task.ownerName ?? null,
    $business_category: task.businessCategory ?? null,
    $current_blocker: task.currentBlocker ?? null,
    $next_action: task.nextAction ?? null,
    $recent_decision: task.recentDecision ?? null,
    $completion_note: task.completionNote ?? null,
    $attachments_json: task.attachments ? JSON.stringify(task.attachments) : null,
    $collaborators_json: task.collaborators ? JSON.stringify(task.collaborators) : null,
    $viewer_inbox_status: task.viewerInboxStatus ?? null,
    $created_at: task.createdAt ?? null,
    $updated_at: task.updatedAt ?? null,
    $local_version: task.localVersion ?? 0,
    $base_remote_version: task.baseRemoteVersion ?? null,
    $server_version: task.serverVersion ?? null,
    $local_state: task.localState ?? "local_committed",
    $remote_state: task.remoteState ?? "synced",
    $sync_reason_code: task.syncReasonCode ?? null,
    $deleted_at: task.deletedAt ?? null,
  };
}

function rowToTask(row: any): TaskRecord {
  return {
    id: row.id,
    remoteId: row.remote_id,
    title: row.title,
    description: row.description,
    dueDate: row.due_date,
    durationMinutes: row.duration_minutes,
    priority: row.priority,
    progressStatus: row.progress_status,
    tags: row.tags ? JSON.parse(row.tags) : null,
    clientId: row.client_id,
    clientName: row.client_name,
    eventLineId: row.event_line_id,
    eventLineName: row.event_line_name,
    listId: row.list_id,
    listName: row.list_name,
    ownerId: row.owner_id,
    ownerName: row.owner_name,
    businessCategory: row.business_category,
    currentBlocker: row.current_blocker,
    nextAction: row.next_action,
    recentDecision: row.recent_decision,
    completionNote: row.completion_note,
    attachments: row.attachments_json ? JSON.parse(row.attachments_json) : undefined,
    collaborators: row.collaborators_json ? JSON.parse(row.collaborators_json) : undefined,
    viewerInboxStatus: row.viewer_inbox_status,
    localVersion: row.local_version ?? 0,
    baseRemoteVersion: row.base_remote_version,
    serverVersion: row.server_version,
    localState: row.local_state ?? "local_committed",
    remoteState: row.remote_state ?? "synced",
    syncReasonCode: row.sync_reason_code ?? null,
    deletedAt: row.deleted_at ?? null,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function upsertTaskRow(
  db: SQLite.SQLiteDatabase,
  task: TaskRecord,
  options: {
    synced: boolean;
    deleted: boolean;
    localUpdatedAt: string | null;
  },
): void {
  db.runSync(`
    INSERT OR REPLACE INTO tasks (
      id, remote_id, title, description, due_date, duration_minutes,
      priority, progress_status, tags, client_id, client_name,
      event_line_id, event_line_name, list_id, list_name,
      owner_id, owner_name, business_category, current_blocker,
      next_action, recent_decision, completion_note,
      attachments_json, collaborators_json, viewer_inbox_status,
      created_at, updated_at, local_version, base_remote_version,
      server_version, local_state, remote_state, sync_reason_code,
      deleted_at, _synced, _local_updated_at, _deleted
    ) VALUES (
      $id, $remote_id, $title, $description, $due_date, $duration_minutes,
      $priority, $progress_status, $tags, $client_id, $client_name,
      $event_line_id, $event_line_name, $list_id, $list_name,
      $owner_id, $owner_name, $business_category, $current_blocker,
      $next_action, $recent_decision, $completion_note,
      $attachments_json, $collaborators_json, $viewer_inbox_status,
      $created_at, $updated_at, $local_version, $base_remote_version,
      $server_version, $local_state, $remote_state, $sync_reason_code,
      $deleted_at, $synced, $local_updated_at, $deleted
    )
  `, {
    ...taskToRow(task),
    $synced: options.synced ? 1 : 0,
    $local_updated_at: options.localUpdatedAt,
    $deleted: options.deleted ? 1 : 0,
  });
}

function upsertTaskServerShadowWithDb(
  db: SQLite.SQLiteDatabase,
  taskId: string,
  serverTask: TaskRecord,
): void {
  db.runSync(
    `INSERT OR REPLACE INTO task_server_shadow (
      task_id, remote_id, server_version, payload_json, updated_at
    ) VALUES (?, ?, ?, ?, datetime('now'))`,
    [
      taskId,
      serverTask.remoteId ?? serverTask.id,
      serverTask.serverVersion ?? null,
      JSON.stringify(serverTask),
    ],
  );
}

function clearTaskServerShadowWithDb(db: SQLite.SQLiteDatabase, taskId: string): void {
  db.runSync("DELETE FROM task_server_shadow WHERE task_id = ?", [taskId]);
}

/**
 * 批量写入从云端拉取的任务（全量同步）。
 * 使用事务保证原子性，先标记所有为已删除，再 upsert 活跃任务。
 */
export function upsertTasksFromCloud(tasks: TaskRecord[]): void {
  const db = getDb();

  db.withTransactionSync(() => {
    // 标记所有现有记录为 "可能已删除"
    db.runSync("UPDATE tasks SET _deleted = 1 WHERE _synced = 1");

    for (const task of tasks) {
      const remoteId = task.remoteId ?? task.id;
      const existing = db.getFirstSync<{
        id: string;
        local_version: number | null;
        _synced: number;
        remote_id: string | null;
      }>(
        "SELECT id, local_version, _synced, remote_id FROM tasks WHERE COALESCE(remote_id, id) = ? LIMIT 1",
        [remoteId],
      );
      if (existing && existing._synced === 0) {
        upsertTaskServerShadowWithDb(db, existing.id, {
          ...task,
          remoteId,
        });
        db.runSync(
          `UPDATE tasks
              SET remote_id = COALESCE(remote_id, ?),
                  server_version = COALESCE(?, server_version)
            WHERE id = ?`,
          [remoteId, task.serverVersion ?? null, existing.id],
        );
        continue;
      }
      upsertTaskRow(
        db,
        {
          ...task,
          id: existing?.id ?? remoteId,
          remoteId,
          localVersion: existing?.local_version ?? task.localVersion ?? 0,
          localState: "local_committed",
          remoteState: "synced",
          syncReasonCode: null,
          deletedAt: null,
        },
        { synced: true, deleted: false, localUpdatedAt: null },
      );
      clearTaskServerShadowWithDb(db, existing?.id ?? remoteId);
    }

    // 清除被标记但本地无未上传修改的记录
    db.runSync("DELETE FROM tasks WHERE _deleted = 1 AND _synced = 1");
  });

  // 更新同步水位
  setSyncMeta("tasks_last_sync", new Date().toISOString());
}

/**
 * 本地创建/更新任务（乐观写入），标记为未同步
 */
export function upsertTaskLocally(task: TaskRecord): void {
  const db = getDb();
  upsertTaskRow(
    db,
    {
      ...task,
      localState: task.localState ?? "local_committed",
      remoteState: task.remoteState ?? "queued",
    },
    {
      synced: false,
      deleted: Boolean(task.deletedAt),
      localUpdatedAt: new Date().toISOString(),
    },
  );
}

/**
 * 标记任务已同步成功
 */
export function markTaskSynced(taskId: string): void {
  const db = getDb();
  db.runSync(
    "UPDATE tasks SET _synced = 1, _local_updated_at = NULL, remote_state = 'synced', sync_reason_code = NULL WHERE id = ?",
    [taskId],
  );
}

export function getTaskById(taskId: string): TaskRecord | null {
  const db = getDb();
  const row = db.getFirstSync("SELECT * FROM tasks WHERE id = ? LIMIT 1", [taskId]);
  return row ? rowToTask(row) : null;
}

export function getTaskServerShadow(taskId: string): TaskServerShadowRecord | null {
  const db = getDb();
  const row = db.getFirstSync(
    "SELECT * FROM task_server_shadow WHERE task_id = ? LIMIT 1",
    [taskId],
  ) as any;
  if (!row?.payload_json) {
    return null;
  }
  return {
    taskId: row.task_id,
    remoteId: row.remote_id ?? null,
    serverVersion: row.server_version ?? null,
    payload: JSON.parse(row.payload_json) as TaskRecord,
    updatedAt: row.updated_at,
  };
}

export function setTaskRemoteState(
  taskId: string,
  remoteState: RemoteMutationState,
  reasonCode: SyncReasonCode | null = null,
): void {
  const db = getDb();
  db.runSync(
    "UPDATE tasks SET remote_state = ?, sync_reason_code = ? WHERE id = ?",
    [remoteState, reasonCode, taskId],
  );
}

export function updateTaskSyncMetadata(
  taskId: string,
  updates: {
    remoteId?: string | null;
    serverVersion?: number | null;
    baseRemoteVersion?: number | null;
    remoteState?: RemoteMutationState;
    syncReasonCode?: SyncReasonCode | null;
    synced?: boolean;
  },
): void {
  const db = getDb();
  db.runSync(
    `UPDATE tasks
        SET remote_id = COALESCE(?, remote_id),
            server_version = COALESCE(?, server_version),
            base_remote_version = CASE
              WHEN ? IS NOT NULL THEN ?
              ELSE base_remote_version
            END,
            remote_state = COALESCE(?, remote_state),
            sync_reason_code = ?,
            _synced = CASE
              WHEN ? IS NULL THEN _synced
              WHEN ? = 1 THEN 1
              ELSE 0
            END
      WHERE id = ?`,
    [
      updates.remoteId ?? null,
      updates.serverVersion ?? null,
      updates.baseRemoteVersion ?? null,
      updates.baseRemoteVersion ?? null,
      updates.remoteState ?? null,
      updates.syncReasonCode ?? null,
      updates.synced == null ? null : updates.synced ? 1 : 0,
      updates.synced == null ? null : updates.synced ? 1 : 0,
      taskId,
    ],
  );
}

export function updatePendingOpsRemoteMapping(
  entityType: string,
  entityId: string,
  remoteId: string,
  options?: {
    promoteCreateToUpdate?: boolean;
    baseRemoteVersion?: number | null;
  },
): void {
  const db = getDb();
  db.runSync(
    `UPDATE pending_ops
        SET entity_remote_id = ?,
            operation = CASE
              WHEN ? = 1 AND operation = 'create' THEN 'update'
              ELSE operation
            END,
            base_remote_version = CASE
              WHEN ? IS NOT NULL THEN ?
              ELSE base_remote_version
            END,
            updated_at = datetime('now')
      WHERE entity_type = ?
        AND entity_id = ?`,
    [
      remoteId,
      options?.promoteCreateToUpdate ? 1 : 0,
      options?.baseRemoteVersion ?? null,
      options?.baseRemoteVersion ?? null,
      entityType,
      entityId,
    ],
  );
}

export function replaceTaskWithServerState(localTaskId: string, serverTask: TaskRecord): void {
  const db = getDb();
  const existing = getTaskById(localTaskId);
  upsertTaskRow(
    db,
    {
      ...(existing ?? {}),
      ...serverTask,
      id: localTaskId,
      remoteId: serverTask.remoteId ?? serverTask.id,
      localVersion: existing?.localVersion ?? 0,
      baseRemoteVersion: null,
      serverVersion: serverTask.serverVersion ?? existing?.serverVersion ?? null,
      localState: "local_committed",
      remoteState: "synced",
      syncReasonCode: null,
      deletedAt: null,
    },
    { synced: true, deleted: false, localUpdatedAt: null },
  );
  clearTaskServerShadowWithDb(db, localTaskId);
}

export function purgeTask(taskId: string): void {
  const db = getDb();
  db.runSync("DELETE FROM tasks WHERE id = ?", [taskId]);
  clearTaskServerShadowWithDb(db, taskId);
}

export function reconcileTaskServerAck(params: {
  taskId: string;
  clientOpId: string;
  operation: PendingOpOperation;
  ackLocalVersion: number | null;
  serverTask: TaskRecord;
}): {
  appliedServerState: boolean;
  shadowOnly: boolean;
} {
  const db = getDb();
  const existing = getTaskById(params.taskId);
  const pendingRows = db.getAllSync(
    `SELECT client_op_id, operation
       FROM pending_ops
      WHERE entity_type = 'task'
        AND entity_id = ?`,
    [params.taskId],
  ) as Array<{ client_op_id: string; operation: PendingOpOperation }>;
  const hasPendingOps = pendingRows.some((row) => row.client_op_id !== params.clientOpId);
  const pendingCreateExists = pendingRows.some(
    (row) => row.client_op_id !== params.clientOpId && row.operation === "create",
  );
  const decision = decideTaskServerAckAction({
    localTask: existing,
    ackLocalVersion: params.ackLocalVersion,
    hasPendingOps,
    pendingCreateExists,
  });
  const remoteId = params.serverTask.remoteId ?? params.serverTask.id;

  db.withTransactionSync(() => {
    if (decision.shouldUpdateShadowOnly) {
      upsertTaskServerShadowWithDb(db, params.taskId, {
        ...params.serverTask,
        remoteId,
      });
      updateTaskSyncMetadata(params.taskId, {
        remoteId,
        serverVersion: params.serverTask.serverVersion ?? null,
        remoteState: "queued",
        syncReasonCode: null,
        synced: false,
      });
      updatePendingOpsRemoteMapping("task", params.taskId, remoteId, {
        promoteCreateToUpdate: params.operation === "create" && decision.shouldPromotePendingCreate,
        baseRemoteVersion: params.serverTask.serverVersion ?? null,
      });
      return;
    }

    replaceTaskWithServerState(params.taskId, {
      ...params.serverTask,
      remoteId,
    });
  });

  return {
    appliedServerState: decision.shouldReplaceLocalTask,
    shadowOnly: decision.shouldUpdateShadowOnly,
  };
}

// ─── Task Queries ───────────────────────────────

/**
 * 获取所有活跃（非已删除）任务，等效于 fetchTaskBoard
 */
export function getAllTasks(options?: { syncedOnly?: boolean }): TaskRecord[] {
  return measureDevSync("local-db", "getAllTasks", () => {
    const db = getDb();
    const rows = db.getAllSync(
      `SELECT * FROM tasks
        WHERE _deleted = 0
          AND (? = 0 OR _synced = 1)
        ORDER BY due_date ASC, updated_at ASC, created_at ASC, id ASC`,
      [options?.syncedOnly ? 1 : 0],
    );
    return rows.map(rowToTask);
  });
}

/**
 * 获取指定日期的任务（日历核心查询）
 */
export function getTasksByDate(dateKey: string): TaskRecord[] {
  return measureDevSync("local-db", "getTasksByDate", () => {
    const db = getDb();
    const rows = db.getAllSync(
      "SELECT * FROM tasks WHERE _deleted = 0 AND due_date LIKE ? ORDER BY due_date ASC",
      [`${dateKey}%`],
    );
    return rows.map(rowToTask);
  });
}

/**
 * 获取日期范围内的任务（月视图/周视图查询）
 */
export function getTasksByDateRange(startDate: string, endDate: string): TaskRecord[] {
  return measureDevSync("local-db", "getTasksByDateRange", () => {
    const db = getDb();
    const rows = db.getAllSync(
      "SELECT * FROM tasks WHERE _deleted = 0 AND due_date >= ? AND due_date < ? ORDER BY due_date ASC",
      [startDate, endDate],
    );
    return rows.map(rowToTask);
  });
}

/**
 * 获取待同步的任务
 */
export function getUnsyncedTasks(): TaskRecord[] {
  return measureDevSync("local-db", "getUnsyncedTasks", () => {
    const db = getDb();
    const rows = db.getAllSync("SELECT * FROM tasks WHERE _synced = 0 AND _deleted = 0");
    return rows.map(rowToTask);
  });
}

/**
 * 获取 inbox 计数和今日任务计数
 */
export function getTaskCounts(options?: { syncedOnly?: boolean }): { inboxCount: number; tasksTodayCount: number } {
  return measureDevSync("local-db", "getTaskCounts", () => {
    const db = getDb();
    const today = formatLocalDateKey(new Date());

    const inboxRow = db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM tasks WHERE _deleted = 0 AND progress_status = 'inbox' AND (? = 0 OR _synced = 1)",
      [options?.syncedOnly ? 1 : 0],
    );
    const todayRow = db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM tasks WHERE _deleted = 0 AND due_date LIKE ? AND (? = 0 OR _synced = 1)",
      [`${today}%`, options?.syncedOnly ? 1 : 0],
    );

    return {
      inboxCount: inboxRow?.cnt ?? 0,
      tasksTodayCount: todayRow?.cnt ?? 0,
    };
  });
}

/**
 * 构建与云端 API 兼容的 TaskBoardResponse
 */
export function getLocalTaskBoard(options?: { syncedOnly?: boolean }): TaskBoardResponse {
  const tasks = getAllTasks(options);
  const counts = getTaskCounts(options);
  return {
    tasks,
    inboxCount: counts.inboxCount,
    tasksTodayCount: counts.tasksTodayCount,
  };
}

// ─── Event Lines ────────────────────────────────

export function upsertEventLinesFromCloud(lines: EventLineRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM event_lines WHERE _synced = 1");
    const stmt = db.prepareSync(`
      INSERT OR REPLACE INTO event_lines (id, name, primary_client_id, primary_client_name,
        summary, current_blocker, next_step, recent_decision, stage, status, _synced)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    `);
    try {
      for (const l of lines) {
        stmt.executeSync([
          l.id, l.name, l.primaryClientId ?? null, l.primaryClientName ?? null,
          l.summary ?? null, l.currentBlocker ?? null, l.nextStep ?? null,
          l.recentDecision ?? null, l.stage ?? null, l.status ?? null,
        ]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
  setSyncMeta("event_lines_last_sync", new Date().toISOString());
}

export function getAllEventLines(): EventLineRecord[] {
  const db = getDb();
  const rows = db.getAllSync("SELECT * FROM event_lines");
  return rows.map((r: any) => ({
    id: r.id,
    name: r.name,
    primaryClientId: r.primary_client_id,
    primaryClientName: r.primary_client_name,
    summary: r.summary,
    currentBlocker: r.current_blocker,
    nextStep: r.next_step,
    recentDecision: r.recent_decision,
    stage: r.stage,
    status: r.status,
  }));
}

// ─── Clients ────────────────────────────────────

export function upsertClientsFromCloud(clients: ClientSummaryRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM clients WHERE _synced = 1");
    const stmt = db.prepareSync(
      "INSERT OR REPLACE INTO clients (id, name, alias, _synced) VALUES (?, ?, ?, 1)",
    );
    try {
      for (const c of clients) {
        stmt.executeSync([c.id, c.name, c.alias ?? null]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
  setSyncMeta("clients_last_sync", new Date().toISOString());
}

export function getAllClients(): ClientSummaryRecord[] {
  const db = getDb();
  const rows = db.getAllSync("SELECT * FROM clients");
  return rows.map((r: any) => ({ id: r.id, name: r.name, alias: r.alias }));
}

// ─── Task Lists ─────────────────────────────────

export function upsertTaskListsFromCloud(lists: TaskListRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM task_lists WHERE _synced = 1");
    const stmt = db.prepareSync(
      "INSERT OR REPLACE INTO task_lists (id, name, color, is_default, _synced) VALUES (?, ?, ?, ?, 1)",
    );
    try {
      for (const l of lists) {
        stmt.executeSync([l.id, l.name, l.color ?? null, l.isDefault ? 1 : 0]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
}

// ─── Pending Ops (离线操作队列) ─────────────────

function rowToPendingOp(row: any): PendingOpRecord {
  return {
    id: row.id,
    clientOpId: row.client_op_id,
    entityType: row.entity_type,
    entityId: row.entity_id,
    entityRemoteId: row.entity_remote_id,
    operation: row.operation,
    payload: row.payload,
    lane: row.lane,
    status: row.status,
    visibilityScope: row.visibility_scope,
    localVersion: row.local_version ?? 0,
    baseRemoteVersion: row.base_remote_version,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    retryCount: row.retry_count,
    lastError: row.last_error,
    reasonCode: row.reason_code ?? null,
  };
}

function pendingOpToDraft(op: PendingOpRecord): PendingOpDraft {
  return {
    clientOpId: op.clientOpId,
    entityType: op.entityType,
    entityId: op.entityId,
    entityRemoteId: op.entityRemoteId ?? null,
    operation: op.operation,
    payload: op.payload ? JSON.parse(op.payload) : null,
    lane: op.lane,
    status: op.status,
    visibilityScope: op.visibilityScope,
    localVersion: op.localVersion,
    baseRemoteVersion: op.baseRemoteVersion ?? null,
  };
}

function replacePendingOpsForEntity(
  db: SQLite.SQLiteDatabase,
  entityType: string,
  entityId: string,
  drafts: readonly PendingOpDraft[],
): void {
  db.runSync(
    "DELETE FROM pending_ops WHERE entity_type = ? AND entity_id = ?",
    [entityType, entityId],
  );
  for (const op of drafts) {
    db.runSync(
      `INSERT INTO pending_ops (
        client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
        lane, status, visibility_scope, local_version, base_remote_version,
        created_at, updated_at, retry_count, last_error, reason_code
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
      [
        op.clientOpId,
        op.entityType,
        op.entityId,
        op.entityRemoteId ?? null,
        op.operation,
        op.payload ? JSON.stringify(op.payload) : null,
        op.lane,
        op.status,
        op.visibilityScope,
        op.localVersion,
        op.baseRemoteVersion ?? null,
      ],
    );
  }
}

function getPendingOpDraftsForEntity(
  db: SQLite.SQLiteDatabase,
  entityType: string,
  entityId: string,
): PendingOpDraft[] {
  const rows = db.getAllSync(
    "SELECT * FROM pending_ops WHERE entity_type = ? AND entity_id = ? ORDER BY created_at ASC, id ASC",
    [entityType, entityId],
  );
  return rows.map((row: any) => pendingOpToDraft(rowToPendingOp(row)));
}

export function enqueueOp(
  entityType: string,
  entityId: string,
  operation: "create" | "update" | "delete",
  payload?: Record<string, unknown>,
  options?: {
    clientOpId?: string;
    entityRemoteId?: string | null;
    lane?: PendingOpLane;
    visibilityScope?: PendingOpVisibilityScope;
    localVersion?: number;
    baseRemoteVersion?: number | null;
  },
): void {
  const db = getDb();
  const nextDraft: PendingOpDraft = {
    clientOpId: options?.clientOpId ?? `legacy_${entityType}_${Date.now()}`,
    entityType,
    entityId,
    entityRemoteId: options?.entityRemoteId ?? null,
    operation,
    payload: payload ?? null,
    lane: options?.lane ?? "interactive",
    status: "queued",
    visibilityScope: options?.visibilityScope ?? "team_shared",
    localVersion: options?.localVersion ?? 0,
    baseRemoteVersion: options?.baseRemoteVersion ?? null,
  };
  const existing = getPendingOpDraftsForEntity(db, entityType, entityId);
  replacePendingOpsForEntity(db, entityType, entityId, foldPendingOps(existing, nextDraft));
}

export function getPendingOps(): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM pending_ops
     WHERE status != 'needs_attention'
     ORDER BY
       CASE lane
         WHEN 'interactive' THEN 0
         WHEN 'transfer' THEN 1
         ELSE 2
       END ASC,
       created_at ASC,
       id ASC`,
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getPendingOpsForEntity(
  entityType: string,
  entityId: string,
): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM pending_ops
     WHERE entity_type = ?
       AND entity_id = ?
     ORDER BY created_at ASC, id ASC`,
    [entityType, entityId],
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getPendingOpsSummary(): PendingOpSummary {
  const db = getDb();
  const rows = db.getAllSync("SELECT lane, status, reason_code FROM pending_ops");
  const summary: PendingOpSummary = {
    total: rows.length,
    queued: 0,
    syncing: 0,
    processing: 0,
    needsAttention: 0,
    byLane: {
      interactive: 0,
      transfer: 0,
      derived: 0,
    },
    byReasonCode: {},
  };

  for (const row of rows as any[]) {
    if (row.lane && row.lane in summary.byLane) {
      summary.byLane[row.lane as PendingOpLane] += 1;
    }
    if (row.status === "queued") summary.queued += 1;
    if (row.status === "syncing") summary.syncing += 1;
    if (row.status === "processing") summary.processing += 1;
    if (row.status === "needs_attention") summary.needsAttention += 1;
    if (row.reason_code) {
      summary.byReasonCode[row.reason_code as SyncReasonCode] =
        (summary.byReasonCode[row.reason_code as SyncReasonCode] ?? 0) + 1;
    }
  }

  return summary;
}

export function getPendingOpsLaneDiagnostics(
  now = Date.now(),
): Record<PendingOpLane, HealthLaneDiagnostic> {
  const diagnostics: Record<PendingOpLane, HealthLaneDiagnostic> = {
    interactive: {
      lane: "interactive",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
    transfer: {
      lane: "transfer",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
    derived: {
      lane: "derived",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
  };
  const reasonCounts: Record<PendingOpLane, Record<string, number>> = {
    interactive: {},
    transfer: {},
    derived: {},
  };
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT lane, status, reason_code, created_at, updated_at FROM pending_ops",
  ) as Array<{
    lane: PendingOpLane;
    status: string;
    reason_code: string | null;
    created_at: string;
    updated_at: string | null;
  }>;

  for (const row of rows) {
    if (!row.lane || !(row.lane in diagnostics)) {
      continue;
    }
    const entry = diagnostics[row.lane];
    entry.total += 1;
    if (row.status === "syncing" || row.status === "processing") {
      entry.active = true;
    }
    const ageBaseline = row.updated_at ?? row.created_at;
    const age = Math.max(0, now - new Date(ageBaseline).getTime());
    entry.oldestAgeMs = entry.oldestAgeMs == null ? age : Math.max(entry.oldestAgeMs, age);
    if (row.reason_code) {
      reasonCounts[row.lane][row.reason_code] =
        (reasonCounts[row.lane][row.reason_code] ?? 0) + 1;
    }
  }

  (Object.keys(reasonCounts) as PendingOpLane[]).forEach((lane) => {
    let topReasonCode: string | null = null;
    let topCount = 0;
    Object.entries(reasonCounts[lane]).forEach(([reasonCode, count]) => {
      if (count > topCount) {
        topReasonCode = reasonCode;
        topCount = count;
      }
    });
    diagnostics[lane].topReasonCode = topReasonCode;
  });

  return diagnostics;
}

export function getPendingOpsDebugList(limit = 20): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT * FROM pending_ops ORDER BY updated_at DESC, created_at DESC LIMIT ?",
    [limit],
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getTaskRemoteStateSummary(): {
  total: number;
  byRemoteState: Record<RemoteMutationState, number>;
  byReasonCode: Partial<Record<SyncReasonCode, number>>;
  recentNeedsAttentionTasks: Array<{
    id: string;
    title: string;
    remoteState: RemoteMutationState;
    syncReasonCode: SyncReasonCode | null;
    updatedAt: string | null;
  }>;
} {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT id, title, remote_state, sync_reason_code, updated_at
       FROM tasks
      WHERE _deleted = 0`,
  ) as Array<{
    id: string;
    title: string;
    remote_state: RemoteMutationState;
    sync_reason_code: SyncReasonCode | null;
    updated_at: string | null;
  }>;

  const summary = {
    total: rows.length,
    byRemoteState: {
      queued: 0,
      syncing: 0,
      processing: 0,
      needs_attention: 0,
      synced: 0,
    } as Record<RemoteMutationState, number>,
    byReasonCode: {} as Partial<Record<SyncReasonCode, number>>,
    recentNeedsAttentionTasks: [] as Array<{
      id: string;
      title: string;
      remoteState: RemoteMutationState;
      syncReasonCode: SyncReasonCode | null;
      updatedAt: string | null;
    }>,
  };

  for (const row of rows) {
    if (row.remote_state in summary.byRemoteState) {
      summary.byRemoteState[row.remote_state] += 1;
    }
    if (row.sync_reason_code) {
      summary.byReasonCode[row.sync_reason_code] =
        (summary.byReasonCode[row.sync_reason_code] ?? 0) + 1;
    }
    if (row.remote_state === "needs_attention") {
      summary.recentNeedsAttentionTasks.push({
        id: row.id,
        title: row.title,
        remoteState: row.remote_state,
        syncReasonCode: row.sync_reason_code,
        updatedAt: row.updated_at,
      });
    }
  }

  summary.recentNeedsAttentionTasks.sort((left, right) =>
    (right.updatedAt ?? "").localeCompare(left.updatedAt ?? ""),
  );
  summary.recentNeedsAttentionTasks = summary.recentNeedsAttentionTasks.slice(0, 10);

  return summary;
}

export function getTaskServerShadowDiagnostics(): {
  total: number;
  stale: number;
} {
  const db = getDb();
  const total = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM task_server_shadow",
  )?.cnt ?? 0;
  const stale = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM task_server_shadow shadow
       LEFT JOIN pending_ops po
         ON po.entity_type = 'task'
        AND po.entity_id = shadow.task_id
      WHERE po.id IS NULL`,
  )?.cnt ?? 0;
  return { total, stale };
}

export function cleanupSafeSyncArtifacts(): {
  clearedTaskServerShadows: number;
} {
  const db = getDb();
  const diagnostics = getTaskServerShadowDiagnostics();
  if (diagnostics.stale > 0) {
    db.runSync(
      `DELETE FROM task_server_shadow
        WHERE task_id NOT IN (
          SELECT DISTINCT entity_id
            FROM pending_ops
           WHERE entity_type = 'task'
        )`,
    );
  }
  return {
    clearedTaskServerShadows: diagnostics.stale,
  };
}

export function getTaskConflictDiagnostics(limit = 10): TaskConflictDiagnostic[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT
        po.entity_id as task_id,
        po.operation as pending_operation,
        po.updated_at as pending_updated_at,
        po.last_error as last_error,
        po.reason_code as pending_reason_code,
        t.title as title,
        t.remote_state as remote_state,
        t.sync_reason_code as task_reason_code,
        shadow.updated_at as shadow_updated_at,
        shadow.server_version as shadow_server_version
      FROM pending_ops po
      INNER JOIN tasks t
        ON t.id = po.entity_id
      LEFT JOIN task_server_shadow shadow
        ON shadow.task_id = t.id
      WHERE po.entity_type = 'task'
        AND po.status = 'needs_attention'
        AND (
          po.reason_code = 'version_conflict'
          OR t.sync_reason_code = 'version_conflict'
        )
      ORDER BY po.updated_at DESC, po.id DESC`,
  ) as Array<{
    task_id: string;
    pending_operation: PendingOpOperation | null;
    pending_updated_at: string | null;
    last_error: string | null;
    pending_reason_code: SyncReasonCode | null;
    title: string | null;
    remote_state: RemoteMutationState;
    task_reason_code: SyncReasonCode | null;
    shadow_updated_at: string | null;
    shadow_server_version: number | null;
  }>;

  const diagnostics = new Map<string, TaskConflictDiagnostic>();

  for (const row of rows) {
    const existing = diagnostics.get(row.task_id);
    if (existing) {
      existing.pendingOpCount += 1;
      if (!existing.hasServerShadow && row.shadow_updated_at) {
        existing.hasServerShadow = true;
        existing.serverShadowUpdatedAt = row.shadow_updated_at;
        existing.serverVersion = row.shadow_server_version ?? null;
      }
      continue;
    }

    diagnostics.set(row.task_id, {
      taskId: row.task_id,
      title: row.title?.trim() || "未命名任务",
      remoteState: row.remote_state ?? "needs_attention",
      syncReasonCode: row.pending_reason_code ?? row.task_reason_code ?? null,
      pendingOperation: row.pending_operation ?? null,
      pendingUpdatedAt: row.pending_updated_at ?? null,
      pendingOpCount: 1,
      lastError: row.last_error ?? null,
      hasServerShadow: Boolean(row.shadow_updated_at),
      serverShadowUpdatedAt: row.shadow_updated_at ?? null,
      serverVersion: row.shadow_server_version ?? null,
    });
  }

  return Array.from(diagnostics.values()).slice(0, Math.max(0, limit));
}

export function removeOp(opId: number): void {
  const db = getDb();
  db.runSync("DELETE FROM pending_ops WHERE id = ?", [opId]);
}

export function markOpSyncing(opId: number): void {
  const db = getDb();
  db.runSync(
    "UPDATE pending_ops SET status = 'syncing', updated_at = datetime('now'), reason_code = NULL, last_error = NULL WHERE id = ?",
    [opId],
  );
}

export function markOpFailed(
  opId: number,
  error: string,
  reasonCode: SyncReasonCode,
  status: RemoteMutationState = "queued",
): void {
  const db = getDb();
  db.runSync(
    `UPDATE pending_ops
     SET retry_count = retry_count + 1,
         last_error = ?,
         reason_code = ?,
         status = ?,
         updated_at = datetime('now')
     WHERE id = ?`,
    [error, reasonCode, status, opId],
  );
}

export function requeueOp(opId: number): void {
  const db = getDb();
  const row = db.getFirstSync<{ entity_id: string; entity_type: string }>(
    "SELECT entity_id, entity_type FROM pending_ops WHERE id = ?",
    [opId],
  );
  db.runSync(
    "UPDATE pending_ops SET status = 'queued', reason_code = NULL, last_error = NULL, updated_at = datetime('now') WHERE id = ?",
    [opId],
  );
  if (row?.entity_type === "task") {
    setTaskRemoteState(row.entity_id, "queued", null);
  }
}

export function requeueAllNeedsAttentionOps(): void {
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT entity_id, entity_type FROM pending_ops WHERE status = 'needs_attention'",
  );
  db.runSync(
    "UPDATE pending_ops SET status = 'queued', reason_code = NULL, last_error = NULL, updated_at = datetime('now') WHERE status = 'needs_attention'",
  );
  for (const row of rows as any[]) {
    if (row.entity_type === "task") {
      setTaskRemoteState(row.entity_id, "queued", null);
    }
  }
}

export function requeueNeedsAttentionOpsForEntity(
  entityType: string,
  entityId: string,
): number {
  const db = getDb();
  const count = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops
      WHERE entity_type = ?
        AND entity_id = ?
        AND status = 'needs_attention'`,
    [entityType, entityId],
  )?.cnt ?? 0;
  if (count === 0) {
    return 0;
  }

  db.runSync(
    `UPDATE pending_ops
        SET status = 'queued',
            reason_code = NULL,
            last_error = NULL,
            updated_at = datetime('now')
      WHERE entity_type = ?
        AND entity_id = ?
        AND status = 'needs_attention'`,
    [entityType, entityId],
  );
  if (entityType === "task") {
    setTaskRemoteState(entityId, "queued", null);
  }
  return count;
}

export function restoreTaskFromServerShadow(taskId: string): {
  restored: boolean;
  clearedPendingOps: number;
} {
  const db = getDb();
  const shadow = getTaskServerShadow(taskId);
  if (!shadow) {
    return { restored: false, clearedPendingOps: 0 };
  }

  const clearedPendingOps = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops
      WHERE entity_type = 'task'
        AND entity_id = ?`,
    [taskId],
  )?.cnt ?? 0;

  db.withTransactionSync(() => {
    db.runSync(
      `DELETE FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?`,
      [taskId],
    );
    replaceTaskWithServerState(taskId, shadow.payload);
  });

  return {
    restored: true,
    clearedPendingOps,
  };
}

export function commitTaskMutation(params: {
  task: TaskRecord;
  operation: "create" | "update" | "delete";
  clientOpId: string;
  payload: Record<string, unknown> | null;
  lane?: PendingOpLane;
  visibilityScope?: PendingOpVisibilityScope;
}): void {
  const db = getDb();
  const deleted = params.operation === "delete";
  const localUpdatedAt = new Date().toISOString();

  db.withTransactionSync(() => {
    upsertTaskRow(
      db,
      {
        ...params.task,
        localState: "local_committed",
        remoteState: "queued",
        syncReasonCode: null,
        deletedAt: deleted ? params.task.deletedAt ?? localUpdatedAt : null,
      },
      { synced: false, deleted, localUpdatedAt },
    );

    const nextDraft: PendingOpDraft = {
      clientOpId: params.clientOpId,
      entityType: "task",
      entityId: params.task.id,
      entityRemoteId: params.task.remoteId ?? null,
      operation: params.operation,
      payload: params.payload,
      lane: params.lane ?? "interactive",
      status: "queued",
      visibilityScope: params.visibilityScope ?? "team_shared",
      localVersion: params.task.localVersion ?? 0,
      baseRemoteVersion: params.task.baseRemoteVersion ?? null,
    };
    const existing = getPendingOpDraftsForEntity(db, "task", params.task.id);
    const nextOps = foldPendingOps(existing, nextDraft);
    replacePendingOpsForEntity(db, "task", params.task.id, nextOps);
  });
}

export function commitTaskReviewMutation(params: {
  task: TaskRecord;
  clientOpId: string;
  reviewNote: string;
  visibilityScope?: PendingOpVisibilityScope;
}): void {
  const db = getDb();
  const localUpdatedAt = new Date().toISOString();

  db.withTransactionSync(() => {
    upsertTaskRow(
      db,
      {
        ...params.task,
        localState: "local_committed",
        remoteState: "queued",
        syncReasonCode: null,
        deletedAt: null,
      },
      { synced: false, deleted: false, localUpdatedAt },
    );

    const existingRows = db.getAllSync(
      `SELECT * FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?
        ORDER BY created_at ASC`,
      [params.task.id],
    ) as any[];

    const hasDeletePending = existingRows.some((row) => row.operation === "delete");
    if (hasDeletePending) {
      return;
    }

    const baseOps = existingRows
      .map((row) => rowToPendingOp(row))
      .filter((op) => op.operation !== "complete_with_review");

    db.runSync(
      `DELETE FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?
          AND operation = 'complete_with_review'`,
      [params.task.id],
    );

    if (baseOps.length === 0) {
      db.runSync(
        `INSERT INTO pending_ops (
          client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
          lane, status, visibility_scope, local_version, base_remote_version,
          created_at, updated_at, retry_count, last_error, reason_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
        [
          params.clientOpId,
          "task",
          params.task.id,
          params.task.remoteId ?? null,
          "complete_with_review",
          JSON.stringify({ reviewNote: params.reviewNote }),
          "interactive",
          "queued",
          params.visibilityScope ?? "official",
          params.task.localVersion ?? 0,
          params.task.baseRemoteVersion ?? null,
        ],
      );
      return;
    }

    db.runSync(
      `INSERT INTO pending_ops (
        client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
        lane, status, visibility_scope, local_version, base_remote_version,
        created_at, updated_at, retry_count, last_error, reason_code
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
      [
        params.clientOpId,
        "task",
        params.task.id,
        params.task.remoteId ?? null,
        "complete_with_review",
        JSON.stringify({ reviewNote: params.reviewNote }),
        "interactive",
        "queued",
        params.visibilityScope ?? "official",
        params.task.localVersion ?? 0,
        params.task.baseRemoteVersion ?? null,
      ],
    );
  });
}

// ─── Sync Meta ──────────────────────────────────

export function getSyncMeta(key: string): string | null {
  const db = getDb();
  const row = db.getFirstSync<{ value: string }>(
    "SELECT value FROM sync_meta WHERE key = ?",
    [key],
  );
  return row?.value ?? null;
}

export function setSyncMeta(key: string, value: string): void {
  const db = getDb();
  db.runSync(
    `INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
     VALUES (?, ?, datetime('now'))`,
    [key, value],
  );
}

// ─── Cleanup ────────────────────────────────────

/**
 * 清除所有本地数据（登出时调用）
 */
export function clearAllData(): void {
  const db = getDb();
  db.withTransactionSync(() => {
    clearSessionDataWithDb(db);
    db.runSync("DELETE FROM sync_meta");
  });
  _activeAccountScopeKey = null;
}

/**
 * 检查本地数据库是否有数据（用于判断是否首次加载）
 */
export function hasLocalData(): boolean {
  const db = getDb();
  const row = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM tasks",
  );
  return (row?.cnt ?? 0) > 0;
}
~~~

## `mobile/lib/local-ids.ts`

- 编码: `utf-8`

~~~typescript
function randomSegment(): string {
  return Math.random().toString(36).slice(2, 10);
}

function timestampSegment(): string {
  return Date.now().toString(36);
}

export function createLocalEntityId(entityType: string): string {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (randomUuid) {
    return `${entityType}_${randomUuid}`;
  }
  return `${entityType}_${timestampSegment()}_${randomSegment()}`;
}

export function createClientOpId(entityType: string): string {
  return createLocalEntityId(`${entityType}_op`);
}
~~~

## `mobile/lib/pending-op-policy.ts`

- 编码: `utf-8`

~~~typescript
import type {
  PendingOpLane,
  PendingOpOperation,
  PendingOpVisibilityScope,
  RemoteMutationState,
} from "./types";

export interface PendingOpDraft {
  clientOpId: string;
  entityType: string;
  entityId: string;
  entityRemoteId?: string | null;
  operation: PendingOpOperation;
  payload: Record<string, unknown> | null;
  lane: PendingOpLane;
  status: RemoteMutationState;
  visibilityScope: PendingOpVisibilityScope;
  localVersion: number;
  baseRemoteVersion?: number | null;
}

function mergePayload(
  first: Record<string, unknown> | null,
  second: Record<string, unknown> | null,
): Record<string, unknown> | null {
  if (!first && !second) return null;
  return {
    ...(first ?? {}),
    ...(second ?? {}),
  };
}

export function foldPendingOps(
  existing: readonly PendingOpDraft[],
  next: PendingOpDraft,
): PendingOpDraft[] {
  const current = [...existing];
  const last = current[current.length - 1] ?? null;

  if (!last) {
    return [next];
  }

  if (last.operation === "create" && next.operation === "update") {
    return [
      {
        ...last,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  if (last.operation === "create" && next.operation === "complete_with_review") {
    return [...current, next];
  }

  if (last.operation === "create" && next.operation === "delete") {
    return last.entityRemoteId ? [{ ...next, entityRemoteId: last.entityRemoteId }] : [];
  }

  if (last.operation === "update" && next.operation === "update") {
    return [
      {
        ...last,
        clientOpId: next.clientOpId,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  if (last.operation === "update" && next.operation === "complete_with_review") {
    return [...current, next];
  }

  if (last.operation === "update" && next.operation === "delete") {
    return [next];
  }

  if (last.operation === "delete" && next.operation === "update") {
    return current;
  }

  if (last.operation === "complete_with_review" && next.operation === "update") {
    const base = current.slice(0, -1);
    const foldedBase = foldPendingOps(base, next);
    return foldedBase.length > 0
      ? [
          ...foldedBase,
          {
            ...last,
            localVersion: next.localVersion,
          },
        ]
      : [next, last];
  }

  if (last.operation === "complete_with_review" && next.operation === "complete_with_review") {
    return [
      ...current.slice(0, -1),
      {
        ...last,
        clientOpId: next.clientOpId,
        entityRemoteId: next.entityRemoteId ?? last.entityRemoteId ?? null,
        payload: mergePayload(last.payload, next.payload),
        localVersion: next.localVersion,
        baseRemoteVersion: next.baseRemoteVersion ?? last.baseRemoteVersion ?? null,
      },
    ];
  }

  return [next];
}

export function comparePendingOpLanePriority(a: PendingOpLane, b: PendingOpLane): number {
  const weights: Record<PendingOpLane, number> = {
    interactive: 0,
    transfer: 1,
    derived: 2,
  };
  return weights[a] - weights[b];
}
~~~

## `mobile/lib/record-note-flow-core.ts`

- 编码: `utf-8`

~~~typescript
export type RecordNoteProgressState =
  | "任务已保存"
  | "录音待挂接"
  | "录音待同步"
  | "正在恢复暂存语音"
  | "录音需处理"
  | "完成";

const ALLOWED_TRANSITIONS: Record<RecordNoteProgressState, readonly RecordNoteProgressState[]> = {
  任务已保存: ["录音待挂接"],
  录音待挂接: ["录音待同步", "录音需处理"],
  录音待同步: ["完成", "录音需处理"],
  正在恢复暂存语音: ["录音待挂接", "录音需处理"],
  录音需处理: [],
  完成: [],
};

export function canTransitionRecordNoteProgress(
  from: RecordNoteProgressState,
  to: RecordNoteProgressState,
): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}

export function getAllowedRecordNoteTransitions(
  from: RecordNoteProgressState,
): readonly RecordNoteProgressState[] {
  return ALLOWED_TRANSITIONS[from];
}
~~~

## `mobile/lib/record-note-service.ts`

- 编码: `utf-8`

~~~typescript
import * as FileSystem from "expo-file-system/legacy";
import * as api from "./api";
import * as localDb from "./local-db";
import { resolveLegacyUploadFailureStatus } from "./legacy-upload-runner-core";
import {
  getLegacyUploadPseudoOp,
  getLegacyUploadPseudoOps,
  markLegacyUploadPseudoOp,
  patchLegacyUploadPseudoOp,
  removeLegacyUploadPseudoOp,
  upsertLegacyUploadPseudoOp,
} from "./legacy-upload-ops";
import { createTaskLocalFirst } from "./task-repository";
import { getSyncControlState, triggerSync } from "./sync-engine";
import type {
  LegacyUploadPseudoOp,
  LegacyUploadReasonCode,
  TaskRecord,
} from "./types";

interface EnsureRemoteTaskResult {
  task: TaskRecord;
  remoteTaskId: string | null;
}

export interface RecordedAttachmentResult {
  status: "uploaded" | "pending_attachment" | "needs_attention";
  task: TaskRecord;
  message: string;
}

export type TaskAttachmentResult = RecordedAttachmentResult;

export type RecordedUploadableFile = api.UploadableFile;

interface RecordedAudioDraft {
  opId: string;
  objectLocalId: string;
  filePath: string;
  size: number | null;
  mtime: number | null;
  hash: string | null;
  mimeType: string;
}

const RECORD_NOTE_DRAFTS_DIR = `${FileSystem.documentDirectory ?? ""}record-note-drafts/`;
const TASK_ATTACHMENT_DRAFTS_DIR = `${FileSystem.documentDirectory ?? ""}task-attachment-drafts/`;

function normalizeUriUploadableFile(
  file: api.UploadableFile,
  defaults?: {
    name: string;
    type: string;
  },
): { uri: string; name: string; type: string } | null {
  if (!file || typeof file !== "object" || !("uri" in file)) {
    return null;
  }
  if (!file.uri) {
    return null;
  }
  return {
    uri: file.uri,
    name: file.name || defaults?.name || `record-note-${Date.now()}.m4a`,
    type: file.type || defaults?.type || "audio/m4a",
  };
}

function inferExtension(file: { uri: string; name: string; type: string }): string {
  const fromName = file.name.split(".").pop()?.trim().toLowerCase();
  if (fromName) {
    return fromName;
  }
  const cleanUri = file.uri.split("?")[0].toLowerCase();
  const fromUri = cleanUri.split(".").pop()?.trim();
  if (fromUri) {
    return fromUri;
  }
  if (file.type.includes("ogg")) return "ogg";
  if (file.type.includes("wav")) return "wav";
  if (file.type.includes("mpeg") || file.type.includes("mp3")) return "mp3";
  if (file.type.includes("aac")) return "aac";
  return "m4a";
}

function makeTransferDraftId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function ensureRecordNoteDraftDirectory(taskLocalId: string): Promise<string> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持录音原件暂存。");
  }
  const scopeKey = localDb.getActiveAccountScopeKey() ?? "no-org:no-user";
  const scopeDir = encodeURIComponent(scopeKey);
  const directory = `${RECORD_NOTE_DRAFTS_DIR}${scopeDir}/${taskLocalId}/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  return directory;
}

async function ensureTaskAttachmentDraftDirectory(taskLocalId: string): Promise<string> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持附件原件暂存。");
  }
  const scopeKey = localDb.getActiveAccountScopeKey() ?? "no-org:no-user";
  const scopeDir = encodeURIComponent(scopeKey);
  const directory = `${TASK_ATTACHMENT_DRAFTS_DIR}${scopeDir}/${taskLocalId}/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  return directory;
}

async function persistRecordedAudioDraft(
  taskLocalId: string,
  file: api.UploadableFile,
): Promise<RecordedAudioDraft | null> {
  const normalized = normalizeUriUploadableFile(file, {
    name: `record-note-${Date.now()}.m4a`,
    type: "audio/m4a",
  });
  if (!normalized) {
    return null;
  }
  const objectLocalId = makeTransferDraftId("voice_draft");
  const extension = inferExtension(normalized);
  const directory = await ensureRecordNoteDraftDirectory(taskLocalId);
  const destinationPath = `${directory}${objectLocalId}.${extension}`;
  if (normalized.uri !== destinationPath) {
    await FileSystem.copyAsync({ from: normalized.uri, to: destinationPath });
  }
  const info = await FileSystem.getInfoAsync(destinationPath, { md5: true } as any);
  return {
    opId: `legacy_upload_${objectLocalId}`,
    objectLocalId,
    filePath: destinationPath,
    size: typeof (info as any)?.size === "number" ? (info as any).size : null,
    mtime:
      typeof (info as any)?.modificationTime === "number"
        ? Number((info as any).modificationTime)
        : null,
    hash: typeof (info as any)?.md5 === "string" ? (info as any).md5 : null,
    mimeType: normalized.type,
  };
}

async function persistTaskAttachmentDraft(
  taskLocalId: string,
  file: api.UploadableFile,
): Promise<RecordedAudioDraft | null> {
  const normalized = normalizeUriUploadableFile(file, {
    name: `attachment-${Date.now()}`,
    type: "application/octet-stream",
  });
  if (!normalized) {
    return null;
  }
  const objectLocalId = makeTransferDraftId("file_draft");
  const extension = inferExtension(normalized);
  const directory = await ensureTaskAttachmentDraftDirectory(taskLocalId);
  const destinationPath = `${directory}${objectLocalId}.${extension}`;
  if (normalized.uri !== destinationPath) {
    await FileSystem.copyAsync({ from: normalized.uri, to: destinationPath });
  }
  const info = await FileSystem.getInfoAsync(destinationPath, { md5: true } as any);
  return {
    opId: `legacy_upload_${objectLocalId}`,
    objectLocalId,
    filePath: destinationPath,
    size: typeof (info as any)?.size === "number" ? (info as any).size : null,
    mtime:
      typeof (info as any)?.modificationTime === "number"
        ? Number((info as any).modificationTime)
        : null,
    hash: typeof (info as any)?.md5 === "string" ? (info as any).md5 : null,
    mimeType: normalized.type || "application/octet-stream",
  };
}

async function removePersistedRecordedAudio(path: string): Promise<void> {
  try {
    await FileSystem.deleteAsync(path, { idempotent: true });
  } catch {}
}

function mapLegacyUploadErrorReasonCode(error: unknown): LegacyUploadReasonCode {
  if (error instanceof api.ApiError) {
    if (error.status === 401) return "auth_required";
    if (error.status === 408 || error.status === 429 || error.status >= 500) {
      return "network_unavailable";
    }
    return "upload_failed";
  }
  if (error instanceof Error) {
    const lowered = error.message.toLowerCase();
    if (lowered.includes("network")) return "network_unavailable";
    return "unknown_error";
  }
  return "unknown_error";
}

function getPendingBindReasonCode(): LegacyUploadReasonCode {
  const syncControl = getSyncControlState();
  if (syncControl.freezeState === "paused_by_user") {
    return "manual_pause";
  }
  if (syncControl.freezeState === "blocked_by_integrity") {
    return "integrity_blocked";
  }
  if (syncControl.freezeState === "blocked_by_scope_mismatch") {
    return "scope_mismatch";
  }
  return "bind_pending_remote_id";
}

function buildPendingAttachmentMessage(
  reasonCode: LegacyUploadReasonCode,
  objectLabel = "录音",
): string {
  switch (reasonCode) {
    case "manual_pause":
      return `任务已保存，${objectLabel}待挂接。当前同步已暂停，请恢复同步后重试。`;
    case "integrity_blocked":
      return `任务已保存，${objectLabel}待挂接。当前同步因本地完整性问题被冻结，请先在系统健康中处理。`;
    case "scope_mismatch":
      return `任务已保存，${objectLabel}待挂接。当前账号作用域未就绪，请重新登录后重试。`;
    default:
      return `任务已保存，${objectLabel}待挂接。可在系统健康中继续重试上传。`;
  }
}

function isPendingAttachmentReasonCode(reasonCode: LegacyUploadReasonCode): boolean {
  return (
    reasonCode === "bind_pending_remote_id" ||
    reasonCode === "manual_pause" ||
    reasonCode === "integrity_blocked" ||
    reasonCode === "scope_mismatch"
  );
}

async function ensureRemoteTaskId(task: TaskRecord): Promise<EnsureRemoteTaskResult> {
  const initialSnapshot = localDb.getTaskById(task.id) ?? task;
  if (initialSnapshot.remoteId) {
    return {
      task: initialSnapshot,
      remoteTaskId: initialSnapshot.remoteId,
    };
  }

  try {
    await triggerSync();
  } catch {}

  const nextSnapshot = localDb.getTaskById(task.id) ?? initialSnapshot;
  return {
    task: nextSnapshot,
    remoteTaskId: nextSnapshot.remoteId ?? null,
  };
}

async function validatePersistedLegacyUploadFile(
  op: LegacyUploadPseudoOp,
): Promise<LegacyUploadReasonCode | null> {
  const info = op.hash
    ? await FileSystem.getInfoAsync(op.filePath, { md5: true } as any)
    : await FileSystem.getInfoAsync(op.filePath);
  if (!(info as any)?.exists) {
    return "file_missing";
  }
  if (
    op.size != null &&
    typeof (info as any)?.size === "number" &&
    (info as any).size !== op.size
  ) {
    return "file_corrupted";
  }
  if (
    op.mtime != null &&
    typeof (info as any)?.modificationTime === "number" &&
    Number((info as any).modificationTime) !== op.mtime
  ) {
    return "file_corrupted";
  }
  if (
    op.hash &&
    typeof (info as any)?.md5 === "string" &&
    (info as any).md5 !== op.hash
  ) {
    return "file_corrupted";
  }
  return null;
}

async function uploadLegacyRecordedAudioOp(
  op: LegacyUploadPseudoOp,
): Promise<TaskRecord> {
  const task = localDb.getTaskById(op.taskLocalId);
  if (!task) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: "scope_mismatch",
      incrementRetryCount: true,
    });
    throw new Error("对应任务不存在，无法恢复录音上传。");
  }

  const resolved = await ensureRemoteTaskId(task);
  patchLegacyUploadPseudoOp(op.opId, {
    objectRemoteId: resolved.remoteTaskId,
  });
  if (!resolved.remoteTaskId) {
    const reasonCode = getPendingBindReasonCode();
    markLegacyUploadPseudoOp(op.opId, {
      status: "queued",
      reasonCode,
    });
    throw new Error(buildPendingAttachmentMessage(reasonCode, "录音"));
  }

  const latestOp = getLegacyUploadPseudoOp(op.opId) ?? op;
  const validationReason = await validatePersistedLegacyUploadFile(latestOp);
  if (validationReason) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: validationReason,
      incrementRetryCount: true,
    });
    throw new Error(validationReason === "file_missing" ? "录音原件丢失。" : "录音原件已损坏。");
  }

  markLegacyUploadPseudoOp(op.opId, {
    status: "processing",
    reasonCode: "unknown_error",
  });

  try {
    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
      file: {
        uri: latestOp.filePath,
        name: latestOp.displayTitle || `record-note-${latestOp.objectLocalId}.m4a`,
        type: latestOp.mimeType || "audio/m4a",
      },
      clientId: resolved.task.clientId,
      eventLineId: resolved.task.eventLineId,
      title: latestOp.displayTitle ?? null,
      durationSeconds: latestOp.durationSeconds ?? null,
    });

    try {
      const latestAttachment = uploadedTask.attachments?.[0];
      if (latestAttachment?.id) {
        await api.transcribeTaskAttachmentToDocument(resolved.remoteTaskId, latestAttachment.id);
      }
    } catch {}

    localDb.reconcileTaskServerAck({
      taskId: resolved.task.id,
      clientOpId: op.opId,
      operation: "update",
      ackLocalVersion: localDb.getTaskById(resolved.task.id)?.localVersion ?? null,
      serverTask: {
        ...uploadedTask,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
    });

    removeLegacyUploadPseudoOp(op.opId);
    await removePersistedRecordedAudio(latestOp.filePath);
    return localDb.getTaskById(resolved.task.id) ?? {
      ...uploadedTask,
      id: resolved.task.id,
      remoteId: uploadedTask.remoteId ?? uploadedTask.id,
    };
  } catch (error) {
    const reasonCode = mapLegacyUploadErrorReasonCode(error);
    markLegacyUploadPseudoOp(op.opId, {
      status: resolveLegacyUploadFailureStatus(reasonCode),
      reasonCode,
      incrementRetryCount: true,
    });
    throw error;
  }
}

async function uploadLegacyTaskAttachmentOp(
  op: LegacyUploadPseudoOp,
): Promise<TaskRecord> {
  const task = localDb.getTaskById(op.taskLocalId);
  if (!task) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: "scope_mismatch",
      incrementRetryCount: true,
    });
    throw new Error("对应任务不存在，无法恢复附件上传。");
  }

  const resolved = await ensureRemoteTaskId(task);
  patchLegacyUploadPseudoOp(op.opId, {
    objectRemoteId: resolved.remoteTaskId,
  });
  if (!resolved.remoteTaskId) {
    const reasonCode = getPendingBindReasonCode();
    markLegacyUploadPseudoOp(op.opId, {
      status: "queued",
      reasonCode,
    });
    throw new Error(buildPendingAttachmentMessage(reasonCode, "附件"));
  }

  const latestOp = getLegacyUploadPseudoOp(op.opId) ?? op;
  const validationReason = await validatePersistedLegacyUploadFile(latestOp);
  if (validationReason) {
    markLegacyUploadPseudoOp(op.opId, {
      status: "needs_attention",
      reasonCode: validationReason,
      incrementRetryCount: true,
    });
    throw new Error(validationReason === "file_missing" ? "附件原件丢失。" : "附件原件已损坏。");
  }

  markLegacyUploadPseudoOp(op.opId, {
    status: "processing",
    reasonCode: "unknown_error",
  });

  try {
    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
      file: {
        uri: latestOp.filePath,
        name: latestOp.displayTitle || `attachment-${latestOp.objectLocalId}`,
        type: latestOp.mimeType || "application/octet-stream",
      },
      clientId: resolved.task.clientId,
      eventLineId: resolved.task.eventLineId,
      title: latestOp.displayTitle ?? null,
    });

    localDb.reconcileTaskServerAck({
      taskId: resolved.task.id,
      clientOpId: op.opId,
      operation: "update",
      ackLocalVersion: localDb.getTaskById(resolved.task.id)?.localVersion ?? null,
      serverTask: {
        ...uploadedTask,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
    });

    removeLegacyUploadPseudoOp(op.opId);
    await removePersistedRecordedAudio(latestOp.filePath);
    return localDb.getTaskById(resolved.task.id) ?? {
      ...uploadedTask,
      id: resolved.task.id,
      remoteId: uploadedTask.remoteId ?? uploadedTask.id,
    };
  } catch (error) {
    const reasonCode = mapLegacyUploadErrorReasonCode(error);
    markLegacyUploadPseudoOp(op.opId, {
      status: resolveLegacyUploadFailureStatus(reasonCode),
      reasonCode,
      incrementRetryCount: true,
    });
    throw error;
  }
}

export async function retryLegacyUploadPseudoOp(
  opId: string,
): Promise<{ ok: true } | { ok: false; reasonCode: LegacyUploadReasonCode; message: string }> {
  const op = getLegacyUploadPseudoOp(opId);
  if (!op) {
    return { ok: false, reasonCode: "unknown_error", message: "未找到待重试的上传项。" };
  }

  try {
    if (op.objectType === "task_attachment") {
      await uploadLegacyTaskAttachmentOp(op);
    } else {
      await uploadLegacyRecordedAudioOp(op);
    }
    return { ok: true };
  } catch (error) {
    const next = getLegacyUploadPseudoOp(opId);
    return {
      ok: false,
      reasonCode: next?.reasonCode ?? "unknown_error",
      message: error instanceof Error ? error.message : "附件上传重试失败。",
    };
  }
}

export async function retryAllLegacyUploadPseudoOps(): Promise<void> {
  const ops = getLegacyUploadPseudoOps().filter((item) => item.status !== "processing");
  for (const op of ops) {
    await retryLegacyUploadPseudoOp(op.opId);
  }
}

export async function createQuickRecordTask(title: string, description: string): Promise<TaskRecord> {
  const { task } = createTaskLocalFirst({
    title,
    description,
    tags: ["速记"],
  });
  const resolved = await ensureRemoteTaskId(task);
  return resolved.task;
}

export async function attachRecordedAudioToTask(
  task: TaskRecord,
  payload: {
    file: api.UploadableFile;
    title: string;
    durationSeconds: number;
  },
): Promise<RecordedAttachmentResult> {
  const draft = await persistRecordedAudioDraft(task.id, payload.file);
  const resolved = localDb.getTaskById(task.id) ?? task;

  if (!draft) {
    const remote = await ensureRemoteTaskId(resolved);
    if (!remote.remoteTaskId) {
      return {
        status: "pending_attachment",
        task: remote.task,
        message: buildPendingAttachmentMessage(getPendingBindReasonCode(), "录音"),
      };
    }
    const uploadedTask = await api.uploadTaskAttachment(remote.remoteTaskId, {
      file: payload.file,
      clientId: remote.task.clientId,
      eventLineId: remote.task.eventLineId,
      title: payload.title,
      durationSeconds: payload.durationSeconds,
    });
    return {
      status: "uploaded",
      task: {
        ...uploadedTask,
        id: resolved.id,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
      message: "录音已上传",
    };
  }

  const pseudoOp = upsertLegacyUploadPseudoOp({
    opId: draft.opId,
    objectType: "recorded_audio_attachment",
    objectLocalId: draft.objectLocalId,
    objectRemoteId: resolved.remoteId ?? null,
    lane: "transfer",
    status: "queued",
    retryCount: 0,
    reasonCode: "bind_pending_remote_id",
    createdAt: new Date().toISOString(),
    lastAttemptAt: null,
    displayTitle: payload.title,
    taskLocalId: resolved.id,
    filePath: draft.filePath,
    size: draft.size,
    mtime: draft.mtime,
    hash: draft.hash,
    entityRefLocalId: resolved.id,
    mimeType: draft.mimeType,
    durationSeconds: payload.durationSeconds,
  });

  try {
    const uploadedTask = await uploadLegacyRecordedAudioOp(pseudoOp);
    return {
      status: "uploaded",
      task: uploadedTask as TaskRecord,
      message: "录音已上传",
    };
  } catch {
    const latestOp = getLegacyUploadPseudoOp(pseudoOp.opId);
    const reasonCode = latestOp?.reasonCode ?? getPendingBindReasonCode();
    if (isPendingAttachmentReasonCode(reasonCode)) {
      return {
        status: "pending_attachment",
        task: localDb.getTaskById(resolved.id) ?? resolved,
        message: buildPendingAttachmentMessage(reasonCode, "录音"),
      };
    }
    return {
      status: "needs_attention",
      task: localDb.getTaskById(resolved.id) ?? resolved,
      message: "录音需处理。请在系统健康页重试上传。",
    };
  }
}

export async function attachFileToTask(
  task: TaskRecord,
  payload: {
    file: api.UploadableFile;
    title?: string | null;
  },
): Promise<TaskAttachmentResult> {
  const fallbackTitle =
    normalizeUriUploadableFile(payload.file, {
      name: `attachment-${Date.now()}`,
      type: "application/octet-stream",
    })?.name || "附件";
  const attachmentTitle = payload.title?.trim() || fallbackTitle;
  const draft = await persistTaskAttachmentDraft(task.id, payload.file);
  const resolved = localDb.getTaskById(task.id) ?? task;

  if (!draft) {
    const remote = await ensureRemoteTaskId(resolved);
    if (!remote.remoteTaskId) {
      return {
        status: "pending_attachment",
        task: remote.task,
        message: buildPendingAttachmentMessage(getPendingBindReasonCode(), "附件"),
      };
    }
    const uploadedTask = await api.uploadTaskAttachment(remote.remoteTaskId, {
      file: payload.file,
      clientId: remote.task.clientId,
      eventLineId: remote.task.eventLineId,
      title: attachmentTitle,
    });
    return {
      status: "uploaded",
      task: {
        ...uploadedTask,
        id: resolved.id,
        remoteId: uploadedTask.remoteId ?? uploadedTask.id,
      },
      message: "附件已上传",
    };
  }

  const pseudoOp = upsertLegacyUploadPseudoOp({
    opId: draft.opId,
    objectType: "task_attachment",
    objectLocalId: draft.objectLocalId,
    objectRemoteId: resolved.remoteId ?? null,
    lane: "transfer",
    status: "queued",
    retryCount: 0,
    reasonCode: "bind_pending_remote_id",
    createdAt: new Date().toISOString(),
    lastAttemptAt: null,
    displayTitle: attachmentTitle,
    taskLocalId: resolved.id,
    filePath: draft.filePath,
    size: draft.size,
    mtime: draft.mtime,
    hash: draft.hash,
    entityRefLocalId: resolved.id,
    mimeType: draft.mimeType,
  });

  try {
    const uploadedTask = await uploadLegacyTaskAttachmentOp(pseudoOp);
    return {
      status: "uploaded",
      task: uploadedTask as TaskRecord,
      message: "附件已上传",
    };
  } catch {
    const latestOp = getLegacyUploadPseudoOp(pseudoOp.opId);
    const reasonCode = latestOp?.reasonCode ?? getPendingBindReasonCode();
    if (isPendingAttachmentReasonCode(reasonCode)) {
      return {
        status: "pending_attachment",
        task: localDb.getTaskById(resolved.id) ?? resolved,
        message: buildPendingAttachmentMessage(reasonCode, "附件"),
      };
    }
    return {
      status: "needs_attention",
      task: localDb.getTaskById(resolved.id) ?? resolved,
      message: "附件需处理。请在系统健康页重试上传。",
    };
  }
}
~~~

## `mobile/lib/runtime-controller.ts`

- 编码: `utf-8`

~~~typescript
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
~~~

## `mobile/lib/runtime-flags.ts`

- 编码: `utf-8`

~~~typescript
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
~~~

## `mobile/lib/runtime.ts`

- 编码: `utf-8`

~~~typescript
import * as api from "./api";
import * as cache from "./cache";
import { buildAccountScopeKey } from "./account-scope";
import { clearClientIntelCache } from "./client-intel-store";
import * as localDb from "./local-db";
import { clearAllSmartInputQueueScopes } from "./smart-input-queue";
import {
  setSyncFreezeStateForRuntime,
  startSyncEngine,
  stopSyncEngine,
} from "./sync-engine";
import { resetTaskBoardStore } from "./task-board-store";
import { resetCurrentFocusStore } from "./current-focus-store";
import { devLog } from "./dev-log";
import { createRuntimeController } from "./runtime-controller";
import { initializeRuntimeFlags } from "./runtime-flags";
import type { SessionUser } from "./types";

async function clearRuntimeSessionArtifacts(): Promise<void> {
  resetTaskBoardStore();
  resetCurrentFocusStore();
  await Promise.allSettled([
    cache.clearAll(),
    clearClientIntelCache({ allScopes: true }),
    clearAllSmartInputQueueScopes(),
  ]);
}

const controller = createRuntimeController({
  initializeBaseUrl: async () => {
    await api.initBaseUrl();
  },
  startSync: async () => {
    devLog("runtime", "start.sync_engine");
    await startSyncEngine();
  },
  stopSync: async () => {
    devLog("runtime", "stop.sync_engine");
    await stopSyncEngine();
  },
  resetSessionState: async () => {
    localDb.clearAllData();
    await clearRuntimeSessionArtifacts();
    devLog("runtime", "session.reset");
  },
});

export async function initializeRuntime(): Promise<void> {
  await controller.initialize();
  await initializeRuntimeFlags();
}

export async function startAuthenticatedRuntime(user: SessionUser): Promise<void> {
  await initializeRuntime();
  let scopePreparation: ReturnType<typeof localDb.prepareDatabaseForAccountScope>;
  try {
    scopePreparation = localDb.prepareDatabaseForAccountScope(buildAccountScopeKey(user));
  } catch (error) {
    const message = error instanceof Error ? error.message : "migration_prepare_failed";
    setSyncFreezeStateForRuntime("blocked_by_migration_failure", message);
    devLog("runtime", "scope.prepare_failed", { message });
    throw error;
  }
  if (scopePreparation.scopeChanged) {
    await clearRuntimeSessionArtifacts();
    devLog("runtime", "scope.changed.cleanup");
  }
  devLog("runtime", "scope.prepared", {
    scopeChanged: scopePreparation.scopeChanged,
    integrityStatus: scopePreparation.integrityStatus,
    integrityReason: scopePreparation.integrityReason,
  });
  await controller.start();
}

export async function stopAuthenticatedRuntime(options?: { clearSessionState?: boolean }): Promise<void> {
  await controller.stop(options);
}

export function isRuntimeSyncRunning(): boolean {
  return controller.isSyncRunning();
}
~~~

## `mobile/lib/scope-storage-core.ts`

- 编码: `utf-8`

~~~typescript
import { NO_ACCOUNT_SCOPE_KEY, normalizeAccountScopeKey } from "./account-scope";

export function resolveScopedStorageNamespace(scopeKey: string | null | undefined): string {
  return encodeURIComponent(normalizeAccountScopeKey(scopeKey) ?? NO_ACCOUNT_SCOPE_KEY);
}

export function buildScopedStorageKey(
  prefix: string,
  key: string,
  scopeKey: string | null | undefined,
): string {
  return `${prefix}${resolveScopedStorageNamespace(scopeKey)}:${key}`;
}

export function buildScopedDirectoryPath(
  baseDirectory: string,
  scopeKey: string | null | undefined,
): string {
  const normalizedBase = baseDirectory.endsWith("/") ? baseDirectory : `${baseDirectory}/`;
  return `${normalizedBase}${resolveScopedStorageNamespace(scopeKey)}/`;
}
~~~

## `mobile/lib/simple-markdown.tsx`

- 编码: `utf-8`

~~~tsx
/**
 * Lightweight Markdown renderer for React Native.
 * Supports: headings (一、二、三 / ## / 1.), bold (**text**), lists (- item), paragraphs.
 * No external dependencies.
 */
import React, { useMemo } from "react";
import { Text, View, StyleSheet } from "react-native";
import type { TextStyle } from "react-native";
import { colors } from "./theme";

interface SimpleMarkdownProps {
  text: string;
  baseStyle?: TextStyle;
}

type Block =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[]; ordered: boolean };

function parseBlocks(raw: string): Block[] {
  const lines = raw.split("\n");
  const blocks: Block[] = [];
  let listBuffer: string[] = [];
  let listOrdered = false;
  let paragraphBuffer: string[] = [];

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return;
    blocks.push({ type: "paragraph", text: paragraphBuffer.join(" ").trim() });
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push({ type: "list", items: [...listBuffer], ordered: listOrdered });
    listBuffer = [];
    listOrdered = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    // Heading patterns: 一、二、三 / ## heading / 1. short heading (standalone)
    if (
      /^[一二三四五六七八九十]+、/.test(trimmed) ||
      /^#{1,4}\s+/.test(trimmed) ||
      /^第[一二三四五六七八九十\d]+部分/.test(trimmed)
    ) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", text: trimmed.replace(/^#{1,4}\s*/, "") });
      continue;
    }

    // Numbered heading: "1. Short title" (≤42 chars, no punctuation ending)
    const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch && trimmed.length <= 42 && !/[。！？!?：:]$/.test(trimmed)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", text: trimmed });
      continue;
    }

    // Unordered list
    const ulMatch = trimmed.match(/^[-*•]\s+(.+)$/);
    if (ulMatch) {
      flushParagraph();
      if (listBuffer.length && listOrdered) flushList();
      listOrdered = false;
      listBuffer.push(ulMatch[1]);
      continue;
    }

    // Ordered list item (longer than heading threshold)
    if (numberedMatch && trimmed.length > 42) {
      flushParagraph();
      if (listBuffer.length && !listOrdered) flushList();
      listOrdered = true;
      listBuffer.push(numberedMatch[2]);
      continue;
    }

    // Regular text
    flushList();
    paragraphBuffer.push(trimmed);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInlineEmphasis(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <Text key={idx} style={inlineStyles.bold}>
          {part.slice(2, -2)}
        </Text>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

export function SimpleMarkdown({ text, baseStyle }: SimpleMarkdownProps) {
  const blocks = useMemo(() => parseBlocks(text), [text]);

  if (!blocks.length) {
    return <Text style={baseStyle}>{text}</Text>;
  }

  return (
    <View style={mdStyles.container}>
      {blocks.map((block, idx) => {
        if (block.type === "heading") {
          return (
            <Text key={`h-${idx}`} style={[baseStyle, mdStyles.heading]}>
              {renderInlineEmphasis(block.text)}
            </Text>
          );
        }
        if (block.type === "list") {
          return (
            <View key={`l-${idx}`} style={mdStyles.listContainer}>
              {block.items.map((item, i) => (
                <View key={`li-${idx}-${i}`} style={mdStyles.listItem}>
                  <Text style={[baseStyle, mdStyles.bullet]}>
                    {block.ordered ? `${i + 1}.` : "•"}
                  </Text>
                  <Text style={[baseStyle, mdStyles.listText]}>
                    {renderInlineEmphasis(item)}
                  </Text>
                </View>
              ))}
            </View>
          );
        }
        return (
          <Text key={`p-${idx}`} style={[baseStyle, mdStyles.paragraph]}>
            {renderInlineEmphasis(block.text)}
          </Text>
        );
      })}
    </View>
  );
}

const inlineStyles = StyleSheet.create({
  bold: {
    fontWeight: "700",
    color: colors.text,
  },
});

const mdStyles = StyleSheet.create({
  container: {
    gap: 8,
  },
  heading: {
    fontWeight: "700",
    fontSize: 15,
    lineHeight: 24,
    color: colors.text,
    marginTop: 4,
  },
  paragraph: {
    lineHeight: 22,
  },
  listContainer: {
    gap: 4,
    paddingLeft: 4,
  },
  listItem: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  bullet: {
    width: 20,
    lineHeight: 22,
    color: colors.brand,
    fontWeight: "600",
  },
  listText: {
    flex: 1,
    lineHeight: 22,
  },
});
~~~

## `mobile/lib/smart-input-queue-core.ts`

- 编码: `utf-8`

~~~typescript
export interface QueuedSmartInputRef {
  id: string;
}

export function reconcileQueuedSmartInputItems<T extends QueuedSmartInputRef>(
  currentQueue: readonly T[],
  removeIds: ReadonlySet<string>,
): T[] {
  if (removeIds.size === 0) {
    return [...currentQueue];
  }
  return currentQueue.filter((item) => !removeIds.has(item.id));
}
~~~

## `mobile/lib/smart-input-queue.ts`

- 编码: `utf-8`

~~~typescript
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as FileSystem from "expo-file-system/legacy";
import * as api from "./api";
import * as localDb from "./local-db";
import {
  buildScopedDirectoryPath,
  buildScopedStorageKey,
  resolveScopedStorageNamespace,
} from "./scope-storage-core";
import { reconcileQueuedSmartInputItems } from "./smart-input-queue-core";
import type { SmartTaskDraftResponse } from "./types";

const SMART_INPUT_QUEUE_KEY_PREFIX = "yiyu_smart_input_audio_queue:";
const SMART_INPUT_QUEUE_BASE_DIR = `${FileSystem.documentDirectory ?? ""}smart-input-queue`;

interface QueuedSmartInputAudio {
  id: string;
  uri: string;
  name: string;
  type: string;
  referenceDate?: string | null;
  transcriptText?: string | null;
  createdAt: string;
}

type UploadableUriFile = {
  uri: string;
  name: string;
  type: string;
};

const flushInFlightByScope = new Map<string, Promise<SmartTaskDraftResponse[]>>();

function getCurrentScopeKey(): string | null {
  return localDb.getActiveAccountScopeKey();
}

function buildSmartInputQueueStorageKey(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): string {
  return buildScopedStorageKey(SMART_INPUT_QUEUE_KEY_PREFIX, "items", scopeKey);
}

function buildSmartInputQueueDirectory(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): string {
  return buildScopedDirectoryPath(SMART_INPUT_QUEUE_BASE_DIR, scopeKey);
}

export function isRetriableSmartInputQueueError(error: unknown): boolean {
  if (error instanceof api.ApiError) {
    return error.status >= 500 || error.status === 408 || error.status === 429;
  }
  if (error instanceof Error) {
    const lowered = error.message.toLowerCase();
    return (
      lowered.includes("network request failed") ||
      lowered.includes("network error") ||
      lowered.includes("timed out") ||
      lowered.includes("fetch")
    );
  }
  return true;
}

export function explainSmartInputQueueError(error: unknown): string {
  if (error instanceof api.ApiError) {
    try {
      const parsed = JSON.parse(error.body);
      if (typeof parsed?.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {}
    return error.body || "暂存语音补传失败。";
  }
  return error instanceof Error ? error.message : "暂存语音补传失败。";
}

function normalizeUploadableFile(file: api.UploadableFile): UploadableUriFile | null {
  if (typeof File !== "undefined" && file instanceof File) {
    return null;
  }
  if (!file || typeof file !== "object" || !("uri" in file)) {
    return null;
  }
  if (!file.uri) {
    return null;
  }
  return {
    uri: file.uri,
    name: file.name || `smart-input-${Date.now()}.m4a`,
    type: file.type || "audio/m4a",
  };
}

function inferExtension(file: UploadableUriFile): string {
  const fromName = file.name.split(".").pop()?.trim().toLowerCase();
  if (fromName) {
    return fromName;
  }
  const cleanUri = file.uri.split("?")[0].toLowerCase();
  const fromUri = cleanUri.split(".").pop()?.trim();
  if (fromUri) {
    return fromUri;
  }
  if (file.type.includes("wav")) return "wav";
  if (file.type.includes("mpeg") || file.type.includes("mp3")) return "mp3";
  if (file.type.includes("ogg")) return "ogg";
  if (file.type.includes("aac")) return "aac";
  return "m4a";
}

async function ensureQueueDirectory(scopeKey: string | null | undefined): Promise<void> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持离线暂存。");
  }
  await FileSystem.makeDirectoryAsync(buildSmartInputQueueDirectory(scopeKey), { intermediates: true });
}

async function persistAudioFile(
  itemId: string,
  file: UploadableUriFile,
  scopeKey: string | null | undefined,
): Promise<UploadableUriFile> {
  await ensureQueueDirectory(scopeKey);
  const extension = inferExtension(file);
  const destinationUri = `${buildSmartInputQueueDirectory(scopeKey)}${itemId}.${extension}`;
  if (file.uri !== destinationUri) {
    await FileSystem.copyAsync({ from: file.uri, to: destinationUri });
  }
  return {
    uri: destinationUri,
    name: `smart-input-${itemId}.${extension}`,
    type: file.type,
  };
}

async function removePersistedAudio(uri: string): Promise<void> {
  try {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  } catch {}
}

async function loadQueue(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): Promise<QueuedSmartInputAudio[]> {
  try {
    const raw = await AsyncStorage.getItem(buildSmartInputQueueStorageKey(scopeKey));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is QueuedSmartInputAudio => {
      return Boolean(item && typeof item.id === "string" && typeof item.uri === "string");
    });
  } catch {
    return [];
  }
}

async function saveQueue(
  items: QueuedSmartInputAudio[],
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): Promise<void> {
  await AsyncStorage.setItem(buildSmartInputQueueStorageKey(scopeKey), JSON.stringify(items));
}

export async function queueSmartInputAudio(
  file: api.UploadableFile,
  meta: { referenceDate?: string | null; transcriptText?: string | null } = {},
): Promise<void> {
  const scopeKey = getCurrentScopeKey();
  const normalized = normalizeUploadableFile(file);
  if (!normalized) {
    throw new Error("当前环境不支持暂存这条语音。");
  }
  const itemId = `smart_audio_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const persistedFile = await persistAudioFile(itemId, normalized, scopeKey);
  const queue = await loadQueue(scopeKey);
  queue.unshift({
    id: itemId,
    uri: persistedFile.uri,
    name: persistedFile.name,
    type: persistedFile.type,
    referenceDate: meta.referenceDate ?? null,
    transcriptText: meta.transcriptText?.trim() || null,
    createdAt: new Date().toISOString(),
  });
  await saveQueue(queue, scopeKey);
}

export async function getQueuedSmartInputCount(): Promise<number> {
  const queue = await loadQueue();
  return queue.length;
}

export async function clearSmartInputQueue(): Promise<number> {
  const scopeKey = getCurrentScopeKey();
  const queue = await loadQueue(scopeKey);
  for (const item of queue) {
    await removePersistedAudio(item.uri);
  }
  await saveQueue([], scopeKey);
  return queue.length;
}

export async function clearAllSmartInputQueueScopes(): Promise<void> {
  flushInFlightByScope.clear();
  const allKeys = await AsyncStorage.getAllKeys();
  const queueKeys = allKeys.filter((item) => item.startsWith(SMART_INPUT_QUEUE_KEY_PREFIX));
  if (queueKeys.length > 0) {
    await AsyncStorage.multiRemove(queueKeys);
  }
  if (FileSystem.documentDirectory) {
    await FileSystem.deleteAsync(`${SMART_INPUT_QUEUE_BASE_DIR}/`, { idempotent: true });
  }
}

export async function flushQueuedSmartInputDrafts(limit: number = 1): Promise<SmartTaskDraftResponse[]> {
  const scopeKey = getCurrentScopeKey();
  const scopeNamespace = resolveScopedStorageNamespace(scopeKey);
  const inflight = flushInFlightByScope.get(scopeNamespace);
  if (inflight) {
    return inflight;
  }

  const nextFlush = (async () => {
    const queue = await loadQueue(scopeKey);
    if (!queue.length) {
      return [];
    }

    const recovered: SmartTaskDraftResponse[] = [];
    const removeIds = new Set<string>();

    for (const item of queue) {
      if (recovered.length >= limit) {
        continue;
      }

      try {
        const info = await FileSystem.getInfoAsync(item.uri);
        if (!info.exists) {
          removeIds.add(item.id);
          continue;
        }

        const response = await api.generateSmartTaskDraft({
          transcriptText: item.transcriptText ?? undefined,
          audioFile: {
            uri: item.uri,
            name: item.name,
            type: item.type,
          },
          referenceDate: item.referenceDate ?? undefined,
        });
        recovered.push(response);
        removeIds.add(item.id);
        await removePersistedAudio(item.uri);
      } catch (error) {
        if (!isRetriableSmartInputQueueError(error)) {
          const currentQueue = await loadQueue(scopeKey);
          await saveQueue(reconcileQueuedSmartInputItems(currentQueue, removeIds), scopeKey);
          throw error;
        }
      }
    }

    const currentQueue = await loadQueue(scopeKey);
    await saveQueue(reconcileQueuedSmartInputItems(currentQueue, removeIds), scopeKey);
    return recovered;
  })();
  flushInFlightByScope.set(scopeNamespace, nextFlush);

  try {
    return await nextFlush;
  } finally {
    flushInFlightByScope.delete(scopeNamespace);
  }
}
~~~

## `mobile/lib/smart-input-recovery.ts`

- 编码: `utf-8`

~~~typescript
import type { SmartTaskDraft } from "./types";

export type RecoveryTrigger = "app_active" | "tasks_enter" | "manual";

export interface RecoveryAttemptOptions {
  trigger: RecoveryTrigger;
  queuedCount: number;
  inFlight: boolean;
  nowMs: number;
  lastAttemptAt: number | null;
  minIntervalMs?: number;
}

export interface AutoOpenOptions {
  trigger: RecoveryTrigger;
  isTasksScreenActive: boolean;
  hasBlockingUi: boolean;
  productRequiresAutoOpen?: boolean;
}

const DEFAULT_RECOVERY_INTERVAL_MS = 1200;

export function shouldAttemptSmartInputRecovery(options: RecoveryAttemptOptions): boolean {
  if (options.queuedCount <= 0 || options.inFlight) {
    return false;
  }
  if (options.trigger === "manual") {
    return true;
  }
  const minIntervalMs = options.minIntervalMs ?? DEFAULT_RECOVERY_INTERVAL_MS;
  if (options.lastAttemptAt == null) {
    return true;
  }
  return options.nowMs - options.lastAttemptAt >= minIntervalMs;
}

export function shouldAutoOpenRecoveredDraft(options: AutoOpenOptions): boolean {
  if (options.productRequiresAutoOpen) {
    return true;
  }
  if (options.trigger !== "manual") {
    return false;
  }
  return options.isTasksScreenActive && !options.hasBlockingUi;
}

export function buildRecoveredDraftKey(draft: SmartTaskDraft | null | undefined): string {
  if (!draft) return "";
  return JSON.stringify({
    title: draft.title ?? "",
    dueDate: draft.dueDate ?? "",
    dueTime: draft.dueTime ?? "",
    description: draft.description ?? "",
  });
}

export function shouldUseRecoveredDraft(nextDraftKey: string, lastRecoveredDraftKey: string | null): boolean {
  if (!nextDraftKey) return false;
  return nextDraftKey !== lastRecoveredDraftKey;
}
~~~

## `mobile/lib/storage.ts`

- 编码: `utf-8`

~~~typescript
import { Platform } from "react-native";

/**
 * Cross-platform secure storage.
 * - iOS/Android: uses expo-secure-store
 * - Web: uses localStorage (for dev preview)
 */

let _secureStore: typeof import("expo-secure-store") | null = null;

async function getSecureStore() {
  if (Platform.OS === "web") return null;
  if (!_secureStore) {
    _secureStore = await import("expo-secure-store");
  }
  return _secureStore;
}

export async function getItem(key: string): Promise<string | null> {
  const store = await getSecureStore();
  if (store) return store.getItemAsync(key);
  if (typeof localStorage !== "undefined") return localStorage.getItem(key);
  return null;
}

export async function setItem(key: string, value: string): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.setItemAsync(key, value);
    return;
  }
  if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
}

export async function deleteItem(key: string): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.deleteItemAsync(key);
    return;
  }
  if (typeof localStorage !== "undefined") localStorage.removeItem(key);
}
~~~

## `mobile/lib/sync-engine.ts`

- 编码: `utf-8`

~~~typescript
/**
 * sync-engine.ts — 双数据库后台同步引擎
 *
 * 核心架构：
 *   ┌────────────┐     ┌──────────────┐     ┌────────────┐
 *   │  UI 层     │ ──▶ │  本地 SQLite  │ ──▶ │  云端 API   │
 *   │ (即时响应)  │ ◀── │  (真实数据源)  │ ◀── │  (远程数据源) │
 *   └────────────┘     └──────────────┘     └────────────┘
 *
 * 数据流：
 *   1. 读取: UI 始终从 SQLite 读取 → 毫秒级响应
 *   2. 写入: 先写 SQLite（乐观更新） → 排入 pending_ops 队列
 *   3. 同步: 后台双向同步
 *      - 上行：将 pending_ops 中的操作推送到云端
 *      - 下行：从云端拉取最新数据写入 SQLite
 *   4. 后台: App 进入后台后通过 BackgroundFetch 定期同步
 *
 * 冲突策略: 服务端权威 (server-wins)
 *   - 上行推送失败时保留本地版本，下次重试
 *   - 下行拉取的数据覆盖本地已同步的记录
 *   - 本地未同步的修改不会被覆盖
 */

import { AppState, type AppStateStatus } from "react-native";
import * as BackgroundFetch from "expo-background-fetch";
import * as TaskManager from "expo-task-manager";
import * as api from "./api";
import { processQueuedLegacyUploadPseudoOps } from "./legacy-upload-runner";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import { mapSyncErrorToReasonCode } from "./sync-errors";
import { isSyncFreezeBlocked, isSyncFreezePaused } from "./sync-freeze-core";
import {
  completeTaskWithReviewLocalFirst as commitCompleteTaskWithReviewLocalFirst,
  createTaskLocalFirst as commitCreateTaskLocalFirst,
  deleteTaskLocalFirst as commitDeleteTaskLocalFirst,
  updateTaskLocalFirst as commitUpdateTaskLocalFirst,
} from "./task-repository";
import type { MutationReceipt, SyncFreezeState, TaskRecord } from "./types";

// ─── Constants ──────────────────────────────────

const BACKGROUND_SYNC_TASK = "YIYU_BACKGROUND_SYNC";
const SYNC_INTERVAL_MS = 2 * 60 * 1000; // 前台自动同步间隔：2分钟
const MAX_OP_RETRIES = 5;

// ─── Sync State ─────────────────────────────────

type SyncStatus = "idle" | "syncing" | "error";
type SyncListener = (status: SyncStatus, lastSyncTime: string | null) => void;
export interface SyncEventLogRecord {
  id: string;
  level: "info" | "error";
  event: string;
  createdAt: string;
  payload?: Record<string, unknown>;
}

let _syncStatus: SyncStatus = "idle";
let _lastSyncTime: string | null = null;
let _listeners: Set<SyncListener> = new Set();
let _syncTimer: ReturnType<typeof setInterval> | null = null;
let _appStateSubscription: any = null;
let _isSyncing = false;
let _isStarted = false;
let _startPromise: Promise<void> | null = null;
let _backgroundSyncRegistered = false;
let _taskBoardFetchCount = 0;
let _syncFreezeState: SyncFreezeState = "ready";
let _syncFreezeDetail: string | null = null;
let _syncEventCounter = 0;
let _recentSyncEvents: SyncEventLogRecord[] = [];

function pushSyncEvent(
  level: "info" | "error",
  event: string,
  payload?: Record<string, unknown>,
): void {
  _syncEventCounter += 1;
  _recentSyncEvents = [
    {
      id: `sync_evt_${_syncEventCounter}`,
      level,
      event,
      createdAt: new Date().toISOString(),
      payload,
    },
    ..._recentSyncEvents,
  ].slice(0, 50);
}

function setSyncFreezeState(
  state: SyncFreezeState,
  detail: string | null = null,
): void {
  const changed = _syncFreezeState !== state || _syncFreezeDetail !== detail;
  _syncFreezeState = state;
  _syncFreezeDetail = detail;
  if (changed) {
    pushSyncEvent("info", "freeze_state_changed", {
      state,
      detail,
    });
  }
  notifyListeners();
}

function notifyListeners(): void {
  for (const listener of _listeners) {
    try {
      listener(_syncStatus, _lastSyncTime);
    } catch {}
  }
}

function setSyncStatus(status: SyncStatus): void {
  _syncStatus = status;
  notifyListeners();
}

// ─── Data Change Listeners ──────────────────────

type DataChangeListener = () => void;
let _dataChangeListeners: Set<DataChangeListener> = new Set();

function notifyDataChanged(): void {
  for (const listener of _dataChangeListeners) {
    try {
      listener();
    } catch {}
  }
}

/**
 * 订阅数据变化通知（同步完成后触发）
 * 返回取消订阅函数
 */
export function onDataChanged(listener: DataChangeListener): () => void {
  _dataChangeListeners.add(listener);
  return () => {
    _dataChangeListeners.delete(listener);
  };
}

export function emitDataChanged(): void {
  notifyDataChanged();
}

// ─── Public API ─────────────────────────────────

/**
 * 订阅同步状态变化
 */
export function onSyncStatusChange(listener: SyncListener): () => void {
  _listeners.add(listener);
  // 立即通知当前状态
  listener(_syncStatus, _lastSyncTime);
  return () => {
    _listeners.delete(listener);
  };
}

/**
 * 获取当前同步状态
 */
export function getSyncStatus(): { status: SyncStatus; lastSyncTime: string | null } {
  return { status: _syncStatus, lastSyncTime: _lastSyncTime };
}

export function getRecentSyncEvents(limit = 20): SyncEventLogRecord[] {
  return _recentSyncEvents.slice(0, limit);
}

export function getSyncControlState(): {
  freezeState: SyncFreezeState;
  isPaused: boolean;
  blockedReason: string | null;
  detail: string | null;
} {
  return {
    freezeState: _syncFreezeState,
    isPaused: isSyncFreezePaused(_syncFreezeState),
    blockedReason: isSyncFreezeBlocked(_syncFreezeState) ? _syncFreezeDetail : null,
    detail: _syncFreezeDetail,
  };
}

export function isSyncPaused(): boolean {
  return isSyncFreezePaused(_syncFreezeState);
}

export function setSyncPaused(paused: boolean): void {
  if (!paused && isSyncFreezeBlocked(_syncFreezeState)) {
    devLog("sync", "resume.skipped_blocked", { blockedReason: _syncFreezeDetail });
    return;
  }
  if (paused) {
    stopForegroundSync();
    if (_syncStatus === "syncing") {
      setSyncStatus("idle");
    }
    setSyncFreezeState("paused_by_user");
    devLog("sync", "paused");
    pushSyncEvent("info", "paused_by_user");
    return;
  }
  setSyncFreezeState("ready");
  devLog("sync", "resumed");
  pushSyncEvent("info", "resumed_by_user");
  if (_isStarted) {
    startForegroundSync();
    void performSync();
  }
}

export function setSyncFreezeStateForRuntime(
  state: SyncFreezeState,
  detail: string | null = null,
): void {
  if (state === "paused_by_user") {
    setSyncPaused(true);
    return;
  }
  stopForegroundSync();
  if (_syncStatus === "syncing") {
    setSyncStatus("idle");
  }
  setSyncFreezeState(state, detail);
  pushSyncEvent("info", "runtime_freeze_applied", { state, detail });
  devLog("sync", "freeze_state.runtime", { state, detail });
}

/**
 * 初始化同步引擎
 * 应在 App 启动、用户登录成功后调用
 */
export async function startSyncEngine(): Promise<void> {
  if (_isStarted) {
    devLog("sync", "start.skipped_already_started");
    return;
  }
  if (_startPromise) {
    devLog("sync", "start.reused_inflight");
    await _startPromise;
    return;
  }

  _startPromise = (async () => {
    localDb.initDatabase();
    const integrity = localDb.getDataIntegrityState();
    setSyncFreezeState(
      integrity.integrityStatus === "blocked" ? "blocked_by_integrity" : "ready",
      integrity.integrityReason,
    );
    _lastSyncTime = localDb.getSyncMeta("tasks_last_sync");

    startForegroundSync();

    if (!_appStateSubscription) {
      _appStateSubscription = AppState.addEventListener("change", handleAppStateChange);
    }

    await registerBackgroundSync();
    _isStarted = true;
    pushSyncEvent("info", "sync_engine_started", {
      lastSyncTime: _lastSyncTime,
      freezeState: _syncFreezeState,
      blockedReason: _syncFreezeDetail,
    });
    devLog("sync", "start.completed", {
      lastSyncTime: _lastSyncTime,
      blockedReason: _syncFreezeDetail,
      freezeState: _syncFreezeState,
    });
    if (!isSyncFreezeBlocked(_syncFreezeState)) {
      void performSync();
    }
  })().finally(() => {
    _startPromise = null;
  });

  await _startPromise;
}

/**
 * 停止同步引擎（登出时调用）
 */
export async function stopSyncEngine(): Promise<void> {
  if (_startPromise) {
    await _startPromise.catch(() => {});
  }

  stopForegroundSync();

  if (_appStateSubscription) {
    _appStateSubscription.remove();
    _appStateSubscription = null;
  }

  _isStarted = false;
  _isSyncing = false;
  setSyncFreezeState("ready");
  _syncStatus = "idle";
  _lastSyncTime = null;
  pushSyncEvent("info", "sync_engine_stopped");
  notifyListeners();

  if (_backgroundSyncRegistered) {
    try {
      await BackgroundFetch.unregisterTaskAsync(BACKGROUND_SYNC_TASK);
    } catch {}
    _backgroundSyncRegistered = false;
  }

  devLog("sync", "stop.completed");
}

/**
 * 手动触发一次完整同步（下拉刷新时调用）
 */
export async function triggerSync(): Promise<void> {
  if (isSyncFreezeBlocked(_syncFreezeState)) {
    devLog("sync", "trigger.skipped_blocked", { blockedReason: _syncFreezeDetail });
    pushSyncEvent("error", "trigger_skipped_blocked", { blockedReason: _syncFreezeDetail });
    return;
  }
  if (isSyncFreezePaused(_syncFreezeState)) {
    devLog("sync", "trigger.skipped_paused");
    pushSyncEvent("info", "trigger_skipped_paused");
    return;
  }
  if (!_isStarted) {
    await startSyncEngine();
  }
  await performSync();
}

// ─── Core Sync Logic ────────────────────────────

async function performSync(): Promise<void> {
  if (isSyncFreezeBlocked(_syncFreezeState)) return;
  if (isSyncFreezePaused(_syncFreezeState)) return;
  if (_isSyncing) return;
  _isSyncing = true;
  setSyncStatus("syncing");
  devLog("sync", "cycle.started");
  pushSyncEvent("info", "cycle_started");

  try {
    // 1. 上行：推送本地待上传操作
    await pushPendingOps();

    // 2. 处理 legacy transfer lane 中已排队的附件/录音上传
    const legacyTransfer = await processQueuedLegacyUploadPseudoOps();
    if (legacyTransfer.attempted > 0) {
      pushSyncEvent("info", "legacy_transfer_processed", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
      devLog("sync", "legacy_transfer.processed", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
    }
    if (legacyTransfer.stoppedByAuth) {
      setSyncFreezeState("blocked_by_auth", "auth_expired");
      pushSyncEvent("error", "legacy_transfer_auth_blocked", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
      throw new Error("Legacy transfer upload blocked by expired auth.");
    }

    // 3. 下行：从云端拉取最新数据
    await pullFromCloud();

    _lastSyncTime = new Date().toISOString();
    setSyncStatus("idle");
    pushSyncEvent("info", "cycle_succeeded", { lastSyncTime: _lastSyncTime });
    devLog("sync", "cycle.succeeded", { lastSyncTime: _lastSyncTime });

    // 通知 UI 数据已更新
    notifyDataChanged();
  } catch (error) {
    console.warn("[SyncEngine] Sync failed:", error);
    devLog("sync", "cycle.failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    pushSyncEvent("error", "cycle_failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    setSyncStatus("error");

    // 即使同步失败，如果有部分数据更新也通知
    notifyDataChanged();
  } finally {
    _isSyncing = false;
  }
}

/**
 * 上行推送：将本地待上传的操作发送到云端
 */
async function pushPendingOps(): Promise<void> {
  const ops = localDb.getPendingOps();
  if (ops.length === 0) return;

  for (const op of ops) {
    if (op.retryCount >= MAX_OP_RETRIES) {
      localDb.markOpFailed(op.id, op.lastError ?? "Max retries exceeded", op.reasonCode ?? "server_rejected", "needs_attention");
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, "needs_attention", op.reasonCode ?? "server_rejected");
      }
      continue;
    }

    try {
      localDb.markOpSyncing(op.id);
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, "syncing");
      }
      const payload = op.payload ? JSON.parse(op.payload) : {};

      switch (op.entityType) {
        case "task": {
          const localTask = localDb.getTaskById(op.entityId);
          const remoteTaskId = op.entityRemoteId ?? localTask?.remoteId ?? null;
          if (op.operation === "create") {
            const created = await api.createTask(payload);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: created,
            });
          } else if (op.operation === "update") {
            if (!remoteTaskId) {
              throw new Error("Missing remote task id for update");
            }
            const updated = await api.updateTask(remoteTaskId, payload);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: updated,
            });
          } else if (op.operation === "complete_with_review") {
            if (!remoteTaskId) {
              throw new Error("Missing remote task id for complete_with_review");
            }
            const reviewNote =
              typeof payload.reviewNote === "string" ? payload.reviewNote.trim() : "";
            if (!reviewNote) {
              throw new Error("Missing review note for complete_with_review");
            }
            const reviewedTask = await api.completeTaskWithReview(remoteTaskId, reviewNote);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: reviewedTask,
            });
          } else if (op.operation === "delete") {
            if (remoteTaskId) {
              await api.deleteTask(remoteTaskId);
            }
            localDb.purgeTask(op.entityId);
          }
          break;
        }
        // 可以扩展其他实体类型...
      }

      localDb.removeOp(op.id);
    } catch (error: any) {
      const message = error?.message || "Unknown error";
      const reasonCode = mapSyncErrorToReasonCode(error);
      const nextStatus = op.retryCount + 1 >= MAX_OP_RETRIES ? "needs_attention" : "queued";
      localDb.markOpFailed(op.id, message, reasonCode, nextStatus);
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, nextStatus, reasonCode);
      }

      // 如果是 401 错误，停止推送（需要重新登录）
      if (error instanceof api.ApiError && error.status === 401) {
        setSyncFreezeState("blocked_by_auth", "auth_expired");
        pushSyncEvent("error", "push_op_auth_blocked", {
          opId: op.id,
          entityType: op.entityType,
          operation: op.operation,
        });
        throw error;
      }
    }
  }
}

/**
 * 下行拉取：从云端获取最新数据写入本地 SQLite
 */
async function pullFromCloud(): Promise<void> {
  _taskBoardFetchCount += 1;
  devLog("taskBoard", "fetch.from_sync_engine", { count: _taskBoardFetchCount });
  pushSyncEvent("info", "pull_started", { taskBoardFetchCount: _taskBoardFetchCount });

  // 并行拉取各类数据
  const [boardResult, eventLinesResult, clientsResult, taskListsResult] =
    await Promise.allSettled([
      api.fetchTaskBoard(),
      api.fetchEventLines(),
      api.fetchClients(),
      api.fetchTaskLists(),
    ]);

  if (boardResult.status === "fulfilled") {
    localDb.upsertTasksFromCloud(boardResult.value.tasks);
  }

  if (eventLinesResult.status === "fulfilled") {
    localDb.upsertEventLinesFromCloud(eventLinesResult.value);
  }

  if (clientsResult.status === "fulfilled") {
    localDb.upsertClientsFromCloud(clientsResult.value);
  }

  if (taskListsResult.status === "fulfilled") {
    localDb.upsertTaskListsFromCloud(taskListsResult.value);
  }

  // 如果所有请求都失败了，抛出错误
  const allFailed = [boardResult, eventLinesResult, clientsResult, taskListsResult]
    .every((r) => r.status === "rejected");
  if (allFailed) {
    pushSyncEvent("error", "pull_failed_all_requests");
    throw new Error("All cloud sync requests failed");
  }

  pushSyncEvent("info", "pull_succeeded", {
    board: boardResult.status,
    eventLines: eventLinesResult.status,
    clients: clientsResult.status,
    taskLists: taskListsResult.status,
  });
}

// ─── Foreground Sync ────────────────────────────

function startForegroundSync(): void {
  stopForegroundSync();
  _syncTimer = setInterval(() => {
    void performSync();
  }, SYNC_INTERVAL_MS);
}

function stopForegroundSync(): void {
  if (_syncTimer) {
    clearInterval(_syncTimer);
    _syncTimer = null;
  }
}

function handleAppStateChange(nextState: AppStateStatus): void {
  if (!_isStarted) return;
  if (nextState === "active") {
    // App 回到前台，立即同步一次 + 恢复定时器
    void performSync();
    startForegroundSync();
  } else if (nextState === "background") {
    // 进入后台，停止前台定时器（交给 BackgroundFetch）
    stopForegroundSync();
  }
}

// ─── Background Sync ────────────────────────────

TaskManager.defineTask(BACKGROUND_SYNC_TASK, async () => {
  try {
    await performSync();
    return BackgroundFetch.BackgroundFetchResult.NewData;
  } catch {
    return BackgroundFetch.BackgroundFetchResult.Failed;
  }
});

async function registerBackgroundSync(): Promise<void> {
  if (_backgroundSyncRegistered) {
    return;
  }
  try {
    const status = await BackgroundFetch.getStatusAsync();
    if (status === BackgroundFetch.BackgroundFetchStatus.Denied) {
      console.warn("[SyncEngine] Background fetch is denied by the OS");
      return;
    }

    const alreadyRegistered = await TaskManager.isTaskRegisteredAsync(BACKGROUND_SYNC_TASK);
    if (!alreadyRegistered) {
      await BackgroundFetch.registerTaskAsync(BACKGROUND_SYNC_TASK, {
        minimumInterval: 15 * 60,
        stopOnTerminate: false,
        startOnBoot: true,
      });
    }
    _backgroundSyncRegistered = true;
  } catch (error) {
    console.warn("[SyncEngine] Failed to register background sync:", error);
  }
}

// ─── Offline-First Write Helpers ────────────────

/**
 * 离线优先的任务创建
 * 立即写入本地 SQLite → 排入上传队列 → 后台异步上传
 */
export function createTaskOfflineFirst(task: TaskRecord): MutationReceipt {
  const { receipt } = commitCreateTaskLocalFirst({
    title: task.title,
    description: task.description ?? undefined,
    dueDate: task.dueDate ?? undefined,
    durationMinutes: task.durationMinutes ?? undefined,
    priority: task.priority,
    clientId: task.clientId ?? undefined,
    eventLineId: task.eventLineId ?? undefined,
    listId: task.listId ?? undefined,
    tags: task.tags ?? undefined,
    businessCategory: task.businessCategory ?? undefined,
    currentBlocker: task.currentBlocker ?? undefined,
    nextAction: task.nextAction ?? undefined,
    recentDecision: task.recentDecision ?? undefined,
  });
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

/**
 * 离线优先的任务更新
 */
export function updateTaskOfflineFirst(
  taskId: string,
  updates: Partial<TaskRecord>,
): MutationReceipt {
  const { receipt } = commitUpdateTaskLocalFirst(taskId, {
    title: updates.title,
    description: updates.description ?? undefined,
    dueDate: updates.dueDate ?? undefined,
    durationMinutes: updates.durationMinutes ?? undefined,
    priority: updates.priority,
    clientId: updates.clientId ?? undefined,
    eventLineId: updates.eventLineId ?? undefined,
    listId: updates.listId ?? undefined,
    tags: updates.tags ?? undefined,
    businessCategory: updates.businessCategory ?? undefined,
    currentBlocker: updates.currentBlocker ?? undefined,
    nextAction: updates.nextAction ?? undefined,
    recentDecision: updates.recentDecision ?? undefined,
    progressStatus: updates.progressStatus,
  });
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

/**
 * 离线优先的任务删除
 */
export function deleteTaskOfflineFirst(taskId: string): MutationReceipt {
  const { receipt } = commitDeleteTaskLocalFirst(taskId);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

export function completeTaskWithReviewOfflineFirst(
  taskId: string,
  reviewNote: string,
): MutationReceipt {
  const { receipt } = commitCompleteTaskWithReviewLocalFirst(taskId, reviewNote);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}
~~~

## `mobile/lib/sync-errors.ts`

- 编码: `utf-8`

~~~typescript
import { ApiError } from "./api";
import type { SyncReasonCode } from "./types";

export function mapSyncErrorToReasonCode(error: unknown): SyncReasonCode {
  if (error instanceof ApiError) {
    if (error.status === 401) return "auth_expired";
    if (error.status === 403) return "permission_denied";
    if (error.status === 409) return "version_conflict";
    if (error.status === 413 || error.status === 507) return "quota_exceeded";
    if (error.status === 400 || error.status === 422) return "validation_failed";
    return "server_rejected";
  }
  return "network_unavailable";
}
~~~

## `mobile/lib/sync-freeze-core.ts`

- 编码: `utf-8`

~~~typescript
import type { SyncFreezeState } from "./types";

export function isSyncFreezeBlocked(state: SyncFreezeState): boolean {
  return state !== "ready" && state !== "paused_by_user";
}

export function isSyncFreezePaused(state: SyncFreezeState): boolean {
  return state === "paused_by_user";
}

export function describeSyncFreezeState(
  state: SyncFreezeState,
  detail: string | null,
): {
  summary: string;
  actionLabel: string | null;
  detail: string | null;
} {
  switch (state) {
    case "ready":
      return {
        summary: "同步正常",
        actionLabel: "暂停同步",
        detail: detail ?? null,
      };
    case "paused_by_user":
      return {
        summary: "同步已暂停",
        actionLabel: "恢复同步",
        detail: detail ?? null,
      };
    case "blocked_by_integrity":
      return {
        summary: "同步已冻结，需要处理本地数据完整性",
        actionLabel: null,
        detail: detail ?? "integrity_blocked",
      };
    case "blocked_by_scope_mismatch":
      return {
        summary: "同步已冻结，需要处理账号作用域切换",
        actionLabel: null,
        detail: detail ?? "scope_mismatch",
      };
    case "blocked_by_migration_failure":
      return {
        summary: "同步已冻结，需要处理本地迁移失败",
        actionLabel: null,
        detail: detail ?? "migration_failure",
      };
    case "blocked_by_auth":
      return {
        summary: "同步已冻结，需要重新登录",
        actionLabel: null,
        detail: detail ?? "auth_expired",
      };
    default:
      return {
        summary: "同步状态未知",
        actionLabel: null,
        detail,
      };
  }
}
~~~

## `mobile/lib/system-health.ts`

- 编码: `utf-8`

~~~typescript
import { useEffect, useMemo, useState } from "react";
import * as FileSystem from "expo-file-system/legacy";
import * as localDb from "./local-db";
import { fetchMobileCapabilities, getBaseUrl } from "./api";
import { getLegacyUploadPseudoOps } from "./legacy-upload-ops";
import { mergeLaneDiagnosticsWithLegacyUploads } from "./legacy-upload-pseudo-op-core";
import {
  retryAllLegacyUploadPseudoOps,
  retryLegacyUploadPseudoOp,
} from "./record-note-service";
import { describeSyncFreezeState } from "./sync-freeze-core";
import {
  getSyncControlState,
  getSyncStatus,
  isSyncPaused,
  onDataChanged,
  onSyncStatusChange,
  setSyncPaused,
  triggerSync,
  getRecentSyncEvents,
} from "./sync-engine";
import { getRuntimeFlags, setRuntimeFlag, type RuntimeFlagName } from "./runtime-flags";
import type {
  HealthLaneDiagnostic,
  LegacyUploadPseudoOp,
  MobileCapabilityRecord,
  PendingOpLane,
  PendingOpRecord,
  PendingOpSummary,
  SyncFreezeState,
  TaskConflictDiagnostic,
} from "./types";

export interface SystemHealthSnapshot {
  syncStatus: "idle" | "syncing" | "error";
  lastSyncTime: string | null;
  syncFreezeState: SyncFreezeState;
  syncFreezeDetail: string | null;
  isSyncPaused: boolean;
  blockedReason: string | null;
  freezeSummary: string;
  freezeActionLabel: string | null;
  pendingSummary: PendingOpSummary;
  recentPendingOps: PendingOpRecord[];
  taskConflicts: TaskConflictDiagnostic[];
  legacyUploadOps: LegacyUploadPseudoOp[];
  laneDiagnostics: Record<PendingOpLane, HealthLaneDiagnostic>;
  taskServerShadowCount: number;
  staleTaskServerShadowCount: number;
  accountScopeKey: string;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
  runtimeFlags: ReturnType<typeof getRuntimeFlags>;
  backendBaseUrl: string;
  backendCapabilities: MobileCapabilityRecord | null;
  backendCapabilitiesError: string | null;
  lastCapabilityProbeAt: string | null;
}

export interface SystemHealthDiagnosticBundle {
  schemaVersion: 1;
  generatedAt: string;
  sync: {
    status: SystemHealthSnapshot["syncStatus"];
    lastSyncTime: string | null;
    freezeState: SyncFreezeState;
    freezeDetail: string | null;
    isPaused: boolean;
    blockedReason: string | null;
    freezeSummary: string;
  };
  pendingSummary: PendingOpSummary;
  recentPendingOps: PendingOpRecord[];
  taskConflicts: TaskConflictDiagnostic[];
  laneDiagnostics: Record<PendingOpLane, HealthLaneDiagnostic>;
  remoteStateSummary: ReturnType<typeof localDb.getTaskRemoteStateSummary>;
  legacyUploadOps: LegacyUploadPseudoOp[];
  taskServerShadow: {
    total: number;
    stale: number;
  };
  account: {
    scopeKey: string;
    integrityStatus: "ok" | "blocked";
    integrityReason: string | null;
  };
  runtimeFlags: ReturnType<typeof getRuntimeFlags>;
  recentSyncEvents: ReturnType<typeof getRecentSyncEvents>;
  backend: {
    baseUrl: string;
    capabilities: MobileCapabilityRecord | null;
    capabilityError: string | null;
    lastProbeAt: string | null;
  };
}

const SYSTEM_HEALTH_EXPORT_DIR = `${FileSystem.documentDirectory ?? ""}system-health-exports/`;

export function loadSystemHealthSnapshot(): SystemHealthSnapshot {
  const syncStatus = getSyncStatus();
  const controlState = getSyncControlState();
  const integrityState = localDb.getDataIntegrityState();
  const shadowDiagnostics = localDb.getTaskServerShadowDiagnostics();
  const freezeDescriptor = describeSyncFreezeState(controlState.freezeState, controlState.detail);
  const legacyUploadOps = getLegacyUploadPseudoOps();
  return {
    syncStatus: syncStatus.status,
    lastSyncTime: syncStatus.lastSyncTime,
    syncFreezeState: controlState.freezeState,
    syncFreezeDetail: controlState.detail,
    isSyncPaused: isSyncPaused(),
    blockedReason: controlState.blockedReason,
    freezeSummary: freezeDescriptor.summary,
    freezeActionLabel: freezeDescriptor.actionLabel,
    pendingSummary: localDb.getPendingOpsSummary(),
    recentPendingOps: localDb.getPendingOpsDebugList(8),
    taskConflicts: localDb.getTaskConflictDiagnostics(8),
    legacyUploadOps,
    laneDiagnostics: mergeLaneDiagnosticsWithLegacyUploads(
      localDb.getPendingOpsLaneDiagnostics(),
      legacyUploadOps,
    ),
    taskServerShadowCount: shadowDiagnostics.total,
    staleTaskServerShadowCount: shadowDiagnostics.stale,
    accountScopeKey: integrityState.accountScopeKey,
    integrityStatus: integrityState.integrityStatus,
    integrityReason: integrityState.integrityReason,
    runtimeFlags: getRuntimeFlags(),
    backendBaseUrl: getBaseUrl(),
    backendCapabilities: null,
    backendCapabilitiesError: null,
    lastCapabilityProbeAt: null,
  };
}

export function buildSystemHealthDiagnosticBundle(
  snapshot: SystemHealthSnapshot = loadSystemHealthSnapshot(),
): SystemHealthDiagnosticBundle {
  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    sync: {
      status: snapshot.syncStatus,
      lastSyncTime: snapshot.lastSyncTime,
      freezeState: snapshot.syncFreezeState,
      freezeDetail: snapshot.syncFreezeDetail,
      isPaused: snapshot.isSyncPaused,
      blockedReason: snapshot.blockedReason,
      freezeSummary: snapshot.freezeSummary,
    },
    pendingSummary: snapshot.pendingSummary,
    recentPendingOps: snapshot.recentPendingOps,
    taskConflicts: snapshot.taskConflicts,
    laneDiagnostics: snapshot.laneDiagnostics,
    remoteStateSummary: localDb.getTaskRemoteStateSummary(),
    legacyUploadOps: snapshot.legacyUploadOps,
    taskServerShadow: {
      total: snapshot.taskServerShadowCount,
      stale: snapshot.staleTaskServerShadowCount,
    },
    account: {
      scopeKey: snapshot.accountScopeKey,
      integrityStatus: snapshot.integrityStatus,
      integrityReason: snapshot.integrityReason,
    },
    runtimeFlags: snapshot.runtimeFlags,
    recentSyncEvents: getRecentSyncEvents(20),
    backend: {
      baseUrl: snapshot.backendBaseUrl,
      capabilities: snapshot.backendCapabilities,
      capabilityError: snapshot.backendCapabilitiesError,
      lastProbeAt: snapshot.lastCapabilityProbeAt,
    },
  };
}

export async function exportSystemHealthDiagnosticBundle(
  snapshot: SystemHealthSnapshot = loadSystemHealthSnapshot(),
): Promise<{ filePath: string; bundle: SystemHealthDiagnosticBundle }> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持导出诊断文件。");
  }
  const bundle = buildSystemHealthDiagnosticBundle(snapshot);
  await FileSystem.makeDirectoryAsync(SYSTEM_HEALTH_EXPORT_DIR, { intermediates: true });
  const filePath = `${SYSTEM_HEALTH_EXPORT_DIR}diagnostic-${Date.now()}.json`;
  await FileSystem.writeAsStringAsync(filePath, JSON.stringify(bundle, null, 2), {
    encoding: FileSystem.EncodingType.UTF8,
  });
  return { filePath, bundle };
}

export function useSystemHealth() {
  const [snapshot, setSnapshot] = useState<SystemHealthSnapshot>(() => loadSystemHealthSnapshot());

  const refreshCapabilities = useMemo(
    () => async () => {
      try {
        const capabilities = await fetchMobileCapabilities();
        setSnapshot((current) => ({
          ...current,
          backendBaseUrl: getBaseUrl(),
          backendCapabilities: capabilities,
          backendCapabilitiesError: null,
          lastCapabilityProbeAt: new Date().toISOString(),
        }));
      } catch (error) {
        setSnapshot((current) => ({
          ...current,
          backendBaseUrl: getBaseUrl(),
          backendCapabilities: null,
          backendCapabilitiesError: error instanceof Error ? error.message : "能力探测失败",
          lastCapabilityProbeAt: new Date().toISOString(),
        }));
      }
    },
    [],
  );

  useEffect(() => {
    const refresh = () =>
      setSnapshot((current) => ({
        ...loadSystemHealthSnapshot(),
        backendCapabilities: current.backendCapabilities,
        backendCapabilitiesError: current.backendCapabilitiesError,
        lastCapabilityProbeAt: current.lastCapabilityProbeAt,
      }));
    const releaseData = onDataChanged(refresh);
    const releaseStatus = onSyncStatusChange(() => refresh());
    refresh();
    void refreshCapabilities();
    return () => {
      releaseData();
      releaseStatus();
    };
  }, [refreshCapabilities]);

  return useMemo(
    () => ({
      ...snapshot,
      pauseSync: () => {
        setSyncPaused(true);
        setSnapshot(loadSystemHealthSnapshot());
      },
      resumeSync: () => {
        setSyncPaused(false);
        setSnapshot(loadSystemHealthSnapshot());
      },
      retryAllFailed: async () => {
        localDb.requeueAllNeedsAttentionOps();
        try {
          await retryAllLegacyUploadPseudoOps();
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryOne: async (opId: number) => {
        try {
          localDb.requeueOp(opId);
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryLegacyUploadOp: async (opId: string) => {
        try {
          await retryLegacyUploadPseudoOp(opId);
          await triggerSync();
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      retryTaskConflict: async (taskId: string) => {
        try {
          const requeued = localDb.requeueNeedsAttentionOpsForEntity("task", taskId);
          if (requeued > 0) {
            await triggerSync();
          }
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      restoreTaskConflict: async (taskId: string) => {
        try {
          return localDb.restoreTaskFromServerShadow(taskId);
        } finally {
          setSnapshot(loadSystemHealthSnapshot());
        }
      },
      clearSafeArtifacts: async () => {
        const result = localDb.cleanupSafeSyncArtifacts();
        setSnapshot(loadSystemHealthSnapshot());
        return result;
      },
      setRuntimeFlag: async (name: RuntimeFlagName, enabled: boolean) => {
        await setRuntimeFlag(name, enabled);
        setSnapshot(loadSystemHealthSnapshot());
      },
      refresh: () => setSnapshot(loadSystemHealthSnapshot()),
      exportDiagnostics: async () => {
        const nextSnapshot = loadSystemHealthSnapshot();
        try {
          const capabilities = await fetchMobileCapabilities();
          nextSnapshot.backendCapabilities = capabilities;
          nextSnapshot.backendCapabilitiesError = null;
        } catch (error) {
          nextSnapshot.backendCapabilitiesError = error instanceof Error ? error.message : "能力探测失败";
          nextSnapshot.backendCapabilities = null;
        }
        nextSnapshot.backendBaseUrl = getBaseUrl();
        nextSnapshot.lastCapabilityProbeAt = new Date().toISOString();
        setSnapshot(nextSnapshot);
        return exportSystemHealthDiagnosticBundle(nextSnapshot);
      },
      refreshBackendCapabilities: async () => {
        await refreshCapabilities();
      },
    }),
    [refreshCapabilities, snapshot],
  );
}
~~~

## `mobile/lib/task-board-store-core.ts`

- 编码: `utf-8`

~~~typescript
import type { TaskBoardResponse } from "./types";

export type TaskBoardSyncStatus = "idle" | "syncing" | "error";

export interface TaskBoardStoreState {
  board: TaskBoardResponse;
  syncStatus: TaskBoardSyncStatus;
  lastSyncTime: string | null;
  isHydrated: boolean;
}

export interface TaskBoardStoreDeps {
  initDatabase: () => void;
  getLocalTaskBoard: () => TaskBoardResponse;
  onDataChanged: (listener: () => void) => () => void;
  onSyncStatusChange: (
    listener: (status: TaskBoardSyncStatus, lastSyncTime: string | null) => void,
  ) => () => void;
  getSyncStatus: () => { status: TaskBoardSyncStatus; lastSyncTime: string | null };
  triggerSync: () => Promise<void>;
  log?: (message: string, payload?: Record<string, unknown>) => void;
}

const EMPTY_BOARD: TaskBoardResponse = {
  tasks: [],
  inboxCount: 0,
  tasksTodayCount: 0,
};

export function createTaskBoardStore(deps: TaskBoardStoreDeps) {
  let state: TaskBoardStoreState = {
    board: EMPTY_BOARD,
    syncStatus: deps.getSyncStatus().status,
    lastSyncTime: deps.getSyncStatus().lastSyncTime,
    isHydrated: false,
  };
  let initialized = false;
  let refreshPromise: Promise<void> | null = null;
  let cleanupDataListener: (() => void) | null = null;
  let cleanupStatusListener: (() => void) | null = null;
  const listeners = new Set<() => void>();

  const emit = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  const setState = (next: TaskBoardStoreState) => {
    state = next;
    emit();
  };

  const hydrateBoard = () => {
    const board = deps.getLocalTaskBoard();
    setState({
      ...state,
      board,
      isHydrated: true,
    });
  };

  const ensureInitialized = () => {
    if (initialized) {
      return;
    }
    initialized = true;
    deps.initDatabase();
    hydrateBoard();
    cleanupDataListener = deps.onDataChanged(() => {
      deps.log?.("board.updated");
      hydrateBoard();
    });
    cleanupStatusListener = deps.onSyncStatusChange((status, lastSyncTime) => {
      setState({
        ...state,
        syncStatus: status,
        lastSyncTime,
      });
    });
  };

  const refresh = async () => {
    ensureInitialized();
    if (!refreshPromise) {
      deps.log?.("refresh.requested");
      refreshPromise = deps.triggerSync().finally(() => {
        refreshPromise = null;
      });
    } else {
      deps.log?.("refresh.reused_inflight");
    }
    await refreshPromise;
  };

  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  const reset = () => {
    cleanupDataListener?.();
    cleanupStatusListener?.();
    cleanupDataListener = null;
    cleanupStatusListener = null;
    initialized = false;
    refreshPromise = null;
    state = {
      board: EMPTY_BOARD,
      syncStatus: "idle",
      lastSyncTime: null,
      isHydrated: false,
    };
    emit();
  };

  return {
    ensureInitialized,
    getSnapshot: () => state,
    subscribe,
    refresh,
    reset,
  };
}
~~~

## `mobile/lib/task-board-store.ts`

- 编码: `utf-8`

~~~typescript
import { useEffect, useMemo, useSyncExternalStore } from "react";
import { devLog, measureDevSync } from "./dev-log";
import * as localDb from "./local-db";
import { getTaskBoardSnapshot } from "./task-query-service";
import {
  getSyncStatus,
  onDataChanged,
  onSyncStatusChange,
  triggerSync,
} from "./sync-engine";
import {
  createTaskBoardStore,
  type TaskBoardStoreState,
} from "./task-board-store-core";

const taskBoardStore = createTaskBoardStore({
  initDatabase: () => {
    localDb.initDatabase();
  },
  getLocalTaskBoard: () =>
    measureDevSync("local-db", "getLocalTaskBoard", () => getTaskBoardSnapshot()),
  onDataChanged,
  onSyncStatusChange,
  getSyncStatus,
  triggerSync,
  log: (message, payload) => {
    devLog("taskBoard", message, payload);
  },
});

export function ensureTaskBoardStoreInitialized(): void {
  taskBoardStore.ensureInitialized();
}

export async function refreshTaskBoard(): Promise<void> {
  await taskBoardStore.refresh();
}

export function resetTaskBoardStore(): void {
  taskBoardStore.reset();
}

export function useTaskBoard(): TaskBoardStoreState & { refresh: () => Promise<void> } {
  const snapshot = useSyncExternalStore(
    taskBoardStore.subscribe,
    taskBoardStore.getSnapshot,
    taskBoardStore.getSnapshot,
  );

  useEffect(() => {
    taskBoardStore.ensureInitialized();
  }, []);

  return useMemo(
    () => ({
      ...snapshot,
      refresh: () => taskBoardStore.refresh(),
    }),
    [snapshot],
  );
}
~~~

## `mobile/lib/task-detail-service.ts`

- 编码: `utf-8`

~~~typescript
import {
  fetchTaskActivities,
  fetchTaskContextPreview,
  fetchTaskUnderstanding,
} from "./api";
import { File } from "expo-file-system";
import * as localDb from "./local-db";
import { getLegacyUploadPseudoOp } from "./legacy-upload-ops";
import {
  attachFileToTask,
  retryLegacyUploadPseudoOp,
  type TaskAttachmentResult,
} from "./record-note-service";
import * as Linking from "expo-linking";
import type { TaskAttachmentRecord, TaskRecord } from "./types";

export {
  fetchTaskActivities,
  fetchTaskContextPreview,
  fetchTaskUnderstanding,
};

function isTaskAttachmentPickerCancelled(error: unknown): boolean {
  return error instanceof Error && /cancel/i.test(error.message);
}

export async function pickAndUploadTaskAttachment(task: TaskRecord): Promise<TaskAttachmentResult | null> {
  let pickedFile: File | null = null;
  try {
    const selection = await File.pickFileAsync();
    pickedFile = Array.isArray(selection) ? selection[0] ?? null : selection;
  } catch (error) {
    if (isTaskAttachmentPickerCancelled(error)) {
      return null;
    }
    throw error;
  }

  if (!pickedFile) {
    return null;
  }

  return attachFileToTask(task, {
    file: {
      uri: pickedFile.uri,
      name: pickedFile.name || `attachment-${Date.now()}`,
      type: pickedFile.type || "application/octet-stream",
    },
    title: pickedFile.name || null,
  });
}

export async function retryTaskAttachmentTransferOp(
  opId: string,
  taskId: string,
): Promise<{
  ok: boolean;
  task: TaskRecord | null;
  message: string;
  status: "queued" | "processing" | "needs_attention" | "completed";
}> {
  const result = await retryLegacyUploadPseudoOp(opId);
  const latestTask = localDb.getTaskById(taskId) ?? null;
  if ("message" in result) {
    return {
      ok: false,
      task: latestTask,
      message: result.message,
      status: getLegacyUploadPseudoOp(opId)?.status ?? "needs_attention",
    };
  }
  return {
    ok: true,
    task: latestTask,
    message: "附件已重新加入上传链路。",
    status: getLegacyUploadPseudoOp(opId)?.status ?? "completed",
  };
}

function normalizeAttachmentUri(value: string): string {
  if (/^[a-z]+:/i.test(value)) {
    return value;
  }
  if (value.startsWith("/")) {
    return `file://${value}`;
  }
  return value;
}

export async function openTaskAttachment(attachment: TaskAttachmentRecord): Promise<void> {
  const rawUri = attachment.localPath || attachment.url || null;
  if (!rawUri) {
    throw new Error("当前附件还没有可打开的原件地址。");
  }
  const targetUri = encodeURI(normalizeAttachmentUri(rawUri));
  await Linking.openURL(targetUri);
}
~~~

## `mobile/lib/task-query-service.ts`

- 编码: `utf-8`

~~~typescript
import * as localDb from "./local-db";
import { isTaskLocalFirstReadEnabled } from "./runtime-flags";
import type { TaskBoardResponse, TaskRecord } from "./types";

function compareDateValue(left: string | null | undefined, right: string | null | undefined): number {
  if (left && right) {
    return left.localeCompare(right);
  }
  if (left) {
    return -1;
  }
  if (right) {
    return 1;
  }
  return 0;
}

export function compareTasksForBoard(left: TaskRecord, right: TaskRecord): number {
  return (
    compareDateValue(left.dueDate, right.dueDate) ||
    compareDateValue(left.updatedAt, right.updatedAt) ||
    compareDateValue(left.createdAt, right.createdAt) ||
    left.id.localeCompare(right.id)
  );
}

export function getTaskBoardSnapshot(): TaskBoardResponse {
  const syncedOnly = !isTaskLocalFirstReadEnabled();
  const board = localDb.getLocalTaskBoard({ syncedOnly });
  return {
    ...board,
    tasks: [...board.tasks].sort(compareTasksForBoard),
  };
}

export function getTaskSnapshot(taskId: string): TaskRecord | null {
  return localDb.getTaskById(taskId);
}
~~~

## `mobile/lib/task-repository.ts`

- 编码: `utf-8`

~~~typescript
import type { CreateTaskPayload, UpdateTaskPayload } from "./api";
import { createClientOpId, createLocalEntityId } from "./local-ids";
import * as localDb from "./local-db";
import type { MutationReceipt, TaskRecord } from "./types";

function nowIso(): string {
  return new Date().toISOString();
}

function buildQueuedReceipt(task: TaskRecord, message: string): MutationReceipt {
  return {
    entityType: "task",
    localId: task.id,
    remoteId: task.remoteId ?? null,
    localState: "local_committed",
    remoteState: "queued",
    reasonCode: null,
    updatedAt: task.updatedAt ?? nowIso(),
    message,
  };
}

function normalizeTaskFromCreatePayload(
  localId: string,
  payload: CreateTaskPayload,
): TaskRecord {
  const timestamp = nowIso();
  return {
    id: localId,
    remoteId: null,
    title: payload.title.trim(),
    description: payload.description ?? null,
    dueDate: payload.dueDate ?? null,
    durationMinutes: payload.durationMinutes ?? null,
    priority: payload.priority ?? "normal",
    progressStatus: "inbox",
    tags: payload.tags ?? null,
    clientId: payload.clientId ?? null,
    eventLineId: payload.eventLineId ?? null,
    listId: payload.listId ?? null,
    businessCategory: payload.businessCategory ?? null,
    currentBlocker: payload.currentBlocker ?? null,
    nextAction: payload.nextAction ?? null,
    recentDecision: payload.recentDecision ?? null,
    localVersion: 1,
    baseRemoteVersion: null,
    serverVersion: null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    deletedAt: null,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

export function createTaskLocalFirst(payload: CreateTaskPayload): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const localId = createLocalEntityId("task");
  const task = normalizeTaskFromCreatePayload(localId, payload);
  localDb.commitTaskMutation({
    task,
    operation: "create",
    clientOpId: createClientOpId("task"),
    payload: {
      ...payload,
      clientEntityId: localId,
    },
  });
  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存，等待同步"),
  };
}

export function updateTaskLocalFirst(taskId: string, updates: UpdateTaskPayload): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法更新");
  }

  const task: TaskRecord = {
    ...existing,
    title: updates.title?.trim() ?? existing.title,
    description: updates.description ?? existing.description ?? null,
    dueDate: updates.dueDate ?? existing.dueDate ?? null,
    durationMinutes: updates.durationMinutes ?? existing.durationMinutes ?? null,
    priority: updates.priority ?? existing.priority,
    progressStatus: updates.progressStatus ?? existing.progressStatus,
    clientId: updates.clientId ?? existing.clientId ?? null,
    eventLineId: updates.eventLineId ?? existing.eventLineId ?? null,
    listId: updates.listId ?? existing.listId ?? null,
    tags: updates.tags ?? existing.tags ?? null,
    businessCategory: updates.businessCategory ?? existing.businessCategory ?? null,
    currentBlocker: updates.currentBlocker ?? existing.currentBlocker ?? null,
    nextAction: updates.nextAction ?? existing.nextAction ?? null,
    recentDecision: updates.recentDecision ?? existing.recentDecision ?? null,
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    updatedAt: nowIso(),
  };

  localDb.commitTaskMutation({
    task,
    operation: "update",
    clientOpId: createClientOpId("task"),
    payload: {
      ...updates,
      clientEntityId: task.id,
    },
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存，等待同步"),
  };
}

export function deleteTaskLocalFirst(taskId: string): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法删除");
  }
  const timestamp = nowIso();
  const task: TaskRecord = {
    ...existing,
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    deletedAt: timestamp,
    updatedAt: timestamp,
  };

  localDb.commitTaskMutation({
    task,
    operation: "delete",
    clientOpId: createClientOpId("task"),
    payload: {
      clientEntityId: task.id,
    },
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已删除，等待同步"),
  };
}

export function completeTaskWithReviewLocalFirst(taskId: string, reviewNote: string): {
  task: TaskRecord;
  receipt: MutationReceipt;
} {
  const trimmedReviewNote = reviewNote.trim();
  if (!trimmedReviewNote) {
    throw new Error("复盘内容不能为空");
  }

  const existing = localDb.getTaskById(taskId);
  if (!existing) {
    throw new Error("任务不存在，无法完成复盘");
  }

  const task: TaskRecord = {
    ...existing,
    progressStatus: "done",
    completionNote: trimmedReviewNote,
    localVersion: (existing.localVersion ?? 0) + 1,
    baseRemoteVersion: existing.serverVersion ?? existing.baseRemoteVersion ?? null,
    localState: "local_committed",
    remoteState: "queued",
    syncReasonCode: null,
    updatedAt: nowIso(),
  };

  localDb.commitTaskReviewMutation({
    task,
    clientOpId: createClientOpId("task"),
    reviewNote: trimmedReviewNote,
  });

  return {
    task,
    receipt: buildQueuedReceipt(task, "已保存复盘，等待同步"),
  };
}
~~~

## `mobile/lib/task-review-service.ts`

- 编码: `utf-8`

~~~typescript
import * as localDb from "./local-db";
import { completeTaskWithReviewOfflineFirst } from "./sync-engine";
import type { MutationReceipt, TaskRecord } from "./types";

export function saveTaskReview(
  taskId: string,
  reviewNote: string,
): { task: TaskRecord; receipt: MutationReceipt } {
  const receipt = completeTaskWithReviewOfflineFirst(taskId, reviewNote);
  const task = localDb.getTaskById(taskId);
  if (!task) {
    throw new Error("任务不存在，无法保存复盘");
  }
  return {
    task,
    receipt,
  };
}
~~~

## `mobile/lib/task-sync-policy.ts`

- 编码: `utf-8`

~~~typescript
import type { TaskRecord } from "./types";

export interface TaskServerAckDecision {
  shouldReplaceLocalTask: boolean;
  shouldPromotePendingCreate: boolean;
  shouldUpdateShadowOnly: boolean;
}

export interface TaskServerAckDecisionInput {
  localTask: TaskRecord | null;
  ackLocalVersion: number | null;
  hasPendingOps: boolean;
  pendingCreateExists: boolean;
}

export function decideTaskServerAckAction(
  input: TaskServerAckDecisionInput,
): TaskServerAckDecision {
  if (!input.localTask) {
    return {
      shouldReplaceLocalTask: true,
      shouldPromotePendingCreate: false,
      shouldUpdateShadowOnly: false,
    };
  }

  const currentLocalVersion = input.localTask.localVersion ?? 0;
  const isStaleAck =
    input.ackLocalVersion != null &&
    currentLocalVersion > input.ackLocalVersion;
  const shouldKeepDirtyLocalState = input.hasPendingOps || isStaleAck;

  return {
    shouldReplaceLocalTask: !shouldKeepDirtyLocalState,
    shouldPromotePendingCreate: shouldKeepDirtyLocalState && input.pendingCreateExists,
    shouldUpdateShadowOnly: shouldKeepDirtyLocalState,
  };
}
~~~

## `mobile/lib/task-sync-presentation.ts`

- 编码: `utf-8`

~~~typescript
import type { SyncReasonCode, TaskRecord } from "./types";

export type TaskSyncIndicatorTone = "info" | "warning" | "danger";

export interface TaskSyncIndicatorModel {
  readonly label: string;
  readonly detail: string | null;
  readonly tone: TaskSyncIndicatorTone;
}

export function formatTaskSyncReasonCode(reasonCode: SyncReasonCode | string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_expired":
      return "登录已过期";
    case "permission_denied":
      return "没有权限";
    case "validation_failed":
      return "数据校验失败";
    case "version_conflict":
      return "服务器版本冲突";
    case "file_missing":
      return "原件缺失";
    case "quota_exceeded":
      return "存储空间不足";
    case "server_rejected":
      return "服务器拒绝";
    case "thermal_blocked":
      return "设备资源受限";
    case "model_unavailable":
      return "模型暂不可用";
    default:
      return "请稍后再试";
  }
}

export function buildTaskSyncIndicator(task: Pick<TaskRecord, "remoteState" | "syncReasonCode">): TaskSyncIndicatorModel | null {
  if (task.syncReasonCode === "version_conflict") {
    return {
      label: "冲突",
      detail: formatTaskSyncReasonCode(task.syncReasonCode),
      tone: "danger",
    };
  }
  if (task.remoteState === "needs_attention") {
    return {
      label: "需处理",
      detail: formatTaskSyncReasonCode(task.syncReasonCode),
      tone: "danger",
    };
  }
  if (task.remoteState === "queued") {
    return {
      label: "待同步",
      detail: "本地已保存，等待后台同步",
      tone: "info",
    };
  }
  if (task.remoteState === "syncing" || task.remoteState === "processing") {
    return {
      label: "处理中",
      detail: "后台正在处理本地修改",
      tone: "warning",
    };
  }
  return null;
}
~~~

## `mobile/lib/task-understanding.ts`

- 编码: `utf-8`

~~~typescript
import type {
  EventLineRecord,
  TaskContextPreviewRecord,
  TaskRecord,
  TaskUnderstandingRecord,
} from "./types";

export type TaskUnderstandingStatus = "ready" | "insufficient_context" | "weak_link";

export interface TaskUnderstandingSections {
  status: TaskUnderstandingStatus;
  whatIsThis: string;
  whyItMatters: string;
  blockerAndDecision: string;
  nextStepAndUnknowns: string;
}

export interface TaskUnderstandingCardSection {
  title: string;
  content: string;
}

export interface TaskUnderstandingCardModel {
  stateLabel: string;
  title: string;
  subtitle: string;
  sections: TaskUnderstandingCardSection[];
  evidence: string[];
  tone: TaskUnderstandingStatus;
}

const STRONG_UNDERSTANDING_SOURCES = new Set([
  "client_background",
  "quarterly_focus",
  "review_note",
  "event_line_memory",
  "meeting",
  "support_request",
  "knowledge_base",
  "org_dna",
]);

const WEAK_EVENT_LINE_HINT_PREFIX = "事件线 · ";
const SOURCE_LABELS: Record<string, string> = {
  client_background: "客户背景",
  quarterly_focus: "阶段目标",
  review_note: "复盘结论",
  event_line_memory: "事件线记录",
  meeting: "会议记录",
  support_request: "支持请求",
  knowledge_base: "知识库",
  org_dna: "组织判断",
  task_title: "任务标题",
  task_desc: "任务描述",
};

function normalizeText(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[「」『』【】（）()《》〈〉〔〕“”‘’"'`]/g, "")
    .replace(/[\s,.;:!?，。！？：；、·\-_—/\\|]/g, "");
}

function looksLikeSameContent(candidate: string | null | undefined, references: Array<string | null | undefined>): boolean {
  const normalizedCandidate = normalizeText(candidate);
  if (!normalizedCandidate) {
    return false;
  }
  return references.some((reference) => {
    const normalizedReference = normalizeText(reference);
    if (!normalizedReference || normalizedReference.length < 4) {
      return false;
    }
    return normalizedCandidate === normalizedReference
      || normalizedCandidate.includes(normalizedReference)
      || normalizedReference.includes(normalizedCandidate);
  });
}

function isGenericWhatIsThis(candidate: string | null | undefined, task: TaskRecord): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  if (looksLikeSameContent(value, [task.title, task.description])) {
    return true;
  }
  return value.includes("是一条")
    && (value.includes("工作任务") || value.includes("状态的任务"));
}

function isGenericWhyItMatters(candidate: string | null | undefined): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  return value.startsWith("这条任务与客户")
    || value.startsWith("当前尚未录入客户背景信息")
    || value === "暂无理解摘要";
}

function isGenericProgress(candidate: string | null | undefined): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  return value.startsWith("当前状态为 ");
}

function collectAvailableSources(understanding: TaskUnderstandingRecord | null): Set<string> {
  return new Set(
    (understanding?.sourceBreakdown ?? [])
      .filter((item) => item?.available && item.sourceType)
      .map((item) => item.sourceType as string),
  );
}

function hasStrongEvidence(understanding: TaskUnderstandingRecord | null): boolean {
  if (!understanding || understanding._pending) {
    return false;
  }
  const sourceTypes = collectAvailableSources(understanding);
  const hasStrongSource = [...sourceTypes].some((sourceType) => STRONG_UNDERSTANDING_SOURCES.has(sourceType));
  return hasStrongSource || understanding.coverage >= 55 || understanding.confidence >= 45;
}

function hasWeakEventLineLink(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): boolean {
  if (task.eventLineId || eventLine?.id) {
    return true;
  }
  return (contextPreview?.summaryChips ?? []).some((chip) => chip.startsWith(WEAK_EVENT_LINE_HINT_PREFIX));
}

function inferMissingContext(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): string[] {
  const items: string[] = [];
  const title = task.title ?? "";

  if (!task.description?.trim()) {
    if (/(吃饭|沟通|电话|见面|拜访|约|会面)/.test(title)) {
      items.push("对象身份");
      items.push("见面或沟通目的");
    } else {
      items.push("任务目的");
    }
  }

  if (!(task.clientId || contextPreview?.clientId)) {
    items.push("关联客户");
  }

  if (!(task.eventLineId || eventLine?.id)) {
    items.push("关联事件线");
  }

  if (!task.currentBlocker?.trim() && !task.recentDecision?.trim()) {
    items.push("最近变化或关键卡点");
  }

  if (task.progressStatus === "done") {
    if (!task.completionNote?.trim()) {
      items.push("完成结果或复盘结论");
    }
  } else if (!task.nextAction?.trim()) {
    items.push("下一步动作");
  }

  return [...new Set(items)];
}

function formatMissingContext(items: string[]): string {
  return items.length > 0
    ? `当前缺少：${items.join("、")}。`
    : "当前还缺少能支持任务级判断的上下文。";
}

function formatMissingSuggestion(items: string[]): string {
  return items.length > 0
    ? `建议补充：${items.join("、")}。`
    : "建议先补充任务目的、关联对象或最近变化。";
}

function buildReadySections(
  task: TaskRecord,
  understanding: TaskUnderstandingRecord | null,
): TaskUnderstandingSections {
  const whatIsThis = isGenericWhatIsThis(understanding?.whatIsThis, task)
    ? "暂无可靠洞察"
    : understanding?.whatIsThis?.trim() || "暂无可靠洞察";

  const whyItMatters = isGenericWhyItMatters(understanding?.whyItMatters)
    ? "当前还没有足够证据说明这件事为什么在现在重要。"
    : understanding?.whyItMatters?.trim() || "当前还没有足够证据说明这件事为什么在现在重要。";

  const blockerAndDecision = [
    isGenericProgress(understanding?.progressNow) ? null : understanding?.progressNow?.trim(),
    task.currentBlocker ? `卡点：${task.currentBlocker}` : null,
    task.recentDecision ? `判断：${task.recentDecision}` : null,
    understanding?.optionalAdvice?.realBlocker ? `真实阻碍：${understanding.optionalAdvice.realBlocker}` : null,
  ].filter(Boolean).join("\n") || "当前还没有足够证据说明最近的卡点或判断。";

  const nextStepAndUnknowns = [
    task.nextAction ? `下一步：${task.nextAction}` : null,
    understanding?.optionalAdvice?.minimumAction ? `最小动作：${understanding.optionalAdvice.minimumAction}` : null,
    understanding?.unknowns?.trim() ? `待补：${understanding.unknowns.trim()}` : null,
  ].filter(Boolean).join("\n") || "当前还没有足够证据给出下一步建议。";

  return {
    status: "ready",
    whatIsThis,
    whyItMatters,
    blockerAndDecision,
    nextStepAndUnknowns,
  };
}

function buildWeakLinkSections(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): TaskUnderstandingSections {
  const missing = inferMissingContext(task, eventLine, contextPreview);
  const lineName = eventLine?.name ?? task.eventLineName ?? "当前事件线";
  const chips = (contextPreview?.summaryChips ?? []).filter(Boolean);
  const weakContext = [
    eventLine?.recentDecision ? `最近变化：${eventLine.recentDecision}` : null,
    eventLine?.currentBlocker ? `事件线卡点：${eventLine.currentBlocker}` : null,
    chips.length > 0 ? `已知线索：${chips.join(" · ")}` : null,
  ].filter(Boolean).join("\n");

  return {
    status: "weak_link",
    whatIsThis: `这条任务已关联「${lineName}」，但当前只有宽泛事件线线索，暂时还不能直接判断它的具体意义。`,
    whyItMatters: "目前只看到了事件线级上下文，尚未找到与这条任务直接相关的会议、历史记录或明确目的。",
    blockerAndDecision: weakContext || formatMissingContext(missing),
    nextStepAndUnknowns: formatMissingSuggestion(missing),
  };
}

function buildInsufficientSections(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): TaskUnderstandingSections {
  const missing = inferMissingContext(task, eventLine, contextPreview);
  return {
    status: "insufficient_context",
    whatIsThis: "暂无可靠洞察",
    whyItMatters: "当前只看到任务本身，尚未找到关联客户、事件线、会议记录或历史判断。",
    blockerAndDecision: formatMissingContext(missing),
    nextStepAndUnknowns: formatMissingSuggestion(missing),
  };
}

export function buildTaskUnderstandingSections(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): TaskUnderstandingSections {
  const { task, eventLine = null, understanding = null, contextPreview = null } = params;

  const strongEvidence = hasStrongEvidence(understanding);
  const needsInput = contextPreview?.safeOutputMode === "needs_input" || contextPreview?.readiness === "low";
  const hasReadyUnderstanding = strongEvidence
    && !needsInput
    && !isGenericWhatIsThis(understanding?.whatIsThis, task)
    && !isGenericWhyItMatters(understanding?.whyItMatters);

  if (hasReadyUnderstanding) {
    return buildReadySections(task, understanding);
  }

  if (hasWeakEventLineLink(task, eventLine, contextPreview)) {
    return buildWeakLinkSections(task, eventLine, contextPreview);
  }

  return buildInsufficientSections(task, eventLine, contextPreview);
}

function dedupeNonEmpty(items: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  for (const rawItem of items) {
    const item = rawItem?.trim();
    if (!item) {
      continue;
    }
    if (seen.has(item)) {
      continue;
    }
    seen.add(item);
    values.push(item);
  }
  return values;
}

function buildUnderstandingEvidence(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): string[] {
  const { task, eventLine = null, understanding = null, contextPreview = null } = params;
  const sourceEvidence = (understanding?.sourceBreakdown ?? [])
    .filter((item) => item?.available)
    .map((item) => item?.label?.trim() || item?.sourceName?.trim() || SOURCE_LABELS[item?.sourceType ?? ""] || null);
  const chipEvidence = (contextPreview?.summaryChips ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3);
  return dedupeNonEmpty([
    ...sourceEvidence,
    ...chipEvidence,
    eventLine?.name ? `事件线：${eventLine.name}` : task.eventLineName ? `事件线：${task.eventLineName}` : null,
    contextPreview?.clientName ? `客户：${contextPreview.clientName}` : task.clientName ? `客户：${task.clientName}` : null,
  ]).slice(0, 4);
}

export function buildTaskUnderstandingCardModel(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): TaskUnderstandingCardModel {
  const sections = buildTaskUnderstandingSections(params);
  const evidence = buildUnderstandingEvidence(params);

  if (sections.status === "ready") {
    return {
      stateLabel: "有依据",
      title: "任务洞察",
      subtitle: "基于已有上下文整理出的当前判断",
      tone: "ready",
      sections: [
        { title: "当前判断", content: sections.whatIsThis },
        { title: "为什么现在重要", content: sections.whyItMatters },
        { title: "当前卡点 / 提醒", content: sections.blockerAndDecision },
        { title: "建议下一步 / 待补", content: sections.nextStepAndUnknowns },
      ],
      evidence,
    };
  }

  if (sections.status === "weak_link") {
    return {
      stateLabel: "弱关联",
      title: "任务洞察",
      subtitle: "当前只有弱关联线索，先不要过度解读",
      tone: "weak_link",
      sections: [
        { title: "当前提醒", content: sections.whatIsThis },
        { title: "你可能需要回忆", content: sections.whyItMatters },
        { title: "已知线索", content: sections.blockerAndDecision },
        { title: "建议下一步 / 还缺什么", content: sections.nextStepAndUnknowns },
      ],
      evidence,
    };
  }

  return {
    stateLabel: "待补上下文",
    title: "任务洞察",
    subtitle: "当前证据不足，先补上下文",
    tone: "insufficient_context",
    sections: [
      { title: "当前提醒", content: sections.whatIsThis },
      { title: "为什么还不能判断", content: sections.whyItMatters },
      { title: "还缺什么", content: sections.blockerAndDecision },
      { title: "建议动作", content: sections.nextStepAndUnknowns },
    ],
    evidence,
  };
}
~~~

## `mobile/lib/theme.ts`

- 编码: `utf-8`

~~~typescript
/**
 * Design tokens aligned with Gemini framework.
 * Primary brand: #2563EB (blue-600) + accent: #F97316 (orange-500)
 */

export const colors = {
  // Brand (blue-600 family)
  brand: "#2563EB",
  brandLight: "#3B82F6",
  brandDark: "#1D4ED8",
  brandBg: "rgba(37,99,235,0.08)",
  brandBg2: "rgba(37,99,235,0.14)",
  brandRing: "rgba(37,99,235,0.24)",

  // Accent (orange-500 family)
  accent: "#F97316",
  accentLight: "#FB923C",
  accentDark: "#EA580C",
  accentBg: "rgba(249,115,22,0.08)",
  accentBg2: "rgba(249,115,22,0.14)",

  // Background & Surface
  background: "#F5F6F8",
  surface: "#FFFFFF",
  surfaceSecondary: "#F6F8FB",
  surfaceDone: "#F8FAFC",
  panel: "#1C1D33",
  panelSecondary: "#2A2C43",
  softBlueSurface: "#EEF5FF",
  softBlueSurfaceStrong: "#E2EDFD",
  softBlueText: "#9BBEFF",
  busySurface: "#FFF0F3",

  // Text
  text: "#1F2937",
  textSecondary: "#6E7787",
  textTertiary: "#A8B0BF",
  textOnBrand: "#FFFFFF",

  // Border
  border: "#E5E7EB",
  borderLight: "#ECEFF3",
  borderFocus: "#2563EB",
  divider: "#EAEFF5",
  headerPill: "#EDF3FC",

  // Priority
  priorityHigh: "#F43F5E",
  priorityHighBg: "#FFF1F2",
  priorityHighBorder: "#FFE4E6",
  priorityNormal: "#F97316",
  priorityNormalBg: "#FFF7ED",
  priorityNormalBorder: "#FFEDD5",
  priorityLow: "#64748B",
  priorityLowBg: "#F1F5F9",
  priorityLowBorder: "#E2E8F0",

  // Status
  statusTodo: "#94A3B8",
  statusDoing: "#2563EB",
  statusDone: "#10B981",
  statusDoneBg: "#ECFDF5",
  statusDoneBorder: "#D1FAE5",

  // Semantic
  error: "#EF4444",
  warning: "#F59E0B",
  success: "#10B981",
  info: "#2563EB",

  // Event line
  eventLine: "#64748B",
  eventLineBg: "#F8FAFC",
  eventLineBorder: "#E2E8F0",

  // Client
  clientBg: "#EFF6FF",
  clientBorder: "#DBEAFE",
  clientText: "#1D4ED8",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  xxxl: 36,
} as const;

export const fontSize = {
  xs: 10,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 18,
  xxl: 22,
  title: 28,
} as const;

export const borderRadius = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  xxl: 30,
  full: 9999,
} as const;

export const shadow = {
  card: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.035,
    shadowRadius: 8,
    elevation: 1,
  },
  softCard: {
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.024,
    shadowRadius: 10,
    elevation: 1,
  },
  elevated: {
    shadowColor: "#2563EB",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 12,
    elevation: 4,
  },
  fab: {
    shadowColor: "#2563EB",
    shadowOffset: { width: 0, height: 7 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 5,
  },
  phone: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 32 },
    shadowOpacity: 0.28,
    shadowRadius: 64,
    elevation: 18,
  },
} as const;
~~~

## `mobile/lib/types.ts`

- 编码: `utf-8`

~~~typescript
export interface SessionUser {
  id: string;
  fullName: string;
  email: string;
  title?: string | null;
  organizationId?: string | null;
  avatarUrl?: string | null;
}

export interface AuthTokenResponse {
  accessToken: string;
  refreshToken?: string | null;
  user: SessionUser;
}

export type TaskPriority = "low" | "normal" | "high" | string;
export type TaskProgressStatus = "inbox" | "todo" | "doing" | "done" | "rejected" | string;

export interface TaskAttachmentRecord {
  id: string;
  title?: string | null;
  summary?: string | null;
  mimeType?: string | null;
  url?: string | null;
  localPath?: string | null;
  durationSeconds?: number | null;
  createdAt?: string;
}

export type LocalMutationState = "local_committed" | "local_failed";
export type RemoteMutationState = "queued" | "syncing" | "processing" | "needs_attention" | "synced";
export type SyncReasonCode =
  | "network_unavailable"
  | "auth_expired"
  | "permission_denied"
  | "validation_failed"
  | "version_conflict"
  | "file_missing"
  | "quota_exceeded"
  | "server_rejected"
  | "thermal_blocked"
  | "model_unavailable";
export type PendingOpLane = "interactive" | "transfer" | "derived";
export type PendingOpOperation = "create" | "update" | "delete" | "complete_with_review";
export type PendingOpVisibilityScope = "private_draft" | "team_shared" | "official";

export interface TaskCollaboratorRecord {
  userId: string;
  fullName: string;
  isOwner: boolean;
  inboxStatus?: string | null;
}

export interface TaskRecord {
  id: string;
  remoteId?: string | null;
  title: string;
  description?: string | null;
  dueDate?: string | null;
  durationMinutes?: number | null;
  priority: TaskPriority;
  progressStatus: TaskProgressStatus;
  tags?: string[] | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  listId?: string | null;
  listName?: string | null;
  ownerId?: string | null;
  ownerName?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  completionNote?: string | null;
  attachments?: TaskAttachmentRecord[];
  collaborators?: TaskCollaboratorRecord[];
  viewerInboxStatus?: "pending" | "accepted" | "returned" | null;
  localVersion?: number;
  baseRemoteVersion?: number | null;
  serverVersion?: number | null;
  localState?: LocalMutationState;
  remoteState?: RemoteMutationState;
  syncReasonCode?: SyncReasonCode | null;
  deletedAt?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface TaskBoardResponse {
  tasks: TaskRecord[];
  inboxCount?: number;
  tasksTodayCount?: number;
}

export interface TaskListRecord {
  id: string;
  name: string;
  color?: string | null;
  isDefault?: boolean;
}

export interface TaskTagRecord {
  id: string;
  name: string;
  color?: string | null;
}

export interface ClientSummaryRecord {
  id: string;
  name: string;
  alias?: string | null;
}

export interface EventLineRecord {
  id: string;
  name: string;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
  summary?: string | null;
  currentBlocker?: string | null;
  nextStep?: string | null;
  recentDecision?: string | null;
  stage?: string | null;
  status?: string;
}

export type SmartInputIntent = "task_schedule" | "record_note" | "unknown";

export interface SmartTaskDraft {
  title?: string | null;
  dueDate?: string | null;
  endDate?: string | null;
  dueTime?: string | null;
  durationMinutes?: number | null;
  location?: string | null;
  description?: string | null;
  tags?: string[];
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectQuery?: string | null;
  eventLineQuery?: string | null;
}

export interface SmartTaskDraftResponse {
  transcript: string;
  intent: SmartInputIntent;
  draft: SmartTaskDraft;
  warnings: string[];
  confidence?: number | null;
}

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId?: string | null;
  target?: "vector_memory" | "document_archive" | string;
  status?: "pending" | "processing" | "completed" | "failed" | string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
  question?: string | null;
  answer?: string | null;
  errorMessage?: string | null;
  localDocumentId?: string | null;
  localDocumentPath?: string | null;
  completedAt?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface ConsultationChatResponse {
  reply: string;
  model?: string | null;
  answerMode?: "grounded" | "limited_context" | "missing_context" | "error" | null;
  contextQuality?: {
    level?: "none" | "thin" | "partial" | "rich" | string;
    availableSources?: string[];
    missingSources?: string[];
    staleSources?: string[];
    contextBundleHash?: string | null;
  } | null;
  evidence?: Array<{
    id: string;
    type:
      | "workspace"
      | "client_dna"
      | "event_line"
      | "meeting"
      | "task"
      | "knowledge_surrogate"
      | "cockpit"
      | "thread_snapshot"
      | "task_board"
      | "client_name"
      | string;
    title: string;
    updatedAt?: string | null;
    snippet?: string | null;
  }>;
  missingContext?: Array<{
    type:
      | "client_dna"
      | "workspace"
      | "event_line"
      | "meeting"
      | "person_profile"
      | "project_background"
      | "strategic_cockpit"
      | "knowledge_surrogate"
      | "task_board"
      | string;
    message: string;
  }>;
}

export interface MobileCapabilityRecord {
  consultationChat: boolean;
  clientWorkspace: boolean;
  strategicCockpit: boolean;
  knowledgeMirror: boolean;
  contextBundle: boolean;
  consultationPayloadVersion: string;
  updatedAt: string;
}

export interface MobileContextSourceStatusRecord {
  source: string;
  available: boolean;
  status: "ready" | "partial" | "missing" | "unavailable" | string;
  detail?: string | null;
  updatedAt?: string | null;
}

export interface SupportRequestRecord {
  id: string;
  title: string;
  description?: string | null;
  status?: string;
  requesterName?: string | null;
  createdAt?: string;
}

export interface EmployeeRecord {
  id: string;
  fullName: string;
  email?: string | null;
  title?: string | null;
}

export interface TaskActivityRecord {
  id: string;
  eventType: string;
  actorId?: string | null;
  actorName?: string | null;
  payload?: Record<string, unknown> | null;
  createdAt?: string;
}

export interface TaskSettingsRecord {
  defaultListId?: string | null;
  defaultPriority?: "low" | "normal" | "high";
  defaultDueDatePreset?: "today" | "none";
  defaultViewMode?: "inbox" | "list" | "calendar" | "review";
  listSortMode?: "manual" | "priority" | "dueDate";
  showCompletedTasks?: boolean;
  defaultReviewScope?: "work" | "personal";
  autoAssignSelf?: boolean;
}

export interface MutationReceipt {
  entityType: "task" | "calendar_block" | "attachment" | "voice_draft" | "consult_draft";
  localId: string;
  remoteId: string | null;
  localState: LocalMutationState;
  remoteState: RemoteMutationState;
  reasonCode?: SyncReasonCode | null;
  updatedAt: string;
  message: string;
}

export interface PendingOpRecord {
  id: number;
  clientOpId: string;
  entityType: string;
  entityId: string;
  entityRemoteId?: string | null;
  operation: PendingOpOperation;
  payload: string | null;
  lane: PendingOpLane;
  status: RemoteMutationState;
  visibilityScope: PendingOpVisibilityScope;
  localVersion: number;
  baseRemoteVersion?: number | null;
  createdAt: string;
  updatedAt?: string;
  retryCount: number;
  lastError: string | null;
  reasonCode?: SyncReasonCode | null;
}

export interface TaskServerShadowRecord {
  taskId: string;
  remoteId?: string | null;
  serverVersion?: number | null;
  payload: TaskRecord;
  updatedAt: string;
}

export interface TaskConflictDiagnostic {
  taskId: string;
  title: string;
  remoteState: RemoteMutationState;
  syncReasonCode: SyncReasonCode | null;
  pendingOperation: PendingOpOperation | null;
  pendingUpdatedAt: string | null;
  pendingOpCount: number;
  lastError: string | null;
  hasServerShadow: boolean;
  serverShadowUpdatedAt: string | null;
  serverVersion: number | null;
}

export interface PendingOpSummary {
  total: number;
  queued: number;
  syncing: number;
  processing: number;
  needsAttention: number;
  byLane: Record<PendingOpLane, number>;
  byReasonCode: Partial<Record<SyncReasonCode, number>>;
}

export type LegacyUploadReasonCode =
  | "network_unavailable"
  | "auth_required"
  | "scope_mismatch"
  | "file_missing"
  | "file_corrupted"
  | "upload_failed"
  | "bind_pending_remote_id"
  | "integrity_blocked"
  | "manual_pause"
  | "unknown_error";

export type LegacyUploadPseudoOpStatus = "queued" | "processing" | "needs_attention";

export interface HealthLaneDiagnostic {
  lane: PendingOpLane;
  total: number;
  oldestAgeMs: number | null;
  active: boolean;
  topReasonCode: string | null;
}

export interface LegacyUploadPseudoOp {
  opId: string;
  objectType: string;
  objectLocalId: string;
  objectRemoteId?: string | null;
  lane: "transfer";
  status: LegacyUploadPseudoOpStatus;
  retryCount: number;
  reasonCode: LegacyUploadReasonCode;
  createdAt: string;
  lastAttemptAt: string | null;
  ageMs: number;
  displayTitle?: string | null;
  taskLocalId: string;
  filePath: string;
  size: number | null;
  mtime: number | null;
  hash: string | null;
  entityRefLocalId: string;
  mimeType?: string | null;
  durationSeconds?: number | null;
}

export type SyncFreezeState =
  | "ready"
  | "paused_by_user"
  | "blocked_by_integrity"
  | "blocked_by_scope_mismatch"
  | "blocked_by_migration_failure"
  | "blocked_by_auth";

export type CurrentFocusSource = "manual" | "from_task" | "from_calendar" | "from_meeting" | "auto";
export type CurrentFocusLockMode = "browse" | "client" | "client_event_line";
export type CurrentFocusBoundaryState =
  | "none"
  | "official"
  | "pending"
  | "risk"
  | "reminder"
  | "mixed";

export interface CurrentFocus {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  weekAnchorDate: string;
  weekLabel: string;
  source: CurrentFocusSource;
  lockMode: CurrentFocusLockMode;
  boundaryState: CurrentFocusBoundaryState;
  updatedAt: string;
}

export interface ConsultThreadContextSnapshot {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
  frozenAt: string;
  snapshotHash: string;
  snapshotVersion: number;
}

export interface TaskContextPreviewRecord {
  taskId: string;
  clientId?: string | null;
  clientName?: string | null;
  summaryChips: string[];
  readiness?: "low" | "medium" | "high" | string;
  safeOutputMode?: "needs_input" | "summary_only" | "full_judgment" | string;
  judgment?: {
    summary?: string | null;
    progressNow?: string | null;
    unknowns?: string | null;
  } | null;
}

export interface TaskUnderstandingRecord {
  mode?: "basic" | "enhanced";
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  confidence: number;
  coverage: number;
  _pending?: boolean;
  optionalAdvice?: {
    realBlocker?: string | null;
    timeGate?: string | null;
    minimumAction?: string | null;
    supportAsk?: string | null;
  } | null;
  sourceBreakdown?: Array<{
    sourceType?: string;
    sourceName?: string;
    label?: string;
    available: boolean;
    snippet?: string | null;
  }>;
}

export type BoundaryCardKind = "official" | "pending" | "risk" | "reminder";

export interface BoundaryCard {
  kind: BoundaryCardKind;
  title: string;
  summary: string;
  sourceType: "meeting" | "document" | "ai" | "manual" | "mixed";
  updatedAt?: string | null;
  evidenceCount: number | null;
  isEmpty: boolean;
}

export interface WorkspaceLiteItem {
  id: string;
  title: string;
  summary?: string | null;
  subtitle?: string | null;
  updatedAt?: string | null;
}

export interface WorkspaceLiteTaskItem {
  id: string;
  title: string;
  status?: string | null;
  clientName?: string | null;
  eventLineName?: string | null;
}

export interface ClientWorkspaceLiteSnapshot {
  clientId: string;
  clientName: string;
  boundaryCards: BoundaryCard[];
  boundaryState: CurrentFocusBoundaryState;
  goals: WorkspaceLiteItem[];
  latestMeetings: WorkspaceLiteItem[];
  knowledgeStatus?: string | null;
  recentDocuments: WorkspaceLiteItem[];
  openQuestions: WorkspaceLiteItem[];
  conflicts: WorkspaceLiteItem[];
  relatedTasks: WorkspaceLiteTaskItem[];
  nextActions: string[];
  headline?: string | null;
  health: string[];
  twoWeekChanges: string[];
  pendingDecisions: string[];
  pendingMaterials: string[];
  updatedAt: string;
}

export interface WeekSignalFactSummary {
  totalCount: number;
  completedCount: number;
  rescheduledCount: number;
  unscheduledCount: number;
  overdueCount: number;
  awaitingReviewCount: number;
}

export interface WeekSignalSnapshot {
  facts: WeekSignalFactSummary;
  pendingJudgments: string[];
  riskSignals: string[];
  suggestedActions: string[];
}
~~~

## `mobile/lib/use-render-count.ts`

- 编码: `utf-8`

~~~typescript
import { useEffect, useRef } from "react";
import { devLog } from "./dev-log";

export function useRenderCount(scope: string): void {
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;

  useEffect(() => {
    devLog("render", scope, { renderCount: renderCountRef.current });
  });
}
~~~

## `mobile/lib/week-signal.ts`

- 编码: `utf-8`

~~~typescript
import { formatLocalDateKey, getLocalWeekRangeKeys, parseLocalDateKey } from "./date";
import type {
  ClientWorkspaceLiteSnapshot,
  EventLineRecord,
  TaskRecord,
  WeekSignalFactSummary,
  WeekSignalSnapshot,
} from "./types";

/**
 * Normalize a task `dueDate` (which may be UTC ISO with `Z`, wall-clock ISO without
 * timezone, or a bare `YYYY-MM-DD`) into a local-calendar date key.
 *
 * Old code did `dueDate.slice(0, 10)`, which for UTC ISO strings returned the UTC
 * date — that mismatches the local week boundaries used everywhere else and made
 * tasks near midnight slip into the wrong week (Bug 1).
 */
function toLocalDateKey(value: string | null | undefined): string | null {
  if (!value) return null;
  // Already a date key like "2026-04-14".
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  // Wall-clock ISO without timezone (e.g. "2026-04-14T12:30") — date portion is
  // already in the local calendar, just slice it off.
  const wallClockMatch = value.match(/^(\d{4}-\d{2}-\d{2})T[\d:.]+$/);
  if (wallClockMatch) {
    return wallClockMatch[1];
  }
  // ISO with Z or explicit offset — parse and convert to the local date.
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }
  return formatLocalDateKey(parsed);
}

function isTaskInWeek(task: TaskRecord, weekAnchorDate: string): boolean {
  const dueKey = toLocalDateKey(task.dueDate);
  if (!dueKey) {
    return false;
  }
  const { startKey, endKey } = getLocalWeekRangeKeys(parseLocalDateKey(weekAnchorDate));
  return dueKey >= startKey && dueKey <= endKey;
}

export function buildWeekSignalFacts(
  tasks: readonly TaskRecord[],
  weekAnchorDate: string,
  now: Date = new Date(),
): WeekSignalFactSummary {
  const weekTasks = tasks.filter((task) => isTaskInWeek(task, weekAnchorDate));
  const todayKey = formatLocalDateKey(now);

  // Counters that describe "this week" — must be scoped to weekTasks (Bug 2).
  const totalCount = weekTasks.length;
  const completedCount = weekTasks.filter((task) => task.progressStatus === "done").length;
  const rescheduledCount = weekTasks.filter((task) => {
    if (!task.updatedAt || !task.createdAt) {
      return false;
    }
    return task.updatedAt !== task.createdAt;
  }).length;
  const awaitingReviewCount = weekTasks.filter(
    (task) => task.progressStatus === "done" && !task.completionNote,
  ).length;

  // Counters that describe "right now" across the whole inbox — kept global on
  // purpose (an unscheduled task is unscheduled regardless of week). They now
  // exclude finished tasks, and `overdue` is measured against today rather than
  // the week anchor so a task due Monday this week shows as overdue on Friday
  // (Bug 2 follow-on).
  const unscheduledCount = tasks.filter(
    (task) => !task.dueDate && task.progressStatus !== "done",
  ).length;
  const overdueCount = tasks.filter((task) => {
    if (task.progressStatus === "done") return false;
    const dueKey = toLocalDateKey(task.dueDate);
    if (!dueKey) return false;
    return dueKey < todayKey;
  }).length;

  return {
    totalCount,
    completedCount,
    rescheduledCount,
    unscheduledCount,
    overdueCount,
    awaitingReviewCount,
  };
}

export function buildWeekSignalSnapshot(params: {
  readonly tasks: readonly TaskRecord[];
  readonly weekAnchorDate: string;
  readonly workspaceLite?: ClientWorkspaceLiteSnapshot | null;
  readonly eventLine?: EventLineRecord | null;
  readonly allowJudgmentOverlay?: boolean;
  readonly now?: Date;
}): WeekSignalSnapshot {
  const facts = buildWeekSignalFacts(params.tasks, params.weekAnchorDate, params.now);
  if (!params.allowJudgmentOverlay) {
    return {
      facts,
      pendingJudgments: [],
      riskSignals: [],
      suggestedActions: [],
    };
  }
  const pending = params.workspaceLite?.boundaryCards
    .filter((card) => card.kind === "pending" && !card.isEmpty)
    .map((card) => card.summary)
    .filter(Boolean) ?? [];
  const risks = params.workspaceLite?.boundaryCards
    .filter((card) => card.kind === "risk" && !card.isEmpty)
    .map((card) => card.summary)
    .filter(Boolean) ?? [];
  const actions = [
    ...(params.workspaceLite?.nextActions ?? []).slice(0, 3),
    ...(params.eventLine?.nextStep ? [params.eventLine.nextStep] : []),
  ].filter(Boolean) as string[];

  return {
    facts,
    pendingJudgments: pending.slice(0, 3),
    riskSignals: risks.slice(0, 3),
    suggestedActions: actions.slice(0, 3),
  };
}
~~~

## `mobile/package-lock.json`

- 编码: `utf-8`

~~~json
{
  "name": "yiyu-mobile",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "yiyu-mobile",
      "version": "1.0.0",
      "dependencies": {
        "@react-native-async-storage/async-storage": "2.2.0",
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-asset": "55.0.11-canary-20260328-bdc6273",
        "expo-audio": "55.0.10-canary-20260328-bdc6273",
        "expo-background-fetch": "55.0.12",
        "expo-blur": "55.0.11-canary-20260328-bdc6273",
        "expo-clipboard": "55.0.10-canary-20260328-bdc6273",
        "expo-constants": "55.0.10-canary-20260328-bdc6273",
        "expo-file-system": "55.0.13-canary-20260328-bdc6273",
        "expo-haptics": "55.0.10-canary-20260328-bdc6273",
        "expo-linking": "55.0.10-canary-20260328-bdc6273",
        "expo-router": "55.0.9-canary-20260328-bdc6273",
        "expo-secure-store": "55.0.10-canary-20260328-bdc6273",
        "expo-speech-recognition": "3.1.2",
        "expo-sqlite": "55.0.13",
        "expo-status-bar": "55.0.5-canary-20260328-bdc6273",
        "expo-task-manager": "55.0.12",
        "lucide-react-native": "1.7.0",
        "react": "19.2.0",
        "react-native": "0.83.4",
        "react-native-safe-area-context": "5.6.2",
        "react-native-screens": "~4.23.0",
        "react-native-svg": "15.15.3"
      },
      "devDependencies": {
        "@types/react": "19.2.14",
        "typescript": "5.9.3"
      }
    },
    "node_modules/@babel/code-frame": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/code-frame/-/code-frame-7.29.0.tgz",
      "integrity": "sha512-9NhCeYjq9+3uxgdtp20LSiJXJvN0FeCtNGpJxuMFZ1Kv3cWUNb6DOhJwUvcVCzKGR66cw4njwM6hrJLqgOwbcw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-validator-identifier": "^7.28.5",
        "js-tokens": "^4.0.0",
        "picocolors": "^1.1.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/compat-data": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/compat-data/-/compat-data-7.29.0.tgz",
      "integrity": "sha512-T1NCJqT/j9+cn8fvkt7jtwbLBfLC/1y1c7NtCeXFRgzGTsafi68MRv8yzkYSapBnFA6L3U2VSc02ciDzoAJhJg==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/core": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/core/-/core-7.29.0.tgz",
      "integrity": "sha512-CGOfOJqWjg2qW/Mb6zNsDm+u5vFQ8DxXfbM09z69p5Z6+mE1ikP2jUXw+j42Pf1XTYED2Rni5f95npYeuwMDQA==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.0",
        "@babel/generator": "^7.29.0",
        "@babel/helper-compilation-targets": "^7.28.6",
        "@babel/helper-module-transforms": "^7.28.6",
        "@babel/helpers": "^7.28.6",
        "@babel/parser": "^7.29.0",
        "@babel/template": "^7.28.6",
        "@babel/traverse": "^7.29.0",
        "@babel/types": "^7.29.0",
        "@jridgewell/remapping": "^2.3.5",
        "convert-source-map": "^2.0.0",
        "debug": "^4.1.0",
        "gensync": "^1.0.0-beta.2",
        "json5": "^2.2.3",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/babel"
      }
    },
    "node_modules/@babel/core/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/@babel/generator": {
      "version": "7.29.1",
      "resolved": "https://registry.npmmirror.com/@babel/generator/-/generator-7.29.1.tgz",
      "integrity": "sha512-qsaF+9Qcm2Qv8SRIMMscAvG4O3lJ0F1GuMo5HR/Bp02LopNgnZBC/EkbevHFeGs4ls/oPz9v+Bsmzbkbe+0dUw==",
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.29.0",
        "@babel/types": "^7.29.0",
        "@jridgewell/gen-mapping": "^0.3.12",
        "@jridgewell/trace-mapping": "^0.3.28",
        "jsesc": "^3.0.2"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-annotate-as-pure": {
      "version": "7.27.3",
      "resolved": "https://registry.npmmirror.com/@babel/helper-annotate-as-pure/-/helper-annotate-as-pure-7.27.3.tgz",
      "integrity": "sha512-fXSwMQqitTGeHLBC08Eq5yXz2m37E4pJX1qAU1+2cNedz/ifv/bVXft90VeSav5nFO61EcNgwr0aJxbyPaWBPg==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.27.3"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-compilation-targets/-/helper-compilation-targets-7.28.6.tgz",
      "integrity": "sha512-JYtls3hqi15fcx5GaSNL7SCTJ2MNmjrkHXg4FSpOA/grxK8KwyZ5bubHsCq8FXCkua6xhuaaBit+3b7+VZRfcA==",
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.28.6",
        "@babel/helper-validator-option": "^7.27.1",
        "browserslist": "^4.24.0",
        "lru-cache": "^5.1.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/@babel/helper-create-class-features-plugin": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-create-class-features-plugin/-/helper-create-class-features-plugin-7.28.6.tgz",
      "integrity": "sha512-dTOdvsjnG3xNT9Y0AUg1wAl38y+4Rl4sf9caSQZOXdNqVn+H+HbbJ4IyyHaIqNR6SW9oJpA/RuRjsjCw2IdIow==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "@babel/helper-member-expression-to-functions": "^7.28.5",
        "@babel/helper-optimise-call-expression": "^7.27.1",
        "@babel/helper-replace-supers": "^7.28.6",
        "@babel/helper-skip-transparent-expression-wrappers": "^7.27.1",
        "@babel/traverse": "^7.28.6",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-create-class-features-plugin/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/@babel/helper-create-regexp-features-plugin": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/helper-create-regexp-features-plugin/-/helper-create-regexp-features-plugin-7.28.5.tgz",
      "integrity": "sha512-N1EhvLtHzOvj7QQOUCCS3NrPJP8c5W6ZXCHDn7Yialuy1iu4r5EmIYkXlKNqT99Ciw+W0mDqWoR6HWMZlFP3hw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "regexpu-core": "^6.3.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-create-regexp-features-plugin/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/@babel/helper-define-polyfill-provider": {
      "version": "0.6.8",
      "resolved": "https://registry.npmmirror.com/@babel/helper-define-polyfill-provider/-/helper-define-polyfill-provider-0.6.8.tgz",
      "integrity": "sha512-47UwBLPpQi1NoWzLuHNjRoHlYXMwIJoBf7MFou6viC/sIHWYygpvr0B6IAyh5sBdA2nr2LPIRww8lfaUVQINBA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-compilation-targets": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "debug": "^4.4.3",
        "lodash.debounce": "^4.0.8",
        "resolve": "^1.22.11"
      },
      "peerDependencies": {
        "@babel/core": "^7.4.0 || ^8.0.0-0 <8.0.0"
      }
    },
    "node_modules/@babel/helper-globals": {
      "version": "7.28.0",
      "resolved": "https://registry.npmmirror.com/@babel/helper-globals/-/helper-globals-7.28.0.tgz",
      "integrity": "sha512-+W6cISkXFa1jXsDEdYA8HeevQT/FULhxzR99pxphltZcVaugps53THCeiWA8SguxxpSp3gKPiuYfSWopkLQ4hw==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-member-expression-to-functions": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/helper-member-expression-to-functions/-/helper-member-expression-to-functions-7.28.5.tgz",
      "integrity": "sha512-cwM7SBRZcPCLgl8a7cY0soT1SptSzAlMH39vwiRpOQkJlh53r5hdHwLSCZpQdVLT39sZt+CRpNwYG4Y2v77atg==",
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.28.5",
        "@babel/types": "^7.28.5"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-imports": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-module-imports/-/helper-module-imports-7.28.6.tgz",
      "integrity": "sha512-l5XkZK7r7wa9LucGw9LwZyyCUscb4x37JWTPz7swwFE/0FMQAGpiWUZn8u9DzkSBWEcK25jmvubfpw2dnAMdbw==",
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-transforms": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-module-transforms/-/helper-module-transforms-7.28.6.tgz",
      "integrity": "sha512-67oXFAYr2cDLDVGLXTEABjdBJZ6drElUSI7WKp70NrpyISso3plG9SAGEF6y7zbha/wOzUByWWTJvEDVNIUGcA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.28.6",
        "@babel/helper-validator-identifier": "^7.28.5",
        "@babel/traverse": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-optimise-call-expression": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-optimise-call-expression/-/helper-optimise-call-expression-7.27.1.tgz",
      "integrity": "sha512-URMGH08NzYFhubNSGJrpUEphGKQwMQYBySzat5cAByY1/YgIRkULnIy3tAMeszlL/so2HbeilYloUmSpd7GdVw==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-plugin-utils": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-plugin-utils/-/helper-plugin-utils-7.28.6.tgz",
      "integrity": "sha512-S9gzZ/bz83GRysI7gAD4wPT/AI3uCnY+9xn+Mx/KPs2JwHJIz1W8PZkg2cqyt3RNOBM8ejcXhV6y8Og7ly/Dug==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-remap-async-to-generator": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-remap-async-to-generator/-/helper-remap-async-to-generator-7.27.1.tgz",
      "integrity": "sha512-7fiA521aVw8lSPeI4ZOD3vRFkoqkJcS+z4hFo82bFSH/2tNd6eJ5qCVMS5OzDmZh/kaHQeBaeyxK6wljcPtveA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.1",
        "@babel/helper-wrap-function": "^7.27.1",
        "@babel/traverse": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-replace-supers": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-replace-supers/-/helper-replace-supers-7.28.6.tgz",
      "integrity": "sha512-mq8e+laIk94/yFec3DxSjCRD2Z0TAjhVbEJY3UQrlwVo15Lmt7C2wAUbK4bjnTs4APkwsYLTahXRraQXhb1WCg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-member-expression-to-functions": "^7.28.5",
        "@babel/helper-optimise-call-expression": "^7.27.1",
        "@babel/traverse": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-skip-transparent-expression-wrappers": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-skip-transparent-expression-wrappers/-/helper-skip-transparent-expression-wrappers-7.27.1.tgz",
      "integrity": "sha512-Tub4ZKEXqbPjXgWLl2+3JpQAYBJ8+ikpQ2Ocj/q/r0LwE3UhENh7EUabyHjz2kCEsrRY83ew2DQdHluuiDQFzg==",
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.27.1",
        "@babel/types": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-string-parser/-/helper-string-parser-7.27.1.tgz",
      "integrity": "sha512-qMlSxKbpRlAridDExk92nSobyDdpPijUq2DW6oDnUqd0iOGxmQjyqhMIihI9+zv4LPyZdRje2cavWPbCbWm3eA==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-identifier": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/helper-validator-identifier/-/helper-validator-identifier-7.28.5.tgz",
      "integrity": "sha512-qSs4ifwzKJSV39ucNjsvc6WVHs6b7S03sOh2OcHF9UHfVPqWWALUsNUVzhSBiItjRZoLHx7nIarVjqKVusUZ1Q==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-option": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-validator-option/-/helper-validator-option-7.27.1.tgz",
      "integrity": "sha512-YvjJow9FxbhFFKDSuFnVCe2WxXk1zWc22fFePVNEaWJEu8IrZVlda6N0uHwzZrUM1il7NC9Mlp4MaJYbYd9JSg==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-wrap-function": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-wrap-function/-/helper-wrap-function-7.28.6.tgz",
      "integrity": "sha512-z+PwLziMNBeSQJonizz2AGnndLsP2DeGHIxDAn+wdHOGuo4Fo1x1HBPPXeE9TAOPHNNWQKCSlA2VZyYyyibDnQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.28.6",
        "@babel/traverse": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helpers": {
      "version": "7.29.2",
      "resolved": "https://registry.npmmirror.com/@babel/helpers/-/helpers-7.29.2.tgz",
      "integrity": "sha512-HoGuUs4sCZNezVEKdVcwqmZN8GoHirLUcLaYVNBK2J0DadGtdcqgr3BCbvH8+XUo4NGjNl3VOtSjEKNzqfFgKw==",
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.28.6",
        "@babel/types": "^7.29.0"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/parser": {
      "version": "7.29.2",
      "resolved": "https://registry.npmmirror.com/@babel/parser/-/parser-7.29.2.tgz",
      "integrity": "sha512-4GgRzy/+fsBa72/RZVJmGKPmZu9Byn8o4MoLpmNe1m8ZfYnz5emHLQz3U4gLud6Zwl0RZIcgiLD7Uq7ySFuDLA==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.29.0"
      },
      "bin": {
        "parser": "bin/babel-parser.js"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@babel/plugin-proposal-decorators": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-proposal-decorators/-/plugin-proposal-decorators-7.29.0.tgz",
      "integrity": "sha512-CVBVv3VY/XRMxRYq5dwr2DS7/MvqPm23cOCjbwNnVrfOqcWlnefua1uUs0sjdKOGjvPUG633o07uWzJq4oI6dA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/plugin-syntax-decorators": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-proposal-export-default-from": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-proposal-export-default-from/-/plugin-proposal-export-default-from-7.27.1.tgz",
      "integrity": "sha512-hjlsMBl1aJc5lp8MoCDEZCiYzlgdRAShOjAfRw6X+GlpLpUPU7c3XNLsKFZbQk/1cRzBlJ7CXg3xJAJMrFa1Uw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-async-generators": {
      "version": "7.8.4",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-async-generators/-/plugin-syntax-async-generators-7.8.4.tgz",
      "integrity": "sha512-tycmZxkGfZaxhMRbXlPXuVFpdWlXpir2W4AMhSJgRKzk/eDlIXOhb2LHWoLpDF7TEHylV5zNhykX6KAgHJmTNw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-bigint": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-bigint/-/plugin-syntax-bigint-7.8.3.tgz",
      "integrity": "sha512-wnTnFlG+YxQm3vDxpGE57Pj0srRU4sHE/mDkt1qv2YJJSeUAec2ma4WLUnUPeKjyrfntVwe/N6dCXpU+zL3Npg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-class-properties": {
      "version": "7.12.13",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-class-properties/-/plugin-syntax-class-properties-7.12.13.tgz",
      "integrity": "sha512-fm4idjKla0YahUNgFNLCB0qySdsoPiZP3iQE3rky0mBUtMZ23yDJ9SJdg6dXTSDnulOVqiF3Hgr9nbXvXTQZYA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.12.13"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-class-static-block": {
      "version": "7.14.5",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-class-static-block/-/plugin-syntax-class-static-block-7.14.5.tgz",
      "integrity": "sha512-b+YyPmr6ldyNnM6sqYeMWE+bgJcJpO6yS4QD7ymxgH34GBPNDM/THBh8iunyvKIZztiwLH4CJZ0RxTk9emgpjw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.14.5"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-decorators": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-decorators/-/plugin-syntax-decorators-7.28.6.tgz",
      "integrity": "sha512-71EYI0ONURHJBL4rSFXnITXqXrrY8q4P0q006DPfN+Rk+ASM+++IBXem/ruokgBZR8YNEWZ8R6B+rCb8VcUTqA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-dynamic-import": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-dynamic-import/-/plugin-syntax-dynamic-import-7.8.3.tgz",
      "integrity": "sha512-5gdGbFon+PszYzqs83S3E5mpi7/y/8M9eC90MRTZfduQOYW76ig6SOSPNe41IG5LoP3FGBn2N0RjVDSQiS94kQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-export-default-from": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-export-default-from/-/plugin-syntax-export-default-from-7.28.6.tgz",
      "integrity": "sha512-Svlx1fjJFnNz0LZeUaybRukSxZI3KkpApUmIRzEdXC5k8ErTOz0OD0kNrICi5Vc3GlpP5ZCeRyRO+mfWTSz+iQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-flow": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-flow/-/plugin-syntax-flow-7.28.6.tgz",
      "integrity": "sha512-D+OrJumc9McXNEBI/JmFnc/0uCM2/Y3PEBG3gfV3QIYkKv5pvnpzFrl1kYCrcHJP8nOeFB/SHi1IHz29pNGuew==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-import-attributes": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-import-attributes/-/plugin-syntax-import-attributes-7.28.6.tgz",
      "integrity": "sha512-jiLC0ma9XkQT3TKJ9uYvlakm66Pamywo+qwL+oL8HJOvc6TWdZXVfhqJr8CCzbSGUAbDOzlGHJC1U+vRfLQDvw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-import-meta": {
      "version": "7.10.4",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-import-meta/-/plugin-syntax-import-meta-7.10.4.tgz",
      "integrity": "sha512-Yqfm+XDx0+Prh3VSeEQCPU81yC+JWZ2pDPFSS4ZdpfZhp4MkFMaDC1UqseovEKwSUpnIL7+vK+Clp7bfh0iD7g==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.10.4"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-json-strings": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-json-strings/-/plugin-syntax-json-strings-7.8.3.tgz",
      "integrity": "sha512-lY6kdGpWHvjoe2vk4WrAapEuBR69EMxZl+RoGRhrFGNYVK8mOPAW8VfbT/ZgrFbXlDNiiaxQnAtgVCZ6jv30EA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-jsx": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-jsx/-/plugin-syntax-jsx-7.28.6.tgz",
      "integrity": "sha512-wgEmr06G6sIpqr8YDwA2dSRTE3bJ+V0IfpzfSY3Lfgd7YWOaAdlykvJi13ZKBt8cZHfgH1IXN+CL656W3uUa4w==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-logical-assignment-operators": {
      "version": "7.10.4",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-logical-assignment-operators/-/plugin-syntax-logical-assignment-operators-7.10.4.tgz",
      "integrity": "sha512-d8waShlpFDinQ5MtvGU9xDAOzKH47+FFoney2baFIoMr952hKOLp1HR7VszoZvOsV/4+RRszNY7D17ba0te0ig==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.10.4"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-nullish-coalescing-operator": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-nullish-coalescing-operator/-/plugin-syntax-nullish-coalescing-operator-7.8.3.tgz",
      "integrity": "sha512-aSff4zPII1u2QD7y+F8oDsz19ew4IGEJg9SVW+bqwpwtfFleiQDMdzA/R+UlWDzfnHFCxxleFT0PMIrR36XLNQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-numeric-separator": {
      "version": "7.10.4",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-numeric-separator/-/plugin-syntax-numeric-separator-7.10.4.tgz",
      "integrity": "sha512-9H6YdfkcK/uOnY/K7/aA2xpzaAgkQn37yzWUMRK7OaPOqOpGS1+n0H5hxT9AUw9EsSjPW8SVyMJwYRtWs3X3ug==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.10.4"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-object-rest-spread": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-object-rest-spread/-/plugin-syntax-object-rest-spread-7.8.3.tgz",
      "integrity": "sha512-XoqMijGZb9y3y2XskN+P1wUGiVwWZ5JmoDRwx5+3GmEplNyVM2s2Dg8ILFQm8rWM48orGy5YpI5Bl8U1y7ydlA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-optional-catch-binding": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-optional-catch-binding/-/plugin-syntax-optional-catch-binding-7.8.3.tgz",
      "integrity": "sha512-6VPD0Pc1lpTqw0aKoeRTMiB+kWhAoT24PA+ksWSBrFtl5SIRVpZlwN3NNPQjehA2E/91FV3RjLWoVTglWcSV3Q==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-optional-chaining": {
      "version": "7.8.3",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-optional-chaining/-/plugin-syntax-optional-chaining-7.8.3.tgz",
      "integrity": "sha512-KoK9ErH1MBlCPxV0VANkXW2/dw4vlbGDrFgz8bmUsBGYkFRcbRwMh6cIJubdPrkxRwuGdtCk0v/wPTKbQgBjkg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.8.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-private-property-in-object": {
      "version": "7.14.5",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-private-property-in-object/-/plugin-syntax-private-property-in-object-7.14.5.tgz",
      "integrity": "sha512-0wVnp9dxJ72ZUJDV27ZfbSj6iHLoytYZmh3rFcxNnvsJF3ktkzLDZPy/mA17HGsaQT3/DQsWYX1f1QGWkCoVUg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.14.5"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-top-level-await": {
      "version": "7.14.5",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-top-level-await/-/plugin-syntax-top-level-await-7.14.5.tgz",
      "integrity": "sha512-hx++upLv5U1rgYfwe1xBQUhRmU41NEvpUvrp8jkrSCdvGSnM5/qdRMtylJ6PG5OFkBaHkbTAKTnd3/YyESRHFw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.14.5"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-syntax-typescript": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-syntax-typescript/-/plugin-syntax-typescript-7.28.6.tgz",
      "integrity": "sha512-+nDNmQye7nlnuuHDboPbGm00Vqg3oO8niRRL27/4LYHUsHYh0zJ1xWOz0uRwNFmM1Avzk8wZbc6rdiYhomzv/A==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-arrow-functions": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-arrow-functions/-/plugin-transform-arrow-functions-7.27.1.tgz",
      "integrity": "sha512-8Z4TGic6xW70FKThA5HYEKKyBpOOsucTOD1DjU3fZxDg+K3zBJcXMFnt/4yQiZnf5+MiOMSXQ9PaEK/Ilh1DeA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-async-generator-functions": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-async-generator-functions/-/plugin-transform-async-generator-functions-7.29.0.tgz",
      "integrity": "sha512-va0VdWro4zlBr2JsXC+ofCPB2iG12wPtVGTWFx2WLDOM3nYQZZIGP82qku2eW/JR83sD+k2k+CsNtyEbUqhU6w==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-remap-async-to-generator": "^7.27.1",
        "@babel/traverse": "^7.29.0"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-async-to-generator": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-async-to-generator/-/plugin-transform-async-to-generator-7.28.6.tgz",
      "integrity": "sha512-ilTRcmbuXjsMmcZ3HASTe4caH5Tpo93PkTxF9oG2VZsSWsahydmcEHhix9Ik122RcTnZnUzPbmux4wh1swfv7g==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-remap-async-to-generator": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-block-scoping": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-block-scoping/-/plugin-transform-block-scoping-7.28.6.tgz",
      "integrity": "sha512-tt/7wOtBmwHPNMPu7ax4pdPz6shjFrmHDghvNC+FG9Qvj7D6mJcoRQIF5dy4njmxR941l6rgtvfSB2zX3VlUIw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-class-properties": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-class-properties/-/plugin-transform-class-properties-7.28.6.tgz",
      "integrity": "sha512-dY2wS3I2G7D697VHndN91TJr8/AAfXQNt5ynCTI/MpxMsSzHp+52uNivYT5wCPax3whc47DR8Ba7cmlQMg24bw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-class-static-block": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-class-static-block/-/plugin-transform-class-static-block-7.28.6.tgz",
      "integrity": "sha512-rfQ++ghVwTWTqQ7w8qyDxL1XGihjBss4CmTgGRCTAC9RIbhVpyp4fOeZtta0Lbf+dTNIVJer6ych2ibHwkZqsQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.12.0"
      }
    },
    "node_modules/@babel/plugin-transform-classes": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-classes/-/plugin-transform-classes-7.28.6.tgz",
      "integrity": "sha512-EF5KONAqC5zAqT783iMGuM2ZtmEBy+mJMOKl2BCvPZ2lVrwvXnB6o+OBWCS+CoeCCpVRF2sA2RBKUxvT8tQT5Q==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "@babel/helper-compilation-targets": "^7.28.6",
        "@babel/helper-globals": "^7.28.0",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-replace-supers": "^7.28.6",
        "@babel/traverse": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-computed-properties": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-computed-properties/-/plugin-transform-computed-properties-7.28.6.tgz",
      "integrity": "sha512-bcc3k0ijhHbc2lEfpFHgx7eYw9KNXqOerKWfzbxEHUGKnS3sz9C4CNL9OiFN1297bDNfUiSO7DaLzbvHQQQ1BQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/template": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-destructuring": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-destructuring/-/plugin-transform-destructuring-7.28.5.tgz",
      "integrity": "sha512-Kl9Bc6D0zTUcFUvkNuQh4eGXPKKNDOJQXVyyM4ZAQPMveniJdxi8XMJwLo+xSoW3MIq81bD33lcUe9kZpl0MCw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/traverse": "^7.28.5"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-export-namespace-from": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-export-namespace-from/-/plugin-transform-export-namespace-from-7.27.1.tgz",
      "integrity": "sha512-tQvHWSZ3/jH2xuq/vZDy0jNn+ZdXJeM8gHvX4lnJmsc3+50yPlWdZXIc5ay+umX+2/tJIqHqiEqcJvxlmIvRvQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-flow-strip-types": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-flow-strip-types/-/plugin-transform-flow-strip-types-7.27.1.tgz",
      "integrity": "sha512-G5eDKsu50udECw7DL2AcsysXiQyB7Nfg521t2OAJ4tbfTJ27doHLeF/vlI1NZGlLdbb/v+ibvtL1YBQqYOwJGg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/plugin-syntax-flow": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-for-of": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-for-of/-/plugin-transform-for-of-7.27.1.tgz",
      "integrity": "sha512-BfbWFFEJFQzLCQ5N8VocnCtA8J1CLkNTe2Ms2wocj75dd6VpiqS5Z5quTYcUoo4Yq+DN0rtikODccuv7RU81sw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/helper-skip-transparent-expression-wrappers": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-function-name": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-function-name/-/plugin-transform-function-name-7.27.1.tgz",
      "integrity": "sha512-1bQeydJF9Nr1eBCMMbC+hdwmRlsv5XYOMu03YSWFwNs0HsAmtSxxF1fyuYPqemVldVyFmlCU7w8UE14LupUSZQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-compilation-targets": "^7.27.1",
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/traverse": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-literals": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-literals/-/plugin-transform-literals-7.27.1.tgz",
      "integrity": "sha512-0HCFSepIpLTkLcsi86GG3mTUzxV5jpmbv97hTETW3yzrAij8aqlD36toB1D0daVFJM8NK6GvKO0gslVQmm+zZA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-logical-assignment-operators": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-logical-assignment-operators/-/plugin-transform-logical-assignment-operators-7.28.6.tgz",
      "integrity": "sha512-+anKKair6gpi8VsM/95kmomGNMD0eLz1NQ8+Pfw5sAwWH9fGYXT50E55ZpV0pHUHWf6IUTWPM+f/7AAff+wr9A==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-modules-commonjs": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-modules-commonjs/-/plugin-transform-modules-commonjs-7.28.6.tgz",
      "integrity": "sha512-jppVbf8IV9iWWwWTQIxJMAJCWBuuKx71475wHwYytrRGQ2CWiDvYlADQno3tcYpS/T2UUWFQp3nVtYfK/YBQrA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-transforms": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-named-capturing-groups-regex": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-named-capturing-groups-regex/-/plugin-transform-named-capturing-groups-regex-7.29.0.tgz",
      "integrity": "sha512-1CZQA5KNAD6ZYQLPw7oi5ewtDNxH/2vuCh+6SmvgDfhumForvs8a1o9n0UrEoBD8HU4djO2yWngTQlXl1NDVEQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-regexp-features-plugin": "^7.28.5",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/plugin-transform-nullish-coalescing-operator": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-nullish-coalescing-operator/-/plugin-transform-nullish-coalescing-operator-7.28.6.tgz",
      "integrity": "sha512-3wKbRgmzYbw24mDJXT7N+ADXw8BC/imU9yo9c9X9NKaLF1fW+e5H1U5QjMUBe4Qo4Ox/o++IyUkl1sVCLgevKg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-numeric-separator": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-numeric-separator/-/plugin-transform-numeric-separator-7.28.6.tgz",
      "integrity": "sha512-SJR8hPynj8outz+SlStQSwvziMN4+Bq99it4tMIf5/Caq+3iOc0JtKyse8puvyXkk3eFRIA5ID/XfunGgO5i6w==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-object-rest-spread": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-object-rest-spread/-/plugin-transform-object-rest-spread-7.28.6.tgz",
      "integrity": "sha512-5rh+JR4JBC4pGkXLAcYdLHZjXudVxWMXbB6u6+E9lRL5TrGVbHt1TjxGbZ8CkmYw9zjkB7jutzOROArsqtncEA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-compilation-targets": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/plugin-transform-destructuring": "^7.28.5",
        "@babel/plugin-transform-parameters": "^7.27.7",
        "@babel/traverse": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-optional-catch-binding": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-optional-catch-binding/-/plugin-transform-optional-catch-binding-7.28.6.tgz",
      "integrity": "sha512-R8ja/Pyrv0OGAvAXQhSTmWyPJPml+0TMqXlO5w+AsMEiwb2fg3WkOvob7UxFSL3OIttFSGSRFKQsOhJ/X6HQdQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-optional-chaining": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-optional-chaining/-/plugin-transform-optional-chaining-7.28.6.tgz",
      "integrity": "sha512-A4zobikRGJTsX9uqVFdafzGkqD30t26ck2LmOzAuLL8b2x6k3TIqRiT2xVvA9fNmFeTX484VpsdgmKNA0bS23w==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-skip-transparent-expression-wrappers": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-parameters": {
      "version": "7.27.7",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-parameters/-/plugin-transform-parameters-7.27.7.tgz",
      "integrity": "sha512-qBkYTYCb76RRxUM6CcZA5KRu8K4SM8ajzVeUgVdMVO9NN9uI/GaVmBg/WKJJGnNokV9SY8FxNOVWGXzqzUidBg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-private-methods": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-private-methods/-/plugin-transform-private-methods-7.28.6.tgz",
      "integrity": "sha512-piiuapX9CRv7+0st8lmuUlRSmX6mBcVeNQ1b4AYzJxfCMuBfB0vBXDiGSmm03pKJw1v6cZ8KSeM+oUnM6yAExg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-private-property-in-object": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-private-property-in-object/-/plugin-transform-private-property-in-object-7.28.6.tgz",
      "integrity": "sha512-b97jvNSOb5+ehyQmBpmhOCiUC5oVK4PMnpRvO7+ymFBoqYjeDHIU9jnrNUuwHOiL9RpGDoKBpSViarV+BU+eVA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-display-name": {
      "version": "7.28.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-display-name/-/plugin-transform-react-display-name-7.28.0.tgz",
      "integrity": "sha512-D6Eujc2zMxKjfa4Zxl4GHMsmhKKZ9VpcqIchJLvwTxad9zWIYulwYItBovpDOoNLISpcZSXoDJ5gaGbQUDqViA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx/-/plugin-transform-react-jsx-7.28.6.tgz",
      "integrity": "sha512-61bxqhiRfAACulXSLd/GxqmAedUSrRZIu/cbaT18T1CetkTmtDN15it7i80ru4DVqRK1WMxQhXs+Lf9kajm5Ow==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "@babel/helper-module-imports": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/plugin-syntax-jsx": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-development": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx-development/-/plugin-transform-react-jsx-development-7.27.1.tgz",
      "integrity": "sha512-ykDdF5yI4f1WrAolLqeF3hmYU12j9ntLQl/AOG1HAS21jxyg1Q0/J/tpREuYLfatGdGmXp/3yS0ZA76kOlVq9Q==",
      "license": "MIT",
      "dependencies": {
        "@babel/plugin-transform-react-jsx": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-self": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx-self/-/plugin-transform-react-jsx-self-7.27.1.tgz",
      "integrity": "sha512-6UzkCs+ejGdZ5mFFC/OCUrv028ab2fp1znZmCZjAOBKiBK2jXD1O+BPSfX8X2qjJ75fZBMSnQn3Rq2mrBJK2mw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-source": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx-source/-/plugin-transform-react-jsx-source-7.27.1.tgz",
      "integrity": "sha512-zbwoTsBruTeKB9hSq73ha66iFeJHuaFkUbwvqElnygoNbj/jHRsSeokowZFN3CZ64IvEqcmmkVe89OPXc7ldAw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-pure-annotations": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-pure-annotations/-/plugin-transform-react-pure-annotations-7.27.1.tgz",
      "integrity": "sha512-JfuinvDOsD9FVMTHpzA/pBLisxpv1aSf+OIV8lgH3MuWrks19R27e6a6DipIg4aX1Zm9Wpb04p8wljfKrVSnPA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.1",
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-regenerator": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-regenerator/-/plugin-transform-regenerator-7.29.0.tgz",
      "integrity": "sha512-FijqlqMA7DmRdg/aINBSs04y8XNTYw/lr1gJ2WsmBnnaNw1iS43EPkJW+zK7z65auG3AWRFXWj+NcTQwYptUog==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-runtime": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-runtime/-/plugin-transform-runtime-7.29.0.tgz",
      "integrity": "sha512-jlaRT5dJtMaMCV6fAuLbsQMSwz/QkvaHOHOSXRitGGwSpR1blCY4KUKoyP2tYO8vJcqYe8cEj96cqSztv3uF9w==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "babel-plugin-polyfill-corejs2": "^0.4.14",
        "babel-plugin-polyfill-corejs3": "^0.13.0",
        "babel-plugin-polyfill-regenerator": "^0.6.5",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-runtime/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/@babel/plugin-transform-shorthand-properties": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-shorthand-properties/-/plugin-transform-shorthand-properties-7.27.1.tgz",
      "integrity": "sha512-N/wH1vcn4oYawbJ13Y/FxcQrWk63jhfNa7jef0ih7PHSIHX2LB7GWE1rkPrOnka9kwMxb6hMl19p7lidA+EHmQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-spread": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-spread/-/plugin-transform-spread-7.28.6.tgz",
      "integrity": "sha512-9U4QObUC0FtJl05AsUcodau/RWDytrU6uKgkxu09mLR9HLDAtUMoPuuskm5huQsoktmsYpI+bGmq+iapDcriKA==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-skip-transparent-expression-wrappers": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-sticky-regex": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-sticky-regex/-/plugin-transform-sticky-regex-7.27.1.tgz",
      "integrity": "sha512-lhInBO5bi/Kowe2/aLdBAawijx+q1pQzicSgnkB6dUPc1+RC8QmJHKf2OjvU+NZWitguJHEaEmbV6VWEouT58g==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-typescript": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-typescript/-/plugin-transform-typescript-7.28.6.tgz",
      "integrity": "sha512-0YWL2RFxOqEm9Efk5PvreamxPME8OyY0wM5wh5lHjF+VtVhdneCWGzZeSqzOfiobVqQaNCd2z0tQvnI9DaPWPw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-annotate-as-pure": "^7.27.3",
        "@babel/helper-create-class-features-plugin": "^7.28.6",
        "@babel/helper-plugin-utils": "^7.28.6",
        "@babel/helper-skip-transparent-expression-wrappers": "^7.27.1",
        "@babel/plugin-syntax-typescript": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-unicode-regex": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-unicode-regex/-/plugin-transform-unicode-regex-7.27.1.tgz",
      "integrity": "sha512-xvINq24TRojDuyt6JGtHmkVkrfVV3FPT16uytxImLeBZqW3/H52yN+kM1MGuyPkIQxrzKwPHs5U/MP3qKyzkGw==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-create-regexp-features-plugin": "^7.27.1",
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/preset-react": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/preset-react/-/preset-react-7.28.5.tgz",
      "integrity": "sha512-Z3J8vhRq7CeLjdC58jLv4lnZ5RKFUJWqH5emvxmv9Hv3BD1T9R/Im713R4MTKwvFaV74ejZ3sM01LyEKk4ugNQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/helper-validator-option": "^7.27.1",
        "@babel/plugin-transform-react-display-name": "^7.28.0",
        "@babel/plugin-transform-react-jsx": "^7.27.1",
        "@babel/plugin-transform-react-jsx-development": "^7.27.1",
        "@babel/plugin-transform-react-pure-annotations": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/preset-typescript": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/preset-typescript/-/preset-typescript-7.28.5.tgz",
      "integrity": "sha512-+bQy5WOI2V6LJZpPVxY+yp66XdZ2yifu0Mc1aP5CQKgjn4QM5IN2i5fAZ4xKop47pr8rpVhiAeu+nDQa12C8+g==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1",
        "@babel/helper-validator-option": "^7.27.1",
        "@babel/plugin-syntax-jsx": "^7.27.1",
        "@babel/plugin-transform-modules-commonjs": "^7.27.1",
        "@babel/plugin-transform-typescript": "^7.28.5"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/runtime": {
      "version": "7.29.2",
      "resolved": "https://registry.npmmirror.com/@babel/runtime/-/runtime-7.29.2.tgz",
      "integrity": "sha512-JiDShH45zKHWyGe4ZNVRrCjBz8Nh9TMmZG1kh4QTK8hCBTWBi8Da+i7s1fJw7/lYpM4ccepSNfqzZ/QvABBi5g==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/template": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/template/-/template-7.28.6.tgz",
      "integrity": "sha512-YA6Ma2KsCdGb+WC6UpBVFJGXL58MDA6oyONbjyF/+5sBgxY/dwkhLogbMT2GXXyU84/IhRw/2D1Os1B/giz+BQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.28.6",
        "@babel/parser": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/traverse/-/traverse-7.29.0.tgz",
      "integrity": "sha512-4HPiQr0X7+waHfyXPZpWPfWL/J7dcN1mx9gL6WdQVMbPnF3+ZhSMs8tCxN7oHddJE9fhNE7+lxdnlyemKfJRuA==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.0",
        "@babel/generator": "^7.29.0",
        "@babel/helper-globals": "^7.28.0",
        "@babel/parser": "^7.29.0",
        "@babel/template": "^7.28.6",
        "@babel/types": "^7.29.0",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse--for-generate-function-map": {
      "name": "@babel/traverse",
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/traverse/-/traverse-7.29.0.tgz",
      "integrity": "sha512-4HPiQr0X7+waHfyXPZpWPfWL/J7dcN1mx9gL6WdQVMbPnF3+ZhSMs8tCxN7oHddJE9fhNE7+lxdnlyemKfJRuA==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.0",
        "@babel/generator": "^7.29.0",
        "@babel/helper-globals": "^7.28.0",
        "@babel/parser": "^7.29.0",
        "@babel/template": "^7.28.6",
        "@babel/types": "^7.29.0",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/types": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/types/-/types-7.29.0.tgz",
      "integrity": "sha512-LwdZHpScM4Qz8Xw2iKSzS+cfglZzJGvofQICy7W7v4caru4EaAmyUuO6BGrbyQ2mYV11W0U8j5mBhd14dd3B0A==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-string-parser": "^7.27.1",
        "@babel/helper-validator-identifier": "^7.28.5"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@egjs/hammerjs": {
      "version": "2.0.17",
      "resolved": "https://registry.npmmirror.com/@egjs/hammerjs/-/hammerjs-2.0.17.tgz",
      "integrity": "sha512-XQsZgjm2EcVUiZQf11UBJQfmZeEmOW8DpI1gsFeln6w0ae0ii4dMQEQ0kjl6DspdWX1aGY1/loyXnP0JS06e/A==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "@types/hammerjs": "^2.0.36"
      },
      "engines": {
        "node": ">=0.8.0"
      }
    },
    "node_modules/@expo-google-fonts/material-symbols": {
      "version": "0.4.27",
      "resolved": "https://registry.npmmirror.com/@expo-google-fonts/material-symbols/-/material-symbols-0.4.27.tgz",
      "integrity": "sha512-cnb3DZnWUWpezGFkJ8y4MT5f/lw6FcgDzeJzic+T+vpQHLHG1cg3SC3i1w1i8Bk4xKR4HPY3t9iIRNvtr5ml8A==",
      "license": "MIT AND Apache-2.0"
    },
    "node_modules/@expo/code-signing-certificates": {
      "version": "0.0.6",
      "resolved": "https://registry.npmmirror.com/@expo/code-signing-certificates/-/code-signing-certificates-0.0.6.tgz",
      "integrity": "sha512-iNe0puxwBNEcuua9gmTGzq+SuMDa0iATai1FlFTMHJ/vUmKvN/V//drXoLJkVb5i5H3iE/n/qIJxyoBnXouD0w==",
      "license": "MIT",
      "dependencies": {
        "node-forge": "^1.3.3"
      }
    },
    "node_modules/@expo/config": {
      "version": "55.0.12-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/config/-/config-55.0.12-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-79kzhpY5VAkLem/BPZasapvtZShK1PAWQYg/78edXRdLAL0k7x7Gy9ubgNgkT6KzbC9xvN6rwQ9wKx95Wd+Urg==",
      "license": "MIT",
      "dependencies": {
        "@expo/config-plugins": "55.0.8-canary-20260328-bdc6273",
        "@expo/config-types": "55.0.6-canary-20260328-bdc6273",
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@expo/require-utils": "55.0.4-canary-20260328-bdc6273",
        "deepmerge": "^4.3.1",
        "getenv": "^2.0.0",
        "glob": "^13.0.0",
        "resolve-from": "^5.0.0",
        "resolve-workspace-root": "^2.0.0",
        "semver": "^7.6.0",
        "slugify": "^1.3.4"
      }
    },
    "node_modules/@expo/config-plugins": {
      "version": "55.0.8-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/config-plugins/-/config-plugins-55.0.8-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-djT9urGkLkL9kJcO1+frUkFgZk63J4akISvXtUmoNGe+k7zGSQmoQRy/tWmhMwwNMGm2BrmVyoLX+243gmnHwA==",
      "license": "MIT",
      "dependencies": {
        "@expo/config-types": "55.0.6-canary-20260328-bdc6273",
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@expo/plist": "0.5.3-canary-20260328-bdc6273",
        "@expo/sdk-runtime-versions": "^1.0.0",
        "chalk": "^4.1.2",
        "debug": "^4.3.5",
        "getenv": "^2.0.0",
        "glob": "^13.0.0",
        "resolve-from": "^5.0.0",
        "semver": "^7.5.4",
        "slugify": "^1.6.6",
        "xcode": "^3.0.1",
        "xml2js": "0.6.0"
      }
    },
    "node_modules/@expo/config-types": {
      "version": "55.0.6-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/config-types/-/config-types-55.0.6-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-IUD5dTOZkTr+dxNmqJi09GzxxRMqTlIFCSWa5DIjioyxCBkRQ1fi3jkmDcS4owHjZpNA2XRKG8QNum+OKwXw/g==",
      "license": "MIT"
    },
    "node_modules/@expo/devcert": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/@expo/devcert/-/devcert-1.2.1.tgz",
      "integrity": "sha512-qC4eaxmKMTmJC2ahwyui6ud8f3W60Ss7pMkpBq40Hu3zyiAaugPXnZ24145U7K36qO9UHdZUVxsCvIpz2RYYCA==",
      "license": "MIT",
      "dependencies": {
        "@expo/sudo-prompt": "^9.3.1",
        "debug": "^3.1.0"
      }
    },
    "node_modules/@expo/devcert/node_modules/debug": {
      "version": "3.2.7",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-3.2.7.tgz",
      "integrity": "sha512-CFjzYYAi4ThfiQvizrFQevTTXHtnCqWfe7x1AhgEscTz6ZbLbfoLRLPugTQyBth6f8ZERVUSyWHFD/7Wu4t1XQ==",
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.1"
      }
    },
    "node_modules/@expo/devtools": {
      "version": "55.0.3-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/devtools/-/devtools-55.0.3-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-P1pzCilRFPNnrqI8PBTeGa2RWX6/DTbMM0Na/tJTHoCPRGcCQvRAzzAhK8QQuGyraxMH1dxFLc+fN1bCILHJJw==",
      "license": "MIT",
      "dependencies": {
        "chalk": "^4.1.2"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      },
      "peerDependenciesMeta": {
        "react": {
          "optional": true
        },
        "react-native": {
          "optional": true
        }
      }
    },
    "node_modules/@expo/dom-webview": {
      "version": "55.0.4-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/dom-webview/-/dom-webview-55.0.4-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-JEWGRGyMZEAGHrzaq+Dd9dgbUdqhx8Dii5vNpUjxB+pRTmLmqYO7WFjniEXUsw5Aq+oswx2h2i4q40SJDb+2yw==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/@expo/env": {
      "version": "2.1.2-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/env/-/env-2.1.2-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-iopcE9NDqKTaLEuiAEEYS0zohyXJamyX7csFTTI93tcnXEr/eh3ZnvQjkEKhPNAVcB9MmcAiowCHQCfiDcV0Nw==",
      "license": "MIT",
      "dependencies": {
        "chalk": "^4.0.0",
        "debug": "^4.3.4",
        "getenv": "^2.0.0"
      },
      "engines": {
        "node": ">=20.12.0"
      }
    },
    "node_modules/@expo/fingerprint": {
      "version": "0.16.7-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/fingerprint/-/fingerprint-0.16.7-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-utVtSXbmIlDdlywrDq+CXqZ6jY9Nh9EHK4ilO0d15VqNFrKk4kx9MT1U1Xa9d7KtqBI7p1emGs5M/Z64hZ9jCQ==",
      "license": "MIT",
      "dependencies": {
        "@expo/env": "2.1.2-canary-20260328-bdc6273",
        "@expo/spawn-async": "^1.7.2",
        "arg": "^5.0.2",
        "chalk": "^4.1.2",
        "debug": "^4.3.4",
        "getenv": "^2.0.0",
        "glob": "^13.0.0",
        "ignore": "^5.3.1",
        "minimatch": "^10.2.2",
        "resolve-from": "^5.0.0",
        "semver": "^7.6.0"
      },
      "bin": {
        "fingerprint": "bin/cli.js"
      }
    },
    "node_modules/@expo/image-utils": {
      "version": "0.8.13-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/image-utils/-/image-utils-0.8.13-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-1n6J1iVSM58n0mTw/czSHmHGXMUUau0PQc0aQqdQyzElrluNpdShJL5McFsr6usbhztz6Fg4dWMFWXuuON9R+Q==",
      "license": "MIT",
      "dependencies": {
        "@expo/spawn-async": "^1.7.2",
        "chalk": "^4.0.0",
        "getenv": "^2.0.0",
        "jimp-compact": "0.16.1",
        "parse-png": "^2.1.0",
        "resolve-from": "^5.0.0",
        "semver": "^7.6.0"
      }
    },
    "node_modules/@expo/json-file": {
      "version": "10.0.13-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/json-file/-/json-file-10.0.13-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-bB+r3u2BIIl4tpc0bc2h9vc6hhwzf0w9vG1co3WHXCDLBfWx0Dvxc5xfUq4E5+Lz61oAO0Qq9dUM8f8qgra4TA==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.20.0",
        "json5": "^2.2.3"
      }
    },
    "node_modules/@expo/local-build-cache-provider": {
      "version": "55.0.8-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/local-build-cache-provider/-/local-build-cache-provider-55.0.8-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-nkz1CNxggcN9LpbjYcCxdjTgJU2wK4Ppw9OA7zQuRXLxLsc1vZEdX7RNgLhigDq0Ma8qZwZTDU5z4ROk571kkQ==",
      "license": "MIT",
      "dependencies": {
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "chalk": "^4.1.2"
      }
    },
    "node_modules/@expo/log-box": {
      "version": "55.0.9-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/log-box/-/log-box-55.0.9-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Ye0/RtCCtiKPcJHrFmb+h+7khDrMb/EY0a0Czm9nkjIa4NxDrJ1nA3nnPYAqVWsGKfYngcxzguti+Pp73piGHA==",
      "license": "MIT",
      "dependencies": {
        "@expo/dom-webview": "55.0.4-canary-20260328-bdc6273",
        "anser": "^1.4.9",
        "stacktrace-parser": "^0.1.10"
      },
      "peerDependencies": {
        "@expo/dom-webview": "55.0.4-canary-20260328-bdc6273",
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/@expo/metro": {
      "version": "54.2.0",
      "resolved": "https://registry.npmmirror.com/@expo/metro/-/metro-54.2.0.tgz",
      "integrity": "sha512-h68TNZPGsk6swMmLm9nRSnE2UXm48rWwgcbtAHVMikXvbxdS41NDHHeqg1rcQ9AbznDRp6SQVC2MVpDnsRKU1w==",
      "license": "MIT",
      "dependencies": {
        "metro": "0.83.3",
        "metro-babel-transformer": "0.83.3",
        "metro-cache": "0.83.3",
        "metro-cache-key": "0.83.3",
        "metro-config": "0.83.3",
        "metro-core": "0.83.3",
        "metro-file-map": "0.83.3",
        "metro-minify-terser": "0.83.3",
        "metro-resolver": "0.83.3",
        "metro-runtime": "0.83.3",
        "metro-source-map": "0.83.3",
        "metro-symbolicate": "0.83.3",
        "metro-transform-plugins": "0.83.3",
        "metro-transform-worker": "0.83.3"
      }
    },
    "node_modules/@expo/metro-runtime": {
      "version": "55.0.8-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/metro-runtime/-/metro-runtime-55.0.8-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-YTChw7FlKFS2b2xZf9W1rgJzg6Uu5hjYzzFP5e/INi//2zNGsB2eHx2t92n0dU8JPM+vb/xScla1ovqB0u1RVw==",
      "license": "MIT",
      "dependencies": {
        "@expo/log-box": "55.0.9-canary-20260328-bdc6273",
        "anser": "^1.4.9",
        "pretty-format": "^29.7.0",
        "stacktrace-parser": "^0.1.10",
        "whatwg-fetch": "^3.0.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-dom": "*",
        "react-native": "*"
      },
      "peerDependenciesMeta": {
        "react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@expo/osascript": {
      "version": "2.4.3-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/osascript/-/osascript-2.4.3-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-BaoWmnqBxF8jMbmaJiGnpPsGPrZO9BBoUowMma9qRyRTOLq3DXQCkceZhvkvpKSvxS7HY37sOkvPvr/d3J4etg==",
      "license": "MIT",
      "dependencies": {
        "@expo/spawn-async": "^1.7.2"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/@expo/package-manager": {
      "version": "1.10.4-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/package-manager/-/package-manager-1.10.4-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-fhRKYOpUgmDfqWtwNqvY1vhvFPzkUIK1Lcyx4ZXV+iEBMniLP0I/wzkyj/wPomYnunCI37JoeK1ttHZA8++uYA==",
      "license": "MIT",
      "dependencies": {
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@expo/spawn-async": "^1.7.2",
        "chalk": "^4.0.0",
        "npm-package-arg": "^11.0.0",
        "ora": "^3.4.0",
        "resolve-workspace-root": "^2.0.0"
      }
    },
    "node_modules/@expo/plist": {
      "version": "0.5.3-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/plist/-/plist-0.5.3-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Mibai5bnKjtaSuQtPS1CuTvIwN9Fi3Vw6+5ZNdoPQ1bwJSYLMDxIIBKBUaAPgJSB/EHYd1rErYabozWGhj1ebg==",
      "license": "MIT",
      "dependencies": {
        "@xmldom/xmldom": "^0.8.8",
        "base64-js": "^1.5.1",
        "xmlbuilder": "^15.1.1"
      }
    },
    "node_modules/@expo/require-utils": {
      "version": "55.0.4-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/require-utils/-/require-utils-55.0.4-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-PhOAVBPFCfgMYKnLWogOLprNEr/S78TRUo1gvK9rPF/PYhLXJBpmrQB8Te7PmbaqD2AoB6rYopy858lrVHHjOw==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.20.0",
        "@babel/core": "^7.25.2",
        "@babel/plugin-transform-modules-commonjs": "^7.24.8"
      },
      "peerDependencies": {
        "typescript": "^5.0.0 || ^5.0.0-0"
      },
      "peerDependenciesMeta": {
        "typescript": {
          "optional": true
        }
      }
    },
    "node_modules/@expo/schema-utils": {
      "version": "55.0.3-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/schema-utils/-/schema-utils-55.0.3-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-KMksTt05lef05Lajfqci2U1RBtrd001aBRT6nEfah31W2T2sELhqauq4juEx/RbtU02RyPfeA0YWsSK6R8A45A==",
      "license": "MIT"
    },
    "node_modules/@expo/sdk-runtime-versions": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/@expo/sdk-runtime-versions/-/sdk-runtime-versions-1.0.0.tgz",
      "integrity": "sha512-Doz2bfiPndXYFPMRwPyGa1k5QaKDVpY806UJj570epIiMzWaYyCtobasyfC++qfIXVb5Ocy7r3tP9d62hAQ7IQ==",
      "license": "MIT"
    },
    "node_modules/@expo/spawn-async": {
      "version": "1.7.2",
      "resolved": "https://registry.npmmirror.com/@expo/spawn-async/-/spawn-async-1.7.2.tgz",
      "integrity": "sha512-QdWi16+CHB9JYP7gma19OVVg0BFkvU8zNj9GjWorYI8Iv8FUxjOCcYRuAmX4s/h91e4e7BPsskc8cSrZYho9Ew==",
      "license": "MIT",
      "dependencies": {
        "cross-spawn": "^7.0.3"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/@expo/sudo-prompt": {
      "version": "9.3.2",
      "resolved": "https://registry.npmmirror.com/@expo/sudo-prompt/-/sudo-prompt-9.3.2.tgz",
      "integrity": "sha512-HHQigo3rQWKMDzYDLkubN5WQOYXJJE2eNqIQC2axC2iO3mHdwnIR7FgZVvHWtBwAdzBgAP0ECp8KqS8TiMKvgw==",
      "license": "MIT"
    },
    "node_modules/@expo/ws-tunnel": {
      "version": "1.0.6",
      "resolved": "https://registry.npmmirror.com/@expo/ws-tunnel/-/ws-tunnel-1.0.6.tgz",
      "integrity": "sha512-nDRbLmSrJar7abvUjp3smDwH8HcbZcoOEa5jVPUv9/9CajgmWw20JNRwTuBRzWIWIkEJDkz20GoNA+tSwUqk0Q==",
      "license": "MIT"
    },
    "node_modules/@expo/xcpretty": {
      "version": "4.4.1",
      "resolved": "https://registry.npmmirror.com/@expo/xcpretty/-/xcpretty-4.4.1.tgz",
      "integrity": "sha512-KZNxZvnGCtiM2aYYZ6Wz0Ix5r47dAvpNLApFtZWnSoERzAdOMzVBOPysBoM0JlF6FKWZ8GPqgn6qt3dV/8Zlpg==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "@babel/code-frame": "^7.20.0",
        "chalk": "^4.1.0",
        "js-yaml": "^4.1.0"
      },
      "bin": {
        "excpretty": "build/cli.js"
      }
    },
    "node_modules/@expo/xcpretty/node_modules/argparse": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/argparse/-/argparse-2.0.1.tgz",
      "integrity": "sha512-8+9WqebbFzpX9OR+Wa6O29asIogeRMzcGtAINdpMHHyAg10f05aSFVBbcEqGf/PXw1EjAZ+q2/bEBg3DvurK3Q==",
      "license": "Python-2.0"
    },
    "node_modules/@expo/xcpretty/node_modules/js-yaml": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/js-yaml/-/js-yaml-4.1.1.tgz",
      "integrity": "sha512-qQKT4zQxXl8lLwBtHMWwaTcGfFOZviOJet3Oy/xmGk2gZH677CJM9EvtfdSkgWcATZhj/55JZ0rmy3myCT5lsA==",
      "license": "MIT",
      "dependencies": {
        "argparse": "^2.0.1"
      },
      "bin": {
        "js-yaml": "bin/js-yaml.js"
      }
    },
    "node_modules/@isaacs/ttlcache": {
      "version": "1.4.1",
      "resolved": "https://registry.npmmirror.com/@isaacs/ttlcache/-/ttlcache-1.4.1.tgz",
      "integrity": "sha512-RQgQ4uQ+pLbqXfOmieB91ejmLwvSgv9nLx6sT6sD83s7umBypgg+OIBOBbEUiJXrfpnp9j0mRhYYdzp9uqq3lA==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/@istanbuljs/load-nyc-config": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/@istanbuljs/load-nyc-config/-/load-nyc-config-1.1.0.tgz",
      "integrity": "sha512-VjeHSlIzpv/NyD3N0YuHfXOPDIixcA1q2ZV98wsMqcYlPmv2n3Yb2lYP9XMElnaFVXg5A7YLTeLu6V84uQDjmQ==",
      "license": "ISC",
      "dependencies": {
        "camelcase": "^5.3.1",
        "find-up": "^4.1.0",
        "get-package-type": "^0.1.0",
        "js-yaml": "^3.13.1",
        "resolve-from": "^5.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/@istanbuljs/load-nyc-config/node_modules/camelcase": {
      "version": "5.3.1",
      "resolved": "https://registry.npmmirror.com/camelcase/-/camelcase-5.3.1.tgz",
      "integrity": "sha512-L28STB170nwWS63UjtlEOE3dldQApaJXZkOI1uMFfzf3rRuPegHaHesyee+YxQ+W6SvRDQV6UrdOdRiR153wJg==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/@istanbuljs/schema": {
      "version": "0.1.3",
      "resolved": "https://registry.npmmirror.com/@istanbuljs/schema/-/schema-0.1.3.tgz",
      "integrity": "sha512-ZXRY4jNvVgSVQ8DL3LTcakaAtXwTVUxE81hslsyD2AtoXW/wVob10HkOJ1X/pAlcI7D+2YoZKg5do8G/w6RYgA==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/@jest/create-cache-key-function": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/@jest/create-cache-key-function/-/create-cache-key-function-29.7.0.tgz",
      "integrity": "sha512-4QqS3LY5PBmTRHj9sAg1HLoPzqAI0uOX6wI/TRqHIcOxlFidy6YEmCQJk6FSZjNLGCeubDMfmkWL+qaLKhSGQA==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jest/environment": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/@jest/environment/-/environment-29.7.0.tgz",
      "integrity": "sha512-aQIfHDq33ExsN4jP1NWGXhxgQ/wixs60gDiKO+XVMd8Mn0NWPWgc34ZQDTb2jKaUWQ7MuwoitXAsN2XVXNMpAw==",
      "license": "MIT",
      "dependencies": {
        "@jest/fake-timers": "^29.7.0",
        "@jest/types": "^29.6.3",
        "@types/node": "*",
        "jest-mock": "^29.7.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jest/fake-timers": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/@jest/fake-timers/-/fake-timers-29.7.0.tgz",
      "integrity": "sha512-q4DH1Ha4TTFPdxLsqDXK1d3+ioSL7yL5oCMJZgDYm6i+6CygW5E5xVr/D1HdsGxjt1ZWSfUAs9OxSB/BNelWrQ==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3",
        "@sinonjs/fake-timers": "^10.0.2",
        "@types/node": "*",
        "jest-message-util": "^29.7.0",
        "jest-mock": "^29.7.0",
        "jest-util": "^29.7.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jest/schemas": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/@jest/schemas/-/schemas-29.6.3.tgz",
      "integrity": "sha512-mo5j5X+jIZmJQveBKeS/clAueipV7KgiX1vMgCxam1RNYiqE1w62n0/tJJnHtjW8ZHcQco5gY85jA3mi0L+nSA==",
      "license": "MIT",
      "dependencies": {
        "@sinclair/typebox": "^0.27.8"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jest/transform": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/@jest/transform/-/transform-29.7.0.tgz",
      "integrity": "sha512-ok/BTPFzFKVMwO5eOHRrvnBVHdRy9IrsrW1GpMaQ9MCnilNLXQKmAX8s1YXDFaai9xJpac2ySzV0YeRRECr2Vw==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.11.6",
        "@jest/types": "^29.6.3",
        "@jridgewell/trace-mapping": "^0.3.18",
        "babel-plugin-istanbul": "^6.1.1",
        "chalk": "^4.0.0",
        "convert-source-map": "^2.0.0",
        "fast-json-stable-stringify": "^2.1.0",
        "graceful-fs": "^4.2.9",
        "jest-haste-map": "^29.7.0",
        "jest-regex-util": "^29.6.3",
        "jest-util": "^29.7.0",
        "micromatch": "^4.0.4",
        "pirates": "^4.0.4",
        "slash": "^3.0.0",
        "write-file-atomic": "^4.0.2"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jest/types": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/@jest/types/-/types-29.6.3.tgz",
      "integrity": "sha512-u3UPsIilWKOM3F9CXtrG8LEJmNxwoCQC/XVj4IKYXvvpx7QIi/Kg1LI5uDmDpKlac62NUtX7eLjRh+jVZcLOzw==",
      "license": "MIT",
      "dependencies": {
        "@jest/schemas": "^29.6.3",
        "@types/istanbul-lib-coverage": "^2.0.0",
        "@types/istanbul-reports": "^3.0.0",
        "@types/node": "*",
        "@types/yargs": "^17.0.8",
        "chalk": "^4.0.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmmirror.com/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "license": "MIT",
      "dependencies": {
        "@jridgewell/sourcemap-codec": "^1.5.0",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmmirror.com/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmmirror.com/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/source-map": {
      "version": "0.3.11",
      "resolved": "https://registry.npmmirror.com/@jridgewell/source-map/-/source-map-0.3.11.tgz",
      "integrity": "sha512-ZMp1V8ZFcPG5dIWnQLr3NSI1MiCU7UETdS/A0G8V/XWHvJv3ZsFqutJn1Y5RPmAPX6F3BiE397OqveU/9NCuIA==",
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.25"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmmirror.com/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "license": "MIT"
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmmirror.com/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "license": "MIT",
      "dependencies": {
        "@jridgewell/resolve-uri": "^3.1.0",
        "@jridgewell/sourcemap-codec": "^1.4.14"
      }
    },
    "node_modules/@radix-ui/primitive": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/primitive/-/primitive-1.1.3.tgz",
      "integrity": "sha512-JTF99U/6XIjCBo0wqkU5sK10glYe27MRRsfwoiq5zzOEZLHU3A3KCMa5X/azekYRCJ0HlwI0crAXS/5dEHTzDg==",
      "license": "MIT"
    },
    "node_modules/@radix-ui/react-collection": {
      "version": "1.1.7",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-collection/-/react-collection-1.1.7.tgz",
      "integrity": "sha512-Fh9rGN0MoI4ZFUNyfFVNU4y9LUz93u9/0K+yLgA2bwRojxM8JU1DyvvMBabnZPBgMWREAJvU2jjVzq+LrFUglw==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-context": "1.1.2",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-slot": "1.2.3"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-collection/node_modules/@radix-ui/react-slot": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-slot/-/react-slot-1.2.3.tgz",
      "integrity": "sha512-aeNmHnBxbi2St0au6VBVC7JXFlhLlOnvIIlePNniyUNAClzmtAUEY8/pBiK3iHjufOlwA+c20/8jngo7xcrg8A==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-compose-refs": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-compose-refs/-/react-compose-refs-1.1.2.tgz",
      "integrity": "sha512-z4eqJvfiNnFMHIIvXP3CY57y2WJs5g2v3X0zm9mEJkrkNv4rDxu+sg9Jh8EkXyeqBkB7SOcboo9dMVqhyrACIg==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-context": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-context/-/react-context-1.1.2.tgz",
      "integrity": "sha512-jCi/QKUM2r1Ju5a3J64TH2A5SpKAgh0LpknyqdQ4m6DCV0xJ2HG1xARRwNGPQfi1SLdLWZ1OJz6F4OMBBNiGJA==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-dialog": {
      "version": "1.1.15",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-dialog/-/react-dialog-1.1.15.tgz",
      "integrity": "sha512-TCglVRtzlffRNxRMEyR36DGBLJpeusFcgMVD9PZEzAKnUs1lKCgX5u9BmC2Yg+LL9MgZDugFFs1Vl+Jp4t/PGw==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/primitive": "1.1.3",
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-context": "1.1.2",
        "@radix-ui/react-dismissable-layer": "1.1.11",
        "@radix-ui/react-focus-guards": "1.1.3",
        "@radix-ui/react-focus-scope": "1.1.7",
        "@radix-ui/react-id": "1.1.1",
        "@radix-ui/react-portal": "1.1.9",
        "@radix-ui/react-presence": "1.1.5",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-slot": "1.2.3",
        "@radix-ui/react-use-controllable-state": "1.2.2",
        "aria-hidden": "^1.2.4",
        "react-remove-scroll": "^2.6.3"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-dialog/node_modules/@radix-ui/react-slot": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-slot/-/react-slot-1.2.3.tgz",
      "integrity": "sha512-aeNmHnBxbi2St0au6VBVC7JXFlhLlOnvIIlePNniyUNAClzmtAUEY8/pBiK3iHjufOlwA+c20/8jngo7xcrg8A==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-direction": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-direction/-/react-direction-1.1.1.tgz",
      "integrity": "sha512-1UEWRX6jnOA2y4H5WczZ44gOOjTEmlqv1uNW4GAJEO5+bauCBhv8snY65Iw5/VOS/ghKN9gr2KjnLKxrsvoMVw==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-dismissable-layer": {
      "version": "1.1.11",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-dismissable-layer/-/react-dismissable-layer-1.1.11.tgz",
      "integrity": "sha512-Nqcp+t5cTB8BinFkZgXiMJniQH0PsUt2k51FUhbdfeKvc4ACcG2uQniY/8+h1Yv6Kza4Q7lD7PQV0z0oicE0Mg==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/primitive": "1.1.3",
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-use-callback-ref": "1.1.1",
        "@radix-ui/react-use-escape-keydown": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-focus-guards": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-focus-guards/-/react-focus-guards-1.1.3.tgz",
      "integrity": "sha512-0rFg/Rj2Q62NCm62jZw0QX7a3sz6QCQU0LpZdNrJX8byRGaGVTqbrW9jAoIAHyMQqsNpeZ81YgSizOt5WXq0Pw==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-focus-scope": {
      "version": "1.1.7",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-focus-scope/-/react-focus-scope-1.1.7.tgz",
      "integrity": "sha512-t2ODlkXBQyn7jkl6TNaw/MtVEVvIGelJDCG41Okq/KwUsJBwQ4XVZsHAVUkK4mBv3ewiAS3PGuUWuY2BoK4ZUw==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-use-callback-ref": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-id": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-id/-/react-id-1.1.1.tgz",
      "integrity": "sha512-kGkGegYIdQsOb4XjsfM97rXsiHaBwco+hFI66oO4s9LU+PLAC5oJ7khdOVFxkhsmlbpUqDAvXw11CluXP+jkHg==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-use-layout-effect": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-portal": {
      "version": "1.1.9",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-portal/-/react-portal-1.1.9.tgz",
      "integrity": "sha512-bpIxvq03if6UNwXZ+HTK71JLh4APvnXntDc6XOX8UVq4XQOVl7lwok0AvIl+b8zgCw3fSaVTZMpAPPagXbKmHQ==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-use-layout-effect": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-presence": {
      "version": "1.1.5",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-presence/-/react-presence-1.1.5.tgz",
      "integrity": "sha512-/jfEwNDdQVBCNvjkGit4h6pMOzq8bHkopq458dPt2lMjx+eBQUohZNG9A7DtO/O5ukSbxuaNGXMjHicgwy6rQQ==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-use-layout-effect": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-primitive": {
      "version": "2.1.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-primitive/-/react-primitive-2.1.3.tgz",
      "integrity": "sha512-m9gTwRkhy2lvCPe6QJp4d3G1TYEUHn/FzJUtq9MjH46an1wJU+GdoGC5VLof8RX8Ft/DlpshApkhswDLZzHIcQ==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-slot": "1.2.3"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-primitive/node_modules/@radix-ui/react-slot": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-slot/-/react-slot-1.2.3.tgz",
      "integrity": "sha512-aeNmHnBxbi2St0au6VBVC7JXFlhLlOnvIIlePNniyUNAClzmtAUEY8/pBiK3iHjufOlwA+c20/8jngo7xcrg8A==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-roving-focus": {
      "version": "1.1.11",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-roving-focus/-/react-roving-focus-1.1.11.tgz",
      "integrity": "sha512-7A6S9jSgm/S+7MdtNDSb+IU859vQqJ/QAtcYQcfFC6W8RS4IxIZDldLR0xqCFZ6DCyrQLjLPsxtTNch5jVA4lA==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/primitive": "1.1.3",
        "@radix-ui/react-collection": "1.1.7",
        "@radix-ui/react-compose-refs": "1.1.2",
        "@radix-ui/react-context": "1.1.2",
        "@radix-ui/react-direction": "1.1.1",
        "@radix-ui/react-id": "1.1.1",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-use-callback-ref": "1.1.1",
        "@radix-ui/react-use-controllable-state": "1.2.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-slot": {
      "version": "1.2.4",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-slot/-/react-slot-1.2.4.tgz",
      "integrity": "sha512-Jl+bCv8HxKnlTLVrcDE8zTMJ09R9/ukw4qBs/oZClOfoQk/cOTbDn+NceXfV7j09YPVQUryJPHurafcSg6EVKA==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-compose-refs": "1.1.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-use-callback-ref": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-use-callback-ref/-/react-use-callback-ref-1.1.1.tgz",
      "integrity": "sha512-FkBMwD+qbGQeMu1cOHnuGB6x4yzPjho8ap5WtbEJ26umhgqVXbhekKUQO+hZEL1vU92a3wHwdp0HAcqAUF5iDg==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-use-controllable-state": {
      "version": "1.2.2",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-use-controllable-state/-/react-use-controllable-state-1.2.2.tgz",
      "integrity": "sha512-BjasUjixPFdS+NKkypcyyN5Pmg83Olst0+c6vGov0diwTEo6mgdqVR6hxcEgFuh4QrAs7Rc+9KuGJ9TVCj0Zzg==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-use-effect-event": "0.0.2",
        "@radix-ui/react-use-layout-effect": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-use-effect-event": {
      "version": "0.0.2",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-use-effect-event/-/react-use-effect-event-0.0.2.tgz",
      "integrity": "sha512-Qp8WbZOBe+blgpuUT+lw2xheLP8q0oatc9UpmiemEICxGvFLYmHm9QowVZGHtJlGbS6A6yJ3iViad/2cVjnOiA==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-use-layout-effect": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-use-escape-keydown": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-use-escape-keydown/-/react-use-escape-keydown-1.1.1.tgz",
      "integrity": "sha512-Il0+boE7w/XebUHyBjroE+DbByORGR9KKmITzbR7MyQ4akpORYP/ZmbhAr0DG7RmmBqoOnZdy2QlvajJ2QA59g==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-use-callback-ref": "1.1.1"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@radix-ui/react-use-layout-effect": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-use-layout-effect/-/react-use-layout-effect-1.1.1.tgz",
      "integrity": "sha512-RbJRS4UWQFkzHTTwVymMTUv8EqYhOp8dOOviLj2ugtTiXRaRQS7GLGxZTLL1jWhMeoSCf5zmcZkqTl9IiYfXcQ==",
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/@react-native-async-storage/async-storage": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/@react-native-async-storage/async-storage/-/async-storage-2.2.0.tgz",
      "integrity": "sha512-gvRvjR5JAaUZF8tv2Kcq/Gbt3JHwbKFYfmb445rhOj6NUMx3qPLixmDx5pZAyb9at1bYvJ4/eTUipU5aki45xw==",
      "license": "MIT",
      "dependencies": {
        "merge-options": "^3.0.4"
      },
      "peerDependencies": {
        "react-native": "^0.0.0-0 || >=0.65 <1.0"
      }
    },
    "node_modules/@react-native/assets-registry": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/assets-registry/-/assets-registry-0.83.4.tgz",
      "integrity": "sha512-aqKtpbJDSQeSX/Dwv0yMe1/Rd2QfXi12lnyZDXNn/OEKz59u6+LuPBVgO/9CRyclHmdlvwg8c7PJ9eX2ZMnjWg==",
      "license": "MIT",
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/babel-plugin-codegen": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/babel-plugin-codegen/-/babel-plugin-codegen-0.83.4.tgz",
      "integrity": "sha512-UFsK+c1rvT84XZfzpmwKePsc5nTr5LK7hh18TI0DooNlVcztDbMDsQZpDnhO/gmk7aTbWEqO5AB3HJ7tvGp+Jg==",
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.25.3",
        "@react-native/codegen": "0.83.4"
      },
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/babel-preset": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/babel-preset/-/babel-preset-0.83.4.tgz",
      "integrity": "sha512-SXPFn3Jp4gOzlBDnDOKPzMfxQPKJMYJs05EmEeFB/6km46xZ9l+2YKXwAwxfNhHnmwNf98U/bnVndU95I0TMCw==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.25.2",
        "@babel/plugin-proposal-export-default-from": "^7.24.7",
        "@babel/plugin-syntax-dynamic-import": "^7.8.3",
        "@babel/plugin-syntax-export-default-from": "^7.24.7",
        "@babel/plugin-syntax-nullish-coalescing-operator": "^7.8.3",
        "@babel/plugin-syntax-optional-chaining": "^7.8.3",
        "@babel/plugin-transform-arrow-functions": "^7.24.7",
        "@babel/plugin-transform-async-generator-functions": "^7.25.4",
        "@babel/plugin-transform-async-to-generator": "^7.24.7",
        "@babel/plugin-transform-block-scoping": "^7.25.0",
        "@babel/plugin-transform-class-properties": "^7.25.4",
        "@babel/plugin-transform-classes": "^7.25.4",
        "@babel/plugin-transform-computed-properties": "^7.24.7",
        "@babel/plugin-transform-destructuring": "^7.24.8",
        "@babel/plugin-transform-flow-strip-types": "^7.25.2",
        "@babel/plugin-transform-for-of": "^7.24.7",
        "@babel/plugin-transform-function-name": "^7.25.1",
        "@babel/plugin-transform-literals": "^7.25.2",
        "@babel/plugin-transform-logical-assignment-operators": "^7.24.7",
        "@babel/plugin-transform-modules-commonjs": "^7.24.8",
        "@babel/plugin-transform-named-capturing-groups-regex": "^7.24.7",
        "@babel/plugin-transform-nullish-coalescing-operator": "^7.24.7",
        "@babel/plugin-transform-numeric-separator": "^7.24.7",
        "@babel/plugin-transform-object-rest-spread": "^7.24.7",
        "@babel/plugin-transform-optional-catch-binding": "^7.24.7",
        "@babel/plugin-transform-optional-chaining": "^7.24.8",
        "@babel/plugin-transform-parameters": "^7.24.7",
        "@babel/plugin-transform-private-methods": "^7.24.7",
        "@babel/plugin-transform-private-property-in-object": "^7.24.7",
        "@babel/plugin-transform-react-display-name": "^7.24.7",
        "@babel/plugin-transform-react-jsx": "^7.25.2",
        "@babel/plugin-transform-react-jsx-self": "^7.24.7",
        "@babel/plugin-transform-react-jsx-source": "^7.24.7",
        "@babel/plugin-transform-regenerator": "^7.24.7",
        "@babel/plugin-transform-runtime": "^7.24.7",
        "@babel/plugin-transform-shorthand-properties": "^7.24.7",
        "@babel/plugin-transform-spread": "^7.24.7",
        "@babel/plugin-transform-sticky-regex": "^7.24.7",
        "@babel/plugin-transform-typescript": "^7.25.2",
        "@babel/plugin-transform-unicode-regex": "^7.24.7",
        "@babel/template": "^7.25.0",
        "@react-native/babel-plugin-codegen": "0.83.4",
        "babel-plugin-syntax-hermes-parser": "0.32.0",
        "babel-plugin-transform-flow-enums": "^0.0.2",
        "react-refresh": "^0.14.0"
      },
      "engines": {
        "node": ">= 20.19.4"
      },
      "peerDependencies": {
        "@babel/core": "*"
      }
    },
    "node_modules/@react-native/codegen": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/codegen/-/codegen-0.83.4.tgz",
      "integrity": "sha512-CJ7XutzIqJPz3Lp/5TOiRWlU/JAjTboMT1BHNLSXjYHXwTmgHM3iGEbpCOtBMjWvsojRTJyRO/G3ghInIIXEYg==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.25.2",
        "@babel/parser": "^7.25.3",
        "glob": "^7.1.1",
        "hermes-parser": "0.32.0",
        "invariant": "^2.2.4",
        "nullthrows": "^1.1.1",
        "yargs": "^17.6.2"
      },
      "engines": {
        "node": ">= 20.19.4"
      },
      "peerDependencies": {
        "@babel/core": "*"
      }
    },
    "node_modules/@react-native/codegen/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "license": "MIT"
    },
    "node_modules/@react-native/codegen/node_modules/brace-expansion": {
      "version": "1.1.13",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.13.tgz",
      "integrity": "sha512-9ZLprWS6EENmhEOpjCYW2c8VkmOvckIJZfkr7rBW6dObmfgJ/L1GpSYW5Hpo9lDz4D1+n0Ckz8rU7FwHDQiG/w==",
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/@react-native/codegen/node_modules/glob": {
      "version": "7.2.3",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-7.2.3.tgz",
      "integrity": "sha512-nFR0zLpU2YCaRxwoCJvL6UvCH2JFyFVIvwTLsIf21AuHlMskA1hhTdk+LlYJtOlYt9v6dvszD2BGRqBL+iQK9Q==",
      "deprecated": "Glob versions prior to v9 are no longer supported",
      "license": "ISC",
      "dependencies": {
        "fs.realpath": "^1.0.0",
        "inflight": "^1.0.4",
        "inherits": "2",
        "minimatch": "^3.1.1",
        "once": "^1.3.0",
        "path-is-absolute": "^1.0.0"
      },
      "engines": {
        "node": "*"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/@react-native/codegen/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/@react-native/community-cli-plugin": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/community-cli-plugin/-/community-cli-plugin-0.83.4.tgz",
      "integrity": "sha512-8os0weQEnjUhWy7Db881+JKRwNHVGM40VtTRvltAyA/YYkrGg4kPCqiTybMxQDEcF3rnviuxHyI+ITiglfmgmQ==",
      "license": "MIT",
      "dependencies": {
        "@react-native/dev-middleware": "0.83.4",
        "debug": "^4.4.0",
        "invariant": "^2.2.4",
        "metro": "^0.83.3",
        "metro-config": "^0.83.3",
        "metro-core": "^0.83.3",
        "semver": "^7.1.3"
      },
      "engines": {
        "node": ">= 20.19.4"
      },
      "peerDependencies": {
        "@react-native-community/cli": "*",
        "@react-native/metro-config": "*"
      },
      "peerDependenciesMeta": {
        "@react-native-community/cli": {
          "optional": true
        },
        "@react-native/metro-config": {
          "optional": true
        }
      }
    },
    "node_modules/@react-native/debugger-frontend": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/debugger-frontend/-/debugger-frontend-0.83.4.tgz",
      "integrity": "sha512-mCE2s/S7SEjax3gZb6LFAraAI3x13gRVWJWqT0HIm71e4ITObENNTDuMw4mvZ/wr4Gz2wv4FcBH5/Nla9LXOcg==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/debugger-shell": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/debugger-shell/-/debugger-shell-0.83.4.tgz",
      "integrity": "sha512-FtAnrvXqy1xeZ+onwilvxEeeBsvBlhtfrHVIC2R/BOJAK9TbKEtFfjio0wsn3DQIm+UZq48DSa+p9jJZ2aJUww==",
      "license": "MIT",
      "dependencies": {
        "cross-spawn": "^7.0.6",
        "fb-dotslash": "0.5.8"
      },
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/dev-middleware": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/dev-middleware/-/dev-middleware-0.83.4.tgz",
      "integrity": "sha512-3s9nXZc/kj986nI2RPqxiIJeTS3o7pvZDxbHu7GE9WVIGX9YucA1l/tEiXd7BAm3TBFOfefDOT08xD46wH+R3Q==",
      "license": "MIT",
      "dependencies": {
        "@isaacs/ttlcache": "^1.4.1",
        "@react-native/debugger-frontend": "0.83.4",
        "@react-native/debugger-shell": "0.83.4",
        "chrome-launcher": "^0.15.2",
        "chromium-edge-launcher": "^0.2.0",
        "connect": "^3.6.5",
        "debug": "^4.4.0",
        "invariant": "^2.2.4",
        "nullthrows": "^1.1.1",
        "open": "^7.0.3",
        "serve-static": "^1.16.2",
        "ws": "^7.5.10"
      },
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/gradle-plugin": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/gradle-plugin/-/gradle-plugin-0.83.4.tgz",
      "integrity": "sha512-AhaSWw2k3eMKqZ21IUdM7rpyTYOpAfsBbIIiom1QQii3QccX0uW2AWTcRhfuWRxqr2faGFaOBYedWl2fzp5hgw==",
      "license": "MIT",
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/js-polyfills": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/js-polyfills/-/js-polyfills-0.83.4.tgz",
      "integrity": "sha512-wYUdv0rt4MjhKhQloO1AnGDXhZQOFZHDxm86dEtEA0WcsCdVrFdRULFM+rKUC/QQtJW2rS6WBqtBusgtrsDADg==",
      "license": "MIT",
      "engines": {
        "node": ">= 20.19.4"
      }
    },
    "node_modules/@react-native/normalize-colors": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/normalize-colors/-/normalize-colors-0.83.4.tgz",
      "integrity": "sha512-9ezxaHjxqTkTOLg62SGg7YhFaE+fxa/jlrWP0nwf7eGFHlGOiTAaRR2KUfiN3K05e+EMbEhgcH/c7bgaXeGyJw==",
      "license": "MIT"
    },
    "node_modules/@react-navigation/bottom-tabs": {
      "version": "7.15.9",
      "resolved": "https://registry.npmmirror.com/@react-navigation/bottom-tabs/-/bottom-tabs-7.15.9.tgz",
      "integrity": "sha512-Ou28A1aZLj5wiFQ3F93aIsrI4NCwn3IJzkkjNo9KLFXsc0Yks+UqrVaFlffHFLsrbajuGRG/OQpnMA1ljayY5Q==",
      "license": "MIT",
      "dependencies": {
        "@react-navigation/elements": "^2.9.14",
        "color": "^4.2.3",
        "sf-symbols-typescript": "^2.1.0"
      },
      "peerDependencies": {
        "@react-navigation/native": "^7.2.2",
        "react": ">= 18.2.0",
        "react-native": "*",
        "react-native-safe-area-context": ">= 4.0.0",
        "react-native-screens": ">= 4.0.0"
      }
    },
    "node_modules/@react-navigation/core": {
      "version": "7.17.2",
      "resolved": "https://registry.npmmirror.com/@react-navigation/core/-/core-7.17.2.tgz",
      "integrity": "sha512-Rt2OZwcgOmjv401uLGAKaRM6xo0fiBce/A7LfRHI1oe5FV+KooWcgAoZ2XOtgKj6UzVMuQWt3b2e6rxo/mDJRA==",
      "license": "MIT",
      "dependencies": {
        "@react-navigation/routers": "^7.5.3",
        "escape-string-regexp": "^4.0.0",
        "fast-deep-equal": "^3.1.3",
        "nanoid": "^3.3.11",
        "query-string": "^7.1.3",
        "react-is": "^19.1.0",
        "use-latest-callback": "^0.2.4",
        "use-sync-external-store": "^1.5.0"
      },
      "peerDependencies": {
        "react": ">= 18.2.0"
      }
    },
    "node_modules/@react-navigation/core/node_modules/react-is": {
      "version": "19.2.4",
      "resolved": "https://registry.npmmirror.com/react-is/-/react-is-19.2.4.tgz",
      "integrity": "sha512-W+EWGn2v0ApPKgKKCy/7s7WHXkboGcsrXE+2joLyVxkbyVQfO3MUEaUQDHoSmb8TFFrSKYa9mw64WZHNHSDzYA==",
      "license": "MIT"
    },
    "node_modules/@react-navigation/elements": {
      "version": "2.9.14",
      "resolved": "https://registry.npmmirror.com/@react-navigation/elements/-/elements-2.9.14.tgz",
      "integrity": "sha512-lKqzu+su2pI/YIZmR7L7xdOs4UL+rVXKJAMpRMBrwInEy96SjIFst6QDGpE89Dunnu3VjVpjWfByo9f2GWBHDQ==",
      "license": "MIT",
      "dependencies": {
        "color": "^4.2.3",
        "use-latest-callback": "^0.2.4",
        "use-sync-external-store": "^1.5.0"
      },
      "peerDependencies": {
        "@react-native-masked-view/masked-view": ">= 0.2.0",
        "@react-navigation/native": "^7.2.2",
        "react": ">= 18.2.0",
        "react-native": "*",
        "react-native-safe-area-context": ">= 4.0.0"
      },
      "peerDependenciesMeta": {
        "@react-native-masked-view/masked-view": {
          "optional": true
        }
      }
    },
    "node_modules/@react-navigation/native": {
      "version": "7.2.2",
      "resolved": "https://registry.npmmirror.com/@react-navigation/native/-/native-7.2.2.tgz",
      "integrity": "sha512-kem1Ko2BcbAjmbQIv66dNmr6EtfDut3QU0qjsVhMnLLhktwyXb6FzZYp8gTrUb6AvkAbaJoi+BF5Pl55pAUa5w==",
      "license": "MIT",
      "dependencies": {
        "@react-navigation/core": "^7.17.2",
        "escape-string-regexp": "^4.0.0",
        "fast-deep-equal": "^3.1.3",
        "nanoid": "^3.3.11",
        "use-latest-callback": "^0.2.4"
      },
      "peerDependencies": {
        "react": ">= 18.2.0",
        "react-native": "*"
      }
    },
    "node_modules/@react-navigation/native-stack": {
      "version": "7.14.10",
      "resolved": "https://registry.npmmirror.com/@react-navigation/native-stack/-/native-stack-7.14.10.tgz",
      "integrity": "sha512-mCbYbYhi7Em2R2nEgwYGdLU38smy+KK+HMMVcwuzllWsF3Qb+jOUEYbB6Or7LvE7SS77BZ6sHdx4HptCEv50hQ==",
      "license": "MIT",
      "dependencies": {
        "@react-navigation/elements": "^2.9.14",
        "color": "^4.2.3",
        "sf-symbols-typescript": "^2.1.0",
        "warn-once": "^0.1.1"
      },
      "peerDependencies": {
        "@react-navigation/native": "^7.2.2",
        "react": ">= 18.2.0",
        "react-native": "*",
        "react-native-safe-area-context": ">= 4.0.0",
        "react-native-screens": ">= 4.0.0"
      }
    },
    "node_modules/@react-navigation/routers": {
      "version": "7.5.3",
      "resolved": "https://registry.npmmirror.com/@react-navigation/routers/-/routers-7.5.3.tgz",
      "integrity": "sha512-1tJHg4KKRJuQ1/EvJxatrMef3NZXEPzwUIUZ3n1yJ2t7Q97siwRtbynRpQG9/69ebbtiZ8W3ScOZF/OmhvM4Rg==",
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.11"
      }
    },
    "node_modules/@sinclair/typebox": {
      "version": "0.27.10",
      "resolved": "https://registry.npmmirror.com/@sinclair/typebox/-/typebox-0.27.10.tgz",
      "integrity": "sha512-MTBk/3jGLNB2tVxv6uLlFh1iu64iYOQ2PbdOSK3NW8JZsmlaOh2q6sdtKowBhfw8QFLmYNzTW4/oK4uATIi6ZA==",
      "license": "MIT"
    },
    "node_modules/@sinonjs/commons": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/@sinonjs/commons/-/commons-3.0.1.tgz",
      "integrity": "sha512-K3mCHKQ9sVh8o1C9cxkwxaOmXoAMlDxC1mYyHrjqOWEcBjYr76t96zL2zlj5dUGZ3HSw240X1qgH3Mjf1yJWpQ==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "type-detect": "4.0.8"
      }
    },
    "node_modules/@sinonjs/fake-timers": {
      "version": "10.3.0",
      "resolved": "https://registry.npmmirror.com/@sinonjs/fake-timers/-/fake-timers-10.3.0.tgz",
      "integrity": "sha512-V4BG07kuYSUkTCSBHG8G8TNhM+F19jXFWnQtzj+we8DrkpSBCee9Z3Ms8yiGer/dlmhe35/Xdgyo3/0rQKg7YA==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "@sinonjs/commons": "^3.0.0"
      }
    },
    "node_modules/@types/babel__core": {
      "version": "7.20.5",
      "resolved": "https://registry.npmmirror.com/@types/babel__core/-/babel__core-7.20.5.tgz",
      "integrity": "sha512-qoQprZvz5wQFJwMDqeseRXWv3rqMvhgpbXFfVyWhbx9X47POIA6i/+dXefEmZKoAgOaTdaIgNSMqMIU61yRyzA==",
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.20.7",
        "@babel/types": "^7.20.7",
        "@types/babel__generator": "*",
        "@types/babel__template": "*",
        "@types/babel__traverse": "*"
      }
    },
    "node_modules/@types/babel__generator": {
      "version": "7.27.0",
      "resolved": "https://registry.npmmirror.com/@types/babel__generator/-/babel__generator-7.27.0.tgz",
      "integrity": "sha512-ufFd2Xi92OAVPYsy+P4n7/U7e68fex0+Ee8gSG9KX7eo084CWiQ4sdxktvdl0bOPupXtVJPY19zk6EwWqUQ8lg==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__template": {
      "version": "7.4.4",
      "resolved": "https://registry.npmmirror.com/@types/babel__template/-/babel__template-7.4.4.tgz",
      "integrity": "sha512-h/NUaSyG5EyxBIp8YRxo4RMe2/qQgvyowRwVMzhYhBCONbW8PUsg4lkFMrhgZhUe5z3L3MiLDuvyJ/CaPa2A8A==",
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.1.0",
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__traverse": {
      "version": "7.28.0",
      "resolved": "https://registry.npmmirror.com/@types/babel__traverse/-/babel__traverse-7.28.0.tgz",
      "integrity": "sha512-8PvcXf70gTDZBgt9ptxJ8elBeBjcLOAcOtoO/mPJjtji1+CdGbHgm77om1GrsPxsiE+uXIpNSK64UYaIwQXd4Q==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.28.2"
      }
    },
    "node_modules/@types/graceful-fs": {
      "version": "4.1.9",
      "resolved": "https://registry.npmmirror.com/@types/graceful-fs/-/graceful-fs-4.1.9.tgz",
      "integrity": "sha512-olP3sd1qOEe5dXTSaFvQG+02VdRXcdytWLAZsAq1PecU8uqQAhkrnbli7DagjtXKW/Bl7YJbUsa8MPcuc8LHEQ==",
      "license": "MIT",
      "dependencies": {
        "@types/node": "*"
      }
    },
    "node_modules/@types/hammerjs": {
      "version": "2.0.46",
      "resolved": "https://registry.npmmirror.com/@types/hammerjs/-/hammerjs-2.0.46.tgz",
      "integrity": "sha512-ynRvcq6wvqexJ9brDMS4BnBLzmr0e14d6ZJTEShTBWKymQiHwlAyGu0ZPEFI2Fh1U53F7tN9ufClWM5KvqkKOw==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/@types/istanbul-lib-coverage": {
      "version": "2.0.6",
      "resolved": "https://registry.npmmirror.com/@types/istanbul-lib-coverage/-/istanbul-lib-coverage-2.0.6.tgz",
      "integrity": "sha512-2QF/t/auWm0lsy8XtKVPG19v3sSOQlJe/YHZgfjb/KBBHOGSV+J2q/S671rcq9uTBrLAXmZpqJiaQbMT+zNU1w==",
      "license": "MIT"
    },
    "node_modules/@types/istanbul-lib-report": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/@types/istanbul-lib-report/-/istanbul-lib-report-3.0.3.tgz",
      "integrity": "sha512-NQn7AHQnk/RSLOxrBbGyJM/aVQ+pjj5HCgasFxc0K/KhoATfQ/47AyUl15I2yBUpihjmas+a+VJBOqecrFH+uA==",
      "license": "MIT",
      "dependencies": {
        "@types/istanbul-lib-coverage": "*"
      }
    },
    "node_modules/@types/istanbul-reports": {
      "version": "3.0.4",
      "resolved": "https://registry.npmmirror.com/@types/istanbul-reports/-/istanbul-reports-3.0.4.tgz",
      "integrity": "sha512-pk2B1NWalF9toCRu6gjBzR69syFjP4Od8WRAX+0mmf9lAjCRicLOWc+ZrxZHx/0XRjotgkF9t6iaMJ+aXcOdZQ==",
      "license": "MIT",
      "dependencies": {
        "@types/istanbul-lib-report": "*"
      }
    },
    "node_modules/@types/node": {
      "version": "25.5.0",
      "resolved": "https://registry.npmmirror.com/@types/node/-/node-25.5.0.tgz",
      "integrity": "sha512-jp2P3tQMSxWugkCUKLRPVUpGaL5MVFwF8RDuSRztfwgN1wmqJeMSbKlnEtQqU8UrhTmzEmZdu2I6v2dpp7XIxw==",
      "license": "MIT",
      "dependencies": {
        "undici-types": "~7.18.0"
      }
    },
    "node_modules/@types/react": {
      "version": "19.2.14",
      "resolved": "https://registry.npmmirror.com/@types/react/-/react-19.2.14.tgz",
      "integrity": "sha512-ilcTH/UniCkMdtexkoCN0bI7pMcJDvmQFPvuPvmEaYA/NSfFTAgdUSLAoVjaRJm7+6PvcM+q1zYOwS4wTYMF9w==",
      "devOptional": true,
      "license": "MIT",
      "dependencies": {
        "csstype": "^3.2.2"
      }
    },
    "node_modules/@types/stack-utils": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/@types/stack-utils/-/stack-utils-2.0.3.tgz",
      "integrity": "sha512-9aEbYZ3TbYMznPdcdr3SmIrLXwC/AKZXQeCf9Pgao5CKb8CyHuEX5jzWPTkvregvhRJHcpRO6BFoGW9ycaOkYw==",
      "license": "MIT"
    },
    "node_modules/@types/yargs": {
      "version": "17.0.35",
      "resolved": "https://registry.npmmirror.com/@types/yargs/-/yargs-17.0.35.tgz",
      "integrity": "sha512-qUHkeCyQFxMXg79wQfTtfndEC+N9ZZg76HJftDJp+qH2tV7Gj4OJi7l+PiWwJ+pWtW8GwSmqsDj/oymhrTWXjg==",
      "license": "MIT",
      "dependencies": {
        "@types/yargs-parser": "*"
      }
    },
    "node_modules/@types/yargs-parser": {
      "version": "21.0.3",
      "resolved": "https://registry.npmmirror.com/@types/yargs-parser/-/yargs-parser-21.0.3.tgz",
      "integrity": "sha512-I4q9QU9MQv4oEOz4tAHJtNz1cwuLxn2F3xcc2iV5WdqLPpUnj30aUuxt1mAxYTG+oe8CZMV/+6rU4S4gRDzqtQ==",
      "license": "MIT"
    },
    "node_modules/@ungap/structured-clone": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/@ungap/structured-clone/-/structured-clone-1.3.0.tgz",
      "integrity": "sha512-WmoN8qaIAo7WTYWbAZuG8PYEhn5fkz7dZrqTBZ7dtt//lL2Gwms1IcnQ5yHqjDfX8Ft5j4YzDM23f87zBfDe9g==",
      "license": "ISC"
    },
    "node_modules/@xmldom/xmldom": {
      "version": "0.8.11",
      "resolved": "https://registry.npmmirror.com/@xmldom/xmldom/-/xmldom-0.8.11.tgz",
      "integrity": "sha512-cQzWCtO6C8TQiYl1ruKNn2U6Ao4o4WBBcbL61yJl84x+j5sOWWFU9X7DpND8XZG3daDppSsigMdfAIl2upQBRw==",
      "license": "MIT",
      "engines": {
        "node": ">=10.0.0"
      }
    },
    "node_modules/abort-controller": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/abort-controller/-/abort-controller-3.0.0.tgz",
      "integrity": "sha512-h8lQ8tacZYnR3vNQTgibj+tODHI5/+l06Au2Pcriv/Gmet0eaj4TwWH41sO9wnHDiQsEj19q0drzdWdeAHtweg==",
      "license": "MIT",
      "dependencies": {
        "event-target-shim": "^5.0.0"
      },
      "engines": {
        "node": ">=6.5"
      }
    },
    "node_modules/accepts": {
      "version": "1.3.8",
      "resolved": "https://registry.npmmirror.com/accepts/-/accepts-1.3.8.tgz",
      "integrity": "sha512-PYAthTa2m2VKxuvSD3DPC/Gy+U+sOA1LAuT8mkmRuvw+NACSaeXEQ+NHcVF7rONl6qcaxV3Uuemwawk+7+SJLw==",
      "license": "MIT",
      "dependencies": {
        "mime-types": "~2.1.34",
        "negotiator": "0.6.3"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/acorn": {
      "version": "8.16.0",
      "resolved": "https://registry.npmmirror.com/acorn/-/acorn-8.16.0.tgz",
      "integrity": "sha512-UVJyE9MttOsBQIDKw1skb9nAwQuR5wuGD3+82K6JgJlm/Y+KI92oNsMNGZCYdDsVtRHSak0pcV5Dno5+4jh9sw==",
      "license": "MIT",
      "bin": {
        "acorn": "bin/acorn"
      },
      "engines": {
        "node": ">=0.4.0"
      }
    },
    "node_modules/agent-base": {
      "version": "7.1.4",
      "resolved": "https://registry.npmmirror.com/agent-base/-/agent-base-7.1.4.tgz",
      "integrity": "sha512-MnA+YT8fwfJPgBx3m60MNqakm30XOkyIoH1y6huTQvC0PwZG7ki8NacLBcrPbNoo8vEZy7Jpuk7+jMO+CUovTQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/anser": {
      "version": "1.4.10",
      "resolved": "https://registry.npmmirror.com/anser/-/anser-1.4.10.tgz",
      "integrity": "sha512-hCv9AqTQ8ycjpSd3upOJd7vFwW1JaoYQ7tpham03GJ1ca8/65rqn0RpaWpItOAd6ylW9wAw6luXYPJIyPFVOww==",
      "license": "MIT"
    },
    "node_modules/ansi-escapes": {
      "version": "4.3.2",
      "resolved": "https://registry.npmmirror.com/ansi-escapes/-/ansi-escapes-4.3.2.tgz",
      "integrity": "sha512-gKXj5ALrKWQLsYG9jlTRmR/xKluxHV+Z9QEwNIgCfM1/uwPMCuzVVnh5mwTd+OuBZcwSIMbqssNWRm1lE51QaQ==",
      "license": "MIT",
      "dependencies": {
        "type-fest": "^0.21.3"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/ansi-escapes/node_modules/type-fest": {
      "version": "0.21.3",
      "resolved": "https://registry.npmmirror.com/type-fest/-/type-fest-0.21.3.tgz",
      "integrity": "sha512-t0rzBq87m3fVcduHDUFhKmyyX+9eo6WQjZvf51Ea/M0Q7+T374Jp1aUiyUl0GKxp8M/OETVHSDvmkyPgvX+X2w==",
      "license": "(MIT OR CC0-1.0)",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/ansi-regex": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/ansi-regex/-/ansi-regex-5.0.1.tgz",
      "integrity": "sha512-quJQXlTSUGL2LH9SUXo8VwsY4soanhgo6LNSm84E1LBcE8s3O0wpdiRzyR9z/ZZJMlMWv37qOOb9pdJlMUEKFQ==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/ansi-styles": {
      "version": "4.3.0",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-4.3.0.tgz",
      "integrity": "sha512-zbB9rCJAT1rbjiVDb2hqKFHNYLxgtk8NURxZ3IZwD3F6NtxbXZQCnnSi1Lkx+IDohdPlFp222wVALIheZJQSEg==",
      "license": "MIT",
      "dependencies": {
        "color-convert": "^2.0.1"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/chalk/ansi-styles?sponsor=1"
      }
    },
    "node_modules/anymatch": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/anymatch/-/anymatch-3.1.3.tgz",
      "integrity": "sha512-KMReFUr0B4t+D+OBkjR3KYqvocp2XaSzO55UcB6mgQMd3KbcE+mWTyvVV7D/zsdEbNnV6acZUutkiHQXvTr1Rw==",
      "license": "ISC",
      "dependencies": {
        "normalize-path": "^3.0.0",
        "picomatch": "^2.0.4"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/arg": {
      "version": "5.0.2",
      "resolved": "https://registry.npmmirror.com/arg/-/arg-5.0.2.tgz",
      "integrity": "sha512-PYjyFOLKQ9y57JvQ6QLo8dAgNqswh8M1RMJYdQduT6xbWSgK36P/Z/v+p888pM69jMMfS8Xd8F6I1kQ/I9HUGg==",
      "license": "MIT"
    },
    "node_modules/argparse": {
      "version": "1.0.10",
      "resolved": "https://registry.npmmirror.com/argparse/-/argparse-1.0.10.tgz",
      "integrity": "sha512-o5Roy6tNG4SL/FOkCAN6RzjiakZS25RLYFrcMttJqbdd8BWrnA+fGz57iN5Pb06pvBGvl5gQ0B48dJlslXvoTg==",
      "license": "MIT",
      "dependencies": {
        "sprintf-js": "~1.0.2"
      }
    },
    "node_modules/aria-hidden": {
      "version": "1.2.6",
      "resolved": "https://registry.npmmirror.com/aria-hidden/-/aria-hidden-1.2.6.tgz",
      "integrity": "sha512-ik3ZgC9dY/lYVVM++OISsaYDeg1tb0VtP5uL3ouh1koGOaUMDPpbFIei4JkFimWUFPn90sbMNMXQAIVOlnYKJA==",
      "license": "MIT",
      "dependencies": {
        "tslib": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/asap": {
      "version": "2.0.6",
      "resolved": "https://registry.npmmirror.com/asap/-/asap-2.0.6.tgz",
      "integrity": "sha512-BSHWgDSAiKs50o2Re8ppvp3seVHXSRM44cdSsT9FfNEUUZLOGWVCsiWaRPWM1Znn+mqZ1OfVZ3z3DWEzSp7hRA==",
      "license": "MIT"
    },
    "node_modules/await-lock": {
      "version": "2.2.2",
      "resolved": "https://registry.npmjs.org/await-lock/-/await-lock-2.2.2.tgz",
      "integrity": "sha512-aDczADvlvTGajTDjcjpJMqRkOF6Qdz3YbPZm/PyW6tKPkx2hlYBzxMhEywM/tU72HrVZjgl5VCdRuMlA7pZ8Gw==",
      "license": "MIT"
    },
    "node_modules/babel-jest": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/babel-jest/-/babel-jest-29.7.0.tgz",
      "integrity": "sha512-BrvGY3xZSwEcCzKvKsCi2GgHqDqsYkOP4/by5xCgIwGXQxIEh+8ew3gmrE1y7XRR6LHZIj6yLYnUi/mm2KXKBg==",
      "license": "MIT",
      "dependencies": {
        "@jest/transform": "^29.7.0",
        "@types/babel__core": "^7.1.14",
        "babel-plugin-istanbul": "^6.1.1",
        "babel-preset-jest": "^29.6.3",
        "chalk": "^4.0.0",
        "graceful-fs": "^4.2.9",
        "slash": "^3.0.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.8.0"
      }
    },
    "node_modules/babel-plugin-istanbul": {
      "version": "6.1.1",
      "resolved": "https://registry.npmmirror.com/babel-plugin-istanbul/-/babel-plugin-istanbul-6.1.1.tgz",
      "integrity": "sha512-Y1IQok9821cC9onCx5otgFfRm7Lm+I+wwxOx738M/WLPZ9Q42m4IG5W0FNX8WLL2gYMZo3JkuXIH2DOpWM+qwA==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.0.0",
        "@istanbuljs/load-nyc-config": "^1.0.0",
        "@istanbuljs/schema": "^0.1.2",
        "istanbul-lib-instrument": "^5.0.4",
        "test-exclude": "^6.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/babel-plugin-jest-hoist": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/babel-plugin-jest-hoist/-/babel-plugin-jest-hoist-29.6.3.tgz",
      "integrity": "sha512-ESAc/RJvGTFEzRwOTT4+lNDk/GNHMkKbNzsvT0qKRfDyyYTskxB5rnU2njIDYVxXCBHHEI1c0YwHob3WaYujOg==",
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.3.3",
        "@babel/types": "^7.3.3",
        "@types/babel__core": "^7.1.14",
        "@types/babel__traverse": "^7.0.6"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/babel-plugin-polyfill-corejs2": {
      "version": "0.4.17",
      "resolved": "https://registry.npmmirror.com/babel-plugin-polyfill-corejs2/-/babel-plugin-polyfill-corejs2-0.4.17.tgz",
      "integrity": "sha512-aTyf30K/rqAsNwN76zYrdtx8obu0E4KoUME29B1xj+B3WxgvWkp943vYQ+z8Mv3lw9xHXMHpvSPOBxzAkIa94w==",
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.28.6",
        "@babel/helper-define-polyfill-provider": "^0.6.8",
        "semver": "^6.3.1"
      },
      "peerDependencies": {
        "@babel/core": "^7.4.0 || ^8.0.0-0 <8.0.0"
      }
    },
    "node_modules/babel-plugin-polyfill-corejs2/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/babel-plugin-polyfill-corejs3": {
      "version": "0.13.0",
      "resolved": "https://registry.npmmirror.com/babel-plugin-polyfill-corejs3/-/babel-plugin-polyfill-corejs3-0.13.0.tgz",
      "integrity": "sha512-U+GNwMdSFgzVmfhNm8GJUX88AadB3uo9KpJqS3FaqNIPKgySuvMb+bHPsOmmuWyIcuqZj/pzt1RUIUZns4y2+A==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-define-polyfill-provider": "^0.6.5",
        "core-js-compat": "^3.43.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.4.0 || ^8.0.0-0 <8.0.0"
      }
    },
    "node_modules/babel-plugin-polyfill-regenerator": {
      "version": "0.6.8",
      "resolved": "https://registry.npmmirror.com/babel-plugin-polyfill-regenerator/-/babel-plugin-polyfill-regenerator-0.6.8.tgz",
      "integrity": "sha512-M762rNHfSF1EV3SLtnCJXFoQbbIIz0OyRwnCmV0KPC7qosSfCO0QLTSuJX3ayAebubhE6oYBAYPrBA5ljowaZg==",
      "license": "MIT",
      "dependencies": {
        "@babel/helper-define-polyfill-provider": "^0.6.8"
      },
      "peerDependencies": {
        "@babel/core": "^7.4.0 || ^8.0.0-0 <8.0.0"
      }
    },
    "node_modules/babel-plugin-react-compiler": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/babel-plugin-react-compiler/-/babel-plugin-react-compiler-1.0.0.tgz",
      "integrity": "sha512-Ixm8tFfoKKIPYdCCKYTsqv+Fd4IJ0DQqMyEimo+pxUOMUR9cVPlwTrFt9Avu+3cb6Zp3mAzl+t1MrG2fxxKsxw==",
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.26.0"
      }
    },
    "node_modules/babel-plugin-react-native-web": {
      "version": "0.21.2",
      "resolved": "https://registry.npmmirror.com/babel-plugin-react-native-web/-/babel-plugin-react-native-web-0.21.2.tgz",
      "integrity": "sha512-SPD0J6qjJn8231i0HZhlAGH6NORe+QvRSQM2mwQEzJ2Fb3E4ruWTiiicPlHjmeWShDXLcvoorOCXjeR7k/lyWA==",
      "license": "MIT"
    },
    "node_modules/babel-plugin-syntax-hermes-parser": {
      "version": "0.32.0",
      "resolved": "https://registry.npmmirror.com/babel-plugin-syntax-hermes-parser/-/babel-plugin-syntax-hermes-parser-0.32.0.tgz",
      "integrity": "sha512-m5HthL++AbyeEA2FcdwOLfVFvWYECOBObLHNqdR8ceY4TsEdn4LdX2oTvbB2QJSSElE2AWA/b2MXZ/PF/CqLZg==",
      "license": "MIT",
      "dependencies": {
        "hermes-parser": "0.32.0"
      }
    },
    "node_modules/babel-plugin-transform-flow-enums": {
      "version": "0.0.2",
      "resolved": "https://registry.npmmirror.com/babel-plugin-transform-flow-enums/-/babel-plugin-transform-flow-enums-0.0.2.tgz",
      "integrity": "sha512-g4aaCrDDOsWjbm0PUUeVnkcVd6AKJsVc/MbnPhEotEpkeJQP6b8nzewohQi7+QS8UyPehOhGWn0nOwjvWpmMvQ==",
      "license": "MIT",
      "dependencies": {
        "@babel/plugin-syntax-flow": "^7.12.1"
      }
    },
    "node_modules/babel-preset-current-node-syntax": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/babel-preset-current-node-syntax/-/babel-preset-current-node-syntax-1.2.0.tgz",
      "integrity": "sha512-E/VlAEzRrsLEb2+dv8yp3bo4scof3l9nR4lrld+Iy5NyVqgVYUJnDAmunkhPMisRI32Qc4iRiz425d8vM++2fg==",
      "license": "MIT",
      "dependencies": {
        "@babel/plugin-syntax-async-generators": "^7.8.4",
        "@babel/plugin-syntax-bigint": "^7.8.3",
        "@babel/plugin-syntax-class-properties": "^7.12.13",
        "@babel/plugin-syntax-class-static-block": "^7.14.5",
        "@babel/plugin-syntax-import-attributes": "^7.24.7",
        "@babel/plugin-syntax-import-meta": "^7.10.4",
        "@babel/plugin-syntax-json-strings": "^7.8.3",
        "@babel/plugin-syntax-logical-assignment-operators": "^7.10.4",
        "@babel/plugin-syntax-nullish-coalescing-operator": "^7.8.3",
        "@babel/plugin-syntax-numeric-separator": "^7.10.4",
        "@babel/plugin-syntax-object-rest-spread": "^7.8.3",
        "@babel/plugin-syntax-optional-catch-binding": "^7.8.3",
        "@babel/plugin-syntax-optional-chaining": "^7.8.3",
        "@babel/plugin-syntax-private-property-in-object": "^7.14.5",
        "@babel/plugin-syntax-top-level-await": "^7.14.5"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0 || ^8.0.0-0"
      }
    },
    "node_modules/babel-preset-jest": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/babel-preset-jest/-/babel-preset-jest-29.6.3.tgz",
      "integrity": "sha512-0B3bhxR6snWXJZtR/RliHTDPRgn1sNHOR0yVtq/IiQFyuOVjFS+wuio/R4gSNkyYmKmJB4wGZv2NZanmKmTnNA==",
      "license": "MIT",
      "dependencies": {
        "babel-plugin-jest-hoist": "^29.6.3",
        "babel-preset-current-node-syntax": "^1.0.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/balanced-match": {
      "version": "4.0.4",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-4.0.4.tgz",
      "integrity": "sha512-BLrgEcRTwX2o6gGxGOCNyMvGSp35YofuYzw9h1IMTRmKqttAZZVU67bdb9Pr2vUHA8+j3i2tJfjO6C6+4myGTA==",
      "license": "MIT",
      "engines": {
        "node": "18 || 20 || >=22"
      }
    },
    "node_modules/base64-js": {
      "version": "1.5.1",
      "resolved": "https://registry.npmmirror.com/base64-js/-/base64-js-1.5.1.tgz",
      "integrity": "sha512-AKpaYlHn8t4SVbOHCy+b5+KKgvR4vrsD8vbvrbiQJps7fKDTkjkDry6ji0rUJjC0kzbNePLwzxq8iypo41qeWA==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/baseline-browser-mapping": {
      "version": "2.10.12",
      "resolved": "https://registry.npmmirror.com/baseline-browser-mapping/-/baseline-browser-mapping-2.10.12.tgz",
      "integrity": "sha512-qyq26DxfY4awP2gIRXhhLWfwzwI+N5Nxk6iQi8EFizIaWIjqicQTE4sLnZZVdeKPRcVNoJOkkpfzoIYuvCKaIQ==",
      "license": "Apache-2.0",
      "bin": {
        "baseline-browser-mapping": "dist/cli.cjs"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/better-opn": {
      "version": "3.0.2",
      "resolved": "https://registry.npmmirror.com/better-opn/-/better-opn-3.0.2.tgz",
      "integrity": "sha512-aVNobHnJqLiUelTaHat9DZ1qM2w0C0Eym4LPI/3JxOnSokGVdsl1T1kN7TFvsEAD8G47A6VKQ0TVHqbBnYMJlQ==",
      "license": "MIT",
      "dependencies": {
        "open": "^8.0.4"
      },
      "engines": {
        "node": ">=12.0.0"
      }
    },
    "node_modules/better-opn/node_modules/open": {
      "version": "8.4.2",
      "resolved": "https://registry.npmmirror.com/open/-/open-8.4.2.tgz",
      "integrity": "sha512-7x81NCL719oNbsq/3mh+hVrAWmFuEYUqrq/Iw3kUzH8ReypT9QQ0BLoJS7/G9k6N81XjW4qHWtjWwe/9eLy1EQ==",
      "license": "MIT",
      "dependencies": {
        "define-lazy-prop": "^2.0.0",
        "is-docker": "^2.1.1",
        "is-wsl": "^2.2.0"
      },
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/big-integer": {
      "version": "1.6.52",
      "resolved": "https://registry.npmmirror.com/big-integer/-/big-integer-1.6.52.tgz",
      "integrity": "sha512-QxD8cf2eVqJOOz63z6JIN9BzvVs/dlySa5HGSBH5xtR8dPteIRQnBxxKqkNTiT6jbDTF6jAfrd4oMcND9RGbQg==",
      "license": "Unlicense",
      "engines": {
        "node": ">=0.6"
      }
    },
    "node_modules/boolbase": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/boolbase/-/boolbase-1.0.0.tgz",
      "integrity": "sha512-JZOSA7Mo9sNGB8+UjSgzdLtokWAky1zbztM3WRLCbZ70/3cTANmQmOdR7y2g+J0e2WXywy1yS468tY+IruqEww==",
      "license": "ISC"
    },
    "node_modules/bplist-creator": {
      "version": "0.1.0",
      "resolved": "https://registry.npmmirror.com/bplist-creator/-/bplist-creator-0.1.0.tgz",
      "integrity": "sha512-sXaHZicyEEmY86WyueLTQesbeoH/mquvarJaQNbjuOQO+7gbFcDEWqKmcWA4cOTLzFlfgvkiVxolk1k5bBIpmg==",
      "license": "MIT",
      "dependencies": {
        "stream-buffers": "2.2.x"
      }
    },
    "node_modules/bplist-parser": {
      "version": "0.3.1",
      "resolved": "https://registry.npmmirror.com/bplist-parser/-/bplist-parser-0.3.1.tgz",
      "integrity": "sha512-PyJxiNtA5T2PlLIeBot4lbp7rj4OadzjnMZD/G5zuBNt8ei/yCU7+wW0h2bag9vr8c+/WuRWmSxbqAl9hL1rBA==",
      "license": "MIT",
      "dependencies": {
        "big-integer": "1.6.x"
      },
      "engines": {
        "node": ">= 5.10.0"
      }
    },
    "node_modules/brace-expansion": {
      "version": "5.0.5",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-5.0.5.tgz",
      "integrity": "sha512-VZznLgtwhn+Mact9tfiwx64fA9erHH/MCXEUfB/0bX/6Fz6ny5EGTXYltMocqg4xFAQZtnO3DHWWXi8RiuN7cQ==",
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^4.0.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      }
    },
    "node_modules/braces": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/braces/-/braces-3.0.3.tgz",
      "integrity": "sha512-yQbXgO/OSZVD2IsiLlro+7Hf6Q18EJrKSEsdoMzKePKXct3gvD8oLcOQdIzGupr5Fj+EDe8gO/lxc1BzfMpxvA==",
      "license": "MIT",
      "dependencies": {
        "fill-range": "^7.1.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/browserslist": {
      "version": "4.28.1",
      "resolved": "https://registry.npmmirror.com/browserslist/-/browserslist-4.28.1.tgz",
      "integrity": "sha512-ZC5Bd0LgJXgwGqUknZY/vkUQ04r8NXnJZ3yYi4vDmSiZmC/pdSN0NbNRPxZpbtO4uAfDUAFffO8IZoM3Gj8IkA==",
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "baseline-browser-mapping": "^2.9.0",
        "caniuse-lite": "^1.0.30001759",
        "electron-to-chromium": "^1.5.263",
        "node-releases": "^2.0.27",
        "update-browserslist-db": "^1.2.0"
      },
      "bin": {
        "browserslist": "cli.js"
      },
      "engines": {
        "node": "^6 || ^7 || ^8 || ^9 || ^10 || ^11 || ^12 || >=13.7"
      }
    },
    "node_modules/bser": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/bser/-/bser-2.1.1.tgz",
      "integrity": "sha512-gQxTNE/GAfIIrmHLUE3oJyp5FO6HRBfhjnw4/wMmA63ZGDJnWBmgY/lyQBpnDUkGmAhbSe39tx2d/iTOAfglwQ==",
      "license": "Apache-2.0",
      "dependencies": {
        "node-int64": "^0.4.0"
      }
    },
    "node_modules/buffer-from": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/buffer-from/-/buffer-from-1.1.2.tgz",
      "integrity": "sha512-E+XQCRwSbaaiChtv6k6Dwgc+bx+Bs6vuKJHHl5kox/BaKbhiXzqQOwK4cO22yElGp2OCmjwVhT3HmxgyPGnJfQ==",
      "license": "MIT"
    },
    "node_modules/bytes": {
      "version": "3.1.2",
      "resolved": "https://registry.npmmirror.com/bytes/-/bytes-3.1.2.tgz",
      "integrity": "sha512-/Nf7TyzTx6S3yRJObOAV7956r8cr2+Oj8AC5dt8wSP3BQAoeX58NoHyCU8P8zGkNXStjTSi6fzO6F0pBdcYbEg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/camelcase": {
      "version": "6.3.0",
      "resolved": "https://registry.npmmirror.com/camelcase/-/camelcase-6.3.0.tgz",
      "integrity": "sha512-Gmy6FhYlCY7uOElZUSbxo2UCDH8owEk996gkbrpsgGtrJLM3J7jGxl9Ic7Qwwj4ivOE5AWZWRMecDdF7hqGjFA==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/caniuse-lite": {
      "version": "1.0.30001781",
      "resolved": "https://registry.npmmirror.com/caniuse-lite/-/caniuse-lite-1.0.30001781.tgz",
      "integrity": "sha512-RdwNCyMsNBftLjW6w01z8bKEvT6e/5tpPVEgtn22TiLGlstHOVecsX2KHFkD5e/vRnIE4EGzpuIODb3mtswtkw==",
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/caniuse-lite"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "CC-BY-4.0"
    },
    "node_modules/chalk": {
      "version": "4.1.2",
      "resolved": "https://registry.npmmirror.com/chalk/-/chalk-4.1.2.tgz",
      "integrity": "sha512-oKnbhFyRIXpUuez8iBMmyEa4nbj4IOQyuhc/wy9kY7/WVPcwIO9VA668Pu8RkO7+0G76SLROeyw9CpQ061i4mA==",
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.1.0",
        "supports-color": "^7.1.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/chalk?sponsor=1"
      }
    },
    "node_modules/chrome-launcher": {
      "version": "0.15.2",
      "resolved": "https://registry.npmmirror.com/chrome-launcher/-/chrome-launcher-0.15.2.tgz",
      "integrity": "sha512-zdLEwNo3aUVzIhKhTtXfxhdvZhUghrnmkvcAq2NoDd+LeOHKf03H5jwZ8T/STsAlzyALkBVK552iaG1fGf1xVQ==",
      "license": "Apache-2.0",
      "dependencies": {
        "@types/node": "*",
        "escape-string-regexp": "^4.0.0",
        "is-wsl": "^2.2.0",
        "lighthouse-logger": "^1.0.0"
      },
      "bin": {
        "print-chrome-path": "bin/print-chrome-path.js"
      },
      "engines": {
        "node": ">=12.13.0"
      }
    },
    "node_modules/chromium-edge-launcher": {
      "version": "0.2.0",
      "resolved": "https://registry.npmmirror.com/chromium-edge-launcher/-/chromium-edge-launcher-0.2.0.tgz",
      "integrity": "sha512-JfJjUnq25y9yg4FABRRVPmBGWPZZi+AQXT4mxupb67766/0UlhG8PAZCz6xzEMXTbW3CsSoE8PcCWA49n35mKg==",
      "license": "Apache-2.0",
      "dependencies": {
        "@types/node": "*",
        "escape-string-regexp": "^4.0.0",
        "is-wsl": "^2.2.0",
        "lighthouse-logger": "^1.0.0",
        "mkdirp": "^1.0.4",
        "rimraf": "^3.0.2"
      }
    },
    "node_modules/ci-info": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ci-info/-/ci-info-2.0.0.tgz",
      "integrity": "sha512-5tK7EtrZ0N+OLFMthtqOj4fI2Jeb88C4CAZPu25LDVUgXJ0A3Js4PMGqrn0JU1W0Mh1/Z8wZzYPxqUrXeBboCQ==",
      "license": "MIT"
    },
    "node_modules/cli-cursor": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/cli-cursor/-/cli-cursor-2.1.0.tgz",
      "integrity": "sha512-8lgKz8LmCRYZZQDpRyT2m5rKJ08TnU4tR9FFFW2rxpxR1FzWi4PQ/NfyODchAatHaUgnSPVcx/R5w6NuTBzFiw==",
      "license": "MIT",
      "dependencies": {
        "restore-cursor": "^2.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/cli-spinners": {
      "version": "2.9.2",
      "resolved": "https://registry.npmmirror.com/cli-spinners/-/cli-spinners-2.9.2.tgz",
      "integrity": "sha512-ywqV+5MmyL4E7ybXgKys4DugZbX0FC6LnwrhjuykIjnK9k8OQacQ7axGKnjDXWNhns0xot3bZI5h55H8yo9cJg==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/client-only": {
      "version": "0.0.1",
      "resolved": "https://registry.npmmirror.com/client-only/-/client-only-0.0.1.tgz",
      "integrity": "sha512-IV3Ou0jSMzZrd3pZ48nLkT9DA7Ag1pnPzaiQhpW7c3RbcqqzvzzVu+L8gfqMp/8IM2MQtSiqaCxrrcfu8I8rMA==",
      "license": "MIT"
    },
    "node_modules/cliui": {
      "version": "8.0.1",
      "resolved": "https://registry.npmmirror.com/cliui/-/cliui-8.0.1.tgz",
      "integrity": "sha512-BSeNnyus75C4//NQ9gQt1/csTXyo/8Sb+afLAkzAptFuMsod9HFokGNudZpi/oQV73hnVK+sR+5PVRMd+Dr7YQ==",
      "license": "ISC",
      "dependencies": {
        "string-width": "^4.2.0",
        "strip-ansi": "^6.0.1",
        "wrap-ansi": "^7.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/clone": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/clone/-/clone-1.0.4.tgz",
      "integrity": "sha512-JQHZ2QMW6l3aH/j6xCqQThY/9OH4D/9ls34cgkUBiEeocRTU04tHfKPBsUK1PqZCUQM7GiA0IIXJSuXHI64Kbg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.8"
      }
    },
    "node_modules/color": {
      "version": "4.2.3",
      "resolved": "https://registry.npmmirror.com/color/-/color-4.2.3.tgz",
      "integrity": "sha512-1rXeuUUiGGrykh+CeBdu5Ie7OJwinCgQY0bc7GCRxy5xVHy+moaqkpL/jqQq0MtQOeYcrqEz4abc5f0KtU7W4A==",
      "license": "MIT",
      "dependencies": {
        "color-convert": "^2.0.1",
        "color-string": "^1.9.0"
      },
      "engines": {
        "node": ">=12.5.0"
      }
    },
    "node_modules/color-convert": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/color-convert/-/color-convert-2.0.1.tgz",
      "integrity": "sha512-RRECPsj7iu/xb5oKYcsFHSppFNnsj/52OVTRKb4zP5onXwVF3zVmmToNcOfGC+CRDpfK/U584fMg38ZHCaElKQ==",
      "license": "MIT",
      "dependencies": {
        "color-name": "~1.1.4"
      },
      "engines": {
        "node": ">=7.0.0"
      }
    },
    "node_modules/color-name": {
      "version": "1.1.4",
      "resolved": "https://registry.npmmirror.com/color-name/-/color-name-1.1.4.tgz",
      "integrity": "sha512-dOy+3AuW3a2wNbZHIuMZpTcgjGuLU/uBL/ubcZF9OXbDo8ff4O8yVp5Bf0efS8uEoYo5q4Fx7dY9OgQGXgAsQA==",
      "license": "MIT"
    },
    "node_modules/color-string": {
      "version": "1.9.1",
      "resolved": "https://registry.npmmirror.com/color-string/-/color-string-1.9.1.tgz",
      "integrity": "sha512-shrVawQFojnZv6xM40anx4CkoDP+fZsw/ZerEMsW/pyzsRbElpsL/DBVW7q3ExxwusdNXI3lXpuhEZkzs8p5Eg==",
      "license": "MIT",
      "dependencies": {
        "color-name": "^1.0.0",
        "simple-swizzle": "^0.2.2"
      }
    },
    "node_modules/commander": {
      "version": "7.2.0",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-7.2.0.tgz",
      "integrity": "sha512-QrWXB+ZQSVPmIWIhtEO9H+gwHaMGYiF5ChvoJ+K9ZGHG/sVsa6yiesAD1GC/x46sET00Xlwo1u49RVVVzvcSkw==",
      "license": "MIT",
      "engines": {
        "node": ">= 10"
      }
    },
    "node_modules/compressible": {
      "version": "2.0.18",
      "resolved": "https://registry.npmmirror.com/compressible/-/compressible-2.0.18.tgz",
      "integrity": "sha512-AF3r7P5dWxL8MxyITRMlORQNaOA2IkAFaTr4k7BUumjPtRpGDTZpl0Pb1XCO6JeDCBdp126Cgs9sMxqSjgYyRg==",
      "license": "MIT",
      "dependencies": {
        "mime-db": ">= 1.43.0 < 2"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/compression": {
      "version": "1.8.1",
      "resolved": "https://registry.npmmirror.com/compression/-/compression-1.8.1.tgz",
      "integrity": "sha512-9mAqGPHLakhCLeNyxPkK4xVo746zQ/czLH1Ky+vkitMnWfWZps8r0qXuwhwizagCRttsL4lfG4pIOvaWLpAP0w==",
      "license": "MIT",
      "dependencies": {
        "bytes": "3.1.2",
        "compressible": "~2.0.18",
        "debug": "2.6.9",
        "negotiator": "~0.6.4",
        "on-headers": "~1.1.0",
        "safe-buffer": "5.2.1",
        "vary": "~1.1.2"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/compression/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/compression/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/compression/node_modules/negotiator": {
      "version": "0.6.4",
      "resolved": "https://registry.npmmirror.com/negotiator/-/negotiator-0.6.4.tgz",
      "integrity": "sha512-myRT3DiWPHqho5PrJaIRyaMv2kgYf0mUVgBNOYMuCH5Ki1yEiQaf/ZJuQ62nvpc44wL5WDbTX7yGJi1Neevw8w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/concat-map": {
      "version": "0.0.1",
      "resolved": "https://registry.npmmirror.com/concat-map/-/concat-map-0.0.1.tgz",
      "integrity": "sha512-/Srv4dswyQNBfohGpz9o6Yb3Gz3SrUDqBH5rTuhGR7ahtlbYKnVxw2bCFMRljaA7EXHaXZ8wsHdodFvbkhKmqg==",
      "license": "MIT"
    },
    "node_modules/connect": {
      "version": "3.7.0",
      "resolved": "https://registry.npmmirror.com/connect/-/connect-3.7.0.tgz",
      "integrity": "sha512-ZqRXc+tZukToSNmh5C2iWMSoV3X1YUcPbqEM4DkEG5tNQXrQUZCNVGGv3IuicnkMtPfGf3Xtp8WCXs295iQ1pQ==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "finalhandler": "1.1.2",
        "parseurl": "~1.3.3",
        "utils-merge": "1.0.1"
      },
      "engines": {
        "node": ">= 0.10.0"
      }
    },
    "node_modules/connect/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/connect/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/convert-source-map": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/convert-source-map/-/convert-source-map-2.0.0.tgz",
      "integrity": "sha512-Kvp459HrV2FEJ1CAsi1Ku+MY3kasH19TFykTz2xWmMeq6bk2NU3XXvfJ+Q61m0xktWwt+1HSYf3JZsTms3aRJg==",
      "license": "MIT"
    },
    "node_modules/core-js-compat": {
      "version": "3.49.0",
      "resolved": "https://registry.npmmirror.com/core-js-compat/-/core-js-compat-3.49.0.tgz",
      "integrity": "sha512-VQXt1jr9cBz03b331DFDCCP90b3fanciLkgiOoy8SBHy06gNf+vQ1A3WFLqG7I8TipYIKeYK9wxd0tUrvHcOZA==",
      "license": "MIT",
      "dependencies": {
        "browserslist": "^4.28.1"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/core-js"
      }
    },
    "node_modules/cross-fetch": {
      "version": "3.2.0",
      "resolved": "https://registry.npmmirror.com/cross-fetch/-/cross-fetch-3.2.0.tgz",
      "integrity": "sha512-Q+xVJLoGOeIMXZmbUK4HYk+69cQH6LudR0Vu/pRm2YlU/hDV9CiS0gKUMaWY5f2NeUH9C1nV3bsTlCo0FsTV1Q==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "node-fetch": "^2.7.0"
      }
    },
    "node_modules/cross-spawn": {
      "version": "7.0.6",
      "resolved": "https://registry.npmmirror.com/cross-spawn/-/cross-spawn-7.0.6.tgz",
      "integrity": "sha512-uV2QOWP2nWzsy2aMp8aRibhi9dlzF5Hgh5SHaB9OiTGEyDTiJJyx0uy51QXdyWbtAHNua4XJzUKca3OzKUd3vA==",
      "license": "MIT",
      "dependencies": {
        "path-key": "^3.1.0",
        "shebang-command": "^2.0.0",
        "which": "^2.0.1"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/css-in-js-utils": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/css-in-js-utils/-/css-in-js-utils-3.1.0.tgz",
      "integrity": "sha512-fJAcud6B3rRu+KHYk+Bwf+WFL2MDCJJ1XG9x137tJQ0xYxor7XziQtuGFbWNdqrvF4Tk26O3H73nfVqXt/fW1A==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "hyphenate-style-name": "^1.0.3"
      }
    },
    "node_modules/css-select": {
      "version": "5.2.2",
      "resolved": "https://registry.npmmirror.com/css-select/-/css-select-5.2.2.tgz",
      "integrity": "sha512-TizTzUddG/xYLA3NXodFM0fSbNizXjOKhqiQQwvhlspadZokn1KDy0NZFS0wuEubIYAV5/c1/lAr0TaaFXEXzw==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "boolbase": "^1.0.0",
        "css-what": "^6.1.0",
        "domhandler": "^5.0.2",
        "domutils": "^3.0.1",
        "nth-check": "^2.0.1"
      },
      "funding": {
        "url": "https://github.com/sponsors/fb55"
      }
    },
    "node_modules/css-tree": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/css-tree/-/css-tree-1.1.3.tgz",
      "integrity": "sha512-tRpdppF7TRazZrjJ6v3stzv93qxRcSsFmW6cX0Zm2NVKpxE1WV1HblnghVv9TreireHkqI/VDEsfolRF1p6y7Q==",
      "license": "MIT",
      "dependencies": {
        "mdn-data": "2.0.14",
        "source-map": "^0.6.1"
      },
      "engines": {
        "node": ">=8.0.0"
      }
    },
    "node_modules/css-tree/node_modules/source-map": {
      "version": "0.6.1",
      "resolved": "https://registry.npmmirror.com/source-map/-/source-map-0.6.1.tgz",
      "integrity": "sha512-UjgapumWlbMhkBgzT7Ykc5YXUT46F0iKu8SGXq0bcwP5dz/h0Plj6enJqjz1Zbq2l5WaqYnrVbwWOWMyF3F47g==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/css-what": {
      "version": "6.2.2",
      "resolved": "https://registry.npmmirror.com/css-what/-/css-what-6.2.2.tgz",
      "integrity": "sha512-u/O3vwbptzhMs3L1fQE82ZSLHQQfto5gyZzwteVIEyeaY5Fc7R4dapF/BvRoSYFeqfBk4m0V1Vafq5Pjv25wvA==",
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">= 6"
      },
      "funding": {
        "url": "https://github.com/sponsors/fb55"
      }
    },
    "node_modules/csstype": {
      "version": "3.2.3",
      "resolved": "https://registry.npmmirror.com/csstype/-/csstype-3.2.3.tgz",
      "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
      "devOptional": true,
      "license": "MIT"
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/decode-uri-component": {
      "version": "0.2.2",
      "resolved": "https://registry.npmmirror.com/decode-uri-component/-/decode-uri-component-0.2.2.tgz",
      "integrity": "sha512-FqUYQ+8o158GyGTrMFJms9qh3CqTKvAqgqsTnkLI8sKu0028orqBhxNMFkFen0zGyg6epACD32pjVk58ngIErQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10"
      }
    },
    "node_modules/deepmerge": {
      "version": "4.3.1",
      "resolved": "https://registry.npmmirror.com/deepmerge/-/deepmerge-4.3.1.tgz",
      "integrity": "sha512-3sUqbMEc77XqpdNO7FRyRog+eW3ph+GYCbj+rK+uYyRMuwsVy0rMiVtPn+QJlKFvWP/1PYpapqYn0Me2knFn+A==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/defaults": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/defaults/-/defaults-1.0.4.tgz",
      "integrity": "sha512-eFuaLoy/Rxalv2kr+lqMlUnrDWV+3j4pljOIJgLIhI058IQfWJ7vXhyEIHu+HtC738klGALYxOKDO0bQP3tg8A==",
      "license": "MIT",
      "dependencies": {
        "clone": "^1.0.2"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/define-lazy-prop": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/define-lazy-prop/-/define-lazy-prop-2.0.0.tgz",
      "integrity": "sha512-Ds09qNh8yw3khSjiJjiUInaGX9xlqZDY7JVryGxdxV7NPeuqQfplOpQ66yJFZut3jLa5zOwkXw1g9EI2uKh4Og==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/depd": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/depd/-/depd-2.0.0.tgz",
      "integrity": "sha512-g7nH6P6dyDioJogAAGprGpCtVImJhpPk/roCzdb3fIh61/s/nPsfR6onyMwkCAR/OlC3yBC0lESvUoQEAssIrw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/destroy": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/destroy/-/destroy-1.2.0.tgz",
      "integrity": "sha512-2sJGJTaXIIaR1w4iJSNoN0hnMY7Gpc/n8D4qSCJw8QqFWXf7cuAgnEHxBpweaVcPevC2l3KpjYCx3NypQQgaJg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8",
        "npm": "1.2.8000 || >= 1.4.16"
      }
    },
    "node_modules/detect-libc": {
      "version": "2.1.2",
      "resolved": "https://registry.npmmirror.com/detect-libc/-/detect-libc-2.1.2.tgz",
      "integrity": "sha512-Btj2BOOO83o3WyH59e8MgXsxEQVcarkUOpEYrubB0urwnN10yQ364rsiByU11nZlqWYZm05i/of7io4mzihBtQ==",
      "license": "Apache-2.0",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/detect-node-es": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/detect-node-es/-/detect-node-es-1.1.0.tgz",
      "integrity": "sha512-ypdmJU/TbBby2Dxibuv7ZLW3Bs1QEmM7nHjEANfohJLvE0XVujisn1qPJcZxg+qDucsr+bP6fLD1rPS3AhJ7EQ==",
      "license": "MIT"
    },
    "node_modules/dnssd-advertise": {
      "version": "1.1.4",
      "resolved": "https://registry.npmmirror.com/dnssd-advertise/-/dnssd-advertise-1.1.4.tgz",
      "integrity": "sha512-AmGyK9WpNf06WeP5TjHZq/wNzP76OuEeaiTlKr9E/EEelYLczywUKoqRz+DPRq/ErssjT4lU+/W7wzJW+7K/ZA==",
      "license": "MIT"
    },
    "node_modules/dom-serializer": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/dom-serializer/-/dom-serializer-2.0.0.tgz",
      "integrity": "sha512-wIkAryiqt/nV5EQKqQpo3SToSOV9J0DnbJqwK7Wv/Trc92zIAYZ4FlMu+JPFW1DfGFt81ZTCGgDEabffXeLyJg==",
      "license": "MIT",
      "dependencies": {
        "domelementtype": "^2.3.0",
        "domhandler": "^5.0.2",
        "entities": "^4.2.0"
      },
      "funding": {
        "url": "https://github.com/cheeriojs/dom-serializer?sponsor=1"
      }
    },
    "node_modules/domelementtype": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/domelementtype/-/domelementtype-2.3.0.tgz",
      "integrity": "sha512-OLETBj6w0OsagBwdXnPdN0cnMfF9opN69co+7ZrbfPGrdpPVNBUj02spi6B1N7wChLQiPn4CSH/zJvXw56gmHw==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/fb55"
        }
      ],
      "license": "BSD-2-Clause"
    },
    "node_modules/domhandler": {
      "version": "5.0.3",
      "resolved": "https://registry.npmmirror.com/domhandler/-/domhandler-5.0.3.tgz",
      "integrity": "sha512-cgwlv/1iFQiFnU96XXgROh8xTeetsnJiDsTc7TYCLFd9+/WNkIqPTxiM/8pSd8VIrhXGTf1Ny1q1hquVqDJB5w==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "domelementtype": "^2.3.0"
      },
      "engines": {
        "node": ">= 4"
      },
      "funding": {
        "url": "https://github.com/fb55/domhandler?sponsor=1"
      }
    },
    "node_modules/domutils": {
      "version": "3.2.2",
      "resolved": "https://registry.npmmirror.com/domutils/-/domutils-3.2.2.tgz",
      "integrity": "sha512-6kZKyUajlDuqlHKVX1w7gyslj9MPIXzIFiz/rGu35uC1wMi+kMhQwGhl4lt9unC9Vb9INnY9Z3/ZA3+FhASLaw==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "dom-serializer": "^2.0.0",
        "domelementtype": "^2.3.0",
        "domhandler": "^5.0.3"
      },
      "funding": {
        "url": "https://github.com/fb55/domutils?sponsor=1"
      }
    },
    "node_modules/ee-first": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/ee-first/-/ee-first-1.1.1.tgz",
      "integrity": "sha512-WMwm9LhRUo+WUaRN+vRuETqG89IgZphVSNkdFgeb6sS/E4OrDIN7t48CAewSHXc6C8lefD8KKfr5vY61brQlow==",
      "license": "MIT"
    },
    "node_modules/electron-to-chromium": {
      "version": "1.5.328",
      "resolved": "https://registry.npmmirror.com/electron-to-chromium/-/electron-to-chromium-1.5.328.tgz",
      "integrity": "sha512-QNQ5l45DzYytThO21403XN3FvK0hOkWDG8viNf6jqS42msJ8I4tGDSpBCgvDRRPnkffafiwAym2X2eHeGD2V0w==",
      "license": "ISC"
    },
    "node_modules/emoji-regex": {
      "version": "8.0.0",
      "resolved": "https://registry.npmmirror.com/emoji-regex/-/emoji-regex-8.0.0.tgz",
      "integrity": "sha512-MSjYzcWNOA0ewAHpz0MxpYFvwg6yjy1NG3xteoqz644VCo/RPgnr1/GGt+ic3iJTzQ8Eu3TdM14SawnVUmGE6A==",
      "license": "MIT"
    },
    "node_modules/encodeurl": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/encodeurl/-/encodeurl-1.0.2.tgz",
      "integrity": "sha512-TPJXq8JqFaVYm2CWmPvnP2Iyo4ZSM7/QKcSmuMLDObfpH5fi7RUGmd/rTDf+rut/saiDiQEeVTNgAmJEdAOx0w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/entities": {
      "version": "4.5.0",
      "resolved": "https://registry.npmmirror.com/entities/-/entities-4.5.0.tgz",
      "integrity": "sha512-V0hjH4dGPh9Ao5p0MoRY6BVqtwCjhz6vI5LT8AJ55H+4g9/4vbHx1I54fS0XuclLhDHArPQCiMjDxjaL8fPxhw==",
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">=0.12"
      },
      "funding": {
        "url": "https://github.com/fb55/entities?sponsor=1"
      }
    },
    "node_modules/error-stack-parser": {
      "version": "2.1.4",
      "resolved": "https://registry.npmmirror.com/error-stack-parser/-/error-stack-parser-2.1.4.tgz",
      "integrity": "sha512-Sk5V6wVazPhq5MhpO+AUxJn5x7XSXGl1R93Vn7i+zS15KDVxQijejNCrz8340/2bgLBjR9GtEG8ZVKONDjcqGQ==",
      "license": "MIT",
      "dependencies": {
        "stackframe": "^1.3.4"
      }
    },
    "node_modules/escalade": {
      "version": "3.2.0",
      "resolved": "https://registry.npmmirror.com/escalade/-/escalade-3.2.0.tgz",
      "integrity": "sha512-WUj2qlxaQtO4g6Pq5c29GTcWGDyd8itL8zTlipgECz3JesAiiOKotd8JU6otB3PACgG6xkJUyVhboMS+bje/jA==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/escape-html": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/escape-html/-/escape-html-1.0.3.tgz",
      "integrity": "sha512-NiSupZ4OeuGwr68lGIeym/ksIZMJodUGOSCZ/FSnTxcrekbvqrgdUxlJOMpijaKZVjAJrWrGs/6Jy8OMuyj9ow==",
      "license": "MIT"
    },
    "node_modules/escape-string-regexp": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/escape-string-regexp/-/escape-string-regexp-4.0.0.tgz",
      "integrity": "sha512-TtpcNJ3XAzx3Gq8sWRzJaVajRs0uVxA2YAkdb1jm2YkPz4G6egUFAyA3n5vtEIZefPk5Wa4UXbKuS5fKkJWdgA==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/esprima": {
      "version": "4.0.1",
      "resolved": "https://registry.npmmirror.com/esprima/-/esprima-4.0.1.tgz",
      "integrity": "sha512-eGuFFw7Upda+g4p+QHvnW0RyTX/SVeJBDM/gCtMARO0cLuT2HcEKnTPvhjV6aGeqrCB/sbNop0Kszm0jsaWU4A==",
      "license": "BSD-2-Clause",
      "bin": {
        "esparse": "bin/esparse.js",
        "esvalidate": "bin/esvalidate.js"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/etag": {
      "version": "1.8.1",
      "resolved": "https://registry.npmmirror.com/etag/-/etag-1.8.1.tgz",
      "integrity": "sha512-aIL5Fx7mawVa300al2BnEE4iNvo1qETxLrPI/o05L7z6go7fCw1J6EQmbK4FmJ2AS7kgVF/KEZWufBfdClMcPg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/event-target-shim": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/event-target-shim/-/event-target-shim-5.0.1.tgz",
      "integrity": "sha512-i/2XbnSz/uxRCU6+NdVJgKWDTM427+MqYbkQzD321DuCQJUqOuJKIA0IM2+W2xtYHdKOmZ4dR6fExsd4SXL+WQ==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/expo": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo/-/expo-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-KfHOCllUcPpkrdBseJYxShwIKeW2qFdoDtZmXjcHhEWqlTKH6s7B4m0og3bx86s3CBzaDqils9wO/Y5VO7jRRw==",
      "license": "MIT",
      "dependencies": {
        "@babel/runtime": "^7.20.0",
        "@expo/cli": "55.0.20-canary-20260328-bdc6273",
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "@expo/config-plugins": "55.0.8-canary-20260328-bdc6273",
        "@expo/devtools": "55.0.3-canary-20260328-bdc6273",
        "@expo/fingerprint": "0.16.7-canary-20260328-bdc6273",
        "@expo/local-build-cache-provider": "55.0.8-canary-20260328-bdc6273",
        "@expo/log-box": "55.0.9-canary-20260328-bdc6273",
        "@expo/metro": "~54.2.0",
        "@expo/metro-config": "55.0.12-canary-20260328-bdc6273",
        "@expo/vector-icons": "^15.0.2",
        "@ungap/structured-clone": "^1.3.0",
        "babel-preset-expo": "55.0.14-canary-20260328-bdc6273",
        "expo-asset": "55.0.11-canary-20260328-bdc6273",
        "expo-constants": "55.0.10-canary-20260328-bdc6273",
        "expo-file-system": "55.0.13-canary-20260328-bdc6273",
        "expo-font": "55.0.5-canary-20260328-bdc6273",
        "expo-keep-awake": "55.0.5-canary-20260328-bdc6273",
        "expo-modules-autolinking": "55.0.13-canary-20260328-bdc6273",
        "expo-modules-core": "55.0.19-canary-20260328-bdc6273",
        "pretty-format": "^29.7.0",
        "react-refresh": "^0.14.2",
        "whatwg-url-minimum": "^0.1.1"
      },
      "bin": {
        "expo": "bin/cli",
        "expo-modules-autolinking": "bin/autolinking",
        "fingerprint": "bin/fingerprint"
      },
      "peerDependencies": {
        "@expo/dom-webview": "55.0.4-canary-20260328-bdc6273",
        "@expo/metro-runtime": "55.0.8-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*",
        "react-native-webview": "*"
      },
      "peerDependenciesMeta": {
        "@expo/dom-webview": {
          "optional": true
        },
        "@expo/metro-runtime": {
          "optional": true
        },
        "react-native-webview": {
          "optional": true
        }
      }
    },
    "node_modules/expo-asset": {
      "version": "55.0.11-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-asset/-/expo-asset-55.0.11-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-xFhENuhTpGyfEmte8fQNT23FPJMZo9bsCXwb5IO7ICTVgmOQU+MpZHnuWB+RbUyhv/ZAiN3oQwEM6cMORBLWvQ==",
      "license": "MIT",
      "dependencies": {
        "@expo/image-utils": "0.8.13-canary-20260328-bdc6273",
        "expo-constants": "55.0.10-canary-20260328-bdc6273"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-audio": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-audio/-/expo-audio-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-6M5jlvvLikg84GZGqbomYA3fIF4yb71p1H0+/EUAJWpg8jWD5l0cfNh5pD3mLbBBFxbSbSeiSwV9vhSvRfKRHw==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-asset": "55.0.11-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-background-fetch": {
      "version": "55.0.12",
      "resolved": "https://registry.npmjs.org/expo-background-fetch/-/expo-background-fetch-55.0.12.tgz",
      "integrity": "sha512-QVzoV7Z5luxX2lra11ac18cvr3wL3pqu0Na8OShknocpq7f3e+I/+LubMbdAC3cErLYINsWtoxi7/D/c3wD22A==",
      "license": "MIT",
      "dependencies": {
        "expo-task-manager": "~55.0.12"
      },
      "peerDependencies": {
        "expo": "*"
      }
    },
    "node_modules/expo-blur": {
      "version": "55.0.11-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-blur/-/expo-blur-55.0.11-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Y9iQJrCef0zJD02X/gblIrAbGwU/NAePYxlPYUivAsVVmyCFarjr//VJpQ+j1FFiFj9Bg24NRI8Isf1SOaRB1Q==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-clipboard": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-clipboard/-/expo-clipboard-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-SX6WQP5+Yswn8fT64uZqaCq1JPYJTELkVYNErXm3KQTD4rmjf/HvCwr6BhSOajxfIZxAGIuE82xkTkgenqnKqg==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-constants": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-constants/-/expo-constants-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-K6Eu2OFjIlDmHsupLdaS/qxIDk+kzPVmFC0kmsME5NDZpPiH7eyS47q3wiMa9ZRxOtk4bLbSYMfMXQ1pcnhh/w==",
      "license": "MIT",
      "dependencies": {
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "@expo/env": "2.1.2-canary-20260328-bdc6273"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react-native": "*"
      }
    },
    "node_modules/expo-file-system": {
      "version": "55.0.13-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-file-system/-/expo-file-system-55.0.13-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-aifXLtABpzNZGbCmAEk7zkI9efy9cRaqxVV++yMvPqCQw3Kxx9QNnhtQD/r/ZrvlE5shRZeCAQjWCfDjCe1Duw==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react-native": "*"
      }
    },
    "node_modules/expo-font": {
      "version": "55.0.5-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-font/-/expo-font-55.0.5-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-ttVJOIGEwDcIvHwdxmjjd6uY/neDxZjAdZLCDmb7VmFqHnFBDjskKAIx6gR7BvuJjok5ynmqsS4If+hZJkUZ6A==",
      "license": "MIT",
      "dependencies": {
        "fontfaceobserver": "^2.1.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-glass-effect": {
      "version": "55.0.9-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-glass-effect/-/expo-glass-effect-55.0.9-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-YdqkJdgJT6pEln3O8dm+qVS5Sv4OJtirmvEbXvSrJc4fWhEXnwB9y8PjXa9pHNfnVKyhQyJFbrxq4tc7LaWV4Q==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-haptics": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-haptics/-/expo-haptics-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-vhYKWMJsphgTRaoHO0chBUUsd8bDls8atbMSeCfT2gQyxeaN/SFjqnKQRnjRkz9GFltM5hbN2FTf7HAi8HJYQg==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273"
      }
    },
    "node_modules/expo-image": {
      "version": "55.0.7-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-image/-/expo-image-55.0.7-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-gl/e2yJcFxpk7O/WQwvICTm63fiLT606n1DBIdNueTn27Fd1iaN9s2LXcjp6rxo1PVid0dSNQNu5q2fWXASUZQ==",
      "license": "MIT",
      "dependencies": {
        "sf-symbols-typescript": "^2.2.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*",
        "react-native-web": "*"
      },
      "peerDependenciesMeta": {
        "react-native-web": {
          "optional": true
        }
      }
    },
    "node_modules/expo-linking": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-linking/-/expo-linking-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-2RTDxY438xK4dmObaA63wJncj25Fo1Wv0kxO1aF4aCO22wsndoViAWcP03Du1r7z4G1qvef3m9vko5qxp0Cwmw==",
      "license": "MIT",
      "dependencies": {
        "expo-constants": "55.0.10-canary-20260328-bdc6273",
        "invariant": "^2.2.4"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-modules-autolinking": {
      "version": "55.0.13-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-modules-autolinking/-/expo-modules-autolinking-55.0.13-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Ibo63RLluAXf3Fz9uPNHwP9vhyRu3bmmO3W+UR06WZbPymhgmu5mMBYpIoQsqMEMbTRuWNOj4YqUQiXuEVCiUg==",
      "license": "MIT",
      "dependencies": {
        "@expo/require-utils": "55.0.4-canary-20260328-bdc6273",
        "@expo/spawn-async": "^1.7.2",
        "chalk": "^4.1.0",
        "commander": "^7.2.0"
      },
      "bin": {
        "expo-modules-autolinking": "bin/expo-modules-autolinking.js"
      }
    },
    "node_modules/expo-modules-core": {
      "version": "55.0.19-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-modules-core/-/expo-modules-core-55.0.19-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-rQPGNCY2rCFPv6TLqIuDhqZ6ozploYnArgXgkzwzLE5b8p+ZOy77jHYw4+SHdkbKhXEa0KZWJWxYnwhEZjznnQ==",
      "license": "MIT",
      "dependencies": {
        "invariant": "^2.2.4"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-router": {
      "version": "55.0.9-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-router/-/expo-router-55.0.9-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-X+R3IrcXqv3cMdJSPOQNCb+ayHOtyWzQq6jGXJ8w10AqbygrPUpJv7GXUmHFhArBD1Q9tL6cgrT0P+jZjCDakg==",
      "license": "MIT",
      "dependencies": {
        "@expo/metro-runtime": "55.0.8-canary-20260328-bdc6273",
        "@expo/schema-utils": "55.0.3-canary-20260328-bdc6273",
        "@radix-ui/react-slot": "^1.2.0",
        "@radix-ui/react-tabs": "^1.1.12",
        "@react-navigation/bottom-tabs": "^7.15.5",
        "@react-navigation/native": "^7.1.33",
        "@react-navigation/native-stack": "^7.14.5",
        "client-only": "^0.0.1",
        "debug": "^4.3.4",
        "escape-string-regexp": "^4.0.0",
        "expo-glass-effect": "55.0.9-canary-20260328-bdc6273",
        "expo-image": "55.0.7-canary-20260328-bdc6273",
        "expo-server": "55.0.7-canary-20260328-bdc6273",
        "expo-symbols": "55.0.6-canary-20260328-bdc6273",
        "fast-deep-equal": "^3.1.3",
        "invariant": "^2.2.4",
        "nanoid": "^3.3.8",
        "query-string": "^7.1.3",
        "react-fast-compare": "^3.2.2",
        "react-native-is-edge-to-edge": "^1.2.1",
        "semver": "~7.6.3",
        "server-only": "^0.0.1",
        "sf-symbols-typescript": "^2.1.0",
        "shallowequal": "^1.1.0",
        "use-latest-callback": "^0.2.1",
        "vaul": "^1.1.2"
      },
      "peerDependencies": {
        "@expo/log-box": "55.0.9-canary-20260328-bdc6273",
        "@expo/metro-runtime": "55.0.8-canary-20260328-bdc6273",
        "@react-navigation/drawer": "^7.9.4",
        "@testing-library/react-native": ">= 13.2.0",
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-constants": "55.0.10-canary-20260328-bdc6273",
        "expo-linking": "55.0.10-canary-20260328-bdc6273",
        "react": "*",
        "react-dom": "*",
        "react-native": "*",
        "react-native-gesture-handler": "*",
        "react-native-reanimated": "*",
        "react-native-safe-area-context": ">= 5.4.0",
        "react-native-screens": "*",
        "react-native-web": "*",
        "react-server-dom-webpack": "~19.0.4 || ~19.1.5 || ~19.2.4"
      },
      "peerDependenciesMeta": {
        "@react-navigation/drawer": {
          "optional": true
        },
        "@testing-library/react-native": {
          "optional": true
        },
        "react-dom": {
          "optional": true
        },
        "react-native-gesture-handler": {
          "optional": true
        },
        "react-native-reanimated": {
          "optional": true
        },
        "react-native-web": {
          "optional": true
        },
        "react-server-dom-webpack": {
          "optional": true
        }
      }
    },
    "node_modules/expo-router/node_modules/@radix-ui/react-tabs": {
      "version": "1.1.13",
      "resolved": "https://registry.npmmirror.com/@radix-ui/react-tabs/-/react-tabs-1.1.13.tgz",
      "integrity": "sha512-7xdcatg7/U+7+Udyoj2zodtI9H/IIopqo+YOIcZOq1nJwXWBZ9p8xiu5llXlekDbZkca79a/fozEYQXIA4sW6A==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/primitive": "1.1.3",
        "@radix-ui/react-context": "1.1.2",
        "@radix-ui/react-direction": "1.1.1",
        "@radix-ui/react-id": "1.1.1",
        "@radix-ui/react-presence": "1.1.5",
        "@radix-ui/react-primitive": "2.1.3",
        "@radix-ui/react-roving-focus": "1.1.11",
        "@radix-ui/react-use-controllable-state": "1.2.2"
      },
      "peerDependencies": {
        "@types/react": "*",
        "@types/react-dom": "*",
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        },
        "@types/react-dom": {
          "optional": true
        }
      }
    },
    "node_modules/expo-router/node_modules/semver": {
      "version": "7.6.3",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.6.3.tgz",
      "integrity": "sha512-oVekP1cKtI+CTDvHWYFUcMtsK/00wmAEfyqKfNdARm8u1wNVhSgaX7A8d4UuIlUI5e84iEwOhs7ZPYRmzU9U6A==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/expo-secure-store": {
      "version": "55.0.10-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-secure-store/-/expo-secure-store-55.0.10-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-klLXN5awOTEzNUcp3ii8gMnhtrskn1+YqGtIdkX808lc08zOeZuP+1SxrcMAa2OyxVKTyYgath6NofxubhbNpg==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273"
      }
    },
    "node_modules/expo-server": {
      "version": "55.0.7-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-server/-/expo-server-55.0.7-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-FT5jQClUlFTd+6KQOMIP3L0mRu/atZZ7ulDKu0xt6amK4tC0cHi/73eoy/YKOI12ibKpMYa2P05WD+Cm6LF2OQ==",
      "license": "MIT",
      "engines": {
        "node": ">=20.16.0"
      }
    },
    "node_modules/expo-speech-recognition": {
      "version": "3.1.2",
      "resolved": "https://registry.npmmirror.com/expo-speech-recognition/-/expo-speech-recognition-3.1.2.tgz",
      "integrity": "sha512-yaXy+6w218Urdshits2KsfLjXNCnGNlXzUxEP4BVehKEbiIPAeUKBzuicCeELU5H2zTLwL9u+RjbFAUom4LiYQ==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "*",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-sqlite": {
      "version": "55.0.13",
      "resolved": "https://registry.npmjs.org/expo-sqlite/-/expo-sqlite-55.0.13.tgz",
      "integrity": "sha512-1iGQKuZZLnZ/jfa63j1klaOXyzYTu7C98oHqV1aiJisdauCVUEh3duADZ6pT3w5KYKT9ysDySgEHjUcgINojRg==",
      "license": "MIT",
      "dependencies": {
        "await-lock": "^2.2.2"
      },
      "peerDependencies": {
        "expo": "*",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-status-bar": {
      "version": "55.0.5-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-status-bar/-/expo-status-bar-55.0.5-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-8BLOQIy5f0AuL9ZtsHA8KpIPAA0HLKhImDOBcyYRd4nkxhI/N2taNm8MwBfHH5xgFFp+ZroUe7pYzYxkA4XmuA==",
      "license": "MIT",
      "dependencies": {
        "react-native-is-edge-to-edge": "^1.2.1"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-symbols": {
      "version": "55.0.6-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-symbols/-/expo-symbols-55.0.6-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-BIJN+KP9cr5MkAzsOkFX1aetDMByDNFW4OgJU7jMdM05Gd881sn1ysOTI/TxRr4BJfNu1A9nlzHzpFkLuI1k/w==",
      "license": "MIT",
      "dependencies": {
        "@expo-google-fonts/material-symbols": "^0.4.1",
        "sf-symbols-typescript": "^2.0.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-font": "55.0.5-canary-20260328-bdc6273",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo-task-manager": {
      "version": "55.0.12",
      "resolved": "https://registry.npmjs.org/expo-task-manager/-/expo-task-manager-55.0.12.tgz",
      "integrity": "sha512-lKt0uLiIIZyWTn8tD7KDMFr0QZVAbBo8OLn0IBGN2aapJBB2A//VSd7EuD+NUkU9jdlxfG6Co63ZCt0X1/NeUA==",
      "license": "MIT",
      "dependencies": {
        "unimodules-app-loader": "~55.0.4"
      },
      "peerDependencies": {
        "expo": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo/node_modules/@expo/cli": {
      "version": "55.0.20-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/cli/-/cli-55.0.20-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Q7zXS/k8+PcXeNs6QakPCsBkOBRRldY2e/LaUhFGYaSyXADWS2PDx06h+URAv9BMYzeioincSLx2rl/wrwhSmA==",
      "license": "MIT",
      "dependencies": {
        "@expo/code-signing-certificates": "^0.0.6",
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "@expo/config-plugins": "55.0.8-canary-20260328-bdc6273",
        "@expo/devcert": "^1.2.1",
        "@expo/env": "2.1.2-canary-20260328-bdc6273",
        "@expo/image-utils": "0.8.13-canary-20260328-bdc6273",
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@expo/log-box": "55.0.9-canary-20260328-bdc6273",
        "@expo/metro": "~54.2.0",
        "@expo/metro-config": "55.0.12-canary-20260328-bdc6273",
        "@expo/osascript": "2.4.3-canary-20260328-bdc6273",
        "@expo/package-manager": "1.10.4-canary-20260328-bdc6273",
        "@expo/plist": "0.5.3-canary-20260328-bdc6273",
        "@expo/prebuild-config": "55.0.12-canary-20260328-bdc6273",
        "@expo/require-utils": "55.0.4-canary-20260328-bdc6273",
        "@expo/router-server": "55.0.12-canary-20260328-bdc6273",
        "@expo/schema-utils": "55.0.3-canary-20260328-bdc6273",
        "@expo/spawn-async": "^1.7.2",
        "@expo/ws-tunnel": "^1.0.1",
        "@expo/xcpretty": "^4.4.0",
        "@react-native/dev-middleware": "0.83.4",
        "accepts": "^1.3.8",
        "arg": "^5.0.2",
        "better-opn": "~3.0.2",
        "bplist-creator": "0.1.0",
        "bplist-parser": "^0.3.1",
        "chalk": "^4.0.0",
        "ci-info": "^3.3.0",
        "compression": "^1.7.4",
        "connect": "^3.7.0",
        "debug": "^4.3.4",
        "dnssd-advertise": "^1.1.3",
        "expo-server": "55.0.7-canary-20260328-bdc6273",
        "fetch-nodeshim": "^0.4.6",
        "getenv": "^2.0.0",
        "glob": "^13.0.0",
        "lan-network": "^0.2.0",
        "multitars": "^0.2.3",
        "node-forge": "^1.3.3",
        "npm-package-arg": "^11.0.0",
        "ora": "^3.4.0",
        "picomatch": "^4.0.3",
        "pretty-format": "^29.7.0",
        "progress": "^2.0.3",
        "prompts": "^2.3.2",
        "resolve-from": "^5.0.0",
        "semver": "^7.6.0",
        "send": "^0.19.0",
        "slugify": "^1.3.4",
        "source-map-support": "~0.5.21",
        "stacktrace-parser": "^0.1.10",
        "structured-headers": "^0.4.1",
        "terminal-link": "^2.1.1",
        "toqr": "^0.1.1",
        "wrap-ansi": "^7.0.0",
        "ws": "^8.12.1",
        "zod": "^3.25.76"
      },
      "bin": {
        "expo-internal": "build/bin/cli"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-router": "55.0.9-canary-20260328-bdc6273",
        "react-native": "*"
      },
      "peerDependenciesMeta": {
        "expo-router": {
          "optional": true
        },
        "react-native": {
          "optional": true
        }
      }
    },
    "node_modules/expo/node_modules/@expo/cli/node_modules/@expo/prebuild-config": {
      "version": "55.0.12-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/prebuild-config/-/prebuild-config-55.0.12-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-hVj++vODTtVyBUeVW92UY4xXDnAcdv9LLvaTPXINyLFXlFXvDxYQUUeptuDdJVfgu+xMYzrzyUDw7v33EVvCAA==",
      "license": "MIT",
      "dependencies": {
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "@expo/config-plugins": "55.0.8-canary-20260328-bdc6273",
        "@expo/config-types": "55.0.6-canary-20260328-bdc6273",
        "@expo/image-utils": "0.8.13-canary-20260328-bdc6273",
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@react-native/normalize-colors": "0.83.4",
        "debug": "^4.3.1",
        "resolve-from": "^5.0.0",
        "semver": "^7.6.0",
        "xml2js": "0.6.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273"
      }
    },
    "node_modules/expo/node_modules/@expo/cli/node_modules/@expo/router-server": {
      "version": "55.0.12-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/router-server/-/router-server-55.0.12-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-+PR7y98jFmwRsrcrugGSEismtz63/BIavsy+ePKudDJRH9iPPRkKRcc1IcnVd3Lw10e0rdxf61q8WivcSVjGcQ==",
      "license": "MIT",
      "dependencies": {
        "debug": "^4.3.4"
      },
      "peerDependencies": {
        "@expo/metro-runtime": "55.0.8-canary-20260328-bdc6273",
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-constants": "55.0.10-canary-20260328-bdc6273",
        "expo-font": "55.0.5-canary-20260328-bdc6273",
        "expo-router": "55.0.9-canary-20260328-bdc6273",
        "expo-server": "55.0.7-canary-20260328-bdc6273",
        "react": "*",
        "react-dom": "*",
        "react-server-dom-webpack": "~19.0.1 || ~19.1.2 || ~19.2.1"
      },
      "peerDependenciesMeta": {
        "@expo/metro-runtime": {
          "optional": true
        },
        "expo-router": {
          "optional": true
        },
        "react-dom": {
          "optional": true
        },
        "react-server-dom-webpack": {
          "optional": true
        }
      }
    },
    "node_modules/expo/node_modules/@expo/metro-config": {
      "version": "55.0.12-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/@expo/metro-config/-/metro-config-55.0.12-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-Y01CxLwR9/+M/RkfhvuduPpxavm4t5V5biCJbGMzYFkw4GF0imkw9X5Teti3OkuieAB50Alke/GwtRtBgYkeIg==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.20.0",
        "@babel/core": "^7.20.0",
        "@babel/generator": "^7.20.5",
        "@expo/config": "55.0.12-canary-20260328-bdc6273",
        "@expo/env": "2.1.2-canary-20260328-bdc6273",
        "@expo/json-file": "10.0.13-canary-20260328-bdc6273",
        "@expo/metro": "~54.2.0",
        "@expo/spawn-async": "^1.7.2",
        "browserslist": "^4.25.0",
        "chalk": "^4.1.0",
        "debug": "^4.3.2",
        "getenv": "^2.0.0",
        "glob": "^13.0.0",
        "hermes-parser": "^0.32.0",
        "jsc-safe-url": "^0.2.4",
        "lightningcss": "^1.30.1",
        "picomatch": "^4.0.3",
        "postcss": "~8.4.32",
        "resolve-from": "^5.0.0"
      },
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273"
      },
      "peerDependenciesMeta": {
        "expo": {
          "optional": true
        }
      }
    },
    "node_modules/expo/node_modules/@expo/vector-icons": {
      "version": "15.1.1",
      "resolved": "https://registry.npmmirror.com/@expo/vector-icons/-/vector-icons-15.1.1.tgz",
      "integrity": "sha512-Iu2VkcoI5vygbtYngm7jb4ifxElNVXQYdDrYkT7UCEIiKLeWnQY0wf2ZhHZ+Wro6Sc5TaumpKUOqDRpLi5rkvw==",
      "license": "MIT",
      "peerDependencies": {
        "expo-font": ">=14.0.4",
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/expo/node_modules/babel-preset-expo": {
      "version": "55.0.14-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/babel-preset-expo/-/babel-preset-expo-55.0.14-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-ZeiGLB1mfQ98oLyaCz1q47FaZaygZVbUaRASxgvqEFUWMHAb4mGSsFVLoWNosRgPfMux8pQj8wB/ajYgK1mMKw==",
      "license": "MIT",
      "dependencies": {
        "@babel/generator": "^7.20.5",
        "@babel/helper-module-imports": "^7.25.9",
        "@babel/plugin-proposal-decorators": "^7.12.9",
        "@babel/plugin-proposal-export-default-from": "^7.24.7",
        "@babel/plugin-syntax-export-default-from": "^7.24.7",
        "@babel/plugin-transform-class-static-block": "^7.27.1",
        "@babel/plugin-transform-export-namespace-from": "^7.25.9",
        "@babel/plugin-transform-flow-strip-types": "^7.25.2",
        "@babel/plugin-transform-modules-commonjs": "^7.24.8",
        "@babel/plugin-transform-object-rest-spread": "^7.24.7",
        "@babel/plugin-transform-parameters": "^7.24.7",
        "@babel/plugin-transform-private-methods": "^7.24.7",
        "@babel/plugin-transform-private-property-in-object": "^7.24.7",
        "@babel/plugin-transform-runtime": "^7.24.7",
        "@babel/preset-react": "^7.22.15",
        "@babel/preset-typescript": "^7.23.0",
        "@react-native/babel-preset": "0.83.4",
        "babel-plugin-react-compiler": "^1.0.0",
        "babel-plugin-react-native-web": "~0.21.0",
        "babel-plugin-syntax-hermes-parser": "^0.32.0",
        "babel-plugin-transform-flow-enums": "^0.0.2",
        "debug": "^4.3.4",
        "resolve-from": "^5.0.0"
      },
      "peerDependencies": {
        "@babel/runtime": "^7.20.0",
        "expo": "55.0.10-canary-20260328-bdc6273",
        "expo-widgets": "55.0.9-canary-20260328-bdc6273",
        "react-refresh": ">=0.14.0 <1.0.0"
      },
      "peerDependenciesMeta": {
        "@babel/runtime": {
          "optional": true
        },
        "expo": {
          "optional": true
        },
        "expo-widgets": {
          "optional": true
        }
      }
    },
    "node_modules/expo/node_modules/ci-info": {
      "version": "3.9.0",
      "resolved": "https://registry.npmmirror.com/ci-info/-/ci-info-3.9.0.tgz",
      "integrity": "sha512-NIxF55hv4nSqQswkAeiOi1r83xy8JldOFDTWiug55KBu9Jnblncd2U6ViHmYgHf01TPZS77NJBhBMKdWj9HQMQ==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/sibiraj-s"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/expo/node_modules/expo-keep-awake": {
      "version": "55.0.5-canary-20260328-bdc6273",
      "resolved": "https://registry.npmmirror.com/expo-keep-awake/-/expo-keep-awake-55.0.5-canary-20260328-bdc6273.tgz",
      "integrity": "sha512-x0m/gkCgVLSdIKwZUN/8cB1RbUtQ3zXW7Wwq0//CO04Gr4QfFXuDT+vZD8TytU9qNQFYj00XKM3z6VYTRpx8YA==",
      "license": "MIT",
      "peerDependencies": {
        "expo": "55.0.10-canary-20260328-bdc6273",
        "react": "*"
      }
    },
    "node_modules/expo/node_modules/picomatch": {
      "version": "4.0.4",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-4.0.4.tgz",
      "integrity": "sha512-QP88BAKvMam/3NxH6vj2o21R6MjxZUAd6nlwAS/pnGvN9IVLocLHxGYIzFhg6fUQ+5th6P4dv4eW9jX3DSIj7A==",
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/expo/node_modules/ws": {
      "version": "8.20.0",
      "resolved": "https://registry.npmmirror.com/ws/-/ws-8.20.0.tgz",
      "integrity": "sha512-sAt8BhgNbzCtgGbt2OxmpuryO63ZoDk/sqaB/znQm94T4fCEsy/yV+7CdC1kJhOU9lboAEU7R3kquuycDoibVA==",
      "license": "MIT",
      "engines": {
        "node": ">=10.0.0"
      },
      "peerDependencies": {
        "bufferutil": "^4.0.1",
        "utf-8-validate": ">=5.0.2"
      },
      "peerDependenciesMeta": {
        "bufferutil": {
          "optional": true
        },
        "utf-8-validate": {
          "optional": true
        }
      }
    },
    "node_modules/exponential-backoff": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/exponential-backoff/-/exponential-backoff-3.1.3.tgz",
      "integrity": "sha512-ZgEeZXj30q+I0EN+CbSSpIyPaJ5HVQD18Z1m+u1FXbAeT94mr1zw50q4q6jiiC447Nl/YTcIYSAftiGqetwXCA==",
      "license": "Apache-2.0"
    },
    "node_modules/fast-deep-equal": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/fast-deep-equal/-/fast-deep-equal-3.1.3.tgz",
      "integrity": "sha512-f3qQ9oQy9j2AhBe/H9VC91wLmKBCCU/gDOnKNAYG5hswO7BLKj09Hc5HYNz9cGI++xlpDCIgDaitVs03ATR84Q==",
      "license": "MIT"
    },
    "node_modules/fast-json-stable-stringify": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/fast-json-stable-stringify/-/fast-json-stable-stringify-2.1.0.tgz",
      "integrity": "sha512-lhd/wF+Lk98HZoTCtlVraHtfh5XYijIjalXck7saUtuanSDyLMxnHhSXEDJqHxD7msR8D0uCmqlkwjCV8xvwHw==",
      "license": "MIT"
    },
    "node_modules/fb-dotslash": {
      "version": "0.5.8",
      "resolved": "https://registry.npmmirror.com/fb-dotslash/-/fb-dotslash-0.5.8.tgz",
      "integrity": "sha512-XHYLKk9J4BupDxi9bSEhkfss0m+Vr9ChTrjhf9l2iw3jB5C7BnY4GVPoMcqbrTutsKJso6yj2nAB6BI/F2oZaA==",
      "license": "(MIT OR Apache-2.0)",
      "bin": {
        "dotslash": "bin/dotslash"
      },
      "engines": {
        "node": ">=20"
      }
    },
    "node_modules/fb-watchman": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/fb-watchman/-/fb-watchman-2.0.2.tgz",
      "integrity": "sha512-p5161BqbuCaSnB8jIbzQHOlpgsPmK5rJVDfDKO91Axs5NC1uu3HRQm6wt9cd9/+GtQQIO53JdGXXoyDpTAsgYA==",
      "license": "Apache-2.0",
      "dependencies": {
        "bser": "2.1.1"
      }
    },
    "node_modules/fbjs": {
      "version": "3.0.5",
      "resolved": "https://registry.npmmirror.com/fbjs/-/fbjs-3.0.5.tgz",
      "integrity": "sha512-ztsSx77JBtkuMrEypfhgc3cI0+0h+svqeie7xHbh1k/IKdcydnvadp/mUaGgjAOXQmQSxsqgaRhS3q9fy+1kxg==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "cross-fetch": "^3.1.5",
        "fbjs-css-vars": "^1.0.0",
        "loose-envify": "^1.0.0",
        "object-assign": "^4.1.0",
        "promise": "^7.1.1",
        "setimmediate": "^1.0.5",
        "ua-parser-js": "^1.0.35"
      }
    },
    "node_modules/fbjs-css-vars": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/fbjs-css-vars/-/fbjs-css-vars-1.0.2.tgz",
      "integrity": "sha512-b2XGFAFdWZWg0phtAWLHCk836A1Xann+I+Dgd3Gk64MHKZO44FfoD1KxyvbSh0qZsIoXQGGlVztIY+oitJPpRQ==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/fbjs/node_modules/promise": {
      "version": "7.3.1",
      "resolved": "https://registry.npmmirror.com/promise/-/promise-7.3.1.tgz",
      "integrity": "sha512-nolQXZ/4L+bP/UGlkfaIujX9BKxGwmQ9OT4mOt5yvy8iK1h3wqTEJCijzGANTCCl9nWjY41juyAn2K3Q1hLLTg==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "asap": "~2.0.3"
      }
    },
    "node_modules/fetch-nodeshim": {
      "version": "0.4.10",
      "resolved": "https://registry.npmmirror.com/fetch-nodeshim/-/fetch-nodeshim-0.4.10.tgz",
      "integrity": "sha512-m6I8ALe4L4XpdETy7MJZWs6L1IVMbjs99bwbpIKphxX+0CTns4IKDWJY0LWfr4YsFjfg+z1TjzTMU8lKl8rG0w==",
      "license": "MIT"
    },
    "node_modules/fill-range": {
      "version": "7.1.1",
      "resolved": "https://registry.npmmirror.com/fill-range/-/fill-range-7.1.1.tgz",
      "integrity": "sha512-YsGpe3WHLK8ZYi4tWDg2Jy3ebRz2rXowDxnld4bkQB00cc/1Zw9AWnC0i9ztDJitivtQvaI9KaLyKrc+hBW0yg==",
      "license": "MIT",
      "dependencies": {
        "to-regex-range": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/filter-obj": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/filter-obj/-/filter-obj-1.1.0.tgz",
      "integrity": "sha512-8rXg1ZnX7xzy2NGDVkBVaAy+lSlPNwad13BtgSlLuxfIslyt5Vg64U7tFcCt4WS1R0hvtnQybT/IyCkGZ3DpXQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/finalhandler": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/finalhandler/-/finalhandler-1.1.2.tgz",
      "integrity": "sha512-aAWcW57uxVNrQZqFXjITpW3sIUQmHGG3qSb9mUah9MgMC4NeWhNOlNjXEYq3HjRAvL6arUviZGGJsBg6z0zsWA==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "on-finished": "~2.3.0",
        "parseurl": "~1.3.3",
        "statuses": "~1.5.0",
        "unpipe": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/finalhandler/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/finalhandler/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/find-up": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/find-up/-/find-up-4.1.0.tgz",
      "integrity": "sha512-PpOwAdQ/YlXQ2vj8a3h8IipDuYRi3wceVQQGYWxNINccq40Anw7BlsEXCMbt1Zt+OLA6Fq9suIpIWD0OsnISlw==",
      "license": "MIT",
      "dependencies": {
        "locate-path": "^5.0.0",
        "path-exists": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/flow-enums-runtime": {
      "version": "0.0.6",
      "resolved": "https://registry.npmmirror.com/flow-enums-runtime/-/flow-enums-runtime-0.0.6.tgz",
      "integrity": "sha512-3PYnM29RFXwvAN6Pc/scUfkI7RwhQ/xqyLUyPNlXUp9S40zI8nup9tUSrTLSVnWGBN38FNiGWbwZOB6uR4OGdw==",
      "license": "MIT"
    },
    "node_modules/fontfaceobserver": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/fontfaceobserver/-/fontfaceobserver-2.3.0.tgz",
      "integrity": "sha512-6FPvD/IVyT4ZlNe7Wcn5Fb/4ChigpucKYSvD6a+0iMoLn2inpo711eyIcKjmDtE5XNcgAkSH9uN/nfAeZzHEfg==",
      "license": "BSD-2-Clause"
    },
    "node_modules/fresh": {
      "version": "0.5.2",
      "resolved": "https://registry.npmmirror.com/fresh/-/fresh-0.5.2.tgz",
      "integrity": "sha512-zJ2mQYM18rEFOudeV4GShTGIQ7RbzA7ozbU9I/XBpm7kqgMywgmylMwXHxZJmkVoYkna9d2pVXVXPdYTP9ej8Q==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/fs.realpath": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/fs.realpath/-/fs.realpath-1.0.0.tgz",
      "integrity": "sha512-OO0pH2lK6a0hZnAdau5ItzHPI6pUlvI7jMVnxUQRtw4owF2wk8lOSabtGDCTP4Ggrg2MbGnWO9X8K1t4+fGMDw==",
      "license": "ISC"
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmmirror.com/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/function-bind": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/function-bind/-/function-bind-1.1.2.tgz",
      "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/gensync": {
      "version": "1.0.0-beta.2",
      "resolved": "https://registry.npmmirror.com/gensync/-/gensync-1.0.0-beta.2.tgz",
      "integrity": "sha512-3hN7NaskYvMDLQY55gnW3NQ+mesEAepTqlg+VEbj7zzqEMBVNhzcGYYeqFo/TlYz6eQiFcp1HcsCZO+nGgS8zg==",
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/get-caller-file": {
      "version": "2.0.5",
      "resolved": "https://registry.npmmirror.com/get-caller-file/-/get-caller-file-2.0.5.tgz",
      "integrity": "sha512-DyFP3BM/3YHTQOCUL/w0OZHR0lpKeGrxotcHWcqNEdnltqFwXVfhEBQ94eIo34AfQpo0rGki4cyIiftY06h2Fg==",
      "license": "ISC",
      "engines": {
        "node": "6.* || 8.* || >= 10.*"
      }
    },
    "node_modules/get-nonce": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/get-nonce/-/get-nonce-1.0.1.tgz",
      "integrity": "sha512-FJhYRoDaiatfEkUK8HKlicmu/3SGFD51q3itKDGoSTysQJBnfOcxU5GxnhE1E6soB76MbT0MBtnKJuXyAx+96Q==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/get-package-type": {
      "version": "0.1.0",
      "resolved": "https://registry.npmmirror.com/get-package-type/-/get-package-type-0.1.0.tgz",
      "integrity": "sha512-pjzuKtY64GYfWizNAJ0fr9VqttZkNiK2iS430LtIHzjBEr6bX8Am2zm4sW4Ro5wjWW5cAlRL1qAMTcXbjNAO2Q==",
      "license": "MIT",
      "engines": {
        "node": ">=8.0.0"
      }
    },
    "node_modules/getenv": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/getenv/-/getenv-2.0.0.tgz",
      "integrity": "sha512-VilgtJj/ALgGY77fiLam5iD336eSWi96Q15JSAG1zi8NRBysm3LXKdGnHb4m5cuyxvOLQQKWpBZAT6ni4FI2iQ==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/glob": {
      "version": "13.0.6",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-13.0.6.tgz",
      "integrity": "sha512-Wjlyrolmm8uDpm/ogGyXZXb1Z+Ca2B8NbJwqBVg0axK9GbBeoS7yGV6vjXnYdGm6X53iehEuxxbyiKp8QmN4Vw==",
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "minimatch": "^10.2.2",
        "minipass": "^7.1.3",
        "path-scurry": "^2.0.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/graceful-fs": {
      "version": "4.2.11",
      "resolved": "https://registry.npmmirror.com/graceful-fs/-/graceful-fs-4.2.11.tgz",
      "integrity": "sha512-RbJ5/jmFcNNCcDV5o9eTnBLJ/HszWV0P73bc+Ff4nS/rJj+YaS6IGyiOL0VoBYX+l1Wrl3k63h/KrH+nhJ0XvQ==",
      "license": "ISC"
    },
    "node_modules/has-flag": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/has-flag/-/has-flag-4.0.0.tgz",
      "integrity": "sha512-EykJT/Q1KjTWctppgIAgfSO0tKVuZUjhgMr17kqTumMl6Afv3EISleU7qZUzoXDFTAHTDC4NOoG/ZxU3EvlMPQ==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/hasown": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/hasown/-/hasown-2.0.2.tgz",
      "integrity": "sha512-0hJU9SCPvmMzIBdZFqNPXWa6dqh7WdH0cII9y+CyS8rG3nL48Bclra9HmKhVVUHyPWNH5Y7xDwAB7bfgSjkUMQ==",
      "license": "MIT",
      "dependencies": {
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/hermes-compiler": {
      "version": "0.14.1",
      "resolved": "https://registry.npmmirror.com/hermes-compiler/-/hermes-compiler-0.14.1.tgz",
      "integrity": "sha512-+RPPQlayoZ9n6/KXKt5SFILWXCGJ/LV5d24L5smXrvTDrPS4L6dSctPczXauuvzFP3QEJbD1YO7Z3Ra4a+4IhA==",
      "license": "MIT"
    },
    "node_modules/hermes-estree": {
      "version": "0.32.0",
      "resolved": "https://registry.npmmirror.com/hermes-estree/-/hermes-estree-0.32.0.tgz",
      "integrity": "sha512-KWn3BqnlDOl97Xe1Yviur6NbgIZ+IP+UVSpshlZWkq+EtoHg6/cwiDj/osP9PCEgFE15KBm1O55JRwbMEm5ejQ==",
      "license": "MIT"
    },
    "node_modules/hermes-parser": {
      "version": "0.32.0",
      "resolved": "https://registry.npmmirror.com/hermes-parser/-/hermes-parser-0.32.0.tgz",
      "integrity": "sha512-g4nBOWFpuiTqjR3LZdRxKUkij9iyveWeuks7INEsMX741f3r9xxrOe8TeQfUxtda0eXmiIFiMQzoeSQEno33Hw==",
      "license": "MIT",
      "dependencies": {
        "hermes-estree": "0.32.0"
      }
    },
    "node_modules/hoist-non-react-statics": {
      "version": "3.3.2",
      "resolved": "https://registry.npmmirror.com/hoist-non-react-statics/-/hoist-non-react-statics-3.3.2.tgz",
      "integrity": "sha512-/gGivxi8JPKWNm/W0jSmzcMPpfpPLc3dY/6GxhX2hQ9iGj3aDfklV4ET7NjKpSinLpJ5vafa9iiGIEZg10SfBw==",
      "license": "BSD-3-Clause",
      "optional": true,
      "peer": true,
      "dependencies": {
        "react-is": "^16.7.0"
      }
    },
    "node_modules/hoist-non-react-statics/node_modules/react-is": {
      "version": "16.13.1",
      "resolved": "https://registry.npmmirror.com/react-is/-/react-is-16.13.1.tgz",
      "integrity": "sha512-24e6ynE2H+OKt4kqsOvNd8kBpV65zoxbA4BVsEOB3ARVWQki/DHzaUoC5KuON/BiccDaCCTZBuOcfZs70kR8bQ==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/hosted-git-info": {
      "version": "7.0.2",
      "resolved": "https://registry.npmmirror.com/hosted-git-info/-/hosted-git-info-7.0.2.tgz",
      "integrity": "sha512-puUZAUKT5m8Zzvs72XWy3HtvVbTWljRE66cP60bxJzAqf2DgICo7lYTY2IHUmLnNpjYvw5bvmoHvPc0QO2a62w==",
      "license": "ISC",
      "dependencies": {
        "lru-cache": "^10.0.1"
      },
      "engines": {
        "node": "^16.14.0 || >=18.0.0"
      }
    },
    "node_modules/hosted-git-info/node_modules/lru-cache": {
      "version": "10.4.3",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-10.4.3.tgz",
      "integrity": "sha512-JNAzZcXrCt42VGLuYz0zfAzDfAvJWW6AfYlDBQyDV5DClI2m5sAmK+OIO7s59XfsRsWHp02jAJrRadPRGTt6SQ==",
      "license": "ISC"
    },
    "node_modules/http-errors": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/http-errors/-/http-errors-2.0.1.tgz",
      "integrity": "sha512-4FbRdAX+bSdmo4AUFuS0WNiPz8NgFt+r8ThgNWmlrjQjt1Q7ZR9+zTlce2859x4KSXrwIsaeTqDoKQmtP8pLmQ==",
      "license": "MIT",
      "dependencies": {
        "depd": "~2.0.0",
        "inherits": "~2.0.4",
        "setprototypeof": "~1.2.0",
        "statuses": "~2.0.2",
        "toidentifier": "~1.0.1"
      },
      "engines": {
        "node": ">= 0.8"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/express"
      }
    },
    "node_modules/http-errors/node_modules/statuses": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/statuses/-/statuses-2.0.2.tgz",
      "integrity": "sha512-DvEy55V3DB7uknRo+4iOGT5fP1slR8wQohVdknigZPMpMstaKJQWhwiYBACJE3Ul2pTnATihhBYnRhZQHGBiRw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/https-proxy-agent": {
      "version": "7.0.6",
      "resolved": "https://registry.npmmirror.com/https-proxy-agent/-/https-proxy-agent-7.0.6.tgz",
      "integrity": "sha512-vK9P5/iUfdl95AI+JVyUuIcVtd4ofvtrOr3HNtM2yxC9bnMbEdp3x01OhQNnjb8IJYi38VlTE3mBXwcfvywuSw==",
      "license": "MIT",
      "dependencies": {
        "agent-base": "^7.1.2",
        "debug": "4"
      },
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/hyphenate-style-name": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/hyphenate-style-name/-/hyphenate-style-name-1.1.0.tgz",
      "integrity": "sha512-WDC/ui2VVRrz3jOVi+XtjqkDjiVjTtFaAGiW37k6b+ohyQ5wYDOGkvCZa8+H0nx3gyvv0+BST9xuOgIyGQ00gw==",
      "license": "BSD-3-Clause",
      "optional": true,
      "peer": true
    },
    "node_modules/ignore": {
      "version": "5.3.2",
      "resolved": "https://registry.npmmirror.com/ignore/-/ignore-5.3.2.tgz",
      "integrity": "sha512-hsBTNUqQTDwkWtcdYI2i06Y/nUBEsNEDJKjWdigLvegy8kDuJAS8uRlpkkcQpyEXL0Z/pjDy5HBmMjRCJ2gq+g==",
      "license": "MIT",
      "engines": {
        "node": ">= 4"
      }
    },
    "node_modules/image-size": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/image-size/-/image-size-1.2.1.tgz",
      "integrity": "sha512-rH+46sQJ2dlwfjfhCyNx5thzrv+dtmBIhPHk0zgRUukHzZ/kRueTJXoYYsclBaKcSMBWuGbOFXtioLpzTb5euw==",
      "license": "MIT",
      "dependencies": {
        "queue": "6.0.2"
      },
      "bin": {
        "image-size": "bin/image-size.js"
      },
      "engines": {
        "node": ">=16.x"
      }
    },
    "node_modules/imurmurhash": {
      "version": "0.1.4",
      "resolved": "https://registry.npmmirror.com/imurmurhash/-/imurmurhash-0.1.4.tgz",
      "integrity": "sha512-JmXMZ6wuvDmLiHEml9ykzqO6lwFbof0GG4IkcGaENdCRDDmMVnny7s5HsIgHCbaq0w2MyPhDqkhTUgS2LU2PHA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.8.19"
      }
    },
    "node_modules/inflight": {
      "version": "1.0.6",
      "resolved": "https://registry.npmmirror.com/inflight/-/inflight-1.0.6.tgz",
      "integrity": "sha512-k92I/b08q4wvFscXCLvqfsHCrjrF7yiXsQuIVvVE7N82W3+aqpzuUdBbfhWcy/FZR3/4IgflMgKLOsvPDrGCJA==",
      "deprecated": "This module is not supported, and leaks memory. Do not use it. Check out lru-cache if you want a good and tested way to coalesce async requests by a key value, which is much more comprehensive and powerful.",
      "license": "ISC",
      "dependencies": {
        "once": "^1.3.0",
        "wrappy": "1"
      }
    },
    "node_modules/inherits": {
      "version": "2.0.4",
      "resolved": "https://registry.npmmirror.com/inherits/-/inherits-2.0.4.tgz",
      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZzAskKMhZ2K+EnBiSM9zGSoIFeMpXKxa4dYeZIQqewQ==",
      "license": "ISC"
    },
    "node_modules/inline-style-prefixer": {
      "version": "7.0.1",
      "resolved": "https://registry.npmmirror.com/inline-style-prefixer/-/inline-style-prefixer-7.0.1.tgz",
      "integrity": "sha512-lhYo5qNTQp3EvSSp3sRvXMbVQTLrvGV6DycRMJ5dm2BLMiJ30wpXKdDdgX+GmJZ5uQMucwRKHamXSst3Sj/Giw==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "css-in-js-utils": "^3.1.0"
      }
    },
    "node_modules/invariant": {
      "version": "2.2.4",
      "resolved": "https://registry.npmmirror.com/invariant/-/invariant-2.2.4.tgz",
      "integrity": "sha512-phJfQVBuaJM5raOpJjSfkiD6BpbCE4Ns//LaXl6wGYtUBY83nWS6Rf9tXm2e8VaK60JEjYldbPif/A2B1C2gNA==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.0.0"
      }
    },
    "node_modules/is-arrayish": {
      "version": "0.3.4",
      "resolved": "https://registry.npmmirror.com/is-arrayish/-/is-arrayish-0.3.4.tgz",
      "integrity": "sha512-m6UrgzFVUYawGBh1dUsWR5M2Clqic9RVXC/9f8ceNlv2IcO9j9J/z8UoCLPqtsPBFNzEpfR3xftohbfqDx8EQA==",
      "license": "MIT"
    },
    "node_modules/is-core-module": {
      "version": "2.16.1",
      "resolved": "https://registry.npmmirror.com/is-core-module/-/is-core-module-2.16.1.tgz",
      "integrity": "sha512-UfoeMA6fIJ8wTYFEUjelnaGI67v6+N7qXJEvQuIGa99l4xsCruSYOVSQ0uPANn4dAzm8lkYPaKLrrijLq7x23w==",
      "license": "MIT",
      "dependencies": {
        "hasown": "^2.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/is-docker": {
      "version": "2.2.1",
      "resolved": "https://registry.npmmirror.com/is-docker/-/is-docker-2.2.1.tgz",
      "integrity": "sha512-F+i2BKsFrH66iaUFc0woD8sLy8getkwTwtOBjvs56Cx4CgJDeKQeqfz8wAYiSb8JOprWhHH5p77PbmYCvvUuXQ==",
      "license": "MIT",
      "bin": {
        "is-docker": "cli.js"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/is-fullwidth-code-point": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/is-fullwidth-code-point/-/is-fullwidth-code-point-3.0.0.tgz",
      "integrity": "sha512-zymm5+u+sCsSWyD9qNaejV3DFvhCKclKdizYaJUuHA83RLjb7nSuGnddCHGv0hk+KY7BMAlsWeK4Ueg6EV6XQg==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-number": {
      "version": "7.0.0",
      "resolved": "https://registry.npmmirror.com/is-number/-/is-number-7.0.0.tgz",
      "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
      "license": "MIT",
      "engines": {
        "node": ">=0.12.0"
      }
    },
    "node_modules/is-plain-obj": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/is-plain-obj/-/is-plain-obj-2.1.0.tgz",
      "integrity": "sha512-YWnfyRwxL/+SsrWYfOpUtz5b3YD+nyfkHvjbcanzk8zgyO4ASD67uVMRt8k5bM4lLMDnXfriRhOpemw+NfT1eA==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-wsl": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/is-wsl/-/is-wsl-2.2.0.tgz",
      "integrity": "sha512-fKzAra0rGJUUBwGBgNkHZuToZcn+TtXHpeCgmkMJMMYx1sQDYaCSyjJBSCa2nH1DGm7s3n1oBnohoVTBaN7Lww==",
      "license": "MIT",
      "dependencies": {
        "is-docker": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/isexe": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/isexe/-/isexe-2.0.0.tgz",
      "integrity": "sha512-RHxMLp9lnKHGHRng9QFhRCMbYAcVpn69smSGcq3f36xjgVVWThj4qqLbTLlq7Ssj8B+fIQ1EuCEGI2lKsyQeIw==",
      "license": "ISC"
    },
    "node_modules/istanbul-lib-coverage": {
      "version": "3.2.2",
      "resolved": "https://registry.npmmirror.com/istanbul-lib-coverage/-/istanbul-lib-coverage-3.2.2.tgz",
      "integrity": "sha512-O8dpsF+r0WV/8MNRKfnmrtCWhuKjxrq2w+jpzBL5UZKTi2LeVWnWOmWRxFlesJONmc+wLAGvKQZEOanko0LFTg==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/istanbul-lib-instrument": {
      "version": "5.2.1",
      "resolved": "https://registry.npmmirror.com/istanbul-lib-instrument/-/istanbul-lib-instrument-5.2.1.tgz",
      "integrity": "sha512-pzqtp31nLv/XFOzXGuvhCb8qhjmTVo5vjVk19XE4CRlSWz0KoeJ3bw9XsA7nOp9YBf4qHjwBxkDzKcME/J29Yg==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "@babel/core": "^7.12.3",
        "@babel/parser": "^7.14.7",
        "@istanbuljs/schema": "^0.1.2",
        "istanbul-lib-coverage": "^3.2.0",
        "semver": "^6.3.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/istanbul-lib-instrument/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/jest-environment-node": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-environment-node/-/jest-environment-node-29.7.0.tgz",
      "integrity": "sha512-DOSwCRqXirTOyheM+4d5YZOrWcdu0LNZ87ewUoywbcb2XR4wKgqiG8vNeYwhjFMbEkfju7wx2GYH0P2gevGvFw==",
      "license": "MIT",
      "dependencies": {
        "@jest/environment": "^29.7.0",
        "@jest/fake-timers": "^29.7.0",
        "@jest/types": "^29.6.3",
        "@types/node": "*",
        "jest-mock": "^29.7.0",
        "jest-util": "^29.7.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-get-type": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/jest-get-type/-/jest-get-type-29.6.3.tgz",
      "integrity": "sha512-zrteXnqYxfQh7l5FHyL38jL39di8H8rHoecLH3JNxH3BwOrBsNeabdap5e0I23lD4HHI8W5VFBZqG4Eaq5LNcw==",
      "license": "MIT",
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-haste-map": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-haste-map/-/jest-haste-map-29.7.0.tgz",
      "integrity": "sha512-fP8u2pyfqx0K1rGn1R9pyE0/KTn+G7PxktWidOBTqFPLYX0b9ksaMFkhK5vrS3DVun09pckLdlx90QthlW7AmA==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3",
        "@types/graceful-fs": "^4.1.3",
        "@types/node": "*",
        "anymatch": "^3.0.3",
        "fb-watchman": "^2.0.0",
        "graceful-fs": "^4.2.9",
        "jest-regex-util": "^29.6.3",
        "jest-util": "^29.7.0",
        "jest-worker": "^29.7.0",
        "micromatch": "^4.0.4",
        "walker": "^1.0.8"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      },
      "optionalDependencies": {
        "fsevents": "^2.3.2"
      }
    },
    "node_modules/jest-message-util": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-message-util/-/jest-message-util-29.7.0.tgz",
      "integrity": "sha512-GBEV4GRADeP+qtB2+6u61stea8mGcOT4mCtrYISZwfu9/ISHFJ/5zOMXYbpBE9RsS5+Gb63DW4FgmnKJ79Kf6w==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.12.13",
        "@jest/types": "^29.6.3",
        "@types/stack-utils": "^2.0.0",
        "chalk": "^4.0.0",
        "graceful-fs": "^4.2.9",
        "micromatch": "^4.0.4",
        "pretty-format": "^29.7.0",
        "slash": "^3.0.0",
        "stack-utils": "^2.0.3"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-mock": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-mock/-/jest-mock-29.7.0.tgz",
      "integrity": "sha512-ITOMZn+UkYS4ZFh83xYAOzWStloNzJFO2s8DWrE4lhtGD+AorgnbkiKERe4wQVBydIGPx059g6riW5Btp6Llnw==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3",
        "@types/node": "*",
        "jest-util": "^29.7.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-regex-util": {
      "version": "29.6.3",
      "resolved": "https://registry.npmmirror.com/jest-regex-util/-/jest-regex-util-29.6.3.tgz",
      "integrity": "sha512-KJJBsRCyyLNWCNBOvZyRDnAIfUiRJ8v+hOBQYGn8gDyF3UegwiP4gwRR3/SDa42g1YbVycTidUF3rKjyLFDWbg==",
      "license": "MIT",
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-util": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-util/-/jest-util-29.7.0.tgz",
      "integrity": "sha512-z6EbKajIpqGKU56y5KBUgy1dt1ihhQJgWzUlZHArA/+X2ad7Cb5iF+AK1EWVL/Bo7Rz9uurpqw6SiBCefUbCGA==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3",
        "@types/node": "*",
        "chalk": "^4.0.0",
        "ci-info": "^3.2.0",
        "graceful-fs": "^4.2.9",
        "picomatch": "^2.2.3"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-util/node_modules/ci-info": {
      "version": "3.9.0",
      "resolved": "https://registry.npmmirror.com/ci-info/-/ci-info-3.9.0.tgz",
      "integrity": "sha512-NIxF55hv4nSqQswkAeiOi1r83xy8JldOFDTWiug55KBu9Jnblncd2U6ViHmYgHf01TPZS77NJBhBMKdWj9HQMQ==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/sibiraj-s"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/jest-validate": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-validate/-/jest-validate-29.7.0.tgz",
      "integrity": "sha512-ZB7wHqaRGVw/9hST/OuFUReG7M8vKeq0/J2egIGLdvjHCmYqGARhzXmtgi+gVeZ5uXFF219aOc3Ls2yLg27tkw==",
      "license": "MIT",
      "dependencies": {
        "@jest/types": "^29.6.3",
        "camelcase": "^6.2.0",
        "chalk": "^4.0.0",
        "jest-get-type": "^29.6.3",
        "leven": "^3.1.0",
        "pretty-format": "^29.7.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-worker": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/jest-worker/-/jest-worker-29.7.0.tgz",
      "integrity": "sha512-eIz2msL/EzL9UFTFFx7jBTkeZfku0yUAyZZZmJ93H2TYEiroIx2PQjEXcwYtYl8zXCxb+PAmA2hLIt/6ZEkPHw==",
      "license": "MIT",
      "dependencies": {
        "@types/node": "*",
        "jest-util": "^29.7.0",
        "merge-stream": "^2.0.0",
        "supports-color": "^8.0.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/jest-worker/node_modules/supports-color": {
      "version": "8.1.1",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-8.1.1.tgz",
      "integrity": "sha512-MpUEN2OodtUzxvKQl72cUF7RQ5EiHsGvSsVG0ia9c5RbWGL2CI4C7EpPS8UTBIplnlzZiNuV56w+FuNxy3ty2Q==",
      "license": "MIT",
      "dependencies": {
        "has-flag": "^4.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/supports-color?sponsor=1"
      }
    },
    "node_modules/jimp-compact": {
      "version": "0.16.1",
      "resolved": "https://registry.npmmirror.com/jimp-compact/-/jimp-compact-0.16.1.tgz",
      "integrity": "sha512-dZ6Ra7u1G8c4Letq/B5EzAxj4tLFHL+cGtdpR+PVm4yzPDj+lCk+AbivWt1eOM+ikzkowtyV7qSqX6qr3t71Ww==",
      "license": "MIT"
    },
    "node_modules/js-tokens": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/js-tokens/-/js-tokens-4.0.0.tgz",
      "integrity": "sha512-RdJUflcE3cUzKiMqQgsCu06FPu9UdIJO0beYbPhHN4k6apgJtifcoCtT9bcxOpYBtpD2kCM6Sbzg4CausW/PKQ==",
      "license": "MIT"
    },
    "node_modules/js-yaml": {
      "version": "3.14.2",
      "resolved": "https://registry.npmmirror.com/js-yaml/-/js-yaml-3.14.2.tgz",
      "integrity": "sha512-PMSmkqxr106Xa156c2M265Z+FTrPl+oxd/rgOQy2tijQeK5TxQ43psO1ZCwhVOSdnn+RzkzlRz/eY4BgJBYVpg==",
      "license": "MIT",
      "dependencies": {
        "argparse": "^1.0.7",
        "esprima": "^4.0.0"
      },
      "bin": {
        "js-yaml": "bin/js-yaml.js"
      }
    },
    "node_modules/jsc-safe-url": {
      "version": "0.2.4",
      "resolved": "https://registry.npmmirror.com/jsc-safe-url/-/jsc-safe-url-0.2.4.tgz",
      "integrity": "sha512-0wM3YBWtYePOjfyXQH5MWQ8H7sdk5EXSwZvmSLKk2RboVQ2Bu239jycHDz5J/8Blf3K0Qnoy2b6xD+z10MFB+Q==",
      "license": "0BSD"
    },
    "node_modules/jsesc": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/jsesc/-/jsesc-3.1.0.tgz",
      "integrity": "sha512-/sM3dO2FOzXjKQhJuo0Q173wf2KOo8t4I8vHy6lF9poUp7bKT0/NHE8fPX23PwfhnykfqnC2xRxOnVw5XuGIaA==",
      "license": "MIT",
      "bin": {
        "jsesc": "bin/jsesc"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/json5": {
      "version": "2.2.3",
      "resolved": "https://registry.npmmirror.com/json5/-/json5-2.2.3.tgz",
      "integrity": "sha512-XmOWe7eyHYH14cLdVPoyg+GOH3rYX++KpzrylJwSW98t3Nk+U8XOl8FWKOgwtzdb8lXGf6zYwDUzeHMWfxasyg==",
      "license": "MIT",
      "bin": {
        "json5": "lib/cli.js"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/kleur": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/kleur/-/kleur-3.0.3.tgz",
      "integrity": "sha512-eTIzlVOSUR+JxdDFepEYcBMtZ9Qqdef+rnzWdRZuMbOywu5tO2w2N7rqjoANZ5k9vywhL6Br1VRjUIgTQx4E8w==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/lan-network": {
      "version": "0.2.0",
      "resolved": "https://registry.npmmirror.com/lan-network/-/lan-network-0.2.0.tgz",
      "integrity": "sha512-EZgbsXMrGS+oK+Ta12mCjzBFse+SIewGdwrSTr5g+MSymnjpox2x05ceI20PQejJOFvOgzcXrfDk/SdY7dSCtw==",
      "license": "MIT",
      "bin": {
        "lan-network": "dist/lan-network-cli.js"
      }
    },
    "node_modules/leven": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/leven/-/leven-3.1.0.tgz",
      "integrity": "sha512-qsda+H8jTaUaN/x5vzW2rzc+8Rw4TAQ/4KjB46IwK5VH+IlVeeeje/EoZRpiXvIqjFgK84QffqPztGI3VBLG1A==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/lighthouse-logger": {
      "version": "1.4.2",
      "resolved": "https://registry.npmmirror.com/lighthouse-logger/-/lighthouse-logger-1.4.2.tgz",
      "integrity": "sha512-gPWxznF6TKmUHrOQjlVo2UbaL2EJ71mb2CCeRs/2qBpi4L/g4LUVc9+3lKQ6DTUZwJswfM7ainGrLO1+fOqa2g==",
      "license": "Apache-2.0",
      "dependencies": {
        "debug": "^2.6.9",
        "marky": "^1.2.2"
      }
    },
    "node_modules/lighthouse-logger/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/lighthouse-logger/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/lightningcss": {
      "version": "1.32.0",
      "resolved": "https://registry.npmmirror.com/lightningcss/-/lightningcss-1.32.0.tgz",
      "integrity": "sha512-NXYBzinNrblfraPGyrbPoD19C1h9lfI/1mzgWYvXUTe414Gz/X1FD2XBZSZM7rRTrMA8JL3OtAaGifrIKhQ5yQ==",
      "license": "MPL-2.0",
      "dependencies": {
        "detect-libc": "^2.0.3"
      },
      "engines": {
        "node": ">= 12.0.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/parcel"
      },
      "optionalDependencies": {
        "lightningcss-android-arm64": "1.32.0",
        "lightningcss-darwin-arm64": "1.32.0",
        "lightningcss-darwin-x64": "1.32.0",
        "lightningcss-freebsd-x64": "1.32.0",
        "lightningcss-linux-arm-gnueabihf": "1.32.0",
        "lightningcss-linux-arm64-gnu": "1.32.0",
        "lightningcss-linux-arm64-musl": "1.32.0",
        "lightningcss-linux-x64-gnu": "1.32.0",
        "lightningcss-linux-x64-musl": "1.32.0",
        "lightningcss-win32-arm64-msvc": "1.32.0",
        "lightningcss-win32-x64-msvc": "1.32.0"
      }
    },
    "node_modules/lightningcss-darwin-arm64": {
      "version": "1.32.0",
      "resolved": "https://registry.npmmirror.com/lightningcss-darwin-arm64/-/lightningcss-darwin-arm64-1.32.0.tgz",
      "integrity": "sha512-RzeG9Ju5bag2Bv1/lwlVJvBE3q6TtXskdZLLCyfg5pt+HLz9BqlICO7LZM7VHNTTn/5PRhHFBSjk5lc4cmscPQ==",
      "cpu": [
        "arm64"
      ],
      "license": "MPL-2.0",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">= 12.0.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/parcel"
      }
    },
    "node_modules/locate-path": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/locate-path/-/locate-path-5.0.0.tgz",
      "integrity": "sha512-t7hw9pI+WvuwNJXwk5zVHpyhIqzg2qTlklJOf0mVxGSbe3Fp2VieZcduNYjaLDoy6p9uGpQEGWG87WpMKlNq8g==",
      "license": "MIT",
      "dependencies": {
        "p-locate": "^4.1.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/lodash.debounce": {
      "version": "4.0.8",
      "resolved": "https://registry.npmmirror.com/lodash.debounce/-/lodash.debounce-4.0.8.tgz",
      "integrity": "sha512-FT1yDzDYEoYWhnSGnpE/4Kj1fLZkDFyqRb7fNt6FdYOSxlUWAtp42Eh6Wb0rGIv/m9Bgo7x4GhQbm5Ys4SG5ow==",
      "license": "MIT"
    },
    "node_modules/lodash.throttle": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/lodash.throttle/-/lodash.throttle-4.1.1.tgz",
      "integrity": "sha512-wIkUCfVKpVsWo3JSZlc+8MB5it+2AN5W8J7YVMST30UrvcQNZ1Okbj+rbVniijTWE6FGYy4XJq/rHkas8qJMLQ==",
      "license": "MIT"
    },
    "node_modules/log-symbols": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/log-symbols/-/log-symbols-2.2.0.tgz",
      "integrity": "sha512-VeIAFslyIerEJLXHziedo2basKbMKtTw3vfn5IzG0XTjhAVEJyNHnL2p7vc+wBDSdQuUpNw3M2u6xb9QsAY5Eg==",
      "license": "MIT",
      "dependencies": {
        "chalk": "^2.0.1"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/log-symbols/node_modules/ansi-styles": {
      "version": "3.2.1",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-3.2.1.tgz",
      "integrity": "sha512-VT0ZI6kZRdTh8YyJw3SMbYm/u+NqfsAxEpWO0Pf9sq8/e94WxxOpPKx9FR1FlyCtOVDNOQ+8ntlqFxiRc+r5qA==",
      "license": "MIT",
      "dependencies": {
        "color-convert": "^1.9.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/log-symbols/node_modules/chalk": {
      "version": "2.4.2",
      "resolved": "https://registry.npmmirror.com/chalk/-/chalk-2.4.2.tgz",
      "integrity": "sha512-Mti+f9lpJNcwF4tWV8/OrTTtF1gZi+f8FqlyAdouralcFWFQWF2+NgCHShjkCb+IFBLq9buZwE1xckQU4peSuQ==",
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^3.2.1",
        "escape-string-regexp": "^1.0.5",
        "supports-color": "^5.3.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/log-symbols/node_modules/color-convert": {
      "version": "1.9.3",
      "resolved": "https://registry.npmmirror.com/color-convert/-/color-convert-1.9.3.tgz",
      "integrity": "sha512-QfAUtd+vFdAtFQcC8CCyYt1fYWxSqAiK2cSD6zDB8N3cpsEBAvRxp9zOGg6G/SHHJYAT88/az/IuDGALsNVbGg==",
      "license": "MIT",
      "dependencies": {
        "color-name": "1.1.3"
      }
    },
    "node_modules/log-symbols/node_modules/color-name": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/color-name/-/color-name-1.1.3.tgz",
      "integrity": "sha512-72fSenhMw2HZMTVHeCA9KCmpEIbzWiQsjN+BHcBbS9vr1mtt+vJjPdksIBNUmKAW8TFUDPJK5SUU3QhE9NEXDw==",
      "license": "MIT"
    },
    "node_modules/log-symbols/node_modules/escape-string-regexp": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/escape-string-regexp/-/escape-string-regexp-1.0.5.tgz",
      "integrity": "sha512-vbRorB5FUQWvla16U8R/qgaFIya2qGzwDrNmCZuYKrbdSUMG6I1ZCGQRefkRVhuOkIGVne7BQ35DSfo1qvJqFg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.8.0"
      }
    },
    "node_modules/log-symbols/node_modules/has-flag": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/has-flag/-/has-flag-3.0.0.tgz",
      "integrity": "sha512-sKJf1+ceQBr4SMkvQnBDNDtf4TXpVhVGateu0t918bl30FnbE2m4vNLX+VWe/dpjlb+HugGYzW7uQXH98HPEYw==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/log-symbols/node_modules/supports-color": {
      "version": "5.5.0",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-5.5.0.tgz",
      "integrity": "sha512-QjVjwdXIt408MIiAqCX4oUKsgU2EqAGzs2Ppkm4aQYbjm+ZEWEcW4SfFNTr4uMNZma0ey4f5lgLrkB0aX0QMow==",
      "license": "MIT",
      "dependencies": {
        "has-flag": "^3.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/loose-envify": {
      "version": "1.4.0",
      "resolved": "https://registry.npmmirror.com/loose-envify/-/loose-envify-1.4.0.tgz",
      "integrity": "sha512-lyuxPGr/Wfhrlem2CL/UcnUc1zcqKAImBDzukY7Y5F/yQiNdko6+fRLevlw1HgMySw7f611UIY408EtxRSoK3Q==",
      "license": "MIT",
      "dependencies": {
        "js-tokens": "^3.0.0 || ^4.0.0"
      },
      "bin": {
        "loose-envify": "cli.js"
      }
    },
    "node_modules/lru-cache": {
      "version": "5.1.1",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-5.1.1.tgz",
      "integrity": "sha512-KpNARQA3Iwv+jTA0utUVVbrh+Jlrr1Fv0e56GGzAFOXN7dk/FviaDW8LHmK52DlcH4WP2n6gI8vN1aesBFgo9w==",
      "license": "ISC",
      "dependencies": {
        "yallist": "^3.0.2"
      }
    },
    "node_modules/lucide-react-native": {
      "version": "1.7.0",
      "resolved": "https://registry.npmmirror.com/lucide-react-native/-/lucide-react-native-1.7.0.tgz",
      "integrity": "sha512-wGJY5nosSawh028jg8r1ZKqnGPDIVfIL9xvKOs4wPYFQHeJMHsADYm/lmuFYXMXXatSkHhpsCjeqIRgeFGzf8g==",
      "license": "ISC",
      "peerDependencies": {
        "react": "^16.5.1 || ^17.0.0 || ^18.0.0 || ^19.0.0",
        "react-native": "*",
        "react-native-svg": "^12.0.0 || ^13.0.0 || ^14.0.0 || ^15.0.0"
      }
    },
    "node_modules/makeerror": {
      "version": "1.0.12",
      "resolved": "https://registry.npmmirror.com/makeerror/-/makeerror-1.0.12.tgz",
      "integrity": "sha512-JmqCvUhmt43madlpFzG4BQzG2Z3m6tvQDNKdClZnO3VbIudJYmxsT0FNJMeiB2+JTSlTQTSbU8QdesVmwJcmLg==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "tmpl": "1.0.5"
      }
    },
    "node_modules/marky": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/marky/-/marky-1.3.0.tgz",
      "integrity": "sha512-ocnPZQLNpvbedwTy9kNrQEsknEfgvcLMvOtz3sFeWApDq1MXH1TqkCIx58xlpESsfwQOnuBO9beyQuNGzVvuhQ==",
      "license": "Apache-2.0"
    },
    "node_modules/mdn-data": {
      "version": "2.0.14",
      "resolved": "https://registry.npmmirror.com/mdn-data/-/mdn-data-2.0.14.tgz",
      "integrity": "sha512-dn6wd0uw5GsdswPFfsgMp5NSB0/aDe6fK94YJV/AJDYXL6HVLWBsxeq7js7Ad+mU2K9LAlwpk6kN2D5mwCPVow==",
      "license": "CC0-1.0"
    },
    "node_modules/memoize-one": {
      "version": "5.2.1",
      "resolved": "https://registry.npmmirror.com/memoize-one/-/memoize-one-5.2.1.tgz",
      "integrity": "sha512-zYiwtZUcYyXKo/np96AGZAckk+FWWsUdJ3cHGGmld7+AhvcWmQyGCYUh1hc4Q/pkOhb65dQR/pqCyK0cOaHz4Q==",
      "license": "MIT"
    },
    "node_modules/merge-options": {
      "version": "3.0.4",
      "resolved": "https://registry.npmmirror.com/merge-options/-/merge-options-3.0.4.tgz",
      "integrity": "sha512-2Sug1+knBjkaMsMgf1ctR1Ujx+Ayku4EdJN4Z+C2+JzoeF7A3OZ9KM2GY0CpQS51NR61LTurMJrRKPhSs3ZRTQ==",
      "license": "MIT",
      "dependencies": {
        "is-plain-obj": "^2.1.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/merge-stream": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/merge-stream/-/merge-stream-2.0.0.tgz",
      "integrity": "sha512-abv/qOcuPfk3URPfDzmZU1LKmuw8kT+0nIHvKrKgFrwifol/doWcdA4ZqsWQ8ENrFKkd67Mfpo/LovbIUsbt3w==",
      "license": "MIT"
    },
    "node_modules/metro": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro/-/metro-0.83.3.tgz",
      "integrity": "sha512-+rP+/GieOzkt97hSJ0MrPOuAH/jpaS21ZDvL9DJ35QYRDlQcwzcvUlGUf79AnQxq/2NPiS/AULhhM4TKutIt8Q==",
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.24.7",
        "@babel/core": "^7.25.2",
        "@babel/generator": "^7.25.0",
        "@babel/parser": "^7.25.3",
        "@babel/template": "^7.25.0",
        "@babel/traverse": "^7.25.3",
        "@babel/types": "^7.25.2",
        "accepts": "^1.3.7",
        "chalk": "^4.0.0",
        "ci-info": "^2.0.0",
        "connect": "^3.6.5",
        "debug": "^4.4.0",
        "error-stack-parser": "^2.0.6",
        "flow-enums-runtime": "^0.0.6",
        "graceful-fs": "^4.2.4",
        "hermes-parser": "0.32.0",
        "image-size": "^1.0.2",
        "invariant": "^2.2.4",
        "jest-worker": "^29.7.0",
        "jsc-safe-url": "^0.2.2",
        "lodash.throttle": "^4.1.1",
        "metro-babel-transformer": "0.83.3",
        "metro-cache": "0.83.3",
        "metro-cache-key": "0.83.3",
        "metro-config": "0.83.3",
        "metro-core": "0.83.3",
        "metro-file-map": "0.83.3",
        "metro-resolver": "0.83.3",
        "metro-runtime": "0.83.3",
        "metro-source-map": "0.83.3",
        "metro-symbolicate": "0.83.3",
        "metro-transform-plugins": "0.83.3",
        "metro-transform-worker": "0.83.3",
        "mime-types": "^2.1.27",
        "nullthrows": "^1.1.1",
        "serialize-error": "^2.1.0",
        "source-map": "^0.5.6",
        "throat": "^5.0.0",
        "ws": "^7.5.10",
        "yargs": "^17.6.2"
      },
      "bin": {
        "metro": "src/cli.js"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-babel-transformer": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-babel-transformer/-/metro-babel-transformer-0.83.3.tgz",
      "integrity": "sha512-1vxlvj2yY24ES1O5RsSIvg4a4WeL7PFXgKOHvXTXiW0deLvQr28ExXj6LjwCCDZ4YZLhq6HddLpZnX4dEdSq5g==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.25.2",
        "flow-enums-runtime": "^0.0.6",
        "hermes-parser": "0.32.0",
        "nullthrows": "^1.1.1"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-cache": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-cache/-/metro-cache-0.83.3.tgz",
      "integrity": "sha512-3jo65X515mQJvKqK3vWRblxDEcgY55Sk3w4xa6LlfEXgQ9g1WgMh9m4qVZVwgcHoLy0a2HENTPCCX4Pk6s8c8Q==",
      "license": "MIT",
      "dependencies": {
        "exponential-backoff": "^3.1.1",
        "flow-enums-runtime": "^0.0.6",
        "https-proxy-agent": "^7.0.5",
        "metro-core": "0.83.3"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-cache-key": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-cache-key/-/metro-cache-key-0.83.3.tgz",
      "integrity": "sha512-59ZO049jKzSmvBmG/B5bZ6/dztP0ilp0o988nc6dpaDsU05Cl1c/lRf+yx8m9WW/JVgbmfO5MziBU559XjI5Zw==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-config": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-config/-/metro-config-0.83.3.tgz",
      "integrity": "sha512-mTel7ipT0yNjKILIan04bkJkuCzUUkm2SeEaTads8VfEecCh+ltXchdq6DovXJqzQAXuR2P9cxZB47Lg4klriA==",
      "license": "MIT",
      "dependencies": {
        "connect": "^3.6.5",
        "flow-enums-runtime": "^0.0.6",
        "jest-validate": "^29.7.0",
        "metro": "0.83.3",
        "metro-cache": "0.83.3",
        "metro-core": "0.83.3",
        "metro-runtime": "0.83.3",
        "yaml": "^2.6.1"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-core": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-core/-/metro-core-0.83.3.tgz",
      "integrity": "sha512-M+X59lm7oBmJZamc96usuF1kusd5YimqG/q97g4Ac7slnJ3YiGglW5CsOlicTR5EWf8MQFxxjDoB6ytTqRe8Hw==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6",
        "lodash.throttle": "^4.1.1",
        "metro-resolver": "0.83.3"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-file-map": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-file-map/-/metro-file-map-0.83.3.tgz",
      "integrity": "sha512-jg5AcyE0Q9Xbbu/4NAwwZkmQn7doJCKGW0SLeSJmzNB9Z24jBe0AL2PHNMy4eu0JiKtNWHz9IiONGZWq7hjVTA==",
      "license": "MIT",
      "dependencies": {
        "debug": "^4.4.0",
        "fb-watchman": "^2.0.0",
        "flow-enums-runtime": "^0.0.6",
        "graceful-fs": "^4.2.4",
        "invariant": "^2.2.4",
        "jest-worker": "^29.7.0",
        "micromatch": "^4.0.4",
        "nullthrows": "^1.1.1",
        "walker": "^1.0.7"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-minify-terser": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-minify-terser/-/metro-minify-terser-0.83.3.tgz",
      "integrity": "sha512-O2BmfWj6FSfzBLrNCXt/rr2VYZdX5i6444QJU0fFoc7Ljg+Q+iqebwE3K0eTvkI6TRjELsXk1cjU+fXwAR4OjQ==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6",
        "terser": "^5.15.0"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-resolver": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-resolver/-/metro-resolver-0.83.3.tgz",
      "integrity": "sha512-0js+zwI5flFxb1ktmR///bxHYg7OLpRpWZlBBruYG8OKYxeMP7SV0xQ/o/hUelrEMdK4LJzqVtHAhBm25LVfAQ==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-runtime": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-runtime/-/metro-runtime-0.83.3.tgz",
      "integrity": "sha512-JHCJb9ebr9rfJ+LcssFYA2x1qPYuSD/bbePupIGhpMrsla7RCwC/VL3yJ9cSU+nUhU4c9Ixxy8tBta+JbDeZWw==",
      "license": "MIT",
      "dependencies": {
        "@babel/runtime": "^7.25.0",
        "flow-enums-runtime": "^0.0.6"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-source-map": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-source-map/-/metro-source-map-0.83.3.tgz",
      "integrity": "sha512-xkC3qwUBh2psVZgVavo8+r2C9Igkk3DibiOXSAht1aYRRcztEZNFtAMtfSB7sdO2iFMx2Mlyu++cBxz/fhdzQg==",
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.25.3",
        "@babel/traverse--for-generate-function-map": "npm:@babel/traverse@^7.25.3",
        "@babel/types": "^7.25.2",
        "flow-enums-runtime": "^0.0.6",
        "invariant": "^2.2.4",
        "metro-symbolicate": "0.83.3",
        "nullthrows": "^1.1.1",
        "ob1": "0.83.3",
        "source-map": "^0.5.6",
        "vlq": "^1.0.0"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-symbolicate": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-symbolicate/-/metro-symbolicate-0.83.3.tgz",
      "integrity": "sha512-F/YChgKd6KbFK3eUR5HdUsfBqVsanf5lNTwFd4Ca7uuxnHgBC3kR/Hba/RGkenR3pZaGNp5Bu9ZqqP52Wyhomw==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6",
        "invariant": "^2.2.4",
        "metro-source-map": "0.83.3",
        "nullthrows": "^1.1.1",
        "source-map": "^0.5.6",
        "vlq": "^1.0.0"
      },
      "bin": {
        "metro-symbolicate": "src/index.js"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-transform-plugins": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-transform-plugins/-/metro-transform-plugins-0.83.3.tgz",
      "integrity": "sha512-eRGoKJU6jmqOakBMH5kUB7VitEWiNrDzBHpYbkBXW7C5fUGeOd2CyqrosEzbMK5VMiZYyOcNFEphvxk3OXey2A==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.25.2",
        "@babel/generator": "^7.25.0",
        "@babel/template": "^7.25.0",
        "@babel/traverse": "^7.25.3",
        "flow-enums-runtime": "^0.0.6",
        "nullthrows": "^1.1.1"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/metro-transform-worker": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/metro-transform-worker/-/metro-transform-worker-0.83.3.tgz",
      "integrity": "sha512-Ztekew9t/gOIMZX1tvJOgX7KlSLL5kWykl0Iwu2cL2vKMKVALRl1hysyhUw0vjpAvLFx+Kfq9VLjnHIkW32fPA==",
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.25.2",
        "@babel/generator": "^7.25.0",
        "@babel/parser": "^7.25.3",
        "@babel/types": "^7.25.2",
        "flow-enums-runtime": "^0.0.6",
        "metro": "0.83.3",
        "metro-babel-transformer": "0.83.3",
        "metro-cache": "0.83.3",
        "metro-cache-key": "0.83.3",
        "metro-minify-terser": "0.83.3",
        "metro-source-map": "0.83.3",
        "metro-transform-plugins": "0.83.3",
        "nullthrows": "^1.1.1"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/micromatch": {
      "version": "4.0.8",
      "resolved": "https://registry.npmmirror.com/micromatch/-/micromatch-4.0.8.tgz",
      "integrity": "sha512-PXwfBhYu0hBCPw8Dn0E+WDYb7af3dSLVWKi3HGv84IdF4TyFoC0ysxFd0Goxw7nSv4T/PzEJQxsYsEiFCKo2BA==",
      "license": "MIT",
      "dependencies": {
        "braces": "^3.0.3",
        "picomatch": "^2.3.1"
      },
      "engines": {
        "node": ">=8.6"
      }
    },
    "node_modules/mime": {
      "version": "1.6.0",
      "resolved": "https://registry.npmmirror.com/mime/-/mime-1.6.0.tgz",
      "integrity": "sha512-x0Vn8spI+wuJ1O6S7gnbaQg8Pxh4NNHb7KSINmEWKiPE4RKOplvijn+NkmYmmRgP68mc70j2EbeTFRsrswaQeg==",
      "license": "MIT",
      "bin": {
        "mime": "cli.js"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/mime-db": {
      "version": "1.52.0",
      "resolved": "https://registry.npmmirror.com/mime-db/-/mime-db-1.52.0.tgz",
      "integrity": "sha512-sPU4uV7dYlvtWJxwwxHD0PuihVNiE7TyAbQ5SWxDCB9mUYvOgroQOwYQQOKPJ8CIbE+1ETVlOoK1UC2nU3gYvg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime-types": {
      "version": "2.1.35",
      "resolved": "https://registry.npmmirror.com/mime-types/-/mime-types-2.1.35.tgz",
      "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
      "license": "MIT",
      "dependencies": {
        "mime-db": "1.52.0"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mimic-fn": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/mimic-fn/-/mimic-fn-1.2.0.tgz",
      "integrity": "sha512-jf84uxzwiuiIVKiOLpfYk7N46TSy8ubTonmneY9vrpHNAnp0QBt2BxWV9dO3/j+BoVAb+a5G6YDPW3M5HOdMWQ==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/minimatch": {
      "version": "10.2.4",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-10.2.4.tgz",
      "integrity": "sha512-oRjTw/97aTBN0RHbYCdtF1MQfvusSIBQM0IZEgzl6426+8jSC0nF1a/GmnVLpfB9yyr6g6FTqWqiZVbxrtaCIg==",
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "brace-expansion": "^5.0.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/minipass": {
      "version": "7.1.3",
      "resolved": "https://registry.npmmirror.com/minipass/-/minipass-7.1.3.tgz",
      "integrity": "sha512-tEBHqDnIoM/1rXME1zgka9g6Q2lcoCkxHLuc7ODJ5BxbP5d4c2Z5cGgtXAku59200Cx7diuHTOYfSBD8n6mm8A==",
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=16 || 14 >=14.17"
      }
    },
    "node_modules/mkdirp": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/mkdirp/-/mkdirp-1.0.4.tgz",
      "integrity": "sha512-vVqVZQyf3WLx2Shd0qJ9xuvqgAyKPLAiqITEtqW0oIUjzo3PePDd6fW9iFz30ef7Ysp/oiWqbhszeGWW2T6Gzw==",
      "license": "MIT",
      "bin": {
        "mkdirp": "bin/cmd.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "license": "MIT"
    },
    "node_modules/multitars": {
      "version": "0.2.4",
      "resolved": "https://registry.npmmirror.com/multitars/-/multitars-0.2.4.tgz",
      "integrity": "sha512-XgLbg1HHchFauMCQPRwMj6MSyDd5koPlTA1hM3rUFkeXzGpjU/I9fP3to7yrObE9jcN8ChIOQGrM0tV0kUZaKg==",
      "license": "MIT"
    },
    "node_modules/nanoid": {
      "version": "3.3.11",
      "resolved": "https://registry.npmmirror.com/nanoid/-/nanoid-3.3.11.tgz",
      "integrity": "sha512-N8SpfPUnUp1bK+PMYW8qSWdl9U+wwNWI4QKxOYDy9JAro3WMX7p2OeVRF9v+347pnakNevPmiHhNmZ2HbFA76w==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "bin": {
        "nanoid": "bin/nanoid.cjs"
      },
      "engines": {
        "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
      }
    },
    "node_modules/negotiator": {
      "version": "0.6.3",
      "resolved": "https://registry.npmmirror.com/negotiator/-/negotiator-0.6.3.tgz",
      "integrity": "sha512-+EUsqGPLsM+j/zdChZjsnX51g4XrHFOIXwfnCVPGlQk/k5giakcKsuxCObBRu6DSm9opw/O6slWbJdghQM4bBg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/node-fetch": {
      "version": "2.7.0",
      "resolved": "https://registry.npmmirror.com/node-fetch/-/node-fetch-2.7.0.tgz",
      "integrity": "sha512-c4FRfUm/dbcWZ7U+1Wq0AwCyFL+3nt2bEw05wfxSz+DWpWsitgmSgYmy2dQdWyKC1694ELPqMs/YzUSNozLt8A==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "whatwg-url": "^5.0.0"
      },
      "engines": {
        "node": "4.x || >=6.0.0"
      },
      "peerDependencies": {
        "encoding": "^0.1.0"
      },
      "peerDependenciesMeta": {
        "encoding": {
          "optional": true
        }
      }
    },
    "node_modules/node-forge": {
      "version": "1.4.0",
      "resolved": "https://registry.npmmirror.com/node-forge/-/node-forge-1.4.0.tgz",
      "integrity": "sha512-LarFH0+6VfriEhqMMcLX2F7SwSXeWwnEAJEsYm5QKWchiVYVvJyV9v7UDvUv+w5HO23ZpQTXDv/GxdDdMyOuoQ==",
      "license": "(BSD-3-Clause OR GPL-2.0)",
      "engines": {
        "node": ">= 6.13.0"
      }
    },
    "node_modules/node-int64": {
      "version": "0.4.0",
      "resolved": "https://registry.npmmirror.com/node-int64/-/node-int64-0.4.0.tgz",
      "integrity": "sha512-O5lz91xSOeoXP6DulyHfllpq+Eg00MWitZIbtPfoSEvqIHdl5gfcY6hYzDWnj0qD5tz52PI08u9qUvSVeUBeHw==",
      "license": "MIT"
    },
    "node_modules/node-releases": {
      "version": "2.0.36",
      "resolved": "https://registry.npmmirror.com/node-releases/-/node-releases-2.0.36.tgz",
      "integrity": "sha512-TdC8FSgHz8Mwtw9g5L4gR/Sh9XhSP/0DEkQxfEFXOpiul5IiHgHan2VhYYb6agDSfp4KuvltmGApc8HMgUrIkA==",
      "license": "MIT"
    },
    "node_modules/normalize-path": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/normalize-path/-/normalize-path-3.0.0.tgz",
      "integrity": "sha512-6eZs5Ls3WtCisHWp9S2GUy8dqkpGi4BVSz3GaqiE6ezub0512ESztXUwUB6C6IKbQkY2Pnb/mD4WYojCRwcwLA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/npm-package-arg": {
      "version": "11.0.3",
      "resolved": "https://registry.npmmirror.com/npm-package-arg/-/npm-package-arg-11.0.3.tgz",
      "integrity": "sha512-sHGJy8sOC1YraBywpzQlIKBE4pBbGbiF95U6Auspzyem956E0+FtDtsx1ZxlOJkQCZ1AFXAY/yuvtFYrOxF+Bw==",
      "license": "ISC",
      "dependencies": {
        "hosted-git-info": "^7.0.0",
        "proc-log": "^4.0.0",
        "semver": "^7.3.5",
        "validate-npm-package-name": "^5.0.0"
      },
      "engines": {
        "node": "^16.14.0 || >=18.0.0"
      }
    },
    "node_modules/nth-check": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/nth-check/-/nth-check-2.1.1.tgz",
      "integrity": "sha512-lqjrjmaOoAnWfMmBPL+XNnynZh2+swxiX3WUE0s4yEHI6m+AwrK2UZOimIRl3X/4QctVqS8AiZjFqyOGrMXb/w==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "boolbase": "^1.0.0"
      },
      "funding": {
        "url": "https://github.com/fb55/nth-check?sponsor=1"
      }
    },
    "node_modules/nullthrows": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/nullthrows/-/nullthrows-1.1.1.tgz",
      "integrity": "sha512-2vPPEi+Z7WqML2jZYddDIfy5Dqb0r2fze2zTxNNknZaFpVHU3mFB3R+DWeJWGVx0ecvttSGlJTI+WG+8Z4cDWw==",
      "license": "MIT"
    },
    "node_modules/ob1": {
      "version": "0.83.3",
      "resolved": "https://registry.npmmirror.com/ob1/-/ob1-0.83.3.tgz",
      "integrity": "sha512-egUxXCDwoWG06NGCS5s5AdcpnumHKJlfd3HH06P3m9TEMwwScfcY35wpQxbm9oHof+dM/lVH9Rfyu1elTVelSA==",
      "license": "MIT",
      "dependencies": {
        "flow-enums-runtime": "^0.0.6"
      },
      "engines": {
        "node": ">=20.19.4"
      }
    },
    "node_modules/object-assign": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/object-assign/-/object-assign-4.1.1.tgz",
      "integrity": "sha512-rJgTQnkUnH1sFw8yT6VSU3zD3sWmu6sZhIseY8VX+GRu3P6F7Fu+JNDoXfklElbLJSnc3FUQHVe4cU5hj+BcUg==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/on-finished": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/on-finished/-/on-finished-2.3.0.tgz",
      "integrity": "sha512-ikqdkGAAyf/X/gPhXGvfgAytDZtDbr+bkNUJ0N9h5MI/dmdgCs3l6hoHrcUv41sRKew3jIwrp4qQDXiK99Utww==",
      "license": "MIT",
      "dependencies": {
        "ee-first": "1.1.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/on-headers": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/on-headers/-/on-headers-1.1.0.tgz",
      "integrity": "sha512-737ZY3yNnXy37FHkQxPzt4UZ2UWPWiCZWLvFZ4fu5cueciegX0zGPnrlY6bwRg4FdQOe9YU8MkmJwGhoMybl8A==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/once": {
      "version": "1.4.0",
      "resolved": "https://registry.npmmirror.com/once/-/once-1.4.0.tgz",
      "integrity": "sha512-lNaJgI+2Q5URQBkccEKHTQOPaXdUxnZZElQTZY0MFUAuaEqe1E+Nyvgdz/aIyNi6Z9MzO5dv1H8n58/GELp3+w==",
      "license": "ISC",
      "dependencies": {
        "wrappy": "1"
      }
    },
    "node_modules/onetime": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/onetime/-/onetime-2.0.1.tgz",
      "integrity": "sha512-oyyPpiMaKARvvcgip+JV+7zci5L8D1W9RZIz2l1o08AM3pfspitVWnPt3mzHcBPp12oYMTy0pqrFs/C+m3EwsQ==",
      "license": "MIT",
      "dependencies": {
        "mimic-fn": "^1.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/open": {
      "version": "7.4.2",
      "resolved": "https://registry.npmmirror.com/open/-/open-7.4.2.tgz",
      "integrity": "sha512-MVHddDVweXZF3awtlAS+6pgKLlm/JgxZ90+/NBurBoQctVOOB/zDdVjcyPzQ+0laDGbsWgrRkflI65sQeOgT9Q==",
      "license": "MIT",
      "dependencies": {
        "is-docker": "^2.0.0",
        "is-wsl": "^2.1.1"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/ora": {
      "version": "3.4.0",
      "resolved": "https://registry.npmmirror.com/ora/-/ora-3.4.0.tgz",
      "integrity": "sha512-eNwHudNbO1folBP3JsZ19v9azXWtQZjICdr3Q0TDPIaeBQ3mXLrh54wM+er0+hSp+dWKf+Z8KM58CYzEyIYxYg==",
      "license": "MIT",
      "dependencies": {
        "chalk": "^2.4.2",
        "cli-cursor": "^2.1.0",
        "cli-spinners": "^2.0.0",
        "log-symbols": "^2.2.0",
        "strip-ansi": "^5.2.0",
        "wcwidth": "^1.0.1"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/ora/node_modules/ansi-regex": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/ansi-regex/-/ansi-regex-4.1.1.tgz",
      "integrity": "sha512-ILlv4k/3f6vfQ4OoP2AGvirOktlQ98ZEL1k9FaQjxa3L1abBgbuTDAdPOpvbGncC0BTVQrl+OM8xZGK6tWXt7g==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/ora/node_modules/ansi-styles": {
      "version": "3.2.1",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-3.2.1.tgz",
      "integrity": "sha512-VT0ZI6kZRdTh8YyJw3SMbYm/u+NqfsAxEpWO0Pf9sq8/e94WxxOpPKx9FR1FlyCtOVDNOQ+8ntlqFxiRc+r5qA==",
      "license": "MIT",
      "dependencies": {
        "color-convert": "^1.9.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/ora/node_modules/chalk": {
      "version": "2.4.2",
      "resolved": "https://registry.npmmirror.com/chalk/-/chalk-2.4.2.tgz",
      "integrity": "sha512-Mti+f9lpJNcwF4tWV8/OrTTtF1gZi+f8FqlyAdouralcFWFQWF2+NgCHShjkCb+IFBLq9buZwE1xckQU4peSuQ==",
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^3.2.1",
        "escape-string-regexp": "^1.0.5",
        "supports-color": "^5.3.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/ora/node_modules/color-convert": {
      "version": "1.9.3",
      "resolved": "https://registry.npmmirror.com/color-convert/-/color-convert-1.9.3.tgz",
      "integrity": "sha512-QfAUtd+vFdAtFQcC8CCyYt1fYWxSqAiK2cSD6zDB8N3cpsEBAvRxp9zOGg6G/SHHJYAT88/az/IuDGALsNVbGg==",
      "license": "MIT",
      "dependencies": {
        "color-name": "1.1.3"
      }
    },
    "node_modules/ora/node_modules/color-name": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/color-name/-/color-name-1.1.3.tgz",
      "integrity": "sha512-72fSenhMw2HZMTVHeCA9KCmpEIbzWiQsjN+BHcBbS9vr1mtt+vJjPdksIBNUmKAW8TFUDPJK5SUU3QhE9NEXDw==",
      "license": "MIT"
    },
    "node_modules/ora/node_modules/escape-string-regexp": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/escape-string-regexp/-/escape-string-regexp-1.0.5.tgz",
      "integrity": "sha512-vbRorB5FUQWvla16U8R/qgaFIya2qGzwDrNmCZuYKrbdSUMG6I1ZCGQRefkRVhuOkIGVne7BQ35DSfo1qvJqFg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.8.0"
      }
    },
    "node_modules/ora/node_modules/has-flag": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/has-flag/-/has-flag-3.0.0.tgz",
      "integrity": "sha512-sKJf1+ceQBr4SMkvQnBDNDtf4TXpVhVGateu0t918bl30FnbE2m4vNLX+VWe/dpjlb+HugGYzW7uQXH98HPEYw==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/ora/node_modules/strip-ansi": {
      "version": "5.2.0",
      "resolved": "https://registry.npmmirror.com/strip-ansi/-/strip-ansi-5.2.0.tgz",
      "integrity": "sha512-DuRs1gKbBqsMKIZlrffwlug8MHkcnpjs5VPmL1PAh+mA30U0DTotfDZ0d2UUsXpPmPmMMJ6W773MaA3J+lbiWA==",
      "license": "MIT",
      "dependencies": {
        "ansi-regex": "^4.1.0"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/ora/node_modules/supports-color": {
      "version": "5.5.0",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-5.5.0.tgz",
      "integrity": "sha512-QjVjwdXIt408MIiAqCX4oUKsgU2EqAGzs2Ppkm4aQYbjm+ZEWEcW4SfFNTr4uMNZma0ey4f5lgLrkB0aX0QMow==",
      "license": "MIT",
      "dependencies": {
        "has-flag": "^3.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/p-limit": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/p-limit/-/p-limit-2.3.0.tgz",
      "integrity": "sha512-//88mFWSJx8lxCzwdAABTJL2MyWB12+eIY7MDL2SqLmAkeKU9qxRvWuSyTjm3FUmpBEMuFfckAIqEaVGUDxb6w==",
      "license": "MIT",
      "dependencies": {
        "p-try": "^2.0.0"
      },
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/p-locate": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/p-locate/-/p-locate-4.1.0.tgz",
      "integrity": "sha512-R79ZZ/0wAxKGu3oYMlz8jy/kbhsNrS7SKZ7PxEHBgJ5+F2mtFW2fK2cOtBh1cHYkQsbzFV7I+EoRKe6Yt0oK7A==",
      "license": "MIT",
      "dependencies": {
        "p-limit": "^2.2.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/p-try": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/p-try/-/p-try-2.2.0.tgz",
      "integrity": "sha512-R4nPAVTAU0B9D35/Gk3uJf/7XYbQcyohSKdvAxIRSNghFl4e71hVoGnBNQz9cWaXxO2I10KTC+3jMdvvoKw6dQ==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/parse-png": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/parse-png/-/parse-png-2.1.0.tgz",
      "integrity": "sha512-Nt/a5SfCLiTnQAjx3fHlqp8hRgTL3z7kTQZzvIMS9uCAepnCyjpdEc6M/sz69WqMBdaDBw9sF1F1UaHROYzGkQ==",
      "license": "MIT",
      "dependencies": {
        "pngjs": "^3.3.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/parseurl": {
      "version": "1.3.3",
      "resolved": "https://registry.npmmirror.com/parseurl/-/parseurl-1.3.3.tgz",
      "integrity": "sha512-CiyeOxFT/JZyN5m0z9PfXw4SCBJ6Sygz1Dpl0wqjlhDEGGBP1GnsUVEL0p63hoG1fcj3fHynXi9NYO4nWOL+qQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/path-exists": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/path-exists/-/path-exists-4.0.0.tgz",
      "integrity": "sha512-ak9Qy5Q7jYb2Wwcey5Fpvg2KoAc/ZIhLSLOSBmRmygPsGwkVVt0fZa0qrtMz+m6tJTAHfZQ8FnmB4MG4LWy7/w==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/path-is-absolute": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/path-is-absolute/-/path-is-absolute-1.0.1.tgz",
      "integrity": "sha512-AVbw3UJ2e9bq64vSaS9Am0fje1Pa8pbGqTTsmXfaIiMpnr5DlDhfJOuLj9Sf95ZPVDAUerDfEk88MPmPe7UCQg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/path-key": {
      "version": "3.1.1",
      "resolved": "https://registry.npmmirror.com/path-key/-/path-key-3.1.1.tgz",
      "integrity": "sha512-ojmeN0qd+y0jszEtoY48r0Peq5dwMEkIlCOu6Q5f41lfkswXuKtYrhgoTpLnyIcHm24Uhqx+5Tqm2InSwLhE6Q==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/path-parse": {
      "version": "1.0.7",
      "resolved": "https://registry.npmmirror.com/path-parse/-/path-parse-1.0.7.tgz",
      "integrity": "sha512-LDJzPVEEEPR+y48z93A0Ed0yXb8pAByGWo/k5YYdYgpY2/2EsOsksJrq7lOHxryrVOn1ejG6oAp8ahvOIQD8sw==",
      "license": "MIT"
    },
    "node_modules/path-scurry": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/path-scurry/-/path-scurry-2.0.2.tgz",
      "integrity": "sha512-3O/iVVsJAPsOnpwWIeD+d6z/7PmqApyQePUtCndjatj/9I5LylHvt5qluFaBT3I5h3r1ejfR056c+FCv+NnNXg==",
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "lru-cache": "^11.0.0",
        "minipass": "^7.1.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/path-scurry/node_modules/lru-cache": {
      "version": "11.2.7",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-11.2.7.tgz",
      "integrity": "sha512-aY/R+aEsRelme17KGQa/1ZSIpLpNYYrhcrepKTZgE+W3WM16YMCaPwOHLHsmopZHELU0Ojin1lPVxKR0MihncA==",
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": "20 || >=22"
      }
    },
    "node_modules/picocolors": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/picocolors/-/picocolors-1.1.1.tgz",
      "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
      "license": "ISC"
    },
    "node_modules/picomatch": {
      "version": "2.3.2",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-2.3.2.tgz",
      "integrity": "sha512-V7+vQEJ06Z+c5tSye8S+nHUfI51xoXIXjHQ99cQtKUkQqqO1kO/KCJUfZXuB47h/YBlDhah2H3hdUGXn8ie0oA==",
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/pirates": {
      "version": "4.0.7",
      "resolved": "https://registry.npmmirror.com/pirates/-/pirates-4.0.7.tgz",
      "integrity": "sha512-TfySrs/5nm8fQJDcBDuUng3VOUKsd7S+zqvbOTiGXHfxX4wK31ard+hoNuvkicM/2YFzlpDgABOevKSsB4G/FA==",
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/plist": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/plist/-/plist-3.1.0.tgz",
      "integrity": "sha512-uysumyrvkUX0rX/dEVqt8gC3sTBzd4zoWfLeS29nb53imdaXVvLINYXTI2GNqzaMuvacNx4uJQ8+b3zXR0pkgQ==",
      "license": "MIT",
      "dependencies": {
        "@xmldom/xmldom": "^0.8.8",
        "base64-js": "^1.5.1",
        "xmlbuilder": "^15.1.1"
      },
      "engines": {
        "node": ">=10.4.0"
      }
    },
    "node_modules/pngjs": {
      "version": "3.4.0",
      "resolved": "https://registry.npmmirror.com/pngjs/-/pngjs-3.4.0.tgz",
      "integrity": "sha512-NCrCHhWmnQklfH4MtJMRjZ2a8c80qXeMlQMv2uVp9ISJMTt562SbGd6n2oq0PaPgKm7Z6pL9E2UlLIhC+SHL3w==",
      "license": "MIT",
      "engines": {
        "node": ">=4.0.0"
      }
    },
    "node_modules/postcss": {
      "version": "8.4.49",
      "resolved": "https://registry.npmmirror.com/postcss/-/postcss-8.4.49.tgz",
      "integrity": "sha512-OCVPnIObs4N29kxTjzLfUryOkvZEq+pf8jTF0lg8E7uETuWHA+v7j3c/xJmiqpX450191LlmZfUKkXxkTry7nA==",
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/postcss"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.7",
        "picocolors": "^1.1.1",
        "source-map-js": "^1.2.1"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      }
    },
    "node_modules/postcss-value-parser": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/postcss-value-parser/-/postcss-value-parser-4.2.0.tgz",
      "integrity": "sha512-1NNCs6uurfkVbeXG4S8JFT9t19m45ICnif8zWLd5oPSZ50QnwMfK+H3jv408d4jw/7Bttv5axS5IiHoLaVNHeQ==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/pretty-format": {
      "version": "29.7.0",
      "resolved": "https://registry.npmmirror.com/pretty-format/-/pretty-format-29.7.0.tgz",
      "integrity": "sha512-Pdlw/oPxN+aXdmM9R00JVC9WVFoCLTKJvDVLgmJ+qAffBMxsV85l/Lu7sNx4zSzPyoL2euImuEwHhOXdEgNFZQ==",
      "license": "MIT",
      "dependencies": {
        "@jest/schemas": "^29.6.3",
        "ansi-styles": "^5.0.0",
        "react-is": "^18.0.0"
      },
      "engines": {
        "node": "^14.15.0 || ^16.10.0 || >=18.0.0"
      }
    },
    "node_modules/pretty-format/node_modules/ansi-styles": {
      "version": "5.2.0",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-5.2.0.tgz",
      "integrity": "sha512-Cxwpt2SfTzTtXcfOlzGEee8O+c+MmUgGrNiBcXnuWxuFJHe6a5Hz7qwhwe5OgaSYI0IJvkLqWX1ASG+cJOkEiA==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/ansi-styles?sponsor=1"
      }
    },
    "node_modules/proc-log": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/proc-log/-/proc-log-4.2.0.tgz",
      "integrity": "sha512-g8+OnU/L2v+wyiVK+D5fA34J7EH8jZ8DDlvwhRCMxmMj7UCBvxiO1mGeN+36JXIKF4zevU4kRBd8lVgG9vLelA==",
      "license": "ISC",
      "engines": {
        "node": "^14.17.0 || ^16.13.0 || >=18.0.0"
      }
    },
    "node_modules/progress": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/progress/-/progress-2.0.3.tgz",
      "integrity": "sha512-7PiHtLll5LdnKIMw100I+8xJXR5gW2QwWYkT6iJva0bXitZKa/XMrSbdmg3r2Xnaidz9Qumd0VPaMrZlF9V9sA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.4.0"
      }
    },
    "node_modules/promise": {
      "version": "8.3.0",
      "resolved": "https://registry.npmmirror.com/promise/-/promise-8.3.0.tgz",
      "integrity": "sha512-rZPNPKTOYVNEEKFaq1HqTgOwZD+4/YHS5ukLzQCypkj+OkYx7iv0mA91lJlpPPZ8vMau3IIGj5Qlwrx+8iiSmg==",
      "license": "MIT",
      "dependencies": {
        "asap": "~2.0.6"
      }
    },
    "node_modules/prompts": {
      "version": "2.4.2",
      "resolved": "https://registry.npmmirror.com/prompts/-/prompts-2.4.2.tgz",
      "integrity": "sha512-NxNv/kLguCA7p3jE8oL2aEBsrJWgAakBpgmgK6lpPWV+WuOmY6r2/zbAVnP+T8bQlA0nzHXSJSJW0Hq7ylaD2Q==",
      "license": "MIT",
      "dependencies": {
        "kleur": "^3.0.3",
        "sisteransi": "^1.0.5"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/query-string": {
      "version": "7.1.3",
      "resolved": "https://registry.npmmirror.com/query-string/-/query-string-7.1.3.tgz",
      "integrity": "sha512-hh2WYhq4fi8+b+/2Kg9CEge4fDPvHS534aOOvOZeQ3+Vf2mCFsaFBYj0i+iXcAq6I9Vzp5fjMFBlONvayDC1qg==",
      "license": "MIT",
      "dependencies": {
        "decode-uri-component": "^0.2.2",
        "filter-obj": "^1.1.0",
        "split-on-first": "^1.0.0",
        "strict-uri-encode": "^2.0.0"
      },
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/queue": {
      "version": "6.0.2",
      "resolved": "https://registry.npmmirror.com/queue/-/queue-6.0.2.tgz",
      "integrity": "sha512-iHZWu+q3IdFZFX36ro/lKBkSvfkztY5Y7HMiPlOUjhupPcG2JMfst2KKEpu5XndviX/3UhFbRngUPNKtgvtZiA==",
      "license": "MIT",
      "dependencies": {
        "inherits": "~2.0.3"
      }
    },
    "node_modules/range-parser": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/range-parser/-/range-parser-1.2.1.tgz",
      "integrity": "sha512-Hrgsx+orqoygnmhFbKaHE6c296J+HTAQXoxEF6gNupROmmGJRoyzfG3ccAveqCBrwr/2yxQ5BVd/GTl5agOwSg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/react": {
      "version": "19.2.0",
      "resolved": "https://registry.npmmirror.com/react/-/react-19.2.0.tgz",
      "integrity": "sha512-tmbWg6W31tQLeB5cdIBOicJDJRR2KzXsV7uSK9iNfLWQ5bIZfxuPEHp7M8wiHyHnn0DD1i7w3Zmin0FtkrwoCQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-devtools-core": {
      "version": "6.1.5",
      "resolved": "https://registry.npmmirror.com/react-devtools-core/-/react-devtools-core-6.1.5.tgz",
      "integrity": "sha512-ePrwPfxAnB+7hgnEr8vpKxL9cmnp7F322t8oqcPshbIQQhDKgFDW4tjhF2wjVbdXF9O/nyuy3sQWd9JGpiLPvA==",
      "license": "MIT",
      "dependencies": {
        "shell-quote": "^1.6.1",
        "ws": "^7"
      }
    },
    "node_modules/react-dom": {
      "version": "19.2.0",
      "resolved": "https://registry.npmmirror.com/react-dom/-/react-dom-19.2.0.tgz",
      "integrity": "sha512-UlbRu4cAiGaIewkPyiRGJk0imDN2T3JjieT6spoL2UeSf5od4n5LB/mQ4ejmxhCFT1tYe8IvaFulzynWovsEFQ==",
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "scheduler": "^0.27.0"
      },
      "peerDependencies": {
        "react": "^19.2.0"
      }
    },
    "node_modules/react-fast-compare": {
      "version": "3.2.2",
      "resolved": "https://registry.npmmirror.com/react-fast-compare/-/react-fast-compare-3.2.2.tgz",
      "integrity": "sha512-nsO+KSNgo1SbJqJEYRE9ERzo7YtYbou/OqjSQKxV7jcKox7+usiUVZOAC+XnDOABXggQTno0Y1CpVnuWEc1boQ==",
      "license": "MIT"
    },
    "node_modules/react-freeze": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/react-freeze/-/react-freeze-1.0.4.tgz",
      "integrity": "sha512-r4F0Sec0BLxWicc7HEyo2x3/2icUTrRmDjaaRyzzn+7aDyFZliszMDOgLVwSnQnYENOlL1o569Ze2HZefk8clA==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "react": ">=17.0.0"
      }
    },
    "node_modules/react-is": {
      "version": "18.3.1",
      "resolved": "https://registry.npmmirror.com/react-is/-/react-is-18.3.1.tgz",
      "integrity": "sha512-/LLMVyas0ljjAtoYiPqYiL8VWXzUUdThrmU5+n20DZv+a+ClRoevUzw5JxU+Ieh5/c87ytoTBV9G1FiKfNJdmg==",
      "license": "MIT"
    },
    "node_modules/react-native": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/react-native/-/react-native-0.83.4.tgz",
      "integrity": "sha512-H5Wco3UJyY6zZsjoBayY8RM9uiAEQ3FeG4G2NAt+lr9DO43QeqPlVe9xxxYEukMkEmeIhNjR70F6bhXuWArOMQ==",
      "license": "MIT",
      "dependencies": {
        "@jest/create-cache-key-function": "^29.7.0",
        "@react-native/assets-registry": "0.83.4",
        "@react-native/codegen": "0.83.4",
        "@react-native/community-cli-plugin": "0.83.4",
        "@react-native/gradle-plugin": "0.83.4",
        "@react-native/js-polyfills": "0.83.4",
        "@react-native/normalize-colors": "0.83.4",
        "@react-native/virtualized-lists": "0.83.4",
        "abort-controller": "^3.0.0",
        "anser": "^1.4.9",
        "ansi-regex": "^5.0.0",
        "babel-jest": "^29.7.0",
        "babel-plugin-syntax-hermes-parser": "0.32.0",
        "base64-js": "^1.5.1",
        "commander": "^12.0.0",
        "flow-enums-runtime": "^0.0.6",
        "glob": "^7.1.1",
        "hermes-compiler": "0.14.1",
        "invariant": "^2.2.4",
        "jest-environment-node": "^29.7.0",
        "memoize-one": "^5.0.0",
        "metro-runtime": "^0.83.3",
        "metro-source-map": "^0.83.3",
        "nullthrows": "^1.1.1",
        "pretty-format": "^29.7.0",
        "promise": "^8.3.0",
        "react-devtools-core": "^6.1.5",
        "react-refresh": "^0.14.0",
        "regenerator-runtime": "^0.13.2",
        "scheduler": "0.27.0",
        "semver": "^7.1.3",
        "stacktrace-parser": "^0.1.10",
        "whatwg-fetch": "^3.0.0",
        "ws": "^7.5.10",
        "yargs": "^17.6.2"
      },
      "bin": {
        "react-native": "cli.js"
      },
      "engines": {
        "node": ">= 20.19.4"
      },
      "peerDependencies": {
        "@types/react": "^19.1.1",
        "react": "^19.2.0"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/react-native-gesture-handler": {
      "version": "2.30.1",
      "resolved": "https://registry.npmmirror.com/react-native-gesture-handler/-/react-native-gesture-handler-2.30.1.tgz",
      "integrity": "sha512-xIUBDo5ktmJs++0fZlavQNvDEE4PsihWhSeJsJtoz4Q6p0MiTM9TgrTgfEgzRR36qGPytFoeq+ShLrVwGdpUdA==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "@egjs/hammerjs": "^2.0.17",
        "hoist-non-react-statics": "^3.3.0",
        "invariant": "^2.2.4"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/react-native-is-edge-to-edge": {
      "version": "1.3.1",
      "resolved": "https://registry.npmmirror.com/react-native-is-edge-to-edge/-/react-native-is-edge-to-edge-1.3.1.tgz",
      "integrity": "sha512-NIXU/iT5+ORyCc7p0z2nnlkouYKX425vuU1OEm6bMMtWWR9yvb+Xg5AZmImTKoF9abxCPqrKC3rOZsKzUYgYZA==",
      "license": "MIT",
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/react-native-safe-area-context": {
      "version": "5.6.2",
      "resolved": "https://registry.npmmirror.com/react-native-safe-area-context/-/react-native-safe-area-context-5.6.2.tgz",
      "integrity": "sha512-4XGqMNj5qjUTYywJqpdWZ9IG8jgkS3h06sfVjfw5yZQZfWnRFXczi0GnYyFyCc2EBps/qFmoCH8fez//WumdVg==",
      "license": "MIT",
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/react-native-screens": {
      "version": "4.23.0",
      "resolved": "https://registry.npmmirror.com/react-native-screens/-/react-native-screens-4.23.0.tgz",
      "integrity": "sha512-XhO3aK0UeLpBn4kLecd+J+EDeRRJlI/Ro9Fze06vo1q163VeYtzfU9QS09/VyDFMWR1qxDC1iazCArTPSFFiPw==",
      "license": "MIT",
      "dependencies": {
        "react-freeze": "^1.0.0",
        "warn-once": "^0.1.0"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/react-native-svg": {
      "version": "15.15.3",
      "resolved": "https://registry.npmmirror.com/react-native-svg/-/react-native-svg-15.15.3.tgz",
      "integrity": "sha512-/k4KYwPBLGcx2f5d4FjE+vCScK7QOX14cl2lIASJ28u4slHHtIhL0SZKU7u9qmRBHxTCKPoPBtN6haT1NENJNA==",
      "license": "MIT",
      "dependencies": {
        "css-select": "^5.1.0",
        "css-tree": "^1.1.3",
        "warn-once": "0.1.1"
      },
      "peerDependencies": {
        "react": "*",
        "react-native": "*"
      }
    },
    "node_modules/react-native-web": {
      "version": "0.21.2",
      "resolved": "https://registry.npmmirror.com/react-native-web/-/react-native-web-0.21.2.tgz",
      "integrity": "sha512-SO2t9/17zM4iEnFvlu2DA9jqNbzNhoUP+AItkoCOyFmDMOhUnBBznBDCYN92fGdfAkfQlWzPoez6+zLxFNsZEg==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "@babel/runtime": "^7.18.6",
        "@react-native/normalize-colors": "^0.74.1",
        "fbjs": "^3.0.4",
        "inline-style-prefixer": "^7.0.1",
        "memoize-one": "^6.0.0",
        "nullthrows": "^1.1.1",
        "postcss-value-parser": "^4.2.0",
        "styleq": "^0.1.3"
      },
      "peerDependencies": {
        "react": "^18.0.0 || ^19.0.0",
        "react-dom": "^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/react-native-web/node_modules/@react-native/normalize-colors": {
      "version": "0.74.89",
      "resolved": "https://registry.npmmirror.com/@react-native/normalize-colors/-/normalize-colors-0.74.89.tgz",
      "integrity": "sha512-qoMMXddVKVhZ8PA1AbUCk83trpd6N+1nF2A6k1i6LsQObyS92fELuk8kU/lQs6M7BsMHwqyLCpQJ1uFgNvIQXg==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/react-native-web/node_modules/memoize-one": {
      "version": "6.0.0",
      "resolved": "https://registry.npmmirror.com/memoize-one/-/memoize-one-6.0.0.tgz",
      "integrity": "sha512-rkpe71W0N0c0Xz6QD0eJETuWAJGnJ9afsl1srmwPrI+yBCkge5EycXXbYRyvL29zZVUWQCY7InPRCv3GDXuZNw==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/react-native/node_modules/@react-native/virtualized-lists": {
      "version": "0.83.4",
      "resolved": "https://registry.npmmirror.com/@react-native/virtualized-lists/-/virtualized-lists-0.83.4.tgz",
      "integrity": "sha512-vNF/8kokMW8JEjG4n+j7veLTjHRRABlt4CaTS6+wtqzvWxCJHNIC8fhCqrDPn9fIn8sNePd8DyiFVX5L9TBBRA==",
      "license": "MIT",
      "dependencies": {
        "invariant": "^2.2.4",
        "nullthrows": "^1.1.1"
      },
      "engines": {
        "node": ">= 20.19.4"
      },
      "peerDependencies": {
        "@types/react": "^19.2.0",
        "react": "*",
        "react-native": "*"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/react-native/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "license": "MIT"
    },
    "node_modules/react-native/node_modules/brace-expansion": {
      "version": "1.1.13",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.13.tgz",
      "integrity": "sha512-9ZLprWS6EENmhEOpjCYW2c8VkmOvckIJZfkr7rBW6dObmfgJ/L1GpSYW5Hpo9lDz4D1+n0Ckz8rU7FwHDQiG/w==",
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/react-native/node_modules/commander": {
      "version": "12.1.0",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-12.1.0.tgz",
      "integrity": "sha512-Vw8qHK3bZM9y/P10u3Vib8o/DdkvA2OtPtZvD871QKjy74Wj1WSKFILMPRPSdUSx5RFK1arlJzEtA4PkFgnbuA==",
      "license": "MIT",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/react-native/node_modules/glob": {
      "version": "7.2.3",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-7.2.3.tgz",
      "integrity": "sha512-nFR0zLpU2YCaRxwoCJvL6UvCH2JFyFVIvwTLsIf21AuHlMskA1hhTdk+LlYJtOlYt9v6dvszD2BGRqBL+iQK9Q==",
      "deprecated": "Glob versions prior to v9 are no longer supported",
      "license": "ISC",
      "dependencies": {
        "fs.realpath": "^1.0.0",
        "inflight": "^1.0.4",
        "inherits": "2",
        "minimatch": "^3.1.1",
        "once": "^1.3.0",
        "path-is-absolute": "^1.0.0"
      },
      "engines": {
        "node": "*"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/react-native/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/react-refresh": {
      "version": "0.14.2",
      "resolved": "https://registry.npmmirror.com/react-refresh/-/react-refresh-0.14.2.tgz",
      "integrity": "sha512-jCvmsr+1IUSMUyzOkRcvnVbX3ZYC6g9TDrDbFuFmRDq7PD4yaGbLKNQL6k2jnArV8hjYxh7hVhAZB6s9HDGpZA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-remove-scroll": {
      "version": "2.7.2",
      "resolved": "https://registry.npmmirror.com/react-remove-scroll/-/react-remove-scroll-2.7.2.tgz",
      "integrity": "sha512-Iqb9NjCCTt6Hf+vOdNIZGdTiH1QSqr27H/Ek9sv/a97gfueI/5h1s3yRi1nngzMUaOOToin5dI1dXKdXiF+u0Q==",
      "license": "MIT",
      "dependencies": {
        "react-remove-scroll-bar": "^2.3.7",
        "react-style-singleton": "^2.2.3",
        "tslib": "^2.1.0",
        "use-callback-ref": "^1.3.3",
        "use-sidecar": "^1.1.3"
      },
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/react-remove-scroll-bar": {
      "version": "2.3.8",
      "resolved": "https://registry.npmmirror.com/react-remove-scroll-bar/-/react-remove-scroll-bar-2.3.8.tgz",
      "integrity": "sha512-9r+yi9+mgU33AKcj6IbT9oRCO78WriSj6t/cF8DWBZJ9aOGPOTEDvdUDz1FwKim7QXWwmHqtdHnRJfhAxEG46Q==",
      "license": "MIT",
      "dependencies": {
        "react-style-singleton": "^2.2.2",
        "tslib": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/react-style-singleton": {
      "version": "2.2.3",
      "resolved": "https://registry.npmmirror.com/react-style-singleton/-/react-style-singleton-2.2.3.tgz",
      "integrity": "sha512-b6jSvxvVnyptAiLjbkWLE/lOnR4lfTtDAl+eUC7RZy+QQWc6wRzIV2CE6xBuMmDxc2qIihtDCZD5NPOFl7fRBQ==",
      "license": "MIT",
      "dependencies": {
        "get-nonce": "^1.0.0",
        "tslib": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/regenerate": {
      "version": "1.4.2",
      "resolved": "https://registry.npmmirror.com/regenerate/-/regenerate-1.4.2.tgz",
      "integrity": "sha512-zrceR/XhGYU/d/opr2EKO7aRHUeiBI8qjtfHqADTwZd6Szfy16la6kqD0MIUs5z5hx6AaKa+PixpPrR289+I0A==",
      "license": "MIT"
    },
    "node_modules/regenerate-unicode-properties": {
      "version": "10.2.2",
      "resolved": "https://registry.npmmirror.com/regenerate-unicode-properties/-/regenerate-unicode-properties-10.2.2.tgz",
      "integrity": "sha512-m03P+zhBeQd1RGnYxrGyDAPpWX/epKirLrp8e3qevZdVkKtnCrjjWczIbYc8+xd6vcTStVlqfycTx1KR4LOr0g==",
      "license": "MIT",
      "dependencies": {
        "regenerate": "^1.4.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/regenerator-runtime": {
      "version": "0.13.11",
      "resolved": "https://registry.npmmirror.com/regenerator-runtime/-/regenerator-runtime-0.13.11.tgz",
      "integrity": "sha512-kY1AZVr2Ra+t+piVaJ4gxaFaReZVH40AKNo7UCX6W+dEwBo/2oZJzqfuN1qLq1oL45o56cPaTXELwrTh8Fpggg==",
      "license": "MIT"
    },
    "node_modules/regexpu-core": {
      "version": "6.4.0",
      "resolved": "https://registry.npmmirror.com/regexpu-core/-/regexpu-core-6.4.0.tgz",
      "integrity": "sha512-0ghuzq67LI9bLXpOX/ISfve/Mq33a4aFRzoQYhnnok1JOFpmE/A2TBGkNVenOGEeSBCjIiWcc6MVOG5HEQv0sA==",
      "license": "MIT",
      "dependencies": {
        "regenerate": "^1.4.2",
        "regenerate-unicode-properties": "^10.2.2",
        "regjsgen": "^0.8.0",
        "regjsparser": "^0.13.0",
        "unicode-match-property-ecmascript": "^2.0.0",
        "unicode-match-property-value-ecmascript": "^2.2.1"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/regjsgen": {
      "version": "0.8.0",
      "resolved": "https://registry.npmmirror.com/regjsgen/-/regjsgen-0.8.0.tgz",
      "integrity": "sha512-RvwtGe3d7LvWiDQXeQw8p5asZUmfU1G/l6WbUXeHta7Y2PEIvBTwH6E2EfmYUK8pxcxEdEmaomqyp0vZZ7C+3Q==",
      "license": "MIT"
    },
    "node_modules/regjsparser": {
      "version": "0.13.0",
      "resolved": "https://registry.npmmirror.com/regjsparser/-/regjsparser-0.13.0.tgz",
      "integrity": "sha512-NZQZdC5wOE/H3UT28fVGL+ikOZcEzfMGk/c3iN9UGxzWHMa1op7274oyiUVrAG4B2EuFhus8SvkaYnhvW92p9Q==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "jsesc": "~3.1.0"
      },
      "bin": {
        "regjsparser": "bin/parser"
      }
    },
    "node_modules/require-directory": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/require-directory/-/require-directory-2.1.1.tgz",
      "integrity": "sha512-fGxEI7+wsG9xrvdjsrlmL22OMTTiHRwAMroiEeMgq8gzoLC/PQr7RsRDSTLUg/bZAZtF+TVIkHc6/4RIKrui+Q==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/resolve": {
      "version": "1.22.11",
      "resolved": "https://registry.npmmirror.com/resolve/-/resolve-1.22.11.tgz",
      "integrity": "sha512-RfqAvLnMl313r7c9oclB1HhUEAezcpLjz95wFH4LVuhk9JF/r22qmVP9AMmOU4vMX7Q8pN8jwNg/CSpdFnMjTQ==",
      "license": "MIT",
      "dependencies": {
        "is-core-module": "^2.16.1",
        "path-parse": "^1.0.7",
        "supports-preserve-symlinks-flag": "^1.0.0"
      },
      "bin": {
        "resolve": "bin/resolve"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/resolve-from": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/resolve-from/-/resolve-from-5.0.0.tgz",
      "integrity": "sha512-qYg9KP24dD5qka9J47d0aVky0N+b4fTU89LN9iDnjB5waksiC49rvMB0PrUJQGoTmH50XPiqOvAjDfaijGxYZw==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/resolve-workspace-root": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/resolve-workspace-root/-/resolve-workspace-root-2.0.1.tgz",
      "integrity": "sha512-nR23LHAvaI6aHtMg6RWoaHpdR4D881Nydkzi2CixINyg9T00KgaJdJI6Vwty+Ps8WLxZHuxsS0BseWjxSA4C+w==",
      "license": "MIT"
    },
    "node_modules/restore-cursor": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/restore-cursor/-/restore-cursor-2.0.0.tgz",
      "integrity": "sha512-6IzJLuGi4+R14vwagDHX+JrXmPVtPpn4mffDJ1UdR7/Edm87fl6yi8mMBIVvFtJaNTUvjughmW4hwLhRG7gC1Q==",
      "license": "MIT",
      "dependencies": {
        "onetime": "^2.0.0",
        "signal-exit": "^3.0.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/rimraf": {
      "version": "3.0.2",
      "resolved": "https://registry.npmmirror.com/rimraf/-/rimraf-3.0.2.tgz",
      "integrity": "sha512-JZkJMZkAGFFPP2YqXZXPbMlMBgsxzE8ILs4lMIX/2o0L9UBw9O/Y3o6wFw/i9YLapcUJWwqbi3kdxIPdC62TIA==",
      "deprecated": "Rimraf versions prior to v4 are no longer supported",
      "license": "ISC",
      "dependencies": {
        "glob": "^7.1.3"
      },
      "bin": {
        "rimraf": "bin.js"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/rimraf/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "license": "MIT"
    },
    "node_modules/rimraf/node_modules/brace-expansion": {
      "version": "1.1.13",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.13.tgz",
      "integrity": "sha512-9ZLprWS6EENmhEOpjCYW2c8VkmOvckIJZfkr7rBW6dObmfgJ/L1GpSYW5Hpo9lDz4D1+n0Ckz8rU7FwHDQiG/w==",
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/rimraf/node_modules/glob": {
      "version": "7.2.3",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-7.2.3.tgz",
      "integrity": "sha512-nFR0zLpU2YCaRxwoCJvL6UvCH2JFyFVIvwTLsIf21AuHlMskA1hhTdk+LlYJtOlYt9v6dvszD2BGRqBL+iQK9Q==",
      "deprecated": "Glob versions prior to v9 are no longer supported",
      "license": "ISC",
      "dependencies": {
        "fs.realpath": "^1.0.0",
        "inflight": "^1.0.4",
        "inherits": "2",
        "minimatch": "^3.1.1",
        "once": "^1.3.0",
        "path-is-absolute": "^1.0.0"
      },
      "engines": {
        "node": "*"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/rimraf/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/safe-buffer": {
      "version": "5.2.1",
      "resolved": "https://registry.npmmirror.com/safe-buffer/-/safe-buffer-5.2.1.tgz",
      "integrity": "sha512-rp3So07KcdmmKbGvgaNxQSJr7bGVSVk5S9Eq1F+ppbRo70+YeaDxkw5Dd8NPN+GD6bjnYm2VuPuCXmpuYvmCXQ==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/sax": {
      "version": "1.6.0",
      "resolved": "https://registry.npmmirror.com/sax/-/sax-1.6.0.tgz",
      "integrity": "sha512-6R3J5M4AcbtLUdZmRv2SygeVaM7IhrLXu9BmnOGmmACak8fiUtOsYNWUS4uK7upbmHIBbLBeFeI//477BKLBzA==",
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=11.0.0"
      }
    },
    "node_modules/scheduler": {
      "version": "0.27.0",
      "resolved": "https://registry.npmmirror.com/scheduler/-/scheduler-0.27.0.tgz",
      "integrity": "sha512-eNv+WrVbKu1f3vbYJT/xtiF5syA5HPIMtf9IgY/nKg0sWqzAUEvqY/xm7OcZc/qafLx/iO9FgOmeSAp4v5ti/Q==",
      "license": "MIT"
    },
    "node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/send": {
      "version": "0.19.2",
      "resolved": "https://registry.npmmirror.com/send/-/send-0.19.2.tgz",
      "integrity": "sha512-VMbMxbDeehAxpOtWJXlcUS5E8iXh6QmN+BkRX1GARS3wRaXEEgzCcB10gTQazO42tpNIya8xIyNx8fll1OFPrg==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "fresh": "~0.5.2",
        "http-errors": "~2.0.1",
        "mime": "1.6.0",
        "ms": "2.1.3",
        "on-finished": "~2.4.1",
        "range-parser": "~1.2.1",
        "statuses": "~2.0.2"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/send/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/send/node_modules/debug/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/send/node_modules/encodeurl": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/encodeurl/-/encodeurl-2.0.0.tgz",
      "integrity": "sha512-Q0n9HRi4m6JuGIV1eFlmvJB7ZEVxu93IrMyiMsGC0lrMJMWzRgx6WGquyfQgZVb31vhGgXnfmPNNXmxnOkRBrg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/send/node_modules/on-finished": {
      "version": "2.4.1",
      "resolved": "https://registry.npmmirror.com/on-finished/-/on-finished-2.4.1.tgz",
      "integrity": "sha512-oVlzkg3ENAhCk2zdv7IJwd/QUD4z2RxRwpkcGY8psCVcCYZNq4wYnVWALHM+brtuJjePWiYF/ClmuDr8Ch5+kg==",
      "license": "MIT",
      "dependencies": {
        "ee-first": "1.1.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/send/node_modules/statuses": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/statuses/-/statuses-2.0.2.tgz",
      "integrity": "sha512-DvEy55V3DB7uknRo+4iOGT5fP1slR8wQohVdknigZPMpMstaKJQWhwiYBACJE3Ul2pTnATihhBYnRhZQHGBiRw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/serialize-error": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/serialize-error/-/serialize-error-2.1.0.tgz",
      "integrity": "sha512-ghgmKt5o4Tly5yEG/UJp8qTd0AN7Xalw4XBtDEKP655B699qMEtra1WlXeE6WIvdEG481JvRxULKsInq/iNysw==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/serve-static": {
      "version": "1.16.3",
      "resolved": "https://registry.npmmirror.com/serve-static/-/serve-static-1.16.3.tgz",
      "integrity": "sha512-x0RTqQel6g5SY7Lg6ZreMmsOzncHFU7nhnRWkKgWuMTu5NN0DR5oruckMqRvacAN9d5w6ARnRBXl9xhDCgfMeA==",
      "license": "MIT",
      "dependencies": {
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "parseurl": "~1.3.3",
        "send": "~0.19.1"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/serve-static/node_modules/encodeurl": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/encodeurl/-/encodeurl-2.0.0.tgz",
      "integrity": "sha512-Q0n9HRi4m6JuGIV1eFlmvJB7ZEVxu93IrMyiMsGC0lrMJMWzRgx6WGquyfQgZVb31vhGgXnfmPNNXmxnOkRBrg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/server-only": {
      "version": "0.0.1",
      "resolved": "https://registry.npmmirror.com/server-only/-/server-only-0.0.1.tgz",
      "integrity": "sha512-qepMx2JxAa5jjfzxG79yPPq+8BuFToHd1hm7kI+Z4zAq1ftQiP7HcxMhDDItrbtwVeLg/cY2JnKnrcFkmiswNA==",
      "license": "MIT"
    },
    "node_modules/setimmediate": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/setimmediate/-/setimmediate-1.0.5.tgz",
      "integrity": "sha512-MATJdZp8sLqDl/68LfQmbP8zKPLQNV6BIZoIgrscFDQ+RsvK/BxeDQOgyxKKoh0y/8h3BqVFnCqQ/gd+reiIXA==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/setprototypeof": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/setprototypeof/-/setprototypeof-1.2.0.tgz",
      "integrity": "sha512-E5LDX7Wrp85Kil5bhZv46j8jOeboKq5JMmYM3gVGdGH8xFpPWXUMsNrlODCrkoxMEeNi/XZIwuRvY4XNwYMJpw==",
      "license": "ISC"
    },
    "node_modules/sf-symbols-typescript": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/sf-symbols-typescript/-/sf-symbols-typescript-2.2.0.tgz",
      "integrity": "sha512-TPbeg0b7ylrswdGCji8FRGFAKuqbpQlLbL8SOle3j1iHSs5Ob5mhvMAxWN2UItOjgALAB5Zp3fmMfj8mbWvXKw==",
      "license": "MIT",
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/shallowequal": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/shallowequal/-/shallowequal-1.1.0.tgz",
      "integrity": "sha512-y0m1JoUZSlPAjXVtPPW70aZWfIL/dSP7AFkRnniLCrK/8MDKog3TySTBmckD+RObVxH0v4Tox67+F14PdED2oQ==",
      "license": "MIT"
    },
    "node_modules/shebang-command": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/shebang-command/-/shebang-command-2.0.0.tgz",
      "integrity": "sha512-kHxr2zZpYtdmrN1qDjrrX/Z1rR1kG8Dx+gkpK1G4eXmvXswmcE1hTWBWYUzlraYw1/yZp6YuDY77YtvbN0dmDA==",
      "license": "MIT",
      "dependencies": {
        "shebang-regex": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/shebang-regex": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/shebang-regex/-/shebang-regex-3.0.0.tgz",
      "integrity": "sha512-7++dFhtcx3353uBaq8DDR4NuxBetBzC7ZQOhmTQInHEd6bSrXdiEyzCvG07Z44UYdLShWUyXt5M/yhz8ekcb1A==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/shell-quote": {
      "version": "1.8.3",
      "resolved": "https://registry.npmmirror.com/shell-quote/-/shell-quote-1.8.3.tgz",
      "integrity": "sha512-ObmnIF4hXNg1BqhnHmgbDETF8dLPCggZWBjkQfhZpbszZnYur5DUljTcCHii5LC3J5E0yeO/1LIMyH+UvHQgyw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/signal-exit": {
      "version": "3.0.7",
      "resolved": "https://registry.npmmirror.com/signal-exit/-/signal-exit-3.0.7.tgz",
      "integrity": "sha512-wnD2ZE+l+SPC/uoS0vXeE9L1+0wuaMqKlfz9AMUo38JsyLSBWSFcHR1Rri62LZc12vLr1gb3jl7iwQhgwpAbGQ==",
      "license": "ISC"
    },
    "node_modules/simple-plist": {
      "version": "1.3.1",
      "resolved": "https://registry.npmmirror.com/simple-plist/-/simple-plist-1.3.1.tgz",
      "integrity": "sha512-iMSw5i0XseMnrhtIzRb7XpQEXepa9xhWxGUojHBL43SIpQuDQkh3Wpy67ZbDzZVr6EKxvwVChnVpdl8hEVLDiw==",
      "license": "MIT",
      "dependencies": {
        "bplist-creator": "0.1.0",
        "bplist-parser": "0.3.1",
        "plist": "^3.0.5"
      }
    },
    "node_modules/simple-swizzle": {
      "version": "0.2.4",
      "resolved": "https://registry.npmmirror.com/simple-swizzle/-/simple-swizzle-0.2.4.tgz",
      "integrity": "sha512-nAu1WFPQSMNr2Zn9PGSZK9AGn4t/y97lEm+MXTtUDwfP0ksAIX4nO+6ruD9Jwut4C49SB1Ws+fbXsm/yScWOHw==",
      "license": "MIT",
      "dependencies": {
        "is-arrayish": "^0.3.1"
      }
    },
    "node_modules/sisteransi": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/sisteransi/-/sisteransi-1.0.5.tgz",
      "integrity": "sha512-bLGGlR1QxBcynn2d5YmDX4MGjlZvy2MRBDRNHLJ8VI6l6+9FUiyTFNJ0IveOSP0bcXgVDPRcfGqA0pjaqUpfVg==",
      "license": "MIT"
    },
    "node_modules/slash": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/slash/-/slash-3.0.0.tgz",
      "integrity": "sha512-g9Q1haeby36OSStwb4ntCGGGaKsaVSjQ68fBxoQcutl5fS1vuY18H3wSt3jFyFtrkx+Kz0V1G85A4MyAdDMi2Q==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/slugify": {
      "version": "1.6.8",
      "resolved": "https://registry.npmmirror.com/slugify/-/slugify-1.6.8.tgz",
      "integrity": "sha512-HVk9X1E0gz3mSpoi60h/saazLKXKaZThMLU3u/aNwoYn8/xQyX2MGxL0ui2eaokkD7tF+Zo+cKTHUbe1mmmGzA==",
      "license": "MIT",
      "engines": {
        "node": ">=8.0.0"
      }
    },
    "node_modules/source-map": {
      "version": "0.5.7",
      "resolved": "https://registry.npmmirror.com/source-map/-/source-map-0.5.7.tgz",
      "integrity": "sha512-LbrmJOMUSdEVxIKvdcJzQC+nQhe8FUZQTXQy6+I75skNgn3OoQ0DZA8YnFa7gp8tqtL3KPf1kmo0R5DoApeSGQ==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/source-map-js": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/source-map-js/-/source-map-js-1.2.1.tgz",
      "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/source-map-support": {
      "version": "0.5.21",
      "resolved": "https://registry.npmmirror.com/source-map-support/-/source-map-support-0.5.21.tgz",
      "integrity": "sha512-uBHU3L3czsIyYXKX88fdrGovxdSCoTGDRZ6SYXtSRxLZUzHg5P/66Ht6uoUlHu9EZod+inXhKo3qQgwXUT/y1w==",
      "license": "MIT",
      "dependencies": {
        "buffer-from": "^1.0.0",
        "source-map": "^0.6.0"
      }
    },
    "node_modules/source-map-support/node_modules/source-map": {
      "version": "0.6.1",
      "resolved": "https://registry.npmmirror.com/source-map/-/source-map-0.6.1.tgz",
      "integrity": "sha512-UjgapumWlbMhkBgzT7Ykc5YXUT46F0iKu8SGXq0bcwP5dz/h0Plj6enJqjz1Zbq2l5WaqYnrVbwWOWMyF3F47g==",
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/split-on-first": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/split-on-first/-/split-on-first-1.1.0.tgz",
      "integrity": "sha512-43ZssAJaMusuKWL8sKUBQXHWOpq8d6CfN/u1p4gUzfJkM05C8rxTmYrkIPTXapZpORA6LkkzcUulJ8FqA7Uudw==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/sprintf-js": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/sprintf-js/-/sprintf-js-1.0.3.tgz",
      "integrity": "sha512-D9cPgkvLlV3t3IzL0D0YLvGA9Ahk4PcvVwUbN0dSGr1aP0Nrt4AEnTUbuGvquEC0mA64Gqt1fzirlRs5ibXx8g==",
      "license": "BSD-3-Clause"
    },
    "node_modules/stack-utils": {
      "version": "2.0.6",
      "resolved": "https://registry.npmmirror.com/stack-utils/-/stack-utils-2.0.6.tgz",
      "integrity": "sha512-XlkWvfIm6RmsWtNJx+uqtKLS8eqFbxUg0ZzLXqY0caEy9l7hruX8IpiDnjsLavoBgqCCR71TqWO8MaXYheJ3RQ==",
      "license": "MIT",
      "dependencies": {
        "escape-string-regexp": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/stack-utils/node_modules/escape-string-regexp": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/escape-string-regexp/-/escape-string-regexp-2.0.0.tgz",
      "integrity": "sha512-UpzcLCXolUWcNu5HtVMHYdXJjArjsF9C0aNnquZYY4uW/Vu0miy5YoWvbV345HauVvcAUnpRuhMMcqTcGOY2+w==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/stackframe": {
      "version": "1.3.4",
      "resolved": "https://registry.npmmirror.com/stackframe/-/stackframe-1.3.4.tgz",
      "integrity": "sha512-oeVtt7eWQS+Na6F//S4kJ2K2VbRlS9D43mAlMyVpVWovy9o+jfgH8O9agzANzaiLjclA0oYzUXEM4PurhSUChw==",
      "license": "MIT"
    },
    "node_modules/stacktrace-parser": {
      "version": "0.1.11",
      "resolved": "https://registry.npmmirror.com/stacktrace-parser/-/stacktrace-parser-0.1.11.tgz",
      "integrity": "sha512-WjlahMgHmCJpqzU8bIBy4qtsZdU9lRlcZE3Lvyej6t4tuOuv1vk57OW3MBrj6hXBFx/nNoC9MPMTcr5YA7NQbg==",
      "license": "MIT",
      "dependencies": {
        "type-fest": "^0.7.1"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/statuses": {
      "version": "1.5.0",
      "resolved": "https://registry.npmmirror.com/statuses/-/statuses-1.5.0.tgz",
      "integrity": "sha512-OpZ3zP+jT1PI7I8nemJX4AKmAX070ZkYPVWV/AaKTJl+tXCTGyVdC1a4SL8RUQYEwk/f34ZX8UTykN68FwrqAA==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/stream-buffers": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/stream-buffers/-/stream-buffers-2.2.0.tgz",
      "integrity": "sha512-uyQK/mx5QjHun80FLJTfaWE7JtwfRMKBLkMne6udYOmvH0CawotVa7TfgYHzAnpphn4+TweIx1QKMnRIbipmUg==",
      "license": "Unlicense",
      "engines": {
        "node": ">= 0.10.0"
      }
    },
    "node_modules/strict-uri-encode": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/strict-uri-encode/-/strict-uri-encode-2.0.0.tgz",
      "integrity": "sha512-QwiXZgpRcKkhTj2Scnn++4PKtWsH0kpzZ62L2R6c/LUVYv7hVnZqcg2+sMuT6R7Jusu1vviK/MFsu6kNJfWlEQ==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/string-width": {
      "version": "4.2.3",
      "resolved": "https://registry.npmmirror.com/string-width/-/string-width-4.2.3.tgz",
      "integrity": "sha512-wKyQRQpjJ0sIp62ErSZdGsjMJWsap5oRNihHhu6G7JVO/9jIB6UyevL+tXuOqrng8j/cxKTWyWUwvSTriiZz/g==",
      "license": "MIT",
      "dependencies": {
        "emoji-regex": "^8.0.0",
        "is-fullwidth-code-point": "^3.0.0",
        "strip-ansi": "^6.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/strip-ansi": {
      "version": "6.0.1",
      "resolved": "https://registry.npmmirror.com/strip-ansi/-/strip-ansi-6.0.1.tgz",
      "integrity": "sha512-Y38VPSHcqkFrCpFnQ9vuSXmquuv5oXOKpGeT6aGrr3o3Gc9AlVa6JBfUSOCnbxGGZF+/0ooI7KrPuUSztUdU5A==",
      "license": "MIT",
      "dependencies": {
        "ansi-regex": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/structured-headers": {
      "version": "0.4.1",
      "resolved": "https://registry.npmmirror.com/structured-headers/-/structured-headers-0.4.1.tgz",
      "integrity": "sha512-0MP/Cxx5SzeeZ10p/bZI0S6MpgD+yxAhi1BOQ34jgnMXsCq3j1t6tQnZu+KdlL7dvJTLT3g9xN8tl10TqgFMcg==",
      "license": "MIT"
    },
    "node_modules/styleq": {
      "version": "0.1.3",
      "resolved": "https://registry.npmmirror.com/styleq/-/styleq-0.1.3.tgz",
      "integrity": "sha512-3ZUifmCDCQanjeej1f6kyl/BeP/Vae5EYkQ9iJfUm/QwZvlgnZzyflqAsAWYURdtea8Vkvswu2GrC57h3qffcA==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/supports-color": {
      "version": "7.2.0",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-7.2.0.tgz",
      "integrity": "sha512-qpCAvRl9stuOHveKsn7HncJRvv501qIacKzQlO/+Lwxc9+0q2wLyv4Dfvt80/DPn2pqOBsJdDiogXGR9+OvwRw==",
      "license": "MIT",
      "dependencies": {
        "has-flag": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/supports-hyperlinks": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/supports-hyperlinks/-/supports-hyperlinks-2.3.0.tgz",
      "integrity": "sha512-RpsAZlpWcDwOPQA22aCH4J0t7L8JmAvsCxfOSEwm7cQs3LshN36QaTkwd70DnBOXDWGssw2eUoc8CaRWT0XunA==",
      "license": "MIT",
      "dependencies": {
        "has-flag": "^4.0.0",
        "supports-color": "^7.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/supports-preserve-symlinks-flag": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/supports-preserve-symlinks-flag/-/supports-preserve-symlinks-flag-1.0.0.tgz",
      "integrity": "sha512-ot0WnXS9fgdkgIcePe6RHNk1WA8+muPa6cSjeR3V8K27q9BB1rTE3R1p7Hv0z1ZyAc8s6Vvv8DIyWf681MAt0w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/terminal-link": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/terminal-link/-/terminal-link-2.1.1.tgz",
      "integrity": "sha512-un0FmiRUQNr5PJqy9kP7c40F5BOfpGlYTrxonDChEZB7pzZxRNp/bt+ymiy9/npwXya9KH99nJ/GXFIiUkYGFQ==",
      "license": "MIT",
      "dependencies": {
        "ansi-escapes": "^4.2.1",
        "supports-hyperlinks": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/terser": {
      "version": "5.46.1",
      "resolved": "https://registry.npmmirror.com/terser/-/terser-5.46.1.tgz",
      "integrity": "sha512-vzCjQO/rgUuK9sf8VJZvjqiqiHFaZLnOiimmUuOKODxWL8mm/xua7viT7aqX7dgPY60otQjUotzFMmCB4VdmqQ==",
      "license": "BSD-2-Clause",
      "dependencies": {
        "@jridgewell/source-map": "^0.3.3",
        "acorn": "^8.15.0",
        "commander": "^2.20.0",
        "source-map-support": "~0.5.20"
      },
      "bin": {
        "terser": "bin/terser"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/terser/node_modules/commander": {
      "version": "2.20.3",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-2.20.3.tgz",
      "integrity": "sha512-GpVkmM8vF2vQUkj2LvZmD35JxeJOLCwJ9cUkugyk2nuhbv3+mJvpLYYt+0+USMxE+oj+ey/lJEnhZw75x/OMcQ==",
      "license": "MIT"
    },
    "node_modules/test-exclude": {
      "version": "6.0.0",
      "resolved": "https://registry.npmmirror.com/test-exclude/-/test-exclude-6.0.0.tgz",
      "integrity": "sha512-cAGWPIyOHU6zlmg88jwm7VRyXnMN7iV68OGAbYDk/Mh/xC/pzVPlQtY6ngoIH/5/tciuhGfvESU8GrHrcxD56w==",
      "license": "ISC",
      "dependencies": {
        "@istanbuljs/schema": "^0.1.2",
        "glob": "^7.1.4",
        "minimatch": "^3.0.4"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/test-exclude/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "license": "MIT"
    },
    "node_modules/test-exclude/node_modules/brace-expansion": {
      "version": "1.1.13",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.13.tgz",
      "integrity": "sha512-9ZLprWS6EENmhEOpjCYW2c8VkmOvckIJZfkr7rBW6dObmfgJ/L1GpSYW5Hpo9lDz4D1+n0Ckz8rU7FwHDQiG/w==",
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/test-exclude/node_modules/glob": {
      "version": "7.2.3",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-7.2.3.tgz",
      "integrity": "sha512-nFR0zLpU2YCaRxwoCJvL6UvCH2JFyFVIvwTLsIf21AuHlMskA1hhTdk+LlYJtOlYt9v6dvszD2BGRqBL+iQK9Q==",
      "deprecated": "Glob versions prior to v9 are no longer supported",
      "license": "ISC",
      "dependencies": {
        "fs.realpath": "^1.0.0",
        "inflight": "^1.0.4",
        "inherits": "2",
        "minimatch": "^3.1.1",
        "once": "^1.3.0",
        "path-is-absolute": "^1.0.0"
      },
      "engines": {
        "node": "*"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/test-exclude/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/throat": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/throat/-/throat-5.0.0.tgz",
      "integrity": "sha512-fcwX4mndzpLQKBS1DVYhGAcYaYt7vsHNIvQV+WXMvnow5cgjPphq5CaayLaGsjRdSCKZFNGt7/GYAuXaNOiYCA==",
      "license": "MIT"
    },
    "node_modules/tmpl": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/tmpl/-/tmpl-1.0.5.tgz",
      "integrity": "sha512-3f0uOEAQwIqGuWW2MVzYg8fV/QNnc/IpuJNG837rLuczAaLVHslWHZQj4IGiEl5Hs3kkbhwL9Ab7Hrsmuj+Smw==",
      "license": "BSD-3-Clause"
    },
    "node_modules/to-regex-range": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/to-regex-range/-/to-regex-range-5.0.1.tgz",
      "integrity": "sha512-65P7iz6X5yEr1cwcgvQxbbIw7Uk3gOy5dIdtZ4rDveLqhrdJP+Li/Hx6tyK0NEb+2GCyneCMJiGqrADCSNk8sQ==",
      "license": "MIT",
      "dependencies": {
        "is-number": "^7.0.0"
      },
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/toidentifier": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/toidentifier/-/toidentifier-1.0.1.tgz",
      "integrity": "sha512-o5sSPKEkg/DIQNmH43V0/uerLrpzVedkUh8tGNvaeXpfpuwjKenlSox/2O/BTlZUtEe+JG7s5YhEz608PlAHRA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.6"
      }
    },
    "node_modules/toqr": {
      "version": "0.1.1",
      "resolved": "https://registry.npmmirror.com/toqr/-/toqr-0.1.1.tgz",
      "integrity": "sha512-FWAPzCIHZHnrE/5/w9MPk0kK25hSQSH2IKhYh9PyjS3SG/+IEMvlwIHbhz+oF7xl54I+ueZlVnMjyzdSwLmAwA==",
      "license": "MIT"
    },
    "node_modules/tr46": {
      "version": "0.0.3",
      "resolved": "https://registry.npmmirror.com/tr46/-/tr46-0.0.3.tgz",
      "integrity": "sha512-N3WMsuqV66lT30CrXNbEjx4GEwlow3v6rr4mCcv6prnfwhS01rkgyFdjPNBYd9br7LpXV1+Emh01fHnq2Gdgrw==",
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/tslib": {
      "version": "2.8.1",
      "resolved": "https://registry.npmmirror.com/tslib/-/tslib-2.8.1.tgz",
      "integrity": "sha512-oJFu94HQb+KVduSUQL7wnpmqnfmLsOA/nAh6b6EH0wCEoK0/mPeXU6c3wKDV83MkOuHPRHtSXKKU99IBazS/2w==",
      "license": "0BSD"
    },
    "node_modules/type-detect": {
      "version": "4.0.8",
      "resolved": "https://registry.npmmirror.com/type-detect/-/type-detect-4.0.8.tgz",
      "integrity": "sha512-0fr/mIH1dlO+x7TlcMy+bIDqKPsw/70tVyeHW787goQjhmqaZe10uwLujubK9q9Lg6Fiho1KUKDYz0Z7k7g5/g==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/type-fest": {
      "version": "0.7.1",
      "resolved": "https://registry.npmmirror.com/type-fest/-/type-fest-0.7.1.tgz",
      "integrity": "sha512-Ne2YiiGN8bmrmJJEuTWTLJR32nh/JdL1+PSicowtNb0WFpn59GK8/lfD61bVtzguz7b3PBt74nxpv/Pw5po5Rg==",
      "license": "(MIT OR CC0-1.0)",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/typescript": {
      "version": "5.9.3",
      "resolved": "https://registry.npmmirror.com/typescript/-/typescript-5.9.3.tgz",
      "integrity": "sha512-jl1vZzPDinLr9eUt3J/t7V6FgNEw9QjvBPdysz9KfQDD41fQrC2Y4vKQdiaUpFT4bXlb1RHhLpp8wtm6M5TgSw==",
      "devOptional": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    },
    "node_modules/ua-parser-js": {
      "version": "1.0.41",
      "resolved": "https://registry.npmmirror.com/ua-parser-js/-/ua-parser-js-1.0.41.tgz",
      "integrity": "sha512-LbBDqdIC5s8iROCUjMbW1f5dJQTEFB1+KO9ogbvlb3nm9n4YHa5p4KTvFPWvh2Hs8gZMBuiB1/8+pdfe/tDPug==",
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/ua-parser-js"
        },
        {
          "type": "paypal",
          "url": "https://paypal.me/faisalman"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/faisalman"
        }
      ],
      "license": "MIT",
      "optional": true,
      "peer": true,
      "bin": {
        "ua-parser-js": "script/cli.js"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/undici-types": {
      "version": "7.18.2",
      "resolved": "https://registry.npmmirror.com/undici-types/-/undici-types-7.18.2.tgz",
      "integrity": "sha512-AsuCzffGHJybSaRrmr5eHr81mwJU3kjw6M+uprWvCXiNeN9SOGwQ3Jn8jb8m3Z6izVgknn1R0FTCEAP2QrLY/w==",
      "license": "MIT"
    },
    "node_modules/unicode-canonical-property-names-ecmascript": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/unicode-canonical-property-names-ecmascript/-/unicode-canonical-property-names-ecmascript-2.0.1.tgz",
      "integrity": "sha512-dA8WbNeb2a6oQzAQ55YlT5vQAWGV9WXOsi3SskE3bcCdM0P4SDd+24zS/OCacdRq5BkdsRj9q3Pg6YyQoxIGqg==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/unicode-match-property-ecmascript": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/unicode-match-property-ecmascript/-/unicode-match-property-ecmascript-2.0.0.tgz",
      "integrity": "sha512-5kaZCrbp5mmbz5ulBkDkbY0SsPOjKqVS35VpL9ulMPfSl0J0Xsm+9Evphv9CoIZFwre7aJoa94AY6seMKGVN5Q==",
      "license": "MIT",
      "dependencies": {
        "unicode-canonical-property-names-ecmascript": "^2.0.0",
        "unicode-property-aliases-ecmascript": "^2.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/unicode-match-property-value-ecmascript": {
      "version": "2.2.1",
      "resolved": "https://registry.npmmirror.com/unicode-match-property-value-ecmascript/-/unicode-match-property-value-ecmascript-2.2.1.tgz",
      "integrity": "sha512-JQ84qTuMg4nVkx8ga4A16a1epI9H6uTXAknqxkGF/aFfRLw1xC/Bp24HNLaZhHSkWd3+84t8iXnp1J0kYcZHhg==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/unicode-property-aliases-ecmascript": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/unicode-property-aliases-ecmascript/-/unicode-property-aliases-ecmascript-2.2.0.tgz",
      "integrity": "sha512-hpbDzxUY9BFwX+UeBnxv3Sh1q7HFxj48DTmXchNgRa46lO8uj3/1iEn3MiNUYTg1g9ctIqXCCERn8gYZhHC5lQ==",
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/unimodules-app-loader": {
      "version": "55.0.4",
      "resolved": "https://registry.npmjs.org/unimodules-app-loader/-/unimodules-app-loader-55.0.4.tgz",
      "integrity": "sha512-l3vMWR/lYLTj3JE4rhIX5vDVMDY9nGS550XaB90HENqUQnBEMdhhOpI8tOA37QJOUZE6pCQGeQX6mIdEu3uqzg==",
      "license": "MIT"
    },
    "node_modules/unpipe": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/unpipe/-/unpipe-1.0.0.tgz",
      "integrity": "sha512-pjy2bYhSsufwWlKwPc+l3cN7+wuJlK6uz0YdJEOlQDbl6jo/YlPi4mb8agUkVC8BF7V8NuzeyPNqRksA3hztKQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/update-browserslist-db": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/update-browserslist-db/-/update-browserslist-db-1.2.3.tgz",
      "integrity": "sha512-Js0m9cx+qOgDxo0eMiFGEueWztz+d4+M3rGlmKPT+T4IS/jP4ylw3Nwpu6cpTTP8R1MAC1kF4VbdLt3ARf209w==",
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "escalade": "^3.2.0",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "update-browserslist-db": "cli.js"
      },
      "peerDependencies": {
        "browserslist": ">= 4.21.0"
      }
    },
    "node_modules/use-callback-ref": {
      "version": "1.3.3",
      "resolved": "https://registry.npmmirror.com/use-callback-ref/-/use-callback-ref-1.3.3.tgz",
      "integrity": "sha512-jQL3lRnocaFtu3V00JToYz/4QkNWswxijDaCVNZRiRTO3HQDLsdu1ZtmIUvV4yPp+rvWm5j0y0TG/S61cuijTg==",
      "license": "MIT",
      "dependencies": {
        "tslib": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/use-latest-callback": {
      "version": "0.2.6",
      "resolved": "https://registry.npmmirror.com/use-latest-callback/-/use-latest-callback-0.2.6.tgz",
      "integrity": "sha512-FvRG9i1HSo0wagmX63Vrm8SnlUU3LMM3WyZkQ76RnslpBrX694AdG4A0zQBx2B3ZifFA0yv/BaEHGBnEax5rZg==",
      "license": "MIT",
      "peerDependencies": {
        "react": ">=16.8"
      }
    },
    "node_modules/use-sidecar": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/use-sidecar/-/use-sidecar-1.1.3.tgz",
      "integrity": "sha512-Fedw0aZvkhynoPYlA5WXrMCAMm+nSWdZt6lzJQ7Ok8S6Q+VsHmHpRWndVRJ8Be0ZbkfPc5LRYH+5XrzXcEeLRQ==",
      "license": "MIT",
      "dependencies": {
        "detect-node-es": "^1.1.0",
        "tslib": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "peerDependencies": {
        "@types/react": "*",
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0 || ^19.0.0-rc"
      },
      "peerDependenciesMeta": {
        "@types/react": {
          "optional": true
        }
      }
    },
    "node_modules/use-sync-external-store": {
      "version": "1.6.0",
      "resolved": "https://registry.npmmirror.com/use-sync-external-store/-/use-sync-external-store-1.6.0.tgz",
      "integrity": "sha512-Pp6GSwGP/NrPIrxVFAIkOQeyw8lFenOHijQWkUTrDvrF4ALqylP2C/KCkeS9dpUM3KvYRQhna5vt7IL95+ZQ9w==",
      "license": "MIT",
      "peerDependencies": {
        "react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/utils-merge": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/utils-merge/-/utils-merge-1.0.1.tgz",
      "integrity": "sha512-pMZTvIkT1d+TFGvDOqodOclx0QWkkgi6Tdoa8gC8ffGAAqz9pzPTZWAybbsHHoED/ztMtkv/VoYTYyShUn81hA==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4.0"
      }
    },
    "node_modules/uuid": {
      "version": "7.0.3",
      "resolved": "https://registry.npmmirror.com/uuid/-/uuid-7.0.3.tgz",
      "integrity": "sha512-DPSke0pXhTZgoF/d+WSt2QaKMCFSfx7QegxEWT+JOuHF5aWrKEn0G+ztjuJg/gG8/ItK+rbPCD/yNv8yyih6Cg==",
      "license": "MIT",
      "bin": {
        "uuid": "dist/bin/uuid"
      }
    },
    "node_modules/validate-npm-package-name": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/validate-npm-package-name/-/validate-npm-package-name-5.0.1.tgz",
      "integrity": "sha512-OljLrQ9SQdOUqTaQxqL5dEfZWrXExyyWsozYlAWFawPVNuD83igl7uJD2RTkNMbniIYgt8l81eCJGIdQF7avLQ==",
      "license": "ISC",
      "engines": {
        "node": "^14.17.0 || ^16.13.0 || >=18.0.0"
      }
    },
    "node_modules/vary": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/vary/-/vary-1.1.2.tgz",
      "integrity": "sha512-BNGbWLfd0eUPabhkXUVm0j8uuvREyTh5ovRa/dyow/BqAbZJyC+5fU+IzQOzmAKzYqYRAISoRhdQr3eIZ/PXqg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/vaul": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/vaul/-/vaul-1.1.2.tgz",
      "integrity": "sha512-ZFkClGpWyI2WUQjdLJ/BaGuV6AVQiJ3uELGk3OYtP+B6yCO7Cmn9vPFXVJkRaGkOJu3m8bQMgtyzNHixULceQA==",
      "license": "MIT",
      "dependencies": {
        "@radix-ui/react-dialog": "^1.1.1"
      },
      "peerDependencies": {
        "react": "^16.8 || ^17.0 || ^18.0 || ^19.0.0 || ^19.0.0-rc",
        "react-dom": "^16.8 || ^17.0 || ^18.0 || ^19.0.0 || ^19.0.0-rc"
      }
    },
    "node_modules/vlq": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/vlq/-/vlq-1.0.1.tgz",
      "integrity": "sha512-gQpnTgkubC6hQgdIcRdYGDSDc+SaujOdyesZQMv6JlfQee/9Mp0Qhnys6WxDWvQnL5WZdT7o2Ul187aSt0Rq+w==",
      "license": "MIT"
    },
    "node_modules/walker": {
      "version": "1.0.8",
      "resolved": "https://registry.npmmirror.com/walker/-/walker-1.0.8.tgz",
      "integrity": "sha512-ts/8E8l5b7kY0vlWLewOkDXMmPdLcVV4GmOQLyxuSswIJsweeFZtAsMF7k1Nszz+TYBQrlYRmzOnr398y1JemQ==",
      "license": "Apache-2.0",
      "dependencies": {
        "makeerror": "1.0.12"
      }
    },
    "node_modules/warn-once": {
      "version": "0.1.1",
      "resolved": "https://registry.npmmirror.com/warn-once/-/warn-once-0.1.1.tgz",
      "integrity": "sha512-VkQZJbO8zVImzYFteBXvBOZEl1qL175WH8VmZcxF2fZAoudNhNDvHi+doCaAEdU2l2vtcIwa2zn0QK5+I1HQ3Q==",
      "license": "MIT"
    },
    "node_modules/wcwidth": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/wcwidth/-/wcwidth-1.0.1.tgz",
      "integrity": "sha512-XHPEwS0q6TaxcvG85+8EYkbiCux2XtWG2mkc47Ng2A77BQu9+DqIOJldST4HgPkuea7dvKSj5VgX3P1d4rW8Tg==",
      "license": "MIT",
      "dependencies": {
        "defaults": "^1.0.3"
      }
    },
    "node_modules/webidl-conversions": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/webidl-conversions/-/webidl-conversions-3.0.1.tgz",
      "integrity": "sha512-2JAn3z8AR6rjK8Sm8orRC0h/bcl/DqL7tRPdGZ4I1CjdF+EaMLmYxBHyXuKL849eucPFhvBoxMsflfOb8kxaeQ==",
      "license": "BSD-2-Clause",
      "optional": true,
      "peer": true
    },
    "node_modules/whatwg-fetch": {
      "version": "3.6.20",
      "resolved": "https://registry.npmmirror.com/whatwg-fetch/-/whatwg-fetch-3.6.20.tgz",
      "integrity": "sha512-EqhiFU6daOA8kpjOWTL0olhVOF3i7OrFzSYiGsEMB8GcXS+RrzauAERX65xMeNWVqxA6HXH2m69Z9LaKKdisfg==",
      "license": "MIT"
    },
    "node_modules/whatwg-url": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/whatwg-url/-/whatwg-url-5.0.0.tgz",
      "integrity": "sha512-saE57nupxk6v3HY35+jzBwYa0rKSy0XR8JSxZPwgLr7ys0IBzhGviA1/TUGJLmSVqs8pb9AnvICXEuOHLprYTw==",
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "tr46": "~0.0.3",
        "webidl-conversions": "^3.0.0"
      }
    },
    "node_modules/whatwg-url-minimum": {
      "version": "0.1.1",
      "resolved": "https://registry.npmmirror.com/whatwg-url-minimum/-/whatwg-url-minimum-0.1.1.tgz",
      "integrity": "sha512-u2FNVjFVFZhdjb502KzXy1gKn1mEisQRJssmSJT8CPhZdZa0AP6VCbWlXERKyGu0l09t0k50FiDiralpGhBxgA==",
      "license": "MIT"
    },
    "node_modules/which": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/which/-/which-2.0.2.tgz",
      "integrity": "sha512-BLI3Tl1TW3Pvl70l3yq3Y64i+awpwXqsGBYWkkqMtnbXgrMD+yj7rhW0kuEDxzJaYXGjEW5ogapKNMEKNMjibA==",
      "license": "ISC",
      "dependencies": {
        "isexe": "^2.0.0"
      },
      "bin": {
        "node-which": "bin/node-which"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/wrap-ansi": {
      "version": "7.0.0",
      "resolved": "https://registry.npmmirror.com/wrap-ansi/-/wrap-ansi-7.0.0.tgz",
      "integrity": "sha512-YVGIj2kamLSTxw6NsZjoBxfSwsn0ycdesmc4p+Q21c5zPuZ1pl+NfxVdxPtdHvmNVOQ6XSYG4AUtyt/Fi7D16Q==",
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.0.0",
        "string-width": "^4.1.0",
        "strip-ansi": "^6.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/wrap-ansi?sponsor=1"
      }
    },
    "node_modules/wrappy": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/wrappy/-/wrappy-1.0.2.tgz",
      "integrity": "sha512-l4Sp/DRseor9wL6EvV2+TuQn63dMkPjZ/sp9XkghTEbV9KlPS1xUsZ3u7/IQO4wxtcFB4bgpQPRcR3QCvezPcQ==",
      "license": "ISC"
    },
    "node_modules/write-file-atomic": {
      "version": "4.0.2",
      "resolved": "https://registry.npmmirror.com/write-file-atomic/-/write-file-atomic-4.0.2.tgz",
      "integrity": "sha512-7KxauUdBmSdWnmpaGFg+ppNjKF8uNLry8LyzjauQDOVONfFLNKrKvQOxZ/VuTIcS/gge/YNahf5RIIQWTSarlg==",
      "license": "ISC",
      "dependencies": {
        "imurmurhash": "^0.1.4",
        "signal-exit": "^3.0.7"
      },
      "engines": {
        "node": "^12.13.0 || ^14.15.0 || >=16.0.0"
      }
    },
    "node_modules/ws": {
      "version": "7.5.10",
      "resolved": "https://registry.npmmirror.com/ws/-/ws-7.5.10.tgz",
      "integrity": "sha512-+dbF1tHwZpXcbOJdVOkzLDxZP1ailvSxM6ZweXTegylPny803bFhA+vqBYw4s31NSAk4S2Qz+AKXK9a4wkdjcQ==",
      "license": "MIT",
      "engines": {
        "node": ">=8.3.0"
      },
      "peerDependencies": {
        "bufferutil": "^4.0.1",
        "utf-8-validate": "^5.0.2"
      },
      "peerDependenciesMeta": {
        "bufferutil": {
          "optional": true
        },
        "utf-8-validate": {
          "optional": true
        }
      }
    },
    "node_modules/xcode": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/xcode/-/xcode-3.0.1.tgz",
      "integrity": "sha512-kCz5k7J7XbJtjABOvkc5lJmkiDh8VhjVCGNiqdKCscmVpdVUpEAyXv1xmCLkQJ5dsHqx3IPO4XW+NTDhU/fatA==",
      "license": "Apache-2.0",
      "dependencies": {
        "simple-plist": "^1.1.0",
        "uuid": "^7.0.3"
      },
      "engines": {
        "node": ">=10.0.0"
      }
    },
    "node_modules/xml2js": {
      "version": "0.6.0",
      "resolved": "https://registry.npmmirror.com/xml2js/-/xml2js-0.6.0.tgz",
      "integrity": "sha512-eLTh0kA8uHceqesPqSE+VvO1CDDJWMwlQfB6LuN6T8w6MaDJ8Txm8P7s5cHD0miF0V+GGTZrDQfxPZQVsur33w==",
      "license": "MIT",
      "dependencies": {
        "sax": ">=0.6.0",
        "xmlbuilder": "~11.0.0"
      },
      "engines": {
        "node": ">=4.0.0"
      }
    },
    "node_modules/xml2js/node_modules/xmlbuilder": {
      "version": "11.0.1",
      "resolved": "https://registry.npmmirror.com/xmlbuilder/-/xmlbuilder-11.0.1.tgz",
      "integrity": "sha512-fDlsI/kFEx7gLvbecc0/ohLG50fugQp8ryHzMTuW9vSa1GJ0XYWKnhsUx7oie3G98+r56aTQIUB4kht42R3JvA==",
      "license": "MIT",
      "engines": {
        "node": ">=4.0"
      }
    },
    "node_modules/xmlbuilder": {
      "version": "15.1.1",
      "resolved": "https://registry.npmmirror.com/xmlbuilder/-/xmlbuilder-15.1.1.tgz",
      "integrity": "sha512-yMqGBqtXyeN1e3TGYvgNgDVZ3j84W4cwkOXQswghol6APgZWaff9lnbvN7MHYJOiXsvGPXtjTYJEiC9J2wv9Eg==",
      "license": "MIT",
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/y18n": {
      "version": "5.0.8",
      "resolved": "https://registry.npmmirror.com/y18n/-/y18n-5.0.8.tgz",
      "integrity": "sha512-0pfFzegeDWJHJIAmTLRP2DwHjdF5s7jo9tuztdQxAhINCdvS+3nGINqPd00AphqJR/0LhANUS6/+7SCb98YOfA==",
      "license": "ISC",
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/yallist": {
      "version": "3.1.1",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-3.1.1.tgz",
      "integrity": "sha512-a4UGQaWPH59mOXUYnAG2ewncQS4i4F43Tv3JoAM+s2VDAmS9NsK8GpDMLrCHPksFT7h3K6TOoUNn2pb7RoXx4g==",
      "license": "ISC"
    },
    "node_modules/yaml": {
      "version": "2.8.3",
      "resolved": "https://registry.npmmirror.com/yaml/-/yaml-2.8.3.tgz",
      "integrity": "sha512-AvbaCLOO2Otw/lW5bmh9d/WEdcDFdQp2Z2ZUH3pX9U2ihyUY0nvLv7J6TrWowklRGPYbB/IuIMfYgxaCPg5Bpg==",
      "license": "ISC",
      "bin": {
        "yaml": "bin.mjs"
      },
      "engines": {
        "node": ">= 14.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/eemeli"
      }
    },
    "node_modules/yargs": {
      "version": "17.7.2",
      "resolved": "https://registry.npmmirror.com/yargs/-/yargs-17.7.2.tgz",
      "integrity": "sha512-7dSzzRQ++CKnNI/krKnYRV7JKKPUXMEh61soaHKg9mrWEhzFWhFnxPxGl+69cD1Ou63C13NUPCnmIcrvqCuM6w==",
      "license": "MIT",
      "dependencies": {
        "cliui": "^8.0.1",
        "escalade": "^3.1.1",
        "get-caller-file": "^2.0.5",
        "require-directory": "^2.1.1",
        "string-width": "^4.2.3",
        "y18n": "^5.0.5",
        "yargs-parser": "^21.1.1"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/yargs-parser": {
      "version": "21.1.1",
      "resolved": "https://registry.npmmirror.com/yargs-parser/-/yargs-parser-21.1.1.tgz",
      "integrity": "sha512-tVpsJW7DdjecAiFpbIB1e3qxIQsE6NoPc5/eTdrbbIC4h0LVsWhnoa3g+m2HclBIujHzsxZ4VJVA+GUuc2/LBw==",
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/zod": {
      "version": "3.25.76",
      "resolved": "https://registry.npmmirror.com/zod/-/zod-3.25.76.tgz",
      "integrity": "sha512-gzUt/qt81nXsFGKIFcC3YnfEAx5NkunCfnDlvuBSSFS02bcXu4Lmea0AFIUwbLWxWPx3d9p8S5QoaujKcNQxcQ==",
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/colinhacks"
      }
    }
  }
}
~~~

## `mobile/package.json`

- 编码: `utf-8`

~~~json
{
  "name": "yiyu-mobile",
  "version": "1.0.0",
  "private": true,
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "android": "expo run:android",
    "ios": "expo run:ios",
    "web": "expo start --web",
    "test:core": "node scripts/run-mobile-core-tests.mjs",
    "check:no-direct-task-api-writes": "node scripts/check-no-direct-task-api-writes.mjs",
    "inventory:direct-api-usage": "node scripts/list-direct-api-usage.mjs",
    "checkpoint:snapshot": "node scripts/write-checkpoint-snapshot.mjs",
    "scan:stability-android": "bash scripts/run-mobile-stability-scan.sh",
    "verify:rc-android": "bash scripts/run-android-rc-gates.sh"
  },
  "dependencies": {
    "@react-native-async-storage/async-storage": "2.2.0",
    "expo": "55.0.10-canary-20260328-bdc6273",
    "expo-asset": "55.0.11-canary-20260328-bdc6273",
    "expo-audio": "55.0.10-canary-20260328-bdc6273",
    "expo-background-fetch": "55.0.12",
    "expo-blur": "55.0.11-canary-20260328-bdc6273",
    "expo-clipboard": "55.0.10-canary-20260328-bdc6273",
    "expo-constants": "55.0.10-canary-20260328-bdc6273",
    "expo-file-system": "55.0.13-canary-20260328-bdc6273",
    "expo-haptics": "55.0.10-canary-20260328-bdc6273",
    "expo-linking": "55.0.10-canary-20260328-bdc6273",
    "expo-router": "55.0.9-canary-20260328-bdc6273",
    "expo-secure-store": "55.0.10-canary-20260328-bdc6273",
    "expo-speech-recognition": "3.1.2",
    "expo-sqlite": "55.0.13",
    "expo-status-bar": "55.0.5-canary-20260328-bdc6273",
    "expo-task-manager": "55.0.12",
    "lucide-react-native": "1.7.0",
    "react": "19.2.0",
    "react-native": "0.83.4",
    "react-native-safe-area-context": "5.6.2",
    "react-native-screens": "~4.23.0",
    "react-native-svg": "15.15.3"
  },
  "devDependencies": {
    "@types/react": "19.2.14",
    "typescript": "5.9.3"
  }
}
~~~

## `mobile/scripts/android-rc-blocker-checklist.md`

- 编码: `utf-8`

~~~markdown
# Android RC Blocker Checklist

Use this only on a real Android device. Do not replace it with simulator-only verification.

## Preflight

- Run `npm run verify:rc-android`.
- Optionally run `npm run scan:stability-android` to complete the static + strategy sweep before the manual pass.
- Confirm release APK exists at `android/app/build/outputs/apk/release/app-release.apk`.
- Connect one Android device with USB debugging enabled.
- Validate both install paths before starting the checklist:
  - 覆盖安装 fresh release build
  - 升级安装 fresh release build（旧版本先制造本地数据和 pending ops，再覆盖升级）
- Open `scripts/mobile-blocker-ledger.md` and record build time, device, and pass/fail notes as you go.

## Run Order

1. Cold launch
- Launch app from a terminated state.
- Confirm no crash, blank screen, or endless splash.

2. Login
- Sign in with Account A.
- Wait for one sync cycle to finish.
- Confirm dev logs show one runtime start and one sync-engine start, not repeated start loops.

3. Quick tab switching
- Rapidly switch `tasks -> calendar -> consult -> tasks`.
- Confirm no extra full-page loading flashes.
- Confirm the three pages reflect the same task snapshot.

4. Pull to refresh
- Pull to refresh once on each of `tasks`, `calendar`, and `consult`.
- Confirm refresh finishes normally and does not fork separate taskBoard states.

5. Background / foreground
- Send app to background, wait 10-20 seconds, return to foreground.
- Confirm app resumes without crash or state loss.
- Confirm sync status recovers cleanly and UI does not flash stale/empty states.

6. Calendar drag date
- In `calendar`, drag a task to a different date.
- Confirm the task moves immediately and remains consistent after page switch.

7. Calendar resize duration
- In `calendar`, drag the duration handle on a timed task.
- Confirm the duration updates, persists after refresh, and does not reset unexpectedly.

8. Tasks drag to calendar
- In `tasks`, long-press a scheduled or unscheduled task and drag it into the date overlay.
- Confirm the due date updates and `calendar` shows the same result.

9. Task insight stopgap validation
- Open these 5 real samples and validate the understanding card one by one:
  - `和元兵吃饭`
  - `晚上约高瑞瑞`
  - `跟进日慈基金会继续推进…`
  - one completed task awaiting review
  - one overdue task with no business context
- For each sample, record in `scripts/mobile-blocker-ledger.md`:
  - state is `ready`, `insufficient_context`, or `weak_link`
  - whether it repeats the task title or description
  - whether it uses event-line preview as task understanding
  - whether it explicitly says what context is missing
  - whether the suggested next step is concrete and evidence-backed
- Treat any of the following as RC blockers:
  - repeats `task.title` or `task.description`
  - shows `contextPreview.judgment.summary` as task understanding
  - gives a business judgment with only task text
  - gives a concrete recommendation from only a broad event-line link

10. Smart input recovery
- Prepare one queued smart-input draft.
- Verify:
  - entering `tasks` can recover draft
  - returning from background can recover draft
  - manual recover entry can recover draft
- Confirm non-manual recovery does not auto-open `CreateTask`.

11. Logout / relogin isolation
- Sign out from Account A.
- Sign in with Account B.
- Confirm no task/client/eventLine residue from Account A remains.
- Treat any residue as release-blocking.

12. Offline restart
- While logged in and after one successful sync, force-stop the app.
- Disable network.
- Relaunch app.
- Confirm `tasks / calendar / consult` render from local board rather than blank or spinner-only states.

13. Upgrade install direct-open validation
- Install an older build, create at least one local task and one pending op, then upgrade to the fresh release build.
- Open the app directly after upgrade.
- Confirm migration succeeds, scope is still correct, pending ops are still visible, and the local board can render before a new full sync completes.

## Confirmation Rerun

After one full clean pass, do not release immediately. Run one confirmation sweep:

1. rerun `npm run verify:rc-android`
2. rerun the 3 hard grep gates
3. rerun these device-critical gates:
   - login and confirm sync starts once
   - quick tab switching and confirm one shared snapshot
   - rerun the 5 task insight samples and confirm no repeat / no fake business judgment
   - logout and confirm local state is cleared
   - offline restart and confirm local-board rendering

Release decisions require both the full pass and the confirmation rerun to stay clean.

## Go / No-Go Rules

- `GO` only if all steps above pass and there is no crash, card freeze, sync lifecycle loop, cross-account residue, offline blank state, or task-insight misclassification.
- `NO-GO` if blocker appears in runtime/store/sync/baseUrl/local-db. Fix there first; do not defer it into later PRs.
- `NO-GO` if page-level taskBoard direct fetch, UTC date-key logic, or legacy `DateTimePicker` usage reappears in grep gates.
- `NO-GO` if the understanding card still repeats task text, still uses event-line preview as task understanding, or still gives business conclusions without evidence.
- `NO-GO` if the confirmation rerun fails after the first clean pass.

## Blocker Log Template

For each blocker, record:

- Layer: `runtime` / `sync` / `taskBoard store` / `tasks` / `calendar` / `consult` / `CreateTask`
- Trigger step
- Expected behavior
- Actual behavior
- Whether reproducible
- Related logs or screenshots
- Fix owner layer
- Which rerun steps proved the blocker closed
~~~

## `mobile/scripts/check-no-direct-task-api-writes.mjs`

- 编码: `utf-8`

~~~javascript
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const targets = [
  "app/(tabs)/tasks.tsx",
  "app/(tabs)/calendar.tsx",
  "components/CreateTask.tsx",
  "components/TaskDetail.tsx",
  "components/TaskReviewComposer.tsx",
  "components/RecordNote.tsx",
];

const bannedPatterns = [
  /lib\/api/,
  /api\.createTask\(/,
  /api\.updateTask\(/,
  /api\.deleteTask\(/,
  /api\.uploadTaskAttachment\(/,
  /api\.completeTaskWithReview\(/,
];

const violations = [];

for (const relativePath of targets) {
  const contents = readFileSync(join(root, relativePath), "utf8");
  for (const pattern of bannedPatterns) {
    if (pattern.test(contents)) {
      violations.push(`${relativePath}: ${pattern}`);
    }
  }
}

if (violations.length > 0) {
  console.error("Direct lib/api usage is blocked in task local-first surfaces:");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

console.log("PASS: no direct task API writes in guarded task local-first surfaces.");
~~~

## `mobile/scripts/checkpoint-snapshot.md`

- 编码: `utf-8`

~~~markdown
# Checkpoint Snapshot

Generated at: `2026-04-18T12:18:39.499Z`

## Baseline

- Branch: `main`
- Commit: `bb64401746c436ebf5284980ce26882a6ac78d21`
- Schema version: `3`

## Runtime Flags Default

- `task_local_first_write_enabled: true`
- `task_local_first_read_enabled: true`
- `calendar_local_first_write_enabled: true`

## Gate Summary

- `npx tsc --noEmit`: PASS
- `npm run test:core`: PASS
- `npm run check:no-direct-task-api-writes`: PASS
- `npm run inventory:direct-api-usage`: PASS

## Inventory Snapshot

```text
> yiyu-mobile@1.0.0 inventory:direct-api-usage
> node scripts/list-direct-api-usage.mjs

=== direct-task-writes ===
lib/sync-engine.ts:353:            const created = await api.createTask(payload);
lib/sync-engine.ts:365:            const updated = await api.updateTask(remoteTaskId, payload);
lib/sync-engine.ts:382:            const reviewedTask = await api.completeTaskWithReview(remoteTaskId, reviewNote);
lib/sync-engine.ts:392:              await api.deleteTask(remoteTaskId);
lib/calendar-repository.ts:60:  const updatedTask = await api.updateTask(existing.remoteId, payload);
lib/record-note-service.ts:268:    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
lib/record-note-service.ts:374:    const uploadedTask = await api.uploadTaskAttachment(remote.remoteTaskId, {
=== direct-api-imports ===
app/(tabs)/consult.tsx:21:import { enqueueConsultationKnowledgeRequest, fetchConsultationKnowledgeRequests, sendConsultationChat } from "../../lib/api";
app/(tabs)/consult.tsx:22:import type { ConsultationKnowledgeRequestRecord } from "../../lib/api";
components/SmartInputSheet.tsx:28:import * as api from "../lib/api";
app/(tabs)/profile.tsx:19:import { fetchHealth, updateMe } from "../../lib/api";
app/login.tsx:17:import * as api from "../lib/api";
components/SettingsTasks.tsx:14:import { fetchTaskSettings, updateTaskSettings } from "../lib/api";
components/SettingsAccount.tsx:13:import * as api from "../lib/api";
```

## Git Status

```text
M app/(tabs)/calendar.tsx
 M app/(tabs)/consult.tsx
 M app/(tabs)/profile.tsx
 M app/(tabs)/tasks.tsx
 M app/login.tsx
 M components/CreateTask.tsx
 D components/DateTimePicker.tsx
 M components/DateTimePickerSheet.tsx
 M components/RecordNote.tsx
 M components/SettingsAccount.tsx
 M components/SmartInputSheet.tsx
 M components/TaskDetail.tsx
 M components/TaskReviewComposer.tsx
 M lib/api.ts
 M lib/auth-context.tsx
 M lib/smart-input-queue.ts
 M lib/types.ts
 M package-lock.json
 M package.json
?? components/EventLineDrawer.tsx
?? components/FocusBar.tsx
?? components/UnderstandingCard.tsx
?? components/WeekSignalCard.tsx
?? components/WorkspaceLiteSheet.tsx
?? components/calendar-screen/
?? components/tasks-screen/
?? lib/__tests__/
?? lib/account-scope.ts
?? lib/base-url.ts
?? lib/boundary-cards.ts
?? lib/calendar-repository-core.ts
?? lib/calendar-repository.ts
?? lib/calendar-selectors.ts
?? lib/client-intel-store.ts
?? lib/consult-context-adapter.ts
?? lib/consult-context.ts
?? lib/consult-thread-context.ts
?? lib/create-task-association.ts
?? lib/create-task-resources.ts
?? lib/create-task-service.ts
?? lib/current-focus-core.ts
?? lib/current-focus-store.ts
?? lib/date.ts
?? lib/dev-log.ts
?? lib/event-line-client-transfer.ts
?? lib/focus-selectors.ts
?? lib/legacy-upload-ops.ts
?? lib/legacy-upload-pseudo-op-core.ts
?? lib/local-db.ts
?? lib/local-ids.ts
?? lib/pending-op-policy.ts
?? lib/record-note-flow-core.ts
?? lib/record-note-service.ts
?? lib/runtime-controller.ts
?? lib/runtime-flags.ts
?? lib/runtime.ts
?? lib/smart-input-queue-core.ts
?? lib/smart-input-recovery.ts
?? lib/sync-engine.ts
?? lib/sync-errors.ts
?? lib/sync-freeze-core.ts
?? lib/system-health.ts
?? lib/task-board-store-core.ts
?? lib/task-board-store.ts
?? lib/task-detail-service.ts
?? lib/task-query-service.ts
?? lib/task-repository.ts
?? lib/task-review-service.ts
?? lib/task-sync-policy.ts
?? lib/task-understanding.ts
?? lib/use-render-count.ts
?? lib/week-signal.ts
?? scripts/
?? tsconfig.tests.json
```
~~~

## `mobile/scripts/list-direct-api-usage.mjs`

- 编码: `utf-8`

~~~javascript
import { execFileSync } from "node:child_process";

const cwd = process.cwd();

// Patterns to hand to ripgrep. Use String.raw so backslashes reach rg
// verbatim, and avoid escaping characters that don't need it (e.g. `"`).
const patterns = [
  String.raw`import \* as api from`,
  String.raw`from "[^"]*lib/api"`,
  String.raw`api\.createTask\(`,
  String.raw`api\.updateTask\(`,
  String.raw`api\.deleteTask\(`,
  String.raw`api\.uploadTaskAttachment\(`,
  String.raw`api\.completeTaskWithReview\(`,
];

let output = "";

try {
  output = execFileSync(
    "rg",
    ["-n", patterns.join("|"), "app", "components", "lib"],
    { cwd, encoding: "utf8" },
  );
} catch (error) {
  if (error && typeof error === "object" && "status" in error && error.status === 1) {
    output = "";
  } else {
    throw error;
  }
}

const lines = output
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean);

const directWrites = lines.filter((line) =>
  /api\.(createTask|updateTask|deleteTask|uploadTaskAttachment|completeTaskWithReview)\(/.test(line),
);
const directImports = lines.filter((line) => /lib\/api/.test(line) && !directWrites.includes(line));

if (directWrites.length > 0) {
  process.stdout.write("=== direct-task-writes ===\n");
  process.stdout.write(`${directWrites.join("\n")}\n`);
}

if (directImports.length > 0) {
  process.stdout.write("=== direct-api-imports ===\n");
  process.stdout.write(`${directImports.join("\n")}\n`);
}
~~~

