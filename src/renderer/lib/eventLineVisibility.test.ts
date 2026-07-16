import { test } from 'node:test';
import assert from 'node:assert/strict';

import { selectEventLinesForList } from './eventLineVisibility.ts';

type Line = {
  id: string;
  status: 'active' | 'done' | 'archived';
  primaryClientId?: string | null;
};

const lines: Line[] = [
  { id: 'active-a', status: 'active', primaryClientId: 'client-a' },
  { id: 'archived-a', status: 'archived', primaryClientId: 'client-a' },
  { id: 'done-b', status: 'done', primaryClientId: 'client-b' },
  { id: 'archived-b', status: 'archived', primaryClientId: 'client-b' },
];

test('默认隐藏已归档事件线，但保留已完成事件线', () => {
  const result = selectEventLinesForList(lines, '__all__', false);

  assert.deepEqual(result.visible.map((line) => line.id), ['active-a', 'done-b']);
  assert.equal(result.archivedCount, 2);
});

test('用户明确选择显示后，已归档事件线恢复到原有顺序', () => {
  const result = selectEventLinesForList(lines, '__all__', true);

  assert.deepEqual(result.visible.map((line) => line.id), lines.map((line) => line.id));
  assert.equal(result.archivedCount, 2);
});

test('项目筛选下仅统计并显示当前项目的已归档事件线', () => {
  const hidden = selectEventLinesForList(lines, 'client-a', false);
  const shown = selectEventLinesForList(lines, 'client-a', true);

  assert.deepEqual(hidden.visible.map((line) => line.id), ['active-a']);
  assert.equal(hidden.archivedCount, 1);
  assert.deepEqual(shown.visible.map((line) => line.id), ['active-a', 'archived-a']);
});

test('没有已归档事件线时归档数量为零，列表保持不变', () => {
  const activeOnly = lines.filter((line) => line.status !== 'archived');
  const result = selectEventLinesForList(activeOnly, '__all__', false);

  assert.equal(result.archivedCount, 0);
  assert.deepEqual(result.visible, activeOnly);
});
