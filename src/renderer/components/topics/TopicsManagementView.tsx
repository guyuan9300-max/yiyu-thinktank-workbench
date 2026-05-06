import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Bookmark, CheckSquare, FileText, Pause, Pencil, Play, Plus, RefreshCw, Search, Send, Share2, Sparkles, Target, Trash2, X } from 'lucide-react';

import type {
  MentionCandidate,
  SessionUser,
  Task,
  TaskList,
  TaskSettings,
  TopicCandidate,
  TopicCandidateChatMessage,
  TopicCandidateInsight,
  TopicContextRef,
  TopicIntelligenceDirection,
  TopicsSettings,
  TopicRadar,
  TopicRadarPayload,
  TopicRadarPreferredSource,
  TopicRadarPushFrequency,
  TopicShareRecipient,
} from '../../../shared/types';
import {
  assistRadarDraft,
  askCandidateQuestion,
  captureIntelligenceRadarTest,
  createRadar,
  deleteRadar,
  favoriteIntelligenceItem,
  getCandidateInsights,
  getMentionCandidates,
  promoteCandidateTasks,
  saveTaskNote,
  shareIntelligenceItem,
  suggestRadarSourceLabel,
  unfavoriteIntelligenceItem,
  updateRadar,
} from '../../lib/api';
import { TopicIntelInboxCard } from './TopicIntelInboxCard';

type TopicCandidateLocalPreference = {
  saved?: boolean;
  note?: string;
  tags?: string[];
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
  collaboratorIds: string[];
  note: string;
};

type TopicRadarDraft = {
  id: string;
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
  contextRefs: TopicContextRef[];
  shareRecipients: TopicShareRecipient[];
  priorityUrls: string[];
  fetchEnabled: boolean;
  pushFrequency: TopicRadarPushFrequency;
  pushTime: string;
  pushWeekday: number | null;
};

type TopicStatusView = 'favorite' | 'shared' | 'sent' | 'task_linked';
type TopicBadgeFilter = 'all' | 'follow_up' | 'focus' | 'none';
type TopicContextDraftType = 'custom_focus' | 'organization_type' | 'service_object' | 'issue_area' | 'region';
type TopicRadarModalMode = 'create' | 'manage';
type TopicTaskModalNotice = {
  type: 'success' | 'error' | 'info';
  text: string;
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
  focusCandidateId?: string | null;
  onFocusCandidateHandled?: () => void;
  flash: (type: 'success' | 'error' | 'info', text: string) => void;
  onTopicsReload: () => Promise<unknown>;
  onTasksReload: () => Promise<unknown>;
};

const TOPIC_LOCAL_STATE_STORAGE_KEY = 'yiyu.workbench.topics.local-state.v2';
const TOPIC_SHARED_READ_AT_STORAGE_KEY = 'yiyu.workbench.topics.shared-read-at.v1';
const TOPIC_PAGE_SIZE = 6;
const TOPIC_DIRECTIONS: Array<{ id: TopicIntelligenceDirection; label: string }> = [
  { id: 'policy_environment', label: '政策环境' },
  { id: 'resource_collaboration', label: '资源与合作' },
  { id: 'public_opinion', label: '舆情与公众理解' },
  { id: 'industry_trend_case', label: '行业趋势与案例' },
];
const TOPIC_BADGE_FILTERS: Array<{ id: TopicBadgeFilter; label: string }> = [
  { id: 'all', label: '全部标记' },
  { id: 'follow_up', label: '待跟进' },
  { id: 'focus', label: '重点' },
  { id: 'none', label: '无标记' },
];
const TOPIC_CONTEXT_TYPE_OPTIONS: Array<{ id: TopicContextDraftType; label: string; placeholder: string }> = [
  { id: 'custom_focus', label: '自定义关注', placeholder: '例如：教师赋能、AI 陪伴、筹资转化' },
  { id: 'organization_type', label: '组织类型', placeholder: '例如：基金会、学校、社区组织' },
  { id: 'service_object', label: '服务对象', placeholder: '例如：儿童、青少年、一线社工' },
  { id: 'issue_area', label: '议题领域', placeholder: '例如：心理健康、社区治理、公益数字化' },
  { id: 'region', label: '地区范围', placeholder: '例如：广东、深圳、长三角' },
];
const TOPIC_CONTEXT_PRESETS: Record<TopicContextDraftType, string[]> = {
  custom_focus: [],
  organization_type: ['公益组织', '基金会', '学校', '社区组织', '企业 CSR'],
  service_object: ['儿童', '青少年', '老人', '残障群体', '一线社工'],
  issue_area: ['心理健康', '教育公平', '社区治理', '公益数字化', '筹资与传播'],
  region: ['全国', '广东', '深圳', '长三角', '粤港澳大湾区'],
};
const TOPIC_STATUS_VIEW_COPY: Record<TopicStatusView, { description: string; emptyTitle: string; emptyDescription: string }> = {
  favorite: {
    description: '这里集中展示当前用户收藏过的情报，不受当前方向、雷达、标记或搜索条件影响。',
    emptyTitle: '当前还没有收藏情报',
    emptyDescription: '在情报卡片上点击“收藏”后，会出现在这里，方便后续复盘或集中处理。',
  },
  shared: {
    description: '这里集中展示其他成员共享给当前用户的情报，不受当前方向、雷达、标记或搜索条件影响。',
    emptyTitle: '当前还没有共享给你的情报',
    emptyDescription: '同事通过情报卡片共享给你后，会出现在这里。',
  },
  sent: {
    description: '这里集中展示当前用户已经共享出去的情报，方便回看自己推荐过什么。',
    emptyTitle: '当前还没有共享出去的情报',
    emptyDescription: '你通过情报卡片共享给同事后，会出现在这里。',
  },
  task_linked: {
    description: '这里集中展示已经创建过任务的情报，不受当前方向、雷达、标记或搜索条件影响。',
    emptyTitle: '当前还没有转成任务的情报',
    emptyDescription: '在情报卡片上点击“转任务”并保存后，会出现在这里。',
  },
};
const TOPIC_WEEKDAY_LABELS = ['', '一', '二', '三', '四', '五', '六', '日'];
const EMPTY_TOPIC_LOCAL_STATE: TopicLocalState = {
  byCandidateId: {},
};
const EMPTY_TOPIC_CANDIDATE_PREFERENCE: TopicCandidateLocalPreference = {
  saved: false,
  note: '',
  tags: [],
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

function topicLocalStateStorageKey(viewerId: string) {
  return `${TOPIC_LOCAL_STATE_STORAGE_KEY}:${normalizeTopicIdentity(viewerId) || 'local-device-user'}`;
}

function readTopicLocalState(viewerId: string): TopicLocalState {
  if (typeof window === 'undefined') return EMPTY_TOPIC_LOCAL_STATE;
  try {
    const raw = window.localStorage.getItem(topicLocalStateStorageKey(viewerId));
    if (!raw) return EMPTY_TOPIC_LOCAL_STATE;
    return normalizeTopicLocalState(JSON.parse(raw));
  } catch {
    return EMPTY_TOPIC_LOCAL_STATE;
  }
}

function writeTopicLocalState(state: TopicLocalState, viewerId: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(topicLocalStateStorageKey(viewerId), JSON.stringify(state));
  } catch {
    // In some Electron/browser contexts storage may be unavailable or read-only.
  }
}

