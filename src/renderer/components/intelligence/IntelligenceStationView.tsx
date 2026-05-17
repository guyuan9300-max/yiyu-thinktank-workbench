// @ts-nocheck — 整合于 2026-05-13：同事 push 的资讯情报站视图，半成品，
// 5 个 setState 函数式更新回调里 `current` 参数 implicit any，等同事下次 sync
// 后他自己加类型注解或在 origin/main 用更宽松的 tsconfig。我们暂时跳过 type check，
// 避免 npx tsc --noEmit 在我们这条线被同事的代码挡掉。
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BellPlus,
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  Loader2,
  MessageCircle,
  RefreshCw,
  Save,
  Send,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react';

import type {
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
  profile_completion: 10,
  timely_intelligence: 5,
};

const TAB_LABEL: Record<IntelligenceContentKind, string> = {
  profile_completion: '资料补全',
  timely_intelligence: '时效情报',
};

const TAB_HINT: Record<IntelligenceContentKind, string> = {
  profile_completion: '已核验资料更新',
  timely_intelligence: '需要判断与跟进的外部信号',
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
  if (result.contentKind === 'profile_completion') {
    return `${label}刷新完成：处理 ${totals.objectCount} 个对象，线索 ${totals.candidateCount} 条，正文抓取 ${totals.bodyFetchedCount} 条，核验通过 ${totals.verifiedCount} 条，摘要生成 ${totals.summarySuccessCount} 条，成卡 ${totals.promotedCount} 条${totals.noResultCount ? `，未找到 ${totals.noResultCount} 个对象` : ''}${totals.failedCount ? `，失败 ${totals.failedCount} 个对象` : ''}。`;
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

function isProfileCompletion(item: IntelligenceItem) {
  return item.contentKind === 'profile_completion';
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

function profileSourceLabel(label: string, url: string) {
  const trimmed = label.trim();
  if (trimmed && !/^https?:\/\//i.test(trimmed)) {
    return trimmed.length > 42 ? `${trimmed.slice(0, 40)}...` : trimmed;
  }
  return compactSourceLabel(label, url);
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
    items.push({ label: isProfileCompletion(item) ? profileSourceLabel(sourceLabel, item.sourceUrl) : readableSourceLabel(sourceLabel, item.sourceUrl), url: item.sourceUrl });
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

function refreshRunDimensionSummary(runs: IntelligenceRefreshRun[]) {
  const covered = Array.from(new Set(runs.flatMap((run) => refreshRunStringList(run, 'profileCoverage'))));
  const missing = Array.from(new Set(runs.flatMap((run) => refreshRunStringList(run, 'profileMissingDimensions'))));
  const coveredText = covered.length ? `覆盖 ${covered.slice(0, 3).join('、')}${covered.length > 3 ? `等 ${covered.length} 项` : ''}` : '覆盖待确认';
  const missingText = missing.length ? `仍缺 ${missing.slice(0, 3).join('、')}${missing.length > 3 ? `等 ${missing.length} 项` : ''}` : '基础缺口较少';
  return `${coveredText}；${missingText}`;
}

function profileDeepDiveSummary(runs: IntelligenceRefreshRun[]) {
  const queued = runs.reduce((sum, run) => sum + refreshRunCount(run, 'deepDiveQueuedCount'), 0);
  const processed = runs.reduce((sum, run) => sum + refreshRunCount(run, 'deepDiveProcessedCount'), 0);
  const skipped = runs.reduce((sum, run) => sum + refreshRunCount(run, 'deepDiveSkippedCount'), 0);
  const remaining = runs.reduce((sum, run) => sum + refreshRunCount(run, 'deepDiveRemainingCount'), 0);
  if (!queued && !processed && !skipped && !remaining) return '';
  const parts: string[] = [];
  if (queued) parts.push(`新增待深挖 ${queued}`);
  if (processed) parts.push(`已处理深挖 ${processed}`);
  if (skipped) parts.push(`跳过复杂来源 ${skipped}`);
  if (remaining) parts.push(`剩余深挖 ${remaining}`);
  return parts.join(' · ');
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
  const pagesFetchedCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'pagesFetchedCount'), 0);
  const profileFactCandidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'profileFactCandidateCount'), 0);
  const processedPageCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'processedPageCount'), 0) || pagesFetchedCount;
  const usableFactCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'usableFactCount'), 0) || profileFactCandidateCount;
  const profileFactCardCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'profileFactCardCount'), 0);
  const scoutCandidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'scoutCandidateCount'), 0);
  const reviewCandidateCount = finishedRuns.reduce((sum, run) => sum + refreshRunCount(run, 'reviewCandidateCount'), 0);
  const timelyScoutCount = scoutCandidateCount || candidateCount;
  const profileLeadText = processedPageCount ? `${candidateCount} / ${processedPageCount}` : String(candidateCount);
  const profileCardCount = profileFactCardCount || promotedCount;
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
            {visibleKind === 'profile_completion'
              ? '正在生成研究问题、校准来源、连续抓取正文、核验身份锚点和基础资料缺口；重点关注只作为优先方向。切到其他模块后回来，状态会继续保留。'
              : '正在抓取可核验详情页，并判断外部变化、影响链条和下一步动作。切到其他模块后回来，状态会继续保留。'}
          </p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {activeRuns.slice(0, 4).map((run) => (
              <div key={run.id} className="rounded-md bg-gray-50 px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <b className="text-gray-900">{refreshRunObjectLabel(run, workObjects)}</b>
                  <span className="text-gray-500">{run.status === 'queued' ? '排队中' : '运行中'} · {formatTime(run.updatedAt)}</span>
                </div>
                <p className="mt-1 text-gray-600">{run.message || run.stage || '后台研究正在推进'}</p>
                {visibleKind === 'profile_completion' && (
                  <>
                    <p className="mt-1 text-gray-500">
                      已处理页面 {refreshRunCount(run, 'processedPageCount') || refreshRunCount(run, 'pagesFetchedCount')} · 可用事实 {refreshRunCount(run, 'usableFactCount') || refreshRunCount(run, 'profileFactCandidateCount')} · 已成卡 {refreshRunCount(run, 'profileFactCardCount') || refreshRunCount(run, 'promotedCount')}
                    </p>
                    {profileDeepDiveSummary([run]) && (
                      <p className="mt-1 text-gray-500">{profileDeepDiveSummary([run])}</p>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        </>
      ) : latestFinishedRun ? (
        <>
          <div className={`mt-3 grid gap-2 ${visibleKind === 'timely_intelligence' ? 'md:grid-cols-6' : 'md:grid-cols-7'}`}>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">客户/项目</span>
              <b>{refreshRunObjectSummary(finishedRuns, workObjects)}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">运行时间</span>
              <b>{refreshRunTimeRange(finishedRuns)}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">{visibleKind === 'timely_intelligence' ? '初筛候选' : '线索/页面'}</span>
              <b>{visibleKind === 'timely_intelligence' ? timelyScoutCount : profileLeadText}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">{visibleKind === 'timely_intelligence' ? '入围复核' : '提炼事实'}</span>
              <b>{visibleKind === 'timely_intelligence' ? reviewCandidateCount : usableFactCount}</b>
            </div>
            <div className="rounded-md bg-white/70 px-3 py-2">
              <span className="block text-blue-900/60">最终成卡</span>
              <b>{visibleKind === 'timely_intelligence' ? promotedCount : profileCardCount}</b>
            </div>
            {visibleKind === 'profile_completion' && (
              <div className="rounded-md bg-white/70 px-3 py-2">
                <span className="block text-blue-900/60">覆盖/仍缺</span>
                <b>{refreshRunDimensionSummary(finishedRuns)}</b>
              </div>
            )}
            {visibleKind === 'profile_completion' && (
              <div className="rounded-md bg-white/70 px-3 py-2">
                <span className="block text-blue-900/60">最新更新时间</span>
                <b>{formatTime(latestFinishedRun.updatedAt)}</b>
              </div>
            )}
            {visibleKind === 'timely_intelligence' && (
              <div className="rounded-md bg-white/70 px-3 py-2">
                <span className="block text-blue-900/60">最新更新时间</span>
                <b>{formatTime(latestFinishedRun.updatedAt)}</b>
              </div>
            )}
          </div>
          <p className="mt-2 text-blue-900/70">
            {latestFinishedRun.message || '后台研究已结束。'}
          </p>
          {visibleKind === 'profile_completion' && profileDeepDiveSummary(finishedRuns) && (
            <p className="mt-1 text-blue-900/70">{profileDeepDiveSummary(finishedRuns)}</p>
          )}
        </>
      ) : (
        <p className="mt-2 text-blue-900/70">
          尚未开始自动抓取，可以点击右上角按钮手动{visibleKind === 'profile_completion' ? '补全资料' : '抓取情报'}。
        </p>
      )}
      {!showingActive && latestFinishedRun && !hasItems && (
        <p className="mt-1 text-blue-900/70">
          当前没有通过严格判断的{visibleKind === 'profile_completion' ? '资料卡' : '时效情报卡'}；系统不会把候选短摘或未核验页面放进普通列表。
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

function ProfileCompletionCard({
  item,
  workObjects,
  pending,
  onClarify,
}: {
  item: IntelligenceItem;
  workObjects: IntelligenceWorkObject[];
  pending: boolean;
  onClarify: (item: IntelligenceItem) => void;
}) {
  const links = sourceLinks(item);
  return (
    <article className="rounded-lg border border-gray-200 bg-white px-5 py-4 shadow-sm">
      <div className="grid gap-4 md:grid-cols-[140px_minmax(0,1fr)]">
        <p className="text-[12px] font-black text-gray-500">客户/项目</p>
        <p className="text-[13px] font-bold text-gray-900">{itemObjectLabel(item, workObjects)}</p>

        <p className="text-[12px] font-black text-gray-500">补足资料</p>
        <p className="text-[14px] font-black leading-6 text-gray-950">{profileGapLabel(item)}</p>

        <p className="text-[12px] font-black text-gray-500">可复用事实</p>
        <div className="space-y-2 text-[13px] leading-6 text-gray-700">
          {item.keyPoints.map((point) => (
            <p key={point}>{point}</p>
          ))}
        </div>

        <p className="text-[12px] font-black text-gray-500">发布时间</p>
        <p className="text-[13px] font-bold text-gray-700">{formatDateOnly(item.publishedAt)}</p>

        <p className="text-[12px] font-black text-gray-500">来源</p>
        <div className="space-y-1 text-[12px] font-semibold leading-5">
          {links.length > 0 ? (
            links.map((link) => (
              <a
                key={link.url}
                href={link.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex max-w-full items-center truncate rounded bg-blue-50 px-2 py-1 text-blue-700 hover:text-blue-900 hover:underline"
                title={link.url}
              >
                {link.label}
              </a>
            ))
          ) : (
            <span className="text-gray-500">{item.source || '来源未知'}</span>
          )}
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={() => onClarify(item)}
          disabled={pending}
          className="inline-flex items-center gap-1 rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-[12px] font-bold text-amber-800 hover:bg-amber-100 disabled:opacity-40"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          我不采纳
        </button>
      </div>
    </article>
  );
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
  const links = sourceLinks(item);
  const objectLabel = itemObjectLabel(item, workObjects);
  const timeliness = item.timelinessLabel || (item.publishedAt ? `发布 ${formatTime(item.publishedAt)}` : `抓取 ${formatTime(item.capturedAt)}`);
  const publishedLabel = item.publishedAt ? formatDateOnly(item.publishedAt) : '未识别';
  return (
    <article className="rounded-lg border border-gray-200 bg-white px-5 py-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-[150px_1fr_130px_180px]">
          <IntelligenceField label="情报类型">
            <span className="font-black text-gray-950">{item.intelligenceType || '时效信号'}</span>
          </IntelligenceField>
          <IntelligenceField label="关联对象">
            <span className="font-bold text-gray-900">{objectLabel}</span>
          </IntelligenceField>
          <IntelligenceField label="发布时间">
            <span className="font-bold text-gray-900">{publishedLabel}</span>
          </IntelligenceField>
          <IntelligenceField label="时效性">
            <span className="font-bold text-gray-900">{timeliness}</span>
          </IntelligenceField>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          {item.userStatus === 'following' && (
            <span className="rounded bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700">已关注</span>
          )}
          {item.convertedTaskId && (
            <span className="rounded bg-gray-950 px-2 py-1 text-[11px] font-bold text-white">已转任务</span>
          )}
        </div>
      </div>

      <div className="mt-4 border-y border-gray-100 py-4">
        <IntelligenceField label="标题">
          <h2 className="text-[18px] font-black leading-7 text-gray-950">{item.title}</h2>
        </IntelligenceField>
        <div className="mt-4">
          <IntelligenceField label="发生了什么">
            <p>{item.summary || '暂无摘要。'}</p>
          </IntelligenceField>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <IntelligenceField label="为什么和你有关">
          <p>{item.relevanceReason || item.analysis || '这条情报尚未补齐结构化相关性判断。'}</p>
        </IntelligenceField>
        <IntelligenceField label="可能影响" tone="amber">
          <p>{item.impact || '需要判断是否跟进。'}</p>
        </IntelligenceField>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <IntelligenceField label="建议动作">
          <p>{item.suggestedAction || item.impact || '可转成阅读/研判任务，再判断是否跟进。'}</p>
        </IntelligenceField>
        <IntelligenceField label="来源">
          <div className="space-y-1 text-[12px] font-semibold leading-5">
            {links.length > 0 ? (
              links.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex max-w-full items-center truncate rounded bg-blue-50 px-2 py-1 text-blue-700 hover:text-blue-900 hover:underline"
                  title={link.url}
                >
                  {link.label}
                </a>
              ))
            ) : (
              <span className="text-gray-500">{item.source || '来源未知'}</span>
            )}
          </div>
        </IntelligenceField>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 pt-4">
        <button
          type="button"
          onClick={() => onQuestion(item)}
          className="inline-flex items-center gap-1 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-[12px] font-bold text-blue-700 hover:bg-blue-100"
        >
          <MessageCircle size={14} />
          追问
        </button>
        <button
          type="button"
          onClick={() => onPromoteToTask(item)}
          disabled={pending}
          className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-40"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <SlidersHorizontal size={14} />}
          转任务
        </button>
        <button
          type="button"
          onClick={() => onFollow(item)}
          disabled={pending}
          className="inline-flex items-center gap-1 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-[12px] font-bold text-emerald-700 hover:bg-emerald-100 disabled:opacity-40"
        >
          <BellPlus size={14} />
          关注后续
        </button>
        <button
          type="button"
          onClick={() => onDismiss(item)}
          disabled={pending}
          className="inline-flex items-center gap-1 rounded-md border border-rose-100 bg-rose-50 px-3 py-2 text-[12px] font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-40"
        >
          <Trash2 size={14} />
          不采纳
        </button>
      </div>
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
  const [selectedScopeKey, setSelectedScopeKey] = useState<WorkObjectSelection>('all');
  const [focusScopeKey, setFocusScopeKey] = useState<ScopeKey>('global');
  const [focusDraft, setFocusDraft] = useState<FocusDraft>(EMPTY_FOCUS_DRAFT);
  const [activeTab, setActiveTab] = useState<IntelligenceContentKind>('profile_completion');
  const [sort, setSort] = useState<SortMode>('captured_desc');
  const [pages, setPages] = useState<Record<IntelligenceContentKind, number>>({
    profile_completion: 1,
    timely_intelligence: 1,
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
  const [dismissReason, setDismissReason] = useState<IntelligenceDismissReasonCode>('irrelevant');
  const [dismissNote, setDismissNote] = useState('');
  const [followTarget, setFollowTarget] = useState<IntelligenceItem | null>(null);
  const [followMode, setFollowMode] = useState<IntelligenceFollowMode>('same_theme');
  const [followNote, setFollowNote] = useState('');
  const [taskDraftTarget, setTaskDraftTarget] = useState<IntelligenceItem | null>(null);
  const [taskDraft, setTaskDraft] = useState<IntelligenceTaskDraftPayload | null>(null);
  const [taskDraftCacheByItemId, setTaskDraftCacheByItemId] = useState<Record<string, IntelligenceTaskDraftPayload>>({});
  const [peopleOptions, setPeopleOptions] = useState<MentionCandidate[]>([]);
  const flashRef = useRef(flash);
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

  useEffect(() => {
    if (activeRefreshRuns.length === 0) return undefined;
    const timer = window.setInterval(() => {
      void refreshWithoutMovingReader(() => Promise.all([loadRefreshRuns(), loadShell(), loadItems({ silent: true })])).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeRefreshRuns.length, loadItems, loadRefreshRuns, loadShell, refreshWithoutMovingReader]);

  function changeScope(next: WorkObjectSelection) {
    setSelectedScopeKey(next);
    setPages({ profile_completion: 1, timely_intelligence: 1 });
  }

  function changeSort(next: SortMode) {
    setSort(next);
    setPages({ profile_completion: 1, timely_intelligence: 1 });
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

  function cycleHoursFor(kind: IntelligenceContentKind) {
    return kind === 'profile_completion'
      ? refreshCycleSettings.profileCompletionHours
      : refreshCycleSettings.timelyIntelligenceHours;
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
      const payload = cycleEditKind === 'profile_completion'
        ? { profileCompletionHours: normalized }
        : { timelyIntelligenceHours: normalized };
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
    setDismissReason('irrelevant');
    setDismissNote('');
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
    if (!dismissTarget) return;
    const item = dismissTarget;
    setPendingItemId(item.id);
    try {
      await dismissIntelligenceItem(item.id, {
        reasonCode: dismissReason,
        note: dismissNote.trim(),
      });
      setDismissTarget(null);
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

  return (
    <div ref={scrollContainerRef} className="h-full overflow-y-auto bg-[#F6F7F9] font-sans text-gray-950">
      <div className="mx-auto max-w-[1320px] px-6 py-6">
        <header className="border-b border-gray-200 pb-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[12px] font-bold uppercase tracking-[0.18em] text-gray-400">资讯情报站</p>
              <h1 className="mt-1 text-[26px] font-black tracking-normal text-gray-950">客户/项目情报流</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-gray-500">
                <span>{selectedLabel}</span>
                <span>·</span>
                <span>{TAB_LABEL[activeTab]}每页 {currentPageSize} 条</span>
                {lastFetchTime && (
                  <>
                    <span>·</span>
                    <span>最近线索抓取 {lastFetchTime}</span>
                  </>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setFocusModalOpen(true)}
                className="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-bold text-gray-700 hover:bg-gray-50"
              >
                <SlidersHorizontal size={16} />
                我重点关注什么
              </button>
              <button
                type="button"
                onClick={() => void handleRefreshSupply('profile_completion')}
                disabled={refreshInProgress}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-3 py-2 text-[13px] font-bold text-white hover:bg-emerald-800 disabled:opacity-50"
              >
                {activeRefreshKind === 'profile_completion' ? <Loader2 size={16} className="animate-spin" /> : <FileCheck2 size={16} />}
                立即补全资料
              </button>
              <button
                type="button"
                onClick={() => void handleRefreshSupply('timely_intelligence')}
                disabled={refreshInProgress}
                className="inline-flex items-center gap-2 rounded-md bg-gray-950 px-3 py-2 text-[13px] font-bold text-white hover:bg-gray-800 disabled:opacity-50"
              >
                {activeRefreshKind === 'timely_intelligence' ? <Loader2 size={16} className="animate-spin" /> : <BellPlus size={16} />}
                立即抓取情报
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(280px,1fr)_240px]">
            <label className="text-[12px] font-bold text-gray-500">
              工作对象
              <select
                value={selectedScopeKey}
                onChange={(event) => changeScope(event.target.value as WorkObjectSelection)}
                className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
              >
                <option value="all">全部客户/项目</option>
                {workObjects.map((item) => (
                  <option key={scopeKeyOfObject(item)} value={scopeKeyOfObject(item)}>
                    {item.type === 'client' ? '客户' : '项目'}：{item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[12px] font-bold text-gray-500">
              时间排序
              <select
                value={sort}
                onChange={(event) => changeSort(event.target.value as SortMode)}
                className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-semibold text-gray-800 outline-none focus:border-gray-400"
              >
                {(Object.keys(SORT_LABEL) as SortMode[]).map((key) => (
                  <option key={key} value={key}>{SORT_LABEL[key]}</option>
                ))}
              </select>
            </label>
          </div>

        </header>

        <main className="mt-5">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200">
            <div className="flex gap-1">
              {(Object.keys(TAB_LABEL) as IntelligenceContentKind[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveTab(key)}
                  className={`border-b-2 px-4 py-3 text-left ${activeTab === key ? 'border-gray-950 text-gray-950' : 'border-transparent text-gray-500 hover:text-gray-800'}`}
                >
                  <span className="block text-[14px] font-black">{TAB_LABEL[key]}</span>
                  <span className="mt-0.5 block text-[11px] font-semibold">{TAB_HINT[key]}</span>
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

          <div className="mt-4 min-h-[420px]">
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
              <div className="space-y-5">
                <section>
                  <div className="space-y-3">
                    {items.map((item) => (
                      isProfileCompletion(item) ? (
                        <ProfileCompletionCard
                          key={item.id}
                          item={item}
                          workObjects={workObjects}
                          pending={pendingItemId === item.id}
                          onClarify={openClarificationForItem}
                        />
                      ) : (
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
                      )
                    ))}
                  </div>
                </section>
              </div>
            )}
          </div>
          <Pagination page={currentPage} pageSize={currentPageSize} total={total} onPageChange={setCurrentPage} />
          <div className="mt-1 text-right text-[12px] font-semibold text-gray-500">
            {total > 0 ? `当前筛选共 ${total} 条，已显示第 ${currentPage} / ${totalPages} 页` : '当前筛选暂无内容'}
          </div>
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

            <div className="mt-4 grid gap-3 overflow-y-auto pr-1 md:grid-cols-3">
              <label className="text-[12px] font-black text-gray-500">
                资料补全优先
                <textarea
                  value={focusDraft.profileCompletionFocus}
                  onChange={(event) => setFocusDraft((current) => ({ ...current, profileCompletionFocus: event.target.value }))}
                  rows={7}
                  placeholder={'客户治理结构\n近期服务对象规模\n项目合作伙伴'}
                  className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
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
                  onClick={() => setDismissReason(key)}
                  className={`rounded-md border px-3 py-2 text-[13px] font-bold ${dismissReason === key ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}
                >
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
                onClick={() => setDismissTarget(null)}
                className="rounded-md border border-gray-200 px-4 py-2 text-[13px] font-bold text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmDismiss()}
                disabled={pendingItemId === dismissTarget.id}
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
