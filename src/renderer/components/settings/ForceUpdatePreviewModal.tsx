import React from 'react';
import { ShieldAlert, RotateCcw } from 'lucide-react';

/**
 * 强制更新阻断弹窗。本阶段为纯界面预览(可关闭以便查看)。
 * 接入数据后:由 update-policy 返回的 forceUpdate=true 触发, 全屏遮罩不可关,
 * 用户只能点「立即重启更新」。
 */

interface ForceUpdatePreviewModalProps {
  open: boolean;
  version?: string;
  onClose: () => void;
  preview?: boolean;
}

export function ForceUpdatePreviewModal({
  open,
  version = '0.2.3',
  onClose,
  preview = true,
}: ForceUpdatePreviewModalProps): React.ReactElement | null {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 px-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-7 shadow-xl">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-50">
            <ShieldAlert size={20} className="text-amber-600" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">REQUIRED UPDATE</p>
            <h3 className="mt-0.5 text-[18px] font-light tracking-tight text-gray-900">本次为必须更新</h3>
          </div>
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-gray-600">
          新版本 <span className="font-medium text-gray-900">v{version}</span> 包含与云端同步所需的重要变更,
          需要重启完成更新后才能继续使用。更新已在后台下载完成,点击下方按钮即可立即重启。
        </p>
        <div className="mt-6 flex items-center justify-end gap-3">
          {preview && (
            <button
              type="button"
              onClick={onClose}
              className="text-[12px] text-gray-400 hover:text-gray-600"
            >
              关闭预览
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-2 rounded-md bg-[#5B7BFE] px-5 py-2.5 text-[13px] font-medium text-white hover:bg-[#4A6AEF]"
          >
            <RotateCcw size={14} />
            立即重启更新
          </button>
        </div>
        {preview && (
          <p className="mt-4 text-center text-[10px] text-gray-400">界面预览 · 正式版此弹窗不可关闭</p>
        )}
      </div>
    </div>
  );
}
