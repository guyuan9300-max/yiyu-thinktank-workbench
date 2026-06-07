import { useEffect } from 'react';
import type { OfficialPushUpdatePayload, UpdateEventPayload } from '../../shared/types';

/**
 * 飞书式无感更新:本组件不在主界面渲染任何 UI。
 * 仅订阅 autoUpdater IPC 事件,把状态写入 window 上的临时槽位 +
 * console.log,方便:
 *   - 设置页"关于本软件"区拉取最新更新状态(版本/进度/已就绪)
 *   - 排查时翻 macOS Console 日志诊断更新链路
 *
 * 用户感知:
 *   - 启动后 10 秒静默检查 → 有新版静默后台下载 →
 *     差分下载几秒完成 → 等用户下次自然退出应用时自动替换 .app →
 *     下次打开就是新版,菜单可能多了新功能,无任何弹窗/进度条/重启提示
 *
 * 急着用新功能的用户,可去设置页"关于本软件"手动【检查更新】或
 * 在有 pending 更新时点【立即重启更新】快进。
 */

export const UPDATE_STATE_KEY = '__yiyuUpdateState__';
export const OFFICIAL_PUSH_STATE_EVENT = 'yiyu-official-push-state-changed';

interface CachedUpdateState {
  lastEvent: UpdateEventPayload | null;
  latestVersion: string | null;
  downloadedVersion: string | null;
  isDownloaded: boolean;
  isDownloading: boolean;
  lastError: string | null;
  officialPush: OfficialPushUpdatePayload | null;
}

declare global {
  interface Window {
    [UPDATE_STATE_KEY]?: CachedUpdateState;
  }
}

function ensureSlot(): CachedUpdateState {
  if (!window[UPDATE_STATE_KEY]) {
    window[UPDATE_STATE_KEY] = {
      lastEvent: null,
      latestVersion: null,
      downloadedVersion: null,
      isDownloaded: false,
      isDownloading: false,
      lastError: null,
      officialPush: null,
    };
  }
  return window[UPDATE_STATE_KEY]!;
}

function notifyOfficialPushStateChanged(push: OfficialPushUpdatePayload | null): void {
  window.dispatchEvent(new CustomEvent(OFFICIAL_PUSH_STATE_EVENT, { detail: push }));
}

export function setCachedOfficialPush(push: OfficialPushUpdatePayload | null): void {
  const slot = ensureSlot();
  slot.officialPush = push;
  slot.lastEvent = {
    kind: push ? 'official-push-available' : 'official-push-not-available',
    version: push?.version,
    officialPush: push,
  };
  if (push) {
    slot.latestVersion = push.version;
    slot.lastError = null;
  }
  notifyOfficialPushStateChanged(push);
}

export function UpdateNotifier(): null {
  useEffect(() => {
    const subscribe = window.yiyuWorkbench?.onUpdateEvent;
    if (typeof subscribe !== 'function') return;

    const unsubscribe = subscribe((payload: UpdateEventPayload) => {
      const slot = ensureSlot();
      slot.lastEvent = payload;
      switch (payload.kind) {
        case 'official-push-available':
          setCachedOfficialPush(payload.officialPush ?? null);
          slot.latestVersion = payload.officialPush?.version ?? payload.version ?? slot.latestVersion;
          slot.isDownloading = false;
          slot.lastError = null;
          console.log('[updater] official push available:', payload.officialPush?.title || payload.version);
          return;
        case 'official-push-not-available':
          setCachedOfficialPush(null);
          slot.isDownloading = false;
          return;
        case 'available':
          slot.latestVersion = payload.version ?? slot.latestVersion;
          slot.isDownloading = true;
          slot.lastError = null;
          console.log('[updater] new version available, starting silent download:', payload.version);
          return;
        case 'download-progress':
          slot.isDownloading = true;
          return;
        case 'downloaded':
          slot.downloadedVersion = payload.version ?? slot.latestVersion;
          slot.isDownloaded = true;
          slot.isDownloading = false;
          slot.lastError = null;
          console.log('[updater] downloaded silently, will install on next app quit:', payload.version);
          return;
        case 'not-available':
          slot.isDownloading = false;
          return;
        case 'error':
          slot.isDownloading = false;
          slot.lastError = payload.message ?? 'unknown update error';
          console.warn('[updater] error (silent, user not notified):', payload.message);
          return;
        case 'checking':
        default:
          return;
      }
    });

    return unsubscribe;
  }, []);

  return null;
}
