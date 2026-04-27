import React from 'react';

type WorkStatusPanelProps = {
  contextQualityLabel: string;
  primarySources: string[];
  routeIntent?: string | null;
  actionSuggestionTitles: string[];
  proposalTitles: string[];
  missingContext: string[];
  boundaryNotes: string[];
};

function renderList(items: string[], emptyText: string) {
  if (items.length === 0) {
    return <p className="mt-2 text-[12px] leading-6 text-slate-400">{emptyText}</p>;
  }
  return (
    <ul className="mt-2 space-y-1 text-[12px] leading-6 text-slate-700">
      {items.map((item) => (
        <li key={item}>• {item}</li>
      ))}
    </ul>
  );
}

export function WorkStatusPanel({
  contextQualityLabel,
  primarySources,
  routeIntent,
  actionSuggestionTitles,
  proposalTitles,
  missingContext,
  boundaryNotes,
}: WorkStatusPanelProps) {
  return (
    <div className="rounded-[24px] border border-amber-100 bg-[linear-gradient(180deg,rgba(255,247,237,0.82),rgba(255,255,255,0.98))] px-5 py-5 xl:px-6 xl:py-6 shadow-[0_8px_28px_rgba(245,158,11,0.08)]">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-600">工作状态视图</p>
        <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-amber-700">上下文质量 · {contextQualityLabel}</span>
        {routeIntent ? (
          <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-amber-700">路由意图 · {routeIntent}</span>
        ) : null}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-amber-100 bg-white px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-600">主来源</p>
          {renderList(primarySources, '当前没有可展示的主来源。')}
        </div>
        <div className="rounded-2xl border border-amber-100 bg-white px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-600">下一步建议</p>
          {renderList(actionSuggestionTitles, '当前没有可展示的下一步建议。')}
        </div>
        <div className="rounded-2xl border border-amber-100 bg-white px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-600">候选动作</p>
          {renderList(proposalTitles, '当前没有可展示的候选动作。')}
        </div>
        <div className="rounded-2xl border border-amber-100 bg-white px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-600">风险 / 缺口 / 边界</p>
          {renderList([...missingContext.slice(0, 4), ...boundaryNotes.slice(0, 4)], '当前没有明显的缺口或边界提示。')}
        </div>
      </div>
    </div>
  );
}
