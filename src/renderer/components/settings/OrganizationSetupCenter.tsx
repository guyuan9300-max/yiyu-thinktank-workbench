import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Building2, Check, ChevronDown, ChevronLeft, Copy, FileText, Pencil, Plus, Save, Trash2, UploadCloud, Users, X } from 'lucide-react';

import type {
  DepartmentOption,
  EmployeeRecord,
  OrgDepartmentSettings,
  OrgEmployeeBindingSettings,
  OrgIntroDocumentSettings,
  OrgModelSettings,
  OrgQuarterKey,
  OrgRoleTemplateSettings,
} from '../../../shared/types';
import { buildDepartmentInviteCode } from '../../../shared/departmentInvite';
import { isAssignableOrganizationEmployee, isLegacyOrganizationPersonName } from '../../lib/organizationEmployeeFilters';

type LinkedSection = 'tasks' | 'handbook';

type Props = {
  value: OrgModelSettings;
  departmentCatalog: DepartmentOption[];
  employees: EmployeeRecord[];
  canEdit: boolean;
  isSaving?: boolean;
  activeWeekLabel: string;
  initialAdvancedTab?: string | null;
  onChange: (next: OrgModelSettings) => void;
  onSave: (next?: OrgModelSettings) => Promise<boolean | void> | boolean | void;
  getInputDrafts?: () => OrganizationSetupInputDraftState;
  setInputDrafts?: (next: OrganizationSetupInputDraftState) => void;
  onUploadIntroDocument?: (title: string) => Promise<OrgIntroDocumentSettings | null>;
  onOpenSection: (section: LinkedSection) => void;
};

export type OrganizationSetupInputDraftState = {
  organizationName?: string;
  organizationLeaderName?: string;
  departmentLeaderNames?: Record<string, string>;
  editingNodeId?: string | null;
  editingField?: 'name' | 'leadName' | null;
  editingText?: string;
};

type ActiveView = 'tree' | 'codes';

type EditableField = 'name' | 'leadName';

type TreeDepartmentNode = {
  id: string;
  name: string;
  type: 'department';
  leadName: string;
  leaderUserId?: string | null;
  leaderName?: string | null;
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

function tint(hexColor: string, suffix = '12') {
  return `${hexColor}${suffix}`;
}

function visibleLeaderNameInput(value: string | null | undefined) {
  const name = (value || '').trim();
  if (!name || isLegacyOrganizationPersonName(name)) return '';
  return name;
}

function isComposingKeyEvent(
  event: React.KeyboardEvent<HTMLInputElement>,
  composingRef: React.MutableRefObject<boolean>,
) {
  const nativeEvent = event.nativeEvent as KeyboardEvent & { isComposing?: boolean; keyCode?: number };
  return composingRef.current || nativeEvent.isComposing || nativeEvent.keyCode === 229;
}

function resolveInputDraftText(draftValue: string | undefined, fallbackValue: string) {
  return typeof draftValue === 'string' ? draftValue : fallbackValue;
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
    children: activeDepartments.map((department) => {
      const rawLeaderName = department.leaderName?.trim() || '';
      const visibleLeaderName = rawLeaderName && !isLegacyOrganizationPersonName(rawLeaderName) ? rawLeaderName : '';
      return {
        id: department.id,
        name: department.name || '未命名部门',
        type: 'department',
        leadName: visibleLeaderName || '待设置',
        leaderUserId: department.leaderUserId || null,
        leaderName: visibleLeaderName || null,
        color: department.color || DEPARTMENT_COLORS[0],
        children: activeRoles
          .filter((role) => role.departmentId === department.id)
          .map((role) => ({
            id: role.id,
            name: role.name || '未命名岗位',
            type: 'position',
            departmentId: department.id,
          })),
      };
    }),
  };
}

function computeStats(
  value: OrgModelSettings,
  employees: EmployeeRecord[],
) {
  const activeDepartments = value.departments.filter((item) => item.active !== false);
  const activeRoles = value.roles.filter((item) => item.active !== false);
  const activePlans = value.departmentPlans.filter((item) => item.status !== 'closed');
  const activeEmployees = employees.filter(isAssignableOrganizationEmployee);
  const activeEmployeeIds = new Set(activeEmployees.map((item) => item.id));
  const boundMemberIds = new Set(value.bindings.filter((item) => item.primaryRoleId && activeEmployeeIds.has(item.userId)).map((item) => item.userId));
  const manualDepartmentLeaderCount = activeDepartments.filter((department) => {
    const visibleLeaderName = visibleLeaderNameInput(department.leaderName);
    return Boolean(visibleLeaderName && !department.leaderUserId);
  }).length;
  const memberCount = Math.max(boundMemberIds.size + manualDepartmentLeaderCount, activeEmployees.length);

  const completenessByDepartment = activeDepartments.map((department) => {
    const roleCount = activeRoles.filter((role) => role.departmentId === department.id).length;
    const planCount = activePlans.filter((plan) => plan.departmentId === department.id).length;
    const memberBindings = value.bindings.filter((binding) => binding.departmentId === department.id && activeEmployeeIds.has(binding.userId));
    const visibleLeaderName = department.leaderName?.trim() && !isLegacyOrganizationPersonName(department.leaderName)
      ? department.leaderName.trim()
      : '';
    const hasVisibleLeader = Boolean(visibleLeaderName) || Boolean(department.leaderUserId && activeEmployeeIds.has(department.leaderUserId));
    const memberCount = countDepartmentMembers(department, memberBindings);
    const missing = [
      !hasVisibleLeader,
      !department.mission.trim(),
      roleCount === 0,
      memberCount === 0,
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

function buildEmptyOrgModel(value: OrgModelSettings): OrgModelSettings {
  const timestamp = new Date().toISOString();
  return {
    ...value,
    organization: {
      ...value.organization,
      name: '',
      annualGoal: '',
      annualStrategyYear: String(new Date().getFullYear()),
      annualStrategy: '',
      quarterPlans: [],
      quarterlyFocus: [],
      leaderUserId: null,
      leaderName: '',
      introDocument: null,
      managementUserIds: [],
      updatedAt: timestamp,
    },
    departments: [],
    roles: [],
    bindings: [],
    reportingLines: [],
    taskControlRules: [],
    roleProcessTemplates: [],
    focusItems: [],
    departmentPlans: [],
    updatedAt: timestamp,
  };
}

function applyOrganizationNameDraft(value: OrgModelSettings, rawName: string): OrgModelSettings {
  const nextName = rawName.trim();
  if (nextName === value.organization.name) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    organization: {
      ...value.organization,
      name: nextName,
      updatedAt: timestamp,
    },
    updatedAt: timestamp,
  };
}

function applyOrganizationLeaderNameDraft(value: OrgModelSettings, rawName: string): OrgModelSettings {
  const nextName = visibleLeaderNameInput(rawName);
  const currentName = visibleLeaderNameInput(value.organization.leaderName);
  if (
    nextName === currentName
    && !value.organization.leaderUserId
    && currentName === (value.organization.leaderName || '').trim()
  ) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    organization: {
      ...value.organization,
      leaderUserId: null,
      leaderName: nextName,
      managementUserIds: [],
      updatedAt: timestamp,
    },
    updatedAt: timestamp,
  };
}

function applyOrganizationLeaderUserIdDraft(
  value: OrgModelSettings,
  userId: string | null,
  displayName: string,
): OrgModelSettings {
  const nextName = displayName.trim();
  if (
    (value.organization.leaderUserId ?? null) === userId
    && (value.organization.leaderName ?? '') === nextName
  ) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    organization: {
      ...value.organization,
      leaderUserId: userId,
      leaderName: nextName,
      managementUserIds: userId ? [userId] : [],
      updatedAt: timestamp,
    },
    updatedAt: timestamp,
  };
}

function applyDepartmentLeaderUserIdDraft(
  value: OrgModelSettings,
  departmentId: string,
  userId: string | null,
  displayName: string,
): OrgModelSettings {
  const dept = value.departments.find((d) => d.id === departmentId);
  if (!dept) return value;
  const nextName = displayName.trim();
  if (
    (dept.leaderUserId ?? null) === userId
    && (dept.leaderName ?? '') === nextName
  ) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    departments: value.departments.map((d) =>
      d.id === departmentId
        ? { ...d, leaderUserId: userId, leaderName: nextName, updatedAt: timestamp }
        : d,
    ),
    updatedAt: timestamp,
  };
}

