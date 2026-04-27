import React, { useEffect, useMemo, useState } from 'react';

import type { DataCenterProposalDraft } from '../../../shared/types';
import {
  getDataCenterProposalDrafts,
  markDataCenterProposalDraftReviewed,
  promoteDataCenterProposalDraft,
  rejectDataCenterProposalDraft,
} from '../../lib/api';

type DraftStatusFilter = 'all' | 'draft' | 'reviewed' | 'rejected' | 'promoted' | 'expired';
type DraftKindFilter =
  | 'all'
  | 'task_prep'
  | 'meeting_prep'
  | 'meeting_followup'
  | 'evidence_request'
  | 'judgment_review'
  | 'context_refresh';

function statusBadge(status: DataCenterProposalDraft['status'] | undefined) {
  const value = status || 'draft';
  if (value === 'promoted') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (value === 'reviewed') return 'bg-blue-50 text-blue-700 border-blue-200';
  if (value === 'rejected') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (value === 'expired') return 'bg-gray-100 text-gray-600 border-gray-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
}

export function DataCenterProposalInboxPanel({ clientId }: { clientId?: string | null }) {
  const [rows, setRows] = useState<DataCenterProposalDraft[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<DraftStatusFilter>('all');
  const [kindFilter, setKindFilter] = useState<DraftKindFilter>('all');
  const [message, setMessage] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  const canLoad = Boolean(clientId && clientId.trim());

  const refresh = async () => {
    if (!canLoad || !clientId) return;
    setLoading(true);
    try {
      const result = await getDataCenterProposalDrafts({
        clientId,
        status: statusFilter === 'all' ? undefined : statusFilter,
        kind: kindFilter === 'all' ? undefined : kindFilter,
        limit: 50,
      });
      setRows(result);
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '读取草稿失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [clientId, statusFilter, kindFilter]);

  const visibleCount = useMemo(() => rows.length, [rows]);

  const runAction = async (draftId: string, action: 'review' | 'reject' | 'promote') => {
    if (!draftId) return;
    setBusyId(draftId);
    try {
      if (action === 'review') {
        await markDataCenterProposalDraftReviewed(draftId, { note: '已查看，待进一步处理' });
        setMessage('已标记 reviewed');
      } else if (action === 'reject') {
        await rejectDataCenterProposalDraft(draftId, { reason: '当前资料不足，暂不推进' });
        setMessage('已驳回草稿');
      } else {
        const promoted = await promoteDataCenterProposalDraft(draftId, { createdBy: 'user', note: '人工确认转正式提案' });
        setMessage(`已 promote 到 proposal: ${promoted.proposalId}`);
      }
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败');
    } finally {
      setBusyId(null);
    }
  };

  if (!canLoad || !clientId) return null;

  return (
    <div className="mt-4 rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[12px] font-bold text-gray-800">Proposal Inbox</p>
          <p className="text-[11px] text-gray-500">草稿 {visibleCount} 条</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-60"
        >
          {loading ? '刷新中…' : '刷新'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as DraftStatusFilter)}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
        >
          <option value="all">状态：全部</option>
          <option value="draft">草稿</option>
          <option value="reviewed">已查看</option>
          <option value="rejected">已驳回</option>
          <option value="promoted">已 promote</option>
          <option value="expired">已过期</option>
        </select>
        <select
          value={kindFilter}
          onChange={(event) => setKindFilter(event.target.value as DraftKindFilter)}
          className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
        >
          <option value="all">类型：全部</option>
          <option value="meeting_followup">meeting_followup</option>
          <option value="meeting_prep">meeting_prep</option>
          <option value="task_prep">task_prep</option>
          <option value="evidence_request">evidence_request</option>
          <option value="judgment_review">judgment_review</option>
          <option value="context_refresh">context_refresh</option>
        </select>
      </div>

      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {rows.length === 0 && !loading ? (
          <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-4 text-[11px] text-gray-500">
            当前筛选条件下没有草稿
          </div>
        ) : null}
        {rows.map((row) => {
          const rowId = row.id || '';
          const isBusy = busyId === rowId;
          const status = row.status || 'draft';
          const promotable = status === 'draft' || status === 'reviewed';
          return (
            <div key={rowId || `${row.kind}-${row.title}`} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold text-gray-800 truncate">{row.title}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{row.summary}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusBadge(status)}`}>
                    {status}
                  </span>
                  <span className="rounded-full border border-gray-200 bg-white px-2 py-0.5 text-[10px] text-gray-600">
                    {row.kind}
                  </span>
                </div>
              </div>
              {row.promotedProposalId ? (
                <p className="text-[10px] text-emerald-700">proposal: {row.promotedProposalId}</p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={isBusy || !rowId || status === 'rejected' || status === 'promoted'}
                  onClick={() => void runAction(rowId, 'review')}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  reviewed
                </button>
                <button
                  type="button"
                  disabled={isBusy || !rowId || status === 'promoted'}
                  onClick={() => void runAction(rowId, 'reject')}
                  className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                >
                  reject
                </button>
                <button
                  type="button"
                  disabled={isBusy || !rowId || !promotable}
                  onClick={() => void runAction(rowId, 'promote')}
                  className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                >
                  promote
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {message ? <p className="text-[11px] text-gray-600">{message}</p> : null}
    </div>
  );
}
