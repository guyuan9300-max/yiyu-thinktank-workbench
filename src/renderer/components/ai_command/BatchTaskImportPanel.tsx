// ============================================================
// BatchTaskImportPanel · 批量建任务面板
//
// 入口: AICommandModal 的"批量导入"。设计origin: execute+1 收敛路径。
//   粘贴清单 → 确定性解析(parseBatchTasks, 零AI) → 可编辑预览表 → 串行节流落库。
//
// 关键取舍(均来自 排查+1 证伪结论):
//   · 确定性解析为主 → 组织AI 502 也能跑; AI 增强留 P1。
//   · 串行落库(非30路并发) → 避开 database is locked + 建任务副作用尖峰。
//   · 自带弹窗外壳 → AICommandModal 单条 quick_task 路径零改动(§M1)。
// ============================================================

import { useRef, useState } from 'react';
import { X, ArrowLeft, Loader2, CheckCircle2, Trash2, AlertCircle, ListPlus } from 'lucide-react';

import { parseBatchTasks, type ParsedBatchTask } from '../../../shared/batchTaskParse';
import { createTask, getClients, getEventLines, getMentionCandidates, createEventLine } from '../../lib/api';
import type { Task } from '../../../shared/types';
import { buildTaskScheduleFromStartEnd } from '../../lib/taskTimeline';
import {
  resolveBatchTask,
  appendUnmatchedToDesc,
  isBatchReusableEventLineStatus,
  type BatchDirectories,
  type ResolvedBatchTask,
} from '../../lib/batchTaskResolve';
import {
  appendUnmatchedEventLineToDesc,
  buildBatchEventLineIdempotencyKey,
  buildBatchEventLinePlan,
  canSubmitBatchImport,
  normalizeBatchEventLineName,
  resolveEventLineIdForSave,
  type EventLineDirectoryState,
} from '../../lib/batchEventLinePlan';

interface BatchTaskImportPanelProps {
  taskLists: Array<{ id: string; name: string }>;
  defaultListId: string | null;
  currentUserId: string | null;
  currentOwnerName: string;
  /** 落库成功后把新任务抬回 App 列表(一次性, 避免 N 次重渲染)。 */
  onCreated: (created: Task[]) => void;
  /** 返回普通 AI 指令视图。 */
  onBack: () => void;
  /** 关闭整个弹窗。 */
  onClose: () => void;
}

type PanelStage = 'input' | 'preview' | 'saving' | 'done';

interface SaveOutcome {
  total: number;
  created: number;
  failed: Array<{ title: string; error: string }>;
}

const SAMPLE = `标题：赛夫提交第一轮选品建议
日期：7/2—7/3
负责人：顾源源
事件线：715上线
客户：汇丰
优先级：高
背景：让赛夫基于现有SKU筛选香港市场爆品、钩子品、常规品，补充清单外必须要有的品类。

标题：现金补充支付方案进入P0
日期：7/6 周一前
优先级：高
背景：把"积分不够可用现金补充/现金换积分"的技术开发优先级提到P0，直接影响转化。`;

