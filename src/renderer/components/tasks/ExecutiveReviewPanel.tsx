import type { AgentWeeklyDigest, AgentWeeklyPlan, HierarchyReport, ReviewSimulationBundle } from '../../../shared/types';
import { AgentWeeklyDigestPanel } from './AgentWeeklyDigestPanel';
import { AgentWeeklyPlanPanel } from './AgentWeeklyPlanPanel';
import { HierarchyReportCard } from './HierarchyReportCard';
import { WeeklyReviewSimulationPanel } from './WeeklyReviewSimulationPanel';

type ExecutiveReviewPanelProps = {
  executiveOrgReport?: HierarchyReport | null;
  departmentReports: HierarchyReport[];
  agentDepartmentDigests: AgentWeeklyDigest[];
  agentDepartmentPlans: AgentWeeklyPlan[];
  simulationBundle?: ReviewSimulationBundle | null;
};

export function ExecutiveReviewPanel({
  executiveOrgReport,
  departmentReports,
  agentDepartmentDigests,
  agentDepartmentPlans,
  simulationBundle,
}: ExecutiveReviewPanelProps) {
  const hasRealRollup = !!executiveOrgReport || departmentReports.length > 0;
  const hasAgentDigest = agentDepartmentDigests.length > 0;
  const hasAgentPlans = agentDepartmentPlans.length > 0;

  if (!hasRealRollup && !simulationBundle && !hasAgentDigest && !hasAgentPlans) {
    return null;
  }

  return (
    <div className="space-y-5">
      {hasAgentPlans && <AgentWeeklyPlanPanel plans={agentDepartmentPlans} />}
      {hasAgentDigest && <AgentWeeklyDigestPanel digests={agentDepartmentDigests} />}

      {hasRealRollup && (
        <div className="rounded-3xl border border-amber-200 bg-[linear-gradient(135deg,rgba(255,251,235,0.95),rgba(255,255,255,1))] px-6 py-5 shadow-sm">
          <h2 className="text-[18px] font-bold text-gray-900">CEO 真实聚合视角</h2>
          <p className="mt-1 text-[12px] leading-6 text-gray-600">
            只看工作域，基于当前系统里真实存在的部门配置、月度 DNA 和周复盘条目生成。若某个部门样本不足，会明确提示缺口而不是硬写结论。
          </p>
        </div>
      )}

      {executiveOrgReport && (
        <HierarchyReportCard
          report={executiveOrgReport}
          title="机构真实聚合视角"
          subtitle="机构层会对照部门月度 DNA 和本周实际推进，帮助 CEO 看方向一致性、偏航和需要上提支持的点。"
          tone="amber"
        />
      )}

      {departmentReports.length > 0 && (
        <div className="grid gap-5 xl:grid-cols-2">
          {departmentReports.map((report) => (
            <HierarchyReportCard
              key={report.id}
              report={report}
              title={`${report.scopeRefId} 真实聚合视角`}
              subtitle="只聚合工作域周复盘；如果这个部门本周没有样本，卡片会明确提醒先补输入。"
              tone="slate"
            />
          ))}
        </div>
      )}

      {simulationBundle && (
        <div className="space-y-4">
          {hasRealRollup && (
            <div className="rounded-3xl border border-gray-200 bg-white px-6 py-5 shadow-sm">
              <h3 className="text-[16px] font-bold text-gray-900">20 人模拟对照口径</h3>
              <p className="mt-1 text-[12px] leading-6 text-gray-600">
                真实聚合之外，仍保留一套 20 人模拟视角，方便你继续比较“真实输入”与“理想分析口径”之间的差异。
              </p>
            </div>
          )}
          <WeeklyReviewSimulationPanel bundle={simulationBundle} />
        </div>
      )}
    </div>
  );
}
