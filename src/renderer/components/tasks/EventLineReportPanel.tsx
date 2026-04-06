import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  Task,
} from '../../../shared/types.js';
import { getEventLineReportSnapshot, updateEventLine } from '../../lib/api.js';

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
  tasks: Task[];
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

/** Key events: task created, manual note (review content), attachment upload.
 *  Uses backend-computed `isKey` flag; falls back to heuristic for older data. */
function isKeyActivity(activity: { sourceType: string; title: string; summary: string; isKey?: boolean; metadata?: Record<string, unknown> }): boolean {
  if (activity.isKey !== undefined) return activity.isKey;
  // Fallback for activities without backend isKey flag
  if (['manual_note', 'attachment'].includes(activity.sourceType)) return true;
  if (activity.sourceType === 'task_activity' && activity.metadata?.eventType === 'created') return true;
  return false;
}

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

/** Map file extension to a display label + color for the file-type badge */
function fileTypeBadge(filename: string): { label: string; color: string; bg: string } {
  const ext = (filename.split('.').pop() || '').toLowerCase();
  switch (ext) {
    case 'doc': case 'docx': return { label: 'Word', color: '#2B579A', bg: '#E8EEF7' };
    case 'xls': case 'xlsx': return { label: 'Excel', color: '#217346', bg: '#E2F0E8' };
    case 'ppt': case 'pptx': return { label: 'PPT', color: '#D24726', bg: '#FCEAE5' };
    case 'pdf': return { label: 'PDF', color: '#B30B00', bg: '#FDE8E7' };
    case 'txt': case 'md': return { label: 'TXT', color: '#6B7280', bg: '#F3F4F6' };
    case 'jpg': case 'jpeg': case 'png': case 'gif': case 'webp': return { label: ext.toUpperCase(), color: '#7C3AED', bg: '#EDE9FE' };
    default: return { label: ext.toUpperCase() || '文件', color: '#6B7280', bg: '#F3F4F6' };
  }
}

