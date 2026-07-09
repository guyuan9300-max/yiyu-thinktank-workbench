import React, { useEffect, useState } from 'react';
import { RefreshCw, CheckCircle2, AlertCircle, RotateCcw, Bell, Download } from 'lucide-react';
import type { DesktopAppInfo, OfficialPushUpdatePayload, UpdateEventPayload } from '../../../shared/types';
import { OFFICIAL_PUSH_STATE_EVENT, UPDATE_STATE_KEY } from '../UpdateNotifier';

interface Props {
  desktopAppInfo: DesktopAppInfo | null;
}

type UpdateUiState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'standard-available'; version?: string }
  | { kind: 'downloading'; version?: string; percent?: number }
  | { kind: 'downloaded'; version?: string }
  | { kind: 'official-push'; push: OfficialPushUpdatePayload; installing?: boolean }
  | { kind: 'official-push-opened'; version?: string | null; fileName?: string | null }
  | { kind: 'up-to-date'; checkedAt: number }
  | { kind: 'error'; message: string };

const UPDATE_FEED_LABEL = '益语官方火山云 TOS';

function formatPercent(percent: number | undefined): string {
  if (typeof percent !== 'number' || !Number.isFinite(percent)) return '0%';
  return `${Math.max(0, Math.min(100, percent)).toFixed(0)}%`;
}

function formatSize(sizeBytes: number | null | undefined): string | null {
  if (typeof sizeBytes !== 'number' || !Number.isFinite(sizeBytes) || sizeBytes <= 0) return null;
  if (sizeBytes >= 1024 * 1024 * 1024) return `${(sizeBytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`;
}

function pushRelationLabel(relation: OfficialPushUpdatePayload['relation']): string {
  if (relation === 'upgrade') return '升级版本';
  if (relation === 'downgrade') return '回退版本';
  if (relation === 'switch-custom') return '组织定制版';
  if (relation === 'different') return '指定版本';
  return '官方推送';
}

function initialUpdateState(): UpdateUiState {
  const cachedPush = typeof window !== 'undefined' ? window[UPDATE_STATE_KEY]?.officialPush : null;
  return cachedPush ? { kind: 'official-push', push: cachedPush } : { kind: 'idle' };
}

