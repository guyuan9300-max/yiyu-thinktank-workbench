import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  X,
  Download,
  Upload,
  ChevronDown,
  ChevronRight,
  Paperclip,
  Clock,
  Users,
  FileBadge,
  FileText,
  Image,
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
/*  DocContentViewer — loads and displays document text content         */
/* ------------------------------------------------------------------ */

function DocContentViewer({ att, backendBaseUrl }: { att: EventLineReportAttachment; backendBaseUrl: string }) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/text-content`)
      .then((r) => r.json())
      .then((data: { text?: string; unsupported?: boolean }) => {
        setText(data.unsupported ? '此文件类型暂不支持内容预览' : (data.text || '（无内容）'));
      })
      .catch(() => setText('内容加载失败'))
      .finally(() => setLoading(false));
  }, [att.id, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2">
      <p className="text-[11px] font-semibold text-gray-700">{att.title}</p>
      {loading ? (
        <div className="mt-1 flex items-center gap-1">
          <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-gray-300 border-t-[#5B7BFE]" />
          <span className="text-[10px] text-gray-400">加载中...</span>
        </div>
      ) : (
        <pre className="mt-1 max-h-[300px] overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 text-gray-600">{text}</pre>
      )}
    </div>
  );
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
  const [uploadProgressByActivity, setUploadProgressByActivity] = useState<Record<string, { current: number; total: number; fileName: string; error?: string }>>({});
  const [exportProgress, setExportProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Local editable draft — built from immutable cloud snapshot */
  const [draft, setDraft] = useState<ReportDraft | null>(null);

  /* Per-activity toggle: which activities have docs expanded / images expanded */
  const [docsExpandedActivities, setDocsExpandedActivities] = useState<Set<string>>(new Set());
  const [imagesExpandedActivities, setImagesExpandedActivities] = useState<Set<string>>(new Set());

  /* Track which attachments are expanded (legacy, kept for export) */
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

  /* Group attachments by activity — match via metadata.taskId or sourceId */
  const attachmentsByActivity = useMemo(() => {
    if (!draft) return new Map<string, EventLineReportAttachment[]>();
    const map = new Map<string, EventLineReportAttachment[]>();
    for (const att of draft.attachments) {
      // Try to match to an activity via metadata.taskId or sourceId
      const matchingActivity = draft.activities.find((a) => {
        const meta = a.metadata as Record<string, unknown> | undefined;
        if (meta?.taskId && String(meta.taskId) === att.taskId) return true;
        if (meta?.attachmentId && String(meta.attachmentId) === att.id) return true;
        if (a.sourceType === 'attachment' && a.sourceId === att.id) return true;
        return false;
      });
      const key = matchingActivity?.id || att.taskId || '_unlinked';
      const list = map.get(key) || [];
      list.push(att);
      map.set(key, list);
    }
    return map;
  }, [draft]);

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
        className="relative flex max-h-[90vh] w-full max-w-[860px] flex-col rounded-[28px] border border-gray-100 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
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
            disabled={!!exportProgress}
            className={`shrink-0 flex items-center gap-2 rounded-2xl px-5 py-2.5 text-[12px] font-bold text-white transition ${exportProgress ? 'bg-blue-400' : 'bg-[#5B7BFE] hover:bg-[#4a6ae8]'}`}
            onClick={() => {
              const exportDraft = { ...draft, expandedAttachmentIds: Array.from(expandedAttachments) };
              setExportProgress({ stage: '准备导出...', detail: '正在整理事件线数据' });
              void (async () => {
                try {
                  setExportProgress({ stage: '生成文档...', detail: `正在处理 ${draft.activities.length} 条活动记录和 ${draft.attachments.length} 个附件` });
                  const response = await fetch(`${backendBaseUrl}/api/v1/event-lines/${eventLineId}/export-word`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(exportDraft),
                  });
                  if (!response.ok) throw new Error('导出失败');
                  setExportProgress({ stage: '下载文件...', detail: '文档已生成，正在下载到本地' });
                  const blob = await response.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${draft.eventLineName || '事件线汇报'}.docx`;
                  a.click();
                  URL.revokeObjectURL(url);
                  setExportProgress(null);
                } catch {
                  setExportProgress(null);
                }
              })();
            }}
          >
            <Download size={14} />
            {exportProgress ? '导出中...' : '导出 Word'}
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

        {/* ── Export progress overlay ── */}
        {exportProgress && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-[28px]">
            <div className="text-center px-8 py-6">
              <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-3 border-gray-200 border-t-[#5B7BFE]" />
              <p className="text-[14px] font-bold text-gray-800">{exportProgress.stage}</p>
              <p className="mt-1 text-[12px] text-gray-500">{exportProgress.detail}</p>
            </div>
          </div>
        )}

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
                const activityAtts = attachmentsByActivity.get(activity.id) || [];
                const imageAtts = activityAtts.filter((a) => (a.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.title));
                const docAtts = activityAtts.filter((a) => !((a.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.title)));
                const hasAtts = activityAtts.length > 0;
                const isDocsExpanded = docsExpandedActivities.has(activity.id);
                const isImagesExpanded = imagesExpandedActivities.has(activity.id);

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
                      <div className="w-[110px] shrink-0 pt-0.5">
                        <p className="text-[11px] text-gray-400">{formatTs(activity.happenedAt)}</p>
                        <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                          {SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType}
                        </span>
                      </div>

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

                        {/* 4 icon buttons — always visible on every activity */}
                          <div className="mt-2 flex items-center gap-1">
                            <button
                              type="button"
                              title={isDocsExpanded ? '折叠文档' : '展开文档'}
                              disabled={docAtts.length === 0}
                              className={`rounded p-1 transition ${docAtts.length === 0 ? 'text-gray-200 cursor-default' : isDocsExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                              onClick={() => { if (docAtts.length === 0) return; setDocsExpandedActivities((prev) => { const next = new Set(prev); if (next.has(activity.id)) next.delete(activity.id); else next.add(activity.id); return next; }); }}
                            >
                              <FileText size={12} />
                            </button>
                            <button
                              type="button"
                              title={isImagesExpanded ? '折叠图片' : '展开图片'}
                              disabled={imageAtts.length === 0}
                              className={`rounded p-1 transition ${imageAtts.length === 0 ? 'text-gray-200 cursor-default' : isImagesExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                              onClick={() => { if (imageAtts.length === 0) return; setImagesExpandedActivities((prev) => { const next = new Set(prev); if (next.has(activity.id)) next.delete(activity.id); else next.add(activity.id); return next; }); }}
                            >
                              <Image size={12} />
                            </button>
                            <button
                              type="button"
                              title={hasAtts ? `下载全部附件（${activityAtts.length}个）` : '暂无附件'}
                              disabled={!hasAtts}
                              className={`rounded p-1 transition ${hasAtts ? 'text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100' : 'text-gray-200 cursor-default'}`}
                              onClick={() => {
                                if (!hasAtts) return;
                                void fetch(`${backendBaseUrl}/api/v1/event-lines/${eventLineId}/attachments/download-zip`, {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ attachmentIds: activityAtts.map((a) => a.id) }),
                                }).then(async (resp) => {
                                  if (!resp.ok) return;
                                  const blob = await resp.blob();
                                  const url = URL.createObjectURL(blob);
                                  const a = document.createElement('a');
                                  a.href = url;
                                  a.download = `附件_${(activity.editedTitle ?? activity.title).slice(0, 15)}.zip`;
                                  a.click();
                                  URL.revokeObjectURL(url);
                                });
                              }}
                            >
                              <Download size={12} />
                            </button>
                            <label
                              title="上传附件"
                              className="rounded p-1 text-gray-400 transition hover:text-[#5B7BFE] hover:bg-gray-100 cursor-pointer"
                            >
                              <Upload size={12} />
                              <input
                                type="file"
                                multiple
                                className="hidden"
                                onChange={(event) => {
                                  const files = event.target.files;
                                  if (!files || files.length === 0) return;
                                  const fileList = Array.from(files);
                                  const actId = activity.id;
                                  void (async () => {
                                    let hasError = false;
                                    for (let i = 0; i < fileList.length; i++) {
                                      const file = fileList[i];
                                      setUploadProgressByActivity((prev) => ({ ...prev, [actId]: { current: i + 1, total: fileList.length, fileName: file.name } }));
                                      const formData = new FormData();
                                      formData.append('file', file);
                                      formData.append('title', file.name);
                                      try {
                                        const resp = await fetch(`${backendBaseUrl}/api/v1/event-lines/${eventLineId}/attachments`, {
                                          method: 'POST',
                                          body: formData,
                                        });
                                        if (!resp.ok) {
                                          const err = await resp.json().catch(() => ({}));
                                          hasError = true;
                                          setUploadProgressByActivity((prev) => ({ ...prev, [actId]: { current: i + 1, total: fileList.length, fileName: file.name, error: err.detail || '上传失败' } }));
                                        }
                                      } catch {
                                        hasError = true;
                                        setUploadProgressByActivity((prev) => ({ ...prev, [actId]: { current: i + 1, total: fileList.length, fileName: file.name, error: '网络错误' } }));
                                      }
                                    }
                                    if (!hasError) {
                                      setUploadProgressByActivity((prev) => { const next = { ...prev }; delete next[actId]; return next; });
                                    } else {
                                      setTimeout(() => setUploadProgressByActivity((prev) => { const next = { ...prev }; delete next[actId]; return next; }), 5000);
                                    }
                                    void loadSnapshot();
                                  })();
                                  event.target.value = '';
                                }}
                              />
                            </label>
                            {hasAtts && <span className="text-[9px] text-gray-300 ml-0.5">{activityAtts.length}</span>}
                          </div>

                        {/* 上传进度（per-activity） */}
                        {uploadProgressByActivity[activity.id] && (
                          <div className="mt-1 rounded-lg bg-blue-50 px-2 py-1">
                            <div className="flex items-center gap-1.5">
                              {uploadProgressByActivity[activity.id].error ? (
                                <span className="text-[10px] text-red-600">{uploadProgressByActivity[activity.id].error}</span>
                              ) : (
                                <>
                                  <div className="h-2 w-2 animate-spin rounded-full border border-blue-300 border-t-[#5B7BFE]" />
                                  <span className="text-[10px] text-blue-700">
                                    上传 {uploadProgressByActivity[activity.id].current}/{uploadProgressByActivity[activity.id].total}：{uploadProgressByActivity[activity.id].fileName}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        )}

                        {/* 附件文件名列表（始终显示） */}
                        {hasAtts && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {activityAtts.map((att) => {
                              const isImg = (att.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(att.title);
                              return (
                                <a
                                  key={att.id}
                                  href={`${backendBaseUrl}${att.downloadUrl}`}
                                  download={att.title}
                                  className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] text-gray-600 transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
                                  title={`${att.title} · ${fileSizeLabel(att.sizeBytes)}`}
                                >
                                  {isImg ? <Image size={10} /> : <FileText size={10} />}
                                  {att.title.length > 20 ? `${att.title.slice(0, 18)}…` : att.title}
                                </a>
                              );
                            })}
                          </div>
                        )}

                        {/* 展开的文档 — 加载并显示文本内容 */}
                        {isDocsExpanded && docAtts.length > 0 && (
                          <div className="mt-2 space-y-2">
                            {docAtts.map((att) => (
                              <DocContentViewer key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
                            ))}
                          </div>
                        )}

                        {/* 展开的图片 — 排版显示 */}
                        {isImagesExpanded && imageAtts.length > 0 && (
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            {imageAtts.map((att) => (
                              <div key={att.id} className="rounded-xl border border-gray-200 overflow-hidden bg-gray-50">
                                <img
                                  src={`${backendBaseUrl}${att.downloadUrl}`}
                                  alt={att.title}
                                  className="w-full object-contain max-h-[300px]"
                                />
                                <p className="px-2 py-1 text-[10px] text-gray-500 truncate">{att.title}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

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

        </div>
      </div>
    </div>
  );
}

export type { ReportDraft };
