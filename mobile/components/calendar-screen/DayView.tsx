import type { RefObject } from "react";
import { Pressable, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { palette } from "../../lib/theme";
import { getTaskScheduleDateTime, getTaskScheduleTimeLabel } from "../../lib/task-time";
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
  onTaskTouchMove: (event: any) => void;
  onTaskTouchEnd: () => void;
  shouldSetTaskResponder: (task: TaskRecord) => boolean;
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

// 时间轴 1 分钟 = 1px（小时行高 60px）。计算任务在【某一展示日】内的可见时段，
// 跨天任务按当前日裁剪：开始日从开始时刻到 24:00，中间日占满，结束日 0:00 到结束时刻。
interface DaySegment {
  top: number;
  height: number;
  continuesBefore: boolean; // 由前一天延续而来
  continuesAfter: boolean; // 延续到次日
}

function getTaskDaySegment(task: TaskRecord, dayKey: string): DaySegment | null {
  const start = getTaskScheduleDateTime(task)?.value;
  if (!start) return null;
  const dur = task.durationMinutes ?? 0;
  const end = dur > 0 ? new Date(start.getTime() + dur * 60_000) : new Date(start.getTime());
  const [y, m, d] = dayKey.split("-").map(Number);
  const dayStart = new Date(y, m - 1, d).getTime();
  const dayEnd = new Date(y, m - 1, d + 1).getTime();
  const segStart = Math.max(start.getTime(), dayStart);
  const segEnd = Math.min(end.getTime(), dayEnd);
  return {
    top: (segStart - dayStart) / 60_000,
    height: Math.max((segEnd - segStart) / 60_000, 28),
    continuesBefore: start.getTime() < dayStart,
    continuesAfter: end.getTime() > dayEnd,
  };
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
  onTaskTouchMove,
  onTaskTouchEnd,
  shouldSetTaskResponder,
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
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={palette.inkBlack} />}
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

        {/* 小时网格+日程块同处一个相对定位容器，块 top 相对网格原点，不受上方全天区高度影响 */}
        <View style={{ position: "relative" }}>
        {Array.from({ length: 24 }, (_, index) => index).map((hour) => {
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
                delayLongPress={500}
              >
                <Text style={styles.hourLabel}>{String(hour).padStart(2, "0")}</Text>
                <View style={[styles.hourLine, isDragHover && styles.hourLineDragHover]} />
                {isDragHover ? <Text style={styles.hourDropHint}>松手安排到{String(hour).padStart(2, "0")}:00</Text> : null}
              </TouchableOpacity>
            </View>
          );
        })}

        {dayScheduledTasks.map((task) => {
          const seg = getTaskDaySegment(task, selectedDateKey);
          if (!seg) {
            return null;
          }
          const { top, height, continuesBefore, continuesAfter } = seg;
          const isCrossDay = continuesBefore || continuesAfter;
          const isDone = task.progressStatus === "done";
          const isDragging = draggingTask?.id === task.id;
          const isTall = height > 50;
          // 续接日显示"续"，开始日显示开始时刻；延续到次日加"›次日"
          const timeText = continuesBefore
            ? "续"
            : `${getTaskScheduleTimeLabel(task) ?? ""}${continuesAfter ? " ›次日" : ""}`;

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
              <Pressable
                style={styles.timelineTaskTouchable}
                onPress={() => onTaskPress(task)}
                onPressIn={(event) => onTaskTouchStart(task, event)}
                onPressOut={onTaskTouchEnd}
                onMoveShouldSetResponder={() => shouldSetTaskResponder(task)}
                onResponderMove={onTaskTouchMove}
                onResponderRelease={onTaskTouchEnd}
                onResponderTerminate={onTaskTouchEnd}
              >
                <View style={styles.timelineTaskHeader}>
                  <View style={[styles.timelineTaskCheck, isDone && styles.timelineTaskCheckDone]} />
                  <Text style={styles.timelineTaskTime}>{timeText}</Text>
                  <TaskSyncBadge task={task} compact />
                </View>
                <Text style={[styles.timelineTaskTitle, isDone && styles.timelineTaskTitleDone]} numberOfLines={isTall ? 3 : 1}>
                  {task.title}
                </Text>
              </Pressable>
              {isTall && !isDragging && !isCrossDay ? (
                <View
                  style={styles.timelineResizeHandle}
                  onStartShouldSetResponder={() => false}
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
        </View>
      </ScrollView>
    </>
  );
}
