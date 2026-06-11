import { useEffect, useState, type ReactNode } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { AlertTriangle, CheckCircle2, Clock3, FileText, FolderOpenDot, Layers } from "lucide-react-native";
import {
  colors,
  borderRadius,
  fontSize,
  spacing,
  shadow,
  palette,
  typography,
  iconStroke,
} from "../lib/theme";
import { useClientIntel } from "../lib/client-intel-store";
import { fetchClientNarrative } from "../lib/api";
import type { BoundaryCard, ClientNarrativeRecord, NarrativeConfidence } from "../lib/types";

interface WorkspaceLiteSheetProps {
  visible: boolean;
  clientId: string | null;
  clientName?: string | null;
  onClose: () => void;
  onTaskPress?: (taskId: string) => void;
}

// 4 类边界卡片 —— 单色 hairline 卡片 + 左侧 3px 状态竖条做区分（去掉彩色填充底）
const TONE_MAP = {
  official: {
    bg: palette.paperSmoke,
    border: palette.borderSubtle,
    accent: palette.bambooGreen,
    icon: <CheckCircle2 size={14} strokeWidth={iconStroke} color={palette.bambooGreen} />,
  },
  pending: {
    bg: palette.paperSmoke,
    border: palette.borderSubtle,
    accent: palette.inkBronze,
    icon: <Clock3 size={14} strokeWidth={iconStroke} color={palette.inkBronze} />,
  },
  risk: {
    bg: palette.paperSmoke,
    border: palette.borderSubtle,
    accent: palette.cinnabar,
    icon: <AlertTriangle size={14} strokeWidth={iconStroke} color={palette.cinnabar} />,
  },
  reminder: {
    bg: palette.paperSmoke,
    border: palette.borderSubtle,
    accent: palette.textTertiary,
    icon: <Layers size={14} strokeWidth={iconStroke} color={palette.textTertiary} />,
  },
} as const;

