import { useState } from 'react';

import type {
  HierarchyReport,
  ReviewActionCard,
  ReviewActionExecutionResult,
  ReviewDashboardCardTarget,
  ReviewDashboardEvidenceRef,
  WeeklyReviewAnalysis,
} from '../../../shared/types';
import { ReviewMetricGrid } from './ReviewMetricGrid';

type HierarchyReportCardTone = 'slate' | 'emerald' | 'amber';

type HierarchyReportCardProps = {
  report: HierarchyReport;
  title: string;
  subtitle: string;
  tone?: HierarchyReportCardTone;
  analysis?: WeeklyReviewAnalysis | null;
  showAnonymousInsights?: boolean;
  onTriggerAction?: (action: ReviewActionCard, report: HierarchyReport) => Promise<ReviewActionExecutionResult | void> | ReviewActionExecutionResult | void;
  onOpenActionResult?: (result: ReviewActionExecutionResult, action: ReviewActionCard, report: HierarchyReport) => Promise<void> | void;
  onDrillTarget?: (target: ReviewDashboardCardTarget) => Promise<void> | void;
};

const toneClassMap: Record<HierarchyReportCardTone, { header: string; subtitle: string; chip: string; action: string; fact: string }> = {
  slate: {
    header: 'bg-slate-900 text-white',
    subtitle: 'text-white/70',
    chip: 'bg-slate-100 text-slate-700',
    action: 'bg-slate-50 text-slate-700',
    fact: 'bg-slate-50 text-slate-700',
  },
  emerald: {
    header: 'bg-emerald-600 text-white',
    subtitle: 'text-emerald-50',
    chip: 'bg-emerald-50 text-emerald-800',
    action: 'bg-emerald-50/70 text-emerald-900/80',
    fact: 'bg-emerald-50/60 text-emerald-900/80',
  },
  amber: {
    header: 'bg-amber-500 text-white',
    subtitle: 'text-amber-50',
    chip: 'bg-amber-50 text-amber-800',
    action: 'bg-amber-50/80 text-amber-900/80',
    fact: 'bg-amber-50 text-amber-900/80',
  },
};

