import { useCallback, useState } from "react";
import {
  Animated,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import * as Haptics from "expo-haptics";
import { Mic, Plus, Sparkles } from "lucide-react-native";
import {
  borderRadius,
  iconStroke,
  palette,
  presets,
  spacing,
  typography,
} from "../lib/theme";
import { zLayer } from "../lib/app-chrome";

interface SuperFABProps {
  readonly onCreateTask: () => void;
  readonly onSmartInput: () => void;
  readonly onRecordNote: () => void;
}

const FAB_SIZE = 56;

export default function SuperFAB({ onCreateTask, onSmartInput, onRecordNote }: SuperFABProps) {
  const [menuVisible, setMenuVisible] = useState(false);

  const openMenu = useCallback(() => {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setMenuVisible(true);
  }, []);

  const runAction = useCallback((action: () => void) => {
    setMenuVisible(false);
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    action();
  }, []);

  return (
    <View style={s.container} pointerEvents="box-none">
      <TouchableOpacity style={s.fabTouchTarget} activeOpacity={0.85} onPress={openMenu}>
        <Animated.View style={s.fab}>
          <Plus size={28} strokeWidth={iconStroke + 0.25} color="#FFFFFF" />
        </Animated.View>
      </TouchableOpacity>

      <Modal
        visible={menuVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setMenuVisible(false)}
      >
        <Pressable style={s.menuOverlay} onPress={() => setMenuVisible(false)}>
          <Pressable style={s.actionSheet} onPress={(event) => event.stopPropagation()}>
            <View style={s.sheetHandle} />
            <Text style={s.sheetTitle}>快速操作</Text>

            {/* 三个 action 全部去掉彩色 iconBg，行高 64，hairline 分隔 */}
            <TouchableOpacity
              style={s.actionRow}
              activeOpacity={0.6}
              onPress={() => runAction(onCreateTask)}
            >
              <Plus size={22} strokeWidth={iconStroke} color={palette.textTertiary} />
              <View style={s.actionCopy}>
                <Text style={s.actionTitle}>新建任务</Text>
              </View>
            </TouchableOpacity>

            <View style={presets.dividerHairline} />

            <TouchableOpacity
              style={s.actionRow}
              activeOpacity={0.6}
              onPress={() => runAction(onSmartInput)}
            >
              <Sparkles size={22} strokeWidth={iconStroke} color={palette.textTertiary} />
              <View style={s.actionCopy}>
                <Text style={s.actionTitle}>智能输入</Text>
              </View>
            </TouchableOpacity>

            <View style={presets.dividerHairline} />

            <TouchableOpacity
              style={s.actionRow}
              activeOpacity={0.6}
              onPress={() => runAction(onRecordNote)}
            >
              <Mic size={22} strokeWidth={iconStroke} color={palette.textTertiary} />
              <View style={s.actionCopy}>
                <Text style={s.actionTitle}>现场记录</Text>
              </View>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    zIndex: zLayer.fab,
  },
  fabTouchTarget: {
    width: FAB_SIZE + 12,
    height: FAB_SIZE + 12,
    borderRadius: (FAB_SIZE + 12) / 2,
    alignItems: "center",
    justifyContent: "center",
  },
  // FAB —— airy blue 主色填 + 白色描边 + airy 蓝雾 shadow
  fab: {
    width: FAB_SIZE,
    height: FAB_SIZE,
    borderRadius: FAB_SIZE / 2,
    backgroundColor: palette.airyBlue,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: "#FFFFFF",
    shadowColor: palette.airyBlue,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.36,
    shadowRadius: 18,
    elevation: 10,
  },
  menuOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(15,23,42,0.32)",
  },
  actionSheet: {
    marginHorizontal: 16,
    marginBottom: 20,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
    borderRadius: borderRadius.xl, // 24 大圆角（桌面 rounded-3xl）
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.16,
    shadowRadius: 40,
    elevation: 12,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.borderDivider,
    marginBottom: 14,
  },
  sheetTitle: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
    marginBottom: 4,
    paddingHorizontal: spacing.xs,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    height: 64,
    paddingHorizontal: spacing.xs,
  },
  actionCopy: {
    flex: 1,
  },
  actionTitle: {
    ...typography.bodyLarge, // 16/400/24
    color: palette.inkBlack,
    fontWeight: "500",
  },
});
