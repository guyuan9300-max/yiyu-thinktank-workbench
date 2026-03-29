import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  Brain,
  CheckCircle2,
  ClipboardList,
  Compass,
  Copy,
  Eye,
  EyeOff,
  FileText,
  Flag,
  Layers,
  Loader2,
  Map as MapIcon,
  PlusSquare,
  Sparkles,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react';

import { applyStrategicMeetingPack, confirmStrategicCockpit, createStrategicMeetingPack, getStrategicCockpit } from '../../lib/api';
import type {
  ClientSummary,
  ClientWorkspace,
  GrowthContextLink,
  MeetingSummary,
  ReviewDashboard,
  StrategicChecklistGroup,
  StrategicChecklistItem,
  StrategicCockpitConfirmPayload,
  StrategicCockpitSnapshot,
  Task,
} from '../../../shared/types';

type StrategicView = 'overview' | 'lines' | 'health' | 'checklist' | 'evidence' | 'assets';

type StrategicAccompanimentShellProps = {
  clients: ClientSummary[];
  currentClientId?: string | null;
  workspace?: ClientWorkspace | null;
  tasks?: Task[];
  reviewDashboard?: ReviewDashboard | null;
  onClientChange?: (clientId: string) => void;
  jumpRequest?: { requestId: string; context: GrowthContextLink } | null;
  onConsumeJump?: (requestId: string) => void;
};

const VIEW_ITEMS: Array<{ key: StrategicView; label: string; helper: string; icon: React.ComponentType<{ size?: number; className?: string }> }> = [
  { key: 'overview', label: '总览', helper: '本周最重要的经营判断', icon: Compass },
  { key: 'lines', label: '战略线', helper: '哪几条线最值得盯', icon: MapIcon },
  { key: 'health', label: '组织健康', helper: '方向、承接、协同、决策、沉淀', icon: TrendingUp },
  { key: 'checklist', label: '周会清单', helper: '下次周会该讨论什么', icon: ClipboardList },
  { key: 'evidence', label: '证据与底稿', helper: '这些判断来自哪里', icon: BookOpen },
  { key: 'assets', label: '资产沉淀', helper: '这条业务留下什么', icon: Layers },
];

