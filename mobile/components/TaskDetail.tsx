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
  RefreshCw,
  Lock,
  ShieldAlert,
  Trash2,
} from "lucide-react-native";
import ReanimatedSwipeable from "react-native-gesture-handler/ReanimatedSwipeable";
import { TouchableOpacity as GHTouchableOpacity } from "react-native-gesture-handler";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, fontSize, spacing, borderRadius, palette, typography, iconStroke } from "../lib/theme";
import {
  fetchTaskActivities,
  fetchTaskById,
  fetchClientNarrative,
  openTaskAttachment,
  pickAndUploadTaskAttachment,
  retryTaskAttachmentTransferOp,
} from "../lib/task-detail-service";
import { getLegacyUploadPseudoOps } from "../lib/legacy-upload-ops";
import * as localDb from "../lib/local-db";
import { buildScheduleFromStartEnd } from "../lib/calendar-repository-core";
import {
  formatTaskDisplayDate,
  getTaskDeadlineDateKey,
  getTaskOverdueDays,
  getTaskScheduleDateTime,
  getTaskScheduleEndDateTime,
} from "../lib/task-time";
import type { RecordingSession } from "../lib/recording-session-core";
import {
  attachRecordingSessionToTask,
  cloudTranscribeRecordingSession,
  deleteRecordingArchive,
  syncRecordingSessionText,
} from "../lib/recording-session-service";
import type {
  ClientNarrativeRecord,
  EventLineRecord,
  TaskActivityRecord,
  TaskRecord,
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

function formatRecordingSyncStatus(session: RecordingSession): string {
  if (session.status === "recording") return "录音中";
  if (session.status === "local_transcribing") return "本地转写中";
  if (session.status === "asr_failed" || session.status === "needs_action") return "需要处理";
  if (session.syncStatus === "syncing") return "文本同步中";
  if (session.syncStatus === "synced") return "已同步";
  if (session.syncStatus === "failed") return "需要处理";
  if (session.syncStatus === "pending") return "已本地保存";
  return "已本地保存";
}

function formatRecordingDisplayTime(value?: string | null): string {
  return formatActivityTime(value ?? undefined) || "刚刚";
}

function getRecordingStatusColor(session: RecordingSession): string {
  if (session.status === "asr_failed" || session.status === "needs_action" || session.syncStatus === "failed") {
    return palette.cinnabar;
  }
  if (session.syncStatus === "syncing") return colors.brand;
  if (session.syncStatus === "synced") return palette.bambooGreen;
  if (session.syncStatus === "pending") return palette.inkBlack;
  return palette.textSecondary;
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
  const overdueDays = getTaskOverdueDays(task);
  const isOverdue = overdueDays > 0 && !isDone;
  const isReviewed = Boolean(task.completionNote);
  const scheduleDateTime = getTaskScheduleDateTime(task);
  const scheduleEndDateTime = getTaskScheduleEndDateTime(task);
  const datePickerValue: DateTimeValue = {
    date: scheduleDateTime?.dateKey || getTaskDeadlineDateKey(task),
    time: scheduleDateTime?.timeLabel ?? null,
    endDate: scheduleEndDateTime?.dateKey ?? null,
    endTime: scheduleEndDateTime?.timeLabel ?? null,
    durationMinutes: task.durationMinutes ?? null,
    reminderMinutesBefore: task.reminderMinutesBefore ?? null,
  };

  const [activities, setActivities] = useState<readonly TaskActivityRecord[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(true);
  // P1-G: 客户上下文区 —— 拉客户 narrative 的 status + blocker 两个维度
  const [clientNarrative, setClientNarrative] = useState<ClientNarrativeRecord | null>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showActionSheet, setShowActionSheet] = useState(false);
  const [showDescriptionEditor, setShowDescriptionEditor] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(task.description ?? "");
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [retryingTransferOpId, setRetryingTransferOpId] = useState<string | null>(null);
  const [pendingTransferVersion, setPendingTransferVersion] = useState(0);
  const [isSavingDescription, setIsSavingDescription] = useState(false);
  const [recordingSessions, setRecordingSessions] = useState<RecordingSession[]>([]);
  const [unboundRecordingSessions, setUnboundRecordingSessions] = useState<RecordingSession[]>([]);
  const [attachingRecordingId, setAttachingRecordingId] = useState<string | null>(null);
  const [retryingRecordingId, setRetryingRecordingId] = useState<string | null>(null);

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

  const loadRecordingSessions = useCallback(() => {
    setRecordingSessions(localDb.listRecordingSessionsForTarget("task", task.id, task.remoteId ?? null));
    setUnboundRecordingSessions(localDb.listUnboundRecordingSessions(10));
  }, [task.id, task.remoteId]);

  useEffect(() => {
    loadRecordingSessions();
  }, [loadRecordingSessions, pendingTransferVersion, task.updatedAt]);

  // 任务录音「需要处理」(本地/云端转写失败)时的可达重试入口。此前 RecordNote 失败兜底
  // 文案承诺"可在任务内重试转写",但任务详情一直没有这个入口——音频是真相源、失败应可恢复
  // (见 recording handoff)。这里补上:无转写文本走云端重转，仅同步失败则重传文本。
  const handleRetryRecordingTranscribe = useCallback(async (session: RecordingSession) => {
    if (retryingRecordingId) {
      return;
    }
    setRetryingRecordingId(session.id);
    try {
      if (session.status === "asr_failed" || session.status === "needs_action") {
        await cloudTranscribeRecordingSession(session.id);
      } else {
        await syncRecordingSessionText(session.id);
      }
      loadRecordingSessions();
      Alert.alert("转写已补上", "录音文字已重新生成并同步。");
    } catch (error) {
      loadRecordingSessions();
      Alert.alert("重试失败", error instanceof Error ? error.message : "请检查网络和登录状态后再试。");
    } finally {
      setRetryingRecordingId(null);
    }
  }, [retryingRecordingId, loadRecordingSessions]);

  const handleAttachUnboundRecording = useCallback(async (recordingId: string) => {
    if (attachingRecordingId) {
      return;
    }
    setAttachingRecordingId(recordingId);
    try {
      const session = await attachRecordingSessionToTask(recordingId, task);
      loadRecordingSessions();
      setPendingTransferVersion((value) => value + 1);
      if (session.status === "needs_action" || session.status === "asr_failed") {
        Alert.alert("录音已挂到任务", session.lastError ?? "录音已挂到任务，但需要补充转写文本后再同步。");
      } else if (session.syncStatus === "failed") {
        Alert.alert("录音已挂到任务", session.lastError ?? "文本同步失败，可稍后重试。");
      } else {
        Alert.alert("录音已挂到任务", "转写文本将继续同步到云端。");
      }
    } catch (error) {
      Alert.alert(
        "挂接失败",
        error instanceof Error ? error.message : "请稍后再试。",
      );
    } finally {
      setAttachingRecordingId(null);
    }
  }, [attachingRecordingId, loadRecordingSessions, task]);

  const handleDeleteUnboundRecording = useCallback((recordingId: string, title: string) => {
    Alert.alert("删除录音", `确认彻底删除「${title}」吗？孤儿录音删除后不可恢复。`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: () => {
          void deleteRecordingArchive(recordingId).then(loadRecordingSessions).catch(() => loadRecordingSessions());
        },
      },
    ]);
  }, [loadRecordingSessions]);

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

  // 进入详情页时拉单条最新数据，避免只读 board payload 里的旧字段
  // （新字段如 orgContext / evidenceCount / nextAction 等需要 fetchTaskById 才能拿全）
  useEffect(() => {
    let cancelled = false;
    fetchTaskById(task.id)
      .then((fresh) => {
        if (!cancelled && fresh) {
          onTaskReplaced?.(fresh);
        }
      })
      .catch(() => {
        // 本地未同步任务或网络失败时静默：详情页继续用 board payload 渲染
      });
    return () => { cancelled = true; };
  }, [task.id, onTaskReplaced]);

  useEffect(() => {
    setDescriptionDraft(task.description ?? "");
  }, [task.description]);

  // P1-G: 拉客户 narrative 用于"客户上下文区"
  useEffect(() => {
    if (!task.clientId) {
      setClientNarrative(null);
      return;
    }
    let cancelled = false;
    fetchClientNarrative(task.clientId)
      .then((record) => { if (!cancelled) setClientNarrative(record); })
      .catch(() => { if (!cancelled) setClientNarrative(null); });
    return () => { cancelled = true; };
  }, [task.clientId]);

  const collaborators = task.collaborators ?? [];
  const attachments = task.attachments ?? [];
  const pendingTransferOps = useMemo(
    () => getLegacyUploadPseudoOps().filter((op) => op.taskLocalId === task.id),
    [attachments.length, isUploadingAttachment, pendingTransferVersion, task.id, task.updatedAt],
  );

  return (
    <View style={s.overlay}>
      {/* Header */}
      <View style={[s.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={s.headerBtn}>
          <ChevronLeft size={26} strokeWidth={2} color={palette.inkBlack} />
        </TouchableOpacity>
        <TouchableOpacity style={s.headerBtn} onPress={() => setShowActionSheet(true)}>
          <MoreHorizontal size={24} color={palette.textTertiary} />
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
            {isDone && <Check size={16} strokeWidth={3} color={palette.paperRice} />}
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
                <Sparkles size={12} color={palette.paperRice} />
                <Text style={s.reviewedBadgeText}>已复盘</Text>
              </View>
            )}
            {isOverdue && (
              <TouchableOpacity style={s.metaItem} onPress={() => setShowDatePicker(true)} activeOpacity={0.6}>
                <CalendarDays size={16} color={palette.cinnabar} />
                <Text style={s.metaTextRed}>已逾期 {overdueDays} 天 ({formatTaskDisplayDate(task)})</Text>
              </TouchableOpacity>
            )}
            {!isOverdue && (
              <TouchableOpacity style={s.metaItem} onPress={() => setShowDatePicker(true)} activeOpacity={0.6}>
                <CalendarDays size={16} color={isDone ? palette.textTertiary : palette.inkBlack} />
                <Text style={[s.metaText, isDone && s.metaTextDone]}>{formatTaskDisplayDate(task)}</Text>
              </TouchableOpacity>
            )}
            {task.priority === "high" && (
              <View style={s.metaItem}>
                <Flag size={16} color={isDone ? palette.textTertiary : palette.reedYellow} />
                <Text style={[s.metaTextOrange, isDone && s.metaTextDone]}>高优</Text>
              </View>
            )}
            {task.businessCategory && (
              <View style={s.metaItem}>
                <Tag size={16} color={isDone ? palette.textTertiary : palette.textSecondary} />
                <Text style={[s.metaTextGray, isDone && s.metaTextDone]}>{task.businessCategory}</Text>
              </View>
            )}
            {(task.evidenceCount ?? 0) > 0 && (
              <View style={s.metaItem}>
                <FileText size={14} color={isDone ? palette.textTertiary : palette.textSecondary} />
                <Text style={[s.metaTextGray, isDone && s.metaTextDone]}>证据 {task.evidenceCount}</Text>
              </View>
            )}
            {task.orgContext?.needsReview && !isDone && (
              <View style={[s.metaItem, s.metaChipAlert]}>
                <AlertTriangle size={14} color={palette.reedYellow} />
                <Text style={s.metaTextAlert}>待复盘</Text>
              </View>
            )}
            {task.orgContext?.approvalState
              && task.orgContext.approvalState !== "approved"
              && task.orgContext.approvalState !== "none"
              && !isDone && (
              <View style={[s.metaItem, s.metaChipInfo]}>
                <ShieldAlert size={14} color={palette.inkBlue} />
                <Text style={s.metaTextInfo}>
                  {(() => {
                    const state = task.orgContext.approvalState;
                    if (state === "pending") return "审批中";
                    if (state === "rejected") return "审批未通过";
                    if (state === "blocked" && task.orgContext.blockedAtStep) return `卡在 ${task.orgContext.blockedAtStep}`;
                    return state;
                  })()}
                </Text>
              </View>
            )}
            {task.scopeMode === "PERSONAL_ONLY" && (
              <View style={s.metaItem}>
                <Lock size={14} color={isDone ? palette.textTertiary : palette.textSecondary} />
                <Text style={[s.metaTextGray, isDone && s.metaTextDone]}>仅自己可见</Text>
              </View>
            )}
          </View>

          {/* Row 2: Collaborators */}
          {collaborators.length > 0 && (
            <View style={s.metaRow}>
              <Users size={14} color={palette.textTertiary} />
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
                  <Link2 size={14} color={palette.textTertiary} />
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
                  <Link2 size={14} color={palette.textTertiary} />
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

        {/* 「任务洞察」卡已按产品要求整卡移除 —— 低上下文任务只剩"暂无可靠洞察/当前缺少/建议补充"占位噪音, 无价值 */}

        {/* P1-G: 客户上下文区 —— narrative 中 status + blocker 两维（"该客户在哪一步 / 卡点在哪"） */}
        {task.clientId && clientNarrative ? (() => {
          const statusDim = clientNarrative.dimensions.find((d) => d.dimension === "status");
          const blockerDim = clientNarrative.dimensions.find((d) => d.dimension === "blocker");
          const statusText = (statusDim?.narrative || "").trim();
          const blockerText = (blockerDim?.narrative || "").trim();
          if (!statusText && !blockerText) return null;
          return (
            <View style={s.clientCtxCard}>
              <Text style={s.clientCtxTitle}>客户当前上下文</Text>
              {statusText ? (
                <View style={s.clientCtxRow}>
                  <Text style={s.clientCtxLabel}>现在到哪一步</Text>
                  <Text style={s.clientCtxBody} numberOfLines={3}>{statusText}</Text>
                </View>
              ) : null}
              {blockerText ? (
                <View style={s.clientCtxRow}>
                  <Text style={s.clientCtxLabel}>卡点在哪</Text>
                  <Text style={s.clientCtxBody} numberOfLines={3}>{blockerText}</Text>
                </View>
              ) : null}
              <Text style={s.clientCtxHint}>
                完整 6 维度 → 工作台
              </Text>
            </View>
          );
        })() : null}

        {/* M3: 「客户工作台 / 事件线详情 / 继续问 AI」三按钮 + 「任务洞察 / 当前阻塞 / 下一步动作 / 近期决策」整卡均已移除(产品要求, 无价值) */}

        {/* Attachments */}
        {attachments.length > 0 && (
          <View style={s.attachmentSection}>
            {attachments.map((att) => {
              const localStatus = processingAttachments.get(att.id);
              const status: AttachmentProcessingStatus = localStatus ?? "completed";
              const isProcessing = status !== "completed";

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
                      status === "uploading" ? <ArrowUpCircle size={24} color={palette.inkBlue} /> :
                      status === "transcribing" ? <FileText size={24} color={palette.inkBlue} /> :
                      <Sparkles size={24} color={palette.inkBronze} />
                    ) : (
                      <PlayCircle size={24} color={palette.inkBlack} />
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

        {recordingSessions.length > 0 && (
          <View style={s.attachmentSection}>
            <Text style={s.sectionLabel}>本地录音</Text>
            {recordingSessions.map((session) => {
              const needsAttention =
                session.status === "asr_failed" ||
                session.status === "needs_action" ||
                session.syncStatus === "failed";
              const isSyncingRecording = session.syncStatus === "syncing";

              return (
                <View
                  key={session.id}
                  style={[
                    s.attachmentCard,
                    needsAttention ? s.pendingAttachmentCardDanger : s.attachmentCardProcessing,
                  ]}
                >
                  <View style={s.attachmentRow}>
                    {isSyncingRecording ? (
                      <ActivityIndicator size="small" color={colors.brand} style={{ width: 24 }} />
                    ) : needsAttention ? (
                      <AlertTriangle size={24} color={palette.reedYellow} />
                    ) : (
                      <Mic size={24} color={palette.inkBlack} />
                    )}
                    <View style={s.attachmentBody}>
                      <View style={s.attachmentHeader}>
                        <Text style={s.attachmentTitle} numberOfLines={1}>任务录音</Text>
                        {session.durationSeconds != null ? (
                          <Text style={s.attachmentDuration}>{formatDuration(session.durationSeconds)}</Text>
                        ) : null}
                      </View>
                      <Text style={[s.attachmentStatusText, { color: getRecordingStatusColor(session) }]}>
                        {formatRecordingSyncStatus(session)} · 音频仅本机 · {formatRecordingDisplayTime(session.createdAt)}
                      </Text>
                      {session.lastError ? (
                        <Text style={s.attachmentSummary} numberOfLines={3}>{session.lastError}</Text>
                      ) : null}
                      {needsAttention && session.audioPath ? (
                        <TouchableOpacity
                          style={[
                            s.inlineRetryButton,
                            retryingRecordingId === session.id && s.inlineRetryButtonBusy,
                          ]}
                          disabled={Boolean(retryingRecordingId)}
                          onPress={() => {
                            void handleRetryRecordingTranscribe(session);
                          }}
                        >
                          {retryingRecordingId === session.id ? (
                            <ActivityIndicator size="small" color={colors.brand} />
                          ) : (
                            <Text style={[s.inlineRetryButtonText, s.inlineRetryButtonTextDanger]}>
                              重试转写
                            </Text>
                          )}
                        </TouchableOpacity>
                      ) : null}
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        )}

        {unboundRecordingSessions.length > 0 && (
          <View style={s.attachmentSection}>
            <Text style={s.sectionLabel}>待挂接录音</Text>
            {unboundRecordingSessions.map((session) => {
              const needsAttention =
                session.status === "asr_failed" ||
                session.status === "needs_action" ||
                session.syncStatus === "failed";
              const isAttaching = attachingRecordingId === session.id;

              return (
                <ReanimatedSwipeable
                  key={session.id}
                  friction={2}
                  rightThreshold={40}
                  renderRightActions={() => (
                    <GHTouchableOpacity
                      style={s.recordingDeleteAction}
                      onPress={() => handleDeleteUnboundRecording(session.id, readRecordingTitle(session))}
                    >
                      <Trash2 size={20} color={palette.paperRice} strokeWidth={1.8} />
                      <Text style={s.recordingDeleteActionText}>删除</Text>
                    </GHTouchableOpacity>
                  )}
                >
                  <View
                    style={[
                      s.attachmentCard,
                      needsAttention ? s.pendingAttachmentCardDanger : s.attachmentCardProcessing,
                    ]}
                  >
                    <View style={s.attachmentRow}>
                      {needsAttention ? (
                        <AlertTriangle size={24} color={palette.reedYellow} />
                      ) : (
                        <Mic size={24} color={palette.inkBlack} />
                      )}
                      <View style={s.attachmentBody}>
                        <View style={s.attachmentHeader}>
                          <Text style={s.attachmentTitle} numberOfLines={1}>{readRecordingTitle(session)}</Text>
                          {session.durationSeconds != null ? (
                            <Text style={s.attachmentDuration}>{formatDuration(session.durationSeconds)}</Text>
                          ) : null}
                        </View>
                        <Text style={[s.attachmentStatusText, { color: getRecordingStatusColor(session) }]}>
                          {formatRecordingSyncStatus(session)} · 未挂载 · {formatRecordingDisplayTime(session.createdAt)}
                        </Text>
                        {session.lastError ? (
                          <Text style={s.attachmentSummary} numberOfLines={3}>{session.lastError}</Text>
                        ) : null}
                        <TouchableOpacity
                          style={[s.inlineRetryButton, isAttaching && s.inlineRetryButtonBusy]}
                          disabled={Boolean(attachingRecordingId)}
                          onPress={() => {
                            void handleAttachUnboundRecording(session.id);
                          }}
                        >
                          {isAttaching ? (
                            <ActivityIndicator size="small" color={colors.brand} />
                          ) : (
                            <Link2 size={14} color={needsAttention ? colors.error : colors.brand} />
                          )}
                          <Text
                            style={[
                              s.inlineRetryButtonText,
                              needsAttention && s.inlineRetryButtonTextDanger,
                            ]}
                          >
                            {isAttaching ? "挂接中..." : "挂到此任务"}
                          </Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  </View>
                </ReanimatedSwipeable>
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
                    <AlertTriangle size={24} color={palette.reedYellow} />
                  ) : op.status === "processing" ? (
                    <ActivityIndicator size="small" color={colors.brand} style={{ width: 24 }} />
                  ) : (
                    <ArrowUpCircle size={24} color={palette.inkBlue} />
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
            <CheckCircle2 size={16} color={palette.bambooGreen} />
            <Text selectable style={s.completionText}>{task.completionNote}</Text>
          </View>
        )}

        {/* Activity timeline */}
        <View style={s.activitySection}>
          <Text style={s.sectionLabel}>活动记录</Text>
          {activitiesLoading ? (
            <ActivityIndicator size="small" color={colors.brand} style={{ marginTop: 8 }} />
          ) : activities.length > 0 ? (
            activities.slice(0, 5).map((a, idx) => (
              <View key={a.id} style={s.activityRow}>
                <View style={s.timelineDot} />
                {idx < Math.min(activities.length, 5) - 1 && <View style={s.timelineLine} />}
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
          <Mic size={22} strokeWidth={2} color={palette.inkBlack} />
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
            <Paperclip size={18} strokeWidth={2} color={palette.inkBlack} />
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
            <CheckCircle2 size={18} strokeWidth={2} color={palette.paperRice} />
          ) : (
            <ClipboardList size={18} strokeWidth={2} color={palette.paperRice} />
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
            date: datePickerValue.date,
            time: datePickerValue.time,
            durationMinutes: datePickerValue.durationMinutes,
            reminderMinutesBefore: datePickerValue.reminderMinutesBefore,
          }}
          onChange={(v) => {
            if (!onUpdate) return;
            onUpdate(task.id, {
              ...buildScheduleFromStartEnd({
                startDate: v.date,
                startTime: v.time,
                endDate: v.endDate ?? null,
                endTime: v.endTime ?? null,
              }),
              reminderMinutesBefore: v.reminderMinutesBefore ?? null,
            });
          }}
          onClose={() => setShowDatePicker(false)}
          onClear={() => {
            if (onUpdate) onUpdate(task.id, buildScheduleFromStartEnd({ startDate: null, startTime: null, endDate: null, endTime: null }));
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
              placeholderTextColor={palette.textTertiary}
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
                  <ActivityIndicator size="small" color={palette.paperRice} />
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
    backgroundColor: palette.paperRice, zIndex: 50,
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
    backgroundColor: palette.paperRice,
    borderRadius: 20,
    padding: 18,
    gap: 4,
  },
  actionSheetTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: palette.inkBlack,
    marginBottom: 8,
  },
  actionSheetRow: {
    paddingVertical: 14,
  },
  actionSheetText: {
    fontSize: 15,
    color: palette.inkBlack,
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
    borderTopColor: palette.borderSubtle,
  },
  actionSheetCancelText: {
    fontSize: 14,
    color: palette.textSecondary,
    fontWeight: "600",
  },
  editorSheet: {
    backgroundColor: palette.paperRice,
    borderRadius: 20,
    padding: 18,
    minHeight: 280,
  },
  editorTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: palette.inkBlack,
    marginBottom: 12,
  },
  editorInput: {
    minHeight: 160,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    lineHeight: 22,
    color: palette.inkBlack,
    backgroundColor: palette.paperMoon,
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
    backgroundColor: palette.borderSubtle,
  },
  editorSecondaryButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: palette.textSecondary,
  },
  editorPrimaryButton: {
    minWidth: 84,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 14,
    backgroundColor: palette.inkBlack,
    alignItems: "center",
    justifyContent: "center",
  },
  editorPrimaryButtonBusy: {
    opacity: 0.8,
  },
  editorPrimaryButtonText: {
    fontSize: 14,
    fontWeight: "700",
    color: palette.paperRice,
  },

  body: { flex: 1 },
  bodyContent: { paddingHorizontal: 24, paddingTop: 8 },

  // Title
  titleRow: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
  checkbox: {
    width: 24, height: 24, borderRadius: 6, borderWidth: 2,
    borderColor: palette.borderSubtle, alignItems: "center", justifyContent: "center", marginTop: 4,
  },
  checkboxDone: { backgroundColor: palette.inkBlack, borderColor: palette.inkBlack },
  checkboxOverdue: { borderColor: palette.cinnabar, backgroundColor: palette.cinnabarTint },
  title: { flex: 1, fontSize: 22, fontWeight: "600", color: palette.inkBlack, lineHeight: 32 },
  titleDone: { color: palette.textTertiary, textDecorationLine: "line-through" },

  // Meta
  metaArea: { paddingLeft: 38, marginTop: 14, gap: 10 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12 },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  metaText: { fontSize: 14, fontWeight: "500", color: palette.inkBlack },
  metaTextRed: { fontSize: 14, fontWeight: "500", color: palette.cinnabar },
  metaTextOrange: { fontSize: 14, fontWeight: "500", color: palette.reedYellow },
  metaTextGray: { fontSize: 14, fontWeight: "500", color: palette.textSecondary },
  metaTextDone: { color: palette.textTertiary },
  metaChipAlert: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999,
    backgroundColor: "rgba(214,148,0,0.12)",
  },
  metaTextAlert: { fontSize: 12, fontWeight: "700", color: palette.reedYellow },
  metaChipInfo: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999,
    backgroundColor: "rgba(74,108,184,0.10)",
  },
  metaTextInfo: { fontSize: 12, fontWeight: "700", color: palette.inkBlue },

  reviewedBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: palette.reedYellow, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12,
  },
  reviewedBadgeText: { fontSize: 11, fontWeight: "700", color: palette.paperRice },

  // Collaborators
  collaboratorChip: { flexDirection: "row", alignItems: "center", gap: 5 },
  avatar: {
    width: 20, height: 20, borderRadius: 10,
    alignItems: "center", justifyContent: "center",
  },
  avatarOwner: { backgroundColor: palette.inkBlue },
  avatarCollab: { backgroundColor: palette.bambooGreen },
  avatarText: { fontSize: 10, fontWeight: "600", color: palette.paperRice },
  collaboratorName: { fontSize: 13, fontWeight: "500", color: palette.textSecondary },
  ownerLabel: { fontSize: 10, fontWeight: "600", color: palette.inkBlue },

  // Related
  relatedItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  relatedText: {
    fontSize: 13, color: palette.textSecondary,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.borderSubtle,
    paddingBottom: 1,
  },

  divider: { height: 1, backgroundColor: palette.borderSubtle, marginVertical: 20, marginLeft: 38 },

  // Description
  descriptionArea: { paddingLeft: 38, marginBottom: 20 },
  descriptionText: { fontSize: 15, lineHeight: 26, color: palette.textSecondary },
  descriptionTextDone: { color: palette.textTertiary },
  descriptionPlaceholder: { fontSize: 15, color: palette.textTertiary }, // 去 italic：中文无 italic 字形会强制斜体光栅化发糊
  // P1-G: 客户上下文卡
  clientCtxCard: {
    marginLeft: 38,
    marginTop: 12,
    marginBottom: 4,
    borderRadius: 14,
    backgroundColor: palette.airyBlueBg,
    borderWidth: 1,
    borderColor: palette.airyBlueBorder,
    padding: spacing.md,
    gap: 8,
  },
  clientCtxTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: palette.airyBlue,
    letterSpacing: 0.2,
  },
  clientCtxRow: {
    gap: 2,
  },
  clientCtxLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: palette.textSecondary,
  },
  clientCtxBody: {
    fontSize: 13,
    lineHeight: 19,
    color: palette.inkBlack,
  },
  clientCtxHint: {
    fontSize: 11,
    color: palette.textTertiary,
    fontStyle: "italic",
  },
  // (contextAction 三按钮 + Blocker / Next action / Recent decision 卡片样式已随整块移除)

  // Attachments
  attachmentSection: { paddingLeft: 38, marginBottom: 20, gap: 10 },
  attachmentCard: {
    borderWidth: 1, borderColor: palette.borderSubtle, borderRadius: 16,
    padding: 14, backgroundColor: palette.paperMoon, overflow: "hidden",
  },
  attachmentCardProcessing: { backgroundColor: palette.paperMoon, borderColor: palette.borderSubtle },
  pendingAttachmentCardDanger: { backgroundColor: palette.paperMoon, borderColor: palette.borderSubtle },
  recordingDeleteAction: {
    backgroundColor: palette.cinnabar,
    justifyContent: "center",
    alignItems: "center",
    width: 84,
    borderRadius: 16,
    marginLeft: 8,
    gap: 2,
  },
  recordingDeleteActionText: { ...typography.label, color: palette.paperRice, fontWeight: "600" },
  attachmentShimmer: {
    position: "absolute", top: 0, left: 0, right: 0, height: 2,
    backgroundColor: palette.inkBlue,
  },
  attachmentRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  attachmentBody: { flex: 1 },
  attachmentHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  attachmentTitle: { fontSize: 14, fontWeight: "600", color: palette.inkBlack, flex: 1 },
  attachmentDuration: { fontSize: 12, color: palette.textTertiary, fontFamily: "monospace" },
  attachmentStatusText: { fontSize: 13, fontWeight: "500", color: palette.inkBlue },
  attachmentSummary: { fontSize: 13, color: palette.textSecondary, lineHeight: 22 },
  inlineRetryButton: {
    marginTop: 10,
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 12,
    backgroundColor: palette.paperRice,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
  },
  inlineRetryButtonBusy: {
    opacity: 0.72,
  },
  inlineRetryButtonText: {
    fontSize: 12,
    fontWeight: "600",
    color: palette.inkBlack,
  },
  inlineRetryButtonTextDanger: {
    color: colors.error,
  },

  // Completion note
  completionCard: {
    flexDirection: "row", alignItems: "flex-start", gap: 10,
    marginLeft: 38, marginBottom: 20,
    backgroundColor: "rgba(92,122,92,0.08)", borderRadius: 12, padding: 14,
  },
  completionText: { flex: 1, fontSize: 13, color: palette.bambooGreen, lineHeight: 20 },

  // Activity timeline
  activitySection: { paddingLeft: 38, marginBottom: 20 },
  sectionLabel: { fontSize: 11, fontWeight: "800", color: palette.textTertiary, marginBottom: 12 },
  activityRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: 16, position: "relative" },
  timelineDot: {
    width: 8, height: 8, borderRadius: 4, backgroundColor: palette.inkBlack,
    marginTop: 4, marginRight: 12, zIndex: 1,
  },
  timelineLine: {
    position: "absolute", left: 3.5, top: 14, bottom: -12,
    width: 1, backgroundColor: palette.borderSubtle,
  },
  activityContent: { flex: 1, flexDirection: "row", flexWrap: "wrap", gap: 8 },
  activityTime: { fontSize: 11, color: palette.textTertiary, fontFamily: "monospace" },
  activityLabel: { fontSize: 12, color: palette.textSecondary, flex: 1 },
  activityActor: { fontSize: 12, color: palette.textTertiary },
  emptyText: { fontSize: 12, color: palette.textTertiary },

  // Bottom info
  bottomInfo: { paddingLeft: 38, marginBottom: 20 },
  bottomInfoText: { fontSize: 11, color: palette.textTertiary },

  // Bottom bar
  bottomBar: {
    flexDirection: "row", gap: 12,
    paddingHorizontal: 24, paddingTop: 16,
    backgroundColor: "rgba(255,255,255,0.9)",
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.borderSubtle,
  },
  micButton: {
    width: 52, height: 52, borderRadius: 16,
    backgroundColor: palette.paperMoon, borderWidth: 1, borderColor: palette.borderSubtle,
    alignItems: "center", justifyContent: "center",
  },
  secondaryActionButton: {
    height: 52,
    borderRadius: 16,
    backgroundColor: palette.paperMoon,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
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
    color: palette.inkBlack,
  },
  reviewButton: {
    flex: 1, height: 52, borderRadius: 16,
    backgroundColor: palette.inkBlack,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
  },
  reviewButtonDone: { backgroundColor: palette.bambooGreen },
  reviewButtonText: { fontSize: 15, fontWeight: "600", color: palette.paperRice, letterSpacing: 0.3 },
});
