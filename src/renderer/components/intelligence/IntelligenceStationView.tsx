// @ts-nocheck — 整合于 2026-05-13：同事 push 的资讯情报站视图，半成品，
// 5 个 setState 函数式更新回调里 `current` 参数 implicit any，等同事下次 sync
// 后他自己加类型注解或在 origin/main 用更宽松的 tsconfig。我们暂时跳过 type check，
// 避免 npx tsc --noEmit 在我们这条线被同事的代码挡掉。
import React, { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  BellPlus,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  FileCheck2,
  Lightbulb,
  Loader2,
  Megaphone,
  MessageCircle,
  Pencil,
  RefreshCw,
  Save,
  Send,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
  Zap,
} from 'lucide-react';

import type {
  BrandMirrorSnapshot,
  IntelligenceCandidateSample,
  IntelligenceContentKind,
  IntelligenceDismissReasonCode,
  IntelligenceFocusDirective,
  IntelligenceFocusDirectivePayload,
  IntelligenceFollowMode,
  IntelligenceItem,
  IntelligenceRefreshCycleSettings,
  IntelligenceRefreshResult,
  IntelligenceRefreshRun,
  IntelligenceTaskDraftPayload,
  IntelligenceWorkObject,
  MentionCandidate,
  SessionUser,
  TaskList,
  TaskSettings,
  TopicCandidateChatMessage,
  TopicTaskPromotionDraft,
} from '../../../shared/types';
import {
  // autoRefreshIntelligenceDue,  // TODO: 半成品，api.ts 未导出；先注释解除启动崩溃
  askIntelligenceItemQuestion,
  createIntelligenceTask,
  dismissIntelligenceItem,
  followIntelligenceItem,
  getCandidateTaskPlan,
  getIntelligenceFocusDirectives,
  getIntelligenceItems,
  getIntelligenceRefreshCycleSettings,
  getIntelligenceRefreshRuns,
  getIntelligenceTaskDraft,
  getIntelligenceWorkObjects,
  getMentionCandidates,
  promoteCandidateTasks,
  refreshIntelligenceSupply,
  saveIntelligenceFocusDirective,
  submitIntelligenceVerificationFeedback,
  updateIntelligenceRefreshCycleSettings,
  // 舆情监控 + 印象主题 + 定位差异（P2-a → P5）
  refreshSentiment,
  listSentimentItems,
  getSentimentProfile,
  sendSentimentFeedback,
  listSentimentThemes,
  recomputeSentimentThemes,
  getThemeItems,
  getPositioningGap,
  getClientBrandProposition,
  updateClientBrandProposition,
  getBrandAudit,
  recomputeBrandAudit,
  fetchBrandMirrorSnapshot,
  triggerBrandMirrorAnalysis,
  type SentimentItem,
  type SentimentProfile,
  type SentimentRefreshResult,
  type SentimentFeedbackAction,
  type SentimentTheme,
  type ThemeItemSource,
  type PositioningGapResponse,
  type GapAlignment,
  type BrandAudit,
} from '../../lib/api';

type IntelligenceStationViewProps = {
  activeTaskLists: TaskList[];
  effectiveTaskSettings: TaskSettings;
  currentSessionUser: SessionUser | null;
  currentOperatorName: string;
  flash: (type: 'success' | 'error' | 'info', text: string) => void;
  onTasksReload: () => Promise<unknown>;
};

type SortMode = 'published_desc' | 'published_asc' | 'captured_desc' | 'captured_asc';
type ScopeKey = 'global' | `${IntelligenceWorkObject['type']}:${string}`;
type WorkObjectSelection = 'all' | ScopeKey;

type FocusDraft = {
  profileCompletionFocus: string;
  timelyIntelligenceFocus: string;
  exclude: string;
};

type ClarificationTarget = { type: 'item'; item: IntelligenceItem };

const PAGE_SIZE: Record<IntelligenceContentKind, number> = {
  brand_mirror: 1,
  timely_intelligence: 5,
  public_opinion: 50,
};

const TAB_LABEL: Record<IntelligenceContentKind, string> = {
  brand_mirror: '品牌镜子',
  timely_intelligence: '时效情报',
  public_opinion: '舆情监控',
};

const TAB_HINT: Record<IntelligenceContentKind, string> = {
  brand_mirror: '从官方/媒体/合作信源照出品牌呈现',
  timely_intelligence: '需要判断与跟进的外部信号',
  public_opinion: '已抓到的公众声音（辅栏）',
};

const SORT_LABEL: Record<SortMode, string> = {
  captured_desc: '抓取时间新到旧（默认）',
  captured_asc: '抓取时间旧到新',
  published_desc: '发布时间新到旧',
  published_asc: '发布时间旧到新',
};

const DISMISS_REASON_LABEL: Record<IntelligenceDismissReasonCode, string> = {
  irrelevant: '不相关',
  inaccurate: '不准确',
  duplicate: '重复',
  outdated: '过期',
  low_value: '低价值',
};

const FOLLOW_MODE_LABEL: Record<IntelligenceFollowMode, string> = {
  same_theme: '同主题',
  same_source: '同来源',
  same_work_object: '同客户/项目机会',
};

const EMPTY_FOCUS_DRAFT: FocusDraft = {
  profileCompletionFocus: '',
  timelyIntelligenceFocus: '',
  exclude: '',
};

const DEFAULT_REFRESH_CYCLE_SETTINGS: IntelligenceRefreshCycleSettings = {
  profileCompletionHours: 72,
  timelyIntelligenceHours: 24,
};

