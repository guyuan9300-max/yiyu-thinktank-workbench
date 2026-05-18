import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  X,
  Download,
  Paperclip,
  Clock,
  Users,
  FileBadge,
  FileText,
  Image,
  ExternalLink,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import type {
  EventLineReportSnapshot,
  EventLineReportAttachment,
  EventLineActivity,
  EventLineTimelineNode as BackendEventLineTimelineNode,
  EventLineTimelineNodeKind as BackendEventLineTimelineNodeKind,
  Task,
} from '../../../shared/types.js';
import { getEventLineReportSnapshot, getOrgModelProfile, updateEventLine, getEventLineTimelineNarrative, regenerateEventLineTimelineNarrative } from '../../lib/api.js';
import type { EventLineTimelineNarrative, EventLineNarrativeNode } from '../../../shared/types';

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
  timelineNodes?: EventLineTimelineNode[];
};

type PreviewCard = {
  label: string;
  value: string;
  note: string;
};

type PreviewSection = {
  index: string;
  title: string;
  pages: string;
  summary: string;
};

type PreviewModel = {
  hasRenderableContent: boolean;
  organizationName: string;
  brandCaption: string;
  reportTitle: string;
  reportSubtitle: string;
  coverSummary: string;
  coreJudgment: string;
  coreJudgmentNote: string;
  reviewWindow: string;
  kindLabel: string;
  statusLabel: string;
  statusTone: string;
  clientName: string;
  audienceLabel: string;
  departmentName: string;
  ownerName: string;
  snapshotAtLabel: string;
  participantNames: string[];
  participantSummary: string;
  supportCards: PreviewCard[];
  tocSections: PreviewSection[];
  reviewQuestions: string[];
  deliverables: string[];
  readingSteps: string[];
  readingIntro: string;
  pageOneNote: string;
  pageTwoNote: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
};

type EventLineMaterialGroupKey = 'core' | 'review' | 'supplement' | 'system';
type EventLineMaterialTabKey = EventLineMaterialGroupKey | 'gaps';
type EventLineMaterialBundleKind = 'task' | 'activity' | 'loose' | 'system';

type EventLineMaterialAttachmentGroup = {
  id: string;
  title: string;
  familyLabel: string;
  isImage: boolean;
  primary: EventLineReportAttachment;
  attachments: EventLineReportAttachment[];
  duplicateCount?: number;
  versionCount?: number;
  hasTest: boolean;
  missingDownload: boolean;
};

type EventLineMaterialBundle = {
  id: string;
  group: EventLineMaterialGroupKey;
  kind: EventLineMaterialBundleKind;
  title: string;
  summary: string;
  sourceLabel: string;
  happenedAt: string;
  actorName?: string | null;
  statusLabel?: string;
  tags: string[];
  warnings: string[];
  attachments: EventLineReportAttachment[];
  attachmentGroups: EventLineMaterialAttachmentGroup[];
  duplicateCount?: number;
  versionCount?: number;
  testAttachmentCount?: number;
  missingDownloadCount?: number;
};

type EventLineMaterialAttachmentAnalysis = {
  attachmentGroups: EventLineMaterialAttachmentGroup[];
  duplicateAttachmentCount: number;
  versionConflictCount: number;
  testAttachmentCount: number;
  missingDownloadCount: number;
  imageCount: number;
  docCount: number;
  totalCount: number;
  hasAnyImage: boolean;
  hasOnlyTestAttachments: boolean;
  familyLabels: string[];
};

type EventLineMaterialModel = {
  groups: Record<EventLineMaterialGroupKey, EventLineMaterialBundle[]>;
  gaps: string[];
  duplicateAttachmentCount: number;
  testAttachmentCount: number;
  looseAttachmentCount: number;
};

type LegacyEventLineTimelineNodeKind = 'project_milestone' | 'task_bundle' | 'meeting_material' | 'attachment_bundle' | 'admin_material' | 'system';
type EventLineTimelineNodeKind = BackendEventLineTimelineNodeKind | LegacyEventLineTimelineNodeKind;

type EventLineTimelineNode = Omit<BackendEventLineTimelineNode, 'kind'> & {
  id: string;
  kind: EventLineTimelineNodeKind;
  title: string;
  time: string;
  summary: string;
  sourceTaskId?: string;
  sourceTaskIds?: string[];
  sourceActivityIds: string[];
  attachments: EventLineReportAttachment[];
  materialCount?: number;
  includeInReport?: boolean;
  evidenceSummary: string;
  warnings: string[];
  tags: string[];
  actorName?: string | null;
  ownerName?: string | null;
};

