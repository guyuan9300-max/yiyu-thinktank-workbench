import type { GestureResponderEvent } from "react-native";
import { Check, Inbox } from "lucide-react-native";
import { Pressable, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import { palette } from "../../lib/theme";
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
  calendarDays: readonly CalendarDay[];
  selectedDateKey: string;
  todayKey: string;
  tasksByDate: ReadonlyMap<string, readonly TaskRecord[]>;
  draggingTask: TaskRecord | null;
  hoveredDropKey: string | null;
  selectedTasks: readonly TaskRecord[];
  highlightedTaskIds?: ReadonlySet<string>;
  refreshing: boolean;
  bottomPadding: number;
  registerDropZone: (key: string, ref: View | null) => void;
  onSelectDate: (dateKey: string) => void;
  onRefresh: () => void;
  onTaskPress: (task: TaskRecord) => void;
  onEventLinePress?: (task: TaskRecord) => void;
  onTaskTouchStart: (task: TaskRecord, event: GestureResponderEvent) => void;
  onTaskTouchMove: (event: GestureResponderEvent) => void;
  onTaskTouchEnd: () => void;
  shouldSetTaskResponder: (task: TaskRecord) => boolean;
  gridPanHandlers?: any;
}

export default function MonthView({
  styles,
  weekdayLabels,
  calendarDays,
  selectedDateKey,
  todayKey,
  tasksByDate,
  draggingTask,
  hoveredDropKey,
  selectedTasks,
  highlightedTaskIds,
  refreshing,
  bottomPadding,
  registerDropZone,
  onSelectDate,
  onRefresh,
  onTaskPress,
  onEventLinePress,
  onTaskTouchStart,
  onTaskTouchMove,
  onTaskTouchEnd,
  shouldSetTaskResponder,
  gridPanHandlers,
}: Props) {
  return (
    <>
      <View {...(gridPanHandlers ?? {})}>
      <View style={styles.weekRow}>
        {weekdayLabels.map((label) => (
          <View key={label} style={styles.weekCell}>
            <Text style={styles.weekLabel}>{label}</Text>
          </View>
        ))}
      </View>

      <View style={styles.calendarGrid}>
        {Array.from({ length: Math.ceil(calendarDays.length / 7) }, (_, weekIndex) => (
          <View key={`week-${weekIndex}`} style={styles.weekGridRow}>
            {calendarDays.slice(weekIndex * 7, weekIndex * 7 + 7).map((item, index) => {
          const isSelected = item.dateKey === selectedDateKey;
          const isToday = item.dateKey === todayKey;
          const hasTasks = tasksByDate.has(item.dateKey);
          const isDragHover = Boolean(draggingTask) && hoveredDropKey === item.dateKey;
          return (
            <TouchableOpacity
              key={`${item.dateKey}-${index}`}
              ref={(ref) => {
                if (ref && draggingTask) {
                  registerDropZone(item.dateKey, ref as any);
                }
              }}
              style={styles.dayCell}
              onPress={() => {
                if (!draggingTask) {
                  onSelectDate(item.dateKey);
                }
              }}
              activeOpacity={0.6}
            >
              <View
                style={[
                  styles.dayCircle,
                  isSelected && styles.dayCircleSelected,
                  isToday && !isSelected && styles.dayCircleToday,
                  isDragHover && styles.dayCircleDragHover,
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    !item.isCurrentMonth && styles.dayTextOther,
                    isSelected && styles.dayTextSelected,
                    isToday && !isSelected && styles.dayTextToday,
                    isDragHover && styles.dayTextDragHover,
                  ]}
                >
                  {item.day}
                </Text>
              </View>
              {hasTasks ? <View style={[styles.taskDot, isSelected && styles.taskDotSelected]} /> : null}
            </TouchableOpacity>
          );
            })}
          </View>
        ))}
      </View>
      </View>

      <ScrollView
        style={styles.taskSection}
        contentContainerStyle={[styles.taskSectionContent, { paddingBottom: bottomPadding }]}
        scrollEnabled={!draggingTask}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={palette.inkBlack} />}
      >
        {selectedTasks.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>待办任务</Text>
            {selectedTasks.map((task) => {
              const isDragging = draggingTask?.id === task.id;
              return (
                <Pressable
                  key={task.id}
                  style={[
                    styles.taskCard,
                    isDragging && styles.taskCardDragging,
                    highlightedTaskIds?.has(task.id) && styles.focusMatchedCard,
                  ]}
                  onPress={() => onTaskPress(task)}
                  onPressIn={(event) => onTaskTouchStart(task, event)}
                  onMoveShouldSetResponder={() => shouldSetTaskResponder(task)}
                  onResponderMove={onTaskTouchMove}
                  onResponderRelease={onTaskTouchEnd}
                  onResponderTerminate={onTaskTouchEnd}
                >
                  <View style={styles.taskRow}>
                    <View style={[styles.taskCheckCircle, task.progressStatus === "done" && styles.taskCheckCircleDone]}>
                      {task.progressStatus === "done" ? <Check size={12} strokeWidth={3} color={palette.paperRice} /> : null}
                    </View>
                    <View style={styles.taskContent}>
                      <Text style={styles.taskTitle} numberOfLines={1}>
                        {task.title}
                      </Text>
                      <TaskSyncBadge task={task} compact />
                      {getTaskScheduleTimeLabel(task) ? (
                        <Text style={styles.taskTime}>{getTaskScheduleTimeLabel(task)}</Text>
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
                    </View>
                  </View>
                </Pressable>
              );
            })}
          </>
        ) : (
          <View style={styles.emptyState}>
            <Inbox size={40} color={palette.textTertiary} />
            <Text style={styles.emptyText}>这一天没有安排任务</Text>
          </View>
        )}
        {draggingTask ? <Text style={styles.dragHint}>拖到上方日历格子中，改变任务日期</Text> : null}
      </ScrollView>
    </>
  );
}
