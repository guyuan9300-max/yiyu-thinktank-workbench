import React, { useEffect, useMemo, useState } from 'react';
import { ClipboardList, ChevronDown, ChevronRight, ExternalLink, Plus, RefreshCw, X, Trash2, Sparkles } from 'lucide-react';

import { getTasksForPlanItem, parseDepartmentPlan } from '../../lib/api';
import type {
  OrgDepartmentPlanItemSettings,
  OrgDepartmentPlanSettings,
  OrgDepartmentPlanItemStatus,
  OrgModelSettings,
  SessionUser,
  Task,
} from '../../../shared/types';

interface Props {
  value: OrgModelSettings;
  currentUser: SessionUser | null;
  onSavePlan?: (plan: OrgDepartmentPlanSettings) => Promise<void> | void;
}

interface DepartmentRow {
  scopeId: string;          // department.id, or ORG_LEVEL_ID for organization-wide
  scopeName: string;        // department name, or organization name
  scopeKind: 'org' | 'department';
  leaderName: string;
  latestPlan: OrgDepartmentPlanSettings | null;
  allPlansCount: number;
  itemCount: number;
  doneCount: number;
  unfinished: number;
  completeness: number;
}

const ORG_LEVEL_ID = '__org__';

type CycleType = 'month' | 'quarter' | 'year' | 'week' | 'custom';

interface DraftItem {
  id: string;
  title: string;
  statement: string;
  expectedOutput: string;
  status: OrgDepartmentPlanItemStatus;
}

const CYCLE_LABELS: Record<CycleType, string> = {
  month: '月度',
  quarter: '季度',
  year: '年度',
  week: '周',
  custom: '自定义',
};

function defaultPeriodValue(cycle: CycleType): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  switch (cycle) {
    case 'month':
      return `${y}-${String(m).padStart(2, '0')}`;
    case 'quarter':
      return `${y}-Q${Math.ceil(m / 3)}`;
    case 'year':
      return `${y}`;
    case 'week':
      // Approximate ISO week
      const start = new Date(y, 0, 1);
      const days = Math.floor((now.getTime() - start.getTime()) / 86400000);
      const week = Math.ceil((days + start.getDay() + 1) / 7);
      return `${y}-W${String(week).padStart(2, '0')}`;
    case 'custom':
      return '';
  }
}

