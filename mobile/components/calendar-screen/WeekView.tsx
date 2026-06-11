import type { GestureResponderEvent } from "react-native";
import { ChevronDown } from "lucide-react-native";
import { Pressable, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { colors, palette, iconStroke } from "../../lib/theme";
import { getTaskScheduleTimeLabel } from "../../lib/task-time";
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
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={palette.inkBlack} />}
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
                          {
                            backgroundColor:
                              task.progressStatus === "done"
                                ? palette.bambooGreen
                                : palette.inkBronze,
                          },
                        ]}
                      />
                      <Text style={styles.weekTaskTitle} numberOfLines={1}>{task.title}</Text>
                      <TaskSyncBadge task={task} compact />
                      {getTaskScheduleTimeLabel(task) ? (
                        <Text style={styles.weekTaskTime}>{getTaskScheduleTimeLabel(task)}</Text>
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
                  <ChevronDown size={12} strokeWidth={iconStroke} color={palette.textSecondary} />
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
