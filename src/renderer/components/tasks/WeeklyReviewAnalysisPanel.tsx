import type { WeeklyReviewAnalysis } from '../../../shared/types';
import { ReviewMetricGrid } from './ReviewMetricGrid';

export type EventLineGapActionPayload = {
  eventLineId: string;
  title: string;
  actionType: 'upload_docs' | 'clarify_now';
  slotLabels: string[];
};

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

function sourceTypeLabel(value: string) {
  if (value === 'user_note') return '轻量复盘';
  if (value === 'task_fact') return '任务事实';
  if (value === 'organization_dna') return '组织背景';
  if (value === 'team_plan') return '部门计划';
  if (value === 'external_context') return '项目/外部背景';
  return value;
}

function readinessLabel(value: string) {
  if (value === 'strong_forecast') return '强预测';
  if (value === 'conservative_forecast') return '保守预测';
  if (value === 'summary_only') return '仅可总结';
  return '证据不足';
}

function readinessClass(value: string) {
  if (value === 'strong_forecast') return 'bg-emerald-50 text-emerald-700';
  if (value === 'conservative_forecast') return 'bg-blue-50 text-[#33449a]';
  if (value === 'summary_only') return 'bg-amber-50 text-amber-700';
  return 'bg-slate-100 text-slate-500';
}

function completenessStatusLabel(value: string) {
  if (value === 'high_confidence') return '高可信';
  if (value === 'forecast_ready') return '可预测';
  if (value === 'summary_ready') return '可总结';
  return '证据不足';
}

function scopeLabel(value: string) {
  if (value === 'org') return '机构';
  if (value === 'project') return '项目';
  if (value === 'team') return '团队';
  return '个人';
}

