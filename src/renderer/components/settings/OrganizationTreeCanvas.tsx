import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRightLeft,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  FileText,
  FolderKanban,
  GripVertical,
  LayoutGrid,
  PanelRightOpen,
  Plus,
  Sparkles,
  UserPlus,
  UserRound,
  Users,
  Workflow,
} from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentSettings,
  OrgEmployeeBindingSettings,
  OrgModelSettings,
  OrgRoleLevel,
  OrgRoleTemplateSettings,
  OrgTaskControlRuleSettings,
} from '../../../shared/types';
import { isAssignableOrganizationEmployee, isLegacyOrganizationPersonName } from '../../lib/organizationEmployeeFilters';

type Props = {
  value: OrgModelSettings;
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  onChange: (next: OrgModelSettings) => void;
};

type ViewMode = 'card' | 'collab';

type SelectedNode =
  | { type: 'organization' }
  | { type: 'department'; id: string }
  | { type: 'role'; id: string }
  | { type: 'member'; id: string };

type DragPayload =
  | { type: 'department'; id: string }
  | { type: 'role'; id: string }
  | { type: 'member'; id: string };

type DepartmentMeta = {
  node: OrgDepartmentSettings;
  roleIds: string[];
  memberIds: string[];
  planCount: number;
  completeness: number;
  missing: string[];
  ownerName: string;
  relatedProjects: string[];
  statusLabel: string;
};

type RoleMeta = {
  node: OrgRoleTemplateSettings;
  memberIds: string[];
  processCount: number;
  templateCount: number;
  completeness: number;
  missing: string[];
  descriptionStatus: string;
  processStatus: string;
  templateStatus: string;
  relatedProjects: string[];
};

type MemberMeta = {
  node: EmployeeRecord;
  binding: OrgEmployeeBindingSettings;
  roleName: string;
  departmentName: string;
  projectCount: number;
  workloadLabel: string;
  relatedProjects: string[];
};

const ROLE_LEVEL_OPTIONS: Array<{ value: OrgRoleLevel; label: string }> = [
  { value: 'organization_lead', label: '机构负责人' },
  { value: 'department_lead', label: '部门负责人' },
  { value: 'supervisor', label: '主管' },
  { value: 'employee', label: '员工' },
];

const VIEW_OPTIONS: Array<{ value: ViewMode; label: string; icon: typeof LayoutGrid }> = [
  { value: 'card', label: '卡片', icon: LayoutGrid },
  { value: 'collab', label: '协作关系', icon: ArrowRightLeft },
];

const DEPARTMENT_COLORS = ['#5B7BFE', '#0EA5E9', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6'];

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

function tint(hexColor: string, suffix = '18') {
  return `${hexColor}${suffix}`;
}

function moveBefore<T>(items: T[], fromIndex: number, toIndex: number) {
  if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
    return items;
  }
  const next = [...items];
  const [item] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, item);
  return next;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function pickWorkload(projectCount: number, isManager: boolean, hasFocus: boolean) {
  const score = projectCount + (isManager ? 2 : 0) + (hasFocus ? 1 : 0);
  if (score >= 5) return '高';
  if (score >= 3) return '中';
  return '轻';
}

function completionTone(percent: number) {
  if (percent >= 80) return 'text-emerald-700 bg-emerald-50 border-emerald-100';
  if (percent >= 55) return 'text-amber-700 bg-amber-50 border-amber-100';
  return 'text-slate-600 bg-slate-100 border-slate-200';
}

