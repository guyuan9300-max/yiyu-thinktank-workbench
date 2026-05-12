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

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '时间未知';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '';
  const diff = Date.now() - parsed.getTime();
  const day = 24 * 60 * 60 * 1000;
  if (diff < day) return '今天';
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
  if (diff < 30 * day) return `${Math.floor(diff / (7 * day))} 周前`;
  return `${Math.floor(diff / (30 * day))} 个月前`;
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function FileMetaLine({
  fileName,
  importedAt,
  sizeBytes,
}: {
  fileName: string | null | undefined;
  importedAt: string | null | undefined;
  sizeBytes: number | null | undefined;
}) {
  const parts: string[] = [];
  if (importedAt) parts.push(`导入于 ${formatRelative(importedAt)}`);
  const sizeLabel = formatBytes(sizeBytes);
  if (sizeLabel) parts.push(sizeLabel);
  return (
    <div className="space-y-0.5">
      <p className="truncate text-[10px] font-bold text-slate-600" title={fileName || ''}>
        📄 {fileName || '未知文件'}
      </p>
      {parts.length > 0 && (
        <p className="text-[9px] font-semibold text-slate-400">{parts.join(' · ')}</p>
      )}
    </div>
  );
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

  const handleAccept = async (id: string, factId: string) => {
    try {
      await reviewContradiction(id, { reviewStatus: 'resolved', acceptedFactId: factId });
      setReload((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleKeepBoth = async (id: string) => {
    try {
      await reviewContradiction(id, {
        reviewStatus: 'dismissed',
        resolutionNote: '两份都保留（不是矛盾）',
      });
      setReload((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  if (!clientId) return null;
  if (!loading && items.length === 0 && !error) return null;

  return (
    <div className="space-y-3 rounded-3xl border border-rose-100 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-black text-rose-700">⚠ 矛盾告警 · 同一客户的不同资料有冲突信息</p>
        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
          {items.length} 待处理
        </span>
      </div>

      {error && <p className="text-[11px] font-semibold text-rose-600">{error}</p>}

      <div className="space-y-3">
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
                严重度 {SEVERITY_LABEL[item.severity] || '中'} · 检出 {formatRelative(item.detectedAt)}
              </span>
            </div>

            <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] leading-5">
              {/* 左侧 · 资料 A */}
              <div className="rounded-xl bg-white/90 px-2.5 py-2 ring-1 ring-slate-200">
                <FileMetaLine
                  fileName={item.docAFileName}
                  importedAt={item.docAImportedAt}
                  sizeBytes={item.docASizeBytes}
                />
                <p className="mt-1.5 text-[13px] font-black text-slate-800">{item.valueA}</p>
                {item.evidenceA && (
                  <p className="mt-1 line-clamp-2 text-[10px] font-medium text-slate-500" title={item.evidenceA}>
                    "{item.evidenceA.trim()}"
                  </p>
                )}
                <button
                  type="button"
                  className="mt-2 w-full rounded-lg bg-emerald-100 px-2 py-1 text-[10px] font-bold text-emerald-700 hover:bg-emerald-200"
                  onClick={() => handleAccept(item.id, item.factAId)}
                  title="采用此版本，自动归档另一份；未来 AI 不再用旧值回答"
                >
                  ✓ 采用此版本
                </button>
              </div>

              {/* 右侧 · 资料 B */}
              <div className="rounded-xl bg-white/90 px-2.5 py-2 ring-1 ring-slate-200">
                <FileMetaLine
                  fileName={item.docBFileName}
                  importedAt={item.docBImportedAt}
                  sizeBytes={item.docBSizeBytes}
                />
                <p className="mt-1.5 text-[13px] font-black text-slate-800">{item.valueB}</p>
                {item.evidenceB && (
                  <p className="mt-1 line-clamp-2 text-[10px] font-medium text-slate-500" title={item.evidenceB}>
                    "{item.evidenceB.trim()}"
                  </p>
                )}
                <button
                  type="button"
                  className="mt-2 w-full rounded-lg bg-emerald-100 px-2 py-1 text-[10px] font-bold text-emerald-700 hover:bg-emerald-200"
                  onClick={() => handleAccept(item.id, item.factBId)}
                  title="采用此版本，自动归档另一份；未来 AI 不再用旧值回答"
                >
                  ✓ 采用此版本
                </button>
              </div>
            </div>

            <div className="mt-2 flex justify-end">
              <button
                type="button"
                className="rounded-lg bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-200"
                onClick={() => handleKeepBoth(item.id)}
                title="两份都不是错的，只是不同时点/不同场景的描述，保持两份都活跃"
              >
                两份都保留（不是矛盾）
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
