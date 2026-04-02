import React, { useEffect, useMemo, useState } from 'react';

import type {
  AgentWeeklyDigest,
  AgentWeeklyPlan,
  HierarchyReport,
  OrganizationDnaModule,
  ReviewActionCard,
  ReviewActionExecutionResult,
  ReviewDashboardCardTarget,
  ReviewSimulationBundle,
  WeeklyReviewAnalysis,
} from '../../../shared/types';
import { AgentWeeklyDigestPanel } from './AgentWeeklyDigestPanel';
import { AgentExecutionPanel } from './AgentExecutionPanel';
import { AgentWeeklyPlanPanel } from './AgentWeeklyPlanPanel';
import { WeeklyReviewSimulationPanel } from './WeeklyReviewSimulationPanel';

type ViewLens = 'all' | 'personal' | 'department' | 'org';

type WeeklyReviewSummaryPanelProps = {
  selfReport?: HierarchyReport | null;
  selfAnalysis?: WeeklyReviewAnalysis | null;
  departmentReports: HierarchyReport[];
  executiveOrgReport?: HierarchyReport | null;
  organizationDnaModules?: OrganizationDnaModule[];
  onUploadOrganizationDna?: (moduleKey: OrganizationDnaModule['moduleKey']) => Promise<void> | void;
  orgDnaSavingKey?: OrganizationDnaModule['moduleKey'] | null;
  agentDepartmentDigests: AgentWeeklyDigest[];
  agentDepartmentPlans: AgentWeeklyPlan[];
  simulationBundle?: ReviewSimulationBundle | null;
  onTriggerAction?: (action: ReviewActionCard, report: HierarchyReport) => Promise<ReviewActionExecutionResult | void> | ReviewActionExecutionResult | void;
  onOpenActionResult?: (result: ReviewActionExecutionResult, action: ReviewActionCard, report: HierarchyReport) => Promise<void> | void;
  onDrillTarget?: (target: ReviewDashboardCardTarget) => Promise<void> | void;
  viewerRole?: 'employee' | 'department_lead' | 'admin';
};

type DepartmentEntry = {
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
): DepartmentEntry[] {
  const entryMap = new Map<string, DepartmentEntry>();

  departmentReports.forEach((report) => {
    const label = report.scopeRefId.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, { id: key, label: existing?.label || label, report, digest: existing?.digest, plan: existing?.plan });
  });

  agentDepartmentDigests.forEach((digest) => {
    const label = digest.departmentName.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, { id: key, label: existing?.label || label, report: existing?.report, digest, plan: existing?.plan });
  });

  agentDepartmentPlans.forEach((plan) => {
    const label = plan.departmentName.trim();
    if (!label) return;
    const key = normalizeDepartmentKey(label);
    const existing = entryMap.get(key);
    entryMap.set(key, { id: key, label: existing?.label || label, report: existing?.report, digest: existing?.digest, plan });
  });

  return Array.from(entryMap.values());
}

const WEEKLY_REVIEW_DNA_QUICK_MODULES: Array<{ moduleKey: OrganizationDnaModule['moduleKey']; title: string }> = [
  { moduleKey: 'organization_intro', title: '组织介绍' },
  { moduleKey: 'team_intro', title: '团队介绍' },
  { moduleKey: 'business_intro', title: '业务介绍' },
];

