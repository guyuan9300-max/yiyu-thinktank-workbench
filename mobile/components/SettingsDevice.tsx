/**
 * SettingsDevice.tsx —— 手机端"设备级偏好"设置页。
 *
 * 按"手机只配置移动场景独有项"原则，集中三件事：
 *   - 流量保护：仅 WiFi 下载附件/录音
 *   - 勿扰时段：本地通知静默时段
 *   - 主题：跟随系统 / 浅色 / 深色（主题真正切换在后续 PR）
 *
 * 全部走 AsyncStorage，不与桌面端互通。
 */

import { useEffect, useState } from "react";
import {
  Alert,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
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
  borderRadius,
  iconStroke,
} from "../lib/theme";
import {
  loadDevicePreferences,
  setDoNotDisturbEnabled,
  setDoNotDisturbEnd,
  setDoNotDisturbStart,
  setThemeMode,
  setWifiOnlyDownload,
  type DevicePreferences,
  type ThemeMode,
} from "../lib/device-preferences";

interface SettingsDeviceProps {
  readonly onClose: () => void;
}

const THEME_OPTIONS: ReadonlyArray<{ key: ThemeMode; label: string; description: string }> = [
  { key: "system", label: "跟随系统", description: "随 iOS / Android 系统设置切换" },
  { key: "light", label: "浅色", description: "强制浅色界面" },
  { key: "dark", label: "深色", description: "强制深色界面（视觉效果稍后上线）" },
];

function isTimeFormat(value: string): boolean {
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}

