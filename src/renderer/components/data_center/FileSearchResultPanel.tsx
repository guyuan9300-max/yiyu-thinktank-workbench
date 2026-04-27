import React from 'react';
import { ExternalLink, Flag, Search } from 'lucide-react';

import type { DataCenterSearchHit, DataCenterSearchResult } from '../../../shared/types';
import {
  buildFileSearchDisplayGroups,
  type FileSearchDisplayGroup,
  type FileSearchSupportLevel,
} from '../../../shared/workspaceFileSearchPresentation';

export interface FileSearchResultPanelProps {
  searchResult?: DataCenterSearchResult | null;
  onOpenOriginal: (hit: DataCenterSearchHit) => void;
  onUseAsEvidence?: (hit: DataCenterSearchHit) => void;
  onMarkUseful?: (hit: DataCenterSearchHit) => void;
  onMarkNoise?: (hit: DataCenterSearchHit) => void;
  onMarkNeedsReview?: (hit: DataCenterSearchHit) => void;
}

const SUPPORT_LABELS: Record<FileSearchSupportLevel, string> = {
  strong: '强相关',
  reference: '可参考',
  background: '背景线索',
};

const SUPPORT_STYLES: Record<FileSearchSupportLevel, string> = {
  strong: 'bg-sky-50 text-sky-700',
  reference: 'bg-slate-50 text-slate-600',
  background: 'bg-gray-50 text-gray-500',
};

const DEFAULT_VISIBLE_RESULT_COUNT = 6;

function sourceKindLabel(group: FileSearchDisplayGroup) {
  if (group.kind === 'original_file') return '原始文件';
  if (group.kind === 'machine_readable_only') return '历史机读稿';
  return '系统线索';
}

