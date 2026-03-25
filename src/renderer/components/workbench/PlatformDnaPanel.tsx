import React from 'react';
import { CheckCircle2, FileText, RefreshCw, UploadCloud } from 'lucide-react';

import type { PlatformDnaProfileDefinition, PlatformDnaProfileDocument, PlatformDnaProfileKey } from './platformDnaProfiles';

type PlatformDnaPanelProps = {
  profiles: PlatformDnaProfileDefinition[];
  documents: Partial<Record<PlatformDnaProfileKey, PlatformDnaProfileDocument>>;
  selectedKey: PlatformDnaProfileKey;
  onSelect: (key: PlatformDnaProfileKey) => void;
  onUpload: (key: PlatformDnaProfileKey) => void;
  uploadingKey: PlatformDnaProfileKey | null;
  showModeHint?: boolean;
};

export function PlatformDnaPanel({
  profiles,
  documents,
  selectedKey,
  onSelect,
  onUpload,
  uploadingKey,
  showModeHint = true,
}: PlatformDnaPanelProps) {
  return (
    <div className="px-3 pb-3">
      <div className="rounded-[16px] border border-black/[0.05] bg-white p-4 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.2)]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">平台 DNA</p>
            <h3 className="mt-2 text-[15px] font-semibold tracking-tight text-black/90">上传平台判断底稿</h3>
            <p className="mt-2 text-[12px] leading-6 text-black/52">
              当前支持 Markdown、DOCX、PDF 和 TXT。上传后会把平台偏好、风险触发点和语气偏好注入筹款测试。
            </p>
          </div>
          <div className="rounded-[10px] bg-[#EEF2FF] px-2 py-1 text-[10px] font-semibold text-[#4A64D6]">MD</div>
        </div>

        {showModeHint && (
          <div className="mt-3 rounded-[12px] border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-[11px] leading-5 text-black/48">
            这组平台 DNA 主要用于“平台筹款”模式。月捐人和 Key Person 仍建议用各自对象画像单独判断。
          </div>
        )}

        <div className="mt-4 space-y-3">
          {profiles.map((profile) => {
            const document = documents[profile.key];
            const isSelected = profile.key === selectedKey;
            const isUploading = uploadingKey === profile.key;
            return (
              <button
                key={profile.key}
                type="button"
                onClick={() => onSelect(profile.key)}
                className={`w-full rounded-[14px] border p-3 text-left transition-all ${
                  isSelected
                    ? 'border-[#5B7BFE]/20 bg-[#EAF2FF] shadow-[inset_0_0_0_1px_rgba(91,123,254,0.12)]'
                    : 'border-black/[0.06] bg-[#F8F9FB] hover:bg-black/[0.02]'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className={`text-[13px] tracking-tight ${isSelected ? 'font-semibold text-[#0A53CC]' : 'font-medium text-black/88'}`}>
                        {profile.shortLabel}
                      </p>
                      {document?.fileName && (
                        <span className="rounded-[6px] bg-white/80 px-1.5 py-0.5 text-[10px] font-semibold text-black/45">
                          {document.fileName}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[12px] leading-6 text-black/50">{document?.summary || profile.helper}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {document?.corePreferences.slice(0, 2).map((item) => (
                        <span key={item} className="rounded-[6px] bg-black/[0.04] px-2 py-0.5 text-[10px] font-semibold text-black/45">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      document ? 'bg-emerald-50 text-emerald-600' : 'bg-black/[0.05] text-black/40'
                    }`}>
                      {document ? '已上传' : '未上传'}
                    </span>
                    {isSelected && <CheckCircle2 className="h-4 w-4 text-[#5B7BFE]" />}
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-[11px] text-black/40">
                    <FileText className="h-3.5 w-3.5" />
                    <span>{document?.updatedAt ? `更新于 ${document.updatedAt.replace('T', ' ').slice(0, 16)}` : '等待上传平台 DNA 文档'}</span>
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onUpload(profile.key);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-[8px] border border-black/[0.06] bg-white px-3 py-1.5 text-[11px] font-semibold text-black/65 hover:bg-black/[0.02]"
                  >
                    {isUploading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <UploadCloud className="h-3.5 w-3.5" />}
                    {document ? '替换' : '上传'}
                  </button>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
