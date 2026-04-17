import React, { useState, useRef } from 'react';
import { X, GripVertical, Plus, Trash2, ChevronDown, ArrowUp, ArrowDown, ClipboardPaste, User, UploadCloud, Paperclip, Users, Check } from 'lucide-react';
import type { MentionCandidate } from '../../../src/shared/types';

export interface TemplateTask {
  id: string;
  title: string;
  description: string;
  /** Days after previous step completes (step 1 defaults to 0) */
  daysAfterPrevious: number;
  /** Duration in days (0.5 step: 0.5, 1, 1.5, 2...) */
  durationDays: number;
  priority: 'low' | 'normal' | 'high';
  ownerId?: string;
  ownerName?: string;
  collaboratorIds?: string[];
  collaboratorNames?: string[];
  attachments?: { name: string; size?: number }[];
  // Legacy compat
  relativeDays?: number;
  durationMinutes?: number;
}

export interface TemplateData {
  name: string;
  scenarioDesc: string;
  tasks: TemplateTask[];
  options?: {
    autoCreateEventLine: boolean;
    aiFillEmpty: boolean;
  };
}

interface Props {
  mode: 'create' | 'edit';
  initialData: TemplateData | null;
  memberOptions?: MentionCandidate[];
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
      const descText = descLines.join('\n');
      const daysAfterMatch = descText.match(/(?:上一步后|上个任务后|前一步后|延后|等待)\s*(\d+)\s*天/);
      const durationMatch = descText.match(/(?:耗时|持续|预计用时|预计耗时)\s*(\d+(?:\.\d+)?)\s*天/);
      tasks.push({
        id: Date.now().toString() + Math.random().toString(36).slice(2, 6),
        title,
        description: descText,
        daysAfterPrevious: daysAfterMatch ? parseInt(daysAfterMatch[1], 10) || 0 : 0,
        durationDays: durationMatch ? parseFloat(durationMatch[1]) || 1 : 1,
        priority: 'normal',
      });
    }
  }
  return tasks;
}

