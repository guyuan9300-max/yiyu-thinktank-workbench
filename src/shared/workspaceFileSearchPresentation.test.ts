import test from 'node:test';
import assert from 'node:assert/strict';

import type { DataCenterSearchHit } from './types.js';
import {
  buildFileSearchDisplayGroups,
  buildSearchGroupKey,
  isOriginalFileHit,
  normalizeFileSearchSupportLevel,
  pickPrimaryHit,
} from './workspaceFileSearchPresentation.js';

function hit(overrides: Partial<DataCenterSearchHit> = {}): DataCenterSearchHit {
  return {
    title: 'CFFC 战略设计.docx',
    excerpt: '战略设计说明片段。',
    sourceType: 'document',
    documentId: 'doc-1',
    path: '/tmp/CFFC 战略设计.docx',
    originalPath: '/tmp/CFFC 战略设计.docx',
    managedPath: null,
    markdownPath: '/tmp/CFFC 战略设计.md',
    openableKind: 'original_file',
    score: 3.2,
    sectionLabel: '正文',
    retrievalStage: 'raw_chunk',
    selectedForAnswer: true,
    qualityFlags: [],
    ...overrides,
  };
}

test('group key prefers document id and section label', () => {
  assert.equal(
    buildSearchGroupKey(hit({ documentId: 'doc-42', sectionLabel: '第 1 页' })),
    'doc:doc-42::第 1 页',
  );
});

test('group key falls back to path and section when document id is missing', () => {
  assert.equal(
    buildSearchGroupKey(hit({ documentId: null, originalPath: '/tmp/a.pdf', path: '/tmp/a.md', sectionLabel: '正文' })),
    'path:/tmp/a.pdf::正文',
  );
});

test('same document and section are merged into one display group', () => {
  const result = buildFileSearchDisplayGroups({
    query: '战略方案',
    routeDecision: {} as never,
    hits: [],
    selectedHits: [
      hit({ excerpt: '第一条片段。', score: 1.2 }),
      hit({ excerpt: '第二条片段。', score: 4.5 }),
    ],
    missingContext: [],
    suggestedFollowups: [],
  });

  assert.equal(result.originalGroups.length, 1);
  assert.equal(result.originalGroups[0].snippets.length, 2);
  assert.equal(result.originalGroups[0].primaryHit.excerpt, '第二条片段。');
});

test('original file and system card are separated into different sections', () => {
  const result = buildFileSearchDisplayGroups({
    query: '战略方案',
    routeDecision: {} as never,
    hits: [],
    selectedHits: [
      hit(),
      hit({
        documentId: 'sys-1',
        title: '事件线：CFFC 战略陪伴',
        path: '/tmp/_v2_meta/system_docs/event.md',
        originalPath: null,
        markdownPath: '/tmp/_v2_meta/system_docs/event.md',
        openableKind: 'system_card',
      }),
    ],
    missingContext: [],
    suggestedFollowups: [],
  });

  assert.equal(result.originalGroups.length, 1);
  assert.equal(result.systemGroups.length, 1);
  assert.equal(result.systemGroups[0].openTarget.label, '打开系统卡片');
});

test('invalid source hits are hidden from file search display groups', () => {
  const result = buildFileSearchDisplayGroups({
    query: '战略方案',
    routeDecision: {} as never,
    hits: [],
    selectedHits: [
      hit({
        documentId: 'invalid-1',
        title: '日慈战略核心思想 2_日慈_20260211.pdf',
        excerpt: '解析重试',
        sourceAvailability: 'invalid_source',
        originalAvailable: false,
        machineReadableAvailable: false,
      }),
    ],
    missingContext: [],
    suggestedFollowups: [],
  });

  assert.equal(result.originalGroups.length, 0);
  assert.equal(result.systemGroups.length, 0);
});

test('missing original with valid markdown is shown as machine-readable result', () => {
  const result = buildFileSearchDisplayGroups({
    query: '战略方案',
    routeDecision: {} as never,
    hits: [],
    selectedHits: [
      hit({
        sourceAvailability: 'machine_readable_only',
        originalAvailable: false,
        machineReadableAvailable: true,
        originalPath: null,
        managedPath: null,
        path: '/tmp/CFFC 战略设计.md',
        markdownPath: '/tmp/CFFC 战略设计.md',
        openableKind: 'machine_markdown',
        openOriginalDisabledReason: '原文件已缺失，当前仅有机读稿。',
      }),
    ],
    missingContext: [],
    suggestedFollowups: [],
  });

  assert.equal(result.originalGroups.length, 1);
  assert.equal(result.originalGroups[0].kind, 'machine_readable_only');
  assert.equal(result.originalGroups[0].openTarget.label, '查看机读稿');
  assert.equal(result.originalGroups[0].openTarget.disabledReason, '原文件已缺失，当前仅有机读稿。');
});

test('primary hit prefers original file over system card even with lower score', () => {
  const primary = pickPrimaryHit([
    hit({
      path: '/tmp/_v2_meta/system.md',
      originalPath: null,
      markdownPath: '/tmp/_v2_meta/system.md',
      openableKind: 'system_card',
      score: 9,
    }),
    hit({ score: 1, openableKind: 'original_file' }),
  ]);

  assert.equal(primary.openableKind, 'original_file');
  assert.equal(isOriginalFileHit(primary), true);
});

test('support score is mapped to user-facing levels', () => {
  assert.equal(normalizeFileSearchSupportLevel(6.34), 'strong');
  assert.equal(normalizeFileSearchSupportLevel(1.4), 'reference');
  assert.equal(normalizeFileSearchSupportLevel(0.4), 'background');
  assert.equal(normalizeFileSearchSupportLevel(null), 'background');
});