function SearchResultCard({
  group,
  index,
  expanded,
  onToggleExpanded,
  onOpenOriginal,
  onUseAsEvidence,
}: {
  group: FileSearchDisplayGroup;
  index: number;
  expanded: boolean;
  onToggleExpanded: (key: string) => void;
  onOpenOriginal: (hit: DataCenterSearchHit) => void;
  onUseAsEvidence?: (hit: DataCenterSearchHit) => void;
}) {
  const hit = group.primaryHit;
  const target = group.openTarget;
  const extraSnippets = group.snippets.slice(1);
  const groupTone = group.kind === 'original_file'
    ? 'border-sky-100 bg-white'
    : group.kind === 'machine_readable_only'
      ? 'border-amber-100 bg-amber-50/40'
      : 'border-slate-100 bg-slate-50/80';

  return (
    <div className={`rounded-2xl border px-4 py-4 ${groupTone}`}>
      <div className="min-w-0">
        <div className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 shrink-0 rounded-full bg-sky-50 px-2 py-1 text-[10px] font-bold text-sky-700">{index + 1}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-bold text-slate-800">{hit.title}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${SUPPORT_STYLES[group.supportLevel]}`}>
                {SUPPORT_LABELS[group.supportLevel]}
              </span>
              <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-500">
                {sourceKindLabel(group)}
              </span>
              {hit.selectedForAnswer && (
                <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">已入本轮材料</span>
              )}
            </div>
          </div>
        </div>
        {hit.sectionLabel && (
          <p className="mt-2 text-[11px] font-semibold text-slate-500">位置：{hit.sectionLabel}</p>
        )}
        {group.kind === 'system_card' && (
          <p className="mt-2 text-[11px] font-semibold text-slate-500">系统整理线索，不是原始上传文件。</p>
        )}
        {target.disabledReason && group.kind !== 'system_card' && (
          <p className="mt-2 text-[11px] font-semibold text-amber-600">{target.disabledReason}</p>
        )}
        {hit.excerpt && (
          <p className="mt-2 line-clamp-4 text-[12px] leading-6 text-slate-700 whitespace-pre-wrap">{hit.excerpt}</p>
        )}
        {extraSnippets.length > 0 && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => onToggleExpanded(group.key)}
              className="text-[11px] font-semibold text-sky-600 hover:text-sky-700"
            >
              {expanded ? '收起相关片段' : `还有 ${extraSnippets.length} 个相关片段`}
            </button>
            {expanded && (
              <div className="mt-2 space-y-2">
                {extraSnippets.map((snippet, snippetIndex) => (
                  <div key={`${group.key}-snippet-${snippetIndex}`} className="rounded-xl border border-slate-100 bg-white/80 px-3 py-2">
                    <p className="text-[11px] font-semibold text-slate-500">
                      {snippet.sectionLabel || '相关片段'}
                    </p>
                    {snippet.excerpt && (
                      <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-slate-600 whitespace-pre-wrap">{snippet.excerpt}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        {onUseAsEvidence && (
          <button
            type="button"
            onClick={() => onUseAsEvidence(hit)}
            className="inline-flex items-center gap-1 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[11px] font-bold text-emerald-700 transition-colors hover:bg-emerald-100"
          >
            <Flag size={13} />
            加入本轮材料
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            if (!target.disabled) onOpenOriginal(hit);
          }}
          disabled={Boolean(target.disabled)}
          title={target.disabledReason || undefined}
          className={`inline-flex items-center gap-1 rounded-xl border px-3 py-2 text-[11px] font-bold transition-colors ${
            target.disabled
              ? 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-400'
              : 'border-sky-100 bg-sky-50 text-sky-700 hover:bg-sky-100'
          }`}
        >
          <ExternalLink size={13} />
          {target.label}
        </button>
      </div>
    </div>
  );
}

export function FileSearchResultPanel({
  searchResult,
  onOpenOriginal,
  onUseAsEvidence,
}: FileSearchResultPanelProps) {
  const [expandedGroupKeys, setExpandedGroupKeys] = React.useState<Set<string>>(() => new Set());
  const [showAllResults, setShowAllResults] = React.useState(false);
  const displayGroups = React.useMemo(() => buildFileSearchDisplayGroups(searchResult), [searchResult]);
  const hits = [
    ...displayGroups.originalGroups,
    ...displayGroups.systemGroups,
  ];
  const visibleOriginalGroups = showAllResults
    ? displayGroups.originalGroups
    : displayGroups.originalGroups.slice(0, DEFAULT_VISIBLE_RESULT_COUNT);
  const remainingDefaultSlots = Math.max(0, DEFAULT_VISIBLE_RESULT_COUNT - visibleOriginalGroups.length);
  const visibleSystemGroups = showAllResults
    ? displayGroups.systemGroups
    : displayGroups.systemGroups.slice(0, displayGroups.originalGroups.length === 0
      ? DEFAULT_VISIBLE_RESULT_COUNT
      : remainingDefaultSlots);
  const collapsedOriginalCount = Math.min(displayGroups.originalGroups.length, DEFAULT_VISIBLE_RESULT_COUNT);
  const collapsedSystemLimit = displayGroups.originalGroups.length === 0
    ? DEFAULT_VISIBLE_RESULT_COUNT
    : Math.max(0, DEFAULT_VISIBLE_RESULT_COUNT - collapsedOriginalCount);
  const collapsedHiddenCount = Math.max(displayGroups.originalGroups.length - collapsedOriginalCount, 0)
    + Math.max(displayGroups.systemGroups.length - collapsedSystemLimit, 0);

  const toggleGroupExpanded = React.useCallback((key: string) => {
    setExpandedGroupKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  if (hits.length === 0) {
    return (
      <div className="rounded-[24px] border border-slate-100 bg-white px-5 py-6 text-[13px] leading-7 text-slate-500 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
        没有找到足够匹配的文件。可以换一个文件名、项目名或关键词再试。
      </div>
    );
  }

  return (
    <div className="rounded-[24px] border border-sky-100 bg-[linear-gradient(180deg,rgba(239,246,255,0.8),rgba(255,255,255,0.98))] px-5 py-5 xl:px-6 xl:py-6 shadow-[0_8px_28px_rgba(14,165,233,0.08)]">
      <div className="flex items-center gap-2">
        <Search size={16} className="text-sky-500" />
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-sky-600">文件检索结果</p>
        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500">
          已合并 {displayGroups.totalGroupCount} 组
        </span>
      </div>
      <div className="mt-4 space-y-3">
        {visibleOriginalGroups.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-2">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-sky-600">原始文件</p>
              <span className="text-[11px] text-slate-400">优先展示可打开的上传资料。</span>
            </div>
            <div className="space-y-3">
              {visibleOriginalGroups.map((group, index) => (
                <SearchResultCard
                  key={group.key}
                  group={group}
                  index={index}
                  expanded={expandedGroupKeys.has(group.key)}
                  onToggleExpanded={toggleGroupExpanded}
                  onOpenOriginal={onOpenOriginal}
                  onUseAsEvidence={onUseAsEvidence}
                />
              ))}
            </div>
          </div>
        )}
        {visibleSystemGroups.length > 0 && (
          <div className="pt-2">
            <div className="mb-2 flex items-center gap-2">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">系统线索</p>
              <span className="text-[11px] text-slate-400">系统整理线索，不是原始上传文件。</span>
            </div>
            <div className="space-y-3">
              {visibleSystemGroups.map((group, index) => (
                <SearchResultCard
                  key={group.key}
                  group={group}
                  index={visibleOriginalGroups.length + index}
                  expanded={expandedGroupKeys.has(group.key)}
                  onToggleExpanded={toggleGroupExpanded}
                  onOpenOriginal={onOpenOriginal}
                  onUseAsEvidence={onUseAsEvidence}
                />
              ))}
            </div>
          </div>
        )}
        {collapsedHiddenCount > 0 && (
          <button
            type="button"
            onClick={() => setShowAllResults((prev) => !prev)}
            className="mx-auto block px-2 py-2 text-[12px] font-semibold text-sky-600 transition-colors hover:text-sky-700"
          >
            {showAllResults ? '收起更多结果' : `展开更多结果（${collapsedHiddenCount} 条）`}
          </button>
        )}
      </div>
    </div>
  );
}
