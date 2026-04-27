import type { DataCenterSearchHit, DataCenterSearchResult } from './types.js';

export type FileSearchGroupKind = 'original_file' | 'machine_readable_only' | 'system_card';
export type FileSearchSupportLevel = 'strong' | 'reference' | 'background';

export interface FileSearchOpenTarget {
  path: string;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
}

export interface FileSearchDisplayGroup {
  key: string;
  kind: FileSearchGroupKind;
  primaryHit: DataCenterSearchHit;
  snippets: DataCenterSearchHit[];
  supportLevel: FileSearchSupportLevel;
  openTarget: FileSearchOpenTarget;
}

export interface FileSearchDisplayGroups {
  originalGroups: FileSearchDisplayGroup[];
  systemGroups: FileSearchDisplayGroup[];
  totalGroupCount: number;
}

export function isMarkdownPath(path?: string | null) {
  return String(path || '').trim().toLowerCase().endsWith('.md');
}

function cleanKeyPart(value: unknown): string {
  return String(value || '').trim().toLowerCase();
}

export function buildSearchGroupKey(hit: DataCenterSearchHit): string {
  const section = cleanKeyPart(hit.sectionLabel) || 'unknown-section';
  const documentId = cleanKeyPart(hit.documentId);
  if (documentId) return `doc:${documentId}::${section}`;

  const sourcePath = [hit.originalPath, hit.managedPath, hit.path]
    .map(cleanKeyPart)
    .find(Boolean);
  if (sourcePath) return `path:${sourcePath}::${section}`;

  return `title:${cleanKeyPart(hit.title) || 'untitled'}::${section}`;
}

export function isOriginalFileHit(hit: DataCenterSearchHit): boolean {
  if (hit.sourceAvailability === 'invalid_source') return false;
  if (hit.originalAvailable === false) return false;
  if (hit.openableKind === 'original_file') return true;
  if (hit.openableKind === 'system_card') return false;
  return [hit.originalPath, hit.managedPath, hit.path]
    .map((value) => String(value || '').trim())
    .some((value) => value && !isMarkdownPath(value));
}

export function buildFileSearchOpenTarget(hit: DataCenterSearchHit): FileSearchOpenTarget {
  const originalPath = [hit.originalPath, hit.managedPath, hit.path]
    .map((value) => String(value || '').trim())
    .find((value) => value && !isMarkdownPath(value));
  if (isOriginalFileHit(hit) && originalPath) {
    return { path: originalPath, label: '打开原文' };
  }
  if (hit.sourceAvailability === 'invalid_source') {
    return {
      path: '',
      label: '打开原文',
      disabled: true,
      disabledReason: hit.openOriginalDisabledReason || '资料已失效，无法打开原文。',
    };
  }
  if (hit.sourceAvailability === 'machine_readable_only') {
    const markdownPath = hit.markdownPath || (isMarkdownPath(hit.path) ? hit.path : '');
    return {
      path: markdownPath || '',
      label: markdownPath ? '查看机读稿' : '打开原文',
      disabled: !markdownPath,
      disabledReason: hit.openOriginalDisabledReason || '原文件已缺失，当前仅有机读稿。',
    };
  }
  if (hit.openableKind === 'system_card') {
    const path = hit.markdownPath || hit.path || '';
    return { path, label: '打开系统卡片' };
  }
  const markdownPath = hit.markdownPath || (isMarkdownPath(hit.path) ? hit.path : '');
  if (markdownPath) return { path: markdownPath, label: '打开机读稿' };
  return { path: hit.path || '', label: '打开资料' };
}

export function normalizeFileSearchSupportLevel(score?: number | null): FileSearchSupportLevel {
  if (typeof score !== 'number' || !Number.isFinite(score)) return 'background';
  if (score >= 3) return 'strong';
  if (score >= 1) return 'reference';
  return 'background';
}

function primaryHitRank(hit: DataCenterSearchHit): number {
  let rank = 0;
  if (isOriginalFileHit(hit)) rank += 1000;
  if (hit.humanLabel === 'useful') rank += 120;
  if (hit.humanLabel === 'noise') rank -= 180;
  if (hit.humanLabel === 'needs_review') rank -= 30;
  rank += Math.min(Number(hit.score || 0), 100) * 10;
  rank += Math.min(String(hit.excerpt || '').trim().length, 500) / 100;
  return rank;
}

export function pickPrimaryHit(hits: DataCenterSearchHit[]): DataCenterSearchHit {
  return [...hits].sort((left, right) => primaryHitRank(right) - primaryHitRank(left))[0];
}

function orderedSearchHits(searchResult?: DataCenterSearchResult | null): DataCenterSearchHit[] {
  if (Array.isArray(searchResult?.selectedHits) && searchResult.selectedHits.length > 0) {
    return searchResult.selectedHits;
  }
  if (Array.isArray(searchResult?.hits)) {
    return searchResult.hits;
  }
  return [];
}

export function buildFileSearchDisplayGroups(
  searchResult?: DataCenterSearchResult | null,
): FileSearchDisplayGroups {
  const groups = new Map<string, DataCenterSearchHit[]>();
  for (const hit of orderedSearchHits(searchResult)) {
    if (hit.sourceAvailability === 'invalid_source') continue;
    const key = buildSearchGroupKey(hit);
    const existing = groups.get(key) || [];
    existing.push(hit);
    groups.set(key, existing);
  }

  const displayGroups = Array.from(groups.entries()).map(([key, snippets]) => {
    const primaryHit = pickPrimaryHit(snippets);
    const sortedSnippets = [...snippets].sort((left, right) => primaryHitRank(right) - primaryHitRank(left));
    const kind: FileSearchGroupKind = isOriginalFileHit(primaryHit)
      ? 'original_file'
      : (primaryHit.sourceAvailability === 'machine_readable_only' ? 'machine_readable_only' : 'system_card');
    return {
      key,
      kind,
      primaryHit,
      snippets: sortedSnippets,
      supportLevel: normalizeFileSearchSupportLevel(primaryHit.score),
      openTarget: buildFileSearchOpenTarget(primaryHit),
    };
  });

  return {
    originalGroups: displayGroups.filter((group) => group.kind !== 'system_card'),
    systemGroups: displayGroups.filter((group) => group.kind === 'system_card'),
    totalGroupCount: displayGroups.length,
  };
}