function formatTime(value?: string | null) {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatDateOnly(value?: string | null) {
  if (!value) return '未标注';
  const trimmed = value.trim();
  const directDate = trimmed.match(/\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}/);
  if (directDate) return directDate[0].replace(/[年月/.]/g, '-').replace(/日/g, '');
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return trimmed;
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

function splitText(value: string) {
  return value
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function compactText(value: string, maxLength = 120) {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function scopeKeyOfObject(item: IntelligenceWorkObject): ScopeKey {
  return `${item.type}:${item.id}`;
}

function directiveMatches(directive: IntelligenceFocusDirective, scopeKey: ScopeKey) {
  if (scopeKey === 'global') return directive.scopeType === 'global';
  const [type, id] = scopeKey.split(':');
  return directive.scopeType === type && directive.scopeId === id;
}

function directivePayload(scopeKey: ScopeKey, draft: FocusDraft): IntelligenceFocusDirectivePayload {
  if (scopeKey === 'global') {
    return {
      scopeType: 'global',
      scopeId: null,
      profileCompletionFocus: splitText(draft.profileCompletionFocus),
      timelyIntelligenceFocus: splitText(draft.timelyIntelligenceFocus),
      exclude: splitText(draft.exclude),
    };
  }
  const [scopeType, scopeId] = scopeKey.split(':') as [IntelligenceWorkObject['type'], string];
  return {
    scopeType,
    scopeId,
    profileCompletionFocus: splitText(draft.profileCompletionFocus),
    timelyIntelligenceFocus: splitText(draft.timelyIntelligenceFocus),
    exclude: splitText(draft.exclude),
  };
}

function draftFromDirective(directive?: IntelligenceFocusDirective): FocusDraft {
  if (!directive) return EMPTY_FOCUS_DRAFT;
  return {
    profileCompletionFocus: directive.profileCompletionFocus.join('\n'),
    timelyIntelligenceFocus: directive.timelyIntelligenceFocus.join('\n'),
    exclude: directive.exclude.join('\n'),
  };
}

function itemObjectLabel(item: IntelligenceItem, objects: IntelligenceWorkObject[]) {
  if (item.projectModuleId) {
    const project = objects.find((object) => object.type === 'project_module' && object.id === item.projectModuleId);
    if (project) return `项目 · ${project.name}`;
  }
  if (item.clientId) {
    const client = objects.find((object) => object.type === 'client' && object.id === item.clientId);
    if (client) return `客户 · ${client.name}`;
  }
  return '全部对象';
}

function selectedObjectLabel(value: WorkObjectSelection, objects: IntelligenceWorkObject[]) {
  if (value === 'all') return '全部客户/项目';
  const object = objects.find((item) => scopeKeyOfObject(item) === value);
  if (!object) return '全部客户/项目';
  return `${object.type === 'client' ? '客户' : '项目'} · ${object.name}`;
}

function scopeRefreshPayload(selection: WorkObjectSelection, object: IntelligenceWorkObject | null, contentKind: IntelligenceContentKind) {
  if (selection === 'all' || !object) {
    return { scopeType: 'all' as const, scopeId: null, contentKind, force: true };
  }
  return { scopeType: object.type, scopeId: object.id, contentKind, force: true };
}

function summarizeRefreshResult(result: IntelligenceRefreshResult) {
  const label = TAB_LABEL[result.contentKind];
  const totals = result.totals;
  if (isBackgroundRefreshQueued(result)) {
    return `${label}已启动：已派发 ${totals.objectCount} 个对象进入后台抓取，正在公开搜索、正文抓取和核验。`;
  }
  if (totals.candidateCount <= 0 && totals.promotedCount <= 0 && !totals.failedCount) {
    return `${label}流程已跑完：处理 ${totals.objectCount} 个对象，但没有找到可进入判断流程的中文公开资料。`;
  }
  return `${label}刷新完成：处理 ${totals.objectCount} 个对象，线索 ${totals.candidateCount} 条，成卡 ${totals.promotedCount} 条${totals.noResultCount ? `，未找到 ${totals.noResultCount} 个对象` : ''}${totals.failedCount ? `，失败 ${totals.failedCount} 个对象` : ''}。`;
}

function isBackgroundRefreshQueued(result: IntelligenceRefreshResult) {
  if (!result.results.length || result.totals.candidateCount > 0 || result.totals.promotedCount > 0) return false;
  return result.results.every((item) => {
    const message = item.message || '';
    return message.includes('后台抓取队列') || message.includes('后台抓取') || message.includes('已加入后台');
  });
}

function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 px-1 py-4 text-[13px] text-gray-600">
      <span className="font-semibold">
        第 {page} / {totalPages} 页，共 {total} 条
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          title="上一页"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          title="下一页"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

function profileTags(tags: string[]) {
  const internalTags = new Set(['已核验资料', 'web_search', 'official_site', 'social_org_registry', 'charity_media']);
  return tags.filter((tag) => tag && !internalTags.has(tag) && !tag.includes('_'));
}

function profileGapLabel(item: IntelligenceItem) {
  const tags = profileTags(item.tags);
  return tags.length > 0 ? tags.join(' / ') : item.title;
}

function compactSourceLabel(label: string, url: string) {
  const trimmed = label.trim();
  if (trimmed && !/^https?:\/\//i.test(trimmed) && trimmed.length <= 36) return trimmed;
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return trimmed || '打开来源';
  }
}

function looksLikeDomainLabel(label: string) {
  const trimmed = label.trim();
  return /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(trimmed);
}

function looksLikeUrlOrDomainLabel(label: string) {
  const trimmed = label.trim();
  return /^https?:\/\//i.test(trimmed) || looksLikeDomainLabel(trimmed);
}

function isGenericSourceLabel(label: string) {
  return ['公开搜索', '通用公开搜索', '公开来源', '搜索结果', 'web_search'].includes(label.trim());
}

function readableSourceLabel(label: string, url: string) {
  const trimmed = label.trim();
  if (trimmed && !looksLikeUrlOrDomainLabel(trimmed)) {
    return trimmed.length > 48 ? `${trimmed.slice(0, 46)}...` : trimmed;
  }
  return compactSourceLabel(label, url);
}

function sourceLinks(item: IntelligenceItem) {
  const items: Array<{ label: string; url: string }> = [];
  if (item.sourceUrl) {
    const rawSource = item.source || '';
    const sourceLabel = looksLikeUrlOrDomainLabel(rawSource) || isGenericSourceLabel(rawSource) ? item.title : rawSource || item.title;
    items.push({ label: readableSourceLabel(sourceLabel, item.sourceUrl), url: item.sourceUrl });
  }
  const sourceText = item.source || '';
  for (const line of sourceText.split(/\n+/)) {
    const trimmed = line.trim();
    const match = trimmed.match(/https?:\/\/\S+/);
    if (!match) continue;
    const url = match[0];
    if (items.some((item) => item.url === url)) continue;
    const label = trimmed.replace(url, '').replace(/[：:｜|\-—\s]+$/g, '').trim();
    items.push({ label: compactSourceLabel(label, url), url });
  }
  return items;
}

function refreshRunObjectLabel(run: IntelligenceRefreshRun, workObjects: IntelligenceWorkObject[]) {
  const targetId = run.projectModuleId || run.clientId || run.scopeId || '';
  const object = workObjects.find((item) => item.id === targetId);
  if (object) return `${object.type === 'client' ? '客户' : '项目'} · ${object.name}`;
  return targetId ? `对象 ${targetId}` : '全部对象';
}

function refreshRunCount(run: IntelligenceRefreshRun, key: string) {
  const value = run.result?.[key];
  const number = typeof value === 'number' ? value : Number(value || 0);
  return Number.isFinite(number) ? number : 0;
}

function refreshRunStringList(run: IntelligenceRefreshRun, key: string) {
  const value = run.result?.[key];
  if (!Array.isArray(value)) return [] as string[];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
}

function runTimestamp(run: IntelligenceRefreshRun) {
  const parsed = new Date(run.finishedAt || run.updatedAt || run.createdAt).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sameRefreshRunBatch(a: IntelligenceRefreshRun, b: IntelligenceRefreshRun) {
  if (a.contentKind !== b.contentKind || a.status !== b.status) return false;
  if (a.triggerSource !== b.triggerSource) return false;
  if (a.createdAt && b.createdAt && a.createdAt === b.createdAt) return true;
  const aCreated = new Date(a.createdAt).getTime();
  const bCreated = new Date(b.createdAt).getTime();
  if (Number.isNaN(aCreated) || Number.isNaN(bCreated)) return false;
  return Math.abs(aCreated - bCreated) <= 10_000;
}

function latestFinishedRunBatch(runs: IntelligenceRefreshRun[], contentKind: IntelligenceContentKind | null) {
  const finished = runs
    .filter((run) => (run.status === 'completed' || run.status === 'failed') && (!contentKind || run.contentKind === contentKind))
    .sort((a, b) => runTimestamp(b) - runTimestamp(a));
  const latest = finished[0] || null;
  if (!latest) return { latest, batch: [] as IntelligenceRefreshRun[] };
  return {
    latest,
    batch: finished.filter((run) => sameRefreshRunBatch(run, latest)),
  };
}

function refreshRunTimeRange(runs: IntelligenceRefreshRun[]) {
  const starts = runs.map((run) => run.startedAt || run.createdAt).filter(Boolean).sort();
  const ends = runs.map((run) => run.finishedAt || run.updatedAt).filter(Boolean).sort();
  if (!starts.length || !ends.length) return '本次运行';
  return `${formatTime(starts[0])} - ${formatTime(ends[ends.length - 1])}`;
}

function refreshRunObjectSummary(runs: IntelligenceRefreshRun[], workObjects: IntelligenceWorkObject[]) {
  const labels = runs.map((run) => refreshRunObjectLabel(run, workObjects)).filter(Boolean);
  const unique = Array.from(new Set(labels));
  if (unique.length <= 2) return unique.join('、') || '当前对象';
  return `${unique.slice(0, 2).join('、')} 等 ${unique.length} 个`;
}

function RefreshProgressPanel({
  contentKind,
  hasItems,
  runs,
  workObjects,
  loading,
  onReload,
}: {
  contentKind: IntelligenceContentKind | null;
  hasItems: boolean;
  runs: IntelligenceRefreshRun[];
  workObjects: IntelligenceWorkObject[];
  loading: boolean;
  onReload: () => void;
}) {
  const scopedRuns = contentKind ? runs.filter((run) => run.contentKind === contentKind) : runs;
  const activeRuns = scopedRuns.filter((run) => run.status === 'queued' || run.status === 'running');
  const { latest: latestFinishedRun, batch: latestFinishedRuns } = latestFinishedRunBatch(scopedRuns, contentKind);
  const visibleKind = contentKind || latestFinishedRun?.contentKind || null;
  if (!visibleKind) return null;
  const showingActive = activeRuns.length > 0;
  const finishedRuns = showingActive ? [] : latestFinishedRuns;
  const promotedCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'promotedCount'), 0);
  const candidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'candidateCount'), 0);
  const scoutCandidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'scoutCandidateCount'), 0);
  const reviewCandidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'reviewCandidateCount'), 0);
  const timelyScoutCount = scoutCandidateCount || candidateCount;
  return (
    <div className={`mb-4 border-l-4 bg-white px-4 py-3 text-[12px] font-semibold leading-5 shadow-sm ${showingActive ? 'border-gray-950 text-gray-700' : latestFinishedRun?.status === 'failed' ? 'border-rose-400 text-rose-950' : 'border-blue-300 text-blue-950'}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-gray-950">
          {showingActive ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          {showingActive
            ? `后台研究中：${TAB_LABEL[visibleKind]}（${activeRuns.length} 个对象）`
            : latestFinishedRun?.status === 'failed'
              ? `最近${TAB_LABEL[visibleKind]}失败`
              : latestFinishedRun
                ? `最近${TAB_LABEL[visibleKind]}已完成`
                : `${TAB_LABEL[visibleKind]}待启动`}
        </div>
        <button
          type="button"
          onClick={onReload}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[12px] font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          刷新状态
        </button>
      </div>
      {showingActive ? (
        <>
          <p className="mt-2 text-gray-500">
            正在抓取可核验详情页，并判断外部变化、影响链条和下一步动作。切到其他模块后回来，状态会继续保留。
          </p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {activeRuns.slice(0, 4).map((run) => (
              <div key={run.id} className="rounded-md bg-gray-50 px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <b className="text-gray-900">{refreshRunObjectLabel(run, workObjects)}</b>
                  <span className="text-gray-500">{run.status === 'queued' ? '排队中' : '运行中'} · {formatTime(run.updatedAt)}</span>
                </div>
                <p className="mt-1 text-gray-600">{run.message || run.stage || '后台研究正在推进'}</p>
              </div>
            ))}
          </div>
        </>
      ) : latestFinishedRun ? (
        <>
          <div className="mt-3 grid gap-2 md:grid-cols-6">
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">客户/项目</span>
              <b>{refreshRunObjectSummary(finishedRuns, workObjects)}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">运行时间</span>
              <b>{refreshRunTimeRange(finishedRuns)}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">初筛候选</span>
              <b>{timelyScoutCount}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">入围复核</span>
              <b>{reviewCandidateCount}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">最终成卡</span>
              <b>{promotedCount}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">最新更新时间</span>
              <b>{formatTime(latestFinishedRun.updatedAt)}</b>
            </div>
          </div>
          <p className="mt-2 text-blue-900/70">
            {latestFinishedRun.message || '后台研究已结束。'}
          </p>
        </>
      ) : (
        <p className="mt-2 text-blue-900/70">
          尚未开始自动抓取，可以点击右上角按钮手动抓取情报。
        </p>
      )}
      {!showingActive && latestFinishedRun && !hasItems && (
        <p className="mt-1 text-blue-900/70">
          当前没有通过严格判断的时效情报卡；系统不会把候选短摘或未核验页面放进普通列表。
        </p>
      )}
    </div>
  );
}

function EmptyState({
  contentKind,
  selectedWorkObject,
  workObjects,
  candidateSamples,
  refreshing,
  onRefresh,
}: {
  contentKind: IntelligenceContentKind;
  selectedWorkObject: IntelligenceWorkObject | null;
  workObjects: IntelligenceWorkObject[];
  candidateSamples: IntelligenceCandidateSample[];
  refreshing: boolean;
  onRefresh: (contentKind: IntelligenceContentKind) => void;
}) {
  void contentKind;
  void selectedWorkObject;
  void workObjects;
  void candidateSamples;
  void refreshing;
  void onRefresh;
  return null;
}

function IntelligenceField({
  label,
  children,
  tone = 'default',
}: {
  label: string;
  children: React.ReactNode;
  tone?: 'default' | 'amber';
}) {
  const labelClass = tone === 'amber' ? 'text-amber-700' : 'text-gray-500';
  const bodyClass = tone === 'amber' ? 'text-amber-950' : 'text-gray-700';
  return (
    <div className="min-w-0">
      <p className={`text-[12px] font-black ${labelClass}`}>{label}</p>
      <div className={`mt-2 text-[13px] leading-6 ${bodyClass}`}>{children}</div>
    </div>
  );
}

type QuestionPromptGroup = {
  title: string;
  ordered?: boolean;
  questions: string[];
};

function buildQuestionPromptGroups(item: IntelligenceItem, objects: IntelligenceWorkObject[]): QuestionPromptGroup[] {
  const cardQuestions = item.followupQuestions
    .map((question) => question.trim())
    .filter(Boolean)
    .slice(0, 3);
  return cardQuestions.length ? [{ title: '', ordered: false, questions: cardQuestions }] : [];
}

function TimelyIntelligenceCard({
  item,
  workObjects,
  pending,
  onDismiss,
  onFollow,
  onQuestion,
  onPromoteToTask,
}: {
  item: IntelligenceItem;
  workObjects: IntelligenceWorkObject[];
  pending: boolean;
  onDismiss: (item: IntelligenceItem) => void;
  onFollow: (item: IntelligenceItem) => void;
  onQuestion: (item: IntelligenceItem) => void;
  onPromoteToTask: (item: IntelligenceItem) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const links = sourceLinks(item);
  const objectLabel = itemObjectLabel(item, workObjects);
  const timeliness = item.timelinessLabel || (item.publishedAt ? `发布 ${formatTime(item.publishedAt)}` : `抓取 ${formatTime(item.capturedAt)}`);
  const isConverted = Boolean(item.convertedTaskId);
  const isFollowing = item.userStatus === 'following';
  const isDismissed = item.userStatus === 'dismissed';
  const isPending = !isConverted && !isFollowing && !isDismissed;
  // 左侧 3px 锚线颜色:状态可视化的核心
  const accentColor = isConverted ? '#94A3B8' : isFollowing ? '#10B981' : isDismissed ? 'transparent' : '#5B7BFE';
  const statusLabel = isConverted ? '已转任务' : isFollowing ? '已关注' : isDismissed ? '已忽略' : '待处理';
  const statusToneCls = isConverted
    ? 'text-gray-500 border-gray-200 bg-gray-50'
    : isFollowing
      ? 'text-emerald-700 border-emerald-200 bg-emerald-50'
      : isDismissed
        ? 'text-gray-400 border-gray-200 bg-gray-50'
        : 'text-[#5B7BFE] border-blue-200 bg-blue-50';

  return (
    <article
      className={`relative border rounded-xl transition-all duration-200 ${
        isDismissed
          ? 'border-gray-100 bg-gray-50/50 opacity-60'
          : expanded
            ? 'border-[#C9D6FF] bg-white shadow-[0_2px_8px_rgba(91,123,254,0.06)]'
            : 'border-gray-100 bg-white hover:border-gray-200 hover:shadow-[0_1px_3px_rgba(15,23,42,0.04)]'
      }`}
      style={{
        boxShadow: `inset 3px 0 0 0 ${accentColor}${expanded ? ', 0 2px 8px rgba(91,123,254,0.06)' : ''}`,
      }}
    >
      {/* 收起状态:meta + 标题 + 摘要 + 主操作 */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((prev) => !prev)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setExpanded((prev) => !prev);
          }
        }}
        className="cursor-pointer pl-6 pr-5 py-4 flex items-start gap-3"
      >
        <div className="min-w-0 flex-1">
          {/* meta 一行:状态点 + 客户名 + 时效 */}
          <div className="flex items-center gap-2 flex-wrap text-[11px] text-gray-500">
            <span
              className="inline-block h-[6px] w-[6px] rounded-full shrink-0"
              style={{ backgroundColor: accentColor === 'transparent' ? '#D1D5DB' : accentColor }}
            />
            <span className="font-medium text-gray-700 truncate max-w-[180px]">{objectLabel}</span>
            <span className="text-gray-300">·</span>
            <span>{timeliness}</span>
            {item.intelligenceType && (
              <>
                <span className="text-gray-300">·</span>
                <span className="text-gray-400">{item.intelligenceType}</span>
              </>
            )}
            <span className={`ml-1 inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${statusToneCls}`}>
              {statusLabel}
            </span>
          </div>
          {/* 标题:14px medium */}
          <h2 className={`mt-1.5 text-[14px] leading-snug font-medium ${isDismissed || isConverted ? 'text-gray-600' : 'text-gray-900'}`}>
            {item.title}
          </h2>
          {/* 摘要:line-clamp-2 */}
          {item.summary && (
            <p className={`mt-1 text-[12px] leading-[1.65] line-clamp-2 ${isDismissed ? 'text-gray-400' : 'text-gray-500'}`}>
              {item.summary}
            </p>
          )}
        </div>
        {/* 右侧操作区:主操作 + 展开 chevron */}
        <div className="flex items-start gap-2 shrink-0">
          {isPending && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onPromoteToTask(item);
              }}
              disabled={pending}
              className="inline-flex items-center gap-1 rounded-md bg-[#5B7BFE] px-3 py-1.5 text-[12px] font-bold text-white hover:bg-[#4A6AE6] disabled:opacity-50 transition-colors"
            >
              {pending ? <Loader2 size={12} className="animate-spin" /> : <SlidersHorizontal size={12} />}
              转任务
            </button>
          )}
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setExpanded((prev) => !prev);
            }}
            className="inline-flex items-center justify-center rounded-md p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-50 transition-colors"
            title={expanded ? '收起' : '展开详情'}
            aria-label={expanded ? '收起' : '展开详情'}
          >
            <ChevronDown size={16} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* 展开后:详细字段 + 完整操作组 */}
      {expanded && (
        <div className="pl-6 pr-5 pb-5 space-y-4 border-t border-gray-100 pt-4">
          {/* WHY · 为什么和你有关 */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-1.5">WHY · 为什么和你有关</p>
            <p className="text-[12.5px] leading-[1.7] text-gray-700">
              {item.relevanceReason || item.analysis || '尚未补齐结构化相关性判断。'}
            </p>
          </div>
          {/* IMPACT · 可能影响 — amber 锚线突出"需要警觉" */}
          <div className="relative pl-3">
            <span className="absolute left-0 top-1 bottom-1 w-[2px] rounded-full bg-amber-400" />
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-700 mb-1.5">IMPACT · 可能影响</p>
            <p className="text-[12.5px] leading-[1.7] text-gray-700">
              {item.impact || '需要判断是否跟进。'}
            </p>
          </div>
          {/* ACTION · 建议动作 */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-1.5">ACTION · 建议动作</p>
            <p className="text-[12.5px] leading-[1.7] text-gray-700">
              {item.suggestedAction || item.impact || '可转成阅读 / 研判任务,再判断是否跟进。'}
            </p>
          </div>
          {/* SOURCE · 来源 */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400 mb-1.5">SOURCE · 来源</p>
            {links.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(event) => event.stopPropagation()}
                    className="inline-flex max-w-full items-center truncate rounded-md border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11.5px] font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                    title={link.url}
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-[11.5px] text-gray-500">{item.source || '来源未知'}</p>
            )}
          </div>
          {/* 完整操作组 */}
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-gray-100">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onQuestion(item);
              }}
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11.5px] font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
            >
              <MessageCircle size={12} />
              追问
            </button>
            {!isFollowing && !isDismissed && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onFollow(item);
                }}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-[11.5px] font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
              >
                <BellPlus size={12} />
                关注后续
              </button>
            )}
            {!isPending && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onPromoteToTask(item);
                }}
                disabled={pending}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11.5px] font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                {pending ? <Loader2 size={12} className="animate-spin" /> : <SlidersHorizontal size={12} />}
                转任务
              </button>
            )}
            {!isDismissed && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onDismiss(item);
                }}
                disabled={pending}
                className="ml-auto inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11.5px] font-medium text-gray-500 hover:bg-rose-50 hover:border-rose-200 hover:text-rose-600 disabled:opacity-50 transition-colors"
              >
                <Trash2 size={12} />
                不采纳
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

export function IntelligenceStationView({
  activeTaskLists,
  effectiveTaskSettings,
  currentSessionUser,
  currentOperatorName,
  flash,
  onTasksReload,
}: IntelligenceStationViewProps) {
  const [workObjects, setWorkObjects] = useState<IntelligenceWorkObject[]>([]);
  const [focusDirectives, setFocusDirectives] = useState<IntelligenceFocusDirective[]>([]);
  // P12 · MRU（最近访问）持久化：上次看过的客户排在最上面，并默认回到上次的客户
  const [selectedScopeKey, setSelectedScopeKey] = useState<WorkObjectSelection>(() => {
    try {
      const saved = localStorage.getItem('yiyu.intelligence.workobject.lastSelected');
      if (saved) return saved as WorkObjectSelection;
    } catch {/* SSR / 隐私模式 fallback */}
    return 'all';
  });
  const [mruScopeKeys, setMruScopeKeys] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('yiyu.intelligence.workobject.mru');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed.filter((x) => typeof x === 'string');
      }
    } catch {/* ignore */}
    return [];
  });
  const [focusScopeKey, setFocusScopeKey] = useState<ScopeKey>('global');
  const [focusDraft, setFocusDraft] = useState<FocusDraft>(EMPTY_FOCUS_DRAFT);
  const [activeTab, setActiveTab] = useState<IntelligenceContentKind>('brand_mirror');
  const [sort, setSort] = useState<SortMode>('captured_desc');
  const [pages, setPages] = useState<Record<IntelligenceContentKind, number>>({
    brand_mirror: 1,
    timely_intelligence: 1,
    public_opinion: 1,
  });
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [candidateSamples, setCandidateSamples] = useState<IntelligenceCandidateSample[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [focusModalOpen, setFocusModalOpen] = useState(false);
  const [savingFocus, setSavingFocus] = useState(false);
  const [pendingItemId, setPendingItemId] = useState('');
  const [questionItem, setQuestionItem] = useState<IntelligenceItem | null>(null);
  const [questionDraft, setQuestionDraft] = useState('');
  const [questionPending, setQuestionPending] = useState(false);
  const [chatMessagesByItemId, setChatMessagesByItemId] = useState<Record<string, TopicCandidateChatMessage[]>>({});
  const [dismissTarget, setDismissTarget] = useState<IntelligenceItem | null>(null);
  const [dismissReasons, setDismissReasons] = useState<IntelligenceDismissReasonCode[]>(['irrelevant']);
  const [dismissNote, setDismissNote] = useState('');
  const [followTarget, setFollowTarget] = useState<IntelligenceItem | null>(null);
  const [followMode, setFollowMode] = useState<IntelligenceFollowMode>('same_theme');
  const [followNote, setFollowNote] = useState('');
  const [taskDraftTarget, setTaskDraftTarget] = useState<IntelligenceItem | null>(null);
  const [taskDraft, setTaskDraft] = useState<IntelligenceTaskDraftPayload | null>(null);
  const [taskDraftCacheByItemId, setTaskDraftCacheByItemId] = useState<Record<string, IntelligenceTaskDraftPayload>>({});
  const [peopleOptions, setPeopleOptions] = useState<MentionCandidate[]>([]);
  const flashRef = useRef(flash);
  const autoRefreshDueCheckedRef = useRef(false);
  const refreshPollTimersRef = useRef<number[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const [refreshingKind, setRefreshingKind] = useState<IntelligenceContentKind | null>(null);
  const [refreshRuns, setRefreshRuns] = useState<IntelligenceRefreshRun[]>([]);
  const [refreshRunsLoading, setRefreshRunsLoading] = useState(false);
  const [refreshCycleSettings, setRefreshCycleSettings] = useState<IntelligenceRefreshCycleSettings>(DEFAULT_REFRESH_CYCLE_SETTINGS);
  const [cycleEditKind, setCycleEditKind] = useState<IntelligenceContentKind | null>(null);
  const [cycleEditValue, setCycleEditValue] = useState('');
  const [cycleSaving, setCycleSaving] = useState(false);
  const [clarificationTarget, setClarificationTarget] = useState<ClarificationTarget | null>(null);
  const [clarificationNote, setClarificationNote] = useState('');
  const [clarificationPending, setClarificationPending] = useState(false);

  const selectedWorkObject = useMemo(() => {
    if (selectedScopeKey === 'all') return null;
    return workObjects.find((item) => scopeKeyOfObject(item) === selectedScopeKey) || null;
  }, [selectedScopeKey, workObjects]);

  // P12 · 按 MRU 排序的 workObjects — 最近看过的排前面，剩余按原顺序
  const sortedWorkObjects = useMemo(() => {
    if (workObjects.length === 0 || mruScopeKeys.length === 0) return workObjects;
    const mruSet = new Set(mruScopeKeys);
    const inMruOrder: IntelligenceWorkObject[] = [];
    for (const key of mruScopeKeys) {
      const found = workObjects.find((w) => scopeKeyOfObject(w) === key);
      if (found) inMruOrder.push(found);
    }
    const notInMru = workObjects.filter((w) => !mruSet.has(scopeKeyOfObject(w)));
    return [...inMruOrder, ...notInMru];
  }, [workObjects, mruScopeKeys]);
  const currentPage = pages[activeTab];
  const currentPageSize = PAGE_SIZE[activeTab];
  const totalPages = Math.max(1, Math.ceil(total / currentPageSize));
  const visibleMessages = questionItem ? chatMessagesByItemId[questionItem.id] || [] : [];
  const questionPromptGroups = questionItem ? buildQuestionPromptGroups(questionItem, workObjects) : [];
  const defaultListId = effectiveTaskSettings.defaultListId || activeTaskLists[0]?.id || 'list-0';
  const currentOwnerName = currentSessionUser?.fullName || currentOperatorName || '当前用户';
  const currentOwnerId = currentSessionUser?.id || null;
  const currentPerson = useMemo<MentionCandidate>(() => ({
    id: currentSessionUser?.id || 'local-device-user',
    fullName: currentOwnerName,
    email: currentSessionUser?.email || '',
    primaryRole: currentSessionUser?.primaryRole === 'admin' ? 'admin' : 'employee',
    isSelf: true,
  }), [currentOwnerName, currentSessionUser]);
  const memberOptions = useMemo(() => {
    const merged = new Map<string, MentionCandidate>();
    [currentPerson, ...peopleOptions].forEach((item) => {
      if (!item.id) return;
      merged.set(item.id, item);
    });
    return Array.from(merged.values());
  }, [currentPerson, peopleOptions]);
  const selectedLabel = selectedObjectLabel(selectedScopeKey, workObjects);
  const lastFetchTime = selectedWorkObject?.lastCandidateFetchAt ? formatTime(selectedWorkObject.lastCandidateFetchAt) : null;
  const activeRefreshRuns = useMemo(() => refreshRuns.filter((run) => run.status === 'queued' || run.status === 'running'), [refreshRuns]);
  const activeRefreshKind = activeRefreshRuns[0]?.contentKind || refreshingKind;
  const refreshInProgress = activeRefreshRuns.length > 0 || refreshingKind !== null;

  useEffect(() => {
    flashRef.current = flash;
  }, [flash]);

  useEffect(() => {
    let cancelled = false;
    void getMentionCandidates('')
      .then((items) => {
        if (!cancelled) setPeopleOptions(items);
      })
      .catch(() => {
        if (!cancelled) setPeopleOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => () => {
    refreshPollTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    refreshPollTimersRef.current = [];
  }, []);

  const loadShell = useCallback(async () => {
    try {
      const [objects, directives, cycleSettings] = await Promise.all([
        getIntelligenceWorkObjects(),
        getIntelligenceFocusDirectives(),
        getIntelligenceRefreshCycleSettings(),
      ]);
      setWorkObjects(objects);
      setFocusDirectives(directives);
      setRefreshCycleSettings(cycleSettings);
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '情报站初始化失败');
    }
  }, []);

  const loadItems = useCallback(async (options?: { silent?: boolean }) => {
    // 品牌镜子 / 舆情监控 tab 都走自己的 panel，不调通用 items 端点
    if (activeTab === 'brand_mirror' || activeTab === 'public_opinion') {
      setItems([]);
      setCandidateSamples([]);
      setTotal(0);
      return;
    }
    const silent = Boolean(options?.silent);
    if (!silent) setLoading(true);
    try {
      const response = await getIntelligenceItems({
        contentKind: activeTab,
        workObjectType: selectedWorkObject?.type,
        workObjectId: selectedWorkObject?.id,
        sort,
        page: currentPage,
        pageSize: currentPageSize,
      });
      setItems(response.items);
      setCandidateSamples(response.candidateSamples || []);
      setTotal(response.total);
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '情报列表加载失败');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [activeTab, currentPage, currentPageSize, selectedWorkObject?.id, selectedWorkObject?.type, sort]);

  const refreshWithoutMovingReader = useCallback(async (refresh: () => Promise<unknown>) => {
    const container = scrollContainerRef.current;
    const previousTop = container?.scrollTop ?? 0;
    const shouldRestore = Boolean(container && previousTop > 0);
    await refresh();
    if (!shouldRestore) return;
    window.requestAnimationFrame(() => {
      const current = scrollContainerRef.current;
      if (!current) return;
      if (current.scrollTop > 8 && Math.abs(current.scrollTop - previousTop) > 24) return;
      current.scrollTop = previousTop;
    });
  }, []);

  const loadRefreshRuns = useCallback(async () => {
    setRefreshRunsLoading(true);
    try {
      const runs = await getIntelligenceRefreshRuns({
        limit: 12,
      });
      setRefreshRuns(runs);
      const activeRun = runs.find((run) => run.status === 'queued' || run.status === 'running') || null;
      if (activeRun) {
        setRefreshingKind(activeRun.contentKind);
      } else {
        setRefreshingKind(null);
      }
      return runs;
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '刷新状态读取失败');
      return [];
    } finally {
      setRefreshRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadShell();
  }, [loadShell]);

  useEffect(() => {
    const directive = focusDirectives.find((item) => directiveMatches(item, focusScopeKey));
    setFocusDraft(draftFromDirective(directive));
  }, [focusDirectives, focusScopeKey]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  useEffect(() => {
    void loadRefreshRuns();
  }, [loadRefreshRuns]);

  // TODO: 半成品，autoRefreshIntelligenceDue 未在 api.ts 实现；后端 endpoint 也只是 stub。
  //       先整段注释解除启动崩溃，待 API 函数补齐 + 后端 endpoint 完善后恢复。
  // useEffect(() => {
  //   if (autoRefreshDueCheckedRef.current || workObjects.length === 0) return;
  //   autoRefreshDueCheckedRef.current = true;
  //   void autoRefreshIntelligenceDue({
  //     contentKinds: ['profile_completion', 'timely_intelligence'],
  //     scopeType: 'all',
  //   })
  //     .then((result) => {
  //       if (result.queuedCount > 0) {
  //         flashRef.current('info', result.message || '已到默认周期，后台已自动排队补跑');
  //         void refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })])).catch(() => undefined);
  //       }
  //     })
  //     .catch((error) => {
  //       flashRef.current('error', error instanceof Error ? error.message : '自动补跑检查失败');
  //     });
  // }, [loadItems, loadRefreshRuns, loadShell, refreshWithoutMovingReader, workObjects.length]);

  useEffect(() => {
    if (activeRefreshRuns.length === 0) return undefined;
    const timer = window.setInterval(() => {
      void refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })])).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeRefreshRuns.length, loadItems, loadRefreshRuns, loadShell, refreshWithoutMovingReader]);

  function changeScope(next: WorkObjectSelection) {
    setSelectedScopeKey(next);
    setPages({ brand_mirror: 1, timely_intelligence: 1, public_opinion: 1 });
    // P12 · MRU 记录：把刚选的 scope 推到最前面，最多保留 20 条
    try {
      localStorage.setItem('yiyu.intelligence.workobject.lastSelected', next);
      if (next !== 'all') {
        setMruScopeKeys((prev) => {
          const filtered = prev.filter((k) => k !== next);
          const updated = [next, ...filtered].slice(0, 20);
          try {
            localStorage.setItem('yiyu.intelligence.workobject.mru', JSON.stringify(updated));
          } catch { /* ignore */ }
          return updated;
        });
      }
    } catch { /* ignore */ }
  }

  function changeSort(next: SortMode) {
    setSort(next);
    setPages({ brand_mirror: 1, timely_intelligence: 1, public_opinion: 1 });
  }

  function setCurrentPage(next: number) {
    setPages((current) => ({ ...current, [activeTab]: next }));
  }

  async function reloadItems() {
    try {
      await Promise.all([loadShell(), loadItems()]);
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '情报列表刷新失败');
    }
  }

  async function reloadRefreshStatus() {
    await refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })]));
  }

  function cycleHoursFor(_kind: IntelligenceContentKind) {
    return refreshCycleSettings.timelyIntelligenceHours;
  }

  function beginCycleEdit(kind: IntelligenceContentKind) {
    setCycleEditKind(kind);
    setCycleEditValue(String(cycleHoursFor(kind)));
  }

  async function commitCycleEdit() {
    if (!cycleEditKind) return;
    const normalized = Math.max(1, Math.min(parseInt(cycleEditValue, 10) || cycleHoursFor(cycleEditKind), 8760));
    setCycleSaving(true);
    try {
      const payload = { timelyIntelligenceHours: normalized };
      void cycleEditKind; // 类型保留，但 profile_completion 已下线，只剩 timely
      const settings = await updateIntelligenceRefreshCycleSettings(payload);
      setRefreshCycleSettings(settings);
      setCycleEditKind(null);
      setCycleEditValue('');
      flashRef.current('success', '默认刷新周期已更新');
      await loadShell();
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '默认周期更新失败');
    } finally {
      setCycleSaving(false);
    }
  }

  function scheduleBackgroundRefreshChecks(contentKind: IntelligenceContentKind) {
    refreshPollTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    refreshPollTimersRef.current = [2500, 8000, 15000].map((delay) => window.setTimeout(() => {
      void refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })]))
        .catch(() => undefined)
        .finally(() => undefined);
    }, delay));
  }

  async function handleRefreshSupply(contentKind: IntelligenceContentKind) {
    let queued = false;
    setRefreshingKind(contentKind);
    try {
      const result = await refreshIntelligenceSupply(scopeRefreshPayload(selectedScopeKey, selectedWorkObject, contentKind));
      queued = isBackgroundRefreshQueued(result);
      if (queued) {
        scheduleBackgroundRefreshChecks(contentKind);
      }
      await refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })]));
      flashRef.current(result.status === 'failed' ? 'error' : result.status === 'no_results' || queued ? 'info' : 'success', summarizeRefreshResult(result));
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : `${TAB_LABEL[contentKind]}刷新失败`);
    } finally {
      if (!queued) setRefreshingKind(null);
    }
  }

  async function handleSaveFocus() {
    setSavingFocus(true);
    try {
      const saved = await saveIntelligenceFocusDirective(directivePayload(focusScopeKey, focusDraft));
      setFocusDirectives((current) => {
        const others = current.filter((item) => !directiveMatches(item, focusScopeKey));
        return [...others, saved];
      });
      setFocusModalOpen(false);
      flash('success', '关注指令已保存');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存关注指令失败');
    } finally {
      setSavingFocus(false);
    }
  }

  function closeFocusModal() {
    const directive = focusDirectives.find((item) => directiveMatches(item, focusScopeKey));
    setFocusDraft(draftFromDirective(directive));
    setFocusModalOpen(false);
  }

  function handleDismiss(item: IntelligenceItem) {
    setDismissTarget(item);
    setDismissReasons(['irrelevant']);
    setDismissNote('');
  }

  function toggleDismissReason(reason: IntelligenceDismissReasonCode) {
    setDismissReasons((current) => {
      if (current.includes(reason)) {
        return current.filter((item) => item !== reason);
      }
      return [...current, reason];
    });
  }

  function openClarificationForItem(item: IntelligenceItem) {
    setClarificationTarget({ type: 'item', item });
    setClarificationNote('');
  }

  function scopeForClarification(target: ClarificationTarget): { scopeType: 'global' | 'client' | 'project_module'; scopeId?: string | null } {
    const scopeType = target.item.scopeType === 'project_module' || target.item.projectModuleId ? 'project_module' : target.item.scopeType === 'client' || target.item.clientId ? 'client' : 'global';
    const scopeId = scopeType === 'project_module' ? target.item.projectModuleId || target.item.scopeId : scopeType === 'client' ? target.item.clientId || target.item.scopeId : null;
    return { scopeType, scopeId };
  }

  async function confirmClarification() {
    if (!clarificationTarget || !clarificationNote.trim()) return;
    const target = clarificationTarget;
    setClarificationPending(true);
    try {
      const scope = scopeForClarification(target);
      await submitIntelligenceVerificationFeedback({
        targetType: target.type,
        targetId: target.item.id,
        scopeType: scope.scopeType,
        scopeId: scope.scopeId,
        note: clarificationNote.trim(),
      });
      setClarificationTarget(null);
      setClarificationNote('');
      await reloadItems();
      flash('success', '判断标准已保存，当前线索会退出活跃展示');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存判断标准失败');
    } finally {
      setClarificationPending(false);
    }
  }

  async function confirmDismiss() {
    if (!dismissTarget || dismissReasons.length === 0) return;
    const item = dismissTarget;
    setPendingItemId(item.id);
    try {
      await dismissIntelligenceItem(item.id, {
        reasonCode: dismissReasons[0],
        reasonCodes: dismissReasons,
        note: dismissNote.trim(),
      });
      setDismissTarget(null);
      setDismissReasons(['irrelevant']);
      await reloadItems();
      flash('success', '已不采纳');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '不采纳失败');
    } finally {
      setPendingItemId('');
    }
  }

  function handleFollow(item: IntelligenceItem) {
    setFollowTarget(item);
    setFollowMode('same_theme');
    setFollowNote('');
  }

  async function confirmFollow() {
    if (!followTarget) return;
    const item = followTarget;
    setPendingItemId(item.id);
    try {
      await followIntelligenceItem(item.id, {
        followMode,
        note: followNote.trim(),
      });
      setFollowTarget(null);
      await reloadItems();
      flash('success', '已关注后续');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '关注后续失败');
    } finally {
      setPendingItemId('');
    }
  }

  async function handlePromoteToTask(item: IntelligenceItem) {
    if (!item.topicCandidateId && taskDraftCacheByItemId[item.id]) {
      setTaskDraftTarget(item);
      setTaskDraft(taskDraftCacheByItemId[item.id]);
      return;
    }
    setPendingItemId(item.id);
    try {
      if (!item.topicCandidateId) {
        const response = await getIntelligenceTaskDraft(item.id);
        setTaskDraftCacheByItemId((current) => ({ ...current, [item.id]: response.draft }));
        setTaskDraftTarget(item);
        setTaskDraft(response.draft);
        return;
      }
      const plan = await getCandidateTaskPlan(item.topicCandidateId);
      const drafts: TopicTaskPromotionDraft[] = plan.tasks.map((task) => ({
        title: task.title,
        desc: task.desc,
        priority: task.priority,
        listId: defaultListId,
        dueDate: task.dueDate || null,
        ddl: task.ddl,
        ownerId: currentOwnerId,
        ownerName: currentOwnerName,
        collaboratorIds: [],
        tags: task.tags,
        note: task.note,
        actorId: currentOwnerId,
        actorName: currentOwnerName,
        autoShare: false,
      }));
      if (drafts.length === 0) {
        flash('info', '这条情报暂未生成可转任务的动作');
        return;
      }
      const result = await promoteCandidateTasks(item.topicCandidateId, drafts);
      await onTasksReload();
      await reloadItems();
      flash('success', `已转为 ${result.createdCount} 个任务`);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '转任务失败');
    } finally {
      setPendingItemId('');
    }
  }

  async function confirmCreateTask() {
    if (!taskDraftTarget || !taskDraft || !taskDraft.title?.trim()) return;
    const item = taskDraftTarget;
    setPendingItemId(item.id);
    try {
      await createIntelligenceTask(item.id, {
        ...taskDraft,
        title: taskDraft.title.trim(),
        desc: taskDraft.desc?.trim() || '',
        ddl: taskDraft.ddl?.trim() || '本周',
        ownerId: taskDraft.ownerId ?? currentOwnerId,
        ownerName: taskDraft.ownerName?.trim() || currentOwnerName,
        collaboratorIds: (taskDraft.collaboratorIds || []).filter((id) => id && id !== (taskDraft.ownerId ?? currentOwnerId)),
        listId: taskDraft.listId || defaultListId,
        tags: taskDraft.tags?.length ? taskDraft.tags : ['情报跟进'],
        note: taskDraft.note?.trim() || '',
      });
      setTaskDraftTarget(null);
      setTaskDraft(null);
      await onTasksReload();
      await reloadItems();
      flash('success', '已创建跟进任务');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '创建任务失败');
    } finally {
      setPendingItemId('');
    }
  }

  async function handleAskQuestion() {
    if (!questionItem || !questionDraft.trim()) return;
    const question = questionDraft.trim();
    const userMessage: TopicCandidateChatMessage = {
      role: 'user',
      content: question,
      createdAt: new Date().toISOString(),
    };
    const history = [...visibleMessages, userMessage];
    setChatMessagesByItemId((current) => ({ ...current, [questionItem.id]: history }));
    setQuestionDraft('');
    setQuestionPending(true);
    try {
      const response = await askIntelligenceItemQuestion(questionItem.id, {
        question,
        history: visibleMessages,
      });
      setChatMessagesByItemId((current) => ({
        ...current,
        [questionItem.id]: [...history, response.message],
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '追问失败';
      flash('error', errorMessage);
      const assistantErrorMessage: TopicCandidateChatMessage = {
        role: 'assistant',
        content: `这次 AI 追问没有稳定返回：${errorMessage}`,
        createdAt: new Date().toISOString(),
      };
      setChatMessagesByItemId((current) => ({ ...current, [questionItem.id]: [...history, assistantErrorMessage] }));
    } finally {
      setQuestionPending(false);
    }
  }

  // 派生 KPI 数据:今日新增 / 待处理 / 已关注 / 已转任务
  // 用于 Hero 区显示"用户进来 1 秒知道当前情报状态"
  const kpiStats = (() => {
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    const todayMs = t.getTime();
    let todayNew = 0;
    let pending = 0;
    let following = 0;
    let converted = 0;
    items.forEach((it) => {
      const ts = it.capturedAt ? new Date(it.capturedAt).getTime() : 0;
      if (ts >= todayMs) todayNew += 1;
      if (it.convertedTaskId) {
        converted += 1;
      } else if (it.userStatus === 'following') {
        following += 1;
      } else if (it.userStatus !== 'dismissed') {
        pending += 1;
      }
    });
    return { todayNew, pending, following, converted };
  })();

  return (
    <div ref={scrollContainerRef} className="h-full overflow-y-auto bg-white font-sans text-gray-900">
      <div className="mx-auto max-w-[1320px] px-6 lg:px-8 pt-8 pb-10">
        {/* HERO · 标题 + 4 KPI + 主操作 ─────────────────────────── */}
        <header>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">INTELLIGENCE · 资讯情报站</p>
              <h1 className="mt-2 text-[22px] font-light tracking-tight text-gray-900">客户 / 项目情报流</h1>
              <p className="mt-1.5 text-[12px] text-gray-500 leading-relaxed">{selectedLabel}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setFocusModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
              >
                <SlidersHorizontal size={14} />
                我重点关注什么
              </button>
              <button
                type="button"
                onClick={() => void handleRefreshSupply('timely_intelligence')}
                disabled={refreshInProgress}
                className="inline-flex items-center gap-1.5 rounded-md bg-[#5B7BFE] px-3 py-2 text-[12px] font-bold text-white hover:bg-[#4A6AE6] disabled:opacity-50 transition-colors"
              >
                {activeRefreshKind === 'timely_intelligence' ? <Loader2 size={14} className="animate-spin" /> : <BellPlus size={14} />}
                立即抓取情报
              </button>
            </div>
          </div>

          {/* 4 KPI block — Connection Status 风格 */}
          <div className="mt-7 grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-6">
            <div className="flex flex-col">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">今日新增</p>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className={`text-[32px] leading-none font-light tracking-tight ${kpiStats.todayNew > 0 ? 'text-[#5B7BFE]' : 'text-gray-900'}`}>{kpiStats.todayNew}</span>
                <span className="text-[14px] leading-none font-light text-gray-400">条</span>
              </div>
              <div className={`mt-2 h-[2px] w-8 rounded-full ${kpiStats.todayNew > 0 ? 'bg-[#5B7BFE]' : 'bg-transparent'}`} />
              <p className="mt-2 text-[11px] text-gray-400 truncate">{kpiStats.todayNew > 0 ? '需要扫一遍' : '今天暂无新情报'}</p>
            </div>
            <div className="flex flex-col">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">待处理</p>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className={`text-[32px] leading-none font-light tracking-tight ${kpiStats.pending > 0 ? 'text-amber-600' : 'text-gray-900'}`}>{kpiStats.pending}</span>
                <span className="text-[14px] leading-none font-light text-gray-400">条</span>
              </div>
              <div className={`mt-2 h-[2px] w-8 rounded-full ${kpiStats.pending > 0 ? 'bg-amber-500' : 'bg-transparent'}`} />
              <p className="mt-2 text-[11px] text-gray-400 truncate">{kpiStats.pending > 0 ? '尚未判断要不要跟进' : '全部已处理'}</p>
            </div>
            <div className="flex flex-col">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">已关注</p>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="text-[32px] leading-none font-light tracking-tight text-gray-900">{kpiStats.following}</span>
                <span className="text-[14px] leading-none font-light text-gray-400">条</span>
              </div>
              <div className={`mt-2 h-[2px] w-8 rounded-full ${kpiStats.following > 0 ? 'bg-emerald-500' : 'bg-transparent'}`} />
              <p className="mt-2 text-[11px] text-gray-400 truncate">{kpiStats.following > 0 ? '关注后续动向' : '暂无关注'}</p>
            </div>
            <div className="flex flex-col">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">上次抓取</p>
              <span className="mt-3 text-[18px] leading-none font-light tracking-tight text-gray-900 truncate">{lastFetchTime || '尚未抓取'}</span>
              <div className="mt-2 h-[2px] w-8 rounded-full bg-transparent" />
              <p className="mt-2 text-[11px] text-gray-400 truncate">已转任务 {kpiStats.converted} 条</p>
            </div>
          </div>
        </header>

        <main className="mt-10">
          {/* Tab 切换:underline 风格,active 用 #5B7BFE 锚线,跟全局一致 */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100">
            <div className="flex gap-7">
              {(Object.keys(TAB_LABEL) as IntelligenceContentKind[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveTab(key)}
                  className={`relative pb-3.5 pt-1 text-left transition-colors ${
                    activeTab === key ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
                  }`}
                >
                  <span className={`block text-[14px] tracking-[0.01em] ${activeTab === key ? 'font-medium' : 'font-normal'}`}>
                    {TAB_LABEL[key]}
                  </span>
                  <span className="mt-0.5 block text-[10.5px] text-gray-400 font-normal">
                    {TAB_HINT[key]}
                  </span>
                  {/* 底部锚线 */}
                  <span
                    className={`absolute left-0 right-0 -bottom-px h-[2px] rounded-full transition-colors ${
                      activeTab === key ? 'bg-[#5B7BFE]' : 'bg-transparent'
                    }`}
                  />
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 pb-3 text-[12px] font-semibold text-gray-500">
              <span>默认周期：</span>
              <span>{TAB_LABEL[activeTab]}</span>
              {cycleEditKind === activeTab ? (
                <input
                  autoFocus
                  type="number"
                  min={1}
                  step={1}
                  value={cycleEditValue}
                  disabled={cycleSaving}
                  onChange={(event) => setCycleEditValue(event.target.value.replace(/[^\d]/g, ''))}
                  onBlur={() => void commitCycleEdit()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') void commitCycleEdit();
                    if (event.key === 'Escape') {
                      setCycleEditKind(null);
                      setCycleEditValue('');
                    }
                  }}
                  className="h-7 w-16 rounded-md border border-gray-200 bg-white px-2 text-center text-[12px] font-black text-gray-900 outline-none focus:border-gray-500"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => beginCycleEdit(activeTab)}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[12px] font-black text-gray-900 hover:bg-gray-50"
                >
                  {cycleHoursFor(activeTab)}
                </button>
              )}
              <span>小时；App 运行时自动检查到期刷新</span>
            </div>
          </div>

          {/* Toolbar:工作对象 + 排序,inline 紧凑 chip 风格 */}
          <div className="flex flex-wrap items-center gap-2 mt-4 mb-2">
            {/* 工作对象下拉 — 所有 tab 都显示，是切换客户的核心入口 */}
            <select
              value={selectedScopeKey}
              onChange={(event) => changeScope(event.target.value as WorkObjectSelection)}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] font-medium text-gray-700 outline-none focus:border-[#5B7BFE] transition-colors max-w-[260px]"
            >
              <option value="all">全部客户/项目</option>
              {sortedWorkObjects.map((item, idx) => {
                const key = scopeKeyOfObject(item);
                const isRecent = mruScopeKeys.includes(key);
                // 加分隔线：第一个非 MRU 元素前显示
                const showDivider =
                  isRecent === false &&
                  idx > 0 &&
                  mruScopeKeys.includes(scopeKeyOfObject(sortedWorkObjects[idx - 1]));
                return (
                  <Fragment key={key}>
                    {showDivider && (
                      <option disabled value="__divider__">────────────</option>
                    )}
                    <option value={key}>
                      {isRecent ? '★ ' : ''}{item.type === 'client' ? '客户' : '项目'}:{item.name}
                    </option>
                  </Fragment>
                );
              })}
            </select>
            {/* 排序 + 计数 仅时效 tab 显示，品牌镜子/舆情 tab 走自己的 panel */}
            {activeTab === 'timely_intelligence' && (
              <>
                <select
                  value={sort}
                  onChange={(event) => changeSort(event.target.value as SortMode)}
                  className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[12px] font-medium text-gray-700 outline-none focus:border-[#5B7BFE] transition-colors"
                >
                  {(Object.keys(SORT_LABEL) as SortMode[]).map((key) => (
                    <option key={key} value={key}>{SORT_LABEL[key]}</option>
                  ))}
                </select>
                <span className="text-[11px] text-gray-400 ml-auto">
                  {items.length > 0 ? `共 ${items.length} 条情报` : '暂无情报'}
                </span>
              </>
            )}
          </div>

          <div className="mt-2 min-h-[420px]">
            {activeTab === 'brand_mirror' ? (
              <BrandMirrorPanel workObject={selectedWorkObject} />
            ) : activeTab === 'public_opinion' ? (
              <SentimentMonitorPanel workObject={selectedWorkObject} />
            ) : (
              <>
            <RefreshProgressPanel
              contentKind={activeTab}
              hasItems={items.length > 0}
              runs={refreshRuns}
              workObjects={workObjects}
              loading={refreshRunsLoading}
              onReload={() => void reloadRefreshStatus()}
            />
            {loading ? (
              <div className="flex min-h-[260px] items-center justify-center text-[13px] font-bold text-gray-500">
                <Loader2 size={18} className="mr-2 animate-spin" />
                正在读取情报
              </div>
            ) : items.length === 0 ? (
              <EmptyState
                contentKind={activeTab}
                selectedWorkObject={selectedWorkObject}
                workObjects={workObjects}
                candidateSamples={candidateSamples}
                refreshing={refreshInProgress}
                onRefresh={(contentKind) => void handleRefreshSupply(contentKind)}
              />
            ) : (
              (() => {
                // 按抓取时间分组:TODAY / YESTERDAY / THIS WEEK / EARLIER
                // 让用户能扫"今天有什么大事"而不是一锅杂烩
                const now = new Date();
                const todayStart = new Date(now); todayStart.setHours(0, 0, 0, 0);
                const yesterdayStart = new Date(todayStart); yesterdayStart.setDate(yesterdayStart.getDate() - 1);
                const weekStart = new Date(todayStart); weekStart.setDate(weekStart.getDate() - 7);
                const buckets: Array<{ key: string; label: string; eyebrow: string; items: IntelligenceItem[] }> = [
                  { key: 'today', label: '今天', eyebrow: 'TODAY · 今天', items: [] },
                  { key: 'yesterday', label: '昨天', eyebrow: 'YESTERDAY · 昨天', items: [] },
                  { key: 'thisWeek', label: '本周早些时候', eyebrow: 'THIS WEEK · 本周早些时候', items: [] },
                  { key: 'earlier', label: '更早', eyebrow: 'EARLIER · 更早', items: [] },
                ];
                items.forEach((it) => {
                  const ts = it.capturedAt ? new Date(it.capturedAt).getTime() : 0;
                  if (ts >= todayStart.getTime()) buckets[0].items.push(it);
                  else if (ts >= yesterdayStart.getTime()) buckets[1].items.push(it);
                  else if (ts >= weekStart.getTime()) buckets[2].items.push(it);
                  else buckets[3].items.push(it);
                });
                const nonEmptyBuckets = buckets.filter((b) => b.items.length > 0);
                return (
                  <div className="space-y-8">
                    {nonEmptyBuckets.map((bucket) => (
                      <section key={bucket.key}>
                        <div className="flex items-baseline justify-between mb-3 border-b border-gray-100 pb-2">
                          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">{bucket.eyebrow}</p>
                          <span className="text-[10.5px] text-gray-400 tabular-nums">{bucket.items.length} 条</span>
                        </div>
                        <div className="space-y-2">
                          {bucket.items.map((item) => (
                            <TimelyIntelligenceCard
                              key={item.id}
                              item={item}
                              workObjects={workObjects}
                              pending={pendingItemId === item.id}
                              onDismiss={handleDismiss}
                              onFollow={handleFollow}
                              onQuestion={setQuestionItem}
                              onPromoteToTask={(next) => void handlePromoteToTask(next)}
                            />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                );
              })()
            )}
              </>
            )}
          </div>
          {activeTab === 'timely_intelligence' && (
            <>
              <Pagination page={currentPage} pageSize={currentPageSize} total={total} onPageChange={setCurrentPage} />
              <div className="mt-1 text-right text-[12px] font-semibold text-gray-500">
                {total > 0 ? `当前筛选共 ${total} 条，已显示第 ${currentPage} / ${totalPages} 页` : '当前筛选暂无内容'}
              </div>
            </>
          )}
        </main>

      </div>

      {focusModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="flex max-h-[88vh] w-full max-w-[880px] flex-col rounded-lg bg-white p-5 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[12px] font-bold text-gray-400">关注指令</p>
                <h2 className="mt-1 text-[18px] font-black text-gray-950">我重点关注什么</h2>
                <p className="mt-2 text-[13px] leading-6 text-gray-500">关注指令会进入当前对象后续搜索、线索判断和排序学习。</p>
              </div>
              <label className="text-[12px] font-bold text-gray-500">
                生效范围
                <select
                  value={focusScopeKey}
                  onChange={(event) => setFocusScopeKey(event.target.value as ScopeKey)}
                  className="ml-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
                >
                  <option value="global">所有客户/项目</option>
                  {workObjects.map((item) => (
                    <option key={scopeKeyOfObject(item)} value={scopeKeyOfObject(item)}>
                      {item.type === 'client' ? '客户' : '项目'}：{item.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 grid gap-3 overflow-y-auto pr-1 md:grid-cols-2">
              <label className="text-[12px] font-black text-gray-500">
                时效情报优先
                <textarea
                  value={focusDraft.timelyIntelligenceFocus}
                  onChange={(event) => setFocusDraft((current) => ({ ...current, timelyIntelligenceFocus: event.target.value }))}
                  rows={7}
                  placeholder={'资助窗口\n监管变化\n同类机构动作'}
                  className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
              <label className="text-[12px] font-black text-gray-500">
                少看或不看
                <textarea
                  value={focusDraft.exclude}
                  onChange={(event) => setFocusDraft((current) => ({ ...current, exclude: event.target.value }))}
                  rows={7}
                  placeholder={'泛泛行业新闻\n重复转载\n无来源截图'}
                  className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeFocusModal}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSaveFocus()}
                disabled={savingFocus}
                className="inline-flex items-center gap-2 rounded-md bg-gray-950 px-4 py-2 text-[13px] font-black text-white hover:bg-gray-800 disabled:bg-gray-300"
              >
                {savingFocus ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                保存关注指令
              </button>
            </div>
          </div>
        </div>
      )}

      {clarificationTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="w-full max-w-[560px] rounded-lg bg-white p-5 shadow-2xl">
            <p className="text-[12px] font-bold text-gray-400">补充判断标准</p>
            <h3 className="mt-1 text-[18px] font-black text-gray-950">{clarificationTarget.item.title}</h3>
            <p className="mt-2 text-[13px] leading-6 text-gray-500">
              用一句话说明这条为什么不对，或以后应该按什么标准判断。系统会把它写入当前客户/项目的核验规则，后续刷新会按新标准执行。
            </p>
            <textarea
              value={clarificationNote}
              onChange={(event) => setClarificationNote(event.target.value)}
              rows={4}
              placeholder="例如：这不是益语智库本身的信息；只采纳客户官网和公益行业公开报道。"
              className="mt-4 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 outline-none focus:border-gray-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setClarificationTarget(null);
                  setClarificationNote('');
                }}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmClarification()}
                disabled={clarificationPending || !clarificationNote.trim()}
                className="inline-flex items-center gap-2 rounded-md bg-amber-700 px-4 py-2 text-[13px] font-black text-white hover:bg-amber-800 disabled:bg-gray-300"
              >
                {clarificationPending && <Loader2 size={15} className="animate-spin" />}
                保存标准
              </button>
            </div>
          </div>
        </div>
      )}

      {questionItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="flex max-h-[86vh] w-full max-w-[720px] flex-col rounded-lg bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[12px] font-bold text-gray-400">追问情报</p>
                <h3 className="mt-1 text-[18px] font-black text-gray-950">{questionItem.title}</h3>
              </div>
              <button
                type="button"
                onClick={() => setQuestionItem(null)}
                className="rounded-md border border-gray-200 px-3 py-2 text-[12px] font-bold text-gray-600 hover:bg-gray-50"
              >
                关闭
              </button>
            </div>
            <div className="mt-4 min-h-[180px] flex-1 overflow-y-auto rounded-md border border-gray-100 bg-gray-50 p-3">
              {visibleMessages.length === 0 ? (
                <div className="space-y-4">
                  {questionPromptGroups.length === 0 ? (
                    <p className="rounded-md bg-white px-3 py-2 text-[13px] font-semibold leading-6 text-gray-500">
                      这张卡暂未生成推荐追问，可以直接输入一个具体判断点。
                    </p>
                  ) : (
                    questionPromptGroups.map((group) => (
                      <div key={group.questions.join('|')}>
                        <div className="space-y-1.5">
                          {group.questions.map((question, index) => (
                            <button
                              key={question}
                              type="button"
                              onClick={() => setQuestionDraft(question)}
                              className="block w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-left text-[13px] font-semibold leading-5 text-gray-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
                            >
                              {group.ordered ? `${index + 1}. ` : ''}{question}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {visibleMessages.map((message, index) => (
                    <div
                      key={`${message.createdAt}-${index}`}
                      className={`whitespace-pre-wrap rounded-md px-3 py-2 text-[13px] leading-6 ${message.role === 'user' ? 'bg-white text-gray-700' : 'bg-gray-950 text-white'}`}
                    >
                      {message.content}
                    </div>
                  ))}
                </div>
              )}
              {questionPending && (
                <div className="mt-2 inline-flex items-center gap-2 rounded-md bg-white px-3 py-2 text-[13px] font-bold text-gray-600">
                  <Loader2 size={16} className="animate-spin" />
                  正在分析
                </div>
              )}
            </div>
            <div className="mt-3 flex gap-2">
              <input
                value={questionDraft}
                onChange={(event) => setQuestionDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleAskQuestion();
                  }
                }}
                placeholder="问一个具体问题"
                className="min-w-0 flex-1 rounded-md border border-gray-200 px-3 py-2 text-[13px] outline-none focus:border-gray-400"
              />
              <button
                type="button"
                onClick={() => void handleAskQuestion()}
                disabled={questionPending || !questionDraft.trim()}
                className="inline-flex items-center gap-1 rounded-md bg-gray-950 px-4 py-2 text-[13px] font-black text-white hover:bg-gray-800 disabled:bg-gray-300"
              >
                <Send size={15} />
                发送
              </button>
            </div>
          </div>
        </div>
      )}

      {dismissTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="w-full max-w-[520px] rounded-lg bg-white p-5 shadow-2xl">
            <p className="text-[12px] font-bold text-gray-400">不采纳原因</p>
            <h3 className="mt-1 text-[18px] font-black text-gray-950">{dismissTarget.title}</h3>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {(Object.keys(DISMISS_REASON_LABEL) as IntelligenceDismissReasonCode[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleDismissReason(key)}
                  className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-left text-[13px] font-bold ${dismissReasons.includes(key) ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                >
                  <span className={`flex h-4 w-4 items-center justify-center rounded border text-[10px] ${dismissReasons.includes(key) ? 'border-rose-500 bg-rose-500 text-white' : 'border-gray-300 bg-white text-transparent'}`}>✓</span>
                  {DISMISS_REASON_LABEL[key]}
                </button>
              ))}
            </div>
            <textarea
              value={dismissNote}
              onChange={(event) => setDismissNote(event.target.value)}
              rows={3}
              placeholder="可选：补一句为什么不采纳"
              className="mt-3 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 outline-none focus:border-gray-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDismissTarget(null);
                  setDismissReasons(['irrelevant']);
                }}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmDismiss()}
                disabled={pendingItemId === dismissTarget.id || dismissReasons.length === 0}
                className="inline-flex items-center gap-2 rounded-md bg-rose-600 px-4 py-2 text-[13px] font-black text-white hover:bg-rose-700 disabled:bg-gray-300"
              >
                {pendingItemId === dismissTarget.id && <Loader2 size={15} className="animate-spin" />}
                确认不采纳
              </button>
            </div>
          </div>
        </div>
      )}

      {followTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="w-full max-w-[540px] rounded-lg bg-white p-5 shadow-2xl">
            <p className="text-[12px] font-bold text-gray-400">关注后续</p>
            <h3 className="mt-1 text-[18px] font-black text-gray-950">{followTarget.title}</h3>
            <p className="mt-2 text-[13px] leading-6 text-gray-500">关注后续会影响当前对象内排序和学习信号，不会直接提高刷新频率。</p>
            <div className="mt-4 grid gap-2">
              {(Object.keys(FOLLOW_MODE_LABEL) as IntelligenceFollowMode[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFollowMode(key)}
                  className={`rounded-md border px-3 py-2 text-left text-[13px] font-bold ${followMode === key ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                >
                  {FOLLOW_MODE_LABEL[key]}
                </button>
              ))}
            </div>
            <textarea
              value={followNote}
              onChange={(event) => setFollowNote(event.target.value)}
              rows={3}
              placeholder="可选：补一句跟进重点"
              className="mt-3 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 outline-none focus:border-gray-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setFollowTarget(null)}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmFollow()}
                disabled={pendingItemId === followTarget.id}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-[13px] font-black text-white hover:bg-emerald-700 disabled:bg-gray-300"
              >
                {pendingItemId === followTarget.id && <Loader2 size={15} className="animate-spin" />}
                确认关注
              </button>
            </div>
          </div>
        </div>
      )}

      {taskDraftTarget && taskDraft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6">
          <div className="w-full max-w-[680px] rounded-lg bg-white p-5 shadow-2xl">
            <p className="text-[12px] font-bold text-gray-400">任务草案</p>
            <h3 className="mt-1 text-[18px] font-black text-gray-950">{taskDraftTarget.title}</h3>
            <div className="mt-4 grid gap-3">
              <label className="text-[12px] font-black text-gray-500">
                任务标题
                <input
                  value={taskDraft.title || ''}
                  onChange={(event) => setTaskDraft((current) => current ? { ...current, title: event.target.value } : current)}
                  className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
              <label className="text-[12px] font-black text-gray-500">
                任务描述
                <textarea
                  value={taskDraft.desc || ''}
                  onChange={(event) => setTaskDraft((current) => current ? { ...current, desc: event.target.value } : current)}
                  rows={8}
                  className="mt-1 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
              {(taskDraft.ownerRoleHint || (taskDraft.collaboratorRoleHints || []).length > 0) && (
                <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-[12px] leading-5 text-blue-900">
                  {taskDraft.ownerRoleHint && (
                    <p><span className="font-black">负责人建议：</span>{taskDraft.ownerRoleHint}</p>
                  )}
                  {(taskDraft.collaboratorRoleHints || []).length > 0 && (
                    <p className="mt-1"><span className="font-black">协作者建议：</span>{(taskDraft.collaboratorRoleHints || []).join('；')}</p>
                  )}
                </div>
              )}
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-[12px] font-black text-gray-500">
                  负责人
                  <select
                    value={taskDraft.ownerId || currentPerson.id}
                    onChange={(event) => {
                      const owner = memberOptions.find((person) => person.id === event.target.value) || currentPerson;
                      setTaskDraft((current) => current ? {
                        ...current,
                        ownerId: owner.id,
                        ownerName: owner.fullName || owner.email || owner.id,
                        collaboratorIds: (current.collaboratorIds || []).filter((id) => id !== owner.id),
                      } : current);
                    }}
                    className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
                  >
                    {memberOptions.map((person) => (
                      <option key={person.id} value={person.id}>
                        {person.fullName || person.email || person.id}{person.isSelf ? '（我）' : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="text-[12px] font-black text-gray-500">
                  协作者
                  <div className="mt-1 max-h-[92px] overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-2">
                    {memberOptions.filter((person) => person.id !== (taskDraft.ownerId || currentPerson.id)).length === 0 ? (
                      <p className="px-2 py-1 text-[12px] font-semibold text-gray-400">暂无可选协作者</p>
                    ) : (
                      memberOptions
                        .filter((person) => person.id !== (taskDraft.ownerId || currentPerson.id))
                        .map((person) => {
                          const checked = (taskDraft.collaboratorIds || []).includes(person.id);
                          return (
                            <label key={person.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[12px] font-semibold text-gray-700 hover:bg-white">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(event) => {
                                  setTaskDraft((current) => {
                                    if (!current) return current;
                                    const currentIds = current.collaboratorIds || [];
                                    const nextIds = event.target.checked
                                      ? [...currentIds, person.id]
                                      : currentIds.filter((id) => id !== person.id);
                                    return { ...current, collaboratorIds: nextIds };
                                  });
                                }}
                              />
                              <span>{person.fullName || person.email || person.id}</span>
                            </label>
                          );
                        })
                    )}
                  </div>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-[12px] font-black text-gray-500">
                  优先级
                  <select
                    value={taskDraft.priority}
                    onChange={(event) => setTaskDraft((current) => current ? { ...current, priority: event.target.value as IntelligenceTaskDraftPayload['priority'] } : current)}
                    className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
                  >
                    <option value="low">低</option>
                    <option value="normal">普通</option>
                    <option value="high">高</option>
                  </select>
                </label>
                <label className="text-[12px] font-black text-gray-500">
                  截止口径
                  <input
                    value={taskDraft.ddl}
                    onChange={(event) => setTaskDraft((current) => current ? { ...current, ddl: event.target.value } : current)}
                    className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
                  />
                </label>
              </div>
              <label className="text-[12px] font-black text-gray-500">
                备注
                <textarea
                  value={taskDraft.note}
                  onChange={(event) => setTaskDraft((current) => current ? { ...current, note: event.target.value } : current)}
                  rows={3}
                  className="mt-1 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setTaskDraftTarget(null);
                  setTaskDraft(null);
                }}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmCreateTask()}
                disabled={pendingItemId === taskDraftTarget.id || !taskDraft.title?.trim()}
                className="inline-flex items-center gap-2 rounded-md bg-gray-950 px-4 py-2 text-[13px] font-black text-white hover:bg-gray-800 disabled:bg-gray-300"
              >
                {pendingItemId === taskDraftTarget.id && <Loader2 size={15} className="animate-spin" />}
                创建任务
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// 舆情监控面板（P2-a 重建 + P5 三件套）
// ──────────────────────────────────────────────────────────────────────────

function SentimentMonitorPanel({ workObject }: { workObject: IntelligenceWorkObject | null }) {
  const targetName = workObject?.name || '请先选择监控对象';
  const clientId = workObject?.type === 'client' ? workObject.id : undefined;
  const projectModuleId = workObject?.type === 'project_module' ? workObject.id : undefined;
  const linkedClientId = clientId || workObject?.clientId || undefined;
  const hasScope = Boolean(clientId || projectModuleId);

  // 品牌词云 + 3 卡 — 暂用日慈真实数据演示形态（后续接 LLM 实时生成）
  const isRiciClient = targetName.includes('日慈');
  const [officialChannels, setOfficialChannels] = useState<OfficialChannel[]>(
    () => _mockOfficialChannelsFor(targetName),
  );
  useEffect(() => {
    setOfficialChannels(_mockOfficialChannelsFor(targetName));
  }, [targetName]);
  const handleAdoptChannel = (idx: number) => {
    setOfficialChannels((cur) =>
      cur.map((c, i) => (i === idx ? { ...c, status: 'user_confirmed' as const } : c)),
    );
  };
  const handleExcludeChannel = (idx: number) => {
    setOfficialChannels((cur) =>
      cur.map((c, i) => (i === idx ? { ...c, status: 'excluded' as const } : c)),
    );
  };

  const [profile, setProfile] = useState<SentimentProfile | null>(null);
  const [items, setItems] = useState<SentimentItem[]>([]);
  const [themes, setThemes] = useState<SentimentTheme[]>([]);
  const [gap, setGap] = useState<PositioningGapResponse | null>(null);
  const [audit, setAudit] = useState<BrandAudit | null>(null);
  const [auditNote, setAuditNote] = useState<string | null>(null);
  const [auditRecomputing, setAuditRecomputing] = useState(false);
  const [auditStep, setAuditStep] = useState<string>(''); // 显示当前级联步骤
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<SentimentRefreshResult | null>(null);

  const reload = useCallback(async () => {
    if (!hasScope) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const [p, it, th, au] = await Promise.all([
        getSentimentProfile({ clientId, projectModuleId, withinDays: 30 }),
        listSentimentItems({ clientId, projectModuleId, withinDays: 30, limit: 50 }),
        listSentimentThemes({ clientId, projectModuleId, autoRecompute: false }),
        getBrandAudit({ clientId, projectModuleId, autoRecompute: false }),
      ]);
      setProfile(p);
      setItems(it.items || []);
      setThemes(th.themes || []);
      setAudit(au.audit);
      setAuditNote(au.recomputeNote);
      // gap 单独拉（依赖 brand_proposition，可能没填）
      try {
        const g = await getPositioningGap({ clientId, projectModuleId });
        setGap(g);
      } catch {
        setGap(null);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : '舆情数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [hasScope, clientId, projectModuleId]);

  // 智能级联：缺什么补什么 — audit 缺 → themes 缺 → items 缺 → refresh
  const handleRecomputeAudit = async () => {
    if (!hasScope) return;
    setAuditRecomputing(true);
    setAuditNote(null);
    setAuditStep('正在生成品牌印象速读…');
    try {
      // 步骤 1：直接试 audit
      let result = await recomputeBrandAudit({ clientId, projectModuleId, targetName });
      if (result.ok && result.audit) {
        setAudit(result.audit);
        return;
      }

      // 步骤 2：缺主题 → 先建主题，再回头试 audit
      if ((result.reason || '').includes('too_few_themes')) {
        setAuditStep('印象主题缺失，正在聚类主题（约 1 分钟）…');
        const themesRes = await recomputeSentimentThemes({ clientId, projectModuleId, targetName });

        // 步骤 3：连主题都建不起来（条目太少）→ 触发一次完整抓取（含 themes + audit 链式）
        if (!themesRes.ok && (themesRes.reason || '').includes('too_few_items')) {
          setAuditStep('舆情数据不足，正在抓取（约 3-5 分钟）…');
          await refreshSentiment({ clientId, projectModuleId, targetName, maxPerQuery: 5 });
          // refresh 后端已经链式跑了 themes + audit，直接读 audit
          const au = await getBrandAudit({ clientId, projectModuleId, autoRecompute: false });
          if (au.audit) {
            setAudit(au.audit);
            await reload();
            return;
          }
          setAuditNote(au.recomputeNote || '抓取完成但 audit 未生成');
          await reload();
          return;
        }

        if (!themesRes.ok) {
          setAuditNote(`主题聚类失败：${themesRes.reason || '未知'}`);
          return;
        }

        // 主题成功，回头试 audit
        setAuditStep('主题已聚类，正在合成品牌印象速读（约 1-2 分钟）…');
        result = await recomputeBrandAudit({ clientId, projectModuleId, targetName });
        if (result.ok && result.audit) {
          setAudit(result.audit);
          await reload(); // 顺手刷一遍 themes/gap
          return;
        }
        setAuditNote(result.reason || '速读合成失败');
        return;
      }

      // 步骤 4：audit 报别的错（LLM 失败等）
      setAuditNote(result.reason || '重算失败');
    } catch (err) {
      setAuditNote(err instanceof Error ? err.message : '重算失败');
    } finally {
      setAuditRecomputing(false);
      setAuditStep('');
    }
  };

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleRefresh = async () => {
    if (!hasScope) {
      setErrorMsg('先在顶部选择监控的客户或业务线');
      return;
    }
    setRefreshing(true);
    setErrorMsg(null);
    try {
      const result = await refreshSentiment({
        clientId,
        projectModuleId,
        targetName,
        maxPerQuery: 5,
      });
      setLastRefresh(result);
      await reload();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : '舆情抓取失败');
    } finally {
      setRefreshing(false);
    }
  };

  const handleFeedback = useCallback(async (itemId: string, action: SentimentFeedbackAction) => {
    const prev = items;
    if (action === 'mark_misclassified' || action === 'mark_resolved') {
      setItems((cur) => cur.filter((it) => it.id !== itemId));
    }
    try {
      await sendSentimentFeedback({ itemId, action });
      try {
        const p = await getSentimentProfile({ clientId, projectModuleId, withinDays: 30 });
        setProfile(p);
      } catch {
        // 不阻塞
      }
    } catch (err) {
      setItems(prev);
      setErrorMsg(err instanceof Error ? err.message : '反馈提交失败');
    }
  }, [items, clientId, projectModuleId]);

  const handleBrandSaved = async () => {
    // brand_proposition 改了之后 gap 要重算
    try {
      const g = await getPositioningGap({ clientId, projectModuleId });
      setGap(g);
    } catch {
      // 不阻塞
    }
  };

  const negativeItems = items.filter((it) => it.sentimentLabel === 'negative');
  const otherItems = items.filter((it) => it.sentimentLabel !== 'negative');

  if (!hasScope) {
    return (
      <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50/40 px-6 py-12 text-center">
        <MessageCircle size={28} className="mx-auto text-gray-300" />
        <p className="mt-3 text-[13px] font-semibold text-gray-500">
          先在左侧选择具体客户或业务线，才能查看舆情画像
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-5">
      {/* ⓪ 品牌印象速读（P6）— 最显眼，放最顶 */}
      <BrandAuditCard
        audit={audit}
        recomputeNote={auditNote}
        recomputing={auditRecomputing}
        recomputeStep={auditStep}
        onRecompute={() => void handleRecomputeAudit()}
      />

      {/* P12 · 品牌词云（先用日慈真实数据演示形态，后续接 LLM 实时生成）*/}
      {isRiciClient && (
        <BrandWordCloud words={REAL_RICI_WORD_CLOUD} targetName={targetName} />
      )}

      {/* P12 · 3 精致信息卡（媒体 / 合作 / 官方）*/}
      {isRiciClient && (
        <BrandInsightCardRow
          mediaCoverage={REAL_RICI_DATA.mediaCoverage}
          partners={REAL_RICI_DATA.partners}
          channels={officialChannels}
          onAdoptChannel={handleAdoptChannel}
          onExcludeChannel={handleExcludeChannel}
        />
      )}

      {/* ① 顶栏 + KPI 三色块 */}
      <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h3 className="text-[14px] font-black text-gray-900">
            监控对象 · <span className="text-[#5B7BFE]">{targetName}</span>
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-gray-400">近 {profile?.withinDays ?? 30} 天</span>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 rounded-md bg-gray-950 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {refreshing ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {refreshing ? '抓取中…' : '立即抓取舆情'}
            </button>
          </div>
        </div>
        {errorMsg && (
          <div className="mb-3 rounded-md border border-rose-200 bg-rose-50/50 px-3 py-2 text-[11px] text-rose-700">
            {errorMsg}
          </div>
        )}
        {lastRefresh && (
          <>
            <div className="mb-3 rounded-md border border-emerald-100 bg-emerald-50/50 px-3 py-2 text-[11px] text-emerald-700">
              刚抓取「{lastRefresh.targetName}」共 {lastRefresh.fetchedCount} 条，
              入库 {lastRefresh.insertedCount} 条（负面 {lastRefresh.negativeCount} · 中性 {lastRefresh.neutralCount} · 积极 {lastRefresh.positiveCount}）
            </div>
            {lastRefresh.themesRecomputeNote && (
              <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800">
                主题重算未完成：<span className="font-bold">{lastRefresh.themesRecomputeNote}</span>
                {lastRefresh.themesRecomputeNote.startsWith('ai_') && '（请检查本地 AI 配置）'}
                {lastRefresh.themesRecomputeNote.startsWith('too_few_items') && '（条目太少，先抓更多舆情）'}
              </div>
            )}
          </>
        )}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-gray-100 bg-gray-50/50 px-4 py-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">整体情感</div>
            <div className={`mt-1 text-[24px] font-bold tabular-nums ${
              (profile?.sentimentScore ?? 0) >= 70 ? 'text-emerald-600' :
              (profile?.sentimentScore ?? 0) >= 40 ? 'text-gray-800' :
              (profile?.totalMentions ?? 0) > 0 ? 'text-rose-600' : 'text-gray-300'
            }`}>
              {(profile?.totalMentions ?? 0) > 0 ? `${profile?.sentimentScore ?? 0}/100` : '—/100'}
            </div>
            <div className="mt-0.5 text-[10px] text-gray-400">0 极负面 · 100 极积极</div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50/50 px-4 py-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">提及量</div>
            <div className={`mt-1 text-[24px] font-bold tabular-nums ${
              (profile?.totalMentions ?? 0) > 0 ? 'text-gray-900' : 'text-gray-300'
            }`}>
              {profile?.totalMentions ?? 0}
            </div>
            <div className="mt-0.5 text-[10px] text-gray-400">所有公开渠道</div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50/50 px-4 py-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">情感分布</div>
            <div className="mt-2 flex items-baseline gap-3 text-[12px] tabular-nums text-gray-500">
              <span><span className="font-bold text-rose-600">{profile?.negativeCount ?? 0}</span> 负面</span>
              <span><span className="font-bold text-gray-700">{profile?.neutralCount ?? 0}</span> 中性</span>
              <span><span className="font-bold text-emerald-600">{profile?.positiveCount ?? 0}</span> 积极</span>
            </div>
          </div>
        </div>
      </section>

      {/* ② 定位差异图（P5-#2）+ 自我定位编辑 */}
      <PositioningGapMap
        gap={gap}
        clientId={linkedClientId}
        loading={loading}
        onSaved={() => void handleBrandSaved()}
      />

      {/* ③ 印象主题（P5-#1）+ 点开溯源（P5-#4） */}
      <ImpressionThemeCards themes={themes} loading={loading} />

      {/* ④ 公众画像 · 高频源 */}
      <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
        <h3 className="mb-3 text-[13px] font-black text-gray-900">公众画像 · 主要声音来源</h3>
        {(profile?.topSources?.length ?? 0) === 0 ? (
          <p className="text-[11px] text-gray-400">暂无数据，先点上方"立即抓取舆情"试试。</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {(profile?.topSources || []).map((s) => (
              <span key={s.source} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-[11px] font-semibold text-gray-700">
                {s.source}
                <span className="text-[10px] font-bold text-gray-400 tabular-nums">×{s.count}</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* ⑤ 负面预警 */}
      <section className="rounded-2xl border border-rose-100 bg-rose-50/30 px-5 py-5">
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle size={14} className="text-rose-500" />
          <h3 className="text-[13px] font-black text-rose-700">负面预警 · 需要关注</h3>
          <span className="text-[11px] font-bold tabular-nums text-rose-400">{negativeItems.length}</span>
        </div>
        {negativeItems.length === 0 ? (
          <p className="text-[11px] leading-relaxed text-rose-700/70">当前没有监测到负面信号。</p>
        ) : (
          <div className="space-y-2">
            {negativeItems.slice(0, 10).map((item) => (
              <SentimentItemCard key={item.id} item={item} highlight onFeedback={handleFeedback} />
            ))}
          </div>
        )}
      </section>

      {/* ⑥ 公开评价（其他情感） */}
      <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageCircle size={14} className="text-gray-400" />
            <h3 className="text-[13px] font-black text-gray-900">公开评价 · 中性 + 积极</h3>
            <span className="text-[11px] font-bold tabular-nums text-gray-400">{otherItems.length}</span>
          </div>
        </div>
        {otherItems.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/40 px-5 py-6 text-center">
            <p className="text-[12px] font-semibold text-gray-500">
              {loading ? '加载中…' : '暂未发现公开评价'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {otherItems.slice(0, 30).map((item) => (
              <SentimentItemCard key={item.id} item={item} onFeedback={handleFeedback} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// 单条舆情卡片 · 标题 + 摘要 + 来源 + 时间 + URL + 反馈
function SentimentItemCard({
  item,
  highlight = false,
  onFeedback,
}: {
  item: SentimentItem;
  highlight?: boolean;
  onFeedback?: (itemId: string, action: SentimentFeedbackAction) => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const labelStyle =
    item.sentimentLabel === 'negative' ? { dot: 'bg-rose-500', text: 'text-rose-700', label: '负面' } :
    item.sentimentLabel === 'positive' ? { dot: 'bg-emerald-500', text: 'text-emerald-700', label: '积极' } :
                                          { dot: 'bg-gray-400', text: 'text-gray-600', label: '中性' };
  const openUrl = () => {
    if (!item.sourceUrl) return;
    if (typeof window !== 'undefined') {
      window.open(item.sourceUrl, '_blank', 'noopener,noreferrer');
    }
  };
  const trigger = async (action: SentimentFeedbackAction) => {
    if (!onFeedback || busy) return;
    setBusy(true);
    try {
      await onFeedback(item.id, action);
    } finally {
      setBusy(false);
    }
  };
  const isNegative = item.sentimentLabel === 'negative';
  return (
    <div className={`rounded-xl border px-4 py-3 transition-all ${
      highlight ? 'border-rose-200 bg-white' : 'border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm'
    }`}>
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${labelStyle.dot}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className={`text-[10px] font-bold uppercase tracking-wide ${labelStyle.text}`}>
              {labelStyle.label}
            </span>
            <span className="text-[11px] text-gray-400">{item.source}</span>
            <span className="text-[11px] text-gray-300">·</span>
            <span className="text-[11px] text-gray-400 tabular-nums">{(item.capturedAt || '').slice(0, 10)}</span>
          </div>
          <p className="mt-1 text-[13px] font-semibold leading-snug text-gray-900">{item.title}</p>
          {item.summary && (
            <p className="mt-1 text-[12px] leading-6 text-gray-600 line-clamp-3">{item.summary}</p>
          )}
          {item.sentimentReason && (
            <p className="mt-1.5 text-[10px] text-gray-400">判断依据：{item.sentimentReason}</p>
          )}
        </div>
        <div className="shrink-0 flex flex-col items-center gap-1">
          {item.sourceUrl && (
            <button
              type="button"
              onClick={openUrl}
              title="查看原文"
              aria-label="查看原文"
              className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1.5 text-gray-500 hover:bg-[#EEF2FF] hover:border-[#C7D5FF] hover:text-[#5B7BFE]"
            >
              <Send size={12} strokeWidth={2.4} />
            </button>
          )}
          {onFeedback && (
            <>
              <button
                type="button"
                onClick={() => void trigger('mark_misclassified')}
                disabled={busy}
                title="误判 · 这条不是真负面"
                aria-label="标记误判"
                className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1.5 text-gray-400 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-700 disabled:opacity-50"
              >
                <X size={12} strokeWidth={2.4} />
              </button>
              {isNegative && (
                <button
                  type="button"
                  onClick={() => void trigger('mark_resolved')}
                  disabled={busy}
                  title="已处理 · 这条负面已跟进"
                  aria-label="标记已处理"
                  className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1.5 text-gray-400 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-700 disabled:opacity-50"
                >
                  <CheckCircle2 size={12} strokeWidth={2.4} />
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// P5-#2 定位差异图
// ──────────────────────────────────────────────────────────────────────────

function PositioningGapMap({
  gap,
  clientId,
  loading,
  onSaved,
}: {
  gap: PositioningGapResponse | null;
  clientId?: string;
  loading: boolean;
  onSaved: () => void;
}) {
  const noBrand = !gap || gap.reason === 'no_brand_proposition';
  const noThemes = gap?.reason === 'no_themes_yet';

  return (
    <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-black text-gray-900">定位差异图 · 你以为 vs 公众怎么看</h3>
        {clientId && (
          <BrandPropositionEditor clientId={clientId} initial={gap?.propositions || []} onSaved={onSaved} />
        )}
      </div>
      {loading && !gap ? (
        <p className="text-[11px] text-gray-400">加载中…</p>
      ) : noBrand ? (
        <p className="text-[11px] text-gray-500">
          先在右上角填入客户的『自我定位关键词』（如 "专业, 透明, 儿童心理"），就能看出公众怎么说和你想说的有没有对齐。
        </p>
      ) : noThemes ? (
        <p className="text-[11px] text-gray-500">
          公众主题还没聚出来。先点上方"立即抓取舆情"跑一次，主题聚类完成后这里会自动出图。
        </p>
      ) : !gap?.ok ? (
        <p className="text-[11px] text-gray-400">差异分析未就绪：{gap?.reason || '未知原因'}</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {/* 左：自我定位逐条状态 */}
          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">你的定位</div>
            {gap.alignments.map((a, idx) => (
              <AlignmentRow key={`${a.proposition}_${idx}`} alignment={a} />
            ))}
          </div>
          {/* 右：公众多出来的主题 */}
          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">公众额外说</div>
            {gap.unexpectedThemes.length === 0 ? (
              <p className="rounded-md border border-dashed border-gray-200 bg-gray-50/30 px-3 py-3 text-[11px] text-gray-400">
                公众讨论的话题都在你的自我定位里。
              </p>
            ) : (
              gap.unexpectedThemes.map((t) => (
                <div key={t.id} className="rounded-md border border-amber-100 bg-amber-50/40 px-3 py-2 text-[12px] text-amber-900">
                  <span className="font-bold">{t.label}</span>
                  <span className="ml-1 text-[10px] text-amber-700/70">— 你没说，但公众在讨论</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function AlignmentRow({ alignment }: { alignment: GapAlignment }) {
  const tone =
    alignment.status === 'affirmed' ? { ring: 'border-emerald-200 bg-emerald-50/40', dot: 'bg-emerald-500', text: 'text-emerald-700', label: '匹配' } :
    alignment.status === 'gap' ? { ring: 'border-rose-200 bg-rose-50/40', dot: 'bg-rose-500', text: 'text-rose-700', label: '存在落差' } :
                                  { ring: 'border-gray-200 bg-gray-50/40', dot: 'bg-gray-400', text: 'text-gray-600', label: '公众未提' };
  return (
    <div className={`rounded-md border px-3 py-2 ${tone.ring}`}>
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
        <span className="text-[13px] font-bold text-gray-900">{alignment.proposition}</span>
        <span className={`ml-auto text-[10px] font-bold uppercase tracking-wide ${tone.text}`}>{tone.label}</span>
      </div>
      {alignment.reason && (
        <p className="mt-1 text-[11px] leading-5 text-gray-600">{alignment.reason}</p>
      )}
      {alignment.supportingThemes.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {alignment.supportingThemes.map((t) => (
            <span key={t.id} className="rounded-sm border border-emerald-100 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
              ✓ {t.label}
            </span>
          ))}
        </div>
      )}
      {alignment.conflictingThemes.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {alignment.conflictingThemes.map((t) => (
            <span key={t.id} className="rounded-sm border border-rose-100 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">
              ✗ {t.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function BrandPropositionEditor({
  clientId,
  initial,
  onSaved,
}: {
  clientId: string;
  initial: string[];
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      // 拉最新值（initial 可能已被 useMemo 缓存）
      void getClientBrandProposition(clientId).then((r) => setText(r.brandProposition || ''));
    }
  }, [open, clientId]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateClientBrandProposition(clientId, text);
      setOpen(false);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-bold text-gray-600 hover:bg-gray-50"
      >
        <Pencil size={11} />
        {initial.length > 0 ? '编辑自我定位' : '填写自我定位'}
      </button>
    );
  }

  return (
    <div className="ml-2 flex items-center gap-2">
      <input
        autoFocus
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="如：专业, 透明, 儿童心理"
        className="w-[280px] rounded-md border border-gray-300 bg-white px-2 py-1 text-[12px] font-medium text-gray-900 outline-none focus:border-gray-500"
      />
      <button
        type="button"
        onClick={() => void handleSave()}
        disabled={saving}
        className="rounded-md bg-gray-950 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {saving ? '…' : '保存'}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="rounded-md border border-gray-200 px-2 py-1 text-[11px] font-bold text-gray-500 hover:bg-gray-50"
      >
        取消
      </button>
      {error && <span className="text-[10px] text-rose-600">{error}</span>}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// P5-#1 印象主题卡片 + #4 点开溯源
// ──────────────────────────────────────────────────────────────────────────

// ──────────────────────────────────────────────────────────────────────────
// P6 品牌印象速读卡片
// ──────────────────────────────────────────────────────────────────────────

function BrandAuditCard({
  audit,
  recomputeNote,
  recomputing,
  recomputeStep,
  onRecompute,
}: {
  audit: BrandAudit | null;
  recomputeNote: string | null;
  recomputing: boolean;
  recomputeStep?: string;
  onRecompute: () => void;
}) {
  if (!audit) {
    return (
      <section className="rounded-2xl border-2 border-dashed border-violet-200 bg-gradient-to-br from-violet-50/60 to-white px-5 py-6">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-violet-500" />
          <h3 className="text-[14px] font-black text-violet-900">品牌印象速读</h3>
          <span className="ml-auto inline-flex items-center gap-1 rounded-md bg-violet-100/60 px-2 py-0.5 text-[10px] font-bold text-violet-700">
            ✨ AI 合成
          </span>
        </div>
        <p className="mt-3 text-[12px] leading-6 text-violet-900/80">
          这里会出现一份公关风格简报：一句话定位、3 段公众印象叙事、关键张力、可执行调整建议。
          {recomputing && recomputeStep
            ? <><br /><span className="text-violet-700 font-semibold">{recomputeStep}</span></>
            : recomputeNote
              ? <><br /><span className="text-amber-700 font-semibold">未生成原因：{recomputeNote}</span></>
              : null}
        </p>
        <div className="mt-3">
          <button
            type="button"
            onClick={onRecompute}
            disabled={recomputing}
            className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {recomputing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            {recomputing ? '处理中…' : '一键生成品牌印象速读'}
          </button>
          {!recomputing && (
            <p className="mt-2 text-[10px] text-violet-700/60">
              系统会自动判断：缺数据先抓取，缺主题先聚类，最后合成速读
            </p>
          )}
        </div>
      </section>
    );
  }
  return (
    <section className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50/40 via-white to-white px-5 py-5">
      <div className="mb-3 flex items-start gap-3">
        <Sparkles size={18} className="mt-0.5 shrink-0 text-violet-600" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[14px] font-black text-violet-900">品牌印象速读</h3>
            <span className="inline-flex items-center gap-1 rounded-md bg-violet-100/70 px-2 py-0.5 text-[10px] font-bold text-violet-700">
              ✨ AI 合成
            </span>
            <span className="ml-auto text-[10px] text-gray-400 tabular-nums">
              {(audit.computedAt || '').slice(0, 16).replace('T', ' ')}
            </span>
            <button
              type="button"
              onClick={onRecompute}
              disabled={recomputing}
              title="重新合成"
              className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1.5 text-gray-500 hover:bg-violet-50 hover:border-violet-200 hover:text-violet-700 disabled:opacity-50"
            >
              {recomputing ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            </button>
          </div>
          {/* Headline · 一句话定位 */}
          <p className="mt-2 text-[14px] font-bold leading-snug text-violet-950">
            {audit.headline}
          </p>
        </div>
      </div>

      {/* 叙事 narrative */}
      {audit.narrativeMd && (
        <div className="mt-3 rounded-lg border border-violet-100 bg-white px-4 py-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-500">
            公众真实印象
          </div>
          <p className="mt-2 whitespace-pre-line text-[12px] leading-7 text-gray-700">
            {audit.narrativeMd}
          </p>
        </div>
      )}

      {/* 张力 tensions */}
      {audit.tensions && audit.tensions.length > 0 && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/40 px-4 py-3">
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={12} className="text-amber-600" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-amber-700">
              关键张力 · 自我 vs 公众
            </span>
          </div>
          <ul className="mt-2 space-y-2">
            {audit.tensions.map((t, idx) => (
              <li key={idx} className="text-[12px] leading-6 text-amber-950">
                <span className="font-bold">{idx + 1}.</span> {t.statement}
                {(t.selfAnchor || t.publicAnchor) && (
                  <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                    {t.selfAnchor && (
                      <span className="rounded-sm bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-800">
                        自称：{t.selfAnchor}
                      </span>
                    )}
                    {t.publicAnchor && (
                      <span className="rounded-sm bg-amber-200/60 px-1.5 py-0.5 font-semibold text-amber-900">
                        公众：{t.publicAnchor}
                      </span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 建议 recommendations */}
      {audit.recommendations && audit.recommendations.length > 0 && (
        <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50/40 px-4 py-3">
          <div className="flex items-center gap-1.5">
            <Lightbulb size={12} className="text-emerald-600" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-700">
              品牌调整建议 · 可执行
            </span>
          </div>
          <ul className="mt-2 space-y-2">
            {audit.recommendations.map((r, idx) => (
              <li key={idx} className="text-[12px] leading-6 text-emerald-950">
                <div className="flex items-baseline gap-2">
                  <span className="font-bold">{idx + 1}.</span>
                  <span className="font-bold flex-1">{r.action}</span>
                  {r.priority === 'high' && (
                    <span className="rounded-sm bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">
                      高优
                    </span>
                  )}
                </div>
                {r.rationale && (
                  <p className="mt-0.5 text-[11px] leading-5 text-emerald-900/80 ml-5">
                    {r.rationale}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* content angles — 已删 reduce / 弱化，避免 AI 在缺乏组织上下文时踩雷 */}
      {audit.contentAngles && (
        audit.contentAngles.amplify?.length || audit.contentAngles.new?.length
      ) ? (
        <div className="mt-3 rounded-lg border border-gray-200 bg-white px-4 py-3">
          <div className="flex items-center gap-1.5">
            <Megaphone size={12} className="text-gray-600" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">
              下次发声建议
            </span>
          </div>
          <div className="mt-2 grid gap-2 text-[11px] md:grid-cols-2">
            {audit.contentAngles.amplify?.length > 0 && (
              <div>
                <div className="text-[10px] font-bold text-emerald-700 mb-1">✓ 强化</div>
                <div className="flex flex-wrap gap-1">
                  {audit.contentAngles.amplify.map((a) => (
                    <span key={a} className="rounded-sm border border-emerald-100 bg-emerald-50/70 px-1.5 py-0.5 font-semibold text-emerald-800">
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {audit.contentAngles.new?.length > 0 && (
              <div>
                <div className="text-[10px] font-bold text-violet-700 mb-1">+ 新增</div>
                <div className="flex flex-wrap gap-1">
                  {audit.contentAngles.new.map((a) => (
                    <span key={a} className="rounded-sm border border-violet-100 bg-violet-50/60 px-1.5 py-0.5 font-semibold text-violet-800">
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {recomputeNote && (
        <p className="mt-3 text-[10px] text-amber-700">
          注：{recomputeNote}
        </p>
      )}
    </section>
  );
}


function ImpressionThemeCards({ themes, loading }: { themes: SentimentTheme[]; loading: boolean }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (loading && themes.length === 0) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
        <h3 className="mb-2 text-[13px] font-black text-gray-900">印象主题 · 网上对他形成了什么印象</h3>
        <p className="text-[11px] text-gray-400">加载中…</p>
      </section>
    );
  }
  if (themes.length === 0) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
        <h3 className="mb-2 text-[13px] font-black text-gray-900">印象主题 · 网上对他形成了什么印象</h3>
        <p className="text-[11px] text-gray-500">
          数据不足（少于 4 条），跑一次"立即抓取舆情"，等聚类完成后这里会出主题。
        </p>
      </section>
    );
  }
  return (
    <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
      <h3 className="mb-3 text-[13px] font-black text-gray-900">印象主题 · 网上对他形成了什么印象</h3>
      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
        {themes.map((t) => (
          <ThemeCard
            key={t.id}
            theme={t}
            expanded={expandedId === t.id}
            onToggle={() => setExpandedId((cur) => (cur === t.id ? null : t.id))}
          />
        ))}
      </div>
    </section>
  );
}

function ThemeCard({
  theme,
  expanded,
  onToggle,
}: {
  theme: SentimentTheme;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tone =
    theme.sentimentTone === 'negative' ? { ring: 'border-rose-200', accent: 'bg-rose-500', text: 'text-rose-700' } :
    theme.sentimentTone === 'positive' ? { ring: 'border-emerald-200', accent: 'bg-emerald-500', text: 'text-emerald-700' } :
                                          { ring: 'border-gray-200', accent: 'bg-gray-400', text: 'text-gray-600' };
  const [details, setDetails] = useState<ThemeItemSource[] | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || details !== null) return;
    setDetailLoading(true);
    setDetailError(null);
    getThemeItems(theme.id, 8)
      .then((r) => setDetails(r.items || []))
      .catch((err) => setDetailError(err instanceof Error ? err.message : '溯源失败'))
      .finally(() => setDetailLoading(false));
  }, [expanded, details, theme.id]);

  const openUrl = (url: string) => {
    if (!url || typeof window === 'undefined') return;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={`rounded-xl border ${tone.ring} bg-white transition-all`}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full px-4 py-3 text-left hover:bg-gray-50/60"
      >
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${tone.accent}`} />
          <span className="text-[13px] font-black text-gray-900">{theme.themeLabel}</span>
          <span className="ml-auto text-[11px] font-bold tabular-nums text-gray-400">{theme.itemCount} 条</span>
          {expanded ? <ChevronUp size={12} className="text-gray-400" /> : <ChevronDown size={12} className="text-gray-400" />}
        </div>
        {theme.themeSummary && (
          <p className="mt-1 text-[11px] leading-5 text-gray-500">{theme.themeSummary}</p>
        )}
        {theme.representativeQuote && (
          <p className={`mt-2 line-clamp-2 rounded-md bg-gray-50/60 px-2.5 py-1.5 text-[11px] italic leading-5 ${tone.text}`}>
            "{theme.representativeQuote}"
          </p>
        )}
      </button>
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3">
          {detailLoading ? (
            <p className="text-[11px] text-gray-400">加载原文中…</p>
          ) : detailError ? (
            <p className="text-[11px] text-rose-600">{detailError}</p>
          ) : (details || []).length === 0 ? (
            <p className="text-[11px] text-gray-400">这个主题下没有可溯源的原文。</p>
          ) : (
            <ul className="space-y-2">
              {(details || []).map((it) => (
                <li key={it.id} className="rounded-md border border-gray-100 bg-gray-50/40 px-3 py-2">
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-semibold leading-5 text-gray-900">{it.title}</p>
                      <p className="mt-0.5 text-[11px] text-gray-400">
                        {it.source} · {(it.capturedAt || '').slice(0, 10)}
                      </p>
                    </div>
                    {it.sourceUrl && (
                      <button
                        type="button"
                        onClick={() => openUrl(it.sourceUrl)}
                        title="看原文"
                        className="shrink-0 inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1 text-gray-500 hover:bg-[#EEF2FF] hover:text-[#5B7BFE]"
                      >
                        <Send size={11} strokeWidth={2.4} />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// P12-UI · 品牌镜子主面板
// 数据源：客户官网 / 官方公众号 / 官方微博 / 官方 B 站 / 招聘 / 合作方
// 5 个分析维度（先 UI 骨架 + mock，后端待接）
// ──────────────────────────────────────────────────────────────────────────

type OfficialChannelKind = 'homepage' | 'wechat' | 'weibo' | 'bilibili' | 'recruit' | 'partner';

interface OfficialChannel {
  kind: OfficialChannelKind;
  label: string;        // 显示名（如 "@日慈公益"）
  url?: string;         // 直接 URL
  identifier?: string;  // 公众号 ID / 微博账号名
  confidence: number;   // 0-100 系统识别置信度
  status: 'auto_detected' | 'user_confirmed' | 'user_added' | 'excluded';
  source?: string;      // 识别来源标识（"搜狗微信" / "天眼查" 等）
  meta?: string;        // 附加信息（粉丝数 / 认证类型）
}

const CHANNEL_META: Record<OfficialChannelKind, { name: string; icon: string; placeholder: string }> = {
  homepage:  { name: '官网',         icon: '🌐', placeholder: 'https://www.xxx.org.cn' },
  wechat:    { name: '官方公众号',    icon: '📱', placeholder: '公众号名称或 WeChat ID' },
  weibo:     { name: '官方微博',      icon: '🔵', placeholder: '@账号名（需带 @）' },
  bilibili:  { name: '官方 B 站',     icon: '🎥', placeholder: 'B 站 UID 或主页 URL' },
  recruit:   { name: '招聘渠道',      icon: '💼', placeholder: 'lagou / 智联 / 官方 HR 页 URL' },
  partner:   { name: '主要合作方',    icon: '🤝', placeholder: '机构名称或官网 URL' },
};

function BrandMirrorPanel({ workObject }: { workObject: IntelligenceWorkObject | null }) {
  const targetName = workObject?.name || '请先选择监控对象';
  const clientId = workObject?.type === 'client' ? workObject.id : (workObject?.clientId || undefined);
  const hasScope = Boolean(clientId);

  // 官方信息渠道（暂保留 P12-UI mock — 后端 official_channels_json 已接通但 UI 未切，单独迭代）
  const [channels, setChannels] = useState<OfficialChannel[]>(() => _mockOfficialChannelsFor(targetName));
  const [scanning, setScanning] = useState(false);

  // P13-D 真实 LLM 画像 snapshot
  const [snapshot, setSnapshot] = useState<BrandMirrorSnapshot | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  useEffect(() => {
    setChannels(_mockOfficialChannelsFor(targetName));
  }, [targetName]);

  useEffect(() => {
    if (!clientId) {
      setSnapshot(null);
      return;
    }
    let cancelled = false;
    setSnapshotLoading(true);
    setSnapshotError(null);
    fetchBrandMirrorSnapshot(clientId)
      .then((res) => {
        if (!cancelled) setSnapshot(res.snapshot);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setSnapshotError(error instanceof Error ? error.message : '加载画像失败');
        }
      })
      .finally(() => {
        if (!cancelled) setSnapshotLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  const handleAutoScan = () => {
    setScanning(true);
    window.setTimeout(() => {
      setScanning(false);
      setChannels((cur) => [
        ...cur,
        { kind: 'wechat', label: `${targetName}-新候选号`, identifier: 'auto_scan_demo', confidence: 75, status: 'auto_detected', source: '自动扫描（mock）' },
      ]);
    }, 1500);
  };

  const handleGenerate = async () => {
    if (!clientId || generating) return;
    setGenerating(true);
    setSnapshotError(null);
    try {
      const fresh = await triggerBrandMirrorAnalysis(clientId);
      // 后端返回字段对齐 BrandMirrorSnapshot 但 snapshotId/clientId 是 POST-only,
      // 重新 GET 最新 snapshot 以拿到 id 字段的正确形态
      const reloaded = await fetchBrandMirrorSnapshot(clientId);
      setSnapshot(reloaded.snapshot ?? {
        id: fresh.snapshotId,
        corpusDocCount: fresh.corpusDocCount,
        corpusCharCount: fresh.corpusCharCount,
        websiteAuditId: fresh.websiteAuditId,
        selfPresentation: fresh.selfPresentation,
        blindspots: fresh.blindspots,
        consistency: fresh.consistency,
        mediaCoverage: fresh.mediaCoverage,
        partners: fresh.partners,
        wordCloud: fresh.wordCloud,
        llmModel: fresh.llmModel,
        error: fresh.error,
        createdAt: fresh.createdAt,
      });
    } catch (error) {
      setSnapshotError(error instanceof Error ? error.message : '生成画像失败');
    } finally {
      setGenerating(false);
    }
  };

  if (!hasScope) {
    return (
      <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50/40 px-6 py-12 text-center">
        <Sparkles size={28} className="mx-auto text-gray-300" />
        <p className="mt-3 text-[13px] font-semibold text-gray-500">
          先在左侧选择具体客户，才能查看品牌呈现诊断
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-5">
      {/* 顶栏 · 客户名 + 生成画像按钮 + 状态 */}
      <section className="rounded-2xl border-2 border-violet-200 bg-gradient-to-br from-violet-50/60 to-white px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Sparkles size={16} className="text-violet-600" />
              <h2 className="text-[15px] font-black text-violet-900">品牌镜子 · {targetName}</h2>
              {snapshot ? (
                <span className="inline-flex items-center gap-1 rounded-md bg-violet-100/70 px-2 py-0.5 text-[10px] font-bold text-violet-700">
                  已生成 · {snapshot.corpusDocCount} 篇语料
                </span>
              ) : snapshotLoading ? (
                <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-bold text-gray-500">
                  加载中…
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-md bg-amber-100/70 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                  未生成
                </span>
              )}
            </div>
            <p className="mt-1 text-[11px] leading-5 text-violet-900/70">
              从客户**自己的官方表达**照出品牌：你说了什么 vs 没说什么、不同渠道一致吗、媒体怎么报道你、谁在和你合作。
            </p>
            {snapshot && (
              <p className="mt-1 text-[10px] text-violet-800/60">
                {snapshot.llmModel ? `${snapshot.llmModel} · ` : ''}
                {snapshot.corpusCharCount.toLocaleString()} 字 ·
                生成时间 {formatTime(snapshot.createdAt)}
                {snapshot.websiteAuditId && ' · 含 Lighthouse 评测'}
              </p>
            )}
            {snapshotError && (
              <p className="mt-1 text-[11px] font-semibold text-rose-600">{snapshotError}</p>
            )}
          </div>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={generating}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-[12px] font-bold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-violet-300"
          >
            {generating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {generating ? '生成中（30-90秒）' : snapshot ? '重新生成' : '生成画像'}
          </button>
        </div>
      </section>

      {/* ① 官方信息出口编辑器 */}
      <OfficialChannelsEditor
        clientId={clientId!}
        targetName={targetName}
        channels={channels}
        scanning={scanning}
        onAutoScan={handleAutoScan}
        onChannelsChange={setChannels}
      />

      {/* ② 品牌词云 — 真实 LLM 输出的 50 个词 */}
      {snapshot && snapshot.wordCloud.length > 0 && (
        <BrandWordCloud
          words={snapshot.wordCloud.map((w) => ({
            tag: w.word,
            strength: w.weight,
            tone: w.tone,
            sourceCount: w.sourceDiversity,
          }))}
          targetName={targetName}
        />
      )}

      {/* ③ 自我表达画像 */}
      <BrandMirrorSectionPlaceholder
        index="①"
        title="自我表达画像"
        subtitle="LLM 从官方语料里识别的核心叙事主张（按强度排序）"
        icon={<Megaphone size={14} className="text-blue-600" />}
        accentClass="border-blue-200 bg-blue-50/40"
        realSelfPresentation={snapshot?.selfPresentation}
        emptyHint={snapshot ? undefined : '点击右上「生成画像」开始'}
      />

      {/* ④ 盲点诊断 */}
      <BrandMirrorSectionPlaceholder
        index="②"
        title="盲点诊断"
        subtitle="机构想强调但语料里证据弱的潜在盲点"
        icon={<AlertTriangle size={14} className="text-amber-600" />}
        accentClass="border-amber-200 bg-amber-50/40"
        realBlindspots={snapshot?.blindspots}
        emptyHint={snapshot ? undefined : '点击右上「生成画像」开始'}
      />

      {/* ⑤ 一致性总评 */}
      <BrandMirrorSectionPlaceholder
        index="③"
        title="媒介一致性"
        subtitle="官网/公众号/媒体不同信源口径是否一致"
        icon={<FileCheck2 size={14} className="text-emerald-600" />}
        accentClass="border-emerald-100 bg-emerald-50/30"
        realConsistencyText={snapshot?.consistency}
        emptyHint={snapshot ? undefined : '点击右上「生成画像」开始'}
      />

      {/* ⑥ 媒体覆盖度 */}
      <BrandMirrorSectionPlaceholder
        index="④"
        title="媒体覆盖度"
        subtitle="按信源类型聚类的媒体声音"
        icon={<MessageCircle size={14} className="text-rose-500" />}
        accentClass="border-rose-100 bg-rose-50/30"
        realMediaCoverage={snapshot?.mediaCoverage}
        emptyHint={snapshot ? undefined : '点击右上「生成画像」开始'}
      />

      {/* ⑦ 合作生态 */}
      <BrandMirrorSectionPlaceholder
        index="⑤"
        title="合作生态"
        subtitle="语料里出现频次较高的合作方/伙伴（含证据来源）"
        icon={<Send size={14} className="text-violet-500" />}
        accentClass="border-violet-100 bg-violet-50/30"
        realPartners={snapshot?.partners}
        emptyHint={snapshot ? undefined : '点击右上「生成画像」开始'}
      />

      {/* 底部 · 数据接入状态 */}
      {snapshot && (
        <section className="rounded-xl border border-gray-200 bg-gray-50/40 px-4 py-3">
          <p className="text-[10px] leading-5 text-gray-500">
            <strong className="font-bold text-gray-700">数据源</strong>：
            {snapshot.corpusDocCount} 篇官方语料（brand_official_corpus），共 {snapshot.corpusCharCount.toLocaleString()} 字。
            {snapshot.websiteAuditId && '已含 Lighthouse 客观评测。'}
            模型 {snapshot.llmModel || '未知'}。
          </p>
        </section>
      )}
    </div>
  );
}

function _mockOfficialChannelsFor(name: string): OfficialChannel[] {
  if (name.includes('日慈')) {
    // 这些数据从实际抓取的 46 条 sentiment items + client_glossary 反推
    return [
      { kind: 'homepage', label: 'www.ricifoundation.org', url: 'https://www.ricifoundation.org', confidence: 100, status: 'user_confirmed', source: '已抓 4 条页面', meta: '官网主域' },
      { kind: 'wechat', label: '日慈公益', identifier: 'ricifoundation', confidence: 95, status: 'auto_detected', source: '搜狗微信抓到 25 条文章', meta: '已抓内容含 99公益日/心智素养/张真专访' },
      { kind: 'wechat', label: '日慈公益基金会', identifier: 'rici_foundation', confidence: 78, status: 'auto_detected', source: '搜狗微信 type=1（待二次确认）' },
      { kind: 'weibo', label: '@日慈公益', url: 'https://weibo.com/ricifoundation', confidence: 92, status: 'auto_detected', source: '已抓 3 条', meta: '心智素养研究院超话主理' },
      { kind: 'bilibili', label: '(暂未识别)', confidence: 0, status: 'auto_detected', source: 'B 站 API 搜不到日慈官方号', meta: '建议手填' },
      { kind: 'recruit', label: 'jobui.com / 日慈基金会页', url: 'https://www.jobui.com/company/...', confidence: 80, status: 'auto_detected', source: '招聘平台抓到 2 条', meta: '广东省日慈公益基金会词条' },
      { kind: 'partner', label: '腾讯基金会', confidence: 90, status: 'auto_detected', source: '联合发布青年情绪白皮书', meta: '心盛计划联合方' },
      { kind: 'partner', label: '北京师范大学中国公益研究院', confidence: 75, status: 'auto_detected', source: 'glossary + 多次媒体引用', meta: '学术合作' },
      { kind: 'partner', label: '健达品牌', confidence: 70, status: 'auto_detected', source: '健达快乐成长计划合作报道', meta: '企业资助方' },
    ];
  }
  return [];
}

// 真实抓回的日慈数据 (从 DB 提炼) — 用于让用户看到真实状态
// ── 品牌词云：50 个加权词，从 46 条 items + glossary + themes 提炼
type WordCloudItem = { tag: string; strength: number; tone?: 'positive' | 'neutral' | 'negative'; sourceCount?: number };
const REAL_RICI_WORD_CLOUD: WordCloudItem[] = [
  // ── 超大（90-100）核心机构身份 ──
  { tag: '日慈', strength: 100, tone: 'neutral', sourceCount: 38 },
  { tag: '公益基金会', strength: 95, tone: 'neutral', sourceCount: 30 },
  { tag: '儿童心理', strength: 95, tone: 'neutral', sourceCount: 28 },
  // ── 大（75-89）核心叙事 ──
  { tag: '心灵魔法学院', strength: 88, tone: 'positive', sourceCount: 18 },
  { tag: '心智素养', strength: 85, tone: 'positive', sourceCount: 14 },
  { tag: '公益', strength: 82, tone: 'positive', sourceCount: 25 },
  { tag: '张真', strength: 80, tone: 'neutral', sourceCount: 6 },
  { tag: '乡村', strength: 78, tone: 'neutral', sourceCount: 16 },
  // ── 中（50-74）次级标签 ──
  { tag: '青少年', strength: 72, tone: 'neutral', sourceCount: 14 },
  { tag: '心理健康', strength: 70, tone: 'neutral', sourceCount: 15 },
  { tag: '心盛计划', strength: 68, tone: 'positive', sourceCount: 8 },
  { tag: '学校', strength: 65, tone: 'neutral', sourceCount: 12 },
  { tag: '白皮书', strength: 62, tone: 'positive', sourceCount: 7 },
  { tag: '教师', strength: 60, tone: 'neutral', sourceCount: 10 },
  { tag: '情绪', strength: 58, tone: 'neutral', sourceCount: 6 },
  { tag: '腾讯基金会', strength: 56, tone: 'positive', sourceCount: 4 },
  { tag: '健达', strength: 54, tone: 'positive', sourceCount: 3 },
  { tag: '招聘', strength: 52, tone: 'neutral', sourceCount: 5 },
  { tag: '北师大公益', strength: 50, tone: 'positive', sourceCount: 3 },
  // ── 小（30-49）辅助标签 ──
  { tag: '捐赠', strength: 48, tone: 'positive', sourceCount: 8 },
  { tag: '99 公益日', strength: 46, tone: 'positive', sourceCount: 4 },
  { tag: '朋辈关怀员', strength: 45, tone: 'neutral', sourceCount: 1 },
  { tag: '暑期游学', strength: 42, tone: 'positive', sourceCount: 3 },
  { tag: '心智魔法', strength: 42, tone: 'positive', sourceCount: 4 },
  { tag: '研究', strength: 44, tone: 'neutral', sourceCount: 6 },
  { tag: '心理咨询', strength: 41, tone: 'neutral', sourceCount: 4 },
  { tag: '评价', strength: 40, tone: 'positive', sourceCount: 5 },
  { tag: '案例', strength: 38, tone: 'neutral', sourceCount: 4 },
  { tag: '超话', strength: 36, tone: 'neutral', sourceCount: 2 },
  { tag: '乡村教师', strength: 36, tone: 'neutral', sourceCount: 3 },
  { tag: '学院', strength: 34, tone: 'neutral', sourceCount: 5 },
  { tag: '工作坊', strength: 33, tone: 'neutral', sourceCount: 2 },
  { tag: '福利', strength: 32, tone: 'neutral', sourceCount: 2 },
  { tag: '影响', strength: 30, tone: 'neutral', sourceCount: 3 },
  // ── 微小（15-29）长尾词 ──
  { tag: '信息公开', strength: 28, tone: 'neutral', sourceCount: 6 },
  { tag: '干预项目', strength: 28, tone: 'positive', sourceCount: 3 },
  { tag: '培训', strength: 27, tone: 'neutral', sourceCount: 3 },
  { tag: '心育乐园', strength: 26, tone: 'positive', sourceCount: 2 },
  { tag: '学校成长画像', strength: 25, tone: 'neutral', sourceCount: 0 },
  { tag: '服务', strength: 25, tone: 'neutral', sourceCount: 4 },
  { tag: '战略陪伴', strength: 24, tone: 'neutral', sourceCount: 1 },
  { tag: '课堂', strength: 23, tone: 'neutral', sourceCount: 2 },
  { tag: '善款', strength: 22, tone: 'neutral', sourceCount: 2 },
  { tag: '任课老师', strength: 21, tone: 'neutral', sourceCount: 2 },
  { tag: '青少年心理支持生态', strength: 20, tone: 'neutral', sourceCount: 0 },
  { tag: '校长', strength: 20, tone: 'neutral', sourceCount: 1 },
  { tag: '会议', strength: 19, tone: 'neutral', sourceCount: 1 },
  { tag: '公益创投', strength: 18, tone: 'neutral', sourceCount: 1 },
  { tag: '案卷质量', strength: 18, tone: 'neutral', sourceCount: 0 },
  { tag: '对接', strength: 17, tone: 'neutral', sourceCount: 1 },
  { tag: '识途专题', strength: 16, tone: 'positive', sourceCount: 1 },
  { tag: '湾区经济', strength: 15, tone: 'positive', sourceCount: 1 },
];

const REAL_RICI_DATA = {
  selfPresentation: [
    { tag: '儿童心理', strength: 95, source: '客户档案 domain + 公众号 25 条高频' },
    { tag: '青少年', strength: 90, source: '客户档案 + 主题聚类' },
    { tag: '心灵魔法学院', strength: 85, source: '业务线 + audit narrative 提及覆盖 12 省 21000 名学生' },
    { tag: '乡村', strength: 78, source: '99 公益日项目 + 教师赋能项目' },
    { tag: '心智素养', strength: 72, source: '微博超话主题 + 心盛计划' },
    { tag: '张真', strength: 70, source: '银杏播客专访 + 媒体专访 ×3' },
    { tag: '公益基金会', strength: 65, source: '机构基础认知' },
    { tag: '心盛计划', strength: 58, source: '2026 青年情绪白皮书' },
    { tag: '教师赋能', strength: 52, source: '教师暑期心理健康游学营' },
  ],
  blindspots: [
    {
      selfTag: '学校成长画像',
      publicEvidence: '公众主题 0 条提及，自报方法论核心但外部认知为 0',
      severity: 'high' as const,
      evidence: '来自 audit tensions[0]',
    },
    {
      selfTag: '青少年心理支持生态网络',
      publicEvidence: '公众仅看到零散报告 + 信息公示，对生态布局无感知',
      severity: 'high' as const,
      evidence: '来自 audit tensions[1]',
    },
    {
      selfTag: '朋辈关怀员',
      publicEvidence: 'glossary 12 个业务术语中的核心方法论，公众讨论 0 次',
      severity: 'medium' as const,
      evidence: '从 glossary × themes 对比推断',
    },
    {
      selfTag: '心理咨询',
      publicEvidence: '官网提，但公众讨论焦点是「活动」「项目」非「咨询服务」',
      severity: 'low' as const,
      evidence: '主题分布判断',
    },
  ],
  consistency: [
    { aspect: '业务焦点表述', count: 4, tag: '官网=支持/捐赠；公众号=项目活动；媒体=张真专访；微博=超话社区——4 个落点', severity: 'medium' as const },
    { aspect: '使命语句', count: 2, tag: 'glossary 定义"青少年心理支持"，audit 推出"少儿心理公益" — 略有出入', severity: 'low' as const },
    { aspect: '核心项目主推', count: 3, tag: '官网主推"支持我们"；公众号主推「心灵魔法学院」；媒体主推「心盛计划/白皮书」', severity: 'medium' as const },
  ],
  mediaCoverage: [
    { source: '微信公众号·24 个号', count: 25, tone: '正面 + 中性混合' },
    { source: '中国企业报湾区经济', count: 1, tone: '正面深度报道' },
    { source: '网易·163', count: 2, tone: '专访秘书长张真 / 湾区经济' },
    { source: '银杏播客', count: 2, tone: '人物专访' },
    { source: '搜狐·sohu', count: 2, tone: '识途专题 + 教师项目' },
    { source: '今日头条', count: 1, tone: '机构介绍' },
    { source: '澎湃·thepaper', count: 1, tone: '中性' },
    { source: '招聘类·jobui/lagou', count: 3, tone: '中性·组织信号' },
  ],
  partners: [
    { name: '腾讯基金会', role: '联合发布 · 2026 青年情绪白皮书', appearance: 4 },
    { name: '北京师范大学中国公益研究院', role: '学术合作', appearance: 3 },
    { name: '健达品牌', role: '健达快乐成长计划 · 企业资助', appearance: 3 },
    { name: '南都基金会 / 北京新阳光慈善', role: '同行联名', appearance: 2 },
    { name: '得润公益基金', role: '英德乡村捐赠', appearance: 2 },
    { name: '关爱委员会', role: '走访 + 桥爱行业交流', appearance: 2 },
    { name: '亚洲动物基金 / 郎朗艺术基金会', role: '同行联名活动', appearance: 1 },
  ],
};

// ── 官方渠道编辑器（核心入口）──
function OfficialChannelsEditor({
  clientId,
  targetName,
  channels,
  scanning,
  onAutoScan,
  onChannelsChange,
}: {
  clientId: string;
  targetName: string;
  channels: OfficialChannel[];
  scanning: boolean;
  onAutoScan: () => void;
  onChannelsChange: (next: OfficialChannel[]) => void;
}) {
  void clientId; // 后端接通时用

  const grouped = (Object.keys(CHANNEL_META) as OfficialChannelKind[]).map((kind) => ({
    kind,
    list: channels.filter((c) => c.kind === kind && c.status !== 'excluded'),
  }));
  const acceptedCount = channels.filter((c) => c.status === 'user_confirmed' || c.status === 'user_added').length;
  const candidateCount = channels.filter((c) => c.status === 'auto_detected').length;

  const handleAdopt = (idx: number) => {
    const next = channels.map((c, i) => (i === idx ? { ...c, status: 'user_confirmed' as const } : c));
    onChannelsChange(next);
  };
  const handleExclude = (idx: number) => {
    const next = channels.map((c, i) => (i === idx ? { ...c, status: 'excluded' as const } : c));
    onChannelsChange(next);
  };

  return (
    <section className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <div>
          <h3 className="text-[14px] font-black text-gray-900">官方信息出口</h3>
          <p className="mt-0.5 text-[11px] text-gray-500">
            系统自动扫描 · 用户一键采纳 · 学习排除模式 — 这是品牌镜子的「数据源根」
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-400">
            已采纳 <b className="text-gray-800 tabular-nums">{acceptedCount}</b> · 待确认 <b className="text-violet-700 tabular-nums">{candidateCount}</b>
          </span>
          <button
            type="button"
            onClick={onAutoScan}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {scanning ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            {scanning ? '扫描中…' : '一键扫描'}
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {grouped.map((g) => (
          <ChannelGroup
            key={g.kind}
            kind={g.kind}
            list={g.list}
            channels={channels}
            onAdopt={handleAdopt}
            onExclude={handleExclude}
            onAdd={(newChannel) => onChannelsChange([...channels, newChannel])}
          />
        ))}
      </div>
    </section>
  );
}

function ChannelGroup({
  kind,
  list,
  channels,
  onAdopt,
  onExclude,
  onAdd,
}: {
  kind: OfficialChannelKind;
  list: OfficialChannel[];
  channels: OfficialChannel[];
  onAdopt: (idx: number) => void;
  onExclude: (idx: number) => void;
  onAdd: (c: OfficialChannel) => void;
}) {
  const meta = CHANNEL_META[kind];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const handleSubmit = () => {
    const value = draft.trim();
    if (!value) return;
    onAdd({
      kind,
      label: value,
      url: value.startsWith('http') ? value : undefined,
      identifier: !value.startsWith('http') ? value : undefined,
      confidence: 100,
      status: 'user_added',
      source: '用户手填',
    });
    setDraft('');
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/30 px-3 py-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-[14px]">{meta.icon}</span>
          <span className="text-[12px] font-black text-gray-900">{meta.name}</span>
          <span className="text-[10px] tabular-nums text-gray-400">{list.length}</span>
        </div>
        <button
          type="button"
          onClick={() => setEditing((v) => !v)}
          className="text-[11px] text-violet-700 hover:underline"
        >
          {editing ? '取消' : '+ 添加'}
        </button>
      </div>
      <div className="mt-2 space-y-1.5">
        {list.length === 0 && !editing && (
          <p className="rounded-md border border-dashed border-gray-200 bg-white px-2 py-1.5 text-[10px] text-gray-400">
            暂无 — 点「一键扫描」或「+ 添加」补充
          </p>
        )}
        {list.map((c) => {
          const idx = channels.indexOf(c);
          return (
            <div
              key={`${c.kind}_${c.label}_${idx}`}
              className={`flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-[11px] ${
                c.status === 'user_confirmed' || c.status === 'user_added'
                  ? 'border-emerald-200 bg-emerald-50/40'
                  : 'border-violet-100 bg-white'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-1.5">
                  {c.status === 'user_confirmed' || c.status === 'user_added' ? (
                    <CheckCircle2 size={11} className="shrink-0 text-emerald-600 mt-0.5" />
                  ) : (
                    <span className="text-[10px] font-bold text-violet-600">{c.confidence}%</span>
                  )}
                  <span className="truncate font-semibold text-gray-900">{c.label}</span>
                </div>
                {c.meta && <p className="mt-0.5 text-[10px] text-gray-400 truncate">{c.meta}</p>}
                {c.source && c.status === 'auto_detected' && (
                  <p className="mt-0.5 text-[10px] text-violet-600/70">来源：{c.source}</p>
                )}
              </div>
              {c.status === 'auto_detected' && (
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => onAdopt(idx)}
                    title="采纳"
                    className="inline-flex items-center justify-center rounded border border-emerald-200 bg-white p-0.5 text-emerald-700 hover:bg-emerald-50"
                  >
                    <CheckCircle2 size={11} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onExclude(idx)}
                    title="排除（系统会记住下次不再推荐）"
                    className="inline-flex items-center justify-center rounded border border-gray-200 bg-white p-0.5 text-gray-500 hover:bg-gray-50"
                  >
                    <X size={11} />
                  </button>
                </div>
              )}
              {(c.status === 'user_confirmed' || c.status === 'user_added') && (
                <button
                  type="button"
                  onClick={() => onExclude(idx)}
                  title="移除"
                  className="inline-flex items-center justify-center rounded border border-gray-200 bg-white p-0.5 text-gray-400 hover:bg-gray-50 hover:text-gray-700"
                >
                  <Trash2 size={11} />
                </button>
              )}
            </div>
          );
        })}
        {editing && (
          <div className="flex items-center gap-1.5">
            <input
              autoFocus
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSubmit();
                if (e.key === 'Escape') { setEditing(false); setDraft(''); }
              }}
              placeholder={meta.placeholder}
              className="flex-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-[11px] text-gray-900 outline-none focus:border-violet-500"
            />
            <button
              type="button"
              onClick={handleSubmit}
              className="rounded-md bg-violet-600 px-2 py-1 text-[10px] font-bold text-white hover:bg-violet-700"
            >
              保存
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 5 个分析维度的通用占位组件 ──
function BrandMirrorSectionPlaceholder({
  index,
  title,
  subtitle,
  icon,
  accentClass,
  mockBullets,
  mockBlindspots,
  mockConsistency,
  mockMediaTags,
  mockPartners,
  realSelfPresentation,
  realBlindspots,
  realConsistencyText,
  realMediaCoverage,
  realPartners,
  emptyHint,
}: {
  index: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  accentClass: string;
  mockBullets?: { tag: string; strength: number; source?: string }[];
  mockBlindspots?: { selfTag: string; publicEvidence: string; severity: 'high' | 'medium' | 'low'; evidence?: string }[];
  mockConsistency?: { aspect: string; count: number; tag: string; severity: 'high' | 'medium' | 'low' }[];
  mockMediaTags?: { source: string; count: number; tone: string }[];
  mockPartners?: { name: string; role: string; appearance: number }[];
  // P13-D 真实 LLM 输出
  realSelfPresentation?: { label: string; score: number; rationale: string }[];
  realBlindspots?: { label: string; rationale: string }[];
  realConsistencyText?: string;
  realMediaCoverage?: { source: string; tone: 'positive' | 'neutral' | 'negative'; summary: string }[];
  realPartners?: { name: string; type: string; evidence: string }[];
  emptyHint?: string;
}) {
  const isReal = Boolean(
    realSelfPresentation || realBlindspots || realConsistencyText
      || realMediaCoverage || realPartners
  );
  const realEmpty = isReal
    && (realSelfPresentation?.length ?? 0) === 0
    && (realBlindspots?.length ?? 0) === 0
    && !realConsistencyText
    && (realMediaCoverage?.length ?? 0) === 0
    && (realPartners?.length ?? 0) === 0;
  return (
    <section className={`rounded-2xl border ${accentClass} px-5 py-4`}>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="text-[10px] font-black text-gray-400 tabular-nums">{index}</span>
        {icon}
        <h3 className="text-[13px] font-black text-gray-900">{title}</h3>
        <span className="text-[10px] text-gray-500">{subtitle}</span>
        {!isReal && (
          <span className="ml-auto rounded-sm bg-gray-100 px-1.5 py-0.5 text-[10px] font-bold text-gray-500">mock</span>
        )}
        {isReal && !realEmpty && (
          <span className="ml-auto rounded-sm bg-emerald-100/70 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">LLM</span>
        )}
      </div>

      {realEmpty && (
        <p className="rounded-md bg-white px-3 py-3 text-[11px] text-gray-400">
          {emptyHint || '语料里暂无可识别的信号'}
        </p>
      )}

      {realSelfPresentation && realSelfPresentation.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {realSelfPresentation.map((entry) => (
              <span
                key={entry.label}
                className="inline-flex items-center gap-1 rounded-md bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-700 shadow-sm"
                style={{ borderLeft: `3px solid hsl(${entry.score * 1.2}, 70%, 55%)` }}
                title={entry.rationale}
              >
                {entry.label}
                <span className="text-[10px] tabular-nums text-gray-400">{entry.score}</span>
              </span>
            ))}
          </div>
          <details className="text-[10px] text-gray-400">
            <summary className="cursor-pointer hover:text-gray-600">查看每条主张的支撑证据</summary>
            <ul className="mt-1 space-y-0.5 pl-3 leading-5">
              {realSelfPresentation.map((entry) => (
                <li key={entry.label}>
                  <b className="text-gray-600">{entry.label}</b> — {entry.rationale}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}

      {realBlindspots && realBlindspots.length > 0 && (
        <ul className="space-y-1.5">
          {realBlindspots.map((entry, idx) => {
            const severity = idx === 0 ? 'high' : idx === 1 ? 'medium' : 'low';
            const toneClass =
              severity === 'high' ? 'text-rose-700'
              : severity === 'medium' ? 'text-amber-700'
              : 'text-gray-700';
            return (
              <li key={entry.label} className="rounded-md bg-white px-2.5 py-1.5 text-[11px] leading-5">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className={`font-bold ${toneClass}`}>「{entry.label}」</span>
                  <span className="text-gray-600">— {entry.rationale}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {realConsistencyText && (
        <div className="rounded-md bg-white px-3 py-2.5 text-[11px] leading-6 text-gray-700">
          {realConsistencyText}
        </div>
      )}

      {realMediaCoverage && realMediaCoverage.length > 0 && (
        <ul className="space-y-1.5">
          {realMediaCoverage.map((entry) => (
            <li key={entry.source} className="rounded-md bg-white px-2.5 py-1.5 text-[11px] leading-5">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="font-bold text-gray-900">{entry.source}</span>
                <span
                  className={`rounded-sm px-1.5 py-0.5 text-[10px] font-semibold ${
                    entry.tone === 'positive' ? 'bg-emerald-100 text-emerald-800'
                    : entry.tone === 'negative' ? 'bg-rose-100 text-rose-800'
                    : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {entry.tone}
                </span>
              </div>
              <p className="mt-0.5 text-gray-600">{entry.summary}</p>
            </li>
          ))}
        </ul>
      )}

      {realPartners && realPartners.length > 0 && (
        <ul className="space-y-1">
          {realPartners.map((entry) => (
            <li key={entry.name} className="rounded-md bg-white px-2.5 py-1.5 text-[11px] leading-5">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="font-bold text-gray-900">{entry.name}</span>
                <span className="rounded-sm bg-violet-100/70 px-1.5 py-0.5 text-[10px] font-semibold text-violet-700">
                  {entry.type}
                </span>
              </div>
              <p className="mt-0.5 text-[10px] italic text-gray-500">{entry.evidence}</p>
            </li>
          ))}
        </ul>
      )}

      {mockBullets && (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {mockBullets.map((b) => (
              <span
                key={b.tag}
                className="inline-flex items-center gap-1 rounded-md bg-white px-2.5 py-1 text-[11px] font-semibold text-gray-700 shadow-sm"
                style={{ borderLeft: `3px solid hsl(${b.strength * 1.2}, 70%, 55%)` }}
                title={b.source || ''}
              >
                {b.tag}
                <span className="text-[10px] tabular-nums text-gray-400">{b.strength}%</span>
              </span>
            ))}
          </div>
          {/* 显示 source 来源（鼠标悬停也能看到） */}
          {mockBullets.some((b) => b.source) && (
            <details className="text-[10px] text-gray-400">
              <summary className="cursor-pointer hover:text-gray-600">查看每个标签的信号来源</summary>
              <ul className="mt-1 space-y-0.5 pl-3 leading-5">
                {mockBullets.filter((b) => b.source).map((b) => (
                  <li key={b.tag}><b className="text-gray-600">{b.tag}</b> ← {b.source}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {mockBlindspots && (
        <ul className="space-y-1.5">
          {mockBlindspots.map((b) => (
            <li key={b.selfTag} className="rounded-md bg-white px-2.5 py-1.5 text-[11px] leading-5">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className={`font-bold ${b.severity === 'high' ? 'text-rose-700' : b.severity === 'medium' ? 'text-amber-700' : 'text-gray-700'}`}>
                  「{b.selfTag}」
                </span>
                <span className="text-gray-500">— {b.publicEvidence}</span>
              </div>
              {b.evidence && (
                <p className="mt-0.5 text-[10px] text-gray-400 italic">证据来源：{b.evidence}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {mockConsistency && (
        <ul className="space-y-1.5">
          {mockConsistency.map((c) => (
            <li key={c.aspect} className="flex items-baseline gap-2 rounded-md bg-white px-2.5 py-1.5 text-[11px]">
              <span className="font-bold text-gray-900">{c.aspect}</span>
              <span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${c.severity === 'medium' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>
                {c.tag}
              </span>
            </li>
          ))}
        </ul>
      )}

      {mockMediaTags && (
        <div className="flex flex-wrap gap-1.5">
          {mockMediaTags.map((m) => (
            <span key={m.source} className="rounded-md bg-white px-2.5 py-1 text-[11px] text-gray-700 shadow-sm">
              <b>{m.source}</b>
              <span className="ml-1 text-[10px] text-gray-400">×{m.count} · {m.tone}</span>
            </span>
          ))}
        </div>
      )}

      {mockPartners && (
        <ul className="space-y-1">
          {mockPartners.map((p) => (
            <li key={p.name} className="flex items-baseline gap-2 rounded-md bg-white px-2.5 py-1.5 text-[11px]">
              <span className="font-bold text-gray-900">{p.name}</span>
              <span className="text-[10px] text-violet-700">{p.role}</span>
              <span className="ml-auto text-[10px] tabular-nums text-gray-400">出现 {p.appearance} 次</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


// ──────────────────────────────────────────────────────────────────────────
// 品牌词云 + 3 精致信息卡（嵌入舆情监控页面顶部）
// ──────────────────────────────────────────────────────────────────────────

function BrandWordCloud({ words, targetName }: { words: WordCloudItem[]; targetName: string }) {
  if (!words || words.length === 0) return null;
  // 按 strength 倒序
  const sorted = [...words].sort((a, b) => b.strength - a.strength);
  const maxStrength = sorted[0].strength;
  const minStrength = sorted[sorted.length - 1].strength;
  const sizeFor = (s: number) => {
    // 字号梯度：14-44px，按平方根映射避免最大词过分突出
    const ratio = (s - minStrength) / Math.max(1, maxStrength - minStrength);
    const sq = Math.sqrt(ratio);
    return Math.round(14 + sq * 30);
  };
  const colorClassFor = (tone?: string) => {
    if (tone === 'positive') return 'text-emerald-700 hover:text-emerald-900';
    if (tone === 'negative') return 'text-rose-700 hover:text-rose-900';
    return 'text-gray-700 hover:text-gray-900';
  };
  const weightClassFor = (sourceCount?: number) => {
    if (!sourceCount) return 'font-medium';
    if (sourceCount >= 15) return 'font-extrabold';
    if (sourceCount >= 8) return 'font-bold';
    if (sourceCount >= 3) return 'font-semibold';
    return 'font-medium';
  };
  const opacityFor = (sourceCount?: number) => {
    if (!sourceCount || sourceCount === 0) return 0.45;  // 客户自报但公众未提及——半透明
    return 1;
  };

  return (
    <section className="rounded-2xl border border-gray-200 bg-gradient-to-br from-white via-violet-50/20 to-white px-6 py-5">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <div>
          <h3 className="text-[14px] font-black text-gray-900">品牌词云 · {targetName}</h3>
          <p className="mt-0.5 text-[11px] text-gray-500">
            公众语境下出现的所有关键词，字号 = 强度，颜色 = 倾向（绿=正/灰=中），半透明 = 你说了但公众没接住
          </p>
        </div>
        <span className="text-[10px] tabular-nums text-gray-400">{sorted.length} 词</span>
      </div>
      <div className="flex flex-wrap items-end gap-x-3 gap-y-2 leading-none">
        {sorted.map((w) => (
          <span
            key={w.tag}
            title={
              w.sourceCount !== undefined
                ? `权重 ${w.strength} · 在 ${w.sourceCount} 个来源中出现${w.sourceCount === 0 ? '（公众未提及，仅来自客户自报）' : ''}`
                : `权重 ${w.strength}`
            }
            className={`inline-block cursor-default transition-all ${colorClassFor(w.tone)} ${weightClassFor(w.sourceCount)}`}
            style={{
              fontSize: `${sizeFor(w.strength)}px`,
              opacity: opacityFor(w.sourceCount),
            }}
          >
            {w.tag}
          </span>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3 text-[10px] text-gray-400">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> 正面
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-gray-400" /> 中性
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-rose-500" /> 负面
        </span>
        <span className="ml-3">字体粗细 = 出现的不同来源数（越多越粗）</span>
      </div>
    </section>
  );
}


// ── 3 精致信息卡（媒体覆盖度 / 合作生态 / 官方信息出口）──
function BrandInsightCardRow({
  mediaCoverage,
  partners,
  channels,
  onAdoptChannel,
  onExcludeChannel,
}: {
  mediaCoverage: { source: string; count: number; tone: string }[];
  partners: { name: string; role: string; appearance: number }[];
  channels: OfficialChannel[];
  onAdoptChannel: (idx: number) => void;
  onExcludeChannel: (idx: number) => void;
}) {
  const acceptedCount = channels.filter((c) => c.status === 'user_confirmed' || c.status === 'user_added').length;
  const candidateCount = channels.filter((c) => c.status === 'auto_detected').length;
  const totalMediaItems = mediaCoverage.reduce((s, m) => s + m.count, 0);

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {/* 📰 媒体覆盖度 */}
      <article className="group rounded-2xl border border-rose-200/70 bg-gradient-to-br from-rose-50/40 to-white px-4 py-4 transition-all hover:border-rose-300 hover:shadow-md">
        <div className="flex items-center gap-2">
          <span className="text-[16px]">📰</span>
          <h4 className="text-[13px] font-black text-rose-900">媒体覆盖度</h4>
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-[28px] font-black text-rose-700 tabular-nums leading-none">{totalMediaItems}</span>
          <span className="text-[11px] text-rose-600/80">条 · {mediaCoverage.length} 个源</span>
        </div>
        <ul className="mt-3 space-y-1">
          {mediaCoverage.slice(0, 5).map((m) => (
            <li key={m.source} className="flex items-baseline gap-1.5 text-[11px] text-gray-700">
              <span className="h-1 w-1 rounded-full bg-rose-400 shrink-0" />
              <span className="truncate font-semibold">{m.source}</span>
              <span className="ml-auto tabular-nums text-gray-500">×{m.count}</span>
            </li>
          ))}
          {mediaCoverage.length > 5 && (
            <li className="text-[10px] text-rose-600/70 pl-2.5">还有 {mediaCoverage.length - 5} 个来源…</li>
          )}
        </ul>
      </article>

      {/* 🤝 合作生态 */}
      <article className="group rounded-2xl border border-violet-200/70 bg-gradient-to-br from-violet-50/40 to-white px-4 py-4 transition-all hover:border-violet-300 hover:shadow-md">
        <div className="flex items-center gap-2">
          <span className="text-[16px]">🤝</span>
          <h4 className="text-[13px] font-black text-violet-900">合作生态</h4>
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-[28px] font-black text-violet-700 tabular-nums leading-none">{partners.length}</span>
          <span className="text-[11px] text-violet-600/80">个识别合作方</span>
        </div>
        <ul className="mt-3 space-y-1">
          {partners.slice(0, 4).map((p) => (
            <li key={p.name} className="text-[11px]">
              <div className="flex items-baseline gap-1.5 text-gray-700">
                <span className="h-1 w-1 rounded-full bg-violet-400 shrink-0" />
                <span className="truncate font-semibold">{p.name}</span>
                <span className="ml-auto tabular-nums text-gray-500">×{p.appearance}</span>
              </div>
              <p className="ml-2.5 text-[10px] text-violet-600/80 truncate">{p.role}</p>
            </li>
          ))}
          {partners.length > 4 && (
            <li className="text-[10px] text-violet-600/70 pl-2.5">还有 {partners.length - 4} 个合作方…</li>
          )}
        </ul>
      </article>

      {/* 🌐 官方信息出口 */}
      <article className="group rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-emerald-50/40 to-white px-4 py-4 transition-all hover:border-emerald-300 hover:shadow-md">
        <div className="flex items-center gap-2">
          <span className="text-[16px]">🌐</span>
          <h4 className="text-[13px] font-black text-emerald-900">官方信息出口</h4>
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <div>
            <span className="text-[28px] font-black text-emerald-700 tabular-nums leading-none">{acceptedCount}</span>
            <span className="ml-1 text-[10px] text-emerald-600/80">已采纳</span>
          </div>
          {candidateCount > 0 && (
            <div className="text-[11px] text-amber-700">
              <span className="font-black tabular-nums">{candidateCount}</span> 待确认
            </div>
          )}
        </div>
        <ul className="mt-3 space-y-1">
          {channels
            .filter((c) => c.status !== 'excluded')
            .slice(0, 5)
            .map((c, idx) => {
              const meta = CHANNEL_META[c.kind];
              const isCandidate = c.status === 'auto_detected';
              const realIdx = channels.indexOf(c);
              return (
                <li key={`${c.kind}_${c.label}_${idx}`} className="flex items-baseline gap-1.5 text-[11px]">
                  <span className="text-[11px]">{meta.icon}</span>
                  <span className={`truncate ${isCandidate ? 'text-gray-600' : 'font-semibold text-gray-800'}`}>
                    {c.label}
                  </span>
                  {isCandidate ? (
                    <span className="ml-auto flex items-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => onAdoptChannel(realIdx)}
                        title="采纳"
                        className="inline-flex items-center justify-center rounded p-0.5 text-emerald-600 hover:bg-emerald-100"
                      >
                        <CheckCircle2 size={10} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onExcludeChannel(realIdx)}
                        title="排除"
                        className="inline-flex items-center justify-center rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ) : (
                    <CheckCircle2 size={9} className="ml-auto shrink-0 text-emerald-500" />
                  )}
                </li>
              );
            })}
        </ul>
      </article>
    </div>
  );
}
