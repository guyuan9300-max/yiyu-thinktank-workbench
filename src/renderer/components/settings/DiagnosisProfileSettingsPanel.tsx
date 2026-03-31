import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Globe, PencilLine, RefreshCw, Sparkles, UploadCloud } from 'lucide-react';

import type { DeepDnaDraft, DeepDnaRecord, DiagnosisProfileRecord } from '../../shared/types';
import type { DiagnosisProfileGroupKey } from '../../lib/diagnosisProfiles';
import {
  DIAGNOSIS_PROFILE_GROUPS,
  readDiagnosisProfileSelection,
  writeDiagnosisProfileSelection,
} from '../../lib/diagnosisProfiles';

type ManualFormState = {
  label: string;
  identitySummary: string;
  corePreferencesText: string;
  supportTriggersText: string;
  redFlagsText: string;
  evidencePreferencesText: string;
  voiceStyleText: string;
  commonQuestionsText: string;
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
};

type DiagnosisProfileSettingsPanelProps = {
  profiles: DiagnosisProfileRecord[];
  deepDnaLibrary: DeepDnaRecord[];
  onPickFile: () => Promise<string[]>;
  onReadFile: (targetPath: string) => Promise<string>;
  onCreateManualRecord: (payload: {
    groupKey: DiagnosisProfileGroupKey;
    label: string;
    identitySummary: string;
    corePreferencesText: string;
    supportTriggersText: string;
    redFlagsText: string;
    evidencePreferencesText: string;
    voiceStyleText: string;
    commonQuestionsText: string;
    authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
  }) => Promise<DeepDnaRecord>;
  onImportDocument: (payload: {
    groupKey: DiagnosisProfileGroupKey;
    label: string;
    fileName: string;
    filePath: string;
    content: string;
    authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
  }) => Promise<DeepDnaRecord>;
  onCreateWebDraft: (payload: {
    groupKey: DiagnosisProfileGroupKey;
    label: string;
    searchQuery: string;
  }) => Promise<DeepDnaDraft>;
  onPublishDraft: (id: string) => Promise<DeepDnaRecord>;
  disabled?: boolean;
  focusGroup?: DiagnosisProfileGroupKey | null;
  focusLabel?: string;
  onDataChange?: () => void;
};

function createManualForm(label = ''): ManualFormState {
  return {
    label,
    identitySummary: '',
    corePreferencesText: '',
    supportTriggersText: '',
    redFlagsText: '',
    evidencePreferencesText: '',
    voiceStyleText: '',
    commonQuestionsText: '',
    authorizationStatus: 'authorized_internal',
  };
}

function formatUpdatedAt(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-CN', { hour12: false, month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function authorizationLabel(value: DeepDnaRecord['authorizationStatus']) {
  if (value === 'public') return '公开资料';
  if (value === 'restricted') return '受限资料';
  return '内部已授权';
}

function confidenceTone(value: DeepDnaRecord['confidenceLevel']) {
  if (value === 'high') return 'bg-emerald-50 text-emerald-600';
  if (value === 'low') return 'bg-rose-50 text-rose-600';
  return 'bg-amber-50 text-amber-600';
}

function dedupeById(records: DeepDnaRecord[]) {
  const seen = new Set<string>();
  return records.filter((record) => {
    if (seen.has(record.id)) return false;
    seen.add(record.id);
    return true;
  });
}

