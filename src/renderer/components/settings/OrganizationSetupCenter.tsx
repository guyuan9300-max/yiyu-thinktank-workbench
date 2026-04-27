import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Building2, Check, ChevronLeft, Copy, Plus, Save, Users, X } from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentSettings,
  OrgEmployeeBindingSettings,
  OrgModelSettings,
  OrgQuarterKey,
  OrgRoleTemplateSettings,
  OrganizationDnaModule,
} from '../../../shared/types';
import { buildDepartmentInviteCode } from '../../../shared/departmentInvite';

type LinkedSection = 'org_dna' | 'tasks' | 'handbook';

type Props = {
  value: OrgModelSettings;
  organizationDnaModules: OrganizationDnaModule[];
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  activeWeekLabel: string;
  initialAdvancedTab?: string | null;
  onChange: (next: OrgModelSettings) => void;
  onSave: (next?: OrgModelSettings) => Promise<void> | void;
  onOpenSection: (section: LinkedSection) => void;
};

type ActiveView = 'tree' | 'codes';

type EditableField = 'name' | 'leadName';

type TreeDepartmentNode = {
  id: string;
  name: string;
  type: 'department';
  leadName: string;
  color: string;
  children: TreePositionNode[];
};

type TreeOrgNode = {
  id: string;
  name: string;
  type: 'org';
  children: TreeDepartmentNode[];
};

type TreePositionNode = {
  id: string;
  name: string;
  type: 'position';
  departmentId: string | null;
};

type LineDefinition = {
  id: string;
  path: string;
};

