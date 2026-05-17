/**
 * M1 · 字典属性审核 (放在事实澄清面板下方)
 *
 * 业务目标:
 *  - 用户能看到 AI 抽出的 pending candidate
 *  - 一键 verify / 拒绝 / 批量
 *  - 验过的进入字典权威值, chat / narrative 自动消费
 *  - 这是 "学霸笔记本" 的写入入口
 */
import { useEffect, useState } from 'react';
import {
  BookOpen,
  Check,
  X,
  Loader2,
  ChevronDown,
  ChevronRight,
  Pencil,
  CalendarDays,
} from 'lucide-react';
import {
  listGlossaryAttributes,
  verifyGlossaryAttribute,
  rejectGlossaryAttribute,
  type GlossaryAttributeRecord,
  type GlossaryAttributeClarifyPayload,
} from '../../lib/api';

interface GlossaryAttributeReviewSectionProps {
  clientId: string;
  onChanged?: () => void;
  flash?: (kind: 'success' | 'error', message: string) => void;
}

const CATEGORY_LABEL: Record<string, { label: string; emoji: string }> = {
  amount: { label: '金额', emoji: '💰' },
  date: { label: '日期', emoji: '📅' },
  person: { label: '人物', emoji: '👤' },
  location: { label: '地点', emoji: '📍' },
  count: { label: '数量', emoji: '🔢' },
  rating: { label: '评级', emoji: '⭐' },
  text: { label: '业务术语', emoji: '📁' },
};

