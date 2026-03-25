import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, RefreshCw, UploadCloud } from 'lucide-react';

import type { DiagnosisProfileGroupKey } from '../../lib/diagnosisProfiles';
import {
  DIAGNOSIS_PROFILE_GROUPS,
  getDiagnosisProfilesByGroup,
  parseDiagnosisProfileDocument,
  readDiagnosisProfileSelection,
  type DiagnosisProfileRecord,
  writeDiagnosisProfileSelection,
} from '../../lib/diagnosisProfiles';

type DiagnosisProfileSettingsPanelProps = {
  profiles: DiagnosisProfileRecord[];
  onPickFile: () => Promise<string[]>;
  onReadFile: (targetPath: string) => Promise<string>;
  onSaveProfiles: (profiles: DiagnosisProfileRecord[]) => Promise<void>;
  disabled?: boolean;
  focusGroup?: DiagnosisProfileGroupKey | null;
  focusLabel?: string;
  onDataChange?: () => void;
};

export function DiagnosisProfileSettingsPanel({
  profiles,
  onPickFile,
  onReadFile,
  onSaveProfiles,
  disabled = false,
  focusGroup = null,
  focusLabel = '',
  onDataChange,
}: DiagnosisProfileSettingsPanelProps) {
  const [selection, setSelection] = useState(() => readDiagnosisProfileSelection());
  const [uploadingKey, setUploadingKey] = useState<string | null>(null);
  const [draftLabels, setDraftLabels] = useState<Partial<Record<DiagnosisProfileGroupKey, string>>>({});
  const groupRefs = useRef<Partial<Record<DiagnosisProfileGroupKey, HTMLDivElement | null>>>({});
  const inputRefs = useRef<Partial<Record<DiagnosisProfileGroupKey, HTMLInputElement | null>>>({});

  useEffect(() => {
    setSelection(readDiagnosisProfileSelection());
  }, [focusGroup]);

  useEffect(() => {
    if (!focusGroup) return;
    const target = groupRefs.current[focusGroup];
    if (!target) return;
    target.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [focusGroup]);

  useEffect(() => {
    if (!focusGroup) return;
    if (!focusLabel.trim()) return;
    setDraftLabels((prev) => ({
      ...prev,
      [focusGroup]: focusLabel.trim(),
    }));
  }, [focusGroup, focusLabel]);

  const grouped = useMemo(
    () => Object.fromEntries(DIAGNOSIS_PROFILE_GROUPS.map((group) => [group.key, getDiagnosisProfilesByGroup(profiles, group.key)])) as Record<
      DiagnosisProfileGroupKey,
      DiagnosisProfileRecord[]
    >,
    [profiles],
  );

  const persistSelection = (nextSelection: Partial<Record<DiagnosisProfileGroupKey, string>>) => {
    setSelection(nextSelection);
    writeDiagnosisProfileSelection(nextSelection);
    onDataChange?.();
  };

  const uploadProfile = async (
    groupKey: DiagnosisProfileGroupKey,
    existing?: DiagnosisProfileRecord | null,
    explicitLabel?: string,
  ) => {
    setUploadingKey(existing?.id || groupKey);
    try {
      const label = (explicitLabel || existing?.label || draftLabels[groupKey] || '').trim();
      if (!label) {
        throw new Error(groupKey === 'platform_fundraising' ? '请先填写平台名称，再上传 MD 文档。' : groupKey === 'monthly_donor' ? '请先填写月捐人类型名称，再上传 MD 文档。' : '请先填写 Key Person 类型名称，再上传 MD 文档。');
      }
      const filePaths = await onPickFile();
      const filePath = filePaths[0];
      if (!filePath) return;
      if (!/\.(md|markdown|txt|docx|pdf)$/i.test(filePath)) {
        throw new Error('当前只支持 Markdown、DOCX、PDF 或 TXT。');
      }
      const text = await onReadFile(filePath);
      if (!text.trim()) {
        throw new Error('文档里没有抽出可用文本，请换一份更完整的文件。');
      }
      const fileName = filePath.split('/').pop() || 'uploaded.md';
      const nextRecord = parseDiagnosisProfileDocument(groupKey, label, text, fileName, filePath, existing?.id);
      const nextProfiles = [
        ...profiles.filter((item) => item.id !== nextRecord.id),
        nextRecord,
      ].sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'));
      await onSaveProfiles(nextProfiles);
      persistSelection({
        ...selection,
        [groupKey]: nextRecord.id,
      });
      setDraftLabels((prev) => ({
        ...prev,
        [groupKey]: nextRecord.label,
      }));
    } catch (error) {
      window.alert(error instanceof Error ? error.message : '画像文档上传失败');
    } finally {
      setUploadingKey(null);
    }
  };

  const focusDraftInput = (groupKey: DiagnosisProfileGroupKey) => {
    window.requestAnimationFrame(() => {
      inputRefs.current[groupKey]?.focus();
    });
  };

  const renderGroup = (groupKey: DiagnosisProfileGroupKey) => {
    const group = DIAGNOSIS_PROFILE_GROUPS.find((item) => item.key === groupKey);
    if (!group) return null;
    const items = grouped[groupKey];
    const isFocused = focusGroup === groupKey;
    const draftLabel = draftLabels[groupKey] || '';
    const suggestedLabels = group.suggestedLabels || [];
    return (
      <div
        key={group.key}
        ref={(node) => {
          groupRefs.current[group.key] = node;
        }}
        className={`bg-white border rounded-3xl p-6 shadow-sm ${isFocused ? 'border-blue-200 ring-2 ring-blue-100' : 'border-gray-100'}`}
      >
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">{group.label}</h2>
            <p className="text-[12px] text-gray-500 mt-1">{group.helper} 上传后会作为组织级共享画像供整个测试工作台复用。</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setDraftLabels((prev) => ({ ...prev, [group.key]: '' }));
                focusDraftInput(group.key);
              }}
              disabled={disabled}
              className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-[12px] font-semibold text-gray-600"
            >
              <Plus size={14} />
              更多
            </button>
            <button
              type="button"
              onClick={() => {
                void uploadProfile(group.key, null, draftLabel);
              }}
              disabled={disabled || !draftLabel.trim() || uploadingKey === group.key}
              className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-semibold text-white shadow-[0_10px_24px_-14px_rgba(91,123,254,0.55)] disabled:opacity-60"
            >
              {uploadingKey === group.key ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
              上传MD文档
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-4 mb-4">
          {suggestedLabels.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {suggestedLabels.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => {
                    setDraftLabels((prev) => ({ ...prev, [group.key]: label }));
                    focusDraftInput(group.key);
                  }}
                  disabled={disabled}
                  className={`rounded-xl px-3 py-2 text-[11px] font-semibold transition-colors ${
                    draftLabel === label
                      ? 'bg-[#EAF2FF] text-[#335CFF]'
                      : 'bg-white text-gray-600 border border-gray-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto] gap-3 items-center">
            <input
              ref={(node) => {
                inputRefs.current[group.key] = node;
              }}
              value={draftLabel}
              onChange={(event) => setDraftLabels((prev) => ({ ...prev, [group.key]: event.target.value }))}
              placeholder={group.key === 'platform_fundraising' ? '填写平台名称，例如：腾讯公益' : group.key === 'monthly_donor' ? '填写月捐人类型名称' : '填写 Key Person 类型名称'}
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE]/40"
              disabled={disabled}
            />
            <div className="text-[11px] text-gray-500">
              先填写名称，再上传 MD、DOCX、PDF 或 TXT
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {items.map((item) => {
            const isSelected = selection[group.key] === item.id;
            const isUploading = uploadingKey === item.id;
            return (
              <div key={item.id} className={`rounded-2xl border px-4 py-4 ${isSelected ? 'border-blue-200 bg-blue-50/50' : 'border-gray-100 bg-gray-50/50'}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[14px] font-bold text-gray-900">{item.label}</p>
                      {isSelected && <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-blue-100 text-[#335CFF]">当前默认</span>}
                    </div>
                    <p className="mt-2 text-[12px] leading-6 text-gray-600">{item.summary}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {item.corePreferences.slice(0, 2).map((tag) => (
                        <span key={tag} className="rounded-[8px] bg-white px-2 py-1 text-[10px] font-semibold text-gray-500 border border-gray-100">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-[11px] text-gray-400">{item.fileName} · {item.updatedAt.replace('T', ' ').slice(0, 16)}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => persistSelection({ ...selection, [group.key]: item.id })}
                      disabled={disabled}
                      className={`rounded-xl px-3 py-2 text-[11px] font-semibold border ${isSelected ? 'border-blue-200 bg-white text-[#335CFF]' : 'border-gray-200 bg-white text-gray-600'}`}
                    >
                      设为当前
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void uploadProfile(group.key, item);
                      }}
                      disabled={disabled}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-semibold text-gray-600"
                    >
                      {isUploading ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
                      替换文档
                    </button>
                  </div>
                </div>
              </div>
            );
          })}

          {items.length === 0 && (
            <div className="rounded-2xl border border-dashed border-gray-200 px-4 py-8 text-center text-[12px] text-gray-400">
              还没有已上传的{group.label}类型。
            </div>
          )}
        </div>
      </div>
    );
  };

  return <div className="space-y-6">{DIAGNOSIS_PROFILE_GROUPS.map((group) => renderGroup(group.key))}</div>;
}
