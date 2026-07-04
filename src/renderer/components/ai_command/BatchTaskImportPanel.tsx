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

import { useState } from 'react';
import { X, ArrowLeft, Loader2, CheckCircle2, Trash2, AlertCircle, ListPlus } from 'lucide-react';

import { parseBatchTasks, type ParsedBatchTask } from '../../../shared/batchTaskParse';
import { createTask, getClients, getEventLines, getMentionCandidates, createEventLine } from '../../lib/api';
import type { Task } from '../../../shared/types';
import { buildTaskScheduleFromStartEnd } from '../../lib/taskTimeline';
import {
  resolveBatchTask,
  appendUnmatchedToDesc,
  type BatchDirectories,
  type ResolvedBatchTask,
} from '../../lib/batchTaskResolve';

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

  const listId = defaultListId || taskLists[0]?.id || 'list-0';

  const validRows = rows.filter((r) => r.include && r.title.trim() && r.startDate);

  // 每行按当前名册解析成 id(纯函数, 名册变了自动重算)。
  const resolvedByLocalId = new Map<string, ResolvedBatchTask>(
    rows.map((r) => [r.localId, resolveBatchTask(r, dirs)]),
  );

  const handleParse = async () => {
    setRows(parseBatchTasks(raw));
    setStage('preview');
    // 加载本地名册用于自动关联(失败也不阻塞, 未命中一律落背景)。
    try {
      const [clients, eventLines, members] = await Promise.all([
        getClients().catch(() => []),
        getEventLines().catch(() => []),
        getMentionCandidates('').catch(() => []),
      ]);
      setDirs({
        clients: clients.map((c) => ({ id: c.id, name: c.name })),
        eventLines: eventLines.map((e) => ({ id: e.id, name: e.name })),
        members: members.map((m) => ({ id: m.id, fullName: m.fullName })),
      });
    } catch {
      /* 名册加载失败 → dirs 保持空 → 全部落背景, 不影响建任务 */
    }
  };

  const updateRow = (localId: string, patch: Partial<ParsedBatchTask>) =>
    setRows((prev) => prev.map((r) => (r.localId === localId ? { ...r, ...patch } : r)));

  const removeRow = (localId: string) =>
    setRows((prev) => prev.filter((r) => r.localId !== localId));

  const handleConfirm = async () => {
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
        // 事件线: 命中已有用其 id; 有名字没命中 → 新建(只传 name), 缓存复用。
        let eventLineId = resolved?.eventLineId ?? null;
        const createName = resolved?.eventLineCreateName;
        if (!eventLineId && createName) {
          eventLineId = eventLineCache.get(createName) ?? null;
          if (!eventLineId) {
            const el = await createEventLine({ name: createName });
            eventLineId = el.id;
            eventLineCache.set(createName, el.id);
          }
        }
        // 负责人: 命中→其 id; 没命中→默认当前用户。协作者含 owner(编辑器语义: collaborators[0]=负责人)。
        const ownerId = resolved?.ownerId || currentUserId;
        const collaboratorIds = Array.from(
          new Set([ownerId, ...(resolved?.collaborators.map((c) => c.id) ?? [])].filter(Boolean) as string[]),
        );
        // 匹配不到的人名并进背景(graceful)。
        const desc = appendUnmatchedToDesc(r.desc.trim(), resolved?.unmatchedPeople ?? []);
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
                                  if (rv?.eventLineId) chips.push({ t: `事件线 ${r.eventLineName}✓`, c: 'bg-blue-50 text-blue-600' });
                                  else if (r.eventLineName) chips.push({ t: `事件线 ${r.eventLineName}(新建)`, c: 'bg-blue-50 text-blue-500' });
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
                      onClick={() => setStage('input')}
                      className="text-[12px] text-gray-500 hover:text-gray-700"
                    >
                      ← 改文本重解析
                    </button>
                    <button
                      type="button"
                      onClick={handleConfirm}
                      disabled={validRows.length === 0}
                      className="rounded-lg bg-[#5B7BFE] px-4 py-2 text-[13px] font-medium text-white transition hover:bg-[#4A6AF0] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      创建 {validRows.length} 条任务
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
                    setRaw('');
                    setRows([]);
                    setOutcome(null);
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
