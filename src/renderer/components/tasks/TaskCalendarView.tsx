import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Plus,
  Search,
  MoveVertical,
} from 'lucide-react';

import type { Task } from '../../../shared/types';
import { formatMonthTitle } from '../../../shared/calendar';
import { getChinaCalendarMarkers, type ChinaCalendarMarker } from '../../../shared/china-calendar';
import {
  assignTimedTaskLanes,
  buildTaskDayTimedSegment,
  formatTaskMinuteOfDay as formatMinuteOfDay,
  formatTaskTimelineLabel,
  resolveTaskDateTimeRange,
  taskDateForCalendar as resolveTaskCalendarDate,
  taskOverlapsCalendarWindow,
} from '../../lib/taskTimeline';

type CalendarDisplayMode = 'month' | 'week';

type TaskCalendarViewProps = {
  tasks: Task[];
  currentUserId?: string | null;
  calendarDisplayMode: CalendarDisplayMode;
  onSetCalendarDisplayMode: (mode: CalendarDisplayMode) => void;
  calendarDate: Date;
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  onShiftMonth: (delta: number) => void;
  onAlignCalendarDate: (date: Date) => void;
  onGoToToday: () => void;
  onOpenTaskEditor: (task?: Task, dueDate?: string, options?: { durationMinutes?: number }) => void;
  onCalendarNotice?: (kind: 'info' | 'error', message: string) => void;
  onToggleTaskStatus: (taskId: string, nextDone?: boolean) => Promise<void>;
  onRescheduleTask: (
    task: Task,
    dueDate: string,
    options?: { preserveCalendarViewport?: boolean },
  ) => Promise<void>;
  onUpdateTaskDuration: (task: Task, durationMinutes: number) => Promise<void>;
  onApproveTaskReview: (taskId: string) => Promise<void>;
  onReturnTaskReview: (taskId: string) => Promise<void>;
  isTaskOverdue: (task: Task, today?: Date) => boolean;
  showCollaborativeTasks: boolean;
  onToggleCollaborativeTasks: () => void;
};

const sourceTypeLabels: Record<string, string> = {
  manual: '手动',
  meeting: '会议',
  goal: '目标',
  topic_candidate: '资讯',
  knowledge_chunk: '知识片段',
  knowledge_document: '知识文档',
  chat: '聊天',
};

const DAY_TIMELINE_SLOT_MINUTES = 15;
const DAY_TIMELINE_SLOT_HEIGHT = 14;
const DAY_TIMELINE_DEFAULT_DURATION_MINUTES = 60;
const DAY_TIMELINE_DEFAULT_START_MINUTE = 8 * 60;
const DAY_TIMELINE_SCROLL_END_PADDING = DAY_TIMELINE_SLOT_HEIGHT * 12;
const DAY_MINUTES = 24 * 60;
type WeekCreateSelection = {
  dayKey: number;
  dayDate: Date;
  startMinute: number;
  endMinute: number;
};

type TimedWeekTask = {
  task: Task;
  dayIndex: number;
  dayDate: Date;
  startMinute: number;
  endMinute: number;
  durationMinutes: number;
  timeLabel: string;
  lane: number;
  laneCount: number;
  clusterId: number;
};

type WeekTaskDisplayItem =
  | {
      kind: 'task';
      taskItem: TimedWeekTask;
      column: number;
      columnCount: number;
    }
  | {
      kind: 'aggregate';
      key: string;
      clusterItems: TimedWeekTask[];
      summary: string;
    };

function formatDateInputValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function combineDateAndTime(date: Date, minuteOfDay: number) {
  return `${formatDateInputValue(date)}T${formatMinuteOfDay(minuteOfDay)}`;
}

function minuteOfDayFromClientPosition(column: HTMLDivElement, clientY: number) {
  const rect = column.getBoundingClientRect();
  const clampedOffsetY = Math.max(0, Math.min(rect.height - 1, clientY - rect.top));
  const slotCount = (24 * 60) / DAY_TIMELINE_SLOT_MINUTES;
  const slotIndex = Math.max(
    0,
    Math.min(slotCount - 1, Math.floor(clampedOffsetY / DAY_TIMELINE_SLOT_HEIGHT)),
  );
  return slotIndex * DAY_TIMELINE_SLOT_MINUTES;
}

