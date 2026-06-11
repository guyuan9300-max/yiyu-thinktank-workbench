import type { ReactNode } from "react";
import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { CalendarClock } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, shadow } from "../lib/theme";
import type { WeekSignalSnapshot } from "../lib/types";

interface WeekSignalCardProps {
  weekLabel: string;
  snapshot: WeekSignalSnapshot;
}

export default function WeekSignalCard({ weekLabel, snapshot }: WeekSignalCardProps) {
  const [open, setOpen] = useState(false);
  const hasSignals = snapshot.pendingJudgments.length > 0 || snapshot.riskSignals.length > 0;
  return (
    <>
      <TouchableOpacity style={styles.card} activeOpacity={0.78} onPress={() => setOpen(true)}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>周信号</Text>
            <Text style={styles.subtitle}>{weekLabel}</Text>
          </View>
          <CalendarClock size={18} color={colors.brand} />
        </View>
        <View style={styles.metricRow}>
          <Metric label="任务" value={String(snapshot.facts.totalCount)} />
          <Metric label="完成" value={String(snapshot.facts.completedCount)} />
          <Metric label="逾期" value={String(snapshot.facts.overdueCount)} />
          <Metric label="待复盘" value={String(snapshot.facts.awaitingReviewCount)} />
        </View>
        {/* P0-4: 有信号才显示行内文案；没信号则给一行引导，避免空卡片 */}
        {snapshot.pendingJudgments[0] ? <Text style={styles.inlineText}>待确认：{snapshot.pendingJudgments[0]}</Text> : null}
        {snapshot.riskSignals[0] ? <Text style={styles.inlineText}>风险：{snapshot.riskSignals[0]}</Text> : null}
        {!hasSignals ? (
          <Text style={styles.inlineHint}>
            本周尚未生成判断/风险信号 · 桌面端「数据中心 → 周复盘」可生成
          </Text>
        ) : null}
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
            <Text style={styles.sheetTitle}>Week Signal</Text>
            <ScrollView contentContainerStyle={styles.sheetContent}>
              <Block title="本周事实">
                <Text style={styles.bullet}>• 本周任务数：{snapshot.facts.totalCount}</Text>
                <Text style={styles.bullet}>• 完成数：{snapshot.facts.completedCount}</Text>
                <Text style={styles.bullet}>• 改期/更新数：{snapshot.facts.rescheduledCount}</Text>
                <Text style={styles.bullet}>• 未安排时间数：{snapshot.facts.unscheduledCount}</Text>
                <Text style={styles.bullet}>• 逾期数：{snapshot.facts.overdueCount}</Text>
                <Text style={styles.bullet}>• 待复盘数：{snapshot.facts.awaitingReviewCount}</Text>
              </Block>
              <Block title="待确认判断">
                {snapshot.pendingJudgments.length > 0 ? snapshot.pendingJudgments.map((item, index) => (
                  <Text key={`pending-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>暂无 · 桌面端「数据中心 → 周复盘」生成后可同步过来</Text>}
              </Block>
              <Block title="风险信号">
                {snapshot.riskSignals.length > 0 ? snapshot.riskSignals.map((item, index) => (
                  <Text key={`risk-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>暂无 · 桌面端复盘后会自动生成本周风险卡</Text>}
              </Block>
              <Block title="建议动作">
                {snapshot.suggestedActions.length > 0 ? snapshot.suggestedActions.map((item, index) => (
                  <Text key={`action-${index}`} style={styles.bullet}>• {item}</Text>
                )) : <Text style={styles.empty}>当前仅提供事实层，不伪造建议</Text>}
              </Block>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metric: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  metricValue: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    color: colors.text,
  },
  metricLabel: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  inlineText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  inlineHint: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    lineHeight: 18,
    fontStyle: "italic",
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.22)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  sheet: {
    borderRadius: borderRadius.xl,
    backgroundColor: colors.surface,
    maxHeight: "80%",
    padding: spacing.lg,
    ...shadow.softCard,
  },
  sheetTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacing.md,
  },
  sheetContent: {
    gap: spacing.md,
  },
  block: {
    gap: spacing.sm,
  },
  blockTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  bullet: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
