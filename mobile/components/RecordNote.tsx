import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Animated,
  PermissionsAndroid,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
import { Mic, Pause, Play, Trash2, Check } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { palette } from "../lib/theme";
import type { RecordedUploadableFile } from "../lib/record-note-service";
import { getAudioRecorderStartFailureMessage } from "../lib/audio-recorder-core";
import { prepareAudioRecorderWithGuard } from "../lib/audio-recorder-prepare-guard";
import { cloudTranscribeRecordingSession, saveTaskRecording, saveUnboundRecording } from "../lib/recording-session-service";
import type { TaskRecord } from "../lib/types";
import { useLocalSpeechRecognition } from "../lib/use-local-speech-recognition";
import { useSpeechRecognitionEvent } from "expo-speech-recognition";
import Waveform from "./Waveform";

function clampMeter(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

// 从转写文本取 ≤10 字标题；无文本（如 Android 系统识别不可用）退回时间串。
function buildAutoRecordingTitle(transcript: string | null | undefined, fallbackPrefix: string, formattedDuration: string): string {
  const text = (transcript ?? "").replace(/\s+/g, "").trim();
  if (text) {
    return text.slice(0, 10);
  }
  return `${fallbackPrefix} ${formattedDuration}`;
}

// ─── Types ─────────────────────────────────

interface RecordNoteProps {
  readonly onClose: () => void;
  readonly taskContext?: TaskRecord | null;
  readonly autoStart?: boolean;
  readonly onUploaded?: (task: TaskRecord) => void;
}

function fileExtensionFromMimeType(mimeType: string): string {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("aac") || mimeType.includes("mp4") || mimeType.includes("m4a")) return "m4a";
  if (mimeType.includes("mpeg")) return "mp3";
  return "webm";
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

function uploadableFileFromUri(uri: string, prefix: string): RecordedUploadableFile {
  const cleanUri = uri.split("?")[0];
  const extension = (cleanUri.split(".").pop() || "m4a").toLowerCase();
  return {
    uri,
    name: `${prefix}-${Date.now()}.${extension}`,
    type: inferMimeTypeFromUri(cleanUri),
  };
}

// ─── Component ──────────────────────────────

export default function RecordNote({
  onClose,
  taskContext = null,
  autoStart = false,
  onUploaded,
}: RecordNoteProps) {
  const chrome = useAppChromeInsets();
  const isTaskMode = Boolean(taskContext);

  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [hasStartedRecording, setHasStartedRecording] = useState(false);
  const [androidSpeechRecordingActive, setAndroidSpeechRecordingActive] = useState(false);
  // 系统语音识别实时音量(value 约 -2~10, <0 听不见)，用来驱动声波随说话跳动。
  const [speechVolume, setSpeechVolume] = useState(0);

  const nativeRecorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const nativeRecorderState = useAudioRecorderState(nativeRecorder, 120);
  const {
    startLocalSpeechRecognition,
    stopLocalSpeechRecognition,
    cancelLocalSpeechRecognition,
  } = useLocalSpeechRecognition();
  // 订阅系统语音识别的实时音量事件，驱动声波随说话跳动（系统识别无 metering 时的真实音量来源）。
  useSpeechRecognitionEvent("volumechange", (event: { value?: number }) => {
    setSpeechVolume(typeof event?.value === "number" ? event.value : 0);
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const webRecorderRef = useRef<any>(null);
  const webStreamRef = useRef<any>(null);
  const webChunksRef = useRef<BlobPart[]>([]);
  const autoStartedRef = useRef(false);
  const startInFlightRef = useRef(false);
  const capturedLocationRef = useRef<{ latitude: number; longitude: number; placeLabel: string | null } | null>(null);
  const slideAnim = useRef(new Animated.Value(300)).current;

  // 现场记录可选记录定位：best-effort，权限未授予/失败都静默跳过，绝不阻塞录音。
  const captureLocation = useCallback(async () => {
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== "granted") return;
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const { latitude, longitude } = position.coords;
      let placeLabel: string | null = null;
      try {
        const places = await Location.reverseGeocodeAsync({ latitude, longitude });
        const place = places[0];
        if (place) {
          placeLabel = [place.city ?? place.region, place.district ?? place.subregion, place.street ?? place.name]
            .filter(Boolean)
            .join("") || null;
        }
      } catch {}
      capturedLocationRef.current = { latitude, longitude, placeLabel };
    } catch {}
  }, []);

  // Slide-in animation
  useEffect(() => {
    Animated.spring(slideAnim, {
      toValue: 0, useNativeDriver: true, speed: 14, bounciness: 4,
    }).start();
  }, [slideAnim]);

  // Format time
  const formatTime = (secs: number) => {
    const m = String(Math.floor(secs / 60)).padStart(2, "0");
    const s = String(secs % 60).padStart(2, "0");
    return `${m}:${s}`;
  };

  // Timer for recording modes that do not report duration through expo-audio.
  useEffect(() => {
    if ((Platform.OS === "web" || androidSpeechRecordingActive) && isRecording && !isPaused) {
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [androidSpeechRecordingActive, isRecording, isPaused]);

  // Sync native recorder state
  useEffect(() => {
    if (Platform.OS === "web") return;
    if (androidSpeechRecordingActive) return;
    setIsRecording(nativeRecorderState.isRecording);
    setRecordingSeconds(Math.max(0, Math.floor(nativeRecorderState.durationMillis / 1000)));
  }, [androidSpeechRecordingActive, nativeRecorderState.durationMillis, nativeRecorderState.isRecording]);

  const stopWebTracks = useCallback(() => {
    const stream = webStreamRef.current;
    if (stream && typeof stream.getTracks === "function") {
      for (const track of stream.getTracks()) track.stop();
    }
    webStreamRef.current = null;
  }, []);

  const resetNativeAudioMode = useCallback(async () => {
    if (Platform.OS === "web") return;
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

  const releaseNativeRecorderSafely = useCallback(async () => {
    if (Platform.OS === "web") return;
    try {
      await nativeRecorder.stop();
    } catch {}
  }, [nativeRecorder]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopWebTracks();
      void cancelLocalSpeechRecognition();
      void releaseNativeRecorderSafely();
      void resetNativeAudioMode();
    };
  }, [cancelLocalSpeechRecognition, releaseNativeRecorderSafely, resetNativeAudioMode, stopWebTracks]);

  // ─── Start recording ──────────────────────

  const startRecording = useCallback(async () => {
    if (isRecording || isUploading || startInFlightRef.current) return;
    startInFlightRef.current = true;
    capturedLocationRef.current = null;
    void captureLocation();
    try {
      if (Platform.OS === "web") {
        const mediaDevices = (globalThis as any).navigator?.mediaDevices;
        const MediaRecorderCtor = (globalThis as any).MediaRecorder;
        if (!mediaDevices?.getUserMedia || !MediaRecorderCtor) {
          throw new Error("当前浏览器不支持录音，请用手机真机测试。");
        }
        const stream = await mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorderCtor(stream);
        webChunksRef.current = [];
        recorder.ondataavailable = (event: any) => {
          if (event.data?.size > 0) webChunksRef.current.push(event.data);
        };
        recorder.start();
        webStreamRef.current = stream;
        webRecorderRef.current = recorder;
        setHasStartedRecording(true);
        setIsRecording(true);
        setIsPaused(false);
        setRecordingSeconds(0);
      } else {
        const permission = await AudioModule.requestRecordingPermissionsAsync();
        if (!permission.granted) throw new Error("请先允许麦克风权限。");

        if (Platform.OS === "android") {
          const sdkInt = typeof Platform.Version === "number" ? Platform.Version : Number(Platform.Version);
          if (Number.isFinite(sdkInt) && sdkInt >= 33) {
            await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
          }
          const speechSnapshot = await startLocalSpeechRecognition({ persistAudio: true });
          if (!speechSnapshot.isAvailable) {
            throw new Error(speechSnapshot.error ?? "本地语音识别启动失败。");
          }
          setHasStartedRecording(true);
          setIsRecording(true);
          setIsPaused(false);
          setRecordingSeconds(0);
          setAndroidSpeechRecordingActive(true);
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
          return;
        }

        await releaseNativeRecorderSafely();
        await setAudioModeAsync({
          playsInSilentMode: true,
          allowsRecording: true,
          shouldRouteThroughEarpiece: false,
          shouldPlayInBackground: true,
          allowsBackgroundRecording: true,
          interruptionMode: "doNotMix",
        });
        await prepareAudioRecorderWithGuard(
          () => nativeRecorder.prepareToRecordAsync({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true }),
          { beforeRetry: releaseNativeRecorderSafely },
        );
        nativeRecorder.record();
        setHasStartedRecording(true);
        setIsPaused(false);
      }
      void startLocalSpeechRecognition();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      setAndroidSpeechRecordingActive(false);
      await releaseNativeRecorderSafely();
      await resetNativeAudioMode();
      const message = getAudioRecorderStartFailureMessage(error);
      setIsRecording(false);
      Alert.alert("录音失败", message);
    } finally {
      startInFlightRef.current = false;
    }
  }, [
    captureLocation,
    isRecording,
    isUploading,
    nativeRecorder,
    releaseNativeRecorderSafely,
    resetNativeAudioMode,
    startLocalSpeechRecognition,
  ]);

  // Only auto-start in explicit task recording flows. Standalone RecordNote opens
  // in a safe idle state so it never requests mic permission by surprise.
  useEffect(() => {
    if (!autoStart) return;
    if (autoStartedRef.current) return;
    autoStartedRef.current = true;
    void startRecording();
  }, [autoStart, startRecording]);

  // ─── Pause / Resume ──────────────────────

  const pauseRecording = useCallback(() => {
    if (androidSpeechRecordingActive) return;
    setIsPaused(true);
    if (Platform.OS === "web" && webRecorderRef.current?.state === "recording") {
      webRecorderRef.current.pause();
    } else if (Platform.OS !== "web") {
      nativeRecorder.pause();
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, [androidSpeechRecordingActive, nativeRecorder]);

  const resumeRecording = useCallback(() => {
    if (androidSpeechRecordingActive) return;
    setIsPaused(false);
    if (Platform.OS === "web" && webRecorderRef.current?.state === "paused") {
      webRecorderRef.current.resume();
    } else if (Platform.OS !== "web") {
      nativeRecorder.record();
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, [androidSpeechRecordingActive, nativeRecorder]);

  // ─── Cancel ──────────────────────────────

  const cancelRecording = useCallback(async () => {
    if (!hasStartedRecording && !isRecording && !nativeRecorderState.isRecording && !webRecorderRef.current) {
      onClose();
      return;
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setHasStartedRecording(false);
    setIsRecording(false);
    setIsPaused(false);
    setRecordingSeconds(0);
    setAndroidSpeechRecordingActive(false);
    try {
      await cancelLocalSpeechRecognition();
      if (Platform.OS === "web" && webRecorderRef.current?.state !== "inactive") {
        webRecorderRef.current.stop();
        webRecorderRef.current = null;
        webChunksRef.current = [];
      }
      await releaseNativeRecorderSafely();
    } catch {}
    await resetNativeAudioMode();
    stopWebTracks();
    onClose();
  }, [cancelLocalSpeechRecognition, hasStartedRecording, isRecording, nativeRecorderState.isRecording, onClose, releaseNativeRecorderSafely, resetNativeAudioMode, stopWebTracks]);

  // ─── Finish and save ──────────────────────

  const finishRecording = useCallback(async () => {
    if (!hasStartedRecording) {
      onClose();
      return;
    }
    const duration = recordingSeconds;
    setHasStartedRecording(false);
    setIsRecording(false);
    setIsPaused(false);
    if (timerRef.current) clearInterval(timerRef.current);

    let uploadFile: RecordedUploadableFile | null = null;
    let speechSnapshot: Awaited<ReturnType<typeof stopLocalSpeechRecognition>> | null = null;
    try {
      if (androidSpeechRecordingActive) {
        speechSnapshot = await stopLocalSpeechRecognition();
        setAndroidSpeechRecordingActive(false);
        const audioUri = speechSnapshot.audioUri;
        if (!audioUri) {
          throw new Error("系统语音识别没有返回录音文件，请确认手机系统语音识别服务可用后再试。");
        }
        uploadFile = uploadableFileFromUri(audioUri, "recording");
      } else if (Platform.OS === "web" && webRecorderRef.current) {
        const recorder = webRecorderRef.current;
        const file = await new Promise<File>((resolve, reject) => {
          recorder.onerror = () => reject(new Error("浏览器录音失败"));
          recorder.onstop = () => {
            const mimeType = recorder.mimeType || "audio/webm";
            const blob = new Blob(webChunksRef.current, { type: mimeType });
            resolve(new File([blob], `recording-${Date.now()}.${fileExtensionFromMimeType(mimeType)}`, { type: mimeType }));
          };
          recorder.stop();
        });
        stopWebTracks();
        webRecorderRef.current = null;
        webChunksRef.current = [];
        uploadFile = file;
      } else {
        // 先在 stop 之前抓住 uri:expo-audio 的 recorder.stop() 之后 nativeRecorder.uri
        // 在部分版本会被清空，而 nativeRecorderState.url 是 120ms 节流的 hook state，
        // 停止瞬间往往还没刷新到最终值——两者同时为空就会误报"录音文件生成失败"、整段白录。
        // 录音进行中 recorder.uri 一定指向正在写入的文件，stop 只是 finalize 它，故 stop 前缓存最稳。
        const preStopUri = nativeRecorder.uri;
        await releaseNativeRecorderSafely();
        const uri = nativeRecorder.uri ?? preStopUri ?? nativeRecorderState.url;
        await resetNativeAudioMode();
        if (uri) {
          const ext = (uri.split("?")[0].split(".").pop() || "m4a").toLowerCase();
          uploadFile = { uri, name: `recording-${Date.now()}.${ext}`, type: `audio/${ext === "caf" ? "x-caf" : ext}` };
        }
      }

      if (!uploadFile) throw new Error("录音文件生成失败");
      speechSnapshot ??= await stopLocalSpeechRecognition();

      if (isTaskMode && taskContext) {
        setIsUploading(true);
        const session = await saveTaskRecording(taskContext, {
          file: uploadFile,
          title: `${taskContext.title} 录音 ${formatTime(duration)}`,
          durationSeconds: duration,
          rawTranscript: speechSnapshot.transcript,
          cleanTranscript: speechSnapshot.transcript,
          segments: speechSnapshot.segments,
          asrError: speechSnapshot.error,
          latitude: capturedLocationRef.current?.latitude ?? null,
          longitude: capturedLocationRef.current?.longitude ?? null,
          placeLabel: capturedLocationRef.current?.placeLabel ?? null,
        });
        if (session.status === "asr_failed" || session.status === "needs_action") {
          // 本地识别失败 → 自动走云端 ASR 兜底(上传音频→豆包转写→回填文字)
          try {
            await cloudTranscribeRecordingSession(session.id);
            await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            Alert.alert("录音已保存", "本地识别没成,已用云端转写补上文字。");
          } catch {
            await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
            Alert.alert("录音已保存", "本地与云端转写都未成功,原音频已保留,可在任务内重试转写。");
          }
        } else if (session.syncStatus === "failed") {
          await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          Alert.alert("录音已保存", session.lastError ?? "文本同步失败，可稍后重试。");
        } else {
          await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          if (session.syncStatus === "pending" || session.syncStatus === "syncing") {
            Alert.alert("录音已保存", "转写文本将继续同步到云端。");
          }
        }
        onUploaded?.(taskContext);
        onClose();
        return;
      }

      // Standalone mode: keep the recording as a local draft until the user picks a target.
      setIsUploading(true);
      await saveUnboundRecording({
        file: uploadFile,
        title: buildAutoRecordingTitle(speechSnapshot.transcript, "速记录音", formatTime(duration)),
        durationSeconds: duration,
        rawTranscript: speechSnapshot.transcript,
        cleanTranscript: speechSnapshot.transcript,
        segments: speechSnapshot.segments,
        asrError: speechSnapshot.error,
        source: "record_note",
        latitude: capturedLocationRef.current?.latitude ?? null,
        longitude: capturedLocationRef.current?.longitude ?? null,
        placeLabel: capturedLocationRef.current?.placeLabel ?? null,
      });
      // 现场记录是孤儿存档：此刻有没有转写都正常（没转写的会在归档进任务时由云端补文字）。
      // 不再把"本地没转出文字"当失败弹窗，统一平静确认 + 告诉去哪找。
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert(
        "已存为录音存档",
        "录音已存进「我的 → 速记录音箱」。到具体任务里把它归档进去，就会转成文字进入该任务。",
      );
      onClose();
    } catch (error) {
      await cancelLocalSpeechRecognition();
      setAndroidSpeechRecordingActive(false);
      const message = error instanceof Error ? error.message : "录音保存失败";
      Alert.alert("保存失败", message);
    } finally {
      setIsUploading(false);
      setAndroidSpeechRecordingActive(false);
      setRecordingSeconds(0);
      await resetNativeAudioMode();
      stopWebTracks();
    }
  }, [androidSpeechRecordingActive, cancelLocalSpeechRecognition, hasStartedRecording, isTaskMode, nativeRecorder, nativeRecorderState.url, onClose, onUploaded, recordingSeconds, releaseNativeRecorderSafely, resetNativeAudioMode, stopLocalSpeechRecognition, stopWebTracks, taskContext]);

  const handleMainControlPress = useCallback(() => {
    if (!hasStartedRecording) {
      void startRecording();
      return;
    }
    if (androidSpeechRecordingActive) {
      return;
    }
    if (isPaused) {
      resumeRecording();
      return;
    }
    pauseRecording();
  }, [androidSpeechRecordingActive, hasStartedRecording, isPaused, pauseRecording, resumeRecording, startRecording]);

  // 实时音量 → 0..1，驱动声波。
  // Android 系统语音识别没有 metering，改用 expo-speech-recognition 的 volumechange 事件(value≈-2~10, <0听不见)；
  // iOS/原生录音用 expo-audio 的 metering(dB)。
  const normalizedMeter = !isRecording || isPaused
    ? 0.08
    : androidSpeechRecordingActive
      ? clampMeter(speechVolume / 7, 0.12, 1)
      : clampMeter(((typeof nativeRecorderState.metering === "number" ? nativeRecorderState.metering : -60) + 60) / 60, 0.08, 1);

  return (
    <View style={s.overlay}>
      {/* Backdrop */}
      <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={cancelRecording} />

      {/* Bottom sheet */}
      <Animated.View style={[s.sheet, { transform: [{ translateY: slideAnim }], paddingBottom: chrome.overlayBottomPadding + 16 }]}>
        <View style={s.handle} />

        {/* Timer */}
        <Text style={s.timer}>{formatTime(recordingSeconds)}</Text>

        {/* 声波：柱高随音量实时跳动 */}
        <Waveform isActive={isRecording && !isPaused} meter={normalizedMeter} barColor={palette.textSecondary} accentColor={palette.cinnabar} />

        {/* Status */}
        <View style={s.statusRow}>
          <View style={[s.statusDot, isPaused ? s.statusDotPaused : isRecording ? s.statusDotRecording : s.statusDotPaused]} />
          <Text style={s.statusText}>
            {isUploading
              ? "本地保存中..."
              : !hasStartedRecording
                ? "点击麦克风开始录音"
                : isPaused
                  ? "已暂停"
                  : isRecording
                    ? androidSpeechRecordingActive
                      ? "正在转写录音，点击右侧完成"
                      : "录音中，可锁屏继续"
                    : "准备录音..."}
          </Text>
        </View>

        {/* Controls */}
        <View style={s.controls}>
          {/* Cancel */}
          <TouchableOpacity style={s.cancelBtn} onPress={cancelRecording} disabled={isUploading}>
            <Trash2 size={22} strokeWidth={1.5} color={palette.textSecondary} />
          </TouchableOpacity>

          {/* Pause / Resume */}
          <TouchableOpacity
            style={[s.mainBtn, !hasStartedRecording || isPaused ? s.mainBtnPaused : s.mainBtnRecording]}
            onPress={handleMainControlPress}
            disabled={isUploading || androidSpeechRecordingActive}
          >
            {!hasStartedRecording ? (
              <Mic size={34} strokeWidth={1.7} color={palette.paperRice} />
            ) : isPaused ? (
              <Play size={32} strokeWidth={1.5} color={palette.paperRice} style={{ marginLeft: 3 }} />
            ) : (
              <Pause size={32} strokeWidth={1.5} color={palette.cinnabar} />
            )}
          </TouchableOpacity>

          {/* Finish */}
          <TouchableOpacity
            style={[s.finishBtn, !hasStartedRecording && s.finishBtnDisabled]}
            onPress={finishRecording}
            disabled={isUploading || !hasStartedRecording}
          >
            <Check size={26} strokeWidth={2} color={palette.paperRice} />
          </TouchableOpacity>
        </View>
      </Animated.View>
    </View>
  );
}

// ─── Styles ─────────────────────────────────

const s = StyleSheet.create({
  overlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 55, justifyContent: "flex-end",
  },
  backdrop: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.2)",
  },
  sheet: {
    backgroundColor: palette.paperRice,
    borderTopLeftRadius: 32, borderTopRightRadius: 32,
    paddingTop: 12, paddingHorizontal: 24,
    shadowColor: palette.inkBlack, shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.12, shadowRadius: 40, elevation: 20,
    alignItems: "center",
  },
  handle: {
    width: 48, height: 6, borderRadius: 3,
    backgroundColor: palette.borderSubtle, marginBottom: 32,
  },

  timer: {
    fontSize: 56, fontFamily: "monospace", fontWeight: "300",
    color: palette.inkBlack, letterSpacing: -1, marginBottom: 8,
  },

  statusRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 40 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusDotRecording: { backgroundColor: palette.cinnabar },
  statusDotPaused: { backgroundColor: palette.reedYellow },
  statusText: { fontSize: 14, fontWeight: "500", color: palette.textSecondary, letterSpacing: 0.3 },

  controls: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 32, width: "100%", paddingHorizontal: 16,
  },
  cancelBtn: {
    width: 50, height: 50, borderRadius: 25,
    backgroundColor: palette.borderSubtle, alignItems: "center", justifyContent: "center",
  },
  mainBtn: {
    width: 72, height: 72, borderRadius: 36,
    alignItems: "center", justifyContent: "center",
  },
  mainBtnRecording: {
    backgroundColor: palette.cinnabarTint, borderWidth: 2, borderColor: palette.borderSubtle,
  },
  mainBtnPaused: {
    backgroundColor: palette.inkBlack,
  },
  finishBtn: {
    width: 50, height: 50, borderRadius: 25,
    backgroundColor: palette.inkBlack, alignItems: "center", justifyContent: "center",
    shadowColor: palette.inkBlack, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 8, elevation: 4,
  },
  finishBtnDisabled: {
    backgroundColor: palette.textTertiary,
    shadowOpacity: 0,
    elevation: 0,
  },
});
