import React, { useEffect, useMemo, useState } from 'react';

import type {
  AgentWeeklyDigest,
  AgentWeeklyPlan,
  HierarchyReport,
  ReviewActionCard,
  ReviewActionExecutionResult,
  ReviewDashboardCardTarget,
  ReviewSimulationBundle,
  WeeklyReviewAnalysis,
} from '../../../shared/types';
import { AgentWeeklyDigestPanel } from './AgentWeeklyDigestPanel';
import { AgentExecutionPanel } from './AgentExecutionPanel';
import { AgentWeeklyPlanPanel } from './AgentWeeklyPlanPanel';
import { HierarchyReportCard } from './HierarchyReportCard';
import { WeeklyReviewAnalysisPanel, type EventLineGapActionPayload } from './WeeklyReviewAnalysisPanel';
import { WeeklyReviewSimulationPanel } from './WeeklyReviewSimulationPanel';

type SummaryScope = 'self' | 'department' | 'org';

type WeeklyReviewSummaryPanelProps = {
  selfReport?: HierarchyReport | null;
  selfAnalysis?: WeeklyReviewAnalysis | null;
  departmentReports: HierarchyReport[];
  executiveOrgReport?: HierarchyReport | null;
  agentDepartmentDigests: AgentWeeklyDigest[];
  agentDepartmentPlans: AgentWeeklyPlan[];
  simulationBundle?: ReviewSimulationBundle | null;
  onTriggerAction?: (action: ReviewActionCard, report: HierarchyReport) => Promise<ReviewActionExecutionResult | void> | ReviewActionExecutionResult | void;
  onOpenActionResult?: (result: ReviewActionExecutionResult, action: ReviewActionCard, report: HierarchyReport) => Promise<void> | void;
  onDrillTarget?: (target: ReviewDashboardCardTarget) => Promise<void> | void;
  onResolveGapAction?: (payload: EventLineGapActionPayload) => void;
};

type DepartmentSummaryEntry = {
  id: string;
  label: string;
  report?: HierarchyReport | null;
  digest?: AgentWeeklyDigest | null;
  plan?: AgentWeeklyPlan | null;
};

function normalizeDepartmentKey(value: string) {
  return value.trim().toLowerCase();
}

function buildDepartmentEntries(
  departmentReports: HierarchyReport[],
  agentDepartmentDigests: AgentWeeklyDigest[],
  agentDepartmentPlans: AgentWeeklyPlan[],
): DepartmentSummaryEntry[] {
  const entryMap = new Map<string, DepartmentSummaryEntry>();

  departmentReports.forEach((report) => {
    const label = report.scopeRefId.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, {
      id: key,
      label: existing?.label || label,
      report,
      digest: existing?.digest,
      plan: existing?.plan,
    });
  });

  agentDepartmentDigests.forEach((digest) => {
    const label = digest.departmentName.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, {
      id: key,
      label: existing?.label || label,
      report: existing?.report,
      digest,
      plan: existing?.plan,
    });
  });

  agentDepartmentPlans.forEach((plan) => {
    const label = plan.departmentName.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, {
      id: key,
      label: existing?.label || label,
      report: existing?.report,
      digest: existing?.digest,
      plan,
    });
  });

  return Array.from(entryMap.values());
}