function formatMetaDate(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function sourceTypeLabel(sourceType: BoundaryCard["sourceType"]): string {
  switch (sourceType) {
    case "meeting":
      return "会议";
    case "document":
      return "文档";
    case "ai":
      return "AI";
    case "manual":
      return "人工";
    default:
      return "混合";
  }
}

function snapshotStatusText(snapshot: ReturnType<typeof useClientIntel>["snapshot"]): string {
  if (!snapshot) {
    return "正在加载客户工作台";
  }
  return "客户资料与任务信息";
}

const DIMENSION_LABEL: Record<string, string> = {
  who: "他是谁",
  what: "在做什么",
  why: "为什么找我们",
  status: "现在到哪一步",
  blocker: "卡点在哪",
  next: "下一步该怎么走",
};

const CONFIDENCE_TONE: Record<NarrativeConfidence, { label: string; color: string; bg: string }> = {
  high: { label: "把握高", color: palette.bambooGreen, bg: "rgba(16,185,129,0.10)" },
  medium: { label: "中等", color: palette.inkBronze, bg: "rgba(245,158,11,0.10)" },
  low: { label: "把握低", color: palette.textTertiary, bg: "rgba(107,114,128,0.10)" },
};

export default function WorkspaceLiteSheet({
  visible,
  clientId,
  clientName,
  onClose,
  onTaskPress,
}: WorkspaceLiteSheetProps) {
  const { snapshot, isLoading, isRefreshing, refresh, error } = useClientIntel(clientId);
  const [narrative, setNarrative] = useState<ClientNarrativeRecord | null>(null);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);

  // P0-3: 拉客户 6 维度叙事（桌面端"战略陪伴"同源；如果没生成过，dimensions 全是空 narrative）
  useEffect(() => {
    if (!visible || !clientId) {
      setNarrative(null);
      setNarrativeError(null);
      return;
    }
    let cancelled = false;
    fetchClientNarrative(clientId)
      .then((record) => {
        if (!cancelled) {
          setNarrative(record);
          setNarrativeError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setNarrative(null);
          setNarrativeError(err instanceof Error ? err.message : "叙事拉取失败");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [visible, clientId]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.title}>{snapshot?.clientName || clientName || "客户工作台"}</Text>
              <Text style={styles.subtitle}>{snapshotStatusText(snapshot)}</Text>
            </View>
            <TouchableOpacity style={styles.refreshButton} onPress={() => void refresh()}>
              <Text style={styles.refreshText}>{isRefreshing ? "刷新中" : "刷新"}</Text>
            </TouchableOpacity>
          </View>

          {!snapshot && isLoading ? (
            <View style={styles.loadingState}>
              <ActivityIndicator size="large" color={colors.brand} />
              <Text style={styles.loadingText}>正在加载工作台…</Text>
            </View>
          ) : (
            <ScrollView contentContainerStyle={styles.content}>
              {error ? (
                <Text style={styles.errorText}>
                  {snapshot ? `刷新失败，正在显示旧缓存：${error}` : error}
                </Text>
              ) : null}

              <Section title="Boundary">
                {snapshot?.boundaryCards.map((card) => (
                  <BoundaryCardView key={card.kind} card={card} />
                ))}
              </Section>

              <Section title="工作台">
                <SimpleList title="目标" items={snapshot?.goals ?? []} emptyText="暂无目标" />
                <SimpleList title="最近会议" items={snapshot?.latestMeetings ?? []} emptyText="暂无会议" />
                <SimpleList title="资料" items={snapshot?.recentDocuments ?? []} emptyText="暂无资料" />
                <InfoRow label="知识状态" value={snapshot?.knowledgeStatus || "暂无知识状态"} icon={<FolderOpenDot size={14} color={colors.brand} />} />
                <SimpleList title="开放问题" items={snapshot?.openQuestions ?? []} emptyText="暂无开放问题" />
                <SimpleList title="相关任务" items={(snapshot?.relatedTasks ?? []).map((item) => ({
                  id: item.id,
                  title: item.title,
                  summary: [item.eventLineName, item.status].filter(Boolean).join(" · "),
                }))} emptyText="暂无相关任务" onItemPress={onTaskPress} />
                <StringList title="下一步" items={snapshot?.nextActions ?? []} emptyText="暂无下一步动作" />
              </Section>

              <Section title="Cockpit">
                <InfoRow label="Headline" value={snapshot?.headline || "暂无 headline"} icon={<Layers size={14} color={colors.brand} />} />
                <StringList title="健康信号" items={snapshot?.health ?? []} emptyText="暂无健康信号" />
                <StringList title="两周变化" items={snapshot?.twoWeekChanges ?? []} emptyText="暂无变化摘要" />
                <StringList title="待确认决策" items={snapshot?.pendingDecisions ?? []} emptyText="暂无待确认决策" />
                <StringList title="待补材料" items={snapshot?.pendingMaterials ?? []} emptyText="暂无待补材料" />
              </Section>

              <NarrativeSection narrative={narrative} error={narrativeError} />
            </ScrollView>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function BoundaryCardView({ card }: { card: BoundaryCard }) {
  const tone = TONE_MAP[card.kind];
  const updatedAt = formatMetaDate(card.updatedAt);
  return (
    <View
      style={[
        styles.boundaryCard,
        { backgroundColor: tone.bg, borderColor: tone.border, borderLeftColor: tone.accent },
      ]}
    >
      <View style={styles.boundaryHeader}>
        <View style={styles.boundaryTitleWrap}>
          {tone.icon}
          <Text style={styles.boundaryTitle}>{card.title}</Text>
        </View>
        <Text style={styles.boundaryMeta}>{card.evidenceCount == null ? "—" : `${card.evidenceCount} 条`}</Text>
      </View>
      <Text style={styles.boundarySummary}>{card.summary}</Text>
      <View style={styles.boundaryFooter}>
        <Text style={styles.boundaryFooterText}>来源：{sourceTypeLabel(card.sourceType)}</Text>
        <Text style={styles.boundaryFooterText}>{updatedAt ? `更新：${updatedAt}` : "更新：暂无"}</Text>
      </View>
    </View>
  );
}

function InfoRow({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <View style={styles.infoRow}>
      <View style={styles.infoLabel}>
        {icon}
        <Text style={styles.infoLabelText}>{label}</Text>
      </View>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

function StringList({ title, items, emptyText }: { title: string; items: readonly string[]; emptyText: string }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {items.length > 0 ? items.map((item, index) => (
        <Text key={`${title}-${index}`} style={styles.bulletText}>• {item}</Text>
      )) : <Text style={styles.emptyText}>{emptyText}</Text>}
    </View>
  );
}

function NarrativeSection({
  narrative,
  error,
}: {
  narrative: ClientNarrativeRecord | null;
  error: string | null;
}) {
  if (error && !narrative) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>叙事 6 维度</Text>
        <Text style={styles.errorText}>叙事拉取失败：{error}</Text>
      </View>
    );
  }
  if (!narrative) {
    return null;
  }
  const hasAnyNarrative = narrative.dimensions.some((d) => (d.narrative || "").trim().length > 0);
  return (
    <View style={styles.section}>
      <View style={styles.narrativeHeader}>
        <Text style={styles.sectionTitle}>叙事 6 维度</Text>
        {narrative.overallConfidence != null ? (
          <Text style={styles.narrativeMeta}>
            把握度 {(narrative.overallConfidence * 100).toFixed(0)}%
            {narrative.openClarificationsCount ? ` · 待澄清 ${narrative.openClarificationsCount}` : ""}
          </Text>
        ) : null}
      </View>
      {!hasAnyNarrative ? (
        <View style={styles.narrativeEmptyHint}>
          <Text style={styles.narrativeEmptyHintText}>
            这位客户的 6 维度叙事还没生成过。请在桌面端"战略陪伴"页面点一次"生成叙事"，回来即可看到。
          </Text>
        </View>
      ) : (
        narrative.dimensions.map((dim) => {
          const tone = CONFIDENCE_TONE[dim.confidence] ?? CONFIDENCE_TONE.low;
          const label = DIMENSION_LABEL[dim.dimension] || dim.dimension;
          const body = (dim.narrative || "").trim();
          return (
            <View key={dim.dimension} style={styles.narrativeDim}>
              <View style={styles.narrativeDimHeader}>
                <Text style={styles.narrativeDimTitle}>{label}</Text>
                <View style={[styles.narrativeBadge, { backgroundColor: tone.bg }]}>
                  <Text style={[styles.narrativeBadgeText, { color: tone.color }]}>{tone.label}</Text>
                </View>
              </View>
              {body ? (
                <Text style={styles.narrativeBody}>{body}</Text>
              ) : (
                <Text style={styles.narrativeBodyMuted}>⏳ AI 还没讲这一段</Text>
              )}
              {dim.openClarifications && dim.openClarifications.length > 0 ? (
                <Text style={styles.narrativeClarif}>
                  待澄清：{dim.openClarifications[0]}
                </Text>
              ) : null}
            </View>
          );
        })
      )}
    </View>
  );
}

function SimpleList({
  title,
  items,
  emptyText,
  onItemPress,
}: {
  title: string;
  items: ReadonlyArray<{ id: string; title: string; summary?: string | null }>;
  emptyText: string;
  onItemPress?: (itemId: string) => void;
}) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {items.length > 0 ? items.map((item) => (
        <TouchableOpacity
          key={item.id}
          style={styles.listRow}
          activeOpacity={onItemPress ? 0.78 : 1}
          disabled={!onItemPress}
          onPress={() => onItemPress?.(item.id)}
        >
          <Text style={styles.listTitle}>{item.title}</Text>
          {item.summary ? <Text style={styles.listSummary}>{item.summary}</Text> : null}
        </TouchableOpacity>
      )) : <Text style={styles.emptyText}>{emptyText}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(31,42,55,0.24)", // 统一 backdrop
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: palette.paperRice, // 与页面 canvas 一致
    borderTopLeftRadius: borderRadius.lg, // 14
    borderTopRightRadius: borderRadius.lg,
    minHeight: "60%",
    maxHeight: "88%",
  },
  handle: {
    alignSelf: "center",
    width: 36,
    height: 4,
    borderRadius: 999,
    backgroundColor: palette.borderDivider,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headerCopy: { flex: 1 },
  title: {
    ...typography.titlePage, // 22/600/30
    color: palette.inkBlack,
  },
  subtitle: {
    marginTop: 4,
    ...typography.caption,
    color: palette.textTertiary,
  },
  refreshButton: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    backgroundColor: "transparent",
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: borderRadius.full,
  },
  refreshText: {
    ...typography.label,
    color: palette.inkBlack,
    fontWeight: "600",
  },
  loadingState: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
  },
  loadingText: {
    marginTop: spacing.sm,
    ...typography.caption,
    color: palette.textTertiary,
  },
  errorText: {
    ...typography.caption,
    color: palette.cinnabar,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.lg,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
  },
  // BoundaryCard —— 卡片 hairline，左侧 3px 状态色竖条
  boundaryCard: {
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderLeftWidth: 3,
    padding: spacing.md,
    gap: spacing.xs,
  },
  boundaryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  boundaryTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flex: 1,
  },
  boundaryTitle: {
    ...typography.body,
    color: palette.inkBlack,
    fontWeight: "600",
  },
  boundaryMeta: {
    ...typography.mono,
    color: palette.inkBronze,
  },
  boundarySummary: {
    ...typography.caption,
    color: palette.inkBlack,
    lineHeight: 20,
  },
  boundaryFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  boundaryFooterText: {
    ...typography.label,
    color: palette.textTertiary,
  },
  block: {
    gap: spacing.sm,
  },
  blockTitle: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
  },
  infoRow: {
    borderRadius: borderRadius.md,
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    padding: spacing.md,
    gap: spacing.sm,
  },
  infoLabel: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  infoLabelText: {
    ...typography.label,
    color: palette.textTertiary,
  },
  infoValue: {
    ...typography.body,
    color: palette.inkBlack,
  },
  // 列表行：hairline 分隔代替灰底块
  listRow: {
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: palette.borderSubtle,
  },
  listTitle: {
    ...typography.body,
    color: palette.inkBlack,
    fontWeight: "500",
  },
  listSummary: {
    marginTop: 2,
    ...typography.caption,
    color: palette.textTertiary,
  },
  bulletText: {
    ...typography.body,
    color: palette.inkBlack,
    lineHeight: 22,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  // ─── Narrative 6 维度 ───
  narrativeHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  narrativeMeta: {
    ...typography.label,
    color: palette.textTertiary,
  },
  narrativeEmptyHint: {
    backgroundColor: palette.paperMoon,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  narrativeEmptyHintText: {
    ...typography.caption,
    color: palette.textSecondary,
    lineHeight: 20,
  },
  narrativeDim: {
    backgroundColor: palette.paperSmoke,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    padding: spacing.md,
    gap: spacing.xs,
  },
  narrativeDimHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  narrativeDimTitle: {
    ...typography.body,
    color: palette.inkBlack,
    fontWeight: "600",
    flex: 1,
  },
  narrativeBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
  },
  narrativeBadgeText: {
    ...typography.label,
    fontWeight: "700",
  },
  narrativeBody: {
    ...typography.body,
    color: palette.inkBlack,
    lineHeight: 22,
  },
  narrativeBodyMuted: {
    ...typography.caption,
    color: palette.textTertiary,
    fontStyle: "italic",
  },
  narrativeClarif: {
    marginTop: 4,
    ...typography.caption,
    color: palette.inkBronze,
    lineHeight: 18,
  },
});
