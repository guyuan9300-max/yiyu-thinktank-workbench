import { StyleSheet, Text, View } from "react-native";
import { AlertTriangle, BrainCircuit, Link2, Sparkles } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, palette, typography, iconStroke } from "../lib/theme";
import type { TaskUnderstandingCardModel } from "../lib/task-understanding";

interface UnderstandingCardProps {
  model: TaskUnderstandingCardModel;
}

const TONE_STYLES = {
  ready: {
    backgroundColor: "rgba(92,122,92,0.08)",
    borderColor: palette.bambooGreen,
    icon: <Sparkles size={16} color={palette.bambooGreen} />,
    badgeBg: "rgba(92,122,92,0.08)",
    badgeText: palette.bambooGreen,
  },
  weak_link: {
    backgroundColor: palette.paperMoon,
    borderColor: palette.borderSubtle,
    icon: <Link2 size={16} color={palette.reedYellow} />,
    badgeBg: palette.borderSubtle,
    badgeText: palette.cinnabar,
  },
  insufficient_context: {
    backgroundColor: palette.paperMoon,
    borderColor: palette.textTertiary,
    icon: <AlertTriangle size={16} color={palette.textSecondary} />,
    badgeBg: palette.borderSubtle,
    badgeText: palette.textSecondary,
  },
} as const;

export default function UnderstandingCard({ model }: UnderstandingCardProps) {
  const tone = TONE_STYLES[model.tone];

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: tone.backgroundColor,
          borderColor: tone.borderColor,
        },
      ]}
    >
      <View style={styles.header}>
        <View style={styles.headerTitleWrap}>
          {tone.icon}
          <Text style={styles.title}>{model.title}</Text>
        </View>
        <View style={[styles.badge, { backgroundColor: tone.badgeBg }]}>
          <Text style={[styles.badgeText, { color: tone.badgeText }]}>{model.stateLabel}</Text>
        </View>
      </View>

      <Text style={styles.subtitle}>{model.subtitle}</Text>

      {model.evidence.length > 0 ? (
        <View style={styles.evidenceBlock}>
          <View style={styles.evidenceHeader}>
            <BrainCircuit size={14} color={colors.textSecondary} />
            <Text style={styles.evidenceTitle}>相关信息</Text>
          </View>
          <View style={styles.evidenceList}>
            {model.evidence.map((item) => (
              <View key={item} style={styles.evidenceChip}>
                <Text style={styles.evidenceChipText}>{item}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {model.sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <Text style={styles.sectionTitle}>{section.title}</Text>
          <Text style={styles.sectionContent}>{section.content || "暂无可靠洞察"}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginLeft: 38,
    marginBottom: 20,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  headerTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  title: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  badge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  evidenceBlock: {
    gap: spacing.xs,
  },
  evidenceHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  evidenceTitle: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  evidenceList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  evidenceChip: {
    borderRadius: borderRadius.full,
    backgroundColor: "rgba(255,255,255,0.72)",
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  evidenceChipText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  section: {
    gap: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.xs,
    fontWeight: "800",
    color: colors.textSecondary,
  },
  sectionContent: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },
});
