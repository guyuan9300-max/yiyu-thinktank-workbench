import React, { useRef, useState } from 'react';
import { ImagePlus, RefreshCw, Save, Trash2 } from 'lucide-react';

type BrandLogoMarkProps = {
  logoDataUrl?: string | null;
  className?: string;
};

export function BrandLogoMark({ logoDataUrl, className = 'w-8 h-8' }: BrandLogoMarkProps) {
  const normalized = logoDataUrl?.trim() || '';
  if (normalized) {
    return (
      <div className={`${className} shrink-0 overflow-hidden rounded-[18px] bg-white border border-gray-100 shadow-[0_8px_24px_rgba(37,99,235,0.12)]`}>
        <img src={normalized} alt="组织 Logo" className="w-full h-full object-contain" />
      </div>
    );
  }

  return (
    <div className={`${className} text-[#2563EB] flex shrink-0 items-center justify-center transition-transform hover:scale-105 duration-300`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full drop-shadow-sm">
        <rect x="3" y="3" width="18" height="18" rx="3.5" />
        <path d="M8 8h8v8H8z" />
        <path d="M12 8v8" />
        <path d="M8 12h8" />
        <circle cx="3" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="21" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="3" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="21" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}

type Props = {
  logoDataUrl?: string | null;
  canManage: boolean;
  busy: boolean;
  hasUnsavedChange: boolean;
  onPickLogo: (file: File) => Promise<void>;
  onClearDraft: () => void;
  onSave: () => Promise<void>;
};

export function BrandLogoSettingsCard({
  logoDataUrl,
  canManage,
  busy,
  hasUnsavedChange,
  onPickLogo,
  onClearDraft,
  onSave,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isPicking, setIsPicking] = useState(false);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setLocalError(null);
    setIsPicking(true);
    try {
      await onPickLogo(file);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : 'PNG 处理失败');
    } finally {
      setIsPicking(false);
    }
  }

  const pending = busy || isPicking;

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">品牌 Logo</h2>
          <p className="text-[12px] text-gray-500 mt-1">
            左上角品牌位支持上传透明背景 PNG。保存后会替换当前内置图标。
          </p>
        </div>
        <div className={`text-[11px] font-bold px-3 py-1.5 rounded-full border ${hasUnsavedChange ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-100 bg-slate-50 text-slate-600'}`}>
          {hasUnsavedChange ? '有未保存更改' : '已与当前生效稿一致'}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[160px_minmax(0,1fr)] gap-6 items-start">
        <div className="rounded-[28px] border border-gray-100 bg-gradient-to-br from-[#eef3ff] via-white to-[#f8fbff] p-5 flex flex-col items-center gap-3">
          <BrandLogoMark logoDataUrl={logoDataUrl} className="w-20 h-20" />
          <div className="text-center">
            <p className="text-[12px] font-bold text-gray-900">侧栏实时预览</p>
            <p className="text-[11px] text-gray-500 mt-1">建议使用方形 PNG</p>
          </div>
        </div>

        <div className="space-y-4">
          <input ref={inputRef} type="file" accept="image/png" className="hidden" onChange={(event) => void handleFileChange(event)} />

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[12px] font-bold text-slate-900">上传规则</p>
            <p className="text-[12px] text-slate-600 mt-2 leading-relaxed">
              仅支持 PNG。上传后会在前端压到不超过 256px 的方形边界，再保存进系统设置，避免把大图直接塞进配置。
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={() => inputRef.current?.click()}
              disabled={!canManage || pending}
            >
              {isPicking ? <RefreshCw size={15} className="animate-spin" /> : <ImagePlus size={15} />}
              {logoDataUrl ? '替换 PNG' : '上传 PNG'}
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-gray-200 text-[13px] font-bold text-gray-700 disabled:opacity-50"
              onClick={onClearDraft}
              disabled={!canManage || pending || !logoDataUrl}
            >
              <Trash2 size={15} />
              清空预览
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-[#5B7BFE] text-white text-[13px] font-bold shadow-sm disabled:opacity-50"
              onClick={() => void onSave()}
              disabled={!canManage || pending || !hasUnsavedChange}
            >
              {busy ? <RefreshCw size={15} className="animate-spin" /> : <Save size={15} />}
              保存 Logo
            </button>
          </div>

          {localError && (
            <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-[12px] text-rose-700">
              {localError}
            </div>
          )}

          {!canManage && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
              当前账号只能查看品牌 Logo，不能上传或替换。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
