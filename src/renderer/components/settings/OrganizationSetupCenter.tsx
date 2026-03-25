import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Building2,
  CalendarRange,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgEmployeeBindingSettings,
  OrgModelSettings,
  OrgQuarterKey,
  OrgQuarterPlanSettings,
  OrganizationDnaModule,
  OrgRoleLevel,
  OrgTaskControlLevel,
  OrgWorkflowTriggerType,
} from '../../../shared/types';
import { buildDepartmentInviteCode, buildDepartmentInviteShareText } from '../../../shared/departmentInvite';
import { OrganizationModelSettingsPanel, type OrgModelTab } from './OrganizationModelSettingsPanel';
import { OrganizationTreeCanvas } from './OrganizationTreeCanvas';

type LinkedSection = 'org_dna' | 'tasks' | 'handbook';

type Props = {
  value: OrgModelSettings;
  organizationDnaModules: OrganizationDnaModule[];
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  activeWeekLabel: string;
  initialAdvancedTab?: OrgModelTab | null;
  onChange: (next: OrgModelSettings) => void;
  onSave: (next?: OrgModelSettings) => Promise<void> | void;
  onOpenSection: (section: LinkedSection) => void;
};

type SetupStepId = 'ceo' | 'department' | 'role' | 'people' | 'workflow' | 'planning';

type SetupStep = {
  id: SetupStepId;
  title: string;
  description: string;
  done: boolean;
  tab: OrgModelTab;
  stat: string;
};

type GeneratedTask = {
  id: string;
  title: string;
  helper: string;
  ownerLabel: string;
  tab?: OrgModelTab;
  section?: LinkedSection;
};

type DepartmentBuilderRow = {
  localId: string;
  departmentId: string;
  name: string;
  leaderUserId: string;
  leaderName: string;
  isConfirmed: boolean;
};

type DraftApplyMode = 'fill_empty' | 'overwrite';

const ROLE_LEVEL_OPTIONS: Array<{ value: OrgRoleLevel; label: string }> = [
  { value: 'organization_lead', label: '机构负责人' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'supervisor', label: '主管' },
  { value: 'employee', label: '员工' },
];

const WORKFLOW_TRIGGER_OPTIONS: Array<{ value: OrgWorkflowTriggerType; label: string }> = [
  { value: 'weekly_followup', label: '周会后推进' },
  { value: 'task_created', label: '任务创建后' },
  { value: 'meeting_closed', label: '会议结束后' },
  { value: 'client_update', label: '客户状态更新后' },
  { value: 'manual', label: '手动触发' },
];

const DEPARTMENT_COLORS = ['#5B7BFE', '#0EA5E9', '#14B8A6', '#F97316', '#EF4444', '#8B5CF6'];
const ORG_QUARTER_OPTIONS: OrgQuarterKey[] = ['Q1', 'Q2', 'Q3', 'Q4'];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function emptyBindingForUser(userId: string, departmentId: string | null = null): OrgEmployeeBindingSettings {
  return {
    userId,
    departmentId,
    primaryRoleId: null,
    managerUserId: null,
    isManager: false,
    projectRoleLabels: [],
    currentFocus: '',
    taskEditScope: 'self',
    canApproveTasks: false,
    canReassignTasks: false,
    canChangeDeadline: false,
    updatedAt: '',
  };
}

function toMultiline(values: string[]) {
  return values.join('\n');
}

