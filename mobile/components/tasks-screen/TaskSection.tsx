import { Fragment, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import type { TaskRecord } from "../../lib/types";
import { borderRadius, palette } from "../../lib/theme";

interface TaskSectionProps {
  title: string;
  hint?: string;
  tasks: readonly TaskRecord[];
  renderTask: (task: TaskRecord) => ReactNode;
}

/**
 * 分组清单(滴答风)的区块容器:安静的小标题 + 计数 →
 * 一张白卡承载该组所有行,行间用左缩进发丝分隔线分开(不再每条任务套边框)。
 */
export default function TaskSection({ title, hint, tasks, renderTask }: TaskSectionProps) {
  if (tasks.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.count}>{tasks.length}</Text>
      </View>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      <View style={styles.listCard}>
        {tasks.map((task, index) => (
          <Fragment key={task.id}>
            {index > 0 ? <View style={styles.divider} /> : null}
            {renderTask(task)}
          </Fragment>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: 16, marginTop: 22 },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10, paddingLeft: 4 },
  title: { fontSize: 14, fontWeight: "700", color: palette.textSecondary, letterSpacing: 0.2 },
  count: { fontSize: 13, fontWeight: "700", color: palette.textMuted },
  hint: { fontSize: 12, lineHeight: 17, color: palette.textTertiary, marginBottom: 10, paddingLeft: 4 },
  listCard: {
    backgroundColor: palette.surfaceCard,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    overflow: "hidden",
  },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: palette.borderSubtle, marginLeft: 51 },
});
