import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  BackHandler,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import ReanimatedSwipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { TouchableOpacity as GHTouchableOpacity } from "react-native-gesture-handler";
import { useRouter } from "expo-router";
import { ChevronLeft, Mic, FolderInput, Trash2 } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { borderRadius, colors, palette, spacing, typography } from "../lib/theme";
import * as localDb from "../lib/local-db";
import { attachRecordingSessionToTask, deleteRecordingArchive } from "../lib/recording-session-service";
import { useTaskBoard } from "../lib/task-board-store";
import type { RecordingSession } from "../lib/recording-session-core";
import type { TaskRecord } from "../lib/types";

function readRecordingTitle(session: RecordingSession): string {
  if (!session.summaryJson) return "未命名录音";
  try {
    const parsed = JSON.parse(session.summaryJson);
    const title = typeof parsed?.title === "string" ? parsed.title.trim() : "";
    return title || "未命名录音";
  } catch {
    return "未命名录音";
  }
}

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mi = String(date.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function recordingStatusLabel(session: RecordingSession): string {
  if (session.status === "asr_failed" || session.status === "needs_action") return "待补文字";
  return "仅本地 · 未归档";
}

export default function RecordingsScreen() {
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const { board } = useTaskBoard();
  const [sessions, setSessions] = useState<RecordingSession[]>([]);
  const [pickerForId, setPickerForId] = useState<string | null>(null);
  const [attachingId, setAttachingId] = useState<string | null>(null);

  const loadSessions = useCallback(() => {
    setSessions(localDb.listUnboundRecordingSessions(50));
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const goBack = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace("/(tabs)/tasks");
  }, [router]);

  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (pickerForId) {
        setPickerForId(null);
        return true;
      }
      goBack();
      return true;
    });
    return () => sub.remove();
  }, [goBack, pickerForId]);

  const handleArchive = useCallback(async (recordingId: string, task: TaskRecord) => {
    if (attachingId) return;
    setAttachingId(recordingId);
    try {
      const session = await attachRecordingSessionToTask(recordingId, task);
      setPickerForId(null);
      loadSessions();
      if (session.status === "needs_action" || session.status === "asr_failed") {
        Alert.alert("已归档到任务", `已放进「${task.title}」，但需要补充转写文本后再同步。`);
      } else {
        Alert.alert("已归档到任务", `已放进「${task.title}」，转写文本将继续同步到云端。`);
      }
    } catch (error) {
      Alert.alert("归档失败", error instanceof Error ? error.message : "请稍后再试。");
    } finally {
      setAttachingId(null);
    }
  }, [attachingId, loadSessions]);

  const handleDelete = useCallback((recordingId: string, title: string) => {
    Alert.alert("删除录音", `确认彻底删除「${title}」吗？孤儿录音删除后不可恢复。`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: () => {
          void deleteRecordingArchive(recordingId).then(loadSessions).catch(() => loadSessions());
        },
      },
    ]);
  }, [loadSessions]);

  const activeTasks = board.tasks.filter((task) => task.progressStatus !== "done");

  return (
    <SafeAreaView style={styles.container} edges={["left", "right", "bottom"]}>
      <View style={[styles.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity style={styles.backButton} onPress={goBack} activeOpacity={0.6}>
          <ChevronLeft size={26} color={palette.inkBlack} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>速记录音箱</Text>
        <View style={styles.backButton} />
      </View>

      <ScrollView
        style={styles.list}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: chrome.tabBarHeight + spacing.xl }}
      >
        <Text style={styles.intro}>
          现场随手录的语音先存在这里（仅本地、未进数据中心）。挑一条放进对应任务，转写就会随任务同步。
        </Text>

        {sessions.length === 0 ? (
          <View style={styles.empty}>
            <Mic size={32} color={palette.textTertiary} strokeWidth={1.5} />
            <Text style={styles.emptyText}>还没有未归档的现场录音</Text>
            <Text style={styles.emptyHint}>用首页「+ → 现场记录」随手录，录完回到这里归档。</Text>
          </View>
        ) : (
          sessions.map((session) => (
            <ReanimatedSwipeable
              key={session.id}
              friction={2}
              rightThreshold={40}
              renderRightActions={() => (
                <GHTouchableOpacity
                  style={styles.deleteAction}
                  onPress={() => handleDelete(session.id, readRecordingTitle(session))}
                >
                  <Trash2 size={22} color={palette.paperRice} strokeWidth={1.8} />
                  <Text style={styles.deleteActionText}>删除</Text>
                </GHTouchableOpacity>
              )}
            >
              <View style={styles.card}>
                <View style={styles.cardMain}>
                  <Text style={styles.cardTitle} numberOfLines={1}>{readRecordingTitle(session)}</Text>
                  <Text style={styles.cardMeta} numberOfLines={1}>
                    {[formatDateTime(session.createdAt), formatDuration(session.durationSeconds), recordingStatusLabel(session)]
                      .filter(Boolean)
                      .join(" · ")}
                  </Text>
                  {session.placeLabel ? (
                    <Text style={styles.cardMeta} numberOfLines={1}>📍 {session.placeLabel}</Text>
                  ) : null}
                </View>
                <TouchableOpacity
                  style={styles.archiveButton}
                  onPress={() => setPickerForId(session.id)}
                  activeOpacity={0.7}
                  disabled={attachingId === session.id}
                >
                  {attachingId === session.id ? (
                    <ActivityIndicator size="small" color={palette.paperRice} />
                  ) : (
                    <>
                      <FolderInput size={16} color={palette.paperRice} strokeWidth={1.8} />
                      <Text style={styles.archiveButtonText}>归档到任务</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </ReanimatedSwipeable>
          ))
        )}
      </ScrollView>

      <Modal
        visible={Boolean(pickerForId)}
        transparent
        animationType="slide"
        onRequestClose={() => setPickerForId(null)}
      >
        <TouchableOpacity style={styles.pickerOverlay} activeOpacity={1} onPress={() => setPickerForId(null)}>
          <TouchableOpacity style={styles.pickerSheet} activeOpacity={1} onPress={(event) => event.stopPropagation()}>
            <View style={styles.pickerHandle} />
            <Text style={styles.pickerTitle}>放进哪个任务？</Text>
            {activeTasks.length === 0 ? (
              <Text style={styles.pickerEmpty}>暂无可选任务，请先创建任务。</Text>
            ) : (
              <ScrollView style={styles.pickerList} keyboardShouldPersistTaps="handled">
                {activeTasks.map((task) => (
                  <TouchableOpacity
                    key={task.id}
                    style={styles.pickerRow}
                    activeOpacity={0.7}
                    onPress={() => {
                      if (pickerForId) void handleArchive(pickerForId, task);
                    }}
                  >
                    <Text style={styles.pickerRowTitle} numberOfLines={1}>{task.title}</Text>
                    {task.clientName ? (
                      <Text style={styles.pickerRowMeta} numberOfLines={1}>{task.clientName}</Text>
                    ) : null}
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
    backgroundColor: palette.paperRice,
  },
  backButton: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  headerTitle: { ...typography.titleCard, color: palette.inkBlack },
  list: { flex: 1 },
  intro: { ...typography.caption, color: palette.textTertiary, marginBottom: spacing.lg, lineHeight: 18 },
  empty: { alignItems: "center", justifyContent: "center", paddingVertical: 64, gap: spacing.sm },
  emptyText: { ...typography.body, color: palette.textSecondary, marginTop: spacing.sm },
  emptyHint: { ...typography.caption, color: palette.textTertiary, textAlign: "center", paddingHorizontal: spacing.xl },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  cardMain: { flex: 1 },
  cardTitle: { ...typography.bodyLarge, color: palette.inkBlack, fontWeight: "500" },
  cardMeta: { ...typography.caption, color: palette.textTertiary, marginTop: 2 },
  archiveButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: palette.inkBlack,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    minWidth: 96,
    justifyContent: "center",
  },
  archiveButtonText: { ...typography.label, color: palette.paperRice, fontWeight: "600" },
  deleteAction: {
    backgroundColor: palette.cinnabar,
    justifyContent: "center",
    alignItems: "center",
    width: 88,
    marginBottom: spacing.sm,
    borderRadius: borderRadius.md,
    gap: 2,
  },
  deleteActionText: { ...typography.label, color: palette.paperRice, fontWeight: "600" },
  pickerOverlay: { flex: 1, backgroundColor: "rgba(31,42,55,0.32)", justifyContent: "flex-end" },
  pickerSheet: {
    backgroundColor: palette.paperRice,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 12,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    maxHeight: "72%",
  },
  pickerHandle: {
    alignSelf: "center",
    width: 40,
    height: 5,
    borderRadius: 3,
    backgroundColor: palette.borderSubtle,
    marginBottom: spacing.md,
  },
  pickerTitle: { ...typography.titleCard, color: palette.inkBlack, marginBottom: spacing.md },
  pickerEmpty: { ...typography.body, color: palette.textTertiary, paddingVertical: spacing.xl, textAlign: "center" },
  pickerList: { flexGrow: 0 },
  pickerRow: {
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: palette.borderSubtle,
  },
  pickerRowTitle: { ...typography.body, color: palette.inkBlack },
  pickerRowMeta: { ...typography.caption, color: palette.textTertiary, marginTop: 2 },
});