function DocContentViewer({ att, backendBaseUrl }: { att: EventLineReportAttachment; backendBaseUrl: string }) {
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const badge = fileTypeBadge(att.title);

  useEffect(() => {
    // Try text-content first, fall back to ocr-summary
    void fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/text-content`)
      .then((r) => r.json())
      .then((data: { text?: string; unsupported?: boolean }) => {
        const text = (data.text || '').trim();
        if (text && !text.includes('提取失败') && !text.includes('No module') && !data.unsupported) {
          setSummary(text);
        } else {
          // Fall back to ocr-summary
          return fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/ocr-summary`)
            .then((r2) => r2.json())
            .then((ocr: { summary?: string; unsupported?: boolean }) => {
              if (ocr.summary && !ocr.unsupported) {
                setSummary(ocr.summary);
              } else {
                setSummary(null);
              }
            });
        }
      })
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [att.id, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* File header — icon badge + filename, looks like a file preview */}
      <div className="flex items-center gap-2.5 px-3 py-2.5 bg-gray-50/80 border-b border-gray-100">
        <div
          className="flex-shrink-0 flex items-center justify-center rounded-lg w-9 h-9 text-[10px] font-bold"
          style={{ backgroundColor: badge.bg, color: badge.color }}
        >
          {badge.label}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium text-gray-800 truncate">{att.title}</p>
          <p className="text-[10px] text-gray-400">{fileSizeLabel(att.sizeBytes)}</p>
        </div>
        <a
          href={`${backendBaseUrl}${att.downloadUrl}`}
          download={att.title}
          className="flex-shrink-0 rounded p-1 text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100 transition"
          title="下载文件"
        >
          <Download size={14} />
        </a>
      </div>
      {/* AI summary */}
      <div className="px-3 py-2">
        {loading ? (
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-gray-300 border-t-[#5B7BFE]" />
            <span className="text-[10px] text-gray-400">正在提取文档摘要…</span>
          </div>
        ) : summary ? (
          <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 text-gray-500">{summary}</pre>
        ) : (
          <p className="text-[10px] text-gray-300">暂无文档摘要</p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ImageWithOcr — image preview with OCR summary below                */
/* ------------------------------------------------------------------ */

function ImageWithOcr({ att, backendBaseUrl }: { att: EventLineReportAttachment; backendBaseUrl: string }) {
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void fetch(`${backendBaseUrl}/api/public/task-attachments/${att.id}/ocr-summary`)
      .then((r) => r.json())
      .then((data: { summary?: string; unsupported?: boolean }) => {
        if (data.summary && !data.unsupported) {
          setOcrText(data.summary);
        } else {
          setOcrText(null);
        }
      })
      .catch(() => setOcrText(null))
      .finally(() => setLoading(false));
  }, [att.id, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-gray-50">
      <img
        src={`${backendBaseUrl}${att.downloadUrl}`}
        alt={att.title}
        className="w-full object-contain max-h-[300px]"
      />
      <div className="px-2 py-1.5">
        <p className="text-[10px] text-gray-500 truncate">{att.title}</p>
        {loading ? (
          <div className="mt-1 flex items-center gap-1">
            <div className="h-2 w-2 animate-spin rounded-full border border-gray-300 border-t-[#5B7BFE]" />
            <span className="text-[9px] text-gray-400">识别中…</span>
          </div>
        ) : ocrText ? (
          <p className="mt-1 text-[10px] leading-4 text-gray-400">{ocrText}</p>
        ) : null}
      </div>
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
  const [showSystemTraces, setShowSystemTraces] = useState(false);

  /* Track which attachments are expanded (legacy, kept for export) */
  const [expandedAttachments, setExpandedAttachments] = useState<Set<string>>(new Set());

  /* Fetch immutable snapshot from cloud */
  const loadSnapshot = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await getEventLineReportSnapshot(eventLineId);
      setSnapshot(data);
      setDraft((prev) => {
        // Preserve user edits during silent refresh
        const prevEditMap = new Map<string, { editedTitle?: string; editedSummary?: string }>();
        if (options?.silent && prev) {
          for (const a of prev.activities) {
            if (a.editedTitle || a.editedSummary) {
              prevEditMap.set(a.id, { editedTitle: a.editedTitle, editedSummary: a.editedSummary });
            }
          }
        }
        return {
          eventLineName: prev?.eventLineName ?? data.eventLine.name,
          summary: prev?.summary ?? data.eventLine.summary ?? '',
          activities: data.activities.map((a: EventLineActivity) => ({
            ...a,
            ...(prevEditMap.get(a.id) || {}),
          })),
          attachments: [...data.attachments],
          tasks: [...(data.tasks || [])],
          participantNames: [...data.participantNames],
          snapshotAt: data.snapshotAt,
        };
      });
    } catch (err) {
      if (!options?.silent) {
        setError(err instanceof Error ? err.message : '加载事件线快照失败');
      }
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
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

  /* Build task lookup map: taskId → Task for displaying task details in activities */
  const taskMap = useMemo(() => {
    const m = new Map<string, Task>();
    if (draft) for (const t of (draft.tasks || [])) m.set(t.id, t);
    return m;
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

  /* Auto-save summary with debounce */
  const summaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveSummary = useCallback(
    (newSummary: string) => {
      if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current);
      summaryTimerRef.current = setTimeout(() => {
        void updateEventLine(eventLineId, { summary: newSummary } as Parameters<typeof updateEventLine>[1]).catch(() => {});
      }, 800);
    },
    [eventLineId],
  );
  // Cleanup timer on unmount
  useEffect(() => () => { if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current); }, []);

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
            <h2 className="mt-1 text-[20px] font-bold text-gray-900">{draft.eventLineName}</h2>
            <textarea
              className="mt-2 w-full resize-none rounded-lg border border-transparent bg-transparent px-0 text-[13px] leading-6 text-gray-500 transition hover:border-gray-200 focus:border-[#5B7BFE] focus:bg-white focus:px-2 focus:py-1 focus:outline-none"
              rows={Math.max(2, (draft.summary || '').split('\n').length)}
              placeholder="点击编辑事件线说明…"
              value={draft.summary}
              onChange={(e) => {
                const val = e.target.value;
                setDraft((prev) => prev ? { ...prev, summary: val } : prev);
                saveSummary(val);
              }}
            />
          </div>
          <button
            type="button"
            disabled={!!exportProgress}
            className={`shrink-0 flex items-center gap-2 rounded-2xl px-5 py-2.5 text-[12px] font-bold text-white transition ${exportProgress ? 'bg-blue-400' : 'bg-[#5B7BFE] hover:bg-[#4a6ae8]'}`}
            onClick={() => {
              const exportDraft = {
                ...draft,
                expandedAttachmentIds: Array.from(expandedAttachments),
                docsExpandedActivityIds: Array.from(docsExpandedActivities),
                imagesExpandedActivityIds: Array.from(imagesExpandedActivities),
                showSystemTraces,
              };
              setExportProgress({ stage: '准备导出...', detail: '正在整理事件线数据' });
              void (async () => {
                try {
                  setExportProgress({ stage: '生成文档...', detail: `正在处理 ${draft.activities.length} 条活动记录和 ${draft.attachments.length} 个附件` });
                  const response = await fetch(`${backendBaseUrl}/api/v1/event-lines/${eventLineId}/export-word`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(exportDraft),
                  });
                  if (!response.ok) throw new Error(`导出失败 (${response.status})`);
                  const result = await response.json();
                  if (!result.filePath) throw new Error('后端未返回文件路径');
                  setExportProgress({ stage: '保存文件...', detail: '文档已生成，请选择保存位置' });
                  const saved = await window.yiyuWorkbench?.saveFileAs(result.filePath, result.fileName);
                  if (saved) {
                    setExportProgress({ stage: '导出成功', detail: `已保存到 ${saved}` });
                    setTimeout(() => setExportProgress(null), 2000);
                  } else {
                    setExportProgress(null);
                  }
                } catch (err) {
                  setExportProgress({ stage: '导出失败', detail: err instanceof Error ? err.message : '未知错误' });
                  setTimeout(() => setExportProgress(null), 3000);
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
            {(() => {
              const keyCount = draft.activities.filter((a) => isKeyActivity(a)).length;
              const traceCount = draft.activities.length - keyCount;
              return (
                <div className="flex items-center justify-between">
                  <p className="text-[12px] font-bold text-gray-500">
                    {showSystemTraces ? '全部活动' : '关键活动'}
                  </p>
                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="text-gray-400">{showSystemTraces ? draft.activities.length : keyCount} 条</span>
                    {traceCount > 0 && (
                      <button
                        type="button"
                        className="text-[#5B7BFE] hover:underline"
                        onClick={() => setShowSystemTraces((prev) => !prev)}
                      >
                        {showSystemTraces ? '只看关键活动' : `显示全部（含 ${traceCount} 条系统痕迹）`}
                      </button>
                    )}
                  </div>
                </div>
              );
            })()}

            <div className="mt-3 space-y-1">
              {draft.activities.filter((a) => showSystemTraces || isKeyActivity(a)).map((activity) => {
                const activityAtts = attachmentsByActivity.get(activity.id) || [];
                const imageAtts = activityAtts.filter((a) => (a.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.title));
                const docAtts = activityAtts.filter((a) => !((a.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(a.title)));
                const hasAtts = activityAtts.length > 0;
                const isDocsExpanded = docsExpandedActivities.has(activity.id);
                const isImagesExpanded = imagesExpandedActivities.has(activity.id);

                return (
                  <div
                    key={activity.id}
                    className="group rounded-2xl border border-gray-100 bg-white px-4 py-3 transition hover:border-gray-200"
                  >
                    <div className="space-y-1.5">
                      <div>
                        <p className="text-[14px] font-bold text-gray-900">{activity.title}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px]">
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold text-slate-500">
                            {SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType}
                          </span>
                          <span className="text-gray-400">{formatTs(activity.happenedAt)}</span>
                          {activity.actorName && (
                            <span className="text-gray-400">— {activity.actorName}</span>
                          )}
                        </div>
                      </div>
                      {activity.summary && (
                        <p className="text-[12px] leading-5 text-gray-500 whitespace-pre-wrap">{activity.summary}</p>
                      )}
                      {/* ── 关联任务详情 ── */}
                      {(() => {
                        const taskId = activity.sourceType === 'task_activity'
                          ? activity.sourceId
                          : (activity.metadata?.taskId as string | undefined);
                        const task = taskId ? taskMap.get(taskId) : undefined;
                        // Cloud returns "description", local uses "desc"
                        const taskDesc = task?.desc || (task as Record<string, unknown> | undefined)?.description as string | undefined;
                        if (!task || !taskDesc) return null;
                        return (
                          <div className="mt-1 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                            <p className="text-[11px] font-medium text-slate-500">{task.title}</p>
                            <p className="mt-0.5 text-[11px] leading-4 text-slate-400 whitespace-pre-wrap">{taskDesc}</p>
                          </div>
                        );
                      })()}
                      <div className="flex-1 min-w-0">

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
                                for (const att of activityAtts) {
                                  const link = document.createElement('a');
                                  link.href = `${backendBaseUrl}${att.downloadUrl}`;
                                  link.download = att.title;
                                  link.click();
                                }
                              }}
                            >
                              <Download size={12} />
                            </button>
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

                        {/* 附件文件名列表 — 折叠时显示完整文件名 */}
                        {hasAtts && !isDocsExpanded && !isImagesExpanded && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {activityAtts.map((att) => {
                              const badge = fileTypeBadge(att.title);
                              return (
                                <a
                                  key={att.id}
                                  href={`${backendBaseUrl}${att.downloadUrl}`}
                                  download={att.title}
                                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] text-gray-600 transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
                                  title={`${att.title} · ${fileSizeLabel(att.sizeBytes)}`}
                                >
                                  <span className="rounded px-1 py-0.5 text-[8px] font-bold" style={{ backgroundColor: badge.bg, color: badge.color }}>{badge.label}</span>
                                  {att.title}
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

                        {/* 展开的图片 — 排版显示 + OCR 摘要 */}
                        {isImagesExpanded && imageAtts.length > 0 && (
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            {imageAtts.map((att) => (
                              <ImageWithOcr key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
                            ))}
                          </div>
                        )}
                      </div>

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
