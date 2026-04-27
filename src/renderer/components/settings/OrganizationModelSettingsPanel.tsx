import { useEffect, useMemo, useState } from 'react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentPlanItemSettings,
  OrgDepartmentPlanSettings,
  OrgDepartmentPlanItemStatus,
  OrgDepartmentPlanStatus,
  OrgEmployeeBindingSettings,
  OrgFocusItemSettings,
  OrgFocusPriority,
  OrgFocusStatus,
  OrgModelSettings,
  OrgRoleProcessTemplateSettings,
  OrgRoleLevel,
  OrgRuleActorScope,
  OrgTaskControlLevel,
  OrgTaskEditScope,
  OrgWorkflowTriggerType,
} from '../../../shared/types';

const ROLE_LEVEL_OPTIONS: Array<{ value: OrgRoleLevel; label: string }> = [
  { value: 'organization_lead', label: '机构负责人' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'supervisor', label: '主管' },
  { value: 'employee', label: '员工' },
];

const TASK_EDIT_SCOPE_OPTIONS: Array<{ value: OrgTaskEditScope; label: string }> = [
  { value: 'self', label: '仅本人' },
  { value: 'manager', label: '直属上级' },
  { value: 'department', label: '部门层' },
  { value: 'organization', label: '机构层' },
];

const RULE_SCOPE_OPTIONS: Array<{ value: OrgRuleActorScope; label: string }> = [
  { value: 'assignee', label: '负责人' },
  { value: 'creator', label: '创建人' },
  { value: 'manager', label: '直属上级' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'organization_lead', label: '机构负责人' },
];

const CONTROL_LEVEL_OPTIONS: Array<{ value: OrgTaskControlLevel; label: string }> = [
  { value: 'normal', label: '普通' },
  { value: 'leader_control', label: 'leader 控制' },
  { value: 'department_control', label: '部门控制' },
  { value: 'organization_control', label: '机构控制' },
];

const WORKFLOW_TRIGGER_OPTIONS: Array<{ value: OrgWorkflowTriggerType; label: string }> = [
  { value: 'weekly_followup', label: '周会后推进' },
  { value: 'task_created', label: '任务创建后' },
  { value: 'meeting_closed', label: '会议结束后' },
  { value: 'client_update', label: '客户状态更新后' },
  { value: 'manual', label: '手动触发' },
];

const FOCUS_PRIORITY_OPTIONS: Array<{ value: OrgFocusPriority; label: string }> = [
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' },
];

const FOCUS_STATUS_OPTIONS: Array<{ value: OrgFocusStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'draft', label: '草稿' },
  { value: 'paused', label: '暂停' },
  { value: 'done', label: '完成' },
];

const PLAN_STATUS_OPTIONS: Array<{ value: OrgDepartmentPlanStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'draft', label: '草稿' },
  { value: 'closed', label: '已关闭' },
];

const PLAN_ITEM_STATUS_OPTIONS: Array<{ value: OrgDepartmentPlanItemStatus; label: string }> = [
  { value: 'active', label: '进行中' },
  { value: 'paused', label: '暂停' },
  { value: 'done', label: '已完成' },
  { value: 'dropped', label: '已放弃' },
];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
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

type Props = {
  value: OrgModelSettings;
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  forcedTab?: OrgModelTab | null;
  hideTabNavigation?: boolean;
  title?: string;
  helper?: string;
  onChange: (next: OrgModelSettings) => void;
  onSave: () => void;
};

export type OrgModelTab = 'overview' | 'departments' | 'people' | 'rules';