/** 从 HierarchyReport 中提取关键判断信号 */
function ReportSignals({ report, label }: { report: HierarchyReport; label: string }) {
  return (
    <div className="rounded-3xl border border-gray-200 bg-white px-5 py-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[15px] font-bold text-gray-900">{label}</span>
        {report.coverageScore != null && (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">覆盖度 {report.coverageScore}%</span>
        )}
        {report.confidenceScore != null && (
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">置信 {report.confidenceScore}%</span>
        )}
        {report.safeOutputMode && (
          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
            report.safeOutputMode === 'full_judgment' ? 'bg-emerald-50 text-emerald-700'
            : report.safeOutputMode === 'summary_only' ? 'bg-amber-50 text-amber-700'
            : 'bg-slate-100 text-slate-500'
          }`}>
            {report.safeOutputMode === 'full_judgment' ? '完整判断' : report.safeOutputMode === 'summary_only' ? '仅可总结' : '待补信息'}
          </span>
        )}
      </div>

      {report.headline && (
        <p className="mt-3 text-[14px] font-bold leading-7 text-gray-800">{report.headline}</p>
      )}
      {report.summary && (
        <p className="mt-2 text-[13px] leading-6 text-gray-600">{report.summary}</p>
      )}

      {report.focusAreas.length > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400">本周焦点</p>
          <div className="mt-2 space-y-1.5">
            {report.focusAreas.map((item) => (
              <div key={item} className="rounded-2xl bg-slate-50 px-4 py-2.5 text-[12px] leading-5 text-gray-700">{item}</div>
            ))}
          </div>
        </div>
      )}

      {report.supportSignals.length > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400">需要支持的信号</p>
          <div className="mt-2 space-y-1.5">
            {report.supportSignals.map((item) => (
              <div key={item} className="rounded-2xl bg-amber-50/70 px-4 py-2.5 text-[12px] leading-5 text-amber-800">{item}</div>
            ))}
          </div>
        </div>
      )}

      {report.suggestedActions.length > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400">建议动作</p>
          <div className="mt-2 space-y-1.5">
            {report.suggestedActions.map((item) => (
              <div key={item} className="rounded-2xl bg-blue-50/70 px-4 py-2.5 text-[12px] leading-5 text-[#33449a]">{item}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function WeeklyReviewSummaryPanel({
  selfReport,
  selfAnalysis,
  departmentReports,
  executiveOrgReport,
  organizationDnaModules = [],
  onUploadOrganizationDna,
  orgDnaSavingKey = null,
  agentDepartmentDigests,
  agentDepartmentPlans,
  simulationBundle,
  viewerRole,
}: WeeklyReviewSummaryPanelProps) {
  const role = viewerRole || 'employee';
  const departmentEntries = useMemo(
    () => buildDepartmentEntries(departmentReports, agentDepartmentDigests, agentDepartmentPlans),
    [agentDepartmentDigests, agentDepartmentPlans, departmentReports],
  );

  const lensOptions = useMemo(() => {
    const options: Array<{ key: ViewLens; label: string }> = [];
    // 员工：只有个人视角
    if (selfReport || selfAnalysis) options.push({ key: 'personal', label: '个人视角' });
    // 部门负责人：个人 + 部门
    if (role !== 'employee' && departmentEntries.length > 0) {
      options.push({ key: 'department', label: '部门视角' });
    }
    // CEO：个人 + 部门 + 机构 + 全局
    if (role === 'admin') {
      if (executiveOrgReport || simulationBundle) options.push({ key: 'org', label: 'CEO 视角' });
      options.push({ key: 'all', label: '全局视角' });
    }
    return options;
  }, [departmentEntries.length, executiveOrgReport, role, selfAnalysis, selfReport, simulationBundle]);

  const [activeLens, setActiveLens] = useState<ViewLens>('all');
  const [activeDepartmentId, setActiveDepartmentId] = useState<string>(departmentEntries[0]?.id || '');

  useEffect(() => {
    if (!lensOptions.some((opt) => opt.key === activeLens)) {
      setActiveLens('all');
    }
  }, [activeLens, lensOptions]);

  useEffect(() => {
    if (!departmentEntries.some((entry) => entry.id === activeDepartmentId)) {
      setActiveDepartmentId(departmentEntries[0]?.id || '');
    }
  }, [activeDepartmentId, departmentEntries]);

  const activeDepartmentEntry = departmentEntries.find((entry) => entry.id === activeDepartmentId) || null;
  const orgWeekLabel =
    executiveOrgReport?.weekLabel ||
    departmentEntries[0]?.report?.weekLabel ||
    agentDepartmentPlans[0]?.weekLabel ||
    agentDepartmentDigests[0]?.weekLabel ||
    '';

  const hasAnyContent = selfReport || departmentEntries.length > 0 || executiveOrgReport || simulationBundle || agentDepartmentDigests.length > 0 || agentDepartmentPlans.length > 0;
  if (!hasAnyContent) return null;

  return (
    <div className="space-y-4">
      {/* 首屏：判断状态 + 理解优先输出 */}
      {selfAnalysis && (
        <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-[16px] font-bold text-gray-900">
              {selfAnalysis.scope === 'work' ? '本周摘要' : '成长摘要'}
            </h3>
            {WEEKLY_REVIEW_DNA_QUICK_MODULES.map((entry) => {
              const module = organizationDnaModules.find((item) => item.moduleKey === entry.moduleKey);
              const isReady = module?.readinessStatus === 'ready';
              const isSaving = orgDnaSavingKey === entry.moduleKey;
              return (
                <button
                  key={entry.moduleKey}
                  type="button"
                  onClick={() => {
                    if (!onUploadOrganizationDna || isSaving) return;
                    void onUploadOrganizationDna(entry.moduleKey);
                  }}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-bold transition ${
                    isReady
                      ? 'bg-[#EFFFF3] text-[#16A34A] hover:bg-[#E7FAEC]'
                      : 'bg-[#F3F6FB] text-[#94A3B8] hover:bg-[#EDF2F7]'
                  } ${isSaving ? 'cursor-wait opacity-80' : ''}`}
                  title={
                    module?.readinessSummary
                      ? `${entry.title} · ${module.readinessSummary}`
                      : `上传 ${entry.title}（支持 .md / .docx）`
                  }
                  disabled={!onUploadOrganizationDna || isSaving}
                >
                  <span
                    className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${
                      isReady ? 'bg-[#22C55E] text-white' : 'bg-white text-[#D1D5DB]'
                    }`}
                  >
                    {isSaving ? '…' : isReady ? '✓' : '·'}
                  </span>
                  <span>{entry.title}</span>
                </button>
              );
            })}
          </div>

          <div>
            <p className="mt-1 text-[12px] leading-6 text-gray-500">
              先理解本周做的事意味着什么，再看需要什么动作。
            </p>
          </div>

          {/* 状态条 */}
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-bold text-slate-600">
              {selfAnalysis.confirmedFacts.length > 0 ? selfAnalysis.confirmedFacts[0] : '暂无事实摘要'}
            </span>
          </div>

          {selfAnalysis.weeklyOverview && (
            <div className="space-y-2.5">
              <div className="rounded-2xl bg-slate-50 px-4 py-3">
                <p className="text-[11px] font-bold text-slate-400">本周概况</p>
                <p className="mt-1 text-[13px] leading-6 text-gray-800">{selfAnalysis.weeklyOverview}</p>
                {selfAnalysis.weeklyFocusLines.length > 0 && (
                  <p className="mt-2 text-[12px] leading-5 text-slate-500">
                    主线：{selfAnalysis.weeklyFocusLines.join('；')}
                  </p>
                )}
              </div>
              {selfAnalysis.weeklyNextFocus.length > 0 && (
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  <p className="text-[11px] font-bold text-slate-400">下周重点</p>
                  <p className="mt-1 text-[13px] leading-6 text-gray-800">{selfAnalysis.weeklyNextFocus.join('；')}</p>
                </div>
              )}
            </div>
          )}

          {/* 如果有叙事分析（narrativeAnalyses），展示第一条的 4 个核心问题 */}
          {(selfAnalysis.narrativeAnalyses ?? []).length > 0 ? (
            <div className="space-y-2.5">
              {(selfAnalysis.narrativeAnalyses ?? []).slice(0, 2).map((n) => (
                <div key={n.eventLineId} className="rounded-2xl border border-indigo-100 bg-indigo-50/30 px-4 py-4 space-y-2">
                  <p className="text-[13px] font-bold text-gray-900">{n.eventLineName}</p>
                  <div className="space-y-1.5 text-[12px] leading-5">
                    <p><span className="font-bold text-slate-500">这是什么事：</span><span className="text-gray-800">{n.whatThisIs}</span></p>
                    <p><span className="font-bold text-slate-500">为什么重要：</span><span className="text-gray-800">{n.whyImportant}</span></p>
                    <p><span className="font-bold text-slate-500">推进到哪：</span><span className="text-gray-800">{n.currentProgress}</span></p>
                    <p><span className="font-bold text-amber-500">还缺什么：</span><span className="text-gray-800">{n.missingUnderstanding}</span></p>
                  </div>
                </div>
              ))}
            </div>
          ) : selfReport ? (
            <div className="space-y-2.5">
              <div className="rounded-2xl bg-slate-50 px-4 py-3">
                <p className="text-[11px] font-bold text-slate-400">本周概况</p>
                <p className="mt-1 text-[13px] leading-6 text-gray-800">{selfReport.headline}</p>
              </div>
              {selfReport.focusAreas.length > 0 && (
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                  <p className="text-[11px] font-bold text-slate-400">焦点</p>
                  <p className="mt-1 text-[13px] leading-6 text-gray-800">{selfReport.focusAreas.join('；')}</p>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* 角色透镜切换 */}
      <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-[16px] font-bold text-gray-900">角色透镜</h3>
            <p className="mt-1 text-[12px] leading-6 text-gray-500">
              同一批事件线和任务，用不同角色的视角来看。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {lensOptions.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={`rounded-2xl px-4 py-2 text-[12px] font-bold transition ${
                  activeLens === opt.key
                    ? 'bg-[#5B7BFE] text-white shadow-sm'
                    : 'border border-gray-200 bg-white text-gray-500 hover:text-gray-800'
                }`}
                onClick={() => setActiveLens(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── 全局视角：概览所有层级的核心信号 ── */}
      {activeLens === 'all' && (
        <div className="space-y-4">
          {selfReport && <ReportSignals report={selfReport} label="个人本周信号" />}
          {departmentEntries.map((entry) => entry.report ? (
            <ReportSignals key={entry.id} report={entry.report} label={`${entry.label}信号`} />
          ) : null)}
          {executiveOrgReport && <ReportSignals report={executiveOrgReport} label="机构整体信号" />}

          {agentDepartmentDigests.length > 0 && (
            <AgentWeeklyDigestPanel
              digests={agentDepartmentDigests}
              title="机器人部门周摘要"
              subtitle="各机器人部门本周真实工作痕迹收敛后的摘要。"
            />
          )}
        </div>
      )}

      {/* ── 个人视角：我在哪些线上出了力 ── */}
      {activeLens === 'personal' && (
        <div className="space-y-4">
          {selfReport ? (
            <ReportSignals report={selfReport} label="我的本周判断" />
          ) : (
            <div className="rounded-3xl border border-dashed border-gray-200 bg-gray-50/60 px-6 py-8 text-center text-[13px] text-gray-400">
              当前还没有产出个人层的判断报告。需要先在上方完成复盘采集并提交。
            </div>
          )}
        </div>
      )}

      {/* ── 部门视角：这个部门负责的线推进如何 ── */}
      {activeLens === 'department' && (
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

          {activeDepartmentEntry?.report && (
            <ReportSignals report={activeDepartmentEntry.report} label={`${activeDepartmentEntry.label}本周判断`} />
          )}

          {activeDepartmentEntry?.digest && (
            <AgentWeeklyDigestPanel
              digests={[activeDepartmentEntry.digest]}
              title={`${activeDepartmentEntry.label}周摘要`}
              subtitle="该部门本周真实工作痕迹收敛后的摘要。"
            />
          )}

          {activeDepartmentEntry?.plan && (
            <AgentWeeklyPlanPanel
              plans={[activeDepartmentEntry.plan]}
              title={`${activeDepartmentEntry.label}周计划`}
              subtitle="该部门本周计划层的结构化视图。"
            />
          )}

          {activeDepartmentEntry && (activeDepartmentEntry.report?.weekLabel || activeDepartmentEntry.plan?.weekLabel || activeDepartmentEntry.digest?.weekLabel) && (
            <AgentExecutionPanel
              weekLabel={activeDepartmentEntry.report?.weekLabel || activeDepartmentEntry.plan?.weekLabel || activeDepartmentEntry.digest?.weekLabel || ''}
              departmentName={activeDepartmentEntry.label}
              title={`${activeDepartmentEntry.label}机器人执行层`}
              subtitle="机器人本周同步成正式任务的执行事实。"
            />
          )}
        </div>
      )}

      {/* ── CEO 视角：跨线看哪些线对机构最关键 ── */}
      {activeLens === 'org' && (
        <div className="space-y-4">
          {executiveOrgReport && (
            <ReportSignals report={executiveOrgReport} label="机构本周判断" />
          )}

          {agentDepartmentDigests.length > 0 && (
            <AgentWeeklyDigestPanel
              digests={agentDepartmentDigests}
              title="各部门周摘要"
              subtitle="机器人部门本周工作痕迹的结构化收敛。"
            />
          )}

          {orgWeekLabel && (
            <AgentExecutionPanel
              weekLabel={orgWeekLabel}
              title="机器人执行层总览"
              subtitle="各机器人部门本周同步成正式任务的执行事实。"
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
        </div>
      )}
    </div>
  );
}