export function WeeklyReviewSummaryPanel({
  selfReport,
  selfAnalysis,
  departmentReports,
  executiveOrgReport,
  agentDepartmentDigests,
  agentDepartmentPlans,
  simulationBundle,
  onTriggerAction,
  onOpenActionResult,
  onDrillTarget,
  onResolveGapAction,
}: WeeklyReviewSummaryPanelProps) {
  const departmentEntries = useMemo(
    () => buildDepartmentEntries(departmentReports, agentDepartmentDigests, agentDepartmentPlans),
    [agentDepartmentDigests, agentDepartmentPlans, departmentReports],
  );

  const summaryScopes = useMemo(() => {
    const scopes: Array<{ key: SummaryScope; label: string }> = [];
    if (selfReport || selfAnalysis) scopes.push({ key: 'self', label: '我的总结' });
    if (departmentEntries.length > 0) scopes.push({ key: 'department', label: '部门总结' });
    if (executiveOrgReport || simulationBundle) scopes.push({ key: 'org', label: '机构总结' });
    return scopes;
  }, [departmentEntries.length, executiveOrgReport, selfAnalysis, selfReport, simulationBundle]);

  const [activeScope, setActiveScope] = useState<SummaryScope>(summaryScopes[0]?.key || 'self');
  const [activeDepartmentId, setActiveDepartmentId] = useState<string>(departmentEntries[0]?.id || '');

  useEffect(() => {
    if (!summaryScopes.some((scope) => scope.key === activeScope)) {
      setActiveScope(summaryScopes[0]?.key || 'self');
    }
  }, [activeScope, summaryScopes]);

  useEffect(() => {
    if (!departmentEntries.some((entry) => entry.id === activeDepartmentId)) {
      setActiveDepartmentId(departmentEntries[0]?.id || '');
    }
  }, [activeDepartmentId, departmentEntries]);

  const activeDepartmentEntry = departmentEntries.find((entry) => entry.id === activeDepartmentId) || null;
  const activeDepartmentWeekLabel =
    activeDepartmentEntry?.report?.weekLabel || activeDepartmentEntry?.plan?.weekLabel || activeDepartmentEntry?.digest?.weekLabel || '';
  const orgWeekLabel =
    executiveOrgReport?.weekLabel ||
    departmentEntries[0]?.report?.weekLabel ||
    agentDepartmentPlans[0]?.weekLabel ||
    agentDepartmentDigests[0]?.weekLabel ||
    '';

  if (summaryScopes.length === 0) {
    return null;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-[16px] font-bold text-gray-900">周判断视角</h3>
            <p className="mt-1 text-[12px] leading-6 text-gray-500">同一批任务痕迹和背景证据，分别为个人、部门和机构产出事实、判断、可能性分析与建议动作。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {summaryScopes.map((scope) => (
              <button
                key={scope.key}
                type="button"
                className={`rounded-2xl px-4 py-2 text-[12px] font-bold transition ${
                  activeScope === scope.key
                    ? 'bg-[#5B7BFE] text-white shadow-sm'
                    : 'border border-gray-200 bg-white text-gray-500 hover:text-gray-800'
                }`}
                onClick={() => setActiveScope(scope.key)}
              >
                {scope.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {activeScope === 'self' && selfReport && (
        <HierarchyReportCard
          report={selfReport}
          title="我的本周总结"
          subtitle="只基于当前登录账号本周工作任务生成，不混入其他成员、部门或机构层信息。"
          tone="emerald"
          analysis={selfAnalysis}
          showAnonymousInsights={false}
          onTriggerAction={onTriggerAction}
          onOpenActionResult={onOpenActionResult}
          onDrillTarget={onDrillTarget}
        />
      )}

      {activeScope === 'self' && !selfReport && selfAnalysis && (
        <WeeklyReviewAnalysisPanel analysis={selfAnalysis} onResolveGapAction={onResolveGapAction} />
      )}

      {activeScope === 'department' && activeDepartmentEntry && (
        <div className="space-y-4">
          {departmentEntries.length > 1 && (
            <div className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap gap-2">
                {departmentEntries.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className={`rounded-2xl px-4 py-2 text-[12px] font-bold transition ${
                      activeDepartmentId === entry.id
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'border border-gray-200 bg-white text-gray-500 hover:text-gray-800'
                    }`}
                    onClick={() => setActiveDepartmentId(entry.id)}
                  >
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeDepartmentEntry.report && (
            <HierarchyReportCard
              report={activeDepartmentEntry.report}
              title={`${activeDepartmentEntry.label}总结`}
              subtitle="部门总结只聚合该部门本周的工作域复盘样本，不包含其他部门和机构层内容。"
              tone="slate"
              onTriggerAction={onTriggerAction}
              onOpenActionResult={onOpenActionResult}
              onDrillTarget={onDrillTarget}
            />
          )}

          {activeDepartmentEntry.digest && (
            <AgentWeeklyDigestPanel
              digests={[activeDepartmentEntry.digest]}
              title={`${activeDepartmentEntry.label}周摘要`}
              subtitle="这是该部门本周真实工作痕迹收敛后的摘要。"
            />
          )}

          {activeDepartmentEntry.plan && (
            <AgentWeeklyPlanPanel
              plans={[activeDepartmentEntry.plan]}
              title={`${activeDepartmentEntry.label}周计划`}
              subtitle="这是该部门本周计划层的结构化视图。"
            />
          )}

          {activeDepartmentWeekLabel && (
            <AgentExecutionPanel
              weekLabel={activeDepartmentWeekLabel}
              departmentName={activeDepartmentEntry.label}
              title={`${activeDepartmentEntry.label}机器人正式任务`}
              subtitle="把机器人本周真实工作同步成正式任务对象，供部门负责人和 CEO 判断执行深度，而不是只看摘要。"
            />
          )}
        </div>
      )}

      {activeScope === 'org' && (
        <div className="space-y-4">
          {executiveOrgReport && (
            <HierarchyReportCard
              report={executiveOrgReport}
              title="机构本周总结"
              subtitle="机构层总结会对照各部门月度 DNA 与本周实际推进，帮助 CEO 判断方向一致性与潜在风险。"
              tone="amber"
              onTriggerAction={onTriggerAction}
              onOpenActionResult={onOpenActionResult}
              onDrillTarget={onDrillTarget}
            />
          )}

          {simulationBundle && (
            <details className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
              <summary className="cursor-pointer text-[13px] font-bold text-gray-700">查看模拟对照口径</summary>
              <div className="mt-4">
                <WeeklyReviewSimulationPanel bundle={simulationBundle} />
              </div>
            </details>
          )}

          {orgWeekLabel && (
            <AgentExecutionPanel
              weekLabel={orgWeekLabel}
              title="机器人正式执行层"
              subtitle="这里展示的是机器人已同步成正式任务对象的执行层事实，机构视角可以据此判断各机器人部门本周到底推进了哪些具体事项。"
            />
          )}
        </div>
      )}
    </div>
  );
}
