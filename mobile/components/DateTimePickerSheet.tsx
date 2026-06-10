/**
 * DateTimePickerSheet – TickTick-style date & time picker bottom sheet.
 *
 * Two tabs:
 *   1. "日期"    – Month calendar grid + optional time + reminder
 *   2. "时间段"  – Visual timeline to drag a time range + all-day toggle
 *
 * Props:
 *   value      – current { date, time, durationMinutes } (may be partial)
 *   onChange   – called with updated values on confirm
 *   onClose    – dismiss
 *   onClear    – optional: remove date entirely
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Dimensions,
  Modal,
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { X, Check, ChevronLeft, ChevronRight, Clock, Bell, Repeat } from "lucide-react-native";
import { colors, fontSize, spacing, borderRadius, shadow, palette, typography, iconStroke } from "../lib/theme";
import { useAppChromeInsets, zLayer } from "../lib/app-chrome";

// ─── Types ──────────────────────────────────────

export interface DateTimeValue {
  /** 开始日 ISO date string "YYYY-MM-DD" */
  date: string | null;
  /** 开始时间 "HH:mm" */
  time: string | null;
  /** 结束日 "YYYY-MM-DD"；跨天时与 date 不同，缺省同 date。仅"时间段"带时间时有意义。 */
  endDate?: string | null;
  /** 结束时间 "HH:mm"；null 表示不设结束。 */
  endTime?: string | null;
  /** Duration in minutes (for time-range mode)；由 (end-start) 推导，跨天可 >1440。 */
  durationMinutes: number | null;
  /** 提醒提前量（分钟）：0=准时, 5=提前5分, null=不提醒。跨端共享同一语义。 */
  reminderMinutesBefore?: number | null;
}

// 提醒预设：产品定的"准时 / 提前5分钟"，外加"不提醒"。后续要加 15/30/1小时在这里扩。
const REMINDER_PRESETS: { label: string; value: number | null }[] = [
  { label: "不提醒", value: null },
  { label: "准时", value: 0 },
  { label: "提前5分钟", value: 5 },
];

function reminderLabel(value: number | null | undefined): string {
  if (value == null) return "不提醒";
  if (value === 0) return "准时";
  return `提前${value}分钟`;
}

interface Props {
  value: DateTimeValue;
  onChange: (v: DateTimeValue) => void;
  onClose: () => void;
  onClear?: () => void;
}

// ─── Constants ──────────────────────────────────

const SCREEN_WIDTH = Dimensions.get("window").width;
const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"] as const;
const TIMELINE_HOUR_START = 6;
const TIMELINE_HOUR_END = 23;
const TIMELINE_HOURS = TIMELINE_HOUR_END - TIMELINE_HOUR_START + 1;
const TIMELINE_ROW_H = 48;
const TIMELINE_TOTAL_H = TIMELINE_HOURS * TIMELINE_ROW_H;
const HANDLE_SIZE = 20;
const MIN_DURATION = 15; // minimum 15 min

// ─── Helpers ────────────────────────────────────

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseMonthYear(dateStr: string): [number, number] {
  const [y, m] = dateStr.split("-").map(Number);
  return [y, m];
}

function isToday(dateStr: string): boolean {
  return dateStr === today();
}

function isSameDay(a: string, b: string | null): boolean {
  if (!b) return false;
  return a === b;
}

