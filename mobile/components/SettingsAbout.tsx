/**
 * SettingsAbout.tsx —— "关于"页。
 *
 * 视觉：东方商务沉稳。Hero 区不再用卡片，而是大字阶直陈应用名/版本，
 * 像翻开一本书的版权页。
 */

import { useState } from "react";
import {
  Alert,
  Linking,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Constants from "expo-constants";
import { ArrowLeft, ChevronRight, FileText, MessageCircle, Shield, Trash2 } from "lucide-react-native";
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
import {
  FEEDBACK_EMAIL,
  LEGAL_VERSION,
  PRIVACY_POLICY_TEXT,
  USER_AGREEMENT_TEXT,
} from "../lib/legal-content";
import LegalDocument from "./LegalDocument";

interface SettingsAboutProps {
  readonly onClose: () => void;
  readonly onClearCache: () => Promise<void>;
}

type LegalView = "agreement" | "privacy" | null;

export default function SettingsAbout({ onClose, onClearCache }: SettingsAboutProps) {
  const chrome = useAppChromeInsets();
  const [legalView, setLegalView] = useState<LegalView>(null);
  const [clearing, setClearing] = useState(false);

  const nativeVersion = Constants.expoConfig?.version ?? "1.0.4";
  const buildNumber = String(
    Constants.expoConfig?.ios?.buildNumber ?? Constants.expoConfig?.android?.versionCode ?? "",
  );

  const handleFeedback = () => {
    const subject = encodeURIComponent("益语智库手机端反馈");
    const url = `mailto:${FEEDBACK_EMAIL}?subject=${subject}`;
    Linking.canOpenURL(url)
      .then((supported) => {
        if (!supported) {
          Alert.alert("没有可用的邮箱应用", `请直接发邮件至 ${FEEDBACK_EMAIL}`);
          return;
        }
        return Linking.openURL(url);
      })
      .catch(() => {
        Alert.alert("无法打开邮箱", `请直接发邮件至 ${FEEDBACK_EMAIL}`);
      });
  };

  const handleClearCache = () => {
    Alert.alert(
      "清除本地缓存",
      "将清除工作台快照、咨询缓存、临时图片等本地数据。同步队列里的待上传内容会保留。",
      [
        { text: "取消", style: "cancel" },
        {
          text: "清除",
          style: "destructive",
          onPress: async () => {
            setClearing(true);
            try {
              await onClearCache();
              Alert.alert("已清除", "本地缓存已清空。");
            } catch (error) {
              Alert.alert("清除失败", error instanceof Error ? error.message : "请稍后重试。");
            } finally {
              setClearing(false);
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[presets.pageHeader, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={palette.inkBlack} strokeWidth={iconStroke} />
        </TouchableOpacity>
        <Text style={presets.pageHeaderTitle}>关于</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        {/* Hero —— 不用卡片包，直接落在 canvas 上，像版权页 */}
        <View style={styles.hero}>
          <Text style={styles.heroAppName}>益语智库</Text>
          <Text style={styles.heroVersion}>
            版本 {nativeVersion}
            {buildNumber ? `  ·  build ${buildNumber}` : ""}
          </Text>
          <Text style={styles.heroPlatform}>
            {Platform.OS === "ios" ? "iOS" : "Android"} 客户端
          </Text>
        </View>

        <Text style={presets.sectionTitle}>法律</Text>
        <View style={presets.cardList}>
          <AboutRow
            icon={<FileText size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
            title="用户协议"
            rightText={LEGAL_VERSION}
            onPress={() => setLegalView("agreement")}
          />
          <View style={presets.dividerHairline} />
          <AboutRow
            icon={<Shield size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
            title="隐私政策"
            rightText={LEGAL_VERSION}
            onPress={() => setLegalView("privacy")}
          />
        </View>

        <Text style={presets.sectionTitle}>反馈与缓存</Text>
        <View style={presets.cardList}>
          <AboutRow
            icon={<MessageCircle size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
            title="发送反馈"
            rightText={FEEDBACK_EMAIL}
            onPress={handleFeedback}
          />
          <View style={presets.dividerHairline} />
          <AboutRow
            icon={
              <Trash2
                size={20}
                color={clearing ? palette.textTertiary : palette.cinnabar}
                strokeWidth={iconStroke}
              />
            }
            title={clearing ? "清除中..." : "清除本地缓存"}
            rightText="不影响云端数据"
            danger
            onPress={clearing ? undefined : handleClearCache}
          />
        </View>

        <Text style={presets.hintText}>
          组织管理、AI 配置、任务规则等"软件级"设置请前往电脑端"系统设置"。本应用仅供已在电脑端注册的员工登录使用。
        </Text>
      </View>

      <Modal
        visible={legalView !== null}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setLegalView(null)}
      >
        {legalView === "agreement" ? (
          <LegalDocument
            title="用户协议"
            body={USER_AGREEMENT_TEXT}
            onClose={() => setLegalView(null)}
          />
        ) : null}
        {legalView === "privacy" ? (
          <LegalDocument
            title="隐私政策"
            body={PRIVACY_POLICY_TEXT}
            onClose={() => setLegalView(null)}
          />
        ) : null}
      </Modal>
    </SafeAreaView>
  );
}

interface AboutRowProps {
  readonly icon: React.ReactNode;
  readonly title: string;
  readonly rightText?: string;
  readonly onPress?: () => void;
  readonly danger?: boolean;
}

function AboutRow({ icon, title, rightText, onPress, danger }: AboutRowProps) {
  return (
    <TouchableOpacity
      style={presets.rowEntry}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.6}
    >
      <View style={styles.rowIconSlot}>{icon}</View>
      <Text style={[styles.rowTitle, danger && { color: palette.cinnabar }]}>{title}</Text>
      <View style={styles.rowRight}>
        {rightText ? (
          <Text style={styles.rowRightText} numberOfLines={1}>
            {rightText}
          </Text>
        ) : null}
        {onPress ? (
          <ChevronRight size={18} color={palette.textTertiary} strokeWidth={iconStroke} />
        ) : null}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  headerSpacer: { width: 36 },
  content: { flex: 1, paddingHorizontal: layout.screenPaddingH },
  hero: {
    alignItems: "center",
    paddingVertical: spacing.xxxl, // 40，公文式留白
  },
  heroAppName: {
    ...typography.titleHero, // 28/600/36
    color: palette.inkBlack,
  },
  heroVersion: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
    marginTop: spacing.sm,
    fontVariant: ["tabular-nums"],
  },
  heroPlatform: {
    ...typography.caption,
    color: palette.textTertiary,
    marginTop: 2,
  },
  rowIconSlot: {
    width: 36,
    alignItems: "flex-start",
    justifyContent: "center",
    marginRight: spacing.lg, // 与 dividerHairline 的 marginLeft 52 对齐：36 + 16 = 52
  },
  rowTitle: {
    flex: 1,
    ...typography.bodyLarge, // 16/400/24
    color: palette.inkBlack,
    fontWeight: "500",
  },
  rowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  rowRightText: {
    ...typography.caption,
    color: palette.textTertiary,
    maxWidth: 160,
    textAlign: "right",
  },
});
