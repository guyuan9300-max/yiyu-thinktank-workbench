import React, { useEffect, useMemo, useState } from 'react';

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

// 把 path 当作 group key——两份资料相同 path 视作同一对
function pairKey(item: FactContradiction): string {
  const a = item.docAOriginalPath || item.docAFileName || item.factAId;
  const b = item.docBOriginalPath || item.docBFileName || item.factBId;
  // 让 (A,B) 和 (B,A) 归为一组
  return [a, b].sort().join('|||');
}

interface DocSide {
  fileName: string | null | undefined;
  importedAt: string | null | undefined;
  sizeBytes: number | null | undefined;
  path: string | null | undefined;
}

interface PairGroup {
  key: string;
  docA: DocSide;
  docB: DocSide;
  items: FactContradiction[];
  severity: 'low' | 'medium' | 'high';
}

function highestSeverity(items: FactContradiction[]): 'low' | 'medium' | 'high' {
  if (items.some((it) => it.severity === 'high')) return 'high';
  if (items.some((it) => it.severity === 'medium')) return 'medium';
  return 'low';
}

function groupByPair(items: FactContradiction[]): PairGroup[] {
  const map = new Map<string, FactContradiction[]>();
  for (const it of items) {
    const key = pairKey(it);
    const list = map.get(key) ?? [];
    list.push(it);
    map.set(key, list);
  }
  const groups: PairGroup[] = [];
  for (const [key, list] of map) {
    const head = list[0];
    groups.push({
      key,
      docA: {
        fileName: head.docAFileName,
        importedAt: head.docAImportedAt,
        sizeBytes: head.docASizeBytes,
        path: head.docAOriginalPath,
      },
      docB: {
        fileName: head.docBFileName,
        importedAt: head.docBImportedAt,
        sizeBytes: head.docBSizeBytes,
        path: head.docBOriginalPath,
      },
      items: list,
      severity: highestSeverity(list),
    });
  }
  return groups;
}

function DocBadge({ side, label }: { side: DocSide; label: string }) {
  const parts: string[] = [];
  if (side.importedAt) parts.push(`导入于 ${formatRelative(side.importedAt)}`);
  const sizeLabel = formatBytes(side.sizeBytes);
  if (sizeLabel) parts.push(sizeLabel);
  return (
    <div className="rounded-xl bg-white/90 px-2.5 py-2 ring-1 ring-slate-200">
      <p className="text-[9px] font-bold text-slate-400">{label}</p>
      <p className="mt-0.5 truncate text-[11px] font-bold text-slate-700" title={side.fileName || ''}>
        📄 {side.fileName || '未知文件'}
      </p>
      {parts.length > 0 && (
        <p className="mt-0.5 text-[9px] font-semibold text-slate-400">{parts.join(' · ')}</p>
      )}
    </div>
  );
}

