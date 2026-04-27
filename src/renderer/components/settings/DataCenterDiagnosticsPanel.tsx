import React, { useEffect, useMemo, useState } from 'react';

import type { LlmHealthcheckResult, LlmProviderProbeResult, SourceIntegrityReport, WorkspaceChatDiagnostics } from '../../../shared/types';
import {
  getClientVectorIndexStatus,
  getDataCenterProposalDrafts,
  getSourceIntegrity,
  getWorkspaceChatDiagnostics,
  resetGenerationRuntimeStateV2,
  runLlmHealthcheck,
  runLlmProviderProbe,
  retryKnowledgeParseFailures,
} from '../../lib/api';

export function DataCenterDiagnosticsPanel({ clientId }: { clientId?: string | null }) {
  const [diagnostics, setDiagnostics] = useState<WorkspaceChatDiagnostics | null>(null);
  const [sourceIntegrity, setSourceIntegrity] = useState<SourceIntegrityReport | null>(null);
  const [healthcheck, setHealthcheck] = useState<LlmHealthcheckResult | null>(null);
  const [providerProbe, setProviderProbe] = useState<LlmProviderProbeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionText, setActionText] = useState('');

  const canLoad = Boolean(clientId && clientId.trim());

  const refresh = async () => {
    if (!canLoad || !clientId) return;
    setLoading(true);
    try {
      const [diag, source] = await Promise.all([
        getWorkspaceChatDiagnostics(clientId, 20),
        getSourceIntegrity(),
      ]);
      setDiagnostics(diag);
      setSourceIntegrity(source);
      setActionText('诊断数据已刷新');
    } catch (error) {
      setActionText(error instanceof Error ? error.message : '诊断刷新失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [clientId]);

  const summary = useMemo(() => {
    if (!diagnostics) return '';
    const generation = diagnostics.breakdown?.generation?.status || 'ok';
    const evidence = diagnostics.breakdown?.evidenceQuality?.status || 'ok';
    return `generation=${generation} / evidence=${evidence}`;
  }, [diagnostics]);

  if (!canLoad || !clientId) return null;

  return (
    <div className="mt-5 rounded-2xl border border-gray-100 bg-gray-50 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[12px] font-bold text-gray-800">DataCenter Diagnostics</p>
          <p className="text-[11px] text-gray-500">{summary || '加载中...'}</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
          disabled={loading}
        >
          {loading ? '刷新中…' : '刷新'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        <button
          type="button"
          onClick={() => {
            void resetGenerationRuntimeStateV2({ clientId, resetScope: 'client' })
              .then(() => setActionText('已重置 runtime 状态'))
              .catch((error) => setActionText(error instanceof Error ? error.message : '重置失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Reset runtime
        </button>
        <button
          type="button"
          onClick={() => {
            void retryKnowledgeParseFailures(clientId)
              .then((result) => setActionText(`parse retry: 成功 ${result.succeeded} / 失败 ${result.failed}`))
              .catch((error) => setActionText(error instanceof Error ? error.message : '重试失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Retry parse failures
        </button>
        <button
          type="button"
          onClick={() => {
            void getDataCenterProposalDrafts({ clientId, limit: 20 })
              .then((rows) => setActionText(`proposal drafts: ${rows.length}`))
              .catch((error) => setActionText(error instanceof Error ? error.message : '读取草稿失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Open proposal drafts
        </button>
        <button
          type="button"
          onClick={() => {
            void getClientVectorIndexStatus(clientId)
              .then((result) => setActionText(`vector index: ${result.status}`))
              .catch((error) => setActionText(error instanceof Error ? error.message : '读取向量状态失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Open vector index status
        </button>
        <button
          type="button"
          onClick={() => {
            void getSourceIntegrity()
              .then((result) => {
                setSourceIntegrity(result);
                setActionText(result.match ? 'source integrity: match' : 'source integrity: mismatch');
              })
              .catch((error) => setActionText(error instanceof Error ? error.message : '读取 source integrity 失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Open source integrity
        </button>
        <button
          type="button"
          onClick={() => {
            void runLlmHealthcheck()
              .then((result) => {
                setHealthcheck(result);
                setActionText(result.success ? `healthcheck: ${result.provider}/${result.model} 正常` : `healthcheck: ${result.errorKind || 'unknown'}`);
              })
              .catch((error) => setActionText(error instanceof Error ? error.message : 'healthcheck 失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Test current model
        </button>
        <button
          type="button"
          onClick={() => {
            void runLlmProviderProbe({ clientId, providers: ['doubao', 'qwen'] })
              .then((result) => {
                setProviderProbe(result);
                setActionText(`provider probe: ${result.results.length}`);
              })
              .catch((error) => setActionText(error instanceof Error ? error.message : 'provider probe 失败'));
          }}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100"
        >
          Probe providers
        </button>
      </div>

      <div className="text-[11px] text-gray-500 space-y-1">
        {actionText ? <p>{actionText}</p> : null}
        {sourceIntegrity && sourceIntegrity.match === false ? (
          <p className="text-amber-700">源码与运行包不一致：{sourceIntegrity.warning || '请检查运行路径'}</p>
        ) : null}
        {diagnostics?.dominantLlmErrorKind ? (
          <p>dominant llm error: {diagnostics.dominantLlmErrorKind}</p>
        ) : null}
        {healthcheck ? (
          <p className={healthcheck.success ? 'text-emerald-700' : 'text-rose-700'}>
            healthcheck: {healthcheck.provider}/{healthcheck.model} · {healthcheck.success ? `ok (${healthcheck.latencyMs}ms)` : `${healthcheck.errorKind || 'unknown'}${healthcheck.error ? ` · ${healthcheck.error}` : ''}`}
          </p>
        ) : null}
        {providerProbe?.results?.length ? (
          <p>
            provider probe: {providerProbe.results.map((item) => `${item.provider}:${item.success ? 'ok' : (item.errorKind || 'fail')}`).join(' / ')}
          </p>
        ) : null}
        {diagnostics?.rootCauseSummary?.length ? (
          <p>root causes: {diagnostics.rootCauseSummary.slice(0, 2).join('；')}</p>
        ) : null}
      </div>
    </div>
  );
}
