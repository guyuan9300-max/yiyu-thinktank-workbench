/**
 * device-preferences.ts —— 手机端"设备级偏好"集中管理。
 *
 * 按"手机端不做组织/系统配置"原则，这里只放跟单台设备使用习惯相关的开关：
 *   - 流量保护：仅 WiFi 下传/下载附件录音
 *   - 勿扰时段：本地通知静默时段
 *   - 主题：跟随系统 / 浅色 / 深色（实际换色板留待主题 PR 单独落地）
 *
 * 跨设备不需要同步，因此只用 AsyncStorage；后端无需感知。
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Network from "expo-network";

const KEYS = {
  wifiOnlyDownload: "yiyu_pref_wifi_only_download",
  doNotDisturbEnabled: "yiyu_pref_dnd_enabled",
  doNotDisturbStart: "yiyu_pref_dnd_start", // "22:00"
  doNotDisturbEnd: "yiyu_pref_dnd_end", // "07:00"
  themeMode: "yiyu_pref_theme_mode",
} as const;

export type ThemeMode = "system" | "light" | "dark";

export interface DevicePreferences {
  wifiOnlyDownload: boolean;
  doNotDisturbEnabled: boolean;
  doNotDisturbStart: string; // "HH:MM"
  doNotDisturbEnd: string;
  themeMode: ThemeMode;
}

const DEFAULTS: DevicePreferences = {
  wifiOnlyDownload: false,
  doNotDisturbEnabled: false,
  doNotDisturbStart: "22:00",
  doNotDisturbEnd: "07:00",
  themeMode: "system",
};

function isValidThemeMode(value: string | null): value is ThemeMode {
  return value === "system" || value === "light" || value === "dark";
}

function isValidTime(value: string | null): boolean {
  return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}

export async function loadDevicePreferences(): Promise<DevicePreferences> {
  const entries = await AsyncStorage.multiGet([
    KEYS.wifiOnlyDownload,
    KEYS.doNotDisturbEnabled,
    KEYS.doNotDisturbStart,
    KEYS.doNotDisturbEnd,
    KEYS.themeMode,
  ]);
  const map = Object.fromEntries(entries) as Record<string, string | null>;
  const themeRaw = map[KEYS.themeMode];
  return {
    wifiOnlyDownload: map[KEYS.wifiOnlyDownload] === "1",
    doNotDisturbEnabled: map[KEYS.doNotDisturbEnabled] === "1",
    doNotDisturbStart: isValidTime(map[KEYS.doNotDisturbStart])
      ? (map[KEYS.doNotDisturbStart] as string)
      : DEFAULTS.doNotDisturbStart,
    doNotDisturbEnd: isValidTime(map[KEYS.doNotDisturbEnd])
      ? (map[KEYS.doNotDisturbEnd] as string)
      : DEFAULTS.doNotDisturbEnd,
    themeMode: isValidThemeMode(themeRaw) ? themeRaw : DEFAULTS.themeMode,
  };
}

export async function setWifiOnlyDownload(value: boolean): Promise<void> {
  await AsyncStorage.setItem(KEYS.wifiOnlyDownload, value ? "1" : "0");
}

export async function setDoNotDisturbEnabled(value: boolean): Promise<void> {
  await AsyncStorage.setItem(KEYS.doNotDisturbEnabled, value ? "1" : "0");
}

export async function setDoNotDisturbStart(value: string): Promise<void> {
  if (!isValidTime(value)) throw new Error("时段格式应为 HH:MM");
  await AsyncStorage.setItem(KEYS.doNotDisturbStart, value);
}

export async function setDoNotDisturbEnd(value: string): Promise<void> {
  if (!isValidTime(value)) throw new Error("时段格式应为 HH:MM");
  await AsyncStorage.setItem(KEYS.doNotDisturbEnd, value);
}

export async function setThemeMode(value: ThemeMode): Promise<void> {
  await AsyncStorage.setItem(KEYS.themeMode, value);
}

/**
 * 下载侧检查：当前网络是否允许下载附件/录音。
 * 用户开了"仅 WiFi" 且当前不是 WiFi 时返回 false。其他情况一律 true。
 *
 * 这是个开放策略 —— 拉不到网络状态时按"允许"处理，避免离线时全面阻断。
 */
export async function shouldAllowMediaDownload(): Promise<{
  allow: boolean;
  reason: "wifi_only_cellular" | "wifi_only_offline" | null;
}> {
  let wifiOnly = false;
  try {
    const raw = await AsyncStorage.getItem(KEYS.wifiOnlyDownload);
    wifiOnly = raw === "1";
  } catch {
    return { allow: true, reason: null };
  }
  if (!wifiOnly) return { allow: true, reason: null };

  try {
    const state = await Network.getNetworkStateAsync();
    if (!state.isConnected) {
      return { allow: false, reason: "wifi_only_offline" };
    }
    if (state.type === Network.NetworkStateType.WIFI) {
      return { allow: true, reason: null };
    }
    return { allow: false, reason: "wifi_only_cellular" };
  } catch {
    // 网络探测失败时按允许处理，避免完全锁死。
    return { allow: true, reason: null };
  }
}

/**
 * 推送/提醒侧检查：当前时间是否在勿扰时段内。
 * 跨午夜的时段（如 22:00 - 07:00）也正确处理。
 */
export async function isInsideDoNotDisturbWindow(now: Date = new Date()): Promise<boolean> {
  let enabled = false;
  let start = DEFAULTS.doNotDisturbStart;
  let end = DEFAULTS.doNotDisturbEnd;
  try {
    const entries = await AsyncStorage.multiGet([
      KEYS.doNotDisturbEnabled,
      KEYS.doNotDisturbStart,
      KEYS.doNotDisturbEnd,
    ]);
    const map = Object.fromEntries(entries) as Record<string, string | null>;
    enabled = map[KEYS.doNotDisturbEnabled] === "1";
    if (isValidTime(map[KEYS.doNotDisturbStart])) start = map[KEYS.doNotDisturbStart] as string;
    if (isValidTime(map[KEYS.doNotDisturbEnd])) end = map[KEYS.doNotDisturbEnd] as string;
  } catch {
    return false;
  }
  if (!enabled) return false;

  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  const cur = now.getHours() * 60 + now.getMinutes();
  const s = sh * 60 + sm;
  const e = eh * 60 + em;
  if (s === e) return false;
  if (s < e) {
    // 同日窗口：22:00 - 23:30
    return cur >= s && cur < e;
  }
  // 跨午夜窗口：22:00 - 07:00 → cur >= 22:00 或 cur < 07:00
  return cur >= s || cur < e;
}
