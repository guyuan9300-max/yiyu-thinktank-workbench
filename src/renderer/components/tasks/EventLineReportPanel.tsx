import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  X,
  Download,
  ChevronDown,
  ChevronRight,
  Paperclip,
  Clock,
  Users,
  FileBadge,
} from 'lucide-react';
import type {
  EventLineReportSnapshot,
  EventLineReportAttachment,
  EventLineActivity,
} from '../../../shared/types.js';
import { getEventLineReportSnapshot } from '../../lib/api.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type EditableActivity = EventLineActivity & {
  /** 用户在本地编辑过的标题 */
  editedTitle?: string;
  /** 用户在本地编辑过的摘要 */
  editedSummary?: string;
  /** 用户标记为隐藏（不纳入导出） */
  hidden?: boolean;
};

type ReportDraft = {
  eventLineName: string;
  summary: string;
  activities: EditableActivity[];
  attachments: EventLineReportAttachment[];
  participantNames: string[];
  snapshotAt: string;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  task_activity: '任务',
  meeting: '会议',
  support_request: '支持请求',
  review: '复核',
  attachment: '附件',
  manual_note: '备注',
};

function formatTs(iso: string) {
  if (!iso) return '';
  return iso.slice(0, 16).replace('T', ' ');
}

function fileSizeLabel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

type Props = {
  eventLineId: string;
  backendBaseUrl: string;
  onClose: () => void;
  onExportWord: (draft: ReportDraft) => void;
};