function applyDepartmentLeaderNameDrafts(
  value: OrgModelSettings,
  drafts: Record<string, string>,
): OrgModelSettings {
  const draftEntries = Object.entries(drafts);
  const timestamp = new Date().toISOString();
  let changed = false;
  const draftByDepartmentId = new Map(draftEntries.map(([departmentId, rawName]) => [departmentId, rawName.trim()]));
  const departments = value.departments.map((department) => {
    const hasDraft = draftByDepartmentId.has(department.id);
    const nextName = visibleLeaderNameInput(hasDraft ? draftByDepartmentId.get(department.id) : department.leaderName);
    const currentName = visibleLeaderNameInput(department.leaderName);
    if (
      nextName === currentName
      && !department.leaderUserId
      && currentName === (department.leaderName || '').trim()
    ) {
      return department;
    }
    changed = true;
    return {
      ...department,
      leaderUserId: null,
      leaderName: nextName,
      updatedAt: timestamp,
    };
  });
  if (!changed) {
    return value;
  }
  return {
    ...value,
    departments,
    updatedAt: timestamp,
  };
}

function applyDepartmentNameDraft(value: OrgModelSettings, departmentId: string, rawName: string): OrgModelSettings {
  const nextName = rawName.trim();
  if (!nextName) return value;
  const department = value.departments.find((item) => item.id === departmentId);
  if (!department || department.name === nextName) return value;
  const timestamp = new Date().toISOString();
  return {
    ...value,
    departments: value.departments.map((item) => (
      item.id === departmentId ? { ...item, name: nextName, updatedAt: timestamp } : item
    )),
    updatedAt: timestamp,
  };
}

function applyRoleNameDraft(value: OrgModelSettings, roleId: string, rawName: string): OrgModelSettings {
  const nextName = rawName.trim();
  if (!nextName) return value;
  const role = value.roles.find((item) => item.id === roleId);
  if (!role || role.name === nextName) return value;
  const timestamp = new Date().toISOString();
  return {
    ...value,
    roles: value.roles.map((item) => (
      item.id === roleId ? { ...item, name: nextName, updatedAt: timestamp } : item
    )),
    updatedAt: timestamp,
  };
}

function introDocumentChanged(nextDocument: OrgIntroDocumentSettings | null | undefined, currentDocument: OrgIntroDocumentSettings | null | undefined) {
  if (!nextDocument) return false;
  return nextDocument.contentHash !== currentDocument?.contentHash
    || nextDocument.fileName !== currentDocument?.fileName
    || nextDocument.uploadedAt !== currentDocument?.uploadedAt;
}

function applyOrganizationIntroDocumentDraft(value: OrgModelSettings, document: OrgIntroDocumentSettings): OrgModelSettings {
  if (!introDocumentChanged(document, value.organization.introDocument)) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    organization: {
      ...value.organization,
      introDocument: document,
      updatedAt: timestamp,
    },
    updatedAt: timestamp,
  };
}

function applyDepartmentIntroDocumentDraft(
  value: OrgModelSettings,
  departmentId: string,
  document: OrgIntroDocumentSettings,
): OrgModelSettings {
  const department = value.departments.find((item) => item.id === departmentId);
  if (!department || !introDocumentChanged(document, department.introDocument)) {
    return value;
  }
  const timestamp = new Date().toISOString();
  return {
    ...value,
    departments: value.departments.map((item) => (
      item.id === departmentId
        ? { ...item, introDocument: document, updatedAt: timestamp }
        : item
    )),
    updatedAt: timestamp,
  };
}

function countDepartmentMembers(
  department: OrgDepartmentSettings,
  bindings: OrgEmployeeBindingSettings[],
) {
  const userIds = new Set(bindings.map((binding) => binding.userId).filter(Boolean));
  if (department.leaderUserId) {
    userIds.add(department.leaderUserId);
  }
  const visibleLeaderName = visibleLeaderNameInput(department.leaderName);
  const manualLeaderCount = !department.leaderUserId && visibleLeaderName ? 1 : 0;
  return userIds.size + manualLeaderCount;
}

