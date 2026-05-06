import React from 'react';
import { Bookmark, BookmarkCheck, ChevronDown, ChevronUp, ExternalLink, FilePlus2, Newspaper, Share2 } from 'lucide-react';

import type { TopicCandidate } from '../../../shared/types';

type TopicIntelInboxCardProps = {
  candidate: TopicCandidate;
  radarTitle: string;
  saved: boolean;
  tags: string[];
  relatedTaskCount: number;
  mainBadge?: string | null;
  sourceStatusText?: string;
  relevanceReason: string;
  suggestedAction: string;
  isDeepAnalysisOpen: boolean;
  isFavoritePending?: boolean;
  onToggleSaved: () => void;
  onShare: () => void;
  onOpenTask: () => void;
  onToggleDeepAnalysis: () => void;
  onOpenSource: () => void;
  children?: React.ReactNode;
};

function formatPublishedAt(value?: string | null) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
}

function formatShareTime(value?: string | null) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function insightStatusLabel(candidate: TopicCandidate) {
  if (candidate.insightStatus !== 'failed') return null;
  return { label: '深度分析生成失败，可重试', className: 'border-rose-100 bg-rose-50 text-rose-700' };
}

export function TopicIntelInboxCard({
  candidate,
  radarTitle,
  saved,
  tags,
  relatedTaskCount,
  mainBadge,
  sourceStatusText,
  relevanceReason,
  suggestedAction,
  isDeepAnalysisOpen,
  isFavoritePending = false,
  onToggleSaved,
  onShare,
  onOpenTask,
  onToggleDeepAnalysis,
  onOpenSource,
  children,
}: TopicIntelInboxCardProps) {
  const analysisBadge = insightStatusLabel(candidate);
  const hasProcessingStatus = Boolean(analysisBadge || sourceStatusText);
  const publishedAtText = formatPublishedAt(candidate.publishedAt) || '未标注';
  const relatedTaskText = relatedTaskCount > 0 ? `已转任务 ${relatedTaskCount}` : '';
  const latestShare = candidate.viewerShareRecords?.[0] || null;
  const latestShareSender = latestShare?.sharedByName || latestShare?.sharedBy || '';
  const latestShareTime = formatShareTime(latestShare?.createdAt);
  const sentShares = candidate.viewerSentShareRecords || [];
  const latestSentShare = sentShares[0] || null;
  const latestSentTime = formatShareTime(latestSentShare?.createdAt);
  const sentRecipientNames = sentShares
    .flatMap((share) => (share.sharedToRecipients || []).map((recipient) => recipient.fullName || recipient.userId))
    .filter(Boolean);
  const uniqueSentRecipientNames = Array.from(new Set(sentRecipientNames));

  return (
    <article className="h-full rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3">
        {mainBadge && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-[#5B7BFE] px-2.5 py-1 text-[11px] font-bold text-white">
              {mainBadge}
            </span>
          </div>
        )}

        <h3 className="text-[17px] font-bold leading-7 text-gray-950">{candidate.title}</h3>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-gray-500">
          <span className="inline-flex items-center gap-1.5">
            <Newspaper size={13} />
            来源：{candidate.source || '未知来源'}
          </span>
          <span>发布时间：{publishedAtText}</span>
          <span>所属雷达：{radarTitle}</span>
        </div>

        {hasProcessingStatus && (
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <span className="font-semibold text-gray-500">处理状态</span>
            {sourceStatusText && (
              <span className="inline-flex items-center rounded-md border border-orange-100 bg-orange-50 px-2.5 py-1 font-semibold text-orange-700">
                {sourceStatusText}
              </span>
            )}
            {analysisBadge && (
              <span className={`inline-flex items-center rounded-md border px-2.5 py-1 font-semibold ${analysisBadge.className}`}>
                {analysisBadge.label}
              </span>
            )}
          </div>
        )}

        <div>
          <p className="text-[11px] font-bold text-gray-500">一句话摘要</p>
          <p className="mt-1 text-[13px] leading-6 text-gray-700">{candidate.summary || '当前暂无摘要。'}</p>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <section className="rounded-lg border border-blue-100 bg-blue-50/70 px-4 py-3">
            <p className="text-[11px] font-bold text-[#5B7BFE]">为什么可能相关</p>
            <p className="mt-2 text-[13px] leading-6 text-slate-700">{relevanceReason}</p>
          </section>
          <section className="rounded-lg border border-emerald-100 bg-emerald-50/70 px-4 py-3">
            <p className="text-[11px] font-bold text-emerald-700">建议动作</p>
            <p className="mt-2 text-[13px] leading-6 text-slate-700">{suggestedAction}</p>
          </section>
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.slice(0, 5).map((tag) => (
              <span key={`${candidate.id}-tag-${tag}`} className="rounded-md border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700">
                #{tag}
              </span>
            ))}
            {tags.length > 5 && (
              <span className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-semibold text-gray-500">
                +{tags.length - 5}
              </span>
            )}
          </div>
        )}

        {(candidate.viewerSharedToMe || candidate.viewerSharedByMe || relatedTaskText) && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {candidate.viewerSharedToMe && (
                <span className="inline-flex items-center rounded-md border border-cyan-100 bg-cyan-50 px-2.5 py-1 text-[11px] font-bold text-cyan-700">
                  共享给我
                </span>
              )}
              {candidate.viewerSharedByMe && (
                <span className="inline-flex items-center rounded-md border border-sky-100 bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700">
                  我已共享
                </span>
              )}
              {relatedTaskText && (
                <span className="inline-flex items-center rounded-md border border-violet-100 bg-violet-50 px-2.5 py-1 text-[11px] font-bold text-violet-700">
                  {relatedTaskText}
                </span>
              )}
            </div>
            {latestShare && (
              <div className="rounded-lg border border-cyan-100 bg-cyan-50/60 px-3 py-2 text-[12px] leading-5 text-cyan-900">
                <p className="font-semibold">
                  {latestShareSender ? `${latestShareSender} 共享给你` : '有人共享给你'}
                  {latestShareTime ? ` · ${latestShareTime}` : ''}
                </p>
                {latestShare.reason ? <p className="mt-1 text-cyan-800">{latestShare.reason}</p> : null}
              </div>
            )}
            {candidate.viewerSharedByMe && (
              <div className="rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-[12px] leading-5 text-sky-900">
                <p className="font-semibold">
                  已共享给 {uniqueSentRecipientNames.slice(0, 4).join('、') || '已配置接收人'}
                  {uniqueSentRecipientNames.length > 4 ? ` 等 ${uniqueSentRecipientNames.length} 人` : ''}
                  {latestSentTime ? ` · ${latestSentTime}` : ''}
                </p>
                {latestSentShare?.reason ? <p className="mt-1 text-sky-800">{latestSentShare.reason}</p> : null}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            onClick={onToggleSaved}
            disabled={isFavoritePending}
            aria-pressed={saved}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-[12px] font-semibold transition-colors ${
              saved
                ? 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
                : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
            } ${isFavoritePending ? 'cursor-wait opacity-70' : ''}`}
          >
            {saved ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
            {saved ? '已收藏' : '收藏'}
          </button>
          <button
            type="button"
            onClick={onShare}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 transition-colors hover:bg-gray-50"
          >
            <Share2 size={14} />
            共享
          </button>
          <button
            type="button"
            onClick={onOpenTask}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 transition-colors hover:bg-gray-50"
          >
            <FilePlus2 size={14} />
            转任务
          </button>
          <button
            type="button"
            onClick={onToggleDeepAnalysis}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-2 text-[12px] font-semibold text-gray-600 transition-colors hover:bg-gray-50"
          >
            {isDeepAnalysisOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {isDeepAnalysisOpen ? '收起分析' : '深度分析'}
          </button>
          <button
            type="button"
            onClick={onOpenSource}
            disabled={!candidate.sourceUrl}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-[12px] font-semibold transition-colors ${
              candidate.sourceUrl
                ? 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                : 'cursor-not-allowed border-gray-100 bg-gray-50 text-gray-300'
            }`}
          >
            <ExternalLink size={14} />
            打开原文
          </button>
        </div>
      </div>

      {isDeepAnalysisOpen && children ? (
        <div className="mt-5 border-t border-gray-100 pt-5">
          {children}
        </div>
      ) : null}
    </article>
  );
}
