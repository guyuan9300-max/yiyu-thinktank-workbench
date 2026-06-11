import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ChevronDown, CheckCircle2, AlertCircle } from "lucide-react-native";
import Constants from "expo-constants";
import { useAuth } from "../lib/auth-context";
import { useAndroidExitApp } from "../lib/android-back";
import * as api from "../lib/api";
import { initializeRuntime } from "../lib/runtime";
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

export default function LoginScreen() {
  const chrome = useAppChromeInsets();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [serverUrl, setServerUrl] = useState(api.getBaseUrl());
  const [testingServer, setTestingServer] = useState(false);
  const [serverMessage, setServerMessage] = useState<string | null>(null);
  const [showServerConfig, setShowServerConfig] = useState(false);

  useAndroidExitApp(() => {
    if (showServerConfig) {
      setShowServerConfig(false);
      return true;
    }
    return false;
  });

  useEffect(() => {
    (async () => {
      await initializeRuntime();
      setServerUrl(api.getBaseUrl());
    })();
  }, []);

  const handleSaveServerUrl = async () => {
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请输入服务地址");
      return;
    }

    setTestingServer(true);
    try {
      const probe = await api.probeMobileBackendContract(serverUrl.trim());
      await api.setAndSaveBaseUrl(probe.baseUrl);
      setServerUrl(api.getBaseUrl());
      setServerMessage(`已保存：${api.formatMobileBackendProbeSummary(probe)}`);
    } catch (error) {
      Alert.alert(
        "保存失败",
        error instanceof Error ? error.message : "服务地址不可用或格式无效",
      );
    } finally {
      setTestingServer(false);
    }
  };

  const handleTestServer = async () => {
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请输入服务地址");
      return;
    }

    setTestingServer(true);
    try {
      const normalized = serverUrl.trim();
      const probe = await api.probeMobileBackendContract(normalized);
      await api.setAndSaveBaseUrl(probe.baseUrl);
      setServerUrl(api.getBaseUrl());
      setServerMessage(api.formatMobileBackendProbeSummary(probe));
    } catch (error) {
      setServerMessage(error instanceof Error ? error.message : "服务不可达");
    } finally {
      setTestingServer(false);
    }
  };

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert("提示", "请输入邮箱和密码");
      return;
    }
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请先确认服务地址");
      return;
    }
    setLoading(true);
    try {
      await api.setAndSaveBaseUrl(serverUrl.trim());
      await signIn(email.trim(), password);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查邮箱、密码和服务地址";
      Alert.alert("登录失败", message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={[styles.inner, { paddingTop: chrome.screenTopPadding }]}
      >
        <ScrollView contentContainerStyle={[styles.scrollContent, { paddingBottom: chrome.screenBottomPadding }]} keyboardShouldPersistTaps="handled">
          {/* Logo area —— 印章式空心方框 + 益字，不再用蓝色实心圆 */}
          <View style={styles.logoArea}>
            <View style={styles.logoStamp}>
              <Text style={styles.logoStampChar}>益</Text>
            </View>
            <Text style={styles.brand}>益语智库</Text>
            <Text style={styles.subtitle}>移动工作台</Text>
          </View>

          {/* Login card */}
          <View style={styles.card}>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>邮箱</Text>
              <TextInput
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                placeholder="your@email.com"
                placeholderTextColor={palette.textTertiary}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>密码</Text>
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                placeholder="输入密码"
                placeholderTextColor={palette.textTertiary}
                secureTextEntry
              />
            </View>

            <TouchableOpacity
              style={styles.serverToggle}
              activeOpacity={0.6}
              onPress={() => setShowServerConfig((value) => !value)}
            >
              <View style={styles.serverToggleRow}>
                <View style={styles.serverToggleTextWrap}>
                  <Text style={styles.serverToggleLabel}>服务地址</Text>
                  <Text style={styles.serverToggleValue} numberOfLines={1}>
                    {serverUrl || "未配置"}
                  </Text>
                </View>
                <ChevronDown
                  size={16}
                  strokeWidth={iconStroke}
                  color={palette.textTertiary}
                  style={{ transform: [{ rotate: showServerConfig ? "180deg" : "0deg" }] }}
                />
              </View>
            </TouchableOpacity>

            {showServerConfig && (
              <View style={styles.serverCard}>
                <Text style={styles.serverHint}>
                  填写你的云端或局域网地址，例如 http://192.168.x.x:47831
                </Text>
                <TextInput
                  style={styles.input}
                  value={serverUrl}
                  onChangeText={setServerUrl}
                  placeholder={api.DEFAULT_BASE_URL || api.DEFAULT_BASE_URL_PLACEHOLDER}
                  placeholderTextColor={palette.textTertiary}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
                <View style={styles.serverActions}>
                  <TouchableOpacity
                    style={[presets.buttonOutline, styles.serverActionBtn, testingServer && styles.buttonDisabled]}
                    onPress={handleSaveServerUrl}
                    disabled={testingServer}
                    activeOpacity={0.6}
                  >
                    <Text style={presets.buttonOutlineText}>保存地址</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[presets.buttonOutline, styles.serverActionBtn, testingServer && styles.buttonDisabled]}
                    onPress={handleTestServer}
                    disabled={testingServer}
                    activeOpacity={0.6}
                  >
                    {testingServer ? (
                      <ActivityIndicator color={palette.inkBlack} size="small" />
                    ) : (
                      <Text style={presets.buttonOutlineText}>测试连接</Text>
                    )}
                  </TouchableOpacity>
                </View>
                {serverMessage ? (
                  <View style={styles.serverMessageRow}>
                    {serverMessage.includes("失败") || serverMessage.includes("无法") ? (
                      <AlertCircle size={12} strokeWidth={iconStroke} color={palette.cinnabar} />
                    ) : (
                      <CheckCircle2 size={12} strokeWidth={iconStroke} color={palette.bambooGreen} />
                    )}
                    <Text
                      style={[
                        styles.serverMessage,
                        {
                          color:
                            serverMessage.includes("失败") || serverMessage.includes("无法")
                              ? palette.cinnabar
                              : palette.bambooGreen,
                        },
                      ]}
                    >
                      {serverMessage}
                    </Text>
                  </View>
                ) : null}
              </View>
            )}

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.85}
            >
              {loading ? (
                <ActivityIndicator color={palette.paperRice} />
              ) : (
                <Text style={styles.buttonText}>登录</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.footer}>
            益语智库 v{Constants.expoConfig?.version ?? "1.0.4"}
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background, // 宣纸米
  },
  inner: {
    flex: 1,
    paddingHorizontal: layout.screenPaddingH,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingVertical: spacing.xxxl,
  },
  logoArea: {
    alignItems: "center",
    marginBottom: spacing.xxxl,
  },
  // 印章式空心方框，1.5px 浓墨描边 + "益"字居中
  logoStamp: {
    width: 64,
    height: 64,
    borderWidth: 1.5,
    borderColor: palette.inkBlack,
    borderRadius: borderRadius.md, // 12
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  logoStampChar: {
    fontSize: 28,
    fontWeight: "600",
    color: palette.inkBlack,
    letterSpacing: -0.5,
  },
  brand: {
    ...typography.titleHero, // 28/600/36/-0.2
    color: palette.inkBlack,
  },
  subtitle: {
    ...typography.caption, // 13/400/18
    color: palette.textTertiary,
    marginTop: 4,
  },
  card: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12
    padding: spacing.xl,
  },
  fieldGroup: {
    marginBottom: spacing.lg,
  },
  label: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: palette.paperMoon, // 月白偏黄
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    ...typography.bodyLarge, // 16/400/24
    color: palette.inkBlack,
  },
  serverToggle: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    paddingTop: spacing.lg,
    marginTop: spacing.sm,
  },
  serverToggleRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  serverToggleTextWrap: {
    flex: 1,
  },
  serverToggleLabel: {
    ...typography.label,
    color: palette.textTertiary,
  },
  serverToggleValue: {
    ...typography.caption,
    color: palette.inkBlack,
    marginTop: 4,
  },
  serverCard: {
    marginTop: spacing.md,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    backgroundColor: palette.paperRice, // 用 canvas 色，"嵌套"出深一档对比
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    gap: spacing.md,
  },
  serverHint: {
    ...typography.caption,
    color: palette.textTertiary,
    lineHeight: 20,
  },
  serverActions: {
    flexDirection: "row",
    gap: spacing.md,
  },
  serverActionBtn: {
    flex: 1,
    paddingVertical: spacing.md,
  },
  serverMessageRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  serverMessage: {
    ...typography.caption,
    lineHeight: 18,
    flex: 1,
  },
  // 登录主 CTA —— airy blue 蓝实心 + 蓝雾 shadow（桌面滴答清单风格）
  button: {
    backgroundColor: palette.airyBlue,
    borderRadius: borderRadius.md, // 16
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.lg,
    shadowColor: palette.airyBlue,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 6,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    ...typography.bodyLarge, // 15/500/22
    color: "#FFFFFF",
    fontWeight: "700",
  },
  footer: {
    textAlign: "center",
    ...typography.label,
    color: palette.textTertiary,
    marginTop: spacing.xxxl,
    fontVariant: ["tabular-nums"],
  },
});