export function ContradictionAlertPanel({ clientId, refreshKey = 0 }: ContradictionAlertPanelProps) {
  const [items, setItems] = useState<FactContradiction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [expandedDetail, setExpandedDetail] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    if (!clientId) {
      setItems([]);
      return;
    }
    setLoading(true);
    setError(null);
    getClientContradictions(clientId, { status: 'pending', limit: 100 })
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

  const groups = useMemo(() => groupByPair(items), [items]);

  const handleAcceptSide = async (group: PairGroup, side: 'a' | 'b') => {
    try {
      // 对该 pair 里所有 contradictions 批量 resolve
      await Promise.all(
        group.items.map((item) =>
          reviewContradiction(item.id, {
            reviewStatus: 'resolved',
            acceptedFactId: side === 'a' ? item.factAId : item.factBId,
            resolutionNote: `整份资料以 ${side === 'a' ? '左侧' : '右侧'} 为数据口径`,
          }),
        ),
      );
      setReload((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleKeepBothGroup = async (group: PairGroup) => {
    try {
      await Promise.all(
        group.items.map((item) =>
          reviewContradiction(item.id, {
            reviewStatus: 'dismissed',
            resolutionNote: '两份口径都保留（不视为矛盾）',
          }),
        ),
      );
      setReload((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleAcceptPerField = async (item: FactContradiction, side: 'a' | 'b') => {
    try {
      await reviewContradiction(item.id, {
        reviewStatus: 'resolved',
        acceptedFactId: side === 'a' ? item.factAId : item.factBId,
        resolutionNote: `逐项判定 · 选 ${side === 'a' ? '左' : '右'}`,
      });
      setReload((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  if (!clientId) return null;
  // 只有真的有 pending 矛盾时才显示 banner
  // 之前的 bug: loading=true 时也渲染, 加载中会看到 "0 组 / 0 个口径"
  // 现在 items 为空就不显示, error 单独用一个极简提示展示
  if (items.length === 0) {
    if (error) {
      return (
        <p className="text-[11px] text-rose-600">矛盾告警加载失败：{error}</p>
      );
    }
    return null;
  }

  return (
    <div className="space-y-3 rounded-3xl border border-rose-100 bg-white p-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-black text-rose-700">⚠ 矛盾告警 · 两份资料对同一口径给出了不同的数值</p>
          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
            {groups.length} 组 / {items.length} 个口径
          </span>
        </div>
        <p className="text-[10px] font-semibold leading-4 text-slate-500">
          💡 你选的是<strong className="text-slate-700">数据口径</strong>，不是删文档——文档本身始终保留。
          你的选择只影响 AI 未来回答时**用哪一份数值**做判断。
        </p>
      </div>

      {error && <p className="text-[11px] font-semibold text-rose-600">{error}</p>}

      <div className="space-y-3">
        {groups.map((group) => {
          const expanded = Boolean(expandedDetail[group.key]);
          return (
            <div
              key={group.key}
              className={`rounded-2xl border px-3 py-2.5 ${SEVERITY_TONE[group.severity] || SEVERITY_TONE.medium}`}
            >
              {/* 摘要：多少个口径冲突 */}
              <div className="flex items-center justify-between mb-2">
                <p className="text-[11px] font-bold text-slate-700">
                  这两份资料在 <span className="text-rose-700">{group.items.length}</span> 个口径上有差异
                  <span className="ml-1 text-[10px] font-bold text-slate-500">
                    （严重度 {SEVERITY_LABEL[group.severity]}）
                  </span>
                </p>
              </div>

              {/* 口径列表：每个口径一行，左侧[文件名 → 数据] / 右侧[数据 ← 文件名] */}
              <ul className="space-y-2">
                {group.items.slice(0, expanded ? group.items.length : 3).map((it) => (
                  <li
                    key={it.id}
                    className="rounded-lg bg-white/80 px-3 py-2 text-[11px]"
                  >
                    {/* 口径标题 */}
                    <div className="font-bold text-slate-800 mb-1.5 text-[12px]">
                      {it.subjectText} · {it.attribute}
                    </div>
                    {/* 左右对照：文件名紧贴对应数据 */}
                    <div className="grid grid-cols-2 gap-2 items-center">
                      {/* 左侧：文件名(左) + 数据(右靠中) */}
                      <div className="flex items-center justify-between gap-2 rounded-md border border-emerald-200 bg-emerald-50/60 px-2.5 py-1.5 min-w-0">
                        <button
                          type="button"
                          disabled={!group.docA.path}
                          onClick={() => {
                            if (group.docA.path) {
                              void window.yiyuWorkbench.openPath(group.docA.path).catch(() => undefined);
                            }
                          }}
                          className="text-[10px] text-slate-500 truncate text-left hover:text-emerald-700 hover:underline disabled:no-underline disabled:cursor-not-allowed cursor-pointer"
                          title={group.docA.path ? `点击打开：${group.docA.fileName || ''}` : (group.docA.fileName || '')}
                        >
                          📄 {group.docA.fileName || '资料 A'}
                        </button>
                        <span className="shrink-0 font-bold text-emerald-700">
                          {it.valueA}
                        </span>
                      </div>
                      {/* 右侧：数据(左靠中) + 文件名(右) */}
                      <div className="flex items-center justify-between gap-2 rounded-md border border-sky-200 bg-sky-50/60 px-2.5 py-1.5 min-w-0">
                        <span className="shrink-0 font-bold text-sky-700">
                          {it.valueB}
                        </span>
                        <button
                          type="button"
                          disabled={!group.docB.path}
                          onClick={() => {
                            if (group.docB.path) {
                              void window.yiyuWorkbench.openPath(group.docB.path).catch(() => undefined);
                            }
                          }}
                          className="text-[10px] text-slate-500 truncate text-right hover:text-sky-700 hover:underline disabled:no-underline disabled:cursor-not-allowed cursor-pointer"
                          title={group.docB.path ? `点击打开：${group.docB.fileName || ''}` : (group.docB.fileName || '')}
                        >
                          {group.docB.fileName || '资料 B'} 📄
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>

              {group.items.length > 3 && (
                <button
                  type="button"
                  className="mt-1 text-[10px] font-bold text-slate-500 hover:text-slate-700"
                  onClick={() =>
                    setExpandedDetail((m) => ({ ...m, [group.key]: !m[group.key] }))
                  }
                >
                  {expanded ? '收起' : `查看全部 ${group.items.length} 个口径`}
                </button>
              )}

              {/* 整份判定 · 主操作 */}
              <div className="mt-3 grid grid-cols-3 gap-2">
                <button
                  type="button"
                  className="rounded-lg bg-emerald-100 px-2 py-1.5 text-[11px] font-bold text-emerald-700 hover:bg-emerald-200"
                  onClick={() => void handleAcceptSide(group, 'a')}
                  title="把这份资料里全部 N 个数值都设为数据中心当前真值；另一份对应数值进入归档"
                >
                  以 A 为准 ({group.items.length})
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-emerald-100 px-2 py-1.5 text-[11px] font-bold text-emerald-700 hover:bg-emerald-200"
                  onClick={() => void handleAcceptSide(group, 'b')}
                  title="把这份资料里全部 N 个数值都设为数据中心当前真值；另一份对应数值进入归档"
                >
                  以 B 为准 ({group.items.length})
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-slate-100 px-2 py-1.5 text-[11px] font-bold text-slate-700 hover:bg-slate-200"
                  onClick={() => void handleKeepBothGroup(group)}
                  title="两份口径都保留（视为合理并存，AI 回答时会同时引用两份）"
                >
                  两份都保留
                </button>
              </div>

              {/* 逐项判定 · 次要操作（折叠） */}
              {group.items.length > 1 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-[10px] font-bold text-slate-500 hover:text-slate-700">
                    分别判定每个口径…
                  </summary>
                  <div className="mt-2 space-y-1.5">
                    {group.items.map((it) => (
                      <div
                        key={`detail-${it.id}`}
                        className="rounded-lg bg-white/60 px-2 py-1.5"
                      >
                        <p className="text-[10px] font-bold text-slate-600">
                          {it.subjectText} · {it.attribute}
                        </p>
                        <div className="mt-1 flex gap-2">
                          <button
                            type="button"
                            className="flex-1 rounded-md bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700 hover:bg-emerald-100"
                            onClick={() => void handleAcceptPerField(it, 'a')}
                          >
                            A: {it.valueA}
                          </button>
                          <button
                            type="button"
                            className="flex-1 rounded-md bg-sky-50 px-2 py-1 text-[10px] font-bold text-sky-700 hover:bg-sky-100"
                            onClick={() => void handleAcceptPerField(it, 'b')}
                          >
                            B: {it.valueB}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
