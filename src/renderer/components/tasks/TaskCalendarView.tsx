import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Flag,
  FolderDot,
  Plus,
  Search,
  UserRound,
  MoveVertical,
} from 'lucide-react';

import type { EventLine, Task, TaskContextPreview } from '../../../shared/types';
import { formatMonthTitle } from '../../../shared/calendar';
import { getChinaCalendarMarkers, type ChinaCalendarMarker } from '../../../shared/china-calendar';
import { getTaskContextPreview } from '../../lib/api';
import { TaskOrgContextPanel } from './TaskOrgContextPanel';

type DetailFilter = 'all' | 'open' | 'done';
type CalendarDisplayMode = 'month' | 'week';

type TaskCalendarViewProps = {
  tasks: Task[];
  eventLinesById?: Record<string, EventLine>;
  currentUserId?: string | null;
  currentUserRole?: 'admin' | 'employee' | null;
  calendarDisplayMode: CalendarDisplayMode;
  onSetCalendarDisplayMode: (mode: CalendarDisplayMode) => void;
  calendarDate: Date;
  selectedDate: Date;
  isDetailOpen: boolean;
  onSelectDate: (date: Date) => void;
  onSetDetailOpen: (open: boolean) => void;
  onShiftMonth: (delta: number) => void;
  onAlignCalendarDate: (date: Date) => void;
  onGoToToday: () => void;
  onOpenTaskEditor: (task?: Task, dueDate?: string, options?: { durationMinutes?: number }) => void;
  onToggleTaskStatus: (taskId: string, nextDone?: boolean) => Promise<void>;
  onQuickCreateTask: (title: string, dueDate: string) => Promise<void>;
  onRescheduleTask: (
    task: Task,
    dueDate: string,
    options?: { preserveCalendarViewport?: boolean },
  ) => Promise<void>;
  onUpdateTaskDuration: (task: Task, durationMinutes: number) => Promise<void>;
  onApproveTaskReview: (taskId: string) => Promise<void>;
  onReturnTaskReview: (taskId: string) => Promise<void>;
  taskDateForCalendar: (task: Task) => Date;
  isTaskOverdue: (task: Task, today?: Date) => boolean;
  showCollaborativeTasks: boolean;
  onToggleCollaborativeTasks: () => void;
};

const DETAIL_FILTERS: Array<{ key: DetailFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'open', label: '待推进' },
  { key: 'done', label: '已完成' },
];

const priorityLabels: Record<Task['priority'], string> = {
  high: '高优先级',
  normal: '普通优先级',
  low: '低优先级',
};

