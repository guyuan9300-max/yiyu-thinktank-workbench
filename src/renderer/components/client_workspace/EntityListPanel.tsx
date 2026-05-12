import React, { useEffect, useMemo, useState } from 'react';

import type { Entity, EntityMergeCandidate, EntityType } from '../../../shared/types';
import { getClientEntities, getEntityMergeCandidates, mergeEntityInto } from '../../lib/api';

type EntityListPanelProps = {
  clientId: string;
  /** 可选：父级控制刷新——比如新文档导入完成后递增触发拉取 */
  refreshKey?: number;
};

interface TypeMeta {
  label: string;
  tone: string;
}

const TYPE_META: Record<EntityType, TypeMeta> = {
  person: { label: '人物', tone: 'border-rose-100 bg-rose-50 text-rose-700' },
  company: { label: '公司', tone: 'border-sky-100 bg-sky-50 text-sky-700' },
  project: { label: '项目', tone: 'border-indigo-100 bg-indigo-50 text-indigo-700' },
  product: { label: '产品', tone: 'border-emerald-100 bg-emerald-50 text-emerald-700' },
  competitor: { label: '竞品', tone: 'border-amber-100 bg-amber-50 text-amber-700' },
  amount: { label: '金额', tone: 'border-slate-100 bg-slate-50 text-slate-700' },
  date: { label: '日期', tone: 'border-violet-100 bg-violet-50 text-violet-700' },
};

const TYPE_ORDER: EntityType[] = [
  'person',
  'company',
  'project',
  'product',
  'competitor',
  'amount',
  'date',
];

function formatRelative(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '';
  const diff = Date.now() - parsed.getTime();
  const day = 24 * 60 * 60 * 1000;
  if (diff < day) return '今天';
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
  if (diff < 30 * day) return `${Math.floor(diff / (7 * day))} 周前`;
  if (diff < 365 * day) return `${Math.floor(diff / (30 * day))} 个月前`;
  return `${(diff / (365 * day)).toFixed(1)} 年前`;
}

export function EntityListPanel({ clientId, refreshKey = 0 }: EntityListPanelProps) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<EntityMergeCandidate[]>([]);
  const [candidatesOpen, setCandidatesOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (!clientId) {
      setEntities([]);
      setCandidates([]);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      getClientEntities(clientId, { limit: 200 }),
      getEntityMergeCandidates(clientId, 50).catch(() => ({ candidates: [] })),
    ])
      .then(([entResult, candResult]) => {
        if (cancelled) return;
        setEntities(entResult.entities);
        setCandidates(candResult.candidates);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : '加载实体失败';
        setError(message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, refreshKey, reloadKey]);

  const handleMerge = async (
    survivingEntityId: string,
    mergedEntityId: string,
    survivingName: string,
    mergedName: string,
  ) => {
    if (!window.confirm(`确认把"${mergedName}"合并到"${survivingName}"？此操作会迁移所有提及/关系/事实到目标实体。`)) {
      return;
    }
    try {
      await mergeEntityInto(mergedEntityId, {
        survivingEntityId,
        mergeReason: `手动合并 · ${mergedName} → ${survivingName}`,
      });
      setReloadKey((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '合并失败');
    }
  };

  const grouped = useMemo(() => {
    const map = new Map<EntityType, Entity[]>();
    for (const entity of entities) {
      const list = map.get(entity.entityType) ?? [];
      list.push(entity);
      map.set(entity.entityType, list);
    }
    for (const [type, list] of map) {
      list.sort((a, b) => b.mentionCount - a.mentionCount);
      map.set(type, list);
    }
    return map;
  }, [entities]);

  if (!clientId) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-3xl border border-slate-100 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-black text-slate-700">识别出的实体</p>
        <div className="flex items-center gap-1.5">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
            {entities.length} 个
          </span>
          {candidates.length > 0 && (
            <button
              type="button"
              className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700 hover:bg-amber-200"
              onClick={() => setCandidatesOpen((v) => !v)}
              title="发现可能是同一实体的相似名（如「张总」和「张总监」）"
            >
              {candidatesOpen ? '收起' : `${candidates.length} 个疑似重复`}
            </button>
          )}
        </div>
      </div>

      {candidatesOpen && candidates.length > 0 && (
        <div className="space-y-1.5 rounded-2xl border border-amber-100 bg-amber-50/70 px-3 py-2">
          <p className="text-[10px] font-bold text-amber-700">疑似重复实体（点击合并方向）</p>
          {candidates.map((c) => {
            // 默认推荐：mention_count 更高的一方作为 surviving
            const aIsBetter = c.mentionCountA >= c.mentionCountB;
            return (
              <div
                key={`${c.entityAId}-${c.entityBId}`}
                className="rounded-lg bg-white px-2.5 py-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] font-bold text-slate-500">
                    {c.entityType} · 相似度 {Math.round(c.similarity * 100)}% · {c.reason}
                  </p>
                </div>
                <div className="mt-1 grid grid-cols-2 gap-1">
                  <button
                    type="button"
                    className={`rounded-md px-2 py-1 text-[10px] font-bold ${
                      aIsBetter
                        ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                    onClick={() => void handleMerge(c.entityAId, c.entityBId, c.nameA, c.nameB)}
                    title={`保留"${c.nameA}"，把"${c.nameB}"的所有提及/关系合进来`}
                  >
                    保留 {c.nameA} ({c.mentionCountA})
                  </button>
                  <button
                    type="button"
                    className={`rounded-md px-2 py-1 text-[10px] font-bold ${
                      !aIsBetter
                        ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                    onClick={() => void handleMerge(c.entityBId, c.entityAId, c.nameB, c.nameA)}
                    title={`保留"${c.nameB}"，把"${c.nameA}"的所有提及/关系合进来`}
                  >
                    保留 {c.nameB} ({c.mentionCountB})
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {loading && entities.length === 0 && (
        <p className="text-[11px] font-semibold text-slate-400">加载中…</p>
      )}

      {error && (
        <p className="text-[11px] font-semibold text-rose-600">{error}</p>
      )}

      {!loading && !error && entities.length === 0 && (
        <p className="text-[11px] font-semibold leading-5 text-slate-400">
          这位客户暂时没有识别出的实体。导入更多资料后会自动出现。
        </p>
      )}

      {TYPE_ORDER.map((type) => {
        const list = grouped.get(type);
        if (!list || list.length === 0) return null;
        const meta = TYPE_META[type];
        return (
          <div key={type} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-black ${meta.tone}`}>
                {meta.label}
              </span>
              <span className="text-[10px] font-bold text-slate-400">{list.length}</span>
            </div>
            <ul className="space-y-1">
              {list.map((entity) => (
                <li
                  key={entity.id}
                  className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 px-3 py-1.5"
                  title={`置信度 ${(entity.confidence * 100).toFixed(0)}% · 最近 ${formatRelative(entity.lastSeenAt)}`}
                >
                  <span className="truncate text-[12px] font-bold text-slate-800">
                    {entity.displayName}
                  </span>
                  <span className="shrink-0 text-[10px] font-bold text-slate-400">
                    {entity.mentionCount} 次 · {formatRelative(entity.lastSeenAt)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
