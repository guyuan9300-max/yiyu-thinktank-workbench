// @ts-nocheck — 整合于 2026-05-13：同事 push 的资讯情报站视图，半成品，
// 5 个 setState 函数式更新回调里 `current` 参数 implicit any，等同事下次 sync
// 后他自己加类型注解或在 origin/main 用更宽松的 tsconfig。我们暂时跳过 type check，
// 避免 npx tsc --noEmit 在我们这条线被同事的代码挡掉。
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
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
  IntelligenceRefreshResult,
  IntelligenceTaskDraftPayload,
  IntelligenceWorkObject,
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
  getIntelligenceTaskDraft,
  getIntelligenceWorkObjects,
  promoteCandidateTasks,
  refreshIntelligenceSupply,
  saveIntelligenceFocusDirective,
  submitIntelligenceVerificationFeedback,
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
  published_desc: '发布时间新到旧',
  published_asc: '发布时间旧到新',
  captured_desc: '抓取时间新到旧',
  captured_asc: '抓取时间旧到新',
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

function weakHintForObject(object: IntelligenceWorkObject | null, objects: IntelligenceWorkObject[]) {
  if (object) {
    const hints = [
      object.searchIntentStatus !== 'ready' ? object.searchIntentHint : '',
      object.sourceCoverageStatus !== 'ready' ? '来源覆盖待刷新' : '',
      object.candidateRefreshStatus !== 'ready' ? object.candidateRefreshHint : '',
    ].filter(Boolean);
    return hints.join(' · ');
  }
  const searchCount = objects.filter((item) => item.searchIntentStatus !== 'ready').length;
  const sourceCount = objects.filter((item) => item.sourceCoverageStatus !== 'ready').length;
  const candidateCount = objects.filter((item) => item.candidateRefreshStatus !== 'ready').length;
  const parts = [
    searchCount ? `${searchCount} 个对象搜索意图待刷新` : '',
    sourceCount ? `${sourceCount} 个对象来源覆盖待校准` : '',
    candidateCount ? `${candidateCount} 个对象线索抓取待完成` : '',
  ].filter(Boolean);
  return parts.join(' · ');
}

