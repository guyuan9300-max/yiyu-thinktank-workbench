import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  GestureResponderEvent,
  NativeSyntheticEvent,
  NativeTouchEvent,
  PanResponder,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useLocalSearchParams, useRouter, type ErrorBoundaryProps } from "expo-router";
import { RouteErrorFallback } from "../../components/ErrorBoundary";
import { takePendingConsultDraft } from "../../lib/consult-to-task";
import * as Haptics from "expo-haptics";
import { runOnJS, useSharedValue, withTiming } from "react-native-reanimated";
import { useAndroidExitApp } from "../../lib/android-back";
import { useAppChromeInsets } from "../../lib/app-chrome";
import * as localDb from "../../lib/local-db";
import type { SmartTaskDraft, TaskBoardResponse, TaskRecord } from "../../lib/types";
import { borderRadius, colors, shadow, palette, typography, iconStroke } from "../../lib/theme";
import { ChevronRight, ChevronDown, Inbox, Check } from "lucide-react-native";
import {
  flushQueuedSmartInputDrafts,
  getQueuedSmartInputCount,
  clearSmartInputQueue,
} from "../../lib/smart-input-queue";
import { formatLocalDateKey, getLocalWeekRangeKeys } from "../../lib/date";
import {
  formatTaskDisplayDate,
  getTaskCalendarDateKey,
} from "../../lib/task-time";
import {
  buildRecoveredDraftKey,
  shouldAttemptSmartInputRecovery,
  shouldAutoOpenRecoveredDraft,
  shouldUseRecoveredDraft,
  type RecoveryTrigger,
} from "../../lib/smart-input-recovery";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import { devLog } from "../../lib/dev-log";
import {
  deleteTaskOfflineFirst,
  updateTaskOfflineFirst,
} from "../../lib/sync-engine";
import {
  moveTaskToCalendarTarget,
  updateCalendarTaskSchedule,
} from "../../lib/calendar-repository";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import TasksHeader from "../../components/tasks-screen/TasksHeader";
import TasksFilterBar from "../../components/tasks-screen/TasksFilterBar";
import InboxTaskList from "../../components/tasks-screen/InboxTaskList";
import ScheduledTaskList from "../../components/tasks-screen/ScheduledTaskList";
import SmartInputRecoveryController from "../../components/tasks-screen/SmartInputRecoveryController";
import TaskModalCoordinator from "../../components/tasks-screen/TaskModalCoordinator";
import DragCalendarOverlay from "../../components/tasks-screen/DragCalendarOverlay";
import SwipeableTaskRow from "../../components/SwipeableTaskRow";

// ─── Constants ─────────────────────────────────

type FilterKey = "today" | "collab_inbox" | "unreviewed" | "all";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "today", label: "今日任务" },
  { key: "collab_inbox", label: "协作收件箱" },
  { key: "unreviewed", label: "未复盘" },
  { key: "all", label: "全部任务" },
];

const SWIPE_ACTION_WIDTH = 92;
// 滴答清单式:卡片锁在手指上,命中的目标日期在手指上方一截 → 手不挡目标,看得清要落到哪天。
const DRAG_TARGET_OFFSET_Y = 120;
const SWIPE_OPEN_THRESHOLD = 28;
const DRAG_CANCEL_DISTANCE = 8;
// 长按拖入日历的触发阈值：260ms 太短，"想点开/想滚动"易被误判为拖拽。
const DRAG_LONG_PRESS_MS = 450;

type SwipeActionDirection = "edit" | "delete" | null;

// ─── Helpers ───────────────────────────────────

