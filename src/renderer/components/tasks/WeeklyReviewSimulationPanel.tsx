import type { ReviewSimulationBundle } from '../../../shared/types';
import { HierarchyReportCard } from './HierarchyReportCard';

type WeeklyReviewSimulationPanelProps = {
  bundle: ReviewSimulationBundle;
};

export function WeeklyReviewSimulationPanel({ bundle }: WeeklyReviewSimulationPanelProps) {
  return (
    <div className="space-y-5">
      <div className="rounded-3xl border border-amber-200 bg-[linear-gradient(135deg,rgba(255,247,237,0.96),rgba(255,255,255,0.98))] px-6 py-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-[18px] font-bold text-gray-900">{bundle.label}</h2>
            <p className="mt-1 text-[12px] leading-6 text-gray-600">
              仅面向 CEO 的工作域模拟视角，不读取任何个人成长或隐私内容。当前先按约 {bundle.sampleSize} 人、4 个部门做调参，用来校准总结和分析口径。
            </p>
          </div>
          <span className="rounded-full bg-white px-4 py-2 text-[11px] font-bold text-amber-700 shadow-sm">
            只看工作域
          </span>
        </div>
      </div>

      {bundle.orgReport && (
        <HierarchyReportCard
          report={bundle.orgReport}
          title="CEO 模拟机构视角"
          subtitle="用机构 DNA 和部门月度 DNA 假设做解释层，不把弱关联推断当成既定事实。"
          tone="amber"
        />
      )}

      {bundle.departmentReports.length > 0 && (
        <div className="grid gap-5 xl:grid-cols-2">
          {bundle.departmentReports.map((report) => (
            <HierarchyReportCard
              key={report.id}
              report={report}
              title={`${report.scopeRefId} 模拟视角`}
              subtitle="模拟汇总约 5 人的一线工作域复盘，用来观察部门主线推进、偏差和潜在阻碍。"
              tone="slate"
            />
          ))}
        </div>
      )}
    </div>
  );
}