export default function EventLineReportPanel({ eventLineId, backendBaseUrl, onClose, onExportWord }: Props) {
  const [snapshot, setSnapshot] = useState<EventLineReportSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Local editable draft — built from immutable cloud snapshot */
  const [draft, setDraft] = useState<ReportDraft | null>(null);

  /* Track which attachments are expanded */
  const [expandedAttachments, setExpandedAttachments] = useState<Set<string>>(new Set());

  /* Fetch immutable snapshot from cloud */
  const loadSnapshot = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEventLineReportSnapshot(eventLineId);
      setSnapshot(data);
      setDraft({
        eventLineName: data.eventLine.name,
        summary: data.eventLine.summary || '',
        activities: data.activities.map((a: EventLineActivity) => ({ ...a })),
        attachments: [...data.attachments],
        participantNames: [...data.participantNames],
        snapshotAt: data.snapshotAt,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载事件线快照失败');
    } finally {
      setLoading(false);
    }
  }, [eventLineId]);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  /* Edit handlers — only modify the local draft */
  const updateActivityField = useCallback(
    (activityId: string, field: 'editedTitle' | 'editedSummary', value: string) => {
      setDraft((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          activities: prev.activities.map((a) => (a.id === activityId ? { ...a, [field]: value } : a)),
        };
      });
    },
    [],
  );

  const toggleActivityHidden = useCallback((activityId: string) => {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        activities: prev.activities.map((a) => (a.id === activityId ? { ...a, hidden: !a.hidden } : a)),
      };
    });
  }, []);

  const toggleAttachmentExpand = useCallback((attachmentId: string) => {
    setExpandedAttachments((prev) => {
      const next = new Set(prev);
      if (next.has(attachmentId)) next.delete(attachmentId);
      else next.add(attachmentId);
      return next;
    });
  }, []);

  const visibleActivities = useMemo(() => (draft?.activities ?? []).filter((a) => !a.hidden), [draft]);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-md">
        <div className="rounded-3xl bg-white px-10 py-8 text-center shadow-xl">
          <p className="text-[13px] text-gray-500">正在从云端拉取完整事件线...</p>
        </div>
      </div>
    );
  }

  if (error || !draft || !snapshot) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-md">
        <div className="rounded-3xl bg-white px-10 py-8 text-center shadow-xl">
          <p className="text-[13px] text-red-600">{error || '无法加载事件线'}</p>
          <button type="button" className="mt-4 rounded-2xl bg-gray-100 px-4 py-2 text-[12px]" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-md animate-in fade-in">
      <div
        className="flex max-h-[90vh] w-full max-w-[860px] flex-col rounded-[28px] border border-gray-100 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-start gap-4 border-b border-gray-100 p-6 pb-4">
          <button
            type="button"
            className="mt-1 rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
            onClick={onClose}
          >
            <X size={16} />
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-bold tracking-[0.12em] text-[#5B7BFE]">事件线汇报</p>
            <input
              className="mt-1 w-full bg-transparent text-[20px] font-bold text-gray-900 outline-none placeholder:text-gray-300"
              value={draft.eventLineName}
              onChange={(e) => setDraft((prev) => prev ? { ...prev, eventLineName: e.target.value } : prev)}
              placeholder="事件线名称"
            />
            <textarea
              className="mt-2 w-full resize-none bg-transparent text-[13px] leading-6 text-gray-500 outline-none placeholder:text-gray-300"
              rows={2}
              value={draft.summary}
              onChange={(e) => setDraft((prev) => prev ? { ...prev, summary: e.target.value } : prev)}
              placeholder="摘要说明"
            />
          </div>
          <button
            type="button"
            className="shrink-0 flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-2.5 text-[12px] font-bold text-white transition hover:bg-[#4a6ae8]"
            onClick={() => onExportWord(draft)}
          >
            <Download size={14} />
            导出 Word
          </button>
        </div>

        {/* ── Meta badges ── */}
        <div className="flex flex-wrap items-center gap-2 border-b border-gray-50 px-6 py-3 text-[11px]">
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 font-bold text-emerald-700">
            {snapshot.eventLine.status}
          </span>
          {snapshot.eventLine.stage && (
            <span className="rounded-full bg-amber-50 px-2.5 py-1 font-bold text-amber-700">{snapshot.eventLine.stage}</span>
          )}
          {snapshot.eventLine.primaryClientName && (
            <span className="rounded-full bg-violet-50 px-2.5 py-1 font-bold text-violet-700">{snapshot.eventLine.primaryClientName}</span>
          )}
          {draft.participantNames.length > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 font-bold text-blue-700">
              <Users size={11} /> {draft.participantNames.join('、')}
            </span>
          )}
          <span className="ml-auto flex items-center gap-1 text-gray-400">
            <Clock size={11} /> 快照于 {formatTs(draft.snapshotAt)}
          </span>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* ── Timeline ── */}
          <div>
            <div className="flex items-center justify-between">
              <p className="text-[12px] font-bold text-gray-500">完整时间线</p>
              <p className="text-[11px] text-gray-400">
                {visibleActivities.length} / {draft.activities.length} 条
                {draft.activities.length !== visibleActivities.length && (
                  <button
                    type="button"
                    className="ml-2 text-[#5B7BFE] hover:underline"
                    onClick={() => setDraft((prev) => prev ? { ...prev, activities: prev.activities.map((a) => ({ ...a, hidden: false })) } : prev)}
                  >
                    全部显示
                  </button>
                )}
              </p>
            </div>

            <div className="mt-3 space-y-1">
              {draft.activities.map((activity) => {
                const isHidden = activity.hidden;
                return (
                  <div
                    key={activity.id}
                    className={`group rounded-2xl border px-4 py-3 transition ${
                      isHidden
                        ? 'border-dashed border-gray-200 bg-gray-50/50 opacity-50'
                        : 'border-gray-100 bg-white hover:border-gray-200'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* 时间 + 类型 */}
                      <div className="w-[110px] shrink-0 pt-0.5">
                        <p className="text-[11px] text-gray-400">{formatTs(activity.happenedAt)}</p>
                        <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                          {SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType}
                        </span>
                      </div>

                      {/* 内容 — 可编辑 */}
                      <div className="flex-1 min-w-0">
                        <input
                          className="w-full bg-transparent text-[13px] font-semibold text-gray-800 outline-none placeholder:text-gray-300"
                          value={activity.editedTitle ?? activity.title}
                          onChange={(e) => updateActivityField(activity.id, 'editedTitle', e.target.value)}
                        />
                        <textarea
                          className="mt-1 w-full resize-none bg-transparent text-[12px] leading-5 text-gray-500 outline-none placeholder:text-gray-300"
                          rows={1}
                          value={activity.editedSummary ?? activity.summary}
                          onChange={(e) => updateActivityField(activity.id, 'editedSummary', e.target.value)}
                        />
                        {activity.actorName && (
                          <p className="mt-1 text-[10px] text-gray-400">— {activity.actorName}</p>
                        )}
                      </div>

                      {/* 隐藏/显示 */}
                      <button
                        type="button"
                        className="shrink-0 rounded-lg px-2 py-1 text-[10px] text-gray-400 opacity-0 transition group-hover:opacity-100 hover:bg-gray-100 hover:text-gray-600"
                        onClick={() => toggleActivityHidden(activity.id)}
                      >
                        {isHidden ? '显示' : '隐藏'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Attachments ── */}
          {draft.attachments.length > 0 && (
            <div className="mt-6">
              <div className="flex items-center gap-2">
                <Paperclip size={14} className="text-gray-400" />
                <p className="text-[12px] font-bold text-gray-500">附件汇总</p>
                <span className="text-[11px] text-gray-400">{draft.attachments.length} 个</span>
              </div>

              <div className="mt-3 space-y-2">
                {draft.attachments.map((att) => {
                  const isExpanded = expandedAttachments.has(att.id);
                  const downloadHref = `${backendBaseUrl}${att.downloadUrl}`;
                  const isPreviewable = /\.(txt|md|csv|json)$/i.test(att.title);

                  return (
                    <div key={att.id} className="rounded-2xl border border-gray-100 bg-white">
                      <div className="flex items-center gap-3 px-4 py-3">
                        <FileBadge size={16} className="shrink-0 text-gray-400" />
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-[13px] font-semibold text-gray-800">{att.title}</p>
                          <p className="text-[11px] text-gray-400">
                            {att.kind} · {fileSizeLabel(att.sizeBytes)}
                            {att.actorName ? ` · ${att.actorName}` : ''}
                            {` · ${formatTs(att.createdAt)}`}
                          </p>
                        </div>

                        {isPreviewable && (
                          <button
                            type="button"
                            className="rounded-lg border border-gray-200 px-2.5 py-1.5 text-[11px] text-gray-500 transition hover:bg-gray-50"
                            onClick={() => toggleAttachmentExpand(att.id)}
                          >
                            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                            {isExpanded ? '折叠' : '展开'}
                          </button>
                        )}

                        <a
                          href={downloadHref}
                          download={att.title}
                          className="flex items-center gap-1 rounded-lg border border-[#D7E0FF] bg-[#F8FAFF] px-3 py-1.5 text-[11px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF]"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Download size={12} />
                          下载
                        </a>
                      </div>

                      {isExpanded && (
                        <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3">
                          <p className="text-[11px] text-gray-400">文件内容预览将在加载后显示</p>
                        </div>
                      )}
                    </div>
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

export type { ReportDraft };
