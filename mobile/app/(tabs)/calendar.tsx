import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  GestureResponderEvent,
  Modal,
  PanResponder,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { useFocusEffect, useRouter, type ErrorBoundaryProps } from "expo-router";
import { RouteErrorFallback } from "../../components/ErrorBoundary";
import { useAppChromeInsets } from "../../lib/app-chrome";
import * as localDb from "../../lib/local-db";
import {
  colors,
  fontSize,
  spacing,
  borderRadius,
  shadow,
  palette,
  typography,
  iconStroke,
} from "../../lib/theme";
import { useAndroidBackToTasks } from "../../lib/android-back";
import type { TaskRecord, SmartTaskDraft } from "../../lib/types";
import CalendarHeader from "../../components/calendar-screen/CalendarHeader";
import MonthView from "../../components/calendar-screen/MonthView";
import WeekView from "../../components/calendar-screen/WeekView";
import DayView from "../../components/calendar-screen/DayView";
import CalendarDragLayer from "../../components/calendar-screen/CalendarDragLayer";
import CalendarModalCoordinator from "../../components/calendar-screen/CalendarModalCoordinator";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import {
  resizeCalendarTaskDuration,
  updateCalendarTaskSchedule,
} from "../../lib/calendar-repository";
import { deleteTaskOfflineFirst, updateTaskOfflineFirst } from "../../lib/sync-engine";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import { buildWeekSignalSnapshot } from "../../lib/week-signal";
import { getLocalWeekAnchorDateKey, weekLabelForDateKey } from "../../lib/date";
import {
  buildMonthCalendarDays,
  getAllDayTasksForDate,
  getScheduledTasksForDate,
  getTasksForDate,
  groupTasksByDate,
} from "../../lib/calendar-selectors";
import { getTaskScheduleDateTime } from "../../lib/task-time";

// ─── Constants ─────────────────────────────────

type CalendarView = "day" | "week" | "month";

const VIEW_OPTIONS: { key: CalendarView; label: string }[] = [
  { key: "month", label: "月" },
  { key: "week", label: "周" },
  { key: "day", label: "日" },
];

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"] as const;
const WEEKDAY_CN = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"] as const;

const HOUR_HEIGHT = 60;
const TIMELINE_START = 0;
const TIMELINE_END = 24;
const DRAG_DOT_SIZE = 40;
const DRAG_DOT_FINGER_OFFSET_Y = 130; // two finger-widths above touch point (touch is on finger pad, not tip)
const DRAG_LONG_PRESS_MS = 450; // 长按起拖阈值：250ms 太短易把"想点开/想滚动"误判为拖拽改期
const DRAG_CANCEL_DISTANCE = 8;

// ─── Helpers ────────────────────────────────────

function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getWeekDates(date: Date): Date[] {
  const day = (date.getDay() + 6) % 7;
  const dates: Date[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(date);
    d.setDate(date.getDate() - day + i);
    d.setHours(0, 0, 0, 0);
    dates.push(d);
  }
  return dates;
}

function getTaskBlockHeight(durationMinutes: number): number {
  return Math.max((durationMinutes / 60) * HOUR_HEIGHT, 28);
}

function getCurrentTimeOffset(): number {
  const now = new Date();
  return (now.getHours() - TIMELINE_START) * HOUR_HEIGHT + (now.getMinutes() / 60) * HOUR_HEIGHT;
}

function isValidTimelineHour(hour: number): boolean {
  return Number.isInteger(hour) && hour >= 0 && hour <= 23;
}

// ─── Types ──────────────────────────────────────

interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

interface DropZoneLayout {
  key: string; // dateKey or "hour:HH"
  x: number;
  y: number;
  width: number;
  height: number;
}

function resolveDragDotHoverPoint(pageX: number, pageY: number) {
  return {
    x: pageX,
    y: pageY - DRAG_DOT_FINGER_OFFSET_Y,
  };
}

// ─── Component ──────────────────────────────────