const DEPARTMENT_COLORS = ['#5B7BFE', '#0EA5E9', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6'];

function nextUiId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function buildEmptyQuarterPlan(): OrgDepartmentSettings['quarterPlan'] {
  return {
    year: '',
    quarter: 'Q1' satisfies OrgQuarterKey,
    objective: '',
    deliverables: [],
    successMetrics: [],
    majorRisks: [],
    updatedAt: '',
  };
}

function emptyBinding(userId: string): OrgEmployeeBindingSettings {
  return {
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
  };
}

function tint(hexColor: string, suffix = '12') {
  return `${hexColor}${suffix}`;
}

function deriveTree(
  value: OrgModelSettings,
  fallbackOrganizationName: string,
): TreeOrgNode {
  const activeDepartments = value.departments.filter((item) => item.active !== false);
  const activeRoles = value.roles
    .filter((item) => item.active !== false)
    .sort((left, right) => left.sortOrder - right.sortOrder);

  return {
    id: value.organization.organizationId || 'organization-root',
    name: value.organization.name.trim() || fallbackOrganizationName,
    type: 'org',
    children: activeDepartments.map((department) => ({
      id: department.id,
      name: department.name || '未命名部门',
      type: 'department',
      leadName: department.leaderName?.trim() || '待设置',
      color: department.color || DEPARTMENT_COLORS[0],
      children: activeRoles
        .filter((role) => role.departmentId === department.id)
        .map((role) => ({
          id: role.id,
          name: role.name || '未命名岗位',
          type: 'position',
          departmentId: department.id,
        })),
    })),
  };
}

function computeStats(
  value: OrgModelSettings,
  employees: EmployeeRecord[],
) {
  const activeDepartments = value.departments.filter((item) => item.active !== false);
  const activeRoles = value.roles.filter((item) => item.active !== false);
  const activePlans = value.departmentPlans.filter((item) => item.status !== 'closed');
  const activeEmployees = employees.filter((item) => item.accountStatus !== 'disabled');
  const boundMembers = value.bindings.filter((item) => item.primaryRoleId).length;
  const memberCount = Math.max(boundMembers, activeEmployees.filter((item) => item.accountStatus === 'approved' || item.primaryRole === 'admin').length);

  const completenessByDepartment = activeDepartments.map((department) => {
    const roleCount = activeRoles.filter((role) => role.departmentId === department.id).length;
    const planCount = activePlans.filter((plan) => plan.departmentId === department.id).length;
    const memberIds = value.bindings.filter((binding) => binding.departmentId === department.id && binding.primaryRoleId).length;
    const missing = [
      !(department.leaderUserId || department.leaderName?.trim()),
      !department.mission.trim(),
      roleCount === 0,
      memberIds === 0,
      planCount === 0,
    ].filter(Boolean).length;
    return clampPercent(((5 - missing) / 5) * 100);
  });

  const completeness = activeDepartments.length > 0
    ? clampPercent(completenessByDepartment.reduce((sum, item) => sum + item, 0) / activeDepartments.length)
    : 0;

  return [
    { label: '部门', value: `${activeDepartments.length}` },
    { label: '岗位', value: `${activeRoles.length}` },
    { label: '成员', value: `${memberCount}` },
    { label: '计划数', value: `${activePlans.length}` },
    { label: '完整度', value: `${completeness}%` },
  ];
}

function departmentColor(index: number, existing?: string | null) {
  if (existing && existing.trim()) return existing;
  return DEPARTMENT_COLORS[index % DEPARTMENT_COLORS.length];
}

function pickDepartmentLeadRoleId(
  roles: OrgRoleTemplateSettings[],
  departmentId: string,
  fallbackRoleId?: string | null,
) {
  const departmentRoles = roles.filter((role) => role.active !== false && role.departmentId === departmentId);
  const explicitLead = departmentRoles.find((role) => role.level === 'department_lead');
  if (explicitLead) return explicitLead.id;
  const managerRole = departmentRoles.find((role) => role.isManager);
  if (managerRole) return managerRole.id;
  if (fallbackRoleId && departmentRoles.some((role) => role.id === fallbackRoleId)) return fallbackRoleId;
  return fallbackRoleId || null;
}

export function OrganizationSetupCenter({
  value,
  organizationDnaModules,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  onChange,
  onSave,
}: Props) {
  void organizationDnaModules;
  void departmentCatalog;

  const [activeView, setActiveView] = useState<ActiveView>('tree');
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<EditableField | null>(null);
  const [editingText, setEditingText] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [bulkInviteCopied, setBulkInviteCopied] = useState(false);
  const [lines, setLines] = useState<LineDefinition[]>([]);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bulkInviteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const tree = useMemo(
    () => deriveTree(value, '当前组织'),
    [value],
  );
  const stats = useMemo(() => computeStats(value, employees), [employees, value]);
  const activeDepartments = useMemo(() => value.departments.filter((item) => item.active !== false), [value.departments]);
  const activeRoles = useMemo(() => value.roles.filter((item) => item.active !== false), [value.roles]);
  const approvedEmployees = useMemo(
    () => employees.filter((item) => item.accountStatus === 'approved' || item.primaryRole === 'admin'),
    [employees],
  );
  const bindingsByDepartmentId = useMemo(() => {
    const mapping = new Map<string, OrgEmployeeBindingSettings[]>();
    value.bindings.forEach((binding) => {
      if (!binding.departmentId) return;
      const list = mapping.get(binding.departmentId) || [];
      list.push(binding);
      mapping.set(binding.departmentId, list);
    });
    return mapping;
  }, [value.bindings]);

  const employeeById = useMemo(() => new Map(employees.map((item) => [item.id, item])), [employees]);
  const organizationName = value.organization.name.trim() || tree.name || '当前组织';
  const organizationLeader = value.organization.leaderUserId
    ? employeeById.get(value.organization.leaderUserId) || null
    : null;
  const organizationLeaderTitle = organizationLeader?.jobTitle?.trim() || '负责人';
  const organizationLeaderSummary = organizationLeader
    ? `${organizationLeaderTitle} · ${organizationLeader.fullName}`
    : '待绑定负责人';
  const bulkInviteText = useMemo(() => {
    const linesOfText = tree.children.map((department, index) => {
      const inviteCode = buildDepartmentInviteCode(department.id, {
        organizationName,
        departmentName: department.name,
        order: index,
      });
      return `${department.name}：${inviteCode}`;
    });
    return [
      `${organizationName} 各部门邀请码`,
      '大家注册时找到自己部门的邀请码填入即可。',
      ...linesOfText,
    ].join('\n');
  }, [organizationName, tree.children]);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = setTimeout(() => setToast(null), 2400);
  }, []);

  useEffect(() => () => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    if (bulkInviteTimerRef.current) {
      clearTimeout(bulkInviteTimerRef.current);
    }
  }, []);

  const handleCopyAllInvites = useCallback(async () => {
    if (tree.children.length === 0) {
      showToast('还没有部门邀请码可复制');
      return;
    }
    try {
      await navigator.clipboard.writeText(bulkInviteText);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = bulkInviteText;
      textArea.style.position = 'absolute';
      textArea.style.left = '-99999px';
      textArea.style.top = '-99999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
    setBulkInviteCopied(true);
    if (bulkInviteTimerRef.current) {
      clearTimeout(bulkInviteTimerRef.current);
    }
    bulkInviteTimerRef.current = window.setTimeout(() => setBulkInviteCopied(false), 1800);
    showToast('已复制全部部门邀请码');
  }, [bulkInviteText, showToast, tree.children.length]);

  const updateDepartment = useCallback((departmentId: string, patch: Partial<OrgDepartmentSettings>) => {
    onChange({
      ...value,
      departments: value.departments.map((item) => (item.id === departmentId ? { ...item, ...patch } : item)),
    });
  }, [onChange, value]);

  const updateOrganization = useCallback((patch: Partial<OrgModelSettings['organization']>) => {
    onChange({
      ...value,
      organization: {
        ...value.organization,
        ...patch,
      },
    });
  }, [onChange, value]);

  const updateRole = useCallback((roleId: string, patch: Partial<OrgRoleTemplateSettings>) => {
    onChange({
      ...value,
      roles: value.roles.map((item) => (item.id === roleId ? { ...item, ...patch } : item)),
    });
  }, [onChange, value]);

  const handleSaveEdit = useCallback(() => {
    const nextValue = editingText.trim();
    if (!editingNodeId || !editingField) {
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    if (!nextValue) {
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    if (editingNodeId === tree.id && editingField === 'name') {
      updateOrganization({ name: nextValue });
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    const targetDepartment = activeDepartments.find((item) => item.id === editingNodeId);
    if (targetDepartment) {
      if (editingField === 'name') {
        updateDepartment(editingNodeId, { name: nextValue });
      } else {
        updateDepartment(editingNodeId, { leaderName: nextValue, leaderUserId: null });
      }
      setEditingNodeId(null);
      setEditingField(null);
      return;
    }

    const targetRole = activeRoles.find((item) => item.id === editingNodeId);
    if (targetRole && editingField === 'name') {
      updateRole(editingNodeId, { name: nextValue });
    }

    setEditingNodeId(null);
    setEditingField(null);
  }, [activeDepartments, activeRoles, editingField, editingNodeId, editingText, tree.id, updateDepartment, updateOrganization, updateRole]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      handleSaveEdit();
    }
    if (event.key === 'Escape') {
      setEditingNodeId(null);
      setEditingField(null);
    }
  }, [handleSaveEdit]);

  const startEditing = useCallback((nodeId: string, field: EditableField, currentText: string) => {
    if (!canEdit) return;
    setEditingNodeId(nodeId);
    setEditingField(field);
    setEditingText(currentText || '');
  }, [canEdit]);

  const handleSelectDepartmentLead = useCallback((departmentId: string, userId: string) => {
    if (!canEdit) return;
    if (userId === '__manual__') {
      const department = activeDepartments.find((item) => item.id === departmentId);
      startEditing(departmentId, 'leadName', department?.leaderName?.trim() || '');
      return;
    }
    if (!userId) {
      updateDepartment(departmentId, {
        leaderUserId: null,
        leaderName: '',
      });
      return;
    }
    const employee = employeeById.get(userId);
    if (!employee) return;
    const previousLeaderUserId = activeDepartments.find((item) => item.id === departmentId)?.leaderUserId || null;
    const existingBinding = value.bindings.find((binding) => binding.userId === employee.id) || emptyBinding(employee.id);
    const nextPrimaryRoleId = pickDepartmentLeadRoleId(value.roles, departmentId, existingBinding.primaryRoleId);
    const nextBindings = value.bindings
      .map((binding) => {
        if (binding.userId === employee.id) {
          return {
            ...binding,
            departmentId,
            primaryRoleId: nextPrimaryRoleId,
            isManager: true,
            managerUserId: value.organization.leaderUserId && value.organization.leaderUserId !== employee.id
              ? value.organization.leaderUserId
              : binding.managerUserId || null,
            taskEditScope: 'department',
            canApproveTasks: true,
            canReassignTasks: true,
            canChangeDeadline: true,
            updatedAt: new Date().toISOString(),
          };
        }
        if (previousLeaderUserId && binding.userId === previousLeaderUserId && previousLeaderUserId !== employee.id && binding.departmentId === departmentId) {
          return {
            ...binding,
            isManager: false,
            taskEditScope: 'self',
            canApproveTasks: false,
            canReassignTasks: false,
            canChangeDeadline: false,
            updatedAt: new Date().toISOString(),
          };
        }
        return binding;
      });
    const bindingExists = value.bindings.some((binding) => binding.userId === employee.id);
    onChange({
      ...value,
      departments: value.departments.map((department) => (
        department.id === departmentId
          ? {
              ...department,
              leaderUserId: employee.id,
              leaderName: employee.fullName,
            }
          : department
      )),
      bindings: bindingExists
        ? nextBindings
        : [
            ...nextBindings,
            {
              ...existingBinding,
              departmentId,
              primaryRoleId: nextPrimaryRoleId,
              isManager: true,
              managerUserId: value.organization.leaderUserId && value.organization.leaderUserId !== employee.id
                ? value.organization.leaderUserId
                : null,
              taskEditScope: 'department',
              canApproveTasks: true,
              canReassignTasks: true,
              canChangeDeadline: true,
              updatedAt: new Date().toISOString(),
            },
          ],
    });
    setEditingNodeId(null);
    setEditingField(null);
  }, [activeDepartments, canEdit, employeeById, onChange, startEditing, value]);

  const handleSelectOrganizationLead = useCallback((userId: string) => {
    if (!canEdit) return;

    const previousLeaderUserId = value.organization.leaderUserId || null;
    if (!userId) {
      onChange({
        ...value,
        organization: {
          ...value.organization,
          leaderUserId: null,
          managementUserIds: value.organization.managementUserIds.filter((id) => id !== previousLeaderUserId),
        },
        bindings: value.bindings.map((binding) => (
          previousLeaderUserId && binding.userId === previousLeaderUserId
            ? {
                ...binding,
                isManager: false,
                taskEditScope: binding.departmentId ? 'department' : 'self',
                canApproveTasks: false,
                canReassignTasks: false,
                canChangeDeadline: false,
                updatedAt: new Date().toISOString(),
              }
            : binding
        )),
      });
      return;
    }

    const employee = employeeById.get(userId);
    if (!employee) return;

    const existingBinding = value.bindings.find((binding) => binding.userId === employee.id) || emptyBinding(employee.id);
    const bindingExists = value.bindings.some((binding) => binding.userId === employee.id);
    const nextBindings = value.bindings
      .map((binding) => {
        if (binding.userId === employee.id) {
          return {
            ...binding,
            isManager: true,
            managerUserId: null,
            taskEditScope: 'organization',
            canApproveTasks: true,
            canReassignTasks: true,
            canChangeDeadline: true,
            updatedAt: new Date().toISOString(),
          };
        }
        if (previousLeaderUserId && binding.userId === previousLeaderUserId && previousLeaderUserId !== employee.id) {
          return {
            ...binding,
            isManager: false,
            taskEditScope: binding.departmentId ? 'department' : 'self',
            canApproveTasks: false,
            canReassignTasks: false,
            canChangeDeadline: false,
            updatedAt: new Date().toISOString(),
          };
        }
        if (binding.userId !== employee.id && binding.isManager && !binding.managerUserId) {
          return {
            ...binding,
            managerUserId: employee.id,
            updatedAt: new Date().toISOString(),
          };
        }
        return binding;
      });

    onChange({
      ...value,
      organization: {
        ...value.organization,
        leaderUserId: employee.id,
        managementUserIds: Array.from(new Set([...value.organization.managementUserIds.filter((id) => id !== previousLeaderUserId), employee.id])),
      },
      bindings: bindingExists
        ? nextBindings
        : [
            ...nextBindings,
            {
              ...existingBinding,
              isManager: true,
              managerUserId: null,
              taskEditScope: 'organization',
              canApproveTasks: true,
              canReassignTasks: true,
              canChangeDeadline: true,
              updatedAt: new Date().toISOString(),
            },
          ],
    });
  }, [canEdit, employeeById, onChange, value]);

  const handleAddDepartment = useCallback(() => {
    if (!canEdit) return;
    const nextIndex = value.departments.length;
    const nextDepartment: OrgDepartmentSettings = {
      id: nextUiId('department'),
      name: `新部门 ${nextIndex + 1}`,
      color: departmentColor(nextIndex),
      leaderUserId: null,
      leaderName: '',
      parentDepartmentId: null,
      mission: '',
      businessContext: '',
      teamContext: '',
      quarterPlan: buildEmptyQuarterPlan(),
      quarterlyFocus: [],
      collaborationDepartmentIds: [],
      active: true,
      updatedAt: '',
    };

    onChange({
      ...value,
      departments: [...value.departments, nextDepartment],
    });

    window.setTimeout(() => {
      startEditing(nextDepartment.id, 'name', nextDepartment.name);
    }, 10);
  }, [canEdit, onChange, startEditing, value]);

  const handleAddRole = useCallback((departmentId: string | null) => {
    if (!canEdit) return;
    const nextRole: OrgRoleTemplateSettings = {
      id: nextUiId('role'),
      departmentId,
      name: '新岗位',
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
    };

    onChange({
      ...value,
      roles: [...value.roles, nextRole],
    });

    window.setTimeout(() => {
      startEditing(nextRole.id, 'name', nextRole.name);
    }, 10);
  }, [canEdit, onChange, startEditing, value]);

  const handleDeleteDepartment = useCallback((departmentId: string) => {
    if (!canEdit) return;
    const hasRoles = value.roles.some((role) => role.active !== false && role.departmentId === departmentId);
    if (hasRoles) {
      showToast('请先删除该部门下的所有岗位');
      return;
    }

    onChange({
      ...value,
      departments: value.departments.map((department) => (
        department.id === departmentId
          ? { ...department, active: false, updatedAt: department.updatedAt || new Date().toISOString() }
          : department
      )),
      bindings: value.bindings.map((binding) => (
        binding.departmentId === departmentId
          ? { ...binding, departmentId: null }
          : binding
      )),
      departmentPlans: value.departmentPlans.map((plan) => (
        plan.departmentId === departmentId
          ? { ...plan, departmentId: null }
          : plan
      )),
    });
  }, [canEdit, onChange, showToast, value]);

  const handleDeleteRole = useCallback((roleId: string) => {
    if (!canEdit) return;

    onChange({
      ...value,
      roles: value.roles.map((role) => (
        role.id === roleId
          ? { ...role, active: false, updatedAt: role.updatedAt || new Date().toISOString() }
          : role
      )),
      bindings: value.bindings.map((binding) => (
        binding.primaryRoleId === roleId
          ? { ...binding, primaryRoleId: null, updatedAt: binding.updatedAt || new Date().toISOString() }
          : binding
      )),
    });
  }, [canEdit, onChange, value]);

  const handleSave = useCallback(() => {
    void onSave(value);
    showToast('组织结构已保存');
  }, [onSave, showToast, value]);

  const drawLines = useCallback(() => {
    if (!containerRef.current || activeView !== 'tree') {
      setLines([]);
      return;
    }

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const nextLines: LineDefinition[] = [];

    const buildPath = (startEl: Element | null, endEl: Element | null) => {
      if (!startEl || !endEl) return null;
      const startRect = startEl.getBoundingClientRect();
      const endRect = endEl.getBoundingClientRect();
      const startX = startRect.right - containerRect.left;
      const startY = startRect.top + startRect.height / 2 - containerRect.top;
      const endX = endRect.left - containerRect.left;
      const endY = endRect.top + endRect.height / 2 - containerRect.top;
      const midX = startX + (endX - startX) / 2;
      return `M ${startX} ${startY} L ${midX} ${startY} L ${midX} ${endY} L ${endX} ${endY}`;
    };

    const orgEl = container.querySelector(`#node-${tree.id}`);
    tree.children.forEach((department) => {
      const departmentEl = container.querySelector(`#node-${department.id}`);
      const departmentPath = buildPath(orgEl, departmentEl);
      if (departmentPath) {
        nextLines.push({ id: `${tree.id}-${department.id}`, path: departmentPath });
      }

      department.children.forEach((role) => {
        const roleEl = container.querySelector(`#node-${role.id}`);
        const rolePath = buildPath(departmentEl, roleEl);
        if (rolePath) {
          nextLines.push({ id: `${department.id}-${role.id}`, path: rolePath });
        }
      });

      const addRoleEl = container.querySelector(`#add-btn-${department.id}`);
      const addRolePath = buildPath(departmentEl, addRoleEl);
      if (addRolePath) {
        nextLines.push({ id: `${department.id}-add`, path: addRolePath });
      }
    });

    const addDepartmentEl = container.querySelector(`#add-btn-${tree.id}`);
    const addDepartmentPath = buildPath(orgEl, addDepartmentEl);
    if (addDepartmentPath) {
      nextLines.push({ id: `${tree.id}-add`, path: addDepartmentPath });
    }

    setLines(nextLines);
  }, [activeView, tree]);

  useLayoutEffect(() => {
    drawLines();
    const observer = new ResizeObserver(() => drawLines());
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    window.addEventListener('resize', drawLines);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', drawLines);
    };
  }, [drawLines, editingField, editingNodeId]);

  return (
    <div className="space-y-6">
      {toast ? (
        <div className="fixed top-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-gray-900/90 px-5 py-2.5 text-[13px] font-medium text-white shadow-lg">
          {toast}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-[28px] border border-gray-100 bg-white px-6 py-5 shadow-sm">
            <p className="text-[13px] font-medium text-gray-400">{stat.label}</p>
            <p className="mt-3 text-[42px] font-bold tracking-tight text-gray-900">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-[32px] border border-[#DCE4FF] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-100 px-8 py-6">
          <div className="flex items-center gap-3">
            {activeView === 'codes' ? (
              <button
                type="button"
                onClick={() => setActiveView('tree')}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 text-gray-500 transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                <ChevronLeft size={18} />
              </button>
            ) : null}
            <div className="inline-flex items-center gap-2 rounded-full border border-gray-100 bg-white px-4 py-2 text-[13px] font-bold text-[#5B7BFE] shadow-sm">
              <Building2 size={14} />
              组织搭建中心
            </div>
          </div>
          <div className="flex items-center gap-3">
            {canEdit ? (
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="inline-flex items-center gap-2 rounded-full bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.25)] transition hover:bg-[#4A63CF] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save size={14} />
                {isSaving ? '保存中' : '保存'}
              </button>
            ) : null}
            {activeView === 'tree' ? (
              <button
                type="button"
                onClick={() => setActiveView('codes')}
                className="rounded-full border border-[#DCE4FF] bg-white px-5 py-3 text-[13px] font-bold text-[#4A63CF] transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                查看邀请码
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleCopyAllInvites()}
                className="inline-flex items-center gap-2 rounded-full border border-[#DCE4FF] bg-white px-5 py-3 text-[13px] font-bold text-[#4A63CF] transition hover:border-[#5B7BFE]/40 hover:text-[#5B7BFE]"
              >
                {bulkInviteCopied ? <Check size={14} /> : <Copy size={14} />}
                {bulkInviteCopied ? '已复制全部邀请码' : '一键复制邀请码'}
              </button>
            )}
          </div>
        </div>

        <div ref={containerRef} className="relative overflow-x-auto bg-[#F9FAFB]">
          {activeView === 'tree' ? (
            <div className="relative min-w-max p-12">
              <svg className="pointer-events-none absolute inset-0 h-full w-full">
                {lines.map((line) => (
                  <path
                    key={line.id}
                    d={line.path}
                    fill="none"
                    stroke="#E5E7EB"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                ))}
              </svg>

              <div className="relative z-10 flex items-center gap-12">
                <div
                  id={`node-${tree.id}`}
                  className="z-10 flex min-w-[260px] flex-col gap-3 rounded-2xl border-2 border-[#5B7BFE]/30 bg-gradient-to-br from-[#EEF3FF] to-white px-5 py-4 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <Building2 className="text-[#5B7BFE]" size={20} />
                    {editingNodeId === tree.id && editingField === 'name' ? (
                      <input
                        autoFocus
                        value={editingText}
                        onChange={(event) => setEditingText(event.target.value)}
                        onBlur={handleSaveEdit}
                        onKeyDown={handleKeyDown}
                        className="w-full border-b border-[#5B7BFE] bg-transparent text-[16px] font-bold text-gray-900 outline-none"
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => startEditing(tree.id, 'name', tree.name)}
                        className="text-left text-[16px] font-bold text-gray-900 transition hover:text-[#5B7BFE]"
                      >
                        {tree.name}
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-[11px] font-medium text-gray-400">负责人</span>
                    {approvedEmployees.length > 0 ? (
                      <select
                        value={value.organization.leaderUserId || ''}
                        onChange={(event) => handleSelectOrganizationLead(event.target.value)}
                        className="min-w-[160px] rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700 outline-none transition hover:border-[#5B7BFE]/50 focus:border-[#5B7BFE]"
                      >
                        <option value="">待绑定</option>
                        {approvedEmployees.map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {(employee.jobTitle?.trim() ? `${employee.jobTitle} · ` : '') + employee.fullName}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700">
                        {organizationLeaderSummary}
                      </span>
                    )}
                  </div>
                  {approvedEmployees.length > 0 && organizationLeader ? (
                    <div className="pl-8 text-[11px] font-medium text-gray-500">
                      {organizationLeaderSummary}
                    </div>
                  ) : null}
                </div>

                <div className="relative flex flex-col gap-6">
                  {tree.children.map((department, index) => {
                    const isEditingDepartmentName = editingNodeId === department.id && editingField === 'name';
                    const isEditingLeadName = editingNodeId === department.id && editingField === 'leadName';
                    const memberCount = bindingsByDepartmentId.get(department.id)?.length || 0;
                    const inviteCode = buildDepartmentInviteCode(department.id, {
                      organizationName,
                      departmentName: department.name,
                      order: index,
                    });
                    return (
                      <div key={department.id} className="flex items-center gap-10">
                        <div
                          id={`node-${department.id}`}
                          className="group relative z-10 flex min-w-[170px] flex-col gap-1.5 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm transition hover:border-[#5B7BFE]/40"
                          style={{ boxShadow: `0 12px 28px ${tint(department.color, '16')}` }}
                        >
                          {canEdit ? (
                            <button
                              type="button"
                              onClick={() => handleDeleteDepartment(department.id)}
                              className="absolute -right-2 -top-2 rounded-full border border-gray-200 bg-white p-0.5 text-gray-300 opacity-0 shadow-sm transition group-hover:opacity-100 hover:border-rose-200 hover:text-rose-500"
                            >
                              <X size={12} />
                            </button>
                          ) : null}

                          <div className="flex items-center gap-2">
                            <Users className="text-gray-400" size={14} />
                            {isEditingDepartmentName ? (
                              <input
                                autoFocus
                                value={editingText}
                                onChange={(event) => setEditingText(event.target.value)}
                                onBlur={handleSaveEdit}
                                onKeyDown={handleKeyDown}
                                className="w-full border-b border-[#5B7BFE] bg-transparent text-[13px] font-bold text-gray-800 outline-none"
                              />
                            ) : (
                              <button
                                type="button"
                                onClick={() => startEditing(department.id, 'name', department.name)}
                                className="text-left text-[13px] font-bold text-gray-800 transition hover:text-[#5B7BFE]"
                              >
                                {department.name}
                              </button>
                            )}
                          </div>

                          <div className="flex items-center gap-1.5 pl-6">
                            <span className="text-[11px] text-gray-400">负责人</span>
                            {approvedEmployees.length > 0 && !isEditingLeadName ? (
                              <select
                                value={department.leaderUserId || (department.leaderName?.trim() ? '__manual__' : '')}
                                onChange={(event) => handleSelectDepartmentLead(department.id, event.target.value)}
                                className="min-w-[112px] rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 outline-none transition hover:border-[#5B7BFE]/40 focus:border-[#5B7BFE]/50"
                              >
                                <option value="">待绑定</option>
                                {approvedEmployees.map((employee) => (
                                  <option key={employee.id} value={employee.id}>
                                    {employee.fullName}
                                  </option>
                                ))}
                                <option value="__manual__">手动填写</option>
                              </select>
                            ) : (
                              <>
                                {isEditingLeadName ? (
                                  <input
                                    autoFocus
                                    value={editingText}
                                    onChange={(event) => setEditingText(event.target.value)}
                                    onBlur={handleSaveEdit}
                                    onKeyDown={handleKeyDown}
                                    className="w-[84px] border-b border-gray-300 bg-transparent text-[11px] text-gray-600 outline-none focus:border-[#5B7BFE]"
                                  />
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => startEditing(department.id, 'leadName', department.leadName)}
                                    className="min-w-[40px] text-left text-[11px] text-gray-500 transition hover:text-[#5B7BFE]"
                                  >
                                    {department.leadName || '待设置'}
                                  </button>
                                )}
                              </>
                            )}
                          </div>

                          {approvedEmployees.length > 0 && !department.leaderUserId && department.leaderName?.trim() ? (
                            <div className="pl-6 text-[11px] font-medium text-gray-500">
                              手动负责人：{department.leaderName.trim()}
                            </div>
                          ) : null}

                          <div className="mt-2 flex items-center gap-2 pl-6">
                            <span
                              className="rounded-full px-2.5 py-1 text-[10px] font-bold"
                              style={{ backgroundColor: tint(department.color), color: department.color }}
                            >
                              邀请码 {inviteCode}
                            </span>
                            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">
                              {memberCount} 人
                            </span>
                          </div>
                        </div>

                        <div className="relative flex flex-col gap-3">
                          {department.children.map((role) => {
                            const isEditingRoleName = editingNodeId === role.id && editingField === 'name';
                            return (
                              <div
                                id={`node-${role.id}`}
                                key={role.id}
                                className="group relative z-10 min-w-[120px] rounded-xl border border-gray-100 bg-gray-50/90 px-3 py-2 transition hover:border-gray-200"
                              >
                                {canEdit ? (
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteRole(role.id)}
                                    className="absolute -right-1.5 -top-1.5 rounded-full border border-gray-200 bg-white p-0.5 text-gray-300 opacity-0 shadow-sm transition group-hover:opacity-100 hover:border-rose-200 hover:text-rose-500"
                                  >
                                    <X size={10} />
                                  </button>
                                ) : null}

                                {isEditingRoleName ? (
                                  <input
                                    autoFocus
                                    value={editingText}
                                    onChange={(event) => setEditingText(event.target.value)}
                                    onBlur={handleSaveEdit}
                                    onKeyDown={handleKeyDown}
                                    className="w-full border-b border-gray-300 bg-transparent text-center text-[12px] font-medium text-gray-700 outline-none focus:border-[#5B7BFE]"
                                  />
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => startEditing(role.id, 'name', role.name)}
                                    className="w-full text-center text-[12px] font-medium text-gray-600 transition hover:text-[#5B7BFE]"
                                  >
                                    {role.name}
                                  </button>
                                )}
                              </div>
                            );
                          })}

                          {canEdit ? (
                            <button
                              id={`add-btn-${department.id}`}
                              type="button"
                              onClick={() => handleAddRole(department.id)}
                              className="z-10 inline-flex min-w-[120px] items-center justify-center gap-1 rounded-xl border border-dashed border-gray-200 bg-white/70 px-3 py-2 text-[12px] text-gray-400 transition hover:border-[#5B7BFE]/40 hover:bg-[#5B7BFE]/5"
                            >
                              <Plus size={12} />
                              添加岗位
                            </button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}

                  {canEdit ? (
                    <button
                      id={`add-btn-${tree.id}`}
                      type="button"
                      onClick={handleAddDepartment}
                      className="z-10 inline-flex min-w-[150px] items-center justify-center gap-1.5 rounded-xl border border-dashed border-gray-300 bg-white/70 px-4 py-3 text-[13px] font-medium text-gray-400 transition hover:border-[#5B7BFE]/60 hover:bg-[#5B7BFE]/5"
                    >
                      <Plus size={14} />
                      添加部门
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8">
              <div className="mx-auto grid max-w-5xl grid-cols-1 gap-5 md:grid-cols-2">
                {tree.children.map((department, index) => {
                  const inviteCode = buildDepartmentInviteCode(department.id, {
                    organizationName,
                    departmentName: department.name,
                    order: index,
                  });
                  const joinedCount = bindingsByDepartmentId.get(department.id)?.length || 0;
                  const positions = department.children.map((item) => item.name).join('、') || '暂无岗位';
                  return (
                    <InviteCard
                      key={department.id}
                      departmentName={department.name}
                      leadName={department.leadName}
                      inviteCode={inviteCode}
                      positions={positions}
                      joinedCount={joinedCount}
                      color={department.color}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

type InviteCardProps = {
  departmentName: string;
  leadName: string;
  inviteCode: string;
  positions: string;
  joinedCount: number;
  color: string;
};

function InviteCard({
  departmentName,
  leadName,
  inviteCode,
  positions,
  joinedCount,
  color,
}: InviteCardProps) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition hover:shadow-md">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-[17px] font-bold text-gray-900">{departmentName}</h3>
          <p className="mt-1 text-[12px] text-gray-500">{leadName || '待设置负责人'}</p>
        </div>
        <div className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-bold text-gray-500">
          已加入 {joinedCount} 人
        </div>
      </div>

      <div className="mt-auto rounded-xl border px-4 py-4" style={{ backgroundColor: tint(color, '08'), borderColor: tint(color, '18') }}>
        <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em]" style={{ color }}>
          邀请码
        </div>
        <div className="text-[22px] font-bold tracking-[0.16em]" style={{ color }}>
          {inviteCode}
        </div>
      </div>

      <div className="mt-4 border-t border-gray-100 pt-4 text-[12px] text-gray-500">
        {positions}
      </div>
    </div>
  );
}
