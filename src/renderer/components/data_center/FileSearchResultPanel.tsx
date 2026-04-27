import React from 'react';

type FileSearchHit = {
  id?: string;
  title?: string;
  excerpt?: string;
  sourceTitle?: string;
  originalPath?: string;
  managedPath?: string;
  markdownPath?: string;
  path?: string;
  annotationId?: string | null;
};

type FileSearchResultPanelProps = {
  searchResult?: { hits?: FileSearchHit[]; selectedHits?: FileSearchHit[] } | null;
  onOpenOriginal?: (hit: FileSearchHit) => void;
  onMarkUseful?: (hit: FileSearchHit) => void;
  onMarkNoise?: (hit: FileSearchHit) => void;
  onMarkNeedsReview?: (hit: FileSearchHit) => void;
};

export function FileSearchResultPanel({
  searchResult,
  onOpenOriginal,
  onMarkUseful,
  onMarkNoise,
  onMarkNeedsReview,
}: FileSearchResultPanelProps) {
  const hits = (searchResult?.selectedHits?.length ? searchResult.selectedHits : searchResult?.hits) || [];
  if (hits.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-[12px] text-slate-500">
        当前没有可展示的文件检索结果。
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-3xl border border-slate-100 bg-white p-4">
      <p className="text-[12px] font-bold text-slate-500">文件检索结果</p>
      {hits.slice(0, 6).map((hit, index) => (
        <div key={hit.id || `${hit.title || 'hit'}-${index}`} className="rounded-2xl bg-slate-50 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[13px] font-bold text-slate-900">{hit.title || hit.sourceTitle || '未命名资料'}</p>
              {hit.excerpt && <p className="mt-1 line-clamp-3 text-[12px] leading-5 text-slate-600">{hit.excerpt}</p>}
            </div>
            {onOpenOriginal && (
              <button type="button" className="shrink-0 text-[12px] font-bold text-[#5B7BFE]" onClick={() => onOpenOriginal(hit)}>
                打开
              </button>
            )}
          </div>
          {hit.annotationId && (
            <div className="mt-2 flex flex-wrap gap-2">
              {onMarkUseful && <button type="button" className="text-[11px] font-bold text-emerald-600" onClick={() => onMarkUseful(hit)}>有用</button>}
              {onMarkNeedsReview && <button type="button" className="text-[11px] font-bold text-amber-600" onClick={() => onMarkNeedsReview(hit)}>复核</button>}
              {onMarkNoise && <button type="button" className="text-[11px] font-bold text-slate-400" onClick={() => onMarkNoise(hit)}>噪声</button>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
