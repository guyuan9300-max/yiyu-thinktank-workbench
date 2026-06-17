import { useEffect, useState, useCallback } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  Modal,
  Linking,
  Image,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "../../lib/auth-context";
import { useAndroidBackToTasks } from "../../lib/android-back";
import { useAppChromeInsets } from "../../lib/app-chrome";
import { colors, spacing, fontSize, borderRadius, shadow, typography, layout, palette, iconStroke } from "../../lib/theme";
import { Camera, Search, Cloud, Smartphone, MessageSquare, Bell, Sliders, Info, ChevronRight, RefreshCw, PauseCircle, PlayCircle, AlertCircle, Download, Mic } from "lucide-react-native";
import { useRouter, type ErrorBoundaryProps } from "expo-router";
import { RouteErrorFallback } from "../../components/ErrorBoundary";
import { clearFeishuUserBinding, fetchHealth, getFeishuUserBinding, resolveAvatarUrl, startFeishuUserBinding, uploadMyAvatar, type FeishuUserBinding } from "../../lib/api";
import { useSystemHealth } from "../../lib/system-health";
import { triggerSync } from "../../lib/sync-engine";
import { formatTaskSyncReasonCode } from "../../lib/task-sync-presentation";
import * as cache from "../../lib/cache";
import { clearClientIntelCache } from "../../lib/client-intel-store";
import SettingsAccount from "../../components/SettingsAccount";
import SettingsDevice from "../../components/SettingsDevice";
import SettingsAbout from "../../components/SettingsAbout";

type SettingsView = "account" | "device" | "about" | null;

const FEISHU_LOCAL_CALDAV_HELP_URL = "https://www.feishu.cn/hc/zh-CN/articles/360043178673-%E8%AE%BE%E7%BD%AE%E6%9C%AC%E5%9C%B0%E7%B3%BB%E7%BB%9F%E6%97%A5%E5%8E%86%E4%B8%8E%E9%A3%9E%E4%B9%A6%E6%97%A5%E5%8E%86%E4%B9%8B%E9%97%B4%E7%9A%84%E5%90%8C%E6%AD%A5";

function getInitials(name: string): string {
  if (name.length <= 2) return name;
  return name.slice(-2);
}