export function GlossaryAttributeReviewSection({
  clientId,
  onChanged,
  flash,
}: GlossaryAttributeReviewSectionProps) {
  const [attrs, setAttrs] = useState<GlossaryAttributeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showSection, setShowSection] = useState(true);
  const [editingAttr, setEditingAttr] = useState<GlossaryAttributeRecord | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await listGlossaryAttributes(clientId, 'pending');
      setAttrs(data.attributes ?? []);
    } catch (err) {
      flash?.('error', `字典待审加载失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!clientId) return;
    void load();
  }, [clientId]);

  const mark = async (
    attrId: string,
    action: 'verify' | 'reject',
    clarifyPayload?: GlossaryAttributeClarifyPayload,
  ) => {
    setActing((s) => new Set(s).add(attrId));
    try {
      if (action === 'verify') {
        await verifyGlossaryAttribute(clientId, attrId, clarifyPayload ?? {});
        flash?.('success', clarifyPayload ? '已澄清并采纳, 进字典权威值' : '已采纳, 进字典权威值');
      } else {
        await rejectGlossaryAttribute(clientId, attrId);
        flash?.('success', '已拒绝');
      }
      setAttrs((prev) => prev.filter((a) => a.id !== attrId));
      onChanged?.();
    } catch (err) {
      flash?.('error', `操作失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setActing((s) => {
        const ns = new Set(s);
        ns.delete(attrId);
        return ns;
      });
    }
  };

  const batchVerifyCategory = async (cat: string) => {
    const targets = attrs.filter((a) => a.value_category === cat);
    if (targets.length === 0) return;
    if (!confirm(`将批量采纳 ${targets.length} 条 ${CATEGORY_LABEL[cat]?.label || cat} 类候选?`)) return;
    for (const a of targets) {
      await mark(a.id, 'verify');
    }
  };

  if (!showSection) {
    return (
      <button
        type="button"
        onClick={() => setShowSection(true)}
        className="text-[12px] text-slate-500 hover:text-slate-700 mt-4 flex items-center gap-1"
      >
        <BookOpen size={13} />
        展开字典待审 ({attrs.length})
      </button>
    );
  }

  // 按 category 分组
  const byCategory = new Map<string, GlossaryAttributeRecord[]>();
  for (const a of attrs) {
    const cat = a.value_category || 'text';
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(a);
  }
  const categoryOrder = ['amount', 'date', 'person', 'location', 'count', 'rating', 'text'];

  return (
    <section className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/30 px-4 py-3">
      <header className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <BookOpen size={14} className="text-blue-600" />
          <h3 className="text-[13px] font-bold text-blue-800">字典待审 · 学霸笔记本</h3>
          <span className="text-[11px] text-blue-600 bg-blue-100 rounded-full px-2 py-0.5 font-semibold">
            {attrs.length} 条
          </span>
          <span className="text-[11px] text-slate-500">
            采纳进入字典权威值, chat/narrative 直接 cite, 不再翻原文
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowSection(false)}
          className="text-[11px] text-slate-400 hover:text-slate-600"
        >
          收起
        </button>
      </header>

      {loading && (
        <div className="text-[12px] text-slate-500 py-3 flex items-center gap-2">
          <Loader2 size={13} className="animate-spin" />
          加载中...
        </div>
      )}

      {!loading && attrs.length === 0 && (
        <div className="text-[12px] text-slate-500 py-3">
          没有待审候选。AI 抽取出新 candidate 后会自动出现这里。
        </div>
      )}

      {!loading && attrs.length > 0 && (
        <div className="space-y-3">
          {categoryOrder.map((cat) => {
            const group = byCategory.get(cat);
            if (!group || group.length === 0) return null;
            const meta = CATEGORY_LABEL[cat] || { label: cat, emoji: '📋' };
            const isExpanded = expanded.has(cat);
            return (
              <div key={cat} className="rounded-lg bg-white border border-slate-100">
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((s) => {
                      const ns = new Set(s);
                      if (ns.has(cat)) ns.delete(cat);
                      else ns.add(cat);
                      return ns;
                    })
                  }
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50"
                >
                  <div className="flex items-center gap-2">
                    {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    <span className="text-[12px] font-bold text-slate-700">
                      {meta.emoji} {meta.label}
                    </span>
                    <span className="text-[11px] text-slate-500">({group.length})</span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void batchVerifyCategory(cat);
                    }}
                    className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-full px-2 py-0.5"
                  >
                    全部采纳
                  </button>
                </button>
                {isExpanded && (
                  <ul className="border-t border-slate-100 divide-y divide-slate-100">
                    {group.map((a) => {
                      const inAction = acting.has(a.id);
                      return (
                        <li key={a.id} className="px-3 py-2.5 text-[12px]">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="font-semibold text-slate-800">
                                {a.term} <span className="text-slate-400 font-normal">·</span>{' '}
                                {a.attribute_name}
                              </div>
                              <div className="mt-1 text-slate-700">
                                = {a.value_text}
                                {a.value_unit && (
                                  <span className="text-slate-400 ml-1">{a.value_unit}</span>
                                )}
                              </div>
                              {(a.scope || a.as_of_date) && (
                                <div className="mt-1 text-[10px] text-slate-500">
                                  {a.scope && <>scope: {a.scope}</>}
                                  {a.scope && a.as_of_date && ' · '}
                                  {a.as_of_date && <>截至 {a.as_of_date}</>}
                                </div>
                              )}
                              {a.source_evidence && (
                                <div className="mt-1 text-[10px] text-slate-500 italic line-clamp-2">
                                  证据: {a.source_evidence}
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                type="button"
                                onClick={() => mark(a.id, 'verify')}
                                disabled={inAction}
                                className="inline-flex items-center gap-1 rounded-md bg-emerald-600 text-white px-2 py-1 text-[10px] font-bold hover:bg-emerald-700 disabled:opacity-50"
                                title="采纳进字典"
                              >
                                {inAction ? (
                                  <Loader2 size={11} className="animate-spin" />
                                ) : (
                                  <Check size={11} />
                                )}
                                采纳
                              </button>
                              <button
                                type="button"
                                onClick={() => mark(a.id, 'reject')}
                                disabled={inAction}
                                className="inline-flex items-center gap-1 rounded-md bg-slate-200 text-slate-700 px-2 py-1 text-[10px] font-bold hover:bg-slate-300 disabled:opacity-50"
                                title="拒绝"
                              >
                                <X size={11} />
                                拒绝
                              </button>
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
