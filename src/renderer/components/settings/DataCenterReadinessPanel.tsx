import React, { useEffect, useMemo, useState } from 'react';

import type {
  WorkspaceContextRefreshEvent,
  WorkspaceDataCenterReadiness,
  WorkspaceDataCenterReadinessActionResult,
  WorkspaceDataCenterReadinessActionType,
  WorkspaceDataCenterReadinessFix,
  WorkspaceDocumentProcessingStatus,
} from '../../../shared/types';
import {
  getWorkspaceDataCenterReadiness,
  runWorkspaceDataCenterReadinessAction,
} from '../../lib/api';

type DocumentFilter = 'all' | 'failed' | 'missing_index';
type MessageTone = 'info' | 'success' | 'error';

function parseStatusClass(status: string) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'ready' || normalized === 'chunk_indexed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (normalized === 'partial_ready') return 'border-sky-200 bg-sky-50 text-sky-700';
  if (normalized === 'queued' || normalized === 'running' || normalized === 'processing' || normalized === 'parsing') {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }
  return 'border-rose-200 bg-rose-50 text-rose-700';
}

function vectorStatusClass(status: string | null | undefined) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'ready') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (normalized === 'building' || normalized === 'pending' || normalized === 'queued' || normalized === 'running') {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }
  if (!normalized || normalized === 'unknown') return 'border-gray-200 bg-gray-100 text-gray-700';
  return 'border-rose-200 bg-rose-50 text-rose-700';
}