function formatDate(): string {
  const d = new Date();
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${d.getMonth() + 1}月${d.getDate()}日 · ${weekdays[d.getDay()]}`;
}

function formatDateKey(date: Date): string {
  return formatLocalDateKey(date);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function resolveSwipeOffset(direction: SwipeActionDirection): number {
  if (direction === "edit") return SWIPE_ACTION_WIDTH;
  if (direction === "delete") return -SWIPE_ACTION_WIDTH;
  return 0;
}

function isCollabInboxTask(task: TaskRecord): boolean {
  return task.viewerInboxStatus === "pending";
}

function buildTaskMeta(task: TaskRecord): string {
  if (isCollabInboxTask(task)) {
    const assigner =
      task.ownerName ||
      task.collaborators?.find((item) => item.isOwner)?.fullName ||
      null;
    const base = assigner ? `协作待确认 · ${assigner}` : "协作待确认";
    if (task.clientName) return `${base} · 客户：${task.clientName}`;
    if (task.eventLineName) return `${base} · ${task.eventLineName}`;
    if (task.listName) return `${base} · ${task.listName}`;
    return base;
  }
  return (
    task.description ||
    (task.clientName ? `客户：${task.clientName}` : task.eventLineName ? task.eventLineName : task.listName)
  );
}

function hasScheduledDate(task: TaskRecord): boolean {
  return Boolean(getTaskCalendarDateKey(task));
}

// P1-F: 任务卡视觉信号 ——
// 1) 左侧 3px 优先级竖条颜色
// 2) 标题旁日期紧迫度 chip
function getTaskPriorityColor(task: TaskRecord): string {
  switch (task.priority) {
    case "high":
      return palette.rose; // 紧急 = 朱砂
    case "low":
      return palette.borderSubtle; // 低优先 = 浅灰，几乎隐形
    default:
      return palette.airyBlue; // 普通 = airy blue 主色
  }
}

interface DateChip {
  label: string;
  bg: string;
  color: string;
}

function getTaskDateChip(task: TaskRecord, todayKey: string): DateChip | null {
  const dateKey = getTaskCalendarDateKey(task);
  if (!dateKey) return null;
  const today = new Date(`${todayKey}T00:00:00`);
  const target = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const dayDiff = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  const isDone = task.progressStatus === "done";
  if (dayDiff < 0 && !isDone) {
    return { label: `逾期 ${-dayDiff} 天`, bg: palette.roseBg, color: palette.roseText };
  }
  if (dayDiff === 0) {
    return { label: "今天", bg: palette.roseBg, color: palette.roseText };
  }
  if (dayDiff === 1) {
    return { label: "明天", bg: palette.amberBg, color: palette.amberText };
  }
  if (dayDiff > 1 && dayDiff <= 7) {
    return { label: `${dayDiff} 天内`, bg: palette.airyBlueBg, color: palette.airyBlue };
  }
  return null; // 大于一周不显示，避免视觉噪音
}

// ─── TodayDashboardCard ────────────────────────
// P1-B: filter=today 时顶部"今日重点"汇总卡：大字汇总 + 高优先级置顶 + 一句话 CTA

interface TodayDashboardCardProps {
  tasks: readonly TaskRecord[];
  scheduledTodayTasks: readonly TaskRecord[];
  pendingTasks: readonly TaskRecord[];
  todayKey: string;
  onStartFirst: (task: TaskRecord) => void;
}

function TodayDashboardCard({
  scheduledTodayTasks,
  pendingTasks,
  todayKey,
  onStartFirst,
}: TodayDashboardCardProps) {
  // 综合"今日（有日程的）+ 待安排"看作今日候选
  const todayPool = useMemo(
    () => [...scheduledTodayTasks, ...pendingTasks].filter((t) => !isCollabInboxTask(t)),
    [scheduledTodayTasks, pendingTasks],
  );
  const total = todayPool.length;
  const doneCount = todayPool.filter((t) => t.progressStatus === "done").length;
  const highCount = todayPool.filter((t) => t.priority === "high" && t.progressStatus !== "done").length;
  const overdueCount = useMemo(() => {
    const today = new Date(`${todayKey}T00:00:00`);
    return scheduledTodayTasks.filter((t) => {
      if (t.progressStatus === "done") return false;
      const key = getTaskCalendarDateKey(t);
      if (!key) return false;
      const target = new Date(`${key}T00:00:00`);
      return target.getTime() < today.getTime();
    }).length;
  }, [scheduledTodayTasks, todayKey]);

  // 优先推"高优先级 + 未完成"的第一件
  const nextActionable = useMemo(() => {
    const highPending = todayPool.find((t) => t.priority === "high" && t.progressStatus !== "done");
    if (highPending) return highPending;
    return todayPool.find((t) => t.progressStatus !== "done") ?? null;
  }, [todayPool]);

  if (total === 0) {
    return (
      <View style={s.todayHeroEmpty}>
        <Text style={s.todayHeroEmptyTitle}>今天还没安排</Text>
        <Text style={s.todayHeroEmptyHint}>下方"待安排任务"长按可拖入日历，或点底部 + 新建。</Text>
      </View>
    );
  }

  const allDone = total > 0 && doneCount === total;
  const ctaLabel = allDone
    ? "今日已完成 ✓"
    : nextActionable
      ? `开始：${(nextActionable.title || "").slice(0, 18)}${(nextActionable.title || "").length > 18 ? "…" : ""}`
      : "查看任务";

  return (
    <View style={s.todayHero}>
      <View style={s.todayHeroHeader}>
        <View>
          <Text style={s.todayHeroLabel}>今日重点</Text>
          <View style={s.todayHeroNumRow}>
            <Text style={s.todayHeroNum}>{total}</Text>
            <Text style={s.todayHeroNumUnit}>件</Text>
            {doneCount > 0 ? (
              <Text style={s.todayHeroProgress}>· 已完成 {doneCount}</Text>
            ) : null}
          </View>
        </View>
        <View style={s.todayHeroChips}>
          {highCount > 0 ? (
            <View style={[s.todayHeroChip, { backgroundColor: palette.roseBg }]}>
              <Text style={[s.todayHeroChipText, { color: palette.roseText }]}>⚑ {highCount} 件高优先级</Text>
            </View>
          ) : null}
          {overdueCount > 0 ? (
            <View style={[s.todayHeroChip, { backgroundColor: palette.roseBg }]}>
              <Text style={[s.todayHeroChipText, { color: palette.roseText }]}>逾期 {overdueCount}</Text>
            </View>
          ) : null}
        </View>
      </View>

      {nextActionable && !allDone ? (
        <TouchableOpacity
          style={s.todayHeroCta}
          activeOpacity={0.78}
          onPress={() => onStartFirst(nextActionable)}
        >
          <Text style={s.todayHeroCtaText} numberOfLines={1}>{ctaLabel}</Text>
          <ChevronRight size={16} strokeWidth={2} color="#FFFFFF" />
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

// ─── ScheduledCardWithDrag ─────────────────────
// Lightweight wrapper that adds long-press → drag-to-calendar on scheduled cards.

interface ScheduledCardWithDragProps {
  task: TaskRecord;
  isDone: boolean;
  isFocusMatched?: boolean;
  onPress: () => void;
  onToggleComplete?: () => void;
  onOpenEventLine?: () => void;
  onDragStart?: (task: TaskRecord, pageX: number, pageY: number) => void;
  onDragMove?: (pageX: number, pageY: number) => void;
  onDragEnd?: () => void;
}

function ScheduledCardWithDrag({
  task,
  isDone,
  isFocusMatched = false,
  onPress,
  onToggleComplete,
  onOpenEventLine,
  onDragStart,
  onDragMove,
  onDragEnd,
}: ScheduledCardWithDragProps) {
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dragActivatedRef = useRef(false);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const lastTouchRef = useRef({ x: 0, y: 0 });

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const handleTouchStart = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    touchStartRef.current = { x: touch.pageX, y: touch.pageY };
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    dragActivatedRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = setTimeout(() => {
      dragActivatedRef.current = true;
      onDragStart?.(task, lastTouchRef.current.x, lastTouchRef.current.y);
    }, DRAG_LONG_PRESS_MS);
  }, [clearLongPressTimer, onDragStart, task]);

  const handleTouchMove = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    if (dragActivatedRef.current) {
      onDragMove?.(touch.pageX, touch.pageY);
      return;
    }
    const dx = touch.pageX - touchStartRef.current.x;
    const dy = touch.pageY - touchStartRef.current.y;
    if (Math.abs(dx) > DRAG_CANCEL_DISTANCE || Math.abs(dy) > DRAG_CANCEL_DISTANCE) {
      clearLongPressTimer();
    }
  }, [clearLongPressTimer, onDragMove]);

  const handleTouchEnd = useCallback(() => {
    clearLongPressTimer();
    if (dragActivatedRef.current) {
      dragActivatedRef.current = false;
      onDragEnd?.();
    }
  }, [clearLongPressTimer, onDragEnd]);

  const handleTouchCancel = useCallback(() => {
    clearLongPressTimer();
  }, [clearLongPressTimer]);

  const meta = Array.from(new Set([task.clientName, task.eventLineName].filter(Boolean))).join(" · ");
  const trailing = getTaskCalendarDateKey(task) ? formatTaskDisplayDate(task) : null;
  const dateChip = getTaskDateChip(task, formatDateKey(new Date()));
  const isHigh = task.priority === "high";
  return (
    <View
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
    >
      <TouchableOpacity
        style={[s.taskRow, isFocusMatched && s.taskRowFocus]}
        activeOpacity={0.6}
        onPress={() => { if (!dragActivatedRef.current) onPress(); }}
      >
        <TouchableOpacity
          style={[s.taskCheck, isDone && s.taskCheckDone]}
          activeOpacity={isDone ? 1 : 0.8}
          disabled={isDone || !onToggleComplete}
          onPress={(event) => {
            event.stopPropagation?.();
            onToggleComplete?.();
          }}
        >
          {isDone ? <Check size={13} strokeWidth={3} color="#FFFFFF" /> : null}
        </TouchableOpacity>
        <View style={s.taskRowBody}>
          <View style={s.taskRowTitleLine}>
            {isHigh ? <View style={s.priorityDot} /> : null}
            <Text style={[s.taskRowTitle, isDone && s.taskRowTitleDone]} numberOfLines={1}>
              {task.title}
            </Text>
          </View>
          {meta ? <Text style={s.taskRowMeta} numberOfLines={1}>{meta}</Text> : null}
          <TaskSyncBadge task={task} compact style={s.taskRowSync} />
        </View>
        {trailing ? (
          <Text style={[s.taskRowTime, dateChip ? { color: dateChip.color } : null]}>{trailing}</Text>
        ) : null}
      </TouchableOpacity>
    </View>
  );
}

// ─── SwipeInboxCard ────────────────────────────

interface SwipeInboxCardProps {
  task: TaskRecord;
  isDone: boolean;
  isFocusMatched?: boolean;
  openDirection: SwipeActionDirection;
  onOpenDirectionChange: (direction: SwipeActionDirection) => void;
  onPress: () => void;
  onToggleComplete?: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onOpenEventLine?: () => void;
  onDragStart?: (task: TaskRecord, pageX: number, pageY: number) => void;
  onDragMove?: (pageX: number, pageY: number) => void;
  onDragEnd?: () => void;
}

function SwipeInboxCard({
  task,
  isDone,
  isFocusMatched = false,
  openDirection,
  onOpenDirectionChange,
  onPress,
  onToggleComplete,
  onEdit,
  onDelete,
  onOpenEventLine,
  onDragStart,
  onDragMove,
  onDragEnd,
}: SwipeInboxCardProps) {
  const translateX = useRef(new Animated.Value(resolveSwipeOffset(openDirection))).current;
  const gestureStartOffsetRef = useRef(resolveSwipeOffset(openDirection));
  const isCollabInbox = isCollabInboxTask(task);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dragActivatedRef = useRef(false);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const lastTouchRef = useRef({ x: 0, y: 0 });

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    Animated.spring(translateX, {
      toValue: resolveSwipeOffset(openDirection),
      useNativeDriver: true,
      speed: 24,
      bounciness: 4,
    }).start();
  }, [openDirection, translateX]);

  const swipeResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => false,
        onStartShouldSetPanResponderCapture: () => false,
        onMoveShouldSetPanResponder: (_, gestureState) =>
          !dragActivatedRef.current &&
          Math.abs(gestureState.dx) > Math.abs(gestureState.dy) + 6 && Math.abs(gestureState.dx) > 12,
        onPanResponderGrant: () => {
          clearLongPressTimer();
          gestureStartOffsetRef.current = resolveSwipeOffset(openDirection);
        },
        onPanResponderMove: (_, gestureState) => {
          if (dragActivatedRef.current) return;
          translateX.setValue(
            clamp(gestureStartOffsetRef.current + gestureState.dx, -SWIPE_ACTION_WIDTH, SWIPE_ACTION_WIDTH),
          );
        },
        onPanResponderRelease: (_, gestureState) => {
          if (dragActivatedRef.current) {
            return;
          }
          const nextOffset = clamp(
            gestureStartOffsetRef.current + gestureState.dx,
            -SWIPE_ACTION_WIDTH,
            SWIPE_ACTION_WIDTH,
          );
          if (nextOffset <= -SWIPE_OPEN_THRESHOLD) {
            onOpenDirectionChange("delete");
            void Haptics.selectionAsync();
            return;
          }
          if (nextOffset >= SWIPE_OPEN_THRESHOLD) {
            onOpenDirectionChange("edit");
            void Haptics.selectionAsync();
            return;
          }
          onOpenDirectionChange(null);
        },
        onPanResponderTerminate: () => {
          clearLongPressTimer();
          onOpenDirectionChange(null);
        },
      }),
    [clearLongPressTimer, onOpenDirectionChange, openDirection, translateX],
  );

  const swipeOpen = openDirection !== null;

  const handleTouchStart = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    if (swipeOpen) return;
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    touchStartRef.current = { x: touch.pageX, y: touch.pageY };
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    dragActivatedRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = setTimeout(() => {
      dragActivatedRef.current = true;
      onDragStart?.(task, lastTouchRef.current.x, lastTouchRef.current.y);
    }, DRAG_LONG_PRESS_MS);
  }, [clearLongPressTimer, onDragStart, swipeOpen, task]);

  const handleTouchMove = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    if (dragActivatedRef.current) {
      onDragMove?.(touch.pageX, touch.pageY);
      return;
    }
    const dx = touch.pageX - touchStartRef.current.x;
    const dy = touch.pageY - touchStartRef.current.y;
    if (Math.abs(dx) > DRAG_CANCEL_DISTANCE || Math.abs(dy) > DRAG_CANCEL_DISTANCE) {
      clearLongPressTimer();
    }
  }, [clearLongPressTimer, onDragMove]);

  const handleTouchEnd = useCallback(() => {
    clearLongPressTimer();
    if (dragActivatedRef.current) {
      dragActivatedRef.current = false;
      onDragEnd?.();
    }
  }, [clearLongPressTimer, onDragEnd]);

  const handleTouchCancel = useCallback(() => {
    clearLongPressTimer();
    // Do not end an active drag on responder cancellation.
    // The parent scroll view / modal transition may transiently cancel the
    // original touch target before the user actually lifts the finger.
  }, [clearLongPressTimer]);

  return (
    <View style={s.swipeCardShell}>
      <View style={s.swipeActionsLayer} pointerEvents="box-none">
        <Animated.View
          style={[
            s.swipeAction,
            s.swipeActionEdit,
            {
              opacity: translateX.interpolate({
                inputRange: [0, SWIPE_ACTION_WIDTH],
                outputRange: [0, 1],
                extrapolate: "clamp",
              }),
            },
          ]}
          pointerEvents={openDirection === "edit" ? "auto" : "none"}
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={0.82} onPress={onEdit}>
            <View style={[s.swipeAction, s.swipeActionEdit, { position: "relative", width: "100%", height: "100%" }]}>
              <Text style={s.swipeActionText}>编辑</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>
        <Animated.View
          style={[
            s.swipeAction,
            s.swipeActionDelete,
            {
              opacity: translateX.interpolate({
                inputRange: [-SWIPE_ACTION_WIDTH, 0],
                outputRange: [1, 0],
                extrapolate: "clamp",
              }),
            },
          ]}
          pointerEvents={openDirection === "delete" ? "auto" : "none"}
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={0.82} onPress={onDelete}>
            <View style={[s.swipeAction, s.swipeActionDelete, { position: "relative", width: "100%", height: "100%" }]}>
              <Text style={s.swipeActionText}>删除</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>
      </View>
      <Animated.View
        style={[s.swipeCardWrap, { transform: [{ translateX }] }]}
        {...swipeResponder.panHandlers}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchCancel}
      >
        <TouchableOpacity
          style={[s.taskRow, isFocusMatched && s.taskRowFocus]}
          activeOpacity={swipeOpen ? 1 : 0.6}
          onPress={() => {
            if (swipeOpen) {
              onOpenDirectionChange(null);
              return;
            }
            onPress();
          }}
        >
          {isCollabInbox ? (
            <View style={[s.collabDot, { backgroundColor: isDone ? palette.emerald : palette.airyBlue }]} />
          ) : (
            <TouchableOpacity
              style={[s.taskCheck, isDone && s.taskCheckDone]}
              activeOpacity={isDone ? 1 : 0.8}
              disabled={isDone || !onToggleComplete}
              onPress={(event) => {
                event.stopPropagation?.();
                onToggleComplete?.();
              }}
            >
              {isDone ? <Check size={13} strokeWidth={3} color="#FFFFFF" /> : null}
            </TouchableOpacity>
          )}
          <View style={s.taskRowBody}>
            <View style={s.taskRowTitleLine}>
              {!isCollabInbox && task.priority === "high" ? <View style={s.priorityDot} /> : null}
              <Text style={[s.taskRowTitle, isDone && s.taskRowTitleDone]} numberOfLines={2}>
                {task.title}
              </Text>
              {isCollabInbox ? (
                <View style={s.collabPill}>
                  <Text style={s.collabPillText}>待确认</Text>
                </View>
              ) : null}
            </View>
            <Text style={s.taskRowMeta} numberOfLines={2}>
              {buildTaskMeta(task)}
            </Text>
            <TaskSyncBadge task={task} compact style={s.taskRowSync} />
          </View>
        </TouchableOpacity>
      </Animated.View>
    </View>
  );
}

// ─── Main Component ────────────────────────────

export default function TasksScreen() {
  useRenderCount("TasksScreen");
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ modal?: string; trigger?: string; from?: string }>();
  const { board, isHydrated, refresh } = useTaskBoard();

  // P0-2: tab 聚焦时立刻拉一次（避免切走再回来看到旧数据）
  useFocusEffect(
    useCallback(() => {
      void refresh().catch(() => undefined);
    }, [refresh]),
  );

  const {
    focus,
    clients,
    eventLines,
    setCurrentFocusBrowseFromTask,
    setCurrentFocusBrowseFromEventLine,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterKey>("today");
  const [selectedTask, setSelectedTask] = useState<TaskRecord | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showSmartInput, setShowSmartInput] = useState(false);
  const [showRecord, setShowRecord] = useState(false);
  const [recordTaskContext, setRecordTaskContext] = useState<TaskRecord | null>(null);
  // 现场记录（FAB 入口）打开后立即开始录音，避免"开界面→再点开始"的二次点击。
  const [recordAutoStart, setRecordAutoStart] = useState(false);
  const [reviewTaskContext, setReviewTaskContext] = useState<TaskRecord | null>(null);
  const [editingTask, setEditingTask] = useState<TaskRecord | null>(null);
  const [smartDraft, setSmartDraft] = useState<SmartTaskDraft | null>(null);
  const [createPreset, setCreatePreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [smartInputPreset, setSmartInputPreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const [openSwipeTaskId, setOpenSwipeTaskId] = useState<string | null>(null);
  const [openSwipeDirection, setOpenSwipeDirection] = useState<SwipeActionDirection>(null);
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [eventLineDrawerId, setEventLineDrawerId] = useState<string | null>(null);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);

  // ─── Drag-to-calendar state (declarations only — callbacks below) ──
  const [dragTask, setDragTask] = useState<TaskRecord | null>(null);
  const [dragCalendarMonth, setDragCalendarMonth] = useState(() => { const d = new Date(); return { year: d.getFullYear(), month: d.getMonth() }; });
  const dragDateLayouts = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const lastHoveredRef = useRef<string | null>(null);
  const dragTaskRef = useRef<TaskRecord | null>(null);
  // 全程跑 UI 线程的共享值(拖动期间零 React 重渲染)—— 丝滑跟手
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  const dragLift = useSharedValue(0);
  const overlayProgress = useSharedValue(0);
  const hoveredKey = useSharedValue<string | null>(null);

  const handledModalTriggerRef = useRef<string | null>(null);
  const smartInputRecoveryInFlightRef = useRef(false);
  const lastRecoveryAttemptAtRef = useRef<number | null>(null);
  const lastRecoveredDraftKeyRef = useRef<string | null>(null);
  const recoveryRequestVersionRef = useRef(0);
  const queuedCountRequestVersionRef = useRef(0);
  const lastQueuedCountRef = useRef(0);
  const [queuedDraftCount, setQueuedDraftCount] = useState(0);
  const [queuedRecoveryDismissed, setQueuedRecoveryDismissed] = useState(false);
  const [isRecoveringDraft, setIsRecoveringDraft] = useState(false);

  const refreshQueuedDraftCount = useCallback(async () => {
    const requestVersion = ++queuedCountRequestVersionRef.current;
    try {
      const nextCount = await getQueuedSmartInputCount();
      if (requestVersion !== queuedCountRequestVersionRef.current) {
        return;
      }
      setQueuedDraftCount(nextCount);
    } catch {}
  }, []);

  const hasBlockingUi = showSmartInput || showRecord || showCreate || Boolean(selectedTask) || Boolean(reviewTaskContext);

  const recoverQueuedSmartInput = useCallback(async (trigger: RecoveryTrigger) => {
    if (hasBlockingUi) {
      devLog("smartInputRecovery", "skipped.blocking_ui", { trigger });
      return false;
    }
    const nowMs = Date.now();
    if (!shouldAttemptSmartInputRecovery({
      trigger,
      queuedCount: queuedDraftCount,
      inFlight: smartInputRecoveryInFlightRef.current,
      nowMs,
      lastAttemptAt: lastRecoveryAttemptAtRef.current,
    })) {
      devLog("smartInputRecovery", "skipped.guard", { trigger, queuedDraftCount });
      return false;
    }

    devLog("smartInputRecovery", "attempt", { trigger, queuedDraftCount });
    lastRecoveryAttemptAtRef.current = nowMs;
    smartInputRecoveryInFlightRef.current = true;
    const requestVersion = recoveryRequestVersionRef.current;
    setIsRecoveringDraft(true);
    try {
      const recovered = await flushQueuedSmartInputDrafts(1);
      await refreshQueuedDraftCount();
      if (requestVersion !== recoveryRequestVersionRef.current) {
        devLog("smartInputRecovery", "skipped.stale_request", { trigger });
        return false;
      }
      const recoveredDraft = recovered[0]?.draft ?? null;
      if (!recoveredDraft) {
        devLog("smartInputRecovery", "empty", { trigger });
        return false;
      }

      const recoveredDraftKey = buildRecoveredDraftKey(recoveredDraft);
      if (!shouldUseRecoveredDraft(recoveredDraftKey, lastRecoveredDraftKeyRef.current)) {
        devLog("smartInputRecovery", "skipped.duplicate", { trigger });
        return false;
      }
      lastRecoveredDraftKeyRef.current = recoveredDraftKey;

      setEditingTask(null);
      setSmartDraft(recoveredDraft);
      setCreatePreset({
        dueDate: recoveredDraft.dueDate ?? undefined,
        dueTime: recoveredDraft.dueTime ?? undefined,
      });

      if (shouldAutoOpenRecoveredDraft({
        trigger,
        isTasksScreenActive: true,
        hasBlockingUi,
      })) {
        setShowCreate(true);
        devLog("smartInputRecovery", "restored", { trigger, autoOpened: true });
        return true;
      }
      devLog("smartInputRecovery", "restored", { trigger, autoOpened: false });
      return true;
    } catch (error) {
      devLog("smartInputRecovery", "failed", {
        trigger,
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    } finally {
      smartInputRecoveryInFlightRef.current = false;
      setIsRecoveringDraft(false);
    }
  }, [hasBlockingUi, queuedDraftCount, refreshQueuedDraftCount]);

  useEffect(() => {
    void refreshQueuedDraftCount();
  }, [refreshQueuedDraftCount]);

  useEffect(() => {
    if (queuedDraftCount !== lastQueuedCountRef.current) {
      setQueuedRecoveryDismissed(false);
      lastQueuedCountRef.current = queuedDraftCount;
    }
  }, [queuedDraftCount]);

  // Web preview debug callbacks (dev builds only — stripped from release bundles)
  useEffect(() => {
    if (!__DEV__) return;
    if (Platform.OS !== "web") return;
    if (typeof window === "undefined") return;
    (window as any).__yiyu_debug_create = () => { setSmartDraft(null); setCreatePreset({}); setShowCreate(true); };
    (window as any).__yiyu_debug_smart = () => { setShowSmartInput(true); };
    (window as any).__yiyu_debug_record = () => { setRecordTaskContext(null); setShowRecord(true); };
    return () => {
      try {
        delete (window as any).__yiyu_debug_create;
        delete (window as any).__yiyu_debug_smart;
        delete (window as any).__yiyu_debug_record;
      } catch {
        /* ignore */
      }
    };
  }, []);

  // Handle modal trigger from SuperFAB
  useEffect(() => {
    if (!params.trigger || handledModalTriggerRef.current === params.trigger) return;
    handledModalTriggerRef.current = params.trigger;
    if (params.modal === "create") {
      // P1-A: 从 consult tab "加为任务"过来时，先取出预置的 SmartTaskDraft 预填 title/description/client
      const consultDraft = params.from === "consult" ? takePendingConsultDraft() : null;
      setSmartDraft(consultDraft); setCreatePreset({}); setRecordTaskContext(null);
      setShowSmartInput(false); setShowRecord(false); setShowCreate(true);
    } else if (params.modal === "smart") {
      setShowCreate(false); setShowRecord(false); setRecordTaskContext(null);
      setSmartInputPreset({}); setSmartDraft(null); setShowSmartInput(true);
    } else if (params.modal === "record") {
      setShowCreate(false); setShowSmartInput(false);
      setRecordTaskContext(null); setRecordAutoStart(true); setShowRecord(true);
    }
  }, [params.modal, params.trigger]);

  // ─── Android back ────────────────────────────

  useAndroidExitApp(
    useCallback(() => {
      if (showFilterMenu) { setShowFilterMenu(false); return true; }
      if (workspaceClientId) { setWorkspaceClientId(null); return true; }
      if (eventLineDrawerId) { setEventLineDrawerId(null); return true; }
      if (showSmartInput) { setShowSmartInput(false); setSmartInputPreset({}); return true; }
      if (showRecord) { setShowRecord(false); setRecordTaskContext(null); return true; }
      if (reviewTaskContext) { setReviewTaskContext(null); return true; }
      if (showCreate) { setShowCreate(false); return true; }
      if (selectedTask) { setSelectedTask(null); return true; }
      return false;
    }, [eventLineDrawerId, reviewTaskContext, selectedTask, showCreate, showFilterMenu, showRecord, showSmartInput, workspaceClientId]),
  );

  // ─── Handlers ────────────────────────────────

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
      await refreshQueuedDraftCount();
    } finally {
      setRefreshing(false);
    }
  }, [refresh, refreshQueuedDraftCount]);

  const closeSwipeActions = useCallback(() => {
    setOpenSwipeTaskId(null);
    setOpenSwipeDirection(null);
  }, []);

  // ─── Drag-to-calendar(UI 线程丝滑版)──────────
  // 一次连续触摸全程拥有拖动(无 responder 交接);浮层纯视觉(pointerEvents=none);
  // ghost/高亮/淡入淡出全部跑共享值 → UI 线程 60fps,拖动期间零 React 重渲染。
  const onCellMeasured = useCallback((dateKey: string, frame: { x: number; y: number; w: number; h: number } | null) => {
    if (!frame) { dragDateLayouts.current.delete(dateKey); return; }
    dragDateLayouts.current.set(dateKey, frame);
  }, []);

  const findDragHoveredDate = useCallback((px: number, py: number): string | null => {
    for (const [key, layout] of dragDateLayouts.current) {
      if (px >= layout.x && px <= layout.x + layout.w && py >= layout.y && py <= layout.y + layout.h) {
        return key;
      }
    }
    return null;
  }, []);

  const handleDragStart = useCallback((task: TaskRecord, pageX: number, pageY: number) => {
    closeSwipeActions();
    dragTaskRef.current = task;
    lastHoveredRef.current = null;
    const now = new Date();
    setDragCalendarMonth({ year: now.getFullYear(), month: now.getMonth() });
    dragDateLayouts.current.clear();
    dragX.value = pageX;
    dragY.value = pageY;
    hoveredKey.value = null;
    overlayProgress.value = withTiming(1, { duration: 170 });
    dragLift.value = withTiming(1, { duration: 150 });
    setDragTask(task); // 在共享值就绪后再挂浮层,保证首帧位置正确
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }, [closeSwipeActions, dragLift, dragX, dragY, hoveredKey, overlayProgress]);

  const handleDragMove = useCallback((pageX: number, pageY: number) => {
    dragX.value = pageX;
    dragY.value = pageY;
    // 命中点在手指上方 DRAG_TARGET_OFFSET_Y,使高亮的目标日期落在手的上方、看得见。
    const hovered = findDragHoveredDate(pageX, pageY - DRAG_TARGET_OFFSET_Y);
    if (hovered !== lastHoveredRef.current) {
      lastHoveredRef.current = hovered;
      hoveredKey.value = hovered; // 高亮在 UI 线程更新,不触发重渲染
      if (hovered) void Haptics.selectionAsync();
    }
  }, [dragX, dragY, hoveredKey, findDragHoveredDate]);

  const handleDragEnd = useCallback(async () => {
    const task = dragTaskRef.current;
    const targetDate = lastHoveredRef.current;
    dragTaskRef.current = null;
    // 平滑淡出 + 落下,动画结束再卸载浮层
    overlayProgress.value = withTiming(0, { duration: 150 }, (done) => {
      "worklet";
      if (done) runOnJS(setDragTask)(null);
    });
    dragLift.value = withTiming(0, { duration: 130 });
    if (!task || !targetDate) return; // 松手在空白处 = 静默取消
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    try {
      await moveTaskToCalendarTarget(task, targetDate, targetDate);
    } catch {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert("改期失败", "请检查网络或同步状态后重试。");
      void refresh();
    }
  }, [dragLift, overlayProgress, refresh]);

  // 浮层接管"进行中的那根手指"(PanResponder 能接管 in-progress touch);移动只写共享值,
  // ghost/高亮/淡入全在 UI 线程渲染,拖动期间零 React 重渲染 → 不卡死 + 流畅。
  const dragPanResponder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => !!dragTaskRef.current,
    onStartShouldSetPanResponderCapture: () => !!dragTaskRef.current,
    onMoveShouldSetPanResponder: () => !!dragTaskRef.current,
    onMoveShouldSetPanResponderCapture: () => !!dragTaskRef.current,
    onPanResponderTerminationRequest: () => false,
    onPanResponderMove: (evt) => {
      const { pageX, pageY } = evt.nativeEvent;
      handleDragMove(pageX, pageY);
    },
    onPanResponderRelease: () => { void handleDragEnd(); },
    onPanResponderTerminate: () => { void handleDragEnd(); },
  }), [handleDragEnd, handleDragMove]);

  const handleEditInboxTask = useCallback((task: TaskRecord) => {
    closeSwipeActions();
    setEditingTask(task);
    setCreatePreset({});
    setShowCreate(true);
  }, [closeSwipeActions]);

  const applySmartDraft = useCallback((draft: SmartTaskDraft) => {
    const mergedDraft: SmartTaskDraft = {
      ...draft,
      dueDate: draft.dueDate ?? smartInputPreset.dueDate ?? null,
      dueTime: draft.dueTime ?? smartInputPreset.dueTime ?? null,
    };
    setShowSmartInput(false);
    setSmartInputPreset({});
    setEditingTask(null);
    setSmartDraft(mergedDraft);
    setCreatePreset({
      dueDate: mergedDraft.dueDate ?? undefined,
      dueTime: mergedDraft.dueTime ?? undefined,
    });
    setShowCreate(true);
  }, [smartInputPreset.dueDate, smartInputPreset.dueTime]);

  const applyTaskUpdates = useCallback(async (taskId: string, updates: Partial<TaskRecord>) => {
    const isScheduleUpdate = Object.prototype.hasOwnProperty.call(updates, "dueDate")
      || Object.prototype.hasOwnProperty.call(updates, "durationMinutes")
      || Object.prototype.hasOwnProperty.call(updates, "deadlineAt")
      || Object.prototype.hasOwnProperty.call(updates, "scheduledStartAt")
      || Object.prototype.hasOwnProperty.call(updates, "scheduledEndAt");

    let nextTask: TaskRecord | null = null;
    if (isScheduleUpdate) {
      const scheduleUpdates: Pick<Partial<TaskRecord>, "dueDate" | "durationMinutes" | "deadlineAt" | "scheduledStartAt" | "scheduledEndAt"> = {};
      if (Object.prototype.hasOwnProperty.call(updates, "dueDate")) {
        scheduleUpdates.dueDate = updates.dueDate;
      }
      if (Object.prototype.hasOwnProperty.call(updates, "durationMinutes")) {
        scheduleUpdates.durationMinutes = updates.durationMinutes;
      }
      if (Object.prototype.hasOwnProperty.call(updates, "deadlineAt")) {
        scheduleUpdates.deadlineAt = updates.deadlineAt;
      }
      if (Object.prototype.hasOwnProperty.call(updates, "scheduledStartAt")) {
        scheduleUpdates.scheduledStartAt = updates.scheduledStartAt;
      }
      if (Object.prototype.hasOwnProperty.call(updates, "scheduledEndAt")) {
        scheduleUpdates.scheduledEndAt = updates.scheduledEndAt;
      }
      nextTask = await updateCalendarTaskSchedule(taskId, scheduleUpdates);
    } else {
      updateTaskOfflineFirst(taskId, updates);
      nextTask = localDb.getTaskById(taskId);
    }

    setSelectedTask((current) => (
      current?.id === taskId
        ? nextTask ?? { ...current, ...updates }
        : current
    ));
    void refresh();
    return nextTask;
  }, [refresh]);

  const handleDeleteInboxTask = useCallback((task: TaskRecord) => {
    closeSwipeActions();
    Alert.alert("删除任务", `确认删除「${task.title}」吗？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            deleteTaskOfflineFirst(task.id);
            void refresh();
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            void refresh();
            Alert.alert("删除失败", "请检查网络后重试。");
          }
        },
      },
    ]);
  }, [closeSwipeActions, refresh]);

  const handleMarkTaskDone = useCallback((task: TaskRecord) => {
    if (task.progressStatus === "done") {
      return;
    }
    closeSwipeActions();
    void applyTaskUpdates(task.id, { progressStatus: "done" }).catch(() => {
      Alert.alert("完成任务失败", "请检查网络或同步状态后重试。");
      void refresh();
    });
  }, [applyTaskUpdates, closeSwipeActions]);

  // ─── Computed ────────────────────────────────

  const tasks = board.tasks ?? [];
  const todayKey = formatDateKey(new Date());
  // FocusBar 已下线 —— 默认就是"全部客户"视图，不再按 focus 过滤
  const effectiveTasks = tasks;
  const orderedTasks = tasks;
  const focusMatchedTaskIds = useMemo<ReadonlySet<string>>(() => new Set(), []);
  const selectedTaskEventLine = useMemo(
    () => eventLines.find((item) => item.id === selectedTask?.eventLineId) ?? null,
    [eventLines, selectedTask?.eventLineId],
  );
  const drawerEventLine = useMemo(
    () => eventLines.find((item) => item.id === eventLineDrawerId) ?? null,
    [eventLineDrawerId, eventLines],
  );
  const handleTransferDrawerEventLine = useCallback(async (clientId: string) => {
    if (!drawerEventLine) {
      return;
    }
    const targetClient = clients.find((item) => item.id === clientId);
    if (!targetClient) {
      Alert.alert("迁移失败", "目标客户不存在，请刷新后重试。");
      return;
    }
    setTransferringEventLineId(drawerEventLine.id);
    try {
      await transferEventLineToClient(drawerEventLine.id, clientId);
      Alert.alert("已更新归属", `已把「${drawerEventLine.name}」转到客户「${targetClient.name}」下。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查网络连接后重试。";
      Alert.alert("迁移失败", message);
    } finally {
      setTransferringEventLineId(null);
    }
  }, [clients, drawerEventLine]);

  const filteredTasks = useMemo(() => {
    if (filter === "collab_inbox") return orderedTasks.filter(isCollabInboxTask);
    if (filter === "today") return orderedTasks.filter((t) => !getTaskCalendarDateKey(t) || getTaskCalendarDateKey(t) === todayKey);
    if (filter === "unreviewed") return orderedTasks.filter((t) => t.progressStatus !== "done");
    // "all" - this week
    const now = new Date();
    const { startKey: monStr, endKey: sunStr } = getLocalWeekRangeKeys(now);
    return orderedTasks.filter((t) => {
      const d = getTaskCalendarDateKey(t);
      if (!d) return true;
      return d >= monStr && d <= sunStr;
    });
  }, [filter, orderedTasks, todayKey]);

  const collabInboxTasks = useMemo(
    () => filteredTasks.filter(isCollabInboxTask),
    [filteredTasks],
  );

  // Pending scheduling = unscheduled tasks excluding collaboration inbox tasks
  const pendingScheduleTasks = useMemo(() => {
    if (filter === "collab_inbox") return [];
    if (filter === "today") {
      return orderedTasks.filter(
        (t) => t.progressStatus !== "done" && !isCollabInboxTask(t) && !hasScheduledDate(t),
      );
    }
    return filteredTasks.filter((t) => !isCollabInboxTask(t) && !hasScheduledDate(t));
  }, [filter, filteredTasks, orderedTasks]);

  // Scheduled tasks (for today or filtered)
  const scheduledTasks = useMemo(() => {
    if (filter === "collab_inbox") return [];
    if (filter === "today") {
      return orderedTasks.filter(
        (t) => !isCollabInboxTask(t) && getTaskCalendarDateKey(t) === todayKey,
      );
    }
    return filteredTasks.filter((t) => !isCollabInboxTask(t) && hasScheduledDate(t));
  }, [filter, filteredTasks, orderedTasks, todayKey]);

  // ─── Render ──────────────────────────────────

  if (!isHydrated) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={palette.inkBlack} />
      </View>
    );
  }

  const filterLabel = FILTERS.find((f) => f.key === filter)?.label ?? "今日任务";
  const visibleQueuedDraftCount = queuedRecoveryDismissed ? 0 : queuedDraftCount;

  return (
    <SafeAreaView style={s.container} edges={["left", "right"]}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={palette.inkBlack} />}
        contentContainerStyle={{ paddingBottom: chrome.tabBarHeight + 34 }}
        stickyHeaderIndices={[0]}
        onScrollBeginDrag={closeSwipeActions}
        scrollEnabled={!dragTask}
      >
        <TasksHeader
          dateText={formatDate()}
          filterLabel={filterLabel}
          topPadding={chrome.headerTopPadding}
          onOpenFilter={() => setShowFilterMenu(true)}
        />

        <SmartInputRecoveryController
          queuedCount={visibleQueuedDraftCount}
          hasRecoveredDraft={Boolean(smartDraft) && !showCreate}
          isRecovering={isRecoveringDraft}
          onRequestRecovery={(trigger) => {
            void recoverQueuedSmartInput(trigger);
          }}
          onOpenRecoveredDraft={() => {
            if (smartDraft) {
              setShowCreate(true);
            }
          }}
          onDismissRecoveredDraft={() => {
            recoveryRequestVersionRef.current += 1;
            setSmartDraft(null);
            setCreatePreset({});
          }}
          onDismissQueuedRecovery={() => {
            void (async () => {
              setQueuedRecoveryDismissed(true);
              queuedCountRequestVersionRef.current += 1;
              try {
                recoveryRequestVersionRef.current += 1;
                await clearSmartInputQueue();
              } finally {
                smartInputRecoveryInFlightRef.current = false;
                lastRecoveryAttemptAtRef.current = null;
                setIsRecoveringDraft(false);
                setSmartDraft(null);
                setCreatePreset({});
                await refreshQueuedDraftCount();
              }
            })();
          }}
        />

        {/* 今日重点 Dashboard 卡已按产品要求移除 */}

        <InboxTaskList
          title="协作收件箱"
          hint="别人派给你的待确认任务，先确认再进入自己的推进节奏。"
          tasks={collabInboxTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <SwipeInboxCard
                key={task.id}
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                openDirection={openSwipeTaskId === task.id ? openSwipeDirection : null}
                onOpenDirectionChange={(direction) => {
                  if (direction) {
                    setOpenSwipeTaskId(task.id);
                    setOpenSwipeDirection(direction);
                    return;
                  }
                  if (openSwipeTaskId === task.id) {
                    closeSwipeActions();
                  }
                }}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onEdit={() => handleEditInboxTask(task)}
                onDelete={() => handleDeleteInboxTask(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
            );
          }}
        />

        <InboxTaskList
          title="待安排任务"
          hint="这些任务还没排到具体日期或时间，可长按直接拖入日历。"
          tasks={pendingScheduleTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <SwipeInboxCard
                key={task.id}
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                openDirection={openSwipeTaskId === task.id ? openSwipeDirection : null}
                onOpenDirectionChange={(direction) => {
                  if (direction) {
                    setOpenSwipeTaskId(task.id);
                    setOpenSwipeDirection(direction);
                    return;
                  }
                  if (openSwipeTaskId === task.id) {
                    closeSwipeActions();
                  }
                }}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onEdit={() => handleEditInboxTask(task)}
                onDelete={() => handleDeleteInboxTask(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
            );
          }}
        />

        <ScheduledTaskList
          title={filter === "today" ? "今日安排" : "已安排任务"}
          tasks={scheduledTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <SwipeableTaskRow
                key={task.id}
                isDone={isDone}
                onComplete={isDone ? undefined : () => handleMarkTaskDone(task)}
                onReschedule={() => { closeSwipeActions(); setSelectedTask(task); }}
              >
              <ScheduledCardWithDrag
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
              </SwipeableTaskRow>
            );
          }}
        />

        {/* Empty state */}
        {collabInboxTasks.length === 0 && pendingScheduleTasks.length === 0 && scheduledTasks.length === 0 && (
          <View style={s.empty}>
            <Inbox size={48} color={colors.textTertiary} />
            <Text style={s.emptyText}>{filter === "collab_inbox" ? "暂无协作收件箱任务" : "暂无任务"}</Text>
          </View>
        )}
      </ScrollView>

      <TasksFilterBar
        visible={showFilterMenu}
        floatingMenuTopInset={chrome.floatingMenuTopInset}
        selectedKey={filter}
        filters={FILTERS}
        onSelect={(nextFilter) => {
          setFilter(nextFilter);
          setShowFilterMenu(false);
        }}
        onClose={() => setShowFilterMenu(false)}
      />

      <TaskModalCoordinator
        selectedTask={selectedTask}
        selectedTaskEventLine={selectedTaskEventLine}
        showCreate={showCreate}
        showSmartInput={showSmartInput}
        showRecord={showRecord}
        reviewTaskContext={reviewTaskContext}
        editingTask={editingTask}
        smartDraft={smartDraft}
        createPreset={createPreset}
        smartInputPreset={smartInputPreset}
        todayKey={todayKey}
        recordTaskContext={recordTaskContext}
        recordAutoStart={recordAutoStart}
        onCloseSelectedTask={() => setSelectedTask(null)}
        onStartReview={(task) => {
          setReviewTaskContext(task);
          setSelectedTask(null);
        }}
        onRecordFromTaskDetail={() => {
          if (!selectedTask) return;
          setRecordTaskContext(selectedTask);
          setSelectedTask(null);
          setShowRecord(true);
        }}
        onUpdateTask={(taskId, updates) => {
          void applyTaskUpdates(taskId, updates).catch(() => {
            Alert.alert("更新任务失败", "请检查网络或同步状态后重试。");
            void refresh();
          });
        }}
        onDeleteTask={async (task) => {
          try {
            deleteTaskOfflineFirst(task.id);
            setSelectedTask(null);
            void refresh();
            await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            void refresh();
            Alert.alert("删除失败", "请检查网络后重试。");
          }
        }}
        onReplaceSelectedTask={(task) => {
          setSelectedTask(task);
          void refresh();
        }}
        onOpenClientWorkspace={(clientId) => setWorkspaceClientId(clientId)}
        onOpenEventLine={(eventLineId) => {
          setCurrentFocusBrowseFromEventLine(eventLineId);
          setEventLineDrawerId(eventLineId);
        }}
        onOpenConsult={(task) => {
          setCurrentFocusBrowseFromTask(task);
          setSelectedTask(null);
          router.push("/(tabs)/consult");
        }}
        onCloseCreate={() => {
          setShowCreate(false);
          setEditingTask(null);
          setSmartDraft(null);
        }}
        onCreated={() => {
          setShowCreate(false);
          setEditingTask(null);
          setSmartDraft(null);
          void refresh();
        }}
        onCloseSmartInput={() => {
          setShowSmartInput(false);
          setSmartInputPreset({});
          void refreshQueuedDraftCount();
        }}
        onApplySmartDraft={applySmartDraft}
        onUploadedRecord={(task) => {
          setShowRecord(false);
          setRecordTaskContext(null);
          setRecordAutoStart(false);
          setSelectedTask(task);
          void refresh();
        }}
        onCloseRecord={() => {
          setShowRecord(false);
          setRecordTaskContext(null);
          setRecordAutoStart(false);
          void refresh();
        }}
        onCloseReview={() => setReviewTaskContext(null)}
        onSavedReview={() => {
          setReviewTaskContext(null);
          void refresh();
        }}
      />

      <DragCalendarOverlay
        dragTask={dragTask}
        dragCalendarMonth={dragCalendarMonth}
        dragX={dragX}
        dragY={dragY}
        dragLift={dragLift}
        overlayProgress={overlayProgress}
        hoveredKey={hoveredKey}
        panHandlers={dragPanResponder.panHandlers}
        formatDateKey={formatDateKey}
        onCellMeasured={onCellMeasured}
      />
      <EventLineDrawer
        visible={Boolean(eventLineDrawerId)}
        eventLine={drawerEventLine}
        tasks={tasks}
        clients={clients}
        meetingHighlights={clientIntel.snapshot?.latestMeetings ?? []}
        onClose={() => setEventLineDrawerId(null)}
        onOpenWorkspace={() => {
          if (drawerEventLine?.primaryClientId) {
            setWorkspaceClientId(drawerEventLine.primaryClientId);
          }
        }}
        onTransferToClient={handleTransferDrawerEventLine}
        isTransferringClient={transferringEventLineId === drawerEventLine?.id}
        onTaskPress={(task) => {
          setEventLineDrawerId(null);
          setSelectedTask(task);
        }}
      />
      <WorkspaceLiteSheet
        visible={Boolean(workspaceClientId)}
        clientId={workspaceClientId}
        clientName={focus.clientName}
        onClose={() => setWorkspaceClientId(null)}
        onTaskPress={(taskId) => {
          const task = localDb.getTaskById(taskId);
          if (!task) {
            return;
          }
          setWorkspaceClientId(null);
          setSelectedTask(task);
        }}
      />
    </SafeAreaView>
  );
}

// ─── Styles ────────────────────────────────────

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: palette.paperRice },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: palette.paperRice },

  // ── 分组清单·任务行(滴答风) ──────────────────────────────
  taskRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 13,
    paddingHorizontal: 16,
    minHeight: 60,
    backgroundColor: palette.surfaceCard,
  },
  taskRowFocus: { backgroundColor: palette.airyBlueBg },
  taskCheck: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: palette.borderStrong,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 13,
    backgroundColor: palette.surfaceCard,
  },
  taskCheckDone: { backgroundColor: palette.emerald, borderColor: palette.emerald },
  collabDot: { width: 9, height: 9, borderRadius: 5, marginLeft: 7, marginRight: 19 },
  taskRowBody: { flex: 1, gap: 3 },
  taskRowTitleLine: { flexDirection: "row", alignItems: "center", gap: 7 },
  priorityDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: palette.rose },
  taskRowTitle: { flex: 1, fontSize: 15, fontWeight: "600", color: palette.textPrimary, lineHeight: 21 },
  taskRowTitleDone: { textDecorationLine: "line-through", color: palette.textMuted, fontWeight: "500" },
  taskRowMeta: { fontSize: 13, color: palette.textTertiary, lineHeight: 18 },
  taskRowSync: { marginTop: 2, alignSelf: "flex-start" },
  taskRowTime: {
    fontSize: 13,
    fontWeight: "600",
    color: palette.textTertiary,
    marginLeft: 10,
    fontVariant: ["tabular-nums"],
  },
  collabPill: {
    backgroundColor: palette.surfaceMuted,
    borderRadius: borderRadius.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  collabPillText: { fontSize: 11, fontWeight: "700", color: palette.textTertiary },
  // Header
  header: {
    backgroundColor: palette.paperRice,
    paddingHorizontal: 20,
    paddingTop: 0,
    paddingBottom: 18,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  date: { fontSize: 20, color: palette.inkBlack, fontWeight: "800", letterSpacing: -0.4 },
  filterDropdown: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(31,42,55,0.06)",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: borderRadius.full,
    gap: 5,
  },
  filterDropdownText: { ...typography.label, fontWeight: "600", color: palette.inkBlack },

  // Filter menu
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(31,42,55,0.24)", // 统一 backdrop
    justifyContent: "flex-start",
    alignItems: "flex-end",
    paddingTop: 0,
    paddingRight: 18,
  },
  menuCard: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12
    paddingVertical: 4,
    minWidth: 140,
  },
  menuItem: { paddingHorizontal: 16, paddingVertical: 12 },
  menuItemActive: { backgroundColor: "rgba(31,42,55,0.06)" },
  menuItemText: { ...typography.body, color: palette.inkBlack },
  menuItemTextActive: { color: palette.inkBlack, fontWeight: "600" },

  // Inbox (unscheduled tasks)
  inboxSection: { paddingHorizontal: 16, paddingTop: 8, marginBottom: 18 },
  inboxHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 12, paddingLeft: 6 },
  inboxTitle: { ...typography.titleCard, color: palette.inkBlack },
  sectionHint: { ...typography.caption, color: palette.textTertiary, marginBottom: 10, paddingLeft: 6 },
  swipeCardShell: { position: "relative", overflow: "hidden", backgroundColor: palette.surfaceCard },
  swipeActionsLayer: {
    ...StyleSheet.absoluteFillObject,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "stretch",
    backgroundColor: colors.surfaceSecondary,
  },
  swipeAction: {
    width: SWIPE_ACTION_WIDTH,
    alignItems: "center",
    justifyContent: "center",
  },
  swipeActionEdit: { backgroundColor: palette.bambooGreen },
  swipeActionDelete: { backgroundColor: colors.error },
  swipeActionText: { fontSize: 14, fontWeight: "700", color: colors.textOnBrand },
  swipeCardWrap: { backgroundColor: "transparent" },
  inboxCard: {
    backgroundColor: palette.paperSmoke,
    borderRadius: borderRadius.md, // 12
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    // 无 shadow，靠 hairline border + paperSmoke 底分层
  },
  focusMatchedCard: {
    borderColor: palette.inkBlue,
    borderLeftWidth: 3,
    backgroundColor: "rgba(31,42,55,0.04)",
  },
  inboxDot: { width: 10, height: 10, borderRadius: 5, marginRight: 14 },
  taskCompleteToggle: {
    width: 22,
    height: 22,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: palette.borderSubtle,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
    backgroundColor: palette.paperRice,
  },
  taskCompleteToggleDone: {
    backgroundColor: palette.inkBlack,
    borderColor: palette.inkBlack,
  },
  inboxCardBody: { flex: 1 },
  inboxCardTitleRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  inboxCardTitle: { fontSize: 15, fontWeight: "700", color: palette.inkBlack, lineHeight: 21 },
  inboxCardTitleDone: { textDecorationLine: "line-through", color: colors.textTertiary },
  inboxCardMeta: { fontSize: 12, color: palette.textTertiary, marginTop: 6, lineHeight: 18 },
  taskSyncBadge: { marginTop: 8 },
  focusChip: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(61,79,102,0.08)",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  focusChipText: {
    ...typography.label,
    color: palette.inkBlue,
  },
  inboxStatusBadge: {
    backgroundColor: palette.paperMoon,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 1,
  },
  inboxStatusBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.inkBronze,
  },
  // P1-F: 日期紧迫度 chip
  inboxDateChip: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 1,
    alignSelf: "flex-start",
  },
  inboxDateChipText: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  // P1-B: 今日 Dashboard 卡
  todayHero: {
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 16,
    borderRadius: borderRadius.lg,
    backgroundColor: palette.airyBlueBg,
    borderWidth: 1,
    borderColor: palette.airyBlueBorder,
    padding: 16,
    gap: 12,
  },
  todayHeroEmpty: {
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 16,
    borderRadius: borderRadius.lg,
    backgroundColor: palette.paperMoon,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    padding: 16,
    gap: 6,
  },
  todayHeroEmptyTitle: {
    ...typography.titleCard,
    color: palette.inkBlack,
  },
  todayHeroEmptyHint: {
    ...typography.caption,
    color: palette.textSecondary,
    lineHeight: 18,
  },
  todayHeroHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  todayHeroLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: palette.airyBlue,
    letterSpacing: 0.3,
    marginBottom: 4,
  },
  todayHeroNumRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 4,
  },
  todayHeroNum: {
    fontSize: 36,
    fontWeight: "800",
    color: palette.inkBlack,
    letterSpacing: -0.5,
    lineHeight: 40,
  },
  todayHeroNumUnit: {
    fontSize: 14,
    fontWeight: "600",
    color: palette.textSecondary,
  },
  todayHeroProgress: {
    marginLeft: 6,
    fontSize: 12,
    color: palette.textSecondary,
  },
  todayHeroChips: {
    alignItems: "flex-end",
    gap: 6,
  },
  todayHeroChip: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  todayHeroChipText: {
    fontSize: 11,
    fontWeight: "700",
  },
  todayHeroCta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: palette.airyBlue,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 8,
    shadowColor: palette.airyBlue,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 10,
    elevation: 3,
  },
  todayHeroCtaText: {
    flex: 1,
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },

  // Scheduled tasks section
  scheduledSection: { paddingHorizontal: 16, marginBottom: 18 },
  scheduledTitle: { fontSize: 17, fontWeight: "800", color: palette.textSecondary, marginBottom: 12, paddingLeft: 6 },
  scheduledCard: {
    backgroundColor: palette.paperSmoke,
    borderRadius: borderRadius.md, // 12
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
  },
  scheduledCardBody: { flex: 1 },
  scheduledCardTitle: { fontSize: 14, fontWeight: "600", color: palette.inkBlack },
  scheduledCardTitleDone: { textDecorationLine: "line-through", color: colors.textTertiary },
  scheduledCardMeta: { fontSize: 11, color: palette.textTertiary, marginTop: 2 },
  scheduledCardTime: { fontSize: 12, fontWeight: "600", color: palette.inkBronze, marginRight: 8 },

  // Empty
  empty: { alignItems: "center", paddingVertical: 80 },
  emptyText: { fontSize: 14, color: palette.textTertiary, marginTop: 12 },
}) as Record<string, any>;

export function ErrorBoundary(props: ErrorBoundaryProps) {
  return (
    <RouteErrorFallback
      {...props}
      label="tasks"
      title="任务页暂时打不开"
      hint="刚才这个页面遇到了异常，你的任务数据保存在本地没有丢失。点下方按钮重试即可。"
    />
  );
}
