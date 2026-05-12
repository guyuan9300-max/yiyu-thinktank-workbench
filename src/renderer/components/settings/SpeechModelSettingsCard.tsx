import { useEffect, useMemo, useState } from 'react';
import { Headphones, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

import type {
  SpeechModelSettings,
  SpeechModelSettingsPayload,
  SpeechModelTestResult,
} from '../../../shared/types';
import {
  SPEECH_MODEL_PROVIDERS,
  findSpeechProvider,
} from '../../../shared/speechModelProviders';
import { LocalAsrModelPanel } from './LocalAsrModelPanel';

interface SpeechModelSettingsCardProps {
  settings: SpeechModelSettings | null;
  canEdit: boolean;
  isSaving: boolean;
  onSave: (payload: SpeechModelSettingsPayload) => Promise<void>;
  onTest: (payload: SpeechModelSettingsPayload) => Promise<SpeechModelTestResult>;
}

function buildEmptyDraft(): SpeechModelSettingsPayload {
  return {
    provider: '',
    credentials: {},
    modelId: '',
    extraConfig: {},
    enabled: false,
  };
}

function settingsToDraft(settings: SpeechModelSettings | null): SpeechModelSettingsPayload {
  if (!settings) return buildEmptyDraft();
  // 给当前 provider 的 extraFields 补默认值，避免已存配置缺新字段（如 cluster）导致提交空值
  const descriptor = findSpeechProvider(settings.provider);
  const defaultExtras: Record<string, string> = {};
  if (descriptor) {
    for (const f of descriptor.extraFields) defaultExtras[f.key] = f.defaultValue;
  }
  return {
    provider: settings.provider || '',
    credentials: { ...(settings.credentials || {}) },
    modelId: settings.modelId || '',
    extraConfig: { ...defaultExtras, ...(settings.extraConfig || {}) },
    enabled: Boolean(settings.enabled),
  };
}

export function SpeechModelSettingsCard({
  settings,
  canEdit,
  isSaving,
  onSave,
  onTest,
}: SpeechModelSettingsCardProps) {
  const [draft, setDraft] = useState<SpeechModelSettingsPayload>(() => settingsToDraft(settings));
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SpeechModelTestResult | null>(null);

  useEffect(() => {
    setDraft(settingsToDraft(settings));
    setTestResult(null);
  }, [settings?.provider, settings?.modelId, settings?.enabled, settings?.updatedAt]);

  const descriptor = useMemo(() => findSpeechProvider(draft.provider), [draft.provider]);
  const isSupported = Boolean(descriptor?.supported);

  const setProvider = (nextId: string) => {
    const next = findSpeechProvider(nextId);
    if (!next) {
      setDraft({ provider: nextId, credentials: {}, modelId: '', extraConfig: {}, enabled: false });
      setTestResult(null);
      return;
    }
    // 切 provider 时清空老凭证，按新 descriptor 默认填一份
    const defaultExtras: Record<string, string> = {};
    for (const f of next.extraFields) defaultExtras[f.key] = f.defaultValue;
    setDraft({
      provider: next.id,
      credentials: {},
      modelId: next.models[0]?.id || '',
      extraConfig: defaultExtras,
      enabled: false,
    });
    setTestResult(null);
  };

  const setCredentialField = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, credentials: { ...prev.credentials, [key]: value } }));
    setTestResult(null);
  };

  const setExtraField = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, extraConfig: { ...prev.extraConfig, [key]: value } }));
  };

  const setModelId = (value: string) => {
    setDraft((prev) => ({ ...prev, modelId: value }));
    setTestResult(null);
  };

  const setEnabled = (value: boolean) => {
    setDraft((prev) => ({ ...prev, enabled: value }));
  };

  const handleSave = async () => {
    await onSave(draft);
  };

  const handleTest = async () => {
    if (!draft.provider) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(draft);
      setTestResult(result);
    } catch (error) {
      setTestResult({
        success: false,
        message: error instanceof Error ? error.message : '测试连接失败（网络错误）',
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Headphones size={18} className="text-[#5B7BFE]" />
            <h2 className="text-[16px] font-bold text-gray-900">语音识别模型 · 用于语音转文字</h2>
          </div>
          <p className="text-[12px] text-gray-500 mt-1">
            配置后即可在客户工作台直接上传 .m4a / .mp3 / .wav 等录音文件，系统自动转写为文字资料入库。
            不同客户可选用不同服务商，凭证只保存在本机。
          </p>
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving || !draft.provider}
            className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? '保存中…' : '保存语音模型配置'}
          </button>
        )}
      </div>

      <div className="space-y-3">
        <label className="text-[12px] font-bold text-gray-700">服务商</label>
        <select
          value={draft.provider}
          onChange={(e) => setProvider(e.target.value)}
          disabled={!canEdit}
          className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE] disabled:bg-gray-50"
        >
          <option value="">— 请选择服务商 —</option>
          {SPEECH_MODEL_PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
              {!p.supported ? ' · 敬请期待' : ''}
            </option>
          ))}
        </select>
        {descriptor && (
          <p className="text-[12px] text-gray-500">{descriptor.description}</p>
        )}
        {descriptor && !descriptor.supported && (
          <div className="flex items-start gap-2 rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-[12px] text-amber-700">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <span>{descriptor.unsupportedHint || '此服务商暂未支持，敬请期待。'}</span>
          </div>
        )}
      </div>

      {descriptor && descriptor.id === 'local_sensevoice' && (
        <div className="border-t border-gray-100 pt-4">
          <LocalAsrModelPanel canEdit={canEdit} />
        </div>
      )}

      {descriptor && descriptor.credentialFields.length > 0 && (
        <>
          <div className="space-y-3 border-t border-gray-100 pt-4">
            <p className="text-[12px] font-bold text-gray-700">鉴权凭证</p>
            {descriptor.credentialFields.map((field) => (
              <div key={field.key} className="space-y-1.5">
                <label className="text-[12px] text-gray-600">{field.label}</label>
                <input
                  type={field.type === 'password' ? 'password' : 'text'}
                  value={draft.credentials[field.key] || ''}
                  onChange={(e) => setCredentialField(field.key, e.target.value)}
                  placeholder={field.placeholder || ''}
                  disabled={!canEdit}
                  className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE] focus:bg-white disabled:bg-gray-100"
                />
                {field.helper && <p className="text-[11px] text-gray-400">{field.helper}</p>}
              </div>
            ))}
          </div>

          {descriptor.models.length > 0 && (
            <div className="space-y-1.5 border-t border-gray-100 pt-4">
              <label className="text-[12px] font-bold text-gray-700">具体模型</label>
              <select
                value={draft.modelId}
                onChange={(e) => setModelId(e.target.value)}
                disabled={!canEdit}
                className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE] disabled:bg-gray-50"
              >
                {descriptor.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
              {descriptor.models.find((m) => m.id === draft.modelId)?.description && (
                <p className="text-[11px] text-gray-400">
                  {descriptor.models.find((m) => m.id === draft.modelId)?.description}
                </p>
              )}
            </div>
          )}

          {descriptor.extraFields.length > 0 && (
            <div className="space-y-3 border-t border-gray-100 pt-4">
              <p className="text-[12px] font-bold text-gray-700">高级选项</p>
              {descriptor.extraFields.map((field) => (
                <div key={field.key} className="space-y-1.5">
                  <label className="text-[12px] text-gray-600">{field.label}</label>
                  <select
                    value={draft.extraConfig[field.key] || field.defaultValue}
                    onChange={(e) => setExtraField(field.key, e.target.value)}
                    disabled={!canEdit}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-900 outline-none focus:border-[#5B7BFE] disabled:bg-gray-50"
                  >
                    {field.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  {field.helper && <p className="text-[11px] text-gray-400">{field.helper}</p>}
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3 border-t border-gray-100 pt-4">
            <label className="inline-flex items-center gap-2 text-[12px] font-medium text-gray-700">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                disabled={!canEdit}
              />
              启用语音识别（保存后客户工作台才能上传录音）
            </label>
          </div>

          <div className="flex items-center gap-3 border-t border-gray-100 pt-4">
            <button
              type="button"
              onClick={() => void handleTest()}
              disabled={testing || !canEdit || !draft.provider || !isSupported}
              className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[12px] font-bold text-gray-700 hover:border-[#5B7BFE] hover:text-[#5B7BFE] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw size={14} className={testing ? 'animate-spin' : ''} />
              {testing ? '测试中…' : '测试连接'}
            </button>
            {testResult && (
              <div
                className={`flex items-start gap-2 rounded-2xl border px-3 py-2 text-[12px] ${
                  testResult.success
                    ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                    : 'border-rose-100 bg-rose-50 text-rose-700'
                }`}
              >
                {testResult.success ? (
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle size={14} className="mt-0.5 shrink-0" />
                )}
                <div className="space-y-0.5">
                  <p className="font-medium">{testResult.message}</p>
                  {testResult.detail && (
                    <p className="text-[11px] opacity-80">{testResult.detail}</p>
                  )}
                  {typeof testResult.latencyMs === 'number' && (
                    <p className="text-[11px] opacity-70">耗时 {Math.round(testResult.latencyMs)} ms</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {!canEdit && (
        <p className="text-[12px] text-amber-700 bg-amber-50 border border-amber-100 rounded-2xl px-4 py-3">
          当前账号没有修改模型配置的权限，仅可查看。
        </p>
      )}
    </div>
  );
}