function readNumber(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function confidenceClass(confidence: string) {
  if (confidence === 'high') return 'bg-emerald-50 text-emerald-700';
  if (confidence === 'medium') return 'bg-amber-50 text-amber-700';
  return 'bg-slate-100 text-slate-500';
}

function confidenceLabel(confidence: string) {
  if (confidence === 'high') return '高置信';
  if (confidence === 'medium') return '中置信';
  return '低置信';
}

function lensLabel(lens: string) {
  if (lens === 'organization') return '组织视角';
  if (lens === 'business') return '业务视角';
  if (lens === 'team') return '团队视角';
  if (lens === 'market') return '市场视角';
  if (lens === 'growth') return '成长视角';
  return '执行视角';
}

function actionTypeLabel(actionType: string) {
  if (actionType === 'meeting') return '会议';
  if (actionType === 'support_request') return '支持请求';
  if (actionType === 'resource_request') return '资源调整';
  if (actionType === 'one_on_one') return '1v1';
  return '任务动作';
}

function actionTypeClass(actionType: string) {
  if (actionType === 'meeting') return 'bg-blue-50 text-[#33449a]';
  if (actionType === 'support_request') return 'bg-amber-50 text-amber-700';
  if (actionType === 'resource_request') return 'bg-rose-50 text-rose-700';
  if (actionType === 'one_on_one') return 'bg-emerald-50 text-emerald-700';
  return 'bg-slate-100 text-slate-600';
}

function severityLabel(severity: string) {
  if (severity === 'high') return '高严重度';
  if (severity === 'medium') return '中严重度';
  return '低严重度';
}

type ExecutiveOverviewCard = {
  key: string;
  title: string;
  subtitle: string;
  items: Array<{
    title: string;
    body: string;
    chips?: string[];
    target?: ReviewDashboardCardTarget | null;
    evidenceRefs?: ReviewDashboardEvidenceRef[];
  }>;
  empty: string;
  className: string;
};

type StructuredLine = {
  title: string;
  body: string;
};

function parseStructuredLine(value: string): StructuredLine | null {
  const normalized = value.trim();
  if (!normalized.includes('｜')) return null;
  const [title, ...rest] = normalized.split('｜');
  const cleanTitle = title.trim();
  const cleanBody = rest.join('｜').trim();
  if (!cleanTitle || !cleanBody) return null;
  return { title: cleanTitle, body: cleanBody };
}

function overviewItemsFromText(values: string[], fallbackChip?: string): Array<{ title: string; body: string; chips?: string[] }> {
  return values.slice(0, 4).map((item) => {
    const parsed = parseStructuredLine(item);
    if (parsed) {
      return {
        title: parsed.title,
        body: parsed.body,
      };
    }
    return {
      title: item,
      body: item,
      chips: fallbackChip ? [fallbackChip] : undefined,
    };
  });
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[28px] border border-gray-200 bg-white px-5 py-5 shadow-sm">
      <div className="mb-4">
        <h4 className="text-[15px] font-bold text-gray-900">{title}</h4>
        {subtitle ? <p className="mt-1 text-[12px] leading-5 text-gray-500">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function buildExecutiveOverviewCards(report: HierarchyReport, analysis?: WeeklyReviewAnalysis | null): ExecutiveOverviewCard[] {
  const trendRiskItems = analysis?.trendSignals?.length
    ? analysis.trendSignals.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [severityLabel(item.severity), item.windowLabel],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : [];
  const eventLineItems = analysis?.eventLineSummaries?.length
    ? analysis.eventLineSummaries.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.whatHappenedThisWeek || item.currentState,
      chips: [
        item.projectName || '',
        item.moduleName || item.flowName || '',
        `完整度 ${item.completenessScore}%`,
      ].filter(Boolean),
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.focusAreas);
  const riskCardItems = analysis?.riskCards?.length
    ? analysis.riskCards.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [
        item.probability === 'high' ? '高概率' : item.probability === 'medium' ? '中概率' : '低概率',
        item.forecastWindow === '1w' ? '未来 1 周' : item.forecastWindow === '2w' ? '未来 2 周' : '未来 3 周',
      ],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.supportSignals);
  const riskItems = [...trendRiskItems, ...riskCardItems]
    .filter((item, index, list) => list.findIndex((candidate) => candidate.title === item.title && candidate.body === item.body) === index)
    .slice(0, 4);
  const opportunityItems = analysis?.opportunityCards?.length
    ? analysis.opportunityCards.slice(0, 4).map((item) => ({
      title: item.title,
      body: item.statement,
      chips: [
        item.confidence === 'high' ? '高把握' : item.confidence === 'medium' ? '中把握' : '低把握',
        item.upside,
      ].filter(Boolean),
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : overviewItemsFromText(report.anonymousInsights);
  const actionItems = report.actions.length > 0
    ? report.actions.slice(0, 4).map((item) => ({
      title: item.title,
      body: typeof item.payload.summary === 'string' ? item.payload.summary : item.title,
      chips: [actionTypeLabel(item.actionType)],
      target: item.target,
      evidenceRefs: item.evidenceRefs || [],
    }))
    : [
      ...overviewItemsFromText(report.suggestedActions.slice(0, 3), '建议动作'),
      ...(analysis?.nextWeekFocus?.slice(0, 1).map((item) => ({ title: '下周关注', body: item, chips: ['下周关注'] })) || []),
    ];

  return [
    {
      key: 'event_lines',
      title: '本周关键事件线',
      subtitle: '先看这一周真正推进了哪几条线。',
      items: eventLineItems,
      empty: '事件线尚在梳理中|任务痕迹积累足够后，事件线会自动归纳到这里',
      className: 'border-blue-100 bg-blue-50/50',
    },
    {
      key: 'risks',
      title: '本周最值得关注的风险',
      subtitle: '优先看未来 1-3 周可能继续放大的问题。',
      items: riskItems,
      empty: '暂无风险信号|当出现延期、阻塞或资源冲突时，风险卡片会自动生成',
      className: 'border-rose-100 bg-rose-50/55',
    },
    {
      key: 'opportunities',
      title: '本周最值得放大的机会',
      subtitle: '不是亮点罗列，而是值得加码的正向势能。',
      items: opportunityItems,
      empty: '暂无机会信号|当出现超预期进展或正向势能时，机会卡片会自动生成',
      className: 'border-emerald-100 bg-emerald-50/45',
    },
    {
      key: 'actions',
      title: '本周建议动作',
      subtitle: '把判断收束成可执行的最小动作。',
      items: actionItems,
      empty: '建议待生成|综合事件线、风险和机会分析后，建议动作会自动归纳',
      className: 'border-amber-100 bg-amber-50/55',
    },
  ];
}

export function HierarchyReportCard({
  report,
  title,
  subtitle,
  tone = 'slate',
  analysis = null,
  showAnonymousInsights = true,
  onTriggerAction,
  onOpenActionResult,
  onDrillTarget,
}: HierarchyReportCardProps) {
  const [runningActionId, setRunningActionId] = useState<string | null>(null);
  const [actionResults, setActionResults] = useState<Record<string, ReviewActionExecutionResult>>({});
  const toneClasses = toneClassMap[tone];
  const sourcePolicy = report.sourcePolicy || {};
  const sampleSize = readNumber(sourcePolicy, 'sampleSize');
  const agentSampleCount = readNumber(sourcePolicy, 'agentSampleCount');
  const simulationMode = sourcePolicy.simulationMode === true;
  const overviewCards = buildExecutiveOverviewCards(report, analysis);
  const focusAreaCards = report.focusAreas
    .map((item) => parseStructuredLine(item))
    .filter((item): item is StructuredLine => Boolean(item));
  const plainFocusAreas = report.focusAreas.filter((item) => !parseStructuredLine(item));
  const evidenceSourceLabels = Array.from(
    new Set([
      '任务痕迹',
      report.scopeType === 'org' ? '组织背景' : report.scopeType === 'team' ? '部门计划' : '个人执行',
      ...(analysis?.dnaModuleTitles || []).map((item) => `参考：${item}`),
      ...(report.scopeType !== 'employee' ? ['项目/业务背景'] : []),
    ]),
  );

  const actionButtonLabel = (actionType: string) => {
    if (actionType === 'meeting') return '发起会议';
    if (actionType === 'support_request') return '发支持请求';
    if (actionType === 'resource_request') return '发资源请求';
    if (actionType === 'one_on_one') return '转成 1v1 任务';
    return '转成任务';
  };

  const handleTriggerAction = async (action: ReviewActionCard) => {
    if (!onTriggerAction || runningActionId) return;
    setRunningActionId(action.id);
    try {
      const result = await onTriggerAction(action, report);
      if (result) {
        setActionResults((prev) => ({
          ...prev,
          [action.id]: result,
        }));
      }
    } finally {
      setRunningActionId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className={`rounded-3xl border border-gray-200 p-5 shadow-sm ${toneClasses.header}`}>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[18px] font-bold">{title}</h2>
          {simulationMode ? (
            <span className="rounded-full bg-white/15 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-white/90">
              模拟视角
            </span>
          ) : null}
        </div>
        <p className={`mt-1 text-[12px] ${toneClasses.subtitle}`}>{subtitle}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {sampleSize ? (
            <span className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              约 {sampleSize} 条复盘样本
            </span>
          ) : null}
          {agentSampleCount && agentSampleCount > 0 ? (
            <span className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              含 {agentSampleCount} 条机器人自动样本
            </span>
          ) : null}
          {evidenceSourceLabels.map((item) => (
            <span key={item} className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
              {item}
            </span>
          ))}
        </div>
      </div>

      <Section title="本周全局判断" subtitle="先建立全局认知，再决定要不要往下看详细事实和解释。">
        <div className="grid gap-3 lg:grid-cols-2">
          {overviewCards.map((card) => (
            <div key={card.key} className={`rounded-3xl border px-4 py-4 ${card.className}`}>
              <div>
                <h5 className="text-[14px] font-bold text-gray-900">{card.title}</h5>
                <p className="mt-1 text-[11px] leading-5 text-gray-500">{card.subtitle}</p>
              </div>
              {card.items.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {card.items.map((item) => (
                    <div key={`${card.key}-${item.title}`} className="rounded-2xl bg-white/80 px-3 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[12px] font-bold leading-5 text-gray-900">{item.title}</p>
                        {item.chips?.map((chip) => (
                          <span key={chip} className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-gray-500">
                            {chip}
                          </span>
                        ))}
                        {item.evidenceRefs && item.evidenceRefs.length > 0 ? (
                          <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-slate-400">
                            {item.evidenceRefs.length} 条证据
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 line-clamp-3 text-[12px] leading-6 text-gray-700">{item.body}</p>
                      {item.target && onDrillTarget ? (
                        <div className="mt-3">
                          <button
                            type="button"
                            className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-bold text-[#33449a] transition hover:border-[#BFD0FF] hover:bg-[#F6F8FF]"
                            onClick={() => void onDrillTarget(item.target!)}
                          >
                            查看证据与下钻
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl bg-white/75 px-3 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">{card.empty.split('|')[0]}</p><p className="text-[12px] text-slate-400 mt-1">{card.empty.split('|')[1]}</p></div>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section title="本周事实" subtitle="先看真实发生了什么，再进入解释和预测。">
        <div className="space-y-4">
          <ReviewMetricGrid metrics={report.summaryMetrics || []} />
          <div className="space-y-2">
            <div className={`rounded-2xl px-4 py-4 text-[13px] leading-6 ${toneClasses.fact}`}>
              <p className="font-bold text-gray-900">{report.headline}</p>
              <p className="mt-2 text-gray-700">{report.summary}</p>
            </div>
            {showAnonymousInsights && report.anonymousInsights.length > 0
              ? report.anonymousInsights.map((item) => (
                <div key={item} className={`rounded-2xl px-4 py-3 text-[13px] leading-6 ${toneClasses.fact}`}>
                  {item}
                </div>
              ))
              : null}
          </div>
        </div>
      </Section>

      <Section title="AI 判断" subtitle="结合组织、部门和项目背景解释这些任务痕迹。">
        <div className="space-y-3">
          {focusAreaCards.length > 0 ? (
            <div className="grid gap-2 lg:grid-cols-2">
              {focusAreaCards.map((item) => (
                <div key={`${item.title}-${item.body}`} className="rounded-2xl bg-slate-50 px-4 py-3">
                  <p className="text-[12px] font-bold text-gray-900">{item.title}</p>
                  <p className="mt-1 text-[12px] leading-6 text-gray-600">{item.body}</p>
                </div>
              ))}
            </div>
          ) : null}
          {plainFocusAreas.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {plainFocusAreas.map((item) => (
                <span key={item} className={`rounded-full px-3 py-2 text-[12px] font-bold ${toneClasses.chip}`}>
                  {item}
                </span>
              ))}
            </div>
          ) : null}
          {report.supportSignals.length > 0 ? (
            <div className="space-y-2">
              {report.supportSignals.map((item) => (
                <div key={item} className="rounded-2xl bg-gray-50 px-4 py-3 text-[13px] leading-6 text-gray-700">
                  {item}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">判断线索待积累</p><p className="text-[12px] text-slate-400 mt-1">任务数据和背景信息足够丰富后，AI 会在这里展示解释性判断</p></div>
          )}
        </div>
      </Section>

      <Section title="可能性分析" subtitle="从当前信号里看未来 1-3 周可能出现的风险和机会。">
        {analysis?.hypothesisHighlights.length ? (
          <div className="space-y-3">
            {analysis.hypothesisHighlights.map((item) => (
              <div key={item.id} className="rounded-3xl border border-gray-200 bg-white px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{lensLabel(item.lens)}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${confidenceClass(item.confidence)}`}>{confidenceLabel(item.confidence)}</span>
                </div>
                <p className="mt-3 text-[13px] leading-6 text-gray-700">{item.statement}</p>
                <p className="mt-3 text-[12px] leading-5 text-slate-500">依据：{item.reason}</p>
                {item.assumptionNote ? <p className="mt-2 text-[12px] leading-5 text-amber-700">提示：{item.assumptionNote}</p> : null}
              </div>
            ))}
          </div>
        ) : report.focusAreas.length > 0 ? (
          <div className="space-y-2">
            {report.focusAreas.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-[#33449a]">
                {item}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">可能性分析待生成</p><p className="text-[12px] text-slate-400 mt-1">积累足够的任务和趋势数据后，风险与机会预测会自动展示</p></div>
        )}
      </Section>

      <Section title="建议动作" subtitle="把总结收敛成个人、部门或机构层面可以执行的动作。">
        {report.actions.length > 0 || report.suggestedActions.length > 0 || analysis?.nextWeekFocus.length ? (
          <div className="space-y-2">
            {report.actions.map((action) => {
              const summary = typeof action.payload.summary === 'string' ? action.payload.summary : '';
              const relatedTaskTitles = Array.isArray(action.payload.relatedTaskTitles)
                ? action.payload.relatedTaskTitles.filter((item): item is string => typeof item === 'string')
                : [];
              const actionResult = actionResults[action.id];
              return (
                <div key={action.id} className="rounded-3xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${actionTypeClass(action.actionType)}`}>
                      {actionTypeLabel(action.actionType)}
                    </span>
                    <span className="text-[14px] font-bold text-gray-900">{action.title}</span>
                  </div>
                  {summary ? <p className="mt-3 text-[13px] leading-6 text-gray-700">{summary}</p> : null}
                  {relatedTaskTitles.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {relatedTaskTitles.map((item) => (
                        <span key={item} className="rounded-full bg-slate-50 px-3 py-1.5 text-[11px] font-bold text-slate-600">
                          {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {onTriggerAction ? (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-sm transition hover:bg-[#4c6df0] disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => void handleTriggerAction(action)}
                        disabled={Boolean(runningActionId)}
                      >
                        {runningActionId === action.id ? '处理中...' : actionButtonLabel(action.actionType)}
                      </button>
                      {actionResult && onOpenActionResult && actionResult.canOpen ? (
                        <button
                          type="button"
                          className="rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[12px] font-bold text-gray-600 transition hover:border-[#5B7BFE] hover:text-[#33449a]"
                          onClick={() => void onOpenActionResult(actionResult, action, report)}
                        >
                          {actionResult.objectType === 'task'
                            ? '打开任务'
                            : actionResult.objectType === 'support_request'
                              ? '打开请求'
                              : '打开项目'}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {actionResult ? (
                    <div className="mt-3 rounded-2xl bg-emerald-50 px-4 py-3 text-[12px] leading-6 text-emerald-800">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-white/90 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
                          已执行
                        </span>
                        <span className="font-bold">
                          {actionResult.objectType === 'task'
                            ? '已创建任务'
                            : actionResult.objectType === 'meeting'
                              ? '已发起会议草稿'
                              : '已创建支持请求'}
                        </span>
                      </div>
                      <p className="mt-2 text-emerald-900">
                        {actionResult.objectLabel}
                        <span className="ml-2 text-emerald-700/80">#{actionResult.objectId}</span>
                      </p>
                      {actionResult.targetClientName ? (
                        <p className="text-emerald-700/80">关联项目：{actionResult.targetClientName}</p>
                      ) : null}
                      {actionResult.targetEventLineName ? (
                        <p className="text-emerald-700/80">关联事件线：{actionResult.targetEventLineName}</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
            {report.suggestedActions.map((item) => (
              <div key={item} className={`rounded-2xl px-4 py-3 text-[13px] leading-6 ${toneClasses.action}`}>
                {item}
              </div>
            ))}
            {analysis?.nextWeekFocus.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-[#33449a]">
                {item}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-center"><p className="text-[13px] font-bold text-slate-500">建议待生成</p><p className="text-[12px] text-slate-400 mt-1">综合分析完成后，可执行的建议动作会归纳到这里</p></div>
        )}
      </Section>
    </div>
  );
}
