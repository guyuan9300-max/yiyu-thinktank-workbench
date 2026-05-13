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
} from 'lucide-react';
import type {
  EventLineReportSnapshot,
  EventLineReportAttachment,
  EventLineActivity,
  EventLineTimelineNode as BackendEventLineTimelineNode,
  EventLineTimelineNodeKind as BackendEventLineTimelineNodeKind,
  Task,
} from '../../../shared/types.js';
import { getEventLineReportSnapshot, getOrgModelProfile, updateEventLine } from '../../lib/api.js';

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
    const hasMaterialContext = taskAttachments.length > 0 || MATERIAL_CORE_KEYWORDS.test(contextText);
    if (!title || !hasMaterialContext) continue;

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
  return {
    mainNodes: backendNodes
      .filter((node) => !['needs_review', 'system_trace'].includes(node.kind))
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
          <div className="mt-1 flex flex-wrap gap-1">
            {tags.map((tag) => (
              <span key={tag} className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${tag === '已解析' ? 'bg-emerald-50 text-emerald-700' : tag === '待确认' ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-[#4B66D8]'}`}>
                {tag}
              </span>
            ))}
            <span className="text-[10px] text-gray-400">{fileSizeLabel(att.sizeBytes)}</span>
          </div>
        </div>
        {openUrl ? (
          <a
            href={openUrl}
            target="_blank"
            rel="noreferrer"
            className="flex-shrink-0 rounded-lg px-2 py-1 text-[11px] font-bold text-[#4B66D8] hover:bg-blue-50 transition"
            title="打开原文"
          >
            打开原文
          </a>
        ) : null}
        {downloadUrl ? (
          <a
            href={downloadUrl}
            download={att.title}
            className="flex-shrink-0 rounded p-1 text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100 transition"
            title="下载文件"
          >
            <Download size={14} />
          </a>
        ) : null}
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
    return (
      <div
        key={node.id}
        className={`rounded-2xl border px-4 py-4 transition ${
          tone === 'review'
            ? 'border-amber-100 bg-amber-50/60'
            : tone === 'system'
              ? 'border-gray-100 bg-gray-50/70'
              : 'border-gray-100 bg-white hover:border-gray-200'
        }`}
      >
        <div className="flex items-start gap-3">
          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
            tone === 'review' ? 'bg-white text-amber-700' : tone === 'system' ? 'bg-white text-gray-400' : 'bg-[#EEF3FF] text-[#4B66D8]'
          }`}>
            {String(index + 1).padStart(2, '0')}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-[10px]">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold text-slate-500">
                {TIMELINE_KIND_LABELS[node.kind]}
              </span>
              <span className="text-gray-400">{timeLabel}</span>
              {node.ownerName && <span className="text-gray-400">负责人：{node.ownerName}</span>}
              {!node.ownerName && node.actorName && <span className="text-gray-400">记录人：{node.actorName}</span>}
            </div>
            <h3 className="mt-2 text-[15px] font-bold text-gray-900">{node.title}</h3>
            <p className="mt-1 whitespace-pre-wrap text-[12px] leading-6 text-gray-600">{node.summary}</p>
            {node.evidenceSummary && (
              <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/60 px-3 py-2">
                <p className="text-[10px] font-bold text-[#4B66D8]">解析依据</p>
                <p className="mt-1 text-[11px] leading-5 text-gray-600">{node.evidenceSummary}</p>
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {node.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-[#F1F4FF] px-2 py-0.5 text-[10px] font-bold text-[#4B66D8]">
                  {tag}
                </span>
              ))}
            </div>
            {node.warnings.length > 0 && (
              <p className="mt-2 text-[11px] leading-5 text-amber-700">{node.warnings.join(' · ')}</p>
            )}
            {renderTimelineAttachments(node.attachments, node.id)}
          </div>
        </div>
      </div>
    );
  };

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
          {(() => {
            const status = snapshot.eventLine.syncStatus;
            if (!status || status === 'synced') return null;
            const cfg: Record<string, { label: string; cls: string }> = {
              local: { label: '仅本地', cls: 'bg-gray-100 text-gray-500' },
              syncing: { label: '同步中', cls: 'bg-sky-50 text-sky-600' },
              pending: { label: '待同步', cls: 'bg-amber-50 text-amber-600' },
              error: { label: '同步失败', cls: 'bg-rose-50 text-rose-600' },
            };
            const item = cfg[status];
            if (!item) return null;
            return (
              <span className={`rounded-full px-2.5 py-1 font-bold ${item.cls}`} title={snapshot.eventLine.lastSyncError || undefined}>
                {item.label}
              </span>
            );
          })()}
        </div>
        {/* ── Completeness panel ── */}
        {typeof snapshot.eventLine.completenessScore === 'number' && (() => {
          const score = snapshot.eventLine.completenessScore;
          const status = snapshot.eventLine.completenessStatus || 'insufficient';
          const missing = snapshot.eventLine.completenessMissingSlots || [];
          const palette: Record<string, { bar: string; chip: string; label: string }> = {
            high_confidence: { bar: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700', label: '可对外汇报' },
            forecast_ready: { bar: 'bg-sky-500', chip: 'bg-sky-50 text-sky-700', label: '可形成预测' },
            summary_ready: { bar: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700', label: '可初步总结' },
            insufficient: { bar: 'bg-rose-500', chip: 'bg-rose-50 text-rose-700', label: '证据不足' },
          };
          const p = palette[status] || palette.insufficient;
          return (
            <div className="border-b border-gray-50 px-6 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="font-bold text-gray-700">证据完整度</span>
                  <span className="font-bold text-gray-900">{score} / 100</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${p.chip}`}>{p.label}</span>
                </div>
                {missing.length > 0 && (
                  <span className="text-[11px] text-gray-500">缺：{missing.slice(0, 4).join('、')}{missing.length > 4 ? '…' : ''}</span>
                )}
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100">
                <div className={`h-1.5 rounded-full transition-all ${p.bar}`} style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
              </div>
            </div>
          );
        })()}

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
          <div className="mb-5 flex items-center justify-between gap-3">
            <div className="inline-flex rounded-full bg-[#F4F6FB] p-1">
              <button
                type="button"
                className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${viewMode === 'timeline' ? 'bg-white text-[#1D3361] shadow-[0_6px_18px_rgba(31,56,110,0.12)]' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setViewMode('timeline')}
              >
                主线还原
              </button>
              <button
                type="button"
                className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${viewMode === 'tasks' ? 'bg-white text-[#1D3361] shadow-[0_6px_18px_rgba(31,56,110,0.12)]' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setViewMode('tasks')}
              >
                按任务查看
              </button>
              <button
                type="button"
                className={`rounded-full px-4 py-2 text-[12px] font-bold transition ${viewMode === 'report' ? 'bg-white text-[#1D3361] shadow-[0_6px_18px_rgba(31,56,110,0.12)]' : 'text-gray-500 hover:text-gray-700'}`}
                onClick={() => setViewMode('report')}
              >
                报告导出
              </button>
            </div>
            <p className="text-right text-[11px] text-gray-400">
              {viewMode === 'timeline'
                ? `当前主线 ${timelineModel?.mainNodes.length ?? 0} 个节点，待确认 ${timelineModel?.reviewNodes.length ?? 0} 个`
                : viewMode === 'tasks'
                  ? '按任务聚合附件、会议纪要和补充材料'
                  : (reportPreview?.hasRenderableContent ? '当前为动态模拟汇报：封面页 + 目录页' : '当前资料不足，建议回到按任务查看补资料')}
            </p>
          </div>

          {viewMode === 'timeline' && timelineModel ? (
            <div className="space-y-5 pb-6">
              <div className="grid grid-cols-4 gap-2">
                <div className="rounded-2xl border border-[#BFD0FF] bg-[#F3F6FF] px-4 py-3">
                  <p className="text-[11px] font-bold text-[#3857D9]">主线节点</p>
                  <p className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[#1D3361]">{timelineModel.mainNodes.length}</p>
                </div>
                <div className="rounded-2xl border border-gray-100 bg-white px-4 py-3">
                  <p className="text-[11px] font-bold text-gray-500">待确认</p>
                  <p className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-gray-900">{timelineModel.reviewNodes.length}</p>
                </div>
                <div className="rounded-2xl border border-gray-100 bg-white px-4 py-3">
                  <p className="text-[11px] font-bold text-gray-500">已解析附件</p>
                  <p className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-gray-900">
                    {draft.attachments.filter((att) => att.documentId && att.parseStatus === 'ready').length}
                  </p>
                </div>
                <div className="rounded-2xl border border-gray-100 bg-white px-4 py-3">
                  <p className="text-[11px] font-bold text-gray-500">系统痕迹</p>
                  <p className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-gray-900">{timelineModel.systemNodes.length}</p>
                </div>
              </div>

              {timelineModel.mainNodes.length > 0 ? (
                <div className="space-y-3">
                  {timelineModel.mainNodes.map((node, index) => renderTimelineNode(node, index))}
                </div>
              ) : (
                <div className="rounded-2xl border border-gray-100 bg-white px-4 py-8 text-center text-[12px] text-gray-400">
                  当前还没有足够信息形成主线节点。
                </div>
              )}

              {timelineModel.reviewNodes.length > 0 && (
                <div className="space-y-3">
                  <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                    <p className="text-[12px] font-bold text-amber-800">待确认节点</p>
                    <p className="mt-1 text-[11px] leading-5 text-amber-700">这些材料缺少归属、含测试文件或解析状态不完整，暂不进入主线叙事。</p>
                  </div>
                  {timelineModel.reviewNodes.map((node, index) => renderTimelineNode(node, index, 'review'))}
                </div>
              )}

              {timelineModel.systemNodes.length > 0 && (
                <div className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 text-left"
                    onClick={() => setShowSystemTraces((prev) => !prev)}
                  >
                    <span>
                      <span className="block text-[12px] font-bold text-gray-700">系统痕迹</span>
                      <span className="mt-1 block text-[11px] text-gray-400">创建、上传、更新等审计流水保留在这里</span>
                    </span>
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-gray-500 shadow-sm">
                      {showSystemTraces ? '收起' : `展开 ${timelineModel.systemNodes.length}`}
                    </span>
                  </button>
                  {showSystemTraces && (
                    <div className="mt-3 space-y-2">
                      {timelineModel.systemNodes.map((node, index) => renderTimelineNode(node, index, 'system'))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : viewMode === 'report' && reportPreview ? (
            reportPreview.hasRenderableContent ? (
            <div className="mx-auto max-w-[760px] space-y-6 pb-6">
              {onOpenAIReport && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenAIReport({
                      eventLineName: draft.eventLineName || '',
                      clientName: organizationName || '',
                    })
                  }
                  className="group flex w-full items-center gap-4 rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 via-white to-indigo-50 px-5 py-4 text-left transition hover:border-blue-400 hover:shadow-lg"
                >
                  <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-md transition group-hover:scale-105">
                    <span className="text-[20px]">✨</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-bold text-gray-900">
                      用 AI 主理人生成完整报告
                    </p>
                    <p className="mt-1 text-[12px] text-gray-600">
                      豆包推骨架 → 章节并行起草 + 信息图 → 一键导出 docx / Markdown ·
                      约 2-4 分钟
                    </p>
                  </div>
                  <div className="flex-shrink-0 text-[12px] font-medium text-blue-600 transition group-hover:translate-x-1">
                    开始 →
                  </div>
                </button>
              )}
              <p className="-mt-1 text-center text-[11px] text-gray-400">
                ↓ 下方为上一代静态预览（封面页 + 目录页 mock）
              </p>
              <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_70px_rgba(56,86,174,0.10)]">
                <div className="relative min-h-[1020px] px-10 py-10 text-[#3F3A36]">
                  <div
                    className="absolute inset-0"
                    style={{
                      background: 'radial-gradient(circle at 18% 14%, rgba(93, 125, 255, 0.14), transparent 26%), radial-gradient(circle at 85% 84%, rgba(123, 168, 255, 0.12), transparent 22%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                    }}
                  />
                  <div className="absolute right-[-90px] top-[-90px] h-[280px] w-[280px] rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(112,143,255,0.26),rgba(112,143,255,0.05)_62%,transparent_74%)]" />
                  <div className="absolute bottom-[40px] right-[8px] h-[140px] w-[140px] rounded-full bg-[radial-gradient(circle_at_center,rgba(122,173,255,0.16),transparent_74%)]" />

                  <div className="relative flex h-full flex-col">
                    <div>
                      <p className="text-[11px] font-bold tracking-[0.16em] text-[#67718B]">{reportPreview.organizationName}</p>
                      <p className="mt-1 text-[11px] font-medium text-[#8A95AF]">{reportPreview.brandCaption}</p>
                      <span className="mt-5 inline-flex rounded-full bg-[#5B7BFE] px-4 py-2 text-[11px] font-bold text-white">
                        封面页
                      </span>
                    </div>

                    <div className="mt-24 max-w-[620px]">
                      <p className="text-[14px] font-semibold tracking-[0.08em] text-[#4B66D8]">{reportPreview.reportSubtitle}</p>
                      <h3 className="mt-5 text-[52px] font-semibold leading-[1.08] tracking-[-0.04em] text-[#3F3A36]">
                        {reportPreview.reportTitle}
                      </h3>
                      <div className="mt-7 h-[4px] w-12 rounded-full bg-[#5B7BFE]" />
                      <p className="mt-7 max-w-[560px] text-[16px] leading-8 text-[#6F685F]">
                        {reportPreview.coverSummary}
                      </p>
                    </div>

                    <div className="mt-20 max-w-[560px]">
                      <p className="text-[32px] font-semibold leading-[1.45] tracking-[-0.03em] text-[#5A524A]">
                        {reportPreview.coreJudgment}
                      </p>
                      <p className="mt-6 max-w-[460px] text-[13px] leading-6 text-[#8A8177]">
                        {reportPreview.coreJudgmentNote}
                      </p>
                    </div>

                    <div className="mt-auto rounded-[28px] border border-[#DDE4F3] bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(239,245,255,0.95)_100%)] px-6 py-6">
                      <div className="grid grid-cols-3 gap-4">
                        {reportPreview.supportCards.map((card, index) => (
                          <div
                            key={card.label}
                            className={`min-w-0 ${index < reportPreview.supportCards.length - 1 ? 'border-r border-[#D7E0F2] pr-4' : ''}`}
                          >
                            <p className="text-[11px] font-bold tracking-[0.12em] text-[#6C7897]">{card.label}</p>
                            <p className="mt-3 text-[22px] font-semibold tracking-[-0.02em] text-[#4B443E]">{card.value}</p>
                            <p className="mt-2 text-[12px] leading-5 text-[#6E778E]">{card.note}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 flex items-end justify-between text-[12px] text-[#9B9388]">
                      <p>{reportPreview.pageOneNote}</p>
                      <span className="font-medium tracking-[0.18em] text-[#4B66D8]">01 / 02</span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_60px_rgba(56,86,174,0.08)]">
                <div className="relative min-h-[1020px] px-10 py-10 text-[#3F3A36]">
                  <div
                    className="absolute inset-0"
                    style={{
                      background: 'radial-gradient(circle at 10% 12%, rgba(102, 132, 255, 0.10), transparent 24%), radial-gradient(circle at 88% 12%, rgba(132, 171, 255, 0.20), transparent 18%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                    }}
                  />
                  <div className="absolute right-[22px] top-[-26px] h-[170px] w-[170px] rounded-full bg-[radial-gradient(circle_at_center,rgba(103,134,255,0.22),transparent_70%)]" />

                  <div className="relative">
                    <div className="flex items-start justify-between gap-6">
                      <div>
                        <p className="text-[11px] font-bold tracking-[0.18em] text-[#6B7692]">目录页</p>
                        <h3 className="mt-3 text-[34px] font-semibold tracking-[-0.03em] text-[#3F3A36]">目录与阅读指引</h3>
                        <div className="mt-4 h-[4px] w-12 rounded-full bg-[#5B7BFE]" />
                        <p className="mt-5 max-w-[520px] text-[13px] leading-6 text-[#756D65]">
                          {reportPreview.readingIntro}
                        </p>
                      </div>
                      <div className="rounded-[24px] border border-[#D7E0F2] bg-[linear-gradient(180deg,rgba(250,252,255,0.98)_0%,rgba(239,245,255,0.95)_100%)] px-5 py-4 shadow-[0_10px_24px_rgba(56,86,174,0.08)]">
                        <p className="text-[10px] font-bold tracking-[0.18em] text-[#4B66D8]">Report Profile</p>
                        <div className="mt-3 flex items-center gap-2 text-[13px] font-semibold text-[#4B443E]">
                          <Clock size={14} />
                          {reportPreview.reviewWindow}
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-[13px] text-[#756D65]">
                          <Users size={14} />
                          {reportPreview.audienceLabel}
                        </div>
                      </div>
                    </div>

                    <div className="mt-8 grid grid-cols-12 gap-5">
                      <div className="col-span-7">
                        <div className="space-y-3">
                          {reportPreview.tocSections.slice(0, 7).map((section) => (
                            <div key={section.index} className="rounded-[22px] border border-[#DFE6F6] bg-white/82 px-5 py-4 shadow-[0_10px_24px_rgba(56,86,174,0.05)]">
                              <div className="flex items-start gap-4">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[#CFDBFB] bg-[#EEF3FF] text-[13px] font-bold text-[#4B66D8]">
                                  {section.index}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-start justify-between gap-4">
                                    <p className="text-[16px] font-semibold tracking-[-0.02em] text-[#4B443E]">{section.title}</p>
                                    <span className="rounded-full bg-[#EAF0FF] px-2.5 py-1 text-[10px] font-bold text-[#4B66D8]">
                                      {section.pages}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-[12px] leading-6 text-[#7A7269]">{section.summary}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="col-span-5 space-y-5">
                        <div className="rounded-[28px] bg-[linear-gradient(180deg,#5B7BFE_0%,#3F5EF7_100%)] p-6 text-white shadow-[0_18px_40px_rgba(63,94,247,0.28)]">
                          <p className="text-[11px] font-bold tracking-[0.18em] text-white/75">建议阅读顺序</p>
                          <div className="mt-5 space-y-3">
                            {reportPreview.readingSteps.map((item, index) => (
                              <div key={`${item}-${index}`} className="flex items-start gap-3 rounded-[18px] bg-white/10 px-4 py-3">
                                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-bold text-[#3F5EF7]">
                                    {index + 1}
                                  </span>
                                <p className="text-[12px] leading-6 text-white/92">{item}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-[28px] border border-[#DFE6F6] bg-white/86 p-6 shadow-[0_12px_32px_rgba(56,86,174,0.05)]">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-[11px] font-bold tracking-[0.18em] text-[#8F857A]">审阅问题</p>
                              <p className="mt-2 text-[22px] font-semibold tracking-[-0.03em] text-[#4B443E]">本报告回答什么</p>
                            </div>
                            <FileBadge size={18} className="text-[#4B66D8]" />
                          </div>
                          <div className="mt-5 space-y-3">
                            {reportPreview.reviewQuestions.map((item, index) => (
                              <div key={`${item}-${index}`} className="rounded-[18px] bg-[#F2F6FF] px-4 py-4">
                                <p className="text-[11px] font-bold tracking-[0.12em] text-[#4B66D8]">0{index + 1}</p>
                                <p className="mt-1 text-[13px] leading-6 text-[#5A524A]">{item}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-[28px] border border-[#D7E0F2] bg-[linear-gradient(180deg,rgba(250,252,255,0.96)_0%,rgba(239,245,255,0.92)_100%)] p-6 shadow-[0_12px_32px_rgba(56,86,174,0.06)]">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-[11px] font-bold tracking-[0.18em] text-[#8F857A]">交付组成</p>
                              <p className="mt-2 text-[22px] font-semibold tracking-[-0.03em] text-[#4B443E]">建议纳入的模块</p>
                            </div>
                            <Paperclip size={18} className="text-[#4B66D8]" />
                          </div>
                          <div className="mt-4 space-y-3">
                            {reportPreview.deliverables.map((deliverable, index) => (
                              <div key={`${deliverable}-${index}`} className="rounded-[18px] px-4 py-3">
                                <div className="flex items-center gap-3">
                                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EAF0FF] text-[11px] font-bold text-[#4B66D8]">
                                    {index + 1}
                                  </span>
                                  <p className="text-[13px] font-semibold leading-6 text-[#5A524A]">{deliverable}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 flex items-end justify-between text-[12px] text-[#8F867B]">
                      <p>{reportPreview.pageTwoNote}</p>
                      <span className="font-medium tracking-[0.18em] text-[#4B66D8]">02 / 02</span>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            ) : (
              <div className="mx-auto max-w-[760px] pb-6">
                <section className="overflow-hidden rounded-[32px] border border-[#DDE4F3] bg-[#F9FBFF] shadow-[0_24px_70px_rgba(56,86,174,0.10)]">
                  <div className="relative min-h-[520px] px-10 py-10 text-[#3F3A36]">
                    <div
                      className="absolute inset-0"
                      style={{
                        background: 'radial-gradient(circle at 20% 16%, rgba(93, 125, 255, 0.14), transparent 26%), radial-gradient(circle at 85% 85%, rgba(123, 168, 255, 0.12), transparent 20%), linear-gradient(180deg, #F9FBFF 0%, #EEF3FD 100%)',
                      }}
                    />
                    <div className="relative flex h-full flex-col items-start justify-center">
                      <span className="inline-flex rounded-full bg-[#5B7BFE] px-4 py-2 text-[11px] font-bold text-white">
                        模拟报告暂不可用
                      </span>
                      <h3 className="mt-6 text-[38px] font-semibold leading-[1.16] tracking-[-0.04em] text-[#3F3A36]">
                        {reportPreview.emptyStateTitle}
                      </h3>
                      <p className="mt-5 max-w-[560px] text-[16px] leading-8 text-[#6F685F]">
                        {reportPreview.emptyStateDescription}
                      </p>
                      <div className="mt-8 flex flex-wrap items-center gap-3 text-[13px] text-[#5D6781]">
                        <span className="rounded-full bg-white/84 px-4 py-2 shadow-[0_8px_20px_rgba(56,86,174,0.08)]">
                          当前事件线：{reportPreview.reportTitle}
                        </span>
                        <span className="rounded-full bg-white/84 px-4 py-2 shadow-[0_8px_20px_rgba(56,86,174,0.08)]">
                          快照日期：{reportPreview.snapshotAtLabel}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="mt-10 rounded-full bg-[#5B7BFE] px-5 py-2.5 text-[13px] font-bold text-white transition hover:bg-[#3F5EF7]"
                        onClick={() => setViewMode('tasks')}
                      >
                        去素材清单补资料
                      </button>
                    </div>
                  </div>
                </section>
              </div>
            )
          ) : viewMode === 'tasks' && materialModel ? (
            <div className="space-y-5">
              <div className="grid grid-cols-5 gap-2">
                {(['core', 'review', 'supplement', 'system', 'gaps'] as EventLineMaterialTabKey[]).map((tab) => {
                  const count = tab === 'gaps' ? materialModel.gaps.length : materialModel.groups[tab].length;
                  const active = activeMaterialTab === tab;
                  return (
                    <button
                      key={tab}
                      type="button"
                      className={`min-w-0 rounded-2xl border px-3 py-3 text-left transition ${
                        active
                          ? 'border-[#BFD0FF] bg-[#F3F6FF] shadow-[0_8px_20px_rgba(91,123,254,0.10)]'
                          : 'border-gray-100 bg-white hover:border-gray-200'
                      }`}
                      onClick={() => {
                        setActiveMaterialTab(tab);
                        setShowSystemTraces(tab === 'system');
                      }}
                    >
                      <p className={`text-[11px] font-bold ${active ? 'text-[#3857D9]' : 'text-gray-500'}`}>
                        {MATERIAL_GROUP_META[tab].label}
                      </p>
                      <p className={`mt-1 text-[22px] font-semibold tracking-[-0.03em] ${active ? 'text-[#1D3361]' : 'text-gray-900'}`}>
                        {count}
                      </p>
                    </button>
                  );
                })}
              </div>

              <div className="rounded-2xl border border-gray-100 bg-[#FAFBFF] px-4 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[12px] font-bold text-gray-800">{MATERIAL_GROUP_META[activeMaterialTab].label}</p>
                    <p className="mt-1 text-[11px] leading-5 text-gray-500">{MATERIAL_GROUP_META[activeMaterialTab].description}</p>
                  </div>
                  <div className="shrink-0 rounded-full bg-white px-3 py-1 text-[11px] font-bold text-gray-500 shadow-sm">
                    附件 {draft.attachments.length} · 任务 {draft.tasks.length}
                  </div>
                </div>
                {activeMaterialTab !== 'gaps' && materialModel.gaps.length > 0 && (
                  <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50/70 px-3 py-2">
                    <p className="text-[11px] font-bold text-amber-700">待补材料提示</p>
                    <p className="mt-1 text-[11px] leading-5 text-amber-700">
                      {materialModel.gaps.slice(0, 2).join(' ')}
                      {materialModel.gaps.length > 2 ? ` 另有 ${materialModel.gaps.length - 2} 项。` : ''}
                    </p>
                  </div>
                )}
              </div>

              {activeMaterialTab === 'gaps' ? (
                <div className="space-y-2">
                  {materialModel.gaps.length > 0 ? materialModel.gaps.map((gap, index) => (
                    <div key={`${gap}-${index}`} className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                      <div className="flex items-start gap-3">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-bold text-amber-700">
                          {index + 1}
                        </span>
                        <p className="text-[12px] leading-6 text-amber-800">{gap}</p>
                      </div>
                    </div>
                  )) : (
                    <div className="rounded-2xl border border-gray-100 bg-white px-4 py-8 text-center text-[12px] text-gray-400">
                      {MATERIAL_GROUP_META.gaps.emptyText}
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
                      <div
                        key={material.id}
                        className="group rounded-2xl border border-gray-100 bg-white px-4 py-3 transition hover:border-gray-200"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2 text-[10px]">
                              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold text-slate-500">
                                {material.sourceLabel}
                              </span>
                              {material.statusLabel && (
                                <span className="rounded bg-blue-50 px-1.5 py-0.5 font-bold text-[#4B66D8]">
                                  {material.statusLabel}
                                </span>
                              )}
                              {material.happenedAt && <span className="text-gray-400">{formatTs(material.happenedAt)}</span>}
                              {material.actorName && <span className="text-gray-400">— {material.actorName}</span>}
                            </div>
                            <p className="mt-2 text-[14px] font-bold text-gray-900">{material.title}</p>
                            {material.summary && (
                              <p className="mt-1 text-[12px] leading-5 text-gray-500 whitespace-pre-wrap">{material.summary}</p>
                            )}
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {material.tags.map((tag) => (
                                <span key={tag} className="rounded-full bg-[#F1F4FF] px-2 py-0.5 text-[10px] font-bold text-[#4B66D8]">
                                  {tag}
                                </span>
                              ))}
                              {material.duplicateCount && (
                                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                                  重复 {material.duplicateCount} 条
                                </span>
                              )}
                              {material.versionCount && (
                                <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                                  {material.versionCount} 组多版本
                                </span>
                              )}
                              {material.testAttachmentCount && (
                                <span className="rounded-full bg-orange-50 px-2 py-0.5 text-[10px] font-bold text-orange-700">
                                  测试素材 {material.testAttachmentCount}
                                </span>
                              )}
                            </div>
                            {material.warnings.length > 0 && (
                              <p className="mt-2 text-[11px] leading-5 text-amber-700">
                                {material.warnings.join(' · ')}
                              </p>
                            )}
                          </div>

                          <div className="flex shrink-0 items-center gap-1">
                            <button
                              type="button"
                              title={isDocsExpanded ? '折叠文档' : '展开文档'}
                              disabled={docGroups.length === 0}
                              className={`rounded p-1 transition ${docGroups.length === 0 ? 'text-gray-200 cursor-default' : isDocsExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
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
                              className={`rounded p-1 transition ${imageGroups.length === 0 ? 'text-gray-200 cursor-default' : isImagesExpanded ? 'bg-blue-100 text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
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
                            <button
                              type="button"
                              title={downloadableAtts.length ? `下载素材附件（${downloadableAtts.length}个）` : '暂无可下载附件'}
                              disabled={downloadableAtts.length === 0}
                              className={`rounded p-1 transition ${downloadableAtts.length ? 'text-gray-400 hover:text-[#5B7BFE] hover:bg-gray-100' : 'text-gray-200 cursor-default'}`}
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
                      </div>
                    );
                  }) : (
                    <div className="rounded-2xl border border-gray-100 bg-white px-4 py-8 text-center text-[12px] text-gray-400">
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