function backgroundSourceLabel(value: string) {
  if (value === '组织笔记') return '组织笔记';
  if (value === '事件线记忆') return '事件线记忆';
  if (value === '周复盘信号') return '周复盘信号';
  if (value === '统一事实池') return '统一事实池';
  if (value === '任务/附件证据') return '任务/附件证据';
  if (value === '待澄清槽位') return '待澄清槽位';
  return value;
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

type WeeklyReviewAnalysisPanelProps = {
  analysis: WeeklyReviewAnalysis;
  onResolveGapAction?: (payload: EventLineGapActionPayload) => void;
};

export function WeeklyReviewAnalysisPanel({ analysis, onResolveGapAction }: WeeklyReviewAnalysisPanelProps) {
  const evidenceSourceLabels = Array.from(
    new Set([
      '任务痕迹',
      ...analysis.evidenceWeights.map((item) => sourceTypeLabel(item.sourceType)),
      ...analysis.dnaModuleTitles.map((item) => `参考：${item}`),
    ]),
  );

  const suggestedActions = Array.from(
    new Set([
      ...analysis.riskCards.map((item) => item.suggestedAction),
      ...analysis.opportunityCards.map((item) => item.recommendedAmplifier),
      ...analysis.nextWeekFocus,
    ]),
  ).slice(0, 5);

  return (
    <div className="space-y-4">
      <div className={`rounded-3xl border border-gray-200 p-5 shadow-sm ${analysis.scope === 'work' ? 'bg-slate-900 text-white' : 'bg-rose-500 text-white'}`}>
        <p className="text-[18px] font-bold">{analysis.scope === 'work' ? '周判断视角' : '成长判断视角'}</p>
        <p className="mt-1 text-[12px] leading-6 text-white/75">{analysis.caution}</p>
        {evidenceSourceLabels.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {evidenceSourceLabels.map((item) => (
              <span key={item} className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-bold text-white/90">
                {item}
              </span>
            ))}
          </div>
        )}
      </div>

      {analysis.eventLineSummaries.length > 0 && (
        <Section title="本周关键事件线" subtitle="先把同类、连续、跨任务的事情压成几条事件线，再看风险和机会。">
          <div className="space-y-3">
            {analysis.eventLineSummaries.map((item) => (
              <div key={item.eventLineId} className="rounded-3xl border border-gray-200 bg-white px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${readinessClass(item.predictionReadiness)}`}>{readinessLabel(item.predictionReadiness)}</span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">完整度 {item.completenessScore}%</span>
                  {typeof item.memoryConfidence === 'number' ? (
                    <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">
                      记忆置信 {Math.round(item.memoryConfidence * 100)}%
                    </span>
                  ) : null}
                  {item.projectName ? <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[10px] font-bold text-violet-700">{item.projectName}</span> : null}
                  {item.moduleName ? <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">{item.moduleName}</span> : null}
                  {item.flowName ? <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">{item.flowName}</span> : null}
                </div>
                <div className="mt-3 space-y-2 text-[13px] leading-6 text-gray-700">
                  <p><span className="font-bold text-gray-900">这条线是什么：</span>{item.whatThisLineIs}</p>
                  <p><span className="font-bold text-gray-900">本周发生了什么：</span>{item.whatHappenedThisWeek}</p>
                  <p><span className="font-bold text-gray-900">当前状态：</span>{item.currentState}</p>
                  <p><span className="font-bold text-gray-900">主要阻碍：</span>{item.mainBlocker}</p>
                  <p><span className="font-bold text-gray-900">下周最关键变化点：</span>{item.nextCriticalMove}</p>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {item.ownerNames.map((owner) => (
                    <span key={owner} className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">负责人：{owner}</span>
                  ))}
                  {(item.backgroundSources || []).map((source) => (
                    <span key={source} className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">
                      背景：{backgroundSourceLabel(source)}
                    </span>
                  ))}
                  {item.missingSlots.map((slot) => (
                    <span key={slot} className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">待补：{slot}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {analysis.riskCards.length > 0 && (
        <Section title="升级中的风险" subtitle="这不是对过去的解释，而是未来 1-3 周最可能放大的问题。">
          <div className="space-y-3">
            {analysis.riskCards.map((item) => (
              <div key={`${item.eventLineId}-${item.riskType}`} className="rounded-3xl border border-red-100 bg-red-50/50 px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-red-600">{item.probability === 'high' ? '高概率' : item.probability === 'medium' ? '中概率' : '低概率'}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500">未来 {item.forecastWindow === '1w' ? '1 周' : item.forecastWindow === '2w' ? '2 周' : '3 周'}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500">{scopeLabel(item.impactScope)}</span>
                </div>
                <p className="mt-3 text-[13px] leading-6 text-gray-700">{item.statement}</p>
                <p className="mt-2 text-[12px] leading-5 text-gray-500">为什么现在要看见：{item.whyNow}</p>
                <p className="mt-2 text-[12px] leading-5 text-gray-500">如果不处理：{item.ifIgnored}</p>
                <p className="mt-2 text-[12px] leading-5 text-[#33449a]">建议动作：{item.suggestedAction}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {analysis.opportunityCards.length > 0 && (
        <Section title="值得放大的机会" subtitle="这些不是简单亮点，而是值得加资源、沉淀方法或复制的正向势能。">
          <div className="space-y-3">
            {analysis.opportunityCards.map((item) => (
              <div key={`${item.eventLineId}-${item.opportunityType}`} className="rounded-3xl border border-emerald-100 bg-emerald-50/40 px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-emerald-700">{item.confidence === 'high' ? '高把握' : item.confidence === 'medium' ? '中把握' : '低把握'}</span>
                </div>
                <p className="mt-3 text-[13px] leading-6 text-gray-700">{item.statement}</p>
                <p className="mt-2 text-[12px] leading-5 text-gray-500">放大收益：{item.upside}</p>
                <p className="mt-2 text-[12px] leading-5 text-[#33449a]">建议放大动作：{item.recommendedAmplifier}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {analysis.trendSignals.length > 0 && (
        <Section title="连续趋势信号" subtitle="这些不是一周内的偶发点，而是已经开始持续化的风险与判断偏差。">
          <div className="space-y-3">
            {analysis.trendSignals.map((item) => (
              <div key={item.key} className="rounded-3xl border border-amber-100 bg-amber-50/45 px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-bold text-gray-900">{item.title}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-amber-700">
                    {item.severity === 'high' ? '高严重度' : item.severity === 'medium' ? '中严重度' : '低严重度'}
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500">{item.windowLabel}</span>
                  {item.relatedTaskIds.length > 0 ? (
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500">
                      关联任务 {item.relatedTaskIds.length} 条
                    </span>
                  ) : null}
                </div>
                <p className="mt-3 text-[13px] leading-6 text-gray-700">{item.statement}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {suggestedActions.length > 0 && (
        <Section title="建议动作" subtitle="先做最小动作，优先改变趋势，而不是继续加解释。">
          <div className="space-y-2">
            {suggestedActions.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-[#33449a]">{item}</div>
            ))}
          </div>
        </Section>
      )}

      {analysis.eventLineCompleteness.length > 0 && (
        <Section title="证据与缺口" subtitle="只有证据够了，系统才应该做强判断。这里告诉你哪些线还缺信息。">
          <div className="grid gap-3 lg:grid-cols-2">
            {analysis.eventLineCompleteness.map((item) => (
              (() => {
                const uploadSlots = item.slots.filter((slot) => slot.coverage !== 'full' && slot.recommendedFix === 'upload_docs');
                const clarifySlots = item.slots.filter((slot) => slot.coverage !== 'full' && slot.recommendedFix === 'clarify_now');
                const passiveSlots = item.slots.filter((slot) => slot.coverage !== 'full' && slot.recommendedFix === 'wait_for_more_trace');
                return (
                  <div key={item.eventLineId} className="rounded-3xl border border-gray-200 bg-white px-4 py-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13px] font-bold text-gray-900">{item.title}</span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{completenessStatusLabel(item.status)}</span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{item.score}%</span>
                      {typeof item.memoryConfidence === 'number' ? (
                        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">
                          记忆置信 {Math.round(item.memoryConfidence * 100)}%
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.strongestSlots.map((slot) => (
                        <span key={slot} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">已清楚：{slot}</span>
                      ))}
                      {item.missingSlots.map((slot) => (
                        <span key={slot} className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">待补：{slot}</span>
                      ))}
                    </div>
                    {(uploadSlots.length > 0 || clarifySlots.length > 0 || passiveSlots.length > 0) && (
                      <div className="mt-4 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3 py-3">
                        {uploadSlots.length > 0 && (
                          <p className="text-[11px] leading-5 text-slate-500">
                            适合补资料：{uploadSlots.map((slot) => slot.label).join('、')}
                          </p>
                        )}
                        {clarifySlots.length > 0 && (
                          <p className="text-[11px] leading-5 text-slate-500">
                            适合快速澄清：{clarifySlots.map((slot) => slot.label).join('、')}
                          </p>
                        )}
                        {passiveSlots.length > 0 && (
                          <p className="text-[11px] leading-5 text-slate-400">
                            继续观察：{passiveSlots.map((slot) => slot.label).join('、')}
                          </p>
                        )}
                        {(item.backgroundSources || []).length > 0 && (
                          <p className="text-[11px] leading-5 text-slate-500">
                            当前背景：{(item.backgroundSources || []).map((source) => backgroundSourceLabel(source)).join('、')}
                          </p>
                        )}
                        {(uploadSlots.length > 0 || clarifySlots.length > 0) && onResolveGapAction ? (
                          <div className="flex flex-wrap gap-2">
                            {uploadSlots.length > 0 && (
                              <button
                                type="button"
                                className="rounded-2xl border border-[#D8E5FF] bg-white px-3 py-2 text-[11px] font-bold text-[#4A63CF] transition-colors hover:border-[#5B7BFE] hover:text-[#3652c9]"
                                onClick={() =>
                                  onResolveGapAction({
                                    eventLineId: item.eventLineId,
                                    title: item.title,
                                    actionType: 'upload_docs',
                                    slotLabels: uploadSlots.map((slot) => slot.label),
                                  })
                                }
                              >
                                补资料
                              </button>
                            )}
                            {clarifySlots.length > 0 && (
                              <button
                                type="button"
                                className="rounded-2xl border border-amber-200 bg-white px-3 py-2 text-[11px] font-bold text-amber-700 transition-colors hover:border-amber-300 hover:text-amber-800"
                                onClick={() =>
                                  onResolveGapAction({
                                    eventLineId: item.eventLineId,
                                    title: item.title,
                                    actionType: 'clarify_now',
                                    slotLabels: clarifySlots.map((slot) => slot.label),
                                  })
                                }
                              >
                                快速澄清
                              </button>
                            )}
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>
                );
              })()
            ))}
          </div>
        </Section>
      )}

      <Section title="本周事实" subtitle="先看事实，不先解释原因。">
        <div className="space-y-4">
          <ReviewMetricGrid metrics={analysis.metricCards || []} />
          {analysis.confirmedFacts.length > 0 ? (
            <div className="space-y-2">
              {analysis.confirmedFacts.map((item) => (
                <div key={item} className="rounded-2xl bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-700">
                  {item}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-500">当前还没有足够稳定的事实摘要。</div>
          )}
        </div>
      </Section>

      <Section title="AI 判断依据" subtitle="下面保留旧的判断依据和假设，用来解释为什么系统会给出上面的事件线结论。">
        <div className="space-y-4">
          <div className="rounded-2xl bg-gray-50 px-4 py-4">
            <p className="text-[15px] font-bold text-gray-900">{analysis.headline}</p>
          </div>
          {analysis.evidenceWeights.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2">
              {analysis.evidenceWeights.map((item) => (
                <div key={`${item.sourceType}-${item.label}`} className="rounded-2xl border border-gray-200 bg-white px-4 py-4">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{sourceTypeLabel(item.sourceType)}</span>
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${item.weight === 'high' ? 'bg-emerald-50 text-emerald-700' : item.weight === 'medium' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>
                      {item.weight === 'high' ? '高权重' : item.weight === 'medium' ? '中权重' : '低权重'}
                    </span>
                  </div>
                  <p className="mt-3 text-[13px] font-bold text-gray-900">{item.label}</p>
                  <p className="mt-2 text-[12px] leading-5 text-gray-600">{item.rationale}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Section>

      <Section title="补充可能性分析" subtitle="旧的假设分析仍然保留，作为事件线风险/机会卡下面的补充解释。">
        {analysis.hypothesisHighlights.length > 0 ? (
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
        ) : (
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-500">当前还没有足够稳定的可能性分析。</div>
        )}
      </Section>
    </div>
  );
}
