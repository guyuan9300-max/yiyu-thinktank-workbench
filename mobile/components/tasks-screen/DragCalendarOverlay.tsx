import { memo } from "react";
import { StyleSheet, Text, View, type GestureResponderHandlers } from "react-native";
import Animated, { useAnimatedStyle, type SharedValue } from "react-native-reanimated";
import type { TaskRecord } from "../../lib/types";

interface DragCalendarMonth {
  year: number;
  month: number;
}

interface Props {
  dragTask: TaskRecord | null;
  dragCalendarMonth: DragCalendarMonth;
  dragX: SharedValue<number>;
  dragY: SharedValue<number>;
  dragLift: SharedValue<number>;
  overlayProgress: SharedValue<number>;
  hoveredKey: SharedValue<string | null>;
  panHandlers: GestureResponderHandlers;
  formatDateKey: (date: Date) => string;
  onCellMeasured: (dateKey: string, frame: { x: number; y: number; w: number; h: number } | null) => void;
}

const GHOST_W = 248;
const GHOST_H = 50;

function buildMonthRows(year: number, month: number): { day: number | null; dateKey: string }[][] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const flat: { day: number | null; dateKey: string }[] = [];
  for (let i = 0; i < firstDay; i += 1) flat.push({ day: null, dateKey: "" });
  for (let day = 1; day <= daysInMonth; day += 1) {
    flat.push({ day, dateKey: `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}` });
  }
  while (flat.length % 7 !== 0) flat.push({ day: null, dateKey: "" });
  const rows: { day: number | null; dateKey: string }[][] = [];
  for (let i = 0; i < flat.length; i += 7) rows.push(flat.slice(i, i + 7));
  return rows;
}

/** 单格 —— 高亮完全由 hoveredKey 共享值在 UI 线程驱动,零 React 重渲染。 */
const DragDayCell = memo(function DragDayCell({
  dateKey,
  day,
  isToday,
  hoveredKey,
  onCellMeasured,
}: {
  dateKey: string;
  day: number | null;
  isToday: boolean;
  hoveredKey: SharedValue<string | null>;
  onCellMeasured: Props["onCellMeasured"];
}) {
  const circleStyle = useAnimatedStyle(() => {
    const active = hoveredKey.value === dateKey;
    return { opacity: active ? 1 : 0, transform: [{ scale: active ? 1 : 0.6 }] };
  });
  const numStyle = useAnimatedStyle(() => ({ color: hoveredKey.value === dateKey ? "#FFFFFF" : isToday ? "#5B7BFE" : "#1F2937" }));

  if (day === null) return <View style={styles.cell} />;
  return (
    <View
      style={styles.cell}
      onLayout={(event) => {
        const t = event.currentTarget as unknown as {
          measureInWindow?: (cb: (x: number, y: number, w: number, h: number) => void) => void;
        };
        t.measureInWindow?.((x, y, w, h) => {
          if (w > 0 && h > 0) onCellMeasured(dateKey, { x, y, w, h });
        });
      }}
    >
      <View style={styles.cellInner}>
        {isToday ? <View style={styles.todayRing} /> : null}
        <Animated.View style={[styles.hoverCircle, circleStyle]} />
        <Animated.Text style={[styles.dayNum, numStyle]}>{day}</Animated.Text>
      </View>
    </View>
  );
});

function DragCalendarOverlay({
  dragTask,
  dragCalendarMonth,
  dragX,
  dragY,
  dragLift,
  overlayProgress,
  hoveredKey,
  panHandlers,
  formatDateKey,
  onCellMeasured,
}: Props) {
  const todayKey = formatDateKey(new Date());
  const rows = buildMonthRows(dragCalendarMonth.year, dragCalendarMonth.month);

  const layerStyle = useAnimatedStyle(() => ({ opacity: overlayProgress.value }));
  const gridStyle = useAnimatedStyle(() => ({
    opacity: overlayProgress.value,
    transform: [{ scale: 0.98 + overlayProgress.value * 0.02 }],
  }));
  // 卡片锁在手指上方一点(手指在卡片下沿),命中的目标格在更高处 → 手不挡目标。
  const ghostStyle = useAnimatedStyle(() => ({
    opacity: dragLift.value,
    transform: [
      { translateX: dragX.value - GHOST_W / 2 },
      { translateY: dragY.value - GHOST_H + 2 },
      { scale: 0.96 + dragLift.value * 0.04 },
    ] as never,
  }));

  if (!dragTask) return null;

  return (
    <Animated.View {...panHandlers} style={[styles.layer, layerStyle]}>
      <Animated.View pointerEvents="none" style={[styles.grid, gridStyle]}>
        <Text style={styles.monthLabel}>
          {dragCalendarMonth.year}年{dragCalendarMonth.month + 1}月
        </Text>
        <View style={styles.weekRow}>
          {["日", "一", "二", "三", "四", "五", "六"].map((d) => (
            <View key={d} style={styles.weekCell}>
              <Text style={styles.weekLabel}>{d}</Text>
            </View>
          ))}
        </View>
        <View style={styles.gridBody}>
          {rows.map((row, rowIndex) => (
            <View key={rowIndex} style={styles.gridRow}>
              {row.map((c, cellIndex) => (
                <DragDayCell
                  key={cellIndex}
                  dateKey={c.dateKey}
                  day={c.day}
                  isToday={c.dateKey === todayKey}
                  hoveredKey={hoveredKey}
                  onCellMeasured={onCellMeasured}
                />
              ))}
            </View>
          ))}
        </View>
      </Animated.View>

      <Animated.View style={[styles.ghost, ghostStyle]}>
        <View style={styles.ghostCheck} />
        <Text style={styles.ghostText} numberOfLines={1}>
          {dragTask.title}
        </Text>
      </Animated.View>
    </Animated.View>
  );
}

export default memo(DragCalendarOverlay);

const styles = StyleSheet.create({
  layer: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 120,
    elevation: 120,
    backgroundColor: "rgba(249,250,251,0.985)",
  },
  grid: { flex: 1, paddingTop: 64, paddingHorizontal: 8, paddingBottom: 28 },
  monthLabel: { fontSize: 26, fontWeight: "800", color: "#1F2937", letterSpacing: -0.4, paddingLeft: 8, marginBottom: 12 },
  weekRow: { flexDirection: "row", marginBottom: 4 },
  weekCell: { flex: 1, alignItems: "center", paddingVertical: 6 },
  weekLabel: { fontSize: 13, fontWeight: "600", color: "#94A3B8" },
  gridBody: { flex: 1 },
  gridRow: { flex: 1, flexDirection: "row" },
  cell: { flex: 1, alignItems: "center", justifyContent: "flex-start", paddingTop: 8 },
  cellInner: { width: 46, height: 46, alignItems: "center", justifyContent: "center" },
  hoverCircle: { ...StyleSheet.absoluteFillObject, borderRadius: 23, backgroundColor: "#5B7BFE" },
  todayRing: { ...StyleSheet.absoluteFillObject, borderRadius: 23, borderWidth: 1.5, borderColor: "#C9D6FF" },
  dayNum: { fontSize: 17, fontWeight: "600" },
  ghost: {
    position: "absolute",
    top: 0,
    left: 0,
    width: GHOST_W,
    height: GHOST_H,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 14,
    shadowColor: "#1F2937",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.18,
    shadowRadius: 22,
    elevation: 14,
  },
  ghostCheck: { width: 20, height: 20, borderRadius: 10, borderWidth: 1.5, borderColor: "#CBD5E1" },
  ghostText: { flex: 1, fontSize: 15, fontWeight: "600", color: "#1F2937" },
});