export default function SettingsDevice({ onClose }: SettingsDeviceProps) {
  const chrome = useAppChromeInsets();
  const [prefs, setPrefs] = useState<DevicePreferences | null>(null);
  const [dndStartDraft, setDndStartDraft] = useState("22:00");
  const [dndEndDraft, setDndEndDraft] = useState("07:00");

  useEffect(() => {
    void loadDevicePreferences().then((loaded) => {
      setPrefs(loaded);
      setDndStartDraft(loaded.doNotDisturbStart);
      setDndEndDraft(loaded.doNotDisturbEnd);
    });
  }, []);

  if (!prefs) {
    return (
      <SafeAreaView style={styles.container} edges={["left", "right"]}>
        <View style={[presets.pageHeader, { paddingTop: chrome.headerTopPadding }]}>
          <TouchableOpacity onPress={onClose} style={styles.backButton}>
            <ArrowLeft size={22} color={palette.inkBlack} strokeWidth={iconStroke} />
          </TouchableOpacity>
          <Text style={presets.pageHeaderTitle}>偏好设置</Text>
          <View style={styles.headerSpacer} />
        </View>
      </SafeAreaView>
    );
  }

  const toggleWifi = async (next: boolean) => {
    setPrefs({ ...prefs, wifiOnlyDownload: next });
    try {
      await setWifiOnlyDownload(next);
    } catch (error) {
      setPrefs({ ...prefs, wifiOnlyDownload: !next });
      Alert.alert("保存失败", error instanceof Error ? error.message : "请稍后重试。");
    }
  };

  const toggleDnd = async (next: boolean) => {
    setPrefs({ ...prefs, doNotDisturbEnabled: next });
    try {
      await setDoNotDisturbEnabled(next);
    } catch (error) {
      setPrefs({ ...prefs, doNotDisturbEnabled: !next });
      Alert.alert("保存失败", error instanceof Error ? error.message : "请稍后重试。");
    }
  };

  const commitDndStart = async () => {
    if (!isTimeFormat(dndStartDraft)) {
      Alert.alert("时段格式有误", "请填写 HH:MM，例如 22:00。");
      setDndStartDraft(prefs.doNotDisturbStart);
      return;
    }
    try {
      await setDoNotDisturbStart(dndStartDraft);
      setPrefs({ ...prefs, doNotDisturbStart: dndStartDraft });
    } catch (error) {
      setDndStartDraft(prefs.doNotDisturbStart);
      Alert.alert("保存失败", error instanceof Error ? error.message : "请稍后重试。");
    }
  };

  const commitDndEnd = async () => {
    if (!isTimeFormat(dndEndDraft)) {
      Alert.alert("时段格式有误", "请填写 HH:MM，例如 07:00。");
      setDndEndDraft(prefs.doNotDisturbEnd);
      return;
    }
    try {
      await setDoNotDisturbEnd(dndEndDraft);
      setPrefs({ ...prefs, doNotDisturbEnd: dndEndDraft });
    } catch (error) {
      setDndEndDraft(prefs.doNotDisturbEnd);
      Alert.alert("保存失败", error instanceof Error ? error.message : "请稍后重试。");
    }
  };

  const pickTheme = async (mode: ThemeMode) => {
    const previous = prefs.themeMode;
    setPrefs({ ...prefs, themeMode: mode });
    try {
      await setThemeMode(mode);
    } catch (error) {
      setPrefs({ ...prefs, themeMode: previous });
      Alert.alert("保存失败", error instanceof Error ? error.message : "请稍后重试。");
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[presets.pageHeader, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={palette.inkBlack} strokeWidth={iconStroke} />
        </TouchableOpacity>
        <Text style={presets.pageHeaderTitle}>偏好设置</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        {/* 流量保护 */}
        <Text style={presets.sectionTitle}>流量保护</Text>
        <View style={[presets.cardPaper, styles.card]}>
          <View style={styles.switchRow}>
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>仅 WiFi 下载附件/录音</Text>
              <Text style={styles.rowSub}>移动数据下不自动拉取大文件</Text>
            </View>
            <Switch
              value={prefs.wifiOnlyDownload}
              onValueChange={toggleWifi}
              trackColor={{ false: palette.borderSubtle, true: palette.inkBlack }}
              thumbColor={palette.paperRice}
              ios_backgroundColor={palette.borderSubtle}
            />
          </View>
        </View>

        {/* 勿扰时段 */}
        <Text style={presets.sectionTitle}>勿扰时段</Text>
        <View style={[presets.cardPaper, styles.card]}>
          <View style={styles.switchRow}>
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>开启勿扰时段</Text>
              <Text style={styles.rowSub}>时段内手机端不弹本地通知</Text>
            </View>
            <Switch
              value={prefs.doNotDisturbEnabled}
              onValueChange={toggleDnd}
              trackColor={{ false: palette.borderSubtle, true: palette.inkBlack }}
              thumbColor={palette.paperRice}
              ios_backgroundColor={palette.borderSubtle}
            />
          </View>
          {prefs.doNotDisturbEnabled ? (
            <>
              <View style={styles.cardInnerDivider} />
              <View style={styles.timeRow}>
                <View style={styles.timeColumn}>
                  <Text style={styles.timeLabel}>开始</Text>
                  <TextInput
                    style={styles.timeInput}
                    value={dndStartDraft}
                    onChangeText={setDndStartDraft}
                    onBlur={commitDndStart}
                    keyboardType="numbers-and-punctuation"
                    placeholder="22:00"
                    placeholderTextColor={palette.textTertiary}
                    maxLength={5}
                  />
                </View>
                <Text style={styles.timeDash}>→</Text>
                <View style={styles.timeColumn}>
                  <Text style={styles.timeLabel}>结束</Text>
                  <TextInput
                    style={styles.timeInput}
                    value={dndEndDraft}
                    onChangeText={setDndEndDraft}
                    onBlur={commitDndEnd}
                    keyboardType="numbers-and-punctuation"
                    placeholder="07:00"
                    placeholderTextColor={palette.textTertiary}
                    maxLength={5}
                  />
                </View>
              </View>
            </>
          ) : null}
        </View>

        {/* 主题 */}
        <Text style={presets.sectionTitle}>主题</Text>
        <View style={[presets.cardPaper, styles.cardThemeList]}>
          {THEME_OPTIONS.map((option, index) => {
            const selected = prefs.themeMode === option.key;
            return (
              <View key={option.key}>
                <TouchableOpacity
                  style={styles.themeRow}
                  onPress={() => pickTheme(option.key)}
                  activeOpacity={0.6}
                >
                  <View style={styles.rowText}>
                    <Text style={styles.rowTitle}>{option.label}</Text>
                    <Text style={styles.rowSub}>{option.description}</Text>
                  </View>
                  <View style={[styles.radio, selected && styles.radioSelected]}>
                    {selected ? <View style={styles.radioInner} /> : null}
                  </View>
                </TouchableOpacity>
                {index < THEME_OPTIONS.length - 1 ? (
                  <View style={styles.themeDivider} />
                ) : null}
              </View>
            );
          })}
        </View>

        <Text style={presets.hintText}>
          这些是仅本机生效的偏好。账号、组织、AI 模型、任务规则等业务配置请在电脑端统一管理。
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  headerSpacer: { width: 36 },
  content: { flex: 1, paddingHorizontal: layout.screenPaddingH },
  card: {
    padding: spacing.lg, // 16
  },
  cardThemeList: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 0,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 48,
  },
  rowText: { flex: 1, marginRight: spacing.md },
  rowTitle: {
    ...typography.bodyLarge, // 16/400/24
    color: palette.inkBlack,
    fontWeight: "500",
  },
  rowSub: {
    ...typography.caption,
    color: palette.textTertiary,
    marginTop: 2,
  },
  cardInnerDivider: {
    height: 0.5,
    backgroundColor: palette.borderDivider,
    marginVertical: spacing.md,
  },
  themeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    height: layout.rowHeightEntry, // 64
  },
  themeDivider: {
    height: 0.5,
    backgroundColor: palette.borderDivider,
    marginLeft: 0,
  },
  timeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  timeColumn: { flex: 1 },
  timeLabel: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
    marginBottom: 6,
  },
  timeInput: {
    backgroundColor: palette.paperMoon, // 月白偏黄
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    ...typography.bodyLarge,
    color: palette.inkBlack,
    textAlign: "center",
    fontVariant: ["tabular-nums"],
  },
  timeDash: {
    fontSize: 18,
    color: palette.textTertiary,
    alignSelf: "flex-end",
    paddingBottom: spacing.md,
  },
  radio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: palette.borderSubtle,
    alignItems: "center",
    justifyContent: "center",
  },
  radioSelected: { borderColor: palette.inkBlack },
  radioInner: { width: 12, height: 12, borderRadius: 6, backgroundColor: palette.inkBlack },
});
