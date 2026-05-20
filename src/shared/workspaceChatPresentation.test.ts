import test from 'node:test';
import assert from 'node:assert/strict';

import { stripFileCitations } from './workspaceChatPresentation.js';

test('stripFileCitations returns empty for nullish', () => {
  assert.equal(stripFileCitations(null), '');
  assert.equal(stripFileCitations(undefined), '');
  assert.equal(stripFileCitations(''), '');
});

test('stripFileCitations removes English parenthetical (见 strategy.md)', () => {
  const input = '客户在赛道里走"心智素养"路线 (见 strategy.md), 这是核心定位。';
  const out = stripFileCitations(input);
  assert.equal(out, '客户在赛道里走"心智素养"路线, 这是核心定位。');
});

test('stripFileCitations removes Chinese full-width parenthetical （来源: strategy.md, methodology.md）', () => {
  const input = '基于四级飞轮的扩散通路（来源: strategy.md, methodology.md）展开。';
  const out = stripFileCitations(input);
  assert.equal(out, '基于四级飞轮的扩散通路展开。');
});

test('stripFileCitations removes square-bracket citations [strategy.md]', () => {
  const input = '客户当前阶段是规模化复制[strategy.md]。';
  const out = stripFileCitations(input);
  assert.equal(out, '客户当前阶段是规模化复制。');
});

test('stripFileCitations rewrites bare strategy.md → 战略文档', () => {
  const input = '根据 strategy.md 描述, 客户走县域路线。';
  const out = stripFileCitations(input);
  assert.equal(out, '根据 战略文档 描述, 客户走县域路线。');
});

test('stripFileCitations rewrites bare methodology.md → 方法论文档', () => {
  const input = '方法论按 methodology.md 的四级飞轮展开。';
  const out = stripFileCitations(input);
  assert.equal(out, '方法论按 方法论文档 的四级飞轮展开。');
});

test('stripFileCitations rewrites unknown filenames to 客户资料', () => {
  const input = '在 survey.docx 和 notes.pdf 提到过客户访谈结论。';
  const out = stripFileCitations(input);
  assert.equal(out, '在 客户资料 和 客户资料 提到过客户访谈结论。');
});

test('stripFileCitations preserves text without any citations', () => {
  const input = '客户战略很清楚, 走县域路线, 不走 KOL 路线。';
  const out = stripFileCitations(input);
  assert.equal(out, input);
});

test('stripFileCitations does not collapse legitimate parentheticals without filenames', () => {
  const input = '客户走县域路线 (而非 KOL 路线), 这是核心差异。';
  const out = stripFileCitations(input);
  assert.equal(out, '客户走县域路线 (而非 KOL 路线), 这是核心差异。');
});

test('stripFileCitations handles multi-citation paragraph end-to-end', () => {
  const input = '基于 strategy.md、methodology.md 推出 (见 strategy.md), 客户走"心智素养"路线。';
  const out = stripFileCitations(input);
  // strategy.md / methodology.md 替换 + (见 strategy.md) 整段删
  assert.equal(out, '基于 战略文档、方法论文档 推出, 客户走"心智素养"路线。');
});

test('stripFileCitations trims edges and caps blank lines at \\n\\n', () => {
  const input = '   客户走县域路线。   \n\n\n\n   不走 KOL 路线。   ';
  const out = stripFileCitations(input);
  // 头尾 trim, 内部连续空行折叠到 \n\n (行间空格保留无害)
  assert.match(out, /^客户走县域路线。/);
  assert.match(out, /不走 KOL 路线。$/);
  assert.ok(!/\n\n\n/.test(out), `expected ≤2 newlines in a row, got: ${JSON.stringify(out)}`);
});