function monthDays(year: number, month: number) {
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startWeekday = first.getDay();
  const cells: { dateStr: string; day: number; isCurrentMonth: boolean }[] = [];

  // Previous month padding
  if (startWeekday > 0) {
    const prevDays = new Date(year, month - 1, 0).getDate();
    const prevMonth = month === 1 ? 12 : month - 1;
    const prevYear = month === 1 ? year - 1 : year;
    for (let i = startWeekday - 1; i >= 0; i--) {
      const day = prevDays - i;
      cells.push({
        dateStr: `${prevYear}-${String(prevMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        day,
        isCurrentMonth: false,
      });
    }
  }
  // Current month
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push({
      dateStr: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      day,
      isCurrentMonth: true,
    });
  }
  // Next month padding
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    const nextMonth = month === 12 ? 1 : month + 1;
    const nextYear = month === 12 ? year + 1 : year;
    for (let day = 1; day <= remaining; day++) {
      cells.push({
        dateStr: `${nextYear}-${String(nextMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        day,
        isCurrentMonth: false,
      });
    }
  }
  return cells;
}

function weekdayLabel(dateStr: string): string {
  const d = new Date(dateStr);
  return ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][d.getDay()];
}

function formatMonthDay(dateStr: string): string {
  const [, m, d] = dateStr.split("-").map(Number);
  return `${m}月${d}日`;
}

function formatDuration(mins: number): string {
  if (mins < 60) return `${mins}分钟`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}小时${m}分钟` : `${h}小时`;
}

function minutesToTimeStr(totalMins: number): string {
  const h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function timeStrToMinutes(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

// 从"开始(日期+时间)+ 时长"反推结束的【日期+时间】。
// 用真实 Date 运算做跨天日期进位——不能用 minutesToTimeStr(start+dur)（会溢出成 26:00 且不换日）。
// 仅当 endDate/endTime 未显式给出、但 durationMinutes 仍在（如云端只回传了 duration）时作回退。
function deriveEndDateTime(
  date: string | null,
  time: string | null,
  durationMinutes: number | null | undefined,
): { endDate: string | null; endTime: string | null } {
  if (!date || !time || !durationMinutes || durationMinutes <= 0) return { endDate: null, endTime: null };
  const start = new Date(`${date}T${time}:00`);
  if (Number.isNaN(start.getTime())) return { endDate: null, endTime: null };
  const end = new Date(start.getTime() + durationMinutes * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    endDate: `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`,
    endTime: `${pad(end.getHours())}:${pad(end.getMinutes())}`,
  };
}

function minutesToY(mins: number): number {
  return ((mins - TIMELINE_HOUR_START * 60) / 60) * TIMELINE_ROW_H;
}

function yToMinutes(y: number): number {
  const raw = (y / TIMELINE_ROW_H) * 60 + TIMELINE_HOUR_START * 60;
  return Math.round(raw / 5) * 5; // snap to 5-min
}

// ─── TIME PICKER (hour grid) ────────────────────

function TimeGrid({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (t: string) => void;
}) {
  const hours = useMemo(() => {
    const result: string[] = [];
    for (let h = 0; h < 24; h++) {
      result.push(`${String(h).padStart(2, "0")}:00`);
      result.push(`${String(h).padStart(2, "0")}:30`);
    }
    return result;
  }, []);

  return (
    <View style={gs.timeGrid}>
      {hours.map((t) => {
        const isSel = t === selected;
        return (
          <TouchableOpacity
            key={t}
            style={[gs.timeGridCell, isSel && gs.timeGridCellSelected]}
            onPress={() => onSelect(t)}
            activeOpacity={0.6}
          >
            <Text style={[gs.timeGridText, isSel && gs.timeGridTextSelected]}>{t}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

// ─── MONTH GRID (self-contained, reused by date tab & range endpoints) ──────

function MonthGrid({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (dateStr: string) => void;
}) {
  const [selYear, selMonth] = parseMonthYear(selected);
  const [viewYear, setViewYear] = useState(selYear);
  const [viewMonth, setViewMonth] = useState(selMonth);

  // 选中日跳到别的月份时（如切换开始/结束端点），让视图月跟随
  useEffect(() => {
    setViewYear(selYear);
    setViewMonth(selMonth);
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  const days = useMemo(() => monthDays(viewYear, viewMonth), [viewYear, viewMonth]);

  const prevMonth = useCallback(() => {
    setViewMonth((m) => {
      if (m === 1) { setViewYear((y) => y - 1); return 12; }
      return m - 1;
    });
  }, []);
  const nextMonth = useCallback(() => {
    setViewMonth((m) => {
      if (m === 12) { setViewYear((y) => y + 1); return 1; }
      return m + 1;
    });
  }, []);

  return (
    <>
      <View style={s.monthNav}>
        <Text style={s.monthTitle}>{viewMonth}月</Text>
        {viewYear !== new Date().getFullYear() && <Text style={s.yearLabel}>{viewYear}年</Text>}
        <View style={s.monthNavRight}>
          <TouchableOpacity onPress={prevMonth} hitSlop={10}>
            <ChevronLeft size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity onPress={nextMonth} hitSlop={10}>
            <ChevronRight size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      </View>
      <View style={s.weekRow}>
        {WEEKDAY_LABELS.map((label) => (
          <Text key={label} style={s.weekLabel}>{label}</Text>
        ))}
      </View>
      <View style={s.daysGrid}>
        {days.map((cell, idx) => {
          const isTd = isToday(cell.dateStr);
          const isSel = isSameDay(cell.dateStr, selected);
          return (
            <TouchableOpacity key={idx} style={s.dayCell} onPress={() => onSelect(cell.dateStr)} activeOpacity={0.6}>
              <View style={[s.dayCircle, isSel && s.dayCircleSel, isTd && !isSel && s.dayCircleToday]}>
                <Text
                  style={[
                    s.dayText,
                    !cell.isCurrentMonth && s.dayTextOther,
                    isSel && s.dayTextSel,
                    isTd && !isSel && s.dayTextToday,
                  ]}
                >
                  {cell.day}
                </Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </>
  );
}

// ─── VISUAL TIMELINE (scrollable + draggable block) ──────────

const TIMELINE_VISIBLE_H = 260;

function VisualTimeline({
  startMins,
  endMins,
  onChangeRange,
}: {
  startMins: number;
  endMins: number;
  onChangeRange: (start: number, end: number) => void;
}) {
  const scrollRef = useRef<ScrollView>(null);
  const [scrollLocked, setScrollLocked] = useState(false);
  const startY = useRef(0);
  const endYRef = useRef(0);
  const blockOffset = useRef(0);

  // Auto-scroll to the time block on mount
  useEffect(() => {
    const targetY = minutesToY(startMins) - 60; // 60px above block
    setTimeout(() => {
      scrollRef.current?.scrollTo({ y: Math.max(0, targetY), animated: false });
    }, 100);
  }, []); // only on mount

  // Block drag (move both handles together)
  const blockPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          blockOffset.current = minutesToY(startMins);
        },
        onPanResponderMove: (_, g) => {
          const duration = endMins - startMins;
          const maxStartY = TIMELINE_TOTAL_H - (duration / 60) * TIMELINE_ROW_H;
          const newStartY = Math.max(0, Math.min(blockOffset.current + g.dy, maxStartY));
          const newStart = yToMinutes(newStartY);
          const newEnd = newStart + duration;
          if (newStart >= TIMELINE_HOUR_START * 60 && newEnd <= (TIMELINE_HOUR_END + 1) * 60) {
            onChangeRange(newStart, newEnd);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  // Top handle (change start time)
  const topPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 3,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          startY.current = minutesToY(startMins);
        },
        onPanResponderMove: (_, g) => {
          const newY = startY.current + g.dy;
          const newStart = yToMinutes(Math.max(0, newY));
          if (newStart < endMins - MIN_DURATION && newStart >= TIMELINE_HOUR_START * 60) {
            onChangeRange(newStart, endMins);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  // Bottom handle (change end time)
  const bottomPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 3,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          endYRef.current = minutesToY(endMins);
        },
        onPanResponderMove: (_, g) => {
          const newY = endYRef.current + g.dy;
          const newEnd = yToMinutes(Math.max(0, newY));
          if (newEnd > startMins + MIN_DURATION && newEnd <= (TIMELINE_HOUR_END + 1) * 60) {
            onChangeRange(startMins, newEnd);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  const blockTop = minutesToY(startMins);
  const blockHeight = minutesToY(endMins) - blockTop;

  // Current time indicator
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();
  const showNowLine = nowMins >= TIMELINE_HOUR_START * 60 && nowMins <= (TIMELINE_HOUR_END + 1) * 60;
  const nowY = minutesToY(nowMins);

  return (
    <ScrollView
      ref={scrollRef}
      style={gs.timelineScrollView}
      contentContainerStyle={gs.timelineContainer}
      showsVerticalScrollIndicator={false}
      scrollEnabled={!scrollLocked}
      nestedScrollEnabled
    >
      {/* Hour labels */}
      {Array.from({ length: TIMELINE_HOURS }, (_, i) => {
        const hour = TIMELINE_HOUR_START + i;
        return (
          <View key={hour} style={[gs.timelineRow, { height: TIMELINE_ROW_H }]}>
            <Text style={gs.timelineHourLabel}>{String(hour).padStart(2, "0")}</Text>
            <View style={gs.timelineHourLine} />
            <View style={[gs.timelineHalfLine, { top: TIMELINE_ROW_H / 2 }]} />
          </View>
        );
      })}

      {/* Time block (draggable) */}
      <View
        style={[gs.timeBlock, { top: blockTop, height: Math.max(blockHeight, 36) }]}
        {...blockPan.panHandlers}
      >
        <Text style={gs.timeBlockLabel}>
          {minutesToTimeStr(startMins)} - {minutesToTimeStr(endMins)}
        </Text>
        <Text style={gs.timeBlockDuration}>{formatDuration(endMins - startMins)}</Text>
      </View>

      {/* Top handle */}
      <View
        style={[gs.handle, gs.handleTop, { top: blockTop - HANDLE_SIZE / 2 }]}
        {...topPan.panHandlers}
      >
        <View style={gs.handleDot} />
      </View>

      {/* Bottom handle */}
      <View
        style={[gs.handle, gs.handleBottom, { top: blockTop + blockHeight - HANDLE_SIZE / 2 }]}
        {...bottomPan.panHandlers}
      >
        <View style={gs.handleDot} />
      </View>

      {/* Current time line */}
      {showNowLine && (
        <View style={[gs.nowLine, { top: nowY }]} pointerEvents="none">
          <View style={gs.nowDot} />
          <View style={gs.nowBar} />
        </View>
      )}
    </ScrollView>
  );
}

// ═════════════════════════════════════════════════
// ─── MAIN COMPONENT ─────────────────────────────
// ═════════════════════════════════════════════════

export default function DateTimePickerSheet({ value, onChange, onClose, onClear }: Props) {
  const chrome = useAppChromeInsets();
  const todayStr = today();

  // ── 起止状态（真相源：开始日/时间 + 结束日/时间）──
  const initialDate = value.date ?? todayStr;
  const [selectedDate, setSelectedDate] = useState(initialDate); // 开始日
  const [selectedTime, setSelectedTime] = useState<string | null>(value.time); // 开始时间
  // 结束日/时间：显式 endDate/endTime 优先；否则从 开始+时长 跨天反推（云端可能只回传 duration）
  const derivedEnd = deriveEndDateTime(value.date, value.time, value.durationMinutes);
  const [endDate, setEndDate] = useState<string>(value.endDate ?? derivedEnd.endDate ?? initialDate); // 结束日
  const [endTime, setEndTime] = useState<string | null>(value.endTime ?? derivedEnd.endTime);
  const [isAllDay, setIsAllDay] = useState(!value.time);
  const [reminderMinutes, setReminderMinutes] = useState<number | null>(value.reminderMinutesBefore ?? null);
  const [showReminderOptions, setShowReminderOptions] = useState(false);

  // date tab 的内联时间网格开关
  const [showTimeGrid, setShowTimeGrid] = useState(false);
  // "时间段" tab 正在编辑哪个端点的"日期+时间"（null=不在编辑，显示同日时间轴）
  const [editingEndpoint, setEditingEndpoint] = useState<"start" | "end" | null>(null);

  // Tab: "date" or "range"。带时长或带结束时间时进"时间段"
  const [tab, setTab] = useState<"date" | "range">(
    (value.durationMinutes && value.durationMinutes > 0) || value.endTime != null ? "range" : "date",
  );

  // 同日可视时间轴拖动 → 同步起止时间（仍锚定同一天）
  const handleRangeChange = useCallback(
    (start: number, end: number) => {
      setSelectedTime(minutesToTimeStr(start));
      setEndTime(minutesToTimeStr(end));
      setEndDate(selectedDate);
      setIsAllDay(false);
    },
    [selectedDate],
  );

  // 全天开关：开→清时间；关→给个默认 09:00–10:00 同日
  const toggleAllDay = useCallback(() => {
    setIsAllDay((prev) => {
      const next = !prev;
      if (!next && !selectedTime) {
        setSelectedTime("09:00");
        setEndTime("10:00");
        setEndDate(selectedDate);
      }
      return next;
    });
  }, [selectedTime, selectedDate]);

  // Confirm。"时间段"输出起止日期+时间（可跨天）；其余输出单时刻/全天。
  const handleConfirm = useCallback(() => {
    if (isAllDay) {
      onChange({
        date: selectedDate, time: null, endDate: null, endTime: null,
        durationMinutes: null, reminderMinutesBefore: reminderMinutes,
      });
    } else if (tab === "range") {
      const startTime = selectedTime ?? "09:00";
      const durationMinutes =
        endTime != null
          ? Math.round(
              (new Date(`${endDate}T${endTime}:00`).getTime() -
                new Date(`${selectedDate}T${startTime}:00`).getTime()) / 60_000,
            )
          : null;
      onChange({
        date: selectedDate,
        time: startTime,
        endDate,
        endTime,
        durationMinutes: durationMinutes && durationMinutes > 0 ? durationMinutes : null,
        reminderMinutesBefore: reminderMinutes,
      });
    } else {
      onChange({
        date: selectedDate, time: selectedTime, endDate: null, endTime: null,
        durationMinutes: null, reminderMinutesBefore: reminderMinutes,
      });
    }
    onClose();
  }, [tab, isAllDay, selectedDate, selectedTime, endDate, endTime, reminderMinutes, onChange, onClose]);

  // 提醒行（两个 tab 共用）：点开展开"不提醒/准时/提前5分钟"
  const renderReminderRow = () => (
    <>
      <TouchableOpacity
        style={s.optionRow}
        activeOpacity={0.6}
        onPress={() => setShowReminderOptions((v) => !v)}
      >
        <Bell size={18} color={colors.textSecondary} />
        <Text style={s.optionLabel}>提醒</Text>
        <Text style={reminderMinutes == null ? s.optionValueGray : s.optionValueBlue}>
          {reminderLabel(reminderMinutes)}
        </Text>
      </TouchableOpacity>
      {showReminderOptions ? (
        <View style={s.reminderOptions}>
          {REMINDER_PRESETS.map((preset) => {
            const active = reminderMinutes === preset.value;
            return (
              <TouchableOpacity
                key={String(preset.value)}
                style={[s.reminderChip, active && s.reminderChipActive]}
                activeOpacity={0.7}
                onPress={() => { setReminderMinutes(preset.value); setShowReminderOptions(false); }}
              >
                <Text style={[s.reminderChipText, active && s.reminderChipTextActive]}>{preset.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      ) : null}
    </>
  );

  // Select time from grid（"日期" tab 的单时刻）
  const handleTimeSelect = useCallback((t: string) => {
    setSelectedTime(t);
    setShowTimeGrid(false);
    setIsAllDay(false);
  }, []);

  // ═════ RENDER ═════

  return (
    <Modal
      visible
      transparent
      animationType="slide"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <View style={s.overlay}>
        <Pressable style={s.backdrop} onPress={onClose} />
        <Animated.View style={s.sheet}>
          {/* Top bar: close / tabs / confirm */}
          <View style={s.topBar}>
          <TouchableOpacity onPress={onClose} hitSlop={12}>
            <X size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={s.tabRow}>
            <TouchableOpacity
              style={[s.tabButton, tab === "date" && s.tabButtonActive]}
              onPress={() => setTab("date")}
            >
              <Text style={[s.tabLabel, tab === "date" && s.tabLabelActive]}>日期</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.tabButton, tab === "range" && s.tabButtonActive]}
              onPress={() => setTab("range")}
            >
              <Text style={[s.tabLabel, tab === "range" && s.tabLabelActive]}>时间段</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity onPress={handleConfirm} hitSlop={12}>
            <Check size={22} color={colors.brand} />
          </TouchableOpacity>
        </View>

        {/* ═══════ DATE TAB ═══════ */}
        {tab === "date" && (
          <View style={s.tabContent}>
            <MonthGrid selected={selectedDate} onSelect={setSelectedDate} />

            {/* Options: time, reminder */}
            <View style={s.optionsSection}>
              {/* Time row */}
              <TouchableOpacity
                style={s.optionRow}
                onPress={() => setShowTimeGrid((v) => !v)}
                activeOpacity={0.6}
              >
                <Clock size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>时间</Text>
                {selectedTime && !isAllDay ? (
                  <View style={s.optionValueRow}>
                    <Text style={s.optionValueBlue}>{selectedTime}</Text>
                    <TouchableOpacity
                      hitSlop={8}
                      onPress={() => { setSelectedTime(null); setIsAllDay(true); setShowTimeGrid(false); }}
                    >
                      <X size={14} color={colors.textTertiary} />
                    </TouchableOpacity>
                  </View>
                ) : (
                  <Text style={s.optionValueGray}>无</Text>
                )}
              </TouchableOpacity>

              {/* Inline time grid */}
              {showTimeGrid && (
                <TimeGrid selected={selectedTime} onSelect={handleTimeSelect} />
              )}

              {/* Reminder row (not supported yet) */}
              {renderReminderRow()}

              {/* Repeat row (not supported yet) */}
              <View style={[s.optionRow, s.optionRowDisabled]}>
                <Repeat size={18} color={colors.textTertiary} />
                <Text style={[s.optionLabel, s.optionLabelDisabled]}>重复</Text>
                <Text style={s.optionValueGray}>暂未支持</Text>
              </View>
            </View>
          </View>
        )}

        {/* ═══════ TIME RANGE TAB ═══════ */}
        {tab === "range" && (
          <View style={s.tabContent}>
            {/* 开始 / 结束 两张卡：点开展开该端点的"日历+时间"编辑 */}
            <View style={s.rangeSummary}>
              <TouchableOpacity
                style={[s.rangeSummaryCard, editingEndpoint === "start" && s.rangeSummaryCardActive]}
                activeOpacity={0.6}
                onPress={() => setEditingEndpoint((e) => (e === "start" ? null : "start"))}
              >
                <Text style={s.rangeSummaryLabel}>开始</Text>
                <Text style={s.rangeSummaryValue}>
                  {formatMonthDay(selectedDate)} {weekdayLabel(selectedDate)}
                </Text>
                <Text style={s.rangeSummaryHint}>{isAllDay ? "全天" : selectedTime ?? "选择时间"}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  s.rangeSummaryCard,
                  editingEndpoint === "end" && s.rangeSummaryCardActive,
                  isAllDay && s.rangeSummaryCardDisabled,
                ]}
                activeOpacity={0.6}
                disabled={isAllDay}
                onPress={() => setEditingEndpoint((e) => (e === "end" ? null : "end"))}
              >
                <Text style={s.rangeSummaryLabel}>结束</Text>
                <Text style={s.rangeSummaryValue}>
                  {formatMonthDay(endDate)} {weekdayLabel(endDate)}
                </Text>
                <Text style={s.rangeSummaryHint}>{isAllDay ? "—" : endTime ?? "选择时间"}</Text>
              </TouchableOpacity>
            </View>

            {/* 跨天提示 */}
            {!isAllDay && endDate !== selectedDate && (
              <Text style={s.crossDayHint}>
                跨天：{formatMonthDay(selectedDate)} → {formatMonthDay(endDate)}
              </Text>
            )}

            {/* All-day toggle */}
            <TouchableOpacity style={s.allDayRow} onPress={toggleAllDay} activeOpacity={0.6}>
              <Text style={s.allDayLabel}>全天</Text>
              <View style={[s.toggle, isAllDay && s.toggleOn]}>
                <View style={[s.toggleKnob, isAllDay && s.toggleKnobOn]} />
              </View>
            </TouchableOpacity>

            {/* 端点编辑：日历 + 时间网格（开始/结束各自选日期与时间） */}
            {!isAllDay && editingEndpoint && (
              <View style={s.endpointEditor}>
                <MonthGrid
                  selected={editingEndpoint === "start" ? selectedDate : endDate}
                  onSelect={(d) => {
                    if (editingEndpoint === "start") {
                      setSelectedDate(d);
                      // 结束不能早于开始：把结束日一起前移
                      if (endDate < d) setEndDate(d);
                    } else {
                      // 结束日不能早于开始日：早于则夹到开始日
                      setEndDate(d < selectedDate ? selectedDate : d);
                    }
                  }}
                />
                <TimeGrid
                  selected={editingEndpoint === "start" ? selectedTime : endTime}
                  onSelect={(t) => {
                    if (editingEndpoint === "start") {
                      setSelectedTime(t);
                      if (endTime == null) setEndTime(minutesToTimeStr(timeStrToMinutes(t) + 60));
                    } else {
                      setEndTime(t);
                    }
                    setIsAllDay(false);
                  }}
                />
              </View>
            )}

            {/* 同日可视时间轴：仅同日、起止时间齐备、且未在编辑端点时显示（便捷拖动） */}
            {!isAllDay && !editingEndpoint && endDate === selectedDate && selectedTime != null && endTime != null && (
              <VisualTimeline
                startMins={timeStrToMinutes(selectedTime)}
                endMins={timeStrToMinutes(endTime)}
                onChangeRange={handleRangeChange}
              />
            )}

            {/* Reminder / repeat placeholders */}
            <View style={s.optionsSection}>
              {renderReminderRow()}
              <View style={[s.optionRow, s.optionRowDisabled]}>
                <Repeat size={18} color={colors.textTertiary} />
                <Text style={[s.optionLabel, s.optionLabelDisabled]}>重复</Text>
                <Text style={s.optionValueGray}>暂未支持</Text>
              </View>
            </View>
          </View>
        )}

        {/* Clear button */}
        {onClear && (
          <TouchableOpacity
            style={[s.clearButton, { marginBottom: chrome.overlayBottomPadding }]}
            onPress={() => { onClear(); onClose(); }}
          >
            <Text style={s.clearButtonText}>清除</Text>
          </TouchableOpacity>
        )}
        </Animated.View>
      </View>
    </Modal>
  );
}

// ═════════════════════════════════════════════════
// ─── STYLES ─────────────────────────────────────
// ═════════════════════════════════════════════════

const s = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: zLayer.picker,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.lg,
    borderTopRightRadius: borderRadius.lg,
    maxHeight: "88%",
    ...shadow.elevated,
  },

  // Top bar
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  tabRow: {
    flexDirection: "row",
    gap: spacing.xl,
  },
  tabButton: {
    paddingBottom: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabButtonActive: {
    borderBottomColor: colors.brand,
  },
  tabLabel: {
    fontSize: fontSize.lg,
    fontWeight: "500",
    color: colors.textTertiary,
  },
  tabLabelActive: {
    color: colors.text,
    fontWeight: "700",
  },

  // Tab content
  tabContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
  },

  // Month nav
  monthNav: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  monthTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.text,
  },
  yearLabel: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  monthNavRight: {
    marginLeft: "auto",
    flexDirection: "row",
    gap: spacing.md,
  },

  // Week labels
  weekRow: {
    flexDirection: "row",
    marginBottom: spacing.xs,
  },
  weekLabel: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    fontWeight: "600",
  },

  // Days grid
  daysGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  dayCell: {
    width: `${100 / 7}%` as any,
    alignItems: "center",
    paddingVertical: spacing.xs + 2,
  },
  dayCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  dayCircleSel: {
    backgroundColor: colors.brand,
  },
  dayCircleToday: {
    backgroundColor: colors.brandBg2,
  },
  dayText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  dayTextOther: {
    color: colors.textTertiary,
  },
  dayTextSel: {
    color: colors.textOnBrand,
    fontWeight: "700",
  },
  dayTextToday: {
    color: colors.brand,
    fontWeight: "700",
  },

  // Options
  optionsSection: {
    marginTop: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    overflow: "hidden",
  },
  optionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md + 2,
    gap: spacing.sm,
  },
  optionRowDisabled: {
    opacity: 0.72,
  },
  optionLabel: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
  },
  optionLabelDisabled: {
    color: colors.textTertiary,
  },
  optionValueBlue: {
    fontSize: fontSize.md,
    color: colors.brand,
    fontWeight: "600",
  },
  optionValueGray: {
    fontSize: fontSize.md,
    color: colors.textTertiary,
  },
  reminderOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  reminderChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  reminderChipActive: {
    borderColor: colors.brand,
    backgroundColor: colors.brand,
  },
  reminderChipText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  reminderChipTextActive: {
    color: "#FFFFFF",
    fontWeight: "600",
  },
  optionValueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },

  // Range summary
  rangeSummary: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
  },
  rangeSummaryCard: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  rangeSummaryLabel: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginBottom: 4,
  },
  rangeSummaryValue: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.brand,
  },
  rangeSummaryHint: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  rangeSummaryCardActive: {
    borderWidth: 1.5,
    borderColor: colors.brand,
  },
  rangeSummaryCardDisabled: {
    opacity: 0.5,
  },
  crossDayHint: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "600",
    marginTop: spacing.sm,
    marginLeft: spacing.xs,
  },
  endpointEditor: {
    marginTop: spacing.sm,
  },

  // All-day toggle
  allDayRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    marginTop: spacing.sm,
  },
  allDayLabel: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.text,
  },
  toggle: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: palette.borderSubtle,
    justifyContent: "center",
    paddingHorizontal: 2,
  },
  toggleOn: {
    backgroundColor: colors.brand,
  },
  toggleKnob: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surface,
    ...shadow.card,
  },
  toggleKnobOn: {
    alignSelf: "flex-end",
  },


  // Clear button — marginBottom 在 JSX 里通过 chrome.overlayBottomPadding 动态覆盖
  clearButton: {
    alignItems: "center",
    paddingVertical: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
  },
  clearButtonText: {
    fontSize: fontSize.md,
    color: palette.cinnabar,
    fontWeight: "600",
  },
});

// ─── Timeline sub-styles ────────────────────────

const gs = StyleSheet.create({
  // Time picker grid
  timeGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
    maxHeight: 180,
  },
  timeGridCell: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.surface,
  },
  timeGridCellSelected: {
    backgroundColor: colors.brand,
  },
  timeGridText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  timeGridTextSelected: {
    color: colors.textOnBrand,
    fontWeight: "700",
  },

  // Visual timeline
  timelineScrollView: {
    height: TIMELINE_VISIBLE_H,
    marginTop: spacing.sm,
  },
  timelineContainer: {
    position: "relative",
    minHeight: TIMELINE_TOTAL_H,
  },
  timelineRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    position: "relative",
  },
  timelineHourLabel: {
    width: 32,
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    textAlign: "right",
    marginRight: spacing.sm,
    paddingTop: 1,
  },
  timelineHourLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.borderLight,
    marginTop: 8,
  },
  timelineHalfLine: {
    position: "absolute",
    left: 40,
    right: 0,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.borderLight,
    opacity: 0.5,
  },

  // Time block
  timeBlock: {
    position: "absolute",
    left: 42,
    right: 8,
    backgroundColor: "rgba(37,99,235,0.7)",
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    justifyContent: "center",
    zIndex: 10,
  },
  timeBlockLabel: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textOnBrand,
  },
  timeBlockDuration: {
    fontSize: fontSize.xs,
    color: "rgba(255,255,255,0.8)",
    marginTop: 2,
  },

  // Handles
  handle: {
    position: "absolute",
    width: HANDLE_SIZE,
    height: HANDLE_SIZE,
    borderRadius: HANDLE_SIZE / 2,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
    left: SCREEN_WIDTH / 2 - HANDLE_SIZE / 2 - spacing.lg,
  },
  handleTop: {},
  handleBottom: {},
  handleDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brand,
  },

  // Current time line
  nowLine: {
    position: "absolute",
    left: 32,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    zIndex: 5,
  },
  nowDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: palette.cinnabar,
  },
  nowBar: {
    flex: 1,
    height: 1.5,
    backgroundColor: palette.cinnabar,
  },
});