export function OrganizationTreeCanvas({ value, departmentCatalog, employees, canEdit, onChange }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('card');
  const [selectedNode, setSelectedNode] = useState<SelectedNode>({ type: 'organization' });
  const [dragHint, setDragHint] = useState<string | null>(null);
  const [memberDraftUserId, setMemberDraftUserId] = useState('');

  const activeEmployees = useMemo(
    () => employees.filter(isAssignableOrganizationEmployee),
    [employees],
  );
  const employeeById = useMemo(() => new Map(activeEmployees.map((item) => [item.id, item])), [activeEmployees]);
  const roleById = useMemo(() => new Map(value.roles.map((item) => [item.id, item])), [value.roles]);
  const bindingByUserId = useMemo(() => new Map(value.bindings.map((item) => [item.userId, item])), [value.bindings]);
  const activeDepartments = useMemo(() => value.departments.filter((item) => item.active !== false), [value.departments]);
  const activeRoles = useMemo(() => value.roles.filter((item) => item.active !== false), [value.roles]);
  const activePlans = useMemo(
    () => value.departmentPlans.filter((item) => item.status !== 'closed'),
    [value.departmentPlans],
  );
  const selectedOrganizationLeaderId = value.organization.leaderUserId && employeeById.has(value.organization.leaderUserId)
    ? value.organization.leaderUserId
    : '';

  const departmentOptions = useMemo(() => {
    if (activeDepartments.length > 0) {
      return activeDepartments.map((item) => ({ id: item.id, name: item.name, color: item.color }));
    }
    return departmentCatalog;
  }, [activeDepartments, departmentCatalog]);

  const rulesByRoleId = useMemo(() => {
    const mapping = new Map<string, OrgTaskControlRuleSettings[]>();
    value.taskControlRules
      .filter((item) => item.active !== false && item.roleTemplateId)
      .forEach((rule) => {
        const key = rule.roleTemplateId as string;
        const list = mapping.get(key) || [];
        list.push(rule);
        mapping.set(key, list);
      });
    return mapping;
  }, [value.taskControlRules]);

  const processByRoleId = useMemo(() => {
    const mapping = new Map<string, OrgModelSettings['roleProcessTemplates']>();
    value.roleProcessTemplates
      .filter((item) => item.active !== false && item.roleTemplateId)
      .forEach((template) => {
        const key = template.roleTemplateId as string;
        const list = mapping.get(key) || [];
        list.push(template);
        mapping.set(key, list);
      });
    return mapping;
  }, [value.roleProcessTemplates]);

  const relatedProjectsByDepartment = useMemo(() => {
    const mapping = new Map<string, string[]>();
    value.bindings.forEach((binding) => {
      if (!binding.departmentId || binding.projectRoleLabels.length === 0) return;
      const existing = new Set(mapping.get(binding.departmentId) || []);
      binding.projectRoleLabels.forEach((label) => existing.add(label));
      mapping.set(binding.departmentId, Array.from(existing));
    });
    return mapping;
  }, [value.bindings]);

  const departmentMetaMap = useMemo(() => {
    const mapping = new Map<string, DepartmentMeta>();
    activeDepartments.forEach((department) => {
      const roleIds = activeRoles.filter((role) => role.departmentId === department.id).map((role) => role.id);
      const memberIds = value.bindings
        .filter((binding) => binding.departmentId === department.id && employeeById.has(binding.userId))
        .map((binding) => binding.userId);
      const visibleLeaderName = department.leaderName?.trim() && !isLegacyOrganizationPersonName(department.leaderName)
        ? department.leaderName.trim()
        : '';
      const hasVisibleLeader = Boolean(visibleLeaderName) || Boolean(department.leaderUserId && employeeById.has(department.leaderUserId));
      const planCount = activePlans.filter((plan) => plan.departmentId === department.id).length;
      const missing: string[] = [];
      if (!hasVisibleLeader) missing.push('待绑定负责人');
      if (!department.mission.trim()) missing.push('待补部门使命');
      if (roleIds.length === 0) missing.push('待补岗位模板');
      if (memberIds.length === 0) missing.push('待补成员归属');
      if (planCount === 0) missing.push('待补部门计划');
      const completeness = clampPercent(((5 - missing.length) / 5) * 100);
      mapping.set(department.id, {
        node: department,
        roleIds,
        memberIds,
        planCount,
        completeness,
        missing,
        ownerName:
          visibleLeaderName ||
          (department.leaderUserId && employeeById.has(department.leaderUserId)
            ? employeeById.get(department.leaderUserId)?.fullName || '已绑定负责人'
            : '待绑定'),
        relatedProjects: relatedProjectsByDepartment.get(department.id) || [],
        statusLabel: department.active === false ? '停用' : completeness >= 80 ? '稳定' : completeness >= 55 ? '搭建中' : '待补全',
      });
    });
    return mapping;
  }, [activeDepartments, activePlans, activeRoles, employeeById, relatedProjectsByDepartment, value.bindings]);

  const roleMetaMap = useMemo(() => {
    const mapping = new Map<string, RoleMeta>();
    activeRoles.forEach((role) => {
      const memberIds = value.bindings
        .filter((binding) => binding.primaryRoleId === role.id && employeeById.has(binding.userId))
        .map((binding) => binding.userId);
      const processCount = (processByRoleId.get(role.id) || []).length;
      const templateCount = (rulesByRoleId.get(role.id) || []).length;
      const missing: string[] = [];
      if (!role.goal.trim() && role.responsibilities.length === 0) missing.push('待补岗位说明');
      if (processCount === 0) missing.push('待补流程模板');
      if (templateCount === 0) missing.push('待补任务模板');
      if (memberIds.length === 0) missing.push('待绑定成员');
      const completeness = clampPercent(((4 - missing.length) / 4) * 100);
      const relatedProjects = Array.from(
        new Set(
          memberIds.flatMap((userId) => bindingByUserId.get(userId)?.projectRoleLabels || []),
        ),
      );
      mapping.set(role.id, {
        node: role,
        memberIds,
        processCount,
        templateCount,
        completeness,
        missing,
        descriptionStatus: role.goal.trim() || role.responsibilities.length > 0 ? '已补说明' : '待补说明',
        processStatus: processCount > 0 ? `${processCount} 个流程` : '待补流程',
        templateStatus: templateCount > 0 ? `${templateCount} 个模板` : '待补模板',
        relatedProjects,
      });
    });
    return mapping;
  }, [activeRoles, bindingByUserId, employeeById, processByRoleId, rulesByRoleId, value.bindings]);

  const memberMetaMap = useMemo(() => {
    const mapping = new Map<string, MemberMeta>();
    activeEmployees.forEach((employee) => {
      const binding = bindingByUserId.get(employee.id);
      if (!binding) return;
      const roleName = binding.primaryRoleId ? roleById.get(binding.primaryRoleId)?.name || '未命名岗位' : '未绑定岗位';
      const departmentName = binding.departmentId
        ? departmentOptions.find((option) => option.id === binding.departmentId)?.name || '未命名部门'
        : '未绑定部门';
      const projectCount = binding.projectRoleLabels.length;
      mapping.set(employee.id, {
        node: employee,
        binding,
        roleName,
        departmentName,
        projectCount,
        workloadLabel: pickWorkload(projectCount, binding.isManager, Boolean(binding.currentFocus.trim())),
        relatedProjects: binding.projectRoleLabels,
      });
    });
    return mapping;
  }, [activeEmployees, bindingByUserId, departmentOptions, roleById]);

  const overallCompleteness = useMemo(() => {
    if (activeDepartments.length === 0) return 0;
    const total = activeDepartments.reduce((sum, department) => sum + (departmentMetaMap.get(department.id)?.completeness || 0), 0);
    return clampPercent(total / activeDepartments.length);
  }, [activeDepartments, departmentMetaMap]);

  const unboundEmployees = useMemo(
    () =>
      activeEmployees.filter((employee) => {
        const binding = bindingByUserId.get(employee.id);
        return !binding || !binding.primaryRoleId;
      }),
    [activeEmployees, bindingByUserId],
  );

  const addDepartment = () => {
    const nextIndex = value.departments.length;
    const color = DEPARTMENT_COLORS[nextIndex % DEPARTMENT_COLORS.length];
    onChange({
      ...value,
      departments: [
        ...value.departments,
        {
          id: nextUiId('department'),
          name: `新部门 ${nextIndex + 1}`,
          color,
          leaderUserId: null,
          leaderName: '',
          parentDepartmentId: null,
          mission: '',
          businessContext: '',
          teamContext: '',
          quarterPlan: {
            year: '',
            quarter: 'Q1',
            objective: '',
            deliverables: [],
            successMetrics: [],
            majorRisks: [],
            updatedAt: '',
          },
          quarterlyFocus: [],
          collaborationDepartmentIds: [],
          active: true,
          updatedAt: '',
        },
      ],
    });
  };

  const addRole = (departmentId?: string | null) => {
    onChange({
      ...value,
      roles: [
        ...value.roles,
        {
          id: nextUiId('role'),
          departmentId: departmentId || activeDepartments[0]?.id || null,
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

  const updateDepartment = (departmentId: string, patch: Partial<OrgDepartmentSettings>) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? { ...item, ...patch } : item)),
    });
  };

  const updateRole = (roleId: string, patch: Partial<OrgRoleTemplateSettings>) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? { ...item, ...patch } : item)),
    });
  };

  const updateBinding = (userId: string, patch: Partial<OrgEmployeeBindingSettings>) => {
    const existing = bindingByUserId.get(userId);
    const nextBinding: OrgEmployeeBindingSettings = {
      userId,
      departmentId: null,
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
      ...(existing || {}),
      ...patch,
    };
    onChange({
      ...value,
      bindings: existing
        ? value.bindings.map((item) => (item.userId === userId ? nextBinding : item))
        : [...value.bindings, nextBinding],
    });
  };

  const bindMemberToRole = (userId: string, roleId: string) => {
    const role = roleById.get(roleId);
    if (!role) return;
    updateBinding(userId, {
      primaryRoleId: roleId,
      departmentId: role.departmentId || null,
      isManager: role.isManager,
    });
  };

  const addMember = (roleId: string) => {
    const targetUserId = memberDraftUserId || unboundEmployees[0]?.id;
    if (!targetUserId) return;
    bindMemberToRole(targetUserId, roleId);
    setMemberDraftUserId('');
  };

  const createProcessTemplateForRole = (roleId: string) => {
    onChange({
      ...value,
      roleProcessTemplates: [
        ...value.roleProcessTemplates,
        {
          id: nextUiId('process'),
          roleTemplateId: roleId,
          name: `${roleById.get(roleId)?.name || '岗位'}标准流程`,
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

  const createRuleTemplateForRole = (roleId: string) => {
    const role = roleById.get(roleId);
    onChange({
      ...value,
      taskControlRules: [
        ...value.taskControlRules,
        {
          id: nextUiId('rule'),
          name: `${role?.name || '岗位'}任务模板`,
          controlLevel: role?.isManager ? 'department_control' : 'normal',
          departmentId: role?.departmentId || null,
          roleTemplateId: roleId,
          contentEditableBy: role?.isManager ? 'department_lead' : 'assignee',
          deadlineEditableBy: role?.isManager ? 'department_lead' : 'manager',
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

  const writeDragPayload = (event: React.DragEvent, payload: DragPayload) => {
    event.dataTransfer.setData('application/x-org-node', JSON.stringify(payload));
    event.dataTransfer.effectAllowed = 'move';
  };

  const readDragPayload = (event: React.DragEvent): DragPayload | null => {
    const raw = event.dataTransfer.getData('application/x-org-node');
    if (!raw) return null;
    try {
      return JSON.parse(raw) as DragPayload;
    } catch {
      return null;
    }
  };

  const reorderDepartments = (sourceId: string, targetId: string) => {
    const fromIndex = value.departments.findIndex((item) => item.id === sourceId);
    const toIndex = value.departments.findIndex((item) => item.id === targetId);
    onChange({ ...value, departments: moveBefore(value.departments, fromIndex, toIndex) });
  };

  const moveRoleToDepartment = (roleId: string, departmentId: string) => {
    const nextOrder = Math.max(
      0,
      ...value.roles.filter((item) => item.departmentId === departmentId).map((item) => item.sortOrder),
    );
    updateRole(roleId, { departmentId, sortOrder: nextOrder + 1 });
  };

  const moveMemberToRole = (userId: string, roleId: string) => {
    bindMemberToRole(userId, roleId);
  };

  const handleDepartmentDrop = (event: React.DragEvent, departmentId: string) => {
    event.preventDefault();
    const payload = readDragPayload(event);
    setDragHint(null);
    if (!payload) return;
    if (payload.type === 'department' && payload.id !== departmentId) {
      reorderDepartments(payload.id, departmentId);
    }
    if (payload.type === 'role') {
      moveRoleToDepartment(payload.id, departmentId);
    }
  };

  const handleRoleDrop = (event: React.DragEvent, roleId: string) => {
    event.preventDefault();
    const payload = readDragPayload(event);
    setDragHint(null);
    if (!payload) return;
    if (payload.type === 'member') {
      moveMemberToRole(payload.id, roleId);
    }
  };

  const selectedDepartmentMeta =
    selectedNode.type === 'department' ? departmentMetaMap.get(selectedNode.id) || null : null;
  const selectedRoleMeta = selectedNode.type === 'role' ? roleMetaMap.get(selectedNode.id) || null : null;
  const selectedMemberMeta = selectedNode.type === 'member' ? memberMetaMap.get(selectedNode.id) || null : null;

  return (
    <div className="rounded-[32px] border border-gray-100 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-gray-100 bg-[linear-gradient(135deg,rgba(91,123,254,0.08),rgba(255,255,255,0.96)_40%,rgba(14,165,233,0.06))] px-6 py-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-[11px] font-bold text-[#5B7BFE] shadow-sm">
              <Sparkles size={12} />
              AI 可读的组织建模画布
            </div>
            <h3 className="mt-4 text-[22px] font-bold tracking-tight text-gray-900">组织建模画布</h3>
            <p className="mt-2 max-w-3xl text-[13px] leading-6 text-gray-500">
              把组织、部门、岗位、成员建成结构化底盘。项目暂时不入画布，先在右侧详情里作为关联项目展示，后续 AI 会直接读取这份层级模型。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {VIEW_OPTIONS.map((option) => {
              const Icon = option.icon;
              const active = viewMode === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setViewMode(option.value)}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-bold transition ${
                    active ? 'bg-[#5B7BFE] text-white shadow-[0_10px_24px_rgba(91,123,254,0.24)]' : 'border border-gray-200 bg-white text-gray-600'
                  }`}
                >
                  <Icon size={14} />
                  {option.label}
                </button>
              );
            })}
            <button
              type="button"
              onClick={addDepartment}
              disabled={!canEdit}
              className="inline-flex items-center gap-2 rounded-full border border-[#DCE4FF] bg-white px-4 py-2 text-[12px] font-bold text-[#4A63CF] shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={14} />
              新增部门
            </button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          {[
            { label: '部门', value: `${activeDepartments.length}` },
            { label: '岗位', value: `${activeRoles.length}` },
            { label: '成员', value: `${value.bindings.filter((item) => item.primaryRoleId && employeeById.has(item.userId)).length}` },
            { label: '计划数', value: `${activePlans.length}` },
            { label: '完整度', value: `${overallCompleteness}%` },
            { label: '缺口', value: `${activeDepartments.reduce((sum, department) => sum + (departmentMetaMap.get(department.id)?.missing.length || 0), 0)}` },
          ].map((stat) => (
            <div key={stat.label} className="rounded-[22px] border border-white/80 bg-white/80 px-4 py-4 shadow-sm">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-gray-400">{stat.label}</p>
              <p className="mt-2 text-[24px] font-bold tracking-tight text-gray-900">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 border-r border-gray-100 bg-[#FBFCFF] p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-[12px] leading-6 text-gray-500">
              {viewMode === 'card' ? '卡片视图用于快速盘点结构与缺口。' : '协作关系视图预留给后续跨部门网络图。'}
            </div>
            {dragHint ? (
              <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#5B7BFE]">{dragHint}</span>
            ) : (
              <span className="rounded-full bg-gray-100 px-3 py-1.5 text-[11px] font-bold text-gray-500">结构化节点字段已启用</span>
            )}
          </div>

          <button
            type="button"
            onClick={() => setSelectedNode({ type: 'organization' })}
            className={`w-full rounded-[28px] border px-5 py-5 text-left shadow-sm transition ${
              selectedNode.type === 'organization' ? 'border-[#B9CAFF] bg-white' : 'border-gray-200 bg-white'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#4A63CF]">
                  <Building2 size={12} />
                  组织
                </div>
                <h4 className="mt-3 text-[20px] font-bold tracking-tight text-gray-900">
                  {value.organization.name.trim() || '当前组织'}
                </h4>
                <p className="mt-2 text-[13px] leading-6 text-gray-500">
                  {value.organization.annualGoal.trim() || '待补组织目标、今年计划与项目意图，后续任务识别会按这层背景理解。'}
                </p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-bold ${completionTone(overallCompleteness)}`}>
                {overallCompleteness}% 完整
              </span>
            </div>
          </button>

          {viewMode === 'collab' ? (
            <div className="mt-6 rounded-[28px] border border-dashed border-gray-200 bg-white px-6 py-12 text-center">
              <ArrowRightLeft size={24} className="mx-auto text-gray-300" />
              <p className="mt-4 text-[16px] font-bold text-gray-900">协作关系视图预留中</p>
              <p className="mt-2 text-[12px] leading-6 text-gray-500">
                下一步会把跨部门依赖、负责人关系和协作频次拉成关系网。当前先在卡片视图和详情抽屉里完成结构建模。
              </p>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-4 2xl:grid-cols-2">
              {activeDepartments.map((department) => {
                const meta = departmentMetaMap.get(department.id);
                if (!meta) return null;
                return (
                  <button
                    key={department.id}
                    type="button"
                    onClick={() => setSelectedNode({ type: 'department', id: department.id })}
                    draggable={canEdit}
                    onDragStart={(event) => writeDragPayload(event, { type: 'department', id: department.id })}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setDragHint('松手即可把部门排到这里');
                    }}
                    onDrop={(event) => handleDepartmentDrop(event, department.id)}
                    onDragLeave={() => setDragHint(null)}
                    className={`rounded-[28px] border bg-white p-5 text-left shadow-sm transition ${
                      selectedNode.type === 'department' && selectedNode.id === department.id
                        ? 'border-[#B9CAFF]'
                        : 'border-gray-200 hover:border-blue-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div
                          className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-bold"
                          style={{ backgroundColor: tint(department.color), color: department.color }}
                        >
                          <GripVertical size={12} />
                          {department.name}
                        </div>
                        <p className="mt-3 text-[14px] font-bold text-gray-900">{meta.ownerName}</p>
                        <p className="mt-1 text-[12px] leading-6 text-gray-500">
                          {department.mission.trim() || '待补部门使命、负责人与本周计划。'}
                        </p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-[11px] font-bold ${completionTone(meta.completeness)}`}>
                        {meta.completeness}%
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-4 gap-3 text-center">
                      {[
                        ['岗位', meta.roleIds.length],
                        ['成员', meta.memberIds.length],
                        ['计划', meta.planCount],
                        ['缺口', meta.missing.length],
                      ].map(([label, count]) => (
                        <div key={label} className="rounded-2xl bg-gray-50 px-3 py-3">
                          <p className="text-[11px] text-gray-500">{label}</p>
                          <p className="mt-1 text-[16px] font-bold text-gray-900">{count}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${completionTone(meta.completeness)}`}>
                        {meta.statusLabel}
                      </span>
                      {meta.missing.slice(0, 2).map((item) => (
                        <span key={item} className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">
                          {item}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <aside className="border-t border-gray-100 bg-white xl:border-t-0">
          <div className="sticky top-0 flex h-full flex-col">
            <div className="border-b border-gray-100 px-5 py-4">
              <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">
                <PanelRightOpen size={13} />
                右侧详情抽屉
              </div>
              <p className="mt-2 text-[13px] leading-6 text-gray-500">
                点击任意节点即可编辑字段、补流程、补模板、绑定负责人，并查看关联项目。
              </p>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5">
              {selectedNode.type === 'organization' ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Building2}
                    title={value.organization.name.trim() || '当前组织'}
                    subtitle="组织节点"
                    tone="blue"
                  />
                  <DrawerTextarea
                    label="组织名称"
                    value={value.organization.name}
                    disabled={!canEdit}
                    placeholder="组织名称"
                    onChange={(next) =>
                      onChange({ ...value, organization: { ...value.organization, name: next } })
                    }
                  />
                  <DrawerTextarea
                    label="年度目标"
                    value={value.organization.annualGoal}
                    disabled={!canEdit}
                    placeholder="年度目标"
                    multiline
                    onChange={(next) =>
                      onChange({ ...value, organization: { ...value.organization, annualGoal: next } })
                    }
                  />
                  <DrawerTextarea
                    label="季度重点"
                    value={toMultiline(value.organization.quarterlyFocus)}
                    disabled={!canEdit}
                    placeholder="每行一条季度重点"
                    multiline
                    onChange={(next) =>
                      onChange({
                        ...value,
                        organization: { ...value.organization, quarterlyFocus: fromMultiline(next) },
                      })
                    }
                  />
	                  <label className="space-y-2">
	                    <span className="text-[12px] font-bold text-gray-700">组织负责人</span>
	                    <select
	                      value={selectedOrganizationLeaderId}
                      onChange={(event) =>
                        onChange({
                          ...value,
                          organization: {
                            ...value.organization,
                            leaderUserId: event.target.value || null,
                            managementUserIds: event.target.value
                              ? Array.from(new Set([...value.organization.managementUserIds, event.target.value]))
                              : value.organization.managementUserIds,
                          },
                        })
                      }
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">请选择负责人</option>
                      {activeEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerInfoBlock
                    title="组织模型完整度"
                    helper="组织根节点主要负责承接名称、目标和负责人。部门以下结构会继续细化岗位、成员、流程与计划。"
                    items={[
                      value.organization.name.trim() ? '组织名称已补齐' : '待补组织名称',
	                      selectedOrganizationLeaderId ? '负责人已绑定' : '待绑定负责人',
                      value.organization.annualGoal.trim() || value.organization.quarterlyFocus.length > 0 ? '目标语境已补齐' : '待补年度目标 / 季度重点',
                    ]}
                  />
                </div>
              ) : null}

              {selectedDepartmentMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Building2}
                    title={selectedDepartmentMeta.node.name}
                    subtitle="部门节点"
                    tone="emerald"
                  />
                  <DrawerTextarea
                    label="部门名称"
                    value={selectedDepartmentMeta.node.name}
                    disabled={!canEdit}
                    placeholder="部门名称"
                    onChange={(next) => updateDepartment(selectedDepartmentMeta.node.id, { name: next })}
                  />
	                  <label className="space-y-2">
	                    <span className="text-[12px] font-bold text-gray-700">负责人</span>
	                    <select
	                      value={selectedDepartmentMeta.node.leaderUserId && employeeById.has(selectedDepartmentMeta.node.leaderUserId) ? selectedDepartmentMeta.node.leaderUserId : ''}
                      onChange={(event) =>
                        updateDepartment(selectedDepartmentMeta.node.id, {
                          leaderUserId: event.target.value || null,
                          leaderName: event.target.value ? employeeById.get(event.target.value)?.fullName || '' : '',
                        })
                      }
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">请选择负责人</option>
                      {activeEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerTextarea
                    label="部门使命"
                    value={selectedDepartmentMeta.node.mission}
                    disabled={!canEdit}
                    placeholder="部门使命与业务定位"
                    multiline
                    onChange={(next) => updateDepartment(selectedDepartmentMeta.node.id, { mission: next })}
                  />
                  <DrawerTextarea
                    label="季度重点"
                    value={toMultiline(selectedDepartmentMeta.node.quarterlyFocus)}
                    disabled={!canEdit}
                    placeholder="每行一条重点"
                    multiline
                    onChange={(next) =>
                      updateDepartment(selectedDepartmentMeta.node.id, { quarterlyFocus: fromMultiline(next) })
                    }
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <InfoMetricCard label="岗位数" value={`${selectedDepartmentMeta.roleIds.length}`} />
                    <InfoMetricCard label="成员数" value={`${selectedDepartmentMeta.memberIds.length}`} />
                    <InfoMetricCard label="计划数" value={`${selectedDepartmentMeta.planCount}`} />
                    <InfoMetricCard label="完整度" value={`${selectedDepartmentMeta.completeness}%`} />
                  </div>
                  <DrawerActionRow
                    actions={[
                      {
                        label: '新增岗位',
                        icon: Plus,
                        onClick: () => addRole(selectedDepartmentMeta.node.id),
                        disabled: !canEdit,
                      },
                    ]}
                  />
                  <DrawerInfoBlock
                    title="缺失项提示"
                    helper="部门节点会优先检查负责人、使命、岗位、成员与计划覆盖。"
                    items={
                      selectedDepartmentMeta.missing.length > 0
                        ? selectedDepartmentMeta.missing
                        : ['该部门的负责人、岗位、成员与计划已经基本齐全']
                    }
                  />
                  <DrawerInfoBlock
                    title="关联项目"
                    helper="项目暂不入树，先在这里聚合展示部门当前已绑定的项目标签。"
                    items={
                      selectedDepartmentMeta.relatedProjects.length > 0
                        ? selectedDepartmentMeta.relatedProjects
                        : ['当前暂无关联项目']
                    }
                    icon={FolderKanban}
                  />
                </div>
              ) : null}

              {selectedRoleMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={BriefcaseBusiness}
                    title={selectedRoleMeta.node.name || '未命名岗位'}
                    subtitle="岗位节点"
                    tone="violet"
                  />
                  <DrawerTextarea
                    label="岗位名称"
                    value={selectedRoleMeta.node.name}
                    disabled={!canEdit}
                    placeholder="岗位名称"
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { name: next })}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">归属部门</span>
                      <select
                        value={selectedRoleMeta.node.departmentId || ''}
                        onChange={(event) => updateRole(selectedRoleMeta.node.id, { departmentId: event.target.value || null })}
                        disabled={!canEdit}
                        className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      >
                        <option value="">未绑定部门</option>
                        {departmentOptions.map((department) => (
                          <option key={department.id} value={department.id}>
                            {department.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2">
                      <span className="text-[12px] font-bold text-gray-700">岗位级别</span>
                      <select
                        value={selectedRoleMeta.node.level}
                        onChange={(event) => updateRole(selectedRoleMeta.node.id, { level: event.target.value as OrgRoleLevel })}
                        disabled={!canEdit}
                        className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                      >
                        {ROLE_LEVEL_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <DrawerTextarea
                    label="岗位目标"
                    value={selectedRoleMeta.node.goal}
                    disabled={!canEdit}
                    placeholder="一句话说明岗位目标"
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { goal: next })}
                  />
                  <DrawerTextarea
                    label="岗位职责"
                    value={toMultiline(selectedRoleMeta.node.responsibilities)}
                    disabled={!canEdit}
                    placeholder="每行一条岗位职责"
                    multiline
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { responsibilities: fromMultiline(next) })}
                  />
                  <DrawerTextarea
                    label="不该长期承担的事务"
                    value={toMultiline(selectedRoleMeta.node.shouldAvoid)}
                    disabled={!canEdit}
                    placeholder="每行一条"
                    multiline
                    onChange={(next) => updateRole(selectedRoleMeta.node.id, { shouldAvoid: fromMultiline(next) })}
                  />
                  <div className="grid grid-cols-3 gap-3">
                    <InfoMetricCard label="成员数" value={`${selectedRoleMeta.memberIds.length}`} />
                    <InfoMetricCard label="流程状态" value={selectedRoleMeta.processStatus} />
                    <InfoMetricCard label="模板状态" value={selectedRoleMeta.templateStatus} />
                  </div>
                  <DrawerActionRow
                    actions={[
                      {
                        label: '补流程',
                        icon: Workflow,
                        onClick: () => createProcessTemplateForRole(selectedRoleMeta.node.id),
                        disabled: !canEdit,
                      },
                      {
                        label: '补模板',
                        icon: FileText,
                        onClick: () => createRuleTemplateForRole(selectedRoleMeta.node.id),
                        disabled: !canEdit,
                      },
                      {
                        label: '新增成员',
                        icon: UserPlus,
                        onClick: () => addMember(selectedRoleMeta.node.id),
                        disabled: !canEdit || unboundEmployees.length === 0,
                      },
                    ]}
                  />
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">绑定成员</span>
                    <select
                      value={memberDraftUserId}
                      onChange={(event) => setMemberDraftUserId(event.target.value)}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">选择未绑定成员</option>
                      {unboundEmployees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.fullName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <DrawerInfoBlock
                    title="缺失项提示"
                    helper="岗位节点主要看说明、流程模板、任务模板和成员覆盖。"
                    items={selectedRoleMeta.missing.length > 0 ? selectedRoleMeta.missing : ['该岗位的说明、流程和模板都已补齐']}
                  />
                  <DrawerInfoBlock
                    title="关联项目"
                    helper="这里先展示与该岗位成员绑定的项目标签。"
                    items={selectedRoleMeta.relatedProjects.length > 0 ? selectedRoleMeta.relatedProjects : ['当前暂无关联项目']}
                    icon={FolderKanban}
                  />
                </div>
              ) : null}

              {selectedMemberMeta ? (
                <div className="space-y-5">
                  <DrawerHeader
                    icon={Users}
                    title={selectedMemberMeta.node.fullName}
                    subtitle="成员节点"
                    tone="amber"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <InfoMetricCard label="当前岗位" value={selectedMemberMeta.roleName} />
                    <InfoMetricCard label="任务负荷" value={selectedMemberMeta.workloadLabel} />
                    <InfoMetricCard label="项目数" value={`${selectedMemberMeta.projectCount}`} />
                    <InfoMetricCard label="部门" value={selectedMemberMeta.departmentName} />
                  </div>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">岗位归属</span>
                    <select
                      value={selectedMemberMeta.binding.primaryRoleId || ''}
                      onChange={(event) => {
                        const roleId = event.target.value || null;
                        const role = roleId ? roleById.get(roleId) : null;
                        updateBinding(selectedMemberMeta.node.id, {
                          primaryRoleId: roleId,
                          departmentId: role?.departmentId || null,
                        });
                      }}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">未绑定岗位</option>
                      {activeRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[12px] font-bold text-gray-700">直属上级</span>
                    <select
                      value={selectedMemberMeta.binding.managerUserId || ''}
                      onChange={(event) => updateBinding(selectedMemberMeta.node.id, { managerUserId: event.target.value || null })}
                      disabled={!canEdit}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
                    >
                      <option value="">未指定上级</option>
                      {activeEmployees
                        .filter((employee) => employee.id !== selectedMemberMeta.node.id)
                        .map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {employee.fullName}
                          </option>
                        ))}
                    </select>
                  </label>
                  <DrawerTextarea
                    label="当前重心"
                    value={selectedMemberMeta.binding.currentFocus}
                    disabled={!canEdit}
                    placeholder="当前主责方向"
                    onChange={(next) => updateBinding(selectedMemberMeta.node.id, { currentFocus: next })}
                  />
                  <DrawerTextarea
                    label="关联项目"
                    value={toMultiline(selectedMemberMeta.binding.projectRoleLabels)}
                    disabled={!canEdit}
                    placeholder="每行一个项目标签"
                    multiline
                    onChange={(next) => updateBinding(selectedMemberMeta.node.id, { projectRoleLabels: fromMultiline(next) })}
                  />
                  <DrawerInfoBlock
                    title="节点提示"
                    helper="成员节点先看岗位归属、任务负荷和项目数量。后续 AI 会基于这些字段判断成员是否超载、是否需要协作补位。"
                    items={[
                      selectedMemberMeta.binding.primaryRoleId ? '岗位已绑定' : '待绑定岗位',
                      selectedMemberMeta.binding.managerUserId ? '直属上级已绑定' : '待绑定直属上级',
                      selectedMemberMeta.projectCount > 0 ? `已关联 ${selectedMemberMeta.projectCount} 个项目` : '当前暂无关联项目',
                    ]}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function DepartmentStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-gray-400">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-gray-900">{value}</p>
    </div>
  );
}

function InfoMetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-gray-200 bg-gray-50 px-4 py-3">
      <p className="text-[11px] font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-gray-900">{value}</p>
    </div>
  );
}

function DrawerTextarea({
  label,
  value,
  placeholder,
  disabled,
  multiline = false,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  disabled: boolean;
  multiline?: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="text-[12px] font-bold text-gray-700">{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="min-h-[104px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
        />
      ) : (
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium outline-none"
        />
      )}
    </label>
  );
}

function DrawerHeader({
  icon: Icon,
  title,
  subtitle,
  tone,
}: {
  icon: typeof Building2;
  title: string;
  subtitle: string;
  tone: 'blue' | 'emerald' | 'violet' | 'amber';
}) {
  const toneClass =
    tone === 'emerald'
      ? 'bg-emerald-50 text-emerald-600'
      : tone === 'violet'
      ? 'bg-violet-50 text-violet-600'
      : tone === 'amber'
      ? 'bg-amber-50 text-amber-600'
      : 'bg-blue-50 text-[#5B7BFE]';
  return (
    <div className="rounded-[24px] border border-gray-100 bg-gray-50/70 p-4">
      <div className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl shadow-sm ${toneClass}`}>
        <Icon size={18} />
      </div>
      <p className="mt-3 text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">{subtitle}</p>
      <h4 className="mt-1 text-[20px] font-bold tracking-tight text-gray-900">{title}</h4>
    </div>
  );
}

function DrawerInfoBlock({
  title,
  helper,
  items,
  icon: Icon = AlertTriangle,
}: {
  title: string;
  helper: string;
  items: string[];
  icon?: typeof AlertTriangle;
}) {
  return (
    <div className="rounded-[24px] border border-gray-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <div className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-gray-50 text-gray-500">
          <Icon size={16} />
        </div>
        <div>
          <h5 className="text-[13px] font-bold text-gray-900">{title}</h5>
          <p className="mt-1 text-[12px] leading-6 text-gray-500">{helper}</p>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <div key={item} className="flex items-start gap-2 rounded-2xl bg-gray-50 px-3 py-3 text-[12px] text-gray-700">
            {item.startsWith('待') || item.startsWith('当前暂无') ? (
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
            ) : (
              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-500" />
            )}
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DrawerActionRow({
  actions,
}: {
  actions: Array<{ label: string; icon: typeof Plus; onClick: () => void; disabled?: boolean }>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            type="button"
            onClick={action.onClick}
            disabled={action.disabled}
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#DCE4FF] bg-white px-4 py-3 text-[12px] font-bold text-[#4A63CF] shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon size={14} />
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
