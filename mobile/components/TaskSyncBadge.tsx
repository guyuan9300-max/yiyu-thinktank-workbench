import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { borderRadius, colors, fontSize, spacing, palette, typography, iconStroke } from "../lib/theme";
import { buildTaskSyncIndicator } from "../lib/task-sync-presentation";
import type { TaskRecord } from "../lib/types";

interface TaskSyncBadgeProps {
  readonly task: Pick<TaskRecord, "remoteState" | "syncReasonCode">;
  readonly compact?: boolean;
  readonly style?: StyleProp<ViewStyle>;
}

const TONE_STYLES = {
  info: {
    backgroundColor: palette.paperMoon,
    borderColor: palette.borderSubtle,
    textColor: palette.inkBlack,
  },
  warning: {
    backgroundColor: palette.paperMoon,
    borderColor: palette.borderSubtle,
    textColor: palette.cinnabar,
  },
  danger: {
    backgroundColor: palette.cinnabarTint,
    borderColor: palette.borderSubtle,
    textColor: colors.error,
  },
} as const;

export default function TaskSyncBadge({ task, compact = false, style }: TaskSyncBadgeProps) {
  const indicator = buildTaskSyncIndicator(task);
  if (!indicator) {
    return null;
  }
  const tone = TONE_STYLES[indicator.tone];
  return (
    <View
      style={[
        styles.badge,
        compact ? styles.badgeCompact : null,
        { backgroundColor: tone.backgroundColor, borderColor: tone.borderColor },
        style,
      ]}
    >
      <Text
        style={[
          styles.badgeText,
          compact ? styles.badgeTextCompact : null,
          { color: tone.textColor },
        ]}
        numberOfLines={1}
      >
        {indicator.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: borderRadius.full,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  badgeCompact: {
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 3,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  badgeTextCompact: {
    fontSize: 10,
  },
});