const priorityStyles: Record<Task['priority'], string> = {
  high: 'bg-rose-50 text-rose-600 border-rose-100',
  normal: 'bg-amber-50 text-amber-700 border-amber-100',
  low: 'bg-slate-100 text-slate-600 border-slate-200',
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
const DAY_MINUTES = 24 * 60;

type WeekCreateSelection = {
  dayKey: number;
  dayDate: Date;
  startMinute: number;
  endMinute: number;
};

type MonthCreateSelection = {
  startDate: Date;
  endDate: Date;
  spanDays: number;
};

function formatDateInputValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function splitTaskDueDateTime(value?: string | null) {
  if (!value) return { date: '', time: '' };
  const text = value.trim();
  if (!text) return { date: '', time: '' };
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/);
  if (match) {
    return {
      date: match[1],
      time: match[2] && match[3] ? `${match[2]}:${match[3]}` : '',
    };
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return { date: '', time: '' };
  return {
    date: formatDateInputValue(parsed),
    time: `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`,
  };
}

function minuteOfDayFromTime(value?: string | null) {
  if (!value) return null;
  const match = value.match(/^(\d{2}):(\d{2})$/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function formatMinuteOfDay(minuteOfDay: number) {
  const normalized = Math.max(0, Math.min(24 * 60, minuteOfDay));
  const hours = Math.floor(normalized / 60);
  const minutes = normalized % 60;
  return `${String(Math.min(hours, 24)).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
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

function compareCalendarDates(left: Date, right: Date) {
  return new Date(left.getFullYear(), left.getMonth(), left.getDate()).getTime()
    - new Date(right.getFullYear(), right.getMonth(), right.getDate()).getTime();
}

function buildMonthCreateSelection(anchorDate: Date, currentDate: Date): MonthCreateSelection {
  const isForward = compareCalendarDates(anchorDate, currentDate) <= 0;
  const startDate = isForward ? anchorDate : currentDate;
  const endDate = isForward ? currentDate : anchorDate;
  const diffDays = Math.round(
    (new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate()).getTime()
      - new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate()).getTime())
      / (24 * 60 * 60 * 1000),
  );
  return {
    startDate,
    endDate,
    spanDays: diffDays + 1,
  };
}

function dateFromCalendarCellTarget(target: EventTarget | null) {
  const element = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-calendar-date]') : null;
  const dateKey = element?.dataset.calendarDate;
  if (!dateKey) return null;
  const [yearText, monthText, dayText] = dateKey.split('-');
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function taskCalendarSpanDays(task: Task) {
  const { time } = splitTaskDueDateTime(task.dueDate);
  if (time) return 1;
  const durationMinutes = Math.max(0, task.durationMinutes ?? 0);
  if (durationMinutes < DAY_MINUTES) return 1;
  return Math.max(1, Math.ceil(durationMinutes / DAY_MINUTES));
}

function taskCoversCalendarDate(task: Task, date: Date, taskDateForCalendar: (task: Task) => Date) {
  const startDate = taskDateForCalendar(task);
  const spanDays = taskCalendarSpanDays(task);
  const endDate = addDays(startDate, spanDays - 1);
  return isDateWithinRange(date, startDate, endDate);
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

function statusLabel(status: Task['status']) {
  if (status === 'done') return '已完成';
  if (status === 'doing') return '进行中';
  if (status === 'inbox') return '待确认';
  return '待处理';
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
  if (isTransportItineraryTask(task)) return '#16A34A';
  return task.listColor;
}

function calendarChipStyle(task: Task) {
  if (task.status === 'done') {
    return {
      color: '#94A3B8',
      backgroundColor: '#F8FAFC',
      borderColor: '#E2E8F0',
    };
  }
  const accentColor = calendarTaskAccentColor(task);
  return {
    color: accentColor,
    backgroundColor: `${accentColor}14`,
    borderColor: `${accentColor}22`,
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

export function TaskCalendarView({
  tasks,
  eventLinesById = {},
  currentUserId,
  currentUserRole,
  calendarDisplayMode,
  onSetCalendarDisplayMode,
  calendarDate,
  selectedDate,
  isDetailOpen,
  onSelectDate,
  onSetDetailOpen,
  onShiftMonth,
  onAlignCalendarDate,
  onGoToToday,
  onOpenTaskEditor,
  onToggleTaskStatus,
  onQuickCreateTask,
  onRescheduleTask,
  onUpdateTaskDuration,
  onApproveTaskReview,
  onReturnTaskReview,
  taskDateForCalendar,
  isTaskOverdue,
  showCollaborativeTasks,
  onToggleCollaborativeTasks,
}: TaskCalendarViewProps) {
  const [detailFilter, setDetailFilter] = useState<DetailFilter>('all');
  const [isJumpPickerOpen, setIsJumpPickerOpen] = useState(false);
  const [quickTaskTitle, setQuickTaskTitle] = useState('');
  const [isCreatingQuickTask, setIsCreatingQuickTask] = useState(false);
  const [draggingTaskId, setDraggingTaskId] = useState<string | null>(null);
  const [dragTargetDay, setDragTargetDay] = useState<number | null>(null);
  const [dragTargetMinute, setDragTargetMinute] = useState<number | null>(null);
  const [expandedCalendarDays, setExpandedCalendarDays] = useState<Set<string>>(new Set());
  const dragDropHandledRef = useRef(false);
  const [selectedDetailTaskId, setSelectedDetailTaskId] = useState<string | null>(null);
  const [selectedDetailContextPreview, setSelectedDetailContextPreview] = useState<TaskContextPreview | null>(null);
  const [resizingTaskId, setResizingTaskId] = useState<string | null>(null);
  const [resizePreviewMinutes, setResizePreviewMinutes] = useState<number | null>(null);
  const [monthCreateSelection, setMonthCreateSelection] = useState<MonthCreateSelection | null>(null);
  const [weekCreateSelection, setWeekCreateSelection] = useState<WeekCreateSelection | null>(null);
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
  const monthCreateDraftRef = useRef<{ anchorDate: Date } | null>(null);
  const monthCreateSelectionRef = useRef<MonthCreateSelection | null>(null);
  const monthCreateCleanupRef = useRef<(() => void) | null>(null);
  const monthCreateDidDragRef = useRef(false);
  const monthCreateSuppressClickRef = useRef(false);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const timelineSectionRef = useRef<HTMLDivElement | null>(null);
  const weekTimelineScrollRef = useRef<HTMLDivElement | null>(null);
  const weekDetailSectionRef = useRef<HTMLDivElement | null>(null);
  const weekPagerRef = useRef<HTMLDivElement | null>(null);
  const weekPagerIdleTimerRef = useRef<number | null>(null);
  const weekPagerVerticalSyncRef = useRef(false);
  const weekPagerGestureDeadlineRef = useRef(0);
  const monthStackRef = useRef<HTMLDivElement | null>(null);
  const monthAlignmentKeyRef = useRef<string | null>(null);
  const explicitMonthFocusDateRef = useRef<Date | null>(null);
  const [centerTodayNonce, setCenterTodayNonce] = useState(0);
  const [visibleMonthDate, setVisibleMonthDate] = useState(() => new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1));
  const today = useMemo(() => new Date(), []);
  const visibleTasks = useMemo(
    () => tasks.filter((task) => task.status !== 'rejected'),
    [tasks],
  );
  const activeMonthDate = visibleMonthDate;

  const tasksByDay = useMemo(() => {
    const mapping = new Map<number, Task[]>();
    visibleTasks.forEach((task) => {
      const date = taskDateForCalendar(task);
      if (date.getMonth() !== activeMonthDate.getMonth() || date.getFullYear() !== activeMonthDate.getFullYear()) return;
      const day = date.getDate();
      const existing = mapping.get(day) || [];
      existing.push(task);
      mapping.set(day, existing);
    });
    mapping.forEach((dayTasks, day) => {
      mapping.set(day, sortTasksForCalendar(dayTasks));
    });
    return mapping;
  }, [activeMonthDate, taskDateForCalendar, visibleTasks]);

  const monthTasks = useMemo(
    () => Array.from(tasksByDay.values()).flat(),
    [tasksByDay],
  );

  const monthTasksByDateKey = useMemo(() => {
    const mapping = new Map<string, Task[]>();
    visibleTasks.forEach((task) => {
      const startDate = taskDateForCalendar(task);
      const spanDays = taskCalendarSpanDays(task);
      for (let offset = 0; offset < spanDays; offset += 1) {
        const date = addDays(startDate, offset);
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
  }, [taskDateForCalendar, visibleTasks]);

  const monthTimelineWeeks = useMemo(() => {
    const firstRenderedMonth = new Date(calendarDate.getFullYear(), calendarDate.getMonth() - 2, 1);
    const lastRenderedMonth = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 9, 1);
    const rangeStart = startOfWeek(firstRenderedMonth);
    const lastRenderedDay = new Date(lastRenderedMonth.getFullYear(), lastRenderedMonth.getMonth() + 1, 0);
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
        visibleTasks.filter((task) => isDateWithinRange(taskDateForCalendar(task), startDate, endDate)),
      );
      const timedTasks = tasks
        .map((task) => {
          const taskDate = taskDateForCalendar(task);
          const dayIndex = days.findIndex((day) => isSameDay(day, taskDate));
          if (dayIndex === -1) return null;
          const { time } = splitTaskDueDateTime(task.dueDate);
          const startMinute = minuteOfDayFromTime(time);
          if (startMinute === null) return null;
          const durationMinutes = Math.max(
            DAY_TIMELINE_SLOT_MINUTES,
            task.durationMinutes ?? DAY_TIMELINE_DEFAULT_DURATION_MINUTES,
          );
          const endMinute = Math.min(startMinute + durationMinutes, 24 * 60);
          return {
            task,
            dayIndex,
            dayDate: days[dayIndex],
            startMinute,
            endMinute,
            durationMinutes: endMinute - startMinute,
            timeLabel: `${formatMinuteOfDay(startMinute)}-${formatMinuteOfDay(endMinute)}`,
          };
        })
        .filter((item): item is { task: Task; dayIndex: number; dayDate: Date; startMinute: number; endMinute: number; durationMinutes: number; timeLabel: string } => Boolean(item));
      const unscheduledTasks = tasks.filter(
        (task) => minuteOfDayFromTime(splitTaskDueDateTime(task.dueDate).time) === null && task.status !== 'done',
      );
      return {
        key: `${startDate.toISOString()}-${offsetDays}`,
        offsetDays,
        startDate,
        endDate,
        days,
        title: formatWeekRangeTitle(startDate, endDate),
        tasks,
        timedTasks,
        unscheduledTasks,
      };
    });
  }, [taskDateForCalendar, visibleTasks, weekStartDate]);
  const currentWeekPage = weekPages[1];
  const visibleWeekPage = weekPages[visibleWeekPageIndex] ?? currentWeekPage;
  const weekStartKey = weekStartDate.getTime();
  const weekDays = visibleWeekPage.days;
  const weekEndDate = visibleWeekPage.endDate;
  const weekTasks = visibleWeekPage.tasks;
  const weekTimedTasks = visibleWeekPage.timedTasks;
  const floatingUnscheduledTasks = visibleWeekPage.unscheduledTasks;

  const selectedDayTasks = useMemo(
    () => sortTasksForCalendar(visibleTasks.filter((task) => taskCoversCalendarDate(task, selectedDate, taskDateForCalendar))),
    [selectedDate, taskDateForCalendar, visibleTasks],
  );

  const filteredDayTasks = useMemo(() => {
    if (detailFilter === 'open') return selectedDayTasks.filter((task) => task.status !== 'done');
    if (detailFilter === 'done') return selectedDayTasks.filter((task) => task.status === 'done');
    return selectedDayTasks;
  }, [detailFilter, selectedDayTasks]);

  const timedDayTasks = useMemo(() => {
    return filteredDayTasks
      .map((task) => {
        const { time } = splitTaskDueDateTime(task.dueDate);
        const startMinute = minuteOfDayFromTime(time);
        if (startMinute === null) return null;
        const durationMinutes = Math.max(DAY_TIMELINE_SLOT_MINUTES, task.durationMinutes ?? DAY_TIMELINE_DEFAULT_DURATION_MINUTES);
        const endMinute = Math.min(startMinute + durationMinutes, 24 * 60);
        return {
          task,
          startMinute,
          endMinute,
          durationMinutes: endMinute - startMinute,
          timeLabel: `${formatMinuteOfDay(startMinute)}-${formatMinuteOfDay(endMinute)}`,
        };
      })
      .filter((item): item is { task: Task; startMinute: number; endMinute: number; durationMinutes: number; timeLabel: string } => Boolean(item));
  }, [filteredDayTasks]);

  const untimedDayTasks = useMemo(
    () => filteredDayTasks.filter((task) => minuteOfDayFromTime(splitTaskDueDateTime(task.dueDate).time) === null),
    [filteredDayTasks],
  );
  const unscheduledTasks = useMemo(
    () => untimedDayTasks.filter((task) => task.status !== 'done'),
    [untimedDayTasks],
  );

  const selectedDetailPool = useMemo(
    () => (calendarDisplayMode === 'week' ? weekTasks : filteredDayTasks),
    [calendarDisplayMode, filteredDayTasks, weekTasks],
  );

  const draggedTask = useMemo(
    () => (calendarDisplayMode === 'week' ? weekTasks : filteredDayTasks).find((task) => task.id === draggingTaskId) || null,
    [calendarDisplayMode, draggingTaskId, filteredDayTasks, weekTasks],
  );

  const draggedDurationMinutes = useMemo(() => {
    if (!draggedTask) return DAY_TIMELINE_DEFAULT_DURATION_MINUTES;
    const timedMatch = (calendarDisplayMode === 'week' ? weekTimedTasks : timedDayTasks).find((item) => item.task.id === draggedTask.id);
    if (timedMatch) return timedMatch.durationMinutes;
    return Math.max(DAY_TIMELINE_SLOT_MINUTES, draggedTask.durationMinutes ?? DAY_TIMELINE_DEFAULT_DURATION_MINUTES);
  }, [calendarDisplayMode, draggedTask, timedDayTasks, weekTimedTasks]);

  const selectedDetailTask = useMemo(
    () => selectedDetailPool.find((task) => task.id === selectedDetailTaskId) || null,
    [selectedDetailPool, selectedDetailTaskId],
  );

  useEffect(() => {
    let isCancelled = false;
    if (!selectedDetailTask) {
      setSelectedDetailContextPreview(null);
      return;
    }
    void getTaskContextPreview(selectedDetailTask.id)
      .then((preview) => {
        if (!isCancelled) setSelectedDetailContextPreview(preview);
      })
      .catch(() => {
        if (!isCancelled) setSelectedDetailContextPreview(null);
      });
    return () => {
      isCancelled = true;
    };
  }, [selectedDetailTask]);

  useEffect(() => {
    const detailSelectionEnabled = calendarDisplayMode === 'week' || isDetailOpen;
    if (!detailSelectionEnabled) return;
    if (selectedDetailPool.length === 0) {
      setSelectedDetailTaskId(null);
      return;
    }
    if (!selectedDetailTaskId || !selectedDetailPool.some((task) => task.id === selectedDetailTaskId)) {
      setSelectedDetailTaskId(selectedDetailPool[0].id);
    }
  }, [calendarDisplayMode, isDetailOpen, selectedDetailPool, selectedDetailTaskId]);

  useEffect(() => {
    const nextScrollTop = Math.max(0, (DAY_TIMELINE_DEFAULT_START_MINUTE / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 12);
    if (calendarDisplayMode === 'week') {
      const pager = weekPagerRef.current;
      if (!pager) return;
      pager.querySelectorAll<HTMLElement>('[data-week-scroll="true"]').forEach((node) => {
        node.scrollTop = nextScrollTop;
      });
      return;
    }
    const activeScrollRef = timelineScrollRef.current;
    if (!isDetailOpen || !activeScrollRef) return;
    activeScrollRef.scrollTop = nextScrollTop;
    if (calendarDisplayMode === 'month' && window.innerWidth < 1280 && timelineSectionRef.current) {
      const target = timelineSectionRef.current;
      const frame = window.requestAnimationFrame(() => {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      return () => window.cancelAnimationFrame(frame);
    }
  }, [calendarDisplayMode, isDetailOpen, selectedDate]);

  useEffect(() => {
    if (calendarDisplayMode === 'week' && isDetailOpen) {
      onSetDetailOpen(false);
    }
  }, [calendarDisplayMode, isDetailOpen, onSetDetailOpen]);

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

  const cleanupMonthCreateInteraction = useCallback(() => {
    monthCreateCleanupRef.current?.();
    monthCreateCleanupRef.current = null;
    monthCreateDraftRef.current = null;
    monthCreateSelectionRef.current = null;
    monthCreateDidDragRef.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    return () => {
      cleanupWeekCreateInteraction();
    };
  }, [cleanupWeekCreateInteraction]);

  useEffect(() => {
    return () => {
      cleanupMonthCreateInteraction();
    };
  }, [cleanupMonthCreateInteraction]);

  useEffect(() => {
    setVisibleMonthDate(new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1));
  }, [calendarDate]);

  const syncVisibleMonthFromScroll = useCallback(() => {
    const container = monthStackRef.current;
    if (!container) return;
    const probeTop = container.scrollTop + Math.max(56, container.clientHeight * 0.28);
    const cells = Array.from(container.querySelectorAll<HTMLElement>('[data-calendar-date]'));
    const candidate =
      cells.find((cell) => cell.offsetTop + cell.offsetHeight > probeTop)
      || cells[0]
      || null;
    const dateKey = candidate?.dataset.calendarDate;
    if (!dateKey) return;
    const [yearText, monthText] = dateKey.split('-');
    const nextVisibleMonth = new Date(Number(yearText), Number(monthText) - 1, 1);
    setVisibleMonthDate((current) => (
      current.getFullYear() === nextVisibleMonth.getFullYear() && current.getMonth() === nextVisibleMonth.getMonth()
        ? current
        : nextVisibleMonth
    ));
  }, []);

  useLayoutEffect(() => {
    if (calendarDisplayMode !== 'month') return;
    const container = monthStackRef.current;
    if (!container) return;

    const isExplicitTodayFocus = centerTodayNonce > 0;
    const isCurrentMonthFocus = calendarDate.getFullYear() === today.getFullYear()
      && calendarDate.getMonth() === today.getMonth();
    const shouldCenterTarget = isExplicitTodayFocus || isCurrentMonthFocus;
    const fallbackDate = shouldCenterTarget
      ? today
      : new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
    const targetDate = explicitMonthFocusDateRef.current ?? fallbackDate;
    const targetKey = formatDateInputValue(targetDate);
    const alignmentKey = isExplicitTodayFocus
      ? `today:${centerTodayNonce}:${targetKey}`
      : shouldCenterTarget
        ? `current-month:${calendarDate.getFullYear()}-${calendarDate.getMonth() + 1}:${targetKey}`
        : `month:${calendarDate.getFullYear()}-${calendarDate.getMonth() + 1}`;

    if (monthAlignmentKeyRef.current === alignmentKey) return;

    let firstFrame = 0;
    let secondFrame = 0;
    let timeoutId: ReturnType<typeof window.setTimeout> | null = null;
    let attempts = 0;

    const alignMonthStack = () => {
      const targetCell = container.querySelector<HTMLElement>(`[data-calendar-date="${targetKey}"]`);
      if (!targetCell || container.clientHeight <= 0 || targetCell.offsetHeight <= 0) {
        if (attempts >= 10) return;
        attempts += 1;
        timeoutId = window.setTimeout(() => {
          firstFrame = window.requestAnimationFrame(() => {
            secondFrame = window.requestAnimationFrame(alignMonthStack);
          });
        }, 16);
        return;
      }

      const topPadding = shouldCenterTarget
        ? Math.max(24, (container.clientHeight - targetCell.offsetHeight) / 2)
        : 18;
      const nextTop = Math.max(0, targetCell.offsetTop - topPadding);
      container.scrollTo({
        top: nextTop,
        behavior: isExplicitTodayFocus ? 'smooth' : 'auto',
      });
      monthAlignmentKeyRef.current = alignmentKey;
      explicitMonthFocusDateRef.current = null;
      syncVisibleMonthFromScroll();
    };

    firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(alignMonthStack);
    });

    return () => {
      window.cancelAnimationFrame(firstFrame);
      if (secondFrame) window.cancelAnimationFrame(secondFrame);
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [calendarDate, calendarDisplayMode, centerTodayNonce, monthTimelineWeeks, syncVisibleMonthFromScroll, today]);

  const timelineSlotMinutes = useMemo(
    () => Array.from({ length: (24 * 60) / DAY_TIMELINE_SLOT_MINUTES }, (_, index) => index * DAY_TIMELINE_SLOT_MINUTES),
    [],
  );
  const hourLineMinutes = useMemo(
    () => timelineSlotMinutes.filter((minute) => minute % 60 === 0),
    [timelineSlotMinutes],
  );

  const canReviewTask = (task: Task) => {
    if (!task.orgContext?.needsReview || !currentUserId) return false;
    if (task.ownerId && task.ownerId === currentUserId) return false;
    return true;
  };

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

  const handleQuickCreate = async () => {
    const trimmed = quickTaskTitle.trim();
    if (!trimmed || isCreatingQuickTask) return;
    setIsCreatingQuickTask(true);
    try {
      await onQuickCreateTask(trimmed, formatDateInputValue(selectedDate));
      setQuickTaskTitle('');
    } finally {
      setIsCreatingQuickTask(false);
    }
  };

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
      if (isSameDay(date, selectedDate) && selectedDetailTaskId) {
        setSelectedDetailTaskId(null);
        return;
      }
      onSelectDate(date);
      setSelectedDetailTaskId(visibleWeekPage.tasks.find((task) => isSameDay(taskDateForCalendar(task), date))?.id || null);
      return;
    }
    if (isDetailOpen && isSameDay(date, selectedDate)) {
      onSetDetailOpen(false);
      return;
    }
    onSelectDate(date);
  };

  const handleDayDoubleClick = (date: Date) => {
    // 双击空白日期 → 直接新建任务（参考滴答清单交互）
    onOpenTaskEditor(undefined, formatDateInputValue(date));
    onAlignCalendarDate(date);
    onSetDetailOpen(true);
  };

  const handleStartMonthCreateSelection = (
    cellDate: Date,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    if (draggingTaskId || resizingTaskId || event.button !== 0) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('[data-no-month-range-drag="true"]')) return;
    cleanupMonthCreateInteraction();
    const initialSelection = buildMonthCreateSelection(cellDate, cellDate);
    monthCreateDraftRef.current = { anchorDate: cellDate };
    monthCreateSelectionRef.current = initialSelection;
    monthCreateDidDragRef.current = false;
    monthCreateSuppressClickRef.current = false;
    setMonthCreateSelection(initialSelection);
    setSelectedDetailTaskId(null);
    document.body.style.cursor = 'crosshair';
    document.body.style.userSelect = 'none';

    const updateSelectionFromPoint = (target: EventTarget | null) => {
      const draft = monthCreateDraftRef.current;
      if (!draft) return;
      const nextDate = dateFromCalendarCellTarget(target);
      if (!nextDate) return;
      const nextSelection = buildMonthCreateSelection(draft.anchorDate, nextDate);
      monthCreateSelectionRef.current = nextSelection;
      monthCreateDidDragRef.current = nextSelection.spanDays > 1;
      setMonthCreateSelection(nextSelection);
    };

    const handleWindowMouseMove = (moveEvent: MouseEvent) => {
      updateSelectionFromPoint(document.elementFromPoint(moveEvent.clientX, moveEvent.clientY));
    };

    const handleWindowMouseUp = (upEvent: MouseEvent) => {
      updateSelectionFromPoint(document.elementFromPoint(upEvent.clientX, upEvent.clientY));
      const selection = monthCreateSelectionRef.current;
      const didDrag = monthCreateDidDragRef.current;
      cleanupMonthCreateInteraction();
      setMonthCreateSelection(null);
      if (!selection || !didDrag) return;
      monthCreateSuppressClickRef.current = true;
      const dueDate = formatDateInputValue(selection.startDate);
      const durationMinutes = selection.spanDays * DAY_MINUTES;
      window.requestAnimationFrame(() => {
        onSelectDate(selection.startDate);
        onAlignCalendarDate(selection.startDate);
        onSetDetailOpen(true);
        onOpenTaskEditor(undefined, dueDate, { durationMinutes });
      });
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);
    monthCreateCleanupRef.current = () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
    };
  };

  const handleMonthCreateSelectionHover = (cellDate: Date) => {
    const draft = monthCreateDraftRef.current;
    if (!draft) return;
    const nextSelection = buildMonthCreateSelection(draft.anchorDate, cellDate);
    monthCreateSelectionRef.current = nextSelection;
    monthCreateDidDragRef.current = nextSelection.spanDays > 1;
    setMonthCreateSelection(nextSelection);
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
    setSelectedDetailTaskId(task.id);
    await onRescheduleTask(task, nextDueDate);
  };

  const handleWeekTimelineTaskDrop = async (task: Task, dayDate: Date, minuteOfDay: number) => {
    const nextDueDate = combineDateAndTime(dayDate, minuteOfDay);
    setDragTargetMinute(null);
    setDragTargetDay(null);
    setDraggingTaskId(null);
    setSelectedDetailTaskId(task.id);
    onSelectDate(dayDate);
    await onRescheduleTask(task, nextDueDate, { preserveCalendarViewport: true });
  };

  const resolveDraggedTaskId = (event: React.DragEvent) => {
    const transferTaskId = event.dataTransfer.getData('text/plain').trim();
    return transferTaskId || draggingTaskId || null;
  };

  const handleMonthStackScroll = () => {
    syncVisibleMonthFromScroll();
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
    setSelectedDetailTaskId(taskId);
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
    setSelectedDetailTaskId(null);
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
    explicitMonthFocusDateRef.current = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    onGoToToday();
    setCenterTodayNonce((value) => value + 1);
  };

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
  }, [calendarDisplayMode, weekStartKey]);

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
      if (node !== source) node.scrollTop = source.scrollTop;
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
    if (Math.abs(event.deltaX) <= Math.abs(event.deltaY) || Math.abs(event.deltaX) < 6) return;
    const pager = weekPagerRef.current;
    if (!pager) return;
    weekPagerGestureDeadlineRef.current = Date.now() + 280;
    pager.scrollLeft += event.deltaX;
    event.preventDefault();
  };

  const handleWeekTaskSelect = (taskId: string, event?: React.MouseEvent) => {
    event?.preventDefault();
    event?.stopPropagation();
    setSelectedDetailTaskId(taskId);
    if (typeof window !== 'undefined' && weekDetailSectionRef.current) {
      window.requestAnimationFrame(() => {
        weekDetailSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  };

  const periodStats = calendarDisplayMode === 'week' ? visibleWeekStats : monthStats;
  const periodTitle = calendarDisplayMode === 'week' ? visibleWeekPage.title : formatMonthTitle(visibleMonthDate);

  return (
    <div className={`w-full min-w-0 grid grid-cols-1 gap-6 items-start transition-all ${
      calendarDisplayMode === 'month' && isDetailOpen ? 'xl:grid-cols-[minmax(0,1.72fr)_minmax(360px,0.74fr)]' : 'xl:grid-cols-[minmax(0,1fr)]'
    }`}>
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

            <div ref={monthStackRef} className="max-h-[920px] overflow-y-auto" onScroll={handleMonthStackScroll}>
              {monthTimelineWeeks.map((week) => (
                <div key={week.key} className="grid w-full grid-cols-7">
                  {week.days.map(({ date: cellDate, dayTasks }) => {
                    const isActiveSelection = isSameDay(cellDate, selectedDate) && isDetailOpen;
                    const isToday = isSameDay(cellDate, today);
                    const isMonthAnchor = cellDate.getDate() === 1;
                    const isInMonthCreateSelection = monthCreateSelection
                      ? isDateWithinRange(cellDate, monthCreateSelection.startDate, monthCreateSelection.endDate)
                      : false;
                    const isMonthCreateStart = monthCreateSelection
                      ? isSameDay(cellDate, monthCreateSelection.startDate)
                      : false;
                    const overflowCount = Math.max(dayTasks.length - 4, 0);
                    const chinaCalendarMarkers = getChinaCalendarMarkers(cellDate);
                    return (
                      <div
                        key={formatDateInputValue(cellDate)}
                        role="button"
                        tabIndex={0}
                        onMouseDown={(event) => handleStartMonthCreateSelection(cellDate, event)}
                        onMouseEnter={() => handleMonthCreateSelectionHover(cellDate)}
                        onClick={() => {
                          if (monthCreateSuppressClickRef.current) {
                            monthCreateSuppressClickRef.current = false;
                            return;
                          }
                          handleDaySelect(cellDate);
                        }}
                        onDoubleClick={() => {
                          if (monthCreateSuppressClickRef.current) {
                            monthCreateSuppressClickRef.current = false;
                            return;
                          }
                          handleDayDoubleClick(cellDate);
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
                        } ${
                          isInMonthCreateSelection ? 'bg-blue-50/75 ring-1 ring-inset ring-[#5B7BFE]/30' : ''
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

                          {isMonthCreateStart && monthCreateSelection && monthCreateSelection.spanDays > 1 && (
                            <div className="mt-2">
                              <span className="inline-flex rounded-full border border-[#C9D7FF] bg-white/95 px-2 py-1 text-[10px] font-bold text-[#5B7BFE] shadow-sm">
                                新建 {monthCreateSelection.spanDays} 天任务
                              </span>
                            </div>
                          )}

                          <div className="mt-2.5 flex min-h-0 flex-1 flex-col gap-1">
                            {dayTasks.slice(0, expandedCalendarDays.has(formatDateInputValue(cellDate)) ? dayTasks.length : 4).map((task) => (
                              <div
                                key={task.id}
                                data-no-month-range-drag="true"
                                draggable
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
                                className={`relative block max-w-full truncate rounded-lg border px-2 py-1 text-[11px] font-semibold text-left leading-4 cursor-grab active:cursor-grabbing ${
                                  task.status === 'done' ? '' : 'shadow-[0_1px_2px_rgba(15,23,42,0.04)]'
                                } ${draggingTaskId === task.id ? 'opacity-50' : selectedDetailTaskId === task.id ? 'ring-2 ring-[#5B7BFE]/35' : ''}`}
                                style={calendarChipStyle(task)}
                                title={taskOrgSummary(task) || task.title}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onOpenTaskEditor(task);
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
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void onToggleTaskStatus(task.id);
                                  }}
                                  title={task.status === 'done' ? '取消完成' : '标记完成'}
                                  aria-label={task.status === 'done' ? `取消完成 ${task.title}` : `完成 ${task.title}`}
                                >
                                  {task.status === 'done' ? <Check size={10} strokeWidth={3} /> : null}
                                </button>
                                <span className="block truncate pl-5 pr-4">{task.title}</span>
                              </div>
                            ))}
                            {overflowCount > 0 && !expandedCalendarDays.has(formatDateInputValue(cellDate)) && (
                              <button
                                type="button"
                                data-no-month-range-drag="true"
                                className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-500 text-left hover:bg-slate-200 transition-colors cursor-pointer"
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
            <div className="px-5 lg:px-6 py-4 flex flex-col gap-3 border-b border-gray-100 bg-slate-50/40">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[13px] font-bold text-gray-700">本周时间轴</p>
                  <p className="mt-1 text-[11px] text-gray-400">把任务直接拖到具体日期和时段里，按周统筹时间安排。</p>
                </div>
              </div>
              {floatingUnscheduledTasks.length > 0 && (
                <div className="rounded-[20px] border border-gray-200 bg-slate-50/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <p className="text-[11px] font-bold text-gray-700">本周待排时间</p>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 border border-slate-200">
                        {floatingUnscheduledTasks.length} 条
                      </span>
                    </div>
                    <p className="text-[10px] font-medium text-gray-400">拖到下方周时间轴</p>
                  </div>
                  <div className="mt-2.5 max-h-[112px] overflow-y-auto pr-1">
                    <div className="flex flex-wrap gap-2">
                      {floatingUnscheduledTasks.map((task) => (
                        <div
                          key={task.id}
                          role="button"
                          tabIndex={0}
                          draggable
                          onDragStart={(event) => {
                            event.stopPropagation();
                            event.dataTransfer.effectAllowed = 'move';
                            event.dataTransfer.setData('text/plain', task.id);
                            dragDropHandledRef.current = false;
                            setDraggingTaskId(task.id);
                            setSelectedDetailTaskId(task.id);
                          }}
                          onDragEnd={() => {
                            if (!dragDropHandledRef.current) {
                              setDraggingTaskId(null);
                              setDragTargetDay(null);
                              setDragTargetMinute(null);
                            }
                            dragDropHandledRef.current = false;
                          }}
                          className={`group max-w-full rounded-2xl border px-3 py-2 text-left text-[11px] font-semibold transition cursor-grab active:cursor-grabbing ${
                            selectedDetailTaskId === task.id
                              ? 'border-[#5B7BFE] bg-blue-50 text-[#5B7BFE]'
                              : 'border-gray-200 bg-white text-gray-600 hover:border-blue-100 hover:text-[#5B7BFE]'
                          }`}
                          title="拖到下方时间轴即可设定日期和时间"
                          onClick={(event) => handleWeekTaskSelect(task.id, event)}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="block max-w-[220px] truncate leading-5">{task.title}</span>
                          </div>
                          <span className="mt-1 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 group-hover:bg-blue-50 group-hover:text-[#5B7BFE]">
                            {taskDateForCalendar(task).getMonth() + 1}-{taskDateForCalendar(task).getDate()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

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
                            onDoubleClick={() => handleDayDoubleClick(day)}
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
                      className="max-h-[860px] overflow-y-auto"
                      data-week-scroll="true"
                      onScroll={handleWeekVerticalScroll}
                    >
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
                            onMouseDown={(event) => handleStartWeekCreateSelection(day, event.currentTarget, event)}
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
                                className={`transition-colors ${dragTargetDay === day.getTime() && dragTargetMinute === minute ? 'bg-blue-50/70' : 'bg-transparent'}`}
                                style={{ height: `${DAY_TIMELINE_SLOT_HEIGHT}px` }}
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
                              />
                            ))}
                            {weekCreateSelection && weekCreateSelection.dayKey === day.getTime() && (
                              <div
                                className="pointer-events-none absolute left-2 right-2 z-[1] rounded-2xl border border-dashed border-[#5B7BFE] bg-blue-50/85 shadow-[0_8px_24px_rgba(91,123,254,0.14)]"
                                style={{
                                  top: `${(weekCreateSelection.startMinute / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT + 2}px`,
                                  minHeight: `${Math.max(40, ((weekCreateSelection.endMinute - weekCreateSelection.startMinute) / DAY_TIMELINE_SLOT_MINUTES) * DAY_TIMELINE_SLOT_HEIGHT - 4)}px`,
                                }}
                              >
                                <div className="flex h-full items-start justify-between gap-2 px-3 py-2 text-[#5B7BFE]">
                                  <span className="min-w-0 flex-1 text-[12px] font-bold leading-5">新建任务</span>
                                  <span className="shrink-0 text-[10px] font-semibold">
                                    {`${formatMinuteOfDay(weekCreateSelection.startMinute)}-${formatMinuteOfDay(weekCreateSelection.endMinute)}`}
                                  </span>
                                </div>
                              </div>
                            )}
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
                            {page.timedTasks.filter((item) => item.dayIndex === dayIndex).map(({ task, startMinute, durationMinutes }) => {
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
                                  className={`group absolute left-2 right-2 rounded-2xl border px-3 py-2 pb-5 text-left shadow-sm transition cursor-grab active:cursor-grabbing ${isResizing ? 'cursor-ns-resize ring-2 ring-[#5B7BFE]/40' : draggingTaskId === task.id ? 'opacity-50' : selectedDetailTaskId === task.id ? 'ring-2 ring-[#5B7BFE]/35' : ''}`}
                                  style={{
                                    top: `${top + 2}px`,
                                    minHeight: `${height}px`,
                                    color: chipStyle.color,
                                    backgroundColor: task.status === 'done' ? '#F8FAFC' : '#FFFFFF',
                                    borderColor: chipStyle.borderColor,
                                    zIndex: draggingTaskId === task.id || selectedDetailTaskId === task.id || isResizing ? 2 : 1,
                                  }}
                                  onMouseDown={(event) => {
                                    event.stopPropagation();
                                  }}
                                  onClick={(event) => handleWeekTaskSelect(task.id, event)}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <span className="min-w-0 flex-1 text-[12px] font-bold leading-5 line-clamp-2">{task.title}</span>
                                    <div className="flex items-start gap-2">
                                      <span className="shrink-0 text-[10px] font-semibold opacity-80">{effectiveTimeLabel}</span>
                                    </div>
                                  </div>
                                  <div className="mt-1 text-[10px] font-medium opacity-80">{statusLabel(task.status)}</div>
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
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {(calendarDisplayMode === 'week' || isDetailOpen) && (
      <div className="min-w-0 w-full self-stretch bg-white border border-gray-200 rounded-[32px] shadow-sm overflow-hidden flex flex-col">
        {calendarDisplayMode === 'week' ? (
          <div className="flex h-full flex-col">
            <div className="px-6 lg:px-7 py-5 border-b border-gray-100">
              <p className="text-[12px] font-bold tracking-[0.25em] text-[#5B7BFE] mb-1.5">WEEK DETAIL</p>
              <div className="flex items-baseline gap-3 flex-wrap">
                <h3 className="text-[22px] font-bold text-gray-900">{periodTitle}</h3>
                <p className="text-[12px] font-medium text-gray-500">
                  当前聚焦 {selectedDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })}
                </p>
              </div>
              <p className="mt-3 text-[12px] leading-6 text-gray-400">拖动左侧周时间轴可以直接调整日期和时间；点击任意任务块，在这里查看完整细节。</p>
            </div>

            <div ref={weekDetailSectionRef} className="p-6 space-y-4 flex-1 min-h-[540px]">
              {selectedDetailTask ? (
                <div className={`rounded-[28px] border p-4 transition-all ${
                  selectedDetailTask.status === 'done'
                    ? 'border-emerald-100 bg-emerald-50/40'
                    : 'border-gray-200 bg-white shadow-sm'
                }`}>
                  <div className="flex items-start gap-3">
                    <button type="button" onClick={() => void onToggleTaskStatus(selectedDetailTask.id)} className="mt-1 shrink-0">
                      {selectedDetailTask.status === 'done' ? (
                        <CheckCircle2 size={22} className="text-emerald-500" />
                      ) : (
                        <Circle size={22} className={selectedDetailTask.priority === 'high' ? 'text-rose-400' : 'text-gray-300'} />
                      )}
                    </button>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className={`text-[15px] font-bold leading-6 ${
                            selectedDetailTask.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-900'
                          }`}>
                            {selectedDetailTask.title}
                          </p>
                          {selectedDetailTask.desc && <p className="mt-2 text-[12px] leading-6 text-gray-500">{selectedDetailTask.desc}</p>}
                        </div>
                        <button
                          type="button"
                          className="shrink-0 text-[11px] font-bold text-gray-400 hover:text-[#5B7BFE]"
                          onClick={() => onOpenTaskEditor(selectedDetailTask)}
                        >
                          编辑
                        </button>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold">
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
                          {statusLabel(selectedDetailTask.status)}
                        </span>
                        <span className={`rounded-full border px-2.5 py-1 ${priorityStyles[selectedDetailTask.priority]}`}>
                          <span className="inline-flex items-center gap-1">
                            <Flag size={11} />
                            {priorityLabels[selectedDetailTask.priority]}
                          </span>
                        </span>
                        <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                          <span className="inline-flex items-center gap-1">
                            <FolderDot size={11} />
                            {selectedDetailTask.listName}
                          </span>
                        </span>
                        <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                          <span className="inline-flex items-center gap-1">
                            <UserRound size={11} />
                            {selectedDetailTask.ownerName || '未指定'}
                          </span>
                        </span>
                        <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                          <span className="inline-flex items-center gap-1">
                            <CalendarClock size={11} />
                            {selectedDetailTask.ddl}
                          </span>
                        </span>
                        {selectedDetailTask.projectContext?.clientName && (
                          <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-blue-700">
                            {selectedDetailTask.projectContext.clientName}
                          </span>
                        )}
                        {selectedDetailTask.eventLineName && (
                          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
                            事件线 · {selectedDetailTask.eventLineName}
                          </span>
                        )}
                      </div>
                      {canReviewTask(selectedDetailTask) && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="rounded-2xl bg-[#5B7BFE] px-3 py-1.5 text-[12px] font-bold text-white shadow-[0_6px_18px_rgba(91,123,254,0.24)]"
                            onClick={() => void onApproveTaskReview(selectedDetailTask.id)}
                          >
                            通过复核
                          </button>
                          <button
                            type="button"
                            className="rounded-2xl border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-bold text-gray-600 hover:border-rose-100 hover:text-rose-600"
                            onClick={() => void onReturnTaskReview(selectedDetailTask.id)}
                          >
                            退回复核
                          </button>
                        </div>
                      )}
                      <TaskOrgContextPanel
                        task={selectedDetailTask}
                        compact
                        viewerRole={currentUserRole}
                        eventLine={selectedDetailTask.eventLineId ? eventLinesById[selectedDetailTask.eventLineId] || null : null}
                        contextPreview={selectedDetailContextPreview}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full min-h-[220px] rounded-[28px] border border-dashed border-gray-200 bg-gray-50/60 flex flex-col items-center justify-center text-center px-8">
                  <div className="h-12 w-12 rounded-2xl bg-white border border-gray-200 flex items-center justify-center text-gray-400">
                    <CalendarClock size={20} />
                  </div>
                  <p className="mt-4 text-[15px] font-bold text-gray-700">先点击左侧周视图里的任务块</p>
                  <p className="mt-2 text-[12px] leading-6 text-gray-400">
                    这里会显示任务完整详情，也可以直接在左侧拖动调整时间。
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
        <div className="flex h-full flex-col">
        <div className="px-6 lg:px-7 py-5 border-b border-gray-100">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[12px] font-bold tracking-[0.25em] text-[#5B7BFE] mb-1.5">DAY DETAIL</p>
              <div className="flex items-baseline gap-3 flex-wrap">
                <h3 className="text-[22px] font-bold text-gray-900">
                  {selectedDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })}
                </h3>
                <p className="text-[12px] font-medium text-gray-500">
                  {selectedDate.toLocaleDateString('zh-CN', { weekday: 'long' })}
                  {isSameDay(selectedDate, today) ? ' · 今天' : ''}
                </p>
                {getChinaCalendarMarkers(selectedDate).length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {getChinaCalendarMarkers(selectedDate).slice(0, 2).map((marker) => (
                      <span
                        key={`${formatDateInputValue(selectedDate)}-${marker.kind}-${marker.label}`}
                        className={`rounded-full border px-2 py-1 text-[10px] font-semibold leading-none ${calendarMarkerClassName(marker)}`}
                      >
                        {marker.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                className="h-10 w-10 rounded-2xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => onSelectDate(addDays(selectedDate, -1))}
              >
                <ChevronLeft size={18} className="mx-auto" />
              </button>
              <button
                type="button"
                className="h-10 w-10 rounded-2xl border border-gray-200 text-gray-500 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
                onClick={() => onSelectDate(addDays(selectedDate, 1))}
              >
                <ChevronRight size={18} className="mx-auto" />
              </button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {DETAIL_FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                  detailFilter === filter.key
                    ? 'bg-[#5B7BFE] text-white shadow-[0_6px_16px_rgba(91,123,254,0.24)]'
                    : 'bg-gray-100 text-gray-500 hover:text-gray-800'
                }`}
                onClick={() => setDetailFilter(filter.key)}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6 space-y-4 flex-1 min-h-[540px]">


          {filteredDayTasks.length > 0 ? (
            filteredDayTasks.map((task) => (
              <div
                key={task.id}
                className={`rounded-[28px] border p-4 transition-all ${
                  task.status === 'done'
                    ? 'border-emerald-100 bg-emerald-50/40'
                    : 'border-gray-200 bg-white shadow-sm'
                } ${
                  selectedDetailTaskId === task.id ? 'ring-2 ring-[#5B7BFE]/20' : ''
                }`}
                onClick={() => setSelectedDetailTaskId(task.id)}
              >
                <div className="flex items-start gap-3">
                  <button type="button" onClick={() => void onToggleTaskStatus(task.id)} className="mt-1 shrink-0">
                    {task.status === 'done' ? (
                      <CheckCircle2 size={22} className="text-emerald-500" />
                    ) : (
                      <Circle size={22} className={task.priority === 'high' ? 'text-rose-400' : 'text-gray-300'} />
                    )}
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`text-[15px] font-bold leading-6 ${
                          task.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-900'
                        }`}>
                          {task.title}
                        </p>
                        {task.desc && <p className="mt-2 text-[12px] leading-6 text-gray-500">{task.desc}</p>}
                      </div>
                      <button
                        type="button"
                        className="shrink-0 text-[11px] font-bold text-gray-400 hover:text-[#5B7BFE]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenTaskEditor(task);
                        }}
                      >
                        编辑
                      </button>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold">
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
                        {statusLabel(task.status)}
                      </span>
                      <span className={`rounded-full border px-2.5 py-1 ${priorityStyles[task.priority]}`}>
                        <span className="inline-flex items-center gap-1">
                          <Flag size={11} />
                          {priorityLabels[task.priority]}
                        </span>
                      </span>
                      <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                        <span className="inline-flex items-center gap-1">
                          <FolderDot size={11} />
                          {task.listName}
                        </span>
                      </span>
                      <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                        <span className="inline-flex items-center gap-1">
                          <UserRound size={11} />
                          {task.ownerName || '未指定'}
                        </span>
                      </span>
                      <span className="rounded-full border border-gray-200 px-2.5 py-1 text-gray-500">
                        <span className="inline-flex items-center gap-1">
                          <CalendarClock size={11} />
                          {task.ddl}
                        </span>
                      </span>
                      {task.projectContext?.clientName && (
                        <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-blue-700">
                          {task.projectContext.clientName}
                        </span>
                      )}
                      {task.eventLineName && (
                        <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
                          事件线 · {task.eventLineName}
                        </span>
                      )}
                    </div>
                    {canReviewTask(task) && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-2xl bg-[#5B7BFE] px-3 py-1.5 text-[12px] font-bold text-white shadow-[0_6px_18px_rgba(91,123,254,0.24)]"
                          onClick={(event) => {
                            event.stopPropagation();
                            void onApproveTaskReview(task.id);
                          }}
                        >
                          通过复核
                        </button>
                        <button
                          type="button"
                          className="rounded-2xl border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-bold text-gray-600 hover:border-rose-100 hover:text-rose-600"
                          onClick={(event) => {
                            event.stopPropagation();
                            void onReturnTaskReview(task.id);
                          }}
                        >
                          退回复核
                        </button>
                      </div>
                    )}
                    <TaskOrgContextPanel
                      task={task}
                      compact
                      viewerRole={currentUserRole}
                      eventLine={task.eventLineId ? eventLinesById[task.eventLineId] || null : null}
                      contextPreview={task.id === selectedDetailTaskId ? selectedDetailContextPreview : null}
                    />
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="h-full min-h-[220px] rounded-[28px] border border-dashed border-gray-200 bg-gray-50/60 flex flex-col items-center justify-center text-center px-8">
              <div className="h-12 w-12 rounded-2xl bg-white border border-gray-200 flex items-center justify-center text-gray-400">
                <CalendarClock size={20} />
              </div>
              <p className="mt-4 text-[15px] font-bold text-gray-700">这一天还没有可查看的任务详情</p>
              <p className="mt-2 text-[12px] leading-6 text-gray-400">
                点击左侧日历里的任务，或者先快速新建一条任务。
              </p>
            </div>
          )}

        </div>

        <div className="border-t border-gray-100 bg-white px-6 py-5 space-y-3">
          <div className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-3">
            <div className="flex items-center gap-3">
              <input
                value={quickTaskTitle}
                onChange={(event) => setQuickTaskTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleQuickCreate();
                  }
                }}
                placeholder={`输入标题后回车，直接排进 ${selectedDate.getMonth() + 1}月${selectedDate.getDate()}日`}
                className="flex-1 bg-transparent px-3 py-2 text-[13px] font-medium text-gray-700 outline-none"
              />
              <button
                type="button"
                className="h-11 px-4 rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold shadow-[0_6px_18px_rgba(91,123,254,0.28)] disabled:opacity-60"
                onClick={() => void handleQuickCreate()}
                disabled={!quickTaskTitle.trim() || isCreatingQuickTask}
              >
                {isCreatingQuickTask ? '添加中...' : '快速添加'}
              </button>
            </div>
          </div>

          <button
            type="button"
            className="w-full rounded-2xl h-[46px] border border-gray-200 bg-white text-[13px] font-bold text-gray-700 hover:text-[#5B7BFE] hover:border-blue-100 transition-colors"
            onClick={() => onOpenTaskEditor(undefined, formatDateInputValue(selectedDate))}
          >
            <span className="inline-flex items-center gap-2">
              <Plus size={15} />
              为该日详细新建任务
            </span>
          </button>
        </div>
        </div>
        )}
      </div>
      )}
    </div>
  );
}