function newBatchImportSessionId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function BatchTaskImportPanel({
  taskLists,
  defaultListId,
  currentUserId,
  currentOwnerName,
  onCreated,
  onBack,
  onClose,
}: BatchTaskImportPanelProps) {
  const [raw, setRaw] = useState('');
  const [rows, setRows] = useState<ParsedBatchTask[]>([]);
  const [stage, setStage] = useState<PanelStage>('input');
  const [progress, setProgress] = useState<{ done: number; total: number }>({ done: 0, total: 0 });
  const [outcome, setOutcome] = useState<SaveOutcome | null>(null);
  // 本地名册(客户/事件线/成员), 解析预览时加载一次。全部读本地表, 离线可用。
  const [dirs, setDirs] = useState<BatchDirectories>({ clients: [], eventLines: [], members: [] });
  const [eventLineDirectoryState, setEventLineDirectoryState] = useState<EventLineDirectoryState>('loading');
  const [eventLineDirectoryError, setEventLineDirectoryError] = useState<string | null>(null);
  const [approvedEventLineNames, setApprovedEventLineNames] = useState<Set<string>>(new Set());
  const [eventLineCreationConfirmed, setEventLineCreationConfirmed] = useState(false);
  const directoryRequestEpochRef = useRef(0);
  const importSessionIdRef = useRef('');

  const listId = defaultListId || taskLists[0]?.id || 'list-0';

  const validRows = rows.filter((r) => r.include && r.title.trim() && r.startDate);

  // 每行按当前名册解析成 id(纯函数, 名册变了自动重算)。
  const resolvedByLocalId = new Map<string, ResolvedBatchTask>(
    rows.map((r) => [r.localId, resolveBatchTask(r, dirs)]),
  );

  const eventLinePlan = buildBatchEventLinePlan(
    validRows.map((r) => ({
      eventLineName: r.eventLineName ?? null,
      eventLineId: resolvedByLocalId.get(r.localId)?.eventLineId ?? null,
    })),
    approvedEventLineNames,
    eventLineDirectoryState,
  );
  const reuseEventLines = eventLinePlan.filter((item) => item.decision === 'reuse');
  const createEventLines = eventLinePlan.filter((item) => item.decision === 'create');
  const unmatchedEventLines = eventLinePlan.filter((item) => item.decision === 'unmatched');
  const canConfirmImport = validRows.length > 0 && canSubmitBatchImport(
    eventLineDirectoryState,
    eventLinePlan,
    eventLineCreationConfirmed,
  );

  const loadDirectories = async () => {
    const requestEpoch = directoryRequestEpochRef.current + 1;
    directoryRequestEpochRef.current = requestEpoch;
    setEventLineDirectoryState('loading');
    setEventLineDirectoryError(null);
    const [clientsResult, eventLinesResult, membersResult] = await Promise.allSettled([
      getClients(),
      getEventLines(),
      getMentionCandidates(''),
    ]);
    if (requestEpoch !== directoryRequestEpochRef.current) return;

    const clients = clientsResult.status === 'fulfilled' ? clientsResult.value : [];
    const members = membersResult.status === 'fulfilled' ? membersResult.value : [];
    if (eventLinesResult.status === 'rejected') {
      setDirs({
        clients: clients.map((c) => ({ id: c.id, name: c.name })),
        eventLines: [],
        members: members.map((m) => ({ id: m.id, fullName: m.fullName })),
      });
      setEventLineDirectoryState('error');
      setEventLineDirectoryError(
        eventLinesResult.reason instanceof Error ? eventLinesResult.reason.message : '事件线名册读取失败',
      );
      return;
    }

    setDirs({
      clients: clients.map((c) => ({ id: c.id, name: c.name })),
      eventLines: eventLinesResult.value
        .filter((e) => isBatchReusableEventLineStatus(e.status))
        .map((e) => ({ id: e.id, name: e.name, status: e.status })),
      members: members.map((m) => ({ id: m.id, fullName: m.fullName })),
    });
    setEventLineDirectoryState('ready');
  };

  const handleParse = async () => {
    importSessionIdRef.current = newBatchImportSessionId();
    setDirs({ clients: [], eventLines: [], members: [] });
    setApprovedEventLineNames(new Set());
    setEventLineCreationConfirmed(false);
    setEventLineDirectoryState('loading');
    setEventLineDirectoryError(null);
    setRows(parseBatchTasks(raw));
    setStage('preview');
    await loadDirectories();
  };

  const updateRow = (localId: string, patch: Partial<ParsedBatchTask>) => {
    setEventLineCreationConfirmed(false);
    setRows((prev) => prev.map((r) => (r.localId === localId ? { ...r, ...patch } : r)));
  };

  const removeRow = (localId: string) => {
    setEventLineCreationConfirmed(false);
    setRows((prev) => prev.filter((r) => r.localId !== localId));
  };

  const toggleApprovedEventLine = (name: string) => {
    const target = normalizeBatchEventLineName(name);
    setApprovedEventLineNames((previous) => {
      const next = new Set(
        Array.from(previous).filter((item) => normalizeBatchEventLineName(item) !== target),
      );
      if (next.size === previous.size) next.add(name);
      return next;
    });
    setEventLineCreationConfirmed(false);
  };

  const handleConfirm = async () => {
    if (!canConfirmImport) return;
    const toCreate = validRows;
    setStage('saving');
    setProgress({ done: 0, total: toCreate.length });
    const created: Task[] = [];
    const failed: Array<{ title: string; error: string }> = [];
    // 同名事件线只新建一次(name → 新建后的 id)。
    const eventLineCache = new Map<string, string>();

    // 串行节流: 一条建完再建下一条 —— 避开 30 路并发的 DB 锁 + 后台线程尖峰。
    for (let i = 0; i < toCreate.length; i += 1) {
      const r = toCreate[i];
      const resolved = resolvedByLocalId.get(r.localId);
      try {
        // 事件线: 已有的直接复用；未匹配的只有在逐项勾选并二次确认后才允许新建。
        const eventLineId = await resolveEventLineIdForSave({
          candidate: {
            eventLineName: r.eventLineName ?? null,
            eventLineId: resolved?.eventLineId ?? null,
          },
          directoryState: eventLineDirectoryState,
          approvedCreateNames: approvedEventLineNames,
          creationConfirmed: eventLineCreationConfirmed,
          cache: eventLineCache,
          createEventLine: (payload) => createEventLine(payload, {
            idempotencyKey: buildBatchEventLineIdempotencyKey(importSessionIdRef.current, payload.name),
          }),
        });
        // 负责人: 命中→其 id; 没命中→默认当前用户。协作者含 owner(编辑器语义: collaborators[0]=负责人)。
        const ownerId = resolved?.ownerId || currentUserId;
        const collaboratorIds = Array.from(
          new Set([ownerId, ...(resolved?.collaborators.map((c) => c.id) ?? [])].filter(Boolean) as string[]),
        );
        // 匹配不到的人名并进背景(graceful)。
        const descWithPeople = appendUnmatchedToDesc(r.desc.trim(), resolved?.unmatchedPeople ?? []);
        const desc = eventLineId
          ? descWithPeople
          : appendUnmatchedEventLineToDesc(descWithPeople, r.eventLineName ?? null);
        // 全天区间任务(如 7/2—7/3)补默认工作时段 09:00–18:00, 让日历画成跨天条。
        // 软件不支持"多天全天任务", 跨天必须带时间(见 buildTaskScheduleFromStartEnd v1)。
        // 预览表已显示起止日期, 结果跨天与之一致; 时间可在预览表微调。
        const isRange = Boolean(r.endDate && r.endDate !== r.startDate);
        const startTime = r.dueTime || (isRange ? '09:00' : '');
        const endTime = isRange ? '18:00' : '';
        const sched = buildTaskScheduleFromStartEnd({
          startDate: r.startDate || '',
          startTime,
          endDate: r.endDate || '',
          endTime,
        });
        const task = await createTask({
          title: r.title.trim(),
          desc,
          priority: r.priority || 'normal',
          listId,
          scopeMode: 'COLLAB_SHARED',
          deadlineAt: sched.deadlineAt,
          scheduledStartAt: sched.scheduledStartAt,
          scheduledEndAt: sched.scheduledEndAt,
          dueDate: sched.dueDate,
          startDate: sched.scheduledStartAt,
          durationMinutes: sched.durationMinutes ?? 60,
          ddl: r.startDate || '待确认',
          clientId: resolved?.clientId || null,
          eventLineId: eventLineId || null,
          ownerId,
          ownerName: resolved?.ownerMatched || currentOwnerName,
          collaboratorIds,
          tagIds: [],
          sourceType: 'batch_import',
        });
        created.push(task);
      } catch (e) {
        failed.push({ title: r.title, error: e instanceof Error ? e.message : '创建失败' });
      }
      setProgress({ done: i + 1, total: toCreate.length });
    }

    if (created.length) onCreated(created);
    setOutcome({ total: toCreate.length, created: created.length, failed });
    setStage('done');
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/15 backdrop-blur-md">
      <div className="flex max-h-[88vh] w-[min(760px,94vw)] flex-col overflow-hidden rounded-2xl bg-white shadow-[0_24px_70px_rgba(15,23,42,0.18)] ring-1 ring-inset ring-gray-100">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-6 py-4">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onBack}
              className="rounded-lg p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
              title="返回 AI 指令"
            >
              <ArrowLeft size={18} />
            </button>
            <ListPlus size={16} className="text-[#5B7BFE]" strokeWidth={2.2} />
            <div>
              <div className="text-[15px] font-medium tracking-tight text-gray-900">批量建任务</div>
              <p className="text-[11px] text-gray-500">粘贴清单, 每条以日期开头(如 7/2 或 7/2—7/3), 自动拆成任务</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {stage === 'input' && (
            <div className="space-y-3">
              <textarea
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                placeholder={`每条以日期开头, 例如:\n\n${SAMPLE}`}
                className="h-64 w-full resize-none rounded-xl border border-gray-200 px-4 py-3 text-[13px] leading-6 text-gray-800 outline-none focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15"
              />
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setRaw(SAMPLE)}
                  className="text-[11.5px] text-gray-400 underline-offset-2 hover:text-gray-600 hover:underline"
                >
                  填入示例
                </button>
                <button
                  type="button"
                  onClick={handleParse}
                  disabled={!raw.trim()}
                  className="rounded-lg bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white transition hover:bg-[#4A6AF0] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  解析清单
                </button>
              </div>
            </div>
          )}

          {stage === 'preview' && (
            <div className="space-y-3">
              {rows.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <AlertCircle size={24} className="text-amber-500" />
                  <p className="text-[13px] text-gray-600">没识别到任务。请确认每条都以日期开头(如 7/2 / 7/2—7/3)。</p>
                </div>
              ) : (
                <>
                  <div className="text-[12px] text-gray-500">
                    识别到 <span className="font-semibold text-gray-800">{rows.length}</span> 条,
                    将创建 <span className="font-semibold text-[#5B7BFE]">{validRows.length}</span> 条
                    (缺日期或标题的行标红, 不会创建)。可逐行修改。
                  </div>
                  {eventLineDirectoryState === 'loading' && (
                    <div className="flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50/60 px-3 py-2.5 text-[12px] text-blue-700">
                      <Loader2 size={14} className="animate-spin" />
                      正在核对现有事件线。核对完成前不会创建任务或事件线。
                    </div>
                  )}
                  {eventLineDirectoryState === 'error' && (
                    <div className="flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5">
                      <div>
                        <div className="text-[12px] font-medium text-rose-700">无法核对事件线，已停止创建</div>
                        <div className="mt-0.5 text-[11px] text-rose-600">
                          {eventLineDirectoryError || '事件线名册读取失败'}。系统不会把读取失败误当成“需要新建”。
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => void loadDirectories()}
                        className="shrink-0 rounded-md border border-rose-200 bg-white px-2.5 py-1 text-[11px] text-rose-700 hover:bg-rose-50"
                      >
                        重新核对
                      </button>
                    </div>
                  )}
                  {eventLineDirectoryState === 'ready' && (
                    <div className="space-y-2 rounded-xl border border-gray-200 bg-gray-50/60 p-3">
                      <div>
                        <div className="text-[12px] font-medium text-gray-800">事件线处理预览</div>
                        <div className="mt-0.5 text-[10.5px] text-gray-500">
                          默认只复用现有事件线。未匹配项不会新建；如确需新建，请逐项勾选并再次确认。
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="rounded-lg border border-emerald-100 bg-white p-2">
                          <div className="text-[11px] font-medium text-emerald-700">复用哪些 · {reuseEventLines.length}</div>
                          <div className="mt-1 space-y-1 text-[10.5px] text-gray-600">
                            {reuseEventLines.length === 0 ? <div className="text-gray-400">无</div> : reuseEventLines.map((item) => (
                              <div key={item.key} className="truncate" title={item.name}>✓ {item.name}（{item.taskCount} 条任务）</div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-blue-100 bg-white p-2">
                          <div className="text-[11px] font-medium text-blue-700">新建哪些 · {createEventLines.length}</div>
                          <div className="mt-1 space-y-1 text-[10.5px] text-gray-600">
                            {createEventLines.length === 0 ? <div className="text-gray-400">无</div> : createEventLines.map((item) => (
                              <label key={item.key} className="flex cursor-pointer items-start gap-1.5">
                                <input
                                  type="checkbox"
                                  checked
                                  onChange={() => toggleApprovedEventLine(item.name)}
                                  className="mt-0.5 accent-[#5B7BFE]"
                                />
                                <span className="min-w-0 truncate" title={item.name}>{item.name}（{item.taskCount} 条）</span>
                              </label>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-amber-100 bg-white p-2">
                          <div className="text-[11px] font-medium text-amber-700">未匹配哪些 · {unmatchedEventLines.length}</div>
                          <div className="mt-1 space-y-1 text-[10.5px] text-gray-600">
                            {unmatchedEventLines.length === 0 ? <div className="text-gray-400">无</div> : unmatchedEventLines.map((item) => (
                              <label key={item.key} className="flex cursor-pointer items-start gap-1.5">
                                <input
                                  type="checkbox"
                                  checked={false}
                                  onChange={() => toggleApprovedEventLine(item.name)}
                                  className="mt-0.5 accent-[#5B7BFE]"
                                />
                                <span className="min-w-0 truncate" title={item.name}>{item.name}（{item.taskCount} 条，不新建）</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                      {unmatchedEventLines.length > 0 && (
                        <div className="text-[10.5px] text-amber-700">
                          未匹配且未勾选的任务将不关联事件线，原名称会保留在任务背景中。
                        </div>
                      )}
                      {createEventLines.length > 0 && (
                        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-2 text-[11px] text-blue-800">
                          <input
                            type="checkbox"
                            checked={eventLineCreationConfirmed}
                            onChange={(event) => setEventLineCreationConfirmed(event.target.checked)}
                            className="mt-0.5 accent-[#5B7BFE]"
                          />
                          <span>
                            我确认本次新建 {createEventLines.length} 条事件线，影响 {createEventLines.reduce((sum, item) => sum + item.taskCount, 0)} 条任务。
                          </span>
                        </label>
                      )}
                    </div>
                  )}
                  <div className="overflow-hidden rounded-xl border border-gray-150 ring-1 ring-gray-100">
                    <table className="w-full border-collapse text-[12px]">
                      <thead>
                        <tr className="bg-gray-50 text-left text-[11px] text-gray-500">
                          <th className="w-8 px-2 py-2" />
                          <th className="px-2 py-2 font-medium">标题</th>
                          <th className="w-32 px-2 py-2 font-medium">开始</th>
                          <th className="w-32 px-2 py-2 font-medium">结束</th>
                          <th className="w-24 px-2 py-2 font-medium">时间</th>
                          <th className="w-8 px-2 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r) => {
                          const invalid = !r.title.trim() || !r.startDate;
                          return (
                            <tr
                              key={r.localId}
                              className={`border-t border-gray-100 ${!r.include ? 'opacity-40' : ''} ${invalid && r.include ? 'bg-rose-50/60' : ''}`}
                            >
                              <td className="px-2 py-1.5 align-top">
                                <input
                                  type="checkbox"
                                  checked={r.include}
                                  onChange={(e) => updateRow(r.localId, { include: e.target.checked })}
                                  className="mt-1 accent-[#5B7BFE]"
                                />
                              </td>
                              <td className="px-2 py-1.5">
                                <input
                                  value={r.title}
                                  onChange={(e) => updateRow(r.localId, { title: e.target.value })}
                                  placeholder="(标题必填)"
                                  className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-[12px] text-gray-800 outline-none hover:border-gray-200 focus:border-[#5B7BFE] focus:bg-white"
                                />
                                {r.desc && (
                                  <div className="truncate px-1.5 text-[10.5px] text-gray-400" title={r.desc}>
                                    {r.desc}
                                  </div>
                                )}
                                {(() => {
                                  const rv = resolvedByLocalId.get(r.localId);
                                  const chips: Array<{ t: string; c: string }> = [];
                                  // 负责人
                                  if (rv?.ownerMatched) chips.push({ t: `负责人 ${rv.ownerMatched}✓`, c: 'bg-emerald-50 text-emerald-600' });
                                  else if (r.ownerName) chips.push({ t: `负责人 ${r.ownerName}→背景`, c: 'bg-amber-50 text-amber-600' });
                                  else chips.push({ t: `负责人 ${currentOwnerName || '我'}`, c: 'bg-gray-100 text-gray-500' });
                                  // 协作者
                                  rv?.collaborators.forEach((c) => chips.push({ t: `协作 ${c.name}✓`, c: 'bg-emerald-50 text-emerald-600' }));
                                  // 事件线
                                  const eventLineDecision = eventLinePlan.find((item) => (
                                    rv?.eventLineId
                                      ? item.eventLineId === rv.eventLineId
                                      : normalizeBatchEventLineName(item.name) === normalizeBatchEventLineName(r.eventLineName || '')
                                  ))?.decision;
                                  if (rv?.eventLineId) chips.push({ t: `复用事件线 ${r.eventLineName}`, c: 'bg-emerald-50 text-emerald-600' });
                                  else if (r.eventLineName && eventLineDecision === 'create') chips.push({ t: `将新建事件线 ${r.eventLineName}`, c: 'bg-blue-50 text-blue-600' });
                                  else if (r.eventLineName && eventLineDecision === 'unmatched') chips.push({ t: `事件线 ${r.eventLineName} 不新建→背景`, c: 'bg-amber-50 text-amber-700' });
                                  else if (r.eventLineName) chips.push({ t: `事件线 ${r.eventLineName} 待核对`, c: 'bg-gray-100 text-gray-500' });
                                  // 客户
                                  if (rv?.clientMatched) chips.push({ t: `客户 ${rv.clientMatched}✓`, c: 'bg-violet-50 text-violet-600' });
                                  else if (r.clientName) chips.push({ t: `客户 ${r.clientName}?`, c: 'bg-amber-50 text-amber-600' });
                                  // 优先级
                                  if (r.priority && r.priority !== 'normal') chips.push({ t: r.priority === 'high' ? '高优' : '低优', c: 'bg-rose-50 text-rose-500' });
                                  // 未关联(协作者里落背景的)
                                  const unmatchedCollab = (rv?.unmatchedPeople ?? []).filter((n) => n !== r.ownerName);
                                  if (unmatchedCollab.length) chips.push({ t: `未关联 ${unmatchedCollab.join('、')}→背景`, c: 'bg-amber-50 text-amber-600' });
                                  return (
                                    <div className="mt-1 flex flex-wrap gap-1 px-1.5">
                                      {chips.map((ch, i) => (
                                        <span key={i} className={`rounded px-1.5 py-0.5 text-[10px] ${ch.c}`}>{ch.t}</span>
                                      ))}
                                    </div>
                                  );
                                })()}
                              </td>
                              <td className="px-2 py-1.5 align-top">
                                <input
                                  type="date"
                                  value={r.startDate || ''}
                                  onChange={(e) => updateRow(r.localId, { startDate: e.target.value || null })}
                                  className="w-full rounded border border-gray-200 px-1.5 py-1 text-[11.5px] text-gray-700 outline-none focus:border-[#5B7BFE]"
                                />
                              </td>
                              <td className="px-2 py-1.5 align-top">
                                <input
                                  type="date"
                                  value={r.endDate || ''}
                                  onChange={(e) => updateRow(r.localId, { endDate: e.target.value || null })}
                                  className="w-full rounded border border-gray-200 px-1.5 py-1 text-[11.5px] text-gray-500 outline-none focus:border-[#5B7BFE]"
                                />
                              </td>
                              <td className="px-2 py-1.5 align-top">
                                <input
                                  type="time"
                                  value={r.dueTime}
                                  onChange={(e) => updateRow(r.localId, { dueTime: e.target.value })}
                                  className="w-full rounded border border-gray-200 px-1.5 py-1 text-[11.5px] text-gray-500 outline-none focus:border-[#5B7BFE]"
                                />
                              </td>
                              <td className="px-2 py-1.5 align-top">
                                <button
                                  type="button"
                                  onClick={() => removeRow(r.localId)}
                                  className="mt-0.5 rounded p-1 text-gray-300 transition hover:bg-rose-50 hover:text-rose-500"
                                  title="删除此行"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        directoryRequestEpochRef.current += 1;
                        setStage('input');
                      }}
                      className="text-[12px] text-gray-500 hover:text-gray-700"
                    >
                      ← 改文本重解析
                    </button>
                    <button
                      type="button"
                      onClick={handleConfirm}
                      disabled={!canConfirmImport}
                      className="rounded-lg bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white transition hover:bg-[#4A6AF0] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      创建 {validRows.length} 条任务
                      {createEventLines.length > 0 && `，并新建 ${createEventLines.length} 条事件线`}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {stage === 'saving' && (
            <div className="flex flex-col items-center gap-4 py-16">
              <Loader2 size={28} className="animate-spin text-[#5B7BFE]" />
              <div className="text-[13px] text-gray-600">
                正在创建 {progress.done} / {progress.total} …
              </div>
              <div className="h-1.5 w-64 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-[#5B7BFE] transition-all"
                  style={{ width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}

          {stage === 'done' && outcome && (
            <div className="space-y-4 py-6">
              <div className="flex flex-col items-center gap-2">
                <CheckCircle2 size={30} className="text-emerald-500" />
                <div className="text-[15px] font-medium text-gray-800">
                  成功创建 {outcome.created} 条
                  {outcome.failed.length > 0 && (
                    <span className="text-rose-500"> · 失败 {outcome.failed.length} 条</span>
                  )}
                </div>
              </div>
              {outcome.failed.length > 0 && (
                <div className="rounded-lg border border-rose-100 bg-rose-50/50 p-3">
                  <div className="mb-1 text-[11.5px] font-medium text-rose-600">失败明细:</div>
                  <ul className="space-y-0.5 text-[11px] text-rose-500">
                    {outcome.failed.map((f, i) => (
                      <li key={i} className="truncate">· {f.title || '(无标题)'} — {f.error}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex justify-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    directoryRequestEpochRef.current += 1;
                    importSessionIdRef.current = '';
                    setRaw('');
                    setRows([]);
                    setOutcome(null);
                    setDirs({ clients: [], eventLines: [], members: [] });
                    setApprovedEventLineNames(new Set());
                    setEventLineCreationConfirmed(false);
                    setEventLineDirectoryState('loading');
                    setEventLineDirectoryError(null);
                    setStage('input');
                  }}
                  className="rounded-lg border border-gray-200 px-4 py-2 text-[13px] text-gray-600 transition hover:bg-gray-50"
                >
                  再导入一批
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white transition hover:bg-[#4A6AF0]"
                >
                  完成
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
