import { useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { ChevronDown, FilterX, Lock, Layers, FolderKanban, CalendarRange } from "lucide-react-native";
import { colors, borderRadius, spacing, fontSize, shadow } from "../lib/theme";
import {
  addDays,
  formatWeekLabelCn,
  getLocalWeekAnchorDateKey,
  parseLocalDateKey,
  weekLabelForDateKey,
} from "../lib/date";
import { useCurrentFocus } from "../lib/current-focus-store";

type PickerMode = "client" | "event_line" | "week" | null;

interface FocusBarProps {
  showAll?: boolean;
  onToggleShowAll?: () => void;
  onOpenWorkspace?: () => void;
  onOpenEventLine?: () => void;
}

const BOUNDARY_LABEL: Record<string, string> = {
  none: "暂无正式结论",
  official: "正式判断",
  pending: "待确认",
  risk: "风险",
  reminder: "提醒",
  mixed: "多层信号",
};

export default function FocusBar({
  showAll = false,
  onToggleShowAll,
  onOpenWorkspace,
  onOpenEventLine,
}: FocusBarProps) {
  const {
    focus,
    clients,
    eventLines,
    setManualClientFocus,
    setManualClientEventLineFocus,
    setCurrentFocusWeek,
    clearStoredCurrentFocus,
  } = useCurrentFocus();
  const [pickerMode, setPickerMode] = useState<PickerMode>(null);

  const eventLineOptions = useMemo(() => {
    if (!focus.clientId) {
      return [];
    }
    return eventLines.filter((item) => item.primaryClientId === focus.clientId);
  }, [eventLines, focus.clientId]);

  const generatedWeekOptions = useMemo(() => {
    const anchor = parseLocalDateKey(focus.weekAnchorDate);
    return Array.from({ length: 7 }, (_, index) => {
      const delta = index - 3;
      const nextAnchor = getLocalWeekAnchorDateKey(addDays(anchor, delta * 7));
      return {
        weekAnchorDate: nextAnchor,
        weekLabel: formatWeekLabelCn(weekLabelForDateKey(nextAnchor)),
      };
    });
  }, [focus.weekAnchorDate]);

  const boundaryLabel = BOUNDARY_LABEL[focus.boundaryState] ?? BOUNDARY_LABEL.none;
  const canLockCurrent = focus.lockMode === "browse" && Boolean(focus.clientId);

  const handleLockCurrent = () => {
    if (!focus.clientId) {
      return;
    }
    if (focus.eventLineId) {
      setManualClientEventLineFocus(focus.clientId, focus.eventLineId);
      return;
    }
    setManualClientFocus(focus.clientId);
  };

  const weekDisplayLabel = formatWeekLabelCn(focus.weekLabel);

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <TouchableOpacity style={styles.pill} activeOpacity={0.78} onPress={() => setPickerMode("client")}>
          <Text style={styles.pillLabel}>客户</Text>
          <Text style={styles.pillValue} numberOfLines={1}>
            {focus.clientName || "全部客户"}
          </Text>
          <ChevronDown size={14} color={colors.brand} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.pill, !focus.clientId && styles.pillDisabled]}
          activeOpacity={focus.clientId ? 0.78 : 1}
          onPress={() => focus.clientId && setPickerMode("event_line")}
        >
          <Text style={styles.pillLabel}>事件线</Text>
          <Text style={styles.pillValue} numberOfLines={1}>
            {focus.eventLineName || "未锁定事件线"}
          </Text>
          <ChevronDown size={14} color={focus.clientId ? colors.brand : colors.textTertiary} />
        </TouchableOpacity>
      </View>
      <View style={styles.row}>
        <TouchableOpacity style={[styles.pill, styles.weekPill]} activeOpacity={0.78} onPress={() => setPickerMode("week")}>
          <CalendarRange size={14} color={colors.brand} />
          <Text style={styles.weekText}>{weekDisplayLabel}</Text>
        </TouchableOpacity>
        <View style={styles.boundaryPill}>
          <Layers size={14} color={colors.textSecondary} />
          <Text style={styles.boundaryText} numberOfLines={1}>{boundaryLabel}</Text>
        </View>
      </View>
      <View style={styles.actionRow}>
        {canLockCurrent ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={handleLockCurrent}>
            <Lock size={14} color={colors.brand} />
            <Text style={styles.actionText}>锁定当前</Text>
          </TouchableOpacity>
        ) : null}
        {(focus.clientId || focus.eventLineId) ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={clearStoredCurrentFocus}>
            <FilterX size={14} color={colors.textSecondary} />
            <Text style={[styles.actionText, { color: colors.textSecondary }]}>清空</Text>
          </TouchableOpacity>
        ) : null}
        {focus.clientId && onOpenWorkspace ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onOpenWorkspace}>
            <FolderKanban size={14} color={colors.brand} />
            <Text style={styles.actionText}>工作台</Text>
          </TouchableOpacity>
        ) : null}
        {focus.eventLineId && onOpenEventLine ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onOpenEventLine}>
            <Layers size={14} color={colors.brand} />
            <Text style={styles.actionText}>事件线详情</Text>
          </TouchableOpacity>
        ) : null}
        {focus.lockMode !== "browse" && onToggleShowAll ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onToggleShowAll}>
            <Text style={styles.actionText}>{showAll ? "恢复聚焦" : "显示全部"}</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <Modal visible={pickerMode !== null} animationType="fade" transparent onRequestClose={() => setPickerMode(null)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setPickerMode(null)}>
          <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
            {pickerMode === "client" ? (
              <>
                <Text style={styles.sheetTitle}>选择客户</Text>
                <ScrollView style={styles.sheetList}>
                  <TouchableOpacity style={styles.sheetRow} onPress={() => { clearStoredCurrentFocus(); setPickerMode(null); }}>
                    <Text style={styles.sheetRowTitle}>全部客户</Text>
                  </TouchableOpacity>
                  {clients.map((client) => (
                    <TouchableOpacity
                      key={client.id}
                      style={styles.sheetRow}
                      onPress={() => {
                        setManualClientFocus(client.id);
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{client.name}</Text>
                      {client.alias ? <Text style={styles.sheetRowMeta}>{client.alias}</Text> : null}
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
            {pickerMode === "event_line" ? (
              <>
                <Text style={styles.sheetTitle}>选择事件线</Text>
                <ScrollView style={styles.sheetList}>
                  <TouchableOpacity
                    style={styles.sheetRow}
                    onPress={() => {
                      if (focus.clientId) {
                        setManualClientFocus(focus.clientId);
                      }
                      setPickerMode(null);
                    }}
                  >
                    <Text style={styles.sheetRowTitle}>仅锁客户</Text>
                  </TouchableOpacity>
                  {eventLineOptions.map((eventLine) => (
                    <TouchableOpacity
                      key={eventLine.id}
                      style={styles.sheetRow}
                      onPress={() => {
                        if (focus.clientId) {
                          setManualClientEventLineFocus(focus.clientId, eventLine.id);
                        }
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{eventLine.name}</Text>
                      <Text style={styles.sheetRowMeta}>{eventLine.stage || eventLine.status || "事件线"}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
            {pickerMode === "week" ? (
              <>
                <Text style={styles.sheetTitle}>切换当前周</Text>
                <ScrollView style={styles.sheetList}>
                  {generatedWeekOptions.map((item) => (
                    <TouchableOpacity
                      key={item.weekAnchorDate}
                      style={styles.sheetRow}
                      onPress={() => {
                        setCurrentFocusWeek(item.weekAnchorDate);
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{item.weekAnchorDate}</Text>
                      <Text style={styles.sheetRowMeta}>{item.weekLabel || formatWeekLabelCn(focus.weekLabel)}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  pill: {
    flex: 1,
    minHeight: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  pillDisabled: {
    opacity: 0.5,
  },
  pillLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  pillValue: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  weekPill: {
    flex: 0.95,
    justifyContent: "center",
  },
  weekText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "800",
  },
  boundaryPill: {
    flex: 1.05,
    minHeight: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.brandBg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.brandRing,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  boundaryText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  actionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
  },
  actionText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.26)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: "72%",
  },
  sheetTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacing.md,
  },
  sheetList: {
    flexGrow: 0,
  },
  sheetRow: {
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  sheetRowTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "700",
  },
  sheetRowMeta: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
