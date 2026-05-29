/**
 * M1 · 事实澄清面板 (战略陪伴 → 客户档案 底部)
 *
 * 业务目标:
 *  - 用户能看到 AI 抽出的 pending candidate
 *  - 一键 verify / 拒绝 / 澄清 / 批量
 *  - 验过的进入字典权威值, chat / narrative 自动消费
 *
 * 设计准则 (5/27 重设计):
 *  - 跟"重点主线 / 任务归属"统一: 细体大字标题 + 中性灰骨架 + 单一蓝紫强调色
 *  - 不用 emoji, 全 lucide-react icons
 *  - 按钮 ghost / outline 风格, 不用实色填充
 *  - chip / pill 统一 text-[10px] font-medium rounded-full
 */
import { useEffect, useState, type ComponentType } from 'react';
import {
  CircleDollarSign,
  CalendarDays,
  User,
  MapPin,
  Hash,
  Star,
  Tag,
  FileText,
  Check,
  X,
  Loader2,
  ChevronDown,
  ChevronRight,
  Pencil,
  Zap,
  Clock,
  Link2,
  Inbox,
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

// 替换原 emoji 为 lucide icon component. 跟整个 codebase icon 风格统一.
type IconType = ComponentType<{ size?: number | string; className?: string; strokeWidth?: number | string }>;
const CATEGORY_META: Record<string, { label: string; Icon: IconType }> = {
  amount: { label: '金额', Icon: CircleDollarSign },
  date: { label: '日期', Icon: CalendarDays },
  person: { label: '人物', Icon: User },
  location: { label: '地点', Icon: MapPin },
  count: { label: '数量', Icon: Hash },
  rating: { label: '评级', Icon: Star },
  text: { label: '业务术语', Icon: Tag },
};

const SOURCE_META: Record<string, string> = {
  ai_inferred: '资料抽取',
  auto_resolved_clarification: '澄清回填',
  internet_ocr: '互联网整理',
  drift_alert: '冲突提示',
  user_input: '用户填写',
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
      flash?.('error', `事实澄清加载失败: ${err instanceof Error ? err.message : String(err)}`);
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
        flash?.('success', clarifyPayload ? '已澄清并采纳，进入客户档案权威值' : '已采纳，进入客户档案权威值');
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
    if (!confirm(`将批量采纳 ${targets.length} 条「${CATEGORY_META[cat]?.label || cat}」类候选?`)) return;
    for (const a of targets) {
      await mark(a.id, 'verify');
    }
  };

  const highConfidenceCount = attrs.filter((a) => (a.confidence ?? 0) >= 0.9).length;
  const batchVerifyHighConfidence = async () => {
    const targets = attrs.filter((a) => (a.confidence ?? 0) >= 0.9);
    if (targets.length === 0) {
      flash?.('error', '没有高置信度（≥90%）的待审条目');
      return;
    }
    if (!confirm(`将批量采纳 ${targets.length} 条高置信度候选（剩余 ${attrs.length - targets.length} 条需要逐条审）?`)) return;
    for (const a of targets) {
      await mark(a.id, 'verify');
    }
    flash?.('success', `已采纳 ${targets.length} 条进入客户档案`);
  };

  if (!showSection) {
    return (
      <button
        type="button"
        onClick={() => setShowSection(true)}
        className="mt-6 inline-flex items-center gap-1.5 text-[12px] font-medium text-gray-500 hover:text-gray-900 transition-colors"
      >
        <ChevronRight size={13} strokeWidth={2} />
        展开事实澄清
        <span className="tabular-nums text-gray-400">· {attrs.length}</span>
      </button>
    );
  }

  // 按 category 分组, 组内按 confidence 倒序
  const byCategory = new Map<string, GlossaryAttributeRecord[]>();
  for (const a of attrs) {
    const cat = a.value_category || 'text';
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(a);
  }
  for (const [, group] of byCategory) {
    group.sort((x, y) => (y.confidence ?? 0) - (x.confidence ?? 0));
  }
  const categoryOrder = ['amount', 'date', 'person', 'location', 'count', 'rating', 'text'];

  return (
    <section className="mt-8">
      {/* Header: 大号细字标题 + 极简副 label + 右上角统计 */}
      <header className="mb-6 flex items-end justify-between gap-6">
        <div>
          <h3 className="text-[20px] font-light tracking-tight text-gray-900">事实澄清</h3>
          <p className="mt-1 text-[12px] text-gray-400 leading-relaxed">
            AI 替你抽出待确认事实 · 一键审过后进入客户档案权威值，后续问答与报告自动引用
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-4 tabular-nums">
          <span className="inline-flex items-baseline gap-1 text-[11px] text-gray-400">
            <span className="text-[15px] font-semibold text-gray-900">{attrs.length}</span>
            待审
          </span>
          {attrs.length > 0 && (
            <>
              <span className="text-gray-200">·</span>
              <span className="inline-flex items-baseline gap-1 text-[11px] text-gray-400">
                <span className="text-[15px] font-semibold text-[#5B7BFE]">{highConfidenceCount}</span>
                高置信
              </span>
            </>
          )}
          <button
            type="button"
            onClick={() => setShowSection(false)}
            className="ml-2 text-[11px] font-medium text-gray-400 hover:text-gray-700 transition-colors"
          >
            收起
          </button>
        </div>
      </header>

      {/* 一键采纳条 (高置信度) — 不挤在 header, 单独一行更显眼 */}
      {!loading && highConfidenceCount > 0 && (
        <button
          type="button"
          onClick={() => void batchVerifyHighConfidence()}
          className="group mb-3 inline-flex items-center gap-2 rounded-md border border-[#5B7BFE]/30 bg-[#5B7BFE]/5 px-3 py-1.5 text-[12px] font-medium text-[#5B7BFE] transition-colors hover:bg-[#5B7BFE]/10 hover:border-[#5B7BFE]/50"
        >
          <Zap size={13} strokeWidth={2} />
          <span>一键采纳全部高置信度</span>
          <span className="rounded-full bg-white px-1.5 py-px text-[10px] font-semibold tabular-nums">
            {highConfidenceCount}
          </span>
        </button>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-4 text-[12px] text-gray-400">
          <Loader2 size={13} className="animate-spin" />
          <span>正在加载待审事实…</span>
        </div>
      )}

      {!loading && attrs.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <Inbox size={22} className="text-gray-300" strokeWidth={1.5} />
          <p className="text-[13px] font-medium text-gray-500">暂无待审事实</p>
          <p className="text-[11px] text-gray-400 max-w-[280px] leading-relaxed">
            导入新资料或 AI 抽取出新候选后会自动出现在这里
          </p>
        </div>
      )}

      {editingAttr && (
        <ClarifyEditModal
          attr={editingAttr}
          onClose={() => setEditingAttr(null)}
          onConfirm={async (payload) => {
            const id = editingAttr.id;
            setEditingAttr(null);
            await mark(id, 'verify', payload);
          }}
        />
      )}

      {!loading && attrs.length > 0 && (
        <div className="space-y-2">
          {categoryOrder.map((cat) => {
            const group = byCategory.get(cat);
            if (!group || group.length === 0) return null;
            const meta = CATEGORY_META[cat] || { label: cat, Icon: Tag };
            const Icon = meta.Icon;
            const isExpanded = expanded.has(cat);
            return (
              <div key={cat} className="rounded-lg border border-gray-100 bg-white overflow-hidden">
                {/* 分组 header: 细线 hover 灰底, 右侧"全部采纳"ghost 按钮 */}
                <div className="flex items-stretch justify-between">
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
                    className="flex flex-1 items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-gray-50"
                  >
                    <span className="flex h-4 w-4 items-center justify-center text-gray-400">
                      {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </span>
                    <Icon size={14} className="text-gray-500" strokeWidth={1.8} />
                    <span className="text-[13px] font-medium text-gray-800">{meta.label}</span>
                    <span className="tabular-nums text-[11px] text-gray-400">{group.length}</span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void batchVerifyCategory(cat);
                    }}
                    className="border-l border-gray-100 px-3 text-[11px] font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-emerald-700"
                  >
                    全部采纳
                  </button>
                </div>

                {isExpanded && (
                  <ul className="border-t border-gray-100 divide-y divide-gray-100">
                    {group.map((a) => {
                      const inAction = acting.has(a.id);
                      const isDateItem = a.value_category === 'date';
                      const verifyLabel = isDateItem ? '已完成' : '采纳';
                      const verifyTitle = isDateItem
                        ? '此 deadline 已完成（不必填具体日期）'
                        : '原文正确，直接采纳进客户档案';
                      const rejectLabel = isDateItem ? '取消' : '拒绝';
                      const rejectTitle = isDateItem
                        ? '此任务/deadline 已取消，不再追踪'
                        : '拒绝（这条不该进客户档案）';
                      const sourceLabel = a.source_type ? SOURCE_META[a.source_type] : null;
                      const confidence = typeof a.confidence === 'number' ? a.confidence : null;
                      const confidenceTone = confidence === null
                        ? null
                        : confidence >= 0.9
                          ? 'text-emerald-700 border-emerald-200 bg-emerald-50/60'
                          : confidence >= 0.7
                            ? 'text-amber-700 border-amber-200 bg-amber-50/60'
                            : 'text-gray-500 border-gray-200 bg-gray-50';
                      return (
                        <li key={a.id} className="px-4 py-3">
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-[13px] font-medium text-gray-900 truncate">
                                  {a.term}
                                  <span className="mx-1 text-gray-300">·</span>
                                  <span className="text-gray-600">{a.attribute_name}</span>
                                </span>
                                {sourceLabel && (
                                  <span className="rounded-full border border-gray-200 px-1.5 py-px text-[10px] font-medium text-gray-500">
                                    {sourceLabel}
                                  </span>
                                )}
                                {confidence !== null && (
                                  <span className={`rounded-full border px-1.5 py-px text-[10px] font-medium tabular-nums ${confidenceTone}`}>
                                    {Math.round(confidence * 100)}%
                                  </span>
                                )}
                              </div>
                              <div className="mt-1.5 flex items-baseline gap-1.5 text-[13px] text-gray-700">
                                <span className="text-gray-300">=</span>
                                <span>{a.value_text}</span>
                                {a.value_unit && (
                                  <span className="text-[12px] text-gray-400">{a.value_unit}</span>
                                )}
                              </div>
                              {(a.scope || a.as_of_date) && (
                                <div className="mt-1 flex items-center gap-2 text-[11px] text-gray-400">
                                  {a.scope && <span>口径：{a.scope}</span>}
                                  {a.scope && a.as_of_date && <span className="text-gray-200">·</span>}
                                  {a.as_of_date && <span>截至 {a.as_of_date}</span>}
                                </div>
                              )}
                              {a.source_evidence && (
                                <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-gray-500">
                                  <span className="text-gray-400">证据：</span>
                                  {a.source_evidence}
                                </p>
                              )}
                              {a.source_doc_path && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (a.source_doc_path) {
                                      void window.yiyuWorkbench.openPath(a.source_doc_path).catch(() => undefined);
                                    }
                                  }}
                                  className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-[#5B7BFE] hover:text-[#3a5cf0] transition-colors"
                                  title={`点击打开来源：${a.source_doc_title || a.source_doc_path}`}
                                >
                                  <Link2 size={11} strokeWidth={1.8} />
                                  {a.source_doc_title || '打开来源文档'}
                                </button>
                              )}
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              <button
                                type="button"
                                onClick={() => mark(a.id, 'verify')}
                                disabled={inAction}
                                title={verifyTitle}
                                className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50/60 px-2.5 py-1 text-[11px] font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50"
                              >
                                {inAction ? (
                                  <Loader2 size={11} className="animate-spin" />
                                ) : (
                                  <Check size={11} strokeWidth={2} />
                                )}
                                {verifyLabel}
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingAttr(a)}
                                disabled={inAction}
                                title="修正/补充后采纳"
                                className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE] disabled:opacity-50"
                              >
                                <Pencil size={11} strokeWidth={1.8} />
                                澄清
                              </button>
                              <button
                                type="button"
                                onClick={() => mark(a.id, 'reject')}
                                disabled={inAction}
                                title={rejectTitle}
                                className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-500 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
                              >
                                <X size={11} strokeWidth={2} />
                                {rejectLabel}
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

interface ClarifyEditModalProps {
  attr: GlossaryAttributeRecord;
  onClose: () => void;
  onConfirm: (payload: GlossaryAttributeClarifyPayload) => void | Promise<void>;
}

function ClarifyEditModal({ attr, onClose, onConfirm }: ClarifyEditModalProps) {
  const [valueText, setValueText] = useState(attr.value_text || '');
  const [valueUnit, setValueUnit] = useState(attr.value_unit || '');
  const [scope, setScope] = useState(attr.scope || '');
  const [asOfDate, setAsOfDate] = useState(attr.as_of_date || '');
  const [attributeName, setAttributeName] = useState(attr.attribute_name || '');

  const isDate = attr.value_category === 'date';
  const isAmount = attr.value_category === 'amount';
  const isCount = attr.value_category === 'count';

  const handleSave = async () => {
    const payload: GlossaryAttributeClarifyPayload = {
      valueText: valueText.trim(),
      valueUnit: valueUnit.trim() || undefined,
      scope: scope.trim() || undefined,
      asOfDate: asOfDate.trim() || null,
      attributeName: attributeName.trim() || undefined,
    };
    await onConfirm(payload);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 backdrop-blur-sm">
      <div className="w-[500px] max-w-[92vw] rounded-2xl border border-gray-100 bg-white shadow-2xl">
        <header className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
          <Pencil size={14} className="text-[#5B7BFE]" strokeWidth={1.8} />
          <h3 className="text-[15px] font-medium text-gray-900">澄清</h3>
          <span className="text-gray-300">·</span>
          <span className="text-[13px] text-gray-600">{attr.term}</span>
        </header>

        <div className="space-y-4 px-6 py-5 text-[12px]">
          <div>
            <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">属性名</label>
            <input
              type="text"
              value={attributeName}
              onChange={(e) => setAttributeName(e.target.value)}
              className="w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
              placeholder="例：总部位置 / 2023年度支出"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">
              {isDate ? '日期' : isAmount ? '金额' : isCount ? '数量' : '权威值'}
            </label>
            {isDate ? (
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <CalendarDays size={14} className="text-gray-400" strokeWidth={1.8} />
                  <input
                    type="date"
                    value={valueText.includes('-') ? valueText.slice(0, 10) : ''}
                    onChange={(e) => setValueText(e.target.value)}
                    className="rounded-md border border-gray-200 px-3 py-1.5 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
                  />
                  <span className="text-[11px] text-gray-400">或自由输入：</span>
                  <input
                    type="text"
                    value={valueText}
                    onChange={(e) => setValueText(e.target.value)}
                    className="flex-1 rounded-md border border-gray-200 px-3 py-1.5 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
                    placeholder="例：2014 年 / 2026-03-30"
                  />
                </div>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-gray-400">快捷标记：</span>
                  <button
                    type="button"
                    onClick={() => setValueText('已完成')}
                    className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50/60 px-2 py-0.5 font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
                  >
                    <Check size={11} strokeWidth={2} />已完成
                  </button>
                  <button
                    type="button"
                    onClick={() => setValueText('进行中')}
                    className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50/60 px-2 py-0.5 font-medium text-amber-700 hover:bg-amber-100 transition-colors"
                  >
                    <Clock size={11} strokeWidth={1.8} />进行中
                  </button>
                  <button
                    type="button"
                    onClick={() => setValueText('暂无 deadline')}
                    className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-0.5 font-medium text-gray-500 hover:bg-gray-50 transition-colors"
                  >
                    <FileText size={11} strokeWidth={1.8} />暂无
                  </button>
                </div>
              </div>
            ) : (
              <textarea
                value={valueText}
                onChange={(e) => setValueText(e.target.value)}
                rows={2}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
                placeholder="填入权威值"
              />
            )}
          </div>

          {(isAmount || isCount) && (
            <div>
              <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">单位</label>
              <input
                type="text"
                value={valueUnit}
                onChange={(e) => setValueUnit(e.target.value)}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
                placeholder="例：元 / 人 / 省"
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">口径</label>
              <input
                type="text"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
                placeholder="机构当前 / 项目累计 / 现任"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">截至日期（可选）</label>
              <input
                type="date"
                value={asOfDate.slice(0, 10)}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] text-gray-800 focus:border-[#5B7BFE] focus:outline-none focus:ring-1 focus:ring-[#5B7BFE]/20"
              />
            </div>
          </div>
        </div>

        <footer className="flex justify-end gap-2 border-t border-gray-100 px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[12px] font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
          >
            <Check size={12} strokeWidth={2} />
            保存并采纳
          </button>
        </footer>
      </div>
    </div>
  );
}