export function TaskTemplateEditorModal({ mode, initialData, memberOptions = [], onClose, onSave }: Props) {
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);
  const memberCandidates = memberOptions.length > 0
    ? memberOptions
    : ['顾源源', '佳乐', '乐乐', '大周', '庆华', '花花', '罗茜茜'].map((fullName, index) => ({
      id: `fallback-${index}`,
      fullName,
      email: '',
      primaryRole: 'employee' as const,
      isSelf: false,
    }));

  const [templateName, setTemplateName] = useState(initialData?.name || '');
  const [scenarioDesc, setScenarioDesc] = useState(initialData?.scenarioDesc || '');
  const [tasks, setTasks] = useState<TemplateTask[]>(() => {
    // Migrate legacy data
    return (initialData?.tasks || []).map((t) => ({
      ...t,
      daysAfterPrevious: t.daysAfterPrevious ?? t.relativeDays ?? 0,
      durationDays: t.durationDays ?? (t.durationMinutes ? t.durationMinutes / 1440 : 1),
      collaboratorIds: t.collaboratorIds || [],
      collaboratorNames: t.collaboratorNames || [],
    }));
  });
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [assigningOwnerTaskId, setAssigningOwnerTaskId] = useState<string | null>(null);
  const [assigningCollaboratorTaskId, setAssigningCollaboratorTaskId] = useState<string | null>(null);

  const handleAddTask = () => {
    setTasks([...tasks, {
      id: Date.now().toString(),
      title: '',
      description: '',
      daysAfterPrevious: 0,
      durationDays: 1,
      priority: 'normal',
      collaboratorIds: [],
      collaboratorNames: [],
    }]);
  };

  const handleDeleteTask = (id: string) => {
    setTasks(tasks.filter((t) => t.id !== id));
  };

  const updateTask = (id: string, field: keyof TemplateTask, value: unknown) => {
    setTasks(tasks.map((t) => (t.id === id ? { ...t, [field]: value } : t)));
  };

  const toggleTaskCollaborator = (taskId: string, candidate: MentionCandidate) => {
    setTasks((prev) => prev.map((task) => {
      if (task.id !== taskId) return task;
      const currentIds = task.collaboratorIds || [];
      const current = task.collaboratorNames || [];
      const selected = currentIds.includes(candidate.id);
      return {
        ...task,
        collaboratorIds: selected
          ? currentIds.filter((item) => item !== candidate.id)
          : [...currentIds, candidate.id],
        collaboratorNames: selected
          ? current.filter((item) => item !== candidate.fullName)
          : [...current, candidate.fullName],
      };
    }));
  };

  const removeTaskCollaborator = (taskId: string, identifier: string) => {
    setTasks((prev) => prev.map((task) => (
      task.id === taskId
        ? {
          ...task,
          collaboratorIds: (task.collaboratorIds || []).filter((item) => item !== identifier),
          collaboratorNames: (task.collaboratorNames || []).filter((_, index) => (task.collaboratorIds || [])[index] !== identifier),
        }
        : task
    )));
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
      options: { autoCreateEventLine: false, aiFillEmpty: false },
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
            {mode === 'edit' ? '编辑任务组模板' : '新建任务组模板'}
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
                placeholder="例如：新客户启动任务组"
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
              <span className="px-3">预设任务步骤</span>
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
                          <span className="text-xs font-semibold text-gray-400 mt-2.5 w-12 shrink-0">步骤 {index + 1}</span>
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
                            onClick={() => {
                              setAssigningOwnerTaskId(assigningOwnerTaskId === task.id ? null : task.id);
                              setAssigningCollaboratorTaskId(null);
                            }}
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
                          {assigningOwnerTaskId === task.id && (
                            <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1 max-h-[200px] overflow-y-auto">
                              <button
                                type="button"
                                className="w-full text-left px-3 py-1.5 text-[12px] text-gray-400 hover:bg-gray-50"
                                onClick={() => {
                                  setTasks((prev) => prev.map((item) => item.id === task.id ? {
                                    ...item,
                                    ownerId: '',
                                    ownerName: '',
                                  } : item));
                                  setAssigningOwnerTaskId(null);
                                }}
                              >
                                不指派
                              </button>
                              {memberCandidates.map((candidate) => (
                                <button
                                  key={candidate.id}
                                  type="button"
                                  className={`w-full text-left px-3 py-1.5 text-[12px] hover:bg-blue-50 ${task.ownerId === candidate.id ? 'text-blue-600 font-bold' : 'text-gray-700'}`}
                                  onClick={() => {
                                    setTasks((prev) => prev.map((item) => item.id === task.id ? {
                                      ...item,
                                      ownerId: candidate.id,
                                      ownerName: candidate.fullName,
                                    } : item));
                                    setAssigningOwnerTaskId(null);
                                  }}
                                >
                                  {candidate.fullName}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => {
                              setAssigningCollaboratorTaskId(assigningCollaboratorTaskId === task.id ? null : task.id);
                              setAssigningOwnerTaskId(null);
                            }}
                            className={`flex items-center gap-1 px-2 py-1.5 rounded border text-[12px] transition ${
                              (task.collaboratorNames || []).length > 0
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                : 'border-gray-300 text-gray-400 hover:border-emerald-400 hover:text-emerald-600'
                            }`}
                            title={(task.collaboratorNames || []).join('、') || '选择协作者'}
                          >
                            <Users className="w-3.5 h-3.5" />
                            <span className="max-w-[72px] truncate">
                              {(task.collaboratorNames || []).length > 0 ? `协作 ${task.collaboratorNames?.length}` : '协作者'}
                            </span>
                          </button>
                          {assigningCollaboratorTaskId === task.id && (
                            <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1 max-h-[220px] overflow-y-auto">
                              {memberCandidates.map((candidate) => {
                                const selected = (task.collaboratorIds || []).includes(candidate.id);
                                return (
                                  <button
                                    key={`${task.id}-${candidate.id}`}
                                    type="button"
                                    className={`flex w-full items-center justify-between px-3 py-1.5 text-[12px] hover:bg-emerald-50 ${selected ? 'text-emerald-700 font-bold' : 'text-gray-700'}`}
                                    onClick={() => toggleTaskCollaborator(task.id, candidate)}
                                  >
                                    <span>{candidate.fullName}</span>
                                    {selected ? <Check className="h-3.5 w-3.5" /> : null}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex gap-2 items-start pl-[56px]">
                        <textarea
                          value={task.description}
                          onChange={(e) => updateTask(task.id, 'description', e.target.value)}
                          placeholder="步骤说明（选填）"
                          className="flex-1 px-3 py-1.5 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 text-sm min-h-[60px]"
                        />
                      </div>

                      {/* Attachments + upload */}
                      <div className="flex items-center gap-2 pl-[56px] flex-wrap">
                        {(task.collaboratorNames || []).map((name, index) => (
                          <button
                            key={`${task.id}-collab-${(task.collaboratorIds || [])[index] || name}`}
                            type="button"
                            onClick={() => removeTaskCollaborator(task.id, (task.collaboratorIds || [])[index] || name)}
                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700 transition hover:bg-emerald-100"
                            title={`移除协作者 ${name}`}
                          >
                            <Users className="w-2.5 h-2.5" />
                            <span className="truncate max-w-[120px]">{name}</span>
                            <span className="text-[10px]">×</span>
                          </button>
                        ))}
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
                          <label className="text-xs text-gray-500 mr-2">{index === 0 ? '从起始时间后' : '上一步后'}</label>
                          <input
                            type="number"
                            value={task.daysAfterPrevious}
                            onChange={(e) => updateTask(task.id, 'daysAfterPrevious', parseInt(e.target.value) || 0)}
                            className="w-14 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                            min="0"
                          />
                          <span className="ml-1 text-xs text-gray-400">天开始</span>
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
                              <option value="low">低</option>
                              <option value="normal">普通</option>
                              <option value="high">高</option>
                            </select>
                            <ChevronDown className="w-3 h-3 absolute right-2 top-2 text-gray-500 pointer-events-none" />
                          </div>
                        </div>
                      </div>
                      <div className="pl-[56px]">
                        <p className="text-[11px] text-gray-400 leading-5">
                          1 天按 24 小时计算，所以 1.5 天会排成 36 小时。
                        </p>
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
                添加一步
              </button>
              <button
                onClick={() => setShowPasteModal(true)}
                className="py-2.5 px-4 border-2 border-dashed border-gray-300 rounded-lg text-sm font-medium text-gray-500 hover:border-blue-500 hover:text-blue-600 transition-colors flex items-center justify-center"
              >
                <ClipboardPaste className="w-4 h-4 mr-1" />
                粘贴批量步骤
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-between items-center rounded-b-xl">
          <span className="text-[12px] text-gray-400">{tasks.length} 个预设步骤</span>
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
              这里走的是规则解析，不需要 AI。系统会按“第 X 步”拆分步骤；如果正文里写了“上一步后 2 天”“耗时 1.5 天”，也会一并识别。
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
                预览：识别到 {parseBulkText(pasteText).length} 个步骤
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
                解析并添加 {parseBulkText(pasteText).length} 个步骤
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
