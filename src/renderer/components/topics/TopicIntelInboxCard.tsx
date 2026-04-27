import React from 'react';
import { Newspaper, Trash2 } from 'lucide-react';

import type { TopicCandidate, TopicCandidateInsight } from '../../../shared/types';

type TopicIntelInboxCardProps = {
  candidate: TopicCandidate;
  radarTitle: string;
  insight?: TopicCandidateInsight | null;
  selected: boolean;
  read: boolean;
  saved: boolean;
  tags: string[];
  relatedTaskCount: number;
  onSelect: () => void;
  onDelete: () => void;
};

function summarizeInsight(candidate: TopicCandidate, insight?: TopicCandidateInsight | null) {
  const editorialNote = (insight?.editorialNote || '')
    .trim()
    .replace(/^大周(?:的)?(?:前哨判断|判断)[：:]\s*/, '');
  if (editorialNote) return editorialNote;
  if (insight?.overview?.trim()) return insight.overview.trim();
  return candidate.summary.trim() || '大周还在整理这篇内容的核心信息。';
}

function relationReason(candidate: TopicCandidate, radarTitle: string, insight?: TopicCandidateInsight | null) {
  if (insight?.recommendationReasons?.length) return insight.recommendationReasons[0];
  if (candidate.summary.trim()) return candidate.summary.trim();
  return `这篇内容与「${radarTitle}」相关，但当前还需要等待进一步解析。`;
}

function formatPublishedAt(value?: string | null) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function insightBadge(candidate: TopicCandidate) {
  if (candidate.insightStatus === 'ready') {
    return { label: '已解析', className: 'bg-emerald-50 text-emerald-700 border border-emerald-100' };
  }
  if (candidate.insightStatus === 'failed') {
    return { label: '解析失败', className: 'bg-rose-50 text-rose-700 border border-rose-100' };
  }
  return { label: '解析中', className: 'bg-gray-100 text-gray-500 border border-gray-200' };
}

export function TopicIntelInboxCard({
  candidate,
  radarTitle,
  insight,
  selected,
  read,
  saved,
  tags,
  relatedTaskCount,
  onSelect,
  onDelete,
}: TopicIntelInboxCardProps) {
  const badge = insightBadge(candidate);
  const points = insight?.keyPoints?.slice(0, 2) || [];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className={`rounded-[28px] border p-5 transition-all cursor-pointer ${
        selected ? 'border-[#b8c7ff] bg-[#f7f9ff] shadow-[0_12px_36px_rgba(91,123,254,0.12)]' : 'border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm'
      }`}
    >
      <div className="relative">
        <button
          type="button"
          title="删除这条情报"
          aria-label="删除这条情报"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          className="absolute right-0 top-0 z-10 w-9 h-9 rounded-full border border-rose-200 bg-white text-rose-500 shadow-sm hover:bg-rose-50 hover:text-rose-600 transition-all flex items-center justify-center"
        >
          <Trash2 size={15} />
        </button>

        <div className="mx-auto w-full max-w-[720px] min-w-0 pt-1">
          <div className="flex flex-wrap items-center justify-center gap-2 mb-2">
            {!read && <span className="w-2.5 h-2.5 rounded-full bg-[#5B7BFE] shrink-0" />}
            <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-[#4a67f5] border border-blue-100">
              {radarTitle}
            </span>
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${badge.className}`}>{badge.label}</span>
            {saved && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-100">
                资料夹
              </span>
            )}
            {relatedTaskCount > 0 && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-violet-50 text-violet-700 border border-violet-100">
                已转任务 {relatedTaskCount}
              </span>
            )}
          </div>

          <h3 className="text-[18px] font-bold text-gray-900 leading-7 text-center">{candidate.title}</h3>

          <div className="flex flex-wrap items-center justify-center gap-3 mt-3 text-[12px] text-gray-500">
            <span className="inline-flex items-center gap-1.5">
              <Newspaper size={13} />
              {candidate.source}
            </span>
            {candidate.publishedAt && <span>{formatPublishedAt(candidate.publishedAt)}</span>}
            {candidate.capturedBy && <span>{candidate.capturedBy} 抓取</span>}
          </div>

          {tags.length > 0 && (
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {tags.slice(0, 4).map((tag) => (
                <span
                  key={`${candidate.id}-tag-${tag}`}
                  className="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700"
                >
                  #{tag}
                </span>
              ))}
              {tags.length > 4 && (
                <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-3 py-1 text-[11px] font-semibold text-gray-500">
                  +{tags.length - 4}
                </span>
              )}
            </div>
          )}

          {points.length > 0 && (
            <div className="mt-4">
              <p className="text-[12px] font-bold text-gray-900 text-center">核心观点</p>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {points.map((item, index) => (
                  <span key={`${candidate.id}-point-${index}`} className="inline-flex items-center rounded-2xl bg-gray-100 px-3 py-2 text-[12px] leading-5 text-gray-700">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4">
            <p className="text-[12px] font-bold text-gray-900 text-center">大周判断</p>
            <p className="text-[13px] text-gray-600 leading-6 mt-2">{summarizeInsight(candidate, insight)}</p>
          </div>

          <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50/70 px-4 py-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#5B7BFE]">为什么相关</p>
            <p className="text-[13px] text-slate-700 leading-6 mt-2">{relationReason(candidate, radarTitle, insight)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
