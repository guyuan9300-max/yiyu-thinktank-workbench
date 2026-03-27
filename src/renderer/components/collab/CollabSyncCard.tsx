import React from 'react';
import { Download, FolderOpen, RefreshCw, UploadCloud } from 'lucide-react';
import type { CollabRepoStatus } from '../../../shared/types';

type CollabSyncCardProps = {
  collapsed: boolean;
  status: CollabRepoStatus | null;
  loading: boolean;
  busyAction: 'push' | 'pull' | 'rebuild' | null;
  onRevealRepo: () => void;
  onPreviewPush: () => void;
  onPreviewPull: () => void;
};

function actionLabel(status: CollabRepoStatus | null) {
  if (!status?.isConfigured) return '点击任一主按钮后，会先帮你绑定源码目录。';
  if (!status.isValid) return '当前目录无效，点击主按钮时会提示你重新选择。';
  return status.statusText;
}

export function CollabSyncCard({
  collapsed,
  status,
  loading,
  busyAction,
  onRevealRepo,
  onPreviewPush,
  onPreviewPull,
}: CollabSyncCardProps) {
  const actionDisabled = loading || busyAction !== null;

  if (collapsed) {
    return (
      <div className="px-3 pb-4 hidden md:block">
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-2 flex flex-col items-center gap-2">
          <button
            type="button"
            className="w-10 h-10 rounded-2xl border border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50 disabled:opacity-50"
            onClick={onPreviewPush}
            disabled={actionDisabled}
            title="提交并推送我的修改"
          >
            {busyAction === 'push' ? <RefreshCw size={16} className="mx-auto animate-spin" /> : <UploadCloud size={16} className="mx-auto" />}
          </button>
          <button
            type="button"
            className="w-10 h-10 rounded-2xl border border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50 disabled:opacity-50"
            onClick={onPreviewPull}
            disabled={actionDisabled}
            title="预览并同步最新版本"
          >
            {busyAction === 'pull' ? <RefreshCw size={16} className="mx-auto animate-spin" /> : <Download size={16} className="mx-auto" />}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 pb-4 hidden md:block">
      <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm space-y-3">
        <div>
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">协作同步</p>
          <p className="mt-1 text-[13px] font-bold text-gray-800">
            {status?.repoName || '尚未绑定源码目录'}
          </p>
          <p className="mt-1 text-[11px] text-gray-500 leading-5">{actionLabel(status)}</p>
        </div>

        {status?.isConfigured && status?.isValid && (
          <div className="rounded-2xl border border-gray-100 bg-gray-50 px-3 py-3 text-[11px] text-gray-600">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white px-2.5 py-1 font-bold text-gray-700 border border-gray-200">
                {status.branch || '未知分支'}
              </span>
              <span>本地 {status.localChangeCount} 项改动</span>
              <span>远端领先 {status.behindCount}</span>
            </div>
            {status.repoPath && (
              <button
                type="button"
                className="mt-2 inline-flex items-center gap-1 text-[#5B7BFE] font-bold hover:text-[#4a6be6]"
                onClick={onRevealRepo}
              >
                <FolderOpen size={12} />
                在 Finder 中显示源码目录
              </button>
            )}
          </div>
        )}

        {!status?.isConfigured && status?.suggestedRepoPath && (
          <div className="rounded-2xl border border-blue-100 bg-blue-50/70 px-3 py-3 text-[11px] text-[#4256C5] leading-5">
            <p className="font-bold">已检测到推荐源码目录</p>
            <p className="mt-1 break-all">{status.suggestedRepoPath}</p>
            <p className="mt-2 text-[11px] text-[#5B7BFE]">直接点下面任一主按钮，就会围绕这个仓库继续。</p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-2">
          <button
            type="button"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-3 text-[12px] font-bold text-white shadow-sm hover:bg-[#4a6be6] disabled:opacity-60 disabled:cursor-not-allowed"
            onClick={onPreviewPush}
            disabled={actionDisabled}
          >
            {busyAction === 'push' ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
            提交并推送我的修改
          </button>
          <button
            type="button"
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] font-bold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60 disabled:cursor-not-allowed"
            onClick={onPreviewPull}
            disabled={actionDisabled}
          >
            {busyAction === 'pull' ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
            预览并同步最新版本
          </button>
        </div>
      </div>
    </div>
  );
}