function emptyBindingForUser(user: EmployeeRecord): OrgEmployeeBindingSettings {
  return {
    userId: user.id,
    departmentId: user.departmentId || null,
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

export function OrganizationModelSettingsPanel({
  value,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  forcedTab = null,
  hideTabNavigation = false,
  title = '组织模型层（P0）',
  helper = '先搭“组织关系 + 岗位职责 + 汇报线 + 权限规则”的最小底座，让任务、周计划和周总结能读到真实组织背景。',
  onChange,
  onSave,
}: Props) {
  const [tab, setTab] = useState<OrgModelTab>(forcedTab || 'overview');

  useEffect(() => {
    if (forcedTab) {
      setTab(forcedTab);
    }
  }, [forcedTab]);

  const employeeOptions = useMemo(
    () => [...employees].sort((a, b) => a.fullName.localeCompare(b.fullName, 'zh-Hans-CN')),
    [employees],
  );

  const departmentOptions = useMemo(() => {
    if (value.departments.length > 0) {
      return value.departments.map((item) => ({ id: item.id, name: item.name, color: item.color }));
    }
    return departmentCatalog;
  }, [departmentCatalog, value.departments]);

  const roleOptions = useMemo(() => [...value.roles].sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name, 'zh-Hans-CN')), [value.roles]);
  const bindingByUserId = useMemo(() => new Map(value.bindings.map((item) => [item.userId, item])), [value.bindings]);

  const updateOrganization = (patch: Partial<OrgModelSettings['organization']>) => {
    onChange({ ...value, organization: { ...value.organization, ...patch } });
  };

  const updateDepartment = (departmentId: string, updater: (current: OrgModelSettings['departments'][number]) => OrgModelSettings['departments'][number]) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? updater(item) : item)),
    });
  };

  const updateRole = (roleId: string, updater: (current: OrgModelSettings['roles'][number]) => OrgModelSettings['roles'][number]) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? updater(item) : item)),
    });
  };

  const ensureBinding = (user: EmployeeRecord) => bindingByUserId.get(user.id) || emptyBindingForUser(user);

  const updateBinding = (user: EmployeeRecord, patch: Partial<OrgEmployeeBindingSettings>) => {
    const existing = bindingByUserId.get(user.id);
    const nextBinding = { ...(existing || emptyBindingForUser(user)), ...patch };
    onChange({
      ...value,
      bindings: existing ? value.bindings.map((item) => (item.userId === user.id ? nextBinding : item)) : [...value.bindings, nextBinding],
    });
  };

  const updateReportingLine = (lineId: string, updater: (current: OrgModelSettings['reportingLines'][number]) => OrgModelSettings['reportingLines'][number]) => {
    onChange({
      ...value,
      reportingLines: value.reportingLines.map((item) => (item.id === lineId ? updater(item) : item)),
    });
  };

  const updateRule = (ruleId: string, updater: (current: OrgModelSettings['taskControlRules'][number]) => OrgModelSettings['taskControlRules'][number]) => {
    onChange({
      ...value,
      taskControlRules: value.taskControlRules.map((item) => (item.id === ruleId ? updater(item) : item)),
    });
  };

  const updateProcessTemplate = (
    templateId: string,
    updater: (current: OrgRoleProcessTemplateSettings) => OrgRoleProcessTemplateSettings,
  ) => {
    onChange({
      ...value,
      roleProcessTemplates: value.roleProcessTemplates.map((item) => (item.id === templateId ? updater(item) : item)),
    });
  };

  const updateFocusItem = (
    focusItemId: string,
    updater: (current: OrgFocusItemSettings) => OrgFocusItemSettings,
  ) => {
    onChange({
      ...value,
      focusItems: value.focusItems.map((item) => (item.id === focusItemId ? updater(item) : item)),
    });
  };

  const updateDepartmentPlan = (
    planId: string,
    updater: (current: OrgDepartmentPlanSettings) => OrgDepartmentPlanSettings,
  ) => {
    onChange({
      ...value,
      departmentPlans: value.departmentPlans.map((item) => (item.id === planId ? updater(item) : item)),
    });
  };

  const updateDepartmentPlanItem = (
    planId: string,
    itemId: string,
    updater: (current: OrgDepartmentPlanItemSettings) => OrgDepartmentPlanItemSettings,
  ) => {
    updateDepartmentPlan(planId, (plan) => ({
      ...plan,
      items: plan.items.map((item) => (item.id === itemId ? updater(item) : item)),
    }));
  };

  const addRole = () => {
    onChange({
      ...value,
      roles: [
        ...value.roles,
        {
          id: nextUiId('role'),
          departmentId: departmentOptions[0]?.id || null,
          name: '',
          level: 'employee',
          managerRoleId: null,
          isManager: false,
          goal: '',
          responsibilities: [],
          shouldAvoid: [],
          collaborationRoleIds: [],
          taskEditScope: 'self',
          canApproveTasks: false,
          canReassignTasks: false,
          canChangeDeadline: false,
          sortOrder: value.roles.length,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addFocusItem = () => {
    onChange({
      ...value,
      focusItems: [
        ...value.focusItems,
        {
          id: nextUiId('focus'),
          periodKey: '',
          title: '',
          statement: '',
          ownerUserId: null,
          priority: 'medium',
          status: 'draft',
          evidenceKeywords: [],
          updatedAt: '',
        },
      ],
    });
  };

  const addDepartmentPlan = (departmentId: string | null = departmentOptions[0]?.id || null) => {
    onChange({
      ...value,
      departmentPlans: [
        ...value.departmentPlans,
        {
          id: nextUiId('plan'),
          departmentId,
          weekLabel: '',
          ownerUserId: null,
          summary: '',
          majorRisks: [],
          dependencies: [],
          status: 'draft',
          items: [],
          updatedAt: '',
        },
      ],
    });
  };

  const addDepartmentPlanItem = (planId: string) => {
    updateDepartmentPlan(planId, (plan) => ({
      ...plan,
      items: [
        ...plan.items,
        {
          id: nextUiId('plan_item'),
          focusItemId: null,
          title: '',
          statement: '',
          ownerUserId: null,
          status: 'active',
          expectedOutput: '',
          sortOrder: plan.items.length,
          updatedAt: '',
        },
      ],
    }));
  };

  const addReportingLine = () => {
    if (employeeOptions.length < 2) return;
    onChange({
      ...value,
      reportingLines: [
        ...value.reportingLines,
        {
          id: nextUiId('line'),
          managerUserId: employeeOptions[0].id,
          reportUserId: employeeOptions[1].id,
          lineType: 'business',
          approvesTasks: true,
          canAdjustTasks: false,
          canChangeDeadline: false,
          canReassignTasks: false,
          isCrossDepartmentApprover: false,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addRule = () => {
    onChange({
      ...value,
      taskControlRules: [
        ...value.taskControlRules,
        {
          id: nextUiId('rule'),
          name: '',
          controlLevel: 'normal',
          departmentId: null,
          roleTemplateId: null,
          contentEditableBy: 'assignee',
          deadlineEditableBy: 'manager',
          ownerEditableBy: 'manager',
          cancellableBy: 'manager',
          requireCollabConfirmation: false,
          defaultApproverUserId: null,
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addProcessTemplate = () => {
    onChange({
      ...value,
      roleProcessTemplates: [
        ...value.roleProcessTemplates,
        {
          id: nextUiId('process'),
          roleTemplateId: roleOptions[0]?.id || null,
          name: '',
          triggerType: 'manual',
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
    });
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">{title}</h2>
          <p className="text-[12px] text-gray-500 mt-1">{helper}</p>
        </div>
        <button
          type="button"
          className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onSave}
          disabled={!canEdit || isSaving}
        >
          {isSaving ? '保存中...' : '保存组织模型'}
        </button>
      </div>

      {!hideTabNavigation && <div className="flex flex-wrap gap-2">
        {[
          ['overview', '组织总览'],
          ['departments', '部门与岗位'],
          ['people', '人员配置'],
          ['rules', '流程与权限'],
        ].map(([key, label]) => {
          const active = tab === key;
          return (
            <button
              key={key}
              type="button"
              className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${active ? 'bg-[#111827] text-white' : 'bg-gray-50 text-gray-500 border border-gray-200'}`}
              onClick={() => setTab(key as OrgModelTab)}
            >
              {label}
            </button>
          );
        })}
      </div>}

      {tab === 'overview' && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                value={value.organization.name}
                onChange={(event) => updateOrganization({ name: event.target.value })}
                className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                placeholder="机构名称"
                disabled={!canEdit}
              />
              <select
                value={value.organization.leaderUserId || ''}
                onChange={(event) => updateOrganization({ leaderUserId: event.target.value || null })}
                className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                disabled={!canEdit}
              >
                <option value="">请选择机构负责人</option>
                {employeeOptions.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.fullName}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              value={value.organization.annualGoal}
              onChange={(event) => updateOrganization({ annualGoal: event.target.value })}
              className="min-h-[84px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              placeholder="年度目标"
              disabled={!canEdit}
            />
            <textarea
              value={toMultiline(value.organization.quarterlyFocus)}
              onChange={(event) => updateOrganization({ quarterlyFocus: fromMultiline(event.target.value) })}
              className="min-h-[96px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              placeholder="当前季度重点，每行一条"
              disabled={!canEdit}
            />
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-gray-700">管理层名单</p>
              <div className="flex flex-wrap gap-2">
                {employeeOptions.map((employee) => {
                  const active = value.organization.managementUserIds.includes(employee.id);
                  return (
                    <button
                      key={`mgmt:${employee.id}`}
                      type="button"
                      disabled={!canEdit}
                      onClick={() =>
                        updateOrganization({
                          managementUserIds: active
                            ? value.organization.managementUserIds.filter((item) => item !== employee.id)
                            : [...value.organization.managementUserIds, employee.id],
                        })
                      }
                      className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${active ? 'bg-[#5B7BFE] text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
                    >
                      {employee.fullName}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">机构季度重点</p>
                <p className="text-[11px] text-gray-500 mt-1">这些重点会作为机构级背景，供任务挂接和 CEO 总结自动对照。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addFocusItem} disabled={!canEdit}>
                新增重点
              </button>
            </div>
            <div className="space-y-3">
              {value.focusItems.map((focusItem) => (
                <div key={focusItem.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                      value={focusItem.periodKey}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, periodKey: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="周期，例如 2026-Q1"
                      disabled={!canEdit}
                    />
                    <input
                      value={focusItem.title}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, title: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="重点标题"
                      disabled={!canEdit}
                    />
                    <select
                      value={focusItem.priority}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, priority: event.target.value as OrgFocusPriority }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {FOCUS_PRIORITY_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <select
                      value={focusItem.status}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, status: event.target.value as OrgFocusStatus }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {FOCUS_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <select
                      value={focusItem.ownerUserId || ''}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未指定负责人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <input
                      value={focusItem.statement}
                      onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, statement: event.target.value }))}
                      className="md:col-span-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="一句话说明这条机构重点"
                      disabled={!canEdit}
                    />
                  </div>
                  <textarea
                    value={toMultiline(focusItem.evidenceKeywords)}
                    onChange={(event) => updateFocusItem(focusItem.id, (current) => ({ ...current, evidenceKeywords: fromMultiline(event.target.value) }))}
                    className="min-h-[74px] w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                    placeholder="证据关键词，每行一条"
                    disabled={!canEdit}
                  />
                </div>
              ))}
              {value.focusItems.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有机构季度重点。建议先录入本季度最重要的 3-5 条战略主线。
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'departments' && (
        <div className="space-y-5">
          {value.departments.map((department) => (
            <div key={department.id} className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: department.color }} />
                <div>
                  <p className="text-[14px] font-bold text-gray-900">{department.name}</p>
                  <p className="text-[11px] text-gray-500 mt-1">部门使命、季度重点、核心协作部门和岗位模板。</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <select
                  value={department.leaderUserId || ''}
                  onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, leaderUserId: event.target.value || null }))}
                  className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                  disabled={!canEdit}
                >
                  <option value="">请选择部门负责人</option>
                  {employeeOptions.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.fullName}
                    </option>
                  ))}
                </select>
                <label className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium flex items-center justify-between">
                  启用部门
                  <input
                    type="checkbox"
                    checked={department.active}
                    onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, active: event.target.checked }))}
                    disabled={!canEdit}
                  />
                </label>
              </div>

              <textarea
                value={department.mission}
                onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, mission: event.target.value }))}
                className="min-h-[76px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                placeholder="部门使命"
                disabled={!canEdit}
              />
              <textarea
                value={toMultiline(department.quarterlyFocus)}
                onChange={(event) => updateDepartment(department.id, (current) => ({ ...current, quarterlyFocus: fromMultiline(event.target.value) }))}
                className="min-h-[90px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                placeholder="部门季度重点，每行一条"
                disabled={!canEdit}
              />

              <div className="space-y-2">
                <p className="text-[12px] font-bold text-gray-700">核心协作部门</p>
                <div className="flex flex-wrap gap-2">
                  {departmentOptions
                    .filter((option) => option.id !== department.id)
                    .map((option) => {
                      const active = department.collaborationDepartmentIds.includes(option.id);
                      return (
                        <button
                          key={`${department.id}:${option.id}`}
                          type="button"
                          disabled={!canEdit}
                          onClick={() =>
                            updateDepartment(department.id, (current) => ({
                              ...current,
                              collaborationDepartmentIds: active
                                ? current.collaborationDepartmentIds.filter((item) => item !== option.id)
                                : [...current.collaborationDepartmentIds, option.id],
                            }))
                          }
                          className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${active ? 'bg-emerald-500 text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
                        >
                          {option.name}
                        </button>
                      );
                    })}
                </div>
              </div>
            </div>
          ))}

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">部门周计划</p>
                <p className="text-[11px] text-gray-500 mt-1">部门负责人每周维护 3-5 条重点计划，后续任务会自动尝试挂接到这些计划项。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={() => addDepartmentPlan()} disabled={!canEdit}>
                新增部门计划
              </button>
            </div>
            <div className="space-y-4">
              {value.departmentPlans.map((plan) => (
                <div key={plan.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={plan.departmentId || ''}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, departmentId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">请选择部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.name}</option>
                      ))}
                    </select>
                    <input
                      value={plan.weekLabel}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, weekLabel: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="周次，例如 2026-W12"
                      disabled={!canEdit}
                    />
                    <select
                      value={plan.ownerUserId || ''}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未指定负责人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select
                      value={plan.status}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, status: event.target.value as OrgDepartmentPlanStatus }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {PLAN_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <textarea
                    value={plan.summary}
                    onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, summary: event.target.value }))}
                    className="min-h-[74px] w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                    placeholder="本周部门计划摘要"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(plan.majorRisks)}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, majorRisks: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="主要风险，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(plan.dependencies)}
                      onChange={(event) => updateDepartmentPlan(plan.id, (current) => ({ ...current, dependencies: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="依赖 / 支持需求，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="rounded-[18px] border border-gray-200 bg-white p-3 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] font-bold text-gray-800">计划项</p>
                      <button type="button" className="rounded-xl border border-gray-200 px-3 py-1.5 text-[11px] font-bold text-gray-600" onClick={() => addDepartmentPlanItem(plan.id)} disabled={!canEdit}>
                        新增计划项
                      </button>
                    </div>
                    <div className="space-y-3">
                      {plan.items.map((item) => (
                        <div key={item.id} className="rounded-[16px] border border-gray-200 bg-gray-50 p-3 space-y-3">
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                            <input
                              value={item.title}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, title: event.target.value }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              placeholder="计划项标题"
                              disabled={!canEdit}
                            />
                            <select
                              value={item.focusItemId || ''}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, focusItemId: event.target.value || null }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              <option value="">未挂机构重点</option>
                              {value.focusItems.map((focusItem) => (
                                <option key={focusItem.id} value={focusItem.id}>{focusItem.title || focusItem.id}</option>
                              ))}
                            </select>
                            <select
                              value={item.ownerUserId || ''}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, ownerUserId: event.target.value || null }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              <option value="">未指定负责人</option>
                              {employeeOptions.map((employee) => (
                                <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                              ))}
                            </select>
                            <select
                              value={item.status}
                              onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, status: event.target.value as OrgDepartmentPlanItemStatus }))}
                              className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                              disabled={!canEdit}
                            >
                              {PLAN_ITEM_STATUS_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                              ))}
                            </select>
                          </div>
                          <input
                            value={item.statement}
                            onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, statement: event.target.value }))}
                            className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                            placeholder="一句话说明计划项要解决什么"
                            disabled={!canEdit}
                          />
                          <input
                            value={item.expectedOutput}
                            onChange={(event) => updateDepartmentPlanItem(plan.id, item.id, (current) => ({ ...current, expectedOutput: event.target.value }))}
                            className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                            placeholder="预期产出"
                            disabled={!canEdit}
                          />
                        </div>
                      ))}
                      {plan.items.length === 0 && (
                        <div className="rounded-[16px] border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-center text-[12px] text-gray-400">
                          还没有计划项。建议每周保持 3-5 条重点项，并尽量关联到机构季度重点。
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {value.departmentPlans.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有部门周计划。保存后，任务会自动尝试挂接到对应部门的计划项。
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">岗位模板</p>
                <p className="text-[11px] text-gray-500 mt-1">每个岗位尽量只保留结构化短字段，后面 AI 才能拿它判断职责偏离。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addRole} disabled={!canEdit}>
                新增岗位
              </button>
            </div>
            <div className="space-y-4">
              {roleOptions.map((role) => (
                <div key={role.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                      value={role.name}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, name: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="岗位名称"
                      disabled={!canEdit}
                    />
                    <select
                      value={role.departmentId || ''}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, departmentId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未绑定部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={role.level}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, level: event.target.value as OrgRoleLevel }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {ROLE_LEVEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      管理岗
                      <input
                        type="checkbox"
                        checked={role.isManager}
                        onChange={(event) => updateRole(role.id, (current) => ({ ...current, isManager: event.target.checked }))}
                        disabled={!canEdit}
                      />
                    </label>
                  </div>
                  <input
                    value={role.goal}
                    onChange={(event) => updateRole(role.id, (current) => ({ ...current, goal: event.target.value }))}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                    placeholder="岗位目标（一句话）"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(role.responsibilities)}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, responsibilities: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="主要职责，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(role.shouldAvoid)}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, shouldAvoid: fromMultiline(event.target.value) }))}
                      className="min-h-[84px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="不该长期承担的事务，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={role.managerRoleId || ''}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, managerRoleId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">无上级岗位</option>
                      {roleOptions
                        .filter((option) => option.id !== role.id)
                        .map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                    </select>
                    <select
                      value={role.taskEditScope}
                      onChange={(event) => updateRole(role.id, (current) => ({ ...current, taskEditScope: event.target.value as OrgTaskEditScope }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {TASK_EDIT_SCOPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      审批任务
                      <input type="checkbox" checked={role.canApproveTasks} onChange={(event) => updateRole(role.id, (current) => ({ ...current, canApproveTasks: event.target.checked }))} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改负责人 / 改日期
                      <input type="checkbox" checked={role.canReassignTasks || role.canChangeDeadline} onChange={(event) => updateRole(role.id, (current) => ({ ...current, canReassignTasks: event.target.checked, canChangeDeadline: event.target.checked }))} disabled={!canEdit} />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">岗位流程模板</p>
                <p className="text-[11px] text-gray-500 mt-1">每个关键岗位先录 2-3 条高频流程，后面 AI 才能判断“卡在流程哪一步”。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addProcessTemplate} disabled={!canEdit}>
                新增流程
              </button>
            </div>
            <div className="space-y-3">
              {value.roleProcessTemplates.map((template) => (
                <div key={template.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select
                      value={template.roleTemplateId || ''}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, roleTemplateId: event.target.value || null }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      <option value="">未绑定岗位</option>
                      {roleOptions.map((role) => (
                        <option key={role.id} value={role.id}>{role.name}</option>
                      ))}
                    </select>
                    <input
                      value={template.name}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, name: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="流程名称"
                      disabled={!canEdit}
                    />
                    <select
                      value={template.triggerType}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, triggerType: event.target.value as OrgWorkflowTriggerType }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      disabled={!canEdit}
                    >
                      {WORKFLOW_TRIGGER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      启用流程
                      <input
                        type="checkbox"
                        checked={template.active}
                        onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, active: event.target.checked }))}
                        disabled={!canEdit}
                      />
                    </label>
                  </div>
                  <input
                    value={template.triggerCondition}
                    onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, triggerCondition: event.target.value }))}
                    className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                    placeholder="触发条件，例如：周会结束后 / 客户会议结束后 / 收到新任务后"
                    disabled={!canEdit}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <input
                      value={template.collaborationStep}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, collaborationStep: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="哪一步需要协作"
                      disabled={!canEdit}
                    />
                    <input
                      value={template.approvalStep}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, approvalStep: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="哪一步需要审批"
                      disabled={!canEdit}
                    />
                    <input
                      value={template.outputArtifact}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, outputArtifact: event.target.value }))}
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                      placeholder="产出物"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <textarea
                      value={toMultiline(template.keySteps)}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, keySteps: fromMultiline(event.target.value) }))}
                      className="min-h-[92px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="关键步骤，每行一条"
                      disabled={!canEdit}
                    />
                    <textarea
                      value={toMultiline(template.commonBlockers)}
                      onChange={(event) => updateProcessTemplate(template.id, (current) => ({ ...current, commonBlockers: fromMultiline(event.target.value) }))}
                      className="min-h-[92px] rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] leading-6 outline-none resize-none"
                      placeholder="常见卡点，每行一条"
                      disabled={!canEdit}
                    />
                  </div>
                </div>
              ))}
              {value.roleProcessTemplates.length === 0 && (
                <div className="rounded-[22px] border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-400">
                  还没有岗位流程模板。建议先给高频岗位录入 2-3 条常见流程。
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'people' && (
        <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
          <div>
            <p className="text-[14px] font-bold text-gray-900">人员配置</p>
            <p className="text-[11px] text-gray-500 mt-1">一个人绑定一个主岗位，可额外附加项目角色和任务权限覆盖。</p>
          </div>
          <div className="space-y-3">
            {employeeOptions.map((employee) => {
              const binding = ensureBinding(employee);
              const roleCandidates = roleOptions.filter((role) => !binding.departmentId || role.departmentId === binding.departmentId || !role.departmentId);
              return (
                <div key={employee.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[13px] font-bold text-gray-900">{employee.fullName}</p>
                      <p className="text-[11px] text-gray-500 mt-1">{employee.email}</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-gray-500 border border-gray-200">{employee.primaryRole === 'admin' ? '管理员' : '员工'}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <select value={binding.departmentId || ''} onChange={(event) => updateBinding(employee, { departmentId: event.target.value || null, primaryRoleId: null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">未绑定部门</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select value={binding.primaryRoleId || ''} onChange={(event) => updateBinding(employee, { primaryRoleId: event.target.value || null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">未绑定岗位</option>
                      {roleCandidates.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                    <select value={binding.managerUserId || ''} onChange={(event) => updateBinding(employee, { managerUserId: event.target.value || null })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">无直属上级</option>
                      {employeeOptions
                        .filter((candidate) => candidate.id !== employee.id)
                        .map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>
                            {candidate.fullName}
                          </option>
                        ))}
                    </select>
                    <select value={binding.taskEditScope} onChange={(event) => updateBinding(employee, { taskEditScope: event.target.value as OrgTaskEditScope })} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {TASK_EDIT_SCOPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <input value={binding.currentFocus} onChange={(event) => updateBinding(employee, { currentFocus: event.target.value })} className="w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" placeholder="当前阶段主责方向" disabled={!canEdit} />
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      管理岗
                      <input type="checkbox" checked={binding.isManager} onChange={(event) => updateBinding(employee, { isManager: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      审批任务
                      <input type="checkbox" checked={binding.canApproveTasks} onChange={(event) => updateBinding(employee, { canApproveTasks: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改负责人
                      <input type="checkbox" checked={binding.canReassignTasks} onChange={(event) => updateBinding(employee, { canReassignTasks: event.target.checked })} disabled={!canEdit} />
                    </label>
                    <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                      改截止日
                      <input type="checkbox" checked={binding.canChangeDeadline} onChange={(event) => updateBinding(employee, { canChangeDeadline: event.target.checked })} disabled={!canEdit} />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'rules' && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">汇报线</p>
                <p className="text-[11px] text-gray-500 mt-1">单独结构化出来，后面 AI 才能判断瓶颈是出在谁的节点上。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addReportingLine} disabled={!canEdit}>
                新增汇报线
              </button>
            </div>
            <div className="space-y-3">
              {value.reportingLines.map((line) => (
                <div key={line.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <select value={line.managerUserId} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, managerUserId: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select value={line.reportUserId} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, reportUserId: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                    <select value={line.lineType} onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, lineType: event.target.value as 'business' | 'administrative' }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="business">业务汇报</option>
                      <option value="administrative">行政汇报</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                    {[
                      ['approvesTasks', '审批任务'],
                      ['canAdjustTasks', '改任务内容'],
                      ['canChangeDeadline', '改截止日'],
                      ['canReassignTasks', '改负责人'],
                      ['isCrossDepartmentApprover', '跨部门确认'],
                    ].map(([key, label]) => (
                      <label key={key} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                        {label}
                        <input
                          type="checkbox"
                          checked={Boolean(line[key as keyof typeof line])}
                          onChange={(event) => updateReportingLine(line.id, (current) => ({ ...current, [key]: event.target.checked }))}
                          disabled={!canEdit}
                        />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-gray-200 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[14px] font-bold text-gray-900">任务控制规则</p>
                <p className="text-[11px] text-gray-500 mt-1">先明确谁能改内容、改时间、改负责人，而不是一开始就上复杂流程引擎。</p>
              </div>
              <button type="button" className="rounded-2xl border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600" onClick={addRule} disabled={!canEdit}>
                新增规则
              </button>
            </div>
            <div className="space-y-3">
              {value.taskControlRules.map((rule) => (
                <div key={rule.id} className="rounded-[22px] border border-gray-200 bg-gray-50 p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input value={rule.name} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, name: event.target.value }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" placeholder="规则名称" disabled={!canEdit} />
                    <select value={rule.controlLevel} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, controlLevel: event.target.value as OrgTaskControlLevel }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      {CONTROL_LEVEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <select value={rule.departmentId || ''} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, departmentId: event.target.value || null }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">全机构</option>
                      {departmentOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.name}</option>
                      ))}
                    </select>
                    <select value={rule.defaultApproverUserId || ''} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, defaultApproverUserId: event.target.value || null }))} className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none" disabled={!canEdit}>
                      <option value="">无默认审批人</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>{employee.fullName}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    {[
                      ['contentEditableBy', '谁可改内容'],
                      ['deadlineEditableBy', '谁可改时间'],
                      ['ownerEditableBy', '谁可改负责人'],
                      ['cancellableBy', '谁可取消任务'],
                    ].map(([key, label]) => (
                      <select
                        key={key}
                        value={rule[key as keyof typeof rule] as string}
                        onChange={(event) => updateRule(rule.id, (current) => ({ ...current, [key]: event.target.value }))}
                        className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium outline-none"
                        disabled={!canEdit}
                      >
                        <option value="">{label}</option>
                        {RULE_SCOPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{label}：{option.label}</option>
                        ))}
                      </select>
                    ))}
                  </div>
                  <label className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-medium flex items-center justify-between">
                    修改任务时需要发起协作确认
                    <input type="checkbox" checked={rule.requireCollabConfirmation} onChange={(event) => updateRule(rule.id, (current) => ({ ...current, requireCollabConfirmation: event.target.checked }))} disabled={!canEdit} />
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
