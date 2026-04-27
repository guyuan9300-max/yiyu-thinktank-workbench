import test from 'node:test';
import assert from 'node:assert/strict';

import type { EvidenceItem } from './types.js';
import {
  buildEvidenceCitationCards,
  deriveEvidenceBusinessTags,
  deriveEvidenceClaimTitle,
  normalizeEvidenceSupportLevel,
} from './workspaceEvidencePresentation.js';

function evidence(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: 'ev-1',
    title: 'CFFC 战略设计.docx',
    excerpt: '战略陪伴要从课程服务交付转向关系生态建设，形成长期支持网络。',
    sourceType: 'document',
    documentId: 'doc-1',
    path: '/tmp/CFFC 战略设计.docx',
    score: 6.34,
    matchedTerms: [],
    sectionLabel: '正文',
    retrievalStage: 'raw_chunk',
    ...overrides,
  };
}

test('claim title prefers excerpt over filename', () => {
  const title = deriveEvidenceClaimTitle(evidence());

  assert.match(title, /战略陪伴要从课程服务交付转向关系生态建设/);
  assert.doesNotMatch(title, /CFFC 战略设计\.docx/);
});

test('claim title falls back to source title when excerpt is empty', () => {
  const title = deriveEvidenceClaimTitle(evidence({ excerpt: '' }));

  assert.equal(title, 'CFFC 战略设计.docx');
});

test('same document and section are merged into one citation card', () => {
  const cards = buildEvidenceCitationCards([
    evidence({ id: 'ev-1', excerpt: '第一条片段说明战略陪伴方向。', score: 2.2 }),
    evidence({ id: 'ev-2', excerpt: '第二条片段说明关系生态建设。', score: 6.34 }),
  ]);

  assert.equal(cards.length, 1);
  assert.equal(cards[0].snippets.length, 2);
  assert.equal(cards[0].primarySnippet.id, 'ev-2');
});

test('high abnormal score is normalized to strong support', () => {
  assert.equal(normalizeEvidenceSupportLevel(6.34), 'strong');
  assert.equal(normalizeEvidenceSupportLevel(1.8), 'reference');
  assert.equal(normalizeEvidenceSupportLevel(0.2), 'background');
  assert.equal(normalizeEvidenceSupportLevel(null), 'background');
});

test('retrieval stage maps to business tags', () => {
  assert.ok(deriveEvidenceBusinessTags(evidence({ retrievalStage: 'raw_chunk' })).includes('raw_source'));
  assert.ok(deriveEvidenceBusinessTags(evidence({ retrievalStage: 'surrogate' })).includes('summary_source'));
  assert.ok(deriveEvidenceBusinessTags(evidence({ retrievalStage: 'master_index' })).includes('index_source'));
  assert.ok(deriveEvidenceBusinessTags(evidence({ retrievalStage: 'state_pool' })).includes('summary_source'));
});

test('source title keywords produce meeting and strategy tags', () => {
  const meetingTags = deriveEvidenceBusinessTags(evidence({ title: 'CFFC 会议纪要.docx' }));
  const strategyTags = deriveEvidenceBusinessTags(evidence({ title: 'CFFC 战略规划.pdf' }));

  assert.ok(meetingTags.includes('meeting_material'));
  assert.ok(strategyTags.includes('strategy_material'));
});

test('citation cards never expose raw percentage labels', () => {
  const cards = buildEvidenceCitationCards([evidence({ score: 6.34 })]);

  assert.equal(cards[0].supportLevel, 'strong');
  assert.equal(String(cards[0].maxScore).includes('634%'), false);
});

test('raw file cards open original documents instead of machine markdown', () => {
  const cards = buildEvidenceCitationCards([
    evidence({
      path: '/tmp/_v2_meta/markdown/CFFC.md',
      originalPath: '/tmp/CFFC 战略设计.docx',
      managedPath: '/tmp/CFFC 战略设计.docx',
      markdownPath: '/tmp/_v2_meta/markdown/CFFC.md',
      canonicalKind: 'raw_file',
      openableKind: 'original_file',
    }),
  ]);

  assert.equal(cards[0].openPath, '/tmp/CFFC 战略设计.docx');
  assert.equal(cards[0].openActionLabel, '查看原文');
  assert.equal(cards[0].openableKind, 'original_file');
});

test('system generated markdown cards are not labelled as original documents', () => {
  const cards = buildEvidenceCitationCards([
    evidence({
      title: '梳理为爱黔行接下来要实施的关键实践',
      path: '/tmp/_v2_meta/system_docs/task_doc/task_1.md',
      markdownPath: '/tmp/_v2_meta/system_docs/task_doc/task_1.md',
      canonicalKind: 'task_doc',
      openableKind: 'system_card',
    }),
  ]);

  assert.equal(cards[0].openPath, '/tmp/_v2_meta/system_docs/task_doc/task_1.md');
  assert.equal(cards[0].openActionLabel, '查看系统卡片');
  assert.equal(cards[0].openableKind, 'system_card');
  assert.ok(cards[0].businessTags.includes('needs_review'));
});

test('invalid source evidence is not rendered as citation card', () => {
  const cards = buildEvidenceCitationCards([
    evidence({
      title: '日慈战略核心思想 2_日慈_20260211.pdf',
      excerpt: '解析重试',
      sourceAvailability: 'invalid_source',
      originalAvailable: false,
      machineReadableAvailable: false,
    }),
  ]);

  assert.equal(cards.length, 0);
});

test('machine-readable-only evidence opens generated markdown instead of stale original', () => {
  const cards = buildEvidenceCitationCards([
    evidence({
      path: '/tmp/_v2_meta/markdown/CFFC.md',
      originalPath: null,
      managedPath: null,
      markdownPath: '/tmp/_v2_meta/markdown/CFFC.md',
      canonicalKind: 'raw_file',
      openableKind: 'machine_markdown',
      sourceAvailability: 'machine_readable_only',
      originalAvailable: false,
      machineReadableAvailable: true,
      openOriginalDisabledReason: '原文件已缺失，当前仅有机读稿。',
    }),
  ]);

  assert.equal(cards[0].openPath, '/tmp/_v2_meta/markdown/CFFC.md');
  assert.equal(cards[0].openActionLabel, '查看机读稿');
  assert.equal(cards[0].openableKind, 'machine_markdown');
});