type EventLineTimelineModel = {
  mainNodes: EventLineTimelineNode[];
  reviewNodes: EventLineTimelineNode[];
  systemNodes: EventLineTimelineNode[];
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

const EVENT_LINE_KIND_LABELS: Record<string, string> = {
  project_line: '项目线',
  issue_line: '议题线',
  coordination_line: '协同线',
  case_line: '案例线',
  custom: '事件线',
};

const EVENT_LINE_STATUS_LABELS: Record<string, string> = {
  active: '推进中',
  blocked: '存在阻点',
  paused: '暂缓中',
  done: '已完成',
  archived: '已归档',
};

const EVENT_LINE_STATUS_TONE: Record<string, string> = {
  active: 'border-emerald-300/30 bg-emerald-400/15 text-emerald-50',
  blocked: 'border-rose-300/30 bg-rose-400/15 text-rose-50',
  paused: 'border-amber-300/30 bg-amber-400/15 text-amber-50',
  done: 'border-sky-300/30 bg-sky-400/15 text-sky-50',
  archived: 'border-white/20 bg-white/10 text-white/75',
};

const TASK_STATUS_LABELS: Record<string, string> = {
  inbox: '待确认',
  todo: '待办',
  doing: '推进中',
  done: '已完成',
  rejected: '已取消',
};

const TIMELINE_KIND_LABELS: Record<EventLineTimelineNodeKind, string> = {
  project_start: '项目启动',
  material_intake: '材料入库',
  project_review: '项目复盘',
  continuing_task: '持续推进',
  admin_archive: '行政归档',
  needs_review: '待确认',
  system_trace: '系统痕迹',
  project_milestone: '里程碑',
  task_bundle: '任务节点',
  meeting_material: '会议材料',
  attachment_bundle: '附件材料',
  admin_material: '行政材料',
  system: '系统痕迹',
};

const MATERIAL_GROUP_META: Record<EventLineMaterialTabKey, { label: string; description: string; emptyText: string }> = {
  core: {
    label: '核心素材',
    description: '可直接支撑交接、汇报或阶段判断的材料',
    emptyText: '还没有识别出可直接进入汇报的核心素材。',
  },
  review: {
    label: '待确认',
    description: '重复、多版本、测试文件或来源不完整的材料',
    emptyText: '当前没有需要确认的素材。',
  },
  supplement: {
    label: '补充素材',
    description: '背景、过程、零散说明和辅助材料',
    emptyText: '当前没有补充素材。',
  },
  system: {
    label: '系统痕迹',
    description: '创建、更新、任务变更和附件上传流水',
    emptyText: '当前没有系统痕迹。',
  },
  gaps: {
    label: '待补项',
    description: '根据当前快照自动识别的材料缺口',
    emptyText: '当前没有明显材料缺口。',
  },
};

const MATERIAL_CORE_KEYWORDS = /(会议纪要|纪要|方案|报告|清单|复盘|提纲|设计|输出|交付|诊断|汇报|关键决策|决策|证据|资助方|成果|项目设计|合同|协议|报销|票据|发票|凭证|回签|结项)/u;
const MATERIAL_ACTIVITY_KEYWORDS = /(会议|沟通|拜访|访谈|讨论|复盘|澄清|确认|决策|判断|补充说明|说明)/u;
const SYSTEM_TRACE_KEYWORDS = /(创建事件线|更新事件线|结束事件线|事件线已归档|上传附件|新增任务|任务更新|已归档到任务附件|已归档到事件线附件)/u;

/** Key events: task created, manual note (review content), attachment upload.
 *  Uses backend-computed `isKey` flag; falls back to heuristic for older data. */
function isKeyActivity(activity: { sourceType: string; title: string; summary: string; isKey?: boolean; metadata?: Record<string, unknown> }): boolean {
  if (activity.isKey !== undefined) return activity.isKey;
  // Fallback for activities without backend isKey flag
  if (['manual_note', 'attachment'].includes(activity.sourceType)) return true;
  if (activity.sourceType === 'task_activity' && activity.metadata?.eventType === 'created') return true;
  return false;
}

function isBootstrapActivity(activity: EditableActivity): boolean {
  const metadata = activity.metadata || {};
  const eventType = String((metadata as Record<string, unknown>).eventType || '').toLowerCase();
  if (activity.sourceType === 'task_activity' && eventType === 'created') return true;
  if (eventType === 'event_line_created' || eventType === 'line_created') return true;
  const text = `${previewActivityTitle(activity)} ${previewActivitySummary(activity)}`.toLowerCase();
  return text.includes('创建事件线') || text.includes('created event line');
}

function isMeaningfulPreviewActivity(activity: EditableActivity): boolean {
  if (isBootstrapActivity(activity)) return false;
  return Boolean(previewActivitySummary(activity) || previewActivityTitle(activity));
}

function formatTs(iso: string) {
  if (!iso) return '';
  return iso.slice(0, 16).replace('T', ' ');
}

function formatDateLabel(iso?: string | null) {
  if (!iso) return '待补充';
  return iso.slice(0, 10).replace(/-/g, '.');
}

function truncateText(value: string | null | undefined, maxLength: number) {
  const normalized = (value || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trim()}…`;
}

function normalizeText(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

function dedupeStrings(items: Array<string | null | undefined>) {
  return Array.from(
    new Set(items.map((item) => normalizeText(item)).filter(Boolean)),
  );
}

function formatReadableList(items: string[], limit = 4) {
  const normalized = dedupeStrings(items);
  if (normalized.length === 0) return '';
  if (normalized.length <= limit) return normalized.join('、');
  return `${normalized.slice(0, limit).join('、')} 等`;
}

function previewActivityTitle(activity: EditableActivity) {
  return normalizeText(activity.editedTitle) || normalizeText(activity.title) || '未命名活动';
}

function previewActivitySummary(activity: EditableActivity) {
  return normalizeText(activity.editedSummary) || normalizeText(activity.summary);
}

function isImageAttachment(att: EventLineReportAttachment) {
  return (att.mimeType || '').startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(att.title);
}

function attachmentFamilyLabel(att: EventLineReportAttachment) {
  if (isImageAttachment(att)) return '图像证据';
  const ext = (att.title.split('.').pop() || '').toLowerCase();
  if (ext === 'pdf') return 'PDF 资料';
  if (['doc', 'docx'].includes(ext)) return 'Word 文档';
  if (['xls', 'xlsx'].includes(ext)) return '表格资料';
  if (['ppt', 'pptx'].includes(ext)) return '汇报材料';
  return '补充资料';
}

function fileSizeLabel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function attachmentFamilySummary(attachments: EventLineReportAttachment[]) {
  const familyCounts = new Map<string, number>();
  for (const attachment of attachments) {
    const family = attachmentFamilyLabel(attachment);
    familyCounts.set(family, (familyCounts.get(family) || 0) + 1);
  }
  const entries = Array.from(familyCounts.entries()).sort((left, right) => {
    if (right[1] !== left[1]) return right[1] - left[1];
    return left[0].localeCompare(right[0], 'zh-CN');
  });
  return {
    entries,
    shortText: entries.length > 0 ? entries.slice(0, 3).map(([label]) => label).join('、') : '暂无附件',
    detailedText: entries.length > 0 ? entries.slice(0, 3).map(([label, count]) => `${label}${count}份`).join('、') : '暂无附件材料',
  };
}

function normalizeAttachmentName(title: string) {
  return normalizeText(title).toLowerCase();
}

function formatAttachmentBytes(bytes: number | null | undefined): string {
  const n = Number(bytes || 0);
  if (!n) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function resolveAttachmentUrl(att: EventLineReportAttachment, backendBaseUrl: string) {
  const url = normalizeText(att.downloadUrl);
  if (!url) return '';
  if (/^https?:\/\//i.test(url)) return url;
  return `${backendBaseUrl}${url}`;
}

function resolveAttachmentOpenUrl(att: EventLineReportAttachment, backendBaseUrl: string) {
  const url = normalizeText(att.openUrl) || normalizeText(att.downloadUrl);
  if (!url) return '';
  if (/^https?:\/\//i.test(url)) return url;
  return `${backendBaseUrl}${url}`;
}

function attachmentDisplayTags(att: EventLineReportAttachment) {
  return [
    att.sourceKind === 'task_attachment' ? '强相关' : '原始文件',
    att.documentId ? '已入本轮材料' : '待确认',
    att.parseStatus === 'ready' ? '已解析' : '',
  ].filter(Boolean);
}

function isTestAttachment(att: EventLineReportAttachment) {
  const title = normalizeText(att.title).toLowerCase();
  return /(^|[\/\s_.-])(test|smoke|dummy|sample|demo)([\/\s_.-]|$)/i.test(title) || title.includes('测试');
}

function isAttachmentUploadTrace(activity: EditableActivity) {
  const text = `${previewActivityTitle(activity)} ${previewActivitySummary(activity)}`;
  return activity.sourceType === 'attachment' || /上传附件|归档到任务附件|归档到事件线附件/u.test(text);
}

function isSystemTraceActivity(activity: EditableActivity) {
  const metadata = activity.metadata || {};
  const eventType = String((metadata as Record<string, unknown>).eventType || '').toLowerCase();
  const title = previewActivityTitle(activity);
  const summary = previewActivitySummary(activity);
  const text = `${title} ${summary}`;
  if (isBootstrapActivity(activity) || isAttachmentUploadTrace(activity)) return true;
  if (eventType === 'updated' || eventType === 'created') return true;
  if (SYSTEM_TRACE_KEYWORDS.test(text)) return true;
  return false;
}

function materialTimeDesc(left: EventLineMaterialBundle, right: EventLineMaterialBundle) {
  return (right.happenedAt || '').localeCompare(left.happenedAt || '');
}

function taskStatusLabel(status: string) {
  return TASK_STATUS_LABELS[status] || status || '';
}

function materialSourceLabel(kind: EventLineMaterialBundleKind, fallback: string) {
  if (kind === 'loose') return fallback || '待确认材料';
  if (kind === 'task') return fallback || '关联任务';
  if (kind === 'system') return fallback || '系统痕迹';
  return fallback || '活动';
}

function looseAttachmentFamilyKey(att: EventLineReportAttachment) {
  if (isImageAttachment(att)) return 'image';
  return attachmentFamilyLabel(att);
}

function latestAttachmentTime(attachments: EventLineReportAttachment[], fallback: string) {
  return attachments
    .map((att) => att.createdAt)
    .filter(Boolean)
    .sort((left, right) => right.localeCompare(left))[0] || fallback;
}

function analyzeMaterialAttachments(attachments: EventLineReportAttachment[]): EventLineMaterialAttachmentAnalysis {
  const attachmentBuckets = new Map<string, EventLineReportAttachment[]>();
  for (const attachment of attachments) {
    const key = normalizeAttachmentName(attachment.title) || attachment.id;
    const list = attachmentBuckets.get(key) || [];
    list.push(attachment);
    attachmentBuckets.set(key, list);
  }

  const attachmentGroups: EventLineMaterialAttachmentGroup[] = [];
  let duplicateAttachmentCount = 0;
  let versionConflictCount = 0;
  let testAttachmentCount = 0;
  let missingDownloadCount = 0;
  let imageCount = 0;
  let docCount = 0;
  const familyLabels = new Set<string>();

  for (const [bucketKey, bucket] of attachmentBuckets) {
    const sorted = [...bucket].sort((left, right) => (right.createdAt || '').localeCompare(left.createdAt || ''));
    const primary = sorted[0];
    const familyLabel = attachmentFamilyLabel(primary);
    const isImage = isImageAttachment(primary);
    const uniqueSizes = new Set(sorted.map((item) => Number(item.sizeBytes || 0)));
    const duplicateCount = sorted.length > 1 ? sorted.length : undefined;
    const versionCount = uniqueSizes.size > 1 ? uniqueSizes.size : undefined;
    const hasTest = sorted.some(isTestAttachment);
    const missingDownload = sorted.some((item) => !normalizeText(item.downloadUrl));

    if (duplicateCount) duplicateAttachmentCount += sorted.length - 1;
    if (versionCount) versionConflictCount += 1;
    testAttachmentCount += sorted.filter(isTestAttachment).length;
    missingDownloadCount += sorted.filter((item) => !normalizeText(item.downloadUrl)).length;
    if (isImage) imageCount += sorted.length;
    else docCount += sorted.length;
    familyLabels.add(familyLabel);

    attachmentGroups.push({
      id: `attachment-group:${bucketKey}:${primary.id}`,
      title: normalizeText(primary.title) || '未命名附件',
      familyLabel,
      isImage,
      primary,
      attachments: sorted,
      duplicateCount,
      versionCount,
      hasTest,
      missingDownload,
    });
  }

  attachmentGroups.sort((left, right) => (right.primary.createdAt || '').localeCompare(left.primary.createdAt || ''));

  return {
    attachmentGroups,
    duplicateAttachmentCount,
    versionConflictCount,
    testAttachmentCount,
    missingDownloadCount,
    imageCount,
    docCount,
    totalCount: attachments.length,
    hasAnyImage: imageCount > 0,
    hasOnlyTestAttachments: attachments.length > 0 && testAttachmentCount === attachments.length,
    familyLabels: Array.from(familyLabels),
  };
}

function materialAttachmentTags(analysis: EventLineMaterialAttachmentAnalysis) {
  return [
    analysis.totalCount > 0 ? `素材 ${analysis.totalCount}` : '',
    analysis.imageCount > 0 ? `图片 ${analysis.imageCount}` : '',
    analysis.docCount > 0 ? `文档 ${analysis.docCount}` : '',
  ].filter(Boolean);
}

function materialAttachmentWarnings(analysis: EventLineMaterialAttachmentAnalysis, extraWarnings: string[] = []) {
  return [
    ...extraWarnings,
    analysis.duplicateAttachmentCount > 0 ? `重复附件 ${analysis.duplicateAttachmentCount} 条` : '',
    analysis.versionConflictCount > 0 ? `多版本素材 ${analysis.versionConflictCount} 组` : '',
    analysis.testAttachmentCount > 0 ? `含疑似测试素材 ${analysis.testAttachmentCount} 个` : '',
    analysis.missingDownloadCount > 0 ? `缺少下载地址 ${analysis.missingDownloadCount} 个` : '',
  ].filter(Boolean);
}

function deriveEventLineMaterialModel(snapshot: EventLineReportSnapshot, draft: ReportDraft): EventLineMaterialModel {
  const groups: Record<EventLineMaterialGroupKey, EventLineMaterialBundle[]> = {
    core: [],
    review: [],
    supplement: [],
    system: [],
  };
  const backendNodes = (snapshot.timelineNodes || []).filter((node) => Boolean(node && node.id && node.title));
  if (backendNodes.length > 0) {
    let duplicateAttachmentCount = 0;
    let testAttachmentCount = 0;
    let looseAttachmentCount = 0;
    for (const node of backendNodes) {
      const attachments = Array.isArray(node.attachments) ? node.attachments : [];
      const analysis = analyzeMaterialAttachments(attachments);
      duplicateAttachmentCount += analysis.duplicateAttachmentCount;
      testAttachmentCount += analysis.testAttachmentCount;
      if (node.kind === 'needs_review') looseAttachmentCount += attachments.filter((att) => !normalizeText(att.taskId)).length;
      const group: EventLineMaterialGroupKey = node.kind === 'system_trace'
        ? 'system'
        : node.kind === 'needs_review'
          ? 'review'
          : node.kind === 'admin_archive'
            ? 'supplement'
            : 'core';
      groups[group].push({
        id: `node:${node.id}`,
        group,
        kind: node.kind === 'system_trace' ? 'system' : node.sourceTaskId || (node.sourceTaskIds || []).length > 0 ? 'task' : 'activity',
        title: node.title,
        summary: truncateText(node.summary || node.evidenceSummary || '', 180),
        sourceLabel: TIMELINE_KIND_LABELS[node.kind] || '事件节点',
        happenedAt: node.time || draft.snapshotAt,
        actorName: node.ownerName || node.actorName,
        statusLabel: node.kind === 'needs_review' ? '待确认' : '',
        tags: [
          ...(node.tags || []),
          ...materialAttachmentTags(analysis),
        ].filter(Boolean),
        warnings: materialAttachmentWarnings(analysis, node.warnings || []),
        attachments,
        attachmentGroups: analysis.attachmentGroups,
        duplicateCount: analysis.duplicateAttachmentCount || undefined,
        versionCount: analysis.versionConflictCount || undefined,
        testAttachmentCount: analysis.testAttachmentCount || undefined,
        missingDownloadCount: analysis.missingDownloadCount || undefined,
      });
    }
    for (const key of Object.keys(groups) as EventLineMaterialGroupKey[]) {
      groups[key] = groups[key].sort(materialTimeDesc);
    }
    const gaps = [
      normalizeText(snapshot.eventLine.recentDecision) ? '' : '缺关键决策：建议补“为什么形成今天这个判断”。',
      normalizeText(snapshot.eventLine.nextStep) ? '' : '缺下一步：建议补负责人、动作和时间点。',
      normalizeText(snapshot.eventLine.currentBlocker) ? '' : '缺当前阻塞：建议补这条线现在卡在哪里。',
      groups.review.length > 0 ? `存在待确认材料：${groups.review.length} 个节点需要补归属、清理测试素材或等待解析。` : '',
    ].filter(Boolean);
    return {
      groups,
      gaps,
      duplicateAttachmentCount,
      testAttachmentCount,
      looseAttachmentCount,
    };
  }
  const taskMap = new Map((draft.tasks || []).map((task) => [task.id, task]));
  let duplicateAttachmentCount = 0;
  let testAttachmentCount = 0;
  let looseAttachmentCount = 0;

  const pushMaterial = (bundle: EventLineMaterialBundle) => {
    groups[bundle.group].push(bundle);
  };

  const taskAttachmentMap = new Map<string, EventLineReportAttachment[]>();
  const looseAttachmentMap = new Map<string, EventLineReportAttachment[]>();

  for (const attachment of draft.attachments) {
    const taskId = normalizeText(attachment.taskId);
    if (taskId && taskMap.has(taskId)) {
      const list = taskAttachmentMap.get(taskId) || [];
      list.push(attachment);
      taskAttachmentMap.set(taskId, list);
      continue;
    }
    const looseKey = looseAttachmentFamilyKey(attachment);
    const list = looseAttachmentMap.get(looseKey) || [];
    list.push(attachment);
    looseAttachmentMap.set(looseKey, list);
  }

  for (const task of draft.tasks || []) {
    const title = normalizeText(task.title);
    const taskLike = task as unknown as Record<string, unknown>;
    const description = normalizeText(task.desc || (typeof taskLike.description === 'string' ? taskLike.description : undefined));
    const taskAttachments = taskAttachmentMap.get(task.id) || [];
    const analysis = analyzeMaterialAttachments(taskAttachments);
    const contextText = [
      title,
      description,
      normalizeText(task.currentBlocker),
      normalizeText(task.nextAction),
      normalizeText(task.recentDecision),
      taskAttachments.map((attachment) => attachment.title).join(' '),
    ].join(' ');
    // 「按任务查看」必须列出完整任务列表 —— 不再用关键词过滤"是否有汇报价值"。
    // 没标题的任务才跳过(数据异常); 即使没附件、没关键词也保留一个骨架卡片。
    if (!title) continue;
    const hasMaterialContext = taskAttachments.length > 0 || MATERIAL_CORE_KEYWORDS.test(contextText);

    duplicateAttachmentCount += analysis.duplicateAttachmentCount;
    testAttachmentCount += analysis.testAttachmentCount;
    const hasCoreSignal = MATERIAL_CORE_KEYWORDS.test(contextText) || analysis.hasAnyImage;
    const hasReviewSignal = (
      analysis.testAttachmentCount > 0
      || analysis.versionConflictCount > 0
      || analysis.missingDownloadCount > 0
      || analysis.hasOnlyTestAttachments
    );
    const group: EventLineMaterialGroupKey = hasReviewSignal ? 'review' : hasCoreSignal ? 'core' : 'supplement';
    const familyText = analysis.familyLabels.length > 0 ? analysis.familyLabels.slice(0, 3).join('、') : '';
    const warnings = materialAttachmentWarnings(analysis, [
      taskAttachments.length > 0 && !description ? '任务缺少说明，建议补充这组材料要证明什么' : '',
    ]);

    pushMaterial({
      id: `task:${task.id}`,
      group,
      kind: 'task',
      title,
      summary: truncateText(description || (taskAttachments.length > 0 ? `这组材料来自任务附件，包含 ${taskAttachments.length} 个素材${familyText ? `（${familyText}）` : ''}。` : ''), 160),
      sourceLabel: materialSourceLabel('task', group === 'core' ? '任务材料包' : '关联任务'),
      happenedAt: latestAttachmentTime(taskAttachments, task.updatedAt || task.createdAt || draft.snapshotAt),
      actorName: task.ownerName,
      statusLabel: taskStatusLabel(task.status),
      tags: [
        '任务材料包',
        taskStatusLabel(task.status),
        hasCoreSignal ? '可进汇报' : '过程材料',
        ...materialAttachmentTags(analysis),
      ].filter(Boolean),
      warnings,
      attachments: taskAttachments,
      attachmentGroups: analysis.attachmentGroups,
      duplicateCount: analysis.duplicateAttachmentCount || undefined,
      versionCount: analysis.versionConflictCount || undefined,
      testAttachmentCount: analysis.testAttachmentCount || undefined,
      missingDownloadCount: analysis.missingDownloadCount || undefined,
    });
  }

  for (const [looseKey, attachments] of looseAttachmentMap) {
    const analysis = analyzeMaterialAttachments(attachments);
    const latest = [...attachments].sort((left, right) => (right.createdAt || '').localeCompare(left.createdAt || ''))[0];
    const familyLabel = looseKey === 'image' ? '图片素材' : looseKey;
    duplicateAttachmentCount += analysis.duplicateAttachmentCount;
    testAttachmentCount += analysis.testAttachmentCount;
    looseAttachmentCount += attachments.length;

    pushMaterial({
      id: `loose:${looseKey}`,
      group: 'review',
      kind: 'loose',
      title: looseKey === 'image' ? '图片材料主题待确认' : `${familyLabel}主题待确认`,
      summary: `这些附件暂时缺少清晰业务上下文，先作为待确认材料保留。建议后续绑定到具体任务或补充说明。`,
      sourceLabel: materialSourceLabel('loose', '待确认材料'),
      happenedAt: latest?.createdAt || draft.snapshotAt,
      actorName: latest?.actorName,
      statusLabel: '待确认',
      tags: ['待确认', ...materialAttachmentTags(analysis)],
      warnings: materialAttachmentWarnings(analysis, ['缺少任务/活动归属']),
      attachments,
      attachmentGroups: analysis.attachmentGroups,
      duplicateCount: analysis.duplicateAttachmentCount || undefined,
      versionCount: analysis.versionConflictCount || undefined,
      testAttachmentCount: analysis.testAttachmentCount || undefined,
      missingDownloadCount: analysis.missingDownloadCount || undefined,
    });
  }

  for (const activity of draft.activities) {
    const title = previewActivityTitle(activity);
    const summary = previewActivitySummary(activity);
    const sourceLabel = SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType;
    const task = activity.sourceType === 'task_activity' ? taskMap.get(activity.sourceId) : undefined;
    const taskText = task ? `${task.title} ${task.desc || ''}` : '';
    const text = `${title} ${summary} ${taskText}`;

    if (isSystemTraceActivity(activity)) {
      pushMaterial({
        id: `activity:${activity.id}`,
        group: 'system',
        kind: 'system',
        title,
        summary: summary || title,
        sourceLabel: materialSourceLabel('system', sourceLabel),
        happenedAt: activity.happenedAt,
        actorName: activity.actorName,
        tags: ['系统记录'],
        warnings: [],
        attachments: [],
        attachmentGroups: [],
      });
      continue;
    }

    if (activity.sourceType === 'task_activity' && taskMap.has(activity.sourceId)) continue;
    if (!summary && !MATERIAL_ACTIVITY_KEYWORDS.test(text)) continue;
    const group: EventLineMaterialGroupKey = (
      isKeyActivity(activity)
      || activity.sourceType === 'manual_note'
      || activity.sourceType === 'meeting'
      || activity.sourceType === 'support_request'
      || activity.sourceType === 'review'
      || MATERIAL_CORE_KEYWORDS.test(text)
    ) ? 'core' : 'supplement';

    pushMaterial({
      id: `activity:${activity.id}`,
      group,
      kind: 'activity',
      title,
      summary: truncateText(summary || title, 160),
      sourceLabel: materialSourceLabel('activity', sourceLabel),
      happenedAt: activity.happenedAt,
      actorName: activity.actorName,
      tags: [activity.sourceType === 'manual_note' ? '补充说明' : sourceLabel, group === 'core' ? '支撑判断' : '过程记录'].filter(Boolean),
      warnings: [],
      attachments: [],
      attachmentGroups: [],
    });
  }

  for (const key of Object.keys(groups) as EventLineMaterialGroupKey[]) {
    groups[key] = groups[key].sort(materialTimeDesc);
  }

  const meaningfulActivities = [...groups.core, ...groups.supplement].filter((item) => item.kind === 'activity');
  const gaps = [
    meaningfulActivities.some((item) => MATERIAL_ACTIVITY_KEYWORDS.test(`${item.title} ${item.summary}`))
      ? ''
      : '缺关键沟通记录：建议补一次会议纪要、访谈记录或阶段沟通说明。',
    draft.attachments.length > 0 ? '' : '缺原始材料或交付底稿：建议上传可支撑判断的附件。',
    normalizeText(snapshot.eventLine.recentDecision) ? '' : '缺关键决策：建议补“为什么形成今天这个判断”。',
    normalizeText(snapshot.eventLine.nextStep) ? '' : '缺下一步：建议补负责人、动作和时间点。',
    normalizeText(snapshot.eventLine.currentBlocker) ? '' : '缺当前阻塞：建议补这条线现在卡在哪里。',
    duplicateAttachmentCount || testAttachmentCount
      ? `存在待清理素材：${duplicateAttachmentCount ? `重复附件 ${duplicateAttachmentCount} 条` : ''}${duplicateAttachmentCount && testAttachmentCount ? '，' : ''}${testAttachmentCount ? `测试文件 ${testAttachmentCount} 条` : ''}。`
      : '',
    looseAttachmentCount ? `存在待确认素材：${looseAttachmentCount} 个附件缺少任务或活动上下文，建议后续绑定到具体任务。` : '',
  ].filter(Boolean);

  return {
    groups,
    gaps,
    duplicateAttachmentCount,
    testAttachmentCount,
    looseAttachmentCount,
  };
}

function attachmentParsedPreview(att: EventLineReportAttachment) {
  return normalizeText(att.parsedPreview);
}

function hasMeetingSignal(text: string) {
  return /(会议纪要|沟通会|沟通会议|会议|纪要|复盘)/u.test(text);
}

function hasAdminMaterialSignal(text: string) {
  return /(报销|票据|发票|凭证|收据|行政)/u.test(text);
}

function parsedEvidenceSummary(attachments: EventLineReportAttachment[]) {
  const parsed = attachments
    .filter((att) => !isTestAttachment(att))
    .map((att) => attachmentParsedPreview(att))
    .filter(Boolean);
  return truncateText(dedupeStrings(parsed).join(' '), 260);
}

function attachmentBasisTags(attachments: EventLineReportAttachment[]) {
  const tags = new Set<string>();
  for (const attachment of attachments) {
    const title = normalizeText(attachment.title);
    const preview = attachmentParsedPreview(attachment);
    if (hasMeetingSignal(`${title} ${preview}`)) tags.add('来自会议纪要');
    if (isImageAttachment(attachment)) tags.add(hasAdminMaterialSignal(`${title} ${preview}`) ? '来自票据 OCR' : '来自图片证据');
    if (attachment.documentId) tags.add(attachment.parseStatus === 'ready' ? '数据中心已解析' : '待解析');
  }
  return Array.from(tags);
}

function timelineNodeTime(attachments: EventLineReportAttachment[], fallback?: string | null) {
  const latest = latestAttachmentTime(attachments, fallback || '');
  return latest || fallback || '';
}

function timelineNodeSummary({
  title,
  description,
  attachments,
  kind,
}: {
  title: string;
  description: string;
  attachments: EventLineReportAttachment[];
  kind: EventLineTimelineNodeKind;
}) {
  const evidence = parsedEvidenceSummary(attachments);
  if (evidence) {
    if (kind === 'meeting_material') return truncateText(evidence, 220);
    if (kind === 'admin_material') return truncateText(`${title}已形成材料归档。${evidence}`, 220);
    return truncateText(evidence, 220);
  }
  if (description) return truncateText(description, 220);
  if (attachments.length > 0) {
    const family = attachmentFamilySummary(attachments).detailedText;
    return `这一步归集了 ${attachments.length} 个附件，主要包括${family}，可在节点内预览或下载。`;
  }
  return '这一步已进入事件线，后续可继续补充任务说明、会议纪要或附件依据。';
}

function deriveEventLineTimelineModel(snapshot: EventLineReportSnapshot, draft: ReportDraft): EventLineTimelineModel {
  const taskMap = new Map((draft.tasks || []).map((task) => [task.id, task]));
  const attachmentByTask = new Map<string, EventLineReportAttachment[]>();
  const looseAttachments: EventLineReportAttachment[] = [];
  for (const attachment of draft.attachments || []) {
    const taskId = normalizeText(attachment.taskId);
    if (taskId && taskMap.has(taskId)) {
      const list = attachmentByTask.get(taskId) || [];
      list.push(attachment);
      attachmentByTask.set(taskId, list);
    } else {
      looseAttachments.push(attachment);
    }
  }

  const activityIdsByTask = new Map<string, string[]>();
  const systemNodes: EventLineTimelineNode[] = [];
  for (const activity of draft.activities || []) {
    const metadata = activity.metadata || {};
    const metadataTaskId = normalizeText((metadata as Record<string, unknown>).taskId as string | undefined);
    const taskId = activity.sourceType === 'task_activity' ? normalizeText(activity.sourceId) : metadataTaskId;
    if (taskId) {
      const ids = activityIdsByTask.get(taskId) || [];
      ids.push(activity.id);
      activityIdsByTask.set(taskId, ids);
    }
    if (isSystemTraceActivity(activity)) {
      systemNodes.push({
        id: `system:${activity.id}`,
        kind: 'system',
        title: previewActivityTitle(activity),
        time: activity.happenedAt,
        summary: previewActivitySummary(activity) || previewActivityTitle(activity),
        sourceActivityIds: [activity.id],
        attachments: [],
        evidenceSummary: '',
        warnings: [],
        tags: ['系统痕迹'],
        actorName: activity.actorName,
      });
    }
  }

  const mainNodes: EventLineTimelineNode[] = [];
  const reviewNodes: EventLineTimelineNode[] = [];

  if (normalizeText(snapshot.eventLine.summary) || normalizeText(snapshot.eventLine.intent)) {
    mainNodes.push({
      id: `event-line:${snapshot.eventLine.id}:overview`,
      kind: 'project_milestone',
      title: '项目启动',
      time: snapshot.eventLine.createdAt || draft.snapshotAt,
      summary: truncateText(normalizeText(snapshot.eventLine.intent) || normalizeText(snapshot.eventLine.summary), 220),
      sourceActivityIds: [],
      attachments: [],
      evidenceSummary: '',
      warnings: [],
      tags: ['项目启动'],
      actorName: snapshot.eventLine.ownerName,
      ownerName: snapshot.eventLine.ownerName,
    });
  }

  for (const task of draft.tasks || []) {
    const title = normalizeText(task.title);
    if (!title) continue;
    const taskLike = task as unknown as Record<string, unknown>;
    const description = normalizeText(task.desc || (typeof taskLike.description === 'string' ? taskLike.description : undefined));
    const attachments = attachmentByTask.get(task.id) || [];
    const contextText = `${title} ${description} ${attachments.map((att) => `${att.title} ${attachmentParsedPreview(att)}`).join(' ')}`;
    const nonTestAttachments = attachments.filter((att) => !isTestAttachment(att));
    const hasOnlyTest = attachments.length > 0 && nonTestAttachments.length === 0;
    const kind: EventLineTimelineNodeKind = hasAdminMaterialSignal(contextText)
      ? 'admin_material'
      : hasMeetingSignal(contextText)
        ? 'meeting_material'
        : 'task_bundle';
    const node: EventLineTimelineNode = {
      id: `task:${task.id}`,
      kind,
      title,
      time: timelineNodeTime(attachments, task.updatedAt || task.createdAt || draft.snapshotAt),
      summary: timelineNodeSummary({ title, description, attachments: nonTestAttachments, kind }),
      sourceTaskId: task.id,
      sourceActivityIds: activityIdsByTask.get(task.id) || [],
      attachments,
      evidenceSummary: parsedEvidenceSummary(nonTestAttachments),
      warnings: [
        hasOnlyTest ? '该任务下只有疑似测试素材，未纳入主线判断。' : '',
        attachments.some((att) => att.documentId && att.parseStatus !== 'ready') ? '部分附件仍待数据中心解析完成。' : '',
      ].filter(Boolean),
      tags: [
        kind === 'meeting_material' ? '会议/复盘节点' : kind === 'admin_material' ? '行政材料' : '任务节点',
        ...attachmentBasisTags(nonTestAttachments),
        attachments.length > 0 ? `附件 ${attachments.length}` : '',
        taskStatusLabel(task.status),
      ].filter(Boolean),
      actorName: task.creatorName,
      ownerName: task.ownerName,
    };
    if (hasOnlyTest) reviewNodes.push(node);
    else mainNodes.push(node);
  }

  const looseGroups = new Map<string, EventLineReportAttachment[]>();
  for (const attachment of looseAttachments) {
    const key = isImageAttachment(attachment) ? 'image' : normalizeAttachmentName(attachment.title).replace(/\(\d+\)(?=\.[^.]+$)/, '');
    const list = looseGroups.get(key) || [];
    list.push(attachment);
    looseGroups.set(key, list);
  }
  for (const [key, attachments] of looseGroups) {
    const nonTestAttachments = attachments.filter((att) => !isTestAttachment(att));
    const latest = [...attachments].sort((left, right) => (right.createdAt || '').localeCompare(left.createdAt || ''))[0];
    const contextText = attachments.map((att) => `${att.title} ${attachmentParsedPreview(att)}`).join(' ');
    const kind: EventLineTimelineNodeKind = hasAdminMaterialSignal(contextText)
      ? 'admin_material'
      : hasMeetingSignal(contextText)
        ? 'meeting_material'
        : 'attachment_bundle';
    const node: EventLineTimelineNode = {
      id: `loose:${key}`,
      kind,
      title: kind === 'meeting_material'
        ? '会议材料主题待确认'
        : kind === 'admin_material'
          ? '行政材料主题待确认'
          : latest && isImageAttachment(latest) ? '图片材料主题待确认' : `${latest?.title || key}主题待确认`,
      time: latest?.createdAt || draft.snapshotAt,
      summary: timelineNodeSummary({
        title: latest?.title || '待确认素材',
        description: '',
        attachments: nonTestAttachments,
        kind,
      }),
      sourceActivityIds: [],
      attachments,
      evidenceSummary: parsedEvidenceSummary(nonTestAttachments),
      warnings: [
        '缺少任务/活动归属。',
        attachments.some((att) => !att.documentId) ? '部分附件尚未完成资料库解析。' : '',
        attachments.some((att) => att.documentId && att.parseStatus !== 'ready') ? '部分附件仍待数据中心解析完成。' : '',
      ].filter(Boolean),
      tags: ['待确认', ...attachmentBasisTags(nonTestAttachments), attachments.length > 0 ? `附件 ${attachments.length}` : ''].filter(Boolean),
      actorName: latest?.actorName,
    };
    if (kind === 'meeting_material' || kind === 'admin_material') mainNodes.push(node);
    else reviewNodes.push(node);
  }

  const nonSystemActivities = (draft.activities || [])
    .filter((activity) => !isSystemTraceActivity(activity))
    .filter((activity) => !(activity.sourceType === 'task_activity' && taskMap.has(activity.sourceId)))
    .filter((activity) => previewActivitySummary(activity) || MATERIAL_ACTIVITY_KEYWORDS.test(`${previewActivityTitle(activity)} ${previewActivitySummary(activity)}`));
  for (const activity of nonSystemActivities) {
    mainNodes.push({
      id: `activity:${activity.id}`,
      kind: activity.sourceType === 'meeting' ? 'meeting_material' : 'project_milestone',
      title: previewActivityTitle(activity),
      time: activity.happenedAt,
      summary: truncateText(previewActivitySummary(activity) || previewActivityTitle(activity), 220),
      sourceActivityIds: [activity.id],
      attachments: [],
      evidenceSummary: '',
      warnings: [],
      tags: [SOURCE_TYPE_LABELS[activity.sourceType] || activity.sourceType, '关键记录'],
      actorName: activity.actorName,
    });
  }

  const byTime = (left: EventLineTimelineNode, right: EventLineTimelineNode) => (left.time || '').localeCompare(right.time || '');
  return {
    mainNodes: mainNodes.sort(byTime),
    reviewNodes: reviewNodes.sort(byTime),
    systemNodes: systemNodes.sort(byTime),
  };
}

function normalizeBackendTimelineNode(node: BackendEventLineTimelineNode): EventLineTimelineNode {
  const sourceTaskIds = Array.isArray(node.sourceTaskIds)
    ? node.sourceTaskIds.filter(Boolean)
    : (node.sourceTaskId ? [node.sourceTaskId] : []);
  return {
    ...node,
    time: node.time || '',
    summary: node.summary || '',
    sourceTaskIds,
    sourceTaskId: node.sourceTaskId || sourceTaskIds[0] || '',
    sourceActivityIds: Array.isArray(node.sourceActivityIds) ? node.sourceActivityIds : [],
    attachments: Array.isArray(node.attachments) ? node.attachments : [],
    evidenceSummary: node.evidenceSummary || '',
    warnings: Array.isArray(node.warnings) ? node.warnings : [],
    tags: Array.isArray(node.tags) ? node.tags : [],
  };
}

function buildEventLineTimelineModel(snapshot: EventLineReportSnapshot, draft: ReportDraft): EventLineTimelineModel {
  const backendNodes = (snapshot.timelineNodes || [])
    .filter((node): node is BackendEventLineTimelineNode => Boolean(node && node.id && node.title))
    .map(normalizeBackendTimelineNode);
  if (backendNodes.length === 0) {
    return deriveEventLineTimelineModel(snapshot, draft);
  }
  const byTime = (left: EventLineTimelineNode, right: EventLineTimelineNode) => (left.time || '').localeCompare(right.time || '');
  // P0 · 主线还原只留有叙事价值的节点 kind:
  //   project_start / material_intake / project_review / project_milestone / key_turning_point
  // 砍掉 continuing_task / admin_archive: 这些是任务流水, 属于"按任务查看"管辖,
  // 留在主线只会让用户在 N 张卡片里找不到真正的转折点。
  const MAIN_KIND_BLACKLIST = new Set(['needs_review', 'system_trace', 'continuing_task', 'admin_archive']);
  return {
    mainNodes: backendNodes
      .filter((node) => !MAIN_KIND_BLACKLIST.has(node.kind))
      .sort(byTime),
    reviewNodes: backendNodes
      .filter((node) => node.kind === 'needs_review')
      .sort(byTime),
    systemNodes: backendNodes
      .filter((node) => node.kind === 'system_trace')
      .sort(byTime),
  };
}

function previewPageLabel(index: number, isLast: boolean) {
  const startPage = 3 + index * 2;
  if (isLast) return `P${String(startPage).padStart(2, '0')}+`;
  return `P${String(startPage).padStart(2, '0')}-P${String(startPage + 1).padStart(2, '0')}`;
}

function buildCoreJudgmentText({
  blockerText,
  decisionText,
  nextStepText,
  latestSignals,
}: {
  blockerText: string;
  decisionText: string;
  nextStepText: string;
  latestSignals: string[];
}) {
  if (decisionText && nextStepText) {
    return `已形成“${truncateText(decisionText, 28)}”，当前要把“${truncateText(nextStepText, 28)}”继续推进到明确结果。`;
  }
  if (blockerText && nextStepText) {
    return `当前卡点是“${truncateText(blockerText, 28)}”，需要围绕“${truncateText(nextStepText, 28)}”继续收束责任人与时间点。`;
  }
  if (decisionText) {
    return `最近已经形成“${truncateText(decisionText, 34)}”，下一步重点是确认这个判断是否真正带动了后续推进。`;
  }
  if (nextStepText) {
    return `当前最需要盯住的是“${truncateText(nextStepText, 34)}”，确保这一步不再停留在口头判断。`;
  }
  if (latestSignals.length >= 2) {
    return `最近的关键推进集中在“${truncateText(latestSignals[0], 26)}”和“${truncateText(latestSignals[1], 26)}”。`;
  }
  if (latestSignals.length === 1) {
    return `目前最值得关注的进展是“${truncateText(latestSignals[0], 40)}”。`;
  }
  return '当前资料不足，建议先补活动记录、阶段判断或附件材料，再生成对外汇报。';
}

function deriveReportPreview(
  snapshot: EventLineReportSnapshot,
  draft: ReportDraft,
  visibleActivities: EditableActivity[],
  organizationName: string,
): PreviewModel {
  const eventLine = snapshot.eventLine;
  const sortedActivities = [...visibleActivities].sort((left, right) => left.happenedAt.localeCompare(right.happenedAt));
  const meaningfulActivities = sortedActivities.filter((activity) => isMeaningfulPreviewActivity(activity));
  const keyActivities = meaningfulActivities.filter((activity) => isKeyActivity(activity));
  const milestoneSource = keyActivities.length > 0 ? keyActivities : meaningfulActivities;
  const latestMilestone = milestoneSource[milestoneSource.length - 1] || null;
  const latestMilestoneSignal = latestMilestone
    ? previewActivitySummary(latestMilestone) || previewActivityTitle(latestMilestone)
    : '';
  const latestSignals = milestoneSource
    .slice(-2)
    .reverse()
    .map((activity) => previewActivitySummary(activity) || previewActivityTitle(activity));
  const clientName = normalizeText(eventLine.primaryClientName);
  const kindLabel = EVENT_LINE_KIND_LABELS[eventLine.kind] || '事件线';
  const statusLabel = EVENT_LINE_STATUS_LABELS[eventLine.status] || eventLine.status;
  const statusTone = EVENT_LINE_STATUS_TONE[eventLine.status] || EVENT_LINE_STATUS_TONE.archived;
  const blockerText = normalizeText(eventLine.currentBlocker);
  const decisionText = normalizeText(eventLine.recentDecision);
  const nextStepText = normalizeText(eventLine.nextStep);
  const ownerName = normalizeText(eventLine.ownerName) || '待指定负责人';
  const departmentName = normalizeText(eventLine.primaryDepartmentName) || '未设置归属部门';
  const attachmentCount = draft.attachments.length;
  const taskCount = draft.tasks.length;
  const completedTaskCount = draft.tasks.filter((task) => task.status === 'done').length;
  const pendingTaskCount = draft.tasks.filter((task) => !['done', 'rejected'].includes(task.status)).length;
  const participantSummary = formatReadableList(draft.participantNames, 4) || ownerName;
  const familySummary = attachmentFamilySummary(draft.attachments);
  const startAt = sortedActivities[0]?.happenedAt || eventLine.createdAt || snapshot.snapshotAt;
  const endAt = sortedActivities[sortedActivities.length - 1]?.happenedAt || snapshot.snapshotAt || eventLine.updatedAt;
  const reviewWindow = `${formatDateLabel(startAt)} - ${formatDateLabel(endAt)}`;
  const hasNarrativeEvidence = [
    normalizeText(eventLine.intent),
    normalizeText(draft.summary),
    normalizeText(eventLine.summary),
    blockerText,
    decisionText,
    nextStepText,
  ].some((item) => item.length >= 6);
  const hasRenderableContent = (
    meaningfulActivities.length >= 2
    || (meaningfulActivities.length >= 1 && (attachmentCount > 0 || taskCount > 0))
    || hasNarrativeEvidence
    || attachmentCount > 0
    || taskCount >= 2
  );

  const reportTitle = normalizeText(draft.eventLineName) || normalizeText(eventLine.name) || '事件线汇报';
  const reportSubtitle = clientName ? `${clientName} · ${kindLabel}汇报` : `${kindLabel}汇报`;
  const normalizedOrganizationName = normalizeText(organizationName) || '当前组织';
  const emptySummaryFallback = '当前资料不足，暂无法生成模拟汇报。请先在素材清单中补充活动说明、阶段判断或附件材料。';
  const coverSummarySource = (
    normalizeText(eventLine.intent)
      || normalizeText(draft.summary)
      || normalizeText(eventLine.summary)
      || (hasRenderableContent ? latestMilestoneSignal : '')
  );
  const coverSummary = truncateText(
    coverSummarySource || emptySummaryFallback,
    122,
  ) || emptySummaryFallback;

  const contentScaleValue = `关键 ${milestoneSource.length} / 活动 ${sortedActivities.length}`;
  const contentScaleNote = `附件 ${attachmentCount} · 任务 ${taskCount}`;

  const sectionSeeds = [
    {
      title: '事件背景与目标',
      summary: truncateText(
        normalizeText(eventLine.intent)
          || normalizeText(draft.summary)
          || normalizeText(eventLine.summary)
          || `${kindLabel}当前处于“${statusLabel}”，需要先补充阶段背景与目标说明。`,
        82,
      ),
    },
    {
      title: '关键里程碑',
      summary: milestoneSource.length > 0
        ? truncateText(`已记录 ${milestoneSource.length} 条关键活动，最近一条是“${previewActivityTitle(latestMilestone || milestoneSource[0])}”。`, 82)
        : '尚未沉淀关键里程碑，建议先在素材清单里补充活动记录。',
    },
    {
      title: '任务推进',
      summary: taskCount > 0
        ? truncateText(`关联任务 ${taskCount} 条，已完成 ${completedTaskCount} 条，待推进 ${pendingTaskCount} 条。${nextStepText ? `当前下一步是“${nextStepText}”。` : ''}`, 82)
        : '当前没有关联任务，建议补充执行动作、责任人和时间点。',
    },
    {
      title: '材料与证据',
      summary: attachmentCount > 0 || eventLine.evidenceCount > 0
        ? truncateText(`当前已有 ${attachmentCount} 份附件，材料类型覆盖 ${familySummary.detailedText}。证据计数 ${eventLine.evidenceCount}。`, 82)
        : '暂未沉淀附件材料，导出时只能依赖活动描述与阶段判断。',
    },
    {
      title: '风险与阻点',
      summary: blockerText
        ? truncateText(`当前主要阻点是“${blockerText}”，需要核对是否已有明确应对动作。`, 82)
        : pendingTaskCount > 0
          ? truncateText(`仍有 ${pendingTaskCount} 条未完成任务需要推进，建议重点关注依赖关系与节奏风险。`, 82)
          : '当前没有突出的阻点记录，但仍建议在复盘中核对潜在风险。',
    },
    {
      title: '决策与下一步',
      summary: decisionText || nextStepText
        ? truncateText(`最近决策：${decisionText || '待补充'}。下一步：${nextStepText || '待补充'}。`, 82)
        : latestMilestoneSignal
          ? truncateText(`可以从最近活动“${latestMilestoneSignal}”继续推演下一步动作。`, 82)
          : '尚未形成明确的下一步动作，建议先补阶段判断。',
    },
  ];

  if (draft.participantNames.length > 0 || normalizeText(eventLine.ownerName) || normalizeText(eventLine.primaryDepartmentName)) {
    sectionSeeds.push({
      title: '协作与责任',
      summary: truncateText(`负责人 ${ownerName}，归属 ${departmentName}，当前参与者 ${participantSummary}。`, 82),
    });
  }

  const tocSections = sectionSeeds.slice(0, 7).map((section, index, array) => ({
    index: String(index + 1).padStart(2, '0'),
    title: section.title,
    pages: previewPageLabel(index, index === array.length - 1),
    summary: section.summary,
  }));

  const readingSteps = dedupeStrings([
    blockerText ? `先看风险与阻点，确认“${truncateText(blockerText, 18)}”是否已有应对动作。` : '',
    pendingTaskCount > 0 ? `再看任务推进，优先识别 ${pendingTaskCount} 条未完成任务里最影响节奏的部分。` : '',
    attachmentCount > 0 ? `随后核对材料与证据，确认现有 ${attachmentCount} 份附件是否足够支撑当前判断。` : '',
    nextStepText ? `最后检查下一步“${truncateText(nextStepText, 18)}”是否已经落实到责任人与时间点。` : '',
  ]);
  while (readingSteps.length < 3) {
    readingSteps.push(
      [
        '先建立这条事件线当前的阶段判断，再回到活动和附件核对事实依据。',
        '把关键活动、关联任务和当前阻点对齐，避免只看动作不看收束程度。',
        '最后确认下一步动作是否足够明确，便于直接用于后续协作或导出。',
      ][readingSteps.length],
    );
  }

  const reviewQuestions = dedupeStrings([
    blockerText ? `当前阻点“${truncateText(blockerText, 22)}”是否已经拆成了具体应对动作？` : '',
    decisionText ? `最近形成的关键决策“${truncateText(decisionText, 22)}”会怎样影响后续推进？` : '',
    nextStepText ? `下一步“${truncateText(nextStepText, 22)}”是否已经落实到责任人与时间点？` : '',
    pendingTaskCount > 0 ? `剩余 ${pendingTaskCount} 条未完成任务里，哪一条最影响整体推进节奏？` : '',
    attachmentCount > 0 ? `现有 ${attachmentCount} 份材料是否足以支撑当前判断与对外汇报？` : '',
    milestoneSource.length > 0 ? '最近关键活动能否证明这条事件线确实产生了阶段性进展？' : '',
  ]).slice(0, 4);
  while (reviewQuestions.length < 4) {
    reviewQuestions.push(
      [
        '这条事件线目前最需要被看清的阶段判断是什么？',
        '有哪些事实已经足够明确，哪些判断仍需要补材料验证？',
        '如果现在导出汇报，最容易被追问的缺口会是什么？',
        '下一步最应该推动的动作，是否已经写到可以执行的程度？',
      ][reviewQuestions.length],
    );
  }

  const deliverables = dedupeStrings([
    milestoneSource.length > 0 ? `${milestoneSource.length} 条关键活动摘要与时间线` : '',
    taskCount > 0 ? `${taskCount} 条关联任务推进状态` : '',
    attachmentCount > 0 ? `${attachmentCount} 份附件材料（${familySummary.shortText}）` : '',
    draft.participantNames.length > 0 || normalizeText(eventLine.ownerName) ? '参与人名单与责任分工说明' : '',
    blockerText || decisionText || nextStepText ? '当前阻点、近期决策与下一步建议' : '',
    '导出时间与快照范围说明',
  ]).slice(0, 6);

  return {
    hasRenderableContent,
    organizationName: normalizedOrganizationName,
    brandCaption: 'EVENT LINE REPORT',
    reportTitle,
    reportSubtitle,
    coverSummary,
    coreJudgment: buildCoreJudgmentText({
      blockerText,
      decisionText,
      nextStepText,
      latestSignals,
    }),
    coreJudgmentNote: dedupeStrings([
      decisionText ? `最近决策：${truncateText(decisionText, 28)}` : '',
      blockerText ? `当前阻点：${truncateText(blockerText, 28)}` : '',
      nextStepText ? `下一步：${truncateText(nextStepText, 28)}` : '',
      milestoneSource.length > 0 ? `最近关键活动 ${milestoneSource.length} 条` : '',
    ]).slice(0, 2).join(' · ') || '当前仅能基于已有快照生成基础判断，建议继续补充活动说明与附件。',
    reviewWindow,
    kindLabel,
    statusLabel,
    statusTone,
    clientName,
    audienceLabel: participantSummary || '待补充参与信息',
    departmentName,
    ownerName,
    snapshotAtLabel: formatDateLabel(snapshot.snapshotAt),
    participantNames: draft.participantNames,
    participantSummary,
    supportCards: [
      {
        label: '汇报类型',
        value: '事件线汇报',
        note: `${kindLabel} · ${statusLabel}`,
      },
      {
        label: '时间范围',
        value: reviewWindow,
        note: `快照日期 ${formatDateLabel(snapshot.snapshotAt)}`,
      },
      {
        label: '内容规模',
        value: contentScaleValue,
        note: contentScaleNote,
      },
    ],
    tocSections,
    reviewQuestions,
    deliverables,
    readingSteps: readingSteps.slice(0, 3),
    readingIntro: hasRenderableContent
      ? `先快速建立这条${kindLabel}的阶段判断，再回到里程碑、任务推进、材料证据与后续动作逐项核对。`
      : '当前资料还不足以组织完整模拟汇报，建议先切到素材清单补充活动说明、任务状态或附件材料。',
    pageOneNote: hasRenderableContent
      ? `${kindLabel} · ${statusLabel} · 快照 ${formatDateLabel(snapshot.snapshotAt)}`
      : '当前资料不足，建议先切换到素材清单补资料。',
    pageTwoNote: hasRenderableContent
      ? '目录依据当前事件线快照自动生成，已包含关键活动、任务、附件和下一步信息。'
      : '目录页仅在形成足够阶段信息后展示。',
    emptyStateTitle: '资料不足，暂无法生成模拟汇报',
    emptyStateDescription: '当前事件线缺少足够的活动、任务、附件或阶段判断。先到素材清单里补活动说明、任务状态或附件材料，再回来预览更合适。',
  };
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
  const downloadUrl = resolveAttachmentUrl(att, backendBaseUrl);
  const openUrl = resolveAttachmentOpenUrl(att, backendBaseUrl);
  const tags = attachmentDisplayTags(att);

  useEffect(() => {
    if (normalizeText(att.parsedPreview)) {
      setSummary(att.parsedPreview || null);
      setLoading(false);
      return;
    }
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
  }, [att.id, att.parsedPreview, backendBaseUrl]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* File header · 极简 */}
      <div className="flex items-center gap-3 px-3.5 py-2.5 border-b border-gray-100">
        <div
          className="flex-shrink-0 flex items-center justify-center rounded w-8 h-8 text-[9px] font-bold"
          style={{ backgroundColor: badge.bg, color: badge.color }}
        >
          {badge.label}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-medium text-gray-900 truncate">{att.title}</p>
          <div className="mt-0.5 flex items-baseline gap-2 text-[10px] text-gray-400">
            {tags.map((tag) => (
              <span
                key={tag}
                className={tag === '已解析' ? 'text-emerald-600' : tag === '待确认' ? 'text-amber-600' : 'text-gray-500'}
              >
                {tag}
              </span>
            ))}
            <span className="tabular-nums">{fileSizeLabel(att.sizeBytes)}</span>
          </div>
        </div>
        {openUrl && (
          <a
            href={openUrl}
            target="_blank"
            rel="noreferrer"
            title="在浏览器中打开"
            className="flex-shrink-0 inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-all hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50"
          >
            <ExternalLink size={11} strokeWidth={2} />
          </a>
        )}
        {downloadUrl && (
          <a
            href={downloadUrl}
            download={att.title}
            title="下载文件"
            className="flex-shrink-0 inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-all hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50"
          >
            <Download size={11} strokeWidth={2} />
          </a>
        )}
      </div>
      {/* AI summary */}
      <div className="px-3.5 py-3 bg-gray-50/40">
        {loading ? (
          <div className="flex items-center gap-2 text-[10.5px] text-gray-400">
            <RefreshCw size={10} strokeWidth={1.8} className="animate-spin" />
            <span>正在提取文档摘要…</span>
          </div>
        ) : summary ? (
          <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap text-[11.5px] leading-5 text-gray-600 font-sans">{summary}</pre>
        ) : (
          <p className="text-[10.5px] text-gray-300">暂无文档摘要</p>
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
  const imageUrl = resolveAttachmentUrl(att, backendBaseUrl);
  const openUrl = resolveAttachmentOpenUrl(att, backendBaseUrl);
  const tags = attachmentDisplayTags(att);

  useEffect(() => {
    if (normalizeText(att.parsedPreview)) {
      setOcrText(att.parsedPreview || null);
      setLoading(false);
      return;
    }
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
  }, [att.id, att.parsedPreview, backendBaseUrl]);

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-gray-50">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={att.title}
          className="w-full object-contain max-h-[300px]"
        />
      ) : (
        <div className="flex h-40 items-center justify-center bg-gray-100 text-[10px] text-gray-400">
          暂无图片预览地址
        </div>
      )}
      <div className="px-2 py-1.5">
        <p className="text-[10px] text-gray-500 truncate">{att.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {tags.map((tag) => (
            <span key={tag} className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${tag === '已解析' ? 'bg-emerald-50 text-emerald-700' : tag === '待确认' ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-[#4B66D8]'}`}>
              {tag}
            </span>
          ))}
          {openUrl ? (
            <a href={openUrl} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[9px] font-bold text-[#4B66D8]">
              <ExternalLink size={10} /> 打开原文
            </a>
          ) : null}
        </div>
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
  /** 切换到 R0~R3 "AI 主理人"完整报告流程（关本面板 → 开 AI 报告 Modal）。 */
  onOpenAIReport?: (target: { eventLineName: string; clientName: string }) => void;
};