export default function CalendarScreen() {
  useRenderCount("CalendarScreen");
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const now = new Date();

  const [viewMode, setViewMode] = useState<CalendarView>("month");
  const [showViewMenu, setShowViewMenu] = useState(false);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selectedDate, setSelectedDate] = useState(
    new Date(now.getFullYear(), now.getMonth(), now.getDate()),
  );
  const selectedDateKey = toDateKey(selectedDate);

  const { board, isHydrated, refresh } = useTaskBoard();

  // P0-2: tab 聚焦时立刻拉一次（切走再回来不再看到旧数据）
  useFocusEffect(
    useCallback(() => {
      void refresh().catch(() => undefined);
    }, [refresh]),
  );

  const {
    focus,
    clients,
    eventLines,
    setCurrentFocusBrowseFromCalendar,
    setCurrentFocusBrowseFromEventLine,
    setCurrentFocusWeek,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const tasks = board.tasks;
  const [refreshing, setRefreshing] = useState(false);
  const [resizeDrafts, setResizeDrafts] = useState<Record<string, number>>({});
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [eventLineDrawerId, setEventLineDrawerId] = useState<string | null>(null);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);

  // Modal states
  const [selectedTask, setSelectedTask] = useState<TaskRecord | null>(null);
  const [recordTaskContext, setRecordTaskContext] = useState<TaskRecord | null>(null);
  const [reviewTaskContext, setReviewTaskContext] = useState<TaskRecord | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showSmartInput, setShowSmartInput] = useState(false);
  const [smartDraft, setSmartDraft] = useState<SmartTaskDraft | null>(null);
  const [createPreset, setCreatePreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [smartInputPreset, setSmartInputPreset] = useState<{ dueDate?: string; dueTime?: string }>({});

  // Week view expanded days
  const [expandedWeekDay, setExpandedWeekDay] = useState<string | null>(null);

  const timelineRef = useRef<ScrollView>(null);
  const [currentTimeOffset, setCurrentTimeOffset] = useState(getCurrentTimeOffset());

  // ─── Drag system ─────────────────────────────

  const [draggingTask, setDraggingTask] = useState<TaskRecord | null>(null);
  const [hoveredDropKey, setHoveredDropKey] = useState<string | null>(null);
  const dragTranslate = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const dragOpacity = useRef(new Animated.Value(0)).current;
  const dragScale = useRef(new Animated.Value(0.9)).current;
  const containerRef = useRef<View>(null);
  const containerOffsetRef = useRef({ x: 0, y: 0 });
  const dropZonesRef = useRef<DropZoneLayout[]>([]);
  const dragPointRef = useRef({ x: 0, y: 0 });
  const resizingTaskRef = useRef<{ taskId: string; startHeight: number; startDuration: number } | null>(null);
  const resizeDurationRef = useRef<Record<string, number>>({});
  const pendingTaskPressRef = useRef<{
    taskId: string | null;
    startX: number;
    startY: number;
    longPressed: boolean;
    timer: ReturnType<typeof setTimeout> | null;
  }>({
    taskId: null,
    startX: 0,
    startY: 0,
    longPressed: false,
    timer: null,
  });
  const suppressTaskPressRef = useRef(false);

  const measureContainer = useCallback(() => {
    (containerRef.current as any)?.measureInWindow?.((x: number, y: number) => {
      containerOffsetRef.current = { x, y };
    });
  }, []);

  const registerDropZone = useCallback((key: string, ref: View | null) => {
    if (!ref) return;
    ref.measureInWindow((x, y, width, height) => {
      if (width <= 0) return;
      const existing = dropZonesRef.current.findIndex((z) => z.key === key);
      const zone: DropZoneLayout = { key, x, y, width, height };
      if (existing >= 0) dropZonesRef.current[existing] = zone;
      else dropZonesRef.current.push(zone);
    });
  }, []);

  const measureAllDropZones = useCallback(() => {
    // Re-measure after a small delay to allow layout
    requestAnimationFrame(() => {
      dropZonesRef.current.forEach((zone) => {
        // zones already measured during render via ref callback
      });
    });
  }, []);

  const findHoveredZone = useCallback((pageX: number, pageY: number): string | null => {
    for (const zone of dropZonesRef.current) {
      if (
        pageX >= zone.x && pageX <= zone.x + zone.width &&
        pageY >= zone.y && pageY <= zone.y + zone.height
      ) {
        return zone.key;
      }
    }
    return null;
  }, []);

  const clearPendingTaskPress = useCallback(() => {
    const pending = pendingTaskPressRef.current;
    if (pending.timer) clearTimeout(pending.timer);
    pendingTaskPressRef.current = {
      taskId: null,
      startX: 0,
      startY: 0,
      longPressed: false,
      timer: null,
    };
  }, []);

  const beginDrag = useCallback((task: TaskRecord, pageX: number, pageY: number) => {
    dropZonesRef.current = [];
    measureContainer();
    measureAllDropZones();
    setDraggingTask(task);
    setHoveredDropKey(null);
    const co = containerOffsetRef.current;
    dragTranslate.setValue({
      x: pageX - DRAG_DOT_SIZE / 2 - co.x,
      y: pageY - DRAG_DOT_SIZE / 2 - DRAG_DOT_FINGER_OFFSET_Y - co.y,
    });
    dragOpacity.setValue(0);
    dragScale.setValue(0.9);
    Animated.parallel([
      Animated.spring(dragScale, { toValue: 1, useNativeDriver: true, speed: 20, bounciness: 6 }),
      Animated.timing(dragOpacity, { toValue: 1, duration: 140, useNativeDriver: true }),
    ]).start();
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }, [dragOpacity, dragScale, dragTranslate, measureAllDropZones, measureContainer]);

  const updateDrag = useCallback((pageX: number, pageY: number) => {
    const co = containerOffsetRef.current;
    dragTranslate.setValue({
      x: pageX - DRAG_DOT_SIZE / 2 - co.x,
      y: pageY - DRAG_DOT_SIZE / 2 - DRAG_DOT_FINGER_OFFSET_Y - co.y,
    });
    const hoverPoint = resolveDragDotHoverPoint(pageX, pageY);
    dragPointRef.current = hoverPoint;
    const hovered = findHoveredZone(hoverPoint.x, hoverPoint.y);
    if (hovered !== hoveredDropKey) {
      setHoveredDropKey(hovered);
      if (hovered) void Haptics.selectionAsync();
    }
  }, [dragTranslate, findHoveredZone, hoveredDropKey]);

  const endDrag = useCallback(async () => {
    const task = draggingTask;
    const targetKey = hoveredDropKey;

    const cleanup = () => {
      setDraggingTask(null);
      setHoveredDropKey(null);
    };

    if (!task || !targetKey) {
      Animated.parallel([
        Animated.timing(dragOpacity, { toValue: 0, duration: 120, useNativeDriver: true }),
        Animated.timing(dragScale, { toValue: 0.8, duration: 120, useNativeDriver: true }),
      ]).start(cleanup);
      return;
    }

    // Determine new dueDate based on target key
    let newDueDate: string;
    if (targetKey.startsWith("hour:")) {
      // Day view: drop on hour slot → keep same date, change time
      const hour = parseInt(targetKey.slice(5), 10);
      if (!isValidTimelineHour(hour)) {
        cleanup();
        void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        Alert.alert("改期失败", "无效的时间槽，请选择 00:00 到 23:00 之间的时间。");
        return;
      }
      const timeStr = `${String(hour).padStart(2, "0")}:00`;
      newDueDate = `${selectedDateKey}T${timeStr}`;
    } else {
      // Date key: keep existing time if any
      const schedule = getTaskScheduleDateTime(task);
      const existingTime = schedule ? `T${schedule.timeLabel}` : "";
      newDueDate = targetKey + existingTime;
      const [y, m, d] = targetKey.split("-").map(Number);
      setSelectedDate(new Date(y, m - 1, d));
      setYear(y);
      setMonth(m - 1);
    }

    cleanup();
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    try {
      const nextTask = await updateCalendarTaskSchedule(task.id, { dueDate: newDueDate });
      setSelectedTask((current) => (current?.id === nextTask.id ? nextTask : current));
    } catch {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert("改期失败", "请检查网络或同步状态后重试。");
      void refresh();
    }
    Animated.parallel([
      Animated.timing(dragOpacity, { toValue: 0, duration: 150, useNativeDriver: true }),
      Animated.timing(dragScale, { toValue: 0.85, duration: 150, useNativeDriver: true }),
    ]).start();
  }, [draggingTask, hoveredDropKey, selectedDateKey, dragOpacity, dragScale, refresh]);

  const dragResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !!draggingTask,
        onStartShouldSetPanResponderCapture: () => !!draggingTask,
        onMoveShouldSetPanResponder: () => !!draggingTask,
        onMoveShouldSetPanResponderCapture: () => !!draggingTask,
        onPanResponderMove: (event) => {
          if (!draggingTask) return;
          const { pageX, pageY } = event.nativeEvent;
          updateDrag(pageX, pageY);
        },
        onPanResponderRelease: () => {
          if (!draggingTask) return;
          void endDrag();
        },
        onPanResponderTerminate: () => {
          if (!draggingTask) return;
          void endDrag();
        },
      }),
    [draggingTask, endDrag, updateDrag],
  );

  const handleTaskTouchStart = useCallback((task: TaskRecord, event: GestureResponderEvent) => {
    if (draggingTask) return;
    clearPendingTaskPress();
    const { pageX, pageY } = event.nativeEvent;
    const timer = setTimeout(() => {
      pendingTaskPressRef.current.longPressed = true;
      suppressTaskPressRef.current = true;
      beginDrag(task, pageX, pageY);
    }, DRAG_LONG_PRESS_MS);
    pendingTaskPressRef.current = {
      taskId: task.id,
      startX: pageX,
      startY: pageY,
      longPressed: false,
      timer,
    };
  }, [beginDrag, clearPendingTaskPress, draggingTask]);

  const handleTaskTouchMove = useCallback((event: GestureResponderEvent) => {
    const pending = pendingTaskPressRef.current;
    if (!pending.taskId) return;
    const { pageX, pageY } = event.nativeEvent;
    if (!pending.longPressed) {
      // Cancel long-press if finger moves too far before timer fires
      if (
        Math.abs(pageX - pending.startX) > DRAG_CANCEL_DISTANCE ||
        Math.abs(pageY - pending.startY) > DRAG_CANCEL_DISTANCE
      ) {
        clearPendingTaskPress();
      }
      return;
    }
    // Once dragging, root onTouchMove handles updates — no need to duplicate
  }, [clearPendingTaskPress]);

  const handleTaskTouchEnd = useCallback(() => {
    const pending = pendingTaskPressRef.current;
    clearPendingTaskPress();
    // Once dragging, root onTouchEnd handles endDrag — no need to duplicate
  }, [clearPendingTaskPress]);

  // ─── Android back ────────────────────────────

  useAndroidBackToTasks(
    useCallback(() => {
      if (draggingTask) { setDraggingTask(null); setHoveredDropKey(null); return true; }
      if (eventLineDrawerId) { setEventLineDrawerId(null); return true; }
      if (workspaceClientId) { setWorkspaceClientId(null); return true; }
      if (reviewTaskContext) { setReviewTaskContext(null); return true; }
      if (recordTaskContext) { setRecordTaskContext(null); return true; }
      if (showCreate) { setShowCreate(false); return true; }
      if (showSmartInput) { setShowSmartInput(false); return true; }
      if (selectedTask) { setSelectedTask(null); return true; }
      if (showViewMenu) { setShowViewMenu(false); return true; }
      return false;
    }, [draggingTask, eventLineDrawerId, recordTaskContext, reviewTaskContext, selectedTask, showCreate, showSmartInput, showViewMenu, workspaceClientId]),
  );

  // ─── Data loading ────────────────────────────

  const loadTasks = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  useEffect(() => {
    setCurrentFocusWeek(getLocalWeekAnchorDateKey(selectedDate));
  }, [selectedDate, setCurrentFocusWeek]);

  // Update current time line every minute
  useEffect(() => {
    if (viewMode !== "day") return;
    const timer = setInterval(() => setCurrentTimeOffset(getCurrentTimeOffset()), 60000);
    return () => clearInterval(timer);
  }, [viewMode]);

  // Auto-scroll timeline to current time
  useEffect(() => {
    if (viewMode !== "day") return;
    const offset = getCurrentTimeOffset() - 200;
    requestAnimationFrame(() => {
      timelineRef.current?.scrollTo({ y: Math.max(0, offset), animated: false });
    });
  }, [viewMode, selectedDateKey]);

  // ─── Task grouping ──────────────────────────
  // FocusBar 已下线 —— 默认就是"全部客户"视图，不再按 focus 过滤
  const effectiveTasks = tasks;
  const focusMatchedTaskIds = useMemo<ReadonlySet<string>>(() => new Set(), []);
  const tasksByDate = useMemo(() => groupTasksByDate(effectiveTasks), [effectiveTasks]);

  const dayScheduledTasks = useMemo(() => {
    return getScheduledTasksForDate(tasksByDate, selectedDateKey);
  }, [tasksByDate, selectedDateKey]);

  const dayAllDayTasks = useMemo(() => {
    return getAllDayTasksForDate(tasksByDate, selectedDateKey);
  }, [tasksByDate, selectedDateKey]);

  const selectedTasks = useMemo(
    () => getTasksForDate(tasksByDate, selectedDateKey),
    [tasksByDate, selectedDateKey],
  );

  const weekDates = useMemo(() => getWeekDates(selectedDate), [selectedDate]);
  const weekSignal = useMemo(
    () => buildWeekSignalSnapshot({
      tasks: effectiveTasks,
      weekAnchorDate: getLocalWeekAnchorDateKey(selectedDate),
      workspaceLite: clientIntel.snapshot,
      eventLine: eventLines.find((item) => item.id === focus.eventLineId) ?? null,
      allowJudgmentOverlay: false,
    }),
    [clientIntel.snapshot, effectiveTasks, eventLines, focus.eventLineId, selectedDate],
  );
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

  // ─── Calendar grid (month view) ─────────────

  const calendarDays = useMemo((): readonly CalendarDay[] => buildMonthCalendarDays(year, month), [year, month]);

  const todayKey = toDateKey(now);

  // ─── Navigation ─────────────────────────────

  const goToPrevMonth = useCallback(() => {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  }, [month]);

  const goToNextMonth = useCallback(() => {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  }, [month]);

  // 左右滑翻月：仅作用于月格区、仅认明显横滑、拖拽任务时不触发（避开拖拽手势）
  const monthSwipeResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_evt, g) =>
          !draggingTask && Math.abs(g.dx) > 24 && Math.abs(g.dx) > Math.abs(g.dy) * 1.8,
        onPanResponderRelease: (_evt, g) => {
          if (g.dx > 48) goToPrevMonth();
          else if (g.dx < -48) goToNextMonth();
        },
      }),
    [draggingTask, goToPrevMonth, goToNextMonth],
  );

  const goToPrevWeek = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() - 7);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToNextWeek = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() + 7);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToPrevDay = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() - 1);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToNextDay = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() + 1);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const selectDate = useCallback((dateKey: string, switchView?: CalendarView) => {
    const [y, m, d] = dateKey.split("-").map(Number);
    setSelectedDate(new Date(y, m - 1, d));
    setYear(y);
    setMonth(m - 1);
    if (switchView) setViewMode(switchView);
  }, []);

  // ─── Timeline interactions ──────────────────

  const handleTimelineSlotPress = useCallback((_hour: number) => {
    // 单击空白时间槽不再直接弹「新建任务」——这是日历日视图最高频的误触来源。
    // 仍可通过：长按该时间槽 → 智能输入，或右下角「+」浮钮新建任务（再选时间）。
  }, []);

  const handleTimelineSlotLongPress = useCallback((hour: number) => {
    if (draggingTask) return;
    if (!isValidTimelineHour(hour)) return;
    setSmartInputPreset({ dueDate: selectedDateKey, dueTime: `${String(hour).padStart(2, "0")}:00` });
    setShowSmartInput(true);
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }, [selectedDateKey, draggingTask]);

  const applySmartDraft = useCallback((draft: SmartTaskDraft) => {
    const mergedDraft: SmartTaskDraft = {
      ...draft,
      dueDate: draft.dueDate ?? smartInputPreset.dueDate ?? null,
      dueTime: draft.dueTime ?? smartInputPreset.dueTime ?? null,
    };
    setShowSmartInput(false);
    setSmartInputPreset({});
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
        ? nextTask ?? localDb.getTaskById(taskId) ?? { ...current, ...updates }
        : current
    ));
    void refresh();
    return nextTask;
  }, [refresh]);

  const dayScheduledTasksForView = useMemo(
    () => dayScheduledTasks.map((task) => (
      resizeDrafts[task.id] == null ? task : { ...task, durationMinutes: resizeDrafts[task.id] }
    )),
    [dayScheduledTasks, resizeDrafts],
  );

  const handleTaskPress = useCallback((task: TaskRecord) => {
    if (suppressTaskPressRef.current) {
      suppressTaskPressRef.current = false;
      return;
    }
    clearPendingTaskPress();
    if (!draggingTask) {
      setCurrentFocusBrowseFromCalendar(task);
      setSelectedTask(task);
    }
  }, [clearPendingTaskPress, draggingTask, setCurrentFocusBrowseFromCalendar]);

  const shouldSetTaskResponder = useCallback((task: TaskRecord) => {
    return Boolean(draggingTask) || pendingTaskPressRef.current.taskId === task.id;
  }, [draggingTask]);

  const handleResizeGrant = useCallback((task: TaskRecord, height: number) => {
    resizingTaskRef.current = {
      taskId: task.id,
      startHeight: height,
      startDuration: task.durationMinutes || 60,
    };
    resizeDurationRef.current[task.id] = task.durationMinutes || 60;
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, []);

  const handleResizeMove = useCallback((pageY: number, top: number) => {
    const meta = resizingTaskRef.current;
    if (!meta) return;
    const deltaY = pageY - (top + meta.startHeight + containerOffsetRef.current.y);
    const newDuration = Math.max(30, Math.round((meta.startDuration + (deltaY / HOUR_HEIGHT) * 60) / 15) * 15);
    resizeDurationRef.current[meta.taskId] = newDuration;
    setResizeDrafts((prev) => (
      prev[meta.taskId] === newDuration ? prev : { ...prev, [meta.taskId]: newDuration }
    ));
  }, []);

  const clearResizeDraft = useCallback((taskId: string) => {
    setResizeDrafts((prev) => {
      if (!(taskId in prev)) return prev;
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
    delete resizeDurationRef.current[taskId];
  }, []);

  const handleResizeRelease = useCallback(() => {
    const meta = resizingTaskRef.current;
    if (meta) {
      const nextDuration = resizeDurationRef.current[meta.taskId] ?? meta.startDuration;
      clearResizeDraft(meta.taskId);
      void resizeCalendarTaskDuration(meta.taskId, nextDuration)
        .then((nextTask) => {
          setSelectedTask((current) => (current?.id === nextTask.id ? nextTask : current));
          void refresh();
        })
        .catch(() => {
          Alert.alert("调整时长失败", "请检查网络或同步状态后重试。");
          void refresh();
        });
    }
    resizingTaskRef.current = null;
  }, [clearResizeDraft, refresh]);

  const handleResizeTerminate = useCallback(() => {
    const meta = resizingTaskRef.current;
    if (meta) {
      clearResizeDraft(meta.taskId);
    }
    resizingTaskRef.current = null;
  }, [clearResizeDraft]);

  // ─── Header ─────────────────────────────────

  const headerTitle = useMemo(() => {
    if (viewMode === "month") return `${year}年${month + 1}月`;
    if (viewMode === "week") {
      const start = weekDates[0];
      const end = weekDates[6];
      if (start.getMonth() === end.getMonth()) {
        return `${start.getFullYear()}年${start.getMonth() + 1}月`;
      }
      return `${start.getMonth() + 1}月 – ${end.getMonth() + 1}月`;
    }
    const weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][selectedDate.getDay()];
    return `${selectedDate.getMonth() + 1}月${selectedDate.getDate()}日 · ${weekday}`;
  }, [viewMode, year, month, selectedDate, weekDates]);

  const viewLabel = VIEW_OPTIONS.find((v) => v.key === viewMode)?.label ?? "月";

  const goToPrev = viewMode === "month" ? goToPrevMonth : viewMode === "week" ? goToPrevWeek : goToPrevDay;
  const goToNext = viewMode === "month" ? goToNextMonth : viewMode === "week" ? goToNextWeek : goToNextDay;

  // ─── Render ──────────────────────────────────

  if (!isHydrated) {
    return (
      <SafeAreaView style={[sty.centered, { paddingTop: chrome.screenTopPadding }]} edges={["left", "right"]}>
        <ActivityIndicator size="large" color={colors.brand} />
        <Text style={sty.loadingText}>加载中...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView
      ref={containerRef as any}
      style={sty.container}
      edges={["left", "right"]}
      onLayout={measureContainer}
      onTouchMove={(e) => {
        if (!draggingTask) return;
        const { pageX, pageY } = e.nativeEvent;
        updateDrag(pageX, pageY);
      }}
      onTouchEnd={() => {
        if (!draggingTask) return;
        void endDrag();
      }}
      onTouchCancel={() => {
        if (!draggingTask) return;
        void endDrag();
      }}
    >
      <CalendarHeader
        styles={sty}
        headerTitle={headerTitle}
        viewLabel={viewLabel}
        topPadding={chrome.headerTopPadding}
        onPrev={goToPrev}
        onNext={goToNext}
        onOpenViewMenu={() => setShowViewMenu(true)}
      />
      {/* 周信号卡已按产品要求移除 */}

      {viewMode === "month" ? (
        <MonthView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          calendarDays={calendarDays}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          selectedTasks={selectedTasks}
          highlightedTaskIds={focusMatchedTaskIds}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + spacing.lg}
          registerDropZone={registerDropZone}
          onSelectDate={(dateKey) => selectDate(dateKey)}
          onRefresh={() => { void loadTasks(); }}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onTaskTouchMove={handleTaskTouchMove}
          onTaskTouchEnd={handleTaskTouchEnd}
          shouldSetTaskResponder={shouldSetTaskResponder}
          gridPanHandlers={monthSwipeResponder.panHandlers}
        />
      ) : null}

      {viewMode === "day" ? (
        <DayView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          weekDates={weekDates}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          dayAllDayTasks={dayAllDayTasks}
          dayScheduledTasks={dayScheduledTasksForView}
          highlightedTaskIds={focusMatchedTaskIds}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + 40}
          currentTimeOffset={currentTimeOffset}
          timelineRef={timelineRef}
          registerDropZone={registerDropZone}
          onRefresh={() => { void loadTasks(); }}
          onSelectDate={(dateKey) => selectDate(dateKey)}
          onTimelineSlotPress={handleTimelineSlotPress}
          onTimelineSlotLongPress={handleTimelineSlotLongPress}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onTaskTouchMove={handleTaskTouchMove}
          onTaskTouchEnd={handleTaskTouchEnd}
          shouldSetTaskResponder={shouldSetTaskResponder}
          onResizeGrant={handleResizeGrant}
          onResizeMove={handleResizeMove}
          onResizeRelease={handleResizeRelease}
          onResizeTerminate={handleResizeTerminate}
        />
      ) : null}

      {viewMode === "week" ? (
        <WeekView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          weekdayNames={WEEKDAY_CN}
          calendarDays={calendarDays}
          weekDates={weekDates}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          expandedWeekDay={expandedWeekDay}
          highlightedTaskIds={focusMatchedTaskIds}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + spacing.lg}
          registerDropZone={registerDropZone}
          onRefresh={() => { void loadTasks(); }}
          onSelectDate={(dateKey, switchView) => selectDate(dateKey, switchView)}
          onSetExpandedWeekDay={setExpandedWeekDay}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onTaskTouchMove={handleTaskTouchMove}
          onTaskTouchEnd={handleTaskTouchEnd}
          shouldSetTaskResponder={shouldSetTaskResponder}
        />
      ) : null}

      <CalendarDragLayer
        styles={sty}
        draggingTask={draggingTask}
        dragOpacity={dragOpacity}
        dragScale={dragScale}
        dragTranslate={dragTranslate}
      />

      {/* ─── View switcher modal ─── */}
      <Modal visible={showViewMenu} transparent animationType="fade" onRequestClose={() => setShowViewMenu(false)}>
        <TouchableOpacity
          style={[sty.menuOverlay, { paddingTop: chrome.floatingMenuTopInset }]}
          activeOpacity={1}
          onPress={() => setShowViewMenu(false)}
        >
          <View style={sty.menuCard}>
            {VIEW_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.key}
                style={[sty.menuItem, viewMode === opt.key && sty.menuItemActive]}
                onPress={() => { setViewMode(opt.key); setShowViewMenu(false); }}
              >
                <Text style={[sty.menuItemText, viewMode === opt.key && sty.menuItemTextActive]}>
                  {opt.label}视图
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>

      <CalendarModalCoordinator
        selectedTask={selectedTask}
        selectedTaskEventLine={selectedTaskEventLine}
        recordTaskContext={recordTaskContext}
        reviewTaskContext={reviewTaskContext}
        showCreate={showCreate}
        showSmartInput={showSmartInput}
        smartDraft={smartDraft}
        createPreset={createPreset}
        smartInputPreset={smartInputPreset}
        selectedDateKey={selectedDateKey}
        onCloseSelectedTask={() => setSelectedTask(null)}
        onStartReview={(task) => {
          setReviewTaskContext(task);
          setSelectedTask(null);
        }}
        onRecordFromTaskDetail={() => {
          if (!selectedTask) return;
          setRecordTaskContext(selectedTask);
          setSelectedTask(null);
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
          setCurrentFocusBrowseFromCalendar(task);
          setSelectedTask(null);
          router.push("/(tabs)/consult");
        }}
        onUploadedRecord={(task) => {
          setRecordTaskContext(null);
          setSelectedTask(task);
          void refresh();
        }}
        onCloseRecord={() => setRecordTaskContext(null)}
        onCloseReview={() => setReviewTaskContext(null)}
        onSavedReview={() => {
          setReviewTaskContext(null);
          void refresh();
        }}
        onCloseCreate={() => {
          setShowCreate(false);
          setSmartDraft(null);
          setCreatePreset({});
        }}
        onCreated={() => {
          setShowCreate(false);
          setSmartDraft(null);
          setCreatePreset({});
          void refresh();
        }}
        onCloseSmartInput={() => {
          setShowSmartInput(false);
          setSmartInputPreset({});
        }}
        onApplySmartDraft={applySmartDraft}
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

// ─── Styles ─────────────────────────────────────

const CELL_SIZE = 44;

const sty = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  loadingText: { marginTop: spacing.md, color: palette.textTertiary, fontSize: fontSize.md },
  errorText: { color: palette.cinnabar, fontSize: fontSize.md },

  // 焦点匹配高亮：浓墨 4% 底 + 1px 黛蓝描边 + 左侧 3px 黛蓝竖条
  focusMatchedCard: {
    borderColor: palette.inkBlue,
    borderLeftWidth: 3,
    backgroundColor: "rgba(31,42,55,0.04)",
  },
  focusChip: {
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    backgroundColor: "rgba(61,79,102,0.08)",
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  focusChipText: {
    ...typography.label,
    color: palette.inkBlue,
  },
  // ─── Header（页面背景一致，无白底） ───
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: palette.paperRice,
  },
  headerNav: { flexDirection: "row", alignItems: "center", flex: 1 },
  headerTitle: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
    marginHorizontal: spacing.md,
  },
  navButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  viewSwitcher: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: borderRadius.full,
    backgroundColor: "rgba(31,42,55,0.06)",
  },
  viewSwitcherText: {
    ...typography.label,
    color: palette.inkBlack,
    fontWeight: "600",
  },

  // ─── Month View ───
  weekRow: {
    flexDirection: "row",
    backgroundColor: palette.paperRice,
    paddingBottom: spacing.sm,
    paddingHorizontal: spacing.sm,
  },
  weekCell: { flex: 1, alignItems: "center" },
  weekLabel: {
    ...typography.label,
    color: palette.textTertiary,
  },

  calendarGrid: {
    backgroundColor: palette.paperRice,
    paddingHorizontal: spacing.sm,
    paddingBottom: spacing.md,
  },
  weekGridRow: {
    flexDirection: "row",
  },
  dayCell: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 2,
  },
  dayCircle: {
    width: CELL_SIZE,
    height: CELL_SIZE,
    borderRadius: CELL_SIZE / 2,
    alignItems: "center",
    justifyContent: "center",
  },
  // 选中：浓墨实心
  dayCircleSelected: { backgroundColor: palette.inkBlack },
  // 今天但未选中：浓墨空心圈
  dayCircleToday: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: palette.inkBlack,
  },
  // 拖拽 hover：朱砂提示（投放区语义）
  dayCircleDragHover: {
    backgroundColor: palette.cinnabarTint,
    borderWidth: 2,
    borderColor: palette.cinnabar,
  },
  dayText: { fontSize: fontSize.md, color: palette.inkBlack },
  dayTextOther: { color: palette.textTertiary },
  dayTextSelected: { color: palette.paperRice, fontWeight: "700" },
  dayTextToday: { color: palette.inkBlack, fontWeight: "700" },
  dayTextDragHover: { color: palette.cinnabar, fontWeight: "700" },
  taskDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: palette.inkBronze, // 古铜色任务点
    marginTop: 2,
  },
  taskDotSelected: { backgroundColor: palette.paperRice },

  taskSection: { flex: 1, backgroundColor: colors.background },
  taskSectionContent: { padding: spacing.lg, paddingBottom: 100 },
  sectionTitle: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
    marginBottom: spacing.md,
  },

  // 任务卡 —— 烟灰白 + hairline border + 无 shadow
  taskCard: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  taskCardDragging: {
    opacity: 0.3,
    borderWidth: 1,
    borderColor: palette.inkBlack,
    borderStyle: "dashed",
  },
  taskRow: { flexDirection: "row", alignItems: "center" },
  taskCheckCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: palette.inkBlue,
    marginRight: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  taskCheckCircleDone: {
    backgroundColor: palette.bambooGreen,
    borderColor: palette.bambooGreen,
  },
  taskContent: { flex: 1 },
  taskTitle: { ...typography.bodyLarge, color: palette.inkBlack, fontWeight: "500" },
  taskTime: { ...typography.caption, color: palette.textTertiary, marginTop: 2 },
  emptyState: { alignItems: "center", justifyContent: "center", paddingVertical: 60 },
  emptyText: { fontSize: fontSize.md, color: palette.textTertiary, marginTop: spacing.md },
  dragHint: {
    ...typography.label,
    color: palette.textTertiary,
    textAlign: "center",
    marginTop: 8,
  },

  // ─── Day View ───
  weekStrip: {
    flexDirection: "row",
    backgroundColor: palette.paperRice,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: palette.borderSubtle,
  },
  weekStripDay: { flex: 1, alignItems: "center", paddingVertical: 4 },
  weekStripLabel: {
    ...typography.label,
    color: palette.textTertiary,
    marginBottom: 4,
  },
  weekStripLabelWeekend: { color: palette.textTertiary, opacity: 0.7 },
  weekStripCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  weekStripCircleSelected: { backgroundColor: palette.inkBlack },
  weekStripCircleToday: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: palette.inkBlack,
  },
  weekStripCircleDragHover: {
    backgroundColor: palette.cinnabarTint,
    borderWidth: 2,
    borderColor: palette.cinnabar,
  },
  weekStripDate: { fontSize: 16, fontWeight: "600", color: palette.inkBlack },
  weekStripDateSelected: { color: palette.paperRice },
  weekStripDateToday: { color: palette.inkBlack },
  weekStripDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.inkBronze,
    marginTop: 3,
  },

  timeline: { flex: 1, backgroundColor: colors.background },
  timelineContent: {
    position: "relative" as const,
    minHeight: (TIMELINE_END - TIMELINE_START + 1) * HOUR_HEIGHT,
  },
  allDaySection: {
    flexDirection: "row" as const,
    alignItems: "flex-start" as const,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: palette.borderSubtle,
    backgroundColor: palette.paperMoon, // 月白偏黄区分"全天"区
  },
  allDayLabel: {
    width: 40,
    ...typography.label,
    color: palette.textTertiary,
    paddingTop: 6,
  },
  allDayList: { flex: 1, gap: 4 },
  // 全天任务条：paperMoon 底 + 古铜左边条
  allDayTask: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: 8,
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.sm,
    borderLeftWidth: 3,
    borderLeftColor: palette.inkBronze,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  // 完成态：竹青 + 半透明
  allDayTaskDone: {
    backgroundColor: "rgba(92,122,92,0.06)",
    borderLeftColor: palette.bambooGreen,
    opacity: 0.7,
  },
  allDayTaskTitle: {
    flex: 1,
    ...typography.caption,
    color: palette.inkBlack,
  },
  allDayTaskTitleDone: {
    textDecorationLine: "line-through" as const,
    color: palette.textTertiary,
  },
  hourRow: {
    height: HOUR_HEIGHT,
    flexDirection: "row",
    alignItems: "flex-start",
  },
  hourRowDragHover: { backgroundColor: palette.cinnabarTint },
  hourLabel: {
    width: 44,
    ...typography.mono, // 12/400/16 mono
    color: palette.textTertiary,
    textAlign: "right",
    paddingRight: 8,
    marginTop: -7,
  },
  hourLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: palette.borderSubtle,
  },
  hourLineDragHover: { height: 2, backgroundColor: palette.cinnabar },
  hourDropHint: {
    position: "absolute",
    right: 12,
    top: 4,
    ...typography.label,
    color: palette.cinnabar,
  },

  // Timeline task blocks —— 浓墨色板下的时间线任务
  timelineTask: {
    position: "absolute" as const,
    borderRadius: borderRadius.sm,
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderLeftWidth: 3,
    borderLeftColor: palette.inkBronze,
    overflow: "hidden",
  },
  timelineTaskDone: {
    backgroundColor: "rgba(92,122,92,0.06)",
    borderLeftColor: palette.bambooGreen,
    opacity: 0.6,
  },
  timelineTaskHidden: { opacity: 0, height: 0, overflow: "hidden" },
  timelineTaskTouchable: { flex: 1, paddingHorizontal: 10, paddingVertical: 8 },
  timelineTaskHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 3,
  },
  timelineTaskCheck: {
    width: 14,
    height: 14,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: palette.inkBlue,
  },
  timelineTaskCheckDone: {
    backgroundColor: palette.bambooGreen,
    borderColor: palette.bambooGreen,
  },
  timelineTaskTitle: {
    ...typography.caption,
    fontWeight: "600",
    color: palette.inkBlack,
    lineHeight: 18,
  },
  timelineTaskTitleDone: {
    color: palette.textTertiary,
    textDecorationLine: "line-through",
  },
  timelineTaskTime: {
    ...typography.mono,
    color: palette.textTertiary,
  },
  timelineResizeHandle: {
    position: "absolute" as const,
    left: 10,
    right: 10,
    bottom: 0,
    height: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  timelineResizeGrip: {
    width: 32,
    height: 4,
    borderRadius: 2,
    backgroundColor: "rgba(31,42,55,0.18)",
  },

  // Current time indicator —— 朱砂细线（透明度 0.7 减弱干扰）
  currentTimeLine: {
    position: "absolute" as const,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    zIndex: 10,
    opacity: 0.75,
  },
  currentTimeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: palette.cinnabar,
    marginLeft: 38,
  },
  currentTimeBar: {
    flex: 1,
    height: 1,
    backgroundColor: palette.cinnabar,
  },

  // ─── Week View ───
  weekView: { flex: 1, backgroundColor: colors.background },
  weekViewContent: { padding: spacing.md },

  miniCalendar: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  miniCalendarHeader: { flexDirection: "row", marginBottom: 4 },
  miniCalendarWeekday: {
    flex: 1,
    textAlign: "center",
    ...typography.label,
    color: palette.textTertiary,
  },
  miniCalendarGrid: { flexDirection: "row", flexWrap: "wrap" },
  miniCalendarCell: {
    width: `${100 / 7}%` as unknown as number,
    alignItems: "center",
    paddingVertical: 2,
  },
  miniCalendarCellInWeek: { backgroundColor: palette.paperMoon },
  miniCalendarDayCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  miniCalendarDayToday: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: palette.inkBlack,
  },
  miniCalendarDaySelected: { backgroundColor: palette.inkBlack },
  miniCalendarDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.inkBronze,
    marginTop: 2,
  },
  miniCalendarDayText: { fontSize: 12, color: palette.inkBlack },
  miniCalendarDayTextOther: { color: palette.textTertiary },
  miniCalendarDayTextToday: { color: palette.inkBlack, fontWeight: "700" },
  miniCalendarDayTextSelected: { color: palette.paperRice, fontWeight: "700" },

  weekDayGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  weekDayColumn: {
    width: "48.5%" as unknown as number,
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    minHeight: 120,
  },
  weekDayColumnDragHover: {
    borderWidth: 2,
    borderColor: palette.cinnabar,
    backgroundColor: palette.cinnabarTint,
  },
  weekDayHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: spacing.sm,
  },
  weekDayName: { fontSize: 13, fontWeight: "600", color: palette.textSecondary },
  weekDayNameWeekend: { color: palette.textTertiary, opacity: 0.7 },
  weekDayDateCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  weekDayDateCircleToday: { backgroundColor: palette.inkBlack },
  weekDayDate: { fontSize: 14, fontWeight: "600", color: palette.inkBlack },
  weekDayDateToday: { color: palette.paperRice },
  // 休 badge —— 浓墨 6% 底 + secondary 字
  weekDayRestBadge: {
    ...typography.label,
    color: palette.textSecondary,
    backgroundColor: "rgba(31,42,55,0.06)",
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: borderRadius.sm,
    overflow: "hidden",
  },
  // 周视图任务卡
  weekTaskCard: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    paddingHorizontal: 8,
    backgroundColor: palette.paperRice,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.sm,
    marginBottom: 4,
    gap: 6,
  },
  weekTaskCardDragging: {
    opacity: 0.3,
    borderWidth: 1,
    borderColor: palette.inkBlack,
    borderStyle: "dashed",
  },
  weekTaskDot: { width: 6, height: 6, borderRadius: 3 },
  weekTaskTitle: { flex: 1, fontSize: 12, fontWeight: "500", color: palette.inkBlack },
  weekTaskTime: {
    ...typography.mono,
    fontSize: 10,
    lineHeight: 14,
    color: palette.textTertiary,
  },
  weekDayEmpty: { minHeight: 30, justifyContent: "center", alignItems: "center" },
  weekDayDropHint: {
    ...typography.label,
    color: palette.cinnabar,
  },
  weekDayMoreButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingTop: 6,
    paddingBottom: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    marginTop: 4,
  },
  weekDayMore: {
    ...typography.label,
    color: palette.textSecondary,
  },

  // ─── Drag dot overlay ───
  dragLayer: { ...StyleSheet.absoluteFillObject, zIndex: 20 },
  dragDot: {
    position: "absolute",
    left: 0,
    top: 0,
    width: DRAG_DOT_SIZE,
    height: DRAG_DOT_SIZE,
    borderRadius: DRAG_DOT_SIZE / 2,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: palette.inkBlack,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 14,
    elevation: 10,
  },
  dragDotText: { fontSize: 16, fontWeight: "700", color: palette.paperRice },

  // ─── View switcher menu ───
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(31,42,55,0.24)", // 统一 backdrop
    justifyContent: "flex-start",
    alignItems: "flex-end",
    paddingRight: 18,
  },
  menuCard: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12
    paddingVertical: 4,
    minWidth: 120,
  },
  menuItem: { paddingHorizontal: 18, paddingVertical: 11 },
  menuItemActive: { backgroundColor: "rgba(31,42,55,0.06)" },
  menuItemText: {
    ...typography.body,
    color: palette.inkBlack,
  },
  menuItemTextActive: {
    color: palette.inkBlack,
    fontWeight: "600",
  },
}) as Record<string, any>;

export function ErrorBoundary(props: ErrorBoundaryProps) {
  return (
    <RouteErrorFallback
      {...props}
      label="calendar"
      title="日历页暂时打不开"
      hint="刚才这个页面遇到了异常，你的日程数据没有丢失。点下方按钮重试即可。"
    />
  );
}
