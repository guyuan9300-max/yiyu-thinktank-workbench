import React, { useEffect, useMemo, useState } from 'react';

import type { Entity, EntityType } from '../../../shared/types';
import { getClientEntities } from '../../lib/api';

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

  useEffect(() => {
    let cancelled = false;
    if (!clientId) {
      setEntities([]);
      return;
    }
    setLoading(true);
    setError(null);
    getClientEntities(clientId, { limit: 200 })
      .then((result) => {
        if (cancelled) return;
        setEntities(result.entities);
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
  }, [clientId, refreshKey]);

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
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
          {entities.length} 个
        </span>
      </div>

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