export function OrganizationSetupCenter({
  value,
  departmentCatalog,
  employees,
  canEdit,
  isSaving = false,
  onChange,
  onSave,
  getInputDrafts,
  setInputDrafts,
  onUploadIntroDocument,
}: Props) {
  void departmentCatalog;

  const initialInputDrafts = getInputDrafts?.() || {};
  const [activeView, setActiveView] = useState<ActiveView>('tree');
  const [editingNodeId, setEditingNodeId] = useState<string | null>(initialInputDrafts.editingNodeId || null);
  const [editingField, setEditingField] = useState<EditableField | null>((initialInputDrafts.editingField as EditableField | null) || null);
  const [editingText, setEditingText] = useState(initialInputDrafts.editingText || '');
  const [toast, setToast] = useState<string | null>(null);
  const [organizationNameInput, setOrganizationNameInput] = useState(
    resolveInputDraftText(initialInputDrafts.organizationName, value.organization.name),
  );
  const [organizationLeaderNameInput, setOrganizationLeaderNameInput] = useState(
    visibleLeaderNameInput(resolveInputDraftText(initialInputDrafts.organizationLeaderName, value.organization.leaderName || '')),
  );
  const [departmentLeaderNameInputs, setDepartmentLeaderNameInputs] = useState<Record<string, string>>(
    initialInputDrafts.departmentLeaderNames || {},
  );
  const [pendingOrganizationIntroDocument, setPendingOrganizationIntroDocument] = useState<OrgIntroDocumentSettings | null>(null);
  const [pendingDepartmentIntroDocuments, setPendingDepartmentIntroDocuments] = useState<Record<string, OrgIntroDocumentSettings>>({});
  const [bulkInviteCopied, setBulkInviteCopied] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');
  // 编辑模式开关：默认关闭，组织搭建视图为只读；点"编辑组织"开启后才显示
  // 各种局部编辑控件（添加部门/岗位、删除 X、保存对勾、文本输入框）。
  const [isEditingMode, setIsEditingMode] = useState(false);
  const canModify = canEdit && isEditingMode;
  const [lines, setLines] = useState<LineDefinition[]>([]);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bulkInviteTimerRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const textCompositionRef = useRef(false);

  const tree = useMemo(
    () => deriveTree(value, '当前组织'),
    [value],
  );
  const stats = useMemo(() => computeStats(value, employees), [employees, value]);
  const activeDepartments = useMemo(() => value.departments.filter((item) => item.active !== false), [value.departments]);
  const activeRoles = useMemo(() => value.roles.filter((item) => item.active !== false), [value.roles]);
  const approvedEmployees = useMemo(
    () => employees.filter(isAssignableOrganizationEmployee),
    [employees],
  );
  const approvedEmployeeIds = useMemo(() => new Set(approvedEmployees.map((item) => item.id)), [approvedEmployees]);
  const bindingsByDepartmentId = useMemo(() => {
    const mapping = new Map<string, OrgEmployeeBindingSettings[]>();
    value.bindings.forEach((binding) => {
      if (!binding.departmentId) return;
      if (!approvedEmployeeIds.has(binding.userId)) return;
      const list = mapping.get(binding.departmentId) || [];
      list.push(binding);
      mapping.set(binding.departmentId, list);
    });
    return mapping;
  }, [approvedEmployeeIds, value.bindings]);

  const organizationName = organizationNameInput.trim() || value.organization.name.trim() || tree.name || '当前组织';
  const bulkInviteText = useMemo(() => {
    const linesOfText = tree.children.map((department, index) => {
      const inviteCode = buildDepartmentInviteCode(department.id, {
        organizationId: value.organization.organizationId,
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
  }, [organizationName, tree.children, value.organization.organizationId]);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = setTimeout(() => setToast(null), 2400);
  }, []);

  const updateInputDrafts = useCallback((updater: (current: OrganizationSetupInputDraftState) => OrganizationSetupInputDraftState) => {
    const current = getInputDrafts?.() || {};
    setInputDrafts?.(updater(current));
  }, [getInputDrafts, setInputDrafts]);

  const clearInputDrafts = useCallback(() => {
    setInputDrafts?.({});
  }, [setInputDrafts]);

  const setOrganizationNameDraft = useCallback((nextName: string) => {
    setOrganizationNameInput(nextName);
    updateInputDrafts((current) => ({ ...current, organizationName: nextName }));
  }, [updateInputDrafts]);

  const setOrganizationLeaderNameDraft = useCallback((nextName: string) => {
    setOrganizationLeaderNameInput(nextName);
    updateInputDrafts((current) => ({ ...current, organizationLeaderName: nextName }));
  }, [updateInputDrafts]);

  const clearOrganizationNameDraft = useCallback(() => {
    updateInputDrafts((current) => {
      const next = { ...current };
      delete next.organizationName;
      return next;
    });
  }, [updateInputDrafts]);

  const clearOrganizationLeaderNameDraft = useCallback(() => {
    updateInputDrafts((current) => {
      const next = { ...current };
      delete next.organizationLeaderName;
      return next;
    });
  }, [updateInputDrafts]);

  const setDepartmentLeaderNameDraft = useCallback((departmentId: string, nextName: string) => {
    setDepartmentLeaderNameInputs((previous) => ({
      ...previous,
      [departmentId]: nextName,
    }));
    updateInputDrafts((current) => ({
      ...current,
      departmentLeaderNames: {
        ...(current.departmentLeaderNames || {}),
        [departmentId]: nextName,
      },
    }));
  }, [updateInputDrafts]);

  const clearDepartmentLeaderNameDraft = useCallback((departmentId: string) => {
    updateInputDrafts((current) => {
      const departmentLeaderNames = { ...(current.departmentLeaderNames || {}) };
      delete departmentLeaderNames[departmentId];
      const next = { ...current };
      if (Object.keys(departmentLeaderNames).length > 0) {
        next.departmentLeaderNames = departmentLeaderNames;
      } else {
        delete next.departmentLeaderNames;
      }
      return next;
    });
  }, [updateInputDrafts]);

  const setEditingTextDraft = useCallback((nextText: string) => {
    setEditingText(nextText);
    updateInputDrafts((current) => ({ ...current, editingText: nextText }));
  }, [updateInputDrafts]);

  const clearEditingDraft = useCallback(() => {
    updateInputDrafts((current) => {
      const next = { ...current };
      delete next.editingNodeId;
      delete next.editingField;
      delete next.editingText;
      return next;
    });
  }, [updateInputDrafts]);

  const handleTextCompositionStart = useCallback(() => {
    textCompositionRef.current = true;
  }, []);

  const handleTextCompositionEnd = useCallback(() => {
    window.setTimeout(() => {
      textCompositionRef.current = false;
    }, 0);
  }, []);

  useEffect(() => {
    const draftName = getInputDrafts?.().organizationName;
    setOrganizationNameInput(resolveInputDraftText(draftName, value.organization.name));
  }, [getInputDrafts, value.organization.name]);

  useEffect(() => {
    const draftName = getInputDrafts?.().organizationLeaderName;
    setOrganizationLeaderNameInput(
      visibleLeaderNameInput(resolveInputDraftText(draftName, value.organization.leaderName || '')),
    );
  }, [getInputDrafts, value.organization.leaderName]);

  useEffect(() => {
    const activeDepartmentIds = new Set(value.departments.map((department) => department.id));
    setDepartmentLeaderNameInputs((previous) => {
      let changed = false;
      const next: Record<string, string> = {};
      const persistedDrafts = getInputDrafts?.().departmentLeaderNames || {};
      Object.entries({ ...persistedDrafts, ...previous }).forEach(([departmentId, draft]) => {
        if (activeDepartmentIds.has(departmentId)) {
          if (previous[departmentId] !== draft) {
            changed = true;
          }
          next[departmentId] = draft;
        } else {
          changed = true;
        }
      });
      if (Object.keys(previous).length !== Object.keys(next).length) {
        changed = true;
      }
      return changed ? next : previous;
    });
  }, [getInputDrafts, value.departments]);

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

  const commitOrganizationNameInput = useCallback(() => {
    const nextValue = applyOrganizationNameDraft(value, organizationNameInput);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setOrganizationNameInput(nextValue.organization.name);
    clearOrganizationNameDraft();
    return nextValue;
  }, [clearOrganizationNameDraft, onChange, organizationNameInput, value]);

  const commitOrganizationLeaderNameInput = useCallback(() => {
    const nextValue = applyOrganizationLeaderNameDraft(value, organizationLeaderNameInput);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setOrganizationLeaderNameInput(visibleLeaderNameInput(nextValue.organization.leaderName));
    clearOrganizationLeaderNameDraft();
    return nextValue;
  }, [clearOrganizationLeaderNameDraft, onChange, organizationLeaderNameInput, value]);

  // 通过下拉选择组织负责人：同时绑定 leaderUserId（精确关联，不依赖文本 fuzzy match）
  const handleSelectOrganizationLeader = useCallback((employee: EmployeeRecord | null) => {
    if (!canEdit) return;
    const nextValue = applyOrganizationLeaderUserIdDraft(
      value,
      employee?.id ?? null,
      employee?.fullName ?? '',
    );
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setOrganizationLeaderNameInput(employee?.fullName ?? '');
    clearOrganizationLeaderNameDraft();
  }, [canEdit, clearOrganizationLeaderNameDraft, onChange, value]);

  // 通过下拉选择岗位持岗人：更新 bindings (userId.primaryRoleId = roleId)
  // 一个员工同时只能有一个 primaryRoleId；若选的员工已经占别的岗位，会被搬过来；
  // 若该岗位本来有人，那个人的 primaryRoleId 会被置空。
  const handleSelectRoleHolder = useCallback((roleId: string, employee: EmployeeRecord | null) => {
    if (!canEdit) return;
    const timestamp = new Date().toISOString();
    const targetUserId = employee?.id ?? null;

    // 1. 找到当前占该岗位的员工 binding
    const currentHolder = value.bindings.find((b) => b.primaryRoleId === roleId);
    // No-op：当前持岗人就是目标
    if ((currentHolder?.userId ?? null) === targetUserId) return;

    // 2. 找到目标员工的现有 binding（如果有）
    const targetExistingBinding = targetUserId
      ? value.bindings.find((b) => b.userId === targetUserId)
      : null;

    // 3. 从该岗位查 departmentId（用作新 binding 的 default departmentId）
    const role = value.roles.find((r) => r.id === roleId);
    const inferredDepartmentId = role?.departmentId ?? null;

    let nextBindings = value.bindings.map((b) => {
      // 清空 current holder 的 primaryRoleId（如果要换人/清空）
      if (currentHolder && b.userId === currentHolder.userId && currentHolder.userId !== targetUserId) {
        return { ...b, primaryRoleId: null, updatedAt: timestamp };
      }
      // 把 target employee 的 binding.primaryRoleId 设到此 role
      if (targetUserId && b.userId === targetUserId) {
        return {
          ...b,
          primaryRoleId: roleId,
          departmentId: b.departmentId ?? inferredDepartmentId,
          updatedAt: timestamp,
        };
      }
      return b;
    });

    // 4. 如果 target employee 没有现存 binding，新建一条
    if (targetUserId && !targetExistingBinding) {
      nextBindings = [
        ...nextBindings,
        {
          userId: targetUserId,
          departmentId: inferredDepartmentId,
          primaryRoleId: roleId,
          managerUserId: null,
          isManager: false,
          projectRoleLabels: [],
          currentFocus: '',
          taskEditScope: 'self',
          canApproveTasks: false,
          canReassignTasks: false,
          canChangeDeadline: false,
          updatedAt: timestamp,
        },
      ];
    }

    onChange({
      ...value,
      bindings: nextBindings,
      updatedAt: timestamp,
    });
  }, [canEdit, onChange, value]);

  // 通过下拉选择部门负责人：同时绑定 leaderUserId
  const handleSelectDepartmentLeader = useCallback((departmentId: string, employee: EmployeeRecord | null) => {
    if (!canEdit) return;
    const nextValue = applyDepartmentLeaderUserIdDraft(
      value,
      departmentId,
      employee?.id ?? null,
      employee?.fullName ?? '',
    );
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setDepartmentLeaderNameInputs((previous) => {
      if (!(departmentId in previous)) return previous;
      const next = { ...previous };
      delete next[departmentId];
      return next;
    });
    clearDepartmentLeaderNameDraft(departmentId);
  }, [canEdit, clearDepartmentLeaderNameDraft, onChange, value]);

  const handleDepartmentLeaderNameChange = useCallback((departmentId: string, nextName: string) => {
    setDepartmentLeaderNameDraft(departmentId, nextName);
  }, [setDepartmentLeaderNameDraft]);

  const commitDepartmentLeaderNameInput = useCallback((departmentId: string) => {
    if (!canEdit) return;
    const rawDraft = departmentLeaderNameInputs[departmentId];
    if (rawDraft === undefined) return;
    const department = value.departments.find((item) => item.id === departmentId);
    if (!department) return;
    const nextName = rawDraft.trim();
      const currentName = visibleLeaderNameInput(department.leaderName);
      if (nextName !== currentName || department.leaderUserId) {
      updateDepartment(departmentId, {
        leaderUserId: null,
        leaderName: nextName,
        updatedAt: new Date().toISOString(),
      });
    }
    setDepartmentLeaderNameInputs((previous) => {
      if (!(departmentId in previous)) return previous;
      const next = { ...previous };
      delete next[departmentId];
      return next;
    });
    clearDepartmentLeaderNameDraft(departmentId);
  }, [canEdit, clearDepartmentLeaderNameDraft, departmentLeaderNameInputs, updateDepartment, value.departments]);

  const handleUploadOrganizationIntroDocument = useCallback(async () => {
    if (!canEdit || !onUploadIntroDocument) return;
    const document = await onUploadIntroDocument(`${organizationName || '当前组织'}组织介绍`);
    if (!document) return;
    setPendingOrganizationIntroDocument(document);
    showToast('组织介绍已添加，点击右上角对勾保存');
  }, [canEdit, onUploadIntroDocument, organizationName, showToast]);

  const handleUploadDepartmentIntroDocument = useCallback(async (department: TreeDepartmentNode) => {
    if (!canEdit || !onUploadIntroDocument) return;
    const document = await onUploadIntroDocument(`${department.name || '部门'}介绍`);
    if (!document) return;
    setPendingDepartmentIntroDocuments((previous) => ({
      ...previous,
      [department.id]: document,
    }));
    showToast('部门介绍已添加，点击卡片右上角对勾保存');
  }, [canEdit, onUploadIntroDocument, showToast]);

  const finishEditing = useCallback(() => {
    setEditingNodeId(null);
    setEditingField(null);
    setEditingText('');
    clearEditingDraft();
  }, [clearEditingDraft]);

  const applyActiveEditingDraft = useCallback((baseValue: OrgModelSettings, targetNodeId?: string) => {
    const nextValue = editingText.trim();
    if (!editingNodeId || !editingField || !nextValue) {
      return baseValue;
    }
    if (targetNodeId && editingNodeId !== targetNodeId) {
      return baseValue;
    }
    if (editingNodeId === tree.id && editingField === 'name') {
      return applyOrganizationNameDraft(baseValue, nextValue);
    }
    const targetDepartment = activeDepartments.find((item) => item.id === editingNodeId);
    if (targetDepartment) {
      if (editingField === 'name') {
        return applyDepartmentNameDraft(baseValue, editingNodeId, nextValue);
      }
      return applyDepartmentLeaderNameDrafts(baseValue, { [editingNodeId]: nextValue });
    }
    const targetRole = activeRoles.find((item) => item.id === editingNodeId);
    if (targetRole && editingField === 'name') {
      return applyRoleNameDraft(baseValue, editingNodeId, nextValue);
    }
    return baseValue;
  }, [activeDepartments, activeRoles, editingField, editingNodeId, editingText, tree.id]);

  const handleSaveEdit = useCallback(() => {
    const nextValue = applyActiveEditingDraft(value);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    finishEditing();
  }, [applyActiveEditingDraft, finishEditing, onChange, value]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
    if (isComposingKeyEvent(event, textCompositionRef)) return;
    if (event.key === 'Enter') {
      handleSaveEdit();
    }
    if (event.key === 'Escape') {
      finishEditing();
    }
  }, [finishEditing, handleSaveEdit]);

  const startEditing = useCallback((nodeId: string, field: EditableField, currentText: string) => {
    if (!canEdit) return;
    const nextText = currentText || '';
    setEditingNodeId(nodeId);
    setEditingField(field);
    setEditingText(nextText);
    updateInputDrafts((current) => ({
      ...current,
      editingNodeId: nodeId,
      editingField: field,
      editingText: nextText,
    }));
  }, [canEdit, updateInputDrafts]);

  const handleAddDepartment = useCallback(() => {
    if (!canEdit) return;
    const nextIndex = value.departments.length;
    const nextDepartment: OrgDepartmentSettings = {
      id: nextUiId('department'),
      name: `新部门 ${nextIndex + 1}`,
      color: departmentColor(nextIndex),
      leaderUserId: null,
      leaderName: '',
      introDocument: null,
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

  const handleSaveOrganizationCard = useCallback(async () => {
    if (!canEdit || isSaving) return;
    let nextValue = applyOrganizationNameDraft(value, organizationNameInput);
    nextValue = applyOrganizationLeaderNameDraft(nextValue, organizationLeaderNameInput);
    if (pendingOrganizationIntroDocument) {
      nextValue = applyOrganizationIntroDocumentDraft(nextValue, pendingOrganizationIntroDocument);
    }
    nextValue = applyActiveEditingDraft(nextValue, tree.id);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setPendingOrganizationIntroDocument(null);
    setOrganizationNameInput(nextValue.organization.name);
    setOrganizationLeaderNameInput(visibleLeaderNameInput(nextValue.organization.leaderName));
    clearOrganizationNameDraft();
    clearOrganizationLeaderNameDraft();
    if (editingNodeId === tree.id) {
      finishEditing();
    }
    const saved = await onSave(nextValue);
    if (saved !== false) {
      showToast('当前组织卡片已保存');
    }
  }, [
    applyActiveEditingDraft,
    canEdit,
    clearOrganizationLeaderNameDraft,
    clearOrganizationNameDraft,
    editingNodeId,
    finishEditing,
    isSaving,
    onChange,
    onSave,
    organizationLeaderNameInput,
    organizationNameInput,
    pendingOrganizationIntroDocument,
    showToast,
    tree.id,
    value,
  ]);

  const handleSaveDepartmentCard = useCallback((departmentId: string) => {
    if (!canEdit || isSaving) return;
    let nextValue = value;
    if (Object.prototype.hasOwnProperty.call(departmentLeaderNameInputs, departmentId)) {
      nextValue = applyDepartmentLeaderNameDrafts(nextValue, {
        [departmentId]: departmentLeaderNameInputs[departmentId],
      });
    }
    if (pendingDepartmentIntroDocuments[departmentId]) {
      nextValue = applyDepartmentIntroDocumentDraft(nextValue, departmentId, pendingDepartmentIntroDocuments[departmentId]);
    }
    nextValue = applyActiveEditingDraft(nextValue, departmentId);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setDepartmentLeaderNameInputs((previous) => {
      if (!(departmentId in previous)) return previous;
      const next = { ...previous };
      delete next[departmentId];
      return next;
    });
    setPendingDepartmentIntroDocuments((previous) => {
      if (!(departmentId in previous)) return previous;
      const next = { ...previous };
      delete next[departmentId];
      return next;
    });
    clearDepartmentLeaderNameDraft(departmentId);
    if (editingNodeId === departmentId) {
      finishEditing();
    }
    void onSave(nextValue);
    showToast('部门卡片已保存');
  }, [
    applyActiveEditingDraft,
    canEdit,
    clearDepartmentLeaderNameDraft,
    departmentLeaderNameInputs,
    editingNodeId,
    finishEditing,
    isSaving,
    onChange,
    onSave,
    pendingDepartmentIntroDocuments,
    showToast,
    value,
  ]);

  const handleSaveRoleCard = useCallback((roleId: string) => {
    if (!canEdit || isSaving) return;
    const nextValue = applyActiveEditingDraft(value, roleId);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    if (editingNodeId === roleId) {
      finishEditing();
    }
    void onSave(nextValue);
    showToast('岗位卡片已保存');
  }, [
    applyActiveEditingDraft,
    canEdit,
    editingNodeId,
    finishEditing,
    isSaving,
    onChange,
    onSave,
    showToast,
    value,
  ]);

  const handleSave = useCallback(async () => {
    const hasDepartmentLeaderDrafts = Object.keys(departmentLeaderNameInputs).length > 0;
    let nextValue = applyOrganizationNameDraft(value, organizationNameInput);
    nextValue = applyOrganizationLeaderNameDraft(nextValue, organizationLeaderNameInput);
    nextValue = applyDepartmentLeaderNameDrafts(nextValue, departmentLeaderNameInputs);
    if (pendingOrganizationIntroDocument) {
      nextValue = applyOrganizationIntroDocumentDraft(nextValue, pendingOrganizationIntroDocument);
    }
    Object.entries(pendingDepartmentIntroDocuments).forEach(([departmentId, document]) => {
      nextValue = applyDepartmentIntroDocumentDraft(nextValue, departmentId, document);
    });
    nextValue = applyActiveEditingDraft(nextValue);
    if (nextValue !== value) {
      onChange(nextValue);
    }
    setOrganizationNameInput(nextValue.organization.name);
    setOrganizationLeaderNameInput(visibleLeaderNameInput(nextValue.organization.leaderName));
    if (hasDepartmentLeaderDrafts) {
      setDepartmentLeaderNameInputs({});
    }
    setPendingOrganizationIntroDocument(null);
    setPendingDepartmentIntroDocuments({});
    clearInputDrafts();
    finishEditing();
    const saved = await onSave(nextValue);
    if (saved !== false) {
      showToast('组织结构已保存');
      // 保存成功后自动退出编辑模式：右上角的 X / + / 对勾按钮一齐隐藏，
      // 用户视觉上明确知道"这一轮编辑已完成"，下次还要改再点"编辑组织"。
      setIsEditingMode(false);
    }
  }, [applyActiveEditingDraft, clearInputDrafts, departmentLeaderNameInputs, finishEditing, onChange, onSave, organizationLeaderNameInput, organizationNameInput, pendingDepartmentIntroDocuments, pendingOrganizationIntroDocument, showToast, value]);

  const handleOpenResetConfirm = useCallback(() => {
    if (!canEdit || isSaving) return;
    setResetConfirmText('');
    setResetConfirmOpen(true);
  }, [canEdit, isSaving]);

  const handleResetOrganizationSetup = useCallback(() => {
    if (!canEdit || isSaving) return;
    if (resetConfirmText.trim() !== '重新搭建') {
      showToast('请输入“重新搭建”确认');
      return;
    }
    const nextValue = buildEmptyOrgModel(value);
    onChange(nextValue);
    setOrganizationNameInput('');
    setOrganizationLeaderNameInput('');
    setDepartmentLeaderNameInputs({});
    setPendingOrganizationIntroDocument(null);
    setPendingDepartmentIntroDocuments({});
    clearInputDrafts();
    setActiveView('tree');
    setEditingNodeId(null);
    setEditingField(null);
    setResetConfirmOpen(false);
    setResetConfirmText('');
    void onSave(nextValue);
    showToast('组织搭建已清空');
  }, [canEdit, clearInputDrafts, isSaving, onChange, onSave, resetConfirmText, showToast, value]);

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

  const organizationCardDirty = organizationNameInput.trim() !== value.organization.name
    || visibleLeaderNameInput(organizationLeaderNameInput) !== visibleLeaderNameInput(value.organization.leaderName)
    || introDocumentChanged(pendingOrganizationIntroDocument, value.organization.introDocument)
    || (editingNodeId === tree.id && editingText.trim().length > 0 && editingText.trim() !== tree.name);

  return (
    <div className="space-y-6">
      {toast ? (
        <div className="fixed top-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-gray-900/90 px-5 py-2.5 text-[13px] font-medium text-white shadow-lg">
          {toast}
        </div>
      ) : null}

      {resetConfirmOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/30 px-4 backdrop-blur-sm">
          <div className="w-full max-w-[440px] rounded-[24px] border border-gray-100 bg-white p-6 shadow-[0_28px_90px_rgba(15,23,42,0.18)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-rose-50 text-rose-500">
                  <Trash2 size={18} />
                </div>
                <h3 className="mt-4 text-[18px] font-bold text-gray-900">删除当前组织搭建</h3>
                <p className="mt-2 text-[13px] leading-6 text-gray-500">
                  会清空部门、岗位、负责人、规则、计划和邀请码，保留组织身份与当前账号。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setResetConfirmOpen(false)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-5">
              <label className="text-[12px] font-bold text-gray-500">
                输入“重新搭建”确认
              </label>
              <input
                autoFocus
                value={resetConfirmText}
                onCompositionStart={handleTextCompositionStart}
                onCompositionEnd={handleTextCompositionEnd}
                onChange={(event) => setResetConfirmText(event.target.value)}
                onKeyDown={(event) => {
                  if (isComposingKeyEvent(event, textCompositionRef)) return;
                  if (event.key === 'Enter') {
                    handleResetOrganizationSetup();
                  }
                }}
                className="mt-2 w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[14px] font-medium text-gray-900 outline-none transition focus:border-rose-300 focus:bg-white"
              />
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setResetConfirmOpen(false)}
                className="rounded-full border border-gray-200 bg-white px-5 py-2.5 text-[13px] font-bold text-gray-600 transition hover:border-gray-300 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleResetOrganizationSetup}
                disabled={isSaving || resetConfirmText.trim() !== '重新搭建'}
                className="inline-flex items-center gap-2 rounded-full bg-rose-500 px-5 py-2.5 text-[13px] font-bold text-white transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 size={14} />
                确认删除
              </button>
            </div>
          </div>
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
              isEditingMode ? (
                <>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="inline-flex items-center gap-2 rounded-full bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.25)] transition hover:bg-[#4A63CF] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Save size={14} />
                    {isSaving ? '保存中' : '保存修改'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsEditingMode(false)}
                    disabled={isSaving}
                    className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-3 text-[13px] font-bold text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <X size={14} />
                    退出编辑
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenResetConfirm}
                    disabled={isSaving}
                    className="inline-flex items-center gap-1.5 rounded-full border border-rose-100 bg-white px-3 py-2 text-[12px] font-medium text-rose-500 transition hover:border-rose-200 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                    title="谨慎操作：会删除整个组织搭建"
                  >
                    <Trash2 size={12} />
                    删除搭建
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsEditingMode(true)}
                  className="inline-flex items-center gap-2 rounded-full bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.25)] transition hover:bg-[#4A63CF]"
                >
                  <Pencil size={14} />
                  编辑组织
                </button>
              )
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
                  className="relative z-10 flex min-w-[260px] flex-col gap-3 rounded-2xl border-2 border-[#5B7BFE]/30 bg-gradient-to-br from-[#EEF3FF] to-white px-5 py-4 pr-12 shadow-sm"
                >
                  {canModify ? (
                    <CardSaveButton
                      active={organizationCardDirty}
                      disabled={isSaving}
                      label="保存当前组织卡片"
                      onClick={handleSaveOrganizationCard}
                    />
                  ) : null}
                  <div className="flex items-center gap-3">
                    <Building2 className="text-[#5B7BFE]" size={20} />
                    {canModify ? (
                      <input
                        value={organizationNameInput}
                        onCompositionStart={handleTextCompositionStart}
                        onCompositionEnd={handleTextCompositionEnd}
                        onChange={(event) => setOrganizationNameDraft(event.target.value)}
                        onBlur={commitOrganizationNameInput}
                        onKeyDown={(event) => {
                          if (isComposingKeyEvent(event, textCompositionRef)) return;
                          if (event.key === 'Enter') {
                            event.currentTarget.blur();
                          }
                          if (event.key === 'Escape') {
                            setOrganizationNameInput(value.organization.name);
                            clearOrganizationNameDraft();
                            event.currentTarget.blur();
                          }
                        }}
                        placeholder="请输入组织名称"
                        className="w-full min-w-[180px] rounded-xl border border-[#DCE4FF] bg-white/90 px-3 py-2 text-[15px] font-bold text-gray-900 outline-none transition placeholder:text-gray-300 focus:border-[#5B7BFE] focus:bg-white"
                      />
                    ) : (
                      <span className="text-[16px] font-bold text-gray-900">
                        {value.organization.name.trim() || '未命名组织'}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-[11px] font-medium text-gray-400">负责人</span>
                    {canModify ? (
                      <LeaderPicker
                        value={{
                          userId: value.organization.leaderUserId ?? null,
                          displayName: visibleLeaderNameInput(value.organization.leaderName),
                        }}
                        employees={employees}
                        onSelect={handleSelectOrganizationLeader}
                        placeholder="从同事中选负责人"
                      />
                    ) : (
                      <span className="rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700">
                        {visibleLeaderNameInput(value.organization.leaderName) || '待填写负责人'}
                      </span>
                    )}
                  </div>
                  <IntroDocumentAction
                    canEdit={canModify}
                    disabled={isSaving || !onUploadIntroDocument}
                    document={value.organization.introDocument}
                    label="组织介绍"
                    onUpload={() => void handleUploadOrganizationIntroDocument()}
                    pendingDocument={pendingOrganizationIntroDocument}
                  />
	                </div>

	                <div className="relative flex flex-col gap-6">
	                  {tree.children.map((department, index) => {
	                    const isEditingDepartmentName = editingNodeId === department.id && editingField === 'name';
	                    const departmentSettings = value.departments.find((item) => item.id === department.id);
	                    const departmentBindings = bindingsByDepartmentId.get(department.id) || [];
	                    const pendingDepartmentIntroDocument = pendingDepartmentIntroDocuments[department.id] || null;
	                    const departmentLeaderNameValue = departmentLeaderNameInputs[department.id] ?? department.leaderName ?? '';
	                    const hasDepartmentLeaderDraft = Object.prototype.hasOwnProperty.call(departmentLeaderNameInputs, department.id);
	                    const departmentForCount = departmentSettings && hasDepartmentLeaderDraft
	                      ? { ...departmentSettings, leaderUserId: null, leaderName: departmentLeaderNameValue }
	                      : departmentSettings;
	                    const memberCount = departmentForCount
	                      ? countDepartmentMembers(departmentForCount, departmentBindings)
	                      : departmentBindings.length;
	                    const departmentCardDirty = (
	                      isEditingDepartmentName
	                      && editingText.trim().length > 0
	                      && editingText.trim() !== department.name
	                    ) || (
	                      hasDepartmentLeaderDraft
	                      && visibleLeaderNameInput(departmentLeaderNameValue) !== visibleLeaderNameInput(department.leaderName)
	                    ) || introDocumentChanged(pendingDepartmentIntroDocument, departmentSettings?.introDocument);
                    const inviteCode = buildDepartmentInviteCode(department.id, {
                      organizationId: value.organization.organizationId,
	                      organizationName,
	                      departmentName: department.name,
	                      order: index,
                    });
                    return (
                      <div key={department.id} className="flex items-center gap-10">
                        <div
                          id={`node-${department.id}`}
                          className="group relative z-10 flex min-w-[170px] flex-col gap-1.5 rounded-2xl border border-gray-200 bg-white px-4 py-3 pr-10 shadow-sm transition hover:border-[#5B7BFE]/40"
                          style={{ boxShadow: `0 12px 28px ${tint(department.color, '16')}` }}
                        >
                          {canModify ? (
                            <CardSaveButton
                              active={departmentCardDirty}
                              disabled={isSaving}
                              label={`保存${department.name}卡片`}
                              onClick={() => handleSaveDepartmentCard(department.id)}
                            />
                          ) : null}
                          {canModify ? (
                            <button
                              type="button"
                              onClick={() => handleDeleteDepartment(department.id)}
                              className="absolute -right-2 -top-2 rounded-full border border-rose-200 bg-white p-0.5 text-rose-400 shadow-sm transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-500"
                              title="删除该部门"
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
                                onCompositionStart={handleTextCompositionStart}
                                onCompositionEnd={handleTextCompositionEnd}
                                onChange={(event) => setEditingTextDraft(event.target.value)}
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
                            {canModify ? (
                              <LeaderPicker
                                value={{
                                  userId: department.leaderUserId ?? null,
                                  displayName: visibleLeaderNameInput(department.leaderName),
                                }}
                                employees={employees}
                                onSelect={(employee) => handleSelectDepartmentLeader(department.id, employee)}
                                placeholder="选负责人"
                                compact
                              />
                            ) : (
                              <span className="text-[11px] text-gray-500">{department.leadName || '待设置'}</span>
                            )}
                          </div>

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
                          <IntroDocumentAction
                            canEdit={canModify}
                            compact
                            disabled={isSaving || !onUploadIntroDocument}
                            document={departmentSettings?.introDocument}
                            label="部门介绍"
                            onUpload={() => void handleUploadDepartmentIntroDocument(department)}
                            pendingDocument={pendingDepartmentIntroDocument}
                          />
                        </div>

                        <div className="relative flex flex-col gap-3">
                          {department.children.map((role) => {
                            const isEditingRoleName = editingNodeId === role.id && editingField === 'name';
                            const roleCardDirty = isEditingRoleName
                              && editingText.trim().length > 0
                              && editingText.trim() !== role.name;
                            // 通过 bindings 反查持岗人
                            const holderBinding = value.bindings.find((b) => b.primaryRoleId === role.id);
                            const holderEmployee = holderBinding
                              ? employees.find((e) => e.id === holderBinding.userId) ?? null
                              : null;
                            return (
                              <div
                                id={`node-${role.id}`}
                                key={role.id}
                                className="group relative z-10 min-w-[180px] rounded-xl border border-gray-100 bg-gray-50/90 px-3 py-2 pr-8 transition hover:border-gray-200"
                              >
                                {canModify ? (
                                  <CardSaveButton
                                    active={roleCardDirty}
                                    className="right-1.5 top-1.5 h-5 w-5"
                                    disabled={isSaving}
                                    iconSize={10}
                                    label={`保存${role.name}卡片`}
                                    onClick={() => handleSaveRoleCard(role.id)}
                                  />
                                ) : null}
                                {canModify ? (
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteRole(role.id)}
                                    className="absolute -right-1.5 -top-1.5 rounded-full border border-rose-200 bg-white p-0.5 text-rose-400 shadow-sm transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-500"
                                    title="删除该岗位"
                                  >
                                    <X size={10} />
                                  </button>
                                ) : null}

                                {/* 岗位名（可编辑） */}
                                {isEditingRoleName ? (
                                  <input
                                    autoFocus
                                    value={editingText}
                                    onCompositionStart={handleTextCompositionStart}
                                    onCompositionEnd={handleTextCompositionEnd}
                                    onChange={(event) => setEditingTextDraft(event.target.value)}
                                    onBlur={handleSaveEdit}
                                    onKeyDown={handleKeyDown}
                                    className="w-full border-b border-gray-300 bg-transparent text-center text-[12px] font-medium text-gray-700 outline-none focus:border-[#5B7BFE]"
                                  />
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => canModify && startEditing(role.id, 'name', role.name)}
                                    disabled={!canModify}
                                    className="w-full text-center text-[12px] font-medium text-gray-600 transition hover:text-[#5B7BFE] disabled:cursor-default disabled:hover:text-gray-600"
                                  >
                                    {role.name}
                                  </button>
                                )}

                                {/* 持岗人（下拉选员工） */}
                                <div className="mt-1.5 flex items-center justify-center gap-1">
                                  {canModify ? (
                                    <LeaderPicker
                                      value={{
                                        userId: holderEmployee?.id ?? null,
                                        displayName: holderEmployee?.fullName ?? '',
                                      }}
                                      employees={employees}
                                      onSelect={(employee) => handleSelectRoleHolder(role.id, employee)}
                                      placeholder="选员工"
                                      compact
                                    />
                                  ) : (
                                    <span className="text-[11px] text-gray-500">
                                      {holderEmployee?.fullName || '待指派'}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}

                          {canModify ? (
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

                  {canModify ? (
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
                    organizationId: value.organization.organizationId,
                    organizationName,
                    departmentName: department.name,
                    order: index,
                  });
                  const departmentSettings = value.departments.find((item) => item.id === department.id);
                  const departmentBindings = bindingsByDepartmentId.get(department.id) || [];
                  const joinedCount = departmentSettings
                    ? countDepartmentMembers(departmentSettings, departmentBindings)
                    : departmentBindings.length;
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

type CardSaveButtonProps = {
  active: boolean;
  disabled?: boolean;
  iconSize?: number;
  label: string;
  onClick: () => void;
  className?: string;
};

type IntroDocumentActionProps = {
  canEdit: boolean;
  compact?: boolean;
  disabled?: boolean;
  document?: OrgIntroDocumentSettings | null;
  label: string;
  onUpload: () => void;
  pendingDocument?: OrgIntroDocumentSettings | null;
};

function IntroDocumentAction({
  canEdit,
  compact = false,
  disabled = false,
  document,
  label,
  onUpload,
  pendingDocument,
}: IntroDocumentActionProps) {
  const activeDocument = pendingDocument || document || null;
  const hasPendingDocument = Boolean(pendingDocument);
  const fileName = activeDocument?.fileName?.trim() || '';
  const buttonText = fileName ? '替换' : '上传';
  return (
    <div className={`flex min-w-0 items-center gap-2 ${compact ? 'pl-6 pt-1' : 'pl-8'}`}>
      <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-bold text-gray-400">
        <FileText size={compact ? 11 : 12} />
        {label}
      </span>
      {fileName ? (
        <span
          title={fileName}
          className={`min-w-0 truncate rounded-full px-2 py-1 text-[10px] font-bold ${
            hasPendingDocument ? 'bg-blue-50 text-[#4A63CF]' : 'bg-gray-100 text-gray-500'
          }`}
        >
          {hasPendingDocument ? '待保存 · ' : ''}{fileName}
        </span>
      ) : (
        <span className="text-[10px] font-medium text-gray-300">未上传</span>
      )}
      {canEdit ? (
        <button
          type="button"
          disabled={disabled}
          onClick={onUpload}
          className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[#DCE4FF] bg-white px-2 py-1 text-[10px] font-bold text-[#5B7BFE] transition hover:border-[#5B7BFE]/60 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <UploadCloud size={11} />
          {buttonText}
        </button>
      ) : null}
    </div>
  );
}

function CardSaveButton({
  active,
  disabled = false,
  iconSize = 13,
  label,
  onClick,
  className = 'right-3 top-3 h-7 w-7',
}: CardSaveButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className={`absolute inline-flex items-center justify-center rounded-full border shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white shadow-[0_8px_18px_rgba(91,123,254,0.24)]'
          : 'border-[#DCE4FF] bg-white text-[#5B7BFE] opacity-75 hover:border-[#5B7BFE]/60 hover:opacity-100'
      } ${className}`}
    >
      <Check size={iconSize} strokeWidth={2.6} />
    </button>
  );
}

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


type LeaderPickerProps = {
  value: { userId: string | null; displayName: string };
  employees: EmployeeRecord[];
  onSelect: (employee: EmployeeRecord | null) => void;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
};

function LeaderPicker({
  value,
  employees,
  onSelect,
  placeholder = '选择负责人',
  compact = false,
  disabled = false,
}: LeaderPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const buttonRef = useRef<HTMLButtonElement>(null);
  // dropdown 位置 — 通过 Portal 渲染到 body 后，需用 fixed 定位
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  const candidates = useMemo(
    () =>
      employees.filter(
        (e) =>
          e.accountStatus === 'approved'
          && (e.membershipStatus ?? 'approved') === 'approved',
      ),
    [employees],
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return candidates;
    return candidates.filter(
      (e) =>
        e.fullName.toLowerCase().includes(needle)
        || (e.email || '').toLowerCase().includes(needle),
    );
  }, [candidates, search]);

  // 计算 dropdown 的 fixed 位置（按钮下方 4px，右边贴齐 viewport）
  const computePosition = useCallback(() => {
    if (!buttonRef.current) return null;
    const rect = buttonRef.current.getBoundingClientRect();
    const dropdownWidth = 260;
    const gap = 6;
    // 默认贴按钮左侧；若右溢出，右对齐
    let left = rect.left;
    if (left + dropdownWidth > window.innerWidth - 12) {
      left = Math.max(12, window.innerWidth - dropdownWidth - 12);
    }
    return { top: rect.bottom + gap, left };
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    setPosition(computePosition());
  }, [open, computePosition]);

  // 监听 scroll / resize 重新算位置（dropdown 跟随按钮）
  useEffect(() => {
    if (!open) return;
    const recalc = () => setPosition(computePosition());
    window.addEventListener('scroll', recalc, true);
    window.addEventListener('resize', recalc);
    return () => {
      window.removeEventListener('scroll', recalc, true);
      window.removeEventListener('resize', recalc);
    };
  }, [open, computePosition]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const close = useCallback(() => {
    setOpen(false);
    setSearch('');
  }, []);

  const handleSelect = useCallback(
    (employee: EmployeeRecord | null) => {
      onSelect(employee);
      close();
    },
    [close, onSelect],
  );

  const displayLabel = value.displayName?.trim() || '';

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className={
          compact
            ? 'inline-flex min-w-[100px] items-center gap-1 rounded-full border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 outline-none transition hover:border-[#5B7BFE]/50 disabled:cursor-not-allowed disabled:opacity-50'
            : 'inline-flex min-w-[160px] items-center gap-1 rounded-full border border-[#DCE4FF] bg-white px-3 py-1.5 text-[11px] font-medium text-gray-700 outline-none transition hover:border-[#5B7BFE] disabled:cursor-not-allowed disabled:opacity-50'
        }
      >
        <span className={displayLabel ? '' : 'text-gray-300'}>{displayLabel || placeholder}</span>
        <ChevronDown size={10} className="ml-auto opacity-60" />
      </button>
      {open && position
        ? createPortal(
            <>
              {/* 毛玻璃 backdrop — 覆盖整个屏幕，点击即关闭 */}
              <div
                className="fixed inset-0 z-[100] bg-gray-900/15 backdrop-blur-[3px] transition-opacity"
                onClick={close}
                aria-hidden
              />
              {/* dropdown 面板 — 在 backdrop 之上 */}
              <div
                role="dialog"
                style={{ top: position.top, left: position.left }}
                className="fixed z-[101] w-[260px] rounded-2xl border border-gray-100 bg-white p-2 shadow-2xl ring-1 ring-black/5"
              >
                <input
                  type="text"
                  autoFocus
                  placeholder="搜索姓名或邮箱..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="mb-1.5 w-full rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-[12px] outline-none transition focus:border-[#5B7BFE] focus:bg-white"
                />
                <div className="max-h-[260px] overflow-y-auto">
                  <button
                    type="button"
                    onClick={() => handleSelect(null)}
                    className="w-full rounded-lg px-2 py-1.5 text-left text-[11px] font-medium text-gray-400 transition hover:bg-gray-50"
                  >
                    清空（不指定负责人）
                  </button>
                  {filtered.length === 0 ? (
                    <p className="px-2 py-2 text-[10px] text-gray-400">
                      无匹配同事 — 请先让 ta 在系统注册
                    </p>
                  ) : (
                    filtered.map((e) => (
                      <button
                        key={e.id}
                        type="button"
                        onClick={() => handleSelect(e)}
                        className={`w-full rounded-lg px-2 py-1.5 text-left text-[11px] transition hover:bg-[#EEF3FF] ${
                          e.id === value.userId ? 'bg-[#EEF3FF] font-bold text-[#4A63CF]' : 'text-gray-700'
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span>{e.fullName}</span>
                          {e.primaryRole === 'admin' ? (
                            <span className="rounded-full bg-[#FFF7E0] px-1.5 py-0.5 text-[9px] font-bold text-[#A87A1F]">
                              admin
                            </span>
                          ) : null}
                        </div>
                        <div className="text-[10px] text-gray-400">{e.email}</div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}
