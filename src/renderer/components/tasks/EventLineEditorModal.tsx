import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Briefcase,
  CalendarClock,
  ChevronDown,
  FileBadge,
  GitBranch,
  MessageSquareText,
  Save,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import type {
  EventLineDetail,
  EventLineKind,
  MentionCandidate,
  Task,
} from '../../../shared/types.js';

export type EventLineProjectOption = {
  id: string;
  label: string;
};

export type EventLineEditorDraft = {
  name: string;
  kind: EventLineKind;
  primaryClientId: string;
  summary: string;
  stage: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  participantIds: string[];
};

type Props = {
  mode: 'create' | 'edit';
  draft: EventLineEditorDraft;
  detail?: EventLineDetail | null;
  projectOptions: EventLineProjectOption[];
  memberOptions: MentionCandidate[];
  canDelete: boolean;
  isSaving: boolean;
  onClose: () => void;
  onChange: (patch: Partial<EventLineEditorDraft>) => void;
  onSubmit: () => void;
  onCreateProject?: (initialName?: string) => Promise<void> | void;
  onDelete?: () => void;
  onOpenReport?: () => void;
  onOpenTask?: (task: Task) => void;
  onOpenMeeting?: (meetingId: string, label: string) => void;
  onAddNote?: (text: string) => Promise<void>;
};

const EVENT_LINE_KIND_OPTIONS: Array<{ value: EventLineKind; label: string }> = [
  { value: 'project_line', label: '项目推进' },
  { value: 'issue_line', label: '问题处理' },
  { value: 'coordination_line', label: '协同推进' },
  { value: 'case_line', label: '案例沉淀' },
  { value: 'custom', label: '自定义' },
];

const EVENT_LINE_STATUS_LABELS: Record<string, string> = {
  active: '进行中',
  paused: '暂停',
  blocked: '阻塞',
  done: '完成',
  archived: '已归档',
};

function formatDateTime(iso?: string | null) {
  if (!iso) return '未记录';
  return iso.slice(0, 16).replace('T', ' ');
}

function formatPredictionReadiness(detail?: EventLineDetail | null) {
  const score = typeof detail?.predictionReadiness === 'number'
    ? Math.round(detail.predictionReadiness)
    : Math.min(92, 36 + Math.min(detail?.eventLine.evidenceCount || 0, 8) * 7);
  const label = score >= 80 ? '高' : score >= 60 ? '中' : '低';
  return { score, label };
}

function deriveClarificationNeeds(detail?: EventLineDetail | null) {
  if (detail?.clarificationNeeds?.length) return detail.clarificationNeeds;
  const fallback: string[] = [];
  if (!detail?.eventLine.stage) fallback.push('当前推进阶段还不够明确');
  if (!detail?.eventLine.currentBlocker) fallback.push('当前阻塞还没有沉淀');
  if (!detail?.eventLine.nextStep) fallback.push('下一步动作还没有收口');
  return fallback.length > 0 ? fallback : ['目前没有明显缺口，可以继续围绕最近进展补充判断。'];
}

function deriveMeetingSummaries(detail?: EventLineDetail | null) {
  return (detail?.activities || [])
    .filter((activity) => activity.sourceType === 'meeting')
    .slice(0, 5)
    .map((activity) => {
      const metadata = activity.metadata || {};
      const stage = typeof metadata.meetingStage === 'string'
        ? metadata.meetingStage
        : typeof metadata.stage === 'string'
          ? metadata.stage
          : '';
      return {
        id: activity.sourceId,
        title: activity.title || '未命名会议',
        stage,
        happenedAt: activity.happenedAt,
      };
    });
}

