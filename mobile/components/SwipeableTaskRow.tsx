import { useRef, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
// 关键:Swipeable 内的可点击按钮必须用 gesture-handler 的 TouchableOpacity,
// 否则在新架构下手势系统会拦截触摸,RN 原生 TouchableOpacity 的 onPress 永不触发。
import ReanimatedSwipeable, { type SwipeableMethods } from "react-native-gesture-handler/ReanimatedSwipeable";
import { TouchableOpacity } from "react-native-gesture-handler";
import { Check, CalendarClock, Trash2 } from "lucide-react-native";
import * as Haptics from "expo-haptics";
import { palette } from "../lib/theme";

interface Props {
  children: ReactNode;
  isDone?: boolean;
  enabled?: boolean;
  /** 右滑(露出左侧)= 完成 */
  onComplete?: () => void;
  /** 左滑(露出右侧)= 改期 */
  onReschedule?: () => void;
  /** 左滑(露出右侧)= 删除 */
  onDelete?: () => void;
}

// 对标滴答清单:任务行右滑=完成、左滑=改期/删除。基于 gesture-handler ReanimatedSwipeable(UI 线程)。
export default function SwipeableTaskRow({
  children,
  isDone = false,
  enabled = true,
  onComplete,
  onReschedule,
  onDelete,
}: Props) {
  const ref = useRef<SwipeableMethods>(null);
  const close = () => ref.current?.close();
  const completedRef = useRef(false);

  if (!enabled || (!onComplete && !onReschedule && !onDelete)) {
    return <>{children}</>;
  }

  const canComplete = Boolean(onComplete) && !isDone;

  const renderLeftActions = canComplete
    ? () => (
        <TouchableOpacity
          style={[s.action, s.complete]}
          activeOpacity={0.85}
          onPress={() => {
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            onComplete?.();
            close();
          }}
        >
          <Check size={22} strokeWidth={2.6} color={palette.paperRice} />
          <Text style={s.actionText}>完成</Text>
        </TouchableOpacity>
      )
    : undefined;

  const renderRightActions = (onReschedule || onDelete)
    ? () => (
        <View style={s.rightRow}>
          {onReschedule ? (
            <TouchableOpacity
              style={[s.action, s.reschedule]}
              activeOpacity={0.85}
              onPress={() => { void Haptics.selectionAsync(); onReschedule?.(); close(); }}
            >
              <CalendarClock size={20} strokeWidth={2} color={palette.paperRice} />
              <Text style={s.actionText}>改期</Text>
            </TouchableOpacity>
          ) : null}
          {onDelete ? (
            <TouchableOpacity
              style={[s.action, s.delete]}
              activeOpacity={0.85}
              onPress={() => { void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning); onDelete?.(); close(); }}
            >
              <Trash2 size={20} strokeWidth={2} color={palette.paperRice} />
              <Text style={s.actionText}>删除</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      )
    : undefined;

  return (
    <ReanimatedSwipeable
      ref={ref}
      friction={2}
      leftThreshold={72}
      rightThreshold={56}
      overshootFriction={8}
      renderLeftActions={renderLeftActions}
      renderRightActions={renderRightActions}
      onSwipeableWillOpen={(direction) => {
        // 右滑到位 = 直接完成(滴答式),不必再点按钮。
        // RNGH 的 direction 是「行移动方向」:右滑(露出左侧「完成」)= "right";
        // 左滑(露出右侧「改期/删除」)= "left",此时不可自动完成,要让面板正常展开。
        if (direction === "right" && canComplete && !completedRef.current) {
          completedRef.current = true;
          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          onComplete?.();
          requestAnimationFrame(() => close());
        }
      }}
      onSwipeableClose={() => { completedRef.current = false; }}
    >
      {children}
    </ReanimatedSwipeable>
  );
}

const s = StyleSheet.create({
  action: { width: 84, alignItems: "center", justifyContent: "center", gap: 4 },
  actionText: { color: palette.paperRice, fontSize: 13, fontWeight: "700" },
  complete: { backgroundColor: palette.bambooGreen },
  rightRow: { flexDirection: "row" },
  reschedule: { backgroundColor: palette.inkBlue },
  delete: { backgroundColor: palette.cinnabar },
});