function buildSelectionRange(anchorMinute: number, currentMinute: number): { startMinute: number; endMinute: number } {
  if (currentMinute >= anchorMinute) {
    return {
      startMinute: anchorMinute,
      endMinute: Math.min(currentMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
    };
  }
  return {
    startMinute: currentMinute,
    endMinute: Math.min(anchorMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
  };
}

function isSameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function addDays(baseDate: Date, days: number) {
  return new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate() + days);
}

function startOfDayValue(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfWeek(baseDate: Date) {
  const dayIndex = (baseDate.getDay() + 6) % 7;
  return addDays(baseDate, -dayIndex);
}

function isDateWithinRange(date: Date, startDate: Date, endDate: Date) {
  const time = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  return time >= startDate.getTime() && time <= endDate.getTime();
}

function formatWeekRangeTitle(startDate: Date, endDate: Date) {
  const sameMonth = startDate.getMonth() === endDate.getMonth() && startDate.getFullYear() === endDate.getFullYear();
  if (sameMonth) {
    return `${startDate.getFullYear()}年 ${startDate.getMonth() + 1}月 · ${startDate.getDate()}-${endDate.getDate()}日`;
  }
  return `${startDate.getFullYear()}年 ${startDate.getMonth() + 1}月${startDate.getDate()}日 - ${endDate.getMonth() + 1}月${endDate.getDate()}日`;
}

function sourceLabel(sourceType: string) {
  return sourceTypeLabels[sourceType] || sourceType || '任务';
}

function controlLevelLabel(task: Task) {
  const level = task.orgContext?.controlLevel;
  if (level === 'leader_control') return '负责人控制';
  if (level === 'department_control') return '部门控制';
  if (level === 'organization_control') return '机构控制';
  return '';
}

function taskOrgSummary(task: Task) {
  const parts: string[] = [];
  const control = controlLevelLabel(task);
  if (task.orgContext?.needsReview) parts.push('待复核');
  if (control) parts.push(control);
  if (task.orgContext?.isCrossDepartment) parts.push('跨部门');
  return parts.join(' · ');
}

function isTransportItineraryTask(task: Task) {
  const text = `${task.title || ''}\n${task.desc || ''}`.trim();
  if (!text) return false;
  return /(飞[\u4e00-\u9fff]{1,8}|飞去[\u4e00-\u9fff]{1,8}|飞往[\u4e00-\u9fff]{1,8}|航班|机票|火车去[\u4e00-\u9fff]{1,8}|高铁去[\u4e00-\u9fff]{1,8}|动车去[\u4e00-\u9fff]{1,8}|坐火车去[\u4e00-\u9fff]{1,8}|坐高铁去[\u4e00-\u9fff]{1,8}|乘火车去[\u4e00-\u9fff]{1,8}|乘高铁去[\u4e00-\u9fff]{1,8})/.test(text);
}

function calendarTaskAccentColor(task: Task) {
  if (task.priority === 'high') return '#EF4444';
  if (task.priority === 'low') return '#9CA3AF';
  return '#5B7BFE';
}

function calendarChipStyle(task: Task) {
  const accentColor = calendarTaskAccentColor(task);
  if (task.status === 'done') {
    return {
      color: '#94A3B8',
      backgroundColor: '#F8FAFC',
      borderColor: accentColor,
    };
  }
  return {
    color: accentColor,
    backgroundColor: '#FFFFFF',
    borderColor: accentColor,
  };
}

function calendarMarkerClassName(marker: ChinaCalendarMarker) {
  if (marker.kind === 'festival') return 'bg-rose-50 text-rose-600 border-rose-100';
  if (marker.kind === 'offday') return 'bg-orange-50 text-orange-700 border-orange-100';
  return 'bg-slate-100 text-slate-600 border-slate-200';
}

function sortTasksForCalendar(items: Task[]) {
  const statusRank: Record<Task['status'], number> = {
    inbox: 0,
    doing: 1,
    todo: 2,
    done: 3,
    rejected: 4,
  };
  const priorityRank: Record<Task['priority'], number> = {
    high: 0,
    normal: 1,
    low: 2,
  };
  return [...items].sort((left, right) => {
    const leftRange = resolveTaskDateTimeRange(left);
    const rightRange = resolveTaskDateTimeRange(right);
    if (leftRange.startDateTime.getTime() !== rightRange.startDateTime.getTime()) {
      return leftRange.startDateTime.getTime() - rightRange.startDateTime.getTime();
    }
    if (leftRange.hasExplicitTime !== rightRange.hasExplicitTime) {
      return leftRange.hasExplicitTime ? -1 : 1;
    }
    const leftDone = left.status === 'done';
    const rightDone = right.status === 'done';
    if (leftDone !== rightDone) return leftDone ? 1 : -1;

    const statusDelta = statusRank[left.status] - statusRank[right.status];
    if (statusDelta !== 0) return statusDelta;

    const priorityDelta = priorityRank[left.priority] - priorityRank[right.priority];
    if (priorityDelta !== 0) return priorityDelta;

    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}

function buildWeekTaskDisplayItems(items: TimedWeekTask[]) {
  const clusters = new Map<number, TimedWeekTask[]>();
  items.forEach((item) => {
    const existing = clusters.get(item.clusterId) || [];
    existing.push(item);
    clusters.set(item.clusterId, existing);
  });

  const displayItems: WeekTaskDisplayItem[] = [];
  [...clusters.entries()]
    .sort((left, right) => {
      const leftStart = Math.min(...left[1].map((item) => item.startMinute));
      const rightStart = Math.min(...right[1].map((item) => item.startMinute));
      return leftStart - rightStart;
    })
    .forEach(([clusterId, clusterItems]) => {
      const sortedClusterItems = [...clusterItems].sort((left, right) => {
        if (left.startMinute !== right.startMinute) return left.startMinute - right.startMinute;
        if (left.endMinute !== right.endMinute) return left.endMinute - right.endMinute;
        return left.lane - right.lane;
      });
      if (sortedClusterItems.length <= 1) {
        sortedClusterItems.forEach((taskItem) => {
          displayItems.push({
            kind: 'task',
            taskItem,
            column: 0,
            columnCount: 1,
          });
        });
        return;
      }

      const clusterTitles = sortedClusterItems.map((item) => item.task.title).filter(Boolean);
      displayItems.push({
        kind: 'aggregate',
        key: `aggregate-${clusterId}`,
        clusterItems: sortedClusterItems,
        summary: clusterTitles.slice(0, 4).join('、'),
      });
    });

  return displayItems;
}

export function TaskCalendarView({
  tasks,
  currentUserId: _currentUserId,
  calendarDisplayMode,
  onSetCalendarDisplayMode,
  calendarDate,
  selectedDate,
  onSelectDate,
  onShiftMonth,
  onAlignCalendarDate,
  onGoToToday,
  onOpenTaskEditor,
  onCalendarNotice,
  onToggleTaskStatus,
  onRescheduleTask,
  onUpdateTaskDuration,
  onApproveTaskReview: _onApproveTaskReview,
  onReturnTaskReview: _onReturnTaskReview,
  isTaskOverdue,
  showCollaborativeTasks,
  onToggleCollaborativeTasks,
}: TaskCalendarViewProps) {
  const [isJumpPickerOpen, setIsJumpPickerOpen] = useState(false);
  const [draggingTaskId, setDraggingTaskId] = useState<string | null>(null);
  const [dragTargetDay, setDragTargetDay] = useState<number | null>(null);
  const [dragTargetMinute, setDragTargetMinute] = useState<number | null>(null);
  const [expandedCalendarDays, setExpandedCalendarDays] = useState<Set<string>>(new Set());
  const dragDropHandledRef = useRef(false);
  const [resizingTaskId, setResizingTaskId] = useState<string | null>(null);
  const [resizePreviewMinutes, setResizePreviewMinutes] = useState<number | null>(null);
  const [weekCreateSelection, setWeekCreateSelection] = useState<WeekCreateSelection | null>(null);
  const [weekAggregateIndexes, setWeekAggregateIndexes] = useState<Record<string, number>>({});
  const [visibleWeekPageIndex, setVisibleWeekPageIndex] = useState(1);
  const [isWeekPaging, setIsWeekPaging] = useState(false);
  const resizePreviewRef = useRef<number | null>(null);
  const resizeDraftRef = useRef<{ taskId: string; startY: number; startMinute: number; baseDuration: number } | null>(null);
  const weekCreateDraftRef = useRef<{
    dayKey: number;
    dayDate: Date;
    anchorMinute: number;
    column: HTMLDivElement;
  } | null>(null);
  const weekCreateSelectionRef = useRef<WeekCreateSelection | null>(null);
  const weekCreateCleanupRef = useRef<(() => void) | null>(null);
  const weekTimelineScrollRef = useRef<HTMLDivElement | null>(null);
  const weekPagerRef = useRef<HTMLDivElement | null>(null);
  const weekPagerIdleTimerRef = useRef<number | null>(null);
  const weekPagerVerticalSyncRef = useRef(false);
  const weekPagerGestureDeadlineRef = useRef(0);
  const today = useMemo(() => new Date(), []);
  const taskDateForCalendar = resolveTaskCalendarDate;
  const visibleTasks = useMemo(
    () => tasks.filter((task) => task.status !== 'rejected'),
    [tasks],
  );
  const activeMonthDate = useMemo(() => new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1), [calendarDate]);

  const monthTasksByDateKey = useMemo(() => {
    const mapping = new Map<string, Task[]>();
    visibleTasks.forEach((task) => {
      const range = resolveTaskDateTimeRange(task);
      for (
        let cursor = startOfDayValue(range.startDateTime);
        cursor.getTime() < range.endDateTime.getTime();
        cursor = addDays(cursor, 1)
      ) {
        const date = cursor;
        const key = formatDateInputValue(date);
        const existing = mapping.get(key) || [];
        existing.push(task);
        mapping.set(key, existing);
      }
    });
    mapping.forEach((dayTasks, key) => {
      mapping.set(key, sortTasksForCalendar(dayTasks));
    });
    return mapping;
  }, [visibleTasks]);

  const tasksByDay = useMemo(() => {
    const mapping = new Map<number, Task[]>();
    const daysInMonth = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth() + 1, 0).getDate();
    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth(), day);
      const dayTasks = monthTasksByDateKey.get(formatDateInputValue(date)) || [];
      if (dayTasks.length > 0) mapping.set(day, dayTasks);
    }
    mapping.forEach((dayTasks, day) => {
      mapping.set(day, sortTasksForCalendar(dayTasks));
    });
    return mapping;
  }, [activeMonthDate, monthTasksByDateKey]);

  const monthTasks = useMemo(() => {
    const monthStart = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth(), 1);
    const monthEndExclusive = new Date(activeMonthDate.getFullYear(), activeMonthDate.getMonth() + 1, 1);
    return sortTasksForCalendar(
      visibleTasks.filter((task) => taskOverlapsCalendarWindow(task, monthStart, monthEndExclusive)),
    );
  }, [activeMonthDate, visibleTasks]);

  const monthTimelineWeeks = useMemo(() => {
    const firstRenderedMonth = new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
    const rangeStart = startOfWeek(firstRenderedMonth);
    const lastRenderedDay = new Date(firstRenderedMonth.getFullYear(), firstRenderedMonth.getMonth() + 1, 0);
    const rangeEnd = addDays(lastRenderedDay, 6 - ((lastRenderedDay.getDay() + 6) % 7));
    const weeks: Array<{
      key: string;
      days: Array<{
        date: Date;
        dayTasks: Task[];
      }>;
    }> = [];
    for (let cursor = rangeStart; cursor.getTime() <= rangeEnd.getTime(); cursor = addDays(cursor, 7)) {
      const weekStart = cursor;
      weeks.push({
        key: formatDateInputValue(weekStart),
        days: Array.from({ length: 7 }, (_, index) => {
          const date = addDays(weekStart, index);
          return {
            date,
            dayTasks: monthTasksByDateKey.get(formatDateInputValue(date)) || [],
          };
        }),
      });
    }
    return weeks;
  }, [calendarDate, monthTasksByDateKey]);

  const weekStartDate = useMemo(() => startOfWeek(selectedDate), [selectedDate]);
  const weekPages = useMemo(() => {
    return [-7, 0, 7].map((offsetDays) => {
      const startDate = addDays(weekStartDate, offsetDays);
      const days = Array.from({ length: 7 }, (_, index) => addDays(startDate, index));
      const endDate = days[6];
      const tasks = sortTasksForCalendar(
        visibleTasks.filter((task) => taskOverlapsCalendarWindow(task, startDate, addDays(endDate, 1))),
      );
      const timedTasks = days.flatMap((day, dayIndex) => {
        const items = tasks
          .map((task) => {
            const segment = buildTaskDayTimedSegment(task, day);
            if (!segment) return null;
            return {
              task,
              dayIndex,
              dayDate: day,
              ...segment,
            };
          })
          .filter((item): item is { task: Task; dayIndex: number; dayDate: Date; startMinute: number; endMinute: number; durationMinutes: number; timeLabel: string } => Boolean(item));
        return assignTimedTaskLanes(items) as TimedWeekTask[];
      });
      return {
        key: `${startDate.toISOString()}-${offsetDays}`,
        offsetDays,
        startDate,
        endDate,
        days,
        title: formatWeekRangeTitle(startDate, endDate),
        tasks,
        timedTasks,
      };
    });
  }, [visibleTasks, weekStartDate]);
  const currentWeekPage = weekPages[1];
  const visibleWeekPage = weekPages[visibleWeekPageIndex] ?? currentWeekPage;
  const weekStartKey = weekStartDate.getTime();
  const weekDays = visibleWeekPage.days;
  const weekEndDate = visibleWeekPage.endDate;
  const weekTasks = visibleWeekPage.tasks;
  const weekTimedTasks = visibleWeekPage.timedTasks;
  const weekDisplayItemsByDay = useMemo(() => {
    const mapping = new Map<number, WeekTaskDisplayItem[]>();
    visibleWeekPage.days.forEach((_, dayIndex) => {
      const items = visibleWeekPage.timedTasks.filter((item) => item.dayIndex === dayIndex) as TimedWeekTask[];
      mapping.set(dayIndex, buildWeekTaskDisplayItems(items));
    });
    return mapping;
  }, [visibleWeekPage.days, visibleWeekPage.timedTasks]);
  const draggedTask = useMemo(
    () => (calendarDisplayMode === 'week' ? weekTasks : visibleTasks).find((task) => task.id === draggingTaskId) || null,
    [calendarDisplayMode, draggingTaskId, visibleTasks, weekTasks],
  );

  const draggedDurationMinutes = useMemo(() => {
    if (!draggedTask) return DAY_TIMELINE_DEFAULT_DURATION_MINUTES;
    const timedMatch = weekTimedTasks.find((item) => item.task.id === draggedTask.id);
    if (timedMatch) return timedMatch.durationMinutes;
    return Math.max(DAY_TIMELINE_SLOT_MINUTES, draggedTask.durationMinutes ?? DAY_TIMELINE_DEFAULT_DURATION_MINUTES);
  }, [draggedTask, weekTimedTasks]);

  useEffect(() => {
    if (calendarDisplayMode !== 'week') return;
    const nextScrollTop = Math.max(0, (DAY_TIMELINE_DEFAULT_START_MINUTE / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 12);
    const pager = weekPagerRef.current;
    if (!pager) return;
    pager.querySelectorAll<HTMLElement>('[data-week-scroll="true"]').forEach((node) => {
      node.scrollTop = nextScrollTop;
    });
  }, [calendarDisplayMode, selectedDate]);

  useEffect(() => {
    if (!resizingTaskId || !resizeDraftRef.current) return;

    const handleMouseMove = (event: MouseEvent) => {
      const draft = resizeDraftRef.current;
      if (!draft) return;
      const deltaY = event.clientY - draft.startY;
      const deltaSlots = Math.round(deltaY / DAY_TIMELINE_SLOT_HEIGHT);
      const maxDuration = Math.max(DAY_TIMELINE_SLOT_MINUTES, 24 * 60 - draft.startMinute);
      const nextDuration = Math.max(
        DAY_TIMELINE_SLOT_MINUTES,
        Math.min(maxDuration, draft.baseDuration + deltaSlots * DAY_TIMELINE_SLOT_MINUTES),
      );
      resizePreviewRef.current = nextDuration;
      setResizePreviewMinutes(nextDuration);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    };

    const handleMouseUp = () => {
      const draft = resizeDraftRef.current;
      const task = weekTimedTasks.find((item) => item.task.id === draft?.taskId)?.task;
      const nextDuration = resizePreviewRef.current ?? draft?.baseDuration ?? null;
      resizeDraftRef.current = null;
      resizePreviewRef.current = null;
      setResizingTaskId(null);
      setResizePreviewMinutes(null);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (task && nextDuration && draft && nextDuration !== draft.baseDuration) {
        void onUpdateTaskDuration(task, nextDuration);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [onUpdateTaskDuration, resizingTaskId, weekTimedTasks]);

  const cleanupWeekCreateInteraction = useCallback(() => {
    weekCreateCleanupRef.current?.();
    weekCreateCleanupRef.current = null;
    weekCreateDraftRef.current = null;
    weekCreateSelectionRef.current = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    return () => {
      cleanupWeekCreateInteraction();
    };
  }, [cleanupWeekCreateInteraction]);

  useEffect(() => {
    setWeekAggregateIndexes({});
  }, [selectedDate, visibleWeekPageIndex]);

  const timelineSlotMinutes = useMemo(
    () => Array.from({ length: (24 * 60) / DAY_TIMELINE_SLOT_MINUTES }, (_, index) => index * DAY_TIMELINE_SLOT_MINUTES),
    [],
  );
  const hourLineMinutes = useMemo(
    () => timelineSlotMinutes.filter((minute) => minute % 60 === 0),
    [timelineSlotMinutes],
  );

  const monthStats = useMemo(() => {
    return {
      dayCount: tasksByDay.size,
      total: monthTasks.length,
      open: monthTasks.filter((task) => task.status !== 'done').length,
      done: monthTasks.filter((task) => task.status === 'done').length,
      overdue: monthTasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: monthTasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, monthTasks, tasksByDay.size, today]);

  const weekStats = useMemo(() => {
    return {
      total: weekTasks.length,
      open: weekTasks.filter((task) => task.status !== 'done').length,
      done: weekTasks.filter((task) => task.status === 'done').length,
      overdue: weekTasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: weekTasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, today, weekTasks]);
  const visibleWeekStats = useMemo(() => {
    return {
      total: visibleWeekPage.tasks.length,
      open: visibleWeekPage.tasks.filter((task) => task.status !== 'done').length,
      done: visibleWeekPage.tasks.filter((task) => task.status === 'done').length,
      overdue: visibleWeekPage.tasks.filter((task) => isTaskOverdue(task, today)).length,
      highPriority: visibleWeekPage.tasks.filter((task) => task.status !== 'done' && task.priority === 'high').length,
    };
  }, [isTaskOverdue, today, visibleWeekPage]);

  const handleDateJump = (value: string) => {
    const nextDate = new Date(value);
    if (Number.isNaN(nextDate.getTime())) return;
    onSelectDate(nextDate);
    onAlignCalendarDate(nextDate);
    setIsJumpPickerOpen(false);
  };

  const handleShiftPeriod = (delta: number) => {
    if (calendarDisplayMode === 'week') {
      const nextDate = addDays(selectedDate, delta * 7);
      onSelectDate(nextDate);
      onAlignCalendarDate(nextDate);
      return;
    }
    onShiftMonth(delta);
  };

  const handleDaySelect = (date: Date) => {
    if (calendarDisplayMode === 'week') {
      onSelectDate(date);
      return;
    }
    onSelectDate(date);
    if (date.getFullYear() !== calendarDate.getFullYear() || date.getMonth() !== calendarDate.getMonth()) {
      onAlignCalendarDate(date);
    }
  };

  const handleTaskDrop = async (task: Task, cellDate: Date) => {
    const nextDueDate = formatDateInputValue(cellDate);
    const currentTaskDate = taskDateForCalendar(task);
    if (
      currentTaskDate.getFullYear() === cellDate.getFullYear()
      && currentTaskDate.getMonth() === cellDate.getMonth()
      && currentTaskDate.getDate() === cellDate.getDate()
    ) {
      return;
    }
    await onRescheduleTask(task, nextDueDate);
    onSelectDate(cellDate);
  };

  const handleTimelineTaskDrop = async (task: Task, minuteOfDay: number) => {
    const nextDueDate = combineDateAndTime(selectedDate, minuteOfDay);
    setDragTargetMinute(null);
    setDraggingTaskId(null);
    await onRescheduleTask(task, nextDueDate);
  };

  const handleWeekTimelineTaskDrop = async (task: Task, dayDate: Date, minuteOfDay: number) => {
    const nextDueDate = combineDateAndTime(dayDate, minuteOfDay);
    setDragTargetMinute(null);
    setDragTargetDay(null);
    setDraggingTaskId(null);
    onSelectDate(dayDate);
    await onRescheduleTask(task, nextDueDate, { preserveCalendarViewport: true });
  };

  const resolveDraggedTaskId = (event: React.DragEvent) => {
    const transferTaskId = event.dataTransfer.getData('text/plain').trim();
    return transferTaskId || draggingTaskId || null;
  };

  const handleStartWeekTaskResize = (
    taskId: string,
    startMinute: number,
    baseDuration: number,
    event: React.MouseEvent,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    resizeDraftRef.current = {
      taskId,
      startY: event.clientY,
      startMinute,
      baseDuration,
    };
    resizePreviewRef.current = baseDuration;
    setResizingTaskId(taskId);
    setResizePreviewMinutes(baseDuration);
  };

  const handleStartWeekCreateSelection = (
    day: Date,
    column: HTMLDivElement,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    if (draggingTaskId || resizingTaskId) return;
    event.preventDefault();
    event.stopPropagation();
    const anchorMinute = minuteOfDayFromClientPosition(column, event.clientY);
    const dayKey = day.getTime();
    cleanupWeekCreateInteraction();
    const initialSelection = {
      dayKey,
      dayDate: day,
      startMinute: anchorMinute,
      endMinute: Math.min(anchorMinute + DAY_TIMELINE_SLOT_MINUTES, 24 * 60),
    };
    weekCreateDraftRef.current = {
      dayKey,
      dayDate: day,
      anchorMinute,
      column,
    };
    weekCreateSelectionRef.current = initialSelection;
    setWeekCreateSelection(initialSelection);
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';

    const updateSelectionFromPointer = (clientY: number) => {
      const draft = weekCreateDraftRef.current;
      if (!draft) return;
      const currentMinute = minuteOfDayFromClientPosition(draft.column, clientY);
      const nextRange = buildSelectionRange(draft.anchorMinute, currentMinute);
      const nextSelection = {
        dayKey: draft.dayKey,
        dayDate: draft.dayDate,
        startMinute: nextRange.startMinute,
        endMinute: nextRange.endMinute,
      };
      weekCreateSelectionRef.current = nextSelection;
      setWeekCreateSelection(nextSelection);
    };

    const handleWindowMouseMove = (moveEvent: MouseEvent) => {
      updateSelectionFromPointer(moveEvent.clientY);
    };

    const handleWindowMouseUp = () => {
      const draft = weekCreateDraftRef.current;
      const selection = weekCreateSelectionRef.current;
      cleanupWeekCreateInteraction();
      setWeekCreateSelection(null);
      if (!draft || !selection) return;
      const durationMinutes = Math.max(DAY_TIMELINE_SLOT_MINUTES, selection.endMinute - selection.startMinute);
      const dueDate = combineDateAndTime(draft.dayDate, selection.startMinute);
      window.requestAnimationFrame(() => {
        onSelectDate(draft.dayDate);
        onOpenTaskEditor(undefined, dueDate, { durationMinutes });
      });
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);
    weekCreateCleanupRef.current = () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
    };
  };

  const handleGoToToday = () => {
    onGoToToday();
  };

  const handleCreateTaskFromWeekSlot = useCallback(
    (day: Date, startMinute: number) => {
      if (draggingTaskId || resizingTaskId) return;
      const durationMinutes = DAY_TIMELINE_DEFAULT_DURATION_MINUTES;
      const endMinute = Math.min(startMinute + durationMinutes, DAY_MINUTES);
      const hasOverlap = visibleWeekPage.timedTasks.some(
        (item) =>
          item.dayDate.getTime() === day.getTime()
          && item.startMinute < endMinute
          && item.endMinute > startMinute,
      );
      if (hasOverlap) {
        onCalendarNotice?.('info', '这个时间段已经有任务了，请点空闲时间再新建，或先调整现有任务。');
        return;
      }
      window.requestAnimationFrame(() => {
        onSelectDate(day);
        onOpenTaskEditor(undefined, combineDateAndTime(day, startMinute), { durationMinutes });
      });
    },
    [draggingTaskId, onCalendarNotice, onOpenTaskEditor, onSelectDate, resizingTaskId, visibleWeekPage.timedTasks],
  );

  const centerWeekPager = (behavior: ScrollBehavior = 'auto') => {
    const pager = weekPagerRef.current;
    if (!pager) return;
    const pageWidth = pager.clientWidth;
    if (!pageWidth) return;
    pager.scrollTo({ left: pageWidth, behavior });
  };

  useEffect(() => {
    if (calendarDisplayMode !== 'week') return;
    let frame = 0;
    frame = window.requestAnimationFrame(() => {
      setVisibleWeekPageIndex(1);
      centerWeekPager('auto');
    });
    return () => {
      window.cancelAnimationFrame(frame);
      if (weekPagerIdleTimerRef.current) {
        window.clearTimeout(weekPagerIdleTimerRef.current);
        weekPagerIdleTimerRef.current = null;
      }
    };
  }, [calendarDisplayMode, weekPages, weekStartKey]);

  useEffect(() => {
    if (calendarDisplayMode !== 'week' || isWeekPaging) return;
    if (Date.now() < weekPagerGestureDeadlineRef.current) return;
    const pager = weekPagerRef.current;
    if (!pager || pager.clientWidth <= 0) return;
    const centerOffset = Math.abs(pager.scrollLeft - pager.clientWidth);
    if (centerOffset < 2) return;
    let frame = 0;
    frame = window.requestAnimationFrame(() => {
      setVisibleWeekPageIndex(1);
      centerWeekPager('auto');
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [calendarDisplayMode, isWeekPaging, weekTasks, weekTimedTasks]);

  const handleWeekVerticalScroll = (event: React.UIEvent<HTMLDivElement>) => {
    if (weekPagerVerticalSyncRef.current) return;
    const source = event.currentTarget;
    const pager = weekPagerRef.current;
    if (!pager) return;
    weekPagerVerticalSyncRef.current = true;
    pager.querySelectorAll<HTMLElement>('[data-week-scroll="true"]').forEach((node) => {
      if (node !== source && Math.abs(node.scrollTop - source.scrollTop) > 1) {
        node.scrollTop = source.scrollTop;
      }
    });
    window.requestAnimationFrame(() => {
      weekPagerVerticalSyncRef.current = false;
    });
  };

  const finalizeWeekPagerScroll = () => {
    const pager = weekPagerRef.current;
    if (!pager) return;
    const pageWidth = pager.clientWidth;
    if (!pageWidth) return;
    weekPagerGestureDeadlineRef.current = 0;
    const pageIndex = Math.round(pager.scrollLeft / pageWidth);
    if (pageIndex === 0) {
      onSelectDate(addDays(selectedDate, -7));
      return;
    }
    if (pageIndex === 2) {
      onSelectDate(addDays(selectedDate, 7));
      return;
    }
    centerWeekPager('smooth');
  };

  const handleWeekPagerScroll = () => {
    const pager = weekPagerRef.current;
    if (!pager || pager.clientWidth <= 0) return;
    const now = Date.now();
    const isUserGesture = now < weekPagerGestureDeadlineRef.current;
    const centerOffset = Math.abs(pager.scrollLeft - pager.clientWidth);
    if (!isUserGesture) {
      if (centerOffset < 6) return;
      return;
    }
    weekPagerGestureDeadlineRef.current = now + 180;
    setIsWeekPaging(true);
    const pageIndex = Math.max(0, Math.min(2, Math.round(pager.scrollLeft / pager.clientWidth)));
    setVisibleWeekPageIndex(pageIndex);
    if (weekPagerIdleTimerRef.current) {
      window.clearTimeout(weekPagerIdleTimerRef.current);
    }
    weekPagerIdleTimerRef.current = window.setTimeout(() => {
      setIsWeekPaging(false);
      finalizeWeekPagerScroll();
    }, 120);
  };

  const handleWeekScrollWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const horizontalIntent = Math.abs(event.deltaX);
    const verticalIntent = Math.abs(event.deltaY);
    if (horizontalIntent < 24 || horizontalIntent <= verticalIntent * 1.4) return;
    const pager = weekPagerRef.current;
    if (!pager) return;
    weekPagerGestureDeadlineRef.current = Date.now() + 280;
    pager.scrollLeft += event.deltaX;
    event.preventDefault();
  };

  const handleWeekTaskSelect = (event?: React.MouseEvent) => {
    event?.preventDefault();
    event?.stopPropagation();
  };

  const periodStats = calendarDisplayMode === 'week' ? visibleWeekStats : monthStats;
  const periodTitle = calendarDisplayMode === 'week' ? visibleWeekPage.title : formatMonthTitle(activeMonthDate);

  return (
    <div className="w-full min-w-0 grid grid-cols-1 gap-6 items-start transition-all xl:grid-cols-[minmax(0,1fr)]">
      <div className="min-w-0 w-full bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden">
        <div className="flex flex-col gap-3 px-5 lg:px-6 py-4 border-b border-gray-100">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-2xl border border-gray-200 bg-slate-50 p-1">
                  {(['month', 'week'] as CalendarDisplayMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={`rounded-[12px] px-3 py-1.5 text-[12px] font-bold transition-colors ${calendarDisplayMode === mode ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500 hover:text-gray-800'}`}
                      onClick={() => onSetCalendarDisplayMode(mode)}
                    >
                      {mode === 'month' ? '月' : '周'}
                    </button>
                  ))}
                </div>
                <h2 className={`text-[18px] lg:text-[22px] font-bold text-gray-900 transition-all duration-200 ${isWeekPaging && calendarDisplayMode === 'week' ? 'opacity-90 translate-x-[1px]' : 'opacity-100 translate-x-0'}`}>{periodTitle}</h2>
              </div>
              <div className={`flex flex-wrap gap-1.5 text-[10px] font-semibold transition-opacity duration-200 ${isWeekPaging && calendarDisplayMode === 'week' ? 'opacity-85' : 'opacity-100'}`}>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-slate-600">{calendarDisplayMode === 'week' ? '本周任务' : '本月任务'} {periodStats.total} 条</span>
                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-emerald-600">完成 {periodStats.done}</span>
                <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-amber-700">待推进 {periodStats.open}</span>
                <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-rose-600">逾期 {periodStats.overdue}</span>
                <span className="rounded-full bg-violet-50 px-2.5 py-0.5 text-violet-600">高优先级 {periodStats.highPriority}</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 self-start lg:self-auto">
              <button
                type="button"
                role="switch"
                aria-checked={showCollaborativeTasks}
                aria-label={showCollaborativeTasks ? '隐藏个人任务' : '显示全部任务'}
                onClick={onToggleCollaborativeTasks}
                className="group relative flex items-center overflow-visible"
              >
                <span className="pointer-events-none absolute left-0 top-1/2 -translate-x-[calc(100%+8px)] -translate-y-1/2 text-[11px] font-medium text-gray-400 whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100 group-active:opacity-100">
                  {showCollaborativeTasks ? '隐藏个人任务' : '显示全部任务'}
                </span>
                <span
                  className={`relative inline-flex h-6 w-10 items-center rounded-full transition-colors duration-200 ${
                    showCollaborativeTasks ? 'bg-[#5B7BFE]' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                      showCollaborativeTasks ? 'translate-x-5' : 'translate-x-1'
                    }`}
                  />
                </span>
              </button>
              <div className="relative flex items-center gap-2">
              <button
                type="button"
                className="h-9 w-9 rounded-xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => handleShiftPeriod(-1)}
              >
                <ChevronLeft size={16} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-9 px-3 rounded-xl border border-gray-200 bg-white text-[12px] font-bold text-gray-700 whitespace-nowrap hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={handleGoToToday}
              >
                今天
              </button>
              <button
                type="button"
                aria-label="跳转日期"
                className={`h-9 w-9 rounded-xl border text-[12px] font-bold transition-colors ${
                  isJumpPickerOpen
                    ? 'border-blue-200 bg-blue-50 text-[#5B7BFE]'
                    : 'border-gray-200 bg-white text-gray-700 hover:text-[#5B7BFE] hover:border-blue-100'
                }`}
                onClick={() => setIsJumpPickerOpen((prev) => !prev)}
              >
                <Search size={14} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-9 w-9 rounded-xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => handleShiftPeriod(1)}
              >
                <ChevronRight size={16} className="mx-auto" />
              </button>

              {isJumpPickerOpen && (
                <div className="absolute top-11 right-0 z-20 w-[280px] rounded-[24px] border border-gray-200 bg-white p-4 shadow-[0_20px_50px_rgba(15,23,42,0.12)]">
                  <p className="text-[12px] font-bold text-gray-500 mb-3">跳到任意日期</p>
                  <input
                    type="date"
                    value={formatDateInputValue(selectedDate)}
                    onChange={(event) => handleDateJump(event.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
                  />
                  <button
                    type="button"
                    className="mt-3 w-full rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold h-11 shadow-[0_6px_18px_rgba(91,123,254,0.28)]"
                    onClick={() => {
                      handleGoToToday();
                      setIsJumpPickerOpen(false);
                    }}
                  >
                    回到今天
                  </button>
                </div>
              )}
              </div>
            </div>
          </div>

        </div>

        {calendarDisplayMode === 'month' ? (
          <>
            <div className="grid grid-cols-7 text-center text-[13px] font-bold text-gray-400 px-5 lg:px-6 pt-4 pb-3">
              {['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((day) => (
                <div key={day}>{day}</div>
              ))}
            </div>

            <div>
              {monthTimelineWeeks.map((week) => (
                <div key={week.key} className="grid w-full grid-cols-7">
                  {week.days.map(({ date: cellDate, dayTasks }) => {
                    const isActiveSelection = isSameDay(cellDate, selectedDate);
                    const isToday = isSameDay(cellDate, today);
                    const isMonthAnchor = cellDate.getDate() === 1;
                    const overflowCount = Math.max(dayTasks.length - 4, 0);
                    const chinaCalendarMarkers = getChinaCalendarMarkers(cellDate);
                    return (
                      <div
                        key={formatDateInputValue(cellDate)}
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          handleDaySelect(cellDate);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            handleDaySelect(cellDate);
                          }
                        }}
                        onDragOver={(event) => {
                          const draggedTaskId = resolveDraggedTaskId(event);
                          if (!draggedTaskId) return;
                          event.preventDefault();
                          if (dragTargetDay !== cellDate.getTime()) {
                            setDragTargetDay(cellDate.getTime());
                          }
                        }}
                        onDragLeave={() => {
                          if (dragTargetDay === cellDate.getTime()) {
                            setDragTargetDay(null);
                          }
                        }}
                        onDrop={(event) => {
                          const draggedTaskId = resolveDraggedTaskId(event);
                          if (!draggedTaskId) return;
                          event.preventDefault();
                          const droppedTask = visibleTasks.find((item) => item.id === draggedTaskId);
                          dragDropHandledRef.current = true;
                          setDragTargetDay(null);
                          setDraggingTaskId(null);
                          if (!droppedTask) return;
                          void handleTaskDrop(droppedTask, cellDate);
                        }}
                        data-calendar-date={formatDateInputValue(cellDate)}
                        className={`relative min-h-[146px] rounded-none border-r border-b border-gray-100 bg-transparent p-2.5 text-left align-top outline-none transition-colors focus:outline-none focus-visible:outline-none cursor-pointer hover:bg-slate-50 ${
                          isActiveSelection ? 'bg-blue-50/40' : ''
                        } ${
                          dragTargetDay === cellDate.getTime() ? 'bg-blue-100 ring-2 ring-inset ring-[#5B7BFE]/40' : ''
                        }`}
                      >
                        <div className="relative z-10 flex h-full flex-col">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <div className={`h-7 min-w-7 rounded-full flex items-center justify-center px-1 text-[13px] font-bold ${
                                isToday ? 'bg-rose-500 text-white' : isActiveSelection ? 'bg-[#5B7BFE] text-white' : 'text-gray-600 bg-white'
                              }`}>
                                {cellDate.getDate()}
                              </div>
                              {isMonthAnchor && (
                                <span className="text-[11px] font-semibold tracking-[0.08em] text-gray-400">
                                  {cellDate.getMonth() + 1}月
                                </span>
                              )}
                            </div>
                            {chinaCalendarMarkers.length > 0 && (
                              <div className="flex flex-wrap justify-end gap-1 max-w-[60%]">
                                {chinaCalendarMarkers.slice(0, 2).map((marker) => (
                                  <span
                                    key={`${formatDateInputValue(cellDate)}-${marker.kind}-${marker.label}`}
                                    className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none ${calendarMarkerClassName(marker)}`}
                                  >
                                    {marker.label}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          <div className="mt-2.5 flex min-h-0 flex-1 flex-col gap-1">
                            {dayTasks.slice(0, expandedCalendarDays.has(formatDateInputValue(cellDate)) ? dayTasks.length : 4).map((task) => {
                              const timedSegment = buildTaskDayTimedSegment(task, cellDate);
                              const timePrefix = timedSegment ? `${formatMinuteOfDay(timedSegment.startMinute)} ` : '';
                              return (
                                <div
                                  key={task.id}
                                  data-no-month-range-drag="true"
                                  draggable
                                  onMouseDown={(event) => {
                                    event.stopPropagation();
                                  }}
                                  onDragStart={(event) => {
                                    event.stopPropagation();
                                    event.dataTransfer.effectAllowed = 'move';
                                    event.dataTransfer.setData('text/plain', task.id);
                                    dragDropHandledRef.current = false;
                                    setDraggingTaskId(task.id);
                                  }}
                                  onDragEnd={() => {
                                    if (!dragDropHandledRef.current) {
                                      setDraggingTaskId(null);
                                      setDragTargetDay(null);
                                    }
                                    dragDropHandledRef.current = false;
                                  }}
                                  className={`group relative block max-w-full truncate rounded-lg border px-2 py-1 text-[11px] font-semibold text-left leading-4 cursor-grab active:cursor-grabbing ${
                                    task.status === 'done' ? '' : 'shadow-[0_1px_2px_rgba(15,23,42,0.04)]'
                                  } ${draggingTaskId === task.id ? 'opacity-50' : ''}`}
                                  style={calendarChipStyle(task)}
                                  title={`${timePrefix}${task.title}${taskOrgSummary(task) ? ` · ${taskOrgSummary(task)}` : ''}`}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleDaySelect(cellDate);
                                  }}
                                >
                                  <button
                                    type="button"
                                    data-no-month-range-drag="true"
                                    className={`absolute left-1.5 top-1/2 z-10 flex h-3.5 w-3.5 -translate-y-1/2 items-center justify-center rounded-[4px] border transition ${
                                      task.status === 'done'
                                        ? 'border-[#CBD5E1] bg-[#CBD5E1] text-white'
                                        : 'border-current bg-white/85 hover:bg-white'
                                    }`}
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void onToggleTaskStatus(task.id);
                                    }}
                                    title={task.status === 'done' ? '取消完成' : '标记完成'}
                                    aria-label={task.status === 'done' ? `取消完成 ${task.title}` : `完成 ${task.title}`}
                                  >
                                    {task.status === 'done' ? <Check size={10} strokeWidth={3} /> : null}
                                  </button>
                                  <button
                                    type="button"
                                    data-no-month-range-drag="true"
                                    className="absolute right-1.5 top-1/2 z-10 flex h-3.5 w-3.5 -translate-y-1/2 items-center justify-center rounded-[4px] border border-current bg-white/85 opacity-0 transition group-hover:opacity-100 hover:bg-white"
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      onOpenTaskEditor(task);
                                    }}
                                    title={`编辑 ${task.title}`}
                                    aria-label={`编辑 ${task.title}`}
                                  >
                                    <Pencil size={9} strokeWidth={2.5} />
                                  </button>
                                  <span className="block truncate pl-5 pr-5">{timePrefix}{task.title}</span>
                                </div>
                              );
                            })}
                            {overflowCount > 0 && !expandedCalendarDays.has(formatDateInputValue(cellDate)) && (
                              <button
                                type="button"
                                data-no-month-range-drag="true"
                                className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500 text-left hover:bg-slate-200 transition-colors cursor-pointer"
                                onMouseDown={(event) => {
                                  event.stopPropagation();
                                }}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setExpandedCalendarDays((prev) => { const next = new Set(prev); next.add(formatDateInputValue(cellDate)); return next; });
                                }}
                              >
                                + {overflowCount} 条更多
                              </button>
                            )}
                            {expandedCalendarDays.has(formatDateInputValue(cellDate)) && dayTasks.length > 4 && (
                              <button
                                type="button"
                                data-no-month-range-drag="true"
                                className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500 text-left hover:bg-slate-200 transition-colors cursor-pointer"
                                onMouseDown={(event) => {
                                  event.stopPropagation();
                                }}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setExpandedCalendarDays((prev) => { const next = new Set(prev); next.delete(formatDateInputValue(cellDate)); return next; });
                                }}
                              >
                                收起
                              </button>
                            )}
                            <button
                              type="button"
                              aria-label={`${cellDate.getDate()}日新建任务`}
                              className="group/add min-h-[18px] flex-1 rounded-lg bg-transparent hover:bg-blue-50/50 transition-colors flex items-center justify-center"
                              onMouseDown={(event) => {
                                event.stopPropagation();
                              }}
                              onClick={(event) => {
                                event.stopPropagation();
                                onOpenTaskEditor(undefined, formatDateInputValue(cellDate));
                              }}
                            >
                              <span className="text-[18px] text-blue-300 opacity-0 group-hover/add:opacity-100 transition-opacity font-light">+</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="border-t border-gray-100">
            <div
              ref={weekPagerRef}
              className="overflow-x-auto overscroll-x-contain snap-x snap-proximity"
              onScroll={handleWeekPagerScroll}
            >
              <div className="flex min-w-full">
                {weekPages.map((page) => (
                  <div
                    key={page.key}
                    className={`min-w-full snap-center transition-opacity duration-200 ${
                      isWeekPaging
                        ? page === visibleWeekPage
                          ? 'opacity-100'
                          : 'opacity-75'
                        : 'opacity-100'
                    }`}
                    onWheel={handleWeekScrollWheel}
                  >
                    <div className="grid grid-cols-[56px_repeat(7,minmax(0,1fr))] border-b border-gray-100 bg-white">
                      <div />
                      {page.days.map((day) => {
                        const isActive = isSameDay(day, selectedDate);
                        const isToday = isSameDay(day, today);
                        const chinaCalendarMarkers = getChinaCalendarMarkers(day);
                        return (
                          <button
                            key={day.toISOString()}
                            type="button"
                            className={`border-l border-gray-100 px-2 py-3 text-center transition-colors ${isActive ? 'bg-blue-50/60' : 'hover:bg-slate-50'}`}
                            onClick={() => handleDaySelect(day)}
                          >
                            <p className="text-[11px] font-semibold text-gray-400">{day.toLocaleDateString('zh-CN', { weekday: 'short' })}</p>
                            <div className="mt-2 flex items-center justify-center">
                              <span className={`flex h-8 min-w-8 items-center justify-center rounded-full px-2 text-[13px] font-bold ${isToday ? 'bg-rose-500 text-white' : isActive ? 'bg-[#5B7BFE] text-white' : 'text-gray-700 bg-white'}`}>
                                {day.getDate()}
                              </span>
                            </div>
                            {chinaCalendarMarkers.length > 0 && (
                              <div className="mt-2 flex flex-wrap items-center justify-center gap-1">
                                {chinaCalendarMarkers.slice(0, 2).map((marker) => (
                                  <span
                                    key={`${day.toISOString()}-${marker.kind}-${marker.label}`}
                                    className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold leading-none ${calendarMarkerClassName(marker)}`}
                                  >
                                    {marker.label}
                                  </span>
                                ))}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    <div
                      className="relative max-h-[860px] overflow-y-auto overscroll-contain"
                      data-week-scroll="true"
                      data-week-page-key={page.key}
                      onScroll={handleWeekVerticalScroll}
                    >
                      <div style={{ paddingBottom: `${DAY_TIMELINE_SCROLL_END_PADDING}px` }}>
                        <div className="grid grid-cols-[56px_repeat(7,minmax(0,1fr))] bg-white">
                        <div className="border-r border-gray-100">
                          {timelineSlotMinutes.map((minute) => {
                            const isHourLine = minute % 60 === 0;
                            return (
                              <div
                                key={`${page.key}-time-${minute}`}
                                className={`pr-2 text-right border-t ${isHourLine ? 'border-gray-200' : 'border-transparent'}`}
                                style={{ height: `${DAY_TIMELINE_SLOT_HEIGHT}px` }}
                              >
                                {isHourLine ? <span className="relative -top-2 text-[10px] font-semibold text-gray-400">{formatMinuteOfDay(minute)}</span> : null}
                              </div>
                            );
                          })}
                        </div>
                        {page.days.map((day, dayIndex) => (
                          <div
                            key={`${page.key}-column-${day.toISOString()}`}
                            className="relative border-r last:border-r-0 border-gray-100"
                            style={{ height: `${timelineSlotMinutes.length * DAY_TIMELINE_SLOT_HEIGHT}px` }}
                            data-week-day-key={day.getTime()}
                          >
                            {hourLineMinutes.map((minute) => (
                              <div
                                key={`${page.key}-hour-line-${day.toISOString()}-${minute}`}
                                className="pointer-events-none absolute left-0 right-0 border-t border-gray-200"
                                style={{ top: `${(minute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT}px` }}
                              />
                            ))}
                            {timelineSlotMinutes.map((minute) => (
                              <div
                                key={`${page.key}-${day.toISOString()}-${minute}`}
                                className={`group/slot relative cursor-pointer transition-colors ${dragTargetDay === day.getTime() && dragTargetMinute === minute ? 'bg-blue-50/70' : 'bg-transparent hover:bg-blue-50/40'}`}
                                style={{ height: `${DAY_TIMELINE_SLOT_HEIGHT}px` }}
                                onClick={() => {
                                  handleCreateTaskFromWeekSlot(day, minute);
                                }}
                                onDragOver={(event) => {
                                  const draggedTaskId = resolveDraggedTaskId(event);
                                  if (!draggedTaskId) return;
                                  event.preventDefault();
                                  if (dragTargetDay !== day.getTime()) setDragTargetDay(day.getTime());
                                  if (dragTargetMinute !== minute) setDragTargetMinute(minute);
                                }}
                                onDragLeave={() => {
                                  if (dragTargetDay === day.getTime() && dragTargetMinute === minute) {
                                    setDragTargetMinute(null);
                                  }
                                }}
                                onDrop={(event) => {
                                  const draggedTaskId = resolveDraggedTaskId(event);
                                  if (!draggedTaskId) return;
                                  event.preventDefault();
                                  const droppedTask = page.tasks.find((task) => task.id === draggedTaskId) || visibleTasks.find((task) => task.id === draggedTaskId);
                                  if (!droppedTask) {
                                    setDragTargetMinute(null);
                                    setDragTargetDay(null);
                                    setDraggingTaskId(null);
                                    return;
                                  }
                                  void handleWeekTimelineTaskDrop(droppedTask, day, minute);
                                }}
                                title={`${formatDateInputValue(day)} ${formatMinuteOfDay(minute)} 新建任务`}
                              >
                                <span className="pointer-events-none absolute inset-x-1 top-1/2 flex -translate-y-1/2 items-center justify-center opacity-0 transition-opacity group-hover/slot:opacity-100">
                                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/95 text-[#5B7BFE] shadow-sm ring-1 ring-[#5B7BFE]/15">
                                    <Plus size={11} strokeWidth={2.5} />
                                  </span>
                                </span>
                              </div>
                            ))}
                            {draggedTask && dragTargetDay === day.getTime() && dragTargetMinute !== null && (
                              <div
                                className="pointer-events-none absolute left-2 right-2 z-[1] rounded-2xl border border-dashed border-[#5B7BFE] bg-blue-50 shadow-[0_8px_24px_rgba(91,123,254,0.14)]"
                                style={{
                                  top: `${(dragTargetMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT + 2}px`,
                                  minHeight: `${Math.max(40, (draggedDurationMinutes / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4)}px`,
                                }}
                              >
                                <div className="flex h-full items-start justify-between gap-2 px-3 py-2 text-[#5B7BFE]">
                                  <span className="min-w-0 flex-1 text-[12px] font-bold leading-5 line-clamp-2">{draggedTask.title}</span>
                                  <span className="shrink-0 text-[10px] font-semibold">{`${formatMinuteOfDay(dragTargetMinute)}-${formatMinuteOfDay(Math.min(dragTargetMinute + draggedDurationMinutes, 24 * 60))}`}</span>
                                </div>
                              </div>
                            )}
                            {(weekDisplayItemsByDay.get(dayIndex) || []).map((displayItem) => {
                              const horizontalInset = 8;
                              const width = `calc(100% - ${horizontalInset * 2}px)`;
                              const left = `${horizontalInset}px`;

                              if (displayItem.kind === 'aggregate') {
                                const clusterCount = displayItem.clusterItems.length;
                                const currentIndex = Math.max(0, Math.min(clusterCount - 1, weekAggregateIndexes[displayItem.key] ?? 0));
                                const currentItem = displayItem.clusterItems[currentIndex];
                                const aggregateTask = currentItem.task;
                                const aggregateAccent = calendarChipStyle(aggregateTask);
                                const aggregateTop = (currentItem.startMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT;
                                const aggregateHeight = Math.max(72, ((currentItem.endMinute - currentItem.startMinute) / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4);
                                const aggregateTimeLabel = `${formatMinuteOfDay(currentItem.startMinute)}-${formatMinuteOfDay(currentItem.endMinute)}`;
                                const aggregateTitle = `重叠任务 ${currentIndex + 1}/${clusterCount}`;
                                const aggregateBorderColor = aggregateTask.status === 'done' ? '#CBD5E1' : aggregateAccent.borderColor;
                                const aggregateTextColor = aggregateTask.status === 'done' ? '#64748B' : aggregateAccent.color;
                                const aggregateBackgroundColor = aggregateTask.status === 'done' ? '#F1F5F9' : '#FFFFFF';
                                return (
                                  <div
                                    key={displayItem.key}
                                    className="group absolute rounded-2xl border px-2.5 py-2 text-left shadow-sm transition"
                                    style={{
                                      top: `${aggregateTop + 2}px`,
                                      left,
                                      width,
                                      minHeight: `${aggregateHeight}px`,
                                      color: aggregateTextColor,
                                      backgroundColor: aggregateBackgroundColor,
                                      borderColor: aggregateBorderColor,
                                      zIndex: 1,
                                    }}
                                    onMouseDown={(event) => {
                                      event.stopPropagation();
                                    }}
                                  >
                                    <div className="flex h-full flex-col gap-1">
                                      <div className="flex items-center justify-between gap-1">
                                        <div className="flex items-center gap-1">
                                          <button
                                            type="button"
                                            className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-current bg-white/90 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
                                            onClick={(event) => {
                                              event.stopPropagation();
                                              setWeekAggregateIndexes((prev) => ({
                                                ...prev,
                                                [displayItem.key]: Math.max(0, currentIndex - 1),
                                              }));
                                            }}
                                            disabled={currentIndex === 0}
                                            aria-label="查看上一条重叠任务"
                                          >
                                            <ChevronLeft size={9} strokeWidth={2.5} />
                                          </button>
                                          <button
                                            type="button"
                                            className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-current bg-white/90 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
                                            onClick={(event) => {
                                              event.stopPropagation();
                                              setWeekAggregateIndexes((prev) => ({
                                                ...prev,
                                                [displayItem.key]: Math.min(clusterCount - 1, currentIndex + 1),
                                              }));
                                            }}
                                            disabled={currentIndex >= clusterCount - 1}
                                            aria-label="查看下一条重叠任务"
                                          >
                                            <ChevronRight size={9} strokeWidth={2.5} />
                                          </button>
                                        </div>
                                        <div className="flex items-center gap-1">
                                          <span className="text-[9px] font-bold opacity-80">{aggregateTitle}</span>
                                          <button
                                            type="button"
                                            className={`flex h-4 w-4 items-center justify-center rounded-[4px] border bg-white/90 hover:bg-white ${aggregateTask.status === 'done' ? 'border-[#CBD5E1] text-[#64748B]' : 'border-current'}`}
                                            onClick={(event) => {
                                              event.stopPropagation();
                                              void onToggleTaskStatus(aggregateTask.id);
                                            }}
                                            title={aggregateTask.status === 'done' ? '取消完成' : '标记完成'}
                                            aria-label={aggregateTask.status === 'done' ? `取消完成 ${aggregateTask.title}` : `完成 ${aggregateTask.title}`}
                                          >
                                            <Check size={9} strokeWidth={3} />
                                          </button>
                                          <button
                                            type="button"
                                            className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-current bg-white/90 hover:bg-white"
                                            onClick={(event) => {
                                              event.stopPropagation();
                                              onOpenTaskEditor(aggregateTask);
                                            }}
                                            title={`编辑 ${aggregateTask.title}`}
                                            aria-label={`编辑 ${aggregateTask.title}`}
                                          >
                                            <Pencil size={9} strokeWidth={2.5} />
                                          </button>
                                        </div>
                                      </div>
                                      <div className="text-[10px] font-semibold opacity-80">{aggregateTimeLabel}</div>
                                      <div className={`text-[12px] font-bold leading-4 break-words line-clamp-3 ${aggregateTask.status === 'done' ? 'line-through opacity-70' : ''}`}>{aggregateTask.title}</div>
                                    </div>
                                  </div>
                                );
                              }

                              const { task, startMinute, durationMinutes } = displayItem.taskItem;
                              const effectiveDuration = resizingTaskId === task.id && resizePreviewMinutes ? resizePreviewMinutes : durationMinutes;
                              const effectiveEndMinute = Math.min(startMinute + effectiveDuration, 24 * 60);
                              const effectiveTimeLabel = `${formatMinuteOfDay(startMinute)}-${formatMinuteOfDay(effectiveEndMinute)}`;
                              const top = (startMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT;
                              const height = Math.max(40, ((effectiveEndMinute - startMinute) / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4);
                              const chipStyle = calendarChipStyle(task);
                              const isResizing = resizingTaskId === task.id;
                              return (
                                <div
                                  key={task.id}
                                  role="button"
                                  tabIndex={0}
                                  draggable={!isResizing}
                                  onDragStart={(event) => {
                                    event.stopPropagation();
                                    event.dataTransfer.effectAllowed = 'move';
                                    event.dataTransfer.setData('text/plain', task.id);
                                    dragDropHandledRef.current = false;
                                    setDraggingTaskId(task.id);
                                  }}
                                  onDragEnd={() => {
                                    if (!dragDropHandledRef.current) {
                                      setDraggingTaskId(null);
                                      setDragTargetDay(null);
                                      setDragTargetMinute(null);
                                    }
                                    dragDropHandledRef.current = false;
                                  }}
                                  className={`group absolute rounded-2xl border px-2.5 py-2 pb-5 text-left shadow-sm transition cursor-grab active:cursor-grabbing ${isResizing ? 'cursor-ns-resize ring-2 ring-[#5B7BFE]/40' : draggingTaskId === task.id ? 'opacity-50' : ''}`}
                                  style={{
                                    top: `${top + 2}px`,
                                    left,
                                    width,
                                    minHeight: `${Math.max(72, height)}px`,
                                    color: chipStyle.color,
                                    backgroundColor: task.status === 'done' ? '#F8FAFC' : '#FFFFFF',
                                    borderColor: chipStyle.borderColor,
                                    zIndex: draggingTaskId === task.id || isResizing ? 2 : 1,
                                  }}
                                  onMouseDown={(event) => {
                                    event.stopPropagation();
                                  }}
                                  onClick={(event) => handleWeekTaskSelect(event)}
                                  title={`${effectiveTimeLabel} ${task.title}`}
                                  aria-label={`${effectiveTimeLabel} ${task.title}`}
                                >
                                  <div className="flex h-full flex-col gap-1">
                                    <div className="flex items-center justify-end gap-1">
                                      <button
                                        type="button"
                                        className={`flex h-4 w-4 items-center justify-center rounded-[4px] border bg-white/90 hover:bg-white ${task.status === 'done' ? 'border-[#CBD5E1] text-[#64748B]' : 'border-current'}`}
                                        onMouseDown={(event) => {
                                          event.stopPropagation();
                                        }}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          void onToggleTaskStatus(task.id);
                                        }}
                                        title={task.status === 'done' ? '取消完成' : '标记完成'}
                                        aria-label={task.status === 'done' ? `取消完成 ${task.title}` : `完成 ${task.title}`}
                                      >
                                        <Check size={9} strokeWidth={3} />
                                      </button>
                                      <button
                                        type="button"
                                        className="flex h-4 w-4 items-center justify-center rounded-[4px] border border-current bg-white/90 hover:bg-white"
                                        onMouseDown={(event) => {
                                          event.stopPropagation();
                                        }}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          onOpenTaskEditor(task);
                                        }}
                                        title={`编辑 ${task.title}`}
                                        aria-label={`编辑 ${task.title}`}
                                      >
                                        <Pencil size={9} strokeWidth={2.5} />
                                      </button>
                                    </div>
                                    <div className="text-[10px] font-semibold opacity-80">{effectiveTimeLabel}</div>
                                    <div className="text-[12px] font-bold leading-4 line-clamp-3 break-words">{task.title}</div>
                                  </div>
                                  <div
                                    className={`absolute inset-x-0 bottom-0 flex h-5 cursor-ns-resize items-end justify-center rounded-b-2xl transition-opacity ${isResizing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                                    onMouseDown={(event) => handleStartWeekTaskResize(task.id, startMinute, durationMinutes, event)}
                                    onClick={(event) => {
                                      event.preventDefault();
                                      event.stopPropagation();
                                    }}
                                    title="拖动底边调整时长"
                                  >
                                    <div className="mb-1 flex items-center justify-center rounded-full bg-white/92 px-2 py-0.5 text-slate-400 shadow-sm ring-1 ring-slate-200">
                                      <MoveVertical size={12} />
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
