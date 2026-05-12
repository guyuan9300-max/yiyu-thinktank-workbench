import React, { useEffect, useState } from 'react';

import type { FactContradiction } from '../../../shared/types';
import { getClientContradictions, reviewContradiction } from '../../lib/api';

type ContradictionAlertPanelProps = {
  clientId: string;
  refreshKey?: number;
};

const SEVERITY_TONE: Record<string, string> = {
  high: 'border-rose-200 bg-rose-50',
  medium: 'border-amber-200 bg-amber-50',
  low: 'border-slate-200 bg-slate-50',
};

const SEVERITY_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

function formatRelative(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '';
  const diff = Date.now() - parsed.getTime();
  const day = 24 * 60 * 60 * 1000;
  if (diff < day) return '今天';
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
  if (diff < 30 * day) return `${Math.floor(diff / (7 * day))} 周前`;
  return `${Math.floor(diff / (30 * day))} 个月前`;
}

export function ContradictionAlertPanel({ clientId, refreshKey = 0 }: ContradictionAlertPanelProps) {
  const [items, setItems] = useState<FactContradiction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (!clientId) {
      setItems([]);
      return;
    }
    setLoading(true);
    setError(null);
    getClientContradictions(clientId, { status: 'pending', limit: 50 })
      .then((result) => {
        if (cancelled) return;
        setItems(result.contradictions);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : '加载矛盾告警失败';
        setError(message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, refreshKey, reload]);

  const handleReview = async (id: string, status: 'dismissed' | 'resolved') => {
    try {
      await reviewContradiction(id, { reviewStatus: status });
      setReload((value) => value + 1);
    } catch (err) {
      const message = err instanceof Error ? err.message : '操作失败';
      setError(message);
    }
  };

  if (!clientId) return null;
  if (!loading && items.length === 0 && !error) {
    // 没有矛盾时不显示，避免占据屏幕
    return null;
  }

  return (
    <div className="space-y-3 rounded-3xl border border-rose-100 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-black text-rose-700">⚠ 矛盾告警</p>
        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
          {items.length} 待处理
        </span>
      </div>

      {error && <p className="text-[11px] font-semibold text-rose-600">{error}</p>}

      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={`rounded-2xl border px-3 py-2.5 ${SEVERITY_TONE[item.severity] || SEVERITY_TONE.medium}`}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-[12px] font-bold text-slate-800">
                {item.subjectText} · {item.attribute}
              </p>
              <span className="shrink-0 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                {SEVERITY_LABEL[item.severity] || '中'} · {formatRelative(item.detectedAt)}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] leading-5">
              <div className="rounded-xl bg-white/80 px-2 py-1.5">
                <p className="text-[10px] font-bold text-slate-400">{formatRelative(item.factAAt)}</p>
                <p className="mt-0.5 font-bold text-slate-700">{item.valueA}</p>
              </div>
              <div className="rounded-xl bg-white/80 px-2 py-1.5">
                <p className="text-[10px] font-bold text-slate-400">{formatRelative(item.factBAt)}</p>
                <p className="mt-0.5 font-bold text-slate-700">{item.valueB}</p>
              </div>
            </div>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded-lg bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-700 hover:bg-emerald-200"
                onClick={() => handleReview(item.id, 'resolved')}
                title="已确认正确版本，忽略此告警"
              >
                ✓ 已解决
              </button>
              <button
                type="button"
                className="rounded-lg bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-200"
                onClick={() => handleReview(item.id, 'dismissed')}
                title="不是真的矛盾，忽略"
              >
                忽略
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