function newDraftItem(): DraftItem {
  return {
    id: `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: '',
    statement: '',
    expectedOutput: '',
    status: 'active',
  };
}

/**
 * 把 weekLabel 转成可排序的 ISO 日期字符串，让月度/季度/年度/周混排时按真实时间序。
 *
 * 不修这个 bug：plans.sort((a,b) => b.weekLabel.localeCompare(a.weekLabel)) 用字符串比较会把
 * "2026-Q3" 排到 "2026-09" 之后（Q > 0~9 字符序），导致月度和季度同时存在时取到错误"最新"。
 */
function weekLabelToSortKey(label: string | null | undefined): string {
  const raw = (label || '').trim();
  if (!raw) return '0000-00-00';
  // YYYY  年度（取 1 月 1 日）
  if (/^\d{4}$/.test(raw)) return `${raw}-01-01`;
  // YYYY-Q1~4  季度起始月
  const qMatch = raw.match(/^(\d{4})-Q([1-4])$/i);
  if (qMatch) {
    const startMonth = (parseInt(qMatch[2], 10) - 1) * 3 + 1;
    return `${qMatch[1]}-${String(startMonth).padStart(2, '0')}-01`;
  }
  // YYYY-MM  月度
  if (/^\d{4}-\d{2}$/.test(raw)) return `${raw}-01`;
  // YYYY-W##  周（近似为年初 + (N-1)*7 天）
  const wMatch = raw.match(/^(\d{4})-W(\d{1,2})$/i);
  if (wMatch) {
    const y = parseInt(wMatch[1], 10);
    const w = parseInt(wMatch[2], 10);
    const start = new Date(y, 0, 1);
    const dayMs = 86400000;
    const dayOffset = (w - 1) * 7;
    const d = new Date(start.getTime() + dayOffset * dayMs);
    return d.toISOString().slice(0, 10);
  }
  // custom / 未知格式：原值参与字典序（至少同格式之间还是单调）
  return raw;
}

export function PlanWorkshopView({ value, currentUser, onSavePlan }: Props) {
  const isAdmin = currentUser?.primaryRole === 'admin';
  const userDeptId = currentUser?.departmentId ?? null;
  const organizationName = value.organization?.name?.trim() || '组织';
  const organizationLeaderName = value.organization?.leaderName?.trim() || '组织负责人未指派';

  const visibleDepartments = useMemo(() => {
    const allActive = value.departments.filter((d) => d.active !== false);
    if (isAdmin) return allActive;
    return allActive.filter((d) => d.id === userDeptId);
  }, [value.departments, isAdmin, userDeptId]);

  const canCreatePlan = Boolean(onSavePlan) && (isAdmin || (currentUser?.isDepartmentLead ?? false));
  // Only admin can author organization-level plans; department leads see them but can't create one.
  const canCreateOrgPlan = Boolean(onSavePlan) && isAdmin;

  const rows: DepartmentRow[] = useMemo(() => {
    const computeRow = (
      scopeId: string,
      scopeName: string,
      scopeKind: 'org' | 'department',
      leaderName: string,
      planFilter: (p: OrgDepartmentPlanSettings) => boolean,
    ): DepartmentRow => {
      const plans = value.departmentPlans.filter(planFilter);
      const latestPlan =
        [...plans].sort((a, b) => {
          // 按 weekLabel 真实时间序排（解决月度/季度混排字典序错排）
          const cmp = weekLabelToSortKey(b.weekLabel).localeCompare(weekLabelToSortKey(a.weekLabel));
          if (cmp !== 0) return cmp;
          // 同 period 时 fallback 用 updatedAt
          return (b.updatedAt || '').localeCompare(a.updatedAt || '');
        })[0] || null;
      const items = latestPlan?.items ?? [];
      const doneCount = items.filter((i) => i.status === 'done').length;
      const completeness = items.length > 0 ? Math.round((doneCount / items.length) * 100) : 0;
      const unfinished = items.length - doneCount;
      return {
        scopeId,
        scopeName,
        scopeKind,
        leaderName,
        latestPlan,
        allPlansCount: plans.length,
        itemCount: items.length,
        doneCount,
        unfinished,
        completeness,
      };
    };

    const result: DepartmentRow[] = [];
    // Organization-level row always first (visible to all roles so everyone can see org strategy)
    result.push(
      computeRow(
        ORG_LEVEL_ID,
        organizationName,
        'org',
        organizationLeaderName,
        (p) => !p.departmentId,
      ),
    );
    for (const dept of visibleDepartments) {
      result.push(
        computeRow(
          dept.id,
          dept.name,
          'department',
          dept.leaderName?.trim() || '未指派负责人',
          (p) => p.departmentId === dept.id,
        ),
      );
    }
    return result;
  }, [visibleDepartments, value.departmentPlans, organizationName, organizationLeaderName]);

  // Stats exclude the org-level row so they read as "department coverage" not "scope coverage".
  const deptRows = rows.filter((r) => r.scopeKind === 'department');
  const totalDepts = deptRows.length;
  const deptsWithPlan = deptRows.filter((r) => r.latestPlan !== null).length;
  const deptsWithoutPlan = totalDepts - deptsWithPlan;
  const totalUnfinished = deptRows.reduce((sum, r) => sum + r.unfinished, 0);
  const avgCompleteness = deptRows.length > 0
    ? Math.round(deptRows.reduce((sum, r) => sum + r.completeness, 0) / deptRows.length)
    : 0;

  const [expandedScopeId, setExpandedScopeId] = useState<string | null>(null);
  useEffect(() => {
    if (expandedScopeId) return;
    const firstWithPlan = rows.find((r) => r.latestPlan !== null);
    if (firstWithPlan) setExpandedScopeId(firstWithPlan.scopeId);
  }, [rows, expandedScopeId]);

  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [itemTasks, setItemTasks] = useState<Record<string, Task[]>>({});
  const [loadingItemId, setLoadingItemId] = useState<string | null>(null);
  const [itemTaskError, setItemTaskError] = useState<string | null>(null);

  const fetchTasksForItem = async (itemId: string) => {
    setItemTaskError(null);
    setLoadingItemId(itemId);
    try {
      const tasks = await getTasksForPlanItem(itemId);
      setItemTasks((prev) => ({ ...prev, [itemId]: tasks }));
    } catch (error) {
      setItemTaskError(error instanceof Error ? error.message : '加载挂接任务失败');
    } finally {
      setLoadingItemId(null);
    }
  };

  const handleSelectItem = async (itemId: string) => {
    setSelectedItemId(itemId);
    setItemTaskError(null);
    if (itemTasks[itemId]) return;
    await fetchTasksForItem(itemId);
  };

  const handleRefreshTasks = async () => {
    if (!selectedItemId) return;
    await fetchTasksForItem(selectedItemId);
  };

  const selectedItem: OrgDepartmentPlanItemSettings | null = useMemo(() => {
    if (!selectedItemId) return null;
    for (const plan of value.departmentPlans) {
      const found = (plan.items || []).find((it) => it.id === selectedItemId);
      if (found) return found;
    }
    return null;
  }, [selectedItemId, value.departmentPlans]);

  const selectedItemScopeName = useMemo(() => {
    if (!selectedItemId) return null;
    for (const plan of value.departmentPlans) {
      if ((plan.items || []).some((it) => it.id === selectedItemId)) {
        if (!plan.departmentId) return organizationName;
        return value.departments.find((d) => d.id === plan.departmentId)?.name || '未知部门';
      }
    }
    return null;
  }, [selectedItemId, value.departmentPlans, value.departments, organizationName]);

  // Find the plan that contains the currently-selected item (used for edit/delete).
  const selectedItemParentPlan: OrgDepartmentPlanSettings | null = useMemo(() => {
    if (!selectedItemId) return null;
    return value.departmentPlans.find((p) => (p.items || []).some((it) => it.id === selectedItemId)) || null;
  }, [selectedItemId, value.departmentPlans]);

  // ─── Edit / Delete state for the selected item ─────────────────────
  const [isEditingItem, setIsEditingItem] = useState(false);
  const [editDraft, setEditDraft] = useState<{ title: string; statement: string; expectedOutput: string; status: OrgDepartmentPlanItemStatus }>({
    title: '',
    statement: '',
    expectedOutput: '',
    status: 'active',
  });
  const [isMutatingItem, setIsMutatingItem] = useState(false);
  const [mutateError, setMutateError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // When user switches selected item, exit edit mode automatically.
  useEffect(() => {
    setIsEditingItem(false);
    setShowDeleteConfirm(false);
    setMutateError(null);
  }, [selectedItemId]);

  const handleEnterEdit = () => {
    if (!selectedItem) return;
    setEditDraft({
      title: selectedItem.title || '',
      statement: selectedItem.statement || '',
      expectedOutput: selectedItem.expectedOutput || '',
      status: selectedItem.status || 'active',
    });
    setMutateError(null);
    setIsEditingItem(true);
  };

  const handleCancelEdit = () => {
    if (isMutatingItem) return;
    setIsEditingItem(false);
    setMutateError(null);
  };

  const handleSaveEdit = async () => {
    if (!onSavePlan || !selectedItem || !selectedItemParentPlan) return;
    const trimmedTitle = editDraft.title.trim();
    if (!trimmedTitle) {
      setMutateError('计划项标题不能为空');
      return;
    }
    const now = new Date().toISOString();
    const updatedPlan: OrgDepartmentPlanSettings = {
      ...selectedItemParentPlan,
      items: (selectedItemParentPlan.items || []).map((it) =>
        it.id === selectedItem.id
          ? {
              ...it,
              title: trimmedTitle,
              statement: editDraft.statement.trim(),
              expectedOutput: editDraft.expectedOutput.trim(),
              status: editDraft.status,
              updatedAt: now,
            }
          : it,
      ),
      updatedAt: now,
    };
    setIsMutatingItem(true);
    setMutateError(null);
    try {
      await onSavePlan(updatedPlan);
      setIsEditingItem(false);
    } catch (error) {
      setMutateError(error instanceof Error ? error.message : '保存失败');
    } finally {
      setIsMutatingItem(false);
    }
  };

  const handleToggleItemDone = async () => {
    if (!onSavePlan || !selectedItem || !selectedItemParentPlan) return;
    const nextStatus: OrgDepartmentPlanItemStatus = selectedItem.status === 'done' ? 'active' : 'done';
    const now = new Date().toISOString();
    const updatedPlan: OrgDepartmentPlanSettings = {
      ...selectedItemParentPlan,
      items: (selectedItemParentPlan.items || []).map((it) =>
        it.id === selectedItem.id
          ? { ...it, status: nextStatus, updatedAt: now }
          : it,
      ),
      updatedAt: now,
    };
    setIsMutatingItem(true);
    setMutateError(null);
    try {
      await onSavePlan(updatedPlan);
    } catch (error) {
      setMutateError(error instanceof Error ? error.message : '更新失败');
    } finally {
      setIsMutatingItem(false);
    }
  };

  /**
   * 进入"删除确认"前先 ensure 任务列表已加载，让确认对话框能显示准确的
   * "挂接 N 条任务会失去关联"提示，避免用户看到模糊的"删除后不可恢复"
   * 就以为是干净删除（其实可能还挂着任务）。
   */
  const handleStartDelete = async () => {
    if (!selectedItemId) return;
    if (!itemTasks[selectedItemId]) {
      await fetchTasksForItem(selectedItemId);
    }
    setShowDeleteConfirm(true);
  };

  const handleDeleteItem = async () => {
    if (!onSavePlan || !selectedItem || !selectedItemParentPlan) return;
    const now = new Date().toISOString();
    const updatedPlan: OrgDepartmentPlanSettings = {
      ...selectedItemParentPlan,
      items: (selectedItemParentPlan.items || []).filter((it) => it.id !== selectedItem.id),
      updatedAt: now,
    };
    setIsMutatingItem(true);
    setMutateError(null);
    try {
      await onSavePlan(updatedPlan);
      setShowDeleteConfirm(false);
      setSelectedItemId(null);
    } catch (error) {
      setMutateError(error instanceof Error ? error.message : '删除失败');
    } finally {
      setIsMutatingItem(false);
    }
  };

  const canMutateSelectedItem = Boolean(onSavePlan) && (() => {
    if (!selectedItemParentPlan) return false;
    // Org-level plan: only admin can edit
    if (!selectedItemParentPlan.departmentId) return isAdmin;
    // Department plan: admin can edit any; others only their own department
    return isAdmin || selectedItemParentPlan.departmentId === userDeptId;
  })();

  // ─── Create-Plan Modal state ───────────────────────────────────────
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createDepartmentId, setCreateDepartmentId] = useState<string>('');
  const [createCycleType, setCreateCycleType] = useState<CycleType>('month');
  const [createPeriodValue, setCreatePeriodValue] = useState<string>(defaultPeriodValue('month'));
  const [createSummary, setCreateSummary] = useState('');
  const [pasteText, setPasteText] = useState('');
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [parseSummary, setParseSummary] = useState<string>('');
  const [parseConfidence, setParseConfidence] = useState<'low' | 'medium' | 'high' | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const openCreateModal = () => {
    // Admin defaults to org-level (季度/年度报告主体一般是组织); others default to own department.
    const defaultDept = isAdmin
      ? ORG_LEVEL_ID
      : (userDeptId || '');
    setCreateDepartmentId(defaultDept);
    setCreateCycleType('month');
    setCreatePeriodValue(defaultPeriodValue('month'));
    setCreateSummary('');
    setPasteText('');
    setDraftItems([newDraftItem()]);
    setCreateError(null);
    setParseSummary('');
    setParseConfidence(null);
    setIsCreateOpen(true);
  };

  const closeCreateModal = () => {
    if (isSaving || isParsing) return;
    setIsCreateOpen(false);
  };

  const handleParseText = async () => {
    if (!pasteText.trim()) {
      setCreateError('请先粘贴计划文本再进行解析');
      return;
    }
    setIsParsing(true);
    setCreateError(null);
    setParseSummary('');
    setParseConfidence(null);
    try {
      const isOrgLevel = createDepartmentId === ORG_LEVEL_ID;
      const dept = value.departments.find((d) => d.id === createDepartmentId);
      const result = await parseDepartmentPlan({
        text: pasteText,
        organizationName,
        scopeKind: isOrgLevel ? 'org' : 'department',
        scopeName: isOrgLevel ? organizationName : (dept?.name || ''),
        periodKey: createPeriodValue.trim(),
        cycleType: createCycleType,
      });
      if (!result.items || result.items.length === 0) {
        setCreateError('AI 没能从原文中提取出计划项。可手动调整原文后重试，或在下方直接逐条添加。');
        return;
      }
      const items: DraftItem[] = result.items.map((it) => ({
        ...newDraftItem(),
        title: it.title,
        statement: it.statement || '',
        expectedOutput: it.expectedOutput || '',
      }));
      setDraftItems(items);
      setParseSummary(result.summary || '');
      setParseConfidence(result.confidence || null);
      if (result.summary && !createSummary.trim()) {
        setCreateSummary(result.summary);
      }
    } catch (error) {
      setCreateError(error instanceof Error ? `AI 解析失败：${error.message}` : 'AI 解析失败');
    } finally {
      setIsParsing(false);
    }
  };

  const handleSubmitCreate = async () => {
    if (!onSavePlan) return;
    if (!createDepartmentId) { setCreateError('请选择计划主体（组织或部门）'); return; }
    if (!createPeriodValue.trim()) { setCreateError('请填写周期值'); return; }
    const validItems = draftItems.filter((it) => it.title.trim().length > 0);
    if (validItems.length === 0) { setCreateError('至少需要填写一条计划项标题'); return; }

    const now = new Date().toISOString();
    const resolvedDepartmentId = createDepartmentId === ORG_LEVEL_ID ? null : createDepartmentId;
    const plan: OrgDepartmentPlanSettings = {
      id: `plan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      departmentId: resolvedDepartmentId,
      weekLabel: createPeriodValue.trim(),
      ownerUserId: null,
      summary: createSummary.trim(),
      majorRisks: [],
      dependencies: [],
      status: 'active',
      items: validItems.map((it, index) => ({
        id: `item-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 6)}`,
        focusItemId: null,
        title: it.title.trim(),
        statement: it.statement.trim(),
        ownerUserId: null,
        status: it.status,
        expectedOutput: it.expectedOutput.trim(),
        sortOrder: index,
        updatedAt: now,
      })),
      updatedAt: now,
    };

    setIsSaving(true);
    setCreateError(null);
    try {
      await onSavePlan(plan);
      setIsCreateOpen(false);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="overflow-y-auto h-full">
      <div className="mx-auto max-w-7xl px-6 pt-6 pb-20 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <ClipboardList className="text-[#5B7BFE]" size={24} />
            <div>
              <h1 className="text-[22px] font-bold text-gray-900 tracking-tight">组织计划</h1>
              <p className="text-[12px] text-gray-500 mt-0.5">
                {isAdmin
                  ? '管理员视图 · 看全部部门当前周期计划与挂接任务'
                  : currentUser?.departmentName
                    ? `${currentUser.departmentName} · 部门负责人视图`
                    : '部门视图'}
              </p>
            </div>
          </div>
          {canCreatePlan && (
            <button
              type="button"
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] text-white px-4 py-2 text-[12px] font-bold shadow-sm hover:bg-[#4a6ae8] transition"
            >
              <Plus size={14} /> 新建计划
            </button>
          )}
        </div>

        {/* Overview cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="部门覆盖" value={`${deptsWithPlan}/${totalDepts}`} />
          <StatCard
            label="待制定计划"
            value={`${deptsWithoutPlan}`}
            highlight={deptsWithoutPlan > 0}
          />
          <StatCard label="未完成项总数" value={`${totalUnfinished}`} />
          <StatCard label="平均完成率" value={rows.length > 0 ? `${avgCompleteness}%` : '—'} />
        </div>

        {/* Department board with two-column expansion */}
        <div className="overflow-hidden rounded-[24px] border border-gray-100 bg-white shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="text-[15px] font-bold text-gray-900">部门看板</h2>
              <p className="text-[11px] text-gray-500 mt-1">
                点击部门展开当前周期的计划项；点击计划项可在右栏查看挂接的任务。
              </p>
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="p-8 text-center text-[12px] text-gray-400">
              {isAdmin ? '当前组织尚未建立部门' : '你的部门信息未配置，请联系管理员'}
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] divide-y lg:divide-y-0 lg:divide-x divide-gray-100">
              <div className="max-h-[640px] overflow-y-auto">
                {rows.map((row) => (
                  <DepartmentRowBlock
                    key={row.scopeId}
                    row={row}
                    expanded={expandedScopeId === row.scopeId}
                    onToggle={() => setExpandedScopeId(expandedScopeId === row.scopeId ? null : row.scopeId)}
                    selectedItemId={selectedItemId}
                    onSelectItem={handleSelectItem}
                  />
                ))}
              </div>

              <div className="max-h-[640px] overflow-y-auto bg-gray-50/40">
                {!selectedItem ? (
                  <div className="p-8 text-center text-[12px] text-gray-400">
                    选择左侧某条计划项，这里会列出挂到它的所有任务。
                  </div>
                ) : (
                  <div className="p-5 space-y-4">
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="text-[11px] text-gray-400 uppercase tracking-wider font-bold">
                            {selectedItemScopeName || '未知主体'} · 计划项
                          </div>
                          {isEditingItem ? (
                            <input
                              type="text"
                              value={editDraft.title}
                              onChange={(e) => setEditDraft((prev) => ({ ...prev, title: e.target.value }))}
                              placeholder="计划项标题"
                              autoFocus
                              className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[15px] font-bold text-gray-900 outline-none focus:border-[#5B7BFE]"
                            />
                          ) : (
                            <h3 className="mt-1 text-[15px] font-bold text-gray-900">{selectedItem.title}</h3>
                          )}
                        </div>
                        {canMutateSelectedItem && (
                          <div className="shrink-0 flex items-center gap-1.5">
                            {isEditingItem ? (
                              <>
                                <button
                                  type="button"
                                  onClick={handleCancelEdit}
                                  disabled={isMutatingItem}
                                  className="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                                >
                                  取消
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleSaveEdit()}
                                  disabled={isMutatingItem}
                                  className="rounded-lg bg-[#5B7BFE] text-white px-2.5 py-1 text-[11px] font-bold hover:bg-[#4a6ae8] disabled:opacity-60"
                                >
                                  {isMutatingItem ? '保存中…' : '保存'}
                                </button>
                              </>
                            ) : (
                              <>
                                {selectedItem.status === 'done' ? (
                                  <button
                                    type="button"
                                    onClick={() => void handleToggleItemDone()}
                                    disabled={isMutatingItem}
                                    className="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                                    title="取消已完成状态，恢复为进行中"
                                  >
                                    {isMutatingItem ? '处理中…' : '取消完成'}
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => void handleToggleItemDone()}
                                    disabled={isMutatingItem}
                                    className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-600 hover:bg-emerald-100 disabled:opacity-50"
                                    title="标记本条计划项为已完成"
                                  >
                                    {isMutatingItem ? '处理中…' : '完成'}
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={handleEnterEdit}
                                  disabled={isMutatingItem}
                                  className="rounded-lg border border-[#D7E0FF] bg-[#F8FAFF] px-2.5 py-1 text-[11px] font-bold text-[#5B7BFE] hover:bg-[#EEF2FF] disabled:opacity-50"
                                >
                                  编辑
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleStartDelete()}
                                  disabled={isMutatingItem}
                                  className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-bold text-rose-600 hover:bg-rose-100 disabled:opacity-50"
                                >
                                  删除
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </div>

                      {isEditingItem ? (
                        <div className="mt-2 space-y-2">
                          <textarea
                            value={editDraft.statement}
                            onChange={(e) => setEditDraft((prev) => ({ ...prev, statement: e.target.value }))}
                            placeholder="说明（可选）"
                            rows={2}
                            className="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] text-gray-700 outline-none focus:border-[#5B7BFE] resize-none"
                          />
                          <textarea
                            value={editDraft.expectedOutput}
                            onChange={(e) => setEditDraft((prev) => ({ ...prev, expectedOutput: e.target.value }))}
                            placeholder="期望产出（可选，如：输出一份 20 页方案 + 3 个 case study）"
                            rows={2}
                            className="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] text-gray-700 outline-none focus:border-[#5B7BFE] resize-none"
                          />
                          <select
                            value={editDraft.status}
                            onChange={(e) => setEditDraft((prev) => ({ ...prev, status: e.target.value as OrgDepartmentPlanItemStatus }))}
                            className="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] text-gray-700 outline-none focus:border-[#5B7BFE]"
                          >
                            <option value="active">进行中</option>
                            <option value="paused">暂停</option>
                            <option value="done">已完成</option>
                            <option value="dropped">已废弃</option>
                          </select>
                        </div>
                      ) : (
                        <>
                          {selectedItem.statement && (
                            <p className="mt-1.5 text-[12px] leading-5 text-gray-500">{selectedItem.statement}</p>
                          )}
                          <div className="mt-2 flex items-center gap-2 text-[10px]">
                            <PlanItemStatusBadge status={selectedItem.status} />
                            {selectedItem.expectedOutput && (
                              <span className="rounded-full bg-blue-50 px-2 py-0.5 font-bold text-blue-600">
                                期望产出：{selectedItem.expectedOutput}
                              </span>
                            )}
                          </div>
                        </>
                      )}

                      {mutateError && (
                        <div className="mt-2 rounded-lg bg-rose-50 border border-rose-200 px-2.5 py-1.5 text-[11px] text-rose-600">
                          {mutateError}
                        </div>
                      )}

                      {showDeleteConfirm && !isEditingItem && (
                        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5">
                          <p className="text-[12px] font-bold text-rose-700">确认删除这条计划项？</p>
                          <p className="mt-1 text-[11px] text-rose-600 leading-5">
                            删除后不可恢复{itemTasks[selectedItem.id] && itemTasks[selectedItem.id].length > 0
                              ? `；已挂接的 ${itemTasks[selectedItem.id].length} 条任务会失去与本计划项的关联（任务本身不会被删）`
                              : ''}。
                          </p>
                          <div className="mt-2 flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => setShowDeleteConfirm(false)}
                              disabled={isMutatingItem}
                              className="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                            >
                              取消
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDeleteItem()}
                              disabled={isMutatingItem}
                              className="rounded-lg bg-rose-500 text-white px-2.5 py-1 text-[11px] font-bold hover:bg-rose-600 disabled:opacity-60"
                            >
                              {isMutatingItem ? '删除中…' : '确认删除'}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-[12px] font-bold text-gray-700">挂接的任务</h4>
                        <div className="flex items-center gap-2">
                          {selectedItemId && itemTasks[selectedItemId] && (
                            <span className="text-[11px] text-gray-400">
                              共 {itemTasks[selectedItemId].length} 条
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={() => void handleRefreshTasks()}
                            disabled={loadingItemId === selectedItemId}
                            title="重新拉取挂接的任务（用户在「任务与日程」新挂任务后点这里刷新）"
                            className="inline-flex items-center justify-center rounded-md p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-40 transition"
                          >
                            <RefreshCw size={12} className={loadingItemId === selectedItemId ? 'animate-spin' : ''} />
                          </button>
                        </div>
                      </div>
                      {loadingItemId === selectedItemId ? (
                        <div className="text-[12px] text-gray-400">加载中…</div>
                      ) : itemTaskError ? (
                        <div className="text-[12px] text-rose-500">{itemTaskError}</div>
                      ) : !itemTasks[selectedItemId!] || itemTasks[selectedItemId!].length === 0 ? (
                        <div className="rounded-xl border border-dashed border-gray-200 bg-white p-4 text-center text-[11px] text-gray-400">
                          这条计划项还没有任何任务挂接。
                          <br />
                          可在「任务与日程」新建任务，在表单的"计划关联"模块里挂到此项。
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {itemTasks[selectedItemId!].map((task) => (
                            <PlanItemTaskCard key={task.id} task={task} />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ──────────────── Create-Plan Modal ──────────────── */}
      {isCreateOpen && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40 px-6"
          onClick={(e) => { if (e.target === e.currentTarget) closeCreateModal(); }}
        >
          <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl flex flex-col" style={{ maxHeight: '90vh' }}>
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
              <h3 className="text-[16px] font-bold text-gray-900">新建计划</h3>
              <button type="button" onClick={closeCreateModal} disabled={isSaving} className="text-gray-400 hover:text-gray-700 disabled:opacity-50">
                <X size={18} />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4 overflow-y-auto">
              {/* 部门 + 周期 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-gray-500 mb-1.5">计划主体</label>
                  <select
                    value={createDepartmentId}
                    onChange={(e) => setCreateDepartmentId(e.target.value)}
                    disabled={!isAdmin && visibleDepartments.length <= 1}
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none disabled:bg-gray-50 disabled:text-gray-400"
                  >
                    {canCreateOrgPlan && (
                      <option value={ORG_LEVEL_ID}>{organizationName}（组织级）</option>
                    )}
                    {visibleDepartments.map((dept) => (
                      <option key={dept.id} value={dept.id}>{dept.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-500 mb-1.5">周期类型</label>
                  <select
                    value={createCycleType}
                    onChange={(e) => {
                      const next = e.target.value as CycleType;
                      setCreateCycleType(next);
                      setCreatePeriodValue(defaultPeriodValue(next));
                    }}
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none"
                  >
                    {Object.entries(CYCLE_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-500 mb-1.5">
                    周期值
                    <span className="text-gray-400 font-normal ml-1">
                      {createCycleType === 'month' && '(YYYY-MM)'}
                      {createCycleType === 'quarter' && '(YYYY-Q1~Q4)'}
                      {createCycleType === 'year' && '(YYYY)'}
                      {createCycleType === 'week' && '(YYYY-W##)'}
                    </span>
                  </label>
                  <input
                    type="text"
                    value={createPeriodValue}
                    onChange={(e) => setCreatePeriodValue(e.target.value)}
                    placeholder={defaultPeriodValue(createCycleType) || '自定义'}
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none"
                  />
                </div>
              </div>

              {/* 计划描述（可选） */}
              <div>
                <label className="block text-[11px] font-bold text-gray-500 mb-1.5">计划总述（可选）</label>
                <input
                  type="text"
                  value={createSummary}
                  onChange={(e) => setCreateSummary(e.target.value)}
                  placeholder="例如：5 月主攻新客户开发与老客户复购"
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none"
                />
              </div>

              {/* 粘贴文本批量解析 */}
              <div className="rounded-2xl border border-dashed border-[#5B7BFE]/30 bg-[#5B7BFE]/5 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles size={14} className="text-[#5B7BFE]" />
                  <span className="text-[12px] font-bold text-[#5B7BFE]">AI 智能解析</span>
                  <span className="text-[10px] text-gray-400">把整段计划原文粘贴进来，AI 会合并多行说明、抽取期望产出、剥列表标记</span>
                </div>
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder={'粘贴整段计划原文，比如月度计划、季度报告、年度战略等。\n\nAI 会自动：\n• 把每条计划的标题、说明、期望产出拆到不同字段\n• 合并多行属于同一条的内容（不会按行拆碎）\n• 忽略章节标题、空白段落、序号'}
                  rows={6}
                  disabled={isParsing}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-[12px] outline-none resize-none disabled:bg-gray-50"
                />
                <div className="mt-2 flex items-center justify-between gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => void handleParseText()}
                    disabled={!pasteText.trim() || isParsing}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[#5B7BFE] text-white px-3 py-1.5 text-[12px] font-bold hover:bg-[#4a6ae8] transition disabled:opacity-50"
                  >
                    {isParsing ? (
                      <>
                        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                        AI 解析中…
                      </>
                    ) : (
                      <>
                        <Sparkles size={12} />
                        AI 解析为计划项
                      </>
                    )}
                  </button>
                  {parseConfidence && (
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className={`rounded-full px-2 py-0.5 font-bold ${
                        parseConfidence === 'high' ? 'bg-emerald-50 text-emerald-700'
                        : parseConfidence === 'medium' ? 'bg-amber-50 text-amber-700'
                        : 'bg-rose-50 text-rose-600'
                      }`}>
                        AI 置信度：{parseConfidence === 'high' ? '高' : parseConfidence === 'medium' ? '中' : '低'}
                      </span>
                      {parseSummary && (
                        <span className="text-gray-500 truncate max-w-[300px]" title={parseSummary}>{parseSummary}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* 计划项列表（可编辑） */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[12px] font-bold text-gray-700">计划项（{draftItems.length}）</span>
                  <button
                    type="button"
                    onClick={() => setDraftItems((prev) => [...prev, newDraftItem()])}
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-[#5B7BFE] hover:underline"
                  >
                    <Plus size={12} /> 新增
                  </button>
                </div>
                <div className="space-y-2 max-h-[280px] overflow-y-auto">
                  {draftItems.length === 0 ? (
                    <p className="text-[11px] text-gray-400 px-3 py-3 text-center rounded-xl border border-dashed border-gray-200">
                      还没有计划项，可在上方粘贴文本解析，或点 "+ 新增"
                    </p>
                  ) : (
                    draftItems.map((item, index) => (
                      <div key={item.id} className="rounded-xl border border-gray-100 bg-white p-3 space-y-2">
                        <div className="flex items-start gap-2">
                          <span className="text-[11px] font-bold text-gray-400 mt-2 w-6 text-center">{index + 1}</span>
                          <div className="flex-1 space-y-2">
                            <input
                              type="text"
                              value={item.title}
                              onChange={(e) => setDraftItems((prev) => prev.map((it) => it.id === item.id ? { ...it, title: e.target.value } : it))}
                              placeholder="计划项标题"
                              className="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[13px] font-medium outline-none"
                            />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                              <textarea
                                value={item.statement}
                                onChange={(e) => setDraftItems((prev) => prev.map((it) => it.id === item.id ? { ...it, statement: e.target.value } : it))}
                                placeholder="说明（可选）"
                                rows={2}
                                className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] outline-none resize-none focus:border-[#5B7BFE]"
                              />
                              <textarea
                                value={item.expectedOutput}
                                onChange={(e) => setDraftItems((prev) => prev.map((it) => it.id === item.id ? { ...it, expectedOutput: e.target.value } : it))}
                                placeholder="期望产出（可选，如：20 页方案 + 3 个 case）"
                                rows={2}
                                className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] outline-none resize-none focus:border-[#5B7BFE]"
                              />
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => setDraftItems((prev) => prev.filter((it) => it.id !== item.id))}
                            className="text-gray-300 hover:text-rose-500 mt-2"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {createError && (
                <div className="rounded-xl bg-rose-50 border border-rose-200 px-3 py-2 text-[12px] text-rose-600">
                  {createError}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-2 shrink-0">
              <button
                type="button"
                onClick={closeCreateModal}
                disabled={isSaving}
                className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSubmitCreate}
                disabled={isSaving}
                className="rounded-xl bg-[#5B7BFE] text-white px-4 py-2 text-[13px] font-bold hover:bg-[#4a6ae8] disabled:opacity-60"
              >
                {isSaving ? '保存中…' : '保存计划'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DepartmentRowBlock({
  row,
  expanded,
  onToggle,
  selectedItemId,
  onSelectItem,
}: {
  row: DepartmentRow;
  expanded: boolean;
  onToggle: () => void;
  selectedItemId: string | null;
  onSelectItem: (id: string) => void;
}) {
  const isOrg = row.scopeKind === 'org';
  return (
    <div className={`border-b last:border-b-0 ${isOrg ? 'border-[#5B7BFE]/20 bg-[#5B7BFE]/5' : 'border-gray-100'}`}>
      <button
        type="button"
        onClick={onToggle}
        className={`w-full px-5 py-3 flex items-center gap-3 text-left transition ${isOrg ? 'hover:bg-[#5B7BFE]/10' : 'hover:bg-gray-50'}`}
      >
        {expanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`font-bold text-[14px] truncate ${isOrg ? 'text-[#5B7BFE]' : 'text-gray-800'}`}>{row.scopeName}</p>
            {isOrg && (
              <span className="rounded-full bg-[#5B7BFE] text-white px-2 py-0.5 text-[9px] font-bold tracking-wider">组织</span>
            )}
          </div>
          <p className="text-[10px] text-gray-400 mt-0.5 truncate">
            {row.leaderName}
            {row.allPlansCount > 0 ? ` · 共 ${row.allPlansCount} 份计划` : ' · 尚未制定'}
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-3 text-[11px]">
          {row.latestPlan ? (
            <>
              <span className="text-gray-500">{row.latestPlan.weekLabel?.trim() || '未填周次'}</span>
              <CompletenessBar pct={row.completeness} />
            </>
          ) : (
            <span className="rounded-full bg-rose-50 px-2 py-0.5 font-bold text-rose-600">未制定</span>
          )}
        </div>
      </button>
      {expanded && row.latestPlan && (
        <div className="px-5 pb-3 pt-1 bg-gray-50/40">
          {(row.latestPlan.items || []).length === 0 ? (
            <p className="text-[11px] text-gray-400 px-2 py-2">本周计划尚未填写计划项</p>
          ) : (
            <div className="space-y-1">
              {(row.latestPlan.items || []).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectItem(item.id)}
                  className={`w-full rounded-lg px-3 py-2 text-left transition ${
                    selectedItemId === item.id
                      ? 'bg-[#5B7BFE]/10 border border-[#5B7BFE]/30'
                      : 'bg-white border border-transparent hover:border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className={`text-[13px] font-medium truncate ${selectedItemId === item.id ? 'text-[#5B7BFE]' : 'text-gray-800'}`}>
                        {item.title || '未命名计划项'}
                      </p>
                      {item.statement && (
                        <p className="mt-0.5 text-[11px] leading-5 text-gray-500 line-clamp-2">{item.statement}</p>
                      )}
                    </div>
                    <PlanItemStatusBadge status={item.status} compact />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PlanItemTaskCard({ task }: { task: Task }) {
  const statusMap: Record<string, { label: string; cls: string }> = {
    doing: { label: '进行中', cls: 'bg-blue-50 text-blue-700' },
    done: { label: '已完成', cls: 'bg-emerald-50 text-emerald-700' },
    paused: { label: '暂停', cls: 'bg-gray-100 text-gray-500' },
    cancelled: { label: '已取消', cls: 'bg-gray-100 text-gray-400' },
  };
  const status = statusMap[task.status] || { label: task.status, cls: 'bg-gray-100 text-gray-500' };

  return (
    <div className="rounded-xl border border-gray-100 bg-white px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold text-gray-800 truncate">{task.title}</p>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-500">
            <span className={`rounded-full px-1.5 py-0.5 font-bold ${status.cls}`}>{status.label}</span>
            {task.ownerName && <span>👤 {task.ownerName}</span>}
            {task.dueDate && <span>📅 {task.dueDate.slice(0, 10)}</span>}
          </div>
        </div>
        <ExternalLink size={12} className="text-gray-300 mt-1 shrink-0" />
      </div>
    </div>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      className={`rounded-2xl border px-4 py-3 shadow-sm ${
        highlight ? 'border-rose-200 bg-rose-50/40' : 'border-gray-100 bg-white'
      }`}
    >
      <p className="text-[11px] text-gray-500">{label}</p>
      <p className={`text-[22px] font-bold mt-1 tracking-tight ${highlight ? 'text-rose-600' : 'text-gray-900'}`}>
        {value}
      </p>
    </div>
  );
}

function PlanItemStatusBadge({ status, compact = false }: { status: string; compact?: boolean }) {
  const colorMap: Record<string, string> = {
    active: 'bg-emerald-50 text-emerald-700',
    paused: 'bg-gray-100 text-gray-500',
    done: 'bg-blue-50 text-blue-700',
    dropped: 'bg-rose-50 text-rose-500',
  };
  const labelMap: Record<string, string> = {
    active: '进行中',
    paused: '暂停',
    done: '已完成',
    dropped: '已废弃',
  };
  return (
    <span className={`inline-block rounded-full font-bold ${colorMap[status] || colorMap.active} ${compact ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-[10px]'}`}>
      {labelMap[status] || status}
    </span>
  );
}

function CompletenessBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      <div className="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full ${pct >= 80 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-gray-300'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-bold text-gray-700 w-9 text-right">{pct}%</span>
    </div>
  );
}