function readSharedReadAtState(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(TOPIC_SHARED_READ_AT_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeSharedReadAtState(state: Record<string, string>) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(TOPIC_SHARED_READ_AT_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Local unread markers are best-effort only.
  }
}

function currentIsoWeekday() {
  const day = new Date().getDay();
  return day === 0 ? 7 : day;
}

function weekdayLabel(value?: number | null) {
  return TOPIC_WEEKDAY_LABELS[value || currentIsoWeekday()] || TOPIC_WEEKDAY_LABELS[currentIsoWeekday()];
}

function pushFrequencyLabel(frequency: TopicRadarPushFrequency, weekday?: number | null) {
  if (frequency === 'daily') return '每天';
  if (frequency === 'workday') return '工作日';
  if (frequency === 'weekly') return `每周（${weekdayLabel(weekday)}）`;
  return '仅手动';
}

function formatTopicDateTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function topicRadarStatusLabel(radar: { status?: string | null; fetchEnabled?: boolean | null }) {
  if (radar.status === 'archived') return '已归档';
  if (radar.status === 'paused' || !radar.fetchEnabled) return '已暂停';
  if (radar.status === 'trial') return '试运行';
  return '运行中';
}

function topicFetchStatusLabel(status?: string | null) {
  if (status === 'done') return '抓取完成';
  if (status === 'running') return '抓取中';
  if (status === 'fetch_success') return '抓取完成，待解析';
  if (status === 'fetch_failed') return '抓取失败';
  if (status === 'parsing') return '解析中';
  if (status === 'parse_success') return '解析完成';
  if (status === 'parse_failed') return '解析失败';
  if (status === 'queued') return '等待抓取';
  return '暂无记录';
}

function nextPushTextForRadar(radar: { fetchEnabled?: boolean | null; pushFrequency?: TopicRadarPushFrequency | null; pushTime?: string | null; pushWeekday?: number | null; nextPushAt?: string | null }) {
  if (!radar.fetchEnabled) return '自动抓取已暂停';
  if (radar.nextPushAt) return `预计 ${formatTopicDateTime(radar.nextPushAt)}`;
  const time = radar.pushTime || '09:00';
  const frequency = radar.pushFrequency || 'manual';
  if (frequency === 'daily') return `每天 ${time} 推送`;
  if (frequency === 'workday') return `工作日 ${time} 推送`;
  if (frequency === 'weekly') return `每周（${weekdayLabel(radar.pushWeekday)}）${time} 推送`;
  return '仅手动试跑';
}

function radarFetchSummaryText(fetch?: TopicRadar['lastFetch'] | null) {
  if (!fetch) return '还没有试跑记录';
  const pieces = [
    `候选 ${fetch.candidateCount ?? fetch.fetchedCount ?? 0}`,
    `入库 ${fetch.insertedCount ?? fetch.createdCount ?? 0}`,
    `重复 ${fetch.duplicateCount ?? fetch.skippedCount ?? 0}`,
  ];
  const parseFailedCount = fetch.parseFailedCount || 0;
  const sourceFailedCount = fetch.sourceFailedCount || 0;
  if (parseFailedCount > 0) pieces.push(`解析失败 ${parseFailedCount}`);
  if (sourceFailedCount > 0) pieces.push(`来源失败 ${sourceFailedCount}`);
  return pieces.join(' / ');
}

function clampTopicPage(page: number, totalCount: number) {
  const totalPages = Math.max(1, Math.ceil(totalCount / TOPIC_PAGE_SIZE));
  return Math.min(Math.max(1, page), totalPages);
}

function shareRecordTime(value?: string | null) {
  const time = new Date(value || '').getTime();
  return Number.isNaN(time) ? 0 : time;
}

function latestReceivedShareTime(candidate: TopicCandidate) {
  return Math.max(0, ...(candidate.viewerShareRecords || []).map((record) => shareRecordTime(record.createdAt)));
}

function latestSentShareTime(candidate: TopicCandidate) {
  return Math.max(0, ...(candidate.viewerSentShareRecords || []).map((record) => shareRecordTime(record.createdAt)));
}

function buildTopicAttachmentNote(
  candidate: TopicCandidate,
  radarTitle: string,
  insight: TopicCandidateInsight | null | undefined,
  operatorNote: string,
) {
  const lines = [
    '【情报来源】',
    `标题：${candidate.title}`,
    `来源：${candidate.source}`,
    `所属雷达：${radarTitle}`,
  ];

  if (candidate.publishedAt) {
    lines.push(`发布时间：${candidate.publishedAt}`);
  }
  lines.push(`情报 ID：${candidate.id}`);
  if (candidate.sourceUrl) {
    lines.push(`外部信息源：${candidate.sourceUrl}`);
  }

  const relationReasons = [
    candidate.relevanceReason?.trim() || '',
    ...(insight?.recommendationReasons?.filter((item) => item.trim()) || []),
  ].filter(Boolean);
  const keyPoints = insight?.keyPoints?.filter((item) => item.trim()) || [];
  const practicalUses = insight?.practicalUses?.filter((item) => item.trim()) || [];
  const editorialNote = insight?.editorialNote?.trim() || '';
  const discussionPrompts = insight?.discussionPrompts?.filter((item) => item.trim()) || [];
  const sentShares = candidate.viewerSentShareRecords || [];
  const receivedShares = candidate.viewerShareRecords || [];

  lines.push('');
  lines.push('【AI 摘要】');
  lines.push(insight?.overview?.trim() || candidate.summary || '当前只有原始摘要，尚未形成完整综述。');

  lines.push('');
  lines.push('【为什么可能相关】');
  if (relationReasons.length) {
    relationReasons.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push(`1. 这篇内容当前被归入「${radarTitle}」雷达下，建议先按这个主题核对。`);
  }

  lines.push('');
  lines.push('【建议动作】');
  lines.push(candidate.suggestedAction?.trim() || '建议先核对原文，再决定是否需要继续推进。');

  lines.push('');
  lines.push('【核心观点】');
  if (keyPoints.length) {
    keyPoints.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 当前还没有稳定的核心观点提炼，建议直接点开原文。');
  }

  lines.push('');
  lines.push('【机会或风险判断】');
  lines.push(editorialNote || '当前还没有稳定的机会或风险判断，建议先结合原文和核心观点继续讨论。');

  lines.push('');
  lines.push('【可继续展开】');
  if (practicalUses.length) {
    practicalUses.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 后续可围绕它是否值得写成文章、是否需要团队跟进继续讨论。');
  }

  lines.push('');
  lines.push('【值得继续追问的问题】');
  if (discussionPrompts.length) {
    discussionPrompts.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 这篇内容背后最值得继续追问的变化，到底是什么？');
  }

  if (receivedShares.length || sentShares.length) {
    lines.push('');
    lines.push('【共享记录】');
    receivedShares.forEach((share) => {
      lines.push(`收到共享：${share.sharedByName || share.sharedBy || '未知成员'}${share.reason ? `；推荐理由：${share.reason}` : ''}`);
    });
    sentShares.forEach((share) => {
      const names = (share.sharedToRecipients || []).map((item) => item.fullName || item.userId).filter(Boolean).join('、');
      lines.push(`我已共享给：${names || share.sharedTo.join('、') || '已配置接收人'}${share.reason ? `；推荐理由：${share.reason}` : ''}`);
    });
  }

  if (operatorNote.trim()) {
    lines.push('');
    lines.push('给同事的补充：');
    lines.push(operatorNote.trim());
  }

  return lines.join('\n');
}

function buildTopicTaskDescription(candidate: TopicCandidate, radarTitle: string, draftDesc: string) {
  const lines = [
    draftDesc.trim() || '请结合这条情报判断是否需要继续跟进。',
    '',
    '【情报原文】',
    `情报标题：${candidate.title}`,
    `所属雷达：${radarTitle}`,
    `来源：${candidate.source}`,
    `情报 ID：${candidate.id}`,
    '查看方式：在任务卡片中点击“查看情报原文”，会回到资讯情报站里的这条情报。',
  ];
  if (candidate.sourceUrl) {
    lines.push('');
    lines.push('【外部来源】');
    lines.push(`信息源链接：${candidate.sourceUrl}`);
  } else {
    lines.push('');
    lines.push('【外部来源】');
    lines.push('当前情报没有可打开的外部信息源链接。');
  }
  return lines.join('\n');
}

function buildTopicTaskAutoShareReason(candidate: TopicCandidate) {
  return `因情报「${candidate.title}」已转成任务，系统自动共享给负责人/协作者，便于查看情报原文。`;
}

function topicShareRecipientFromAssignee(assignee: MentionCandidate): TopicShareRecipient {
  return {
    userId: assignee.id,
    fullName: assignee.fullName,
    email: assignee.email || null,
  };
}

function topicShareRecipientFromOwner(ownerId: string | null, ownerName: string): TopicShareRecipient | null {
  const normalizedOwnerId = ownerId?.trim();
  const normalizedOwnerName = ownerName.trim();
  if (!normalizedOwnerId && !normalizedOwnerName) return null;
  return {
    userId: normalizedOwnerId || normalizedOwnerName,
    fullName: normalizedOwnerName || normalizedOwnerId || '未命名成员',
    email: null,
  };
}

function mergeTopicShareRecipients(recipients: Array<TopicShareRecipient | null | undefined>) {
  const seen = new Set<string>();
  const merged: TopicShareRecipient[] = [];
  recipients.forEach((recipient) => {
    if (!recipient) return;
    const userId = recipient.userId.trim();
    const key = normalizeTopicIdentity(userId || recipient.email || recipient.fullName);
    if (!key || seen.has(key)) return;
    seen.add(key);
    merged.push({
      userId: userId || recipient.fullName,
      fullName: recipient.fullName || userId || recipient.email || '未命名成员',
      email: recipient.email || null,
    });
  });
  return merged;
}

function filterOutCurrentViewerRecipients(recipients: TopicShareRecipient[], currentViewerId: string, currentSessionUser: SessionUser | null, currentOperatorName: string) {
  const viewerAliases = new Set(
    [currentViewerId, currentSessionUser?.id, currentSessionUser?.email, currentSessionUser?.fullName, currentOperatorName]
      .map((item) => normalizeTopicIdentity(item))
      .filter(Boolean),
  );
  return recipients.filter((recipient) => {
    const aliases = [recipient.userId, recipient.email || '', recipient.fullName]
      .map((item) => normalizeTopicIdentity(item))
      .filter(Boolean);
    return !aliases.some((alias) => viewerAliases.has(alias));
  });
}

function elapsedSeconds(startedAt: number | null, now: number) {
  if (!startedAt) return 0;
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

function captureProgressText(seconds: number) {
  if (seconds < 4) return '正在读取雷达配置和优先来源。';
  if (seconds < 14) return '正在访问 RSSHub、优先网址和公开搜索来源。';
  if (seconds < 28) return '正在解析、翻译、去重，并判断是否能入库为新情报。';
  return '仍在等待外部来源或搜索返回；已有情报不会被清空。';
}

function insightProgressText(seconds: number) {
  if (seconds < 6) return '正在读取原文、附件解析结果和关联画像。';
  if (seconds < 22) return '正在调用已配置的 AI 生成深度分析。';
  if (seconds < 42) return '正在整理结果并写入缓存，完成后会自动显示。';
  return '仍在等待 AI 或外部原文返回；你可以先继续浏览，完成后会缓存。';
}

function latestFetchStatusNote(fetch?: TopicRadar['lastFetch'] | null) {
  const statusLog = fetch?.statusLog || [];
  for (let index = statusLog.length - 1; index >= 0; index -= 1) {
    const note = statusLog[index]?.note?.trim();
    if (note) return note;
  }
  return '';
}

function captureResultMessage(result: { fetchedCount: number; createdCount: number; skippedCount: number; parseFailedCount?: number; sourceFailedCount?: number }) {
  const fetched = result.fetchedCount || 0;
  const created = result.createdCount || 0;
  const skipped = result.skippedCount || 0;
  const parseFailed = result.parseFailedCount || 0;
  const sourceFailed = result.sourceFailedCount || 0;
  if (created > 0) {
    return `试跑完成：抓到 ${fetched} 条线索，新增 ${created} 篇情报。`;
  }
  if (fetched > 0) {
    const details = [`重复 ${skipped} 条`];
    if (parseFailed > 0) details.push(`解析失败 ${parseFailed} 条`);
    if (sourceFailed > 0) details.push(`来源失败 ${sourceFailed} 个`);
    return `试跑完成：抓到 ${fetched} 条线索，但没有新增情报（${details.join('，')}）。`;
  }
  if (sourceFailed > 0) {
    return `试跑完成：外部来源没有返回可用线索，且有 ${sourceFailed} 个来源访问失败。请检查优先来源、RSSHub/EasySpider/TrendRadar 配置。`;
  }
  return '试跑完成：没有抓到新的候选线索。AI 会负责筛选和分析，但不会凭空生成外部资讯；请检查雷达关键词、时间窗和优先来源。';
}

function candidateSortTime(candidate: TopicCandidate) {
  return new Date(candidate.publishedAt || candidate.createdAt).getTime();
}

function candidateMatchesBadgeFilter(candidate: TopicCandidate, filter: TopicBadgeFilter) {
  if (filter === 'all') return true;
  if (filter === 'none') return !candidate.primaryBadge;
  return candidate.primaryBadge === filter;
}

function normalizeTagDraft(value: string) {
  return value.trim().replace(/\s+/g, ' ');
}

function normalizeTopicIdentity(value?: string | null) {
  return (value || '').trim().toLowerCase();
}

function topicViewerAliases(user: SessionUser | null) {
  const aliases = new Set<string>();
  [user?.id, user?.email, user?.fullName].forEach((value) => {
    const normalized = normalizeTopicIdentity(value);
    if (normalized) aliases.add(normalized);
  });
  if (user?.id === 'local-device-user' || user?.email === 'local@device.yiyu') {
    aliases.add('local_user');
    aliases.add('local-device-user');
  }
  return aliases;
}

function isLocalTopicViewer(user: SessionUser | null) {
  return !user || user.id === 'local-device-user' || user.organizationId === 'local-device' || user.email === 'local@device.yiyu';
}

function topicRadarBelongsToViewer(radar: TopicRadar, viewerAliases: Set<string>, localViewer: boolean) {
  const createdBy = normalizeTopicIdentity(radar.createdBy || '');
  if (!createdBy) return localViewer;
  return viewerAliases.has(createdBy);
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
  focusCandidateId,
  onFocusCandidateHandled,
  flash,
  onTopicsReload,
  onTasksReload,
}: TopicsManagementViewProps) {
  const currentViewerId = currentSessionUser?.id || 'local-device-user';
  const [selectedRadarId, setSelectedRadarId] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [activeDirection, setActiveDirection] = useState<TopicIntelligenceDirection>('policy_environment');
  const [badgeFilter, setBadgeFilter] = useState<TopicBadgeFilter>('all');
  const [mainPage, setMainPage] = useState(1);
  const [statusModalView, setStatusModalView] = useState<TopicStatusView | null>(null);
  const [statusModalPage, setStatusModalPage] = useState(1);
  const [expandedCandidateId, setExpandedCandidateId] = useState('');
  const [tagDraft, setTagDraft] = useState('');
  const [localState, setLocalState] = useState<TopicLocalState>(() => readTopicLocalState(currentViewerId));
  const [sharedReadAtByViewer, setSharedReadAtByViewer] = useState<Record<string, string>>(() => readSharedReadAtState());
  const [editingPrefIndex, setEditingPrefIndex] = useState<number | null>(null);
  const [radarModalMode, setRadarModalMode] = useState<TopicRadarModalMode>('create');
  const [tempPref, setTempPref] = useState<TopicRadarDraft | null>(null);
  const [preferredSourceDraft, setPreferredSourceDraft] = useState('');
  const [contextRefDraft, setContextRefDraft] = useState('');
  const [contextRefType, setContextRefType] = useState<TopicContextDraftType>('custom_focus');
  const [radarShareOptions, setRadarShareOptions] = useState<MentionCandidate[]>([]);
  const [isLoadingRadarShareOptions, setIsLoadingRadarShareOptions] = useState(false);
  const [isAssistingRadar, setIsAssistingRadar] = useState(false);
  const [isGeneratingSourceLabel, setIsGeneratingSourceLabel] = useState(false);
  const [isSavingRadarConfig, setIsSavingRadarConfig] = useState(false);
  const [radarTogglePendingId, setRadarTogglePendingId] = useState<string | null>(null);
  const [radarDeletePendingId, setRadarDeletePendingId] = useState<string | null>(null);
  const [radarModalNotice, setRadarModalNotice] = useState<string | null>(null);
  const [captureTestingRadarId, setCaptureTestingRadarId] = useState<string | null>(null);
  const [captureTestingStartedAt, setCaptureTestingStartedAt] = useState<number | null>(null);
  const [globalMessage, setGlobalMessage] = useState<string | null>(null);
  const [shareCandidateId, setShareCandidateId] = useState<string | null>(null);
  const [shareReason, setShareReason] = useState('');
  const [shareModalNotice, setShareModalNotice] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [favoriteOverrides, setFavoriteOverrides] = useState<Record<string, boolean>>({});
  const [favoritePendingIds, setFavoritePendingIds] = useState<Set<string>>(() => new Set());
  const [insightCache, setInsightCache] = useState<Record<string, TopicCandidateInsight>>({});
  const [insightLoadingId, setInsightLoadingId] = useState<string | null>(null);
  const [insightLoadingStartedAt, setInsightLoadingStartedAt] = useState<number | null>(null);
  const [topicUiTick, setTopicUiTick] = useState(() => Date.now());
  const [chatByCandidateId, setChatByCandidateId] = useState<Record<string, TopicCandidateChatMessage[]>>({});
  const [chatDraftByCandidateId, setChatDraftByCandidateId] = useState<Record<string, string>>({});
  const [chatLoadingCandidateId, setChatLoadingCandidateId] = useState<string | null>(null);
  const [taskModalCandidateId, setTaskModalCandidateId] = useState<string | null>(null);
  const [taskDraft, setTaskDraft] = useState<TopicQuickTaskDraft | null>(null);
  const [taskAssignees, setTaskAssignees] = useState<MentionCandidate[]>([]);
  const [taskModalNotice, setTaskModalNotice] = useState<TopicTaskModalNotice | null>(null);
  const [createdTopicTaskId, setCreatedTopicTaskId] = useState<string | null>(null);
  const [isPreparingTaskModal, setIsPreparingTaskModal] = useState(false);
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);

  const defaultListId = effectiveTaskSettings.defaultListId || activeTaskLists[0]?.id || 'list-0';
  const radarMap = useMemo(() => new Map(radars.map((item) => [item.id, item])), [radars]);
  const viewerAliases = useMemo(() => topicViewerAliases(currentSessionUser), [
    currentSessionUser?.email,
    currentSessionUser?.fullName,
    currentSessionUser?.id,
  ]);
  const localViewer = isLocalTopicViewer(currentSessionUser);
  const viewerRadars = useMemo(
    () => radars.filter((radar) => topicRadarBelongsToViewer(radar, viewerAliases, localViewer)),
    [localViewer, radars, viewerAliases],
  );
  const viewerRadarIds = useMemo(() => new Set(viewerRadars.map((radar) => radar.id)), [viewerRadars]);
  const mainCandidates = useMemo(
    () => candidates.filter((candidate) => viewerRadarIds.has(candidate.radarId)),
    [candidates, viewerRadarIds],
  );
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
    const visible = [...viewerRadars].map((item) => ({
      id: item.id,
      title: item.title,
      prompt: item.prompt,
      timeRange: item.timeRange,
      preferredSources: item.preferredSources || [],
      contextRefs: item.contextRefs || [],
      shareRecipients: item.shareRecipients || [],
      priorityUrls: item.priorityUrls || (item.preferredSources || []).map((source) => source.url),
      status: item.status || (item.fetchEnabled ? 'running' : 'paused'),
      fetchEnabled: Boolean(item.fetchEnabled),
      pushFrequency: item.pushFrequency || 'manual',
      pushTime: item.pushTime || '09:00',
      pushWeekday: item.pushWeekday || null,
      candidateCount: candidates.filter((candidate) => candidate.radarId === item.id).length,
      nextPushAt: item.nextPushAt || null,
      lastAutoFetchAt: item.lastAutoFetchAt || null,
      lastPushedAt: item.lastPushedAt || null,
      lastFetch: item.lastFetch || null,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt || item.createdAt,
    }));
    visible.push({
      id: 'placeholder-new',
      title: '',
      prompt: '',
      timeRange: topicsSettingsState.defaultTimeRange,
      preferredSources: [],
      contextRefs: [],
      shareRecipients: [],
      priorityUrls: [],
      status: 'trial',
      fetchEnabled: false,
      pushFrequency: 'manual' as TopicRadarPushFrequency,
      pushTime: '09:00',
      pushWeekday: currentIsoWeekday(),
      candidateCount: 0,
      nextPushAt: null,
      lastAutoFetchAt: null,
      lastPushedAt: null,
      lastFetch: null,
      createdAt: '',
      updatedAt: '',
    });
    return visible;
  }, [candidates, topicsSettingsState.defaultTimeRange, viewerRadars]);

  const preferenceOf = (candidateId: string) => localState.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
  const setFavoriteOverride = (candidateId: string, value: boolean | null) => {
    setFavoriteOverrides((prev) => {
      const next = { ...prev };
      if (value === null) {
        delete next[candidateId];
      } else {
        next[candidateId] = value;
      }
      return next;
    });
  };
  const setFavoritePending = (candidateId: string, pending: boolean) => {
    setFavoritePendingIds((prev) => {
      const next = new Set(prev);
      if (pending) {
        next.add(candidateId);
      } else {
        next.delete(candidateId);
      }
      return next;
    });
  };
  const isSavedCandidate = (candidate: TopicCandidate, preference = preferenceOf(candidate.id)) => {
    const override = favoriteOverrides[candidate.id];
    if (typeof override === 'boolean') return override;
    return Boolean(candidate.viewerFavorite || preference.saved);
  };
  const isCandidateTaskLinked = (candidate: TopicCandidate) =>
    Boolean(candidate.convertedTaskId || (relatedTasksByCandidate.get(candidate.id) || []).length > 0);
  const updateLocalPreference = (candidateId: string, patch: Partial<TopicCandidateLocalPreference>) => {
    setLocalState((prev) => {
      const current = prev.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
      const nextPreference = normalizePreference({
        ...current,
        ...patch,
      });
      const shouldRemove =
        !nextPreference.saved &&
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
      writeTopicLocalState(next, currentViewerId);
      return next;
    });
  };

  const viewCounts = useMemo(() => {
    const counts = {
      favorite: 0,
      shared: 0,
      sent: 0,
      task_linked: 0,
    };
    candidates.forEach((candidate) => {
      const preference = preferenceOf(candidate.id);
      const saved = isSavedCandidate(candidate, preference);
      if (saved) counts.favorite += 1;
      if (candidate.viewerSharedToMe) counts.shared += 1;
      if (candidate.viewerSharedByMe) counts.sent += 1;
      if (viewerRadarIds.has(candidate.radarId) && isCandidateTaskLinked(candidate)) counts.task_linked += 1;
    });
    return counts;
  }, [candidates, favoriteOverrides, localState, relatedTasksByCandidate, viewerRadarIds]);
  const sharedInboxReadAt = sharedReadAtByViewer[currentViewerId] || '';
  const sharedInboxUnreadCount = useMemo(() => {
    const readAtTime = shareRecordTime(sharedInboxReadAt);
    return candidates.filter((candidate) => (
      Boolean(candidate.viewerSharedToMe) && latestReceivedShareTime(candidate) > readAtTime
    )).length;
  }, [candidates, sharedInboxReadAt]);

  const filteredCandidates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return mainCandidates
      .filter((candidate) => {
        const preference = preferenceOf(candidate.id);
        const customTags = [...(preference.tags || []), ...(candidate.favoriteTags || [])];

        if ((candidate.primaryDirection || 'industry_trend_case') !== activeDirection) return false;
        if (selectedRadarId !== 'all' && candidate.radarId !== selectedRadarId) return false;
        if (!candidateMatchesBadgeFilter(candidate, badgeFilter)) return false;
        if (!query) return true;

        const radarTitle = radarMap.get(candidate.radarId)?.title || '';
        const insight = insightCache[candidate.id];
        const corpus = [
          candidate.title,
          candidate.summary,
          candidate.source,
          radarTitle,
          candidate.relevanceReason || '',
          candidate.suggestedAction || '',
          candidate.favoriteNote || '',
          preference.note || '',
          ...customTags,
          insight?.overview || '',
          ...(insight?.keyPoints || []),
          ...(insight?.recommendationReasons || []),
          ...(insight?.practicalUses || []),
          ...(insight?.discussionPrompts || []),
          insight?.editorialNote || '',
        ]
          .join(' ')
          .toLowerCase();
        return corpus.includes(query);
      })
      .sort((left, right) => candidateSortTime(right) - candidateSortTime(left));
  }, [activeDirection, badgeFilter, insightCache, localState, mainCandidates, radarMap, searchQuery, selectedRadarId]);
  const currentMainPage = clampTopicPage(mainPage, filteredCandidates.length);
  const pagedFilteredCandidates = useMemo(() => {
    const start = (currentMainPage - 1) * TOPIC_PAGE_SIZE;
    return filteredCandidates.slice(start, start + TOPIC_PAGE_SIZE);
  }, [currentMainPage, filteredCandidates]);

  const selectedCandidate = useMemo(
    () => filteredCandidates.find((candidate) => candidate.id === selectedCandidateId) || filteredCandidates[0] || null,
    [filteredCandidates, selectedCandidateId],
  );
  const expandedCandidate = useMemo(
    () => candidates.find((candidate) => candidate.id === expandedCandidateId) || null,
    [candidates, expandedCandidateId],
  );
  const shareCandidate = useMemo(
    () => candidates.find((candidate) => candidate.id === shareCandidateId) || null,
    [candidates, shareCandidateId],
  );
  useEffect(() => {
    setLocalState(readTopicLocalState(currentViewerId));
    setFavoriteOverrides({});
    setFavoritePendingIds(new Set());
    setSelectedCandidateId('');
    setExpandedCandidateId('');
    setStatusModalView(null);
    setMainPage(1);
    setStatusModalPage(1);
  }, [currentViewerId]);

  useEffect(() => {
    setMainPage(1);
    setExpandedCandidateId('');
  }, [activeDirection, badgeFilter, searchQuery, selectedRadarId]);

  useEffect(() => {
    setMainPage((page) => clampTopicPage(page, filteredCandidates.length));
  }, [filteredCandidates.length]);

  useEffect(() => {
    if (selectedRadarId !== 'all' && !viewerRadarIds.has(selectedRadarId)) {
      setSelectedRadarId('all');
      return;
    }
    if (!filteredCandidates.length) {
      if (selectedCandidateId) setSelectedCandidateId('');
      if (!statusModalView && expandedCandidateId) setExpandedCandidateId('');
      return;
    }
    if (!filteredCandidates.some((candidate) => candidate.id === selectedCandidateId)) {
      setSelectedCandidateId(filteredCandidates[0].id);
    }
    if (!statusModalView && expandedCandidateId && !filteredCandidates.some((candidate) => candidate.id === expandedCandidateId)) {
      setExpandedCandidateId('');
    }
  }, [expandedCandidateId, filteredCandidates, selectedCandidateId, selectedRadarId, statusModalView, viewerRadarIds]);

  useEffect(() => {
    setTagDraft('');
  }, [selectedCandidateId]);

  useEffect(() => {
    if (!expandedCandidate) return;
    if (insightCache[expandedCandidate.id]) return;
    let active = true;
    setInsightLoadingId(expandedCandidate.id);
    setInsightLoadingStartedAt(Date.now());
    void getCandidateInsights(expandedCandidate.id)
      .then((insight) => {
        if (!active) return;
        setInsightCache((prev) => ({ ...prev, [expandedCandidate.id]: insight }));
        void onTopicsReload();
      })
      .catch((error) => {
        if (!active) return;
        flash('error', error instanceof Error ? error.message : '情报详情加载失败');
      })
      .finally(() => {
        if (!active) return;
        setInsightLoadingId((current) => (current === expandedCandidate.id ? null : current));
        setInsightLoadingStartedAt((current) => (current ? null : current));
      });
    return () => {
      active = false;
    };
  }, [expandedCandidate, flash, insightCache, onTopicsReload]);

  useEffect(() => {
    if (!captureTestingRadarId && !insightLoadingId) return;
    setTopicUiTick(Date.now());
    const timer = window.setInterval(() => setTopicUiTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [captureTestingRadarId, insightLoadingId]);

  const showMessage = (message: string, duration = 3200) => {
    setGlobalMessage(message);
    window.setTimeout(() => {
      setGlobalMessage((current) => (current === message ? null : current));
    }, duration);
  };

  const markSharedInboxRead = () => {
    const readAt = new Date().toISOString();
    setSharedReadAtByViewer((prev) => {
      const next = { ...prev, [currentViewerId]: readAt };
      writeSharedReadAtState(next);
      return next;
    });
  };

  const openStatusModal = (view: TopicStatusView) => {
    if (view === 'shared') {
      markSharedInboxRead();
    }
    setStatusModalView(view);
    setStatusModalPage(1);
    setExpandedCandidateId('');
  };

  useEffect(() => {
    if (!focusCandidateId) return;
    const candidate = candidates.find((item) => item.id === focusCandidateId);
    if (!candidate) {
      flash('info', '这条情报暂时没有在当前账号的资讯情报站里找到。');
      onFocusCandidateHandled?.();
      return;
    }
    setSelectedCandidateId(candidate.id);
    setExpandedCandidateId(candidate.id);
    setStatusModalPage(1);
    if (viewerRadarIds.has(candidate.radarId)) {
      setStatusModalView(null);
      setActiveDirection(candidate.primaryDirection || 'industry_trend_case');
      setSelectedRadarId('all');
      setMainPage(1);
    } else if (candidate.viewerSharedToMe) {
      markSharedInboxRead();
      setStatusModalView('shared');
    } else {
      setStatusModalView(null);
      flash('info', '这条情报不属于当前账号的雷达，也还没有共享给当前账号。');
    }
    onFocusCandidateHandled?.();
  }, [candidates, flash, focusCandidateId, onFocusCandidateHandled, viewerRadarIds]);

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

  const ensureRadarShareOptions = async () => {
    if (radarShareOptions.length || isLoadingRadarShareOptions) return;
    setIsLoadingRadarShareOptions(true);
    try {
      const items = await getMentionCandidates('');
      setRadarShareOptions(ensureTaskAssignees(items));
    } catch {
      if (currentSessionUser) {
        setRadarShareOptions([
          {
            id: currentSessionUser.id,
            fullName: currentSessionUser.fullName,
            email: currentSessionUser.email,
            primaryRole: currentSessionUser.primaryRole,
            isSelf: true,
          },
        ]);
      }
    } finally {
      setIsLoadingRadarShareOptions(false);
    }
  };

  const organizationContextRef = (): TopicContextRef => ({
    type: 'organization_dna',
    id: currentSessionUser?.organizationId || 'local_org',
    label: '本组织 DNA',
    role: 'canonical_context',
  });

  const contextTypeLabel = (type: string) =>
    TOPIC_CONTEXT_TYPE_OPTIONS.find((option) => option.id === type)?.label || (type === 'organization_dna' ? '组织画像' : '关注对象');

  const buildContextRef = (type: TopicContextDraftType, label: string): TopicContextRef => {
    const normalizedLabel = label.trim().replace(/\s+/g, ' ');
    return {
      type,
      id: `${type}:${normalizedLabel}`,
      label: normalizedLabel,
      role: type === 'custom_focus' ? 'custom_focus' : 'target_filter',
    };
  };

  const buildRadarDraftFromRadar = (radar?: TopicRadar | null): TopicRadarDraft => ({
    id: radar?.id || 'placeholder-new',
    title: radar?.title || '',
    prompt: radar?.prompt || '',
    timeRange: radar?.timeRange || topicsSettingsState.defaultTimeRange,
    preferredSources: radar?.preferredSources || [],
    contextRefs: radar?.contextRefs?.length ? radar.contextRefs : [organizationContextRef()],
    shareRecipients: radar?.shareRecipients || [],
    priorityUrls: radar?.priorityUrls || (radar?.preferredSources || []).map((source) => source.url),
    fetchEnabled: radar ? Boolean(radar.fetchEnabled) : true,
    pushFrequency: radar?.pushFrequency || 'daily',
    pushTime: radar?.pushTime || '09:00',
    pushWeekday: radar?.pushWeekday || currentIsoWeekday(),
  });

  const openRadarConfig = (radar?: TopicRadar | null, index = 0, mode: TopicRadarModalMode = 'manage') => {
    setRadarModalMode(mode);
    setEditingPrefIndex(index);
    setPreferredSourceDraft('');
    setContextRefDraft('');
    setContextRefType('custom_focus');
    setRadarModalNotice(null);
    setTempPref(buildRadarDraftFromRadar(radar));
    void ensureRadarShareOptions();
  };

  const openNewRadarConfig = () => {
    openRadarConfig(null, radarCards.findIndex((item) => item.id === 'placeholder-new'), 'create');
  };

  const openRadarManager = () => {
    const firstRadar = viewerRadars[0] || null;
    openRadarConfig(firstRadar, 0, 'manage');
  };

  const closeRadarConfig = () => {
    if (isSavingRadarConfig) return;
    setEditingPrefIndex(null);
    setRadarModalMode('create');
    setTempPref(null);
    setPreferredSourceDraft('');
    setContextRefDraft('');
    setContextRefType('custom_focus');
    setRadarModalNotice(null);
  };

  const hasContextRef = (refs: TopicContextRef[], type: string, id: string) =>
    refs.some((item) => item.type === type && item.id === id);

  const toggleOrganizationDnaRef = () => {
    const orgRef = organizationContextRef();
    setTempPref((prev) => {
      if (!prev) return prev;
      if (hasContextRef(prev.contextRefs, orgRef.type, orgRef.id)) {
        return { ...prev, contextRefs: prev.contextRefs.filter((item) => !(item.type === orgRef.type && item.id === orgRef.id)) };
      }
      return { ...prev, contextRefs: [orgRef, ...prev.contextRefs] };
    });
  };

  const addCustomContextRef = () => {
    const label = contextRefDraft.trim().replace(/\s+/g, ' ');
    if (!label || !tempPref) return;
    const nextRef = buildContextRef(contextRefType, label);
    if (hasContextRef(tempPref.contextRefs, nextRef.type, nextRef.id)) {
      setContextRefDraft('');
      return;
    }
    setTempPref({
      ...tempPref,
      contextRefs: [...tempPref.contextRefs, nextRef],
    });
    setContextRefDraft('');
  };

  const togglePresetContextRef = (type: TopicContextDraftType, label: string) => {
    const nextRef = buildContextRef(type, label);
    setTempPref((prev) => {
      if (!prev) return prev;
      if (hasContextRef(prev.contextRefs, nextRef.type, nextRef.id)) {
        return { ...prev, contextRefs: prev.contextRefs.filter((item) => !(item.type === nextRef.type && item.id === nextRef.id)) };
      }
      return { ...prev, contextRefs: [...prev.contextRefs, nextRef] };
    });
  };

  const removeContextRef = (ref: TopicContextRef) => {
    setTempPref((prev) => (
      prev
        ? { ...prev, contextRefs: prev.contextRefs.filter((item) => !(item.type === ref.type && item.id === ref.id)) }
        : prev
    ));
  };

  const toggleShareRecipient = (candidate: MentionCandidate) => {
    setTempPref((prev) => {
      if (!prev) return prev;
      if (prev.shareRecipients.some((item) => item.userId === candidate.id)) {
        return { ...prev, shareRecipients: prev.shareRecipients.filter((item) => item.userId !== candidate.id) };
      }
      return {
        ...prev,
        shareRecipients: [
          ...prev.shareRecipients,
          { userId: candidate.id, fullName: candidate.fullName, email: candidate.email || null },
        ],
      };
    });
  };

  const directionCounts = useMemo(() => {
    const counts = new Map<TopicIntelligenceDirection, number>();
    TOPIC_DIRECTIONS.forEach((direction) => counts.set(direction.id, 0));
    mainCandidates.forEach((candidate) => {
      const direction = candidate.primaryDirection || 'industry_trend_case';
      counts.set(direction, (counts.get(direction) || 0) + 1);
    });
    return counts;
  }, [mainCandidates]);
  const badgeFilterCounts = useMemo(() => {
    const counts: Record<TopicBadgeFilter, number> = {
      all: 0,
      follow_up: 0,
      focus: 0,
      none: 0,
    };
    mainCandidates.forEach((candidate) => {
      if ((candidate.primaryDirection || 'industry_trend_case') !== activeDirection) return;
      if (selectedRadarId !== 'all' && candidate.radarId !== selectedRadarId) return;
      counts.all += 1;
      if (candidate.primaryBadge === 'follow_up') {
        counts.follow_up += 1;
      } else if (candidate.primaryBadge === 'focus') {
        counts.focus += 1;
      } else {
        counts.none += 1;
      }
    });
    return counts;
  }, [activeDirection, mainCandidates, selectedRadarId]);

  const statusViewOptions: Array<{ id: TopicStatusView; label: string; count: number; icon: React.ReactNode }> = [
    { id: 'shared', label: '共享给我', count: viewCounts.shared, icon: <Share2 size={14} /> },
    { id: 'sent', label: '我的共享', count: viewCounts.sent, icon: <Send size={14} /> },
    { id: 'favorite', label: '我的收藏', count: viewCounts.favorite, icon: <Bookmark size={14} /> },
    { id: 'task_linked', label: '已转任务', count: viewCounts.task_linked, icon: <CheckSquare size={14} /> },
  ];
  const activeStatusLabel = statusViewOptions.find((option) => option.id === statusModalView)?.label || '';
  const activeStatusCopy = statusModalView ? TOPIC_STATUS_VIEW_COPY[statusModalView] : null;
  const statusModalCandidates = useMemo(() => {
    if (!statusModalView) return [];
    return candidates
      .filter((candidate) => {
        const preference = preferenceOf(candidate.id);
        if (statusModalView === 'favorite') return isSavedCandidate(candidate, preference);
        if (statusModalView === 'shared') return Boolean(candidate.viewerSharedToMe);
        if (statusModalView === 'sent') return Boolean(candidate.viewerSharedByMe);
        return viewerRadarIds.has(candidate.radarId) && isCandidateTaskLinked(candidate);
      })
      .sort((left, right) => {
        if (statusModalView === 'shared') return latestReceivedShareTime(right) - latestReceivedShareTime(left);
        if (statusModalView === 'sent') return latestSentShareTime(right) - latestSentShareTime(left);
        return candidateSortTime(right) - candidateSortTime(left);
      });
  }, [candidates, favoriteOverrides, localState, relatedTasksByCandidate, statusModalView, viewerRadarIds]);
  const currentStatusModalPage = clampTopicPage(statusModalPage, statusModalCandidates.length);
  const pagedStatusModalCandidates = useMemo(() => {
    const start = (currentStatusModalPage - 1) * TOPIC_PAGE_SIZE;
    return statusModalCandidates.slice(start, start + TOPIC_PAGE_SIZE);
  }, [currentStatusModalPage, statusModalCandidates]);
  useEffect(() => {
    setStatusModalPage((page) => clampTopicPage(page, statusModalCandidates.length));
  }, [statusModalCandidates.length]);
  const processingCandidates = useMemo(
    () => mainCandidates.filter((candidate) => (
      candidate.insightStatus === 'pending' &&
      (!candidate.relevanceReason?.trim() || !candidate.suggestedAction?.trim())
    )),
    [mainCandidates],
  );
  const processingRadarTitles = useMemo(() => {
    const titles = new Set<string>();
    processingCandidates.forEach((candidate) => {
      titles.add(radarMap.get(candidate.radarId)?.title || '未命名雷达');
    });
    return Array.from(titles);
  }, [processingCandidates, radarMap]);
  const captureTestingRadarTitle = captureTestingRadarId ? radarMap.get(captureTestingRadarId)?.title || '当前雷达' : '';

  const mainBadgeForCandidate = (candidate: TopicCandidate) => {
    if (candidate.primaryBadge === 'follow_up') return '待跟进';
    if (candidate.primaryBadge === 'focus') return '重点';
    return null;
  };

  const sourceStatusTextForCandidate = (candidate: TopicCandidate) => {
    if (candidate.sourceStatus === 'unreachable') return '来源访问失败';
    if (candidate.sourceStatus === 'needs_review') return '来源需复核';
    if (candidate.hasAttachments && candidate.attachmentParseStatus === 'pending') return '附件解析中';
    if (candidate.hasAttachments && candidate.attachmentParseStatus === 'failed') return '附件解析失败';
    if (candidate.hasAttachments && candidate.attachmentParseStatus === 'parsed') return '附件已解析';
    return '';
  };

  const relevanceReasonForCandidate = (candidate: TopicCandidate, radarTitle: string, insight?: TopicCandidateInsight | null) => {
    const explicit = candidate.relevanceReason?.trim();
    if (explicit) return explicit;
    const reason = insight?.recommendationReasons?.find((item) => item.trim());
    if (reason) return reason;
    return `这篇内容当前被归入「${radarTitle}」雷达，建议先结合该主题判断是否值得继续跟进。`;
  };

  const suggestedActionForCandidate = (candidate: TopicCandidate) => {
    const explicit = candidate.suggestedAction?.trim();
    if (explicit) return explicit;
    if (candidate.primaryBadge === 'follow_up') return '建议转成任务或共享给相关同事，确认是否需要推进。';
    if (candidate.primaryBadge === 'focus') return '建议先收藏，后续复盘或选题讨论时重点查看。';
    return '可先打开原文确认价值，必要时收藏、共享或转成任务。';
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
          priorityUrls: prev.priorityUrls.includes(suggested.url) ? prev.priorityUrls : [...prev.priorityUrls, suggested.url],
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
    setTempPref((prev) => (prev ? { ...prev, preferredSources: prev.preferredSources.filter((item) => item.url !== url), priorityUrls: prev.priorityUrls.filter((item) => item !== url) } : prev));
  };

  const buildRadarPayloadFromDraft = (draft: TopicRadarDraft, overrides: Partial<TopicRadarDraft> = {}): TopicRadarPayload => {
    const source = { ...draft, ...overrides };
    const title = source.title.trim() || '自定义追踪项';
    const isExistingRadar = !source.id.startsWith('placeholder-');
    return {
      title,
      prompt: source.prompt.trim(),
      timeRange: source.timeRange,
      preferredSources: source.preferredSources,
      orgId: currentSessionUser?.organizationId || 'local_org',
      label: title,
      status: source.fetchEnabled ? (isExistingRadar ? 'running' : 'trial') : 'paused',
      contextRefs: source.contextRefs,
      shareRecipients: source.shareRecipients,
      priorityUrls: source.priorityUrls.length ? source.priorityUrls : source.preferredSources.map((item) => item.url),
      fetchEnabled: source.fetchEnabled,
      pushFrequency: source.pushFrequency,
      pushTime: source.pushTime || null,
      pushWeekday: source.pushFrequency === 'weekly' ? (source.pushWeekday || currentIsoWeekday()) : null,
      createdBy: currentViewerId,
    };
  };

  const handleSavePrefEdit = async () => {
    if (!tempPref) return;
    if (!tempPref.prompt.trim()) {
      setRadarModalNotice('请先填写“想持续追踪什么”，这样 AI 才知道这个雷达要长期关注什么。');
      return;
    }
    setIsSavingRadarConfig(true);
    setRadarModalNotice(null);
    try {
      const payload = buildRadarPayloadFromDraft(tempPref);
      const isExistingRadar = !tempPref.id.startsWith('placeholder-');
      let savedRadar: TopicRadar;
      if (isExistingRadar) {
        savedRadar = await updateRadar(tempPref.id, payload);
      } else {
        savedRadar = await createRadar(payload);
      }
      await onTopicsReload();
      closeRadarConfig();
      showMessage(`${isExistingRadar ? '雷达规则已更新' : '已新增雷达规则'}，共享者 ${savedRadar.shareRecipients?.length || 0} 人`);
    } catch (error) {
      setRadarModalNotice(error instanceof Error ? error.message : '保存失败');
    } finally {
      setIsSavingRadarConfig(false);
    }
  };

  const handleToggleRadarFetch = async (radar: TopicRadar) => {
    if (radarTogglePendingId) return;
    const nextEnabled = !radar.fetchEnabled;
    setRadarTogglePendingId(radar.id);
    setRadarModalNotice(null);
    try {
      const draft = buildRadarDraftFromRadar(radar);
      await updateRadar(radar.id, buildRadarPayloadFromDraft(draft, { fetchEnabled: nextEnabled }));
      if (tempPref?.id === radar.id) {
        setTempPref((prev) => (prev?.id === radar.id ? { ...prev, fetchEnabled: nextEnabled } : prev));
      }
      await onTopicsReload();
      showMessage(nextEnabled ? `已启用「${radar.title}」自动抓取` : `已暂停「${radar.title}」自动抓取`);
    } catch (error) {
      setRadarModalNotice(error instanceof Error ? error.message : '雷达启停失败');
    } finally {
      setRadarTogglePendingId(null);
    }
  };

  const handleDeleteRadar = async (radar: TopicRadar) => {
    if (radarDeletePendingId) return;
    const candidateCount = candidates.filter((candidate) => candidate.radarId === radar.id).length;
    const confirmed = window.confirm(
      `确定删除「${radar.title || '未命名雷达'}」吗？\n\n如果只是想调整追踪说明、共享者、推送频率或优先来源，建议点“编辑”修改雷达，通常不需要删除。\n\n继续删除会同时移除该雷达下的 ${candidateCount} 条情报，以及相关收藏、共享和抓取记录；已经转成的任务不会自动删除。`,
    );
    if (!confirmed) return;
    const nextRadar = viewerRadars.find((item) => item.id !== radar.id) || null;
    setRadarDeletePendingId(radar.id);
    setRadarModalNotice(null);
    try {
      await deleteRadar(radar.id);
      if (selectedRadarId === radar.id) {
        setSelectedRadarId('all');
      }
      if (tempPref?.id === radar.id) {
        if (nextRadar) {
          setTempPref(buildRadarDraftFromRadar(nextRadar));
          setRadarModalMode('manage');
        } else {
          closeRadarConfig();
        }
      }
      await onTopicsReload();
      showMessage(`已删除雷达「${radar.title || '未命名雷达'}」`);
    } catch (error) {
      setRadarModalNotice(error instanceof Error ? error.message : '删除雷达失败');
    } finally {
      setRadarDeletePendingId(null);
    }
  };

  const handleCaptureTestRadar = async (radarId: string) => {
    setCaptureTestingRadarId(radarId);
    setCaptureTestingStartedAt(Date.now());
    try {
      const result = await captureIntelligenceRadarTest(radarId);
      await onTopicsReload();
      showMessage(captureResultMessage(result), 7200);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '单雷达试跑失败');
    } finally {
      setCaptureTestingRadarId(null);
      setCaptureTestingStartedAt(null);
    }
  };

  const handleToggleSaved = async (candidate: TopicCandidate) => {
    const current = preferenceOf(candidate.id);
    const currentlySaved = isSavedCandidate(candidate, current);
    const targetSaved = !currentlySaved;
    if (favoritePendingIds.has(candidate.id)) return;
    setFavoriteOverride(candidate.id, targetSaved);
    setFavoritePending(candidate.id, true);
    try {
      if (targetSaved) {
        await favoriteIntelligenceItem(candidate.id, {
          userId: currentViewerId,
          note: current.note || '',
          tags: current.tags || [],
        });
        updateLocalPreference(candidate.id, { saved: true });
        flash('success', '已收藏');
      } else {
        await unfavoriteIntelligenceItem(candidate.id, currentViewerId);
        updateLocalPreference(candidate.id, { saved: false, note: '', tags: [] });
        flash('success', '已取消收藏');
      }
      try {
        await onTopicsReload();
        setFavoriteOverride(candidate.id, null);
      } catch {
        // Keep the optimistic state visible if the refresh fails; the next reload will reconcile it.
      }
    } catch (error) {
      if (targetSaved) {
        updateLocalPreference(candidate.id, { saved: true });
        setFavoriteOverride(candidate.id, true);
        flash('error', error instanceof Error ? `${error.message}，已先保留在本机` : '收藏状态保存失败，已先保留在本机');
      } else {
        setFavoriteOverride(candidate.id, currentlySaved);
        flash('error', error instanceof Error ? error.message : '取消收藏失败');
      }
    } finally {
      setFavoritePending(candidate.id, false);
    }
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

  const closeTopicTaskModal = () => {
    setTaskModalCandidateId(null);
    setTaskDraft(null);
    setTaskAssignees([]);
    setTaskModalNotice(null);
    setCreatedTopicTaskId(null);
    setIsPreparingTaskModal(false);
  };

  const topicTaskOwnerIsSelf = (ownerId: string | null, ownerName: string) => {
    const aliases = new Set(
      [
        currentSessionUser?.id,
        currentSessionUser?.email,
        currentSessionUser?.fullName,
        currentOperatorName,
      ]
        .map((item) => normalizeTopicIdentity(item))
        .filter(Boolean),
    );
    return Boolean((ownerId && aliases.has(normalizeTopicIdentity(ownerId))) || aliases.has(normalizeTopicIdentity(ownerName)));
  };

  const openTaskModal = async (candidate: TopicCandidate) => {
    const existingTasks = relatedTasksByCandidate.get(candidate.id) || [];
    if (candidate.convertedTaskId || existingTasks.length > 0) {
      setSelectedCandidateId(candidate.id);
      setExpandedCandidateId(candidate.id);
      showMessage(`这篇情报已关联 ${Math.max(existingTasks.length, candidate.convertedTaskId ? 1 : 0)} 条任务，已在卡片下方展开。`);
      return;
    }

    const defaultOwnerId = currentSessionUser?.id || '';
    setSelectedCandidateId(candidate.id);
    setTaskModalCandidateId(candidate.id);
    setTaskDraft({
      title: `跟进情报：${candidate.title.trim()}`,
      desc: candidate.suggestedAction?.trim() || `请查看任务备注中的情报来源和分析背景，并结合团队安排决定下一步处理方式。`,
      listId: defaultListId,
      priority: 'normal',
      dueDate: '',
      ddl: '待确认',
      ownerId: defaultOwnerId,
      ownerName: currentSessionUser?.fullName || currentOperatorName,
      collaboratorIds: [],
      note: '',
    });
    setTaskModalNotice(null);
    setCreatedTopicTaskId(null);
    setIsPreparingTaskModal(true);
    try {
      const mentionItems = await getMentionCandidates('').catch(() => []);
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
                collaboratorIds: prev.collaboratorIds.filter((id) => id !== defaultOwner.id),
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
    setTaskModalNotice({ type: 'info', text: '正在创建任务，完成后会在这里显示结果。' });
    try {
      const owner = taskAssignees.find((item) => item.id === taskDraft.ownerId);
      const ownerId = owner?.id || taskDraft.ownerId || null;
      const ownerName = owner?.fullName || taskDraft.ownerName || currentOperatorName;
      const radarTitle = radarMap.get(modalCandidate.radarId)?.title || '未命名雷达';
      const insight = insightCache[modalCandidate.id] || null;
      const note = buildTopicAttachmentNote(modalCandidate, radarTitle, insight, taskDraft.note);
      const desc = buildTopicTaskDescription(modalCandidate, radarTitle, taskDraft.desc);
      const promoted = await promoteCandidateTasks(modalCandidate.id, [
        {
          title: taskDraft.title.trim(),
          desc,
          priority: taskDraft.priority,
          listId: taskDraft.listId,
          dueDate: taskDraft.dueDate || null,
          ddl: taskDraft.ddl.trim() || taskDraft.dueDate || '待确认',
          ownerId,
          ownerName,
          collaboratorIds: taskDraft.collaboratorIds.filter((id) => id && id !== ownerId),
          tagIds: [],
          tags: ['情报跟进'],
          note,
        },
      ]);
      const createdTask = promoted.tasks[0];
      if (createdTask && !createdTask.note) {
        await saveTaskNote(createdTask.id, note);
      }
      const ownerRecipient = topicShareRecipientFromOwner(ownerId, ownerName);
      const collaboratorRecipients = taskDraft.collaboratorIds
        .filter((id) => id && id !== ownerId)
        .map((id) => {
          const assignee = taskAssignees.find((item) => item.id === id);
          return assignee ? topicShareRecipientFromAssignee(assignee) : { userId: id, fullName: id, email: null };
        });
      const autoShareRecipients = filterOutCurrentViewerRecipients(
        mergeTopicShareRecipients([ownerRecipient, ...collaboratorRecipients]),
        currentViewerId,
        currentSessionUser,
        currentOperatorName,
      );
      let autoShareFailed = false;
      if (autoShareRecipients.length > 0) {
        try {
          await shareIntelligenceItem(modalCandidate.id, {
            sharedBy: currentViewerId,
            sharedByName: currentSessionUser?.fullName || currentOperatorName || currentViewerId,
            sharedTo: autoShareRecipients.map((item) => item.userId),
            sharedToRecipients: autoShareRecipients,
            reason: buildTopicTaskAutoShareReason(modalCandidate),
          });
        } catch {
          autoShareFailed = true;
        }
      }
      await onTasksReload();
      await onTopicsReload();
      let successText = topicTaskOwnerIsSelf(ownerId, ownerName)
        ? '已创建任务，负责人是你，已进入任务列表；无需再到协作收件箱确认。'
        : '任务已发出，等待负责人确认；这也算转任务成功，请不要重复点击。';
      if (autoShareRecipients.length > 0 && !autoShareFailed) {
        successText += ` 已自动把情报共享给 ${autoShareRecipients.length} 位负责人/协作者。`;
      } else if (autoShareFailed) {
        successText += ' 但自动共享情报失败，请稍后在情报卡片里手动共享。';
      }
      setCreatedTopicTaskId(createdTask?.id || 'created');
      setTaskModalNotice({ type: 'success', text: successText });
      showMessage(successText, 7200);
      flash('success', successText);
    } catch (error) {
      const message = error instanceof Error ? error.message : '转任务失败';
      setTaskModalNotice({ type: 'error', text: message });
      flash('error', message);
    } finally {
      setIsSubmittingTask(false);
    }
  };

  const openShareModal = (candidate: TopicCandidate) => {
    setShareCandidateId(candidate.id);
    setShareReason('');
    const radar = radarMap.get(candidate.radarId);
    setShareModalNotice(
      radar?.shareRecipients?.length
        ? null
        : '这个雷达还没有配置情报共享者。请先在“管理已有雷达”里为该雷达添加共享者，再回来共享这篇情报。',
    );
  };

  const handleSubmitShare = async () => {
    if (!shareCandidate) return;
    const radar = radarMap.get(shareCandidate.radarId);
    const recipients = radar?.shareRecipients || [];
    if (!recipients.length) {
      setShareModalNotice('这个雷达还没有配置情报共享者，暂时不能共享。');
      return;
    }
    setIsSharing(true);
    try {
      await shareIntelligenceItem(shareCandidate.id, {
        sharedBy: currentViewerId,
        sharedByName: currentSessionUser?.fullName || currentOperatorName || currentViewerId,
        sharedTo: recipients.map((item) => item.userId),
        sharedToRecipients: recipients,
        reason: shareReason.trim(),
      });
      setShareCandidateId(null);
      setShareReason('');
      setShareModalNotice(null);
      await onTopicsReload();
      flash('success', '已共享给雷达配置的接收人');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '共享失败');
    } finally {
      setIsSharing(false);
    }
  };

  const taskModalCandidate = taskModalCandidateId
    ? candidates.find((candidate) => candidate.id === taskModalCandidateId) || null
    : null;
  const shareRadar = shareCandidate ? radarMap.get(shareCandidate.radarId) || null : null;
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
  const toggleTaskCollaborator = (id: string) => {
    setTaskDraft((prev) => {
      if (!prev || !id || id === prev.ownerId) return prev;
      const exists = prev.collaboratorIds.includes(id);
      return {
        ...prev,
        collaboratorIds: exists
          ? prev.collaboratorIds.filter((item) => item !== id)
          : [...prev.collaboratorIds, id],
      };
    });
  };

  const renderExpandedCandidate = (candidate: TopicCandidate, radarTitle: string) => {
    const insight = insightCache[candidate.id] || null;
    const isLoadingInsight = insightLoadingId === candidate.id;
    const chatMessages = chatByCandidateId[candidate.id] || [];
    const chatDraft = chatDraftByCandidateId[candidate.id] || '';
    const relatedTasks = relatedTasksByCandidate.get(candidate.id) || [];
    const deepAnalysis = candidate.deepAnalysis || {};
    const deepText = (key: string, fallback = '') => {
      const value = deepAnalysis[key];
      return typeof value === 'string' && value.trim() ? value.trim() : fallback;
    };
    const suggestedQuestions = Array.isArray(deepAnalysis.suggestedQuestions)
      ? deepAnalysis.suggestedQuestions.map((item) => String(item)).filter(Boolean)
      : insight?.discussionPrompts || [];
    const publicOpinionSample = (
      deepAnalysis.publicOpinionSample && typeof deepAnalysis.publicOpinionSample === 'object'
        ? deepAnalysis.publicOpinionSample as Record<string, unknown>
        : null
    );

    return (
      <div className="space-y-4">
        {isLoadingInsight ? (
          <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-6 text-center text-[13px] text-gray-500">
            <RefreshCw size={18} className="mx-auto mb-2 animate-spin text-[#5B7BFE]" />
            <p className="font-semibold text-gray-700">正在生成深度分析，完成后会自动缓存…</p>
            <p className="mt-1 text-[12px] text-gray-500">
              {insightProgressText(elapsedSeconds(insightLoadingStartedAt, topicUiTick))}
            </p>
          </div>
        ) : insight ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <section className="rounded-lg border border-gray-100 bg-gray-50/70 p-4">
              <p className="text-[12px] font-bold text-gray-900">核心信息拆解</p>
              <p className="mt-2 text-[13px] leading-6 text-gray-700">{deepText('coreInfo', insight.overview || candidate.summary)}</p>
              {insight.keyPoints.length > 0 && (
                <div className="mt-4">
                  <p className="text-[12px] font-bold text-gray-900">核心观点</p>
                  <ul className="mt-2 space-y-2 text-[13px] leading-6 text-gray-700">
                    {insight.keyPoints.map((item, index) => (
                      <li key={`${candidate.id}-key-${index}`}>{index + 1}. {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
            <section className="rounded-lg border border-gray-100 bg-white p-4">
              <p className="text-[12px] font-bold text-gray-900">与关联画像的关系</p>
              <p className="mt-2 text-[13px] leading-6 text-gray-700">
                {deepText('contextRelation', candidate.relevanceReason || insight.recommendationReasons.join('；') || '当前还没有稳定的画像关系判断。')}
              </p>
              <div className="mt-4">
                <p className="text-[12px] font-bold text-gray-900">机会或风险</p>
                <p className="mt-2 text-[13px] leading-6 text-gray-700">{deepText('opportunityOrRisk', insight.editorialNote || '当前还没有稳定判断。')}</p>
              </div>
              {insight.practicalUses.length > 0 && (
                <div className="mt-4">
                  <p className="text-[12px] font-bold text-gray-900">可继续展开</p>
                  <ul className="mt-2 space-y-2 text-[13px] leading-6 text-gray-700">
                    {insight.practicalUses.map((item, index) => (
                      <li key={`${candidate.id}-use-${index}`}>{index + 1}. {item}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-4 rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-[12px] leading-5 text-gray-600">
                <p className="font-bold text-gray-800">来源与可信度提示</p>
                <p className="mt-1">{deepText('sourceCredibility', candidate.sourceUrl ? '建议打开原文核对关键事实、时间和主体。' : '当前没有原文链接，需要人工复核来源。')}</p>
              </div>
            </section>
          </div>
        ) : candidate.insightStatus === 'failed' ? (
          <div className="rounded-lg border border-rose-100 bg-rose-50 px-4 py-3 text-[13px] leading-6 text-rose-700">
            这篇情报深度分析生成失败，可以先打开原文，稍后再次点击深度分析重试。
          </div>
        ) : (
          <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 text-[13px] leading-6 text-gray-500">
            点击“深度分析”后，系统会读取原文、附件解析结果和关联画像生成完整判断；未生成前不影响卡片浏览。
          </div>
        )}

        {publicOpinionSample && (
          <div className="rounded-lg border border-amber-100 bg-amber-50/70 p-4 text-[12px] leading-5 text-amber-900">
            <p className="font-bold text-amber-800">公开来源样本</p>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-4">
              <span>范围：{String(publicOpinionSample.sourceScope || '公开来源样本')}</span>
              <span>时间：{String(publicOpinionSample.timeRange || '未标注')}</span>
              <span>样本：{String(publicOpinionSample.sampleCount ?? 0)} 条</span>
              <span>可信度：{String(publicOpinionSample.trendConfidence || 'low')}</span>
            </div>
            {publicOpinionSample.note ? <p className="mt-2">{String(publicOpinionSample.note)}</p> : null}
          </div>
        )}

        {suggestedQuestions.length ? (
          <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4">
            <p className="text-[12px] font-bold text-indigo-700">可继续追问</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestedQuestions.slice(0, 4).map((prompt) => (
                <button
                  type="button"
                  key={`${candidate.id}-prompt-${prompt}`}
                  onClick={() => void handleAskCandidateQuestion(candidate, prompt)}
                  className="rounded-md border border-indigo-100 bg-white px-3 py-2 text-[12px] font-semibold text-indigo-700 hover:bg-indigo-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {relatedTasks.length > 0 && (
          <div className="rounded-lg border border-violet-100 bg-violet-50/60 p-4">
            <p className="text-[12px] font-bold text-violet-700">已关联任务</p>
            <div className="mt-2 space-y-2 text-[13px] text-violet-900">
              {relatedTasks.slice(0, 3).map((task) => (
                <div key={task.id} className="rounded-md border border-violet-100 bg-white/70 px-3 py-2">
                  <p className="font-semibold">{task.title}</p>
                  <p className="mt-1 text-[12px] text-violet-700">
                    {task.ownerName ? `负责人：${task.ownerName}` : '负责人待确认'}
                    {task.ddl ? ` · 时间：${task.ddl}` : ''}
                    {task.collaborators?.length ? ` · 协作者：${task.collaborators.map((item) => item.fullName).join('、')}` : ''}
                  </p>
                  {task.note ? <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-violet-700">{task.note}</p> : null}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-lg border border-gray-100 bg-white p-4">
          <div className="flex items-center gap-2 text-[12px] font-bold text-gray-900">
            <FileText size={14} className="text-[#5B7BFE]" />
            围绕这篇情报追问
          </div>
          {chatMessages.length > 0 && (
            <div className="mt-3 max-h-[220px] space-y-3 overflow-y-auto rounded-lg bg-gray-50 p-3">
              {chatMessages.map((message, index) => (
                <div key={`${candidate.id}-chat-${index}`} className={`text-[13px] leading-6 ${message.role === 'user' ? 'text-gray-900' : 'text-gray-600'}`}>
                  <span className="font-bold">{message.role === 'user' ? '我' : '情报助手'}：</span>
                  {message.content}
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <textarea
              value={chatDraft}
              onChange={(event) => setCandidateChatDraft(candidate.id, event.target.value)}
              placeholder={`继续问「${radarTitle}」下这篇情报`}
              className="min-h-[76px] flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[13px] leading-6 outline-none focus:border-[#5B7BFE] focus:bg-white"
            />
            <button
              type="button"
              onClick={() => void handleAskCandidateQuestion(candidate)}
              disabled={!chatDraft.trim() || chatLoadingCandidateId === candidate.id}
              className="self-end rounded-md bg-[#5B7BFE] px-4 py-2 text-[12px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {chatLoadingCandidateId === candidate.id ? '发送中…' : '发送'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderCandidateCard = (candidate: TopicCandidate) => {
    const preference = preferenceOf(candidate.id);
    const radarTitle = radarMap.get(candidate.radarId)?.title || '未命名雷达';
    const cardTags = Array.from(new Set([...(candidate.favoriteTags || []), ...(preference.tags || [])]));
    const relatedTaskCount = Math.max((relatedTasksByCandidate.get(candidate.id) || []).length, candidate.convertedTaskId ? 1 : 0);
    const insight = insightCache[candidate.id];
    const isExpanded = expandedCandidateId === candidate.id;
    return (
      <TopicIntelInboxCard
        key={candidate.id}
        candidate={candidate}
        radarTitle={radarTitle}
        saved={isSavedCandidate(candidate, preference)}
        tags={cardTags}
        relatedTaskCount={relatedTaskCount}
        mainBadge={mainBadgeForCandidate(candidate)}
        sourceStatusText={sourceStatusTextForCandidate(candidate)}
        relevanceReason={relevanceReasonForCandidate(candidate, radarTitle, insight)}
        suggestedAction={suggestedActionForCandidate(candidate)}
        isDeepAnalysisOpen={isExpanded}
        isFavoritePending={favoritePendingIds.has(candidate.id)}
        onToggleSaved={() => void handleToggleSaved(candidate)}
        onShare={() => openShareModal(candidate)}
        onOpenTask={() => void openTaskModal(candidate)}
        onToggleDeepAnalysis={() => {
          setSelectedCandidateId(candidate.id);
          setExpandedCandidateId((current) => (current === candidate.id ? '' : candidate.id));
        }}
        onOpenSource={() => {
          if (!candidate.sourceUrl) return;
          window.open(candidate.sourceUrl, '_blank', 'noopener,noreferrer');
        }}
      >
        {renderExpandedCandidate(candidate, radarTitle)}
      </TopicIntelInboxCard>
    );
  };

  const renderPaginationControls = (
    totalCount: number,
    currentPage: number,
    onPageChange: (page: number) => void,
  ) => {
    const totalPages = Math.max(1, Math.ceil(totalCount / TOPIC_PAGE_SIZE));
    if (totalPages <= 1) return null;
    const page = clampTopicPage(currentPage, totalCount);
    const start = (page - 1) * TOPIC_PAGE_SIZE + 1;
    const end = Math.min(totalCount, page * TOPIC_PAGE_SIZE);
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-gray-100 bg-white px-4 py-3 text-[12px] text-gray-500 sm:flex-row sm:items-center sm:justify-between">
        <span>
          第 {start}-{end} 条，共 {totalCount} 条
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              onPageChange(Math.max(1, page - 1));
              setExpandedCandidateId('');
            }}
            disabled={page <= 1}
            className="rounded-md border border-gray-200 bg-white px-3 py-1.5 font-semibold text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            上一页
          </button>
          <span className="min-w-[76px] text-center font-semibold text-gray-700">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => {
              onPageChange(Math.min(totalPages, page + 1));
              setExpandedCandidateId('');
            }}
            disabled={page >= totalPages}
            className="rounded-md border border-gray-200 bg-white px-3 py-1.5 font-semibold text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#F9FAFB] overflow-hidden relative font-sans text-gray-800">
      <div className="shrink-0 border-b border-gray-100 bg-white px-5 py-4 lg:px-8">
        <div className="mx-auto flex max-w-[1160px] flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-[18px] font-bold text-gray-950">
                <Search size={18} className="text-[#5B7BFE]" />
                资讯情报站
              </h1>
              <p className="mt-2 max-w-[760px] text-[13px] leading-6 text-gray-500">
                请先新建雷达并开启自动抓取，AI 会在后台按你设置的频率抓取、解析和轻分析，并定时推送情报；新雷达会先试跑，首次推送通常不会立即出现。
              </p>
            </div>
            <div className="grid w-full grid-cols-2 gap-2 sm:w-[330px]">
              {statusViewOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
	                  onClick={() => openStatusModal(option.id)}
                    aria-haspopup="dialog"
                    aria-expanded={statusModalView === option.id}
	                  className={`inline-flex min-h-[38px] items-center justify-between gap-1.5 rounded-md border px-3 py-2 text-[12px] font-semibold transition-colors ${
                      statusModalView === option.id
                        ? 'border-[#5B7BFE] bg-[#eef2ff] text-[#4a67f5]'
                        : option.id === 'shared' && sharedInboxUnreadCount > 0
                          ? 'border-cyan-200 bg-cyan-50 text-cyan-700 hover:bg-cyan-100'
                        : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                    }`}
	                >
                    <span className="inline-flex min-w-0 items-center gap-1.5">
	                    {option.icon}
	                    <span className="truncate">{option.label}</span>
                    </span>
                    <span className="inline-flex shrink-0 items-center gap-1">
	                    <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">{option.count}</span>
                      {option.id === 'shared' && sharedInboxUnreadCount > 0 && (
                        <span className="rounded-full bg-cyan-600 px-1.5 py-0.5 text-[11px] text-white">未读 {sharedInboxUnreadCount}</span>
                      )}
                    </span>
	                </button>
	              ))}
	            </div>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative min-w-0 flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="搜索标题、来源、雷达、摘要、相关性说明、建议动作"
                className="w-full rounded-md border border-gray-200 bg-gray-50 py-2 pl-9 pr-3 text-[13px] outline-none focus:border-[#5B7BFE] focus:bg-white"
              />
            </div>
            <select
              value={selectedRadarId}
              onChange={(event) => setSelectedRadarId(event.target.value)}
              className="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE] focus:bg-white lg:w-[180px]"
            >
              <option value="all">全部雷达</option>
              {viewerRadars.map((radar) => (
                <option key={radar.id} value={radar.id}>
                  {radar.title}
                </option>
              ))}
            </select>
            <select
              value={badgeFilter}
              onChange={(event) => {
                setBadgeFilter(event.target.value as TopicBadgeFilter);
                setExpandedCandidateId('');
              }}
              className="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE] focus:bg-white lg:w-[150px]"
            >
              {TOPIC_BADGE_FILTERS.map((filter) => (
                <option key={filter.id} value={filter.id}>
                  {filter.label} {badgeFilterCounts[filter.id]}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={openNewRadarConfig}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#5B7BFE] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#4a6be6]"
            >
              <Plus size={15} />
              新建雷达
            </button>
            <button
              type="button"
              onClick={openRadarManager}
              disabled={viewerRadars.length === 0}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-gray-200 bg-white px-4 py-2 text-[13px] font-semibold text-gray-600 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Target size={15} />
              管理已有雷达
            </button>
          </div>

          <div className="flex gap-2 overflow-x-auto">
            {TOPIC_DIRECTIONS.map((direction) => (
              <button
                key={direction.id}
                type="button"
                onClick={() => setActiveDirection(direction.id)}
                className={`shrink-0 rounded-md border px-4 py-2 text-[13px] font-semibold transition-colors ${
                  activeDirection === direction.id
                    ? 'border-[#5B7BFE] bg-[#eef2ff] text-[#4a67f5]'
                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {direction.label}
                <span className="ml-2 text-[11px] text-gray-400">{directionCounts.get(direction.id) || 0}</span>
              </button>
            ))}
          </div>

          {activeDirection === 'public_opinion' && (
            <div className="rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-800">
              当前舆情观察基于公开来源样本，不代表全网完整舆情。
            </div>
          )}

          {(processingCandidates.length > 0 || captureTestingRadarId) && (
            <div className="flex items-start gap-3 rounded-md border border-indigo-100 bg-indigo-50 px-3 py-2 text-[12px] leading-5 text-indigo-800">
              <RefreshCw size={14} className="mt-0.5 shrink-0 animate-spin text-[#5B7BFE]" />
              <div>
                {captureTestingRadarId ? `「${captureTestingRadarTitle}」正在试跑抓取：${captureProgressText(elapsedSeconds(captureTestingStartedAt, topicUiTick))}` : ''}
                {processingCandidates.length > 0
                  ? `AI 正在处理 ${processingCandidates.length} 条新情报${processingRadarTitles.length ? `（${processingRadarTitles.slice(0, 3).join('、')}${processingRadarTitles.length > 3 ? '等' : ''}）` : ''}。`
                  : ''}
                处理期间，已推送过的情报会继续保留在列表中。
              </div>
            </div>
          )}

          {globalMessage && (
            <div className="flex items-center justify-center animate-in fade-in absolute left-1/2 -translate-x-1/2 top-4 z-50">
              <div className="text-[12px] font-bold text-emerald-600 bg-emerald-50 px-4 py-2 rounded-full shadow-sm flex items-center gap-2">
                <CheckSquare size={14} /> {globalMessage}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-6 lg:px-8">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filteredCandidates.length > 0 ? (
            pagedFilteredCandidates.map((candidate) => renderCandidateCard(candidate))
          ) : (
            <div className="rounded-lg border border-dashed border-gray-200 bg-white px-6 py-12 text-center xl:col-span-2">
              <p className="text-[16px] font-bold text-gray-900">当前筛选条件下还没有情报</p>
              <p className="mt-2 text-[13px] text-gray-500">
                可以切换方向、标记、雷达或搜索条件；新雷达首次试跑后会逐步出现内容。
              </p>
            </div>
          )}
          </div>
          {renderPaginationControls(filteredCandidates.length, currentMainPage, setMainPage)}
        </div>
      </div>

      {statusModalView && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="w-[1120px] max-w-[94vw] max-h-[86vh] overflow-hidden rounded-[24px] border border-gray-100 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]">
            <div className="flex items-center justify-between gap-4 border-b border-gray-100 px-6 py-5">
              <div>
                <h3 className="flex items-center gap-2 text-[18px] font-bold text-gray-900">
                  {activeStatusLabel}
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[12px] font-semibold text-gray-500">
                    {statusModalCandidates.length}
                  </span>
                </h3>
                <p className="mt-1 text-[12px] text-gray-500">
                  {activeStatusCopy?.description || '这里展示跨方向完整列表，不受当前页面筛选影响。'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setStatusModalView(null);
                  setStatusModalPage(1);
                  setExpandedCandidateId('');
                }}
                className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                aria-label="关闭情报列表弹窗"
              >
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[calc(86vh-94px)] overflow-y-auto bg-[#F9FAFB] p-5">
              {statusModalCandidates.length > 0 ? (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    {pagedStatusModalCandidates.map((candidate) => renderCandidateCard(candidate))}
                  </div>
                  {renderPaginationControls(statusModalCandidates.length, currentStatusModalPage, setStatusModalPage)}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-gray-200 bg-white px-6 py-12 text-center xl:col-span-2">
                  <p className="text-[16px] font-bold text-gray-900">{activeStatusCopy?.emptyTitle || `当前「${activeStatusLabel}」还没有情报`}</p>
                  <p className="mt-2 text-[13px] text-gray-500">{activeStatusCopy?.emptyDescription || '等收藏、共享或转任务动作产生后，这里会集中显示对应情报。'}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {editingPrefIndex !== null && tempPref && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
	          <div className={`bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] ${radarModalMode === 'manage' ? 'w-[1120px]' : 'w-[860px]'} max-w-[94vw] overflow-hidden transform animate-in zoom-in-95 border border-gray-100`} onClick={(event) => event.stopPropagation()}>
            <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
	              <button type="button" onClick={closeRadarConfig} className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700" aria-label="关闭深度追踪雷达弹窗">
                <X size={18} />
              </button>
              <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                  <Target size={16} strokeWidth={2.5} />
                </div>
                {radarModalMode === 'manage' ? '管理已有雷达' : '新建雷达'}
              </h3>
            </div>

            <div className="max-h-[calc(88vh-150px)] overflow-y-auto p-8 space-y-6">
              {radarModalNotice && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] leading-5 text-amber-800">
                  <AlertCircle size={15} className="mt-0.5 shrink-0" />
                  <span>{radarModalNotice}</span>
                </div>
              )}

              {radarModalMode === 'manage' && radarCards.some((item) => item.id !== 'placeholder-new') && (
                <div className="rounded-lg border border-gray-100 bg-gray-50/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[12px] font-bold text-gray-900">已有雷达</p>
                      <p className="mt-1 text-[12px] text-gray-500">在这里编辑雷达、暂停自动抓取，或手动试跑一次。</p>
                    </div>
                  </div>
                  <div className="mt-4 grid max-h-[400px] grid-cols-1 gap-3 overflow-y-auto pr-1">
                    {radarCards.filter((item) => item.id !== 'placeholder-new').map((pref, index) => {
                      const radar = radars.find((item) => item.id === pref.id);
                      const active = tempPref.id === pref.id;
                      const isTesting = captureTestingRadarId === pref.id;
                      const isToggling = radarTogglePendingId === pref.id;
                      const isDeleting = radarDeletePendingId === pref.id;
                      const lastFetch = pref.lastFetch;
                      const lastFetchNote = latestFetchStatusNote(lastFetch);
                      return (
                        <div
                          key={pref.id}
                          className={`rounded-lg border bg-white p-4 text-[12px] transition-colors ${
                            active ? 'border-[#5B7BFE] shadow-[0_8px_24px_rgba(91,123,254,0.12)]' : 'border-gray-200'
                          }`}
                        >
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="truncate text-[14px] font-bold text-gray-900">{pref.title || '未命名雷达'}</span>
                                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                                  pref.fetchEnabled ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'
                                }`}>
                                  {topicRadarStatusLabel(pref)}
                                </span>
                                <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
                                  {pushFrequencyLabel(pref.pushFrequency, pref.pushWeekday)}
                                </span>
                              </div>
                              <p className="mt-2 max-h-[42px] overflow-hidden text-[12px] leading-[21px] text-gray-500">
                                {pref.prompt || '还没有填写追踪说明。'}
                              </p>
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => openRadarConfig(radar || null, index, 'manage')}
                                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 hover:bg-gray-50"
                              >
                                <Pencil size={13} />
                                编辑
                              </button>
                              <button
                                type="button"
                                onClick={() => radar && void handleToggleRadarFetch(radar)}
                                disabled={!radar || Boolean(radarTogglePendingId)}
                                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {isToggling ? <RefreshCw size={13} className="animate-spin" /> : pref.fetchEnabled ? <Pause size={13} /> : <Play size={13} />}
                                {pref.fetchEnabled ? '暂停' : '启用'}
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleCaptureTestRadar(pref.id)}
                                disabled={Boolean(captureTestingRadarId)}
                                className="inline-flex items-center gap-1.5 rounded-md border border-indigo-100 bg-indigo-50 px-3 py-2 text-[12px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {isTesting ? <RefreshCw size={13} className="animate-spin" /> : <Search size={13} />}
                                {isTesting ? '试跑中…' : '试跑一次'}
                              </button>
                              <button
                                type="button"
                                onClick={() => radar && void handleDeleteRadar(radar)}
                                disabled={!radar || Boolean(radarDeletePendingId)}
                                className="inline-flex items-center gap-1.5 rounded-md border border-rose-100 bg-white px-3 py-2 text-[12px] font-semibold text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {isDeleting ? <RefreshCw size={13} className="animate-spin" /> : <Trash2 size={13} />}
                                {isDeleting ? '删除中…' : '删除'}
                              </button>
                            </div>
                          </div>

                          <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-5">
                            <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                              <p className="text-[11px] font-semibold text-gray-400">情报</p>
                              <p className="mt-1 font-bold text-gray-800">{pref.candidateCount} 条</p>
                            </div>
                            <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                              <p className="text-[11px] font-semibold text-gray-400">关联画像</p>
                              <p className="mt-1 font-bold text-gray-800">{pref.contextRefs.length} 个</p>
                            </div>
                            <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                              <p className="text-[11px] font-semibold text-gray-400">共享者</p>
                              <p className="mt-1 font-bold text-gray-800">{pref.shareRecipients.length} 人</p>
                            </div>
                            <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                              <p className="text-[11px] font-semibold text-gray-400">优先来源</p>
                              <p className="mt-1 font-bold text-gray-800">{pref.priorityUrls.length || pref.preferredSources.length} 个</p>
                            </div>
                            <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                              <p className="text-[11px] font-semibold text-gray-400">下次推送</p>
                              <p className="mt-1 font-bold text-gray-800">{nextPushTextForRadar(pref)}</p>
                            </div>
                          </div>

                          <div className={`mt-3 rounded-md border px-3 py-2 ${
                            lastFetch?.status === 'fetch_failed'
                              ? 'border-rose-100 bg-rose-50 text-rose-700'
                              : 'border-gray-100 bg-gray-50 text-gray-600'
                          }`}>
                            <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                              <p className="font-semibold">
                                最近抓取：{topicFetchStatusLabel(lastFetch?.status)} · {radarFetchSummaryText(lastFetch)}
                              </p>
                              <p className="text-[11px] text-gray-400">
                                {formatTopicDateTime(lastFetch?.finishedAt || lastFetch?.startedAt || lastFetch?.createdAt) || '尚未运行'}
                              </p>
                            </div>
                            {lastFetch?.error && (
                              <p className="mt-1 break-all text-[11px] leading-5">{lastFetch.error}</p>
                            )}
                            {lastFetchNote && !lastFetch?.error && (
                              <p className="mt-1 text-[11px] leading-5 text-gray-500">{lastFetchNote}</p>
                            )}
                            {lastFetch && (lastFetch.fetchedCount || 0) === 0 && !lastFetch.error && (
                              <p className="mt-1 text-[11px] leading-5 text-gray-400">
                                没有新增通常是因为没有配置真实来源、公开搜索无候选，或被时间窗/去重过滤；AI 只负责筛选和分析，不会凭空生成外部资讯。
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {radarModalMode === 'manage' && (
                <div className="flex items-center justify-between rounded-lg border border-indigo-100 bg-indigo-50 px-4 py-3">
                  <div>
                    <p className="text-[12px] font-bold text-indigo-900">当前编辑</p>
                    <p className="mt-1 text-[12px] text-indigo-700">{tempPref.title || '未命名雷达'}</p>
                  </div>
                  <span className="rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-indigo-700">
                    {tempPref.id.startsWith('placeholder-') ? '新建' : '已有雷达'}
                  </span>
                </div>
              )}

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

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <section className="rounded-lg border border-gray-100 bg-gray-50/70 p-4">
                  <p className="text-[12px] font-bold uppercase tracking-widest text-gray-500">关联画像 / 关注对象</p>
                  <p className="mt-2 text-[12px] leading-5 text-gray-500">先选择已有画像，再补充组织类型、服务对象、议题领域或地区范围；这里不重复维护画像正文。</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={toggleOrganizationDnaRef}
                      className={`rounded-md border px-3 py-2 text-[12px] font-semibold ${
                        hasContextRef(tempPref.contextRefs, 'organization_dna', organizationContextRef().id)
                          ? 'border-[#5B7BFE] bg-[#eef2ff] text-[#4a67f5]'
                          : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      本组织 DNA
                    </button>
                    <span className="rounded-md border border-dashed border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-400">客户画像后续接入</span>
                    <span className="rounded-md border border-dashed border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-400">项目画像后续接入</span>
                  </div>

                  <div className="mt-4 space-y-3">
                    {TOPIC_CONTEXT_TYPE_OPTIONS.filter((option) => option.id !== 'custom_focus').map((option) => (
                      <div key={option.id}>
                        <p className="text-[11px] font-bold text-gray-500">{option.label}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {TOPIC_CONTEXT_PRESETS[option.id].map((label) => {
                            const ref = buildContextRef(option.id, label);
                            const checked = hasContextRef(tempPref.contextRefs, ref.type, ref.id);
                            return (
                              <button
                                key={ref.id}
                                type="button"
                                onClick={() => togglePresetContextRef(option.id, label)}
                                className={`rounded-md border px-2.5 py-1.5 text-[12px] font-semibold ${
                                  checked
                                    ? 'border-[#5B7BFE] bg-[#eef2ff] text-[#4a67f5]'
                                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                                }`}
                              >
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-[140px_1fr_auto]">
                    <select
                      value={contextRefType}
                      onChange={(event) => setContextRefType(event.target.value as TopicContextDraftType)}
                      className="rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                    >
                      {TOPIC_CONTEXT_TYPE_OPTIONS.map((option) => (
                        <option key={option.id} value={option.id}>{option.label}</option>
                      ))}
                    </select>
                    <input
                      value={contextRefDraft}
                      onChange={(event) => setContextRefDraft(event.target.value)}
                      placeholder={TOPIC_CONTEXT_TYPE_OPTIONS.find((option) => option.id === contextRefType)?.placeholder}
                      className="min-w-0 flex-1 rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                    />
                    <button
                      type="button"
                      onClick={addCustomContextRef}
                      disabled={!contextRefDraft.trim()}
                      className="rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      添加
                    </button>
                  </div>
                  {tempPref.contextRefs.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {tempPref.contextRefs.map((ref) => (
                        <button
                          type="button"
                          key={`${ref.type}-${ref.id}`}
                          onClick={() => removeContextRef(ref)}
                          className="rounded-md border border-indigo-100 bg-white px-2.5 py-1.5 text-[12px] font-semibold text-indigo-700 hover:bg-indigo-50"
                        >
                          {contextTypeLabel(ref.type)}：{ref.label || ref.id} ×
                        </button>
                      ))}
                    </div>
                  )}
                </section>

                <section className="rounded-lg border border-gray-100 bg-gray-50/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[12px] font-bold uppercase tracking-widest text-gray-500">情报共享者</p>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-500">
                      已选 {tempPref.shareRecipients.length} 人
                    </span>
                  </div>
                  <p className="mt-2 text-[12px] leading-5 text-gray-500">用户点击情报卡片里的共享时，默认共享给这里选择的成员。</p>
                  {tempPref.shareRecipients.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {tempPref.shareRecipients.map((recipient) => (
                        <button
                          type="button"
                          key={recipient.userId}
                          onClick={() => setTempPref((prev) => (
                            prev
                              ? { ...prev, shareRecipients: prev.shareRecipients.filter((item) => item.userId !== recipient.userId) }
                              : prev
                          ))}
                          className="rounded-md border border-cyan-100 bg-white px-2.5 py-1.5 text-[12px] font-semibold text-cyan-700 hover:bg-cyan-50"
                        >
                          {recipient.fullName || recipient.userId} ×
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 max-h-[188px] space-y-2 overflow-y-auto pr-1">
                    {isLoadingRadarShareOptions ? (
                      <div className="flex items-center gap-2 rounded-md border border-gray-100 bg-white px-3 py-2 text-[12px] text-gray-500">
                        <RefreshCw size={13} className="animate-spin text-[#5B7BFE]" />
                        正在加载成员…
                      </div>
                    ) : radarShareOptions.length > 0 ? (
                      radarShareOptions.map((member) => {
                        const checked = tempPref.shareRecipients.some((item) => item.userId === member.id);
                        return (
                          <label key={member.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-md border border-gray-100 bg-white px-3 py-2 text-[12px] hover:bg-gray-50">
                            <span className="min-w-0">
                              <span className="block truncate font-semibold text-gray-800">{member.fullName}</span>
                              <span className="block truncate text-gray-400">{member.email || member.primaryRole}</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleShareRecipient(member)}
                              className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE]"
                            />
                          </label>
                        );
                      })
                    ) : (
                      <div className="rounded-md border border-dashed border-gray-200 bg-white px-3 py-3 text-[12px] text-gray-400">
                        暂时没有可选成员。
                      </div>
                    )}
                  </div>
                </section>
              </div>

              <div className={`grid grid-cols-1 gap-4 rounded-lg border border-gray-100 bg-gray-50/70 p-4 ${tempPref.pushFrequency === 'weekly' ? 'md:grid-cols-5' : 'md:grid-cols-4'}`}>
                <label className="flex items-center gap-3 text-[13px] font-semibold text-gray-700">
                  <input
                    type="checkbox"
                    checked={tempPref.fetchEnabled}
                    onChange={(event) => setTempPref({ ...tempPref, fetchEnabled: event.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE]"
                  />
                  开启自动抓取
                </label>
                <div>
                  <label className="mb-2 block text-[12px] font-bold uppercase tracking-widest text-gray-500">推送频率</label>
                  <select
                    value={tempPref.pushFrequency}
                    onChange={(event) => {
                      const pushFrequency = event.target.value as TopicRadarPushFrequency;
                      setTempPref({
                        ...tempPref,
                        pushFrequency,
                        pushWeekday: pushFrequency === 'weekly' ? (tempPref.pushWeekday || currentIsoWeekday()) : tempPref.pushWeekday,
                      });
                    }}
                    className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                  >
                    <option value="manual">仅手动</option>
                    <option value="daily">每天</option>
                    <option value="workday">工作日</option>
                    <option value="weekly">每周（{weekdayLabel(tempPref.pushWeekday)}）</option>
                  </select>
                </div>
                {tempPref.pushFrequency === 'weekly' && (
                  <div>
                    <label className="mb-2 block text-[12px] font-bold uppercase tracking-widest text-gray-500">推送周几</label>
                    <select
                      value={tempPref.pushWeekday || currentIsoWeekday()}
                      onChange={(event) => setTempPref({ ...tempPref, pushWeekday: Number(event.target.value) })}
                      className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                    >
                      {TOPIC_WEEKDAY_LABELS.slice(1).map((label, index) => (
                        <option key={label} value={index + 1}>周{label}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="mb-2 block text-[12px] font-bold uppercase tracking-widest text-gray-500">推送时间</label>
                  <input
                    type="time"
                    value={tempPref.pushTime}
                    onChange={(event) => setTempPref({ ...tempPref, pushTime: event.target.value })}
                    className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-[12px] font-bold uppercase tracking-widest text-gray-500">时间范围</label>
                  <select
                    value={tempPref.timeRange}
                    onChange={(event) => setTempPref({ ...tempPref, timeRange: event.target.value })}
                    className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-[#5B7BFE]"
                  >
                    <option value="3_days">近 3 天</option>
                    <option value="7_days">近 7 天</option>
                    <option value="30_days">近 30 天</option>
                  </select>
                </div>
              </div>

	              <div className="rounded-[24px] border border-gray-100 bg-gray-50/60 p-5">
	                <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">优先检索网址</label>
	                <div className="mt-3 flex gap-2">
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
	                    {isGeneratingSourceLabel ? <RefreshCw size={14} className="animate-spin" /> : <Plus size={14} />}
	                    {isGeneratingSourceLabel ? '添加中…' : '添加网址'}
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

            <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={() => void handleCaptureTestRadar(tempPref.id)}
                disabled={tempPref.id.startsWith('placeholder-') || captureTestingRadarId === tempPref.id}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-indigo-100 bg-indigo-50 px-4 py-2.5 text-[13px] font-semibold text-indigo-700 transition-colors hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {captureTestingRadarId === tempPref.id ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
                {captureTestingRadarId === tempPref.id ? '试跑中…' : '手动试跑一次'}
              </button>
              <div className="flex justify-end gap-3">
                <button type="button" onClick={closeRadarConfig} className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors">
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => void handleSavePrefEdit()}
                  disabled={isSavingRadarConfig}
                  className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] transition-all inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSavingRadarConfig ? <RefreshCw size={14} className="animate-spin" /> : null}
                  {isSavingRadarConfig ? '保存中…' : radarModalMode === 'manage' ? '保存修改' : '保存新雷达'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {shareCandidate && shareRadar && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="w-[560px] overflow-hidden rounded-[24px] border border-gray-100 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.15)]" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-4 border-b border-gray-100 px-6 py-5">
              <button
                type="button"
                onClick={() => { if (!isSharing) { setShareCandidateId(null); setShareReason(''); setShareModalNotice(null); } }}
                className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="关闭共享弹窗"
                disabled={isSharing}
              >
                <X size={18} />
              </button>
              <div>
                <h3 className="flex items-center gap-2 text-[17px] font-bold text-gray-900">
                  <Share2 size={16} className="text-[#5B7BFE]" />
                  共享情报
                </h3>
                <p className="mt-1 text-[12px] text-gray-500">接收人来自所属雷达的共享对象配置。</p>
              </div>
            </div>
            <div className="space-y-4 p-6">
              <div className="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3">
                <p className="text-[11px] font-bold text-[#5B7BFE]">当前情报</p>
                <h4 className="mt-2 text-[15px] font-bold leading-6 text-gray-900">{shareCandidate.title}</h4>
                <p className="mt-2 text-[12px] leading-6 text-gray-600">{shareCandidate.summary}</p>
              </div>
              {shareModalNotice && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] leading-5 text-amber-800">
                  <AlertCircle size={15} className="mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p>{shareModalNotice}</p>
                    {shareRadar && !(shareRadar.shareRecipients || []).length && (
                      <button
                        type="button"
                        onClick={() => {
                          setShareCandidateId(null);
                          setShareReason('');
                          setShareModalNotice(null);
                          openRadarConfig(shareRadar, radars.findIndex((radar) => radar.id === shareRadar.id), 'manage');
                        }}
                        className="mt-2 rounded-md border border-amber-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-amber-800 hover:bg-amber-100"
                      >
                        去配置雷达共享者
                      </button>
                    )}
                  </div>
                </div>
              )}
              <div>
                <p className="text-[12px] font-bold text-gray-900">共享给</p>
                {(shareRadar.shareRecipients || []).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(shareRadar.shareRecipients || []).map((recipient) => (
                      <span key={recipient.userId} className="rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-[12px] font-semibold text-gray-700">
                        {recipient.fullName || recipient.userId}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 rounded-md border border-dashed border-gray-200 bg-gray-50 px-3 py-2 text-[12px] text-gray-500">
                    暂无共享者，保存共享者后这里会显示接收人。
                  </p>
                )}
              </div>
              <textarea
                value={shareReason}
                onChange={(event) => setShareReason(event.target.value)}
                placeholder="可选：补充推荐理由"
                className="min-h-[110px] w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none focus:border-[#5B7BFE] focus:bg-white"
              />
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-100 bg-gray-50/50 px-6 py-4">
              <button
                type="button"
                onClick={() => { if (!isSharing) { setShareCandidateId(null); setShareReason(''); setShareModalNotice(null); } }}
                className="px-5 py-2 text-[13px] font-bold text-gray-500 hover:text-gray-800"
                disabled={isSharing}
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSubmitShare()}
                disabled={isSharing || !(shareRadar.shareRecipients || []).length}
                className="inline-flex items-center gap-2 rounded-xl bg-[#5B7BFE] px-6 py-2.5 text-[13px] font-semibold text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSharing ? <RefreshCw size={14} className="animate-spin" /> : <Share2 size={14} />}
                {isSharing ? '共享中…' : '确认共享'}
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
                onClick={() => { if (!isSubmittingTask) closeTopicTaskModal(); }}
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
                <p className="text-[12px] text-gray-500 mt-1">这里只创建一条任务，并把当前情报原文入口、摘要和观点写进任务说明与备注。</p>
              </div>
            </div>

            <div className="p-8 space-y-5 overflow-y-auto max-h-[calc(88vh-150px)]">
              {taskModalNotice && (
                <div className={`rounded-2xl border px-4 py-3 text-[13px] leading-6 ${
                  taskModalNotice.type === 'success'
                    ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                    : taskModalNotice.type === 'error'
                      ? 'border-rose-100 bg-rose-50 text-rose-700'
                      : 'border-blue-100 bg-blue-50 text-blue-700'
                }`}>
                  {taskModalNotice.text}
                </div>
              )}

              <div className="rounded-[24px] border border-blue-100 bg-blue-50/50 px-5 py-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#5B7BFE]">当前情报</p>
                <h4 className="text-[16px] font-bold text-gray-900 mt-2">{taskModalCandidate.title}</h4>
                <p className="text-[12px] text-gray-600 mt-2 leading-6">{taskModalCandidate.summary}</p>
              </div>

              {isPreparingTaskModal ? (
                <div className="rounded-[24px] border border-gray-100 bg-gray-50 px-5 py-10 text-center text-gray-500 flex flex-col items-center gap-3">
                  <RefreshCw size={20} className="animate-spin text-[#5B7BFE]" />
                  <p className="text-[13px] font-medium">正在加载可选负责人和协作者…</p>
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
                                collaboratorIds: prev.collaboratorIds.filter((id) => id !== event.target.value),
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

                  <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] font-bold text-gray-700">协作者</p>
                      <p className="text-[11px] text-gray-400">可多选，负责人不重复列为协作者</p>
                    </div>
                    <div className="mt-3 flex max-h-[116px] flex-wrap gap-2 overflow-y-auto">
                      {taskOwnerOptions
                        .filter((candidate) => candidate.id !== taskDraft.ownerId)
                        .map((candidate) => {
                          const checked = taskDraft.collaboratorIds.includes(candidate.id);
                          return (
                            <button
                              key={`task-collab-${candidate.id}`}
                              type="button"
                              onClick={() => toggleTaskCollaborator(candidate.id)}
                              className={`rounded-md border px-3 py-2 text-[12px] font-semibold transition-colors ${
                                checked
                                  ? 'border-[#5B7BFE] bg-[#eef2ff] text-[#4a67f5]'
                                  : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                              }`}
                            >
                              {candidate.fullName}{candidate.isSelf ? '（自己）' : ''}
                            </button>
                          );
                        })}
                      {taskOwnerOptions.filter((candidate) => candidate.id !== taskDraft.ownerId).length === 0 && (
                        <span className="text-[12px] text-gray-400">暂无可选协作者。</span>
                      )}
                    </div>
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
                    placeholder="给同事的补充说明。系统会自动把情报原文入口、摘要和核心观点附在任务说明与备注里。"
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
                  closeTopicTaskModal();
                }}
                className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors"
              >
                {createdTopicTaskId ? '关闭' : '取消'}
              </button>
              <button
                type="button"
                onClick={() => void handleSubmitTask()}
                disabled={isPreparingTaskModal || isSubmittingTask || Boolean(createdTopicTaskId)}
                className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] disabled:opacity-60 disabled:cursor-not-allowed transition-all inline-flex items-center gap-2"
              >
                {isSubmittingTask ? <RefreshCw size={14} className="animate-spin" /> : <CheckSquare size={14} />}
                {createdTopicTaskId ? '已同步' : isSubmittingTask ? '同步中…' : '确认同步到任务'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