export default function EventLineReportPanel({ eventLineId, backendBaseUrl, onClose, onExportWord, onOpenAIReport }: Props) {
  const [snapshot, setSnapshot] = useState<EventLineReportSnapshot | null>(null);
  const [organizationName, setOrganizationName] = useState('');
  const [exportProgress, setExportProgress] = useState<{ stage: string; detail: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Local editable draft — built from immutable cloud snapshot */
  const [draft, setDraft] = useState<ReportDraft | null>(null);

  /* Per-activity toggle: which activities have docs expanded / images expanded */
  const [docsExpandedActivities, setDocsExpandedActivities] = useState<Set<string>>(new Set());
  const [imagesExpandedActivities, setImagesExpandedActivities] = useState<Set<string>>(new Set());
  const [showSystemTraces, setShowSystemTraces] = useState(false);
  const [viewMode, setViewMode] = useState<'timeline' | 'tasks' | 'report'>('timeline');
  const [activeMaterialTab, setActiveMaterialTab] = useState<EventLineMaterialTabKey>('core');

  /* Track which attachments are expanded (legacy, kept for export) */
  const [expandedAttachments, setExpandedAttachments] = useState<Set<string>>(new Set());

  /* P1 主线还原 LLM 叙事 */
  const [timelineNarrative, setTimelineNarrative] = useState<EventLineTimelineNarrative | null>(null);
  const [narrativeRegenerating, setNarrativeRegenerating] = useState(false);
  const [narrativeError, setNarrativeError] = useState<string | null>(null);

  /* 加载已有叙事 */
  useEffect(() => {
    if (!eventLineId) {
      setTimelineNarrative(null);
      return;
    }
    let cancelled = false;
    void getEventLineTimelineNarrative(eventLineId)
      .then((data) => { if (!cancelled) setTimelineNarrative(data); })
      .catch(() => { if (!cancelled) setTimelineNarrative(null); });
    return () => { cancelled = true; };
  }, [eventLineId]);

  const handleRegenerateNarrative = async () => {
    if (!eventLineId || narrativeRegenerating) return;
    setNarrativeRegenerating(true);
    setNarrativeError(null);
    try {
      const next = await regenerateEventLineTimelineNarrative(eventLineId, 'manual');
      setTimelineNarrative(next);
    } catch (err) {
      setNarrativeError(err instanceof Error ? err.message : '生成失败');
    } finally {
      setNarrativeRegenerating(false);
    }
  };

  const renderNarrativeNode = (node: EventLineNarrativeNode, index: number) => {
    const rankText = String(index + 1).padStart(2, '0');
    const confColor =
      node.confidence === 'high'
        ? 'text-emerald-700 bg-emerald-50 ring-emerald-200'
        : node.confidence === 'low'
          ? 'text-rose-700 bg-rose-50 ring-rose-200'
          : 'text-amber-700 bg-amber-50 ring-amber-200';
    const timeLabel = node.time ? (node.time.slice(0, 10) || node.time) : '时间待补';
    return (
      <article key={node.id} className="group relative pl-8">
        <div className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full bg-gray-900" />
        <div className="flex items-baseline gap-4 mb-2">
          <span className="text-[28px] leading-none font-extralight tracking-tighter text-gray-200">
            {rankText}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h4 className="text-[16px] font-semibold leading-snug text-gray-900">{node.title}</h4>
              <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase ring-1 ${confColor}`}>
                <span className={`h-1 w-1 rounded-full ${node.confidence === 'high' ? 'bg-emerald-500' : node.confidence === 'low' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                {node.confidence}
              </span>
              <span className="text-[11px] text-gray-400 tabular-nums">{timeLabel}</span>
            </div>
            <p className="mt-2 text-[14px] leading-relaxed text-gray-700">{node.narrative}</p>
            {(node.linkedTaskIds.length > 0 || node.linkedAttachmentIds.length > 0) && (
              <p className="mt-2 text-[10px] tracking-wide uppercase text-gray-400">
                关联 ·
                {node.linkedTaskIds.length > 0 && ` ${node.linkedTaskIds.length} 任务`}
                {node.linkedAttachmentIds.length > 0 && ` ${node.linkedAttachmentIds.length} 附件`}
              </p>
            )}
          </div>
        </div>
      </article>
    );
  };

  /* Fetch immutable snapshot from cloud */
  useEffect(() => {
    setSnapshot(null);
    setOrganizationName('');
    setDraft(null);
    setError(null);
    setLoading(true);
    setExportProgress(null);
    setDocsExpandedActivities(new Set());
    setImagesExpandedActivities(new Set());
    setExpandedAttachments(new Set());
    setShowSystemTraces(false);
    setViewMode('timeline');
    setActiveMaterialTab('core');
  }, [eventLineId]);

  const loadSnapshot = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [data, orgProfile] = await Promise.all([
        getEventLineReportSnapshot(eventLineId),
        getOrgModelProfile().catch(() => null),
      ]);
      setSnapshot(data);
      const orgName = normalizeText(orgProfile?.organization?.name);
      setOrganizationName(orgName);
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
          eventLineName: options?.silent && prev ? prev.eventLineName : data.eventLine.name,
          summary: options?.silent && prev ? prev.summary : data.eventLine.summary ?? '',
          activities: data.activities.map((a: EventLineActivity) => ({
            ...a,
            ...(prevEditMap.get(a.id) || {}),
          })),
          attachments: [...data.attachments],
          tasks: [...(data.tasks || [])],
          participantNames: [...data.participantNames],
          snapshotAt: data.snapshotAt,
          timelineNodes: [...(data.timelineNodes || [])].map(normalizeBackendTimelineNode),
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

  const visibleActivities = useMemo(() => (draft?.activities ?? []).filter((a) => !a.hidden), [draft]);

  const reportPreview = useMemo(() => {
    if (!draft || !snapshot) return null;
    return deriveReportPreview(snapshot, draft, visibleActivities, organizationName);
  }, [draft, snapshot, visibleActivities, organizationName]);

  const materialModel = useMemo(() => {
    if (!draft || !snapshot) return null;
    return deriveEventLineMaterialModel(snapshot, draft);
  }, [draft, snapshot]);

  const timelineModel = useMemo(() => {
    if (!draft || !snapshot) return null;
    return buildEventLineTimelineModel(snapshot, draft);
  }, [draft, snapshot]);

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

  const renderTimelineAttachments = (attachments: EventLineReportAttachment[], nodeId: string) => {
    if (attachments.length === 0) return null;
    const imageAttachments = attachments.filter(isImageAttachment);
    const docAttachments = attachments.filter((att) => !isImageAttachment(att));
    const downloadableAtts = attachments.filter((att) => resolveAttachmentUrl(att, backendBaseUrl));
    const docKey = `timeline-docs:${nodeId}`;
    const imageKey = `timeline-images:${nodeId}`;
    const isDocsExpanded = docsExpandedActivities.has(docKey);
    const isImagesExpanded = imagesExpandedActivities.has(imageKey);
    const primaryOpenAtt = attachments.find((att) => resolveAttachmentOpenUrl(att, backendBaseUrl));
    const primaryOpenUrl = primaryOpenAtt ? resolveAttachmentOpenUrl(primaryOpenAtt, backendBaseUrl) : '';

    return (
      <div className="mt-3 rounded-2xl border border-gray-100 bg-[#FAFBFF] p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-gray-500 shadow-sm">
              附件 {attachments.length}
            </span>
            {imageAttachments.length > 0 && (
              <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[10px] font-bold text-violet-700">
                图片 {imageAttachments.length}
              </span>
            )}
            {docAttachments.length > 0 && (
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-700">
                文档 {docAttachments.length}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              title={isDocsExpanded ? '折叠文档' : '展开文档'}
              disabled={docAttachments.length === 0}
              className={`rounded p-1 transition ${docAttachments.length === 0 ? 'cursor-default text-gray-200' : isDocsExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
              onClick={() => {
                if (docAttachments.length === 0) return;
                setDocsExpandedActivities((prev) => {
                  const next = new Set(prev);
                  if (next.has(docKey)) next.delete(docKey);
                  else next.add(docKey);
                  return next;
                });
              }}
            >
              <FileText size={12} />
            </button>
            <button
              type="button"
              title={isImagesExpanded ? '折叠图片' : '展开图片'}
              disabled={imageAttachments.length === 0}
              className={`rounded p-1 transition ${imageAttachments.length === 0 ? 'cursor-default text-gray-200' : isImagesExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
              onClick={() => {
                if (imageAttachments.length === 0) return;
                setImagesExpandedActivities((prev) => {
                  const next = new Set(prev);
                  if (next.has(imageKey)) next.delete(imageKey);
                  else next.add(imageKey);
                  return next;
                });
              }}
            >
              <Image size={12} />
            </button>
            <div className="relative group/dl">
              <button
                type="button"
                title={downloadableAtts.length ? `下载节点附件（${downloadableAtts.length}个）` : '暂无可下载附件'}
                disabled={downloadableAtts.length === 0}
                className={`rounded p-1 transition ${downloadableAtts.length ? 'text-gray-400 hover:bg-gray-100 hover:text-[#5B7BFE]' : 'cursor-default text-gray-200'}`}
                onClick={() => {
                  for (const att of downloadableAtts) {
                    const link = document.createElement('a');
                    link.href = resolveAttachmentUrl(att, backendBaseUrl);
                    link.download = att.title;
                    link.click();
                  }
                }}
              >
                <Download size={12} />
              </button>
              {downloadableAtts.length > 0 && (
                <div className="invisible group-hover/dl:visible absolute right-0 top-full z-30 mt-1 w-72 max-h-80 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                  <div className="border-b border-gray-100 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">
                    附件列表 · {downloadableAtts.length} 个
                  </div>
                  {downloadableAtts.map((att) => {
                    const dlUrl = resolveAttachmentUrl(att, backendBaseUrl);
                    const openUrl = resolveAttachmentOpenUrl(att, backendBaseUrl);
                    return (
                      <div key={att.id} className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-gray-50">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[12px] font-medium text-gray-800" title={att.title}>{att.title}</p>
                          <p className="text-[10px] text-gray-400">{formatAttachmentBytes(att.sizeBytes)}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          {openUrl && (
                            <a
                              href={openUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="在浏览器中打开"
                              className="rounded p-1 text-gray-400 transition hover:bg-blue-50 hover:text-[#5B7BFE]"
                            >
                              <ExternalLink size={11} />
                            </a>
                          )}
                          <a
                            href={dlUrl}
                            download={att.title}
                            title="下载"
                            className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-[#5B7BFE]"
                          >
                            <Download size={11} />
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {!isDocsExpanded && !isImagesExpanded && (
          <div className="mt-3 space-y-2">
            {imageAttachments.length > 0 && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {imageAttachments.slice(0, 4).map((att) => {
                  const url = resolveAttachmentUrl(att, backendBaseUrl);
                  return url ? (
                    <a
                      key={att.id}
                      href={url}
                      download={att.title}
                      className="min-w-0 rounded-xl border border-gray-100 bg-white p-1.5 transition hover:border-[#C9D6FF]"
                      title={att.title}
                    >
                      <img src={url} alt={att.title} className="h-20 w-full rounded-lg object-cover" loading="lazy" />
                      <p className="mt-1 truncate text-[10px] text-gray-500">{att.title}</p>
                    </a>
                  ) : (
                    <div key={att.id} className="min-w-0 rounded-xl border border-gray-100 bg-white p-1.5" title={att.title}>
                      <div className="flex h-20 items-center justify-center rounded-lg bg-gray-100 text-[10px] text-gray-300">
                        无预览
                      </div>
                      <p className="mt-1 truncate text-[10px] text-gray-400">{att.title}</p>
                    </div>
                  );
                })}
                {imageAttachments.length > 4 && (
                  <div className="flex h-[104px] items-center justify-center rounded-xl border border-gray-100 bg-white text-[10px] text-gray-400">
                    另有 {imageAttachments.length - 4} 张图片
                  </div>
                )}
              </div>
            )}

            {docAttachments.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {docAttachments.slice(0, 8).map((att) => {
                  const badge = fileTypeBadge(att.title);
                  const url = resolveAttachmentUrl(att, backendBaseUrl);
                  const content = (
                    <>
                      <span className="rounded px-1 py-0.5 text-[8px] font-bold" style={{ backgroundColor: badge.bg, color: badge.color }}>
                        {badge.label}
                      </span>
                      <span className="truncate">{att.title}</span>
                      {att.parseStatus && (
                        <span className={`rounded px-1 text-[9px] font-bold ${att.parseStatus === 'ready' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                          {att.parseStatus === 'ready' ? '已解析' : '待解析'}
                        </span>
                      )}
                    </>
                  );
                  return url ? (
                    <a
                      key={att.id}
                      href={url}
                      download={att.title}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2 py-1 text-[10px] text-gray-600 transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
                      title={att.title}
                    >
                      {content}
                    </a>
                  ) : (
                    <span
                      key={att.id}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-gray-100 bg-white px-2 py-1 text-[10px] text-gray-300"
                      title={att.title}
                    >
                      {content}
                    </span>
                  );
                })}
                {docAttachments.length > 8 && (
                  <span className="rounded-lg bg-white px-2 py-1 text-[10px] text-gray-400">
                    另有 {docAttachments.length - 8} 份文档
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {isDocsExpanded && docAttachments.length > 0 && (
          <div className="mt-3 space-y-2">
            {docAttachments.map((att) => (
              <DocContentViewer key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
            ))}
          </div>
        )}

        {isImagesExpanded && imageAttachments.length > 0 && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            {imageAttachments.map((att) => (
              <ImageWithOcr key={att.id} att={att} backendBaseUrl={backendBaseUrl} />
            ))}
          </div>
        )}

        {primaryOpenUrl && (
          <div className="mt-3 flex justify-end">
            <a
              href={primaryOpenUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-50 px-3 py-2 text-[11px] font-bold text-[#4B66D8] transition hover:bg-blue-100"
            >
              <ExternalLink size={12} />
              打开原文
            </a>
          </div>
        )}
      </div>
    );
  };

  const renderTimelineNode = (node: EventLineTimelineNode, index: number, tone: 'main' | 'review' | 'system' = 'main') => {
    const timeLabel = node.time ? formatTs(node.time) : '时间待补';
    const accentLine =
      tone === 'review' ? 'bg-amber-500'
        : tone === 'system' ? 'bg-gray-300'
          : 'bg-gray-900';
    return (
      <article key={node.id} className="group relative pl-7 py-3">
        <div className={`absolute left-0 top-3 bottom-3 w-[2px] rounded-full ${accentLine}`} />
        <div className="flex items-baseline gap-4 mb-1.5">
          <span className="text-[24px] leading-none font-extralight tracking-tighter text-gray-200">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-3 flex-wrap mb-0.5">
              <h3 className="text-[14.5px] font-semibold leading-snug text-gray-900">{node.title}</h3>
              <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-gray-400">
                {TIMELINE_KIND_LABELS[node.kind]}
              </span>
              <span className="text-[10px] text-gray-400 tabular-nums">{timeLabel}</span>
              {node.ownerName && <span className="text-[10px] text-gray-400">{node.ownerName}</span>}
              {!node.ownerName && node.actorName && <span className="text-[10px] text-gray-400">{node.actorName}</span>}
            </div>
            <p className="whitespace-pre-wrap text-[12.5px] leading-6 text-gray-600">{node.summary}</p>
            {node.evidenceSummary && (
              <div className="mt-2 border-l-[2px] border-gray-200 pl-3 py-1">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400 mb-0.5">解析依据</p>
                <p className="text-[11.5px] leading-5 text-gray-600">{node.evidenceSummary}</p>
              </div>
            )}
            {node.tags.length > 0 && (
              <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[10.5px] text-gray-500">
                {node.tags.map((tag, i) => (
                  <span key={tag}>{i > 0 && <span className="text-gray-300 mr-2">·</span>}{tag}</span>
                ))}
              </div>
            )}
            {node.warnings.length > 0 && (
              <p className="mt-1.5 text-[11px] leading-5 text-amber-700">⚠ {node.warnings.join(' · ')}</p>
            )}
            {renderTimelineAttachments(node.attachments, node.id)}
          </div>
        </div>
      </article>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm animate-in fade-in">
      <div
        className="relative flex h-[88vh] w-full max-w-[920px] flex-col rounded-xl border border-gray-200 bg-white shadow-[0_8px_32px_rgba(0,0,0,0.08)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header · 极简 typography ── */}
        <div className="flex items-start gap-4 border-b border-gray-100 px-7 pt-6 pb-5">
          <button
            type="button"
            className="mt-1 inline-flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-400 transition-all hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50"
            onClick={onClose}
            aria-label="关闭"
          >
            <X size={14} strokeWidth={2} />
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">事件线汇报</p>
            <h2 className="mt-1.5 text-[24px] font-light tracking-tight text-gray-900 leading-tight">{draft.eventLineName}</h2>
            <textarea
              className="mt-3 w-full resize-none border-0 border-b border-transparent bg-transparent px-0 py-1 text-[13px] leading-6 text-gray-500 transition-colors placeholder:text-gray-300 placeholder:font-light hover:border-gray-200 focus:border-gray-400 focus:outline-none"
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
            className={`shrink-0 inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-[12px] font-medium transition-all ${
              exportProgress
                ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                : 'bg-gray-900 text-white shadow-sm hover:bg-gray-700'
            }`}
            onClick={() => {
              const exportDraft = {
                ...draft,
                timelineNodes: timelineModel
                  ? [
                    ...timelineModel.mainNodes,
                    ...timelineModel.reviewNodes,
                    ...(showSystemTraces ? timelineModel.systemNodes : []),
                  ]
                  : [],
                expandedAttachmentIds: Array.from(expandedAttachments),
                docsExpandedActivityIds: Array.from(docsExpandedActivities),
                imagesExpandedActivityIds: Array.from(imagesExpandedActivities),
                showSystemTraces,
              };
              setExportProgress({ stage: '准备导出...', detail: '正在整理事件线数据' });
              void (async () => {
                try {
                  setExportProgress({ stage: '生成文档...', detail: `正在处理 ${timelineModel?.mainNodes.length ?? 0} 个里程碑节点和 ${draft.attachments.length} 个附件` });
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
            {exportProgress ? (
              <>
                <RefreshCw size={12} strokeWidth={2.2} className="animate-spin" />
                <span>导出中</span>
              </>
            ) : (
              <>
                <Download size={12} strokeWidth={2.2} />
                <span>导出 Word</span>
              </>
            )}
          </button>
        </div>

        {/* ── Meta · 极简 inline (status dot + 客户 + 阶段 + 参与) ── */}
        <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 border-b border-gray-100 px-7 py-3 text-[11px]">
          {(() => {
            const statusMeta: Record<string, { dot: string; label: string; text: string }> = {
              active: { dot: 'bg-emerald-500', label: '进行中', text: 'text-emerald-700' },
              blocked: { dot: 'bg-rose-500', label: '受阻', text: 'text-rose-700' },
              paused: { dot: 'bg-amber-500', label: '暂停', text: 'text-amber-700' },
              done: { dot: 'bg-gray-400', label: '已完成', text: 'text-gray-600' },
              archived: { dot: 'bg-gray-300', label: '已归档', text: 'text-gray-500' },
            };
            const s = statusMeta[snapshot.eventLine.status] || statusMeta.active;
            return (
              <span className={`inline-flex items-center gap-1.5 font-medium ${s.text}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
                {s.label}
              </span>
            );
          })()}
          {snapshot.eventLine.stage && (
            <span className="text-gray-400">
              <span className="text-[10px] uppercase tracking-[0.14em] mr-1">阶段</span>
              <span className="text-gray-700 font-medium">{snapshot.eventLine.stage}</span>
            </span>
          )}
          {snapshot.eventLine.primaryClientName && (
            <span className="text-gray-400">
              <span className="text-[10px] uppercase tracking-[0.14em] mr-1">客户</span>
              <span className="text-gray-700 font-medium">{snapshot.eventLine.primaryClientName}</span>
            </span>
          )}
          {draft.participantNames.length > 0 && (
            <span className="text-gray-400 inline-flex items-baseline gap-1">
              <span className="text-[10px] uppercase tracking-[0.14em]">参与</span>
              <span className="text-gray-700 font-medium">{draft.participantNames.join(' · ')}</span>
            </span>
          )}
          {(() => {
            const status = snapshot.eventLine.syncStatus;
            if (!status || status === 'synced') return null;
            const cfg: Record<string, { label: string; dot: string; text: string; bg: string; ring: string }> = {
              local: { label: '仅本地', dot: 'bg-gray-400', text: 'text-gray-600', bg: 'bg-gray-50', ring: 'ring-gray-200' },
              syncing: { label: '同步中', dot: 'bg-sky-500', text: 'text-sky-700', bg: 'bg-sky-50', ring: 'ring-sky-200' },
              pending: { label: '待同步', dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50', ring: 'ring-amber-200' },
              error: { label: '同步失败', dot: 'bg-rose-500', text: 'text-rose-700', bg: 'bg-rose-50', ring: 'ring-rose-200' },
            };
            const item = cfg[status];
            if (!item) return null;
            return (
              <span
                className={`inline-flex items-center gap-1 rounded-md ${item.bg} px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase ${item.text} ring-1 ${item.ring}/60`}
                title={snapshot.eventLine.lastSyncError || undefined}
              >
                <span className={`h-1 w-1 rounded-full ${item.dot}`} />
                {item.label}
              </span>
            );
          })()}
        </div>
        {/* ── Completeness · 极简一行 + 细 bar ── */}
        {typeof snapshot.eventLine.completenessScore === 'number' && (() => {
          const score = snapshot.eventLine.completenessScore;
          const status = snapshot.eventLine.completenessStatus || 'insufficient';
          const missing = snapshot.eventLine.completenessMissingSlots || [];
          const palette: Record<string, { bar: string; text: string; label: string }> = {
            high_confidence: { bar: 'bg-emerald-500', text: 'text-emerald-700', label: '可对外汇报' },
            forecast_ready: { bar: 'bg-sky-500', text: 'text-sky-700', label: '可形成预测' },
            summary_ready: { bar: 'bg-amber-500', text: 'text-amber-700', label: '可初步总结' },
            insufficient: { bar: 'bg-rose-500', text: 'text-rose-700', label: '证据不足' },
          };
          const p = palette[status] || palette.insufficient;
          return (
            <div className="border-b border-gray-100 px-7 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-baseline gap-3 text-[11px]">
                  <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">证据完整度</span>
                  <span className="text-[15px] font-light tabular-nums text-gray-900">{score}</span>
                  <span className="text-gray-300 text-[10px]">/ 100</span>
                  <span className={`font-medium ${p.text}`}>{p.label}</span>
                </div>
                {missing.length > 0 && (
                  <span className="text-[11px] text-gray-400">
                    缺：<span className="text-gray-600">{missing.slice(0, 4).join('、')}{missing.length > 4 ? '…' : ''}</span>
                  </span>
                )}
              </div>
              <div className="mt-2 h-[2px] w-full rounded-full bg-gray-100">
                <div className={`h-[2px] rounded-full transition-all ${p.bar}`} style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
              </div>
            </div>
          );
        })()}

        {/* ── Export progress overlay ── */}
        {exportProgress && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-xl">
            <div className="text-center px-8 py-6">
              <RefreshCw size={20} strokeWidth={1.5} className="mx-auto mb-3 animate-spin text-gray-700" />
              <p className="text-[13px] font-semibold text-gray-900">{exportProgress.stage}</p>
              <p className="mt-1 text-[11px] text-gray-500">{exportProgress.detail}</p>
            </div>
          </div>
        )}

        {/* ── Scrollable body · overflow-y-scroll 让 scrollbar 始终占位, 切 tab 时宽度不跳 ── */}
        <div className="flex-1 overflow-y-scroll px-7 py-5" style={{ scrollbarGutter: 'stable' }}>
          {/* Tab 切换 · 周复盘同款极简下划线 */}
          <div className="mb-6 flex items-center justify-between gap-3 border-b border-gray-100">
            <div className="flex items-center gap-8">
              {([
                { id: 'timeline' as const, label: '主线还原' },
                { id: 'tasks' as const, label: '按任务查看' },
                { id: 'report' as const, label: '报告导出' },
              ]).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setViewMode(tab.id)}
                  className={`relative pb-3 text-[13px] tracking-wide transition-colors whitespace-nowrap ${
                    viewMode === tab.id
                      ? 'text-gray-900 font-semibold'
                      : 'text-gray-400 font-medium hover:text-gray-700'
                  }`}
                >
                  {tab.label}
                  {viewMode === tab.id && (
                    <span className="absolute bottom-[-1px] left-0 w-full h-[1.5px] bg-gray-900" />
                  )}
                </button>
              ))}
            </div>
            <p className="pb-3 text-[10px] uppercase tracking-[0.14em] text-gray-400">
              {viewMode === 'timeline'
                ? `${timelineModel?.mainNodes.length ?? 0} 节点 · ${timelineModel?.reviewNodes.length ?? 0} 待确认`
                : viewMode === 'tasks'
                  ? '按任务聚合附件 · 会议 · 补充材料'
                  : (reportPreview?.hasRenderableContent ? '封面 + 目录 模拟汇报' : '资料不足 · 建议补素材')}
            </p>
          </div>

          {viewMode === 'timeline' && timelineModel ? (
            <div className="space-y-5 pb-6">
              {/* P1 · AI 主线还原 banner */}
              {timelineNarrative && timelineNarrative.nodes.length > 0 ? (
                <section className="rounded-2xl border border-gray-900 bg-gray-900 px-5 py-5 text-white">
                  <div className="flex items-baseline justify-between gap-4 mb-3">
                    <div className="flex items-center gap-2">
                      <Sparkles size={14} className="text-amber-300" />
                      <h3 className="text-[15px] font-semibold tracking-tight">{timelineNarrative.headline || 'AI 主线还原'}</h3>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-gray-400">
                      <span>rev {timelineNarrative.rev}</span>
                      <span>·</span>
                      <span>{timelineNarrative.updatedAt.slice(0, 16).replace('T', ' ')}</span>
                      <button
                        type="button"
                        onClick={handleRegenerateNarrative}
                        disabled={narrativeRegenerating}
                        className="ml-2 inline-flex items-center gap-1 rounded-md border border-gray-700 bg-gray-800 px-2.5 py-1 text-[10px] font-medium text-gray-200 transition hover:bg-gray-700 disabled:opacity-60"
                      >
                        {narrativeRegenerating ? (
                          <>
                            <RefreshCw size={10} className="animate-spin" />
                            重新生成中
                          </>
                        ) : (
                          <>
                            <RefreshCw size={10} />
                            重新生成
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  {timelineNarrative.opening && (
                    <p className="text-[13px] leading-relaxed text-gray-200">{timelineNarrative.opening}</p>
                  )}
                  {narrativeError && (
                    <p className="mt-2 text-[11px] text-rose-300">{narrativeError}</p>
                  )}
                </section>
              ) : (
                <section className="rounded-2xl border border-dashed border-gray-300 bg-gray-50/60 px-5 py-6 text-center">
                  <Sparkles size={16} className="mx-auto mb-2 text-gray-400" />
                  <p className="text-[13px] font-semibold text-gray-700">主线还原尚未生成</p>
                  <p className="mt-1 text-[11.5px] text-gray-500">
                    AI 会读完所有任务/活动/附件，写一篇 3-5 个关键转折的"传记"
                  </p>
                  <button
                    type="button"
                    onClick={handleRegenerateNarrative}
                    disabled={narrativeRegenerating}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-gray-900 px-4 py-2 text-[12px] font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
                  >
                    {narrativeRegenerating ? (
                      <>
                        <RefreshCw size={12} className="animate-spin" />
                        AI 生成中 · 约 1-2 分钟
                      </>
                    ) : (
                      <>
                        <Sparkles size={12} />
                        生成主线还原
                      </>
                    )}
                  </button>
                  {narrativeError && (
                    <p className="mt-3 text-[11px] text-rose-600">{narrativeError}</p>
                  )}
                </section>
              )}

              {timelineNarrative && timelineNarrative.nodes.length > 0 ? (
                <div className="space-y-5">
                  {timelineNarrative.nodes.map((node, index) => renderNarrativeNode(node, index))}
                  {timelineNarrative.closing && (
                    <section className="rounded-2xl border-l-[2px] border-gray-900 bg-gray-50 pl-4 py-3">
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">今天在哪里</p>
                      <p className="text-[13px] leading-relaxed text-gray-700">{timelineNarrative.closing}</p>
                    </section>
                  )}
                  {timelineModel.mainNodes.length > 0 && (
                    <details className="mt-6 rounded-xl border border-gray-100 bg-gray-50/40 px-4 py-3">
                      <summary className="cursor-pointer text-[11px] font-medium text-gray-500 hover:text-gray-700">
                        查看原始时间线节点 ({timelineModel.mainNodes.length} 个) — 由规则切分, 仅供参考
                      </summary>
                      <div className="mt-3 space-y-3">
                        {timelineModel.mainNodes.map((node, index) => renderTimelineNode(node, index))}
                      </div>
                    </details>
                  )}
                </div>
              ) : timelineModel.mainNodes.length > 0 ? (
                <div className="space-y-3">
                  {timelineModel.mainNodes.map((node, index) => renderTimelineNode(node, index))}
                </div>
              ) : (
                <div className="rounded-2xl border border-gray-100 bg-white px-4 py-8 text-center text-[12px] text-gray-400">
                  当前还没有足够信息形成主线节点。
                </div>
              )}

              {timelineModel.reviewNodes.length > 0 && (
                <section className="pt-5 border-t border-gray-100">
                  <div className="mb-3 flex items-baseline gap-3">
                    <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-600">待确认节点</h3>
                    <span className="text-[11px] text-gray-400 tabular-nums">{timelineModel.reviewNodes.length} 项</span>
                  </div>
                  <p className="mb-4 text-[11.5px] leading-relaxed text-gray-500">
                    缺少归属、含测试文件或解析状态不完整 · 暂不进入主线叙事
                  </p>
                  <div className="space-y-2">
                    {timelineModel.reviewNodes.map((node, index) => renderTimelineNode(node, index, 'review'))}
                  </div>
                </section>
              )}

              {timelineModel.systemNodes.length > 0 && (
                <section className="pt-5 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => setShowSystemTraces((prev) => !prev)}
                    className="flex w-full items-baseline justify-between gap-3 text-left group/sys"
                  >
                    <div className="flex items-baseline gap-3">
                      <h3 className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 group-hover/sys:text-gray-700">系统痕迹</h3>
                      <span className="text-[11px] text-gray-400 tabular-nums">{timelineModel.systemNodes.length} 项</span>
                    </div>
                    <span className="text-[11px] font-medium text-gray-400 group-hover/sys:text-gray-900 transition-colors">
                      {showSystemTraces ? '收起 ↑' : '展开 ↓'}
                    </span>
                  </button>
                  <p className="mt-1 text-[11.5px] leading-relaxed text-gray-400">
                    创建 · 上传 · 更新等审计流水
                  </p>
                  {showSystemTraces && (
                    <div className="mt-4 space-y-2">
                      {timelineModel.systemNodes.map((node, index) => renderTimelineNode(node, index, 'system'))}
                    </div>
                  )}
                </section>
              )}
            </div>
          ) : viewMode === 'report' && reportPreview ? (
            reportPreview.hasRenderableContent ? (
            <div className="space-y-10 pb-6">
              {/* AI 主理人入口 · 改极简深色 CTA */}
              {onOpenAIReport && (
                <section className="rounded-xl border border-gray-900 bg-gray-900 px-5 py-4 text-white">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <Sparkles size={16} className="mt-0.5 text-amber-300 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[13.5px] font-semibold tracking-tight">用 AI 主理人生成完整报告</p>
                        <p className="mt-0.5 text-[11.5px] leading-relaxed text-gray-300">
                          豆包推骨架 → 章节并行起草 + 信息图 → 一键导出 docx / Markdown · 约 2-4 分钟
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        onOpenAIReport({
                          eventLineName: draft.eventLineName || '',
                          clientName: organizationName || '',
                        })
                      }
                      className="shrink-0 inline-flex items-center gap-1.5 rounded-md bg-white px-3.5 py-1.5 text-[12px] font-medium text-gray-900 transition hover:bg-gray-100"
                    >
                      开始
                      <ArrowRight size={11} strokeWidth={2.2} />
                    </button>
                  </div>
                </section>
              )}

              {/* 真报告预览 · 用 narrative + tasks + attachments 实数据 */}
              <ReportPreviewBody
                narrative={timelineNarrative}
                draft={draft}
                organizationName={organizationName}
                snapshot={snapshot}
              />
            </div>
            ) : (
              <div className="py-16 text-center">
                <p className="text-[14px] font-semibold text-gray-700">报告尚不可用</p>
                <p className="mt-3 max-w-md mx-auto text-[12px] leading-relaxed text-gray-400">
                  当前事件线的素材不足以形成报告。建议先在「按任务查看」补充关键附件，
                  在「主线还原」点击 AI 生成关键转折点，再回来导出。
                </p>
                <div className="mt-6 flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setViewMode('tasks')}
                    className="inline-flex items-center rounded-md border border-gray-200 bg-white px-3.5 py-1.5 text-[12px] font-medium text-gray-700 transition hover:border-gray-300 hover:bg-gray-50"
                  >
                    去补充素材
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('timeline')}
                    className="inline-flex items-center rounded-md bg-gray-900 px-3.5 py-1.5 text-[12px] font-medium text-white transition hover:bg-gray-700"
                  >
                    去生成主线还原
                  </button>
                </div>
              </div>
            )
          ) : viewMode === 'report' ? (
            <div className="py-16 text-center text-[13px] text-gray-400">报告预览加载中…</div>
          ) : null}

          {viewMode === 'tasks' && materialModel ? (
            <div className="space-y-6">
              {/* 5 个分类 · 极简下划线 tab + 旁边显示当前数 */}
              <div className="flex items-center gap-7 border-b border-gray-100">
                {(['core', 'review', 'supplement', 'system', 'gaps'] as EventLineMaterialTabKey[]).map((tab) => {
                  const count = tab === 'gaps' ? materialModel.gaps.length : materialModel.groups[tab].length;
                  const active = activeMaterialTab === tab;
                  return (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => {
                        setActiveMaterialTab(tab);
                        setShowSystemTraces(tab === 'system');
                      }}
                      className={`relative inline-flex items-baseline gap-2 pb-3 text-[13px] tracking-wide transition-colors whitespace-nowrap ${
                        active
                          ? 'text-gray-900 font-semibold'
                          : 'text-gray-400 font-medium hover:text-gray-700'
                      }`}
                    >
                      <span>{MATERIAL_GROUP_META[tab].label}</span>
                      <span className={`text-[11px] tabular-nums ${active ? 'text-gray-700' : 'text-gray-300'}`}>{count}</span>
                      {active && (
                        <span className="absolute bottom-[-1px] left-0 w-full h-[1.5px] bg-gray-900" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* 当前分类描述行 · 极简 */}
              <div className="flex items-baseline justify-between gap-4">
                <p className="text-[12px] leading-relaxed text-gray-500 max-w-2xl">
                  {MATERIAL_GROUP_META[activeMaterialTab].description}
                </p>
                <p className="shrink-0 text-[10px] uppercase tracking-[0.14em] text-gray-400 tabular-nums">
                  共 <span className="text-gray-900 font-medium">{draft.attachments.length}</span> 附件 · <span className="text-gray-900 font-medium">{draft.tasks.length}</span> 任务
                </p>
              </div>

              {activeMaterialTab !== 'gaps' && materialModel.gaps.length > 0 && (
                <div className="flex items-start gap-2.5 rounded-md bg-amber-50/60 border-l-[2px] border-amber-400 px-3.5 py-2.5">
                  <AlertTriangle size={13} strokeWidth={2} className="text-amber-600 mt-0.5 shrink-0" />
                  <p className="text-[12px] leading-relaxed text-amber-700">
                    {materialModel.gaps.slice(0, 2).join(' ')}
                    {materialModel.gaps.length > 2 ? ` 另有 ${materialModel.gaps.length - 2} 项。` : ''}
                  </p>
                </div>
              )}

              {activeMaterialTab === 'gaps' ? (
                <div className="space-y-2">
                  {materialModel.gaps.length > 0 ? materialModel.gaps.map((gap, index) => (
                    <div key={`${gap}-${index}`} className="flex items-start gap-3 py-3 border-b border-gray-100 last:border-0">
                      <span className="text-[24px] leading-none font-extralight tracking-tighter text-gray-200 pt-0.5">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <p className="flex-1 text-[13px] leading-relaxed text-gray-700">{gap}</p>
                    </div>
                  )) : (
                    <div className="py-16 text-center">
                      <p className="text-[13px] text-gray-400">{MATERIAL_GROUP_META.gaps.emptyText}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {materialModel.groups[activeMaterialTab].length > 0 ? materialModel.groups[activeMaterialTab].map((material) => {
                    const imageGroups = material.attachmentGroups.filter((group) => group.isImage);
                    const docGroups = material.attachmentGroups.filter((group) => !group.isImage);
                    const downloadableAtts = material.attachments.filter((att) => resolveAttachmentUrl(att, backendBaseUrl));
                    const isDocsExpanded = docsExpandedActivities.has(material.id);
                    const isImagesExpanded = imagesExpandedActivities.has(material.id);
                    const hasAtts = material.attachments.length > 0;
                    const totalGroupCount = material.attachmentGroups.length;

                    return (
                      <article
                        key={material.id}
                        className="group relative py-4 border-b border-gray-100 last:border-0"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[10px]">
                              <span className="font-bold uppercase tracking-[0.16em] text-gray-400">
                                {material.sourceLabel}
                              </span>
                              {material.statusLabel && (
                                <span className="text-gray-500 font-medium">{material.statusLabel}</span>
                              )}
                              {material.happenedAt && <span className="text-gray-400 tabular-nums">{formatTs(material.happenedAt)}</span>}
                              {material.actorName && <span className="text-gray-400">{material.actorName}</span>}
                            </div>
                            <h4 className="mt-1.5 text-[14.5px] font-semibold leading-snug text-gray-900">{material.title}</h4>
                            {material.summary && (
                              <p className="mt-1 text-[12.5px] leading-6 text-gray-500 whitespace-pre-wrap">{material.summary}</p>
                            )}
                            <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[10.5px]">
                              {material.tags.map((tag) => (
                                <span key={tag} className="text-gray-500">
                                  {tag}
                                </span>
                              ))}
                              {material.duplicateCount && (
                                <span className="text-amber-700 font-medium">
                                  · 重复 {material.duplicateCount}
                                </span>
                              )}
                              {material.versionCount && (
                                <span className="text-rose-700 font-medium">
                                  · {material.versionCount} 版本
                                </span>
                              )}
                              {material.testAttachmentCount && (
                                <span className="text-orange-700 font-medium">
                                  · 测试 {material.testAttachmentCount}
                                </span>
                              )}
                            </div>
                            {material.warnings.length > 0 && (
                              <p className="mt-2 text-[11px] leading-5 text-amber-700">
                                ⚠ {material.warnings.join(' · ')}
                              </p>
                            )}
                          </div>

                          <div className="flex shrink-0 items-center gap-1.5">
                            <button
                              type="button"
                              title={isDocsExpanded ? '折叠文档' : '展开文档'}
                              disabled={docGroups.length === 0}
                              className={`inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-all ${docGroups.length === 0 ? 'cursor-not-allowed opacity-40' : isDocsExpanded ? 'bg-gray-100 text-gray-900 border-gray-300' : 'hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50'}`}
                              onClick={() => {
                                if (docGroups.length === 0) return;
                                setDocsExpandedActivities((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(material.id)) next.delete(material.id);
                                  else next.add(material.id);
                                  return next;
                                });
                              }}
                            >
                              <FileText size={12} />
                            </button>
                            <button
                              type="button"
                              title={isImagesExpanded ? '折叠图片' : '展开图片'}
                              disabled={imageGroups.length === 0}
                              className={`inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-all ${imageGroups.length === 0 ? 'cursor-not-allowed opacity-40' : isImagesExpanded ? 'bg-gray-100 text-gray-900 border-gray-300' : 'hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50'}`}
                              onClick={() => {
                                if (imageGroups.length === 0) return;
                                setImagesExpandedActivities((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(material.id)) next.delete(material.id);
                                  else next.add(material.id);
                                  return next;
                                });
                              }}
                            >
                              <Image size={12} />
                            </button>
                            <div className="relative group/dl">
                              <button
                                type="button"
                                title={downloadableAtts.length ? `下载素材附件（${downloadableAtts.length}个）` : '暂无可下载附件'}
                                disabled={downloadableAtts.length === 0}
                                className={`inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-all ${downloadableAtts.length === 0 ? 'cursor-not-allowed opacity-40' : 'hover:border-gray-300 hover:text-gray-900 hover:bg-gray-50'}`}
                                onClick={() => {
                                  for (const att of downloadableAtts) {
                                    const link = document.createElement('a');
                                    link.href = resolveAttachmentUrl(att, backendBaseUrl);
                                    link.download = att.title;
                                    link.click();
                                  }
                                }}
                              >
                                <Download size={12} />
                              </button>
                              {downloadableAtts.length > 0 && (
                                <div className="invisible group-hover/dl:visible absolute right-0 top-full z-30 mt-1 w-72 max-h-80 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                                  <div className="border-b border-gray-100 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">
                                    附件列表 · {downloadableAtts.length} 个
                                  </div>
                                  {downloadableAtts.map((att) => {
                                    const dlUrl = resolveAttachmentUrl(att, backendBaseUrl);
                                    const openUrl = resolveAttachmentOpenUrl(att, backendBaseUrl);
                                    return (
                                      <div key={att.id} className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-gray-50">
                                        <div className="min-w-0 flex-1">
                                          <p className="truncate text-[12px] font-medium text-gray-800" title={att.title}>{att.title}</p>
                                          <p className="text-[10px] text-gray-400">{formatAttachmentBytes(att.sizeBytes)}</p>
                                        </div>
                                        <div className="flex shrink-0 items-center gap-1">
                                          {openUrl && (
                                            <a
                                              href={openUrl}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              title="在浏览器中打开"
                                              className="rounded p-1 text-gray-400 transition hover:bg-blue-50 hover:text-[#5B7BFE]"
                                            >
                                              <ExternalLink size={11} />
                                            </a>
                                          )}
                                          <a
                                            href={dlUrl}
                                            download={att.title}
                                            title="下载"
                                            className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-[#5B7BFE]"
                                          >
                                            <Download size={11} />
                                          </a>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        {hasAtts && !isDocsExpanded && !isImagesExpanded && (
                          <div className="mt-3 space-y-2">
                            {imageGroups.length > 0 && (
                              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                                {imageGroups.slice(0, 6).map((group) => {
                                  const url = resolveAttachmentUrl(group.primary, backendBaseUrl);
                                  const title = `${group.title} · ${fileSizeLabel(group.primary.sizeBytes)}`;
                                  const inner = (
                                    <>
                                      {url ? (
                                        <img
                                          src={url}
                                          alt={group.title}
                                          className="h-20 w-full rounded-lg object-cover"
                                          loading="lazy"
                                        />
                                      ) : (
                                        <div className="flex h-20 items-center justify-center rounded-lg bg-gray-100 text-[10px] text-gray-300">
                                          无预览
                                        </div>
                                      )}
                                      <div className="mt-1 flex items-center gap-1">
                                        <span className="truncate text-[10px] text-gray-500">{group.title}</span>
                                        {group.attachments.length > 1 && (
                                          <span className="shrink-0 rounded bg-amber-50 px-1 text-[9px] font-bold text-amber-700">
                                            x{group.attachments.length}
                                          </span>
                                        )}
                                      </div>
                                    </>
                                  );
                                  return url ? (
                                    <a
                                      key={group.id}
                                      href={url}
                                      download={group.primary.title}
                                      title={title}
                                      className="min-w-0 rounded-xl border border-gray-100 bg-gray-50 p-1.5 transition hover:border-[#C9D6FF]"
                                    >
                                      {inner}
                                    </a>
                                  ) : (
                                    <div key={group.id} title={title} className="min-w-0 rounded-xl border border-gray-100 bg-gray-50 p-1.5">
                                      {inner}
                                    </div>
                                  );
                                })}
                                {imageGroups.length > 6 && (
                                  <div className="flex h-[104px] items-center justify-center rounded-xl border border-gray-100 bg-gray-50 text-[10px] text-gray-400">
                                    另有 {imageGroups.length - 6} 组图片
                                  </div>
                                )}
                              </div>
                            )}

                            {docGroups.length > 0 && (
                              <div className="flex flex-wrap gap-1.5">
                                {docGroups.slice(0, 8).map((group) => {
                                  const att = group.primary;
                                  const badge = fileTypeBadge(att.title);
                                  const url = resolveAttachmentUrl(att, backendBaseUrl);
                                  const title = `${att.title} · ${fileSizeLabel(att.sizeBytes)}`;
                                  const content = (
                                    <>
                                      <span className="rounded px-1 py-0.5 text-[8px] font-bold" style={{ backgroundColor: badge.bg, color: badge.color }}>{badge.label}</span>
                                      <span className="truncate">{att.title}</span>
                                      {group.attachments.length > 1 && (
                                        <span className="rounded bg-amber-50 px-1 text-[9px] font-bold text-amber-700">
                                          x{group.attachments.length}
                                        </span>
                                      )}
                                      {group.versionCount && (
                                        <span className="rounded bg-rose-50 px-1 text-[9px] font-bold text-rose-700">
                                          {group.versionCount}版
                                        </span>
                                      )}
                                    </>
                                  );
                                  return url ? (
                                    <a
                                      key={group.id}
                                      href={url}
                                      download={att.title}
                                      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] text-gray-600 transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
                                      title={title}
                                    >
                                      {content}
                                    </a>
                                  ) : (
                                    <span
                                      key={group.id}
                                      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-gray-100 bg-gray-50 px-2 py-1 text-[10px] text-gray-300"
                                      title={title}
                                    >
                                      {content}
                                    </span>
                                  );
                                })}
                                {totalGroupCount > imageGroups.length + Math.min(docGroups.length, 8) && (
                                  <span className="rounded-lg bg-gray-50 px-2 py-1 text-[10px] text-gray-400">
                                    另有 {totalGroupCount - imageGroups.length - Math.min(docGroups.length, 8)} 组素材
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {isDocsExpanded && docGroups.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {docGroups.map((group) => (
                              <div key={group.id} className="space-y-1">
                                {(group.duplicateCount || group.versionCount) && (
                                  <p className="text-[10px] text-amber-700">
                                    {[
                                      group.duplicateCount ? `同名素材出现 ${group.duplicateCount} 次` : '',
                                      group.versionCount ? `${group.versionCount} 个版本，默认展示最新版本` : '',
                                    ].filter(Boolean).join(' · ')}
                                  </p>
                                )}
                                <DocContentViewer att={group.primary} backendBaseUrl={backendBaseUrl} />
                              </div>
                            ))}
                          </div>
                        )}

                        {isImagesExpanded && imageGroups.length > 0 && (
                          <div className="mt-3 grid grid-cols-2 gap-2">
                            {imageGroups.map((group) => (
                              <div key={group.id} className="space-y-1">
                                {(group.duplicateCount || group.versionCount) && (
                                  <p className="text-[10px] text-amber-700">
                                    {[
                                      group.duplicateCount ? `同名素材出现 ${group.duplicateCount} 次` : '',
                                      group.versionCount ? `${group.versionCount} 个版本，默认展示最新版本` : '',
                                    ].filter(Boolean).join(' · ')}
                                  </p>
                                )}
                                <ImageWithOcr att={group.primary} backendBaseUrl={backendBaseUrl} />
                              </div>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  }) : (
                    <div className="py-16 text-center text-[12px] text-gray-400">
                      {MATERIAL_GROUP_META[activeMaterialTab].emptyText}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export type { ReportDraft };

/* ══════════════════════════════════════════════════════════════════════
   ReportPreviewBody — 真报告预览
   用 timelineNarrative + draft tasks/attachments + snapshot 实数据渲染,
   跟 Word 导出的内容保持一致, 替代之前的封面/目录 mock。
   ══════════════════════════════════════════════════════════════════ */
function ReportPreviewBody({
  narrative,
  draft,
  organizationName,
  snapshot,
}: {
  narrative: EventLineTimelineNarrative | null;
  draft: ReportDraft;
  organizationName: string;
  snapshot: EventLineReportSnapshot;
}) {
  const el = snapshot.eventLine;
  const taskCount = draft.tasks.length;
  const doneTasks = draft.tasks.filter((t) => t.status === 'done').length;
  const attachmentCount = draft.attachments.length;

  return (
    <section className="border border-gray-200 rounded-xl bg-white">
      {/* 报告头 · 像真报告封面但极简 */}
      <header className="px-8 pt-8 pb-6 border-b border-gray-100">
        <div className="flex items-baseline justify-between gap-4 mb-5">
          <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-gray-400">
            事件线汇报
          </span>
          <span className="text-[10px] text-gray-400 tabular-nums">
            {organizationName} · 快照 {draft.snapshotAt.slice(0, 10)}
          </span>
        </div>
        <h1 className="text-[28px] font-light tracking-tight leading-tight text-gray-900">
          {narrative?.headline || draft.eventLineName}
        </h1>
        {el.primaryClientName && (
          <p className="mt-2 text-[12px] text-gray-500">
            <span className="text-[10px] uppercase tracking-[0.14em] text-gray-400 mr-1.5">客户</span>
            {el.primaryClientName}
          </p>
        )}
      </header>

      {/* 摘要数据 · 4 个极简指标 */}
      <div className="grid grid-cols-4 gap-8 px-8 py-6 border-b border-gray-100">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">主线转折</p>
          <p className="mt-2 text-[28px] font-light text-gray-900 leading-none tabular-nums">
            {narrative?.nodes.length || 0}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">任务</p>
          <p className="mt-2 text-[28px] font-light text-gray-900 leading-none tabular-nums">
            {taskCount}
            <span className="text-[14px] text-gray-400 ml-1">/ {doneTasks} 完成</span>
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">附件</p>
          <p className="mt-2 text-[28px] font-light text-gray-900 leading-none tabular-nums">
            {attachmentCount}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">参与</p>
          <p className="mt-2 text-[14px] text-gray-700 leading-tight line-clamp-2">
            {draft.participantNames.join(' · ') || '—'}
          </p>
        </div>
      </div>

      {/* Opening */}
      {narrative?.opening && (
        <div className="px-8 py-6 border-b border-gray-100">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-3">起源</p>
          <p className="text-[15px] font-light leading-[1.75] tracking-tight text-gray-800 border-l-[2px] border-gray-900 pl-5">
            {narrative.opening}
          </p>
        </div>
      )}

      {/* Nodes */}
      {narrative && narrative.nodes.length > 0 && (
        <div className="px-8 py-6 border-b border-gray-100">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-5">关键转折</p>
          <div className="space-y-7">
            {narrative.nodes.map((node, index) => (
              <article key={node.id} className="flex items-baseline gap-5">
                <span className="text-[24px] leading-none font-extralight tracking-tighter text-gray-200 tabular-nums">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3 mb-1.5">
                    <h3 className="text-[14.5px] font-semibold leading-snug text-gray-900">
                      {node.title}
                    </h3>
                    <span className="text-[10px] text-gray-400 tabular-nums">
                      {node.time.slice(0, 10)}
                    </span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-gray-700">{node.narrative}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      {/* 任务清单 */}
      {taskCount > 0 && (
        <div className="px-8 py-6 border-b border-gray-100">
          <div className="flex items-baseline justify-between mb-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">任务清单</p>
            <span className="text-[10px] tabular-nums text-gray-400">{taskCount} 条 · {doneTasks} 完成</span>
          </div>
          <div>
            {draft.tasks.slice(0, 20).map((task) => {
              const statusDot =
                task.status === 'done' ? 'bg-emerald-500'
                  : task.status === 'doing' ? 'bg-blue-400'
                    : task.status === 'rejected' ? 'bg-rose-400'
                      : 'bg-amber-400';
              return (
                <div key={task.id} className="flex items-baseline gap-3 py-2 border-b border-gray-50 last:border-0">
                  <span className={`h-1.5 w-1.5 rounded-full ${statusDot} shrink-0 mt-1.5`} />
                  <p className={`flex-1 text-[12.5px] ${task.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                    {task.title}
                  </p>
                  {task.ownerName && (
                    <span className="shrink-0 text-[10px] text-gray-400">{task.ownerName}</span>
                  )}
                  {task.ddl && (
                    <span className="shrink-0 text-[10px] text-gray-400 tabular-nums">{task.ddl}</span>
                  )}
                </div>
              );
            })}
            {taskCount > 20 && (
              <p className="mt-2 text-[11px] text-gray-400">…还有 {taskCount - 20} 条</p>
            )}
          </div>
        </div>
      )}

      {/* 附件清单 */}
      {attachmentCount > 0 && (
        <div className="px-8 py-6 border-b border-gray-100">
          <div className="flex items-baseline justify-between mb-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">附件清单</p>
            <span className="text-[10px] tabular-nums text-gray-400">{attachmentCount} 个</span>
          </div>
          <div>
            {draft.attachments.slice(0, 15).map((att) => (
              <div key={att.id} className="flex items-baseline gap-3 py-2 border-b border-gray-50 last:border-0">
                <span className="text-[10px] text-gray-400 tabular-nums shrink-0 uppercase">
                  {(att.kind || 'file').slice(0, 4)}
                </span>
                <p className="flex-1 text-[12.5px] text-gray-700 truncate" title={att.title}>{att.title}</p>
                <span className="shrink-0 text-[10px] text-gray-400 tabular-nums">
                  {att.sizeBytes ? `${Math.round(att.sizeBytes / 1024)} KB` : '—'}
                </span>
              </div>
            ))}
            {attachmentCount > 15 && (
              <p className="mt-2 text-[11px] text-gray-400">…还有 {attachmentCount - 15} 个</p>
            )}
          </div>
        </div>
      )}

      {/* Closing · 今天在哪里 */}
      {narrative?.closing && (
        <div className="px-8 py-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-3">今天在哪里</p>
          <p className="text-[14px] leading-[1.75] text-gray-700 border-l-[2px] border-gray-900 pl-5">
            {narrative.closing}
          </p>
        </div>
      )}

      {/* 没 narrative 时的兜底 */}
      {!narrative && (
        <div className="px-8 py-12 text-center border-t border-gray-100">
          <p className="text-[12.5px] text-gray-500">
            还没有 AI 主线还原。<span className="text-gray-400">在「主线还原」tab 生成后，这里会自动出现完整的报告预览。</span>
          </p>
        </div>
      )}
    </section>
  );
}