function fromMultiline(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function currentQuarterKey(): OrgQuarterKey {
  const month = new Date().getMonth();
  if (month < 3) return 'Q1';
  if (month < 6) return 'Q2';
  if (month < 9) return 'Q3';
  return 'Q4';
}

function createEmptyQuarterPlan(year: string, quarter: OrgQuarterKey): OrgQuarterPlanSettings {
  return {
    id: `org_${year || 'draft'}_${quarter.toLowerCase()}`,
    year,
    quarter,
    theme: '',
    objective: '',
    keyResults: [],
    keyActions: [],
    majorRisks: [],
    updatedAt: '',
  };
}

function ensureQuarterPlans(plans: OrgQuarterPlanSettings[], year: string) {
  const byQuarter = new Map(plans.map((plan) => [plan.quarter, plan]));
  return ORG_QUARTER_OPTIONS.map((quarter) => {
    const current = byQuarter.get(quarter);
    return current
      ? { ...current, year: current.year || year, quarter }
      : createEmptyQuarterPlan(year, quarter);
  });
}

function createEmptyDepartmentQuarterPlan(year: string, quarter: OrgQuarterKey) {
  return {
    year,
    quarter,
    objective: '',
    deliverables: [],
    successMetrics: [],
    majorRisks: [],
    updatedAt: '',
  };
}

function buildQuarterDrafts(year: string, annualGoal: string, annualStrategy: string) {
  const normalizedYear = year.trim() || String(new Date().getFullYear());
  const lines = annualStrategy
    .split(/\n+/)
    .map((item) => item.trim().replace(/^[\d\-•\s]+/, ''))
    .filter(Boolean);
  const fallbacks: Record<OrgQuarterKey, { theme: string; objective: string }> = {
    Q1: { theme: '打稳底盘', objective: '先把组织骨架、关键背景资料和基础协同节奏建立起来。' },
    Q2: { theme: '跑通主线', objective: '把核心业务主线与跨部门协同真正跑顺，形成可复用闭环。' },
    Q3: { theme: '产品化与复用', objective: '把高频方法、工具和交付能力转成稳定可复用资产。' },
    Q4: { theme: '复盘与校准', objective: '围绕全年执行结果做复盘校准，准备下一年度的升级节奏。' },
  };
  return ORG_QUARTER_OPTIONS.map((quarter, index) => {
    const line = lines[index] || '';
    const fallback = fallbacks[quarter];
    return {
      id: `org_${normalizedYear}_${quarter.toLowerCase()}`,
      year: normalizedYear,
      quarter,
      theme: line ? `${quarter} 主线` : fallback.theme,
      objective: line || annualGoal.trim() || fallback.objective,
      keyResults: line ? [line] : [],
      keyActions: [],
      majorRisks: [],
      updatedAt: '',
    } satisfies OrgQuarterPlanSettings;
  });
}

function takeShortSentence(text: string) {
  const normalized = text
    .replace(/\s+/g, ' ')
    .replace(/[•·]/g, ' ')
    .trim();
  if (!normalized) return '';
  const sentence = normalized.split(/[。！？.!?；;]/)[0]?.trim() || normalized;
  return sentence.slice(0, 80);
}

function buildAnnualStrategyCandidate(
  organizationName: string,
  modules: OrganizationDnaModule[],
  currentGoal: string,
): Pick<OrgModelSettings['organization'], 'annualGoal' | 'annualStrategy'> {
  const moduleSummaryByKey = new Map(modules.map((module) => [module.moduleKey, takeShortSentence(module.summary || module.normalizedText || module.markdownContent || '')]));
  const orgIntro = moduleSummaryByKey.get('organization_intro') || '';
  const businessIntro = moduleSummaryByKey.get('business_intro') || '';
  const teamIntro = moduleSummaryByKey.get('team_intro') || '';
  const marketIntro = moduleSummaryByKey.get('market_intro') || '';
  const label = organizationName.trim() || '当前组织';
  const annualGoal = currentGoal.trim() || `围绕 ${label} 的核心业务与组织主线，把今年最关键的交付闭环、协作节奏和组织能力稳定下来。`;
  const strategyLines = [
    `围绕 ${label} 的年度目标，优先把真正服务主线的动作收口成可执行节奏，而不是继续分散投入。`,
    businessIntro ? `业务主线参考：${businessIntro}` : `业务主线需要继续从现有材料里收口为少数关键押注。`,
    orgIntro ? `组织定位参考：${orgIntro}` : `组织定位需要继续统一成可供 AI 读取的稳定背景。`,
    teamIntro ? `组织能力重点：${teamIntro}` : `团队能力侧重点应围绕岗位分工、协作节奏和交付闭环继续补齐。`,
    marketIntro ? `外部环境提示：${marketIntro}` : `外部环境与市场变化应作为本年度押注与风险判断的重要参考。`,
  ];
  return {
    annualGoal,
    annualStrategy: strategyLines.join('\n'),
  };
}

function mergeTextByMode(currentValue: string, nextValue: string, mode: DraftApplyMode) {
  if (mode === 'overwrite') return nextValue;
  return currentValue.trim() ? currentValue : nextValue;
}

function mergeListByMode(currentValue: string[], nextValue: string[], mode: DraftApplyMode) {
  if (mode === 'overwrite') return nextValue;
  return currentValue.length > 0 ? currentValue : nextValue;
}

function mergeQuarterPlanByMode(
  currentPlan: OrgQuarterPlanSettings,
  nextPlan: OrgQuarterPlanSettings,
  mode: DraftApplyMode,
): OrgQuarterPlanSettings {
  return {
    ...currentPlan,
    year: mergeTextByMode(currentPlan.year, nextPlan.year, mode),
    theme: mergeTextByMode(currentPlan.theme, nextPlan.theme, mode),
    objective: mergeTextByMode(currentPlan.objective, nextPlan.objective, mode),
    keyResults: mergeListByMode(currentPlan.keyResults, nextPlan.keyResults, mode),
    keyActions: mergeListByMode(currentPlan.keyActions, nextPlan.keyActions, mode),
    majorRisks: mergeListByMode(currentPlan.majorRisks, nextPlan.majorRisks, mode),
    updatedAt: mode === 'overwrite' ? '' : currentPlan.updatedAt,
  };
}

function getQuarterPlanStatus(plan: OrgQuarterPlanSettings) {
  if (!plan.objective.trim()) return '待补';
  if (plan.updatedAt) return '已校正';
  return '候选已生成';
}

function getDepartmentRelayStatus(department: OrgModelSettings['departments'][number]) {
  const hasContent = Boolean(
    department.businessContext.trim()
    || department.teamContext.trim()
    || department.quarterPlan.objective.trim()
    || department.quarterPlan.deliverables.length > 0
    || department.quarterPlan.successMetrics.length > 0
    || department.quarterPlan.majorRisks.length > 0,
  );
  if (!hasContent) return '待补';
  if (department.updatedAt || department.quarterPlan.updatedAt) return '已校正';
  return '候选已生成';
}

function getDepartmentLatestManualUpdate(department: OrgModelSettings['departments'][number]) {
  const latest = [department.updatedAt, department.quarterPlan.updatedAt].filter(Boolean).sort().at(-1);
  return latest ? new Date(latest).toLocaleString('zh-CN', { hour12: false }) : '';
}

function buildDepartmentDraft(
  department: OrgModelSettings['departments'][number],
  organizationName: string,
  focusedQuarterPlan: OrgQuarterPlanSettings,
) {
  const orgLabel = organizationName.trim() || '当前组织';
  const quarterLabel = `${focusedQuarterPlan.quarter} ${focusedQuarterPlan.theme || '季度主线'}`.trim();
  const leaderLabel = department.leaderName?.trim() || '部门负责人';
  const mission = department.mission.trim() || `${department.name} 的核心职责`;
  const businessContext = department.businessContext.trim() || `${department.name} 在 ${orgLabel} 当前组织主线中，主要承担 ${mission}。这一季应重点承接「${quarterLabel}」相关动作，并把部门输出转成可被其他团队协同使用的结果。`;
  const teamContext = department.teamContext.trim() || `当前由 ${leaderLabel} 牵头，团队需要围绕本季度目标形成稳定分工、协作节奏和问题升级路径。成员和岗位资料后续继续补齐，但本季度应先把关键职责和执行节奏跑顺。`;
  const objective = department.quarterPlan.objective.trim() || `承接 ${quarterLabel}，把 ${department.name} 的关键职责落成清晰、可交付、可复盘的季度结果。`;
  const deliverables = department.quarterPlan.deliverables.length > 0
    ? department.quarterPlan.deliverables
    : [
        `明确 ${department.name} 本季度的关键输出与协作边界`,
        `围绕「${quarterLabel}」形成 1-2 项稳定交付成果`,
        '把部门内高频动作逐步沉淀为可复用流程或模板',
      ];
  const successMetrics = department.quarterPlan.successMetrics.length > 0
    ? department.quarterPlan.successMetrics
    : [
        '部门季度目标已被拆成清晰执行重点',
        '关键输出能够直接支撑组织季度主线推进',
        '跨部门协作中的等待和返工明显减少',
      ];
  const majorRisks = department.quarterPlan.majorRisks.length > 0
    ? department.quarterPlan.majorRisks
    : [
        focusedQuarterPlan.majorRisks[0] || '组织季度主线本身还存在上游不确定性',
        '部门职责边界不清会导致任务反复',
        '负责人和成员分工尚未稳定会影响季度承接效率',
      ].filter(Boolean);
  return {
    businessContext,
    teamContext,
    quarterPlan: {
      ...department.quarterPlan,
      year: department.quarterPlan.year || focusedQuarterPlan.year,
      quarter: department.quarterPlan.quarter || focusedQuarterPlan.quarter,
      objective,
      deliverables,
      successMetrics,
      majorRisks,
    },
  };
}

export function OrganizationSetupCenter({
  value,
  organizationDnaModules,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  activeWeekLabel,
  initialAdvancedTab = null,
  onChange,
  onSave,
  onOpenSection,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(Boolean(initialAdvancedTab));
  const [advancedTab, setAdvancedTab] = useState<OrgModelTab>(initialAdvancedTab || 'overview');
  const [ceoCandidateId, setCeoCandidateId] = useState('');
  const [organizationNameDraft, setOrganizationNameDraft] = useState('');
  const [departmentBuilderRows, setDepartmentBuilderRows] = useState<DepartmentBuilderRow[]>([]);
  const [newRoleDepartmentId, setNewRoleDepartmentId] = useState('');
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleLevel, setNewRoleLevel] = useState<OrgRoleLevel>('department_lead');
  const [workflowRoleId, setWorkflowRoleId] = useState('');
  const [workflowName, setWorkflowName] = useState('');
  const [workflowTrigger, setWorkflowTrigger] = useState<OrgWorkflowTriggerType>('weekly_followup');
  const [focusTitle, setFocusTitle] = useState('');
  const [focusOwnerId, setFocusOwnerId] = useState('');
  const [focusDepartmentId, setFocusDepartmentId] = useState('');
  const [copiedInviteDepartmentId, setCopiedInviteDepartmentId] = useState('');
  const [departmentStepLocked, setDepartmentStepLocked] = useState(false);
  const [selectedStepId, setSelectedStepId] = useState<SetupStepId | null>(null);
  const [selectedStrategyQuarter, setSelectedStrategyQuarter] = useState<OrgQuarterKey>(currentQuarterKey());
  const [annualDraftApplyMode, setAnnualDraftApplyMode] = useState<DraftApplyMode>('fill_empty');
  const [quarterDraftApplyMode, setQuarterDraftApplyMode] = useState<DraftApplyMode>('fill_empty');
  const [departmentDraftApplyMode, setDepartmentDraftApplyMode] = useState<DraftApplyMode>('fill_empty');

  useEffect(() => {
    if (!initialAdvancedTab) return;
    setAdvancedTab(initialAdvancedTab);
    setAdvancedOpen(true);
  }, [initialAdvancedTab]);

  useEffect(() => {
    setOrganizationNameDraft(value.organization.name || '');
  }, [value.organization.name]);

  const activeEmployees = useMemo(
    () => employees.filter((item) => item.accountStatus !== 'disabled'),
    [employees],
  );

  const assignableEmployees = useMemo(
    () => activeEmployees.filter((item) => item.accountStatus === 'approved' || item.primaryRole === 'admin'),
    [activeEmployees],
  );

  const employeeById = useMemo(() => new Map(activeEmployees.map((item) => [item.id, item])), [activeEmployees]);
  const bindingsByUserId = useMemo(() => new Map(value.bindings.map((item) => [item.userId, item])), [value.bindings]);
  const roleById = useMemo(() => new Map(value.roles.map((item) => [item.id, item])), [value.roles]);

  const activeDepartments = useMemo(
    () => value.departments.filter((item) => item.active !== false),
    [value.departments],
  );
  const departmentById = useMemo(() => new Map(activeDepartments.map((item) => [item.id, item])), [activeDepartments]);
  const activeRoles = useMemo(
    () => value.roles.filter((item) => item.active !== false),
    [value.roles],
  );
  const strategyYear = value.organization.annualStrategyYear.trim() || String(new Date().getFullYear());
  const activeQuarter = currentQuarterKey();
  useEffect(() => {
    if (!ORG_QUARTER_OPTIONS.includes(selectedStrategyQuarter)) {
      setSelectedStrategyQuarter(activeQuarter);
    }
  }, [activeQuarter, selectedStrategyQuarter]);
  const orgQuarterPlans = useMemo(
    () => ensureQuarterPlans(value.organization.quarterPlans, strategyYear),
    [strategyYear, value.organization.quarterPlans],
  );
  const orgDnaCompletedCount = useMemo(
    () => organizationDnaModules.filter((item) => item.hasDocument).length,
    [organizationDnaModules],
  );
  const hasAnyOrganizationDna = orgDnaCompletedCount > 0;
  const organizationDnaReadyModules = useMemo(
    () => organizationDnaModules.filter((item) => item.hasDocument),
    [organizationDnaModules],
  );
  const annualStrategyReady = Boolean(value.organization.annualGoal.trim() && value.organization.annualStrategy.trim() && strategyYear);
  const orgQuarterPlansReady = orgQuarterPlans.every((plan) => plan.objective.trim());
  const departmentsWithQuarterPlan = useMemo(
    () => activeDepartments.filter((department) => department.quarterPlan.objective.trim()).length,
    [activeDepartments],
  );
  const departmentsNeedingQuarterPlan = useMemo(
    () => activeDepartments.filter((department) => !department.quarterPlan.objective.trim()),
    [activeDepartments],
  );
  const departmentsWithContext = useMemo(
    () => activeDepartments.filter((department) => department.businessContext.trim() || department.teamContext.trim()).length,
    [activeDepartments],
  );
  const departmentsMissingContextCount = useMemo(
    () => activeDepartments.filter((department) => !(department.businessContext.trim() || department.teamContext.trim())).length,
    [activeDepartments],
  );
  const departmentsMissingQuarterPlanCount = useMemo(
    () => activeDepartments.filter((department) => !department.quarterPlan.objective.trim()).length,
    [activeDepartments],
  );
  const departmentRelayRows = useMemo(
    () => activeDepartments.map((department) => {
      const hasLeader = Boolean(department.leaderUserId || department.leaderName?.trim());
      const hasContext = Boolean(department.businessContext.trim() || department.teamContext.trim());
      const hasPlan = Boolean(department.quarterPlan.objective.trim());
      const missingItems = [
        !hasLeader ? '负责人' : '',
        !hasContext ? '部门背景' : '',
        !hasPlan ? '季度计划' : '',
      ].filter(Boolean);
      const statusLabel = !hasLeader
        ? '待指定负责人'
        : !hasContext
          ? '待补部门背景'
          : !hasPlan
            ? '待补季度计划'
            : '已承接季度计划';
      const toneClass = !hasLeader || !hasPlan
        ? 'bg-amber-100 text-amber-700'
        : hasContext
          ? 'bg-emerald-100 text-emerald-700'
          : 'bg-slate-100 text-slate-600';
      const nextActionLabel = !hasLeader
        ? '去指定负责人'
        : !hasContext
          ? '去补部门背景'
          : !hasPlan
            ? '去补季度计划'
            : '查看已承接内容';
      const nextStepId: SetupStepId = !hasLeader ? 'department' : 'planning';
      return {
        id: department.id,
        name: department.name,
        leaderLabel: department.leaderName?.trim() || (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '已指定负责人' : '待指定负责人'),
        hasLeader,
        hasContext,
        hasPlan,
        missingItems,
        statusLabel,
        toneClass,
        nextActionLabel,
        nextStepId,
      };
    }),
    [activeDepartments, employeeById],
  );
  const ceoRelayReady = orgDnaCompletedCount === organizationDnaModules.length && annualStrategyReady && orgQuarterPlansReady;
  const focusedQuarterPlan = useMemo(
    () => orgQuarterPlans.find((plan) => plan.quarter === selectedStrategyQuarter) || orgQuarterPlans[0] || createEmptyQuarterPlan(strategyYear, activeQuarter),
    [activeQuarter, orgQuarterPlans, selectedStrategyQuarter, strategyYear],
  );

  useEffect(() => {
    setDepartmentBuilderRows((prev) => {
      const persistedIds = new Set(activeDepartments.map((department) => department.id));
      const persistedRows = activeDepartments.map((department) => ({
        localId: department.id,
        departmentId: department.id,
        name: department.name,
        leaderUserId: department.leaderUserId || '',
        leaderName: department.leaderName?.trim() || (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '' : ''),
        isConfirmed: true,
      }));
      const draftRows = prev.filter((row) => !persistedIds.has(row.departmentId));
      return [...persistedRows, ...draftRows];
    });
  }, [activeDepartments, employeeById]);

  const departmentOptions = useMemo(
    () => activeDepartments.map((item) => ({ id: item.id, name: item.name, color: item.color })),
    [activeDepartments],
  );
  const persistedDepartmentIdSet = useMemo(() => new Set(activeDepartments.map((item) => item.id)), [activeDepartments]);

  const departmentsMissingLeader = activeDepartments.filter((item) => !(item.leaderUserId || item.leaderName?.trim()));
  const unmappedEmployees = assignableEmployees.filter((employee) => {
    const binding = bindingsByUserId.get(employee.id);
    return !(binding?.departmentId && binding?.primaryRoleId);
  });
  const activeTaskRules = value.taskControlRules.filter((item) => item.active !== false);
  const activeProcessTemplates = value.roleProcessTemplates.filter((item) => item.active !== false);
  const memberRelayReady = assignableEmployees.length > 0 && activeProcessTemplates.length > 0;
  const activeFocusItems = value.focusItems.filter((item) => item.status !== 'done');
  const activeDepartmentPlans = value.departmentPlans.filter((item) => item.status !== 'closed');
  const weekPlans = activeDepartmentPlans.filter((item) => item.weekLabel === activeWeekLabel);
  const designedDepartmentRows = departmentBuilderRows.filter((row) => row.isConfirmed && row.name.trim());
  const editableDepartmentRows = departmentBuilderRows.filter((row) => !row.isConfirmed);

  const leaderName = value.organization.leaderUserId ? employeeById.get(value.organization.leaderUserId)?.fullName || '已设置负责人' : '待确认';
  const organizationLabel = value.organization.name.trim() || '当前组织';
  const ceoOptions = assignableEmployees.length > 0 ? assignableEmployees : activeEmployees;

  const steps = useMemo<SetupStep[]>(() => [
    {
      id: 'ceo',
      title: '确认 CEO / 组织管理员',
      description: '先确认顾源源或当前初始化负责人，让整个组织的任务、审批和知识上下文有唯一起点。',
      done: Boolean(value.organization.leaderUserId),
      tab: 'overview',
      stat: value.organization.leaderUserId ? `当前负责人：${leaderName}` : '待确认',
    },
    {
      id: 'department',
      title: '设计部门并指定负责人',
      description: '每保存一个部门和负责人，就立刻生成该部门的邀请码；全部确认后，再点完成进入下一步。',
      done: activeDepartments.length > 0 && departmentsMissingLeader.length === 0,
      tab: 'departments',
      stat: activeDepartments.length === 0
        ? '尚未创建部门'
        : departmentsMissingLeader.length > 0
          ? `${departmentsMissingLeader.length} 个待补负责人`
          : `${activeDepartments.length} 个部门已完成`,
    },
    {
      id: 'role',
      title: '建立岗位模板',
      description: '岗位模板会直接决定任务归属、上下级协同和权限边界，不再让系统靠猜。',
      done: activeRoles.length > 0,
      tab: 'departments',
      stat: activeRoles.length > 0 ? `${activeRoles.length} 个岗位模板` : '还没有岗位模板',
    },
    {
      id: 'people',
      title: '邀请成员加入并补岗位归属',
      description: '新公司先把部门邀请码发出去，成员注册时先锁定部门、自己补岗位信息，组织搭建以邀请码加入为主。',
      done: assignableEmployees.length > 0,
      tab: 'people',
      stat: assignableEmployees.length > 0 ? `${assignableEmployees.length} 人已加入` : '等待成员带邀请码加入',
    },
    {
      id: 'workflow',
      title: '补流程模板与任务权限',
      description: '流程模板、审批边界和任务控制规则会决定会议后怎么落任务、谁能改期、谁能分配。',
      done: activeProcessTemplates.length > 0 && activeTaskRules.length > 0,
      tab: 'rules',
      stat: `${activeProcessTemplates.length} 个流程模板 / ${activeTaskRules.length} 条规则`,
    },
    {
      id: 'planning',
      title: '上传年度战略并承接部门季度计划',
      description: 'CEO 先补组织 DNA 状态、年度目标和四季草稿，部门负责人再补部门业务/团队背景与季度目标，后续任务和成长判断才有真正的上游语境。',
      done: orgDnaCompletedCount === organizationDnaModules.length
        && annualStrategyReady
        && orgQuarterPlansReady
        && (activeDepartments.length === 0 || departmentsWithQuarterPlan === activeDepartments.length),
      tab: 'overview',
      stat: !annualStrategyReady
        ? '待补年度战略'
        : !orgQuarterPlansReady
          ? '待生成四季草稿'
          : activeDepartments.length > 0 && departmentsWithQuarterPlan < activeDepartments.length
            ? `${activeDepartments.length - departmentsWithQuarterPlan} 个部门待承接`
            : `${orgDnaCompletedCount}/${organizationDnaModules.length} 份 DNA · ${orgQuarterPlans.length} 季已就绪`,
    },
  ], [
    activeDepartments.length,
    activeProcessTemplates.length,
    activeRoles.length,
    activeTaskRules.length,
    assignableEmployees.length,
    departmentsMissingLeader.length,
    departmentsWithQuarterPlan,
    leaderName,
    annualStrategyReady,
    orgDnaCompletedCount,
    orgQuarterPlans.length,
    orgQuarterPlansReady,
    organizationDnaModules.length,
    value.organization.leaderUserId,
    value.organization.name,
  ]);

  const completedSteps = steps.filter((step) => step.done).length;
  const progressPercent = Math.round((completedSteps / steps.length) * 100);
  const nextStep = steps.find((step) => !step.done) || steps[steps.length - 1];
  const holdDepartmentStep = departmentStepLocked && nextStep.id !== 'department' && activeDepartments.length > 0 && departmentsMissingLeader.length === 0;
  const autoCurrentStep = holdDepartmentStep ? steps.find((step) => step.id === 'department') || nextStep : nextStep;
  const currentStep = selectedStepId ? steps.find((step) => step.id === selectedStepId) || autoCurrentStep : autoCurrentStep;

  useEffect(() => {
    if (nextStep.id === 'department') {
      setDepartmentStepLocked(true);
    }
  }, [nextStep.id]);

  useEffect(() => {
    if (selectedStepId && !steps.some((step) => step.id === selectedStepId)) {
      setSelectedStepId(null);
    }
  }, [selectedStepId, steps]);

  const generatedTasks = useMemo<GeneratedTask[]>(() => {
    const items: GeneratedTask[] = [];
    if (!value.organization.leaderUserId) {
      items.push({
        id: 'task_ceo',
        title: '先确认组织管理员',
        helper: '没有 CEO / 管理员，后续部门认领、权限边界和组织上下文都没有锚点。',
        ownerLabel: '顾源源',
        tab: 'overview',
      });
    }
    if (activeDepartments.length === 0) {
      items.push({
        id: 'task_first_department',
        title: '创建第一个部门',
        helper: '部门是成员、岗位、流程和计划的归属单位，先从一个核心部门开始。',
        ownerLabel: leaderName,
        tab: 'departments',
      });
    }
    departmentsMissingLeader.slice(0, 3).forEach((department) => {
      items.push({
        id: `task_department_lead_${department.id}`,
        title: `为「${department.name}」指定负责人`,
        helper: '部门负责人是该部门后续继续补岗位职责、业务介绍和流程规则的人。',
        ownerLabel: leaderName,
        tab: 'departments',
      });
    });
    if (activeRoles.length === 0) {
      items.push({
        id: 'task_roles',
        title: '建立首批岗位模板',
        helper: '没有岗位模板，任务权限、复盘归因和部门协作都只能停留在人名层。',
        ownerLabel: leaderName,
        tab: 'departments',
      });
    }
    if (activeDepartments.length > 0 && assignableEmployees.length === 0) {
      items.push({
        id: 'task_invite_members',
        title: '把部门邀请码发给负责人和成员',
        helper: '新公司第一次搭建时，不是先手工下拉绑定，而是先让大家带邀请码注册进入各自部门。',
        ownerLabel: leaderName,
        tab: 'people',
      });
    }
    if (activeProcessTemplates.length === 0 || activeTaskRules.length === 0) {
      items.push({
        id: 'task_workflow',
        title: '补流程模板与任务权限规则',
        helper: '把会议、任务创建和周会后的动作写成模板，系统才能稳定地自动推进。',
        ownerLabel: leaderName,
        tab: 'rules',
      });
    }
    if (orgDnaCompletedCount < organizationDnaModules.length) {
      items.push({
        id: 'task_org_dna',
        title: '补组织 DNA 资料',
        helper: '组织介绍、业务介绍、团队介绍和市场调研是后续战略分解与建议判断的背景母体。',
        ownerLabel: 'CEO / 组织管理员',
        section: 'org_dna',
      });
    }
    if (!annualStrategyReady) {
      items.push({
        id: 'task_annual_strategy',
        title: '补年度目标与年度战略',
        helper: '没有年度战略时，四季计划和部门承接都没有统一上游语境。',
        ownerLabel: 'CEO / 组织管理员',
        tab: 'overview',
      });
    }
    if (annualStrategyReady && !orgQuarterPlansReady) {
      items.push({
        id: 'task_org_quarters',
        title: '生成并校正四季草稿',
        helper: '先把年度战略拆成 Q1-Q4 草稿，再继续让各部门承接季度目标。',
        ownerLabel: 'CEO / 组织管理员',
        tab: 'overview',
      });
    }
    departmentsNeedingQuarterPlan.slice(0, 3).forEach((department) => {
      items.push({
        id: `task_department_plan_${department.id}`,
        title: `补「${department.name}」的季度计划`,
        helper: '部门负责人需要补业务/团队背景和季度目标，后续月度计划才有落点。',
        ownerLabel: department.leaderName?.trim() || '部门负责人',
        tab: 'overview',
      });
    });
    return items.slice(0, 8);
  }, [
    activeDepartments.length,
    activeProcessTemplates.length,
    activeRoles.length,
    activeTaskRules.length,
    assignableEmployees.length,
    annualStrategyReady,
    departmentsMissingLeader,
    departmentsNeedingQuarterPlan,
    leaderName,
    orgDnaCompletedCount,
    orgQuarterPlansReady,
    organizationDnaModules.length,
    value.organization.annualGoal,
    value.organization.annualStrategy,
    value.organization.leaderUserId,
    value.organization.name,
  ]);

  function syncStrategyContext(nextDraft: OrgModelSettings): OrgModelSettings {
    const normalizedYear = nextDraft.organization.annualStrategyYear.trim() || strategyYear;
    const normalizedQuarterPlans = ensureQuarterPlans(nextDraft.organization.quarterPlans, normalizedYear);
    const currentPlan = normalizedQuarterPlans.find((plan) => plan.quarter === activeQuarter);
    return {
      ...nextDraft,
      organization: {
        ...nextDraft.organization,
        annualStrategyYear: normalizedYear,
        quarterPlans: normalizedQuarterPlans,
        quarterlyFocus:
          currentPlan && (currentPlan.keyResults.length > 0 || currentPlan.keyActions.length > 0)
            ? [...currentPlan.keyResults, ...currentPlan.keyActions].slice(0, 5)
            : nextDraft.organization.quarterlyFocus,
      },
      departments: nextDraft.departments.map((department) => ({
        ...department,
        quarterPlan: {
          ...department.quarterPlan,
          year: department.quarterPlan.year || normalizedYear,
          quarter: department.quarterPlan.quarter || activeQuarter,
        },
        quarterlyFocus:
          department.quarterPlan.deliverables.length > 0 || department.quarterPlan.successMetrics.length > 0
            ? [...department.quarterPlan.deliverables, ...department.quarterPlan.successMetrics].slice(0, 5)
            : department.quarterlyFocus,
      })),
    };
  }

  async function commitDraft(nextDraft: OrgModelSettings) {
    const syncedDraft = syncStrategyContext(nextDraft);
    onChange(syncedDraft);
    await onSave(syncedDraft);
    setAdvancedTab(nextStep.tab);
  }

  function openTaskTab(tab: OrgModelTab) {
    setAdvancedTab(tab);
    setAdvancedOpen(true);
  }

  function handleOpenGeneratedTask(task: GeneratedTask) {
    if (task.section) {
      onOpenSection(task.section);
      return;
    }
    openTaskTab(task.tab || 'overview');
  }

  function handleSelectStep(step: SetupStep) {
    setSelectedStepId(step.id);
    openTaskTab(step.tab);
  }

  async function handleConfirmLeader() {
    const selectedLeaderId = ceoCandidateId || value.organization.leaderUserId || ceoOptions[0]?.id;
    if (!selectedLeaderId) return;
    const nextDraft: OrgModelSettings = {
      ...value,
      organization: {
        ...value.organization,
        name: organizationNameDraft.trim() || value.organization.name,
        leaderUserId: selectedLeaderId,
        managementUserIds: Array.from(new Set([...value.organization.managementUserIds, selectedLeaderId].filter(Boolean))),
      },
    };
    await commitDraft(nextDraft);
  }

  function updateDepartmentBuilderRow(localId: string, patch: Partial<DepartmentBuilderRow>) {
    setDepartmentBuilderRows((prev) => prev.map((row) => (row.localId === localId ? { ...row, ...patch } : row)));
  }

  function resolveLeaderUserIdByName(rawName: string) {
    const leaderName = rawName.trim();
    if (!leaderName) return '';
    return assignableEmployees.find((employee) => employee.fullName.trim() === leaderName)?.id || '';
  }

  function addDepartmentBuilderRow() {
    setDepartmentStepLocked(true);
    setDepartmentBuilderRows((prev) => [...prev, {
      localId: nextUiId('department_row'),
      departmentId: nextUiId('department'),
      name: '',
      leaderUserId: '',
      leaderName: '',
      isConfirmed: false,
    }]);
  }

  function handleEditDepartmentRow(localId: string) {
    setDepartmentStepLocked(true);
    setDepartmentBuilderRows((prev) => prev.map((row) => (
      row.localId === localId ? { ...row, isConfirmed: false } : row
    )));
  }

  function handleCancelDepartmentEdit(localId: string) {
    setDepartmentBuilderRows((prev) => prev.flatMap((row) => {
      if (row.localId !== localId) return [row];
      const persistedDepartment = departmentById.get(row.departmentId);
      if (!persistedDepartment) return [];
      return [{
        localId: persistedDepartment.id,
        departmentId: persistedDepartment.id,
        name: persistedDepartment.name,
        leaderUserId: persistedDepartment.leaderUserId || '',
        leaderName: persistedDepartment.leaderName?.trim() || (persistedDepartment.leaderUserId ? employeeById.get(persistedDepartment.leaderUserId)?.fullName || '' : ''),
        isConfirmed: true,
      }];
    }));
  }

  function removeDepartmentBuilderRow(localId: string) {
    setDepartmentBuilderRows((prev) => prev.filter((row) => row.localId !== localId));
  }

  async function handleSaveDepartmentRow(localId: string) {
    const targetRow = departmentBuilderRows.find((row) => row.localId === localId);
    if (!targetRow) return;

    const name = targetRow.name.trim();
    const leaderName = targetRow.leaderName.trim();
    const leaderUserId = targetRow.leaderUserId || resolveLeaderUserIdByName(leaderName);
    if (!name || !leaderName) return;

    const existingDepartment = departmentById.get(targetRow.departmentId);
    const nextDepartments = value.departments.map((department) => (
      department.id === targetRow.departmentId
        ? { ...department, name, leaderUserId: leaderUserId || null, leaderName }
        : department
    ));

    if (!existingDepartment) {
      nextDepartments.push({
        id: targetRow.departmentId,
        name,
        color: DEPARTMENT_COLORS[nextDepartments.length % DEPARTMENT_COLORS.length],
        leaderUserId: leaderUserId || null,
        leaderName,
        parentDepartmentId: null,
        mission: '',
        businessContext: '',
        teamContext: '',
        quarterPlan: createEmptyDepartmentQuarterPlan(strategyYear, activeQuarter),
        quarterlyFocus: [],
        collaborationDepartmentIds: [],
        active: true,
        updatedAt: '',
      });
    }

    const nextBindings = [...value.bindings];

    if (existingDepartment?.leaderUserId && existingDepartment.leaderUserId !== leaderUserId) {
      const previousLeaderIndex = nextBindings.findIndex((item) => item.userId === existingDepartment.leaderUserId);
      if (previousLeaderIndex >= 0 && nextBindings[previousLeaderIndex].departmentId === targetRow.departmentId) {
        nextBindings[previousLeaderIndex] = {
          ...nextBindings[previousLeaderIndex],
          isManager: false,
        };
      }
    }

    if (leaderUserId) {
      const existingBinding = bindingsByUserId.get(leaderUserId);
      const nextBinding: OrgEmployeeBindingSettings = existingBinding
        ? { ...existingBinding, departmentId: targetRow.departmentId, isManager: true }
        : { ...emptyBindingForUser(leaderUserId, targetRow.departmentId), isManager: true };
      const bindingIndex = nextBindings.findIndex((item) => item.userId === leaderUserId);
      if (bindingIndex >= 0) {
        nextBindings[bindingIndex] = nextBinding;
      } else {
        nextBindings.push(nextBinding);
      }
    }

    setDepartmentBuilderRows((prev) => prev.map((row) => (
      row.localId === localId
        ? { ...row, name, leaderName, leaderUserId, isConfirmed: true }
        : row
    )));

    await commitDraft({
      ...value,
      departments: nextDepartments,
      bindings: nextBindings,
    });
  }

  async function handleDeleteDepartmentRow(localId: string) {
    const targetRow = departmentBuilderRows.find((row) => row.localId === localId);
    if (!targetRow) return;

    if (!persistedDepartmentIdSet.has(targetRow.departmentId)) {
      removeDepartmentBuilderRow(localId);
      return;
    }

    const confirmed = window.confirm(`确认删除部门「${targetRow.name || departmentById.get(targetRow.departmentId)?.name || '未命名部门'}」吗？这会一起移除该部门下的岗位模板、流程模板和部门计划。`);
    if (!confirmed) return;

    const removedRoleIds = new Set(value.roles.filter((role) => role.departmentId === targetRow.departmentId).map((role) => role.id));

    const nextDepartments = value.departments
      .filter((department) => department.id !== targetRow.departmentId)
      .map((department) => ({
        ...department,
        parentDepartmentId: department.parentDepartmentId === targetRow.departmentId ? null : department.parentDepartmentId,
        collaborationDepartmentIds: department.collaborationDepartmentIds.filter((departmentId) => departmentId !== targetRow.departmentId),
      }));

    const nextRoles = value.roles
      .filter((role) => role.departmentId !== targetRow.departmentId)
      .map((role) => ({
        ...role,
        managerRoleId: role.managerRoleId && removedRoleIds.has(role.managerRoleId) ? null : role.managerRoleId,
        collaborationRoleIds: role.collaborationRoleIds.filter((roleId) => !removedRoleIds.has(roleId)),
      }));

    const nextBindings = value.bindings.map((binding) => {
      const shouldClearDepartment = binding.departmentId === targetRow.departmentId;
      const shouldClearRole = Boolean(binding.primaryRoleId && removedRoleIds.has(binding.primaryRoleId));
      return shouldClearDepartment || shouldClearRole
        ? {
            ...binding,
            departmentId: shouldClearDepartment ? null : binding.departmentId,
            primaryRoleId: shouldClearRole ? null : binding.primaryRoleId,
            managerUserId: shouldClearDepartment ? null : binding.managerUserId,
            isManager: shouldClearDepartment ? false : binding.isManager,
          }
        : binding;
    });

    await commitDraft({
      ...value,
      departments: nextDepartments,
      roles: nextRoles,
      bindings: nextBindings,
      taskControlRules: value.taskControlRules.filter((rule) => rule.departmentId !== targetRow.departmentId && !(rule.roleTemplateId && removedRoleIds.has(rule.roleTemplateId))),
      roleProcessTemplates: value.roleProcessTemplates.filter((template) => !(template.roleTemplateId && removedRoleIds.has(template.roleTemplateId))),
      departmentPlans: value.departmentPlans.filter((plan) => plan.departmentId !== targetRow.departmentId),
    });
  }

  function handleCompleteDepartmentStep() {
    setDepartmentStepLocked(false);
  }

  function updateOrganizationStrategy(patch: Partial<OrgModelSettings['organization']>) {
    onChange(syncStrategyContext({
      ...value,
      organization: {
        ...value.organization,
        ...patch,
      },
    }));
  }

  function updateQuarterPlan(quarter: OrgQuarterKey, patch: Partial<OrgQuarterPlanSettings>) {
    const nextPlans = orgQuarterPlans.map((plan) => (
      plan.quarter === quarter
        ? {
            ...plan,
            ...patch,
            quarter,
            updatedAt: new Date().toISOString(),
          }
        : plan
    ));
    updateOrganizationStrategy({ quarterPlans: nextPlans });
  }

  function handleGenerateQuarterDrafts() {
    const drafts = buildQuarterDrafts(strategyYear, value.organization.annualGoal, value.organization.annualStrategy);
    updateOrganizationStrategy({
      quarterPlans: orgQuarterPlans.map((plan, index) => mergeQuarterPlanByMode(plan, drafts[index] || createEmptyQuarterPlan(strategyYear, plan.quarter), quarterDraftApplyMode)),
    });
  }

  function handleGenerateSingleQuarterDraft(quarter: OrgQuarterKey) {
    const drafts = buildQuarterDrafts(strategyYear, value.organization.annualGoal, value.organization.annualStrategy);
    const nextCandidate = drafts.find((plan) => plan.quarter === quarter);
    if (!nextCandidate) return;
    updateOrganizationStrategy({
      quarterPlans: orgQuarterPlans.map((plan) => (
        plan.quarter === quarter ? mergeQuarterPlanByMode(plan, nextCandidate, quarterDraftApplyMode) : plan
      )),
    });
  }

  function handleGenerateAnnualStrategyCandidate() {
    const nextCandidate = buildAnnualStrategyCandidate(value.organization.name, organizationDnaModules, value.organization.annualGoal);
    updateOrganizationStrategy({
      annualGoal: mergeTextByMode(value.organization.annualGoal, nextCandidate.annualGoal, annualDraftApplyMode),
      annualStrategy: mergeTextByMode(value.organization.annualStrategy, nextCandidate.annualStrategy, annualDraftApplyMode),
    });
  }

  function handleGenerateDepartmentCandidate(departmentId: string) {
    const target = value.departments.find((department) => department.id === departmentId);
    if (!target) return;
    const nextDraft = buildDepartmentDraft(target, value.organization.name, focusedQuarterPlan);
    updateDepartmentStrategy(departmentId, {
      businessContext: mergeTextByMode(target.businessContext, nextDraft.businessContext, departmentDraftApplyMode),
      teamContext: mergeTextByMode(target.teamContext, nextDraft.teamContext, departmentDraftApplyMode),
      updatedAt: departmentDraftApplyMode === 'overwrite' ? '' : target.updatedAt,
      quarterPlan: {
        ...target.quarterPlan,
        year: mergeTextByMode(target.quarterPlan.year, nextDraft.quarterPlan.year, departmentDraftApplyMode),
        quarter: target.quarterPlan.quarter || nextDraft.quarterPlan.quarter,
        objective: mergeTextByMode(target.quarterPlan.objective, nextDraft.quarterPlan.objective, departmentDraftApplyMode),
        deliverables: mergeListByMode(target.quarterPlan.deliverables, nextDraft.quarterPlan.deliverables, departmentDraftApplyMode),
        successMetrics: mergeListByMode(target.quarterPlan.successMetrics, nextDraft.quarterPlan.successMetrics, departmentDraftApplyMode),
        majorRisks: mergeListByMode(target.quarterPlan.majorRisks, nextDraft.quarterPlan.majorRisks, departmentDraftApplyMode),
        updatedAt: departmentDraftApplyMode === 'overwrite' ? '' : target.quarterPlan.updatedAt,
      },
    }, 'candidate');
  }

  function handleGenerateAllDepartmentCandidates() {
    onChange(syncStrategyContext({
      ...value,
      departments: value.departments.map((department) => ({
        ...department,
        ...(() => {
          const nextDraft = buildDepartmentDraft(department, value.organization.name, focusedQuarterPlan);
          return {
            businessContext: mergeTextByMode(department.businessContext, nextDraft.businessContext, departmentDraftApplyMode),
            teamContext: mergeTextByMode(department.teamContext, nextDraft.teamContext, departmentDraftApplyMode),
            updatedAt: departmentDraftApplyMode === 'overwrite' ? '' : department.updatedAt,
            quarterPlan: {
              ...department.quarterPlan,
              year: mergeTextByMode(department.quarterPlan.year, nextDraft.quarterPlan.year, departmentDraftApplyMode),
              quarter: department.quarterPlan.quarter || nextDraft.quarterPlan.quarter,
              objective: mergeTextByMode(department.quarterPlan.objective, nextDraft.quarterPlan.objective, departmentDraftApplyMode),
              deliverables: mergeListByMode(department.quarterPlan.deliverables, nextDraft.quarterPlan.deliverables, departmentDraftApplyMode),
              successMetrics: mergeListByMode(department.quarterPlan.successMetrics, nextDraft.quarterPlan.successMetrics, departmentDraftApplyMode),
              majorRisks: mergeListByMode(department.quarterPlan.majorRisks, nextDraft.quarterPlan.majorRisks, departmentDraftApplyMode),
              updatedAt: departmentDraftApplyMode === 'overwrite' ? '' : department.quarterPlan.updatedAt,
            },
          };
        })(),
      })),
    }));
  }

  function updateDepartmentStrategy(
    departmentId: string,
    patch: Partial<OrgModelSettings['departments'][number]>,
    source: 'manual' | 'candidate' = 'manual',
  ) {
    const manualUpdatedAt = source === 'manual' ? new Date().toISOString() : undefined;
    onChange(syncStrategyContext({
      ...value,
      departments: value.departments.map((department) => (
        department.id === departmentId
          ? {
              ...department,
              ...(manualUpdatedAt ? { updatedAt: manualUpdatedAt } : {}),
              ...patch,
            }
          : department
      )),
    }));
  }

  function updateDepartmentQuarterPlan(
    departmentId: string,
    patch: Partial<OrgModelSettings['departments'][number]['quarterPlan']>,
    source: 'manual' | 'candidate' = 'manual',
  ) {
    const currentQuarterPlan = value.departments.find((department) => department.id === departmentId)?.quarterPlan
      || createEmptyDepartmentQuarterPlan(strategyYear, activeQuarter);
    updateDepartmentStrategy(departmentId, {
      quarterPlan: {
        ...currentQuarterPlan,
        ...patch,
        ...(source === 'manual' ? { updatedAt: new Date().toISOString() } : {}),
      },
    }, source);
  }

  async function handleSaveStrategyStep() {
    await commitDraft(value);
  }

  async function handleCopyDepartmentInvite(departmentId: string, departmentName?: string) {
    const inviteCode = buildDepartmentInviteCode(departmentId);
    const resolvedDepartmentName = departmentName?.trim()
      || activeDepartments.find((department) => department.id === departmentId)?.name
      || departmentBuilderRows.find((row) => row.departmentId === departmentId)?.name
      || '部门';
    try {
      await navigator.clipboard.writeText(buildDepartmentInviteShareText(resolvedDepartmentName, inviteCode));
      setCopiedInviteDepartmentId(departmentId);
      window.setTimeout(() => setCopiedInviteDepartmentId((current) => (current === departmentId ? '' : current)), 1600);
    } catch {
      setCopiedInviteDepartmentId('');
    }
  }

  async function handleCreateRole() {
    const roleName = newRoleName.trim();
    const departmentId = newRoleDepartmentId || null;
    if (!roleName || !departmentId) return;
    const nextDraft: OrgModelSettings = {
      ...value,
      roles: [
        ...value.roles,
        {
          id: nextUiId('role'),
          departmentId,
          name: roleName,
          level: newRoleLevel,
          managerRoleId: null,
          isManager: newRoleLevel === 'organization_lead' || newRoleLevel === 'department_lead' || newRoleLevel === 'supervisor',
          goal: '',
          responsibilities: [],
          shouldAvoid: [],
          collaborationRoleIds: [],
          taskEditScope: newRoleLevel === 'employee' ? 'self' : 'department',
          canApproveTasks: newRoleLevel !== 'employee',
          canReassignTasks: newRoleLevel === 'department_lead' || newRoleLevel === 'organization_lead',
          canChangeDeadline: newRoleLevel !== 'employee',
          sortOrder: value.roles.length + 1,
          active: true,
          updatedAt: '',
        },
      ],
    };
    setNewRoleName('');
    await commitDraft(nextDraft);
  }

  async function handleCreateWorkflow() {
    const roleId = workflowRoleId || activeRoles[0]?.id;
    const templateName = workflowName.trim();
    if (!roleId || !templateName) return;
    const role = roleById.get(roleId);
    const needsRule = activeTaskRules.length === 0;
    const nextDraft: OrgModelSettings = {
      ...value,
      roleProcessTemplates: [
        ...value.roleProcessTemplates,
        {
          id: nextUiId('workflow'),
          roleTemplateId: roleId,
          name: templateName,
          triggerType: workflowTrigger,
          triggerCondition: '',
          keySteps: [],
          collaborationStep: '',
          approvalStep: '',
          outputArtifact: '',
          commonBlockers: [],
          active: true,
          updatedAt: '',
        },
      ],
      taskControlRules: needsRule
        ? [
            ...value.taskControlRules,
            {
              id: nextUiId('rule'),
              name: `${role?.name || '组织'}任务控制规则`,
              controlLevel: (role?.level === 'organization_lead' ? 'organization_control' : 'department_control') as OrgTaskControlLevel,
              departmentId: role?.departmentId || null,
              roleTemplateId: roleId,
              contentEditableBy: 'manager',
              deadlineEditableBy: 'manager',
              ownerEditableBy: 'department_lead',
              cancellableBy: 'department_lead',
              requireCollabConfirmation: true,
              defaultApproverUserId: null,
              active: true,
              updatedAt: '',
            },
          ]
        : value.taskControlRules,
    };
    setWorkflowName('');
    await commitDraft(nextDraft);
  }

  async function handleCreateFocusAndPlan() {
    const title = focusTitle.trim();
    const departmentId = focusDepartmentId || activeDepartments[0]?.id || null;
    if (!title) return;
    const focusId = nextUiId('focus');
    const existingPlan = value.departmentPlans.find((plan) => plan.departmentId === departmentId && plan.weekLabel === activeWeekLabel);
    const nextPlans: OrgModelSettings['departmentPlans'] = existingPlan
      ? value.departmentPlans.map((plan) => (
          plan.id === existingPlan.id
            ? {
                ...plan,
                summary: plan.summary || title,
                items: [
                  ...plan.items,
                  {
                    id: nextUiId('plan_item'),
                    focusItemId: focusId,
                    title,
                    statement: '',
                    ownerUserId: focusOwnerId || null,
                    status: 'active' as const,
                    expectedOutput: '',
                    sortOrder: plan.items.length + 1,
                    updatedAt: '',
                  },
                ],
              }
            : plan
        ))
      : [
          ...value.departmentPlans,
          {
            id: nextUiId('plan'),
            departmentId,
            weekLabel: activeWeekLabel,
            ownerUserId: focusOwnerId || null,
            summary: title,
            majorRisks: [],
            dependencies: [],
            status: 'active' as const,
            items: [
              {
                id: nextUiId('plan_item'),
                focusItemId: focusId,
                title,
                statement: '',
                ownerUserId: focusOwnerId || null,
                status: 'active' as const,
                expectedOutput: '',
                sortOrder: 1,
                updatedAt: '',
              },
            ],
            updatedAt: '',
          },
        ];
    const nextDraft: OrgModelSettings = {
      ...value,
      focusItems: [
        ...value.focusItems,
        {
          id: focusId,
          periodKey: activeWeekLabel,
          title,
          statement: '',
          ownerUserId: focusOwnerId || null,
          priority: 'high' as const,
          status: 'active' as const,
          evidenceKeywords: [],
          updatedAt: '',
        },
      ],
      departmentPlans: nextPlans,
    };
    setFocusTitle('');
    await commitDraft(nextDraft);
  }

  const primaryRoleValue = newRoleDepartmentId || '';
  const workflowRoleValue = workflowRoleId || activeRoles[0]?.id || '';
  const focusDepartmentValue = focusDepartmentId || activeDepartments[0]?.id || '';

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-[#dbe5ff] bg-[linear-gradient(135deg,#f8fbff_0%,#f3f7ff_50%,#f9fafb_100%)] p-6 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
              <Sparkles size={12} />
              组织搭建中心
            </div>
            <h2 className="mt-4 text-[22px] font-bold tracking-tight text-gray-900">把组织骨架、任务语义、周计划和学习沉淀收口到一页</h2>
            <p className="mt-3 max-w-2xl text-[13px] leading-7 text-gray-600">
              这不是一组孤立设置，而是整个软件的组织底盘。顾源源先起盘，部门负责人再接力补部门、岗位、流程和计划，缺失项会直接变成待补事项。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 xl:w-[340px]">
            {[
              ['完成度', `${progressPercent}%`],
              ['已完成步骤', `${completedSteps}/${steps.length}`],
              ['组织 DNA', `${orgDnaCompletedCount}/${organizationDnaModules.length}`],
              ['部门季度计划', `${departmentsWithQuarterPlan}/${activeDepartments.length || 0}`],
            ].map(([label, valueLabel]) => (
              <div key={label} className="rounded-[24px] border border-white/80 bg-white/90 px-4 py-3 shadow-sm">
                <p className="text-[11px] font-bold text-gray-500">{label}</p>
                <p className="mt-2 text-[20px] font-bold text-gray-900">{valueLabel}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.15fr)_360px] gap-6">
        <div className="rounded-3xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="mb-6 rounded-[28px] border border-gray-100 bg-gray-50/70 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#5B7BFE]">角色接力看板</p>
                <h3 className="mt-2 text-[18px] font-bold text-gray-900">谁来上传什么，现在卡在哪一层</h3>
                <p className="mt-2 text-[12px] leading-6 text-gray-500">
                  CEO 负责组织级母体资料和年度战略，部门负责人承接部门背景与季度计划，普通成员后续在任务与日历里补流程和经验。
                </p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
              <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <div className="rounded-2xl bg-blue-50 p-2 text-[#5B7BFE]">
                    <ShieldCheck size={16} />
                  </div>
                  <div>
                    <p className="text-[13px] font-bold text-gray-900">CEO / 组织管理员</p>
                    <p className="mt-1 text-[11px] text-gray-500">低频但根本：组织 DNA、年度战略、四季计划</p>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#5B7BFE]">
                    战略年 {strategyYear}
                  </span>
                  <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[10px] font-bold text-gray-600">
                    系统当前季度 {activeQuarter}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">DNA</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{orgDnaCompletedCount}/{organizationDnaModules.length}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">年度战略</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{annualStrategyReady ? '已补' : '待补'}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">四季草稿</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{orgQuarterPlansReady ? '已成稿' : '待校正'}</p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {ORG_QUARTER_OPTIONS.map((quarter) => {
                    const isActive = selectedStrategyQuarter === quarter;
                    const plan = orgQuarterPlans.find((item) => item.quarter === quarter);
                    const hasPlan = Boolean(plan?.objective.trim());
                    return (
                      <button
                        key={quarter}
                        type="button"
                        onClick={() => setSelectedStrategyQuarter(quarter)}
                        className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${isActive ? 'bg-[#5B7BFE] text-white' : hasPlan ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-white text-gray-500 border border-gray-200'}`}
                      >
                        {quarter}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-4 rounded-2xl bg-gray-50 px-3 py-3 text-[11px] text-gray-600">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-bold text-gray-900">{focusedQuarterPlan.theme || `${selectedStrategyQuarter} 季度主线`}</span>
                    <span className={`rounded-full px-2 py-0.5 ${focusedQuarterPlan.objective.trim() ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                      {focusedQuarterPlan.objective.trim() ? '已成稿' : '待补'}
                    </span>
                  </div>
                  <p className="mt-2 leading-6">{focusedQuarterPlan.objective.trim() || '当前季度目标还没写，建议先补目标，再继续让部门负责人承接。'}</p>
                  <p className="mt-2 text-[10px] text-gray-500">
                    关键结果 {focusedQuarterPlan.keyResults.length} 条 · 关键动作 {focusedQuarterPlan.keyActions.length} 条 · 风险 {focusedQuarterPlan.majorRisks.length} 条
                  </p>
                </div>
                <div className="mt-3 rounded-2xl border border-dashed border-blue-100 bg-blue-50/60 px-3 py-3 text-[11px] leading-6 text-gray-600">
                  {selectedStrategyQuarter === activeQuarter
                    ? '当前正在看的就是系统当前季度。建议先把这一季目标补完整，再让部门负责人承接到部门季度计划。'
                    : `你当前查看的是 ${selectedStrategyQuarter}，但系统当前季度是 ${activeQuarter}。若要先收口当季执行，优先补 ${activeQuarter}。`}
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${ceoRelayReady ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {ceoRelayReady ? 'CEO 侧已就绪' : 'CEO 侧仍有缺口'}
                  </span>
                  {!ceoRelayReady && (
                    <button
                      type="button"
                      onClick={() => handleSelectStep(steps.find((step) => step.id === 'planning') || currentStep)}
                      className="text-[11px] font-bold text-[#5B7BFE]"
                    >
                      去补齐
                    </button>
                  )}
                </div>
              </div>

              <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <div className="rounded-2xl bg-emerald-50 p-2 text-emerald-600">
                    <Building2 size={16} />
                  </div>
                  <div>
                    <p className="text-[13px] font-bold text-gray-900">部门负责人</p>
                    <p className="mt-1 text-[11px] text-gray-500">承接部门背景、团队信息和部门季度计划</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">已设负责人</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{activeDepartments.length - departmentsMissingLeader.length}/{activeDepartments.length || 0}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">已补背景</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{departmentsWithContext}/{activeDepartments.length || 0}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">已补季度计划</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{departmentsWithQuarterPlan}/{activeDepartments.length || 0}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-2xl border border-dashed border-emerald-100 bg-emerald-50/60 px-3 py-3 text-[11px] leading-6 text-gray-600">
                  负责人缺口 {departmentsMissingLeader.length} 个 · 背景待补 {departmentsMissingContextCount} 个 · 季度计划待补 {departmentsMissingQuarterPlanCount} 个。
                  这里优先帮你看清哪个部门还没接住公司战略。
                </div>
                <div className="mt-4 space-y-2">
                  {departmentRelayRows.length === 0 && (
                    <div className="rounded-2xl bg-gray-50 px-3 py-4 text-[11px] leading-6 text-gray-500">
                      还没有任何部门。先由 CEO 完成部门设计和负责人指定，部门负责人接力区才会出现。
                    </div>
                  )}
                  {departmentRelayRows.slice(0, 4).map((row) => (
                    <div key={row.id} className="rounded-2xl bg-gray-50 px-3 py-3 text-[11px] text-gray-600">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-bold text-gray-900">{row.name}</p>
                          <p className="mt-1 text-[10px] text-gray-500">{row.leaderLabel}</p>
                        </div>
                        <span className={`rounded-full px-2 py-0.5 ${row.toneClass}`}>
                          {row.statusLabel}
                        </span>
                      </div>
                      <p className="mt-2 leading-6">
                        {row.missingItems.length > 0 ? `当前还缺：${row.missingItems.join('、')}` : '部门负责人、背景资料和季度计划都已经承接到位。'}
                      </p>
                      <div className="mt-3 flex items-center justify-between gap-3">
                        <span className="text-[10px] text-gray-400">
                          {row.hasPlan ? '已接住季度目标，可继续细化执行。' : '建议先补齐上游语境，再进入月度执行。'}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleSelectStep(steps.find((step) => step.id === row.nextStepId) || currentStep)}
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-[#5B7BFE]"
                        >
                          {row.nextActionLabel}
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {departmentRelayRows.length > 4 && (
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() => handleSelectStep(steps.find((step) => step.id === 'planning') || currentStep)}
                      className="text-[11px] font-bold text-[#5B7BFE]"
                    >
                      查看全部部门承接状态
                    </button>
                  </div>
                )}
              </div>

              <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <div className="rounded-2xl bg-violet-50 p-2 text-violet-600">
                    <Users size={16} />
                  </div>
                  <div>
                    <p className="text-[13px] font-bold text-gray-900">普通成员</p>
                    <p className="mt-1 text-[11px] text-gray-500">通过邀请码加入，后续在任务与日历里高频补流程与经验</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">已加入成员</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{assignableEmployees.length}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">岗位模板</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{activeRoles.length}</p>
                  </div>
                  <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">流程模板</p>
                    <p className="mt-1 text-[14px] font-bold text-gray-900">{activeProcessTemplates.length}</p>
                  </div>
                </div>
                <div className="mt-4 rounded-2xl bg-gray-50 px-3 py-3 text-[11px] leading-6 text-gray-600">
                  当前阶段成员侧先完成加入和岗位归属。流程沉淀、模板补录、经验补录会在第二阶段进入任务与日历的浅入口，不会继续压在设置深层。
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${memberRelayReady ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {memberRelayReady ? '成员接力基础已具备' : '成员接力仍待铺底'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#5B7BFE]">当前唯一主任务</p>
              <h3 className="mt-2 text-[20px] font-bold text-gray-900">{currentStep.title}</h3>
              <p className="mt-2 text-[13px] leading-7 text-gray-600">{currentStep.description}</p>
            </div>
            <div className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#5B7BFE]">
              {currentStep.stat}
            </div>
          </div>

          <div className="mt-6 rounded-[28px] border border-blue-100 bg-blue-50/50 p-5">
            {currentStep.id === 'ceo' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">组织管理员</span>
                    <select
                      value={ceoCandidateId || value.organization.leaderUserId || ceoOptions[0]?.id || ''}
                      onChange={(event) => setCeoCandidateId(event.target.value)}
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">请选择组织管理员</option>
                      {ceoOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">组织名称</span>
                    <input
                      value={organizationNameDraft}
                      onChange={(event) => setOrganizationNameDraft(event.target.value)}
                      placeholder="例如：益语智库"
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    />
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() => void handleConfirmLeader()}
                  disabled={!canEdit || isSaving || !(ceoCandidateId || value.organization.leaderUserId || ceoOptions[0]?.id)}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  确认组织管理员
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {currentStep.id === 'department' && (
              <div className="space-y-4">
                <div className="rounded-[28px] border border-blue-100 bg-[#F8FBFF] px-5 py-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[15px] font-bold text-gray-900">已设计部门</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">每保存一个部门和负责人，就立即生成该部门邀请码。全部确认后，再点右下角完成进入下一步。</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
                      {activeDepartments.length > 0 ? `${activeDepartments.length} 个部门` : '尚未创建部门'}
                    </span>
                  </div>

                  <div className="mt-4 space-y-3">
                    {designedDepartmentRows.length > 0 ? designedDepartmentRows.map((row) => (
                      <div key={row.localId} className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-[14px] font-bold text-gray-900">{row.name}</p>
                            <p className="mt-1 text-[12px] text-gray-500">负责人：{row.leaderName}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleEditDepartmentRow(row.localId)}
                              disabled={!canEdit || isSaving}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDeleteDepartmentRow(row.localId)}
                              disabled={!canEdit || isSaving}
                              className="rounded-2xl border border-rose-200 bg-white px-3 py-2 text-[11px] font-bold text-rose-500 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              删除
                            </button>
                          </div>
                        </div>
                        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                          <div className="rounded-2xl bg-gray-50 px-3 py-3 text-[12px] font-mono text-gray-700">
                            {buildDepartmentInviteCode(row.departmentId)}
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleCopyDepartmentInvite(row.departmentId, row.name)}
                            className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm"
                          >
                            {copiedInviteDepartmentId === row.departmentId ? '已复制' : '复制邀请码'}
                          </button>
                        </div>
                      </div>
                    )) : (
                      <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-4 py-6 text-center">
                        <p className="text-[13px] font-bold text-gray-900">还没有部门</p>
                        <p className="mt-2 text-[12px] leading-6 text-gray-500">先新增一个部门并指定负责人，邀请码会在保存后立即出现。</p>
                      </div>
                    )}
                  </div>

                  <div className="mt-5 border-t border-blue-100/80 pt-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[13px] font-bold text-gray-900">新增或编辑部门</p>
                        <p className="mt-1 text-[11px] text-gray-500">部门负责人现在可以先填名字；对方以后带邀请码加入后，会再和真实账号接上。</p>
                      </div>
                      <button
                        type="button"
                        onClick={addDepartmentBuilderRow}
                        disabled={!canEdit || isSaving}
                        className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        新增一个部门
                      </button>
                    </div>

                    <div className="mt-4 space-y-3">
                      {editableDepartmentRows.length > 0 ? editableDepartmentRows.map((row) => (
                        <div key={row.localId} className="rounded-[24px] border border-blue-100 bg-white px-4 py-4">
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
                            <label className="space-y-2">
                              <span className="text-[12px] font-bold text-gray-700">部门名称</span>
                              <input
                                value={row.name}
                                onChange={(event) => updateDepartmentBuilderRow(row.localId, { name: event.target.value, isConfirmed: false })}
                                placeholder="例如：战略咨询部"
                                className="w-full rounded-2xl border border-blue-100 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                                disabled={!canEdit}
                              />
                            </label>
                            <label className="space-y-2">
                              <span className="text-[12px] font-bold text-gray-700">部门负责人</span>
                              <input
                                value={row.leaderName}
                                onChange={(event) => updateDepartmentBuilderRow(row.localId, { leaderName: event.target.value, leaderUserId: '', isConfirmed: false })}
                                placeholder="例如：庆华"
                                className="w-full rounded-2xl border border-blue-100 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                                disabled={!canEdit}
                              />
                            </label>
                            <div className="flex items-center gap-2 md:justify-end">
                              <button
                                type="button"
                                onClick={() => (persistedDepartmentIdSet.has(row.departmentId) ? handleCancelDepartmentEdit(row.localId) : removeDepartmentBuilderRow(row.localId))}
                                disabled={!canEdit || isSaving}
                                className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[12px] font-bold text-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {persistedDepartmentIdSet.has(row.departmentId) ? '取消' : '删除'}
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleSaveDepartmentRow(row.localId)}
                                disabled={!canEdit || isSaving || !row.name.trim() || !row.leaderName.trim()}
                                className="rounded-2xl bg-[#5B7BFE] px-4 py-3 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                保存
                              </button>
                            </div>
                          </div>
                        </div>
                      )) : (
                        <div className="rounded-[24px] border border-dashed border-gray-200 bg-white px-4 py-6 text-center">
                          <p className="text-[13px] font-bold text-gray-900">当前没有待编辑的部门</p>
                          <p className="mt-2 text-[12px] leading-6 text-gray-500">如果要继续新增部门，点击上面的“新增一个部门”；如果要改已有部门，直接点对应卡片右上角的编辑。</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-5 flex justify-end">
                    <button
                      type="button"
                      onClick={handleCompleteDepartmentStep}
                      disabled={!canEdit || isSaving || activeDepartments.length === 0 || editableDepartmentRows.length > 0 || departmentsMissingLeader.length > 0}
                      className="rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      完成
                    </button>
                  </div>
                </div>
              </div>
            )}

            {currentStep.id === 'role' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">归属部门</span>
                    <select
                      value={primaryRoleValue}
                      onChange={(event) => setNewRoleDepartmentId(event.target.value)}
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">请选择部门</option>
                      {departmentOptions.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">岗位名称</span>
                    <input
                      value={newRoleName}
                      onChange={(event) => setNewRoleName(event.target.value)}
                      placeholder="例如：部门负责人"
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">岗位层级</span>
                    <select
                      value={newRoleLevel}
                      onChange={(event) => setNewRoleLevel(event.target.value as OrgRoleLevel)}
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {ROLE_LEVEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() => void handleCreateRole()}
                  disabled={!canEdit || isSaving || !primaryRoleValue || !newRoleName.trim()}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  添加岗位模板
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {currentStep.id === 'people' && (
              <div className="space-y-4">
                {activeDepartments.length > 0 && (
                  <div className="rounded-[24px] border border-blue-100 bg-blue-50/70 px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-[13px] font-bold text-gray-900">已设计部门</p>
                        <p className="mt-1 text-[12px] text-gray-500">已经搭好的部门先折成一行，你可以一眼看清目前的组织骨架和负责人归属。</p>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">{activeDepartments.length} 个部门</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {activeDepartments.map((department) => (
                        <div key={department.id} className="flex flex-col gap-1 rounded-2xl border border-white/80 bg-white/90 px-4 py-3 text-[12px] text-gray-600 md:flex-row md:items-center md:justify-between">
                          <span className="font-bold text-gray-900">{department.name}</span>
                          <span>负责人：{department.leaderName?.trim() || (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '已指定' : '待指定负责人')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {assignableEmployees.length === 0 ? (
                  <div className="rounded-[24px] border border-amber-100 bg-amber-50/80 px-4 py-4">
                    <p className="text-[14px] font-bold text-gray-900">现在不是手工下拉绑定的时候</p>
                    <p className="mt-2 text-[12px] leading-6 text-gray-600">
                      新公司第一次搭建时，先把下面的部门邀请码发给负责人或成员。对方注册时第 1 步填邀请码锁定部门，第 2 步自己补岗位信息；等他们加入后，你再回来补直属上级或做少量人工校正。
                    </p>
                    <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
                      {activeDepartments.map((department) => (
                        <div key={department.id} className="rounded-[22px] border border-white/80 bg-white/90 px-4 py-4 shadow-sm">
                          <div className="min-w-0">
                            <p className="text-[13px] font-bold text-gray-900">{organizationLabel} · {department.name}</p>
                            <p className="mt-1 text-[11px] text-gray-500">负责人：{department.leaderName?.trim() || (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '已指定' : '待指定')}</p>
                          </div>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <div className="rounded-2xl bg-gray-50 px-3 py-3 text-[12px] font-mono text-gray-700">
                              {buildDepartmentInviteCode(department.id)}
                            </div>
                            <button
                              type="button"
                              onClick={() => void handleCopyDepartmentInvite(department.id, department.name)}
                              className="shrink-0 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm"
                            >
                              {copiedInviteDepartmentId === department.id ? '已复制' : '复制'}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-emerald-100 bg-emerald-50/70 px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-[14px] font-bold text-gray-900">成员已经开始带邀请码加入</p>
                        <p className="mt-2 text-[12px] leading-6 text-gray-600">
                          成员注册时已经锁定部门并自填岗位信息，管理员现在只需要看哪些部门已经有人接入，必要时再回头校正。
                        </p>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-emerald-700 shadow-sm">
                        {assignableEmployees.length} 人已加入
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
                      {assignableEmployees.slice(0, 6).map((employee) => {
                        const binding = bindingsByUserId.get(employee.id);
                        const departmentName = binding?.departmentId
                          ? departmentById.get(binding.departmentId)?.name || employee.departmentName || '待锁定部门'
                          : employee.departmentName || '待锁定部门';
                        const roleName = binding?.primaryRoleId
                          ? roleById.get(binding.primaryRoleId)?.name || employee.jobTitle || '待补岗位'
                          : employee.jobTitle || '待补岗位';
                        return (
                          <div key={employee.id} className="rounded-[22px] border border-white/80 bg-white/90 px-4 py-4 shadow-sm">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-[13px] font-bold text-gray-900">{employee.fullName}</p>
                                <p className="mt-1 text-[11px] text-gray-500">{employee.email}</p>
                              </div>
                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
                                {employee.isDepartmentLead || binding?.isManager ? '负责人' : '成员'}
                              </span>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-gray-600">
                              <span className="rounded-full bg-gray-50 px-3 py-1.5">{departmentName}</span>
                              <span className="rounded-full bg-gray-50 px-3 py-1.5">{roleName}</span>
                              {employee.currentFocus ? (
                                <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[#4A63CF]">{employee.currentFocus}</span>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {currentStep.id === 'workflow' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">岗位</span>
                    <select
                      value={workflowRoleValue}
                      onChange={(event) => setWorkflowRoleId(event.target.value)}
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">请选择岗位</option>
                      {activeRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">流程名称</span>
                    <input
                      value={workflowName}
                      onChange={(event) => setWorkflowName(event.target.value)}
                      placeholder="例如：周会后任务推进"
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">触发时机</span>
                    <select
                      value={workflowTrigger}
                      onChange={(event) => setWorkflowTrigger(event.target.value as OrgWorkflowTriggerType)}
                      className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {WORKFLOW_TRIGGER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() => void handleCreateWorkflow()}
                  disabled={!canEdit || isSaving || !workflowRoleValue || !workflowName.trim()}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  建立流程模板
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {currentStep.id === 'planning' && (
              <div className="space-y-4">
                <div className="rounded-[24px] border border-[#dbe5ff] bg-[linear-gradient(135deg,#f7faff_0%,#eef4ff_52%,#f9fafb_100%)] px-4 py-4 shadow-sm">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="max-w-3xl">
                      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#5B7BFE]">组织启动母盘</p>
                      <h4 className="mt-2 text-[18px] font-bold text-gray-900">{strategyYear} 年组织战略与季度承接</h4>
                      <p className="mt-2 text-[12px] leading-6 text-gray-600">
                        先把组织 DNA、年度战略和四季草稿固定，再让部门负责人承接本季度目标。后续任务建议、成长判断和流程沉淀都会从这里读上游语境。
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">战略年 {strategyYear}</span>
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-gray-600 shadow-sm">当前季度 {activeQuarter}</span>
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-[11px] font-bold text-[#4A63CF]">当前聚焦 {selectedStrategyQuarter}</span>
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
                    <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 shadow-sm">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">组织 DNA</p>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <p className="text-[15px] font-bold text-gray-900">{orgDnaCompletedCount}/{organizationDnaModules.length}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${orgDnaCompletedCount === organizationDnaModules.length ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                          {orgDnaCompletedCount === organizationDnaModules.length ? '已就绪' : '待补'}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 shadow-sm">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">年度战略</p>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <p className="text-[15px] font-bold text-gray-900">{annualStrategyReady ? '已补' : '待补'}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${annualStrategyReady ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                          {annualStrategyReady ? '已就绪' : '待补'}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 shadow-sm">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">四季草稿</p>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <p className="text-[15px] font-bold text-gray-900">{orgQuarterPlansReady ? '已成稿' : '待校正'}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${orgQuarterPlansReady ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                          {orgQuarterPlansReady ? '已就绪' : '待补'}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 shadow-sm">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">部门承接</p>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <p className="text-[15px] font-bold text-gray-900">{departmentsWithQuarterPlan}/{activeDepartments.length || 0}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${activeDepartments.length === 0 || departmentsWithQuarterPlan === activeDepartments.length ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                          {activeDepartments.length === 0 || departmentsWithQuarterPlan === activeDepartments.length ? '已铺开' : '待补'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 rounded-[22px] border border-white/80 bg-white/90 px-4 py-4 shadow-sm">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="max-w-3xl">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#4A63CF]">{selectedStrategyQuarter}</span>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${selectedStrategyQuarter === activeQuarter ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                            {selectedStrategyQuarter === activeQuarter ? '当前执行季度' : '手动校正季度'}
                          </span>
                        </div>
                        <p className="mt-3 text-[14px] font-bold text-gray-900">{focusedQuarterPlan.theme || `${selectedStrategyQuarter} 季度主线待补`}</p>
                        <p className="mt-2 text-[12px] leading-6 text-gray-600">
                          {focusedQuarterPlan.objective.trim() || '这一季的目标还没写。建议先把当季目标和关键结果补完整，再让部门负责人承接。'}
                        </p>
                      </div>
                      <div className="grid grid-cols-3 gap-2 xl:w-[280px]">
                        <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">关键结果</p>
                          <p className="mt-1 text-[14px] font-bold text-gray-900">{focusedQuarterPlan.keyResults.length}</p>
                        </div>
                        <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">关键动作</p>
                          <p className="mt-1 text-[14px] font-bold text-gray-900">{focusedQuarterPlan.keyActions.length}</p>
                        </div>
                        <div className="rounded-2xl bg-gray-50 px-3 py-3 text-center">
                          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">主要风险</p>
                          <p className="mt-1 text-[14px] font-bold text-gray-900">{focusedQuarterPlan.majorRisks.length}</p>
                        </div>
                      </div>
                    </div>
                  <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
                      {orgDnaCompletedCount < organizationDnaModules.length ? (
                        <span className="rounded-full bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
                          仍有 {organizationDnaModules.length - orgDnaCompletedCount} 个组织 DNA 模块待上传
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-50 px-3 py-1.5 font-medium text-emerald-700">组织 DNA 已齐备</span>
                      )}
                      {departmentsMissingQuarterPlanCount > 0 ? (
                        <span className="rounded-full bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
                          仍有 {departmentsMissingQuarterPlanCount} 个部门未承接季度计划
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-50 px-3 py-1.5 font-medium text-emerald-700">部门季度承接已铺开</span>
                      )}
                    </div>
                    <div className="mt-4 rounded-[20px] border border-dashed border-blue-100 bg-white/80 px-4 py-3">
                      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#5B7BFE]">背景生成链路</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-gray-600">
                        <span className="rounded-full bg-blue-50 px-3 py-1.5 font-medium text-[#4A63CF]">组织 DNA</span>
                        <ArrowRight size={12} className="text-gray-300" />
                        <span className="rounded-full bg-blue-50 px-3 py-1.5 font-medium text-[#4A63CF]">年度战略候选</span>
                        <ArrowRight size={12} className="text-gray-300" />
                        <span className="rounded-full bg-blue-50 px-3 py-1.5 font-medium text-[#4A63CF]">四季草稿</span>
                        <ArrowRight size={12} className="text-gray-300" />
                        <span className="rounded-full bg-blue-50 px-3 py-1.5 font-medium text-[#4A63CF]">部门承接候选</span>
                      </div>
                      <p className="mt-3 text-[11px] leading-6 text-gray-600">
                        这条链路的目标是让系统先利用已有背景生成候选内容，再由 CEO 和部门负责人轻量校正，而不是从头写完所有计划。
                      </p>
                    </div>
                  </div>
                </div>

                <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[14px] font-bold text-gray-900">组织 DNA 状态</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">
                        CEO 先补组织介绍、业务介绍、组织介绍和市场调研，后面的战略拆分和智能建议才不会空转。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenSection('org_dna')}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm"
                    >
                      去上传组织 DNA
                    </button>
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                    {organizationDnaModules.map((module) => (
                      <div key={module.moduleKey} className="rounded-[20px] border border-gray-100 bg-gray-50/70 px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-[13px] font-bold text-gray-900">{module.title}</p>
                            <p className="mt-1 text-[11px] text-gray-500">{module.fileName || '尚未上传材料'}</p>
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${module.hasDocument ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                            {module.hasDocument ? '已就绪' : '待上传'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[14px] font-bold text-gray-900">年度目标与年度战略</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">
                        这层由 CEO 维护，一年通常只改少量几次；四季草稿会从这里往下承接。
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={handleGenerateAnnualStrategyCandidate}
                        disabled={!canEdit || !hasAnyOrganizationDna}
                        className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        从已上传资料生成候选草稿
                      </button>
                      <button
                        type="button"
                        onClick={handleGenerateQuarterDrafts}
                        disabled={!canEdit || !value.organization.annualGoal.trim() || !value.organization.annualStrategy.trim()}
                        className="rounded-2xl border border-blue-100 bg-blue-50 px-3 py-2 text-[11px] font-bold text-[#5B7BFE] shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        生成四季草稿
                      </button>
                    </div>
                  </div>
                  <div className="rounded-[20px] border border-dashed border-blue-100 bg-blue-50/60 px-4 py-3 text-[11px] leading-6 text-gray-600">
                    这些字段的首要目标不是做展示，而是给 AI 提供组织级思考背景。后续任务建议、成长判断和流程沉淀，都会优先读取这里的年度目标、战略说明和季度主线。
                  </div>
                  <div className="rounded-[20px] border border-dashed border-gray-200 bg-gray-50/80 px-4 py-3 text-[11px] leading-6 text-gray-600">
                    优先顺序现在改成：先读已上传的组织 DNA 摘要生成候选草稿，再由 CEO 轻量修改；不再默认从空白输入框开始写整套年度战略。
                  </div>
                  <div className="rounded-[20px] border border-gray-100 bg-white px-4 py-3">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-[12px] font-bold text-gray-900">候选草稿写入方式</p>
                        <p className="mt-1 text-[11px] leading-6 text-gray-500">
                          默认只补空白字段，避免覆盖已经人工修改过的内容。需要整段重置时，再切到“覆盖已有内容”。
                        </p>
                      </div>
                      <div className="inline-flex rounded-2xl border border-gray-200 bg-gray-50 p-1">
                        <button
                          type="button"
                          onClick={() => setAnnualDraftApplyMode('fill_empty')}
                          className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${annualDraftApplyMode === 'fill_empty' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                        >
                          只填空白字段
                        </button>
                        <button
                          type="button"
                          onClick={() => setAnnualDraftApplyMode('overwrite')}
                          className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${annualDraftApplyMode === 'overwrite' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                        >
                          覆盖已有内容
                        </button>
                      </div>
                    </div>
                    {organizationDnaReadyModules.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {organizationDnaReadyModules.map((module) => (
                          <span key={module.moduleKey} className="rounded-full bg-gray-50 px-3 py-1 text-[10px] font-bold text-gray-600">
                            已读取：{module.title}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-[11px] text-amber-700">当前还没有可读取的组织 DNA 模块，先上传资料后再生成候选草稿。</p>
                    )}
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-[140px_minmax(0,1fr)]">
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">战略年份</span>
                      <input
                        value={value.organization.annualStrategyYear}
                        onChange={(event) => updateOrganizationStrategy({ annualStrategyYear: event.target.value })}
                        placeholder={String(new Date().getFullYear())}
                        className="w-full rounded-2xl border border-blue-100 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                        disabled={!canEdit}
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">年度目标 / 北极星</span>
                      <textarea
                        value={value.organization.annualGoal}
                        onChange={(event) => updateOrganizationStrategy({ annualGoal: event.target.value })}
                        placeholder="一句话说明今年最核心的目标。"
                        className="min-h-[78px] w-full rounded-2xl border border-blue-100 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                        disabled={!canEdit}
                      />
                    </label>
                  </div>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">年度战略说明</span>
                    <textarea
                      value={value.organization.annualStrategy}
                      onChange={(event) => updateOrganizationStrategy({ annualStrategy: event.target.value })}
                      placeholder="上传或整理后的年度战略摘要，后续四季草稿会从这里承接。"
                      className="min-h-[132px] w-full rounded-2xl border border-blue-100 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                      disabled={!canEdit}
                    />
                  </label>
                </div>

                <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                      <p className="text-[14px] font-bold text-gray-900">四季草稿生成方式</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">
                        四季草稿由年度目标、年度战略和已上传的组织 DNA 共同提供背景。默认只补空白字段，避免覆盖已经人工校正过的季度内容。
                      </p>
                    </div>
                    <div className="inline-flex rounded-2xl border border-gray-200 bg-gray-50 p-1">
                      <button
                        type="button"
                        onClick={() => setQuarterDraftApplyMode('fill_empty')}
                        className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${quarterDraftApplyMode === 'fill_empty' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                      >
                        只填空白字段
                      </button>
                      <button
                        type="button"
                        onClick={() => setQuarterDraftApplyMode('overwrite')}
                        className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${quarterDraftApplyMode === 'overwrite' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                      >
                        覆盖已有内容
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-full bg-gray-50 px-3 py-1 text-[10px] font-bold text-gray-600">来源：年度目标</span>
                    <span className="rounded-full bg-gray-50 px-3 py-1 text-[10px] font-bold text-gray-600">来源：年度战略说明</span>
                    {organizationDnaReadyModules.length > 0 ? organizationDnaReadyModules.map((module) => (
                      <span key={module.moduleKey} className="rounded-full bg-gray-50 px-3 py-1 text-[10px] font-bold text-gray-600">
                        来源：{module.title}
                      </span>
                    )) : (
                      <span className="rounded-full bg-amber-50 px-3 py-1 text-[10px] font-bold text-amber-700">组织 DNA 未齐备时，季度草稿会更保守</span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  {orgQuarterPlans.map((plan) => (
                    <div
                      key={plan.quarter}
                      className={`rounded-[24px] border px-4 py-4 shadow-sm space-y-3 ${selectedStrategyQuarter === plan.quarter ? 'border-[#cdd9ff] bg-[#f7faff]' : 'border-white/80 bg-white'}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[13px] font-bold text-gray-900">{plan.quarter} · {plan.year || strategyYear}</p>
                          <p className="mt-1 text-[11px] text-gray-500">先生成候选，再人工校正。系统会默认保护已经改过的内容。</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${getQuarterPlanStatus(plan) === '待补' ? 'bg-amber-100 text-amber-700' : getQuarterPlanStatus(plan) === '已校正' ? 'bg-blue-100 text-[#4A63CF]' : 'bg-emerald-100 text-emerald-700'}`}>
                            {getQuarterPlanStatus(plan)}
                          </span>
                          <button
                            type="button"
                            onClick={() => setSelectedStrategyQuarter(plan.quarter)}
                            className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${selectedStrategyQuarter === plan.quarter ? 'border-[#5B7BFE] bg-white text-[#5B7BFE]' : 'border-gray-200 bg-white text-gray-600'}`}
                          >
                            {selectedStrategyQuarter === plan.quarter ? '当前聚焦' : '设为聚焦'}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleGenerateSingleQuarterDraft(plan.quarter)}
                            disabled={!canEdit || !value.organization.annualGoal.trim() || !value.organization.annualStrategy.trim()}
                            className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[10px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            生成候选
                          </button>
                        </div>
                      </div>
                      <div className="rounded-[18px] border border-dashed border-gray-200 bg-white/80 px-3 py-2 text-[11px] leading-6 text-gray-600">
                        读取来源：年度目标、年度战略说明{organizationDnaReadyModules.length > 0 ? '、组织 DNA 摘要' : ''}。
                        {plan.updatedAt ? ` 最近人工校正：${new Date(plan.updatedAt).toLocaleString('zh-CN', { hour12: false })}` : ' 当前仍以候选草稿为主，可继续人工校正。'}
                      </div>
                      <input
                        value={plan.theme}
                        onChange={(event) => updateQuarterPlan(plan.quarter, { theme: event.target.value })}
                        placeholder="季度主题"
                        className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                        disabled={!canEdit}
                      />
                      <textarea
                        value={plan.objective}
                        onChange={(event) => updateQuarterPlan(plan.quarter, { objective: event.target.value })}
                        placeholder="季度目标"
                        className="min-h-[88px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                        disabled={!canEdit}
                      />
                      <textarea
                        value={toMultiline(plan.keyResults)}
                        onChange={(event) => updateQuarterPlan(plan.quarter, { keyResults: fromMultiline(event.target.value) })}
                        placeholder="关键结果，每行一条"
                        className="min-h-[84px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                        disabled={!canEdit}
                      />
                      <textarea
                        value={toMultiline(plan.keyActions)}
                        onChange={(event) => updateQuarterPlan(plan.quarter, { keyActions: fromMultiline(event.target.value) })}
                        placeholder="关键动作，每行一条"
                        className="min-h-[84px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                        disabled={!canEdit}
                      />
                      <textarea
                        value={toMultiline(plan.majorRisks)}
                        onChange={(event) => updateQuarterPlan(plan.quarter, { majorRisks: fromMultiline(event.target.value) })}
                        placeholder="主要风险，每行一条"
                        className="min-h-[74px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                        disabled={!canEdit}
                      />
                    </div>
                  ))}
                </div>

                <div className="rounded-[24px] border border-white/80 bg-white px-4 py-4 shadow-sm space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[14px] font-bold text-gray-900">部门负责人承接季度计划</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">
                        这一层是部门负责人来补，先写部门业务/团队背景，再把本部门本季度要完成的目标和产出补齐。
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
                        {departmentsWithQuarterPlan}/{activeDepartments.length || 0} 个已承接
                      </span>
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-[11px] font-bold text-[#4A63CF]">
                        当前默认承接 {selectedStrategyQuarter}
                      </span>
                      <button
                        type="button"
                        onClick={handleGenerateAllDepartmentCandidates}
                        disabled={!canEdit || activeDepartments.length === 0}
                        className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        批量生成候选承接草稿
                      </button>
                    </div>
                  </div>
                  <div className="rounded-[20px] border border-dashed border-emerald-100 bg-emerald-50/60 px-4 py-3 text-[11px] leading-6 text-gray-600">
                    这层不是孤立的部门填表。AI 后续会先读公司季度主线，再读这里的部门背景与部门季度目标，所以部门负责人补的是“承接语境”，不是单独写一份说明书。
                  </div>
                  <div className="rounded-[20px] border border-dashed border-gray-200 bg-gray-50/80 px-4 py-3 text-[11px] leading-6 text-gray-600">
                    这里也不应该让部门负责人从空白开始写。系统会优先使用：部门名称、负责人、部门使命、当前聚焦季度主线和已有组织背景，生成可修改的候选草稿。
                  </div>
                  <div className="rounded-[20px] border border-gray-100 bg-white px-4 py-3">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-[12px] font-bold text-gray-900">部门承接候选写入方式</p>
                        <p className="mt-1 text-[11px] leading-6 text-gray-500">
                          默认只补空白字段，优先保护负责人已经改过的内容。只有明确要重置部门承接时，再切到覆盖模式。
                        </p>
                      </div>
                      <div className="inline-flex rounded-2xl border border-gray-200 bg-gray-50 p-1">
                        <button
                          type="button"
                          onClick={() => setDepartmentDraftApplyMode('fill_empty')}
                          className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${departmentDraftApplyMode === 'fill_empty' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                        >
                          只填空白字段
                        </button>
                        <button
                          type="button"
                          onClick={() => setDepartmentDraftApplyMode('overwrite')}
                          className={`rounded-2xl px-3 py-2 text-[11px] font-bold transition ${departmentDraftApplyMode === 'overwrite' ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500'}`}
                        >
                          覆盖已有内容
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    {activeDepartments.length > 0 ? activeDepartments.map((department) => {
                      const relayStatus = getDepartmentRelayStatus(department);
                      const latestManualUpdate = getDepartmentLatestManualUpdate(department);
                      const relaySourceLabels = [
                        selectedStrategyQuarter ? `${selectedStrategyQuarter} 聚焦季度` : '',
                        value.organization.annualStrategy.trim() || value.organization.annualGoal.trim() ? `${strategyYear} 战略主线` : '',
                        organizationDnaReadyModules.length > 0 ? `组织 DNA（${organizationDnaReadyModules.length} 项）` : '',
                        '部门名称 / 负责人 / 部门使命',
                      ].filter(Boolean);
                      const deliverableCount = department.quarterPlan.deliverables.filter((item) => item.trim()).length;
                      const successMetricCount = department.quarterPlan.successMetrics.filter((item) => item.trim()).length;
                      const riskCount = department.quarterPlan.majorRisks.filter((item) => item.trim()).length;
                      return (
                      <div key={department.id} className="rounded-[22px] border border-gray-100 bg-gray-50/70 px-4 py-4 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-[14px] font-bold text-gray-900">{department.name}</p>
                            <p className="mt-1 text-[11px] text-gray-500">负责人：{department.leaderName?.trim() || (department.leaderUserId ? employeeById.get(department.leaderUserId)?.fullName || '已指定' : '待指定')}</p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                              relayStatus === '已校正'
                                ? 'bg-emerald-100 text-emerald-700'
                                : relayStatus === '候选已生成'
                                  ? 'bg-sky-100 text-sky-700'
                                  : 'bg-amber-100 text-amber-700'
                            }`}>
                              {relayStatus}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleGenerateDepartmentCandidate(department.id)}
                              disabled={!canEdit}
                              className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[10px] font-bold text-gray-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              生成候选
                            </button>
                          </div>
                        </div>
                        <div className="rounded-2xl border border-[#DCE5FF] bg-[#F6F8FF] px-3 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            {relaySourceLabels.map((label) => (
                              <span key={label} className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-[#5B7BFE] shadow-sm">
                                {label}
                              </span>
                            ))}
                          </div>
                          <p className="mt-2 text-[11px] leading-6 text-gray-500">
                            系统会先根据这些背景生成部门承接候选，再由负责人做轻量校正。
                            {latestManualUpdate ? ` 最近人工校正：${latestManualUpdate}` : ' 当前仍以候选草稿为主，可继续人工校正。'}
                          </p>
                        </div>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                          <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">年度</p>
                            <p className="mt-2 text-[15px] font-bold text-gray-900">{department.quarterPlan.year || strategyYear}</p>
                          </div>
                          <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">季度</p>
                            <p className="mt-2 text-[15px] font-bold text-gray-900">{department.quarterPlan.quarter || activeQuarter}</p>
                          </div>
                          <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">关键产出</p>
                            <p className="mt-2 text-[15px] font-bold text-gray-900">{deliverableCount}</p>
                          </div>
                          <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3">
                            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">主要风险</p>
                            <p className="mt-2 text-[15px] font-bold text-gray-900">{riskCount}</p>
                          </div>
                        </div>
                        <div className="rounded-[20px] border border-gray-200 bg-white p-4 space-y-3">
                          <div>
                            <p className="text-[12px] font-bold text-gray-900">部门背景</p>
                            <p className="mt-1 text-[11px] leading-6 text-gray-500">先补这个部门在组织里承担的价值和当前团队情况，后面的季度承接会更贴近真实能力边界。</p>
                          </div>
                          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                            <div className="space-y-2">
                              <p className="text-[11px] font-bold text-gray-500">部门业务介绍</p>
                              <textarea
                                value={department.businessContext}
                                onChange={(event) => updateDepartmentStrategy(department.id, { businessContext: event.target.value })}
                                placeholder="这个部门负责什么、在组织里承担什么价值。"
                                className="min-h-[92px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                                disabled={!canEdit}
                              />
                            </div>
                            <div className="space-y-2">
                              <p className="text-[11px] font-bold text-gray-500">团队情况</p>
                              <textarea
                                value={department.teamContext}
                                onChange={(event) => updateDepartmentStrategy(department.id, { teamContext: event.target.value })}
                                placeholder="团队构成、当前能力、协作方式和主要缺口。"
                                className="min-h-[92px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                                disabled={!canEdit}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="rounded-[20px] border border-gray-200 bg-white p-4 space-y-3">
                          <div className="flex flex-wrap items-end justify-between gap-3">
                            <div>
                              <p className="text-[12px] font-bold text-gray-900">当前季度承接</p>
                              <p className="mt-1 text-[11px] leading-6 text-gray-500">先确定这季度要达成什么，再拆关键产出、成功标准和主要风险。</p>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              <input
                                value={department.quarterPlan.year}
                                onChange={(event) => updateDepartmentQuarterPlan(department.id, { year: event.target.value })}
                                placeholder={strategyYear}
                                className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                                disabled={!canEdit}
                              />
                              <select
                                value={department.quarterPlan.quarter}
                                onChange={(event) => updateDepartmentQuarterPlan(department.id, { quarter: event.target.value as OrgQuarterKey })}
                                className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium outline-none"
                                disabled={!canEdit}
                              >
                                {ORG_QUARTER_OPTIONS.map((quarter) => (
                                  <option key={quarter} value={quarter}>
                                    {quarter}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                          <div className="space-y-2">
                            <p className="text-[11px] font-bold text-gray-500">本季度目标</p>
                            <textarea
                              value={department.quarterPlan.objective}
                              onChange={(event) => updateDepartmentQuarterPlan(department.id, { objective: event.target.value })}
                              placeholder="这个部门本季度最重要的目标是什么，最好写成一句可执行的话。"
                              className="min-h-[92px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                              disabled={!canEdit}
                            />
                          </div>
                          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <p className="text-[11px] font-bold text-gray-500">关键产出</p>
                                <span className="text-[10px] font-bold text-gray-400">{deliverableCount} 条</span>
                              </div>
                              <textarea
                                value={toMultiline(department.quarterPlan.deliverables)}
                                onChange={(event) => updateDepartmentQuarterPlan(department.id, { deliverables: fromMultiline(event.target.value) })}
                                placeholder="每行一条，写这个季度要交付什么。"
                                className="min-h-[104px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                                disabled={!canEdit}
                              />
                            </div>
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <p className="text-[11px] font-bold text-gray-500">成功标准</p>
                                <span className="text-[10px] font-bold text-gray-400">{successMetricCount} 条</span>
                              </div>
                              <textarea
                                value={toMultiline(department.quarterPlan.successMetrics)}
                                onChange={(event) => updateDepartmentQuarterPlan(department.id, { successMetrics: fromMultiline(event.target.value) })}
                                placeholder="每行一条，写怎么判断这个季度做成了。"
                                className="min-h-[104px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                                disabled={!canEdit}
                              />
                            </div>
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <p className="text-[11px] font-bold text-gray-500">主要风险</p>
                                <span className="text-[10px] font-bold text-gray-400">{riskCount} 条</span>
                              </div>
                              <textarea
                                value={toMultiline(department.quarterPlan.majorRisks)}
                                onChange={(event) => updateDepartmentQuarterPlan(department.id, { majorRisks: fromMultiline(event.target.value) })}
                                placeholder="每行一条，写当前最可能卡住这一季的风险。"
                                className="min-h-[104px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 outline-none resize-none"
                                disabled={!canEdit}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    ); }) : (
                      <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                        先在前面的步骤里创建部门并指定负责人，这里才会出现部门季度计划承接区。
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => void handleSaveStrategyStep()}
                    disabled={!canEdit || isSaving || !annualStrategyReady}
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    保存战略与部门季度计划
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-[16px] font-bold text-gray-900">组织搭建进度</h3>
                <p className="mt-1 text-[12px] text-gray-500">一次只推进一步，剩余项自动留在待补清单里。</p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#5B7BFE]">{progressPercent}%</span>
            </div>
            <div className="mt-4 space-y-3">
              {steps.map((step, index) => (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => handleSelectStep(step)}
                  className={`w-full rounded-[22px] border px-4 py-3 text-left transition ${step.done ? 'border-emerald-100 bg-emerald-50/70 hover:border-emerald-200 hover:bg-emerald-50' : currentStep.id === step.id ? 'border-blue-200 bg-blue-50/70' : 'border-gray-100 bg-gray-50/70 hover:border-blue-100 hover:bg-blue-50/40'}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {step.done ? <CheckCircle2 size={16} className="text-emerald-600" /> : <div className="flex h-4 w-4 items-center justify-center rounded-full border border-gray-300 text-[10px] font-bold text-gray-500">{index + 1}</div>}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-gray-900">{step.title}</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">{step.stat}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-amber-100 bg-amber-50/70 p-5 shadow-sm">
            <h3 className="text-[16px] font-bold text-gray-900">待补事项</h3>
            <p className="mt-1 text-[12px] text-gray-500">这些缺口会直接影响任务路由、周计划判断和学习沉淀质量。</p>
            <div className="mt-4 space-y-3">
              {generatedTasks.map((task) => (
                <button
                  key={task.id}
                  type="button"
                  onClick={() => handleOpenGeneratedTask(task)}
                  className="w-full rounded-[22px] border border-white/70 bg-white/80 px-4 py-3 text-left shadow-sm transition hover:border-amber-200"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-gray-900">{task.title}</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">{task.helper}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold text-amber-700">
                      {task.ownerLabel}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <OrganizationTreeCanvas
        value={value}
        departmentCatalog={departmentCatalog}
        employees={employees}
        canEdit={canEdit}
        onChange={onChange}
      />

      <div className="rounded-3xl border border-gray-100 bg-white shadow-sm">
        <button
          type="button"
          onClick={() => setAdvancedOpen((prev) => !prev)}
          className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
        >
          <div>
            <h3 className="text-[16px] font-bold text-gray-900">高级编辑</h3>
            <p className="mt-1 text-[12px] text-gray-500">
              需要精细调整部门使命、岗位职责、汇报线和任务控制规则时，再进入这一层。
            </p>
          </div>
          {advancedOpen ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
        </button>
        {advancedOpen && (
          <div className="border-t border-gray-100 p-6 pt-5">
            <OrganizationModelSettingsPanel
              value={value}
              departmentCatalog={departmentCatalog}
              employees={employees}
              canEdit={canEdit}
              isSaving={isSaving}
              forcedTab={advancedTab}
              title="组织底盘高级编辑"
              helper={`用同一份组织模型继续细化机构目标、岗位职责、汇报线、流程模板和任务控制规则。当前推荐聚焦：${steps.find((step) => step.tab === advancedTab && !step.done)?.title || '继续补全组织底盘'}`}
              onChange={onChange}
              onSave={() => void onSave()}
            />
          </div>
        )}
      </div>
    </div>
  );
}
