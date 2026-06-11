import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import {
  colors,
  spacing,
  layout,
  palette,
  typography,
  presets,
  iconStroke,
} from "../lib/theme";
import type { SessionUser } from "../lib/types";

interface SettingsAccountProps {
  readonly onClose: () => void;
  readonly user: SessionUser | null;
}

// 账号信息只读展示页（按"手机端不做组织/系统配置"原则）。
// 设计语言：东方商务沉稳 —— 大字阶 + hairline 分隔 + 无 shadow。
export default function SettingsAccount({ onClose, user }: SettingsAccountProps) {
  const chrome = useAppChromeInsets();

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[presets.pageHeader, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={palette.inkBlack} strokeWidth={iconStroke} />
        </TouchableOpacity>
        <Text style={presets.pageHeaderTitle}>账号设置</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        {/* 当前账号 —— "翻公文"式：姓名作为 titleCard 17pt 主信息，下方 caption 串起其他字段 */}
        <Text style={presets.sectionTitle}>当前账号</Text>
        <View style={[presets.cardPaper, styles.card]}>
          <Text style={styles.identityName}>{user?.fullName ?? "未登录"}</Text>
          <Text style={styles.identitySub}>
            {[user?.organizationName, user?.departmentName].filter(Boolean).join(" · ") ||
              user?.title ||
              "未关联组织"}
          </Text>

          <View style={styles.fieldDivider} />

          <View style={styles.fieldRow}>
            <Text style={styles.fieldLabel}>邮箱</Text>
            <Text style={styles.fieldValue}>{user?.email ?? "—"}</Text>
          </View>
          {user?.organizationId ? (
            <>
              <View style={styles.fieldDivider} />
              <View style={styles.fieldRow}>
                <Text style={styles.fieldLabel}>组织编号</Text>
                <Text style={[styles.fieldValue, styles.fieldValueMono]} numberOfLines={1}>
                  {user.organizationId}
                </Text>
              </View>
            </>
          ) : null}
        </View>

        <Text style={presets.hintText}>
          姓名、企业、部门信息由电脑端管理员维护后多端同步。如需修改，请前往电脑端"系统设置 → 组织搭建"。
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background, // 宣纸米
  },
  backButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerSpacer: { width: 36 },
  content: {
    flex: 1,
    paddingHorizontal: layout.screenPaddingH, // 20
  },
  card: {
    padding: spacing.xl, // 20，比常规 16 略宽，让"姓名大字"有呼吸
  },
  identityName: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
  },
  identitySub: {
    ...typography.caption, // 13/400/18
    color: palette.textTertiary,
    marginTop: 4, // 紧贴
  },
  fieldDivider: {
    height: 0.5,
    backgroundColor: palette.borderDivider,
    marginVertical: spacing.lg, // 16，比 hairline marginLeft 52 这种内容行更宽的留白
  },
  fieldRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  fieldLabel: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
  },
  fieldValue: {
    ...typography.body, // 15/400/22
    color: palette.inkBlack,
    flexShrink: 1,
    textAlign: "right",
  },
  fieldValueMono: {
    fontVariant: ["tabular-nums"],
    fontSize: 13,
  },
});