function judgmentStatusTone(status: StrategicCockpitSnapshot['headline']['weekSummary']['status']) {
  switch (status) {
    case 'confirmed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'waiting':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
}

function healthTone(status: StrategicCockpitSnapshot['health'][number]['status']) {
  switch (status) {
    case 'healthy':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'watch':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'risk':
      return 'border-rose-200 bg-rose-50 text-rose-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
}

function priorityTone(priority: StrategicChecklistItem['priority']) {
  switch (priority) {
    case 'high':
      return 'border-rose-200 bg-rose-50 text-rose-700';
    case 'medium':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
}

function momentumTone(momentum: StrategicCockpitSnapshot['strategicLines'][number]['momentum']) {
  switch (momentum) {
    case '加码':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case '收口':
      return 'border-slate-200 bg-slate-100 text-slate-700';
    case '暂停':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    default:
      return 'border-sky-200 bg-sky-50 text-sky-700';
  }
}

function predictionReadinessTone(score?: number | null) {
  if ((score || 0) >= 0.72) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if ((score || 0) >= 0.5) return 'border-sky-200 bg-sky-50 text-sky-700';
  return 'border-amber-200 bg-amber-50 text-amber-700';
}

function formatReadinessPercent(score?: number | null) {
  return `${Math.round(Math.max(0, Math.min(1, score || 0)) * 100)}%`;
}

function buildLogo(source?: string | null) {
  const text = (source || '业').trim();
  return text.slice(0, 1).toUpperCase();
}

function buildMeetingPackText(clientName: string, groups: StrategicChecklistGroup[], agenda: string[]) {
  const lines: string[] = [`${clientName} 周盘点会`, ''];
  if (agenda.length > 0) {
    lines.push('建议议程');
    for (const item of agenda) {
      lines.push(`- ${item}`);
    }
    lines.push('');
  }
  for (const group of groups) {
    lines.push(`${group.title}`);
    lines.push(group.description);
    for (const item of group.items) {
      lines.push(`- ${item.title}`);
      lines.push(`  说明：${item.detail}`);
      lines.push(`  来源：${item.source}`);
    }
    lines.push('');
  }
  return lines.join('\n').trim();
}

function normalizeDraft(snapshot: StrategicCockpitSnapshot): StrategicCockpitConfirmPayload {
  return {
    weekSummary: snapshot.headline.weekSummary.value,
    mainContradiction: snapshot.headline.mainContradiction.value,
    coreBreakthrough: snapshot.headline.coreBreakthrough.value,
    focusItems: [...snapshot.headline.focusItems],
  };
}

function OverviewPanel({
  snapshot,
  draft,
  editing,
  setDraft,
}: {
  snapshot: StrategicCockpitSnapshot;
  draft: StrategicCockpitConfirmPayload;
  editing: boolean;
  setDraft: React.Dispatch<React.SetStateAction<StrategicCockpitConfirmPayload>>;
}) {
  const headlineCards = [
    { key: 'weekSummary', title: '本周一句话', judgment: snapshot.headline.weekSummary, draftValue: draft.weekSummary },
    { key: 'mainContradiction', title: '主矛盾', judgment: snapshot.headline.mainContradiction, draftValue: draft.mainContradiction },
    { key: 'coreBreakthrough', title: '核心突破', judgment: snapshot.headline.coreBreakthrough, draftValue: draft.coreBreakthrough },
  ] as const;

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-blue-100 bg-[linear-gradient(180deg,#F7FAFF_0%,#FFFFFF_100%)] p-6 shadow-sm">
        <div className="flex flex-wrap items-start gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#5B7BFE]">经营判断总览</p>
            <h2 className="mt-3 text-[30px] font-semibold tracking-tight text-slate-900">{snapshot.clientName}</h2>
            <p className="mt-2 max-w-4xl text-sm leading-7 text-slate-600">{snapshot.clientTagline}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
              当前阶段：{snapshot.stageLabel}
            </span>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${snapshot.readiness.status === 'ready' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
              判断准备度 {snapshot.readiness.score}
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-500">
              信息鲜度：{snapshot.headline.freshness}
            </span>
          </div>
        </div>
        <div className="mt-5 rounded-3xl border border-slate-200 bg-white/80 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">判断准备度说明</p>
          <p className="mt-2 text-sm leading-7 text-slate-700">{snapshot.readiness.summary}</p>
          {snapshot.readiness.gaps.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {snapshot.readiness.gaps.slice(0, 4).map((gap) => (
                <span key={gap} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                  {gap}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {headlineCards.map((card) => (
          <article key={card.key} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">{card.title}</p>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${judgmentStatusTone(card.judgment.status)}`}>
                {card.judgment.status === 'confirmed' ? '已确认' : card.judgment.status === 'waiting' ? '待澄清' : '系统草案'}
              </span>
            </div>
            {editing ? (
              <textarea
                value={card.draftValue}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    [card.key]: event.target.value,
                  }))
                }
                className="mt-4 h-32 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700 outline-none transition-colors focus:border-[#5B7BFE] focus:bg-white"
              />
            ) : (
              <p className="mt-4 text-[18px] font-semibold leading-8 text-slate-900">{card.judgment.value}</p>
            )}
            <div className="mt-4 space-y-2">
              {card.judgment.sources.map((source) => (
                <div key={source} className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-500">
                  来源：{source}
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className="space-y-6">
          {(snapshot.notebookSummary || snapshot.memoryStatus) ? (
            <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">底座状态</p>
                  <h3 className="mt-2 text-lg font-semibold text-slate-900">组织笔记与事件线记忆</h3>
                </div>
                {snapshot.memoryStatus ? (
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${snapshot.memoryStatus.pendingClarifications > 0 || snapshot.memoryStatus.lowEvidenceJudgments > 0 ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
                    待澄清 {snapshot.memoryStatus.pendingClarifications} · 低证据判断 {snapshot.memoryStatus.lowEvidenceJudgments}
                  </span>
                ) : null}
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">组织笔记完整度</p>
                  <p className="mt-2 text-xl font-semibold text-slate-900">{formatReadinessPercent(snapshot.memoryStatus?.notebookCompleteness)}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">组织笔记置信度</p>
                  <p className="mt-2 text-xl font-semibold text-slate-900">{formatReadinessPercent(snapshot.memoryStatus?.notebookConfidence)}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">事件线覆盖率</p>
                  <p className="mt-2 text-xl font-semibold text-slate-900">
                    {snapshot.memoryStatus ? `${snapshot.memoryStatus.coveredEventLines}/${snapshot.memoryStatus.totalEventLines}` : '0/0'}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">当前组织阶段</p>
                  <p className="mt-2 text-lg font-semibold text-slate-900">{snapshot.notebookSummary?.currentStage || snapshot.stageLabel}</p>
                </div>
              </div>
              {snapshot.notebookSummary?.informationGaps?.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {snapshot.notebookSummary.informationGaps.slice(0, 4).map((gap) => (
                    <span key={gap} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                      待补：{gap}
                    </span>
                  ))}
                </div>
              ) : null}
            </article>
          ) : null}

          <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">本期聚焦</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">本周期只抓的事</h3>
              </div>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${judgmentStatusTone(snapshot.headline.focusStatus)}`}>
                {snapshot.headline.focusStatus === 'confirmed' ? '已确认' : snapshot.headline.focusStatus === 'waiting' ? '待澄清' : '系统草案'}
              </span>
            </div>
            {editing ? (
              <div className="mt-4 space-y-3">
                {[0, 1, 2].map((index) => (
                  <textarea
                    key={index}
                    value={draft.focusItems[index] || ''}
                    placeholder={`聚焦 ${index + 1}`}
                    onChange={(event) =>
                      setDraft((current) => {
                        const next = [...current.focusItems];
                        next[index] = event.target.value;
                        return { ...current, focusItems: next };
                      })
                    }
                    className="h-20 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700 outline-none transition-colors focus:border-[#5B7BFE] focus:bg-white"
                  />
                ))}
              </div>
            ) : (
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {snapshot.headline.focusItems.map((item) => (
                  <div key={item} className="rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-4 text-sm leading-7 text-[#3655D4]">
                    {item}
                  </div>
                ))}
              </div>
            )}
          </article>

          <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">组织健康总览</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {snapshot.health.map((item) => (
                <div key={item.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-slate-900">{item.title}</h4>
                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${healthTone(item.status)}`}>
                      {item.status === 'healthy' ? '健康' : item.status === 'watch' ? '关注' : item.status === 'risk' ? '风险' : '待校准'}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{item.summary}</p>
                  <p className="mt-3 text-xs font-semibold text-slate-400">趋势：{item.trend}</p>
                  <ul className="mt-3 space-y-2">
                    {item.evidence.map((evidence) => (
                      <li key={evidence} className="text-xs leading-6 text-slate-500">
                        {evidence}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </article>
        </div>

        <div className="space-y-6">
          <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">两周变化点</p>
            <div className="mt-4 space-y-3">
              {snapshot.twoWeekChanges.map((item) => (
                <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-slate-900">{item.title}</h4>
                    <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-500">
                      {item.confidence}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{item.summary}</p>
                  <ul className="mt-3 space-y-2">
                    {item.signals.map((signal) => (
                      <li key={signal} className="text-xs leading-6 text-slate-500">
                        {signal}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">本周关键事实</p>
            <div className="mt-4 grid gap-3">
              {snapshot.evidencePreview.keyFacts.map((item) => (
                <div key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700">
                  {item}
                </div>
              ))}
            </div>
            {snapshot.evidencePreview.keyWarnings.length > 0 ? (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-600">当前提醒</p>
                <ul className="mt-3 space-y-2">
                  {snapshot.evidencePreview.keyWarnings.map((item) => (
                    <li key={item} className="text-sm leading-7 text-amber-700">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
        </div>
      </section>
    </div>
  );
}

function StrategicLinesPanel({
  snapshot,
  highlightedLineId,
  highlightedLabel,
}: {
  snapshot: StrategicCockpitSnapshot;
  highlightedLineId?: string | null;
  highlightedLabel?: string | null;
}) {
  return (
    <div className="space-y-4">
      {snapshot.strategicLines.map((line) => {
        const isHighlighted = Boolean(
          (highlightedLineId && line.id === highlightedLineId)
          || (highlightedLabel && (line.title.includes(highlightedLabel) || highlightedLabel.includes(line.title))),
        );
        return (
          <article
            key={line.id}
            className={`rounded-3xl border bg-white p-5 shadow-sm ${isHighlighted ? 'border-blue-200 ring-2 ring-blue-100' : 'border-slate-200'}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-slate-900">{line.title}</h3>
                  {isHighlighted ? (
                    <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-[11px] font-semibold text-blue-700">成长呼应</span>
                  ) : null}
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${momentumTone(line.momentum)}`}>{line.momentum}</span>
                  {line.predictionReadiness != null ? (
                    <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${predictionReadinessTone(line.predictionReadiness)}`}>
                      预测准备度 {formatReadinessPercent(line.predictionReadiness)}
                    </span>
                  ) : null}
                  {line.stage ? (
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-500">
                      {line.stage}
                    </span>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-700">{line.summary}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                {line.module ? <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">{line.module}</span> : null}
                {line.flow ? <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">{line.flow}</span> : null}
              </div>
            </div>
            <div className="mt-5 grid gap-4 lg:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">当前主阻塞</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">{line.blocker}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">最近关键决策</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">{line.decision}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">下一步</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">{line.nextStep}</p>
              </div>
            </div>
            {line.evidence.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {line.evidence.map((item) => (
                  <span key={item} className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs text-blue-700">
                    {item}
                  </span>
                ))}
              </div>
            ) : null}
            {(line.memoryConfidence != null || (line.clarificationNeeds || []).length > 0) ? (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  {line.memoryConfidence != null ? (
                    <span>记忆置信度 {formatReadinessPercent(line.memoryConfidence)}</span>
                  ) : null}
                  {(line.clarificationNeeds || []).length > 0 ? (
                    <span>待澄清 {(line.clarificationNeeds || []).length} 项</span>
                  ) : null}
                </div>
                {(line.clarificationNeeds || []).length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {line.clarificationNeeds!.slice(0, 3).map((item) => (
                      <span key={item} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                        {item}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function StrategicHealthPanel({ snapshot }: { snapshot: StrategicCockpitSnapshot }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {snapshot.health.map((item) => (
        <article key={item.key} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{item.title}</p>
              <h3 className="mt-2 text-xl font-semibold text-slate-900">{item.trend}</h3>
            </div>
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${healthTone(item.status)}`}>
              {item.status === 'healthy' ? '健康' : item.status === 'watch' ? '关注' : item.status === 'risk' ? '风险' : '待校准'}
            </span>
          </div>
          <p className="mt-4 text-sm leading-7 text-slate-700">{item.summary}</p>
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">证据</p>
            <ul className="mt-3 space-y-2">
              {item.evidence.map((evidence) => (
                <li key={evidence} className="text-sm leading-7 text-slate-600">
                  {evidence}
                </li>
              ))}
            </ul>
          </div>
        </article>
      ))}
    </div>
  );
}

function ChecklistPanel({ snapshot }: { snapshot: StrategicCockpitSnapshot }) {
  return (
    <div className="space-y-5">
      {snapshot.meetingPackDraft.groups.map((group) => (
        <article key={group.key} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">{group.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">{group.description}</p>
            </div>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-500">
              {group.items.length} 条
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {group.items.map((item) => (
              <div key={`${group.key}-${item.title}-${item.detail}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <h4 className="text-sm font-semibold leading-7 text-slate-900">{item.title}</h4>
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${priorityTone(item.priority)}`}>
                    {item.priority === 'high' ? '高' : item.priority === 'medium' ? '中' : '低'}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-7 text-slate-700">{item.detail}</p>
                <p className="mt-3 text-xs text-slate-500">来源：{item.source}</p>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function EvidencePanel({ snapshot }: { snapshot: StrategicCockpitSnapshot }) {
  const notebook = snapshot.notebookSummary;
  const memoryStatus = snapshot.memoryStatus;
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">组织业务笔记摘要</p>
        <p className="mt-4 text-sm leading-7 text-slate-700">{notebook?.organizationIntro || snapshot.evidencePreview.summary}</p>
        {notebook?.collaborationRelationship ? (
          <p className="mt-3 text-sm leading-7 text-slate-600">合作关系：{notebook.collaborationRelationship}</p>
        ) : null}
        {notebook?.collaborationGoals?.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {notebook.collaborationGoals.slice(0, 4).map((goal) => (
              <span key={goal} className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs text-blue-700">
                {goal}
              </span>
            ))}
          </div>
        ) : null}
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {snapshot.evidencePreview.cards.map((card) => (
          <article key={card.label} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{card.label}</p>
            <p className="mt-3 text-lg font-semibold text-slate-900">{card.value}</p>
          </article>
        ))}
        {memoryStatus ? (
          <>
            <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">事件线覆盖</p>
              <p className="mt-3 text-lg font-semibold text-slate-900">{memoryStatus.coveredEventLines}/{memoryStatus.totalEventLines}</p>
            </article>
            <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">待澄清问题</p>
              <p className="mt-3 text-lg font-semibold text-slate-900">{memoryStatus.pendingClarifications}</p>
            </article>
            <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">低证据判断</p>
              <p className="mt-3 text-lg font-semibold text-slate-900">{memoryStatus.lowEvidenceJudgments}</p>
            </article>
          </>
        ) : null}
      </section>
      <section className="grid gap-6 xl:grid-cols-2">
        <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">关键事实</p>
          <ul className="mt-4 space-y-3">
            {snapshot.evidencePreview.keyFacts.map((item) => (
              <li key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700">
                {item}
              </li>
            ))}
          </ul>
        </article>
        <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">边界与缺口</p>
          <ul className="mt-4 space-y-3">
            {[...snapshot.evidencePreview.boundaries, ...snapshot.evidencePreview.keyWarnings].map((item) => (
              <li key={item} className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-700">
                {item}
              </li>
            ))}
          </ul>
        </article>
      </section>
      {(snapshot.linkedEventLineMemories || []).length > 0 ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">事件线连续记忆</p>
          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            {(snapshot.linkedEventLineMemories || []).slice(0, 6).map((item) => (
              <article key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h4 className="text-sm font-semibold text-slate-900">{item.lineName}</h4>
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${predictionReadinessTone(item.predictionReadiness)}`}>
                    预测准备度 {formatReadinessPercent(item.predictionReadiness)}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-700">当前事项：{item.currentWork || '待补'}</p>
                <p className="mt-2 text-sm leading-7 text-slate-700">当前阻塞：{item.currentBlocker || '待补'}</p>
                <p className="mt-2 text-sm leading-7 text-slate-700">下一步：{item.nextStep || '待补'}</p>
                {item.clarificationNeeds.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.clarificationNeeds.slice(0, 3).map((slot) => (
                      <span key={slot} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                        {slot}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function AssetsPanel({ snapshot }: { snapshot: StrategicCockpitSnapshot }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {snapshot.assetCandidates.map((item) => (
        <article key={`${item.title}-${item.source}`} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold text-slate-900">{item.title}</h3>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-500">
              {item.source}
            </span>
          </div>
          <p className="mt-4 text-sm leading-7 text-slate-700">{item.summary}</p>
          <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-7 text-blue-700">
            下一步：{item.nextAction}
          </div>
        </article>
      ))}
    </div>
  );
}

function ActionRail({
  snapshot,
  canOperate,
  onCopyChecklist,
  onCreateMeetingDraft,
  onApplyMeeting,
  runningAction,
  latestMeeting,
}: {
  snapshot: StrategicCockpitSnapshot;
  canOperate: boolean;
  onCopyChecklist: () => Promise<void>;
  onCreateMeetingDraft: () => Promise<void>;
  onApplyMeeting: () => Promise<void>;
  runningAction: 'copy' | 'meeting' | 'apply' | null;
  latestMeeting: MeetingSummary | null;
}) {
  return (
    <aside className="space-y-5">
      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <Target size={18} className="text-[#5B7BFE]" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">本期聚焦</h3>
            <p className="mt-1 text-sm text-slate-500">这一列负责把判断压成动作。</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {snapshot.headline.focusItems.map((item) => (
            <div key={item} className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-7 text-[#3655D4]">
              {item}
            </div>
          ))}
        </div>
      </article>

      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <Flag size={18} className="text-amber-500" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">待决策</h3>
            <p className="mt-1 text-sm text-slate-500">这些项不拍板，下周推进容易继续失焦。</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {snapshot.pendingDecisions.map((item) => (
            <div key={`${item.title}-${item.detail}`} className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-slate-900">{item.title}</h4>
                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${priorityTone(item.priority)}`}>
                  {item.priority === 'high' ? '高' : item.priority === 'medium' ? '中' : '低'}
                </span>
              </div>
              <p className="mt-2 text-sm leading-7 text-slate-700">{item.detail}</p>
              <p className="mt-2 text-xs text-slate-500">来源：{item.source}</p>
            </div>
          ))}
        </div>
      </article>

      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <AlertCircle size={18} className="text-[#5B7BFE]" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">待补资料</h3>
            <p className="mt-1 text-sm text-slate-500">这些证据不到位，很多判断只能保守表达。</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {snapshot.pendingMaterials.map((item) => (
            <div key={`${item.title}-${item.detail}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <h4 className="text-sm font-semibold text-slate-900">{item.title}</h4>
              <p className="mt-2 text-sm leading-7 text-slate-700">{item.detail}</p>
              <p className="mt-2 text-xs text-slate-500">来源：{item.source}</p>
            </div>
          ))}
        </div>
      </article>

      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <ClipboardList size={18} className="text-[#5B7BFE]" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">周会动作</h3>
            <p className="mt-1 text-sm text-slate-500">{snapshot.meetingPackDraft.title}</p>
          </div>
        </div>
        <ul className="mt-4 space-y-2">
          {snapshot.meetingPackDraft.agenda.map((item) => (
            <li key={item} className="text-sm leading-7 text-slate-700">
              {item}
            </li>
          ))}
        </ul>
        <div className="mt-5 grid gap-3">
          <button
            type="button"
            disabled={!canOperate || runningAction !== null}
            onClick={() => void onCopyChecklist()}
            className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${canOperate ? 'bg-white text-slate-700 border border-slate-200 hover:border-blue-200 hover:text-[#3655D4]' : 'border border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'}`}
          >
            {runningAction === 'copy' ? <Loader2 size={16} className="animate-spin" /> : <Copy size={16} />}
            复制周会清单
          </button>
          <button
            type="button"
            disabled={!canOperate || runningAction !== null}
            onClick={() => void onCreateMeetingDraft()}
            className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${canOperate ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}
          >
            {runningAction === 'meeting' ? <Loader2 size={16} className="animate-spin" /> : <PlusSquare size={16} />}
            创建正式周会草稿
          </button>
          <button
            type="button"
            disabled={!canOperate || !latestMeeting || runningAction !== null}
            onClick={() => void onApplyMeeting()}
            className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${canOperate && latestMeeting ? 'border border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:text-[#3655D4]' : 'border border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'}`}
          >
            {runningAction === 'apply' ? <Loader2 size={16} className="animate-spin" /> : <Brain size={16} />}
            用最近周会回填判断
          </button>
        </div>
        {latestMeeting ? (
          <p className="mt-3 text-xs leading-6 text-slate-500">当前将使用《{latestMeeting.title}》回填战略判断。</p>
        ) : (
          <div className="mt-3">
            <p className="text-[13px] font-bold text-slate-500">暂无可用周会记录</p>
            <p className="text-[12px] text-slate-400 mt-1">请先在周会模块中创建一条会议记录，即可用于回填战略判断。</p>
          </div>
        )}
      </article>
    </aside>
  );
}

export function StrategicAccompanimentShell({
  clients,
  currentClientId,
  workspace,
  tasks,
  reviewDashboard,
  onClientChange,
  jumpRequest,
  onConsumeJump,
}: StrategicAccompanimentShellProps) {
  const [view, setView] = useState<StrategicView>('overview');
  const [immersive, setImmersive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningAction, setRunningAction] = useState<'copy' | 'meeting' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<StrategicCockpitSnapshot | null>(null);
  const [editing, setEditing] = useState(false);
  const [createdMeetingDraft, setCreatedMeetingDraft] = useState<MeetingSummary | null>(null);
  const [highlightedStrategicLabel, setHighlightedStrategicLabel] = useState<string | null>(null);
  const [highlightedStrategicLineId, setHighlightedStrategicLineId] = useState<string | null>(null);
  const [draft, setDraft] = useState<StrategicCockpitConfirmPayload>({
    weekSummary: '',
    mainContradiction: '',
    coreBreakthrough: '',
    focusItems: [],
  });

  const selectedClient = useMemo(() => {
    const byId = clients.find((item) => item.id === currentClientId);
    if (byId) return byId;
    if (workspace?.client && workspace.client.id === currentClientId) {
      return workspace.client;
    }
    return clients[0] || workspace?.client || null;
  }, [clients, currentClientId, workspace]);

  useEffect(() => {
    if (!currentClientId) {
      setSnapshot(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotice(null);
    void getStrategicCockpit(currentClientId)
      .then((response) => {
        if (cancelled) return;
        setSnapshot(response);
        setDraft(normalizeDraft(response));
        setEditing(false);
        setCreatedMeetingDraft(null);
      })
      .catch((loadError) => {
        if (cancelled) return;
        setError(loadError instanceof Error ? loadError.message : '战略陪伴数据加载失败。');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentClientId, workspace?.client?.updatedAt, tasks?.length, reviewDashboard?.currentReview?.updatedAt]);

  useEffect(() => {
    if (!jumpRequest) return;
    const { requestId, context } = jumpRequest;
    if (!['strategic_focus', 'client'].includes(context.objectType) && context.tab !== 'strategic_accompaniment') return;
    if (context.objectType === 'client') {
      if (context.objectId && context.objectId !== currentClientId) {
        onClientChange?.(context.objectId);
      }
      setView('overview');
      setHighlightedStrategicLineId(null);
      setHighlightedStrategicLabel(null);
      setNotice(`已切到项目「${context.label}」的战略视角。`);
      onConsumeJump?.(requestId);
      return;
    }
    if (context.objectType === 'strategic_focus') {
      const [targetClientId, targetLineId] = (context.objectId || '').split(':');
      if (targetClientId && targetClientId !== currentClientId) {
        onClientChange?.(targetClientId);
      }
      setView('lines');
      setHighlightedStrategicLineId(targetLineId || null);
      setHighlightedStrategicLabel(context.label);
      setNotice(`已定位到战略呼应「${context.label}」`);
      onConsumeJump?.(requestId);
      return;
    }
    onConsumeJump?.(requestId);
  }, [currentClientId, jumpRequest, onClientChange, onConsumeJump]);

  const canEdit = snapshot?.permission.canEdit ?? false;

  async function handleSave() {
    if (!currentClientId || !snapshot || !canEdit) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: StrategicCockpitConfirmPayload = {
        weekSummary: draft.weekSummary.trim(),
        mainContradiction: draft.mainContradiction.trim(),
        coreBreakthrough: draft.coreBreakthrough.trim(),
        focusItems: draft.focusItems.map((item) => item.trim()).filter(Boolean).slice(0, 3),
      };
      const response = await confirmStrategicCockpit(currentClientId, payload);
      setSnapshot(response);
      setDraft(normalizeDraft(response));
      setEditing(false);
      setNotice('经营判断已更新。');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '经营判断保存失败。');
    } finally {
      setSaving(false);
    }
  }

  async function handleCopyChecklist() {
    if (!snapshot || !canEdit) return;
    setRunningAction('copy');
    setError(null);
    setNotice(null);
    try {
      const text = buildMeetingPackText(snapshot.clientName, snapshot.meetingPackDraft.groups, snapshot.meetingPackDraft.agenda);
      await navigator.clipboard.writeText(text);
      setNotice('周会清单已复制。');
    } catch (copyError) {
      setError(copyError instanceof Error ? copyError.message : '周会清单复制失败。');
    } finally {
      setRunningAction(null);
    }
  }

  const latestMeetingForApply = createdMeetingDraft || workspace?.meetings?.[0] || null;

  async function handleCreateMeetingDraft() {
    if (!currentClientId || !snapshot || !canEdit) return;
    setRunningAction('meeting');
    setError(null);
    setNotice(null);
    try {
      const response = await createStrategicMeetingPack(currentClientId);
      setCreatedMeetingDraft(response.meeting);
      const text = buildMeetingPackText(snapshot.clientName, snapshot.meetingPackDraft.groups, snapshot.meetingPackDraft.agenda);
      await navigator.clipboard.writeText(text);
      setNotice('正式周会草稿已创建，议程也已复制到剪贴板。');
    } catch (meetingError) {
      setError(meetingError instanceof Error ? meetingError.message : '会议草稿创建失败。');
    } finally {
      setRunningAction(null);
    }
  }

  async function handleApplyMeeting() {
    if (!currentClientId || !snapshot || !canEdit || !latestMeetingForApply) return;
    setRunningAction('apply');
    setError(null);
    setNotice(null);
    try {
      const response = await applyStrategicMeetingPack(currentClientId, latestMeetingForApply.id);
      setSnapshot(response);
      setDraft(normalizeDraft(response));
      setEditing(false);
      setNotice(`已根据《${latestMeetingForApply.title}》回填战略判断。`);
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : '周会结果回填失败。');
    } finally {
      setRunningAction(null);
    }
  }

  const shellBody = (() => {
    if (!selectedClient && !snapshot) {
      return (
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <p className="text-[13px] font-bold text-slate-500">尚未选择业务对象</p>
          <p className="text-[12px] text-slate-400 mt-1">请在左侧列表中选择一个客户，查看其经营判断总览。</p>
        </div>
      );
    }
    if (loading && !snapshot) {
      return (
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            正在生成经营判断总览
          </div>
        </div>
      );
    }
    if (error && !snapshot) {
      return (
        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 text-sm text-rose-700 shadow-sm">
          {error}
        </div>
      );
    }
    if (!snapshot) {
      return null;
    }

    let panel: React.ReactNode;
    switch (view) {
      case 'lines':
        panel = <StrategicLinesPanel snapshot={snapshot} highlightedLineId={highlightedStrategicLineId} highlightedLabel={highlightedStrategicLabel} />;
        break;
      case 'health':
        panel = <StrategicHealthPanel snapshot={snapshot} />;
        break;
      case 'checklist':
        panel = <ChecklistPanel snapshot={snapshot} />;
        break;
      case 'evidence':
        panel = <EvidencePanel snapshot={snapshot} />;
        break;
      case 'assets':
        panel = <AssetsPanel snapshot={snapshot} />;
        break;
      case 'overview':
      default:
        panel = <OverviewPanel snapshot={snapshot} draft={draft} editing={editing} setDraft={setDraft} />;
        break;
    }

    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-6">{panel}</div>
        <ActionRail
          snapshot={snapshot}
          canOperate={canEdit}
          onCopyChecklist={handleCopyChecklist}
          onCreateMeetingDraft={handleCreateMeetingDraft}
          onApplyMeeting={handleApplyMeeting}
          runningAction={runningAction}
          latestMeeting={latestMeetingForApply}
        />
      </div>
    );
  })();

  return (
    <div className={`h-full overflow-y-auto ${immersive ? 'bg-white' : 'bg-[#F6F8FC]'} pb-10`}>
      <div className={`mx-auto w-full ${immersive ? 'max-w-[1600px] px-8 py-8' : 'max-w-[1680px] px-6 py-6'}`}>
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl border border-blue-100 bg-blue-50 text-[28px] font-semibold text-[#5B7BFE] shadow-inner">
              {buildLogo(selectedClient?.alias || snapshot?.clientName || selectedClient?.name)}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <select
                    value={currentClientId || selectedClient?.id || ''}
                    onChange={(event) => onClientChange?.(event.target.value)}
                    className="appearance-none rounded-2xl border border-slate-200 bg-white px-4 py-2 pr-10 text-xl font-semibold tracking-tight text-slate-900 outline-none transition-colors focus:border-[#5B7BFE]"
                  >
                    {clients.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400">
                    <MapIcon size={14} />
                  </div>
                </div>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-500">
                  战略陪伴 / 业务发展驾驶台
                </span>
                {snapshot ? (
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${snapshot.permission.canEdit ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                    {snapshot.permission.canEdit ? 'CEO 可确认' : '只读'}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-slate-500">{selectedClient?.type || snapshot?.clientTagline || '项目'}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 rounded-3xl border border-slate-200 bg-white p-1.5 shadow-sm">
            <button
              type="button"
              onClick={() => setImmersive((current) => !current)}
              className="inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              {immersive ? <EyeOff size={16} /> : <Eye size={16} />}
              {immersive ? '退出沉浸' : '沉浸阅览'}
            </button>
            {snapshot?.permission.canEdit ? (
              editing ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      if (snapshot) {
                        setDraft(normalizeDraft(snapshot));
                      }
                      setEditing(false);
                    }}
                    className="rounded-2xl px-4 py-2 text-sm font-semibold text-slate-500 transition-colors hover:bg-slate-50"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={saving}
                    className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:opacity-70"
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                    保存判断
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
                >
                  <Sparkles size={16} />
                  确认经营判断
                </button>
              )
            ) : null}
          </div>
        </header>

        {snapshot?.permission.notice ? (
          <div className="mb-5 rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-7 text-amber-700">
            {snapshot.permission.notice}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-5 rounded-3xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm leading-7 text-emerald-700">
            {notice}
          </div>
        ) : null}
        {error ? (
          <div className="mb-5 rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm leading-7 text-rose-700">
            {error}
          </div>
        ) : null}

        <nav className="mb-6 grid gap-3 rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm md:grid-cols-3 xl:grid-cols-6">
          {VIEW_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = view === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setView(item.key)}
                className={`rounded-3xl border px-4 py-4 text-left transition-all ${active ? 'border-blue-200 bg-blue-50 text-[#3655D4]' : 'border-transparent bg-white text-slate-700 hover:border-slate-200 hover:bg-slate-50'}`}
              >
                <div className="flex items-center gap-2">
                  <Icon size={16} />
                  <span className="text-base font-semibold">{item.label}</span>
                </div>
                <p className="mt-2 text-xs leading-6 text-slate-500">{item.helper}</p>
              </button>
            );
          })}
        </nav>

        {shellBody}
      </div>
    </div>
  );
}
