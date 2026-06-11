import { useMemo, useState, type ReactNode } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Paperclip, Mic, CircleAlert, ChevronRight } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, shadow } from "../lib/theme";
import { formatTaskDisplayDate, getTaskCalendarDateKey } from "../lib/task-time";
import type { ClientSummaryRecord, EventLineRecord, TaskRecord, WorkspaceLiteItem } from "../lib/types";

interface EventLineDrawerProps {
  visible: boolean;
  eventLine: EventLineRecord | null;
  tasks: readonly TaskRecord[];
  meetingHighlights?: readonly WorkspaceLiteItem[];
  clients?: readonly ClientSummaryRecord[];
  onClose: () => void;
  onOpenWorkspace?: () => void;
  onTaskPress?: (task: TaskRecord) => void;
  onTransferToClient?: (clientId: string) => Promise<void> | void;
  isTransferringClient?: boolean;
}

export default function EventLineDrawer({
  visible,
  eventLine,
  tasks,
  meetingHighlights = [],
  clients = [],
  onClose,
  onOpenWorkspace,
  onTaskPress,
  onTransferToClient,
  isTransferringClient = false,
}: EventLineDrawerProps) {
  const [showClientPicker, setShowClientPicker] = useState(false);
  const relatedTasks = eventLine ? tasks.filter((task) => task.eventLineId === eventLine.id) : [];
  const recentTasks = relatedTasks.slice(0, 5);
  const attachments = relatedTasks.flatMap((task) => task.attachments ?? []);
  const recentAttachments = attachments.slice(0, 4);
  const recentAudio = recentAttachments.filter((item) => item.mimeType?.startsWith("audio/")).slice(0, 3);
  const sortedClients = useMemo(
    () => [...clients].sort((left, right) => left.name.localeCompare(right.name, "zh-CN")),
    [clients],
  );
  const transferButtonLabel = eventLine?.primaryClientId ? "更改归属" : "转入客户";

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          <View style={styles.handle} />
          {eventLine ? (
            <ScrollView contentContainerStyle={styles.content}>
              <View style={styles.headerRow}>
                <View style={styles.headerCopy}>
                  <Text style={styles.title}>{eventLine.name}</Text>
                  <Text style={styles.subtitle}>
                    {eventLine.primaryClientName || "未关联客户"}
                    {eventLine.stage ? ` · ${eventLine.stage}` : ""}
                    {eventLine.status ? ` · ${eventLine.status}` : ""}
                  </Text>
                </View>
                <View style={styles.headerActions}>
                  {onTransferToClient ? (
                    <TouchableOpacity
                      style={styles.secondaryActionButton}
                      onPress={() => setShowClientPicker(true)}
                      disabled={isTransferringClient}
                    >
                      {isTransferringClient ? (
                        <ActivityIndicator size="small" color={colors.brand} />
                      ) : (
                        <Text style={styles.secondaryActionButtonText}>{transferButtonLabel}</Text>
                      )}
                    </TouchableOpacity>
                  ) : null}
                  {onOpenWorkspace && eventLine.primaryClientId ? (
                    <TouchableOpacity style={styles.workspaceButton} onPress={onOpenWorkspace}>
                      <Text style={styles.workspaceButtonText}>工作台</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>

              {onTransferToClient ? (
                <View style={styles.tipCard}>
                  <Text style={styles.tipText}>迁移归属会同步这条事件线下任务与资料的客户分类。</Text>
                </View>
              ) : null}

              <View style={styles.card}>
                <Section title="摘要" content={eventLine.summary || "暂无事件线摘要"} />
                <Section title="当前卡点" content={eventLine.currentBlocker || "暂无明确卡点"} />
                <Section title="最近判断" content={eventLine.recentDecision || "暂无最近判断"} />
                <Section title="下一步" content={eventLine.nextStep || "暂无下一步动作"} />
              </View>

              <View style={styles.metricRow}>
                <Metric icon={<CircleAlert size={14} color={colors.brand} />} label="未完成任务" value={String(relatedTasks.filter((task) => task.progressStatus !== "done").length)} />
                <Metric icon={<Paperclip size={14} color={colors.brand} />} label="最近附件" value={String(recentAttachments.length)} />
                <Metric icon={<Mic size={14} color={colors.brand} />} label="最近录音" value={String(recentAudio.length)} />
              </View>

              {meetingHighlights.length > 0 ? (
                <View style={styles.sectionBlock}>
                  <Text style={styles.sectionTitle}>最近会议片段</Text>
                  {meetingHighlights.slice(0, 2).map((item) => (
                    <View key={item.id} style={styles.listRow}>
                      <Text style={styles.listRowTitle}>{item.title}</Text>
                      {item.summary ? <Text style={styles.listRowSummary}>{item.summary}</Text> : null}
                    </View>
                  ))}
                </View>
              ) : null}

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionTitle}>最近任务</Text>
                {recentTasks.length > 0 ? recentTasks.map((task) => (
                  <TouchableOpacity
                    key={task.id}
                    style={styles.taskRow}
                    onPress={() => onTaskPress?.(task)}
                    activeOpacity={0.78}
                  >
                    <View style={styles.taskRowCopy}>
                      <Text style={styles.taskTitle}>{task.title}</Text>
                      <Text style={styles.taskMeta}>
                        {task.clientName || eventLine.primaryClientName || "客户"}
                        {getTaskCalendarDateKey(task) ? ` · ${formatTaskDisplayDate(task)}` : ""}
                      </Text>
                    </View>
                    <ChevronRight size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                )) : (
                  <Text style={styles.emptyText}>这条事件线下还没有最近任务。</Text>
                )}
              </View>
            </ScrollView>
          ) : null}
        </Pressable>
      </Pressable>
      <Modal
        visible={showClientPicker && Boolean(eventLine)}
        transparent
        animationType="fade"
        onRequestClose={() => setShowClientPicker(false)}
      >
        <Pressable style={styles.pickerOverlay} onPress={() => setShowClientPicker(false)}>
          <Pressable style={styles.pickerCard} onPress={(event) => event.stopPropagation()}>
            <Text style={styles.pickerTitle}>{transferButtonLabel}</Text>
            <Text style={styles.pickerHint}>选择后会把这条事件线及其关联任务、资料一起归到目标客户下。</Text>
            <ScrollView style={styles.pickerList} showsVerticalScrollIndicator={false}>
              {sortedClients.map((client) => {
                const isActive = client.id === eventLine?.primaryClientId;
                return (
                  <TouchableOpacity
                    key={client.id}
                    style={[styles.pickerItem, isActive && styles.pickerItemActive]}
                    activeOpacity={0.82}
                    disabled={isActive || isTransferringClient}
                    onPress={async () => {
                      if (!onTransferToClient || isActive) {
                        return;
                      }
                      await onTransferToClient(client.id);
                      setShowClientPicker(false);
                    }}
                  >
                    <Text style={[styles.pickerItemText, isActive && styles.pickerItemTextActive]}>
                      {client.name}
                    </Text>
                    {isActive ? <Text style={styles.pickerItemMeta}>当前归属</Text> : null}
                  </TouchableOpacity>
                );
              })}
              {sortedClients.length === 0 ? (
                <Text style={styles.emptyText}>还没有可选客户。</Text>
              ) : null}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </Modal>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <View style={styles.sectionItem}>
      <Text style={styles.sectionLabel}>{title}</Text>
      <Text style={styles.sectionContent}>{content}</Text>
    </View>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <View style={styles.metricCard}>
      <View style={styles.metricIcon}>{icon}</View>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.24)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    minHeight: "58%",
    maxHeight: "86%",
    ...shadow.softCard,
  },
  handle: {
    alignSelf: "center",
    width: 42,
    height: 5,
    borderRadius: 999,
    backgroundColor: colors.border,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  headerCopy: {
    flex: 1,
  },
  headerActions: {
    alignItems: "flex-end",
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  secondaryActionButton: {
    minWidth: 84,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryActionButtonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  workspaceButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.brandBg,
    alignSelf: "flex-start",
  },
  workspaceButtonText: {
    color: colors.brand,
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  tipCard: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.brandBg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  tipText: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  card: {
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
    gap: spacing.sm,
  },
  sectionItem: {
    gap: spacing.xs,
  },
  sectionLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  sectionContent: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.text,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metricCard: {
    flex: 1,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  metricIcon: {
    marginBottom: spacing.xs,
  },
  metricValue: {
    fontSize: fontSize.xl,
    color: colors.text,
    fontWeight: "800",
  },
  metricLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  sectionBlock: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  listRow: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
  },
  listRowTitle: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  listRowSummary: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  taskRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
  },
  taskRowCopy: {
    flex: 1,
  },
  taskTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  taskMeta: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  pickerOverlay: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.24)",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  pickerCard: {
    maxHeight: "70%",
    borderRadius: borderRadius.xl,
    backgroundColor: colors.surface,
    padding: spacing.lg,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  pickerTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
  },
  pickerHint: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  pickerList: {
    marginTop: spacing.sm,
  },
  pickerItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
  },
  pickerItemActive: {
    backgroundColor: colors.brandBg,
    borderColor: colors.brand,
  },
  pickerItemText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  pickerItemTextActive: {
    color: colors.brand,
  },
  pickerItemMeta: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
});