export function DiagnosisProfileSettingsPanel({
  profiles,
  deepDnaLibrary,
  onPickFile,
  onReadFile,
  onCreateManualRecord,
  onImportDocument,
  onCreateWebDraft,
  onPublishDraft,
  disabled = false,
  focusGroup = null,
  focusLabel = '',
  onDataChange,
}: DiagnosisProfileSettingsPanelProps) {
  const [selection, setSelection] = useState(() => readDiagnosisProfileSelection());
  const [draftLabels, setDraftLabels] = useState<Partial<Record<DiagnosisProfileGroupKey, string>>>({});
  const [webQueries, setWebQueries] = useState<Partial<Record<DiagnosisProfileGroupKey, string>>>({});
  const [manualForms, setManualForms] = useState<Partial<Record<DiagnosisProfileGroupKey, ManualFormState>>>({});
  const [manualOpen, setManualOpen] = useState<Partial<Record<DiagnosisProfileGroupKey, boolean>>>({});
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const groupRefs = useRef<Partial<Record<DiagnosisProfileGroupKey, HTMLDivElement | null>>>({});

  useEffect(() => {
    setSelection(readDiagnosisProfileSelection());
  }, [profiles, deepDnaLibrary.length]);

  useEffect(() => {
    if (!focusGroup) return;
    groupRefs.current[focusGroup]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [focusGroup]);

  useEffect(() => {
    if (!focusGroup || !focusLabel.trim()) return;
    setDraftLabels((prev) => ({ ...prev, [focusGroup]: focusLabel.trim() }));
    setManualForms((prev) => ({
      ...prev,
      [focusGroup]: {
        ...(prev[focusGroup] || createManualForm(focusLabel.trim())),
        label: focusLabel.trim(),
      },
    }));
  }, [focusGroup, focusLabel]);

  const groupedRecords = useMemo(
    () =>
      Object.fromEntries(
        DIAGNOSIS_PROFILE_GROUPS.map((group) => [
          group.key,
          dedupeById(
            deepDnaLibrary
              .filter((record) => record.groupKey === group.key)
              .sort((left, right) => {
                if (left.status !== right.status) return left.status === 'published' ? -1 : 1;
                return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
              }),
          ),
        ]),
      ) as Record<DiagnosisProfileGroupKey, DeepDnaRecord[]>,
    [deepDnaLibrary],
  );

  const persistSelection = (groupKey: DiagnosisProfileGroupKey, profileId: string) => {
    const nextSelection = { ...selection, [groupKey]: profileId };
    setSelection(nextSelection);
    writeDiagnosisProfileSelection(nextSelection);
    onDataChange?.();
  };

  const runWithPending = async (key: string, task: () => Promise<void>) => {
    setPendingKey(key);
    try {
      await task();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : '保存失败');
    } finally {
      setPendingKey(null);
    }
  };

  const handleImportDocument = async (groupKey: DiagnosisProfileGroupKey) => {
    const label = (draftLabels[groupKey] || manualForms[groupKey]?.label || '').trim();
    if (!label) {
      window.alert('请先填写对象名称，再导入文档。');
      return;
    }
    await runWithPending(`${groupKey}:import`, async () => {
      const filePaths = await onPickFile();
      const filePath = filePaths[0];
      if (!filePath) return;
      const fileName = filePath.split('/').pop() || 'uploaded.txt';
      const content = await onReadFile(filePath);
      if (!content.trim()) {
        throw new Error('文档里没有抽出可用文本，请换一份更完整的文件。');
      }
      const saved = await onImportDocument({
        groupKey,
        label,
        fileName,
        filePath,
        content,
        authorizationStatus: manualForms[groupKey]?.authorizationStatus || 'authorized_internal',
      });
      persistSelection(groupKey, saved.id);
      setDraftLabels((prev) => ({ ...prev, [groupKey]: saved.label }));
      setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || createManualForm(saved.label)), label: saved.label } }));
    });
  };

  const handleCreateWebDraft = async (groupKey: DiagnosisProfileGroupKey) => {
    const label = (draftLabels[groupKey] || manualForms[groupKey]?.label || '').trim();
    const searchQuery = (webQueries[groupKey] || label).trim();
    if (!label || !searchQuery) {
      window.alert('请先填写对象名称和联网检索描述。');
      return;
    }
    await runWithPending(`${groupKey}:web`, async () => {
      await onCreateWebDraft({ groupKey, label, searchQuery });
      onDataChange?.();
    });
  };

  const handlePublishDraft = async (groupKey: DiagnosisProfileGroupKey, recordId: string) => {
    await runWithPending(`${recordId}:publish`, async () => {
      const saved = await onPublishDraft(recordId);
      persistSelection(groupKey, saved.id);
    });
  };

  const handleSaveManual = async (groupKey: DiagnosisProfileGroupKey) => {
    const form = manualForms[groupKey] || createManualForm(draftLabels[groupKey] || '');
    if (!form.label.trim()) {
      window.alert('请先填写对象名称。');
      return;
    }
    await runWithPending(`${groupKey}:manual`, async () => {
      const saved = await onCreateManualRecord({
        groupKey,
        label: form.label.trim(),
        identitySummary: form.identitySummary,
        corePreferencesText: form.corePreferencesText,
        supportTriggersText: form.supportTriggersText,
        redFlagsText: form.redFlagsText,
        evidencePreferencesText: form.evidencePreferencesText,
        voiceStyleText: form.voiceStyleText,
        commonQuestionsText: form.commonQuestionsText,
        authorizationStatus: form.authorizationStatus,
      });
      persistSelection(groupKey, saved.id);
      setDraftLabels((prev) => ({ ...prev, [groupKey]: saved.label }));
    });
  };

  const renderGroup = (groupKey: DiagnosisProfileGroupKey) => {
    const group = DIAGNOSIS_PROFILE_GROUPS.find((item) => item.key === groupKey);
    if (!group) return null;
    const records = groupedRecords[groupKey];
    const form = manualForms[groupKey] || createManualForm(draftLabels[groupKey] || '');
    const isManualOpen = Boolean(manualOpen[groupKey]);
    const selectedId = selection[groupKey];
    return (
      <div
        key={groupKey}
        ref={(node) => {
          groupRefs.current[groupKey] = node;
        }}
        className={`rounded-3xl border bg-white p-6 shadow-sm ${focusGroup === groupKey ? 'border-blue-200 ring-2 ring-blue-100' : 'border-gray-100'}`}
      >
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">{group.label}</h2>
            <p className="text-[12px] text-gray-500 mt-1">{group.helper} 现在支持导入文档、联网草稿和手动建档，都会统一落成同一份 Deep DNA。</p>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-4 mb-5 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3">
            <input
              value={draftLabels[groupKey] || form.label}
              onChange={(event) => {
                const nextLabel = event.target.value;
                setDraftLabels((prev) => ({ ...prev, [groupKey]: nextLabel }));
                setManualForms((prev) => ({
                  ...prev,
                  [groupKey]: {
                    ...(prev[groupKey] || createManualForm(nextLabel)),
                    label: nextLabel,
                  },
                }));
              }}
              placeholder={group.key === 'platform_fundraising' ? '对象名称，例如：腾讯公益' : group.key === 'monthly_donor' ? '对象名称，例如：续捐犹豫月捐人' : '对象名称，例如：企业 CSR 负责人'}
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE]/40"
              disabled={disabled}
            />
            <input
              value={webQueries[groupKey] || ''}
              onChange={(event) => setWebQueries((prev) => ({ ...prev, [groupKey]: event.target.value }))}
              placeholder="联网检索描述，例如：平台偏好、规则、捐赠人反馈"
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE]/40"
              disabled={disabled}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setManualOpen((prev) => ({ ...prev, [groupKey]: !isManualOpen }))}
              disabled={disabled}
              className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-[12px] font-semibold text-gray-700"
            >
              <PencilLine size={14} />
              {isManualOpen ? '收起手动建档' : '手动填写'}
            </button>
            <button
              type="button"
              onClick={() => void handleImportDocument(groupKey)}
              disabled={disabled || pendingKey === `${groupKey}:import`}
              className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-semibold text-white shadow-[0_10px_24px_-14px_rgba(91,123,254,0.55)] disabled:opacity-60"
            >
              {pendingKey === `${groupKey}:import` ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
              导入文档
            </button>
            <button
              type="button"
              onClick={() => void handleCreateWebDraft(groupKey)}
              disabled={disabled || pendingKey === `${groupKey}:web`}
              className="inline-flex items-center gap-2 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-2.5 text-[12px] font-semibold text-[#335CFF] disabled:opacity-60"
            >
              {pendingKey === `${groupKey}:web` ? <RefreshCw size={14} className="animate-spin" /> : <Globe size={14} />}
              联网草稿
            </button>
          </div>

          {isManualOpen && (
            <div className="rounded-2xl border border-blue-100 bg-white p-4 space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <textarea
                  value={form.identitySummary}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), identitySummary: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="基础身份：这个对象是谁，目前处在什么位置。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
                <textarea
                  value={form.corePreferencesText}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), corePreferencesText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="核心偏好：分行填写，例如“更看重真实感和用途清晰”。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
                <textarea
                  value={form.supportTriggersText}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), supportTriggersText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="支持触发器：什么会促使 TA 愿意支持。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
                <textarea
                  value={form.redFlagsText}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), redFlagsText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="红线与反感点：哪些表达会伤害判断。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
                <textarea
                  value={form.evidencePreferencesText}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), evidencePreferencesText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="证据偏好：TA 更认什么类型的事实、预算、证明材料。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
                <textarea
                  value={form.voiceStyleText}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), voiceStyleText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                  placeholder="说话风格：TA 更适合怎样的语言和口吻。"
                  className="min-h-[110px] rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                  disabled={disabled}
                />
              </div>
              <textarea
                value={form.commonQuestionsText}
                onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), commonQuestionsText: event.target.value, label: draftLabels[groupKey] || form.label } }))}
                placeholder="常问问题：分行填写，帮助后续建议更贴近真实判断。"
                className="min-h-[110px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12.5px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE]/40"
                disabled={disabled}
              />
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={form.authorizationStatus}
                  onChange={(event) => setManualForms((prev) => ({ ...prev, [groupKey]: { ...(prev[groupKey] || form), authorizationStatus: event.target.value as ManualFormState['authorizationStatus'], label: draftLabels[groupKey] || form.label } }))}
                  className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] font-semibold text-gray-700 outline-none"
                  disabled={disabled}
                >
                  <option value="authorized_internal">内部已授权</option>
                  <option value="public">公开资料</option>
                  <option value="restricted">受限资料</option>
                </select>
                <button
                  type="button"
                  onClick={() => void handleSaveManual(groupKey)}
                  disabled={disabled || pendingKey === `${groupKey}:manual`}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#0A53CC] px-4 py-3 text-[12px] font-semibold text-white shadow-[0_10px_24px_-14px_rgba(10,83,204,0.55)] disabled:opacity-60"
                >
                  {pendingKey === `${groupKey}:manual` ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  保存为对象档案
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-3">
          {records.map((record) => {
            const isSelected = selectedId === record.id;
            const isDraft = record.status === 'draft';
            const linkedProfile = profiles.find((profile) => (profile.deepDnaId || profile.id) === record.id);
            return (
              <div key={record.id} className={`rounded-2xl border px-4 py-4 ${isSelected ? 'border-blue-200 bg-blue-50/50' : 'border-gray-100 bg-gray-50/50'}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[14px] font-bold text-gray-900">{record.label}</p>
                      <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${confidenceTone(record.confidenceLevel)}`}>
                        {record.confidenceLevel === 'high' ? '高把握' : record.confidenceLevel === 'low' ? '低把握' : '中等把握'} · {record.confidenceScore}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">
                        {authorizationLabel(record.authorizationStatus)}
                      </span>
                      {isDraft && <span className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-600">联网草稿</span>}
                      {isSelected && <span className="rounded-full bg-blue-100 px-2 py-1 text-[10px] font-bold text-[#335CFF]">当前默认</span>}
                    </div>
                    <p className="mt-2 text-[12px] leading-6 text-gray-600">{record.identitySummary}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {[...record.corePreferences, ...record.redFlags].slice(0, 5).map((tag) => (
                        <span key={`${record.id}:${tag}`} className="rounded-[8px] border border-gray-100 bg-white px-2 py-1 text-[10px] font-semibold text-gray-500">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="mt-3 text-[11px] text-gray-400">
                      {linkedProfile?.fileName || record.sources[0]?.fileName || 'Deep DNA'} · {formatUpdatedAt(record.updatedAt)}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {!isDraft ? (
                      <button
                        type="button"
                        onClick={() => persistSelection(groupKey, record.id)}
                        disabled={disabled}
                        className={`rounded-xl px-3 py-2 text-[11px] font-semibold border ${isSelected ? 'border-blue-200 bg-white text-[#335CFF]' : 'border-gray-200 bg-white text-gray-600'}`}
                      >
                        设为当前
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void handlePublishDraft(groupKey, record.id)}
                        disabled={disabled || pendingKey === `${record.id}:publish`}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-amber-200 bg-white px-3 py-2 text-[11px] font-semibold text-amber-700 disabled:opacity-60"
                      >
                        {pendingKey === `${record.id}:publish` ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
                        发布草稿
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {records.length === 0 && (
            <div className="rounded-2xl border border-dashed border-gray-200 px-4 py-8 text-center text-[12px] text-gray-400">
              还没有这个分组的对象档案。你可以先导入文档、生成联网草稿，或者手动填写。
            </div>
          )}
        </div>
      </div>
    );
  };

  return <div className="space-y-6">{DIAGNOSIS_PROFILE_GROUPS.map((group) => renderGroup(group.key))}</div>;
}
