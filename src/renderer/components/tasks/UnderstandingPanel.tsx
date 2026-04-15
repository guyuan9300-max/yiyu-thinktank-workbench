import type { UnderstandingSnapshotV1, UnderstandingSourceBreakdown } from '../../../shared/types';

function completenessBadge(coverage: number) {
  if (coverage >= 75) return { label: '信息较完整', className: 'bg-emerald-50 text-emerald-700' };
  if (coverage >= 45) return { label: '基本可判断', className: 'bg-sky-50 text-sky-700' };
  return { label: '信息较少', className: 'bg-amber-50 text-amber-700' };
}

const SOURCE_GROUPS: Array<{ key: string; label: string; types: UnderstandingSourceBreakdown['sourceType'][] }> = [
  { key: 'org', label: '机构背景', types: ['org_dna', 'quarterly_focus'] },
  { key: 'project', label: '项目背景', types: ['client_background'] },
  { key: 'task', label: '任务内容', types: ['task_title', 'task_desc', 'review_note'] },
  { key: 'context', label: '事件线/会议材料', types: ['event_line_memory', 'meeting', 'support_request', 'knowledge_base', 'attachment', 'calendar'] },
];

function summarizeSourceGroups(sourceBreakdown: UnderstandingSourceBreakdown[]) {
  const availableTypes = new Set(sourceBreakdown.filter((item) => item.available).map((item) => item.sourceType));
  const available = SOURCE_GROUPS.filter((group) => group.types.some((type) => availableTypes.has(type))).map((group) => group.label);
  const missing = SOURCE_GROUPS.filter((group) => !group.types.some((type) => availableTypes.has(type))).map((group) => group.label);
  return { available, missing };
}

type UnderstandingPanelProps = {
  snapshot: UnderstandingSnapshotV1;
};

export function UnderstandingPanel({ snapshot }: UnderstandingPanelProps) {
  const badge = completenessBadge(snapshot.coverage);
  const sourceSummary = summarizeSourceGroups(snapshot.sourceBreakdown);
  const referenceSummary = sourceSummary.available.length > 0 ? sourceSummary.available.join('、') : '当前任务基础信息';
  const suggestionSummary = sourceSummary.missing.length > 0 ? sourceSummary.missing.join('、') : '当前信息已够用';

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${badge.className}`}>信息量：{badge.label}</span>
        <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[10px] font-bold text-gray-500">
          已参考：{referenceSummary}
        </span>
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">
          建议补充：{suggestionSummary}
        </span>
      </div>

      <div className="space-y-2.5">
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">这是什么事</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.whatIsThis}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">为什么重要</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.whyItMatters}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">推进到哪</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.progressNow}</p>
        </div>
        <div className="rounded-2xl bg-amber-50/50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-amber-500">还缺什么理解</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.unknowns}</p>
        </div>
      </div>

      {snapshot.optionalAdvice && (
        <div className="space-y-2 rounded-2xl border border-slate-100 bg-white px-4 py-3">
          {snapshot.optionalAdvice.timeGate && (
            <p className="text-[12px] leading-5 text-red-600">
              <span className="font-bold">时间闸门：</span>{snapshot.optionalAdvice.timeGate}
            </p>
          )}
          {snapshot.optionalAdvice.realBlocker && (
            <p className="text-[12px] leading-5 text-amber-700">
              <span className="font-bold">真正阻碍：</span>{snapshot.optionalAdvice.realBlocker}
            </p>
          )}
          {snapshot.optionalAdvice.minimumAction && (
            <p className="text-[12px] leading-5 text-[#33449a]">
              <span className="font-bold">最小动作：</span>{snapshot.optionalAdvice.minimumAction}
            </p>
          )}
          {snapshot.optionalAdvice.supportAsk && (
            <p className="text-[12px] leading-5 text-gray-600">
              <span className="font-bold">需要支持：</span>{snapshot.optionalAdvice.supportAsk}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