function formatLocalTime(value: string | null | undefined): string {
  if (!value) return "未同步";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function formatPendingAge(value: string | null | undefined): string {
  if (!value) return "刚刚";
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 60_000) return "刚刚";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

function formatAgeMs(value: number | null | undefined): string {
  if (value == null || value < 60_000) return "刚刚";
  const minutes = Math.floor(value / 60_000);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时`;
  return `${Math.floor(hours / 24)} 天`;
}

function formatLegacyUploadReason(reasonCode: string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_required":
      return "需要重新登录";
    case "scope_mismatch":
      return "账号作用域不一致";
    case "file_missing":
      return "原件丢失";
    case "file_corrupted":
      return "原件损坏";
    case "upload_failed":
      return "上传失败";
    case "bind_pending_remote_id":
      return "等待远端任务 ID";
    case "integrity_blocked":
      return "本地完整性冻结";
    case "manual_pause":
      return "同步已暂停";
    default:
      return "未知错误";
  }
}

function formatSyncReasonCode(reasonCode: string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_expired":
      return "登录已过期";
    case "permission_denied":
      return "权限不足";
    case "validation_failed":
      return "数据校验失败";
    case "version_conflict":
      return "服务器版本冲突";
    case "file_missing":
      return "原件缺失";
    case "quota_exceeded":
      return "配额不足";
    case "server_rejected":
      return "服务器拒绝";
    case "thermal_blocked":
      return "设备温度受限";
    case "model_unavailable":
      return "模型不可用";
    default:
      return "需人工处理";
  }
}

function formatPendingOperationLabel(operation: string | null | undefined): string {
  switch (operation) {
    case "create":
      return "创建";
    case "update":
      return "更新";
    case "delete":
      return "删除";
    case "complete_with_review":
      return "完成并复盘";
    default:
      return "任务修改";
  }
}

interface SettingsRowProps {
  /** @deprecated 旧"彩色背景方块"方案保留 prop 兼容 call site，新设计不再渲染 */
  readonly iconBg?: string;
  readonly icon: React.ReactNode;
  readonly title: string;
  readonly subtitle: string;
  readonly onPress: () => void;
  readonly rightText?: string;
}

function SettingsRow({
  icon,
  title,
  subtitle,
  onPress,
  rightText,
}: SettingsRowProps) {
  return (
    <TouchableOpacity style={styles.settingsRow} onPress={onPress} activeOpacity={0.6}>
      <View style={styles.settingsIconSlot}>{icon}</View>
      <View style={styles.settingsTextContainer}>
        <Text style={styles.settingsTitle}>{title}</Text>
        {subtitle ? (
          <Text style={styles.settingsSubtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {rightText ? (
        <Text style={styles.settingsRightText} numberOfLines={1}>
          {rightText}
        </Text>
      ) : (
        <ChevronRight size={22} color={colors.textTertiary} />
      )}
    </TouchableOpacity>
  );
}

export default function ProfileScreen() {
  const { user, signOut, applyUser } = useAuth();
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const systemHealth = useSystemHealth();
  const [activeSettings, setActiveSettings] = useState<SettingsView>(null);
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [processingPending, setProcessingPending] = useState(false);
  // 按"手机端不做组织/身份配置"原则：姓名、职位由桌面端维护后多端同步，
  // 手机不提供编辑入口。头像后续在第二批接 image picker，本文件先占位。
  // 诊断面板默认隐藏 —— 普通用户进 profile 不该一眼看到 baseUrl / Lane / op 详情这类
  // 开发信息。客服可指导用户"连点版本号 7 次"开启 dev 模式查看完整诊断。
  const [debugTapCount, setDebugTapCount] = useState(0);
  const debugUnlocked = debugTapCount >= 7;
  const [feishuBinding, setFeishuBinding] = useState<FeishuUserBinding | null>(null);
  const [feishuBindingBusy, setFeishuBindingBusy] = useState<"idle" | "loading" | "starting" | "clearing">("idle");

  const pingHealth = useCallback(async () => {
    try {
      await fetchHealth();
      const now = new Date();
      setLastSyncTime(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
    } catch {
      setLastSyncTime("同步失败");
    }
  }, []);

  // "立即同步" button: push pending ops + pull cloud, then refresh liveness.
  // Previously this only called fetchHealth() which is just a /health ping and
  // did NOT flush the local-first queue, so users would tap "Sync Now" and see
  // the timestamp update even though nothing had actually synced.
  const doSync = useCallback(async () => {
    setSyncing(true);
    try {
      await triggerSync();
      await pingHealth();
    } catch {
      setLastSyncTime("同步失败");
    } finally {
      setSyncing(false);
    }
  }, [pingHealth]);

  const refreshFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("loading");
    try {
      const binding = await getFeishuUserBinding();
      setFeishuBinding(binding);
    } catch (error) {
      // 静默处理：cloud_backend 上 OAuth 绑定路由可能未部署（404）/ 暂时不可达
      // 等情况，profile 一打开就弹 Alert 会干扰用户使用 app 主流程。
      // 视为"未绑定"状态，用户可以点入口手动触发重新绑定。
      const status =
        error instanceof Error && /404|not\s*found/i.test(error.message) ? 404 : 500;
      if (status === 404) {
        // 路由不存在 —— 服务器还没部署 OAuth 绑定能力，把状态留空，UI 显示未绑定
        setFeishuBinding(null);
      } else if (error instanceof Error && /401|unauthorized/i.test(error.message)) {
        // 401 由 api.ts 的 token refresh 已处理；走到这里通常是刷新也失败 → 不弹弹窗
        setFeishuBinding(null);
      } else {
        // 其它错误（网络断开等）静默，下次 profile 重新挂载时再试
        setFeishuBinding(null);
      }
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, []);

  // On mount we only ping liveness — a full sync already runs in the background
  // via the sync-engine foreground loop, so we avoid a heavy extra cycle here.
  useEffect(() => {
    void pingHealth();
  }, [pingHealth]);

  useEffect(() => {
    void refreshFeishuBinding();
  }, [refreshFeishuBinding]);

  const handleStartFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("starting");
    try {
      const started = await startFeishuUserBinding();
      await Linking.openURL(started.authorizeUrl);
      Alert.alert(
        "已打开飞书授权页",
        started.qrReady
          ? "请在飞书里扫码并确认授权，完成后回到手机端刷新状态。"
          : "已打开授权页；如果当前环境不能直接扫码，请在浏览器继续完成授权。",
      );
      await refreshFeishuBinding();
    } catch (error) {
      Alert.alert("发起绑定失败", error instanceof Error ? error.message : "无法发起飞书绑定。");
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, [refreshFeishuBinding]);

  const handleClearFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("clearing");
    try {
      const binding = await clearFeishuUserBinding();
      setFeishuBinding(binding);
      Alert.alert("已解除绑定", "当前账号的飞书身份绑定已清除。");
    } catch (error) {
      Alert.alert("解除失败", error instanceof Error ? error.message : "无法解除飞书绑定。");
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, []);

  const handleOpenFeishuBinding = useCallback(() => {
    if (feishuBindingBusy !== "idle") {
      return;
    }
    if (!feishuBinding) {
      void refreshFeishuBinding();
      return;
    }
    if (feishuBinding.linked) {
      Alert.alert(
        "飞书已绑定",
        `${feishuBinding.name || feishuBinding.email || "当前账号"} 已完成飞书身份绑定。`,
        [
          { text: "取消", style: "cancel" },
          {
            text: "刷新状态",
            onPress: () => {
              void refreshFeishuBinding();
            },
          },
          {
            text: "解除绑定",
            style: "destructive",
            onPress: () => {
              void handleClearFeishuBinding();
            },
          },
        ],
      );
      return;
    }
    if (feishuBinding.readyForAuthorization) {
      void handleStartFeishuBinding();
      return;
    }
    Alert.alert(
      "暂不可绑定",
      feishuBinding.lastError || "需要管理员先配置飞书 App ID、App Secret 和机器人基础设置。",
    );
  }, [feishuBinding, feishuBindingBusy, handleClearFeishuBinding, handleStartFeishuBinding, refreshFeishuBinding]);

  const handleOpenNotificationSettings = useCallback(() => {
    Linking.openSettings().catch(() => {
      Alert.alert("无法打开设置", "请手动前往系统设置调整通知权限。");
    });
  }, []);

  const feishuBindingRightText =
    feishuBindingBusy !== "idle"
      ? "处理中"
      : feishuBinding?.linked
        ? "已绑定"
        : feishuBinding?.readyForAuthorization
          ? "待绑定"
          : "未就绪";

  useAndroidBackToTasks(
    useCallback(() => {
      if (activeSettings) {
        setActiveSettings(null);
        return true;
      }
      return false;
    }, [activeSettings]),
  );

  const handleLogout = useCallback(() => {
    Alert.alert("退出登录", "确定要退出当前账号吗？", [
      { text: "取消", style: "cancel" },
      {
        text: "退出",
        style: "destructive",
        onPress: () => signOut(),
      },
    ]);
  }, [signOut]);

  const closeSettings = useCallback(() => setActiveSettings(null), []);

  const [avatarUploading, setAvatarUploading] = useState(false);

  // 头像上传：手机端唯一允许的"个人字段"修改入口。其他身份信息（姓名/职位/
  // 组织/部门）都在桌面端维护后多端同步。
  const handleEditAvatar = useCallback(() => {
    if (avatarUploading) return;
    Alert.alert("更换头像", undefined, [
      { text: "取消", style: "cancel" },
      {
        text: "从相册选择",
        onPress: async () => {
          const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
          if (!perm.granted) {
            Alert.alert("无法访问相册", "请到系统设置允许「益语智库」访问照片。");
            return;
          }
          const result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsEditing: true,
            aspect: [1, 1],
            quality: 0.8,
          });
          if (result.canceled || !result.assets?.[0]) return;
          await doUploadAvatar(result.assets[0]);
        },
      },
      {
        text: "拍照",
        onPress: async () => {
          const perm = await ImagePicker.requestCameraPermissionsAsync();
          if (!perm.granted) {
            Alert.alert("无法使用相机", "请到系统设置允许「益语智库」访问相机。");
            return;
          }
          const result = await ImagePicker.launchCameraAsync({
            allowsEditing: true,
            aspect: [1, 1],
            quality: 0.8,
          });
          if (result.canceled || !result.assets?.[0]) return;
          await doUploadAvatar(result.assets[0]);
        },
      },
    ]);
  }, [avatarUploading]);

  const doUploadAvatar = useCallback(
    async (asset: ImagePicker.ImagePickerAsset) => {
      setAvatarUploading(true);
      try {
        const mime =
          asset.mimeType ||
          (asset.uri.match(/\.(jpe?g|png|webp|heic)$/i)
            ? `image/${asset.uri.split(".").pop()!.toLowerCase().replace("jpg", "jpeg")}`
            : "image/jpeg");
        const filename = asset.fileName || `avatar.${mime.split("/")[1] || "jpg"}`;
        const next = await uploadMyAvatar({ uri: asset.uri, name: filename, type: mime });
        applyUser(next);
      } catch (error) {
        Alert.alert("上传失败", error instanceof Error ? error.message : "请检查网络后重试。");
      } finally {
        setAvatarUploading(false);
      }
    },
    [applyUser],
  );

  const displayName = user?.fullName ?? "用户";
  const displayEmail = user?.email ?? "";
  const initials = getInitials(displayName);
  const avatarFullUrl = resolveAvatarUrl(user?.avatarUrl ?? null);
  const legacyUploadNeedsAttention = systemHealth.legacyUploadOps.filter(
    (op) => op.status === "needs_attention",
  ).length;
  const recordingPendingTextCount = systemHealth.recordings.pendingTextSync;
  const recordingNeedsAttentionCount = systemHealth.recordings.failedTextSync + systemHealth.recordings.needsAction;
  const combinedPendingTotal =
    systemHealth.pendingSummary.total + systemHealth.legacyUploadOps.length + recordingPendingTextCount;
  const combinedQueuedCount =
    systemHealth.pendingSummary.queued +
    systemHealth.legacyUploadOps.filter((op) => op.status === "queued").length +
    recordingPendingTextCount;
  const combinedProcessingCount =
    systemHealth.pendingSummary.syncing +
    systemHealth.pendingSummary.processing +
    systemHealth.legacyUploadOps.filter((op) => op.status === "processing").length;
  const combinedNeedsAttention =
    systemHealth.pendingSummary.needsAttention + legacyUploadNeedsAttention + recordingNeedsAttentionCount;

  // 点击「待处理」：retryAllFailed 会先 requeue 卡死项(已修为重置 retry_count)再全量同步，
  // 是真正能把离线卡住的任务救回云端的动作(triggerSync 单独调对 needs_attention 无效)。
  const runPendingRetry = async () => {
    if (processingPending) return;
    setProcessingPending(true);
    try {
      await systemHealth.retryAllFailed();
      await pingHealth();
    } catch {
      setLastSyncTime("同步失败");
    } finally {
      setProcessingPending(false);
    }
  };
  const processPending = () => {
    if (processingPending || combinedPendingTotal === 0) return;
    // 有卡死项 → 先把失败原因摊给用户再重试;纯排队项 → 直接同步。
    if (combinedNeedsAttention > 0) {
      const reasons = Object.entries(systemHealth.pendingSummary.byReasonCode ?? {})
        .filter(([, count]) => (count ?? 0) > 0)
        .map(([code, count]) => `· ${formatTaskSyncReasonCode(code)}（${count}）`)
        .join("\n");
      Alert.alert(
        `待处理 ${combinedNeedsAttention} 项`,
        reasons
          ? `这些项暂未同步到云端：\n${reasons}\n\n点击「立即重试」重新尝试上传。`
          : "有未同步到云端的项，点击「立即重试」重新尝试上传。",
        [
          { text: "取消", style: "cancel" },
          { text: "立即重试", onPress: () => { void runPendingRetry(); } },
        ],
      );
      return;
    }
    void runPendingRetry();
  };

  return (
    <>
      <SafeAreaView style={styles.container} edges={["left", "right"]}>
        <ScrollView
          contentContainerStyle={{ paddingTop: chrome.screenTopPadding, paddingBottom: chrome.screenBottomPadding + spacing.xl }}
          showsVerticalScrollIndicator={false}
        >
          {/* Profile card */}
          <View style={[styles.profileCard, shadow.card]}>
            <View style={styles.profileRow}>
              <View style={styles.avatarContainer}>
                <View style={styles.avatar}>
                  {avatarFullUrl ? (
                    <Image source={{ uri: avatarFullUrl }} style={styles.avatarImage} />
                  ) : (
                    <Text style={styles.avatarText}>{initials}</Text>
                  )}
                </View>
                <TouchableOpacity
                  style={styles.cameraOverlay}
                  onPress={handleEditAvatar}
                  disabled={avatarUploading}
                >
                  {avatarUploading ? (
                    <ActivityIndicator size="small" color={colors.textSecondary} />
                  ) : (
                    <Camera size={12} color={colors.textSecondary} />
                  )}
                </TouchableOpacity>
              </View>
              <View style={styles.profileInfo}>
                <View style={styles.nameRow}>
                  <Text style={styles.profileName}>{displayName}</Text>
                </View>
                <Text style={styles.profileTitle}>
                  {[user?.organizationName, user?.departmentName].filter(Boolean).join(" · ") ||
                    user?.title ||
                    "—"}
                </Text>
              </View>
              <TouchableOpacity style={styles.searchButton} onPress={() => setActiveSettings("account")}>
                <Search size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
          </View>

          {/* Cloud sync card */}
          <View style={styles.syncCard}>
            <View style={styles.syncLeft}>
              <Cloud size={20} strokeWidth={iconStroke} color={palette.textTertiary} />
              <View>
                <Text style={styles.syncText}>
                  {lastSyncTime === "同步失败" ? "云端连接失败" : "数据已同步至云端"}
                </Text>
                <Text style={styles.syncTime}>
                  {lastSyncTime ? `上次同步 ${lastSyncTime}` : "未同步"}
                </Text>
              </View>
            </View>
            <TouchableOpacity style={styles.syncButton} onPress={() => { void doSync(); }} disabled={syncing}>
              {syncing ? (
                <ActivityIndicator size="small" color={colors.brand} />
              ) : (
                <Text style={styles.syncButtonText}>立即同步</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.sectionLabel}>系统健康</Text>
          <View style={[styles.healthCard, shadow.card]}>
            <View style={styles.healthTopRow}>
              <View>
                <Text style={styles.healthTitle}>
                  {systemHealth.syncFreezeState !== "ready"
                    ? "同步已冻结"
                    : combinedNeedsAttention > 0
                    ? "待处理"
                    : systemHealth.syncStatus === "syncing"
                      ? "同步中"
                      : "正常"}
                </Text>
                <Text style={styles.healthSubtitle}>
                  最近同步 {formatLocalTime(systemHealth.lastSyncTime)}
                </Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.healthBadge,
                  { flexDirection: "row", alignItems: "center", gap: 5 },
                  combinedNeedsAttention > 0 && { borderColor: colors.error, backgroundColor: "rgba(220,38,38,0.08)" },
                ]}
                onPress={processPending}
                disabled={combinedPendingTotal === 0 || processingPending}
                activeOpacity={0.7}
              >
                {processingPending ? (
                  <ActivityIndicator size="small" color={combinedNeedsAttention > 0 ? colors.error : colors.brand} />
                ) : (
                  <>
                    <Text style={[styles.healthBadgeText, combinedNeedsAttention > 0 && { color: colors.error }]}>
                      待处理 {combinedPendingTotal}
                    </Text>
                    {combinedPendingTotal > 0 ? (
                      <RefreshCw size={13} color={combinedNeedsAttention > 0 ? colors.error : palette.textTertiary} />
                    ) : null}
                  </>
                )}
              </TouchableOpacity>
            </View>

            {systemHealth.syncFreezeState !== "ready" ? (
              <View style={styles.healthNoticeRow}>
                <AlertCircle size={14} color={colors.error} />
                <Text style={styles.healthNoticeText}>
                  {systemHealth.freezeSummary}
                  {systemHealth.syncFreezeDetail ? ` · ${systemHealth.syncFreezeDetail}` : ""}
                </Text>
              </View>
            ) : null}

            <View style={styles.healthMetricsRow}>
              <View style={styles.healthMetricPill}>
                <Text style={styles.healthMetricLabel}>队列</Text>
                <Text style={styles.healthMetricValue}>{combinedQueuedCount}</Text>
              </View>
              <View style={styles.healthMetricPill}>
                <Text style={styles.healthMetricLabel}>进行中</Text>
                <Text style={styles.healthMetricValue}>{combinedProcessingCount}</Text>
              </View>
            </View>

            {debugUnlocked ? (
              <>
            <View style={styles.healthBackendPanel}>
              <Text style={styles.healthDebugSectionTitle}>当前后端能力</Text>
              <Text style={styles.healthDebugMeta}>baseUrl={systemHealth.backendBaseUrl}</Text>
              {systemHealth.backendCapabilities ? (
                <>
                  <Text style={styles.healthDebugMeta}>
                    consult={systemHealth.backendCapabilities.consultationChat ? "ready" : "unavailable"}
                    {` · workspace=${systemHealth.backendCapabilities.clientWorkspace ? "ready" : "route_unavailable"}`}
                    {` · cockpit=${systemHealth.backendCapabilities.strategicCockpit ? "ready" : "route_unavailable"}`}
                  </Text>
                  <Text style={styles.healthDebugMeta}>
                    mirror={systemHealth.backendCapabilities.knowledgeMirror ? "ready" : "data_missing"}
                    {` · contextBundle=${systemHealth.backendCapabilities.contextBundle ? "ready" : "unavailable"}`}
                    {` · payload=${systemHealth.backendCapabilities.consultationPayloadVersion}`}
                  </Text>
                  <Text style={styles.healthDebugMeta}>
                    最近探测 {formatLocalTime(systemHealth.lastCapabilityProbeAt)}
                  </Text>
                </>
              ) : (
                <Text style={[styles.healthDebugMeta, styles.healthDebugMetaDanger]}>
                  能力探测失败：{systemHealth.backendCapabilitiesError ?? "无法确认当前后端是否支持 workspace / cockpit / context bundle"}
                </Text>
              )}
            </View>

            <View style={styles.healthBackendPanel}>
              <Text style={styles.healthDebugSectionTitle}>录音本地链路</Text>
              <Text style={styles.healthDebugMeta}>
                目录={systemHealth.recordings.localDirectory || "未就绪"}
              </Text>
              <Text style={styles.healthDebugMeta}>
                会话={systemHealth.recordings.total}
                {` · 待同步文本=${systemHealth.recordings.pendingTextSync}`}
                {` · 需处理=${recordingNeedsAttentionCount}`}
              </Text>
              <Text style={styles.healthDebugMeta}>云端 Base URL={systemHealth.backendBaseUrl}</Text>
              {systemHealth.recordings.latestError ? (
                <Text style={[styles.healthDebugMeta, styles.healthDebugMetaDanger]}>
                  最近错误：{systemHealth.recordings.latestError}
                </Text>
              ) : null}
            </View>

            <View style={styles.healthActionRow}>
              <TouchableOpacity
                style={styles.healthActionButton}
                disabled={!systemHealth.freezeActionLabel}
                onPress={() => {
                  if (systemHealth.isSyncPaused) {
                    systemHealth.resumeSync();
                  } else {
                    systemHealth.pauseSync();
                  }
                }}
              >
                {systemHealth.isSyncPaused ? (
                  <PlayCircle size={18} strokeWidth={iconStroke} color={palette.textTertiary} />
                ) : (
                  <PauseCircle size={18} strokeWidth={iconStroke} color={palette.textTertiary} />
                )}
                <Text style={styles.healthActionText}>
                  {systemHealth.freezeActionLabel ?? "同步已冻结"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => { void systemHealth.retryAllFailed(); }}
                disabled={combinedNeedsAttention === 0}
              >
                <RefreshCw size={16} color={combinedNeedsAttention === 0 ? colors.textTertiary : colors.brand} />
                <Text style={[styles.healthActionText, combinedNeedsAttention === 0 && styles.healthActionTextDisabled]}>
                  重试失败项
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.clearSafeArtifacts().then((result) => {
                    Alert.alert(
                      "已清理",
                      `已清理 ${result.clearedTaskServerShadows} 条可安全删除的同步影子记录。`,
                    );
                  });
                }}
              >
                <RefreshCw size={16} color={colors.brand} />
                <Text style={styles.healthActionText}>清理安全缓存</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.exportDiagnostics().then(({ filePath, bundle }) => {
                    Alert.alert(
                      "诊断包已导出",
                      `已保存到：\n${filePath}\n\n最近 sync 事件：${bundle.recentSyncEvents.length} 条\n待同步操作：${bundle.pendingSummary.total} 条\n录音待同步文本：${bundle.recordings.pendingTextSync} 条`,
                    );
                  }).catch((error: unknown) => {
                    Alert.alert(
                      "导出失败",
                      error instanceof Error ? error.message : "无法导出诊断包。",
                    );
                  });
                }}
              >
                <Download size={18} strokeWidth={iconStroke} color={palette.textTertiary} />
                <Text style={styles.healthActionText}>导出诊断包</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.refreshBackendCapabilities();
                }}
              >
                <RefreshCw size={16} color={colors.brand} />
                <Text style={styles.healthActionText}>刷新后端能力</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.healthDebugPanel}>
              <Text style={styles.healthDebugSectionTitle}>高级诊断</Text>
              <Text style={styles.healthDebugMeta}>
                scope={systemHealth.accountScopeKey} · integrity={systemHealth.integrityStatus}
                {systemHealth.integrityReason ? ` · ${systemHealth.integrityReason}` : ""}
              </Text>
              <Text style={styles.healthDebugMeta}>
                freeze={systemHealth.syncFreezeState}
                {systemHealth.syncFreezeDetail ? ` · ${systemHealth.syncFreezeDetail}` : ""}
                {` · shadow=${systemHealth.taskServerShadowCount}`}
                {` · staleShadow=${systemHealth.staleTaskServerShadowCount}`}
              </Text>
              <View style={styles.healthSubsection}>
                <Text style={styles.healthDebugSectionTitle}>Lane 诊断</Text>
                {Object.values(systemHealth.laneDiagnostics).map((lane) => (
                  <View key={lane.lane} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>{lane.lane}</Text>
                      <Text style={styles.healthDebugMeta}>
                        total={lane.total}
                        {` · oldest=${formatAgeMs(lane.oldestAgeMs)}`}
                        {` · active=${lane.active ? "yes" : "no"}`}
                        {lane.topReasonCode ? ` · top1=${formatLegacyUploadReason(lane.topReasonCode)}` : ""}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
              {systemHealth.blockedReason ? (
                <Text style={[styles.healthDebugMeta, styles.healthDebugMetaDanger]}>
                  同步冻结：{systemHealth.blockedReason}
                </Text>
              ) : null}
              {(
                Object.entries(systemHealth.runtimeFlags) as Array<[keyof typeof systemHealth.runtimeFlags, boolean]>
              ).map(([name, enabled]) => (
                <View key={name} style={styles.healthFlagRow}>
                  <Text style={styles.healthFlagLabel}>{name}</Text>
                  <TouchableOpacity
                    style={[styles.healthFlagToggle, enabled ? styles.healthFlagToggleEnabled : styles.healthFlagToggleDisabled]}
                    onPress={() => { void systemHealth.setRuntimeFlag(name, !enabled); }}
                  >
                    <Text style={[styles.healthFlagToggleText, !enabled && styles.healthFlagToggleTextDisabled]}>
                      {enabled ? "已开启" : "已关闭"}
                    </Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>

            {systemHealth.recentPendingOps.length > 0 ? (
              <View style={styles.healthDebugList}>
                {systemHealth.recentPendingOps.slice(0, 4).map((op) => (
                  <View key={op.clientOpId} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>
                        {op.entityType}:{op.operation}
                      </Text>
                      <Text style={styles.healthDebugMeta}>
                        lane={op.lane} · status={op.status}
                        {` · retry=${op.retryCount}`}
                        {` · age=${formatPendingAge(op.updatedAt ?? op.createdAt)}`}
                        {op.reasonCode ? ` · ${op.reasonCode}` : ""}
                      </Text>
                    </View>
                    {op.status === "needs_attention" ? (
                      <TouchableOpacity onPress={() => { void systemHealth.retryOne(op.id); }}>
                        <AlertCircle size={16} color={colors.error} />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                ))}
              </View>
            ) : null}

            {systemHealth.taskConflicts.length > 0 ? (
              <View style={styles.healthDebugList}>
                <Text style={styles.healthDebugSectionTitle}>冲突恢复</Text>
                {systemHealth.taskConflicts.map((conflict) => (
                  <View key={conflict.taskId} style={styles.healthConflictCard}>
                    <Text style={styles.healthDebugTitle}>{conflict.title}</Text>
                    <Text style={styles.healthDebugMeta}>
                      {formatPendingOperationLabel(conflict.pendingOperation)}
                      {` · ${formatPendingAge(conflict.pendingUpdatedAt)}`}
                      {` · ${formatSyncReasonCode(conflict.syncReasonCode)}`}
                    </Text>
                    <Text style={styles.healthDebugMeta}>
                      {conflict.hasServerShadow
                        ? `已缓存服务器快照${conflict.serverVersion != null ? ` · v${conflict.serverVersion}` : ""}`
                        : "尚未缓存服务器快照，暂时不能恢复服务器版本"}
                      {conflict.lastError ? ` · ${conflict.lastError}` : ""}
                    </Text>
                    <View style={styles.healthConflictActions}>
                      <TouchableOpacity
                        style={[
                          styles.healthConflictButton,
                          conflict.hasServerShadow
                            ? styles.healthConflictButtonDanger
                            : styles.healthConflictButtonDisabled,
                        ]}
                        disabled={!conflict.hasServerShadow}
                        onPress={() => {
                          Alert.alert(
                            "恢复服务器版本",
                            `这会丢弃「${conflict.title}」的本地未同步修改，并恢复到最近一次拉取到手机的服务器版本。`,
                            [
                              { text: "取消", style: "cancel" },
                              {
                                text: "恢复",
                                style: "destructive",
                                onPress: () => {
                                  void systemHealth.restoreTaskConflict(conflict.taskId).then((result) => {
                                    if (!result.restored) {
                                      Alert.alert("无法恢复", "当前没有可用的服务器快照。");
                                      return;
                                    }
                                    Alert.alert(
                                      "已恢复服务器版本",
                                      `已清理 ${result.clearedPendingOps} 条本地待同步修改，并恢复服务器版本。`,
                                    );
                                  }).catch((error: unknown) => {
                                    Alert.alert(
                                      "恢复失败",
                                      error instanceof Error ? error.message : "无法恢复服务器版本。",
                                    );
                                  });
                                },
                              },
                            ],
                          );
                        }}
                      >
                        <Text
                          style={[
                            styles.healthConflictButtonText,
                            conflict.hasServerShadow
                              ? styles.healthConflictButtonTextDanger
                              : styles.healthConflictButtonTextDisabled,
                          ]}
                        >
                          恢复服务器版本
                        </Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.healthConflictButton, styles.healthConflictButtonPrimary]}
                        onPress={() => {
                          void systemHealth.retryTaskConflict(conflict.taskId).then(() => {
                            Alert.alert("已重试", `已保留「${conflict.title}」的本地修改并重新进入同步队列。`);
                          }).catch((error: unknown) => {
                            Alert.alert(
                              "重试失败",
                              error instanceof Error ? error.message : "无法重新加入同步队列。",
                            );
                          });
                        }}
                      >
                        <Text style={[styles.healthConflictButtonText, styles.healthConflictButtonTextPrimary]}>
                          保留本地并重试
                        </Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            ) : null}

            {systemHealth.legacyUploadOps.length > 0 ? (
              <View style={styles.healthDebugList}>
                <Text style={styles.healthDebugSectionTitle}>附件 / 录音上传</Text>
                {systemHealth.legacyUploadOps.map((op) => (
                  <View key={op.opId} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>
                        {op.displayTitle || op.objectType}
                      </Text>
                      <Text style={styles.healthDebugMeta}>
                        lane={op.lane} · status={op.status}
                        {` · retry=${op.retryCount}`}
                        {` · age=${formatAgeMs(op.ageMs)}`}
                        {` · ${formatLegacyUploadReason(op.reasonCode)}`}
                      </Text>
                    </View>
                    {op.status !== "processing" ? (
                      <TouchableOpacity onPress={() => { void systemHealth.retryLegacyUploadOp(op.opId); }}>
                        <RefreshCw
                          size={16}
                          color={op.status === "needs_attention" ? colors.error : colors.brand}
                        />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                ))}
              </View>
            ) : null}
              </>
            ) : null}
          </View>

          {/* 业务模块偏好（任务/日历/AI）已迁回桌面端统一管理，
              手机端不再暴露这些"软件级配置" —— 见 PRD 中"手机端只做登录即用"原则。 */}

          {/* Settings section: 现场记录 */}
          <Text style={styles.sectionLabel}>现场记录</Text>
          <View style={styles.settingsCard}>
            <SettingsRow
              icon={<Mic size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="速记录音箱"
              subtitle="现场随手录的语音，回头归档到任务"
              onPress={() => router.push("/recordings")}
            />
          </View>

          {/* Settings section: 账号与系统 */}
          <Text style={styles.sectionLabel}>账号与系统</Text>
          <View style={styles.settingsCard}>
            <SettingsRow
              icon={<Smartphone size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="账号设置"
              subtitle=""
              onPress={() => setActiveSettings("account")}
              rightText={displayEmail}
            />
            <View style={styles.separator} />
            <SettingsRow
              icon={<MessageSquare size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="飞书绑定"
              subtitle="绑定后，你参与的飞书任务可进入益语，也用于飞书文档权限"
              onPress={handleOpenFeishuBinding}
              rightText={feishuBindingRightText}
            />
            <View style={styles.separator} />
            <SettingsRow
              icon={<Bell size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="系统通知权限"
              subtitle=""
              onPress={handleOpenNotificationSettings}
              rightText="前往设置"
            />
          </View>
          <View style={styles.feishuCalendarHintCard}>
            <Text style={styles.feishuCalendarHintTitle}>手机日历提醒说明</Text>
            <Text style={styles.feishuCalendarHintText}>
              若要在手机系统日历收到提醒，请按飞书官方指引启用 CalDAV；系统日历只看提醒，不作为任务编辑入口。
            </Text>
            <TouchableOpacity
              activeOpacity={0.72}
              onPress={() => {
                void Linking.openURL(FEISHU_LOCAL_CALDAV_HELP_URL);
              }}
            >
              <Text style={styles.feishuCalendarHintLink}>查看飞书 CalDAV 指引</Text>
            </TouchableOpacity>
          </View>

          {/* Settings section: 本机偏好 */}
          <Text style={styles.sectionLabel}>本机偏好</Text>
          <View style={styles.settingsCard}>
            <SettingsRow
              icon={<Sliders size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="偏好设置"
              subtitle="流量保护、勿扰时段、主题"
              onPress={() => setActiveSettings("device")}
            />
            <View style={styles.separator} />
            <SettingsRow
              icon={<Info size={20} color={palette.textTertiary} strokeWidth={iconStroke} />}
              title="关于"
              subtitle="协议、隐私政策、反馈、清缓存"
              onPress={() => setActiveSettings("about")}
            />
          </View>

          {/* Logout */}
          <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
            <Text style={styles.logoutText}>退出登录</Text>
          </TouchableOpacity>
          <TouchableOpacity
            activeOpacity={1}
            onPress={() => {
              setDebugTapCount((previous) => {
                const next = previous + 1;
                if (previous < 7 && next === 7) {
                  Alert.alert("诊断模式已开启", "顶部「系统健康」区已展开完整后端能力与同步诊断信息。");
                }
                if (previous >= 7) {
                  // 已经处于解锁态，再点用于关闭。
                  Alert.alert("诊断模式已关闭", "顶部「系统健康」区已收起为精简视图。");
                  return 0;
                }
                return next;
              });
            }}
          >
            <Text style={styles.versionText}>
              益语智库 v1.0.4{debugUnlocked ? "  ·  dev" : ""}
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>

      {/* 账号设置仍保留，承载"当前账号信息只读展示 + 退出登录提示" */}
      <Modal
        visible={activeSettings === "account"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsAccount onClose={closeSettings} user={user} />
      </Modal>
      <Modal
        visible={activeSettings === "device"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsDevice onClose={closeSettings} />
      </Modal>
      <Modal
        visible={activeSettings === "about"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsAbout
          onClose={closeSettings}
          onClearCache={async () => {
            // 清掉用户主动可清的本地缓存：API 缓存 + 客户工作台/cockpit 缓存。
            // 同步队列里的 pending op 保留，避免误删未上传的工作。
            await cache.clearAll();
            await clearClientIntelCache({ allScopes: false });
          }}
        />
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.lg,
  },
  // Profile card —— "未装订宣纸公文"的入口。
  // 关键视觉信号：28pt 姓名大字 + 13pt 企业·部门紧贴下方（gap 仅 6）；
  // 头像 56pt 在右侧反相浓墨底（不抢戏）。
  profileCard: {
    backgroundColor: "transparent", // 不要卡片，让大字直接落在 canvas 上
    paddingTop: spacing.xxl, // 28，配合外层 paddingTop=40 共 ≈68 留白
    paddingHorizontal: 0,
    paddingBottom: spacing.xl,
  },
  profileRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  avatarContainer: {
    position: "relative",
    marginRight: spacing.lg, // 当前 JSX 顺序：头像左、姓名右，沿用
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: palette.airyBlue, // 滴答清单风格：airy blue 蓝底头像
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    shadowColor: palette.airyBlue,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.24,
    shadowRadius: 10,
    elevation: 4,
  },
  avatarText: {
    ...typography.titleCard,
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 20,
  },
  avatarImage: {
    width: 56,
    height: 56,
  },
  cameraOverlay: {
    position: "absolute",
    bottom: -2,
    right: -2,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: palette.paperRice,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: palette.borderSubtle,
  },
  cameraIcon: {
    fontSize: 12,
  },
  profileInfo: {
    flex: 1,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  profileName: {
    ...typography.titleHero, // 28/600/36 letter-spacing -0.2
    color: palette.inkBlack,
  },
  editButton: {
    padding: spacing.xs,
  },
  editIcon: {
    fontSize: 16,
    color: palette.textTertiary,
  },
  profileTitle: {
    ...typography.caption, // 13/400/18
    color: palette.textTertiary,
    marginTop: 6, // 紧贴姓名下方，制造层级反差
  },
  searchButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  searchIcon: {
    fontSize: 18,
  },

  // Sync card —— surface.card + hairline border 取代 shadow，朱砂/淡蓝换为烟灰白
  syncCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: palette.paperSmoke, // 烟灰白
    borderWidth: 1,
    borderColor: palette.borderSubtle, // hairline border
    borderRadius: borderRadius.lg, // 14
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    marginTop: spacing.md,
  },
  syncLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  syncCloudIcon: {
    fontSize: 22,
  },
  syncText: {
    ...typography.titleCard, // 17/600/24
    color: palette.inkBlack,
  },
  syncTime: {
    ...typography.caption, // 13/400/18
    color: palette.textTertiary,
    marginTop: 2,
  },
  syncButton: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: palette.inkBlack,
    borderRadius: borderRadius.sm, // 8
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  syncButtonText: {
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.inkBlack,
    fontWeight: "600",
  },

  // 系统健康卡 —— 同样 surface.card + hairline 取代 shadow
  healthCard: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12（比同步卡略小，做层级）
    padding: spacing.lg,
    marginTop: spacing.md,
  },
  healthTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  healthTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  healthSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  healthBadge: {
    backgroundColor: "rgba(199,149,109,0.10)", // 缃色 10% 底（数字 badge 唯一允许色）
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  healthBadgeText: {
    ...typography.label,
    color: palette.inkBronze,
    fontWeight: "600",
  },
  healthMetricsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  healthNoticeRow: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "rgba(239,68,68,0.08)",
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  healthNoticeText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.error,
    fontWeight: "600",
  },
  healthMetricPill: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  healthMetricLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  healthMetricValue: {
    marginTop: 2,
    fontSize: fontSize.lg,
    color: colors.text,
    fontWeight: "700",
  },
  healthMetricValueDanger: {
    color: colors.error,
  },
  healthBackendPanel: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    gap: spacing.xs,
  },
  healthActionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  healthActionButton: {
    minWidth: "31%",
    flexGrow: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  healthActionText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "600",
  },
  healthActionTextDisabled: {
    color: colors.textTertiary,
  },
  healthDebugPanel: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    gap: spacing.xs,
  },
  healthSubsection: {
    marginTop: spacing.xs,
    gap: spacing.xs,
  },
  healthDebugSectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  healthDebugList: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  healthDebugMetaDanger: {
    color: colors.error,
  },
  healthDebugRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
  },
  healthDebugCopy: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  healthDebugTitle: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "600",
  },
  healthDebugMeta: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },
  healthConflictCard: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    paddingTop: spacing.sm,
    gap: spacing.xs,
  },
  healthConflictActions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  healthConflictButton: {
    flex: 1,
    borderRadius: borderRadius.md,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  healthConflictButtonPrimary: {
    backgroundColor: colors.brandBg,
    borderColor: colors.brand,
  },
  healthConflictButtonDanger: {
    backgroundColor: "rgba(239,68,68,0.08)",
    borderColor: "rgba(239,68,68,0.28)",
  },
  healthConflictButtonDisabled: {
    backgroundColor: colors.surfaceSecondary,
    borderColor: colors.borderLight,
  },
  healthConflictButtonText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  healthConflictButtonTextPrimary: {
    color: colors.brand,
  },
  healthConflictButtonTextDanger: {
    color: colors.error,
  },
  healthConflictButtonTextDisabled: {
    color: colors.textTertiary,
  },
  healthFlagRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  healthFlagLabel: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  healthFlagToggle: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  healthFlagToggleEnabled: {
    backgroundColor: colors.brandBg,
  },
  healthFlagToggleDisabled: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  healthFlagToggleText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  healthFlagToggleTextDisabled: {
    color: colors.textSecondary,
  },

  // Section label —— 章节标题用 titlePage 22pt（"翻公文"感关键）
  sectionLabel: {
    ...typography.titlePage, // 22/600/30
    color: palette.inkBlack,
    marginTop: spacing.xxl, // 28
    marginBottom: spacing.md, // 12
    marginLeft: 0, // 左对齐到 screenPadding 而非缩进 4
  },

  // Settings card —— 5 行装在一张卡里，靠 hairline 分隔
  settingsCard: {
    backgroundColor: palette.paperSmoke, // 烟灰白
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12
    paddingHorizontal: spacing.lg, // 16
    paddingVertical: 0, // 行高 64 已经足够，不再加垂直 padding
    overflow: "hidden", // 首末行内圆角
  },
  feishuCalendarHintCard: {
    marginTop: spacing.md,
    backgroundColor: "rgba(91,123,254,0.08)",
    borderWidth: 1,
    borderColor: "rgba(91,123,254,0.18)",
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  feishuCalendarHintTitle: {
    ...typography.label,
    color: palette.inkBlue,
    fontWeight: "700",
  },
  feishuCalendarHintText: {
    ...typography.caption,
    color: palette.textSecondary,
    marginTop: spacing.xs,
    lineHeight: 19,
  },
  feishuCalendarHintLink: {
    ...typography.label,
    color: palette.inkBlue,
    fontWeight: "700",
    marginTop: spacing.sm,
  },
  // 入口行 —— 高 64，icon 占 layout.iconSlotWidth=52（含 gap），rightText 13pt
  settingsRow: {
    flexDirection: "row",
    alignItems: "center",
    height: layout.rowHeightEntry, // 64
    paddingVertical: 0,
  },
  /** @deprecated 旧"彩色背景方块" —— 设计方案去掉，保留以防漏改 */
  settingsIconBg: {
    width: 0,
    height: 0,
  },
  // 新的 icon 占位 —— 无背景方块，仅给 icon 摆位
  settingsIconSlot: {
    width: 36,
    alignItems: "flex-start",
    justifyContent: "center",
    marginRight: spacing.lg, // 16，与缩进 hairline 对齐
  },
  settingsIcon: {
    fontSize: 18,
  },
  settingsTextContainer: {
    flex: 1,
  },
  settingsTitle: {
    ...typography.bodyLarge, // 16/400/24
    color: palette.inkBlack,
    fontWeight: "500",
  },
  settingsSubtitle: {
    ...typography.caption, // 13/400/18
    color: palette.textTertiary,
    marginTop: 2,
  },
  settingsRightText: {
    ...typography.caption,
    color: palette.textTertiary,
    maxWidth: 140,
    textAlign: "right",
    marginRight: spacing.sm,
  },
  chevron: {
    fontSize: 18,
    color: palette.textTertiary,
  },
  // hairline 行间分隔 —— 左缩进 52（layout.iconSlotWidth）
  separator: {
    height: 0.5,
    backgroundColor: palette.borderDivider,
    marginLeft: layout.iconSlotWidth, // 52
  },

  // 退出 —— 唯一朱砂强调点：描边不填色，按下态 6% 朱砂底
  logoutButton: {
    backgroundColor: "transparent",
    borderRadius: borderRadius.md, // 12
    paddingVertical: spacing.lg, // 16
    alignItems: "center",
    marginTop: spacing.xxl, // 28
    borderWidth: 1,
    borderColor: palette.cinnabarBorder, // 朱砂 32% 透明描边
  },
  logoutText: {
    ...typography.bodyLarge, // 16/400/24
    color: palette.cinnabar,
    fontWeight: "500",
  },
  // 版本号 —— 居中 label 12/500，距底有呼吸
  versionText: {
    textAlign: "center",
    ...typography.label, // 12/500/16 letter-spacing 0.3
    color: palette.textTertiary,
    marginTop: spacing.xl, // 20
    marginBottom: spacing.xl,
  },

  // Edit profile modal
  editOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  editCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    width: "100%",
    maxWidth: 360,
    ...shadow.elevated,
  },
  editTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.xl,
    textAlign: "center",
  },
  editLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  editInput: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  editActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  editCancelButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: 10,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
  },
  editCancelText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  editSaveButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: 10,
    borderRadius: borderRadius.md,
    backgroundColor: colors.brand,
    minWidth: 72,
    alignItems: "center",
  },
  editSaveText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textOnBrand,
  },
});

export function ErrorBoundary(props: ErrorBoundaryProps) {
  return (
    <RouteErrorFallback
      {...props}
      label="profile"
      title="「我的」页暂时打不开"
      hint="刚才这个页面遇到了异常，你的账号与本地数据没有丢失。点下方按钮重试即可。"
    />
  );
}