export default function EventLineEditorModal({
  mode,
  draft,
  detail,
  projectOptions,
  memberOptions,
  canDelete,
  isSaving,
  onClose,
  onChange,
  onSubmit,
  onCreateProject,
  onDelete,
  onOpenReport,
  onOpenTask,
  onOpenMeeting,
  onAddNote,
}: Props) {
  const projectDropdownRef = useRef<HTMLDivElement | null>(null);
  const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);
  const [projectQuery, setProjectQuery] = useState('');
  const [isProjectCreating, setIsProjectCreating] = useState(false);
  const [isMemberMenuOpen, setIsMemberMenuOpen] = useState(false);
  const [memberQuery, setMemberQuery] = useState('');
  const [noteText, setNoteText] = useState('');
  const [isNoteBusy, setIsNoteBusy] = useState(false);

  const memberMap = useMemo(
    () => new Map(memberOptions.map((item) => [item.id, item])),
    [memberOptions],
  );
  const selectedProject = useMemo(
    () => projectOptions.find((item) => item.id === draft.primaryClientId) || null,
    [draft.primaryClientId, projectOptions],
  );
  const filteredProjects = useMemo(() => {
    const needle = projectQuery.trim().toLowerCase();
    if (!needle) return projectOptions;
    return projectOptions.filter((item) => item.label.toLowerCase().includes(needle));
  }, [projectOptions, projectQuery]);
  const selectedMembers = draft.participantIds
    .map((id) => memberMap.get(id))
    .filter((item): item is MentionCandidate => Boolean(item));
  const filteredMembers = memberOptions.filter((item) => {
    const needle = memberQuery.trim().toLowerCase();
    if (!needle) return true;
    return item.fullName.toLowerCase().includes(needle) || item.email.toLowerCase().includes(needle);
  });
  const readiness = formatPredictionReadiness(detail);
  const clarificationNeeds = deriveClarificationNeeds(detail);
  const relatedMeetings = deriveMeetingSummaries(detail);
  const memorySummary = detail?.memorySnapshot?.currentWork || detail?.eventLine.summary || '还没有形成稳定的记忆摘要，可先补一句当前在推进什么。';

  useEffect(() => {
    if (!isProjectMenuOpen) {
      setProjectQuery(selectedProject?.label || '');
    }
  }, [isProjectMenuOpen, selectedProject]);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!projectDropdownRef.current) return;
      if (!projectDropdownRef.current.contains(event.target as Node)) {
        setIsProjectMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  const toggleMember = (candidate: MentionCandidate) => {
    const exists = draft.participantIds.includes(candidate.id);
    onChange({
      participantIds: exists
        ? draft.participantIds.filter((item) => item !== candidate.id)
        : [...draft.participantIds, candidate.id],
    });
  };

  const handleProjectQueryChange = (value: string) => {
    setProjectQuery(value);
    setIsProjectMenuOpen(true);
    if ((selectedProject?.label || '') !== value) {
      onChange({ primaryClientId: '' });
    }
  };

  const handleSelectProject = (project: EventLineProjectOption) => {
    onChange({ primaryClientId: project.id });
    setProjectQuery(project.label);
    setIsProjectMenuOpen(false);
  };

  const handleCreateProjectFromQuery = async () => {
    const name = projectQuery.trim();
    if (!name || !onCreateProject || isProjectCreating) return;
    setIsProjectCreating(true);
    try {
      await onCreateProject(name);
      setIsProjectMenuOpen(false);
    } finally {
      setIsProjectCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/30 px-4 py-6 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[88vh] w-full max-w-[880px] flex-col overflow-hidden rounded-[28px] border border-gray-100 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.16)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4 border-b border-gray-100 px-6 py-5">
          <div className="min-w-0">
            <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-[#5B7BFE]">
              {mode === 'create' ? '新建事件线' : '编辑事件线'}
            </p>
            <h2 className="mt-1 truncate text-[22px] font-bold text-gray-900">
              {mode === 'create' ? '按项目创建新的推进主线' : draft.name || detail?.eventLine.name || '未命名事件线'}
            </h2>
            {detail ? (
              <p className="mt-1 text-[12px] text-gray-500">
                当前状态：{EVENT_LINE_STATUS_LABELS[detail.eventLine.status] || detail.eventLine.status}
              </p>
            ) : (
              <p className="mt-1 text-[12px] text-gray-500">这里直接填写名称、类型、关联项目和主要负责人。</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {mode === 'edit' && onOpenReport ? (
              <button
                type="button"
                onClick={onOpenReport}
                className="inline-flex items-center gap-2 rounded-2xl border border-[#D7E0FF] bg-[#F8FAFF] px-4 py-2 text-[12px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF]"
              >
                <FileBadge size={14} />
                汇报预览
              </button>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-gray-200 text-gray-400 transition hover:bg-gray-50 hover:text-gray-700"
              aria-label="关闭事件线编辑弹窗"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="grid gap-6 lg:grid-cols-[1.12fr_0.88fr]">
            <div className="space-y-5">
              <section className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">名称</span>
                    <input
                      value={draft.name}
                      onChange={(event) => onChange({ name: event.target.value })}
                      placeholder="输入事件线名称"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] font-medium text-gray-800 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">类型</span>
                    <select
                      value={draft.kind}
                      onChange={(event) => onChange({ kind: event.target.value as EventLineKind })}
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] font-medium text-gray-800 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    >
                      {EVENT_LINE_KIND_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="mt-4 block">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="block text-[12px] font-bold text-gray-500">关联项目</span>
                  </div>
                  <div className="relative" ref={projectDropdownRef}>
                    <div className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 transition focus-within:border-[#5B7BFE] focus-within:ring-2 focus-within:ring-[#5B7BFE]/10">
                      <Search size={14} className="shrink-0 text-gray-400" />
                      <input
                        value={projectQuery}
                        onChange={(event) => handleProjectQueryChange(event.target.value)}
                        onFocus={() => setIsProjectMenuOpen(true)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            if (filteredProjects[0]) {
                              handleSelectProject(filteredProjects[0]);
                            } else if (onCreateProject && projectQuery.trim()) {
                              void handleCreateProjectFromQuery();
                            }
                          }
                        }}
                        placeholder={projectOptions.length > 0 ? '输入项目名称搜索' : '输入项目名称后直接创建'}
                        className="w-full border-0 bg-transparent text-[14px] font-medium text-gray-800 outline-none"
                      />
                      {selectedProject ? (
                        <button
                          type="button"
                          onClick={() => {
                            onChange({ primaryClientId: '' });
                            setProjectQuery('');
                            setIsProjectMenuOpen(true);
                          }}
                          className="flex h-5 w-5 items-center justify-center rounded-full text-gray-400 transition hover:bg-slate-100 hover:text-gray-600"
                          aria-label="清空已选项目"
                        >
                          <X size={12} />
                        </button>
                      ) : null}
                    </div>
                    {isProjectMenuOpen ? (
                      <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-2xl border border-gray-200 bg-white p-2 shadow-lg">
                        <div className="max-h-56 overflow-y-auto">
                          {filteredProjects.map((project) => {
                            const checked = draft.primaryClientId === project.id;
                            return (
                              <button
                                key={project.id}
                                type="button"
                                onClick={() => handleSelectProject(project)}
                                className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                              >
                                <span className="truncate">{project.label}</span>
                                <span className={`ml-3 flex h-5 w-5 items-center justify-center rounded border text-[12px] font-bold ${checked ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white' : 'border-gray-300 bg-white text-transparent'}`}>
                                  ✓
                                </span>
                              </button>
                            );
                          })}
                          {filteredProjects.length === 0 ? (
                            <div className="px-3 py-2 text-xs text-gray-400">没有找到匹配项目</div>
                          ) : null}
                        </div>
                        {onCreateProject && projectQuery.trim() && !filteredProjects.some((item) => item.label === projectQuery.trim()) ? (
                          <button
                            type="button"
                            onClick={() => void handleCreateProjectFromQuery()}
                            disabled={isProjectCreating}
                            className="mt-2 inline-flex items-center gap-1 rounded-full border border-[#D7E0FF] bg-[#F8FAFF] px-3 py-1 text-[11px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF] disabled:cursor-wait disabled:opacity-60"
                          >
                            <Briefcase size={12} />
                            {isProjectCreating ? `正在创建“${projectQuery.trim()}”` : `创建项目“${projectQuery.trim()}”`}
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  <p className="mt-2 text-[12px] text-gray-400">
                    输入项目名称可直接搜索；如果没有匹配项，可以直接用当前输入创建项目。
                  </p>
                </label>

                <div className="mt-4">
                  <span className="mb-2 block text-[12px] font-bold text-gray-500">主要负责人</span>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsMemberMenuOpen((prev) => !prev)}
                      className="flex min-h-[48px] w-full items-center justify-between rounded-2xl border border-gray-200 bg-white px-4 py-3 text-left transition hover:border-[#5B7BFE]"
                    >
                      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                        {selectedMembers.length > 0 ? (
                          selectedMembers.map((member) => (
                            <span key={member.id} className="inline-flex max-w-full items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[13px] text-gray-700">
                              <span className="truncate">{member.fullName}</span>
                              <span
                                role="button"
                                tabIndex={0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  toggleMember(member);
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === 'Enter' || event.key === ' ') {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    toggleMember(member);
                                  }
                                }}
                                className="flex h-4 w-4 items-center justify-center rounded-full text-gray-400 hover:bg-slate-200 hover:text-gray-600"
                                aria-label={`移除主要负责人${member.fullName}`}
                              >
                                <X size={12} />
                              </span>
                            </span>
                          ))
                        ) : (
                          <span className="text-[14px] text-gray-400">可多选，建议至少选 1 位主要负责人</span>
                        )}
                      </div>
                      <ChevronDown size={16} className={`ml-2 text-gray-400 transition-transform ${isMemberMenuOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {isMemberMenuOpen ? (
                      <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-2xl border border-gray-200 bg-white p-3 shadow-lg">
                        <div className="flex items-center gap-2 rounded-xl border border-gray-200 px-3 py-2">
                          <Search size={14} className="text-gray-400" />
                          <input
                            value={memberQuery}
                            onChange={(event) => setMemberQuery(event.target.value)}
                            placeholder="搜索成员"
                            className="w-full border-0 bg-transparent text-sm outline-none"
                          />
                        </div>
                        <div className="mt-2 max-h-56 overflow-y-auto">
                          {filteredMembers.length === 0 ? (
                            <div className="px-3 py-2 text-xs text-gray-400">暂无匹配成员</div>
                          ) : filteredMembers.map((member) => {
                            const checked = draft.participantIds.includes(member.id);
                            return (
                              <button
                                key={member.id}
                                type="button"
                                onClick={() => toggleMember(member)}
                                className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                              >
                                <span>{member.fullName}{member.isSelf ? '（自己）' : ''}</span>
                                <span className={`flex h-5 w-5 items-center justify-center rounded border text-[12px] font-bold ${checked ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white' : 'border-gray-300 bg-white text-transparent'}`}>
                                  ✓
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>

                <label className="mt-4 block">
                  <span className="mb-2 block text-[12px] font-bold text-gray-500">事件线概述</span>
                  <textarea
                    value={draft.summary}
                    onChange={(event) => onChange({ summary: event.target.value })}
                    rows={4}
                    placeholder="一句话说明这条主线在推进什么。"
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] leading-6 text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                  />
                </label>
              </section>

              <section className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2">
                  <GitBranch size={16} className="text-[#5B7BFE]" />
                  <h3 className="text-[15px] font-bold text-gray-900">线索判断</h3>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">当前判断成熟度</p>
                    <p className="mt-2 text-[15px] font-bold text-slate-900">{readiness.label} · {readiness.score} 分</p>
                  </div>
                  <div className="rounded-2xl bg-slate-50 px-4 py-3 md:col-span-2">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">最近形成的记忆摘要</p>
                    <p className="mt-2 text-[13px] leading-6 text-slate-700">{memorySummary}</p>
                  </div>
                </div>
                <div className="mt-4 rounded-2xl bg-amber-50 px-4 py-3">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-amber-700">还缺哪些澄清</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {clarificationNeeds.map((item) => (
                      <span key={item} className="rounded-full bg-white px-3 py-1 text-[12px] font-medium text-amber-700">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <label className="block">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">当前阶段</span>
                    <input
                      value={draft.stage}
                      onChange={(event) => onChange({ stage: event.target.value })}
                      placeholder="如：方案收口 / 落地推进"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    />
                  </label>
                  <label className="block md:col-span-2">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">当前阻塞</span>
                    <input
                      value={draft.currentBlocker}
                      onChange={(event) => onChange({ currentBlocker: event.target.value })}
                      placeholder="当前最大的卡点是什么"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-medium text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    />
                  </label>
                  <label className="block md:col-span-3">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">最近关键决策</span>
                    <textarea
                      value={draft.recentDecision}
                      onChange={(event) => onChange({ recentDecision: event.target.value })}
                      rows={3}
                      placeholder="最近明确了什么方向、口径或边界"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    />
                  </label>
                  <label className="block md:col-span-3">
                    <span className="mb-2 block text-[12px] font-bold text-gray-500">下一步动作</span>
                    <textarea
                      value={draft.nextStep}
                      onChange={(event) => onChange({ nextStep: event.target.value })}
                      rows={3}
                      placeholder="下一步最该推进什么"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                    />
                  </label>
                </div>
              </section>
            </div>

            <div className="space-y-5">
              <section className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2">
                  <CalendarClock size={16} className="text-[#5B7BFE]" />
                  <h3 className="text-[15px] font-bold text-gray-900">关联会议</h3>
                </div>
                {relatedMeetings.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-4 text-[13px] leading-6 text-gray-400">
                    当前还没有稳定挂进来的会议。会议一旦和这条事件线关联，这里会优先显示最近会议标题、时间和阶段。
                  </p>
                ) : (
                  <div className="space-y-3">
                    {relatedMeetings.map((meeting) => (
                      <button
                        key={`${meeting.id}-${meeting.happenedAt}`}
                        type="button"
                        onClick={() => onOpenMeeting?.(meeting.id, meeting.title)}
                        className="w-full rounded-2xl border border-gray-100 bg-slate-50 px-4 py-3 text-left transition hover:border-[#D7E0FF] hover:bg-[#F8FAFF]"
                      >
                        <p className="text-[14px] font-bold text-gray-900">{meeting.title}</p>
                        <p className="mt-1 text-[12px] text-gray-500">
                          {formatDateTime(meeting.happenedAt)}
                          {meeting.stage ? ` · ${meeting.stage}` : ''}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2">
                  <Briefcase size={16} className="text-[#5B7BFE]" />
                  <h3 className="text-[15px] font-bold text-gray-900">关联任务</h3>
                </div>
                {detail?.tasks?.length ? (
                  <div className="space-y-2">
                    {detail.tasks.slice(0, 8).map((task) => (
                      <button
                        key={task.id}
                        type="button"
                        onClick={() => onOpenTask?.(task)}
                        className="w-full rounded-2xl border border-gray-100 bg-white px-4 py-3 text-left transition hover:border-[#D7E0FF] hover:bg-[#F8FAFF]"
                      >
                        <p className="text-[14px] font-bold text-gray-900">{task.title}</p>
                        <p className="mt-1 text-[12px] text-gray-500">
                          {task.ownerName || '未指定负责人'}
                          {task.dueDate ? ` · ${formatDateTime(task.dueDate)}` : ''}
                        </p>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-4 text-[13px] leading-6 text-gray-400">
                    这条事件线下还没有关联任务。后续只要任务挂进来，这里就会自动汇总。
                  </p>
                )}
              </section>

              {mode === 'edit' && onAddNote ? (
                <section className="rounded-3xl border border-gray-100 bg-white p-5 shadow-sm">
                  <div className="mb-3 flex items-center gap-2">
                    <MessageSquareText size={16} className="text-[#5B7BFE]" />
                    <h3 className="text-[15px] font-bold text-gray-900">补充一条线索备注</h3>
                  </div>
                  <textarea
                    value={noteText}
                    onChange={(event) => setNoteText(event.target.value)}
                    rows={4}
                    placeholder="记录一条观察、补充说明或新的判断。"
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                  />
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      disabled={!noteText.trim() || isNoteBusy}
                      onClick={() => {
                        if (!noteText.trim()) return;
                        void (async () => {
                          setIsNoteBusy(true);
                          try {
                            await onAddNote(noteText.trim());
                            setNoteText('');
                          } finally {
                            setIsNoteBusy(false);
                          }
                        })();
                      }}
                      className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white transition hover:bg-[#4A6AE8] disabled:opacity-50"
                    >
                      <MessageSquareText size={14} />
                      {isNoteBusy ? '保存中...' : '添加备注'}
                    </button>
                  </div>
                </section>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-gray-100 bg-gray-50/50 px-6 py-4">
          <div>
            {mode === 'edit' && canDelete && onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                className="inline-flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-[12px] font-bold text-rose-600 transition hover:bg-rose-100"
              >
                <Trash2 size={14} />
                删除事件线
              </button>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-[13px] font-bold text-gray-500 transition hover:text-gray-800"
            >
              取消
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={isSaving || !draft.name.trim()}
              className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-2.5 text-[13px] font-bold text-white transition hover:bg-[#4A6AE8] disabled:opacity-50"
            >
              <Save size={14} />
              {isSaving ? '保存中...' : mode === 'create' ? '创建事件线' : '保存修改'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