function refreshStatusClass(status: WorkspaceContextRefreshEvent['status']) {
  if (status === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700';
  if (status === 'queued' || status === 'running') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-gray-200 bg-gray-100 text-gray-700';
}

function toneClass(tone: MessageTone) {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (tone === 'error') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-gray-200 bg-gray-50 text-gray-700';
}

function actionLabel(actionType: WorkspaceDataCenterReadinessActionType) {
  switch (actionType) {
    case 'retry_parse':
      return '重试解析';
    case 'rebuild_client_knowledge':
      return '重建知识库';
    case 'regenerate_document_cards':
      return '重建资料卡';
    case 'sync_master_index':
      return '同步主索引';
    case 'sync_vector_index':
      return '同步向量索引';
    case 'refresh_context_pack':
      return '刷新上下文包';
    case 'inspect_failed_documents':
      return '检查失败资料';
    default:
      return actionType;
  }
}

function summarizeActionResult(result: WorkspaceDataCenterReadinessActionResult) {
  const base = `${actionLabel(result.actionType as WorkspaceDataCenterReadinessActionType)}：${result.message || result.status}`;
  const suffix: string[] = [];
  if (typeof result.affectedCount === 'number') {
    suffix.push(`影响 ${result.affectedCount} 条`);
  }
  if (result.refreshEventId) {
    suffix.push(`refresh ${result.refreshEventId}`);
  }
  if (result.jobId) {
    suffix.push(`job ${result.jobId}`);
  }
  return suffix.length > 0 ? `${base}（${suffix.join('，')}）` : base;
}

function isMissingIndex(item: WorkspaceDocumentProcessingStatus) {
  return !item.hasDocumentCard || !item.hasMasterIndex || !item.hasSurrogate;
}

function isFailedDocument(item: WorkspaceDocumentProcessingStatus) {
  const normalized = String(item.parseStatus || '').toLowerCase();
  return !['ready', 'partial_ready', 'queued', 'running', 'processing', 'parsing'].includes(normalized);
}

export function DataCenterReadinessPanel({ clientId }: { clientId?: string | null }) {
  const [readiness, setReadiness] = useState<WorkspaceDataCenterReadiness | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<WorkspaceDataCenterReadinessActionType | null>(null);
  const [documentFilter, setDocumentFilter] = useState<DocumentFilter>('all');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState<MessageTone>('info');

  const canLoad = Boolean(clientId && clientId.trim());

  const refresh = async () => {
    if (!canLoad || !clientId) return;
    setLoading(true);
    try {
      const next = await getWorkspaceDataCenterReadiness(clientId);
      setReadiness(next);
      if (!message) {
        setMessage('准备度已刷新');
        setMessageTone('info');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '读取数据中心准备度失败');
      setMessageTone('error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setMessage('');
    setMessageTone('info');
    void refresh();
  }, [clientId]);

  const runAction = async (
    actionType: WorkspaceDataCenterReadinessActionType,
    targetIds: string[] = [],
    reason?: string,
  ) => {
    if (!canLoad || !clientId) return;
    setBusyAction(actionType);
    try {
      const result = await runWorkspaceDataCenterReadinessAction(clientId, {
        actionType,
        targetIds,
        reason,
      });
      setMessage(summarizeActionResult(result));
      setMessageTone(result.status === 'failed' ? 'error' : 'success');
      if (Array.isArray(result.errors) && result.errors.length > 0) {
        setMessage((prev) => `${prev}\n${result.errors.join('\n')}`);
      }
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${actionLabel(actionType)} 执行失败`);
      setMessageTone('error');
    } finally {
      setBusyAction(null);
    }
  };

  const recommendedFixes = readiness?.recommendedFixes || [];

  const documentItems = useMemo(() => {
    const items = (readiness?.documents || []).slice(0, 300);
    if (documentFilter === 'failed') return items.filter((item) => isFailedDocument(item));
    if (documentFilter === 'missing_index') return items.filter((item) => isMissingIndex(item));
    return items;
  }, [readiness, documentFilter]);

  const failedDocumentIds = useMemo(
    () => (readiness?.documents || []).filter((item) => isFailedDocument(item)).map((item) => item.documentId),
    [readiness],
  );

  if (!canLoad || !clientId) return null;

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[12px] font-bold text-gray-800">数据中心准备度</p>
          <p className="text-[11px] text-gray-500">解释资料为什么没有进入回答主链，并提供修复入口</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          disabled={loading}
        >
          {loading ? '刷新中…' : '刷新'}
        </button>
      </div>

      {readiness ? (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">资料总数</p>
              <p className="text-[13px] font-bold text-gray-800">{readiness.summary.totalDocuments}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">ready</p>
              <p className="text-[13px] font-bold text-emerald-700">{readiness.summary.readyDocuments}</p>
              {readiness.summary.partialReadyDocuments ? (
                <p className="text-[10px] font-semibold text-sky-700">partial {readiness.summary.partialReadyDocuments}</p>
              ) : null}
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">queued/running</p>
              <p className="text-[13px] font-bold text-amber-700">
                {readiness.summary.queuedDocuments}/{readiness.summary.runningDocuments}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">解析失败</p>
              <p className="text-[13px] font-bold text-rose-700">{readiness.summary.failedDocuments}</p>
              {readiness.summary.ocrRecoverableCount ? (
                <p className="text-[10px] font-semibold text-amber-700">可 OCR {readiness.summary.ocrRecoverableCount}</p>
              ) : null}
              {Object.keys(readiness.summary.parseFailureBuckets || {}).length > 0 ? (
                <p className="text-[10px] text-gray-500 truncate">
                  {Object.entries(readiness.summary.parseFailureBuckets)
                    .slice(0, 3)
                    .map(([key, count]) => `${key}:${count}`)
                    .join(' · ')}
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">上下文质量</p>
              <p className="text-[13px] font-bold text-indigo-700">{readiness.summary.contextQuality}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">document card</p>
              <p className="text-[13px] font-bold text-gray-800">{readiness.summary.documentCards}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">master index</p>
              <p className="text-[13px] font-bold text-gray-800">{readiness.summary.masterIndexEntries}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">vector</p>
              <p className="text-[13px] font-bold text-gray-800">
                {readiness.summary.vectorStatus} · {readiness.summary.vectorReadyDocuments}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">missingContext</p>
              <p className="text-[13px] font-bold text-amber-700">{readiness.summary.missingContextCount}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[10px] text-gray-400">refresh 队列</p>
              <p className="text-[13px] font-bold text-gray-800">
                {readiness.summary.refreshEventQueuedCount}/{readiness.summary.refreshEventRunningCount}/{readiness.summary.refreshEventFailedCount}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-3 space-y-2">
            <p className="text-[11px] font-bold text-gray-700">推荐修复动作</p>
            {recommendedFixes.length > 0 ? (
              <div className="space-y-2">
                {recommendedFixes.map((fix: WorkspaceDataCenterReadinessFix) => (
                  <div key={fix.id} className="rounded-lg border border-gray-200 bg-white px-3 py-2 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-[12px] font-semibold text-gray-800">{fix.label}</p>
                        <p className="text-[11px] text-gray-500">{fix.reason}</p>
                        {fix.estimatedImpact ? (
                          <p className="text-[10px] text-indigo-600 mt-1">影响：{fix.estimatedImpact}</p>
                        ) : null}
                      </div>
                      <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-semibold text-gray-600">
                        {fix.severity}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] text-gray-500">目标 {fix.targetIds.length} 条</span>
                      <button
                        type="button"
                        onClick={() => void runAction(fix.actionType, fix.targetIds, fix.reason)}
                        disabled={busyAction === fix.actionType}
                        className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                      >
                        {busyAction === fix.actionType ? '执行中…' : actionLabel(fix.actionType)}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-gray-200 bg-white px-3 py-3 text-[11px] text-gray-500">
                当前没有推荐修复动作。
              </div>
            )}
            {failedDocumentIds.length > 0 ? (
              <button
                type="button"
                onClick={() => void runAction('retry_parse', failedDocumentIds, 'retry_failed_documents_from_panel')}
                disabled={busyAction === 'retry_parse'}
                className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
              >
                一键重试全部失败解析（{failedDocumentIds.length}）
              </button>
            ) : null}
          </div>

          <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-bold text-gray-700">文档加工明细（最多 300 条）</p>
              <select
                value={documentFilter}
                onChange={(event) => setDocumentFilter(event.target.value as DocumentFilter)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] text-gray-700"
              >
                <option value="all">全部</option>
                <option value="failed">仅失败</option>
                <option value="missing_index">缺索引/card</option>
              </select>
            </div>
            <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
              {documentItems.map((item: WorkspaceDocumentProcessingStatus) => (
                <div key={`${item.documentId}-${item.v2DocumentId || ''}`} className="rounded-lg border border-gray-200 bg-white px-3 py-2 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[12px] font-semibold text-gray-800 truncate">{item.fileName || item.title}</p>
                      <p className="text-[10px] text-gray-500 truncate">{item.documentId}</p>
                    </div>
                    <div className="flex gap-1.5">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${parseStatusClass(item.parseStatus)}`}>
                        {item.parseStatus}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${vectorStatusClass(item.vectorStatus)}`}>
                        vector {item.vectorStatus || 'unknown'}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${item.hasDocumentCard ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
                      card {item.hasDocumentCard ? 'yes' : 'no'}
                    </span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${item.hasSurrogate ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
                      surrogate {item.hasSurrogate ? 'yes' : 'no'}
                    </span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${item.hasMasterIndex ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
                      master {item.hasMasterIndex ? 'yes' : 'no'}
                    </span>
                    <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-semibold text-gray-700">
                      section/chunk {item.sectionCount}/{item.chunkCount}
                    </span>
                    {item.parseErrorCategory ? (
                      <span className="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold text-rose-700">
                        {item.parseErrorCategory}
                      </span>
                    ) : null}
                    {item.usedByLatestContextPack ? (
                      <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                        latest context used
                      </span>
                    ) : null}
                  </div>
                  {item.parseError ? (
                    <p className="text-[11px] text-rose-700">{item.parseError}</p>
                  ) : null}
                  <p className="text-[10px] text-gray-400">updatedAt: {item.updatedAt}</p>
                </div>
              ))}
              {documentItems.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-200 bg-white px-3 py-4 text-[11px] text-gray-500">
                  当前筛选条件下没有资料明细。
                </div>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-3 space-y-2">
              <p className="text-[11px] font-bold text-gray-700">最近作业（knowledge jobs）</p>
              <div className="max-h-40 overflow-y-auto space-y-1 pr-1">
                {(readiness.recentJobs || []).map((job) => (
                  <div key={job.id} className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-[10px] text-gray-600">
                    [{job.status}] {job.jobType} · {job.processedItems}/{job.totalItems}
                    {job.lastError ? <p className="mt-1 text-rose-600">{job.lastError}</p> : null}
                  </div>
                ))}
                {(readiness.recentJobs || []).length === 0 ? (
                  <div className="rounded-md border border-dashed border-gray-200 bg-white px-2 py-2 text-[10px] text-gray-500">
                    最近没有作业记录。
                  </div>
                ) : null}
              </div>
            </div>
            <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-3 space-y-2">
              <p className="text-[11px] font-bold text-gray-700">最近上下文刷新事件</p>
              <div className="max-h-40 overflow-y-auto space-y-1 pr-1">
                {(readiness.recentRefreshEvents || []).map((event) => (
                  <div key={event.id} className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-[10px] text-gray-600">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate">{event.reason}</p>
                      <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${refreshStatusClass(event.status)}`}>
                        {event.status}
                      </span>
                    </div>
                    <p className="mt-1 text-gray-500 truncate">{event.sourceType}{event.sourceId ? ` · ${event.sourceId}` : ''}</p>
                    {event.error ? <p className="mt-1 text-rose-600">{event.error}</p> : null}
                  </div>
                ))}
                {(readiness.recentRefreshEvents || []).length === 0 ? (
                  <div className="rounded-md border border-dashed border-gray-200 bg-white px-2 py-2 text-[10px] text-gray-500">
                    最近没有上下文刷新事件。
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-4 text-[11px] text-gray-500">
          正在加载数据中心准备度…
        </div>
      )}

      {message ? (
        <div className={`whitespace-pre-wrap rounded-lg border px-3 py-2 text-[11px] ${toneClass(messageTone)}`}>
          {message}
        </div>
      ) : null}
    </div>
  );
}