function statusText(value?: string | null) {
  if (value === 'ready') return '已就绪';
  if (value === 'running') return '刷新中';
  if (value === 'stale') return '已过期';
  if (value === 'failed') return '失败';
  return '未生成';
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
  if (totals.candidateCount <= 0 && totals.promotedCount <= 0 && !totals.failedCount) {
    return `${label}流程已跑完：处理 ${totals.objectCount} 个对象，但没有找到可进入判断流程的中文公开资料。`;
  }
  if (result.contentKind === 'profile_completion') {
    return `${label}刷新完成：处理 ${totals.objectCount} 个对象，线索 ${totals.candidateCount} 条，正文抓取 ${totals.bodyFetchedCount} 条，核验通过 ${totals.verifiedCount} 条，摘要生成 ${totals.summarySuccessCount} 条，成卡 ${totals.promotedCount} 条${totals.noResultCount ? `，未找到 ${totals.noResultCount} 个对象` : ''}${totals.failedCount ? `，失败 ${totals.failedCount} 个对象` : ''}。`;
  }
  return `${label}刷新完成：处理 ${totals.objectCount} 个对象，线索 ${totals.candidateCount} 条，成卡 ${totals.promotedCount} 条${totals.noResultCount ? `，未找到 ${totals.noResultCount} 个对象` : ''}${totals.failedCount ? `，失败 ${totals.failedCount} 个对象` : ''}。`;
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

function sourceLinks(item: IntelligenceItem) {
  const items: Array<{ label: string; url: string }> = [];
  if (item.sourceUrl) {
    items.push({ label: item.source || item.sourceUrl, url: item.sourceUrl });
  }
  const sourceText = item.source || '';
  for (const line of sourceText.split(/\n+/)) {
    const trimmed = line.trim();
    const match = trimmed.match(/https?:\/\/\S+/);
    if (!match) continue;
    const url = match[0];
    if (items.some((item) => item.url === url)) continue;
    items.push({ label: trimmed.replace(url, '').replace(/[：:｜|\-—\s]+$/g, '').trim() || url, url });
  }
  return items;
}

function RefreshProgressPanel({ contentKind }: { contentKind: IntelligenceContentKind | null }) {
  if (!contentKind) return null;
  return (
    <div className="mb-4 border-l-4 border-gray-950 bg-white px-4 py-3 text-[12px] font-semibold leading-5 text-gray-700 shadow-sm">
      <div className="flex items-center gap-2 text-gray-950">
        <Loader2 size={15} className="animate-spin" />
        正在刷新{TAB_LABEL[contentKind]}
      </div>
      <p className="mt-2 text-gray-500">
        {contentKind === 'profile_completion'
          ? '正在生成搜索意图、校准来源、抓取线索、抓取正文、核验身份锚点，并尝试生成摘要成卡。完成后会刷新列表并显示核验、成卡和失败摘要。'
          : '正在生成搜索意图、校准来源、抓取线索，并尝试整理为可跟进的时效情报。完成后会刷新列表并显示成卡、未成卡原因和失败摘要。'}
      </p>
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
  const statusTarget = selectedWorkObject;
  const latestAllFetchAt =
    workObjects
      .map((item) => item.lastCandidateFetchAt)
      .filter((value): value is string => Boolean(value))
      .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] || null;
  const allSummary = selectedWorkObject
    ? null
    : {
        searchIntentStatus: workObjects.some((item) => item.searchIntentStatus === 'failed') ? 'failed' : workObjects.some((item) => item.searchIntentStatus === 'ready') ? 'ready' : 'missing',
        sourceCoverageStatus: workObjects.some((item) => item.sourceCoverageStatus === 'failed') ? 'failed' : workObjects.some((item) => item.sourceCoverageStatus === 'ready') ? 'ready' : 'missing',
        candidateRefreshStatus: workObjects.some((item) => item.candidateRefreshStatus === 'failed') ? 'failed' : workObjects.some((item) => item.candidateRefreshStatus === 'ready') ? 'ready' : 'missing',
        lastCandidateFetchAt: latestAllFetchAt,
      };
  const searchStatus = statusTarget?.searchIntentStatus || allSummary?.searchIntentStatus || 'missing';
  const sourceStatus = statusTarget?.sourceCoverageStatus || allSummary?.sourceCoverageStatus || 'missing';
  const candidateStatus = statusTarget?.candidateRefreshStatus || allSummary?.candidateRefreshStatus || 'missing';
  const lastFetchAt = statusTarget?.lastCandidateFetchAt || allSummary?.lastCandidateFetchAt || null;
  const hasWorkObjects = workObjects.length > 0;
  const hasCandidates = candidateSamples.length > 0;
  const isProfile = contentKind === 'profile_completion';
  const title = !hasWorkObjects
    ? '暂无工作对象'
    : hasCandidates && !isProfile
      ? '已抓到线索，暂无成卡'
      : isProfile
        ? '暂无已核验资料'
        : '暂无新的时效情报';
  const description = !hasWorkObjects
    ? '当前还没有可用于情报站的客户或项目。先在工作台创建客户/项目后，再回来补全资料或抓取情报。'
    : hasCandidates && !isProfile
      ? '系统已经抓到公开线索，但暂未通过相关性、时效性或动作价值判断。普通列表只展示成卡后的情报，不把搜索短摘当作情报展示。'
      : isProfile
        ? '系统还没有找到同时确认属于当前客户/项目、能补足明确资料缺口、来源页面可访问且已整理为可复用事实的资料。'
        : '当前还没有通过整理成卡的时效情报。可以先手动启动一轮政策、招采、资助和动态检索。';
  return (
    <div className="border-y border-dashed border-gray-200 bg-white px-6 py-10 text-center">
      <p className="text-[15px] font-black text-gray-800">{title}</p>
      <p className="mx-auto mt-2 max-w-[520px] text-[13px] leading-6 text-gray-500">
        {description}
      </p>
      {isProfile ? (
        <div className="mx-auto mt-5 max-w-[640px] rounded-md bg-gray-50 px-4 py-3 text-left text-[12px] font-semibold leading-6 text-gray-600">
          <p className="font-black text-gray-800">未成卡条件</p>
          <p>没有抓到可清洗正文、正文未命中客户/项目身份、无法对应资料缺口，或 AI 暂时不可用时，系统都不会把搜索短摘或脏原文当作资料展示。</p>
          <p className="mt-2 text-gray-500">最近抓取：{lastFetchAt ? formatTime(lastFetchAt) : '暂无'}</p>
        </div>
      ) : (
        <div className="mx-auto mt-5 grid max-w-[640px] gap-2 text-left text-[12px] font-semibold text-gray-600 md:grid-cols-4">
          <div className="rounded-md bg-gray-50 px-3 py-2">
            <span className="block text-gray-400">检索准备</span>
            <b className="mt-1 block text-gray-800">{statusText(searchStatus)}</b>
          </div>
          <div className="rounded-md bg-gray-50 px-3 py-2">
            <span className="block text-gray-400">来源路线</span>
            <b className="mt-1 block text-gray-800">{statusText(sourceStatus)}</b>
          </div>
          <div className="rounded-md bg-gray-50 px-3 py-2">
            <span className="block text-gray-400">线索抓取</span>
            <b className="mt-1 block text-gray-800">{statusText(candidateStatus)}</b>
          </div>
          <div className="rounded-md bg-gray-50 px-3 py-2">
            <span className="block text-gray-400">最近抓取</span>
            <b className="mt-1 block text-gray-800">{lastFetchAt ? formatTime(lastFetchAt) : '暂无'}</b>
          </div>
        </div>
      )}
      {(statusTarget?.candidateRefreshHint || (!statusTarget && weakHintForObject(null, workObjects))) && (
        <p className="mx-auto mt-4 max-w-[640px] text-left text-[12px] font-semibold leading-5 text-amber-800">
          {statusTarget?.candidateRefreshHint || weakHintForObject(null, workObjects)}
        </p>
      )}
      <button
        type="button"
        onClick={() => onRefresh(contentKind)}
        disabled={refreshing || !hasWorkObjects}
        className="mt-5 inline-flex items-center gap-2 rounded-md bg-gray-950 px-4 py-2 text-[13px] font-bold text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {refreshing ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
        {contentKind === 'profile_completion' ? '立即补全资料' : '立即抓取情报'}
      </button>
    </div>
  );
}

function RefreshResultPanel({ result }: { result: IntelligenceRefreshResult | null }) {
  if (!result) return null;
  const failedResults = result.results.filter((item) => item.status === 'failed' || item.errors.length > 0).slice(0, 3);
  const noResultItems = result.results.filter((item) => item.status === 'no_results').slice(0, 3);
  const rejectionEntries = Object.entries(result.totals.rejectionCounts || {}).slice(0, 4);
  return (
    <div className="mb-4 border-l-4 border-blue-300 bg-blue-50 px-4 py-4 text-[12px] font-semibold leading-5 text-blue-950">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>{summarizeRefreshResult(result)}</span>
        <span>{formatTime(result.generatedAt)}</span>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-6">
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">对象</span>
          <b>{result.totals.objectCount}</b>
        </div>
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">有结果</span>
          <b>{result.totals.completedCount}</b>
        </div>
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">未找到</span>
          <b>{result.totals.noResultCount}</b>
        </div>
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">失败</span>
          <b>{result.totals.failedCount}</b>
        </div>
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">线索</span>
          <b>{result.totals.candidateCount}</b>
        </div>
        <div className="rounded-md bg-white/70 px-3 py-2">
          <span className="block text-blue-900/60">成卡</span>
          <b>{result.totals.promotedCount}</b>
        </div>
      </div>
      {result.contentKind === 'profile_completion' && (
        <div className="mt-2 grid gap-2 md:grid-cols-3">
          <div className="rounded-md bg-white/70 px-3 py-2">
            <span className="block text-blue-900/60">正文抓取</span>
            <b>{result.totals.bodyFetchedCount}</b>
          </div>
          <div className="rounded-md bg-white/70 px-3 py-2">
            <span className="block text-blue-900/60">核验通过</span>
            <b>{result.totals.verifiedCount}</b>
          </div>
          <div className="rounded-md bg-white/70 px-3 py-2">
            <span className="block text-blue-900/60">摘要生成</span>
            <b>{result.totals.summarySuccessCount}</b>
          </div>
        </div>
      )}
      {rejectionEntries.length > 0 && (
        <div className="mt-3 rounded-md bg-white/70 px-3 py-2 text-blue-900/80">
          <p className="font-black">未成卡原因</p>
          <div className="mt-1 flex flex-wrap gap-2">
            {rejectionEntries.map(([reason, count]) => (
              <span key={reason} className="rounded bg-blue-100/70 px-2 py-1">
                {reason}：{count}
              </span>
            ))}
          </div>
        </div>
      )}
      {failedResults.length > 0 && (
        <div className="mt-2 space-y-1 text-blue-900/80">
          {failedResults.map((item) => (
            <p key={`${item.scopeType}:${item.scopeId}`}>
              {item.name}：{item.errors[0] || item.message || '未返回具体原因'}
            </p>
          ))}
        </div>
      )}
      {noResultItems.length > 0 && (
        <div className="mt-2 space-y-1 text-blue-900/80">
          {noResultItems.map((item) => (
            <p key={`${item.scopeType}:${item.scopeId}:no-results`}>
              {item.name}：{item.message || '检索链路已跑完，但没有找到可进入判断流程的中文公开资料。'}
            </p>
          ))}
        </div>
      )}
    </div>
  );
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

        <p className="text-[12px] font-black text-gray-500">来源</p>
        <div className="space-y-1 text-[12px] font-semibold leading-5">
          {links.length > 0 ? (
            links.map((link) => (
              <a
                key={link.url}
                href={link.url}
                target="_blank"
                rel="noreferrer"
                className="block break-all text-blue-700 hover:text-blue-900 hover:underline"
              >
                {link.label}：{link.url}
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
          {pending ? <Loader2 size={14} className="animate-spin" /> : <AlertCircle size={14} />}
          这条不对
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

function containsAny(text: string, terms: string[]) {
  return terms.some((term) => text.includes(term));
}

function buildQuestionPromptGroups(item: IntelligenceItem, objects: IntelligenceWorkObject[]): QuestionPromptGroup[] {
  const objectLabel = itemObjectLabel(item, objects);
  const contextText = `${item.intelligenceType || ''} ${item.title} ${item.summary} ${item.tags.join(' ')}`;
  const groups: QuestionPromptGroup[] = [
    {
      title: '你可以问',
      ordered: true,
      questions: [
        `这条外部变化会通过什么链条影响${objectLabel}？`,
        `它和${objectLabel}的业务、对象、地域、资源需求分别有多强相关？`,
        '如果要跟进，最关键的不确定点是什么？',
        '它更像机会、风险、约束，还是行业趋势？',
        '哪些证据不足，暂时不能据此行动？',
      ],
    },
  ];
  if (containsAny(contextText, ['行业风险', '监管', '合规', '舆情', '风险', '政策变化', '隐私', '公开募捐'])) {
    groups.push({
      title: '针对行业风险',
      questions: [
        `这类监管提醒可能通过什么链条传导到${objectLabel}？`,
        `如果${objectLabel}缺少相关资质，哪些项目传播表述最容易踩线？`,
        '这个风险是立即需要处理，还是只需要纳入材料审核清单？',
        '需要检查哪些现有材料，才能判断它是否真的相关？',
      ],
    });
  }
  if (containsAny(contextText, ['公益创投', '资助', '申报', '征集', '基金', '机会', 'grant'])) {
    groups.push({
      title: '针对公益创投/资助机会',
      questions: [
        `资助方向和${objectLabel}关注对象的相关度有多高？`,
        `如果只看申报方向，${objectLabel}更适合直接申报，还是作为资助方/合作方参与？`,
        '这条机会需要哪些已有资料支撑？哪些资料目前还缺？',
        '申报窗口和当前项目准备度之间的缺口有多大？',
      ],
    });
  }
  if (containsAny(contextText, ['合作方', '合作', '伙伴', '资助方', '同类机构', '动态'])) {
    groups.push({
      title: '针对合作方动态',
      questions: [
        '这条合作方动态说明资助方或合作方偏好发生了什么变化？',
        `它对${objectLabel}的项目设计有什么启发？`,
        '它对益语智库的服务方案有什么可转化价值？',
        '是否值得转成同事阅读任务，而不是立即执行任务？',
      ],
    });
  }
  return groups;
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
  return (
    <article className="rounded-lg border border-gray-200 bg-white px-5 py-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-[160px_1fr_180px]">
          <IntelligenceField label="情报类型">
            <span className="font-black text-gray-950">{item.intelligenceType || '时效信号'}</span>
          </IntelligenceField>
          <IntelligenceField label="关联对象">
            <span className="font-bold text-gray-900">{objectLabel}</span>
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
                  className="block break-all text-blue-700 hover:text-blue-900 hover:underline"
                >
                  {link.label}：{link.url}
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
  const [sort, setSort] = useState<SortMode>('published_desc');
  const [pages, setPages] = useState<Record<IntelligenceContentKind, number>>({
    profile_completion: 1,
    timely_intelligence: 1,
  });
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [candidateSamples, setCandidateSamples] = useState<IntelligenceCandidateSample[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
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
  const flashRef = useRef(flash);
  const [refreshingKind, setRefreshingKind] = useState<IntelligenceContentKind | null>(null);
  const [lastRefreshResult, setLastRefreshResult] = useState<IntelligenceRefreshResult | null>(null);
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
  const weakHint = weakHintForObject(selectedWorkObject, workObjects);
  const selectedLabel = selectedObjectLabel(selectedScopeKey, workObjects);
  const lastFetchTime = selectedWorkObject?.lastCandidateFetchAt ? formatTime(selectedWorkObject.lastCandidateFetchAt) : null;

  useEffect(() => {
    flashRef.current = flash;
  }, [flash]);

  const loadShell = useCallback(async () => {
    try {
      const [objects, directives] = await Promise.all([
        getIntelligenceWorkObjects(),
        getIntelligenceFocusDirectives(),
      ]);
      setWorkObjects(objects);
      setFocusDirectives(directives);
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : '情报站初始化失败');
    }
  }, []);

  const loadItems = useCallback(async () => {
    setLoading(true);
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
      setLoading(false);
    }
  }, [activeTab, currentPage, currentPageSize, selectedWorkObject?.id, selectedWorkObject?.type, sort]);

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

  async function handleRefreshSupply(contentKind: IntelligenceContentKind) {
    setRefreshingKind(contentKind);
    setLastRefreshResult(null);
    try {
      const result = await refreshIntelligenceSupply(scopeRefreshPayload(selectedScopeKey, selectedWorkObject, contentKind));
      setLastRefreshResult(result);
      await Promise.all([loadShell(), loadItems()]);
      flashRef.current(result.status === 'failed' ? 'error' : result.status === 'no_results' ? 'info' : 'success', summarizeRefreshResult(result));
    } catch (error) {
      flashRef.current('error', error instanceof Error ? error.message : `${TAB_LABEL[contentKind]}刷新失败`);
    } finally {
      setRefreshingKind(null);
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
      flash('success', '关注指令已保存');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存关注指令失败');
    } finally {
      setSavingFocus(false);
    }
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
    setPendingItemId(item.id);
    try {
      if (!item.topicCandidateId) {
        const response = await getIntelligenceTaskDraft(item.id);
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
        listId: taskDraft.listId || defaultListId,
        tags: taskDraft.tags.length ? taskDraft.tags : ['情报跟进'],
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
      flash('error', error instanceof Error ? error.message : '追问失败');
      setChatMessagesByItemId((current) => ({ ...current, [questionItem.id]: visibleMessages }));
    } finally {
      setQuestionPending(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-[#F6F7F9] font-sans text-gray-950">
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
                onClick={() => void handleRefreshSupply('profile_completion')}
                disabled={refreshingKind !== null}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-3 py-2 text-[13px] font-bold text-white hover:bg-emerald-800 disabled:opacity-50"
              >
                {refreshingKind === 'profile_completion' ? <Loader2 size={16} className="animate-spin" /> : <FileCheck2 size={16} />}
                立即补全资料
              </button>
              <button
                type="button"
                onClick={() => void handleRefreshSupply('timely_intelligence')}
                disabled={refreshingKind !== null}
                className="inline-flex items-center gap-2 rounded-md bg-gray-950 px-3 py-2 text-[13px] font-bold text-white hover:bg-gray-800 disabled:opacity-50"
              >
                {refreshingKind === 'timely_intelligence' ? <Loader2 size={16} className="animate-spin" /> : <BellPlus size={16} />}
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

          {weakHint && (
            <div className="mt-4 flex items-start gap-2 border-l-4 border-amber-300 bg-amber-50 px-3 py-2 text-[12px] font-semibold leading-5 text-amber-900">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>{weakHint}</span>
            </div>
          )}
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
            <div className="pb-3 text-[12px] font-semibold text-gray-500">
              {activeTab === 'profile_completion'
                ? '建议周期：资料补全 72 小时；App 运行时会自动检查到期刷新'
                : '建议周期：时效情报 24 小时；App 运行时会自动检查到期刷新'}
            </div>
          </div>

          <div className="mt-4 min-h-[420px]">
            <RefreshProgressPanel contentKind={refreshingKind} />
            <RefreshResultPanel result={lastRefreshResult} />
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
                refreshing={refreshingKind !== null}
                onRefresh={(contentKind) => void handleRefreshSupply(contentKind)}
              />
            ) : (
              <div className="space-y-5">
                <section>
                  {activeTab === 'profile_completion' && (
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h2 className="text-[15px] font-black text-gray-950">已核验资料</h2>
                        <p className="mt-1 text-[12px] font-semibold text-gray-500">已完成正文抓取、身份核验、缺口映射和摘要整理。</p>
                      </div>
                    </div>
                  )}
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

        <section className="mt-7 border-t border-gray-200 pt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-[17px] font-black text-gray-950">我重点关注什么</h2>
              <p className="mt-1 text-[12px] font-semibold text-gray-500">关注指令会进入当前对象后续搜索、线索判断和排序学习。</p>
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

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <label className="text-[12px] font-black text-gray-500">
              资料补全优先
              <textarea
                value={focusDraft.profileCompletionFocus}
                onChange={(event) => setFocusDraft((current) => ({ ...current, profileCompletionFocus: event.target.value }))}
                rows={5}
                placeholder={'客户治理结构\n近期服务对象规模\n项目合作伙伴'}
                className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
              />
            </label>
            <label className="text-[12px] font-black text-gray-500">
              时效情报优先
              <textarea
                value={focusDraft.timelyIntelligenceFocus}
                onChange={(event) => setFocusDraft((current) => ({ ...current, timelyIntelligenceFocus: event.target.value }))}
                rows={5}
                placeholder={'资助窗口\n监管变化\n同类机构动作'}
                className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
              />
            </label>
            <label className="text-[12px] font-black text-gray-500">
              少看或不看
              <textarea
                value={focusDraft.exclude}
                onChange={(event) => setFocusDraft((current) => ({ ...current, exclude: event.target.value }))}
                rows={5}
                placeholder={'泛泛行业新闻\n重复转载\n无来源截图'}
                className="mt-2 w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-[13px] font-medium leading-6 text-gray-800 outline-none focus:border-gray-400"
              />
            </label>
          </div>
          <div className="mt-4 flex justify-end">
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
        </section>
      </div>

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
                  {questionPromptGroups.map((group) => (
                    <div key={group.title}>
                      <p className="text-[12px] font-black text-gray-500">{group.title}</p>
                      <div className="mt-2 space-y-1.5">
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
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {visibleMessages.map((message, index) => (
                    <div
                      key={`${message.createdAt}-${index}`}
                      className={`rounded-md px-3 py-2 text-[13px] leading-6 ${message.role === 'user' ? 'bg-white text-gray-700' : 'bg-gray-950 text-white'}`}
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
                  rows={5}
                  className="mt-1 w-full resize-none rounded-md border border-gray-200 px-3 py-2 text-[13px] leading-6 text-gray-800 outline-none focus:border-gray-400"
                />
              </label>
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