export function AboutAppSettingsPanel({ desktopAppInfo }: Props): React.ReactElement {
  const [updateState, setUpdateState] = useState<UpdateUiState>(() => initialUpdateState());
  const [checkBusy, setCheckBusy] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);

  useEffect(() => {
    const subscribe = window.yiyuWorkbench?.onUpdateEvent;
    if (typeof subscribe !== 'function') return;
    const unsubscribe = subscribe((payload: UpdateEventPayload) => {
      switch (payload.kind) {
        case 'checking':
          setUpdateState({ kind: 'checking' });
          return;
        case 'available':
          setUpdateState({ kind: 'standard-available', version: payload.version });
          return;
        case 'download-progress':
          setUpdateState((prev) =>
            prev.kind === 'downloading'
              ? { ...prev, percent: payload.percent }
              : { kind: 'downloading', percent: payload.percent },
          );
          return;
        case 'downloaded':
          setUpdateState({ kind: 'downloaded', version: payload.version });
          return;
        case 'official-push-available':
          if (payload.officialPush) setUpdateState({ kind: 'official-push', push: payload.officialPush });
          return;
        case 'official-push-not-available':
          setUpdateState({ kind: 'up-to-date', checkedAt: Date.now() });
          return;
        case 'not-available':
          setUpdateState({ kind: 'up-to-date', checkedAt: Date.now() });
          return;
        case 'error':
          setUpdateState({ kind: 'error', message: payload.message ?? '未知错误' });
          return;
        default:
          return;
      }
    });
    return unsubscribe;
  }, []);

  const handleCheck = async () => {
    const trigger = window.yiyuWorkbench?.checkForUpdates;
    if (typeof trigger !== 'function') return;
    setCheckBusy(true);
    setUpdateState({ kind: 'checking' });
    try {
      const result = await trigger();
      if (!result.ok) {
        setUpdateState({ kind: 'error', message: result.reason ?? '检查失败' });
      }
    } finally {
      setCheckBusy(false);
    }
  };

  const handleRestart = async () => {
    const trigger = window.yiyuWorkbench?.quitAndInstallUpdate;
    if (typeof trigger !== 'function') return;
    setRestartBusy(true);
    const result = await trigger();
    if (!result.ok) {
      setRestartBusy(false);
      setUpdateState({ kind: 'error', message: result.reason ?? '重启失败' });
    }
  };

  const handleDownloadStandardUpdate = async () => {
    const trigger = window.yiyuWorkbench?.downloadStandardUpdate;
    if (typeof trigger !== 'function') {
      setUpdateState({ kind: 'error', message: '当前安装包还不支持确认下载更新，请先安装迁移版本。' });
      return;
    }
    const version = updateState.kind === 'standard-available' ? updateState.version : undefined;
    setUpdateState({ kind: 'downloading', version });
    const result = await trigger();
    if (!result.ok) {
      setUpdateState({ kind: 'error', message: result.reason ?? '下载更新失败' });
    }
  };

  const handleInstallOfficialPush = async (push: OfficialPushUpdatePayload) => {
    const trigger = window.yiyuWorkbench?.installOfficialPushUpdate;
    if (typeof trigger !== 'function') {
      setUpdateState({ kind: 'error', message: '当前安装包还不支持安装官方推送，请先安装迁移版本。' });
      return;
    }
    setUpdateState({ kind: 'official-push', push, installing: true });
    const result = await trigger();
    if (!result.ok) {
      setUpdateState({ kind: 'error', message: result.reason ?? '安装推送版本失败' });
      return;
    }
    setUpdateState({ kind: 'official-push-opened', version: result.version ?? push.version, fileName: result.fileName ?? push.fileName ?? null });
  };

  const handleDismissOfficialPush = () => {
    if (typeof window !== 'undefined' && window[UPDATE_STATE_KEY]) {
      window[UPDATE_STATE_KEY]!.officialPush = null;
      window.dispatchEvent(new CustomEvent(OFFICIAL_PUSH_STATE_EVENT, { detail: null }));
    }
    setUpdateState({ kind: 'idle' });
  };

  const appVersion = desktopAppInfo?.appVersion ?? '未知';
  const platformLabel = desktopAppInfo
    ? `${desktopAppInfo.platform} · ${desktopAppInfo.arch}${desktopAppInfo.isPackaged ? '' : ' · 开发模式'}`
    : '—';
  const channelLabel = desktopAppInfo?.updateChannel === 'beta' ? 'Beta 通道' : '稳定通道';
  const lastCheckLabel = updateState.kind === 'up-to-date'
    ? new Date(updateState.checkedAt).toLocaleString('zh-CN', { hour12: false })
    : updateState.kind === 'checking'
      ? '正在检查'
      : updateState.kind === 'error'
        ? '检查失败'
        : '尚未手动检查';

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div className="rounded-2xl border border-gray-100 bg-white p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">ABOUT</p>
            <h2 className="mt-2 text-[20px] font-light tracking-tight text-gray-900">关于本软件</h2>
            <p className="mt-1.5 text-[12px] text-gray-500">
              益语智库自用平台 V2.0 · 桌面版
            </p>
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">当前版本</dt>
            <dd className="mt-1 text-[15px] font-medium text-gray-900">{appVersion}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">运行环境</dt>
            <dd className="mt-1 text-[13px] text-gray-700">{platformLabel}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">更新通道</dt>
            <dd className="mt-1 text-[13px] text-gray-700">{channelLabel}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">更新源</dt>
            <dd className="mt-1 text-[13px] text-gray-700">{UPDATE_FEED_LABEL}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">最近检查</dt>
            <dd className="mt-1 text-[13px] text-gray-700">{lastCheckLabel}</dd>
          </div>
          {desktopAppInfo?.frontendBuildVersion && (
            <div>
              <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-gray-400">构建版本</dt>
              <dd className="mt-1 truncate text-[12px] text-gray-500" title={desktopAppInfo.frontendBuildVersion}>
                {desktopAppInfo.frontendBuildVersion}
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-6">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">UPDATES</p>
        <h3 className="mt-2 text-[18px] font-light tracking-tight text-gray-900">软件更新</h3>
        <p className="mt-1.5 text-[12px] leading-relaxed text-gray-500">
          软件采用静默更新:启动后会自动检查、后台下载并在下次自然退出应用时安装,正常情况下你不需要做任何操作。
          下面的按钮提供"立刻检查"和"现在就重启完成更新"两种主动入口。
        </p>

        <div className="mt-5 space-y-3">
          {updateState.kind === 'checking' && (
            <div className="flex items-center gap-2 rounded-md bg-gray-50 px-3 py-2 text-[12px] text-gray-600">
              <RefreshCw size={14} className="animate-spin" />
              正在检查更新…
            </div>
          )}
          {updateState.kind === 'downloading' && (
            <div className="rounded-md bg-indigo-50 px-3 py-2 text-[12px] text-indigo-700">
              正在后台下载新版本{updateState.version ? ` ${updateState.version}` : ''}
              {typeof updateState.percent === 'number' && (
                <span className="ml-2 font-medium">{formatPercent(updateState.percent)}</span>
              )}
            </div>
          )}
          {updateState.kind === 'standard-available' && (
            <div className="flex items-start gap-2 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-[12px] text-blue-800">
              <Bell size={14} className="mt-[2px] shrink-0" />
              <span>
                发现新版本{updateState.version ? ` ${updateState.version}` : ''}。确认后才会开始下载，下载完成后可重启安装。
              </span>
            </div>
          )}
          {updateState.kind === 'downloaded' && (
            <div className="flex items-start gap-2 rounded-md bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              <CheckCircle2 size={14} className="mt-[2px] shrink-0" />
              <span>
                新版本 {updateState.version} 已下载完成。下次自然退出应用时会自动安装;
                如果想立刻使用,点下方"立即重启更新"。
              </span>
            </div>
          )}
          {updateState.kind === 'official-push-opened' && (
            <div className="flex items-start gap-2 rounded-md bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              <CheckCircle2 size={14} className="mt-[2px] shrink-0" />
              <span>
                版本 {updateState.version || ''} 的安装包已下载并打开
                {updateState.fileName ? `（${updateState.fileName}）` : ''}。请按系统提示完成安装或解压。
              </span>
            </div>
          )}
          {updateState.kind === 'official-push' && (
            <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-3 text-[12px] text-blue-800">
              <div className="flex items-start gap-2">
                <Bell size={15} className="mt-[2px] shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{updateState.push.title}</span>
                    <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                      {pushRelationLabel(updateState.push.relation)}
                    </span>
                  </div>
                  <p className="mt-1 leading-relaxed text-blue-700/90">
                    当前安装版本 {updateState.push.currentVersion}，推送版本 {updateState.push.version}
                    {updateState.push.releaseVersion && updateState.push.releaseVersion !== updateState.push.version
                      ? `（安装底版 ${updateState.push.releaseVersion}）`
                      : ''}
                    {formatSize(updateState.push.sizeBytes) ? ` · ${formatSize(updateState.push.sizeBytes)}` : ''}。
                    {updateState.push.relation === 'downgrade'
                      ? '这是官方指定的回退版本，适合测试或组织临时回滚。'
                      : updateState.push.packageKind === 'custom'
                        ? '这是益语智库为你所在组织指派的定制版本。'
                        : updateState.push.organizationCode
                          ? '这是益语智库官方特地推送给你所在组织的版本。'
                          : '这是益语智库官方发布的安装包。'}
                  </p>
                  <p className="mt-1 text-[11px] text-blue-600/80">
                    检查更新只读取版本信息；点下方按钮后才会下载安装包。
                  </p>
                </div>
              </div>
            </div>
          )}
          {updateState.kind === 'up-to-date' && (
            <div className="flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              <CheckCircle2 size={14} />
              当前已经是最新版本。
            </div>
          )}
          {updateState.kind === 'error' && (
            <div className="flex items-start gap-2 rounded-md bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
              <AlertCircle size={14} className="mt-[2px] shrink-0" />
              <span className="break-words">检查更新失败:{updateState.message}</span>
            </div>
          )}
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleCheck}
            disabled={checkBusy || updateState.kind === 'checking' || updateState.kind === 'downloading'}
            className="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-[13px] font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw size={14} className={checkBusy || updateState.kind === 'checking' ? 'animate-spin' : ''} />
            检查更新
          </button>
          {updateState.kind === 'standard-available' && (
            <button
              type="button"
              onClick={handleDownloadStandardUpdate}
              className="inline-flex items-center gap-2 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#4A6AEF]"
            >
              <Download size={14} />
              下载并准备更新
            </button>
          )}
          {updateState.kind === 'official-push' && (
            <>
              <button
                type="button"
                onClick={() => handleInstallOfficialPush(updateState.push)}
                disabled={updateState.installing}
                className="inline-flex items-center gap-2 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#4A6AEF] disabled:opacity-60"
              >
                <Download size={14} />
                {updateState.installing ? '正在准备…' : '下载安装包'}
              </button>
              <button
                type="button"
                onClick={handleDismissOfficialPush}
                className="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-[13px] font-medium text-gray-600 hover:bg-gray-50"
              >
                暂不安装
              </button>
            </>
          )}
          {updateState.kind === 'downloaded' && (
            <button
              type="button"
              onClick={handleRestart}
              disabled={restartBusy}
              className="inline-flex items-center gap-2 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#4A6AEF] disabled:opacity-60"
            >
              <RotateCcw size={14} />
              {restartBusy ? '正在重启…' : '立即重启更新'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
