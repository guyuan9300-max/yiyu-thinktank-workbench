# 益语软件平台源码导出（第012卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `src/renderer/components/tasks/TaskTemplateEditorModal.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useState, useRef } from 'react';
import { X, GripVertical, Plus, Trash2, ChevronDown, ArrowUp, ArrowDown, ClipboardPaste, User, UploadCloud, Paperclip } from 'lucide-react';

export interface TemplateTask {
  id: string;
  title: string;
  description: string;
  /** Days after previous step completes (step 1 defaults to 0) */
  daysAfterPrevious: number;
  /** Duration in days (0.5 step: 0.5, 1, 1.5, 2...) */
  durationDays: number;
  priority: 'normal' | 'high';
  ownerName?: string;
  attachments?: { name: string; size?: number }[];
  // Legacy compat
  relativeDays?: number;
  durationMinutes?: number;
}

export interface TemplateData {
  name: string;
  scenarioDesc: string;
  tasks: TemplateTask[];
  options: {
    autoCreateEventLine: boolean;
    aiFillEmpty: boolean;
  };
}

interface Props {
  mode: 'create' | 'edit';
  initialData: TemplateData | null;
  memberNames?: string[];
  onClose: () => void;
  onSave: (data: TemplateData) => void;
}

/* ── Parse pasted text into tasks ── */
function parseBulkText(raw: string): TemplateTask[] {
  const tasks: TemplateTask[] = [];
  // Split by ・第X步： or 第X步： or ・ followed by content
  const sections = raw.split(/(?=・第[一二三四五六七八九十\d]+步[:：]|(?:^|\n)第[一二三四五六七八九十\d]+步[:：])/);
  for (const section of sections) {
    const trimmed = section.trim();
    if (!trimmed) continue;
    // Extract title from first line
    const firstLineMatch = trimmed.match(/^[・]?第[一二三四五六七八九十\d]+步[:：]\s*(.+)/);
    if (firstLineMatch) {
      const title = firstLineMatch[1].trim();
      // Rest is description
      const descLines = trimmed.split('\n').slice(1).map((l) => l.trim()).filter(Boolean);
      tasks.push({
        id: Date.now().toString() + Math.random().toString(36).slice(2, 6),
        title,
        description: descLines.join('\n'),
        daysAfterPrevious: 0,
        durationDays: 1,
        priority: 'normal',
      });
    }
  }
  return tasks;
}

export function TaskTemplateEditorModal({ mode, initialData, memberNames = [], onClose, onSave }: Props) {
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  const [templateName, setTemplateName] = useState(initialData?.name || '');
  const [scenarioDesc, setScenarioDesc] = useState(initialData?.scenarioDesc || '');
  const [tasks, setTasks] = useState<TemplateTask[]>(() => {
    // Migrate legacy data
    return (initialData?.tasks || []).map((t) => ({
      ...t,
      daysAfterPrevious: t.daysAfterPrevious ?? t.relativeDays ?? 0,
      durationDays: t.durationDays ?? (t.durationMinutes ? t.durationMinutes / 480 : 1),
    }));
  });
  const [autoCreateEventLine, setAutoCreateEventLine] = useState(initialData?.options?.autoCreateEventLine ?? true);
  const [aiFillEmpty, setAiFillEmpty] = useState(initialData?.options?.aiFillEmpty ?? false);
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [assigningTaskId, setAssigningTaskId] = useState<string | null>(null);

  const handleAddTask = () => {
    setTasks([...tasks, {
      id: Date.now().toString(),
      title: '',
      description: '',
      daysAfterPrevious: 0,
      durationDays: 1,
      priority: 'normal',
    }]);
  };

  const handleDeleteTask = (id: string) => {
    setTasks(tasks.filter((t) => t.id !== id));
  };

  const updateTask = (id: string, field: keyof TemplateTask, value: unknown) => {
    setTasks(tasks.map((t) => (t.id === id ? { ...t, [field]: value } : t)));
  };

  const handleParsePaste = () => {
    const parsed = parseBulkText(pasteText);
    if (parsed.length > 0) {
      setTasks([...tasks, ...parsed]);
      setPasteText('');
      setShowPasteModal(false);
    }
  };

  const handleFileUpload = (taskId: string, files: FileList) => {
    const newAtts = Array.from(files).map((f) => ({ name: f.name, size: f.size }));
    setTasks(tasks.map((t) => {
      if (t.id !== taskId) return t;
      return { ...t, attachments: [...(t.attachments || []), ...newAtts] };
    }));
  };

  const handleSave = () => {
    if (!templateName.trim()) return;
    onSave({
      name: templateName.trim(),
      scenarioDesc: scenarioDesc.trim(),
      tasks: tasks.filter((t) => t.title.trim()),
      options: { autoCreateEventLine, aiFillEmpty },
    });
  };

  const dragStart = (_e: React.DragEvent, position: number) => { dragItem.current = position; };
  const dragEnter = (_e: React.DragEvent, position: number) => { dragOverItem.current = position; };
  const drop = () => {
    if (dragItem.current === null || dragOverItem.current === null) return;
    const copy = [...tasks];
    const dragged = copy[dragItem.current];
    copy.splice(dragItem.current, 1);
    copy.splice(dragOverItem.current, 0, dragged);
    dragItem.current = null;
    dragOverItem.current = null;
    setTasks(copy);
  };

  const moveTask = (index: number, direction: 'up' | 'down') => {
    const next = [...tasks];
    const swap = direction === 'up' ? index - 1 : index + 1;
    if (swap < 0 || swap >= next.length) return;
    [next[index], next[swap]] = [next[swap], next[index]];
    setTasks(next);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white w-full max-w-2xl rounded-xl shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-800">
            {mode === 'edit' ? '编辑任务模板' : '新建任务模板'}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full text-gray-500 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">

          {/* Basic info */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模板名称 <span className="text-red-500">*</span></label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="例如：益语智库咨询标准流程"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">适用场景说明</label>
              <textarea
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[60px]"
                value={scenarioDesc}
                onChange={(e) => setScenarioDesc(e.target.value)}
                placeholder="描述该模板适用于何种情况..."
              />
            </div>
          </div>

          {/* Task list */}
          <div>
            <div className="flex items-center text-sm font-medium text-gray-500 mb-4">
              <div className="flex-1 border-t border-gray-200" />
              <span className="px-3">预设任务清单</span>
              <div className="flex-1 border-t border-gray-200" />
            </div>

            <div className="space-y-3">
              {tasks.map((task, index) => (
                <div
                  key={task.id}
                  draggable
                  onDragStart={(e) => dragStart(e, index)}
                  onDragEnter={(e) => dragEnter(e, index)}
                  onDragEnd={drop}
                  onDragOver={(e) => e.preventDefault()}
                  className="group relative bg-gray-50 border border-gray-200 rounded-lg p-4 transition-all hover:shadow-md hover:border-gray-300"
                >
                  <div className="flex gap-3">
                    {/* Drag handle */}
                    <div className="flex flex-col items-center pt-1 space-y-1">
                      <div className="cursor-grab text-gray-400 hover:text-gray-600 active:cursor-grabbing pb-1">
                        <GripVertical className="w-5 h-5" />
                      </div>
                      <button onClick={() => moveTask(index, 'up')} disabled={index === 0} className="p-0.5 text-gray-300 hover:text-blue-600 disabled:opacity-0"><ArrowUp className="w-3.5 h-3.5" /></button>
                      <button onClick={() => moveTask(index, 'down')} disabled={index === tasks.length - 1} className="p-0.5 text-gray-300 hover:text-blue-600 disabled:opacity-0"><ArrowDown className="w-3.5 h-3.5" /></button>
                    </div>

                    {/* Task form */}
                    <div className="flex-1 space-y-3">
                      <div className="flex gap-2 items-start">
                        <span className="text-xs font-semibold text-gray-400 mt-2.5 w-12 shrink-0">任务 {index + 1}</span>
                        <input
                          type="text"
                          value={task.title}
                          onChange={(e) => updateTask(task.id, 'title', e.target.value)}
                          placeholder="任务标题（必填）"
                          className="flex-1 px-3 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
                        />
                        {/* Person assignment */}
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setAssigningTaskId(assigningTaskId === task.id ? null : task.id)}
                            className={`flex items-center gap-1 px-2 py-1.5 rounded border text-[12px] transition ${
                              task.ownerName
                                ? 'border-blue-200 bg-blue-50 text-blue-700'
                                : 'border-gray-300 text-gray-400 hover:border-blue-400 hover:text-blue-600'
                            }`}
                            title={task.ownerName || '指派负责人'}
                          >
                            <User className="w-3.5 h-3.5" />
                            <span className="max-w-[60px] truncate">{task.ownerName || '指派'}</span>
                          </button>
                          {assigningTaskId === task.id && (
                            <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1 max-h-[200px] overflow-y-auto">
                              <button
                                type="button"
                                className="w-full text-left px-3 py-1.5 text-[12px] text-gray-400 hover:bg-gray-50"
                                onClick={() => { updateTask(task.id, 'ownerName', ''); setAssigningTaskId(null); }}
                              >
                                不指派
                              </button>
                              {(memberNames.length > 0 ? memberNames : ['顾源源', '佳乐', '乐乐', '大周', '庆华', '花花', '罗茜茜']).map((name) => (
                                <button
                                  key={name}
                                  type="button"
                                  className={`w-full text-left px-3 py-1.5 text-[12px] hover:bg-blue-50 ${task.ownerName === name ? 'text-blue-600 font-bold' : 'text-gray-700'}`}
                                  onClick={() => { updateTask(task.id, 'ownerName', name); setAssigningTaskId(null); }}
                                >
                                  {name}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex gap-2 items-start pl-[56px]">
                        <textarea
                          value={task.description}
                          onChange={(e) => updateTask(task.id, 'description', e.target.value)}
                          placeholder="任务说明（选填，支持 {{客户名}} 占位符）"
                          className="flex-1 px-3 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 text-sm min-h-[60px]"
                        />
                      </div>

                      {/* Attachments + upload */}
                      <div className="flex items-center gap-2 pl-[56px] flex-wrap">
                        {(task.attachments || []).map((att, ai) => (
                          <span key={ai} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-0.5 text-[10px] text-gray-600">
                            <Paperclip className="w-2.5 h-2.5 text-gray-400" />
                            <span className="truncate max-w-[120px]">{att.name}</span>
                          </span>
                        ))}
                        <label className="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10px] text-gray-400 cursor-pointer transition hover:text-blue-600 hover:bg-blue-50">
                          <UploadCloud className="w-3 h-3" />
                          附件
                          <input
                            type="file"
                            multiple
                            className="hidden"
                            onChange={(e) => { if (e.target.files) handleFileUpload(task.id, e.target.files); e.target.value = ''; }}
                          />
                        </label>
                      </div>

                      <div className="flex flex-wrap gap-4 items-center pl-[56px]">
                        <div className="flex items-center">
                          <label className="text-xs text-gray-500 mr-2">{index === 0 ? '开始延迟' : '上一步后'}</label>
                          <input
                            type="number"
                            value={task.daysAfterPrevious}
                            onChange={(e) => updateTask(task.id, 'daysAfterPrevious', parseInt(e.target.value) || 0)}
                            className="w-14 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                            min="0"
                          />
                          <span className="ml-1 text-xs text-gray-400">天</span>
                        </div>

                        <div className="flex items-center">
                          <label className="text-xs text-gray-500 mr-2">耗时</label>
                          <input
                            type="number"
                            value={task.durationDays}
                            onChange={(e) => updateTask(task.id, 'durationDays', parseFloat(e.target.value) || 0.5)}
                            className="w-16 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                            min="0.5"
                            step="0.5"
                          />
                          <span className="ml-1 text-xs text-gray-400">天</span>
                        </div>

                        <div className="flex items-center">
                          <label className="text-xs text-gray-500 mr-2">优先级</label>
                          <div className="relative">
                            <select
                              value={task.priority}
                              onChange={(e) => updateTask(task.id, 'priority', e.target.value)}
                              className="appearance-none bg-white border border-gray-300 text-sm rounded pl-3 pr-8 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="normal">普通</option>
                              <option value="high">高</option>
                            </select>
                            <ChevronDown className="w-3 h-3 absolute right-2 top-2 text-gray-500 pointer-events-none" />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Delete */}
                    <button
                      onClick={() => handleDeleteTask(task.id)}
                      className="text-gray-400 hover:text-red-500 p-2 h-fit rounded-md transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleAddTask}
                className="flex-1 py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm font-medium text-gray-500 hover:border-blue-500 hover:text-blue-600 transition-colors flex items-center justify-center"
              >
                <Plus className="w-4 h-4 mr-1" />
                添加一条预设任务
              </button>
              <button
                onClick={() => setShowPasteModal(true)}
                className="py-2.5 px-4 border-2 border-dashed border-gray-300 rounded-lg text-sm font-medium text-gray-500 hover:border-blue-500 hover:text-blue-600 transition-colors flex items-center justify-center"
              >
                <ClipboardPaste className="w-4 h-4 mr-1" />
                粘贴批量任务
              </button>
            </div>
          </div>

          {/* Options */}
          <div>
            <div className="flex items-center text-sm font-medium text-gray-500 mb-4 mt-6">
              <div className="flex-1 border-t border-gray-200" />
              <span className="px-3">模板选项</span>
              <div className="flex-1 border-t border-gray-200" />
            </div>

            <div className="space-y-3">
              <label className="flex items-center cursor-pointer group w-fit">
                <input
                  type="checkbox"
                  checked={autoCreateEventLine}
                  onChange={(e) => setAutoCreateEventLine(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                />
                <span className="ml-3 text-sm text-gray-700 group-hover:text-gray-900">套用时自动创建事件线（用模板名作为事件线名）</span>
              </label>

              <label className="flex items-center cursor-pointer group w-fit">
                <input
                  type="checkbox"
                  checked={aiFillEmpty}
                  onChange={(e) => setAiFillEmpty(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                />
                <span className="ml-3 text-sm text-gray-700 group-hover:text-gray-900">任务说明留空的部分由 AI 根据客户背景自动填写</span>
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center rounded-b-xl">
          <span className="text-[12px] text-gray-400">{tasks.length} 个预设任务</span>
          <div className="flex space-x-3">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={!templateName.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              保存模板
            </button>
          </div>
        </div>
      </div>

      {/* Paste modal */}
      {showPasteModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/30 p-4">
          <div className="bg-white w-full max-w-lg rounded-xl shadow-2xl p-6">
            <h3 className="text-[16px] font-bold text-gray-800 mb-3">粘贴批量任务</h3>
            <p className="text-[12px] text-gray-500 mb-3">
              粘贴包含多个步骤的文本，系统会自动按"第X步："拆分成多个任务。
            </p>
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="粘贴文本...&#10;&#10;格式示例：&#10;・第一步：需求调研&#10;1. 收集需求&#10;2. 分析痛点&#10;&#10;・第二步：方案设计&#10;1. 画原型..."
              className="w-full min-h-[200px] px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-[13px] leading-relaxed"
              autoFocus
            />
            {pasteText.trim() && (
              <p className="mt-2 text-[11px] text-blue-600">
                预览：识别到 {parseBulkText(pasteText).length} 个任务
              </p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => { setPasteText(''); setShowPasteModal(false); }}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleParsePaste}
                disabled={parseBulkText(pasteText).length === 0}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                解析并添加 {parseBulkText(pasteText).length} 个任务
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/components/tasks/UnderstandingPanel.tsx`

- 编码: `utf-8`

~~~tsx
import type { UnderstandingSnapshotV1 } from '../../../shared/types';

function confidenceBadge(confidence: number) {
  if (confidence >= 70) return { label: '高置信', className: 'bg-emerald-50 text-emerald-700' };
  if (confidence >= 40) return { label: '中置信', className: 'bg-amber-50 text-amber-700' };
  return { label: '低置信', className: 'bg-slate-100 text-slate-500' };
}

type UnderstandingPanelProps = {
  snapshot: UnderstandingSnapshotV1;
};

export function UnderstandingPanel({ snapshot }: UnderstandingPanelProps) {
  const badge = confidenceBadge(snapshot.confidence);

  return (
    <div className="space-y-3">
      {/* 状态条 */}
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${badge.className}`}>{badge.label}</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
          覆盖 {snapshot.coverage}%
        </span>
        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-[#33449a]">
          {snapshot.mode === 'enhanced' ? '增强模式' : '基础模式'}
        </span>
        {snapshot.sourceBreakdown.filter((s) => s.available).map((s) => (
          <span key={s.sourceType} className="rounded-full bg-gray-50 px-2 py-0.5 text-[9px] font-bold text-gray-400">
            {s.label}
          </span>
        ))}
      </div>

      {/* 第一层：4 个核心问题 */}
      <div className="space-y-2.5">
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">这是什么事</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.whatIsThis}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">为什么重要</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.whyItMatters}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">推进到哪</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.progressNow}</p>
        </div>
        <div className="rounded-2xl bg-amber-50/50 px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wider text-amber-500">还缺什么理解</p>
          <p className="mt-1.5 text-[13px] leading-6 text-gray-800">{snapshot.unknowns}</p>
        </div>
      </div>

      {/* 已知事实 */}
      {snapshot.knownFacts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {snapshot.knownFacts.map((fact) => (
            <span key={fact} className="rounded-full bg-gray-50 px-2.5 py-1 text-[10px] text-gray-500">{fact}</span>
          ))}
        </div>
      )}

      {/* 第二层：可选建议（只在有内容时显示） */}
      {snapshot.optionalAdvice && (
        <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 space-y-2">
          {snapshot.optionalAdvice.timeGate && (
            <p className="text-[12px] leading-5 text-red-600">
              <span className="font-bold">时间闸门：</span>{snapshot.optionalAdvice.timeGate}
            </p>
          )}
          {snapshot.optionalAdvice.realBlocker && (
            <p className="text-[12px] leading-5 text-amber-700">
              <span className="font-bold">真正阻碍：</span>{snapshot.optionalAdvice.realBlocker}
            </p>
          )}
          {snapshot.optionalAdvice.minimumAction && (
            <p className="text-[12px] leading-5 text-[#33449a]">
              <span className="font-bold">最小动作：</span>{snapshot.optionalAdvice.minimumAction}
            </p>
          )}
          {snapshot.optionalAdvice.supportAsk && (
            <p className="text-[12px] leading-5 text-gray-600">
              <span className="font-bold">需要支持：</span>{snapshot.optionalAdvice.supportAsk}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/components/tasks/WeeklyReviewSimulationPanel.tsx`

- 编码: `utf-8`

~~~tsx
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
~~~

## `src/renderer/components/tasks/WeeklyReviewStructuredFields.tsx`

- 编码: `utf-8`

~~~tsx
import { Check, Circle, X } from 'lucide-react';
import type { TaskStatus, WeeklyReviewTaskStructuredNote } from '../../../shared/types';

const LIGHTWEIGHT_TAGS = ['资料不足', '等待他人', '方向不清', '资源不够', '工作过度饱和'] as const;

const GROWTH_HINT_RULES = [
  { key: 'exec', label: '推进执行', keywords: ['推进', '闭环', '行动项', '排期', '拆解', '跟进', '完成', '延期'] },
  { key: 'collab', label: '协作沟通', keywords: ['协作', '沟通', '对齐', '会议', '负责人', '跨组', '边界', '配合'] },
  { key: 'analyze', label: '分析判断', keywords: ['分析', '判断', '原因', '本质', '结论', '规律', '为什么'] },
  { key: 'insight', label: '客户洞察', keywords: ['客户', '用户', '访谈', '需求', '顾虑', '诉求', '反馈'] },
  { key: 'risk', label: '风险识别', keywords: ['风险', '阻碍', '卡点', '依赖', '预警', '退回', '失败'] },
  { key: 'write', label: '写作表达', keywords: ['模板', '方法', '清单', '沉淀', '复用', '记录', '总结'] },
] as const;

export function createEmptyReviewStructuredNote(): WeeklyReviewTaskStructuredNote {
  return {
    reflection: '',
    lightweightTag: '',
    planCommitment: '',
    progress: '',
    completionStatus: 'in_progress',
    departmentPlanId: null,
    departmentPlanAlignment: 'unknown',
    organizationPlanId: null,
    organizationPlanAlignment: 'unknown',
    successReason: '',
    successExperience: '',
    blockerReason: '',
    failureInsight: '',
    supportNeeded: '',
    nextAction: '',
  };
}

function reviewModeFromValue(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  if (taskStatus === 'done') return 'done' as const;
  if (value.completionStatus === 'done_on_time' || value.completionStatus === 'done_late') return 'done' as const;
  return 'pending' as const;
}

function normalizeSimpleReviewText(text: string) {
  return text
    .replace(/^任务完成心得：\s*/, '')
    .replace(/^需要支持\s*\/\s*思考：\s*/, '')
    .replace(/^支持需求：\s*/, '')
    .replace(/^失败心得：\s*/, '')
    .replace(/^阻碍原因：\s*/, '')
    .replace(/^本周推进：\s*/, '')
    .trim();
}

function detectGrowthHints(text: string) {
  const normalized = normalizeSimpleReviewText(text);
  if (!normalized) return [];
  return GROWTH_HINT_RULES.filter((rule) => rule.keywords.some((keyword) => normalized.includes(keyword))).map((rule) => rule.label);
}

function detectContributionPremiumHint(text: string) {
  const normalized = normalizeSimpleReviewText(text);
  if (!normalized) return null;
  if (['模板', '复用', '流程', '规则', '机制', '统一'].some((keyword) => normalized.includes(keyword))) {
    return '这条复盘有机会拿到 30%-50% 的组织贡献溢价';
  }
  if (['协作', '会议', '负责人', '时间点', '边界', '支持', '帮助', '风险', '预警'].some((keyword) => normalized.includes(keyword))) {
    return '这条复盘有机会拿到 20%-40% 的组织贡献溢价';
  }
  return null;
}

export function getSimpleReviewText(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  if (value.reflection.trim()) {
    return normalizeSimpleReviewText(value.reflection);
  }
  const mode = reviewModeFromValue(value, taskStatus);
  const candidates = mode === 'done'
    ? [
        value.successExperience.trim(),
        value.successReason.trim(),
        value.progress.trim(),
        value.nextAction.trim(),
      ]
    : [
        value.supportNeeded.trim(),
        value.failureInsight.trim(),
        value.blockerReason.trim(),
        value.progress.trim(),
        value.nextAction.trim(),
      ];
  return normalizeSimpleReviewText(candidates.find(Boolean) || '');
}

export function applySimpleReviewText(
  value: WeeklyReviewTaskStructuredNote,
  nextText: string,
  taskStatus?: TaskStatus,
): WeeklyReviewTaskStructuredNote {
  const trimmed = nextText.trim();
  const mode = reviewModeFromValue(value, taskStatus);
  if (mode === 'done') {
    return {
      ...value,
      completionStatus: value.completionStatus === 'done_late' ? 'done_late' : 'done_on_time',
      reflection: trimmed,
    };
  }
  return {
    ...value,
    completionStatus: value.completionStatus === 'not_done' ? 'not_done' : 'in_progress',
    reflection: trimmed,
  };
}

export function hasMeaningfulReviewStructuredNote(value: WeeklyReviewTaskStructuredNote) {
  return [
    value.reflection.trim(),
    value.lightweightTag,
    value.planCommitment.trim(),
    value.progress.trim(),
    value.departmentPlanId || '',
    value.organizationPlanId || '',
    value.successReason.trim(),
    value.successExperience.trim(),
    value.blockerReason.trim(),
    value.failureInsight.trim(),
    value.supportNeeded.trim(),
    value.nextAction.trim(),
    value.completionStatus !== 'in_progress' ? value.completionStatus : '',
    value.departmentPlanAlignment !== 'unknown' ? value.departmentPlanAlignment : '',
    value.organizationPlanAlignment !== 'unknown' ? value.organizationPlanAlignment : '',
  ].some(Boolean);
}

export function composeReviewNoteFromStructuredFields(value: WeeklyReviewTaskStructuredNote, taskStatus?: TaskStatus) {
  const text = getSimpleReviewText(value, taskStatus);
  const tagSuffix = reviewModeFromValue(value, taskStatus) === 'pending' && value.lightweightTag
    ? `（当前卡点：${value.lightweightTag}）`
    : '';
  if (!text && tagSuffix) {
    return `需要支持 / 思考：${value.lightweightTag}`;
  }
  if (!text) return '';
  return reviewModeFromValue(value, taskStatus) === 'done'
    ? `任务完成心得：${text}`
    : `需要支持 / 思考：${text}${tagSuffix}`;
}

type WeeklyReviewStructuredFieldsProps = {
  scope: 'work' | 'personal';
  value: WeeklyReviewTaskStructuredNote;
  taskStatus: TaskStatus;
  onChange: (nextValue: WeeklyReviewTaskStructuredNote) => void;
  onSave?: () => void;
  isSaving?: boolean;
  saveDisabled?: boolean;
  saveSucceeded?: boolean;
  onStatusChange?: (nextStatus: 'done' | 'delayed' | 'cancelled') => void;
  isStatusChanging?: boolean;
  statusScopeLabel?: string;
};

export function WeeklyReviewStructuredFields({
  scope,
  value,
  taskStatus,
  onChange,
  onSave,
  isSaving = false,
  saveDisabled = false,
  saveSucceeded = false,
  onStatusChange,
  isStatusChanging = false,
  statusScopeLabel = '本条任务状态',
}: WeeklyReviewStructuredFieldsProps) {
  const mode = reviewModeFromValue(value, taskStatus);
  const helperLabel = mode === 'done'
    ? '已完成'
    : taskStatus === 'rejected'
      ? '已取消'
      : value.completionStatus === 'not_done'
        ? '已延迟'
        : taskStatus === 'doing'
          ? '仍在推进'
          : '未完成 / 逾期';
  const textareaLabel = mode === 'done' ? '完成心得' : '需要支持 / 这周思考';
  const placeholder = mode === 'done'
    ? '任务完成了，有什么心得？'
    : scope === 'work'
      ? '这项任务还没收口，需要什么支持，或者有什么思考？'
      : '这件事还没推进完，需要什么支持，或者有什么思考？';
  const currentValue = getSimpleReviewText(value, taskStatus);
  const growthHints = detectGrowthHints(currentValue);
  const contributionPremiumHint = detectContributionPremiumHint(currentValue);
  const saveButtonState = isSaving ? 'saving' : saveSucceeded ? 'saved' : saveDisabled ? 'disabled' : 'ready';
  const selectedStatus =
    taskStatus === 'done'
      ? 'done'
      : taskStatus === 'rejected'
        ? 'cancelled'
        : value.completionStatus === 'not_done'
          ? 'delayed'
          : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1.5 text-[11px] font-bold text-gray-500">
          <span className={`h-2 w-2 rounded-full ${mode === 'done' ? 'bg-emerald-400' : taskStatus === 'rejected' ? 'bg-rose-400' : value.completionStatus === 'not_done' ? 'bg-amber-400' : 'bg-amber-300'}`} />
          系统识别：{helperLabel}
        </div>
        {onStatusChange ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">{statusScopeLabel}</span>
            <button
              type="button"
              onClick={() => onStatusChange('done')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'done'
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-emerald-200 hover:text-emerald-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <Check size={13} />
              <span>完成</span>
            </button>
            <button
              type="button"
              onClick={() => onStatusChange('delayed')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'delayed'
                  ? 'border-amber-300 bg-amber-50 text-amber-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-amber-200 hover:text-amber-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <Circle size={13} />
              <span>延迟</span>
            </button>
            <button
              type="button"
              onClick={() => onStatusChange('cancelled')}
              disabled={isStatusChanging}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                selectedStatus === 'cancelled'
                  ? 'border-rose-300 bg-rose-50 text-rose-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:border-rose-200 hover:text-rose-700'
              } ${isStatusChanging ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <X size={13} />
              <span>取消</span>
            </button>
          </div>
        ) : null}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-[12px] font-bold text-gray-700">{textareaLabel}</p>
          {onSave ? (
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving || saveDisabled}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-bold transition ${
                saveButtonState === 'disabled'
                  ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                  : saveButtonState === 'saved'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-[#DCE7FF] bg-[#F8FAFF] text-[#335CFF] hover:border-[#BFD2FF] hover:bg-[#EEF4FF]'
              }`}
            >
              <span className="text-[13px] leading-none">{isSaving ? '…' : '✓'}</span>
              <span>{isSaving ? '保存中' : saveSucceeded ? '已保存' : '保存'}</span>
            </button>
          ) : null}
        </div>
        <textarea
          value={currentValue}
          onChange={(event) => onChange(applySimpleReviewText(value, event.target.value, taskStatus))}
          placeholder={placeholder}
          className="w-full min-h-[96px] rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-800 outline-none"
        />
      </div>

      {mode === 'pending' ? (
        <div className="space-y-2">
          <p className="text-[12px] font-bold text-gray-700">当前主要卡点（可不选）</p>
          <div className="flex flex-wrap gap-2">
            {LIGHTWEIGHT_TAGS.map((tag) => {
              const active = value.lightweightTag === tag;
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => onChange({ ...value, lightweightTag: active ? '' : tag })}
                  className={`rounded-full border px-3 py-1.5 text-[12px] font-semibold transition ${
                    active
                      ? 'border-[#5B7BFE] bg-[#EEF4FF] text-[#335CFF]'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-800'
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {growthHints.length ? (
        <div className="space-y-2">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">识别到的成长点</p>
          <div className="flex flex-wrap gap-2">
            {growthHints.map((label) => (
              <span key={label} className="rounded-full bg-[#EEF4FF] px-3 py-1 text-[11px] font-semibold text-[#335CFF]">
                {label}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {contributionPremiumHint ? (
        <div className="rounded-2xl border border-[#DCE7FF] bg-[#F8FAFF] px-4 py-3 text-[12px] font-medium leading-6 text-[#335CFF]">
          {contributionPremiumHint}
        </div>
      ) : null}
    </div>
  );
}
~~~

## `src/renderer/components/tasks/WeeklyReviewSummaryPanel.tsx`

- 编码: `utf-8`

~~~tsx
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
~~~

## `src/renderer/components/tasks/reviewDraft.ts`

- 编码: `utf-8`

~~~typescript
import type { ReviewDashboard, Task, WeeklyReviewAnalysis, WeeklyReviewTaskStructuredNote } from '../../../shared/types';

export type ReviewTaskRow = {
  task: Task;
  note: string;
  structuredNote: WeeklyReviewTaskStructuredNote;
  reviewedAt: string | null;
};

type ReviewDraftGroup = {
  id: string;
  title: string;
  eventLineId: string | null;
  rows: ReviewTaskRow[];
  sharedNote: string;
};

export function reviewStatusLabel(task: Task) {
  if (task.status === 'done') return '已完成';
  if (task.status === 'doing') return '进行中';
  if (task.status === 'rejected') return '已取消';
  if (task.status === 'inbox') return '收件箱';
  return '未完成';
}

export function reviewTaskDateLabel(task: Task) {
  return task.dueDate || task.createdAt.slice(0, 10);
}

export function reviewTaskBackground(task: Task) {
  const segments = [
    task.desc.trim() || '任务背景待补充。',
    `归属清单：${task.listName}`,
    `负责人：${task.ownerName || '未指定'}`,
  ];
  return segments.join('；');
}

function lensLabel(lens: string) {
  if (lens === 'organization') return '组织视角';
  if (lens === 'business') return '业务视角';
  if (lens === 'team') return '团队视角';
  if (lens === 'market') return '市场视角';
  if (lens === 'growth') return '成长视角';
  return '执行视角';
}

function confidenceLabel(confidence: string) {
  if (confidence === 'high') return '高';
  if (confidence === 'medium') return '中';
  return '低';
}

const SECTION_LABELS = ['一', '二', '三', '四', '五', '六', '七', '八', '九'];

function buildReviewDraftGroups(rows: ReviewTaskRow[]): ReviewDraftGroup[] {
  const groups = new Map<string, ReviewTaskRow[]>();
  rows.forEach((row) => {
    const eventLineId = row.task.eventLineId?.trim() || '';
    const key = eventLineId ? `event-line:${eventLineId}` : `task:${row.task.id}`;
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(row);
    } else {
      groups.set(key, [row]);
    }
  });

  return Array.from(groups.entries()).map(([id, groupRows]) => {
    const sharedNote = groupRows.find(({ note }) => note.trim())?.note.trim() || '';
    return {
      id,
      title: groupRows[0]?.task.eventLineName?.trim() || groupRows[0]?.task.title || '未命名事项',
      eventLineId: groupRows[0]?.task.eventLineId?.trim() || null,
      rows: [...groupRows],
      sharedNote,
    };
  });
}

export function buildWeeklyReviewDocumentDraft(
  scope: 'work' | 'personal',
  weekLabel: string,
  rows: ReviewTaskRow[],
  analysis?: WeeklyReviewAnalysis | null,
  dashboard?: Pick<ReviewDashboard, 'teamReport' | 'orgReport' | 'agentDepartmentDigests' | 'agentDepartmentPlans'> | null,
) {
  const scopeLabel = scope === 'work' ? '组织' : '成长';
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });
  const completedCount = rows.filter(({ task }) => task.status === 'done').length;
  const reviewedCount = rows.filter(({ note }) => Boolean(note.trim())).length;
  const unfinishedRows = rows.filter(({ task }) => task.status !== 'done');
  const reviewGroups = buildReviewDraftGroups(rows);
  const eventLineGroupCount = reviewGroups.filter((group) => group.eventLineId).length;
  const agentDepartmentDigests = dashboard?.agentDepartmentDigests || [];
  const agentDepartmentPlans = dashboard?.agentDepartmentPlans || [];

  const lines = [
    `${weekLabel} ${scopeLabel}复盘文档（草稿）`,
    `生成时间：${generatedAt}`,
    '',
  ];
  let sectionIndex = 0;
  const pushSection = (title: string) => {
    if (lines[lines.length - 1] !== '') {
      lines.push('');
    }
    const label = SECTION_LABELS[sectionIndex] || String(sectionIndex + 1);
    lines.push(`${label}、${title}`);
    sectionIndex += 1;
  };

  if (analysis) {
    lines.push('说明：以下内容分为“已确认事实”和“可能性分析”两层。可能性分析会明确标注权重与置信度，供人工继续判断，不应直接当成确定事实。', '');
  }

  pushSection('整体概览');
  lines.push(`本周共纳入 ${rows.length} 项${scope === 'work' ? '任务' : '成长事项'}，已完成 ${completedCount} 项，未完成 ${rows.length - completedCount} 项，已补充复盘说明 ${reviewedCount} 项。`);
  lines.push(`当前已按 ${reviewGroups.length} 个复盘模块整理，其中 ${eventLineGroupCount} 个模块来自事件线聚合。`);

  if (analysis?.headline) {
    lines.push(`整体判断：${analysis.headline}`);
  } else {
    lines.push(
      scope === 'work'
        ? `从整体执行情况看，当前周内任务推进呈现“已完成 ${completedCount} 项、仍待继续推进 ${rows.length - completedCount} 项”的节奏。以下文档会优先按事件线展开，避免把同一件事拆成多条重复记录。`
        : '从个人成长事项来看，本周已经补充的内容主要围绕状态、观察与感受展开；以下文档会优先按事件线展开，方便围绕同一件事集中复盘。',
    );
  }

  if (analysis?.metricCards?.length) {
    pushSection('核心指标');
    analysis.metricCards.forEach((metric, index) => {
      lines.push(`${index + 1}. ${metric.label}：${metric.valueText}（${metric.denominator > 0 ? `${metric.numerator}/${metric.denominator}` : '待补录'}）`);
      lines.push(metric.description);
    });
  }

  if (analysis?.confirmedFacts.length) {
    pushSection('已确认事实');
    analysis.confirmedFacts.forEach((item, index) => {
      lines.push(`${index + 1}. ${item}`);
    });
  }

  if (analysis?.evidenceWeights.length) {
    pushSection('证据权重说明');
    analysis.evidenceWeights.forEach((item) => {
      const weightLabel = item.weight === 'high' ? '高权重' : item.weight === 'medium' ? '中权重' : '低权重';
      lines.push(`- ${item.label}（${weightLabel}）：${item.rationale}`);
    });
  }

  if (analysis?.hypothesisHighlights.length) {
    pushSection('可能性分析');
    analysis.hypothesisHighlights.forEach((item, index) => {
      lines.push(`${index + 1}. ${item.title}｜${lensLabel(item.lens)}｜置信度 ${confidenceLabel(item.confidence)}`);
      lines.push(item.statement);
      lines.push(`依据：${item.reason}`);
      if (item.assumptionNote) {
        lines.push(`提示：${item.assumptionNote}`);
      }
      lines.push('');
    });
  } else {
    pushSection('可能性分析');
    lines.push(scope === 'work' ? '当前还没有足够多的过程说明，系统暂时只能给出保守判断；建议先补齐关键任务的一线说明。' : '当前成长复盘更偏事实记录，尚不足以形成更强的成长判断。');
  }

  if (scope === 'work' && dashboard?.teamReport?.summary) {
    lines.push('团队视角补充：' + dashboard.teamReport.summary, '');
  }
  if (scope === 'work' && dashboard?.orgReport?.summary) {
    lines.push('组织视角补充：' + dashboard.orgReport.summary, '');
  }
  if (scope === 'work' && agentDepartmentDigests.length > 0) {
    pushSection('部门周摘要补充');
    agentDepartmentDigests.forEach((digest, index) => {
      lines.push(`${index + 1}. ${digest.departmentName}（${digest.agentName}）`);
      lines.push(digest.summary);
      if (digest.focusItems.length > 0) {
        lines.push(`下周延续重点：${digest.focusItems.join('；')}`);
      }
      lines.push(`证据说明：本摘要基于 ${digest.evidenceCount} 条真实日志聚合，来源类型为 ${String(digest.sourcePolicy?.sourceType || 'real_log')}。`);
      lines.push('');
    });
  }
  if (scope === 'work' && agentDepartmentPlans.length > 0) {
    pushSection('部门下周计划补充');
    agentDepartmentPlans.forEach((plan, index) => {
      lines.push(`${index + 1}. ${plan.departmentName}（${plan.agentName}）`);
      lines.push(plan.summary);
      plan.planItems.forEach((item, itemIndex) => {
        lines.push(`   - 计划项 ${itemIndex + 1}：${item.title}`);
        if (item.rationale) lines.push(`   推演依据：${item.rationale}`);
        if (item.scheduleHint) lines.push(`   节奏提示：${item.scheduleHint}`);
      });
      lines.push('');
    });
  }

  pushSection('逐事件线推进情况');
  reviewGroups.forEach((group, index) => {
    lines.push(`${index + 1}. ${group.title}`);
    if (group.eventLineId) {
      lines.push(`事件线任务数：${group.rows.length}；这是本周围绕同一条事件线自动聚合出的复盘模块。`);
    } else {
      lines.push(`单项事项：当前尚未挂入事件线，仍按单条任务记录。`);
    }
    const backgroundLines = group.rows.map(({ task }) => `- ${task.title}｜${reviewStatusLabel(task)}｜${reviewTaskDateLabel(task)}｜${task.listName}`);
    lines.push('本周相关任务：');
    lines.push(...backgroundLines);
    const firstTask = group.rows[0]?.task;
    if (firstTask) {
      lines.push(`背景补充：${reviewTaskBackground(firstTask)}`);
    }
    lines.push(group.sharedNote || '尚未补充这条事件线的统一复盘说明。');
    lines.push('');
  });

  pushSection('下周关注重点');
  if (analysis?.nextWeekFocus.length) {
    analysis.nextWeekFocus.forEach((item) => {
      lines.push(`- ${item}`);
    });
  } else if (unfinishedRows.length) {
    reviewGroups
      .filter((group) => group.rows.some(({ task }) => task.status !== 'done'))
      .slice(0, 3)
      .forEach((group) => {
        lines.push(`- ${group.title}：优先继续推进；${group.sharedNote ? `可延续当前事件线判断：${group.sharedNote}` : '建议补全这一条事件线当前卡点和下一步动作。'}`);
      });
    if (reviewGroups.filter((group) => group.rows.some(({ task }) => task.status !== 'done')).length === 0) {
      unfinishedRows.slice(0, 3).forEach(({ task, note }) => {
        lines.push(`- ${task.title}：优先继续推进；${note.trim() ? `可延续当前说明中的重点：${note.trim()}` : '建议补全背景、卡点和下一步动作。'}`);
      });
    }
  } else {
    lines.push('- 当前纳入复盘的事项都已完成，可以把重点放在经验沉淀和下一轮任务准备。');
  }

  return lines.join('\n');
}
~~~

## `src/renderer/components/topics/TopicIntelChatPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useRef } from 'react';
import { MessageCircle, SendHorizontal } from 'lucide-react';

import type { TopicCandidateChatMessage } from '../../../shared/types';

type TopicIntelChatPanelProps = {
  messages: TopicCandidateChatMessage[];
  draft: string;
  loading: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

function formatChatTime(value: string) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

export function TopicIntelChatPanel({ messages, draft, loading, onDraftChange, onSend }: TopicIntelChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
  }, [loading, messages]);

  return (
    <section className="rounded-[24px] border border-gray-100 px-5 py-4">
      <div className="flex items-center gap-2">
        <MessageCircle size={16} className="text-[#5B7BFE]" />
        <p className="text-[12px] font-bold text-gray-900">围绕这篇情报继续问</p>
      </div>
      <p className="text-[12px] text-gray-500 mt-1">如果你对这篇新闻还有疑问，可以直接问大周。它会只围绕当前情报和已有解析继续回答。</p>

      <div
        ref={scrollRef}
        className="mt-3 rounded-[20px] border border-gray-100 bg-gray-50/70 px-4 py-4 space-y-3 min-h-[320px] max-h-[440px] overflow-y-auto"
      >
        {messages.length === 0 ? (
          <p className="text-[12px] text-gray-400 leading-6">上面那些“值得继续追问的问题”可以直接点，也可以在下面自己输入更具体的问题。</p>
        ) : (
          messages.map((message, index) => (
            <div key={`${message.role}-${message.createdAt}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[88%] rounded-[18px] px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-[#5B7BFE] text-white shadow-[0_8px_20px_rgba(91,123,254,0.18)]'
                    : 'bg-white text-gray-700 border border-gray-100'
                }`}
              >
                <p className="text-[14px] leading-7 whitespace-pre-line">{message.content}</p>
                <p className={`text-[11px] mt-2 ${message.role === 'user' ? 'text-white/70' : 'text-gray-400'}`}>{formatChatTime(message.createdAt)}</p>
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="max-w-[88%] rounded-[18px] px-4 py-3 bg-white text-gray-500 border border-gray-100">
              <p className="text-[14px] leading-7">大周正在结合这篇情报继续思考…</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 flex gap-3">
        <textarea
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder="例如：这篇新闻真正值得我们追问的，不是表面结论，而是哪层变化？"
          className="flex-1 min-h-[120px] rounded-[20px] border border-gray-200 bg-gray-50 px-4 py-3 text-[14px] leading-7 text-gray-700 outline-none resize-none focus:border-[#5B7BFE] focus:bg-white"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={loading || !draft.trim()}
          className="shrink-0 self-end inline-flex items-center gap-2 rounded-[18px] bg-[#5B7BFE] px-4 py-3 text-[13px] font-semibold text-white shadow-[0_8px_20px_rgba(91,123,254,0.22)] transition-all hover:bg-[#4a6be6] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <SendHorizontal size={14} />
          发送
        </button>
      </div>
    </section>
  );
}
~~~

## `src/renderer/components/topics/TopicIntelDetailPanel.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import { ArrowUpRight, Bookmark, BookmarkCheck, ExternalLink, FilePlus2, Newspaper, Sparkles } from 'lucide-react';

import type { Task, TopicCandidate, TopicCandidateChatMessage, TopicCandidateInsight } from '../../../shared/types';
import { TopicIntelChatPanel } from './TopicIntelChatPanel';

type TopicIntelDetailPanelProps = {
  candidate: TopicCandidate | null;
  radarTitle?: string;
  insight?: TopicCandidateInsight | null;
  isLoadingInsight: boolean;
  saved: boolean;
  relatedTasks: Task[];
  chatMessages: TopicCandidateChatMessage[];
  chatDraft: string;
  isChatting: boolean;
  onToggleSaved: () => void;
  onAskDiscussionPrompt: (question: string) => void;
  onChatDraftChange: (value: string) => void;
  onSendChat: () => void;
  onOpenTask: () => void;
  onOpenSource: () => void;
};

function formatPublishedAt(value?: string | null) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function normalizeEditorialNote(value?: string | null) {
  return (value || '')
    .trim()
    .replace(/^大周(?:的)?(?:前哨判断|判断)[：:]\s*/, '');
}

export function TopicIntelDetailPanel({
  candidate,
  radarTitle,
  insight,
  isLoadingInsight,
  saved,
  relatedTasks,
  chatMessages,
  chatDraft,
  isChatting,
  onToggleSaved,
  onAskDiscussionPrompt,
  onChatDraftChange,
  onSendChat,
  onOpenTask,
  onOpenSource,
}: TopicIntelDetailPanelProps) {
  if (!candidate) {
    return (
      <div className="h-full bg-white border border-gray-100 rounded-[32px] shadow-sm p-6 flex flex-col justify-center items-center text-center">
        <div className="w-14 h-14 rounded-2xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
          <Newspaper size={24} />
        </div>
        <h2 className="text-[18px] font-bold text-gray-900 mt-5">选择一篇情报</h2>
        <p className="text-[13px] text-gray-500 mt-2 max-w-[320px] leading-6">
          左侧会显示大周夜间抓回的情报。点开任意一篇，就能看到它和哪个雷达相关、主要观点是什么，以及能不能收进资料夹或转成任务。
        </p>
      </div>
    );
  }

  const canCreateTask = candidate.insightStatus === 'ready';
  const keyPoints = insight?.keyPoints?.length ? insight.keyPoints : ['当前还没有稳定的核心观点，建议先看原文。'];
  const writingAngles = insight?.practicalUses?.length ? insight.practicalUses : ['后续可围绕这篇内容继续追问：哪些判断值得转成文章、哪些事实值得交给同事跟进。'];
  const discussionPrompts = insight?.discussionPrompts?.length ? insight.discussionPrompts : ['如果继续深挖，这篇内容最值得追问的，是它背后到底反映了怎样的变化。'];
  const editorialNote = normalizeEditorialNote(insight?.editorialNote) || '大周还在把这篇文章里的显性观点转成更值得继续思考的前哨判断。';

  return (
    <div className="h-full bg-white border border-gray-100 rounded-[32px] shadow-sm p-6 overflow-y-auto">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-[#4a67f5] border border-blue-100">
              {radarTitle || '未命名雷达'}
            </span>
            {saved && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-100">
                资料夹
              </span>
            )}
            {relatedTasks.length > 0 && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-violet-50 text-violet-700 border border-violet-100">
                已转任务 {relatedTasks.length}
              </span>
            )}
          </div>
          <h2 className="text-[24px] font-bold text-gray-900 mt-3 leading-9">{candidate.title}</h2>
          <div className="flex flex-wrap items-center gap-3 mt-3 text-[12px] text-gray-500">
            <span>{candidate.source}</span>
            {candidate.publishedAt && <span>发布于 {formatPublishedAt(candidate.publishedAt)}</span>}
            <span>收录于 {formatPublishedAt(candidate.createdAt)}</span>
          </div>
        </div>

        <div className="flex flex-col gap-2 shrink-0">
          <button
            type="button"
            onClick={onToggleSaved}
            className={`px-4 py-2.5 rounded-xl text-[13px] font-semibold transition-all inline-flex items-center justify-center gap-2 ${
              saved ? 'bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100' : 'bg-white border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300'
            }`}
          >
            {saved ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
            {saved ? '移出资料夹' : '收进资料夹'}
          </button>
          <button
            type="button"
            disabled={!canCreateTask}
            onClick={onOpenTask}
            className={`px-4 py-2.5 rounded-xl text-[13px] font-semibold transition-all inline-flex items-center justify-center gap-2 ${
              canCreateTask
                ? 'bg-white border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300'
                : 'bg-gray-100 border border-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            <FilePlus2 size={14} />
            转任务
          </button>
          <button
            type="button"
            onClick={onOpenSource}
            className="px-4 py-2.5 rounded-xl text-[13px] font-semibold bg-white border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300 transition-all inline-flex items-center justify-center gap-2"
          >
            <ExternalLink size={14} />
            查看原文
          </button>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4">
        <section className="rounded-[24px] border border-gray-100 px-5 py-4">
          <p className="text-[12px] font-bold text-gray-900">核心观点</p>
          <div className="mt-3 space-y-3">
            {keyPoints.map((item, index) => (
              <div key={`${candidate.id}-point-${index}`} className="flex items-start gap-3 text-[13px] text-gray-600">
                <span className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center text-[11px] font-bold shrink-0">
                  {index + 1}
                </span>
                <p className="leading-6">{item}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[24px] border border-gray-100 px-5 py-4">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-violet-600" />
            <p className="text-[12px] font-bold text-gray-900">大周前哨判断</p>
          </div>
          {isLoadingInsight ? (
            <p className="text-[13px] text-gray-500 mt-3">大周正在补全这篇情报的前哨判断…</p>
          ) : (
            <p className="text-[13px] text-gray-600 mt-3 leading-7 whitespace-pre-line">{editorialNote}</p>
          )}
        </section>

        <section className="rounded-[24px] border border-gray-100 px-5 py-4">
          <p className="text-[12px] font-bold text-gray-900">可直接展开成文</p>
          <div className="mt-3 space-y-3">
            {writingAngles.map((item, index) => (
              <div key={`${candidate.id}-use-${index}`} className="flex items-start gap-3 text-[13px] text-gray-600">
                <span className="w-6 h-6 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center text-[11px] font-bold shrink-0">
                  {index + 1}
                </span>
                <p className="leading-6">{item}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[24px] border border-gray-100 px-5 py-4">
          <p className="text-[12px] font-bold text-gray-900">值得继续追问的问题</p>
          <p className="text-[12px] text-gray-500 mt-1">点任何一条问题，都可以直接让大周基于这篇情报继续回答。</p>
          <div className="mt-3 space-y-3">
            {discussionPrompts.map((item, index) => (
              <button
                key={`${candidate.id}-discussion-${index}`}
                type="button"
                onClick={() => onAskDiscussionPrompt(item)}
                className="w-full flex items-start gap-3 rounded-[18px] border border-sky-100 bg-sky-50/60 px-3 py-3 text-left transition-all hover:border-sky-200 hover:bg-sky-50"
              >
                <span className="w-6 h-6 rounded-full bg-white text-sky-700 flex items-center justify-center text-[11px] font-bold shrink-0">
                  {index + 1}
                </span>
                <span className="flex-1 text-[13px] leading-6 text-slate-700">{item}</span>
                <ArrowUpRight size={14} className="shrink-0 mt-1 text-sky-600" />
              </button>
            ))}
          </div>
        </section>

        <TopicIntelChatPanel
          messages={chatMessages}
          draft={chatDraft}
          loading={isChatting}
          onDraftChange={onChatDraftChange}
          onSend={onSendChat}
        />
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/topics/TopicIntelInboxCard.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import { Newspaper, Trash2 } from 'lucide-react';

import type { TopicCandidate, TopicCandidateInsight } from '../../../shared/types';

type TopicIntelInboxCardProps = {
  candidate: TopicCandidate;
  radarTitle: string;
  insight?: TopicCandidateInsight | null;
  selected: boolean;
  read: boolean;
  saved: boolean;
  tags: string[];
  relatedTaskCount: number;
  onSelect: () => void;
  onDelete: () => void;
};

function summarizeInsight(candidate: TopicCandidate, insight?: TopicCandidateInsight | null) {
  const editorialNote = (insight?.editorialNote || '')
    .trim()
    .replace(/^大周(?:的)?(?:前哨判断|判断)[：:]\s*/, '');
  if (editorialNote) return editorialNote;
  if (insight?.overview?.trim()) return insight.overview.trim();
  return candidate.summary.trim() || '大周还在整理这篇内容的核心信息。';
}

function relationReason(candidate: TopicCandidate, radarTitle: string, insight?: TopicCandidateInsight | null) {
  if (insight?.recommendationReasons?.length) return insight.recommendationReasons[0];
  if (candidate.summary.trim()) return candidate.summary.trim();
  return `这篇内容与「${radarTitle}」相关，但当前还需要等待进一步解析。`;
}

function formatPublishedAt(value?: string | null) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function insightBadge(candidate: TopicCandidate) {
  if (candidate.insightStatus === 'ready') {
    return { label: '已解析', className: 'bg-emerald-50 text-emerald-700 border border-emerald-100' };
  }
  if (candidate.insightStatus === 'failed') {
    return { label: '解析失败', className: 'bg-rose-50 text-rose-700 border border-rose-100' };
  }
  return { label: '解析中', className: 'bg-gray-100 text-gray-500 border border-gray-200' };
}

export function TopicIntelInboxCard({
  candidate,
  radarTitle,
  insight,
  selected,
  read,
  saved,
  tags,
  relatedTaskCount,
  onSelect,
  onDelete,
}: TopicIntelInboxCardProps) {
  const badge = insightBadge(candidate);
  const points = insight?.keyPoints?.slice(0, 2) || [];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className={`rounded-[28px] border p-5 transition-all cursor-pointer ${
        selected ? 'border-[#b8c7ff] bg-[#f7f9ff] shadow-[0_12px_36px_rgba(91,123,254,0.12)]' : 'border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm'
      }`}
    >
      <div className="relative">
        <button
          type="button"
          title="删除这条情报"
          aria-label="删除这条情报"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          className="absolute right-0 top-0 z-10 w-9 h-9 rounded-full border border-rose-200 bg-white text-rose-500 shadow-sm hover:bg-rose-50 hover:text-rose-600 transition-all flex items-center justify-center"
        >
          <Trash2 size={15} />
        </button>

        <div className="mx-auto w-full max-w-[720px] min-w-0 pt-1">
          <div className="flex flex-wrap items-center justify-center gap-2 mb-2">
            {!read && <span className="w-2.5 h-2.5 rounded-full bg-[#5B7BFE] shrink-0" />}
            <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-[#4a67f5] border border-blue-100">
              {radarTitle}
            </span>
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${badge.className}`}>{badge.label}</span>
            {saved && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-100">
                资料夹
              </span>
            )}
            {relatedTaskCount > 0 && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-violet-50 text-violet-700 border border-violet-100">
                已转任务 {relatedTaskCount}
              </span>
            )}
          </div>

          <h3 className="text-[18px] font-bold text-gray-900 leading-7 text-center">{candidate.title}</h3>

          <div className="flex flex-wrap items-center justify-center gap-3 mt-3 text-[12px] text-gray-500">
            <span className="inline-flex items-center gap-1.5">
              <Newspaper size={13} />
              {candidate.source}
            </span>
            {candidate.publishedAt && <span>{formatPublishedAt(candidate.publishedAt)}</span>}
            {candidate.capturedBy && <span>{candidate.capturedBy} 抓取</span>}
          </div>

          {tags.length > 0 && (
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {tags.slice(0, 4).map((tag) => (
                <span
                  key={`${candidate.id}-tag-${tag}`}
                  className="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700"
                >
                  #{tag}
                </span>
              ))}
              {tags.length > 4 && (
                <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-3 py-1 text-[11px] font-semibold text-gray-500">
                  +{tags.length - 4}
                </span>
              )}
            </div>
          )}

          {points.length > 0 && (
            <div className="mt-4">
              <p className="text-[12px] font-bold text-gray-900 text-center">核心观点</p>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {points.map((item, index) => (
                  <span key={`${candidate.id}-point-${index}`} className="inline-flex items-center rounded-2xl bg-gray-100 px-3 py-2 text-[12px] leading-5 text-gray-700">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4">
            <p className="text-[12px] font-bold text-gray-900 text-center">大周判断</p>
            <p className="text-[13px] text-gray-600 leading-6 mt-2">{summarizeInsight(candidate, insight)}</p>
          </div>

          <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50/70 px-4 py-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#5B7BFE]">为什么相关</p>
            <p className="text-[13px] text-slate-700 leading-6 mt-2">{relationReason(candidate, radarTitle, insight)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
~~~

## `src/renderer/components/topics/TopicsManagementView.tsx`

- 编码: `utf-8`

~~~tsx
import React, { useEffect, useMemo, useState } from 'react';
import { Activity, CheckSquare, Plus, RefreshCw, Search, Sparkles, Target, X } from 'lucide-react';

import type {
  MentionCandidate,
  SessionUser,
  Task,
  TaskList,
  TaskSettings,
  TopicCandidate,
  TopicCandidateChatMessage,
  TopicCandidateInsight,
  TopicsSettings,
  TopicRadar,
  TopicRadarPreferredSource,
} from '../../../shared/types';
import {
  assistRadarDraft,
  askCandidateQuestion,
  captureTopicRadars,
  createRadar,
  createTask,
  deleteCandidate,
  getCandidateInsights,
  getMentionCandidates,
  saveTaskNote,
  suggestRadarSourceLabel,
  updateRadar,
} from '../../lib/api';
import { TopicIntelDetailPanel } from './TopicIntelDetailPanel';
import { TopicIntelInboxCard } from './TopicIntelInboxCard';

type TopicReadFilter = 'all' | 'unread';

type TopicCandidateLocalPreference = {
  saved?: boolean;
  note?: string;
  tags?: string[];
  read?: boolean;
};

type TopicCandidateLegacyPreference = TopicCandidateLocalPreference & {
  archived?: boolean;
  favorite?: boolean;
  favoriteNote?: string;
};

type TopicLocalState = {
  byCandidateId: Record<string, TopicCandidateLocalPreference>;
};

type TopicQuickTaskDraft = {
  title: string;
  desc: string;
  listId: string;
  priority: 'low' | 'normal' | 'high';
  dueDate: string;
  ddl: string;
  ownerId: string;
  ownerName: string;
  note: string;
};

type TopicRadarDraft = {
  id: string;
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
};

type TopicsManagementViewProps = {
  radars: TopicRadar[];
  candidates: TopicCandidate[];
  tasks: Task[];
  activeTaskLists: TaskList[];
  effectiveTaskSettings: TaskSettings;
  topicsSettingsState: TopicsSettings;
  currentSessionUser: SessionUser | null;
  currentOperatorName: string;
  flash: (type: 'success' | 'error' | 'info', text: string) => void;
  onTopicsReload: () => Promise<unknown>;
  onTasksReload: () => Promise<unknown>;
};

const TOPIC_LOCAL_STATE_STORAGE_KEY = 'yiyu.workbench.topics.local-state.v2';
const TOPIC_LEGACY_STATE_STORAGE_KEY = 'yiyu.workbench.topics.local-state.v1';
const EMPTY_TOPIC_LOCAL_STATE: TopicLocalState = {
  byCandidateId: {},
};
const EMPTY_TOPIC_CANDIDATE_PREFERENCE: TopicCandidateLocalPreference = {
  saved: false,
  note: '',
  tags: [],
  read: false,
};

function normalizeCustomTags(value: unknown) {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value
    .map((item) => (typeof item === 'string' ? item.trim().replace(/\s+/g, ' ') : ''))
    .filter((item) => {
      const key = item.toLowerCase();
      if (!item || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function normalizePreference(preference?: TopicCandidateLegacyPreference | null): TopicCandidateLocalPreference {
  const note =
    typeof preference?.note === 'string'
      ? preference.note.trimStart()
      : typeof preference?.favoriteNote === 'string'
        ? preference.favoriteNote.trimStart()
        : '';
  const tags = normalizeCustomTags(preference?.tags);
  return {
    saved: Boolean(preference?.saved || preference?.favorite || preference?.archived || note.trim() || tags.length),
    note,
    tags,
    read: Boolean(preference?.read),
  };
}

function normalizeTopicLocalState(input: unknown): TopicLocalState {
  if (!input || typeof input !== 'object' || typeof (input as TopicLocalState).byCandidateId !== 'object') {
    return EMPTY_TOPIC_LOCAL_STATE;
  }

  const nextByCandidateId: Record<string, TopicCandidateLocalPreference> = {};
  Object.entries((input as TopicLocalState).byCandidateId).forEach(([candidateId, preference]) => {
    nextByCandidateId[candidateId] = normalizePreference(preference as TopicCandidateLegacyPreference);
  });

  return { byCandidateId: nextByCandidateId };
}

function readTopicLocalState(): TopicLocalState {
  if (typeof window === 'undefined') return EMPTY_TOPIC_LOCAL_STATE;
  try {
    const raw = window.localStorage.getItem(TOPIC_LOCAL_STATE_STORAGE_KEY) || window.localStorage.getItem(TOPIC_LEGACY_STATE_STORAGE_KEY);
    if (!raw) return EMPTY_TOPIC_LOCAL_STATE;
    return normalizeTopicLocalState(JSON.parse(raw));
  } catch {
    return EMPTY_TOPIC_LOCAL_STATE;
  }
}

function writeTopicLocalState(state: TopicLocalState) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(TOPIC_LOCAL_STATE_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // In some Electron/browser contexts storage may be unavailable or read-only.
  }
}

function buildTopicAttachmentNote(
  candidate: TopicCandidate,
  radarTitle: string,
  insight: TopicCandidateInsight | null | undefined,
  operatorNote: string,
) {
  const lines = [
    `【情报附件】${candidate.title}`,
    `关联雷达：${radarTitle}`,
    `来源：${candidate.source}`,
  ];

  if (candidate.publishedAt) {
    lines.push(`发布时间：${candidate.publishedAt}`);
  }
  if (candidate.sourceUrl) {
    lines.push(`原文链接：${candidate.sourceUrl}`);
  }

  const relationReasons = insight?.recommendationReasons?.filter((item) => item.trim()) || [];
  const keyPoints = insight?.keyPoints?.filter((item) => item.trim()) || [];
  const practicalUses = insight?.practicalUses?.filter((item) => item.trim()) || [];
  const editorialNote = insight?.editorialNote?.trim() || '';
  const discussionPrompts = insight?.discussionPrompts?.filter((item) => item.trim()) || [];

  lines.push('');
  lines.push('为什么和当前雷达相关：');
  if (relationReasons.length) {
    relationReasons.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push(`1. 这篇内容当前被归入「${radarTitle}」雷达下，建议先按这个主题核对。`);
  }

  lines.push('');
  lines.push('主要内容：');
  lines.push(insight?.overview?.trim() || candidate.summary || '当前只有原始摘要，尚未形成完整综述。');

  lines.push('');
  lines.push('核心观点：');
  if (keyPoints.length) {
    keyPoints.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 当前还没有稳定的核心观点提炼，建议直接点开原文。');
  }

  lines.push('');
  lines.push('大周前哨判断：');
  lines.push(editorialNote || '当前还没有稳定的大周前哨判断，建议先结合原文和核心观点继续讨论。');

  lines.push('');
  lines.push('可直接展开成文：');
  if (practicalUses.length) {
    practicalUses.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 后续可围绕它是否值得写成文章、是否需要团队跟进继续讨论。');
  }

  lines.push('');
  lines.push('值得继续追问的问题：');
  if (discussionPrompts.length) {
    discussionPrompts.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 这篇内容背后最值得继续追问的变化，到底是什么？');
  }

  if (operatorNote.trim()) {
    lines.push('');
    lines.push('给同事的补充：');
    lines.push(operatorNote.trim());
  }

  return lines.join('\n');
}

function candidateSortTime(candidate: TopicCandidate) {
  return new Date(candidate.publishedAt || candidate.createdAt).getTime();
}

function normalizeTagDraft(value: string) {
  return value.trim().replace(/\s+/g, ' ');
}

export function TopicsManagementView({
  radars,
  candidates,
  tasks,
  activeTaskLists,
  effectiveTaskSettings,
  topicsSettingsState,
  currentSessionUser,
  currentOperatorName,
  flash,
  onTopicsReload,
  onTasksReload,
}: TopicsManagementViewProps) {
  const [selectedRadarId, setSelectedRadarId] = useState<string>('all');
  const [readFilter, setReadFilter] = useState<TopicReadFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [tagDraft, setTagDraft] = useState('');
  const [localState, setLocalState] = useState<TopicLocalState>(() => readTopicLocalState());
  const [editingPrefIndex, setEditingPrefIndex] = useState<number | null>(null);
  const [tempPref, setTempPref] = useState<TopicRadarDraft | null>(null);
  const [preferredSourceDraft, setPreferredSourceDraft] = useState('');
  const [isAssistingRadar, setIsAssistingRadar] = useState(false);
  const [isGeneratingSourceLabel, setIsGeneratingSourceLabel] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [globalMessage, setGlobalMessage] = useState<string | null>(null);
  const [insightCache, setInsightCache] = useState<Record<string, TopicCandidateInsight>>({});
  const [insightLoadingId, setInsightLoadingId] = useState<string | null>(null);
  const [chatByCandidateId, setChatByCandidateId] = useState<Record<string, TopicCandidateChatMessage[]>>({});
  const [chatDraftByCandidateId, setChatDraftByCandidateId] = useState<Record<string, string>>({});
  const [chatLoadingCandidateId, setChatLoadingCandidateId] = useState<string | null>(null);
  const [taskModalCandidateId, setTaskModalCandidateId] = useState<string | null>(null);
  const [taskDraft, setTaskDraft] = useState<TopicQuickTaskDraft | null>(null);
  const [taskAssignees, setTaskAssignees] = useState<MentionCandidate[]>([]);
  const [isPreparingTaskModal, setIsPreparingTaskModal] = useState(false);
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);

  const defaultListId = effectiveTaskSettings.defaultListId || activeTaskLists[0]?.id || 'list-0';
  const radarMap = useMemo(() => new Map(radars.map((item) => [item.id, item])), [radars]);
  const relatedTasksByCandidate = useMemo(() => {
    const grouped = new Map<string, Task[]>();
    tasks.forEach((task) => {
      if (task.sourceType !== 'topic_candidate' || !task.sourceId) return;
      const rows = grouped.get(task.sourceId) || [];
      rows.push(task);
      grouped.set(task.sourceId, rows);
    });
    return grouped;
  }, [tasks]);
  const radarCards = useMemo(() => {
    const visible = [...radars].slice(-5).map((item) => ({
      id: item.id,
      title: item.title,
      prompt: item.prompt,
      timeRange: item.timeRange,
      preferredSources: item.preferredSources || [],
      candidateCount: candidates.filter((candidate) => candidate.radarId === item.id).length,
    }));
    visible.push({
      id: 'placeholder-new',
      title: '',
      prompt: '',
      timeRange: topicsSettingsState.defaultTimeRange,
      preferredSources: [],
      candidateCount: 0,
    });
    return visible;
  }, [candidates, radars, topicsSettingsState.defaultTimeRange]);

  const preferenceOf = (candidateId: string) => localState.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
  const isSavedCandidate = (candidate: TopicCandidate, preference = preferenceOf(candidate.id)) =>
    Boolean(preference.saved || candidate.status === 'archived');
  const updateLocalPreference = (candidateId: string, patch: Partial<TopicCandidateLocalPreference>) => {
    setLocalState((prev) => {
      const current = prev.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
      const nextPreference = normalizePreference({
        ...current,
        ...patch,
      });
      const shouldRemove =
        !nextPreference.saved &&
        !nextPreference.read &&
        !nextPreference.note?.trim() &&
        !(nextPreference.tags?.length);
      const nextByCandidateId = { ...prev.byCandidateId };
      if (shouldRemove) {
        delete nextByCandidateId[candidateId];
      } else {
        nextByCandidateId[candidateId] = nextPreference;
      }
      const next: TopicLocalState = {
        byCandidateId: nextByCandidateId,
      };
      writeTopicLocalState(next);
      return next;
    });
  };

  const viewCounts = useMemo(() => {
    const counts = {
      new: 0,
      saved: 0,
      task_linked: 0,
      unread: 0,
    };
    candidates.forEach((candidate) => {
      const preference = preferenceOf(candidate.id);
      const saved = isSavedCandidate(candidate, preference);
      const linked = (relatedTasksByCandidate.get(candidate.id) || []).length > 0;
      const read = Boolean(preference.read);
      if (!read) counts.unread += 1;
      if (!saved && !linked) counts.new += 1;
      if (saved) counts.saved += 1;
      if (linked) counts.task_linked += 1;
    });
    return counts;
  }, [candidates, localState, relatedTasksByCandidate]);

  const filteredCandidates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return candidates
      .filter((candidate) => {
        const preference = preferenceOf(candidate.id);
        const saved = isSavedCandidate(candidate, preference);
        const linked = (relatedTasksByCandidate.get(candidate.id) || []).length > 0;
        const read = Boolean(preference.read);
        const customTags = preference.tags || [];

        if (selectedRadarId !== 'all' && candidate.radarId !== selectedRadarId) return false;
        if (readFilter === 'unread' && read) return false;
        if (!query) return true;

        const radarTitle = radarMap.get(candidate.radarId)?.title || '';
        const insight = insightCache[candidate.id];
        const corpus = [
          candidate.title,
          candidate.summary,
          candidate.source,
          radarTitle,
          preference.note || '',
          ...customTags,
          insight?.overview || '',
          ...(insight?.keyPoints || []),
          ...(insight?.recommendationReasons || []),
          ...(insight?.practicalUses || []),
        ]
          .join(' ')
          .toLowerCase();
        return corpus.includes(query);
      })
      .sort((left, right) => candidateSortTime(right) - candidateSortTime(left));
  }, [candidates, insightCache, localState, radarMap, readFilter, relatedTasksByCandidate, searchQuery, selectedRadarId]);

  const selectedCandidate = useMemo(
    () => filteredCandidates.find((candidate) => candidate.id === selectedCandidateId) || filteredCandidates[0] || null,
    [filteredCandidates, selectedCandidateId],
  );
  const selectedInsight = selectedCandidate ? insightCache[selectedCandidate.id] || null : null;
  const selectedRadarTitle = selectedCandidate ? radarMap.get(selectedCandidate.radarId)?.title || '未命名雷达' : '';
  const selectedRelatedTasks = selectedCandidate ? relatedTasksByCandidate.get(selectedCandidate.id) || [] : [];
  const selectedChatMessages = selectedCandidate ? chatByCandidateId[selectedCandidate.id] || [] : [];
  const selectedChatDraft = selectedCandidate ? chatDraftByCandidateId[selectedCandidate.id] || '' : '';
  const unreadCandidates = useMemo(
    () => candidates.filter((candidate) => !preferenceOf(candidate.id).read).length,
    [candidates, localState],
  );

  useEffect(() => {
    if (!filteredCandidates.length) {
      if (selectedCandidateId) setSelectedCandidateId('');
      return;
    }
    if (!filteredCandidates.some((candidate) => candidate.id === selectedCandidateId)) {
      setSelectedCandidateId(filteredCandidates[0].id);
    }
  }, [filteredCandidates, selectedCandidateId]);

  useEffect(() => {
    if (!selectedCandidateId) return;
    const preference = preferenceOf(selectedCandidateId);
    if (preference.read) return;
    updateLocalPreference(selectedCandidateId, { read: true });
  }, [selectedCandidateId]);

  useEffect(() => {
    setTagDraft('');
  }, [selectedCandidateId]);

  useEffect(() => {
    if (!selectedCandidate || selectedCandidate.insightStatus !== 'ready') return;
    if (insightCache[selectedCandidate.id]) return;
    let active = true;
    setInsightLoadingId(selectedCandidate.id);
    void getCandidateInsights(selectedCandidate.id)
      .then((insight) => {
        if (!active) return;
        setInsightCache((prev) => ({ ...prev, [selectedCandidate.id]: insight }));
      })
      .catch((error) => {
        if (!active) return;
        flash('error', error instanceof Error ? error.message : '情报详情加载失败');
      })
      .finally(() => {
        if (!active) return;
        setInsightLoadingId((current) => (current === selectedCandidate.id ? null : current));
      });
    return () => {
      active = false;
    };
  }, [flash, insightCache, selectedCandidate]);

  const showMessage = (message: string) => {
    setGlobalMessage(message);
    window.setTimeout(() => {
      setGlobalMessage((current) => (current === message ? null : current));
    }, 3200);
  };

  const ensureInsightLoaded = async (candidate: TopicCandidate) => {
    if (insightCache[candidate.id]) return insightCache[candidate.id];
    const insight = await getCandidateInsights(candidate.id);
    setInsightCache((prev) => ({ ...prev, [candidate.id]: insight }));
    return insight;
  };

  const ensureTaskAssignees = (items: MentionCandidate[]) => {
    const next = [...items];
    if (currentSessionUser && !next.some((item) => item.id === currentSessionUser.id)) {
      next.unshift({
        id: currentSessionUser.id,
        fullName: currentSessionUser.fullName,
        email: currentSessionUser.email,
        primaryRole: currentSessionUser.primaryRole,
        isSelf: true,
      });
    }
    return next;
  };

  const handleAssistRadarDraft = async () => {
    if (!tempPref?.prompt.trim()) {
      flash('error', '请先填写追踪内容说明');
      return;
    }
    setIsAssistingRadar(true);
    try {
      const assisted = await assistRadarDraft(tempPref.prompt, tempPref.timeRange);
      setTempPref((prev) => (
        prev
          ? {
              ...prev,
              title: assisted.title,
              prompt: assisted.prompt,
            }
          : prev
      ));
      showMessage('已补强检索说明，并同步提炼标题');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : 'AI 补强失败');
    } finally {
      setIsAssistingRadar(false);
    }
  };

  const handleAddPreferredSource = async () => {
    if (!tempPref) return;
    if (!preferredSourceDraft.trim()) {
      flash('error', '请先填写优先检索的网址');
      return;
    }
    setIsGeneratingSourceLabel(true);
    try {
      const suggested = await suggestRadarSourceLabel(preferredSourceDraft);
      setTempPref((prev) => {
        if (!prev) return prev;
        if (prev.preferredSources.some((item) => item.url === suggested.url)) {
          return prev;
        }
        return {
          ...prev,
          preferredSources: [...prev.preferredSources, { url: suggested.url, label: suggested.label }],
        };
      });
      setPreferredSourceDraft('');
      flash('success', `已加入优先网址「${suggested.label}」`);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '网址添加失败');
    } finally {
      setIsGeneratingSourceLabel(false);
    }
  };

  const handleRemovePreferredSource = (url: string) => {
    setTempPref((prev) => (prev ? { ...prev, preferredSources: prev.preferredSources.filter((item) => item.url !== url) } : prev));
  };

  const handleSavePrefEdit = async () => {
    if (!tempPref || !tempPref.prompt.trim()) return;
    try {
      const payload = {
        title: tempPref.title.trim() || '自定义追踪项',
        prompt: tempPref.prompt.trim(),
        timeRange: tempPref.timeRange,
        preferredSources: tempPref.preferredSources,
      };
      const isExistingRadar = !tempPref.id.startsWith('placeholder-');
      if (isExistingRadar) {
        await updateRadar(tempPref.id, payload);
      } else {
        await createRadar(payload);
      }
      await onTopicsReload();
      setEditingPrefIndex(null);
      setTempPref(null);
      setPreferredSourceDraft('');
      showMessage(isExistingRadar ? '雷达规则已更新' : '已新增雷达规则');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存失败');
    }
  };

  const handleCapture = async () => {
    setIsCapturing(true);
    try {
      const result = await captureTopicRadars();
      await onTopicsReload();
      const totalFetched = result.runs.reduce((sum, item) => sum + item.fetchedCount, 0);
      if (result.totalCreated > 0) {
        showMessage(`大周本轮抓到 ${totalFetched} 条线索，新增 ${result.totalCreated} 篇情报，正在继续解析`);
      } else if (totalFetched > 0 && result.totalSkipped > 0) {
        showMessage(`大周本轮抓到 ${totalFetched} 条线索，但都已在历史情报里，本次没有新增`);
      } else {
        showMessage('大周完成本轮检索，但暂时没有新的高相关情报');
      }
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '大周抓取失败');
    } finally {
      setIsCapturing(false);
    }
  };

  const handleToggleSaved = (candidate: TopicCandidate) => {
    const current = preferenceOf(candidate.id);
    const currentlySaved = isSavedCandidate(candidate, current);
    if (candidate.status === 'archived' && currentlySaved) {
      flash('info', '这篇情报来自历史归档记录，当前只支持继续保留在资料夹中');
      return;
    }
    const next = !currentlySaved;
    updateLocalPreference(candidate.id, { saved: next });
    flash('success', next ? '已收进资料夹' : '已从资料夹移出');
  };

  const handleAddCustomTag = (candidate: TopicCandidate) => {
    const nextTag = normalizeTagDraft(tagDraft);
    if (!nextTag) return;
    const currentTags = preferenceOf(candidate.id).tags || [];
    if (currentTags.some((tag) => tag.toLowerCase() === nextTag.toLowerCase())) {
      flash('info', '这个标签已经存在');
      return;
    }
    updateLocalPreference(candidate.id, {
      saved: true,
      tags: [...currentTags, nextTag],
    });
    setTagDraft('');
    flash('success', `已添加标签「${nextTag}」`);
  };

  const handleRemoveCustomTag = (candidate: TopicCandidate, tag: string) => {
    const currentTags = preferenceOf(candidate.id).tags || [];
    updateLocalPreference(candidate.id, {
      saved: currentTags.length > 1 || Boolean(preferenceOf(candidate.id).note?.trim()),
      tags: currentTags.filter((item) => item !== tag),
    });
    flash('success', `已移除标签「${tag}」`);
  };

  const handleDeleteCandidate = async (candidate: TopicCandidate) => {
    try {
      await deleteCandidate(candidate.id);
      setInsightCache((prev) => {
        if (!prev[candidate.id]) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      if (taskModalCandidateId === candidate.id) {
        setTaskModalCandidateId(null);
        setTaskDraft(null);
        setTaskAssignees([]);
      }
      if (selectedCandidateId === candidate.id) {
        setSelectedCandidateId('');
      }
      setChatByCandidateId((prev) => {
        if (!prev[candidate.id]) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      setChatDraftByCandidateId((prev) => {
        if (!(candidate.id in prev)) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      setChatLoadingCandidateId((current) => (current === candidate.id ? null : current));
      await onTopicsReload();
      flash('success', '情报已删除');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '删除失败');
    }
  };

  const setCandidateChatDraft = (candidateId: string, value: string) => {
    setChatDraftByCandidateId((prev) => {
      if (!value) {
        if (!(candidateId in prev)) return prev;
        const next = { ...prev };
        delete next[candidateId];
        return next;
      }
      return {
        ...prev,
        [candidateId]: value,
      };
    });
  };

  const handleAskCandidateQuestion = async (candidate: TopicCandidate, forcedQuestion?: string) => {
    const question = (forcedQuestion ?? (chatDraftByCandidateId[candidate.id] || '')).trim();
    if (!question) return;
    if (chatLoadingCandidateId === candidate.id) return;

    const userMessage: TopicCandidateChatMessage = {
      role: 'user',
      content: question,
      createdAt: new Date().toISOString(),
    };
    const history = (chatByCandidateId[candidate.id] || []).slice(-8);

    setChatByCandidateId((prev) => ({
      ...prev,
      [candidate.id]: [...(prev[candidate.id] || []), userMessage],
    }));
    if (!forcedQuestion) {
      setCandidateChatDraft(candidate.id, '');
    }
    setChatLoadingCandidateId(candidate.id);

    try {
      const response = await askCandidateQuestion(candidate.id, {
        question,
        history,
      });
      setChatByCandidateId((prev) => ({
        ...prev,
        [candidate.id]: [...(prev[candidate.id] || []), response.message],
      }));
    } catch (error) {
      const fallbackMessage: TopicCandidateChatMessage = {
        role: 'assistant',
        content: error instanceof Error ? `我暂时没能接住这个追问：${error.message}` : '我暂时没能接住这个追问，请稍后再试。',
        createdAt: new Date().toISOString(),
      };
      setChatByCandidateId((prev) => ({
        ...prev,
        [candidate.id]: [...(prev[candidate.id] || []), fallbackMessage],
      }));
      flash('error', error instanceof Error ? error.message : '追问失败');
    } finally {
      setChatLoadingCandidateId((current) => (current === candidate.id ? null : current));
    }
  };

  const openTaskModal = async (candidate: TopicCandidate) => {
    if (candidate.insightStatus !== 'ready') {
      flash('error', '请等大周完成解析后再转任务');
      return;
    }

    const defaultOwnerId = currentSessionUser?.id || '';
    setSelectedCandidateId(candidate.id);
    setTaskModalCandidateId(candidate.id);
    setTaskDraft({
      title: candidate.title.trim(),
      desc: `请查看任务备注中的情报附件，并结合团队安排决定下一步处理方式。`,
      listId: defaultListId,
      priority: 'normal',
      dueDate: '',
      ddl: '待确认',
      ownerId: defaultOwnerId,
      ownerName: currentSessionUser?.fullName || currentOperatorName,
      note: '',
    });
    setIsPreparingTaskModal(true);
    try {
      const [mentionItems] = await Promise.all([
        getMentionCandidates('').catch(() => []),
        ensureInsightLoaded(candidate),
      ]);
      const assignees = ensureTaskAssignees(mentionItems);
      setTaskAssignees(assignees);
      const defaultOwner = assignees.find((item) => item.id === defaultOwnerId) || assignees[0];
      if (defaultOwner) {
        setTaskDraft((prev) =>
          prev
            ? {
                ...prev,
                ownerId: defaultOwner.id,
                ownerName: defaultOwner.fullName,
              }
            : prev,
        );
      }
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '任务弹窗准备失败');
    } finally {
      setIsPreparingTaskModal(false);
    }
  };

  const handleSubmitTask = async () => {
    const modalCandidate = candidates.find((candidate) => candidate.id === taskModalCandidateId);
    if (!modalCandidate || !taskDraft) return;
    if (!taskDraft.title.trim()) {
      flash('error', '请填写任务标题');
      return;
    }
    if (!taskDraft.listId) {
      flash('error', '请先选择任务清单');
      return;
    }

    setIsSubmittingTask(true);
    try {
      const owner = taskAssignees.find((item) => item.id === taskDraft.ownerId);
      const ownerId = owner?.id || taskDraft.ownerId || null;
      const ownerName = owner?.fullName || taskDraft.ownerName || currentOperatorName;
      const createdTask = await createTask({
        title: taskDraft.title.trim(),
        desc: taskDraft.desc.trim(),
        priority: taskDraft.priority,
        listId: taskDraft.listId,
        dueDate: taskDraft.dueDate || null,
        ddl: taskDraft.ddl.trim() || taskDraft.dueDate || '待确认',
        ownerId,
        ownerName,
        collaboratorIds: ownerId ? [ownerId] : [],
        tagIds: [],
        tags: ['情报跟进'],
        sourceType: 'topic_candidate',
        sourceId: modalCandidate.id,
      });
      const insight = await ensureInsightLoaded(modalCandidate);
      const radarTitle = radarMap.get(modalCandidate.radarId)?.title || '未命名雷达';
      await saveTaskNote(createdTask.id, buildTopicAttachmentNote(modalCandidate, radarTitle, insight, taskDraft.note));
      await onTasksReload();
      setTaskModalCandidateId(null);
      setTaskDraft(null);
      setTaskAssignees([]);
      showMessage('已同步到任务，并附上当前情报说明');
      flash('success', '情报已转成任务');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '转任务失败');
    } finally {
      setIsSubmittingTask(false);
    }
  };

  const taskModalCandidate = taskModalCandidateId
    ? candidates.find((candidate) => candidate.id === taskModalCandidateId) || null
    : null;
  const taskOwnerOptions = taskAssignees.length
    ? taskAssignees
    : currentSessionUser
      ? [{
          id: currentSessionUser.id,
          fullName: currentSessionUser.fullName,
          email: currentSessionUser.email,
          primaryRole: currentSessionUser.primaryRole,
          isSelf: true,
        }]
      : [];

  return (
    <div className="h-full flex flex-col bg-[#F9FAFB] overflow-hidden relative font-sans text-gray-800">
      <div className="bg-white border-b border-gray-100 px-5 lg:px-8 py-3.5 shrink-0 z-10">
        <div className="flex flex-col gap-2.5">
          {/* Row 1: title + inline stats + actions */}
          <div className="flex items-center gap-4">
            <h1 className="text-[15px] font-semibold text-gray-800 flex items-center gap-1.5 shrink-0">
              <Search size={15} className="text-[#5B7BFE]" />
              情报站
            </h1>
            <div className="flex items-center gap-3 text-[12px] text-gray-400 ml-1">
              <span><span className="font-semibold text-[#5B7BFE]">{viewCounts.new}</span> 新发现</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{unreadCandidates}</span> 未读</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{viewCounts.saved}</span> 资料夹</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{viewCounts.task_linked}</span> 已转任务</span>
            </div>
            <div className="flex items-center gap-2 ml-auto shrink-0 flex-wrap justify-end">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="搜索标题、摘要、来源或核心观点"
                  className="w-[200px] rounded-xl border border-gray-200 bg-gray-50 pl-9 pr-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
                />
              </div>
              <select
                value={selectedRadarId}
                onChange={(event) => setSelectedRadarId(event.target.value)}
                className="w-[132px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
              >
                <option value="all">全部雷达</option>
                {radars.map((radar) => (
                  <option key={radar.id} value={radar.id}>
                    {radar.title}
                  </option>
                ))}
              </select>
              <select
                value={readFilter}
                onChange={(event) => setReadFilter(event.target.value as TopicReadFilter)}
                className="w-[132px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
              >
                <option value="all">全部阅读状态</option>
                <option value="unread">只看未读</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  const placeholderIndex = radarCards.findIndex((item) => item.id === 'placeholder-new');
                  setEditingPrefIndex(placeholderIndex);
                  setPreferredSourceDraft('');
                  setTempPref({ id: 'placeholder-new', title: '', prompt: '', timeRange: topicsSettingsState.defaultTimeRange, preferredSources: [] });
                }}
                className="px-3 py-1.5 rounded-lg text-[12px] font-medium bg-white border border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-700 transition-all inline-flex items-center gap-1.5"
              >
                <Plus size={13} />
                管理雷达
              </button>
              <button
                type="button"
                onClick={() => void handleCapture()}
                disabled={isCapturing || radars.length === 0}
                className="px-3.5 py-1.5 rounded-lg text-[12px] font-medium bg-[#5B7BFE] text-white hover:bg-[#4a6be6] disabled:opacity-50 disabled:cursor-not-allowed transition-all inline-flex items-center gap-1.5"
              >
                {isCapturing ? <RefreshCw size={13} className="animate-spin" /> : <Search size={13} />}
                {isCapturing ? '抓取中…' : '抓取'}
              </button>
            </div>
          </div>

          {/* Row 2: radar chips */}
          <div className="flex gap-2 w-full overflow-x-auto scrollbar-hide">
            {radarCards.map((pref, index) => {
              const isPlaceholder = pref.id === 'placeholder-new';
              return (
                <button
                  key={pref.id || index}
                  type="button"
                  onClick={() => {
                    setEditingPrefIndex(index);
                    setPreferredSourceDraft('');
                    setTempPref({
                      id: pref.id,
                      title: pref.title,
                      prompt: pref.prompt,
                      timeRange: pref.timeRange,
                      preferredSources: pref.preferredSources || [],
                    });
                  }}
                  className={`shrink-0 rounded-full border px-3 py-1 text-left transition-all ${
                    isPlaceholder
                      ? 'border-dashed border-gray-200 text-gray-400 hover:border-[#b8c7ff] hover:text-[#5B7BFE]'
                      : 'bg-[#f7f9ff] border-[#e4eaff] text-[#5B7BFE] hover:bg-[#eef2ff]'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <Activity size={11} />
                    <span className="text-[12px] font-medium whitespace-nowrap">{pref.title || '添加雷达…'}</span>
                    {!isPlaceholder && (
                      <span className="text-[10px] text-[#5B7BFE]/50 whitespace-nowrap">{pref.candidateCount}</span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>

          {globalMessage && (
            <div className="flex items-center justify-center animate-in fade-in absolute left-1/2 -translate-x-1/2 top-4 z-50">
              <div className="text-[12px] font-bold text-emerald-600 bg-emerald-50 px-4 py-2 rounded-full shadow-sm flex items-center gap-2">
                <CheckSquare size={14} /> {globalMessage}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-[1.12fr_0.88fr] gap-6 p-8 overflow-y-auto">
        <div className="bg-white border border-gray-100 rounded-[32px] shadow-sm p-6 overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div>
              <h2 className="text-[18px] font-bold text-gray-900">情报收件箱</h2>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            {filteredCandidates.length > 0 ? (
              filteredCandidates.map((candidate) => {
                const preference = preferenceOf(candidate.id);
                const radarTitle = radarMap.get(candidate.radarId)?.title || '未命名雷达';
                return (
                  <TopicIntelInboxCard
                    key={candidate.id}
                    candidate={candidate}
                    radarTitle={radarTitle}
                    insight={insightCache[candidate.id]}
                    selected={selectedCandidate?.id === candidate.id}
                    read={Boolean(preference.read)}
                    saved={isSavedCandidate(candidate, preference)}
                    tags={preference.tags || []}
                    relatedTaskCount={(relatedTasksByCandidate.get(candidate.id) || []).length}
                    onSelect={() => setSelectedCandidateId(candidate.id)}
                    onDelete={() => void handleDeleteCandidate(candidate)}
                  />
                );
              })
            ) : (
              <div className="rounded-[28px] border border-dashed border-gray-200 bg-gray-50/70 px-6 py-12 text-center">
                <p className="text-[16px] font-bold text-gray-900">当前筛选条件下还没有情报</p>
                <p className="text-[13px] text-gray-500 mt-2">可以切换视图、放宽筛选，或者让大周立即再抓一轮。</p>
              </div>
            )}
          </div>
        </div>

        <TopicIntelDetailPanel
          candidate={selectedCandidate}
          radarTitle={selectedRadarTitle}
          insight={selectedInsight}
          isLoadingInsight={Boolean(selectedCandidate && insightLoadingId === selectedCandidate.id)}
          saved={Boolean(selectedCandidate && isSavedCandidate(selectedCandidate))}
          relatedTasks={selectedRelatedTasks}
          chatMessages={selectedChatMessages}
          chatDraft={selectedChatDraft}
          isChatting={Boolean(selectedCandidate && chatLoadingCandidateId === selectedCandidate.id)}
          onToggleSaved={() => {
            if (!selectedCandidate) return;
            handleToggleSaved(selectedCandidate);
          }}
          onAskDiscussionPrompt={(question) => {
            if (!selectedCandidate) return;
            void handleAskCandidateQuestion(selectedCandidate, question);
          }}
          onChatDraftChange={(value) => {
            if (!selectedCandidate) return;
            setCandidateChatDraft(selectedCandidate.id, value);
          }}
          onSendChat={() => {
            if (!selectedCandidate) return;
            void handleAskCandidateQuestion(selectedCandidate);
          }}
          onOpenTask={() => {
            if (!selectedCandidate) return;
            void openTaskModal(selectedCandidate);
          }}
          onOpenSource={() => {
            if (!selectedCandidate?.sourceUrl) return;
            window.open(selectedCandidate.sourceUrl, '_blank', 'noopener,noreferrer');
          }}
        />
      </div>

      {editingPrefIndex !== null && tempPref && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[620px] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
            <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
              <button type="button" onClick={() => { setEditingPrefIndex(null); setTempPref(null); setPreferredSourceDraft(''); }} className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700" aria-label="关闭深度追踪雷达弹窗">
                <X size={18} />
              </button>
              <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                  <Target size={16} strokeWidth={2.5} />
                </div>
                配置深度追踪雷达
              </h3>
            </div>

            <div className="p-8 space-y-6">
              <div>
                <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5 flex justify-between items-end">
                  想持续追踪什么
                  <button
                    type="button"
                    onClick={() => void handleAssistRadarDraft()}
                    disabled={isAssistingRadar || !tempPref.prompt.trim()}
                    className="text-[11px] font-semibold text-indigo-500 flex items-center gap-1 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100 hover:bg-indigo-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isAssistingRadar ? <RefreshCw size={10} className="animate-spin" /> : <Sparkles size={10} />}
                    {isAssistingRadar ? 'AI 补强中…' : '扩写指令 + 提炼标题'}
                  </button>
                </label>
                <textarea
                  value={tempPref.prompt}
                  onChange={(event) => setTempPref({ ...tempPref, prompt: event.target.value })}
                  placeholder="例如：公益咨询团队如何做产品验收；大模型在公益组织中的落地案例；筹资团队分层运营的最新打法。"
                  className="w-full bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[14px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE] min-h-[120px] resize-none"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[1.2fr_0.8fr] gap-6">
                <div>
                  <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">雷达标签名</label>
                  <input
                    type="text"
                    value={tempPref.title}
                    onChange={(event) => setTempPref({ ...tempPref, title: event.target.value })}
                    placeholder="可手动填写，或使用上方 AI 一键补强"
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none focus:bg-white focus:border-[#5B7BFE]"
                  />
                </div>

                <div>
                  <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">时间范围</label>
                  <select
                    value={tempPref.timeRange}
                    onChange={(event) => setTempPref({ ...tempPref, timeRange: event.target.value })}
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE]"
                  >
                    <option value="3_days">近 3 天</option>
                    <option value="7_days">近 7 天</option>
                    <option value="30_days">近 30 天</option>
                  </select>
                </div>
              </div>

              <div className="rounded-[24px] border border-gray-100 bg-gray-50/60 p-5">
                <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">优先检索网址</label>
                <p className="text-[12px] text-gray-500 leading-6">
                  大周会优先结合这些站点做检索。输入网址后，会自动生成一个简短标签。
                </p>
                <div className="mt-4 flex gap-2">
                  <input
                    type="text"
                    value={preferredSourceDraft}
                    onChange={(event) => setPreferredSourceDraft(event.target.value)}
                    placeholder="例如：https://www.chinadevelopmentbrief.org.cn 或机构公告页网址"
                    className="flex-1 bg-white border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE]"
                  />
                  <button
                    type="button"
                    onClick={() => void handleAddPreferredSource()}
                    disabled={isGeneratingSourceLabel || !preferredSourceDraft.trim()}
                    className="px-4 py-3 rounded-2xl text-[12px] font-semibold bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2 shrink-0"
                  >
                    {isGeneratingSourceLabel ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    {isGeneratingSourceLabel ? '生成中…' : 'AI 生成标签'}
                  </button>
                </div>
                {tempPref.preferredSources.length > 0 ? (
                  <div className="mt-4 space-y-2">
                    {tempPref.preferredSources.map((item) => (
                      <div key={item.url} className="rounded-2xl border border-indigo-100 bg-white px-4 py-3 flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-700">
                            {item.label}
                          </div>
                          <p className="text-[12px] text-gray-500 mt-2 break-all">{item.url}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemovePreferredSource(item.url)}
                          className="text-[12px] font-semibold text-gray-400 hover:text-rose-500 transition-colors shrink-0"
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12px] text-gray-400 mt-4">还没有优先网址。默认会先做全网检索。</p>
                )}
              </div>
            </div>

            <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
              <button type="button" onClick={() => { setEditingPrefIndex(null); setTempPref(null); setPreferredSourceDraft(''); }} className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors">
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSavePrefEdit()}
                className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] transition-all inline-flex items-center gap-2"
              >
                保存配置
              </button>
            </div>
          </div>
        </div>
      )}

      {taskModalCandidate && taskDraft && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[760px] max-h-[88vh] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
            <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
              <button
                type="button"
                onClick={() => { if (!isSubmittingTask) { setTaskModalCandidateId(null); setTaskDraft(null); setTaskAssignees([]); } }}
                className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="关闭同步到任务弹窗"
                disabled={isSubmittingTask}
              >
                <X size={18} />
              </button>
              <div>
                <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                    <CheckSquare size={16} strokeWidth={2.5} />
                  </div>
                  同步到任务
                </h3>
                <p className="text-[12px] text-gray-500 mt-1">这里只创建一条任务，并把当前情报的摘要、观点、原文链接写进任务备注。</p>
              </div>
            </div>

            <div className="p-8 space-y-5 overflow-y-auto max-h-[calc(88vh-150px)]">
              <div className="rounded-[24px] border border-blue-100 bg-blue-50/50 px-5 py-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#5B7BFE]">当前情报</p>
                <h4 className="text-[16px] font-bold text-gray-900 mt-2">{taskModalCandidate.title}</h4>
                <p className="text-[12px] text-gray-600 mt-2 leading-6">{taskModalCandidate.summary}</p>
              </div>

              {isPreparingTaskModal ? (
                <div className="rounded-[24px] border border-gray-100 bg-gray-50 px-5 py-10 text-center text-gray-500 flex flex-col items-center gap-3">
                  <RefreshCw size={20} className="animate-spin text-[#5B7BFE]" />
                  <p className="text-[13px] font-medium">正在准备任务表单与情报附件…</p>
                </div>
              ) : (
                <>
                  <div className="space-y-3">
                    <input
                      value={taskDraft.title}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                      placeholder="任务标题"
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />
                    <textarea
                      value={taskDraft.desc}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, desc: event.target.value } : prev))}
                      placeholder="任务说明"
                      className="w-full min-h-[96px] bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] leading-6 font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <select
                      value={taskDraft.ownerId}
                      onChange={(event) => {
                        const owner = taskOwnerOptions.find((item) => item.id === event.target.value);
                        setTaskDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                ownerId: event.target.value,
                                ownerName: owner?.fullName || prev.ownerName,
                              }
                            : prev,
                        );
                      }}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      <option value="">请选择负责人</option>
                      {taskOwnerOptions.map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>
                          {candidate.fullName}{candidate.isSelf ? '（自己）' : ''}
                        </option>
                      ))}
                    </select>

                    <select
                      value={taskDraft.listId}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, listId: event.target.value } : prev))}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      {activeTaskLists.map((list) => (
                        <option key={list.id} value={list.id}>
                          {list.name}
                        </option>
                      ))}
                    </select>

                    <input
                      type="date"
                      value={taskDraft.dueDate}
                      onChange={(event) =>
                        setTaskDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                dueDate: event.target.value,
                                ddl: event.target.value || prev.ddl,
                              }
                            : prev,
                        )
                      }
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />

                    <select
                      value={taskDraft.priority}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, priority: event.target.value as TopicQuickTaskDraft['priority'] } : prev))}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      <option value="low">低优先级</option>
                      <option value="normal">普通优先级</option>
                      <option value="high">高优先级</option>
                    </select>
                  </div>

                  <input
                    value={taskDraft.ddl}
                    onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, ddl: event.target.value } : prev))}
                    placeholder="时间描述，例如 本周内 / 3 月 18 日前 / 待确认"
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                  />

                  <textarea
                    value={taskDraft.note}
                    onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, note: event.target.value } : prev))}
                    placeholder="给同事的补充说明。系统会自动把情报摘要、核心观点和原文链接附在任务备注里。"
                    className="w-full min-h-[120px] bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] leading-6 font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                  />
                </>
              )}
            </div>

            <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  if (isSubmittingTask) return;
                  setTaskModalCandidateId(null);
                  setTaskDraft(null);
                  setTaskAssignees([]);
                }}
                className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSubmitTask()}
                disabled={isPreparingTaskModal || isSubmittingTask}
                className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] disabled:opacity-60 disabled:cursor-not-allowed transition-all inline-flex items-center gap-2"
              >
                {isSubmittingTask ? <RefreshCw size={14} className="animate-spin" /> : <CheckSquare size={14} />}
                {isSubmittingTask ? '同步中…' : '确认同步到任务'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
~~~

## `src/renderer/lib/api.ts`

- 编码: `utf-8`

~~~typescript
import type {
  AnalysisJob,
  AnalysisBackfillMainChainPayload,
  AnalysisBackfillMainChainResult,
  AnalysisJobCreatePayload,
  AnalysisJobStageRun,
  AnalysisRunPayload,
  AgentWeeklyPlan,
  AgentWeeklyPlanPayload,
  AgentWorklogResponse,
  AnalysisRun,
  AnalysisWorkbenchSettings,
  AnalysisWorkbenchSettingsPayload,
  AnalysisTemplate,
  AppSettings,
  AdminResetPasswordPayload,
  AuthLoginPayload,
  AuthRegisterPayload,
  ChangePasswordPayload,
  ConsultationKnowledgeProcessSummary,
  ConsultationKnowledgeRequestRecord,
  ConsultationKnowledgeRequestStatus,
  BadgeBoard,
  AuthState,
  ChatMessage,
  ChatStartResponse,
  ChatThreadDetailResponse,
  ClientDnaModule,
  ClientDnaModulesResponse,
  ClientAnalysisRun,
  ClientTemplateFillResponse,
  ClientTemplateFillRun,
  ClientMutationPayload,
  ClientStrategicProfile,
  ClientSummary,
  ClientWorkspace,
  CooperationRelationship,
  WorkspaceImportBackfillResponse,
  AnalysisMigrationMetrics,
  MainChainStabilitySettings,
  MainChainStabilitySettingsPayload,
  ApprovalDecisionPayload,
  ApprovalRecord,
  ClientWorkspaceSettings,
  ClientWorkspaceSettingsPayload,
  DepartmentOption,
  DeepDnaDraft,
  DeepDnaRecord,
  DnaDelta,
  DnaDeltaCreatePayload,
  DnaTerm,
  DemoDataReport,
  EmployeeRecord,
  EmployeeRejectPayload,
  EmployeeDepartmentPayload,
  FeishuBotSettings,
  FeishuMeetingLaunchResult,
  FeishuBotSettingsPayload,
  FeishuDeliveryProfile,
  FeishuDeliveryProfilePayload,
  FeishuMemberAuthorizationRecord,
  FeishuMemberAuthorizationStartResponse,
  FeishuUserBinding,
  FeishuUserBindingStartResult,
  EmployeeRolePayload,
  EventLine,
  EventLineClarificationDraftPayload,
  EventLineClarificationDraftResult,
  EventLineDetail,
  EventLineMutationPayload,
  GoalRecord,
  GrowthLedgerResponse,
  GrowthOverview,
  GrowthPendingCaptureActionPayload,
  GrowthPendingCaptureActionResponse,
  GrowthRecommendationActionResponse,
  GrowthRecommendationDismissPayload,
  GrowthWorkbenchSnapshot,
  GrowthValidationActionResponse,
  GrowthValidationPayload,
  HandbookEntry,
  HandbookEntryDetail,
  HandbookEntryPayload,
  HealthResponse,
  ImportRecord,
  KnowledgeJob,
  KnowledgeMemoryRecord,
  KnowledgeSearchResult,
  KnowledgeStatus,
  LegacyScanReport,
  MentionCandidate,
  OrganizationDnaModule,
  OrgModelSettings,
  OrganizationDnaResponse,
  OrganizationDnaUploadPayload,
  MeetingPipelineResult,
  Operator,
  ProjectFlow,
  ProjectFlowDetail,
  ProjectFlowPayload,
  ProjectModule,
  ProjectModuleDetail,
  ProjectModulePayload,
  ProjectStructureResponse,
  PrepPackCard,
  ProposalExecutionResponse,
  ProposalRecord,
  SettingsPayload,
  SystemAdminSettings,
  SystemAdminSettingsPayload,
  TaskOrgBackfillResult,
  Task,
  TaskActivityRecord,
  TaskContextPreview,
  TaskSmartBrief,
  TaskTag,
  TaskTagMutationPayload,
  TaskTagSuggestionPayload,
  TaskMutationPayload,
  TaskListMutationPayload,
  TaskList,
  TaskSettings,
  TaskSettingsPayload,
  TopicsSettings,
  TopicsSettingsPayload,
  UpdateProfilePayload,
  HandbookSettings,
  HandbookSettingsPayload,
  CoachCaseRecord,
  CoachReminderRule,
  TopicCaptureBatchResult,
  TopicCandidate,
  TopicCandidateChatPayload,
  TopicCandidateChatResponse,
  TopicCandidateInsight,
  TopicCandidatePayload,
  TopicTaskPlanResult,
  TopicTaskPromotionDraft,
  TopicTaskPromotionResult,
  TopicRadar,
  TopicRadarPayload,
  ReviewDashboard,
  ReviewHistoryResponse,
  ReviewGovernanceSettings,
  ReviewGovernanceSettingsPayload,
  RedeemOrgInvitationPayload,
  JudgmentConfirmPayload,
  JudgmentVersion,
  ConflictGroup,
  OpenQuestion,
  OrgWritingNorm,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
  RunComparison,
  RuntimeRunLog,
  SupportRequestCreatePayload,
  SupportRequestResolvePayload,
  SupportRequestRecord,
  StrategicCockpitConfirmPayload,
  StrategicCockpitSnapshot,
  StrategicThought,
  StrategicThoughtReview,
  StrategicThoughtReviewPayload,
  StrategicThoughtsResponse,
  StrategicLineDetail,
  ThemeCluster,
  TaskViewDefinition,
  TaskViewMutationPayload,
  TaskViewsResponse,
  WeeklyReviewPayload,
  LearningRecommendation,
  LocalInputMemory,
  ReviewDashboardDrillTargetResponse,
  SaveAiInputMemoryPayload,
  SaveCloudAuthInputMemoryPayload,
  SaveFeishuInputMemoryPayload,
  CollabActionResult,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
  EventLineReportSnapshot,
} from '../../shared/types';

export type {
  StrategicThought,
  StrategicThoughtReview,
  StrategicThoughtReviewPayload,
  StrategicThoughtsResponse,
} from '../../shared/types';

function createBrowserWorkbenchFallback(): Window['yiyuWorkbench'] {
  const backendBaseUrl = 'http://127.0.0.1:47829';
  const notAvailable = async (action: string) => {
    throw new Error(`${action} 仅在桌面版可用，请在 Electron 应用中打开。`);
  };

  return {
    backendBaseUrl,
    getDesktopAppInfo: async () => ({
      appVersion: 'browser-preview',
      isPackaged: false,
      platform: 'browser',
      arch: 'browser',
      appBundlePath: '',
      executablePath: '',
      releasePlanPath: '',
      releaseArtifactsPath: '',
      updateChannel: 'beta',
      updaterPhase: 'planning',
      recommendedInstallPath: '',
      installStatus: 'warning',
      installWarning: '当前为浏览器预览模式，文件选择、协作同步和本地安装能力不可用。',
      detectedAppPaths: [],
      legacyAppPaths: [],
    }),
    selectFiles: async () => [],
    selectFolder: async () => null,
    selectCollabRepo: async () => null,
    getCollabRepoStatus: async () => ({
      repoPath: null,
      repoName: null,
      suggestedRepoPath: null,
      isConfigured: false,
      isValid: false,
      branch: null,
      isMainBranch: false,
      hasLocalChanges: false,
      hasUnmergedPaths: false,
      aheadCount: 0,
      behindCount: 0,
      localChangeCount: 0,
      remoteChangeCount: 0,
      statusText: '当前为浏览器预览模式，Git 协作能力不可用。',
    }),
    previewPushToMain: async () => notAvailable('推送到 main'),
    commitAndPushToMain: async () => notAvailable('推送到 main'),
    previewPullFromMain: async () => notAvailable('从 main 拉取'),
    pullSelectedFromMain: async () => notAvailable('从 main 拉取'),
    rebuildAndInstallFromRepo: async () => notAvailable('重装应用'),
    getDroppedFilePath: () => null,
    readTextFile: async () => notAvailable('读取本地文件'),
    openPath: async () => notAvailable('打开本地路径'),
    openExternalUrl: async (targetUrl: string) => {
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
      return true;
    },
    revealInFinder: async () => notAvailable('在 Finder 中显示'),
    saveFileAs: async () => notAvailable('另存为'),
  };
}

if (typeof window !== 'undefined' && !window.yiyuWorkbench) {
  window.yiyuWorkbench = createBrowserWorkbenchFallback();
}

const baseUrl = window.yiyuWorkbench.backendBaseUrl;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase();
  const maxRetry = method === 'GET' ? 12 : 0;
  let response: Response | null = null;
  let lastError: unknown = null;
  for (let attempt = 0; attempt <= maxRetry; attempt += 1) {
    try {
      response = await fetch(`${baseUrl}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(options?.headers ?? {}),
        },
        ...options,
      });
      break;
    } catch (error) {
      lastError = error;
      const detail = error instanceof Error ? error.message : String(error);
      const isTransient = /Failed to fetch/i.test(detail) || /Load failed/i.test(detail);
      if (!isTransient || attempt === maxRetry) {
        if (isTransient) {
          throw new Error('无法连接本地服务，请等待应用完成启动，或重启软件后重试。');
        }
        throw new Error(detail || '请求失败');
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  if (!response) {
    const detail = lastError instanceof Error ? lastError.message : String(lastError ?? '');
    throw new Error(detail || '请求失败');
  }
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail || text;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

type FormRequestOptions = Omit<RequestInit, 'body'> & {
  onProgress?: (loaded: number, total: number) => void;
};

async function requestForm<T>(path: string, formData: FormData, options?: FormRequestOptions): Promise<T> {
  const onProgress = options?.onProgress;
  if (onProgress) {
    return new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open((options?.method || 'POST').toUpperCase(), `${baseUrl}${path}`);
      const headers = new Headers(options?.headers || {});
      headers.forEach((value, key) => {
        xhr.setRequestHeader(key, value);
      });
      xhr.upload.onprogress = (event) => {
        onProgress(event.loaded, event.lengthComputable ? event.total : 0);
      };
      xhr.onerror = () => {
        reject(new Error('附件上传失败，请稍后重试。'));
      };
      xhr.onload = () => {
        const text = xhr.responseText || '';
        if (xhr.status < 200 || xhr.status >= 300) {
          let detail = text;
          try {
            const payload = JSON.parse(text) as { detail?: string };
            detail = payload.detail || text;
          } catch {}
          reject(new Error(detail || `HTTP ${xhr.status}`));
          return;
        }
        try {
          resolve(JSON.parse(text) as T);
        } catch (error) {
          reject(error instanceof Error ? error : new Error('附件上传响应解析失败'));
        }
      };
      xhr.send(formData);
    });
  }
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const payload = JSON.parse(text) as { detail?: string };
      detail = payload.detail || text;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth() {
  return request<HealthResponse>('/api/v1/system/health');
}

export type BrainPulse = {
  memoryCount: number;
  docCount: number;
  taskCount: number;
  chatCount: number;
  eventLineCount: number;
  dnaCount: number;
  badgeCount: number;
  handbookCount: number;
  daysAccompanied: number;
  reviewCount: number;
  meetingCount: number;
  weeklyNewFacts: number;
};

export type BrainClientData = {
  id: string;
  name: string;
  confidence: number;
  stage: string;
  intro?: string | null;
  docs: number;
  dna: number;
  eventLines: number;
  memoryFacts: number;
};

export type BrainDashboard = {
  pulse: BrainPulse;
  clients: BrainClientData[];
};

export async function getBrainDashboard() {
  return request<BrainDashboard>('/api/v1/brain/dashboard');
}

export async function getTaskContextPreview(taskId: string) {
  return request<TaskContextPreview>(`/api/v1/tasks/${taskId}/context-preview`);
}

export type TaskUnderstandingSnapshot = {
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  confidence: number;
  sourceBreakdown: Array<{ sourceName: string; available: boolean; snippet: string }>;
  coverage: number;
  optionalAdvice?: {
    realBlocker?: string;
    timeGate?: string;
    minimumAction?: string;
    supportAsk?: string;
  } | null;
};

export async function getTaskUnderstanding(taskId: string) {
  return request<TaskUnderstandingSnapshot>(`/api/v1/tasks/${taskId}/understanding`);
}

export async function getTaskSmartBrief(taskId: string) {
  return request<TaskSmartBrief>(`/api/v1/tasks/${taskId}/smart-brief`);
}

export async function getTaskPrepPack(taskId: string) {
  return request<PrepPackCard>(`/api/v1/tasks/${taskId}/prep-pack`);
}

export async function createTaskPrepProposal(taskId: string) {
  return request<ProposalRecord>(`/api/v1/tasks/${taskId}/prep-pack/proposals`, {
    method: 'POST',
  });
}

export async function getTaskSmartBriefsBatch(taskHints: Array<{ id: string; title: string; desc?: string; clientId?: string | null; eventLineId?: string | null; attachmentTitles?: string[] }>) {
  return request<TaskSmartBrief[]>('/api/v1/tasks/smart-briefs', {
    method: 'POST',
    body: JSON.stringify({ tasks: taskHints }),
  });
}

export async function adoptTaskSmartBriefAction(taskId: string, actionKey: string, payload: { createdTaskId: string; actionText?: string }) {
  return request<{ ok: boolean; taskId: string; actionKey: string; createdTaskId: string }>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/smart-brief-actions/${encodeURIComponent(actionKey)}/adopt`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export async function getAuthState() {
  return request<AuthState>('/api/v1/auth/me');
}

export async function register(payload: AuthRegisterPayload) {
  return request<AuthState>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getDepartmentOptions() {
  return request<DepartmentOption[]>('/api/v1/auth/department-options');
}

export async function login(payload: AuthLoginPayload) {
  return request<AuthState>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function processPendingConsultationKnowledgeRequests() {
  return request<ConsultationKnowledgeProcessSummary>('/api/v1/consultation/knowledge-requests/process-pending', {
    method: 'POST',
  });
}

export async function logout() {
  return request<AuthState>('/api/v1/auth/logout', { method: 'POST' });
}

export async function changePassword(payload: ChangePasswordPayload) {
  return request<{ message: string }>('/api/v1/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProfile(payload: UpdateProfilePayload) {
  return request<AuthState>('/api/v1/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getLocalInputMemory() {
  return request<LocalInputMemory>('/api/v1/local-input-memory');
}

export async function saveCloudAuthInputMemory(payload: SaveCloudAuthInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/cloud-auth', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function saveAiInputMemory(payload: SaveAiInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/ai', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function saveFeishuInputMemory(payload: SaveFeishuInputMemoryPayload) {
  return request<LocalInputMemory>('/api/v1/local-input-memory/feishu', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function adminResetPassword(employeeId: string, payload: AdminResetPasswordPayload) {
  return request<{ message: string }>(`/api/v1/admin/employees/${encodeURIComponent(employeeId)}/reset-password`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSettings() {
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings');
}

export async function updateSettings(payload: SettingsPayload) {
  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTaskSettings() {
  return request<TaskSettings>('/api/v1/settings/tasks');
}

export async function updateTaskSettings(payload: TaskSettingsPayload) {
  return request<TaskSettings>('/api/v1/settings/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getReviewGovernanceSettings() {
  return request<ReviewGovernanceSettings>('/api/v1/settings/review-governance');
}

export async function updateReviewGovernanceSettings(payload: ReviewGovernanceSettingsPayload) {
  return request<ReviewGovernanceSettings>('/api/v1/settings/review-governance', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getOrgModelProfile() {
  return request<OrgModelSettings>('/api/v1/settings/org-model/profile');
}

export async function updateOrgModelProfile(payload: OrgModelSettings) {
  return request<OrgModelSettings>('/api/v1/settings/org-model/profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function backfillOrgTaskLinks() {
  return request<TaskOrgBackfillResult>('/api/v1/settings/org-model/backfill-task-links', {
    method: 'POST',
  });
}

export async function getOrganizationDna() {
  return request<OrganizationDnaResponse>('/api/v1/settings/org-dna');
}

export async function updateOrganizationDnaModule(moduleKey: OrganizationDnaModule['moduleKey'], payload: OrganizationDnaUploadPayload) {
  return request<OrganizationDnaModule>(`/api/v1/settings/org-dna/${moduleKey}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientWorkspaceSettings() {
  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace');
}

export async function updateClientWorkspaceSettings(payload: ClientWorkspaceSettingsPayload) {
  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTopicsSettings() {
  return request<TopicsSettings>('/api/v1/settings/topics');
}

export async function updateTopicsSettings(payload: TopicsSettingsPayload) {
  return request<TopicsSettings>('/api/v1/settings/topics', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisWorkbenchSettings() {
  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench');
}

export async function updateAnalysisWorkbenchSettings(payload: AnalysisWorkbenchSettingsPayload) {
  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getHandbookSettings() {
  return request<HandbookSettings>('/api/v1/settings/handbook');
}

export async function updateHandbookSettings(payload: HandbookSettingsPayload) {
  return request<HandbookSettings>('/api/v1/settings/handbook', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSystemAdminSettings() {
  return request<SystemAdminSettings>('/api/v1/settings/system-admin');
}

export async function updateSystemAdminSettings(payload: SystemAdminSettingsPayload) {
  return request<SystemAdminSettings>('/api/v1/settings/system-admin', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getMainChainStabilitySettings() {
  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability');
}

export async function updateMainChainStabilitySettings(payload: MainChainStabilitySettingsPayload) {
  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuBotSettings() {
  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot');
}

export async function updateFeishuBotSettings(payload: FeishuBotSettingsPayload) {
  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuUserBinding() {
  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding');
}

export async function startFeishuUserBinding() {
  return request<FeishuUserBindingStartResult>('/api/v1/settings/feishu-user-binding/start', {
    method: 'POST',
  });
}

export async function clearFeishuUserBinding() {
  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding', {
    method: 'DELETE',
  });
}

export async function getOrgMembershipSummary() {
  return request<OrgMembershipSummary>('/api/v1/me/org-membership');
}

export async function getFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorizationRecord>('/api/v1/me/feishu-authorization');
}

export async function startFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorizationStartResponse>('/api/v1/me/feishu-authorization/start', {
    method: 'POST',
  });
}

export async function clearFeishuMemberAuthorization() {
  return request<FeishuMemberAuthorizationRecord>('/api/v1/me/feishu-authorization', {
    method: 'DELETE',
  });
}

export async function getOrgFeishuIntegration() {
  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu');
}

export async function saveOrgFeishuIntegration(payload: OrgFeishuIntegrationPayload) {
  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu/validate-and-save', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFeishuDeliveryProfile() {
  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile');
}

export async function saveFeishuDeliveryProfile(payload: FeishuDeliveryProfilePayload) {
  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createBackup() {
  return request<{ backupPath: string; createdAt: string }>('/api/v1/settings/backup', { method: 'POST' });
}

export async function scanLegacy(path: string) {
  return request<LegacyScanReport>('/api/v1/settings/legacy-scan', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function loadDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/load', { method: 'POST' });
}

export async function clearDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/clear', { method: 'POST' });
}

export async function getActivityLogs() {
  return request<
    Array<{
      id: string;
      actorName: string;
      action: string;
      entityType: string;
      entityId: string;
      detail: Record<string, unknown>;
      createdAt: string;
    }>
  >('/api/v1/settings/logs');
}

// ── System Logs ───────────────────────────────────────────────
export type SystemLogEntry = {
  ts: string;
  level: string;
  source: string;
  message: string;
  method?: string;
  path?: string;
  status?: number;
  duration_ms?: number;
  user?: string;
  error?: string;
  traceback?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  actor?: string;
  detail?: Record<string, unknown>;
};

export type SystemLogsResponse = {
  entries: SystemLogEntry[];
  dates: string[];
  total: number;
};

export async function getSystemLogs(params?: {
  startDate?: string;
  endDate?: string;
  level?: string;
  source?: string;
  keyword?: string;
  limit?: number;
}) {
  const search = new URLSearchParams();
  if (params?.startDate) search.set('startDate', params.startDate);
  if (params?.endDate) search.set('endDate', params.endDate);
  if (params?.level) search.set('level', params.level);
  if (params?.source) search.set('source', params.source);
  if (params?.keyword) search.set('keyword', params.keyword);
  if (params?.limit) search.set('limit', String(params.limit));
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<SystemLogsResponse>(`/api/v1/logs${suffix}`);
}

export async function exportSystemLogs(params?: {
  startDate?: string;
  endDate?: string;
  level?: string;
  keyword?: string;
}) {
  const search = new URLSearchParams();
  if (params?.startDate) search.set('startDate', params.startDate);
  if (params?.endDate) search.set('endDate', params.endDate);
  if (params?.level) search.set('level', params.level);
  if (params?.keyword) search.set('keyword', params.keyword);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  const res = await fetch(`${baseUrl}/api/v1/logs/export${suffix}`);
  return res.text();
}

export async function getLogDates() {
  return request<string[]>('/api/v1/logs/dates');
}

export async function getEmployees() {
  return request<EmployeeRecord[]>('/api/v1/admin/employees');
}

export async function approveEmployee(id: string, payload: EmployeeRolePayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function rejectEmployeeReview(id: string, payload: EmployeeRejectPayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function disableEmployee(id: string) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/disable`, {
    method: 'POST',
  });
}

export async function updateEmployeeRole(id: string, payload: EmployeeRolePayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/role`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function updateEmployeeDepartment(id: string, payload: EmployeeDepartmentPayload) {
  return request<EmployeeRecord>(`/api/v1/admin/employees/${id}/department`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getMentionCandidates(query = '') {
  return request<MentionCandidate[]>(`/api/v1/employees/mention-candidates?q=${encodeURIComponent(query)}`);
}

export async function getClients() {
  return request<ClientSummary[]>('/api/v1/clients');
}

export async function createClient(payload: ClientMutationPayload) {
  return request<ClientSummary>('/api/v1/clients', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateClient(id: string, payload: ClientMutationPayload) {
  return request<ClientSummary>(`/api/v1/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteClient(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/clients/${id}`, {
    method: 'DELETE',
  });
}

export async function deleteClientFolder(clientId: string, folderId: string) {
  return request<{ deleted: boolean }>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'DELETE',
  });
}

export async function getClientWorkspace(id: string) {
  return request<ClientWorkspace>(`/api/v1/clients/${id}/workspace`);
}

export async function createAnalysisJob(payload: AnalysisJobCreatePayload) {
  return request<AnalysisJob>('/api/v1/analysis/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function backfillAnalysisMainChain(payload: AnalysisBackfillMainChainPayload) {
  return request<AnalysisBackfillMainChainResult>('/api/v1/analysis/backfill-main-chain', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisJob(jobId: string) {
  return request<AnalysisJob>(`/api/v1/analysis/jobs/${jobId}`);
}

export async function getAnalysisJobStages(jobId: string) {
  return request<AnalysisJobStageRun[]>(`/api/v1/analysis/jobs/${jobId}/stages`);
}

export async function getRuntimeRunLog(runId: string) {
  return request<RuntimeRunLog>(`/api/v1/runtime/run-log/${runId}`);
}

export async function createDnaDelta(payload: DnaDeltaCreatePayload) {
  return request<DnaDelta>('/api/v1/memory/dna/delta', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function confirmJudgment(payload: JudgmentConfirmPayload) {
  return request<JudgmentVersion>('/api/v1/memory/judgments/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function decideApproval(payload: ApprovalDecisionPayload) {
  return request<ApprovalRecord>('/api/v1/approvals/decide', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientJudgments(clientId: string) {
  return request<JudgmentVersion[]>(`/api/v1/clients/${clientId}/judgments`);
}

export async function getClientTopics(clientId: string) {
  return request<ThemeCluster[]>(`/api/v1/clients/${clientId}/topics`);
}

export async function getClientConflicts(clientId: string) {
  return request<ConflictGroup[]>(`/api/v1/clients/${clientId}/conflicts`);
}

export async function getClientOpenQuestions(clientId: string) {
  return request<OpenQuestion[]>(`/api/v1/clients/${clientId}/open-questions`);
}

export async function getClientRuntimeRunLogs(clientId: string) {
  return request<RuntimeRunLog[]>(`/api/v1/clients/${clientId}/runtime-run-logs`);
}

export async function getAnalysisMigrationMetrics() {
  return request<AnalysisMigrationMetrics>('/api/v1/runtime/analysis-migration-metrics');
}

export async function getClientDnaDocuments(clientId: string) {
  return request<ClientDnaModulesResponse>(`/api/v1/clients/${clientId}/dna-documents`);
}

export async function getClientDnaDocument(clientId: string, moduleKey: ClientDnaModule['moduleKey']) {
  return request<ClientDnaModule>(`/api/v1/clients/${clientId}/dna-documents/${moduleKey}`);
}

export async function updateClientDnaDocument(
  clientId: string,
  moduleKey: ClientDnaModule['moduleKey'],
  payload: OrganizationDnaUploadPayload,
) {
  return request<ClientDnaModule>(`/api/v1/clients/${clientId}/dna-documents/${moduleKey}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getClientProjectStructure(clientId: string) {
  return request<ProjectStructureResponse>(`/api/v1/clients/${clientId}/project-structure`);
}

export async function getProjectModuleDetail(clientId: string, moduleId: string) {
  return request<ProjectModuleDetail>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`);
}

export async function createProjectModule(clientId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(`/api/v1/clients/${clientId}/project-modules`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectModule(clientId: string, moduleId: string, payload: ProjectModulePayload) {
  return request<ProjectModule>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectModule(clientId: string, moduleId: string) {
  return request<{ status: string }>(`/api/v1/clients/${clientId}/project-modules/${moduleId}`, {
    method: 'DELETE',
  });
}

export async function getProjectFlowDetail(clientId: string, flowId: string) {
  return request<ProjectFlowDetail>(`/api/v1/clients/${clientId}/project-flows/${flowId}`);
}

export async function createProjectFlow(clientId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectFlow(clientId: string, flowId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows/${flowId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getClientKnowledgeStatus(clientId: string) {
  return request<KnowledgeStatus>(`/api/v1/clients/${clientId}/knowledge/status`);
}

export async function searchClientKnowledge(clientId: string, prompt: string, threadId?: string) {
  return request<KnowledgeSearchResult>(`/api/v1/clients/${clientId}/knowledge/search`, {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId }),
  });
}

export async function rebuildClientKnowledge(clientId: string) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/knowledge/rebuild`, {
    method: 'POST',
  });
}

export async function generateClientDnaCandidates(clientId: string, payload?: { refreshGenerated?: boolean }) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/dna-documents/generate`, {
    method: 'POST',
    body: JSON.stringify({ refreshGenerated: payload?.refreshGenerated ?? false }),
  });
}

export async function importPaths(clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) {
  return request<ImportRecord[]>('/api/v1/imports', {
    method: 'POST',
    body: JSON.stringify({ clientId, mode, paths, allowLegacy: options?.allowLegacy ?? false }),
  });
}

export async function startClientMessage(
  clientId: string,
  prompt: string,
  threadId?: string,
  searchId?: string,
  options?: RequestInit,
) {
  return request<ChatStartResponse>(`/api/v1/clients/${clientId}/workspace/chat/start`, {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId, searchId }),
    ...options,
  });
}

export async function getClientMessage(clientId: string, messageId: string) {
  return request<ChatMessage>(`/api/v1/clients/${clientId}/workspace/chat/messages/${messageId}`);
}

export async function getClientChatThread(clientId: string, threadId: string) {
  return request<ChatThreadDetailResponse>(`/api/v1/clients/${clientId}/workspace/chat/threads/${threadId}`);
}

export async function getClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(`/api/v1/clients/${clientId}/analysis-runs/${runId}`);
}

export async function cancelClientAnalysisRun(clientId: string, runId: string) {
  return request<ClientAnalysisRun>(`/api/v1/clients/${clientId}/analysis-runs/${runId}/cancel`, {
    method: 'POST',
  });
}

export async function vectorizeAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/knowledge/vectorize-answer`, {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function exportAnswer(clientId: string, messageId: string) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/knowledge/export-answer`, {
    method: 'POST',
    body: JSON.stringify({ messageId }),
  });
}

export async function createClientTextDocument(clientId: string, payload: { title?: string | null; content: string }) {
  return request<{ clientId: string; documentId: string; title: string; fileName: string; path: string }>(`/api/v1/clients/${clientId}/documents/from-text`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function startClientTemplateFill(clientId: string, templatePath: string) {
  return request<ClientTemplateFillRun>(`/api/v1/clients/${clientId}/documents/fill-template/start`, {
    method: 'POST',
    body: JSON.stringify({ templatePath }),
  });
}

export async function getClientTemplateFillRun(clientId: string, runId: string) {
  return request<ClientTemplateFillRun>(`/api/v1/clients/${clientId}/template-fill-runs/${runId}`);
}

export async function backfillClientWorkspaceImports(clientId: string) {
  return request<WorkspaceImportBackfillResponse>(`/api/v1/clients/${clientId}/workspace/backfill-imports`, {
    method: 'POST',
  });
}

export async function createMeeting(clientId: string, title: string, scheduledAt?: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings`, {
    method: 'POST',
    body: JSON.stringify({ title, scheduledAt }),
  });
}

export async function getStrategicCockpit(clientId: string) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit`);
}

export async function confirmStrategicCockpit(clientId: string, payload: StrategicCockpitConfirmPayload) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createStrategicMeetingPack(clientId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/strategic-cockpit/meeting-pack`, {
    method: 'POST',
  });
}

export async function applyStrategicMeetingPack(clientId: string, meetingId: string) {
  return request<StrategicCockpitSnapshot>(`/api/v1/clients/${clientId}/strategic-cockpit/meeting-pack/${meetingId}/apply`, {
    method: 'POST',
  });
}

export async function getStrategicThoughts(params?: {
  clientId?: string | null;
  includeDismissed?: boolean;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.clientId) searchParams.set('clientId', params.clientId);
  if (params?.includeDismissed) searchParams.set('includeDismissed', 'true');
  if (typeof params?.limit === 'number') searchParams.set('limit', String(params.limit));
  const query = searchParams.toString();
  return request<StrategicThoughtsResponse>(`/api/v1/strategic/thoughts${query ? `?${query}` : ''}`);
}

export async function reviewStrategicThought(thoughtId: string, payload: StrategicThoughtReviewPayload) {
  return request<StrategicThought | StrategicThoughtReview>(`/api/v1/strategic/thoughts/${encodeURIComponent(thoughtId)}/review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createClientFolder(clientId: string, label: string) {
  return request<{ id: string; label: string; created: boolean }>(`/api/v1/clients/${clientId}/folders`, {
    method: 'POST',
    body: JSON.stringify({ label }),
  });
}

export async function renameClientFolder(clientId: string, folderId: string, label: string) {
  return request<{ id: string; label: string }>(`/api/v1/clients/${clientId}/folders/${folderId}`, {
    method: 'PUT',
    body: JSON.stringify({ label }),
  });
}

export async function launchFeishuMeeting(clientId: string, payload: { title: string; scheduledAt?: string; sourceTaskId?: string | null }) {
  return request<FeishuMeetingLaunchResult>(`/api/v1/clients/${clientId}/meetings/launch-feishu`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function ingestMeeting(clientId: string, meetingId: string, transcriptText: string, notes: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/ingest`, {
    method: 'POST',
    body: JSON.stringify({ transcriptText, notes }),
  });
}

export async function extractMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/extract`, {
    method: 'POST',
  });
}

export async function resolveMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/resolve`, {
    method: 'POST',
  });
}

export async function publishMeeting(clientId: string, meetingId: string) {
  return request<MeetingPipelineResult>(`/api/v1/clients/${clientId}/meetings/${meetingId}/publish`, {
    method: 'POST',
  });
}

export async function createMeetingPrepareProposal(clientId: string, meetingId: string) {
  return request<ProposalRecord>(`/api/v1/clients/${clientId}/meetings/${meetingId}/proposals/prepare`, {
    method: 'POST',
  });
}

export async function createMeetingFollowupProposal(clientId: string, meetingId: string) {
  return request<ProposalRecord>(`/api/v1/clients/${clientId}/meetings/${meetingId}/proposals/follow-up`, {
    method: 'POST',
  });
}

export async function getProposals(options?: { status?: string; clientId?: string }) {
  const params = new URLSearchParams();
  if (options?.status) params.set('status', options.status);
  if (options?.clientId) params.set('clientId', options.clientId);
  const query = params.toString();
  return request<ProposalRecord[]>(`/api/v1/proposals${query ? `?${query}` : ''}`);
}

export async function approveProposal(proposalId: string, comment = '') {
  return request<ProposalRecord>(`/api/v1/proposals/${proposalId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function rejectProposal(proposalId: string, comment = '') {
  return request<ProposalRecord>(`/api/v1/proposals/${proposalId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function executeProposal(proposalId: string, comment = '') {
  return request<ProposalExecutionResponse>(`/api/v1/proposals/${proposalId}/execute`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function createGoal(clientId: string, payload: { title: string; quarter: string; progress: number; ownerName: string }) {
  return request<GoalRecord>(`/api/v1/clients/${clientId}/goals`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function upsertDna(clientId: string, payload: { category: string; canonicalName: string; aliases: string[]; description: string }) {
  return request<DnaTerm>(`/api/v1/clients/${clientId}/dna`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTaskBoard() {
  return request<{ tasks: Task[]; lists: TaskList[]; tags: TaskTag[] }>('/api/v1/tasks');
}

export async function createSupportRequest(payload: SupportRequestCreatePayload) {
  return request<SupportRequestRecord>('/api/v1/support-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSupportRequests(params?: { status?: string; taskId?: string }) {
  const search = new URLSearchParams();
  if (params?.status) search.set('status', params.status);
  if (params?.taskId) search.set('taskId', params.taskId);
  const suffix = search.size > 0 ? `?${search.toString()}` : '';
  return request<SupportRequestRecord[]>(`/api/v1/support-requests${suffix}`);
}

export async function resolveSupportRequest(id: string, payload: SupportRequestResolvePayload) {
  return request<SupportRequestRecord>(`/api/v1/support-requests/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAgentWorklogs(month?: string) {
  const suffix = month ? `?month=${encodeURIComponent(month)}` : '';
  return request<AgentWorklogResponse>(`/api/v1/tasks/agent-worklogs${suffix}`);
}

export async function updateAgentWeeklyPlan(weekLabel: string, agentKey: string, payload: AgentWeeklyPlanPayload) {
  return request<AgentWeeklyPlan>(`/api/v1/tasks/agent-weekly-plans/${encodeURIComponent(weekLabel)}/${encodeURIComponent(agentKey)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getAgentExecutionTasks(weekLabel: string, departmentName?: string) {
  const params = new URLSearchParams({ week: weekLabel });
  if (departmentName?.trim()) {
    params.set('department', departmentName.trim());
  }
  return request<Task[]>(`/api/v1/tasks/agent-execution?${params.toString()}`);
}

export async function createTaskList(payload: TaskListMutationPayload) {
  return request<TaskList>('/api/v1/task-lists', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTaskList(id: string, payload: TaskListMutationPayload) {
  return request<TaskList>(`/api/v1/task-lists/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskList(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/task-lists/${id}`, {
    method: 'DELETE',
  });
}

export async function createTaskTag(payload: TaskTagMutationPayload) {
  return request<TaskTag>('/api/v1/task-tags', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTaskTag(id: string, payload: TaskTagMutationPayload) {
  return request<TaskTag>(`/api/v1/task-tags/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTaskTag(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/task-tags/${id}`, {
    method: 'DELETE',
  });
}

export async function createTask(payload: TaskMutationPayload) {
  return request<Task>('/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTask(id: string, payload: Partial<TaskMutationPayload> & { status?: string }) {
  return request<Task>(`/api/v1/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteTask(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/tasks/${id}`, {
    method: 'DELETE',
  });
}

export async function uploadTaskAttachment(
  taskId: string,
  payload: {
    file: File;
    clientId?: string | null;
    eventLineId?: string | null;
    taskTitle?: string | null;
    onProgress?: (loaded: number, total: number) => void;
  },
) {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.clientId) formData.append('clientId', payload.clientId);
  if (payload.eventLineId) formData.append('eventLineId', payload.eventLineId);
  if (payload.taskTitle) formData.append('taskTitle', payload.taskTitle);
  return requestForm<Task>(`/api/v1/tasks/${taskId}/attachments`, formData, {
    method: 'POST',
    onProgress: payload.onProgress,
  });
}

export async function getEventLines() {
  return request<EventLine[]>('/api/v1/event-lines');
}

export async function createEventLine(payload: EventLineMutationPayload) {
  return request<EventLine>('/api/v1/event-lines', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getEventLine(id: string) {
  return request<EventLineDetail>(`/api/v1/event-lines/${id}`);
}

export async function getEventLineReportSnapshot(id: string) {
  return request<EventLineReportSnapshot>(`/api/v1/event-lines/${id}/report-snapshot`);
}

export async function updateEventLine(id: string, payload: Partial<EventLineMutationPayload>) {
  return request<EventLine>(`/api/v1/event-lines/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function closeEventLine(id: string) {
  return request<{ status: string }>(`/api/v1/event-lines/${id}/close`, {
    method: 'POST',
  });
}

export async function reopenEventLine(id: string) {
  return request<{ status: string }>(`/api/v1/event-lines/${id}/reopen`, {
    method: 'POST',
  });
}

export async function deleteEventLine(id: string) {
  return request<{ status: string; counts?: Record<string, number> }>(`/api/v1/event-lines/${id}`, {
    method: 'DELETE',
  });
}

export async function addEventLineNote(id: string, text: string) {
  return request<{ id: string; eventLineId: string; text: string; createdAt: string }>(`/api/v1/event-lines/${id}/notes`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function generateEventLineClarificationDraft(
  id: string,
  payload: EventLineClarificationDraftPayload,
) {
  return request<EventLineClarificationDraftResult>(`/api/v1/event-lines/${id}/clarification-draft`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function confirmTask(id: string) {
  return request<Task>(`/api/v1/tasks/${id}/confirm`, { method: 'POST' });
}

export async function rejectTask(id: string, reason: string) {
  return request<Task>(`/api/v1/tasks/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function approveTaskReview(id: string) {
  return request<Task>(`/api/v1/tasks/${id}/review/approve`, { method: 'POST' });
}

export async function returnTaskReview(id: string, reason: string) {
  return request<Task>(`/api/v1/tasks/${id}/review/return`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function saveTaskNote(id: string, note: string) {
  return request<Task>(`/api/v1/tasks/${id}/note`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export async function completeTaskWithReview(id: string, reviewNote: string) {
  return request<Task>(`/api/v1/tasks/${id}/complete-with-review`, {
    method: 'POST',
    body: JSON.stringify({ reviewNote }),
  });
}

export async function getTaskViews() {
  return request<TaskViewsResponse>('/api/v1/task-views');
}

export async function getTaskTagSuggestions(payload: TaskTagSuggestionPayload) {
  return request<{ suggestedTags: string[] }>('/api/v1/local/tasks/tag-suggestions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getReviews(weekLabel?: string) {
  const suffix = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : '';
  return request<ReviewDashboard>(`/api/v1/reviews${suffix}`);
}

export async function getReviewDashboardDrillTarget(params: {
  targetType: string;
  targetId: string;
  targetLabel?: string;
  targetFilters?: Record<string, unknown>;
}) {
  const search = new URLSearchParams({
    targetType: params.targetType,
    targetId: params.targetId,
  });
  if (params.targetLabel?.trim()) {
    search.set('targetLabel', params.targetLabel.trim());
  }
  if (params.targetFilters && Object.keys(params.targetFilters).length > 0) {
    search.set('targetFilters', JSON.stringify(params.targetFilters));
  }
  return request<ReviewDashboardDrillTargetResponse>(`/api/v1/reviews/dashboard/drill-target?${search.toString()}`);
}

export async function getReviewHistory() {
  return request<ReviewHistoryResponse>('/api/v1/reviews/history');
}

export async function createWeeklyReview(payload: WeeklyReviewPayload) {
  return request<ReviewDashboard>('/api/v1/reviews/weekly', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createWeeklyReviewDraft(payload: WeeklyReviewPayload) {
  return request<ReviewDashboard>('/api/v1/reviews/weekly/draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getTopics() {
  return request<{ radars: TopicRadar[]; candidates: TopicCandidate[] }>('/api/v1/topics');
}

export async function captureTopicRadars() {
  return request<TopicCaptureBatchResult>('/api/v1/topics/capture', {
    method: 'POST',
  });
}

export async function createRadar(payload: TopicRadarPayload) {
  return request<TopicRadar>('/api/v1/topics/radars', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateRadar(id: string, payload: TopicRadarPayload) {
  return request<TopicRadar>(`/api/v1/topics/radars/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function suggestRadarTitle(prompt: string) {
  return request<{ title: string }>('/api/v1/topics/radars/generate-title', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

export async function assistRadarDraft(prompt: string, timeRange: string) {
  return request<{ title: string; prompt: string; queries: string[] }>('/api/v1/topics/radars/assist', {
    method: 'POST',
    body: JSON.stringify({ prompt, timeRange }),
  });
}

export async function suggestRadarSourceLabel(url: string) {
  return request<{ url: string; label: string }>('/api/v1/topics/radars/source-label', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function getCandidateInsights(id: string) {
  return request<TopicCandidateInsight>(`/api/v1/topics/candidates/${id}/insights`, { method: 'POST' });
}

export async function askCandidateQuestion(id: string, payload: TopicCandidateChatPayload) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 25000);
  try {
    return await request<TopicCandidateChatResponse>(`/api/v1/topics/candidates/${id}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    if (/abort|aborted|signal is aborted/i.test(detail)) {
      throw new Error('大周这次追问超时了。可以直接再问一次，或者把问题问得更具体一点。');
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getCandidateTaskPlan(id: string) {
  return request<TopicTaskPlanResult>(`/api/v1/topics/candidates/${id}/task-plan`, { method: 'POST' });
}

export async function promoteCandidateTasks(id: string, tasks: TopicTaskPromotionDraft[]) {
  return request<TopicTaskPromotionResult>(`/api/v1/topics/candidates/${id}/promote-tasks`, {
    method: 'POST',
    body: JSON.stringify({ tasks }),
  });
}

export async function deleteCandidate(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/topics/candidates/${id}`, { method: 'DELETE' });
}

export async function getAnalysisTools() {
  return request<{ templates: AnalysisTemplate[]; runs: AnalysisRun[] }>('/api/v1/analysis-tools');
}

export async function runAnalysis(payload: AnalysisRunPayload) {
  return request<AnalysisRun>('/api/v1/analysis-tools/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingDeepDnaLibrary() {
  return request<DeepDnaRecord[]>('/api/v1/analysis-tools/fundraising/dna');
}

export async function upsertFundraisingDeepDna(payload: DeepDnaRecord) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createFundraisingManualDna(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  identitySummary: string;
  corePreferencesText: string;
  supportTriggersText: string;
  redFlagsText: string;
  evidencePreferencesText: string;
  voiceStyleText: string;
  commonQuestionsText: string;
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
}) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna/manual', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function importFundraisingDna(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  fileName: string;
  filePath: string;
  content: string;
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
}) {
  return request<DeepDnaRecord>('/api/v1/analysis-tools/fundraising/dna/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createFundraisingWebDnaDraft(payload: {
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  searchQuery: string;
}) {
  return request<DeepDnaDraft>('/api/v1/analysis-tools/fundraising/dna/web-drafts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function publishFundraisingDna(id: string) {
  return request<DeepDnaRecord>(`/api/v1/analysis-tools/fundraising/dna/${encodeURIComponent(id)}/publish`, {
    method: 'POST',
  });
}

export async function getFundraisingCases() {
  return request<CoachCaseRecord[]>('/api/v1/analysis-tools/fundraising/cases');
}

export async function upsertFundraisingCase(payload: CoachCaseRecord) {
  return request<CoachCaseRecord>('/api/v1/analysis-tools/fundraising/cases', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingReminderRules() {
  return request<CoachReminderRule[]>('/api/v1/analysis-tools/fundraising/reminders');
}

export async function upsertFundraisingReminderRule(payload: CoachReminderRule) {
  return request<CoachReminderRule>('/api/v1/analysis-tools/fundraising/reminders', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingWritingNorms() {
  return request<OrgWritingNorm[]>('/api/v1/analysis-tools/fundraising/norms');
}

export async function upsertFundraisingWritingNorm(payload: OrgWritingNorm) {
  return request<OrgWritingNorm>('/api/v1/analysis-tools/fundraising/norms', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getFundraisingRunComparison(runId: string) {
  return request<RunComparison>(`/api/v1/analysis-tools/fundraising/runs/${encodeURIComponent(runId)}/comparison`);
}

export async function getHandbook() {
  return request<{ entries: HandbookEntry[] }>('/api/v1/handbook');
}

export async function getHandbookEntry(id: string) {
  return request<HandbookEntryDetail>(`/api/v1/handbook/${encodeURIComponent(id)}`);
}

export async function createHandbook(payload: HandbookEntryPayload) {
  return request<HandbookEntry>('/api/v1/handbook', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getGrowthOverview(weekLabel?: string) {
  const search = weekLabel ? `?weekLabel=${encodeURIComponent(weekLabel)}` : '';
  return request<GrowthOverview>(`/api/v1/growth/overview${search}`);
}

export async function getGrowthWorkbench(params?: {
  weekLabel?: string;
  clientId?: string | null;
  mode?: 'global' | 'strategic';
}) {
  const search = new URLSearchParams();
  if (params?.weekLabel) search.set('weekLabel', params.weekLabel);
  if (params?.clientId) search.set('clientId', params.clientId);
  if (params?.mode) search.set('mode', params.mode);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<GrowthWorkbenchSnapshot>(`/api/v1/growth/workbench${suffix}`);
}

export async function getGrowthBadges() {
  return request<BadgeBoard>('/api/v1/growth/badges');
}

export async function getGrowthLedger(params?: { abilityKey?: string; weekLabel?: string }) {
  const search = new URLSearchParams();
  if (params?.abilityKey) search.set('abilityKey', params.abilityKey);
  if (params?.weekLabel) search.set('weekLabel', params.weekLabel);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return request<GrowthLedgerResponse>(`/api/v1/growth/ledger${suffix}`);
}

export async function acceptGrowthRecommendation(id: string) {
  return request<GrowthRecommendationActionResponse>(`/api/v1/growth/recommendations/${id}/accept`, {
    method: 'POST',
  });
}

export async function dismissGrowthRecommendation(id: string, payload: GrowthRecommendationDismissPayload = {}) {
  return request<GrowthRecommendationActionResponse>(`/api/v1/growth/recommendations/${id}/dismiss`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function markHandbookEntryReused(id: string, payload: GrowthValidationPayload = {}) {
  return request<GrowthValidationActionResponse>(`/api/v1/growth/handbook/${id}/mark-reused`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateGrowthPendingCapture(id: string, payload: GrowthPendingCaptureActionPayload) {
  return request<GrowthPendingCaptureActionResponse>(`/api/v1/growth/pending-captures/${id}/state`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function selectCollabRepo() {
  return window.yiyuWorkbench.selectCollabRepo() as Promise<string | null>;
}

export async function getCollabRepoStatus(repoPath?: string | null) {
  return window.yiyuWorkbench.getCollabRepoStatus(repoPath) as Promise<CollabRepoStatus>;
}

export async function previewPushToMain(repoPath: string) {
  return window.yiyuWorkbench.previewPushToMain(repoPath) as Promise<PushPreview>;
}

export async function commitAndPushToMain(payload: CommitAndPushToMainPayload) {
  return window.yiyuWorkbench.commitAndPushToMain(payload) as Promise<CollabActionResult>;
}

export async function previewPullFromMain(repoPath: string) {
  return window.yiyuWorkbench.previewPullFromMain(repoPath) as Promise<PullPreview>;
}

export async function pullSelectedFromMain(payload: PullSelectedFromMainPayload) {
  return window.yiyuWorkbench.pullSelectedFromMain(payload) as Promise<CollabActionResult>;
}

export async function rebuildAndInstallFromRepo(repoPath: string) {
  return window.yiyuWorkbench.rebuildAndInstallFromRepo(repoPath) as Promise<boolean>;
}
~~~

## `src/renderer/lib/clientDnaPromptTemplates.ts`

- 编码: `utf-8`

~~~typescript
import type { ClientDnaModule } from '../../shared/types';

const PROMPTS: Record<ClientDnaModule['moduleKey'], string> = {
  organization_intro: `请根据我提供的材料，撰写一份用于企业内部系统引用的《组织介绍》Markdown 文档。

要求：
1. 只输出 Markdown，不要解释。
2. 不要写宣传口号，不要编造信息。
3. 执行摘要控制在 100-200 字。
4. 正文请写细，重点服务系统理解，不是对外宣传。
5. 如果资料不足，最后单独列出“缺失信息”。

请严格按下面结构输出：

# 执行摘要

# 正文
## 1. 组织定位
## 2. 发展背景
## 3. 核心使命
## 4. 服务对象
## 5. 工作方式
## 6. 核心能力
## 7. 当前阶段特点
## 8. 关键词

# 缺失信息
`,
  business_intro: `请根据我提供的材料，撰写一份用于企业内部系统引用的《项目介绍》Markdown 文档。

要求：
1. 只输出 Markdown，不要解释。
2. 不要写空泛描述，不要编造信息。
3. 执行摘要控制在 100-200 字。
4. 正文请尽量详细，因为这份内容会被任务、日历、学习和问答系统共同引用。
5. 如果资料不足，最后单独列出“缺失信息”。

请严格按下面结构输出：

# 执行摘要

# 正文
## 1. 项目概述
## 2. 项目背景
## 3. 项目目标
## 4. 核心问题
## 5. 服务范围
## 6. 合作机制
## 7. 主要交付物
## 8. 当前阶段重点
## 9. 成功标准
## 10. 项目关键词

# 缺失信息
`,
  team_intro: `请根据我提供的材料，撰写一份用于企业内部系统引用的《团队介绍》Markdown 文档。

要求：
1. 只输出 Markdown，不要解释。
2. 重点写角色、职责和协作关系，不要写空泛团队介绍。
3. 执行摘要控制在 100-180 字。
4. 正文请写细，方便系统理解任务分配、会议参与和协作边界。
5. 如果资料不足，最后单独列出“缺失信息”。

请严格按下面结构输出：

# 执行摘要

# 正文
## 1. 团队概述
## 2. 核心负责人
## 3. 关键角色分工
## 4. 协作关系
## 5. 客户侧或外部关键角色
## 6. 当前协作重点
## 7. 团队风险点

# 缺失信息
`,
  market_intro: `请根据我提供的材料，撰写一份用于企业内部系统引用的《市场背景》Markdown 文档。

要求：
1. 只输出 Markdown，不要解释。
2. 不要写成泛泛行业介绍，要尽量贴近当前项目。
3. 执行摘要控制在 100-180 字。
4. 正文请写细，方便系统理解外部环境、机会和风险。
5. 如果资料不足，最后单独列出“缺失信息”。

请严格按下面结构输出：

# 执行摘要

# 正文
## 1. 行业概况
## 2. 核心需求与痛点
## 3. 当前市场环境
## 4. 竞品或参照对象
## 5. 外部约束
## 6. 当前机会点
## 7. 风险提醒

# 缺失信息
`,
};

export function getClientDnaPromptTemplate(moduleKey: ClientDnaModule['moduleKey']) {
  return PROMPTS[moduleKey];
}
~~~

## `src/renderer/lib/taskTimeline.ts`

- 编码: `utf-8`

~~~typescript
import type { Task } from '../../shared/types';

const TASK_DEFAULT_DUE_TIME = '09:00';
const DAY_MINUTES = 24 * 60;
const MIN_DURATION_MINUTES = 15;
const DEFAULT_TIMED_DURATION_MINUTES = 60;

function startOfDayValue(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(baseDate: Date, days: number) {
  return new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate() + days);
}

export function splitTaskDueDateTime(value?: string | null) {
  if (!value) return { date: '', time: '' };
  const text = value.trim();
  if (!text) return { date: '', time: '' };
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/);
  if (match) {
    return {
      date: match[1],
      time: match[2] && match[3] ? `${match[2]}:${match[3]}` : '',
    };
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return { date: '', time: '' };
  return {
    date: `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`,
    time: `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`,
  };
}

export function normalizeTaskTimeInput(timePart?: string | null) {
  const normalized = (timePart || '').trim();
  if (!normalized) return '';
  const match = normalized.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return '';
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (Number.isNaN(hours) || Number.isNaN(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return '';
  }
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

export function minuteOfDayFromTaskTime(timePart?: string | null) {
  const normalized = normalizeTaskTimeInput(timePart);
  if (!normalized) return null;
  const [hoursText, minutesText] = normalized.split(':');
  return Number(hoursText) * 60 + Number(minutesText);
}

export function formatTaskMinuteOfDay(minuteOfDay: number) {
  const safeMinute = Math.max(0, Math.min(DAY_MINUTES, minuteOfDay));
  const hours = Math.floor(safeMinute / 60);
  const minutes = safeMinute % 60;
  return `${String(Math.min(hours, 24)).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

export function parseTaskDateValue(value?: string | null) {
  if (!value) return null;
  const { date } = splitTaskDueDateTime(value);
  const match = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

export function normalizeDdlToDate(label?: string | null) {
  const text = (label || '').trim();
  const now = new Date();
  if (!text || text === '待确认') return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (text === '今天') return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (text === '本周') return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 3);
  const dayMap: Record<string, number> = { 周一: 1, 周二: 2, 周三: 3, 周四: 4, 周五: 5, 周六: 6, 周日: 0 };
  if (text in dayMap) {
    const delta = (dayMap[text] - now.getDay() + 7) % 7;
    return new Date(now.getFullYear(), now.getMonth(), now.getDate() + delta);
  }
  const match = text.match(/^(\d{2})-(\d{2})$/);
  if (match) {
    return new Date(now.getFullYear(), Number(match[1]) - 1, Number(match[2]));
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

export function normalizeDdlToDateTime(label?: string | null) {
  if (!label) return null;
  const text = label.trim();
  if (!text || text === '待确认') return null;

  const now = new Date();
  const applyTime = (date: Date, hours = 0, minutes = 0) =>
    new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes);

  const todayMatch = text.match(/^今天(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (todayMatch) {
    return applyTime(
      new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      Number(todayMatch[1] || 0),
      Number(todayMatch[2] || 0),
    );
  }

  const weekMatch = text.match(/^本周(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (weekMatch) {
    const base = normalizeDdlToDate('本周');
    return applyTime(base, Number(weekMatch[1] || 0), Number(weekMatch[2] || 0));
  }

  const weekdayMatch = text.match(/^(周[一二三四五六日])(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (weekdayMatch) {
    const base = normalizeDdlToDate(weekdayMatch[1]);
    return applyTime(base, Number(weekdayMatch[2] || 0), Number(weekdayMatch[3] || 0));
  }

  const monthDayMatch = text.match(/^(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (monthDayMatch) {
    const base = normalizeDdlToDate(`${monthDayMatch[1]}-${monthDayMatch[2]}`);
    return applyTime(base, Number(monthDayMatch[3] || 0), Number(monthDayMatch[4] || 0));
  }

  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function resolveTaskDueTimeForDisplay(datePart?: string | null, timePart?: string | null) {
  if (!(datePart || '').trim()) return '';
  const normalizedTime = normalizeTaskTimeInput(timePart);
  return normalizedTime || TASK_DEFAULT_DUE_TIME;
}

export function formatTaskDateTimeLabel(
  value?: string | null,
  options?: { fallbackTime?: string | null },
) {
  if (!value) return '待确认';
  const { date, time } = splitTaskDueDateTime(value);
  if (!date) return value;
  const parsedDate = parseTaskDateValue(date);
  if (!parsedDate) return value;
  const today = new Date();
  const isToday = parsedDate.getFullYear() === today.getFullYear()
    && parsedDate.getMonth() === today.getMonth()
    && parsedDate.getDate() === today.getDate();
  const baseLabel = isToday
    ? '今天'
    : `${String(parsedDate.getMonth() + 1).padStart(2, '0')}-${String(parsedDate.getDate()).padStart(2, '0')}`;
  const explicitTime = normalizeTaskTimeInput(time);
  if (explicitTime) return `${baseLabel} ${explicitTime}`;
  const fallbackTime = normalizeTaskTimeInput(options?.fallbackTime || '');
  return fallbackTime ? `${baseLabel} ${fallbackTime}` : baseLabel;
}

export function formatTaskDateWindowLabel(startValue?: string | null, dueValue?: string | null) {
  if (!dueValue) return '';
  const { date } = splitTaskDueDateTime(dueValue);
  if (!date) return formatTaskDateTimeLabel(dueValue, { fallbackTime: null });
  const normalizedStart = (startValue || '').trim();
  if (!normalizedStart || normalizedStart === date) {
    return formatTaskDateTimeLabel(dueValue, { fallbackTime: null });
  }
  const startDate = parseTaskDateValue(normalizedStart);
  if (!startDate) return formatTaskDateTimeLabel(dueValue, { fallbackTime: null });
  const startLabel = formatTaskDateTimeLabel(normalizedStart, { fallbackTime: null });
  return `${startLabel} → ${formatTaskDateTimeLabel(dueValue, { fallbackTime: null })}`;
}

export function formatTaskTimelineLabel(task: Pick<Task, 'startDate' | 'dueDate' | 'durationMinutes' | 'ddl'>) {
  if (!task.dueDate) return task.ddl || '待确认';
  if (task.startDate) {
    return formatTaskDateWindowLabel(task.startDate, task.dueDate);
  }
  const { date: dueDatePart, time: dueTimePart } = splitTaskDueDateTime(task.dueDate);
  if (!dueDatePart) {
    return formatTaskDateTimeLabel(task.dueDate, { fallbackTime: null });
  }
  const normalizedDueTime = resolveTaskDueTimeForDisplay(dueDatePart, dueTimePart);
  const baseLabel = formatTaskDateTimeLabel(dueDatePart, { fallbackTime: null });
  const startMinute = minuteOfDayFromTaskTime(normalizedDueTime);
  if (startMinute === null) {
    return `${baseLabel} ${normalizedDueTime}`.trim();
  }
  const durationMinutes = Math.max(MIN_DURATION_MINUTES, task.durationMinutes || 0);
  const endMinute = Math.min(startMinute + durationMinutes, DAY_MINUTES);
  return `${baseLabel} ${normalizedDueTime}-${formatTaskMinuteOfDay(endMinute)}`.trim();
}

export function resolveTaskTimelineDateTime(task: Pick<Task, 'dueDate' | 'ddl' | 'createdAt'>) {
  if (task.dueDate) {
    const { date, time } = splitTaskDueDateTime(task.dueDate);
    const normalizedDue = date ? `${date}T${resolveTaskDueTimeForDisplay(date, time)}` : task.dueDate;
    const parsedDue = new Date(normalizedDue);
    if (!Number.isNaN(parsedDue.getTime())) return parsedDue;
  }
  const ddlDate = normalizeDdlToDateTime(task.ddl);
  if (ddlDate) return ddlDate;
  const createdAt = new Date(task.createdAt);
  return Number.isNaN(createdAt.getTime()) ? null : createdAt;
}

export function taskDateForCalendar(task: Pick<Task, 'startDate' | 'dueDate' | 'ddl'>) {
  const explicitStartDate = parseTaskDateValue(task.startDate);
  if (explicitStartDate) return explicitStartDate;
  const explicitDate = parseTaskDateValue(task.dueDate);
  if (explicitDate) return explicitDate;
  return normalizeDdlToDate(task.ddl);
}

export type TaskDateTimeRange = {
  hasExplicitTime: boolean;
  startDateTime: Date;
  endDateTime: Date;
};

export function resolveTaskDateTimeRange(
  task: Pick<Task, 'startDate' | 'dueDate' | 'durationMinutes' | 'ddl' | 'createdAt'>,
): TaskDateTimeRange {
  const fallbackDate = startOfDayValue(taskDateForCalendar(task));
  const startParts = splitTaskDueDateTime(task.startDate);
  const dueParts = splitTaskDueDateTime(task.dueDate);
  const startDate = parseTaskDateValue(startParts.date || task.startDate) || null;
  const dueDate = parseTaskDateValue(dueParts.date || task.dueDate) || null;
  const startMinute = minuteOfDayFromTaskTime(startParts.time);
  const dueMinute = minuteOfDayFromTaskTime(resolveTaskDueTimeForDisplay(dueParts.date || task.dueDate, dueParts.time));
  const safeDuration = Math.max(MIN_DURATION_MINUTES, task.durationMinutes ?? DEFAULT_TIMED_DURATION_MINUTES);

  const dateTimeFromDateAndMinute = (date: Date, minuteOfDay: number) => {
    const safeMinute = Math.max(0, minuteOfDay);
    const dayOffset = Math.floor(safeMinute / DAY_MINUTES);
    const minuteInDay = safeMinute % DAY_MINUTES;
    return new Date(
      date.getFullYear(),
      date.getMonth(),
      date.getDate() + dayOffset,
      Math.floor(minuteInDay / 60),
      minuteInDay % 60,
    );
  };

  if (startDate && (startMinute !== null || dueMinute !== null)) {
    const startDateTime = dateTimeFromDateAndMinute(startDate, startMinute ?? 0);
    if (dueDate && dueMinute !== null) {
      const explicitEndDateTime = dateTimeFromDateAndMinute(dueDate, dueMinute);
      return {
        hasExplicitTime: true,
        startDateTime,
        endDateTime: explicitEndDateTime > startDateTime
          ? explicitEndDateTime
          : new Date(startDateTime.getTime() + safeDuration * 60_000),
      };
    }
    return {
      hasExplicitTime: true,
      startDateTime,
      endDateTime: new Date(startDateTime.getTime() + safeDuration * 60_000),
    };
  }

  if (dueDate && dueMinute !== null) {
    const startDateTime = dateTimeFromDateAndMinute(dueDate, dueMinute);
    return {
      hasExplicitTime: true,
      startDateTime,
      endDateTime: new Date(startDateTime.getTime() + safeDuration * 60_000),
    };
  }

  const normalizedStartDate = startDate || dueDate || fallbackDate;
  if (dueDate) {
    const defaultMinute = minuteOfDayFromTaskTime(TASK_DEFAULT_DUE_TIME) ?? 9 * 60;
    const startBaseDate = startDate || dueDate;
    const startDateTime = dateTimeFromDateAndMinute(startBaseDate, startMinute ?? defaultMinute);
    const endDateTime = dateTimeFromDateAndMinute(dueDate, dueMinute ?? defaultMinute);
    return {
      hasExplicitTime: true,
      startDateTime,
      endDateTime: endDateTime > startDateTime
        ? endDateTime
        : new Date(startDateTime.getTime() + safeDuration * 60_000),
    };
  }

  const durationDays = Math.max(1, Math.ceil(Math.max(0, task.durationMinutes ?? 0) / DAY_MINUTES));
  const defaultMinute = minuteOfDayFromTaskTime(TASK_DEFAULT_DUE_TIME) ?? 9 * 60;
  const fallbackStartDateTime = dateTimeFromDateAndMinute(normalizedStartDate, defaultMinute);
  return {
    hasExplicitTime: true,
    startDateTime: fallbackStartDateTime,
    endDateTime: new Date(fallbackStartDateTime.getTime() + Math.max(safeDuration, DEFAULT_TIMED_DURATION_MINUTES) * 60_000),
  };
}

export function taskOverlapsCalendarWindow(task: Task, startDate: Date, endExclusive: Date) {
  const range = resolveTaskDateTimeRange(task);
  return range.endDateTime > startDate && range.startDateTime < endExclusive;
}

export function taskCoversCalendarDate(task: Task, date: Date) {
  const dayStart = startOfDayValue(date);
  return taskOverlapsCalendarWindow(task, dayStart, addDays(dayStart, 1));
}

export function buildTaskDayTimedSegment(task: Task, dayDate: Date) {
  const range = resolveTaskDateTimeRange(task);
  if (!range.hasExplicitTime) return null;
  const dayStart = startOfDayValue(dayDate);
  const dayEnd = addDays(dayStart, 1);
  if (range.endDateTime <= dayStart || range.startDateTime >= dayEnd) return null;
  const segmentStart = range.startDateTime > dayStart ? range.startDateTime : dayStart;
  const segmentEnd = range.endDateTime < dayEnd ? range.endDateTime : dayEnd;
  const startMinute = segmentStart.getHours() * 60 + segmentStart.getMinutes();
  const endMinute = segmentEnd.getTime() === dayEnd.getTime()
    ? DAY_MINUTES
    : segmentEnd.getHours() * 60 + segmentEnd.getMinutes();
  if (endMinute <= startMinute) return null;
  return {
    startMinute,
    endMinute,
    durationMinutes: endMinute - startMinute,
    timeLabel: `${formatTaskMinuteOfDay(startMinute)}-${formatTaskMinuteOfDay(endMinute)}`,
  };
}

export function assignTimedTaskLanes<T extends { startMinute: number; endMinute: number }>(
  items: T[],
): Array<T & { lane: number; laneCount: number; clusterId: number }> {
  const sorted = [...items].sort((left, right) => {
    if (left.startMinute !== right.startMinute) return left.startMinute - right.startMinute;
    if (left.endMinute !== right.endMinute) return right.endMinute - left.endMinute;
    return 0;
  });
  const result = sorted.map((item) => ({ ...item, lane: 0, laneCount: 1, clusterId: 0 }));
  let active: Array<{ lane: number; endMinute: number; index: number }> = [];
  let groupIndices: number[] = [];
  let groupLaneCount = 1;
  let clusterId = 0;

  const flushGroup = () => {
    groupIndices.forEach((index) => {
      result[index].laneCount = groupLaneCount;
      result[index].clusterId = clusterId;
    });
    groupIndices = [];
    groupLaneCount = 1;
    clusterId += 1;
  };

  result.forEach((item, index) => {
    active = active.filter((entry) => entry.endMinute > item.startMinute);
    if (active.length === 0 && groupIndices.length > 0) {
      flushGroup();
    }
    const occupied = new Set(active.map((entry) => entry.lane));
    let nextLane = 0;
    while (occupied.has(nextLane)) nextLane += 1;
    item.lane = nextLane;
    active.push({ lane: nextLane, endMinute: item.endMinute, index });
    groupIndices.push(index);
    groupLaneCount = Math.max(groupLaneCount, active.length);
  });

  if (groupIndices.length > 0) flushGroup();
  return result;
}
~~~

## `src/renderer/main.tsx`

- 编码: `utf-8`

~~~tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

declare global {
  interface Window {
    __YIYU_BOOT_EVENTS__?: string[];
    __YIYU_APP_RENDERED__?: boolean;
    __YIYU_HIDE_BOOT_DIAGNOSTIC__?: () => void;
  }
}

function recordBootEvent(event: string) {
  if (!Array.isArray(window.__YIYU_BOOT_EVENTS__)) {
    window.__YIYU_BOOT_EVENTS__ = [];
  }
  window.__YIYU_BOOT_EVENTS__.push(`${new Date().toISOString()} ${event}`);
  console.info(`[renderer:boot] ${event}`);
}

class RendererErrorBoundary extends React.Component<
  React.PropsWithChildren,
  { error: Error | null; stack: string }
> {
  state = {
    error: null as Error | null,
    stack: '',
  };

  static getDerivedStateFromError(error: Error) {
    return { error, stack: '' };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    recordBootEvent(`error-boundary:${error.name}:${error.message}`);
    console.error(`[renderer:error-boundary] ${error.name}: ${error.message}\n${error.stack || ''}\n${info.componentStack || ''}`);
    this.setState({ error, stack: info.componentStack || '' });
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-[#F9FAFB] px-8 py-10 text-gray-800">
        <div className="mx-auto max-w-[960px] rounded-[28px] border border-rose-100 bg-white p-8 shadow-[0_20px_60px_rgba(15,23,42,0.12)]">
          <p className="text-[12px] font-bold tracking-[0.22em] text-rose-500 uppercase">Renderer Startup Failed</p>
          <h1 className="mt-3 text-[28px] font-bold text-gray-900">桌面界面启动失败</h1>
          <p className="mt-4 text-[14px] leading-7 text-gray-600">
            React 在渲染阶段捕获到错误，已经阻止白屏。请把下面的信息发给我，我会继续修复。
          </p>

          <div className="mt-6 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-4">
            <p className="text-[13px] font-bold text-rose-700">
              {this.state.error.name}: {this.state.error.message}
            </p>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4">
              <p className="text-[12px] font-bold tracking-[0.18em] text-gray-500 uppercase">Boot Events</p>
              <pre className="mt-3 whitespace-pre-wrap text-[12px] leading-6 text-gray-700">
                {(window.__YIYU_BOOT_EVENTS__ || []).join('\n') || 'No boot events'}
              </pre>
            </div>
            <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4">
              <p className="text-[12px] font-bold tracking-[0.18em] text-gray-500 uppercase">Component Stack</p>
              <pre className="mt-3 whitespace-pre-wrap text-[12px] leading-6 text-gray-700">
                {this.state.stack || 'No component stack'}
              </pre>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

function BootMarker() {
  React.useEffect(() => {
    window.__YIYU_APP_RENDERED__ = true;
    recordBootEvent('app-committed');
    window.__YIYU_HIDE_BOOT_DIAGNOSTIC__?.();
  }, []);
  return null;
}

recordBootEvent('main.tsx:module-evaluated');

window.addEventListener('error', (event) => {
  const detail = event.error instanceof Error
    ? `${event.error.name}: ${event.error.message}\n${event.error.stack || ''}`
    : `${event.message} @ ${event.filename}:${event.lineno}:${event.colno}`;
  recordBootEvent(`window-error:${detail.split('\n')[0]}`);
  console.error(`[renderer:window-error] ${detail}`);
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason instanceof Error
    ? `${event.reason.name}: ${event.reason.message}\n${event.reason.stack || ''}`
    : String(event.reason);
  recordBootEvent(`unhandled-rejection:${reason.split('\n')[0]}`);
  console.error(`[renderer:unhandled-rejection] ${reason}`);
});

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Renderer root element not found');
}

rootElement.innerHTML = '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#F9FAFB;color:#6B7280;font:500 14px PingFang SC, sans-serif;">正在初始化界面…</div>';
recordBootEvent('main.tsx:before-createRoot');

const root = ReactDOM.createRoot(rootElement);
recordBootEvent('main.tsx:before-root-render');

root.render(
  <React.StrictMode>
    <RendererErrorBoundary>
      <BootMarker />
      <App />
    </RendererErrorBoundary>
  </React.StrictMode>
);
~~~

## `src/renderer/qrcode.d.ts`

- 编码: `utf-8`

~~~typescript
declare module 'qrcode';
~~~

## `src/renderer/styles.css`

- 编码: `utf-8`

~~~css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
  --window-drag-strip-height: 42px;
}

* {
  box-sizing: border-box;
}

html,
body,
#root {
  min-height: 100%;
  margin: 0;
}

body {
  font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
  background-color: #f9fafb;
  color: #1f2937;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.window-no-drag {
  -webkit-app-region: no-drag;
}

.window-drag {
  -webkit-app-region: drag;
  user-select: none;
}

.window-drag-strip {
  position: fixed;
  inset: 0 0 auto 0;
  height: var(--window-drag-strip-height);
  z-index: 40;
}

button,
input,
select,
textarea {
  font: inherit;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.animate-in {
  animation: fadeIn 240ms ease-out both;
}

.fade-in {
  animation: fadeIn 240ms ease-out both;
}

.slide-in-from-bottom-4,
.slide-in-from-bottom-8 {
  animation: slideInFromBottom 280ms ease-out both;
}

.slide-in-from-bottom,
.slide-in-from-bottom-full {
  animation: slideInFromBottomFull 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.slide-in-from-right {
  animation: slideInFromRight 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.slide-in-from-top-5 {
  animation: slideInFromTop 280ms ease-out both;
}

.zoom-in-95 {
  animation: zoomIn95 220ms ease-out both;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideInFromBottom {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInFromBottomFull {
  from {
    opacity: 0;
    transform: translateY(100%);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInFromRight {
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInFromTop {
  from {
    opacity: 0;
    transform: translate(-50%, -20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

@keyframes zoomIn95 {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.thinking-orb {
  position: relative;
  z-index: 1;
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5b7bfe;
  background: radial-gradient(circle at 30% 30%, rgba(126, 160, 255, 0.24), rgba(91, 123, 254, 0.08) 62%, rgba(91, 123, 254, 0.04));
  border: 1px solid rgba(91, 123, 254, 0.16);
  box-shadow: 0 10px 24px rgba(91, 123, 254, 0.14);
  animation: thinkingFloat 2.8s ease-in-out infinite;
}

.thinking-ring {
  position: absolute;
  inset: -0.4rem;
  border-radius: 1.25rem;
  border: 1px solid rgba(91, 123, 254, 0.22);
  opacity: 0;
  animation: thinkingRingPulse 2.4s ease-out infinite;
}

.thinking-ring-delay {
  animation-delay: 1.2s;
}

.thinking-progress-bar {
  background: linear-gradient(90deg, #5b7bfe 0%, #8aa7ff 38%, #5b7bfe 72%, #b4c5ff 100%);
  background-size: 200% 100%;
  animation: thinkingShimmer 2.2s linear infinite;
}

.thinking-dot,
.thinking-status-dot {
  display: inline-block;
  border-radius: 999px;
  background: #5b7bfe;
}

.thinking-dot {
  width: 0.4rem;
  height: 0.4rem;
  opacity: 0.35;
  animation: thinkingDotWave 1.2s ease-in-out infinite;
}

.thinking-dot-delay-1 {
  animation-delay: 0.18s;
}

.thinking-dot-delay-2 {
  animation-delay: 0.36s;
}

.thinking-status-dot {
  width: 0.5rem;
  height: 0.5rem;
  box-shadow: 0 0 0 0 rgba(91, 123, 254, 0.45);
  animation: thinkingStatusPulse 1.8s ease-out infinite;
}

@keyframes thinkingFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

@keyframes thinkingRingPulse {
  0% {
    opacity: 0;
    transform: scale(0.9);
  }
  30% {
    opacity: 0.55;
  }
  100% {
    opacity: 0;
    transform: scale(1.18);
  }
}

@keyframes thinkingShimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@keyframes thinkingDotWave {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.28;
  }
  40% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

@keyframes thinkingStatusPulse {
  0% {
    box-shadow: 0 0 0 0 rgba(91, 123, 254, 0.42);
  }
  70% {
    box-shadow: 0 0 0 0.45rem rgba(91, 123, 254, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(91, 123, 254, 0);
  }
}
~~~

## `src/shared/calendar.test.ts`

- 编码: `utf-8`

~~~typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCalendarCells,
  getTodayCalendarState,
  shiftCalendarMonth,
} from './calendar.js';

test('buildCalendarCells aligns Sunday-start months to the last column in a Monday-first calendar', () => {
  const cells = buildCalendarCells(new Date(2026, 2, 1));

  assert.equal(cells.length, 42);
  assert.equal(cells[6]?.day, 1);
});

test('buildCalendarCells aligns Wednesday-start months to the third column in a Monday-first calendar', () => {
  const cells = buildCalendarCells(new Date(2026, 3, 1));

  assert.equal(cells[2]?.day, 1);
});

test('shiftCalendarMonth clamps the selected day to the target month length', () => {
  const state = shiftCalendarMonth(new Date(2026, 4, 1), 31, -1);

  assert.equal(state.calendarDate.getFullYear(), 2026);
  assert.equal(state.calendarDate.getMonth(), 3);
  assert.equal(state.selectedDay, 30);
});

test('getTodayCalendarState resets month anchor and selected day together', () => {
  const today = new Date(2026, 2, 12);
  const state = getTodayCalendarState(today);

  assert.equal(state.calendarDate.getFullYear(), 2026);
  assert.equal(state.calendarDate.getMonth(), 2);
  assert.equal(state.calendarDate.getDate(), 1);
  assert.equal(state.selectedDay, 12);
});
~~~

## `src/shared/calendar.ts`

- 编码: `utf-8`

~~~typescript
export interface CalendarCell {
  day: number | null;
  date: Date | null;
}

export function getStartOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function getDaysInMonth(baseDate: Date) {
  return new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 0).getDate();
}

export function clampCalendarDay(baseDate: Date, day: number) {
  return Math.min(Math.max(day, 1), getDaysInMonth(baseDate));
}

export function buildCalendarCells(baseDate: Date): CalendarCell[] {
  const year = baseDate.getFullYear();
  const month = baseDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const mondayFirstOffset = (firstDay + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: CalendarCell[] = [];

  for (let i = 0; i < mondayFirstOffset; i += 1) {
    cells.push({ day: null, date: null });
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({ day, date: new Date(year, month, day) });
  }

  // Keep the month grid at 6 rows so the calendar card height stays stable
  // and different months do not visually collapse to content width/height.
  while (cells.length % 7 !== 0 || cells.length < 42) {
    cells.push({ day: null, date: null });
  }

  return cells;
}

export function formatMonthTitle(date: Date) {
  return `${date.getFullYear()}年 ${date.getMonth() + 1}月`;
}

export function shiftCalendarMonth(baseDate: Date, selectedDay: number, monthDelta: number) {
  const calendarDate = new Date(baseDate.getFullYear(), baseDate.getMonth() + monthDelta, 1);

  return {
    calendarDate,
    selectedDay: clampCalendarDay(calendarDate, selectedDay),
  };
}

export function getTodayCalendarState(today = new Date()) {
  return {
    calendarDate: getStartOfMonth(today),
    selectedDay: today.getDate(),
  };
}
~~~

## `src/shared/china-calendar.test.ts`

- 编码: `utf-8`

~~~typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import { getChinaCalendarMarkers } from './china-calendar.js';

test('returns festival and off-day markers for 2026 Qingming Festival', () => {
  const markers = getChinaCalendarMarkers(new Date(2026, 3, 4));

  assert.deepEqual(
    markers.map((item) => item.label),
    ['清明', '休'],
  );
});

test('returns make-up workday marker for 2026-10-10', () => {
  const markers = getChinaCalendarMarkers(new Date(2026, 9, 10));

  assert.deepEqual(
    markers.map((item) => item.label),
    ['班'],
  );
});

test('returns empty array for ordinary workday without official holiday markers', () => {
  const markers = getChinaCalendarMarkers(new Date(2026, 2, 23));

  assert.deepEqual(markers, []);
});

~~~

## `src/shared/china-calendar.ts`

- 编码: `utf-8`

~~~typescript
export type ChinaCalendarMarkerKind = 'festival' | 'offday' | 'workday';

export interface ChinaCalendarMarker {
  label: string;
  kind: ChinaCalendarMarkerKind;
}

type MarkerDraft = {
  date: string;
  label: string;
  kind: ChinaCalendarMarkerKind;
};

type RangeMarkerDraft = {
  start: string;
  end: string;
  label: string;
  kind: ChinaCalendarMarkerKind;
};

function addDays(base: Date, days: number) {
  return new Date(base.getFullYear(), base.getMonth(), base.getDate() + days);
}

function toDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function expandRanges(ranges: RangeMarkerDraft[]) {
  const expanded: MarkerDraft[] = [];
  ranges.forEach((range) => {
    const start = new Date(`${range.start}T00:00:00`);
    const end = new Date(`${range.end}T00:00:00`);
    for (let cursor = start; cursor.getTime() <= end.getTime(); cursor = addDays(cursor, 1)) {
      expanded.push({
        date: toDateKey(cursor),
        label: range.label,
        kind: range.kind,
      });
    }
  });
  return expanded;
}

function buildMarkerMap() {
  const ranges: RangeMarkerDraft[] = [
    { start: '2025-01-01', end: '2025-01-01', label: '休', kind: 'offday' },
    { start: '2025-01-28', end: '2025-02-04', label: '休', kind: 'offday' },
    { start: '2025-04-04', end: '2025-04-06', label: '休', kind: 'offday' },
    { start: '2025-05-01', end: '2025-05-05', label: '休', kind: 'offday' },
    { start: '2025-05-31', end: '2025-06-02', label: '休', kind: 'offday' },
    { start: '2025-10-01', end: '2025-10-08', label: '休', kind: 'offday' },
    { start: '2026-01-01', end: '2026-01-03', label: '休', kind: 'offday' },
    { start: '2026-02-15', end: '2026-02-23', label: '休', kind: 'offday' },
    { start: '2026-04-04', end: '2026-04-06', label: '休', kind: 'offday' },
    { start: '2026-05-01', end: '2026-05-05', label: '休', kind: 'offday' },
    { start: '2026-06-19', end: '2026-06-21', label: '休', kind: 'offday' },
    { start: '2026-09-25', end: '2026-09-27', label: '休', kind: 'offday' },
    { start: '2026-10-01', end: '2026-10-07', label: '休', kind: 'offday' },
  ];

  const singles: MarkerDraft[] = [
    { date: '2025-01-01', label: '元旦', kind: 'festival' },
    { date: '2025-01-28', label: '除夕', kind: 'festival' },
    { date: '2025-01-29', label: '春节', kind: 'festival' },
    { date: '2025-04-04', label: '清明', kind: 'festival' },
    { date: '2025-05-01', label: '劳动节', kind: 'festival' },
    { date: '2025-05-31', label: '端午', kind: 'festival' },
    { date: '2025-10-01', label: '国庆', kind: 'festival' },
    { date: '2025-10-06', label: '中秋', kind: 'festival' },
    { date: '2025-01-26', label: '班', kind: 'workday' },
    { date: '2025-02-08', label: '班', kind: 'workday' },
    { date: '2025-04-27', label: '班', kind: 'workday' },
    { date: '2025-09-28', label: '班', kind: 'workday' },
    { date: '2025-10-11', label: '班', kind: 'workday' },
    { date: '2026-01-01', label: '元旦', kind: 'festival' },
    { date: '2026-02-16', label: '除夕', kind: 'festival' },
    { date: '2026-02-17', label: '春节', kind: 'festival' },
    { date: '2026-04-04', label: '清明', kind: 'festival' },
    { date: '2026-05-01', label: '劳动节', kind: 'festival' },
    { date: '2026-06-19', label: '端午', kind: 'festival' },
    { date: '2026-09-25', label: '中秋', kind: 'festival' },
    { date: '2026-10-01', label: '国庆', kind: 'festival' },
    { date: '2026-01-04', label: '班', kind: 'workday' },
    { date: '2026-02-14', label: '班', kind: 'workday' },
    { date: '2026-02-28', label: '班', kind: 'workday' },
    { date: '2026-05-09', label: '班', kind: 'workday' },
    { date: '2026-09-20', label: '班', kind: 'workday' },
    { date: '2026-10-10', label: '班', kind: 'workday' },
  ];

  const priority: Record<ChinaCalendarMarkerKind, number> = {
    festival: 0,
    offday: 1,
    workday: 2,
  };

  const map = new Map<string, ChinaCalendarMarker[]>();
  [...expandRanges(ranges), ...singles].forEach((marker) => {
    const existing = map.get(marker.date) || [];
    if (!existing.some((item) => item.label === marker.label && item.kind === marker.kind)) {
      existing.push({ label: marker.label, kind: marker.kind });
      existing.sort((left, right) => priority[left.kind] - priority[right.kind]);
      map.set(marker.date, existing);
    }
  });

  return map;
}

const CHINA_CALENDAR_MARKERS = buildMarkerMap();

export function getChinaCalendarMarkers(date: Date): ChinaCalendarMarker[] {
  return CHINA_CALENDAR_MARKERS.get(toDateKey(date)) || [];
}

~~~

## `src/shared/departmentInvite.ts`

- 编码: `utf-8`

~~~typescript
const ORGANIZATION_ALIAS_MAP: Record<string, string> = {
  '益语智库': 'YIYU',
  '益语': 'YIYU',
};

const DEPARTMENT_ALIAS_MAP: Record<string, string> = {
  '咨询部': 'ZX',
  '咨询策略部': 'ZX',
  '运营部': 'YY',
  '客户服务部': 'KF',
  '科技发展部': 'KJ',
  '信息数据部': 'SJ',
};

function toInviteSeed(value: string) {
  let hash = 0;
  for (const char of value) {
    hash = (hash * 131 + char.charCodeAt(0)) % 1_000_000;
  }
  return String(hash).padStart(6, '0');
}

function toBase36Seed(value: string, modulo = 36 ** 4) {
  let hash = 0;
  for (const char of value) {
    hash = (hash * 131 + char.charCodeAt(0)) % modulo;
  }
  return hash.toString(36).toUpperCase();
}

function normalizeInviteSegment(
  rawValue: string | null | undefined,
  limit: number,
  aliasMap?: Record<string, string>,
) {
  const value = rawValue?.trim();
  if (!value) return '';
  if (aliasMap && aliasMap[value]) {
    return aliasMap[value].slice(0, limit).toUpperCase();
  }
  const asciiOnly = value.replace(/[^A-Za-z0-9]+/g, '').toUpperCase();
  if (asciiOnly) {
    return asciiOnly.slice(0, limit);
  }
  return toBase36Seed(value, 36 ** limit).padStart(limit, '0').slice(0, limit);
}

export type DepartmentInviteCodeOptions = {
  organizationName?: string | null;
  departmentName?: string | null;
  order?: number | null;
};

export function buildDepartmentInviteCode(
  departmentId: string,
  options: DepartmentInviteCodeOptions = {},
) {
  const { organizationName, departmentName, order } = options;
  if (!organizationName && !departmentName && typeof order !== 'number') {
    return toInviteSeed(departmentId);
  }

  const orgPrefix = normalizeInviteSegment(organizationName, 4, ORGANIZATION_ALIAS_MAP) || 'ORGX';
  const deptPrefix = normalizeInviteSegment(departmentName, 2, DEPARTMENT_ALIAS_MAP) || 'BM';
  const orderValue = typeof order === 'number' && Number.isFinite(order)
    ? Math.max(1, order + 1)
    : (parseInt(toInviteSeed(departmentId).slice(-2), 10) % 99) + 1;
  const orderSegment = String(orderValue).padStart(2, '0');
  return `${orgPrefix}-${deptPrefix}${orderSegment}`;
}

export function buildDepartmentInviteShareText(departmentName: string, inviteCode: string) {
  return `${departmentName} 邀请码 ${inviteCode}`;
}

export function parseDepartmentInviteCode(rawValue: string) {
  const value = rawValue.trim();
  if (!value) return '';

  try {
    const directUrl = new URL(value);
    const invite = directUrl.searchParams.get('invite');
    if (invite) return parseDepartmentInviteCode(decodeURIComponent(invite));
    const departmentId = directUrl.searchParams.get('departmentId');
    if (departmentId) return departmentId.trim();
  } catch {}

  const inviteMatch = value.match(/invite=([^&]+)/i);
  if (inviteMatch) {
    try {
      return parseDepartmentInviteCode(decodeURIComponent(inviteMatch[1]));
    } catch {
      return parseDepartmentInviteCode(inviteMatch[1]);
    }
  }

  const departmentMatch = value.match(/departmentId=([^&]+)/i);
  if (departmentMatch) {
    return decodeURIComponent(departmentMatch[1]).trim();
  }

  if (value.startsWith('dept:')) {
    return value.slice(5).trim();
  }

  const formattedInviteCodeMatch = value.match(/\b([A-Z0-9]{2,8}-[A-Z0-9]{2,8})\b/i);
  if (formattedInviteCodeMatch) {
    return formattedInviteCodeMatch[1].toUpperCase();
  }

  const inviteCodeMatch = value.match(/\b(\d{6})\b/);
  if (inviteCodeMatch) {
    return inviteCodeMatch[1];
  }

  return value;
}
~~~

## `src/shared/mainChainPresentation.test.ts`

- 编码: `utf-8`

~~~typescript
import test from 'node:test';
import assert from 'node:assert/strict';

import type { ProposalRecord } from './types.js';
import {
  containsChatProcessLeakMarkers,
  formatStateSourceSummary,
  getChatRouteDecision,
  getChatRetrievalPresentation,
  getCockpitHeadlineTone,
  getProposalEffectType,
  getWorkspaceSignalTone,
  groupProposalRecords,
  shouldRenderChatExtendedAnalysis,
} from './mainChainPresentation.js';

test('workspace uses formal tone only for approved baseline', () => {
  const tone = getWorkspaceSignalTone({ hasOfficialBaseline: true, authorityLevel: 'approved' });

  assert.equal(tone.sectionLabel, '客户级正式基线');
  assert.equal(tone.authorityBadge, '正式判断');
  assert.equal(tone.notice, null);
  assert.equal(tone.formal, true);
});

test('workspace keeps candidate and fallback in non-formal tone', () => {
  const candidateTone = getWorkspaceSignalTone({ hasOfficialBaseline: false, authorityLevel: 'candidate' });
  const fallbackTone = getWorkspaceSignalTone({ hasOfficialBaseline: false, authorityLevel: 'fallback' });

  assert.equal(candidateTone.sectionLabel, '主链候选信号');
  assert.match(candidateTone.notice || '', /不代表正式结论/);
  assert.equal(candidateTone.formal, false);

  assert.equal(fallbackTone.authorityBadge, '回退判断');
  assert.match(fallbackTone.notice || '', /不代表正式结论/);
  assert.equal(fallbackTone.formal, false);
});

test('cockpit empty official layer disables formal headline', () => {
  const tone = getCockpitHeadlineTone({
    officialLayerStatus: 'empty',
    officialEmptyReason: '当前暂无已批准判断',
  });

  assert.equal(tone.title, '当前暂无已批准判断');
  assert.match(tone.subtitle, /风险雷达/);
  assert.equal(tone.allowFormalHeadline, false);
});

test('chat retrieval reason maps to stable user-facing explanation', () => {
  const stateFirst = getChatRetrievalPresentation({ reason: 'state_first_default' });
  const introEvidence = getChatRetrievalPresentation({ reason: 'intro_query_needs_evidence' });
  const identityGuard = getChatRetrievalPresentation({ reason: 'identity_query_needs_evidence' });
  const insufficient = getChatRetrievalPresentation({ reason: 'state_pool_insufficient' });

  assert.equal(stateFirst.label, '状态优先');
  assert.match(stateFirst.detail, /状态池/);
  assert.equal(introEvidence.label, '证据下钻');
  assert.match(introEvidence.detail, /机构介绍|原始证据/);
  assert.equal(identityGuard.label, '身份校验');
  assert.equal(insufficient.label, '状态不足');
});

test('new retrieval reasons map to evidence-first and registry copy', () => {
  const meeting = getChatRetrievalPresentation({ reason: 'meeting_summary_needs_evidence' });
  const nextActions = getChatRetrievalPresentation({ reason: 'next_actions_needs_evidence' });
  const registry = getChatRetrievalPresentation({ reason: 'official_registry_requested' });
  const hybrid = getChatRetrievalPresentation({ reason: 'default_hybrid_evidence' });

  assert.equal(meeting.label, '证据下钻');
  assert.match(meeting.detail, /会议|行动项/);
  assert.equal(nextActions.label, '证据下钻');
  assert.match(nextActions.detail, /任务|会议行动项/);
  assert.equal(registry.label, '状态优先');
  assert.match(registry.detail, /正式判断/);
  assert.equal(hybrid.label, '证据下钻');
});

test('route decision exposes intent, drilldown and source', () => {
  const evidenceRoute = getChatRouteDecision({
    answerIntent: 'meeting_summary',
    answerMode: 'grounded_answer',
    retrievalDeferred: false,
    reason: 'meeting_summary_needs_evidence',
  });
  const stateRoute = getChatRouteDecision({
    answerIntent: 'official_judgment_registry',
    answerMode: 'grounded_fallback',
    retrievalDeferred: true,
    reason: 'official_registry_requested',
    judgmentQueryMode: 'registry_only',
  });

  assert.equal(evidenceRoute.intentLabel, '会议纪要');
  assert.equal(evidenceRoute.drilldownLabel, '是');
  assert.equal(evidenceRoute.primarySource, '原始资料');

  assert.equal(stateRoute.intentLabel, '正式判断查询');
  assert.equal(stateRoute.drilldownLabel, '否');
  assert.equal(stateRoute.primarySource, '状态池');
  assert.match(stateRoute.noDrilldownReason || '', /正式判断/);
});

test('judgment retrieval modes expose hybrid and registry specific copy', () => {
  const registryOnly = getChatRetrievalPresentation({ judgmentQueryMode: 'registry_only' });
  const hybrid = getChatRetrievalPresentation({
    judgmentQueryMode: 'hybrid',
    evidenceSupportMode: 'linked_state_evidence',
  });
  const evidenceBased = getChatRetrievalPresentation({ judgmentQueryMode: 'evidence_based_synthesis' });

  assert.equal(registryOnly.label, '状态优先');
  assert.match(registryOnly.detail, /已登记的正式判断/);
  assert.equal(hybrid.label, '状态优先');
  assert.match(hybrid.detail, /DNA 信号|待确认判断/);
  assert.equal(evidenceBased.label, '证据下钻');
  assert.match(evidenceBased.detail, /状态池与原始资料/);
});

test('state source summary renders stable summary chips', () => {
  assert.deepEqual(
    formatStateSourceSummary({
      judgments: 2,
      meetings: 1,
      tasks: 3,
      openQuestions: 1,
      conflicts: 0,
      documents: 2,
    }),
    ['2 条判断', '1 次会议', '3 条任务', '1 个未决问题', '2 份原文'],
  );
});

test('state cards only fallback suppresses extended analysis rendering', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '当前已保留结构化回答，延展长文未完整完成。',
    stateSections: {
      official: [],
      candidate: ['待确认判断 A'],
      draftFindings: [],
      evidenceSupport: ['会议纪要：当前仍需补证据'],
      actions: [],
      risks: [],
      unknowns: [],
    },
    fallbackPresentationMode: 'state_cards_only',
  });

  assert.equal(decision.shouldRender, false);
  assert.equal(decision.blockedByPresentationMode, true);
});

test('compact user answer hides leaked process draft content', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '先基于客户工作台里的最新状态信号和当前已命中的高信号原始证据，给出一版可继续推进讨论的判断稿。',
    stateSections: null,
    fallbackPresentationMode: 'compact_user_answer',
  });

  assert.equal(containsChatProcessLeakMarkers('当前最值得抓住的原始观察包括：'), true);
  assert.equal(decision.shouldRender, false);
  assert.equal(decision.blockedByLeakMarkers, true);
});

test('full answer keeps extended analysis visible when not duplicated', () => {
  const decision = shouldRenderChatExtendedAnalysis({
    content: '一、机构定位\n- 当前已经形成一版可展示的正式介绍。',
    stateSections: {
      official: ['当前已经形成正式判断。'],
      candidate: [],
      draftFindings: [],
      evidenceSupport: [],
      actions: [],
      risks: [],
      unknowns: [],
    },
    fallbackPresentationMode: 'full_answer',
  });

  assert.equal(decision.shouldRender, true);
  assert.equal(decision.blockedByPresentationMode, false);
  assert.equal(decision.blockedByLeakMarkers, false);
});

test('proposal grouping keeps review, execute, and history separated', () => {
  const baseProposal = {
    clientId: 'client-1',
    riskLevel: 'medium' as ProposalRecord['riskLevel'],
    title: 'proposal',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
  } satisfies Omit<ProposalRecord, 'id' | 'kind' | 'status'>;
  const grouped = groupProposalRecords([
    { ...baseProposal, id: 'p1', kind: 'task_prep', status: 'pending_review' },
    { ...baseProposal, id: 'p2', kind: 'meeting_prep', status: 'approved' },
    { ...baseProposal, id: 'p3', kind: 'meeting_followup', status: 'executed' },
  ]);

  assert.deepEqual(grouped.pendingReview.map((item) => item.id), ['p1']);
  assert.deepEqual(grouped.approvedExecution.map((item) => item.id), ['p2']);
  assert.deepEqual(grouped.history.map((item) => item.id), ['p3']);
});

test('proposal effect type prefers execution result and falls back to kind/status', () => {
  const prepExecuted = getProposalEffectType({
    id: 'prep',
    clientId: 'client-1',
    kind: 'task_prep',
    status: 'executed',
    riskLevel: 'low',
    title: '任务准备',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
  });
  const followupExecuted = getProposalEffectType({
    id: 'followup',
    clientId: 'client-1',
    kind: 'meeting_followup',
    status: 'executed',
    riskLevel: 'medium',
    title: '会后跟进',
    summary: '',
    rationale: '',
    targetRefs: [],
    sourceRefs: [],
    boundaryNotes: [],
    payload: {},
    createdBy: 'tester',
    createdAt: '2026-04-18T10:00:00',
    updatedAt: '2026-04-18T10:00:00',
    executionTicket: {
      id: 'exec-1',
      proposalId: 'followup',
      clientId: 'client-1',
      executionType: 'task_creation',
      status: 'executed',
      payload: {},
      result: {
        resultType: 'followup_task_created',
        summary: '已创建任务',
        createdTaskIds: ['task-1'],
        artifactRefs: [],
      },
      createdAt: '2026-04-18T10:01:00',
      updatedAt: '2026-04-18T10:01:00',
    },
  });

  assert.equal(prepExecuted, 'prep_artifact_ready');
  assert.equal(followupExecuted, 'followup_task_created');
});
~~~

## `src/shared/mainChainPresentation.ts`

- 编码: `utf-8`

~~~typescript
import type {
  AnalysisAuthorityLevel,
  EvidenceSupportMode,
  FallbackPresentationMode,
  JudgmentQueryMode,
  ProposalRecord,
  RetrievalDecisionReason,
  StateAnswerSections,
  StateSourceSummary,
  WorkspaceAnswerIntent,
} from './types.js';

export type WorkspaceSignalTone = {
  sectionLabel: string;
  authorityBadge: string;
  notice: string | null;
  formal: boolean;
};

export type CockpitHeadlineTone = {
  title: string;
  subtitle: string;
  allowFormalHeadline: boolean;
};

export type ChatRetrievalPresentation = {
  label: '状态优先' | '证据下钻' | '身份校验' | '状态不足';
  detail: string;
};

export type ChatRouteDecision = {
  intentLabel: string;
  drilldownLabel: '是' | '否';
  primarySource: '状态池' | '原始资料' | '状态池 + 原始资料' | '通用背景';
  noDrilldownReason: string | null;
};

export type ProposalEffectType = 'recorded_only' | 'prep_artifact_ready' | 'followup_task_created' | 'failed';

export type ProposalGroupBuckets = {
  pendingReview: ProposalRecord[];
  approvedExecution: ProposalRecord[];
  history: ProposalRecord[];
};

export type ChatExtendedAnalysisDecision = {
  shouldRender: boolean;
  duplicateStateOnlyContent: boolean;
  blockedByPresentationMode: boolean;
  blockedByLeakMarkers: boolean;
};

const CHAT_PROCESS_LEAK_MARKERS = [
  'analysis-first',
  '当前最值得抓住的原始观察包括',
  '先基于客户工作台里的最新状态信号',
  '[本周动作]',
  '[缺失信息]',
  '单击此处编辑母版文本样式',
  '演示文稿标题',
  '演示文稿副标题',
];

function looksLikeAnswerTitle(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (trimmed.length < 6 || trimmed.length > 42) return false;
  if (/[。！？!?]$/.test(trimmed)) return false;
  return !/^(问题|资料简报|回答原则|当前可确认的资料事实)[:：]/.test(trimmed);
}

export function normalizeAnswerTextForDisplay(rawText: string) {
  let text = rawText.replace(/\r\n/g, '\n').trim();
  const firstLineMatch = text.match(/^([^\n]{6,48}?)(\s{2,})(.+)$/s);
  if (firstLineMatch) {
    const candidateTitle = firstLineMatch[1].trim();
    const rest = firstLineMatch[3].trimStart();
    if (looksLikeAnswerTitle(candidateTitle)) {
      text = `${candidateTitle}\n\n${rest}`;
    }
  }
  text = text.replace(/\n([一二三四五六七八九十]+、)/g, '\n\n$1');
  text = text.replace(/\n(第[一二三四五六七八九十0-9]+部分)/g, '\n\n$1');
  return text;
}

export function renderStateSectionsTextForComparison(sections?: StateAnswerSections | null) {
  if (!sections) return '';
  const orderedSections: Array<[string, string[]]> = [
    ['一、正式判断', sections.official],
    ['二、待确认判断 / 判断草稿', [...sections.candidate, ...(sections.draftFindings || [])]],
    ['三、支撑证据摘要', sections.evidenceSupport || []],
    ['四、本周动作 / 当前推进', sections.actions],
    ['五、风险提醒 / 未决问题', sections.risks],
    ['六、缺失信息 / 下一步建议', sections.unknowns],
  ];
  return orderedSections
    .map(([title, items]) => `${title}\n${items.length ? items.map((item) => `- ${item}`).join('\n') : '- 当前暂无可展示内容。'}`)
    .join('\n\n')
    .trim();
}

export function containsChatProcessLeakMarkers(rawText: string) {
  const haystack = rawText.toLowerCase();
  return CHAT_PROCESS_LEAK_MARKERS.some((marker) => haystack.includes(marker.toLowerCase()));
}

export function shouldRenderChatExtendedAnalysis(input: {
  content?: string | null;
  stateSections?: StateAnswerSections | null;
  fallbackPresentationMode?: FallbackPresentationMode | null;
}): ChatExtendedAnalysisDecision {
  const rawContent = (input.content || '').trim();
  if (!rawContent) {
    return {
      shouldRender: false,
      duplicateStateOnlyContent: false,
      blockedByPresentationMode: false,
      blockedByLeakMarkers: false,
    };
  }
  const duplicateStateOnlyContent = Boolean(input.stateSections)
    && normalizeAnswerTextForDisplay(rawContent) === normalizeAnswerTextForDisplay(renderStateSectionsTextForComparison(input.stateSections));
  const blockedByPresentationMode = input.fallbackPresentationMode === 'state_cards_only';
  const blockedByLeakMarkers = input.fallbackPresentationMode === 'compact_user_answer' && containsChatProcessLeakMarkers(rawContent);
  return {
    shouldRender: !duplicateStateOnlyContent && !blockedByPresentationMode && !blockedByLeakMarkers,
    duplicateStateOnlyContent,
    blockedByPresentationMode,
    blockedByLeakMarkers,
  };
}

export function getWorkspaceSignalTone(input: {
  hasOfficialBaseline: boolean;
  authorityLevel?: AnalysisAuthorityLevel | null;
}): WorkspaceSignalTone {
  const authorityLevel = input.authorityLevel || 'fallback';
  const authorityBadge =
    authorityLevel === 'approved'
      ? '正式判断'
      : authorityLevel === 'candidate'
        ? '候选判断'
        : '回退判断';
  if (input.hasOfficialBaseline && authorityLevel === 'approved') {
    return {
      sectionLabel: '客户级正式基线',
      authorityBadge,
      notice: null,
      formal: true,
    };
  }
  return {
    sectionLabel: '主链候选信号',
    authorityBadge,
    notice: '当前暂无客户级已批准判断。以下内容只作为候选信号或回退结果，不代表正式结论。',
    formal: false,
  };
}

export function getCockpitHeadlineTone(input: {
  officialLayerStatus: 'ready' | 'empty';
  officialEmptyReason?: string | null;
}): CockpitHeadlineTone {
  if (input.officialLayerStatus === 'ready') {
    return {
      title: '官方层已就绪',
      subtitle: '当前标题和结论可以使用正式语气。',
      allowFormalHeadline: true,
    };
  }
  return {
    title: input.officialEmptyReason || '当前暂无已批准判断',
    subtitle: '以下仅展示候选信号与风险雷达，不代表正式结论。',
    allowFormalHeadline: false,
  };
}

export function getChatRetrievalPresentation(input?: {
  reason?: RetrievalDecisionReason | null;
  judgmentQueryMode?: JudgmentQueryMode | null;
  evidenceSupportMode?: EvidenceSupportMode | null;
} | null): ChatRetrievalPresentation {
  const reason = input?.reason;
  const judgmentQueryMode = input?.judgmentQueryMode;
  const evidenceSupportMode = input?.evidenceSupportMode;

  if (judgmentQueryMode === 'registry_only') {
    return {
      label: '状态优先',
      detail: '当前优先展示系统内已登记的正式判断。',
    };
  }
  if (judgmentQueryMode === 'hybrid') {
    return {
      label: '状态优先',
      detail:
        evidenceSupportMode === 'raw_doc_drilldown'
          ? '当前先读取已登记判断，再结合资料、会议、任务和 DNA 信号形成待确认判断，并补充少量原文回引。'
          : '当前先读取已登记判断，再结合资料、会议、任务和 DNA 信号形成待确认判断。',
    };
  }
  if (judgmentQueryMode === 'evidence_based_synthesis') {
    return {
      label: '证据下钻',
      detail: '当前已进入证据下钻，将结合状态池与原始资料回答。',
    };
  }

  switch (reason) {
    case 'official_registry_requested':
    case 'state_first_default':
      return {
        label: '状态优先',
        detail: reason === 'official_registry_requested'
          ? '当前优先读取系统内已登记的正式判断。'
          : '这次先读客户状态池，再按需下钻原文。',
      };
    case 'document_drilldown_requested':
    case 'search_cache_requested':
      return {
        label: '证据下钻',
        detail: '这次明确要求引用原文或已有搜索证据，优先走证据链。',
      };
    case 'intro_query_needs_evidence':
    case 'project_intro_needs_evidence':
      return {
        label: '证据下钻',
        detail: reason === 'project_intro_needs_evidence'
          ? '项目介绍类问题优先回到项目资料与原始证据，不直接套状态池。'
          : '介绍或简介类问题优先回到机构介绍、项目资料和原始证据，不直接套状态池。',
      };
    case 'meeting_summary_needs_evidence':
      return {
        label: '证据下钻',
        detail: '会议纪要类问题优先检索会议、行动项和原始资料证据。',
      };
    case 'next_actions_needs_evidence':
      return {
        label: '证据下钻',
        detail: '下一步类问题优先结合任务、会议行动项与原始资料。',
      };
    case 'evidence_question_needs_evidence':
      return {
        label: '证据下钻',
        detail: '这次问题明确要求依据或引用，回答优先回到原始证据。',
      };
    case 'status_progress_needs_hybrid_evidence':
    case 'default_hybrid_evidence':
      return {
        label: '证据下钻',
        detail: '当前采用状态池 + 原始资料的混合证据回答。',
      };
    case 'identity_query_needs_evidence':
      return {
        label: '身份校验',
        detail: '涉及人物或角色问题，必须先确认原始证据。',
      };
    case 'state_pool_insufficient':
    case 'state_pool_empty':
    default:
      return {
        label: '状态不足',
        detail: '当前状态池还不够稳，需要更多证据或补充信息。',
      };
  }
}

export function getWorkspaceAnswerIntentLabel(intent?: WorkspaceAnswerIntent | null): string {
  switch (intent) {
    case 'intro_profile':
      return '介绍客户/机构';
    case 'project_intro':
      return '介绍项目';
    case 'meeting_summary':
      return '会议纪要';
    case 'next_actions':
      return '下一步行动';
    case 'official_judgment_registry':
      return '正式判断查询';
    case 'evidence_question':
      return '证据追问';
    case 'status_progress':
      return '状态推进';
    case 'general':
    default:
      return '通用问答';
  }
}

export function getChatRouteDecision(input: {
  answerIntent?: WorkspaceAnswerIntent | null;
  answerMode?: 'grounded_answer' | 'grounded_fallback' | 'low_confidence_answer' | 'general_answer' | 'system_failure' | null;
  retrievalDeferred?: boolean;
  reason?: RetrievalDecisionReason | null;
  judgmentQueryMode?: JudgmentQueryMode | null;
}): ChatRouteDecision {
  const intentLabel = getWorkspaceAnswerIntentLabel(input.answerIntent);
  const retrievalDeferred = Boolean(input.retrievalDeferred);
  const reason = input.reason || null;
  const drilledDown = !retrievalDeferred;
  let primarySource: ChatRouteDecision['primarySource'] = '原始资料';
  if (input.answerMode === 'general_answer') {
    primarySource = '通用背景';
  } else if (reason === 'official_registry_requested' || reason === 'state_first_default' || input.judgmentQueryMode === 'registry_only') {
    primarySource = '状态池';
  } else if (input.judgmentQueryMode === 'hybrid' || input.judgmentQueryMode === 'evidence_based_synthesis') {
    primarySource = drilledDown ? '状态池 + 原始资料' : '状态池';
  } else if (retrievalDeferred) {
    primarySource = '状态池';
  }
  let noDrilldownReason: string | null = null;
  if (!drilledDown) {
    noDrilldownReason = getChatRetrievalPresentation({
      reason,
      judgmentQueryMode: input.judgmentQueryMode,
    }).detail;
  }
  return {
    intentLabel,
    drilldownLabel: drilledDown ? '是' : '否',
    primarySource,
    noDrilldownReason,
  };
}

export function formatStateSourceSummary(summary?: StateSourceSummary | null): string[] {
  if (!summary) return [];
  const items: string[] = [];
  if (summary.judgments > 0) items.push(`${summary.judgments} 条判断`);
  if (summary.meetings > 0) items.push(`${summary.meetings} 次会议`);
  if (summary.tasks > 0) items.push(`${summary.tasks} 条任务`);
  if (summary.openQuestions > 0) items.push(`${summary.openQuestions} 个未决问题`);
  if (summary.conflicts > 0) items.push(`${summary.conflicts} 个风险冲突`);
  if (summary.documents > 0) items.push(`${summary.documents} 份原文`);
  return items;
}

export function groupProposalRecords(proposals: ProposalRecord[]): ProposalGroupBuckets {
  return {
    pendingReview: proposals.filter((proposal) => proposal.status === 'pending_review' || proposal.status === 'draft'),
    approvedExecution: proposals.filter((proposal) => proposal.status === 'approved' || proposal.status === 'execution_pending'),
    history: proposals.filter((proposal) => ['executed', 'failed', 'rejected'].includes(proposal.status)).slice(0, 8),
  };
}

export function getProposalEffectType(proposal: ProposalRecord): ProposalEffectType {
  const resultType = proposal.executionTicket?.result?.resultType;
  if (resultType) return resultType;
  if (proposal.status === 'failed') return 'failed';
  if (proposal.status === 'executed') {
    return proposal.kind === 'meeting_followup' ? 'followup_task_created' : 'prep_artifact_ready';
  }
  return 'recorded_only';
}
~~~

## `src/shared/types.ts`

- 编码: `utf-8`

~~~typescript
export type Priority = 'low' | 'normal' | 'high';
export type TaskStatus = 'inbox' | 'todo' | 'doing' | 'done' | 'rejected';
export type TaskDueDatePreset = 'today' | 'none';
export type TaskListSortMode = 'dueDate' | 'priority' | 'manual';
export type TaskViewPreference = 'inbox' | 'list' | 'calendar' | 'review';
export type TaskReviewScope = 'work' | 'personal';
export type TaskScopeMode = 'COLLAB_SHARED' | 'PERSONAL_ONLY';
export type ReviewCompletionStatus = 'done_on_time' | 'done_late' | 'in_progress' | 'not_done';
export type ReviewAlignmentStatus = 'aligned' | 'partial' | 'misaligned' | 'unknown';
export type ReviewLightweightTag = '' | '资料不足' | '等待他人' | '方向不清' | '资源不够' | '工作过度饱和';
export type AgentDepartmentKey = 'strategy_design' | 'tech_development' | 'info_data';
export type AgentPlanStatus = 'planned' | 'doing' | 'done' | 'blocked';
export type TopicTaskOwnerMode = 'self' | 'empty';
export type TopicCandidateStatus = 'candidate' | 'tracking' | 'promoted' | 'archived';
export type TopicCandidateInsightStatus = 'pending' | 'ready' | 'failed';
export type MeetingStage = 'prepared' | 'ingested' | 'extracted' | 'resolved' | 'published';
export type AiProvider = 'mock' | 'qwen' | 'doubao';
export type AccountStatus = 'pending' | 'approved' | 'rejected' | 'disabled';
export type EmployeeRole = 'admin' | 'employee';
export type CollaboratorInboxStatus = 'pending' | 'accepted' | 'returned';
export type OrgRoleLevel = 'employee' | 'supervisor' | 'department_lead' | 'organization_lead';
export type OrgReportingLineType = 'business' | 'administrative';
export type OrgTaskEditScope = 'self' | 'manager' | 'department' | 'organization';
export type OrgTaskControlLevel = 'normal' | 'leader_control' | 'department_control' | 'organization_control';
export type OrgRuleActorScope = 'assignee' | 'manager' | 'department_lead' | 'organization_lead' | 'creator';
export type OrgWorkflowTriggerType = 'weekly_followup' | 'task_created' | 'meeting_closed' | 'client_update' | 'manual';
export type OrgFocusPriority = 'high' | 'medium' | 'low';
export type OrgFocusStatus = 'draft' | 'active' | 'paused' | 'done';
export type OrgDepartmentPlanStatus = 'draft' | 'active' | 'closed';
export type OrgDepartmentPlanItemStatus = 'active' | 'paused' | 'done' | 'dropped';
export type TaskPlanLinkSource = 'ai' | 'manager' | 'rule';
export type SupportRequestTargetScope = 'manager' | 'department' | 'organization' | 'cross_department';
export type SupportRequestType = 'resource' | 'decision' | 'collaboration' | 'workload' | 'clarification';
export type SupportRequestStatus = 'open' | 'accepted' | 'resolved' | 'dismissed';
export type DnaSourceLevel = 'organization' | 'client';
export type OrganizationDnaModuleKey = 'organization_intro' | 'business_intro' | 'team_intro' | 'market_intro';
export type FeishuReceiveIdType = 'open_id' | 'user_id' | 'email' | 'chat_id';
export type GrowthAbilityKey = 'exec' | 'collab' | 'analyze' | 'insight' | 'risk' | 'write';
export type GrowthEvidenceType = 'reflection' | 'codification' | 'reuse' | 'improvement';
export type GrowthConfidence = 'high' | 'medium' | 'low';
export type LearningContentType = 'method_card' | 'practice_card' | 'correction_card';
export type LearningRecommendationStatus = 'active' | 'accepted' | 'dismissed';
export type GrowthContributionTag = 'knowledge_asset' | 'critical_resolution' | 'collaboration_enablement' | 'risk_alignment' | 'mechanism_building';
export type GrowthValidationState = 'candidate' | 'observed' | 'validated' | 'institutionalized';
export type GrowthPendingCaptureState = 'open' | 'dismissed' | 'reviewed' | 'promoted';
export type BadgeState = 'locked' | 'progress' | 'ready' | 'lit' | 'mastered';
export type AnalysisScopeType = 'client' | 'event_line' | 'meeting' | 'task' | 'module' | 'flow';
export type AnalysisJobType = 'asset_ingest' | 'evidence_extract' | 'customer_compare' | 'meeting_enhance' | 'dna_refresh' | 'strategy_pack';
export type AnalysisJobStatus =
  | 'queued'
  | 'running'
  | 'preparing'
  | 'extracting'
  | 'clustering'
  | 'comparing'
  | 'drafting'
  | 'awaiting_review'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rolled_back';
export type AnalysisReviewState = 'draft' | 'awaiting_review' | 'awaiting_revision' | 'approved' | 'rejected' | 'superseded';
export type AnalysisStageStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';
export type AnalysisOriginType = 'projection' | 'analysis' | 'human_override';
export type AnalysisAuthorityLevel = 'fallback' | 'candidate' | 'approved';
export type AnalysisQualityTier = 'legacy' | 'normalized' | 'reviewed';
export type AnalysisIntentProfile = 'task_ai' | 'weekly_review' | 'meeting_enhance' | 'client_overview' | 'strategic_cockpit' | 'dna_summary';
export type AnalysisStaleReason =
  | 'superseded_by_newer_judgment'
  | 'source_snapshot_changed'
  | 'approval_revoked'
  | 'scope_no_longer_primary'
  | 'insufficient_evidence'
  | 'manual_invalidation';
export type AnalysisRejectedReason =
  | 'authority_too_low'
  | 'scope_less_relevant'
  | 'stale'
  | 'superseded'
  | 'insufficient_evidence'
  | 'not_approved_for_official_use';
export type ApprovalDecision = 'approved' | 'rejected' | 'returned_for_revision';
export type ApprovalTargetType = 'judgment_version' | 'dna_delta' | 'conflict_group' | 'proposal_record';
export type AnalysisLane = 'light_extractor' | 'local_deep' | 'cloud_final';

export interface Operator {
  id: string;
  name: string;
  role: string;
  team: string;
  color: string;
  isCurrent: boolean;
}

export interface AppSettings {
  currentOperatorId: string;
  aiProvider: AiProvider;
  aiModel: string;
  dataDir: string;
  backupDir: string;
  cloudApiUrl: string;
  lastBackupAt?: string | null;
  foldersRootLabel: string;
  aiConfigured: boolean;
  aiCredentialSource: string;
  aiFingerprint?: string | null;
  demoDataLoaded: boolean;
}

export interface SessionUser {
  id: string;
  organizationId: string;
  email: string;
  fullName: string;
  primaryRole: EmployeeRole;
  accountStatus: AccountStatus;
}

export interface AuthState {
  authenticated: boolean;
  user?: SessionUser | null;
  message?: string | null;
  sessionMode?: 'local' | 'cloud';
}

export type ConsultationKnowledgeTarget = 'vector_memory' | 'document_archive';
export type ConsultationKnowledgeRequestStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface ConsultationKnowledgeRequestRecord {
  id: string;
  answerId: string;
  organizationId: string;
  target: ConsultationKnowledgeTarget;
  status: ConsultationKnowledgeRequestStatus;
  requestedByUserId: string;
  requestedByName: string;
  clientId?: string | null;
  clientName?: string | null;
  taskId?: string | null;
  eventLineId?: string | null;
  question: string;
  answer: string;
  errorMessage?: string | null;
  localDocumentId?: string | null;
  localDocumentPath?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConsultationKnowledgeProcessSummary {
  totalPending: number;
  processedCount: number;
  completedCount: number;
  failedCount: number;
  skippedCount: number;
  updatedAt: string;
  items: ConsultationKnowledgeRequestRecord[];
}

export interface EmployeeRecord {
  id: string;
  email: string;
  fullName: string;
  primaryRole: EmployeeRole;
  accountStatus: AccountStatus;
  departmentId?: string | null;
  departmentName?: string | null;
  jobTitle?: string | null;
  managerName?: string | null;
  currentFocus?: string | null;
  isDepartmentLead?: boolean;
  approvedAt?: string | null;
  rejectedReason?: string | null;
  disabledAt?: string | null;
  lastLoginAt?: string | null;
  createdAt: string;
}

export interface DepartmentOption {
  id: string;
  name: string;
  color: string;
}

export interface OrgProfileSettings {
  organizationId: string;
  name: string;
  annualGoal: string;
  annualStrategyYear: string;
  annualStrategy: string;
  quarterPlans: OrgQuarterPlanSettings[];
  quarterlyFocus: string[];
  leaderUserId?: string | null;
  managementUserIds: string[];
  updatedAt: string;
}

export type OrgQuarterKey = 'Q1' | 'Q2' | 'Q3' | 'Q4';

export interface OrgQuarterPlanSettings {
  id: string;
  year: string;
  quarter: OrgQuarterKey;
  theme: string;
  objective: string;
  keyResults: string[];
  keyActions: string[];
  majorRisks: string[];
  updatedAt: string;
}

export interface OrgDepartmentQuarterPlanSettings {
  year: string;
  quarter: OrgQuarterKey;
  objective: string;
  deliverables: string[];
  successMetrics: string[];
  majorRisks: string[];
  updatedAt: string;
}

export interface OrgDepartmentSettings {
  id: string;
  name: string;
  color: string;
  leaderUserId?: string | null;
  leaderName?: string;
  parentDepartmentId?: string | null;
  mission: string;
  businessContext: string;
  teamContext: string;
  quarterPlan: OrgDepartmentQuarterPlanSettings;
  quarterlyFocus: string[];
  collaborationDepartmentIds: string[];
  active: boolean;
  updatedAt: string;
}

export interface OrgRoleTemplateSettings {
  id: string;
  departmentId?: string | null;
  name: string;
  level: OrgRoleLevel;
  managerRoleId?: string | null;
  isManager: boolean;
  goal: string;
  responsibilities: string[];
  shouldAvoid: string[];
  collaborationRoleIds: string[];
  taskEditScope: OrgTaskEditScope;
  canApproveTasks: boolean;
  canReassignTasks: boolean;
  canChangeDeadline: boolean;
  sortOrder: number;
  active: boolean;
  updatedAt: string;
}

export interface OrgEmployeeBindingSettings {
  userId: string;
  departmentId?: string | null;
  primaryRoleId?: string | null;
  managerUserId?: string | null;
  isManager: boolean;
  projectRoleLabels: string[];
  currentFocus: string;
  taskEditScope: OrgTaskEditScope;
  canApproveTasks: boolean;
  canReassignTasks: boolean;
  canChangeDeadline: boolean;
  updatedAt: string;
}

export interface OrgReportingLineSettings {
  id: string;
  managerUserId: string;
  reportUserId: string;
  lineType: OrgReportingLineType;
  approvesTasks: boolean;
  canAdjustTasks: boolean;
  canChangeDeadline: boolean;
  canReassignTasks: boolean;
  isCrossDepartmentApprover: boolean;
  active: boolean;
  updatedAt: string;
}

export interface OrgTaskControlRuleSettings {
  id: string;
  name: string;
  controlLevel: OrgTaskControlLevel;
  departmentId?: string | null;
  roleTemplateId?: string | null;
  contentEditableBy: OrgRuleActorScope;
  deadlineEditableBy: OrgRuleActorScope;
  ownerEditableBy: OrgRuleActorScope;
  cancellableBy: OrgRuleActorScope;
  requireCollabConfirmation: boolean;
  defaultApproverUserId?: string | null;
  active: boolean;
  updatedAt: string;
}

export interface OrgRoleProcessTemplateSettings {
  id: string;
  roleTemplateId?: string | null;
  name: string;
  triggerType: OrgWorkflowTriggerType;
  triggerCondition: string;
  keySteps: string[];
  collaborationStep: string;
  approvalStep: string;
  outputArtifact: string;
  commonBlockers: string[];
  active: boolean;
  updatedAt: string;
}

export interface OrgFocusItemSettings {
  id: string;
  periodKey: string;
  title: string;
  statement: string;
  ownerUserId?: string | null;
  priority: OrgFocusPriority;
  status: OrgFocusStatus;
  evidenceKeywords: string[];
  updatedAt: string;
}

export interface OrgDepartmentPlanItemSettings {
  id: string;
  focusItemId?: string | null;
  title: string;
  statement: string;
  ownerUserId?: string | null;
  status: OrgDepartmentPlanItemStatus;
  expectedOutput: string;
  sortOrder: number;
  updatedAt: string;
}

export interface OrgDepartmentPlanSettings {
  id: string;
  departmentId?: string | null;
  weekLabel: string;
  ownerUserId?: string | null;
  summary: string;
  majorRisks: string[];
  dependencies: string[];
  status: OrgDepartmentPlanStatus;
  items: OrgDepartmentPlanItemSettings[];
  updatedAt: string;
}

export interface TaskPlanLinkRecord {
  taskId: string;
  departmentPlanItemId?: string | null;
  focusItemId?: string | null;
  linkedBy: TaskPlanLinkSource;
  confidence: number;
  updatedAt: string;
}

export interface SupportRequestRecord {
  id: string;
  taskId?: string | null;
  requesterUserId: string;
  targetScope: SupportRequestTargetScope;
  targetRefId?: string | null;
  requestType: SupportRequestType;
  urgency: OrgFocusPriority;
  summary: string;
  status: SupportRequestStatus;
  resolutionNote: string;
  createdAt: string;
  updatedAt: string;
}

export interface SupportRequestCreatePayload {
  taskId?: string | null;
  eventLineId?: string | null;
  targetScope: SupportRequestTargetScope;
  targetRefId?: string | null;
  requestType: SupportRequestType;
  urgency: OrgFocusPriority;
  summary: string;
}

export interface SupportRequestResolvePayload {
  resolutionNote?: string;
  status?: 'accepted' | 'resolved' | 'dismissed';
}

export interface TaskOrgBackfillResult {
  organizationId: string;
  totalTasks: number;
  linkedTasks: number;
  createdLinks: number;
  updatedLinks: number;
  updatedAt: string;
}

export interface OrgModelSettings {
  organization: OrgProfileSettings;
  departments: OrgDepartmentSettings[];
  roles: OrgRoleTemplateSettings[];
  bindings: OrgEmployeeBindingSettings[];
  reportingLines: OrgReportingLineSettings[];
  taskControlRules: OrgTaskControlRuleSettings[];
  roleProcessTemplates: OrgRoleProcessTemplateSettings[];
  focusItems: OrgFocusItemSettings[];
  departmentPlans: OrgDepartmentPlanSettings[];
  updatedAt: string;
}

export interface MentionCandidate {
  id: string;
  fullName: string;
  email: string;
  primaryRole: EmployeeRole;
  isSelf: boolean;
}

export interface HealthResponse {
  backend: 'online';
  appName: string;
  appVersion: string;
  buildVersion: string;
  backendBuildHash?: string;
  backendSchemaVersion?: number;
  runtimeMode?: 'packaged' | 'dev';
  startedAt: string;
  featureFlags: string[];
  dataDir: string;
  stats: {
    clients: number;
    tasks: number;
    topics: number;
    handbookEntries: number;
    analysisRuns: number;
  };
  ai: {
    provider: AiProvider;
    model: string;
    ready: boolean;
    detail: string;
    credentialSource: string;
    fingerprint?: string | null;
  };
}

export interface ClientSummary {
  id: string;
  name: string;
  alias: string;
  domain: string;
  type: string;
  intro: string;
  stage: string;
  color?: string;
  folderCount: number;
  documentCount: number;
  taskCount: number;
  lastActivityAt?: string | null;
}

export interface ClientFolder {
  id: string;
  clientId: string;
  label: string;
  path: string;
  fileCount: number;
  lastScannedAt?: string | null;
}

export interface DocumentRecord {
  id: string;
  clientId: string;
  folderId?: string | null;
  title: string;
  path: string;
  kind: string;
  source: 'folder' | 'file' | 'meeting';
  excerpt: string;
  tags: string[];
  importedAt: string;
}

export interface KnowledgeStatus {
  totalDocuments: number;
  totalChunks: number;
  vectorizedDocuments: number;
  dedupedDocuments: number;
  reviewPendingDocuments: number;
  surrogateCount: number;
  memoryDocCount: number;
  masterIndexCount: number;
  reclassifiedDocumentCount: number;
  qdrantReady: boolean;
  lastUpdatedAt?: string | null;
  pendingJobs: number;
  runningJobs: number;
  lastJobStatus: 'idle' | 'queued' | 'running' | 'completed' | 'failed';
  lastJobError?: string | null;
  lastSuccessfulRunAt?: string | null;
  embeddingMode: string;
  embeddingModel?: string | null;
  embeddingError?: string | null;
}

export interface OrganizationNotebookSnapshot {
  id: string;
  clientId: string;
  organizationIntro: string;
  collaborationRelationship: string;
  currentStage: string;
  businessModules: string[];
  keyPeople: string[];
  keyProducts: string[];
  currentChallenges: string[];
  collaborationGoals: string[];
  recentFacts: string[];
  informationGaps: string[];
  updatedAt: string;
  confidence: number;
}

export interface EventLineMemorySnapshot {
  id: string;
  eventLineId: string;
  lineName: string;
  currentStage: string;
  currentWork: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  evidenceRefs: string[];
  clarificationNeeds: string[];
  analysisSignals: string[];
  predictionReadiness: number;
  updatedAt: string;
  confidence: number;
}

export interface MemoryFact {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  factKey: string;
  factValue: string;
  sourceType: string;
  sourceId: string;
  confidence: number;
  freshness: number;
  evidenceRefs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ClarificationRecord {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  slotKey: string;
  question: string;
  status: 'pending' | 'answered';
  answerText?: string | null;
  writeScope: string[];
  resolvedFactIds: string[];
  reusable: boolean;
  createdAt: string;
  answeredAt?: string | null;
  updatedAt: string;
}

export interface MemoryStatus {
  clientId: string;
  notebookCompleteness: number;
  notebookConfidence: number;
  eventLineCoverage: number;
  totalEventLines: number;
  coveredEventLines: number;
  pendingClarifications: number;
  lowEvidenceJudgments: number;
  updatedAt: string;
}

export interface BackgroundReadiness {
  score: number;
  level: 'low' | 'medium' | 'high';
  missingSlots: string[];
  backgroundSources: string[];
}

export interface DocumentCard {
  id: string;
  docId: string;
  clientId: string;
  documentId: string;
  title: string;
  originalPath: string;
  sourcePath: string;
  logicalCategory?: string | null;
  logicalSubcategory?: string | null;
  classificationReason?: string | null;
  importSourcePath?: string | null;
  currentHumanPath?: string | null;
  humanFolderCategory?: string | null;
  normalizedPath?: string | null;
  surrogateMdPath?: string | null;
  kind: string;
  primaryCategory: string;
  secondaryCategory: string;
  shortSummary: string;
  summary: string;
  retrievalSummary: string;
  documentRole: string;
  queryHints: string[];
  distinctFindings: string[];
  coreQuestions: string[];
  keywords: string[];
  tags: string[];
  entities: string[];
  dateRange?: string | null;
  classificationConfidence: number;
  needsReview: boolean;
  deepRead: boolean;
  lastHitQuestion?: string | null;
  dedupStatus: string;
  vectorStatus: string;
  version: number;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ImportRecord {
  id: string;
  clientId: string;
  sourcePath: string;
  mode: 'folder' | 'file';
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'scanned';
  importedCount: number;
  skippedCount: number;
  createdAt: string;
}

export interface WorkspaceImportBackfillResponse {
  importId: string;
  jobId: string;
  sourceRoot: string;
  discovered: number;
  imported: number;
  skipped: number;
}

export interface ClientTemplateFillField {
  label: string;
  value: string;
  status: 'filled' | 'missing';
  evidenceTitles: string[];
  webSourceTitles?: string[];
  fieldType?: 'precise_fact' | 'structural_summary' | 'governance_mechanism' | 'quantitative_result' | 'attachment_material' | 'general' | null;
  valueKind?: 'fact' | 'summary' | 'inference' | 'missing' | null;
  confidence?: number | null;
  basisSummary?: string | null;
  followUpQuestion?: string | null;
  suggestedSources?: string[];
  reviewRequired?: boolean;
}

export interface ClientTemplateFillResponse {
  path: string;
  fileName: string;
  fieldCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
}

export interface ClientTemplateFillRun {
  id: string;
  clientId: string;
  templateName: string;
  templatePath: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: 'queued' | 'parsing' | 'retrieving' | 'writing' | 'completed' | 'failed';
  progress: number;
  stageLabel?: string | null;
  elapsedMs: number;
  fieldCount: number;
  processedCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  currentFieldLabel?: string | null;
  evidenceTitles: string[];
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
  outputPath?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GoalRecord {
  id: string;
  clientId: string;
  title: string;
  quarter: string;
  progress: number;
  ownerName: string;
}

export interface DnaTerm {
  id: string;
  clientId: string;
  category: string;
  canonicalName: string;
  aliases: string[];
  description: string;
  sourceLevel: DnaSourceLevel;
}

export interface EvidenceItem {
  id: string;
  title: string;
  excerpt: string;
  sourceType: string;
  documentId?: string | null;
  path?: string | null;
  score?: number | null;
  coverage?: number | null;
  sectionLabel?: string | null;
  retrievalStage?: 'master_index' | 'surrogate' | 'raw_chunk' | null;
  isFallback?: boolean;
  matchedTerms: string[];
}

export interface AiStructuredResponse {
  content: string;
  judgment: string;
  analysis: string;
  actions: string;
  timeline: string;
}

export type JudgmentQueryMode = 'registry_only' | 'hybrid' | 'evidence_based_synthesis';

export type EvidenceSupportMode =
  | 'none'
  | 'linked_state_evidence'
  | 'evidence_cards'
  | 'raw_doc_drilldown'
  | 'generic_retrieval_fallback';

export type WorkspaceAnswerIntent =
  | 'intro_profile'
  | 'project_intro'
  | 'meeting_summary'
  | 'next_actions'
  | 'official_judgment_registry'
  | 'evidence_question'
  | 'status_progress'
  | 'general';

export type RetrievalDecisionReason =
  | 'state_first_default'
  | 'document_drilldown_requested'
  | 'search_cache_requested'
  | 'intro_query_needs_evidence'
  | 'identity_query_needs_evidence'
  | 'project_intro_needs_evidence'
  | 'meeting_summary_needs_evidence'
  | 'next_actions_needs_evidence'
  | 'evidence_question_needs_evidence'
  | 'official_registry_requested'
  | 'status_progress_needs_hybrid_evidence'
  | 'default_hybrid_evidence'
  | 'state_pool_insufficient'
  | 'state_pool_empty';

export type FallbackPresentationMode = 'state_cards_only' | 'compact_user_answer' | 'full_answer';

export interface StateAnswerSections {
  official: string[];
  candidate: string[];
  draftFindings: string[];
  evidenceSupport: string[];
  actions: string[];
  risks: string[];
  unknowns: string[];
}

export interface StateSourceSummary {
  judgments: number;
  meetings: number;
  tasks: number;
  openQuestions: number;
  conflicts: number;
  documents: number;
}

export interface ChatMessage {
  id: string;
  threadId: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  status: 'success' | 'loading';
  modelRoute?: string | null;
  llmInvoked?: boolean;
  providerUsed?: string | null;
  answerMode?: 'grounded_answer' | 'grounded_fallback' | 'low_confidence_answer' | 'general_answer' | 'system_failure' | null;
  evidenceStatus?: 'sufficient' | 'partial' | 'none' | null;
  failureReason?: string | null;
  fallbackReason?: string | null;
  fallbackPresentationMode?: FallbackPresentationMode | null;
  stateConfidence?: 'low' | 'medium' | 'high' | null;
  stateSources?: string[];
  boundaryNotes?: string[];
  answerIntent?: WorkspaceAnswerIntent | null;
  retrievalDecisionReason?: RetrievalDecisionReason | null;
  judgmentQueryMode?: JudgmentQueryMode | null;
  evidenceSupportMode?: EvidenceSupportMode | null;
  stateAnswerSections?: StateAnswerSections | null;
  stateSourceSummary?: StateSourceSummary | null;
  timing?: Record<string, number>;
  retrievalSummary?: Record<string, unknown>;
  structuredData?: AiStructuredResponse | null;
  evidence: EvidenceItem[];
}

export interface ChatThread {
  id: string;
  clientId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatStartResponse {
  threadId: string;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
  analysisRun: ClientAnalysisRun;
}

export interface ChatThreadDetailResponse {
  thread: ChatThread;
  messages: ChatMessage[];
}

export interface WorkspaceStateItem {
  id: string;
  signalType: 'change' | 'progress' | 'risk' | 'question' | 'judgment' | 'meeting' | 'task' | 'noise';
  sourceType: string;
  sourceId: string;
  title: string;
  summary: string;
  authority: 'approved' | 'candidate' | 'informational' | 'warning';
  updatedAt?: string | null;
}

export interface WorkspaceStateProjection {
  changeItems: WorkspaceStateItem[];
  progressItems: WorkspaceStateItem[];
  signalNoiseFlags: string[];
  boundaryNotes: string[];
  stateConfidence: 'low' | 'medium' | 'high';
}

export interface StateQueryPlan {
  primaryIntent: 'overview' | 'changes' | 'progress' | 'risk' | 'questions' | 'judgment' | 'timeline';
  focusAreas: string[];
  needsBoundaryGuard: boolean;
}

export interface StateQueryHit {
  sourceType: string;
  sourceId: string;
  label: string;
  summary: string;
  signalKind: 'change' | 'progress' | 'risk' | 'question' | 'judgment' | 'timeline';
  authorityLevel: 'approved' | 'candidate' | 'informational' | 'warning';
}

export interface StateAnswerContextPack {
  plan: StateQueryPlan;
  summary: string;
  stateSources: string[];
  boundaryNotes: string[];
  stateConfidence: 'low' | 'medium' | 'high';
  hits: StateQueryHit[];
  sections: StateAnswerSections;
  sourceSummary: StateSourceSummary;
  candidateLeakageCount: number;
  fallbackReason?: string | null;
}

export interface AgendaItem {
  id: string;
  title: string;
  description: string;
}

export interface DecisionItem {
  id: string;
  summary: string;
}

export interface RiskItem {
  id: string;
  summary: string;
  severity: Priority;
}

export interface AmbiguityItem {
  id: string;
  rawText: string;
  candidates: string[];
  status: 'pending' | 'resolved';
}

export interface MeetingSummary {
  id: string;
  clientId: string;
  title: string;
  stage: MeetingStage;
  scheduledAt?: string | null;
  updatedAt: string;
}

export interface MeetingDetail extends MeetingSummary {
  transcriptText: string;
  notes: string;
  agendaItems: AgendaItem[];
  decisions: DecisionItem[];
  actionItems: Task[];
  risks: RiskItem[];
  ambiguities: AmbiguityItem[];
}

export interface FeishuMeetingLaunchResult {
  meeting: MeetingDetail;
  deliveryStatus: 'sent' | 'skipped' | 'failed';
  deliveryMessage: string;
  commandHint: string;
  noticeText: string;
  deliveryMode: 'bound_user' | 'configured_receiver' | 'none';
  deliveryTarget?: string | null;
}

export interface TaskList {
  id: string;
  name: string;
  color: string;
  sortOrder: number;
  isDefault: boolean;
  scope?: 'org' | 'personal';
  archivedAt?: string | null;
}

export interface TaskTag {
  id: string;
  name: string;
  color: string;
  scope: 'org' | 'self';
  ownerUserId?: string | null;
  createdBy?: string | null;
  updatedAt: string;
  archivedAt?: string | null;
}

export interface Task {
  id: string;
  title: string;
  desc: string;
  status: TaskStatus;
  creatorId?: string | null;
  creatorName?: string | null;
  priority: Priority;
  listId: string;
  listName: string;
  listColor: string;
  ddl: string;
  startDate?: string | null;
  dueDate?: string | null;
  durationMinutes?: number;
  scopeMode?: TaskScopeMode;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  ownerId?: string | null;
  ownerName: string;
  sourceType: string;
  sourceId?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  evidenceCount: number;
  tags: TaskTag[];
  note?: string | null;
  attachments: TaskAttachment[];
  collaborators: TaskCollaborator[];
  collaborationSummary: Record<string, number>;
  viewerInboxStatus?: CollaboratorInboxStatus | null;
  orgContext?: TaskOrgContext | null;
  projectContext?: TaskProjectContext | null;
  memoryHints?: string[];
  backgroundReadiness?: BackgroundReadiness | null;
  linkedFactsPreview?: MemoryFact[];
  syncStatus?: 'local' | 'syncing' | 'synced' | 'pending' | 'error' | null;
  createdAt: string;
  updatedAt: string;
}

export interface TaskAttachment {
  id: string;
  taskId: string;
  clientId: string;
  eventLineId?: string | null;
  documentId?: string | null;
  title: string;
  summary?: string | null;
  path: string;
  kind: string;
  source: string;
  sizeBytes: number;
  createdAt: string;
}

export type TaskAttachmentRecord = TaskAttachment;

export interface TaskOrgContext {
  departmentId?: string | null;
  roleTemplateId?: string | null;
  controlRuleId?: string | null;
  controlLevel?: OrgTaskControlLevel | null;
  organizationFocusKey?: string | null;
  departmentFocusKey?: string | null;
  focusItemId?: string | null;
  departmentPlanItemId?: string | null;
  isCrossDepartment: boolean;
  approvalState?: string | null;
  blockedAtStep?: string | null;
  needsReview: boolean;
}

export interface TaskProjectContext {
  clientId: string;
  clientName: string;
  stage?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectModuleSummary?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectFlowSummary?: string | null;
  backgroundSummary: string;
  goalSummary: string;
  riskSummary: string;
  currentFocus?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentProgress?: string | null;
  infoCompleteness: 'low' | 'medium' | 'high';
  sourceEvidence: string[];
}

export type EventLineKind = 'project_line' | 'issue_line' | 'coordination_line' | 'case_line' | 'custom';
export type EventLineStatus = 'active' | 'blocked' | 'paused' | 'done' | 'archived';
export type EventLineVisibilityScope = 'private' | 'project_public';

export interface EventLine {
  id: string;
  name: string;
  kind: EventLineKind;
  status: EventLineStatus;
  visibilityScope: EventLineVisibilityScope;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount: number;
  ownerId?: string | null;
  ownerName?: string | null;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
  primaryDepartmentId?: string | null;
  primaryDepartmentName?: string | null;
  participantIds: string[];
  closedAt?: string | null;
  closedByUserId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface EventLineActivity {
  id: string;
  eventLineId: string;
  sourceType: 'task_activity' | 'meeting' | 'support_request' | 'review' | 'attachment' | 'manual_note';
  sourceId: string;
  happenedAt: string;
  actorId?: string | null;
  actorName?: string | null;
  title: string;
  summary: string;
  metadata?: Record<string, unknown>;
  isKey?: boolean;
}

export interface EventLineDetail {
  eventLine: EventLine;
  tasks: Task[];
  activities: EventLineActivity[];
  memorySnapshot?: EventLineMemorySnapshot | null;
  predictionReadiness?: number | null;
  clarificationNeeds?: string[];
}

export interface TaskSmartBriefActionItem {
  text: string;
  sourceLabel: string;
  internalSuggestedOwner?: string;
  actionKind?: string;
  dueHint?: string;
  deliverable?: string;
  actionKey?: string;
  taskTitleSuggestion?: string;
  taskDescriptionSuggestion?: string;
}

export interface TaskSmartBrief {
  taskId: string;
  summary: string;
  summarySourceLabels: string[];
  actionItems: TaskSmartBriefActionItem[];
}

export interface PrepPackMaterial {
  sourceType: string;
  sourceId: string;
  title: string;
  summary: string;
  authorityLevel?: string;
}

export interface PrepPackCard {
  taskId: string;
  title: string;
  summary: string;
  materials: PrepPackMaterial[];
  openQuestions: string[];
  judgments: string[];
  risks: string[];
  boundaryNotes: string[];
  sourceLabels: string[];
  proposalId?: string | null;
}

export interface ProposalTargetRef {
  targetType: 'client' | 'task' | 'meeting' | 'event_line' | 'judgment';
  targetId: string;
  label: string;
}

export interface ProposalRecord {
  id: string;
  clientId: string;
  kind: 'task_prep' | 'meeting_prep' | 'meeting_followup';
  status: 'draft' | 'pending_review' | 'approved' | 'rejected' | 'execution_pending' | 'executed' | 'failed';
  riskLevel: 'low' | 'medium' | 'high';
  title: string;
  summary: string;
  rationale: string;
  targetRefs: ProposalTargetRef[];
  sourceRefs: string[];
  boundaryNotes: string[];
  payload: Record<string, unknown>;
  createdBy: string;
  decidedBy?: string | null;
  decidedAt?: string | null;
  rejectedReason?: string | null;
  executionTicketId?: string | null;
  executionTicket?: ExecutionTicket | null;
  createdAt: string;
  updatedAt: string;
}

export type ExecutionTicketResultType = 'recorded_only' | 'prep_artifact_ready' | 'followup_task_created' | 'failed';

export interface ExecutionTicketArtifactRef {
  artifactType: string;
  refId: string;
  title: string;
}

export interface ExecutionTicketResult {
  resultType: ExecutionTicketResultType;
  summary: string;
  createdTaskIds: string[];
  artifactRefs: ExecutionTicketArtifactRef[];
}

export interface ExecutionTicket {
  id: string;
  proposalId: string;
  clientId: string;
  executionType: string;
  status: 'pending' | 'running' | 'executed' | 'failed';
  payload: Record<string, unknown>;
  result: ExecutionTicketResult;
  errorMessage?: string | null;
  executedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProposalExecutionResponse {
  proposal: ProposalRecord;
  executionTicket?: ExecutionTicket | null;
}

export interface EventLineReportAttachment {
  id: string;
  taskId: string;
  title: string;
  kind: string;
  mimeType?: string | null;
  sizeBytes: number;
  downloadUrl: string;
  actorName?: string | null;
  createdAt: string;
}

export interface EventLineReportSnapshot {
  eventLine: EventLine;
  activities: EventLineActivity[];
  tasks: Task[];
  attachments: EventLineReportAttachment[];
  participantNames: string[];
  snapshotAt: string;
}

/** 事件线文档附件 — 为 PDF 汇报功能预留 */
export type EventLineAttachmentDisplayMode = 'expanded' | 'collapsed';

export interface EventLineAttachment {
  id: string;
  eventLineId: string;
  fileName: string;
  fileType: string;
  displayMode: EventLineAttachmentDisplayMode;
  description: string;
  uploadedBy: string;
  uploadedAt: string;
  /** 本地文件路径（不同步到云端） */
  localPath?: string | null;
  /** 票据/图片预览 URL */
  previewUrl?: string | null;
}

/** 事件线审批节点 */
export type EventLineApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface EventLineApprovalNode {
  id: string;
  eventLineId: string;
  title: string;
  requestedBy: string;
  approverName: string;
  status: EventLineApprovalStatus;
  note: string;
  createdAt: string;
  resolvedAt?: string | null;
}

export interface EventLineMutationPayload {
  name: string;
  kind?: EventLineKind;
  status?: EventLineStatus;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount?: number | null;
  ownerId?: string | null;
  primaryClientId?: string | null;
  primaryDepartmentId?: string | null;
  participantIds?: string[];
  syncLinkedTaskClientIds?: boolean;
}

export interface EventLineClarificationDraftPayload {
  conversationText: string;
}

export interface EventLineClarificationDraftResult {
  summary: string;
  stage: string;
  intent: string;
  currentBlocker: string;
  nextStep: string;
  recentDecision: string;
  missingInfo: string[];
  confidence: 'low' | 'medium' | 'high';
}

export interface ProjectModule {
  id: string;
  clientId: string;
  name: string;
  alias?: string | null;
  goal: string;
  description: string;
  ownerName?: string | null;
  deliverables: string[];
  keywords: string[];
  templateTasksJson?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectFlow {
  id: string;
  clientId: string;
  moduleId: string;
  moduleName?: string | null;
  name: string;
  description: string;
  scenario: string;
  triggerCondition: string;
  steps: string[];
  inputs: string[];
  outputs: string[];
  collaborators: string[];
  riskPoints: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ProjectStructureResponse {
  modules: ProjectModule[];
  flows: ProjectFlow[];
}

export interface ProjectModuleDetail extends ProjectModule {
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  flowIds: string[];
  flowNames: string[];
  contextSummary: string;
}

export interface ProjectFlowDetail extends ProjectFlow {
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  contextSummary: string;
}

export interface TaskCollaborator {
  userId: string;
  fullName: string;
  email: string;
  orderIndex: number;
  isOwner: boolean;
  inboxStatus: CollaboratorInboxStatus;
  returnReason?: string | null;
  handledAt?: string | null;
}

export interface TaskActivityRecord {
  id: string;
  taskId: string;
  actorId: string;
  actorName: string;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface WeeklyReview {
  id: string;
  userId: string;
  userName: string;
  weekLabel: string;
  workProgress?: string;
  workBlocker?: string;
  blockerType?: string;
  workDirection?: string;
  nextWeekFocus?: string;
  supportNeeded?: string;
  relatedPlanIds?: string[];
  workFreeNote?: string;
  personalGrowthNote?: string;
  personalPrivateNote?: string;
  personalVisibility?: 'self';
  submittedAt: string;
  createdAt: string;
  updatedAt: string;
}

export interface AgentWorklog {
  id: string;
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  date: string;
  weekLabel: string;
  title: string;
  summary: string;
  detailLines: string[];
  sourceType: 'activity_log' | 'topic_capture' | 'workspace_sync';
  createdAt: string;
}

export interface AgentWeeklyDigest {
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  weekLabel: string;
  summary: string;
  focusItems: string[];
  evidenceCount: number;
  sourcePolicy: Record<string, unknown>;
}

export interface AgentWeeklyPlanItem {
  id: string;
  title: string;
  rationale: string;
  scheduleHint: string;
  status: AgentPlanStatus;
}

export interface AgentWeeklyPlan {
  agentKey: AgentDepartmentKey;
  agentName: string;
  departmentName: string;
  color: string;
  weekLabel: string;
  summary: string;
  planItems: AgentWeeklyPlanItem[];
  sourcePolicy: Record<string, unknown>;
}

export interface AgentWorklogResponse {
  month: string;
  worklogs: AgentWorklog[];
  weeklyDigests: AgentWeeklyDigest[];
  weeklyPlans: AgentWeeklyPlan[];
}

export interface AgentWeeklyPlanItemPayload {
  title: string;
  rationale: string;
  scheduleHint: string;
  status: AgentPlanStatus;
}

export interface AgentWeeklyPlanPayload {
  weekLabel: string;
  agentKey: AgentDepartmentKey;
  summary: string;
  planItems: AgentWeeklyPlanItemPayload[];
}

export interface WeeklyReviewTaskSnapshot {
  title: string;
  status: TaskStatus;
  startDate?: string | null;
  dueDate?: string | null;
  createdAt: string;
  ownerId?: string | null;
  ownerName?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  tags: TaskTag[];
  listName: string;
  listColor: string;
  orgContext?: TaskOrgContext | null;
  projectContext?: TaskProjectContext | null;
  eventLineContext?: WeeklyReviewEventLineContext | null;
}

export interface WeeklyReviewEventLineContext {
  id?: string | null;
  name?: string | null;
  businessCategory?: string | null;
  stage?: string | null;
  summary?: string | null;
  intent?: string | null;
  currentBlocker?: string | null;
  recentDecision?: string | null;
  nextStep?: string | null;
  evidenceCount: number;
  primaryClientId?: string | null;
  primaryClientName?: string | null;
}

export interface WeeklyReviewTaskStructuredNote {
  reflection: string;
  lightweightTag: ReviewLightweightTag;
  planCommitment: string;
  progress: string;
  completionStatus: ReviewCompletionStatus;
  departmentPlanId?: string | null;
  departmentPlanAlignment: ReviewAlignmentStatus;
  organizationPlanId?: string | null;
  organizationPlanAlignment: ReviewAlignmentStatus;
  successReason: string;
  successExperience: string;
  blockerReason: string;
  failureInsight: string;
  supportNeeded: string;
  nextAction: string;
}

export interface ReviewMetricCard {
  key: 'timely_completion' | 'department_alignment' | 'strategy_alignment' | 'reflection_capture';
  label: string;
  valueText: string;
  numerator: number;
  denominator: number;
  rate: number;
  description: string;
  tone: 'positive' | 'neutral' | 'warning' | 'risk';
}

export interface WeeklyReviewTaskEntry {
  id: string;
  reviewId?: string | null;
  taskId: string;
  weekLabel: string;
  contentDomain: 'work' | 'personal';
  note: string;
  structuredNote: WeeklyReviewTaskStructuredNote;
  reviewedAt?: string | null;
  taskSnapshot: WeeklyReviewTaskSnapshot;
}

export interface ReviewEvidenceWeight {
  sourceType: 'user_note' | 'task_fact' | 'organization_dna' | 'team_plan' | 'focus_plan' | 'project_context' | 'external_context';
  label: string;
  weight: 'high' | 'medium' | 'low';
  rationale: string;
}

export interface ReviewHypothesis {
  id: string;
  lens: 'execution' | 'organization' | 'business' | 'team' | 'market' | 'growth';
  title: string;
  statement: string;
  confidence: 'high' | 'medium' | 'low';
  reason: string;
  relatedTaskIds: string[];
  evidenceSources: string[];
  assumptionNote: string;
}

export interface EventLineEvidenceSlot {
  key:
    | 'stage'
    | 'goal'
    | 'blocker'
    | 'next_action'
    | 'recent_change'
    | 'owner_chain'
    | 'recent_decision'
    | 'project_link';
  label: string;
  coverage: 'full' | 'partial' | 'missing';
  evidenceStrength: 'strong' | 'medium' | 'weak' | 'none';
  sourceTypes: Array<'event_line' | 'task_fact' | 'project_context' | 'user_note' | 'uploaded_doc' | 'manual_clarification'>;
  summary: string;
  recommendedFix: 'upload_docs' | 'clarify_now' | 'wait_for_more_trace';
}

export interface EventLineCompleteness {
  eventLineId: string;
  title: string;
  score: number;
  status: 'insufficient' | 'summary_ready' | 'forecast_ready' | 'high_confidence';
  missingSlots: string[];
  strongestSlots: string[];
  memoryConfidence?: number | null;
  backgroundSources?: string[];
  slots: EventLineEvidenceSlot[];
}

export interface ReviewDashboardEvidenceRef {
  sourceType: 'task' | 'meeting' | 'support_request' | 'attachment' | 'clarification' | 'event_line' | 'notebook' | 'event_line_memory';
  sourceId: string;
  title: string;
  summary?: string;
}

export interface ReviewDashboardCardTarget {
  targetType: 'event_line' | 'task_view' | 'meeting' | 'support_request' | 'attachment_group' | 'task';
  targetId: string;
  targetLabel?: string;
  targetFilters?: Record<string, unknown>;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineContextFact {
  sourceType: 'task' | 'meeting' | 'attachment' | 'support_request' | 'clarification' | 'notebook' | 'event_line_memory';
  sourceId: string;
  title: string;
  summary: string;
  happenedAt?: string | null;
}

export interface EventLineJudgment {
  eventLineId: string;
  title: string;
  viewerRole: 'employee' | 'department_lead' | 'admin';
  judgmentVersion: string;
  bundleFingerprint: string;
  coverageScore: number;
  confidenceScore: number;
  safeOutputMode: 'needs_input' | 'summary_only' | 'full_judgment';
  publishState: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  whatHappened: string;
  whyItMatters: string;
  coreBlocker: string;
  blockerType: 'business' | 'collaboration' | 'decision' | 'structure' | 'capacity' | 'evidence';
  evidenceSummary: string;
  managerImplication: string;
  nextWeekFocus: string;
  minimumAction: string;
  riskIfIgnored: string;
  opportunityIfAmplified: string;
  evidenceRefs: ReviewDashboardEvidenceRef[];
  target?: ReviewDashboardCardTarget | null;
}

export interface EventLineContextBundle {
  eventLineId: string;
  lineName: string;
  businessCategory: string;
  stage: string;
  summary: string;
  intent: string;
  currentWork: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  recentProgress: string;
  projectName: string;
  collaborationRelationship: string;
  organizationIntro: string;
  currentChallenges: string[];
  collaborationGoals: string[];
  keyPeople: string[];
  keyProducts: string[];
  recentFacts: string[];
  taskFacts: EventLineContextFact[];
  meetingFacts: EventLineContextFact[];
  attachmentFacts: EventLineContextFact[];
  clarificationFacts: EventLineContextFact[];
  evidenceRefs: ReviewDashboardEvidenceRef[];
  trendSignals: TrendSignal[];
  taskCount: number;
  meetingCount: number;
  attachmentCount: number;
  supportRequestCount: number;
  readiness: 'low' | 'medium' | 'high';
}

export interface EventLineSummaryCard {
  eventLineId: string;
  title: string;
  kind: 'project_line' | 'issue_line' | 'coordination_line' | 'case_line' | 'custom';
  status: 'active' | 'blocked' | 'paused' | 'done' | 'archived';
  projectName?: string | null;
  moduleName?: string | null;
  flowName?: string | null;
  whatThisLineIs: string;
  whatHappenedThisWeek: string;
  currentState: string;
  mainBlocker: string;
  nextCriticalMove: string;
  ownerNames: string[];
  completenessScore: number;
  predictionReadiness: 'not_ready' | 'summary_only' | 'conservative_forecast' | 'strong_forecast';
  missingSlots: string[];
  memoryConfidence?: number | null;
  backgroundSources?: string[];
  evidencePreview: string[];
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineRiskCard {
  eventLineId: string;
  title: string;
  riskType: 'schedule_drift' | 'collaboration_friction' | 'decision_lag' | 'goal_drift' | 'workflow_breakdown' | 'overload';
  statement: string;
  forecastWindow: '1w' | '2w' | '3w';
  probability: 'high' | 'medium' | 'low';
  impactScope: 'person' | 'team' | 'project' | 'org';
  triggerSignals: string[];
  whyNow: string;
  ifIgnored: string;
  suggestedAction: string;
  ownerRole: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface EventLineOpportunityCard {
  eventLineId: string;
  title: string;
  opportunityType: 'repeatable_pattern' | 'momentum_building' | 'process_upgrade' | 'capability_signal' | 'leverage_point';
  statement: string;
  forecastWindow: '1w' | '2w' | '3w';
  confidence: 'high' | 'medium' | 'low';
  upside: string;
  supportingSignals: string[];
  recommendedAmplifier: string;
  ownerRole: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface TrendSignal {
  key: string;
  title: string;
  statement: string;
  signalType:
    | 'repeat_reschedule'
    | 'repeat_review_pending'
    | 'repeat_support_request'
    | 'stalled_event_line'
    | 'escalating_blocker'
    | 'thin_evidence';
  severity: 'high' | 'medium' | 'low';
  windowLabel: string;
  relatedEventLineId?: string | null;
  relatedTaskIds: string[];
  evidenceRefs: ReviewDashboardEvidenceRef[];
  target?: ReviewDashboardCardTarget | null;
}

export interface WeeklyReviewAnalysis {
  scope: TaskReviewScope;
  emphasis: 'summary' | 'analysis';
  headline: string;
  caution: string;
  weeklyOverview: string;
  weeklyFocusLines: string[];
  weeklyNextFocus: string[];
  dnaModuleTitles: string[];
  metricCards: ReviewMetricCard[];
  evidenceWeights: ReviewEvidenceWeight[];
  confirmedFacts: string[];
  hypothesisHighlights: ReviewHypothesis[];
  nextWeekFocus: string[];
  eventLineSummaries: EventLineSummaryCard[];
  eventLineCompleteness: EventLineCompleteness[];
  eventLineContextBundles: EventLineContextBundle[];
  eventLineJudgments: EventLineJudgment[];
  riskCards: EventLineRiskCard[];
  opportunityCards: EventLineOpportunityCard[];
  trendSignals: TrendSignal[];
  narrativeAnalyses: NarrativeAnalysis[];
}

export interface TaskContextPreview {
  taskId: string;
  clientId?: string | null;
  clientName?: string | null;
  contextBundle: EventLineContextBundle;
  judgment: EventLineJudgment;
  judgmentVersion: string;
  bundleFingerprint: string;
  coverageScore: number;
  confidenceScore: number;
  safeOutputMode: 'needs_input' | 'summary_only' | 'full_judgment';
  publishState: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  summaryChips: string[];
  readiness: 'low' | 'medium' | 'high';
}

export interface PlanNode {
  id: string;
  level: 'ceo' | 'director' | 'manager' | 'project';
  title: string;
  summary: string;
  status: string;
  ownerUserId?: string | null;
  ownerName?: string | null;
  ownerUnitId?: string | null;
  startsAt?: string | null;
  endsAt?: string | null;
}

export interface ManagementSignalCard {
  id: string;
  reviewId: string;
  userId: string;
  userName: string;
  weekLabel: string;
  contentDomain: 'work';
  visibilityScope: 'team' | 'department' | 'org';
  eligibleForAggregation: boolean;
  eligibleForManagerRetrieval: boolean;
  signals: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface PersonalGrowthCard {
  id: string;
  reviewId: string;
  userId: string;
  contentDomain: 'personal';
  visibilityScope: 'self';
  summary: string;
  suggestions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ReviewActionCard {
  id: string;
  actionType: 'task' | 'support_request' | 'resource_request' | 'meeting' | 'one_on_one';
  title: string;
  payload: Record<string, unknown>;
  status: string;
  createdAt: string;
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  target?: ReviewDashboardCardTarget | null;
  evidenceRefs?: ReviewDashboardEvidenceRef[];
}

export interface ReviewActionExecutionResult {
  objectType: 'task' | 'support_request' | 'meeting';
  objectId: string;
  objectLabel: string;
  targetClientId?: string | null;
  targetClientName?: string | null;
  targetEventLineId?: string | null;
  targetEventLineName?: string | null;
  canOpen?: boolean;
  supportRequest?: SupportRequestRecord;
}

export interface HierarchyReport {
  id: string;
  scopeType: 'employee' | 'team' | 'org';
  scopeRefId: string;
  weekLabel: string;
  logicMode: string;
  judgmentVersion?: string | null;
  bundleFingerprint?: string | null;
  coverageScore?: number | null;
  confidenceScore?: number | null;
  safeOutputMode?: 'needs_input' | 'summary_only' | 'full_judgment' | null;
  headline: string;
  summary: string;
  summaryMetrics: ReviewMetricCard[];
  focusAreas: string[];
  supportSignals: string[];
  suggestedActions: string[];
  anonymousInsights: string[];
  sourcePolicy: Record<string, unknown>;
  actions: ReviewActionCard[];
  publishState?: 'local_preview' | 'publish_ready' | 'published_by_human' | 'published_by_robot' | 'stale';
  publishedAt?: string | null;
  publishedBy?: string | null;
  invalidatedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface TaskViewFilterSet {
  sourceTypes?: string[];
  businessCategories?: string[];
  eventLineIds?: string[];
  onlyRisky?: boolean;
  onlyWithEventLine?: boolean;
  needsReview?: boolean | null;
  minimumEvidenceCount?: number | null;
}

export interface TaskViewDefinition {
  id: string;
  name: string;
  kind: 'event_line' | 'risk' | 'source' | 'business_category' | 'custom';
  description: string;
  calendarScope: 'all' | 'event_line' | 'risk' | 'source' | 'business_category';
  shareability: 'private' | 'org';
  sortBy: 'updatedAt' | 'dueDate' | 'priority' | 'evidenceCount';
  sortDirection: 'asc' | 'desc';
  visibleFields: string[];
  filterSet: TaskViewFilterSet;
  builtIn: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TaskViewPreset {
  key: 'event_line' | 'risk' | 'source' | 'business_category';
  label: string;
  description: string;
  viewId: string;
}

export interface TaskViewsResponse {
  views: TaskViewDefinition[];
  presets: TaskViewPreset[];
}

export interface TaskViewMutationPayload {
  name: string;
  kind?: 'event_line' | 'risk' | 'source' | 'business_category' | 'custom';
  description?: string;
  calendarScope?: 'all' | 'event_line' | 'risk' | 'source' | 'business_category';
  shareability?: 'private' | 'org';
  sortBy?: 'updatedAt' | 'dueDate' | 'priority' | 'evidenceCount';
  sortDirection?: 'asc' | 'desc';
  visibleFields?: string[];
  filterSet?: TaskViewFilterSet;
}

export interface ReviewDashboardDrillTargetResponse {
  target: ReviewDashboardCardTarget;
  eventLineDetail?: EventLineDetail | null;
  eventLineMemory?: EventLineMemorySnapshot | null;
  tasks: Task[];
  meetings: MeetingSummary[];
  supportRequests: SupportRequestRecord[];
  attachments: TaskAttachmentRecord[];
}

export interface ReviewSimulationBundle {
  sampleSize: number;
  label: string;
  orgReport?: HierarchyReport | null;
  departmentReports: HierarchyReport[];
}

export interface ReviewDashboard {
  currentReview?: WeeklyReview | null;
  workItems: WeeklyReviewTaskEntry[];
  personalItems: WeeklyReviewTaskEntry[];
  workAnalysis?: WeeklyReviewAnalysis | null;
  personalAnalysis?: WeeklyReviewAnalysis | null;
  selfReport?: HierarchyReport | null;
  workSignalCard?: ManagementSignalCard | null;
  personalGrowthCard?: PersonalGrowthCard | null;
  teamReport?: HierarchyReport | null;
  orgReport?: HierarchyReport | null;
  executiveOrgReport?: HierarchyReport | null;
  departmentReports: HierarchyReport[];
  agentDepartmentDigests: AgentWeeklyDigest[];
  agentDepartmentPlans: AgentWeeklyPlan[];
  simulationBundle?: ReviewSimulationBundle | null;
  plans: PlanNode[];
}

// ── UnderstandingSnapshotV1: 统一理解输出对象 ──

export type UnderstandingMode = 'basic' | 'enhanced';

export interface UnderstandingSourceBreakdown {
  sourceType: 'org_dna' | 'client_background' | 'quarterly_focus' | 'task_title' | 'task_desc' | 'review_note' | 'event_line_memory' | 'meeting' | 'support_request' | 'calendar' | 'attachment';
  available: boolean;
  label: string;
}

export interface UnderstandingOptionalAdvice {
  realBlocker?: string | null;
  timeGate?: string | null;
  minimumAction?: string | null;
  supportAsk?: string | null;
}

export interface UnderstandingSnapshotV1 {
  taskId: string;
  mode: UnderstandingMode;
  coverage: number;
  confidence: number;
  whatIsThis: string;
  whyItMatters: string;
  progressNow: string;
  unknowns: string;
  knownFacts: string[];
  optionalAdvice?: UnderstandingOptionalAdvice | null;
  sourceBreakdown: UnderstandingSourceBreakdown[];
}

// ── Phase 1: 客户战略画像 + 合作关系 + 事件线周历史 ──

export type CooperationType = 'strategic_companion' | 'single_project' | 'exploring' | 'dormant';
export type RelationshipHealth = 'thriving' | 'steady' | 'cooling' | 'at_risk';

/** 客户战略画像 — 补充 ClientSummary 中缺失的深层信息 */
export interface ClientStrategicProfile {
  clientId: string;
  industry: string;
  scale: string;
  influence: string;
  currentNeeds: string;
  painPoints: string;
  strategicValueToYiyu: string;
  decisionChain: string;
  updatedAt: string;
}

/** 益语与客户的合作关系 */
export interface CooperationRelationship {
  id: string;
  clientId: string;
  clientName: string;
  whyConnected: string;
  meaningToYiyu: string;
  meaningToClient: string;
  cooperationType: CooperationType;
  relationshipHealth: RelationshipHealth;
  keyStakeholders: CooperationStakeholder[];
  milestones: string;
  startedAt: string;
  updatedAt: string;
}

export interface CooperationStakeholder {
  name: string;
  role: string;
  relationship: string;
}

/** 事件线周快照历史 — 每周复盘时自动归档 */
export interface EventLineWeeklySnapshot {
  id: string;
  eventLineId: string;
  eventLineName: string;
  weekLabel: string;
  stageAtThatTime: string;
  keyDecisions: string[];
  turningPoints: string[];
  blockersThen: string[];
  progressDelta: string;
  taskCount: number;
  completedCount: number;
  createdAt: string;
}

/** 五层上下文叙事分析 — LLM 生成 */
export interface NarrativeAnalysis {
  eventLineId: string;
  eventLineName: string;
  clientId?: string | null;
  clientName?: string | null;
  whatThisIs: string;
  whyImportant: string;
  currentProgress: string;
  missingUnderstanding: string;
  riskNote?: string | null;
  timeGate?: string | null;
  minimumAction?: string | null;
  managementAdvice?: string | null;
  contextLayersUsed: string[];
  confidenceLevel: 'low' | 'medium' | 'high';
}

export type StrategicJudgmentStatus = 'system_draft' | 'confirmed' | 'waiting';
export type StrategicHealthStatus = 'healthy' | 'watch' | 'risk' | 'uncalibrated';
export type StrategicLineMomentum = '加码' | '稳住' | '收口' | '暂停';
export type StrategicItemPriority = 'high' | 'medium' | 'low';

export interface StrategicPermission {
  canEdit: boolean;
  isCeo: boolean;
  leaderUserId?: string | null;
  notice?: string | null;
}

export interface StrategicReadiness {
  status: 'ready' | 'insufficient';
  score: number;
  summary: string;
  gaps: string[];
}

export interface StrategicJudgment {
  value: string;
  status: StrategicJudgmentStatus;
  sources: string[];
}

export interface StrategicHeadline {
  weekSummary: StrategicJudgment;
  mainContradiction: StrategicJudgment;
  coreBreakthrough: StrategicJudgment;
  focusItems: string[];
  focusStatus: StrategicJudgmentStatus;
  freshness: string;
}

export interface StrategicHealthLine {
  key: string;
  title: string;
  status: StrategicHealthStatus;
  trend: string;
  summary: string;
  evidence: string[];
}

export interface StrategicLine {
  id: string;
  title: string;
  summary: string;
  module?: string | null;
  flow?: string | null;
  stage?: string | null;
  blocker: string;
  decision: string;
  nextStep: string;
  momentum: StrategicLineMomentum;
  evidence: string[];
  memoryConfidence?: number | null;
  predictionReadiness?: number | null;
  clarificationNeeds?: string[];
}

export interface StrategicLineDetail extends StrategicLine {
  clientId: string;
  clientName: string;
  stageLabel: string;
  relatedTaskIds: string[];
  relatedTaskTitles: string[];
  contextSummary: string;
}

export interface StrategicChecklistItem {
  title: string;
  detail: string;
  source: string;
  priority: StrategicItemPriority;
}

export interface StrategicChecklistGroup {
  key: string;
  title: string;
  description: string;
  items: StrategicChecklistItem[];
}

export interface StrategicChangePoint {
  title: string;
  summary: string;
  confidence: string;
  signals: string[];
}

export interface StrategicEvidenceCard {
  label: string;
  value: string;
}

export interface StrategicEvidencePreview {
  summary: string;
  cards: StrategicEvidenceCard[];
  boundaries: string[];
  keyFacts: string[];
  keyWarnings: string[];
}

export interface StrategicAssetCandidate {
  title: string;
  source: string;
  summary: string;
  nextAction: string;
}

export interface StrategicMeetingPackDraft {
  title: string;
  agenda: string[];
  groups: StrategicChecklistGroup[];
}

export interface StrategicCockpitSnapshot {
  clientId: string;
  clientName: string;
  clientTagline: string;
  stageLabel: string;
  permission: StrategicPermission;
  readiness: StrategicReadiness;
  headline: StrategicHeadline;
  health: StrategicHealthLine[];
  strategicLines: StrategicLine[];
  twoWeekChanges: StrategicChangePoint[];
  pendingDecisions: StrategicChecklistItem[];
  pendingMaterials: StrategicChecklistItem[];
  meetingPackDraft: StrategicMeetingPackDraft;
  evidencePreview: StrategicEvidencePreview;
  assetCandidates: StrategicAssetCandidate[];
  officialLayer: Record<string, unknown>;
  radarLayer: Record<string, unknown>;
  officialLayerStatus: 'ready' | 'empty';
  officialEmptyReason?: string | null;
  resolutionTrace: Record<string, unknown>;
  notebookSummary?: OrganizationNotebookSnapshot | null;
  memoryStatus?: MemoryStatus | null;
  linkedEventLineMemories?: EventLineMemorySnapshot[];
}

export interface StrategicCockpitConfirmPayload {
  weekSummary: string;
  mainContradiction: string;
  coreBreakthrough: string;
  focusItems: string[];
}

export type StrategicThoughtScope = 'client' | 'system';
export type StrategicThoughtStatus = 'draft' | 'confirmed' | 'dismissed' | 'task_created' | 'waiting_evidence';
export type StrategicThoughtConfidenceLevel = 'low' | 'medium' | 'high' | 'none';

export type StrategicThoughtSourceType =
  | 'strategic_cockpit'
  | 'strategic_line'
  | 'headline'
  | 'pending_decision'
  | 'pending_material'
  | 'brain_dashboard'
  | 'judgment_version'
  | 'theme_cluster'
  | 'conflict_group'
  | 'open_question'
  | 'event_line'
  | 'meeting'
  | 'review'
  | 'knowledge'
  | 'system';

export interface StrategicThoughtSource {
  sourceType: StrategicThoughtSourceType;
  sourceId?: string | null;
  label: string;
  detail?: string | null;
}

export interface StrategicThoughtReview {
  thoughtId: string;
  status: StrategicThoughtStatus;
  note: string;
  taskId?: string | null;
  judgmentId?: string | null;
  reviewedAt?: string | null;
  reviewedBy?: string | null;
}

export interface StrategicThought {
  id: string;
  scope: StrategicThoughtScope;
  clientId?: string | null;
  clientName: string;
  line: string;
  observation: string;
  suggestion: string;
  confidence?: number | null;
  confidenceLevel: StrategicThoughtConfidenceLevel;
  status: StrategicThoughtStatus;
  isSystem: boolean;
  dueDateHint: string;
  tags: string[];
  sources: StrategicThoughtSource[];
  evidenceCount: number;
  generatedAt: string;
  staleReason?: string | null;
  evidenceLevel?: 'none' | 'weak' | 'medium' | 'strong' | null;
  reason?: string | null;
  review?: StrategicThoughtReview | null;
}

export interface StrategicThoughtsResponse {
  items: StrategicThought[];
  total: number;
  generatedAt: string;
  selectedClientId?: string | null;
  usingMockData?: boolean;
}

export interface StrategicThoughtReviewPayload {
  action: 'confirm' | 'dismiss' | 'mark_task_created';
  note?: string;
  taskId?: string | null;
  createJudgment?: boolean;
}

export interface ReviewHistoryEntry {
  weekLabel: string;
  submittedAt: string;
  workItemCount: number;
  personalItemCount: number;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryEntry[];
}

export interface TaskSettings {
  defaultListId?: string | null;
  defaultPriority: Priority;
  defaultDueDatePreset: TaskDueDatePreset;
  defaultViewMode: TaskViewPreference;
  listSortMode: TaskListSortMode;
  showCompletedTasks: boolean;
  defaultReviewScope: TaskReviewScope;
  autoAssignSelf: boolean;
  updatedAt: string;
}

export interface ReviewDepartmentMember {
  id: string;
  fullName: string;
  email?: string | null;
}

export interface ReviewDepartmentConfig {
  id: string;
  name: string;
  color: string;
  monthlyDna: string;
  weeklyFocus: string;
  leaders: ReviewDepartmentMember[];
  members: ReviewDepartmentMember[];
}

export interface ReviewGovernanceSettings {
  departments: ReviewDepartmentConfig[];
  updatedAt: string;
}

export interface OrganizationDnaModule {
  moduleKey: OrganizationDnaModuleKey;
  title: string;
  markdownContent: string;
  normalizedText: string;
  summary: string;
  fileName?: string | null;
  contentHash?: string | null;
  updatedAt?: string | null;
  updatedBy?: string | null;
  hasDocument: boolean;
  readinessStatus: 'ready' | 'missing';
  readinessAnsweredCount: number;
  readinessQuestionCount: number;
  readinessSource: 'client_dna' | 'manual_document' | 'auto_enqueued' | 'none';
  readinessSummary: string;
  readinessQuestions: DnaReadinessQuestion[];
}

export interface OrganizationDnaResponse {
  modules: OrganizationDnaModule[];
}

export interface DnaReadinessQuestion {
  question: string;
  answered: boolean;
  evidence?: string | null;
}

export interface ClientDnaModule {
  clientId: string;
  moduleKey: OrganizationDnaModuleKey;
  title: string;
  markdownContent: string;
  normalizedText: string;
  summary: string;
  fileName?: string | null;
  contentHash?: string | null;
  sourceKind: 'manual' | 'generated';
  missingInfo: string[];
  updatedAt?: string | null;
  updatedBy?: string | null;
  hasDocument: boolean;
}

export interface ClientDnaModulesResponse {
  modules: ClientDnaModule[];
}

export interface ClientDnaGeneratePayload {
  refreshGenerated?: boolean;
}

export interface ClientWorkspaceSettings {
  useOrgDnaInChat: boolean;
  useOrgDnaInKnowledgeQa: boolean;
  meetingPublishDefaultListId?: string | null;
  meetingPublishDefaultPriority: Priority;
  defaultGoalQuarter: string;
  defaultMeetingTitlePrefix: string;
  clientDnaModeLabel: string;
  updatedAt: string;
}

export interface TopicsSettings {
  chineseOnly: boolean;
  requireInsightBeforeActions: boolean;
  defaultTaskOwnerMode: TopicTaskOwnerMode;
  defaultTimeRange: string;
  defaultSourceStrategy: string;
  useOrgDnaForInsight: boolean;
  useOrgDnaForTaskPlan: boolean;
  updatedAt: string;
}

export interface DiagnosisProfileRecord {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  deepDnaId?: string | null;
  label: string;
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  corePreferences: string[];
  riskTriggers: string[];
  tonePreference?: string;
  updatedAt: string;
}

export interface OrganizationRiskDnaDocument {
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  coreRisks: string[];
  sensitiveScenarios: string[];
  tonePreference?: string;
  updatedAt: string;
}

export interface FundraisingKnowledgeDocument {
  id: string;
  title: string;
  fileName: string;
  filePath: string;
  markdownContent: string;
  summary: string;
  scenes: string[];
  tags: string[];
  principles: string[];
  riskSignals: string[];
  updatedAt: string;
}

export interface DeepDnaSourceRecord {
  id: string;
  kind: 'manual' | 'import' | 'web';
  title: string;
  excerpt: string;
  sourceUrl?: string | null;
  fileName?: string | null;
  filePath?: string | null;
  createdAt: string;
}

export interface DeepDnaRecord {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  status: 'draft' | 'published';
  sourceKind: 'manual' | 'import' | 'web';
  identitySummary: string;
  corePreferences: string[];
  supportTriggers: string[];
  redFlags: string[];
  evidencePreferences: string[];
  voiceStyle: string[];
  commonQuestions: string[];
  sources: DeepDnaSourceRecord[];
  confidenceScore: number;
  confidenceLevel: 'low' | 'medium' | 'high';
  authorizationStatus: 'public' | 'authorized_internal' | 'restricted';
  rawContent: string;
  searchQuery?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeepDnaDraft {
  id: string;
  groupKey: 'platform_fundraising' | 'monthly_donor' | 'key_person';
  label: string;
  searchQuery: string;
  draftRecord: DeepDnaRecord;
  previewSources: DeepDnaSourceRecord[];
  createdAt: string;
  updatedAt: string;
}

export interface CoachCaseRecord {
  id: string;
  title: string;
  summary: string;
  whyEffective: string;
  takeaways: string[];
  keyExcerpt: string;
  scenes: string[];
  tags: string[];
  issueTypes: string[];
  sourceType: 'system' | 'organization';
  sourceLabel: string;
  createdAt: string;
  updatedAt: string;
}

export interface CoachReminderRule {
  id: string;
  title: string;
  modeIds: string[];
  knowledgeKey: string;
  issuePattern: string;
  message: string;
  createdAt: string;
  updatedAt: string;
}

export interface OrgWritingNorm {
  id: string;
  title: string;
  description: string;
  instruction: string;
  modeIds: string[];
  triggerKeywords: string[];
  createdAt: string;
  updatedAt: string;
}

export interface CoachCardRecord {
  id: string;
  issueKey: string;
  insightTitle: string;
  issueWhat: string;
  whyImportant: string;
  knowledgePointTitle: string;
  knowledgePointBody: string;
  caseIds: string[];
  selfRewriteHint: string;
  learningAction: string;
  referenceDraft?: string | null;
}

export interface CoachPayload {
  cards: CoachCardRecord[];
  triggeredReminders: CoachReminderRule[];
  appliedNorms: OrgWritingNorm[];
}

export interface RunComparison {
  currentRunId: string;
  previousRunId?: string | null;
  resultChanges: string[];
  learningChanges: string[];
  resolvedIssues: string[];
  newIssues: string[];
  repeatedIssues: string[];
}

export interface AnalysisWorkbenchSettings {
  enabledTemplateIds: string[];
  defaultTemplateId?: string | null;
  defaultTitlePrefix: string;
  useOrgDna: boolean;
  allowEmployeeTemplateEditing: boolean;
  diagnosisProfiles: DiagnosisProfileRecord[];
  organizationRiskDna?: OrganizationRiskDnaDocument | null;
  fundraisingKnowledgeLibrary: FundraisingKnowledgeDocument[];
  deepDnaLibrary: DeepDnaRecord[];
  coachCaseLibrary: CoachCaseRecord[];
  coachReminderRules: CoachReminderRule[];
  orgWritingNorms: OrgWritingNorm[];
  updatedAt: string;
}

export interface HandbookSettings {
  defaultTags: string[];
  defaultCategory: string;
  allowTaskSource: boolean;
  allowAnalysisSource: boolean;
  visibilityBoundary: string;
  updatedAt: string;
}

export interface SystemAdminSettings {
  allowBusinessSettingsForEmployees: boolean;
  allowOrgDnaForEmployees: boolean;
  protectEmployeeAdmin: boolean;
  protectAiAndCloud: boolean;
  protectCloudSecurity: boolean;
  brandLogoDataUrl?: string | null;
  updatedAt: string;
}

export interface FeishuBotSettings {
  appId: string;
  receiveIdType: FeishuReceiveIdType;
  receiverId: string;
  botName: string;
  userBindingCallbackUrl: string;
  ready: boolean;
  hasAppSecret: boolean;
  secretSource: string;
  secretFingerprint?: string | null;
  lastConnectionStatus: 'idle' | 'success' | 'failed';
  lastConnectionMessage?: string | null;
  lastConnectedAt?: string | null;
  lastTestMessageAt?: string | null;
  updatedAt: string;
}

export interface FeishuUserBinding {
  linked: boolean;
  readyForAuthorization: boolean;
  appId: string;
  userId: string;
  openId?: string | null;
  unionId?: string | null;
  feishuUserId?: string | null;
  name?: string | null;
  enName?: string | null;
  avatarUrl?: string | null;
  email?: string | null;
  tenantKey?: string | null;
  boundAt?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
}

export interface FeishuUserBindingStartResult {
  authorizeUrl: string;
  state: string;
  expiresAt: string;
  callbackUrl: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
}

export interface OrgMembershipSummary {
  hasOrganization: boolean;
  organizationId?: string | null;
  organizationName?: string | null;
}

export interface OrgFeishuIntegrationAuditRecord {
  id: string;
  organizationId: string;
  actorUserId?: string | null;
  actorName?: string | null;
  appId: string;
  validationStatus: 'success' | 'failed';
  validationMessage: string;
  createdAt: string;
}

export interface OrgFeishuIntegration {
  organizationId?: string | null;
  organizationName?: string | null;
  appId: string;
  enabled: boolean;
  hasAppSecret: boolean;
  configuredBy?: string | null;
  configuredAt?: string | null;
  updatedAt: string;
  lastValidationStatus: 'idle' | 'success' | 'failed';
  lastValidationMessage?: string | null;
  recentAudits: OrgFeishuIntegrationAuditRecord[];
}

export interface OrgFeishuIntegrationPayload {
  appId?: string;
  appSecret?: string;
  clearAppSecret?: boolean;
}

export interface FeishuDeliveryProfile {
  userId: string;
  organizationId?: string | null;
  organizationName?: string | null;
  mobile: string;
  normalizedMobile?: string | null;
  deliveryStatus: 'missing_org' | 'integration_pending' | 'missing_mobile' | 'matched' | 'not_found' | 'failed';
  deliveryStatusLabel: string;
  readyForNotifications: boolean;
  receiveId?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
  blockedReason?: string | null;
}

export interface FeishuDeliveryProfilePayload {
  mobile?: string | null;
}

export interface FeishuMemberAuthorization {
  linked: boolean;
  readyForAuthorization: boolean;
  organizationId?: string | null;
  organizationName?: string | null;
  appId: string;
  userId: string;
  openId?: string | null;
  unionId?: string | null;
  feishuUserId?: string | null;
  name?: string | null;
  enName?: string | null;
  avatarUrl?: string | null;
  email?: string | null;
  tenantKey?: string | null;
  boundAt?: string | null;
  lastVerifiedAt?: string | null;
  lastError?: string | null;
  blockedReason?: string | null;
}

export interface FeishuMemberAuthorizationStartResult {
  authorizeUrl: string;
  state: string;
  expiresAt: string;
  callbackUrl: string;
  qrReady: boolean;
  qrBlockedReason?: string | null;
}

export interface TopicRadar {
  id: string;
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
  createdAt: string;
}

export interface TopicRadarPreferredSource {
  url: string;
  label: string;
}

export interface TopicCandidate {
  id: string;
  radarId: string;
  title: string;
  summary: string;
  source: string;
  sourceUrl?: string | null;
  publishedAt?: string | null;
  captureMethod: string;
  capturedBy?: string | null;
  status: TopicCandidateStatus;
  insightStatus: TopicCandidateInsightStatus;
  insightUpdatedAt?: string | null;
  createdAt: string;
}

export interface TopicCandidateInsight {
  candidateId: string;
  overview: string;
  keyPoints: string[];
  recommendationReasons: string[];
  practicalUses: string[];
  editorialNote: string;
  discussionPrompts: string[];
  createdAt: string;
  updatedAt: string;
}

export interface TopicCandidateChatMessage {
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export interface TopicCandidateChatPayload {
  question: string;
  history?: TopicCandidateChatMessage[];
}

export interface TopicCandidateChatResponse {
  candidateId: string;
  question: string;
  answer: string;
  generatedAt: string;
  message: TopicCandidateChatMessage;
}

export interface TopicCaptureRun {
  radarId: string;
  radarTitle: string;
  query: string;
  fetchedCount: number;
  createdCount: number;
  skippedCount: number;
  candidates: TopicCandidate[];
}

export interface TopicCaptureBatchResult {
  runs: TopicCaptureRun[];
  totalCreated: number;
  totalSkipped: number;
}

export interface TopicTaskSuggestion {
  title: string;
  desc: string;
  dueDate?: string | null;
  ddl: string;
  note: string;
  priority: Priority;
  tags: string[];
}

export interface TopicTaskPlanResult {
  candidateId: string;
  candidateTitle: string;
  candidateSummary: string;
  candidateSource: string;
  candidateSourceUrl?: string | null;
  overview: string;
  tasks: TopicTaskSuggestion[];
}

export interface TopicTaskPromotionDraft {
  title: string;
  desc: string;
  priority: Priority;
  listId: string;
  dueDate?: string | null;
  ddl: string;
  ownerId?: string | null;
  ownerName: string;
  collaboratorIds: string[];
  tagIds?: string[];
  tags: string[];
  note: string;
}

export interface TopicTaskPromotionResult {
  tasks: Task[];
  createdCount: number;
}

export interface AnalysisTemplate {
  id: string;
  title: string;
  description: string;
  templateKey: string;
}

export interface AnalysisRun {
  id: string;
  templateId: string;
  title: string;
  inputText: string;
  output: AiStructuredResponse;
  parentRunId?: string | null;
  coachPayload?: CoachPayload | null;
  createdAt: string;
  status: 'success' | 'failed';
}

export interface HandbookEntry {
  id: string;
  title: string;
  summary: string;
  tags: string[];
  sourceType: string;
  clientName?: string | null;
  clientId?: string | null;
  authorUserId?: string | null;
  authorUserName?: string | null;
  sourceObjectType?: string | null;
  sourceObjectId?: string | null;
  sourceTitle?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  abilityKeys: GrowthAbilityKey[];
  evidenceRefs: string[];
  contextSummary: string;
  reuseCount: number;
  lastReusedAt?: string | null;
  linkedContexts: GrowthContextLink[];
  createdAt: string;
}

export interface GrowthContextLink {
  objectType: string;
  objectId: string;
  label: string;
  subtitle: string;
  tab: string;
  statusLabel: string;
}

export interface HandbookEntryDetail extends HandbookEntry {
  relatedLedgerEntries: XpLedgerEntry[];
  originContexts: GrowthContextLink[];
  reuseHistory: HandbookReuseRecord[];
}

export interface HandbookReuseRecord {
  id: string;
  sourceType: string;
  sourceId: string;
  sourceLabel: string;
  note: string;
  contextSummary: string;
  gainedXp: number;
  createdAt: string;
  linkedContexts: GrowthContextLink[];
}

export interface XpLedgerEntry {
  id: string;
  userId: string;
  userName: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  evidenceId: string;
  xpType: GrowthEvidenceType;
  delta: number;
  baseXp: number;
  premiumRate: number;
  premiumXp: number;
  totalXp: number;
  reason: string;
  sourceType: string;
  sourceId: string;
  sourceTitle?: string | null;
  handbookEntryId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  reviewId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  businessCategory?: string | null;
  projectStage?: string | null;
  sourceRoute: string[];
  evidenceRefs: string[];
  contextSummary: string;
  strategicLink?: string | null;
  linkedContexts: GrowthContextLink[];
  contributionTags: GrowthContributionTag[];
  validationState: GrowthValidationState;
  orgContributionScore: number;
  weekLabel: string;
  createdAt: string;
  reversedAt?: string | null;
}

export interface GrowthAbilityScore {
  abilityKey: GrowthAbilityKey;
  label: string;
  currentScore: number;
  previousScore: number;
  totalXp: number;
  weeklyXp: number;
  stage: string;
  nextStage: string;
  evidence: string;
}

export interface GrowthRank {
  key: string;
  name: string;
  division?: string | null;
  fullLabel: string;
  progress: number;
  nextName?: string | null;
  xpToNext: number;
}

export interface LearningRecommendation {
  id: string;
  userId: string;
  userName: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  contentItemId: string;
  contentType: LearningContentType;
  title: string;
  summary: string;
  body: string;
  practiceTask: string;
  reason: string;
  linkedTaskId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  whyNow: string;
  linkedContexts: GrowthContextLink[];
  priority: 'high' | 'normal' | 'low';
  status: LearningRecommendationStatus;
  acceptedTaskId?: string | null;
  dismissedReason?: string | null;
  dedupeKey: string;
  createdAt: string;
  updatedAt: string;
}

export interface GrowthOverview {
  userId: string;
  userName: string;
  totalXp: number;
  weeklyXp: number;
  weeklyBaseXp: number;
  weeklyPremiumXp: number;
  level: number;
  stageLabel: string;
  xpToNext: number;
  rank: GrowthRank;
  abilities: GrowthAbilityScore[];
  recentEntries: XpLedgerEntry[];
  recommendations: LearningRecommendation[];
  sourceCoverage: GrowthSourceCoverage;
  projectGrowthHighlights: GrowthProjectHighlight[];
  eventLineGrowthHighlights: GrowthProjectHighlight[];
  strategicAlignmentHighlights: GrowthProjectHighlight[];
  pendingCaptures: GrowthPendingCapture[];
  currentFocusActions: GrowthFocusAction[];
  abilityGaps: GrowthAbilityGap[];
  updatedAt: string;
}

export interface GrowthSourceCoverage {
  taskSignals: number;
  meetingSignals: number;
  strategicSignals: number;
  reviewSignals: number;
  handbookSignals: number;
  clientCount: number;
  eventLineCount: number;
}

export interface GrowthProjectHighlight {
  id: string;
  label: string;
  type: string;
  weeklyXp: number;
  entryCount: number;
  summary: string;
  abilityKeys: GrowthAbilityKey[];
  contexts: GrowthContextLink[];
}

export interface GrowthPendingCapture {
  id: string;
  sourceType: string;
  sourceId: string;
  status: GrowthPendingCaptureState;
  title: string;
  summary: string;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  nextActionText: string;
  missingReasons: string[];
  abilityKeys: GrowthAbilityKey[];
  linkedContexts: GrowthContextLink[];
  stateReason: string;
  promotedHandbookEntryId?: string | null;
  updatedAt: string;
}

export interface GrowthFocusAction {
  id: string;
  title: string;
  summary: string;
  whyNow: string;
  linkedTaskId?: string | null;
  clientId?: string | null;
  clientName?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectStage?: string | null;
  triggerNode?: string | null;
  linkedContexts: GrowthContextLink[];
}

export interface GrowthAbilityGap {
  abilityKey: GrowthAbilityKey;
  label: string;
  currentScore: number;
  requiredScore: number;
  gap: number;
  reason: string;
  sourceLabel: string;
  sourceType: string;
  sourceId: string;
}

export interface GrowthTaskIntent {
  taskKind: string;
  goal: string;
  deliverable: string;
  riskTypes: string[];
  requiredAbilities: GrowthAbilityKey[];
  confidence: number;
  whyRelevant: string;
}

export interface GrowthUniversalSkillItem {
  id: string;
  cardType: '动作卡' | '检查卡' | '话术卡' | '模板卡';
  title: string;
  summary: string;
  whyRelevant: string;
  checklist: string[];
  talkTrack: string[];
  templateHint: string;
  sourceKind: 'rule' | 'project_context' | 'ai_supplement';
  expectedOutput: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthProjectContextPack {
  title: string;
  taskNotes: string[];
  attachments: string[];
  memoryHints: string[];
  linkedFacts: string[];
  clientSummary: string;
  recentMeetings: string[];
  eventLineSummary: string;
  strategicFocus: string[];
  keyWarnings: string[];
  contextGaps: string[];
}

export interface GrowthActionPlanItem {
  id: string;
  phaseGroup: 'before' | 'during' | 'after';
  title: string;
  purpose: string;
  expectedOutput: string;
  ifMissing: string;
  actionLabel: string;
  sourceKind: 'rule' | 'project_context' | 'ai_supplement';
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthMaterialRef {
  id: string;
  title: string;
  summary: string;
  sourceKind: 'task_material' | 'project_context' | 'client_workspace' | 'event_line' | 'strategic_focus' | 'rule' | 'ai_supplement';
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthWorkbenchStep {
  id: string;
  name: string;
  output: string;
  bottlenecks: string[];
}

export interface GrowthWorkbenchTask {
  id: string;
  title: string;
  project: string;
  clientName?: string | null;
  eventLineName?: string | null;
  deadline: string;
  urgency: string;
  urgencyColor: string;
  phase: string;
  risks: string[];
  nextAdvice: string;
  robotReady: boolean;
  robotReasons: string[];
  recommendationId?: string | null;
  linkedTaskId?: string | null;
  linkedContexts: GrowthContextLink[];
  xpReward: number;
  contextSummary: string;
  projectModuleName?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  sourceEvidence: string[];
  currentBlocker?: string | null;
  missingSignals: string[];
  hasBackground: boolean;
  hasDeadline: boolean;
  isCrossDepartment: boolean;
  needsReview: boolean;
  evidenceCount: number;
  pendingCollaborations: number;
  taskIntent: GrowthTaskIntent;
  universalSkills: GrowthUniversalSkillItem[];
  projectContextPack: GrowthProjectContextPack;
  actionPlan: GrowthActionPlanItem[];
  materialRefs: GrowthMaterialRef[];
}

export interface GrowthWorkbenchAction {
  id: string;
  title: string;
  output: string;
  scenario: string;
  actionLabel: string;
  supportTitle: string;
  detail: string;
  kind: 'schedule' | 'support' | 'process' | 'compose' | 'task';
  recommendationId?: string | null;
  linkedContext?: GrowthContextLink | null;
  seedTitle?: string | null;
  seedSummary?: string | null;
}

export interface GrowthWorkbenchMaterial {
  id: string;
  title: string;
  type: '流程说明' | '经验案例' | '模板工具';
  scenario: string;
  summary: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthLearningSummary {
  headline: string;
  whyItMatters: string;
  immediateMove: string;
  generator: 'rules' | 'ai';
  confidence: GrowthConfidence;
}

export interface GrowthGenericLesson {
  id: string;
  title: string;
  judgment: string;
  applicableScene: string;
  whyItWorks: string;
  reuseHint: string;
  linkedContext?: GrowthContextLink | null;
}

export interface GrowthProjectGuidance {
  id: string;
  title: string;
  judgment: string;
  whySpecial: string;
  guidanceType: 'project_specific' | 'stage_risk' | 'context_gap';
  linkedContexts: GrowthContextLink[];
  evidenceRefs: string[];
}

export interface GrowthReasoningInput {
  id: string;
  sourceType: 'task' | 'event_line' | 'client' | 'project_module' | 'project_flow' | 'focus_action' | 'pending_capture' | 'recommendation' | 'rule';
  label: string;
  detail: string;
}

export interface GrowthReasoningTrace {
  mode: 'rules_only' | 'ai_synthesized';
  usedInputs: GrowthReasoningInput[];
  evidenceRefs: string[];
  missingContext: string[];
  aiContribution: string[];
  modelLabel?: string | null;
  confidence: GrowthConfidence;
}

export interface GrowthRobotAssist {
  ready: boolean;
  canDelegate: string[];
  mustStayHuman: string[];
  why: string[];
}

export interface GrowthAfterActionCapture {
  title: string;
  summary: string;
  experienceType: string;
  recommendedWriteback: string;
}

export interface GrowthWorkbenchSupportCopy {
  title: string;
  intro: string;
  bullets: string[];
}

export interface GrowthWorkbenchSnapshot {
  tasks: GrowthWorkbenchTask[];
  activeTaskId?: string | null;
  learningSummary: GrowthLearningSummary;
  genericLessons: GrowthGenericLesson[];
  projectGuidance: GrowthProjectGuidance[];
  reasoningTrace: GrowthReasoningTrace;
  robotAssist: GrowthRobotAssist;
  afterActionCapture: GrowthAfterActionCapture;
  processSteps: GrowthWorkbenchStep[];
  activeProcessId?: string | null;
  actionsBefore: GrowthWorkbenchAction[];
  actionsDuring: GrowthWorkbenchAction[];
  actionsAfter: GrowthWorkbenchAction[];
  supportMaterials: GrowthWorkbenchMaterial[];
  checklistItems: string[];
  supportCopy: GrowthWorkbenchSupportCopy;
  robotPlan: string[];
  sourceMode: 'task' | 'growth_seed' | 'empty';
  scopeMode?: 'global' | 'strategic';
  scopeClientId?: string | null;
  scopeClientName?: string | null;
  updatedAt: string;
}

export interface GrowthLedgerResponse {
  entries: XpLedgerEntry[];
}

export interface GrowthRecommendationDismissPayload {
  reason?: string;
}

export interface GrowthRecommendationActionResponse {
  recommendation: LearningRecommendation;
  task?: Task | null;
}

export interface BadgeActionLink {
  label: string;
  tab: string;
}

export interface BadgeEvidence {
  id: string;
  title: string;
  sourceType: string;
  sourceId: string;
  subtitle: string;
  occurredAt: string;
}

export interface BadgeProgress {
  id: string;
  code: string;
  name: string;
  categoryId: string;
  categoryLabel: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  roles: string[];
  xp: number;
  iconMotif: string;
  description: string;
  whyItMatters: string;
  systemHowText: string;
  state: BadgeState;
  progressValue: number;
  progressTarget: number;
  progressPercent: number;
  progressText: string;
  nextActionText: string;
  actionLinks: BadgeActionLink[];
  evidence: BadgeEvidence[];
  linkedContexts: GrowthContextLink[];
  missingSignals: string[];
  unlockedAt?: string | null;
  masteryLevel: number;
  historical: boolean;
}

export interface BadgeCategory {
  id: string;
  label: string;
  abilityKey: GrowthAbilityKey;
  abilityLabel: string;
  litCount: number;
  totalCount: number;
  badges: BadgeProgress[];
}

export interface BadgeBoardOverview {
  totalBadges: number;
  litBadges: number;
  readyBadges: number;
  inProgressBadges: number;
  monthlyNewBadges: number;
  totalXp: number;
  upcomingBadgeIds: string[];
}

export interface BadgeBoard {
  overview: BadgeBoardOverview;
  categories: BadgeCategory[];
  updatedAt: string;
}

export interface GrowthValidationPayload {
  note?: string;
  sourceType?: string;
  sourceId?: string | null;
  sourceLabel?: string;
  contextSummary?: string;
  linkedContexts?: GrowthContextLink[];
}

export interface GrowthPendingCaptureActionPayload {
  status: GrowthPendingCaptureState;
  reason?: string;
  handbookEntryId?: string | null;
}

export interface GrowthPendingCaptureActionResponse {
  capture: GrowthPendingCapture;
}

export interface GrowthValidationActionResponse {
  entryId: string;
  eventType: 'handbook_reused';
  gainedXp: number;
  createdEntries: number;
  validationState: GrowthValidationState;
  duplicate: boolean;
  sourceId: string;
  createdAt: string;
}

export interface ClientAnalysisEvidenceSummary {
  summaryText: string;
  masterHitCount: number;
  surrogateHitCount: number;
  rawChunkHitCount: number;
  drillthroughUsed: boolean;
  coveredCategories: string[];
  missingCategories: string[];
  evidenceList: KnowledgeSearchHit[];
}

export interface ClientAnalysisRun {
  id: string;
  clientId: string;
  threadId: string;
  userMessageId: string;
  assistantMessageId: string;
  question: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
  phase: 'queued' | 'retrieving' | 'evidence_ready' | 'generating_long_answer' | 'generating_summary' | 'completed' | 'failed' | 'canceled';
  progress: number;
  progressFloor: number;
  progressCeiling: number;
  stageLabel?: string | null;
  elapsedMs: number;
  evidenceSummary: ClientAnalysisEvidenceSummary;
  longAnswerStatus: 'pending' | 'ready' | 'fallback' | 'failed';
  summaryStatus: 'pending' | 'ready' | 'fallback' | 'failed';
  longAnswer?: string | null;
  structuredSummary?: AiStructuredResponse | null;
  answerMode?: 'grounded_answer' | 'grounded_fallback' | 'low_confidence_answer' | 'general_answer' | 'system_failure' | null;
  llmInvoked: boolean;
  providerUsed?: string | null;
  failureReason?: string | null;
  timing: Record<string, number>;
  assistantMessage?: ChatMessage | null;
  createdAt: string;
  updatedAt: string;
}

export interface AnalysisJobCreatePayload {
  jobType: AnalysisJobType;
  clientId: string;
  scopeType?: AnalysisScopeType;
  scopeId: string;
  priority?: Priority;
  triggerType?: string;
  intentProfile?: AnalysisIntentProfile;
  question?: string;
  sourceScope?: Record<string, string[]>;
  featureFlags?: Record<string, boolean>;
}

export interface AnalysisJob {
  id: string;
  jobType: AnalysisJobType;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  status: AnalysisJobStatus;
  priority: Priority;
  triggerType: string;
  intentProfile: AnalysisIntentProfile;
  question: string;
  sourceSnapshot: string;
  sourceSnapshotHash: string;
  dedupeKey: string;
  featureFlags: Record<string, boolean>;
  progress: number;
  stageLabel?: string | null;
  runLogId?: string | null;
  error?: string | null;
  lockedBy?: string | null;
  lockedAt?: string | null;
  lockExpiresAt?: string | null;
  attemptCount: number;
  lastError?: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
}

export interface AnalysisJobStageRun {
  id: string;
  jobId: string;
  stageName: string;
  status: AnalysisStageStatus;
  provider?: string | null;
  modelName?: string | null;
  lane: AnalysisLane;
  cacheKey?: string | null;
  cacheHit: boolean;
  degraded: boolean;
  evidenceCount: number;
  topicCount: number;
  conflictCount: number;
  contextTimeRange?: string | null;
  metrics: Record<string, number | string>;
  detail?: string | null;
  correlationId?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RuntimeRunLog {
  id: string;
  clientId: string;
  jobId?: string | null;
  analysisJobId?: string | null;
  stageRunId?: string | null;
  contextPackId?: string | null;
  judgmentVersionId?: string | null;
  correlationId?: string | null;
  provider?: string | null;
  model?: string | null;
  lane: AnalysisLane;
  cacheHit: boolean;
  degraded: boolean;
  documentCount: number;
  evidenceCount: number;
  conflictCount: number;
  contextTimeRange?: string | null;
  promptVersion?: string | null;
  schemaVersion?: string | null;
  summary: string;
  detail: Record<string, unknown>;
  createdAt: string;
}

export interface ThemeCluster {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  themeKey: string;
  title: string;
  supportIds: string[];
  opposeIds: string[];
  gapSummary: string;
  latestChangeSummary: string;
  evidenceCount: number;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface ConflictGroup {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  conflictType: string;
  title: string;
  summary: string;
  evidenceIds: string[];
  unresolvedQuestionIds: string[];
  resolutionStatus: AnalysisReviewState;
  severity: 'low' | 'medium' | 'high';
  createdAt: string;
  updatedAt: string;
}

export interface OpenQuestion {
  id: string;
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  themeKey: string;
  question: string;
  reason: string;
  blockerLevel: 'low' | 'medium' | 'high';
  status: AnalysisReviewState;
  createdAt: string;
  updatedAt: string;
}

export interface ContextPack {
  id: string;
  clientId: string;
  jobId?: string | null;
  targetType: AnalysisScopeType;
  targetId: string;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  promptVersion: string;
  sourceCount: number;
  evidenceCount: number;
  payload: Record<string, unknown>;
  staleAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DnaDelta {
  id: string;
  clientId: string;
  dimension: string;
  previousVersion?: string | null;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  proposedChange: string;
  summary: string;
  evidenceIds: string[];
  confidence: GrowthConfidence;
  status: AnalysisReviewState;
  contextPackId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DnaDeltaCreatePayload {
  clientId: string;
  dimension: string;
  proposedChange: string;
  summary?: string;
  evidenceIds?: string[];
  confidence?: GrowthConfidence;
  contextPackId?: string | null;
}

export interface JudgmentVersion {
  id: string;
  clientId: string;
  targetType: AnalysisScopeType;
  targetId: string;
  topic: string;
  version: number;
  status: AnalysisReviewState;
  originType: AnalysisOriginType;
  authorityLevel: AnalysisAuthorityLevel;
  qualityTier: AnalysisQualityTier;
  supersedesId?: string | null;
  sourceSnapshotHash: string;
  staleReason?: AnalysisStaleReason | null;
  invalidatedBy?: string | null;
  summary: string;
  evidenceIds: string[];
  contextPackId?: string | null;
  riskLevel: 'low' | 'medium' | 'high';
  confidence: GrowthConfidence;
  createdAt: string;
  updatedAt: string;
}

export interface JudgmentConfirmPayload {
  judgmentId: string;
  action: ApprovalDecision;
  note?: string;
}

export interface ApprovalDecisionPayload {
  targetType: ApprovalTargetType;
  targetId: string;
  decision: ApprovalDecision;
  comment?: string;
  policyType?: string;
  metadata?: Record<string, unknown>;
}

export interface ApprovalRecord {
  id: string;
  approvalTargetType: ApprovalTargetType;
  approvalTargetId: string;
  clientId: string;
  policyType: string;
  decision: ApprovalDecision;
  comment: string;
  decidedBy: string;
  decidedAt: string;
  metadata: Record<string, unknown>;
}

export interface ApprovalState {
  targetType: ApprovalTargetType;
  targetId: string;
  currentDecision?: ApprovalDecision | null;
  currentStatus?: AnalysisReviewState | null;
  lastApproval?: ApprovalRecord | null;
}

export interface ResolutionScope {
  scopeType: AnalysisScopeType;
  scopeId: string;
}

export interface ResolutionCandidate {
  objectId?: string | null;
  topic?: string | null;
  scopeType: AnalysisScopeType;
  scopeId: string;
  originType?: AnalysisOriginType | null;
  authorityLevel?: AnalysisAuthorityLevel | null;
  qualityTier?: AnalysisQualityTier | null;
  staleReason?: AnalysisStaleReason | null;
  status?: AnalysisReviewState | null;
  rejectedReason?: AnalysisRejectedReason | null;
}

export interface ResolutionTrace {
  selectedCandidate?: ResolutionCandidate | null;
  consideredCandidates: ResolutionCandidate[];
  requestedScope: ResolutionScope;
  resolvedScope?: ResolutionScope | null;
  writebackScope: ResolutionScope;
  fallbackUsed: boolean;
  fallbackReason?: string | null;
}

export interface JudgmentBundle {
  baselineJudgment?: JudgmentVersion | null;
  overlayDeltas: JudgmentVersion[];
  resolutionTrace: ResolutionTrace;
}

export interface AnalysisMigrationMetrics {
  windowDays: number;
  newObjectHitRate: number;
  fallbackRate: number;
  approvalBacklog: number;
  approvalLagHoursMedian: number;
  candidateReviewWarningCount: number;
  candidateReviewOverdueCount: number;
  newCandidateUnreviewed24h: number;
  candidateToApprovedConversionRate: number;
  staleApprovedJudgmentCount: number;
  resolverMismatchRate: number;
  pageBreakdown: Record<string, AnalysisMigrationMetricBucket>;
}

export interface AnalysisMigrationMetricBucket {
  newObjectHitRate: number;
  fallbackRate: number;
  resolverMismatchRate: number;
  totalRuns: number;
}

export interface AnalysisWorkerCounterSnapshot {
  claimCounts: Record<string, number>;
  lockContention: Record<string, number>;
  backfillThrottle: Record<string, number>;
}

export interface MainChainCanaryObservation {
  recordedAt: string;
  timeRange: string;
  clientCount: number;
  enqueuedJobs: number;
  completedJobs: number;
  failedJobs: number;
  newObjectHitRateBefore: number;
  newObjectHitRateAfter: number;
  fallbackRateBefore: number;
  fallbackRateAfter: number;
  resolverMismatchRateBefore: number;
  resolverMismatchRateAfter: number;
  approvalBacklog: number;
  approvalLagHoursMedian: number;
  claimCounts: Record<string, number>;
  lockContention: Record<string, number>;
  backfillThrottle: Record<string, number>;
  impactedRealtimeTasks: boolean;
  latestJudgmentsShadowOff: boolean;
  verdict: 'pass' | 'watch' | 'fail';
  conclusion: string;
}

export interface MainChainCanaryObservationPayload {
  timeRange?: string | null;
  clientCount?: number | null;
  enqueuedJobs?: number | null;
  completedJobs?: number | null;
  failedJobs?: number | null;
  newObjectHitRateBefore?: number | null;
  newObjectHitRateAfter?: number | null;
  fallbackRateBefore?: number | null;
  fallbackRateAfter?: number | null;
  resolverMismatchRateBefore?: number | null;
  resolverMismatchRateAfter?: number | null;
  approvalBacklog?: number | null;
  approvalLagHoursMedian?: number | null;
  claimCounts?: Record<string, number> | null;
  lockContention?: Record<string, number> | null;
  backfillThrottle?: Record<string, number> | null;
  impactedRealtimeTasks?: boolean | null;
  latestJudgmentsShadowOff?: boolean | null;
  verdict?: 'pass' | 'watch' | 'fail' | null;
  conclusion?: string | null;
}

export interface MainChainStabilitySettings {
  latestJudgmentsShadowOff: boolean;
  backfillPaused: boolean;
  workerCounters: AnalysisWorkerCounterSnapshot;
  lastCanaryObservation?: MainChainCanaryObservation | null;
  updatedAt: string;
}

export interface MainChainStabilitySettingsPayload {
  latestJudgmentsShadowOff?: boolean | null;
  backfillPaused?: boolean | null;
  lastCanaryObservation?: MainChainCanaryObservationPayload | null;
}

export interface AnalysisCenterSummary {
  clientId: string;
  evidenceCardCount: number;
  themeClusterCount: number;
  conflictGroupCount: number;
  openQuestionCount: number;
  draftJudgmentCount: number;
  approvedJudgmentCount: number;
  analysisJobCount: number;
  latestJobStatus?: AnalysisJobStatus | null;
  latestJobLabel?: string | null;
  latestContextPackUpdatedAt?: string | null;
  latestRunLogId?: string | null;
  latestRunSummary?: string | null;
}

export interface ClientWorkspace {
  client: ClientSummary;
  folders: ClientFolder[];
  documents: DocumentRecord[];
  documentCards: DocumentCard[];
  imports: ImportRecord[];
  knowledgeStatus?: KnowledgeStatus | null;
  knowledgeJobs: KnowledgeJob[];
  recentReclassEvents: FileReclassEvent[];
  surrogateCount: number;
  memoryDocCount: number;
  threads: ChatThread[];
  recentMessages: ChatMessage[];
  analysisRuns: ClientAnalysisRun[];
  meetings: MeetingSummary[];
  goals: GoalRecord[];
  dnaModules: ClientDnaModule[];
  projectModules: ProjectModule[];
  projectFlows: ProjectFlow[];
  dnaTerms: DnaTerm[];
  relatedTasks: Task[];
  notebookSummary?: OrganizationNotebookSnapshot | null;
  memoryStatus?: MemoryStatus | null;
  analysisCenter?: AnalysisCenterSummary | null;
  latestContextPack?: ContextPack | null;
  judgmentBundle?: JudgmentBundle | null;
  latestResolutionTrace?: ResolutionTrace | null;
  latestJudgments: JudgmentVersion[];
  latestTopics: ThemeCluster[];
  latestConflicts: ConflictGroup[];
  latestOpenQuestions: OpenQuestion[];
  latestRunLogs: RuntimeRunLog[];
  stateProjection?: WorkspaceStateProjection | null;
}

export interface AnalysisBackfillMainChainJob {
  clientId: string;
  scopeType: AnalysisScopeType;
  scopeId: string;
  jobType: AnalysisJobType;
  triggerType: string;
  intentProfile: AnalysisIntentProfile;
}

export interface AnalysisBackfillMainChainPayload {
  clientIds?: string[];
  dryRun?: boolean;
  batchSize?: number;
  maxJobs?: number;
  pauseRequested?: boolean;
}

export interface AnalysisBackfillMainChainResult {
  dryRun: boolean;
  pauseRequested: boolean;
  paused: boolean;
  scannedClients: number;
  queuedJobs: number;
  skippedJobs: number;
  candidates: AnalysisBackfillMainChainJob[];
}

export interface FileReclassEvent {
  id: string;
  knowledgeDocumentId: string;
  fromPath: string;
  toPath: string;
  fromCategory?: string | null;
  toCategory: string;
  reason: string;
  confidence: number;
  createdAt: string;
}

export interface KnowledgeJob {
  id: string;
  clientId: string;
  jobType: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  totalItems: number;
  processedItems: number;
  lastError?: string | null;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  updatedAt: string;
}

export interface KnowledgeSearchHit {
  title: string;
  excerpt: string;
  score?: number | null;
  stage: 'master_index' | 'surrogate' | 'raw_chunk';
  path?: string | null;
  sectionLabel?: string | null;
  matchedTerms: string[];
}

export interface KnowledgeSearchResult {
  searchId: string;
  clientId: string;
  query: string;
  coverage: number;
  matchedTerms: string[];
  masterHitCount: number;
  surrogateHitCount: number;
  rawChunkHitCount: number;
  drillthroughUsed: boolean;
  strategicMode?: boolean;
  categoryCoverage?: string[];
  preferredCategories?: string[];
  phase?: 'retrieving' | 'grounding' | 'generating' | 'completed' | 'failed';
  progress?: number;
  progressFloor?: number;
  progressCeiling?: number;
  stageLabel?: string | null;
  lastUpdatedAt?: string | null;
  failureReason?: string | null;
  hits: KnowledgeSearchHit[];
  previewSummary?: string | null;
}

export interface KnowledgeMemoryRecord {
  id: string;
  clientId: string;
  sourceType: string;
  title: string;
  folderCategory: string;
  surrogateMdPath: string;
  createdAt: string;
  updatedAt: string;
}

export interface SettingsPayload {
  currentOperatorId?: string;
  aiProvider?: AiProvider;
  aiModel?: string;
  apiKey?: string;
  clearApiKey?: boolean;
}

export interface LegacyScanReport {
  path: string;
  found: string[];
  entries: Array<{
    path: string;
    kind: string;
    importable: boolean;
  }>;
  message: string;
}

export interface DemoDataReport {
  loaded: boolean;
  clients: number;
  documents: number;
  tasks: number;
  topics: number;
  handbookEntries: number;
}

export interface ClientMutationPayload {
  name: string;
  alias: string;
  domain: string;
  type: string;
  intro: string;
  stage: string;
  color?: string;
}

export interface TaskMutationPayload {
  title: string;
  desc: string;
  priority: Priority;
  listId: string;
  startDate?: string | null;
  dueDate?: string | null;
  durationMinutes?: number;
  scopeMode?: TaskScopeMode;
  clientId?: string | null;
  eventLineId?: string | null;
  projectModuleId?: string | null;
  projectFlowId?: string | null;
  ddl: string;
  ownerId?: string | null;
  ownerName: string;
  collaboratorIds: string[];
  tagIds: string[];
  tags?: string[];
  sourceType?: string;
  sourceId?: string | null;
  businessCategory?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  recentDecision?: string | null;
  evidenceCount?: number | null;
}

export interface AuthRegisterPayload {
  email: string;
  fullName: string;
  password: string;
  departmentId?: string | null;
  jobTitle?: string | null;
  managerName?: string | null;
  currentFocus?: string | null;
  isDepartmentLead?: boolean;
}

export interface AuthLoginPayload {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RememberedCloudAuthAccount {
  email: string;
  fullName: string;
  password: string;
  updatedAt: string;
}

export interface LocalInputMemoryCloudAuth {
  rememberInputs: boolean;
  lastEmail?: string | null;
  accounts: RememberedCloudAuthAccount[];
}

export interface LocalInputMemoryAiSettings {
  rememberApiKey: boolean;
  apiKey: string;
}

export interface LocalInputMemoryFeishuIntegration {
  rememberInputs: boolean;
  appId: string;
  callbackMode: string;
  customCallbackUrl: string;
  appSecret: string;
}

export interface LocalInputMemory {
  cloudAuth: LocalInputMemoryCloudAuth;
  aiSettings: LocalInputMemoryAiSettings;
  feishuIntegration: LocalInputMemoryFeishuIntegration;
}

export interface SaveCloudAuthInputMemoryPayload {
  rememberInputs: boolean;
  email: string;
  fullName?: string | null;
  password?: string | null;
}

export interface SaveAiInputMemoryPayload {
  rememberApiKey: boolean;
  apiKey?: string | null;
}

export interface SaveFeishuInputMemoryPayload {
  rememberInputs: boolean;
  appId?: string | null;
  callbackMode?: string | null;
  customCallbackUrl?: string | null;
  appSecret?: string | null;
}

export interface EmployeeRolePayload {
  role: EmployeeRole;
}

export interface EmployeeDepartmentPayload {
  departmentId?: string | null;
}

export interface EmployeeRejectPayload {
  reason: string;
}

export interface ChangePasswordPayload {
  currentPassword: string;
  newPassword: string;
}

export interface UpdateProfilePayload {
  fullName?: string;
  email?: string;
}

export interface AdminResetPasswordPayload {
  newPassword: string;
}

export interface TaskTagSuggestionPayload {
  title: string;
  desc: string;
  collaboratorNames: string[];
  dueDate?: string | null;
  module: string;
}

export interface TaskTagMutationPayload {
  name: string;
  color?: string;
  scope: 'org' | 'self';
  archived?: boolean;
}

export interface TaskListMutationPayload {
  name: string;
  color: string;
  isDefault?: boolean;
  scope?: 'org' | 'personal';
  archived?: boolean;
  sortOrder?: number;
}

export interface TaskSettingsPayload {
  defaultListId?: string | null;
  defaultPriority?: Priority;
  defaultDueDatePreset?: TaskDueDatePreset;
  defaultViewMode?: TaskViewPreference;
  listSortMode?: TaskListSortMode;
  showCompletedTasks?: boolean;
  defaultReviewScope?: TaskReviewScope;
  autoAssignSelf?: boolean;
}

export interface ReviewGovernanceSettingsPayload {
  departments: ReviewDepartmentConfig[];
}

export interface OrganizationDnaUploadPayload {
  filePath?: string;
  markdownContent?: string;
  fileName?: string;
}

export interface ProjectModulePayload {
  name: string;
  alias?: string | null;
  goal?: string | null;
  description?: string | null;
  ownerName?: string | null;
  deliverables?: string[];
  keywords?: string[];
  templateTasksJson?: string | null;
}

export interface ProjectFlowPayload {
  moduleId: string;
  name: string;
  description?: string | null;
  scenario?: string | null;
  triggerCondition?: string | null;
  steps?: string[];
  inputs?: string[];
  outputs?: string[];
  collaborators?: string[];
  riskPoints?: string[];
}

export interface ClientWorkspaceSettingsPayload {
  useOrgDnaInChat?: boolean;
  useOrgDnaInKnowledgeQa?: boolean;
  meetingPublishDefaultListId?: string | null;
  meetingPublishDefaultPriority?: Priority;
  defaultGoalQuarter?: string;
  defaultMeetingTitlePrefix?: string;
  clientDnaModeLabel?: string;
}

export interface TopicsSettingsPayload {
  chineseOnly?: boolean;
  requireInsightBeforeActions?: boolean;
  defaultTaskOwnerMode?: TopicTaskOwnerMode;
  defaultTimeRange?: string;
  defaultSourceStrategy?: string;
  useOrgDnaForInsight?: boolean;
  useOrgDnaForTaskPlan?: boolean;
}

export interface AnalysisWorkbenchSettingsPayload {
  enabledTemplateIds?: string[];
  defaultTemplateId?: string | null;
  defaultTitlePrefix?: string;
  useOrgDna?: boolean;
  allowEmployeeTemplateEditing?: boolean;
  diagnosisProfiles?: DiagnosisProfileRecord[];
  organizationRiskDna?: OrganizationRiskDnaDocument | null;
  fundraisingKnowledgeLibrary?: FundraisingKnowledgeDocument[];
  deepDnaLibrary?: DeepDnaRecord[];
  coachCaseLibrary?: CoachCaseRecord[];
  coachReminderRules?: CoachReminderRule[];
  orgWritingNorms?: OrgWritingNorm[];
}

export interface HandbookSettingsPayload {
  defaultTags?: string[];
  defaultCategory?: string;
  allowTaskSource?: boolean;
  allowAnalysisSource?: boolean;
  visibilityBoundary?: string;
}

export interface SystemAdminSettingsPayload {
  allowBusinessSettingsForEmployees?: boolean;
  allowOrgDnaForEmployees?: boolean;
  protectEmployeeAdmin?: boolean;
  protectAiAndCloud?: boolean;
  protectCloudSecurity?: boolean;
  brandLogoDataUrl?: string | null;
}

export interface FeishuBotSettingsPayload {
  appId?: string;
  receiveIdType?: FeishuReceiveIdType;
  receiverId?: string;
  botName?: string;
  userBindingCallbackUrl?: string;
  appSecret?: string;
  clearAppSecret?: boolean;
  sendTestMessage?: boolean;
  testMessage?: string;
}

export interface WeeklyReviewPayload {
  weekLabel: string;
  taskEntries: Array<{
    taskId: string;
    contentDomain: 'work' | 'personal';
    note: string;
    structuredNote?: WeeklyReviewTaskStructuredNote;
  }>;
  workProgress?: string;
  workBlocker?: string;
  blockerType?: string;
  workDirection?: string;
  nextWeekFocus?: string;
  supportNeeded?: string;
  relatedPlanIds?: string[];
  workFreeNote?: string;
  personalGrowthNote?: string;
  personalPrivateNote?: string;
}

export interface TopicRadarPayload {
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
}

export interface MeetingPipelineResult {
  meeting: MeetingDetail;
  message: string;
}

export interface TopicCandidatePayload {
  radarId: string;
  title: string;
  summary: string;
  source: string;
}

export interface HandbookEntryPayload {
  title: string;
  summary: string;
  tags: string[];
  sourceType: string;
  clientId?: string | null;
  sourceObjectType?: string | null;
  sourceObjectId?: string | null;
  sourceTitle?: string | null;
  eventLineId?: string | null;
  eventLineName?: string | null;
  projectModuleId?: string | null;
  projectModuleName?: string | null;
  projectFlowId?: string | null;
  projectFlowName?: string | null;
  projectStage?: string | null;
  businessCategory?: string | null;
  abilityKeys?: GrowthAbilityKey[];
  evidenceRefs?: string[];
  contextSummary?: string;
}

export interface AnalysisRunPayload {
  templateId: string;
  title: string;
  inputText: string;
  parentRunId?: string | null;
}

export type DiagnosisScene = 'fundraising' | 'pr' | 'project';
export type DiagnosisAudienceType = 'donor' | 'media' | 'public' | 'key_person' | 'beneficiary' | 'partner';
export type DiagnosisEngineMode = 'fast' | 'standard' | 'deep';

export interface DiagnosisContextReference {
  title: string;
  summary: string;
}

export interface ExternalDiagnosisRequest {
  scene: DiagnosisScene;
  audienceType: DiagnosisAudienceType;
  title: string;
  content: string;
  workspaceLabel?: string;
  modeLabel?: string;
  focusPoints?: string[];
  organizationContext?: {
    name?: string;
    mission?: string;
    projectType?: string;
    sensitivePoints?: string[];
  };
  dnaSummary?: {
    corePreferences?: string[];
    riskTriggers?: string[];
    tonePreference?: string;
  };
  knowledgeRefs?: DiagnosisContextReference[];
  caseRefs?: DiagnosisContextReference[];
  analysisOptions?: {
    engineMode: DiagnosisEngineMode;
    needEmotion?: boolean;
    needRiskPoints?: boolean;
    needMisunderstanding?: boolean;
    needSimulation?: boolean;
  };
}

export interface DiagnosisEngineHealth {
  engineKey: 'bettafish' | 'mirofish';
  enabled: boolean;
  reachable: boolean;
  status: 'healthy' | 'disabled' | 'not_configured' | 'not_installed' | 'unreachable' | 'error';
  detail: string;
  baseUrl: string;
  latencyMs?: number | null;
}

export interface BettaFishSignal {
  engineKey: 'bettafish';
  emotion: string;
  credibility: string;
  riskPoints: string[];
  misunderstandingPoints: string[];
  generatedAt: string;
  mode: DiagnosisEngineMode;
}

export interface DesktopAppInfo {
  appVersion: string;
  isPackaged: boolean;
  platform: string;
  arch: string;
  appBundlePath: string;
  executablePath: string;
  releasePlanPath: string;
  releaseArtifactsPath: string;
  updateChannel: 'stable' | 'beta';
  updaterPhase: 'planning' | 'preparing_release' | 'ready_for_feed' | 'ready_for_in_app_update';
  recommendedInstallPath: string;
  installStatus: 'ok' | 'warning';
  installWarning: string | null;
  detectedAppPaths: string[];
  legacyAppPaths: string[];
}

export type CollabChangeGroupKey =
  | 'shared_settings'
  | 'renderer'
  | 'desktop_shell'
  | 'local_backend'
  | 'cloud_backend'
  | 'scripts_docs'
  | 'other';

export type CollabFileChangeType = 'modified' | 'added' | 'deleted' | 'renamed' | 'untracked';

export type CollabConflictRiskKind = 'overlap' | 'unmerged' | 'binary' | 'rename' | 'delete_replace';

export interface CollabConflictRisk {
  kind: CollabConflictRiskKind;
  message: string;
}

export interface CollabFileChange {
  path: string;
  previousPath?: string | null;
  type: CollabFileChangeType;
  groupKey: CollabChangeGroupKey;
  groupLabel: string;
  summary: string;
  risk?: CollabConflictRisk | null;
}

export interface CollabChangeGroup {
  key: CollabChangeGroupKey;
  label: string;
  fileCount: number;
}

export type CollabEffectVisibility = 'visible' | 'mixed' | 'background';

export interface CollabEffectPreview {
  id: string;
  title: string;
  summary: string;
  visibility: CollabEffectVisibility;
  scopeLabel: string;
  details: string[];
  relatedPaths: string[];
  beforeLabel?: string | null;
  afterLabel?: string | null;
  beforeImageDataUrl?: string | null;
  afterImageDataUrl?: string | null;
}

export interface CollabRepoStatus {
  repoPath: string | null;
  repoName: string | null;
  suggestedRepoPath?: string | null;
  workingRepoPath?: string | null;
  workingBranch?: string | null;
  workingChangeCount?: number;
  isConfigured: boolean;
  isValid: boolean;
  branch: string | null;
  isMainBranch: boolean;
  hasLocalChanges: boolean;
  hasUnmergedPaths: boolean;
  aheadCount: number;
  behindCount: number;
  localChangeCount: number;
  remoteChangeCount: number;
  statusText: string;
}

export interface PushPreview {
  status: CollabRepoStatus;
  suggestedMessage: string;
  effects: CollabEffectPreview[];
  groups: CollabChangeGroup[];
  files: CollabFileChange[];
  notice?: string | null;
  executionBlockReason?: string | null;
}

export interface PullPreview {
  status: CollabRepoStatus;
  suggestedMessage: string;
  commitSummaries: string[];
  effects: CollabEffectPreview[];
  groups: CollabChangeGroup[];
  files: CollabFileChange[];
  notice?: string | null;
  executionBlockReason?: string | null;
}

export interface CommitAndPushToMainPayload {
  repoPath: string;
  selectedPaths: string[];
  confirmedRiskPaths: string[];
  message: string;
}

export interface PullSelectedFromMainPayload {
  repoPath: string;
  selectedPaths: string[];
  confirmedRiskPaths: string[];
  message: string;
}

export interface CollabActionResult {
  status: CollabRepoStatus;
  changedPaths: string[];
  createdCommit: boolean;
  commitMessage?: string | null;
}

declare global {
  interface Window {
    __YIYU_TEST_DIALOGS__?: {
      selectFiles?: () => Promise<string[]>;
      selectFolder?: () => Promise<string | null>;
      selectCollabRepo?: () => Promise<string | null>;
      openPath?: (targetPath: string) => Promise<boolean>;
      revealInFinder?: (targetPath: string) => Promise<boolean>;
      saveFileAs?: (sourcePath: string, suggestedName?: string) => Promise<string | null>;
    };
    yiyuWorkbench: {
      backendBaseUrl: string;
      getDesktopAppInfo(): Promise<DesktopAppInfo>;
      selectFiles(): Promise<string[]>;
      selectFolder(): Promise<string | null>;
      selectCollabRepo(): Promise<string | null>;
      getCollabRepoStatus(repoPath?: string | null): Promise<CollabRepoStatus>;
      previewPushToMain(repoPath: string): Promise<PushPreview>;
      commitAndPushToMain(payload: CommitAndPushToMainPayload): Promise<CollabActionResult>;
      previewPullFromMain(repoPath: string): Promise<PullPreview>;
      pullSelectedFromMain(payload: PullSelectedFromMainPayload): Promise<CollabActionResult>;
      rebuildAndInstallFromRepo(repoPath: string): Promise<boolean>;
      getDroppedFilePath(file: File): string | null;
      readTextFile(targetPath: string): Promise<string>;
      openPath(targetPath: string): Promise<boolean>;
      openExternalUrl(targetUrl: string): Promise<boolean>;
      revealInFinder(targetPath: string): Promise<boolean>;
      saveFileAs(sourcePath: string, suggestedName?: string): Promise<string | null>;
    };
  }
}
~~~

## `tailwind.config.cjs`

- 编码: `utf-8`

~~~javascript
const typography = require('@tailwindcss/typography');

module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"PingFang SC"', '"SF Pro Display"', '"Helvetica Neue"', 'sans-serif'],
      },
      boxShadow: {
        airy: '0 8px 30px rgba(91,123,254,0.12)',
      },
      colors: {
        airy: {
          blue: '#5B7BFE',
        },
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideInFromBottom: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        zoomIn95: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 240ms ease-out both',
        'slide-in-from-bottom-4': 'slideInFromBottom 280ms ease-out both',
        'zoom-in-95': 'zoomIn95 220ms ease-out both',
      },
    },
  },
  plugins: [typography],
};
~~~

## `tsconfig.json`

- 编码: `utf-8`

~~~json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src/renderer", "src/shared"]
}

~~~

## `tsconfig.node.json`

- 编码: `utf-8`

~~~json
{
  "compilerOptions": {
    "composite": true,
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "allowSyntheticDefaultImports": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "strict": true,
    "target": "ES2022",
    "types": ["node", "electron"],
    "rootDir": "src",
    "outDir": "build",
    "resolveJsonModule": true
  },
  "include": ["src/main", "src/shared"]
}
~~~

## `vite.config.ts`

- 编码: `utf-8`

~~~typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 4173
  }
});
~~~

